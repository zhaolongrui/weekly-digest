# -*- coding: utf-8 -*-
"""抓取周刊 Markdown 原文：补全已有期号，并自动探测新发布的期。

数据源优先级：jsDelivr 镜像（对国内/CI 都稳定）→ 直连 GitHub。
新增期号通过"从已知最大期号往上试探"发现，最多连续失败 3 次即停。
"""
import os, re, json, time, urllib.request, ssl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
os.makedirs(RAW, exist_ok=True)

START = 380          # 收录的起始期号
MAX_PROBE = 8        # 每次最多往上试探几期
MAX_MISS = 3         # 连续失败几次就认为没有新期

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

MIRRORS = [
    "https://cdn.jsdelivr.net/gh/ruanyf/weekly@master/docs/issue-{n}.md",
    "https://fastly.jsdelivr.net/gh/ruanyf/weekly@master/docs/issue-{n}.md",
    "https://gcore.jsdelivr.net/gh/ruanyf/weekly@master/docs/issue-{n}.md",
    "https://raw.githubusercontent.com/ruanyf/weekly/master/docs/issue-{n}.md",
]
ARCHIVE = "https://www.ruanyifeng.com/blog/weekly/"


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    return urllib.request.urlopen(req, timeout=timeout, context=CTX).read()


def issue_path(n):
    return os.path.join(RAW, "issue-%d.md" % n)


def has_issue(n):
    p = issue_path(n)
    return os.path.exists(p) and os.path.getsize(p) > 2000


def fetch_issue(n):
    """下载第 n 期，成功返回 True"""
    for tpl in MIRRORS:
        try:
            txt = get(tpl.format(n=n)).decode("utf-8", "ignore")
        except Exception:
            continue
        if txt.lstrip().startswith("#"):
            open(issue_path(n), "w", encoding="utf-8").write(txt)
            return True
    return False


def known_issues():
    ns = []
    for f in os.listdir(RAW):
        m = re.match(r"issue-(\d+)\.md$", f)
        if m:
            ns.append(int(m.group(1)))
    return sorted(ns)


def load_date_cache():
    p = os.path.join(ROOT, "dates.json")
    if os.path.exists(p):
        try:
            return {int(k): v for k, v in json.load(open(p, encoding="utf-8")).items()}
        except Exception:
            return {}
    return {}


def save_date_cache(d):
    json.dump({str(k): v for k, v in sorted(d.items())},
              open(os.path.join(ROOT, "dates.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def fetch_commit_date(n):
    """用周刊仓库的提交日期作为发布日期。

    归档页（www.ruanyifeng.com）在 GitHub Actions 里常常取不到，而 api.github.com
    对 Actions 永远可达，因此把 commit 日期作为可靠来源，并缓存进 dates.json。
    """
    url = ("https://api.github.com/repos/ruanyf/weekly/commits"
           "?path=docs/issue-%d.md&per_page=1" % n)
    try:
        arr = json.loads(get(url, timeout=30).decode("utf-8", "ignore"))
        if arr and arr[0].get("commit"):
            return arr[0]["commit"]["committer"]["date"][:10]
    except Exception:
        pass
    return ""


def backfill_dates(nums, limit=40):
    cache = load_date_cache()
    todo = [n for n in nums if not cache.get(n)]
    if not todo:
        return cache, 0
    got = 0
    for n in todo[-limit:]:
        d = fetch_commit_date(n)
        if d:
            cache[n] = d
            got += 1
            print("date", n, d)
        time.sleep(0.2)
    if got:
        save_date_cache(cache)
    return cache, got


def fetch_archive():
    for url in (ARCHIVE,):
        try:
            html = get(url, timeout=60).decode("utf-8", "ignore")
        except Exception as e:
            print("archive FAIL", type(e).__name__)
            return False
        open(os.path.join(ROOT, "archive.html"), "w", encoding="utf-8").write(html)
        print("archive.html", len(html))
        return True
    return False


def main():
    have = known_issues()
    lo = min(have) if have else START
    hi = max(have) if have else START - 1

    # 1) 补全区间内的缺口
    filled = 0
    for n in range(lo, hi + 1):
        if not has_issue(n) and fetch_issue(n):
            filled += 1
            print("fill", n)
            time.sleep(0.15)

    # 2) 往上探测新期
    added, miss = [], 0
    n = hi + 1
    while len(added) + miss < MAX_PROBE and miss < MAX_MISS:
        if fetch_issue(n):
            added.append(n)
            miss = 0
            print("new", n)
        else:
            miss += 1
        n += 1
        time.sleep(0.15)

    fetch_archive()
    now = known_issues()
    cache, got = backfill_dates(now)
    print("filled=%d new=%s dates+=%d total=%d range=%d-%d"
          % (filled, added, got, len(now), now[0], now[-1]))
    return 1 if added else 0


if __name__ == "__main__":
    raise SystemExit(main())
