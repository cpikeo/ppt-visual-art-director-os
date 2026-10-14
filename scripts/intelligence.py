# -*- coding: utf-8 -*-
"""intelligence.py · 设计智能层（唯一决策链，判断 + 理由）

    内容理解 → 受众 → 决策 → 结论抽取 → 信息权重 → 视觉角色 → 焦点判定
    → 构图推理 → 空间结构 → 媒体必要性 → 生产规格

本层依据 SKILL.md 生成确定性候选，不替代作者的品牌与整稿视觉判断；**说出为什么**：

  * 每个判断都带 `why`；
  * 真正竞争的形式才带 `rejected`；不为凑否决理由重复读稿；
  * 证据不足时给 `open_question`，不编造答案（标题不是证据，数字不得脑补）。

本层**不给**坐标、字号、色值以外的执行细节：几何与尺度是生成侧的判断。
视觉世界（纸/墨/强调语义/材质/光/字体语气）由内容推导——没有风格预设表，
相同内容允许产生不同视觉结果（推导吃的是内容实质，不是页面类型）。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────
# 1 · Brief 加载（唯一加载器：yml / json / 定义 BRIEF|NEED 的模块）
# ─────────────────────────────────────────────────────────────────────
def load_brief(path, *, with_digest: bool = False):
    """加载 brief；`with_digest=True` 时同一份内存字节同时用于解析与凭证。

    规划路径不能先 read_text 再 file_digest：那会把 brief 完整读两遍。
    普通调用仍只返回 dict，兼容现有消费者。
    """
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"需求文件不存在: {p}（brief 需为 .yml/.yaml/.json 或定义 BRIEF/NEED 的 .py）")
    try:
        raw = p.read_bytes()
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"brief 不是 UTF-8 文本：{p}（{exc.reason}）") from None
    if p.suffix in (".yml", ".yaml"):
        import yaml
        try:
            value = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = f":{mark.line + 1}:{mark.column + 1}" if mark else ""
            raise ValueError(f"brief YAML 解析失败：{p}{where} — "
                             f"{getattr(exc, 'problem', None) or exc}") from None
    elif p.suffix == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"brief JSON 解析失败：{p}:{exc.lineno}:{exc.colno} — {exc.msg}") from None
    elif p.suffix == ".py":
        import types
        mod = types.ModuleType("need_mod")
        mod.__file__ = str(p)
        exec(compile(text, str(p), "exec"), mod.__dict__)
        value = dict(mod.BRIEF) if hasattr(mod, "BRIEF") else (
            dict(mod.NEED) if hasattr(mod, "NEED") else None)
        if value is None:
            raise ValueError("brief 模块必须定义 BRIEF 或 NEED")
    else:
        raise ValueError("brief 只接受 .yml/.yaml/.json，或定义 BRIEF/NEED 的 .py")
    if not isinstance(value, dict):
        raise ValueError(f"brief 顶层必须是对象，实际是 {type(value).__name__}：{p}")
    if with_digest:
        return value, hashlib.sha256(raw).hexdigest()
    return value


# ─────────────────────────────────────────────────────────────────────
# 2 · 内容理解（Content Understanding）
# ─────────────────────────────────────────────────────────────────────
# 证据形态：结论由哪一种承担，决定了后面的焦点与构图。
EVIDENCE_MODES = ("comparison", "series", "part_whole", "number", "structure",
                  "sequence", "proposition", "none")

# 单位表按「长单位在前」排：先匹配「公里」再轮到「分」，否则「186 公里」
# 会被读成无单位数字 186，判断卡与骨架里就这么丢了量纲（实测：主语写成
# 「186」，读者无法知道这是公里还是家数）。只收真实出现的量词，不引入
# 任何业务口径。
_NUM = re.compile(
    r"(?<![A-Za-z])(-?\d+(?:[.,]\d+)?)\s*"
    r"(亿美元|万美元|亿元|万元|万家|万人|万次|个月|分钟|小时|美元|公里|千米|"
    r"万吨|吨|公斤|千克|克|厘米|毫米|米|升|毫升|千瓦时|千瓦|平方米|平米|立方米|"
    r"台|套|箱|份|笔|张|页|股|手|"
    r"%|％|pp|倍|万|亿|元|家|人|个|名|位|件|次|天|月|年|分|秒)?")
_SENTENCE_SPLIT = re.compile(r"[。；;!?！？\n]|(?<=\.)\s+")

_NEGATED_EXCEED = re.compile(r"没(有)?超[过越]|[不未]超[过越]")
# 「第 3 个月 / 第 6 个月」是序列位置，不是可比量（见 same_unit 的说明）。
_AXIS_TIME_TOKEN = re.compile(r"第\s*(\d+(?:[.,]\d+)?)\s*(个月|月|年|天|周|季度|季|日)")
# 条件从句里的比较词是**边界条件**，不是本页要展示的比较：决策页写
# 「若 2027Q1 周期仍高于 7 个月，暂停后续批次」时，「高于」描述的是一个阀门，
# 不是两端证据。剥掉条件从句再判比较，页面的焦点/构图/未决项才不会被一句
# guardrail 带偏（实测：收尾决策页被判成 comparison，选出对比构图，焦点落到
# 一个非主张的数字上）。只收明确的条件引导词，不用「当」——它是常用字
#（当前/当时），误剥会吃掉真实从句。
_CONDITIONAL_CLAUSE = re.compile(
    r"(?:如果|若|假如|倘若|一旦|除非)[^。；;！？!?\n]{0,40}?(?:[，,]|则|就|便)")
_MULTIPLE_OF = re.compile(r"\d+(?:\.\d+)?\s*倍")
_COMPARISON_WORDS = ("相比", "vs", " versus ", "高于", "低于", "前者", "后者",
                     "优于", "落后", "差距", "benchmark", "对标", "增减",
                     "超过", "超越")
_SERIES_WORDS = ("趋势", "增长", "下降", "同比", "环比", "逐年", "路径", "曲线",
                 "涨", "跌", "下滑", "回升", "掉到", "掉至", "跌到", "跌至",
                 "升至", "升到", "降至", "降到", "增至", "增到", "减至", "回落至",
                 "trend", "growth", "grew", "rose", "fell", "yoy", "qoq")
_SEQUENCE_WORDS = ("步骤", "流程", "阶段", "路径", "迭代", "先", "然后", "接着", "最后",
                   "roadmap", "phase", "step", "milestone", "里程碑")
# 强顺序标记：本身就是「这是一条流程」的名词。弱标记（先/然后/接着/最后）是连接
# 副词，单独出现不足以证明形状——「先把 A 压回去，再谈 B」是优先级排序。
_PHASE_MARKERS = re.compile(r"[一二三四五六七八九十\d]期|第[一二三四五六七八九十\d]+(?:期|阶段|批)"
                            r"|分[一二三四五六七八九十\d]+(?:期|批|阶段)")
_SEQUENCE_STRONG = ("步骤", "流程", "阶段", "迭代", "roadmap", "phase", "step",
                    "milestone", "里程碑")
# 顺序的**形状**标记：箭头链本身就是序列，不需要作者写「步骤」两个字。
SEQUENCE_MARKERS = {"→", "⇒", "➜", "⇢"} | {"-"}
_QUANTIFIED_ARROW = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:%|％|pp|万|亿|元|家|人|次)?\s*"
    r"(?:→|⇒|➜|⇢|->)\s*\d+")
_FROM_TO_QUANTITY = re.compile(
    r"(?:从|\bfrom\b)\s*\d+(?:[.,]\d+)?\s*(%|％|万元|元|万|亿|家|人|次)"
    r"\s*(?:到|至|\bto\b)\s*\d+(?:[.,]\d+)?\s*\1", re.I)
_BETWEEN_METRICS = re.compile(r"(?<!占)(?<!同)比(?![例率值])")
# 『12 家试点门店中，9 家续约』是总体与子集，不是 12→9 的下降。
_PART_OF_WHOLE = re.compile(
    r"(?P<total>\d+(?:[.,]\d+)?\s*(?P<unit>家|人|个|台|名|位|件|%|％))"
    r"[^。；;!?！？]{0,30}?中[，,\s]*(?P<part>\d+(?:[.,]\d+)?\s*(?P=unit))")
_STRUCTURE_WORDS = ("体系", "架构", "框架", "模型", "组织", "结构", "模块", "层级",
                    "平台", "中台", "framework", "architecture", "system")
# 「结构性增长 / 结构化数据」里的「结构」是形容词，「结构性增长」是一个东西的
# 名字、不是一条时间序列。不剥掉它，一句封面主张（「唯一还能拿到结构性增长的
# 战场」）会先被判成结构说明页、再被判成数据序列页，焦点与构图随之落到一张
# 并不存在的层级图/曲线上（CASE_006 s01 实测）。
_COMPOUND_NOUNS = re.compile(r"结构性(?:增长|提升|变化|下降|调整|机会)?|结构化|结构图")


def _evidence_body(body: str) -> str:
    """证据形态只按**谓词**判定：复合名词（结构性增长）不产生证据形态。"""
    return _COMPOUND_NOUNS.sub("", body)
_CONCLUSION_WORDS = ("结论", "所以", "因此", "必须", "唯一", "只有", "本质", "关键",
                     "决定", "建议", "请批准", "意味着", "证明")
# 现场/记录信号：内容里出现可指认的场所与记录动作时，图像才可能是证词。
# 这是**意义**判据（有没有现场），不是风格判据（像不像照片）。
_SCENE_WORDS = ("现场", "记录", "回访", "走访", "探访", "实录", "课堂", "门店", "车间",
                "工地", "田间", "实验室", "展厅", "产线", "工厂", "仓库", "医院", "学校",
                "车间", "山村", "厨房", "田", "菜场", "港口", "车站",
                "on-site", "field visit", "visit", "scene", "classroom", "store", "shop",
                "factory", "farm", "lab", "studio")
# 追问句/概览句是**话题**，不是结论：它们可以进标题，但不能冒充这一页的主张。
_TOPIC_MARKERS = ("如何", "怎样", "有哪些", "为什么", "是什么", "怎么", "介绍", "概览",
                  "背景", "how to", "overview", "introduction")
_TOPIC_TAILS = ("记录", "流程", "结构", "说明", "概览", "介绍", "方案", "清单", "框架",
                "体系", "回顾", "背景", "进展", "情况", "梳理", "节奏", "趋势", "现状", "数据", "分析", "画像", "对比", "时间表", "路线图")
# 要决定的一句话：出现它时，这一页的职责是把决定收成可执行的一句。
# 断言信号：一句真正的主张在**说变化或比较**（降至/超过/持平/翻倍…），
# 而不是在说相关性（「如何使用…」）。它比长度更接近「结论」的定义。
_CHANGE_WORDS = ("降至", "降到", "减到", "增至", "提升", "增加", "减少", "超过", "达到",
                 "带来", "持平", "翻倍", "高于", "低于", "上升", "下降", "占",
                 "grow", "drop", "reach", "cut", "exceed")
_ASK_WORDS = ("请批准", "请决定", "请审议", "请确认", "批准", "表决", "approve", "sign off",
              "approval")
# 只收可以被看见的具体人物；群体与角色名词（客户、团队、伙伴）是抽象指称，不是证词主体。
_HUMAN_WORDS = ("患者", "工匠", "师傅", "老师", "学生", "医生", "护士", "农民", "工人",
                "居民", "孩子", "老人", "patient", "craftsman", "teacher", "nurse")
# 内容是不是「实体世界」：只有实体世界的开场才靠图像建立现场；
# 信息世界（纸/墨）的开场由排版与字阶建立——避免策略稿一律配图。
_PHYSICAL_SUBJECTS = ("stone_architecture", "metal_glass", "botanical", "water_sky",
                      "textile_domestic", "stage_screen", "ceramic_craft")

# 图像名额的价值权重：证词（图像就是证据）> 建立（图像就是主语）> 其余角色。
# 这不是风格偏好，是「删掉这张图，这一页少掉的是什么」的排序。

# 内容实质 → 材质世界。这不是风格预设表：键是**内容里的实体**，
# 不是「高级/极简/奢华」这类风格名；命中不了就不猜（走中性纸）。
_MATERIAL_LEXICON: dict[str, dict] = {
    "paper_ink": {
        "words": ("纸", "墨", "写作", "内容", "文案", "文档", "档案", "出版", "编辑", "文字",
                  "报告", "年报", "paper", "ink", "editorial", "content", "words"),
        "material": "handmade paper ground, pigment settling into fiber, matte finish",
        "light": "even diffuse daylight, no visible source",
        "textures": ("paper", "ink"),
    },
    "stone_architecture": {
        "words": ("建筑", "城市", "场所", "场地", "空间", "结构", "基础设施", "地产",
                  "园区", "architecture", "city", "infrastructure", "built"),
        "material": "honed stone, board-formed concrete, structural shadow lines",
        "light": "single raking light across a plane",
        "textures": ("stone", "structure"),
    },
    "metal_glass": {
        "words": ("芯片", "设备", "硬件", "手机", "机械", "制造", "工业", "机器人",
                  "引擎", "器械", "chip", "device", "hardware", "engine"),
        "material": "machined metal edge, optical glass, controlled specular highlight",
        "light": "one key light on a dark stage",
        "textures": ("metal", "glass"),
    },
    "botanical": {
        "words": ("农业", "农田", "田间", "食品", "健康", "有机", "生长", "森林", "茶叶",
                  "茶", "土壤", "自然", "可持续", "医疗", "药品", "food", "farm", "health",
                  "nature", "green"),
        "material": "oat fiber, leaf vein macro, matte clay, living surface",
        "light": "soft top light through canopy",
        "textures": ("fiber", "leaf"),
    },
    "water_sky": {
        "words": ("海洋", "水源", "水利", "航运", "电力", "电动", "旅行", "能源", "气候",
                  "海岛", "风电", "ocean", "water", "energy", "climate", "travel", "sky"),
        "material": "wet stone, mist over water, cold diffuse sea light",
        "light": "cold diffuse light from a wide opening",
        "textures": ("water", "mist"),
    },
    "textile_domestic": {
        "words": ("家庭", "生活", "服饰", "零售", "门店", "消费", "社区", "餐饮", "酒店",
                  "retail", "store", "home", "life", "community", "hotel"),
        "material": "woven textile, warm clay, worn timber, human-scale surfaces",
        "light": "late afternoon window light",
        "textures": ("textile", "clay"),
    },
    "stage_screen": {
        "words": ("发布会", "舞台", "演出", "影像", "直播", "游戏", "电影", "音乐", "屏幕",
                  "launch", "stage", "screen", "film", "music", "game"),
        "material": "light as material on a dark stage, wet black floor, glass reflection",
        "light": "controlled stage key, deep falloff",
        "textures": ("stage", "screen"),
    },
    # 手作/器物世界：luxury/museum 两域的主题实体（青瓷/文物/长卷）。
    # 与 textile_domestic 分工：纺织=生活消费表面，陶瓷=被手长期触摸的器物。
    "ceramic_craft": {
        "words": ("青瓷", "瓷器", "陶瓷", "瓷", "釉", "窑", "瓷土", "匠人", "手作",
                  "漆器", "银壶", "银器", "青铜", "玉器", "书画", "长卷", "卷轴",
                  "文物", "藏品", "展品",
                  "ceramic", "porcelain", "kiln", "glaze", "craft", "artifact"),
        "material": "kiln glaze on clay, matte crackle, pigment settling into earth",
        "light": "single warm side light, long soft shadows",
        "textures": ("glaze", "clay"),
    },
}
_REGISTER_WORDS = {
    "document": ("董事会", "投资人", "投委会", "股东", "机构", "审计", "监管", "年报",
                 "评审", "委员会", "bank", "board", "investor", "audit", "review"),
    "stage": ("发布会", "客户", "用户", "消费者", "公众", "媒体", "大会", "演讲", "路演",
              "keynote", "launch", "public", "campaign", "roadshow"),
    "working": ("团队", "内部", "周会", "复盘", "培训", "协作", "同事", "内部",
                "internal", "team", "workshop"),
}


_WITNESS_WORDS = ("现场", "记录", "回访", "走访", "探访", "实录", "on-site", "field visit", "visit")
# 证词现场需要「有人去看、去记」。场所词单独出现在数据句里（「门店 120 家」「门店规模稳定」）
# 只说明在哪里发生，不说明有人在场记录；有可核对数字时，它是计数对象。
_ENUM_LIST = re.compile(r"[^、，,：:。；;\s]+、[^、，,：:。；;\s]+、[^、，,：:。；;\s]+")


def _scene_of(body: str, distinct: int) -> bool:
    if not _hit(body, _SCENE_WORDS):
        return False
    return distinct == 0 or _hit(body, _WITNESS_WORDS)


def _hit(text: str, words) -> bool:
    """CJK 用子串；拉丁整词（避免 history→story 误判）。"""
    low = str(text or "").lower()
    for w in words:
        w = str(w).strip().lower()
        if not w:
            continue
        if any("\u4e00" <= ch <= "\u9fff" for ch in w):
            if w in low:
                return True
        elif re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", low):
            return True
    return False


def _sentences(text: str) -> list[str]:
    return [s.strip(" \t·—,，、") for s in _SENTENCE_SPLIT.split(str(text or "")) if s.strip()]


def numerals(text: str) -> list[dict]:
    """文本里的数字及其单位（结论的候选承载体）。

    年份（1900–2100 的四位无单位数字）单独标记：它是时间坐标，不是证据量——
    把「2026」当作本页最大的数字是典型的误判。字母紧贴的数字（Q1/V2）是编号
    不是量，也不进证据。**日期与编号的碎片同样不进证据**：「2026-09」里的
    「-09」、「2026/03」里的「03」、「2026 年 9 月」里的「9」都是时间坐标的
    零件，把它们当成第二个数据点会让证据形态、密度与权重同时失真
    （实测：一张排期页的权重卡出现过「次 -09」）。
    """
    out = []
    raw_text = str(text or "")
    for m in _NUM.finditer(raw_text):
        raw = m.group(0).strip()
        value = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").strip()
        # 『曲线1/方案2/第3页』是对象编号，不是可比较的数据点。判断证据数量
        # 不得把标签末尾的索引偷换成不同单位的实测值。
        prefix = raw_text[max(0, m.start() - 4):m.start()]
        if not unit and re.search(r"(?:曲线|版本|方案|阶段|步骤|第)\s*$", prefix):
            continue
        # 日期 / 区间 / 版本号的碎片：'-09'、'/03' 这类数字前面贴着数字或
        # 年份分隔符，或处于 '1.2.3' 这样的多段编号中。
        token = m.group(0)
        before = raw_text[:m.start()].rstrip()
        prev_char = raw_text[m.start() - 1] if m.start() else ""
        if token[:1] in ("-", "+") and prev_char.isdigit():
            continue                                   # 2026-09 / 38-92 的后半段
        if re.search(r"\d{4}\s*[-/.]$", before):
            continue                                   # 2026/03 · 2026.09
        if re.search(r"\d\.\d\s*\.$", before):
            continue                                   # 1.2.3 版本号中段
        after = raw_text[m.end():m.end() + 1]
        if "." in token and after == ".":
            continue                                   # 1.2.3 版本号首段
        # 点分日期（2026.10 / 2026.10.14）：整个 token 被小数规则吞下
        #（value=2026.1），日期于是变成「本页唯一的证据量」——封面把
        #「投委会 2026.10」认成主证据后，焦点/权重/构图/字阶一起落到一个
        # 时间坐标上（实测封面最大的元素成了日期）。四位年 + 点分月日、
        # 且不带单位，就是时间坐标，与「2026-09 / 2026/03」同一处理。
        if not unit and re.fullmatch(r"\d{4}\.\d{1,2}(?:\.\d{1,2})?", token):
            continue
        # 点分日期的后半段：「2026.10.14」被小数规则切成 2026.10 与 14，
        # 后者是月日零件，同样不是证据量。
        if not unit and re.search(r"\d{4}\.\d{1,2}\.\s*$", before):
            continue
        if unit in ("年", "月") and re.search(r"\d{4}\s*年\s*$", before):
            continue                                   # 「2026 年 9 月」是日期不是时长
        # 列表编号不是数据：「1）汇率…/2)…/3、…/1. …/(1)/①」这种枚举前缀本身不是量，
        # 把它当成「本页最大的数字」会让列表开头的风险页/方法页错把序号当 KPI。
        # 判据：数字后面紧跟 ）)、.．:：或全角右括号/顿号/点，且数字无单位，且
        # 前面非小数点/数位（不是 3.14 这种数）。
        after_chars = raw_text[m.end():m.end() + 2]
        if not unit and re.match(r"^[）)、\.．:：\)\s]", after_chars) \
                and not prev_char.isdigit() and prev_char != ".":
            # 允许「1.5」「0.8」这种真正的小数：只有整数后直接跟枚举分隔符才算编号。
            if "." not in m.group(1):
                continue
        # 「2026」「2026 年」都是时间坐标；「3 年」才是时长（值不在年份区间）。
        year = unit in ("", "年") and 1900 <= value <= 2100 and "." not in m.group(1)
        out.append({"raw": raw, "value": value, "unit": unit, "year": year})
    return out


def evidence_numerals(text: str) -> list[dict]:
    return [n for n in numerals(text) if not n["year"]]


_ARRIVAL_CUE = re.compile(
    r"(?:升[至到]|降[至到]|增[至到]|减[至到]|跌[至到]|回落[至到]|提高[至到]|"
    r"达到|→|->|到(?=\s*(?:20\d{2}\s*年?)?\s*\d)|今年|目前|当前|现为|"
    r"\b(?:to|now|currently)\b)\s*", re.I)


_CLAUSE_SPLIT = re.compile(r"[，,。；;：:！!？?\n]")
# 指标名归属时要剔掉的「非指标」词：连词、代词、时态与量词外壳。
# 只做减法——不认识的词一律保留（宁可多留一个候选，也不误删真指标）。
_METRIC_STOPWORDS = frozenset({
    "我们", "他们", "它们", "本页", "本期", "同期", "分别", "其中", "通过", "进行",
    "已经", "可以", "不能", "无法", "没有", "出现", "达到", "成为", "包括", "以及",
    "并且", "而且", "但是", "因此", "所以", "目前", "当前", "现在", "未来", "今年",
    "去年", "明年", "所有", "全部", "部分", "这些", "那些", "一个", "两个", "三个",
    "四个", "存在", "产生", "导致", "使得", "用于", "属于", "位于", "来自", "采用",
    "使用", "是否", "还是", "就是", "不是", "只有", "还有", "其它", "其他", "之上",
    "之下", "之内", "之外", "其中", "上述", "以下", "之间", "左右", "前后", "连续",
    "每个", "任何", "每一", "这一", "该", "其", "此", "后", "前",
})
_CJK_RUN = re.compile(r"[一-鿿]{2,}")
# 长 CJK 串内部按虚词再切：不切的话「与印尼的口岸清关时效在」会成为一个
# 19 字的「指标名」，主张里的「清关」永远命中不上。
_METRIC_SEPARATORS = re.compile(r"[的与和或是在由从对把被之并而就才更最也都还又则即及等中上下为了到至使让]")
# 太通用的 2 字片段（「成本」「数据」…）不足以证明主张点名了这个指标。
_WEAK_METRIC_SLICE = frozenset({
    "成本", "数据", "时间", "比例", "金额", "数量", "情况", "内容", "方式", "结果",
    "问题", "比率", "水平", "规模", "增长", "下降", "提升", "下降", "变化", "区间",
    "部分", "整体", "合计", "平均", "同比", "环比", "口径", "来源", "期间", "单位",
})
# 区间下界：「1.8 至 6.4 天」里的 1.8 是波动的下沿，不是这一页要立住的量。
_RANGE_NEXT = re.compile(r"^\s*(?:至|到|~|～|—|–|-)\s*[-+]?\d")
# 序数→序列下标：主张说「第二年」，证据按年份分句时，焦点属于那一年。
_ORDINAL_INDEX = {"第一": 0, "第二年": 1, "第二年": 1, "第三年": 2, "首年": 0, "次年": 1,
                  "末年": -1, "第一年": 0, "第二年": 1, "第三年": 2, "第四年": 3,
                  "首个": 0, "第二个": 1, "第三个": 2, "最后一个": -1}
_YEAR_TOKEN = re.compile(r"(20\d{2})\s*年?")
_DIGIT_TAIL = re.compile(r"[0-9][0-9.,]*\s*$")


# 纯函数记忆化：同一页的从句切分 / 指标名 / 数字角色在一轮判断里会被
# number_roles → focus_of / information_weight / typography 反复问到。
# 它们都是输入的纯函数，缓存不改变任何判断结果，只去掉重复解析。
def _metric_of_clause(clause: str) -> list[str]:
    """从句里取可能的指标名（连续 CJK 片段按虚词再切，去掉连词与动词外壳）。"""
    out = []
    for m in _CJK_RUN.finditer(clause):
        for tok in _METRIC_SEPARATORS.split(m.group(0)):
            if tok in _METRIC_STOPWORDS or len(tok) < 2:
                continue
            # 「降至 / 升至 / 达到」这类动词壳不是指标名；剥掉常见后缀再判一次。
            core = re.sub(r"(降至|升至|增到|减到|达到|超过|低于|高于|为|约|达|从)$", "", tok)
            if len(core) >= 2 and core not in _METRIC_STOPWORDS:
                out.append(core)
    return out


def _claim_mentions(claim: str, metric: str) -> bool:
    """主张是否点名了这个指标：全名命中，或片段命中（中文常写简称）。

    4 字以上的指标允许 2 字片段（「单均履约成本」↔ 主张里的「履约」），
    但太通用的 2 字片段不算——否则任何带「成本」的指标都会被当成被点名的那个。
    """
    if not claim or not metric:
        return False
    if metric in claim:
        return True
    if len(metric) >= 3 and any(metric[i:i + 3] in claim for i in range(len(metric) - 2)):
        return True
    if len(metric) >= 4:
        return any(metric[i:i + 2] in claim and metric[i:i + 2] not in _WEAK_METRIC_SLICE
                   for i in range(len(metric) - 1))
    return False


# 纯函数记忆化：同一页的从句切分 / 指标名 / 数字角色在一轮判断里会被
# number_roles → focus_of / information_weight / typography 反复问到。
# 它们都是输入的纯函数，缓存不改变任何判断结果，只去掉重复解析。
def _clause_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _CLAUSE_SPLIT.finditer(text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if b > a]


def _year_by_clause(text: str) -> dict[int, str]:
    """按从句给出「当前年份」：年份标记只在它出现的那一句，其后各句沿用，
    直到下一个年份标记出现（「2027 年：收入 12.8 亿元」——年份在冒号前）。"""
    out: dict[int, str] = {}
    current = None
    for i, (a, b) in enumerate(_clause_spans(text)):
        m = _YEAR_TOKEN.search(text[a:b])
        if m:
            current = m.group(1)
        if current:
            out[i] = current
    return out


def _ordinal_year(text: str, claim: str) -> str | None:
    """主张用序数点名某一年（「第二年」）时，返回证据里对应的那一年的年份串。"""
    hits = [(ordinal, idx) for ordinal, idx in _ORDINAL_INDEX.items() if ordinal in claim]
    if not hits:
        return None
    idx = max(hits, key=lambda kv: len(kv[0]))[1]
    years = []
    for y in _year_by_clause(text).values():
        if y not in years:
            years.append(y)
    if not years:
        return None
    try:
        return years[idx]
    except IndexError:
        return None


def _arrival_value(n: dict, text: str) -> bool:
    """这个数字是不是「从 A 到 B」里的 B：只有真带终值信号才配叫结果值。

    旧实现把 evidence==series 页面上**任何**主数字都写成「变化后的结果值」，
    于是一个静态半径（186 公里）与一个待批准的扩编目标（3 个）都被说成变化
    的结果——理由与数据不符，就是判断在脑补（SKILL §3：数字必须与主张一致）。
    """
    raw = str((n or {}).get("raw") or "")
    body = str(text or "")
    pos = body.find(raw)
    if not raw or pos < 0:
        return False
    return bool(_ARRIVAL_CUE.search(body[max(0, pos - 12):pos]))


def claim_units_conflict(claim_text: str) -> bool:
    """主张自己是否在比较两种不同单位的量。

    「比较量的单位不同」只在**主张**层面成立：页面里同时出现家数、月数与百分比，
    不等于这一页要把它们画到同一条数量轴上（实测：人效对比页的告警来自正文里的
    门店家数与培养周期，主张其实只有 34% 一个量）。主张自带两种单位——「总收入
    480 万元，人均成本 90 元」——才是真的不可直接相减。
    """
    return len({n.get("unit") or "" for n in evidence_numerals(claim_text)}) > 1


def _metric_by_clause(text: str) -> dict[int, list[str]]:
    """按从句给出**当前指标名**：指标名写在冒号前时，其后的取值沿用它。

    「同店销售额同比增速：2025Q4 为 8.6%，2026Q1 为 6.1%…」里，四个取值各自
    的从句一个字指标名都没有；只看本从句就锚不上主张，焦点于是落到页面末句
    那个不相干的数字上（实测：增速页的主语变成另一个指标的 37.5 万元）。
    规则与 `_year_by_clause` 同源：标签写在前面，后续从句沿用，直到新标签出现。
    句号/分号/问叹号是**句界**，跨句不继承——标签的作用域是一句话，不是一整页
    （否则「增速：… 2.2%。同期新店 9 家」会让后面每个数字都以为自己在讲增速）。
    """
    out: dict[int, list[str]] = {}
    current: list[str] = []
    spans = _clause_spans(text)
    last = 0
    for idx, (a, b) in enumerate(spans):
        # 紧邻本从句之前的那个分隔符决定是否换句。
        sep = text[last:a].strip() if a >= last else ""
        if idx and sep and (sep[-1] in "。；;！？!?\n"):
            current = []
        own = _metric_of_clause(text[a:b])
        if own:
            current = own
        out[idx] = current
        last = b
    return out


def _attributed_primary(text: str, nums: list[dict], claim: str) -> dict | None:
    """焦点数字＝**主张所指的那个量**，不是第一个或最后一个数字。

    判据（全部来自本页文本，确定性）：
      1. 数字按从句归属它前面的指标名（「履约成本 11.2 元」→ 履约成本）；
      2. 主张里点名的指标，其数字优先（+3）；主张用序数点名某年（「第二年」）
         时，那一年从句里的数字优先（+3）；
      3. 变化终值（降至 / 升至 …）优先（+1）；
      4. 区间下界（「1.8 至 6.4」里的 1.8）不是可以立住的量，出局。
    """
    spans = _clause_spans(text)
    years = _year_by_clause(text)
    metrics = _metric_by_clause(text)
    year = _ordinal_year(text, claim)
    cursor, scored = 0, []
    for n in nums:
        pos = text.find(n["raw"], cursor)
        if pos < 0:
            pos = cursor
        cursor = pos + len(n["raw"])
        idx = next((i for i, (a, b) in enumerate(spans) if a <= pos < b), 0)
        a, b = spans[idx]
        clause = text[a:b]
        tail = text[pos + len(n["raw"]):pos + len(n["raw"]) + 6]
        is_range_bound = bool(_RANGE_NEXT.match(tail))
        score = 0.0
        if any(_claim_mentions(claim, m) for m in metrics.get(idx, ())):
            score += 3.0
        # 主张在要一个决定时，**被申请的那个量**才是主语：决策页写「批准本轮
        # 30 家，同步把培训基地从 2 个扩到 3 个」，「3 个」带着终值信号（扩到），
        # 但它不是要批的东西。终值信号不该压过请求本身。
        if _hit(claim, _ASK_WORDS) and _hit(clause, _ASK_WORDS):
            score += 2.0
        if year and years.get(idx) == year:
            score += 3.0
        if _ARRIVAL_CUE.search(clause[:pos - a]):
            score += 1.0
        scored.append((score, not is_range_bound, n))
    alive = [s for s in scored if s[1]]
    pool = alive or scored                       # 全是区间边界时退回全体（不判空）
    best = max(pool, key=lambda t: t[0])
    if best[0] <= 0:
        return None
    # 同分且同单位的取最后一个：主张没有点名某个取值时（「增速已经连续三个季度
    # 收窄」），这一页的答案是**当前状态**，不是序列开头那一年的基期。旧实现取
    # 同分里的第一个，等于每次讲趋势都把三年前的旧数字推成主语。
    tied = [t for t in pool if round(t[0], 6) == round(best[0], 6)]
    if len(tied) >= 2 and len({t[2].get("unit") or "" for t in tied}) == 1:
        return tied[-1][2]
    return best[2]


def number_roles(text: str, claim: str | None = None) -> tuple[list[dict], dict | None]:
    """区分基期和结果：『从 38% 升至 61%』的视觉主语是 61%，不是首个数字。

    只认明确的终值信号；没有信号时保留原始顺序，不擅自把最大值当答案。
    页判断只调用一次，焦点与信息权重共享；直接调用两者时各自可回退。
    `claim` 给了就做**主张锚定**：焦点数字必须属于主张所指的那个指标，
    否则这一页会拿一个不相干的最大数字当主语（CASE_006 实测：单位经济页
    把客单价当焦点、风险页把波动下界当焦点）。
    """
    text = str(text or "")
    nums = evidence_numerals(text)
    if not nums:
        return nums, None
    if claim:
        anchored = _attributed_primary(text, nums, str(claim))
        if anchored is not None:
            return nums, anchored
    subset = _PART_OF_WHOLE.search(text)
    if subset:
        part = evidence_numerals(subset.group("part"))
        if part:
            matched = next((n for n in nums if n["value"] == part[0]["value"]
                            and n["unit"] == part[0]["unit"]), None)
            if matched:
                return nums, matched
    for cue in reversed(list(_ARRIVAL_CUE.finditer(text))):
        # 离终值太远的数字属于下一句话，不得误认；允许「到 2025 年 61%」。
        nearby = re.split(r"[，。；;!?！？]", text[cue.end():], maxsplit=1)[0][:32]
        arrival = next(iter(evidence_numerals(nearby)), None)
        if arrival:
            primary = next((n for n in nums if n["value"] == arrival["value"]
                            and n["unit"] == arrival["unit"]), None)
            if primary:
                return nums, primary
    return nums, nums[0]


# 只收正文中可逐字核对的「主体—关系—对象」，不从“治理/四层”等话题词造图。
# 这是保守的中文显式句式提取，不是通用语义解析：不确定句、结果数字与步骤留给原判断。
_RELATION_CLAUSE = re.compile(
    r"^(?P<subject>[^\s，,；;。！？!?：:]{1,24}?)"
    r"(?P<relation>负责(?!人|率)|决定|协调|执行|隶属)"
    r"(?P<object>[^，,；;。！？!?：:]{1,32})$")
_REPORTING_CLAUSE = re.compile(
    r"^(?P<subject>[^\s，,；;。！？!?：:]{1,24}?)向"
    r"(?P<object>[^\s，,；;。！？!?：:]{1,24}?)汇报$")


def explicit_relations(content: str) -> list[dict]:
    """保留原句事实；至少两个不同主体才足以构成同屏关系，不据顺序推上下级。"""
    if re.search(r"[?？]|(?:谁|如何|是否|可能|如果|建议|应该|应当|拟|尚未)", content):
        return []
    found = []
    for raw in re.split(r"[，,；;。\n]", _SOURCE_TAIL.sub("", content)):
        clause = re.sub(r"^\s*(?:[0-9]+[、.)）]\s*)?", "", raw).strip()
        match = _REPORTING_CLAUSE.fullmatch(clause) or _RELATION_CLAUSE.fullmatch(clause)
        if not match:
            continue
        fact = match.groupdict()
        fact.setdefault("relation", "汇报")
        if fact["subject"].endswith(("不", "未", "没有", "应", "将", "先", "然后", "最后")):
            continue
        if any(n for n in evidence_numerals(clause)):
            continue
        fact["object"] = fact["object"].strip()
        if fact["object"] and fact not in found:
            found.append(fact)
    return found if len({f["subject"] for f in found}) >= 2 else []


def understand(text: str, *, has_chart: bool = False, content: str | None = None) -> dict:
    """内容理解：这段内容靠什么成立（证据形态）、有多少数字、有没有人。

    确定性、无副作用；它是判断的输入，不是判定的结果。
    """
    text = str(text or "")
    # 出处标注（「（来源：门店台账）」）不是内容：世界推导、人物/现场判定、
    # 证据形态都不该被它触发——否则一张台账的名字就能给整页配图。
    body = _SOURCE_TAIL.sub("", text).strip() or text
    # 「不超过/未超过」是界限不是对比：先剥掉再匹配，否则「误差不超过5%」
    # 会被判成两端对比（A超过B但C不超过D——真的超过不受影响）。
    cmp_body = _CONDITIONAL_CLAUSE.sub("", _NEGATED_EXCEED.sub("", body))
    # 证据量只从**内容本体**扫描：出处标注里的台账编号与日期（「来源：投放台账
    # 2026Q2」）是档案坐标，不是这一页的证据——把它算进去会让证据数量、
    # 密度与权重一起虚高。
    nums = numerals(body)
    # 按年份排列的同一指标是时间序列，不是并置比较；分期（一期/第二阶段）是同一承诺的先后。
    years = sum(1 for n in nums if n["year"])
    phased = bool(_PHASE_MARKERS.search(body))
    ev = [n for n in nums if not n["year"]]
    # 标题重复正文的数字、同一数字写两遍：那是**同一个事实**，不是两个证据。
    # 判断证据形态与密度按去重后的数量算；「重复」这件事本身归信息权重管。
    distinct = len({(round(n["value"], 6), n.get("unit") or "") for n in ev})
    # 比较轴上的时间坐标（「第 3 个月」）说明的是**位置**，不是与金额并置比较的
    # 另一个量。把它算进单位集合，同一条曲线的同一单位会被误判成「单位不同」：
    # 数据页因此丢掉 data_field、未决项里多出一条并不存在的口径告警（实测：
    # 「第 3/6/9 个月 × 月均营收（万元）」被判单位不一致，构图退到两端对照）。
    axis_tokens = {(round(float(m.group(1).replace(",", "")), 6), m.group(2))
                   for m in _AXIS_TIME_TOKEN.finditer(body)}
    compared = [n for n in ev
                if (round(n["value"], 6), n.get("unit") or "") not in axis_tokens]
    same_unit = len({n.get("unit") or "" for n in (compared or ev)}) <= 1
    chars = max(len(text), 1)
    pct = [n["value"] for n in ev if (n.get("unit") or "") in ("%", "％")]
    pct_whole = len(pct) >= 2 and abs(sum(pct) - 100) < 0.5
    is_subset = (distinct >= 2 and bool(_PART_OF_WHOLE.search(body))) or pct_whole
    is_comparison = not phased and (_hit(cmp_body, _COMPARISON_WORDS)
                                    or bool(_MULTIPLE_OF.search(cmp_body))
                                    or (distinct >= 2 and bool(_BETWEEN_METRICS.search(cmp_body))))
    # 只在无量化竞争/比较/时间推进时采信显式关系；标题不参与关系抽取。
    relation_text = body if content is None else str(content)
    relations = explicit_relations(relation_text)
    if ev or is_comparison or _hit(relation_text, _SEQUENCE_WORDS) or SEQUENCE_MARKERS & set(relation_text):
        relations = []
    modes: dict[str, float] = {}
    if is_comparison or (distinct >= 2 and has_chart and years < 2):
        modes["comparison"] = 0.6 + 0.1 * min(distinct, 3)
    if is_subset:
        modes["part_whole"] = 0.84
    # 序列至少两个数据点：「增长/趋势」这类词只有配上两个以上的量才是曲线；
    # 单独出现在封面或收尾的措辞里（「接管增长」「内容增长负责人」）不是证据。
    if (distinct >= 2 and _hit(_evidence_body(body), _SERIES_WORDS)) \
            or (distinct >= 3 and same_unit) \
            or _FROM_TO_QUANTITY.search(body):
        modes["series"] = 0.55 + 0.08 * min(distinct, 4)
    if distinct == 1:
        modes["number"] = 0.7
    if _hit(_evidence_body(body), _STRUCTURE_WORDS) or (not ev and _ENUM_LIST.search(body)):
        modes["structure"] = 0.65
    seq_strong = _hit(body, _SEQUENCE_STRONG)
    seq_hits = sum(1 for w in _SEQUENCE_WORDS if w in body)
    if seq_strong or seq_hits >= 2:
        # 顺序词出现得越多，形状越是「有步骤的行动」，越不该被一个孤立的时长数字
        # 压成 number（实测：三段里程碑 + 总计 18 个月的排期页被判成 number）。
        # 单个「先」不算顺序：它是中文里最高频的副词之一（「先把周期压回去，再谈
        # 扩张」是优先级，不是流程）。只有流程名（步骤/流程/里程碑…）或两个以上
        # 顺序标记才构成序列形状，否则决策页会被派成时间轴。
        modes["sequence"] = 0.6 + 0.05 * min(seq_hits or 1, 4)
    if SEQUENCE_MARKERS & set(body):
        # 两个可比较的量由箭头连起来是变化，不是『步骤模板』；有明确阶段词
        # 则仍由真实流程承担形状。无数字的箭头链维持原先的顺序判定。
        phases = _hit(body, ("阶段", "步骤", "流程", "里程碑", "phase", "step"))
        if distinct >= 2 and not phases and _QUANTIFIED_ARROW.search(body):
            modes["series"] = max(modes.get("series", 0.0), 0.81)
        else:
            modes["sequence"] = 0.75
    if phased:
        modes["sequence"] = max(modes.get("sequence", 0.0), 0.9)  # 分期结构压过数值形态（series 上限 0.87）
    if _hit(body, _CONCLUSION_WORDS):
        modes["proposition"] = 0.55
    if relations:
        modes["structure"] = 0.9  # 多个可核对的关系强于一句“决定/必须”的观点信号
    dominant = max(modes, key=lambda k: (modes[k], -EVIDENCE_MODES.index(k))) if modes else "none"
    # 主题实体也走复合名词过滤：「结构性增长」里的「结构」不是建筑实体，
    # 否则一句抽象封面主张会推导出一个石头与混凝土的世界，并给封面派一张图。
    subjects = [name for name, spec in _MATERIAL_LEXICON.items()
                if _hit(_evidence_body(body), spec["words"])]
    return {
        "evidence": dominant,
        **({"relations": relations} if relations else {}),
        "numerals": nums,
        "distinct_numerals": distinct,
        "numeric_density": round(distinct / (chars / 100), 2),
        "subjects": subjects,
        "human": _hit(body, _HUMAN_WORDS),
        "scene": _scene_of(body, distinct),
        "comparison": bool(is_comparison and not is_subset),
        "part_whole": is_subset,
        "same_unit": same_unit,
        "has_chart": bool(has_chart),
    }


# ─────────────────────────────────────────────────────────────────────
# 3 · 结论抽取（Claim Extraction）
# ─────────────────────────────────────────────────────────────────────
_SOURCE_TAIL = re.compile(r"[（(]\s*(来源|数据来源|source)[:：]?.*?[)）]\s*$", re.I)
_META_LINE = re.compile(r"[·｜|]|@|https?://|confidential|机密", re.I)
_CREDENTIAL_WORDS = ("提案", "汇报人", "主讲", "日期", "部门", "内部资料", "谢谢", "thanks",
                     "subtitle", "presented by")
# 句首列表编号（「1）」「2)」「3.」「1、」「①」「(1)」「（2）」）是枚举顺序标记，
# 不是主张本身；不剥掉会把「1）汇率波动…」的首词当成「短可复述的结论」，
# 并让信息权重把无单位的编号「1」当 KPI。
_LIST_PREFIX = re.compile(
    r"^\s*(?:[(（]\s*\d{1,2}\s*[)）]|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫]"
    r"|\d{1,2}\s*[)）、\.．:：])\s*")


def _fired(sent: str, words) -> str:
    """命中词回显：claim.why 里点名是哪一个词，不只说有一类词。"""
    return next((w for w in words if w in sent), "")


def _topic_shaped(title: str) -> bool:
    """标题是话题标签还是结论句：以「记录/流程/结构/说明…」收尾的是标签。"""
    return bool(title) and title.endswith(_TOPIC_TAILS)


# 标题能当结论的**断言证据**：判断词、变化词、范围词。命中任何一个，
# 这一句就不只是名词标签（「华东区数据」），而是对内容有主张的一句话。
# 断言谓语：标题里出现这些词，说明作者在下判断（「差距明显」「回本周期缩短」），
# 而不是给一个名词标签（「华东区数据」）。词表只收谓语，不收题材名词。
_TITLE_ASSERTION = ("是", "才", "最", "唯一", "第一", "过半", "不足", "超过", "低于", "高于",
                    "不再", "已经", "正在", "仍未", "尚未", "必须", "需要", "决定", "意味",
                    "成为", "没有", "不能", "无法", "达到", "降至", "升至", "翻倍",
                    "下降", "上升", "增长", "减少", "解耦", "落地", "启动", "完成",
                    "明显", "显著", "稳定", "放缓", "收窄", "扩大", "提升", "降低", "缩短",
                    "拉开", "分化", "集中", "依赖", "领先", "落后", "突破", "加速", "承压",
                    "见效", "回本", "收敛", "分散", "高企", "偏低", "偏高", "翻番",
                    "认为", "应该", "上涨", "下跌", "下滑", "回落", "改善", "恶化")


# 对比式断言：「增长来自复购而非补贴」「不是在赌市场，是在买能力」
# ——中文商业写作里最典型的判断句形，和「唯一/只有」同样属于断言证据。
_CONTRAST_ASSERTION = re.compile(
    r"而非|不是[^，。；]{0,12}(?:而是|是)|不在于|不在[^。；]{1,12}?[，,、]?在|不再只是|关键在于|取决于|本质上是|"
    r"差别不在|问题不在|真正的")


def _title_thesis(title: str) -> bool:
    """标题本身就是一个论断（与正文无关）：话题标签不是；断言谓语、对比句式、
    「从 A 增至 B」的变化句是。作者写下的这句话就是结论位，不是我们替他编的。"""
    return bool(title) and not _topic_shaped(title) and (
        _hit(title, _TITLE_ASSERTION) or bool(_CONTRAST_ASSERTION.search(title))
        or bool(_FROM_TO_QUANTITY.search(title)))


def _title_assertive(title: str) -> bool:
    """标题是否携带主张（而不是一个名词标签）。

    契约说「标题写结论」，但作者也会写标签（「华东区数据」）。标签没有主张，
    把它当结论等于替作者编了一句他没写下的话——所以只有带断言证据或数字的
    标题才占结论位，其余退回从内容里抽。
    """
    return bool(evidence_numerals(title)) or any(w in title for w in _TITLE_ASSERTION)


def _is_data_listing(sent: str) -> bool:
    """数字列举不是结论：「华东 +42%、华南 +28%、华北 +15%」是证据表的一行。

    判据是**形状**而不是字数。列举= 报告「各自是多少/走到哪」，主张= 让人得出
    「所以呢」。所以：结论句／要决定的句子／比较措辞＝主张（先判，压过其余）；
    两组以上的到达句并排（「甲方从 12% 升至 19%，我方从 9% 降至 7%」）＝列举——
    它把两条变化摆在一起，仍然只是证据表的一行；单组「从 A 到 B」是一个关系句，
    算主张。作者真要列举句当结论，写 insight 声明即可。
    """
    if _hit(sent, _CONCLUSION_WORDS) or _hit(sent, _ASK_WORDS) \
            or _hit(sent, _COMPARISON_WORDS):
        return False
    if len(_ARRIVAL_CUE.findall(sent)) >= 2:
        return True                      # 两条以上的变化并排 = 比较证据行
    if _hit(sent, _CHANGE_WORDS):
        return False
    ev = evidence_numerals(sent)
    if len(ev) < 2:
        return False
    # 三个以上数字且没有任何断言词＝规格行（「首城盈利周期 14 个月，履约成本
    # 11.2 元，可控节点 9 个」）：它回答「各是多少」，不回答「所以呢」。
    # 混合单位比同单位更像清单——同单位还可能是一个真实的关系句。
    if len(ev) >= 3:
        return True
    units = [n.get("unit") or "" for n in ev]
    if len(set(units)) != 1:
        return False
    # 「从 A 到 B」「A → B」把两个数字说成一个关系：那是断言，不是列举。
    if _FROM_TO_QUANTITY.search(sent) or _QUANTIFIED_ARROW.search(sent):
        return False
    return True


def extract_claim(item: dict, *, positional: bool = False) -> dict:
    """本页唯一结论：作者写了就用；没写就从内容里抽首句结论。

    抽不出来就 `absent`——**不编造**。摘要是观点不是证据，**标题是结论位**
    （brief 契约：标题写结论，不写字段名）：只要标题不像话题标签、内容里也没有
    更强的结论句（决定/结论措辞），就用作者写下的那一句。否则数据列举句会顶掉
    作者的结论，焦点、构图与排版跟着一起走偏。
    """
    declared = str(item.get("insight") or "").strip()
    if declared:
        return {"text": declared, "source": "declared",
                "why": "作者已在 brief 声明本页结论，规划不重写。"}
    content = str(item.get("content") or "").strip()
    title = str(item.get("title") or "").strip()
    cands: list[tuple[str, float]] = []
    if title:
        # 标题是最常见的结论位置，但它只有在「内容也在场」时才算主张：
        # 只有一句话题词、没有内容的页面，我们并不知道作者想说什么（不编）。
        # 以「记录/流程/结构/说明…」结尾的标题是话题标签，不是结论。
        # 首/末页是**陈述位**：没有证据也不等于没有主张。封面与收尾的职责就是
        # 立住或回收那一句话，它的证据在别的页上——把它们按「缺内容」扣分，
        # 会逼作者给封面补数据、或把收尾页降级成章节页（CASE_006 s01/s12 实测）。
        thesis = _title_thesis(title)
        bonus = 1.2 if (content or positional or thesis) else 0.6
        if _topic_shaped(title):
            bonus -= 0.8
        elif (content or thesis) and _title_assertive(title):
            # 结论位加权：标题不像标签、内容也在场时，它是作者写下的结论位
            # （brief 契约：标题写结论）。少了这一档，一句没有数字的结论
            # （「三年前的第一间门店，今天还在同一个街角」）会被内容里的证据表
            # 压掉，主张、焦点与构图跟着一起落到「有多少」而不是「所以呢」。
            bonus += 0.6
        cands.append((title, bonus))
    for rank, sent in enumerate(_sentences(content)):
        cleaned = _LIST_PREFIX.sub("", _SOURCE_TAIL.sub("", sent)).strip()
        cands.append((cleaned, 0.8 if rank == 0 else 0.0))
    best, best_score, best_bits = None, 0.0, []
    # 标题是作者写下的结论位：正文候选只有在**谈同一件事**时才谈得上更强的结论。
    # 正文换了指标（数据页标题说「增速连续三个季度收窄」，正文末句说「单店月均
    # 营收从 41.2 万元降至 37.5 万元」）时，数字+变化分会把一个次要指标顶上结论位，
    # 焦点、排版与信息权重随之一起走偏。带结论/决定措辞的正文句不受此限——那才是
    # 契约里说的「内容里更强的结论句」。
    title_metrics = set(_metric_of_clause(title)) if (title and _title_assertive(title)) else set()
    for rank, (sent, bonus) in enumerate(cands):
        if not sent:
            continue
        score = bonus
        # §03 取舍写到页上：why 不再是同一句套话——哪一句赢、靠哪几个分赢，
        # 没赢的差在哪，作者照着 why 就能改。
        is_title = bool(title) and rank == 0
        bits = ["标题" if is_title else
                "首句" if rank == (1 if title else 0) else "正文"]
        if is_title and not content:
            bits.append("无内容支撑")
        if is_title and title.endswith(_TOPIC_TAILS):
            bits.append("话题结尾扣分")
        if _hit(sent, _CONCLUSION_WORDS):
            score += 2.0
            bits.append(f"结论措辞「{_fired(sent, _CONCLUSION_WORDS)}」")
        elif _CONTRAST_ASSERTION.search(sent):
            score += 2.0
            bits.append("对比式断言（「不是/不在于…而是…」）")
        if is_title and positional and not content:
            score += 2.0
            bits.append("首末页陈述位（不要求本页证据）")
        if _hit(sent, _ASK_WORDS):
            # 要决定的话本身就是结论（「请批准试点预算」没写也得算写了）：
            # 否则 ask 全在标题里时结论判 absent，role 会把要决定的页判成别的。
            score += 2.0
            bits.append(f"要决定「{_fired(sent, _ASK_WORDS)}」")
        snums = evidence_numerals(sent)
        listing = bool(snums) and _is_data_listing(sent)
        if snums:
            # 没有内容时，光是数字说不上是结论（「18 个月落地节奏」是话题不是主张）：
            # 证据缺席的页面只能靠结论措辞立住，或者老实标 absent。
            # 数字**并排列举**同样不是结论：它回答「有多少」，不回答「所以呢」。
            if listing:
                bits.append("数字列举（不是结论）「"
                            + "/".join(n["raw"] for n in snums[:3]) + "」")
            else:
                score += 1.6 if content else 0.0
                bits.append("数字「" + "/".join(n["raw"] for n in snums[:3]) + "」")
        if not listing and _hit(sent, _CHANGE_WORDS):
            score += 0.8
            bits.append(f"变化「{_fired(sent, _CHANGE_WORDS)}」")
        if len(sent) <= 42:
            # 标题（rank 0 且有标题时）不吃短句分：短标题是话题标签，
            # 只能靠结论措辞/数字立住，否则与 43–64 字标题一样止于 1.2 → absent。
            if rank > 0 or not title:
                score += 0.4
                bits.append("短句可复述")
        elif len(sent) > 64:
            # 太长的一句记不住：结论必须是观众离场后可复述的一句话，超长只可能是论述。
            score -= 1.0
            bits.append("超长难复述扣分")
        if not is_title and title_metrics and not (
                _hit(sent, _CONCLUSION_WORDS) or _CONTRAST_ASSERTION.search(sent)
                or _hit(sent, _ASK_WORDS)):
            sent_metrics = set(_metric_of_clause(sent))
            if sent_metrics and not (sent_metrics & title_metrics):
                score -= 1.2
                bits.append("换了指标（与标题主张不是同一度量）")
        if _META_LINE.search(sent) or _hit(sent, _CREDENTIAL_WORDS):
            score -= 2.0     # 署名/提案/日期行不是结论
            bits.append("署名行扣分")
        if _hit(sent, _TOPIC_MARKERS):
            # 「如何使用/有哪些/概览」是话题：它说了要讲什么，没说结论——
            # 数字与短句都不该把它救成主张。
            score -= 2.5
            bits.append("话题标签扣分")
        # 打分必须可比较：浮点累积会让两个「2.8 分」分出胜负（实测：标题结论
        # 1.2+1.6 输给首句 0.8+1.6+0.4，只因为后者的浮点结果大了 4e-16）。
        # 判断不能由浮点噪声决定——先量化到 6 位再做严格比较，于是同分保持
        # 候选顺序：标题（作者的结论位）压过正文的列举句。
        score = round(score, 6)
        if score > best_score:
            best, best_score, best_bits = sent, score, bits
    threshold = 1.2 if (content or _title_thesis(title)) else 2.0
    if best and best_score > threshold:
        return {"text": best, "source": "extracted",
                "why": " ＋ ".join(best_bits) + "；发布前请作者确认口径。"}
    pos = best_bits[0] if best_bits else "（无候选）"
    return {"text": None, "source": "absent",
            "why": (f"最接近的是{pos}（{' ＋ '.join(best_bits[1:]) or '只有位置分'}，"
                    f"{round(best_score, 2)}分）：没有结论措辞/数字/决定句——"
                    "先补一句结论，或把它降级为章节/证据页。")}


# ─────────────────────────────────────────────────────────────────────
# 4 · 信息权重（Information Weight：最大化 / 弱化 / 删除）
# ─────────────────────────────────────────────────────────────────────
_HEDGES = ("可能", "或许", "一定程度上", "某种程度上", "应该说", "相对而言", "总体而言",
           "在某种意义上", "似乎", "大概")
_FILLERS = ("赋能", "助力", "打造", "全方位", "闭环", "抓手", "生态化", "体系化", "强赋能",
            "引领", "加持", "焕新", "新高度")


def information_weight(u: dict, claim: dict, text: str = "", *,
                       number_anchor: tuple[list[dict], dict | None] | None = None) -> dict:
    """三档权重：必须最大化 / 必须弱化 / 必须删除——每条给出理由。"""
    text = str(text or "")
    claim_text = str(claim.get("text") or "")
    maxi, weak, kill = [], [], []

    claim_nums, primary = number_anchor if number_anchor is not None else number_roles(claim_text)
    carried = [n["raw"] for n in claim_nums]
    comparing = u.get("comparison") or u.get("evidence") == "comparison"
    if primary:
        if u.get("part_whole"):
            why = "子集的实际人数/数量：突出已发生的结果，同时明确给出总体"
        elif comparing:
            why = "主张所指的比较侧：与另一指标同屏，先核对指标分母和口径"
        elif u.get("evidence") == "series" and _arrival_value(primary, text):
            why = "变化后的结果值：本页最大的数字应是它，不是基期"
        elif _hit(claim_text, _ASK_WORDS):
            why = "请求的资源量：金额/数量属于要做的决定，而非趋势终值"
        else:
            why = "主证据量：让观众看见可核验的量，不替它编造变化"
        maxi.append(f"{primary['raw']} — {why}")
    for n in [n for n in claim_nums if n is not primary][:2]:
        if u.get("part_whole") and primary and n["unit"] == primary["unit"]:
            why = "总体/分母：和子集同屏，但不是变化前的基期"
        elif comparing:
            why = "另一比较对象：注明各自定义，口径不同不得直接相减"
        elif u.get("evidence") == "series" and primary and n["unit"] == primary["unit"]:
            why = "变化前的基期：与结果同屏但小一档，让变化有参照"
        elif n["unit"] in ("天", "月", "个月", "年", "小时", "分钟", "秒"):
            why = "执行期限：保留在请求旁作条件，不能与金额当作两端"
        else:
            why = "支撑条件：不与主数字强行比较，不称作基期"
        weak.append(f"{n['raw']} — {why}")
    if claim_text and not primary:
        maxi.append(f"「{claim_text[:26]}」— 结论句，本页第一落点必须落在它身上")
    if comparing:
        maxi.append("比较对象与口径 — 两端要能辨认；只有分母一致时才画差值")
    if u.get("evidence") in ("structure", "sequence"):
        maxi.append("关系的形状（层级/顺序）— 结构本身就是这一页的视觉对象")

    for n in [x for x in (u.get("numerals") or [])
              if not x["year"] and x["raw"] not in carried][:4]:
        weak.append(f"{n['raw']} — 支撑证据：与结论同屏但小一档，读者需要时能找到")
    if _hit(text, ("来源", "口径", "期间", "统计", "抽样", "估算", "source", "basis")):
        weak.append("来源/口径/期间 — 必须可见但不争夺注意力（小字、固定位置）")
    if u.get("evidence") == "series":
        weak.append("坐标轴与刻度 — 让基线和量级可核验，不参与叙事")
    if u.get("human") and claim.get("source") == "extracted":
        weak.append("人类主体的具体称谓 — 除非它就是结论的主语")

    for h in _HEDGES:
        if h in text:
            kill.append(f"「{h}」— 判断模糊化：要么下结论，要么不放这一页")
    for f in _FILLERS:
        if f in text and f not in claim_text:
            kill.append(f"「{f}」— 零信息量形容词，删除后意义不变")
    counts: dict[str, int] = {}
    for n in u.get("numerals") or []:
        if not n["year"]:
            counts[n["raw"]] = counts.get(n["raw"], 0) + 1
    # 序列位置坐标（「第 9 个月」）不算「重复」：它在结论里点明落点、在证据里
    # 必须作为位置标注存在（图上就那一列）。把它列进删除清单等于叫作者删掉
    # 本页的主张（实测：收敛页的删除清单里出现「9 个月 的重复出现」）。
    # 真正要删的是同一句话里的数字重复，不是结论与证据之间必要的那一次呼应。
    axis_values = {(round(float(m.group(1).replace(",", "")), 6), m.group(2))
                   for m in _AXIS_TIME_TOKEN.finditer(text)}
    dupes = [raw for raw, c in counts.items() if c >= 2 and not any(
        (round(n["value"], 6), n.get("unit") or "") in axis_values
        for n in (u.get("numerals") or []) if n["raw"] == raw)]
    if dupes:
        kill.append(f"{'、'.join(dupes[:3])} 的重复出现 — 同一数字在一页出现两次就删一次")
    return {"maximize": maxi, "weaken": weak, "delete": kill}


# ─────────────────────────────────────────────────────────────────────
# 5 · 视觉角色（Visual Role）
# ─────────────────────────────────────────────────────────────────────
def visual_role(u: dict, *, index: int, total: int, tension: str,
                claim: dict) -> dict:
    """页面在整副 deck 里承担什么：建立 / 解释 / 对比 / 证明 / 说服 / 收束。

    **内容意义先决，位置只做兜底**：数字页在哪一页都是 prove，对比页在哪一页都是
    compare；只有内容本身说不出角色时（纯观点/纯标题），才用「第一页 / 最后一页」
    这个叙事位置决定 establish / summarize。
    """
    ev = str(u.get("evidence") or "none")
    witness = bool(u.get("human") or u.get("scene"))
    ask = _hit(str(claim.get("text") or ""), _ASK_WORDS)
    if u.get("comparison") or ev == "comparison":
        role = "compare"
        why = "内容本身有两端对比，张力来自内容而不是装饰。"
        alts = [["explain", "把对比讲成并列说明＝抹平了本来存在的选择"]]
    elif ask:
        role = "summarize"
        why = "这一页要的是一个决定：把主张收成可执行的一句（做什么、谁来做、什么时候）。"
        alts = [["prove", "在要决定的页面上继续堆证据＝把决定推迟到下一次提问之后"]]
    elif ev in ("series", "number", "part_whole"):
        role = "prove"
        why = "数字承担论证：这一页的说服力来自可核验的量，而不是措辞。"
        alts = [["persuade", "用形容词说服＝把可核验的东西换成不可核验的"]]
    elif index in (0, total - 1) and ev in ("none", "proposition", "structure", "sequence") \
            and not int(u.get("distinct_numerals") or 0) and not u.get("relations"):
        # 开场与收尾在没有可核验的量时按叙事位置取角色：这一页的职责是立住或回收
        # 整套主张，不是解释一个结构。只有一句主张的封面被判成「说明页」，
        # 焦点与构图会跟着落到一个并不存在的层级图上（CASE_006 s01/s12 实测）。
        if index == 0:
            role = "establish"
            why = "开场页建立世界与主张：观众从这里决定要不要继续读。"
            alts = [["explain", "开场就解释细节＝在观众建立兴趣之前要求注意力"]]
        else:
            role = "summarize"
            why = "收尾页回收开场的决定：把主张收成一句可执行的话，不用新装饰稀释请求。"
            alts = [["prove", "收尾再补证据＝把决定推迟到最后一次提问之后"]]
    elif ev in ("structure", "sequence"):
        role = "explain"
        why = "关系的形状比措辞更能说明机制，观众要的是结构。"
        alts = [["prove", "用数字解释结构＝把关系压成孤立数值"]]
    elif witness and ev in ("none", "proposition"):
        role = "prove"
        why = (f"内容里有可指认的现场/对象（{','.join(u.get('subjects') or []) or '人物'}）："
               "这一页靠「确有其事」成立，图片或记录本身就是证词。")
        alts = [["persuade", "把证据换成形容词：观众会相信形容不出来的东西吗"],
                ["explain", "把现场讲成说明＝把可信度换成可读性"]]
    elif index == 0:
        role = "establish"
        why = "开场页建立世界与主张，观众从这里决定要不要继续读。"
        alts = [["explain", "开场就解释细节＝在观众建立兴趣之前要求注意力"]]
    elif index == total - 1 and total > 1:
        role = "summarize"
        why = "收尾页把主张收成一句可执行的话（做什么、谁来做、什么时候）。"
        alts = [["prove", "收尾再补证据＝把决定推迟到最后一次提问之后"]]
    elif ev == "proposition" and str(tension or "").strip():
        role = "persuade"
        why = (f"这一页对着观众的疑虑成立（「{str(tension)[:24]}」），不回应它，"
               "主张再漂亮也不可信。")
        alts = [["explain", "回避疑虑只讲优点＝观众带着问题离场"]]
    else:
        role = "persuade" if ev in ("proposition", "none") else "explain"
        why = ("内容以观点为主：这一页的职责是把观点说得比周围信息更清楚。"
               if role == "persuade" else
               "内容提供的信息需要被组织：结构清楚比说得漂亮重要。")
        alts = [["prove", "没有证据却摆出证据的姿态＝最容易被识破的一种设计"]]
    return {"role": role, "why": why, "alternatives": alts}


# ─────────────────────────────────────────────────────────────────────
# 6 · 焦点判定（Focus Determination）
# ─────────────────────────────────────────────────────────────────────
def _metric_attribution(text: str, nums: list[dict]) -> list[tuple[dict, str]]:
    """每个数字归属它前面最近的那个指标名（「履约成本 11.2 元」→ 履约成本）。"""
    spans = _clause_spans(text)
    cursor, pairs = 0, []
    for n in nums:
        pos = text.find(n["raw"], cursor)
        if pos < 0:
            pos = cursor
        cursor = pos + len(n["raw"])
        clause = next((text[a:b] for a, b in spans if a <= pos < b), text)
        prefix = clause[:max(0, pos - next(a for a, b in spans if a <= pos < b))] \
            if any(a <= pos < b for a, b in spans) else clause
        # 取**离数字最近**的那个指标名（「…口岸清关时效在 1.8」→ 清关时效，
        # 不是句首的「越南」）：指标名归属错了，集中度与焦点判据一起错。
        head = _metric_of_clause(prefix) or _metric_of_clause(clause)
        pairs.append((n, head[-1] if head else ""))
    return pairs


def _canonical_metrics(tokens: list[str]) -> list[str]:
    """指标名归一：页面中已有更短的核心名时，用核心名（单均履约成本 → 履约成本）。

    不归一会把「同一个指标的不同写法」当成两个指标，集中度被摊薄，
    焦点判据随之把一个真正的单指标页误判成多量纲罗列。
    """
    uniq = [t for t in dict.fromkeys(tokens) if t]
    out = []
    for t in uniq:
        shorter = [o for o in uniq if o != t and o in t]
        out.append(min(shorter, key=len) if shorter else t)
    return out


def _metric_concentration(text: str, nums: list[dict]) -> float:
    """页面数字被**同一个指标**占住的比例：越高，这一页越是「一个量」的页。"""
    pairs = _metric_attribution(text, nums)
    raw = [m for _, m in pairs if m]
    if not raw:
        return 0.0
    canon = dict(zip(dict.fromkeys(raw), _canonical_metrics(raw)))
    named = [canon.get(m, m) for m in raw]
    if not named:
        return 0.0
    return max(named.count(m) for m in set(named)) / len(pairs)


def _numbers_are_support(claim_text: str, u: dict, carried: list[dict],
                         text: str) -> bool:
    """数字是否只是支撑：**主张里没有数字，而证据横跨三种以上量纲，且页面
    不是「同一个指标的不同取值」**时，这一页要立住的是那句话。

    典型误判（CASE_006 s05）：风险页的主张是「清关与用工无法靠补贴解决」，
    证据里却有天 / 百分比 / 元三种量纲 —— 让其中任何一个当主语都会把
    「阻力」读成「某个指标的值」。这时数字退到支撑位，第一落点回到那句话。
    反例（s02）：同一页里履约成本出现五次（占 62%），它就是这一页的主语，
    不能因为主张句没写数字就把它降成支撑。
    """
    if not claim_text or evidence_numerals(claim_text):
        return False
    units = {str(n.get("unit") or "").strip() for n in carried}
    if len(units) < 3:
        return False
    return _metric_concentration(text, carried) < 0.5


def focus_of(role: str, u: dict, claim: dict, media: dict | None = None, *,
             number_anchor: tuple[list[dict], dict | None] | None = None,
             page_text: str = "") -> dict:
    """第一落点：哪个元素承担结论，以及为什么不是别的元素。

    顺序即优先级：**通过必要性测试的图像 > 结论里的数字 > 那句话 > 标题**。
    图像之所以能排在最前，是因为它先通过了「没有它这一页会下降在哪里」这一问；
    没过测试的页面上根本不存在图像，第一落点自然回到文字。
    """
    media = media or {}
    # 结论里的基期不能因为「出现在前」就压过结果；与信息权重同用一份判定。
    carried, primary = (number_anchor if number_anchor is not None
                        else number_roles(claim.get("text") or ""))
    if not carried and u.get("evidence") in ("number", "series"):
        carried = [n for n in (u.get("numerals") or []) if not n.get("year")][:1]
        primary = carried[0] if carried else None
    has_image = media.get("decision") in ("required", "reuse")
    claim_text = (claim.get("text") or "").strip()
    # 数字是主语还是支撑：主张没点名任何量、证据横跨多量纲、且页面不是
    # 「同一个指标的不同取值」时，第一落点回到那句话（见 _numbers_are_support）。
    support_only = _numbers_are_support(claim_text, u, carried, page_text)
    if has_image:
        choice = {"element_role": "image_subject" if media.get("function") != "witness"
                                     else "image_witness",
                  "type": "image",
                  "why": "本页的图像是主语/证词（已通过必要性测试）：第一落点是它，"
                         "文字退到解说位——否则图像就只是背景花纹。"}
        rejected = [["hero_statement", "用一句话当第一落点＝把已经赢得的现场感再退回文字"],
                    ["kpi_row", "把数字排成一行＝观众先看数字后看主张，顺序反了"]]
    elif u.get("part_whole") and carried:
        part = (primary or carried[-1])["raw"]
        whole = next((n["raw"] for n in carried if n is not primary), "总体")
        choice = {"element_role": "ratio_main", "type": "text",
                  "why": f"「{part}」是已经发生的子集；同屏写清「{whole}」的总体，"
                         "不把整体→子集误画成下降，也不让比例脱离分母。"}
        rejected = [["trend_line", "总量和子集不是先后两个时间点：折线会虚构下降"],
                    ["card_grid_4", "一个分子与分母不需要四张等权卡片"]]
    elif (u.get("comparison") or u.get("evidence") == "comparison") \
            and int(u.get("distinct_numerals") or 0) >= 2:
        # 六个以上的数字是**一条序列**，不是两端对照：同屏排成数字墙会丢掉形状，
        # 交给图表（同一基线 + 单一高亮终值）才读得出趋势。
        many = int(u.get("distinct_numerals") or 0) >= 6
        choice = {"element_role": "comparison_field",
                  "type": "chart" if (u.get("has_chart") or many) else "text",
                  "why": ("这一页有 %d 个数字：把它们排进文本框读者要自己连点成线，"
                          "交给同一基线的图表，只高亮主张所指的终点。" %
                          int(u.get("distinct_numerals") or 0)) if many else
                         "把两端的指标名与数值同屏标出；只有同口径才共享轴线并标差值，"
                         "分母不同时先说明比较边界。"}
        rejected = [["two_pie", "两个饼图：占比比较最不可读的一种形式"],
                    ["radar", "雷达图形状相似度高，差异看不出来"],
                    ["side_by_side_cards", "左右卡片墙：视觉等权，读者得自己找答案"]]
    elif carried and role in ("prove", "summarize", "compare") and not support_only:
        raw = (primary or carried[0])["raw"]
        if (_hit(claim_text, _ASK_WORDS)):
            why = f"「{raw}」是请求的资源量：它和动作同屏，期限不被误称作基期。"
        elif u.get("evidence") == "series" and len(carried) >= 2 and u.get("same_unit"):
            why = f"「{raw}」是变化终值：让它先被看见，再给出较小的基期参照。"
        else:
            why = f"「{raw}」承担本页证据：保持来源与口径可见，不为数字编造基期。"
        # 单一结论量或预算请求用原生文字直立；真有时间序列/作者声明图表
        # 才让图表承担焦点，不能把每一个数字机械地变成一张图。
        chart_needed = bool(u.get("has_chart")
                            or (u.get("evidence") == "series" and len(carried) >= 2)
                            or int(u.get("distinct_numerals") or 0) >= 6)
        choice = {"element_role": "kpi_main",
                  "type": "chart" if chart_needed else "text", "why": why}
        rejected = [["card_grid_4", "四张等权卡片：等权＝没有结论，观众平均用力后什么都没记住"],
                    ["donut", "把一句话画成一圈：环形图要求读者心算比例，结论被稀释"],
                    ["gauge", "仪表盘指针只表达「好/不好」，不表达「多少」"]]
    elif u.get("evidence") in ("structure", "sequence"):
        choice = {"element_role": "structure_map", "type": "chart",
                  "why": "层级/顺序是内容本身的形状，画出来比写出来短。"}
        rejected = [["icon_row", "一排图标：图标不承载关系，只承载「我们有很多模块」"],
                    ["card_stack", "卡片堆叠把结构压成清单，关系丢失"]]
    elif role == "persuade" or (role == "establish" and len(claim_text) <= 42) \
            or (support_only and claim_text):
        why = ("焦点是这一页要立住的那句话：字阶与留白负责它的分量。"
               if not support_only else
               "主张里没有一个可以立住的量：证据横跨多种量纲，任何一个数字当主语都会把"
               "「这件事为什么难」读成「某个指标是多少」——数字退到支撑位。")
        choice = {"element_role": "statement_text", "type": "text", "why": why}
        rejected = [["banner_quote", "色块包一句引用：包起来的句子看起来像广告"],
                    ["stock_photo", "配一张氛围图：把不可回答的问题装饰掉"]]
    else:
        choice = {"element_role": "headline", "type": "text",
                  "why": "这一页以陈述为主，标题即焦点（标题写结论，不写字段名）。"}
        rejected = [["subtitle_heavy", "副标题抢主标题：层级变成装饰"],
                    ["kpi_row", "无证据支撑地摆一排数字：数字成了布景"]]
    return {**choice, "rejected": [{"option": o, "why_not": w} for o, w in rejected]}


# ─────────────────────────────────────────────────────────────────────
# 7 · 构图推理（Composition Reasoning）
# ─────────────────────────────────────────────────────────────────────
# 六个算子的中文释义住文档（SKILL.md §3 构图行）：
# plan 里 chosen 键已唯一确定算子，label 是零信息重复，不再输出。


# 构图算子：每个算子只在**内容的形状**合适时成立。没有「页面类型 → 构图」的查表；
# 同一类内容因为数字个数、证据形态、是否存在通过测试的图像而落到不同算子上。
# 并列时的次序：空间优先（留白 → 数据场 → 线性 → 张力 → 编辑 → 图像）。
# 它只在分数打平时生效，不能盖过内容判断。
_COMPOSITION_TIEBREAK = ("big_whitespace", "data_field", "linear_structure",
                         "asymmetric_tension", "editorial", "image_narrative")
_GRAMMAR_PREFERENCE = {
    "evidence_field": "data_field", "soft_asymmetry": "asymmetric_tension",
    "grid": "editorial", "quiet": "big_whitespace", "spotlight": "image_narrative",
    "linear": "linear_structure",
}


def _composition_scores(u: dict, role: str, media: dict, text_len: int,
                        grammar: str, claim: dict | None = None) -> dict[str, float]:
    """各算子的适配分（内部用，用完即弃；plan 里只留 chosen/why/rejected）。

    分来自这一页的事实（结论有无 / 证据形态 / 数字个数 / 内容体量 /
    图像是否通过必要性测试），不来自页面类型。
    """
    claim = claim or {}
    ev = str(u.get("evidence") or "")
    n = int(u.get("distinct_numerals") or 0)
    dense = float(u.get("numeric_density") or 0.0)
    has_image = media.get("decision") in ("required", "reuse")
    s: dict[str, float] = {}
    # 图像叙事只在图像通过必要性测试时存在（否则它连候选都不是）
    # 图像一旦通过必要性测试，它就是这一页的第一落点——构图必须承载它，
    # 否则「焦点是图、构图是留白」自相矛盾。
    s["image_narrative"] = (4.5 if has_image else -99.0) + (1.5 if role == "establish" else 0.0)
    # 同一数量轴不能把不一致的单位并成两端；另有图表声明也不替它捏造同口径。
    # 数据场要有**可对齐的同量纲数字**：一个数字都没有的页（纯层级/纯陈述）
    # 不被「数据场」接住——否则四层架构页会被判成数据网格，网格里却没有数据。
    s["data_field"] = (3.0 if ev in ("series", "comparison") and n >= 2
                       and u.get("same_unit", True) else 0.0) \
        + (2.0 if n >= 3 and u.get("same_unit", True) else 0.0) \
        + (1.0 if dense >= 6 and u.get("same_unit", True) else 0.0) \
        + (0.5 if u.get("comparison") and n >= 2 else 0.0)
    s["big_whitespace"] = (3.0 if (n == 1 and ev in ("number", "series")) else 0.0) \
        + (3.25 if ev == "part_whole" else 0.0) \
        + (2.0 if role == "persuade" else 0.0) + (1.0 if text_len <= 40 else 0.0) \
        - (1.5 if n >= 3 else 0.0)
    if not claim.get("text") and ev in ("none", "proposition"):
        # 无结论页用最少结构：结论没落定之前铺开，只会把缺席藏起来。
        s["big_whitespace"] += 1.0
    s["linear_structure"] = (4.5 if u.get("relations") else
                             3.0 if ev in ("sequence", "structure") else 0.0)
    s["asymmetric_tension"] = (2.5 if u.get("comparison") else 0.0) \
        + (1.5 if role == "compare" else 0.0) + (1.0 if n >= 2 else 0.0)
    s["editorial"] = (2.0 if text_len > 60 else 0.0) \
        + (1.5 if role == "summarize" else 0.0) + (1.0 if n == 0 else 0.0) \
        + (0.5 if text_len > 120 else 0.0)
    if role == "establish" and not has_image:
        s["big_whitespace"] += 1.5               # 开场建立权威靠空间，不靠铺陈
    if role == "summarize" and n == 0 and text_len <= 40:
        s["big_whitespace"] += 1.5               # 一句话收束（致谢/问答）：空间替它把话停住
    preferred = _GRAMMAR_PREFERENCE.get(str(grammar or "").strip())
    if preferred and s.get(preferred, -99) > 0:
        s[preferred] += 0.75                     # 世界的构图纪律只做同分倾向
    return s


def _composition_choice(u: dict, role: str, media: dict, text_len: int,
                        grammar: str, claim: dict | None = None) -> dict:
    """一次算完：适配分 → 选中的算子 + 为什么 + 落选的为什么落选。"""
    s = _composition_scores(u, role, media, text_len, grammar, claim)
    order = {name: i for i, name in enumerate(_COMPOSITION_TIEBREAK)}
    chosen = max(s, key=lambda k: (s[k], -order[k]))
    return {"chosen": chosen, "rejected": _composition_rejections(chosen, s)}


def _composition_rejections(chosen: str, scores: dict) -> list[dict]:
    """没选中的五个算子：以这一页的事实说明为什么落选。"""
    out = []
    for option, score in sorted(scores.items(), key=lambda kv: -kv[1]):
        if option == chosen:
            continue
        if score <= 0:
            continue      # 内容不成立的算子不是竞争者：无竞争时 rejected 为空
        # 图像叙事 -99（图像没通过必要性测试）时恒为末位，进不了 [:2]，
        # 落选理由只可能是「输给内容成立的算子」——无需单独分支。
        if option == "data_field":
            why_not = "数字不足或不同基线：铺开只会把结论稀释成背景"
        elif option == "big_whitespace":
            why_not = "这一页需要同屏参照，大留白会把该比的拆散"
        elif option == "linear_structure":
            why_not = "内容没有顺序关系：位置一旦表达顺序，读者会去找不存在的阶段"
        elif option == "asymmetric_tension":
            why_not = "两方等权时不制造倾向：张力会变成没有依据的戏剧化"
        elif option == "image_narrative":
            why_not = "图像只能当氛围用：装饰性图像一律不进这一页"
        else:
            why_not = "这一页的字数与数字撑不起编辑节奏：排版会显得在凑版面"
        out.append({"option": option, "why_not": why_not})
    return out[:2]


def _composition_why(chosen: str, u: dict, media: dict) -> str:
    """选中它的理由：一句话，指到这一页的事实上。"""
    n = int(u.get("distinct_numerals") or 0)
    if chosen == "image_narrative":
        return (f"这一页的{'主语' if media.get('function') != 'witness' else '证词'}是具体实体"
                f"（{media.get('function')}）：图像承担现场，文字退到解说位。")
    if chosen == "data_field":
        return (f"{n} 个同量纲数字交给对齐与数据场；先核对分母与期间，"
                "同口径才共用基线，不让装饰抢证据。")
    if chosen == "big_whitespace":
        if u.get("part_whole"):
            return "突出已发生的子集，安静地给出总体分母；不把一个证据拆成两块等权卡。"
        return ("只有" + ("一个数字" if n == 1 else "一句话")
                + "要立住：留白把结论从噪音里隔离出来，空间本身就是分量。")
    if chosen == "linear_structure":
        if u.get("evidence") == "structure":
            return "主体与对象的关系同屏可读；只画已明示的归属/职责，不由列举顺序补上下级或时间。"
        return "内容本身有序（步骤/阶段）：位置表达推进，轴与间距比装饰准确。"
    if chosen == "asymmetric_tension":
        return ("两端承载不同主张：让主张侧先被看见，但先核对指标口径，"
                "不可比时不让空间暗示一个虚假的差值。")
    return "这一页以阅读节奏为主：字阶与栏宽决定先读什么、读多久。"


def composition_of(role: str, u: dict, *, composition_grammar: str = "",
                   media: dict | None = None, claim: dict | None = None,
                   content_len: int = 0) -> dict:
    """为什么是这种构图，为什么不是其他几种——从这一页的事实推，不查表。

    体量取整页内容长度（空间需求），不是结论句长度：长内容撑得起编辑节奏，
    短内容立不住的东西不硬撑。
    """
    media = media or {}
    claim = claim or {}
    text_len = int(content_len or 0) or len(claim.get("text") or "")
    picked = _composition_choice(u, role, media, text_len, composition_grammar, claim)
    chosen = picked["chosen"]
    return {"chosen": chosen,
            "why": _composition_why(chosen, u, media),
            "rejected": picked["rejected"]}


# ─────────────────────────────────────────────────────────────────────
# 8 · 空间结构（Spatial Structure：职责，不是坐标）
# ─────────────────────────────────────────────────────────────────────
def spatial_of(comp: dict, u: dict | None = None) -> dict:
    """空间职责：主区 / 安静区 / 阅读路径 / 四层权重。坐标由作者给。"""
    chosen = comp.get("chosen")
    if chosen == "big_whitespace":
        path, primary, quiet = "焦点 → 真实支撑（若有）→ 收束", "主张或证据的唯一焦点区", "大面积安静面"
        duty = "保护主语：空白隔开竞争信息，不因版面空就捏造参照或添加装饰"
    elif chosen == "data_field":
        path, primary, quiet = "结论 → 对照 → 明细", "上部结论带 + 中部数据场", "分组之间"
        duty = "承载证据密度：秩序来自网格与对齐，留白只出现在分组之间"
    elif chosen == "asymmetric_tension":
        path, primary, quiet = "主张侧 → 对照侧 → 比较边界", "被推荐的一侧（大尺度）", "对照侧周围"
        duty = "使两端关系可读：不靠等权卡片、不凭空间尺度捏造不可比的差值"
    elif chosen == "linear_structure" and (u or {}).get("evidence") == "structure":
        path, primary, quiet = "主体 → 职责/对象 → 关系", "关系与归属的共同阅读区", "关系组之间"
        duty = "分组与辨认归属；未给出上下级就不用连线暗示层级，空白不代表时间"
    elif chosen == "linear_structure":
        path, primary, quiet = "起点 → 序列 → 终点", "轴线上第一个与当前节点", "节点之间（时间）"
        duty = "分隔与推进：间距表达节奏，节点之间的空白是时间"
    elif chosen == "image_narrative":
        path, primary, quiet = "画心 → 标题 → 说明", "画心（图像主体）", "文字侧负空间"
        duty = "承载情绪与现场：文字侧留白是给标题的呼吸位"
    else:
        path, primary, quiet = "标题 → 论据 → 出处", "标题与导语区", "栏间留白"
        duty = "建立阅读节奏：栏宽与字阶让读者知道先读什么、读多久"
    return {"reading_path": path, "primary_zone": primary, "quiet_zone": quiet,
            "whitespace_duty": duty}


def tension_of(item: dict, brief: dict, role: str) -> dict:
    """页面究竟回答哪一道阻力：作者声明优先；不相关时不虚构戏剧冲突。"""
    local = str(item.get("tension") or "").strip()
    if local:
        return {"issue": local, "source": "author",
                "why": "作者指定本页需要回答的阻力；先把主张对准它，再决定画面力度。"}
    deck = str(brief.get("tension") or "").strip()
    if deck and role == "persuade":
        return {"issue": deck, "source": "deck",
                "why": "说服页要正面回应整套决定面临的阻力，不能用漂亮画面绕过它。"}
    return {"issue": None, "source": "not_asserted",
            "why": "这一页靠证据或章节职责成立；没有页级冲突，不凭空制造张力。"}


def _weight_label(value) -> str:
    """从权重「标签 — 理由」提取排版短名；完整理由只留在判断卡。"""
    text = str(value)
    if text.startswith("「") and "」— " in text:
        return text.split("」— ", 1)[0] + "」"
    return re.split(r"\s*—\s+", text, maxsplit=1)[0]


# ── 排版尺度：由本页内容量推导的可执行约束（可读域，不是字阶模板）──────────
# 行长、行距与内边距是**物理可读域**（像对比度 4.5:1），不是风格：中文方块字
# 一行超过 45 个汉字，投影尺度下读者的回扫会丢行；少于 22 个则每行都在半句处
# 折断。此前骨架只给一句散文纪律，作者凭手感定栏宽——实测同一份内容里出现
# 60–68 汉字/行的正文块（CASE_006 s07/s08/s10）。
_MEASURE_MAX_CJK = 45          # 行长上限（超过即回扫丢行）
_MEASURE_MIN_CJK = 22          # 行长下限（低于即断句破碎）
_LEAD_MAX_CJK = 20             # 主张/标题每行上限（大字阶，靠行数不靠缩放）
# 断行候选，按**语义强度**排序；(token 组, 断在 token 前还是后)。
# 只收「断在这里不会割裂词」的位置：停顿标点 > 系词/转折连词 > 时间数量短语 > 的。
# 介词与助动词（在/把/让/能…）一律不收——实测会把「用工」切成「与用｜工」。
_BREAK_RULES = (
    (("，", "、", "；", "：", "。", "！", "？"), "after"),          # 停顿：最强
    (("而是", "而非", "不是", "不再", "尚未", "所以", "因此", "同时",
      "另外", "其中", "其次", "最后", "首先", "就是", "才是", "但", "却",
      "则", "是"), "before"),                                     # 系词/转折：领起谓语
    (("年", "季度", "月", "日", "天", "小时", "倍"), "after"),      # 时间数量短语之后
    (("的",), "after"),                                           # 定语之后（悬挂）
)
_NO_LINE_START_CJK = "，。、；：？！）〉》」』】〕｝·…—～”’"
_NO_LINE_END_CJK = "（《「『【〔｛“‘"
_UNIT_AFTER_DIGIT = re.compile(
    r"^\s*(亿元|万元|万户|万单|万人|万家|万次|个月|分钟|小时|美元|元|家|人|个|台|"
    r"名|位|件|次|天|月|年|%|％|pp|倍)")


def suggest_break(sentence: str, max_line: int = _LEAD_MAX_CJK) -> str | None:
    """给主张一句**断行建议**：在语义边界处断，不在数字与单位之间断。

    断行决定中文标题的视觉形状：机械按框宽折行会把「11.2 元」拆成两行、
    把「，」甩到行首。这里只给一处断口（两行），用「｜」标出；作者仍可改写。
    """
    text = str(sentence or "").strip()
    if len(text) < 8 or len(text) <= max_line:
        return None
    cap = max(max_line, (len(text) + 1) // 2 + 4)
    best, best_score = None, None
    for strength, (group, side) in enumerate(_BREAK_RULES):
        for i in range(1, len(text)):
            hit = next((w for w in group if text[i:i + len(w)] == w), None)
            if not hit:
                continue
            at = i + len(hit) if side == "after" else i
            left, right = text[:at], text[at:]
            if len(left) < 4 or len(right) < 4:
                continue
            if max(len(left), len(right)) > cap:
                continue
            if right[0] in _NO_LINE_START_CJK:
                continue                       # 行首禁则：标点不能领行
            if left[-1:] in _NO_LINE_END_CJK:
                continue                       # 行尾禁则：开引号不能收尾
            if left[-1:].isdigit() and _UNIT_AFTER_DIGIT.match(right):
                continue                       # 数字与单位不拆行
            score = (strength, abs(len(left) - len(right)))
            if best_score is None or score < best_score:
                best, best_score = f"{left}｜{right}", score
    return best


def measure_of(text_len: int, *, has_long_lead: bool = False) -> dict:
    """按内容长度给栏宽起点；不是实测字体容量或固定排版配额。"""
    if text_len >= 220:
        cjk, note = 30, "长文窄栏：信息密度高，窄栏换取回扫可靠"
    elif text_len >= 120:
        cjk, note = 34, "中长文本：两栏或窄单栏，避免一行横跨整页"
    else:
        cjk, note = 38, "短文本：栏宽可以放开，但仍不横跨整页"
    return {"body_measure_cjk": cjk, "why": note,
            "limit": f"{_MEASURE_MIN_CJK}–{_MEASURE_MAX_CJK} 汉字/行（启发式建议，实际字体与投影须另验）"}


BASE_DISCIPLINE = ("结论按语义停顿断行，动词与对象相连、数字不与单位拆开；"
                   "标题与支撑共用阅读轴，字距克制，装不下先删句而非压行距或缩字号。")


def typography_of(claim: dict, weight: dict, focus: dict, role: str,
                  u: dict | None = None, *, text_len: int = 0,
                  number_anchor: tuple[list[dict], dict | None] | None = None) -> dict:
    """把一份数字锚与信息权重转成可执行的编辑次序；不派发坐标/模板。"""
    weak = weight.get("weaken") or []
    _, primary = number_anchor if number_anchor is not None else number_roles(claim.get("text") or "")
    # 以前拿「结论句—理由」的字符串按空格切，分隔符恰好没空格，
    # 把判断理由当成了将排上页面的主语。主语必须来自 claim/数字事实。
    focal = primary["raw"] if primary else (
        claim.get("text") or ("本页标题" if claim.get("source") == "frame" else "未决结论"))
    secondary = _weight_label(weak[0]) if weak else None
    if focus.get("type") == "image":
        rule = ("让现场/物件先被看见；注解贴合图像安全区的轴线与负空间，"
                "文本框边距保持可读，不用大标题遮住证词主体。")
    elif focus.get("element_role") == "ratio_main":
        rule = ("子集先读、总体分母紧跟；数量与单位不拆行，标签沿同一阅读轴，"
                "不把一个证据拆成两张等权卡或画成趋势。")
    elif focus.get("element_role") == "comparison_field":
        rule = ("两端指标名与数字分别对齐；分母/期间就近标注，只有同口径才共享刻度轴。"
                "不可比时用留白标出边界，不用面积暗示虚构倍数。")
        # 主张讲的是「差」时，图形对象是差本身。两条几乎平行的线各带一套数值标签，
        # 会在同一个 x 上挤到一起（实测渲染：末端 42.1 与 38.9 两个标签上下贴死），
        # 而且读者无法把数字归属到序列——颜色成了唯一的身份线索，正是 SKILL §2
        # 禁止的那件事。差直接画成一条序列，或只标端点。
        if _hit(str(claim.get("text") or ""), _GAP_WORDS):
            rule += ("本页讲的是差：把差值画成一条序列（每个节点一个数），"
                     "或只标端点——不要给两条近重合的线各配一套数值标签，"
                     "同 x 的标签会互压且认不出归属。")
    elif (u or {}).get("evidence") == "structure" and focus.get("element_role") == "structure_map":
        rule = ("主体与职责/对象按成对关系对齐，必要限定贴近所属对象；"
                "层级只按明确归属表达，不把职责分工改成时间轴或推测汇报线。")
    elif focus.get("element_role") == "structure_map" or role == "explain":
        rule = ("节点→机制沿一条清楚的轴线排字；标签、解释共用文字边界，"
                "在语义节点断行，节点间距比容器与图标更能表达顺序。")
    elif focus.get("element_role") == "kpi_main" and role == "summarize":
        rule = ("请求动作与资源量同行，数字及单位不拆行；期限在下一阅读层沿同轴退后，"
                "两种单位不共用数量刻度，不用等权卡片制造第二焦点。")
    elif focus.get("element_role") == "kpi_main" and (u or {}).get("evidence") == "series":
        rule = ("终值与单位为主轴，基期退一层；可比数字才共享刻度/基线，"
                "期间与出处就近但不抢主值，勿用线框填空。"
                if (u or {}).get("same_unit", True) else
                "量纲不同先统一口径或拆开说明；不得为齐版而共用数量轴。")
    elif focus.get("element_role") == "kpi_main":
        rule = ("主数字连同单位先读；说明、出处沿同一阅读轴退后。"
                "只有真实基期才画比较，用留白而非加字距或卡片填满画面。")
    else:
        rule = BASE_DISCIPLINE
    scale = {"lead_break": suggest_break(str(claim.get("text") or "")),
             **measure_of(int(text_len or 0))}
    return {"lead": focal, "support": secondary, "discipline": rule, "scale": scale}


# ─────────────────────────────────────────────────────────────────────
# 9 · 媒体必要性（Media Necessity：为什么没有它页面会下降）
# ─────────────────────────────────────────────────────────────────────
def _media_hint(function: str, cue: str) -> dict:
    """词表提示而非决定：标明来源是 hint，并给出作者如何声明。"""
    return {"decision": "none", "source": "hint", "function": None,
            "suggested": function,
            "necessity": f"词表命中（{cue}），但它是否构成{'证词' if function == 'witness' else '主体'}需要作者判断："
                         "未声明则不出图。如需图像，在 brief 声明 asset: required（画面主体写 asset_subject）。"}


def media_necessity(u: dict, role: str, *, declared: str | None = None,
                    has_chart: bool = False) -> dict:
    """图片必须通过必要性测试：**没有它，这一页会下降在哪里？**

    唯一两种可成立的答案：
      witness  — 它是证词：现场/人/物件本身就是主张所声称的东西；
      subject  — 它就是主语：产品/世界本身需要被看见（开场建立）。
    答不出来的，判定为不出图——装饰图、氛围图、无意义背景一律过不了这道测试。
    """
    if declared in ("required", "reuse", "none"):
        return {"decision": declared, "source": "author",
                "function": "declared", "necessity": "作者显式声明：压过一切判断。"}
    if has_chart:
        return {"decision": "none", "source": "judgment",
                "function": None,
                "necessity": "本页已有图表承担注意力，再放图片＝两个焦点互相削价。"}
    presence = bool(u.get("human") or u.get("scene"))
    physical = [s for s in (u.get("subjects") or []) if s in _PHYSICAL_SUBJECTS]
    # 词表只能提示「内容里可能有人/场所/实体」，不能决定「这张图是证词还是主语」。
    # 图像是否成立要作者判断：未声明则不出图，并把问题交还作者（不是默默不出、也不默默出）。
    if role == "establish" and presence:
        return _media_hint("subject", "人物或场所词")
    if role == "establish" and physical:
        return _media_hint("subject", f"实体世界词（{physical[0]}）")
    if role == "prove" and presence and str(u.get("evidence")) not in ("series", "comparison", "part_whole"):
        return _media_hint("witness", "人物、场所或记录动作")
    reasons = {
        "compare": "对比页的注意力属于两端本身，图片会把比较读成氛围。",
        "explain": "结构页的注意力属于关系本身，图片无法替代关系。",
        "summarize": "收尾页的注意力属于要做的决定，图片会把请求变成一个画面。",
        "persuade": "主张页的注意力属于那句话，配图会把不可回答的问题装饰掉。",
        "prove": "这一页的说服力来自可核验的量，图像的证明力低于数字本身。",
        "establish": "内容里没有可指认的人/现场：用排版与字阶建立世界，比塞一张图更诚实。",
    }
    return {"decision": "none", "source": "judgment",
            "function": None,
            "necessity": reasons.get(role, "说不出没有它这一页会下降在哪里——那就是装饰。")}


# ─────────────────────────────────────────────────────────────────────
# 10 · 生产规格（Production Spec：元素职责与阈值，不含坐标）
# ─────────────────────────────────────────────────────────────────────
def production_spec(focus: dict, comp: dict, media: dict, u: dict,
                    weight: dict | None = None) -> dict:
    """生产规格：必落元素 + 明确不做 + 密度目标（无坐标）。

    信息权重的删除清单在这里变成明确禁令——权重不是注释，它直接决定
    这一页不许出现什么。
    """
    # must_place 只留 role/type：理由分别住 focus.why / media.necessity / claim 规则，
    # 不在生产规格里再存一份（零消费者 + 与上游重复）。
    must = [{"role": focus["element_role"], "type": focus["type"]}]
    if focus["type"] != "text" or focus["element_role"] not in ("statement_text", "headline"):
        # 数字/比较虽也可以用文字排版，但它不是结论句；主张不能因类型=文本
        # 就被省略。真正以主张为焦点的页才不用二次重复落结论。
        must.append({"role": "claim_text", "type": "text"})
    if u.get("numerals"):
        must.append({"role": "source", "type": "text"})
    if media["decision"] in ("required", "reuse"):
        must.append({"role": "image", "type": "image"})
    if u.get("human") and media["decision"] == "none":
        must.append({"role": "witness_line", "type": "text"})
    # must_not 只收真正独立的硬约束（信息权重的删除清单）：focus/comp 的
    # rejected 是 Intelligence 的竞争证据，canonical owner 是它们自己——
    # 生产规格只引用结论（删什么），不复制「为什么不是别的」。
    must_not = [f"删：{doomed}" for doomed in ((weight or {}).get("delete") or [])[:2]]
    return {
        "must_place": must,
        "must_not": must_not,
        "density_target": {"big_whitespace": "sparse", "editorial": "balanced",
                           "data_field": "dense", "image_narrative": "sparse",
                           "linear_structure": "balanced",
                           "asymmetric_tension": "balanced"}.get(comp.get("chosen"),
                                                                "balanced"),
    }


# ─────────────────────────────────────────────────────────────────────
# 11 · 视觉世界（由内容推导，不查风格预设表）
# ─────────────────────────────────────────────────────────────────────
def register_of(text: str) -> str:
    for name in ("document", "stage", "working"):
        if _hit(text, _REGISTER_WORDS[name]):
            return name
    return "document"


# 纸：**推导**，不是色表。语域给中性底（三个锚点），内容实体的强调色按语域
# 的克制程度掺进纸里——同一副 deck 的纸因此跟着它的实体走，而不是跟着风格名走。
# 深色只在「光本身是材料」的语域里成立（stage + 实体/场景声明），这不是风格开关。
_PAPER_ANCHOR = {"document": "#F7F5F0", "working": "#FCFCFC", "stage": "#F3F2EF"}
_PAPER_TINT = {"document": 0.04, "working": 0.03, "stage": 0.05}
_DARK_PAPER_ANCHOR = "#0A0A0C"
_DARK_PAPER_TINT = 0.04

_ACCENT = {"paper_ink": ("#9C3B26", "印泥/朱砂：一句话被盖了章"),
           "stone_architecture": ("#8A6A4F", "氧化铜/土：材料自己的颜色"),
           "metal_glass": ("#2E6BD6", "信号蓝：技术世界里唯一的电流"),
           "botanical": ("#5F7A55", "苔绿：生长一侧的颜色"),
           "water_sky": ("#2F6E78", "深青：冷而深的水色"),
           "textile_domestic": ("#A2563F", "陶土：被手触摸过的颜色"),
           "stage_screen": ("#3B6FE0", "舞台信号蓝：黑暗里的一束光"),
    "ceramic_craft": ("#4F6E6A", "窑青/铜绿：釉自己的颜色")}
_NEUTRAL_ACCENT = ("#6E6A63", "中性矿物灰：没有主题实体时最克制的一支（不与任何实体世界撞色）")
_TYPE_VOICE = {"document": ("austerity with human warmth：窄栏、大字阶、克制的粗体",
                            "serif"), "stage": ("aperture：大尺度、强对比、极少的字",
                                                "sans"),
               "working": ("clarity：信息优先，字体是最安静的工具", "sans")}
_FONTS = {"serif": {"cn": "Source Han Serif SC", "latin": "Georgia"},
          "sans": {"cn": "Source Han Sans SC", "latin": "Arial"}}


def derive_world(brief: dict, understanding: list) -> dict:
    """从内容实质推导视觉世界：受众语域 + 主题实体 + 证据形态 + 张力。

    没有「风格预设表」可查：同样的「融资路演」在实体、证据、受众不同时
    会得到不同的纸、墨、强调语义与构图纪律——**相同内容类型不默认相同视觉结果**。
    """
    audience = str(brief.get("audience") or "")
    decision = str(brief.get("decision") or "")
    tension = str(brief.get("tension") or "")
    occasion = " ".join(str(brief.get(k) or "") for k in ("occasion", "subject", "visual_world"))
    register = register_of(audience + " " + occasion + " " + decision)
    if register == "document" and _hit(audience + occasion, _REGISTER_WORDS["stage"]):
        register = "stage"

    hits: dict[str, int] = {}
    for u in understanding:
        for s in u.get("subjects") or []:
            hits[s] = hits.get(s, 0) + 1
    # Deck 级世界需要 deck 级证据：单页单个词不足以决定整套的材质与光
    # （一页提「发布」，整套就变舞台——那是误判）。单页 deck 除外。
    top = max(hits, key=lambda k: (hits[k], k)) if hits else None
    subject = top if (top and (hits[top] >= 2 or len(understanding) <= 1)) else None
    human_share = sum(1 for u in understanding if u.get("human")) / max(len(understanding), 1)
    number_share = sum(1 for u in understanding
                       if u.get("evidence") in ("series", "number", "comparison", "part_whole")) / max(len(understanding), 1)

    declared = str(brief.get("visual_world") or "").strip()
    if declared and declared.lower() not in ("unknown", "none"):
        visual_world = declared
        world_source = "declared"
    elif subject:
        visual_world = _MATERIAL_LEXICON[subject]["material"]
        world_source = f"subject:{subject}"
    else:
        visual_world = "neutral matte ground, one light source, nothing decorative"
        world_source = "neutral_fallback"

    # 纸由语域锚点 + 实体强调色推导（不是色表）；张力不改变纸，它改变强调色的语义。
    accent, accent_note = _ACCENT.get(subject or "", _NEUTRAL_ACCENT)
    dark = register == "stage" and (subject in (None, "metal_glass", "stage_screen", "water_sky")
                                    or str(brief.get("background_scene") or "").lower()
                                    in ("dark", "dark_luminous", "cinematic"))
    from primitives import blend
    if dark:
        paper = blend(_DARK_PAPER_ANCHOR, accent, _DARK_PAPER_TINT)
    else:
        paper = blend(_PAPER_ANCHOR[register], accent, _PAPER_TINT[register])
    ink = "#EFEFEC" if dark else ("#12120F" if register == "document" else "#1A1A1A")
    if brief.get("brand_colors"):
        accent_note = "品牌色覆盖：强调色的语义由 deck 决定，色相由品牌决定"
    accent_role = ("指向被批准的那一件事" if _hit(decision, ("批准", "决定", "确认", "approve"))
                   else "标记风险本身" if _hit(tension, ("风险", "疑虑", "担心", "不足"))
                   else "标记当前值/现状")
    if understanding:
        # 整套的证据性格取最常见的非空证据（出现次数压过一切；打平按形态序）：
        # 「没有证据」不能盖过真实存在的证据形态。
        freq: dict[str, int] = {}
        for u in understanding:
            mode = u.get("evidence") or "none"
            if mode != "none":
                freq[mode] = freq.get(mode, 0) + 1
        evidence_top = max(freq, key=lambda m: (freq[m], -EVIDENCE_MODES.index(m))) if freq else "none"
    else:
        evidence_top = "none"
    chart_style = {"comparison": "shared baseline, two-tone delta, direct labels",
                   "series": "hairline axis, one highlighted point, direct labels",
                   "number": "single large figure with an explicit baseline",
                   "structure": "layer map with hairline connectors",
                   "sequence": "single axis, spacing carries rhythm",
                   "proposition": "no chart: type carries the page"}.get(evidence_top,
                                                                          "hairline + direct label")
    light = (_MATERIAL_LEXICON[subject]["light"] if subject
             else "even diffuse daylight, no visible source")
    texture_keys = list(_MATERIAL_LEXICON[subject]["textures"]) if subject else ["paper"]
    fonts = _FONTS[_TYPE_VOICE[register][1]]
    voice, _ = _TYPE_VOICE[register]
    grammar = ("soft_asymmetry" if human_share > 0.4 or number_share < 0.3
               else "evidence_field" if number_share > 0.6 else "strict_grid")
    return {
        "name": f"{register}/{subject or 'neutral'}",
        "source": world_source,
        "visual_world": visual_world,
        "light": light,
        "texture_keys": texture_keys,
        "chart_style": chart_style,
        "composition_grammar": grammar,
        "type_voice": voice,
        "fonts": fonts,
        "paper": paper,
        "ink": ink,
        "accent": accent,
        "accent_role": accent_role,
        "accent_why": accent_note,
        "reasons": {
            "register": f"受众与场合语域＝{register}（决定纸、字与克制程度）",
            "subject": (f"内容里的主题实体＝{subject}（决定材质、光与强调色相）"
                        if subject else "内容里没有可指认的主题实体：退到中性纸世界，不猜风格"),
            "regime": f"{'深色舞台：' if dark else '浅色纸面：'}"
                      f"{'发布会/产品语域下光本身是材料' if dark else '文档语域下纸面托住信息'}",
            "accent_role": f"强调色语义＝{accent_role}（颜色服从语义，不服从风格）",
            "composition": f"世界级构图纪律＝{grammar}（由人的存在与数字密度推开，不是预设）",
            "type_voice": voice,
        },
    }


# ─────────────────────────────────────────────────────────────────────
# 12 · 逐页判断（judgment = 一次算完的完整判断卡）
# ─────────────────────────────────────────────────────────────────────
_PAGE_DECLARATIONS = ("audience", "decision", "tension", "density", "energy",
                      "asset", "asset_role", "asset_function", "asset_subject",
                      "medium", "material", "lighting", "texture",
                      "asset_color", "safe_area", "text_color", "negative_space_anchor",
                      "asset_ratio", "asset_allow_crop", "asset_source", "composition",
                      "insight", "focus",
                      # 页级底色参与资产 QC 亮度参照：声明必须透传到清单（CASE_004）。
                      "background", "eyebrow")


def _intent_value(value) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


# 眉标（跨页锚）：此前直接把视觉角色的英文枚举大写贴上去（PROVE / COMPARE…），
# 12 页里 7 页同为 PROVE —— 它是内部枚举，不是给观众看的内容，机械重复还会
# 把整套读成模板。眉标该说的是「现在走到论证的哪一段」，所以由本页结论派生；
# 作者可在 brief 里逐页声明 `eyebrow` 压过推导。
_ROLE_LABEL_CN = {"establish": "建立", "explain": "解释", "compare": "对比",
                  "prove": "证明", "persuade": "说服", "summarize": "收束"}
_LABEL_HEAD_PREFIX = ("我们", "本页", "这一页", "首先", "其次", "同时", "另外",
                      "因此", "所以", "但是", "请", "建议", "也就是说", "换句话说",
                      "同期", "本期", "目前", "当前", "今年", "未来")
# 眉标在**谓语/虚词之前**收口：主语短语才是「这一段在论证里的位置」。
_LABEL_BOUNDARY = ("是", "在", "与", "和", "或", "由", "从", "对", "把", "被", "并",
                   "为", "到", "至", "使", "让", "的", "，", "。", "、", "；", "：",
                   "！", "？", "只", "才", "更", "最", "也", "都", "还", "就", "而",
                   "却", "但", "已", "将", "会", "能", "要", "有", "按", "靠", "用",
                   # 副词也是切段边界：「同店销售额仍在增长」的名词短语在「仍」处
                   # 结束，收到「仍在增长」会把眉标读成半句话。
                   "仍", "再", "又", "仅", "正", "且",
                   "之", "占", "达", "超", "低于", "高于", "无法", "不能", "不是",
                   "不再", "尚未", "来自", "关键")
# 收尾的虚词/单位：以它们结尾的段是被截断的从句。注意「度」不在其中——
# 速度/密度/成熟度是完整名词，收掉它会让「开店速度」永远派不出来。
# 主张自己在讲「差」的词：这时页面的图形对象是差本身，不是两条曲线。
_GAP_WORDS = ("差距", "差值", "差额", "价差", "落差", "收敛", "收窄", "拉大", "缩小", "差额率")

_LABEL_TAIL = "的里中上下内外前后了过等及"
_NON_CJK = re.compile(r"[^一-鿿]")
# 段首的「名词 + 数字 + 单位」说明语：「中国 800 元以上」「本轮 1.8 亿元里」
_NUM_MODIFIER = re.compile(r"^[^0-9A-Za-z]{0,6}[0-9][0-9.,]*\s*[一-鿿]{0,3}")
# 切段边界（长词优先），在此处断开而不是在断口前截断
_BOUNDARY_SPLIT = re.compile("|".join(
    re.escape(w) for w in sorted(_LABEL_BOUNDARY, key=len, reverse=True)))
# 领头的动词/介词/数词：以它们开头的段是谓语或数量说明，不是眉标要的名词短语
_LABEL_HEAD_STOP = set("把被将使让在为到按靠用向给与和或并且也还就而却但已会能要"
                       "有只才更最都半多少整全各每本该此其做至升降增减投买卖产销"
                       "提开完实进转扩缩换不从由")
# 收尾的动词/连词/量词：以它们结尾的段是半句话或一个数量短语，不是可定位的名词
_LABEL_TAIL_STOP = set("做在为有成给使让占到把被与和或并且而则及升降增减投买卖产"
                       "销是年月日周季天时分秒个片条块件层倍成回次遍"
                       # 否定/未完副词收尾 = 被截断的从句，不是名词短语：
                       # 「答案不在开店速度」曾派生出眉标「答案不」，
                       # 「同店销售额仍在增长」曾派生出「同店销售额仍」。
                       "不没无未仍还也都又再更才就只仅正已将且")


def section_label(item: dict, claim: dict, role: str) -> str:
    """眉标：本页结论的**主题短语**（3–6 字），派不出来才退回中文角色词。

    取法：先剥语气/时间前缀，再在第一个虚词或谓语之前收口（「三个市场｜里只有…」
    → 三个市场）；收口太短就顺延到下一个边界，太长就退回角色词——宁可退回，
    也不输出半截词（此前的截断做法产出过「三个市场里只有印」）。
    """
    declared = str((item or {}).get("eyebrow") or "").strip()
    if declared:
        return declared[:16]
    text = str((claim or {}).get("text") or (item or {}).get("title") or "").strip()
    for prefix in _LABEL_HEAD_PREFIX:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    head = re.split(r"[，。；：！？\n]", text, maxsplit=1)[0].strip()
    fallback = _ROLE_LABEL_CN.get(str(role), str(role))
    if not head:
        return fallback

    def _label_of(seg: str) -> str:
        """按虚词/谓语切段，取**第一个干净的名词短语**作眉标（2–6 字，优取 3–6）。

        旧做法先删数字、再按「第一个边界之前」截断：等于把数字两侧的汉字缝在一起
        （「中国 800 元以上」→「中国元以」），或收下一截动词短语（「会员做」）。
        眉标是页眉上的定位词，缝出来的词比退回角色词更糟——它看着像有信息，
        实际是噪声。切段 + 首尾虚词/动词剔除，宁可退回角色词。
        """
        for part in _BOUNDARY_SPLIT.split(seg):
            q = part.strip()
            core = re.sub(r"[^一-鿿]", "", q)
            # 数字/拉丁夹在汉字之间（「中国 800 元以上」）说明这段不是连续名词，
            # 硬删会把数字两侧的字缝成一个不存在的词；只在边缘的（「东南亚市场1」）
            # 是编号，去掉边缘编号仍是同一个名词。
            if not core or core not in q:
                continue
            p = core.strip(_LABEL_TAIL)
            if not (2 <= len(p) <= 6):
                continue
            if p[0] in _LABEL_HEAD_STOP or p[-1] in _LABEL_TAIL_STOP:
                continue                       # 动词/量词领头或收尾的不是名词短语
            return p                           # 主语在前：取第一个干净的段
        return ""

    label = _label_of(head)
    if label:
        return label
    # 段首是「名词 + 数字 + 单位」的说明语（「中国 800 元以上…」）：剥掉它再收一次，
    # 真正的主语常常在数量词之后。
    stripped = _NUM_MODIFIER.sub("", head, count=1).strip()
    if stripped and stripped != head:
        label = _label_of(stripped)
        if label:
            return label
    return fallback


def _apply_declared_spot(focus: dict, comp: dict, declared) -> tuple[dict, dict]:
    """作者声明的第一落点/构图意图原样生效（初判与跨页重算共用同一处）。"""
    declared = declared if isinstance(declared, dict) else {}
    spot = str(declared.get("focus") or "").strip()
    if spot:
        focus = {**focus, "element_role": spot, "source": "author",
                 "why": "作者声明第一落点；规划保留其余判断作为对照"}
    want = str(declared.get("composition") or "").strip()
    if want:
        comp = {**comp, "chosen": want, "source": "author",
                "why": "作者声明构图意图（原样生效）",
                "rejected": [r for r in comp.get("rejected") or [] if r.get("option") != want]}
    return focus, comp


_CLAUSE_MARK = re.compile(r"[。；;，,！!？?→]")
_DATE_TOKEN = re.compile(r"(?:19|20)\d{2}|\bQ[1-4]\b|\d{4}[.\-/年]\d")


def _is_meta_line(content: str, index: int) -> bool:
    """首页的一行是文档元信息（部门 · 日期 · 活动名），而不是这一页的论证。

    判据是**文档元信息的形状**：有分隔符（· | @）、有日期/季度、或有凭证词
    （提案、部门、汇报人）；并且没有子句或箭头。只靠「短」不够：首页也可能是一句
    证词（「华东 6 家门店走访记录」），那不是元信息。
    """
    text = content.strip()
    if index != 0 or not 0 < len(text) <= 30 or _CLAUSE_MARK.search(text):
        return False
    return bool(_META_LINE.search(text) or _DATE_TOKEN.search(text)
                or _hit(text, _CREDENTIAL_WORDS))


def judgment_view(item: dict, index: int) -> dict:
    """判断视图：首页的文档元信息行不参与角色、证据、结论与图像判定。

    例如「2026 Q4 发布流程评审」若参与判断，会把封面判成流程页。它照常渲染；
    凭证词检测仍读原文。非元信息的内容原样保留。
    """
    if _is_meta_line(str(item.get("content") or ""), index):
        return {**item, "content": ""}
    return item


_DECLARABLE_ROLES = ("establish", "explain", "compare", "prove", "persuade", "summarize")


def _declared_intent(item: dict, warnings: list) -> tuple[str, str]:
    """作者可在页面上声明 role / evidence：合法值原样生效，非法值 warning 后忽略。"""
    role = str(item.get("role") or "").strip().lower()
    evidence = str(item.get("evidence") or "").strip().lower()
    if role and role not in _DECLARABLE_ROLES:
        warnings.append({"rule": "declared_role_invalid", "scope": item.get("id"), "input": role,
                         "msg": f"role 只能是 {'/'.join(_DECLARABLE_ROLES)}；已忽略，按内容判断"})
        role = ""
    if evidence and evidence not in EVIDENCE_MODES:
        warnings.append({"rule": "declared_evidence_invalid", "scope": item.get("id"),
                         "input": evidence,
                         "msg": f"evidence 只能是 {'/'.join(EVIDENCE_MODES)}；已忽略，按内容判断"})
        evidence = ""
    return role, evidence


def page_judgment(item: dict, *, index: int, total: int, brief: dict, world: dict,
                  warnings: list, u: dict | None = None) -> dict:
    """逐页判断：受众/决定/主张/阻力/权重/角色/焦点/空间/构图/排版/媒体/生产。

    执行依赖允许媒体必要性先于焦点、构图先于由它推导的空间；节奏在整套回看时
    添加。`u` 由 think 一次算好传进来（整页只理解一次）；直接调用时当场算。
    """
    title = str(item.get("title") or "").strip()
    raw_content = str(item.get("content") or "").strip()
    view = judgment_view(item, index)
    content = str(view.get("content") or "").strip()
    text = f"{title} {content}".strip()
    if u is None:
        u = understand(text, has_chart=bool(item.get("chart")), content=content)
    claim = extract_claim(view, positional=index in (0, total - 1))
    # 封面与致谢/问答页的职责是立住或回收整套主张，不承载新结论：没有数字证据、
    # 带凭证语（提案/谢谢/汇报人…）的首末页，不追问「先写一句结论」。
    credential_frame = (index in (0, total - 1) and not int(u.get("distinct_numerals") or 0)
                        and _hit(f"{title} {raw_content}", _CREDENTIAL_WORDS))
    if credential_frame and claim["source"] == "absent":
        # 「不承载结论」是这一页的设计身份，不是缺口：来源标为 frame，骨架如实表达。
        claim = {"text": None, "source": "frame",
                 "why": "凭证型首末页（封面 / 致谢 / 问答）：职责是立住或回收整套主张，不承载新结论，不补句。"}
    if claim["source"] == "absent":
        warnings.append({"rule": "unresolved_content", "scope": item.get("id"),
                         "msg": "这一页没有可复述的结论（content 缺失）："
                                "标题不是证据，不得脑补数据/案例——补真实内容，"
                                "或把它降级为章节页，或删掉"})
    audience = str(item.get("audience") or brief.get("audience") or "").strip()
    decision = str(item.get("decision") or brief.get("decision") or "").strip()
    page_tension = str(item.get("tension") or brief.get("tension") or "").strip()
    declared_role, declared_ev = _declared_intent(item, warnings)
    if declared_ev:
        u = {**u, "evidence": declared_ev, "evidence_source": "author"}
    role = visual_role(u, index=index, total=total,
                       tension=page_tension, claim=claim)
    role.setdefault("source", "judgment")
    if declared_role:
        role = {"role": declared_role, "source": "author", "alternatives": [],
                "why": "作者声明页面角色（原样生效）；内容判断保留为对照。"}
    tension = tension_of(item, brief, role["role"])
    media = media_necessity(u, role["role"],
                            declared=str(item.get("asset") or "").lower() or None,
                            has_chart=bool(item.get("chart")))
    claim_text = str(claim.get("text") or "")
    # 主张自己带数字时，也要把它当**主张**来锚定（把 claim 传给 number_roles）：
    # 只按「终值信号」扫一遍，会把决策页的「扩到 3 个」当成主语，而真正要批的
    #「30 家」被降成支撑——主张点名的量必须赢过任何后出现的终值。
    anchor = number_roles(claim_text, claim_text or None)
    if not anchor[0] and role["role"] in ("prove", "compare") \
            and u.get("evidence") in ("number", "series", "comparison", "part_whole"):
        # 结论在标题、结果值在证据中：主张照样锚定「哪一个量」是本页主语
        anchor = number_roles(content, claim_text or None)
    focus = focus_of(role["role"], u, claim, media, number_anchor=anchor,
                     page_text=content)
    comp = composition_of(role["role"], u,
                          composition_grammar=world.get("composition_grammar", ""),
                          media=media, claim=claim, content_len=len(text))
    focus, comp = _apply_declared_spot(focus, comp, item)
    spatial = spatial_of(comp, u)
    weight = information_weight(u, claim, text, number_anchor=anchor)
    typography = typography_of(claim, weight, focus, role["role"], u,
                                text_len=len(text), number_anchor=anchor)
    prod = production_spec(focus, comp, media, u, weight)
    open_q = []
    if claim["source"] == "absent":
        open_q.append("本页结论：先写出一句可复述的话（或删掉这一页）")
    if media["source"] == "judgment" and media["decision"] == "required":
        open_q.append("图像主题由作者确认：画面里究竟出现什么（人物/场所/物件）")
    if media["source"] == "hint":
        open_q.append("图像：内容提到人物或场所，但未声明是否配图；需要时声明 asset: required")
    if u.get("evidence") == "comparison" and not u.get("same_unit", True) \
            and claim_units_conflict(claim_text):
        open_q.append("比较量的单位不同：先统一口径，或在同屏解释两端不可直接相减。")
    elif (u.get("evidence") == "comparison" and
          any(n.get("unit") in ("%", "％") for n in u.get("numerals") or [])):
        open_q.append("比较比例前核对分母/样本与期间；不同指标的百分比不能直接相减。")
    return {"audience": audience or None, "decision": decision or None,
            "claim": claim, "tension": tension, "information_weight": weight,
            "visual_role": role, "focus": focus, "composition": comp, "spatial": spatial,
            "typography": typography, "media": media, "production": prod,
            "understanding": u, "open_questions": open_q or None}


def _coherence_pass(pages: list) -> dict:
    """记录内容已经造成的节奏；连续同构图不是改写页级判断的证据。"""
    notes: list[str] = []
    i = 0
    while i < len(pages) and len(notes) < 3:
        j = i
        while (j < len(pages) and pages[j]["judgment"]["focus"].get("element_role")
               == pages[i]["judgment"]["focus"].get("element_role")):
            j += 1
        if j - i >= 4:
            notes.append(f"{pages[i]['id']}–{pages[j - 1]['id']} 焦点连续落在 "
                         f"{pages[i]['judgment']['focus'].get('element_role')}："
                         "确认每页真的需要同一落点，否则合并页面或改写结论")
        i = j
    media_seq = [f"{p['judgment']['media'].get('decision')}"
                 f":{p['judgment']['media'].get('function') or '-'}"
                 for p in pages]
    # 同一次整套回看，给作者一条跨页呼吸说明；只标注内容已造成的变化，
    # 不为看起来不一样而强制改构图，也不单独另跑一轮『节奏 AI』。
    for index, page in enumerate(pages):
        current = page["judgment"]
        previous = pages[index - 1]["judgment"] if index else None
        if previous is None:
            move, why = "open", "建立整套主张：先让观众知道要判断什么。"
        elif index == len(pages) - 1:
            move, why = "close", "回收开场的决定，不用新装饰或谢谢页稀释请求。"
        elif current["production"]["density_target"] != previous["production"]["density_target"]:
            move, why = ("breathe", "信息密度变化来自证据体量；用疏密给前一页让出阅读时间。")
        elif current["media"]["decision"] != previous["media"]["decision"]:
            move, why = ("turn", "内容决定图像是否在场；视觉重心随证据载体切换。")
        elif current["composition"]["chosen"] == previous["composition"]["chosen"]:
            move, why = ("hold", "内容需要相同的表达逻辑；保持关系可比，不凭空换版式。")
        else:
            move, why = ("turn", "主张或证据形态变化，阅读路径跟着内容转向。")
        current["rhythm"] = {"move": move, "previous": pages[index - 1]["id"] if index else None,
                             "why": why}
    return {"compositions": [p["judgment"]["composition"]["chosen"] for p in pages],
            "densities": [p["judgment"]["production"]["density_target"] for p in pages],
            "roles": [p["judgment"]["visual_role"]["role"] for p in pages],
            "media": media_seq,
            "adjustments": None,
            "notes": notes or None}


# ─────────────────────────────────────────────────────────────────────
ADVANCED_TRIGGERS = ("发布会", "品牌", "年报", "旗舰", "形象", "高端", "launch", "brand",
                     "keynote", "manifesto", "premium", "campaign")
QUALITY_ALIASES = {"fast": "fast", "quick": "fast", "standard": "fast",
                   "advanced": "advanced", "premium": "advanced", "keynote": "advanced",
                   "benchmark": "advanced"}


def think(brief: dict) -> dict:
    """唯一规划入口：一次计算，产出判断面（含理由）与单份页事实。确定性、零写入。"""
    brief = brief if isinstance(brief, dict) else {}
    warnings: list[dict] = []
    audience = str(brief.get("audience") or "").strip()
    decision = str(brief.get("decision") or "").strip()
    tension = str(brief.get("tension") or "").strip()
    if not audience or not decision or not tension:
        missing = "/".join(name for name, val in
                           (("audience", audience), ("decision", decision),
                            ("tension", tension)) if not val)
        parts = []
        if not audience or not decision:
            parts.append("先回答「谁看 + 看完要做什么决定」，其余判断都从这两个答案推出")
        if not tension:
            parts.append("tension 缺失：说服页会失去「直面观众疑虑」的对象")
        warnings.append({"rule": "deck_contract", "scope": "deck",
                         "msg": "brief 缺 " + missing + "：" + "；".join(parts)})

    occasion = f"{brief.get('occasion','')} {brief.get('subject','')} {brief.get('brief','')}"
    quality_input = brief.get("quality_level")
    quality = QUALITY_ALIASES.get(str(quality_input or "").strip().lower()) if quality_input else (
        "advanced" if any(k in occasion.lower() or k in occasion for k in ADVANCED_TRIGGERS)
        else "fast")
    if quality_input and str(quality_input).strip().lower() not in QUALITY_ALIASES:
        warnings.append({"input": quality_input, "canonical": quality,
                         "rule": "quality_fallback"})

    raw = brief.get("slides")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise TypeError("brief.slides must be a list of page briefs")
    items = [it if isinstance(it, dict) else {"title": str(it)} for it in raw]

    views = [judgment_view(it, i) for i, it in enumerate(items)]
    understanding = [understand(f"{v.get('title') or ''} {v.get('content') or ''}".strip(),
                               has_chart=bool(v.get("chart")), content=str(v.get("content") or ""))
                     for v in views]
    world = derive_world(brief, understanding)
    if str(brief.get("design_direction") or "").strip():
        warnings.append({"rule": "direction_retired", "scope": "deck",
                         "input": str(brief["design_direction"]),
                         "msg": "design_direction 已退役：视觉世界由内容推导（受众语域 + "
                                "主题实体 + 证据形态）。要固定世界就写 visual_world，"
                                "要固定品牌就写 brand_colors"})

    pages = []
    texts: dict[str, str] = {}
    for i, it in enumerate(items):
        sid = str(it.get("id") or f"s{i + 1:02d}")
        declared = {k: it[k] for k in _PAGE_DECLARATIONS if _intent_value(it.get(k))}
        if "asset_subject" in declared and str(declared.get("asset") or "").lower() not in (
                "required", "reuse", "none"):
            # 写了画面主题就是要出图（等价 required；显式 none 除外）：注入判断输入，
            # 不只留在回显里——否则「写了主题却不出图」，声明等于没写。
            declared["asset"] = "required"
        texts[sid] = f"{it.get('title') or ''} {it.get('content') or ''}".strip()
        judgment = page_judgment({**views[i], "id": sid,
                                  "asset": declared.get("asset", it.get("asset"))},
                                 index=i, total=len(items), brief=brief,
                                 world=world, warnings=warnings, u=understanding[i])
        anchor = None
        if len(items) >= 4:
            anchor = {"eyebrow": section_label(
                it, judgment["claim"], judgment["visual_role"]["role"])}
            if i > 0:
                anchor["page_number"] = i + 1
        pages.append({"id": sid,
                      # BUILD 不能只看到前 88/120 字后再猜剩余证据；原文只保留一份。
                      "ref": texts[sid],
                      "judgment": judgment,
                      "anchor": anchor,
                      "declarations": declared or None})

    # 图像清单只收作者声明的出图：词表命中只产生 hint，不自动占图位，因此没有额度需要分配。
    coherence = _coherence_pass(pages)
    return {
        "deck": {
            "audience": audience or None,
            "decision": decision or None,
            "tension": tension or None,
            "quality": quality,
            "world": world,
            "theme": _theme_seed(world, brief.get("brand_colors")),
            "coherence": coherence,
        },
        "pages": pages,
        "assets_hint": {
            "generate": [p["id"] for p in pages
                         if p["judgment"]["media"]["decision"] in ("required", "reuse")
                         and p["judgment"]["media"]["source"] == "author"]},
        "warnings": warnings,
    }


def _muted_of(world: dict) -> str:
    """支持色：由纸与墨推导的一支中性（不是预设槽）。"""
    paper, ink = world.get("paper"), world.get("ink")
    try:
        from primitives import blend, is_light
        return blend(ink, paper, 0.58) if is_light(paper) else blend(ink, paper, 0.45)
    except Exception:
        return "#8A8A86"


# 品牌色槽位别名：品牌永远压过推导（唯一入口 normalize_brand_colors）
_BRAND_SLOT_ALIAS = {"ink": "information", "primary": "information",
                     "information": "information", "text": "information",
                     "secondary": "supporting", "muted": "supporting",
                     "supporting": "supporting", "accent": "accent",
                     "background": "foundation", "paper": "foundation",
                     "foundation": "foundation"}


def normalize_brand_colors(brand) -> dict:
    """brand_colors 唯一归一：{slot:#HEX} 或 [#主,#强调,#辅] → {slot:#HEX}。"""
    if isinstance(brand, dict):
        items = [(k, v) for k, v in brand.items()]
    elif isinstance(brand, (list, tuple)):
        items = list(zip(("primary", "accent", "secondary"), brand))
    else:
        return {}
    out = {}
    for k, v in items:
        if isinstance(v, str) and v.strip().startswith("#") and len(v.strip()) in (4, 7):
            slot = _BRAND_SLOT_ALIAS.get(str(k).strip().lower())
            if slot and slot not in out:
                out[slot] = v.strip()
    return out


def _theme_seed(world: dict, brand) -> dict:
    """世界推导 → 四槽种子；品牌色一到立即让位（一步，无第二管线）。"""
    seed = {"foundation": world["paper"], "information": world["ink"],
            "supporting": _muted_of(world), "accent": world["accent"]}
    over = normalize_brand_colors(brand)
    if over:
        seed.update(over)
    return {"colors_seed": seed,
            "seed_source": "brand_colors" if over else "world_derivation",
            "slots_overridden": sorted(over) or None}


# ─────────────────────────────────────────────────────────────────────
# 15 · 主题 token（世界 → theme.colors；可读性兜底在这里一次做掉）
# ─────────────────────────────────────────────────────────────────────
def theme_tokens(seed: dict) -> dict:
    """世界种子 → spec.theme.colors 六 token；起点保证可读（墨色与纸面分得开）。"""
    colors = {"background": seed.get("foundation", "#FFFFFF"),
              "ink": seed.get("information", "#111111"),
              "muted": seed.get("supporting", "#777777"),
              "primary": seed.get("information", "#222222"),
              "secondary": seed.get("supporting", "#333333"),
              "accent": seed.get("accent", "#AA0000")}
    try:
        from primitives import blend, contrast, is_light

        def _blend_toward(color, target, t=0.55):
            try:
                return blend(color, target, t)
            except Exception:
                return target
        if contrast(colors["background"], colors["ink"]) < 4.5:
            readable = "#141414" if is_light(colors["background"]) else "#FFFFFF"
            colors["ink"] = readable
            if contrast(colors["background"], colors["primary"]) < 4.5:
                colors["primary"] = readable
            if contrast(colors["background"], colors["secondary"]) < 3.0:
                colors["secondary"] = _blend_toward(colors["secondary"], readable)
            if contrast(colors["background"], colors["muted"]) < 3.0:
                colors["muted"] = _blend_toward(colors["muted"], readable)
    except Exception:
        pass
    return colors


# ─────────────────────────────────────────────────────────────────────
# 16 · 骨架（plan → build.py：判断卡 + 落笔清单；不给坐标）
# ─────────────────────────────────────────────────────────────────────
def _fmt_items(items, limit=3) -> str:
    if not items:
        return "—"
    out = [str(x) for x in items[:limit]]
    return " / ".join(out) + ("…" if len(items) > limit else "")


def _weight_brief(items, limit=2) -> str:
    """骨架只抄选择；理由的唯一真源是 plan.json 的权重判断卡。"""
    return _fmt_items([_weight_label(item) for item in (items or [])], limit)


def build_skeleton(bundle: dict) -> str:
    """plan bundle → 构图作业稿：简短行动摘要；完整竞争理由只住 plan.json。

    内容原文不截断；几何、字号与媒介落点仍由作者决定，不出模板坐标。
    """
    deck = bundle.get("deck") or {}
    pages = bundle.get("pages") or []
    world = deck.get("world") or {}
    colors = theme_tokens((deck.get("theme") or {}).get("colors_seed") or {})
    fonts = world.get("fonts") or {"cn": "Source Han Sans SC", "latin": "Arial"}
    coherence = deck.get("coherence") or {}

    facts = [f"受众: {deck.get('audience') or '未声明'} · 决策: {deck.get('decision') or '未声明'}"
             + (f" · 张力: {deck['tension']}" if deck.get("tension") else "")]
    facts.append(f"视觉世界（由内容推导 · {world.get('source')}）: {world.get('visual_world')}")
    facts.append(f"  纸/墨: {world.get('paper')} / {world.get('ink')} · "
                 f"强调: {world.get('accent')} = {world.get('accent_role')}")
    facts.append(f"  光: {world.get('light')} · 图表性格: {world.get('chart_style')}")
    facts.append(f"  排版声音: {world.get('type_voice')} · 字体: {world.get('fonts')}")
    reasons = world.get("reasons") or {}
    if reasons:
        facts.append("  为什么: " + "；".join(f"{k}→{v}" for k, v in list(reasons.items())[:3]))
    seq = coherence.get("compositions") or []
    if seq:
        facts.append("整套节奏: " + " → ".join(map(str, seq)))
    for adj in (coherence.get("adjustments") or [])[:4]:
        facts.append(f"跨页校准: {adj.get('page')} {adj.get('field')} "
                     f"{adj.get('from')}→{adj.get('to')}（{adj.get('why')}）")
    for note in (coherence.get("notes") or [])[:2]:
        facts.append(f"跨页提醒: {note}")

    L = ['# -*- coding: utf-8 -*-',
         'plan → build：逐页判断只在 plan.json 有一份完整记录，几何由作者决定。',
         '',
         '作业顺序：受众/决定 → 结论/阻力 → 权重 → 焦点/空间/构图 → 字体/媒体/节奏。',
         '完整竞争理由在 plan.json；此处只带着原文与为什么这样落笔的短备忘。',
         '内容必须真实出现，不因骨架省略证据；能删就不加，不能用小字掩盖过载。',
         f'排版纪律（逐页默认，页内不再重复）: {BASE_DISCIPLINE}',
         '留白：每处空白说得出保护什么；说不出的是事故。行长建议为非实测容量。',
         '跨页锚（anchor：眉标 / 页码，≥4 页时由 plan 发）：落成 role=eyebrow / role=page_number 的元素，位置全稿一致。',
         '字段契约 → references/contract.md（一次）；判断有真实缺口才回看 SKILL.md §2–3。',
         f'质量档: {deck.get("quality")} · 页数: {len(pages)}']
    L += [f'  {line}' for line in facts]
    has_media = any((p.get("judgment") or {}).get("media", {}).get("decision")
                    in ("required", "reuse") for p in pages)
    if has_media:
        manifest_path = (bundle.get("workflow") or {}).get("assets_manifest_path")
        manifest = manifest_path or "asset_manifest.json"
        status = (f'同次 plan 已准备清单 {manifest}' if manifest_path else
                  '只有 think 判断卡、尚未落盘：用一次 vao.py plan 生成资产清单')
        L += ['', f'有图：{status}；媒体有证据职责才占画面。',
              '图像元素写 asset_id；出图按清单一次批量进行，check 时绑定核验。']
        manifest_flag = f' --assets-manifest "{manifest}"'
    else:
        L += ['', '无必要图像：不出图、不加载清单、不为填版造画面。']
        manifest_flag = ''
    L += ['填完后一次收口：',
          '  python scripts/vao.py check <本文件> out.pptx --mode release --speed strict'
          + manifest_flag,
          '', 'SPEC = {',
          '    "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},',
          '    "theme": {',
          f'        "colors": {colors!r},',
          f'        "fonts": {fonts!r},  # 世界排版语气；作者有依据时可覆盖',
          '    },',
          '    "slides": [']
    for pg in pages:
        # 骨架只写「下一步怎么落」：结论、权重、焦点+构图、排版、节奏、必落元素、未决。
        # 构图/焦点/空间的完整理由只在 plan.json 一处（SKILL §4），不在骨架重抄。
        j = pg.get("judgment") or {}
        claim = j.get("claim") or {}
        weight = j.get("information_weight") or {}
        role = j.get("visual_role") or {}
        focus = j.get("focus") or {}
        comp = j.get("composition") or {}
        spatial = j.get("spatial") or {}
        media = j.get("media") or {}
        prod = j.get("production") or {}
        typ = j.get("typography") or {}
        sc = typ.get("scale") or {}
        rhythm = j.get("rhythm") or {}
        evidence = (j.get("understanding") or {}).get("evidence")
        L.append(f'        # ── {pg.get("id")} · 角色:{role.get("role")} · 证据={evidence} · '
                 f'媒体:{_fmt_items([media.get("decision")], 1)}')
        if pg.get("ref"):
            # JSON 字面转义换行，避免作者原文里的换行破坏 Python 注释/骨架语法。
            L.append('        #    内容原文: ' + json.dumps(pg["ref"], ensure_ascii=False))
        if (pg.get("declarations") or {}).get("audience") \
                or (pg.get("declarations") or {}).get("decision"):
            L.append(f'        #    本页受众/决定: {j.get("audience")} → {j.get("decision")}')
        ctext = claim.get("text") or ("（本页不承载新结论）" if claim.get("source") == "frame"
                                      else "（缺：先写一句可复述的结论，或删掉这一页）")
        why = "" if claim.get("source") == "declared" else f' · 理由: {claim.get("why")}'
        L.append(f'        #    结论[{claim.get("source")}]: {ctext}{why}')
        t = j.get("tension") or {}
        if t.get("issue"):
            L.append(f'        #    阻力[{t.get("source")}]: {t["issue"]} · {t.get("why")}')
        L.append(f'        #    权重: 主 {_weight_brief(weight.get("maximize"))}；'
                 f'次 {_weight_brief(weight.get("weaken"))}；'
                 f'删除 {_weight_brief(weight.get("delete"))}')
        L.append(f'        #    焦点: {focus.get("element_role")}（{focus.get("type")}）· '
                 f'构图: {comp.get("chosen")} · 主区: {spatial.get("primary_zone")}')
        head = f'        #    排版: 主语 {typ.get("lead")} · 退后 {typ.get("support") or "无"}'
        if sc.get("body_measure_cjk"):
            head += f' · 行长≈{sc.get("body_measure_cjk")}字'
        if sc.get("lead_break"):
            head += f' · 断行: {sc["lead_break"]}'
        if typ.get("discipline") != BASE_DISCIPLINE:
            head += f'；{typ.get("discipline")}'
        L.append(head)
        if media.get("decision") not in (None, "none"):
            L.append(f'        #    媒体: {media.get("decision")} — {media.get("necessity")}')
        L.append(f'        #    跨页节奏[{rhythm.get("move")}]：{rhythm.get("why")}')
        if prod.get("must_place"):
            L.append('        #    必落元素: ' + "；".join(
                f'{x["role"]}({x["type"]})' for x in prod["must_place"])
                + f' · 密度 {prod.get("density_target")}')
        if j.get("open_questions"):
            L.append('        #    ⚠ 未决: ' + "；".join(j["open_questions"]))
        if pg.get("declarations"):
            shown = ", ".join(f"{k}={v!r}" for k, v in pg["declarations"].items())
            L.append(f'        #    作者声明（原样生效）: {shown}')
        L.append('        {')
        L.append(f'            "id": {pg.get("id")!r},')
        if pg.get("anchor"):
            # 判断对象原样落进 spec（不是散文提醒）：spec 层从此没有第二个「结论位」——
            # 结论住上面的判断注释，跨页锚住这里，作者一眼能对上是哪一个对象。
            L.append(f'            "anchor": {json.dumps(pg["anchor"], ensure_ascii=False)},')
        L.append('            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},')
        L.append('            "elements": [  # TODO：按上面的判断落元素')
        L.append('            ],')
        L.append('        },')
    L += ['    ],', '}', '']
    # 所有叙述都是注释，不让作者换行/三引号变成 Python 代码；spec 值仍用 repr/JSON。
    start = L.index('SPEC = {')
    lines = []
    for index, line in enumerate(L):
        if index < start or line.lstrip().startswith("#"):
            prefix = "# " if index < start else line[:line.index("#") + 1] + " "
            text = line if index < start else line[line.index("#") + 1:].lstrip()
            lines.extend(prefix + part.replace("\0", "\\0") for part in text.splitlines())
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"