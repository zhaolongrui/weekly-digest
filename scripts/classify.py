# -*- coding: utf-8 -*-
"""给新条目补主题标签与一句话提炼。

已有的人工标签存在 labels.json（键为 "期号|板块|序号"），本脚本只补**缺失**的条目，
不覆盖人工成果。新增条目采用确定性规则：关键词打分选主题 + 抽取式首句摘要。
（若想让新增条目的提炼质量追平人工，可在 CI 里接入 LLM，见 README。）

主题只分**大类**（5 个），不再细分——大类之间语义距离大，关键词可判性更好，
覆盖率也明显高于细分主题。
"""
import os, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 五大类：类名 → 颜色、一句话说明
THEMES = [
    ("AI 与技术", "#c2410c",
     "AI、编程与软件工程的一切：模型怎么改变写代码的方式，以及代码本身的老问题。"),
    ("职业与商业", "#b45309",
     "求职、晋升、创业、融资、商业模式——工作与钱是怎么流动和分配的。"),
    ("产品与社会", "#0e7490",
     "产品该做成什么样，以及技术落到社会、城市、制度里会长成什么样子。"),
    ("学习与成长", "#4338ca",
     "怎么学、怎么想、怎么写，以及怎么跟自己相处。"),
    ("科学与趣味", "#65a30d",
     "沙子为什么粘手、太空咖啡机、一米有多长。纯粹的好奇心。"),
]
# 置信度不足时归入「未归类」，而不是瞎猜一个主题（排在所有主题之后）
PENDING = "未归类"
PENDING_COLOR = "#8a929c"
THEME_ORDER = [t[0] for t in THEMES]
MIN_SCORE = 2   # 关键词打分低于此值 → 归入「未归类」

# 旧细分主题 → 大类（用于把已有的人工标签迁移到大类，人工提炼原文保留不动）
LEGACY_MAP = {
    "AI 冲击与反思": "AI 与技术",
    "AI 编程实践": "AI 与技术",
    "编程与工程": "AI 与技术",
    "开源与生态": "AI 与技术",
    "安全与风险": "AI 与技术",
    "职业与职场": "职业与商业",
    "创业与商业": "职业与商业",
    "产品与设计": "产品与社会",
    "科技与社会": "产品与社会",
    "学习与方法": "学习与成长",
    "人生与心态": "学习与成长",
    "科学与趣味": "科学与趣味",
}

