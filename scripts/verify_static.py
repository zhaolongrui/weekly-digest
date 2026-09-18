# -*- coding: utf-8 -*-
"""冒烟检查：静态可读性（无脚本也完整）、CSS/JS 兼容性、数据完整性。

检查对象：index.html 与所有 <年份>.html。用法: python scripts/verify_static.py
"""
import os, re, json, subprocess, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = r"C:\Users\hp\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"

CSS_BAN = {"CSS 变量": r"var\(--", "吸顶定位": r"position:\s*sticky", "毛玻璃": r"backdrop-filter",
           "网格布局": r"display:\s*(inline-)?grid", "grid-template": r"grid-template-columns",
           "flex": r"display:\s*flex", "gap": r"^\s*gap:", "rem": r"\drem"}
# 反引号检查只针对脚本代码，数据段（DATA）里的正文可能含行内代码标记，需先剔除
JS_BAN = {"let": r"\blet\s+[A-Za-z_$]", "const": r"\bconst\s+[A-Za-z_$]", "箭头函数": r"=>",
          "模板字符串": r"`", "Set/Map": r"new\s+(Set|Map)\(", "Promise": r"new\s+Promise\(",
          "closest": r"\.closest\(", "fetch": r"\bfetch\(", "class": r"\bclass\s+[A-Za-z]"}

fail = 0


def scan(label, text, rules):
    global fail
    bad = ["%s×%d" % (n, len(re.findall(p, text, re.M)))
           for n, p in rules.items() if re.findall(p, text, re.M)]
    if bad:
        fail += 1
    return "全部通过" if not bad else "、".join(bad)


def strip_css_comments(s):
    return re.sub(r"/\*.*?\*/", "", s, flags=re.S)


files = ["index.html"] + sorted(glob.glob(os.path.join(ROOT, "[0-9][0-9][0-9][0-9].html")))
files = [f if os.path.isabs(f) else os.path.join(ROOT, f) for f in files]

for P in files:
    t = open(P, encoding="utf-8").read()
    name = os.path.basename(P)
    print("\n===== %s  (%.0f KB) =====" % (name, len(t.encode("utf-8")) / 1024))

    has_script = "<script>" in t
    body = t[:t.index("<script>")] if has_script else t
    css = strip_css_comments(t[t.index("<style>") + 7: t.index("</style>")])

    print("  静态卡片:", body.count('class="card"'),
          "| 分组:", body.count('class="group"'),
          "| 提炼行:", body.count('class="take"'),
          "| 出处行:", body.count('class="src"'))
    print("  已移除(统计/速览/芯片):",
          body.count('class="stat"'), body.count('class="tcard"'), body.count('class="chip'))
    ph = [k for k in ("__DATA__", "__LIST__", "__TITLE__", "__SUB__", "__FOOTER__",
                      "__YEARS__", "__CSS__", "__VOLS__", "__NOTE__", "__RECENT__") if k in t]
    if ph:
        fail += 1
    print("  占位符残留:", ph or "无")
    print("  CSS 兼容性:", scan("css", css, CSS_BAN))

    if not has_script:
        print("  JS: 本页无脚本（纯静态）")
        continue

    js = t[t.index("<script>") + 8: t.rindex("</script>")]
    js_code = re.sub(r"var DATA = \{[\s\S]*?\};\n", "var DATA = {};\n", js, count=1)
    print("  JS ES5 兼容性:", scan("js", js_code, JS_BAN))

    tmp = os.path.join(ROOT, "_check.js")
    open(tmp, "w", encoding="utf-8").write(js)
    r = subprocess.run([NODE, "--check", tmp], capture_output=True, text=True, encoding="utf-8")
    print("  node --check:", "通过" if r.returncode == 0 else "失败")
    if r.returncode != 0:
        fail += 1
        print(r.stderr[:500])
    os.remove(tmp)

    i = js.index("var DATA = ") + len("var DATA = ")
    d, _ = json.JSONDecoder().raw_decode(js[i:])
    miss = [x["issue"] for x in d["items"]
            if not x.get("take") or not x.get("theme") or not x.get("text")]
    if miss:
        fail += 1
    print("  数据:", len(d["items"]), "条 /", len(d["themes"]), "主题 /", len(d["issues"]), "期 | 缺字段:", miss or "无")
    print("  标题:", re.search(r"<title>(.*?)</title>", t).group(1))

print("\n" + ("全部通过" if fail == 0 else "失败 %d 项" % fail))
sys.exit(0 if fail == 0 else 1)
