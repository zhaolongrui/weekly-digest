# -*- coding: utf-8 -*-
"""全量下载 1..N 期周刊 Markdown 到 raw/，并统计每期的板块构成。

只用于一次性摸底；正式抓取请用 fetch.py。
"""
import os, ssl, json, time, collections
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
os.makedirs(RAW, exist_ok=True)

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
MIRRORS = [
    "https://cdn.jsdelivr.net/gh/ruanyf/weekly@master/docs/issue-%d.md",
    "https://fastly.jsdelivr.net/gh/ruanyf/weekly@master/docs/issue-%d.md",
    "https://gcore.jsdelivr.net/gh/ruanyf/weekly@master/docs/issue-%d.md",
    "https://raw.githubusercontent.com/ruanyf/weekly/master/docs/issue-%d.md",
]


def get(n, tries=2):
    for m in MIRRORS:
        for _ in range(tries):
            try:
                req = urllib.request.Request(m % n, headers={"User-Agent": UA})
                d = urllib.request.urlopen(req, timeout=30, context=CTX).read()
                d = d.decode("utf-8", "ignore")
                if len(d) > 200:
                    return d
            except Exception:
                time.sleep(0.4)
    return None


def one(n):
    p = os.path.join(RAW, "issue-%d.md" % n)
    if os.path.exists(p) and os.path.getsize(p) > 200:
        t = open(p, encoding="utf-8").read()
    else:
        t = get(n)
        if not t:
            return n, None
        open(p, "w", encoding="utf-8").write(t)
    heads = [l.lstrip("# ").strip() for l in t.split("\n")
             if l.startswith("##") and not l.startswith("###")]
    return n, heads


def main():
    lo, hi = 1, 413
    res = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        for n, heads in ex.map(one, range(lo, hi + 1)):
            res[n] = heads
    missing = [n for n, v in res.items() if not v]
    open(os.path.join(ROOT, "scan_sections.json"), "w", encoding="utf-8").write(
        json.dumps({str(k): v for k, v in sorted(res.items()) if v},
                   ensure_ascii=False, indent=0))

    print("下载 %d/%d，缺失 %s" % (len(res) - len(missing), len(res), missing[:10]))

    cnt = collections.Counter()
    for v in res.values():
        for h in v or []:
            cnt[h] += 1
    print("\n板块出现频次（全部 %d 期）:" % len(res))
    for k, v in cnt.most_common(16):
        print("   %-10s %d 期" % (k, v))

    def has(n, kw):
        return any(kw in h for h in (res.get(n) or []))

    nd = [n for n in range(lo, hi + 1) if not has(n, "文摘")]
    nq = [n for n in range(lo, hi + 1) if not (has(n, "言论") or has(n, "金句"))]
    print("\n无「文摘」的期 (%d):" % len(nd), nd[:20])
    print("既无「言论」也无「金句」的期 (%d):" % len(nq), nq[:20])

    # 「本周金句」与「言论」的分界
    jin = [n for n in range(lo, hi + 1) if has(n, "金句")]
    yan = [n for n in range(lo, hi + 1) if has(n, "言论")]
    print("\n本周金句: %d 期, 范围 %d-%d" % (len(jin), jin[0], jin[-1]))
    print("言论:     %d 期, 范围 %d-%d" % (len(yan), yan[0], yan[-1]))


if __name__ == "__main__":
    main()