# 关键词权重：命中即累加，取总分最高者；同分则按上面顺序靠前者优先
RULES = {
    # 说明：AI 专属词权重高（2-3）；泛技术词（代码/编程/开发…）一律压到 1，
    # 否则职场、社会类条目只要提到"代码"就会被抢到本类（实测调低后准确率 64%→69%）。
    "AI 与技术": [
        ("AI", 3), ("人工智能", 3), ("大模型", 3), ("机器学习", 3), ("模型", 2),
        ("ChatGPT", 3), ("GPT", 3), ("Claude", 3), ("LLM", 3), ("AGI", 3),
        ("神经网络", 3), ("深度学习", 3), ("替代", 2),
        ("提示词", 3), ("prompt", 3), ("上下文工程", 3), ("氛围编码", 3),
        ("vibe", 2), ("agent", 2), ("Agent", 2), ("Copilot", 3), ("Cursor", 3),
        ("token", 2), ("代码生成", 3), ("用 AI", 2), ("AI 编程", 3), ("程序员", 3),
        ("开源", 3), ("许可证", 3), ("license", 3), ("GitHub", 3), ("Star", 2),
        ("贡献者", 3), ("维护者", 2), ("fork", 3),
        ("漏洞", 3), ("攻击", 3), ("泄漏", 3), ("泄露", 3),
        ("投毒", 3), ("注入", 3), ("诈骗", 3), ("隐私", 2), ("黑箱", 2), ("病毒", 3),
        ("芯片", 3), ("半导体", 3), ("操作系统", 3), ("机器人", 2),
        # 以下泛技术词权重为 1，仅作弱信号
        ("编码", 1), ("写代码", 1), ("编程", 1), ("代码", 1), ("程序", 1),
        ("开发", 1), ("软件", 1), ("算法", 1), ("训练", 1), ("推理", 1),
        ("自动化", 1), ("失业", 1), ("开发者", 1), ("工程师", 1),
        ("抽象", 1), ("复杂性", 1), ("重构", 1), ("架构", 1), ("编译", 1),
        ("测试", 1), ("框架", 1), ("bug", 1), ("性能", 1), ("依赖", 1),
        ("调试", 1), ("部署", 1), ("工程", 1), ("语言", 1), ("技术", 1),
        ("志愿者", 1), ("安全", 1), ("计算机", 1), ("数据库", 1), ("服务器", 1),
        ("浏览器", 1), ("网络", 1), ("硬件", 1),
    ],
    "职业与商业": [
        ("工作", 2), ("职业", 3), ("职场", 3), ("公司", 2), ("员工", 3),
        ("老板", 3), ("经理", 2), ("团队", 2), ("招聘", 3), ("面试", 3),
        ("简历", 3), ("晋升", 3), ("离职", 3), ("退休", 3), ("裁员", 3),
        ("工资", 3), ("薪水", 3), ("收入", 2), ("加班", 3), ("劳动合同", 3),
        ("合同工", 3), ("初级工程师", 3), ("领导力", 3), ("大厂", 3), ("远程", 2),
        ("创业", 3), ("创始人", 3), ("融资", 3), ("投资", 2), ("估值", 3),
        ("商业模式", 3), ("利润", 3), ("营收", 3), ("股价", 3), ("上市", 2),
        ("客户", 2), ("市场", 2), ("增长", 2), ("商业", 3), ("竞品", 3),
        ("YC", 3), ("广告", 2), ("销售", 3), ("成本", 2), ("价格", 2), ("收费", 2),
        ("企业", 3), ("行业", 2), ("岗位", 3), ("效率", 2), ("管理", 2),
    ],
    "产品与社会": [
        ("产品", 3), ("设计", 3), ("界面", 3), ("UI", 3), ("用户体验", 3),
        ("交互", 3), ("按钮", 3), ("功能", 2), ("用户", 2),
        ("社会", 3), ("城市", 3), ("政府", 3), ("政策", 3), ("国家", 2),
        ("中国", 2), ("美国", 2), ("世界", 2), ("经济", 2), ("房价", 3),
        ("能源", 2), ("基建", 3), ("互联网", 2), ("平台", 2), ("文明", 2),
        ("制度", 3), ("法律", 3), ("监管", 3), ("权力", 2), ("阶层", 3),
        ("人口", 3), ("农村", 3), ("工厂", 3), ("工厂", 2), ("战争", 3),
        ("媒体", 2), ("舆论", 3), ("文化", 2), ("历史", 2), ("政治", 3),
    ],
    "学习与成长": [
        ("学习", 3), ("教育", 3), ("教学", 3), ("老师", 3), ("学生", 3),
        ("大学", 3), ("博士", 3), ("课程", 3), ("读书", 3), ("书籍", 3),
        ("写作", 3), ("思考", 3), ("知识", 3), ("练习", 3), ("理解", 2),
        ("方法", 2), ("经验", 2), ("技能", 3), ("能力", 2),
        ("人生", 3), ("心态", 3), ("焦虑", 3), ("幸福", 3), ("勇气", 3),
        ("习惯", 3), ("拖延", 3), ("耐心", 3), ("创造力", 3), ("孤独", 3),
        ("时间", 2), ("自由", 2), ("意义", 2), ("价值", 2), ("快乐", 3),
        ("成长", 3), ("失败", 2), ("选择", 2), ("目标", 2), ("自己", 2),
    ],
    "科学与趣味": [
        ("科学", 3), ("科学家", 3), ("物理", 3), ("数学", 3), ("化学", 3),
        ("生物", 3), ("医学", 3), ("实验", 3), ("研究", 2), ("宇宙", 3),
        ("太空", 3), ("卫星", 3), ("火箭", 3), ("星球", 3), ("地球", 2),
        ("自然", 3), ("动物", 3), ("植物", 3), ("海洋", 3), ("气候", 3),
        ("咖啡", 3), ("沙子", 3), ("米", 1), ("光", 1), ("声音", 2),
        ("趣味", 3), ("好奇", 3), ("谜", 2), ("发明", 2), ("测量", 3),
    ],
}

SENT_SPLIT = re.compile(r"(?<=[。！？!?])")
MARKDOWN = re.compile(r"[*`>#\[\]]")


def key(it):
    return "%d|%s|%d" % (it["issue"], it["section"], it["idx"])


def normalize_theme(name):
    """把旧细分主题名迁移到大类名；已是新类名则原样返回"""
    return LEGACY_MAP.get(name, name)


def classify_theme(it):
    """关键词打分选主题；置信不足返回 PENDING。"""
    blob = " ".join([it.get("title", ""), it.get("text", ""), it.get("source", "")])
    low = blob.lower()
    best, best_score = None, 0
    for name in THEME_ORDER:
        score = 0
        for kw, w in RULES.get(name, []):
            if kw.lower() in low:
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

    # 旧细分主题 → 大类（人工提炼保留；未归类与机器标签则交给规则重算）
    migrated = 0
    for k in list(labels):
        v = labels[k]
        old = v.get("theme")
        if old in LEGACY_MAP:
            labels[k]["theme"] = LEGACY_MAP[old]
            migrated += 1
        if old in (PENDING, "最新更新") or v.get("auto"):
            del labels[k]  # 交由下方规则重算

    added = []
    for it in data["items"]:
        k = key(it)
        if k in labels and labels[k].get("theme") and labels[k].get("take"):
            continue
        theme, score = classify_theme(it)
        labels[k] = {"theme": theme, "take": auto_take(it), "auto": True}
        added.append((it["issue"], it["section"], theme, score, labels[k]["take"]))

    json.dump(labels, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    import collections
    dist = collections.Counter(v["theme"] for v in labels.values())
    total = sum(dist.values())
    print("labels=%d 迁移=%d 重算=%d 清理孤儿=%d"
          % (len(labels), migrated, len(added), len(orphan)))
    for name, n in dist.most_common():
        print("   %-8s %4d  (%.0f%%)" % (name, n, 100.0 * n / total))
    for a in added[:15]:
        print("  #%d %s → %s (score %d) %s" % a)


if __name__ == "__main__":
    main()
