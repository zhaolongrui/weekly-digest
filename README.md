# 科技爱好者集锦

阮一峰《科技爱好者周刊》「文摘」「言论」板块的汇总阅读页：逐条保留原文与出处，补一条提炼，按主题重新归类。

页面是**单文件静态 HTML**，正文全部预渲染，不依赖 JavaScript 也能完整阅读；JS 只负责搜索、板块切换、按期号浏览与复制。兼容老旧手机浏览器（ES5 + 降级 CSS）。

- 在线地址：仓库开启 GitHub Pages 后为 `https://<用户名>.github.io/<仓库名>/`
- 正式文件名：`科技爱好者集锦.html`；同时输出 `index.html` 作为 Pages 根页

## 自动更新

每周五 UTC 13:00（北京时间 21:00）由 `.github/workflows/update.yml` 自动运行：

1. `scripts/fetch.py` —— 从已知最大期号往上探测，下载新一期 Markdown（jsDelivr 镜像优先，失败回落直连 GitHub）
2. `scripts/extract.py` —— 抽取「文摘」「言论」，并从归档页解码每期发布日期
3. `scripts/classify.py` —— 给新条目补主题与提炼
4. `scripts/build.py` —— 重新渲染页面
5. 有变化就自动 commit + push，Pages 随即更新

也可以在仓库 Actions 页面手动点 **Run workflow** 立即更新。

## 主题与提炼从哪来

- `labels.json` 保存每条的 `{theme, take}`，键为 `期号|板块|序号`。现有 189 条是人工标注的。
- 新条目由 `classify.py` 自动补：关键词打分选主题，**置信不足（<5 分）则归入「最新更新」待归类**，提炼取正文首句自动摘要。
- 实测规则分类在人工标签上的表现：阈值 5 时覆盖约 28%、准确率约 74%；阈值 3 时覆盖 61%、准确 64%。为了保证不贴错标签，默认取保守阈值 5。
- 手工归类：改 `labels.json` 后 push 即可（工作流监听 `labels.json` 变更自动重渲染）。`classify.py` **不会覆盖已有标签**。

想让新增条目的质量追平人工，可以在 `classify.py` 里把 `classify_theme` / `auto_take` 换成 LLM 调用（用仓库 Secret 存 key）。

## 本地运行

```bash
python scripts/fetch.py      # 抓取（含新期探测）
python scripts/extract.py    # 解析 → data.json
python scripts/classify.py   # 补标签 → labels.json
python scripts/build.py      # 渲染 → 科技爱好者集锦.html + index.html
```

只需 Python 标准库，无第三方依赖。

## 版权

原文版权归原作者及《科技爱好者周刊》所有，本仓库仅作摘录、归类与阅读整理；「提炼」与主题标签为整理者所加，不代表原作者观点。
