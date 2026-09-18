# -*- coding: utf-8 -*-
"""渲染汇总页：读 data.json（原文）+ labels.json（主题与提炼），生成静态 HTML。

全部内容静态预渲染，无脚本也能完整阅读；脚本只负责搜索、板块切换、按期号视图与复制。
输出两份同名内容：科技爱好者集锦.html（正式名）与 index.html（GitHub Pages 根页）。
"""
import os, re, json, html, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import THEMES, PENDING, key  # noqa: E402

THEME_COLOR = {t[0]: t[1] for t in THEMES}
THEME_DESC = {t[0]: t[2] for t in THEMES}


def esc(s):
    return html.escape(s, quote=False)


def inline(s):
    s = esc(s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


def md_to_html(text):
    lines = text.split("\n")
    out, buf, in_quote = [], [], False

    def flush():
        nonlocal buf
        if buf:
            body = "<br>".join(inline(x) for x in buf if x.strip())
            if body:
                out.append('<p class="qblock">%s</p>' % body if in_quote else "<p>%s</p>" % body)
            buf = []

    for ln in lines:
        st = ln.strip()
        is_q = st.startswith("> ")
        if is_q != in_quote:
            flush()
            in_quote = is_q
        buf.append(st[2:] if is_q and len(st) > 2 else ln)
        if not st:
            flush()
    flush()
    return "".join(out)


def source_html(src):
    if not src:
        return ""
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                  r'<a href="\2" target="_blank" rel="noopener">\1</a>', esc(src))


def card_static(it):
    scode = "0" if it["section"] == "文摘" else "1"
    cid = "c%d-%s-%d" % (it["issue"], scode, it["idx"])
    color = THEME_COLOR.get(it["theme"], "#888")
    head = ""
    if it["section"] == "文摘":
        t = esc(it["title"])
        head = ('<div class="title">'
                + ('<a href="%s" target="_blank" rel="noopener">%s</a>' % (it["url"], t) if it["url"] else t)
                + "</div>")
    body = ('<div class="body">%s</div>' % md_to_html(it["text"])) if it["section"] == "文摘" \
        else ('<blockquote class="quote">%s</blockquote>' % md_to_html(it["text"]))
    src = source_html(it["source"])
    return (
        '<div class="card" id="%s" data-i="%d" data-s="%s" data-x="%d">'
        '<div class="meta">'
        '<span class="iss">第 %d 期</span><span class="date">%s</span>'
        '<span class="sec2">%s</span>'
        '<span class="tag" style="background:%s">%s</span>'
        '<button class="copy" data-copy="%d|%s|%d">复制</button>'
        '</div>%s%s'
        '<div class="take"><b>提炼</b>%s</div>%s</div>'
    ) % (cid, it["issue"], it["section"], it["idx"],
         it["issue"], it["date"], it["section"], color, it["theme"],
         it["issue"], it["section"], it["idx"],
         head, body, esc(it["take"]),
         '<div class="src">— %s</div>' % src if src else "")


def main():
    data = json.load(open(os.path.join(ROOT, "data.json"), encoding="utf-8"))
    labels = json.load(open(os.path.join(ROOT, "labels.json"), encoding="utf-8"))

    items = []
    for it in data["items"]:
        lb = labels.get(key(it))
        if not lb:
            continue
        it["theme"] = lb["theme"]
        it["take"] = lb["take"]
        items.append(it)

    issues = sorted({i["issue"] for i in items})
    lo, hi = issues[0], issues[-1]
    dates = sorted(i["date"] for i in items if i["date"])
    d0, d1 = (dates[0], dates[-1]) if dates else ("", "")
    n_dig = sum(1 for i in items if i["section"] == "文摘")
    n_quo = len(items) - n_dig
    year = d1[:4] if d1 else ""
    range_txt = "第 %d–%d 期" % (lo, hi)
    span = "%s 至 %s" % (d0, d1) if d0 else ""

    title = "科技爱好者集锦 · 文摘与言论汇总（%s）" % range_txt
    sub = ("阮一峰《科技爱好者周刊》%s%s的「文摘」与「言论」板块，共 %d 条（文摘 %d、言论 %d），"
           "逐条保留原文、补一条提炼，并按主题重新归类。"
           % (year + "年" if year else "", range_txt, len(items), n_dig, n_quo))
    footer = "数据来源：阮一峰《科技爱好者周刊》开源仓库（%s%s）的「文摘」「言论」板块原文。" % (
        range_txt, "，%s" % span if span else "")

    # 按主题分组；「最新更新」（未归类）排在最前，便于看到新增内容
    pending = [i for i in items if i["theme"] == PENDING]
    list_html = ""
    if pending:
        pending.sort(key=lambda x: (-x["issue"], x["idx"]))
        list_html += ('<div class="group" data-theme="%s"><div class="ghead">'
                      '<h3><span style="color:#b45309">●</span> %s</h3>'
                      '<span class="gdesc">最近新收录、尚未归入具体主题的条目（提炼为自动摘要）。</span>'
                      '<span class="gn">%d 条</span></div>%s</div>') % (
            PENDING, PENDING, len(pending), "".join(card_static(i) for i in pending))

    order = [t[0] for t in THEMES]
    for name in order:
        g = [i for i in items if i["theme"] == name]
        if not g:
            continue
        g.sort(key=lambda x: (-x["issue"], x["idx"]))
        list_html += ('<div class="group" data-theme="%s"><div class="ghead">'
                      '<h3><span style="color:%s">●</span> %s</h3>'
                      '<span class="gdesc">%s</span><span class="gn">%d 条</span></div>%s</div>') % (
            esc(name), THEME_COLOR[name], esc(name), esc(THEME_DESC[name]),
            len(g), "".join(card_static(i) for i in g))

    light = [{k: it[k] for k in ("issue", "date", "section", "idx", "title", "url",
                                 "source", "text", "theme", "take")} for it in items]
    payload = {"items": light, "issues": data["issues"],
               "themes": [{"name": n, "color": c, "desc": d} for n, c, d in THEMES]
                         + [{"name": PENDING, "color": "#b45309",
                             "desc": "最近新收录、尚未归入具体主题的条目。"}]}

    tpl = open(os.path.join(ROOT, "scripts", "template.html"), encoding="utf-8").read()
    out = (tpl.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False))
              .replace("/*__LIST__*/", list_html)
              .replace("/*__TITLE__*/", esc(title))
              .replace("/*__SUB__*/", esc(sub))
              .replace("/*__FOOTER__*/", footer))

    for name in ("科技爱好者集锦.html", "index.html"):
        open(os.path.join(ROOT, name), "w", encoding="utf-8").write(out)
    print("written:", len(out), "bytes | 条目", len(items),
          "| 期号 %d-%d | 分组" % (lo, hi), out.count('class="group"'))
    print("残留占位符:", [k for k in ("__DATA__", "__LIST__", "__TITLE__", "__SUB__", "__FOOTER__") if k in out])


if __name__ == "__main__":
    main()
