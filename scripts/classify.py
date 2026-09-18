# -*- coding: utf-8 -*-
"""给新条目补主题标签与一句话提炼。

已有的人工标签存在 labels.json（键为 "期号|板块|序号"），本脚本只补**缺失**的条目，
不覆盖人工成果。新增条目采用确定性规则：关键词打分选主题 + 抽取式首句摘要。
（若想让新增条目的提炼质量追平人工，可在 CI 里接入 LLM，见 README。）
"""
import os, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

THEMES = [
    ("AI 冲击与反思", "#c2410c", "AI 到底夺走了什么：能力、判断力，还是对工作的意义感。"),
    ("AI 编程实践", "#0369a1", "怎么用 AI 写代码：上下文工程、agent、值班、模型选型。"),
    ("编程与工程", "#0f766e", "抽象、复杂性、代码质量、语言选择——AI 时代这些老问题一个都没消失。"),
    ("职业与职场", "#7c3aed", "晋升、退休、合同工、大厂政治。工作本身的安全感正在被重新评估。"),
    ("创业与商业", "#b91c1c", "团队规模、商业模式、估值叙事与泡沫——资本如何追逐一场技术热潮。"),
    ("开源与生态", "#15803d", "志愿者、许可证、依赖链、Star 指标。支撑互联网的地基，也是脆弱的一环。"),
    ("产品与设计", "#be185d", "什么值得被造出来，以及该做成什么样子。"),
    ("安全与风险", "#a16207", "投毒、注入、泄漏、黑箱。能力越强，验证越难的困境。"),
    ("学习与方法", "#4338ca", "怎么学、怎么写、怎么判断自己真的懂了。"),
    ("科技与社会", "#0e7490", "技术之外的制度、城市、资源与人群——它们决定技术最终长成什么样。"),
    ("科学与趣味", "#65a30d", "沙子为什么粘手、米有多长、太空咖啡机。纯粹的好奇心。"),
    ("人生与心态", "#9333ea", "关于时间、确定性与如何与自己相处的零散智慧。"),
]
# 置信度不足时归入「未归类」，而不是瞎猜一个主题（排在所有主题之后）
PENDING = "未归类"
THEME_ORDER = [t[0] for t in THEMES]
MIN_SCORE = 5   # 关键词打分低于此值 → 归入「最新更新」（实测阈值 5 时准确率约 74%）

# 关键词权重：命中即累加，取总分最高者；同分则按上面顺序靠前者优先
RULES = {
    # 说明：泛词（AI、公司、工作、代码）权重压低，避免盖过真正的主题词
    "AI 冲击与反思": [("AI", 1), ("人工智能", 3), ("大模型", 2), ("ChatGPT", 3), ("GPT", 2),
                 ("Claude", 3), ("LLM", 3), ("AGI", 3), ("机器学习", 2), ("自动化", 1),
                 ("替代", 2), ("失业", 3), ("失业率", 3), ("被 AI", 3), ("不会失业", 2)],
    "AI 编程实践": [("编码", 2), ("写代码", 3), ("提示词", 3), ("prompt", 3), ("上下文工程", 3),
                ("氛围编码", 3), ("vibe", 2), ("agent", 2), ("Agent", 2), ("Copilot", 3),
                ("token", 1), ("AI 编程", 3), ("代码生成", 3), ("黑箱编程", 3), ("AI 写", 3),
                ("值班", 2), ("用 AI", 2)],
    "编程与工程": [("代码", 1), ("编程", 2), ("抽象", 3), ("复杂性", 3), ("重构", 3), ("架构", 2),
               ("编译", 3), ("测试", 1), ("框架", 2), ("语言", 1), ("bug", 2), ("性能", 3),
               ("依赖", 2), ("调试", 3), ("部署", 2), ("工程", 1), ("千层面", 3), ("PHP", 2)],
    "职业与职场": [("晋升", 3), ("招聘", 3), ("离职", 3), ("退休", 3), ("工资", 3), ("薪水", 3),
               ("职场", 3), ("员工", 2), ("经理", 2), ("面试", 3), ("简历", 3), ("加班", 2),
               ("合同工", 3), ("初级工程师", 3), ("职业", 2), ("领导力", 3), ("大厂", 3)],
    "创业与商业": [("创业", 3), ("融资", 3), ("估值", 3), ("商业模式", 3), ("利润", 2), ("收入", 2),
               ("股价", 3), ("客户", 2), ("上市", 2), ("增长", 2), ("团队规模", 3),
               ("YC", 2), ("商业", 2), ("创始人", 3), ("团队", 1), ("竞品", 2), ("广告", 2)],
    "开源与生态": [("开源", 3), ("许可证", 3), ("license", 3), ("GitHub", 2), ("Star", 2),
               ("志愿者", 3), ("贡献者", 3), ("维护者", 2), ("fork", 2)],
    "产品与设计": [("设计", 2), ("界面", 3), ("UI", 3), ("产品", 2), ("用户体验", 3), ("交互", 3),
               ("按钮", 2), ("注册", 1), ("登录", 1)],
    "安全与风险": [("安全", 2), ("漏洞", 3), ("攻击", 3), ("泄漏", 3), ("泄露", 3), ("投毒", 3),
               ("注入", 3), ("诈骗", 3), ("风险", 2), ("隐私", 2), ("黑箱", 2), ("病毒", 2)],
    "学习与方法": [("学习", 3), ("教育", 3), ("教学", 3), ("读书", 3), ("写作", 3), ("思考", 2),
               ("知识", 2), ("学生", 3), ("大学", 3), ("博士", 3), ("练习", 2), ("课程", 2)],
    "科技与社会": [("社会", 3), ("城市", 3), ("政府", 3), ("政策", 3), ("国家", 2), ("中国", 2),
               ("美国", 2), ("经济", 2), ("房价", 3), ("能源", 2), ("基建", 3), ("互联网", 2),
               ("平台", 1), ("文明", 2)],
    "科学与趣味": [("科学", 2), ("物理", 3), ("数学", 3), ("太空", 3), ("卫星", 3), ("生物", 3),
               ("实验", 2), ("宇宙", 3), ("自然", 2), ("咖啡", 2), ("沙子", 3)],
    "人生与心态": [("人生", 3), ("心态", 3), ("焦虑", 3), ("幸福", 3), ("勇气", 3), ("习惯", 2),
               ("拖延", 3), ("耐心", 3), ("自己", 1), ("时间", 1), ("创造力", 2), ("孤独", 2)],
}

