# -*- coding: utf-8 -*-
"""渲染汇总页：读 data.json（原文）+ labels.json（主题与提炼），生成静态 HTML。

全部内容静态预渲染，无脚本也能完整阅读；脚本只负责搜索、板块切换、按期号视图与复制。

输出：
  index.html / 科技爱好者集锦.html —— 索引页（按年分卷入口 + 最近收录）
  <年份>.html（如 2018.html）      —— 该年份分卷正文
"""
import os, re, json, html, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import THEMES, PENDING, key  # noqa: E402

THEME_COLOR = {t[0]: t[1] for t in THEMES}
THEME_DESC = {t[0]: t[2] for t in THEMES}
PENDING_COLOR = "#8a929c"
PENDING_DESC = "关键词置信不足，未归入具体主题；新收录的条目也会先落在这里。"
# 主题色写成 class（t0/t1…），避免每张卡片内联 style，减小文件体积
ALL_THEMES = list(THEMES) + [(PENDING, PENDING_COLOR, PENDING_DESC)]
THEME_CLASS = {t[0]: "t%d" % i for i, t in enumerate(ALL_THEMES)}
TAGS_CSS = "".join(".tag.%s{background:%s}" % (THEME_CLASS[t[0]], t[1]) for t in ALL_THEMES)


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
    tcls = THEME_CLASS.get(it["theme"], THEME_CLASS[PENDING])
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
        '<div class="card" id="%s" data-i="%d" data-s="%s" data-x="%d" data-t="%s">'
        '<div class="meta">'
        '<span class="iss">第 %d 期</span><span class="date">%s</span>'
        '<span class="sec2">%s</span>'
        '<span class="tag %s">%s</span>'
        '<button class="copy" data-copy="%d|%s|%d">复制</button>'
        '</div>%s%s'
        '<div class="take"><b>提炼</b>%s</div>%s</div>'
    ) % (cid, it["issue"], it["section"], it["idx"], esc(it["theme"]),
         it["issue"], it["date"], it["section"], tcls, esc(it["theme"]),
         it["issue"], it["section"], it["idx"],
         head, body, esc(it["take"]),
         '<div class="src">— %s</div>' % src if src else "")


def group_html(name, color, desc, items):
    return ('<div class="group" data-theme="%s"><div class="ghead">'
            '<h3><span style="color:%s">●</span> %s</h3>'
            '<span class="gdesc">%s</span><span class="gn">%d 条</span></div>%s</div>') % (
        esc(name), color, esc(name), esc(desc), len(items),
        "".join(card_static(i) for i in items))


def theme_list_html(items):
    """按主题分组：正常主题按 THEMES 顺序，「未归类」永远排在最后"""
    out = []
    for name, color, desc in THEMES:
        g = [i for i in items if i["theme"] == name]
        if g:
            g.sort(key=lambda x: (-x["issue"], x["idx"]))
            out.append(group_html(name, color, desc, g))
    rest = [i for i in items if i["theme"] == PENDING]
    if rest:
        rest.sort(key=lambda x: (-x["issue"], x["idx"]))
        out.append(group_html(PENDING, PENDING_COLOR, PENDING_DESC, rest))
    return "".join(out)


def issue_groups_html(items, meta_by_issue):
    """「按期号」视图的静态骨架：只有分组头，卡片由脚本搬进来（不克隆、不重建）"""
    by = collections.OrderedDict()
    for it in items:
        by.setdefault(it["issue"], []).append(it)
    out = []
    for n in sorted(by, reverse=True):
        m = meta_by_issue.get(n, {})
        out.append(
            '<div class="group" data-iss="%d"><div class="ghead">'
            '<h3>第 %d 期</h3><span class="gdesc">%s　%s</span>'
            '<span class="gn">%d 条</span></div></div>'
            % (n, n, esc(m.get("date", "")), esc(m.get("subject", "")), len(by[n])))
    return "".join(out)


def years_html(years, cur=None):
    a = ['<a class="idx" href="index.html">总览</a>']
    for y in years:
        a.append('<a href="%d.html"%s>%d</a>' % (y, ' class="on"' if y == cur else "", y))
    return "".join(a)


def render_volume(items, years, year, css_tpl, tpl, meta_by_issue):
    issues = sorted({i["issue"] for i in items})
    lo, hi = issues[0], issues[-1]
    dates = sorted(i["date"] for i in items if i["date"])
    d0, d1 = (dates[0], dates[-1]) if dates else ("", "")
    n_dig = sum(1 for i in items if i["section"] == "文摘")
    n_quo = len(items) - n_dig

    title = "科技爱好者集锦 · %d 年（第 %d–%d 期）" % (year, lo, hi)
    sub = ("阮一峰《科技爱好者周刊》%d 年共 %d 期（第 %d–%d 期，%s 至 %s），"
           "收录「文摘」%d 条、「言论」%d 条，合计 %d 条。原文逐条保留，另附主题与一句话提炼。"
           % (year, len(issues), lo, hi, d0, d1, n_dig, n_quo, len(items)))
    footer = ("数据来源：阮一峰《科技爱好者周刊》开源仓库 %d 年第 %d–%d 期（%s 至 %s）"
              "的「文摘」「言论」板块原文。" % (year, lo, hi, d0, d1))

    out = (tpl.replace("/*__LIST__*/", theme_list_html(items))
              .replace("/*__IGROUPS__*/", issue_groups_html(items, meta_by_issue))
              .replace("/*__TAGS__*/", TAGS_CSS)
              .replace("/*__TITLE__*/", esc(title))
              .replace("/*__SUB__*/", esc(sub))
              .replace("/*__FOOTER__*/", footer)
              .replace("/*__YEARS__*/", years_html(years, year)))
    return out, len(items)


