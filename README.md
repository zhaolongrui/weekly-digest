# 科技爱好者集锦

阮一峰《科技爱好者周刊》「文摘」「言论」板块的汇总阅读站：收录 **2018 年第 1 期至最新一期**，逐条保留原文与出处，补一条提炼，按年份分卷。

- 在线地址：https://zhaolongrui.github.io/weekly-digest/
- 全部页面都是**静态 HTML**，正文预渲染，不依赖 JavaScript 也能完整阅读；JS 只负责搜索、板块切换、按期号浏览与复制。兼容老旧手机浏览器（ES5 + 降级 CSS）。

## 页面结构

| 文件 | 内容 |
| --- | --- |
| `index.html` / `科技爱好者集锦.html` | 索引页：9 个年份分卷入口 + 最近收录 |
| `2018.html` … `2026.html` | 各年份分卷（每年 190–310 条，约 320–750 KB） |

分卷是为了老手机：全部 2300+ 条塞进一个页面会到 2.5 MB，低端机打开明显卡顿；按年拆开后每卷都在 1 MB 以内。

分卷页顶部有年份导航可互相跳转，页内可：搜索关键词、只看「文摘」或「言论」、在「按主题 / 按期号」之间切换、单条复制原文与出处。

## 收录范围与两个历史坑

- 周刊第 1 期发布于 **2018-04-22**，至今 400+ 期。
- 「言论」在 2019 年 3 月（第 49 期）之前叫「**本周金句**」，性质相同，已统一按言论收录。
- 早期「文摘」每期有 6–8 条短篇摘录（标题 + 链接 + 一段摘录），2021 年后才固定为每期一篇长文摘。所以 2018–2020 年的卷里，文摘条数明显多于后期。

## 自动更新

每周五 UTC 13:00（北京时间 21:00）由 `.github/workflows/update.yml` 自动运行：

1. `scripts/fetch.py` —— 从已知最大期号往上探测，下载新一期 Markdown（jsDelivr 镜像优先，失败回落直连 GitHub）
2. `scripts/extract.py` —— 抽取「文摘」「言论 / 本周金句」，发布日期取自 `dates.json`（由周刊仓库提交日期生成并缓存）
3. `scripts/classify.py` —— 给新条目补主题与提炼
4. `scripts/build.py` —— 重新渲染索引页与各年份分卷
5. 有变化就自动 commit + push，Pages 随即更新

也可以在仓库 Actions 页面手动点 **Run workflow** 立即更新。

`raw/`（413 期 Markdown 原文）与 `dates.json` 都已入库，CI 无需重新抓取历史。

## 主题与提炼从哪来

- `labels.json` 保存每条的 `{theme, take}`，键为 `期号|板块|序号`。
- 2026 年（第 380–413 期）那 189 条是**人工标注**的；其余 2000+ 条由 `classify.py` 自动生成：关键词打分选主题，**置信不足（<5 分）归入「未归类」**（排在所有主题之后），提炼取正文首句自动摘要。
- 规则分类在人工标签上回测：阈值 5 时覆盖率约 28%、准确率约 74%；阈值 3 时覆盖 61%、准确 64%。为保证不贴错标签，默认取保守阈值——代价是约七成条目落在「未归类」，这是有意为之，不是故障。
- 手工归类：改 `labels.json` 后 push 即可（工作流监听 `labels.json` 变更自动重渲染）。`classify.py` **不会覆盖已有标签**；若解析规则变动导致标签失效，删掉对应条目的 `auto` 标签重跑即可。

想让自动条目的质量追平人工，可以在 `classify.py` 里把 `classify_theme` / `auto_take` 换成 LLM 调用（用仓库 Secret 存 key）。

## 本地运行

```bash
python scripts/fetch.py            # 抓取（含新期探测）
python scripts/extract.py          # 解析 → data.json
python scripts/classify.py         # 补标签 → labels.json
python scripts/build.py            # 渲染 → index.html + <年份>.html
python scripts/verify_static.py    # 静态可读性 + CSS/JS 兼容性 + 数据完整性
node scripts/verify_dom.js         # jsdom 真实 DOM：静态渲染与交互
```

只需 Python 标准库；`verify_dom.js` 需要 jsdom。

## 版权

原文版权归原作者及《科技爱好者周刊》所有，本仓库仅作摘录、归类与阅读整理；「提炼」与主题标签为整理者所加，不代表原作者观点。