SENT_SPLIT = re.compile(r"(?<=[。！？!?])")
MARKDOWN = re.compile(r"[*`>#\[\]]")


def key(it):
    return "%d|%s|%d" % (it["issue"], it["section"], it["idx"])


def classify_theme(it):
    """关键词打分选主题；置信不足返回 PENDING。用 189 条人工标签实测：
    阈值 5 时覆盖率约 28%、准确率约 74%；阈值 3 时覆盖 61%、准确 64%。"""
    blob = " ".join([it.get("title", ""), it.get("text", ""), it.get("source", "")])
    best, best_score = None, 0
    for name in THEME_ORDER:
        score = 0
        for kw, w in RULES.get(name, []):
            if kw.lower() in blob.lower():
                score += w
        if score > best_score or (score == best_score and score > 0
                                  and THEME_ORDER.index(name) < THEME_ORDER.index(best or name)):
            best, best_score = name, score
    if not best or best_score < MIN_SCORE:
        return PENDING, best_score
    return best, best_score


def auto_take(it, limit=40):
    """抽取式摘要：取正文第一句，去掉 Markdown 标记与引号，超长截断"""
    txt = (it.get("text") or "").strip()
    txt = MARKDOWN.sub("", txt).replace("\n", " ").strip()
    txt = re.sub(r"^\s*[「\"'“【]", "", txt)
    parts = [p.strip() for p in SENT_SPLIT.split(txt) if p.strip()]
    if not parts:
        parts = [txt]
    s = parts[0]
    if len(s) < 8 and len(parts) > 1:
        s = parts[0] + parts[1]
    s = s.strip(" 。，、；：")
    if len(s) > limit:
        s = s[:limit].rstrip("，,、；;") + "…"
    return s or (it.get("title") or "（无摘要）")


def main():
    data = json.load(open(os.path.join(ROOT, "data.json"), encoding="utf-8"))
    lp = os.path.join(ROOT, "labels.json")
    labels = json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else {}

    # 丢弃已不存在条目的孤儿标签（期号/板块/序号变化或解析修正后会产生）
    valid = {key(it) for it in data["items"]}
    orphan = [k for k in labels if k not in valid]
    for k in orphan:
        del labels[k]

    added = []
    for it in data["items"]:
        k = key(it)
        if k in labels and labels[k].get("theme") and labels[k].get("take"):
            continue
        theme, score = classify_theme(it)
        take = auto_take(it)
        labels[k] = {"theme": theme, "take": take, "auto": True}
        added.append((it["issue"], it["section"], theme, score, take))

    json.dump(labels, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    import collections
    dist = collections.Counter(v["theme"] for v in labels.values())
    print("labels=%d 新增=%d 清理孤儿=%d" % (len(labels), len(added), len(orphan)))
    print("主题分布:", dist.most_common())
    for a in added[:25]:
        print("  #%d %s → %s (score %d) %s" % a)


if __name__ == "__main__":
    main()
