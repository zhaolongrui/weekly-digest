# -*- coding: utf-8 -*-
"""从 raw/ 下的周刊 Markdown 中抽取「文摘」「言论」并解析发布日期，输出 data.json。

扫描范围由 raw/ 目录里实际存在的文件决定，不写死期号，新期下载后自动纳入。
"""
import os, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")


def decode_cfemail(hexstr):
    try:
        b = bytes.fromhex(hexstr)
        key = b[0]
        return "".join(chr(c ^ key) for c in b[1:])
    except Exception:
        return ""


def load_dates():
    """发布日期：dates.json（缓存，CI 里稳定可得）为底，归档页补充缺失项。

    归档页 www.ruanyifeng.com 在 GitHub Actions 里可能取不到，所以缓存是主数据源；
    本地有归档页时用它补齐尚未缓存的期号。
    """
    out = {}
    cp = os.path.join(ROOT, "dates.json")
    if os.path.exists(cp):
        try:
            out = {int(k): v for k, v in json.load(open(cp, encoding="utf-8")).items()
                   if str(v).startswith("20")}
        except Exception:
            out = {}
    p = os.path.join(ROOT, "archive.html")
    if not os.path.exists(p):
        return out
    t = open(p, encoding="utf-8", errors="ignore").read()
    for m in re.finditer(
        r'href="https://www\.ruanyifeng\.com/blog/(\d{4})/(\d{2})/weekly-issue-(\d+)\.html"'
        r'(.{0,900}?)</li>',
        t, re.S,
    ):
        year, month, num, tail = m.group(1), m.group(2), m.group(3), m.group(4)
        cf = re.search(r'data-cfemail="([0-9a-f]+)"', tail)
        date = ""
        if cf:
            mm = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", decode_cfemail(cf.group(1)))
            if mm:
                date = "-".join(mm.groups())
        num = int(num)
        if num not in out:
            out[num] = date or (year + "-" + month)
    return out


def section_text(text, start_head, end_heads=None):
    """截取某个二级板块的正文。

    end_heads 为 None 时，终止于**任意下一个二级标题**——历期板块名变化很多
    （本周图片 / 新奇 / 历史上的本周 / 封面图…），枚举终止词容易漏，导致把后面
    板块的内容误吞进来，所以默认一律按「下一个 ##」截断。
    """
    m = re.search(r"^##\s*" + start_head + r"\s*$", text, re.M)
    if not m:
        return None
    s, nxt = m.end(), len(text)
    if end_heads is None:
        mm = re.search(r"^##\s+\S", text[s:], re.M)
        if mm:
            nxt = s + mm.start()
    else:
        for h in end_heads:
            mm = re.search(r"^##\s*" + h + r"\s*$", text[s:], re.M)
            if mm:
                nxt = min(nxt, s + mm.start())
    return text[s:nxt]


# 板块终止标题：遇到其中任意一个即认为当前板块结束
DIGEST_ENDS = ["言论", "本周金句", "往年回顾", "订阅", "图片", "资源", "工具",
               "文章", "科技动态", "资讯", "新奇", "软件", "封面图", "历史上的本周"]
QUOTE_ENDS = ["往年回顾", "订阅", "图片", "资源", "工具", "文章", "科技动态",
              "资讯", "文摘", "新奇", "软件", "封面图", "历史上的本周"]
JINJU_ENDS = ["往年回顾", "订阅", "欢迎订阅", "图片", "资源", "工具", "文章",
              "新奇", "软件", "历史上的本周"]

NUM_RE = re.compile(r"^(\d+)、\s*(.*)$")
IMG_RE = re.compile(r"^!\[\]\(.*\)\s*$")
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def split_entries(block):
    entries, cur = [], None
    for line in block.split("\n"):
        if IMG_RE.match(line.strip()):
            continue
        m = NUM_RE.match(line.strip())
        if m:
            if cur:
                entries.append(cur)
            cur = [int(m.group(1)), [m.group(2)]]
        elif cur is not None:
            cur[1].append(line)
    if cur:
        entries.append(cur)
        return entries
    # 无编号的老排版（如第 1 期「本周金句」）：整块视为一条
    body = clean_lines(block.split("\n"))
    return [[1, body]] if body else []


def clean_lines(lines):
    out = [l.rstrip() for l in lines]
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def parse_issue(n, dates):
    p = os.path.join(RAW, "issue-%d.md" % n)
    if not os.path.exists(p):
        return None, []
    t = open(p, encoding="utf-8").read()

    h1 = re.search(r"^#\s*(.+)$", t, re.M)
    title = h1.group(1).strip() if h1 else "第 %d 期" % n
    mt = re.search(r"（第\s*(\d+)\s*期）(?:：|:)?\s*(.*)$", title)
    issue_no = int(mt.group(1)) if mt else n
    subject = mt.group(2).strip() if mt else title
    items = []

    blk = section_text(t, "文摘")
    if blk:
        for idx, lines in split_entries(blk):
            lines = clean_lines(lines)
            if not lines:
                continue
            lm = LINK_RE.search(lines[0])
            if lm:
                ti, url = lm.group(1), lm.group(2)
            else:
                ti, url = re.sub(r"[\[\]]", "", lines[0]).strip() or "(无题)", ""
            items.append({
                "issue": issue_no, "date": dates.get(issue_no, ""), "subject": subject,
                "section": "文摘", "idx": idx, "title": ti, "url": url,
                "source": url, "text": "\n".join(lines[1:]).strip(),
            })

    # 言论：2019-03 之前该板块名为「本周金句」，内容性质相同，统一归为「言论」
    got_quote = False
    for head in ("言论", "本周金句"):
        if got_quote:
            break
        blk = section_text(t, head)
        if not blk:
            continue
        got_quote = True
        for idx, lines in split_entries(blk):
            lines = clean_lines(lines)
            if not lines:
                continue
            src, srcline = "", -1
            for i, l in enumerate(lines):
                if l.strip().startswith("--"):
                    src, srcline = l.strip().lstrip("-").strip(), i
                    break
            quote = clean_lines([l for i, l in enumerate(lines) if i != srcline])
            lm = LINK_RE.search(src)
            items.append({
                "issue": issue_no, "date": dates.get(issue_no, ""), "subject": subject,
                "section": "言论", "idx": idx, "title": "", "url": lm.group(2) if lm else "",
                "source": src, "text": "\n".join(quote).strip(),
            })

    return {"issue": issue_no, "title": title, "subject": subject,
            "date": dates.get(issue_no, "")}, items


def main():
    nums = sorted(int(m.group(1)) for m in
                  (re.match(r"issue-(\d+)\.md$", f) for f in os.listdir(RAW)) if m)
    dates = load_dates()
    issues, allitems = [], []
    for n in nums:
        meta, items = parse_issue(n, dates)
        if meta:
            issues.append(meta)
        allitems.extend(i for i in items if i["text"].strip())
    issues.sort(key=lambda x: x["issue"])
    allitems.sort(key=lambda x: (x["issue"], 0 if x["section"] == "文摘" else 1, x["idx"]))
    json.dump({"issues": issues, "items": allitems},
              open(os.path.join(ROOT, "data.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("issues=%d items=%d (文摘 %d / 言论 %d)" % (
        len(issues), len(allitems),
        sum(1 for i in allitems if i["section"] == "文摘"),
        sum(1 for i in allitems if i["section"] == "言论")))


if __name__ == "__main__":
    main()
