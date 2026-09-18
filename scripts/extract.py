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
    """发布日期：优先用 dates.json（来自周刊仓库提交日期，稳定可得），
    缺失时回落归档页（日期被 Cloudflare 邮箱保护混淆，按首字节 XOR 解码）。"""
    out = {}
    cp = os.path.join(ROOT, "dates.json")
    if os.path.exists(cp):
        try:
            out = {int(k): v for k, v in json.load(open(cp, encoding="utf-8")).items()}
        except Exception:
            out = {}
    p = os.path.join(ROOT, "archive.html")
    if not os.path.exists(p):
        return out
    t = open(p, encoding="utf-8", errors="ignore").read()
    out = {}
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


def section_text(text, start_head, end_heads):
    m = re.search(r"^##\s*" + start_head + r"\s*$", text, re.M)
    if not m:
        return None
    s, nxt = m.end(), len(text)
    for h in end_heads:
        mm = re.search(r"^##\s*" + h + r"\s*$", text[s:], re.M)
        if mm:
            nxt = min(nxt, s + mm.start())
    return text[s:nxt]


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

    blk = section_text(t, "文摘", ["言论", "往年回顾", "订阅", "图片", "资源"])
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

    blk = section_text(t, "言论", ["往年回顾", "订阅", "图片", "资源", "文摘"])
    if blk:
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
        allitems.extend(items)
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