def main():
    data = json.load(open(os.path.join(ROOT, "data.json"), encoding="utf-8"))
    labels = json.load(open(os.path.join(ROOT, "labels.json"), encoding="utf-8"))

    known = {t[0] for t in THEMES}
    items = []
    for it in data["items"]:
        lb = labels.get(key(it))
        if not lb:
            continue
        # 兜底：主题名不在当前体系中（改名、旧标签残留）时归入「未归类」，绝不丢条目
        it["theme"] = lb["theme"] if lb["theme"] in known else PENDING
        it["take"] = lb["take"]
        items.append(it)
    items.sort(key=lambda x: (x["date"] or "", x["issue"],
                              0 if x["section"] == "文摘" else 1, x["idx"]))

    by_year = collections.OrderedDict()
    for it in items:
        by_year.setdefault(it["date"][:4] or "未知", []).append(it)
    # 新→旧：索引页分卷入口、分卷顶部年份导航均由这一顺序决定
    years = sorted((int(y) for y in by_year if y != "未知"), reverse=True)

    tpl = open(os.path.join(ROOT, "scripts", "template.html"), encoding="utf-8").read()
    itpl = open(os.path.join(ROOT, "scripts", "index_template.html"), encoding="utf-8").read()
    css = tpl[tpl.index("<style>") + 7:tpl.index("</style>")].replace("/*__TAGS__*/", TAGS_CSS)

    meta_by_issue = {m["issue"]: m for m in data["issues"]}

    total = 0
    for y in years:
        out, n = render_volume(by_year[str(y)], years, y, css, tpl, meta_by_issue)
        open(os.path.join(ROOT, "%d.html" % y), "w", encoding="utf-8").write(out)
        total += n
        print("  %d.html  %d 条  %.0f KB" % (y, n, len(out.encode("utf-8")) / 1024))

    # ---- 索引页 ----
    all_issues = sorted({i["issue"] for i in items})
    all_dates = sorted(i["date"] for i in items if i["date"])
    n_dig = sum(1 for i in items if i["section"] == "文摘")
    n_quo = len(items) - n_dig
    maxv = max(len(by_year[str(y)]) for y in years)

    vols = []
    for y in years:
        g = by_year[str(y)]
        iss = sorted({i["issue"] for i in g})
        d = sorted(i["date"] for i in g if i["date"])
        nd = sum(1 for i in g if i["section"] == "文摘")
        vols.append(
            '<a class="vol" href="%d.html"><b>%d 年</b>'
            '<span class="rng">第 %d–%d 期 · %s 至 %s</span>'
            '<span class="cnt">%d 条 · 文摘 %d · 言论 %d</span>'
            '<span class="bar2"><i style="width:%d%%"></i></span></a>'
            % (y, y, iss[0], iss[-1], d[0][5:], d[-1][5:], len(g), nd, len(g) - nd,
               round(len(g) / maxv * 100)))
    recent = sorted(items, key=lambda x: (-x["issue"], 0 if x["section"] == "文摘" else 1, x["idx"]))[:12]

    old, new = years[-1], years[0]
    title = "科技爱好者集锦 · 阮一峰周刊文摘与言论汇总（%d–%d）" % (old, new)
    sub = ("阮一峰《科技爱好者周刊》第 %d–%d 期（%s 至 %s）的「文摘」与「言论」板块，"
           "共 %d 条（文摘 %d、言论 %d），按年份分为 %d 卷。"
           % (all_issues[0], all_issues[-1], all_dates[0], all_dates[-1],
              len(items), n_dig, n_quo, len(years)))
    note = ("每卷是独立页面，老手机打开也无压力：点年份进入后可搜索关键词、只看文摘或言论、"
            "在「按主题」与「按期号」之间切换。<br>"
            "2019 年 3 月（第 49 期）之前，「言论」板块名为「本周金句」，性质相同，已统一按言论收录；"
            "早期的「文摘」每期有多条短篇摘录，后期才固定为每期一篇长文摘。")
    footer = ("数据来源：阮一峰《科技爱好者周刊》开源仓库第 %d–%d 期（%s 至 %s）"
              "的「文摘」「言论」板块原文。"
              % (all_issues[0], all_issues[-1], all_dates[0], all_dates[-1]))

    idx = (itpl.replace("/*__CSS__*/", css)
               .replace("/*__TITLE__*/", esc(title))
               .replace("/*__SUB__*/", esc(sub))
               .replace("/*__NOTE__*/", note)
               .replace("/*__VOLS__*/", "".join(vols))
               .replace("/*__RECENT__*/", "".join(card_static(i) for i in recent))
               .replace("/*__FOOTER__*/", footer))

    for name in ("index.html", "科技爱好者集锦.html"):
        open(os.path.join(ROOT, name), "w", encoding="utf-8").write(idx)

    print("index.html  索引页 %.0f KB | 共 %d 条 / %d 卷 | 期号 %d-%d"
          % (len(idx.encode("utf-8")) / 1024, total, len(years), all_issues[0], all_issues[-1]))
    ph = ("__DATA__", "__LIST__", "__IGROUPS__", "__TAGS__", "__TITLE__", "__SUB__",
          "__FOOTER__", "__YEARS__", "__CSS__", "__VOLS__", "__NOTE__", "__RECENT__")
    print("残留占位符:", [k for k in ph if ("/*" + k + "*/") in idx])


if __name__ == "__main__":
    main()
