# -*- coding: utf-8 -*-
"""intelligence.py · 设计智能层（唯一决策链，判断 + 理由）

    内容理解 → 受众 → 决策 → 结论抽取 → 信息权重 → 视觉角色 → 焦点判定
    → 构图推理 → 空间结构 → 媒体必要性 → 生产规格

本层做判断，并且**说出为什么**：

  * 每个判断都带 `why`；
  * 每个形式选择都带 `rejected`（被否掉的替代项与理由）——「为什么不是别的形式」
    和「为什么是这个形式」同等重要；
  * 证据不足时给 `open_question`，不编造答案（标题不是证据，数字不得脑补）。

本层**不给**坐标、字号、色值以外的执行细节：几何与尺度是生成侧的判断。
视觉世界（纸/墨/强调语义/材质/光/字体语气）由内容推导——没有风格预设表，
相同内容允许产生不同视觉结果（推导吃的是内容实质，不是页面类型）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DNA_STORE = Path(__file__).resolve().parent.parent / "memory" / "design_dna.json"

# ─────────────────────────────────────────────────────────────────────
# 1 · Brief 加载（唯一加载器：yml / json / 定义 BRIEF|NEED 的模块）
# ─────────────────────────────────────────────────────────────────────
def load_brief(path) -> dict:
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"需求文件不存在: {p}（brief 需为 .yml/.yaml/.json 或定义 BRIEF/NEED 的 .py）")
    if p.suffix in (".yml", ".yaml"):
        import yaml
        try:
            value = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = f":{mark.line + 1}:{mark.column + 1}" if mark else ""
            raise ValueError(f"brief YAML 解析失败：{p}{where} — "
                             f"{getattr(exc, 'problem', None) or exc}") from None
    elif p.suffix == ".json":
        try:
            value = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"brief JSON 解析失败：{p}:{exc.lineno}:{exc.colno} — {exc.msg}") from None
    elif p.suffix == ".py":
        import types
        mod = types.ModuleType("need_mod")
        mod.__file__ = str(p)
        exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), mod.__dict__)
        value = dict(mod.BRIEF) if hasattr(mod, "BRIEF") else (
            dict(mod.NEED) if hasattr(mod, "NEED") else None)
        if value is None:
            raise ValueError("brief 模块必须定义 BRIEF 或 NEED")
    else:
        raise ValueError("brief 只接受 .yml/.yaml/.json，或定义 BRIEF/NEED 的 .py")
    if not isinstance(value, dict):
        raise ValueError(f"brief 顶层必须是对象，实际是 {type(value).__name__}：{p}")
    return value


# ─────────────────────────────────────────────────────────────────────
# 2 · 内容理解（Content Understanding）
# ─────────────────────────────────────────────────────────────────────
# 六种证据形态：结论由哪一种承担，决定了后面的焦点与构图。
EVIDENCE_MODES = ("comparison", "series", "number", "structure", "sequence",
                  "proposition", "none")
VISUAL_ROLES = ("establish", "explain", "compare", "prove", "persuade", "summarize")

_NUM = re.compile(r"(?<![A-Za-z])(-?\d+(?:[.,]\d+)?)\s*(%|％|pp|倍|万|亿|元|美元|家|人|个|台|次|天|月|年|小时|分钟|分|秒)?")
_SENTENCE_SPLIT = re.compile(r"[。；;!?！？\n]|(?<=\.)\s+")

_NEGATED_EXCEED = re.compile(r"没(有)?超[过越]|[不未]超[过越]")
_COMPARISON_WORDS = ("对比", "相比", "vs", " versus ", "高于", "低于", "前者", "后者",
                     "优于", "落后", "差距", "benchmark", "对标", "增减",
                     "超过", "超越")
_SERIES_WORDS = ("趋势", "增长", "下降", "同比", "环比", "逐年", "路径", "曲线",
                 "涨", "跌", "下滑", "回升", "掉到", "掉至", "跌到", "跌至",
                 "trend", "growth", "yoy", "qoq")
_SEQUENCE_WORDS = ("步骤", "流程", "阶段", "路径", "迭代", "先", "然后", "接着", "最后",
                   "roadmap", "phase", "step", "milestone", "里程碑")
# 顺序的**形状**标记：箭头链本身就是序列，不需要作者写「步骤」两个字。
SEQUENCE_MARKERS = {"→", "⇒", "➜", "⇢"} | {"-"}
_STRUCTURE_WORDS = ("体系", "架构", "框架", "模型", "组织", "结构", "模块", "层级",
                    "平台", "中台", "能力", "framework", "architecture", "system")
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
                "体系", "回顾", "背景", "进展", "情况", "梳理")
# 要决定的一句话：出现它时，这一页的职责是把决定收成可执行的一句。
# 断言信号：一句真正的主张在**说变化或比较**（降至/超过/持平/翻倍…），
# 而不是在说相关性（「如何使用…」）。它比长度更接近「结论」的定义。
_CHANGE_WORDS = ("降至", "降到", "减到", "增至", "提升", "增加", "减少", "超过", "达到",
                 "带来", "持平", "翻倍", "高于", "低于", "上升", "下降", "占",
                 "grow", "drop", "reach", "cut", "exceed")
_ASK_WORDS = ("请批准", "请决定", "请审议", "请确认", "批准", "表决", "approve", "sign off",
              "approval")
_HUMAN_WORDS = ("客户", "用户", "团队", "员工", "患者", "伙伴", "受众", "消费者",
                "customer", "user", "team", "people", "community")
# 内容是不是「实体世界」：只有实体世界的开场才靠图像建立现场；
# 信息世界（纸/墨）的开场由排版与字阶建立——避免策略稿一律配图。
_PHYSICAL_SUBJECTS = ("stone_architecture", "metal_glass", "botanical", "water_sky",
                      "textile_domestic", "stage_screen", "ceramic_craft")

# 图像名额的价值权重：证词（图像就是证据）> 建立（图像就是主语）> 其余角色。
# 这不是风格偏好，是「删掉这张图，这一页少掉的是什么」的排序。
_MEDIA_VALUE = {"witness": 3.0, "subject": 2.0}
_ROLE_VALUE = {"establish": 3.0, "prove": 2.5, "persuade": 2.0, "compare": 1.5,
               "explain": 1.0, "summarize": 1.0}

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
        "words": ("发布", "舞台", "演出", "影像", "直播", "游戏", "电影", "音乐", "屏幕",
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
    不是量，也不进证据。
    """
    out = []
    for m in _NUM.finditer(str(text or "")):
        raw = m.group(0).strip()
        value = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").strip()
        # 「2026」「2026 年」都是时间坐标；「3 年」才是时长（值不在年份区间）。
        year = unit in ("", "年") and 1900 <= value <= 2100 and "." not in m.group(1)
        out.append({"raw": raw, "value": value, "unit": unit, "year": year})
    return out


def evidence_numerals(text: str) -> list[dict]:
    return [n for n in numerals(text) if not n["year"]]


def understand(text: str, *, has_chart: bool = False) -> dict:
    """内容理解：这段内容靠什么成立（证据形态）、有多少数字、有没有人。

    确定性、无副作用；它是判断的输入，不是判定的结果。
    """
    text = str(text or "")
    # 出处标注（「（来源：门店台账）」）不是内容：世界推导、人物/现场判定、
    # 证据形态都不该被它触发——否则一张台账的名字就能给整页配图。
    body = _SOURCE_TAIL.sub("", text).strip() or text
    # 「不超过/未超过」是界限不是对比：先剥掉再匹配，否则「误差不超过5%」
    # 会被判成两端对比（A超过B但C不超过D——真的超过不受影响）。
    cmp_body = _NEGATED_EXCEED.sub("", body)
    nums = numerals(text)
    ev = [n for n in nums if not n["year"]]   # = evidence_numerals(text)，复用同一次扫描
    # 标题重复正文的数字、同一数字写两遍：那是**同一个事实**，不是两个证据。
    # 判断证据形态与密度按去重后的数量算；「重复」这件事本身归信息权重管。
    distinct = len({(round(n["value"], 6), n.get("unit") or "") for n in ev})
    chars = max(len(text), 1)
    modes: dict[str, float] = {}
    if _hit(cmp_body, _COMPARISON_WORDS) or (distinct >= 2 and has_chart):
        modes["comparison"] = 0.6 + 0.1 * min(distinct, 3)
    if _hit(text, _SERIES_WORDS) or distinct >= 3:
        modes["series"] = 0.55 + 0.08 * min(distinct, 4)
    if distinct == 1:
        modes["number"] = 0.7
    if _hit(body, _STRUCTURE_WORDS):
        modes["structure"] = 0.65
    if _hit(body, _SEQUENCE_WORDS):
        modes["sequence"] = 0.6
    if SEQUENCE_MARKERS & set(body):
        # 箭头链本身就是顺序的形状：它比孤立数字更接近这一页的结构。
        modes["sequence"] = 0.75
    if _hit(body, _CONCLUSION_WORDS):
        modes["proposition"] = 0.55
    dominant = max(modes, key=lambda k: (modes[k], -EVIDENCE_MODES.index(k))) if modes else "none"
    subjects = [name for name, spec in _MATERIAL_LEXICON.items() if _hit(body, spec["words"])]
    return {
        "evidence": dominant,
        "numerals": nums,
        "distinct_numerals": distinct,
        "numeric_density": round(distinct / (chars / 100), 2),
        "subjects": subjects,
        "human": _hit(body, _HUMAN_WORDS),
        "scene": _hit(body, _SCENE_WORDS),
        "comparison": _hit(cmp_body, _COMPARISON_WORDS),
        "has_chart": bool(has_chart),
    }


# ─────────────────────────────────────────────────────────────────────
# 3 · 结论抽取（Claim Extraction）
# ─────────────────────────────────────────────────────────────────────
_SOURCE_TAIL = re.compile(r"[（(]\s*(来源|数据来源|source)[:：]?.*?[)）]\s*$", re.I)
_META_LINE = re.compile(r"[·｜|]|@|https?://|confidential|机密", re.I)
_CREDENTIAL_WORDS = ("提案", "汇报人", "主讲", "日期", "部门", "内部资料", "谢谢", "thanks",
                     "subtitle", "presented by")


def _fired(sent: str, words) -> str:
    """命中词回显：claim.why 里点名是哪一个词，不只说有一类词。"""
    return next((w for w in words if w in sent), "")


def extract_claim(item: dict) -> dict:
    """本页唯一结论：作者写了就用；没写就从内容里抽首句结论。

    抽不出来就 `absent`——**不编造**。摘要是观点不是证据，标题是话题不是结论。
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
        bonus = 1.2 if content else 0.6
        if title.endswith(_TOPIC_TAILS):
            bonus -= 0.8
        cands.append((title, bonus))
    for rank, sent in enumerate(_sentences(content)):
        cands.append((_SOURCE_TAIL.sub("", sent).strip(), 0.8 if rank == 0 else 0.0))
    best, best_score, best_bits = None, 0.0, []
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
        if _hit(sent, _ASK_WORDS):
            # 要决定的话本身就是结论（「请批准试点预算」没写也得算写了）：
            # 否则 ask 全在标题里时结论判 absent，role 会把要决定的页判成别的。
            score += 2.0
            bits.append(f"要决定「{_fired(sent, _ASK_WORDS)}」")
        snums = evidence_numerals(sent)
        if snums:
            # 没有内容时，光是数字说不上是结论（「18 个月落地节奏」是话题不是主张）：
            # 证据缺席的页面只能靠结论措辞立住，或者老实标 absent。
            score += 1.6 if content else 0.0
            bits.append("数字「" + "/".join(n["raw"] for n in snums[:3]) + "」")
        if _hit(sent, _CHANGE_WORDS):
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
        if _META_LINE.search(sent) or _hit(sent, _CREDENTIAL_WORDS):
            score -= 2.0     # 署名/提案/日期行不是结论
            bits.append("署名行扣分")
        if _hit(sent, _TOPIC_MARKERS):
            # 「如何使用/有哪些/概览」是话题：它说了要讲什么，没说结论——
            # 数字与短句都不该把它救成主张。
            score -= 2.5
            bits.append("话题标签扣分")
        if score > best_score:
            best, best_score, best_bits = sent, score, bits
    threshold = 1.2 if content else 2.0
    if best and round(best_score, 6) > threshold:
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


def information_weight(u: dict, claim: dict, text: str = "") -> dict:
    """三档权重：必须最大化 / 必须弱化 / 必须删除——每条给出理由。"""
    text = str(text or "")
    claim_text = str(claim.get("text") or "")
    maxi, weak, kill = [], [], []

    claim_nums = evidence_numerals(claim_text)
    primary = claim_nums[0] if claim_nums else None
    carried = [n["raw"] for n in claim_nums]
    if primary:
        maxi.append(f"{primary['raw']} — 结论的数字：本页最大的东西应该是它")
    for n in claim_nums[1:3]:
        weak.append(f"{n['raw']} — 对照基数：与结论同屏但小一档，用来把结论放回参照系")
    if claim_text and not claim_nums:
        maxi.append(f"「{claim_text[:26]}」— 结论句，本页第一落点必须落在它身上")
    if u.get("comparison"):
        maxi.append("对比的两端与差值 — 张力来自内容本身，读图要能读出方向")
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
    dupes = [raw for raw, c in counts.items() if c >= 2]
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
    if u.get("comparison"):
        role = "compare"
        why = "内容本身有两端对比，张力来自内容而不是装饰。"
        alts = [["explain", "把对比讲成并列说明＝抹平了本来存在的选择"]]
    elif ask:
        role = "summarize"
        why = "这一页要的是一个决定：把主张收成可执行的一句（做什么、谁来做、什么时候）。"
        alts = [["prove", "在要决定的页面上继续堆证据＝把决定推迟到下一次提问之后"]]
    elif ev in ("series", "number"):
        role = "prove"
        why = "数字承担论证：这一页的说服力来自可核验的量，而不是措辞。"
        alts = [["persuade", "用形容词说服＝把可核验的东西换成不可核验的"]]
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
def focus_of(role: str, u: dict, claim: dict, media: dict | None = None) -> dict:
    """第一落点：哪个元素承担结论，以及为什么不是别的元素。

    顺序即优先级：**通过必要性测试的图像 > 结论里的数字 > 那句话 > 标题**。
    图像之所以能排在最前，是因为它先通过了「没有它这一页会下降在哪里」这一问；
    没过测试的页面上根本不存在图像，第一落点自然回到文字。
    """
    media = media or {}
    # 承载结论的必须是证据量：年份（2026）与编号（Q1）不当第一落点。
    carried = evidence_numerals(claim.get("text") or "") or (
        [n for n in (u.get("numerals") or []) if not n.get("year")][:1]
        if u.get("evidence") in ("number", "series") else [])
    has_image = media.get("decision") in ("required", "reuse")
    claim_text = (claim.get("text") or "").strip()
    if has_image:
        choice = {"element_role": "image_subject" if media.get("function") != "witness"
                                     else "image_witness",
                  "type": "image",
                  "why": "本页的图像是主语/证词（已通过必要性测试）：第一落点是它，"
                         "文字退到解说位——否则图像就只是背景花纹。"}
        rejected = [["hero_statement", "用一句话当第一落点＝把已经赢得的现场感再退回文字"],
                    ["kpi_row", "把数字排成一行＝观众先看数字后看主张，顺序反了"]]
    elif u.get("comparison") and int(u.get("distinct_numerals") or 0) >= 2:
        choice = {"element_role": "comparison_field", "type": "chart",
                  "why": "两端共享同一基线与单位，差值肉眼可读；比较页的焦点是差，不是两端。"}
        rejected = [["two_pie", "两个饼图：占比比较最不可读的一种形式"],
                    ["radar", "雷达图形状相似度高，差异看不出来"],
                    ["side_by_side_cards", "左右卡片墙：视觉等权，读者得自己找答案"]]
    elif carried and role in ("prove", "summarize", "compare"):
        raw = carried[0]["raw"]
        choice = {"element_role": "kpi_main", "type": "chart",
                  "why": f"「{raw}」就是结论本身：让它成为页面上最大的对象，"
                         "并给出基期参照，读者不需要心算。"}
        rejected = [["card_grid_4", "四张等权卡片：等权＝没有结论，观众平均用力后什么都没记住"],
                    ["donut", "把一句话画成一圈：环形图要求读者心算比例，结论被稀释"],
                    ["gauge", "仪表盘指针只表达「好/不好」，不表达「多少」"]]
    elif u.get("evidence") in ("structure", "sequence"):
        choice = {"element_role": "structure_map", "type": "chart",
                  "why": "层级/顺序是内容本身的形状，画出来比写出来短。"}
        rejected = [["icon_row", "一排图标：图标不承载关系，只承载「我们有很多模块」"],
                    ["card_stack", "卡片堆叠把结构压成清单，关系丢失"]]
    elif role == "persuade" or (role == "establish" and len(claim_text) <= 42):
        choice = {"element_role": "statement_text", "type": "text",
                  "why": "焦点是这一页要立住的那句话：字阶与留白负责它的分量。"}
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
# 六个算子的中文释义住文档（references/judgment.md §算子 / SKILL 构图行）：
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
    s["data_field"] = (3.0 if ev in ("series", "comparison") else 0.0) \
        + (2.0 if n >= 3 else 0.0) + (1.0 if dense >= 6 else 0.0) \
        + (0.5 if u.get("comparison") else 0.0)
    s["big_whitespace"] = (3.0 if (n == 1 and ev in ("number", "series")) else 0.0) \
        + (2.0 if role == "persuade" else 0.0) + (1.0 if text_len <= 40 else 0.0) \
        - (1.5 if n >= 3 else 0.0)
    if not claim.get("text") and ev in ("none", "proposition"):
        # 无结论页用最少结构：结论没落定之前铺开，只会把缺席藏起来。
        s["big_whitespace"] += 1.0
    s["linear_structure"] = (3.0 if ev in ("sequence", "structure") else 0.0)
    s["asymmetric_tension"] = (2.5 if u.get("comparison") else 0.0) \
        + (1.5 if role == "compare" else 0.0) + (1.0 if n >= 2 else 0.0)
    s["editorial"] = (2.0 if text_len > 60 else 0.0) \
        + (1.5 if role == "summarize" else 0.0) + (1.0 if n == 0 else 0.0) \
        + (0.5 if text_len > 120 else 0.0)
    if role == "establish" and not has_image:
        s["big_whitespace"] += 1.5               # 开场建立权威靠空间，不靠铺陈
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
        return f"{n} 个数字共享同一基线：秩序交给网格与对齐，证据自己铺满这一页。"
    if chosen == "big_whitespace":
        return ("只有" + ("一个数字" if n == 1 else "一句话")
                + "要立住：留白把结论从噪音里隔离出来，空间本身就是分量。")
    if chosen == "linear_structure":
        return "内容本身有序（步骤/阶段/层级）：位置即顺序，轴与间距比装饰准确。"
    if chosen == "asymmetric_tension":
        return "两方不对等才有结论：让被推荐的一侧拿到尺度与墨色优先，差值自己说话。"
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
def spatial_of(comp: dict) -> dict:
    """空间职责：主区 / 安静区 / 阅读路径 / 四层权重。坐标由作者给。"""
    chosen = comp.get("chosen")
    if chosen == "big_whitespace":
        path, primary, quiet = "单点 → 参照 → 收束", "焦点区上三分之一至中部", "大面积安静面"
        duty = "保护焦点：让结论周围无竞争，空白可数、可命名为「参照系」"
    elif chosen == "data_field":
        path, primary, quiet = "结论 → 对照 → 明细", "上部结论带 + 中部数据场", "分组之间"
        duty = "承载证据密度：秩序来自网格与对齐，留白只出现在分组之间"
    elif chosen == "asymmetric_tension":
        path, primary, quiet = "重侧 → 轻侧 → 差值", "被推荐的一侧（大尺度）", "轻侧周围"
        duty = "制造倾向：轻侧的存在是为了让重侧更清楚"
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


# ─────────────────────────────────────────────────────────────────────
# 9 · 媒体必要性（Media Necessity：为什么没有它页面会下降）
# ─────────────────────────────────────────────────────────────────────
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
    if role == "establish" and presence:
        return {"decision": "required", "source": "judgment",
                "function": "subject",
                "necessity": "开场页要建立世界：内容里有可指认的人/场所，观众先看见它，"
                             "才愿意读主张。"}
    if role == "establish" and physical:
        return {"decision": "required", "source": "judgment",
                "function": "subject",
                "necessity": f"这一副讲的是实体世界（{physical[0]}）：开场让材质与光先说话，"
                             "比一句抽象主张更快建立可信度。"}
    if role == "prove" and presence and str(u.get("evidence")) not in ("series", "comparison"):
        return {"decision": "required", "source": "judgment",
                "function": "witness",
                "necessity": "这一页靠「确有其事」成立：图像是现场记录，页面上的话才有出处。"}
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
    if focus["type"] != "text":
        # 焦点不是文字时，结论句仍须落页；焦点就是那句话时不再重复要求一遍。
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
          "sans": {"cn": "Source Han l"}}


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
                       if u.get("evidence") in ("series", "number", "comparison")) / max(len(understanding), 1)

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
_PAGE_DECLARATIONS = ("density", "energy", "asset", "asset_role", "asset_function",
                      "asset_subject", "medium", "material", "lighting", "texture",
                      "asset_color", "safe_area", "text_color", "negative_space_anchor",
                      "asset_ratio", "asset_allow_crop", "asset_source", "composition",
                      "insight", "focus")


def _intent_value(value) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


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


def page_judgment(item: dict, *, index: int, total: int, brief: dict, world: dict,
                  warnings: list, u: dict | None = None) -> dict:
    """一页走完决策链：结论 → 权重 → 角色 → 焦点 → 构图 → 空间 → 媒体 → 生产规格。

    `u` 由 think 一次算好传进来（整页只理解一次）；直接调用时缺省当场算。
    """
    title = str(item.get("title") or "").strip()
    content = str(item.get("content") or "").strip()
    text = f"{title} {content}".strip()
    if u is None:
        u = understand(text, has_chart=bool(item.get("chart")))
    claim = extract_claim(item)
    if claim["source"] == "absent":
        warnings.append({"rule": "unresolved_content", "scope": item.get("id"),
                         "msg": "这一页没有可复述的结论（content 缺失）："
                                "标题不是证据，不得脑补数据/案例——补真实内容，"
                                "或把它降级为章节页，或删掉"})
    role = visual_role(u, index=index, total=total,
                       tension=str(brief.get("tension") or ""), claim=claim)
    media = media_necessity(u, role["role"],
                            declared=str(item.get("asset") or "").lower() or None,
                            has_chart=bool(item.get("chart")))
    focus = focus_of(role["role"], u, claim, media)
    comp = composition_of(role["role"], u,
                          composition_grammar=world.get("composition_grammar", ""),
                          media=media, claim=claim, content_len=len(text))
    focus, comp = _apply_declared_spot(focus, comp, item)
    spatial = spatial_of(comp)
    weight = information_weight(u, claim, text)
    prod = production_spec(focus, comp, media, u, weight)
    open_q = []
    if claim["source"] == "absent":
        open_q.append("本页结论：先写出一句可复述的话（或删掉这一页）")
    if media["source"] == "judgment" and media["decision"] == "required":
        open_q.append("图像主题由作者确认：画面里究竟出现什么（人物/场所/物件）")
    return {"claim": claim, "information_weight": weight,
            "visual_role": role, "focus": focus, "composition": comp, "spatial": spatial,
            "media": media, "production": prod, "understanding": u,
            "open_questions": open_q or None}


def _rejudge_without_image(entry: dict, *, text: str, world: dict,
                           budget_why: str) -> dict:
    """图位落选：media 回 none，焦点/构图/空间/生产随之重算。

    跨页预算校准单页——落选页不再是「要图但没图位」，而是「不要图」：
    焦点回到文字/数据，构图回到非图像算子，未决事项里不再追问图像主题。
    """
    j = entry["judgment"]
    old_fn = j["media"].get("function")
    media = {"decision": "none", "source": "judgment", "function": None,
             "necessity": budget_why}
    j["media"] = media
    u = j["understanding"]
    role = j["visual_role"]["role"]
    focus = focus_of(role, u, j["claim"], media)
    comp = composition_of(role, u, composition_grammar=world.get("composition_grammar", ""),
                          media=media, claim=j["claim"], content_len=len(text))
    focus, comp = _apply_declared_spot(focus, comp, entry.get("declarations"))
    j["focus"] = focus
    j["composition"] = comp
    j["spatial"] = spatial_of(comp)
    j["production"] = production_spec(focus, comp, media, u, j["information_weight"])
    j["open_questions"] = (["本页结论：先写出一句可复述的话（或删掉这一页）"]
                           if j["claim"].get("source") == "absent" else None)
    return {"page": entry["id"], "field": "media",
            "from": f"required:{old_fn}", "to": "none",
            "why": "跨页预算：图位让给更高价值页，本页由排版与数据承担"}


def _repick_avoiding(entry: dict, world: dict, text: str, avoid: str) -> dict | None:
    """连续同构图时取第二选择：内容不成立就不换（内容契合压过节奏）。"""
    j = entry["judgment"]
    u = j["understanding"]
    role = j["visual_role"]["role"]
    media = j["media"]
    grammar = world.get("composition_grammar", "")
    base = _composition_scores(u, role, media, len(text), grammar, j["claim"])
    penalized = dict(base)
    if avoid in penalized:
        penalized[avoid] -= 2.5
    order = {name: i for i, name in enumerate(_COMPOSITION_TIEBREAK)}
    new = max(penalized, key=lambda k: (penalized[k], -order[k]))
    if new == avoid or base.get(new, 0) <= 0:
        return None
    return {"chosen": new,
            "why": _composition_why(new, u, media) + "（跨页校准：连续同构图时的第二选择）",
            "rejected": _composition_rejections(new, base)}


def _coherence_pass(pages: list, world: dict, texts: dict) -> dict:
    """整套回看：连续同构图回拨中间页 + 节奏序列 + 焦点连落提醒。

    不是新规则，是单页判断在看到整套之后的重新校准：只改「内容允许第二选择」
    的页面；作者声明的构图不动；图像叙事不动（每张图各自通过必要性测试，
    数量由预算管，不由节奏管）。不新增逐页字段。
    """
    adjustments: list[dict] = []
    i = 0
    while i < len(pages):
        j = i
        while (j < len(pages) and pages[j]["judgment"]["composition"]["chosen"]
               == pages[i]["judgment"]["composition"]["chosen"]):
            j += 1
        run = pages[i:j]
        if len(run) >= 3 and run[0]["judgment"]["composition"]["chosen"] != "image_narrative":
            for entry in run[1:-1]:
                if entry["judgment"]["composition"].get("source") == "author":
                    continue
                new_comp = _repick_avoiding(entry, world, texts.get(entry["id"], ""),
                                            run[0]["judgment"]["composition"]["chosen"])
                if new_comp is None:
                    continue
                old = entry["judgment"]["composition"]["chosen"]
                entry["judgment"]["composition"] = new_comp
                entry["judgment"]["spatial"] = spatial_of(new_comp)
                entry["judgment"]["production"] = production_spec(
                    entry["judgment"]["focus"], new_comp, entry["judgment"]["media"],
                    entry["judgment"]["understanding"], entry["judgment"]["information_weight"])
                adjustments.append({"page": entry["id"], "field": "composition",
                                    "from": old, "to": new_comp["chosen"],
                                    "why": f"连续 {len(run)} 页同构图，内容允许第二选择"})
        i = j
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
    return {"compositions": [p["judgment"]["composition"]["chosen"] for p in pages],
            "densities": [p["judgment"]["production"]["density_target"] for p in pages],
            "roles": [p["judgment"]["visual_role"]["role"] for p in pages],
            "media": media_seq,
            "adjustments": adjustments or None,
            "notes": notes or None}


# ─────────────────────────────────────────────────────────────────────
# 13 · Design DNA（判断记忆：为什么有效，不是参数表）
# ─────────────────────────────────────────────────────────────────────
RESULT_MEMORY_KEYS = {"palette", "color", "colors", "font", "fonts",
                      "image_style", "layout", "layout_result"}
JUDGMENT_KEYS = {"hierarchy", "space", "media", "color_behavior",
                 "charts", "anchor_rule", "structure", "type_voice"}
_HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{3,8}\b")


def _load_store(path=None, strict=False) -> dict:
    target = Path(path) if path else DNA_STORE
    if not target.exists():
        return {"version": 1, "entries": []}
    try:
        from primitives import json_read_cached
        value = json_read_cached(target)
        if not isinstance(value, dict) or not isinstance(value.get("entries"), list):
            raise ValueError("经验库顶层必须是对象且 entries 必须是数组")
        return value
    except Exception as exc:
        if strict:
            raise
        return {"version": 1, "entries": [], "_load_error": f"{type(exc).__name__}: {exc}"}


def _leaf_strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _leaf_strings(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _leaf_strings(x)


def recall_dna(brief: dict) -> dict:
    """brief → 最匹配的设计经验（确定性关键词打分）。DNA 是起点不是模板。"""
    parts = [str(v) for v in (brief or {}).values() if isinstance(v, (str, int, float))]
    slides = (brief or {}).get("slides")
    if isinstance(slides, list):
        for s in slides:
            if isinstance(s, dict):
                parts.extend(str(s[k]) for k in ("title", "content", "subject", "text")
                             if isinstance(s.get(k), str))
            elif isinstance(s, str):
                parts.append(s)
    low = " ".join(parts).lower()
    store = _load_store()
    load_error = store.get("_load_error")
    entries = [e for e in (store.get("entries") or []) if isinstance(e, dict)]
    scored = []
    for e in entries:
        signature = e.get("signature") if isinstance(e.get("signature"), dict) else {}
        keywords = signature.get("keywords") if isinstance(signature.get("keywords"), list) else []
        sig = [str(s).lower() for s in keywords if str(s).strip()]
        if not sig:
            continue
        hits = sum(1 for s in sig if s in low)
        scored.append((hits / len(sig), hits, e))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2].get("id", "")))
    broken = len(entries) - len(scored)
    if not scored or scored[0][0] <= 0:
        note = ("无匹配 DNA：按内容推导视觉世界，发布 PASS 后运行 "
                "python scripts/vao.py dna --add <条目>.json 沉淀这条经验")
        if load_error:
            note += f"；经验库读取失败，已安全降级（{load_error}）"
        return {"matched": None, "confidence": 0.0, "dna": None, "alternatives": [],
                "note": note, "broken_entries": broken,
                **({"load_error": load_error} if load_error else {})}
    conf, hits, best = scored[0]
    return {"matched": best.get("id"), "confidence": round(conf, 2),
            "judgment": best.get("judgment"), "design_problem": best.get("design_problem"),
            "avoid": best.get("avoid"), "works_because": best.get("works_because"),
            "when_not_to": best.get("when_not_to"),
            "alternatives": [{"id": e.get("id"), "confidence": round(c, 2)}
                             for c, h, e in scored[1:3] if c > 0],
            "proven": best.get("proven"), "broken_entries": broken,
            "note": ("DNA 是起点不是模板：按本稿内容与受众重组，禁止照抄" if conf < 0.6
                     else "高置信命中：以该经验为基线，只做内容级调整")}


def validate_dna_entry(entry) -> tuple[list, list]:
    if not isinstance(entry, dict):
        return ["条目必须是对象（id / signature.keywords / judgment / pattern）"], []
    errors, warnings = [], []
    if not str(entry.get("id") or "").strip():
        errors.append("缺 id：稳定标识，用于去重与人工引用")
    if not str(entry.get("pattern") or "").strip():
        errors.append("缺 pattern：这条经验的模式名（一句话说清它解决什么）")
    judgment = entry.get("judgment")
    if not judgment or (isinstance(judgment, str) and not judgment.strip()):
        errors.append("缺 judgment：可迁移的行为判断（不是结果值）")
    signature = entry.get("signature") if isinstance(entry.get("signature"), dict) else {}
    keywords = [str(k).strip() for k in (signature.get("keywords") or []) if str(k).strip()]
    if not keywords:
        errors.append("缺 signature.keywords：召回只按关键词打分，空 = 永远命不中")
    if isinstance(judgment, dict):
        leaked = [str(k) for k in judgment if str(k) in RESULT_MEMORY_KEYS]
        if leaked:
            errors.append(f"judgment 里出现结果键 {leaked}：色值/字体/版式结果属于证据，"
                          "请移到 proven")
        unknown = sorted(str(k) for k in judgment
                         if str(k) not in JUDGMENT_KEYS and str(k) not in RESULT_MEMORY_KEYS)
        if unknown:
            errors.append(f"judgment 维度 {unknown} 不在合法维度内：{sorted(JUDGMENT_KEYS)}")
    hexes = sorted({h for leaf in _leaf_strings(judgment) for h in _HEX_COLOR.findall(leaf)})
    if hexes:
        errors.append(f"judgment 里写死了色值 {hexes}：判断要与具体值解耦")
    for key, why in (("design_problem", "当时面对什么矛盾"),
                     ("works_because", "为什么这个判断成立"),
                     ("avoid", "什么做法要避开"),
                     ("when_not_to", "什么情况下不适用")):
        if not entry.get(key):
            warnings.append(f"建议补 {key}（{why}）")
    return errors, warnings


def validate_dna_store(path=None) -> dict:
    store = _load_store(path)
    load_error = store.get("_load_error")
    if load_error:
        return {"ok": False, "entries": 0, "errors": [{"id": None, "reason": load_error}],
                "warnings": []}
    errors, warnings, seen = [], [], set()
    for i, entry in enumerate(store.get("entries") or []):
        eid = entry.get("id") if isinstance(entry, dict) else None
        label = str(eid) if eid else f"#{i}"
        if eid is not None and str(eid) in seen:
            errors.append({"id": label, "reason": "id 重复（同 id 只会在召回里互相遮蔽）"})
        seen.add(str(eid))
        e_errs, e_warns = validate_dna_entry(entry)
        errors += [{"id": label, "reason": m} for m in e_errs]
        warnings += [{"id": label, "reason": m} for m in e_warns]
    return {"ok": not errors, "entries": len(store.get("entries") or []),
            "errors": errors, "warnings": warnings}


def record_dna(entry, path=None, replace=False) -> dict:
    """写入一条经验：校验 → 去重 → 原子替换。写坏记忆比不写更贵。"""
    errors, warnings = validate_dna_entry(entry)
    if errors:
        return {"added": False, "id": (entry or {}).get("id") if isinstance(entry, dict) else None,
                "errors": errors, "warnings": warnings}
    target = Path(path) if path else DNA_STORE
    store = _load_store(target, strict=True)
    entries = [e for e in (store.get("entries") or []) if isinstance(e, dict)]
    eid = str(entry["id"]).strip()
    same = next((e for e in entries if str(e.get("id") or "").strip() == eid), None)
    if same is not None and not replace:
        if same == entry:
            return {"added": False, "id": eid, "entries": len(entries), "warnings": warnings,
                    "note": "同 id 且内容一致，已是库中条目（幂等，未改动）"}
        return {"added": False, "id": eid,
                "errors": ["同 id 条目已存在且内容不同：确认覆盖时加 --replace"],
                "warnings": warnings}
    if same is not None:
        entries[entries.index(same)] = entry
        action = "replaced"
    else:
        entries.append(entry)
        action = "added"
    store["entries"] = entries
    store["version"] = max(int(store.get("version") or 1), 2)
    from primitives import json_write
    json_write(target, store, indent=1)
    return {"added": True, "action": action, "id": eid, "entries": len(entries),
            "warnings": warnings, "note": f"{action} {eid} · 经验库现有 {len(entries)} 条"}


# ─────────────────────────────────────────────────────────────────────
# 14 · 单趟规划（think）
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

    try:
        dna = recall_dna(brief)
    except Exception as exc:
        warnings.append({"rule": "dna_unavailable", "scope": "deck",
                         "error": f"{type(exc).__name__}: {exc}"})
        dna = {"matched": None, "confidence": 0.0, "judgment": None, "note": "DNA 不可用"}

    raw = brief.get("slides")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise TypeError("brief.slides must be a list of page briefs")
    items = [it if isinstance(it, dict) else {"title": str(it)} for it in raw]

    understanding = [understand(f"{it.get('title') or ''} {it.get('content') or ''}".strip(),
                               has_chart=bool(it.get("chart"))) for it in items]
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
        judgment = page_judgment({**it, "id": sid,
                                  "asset": declared.get("asset", it.get("asset"))},
                                 index=i, total=len(items), brief=brief,
                                 world=world, warnings=warnings, u=understanding[i])
        anchor = None
        if len(items) >= 4:
            anchor = {"eyebrow": judgment["visual_role"]["role"].upper()}
            if i > 0:
                anchor["page_number"] = i + 1
        pages.append({"id": sid,
                      "ref": (f"{it.get('title') or ''} {it.get('content') or ''}").strip()[:120],
                      "judgment": judgment,
                      "anchor": anchor,
                      "declarations": declared or None})

    # 资产预算：只约束判断产生的出图；作者声明永不被截断。
    # 名额按**视觉价值**排（证词 > 建立 > 其余），不按页序截断——第 8 页的证词
    # 比第 1 页的装饰更值一张图。
    def _value(page: dict) -> float:
        media = page["judgment"]["media"]
        return _MEDIA_VALUE.get(str(media.get("function") or ""), 0.0) \
            + _ROLE_VALUE.get(page["judgment"]["visual_role"]["role"], 0.0)

    judged = [(p["id"], _value(p)) for p in pages
              if p["judgment"]["media"]["decision"] == "required"
              and p["judgment"]["media"]["source"] == "judgment"]
    declared_need = [p["id"] for p in pages
                     if p["judgment"]["media"]["decision"] in ("required", "reuse")
                     and p["judgment"]["media"]["source"] == "author"]
    cap = 2 if quality == "fast" else 4
    ranked = sorted(judged, key=lambda kv: (-kv[1], kv[0]))
    keep = {sid for sid, _ in ranked[:cap]}
    deferred = [{"slide_id": sid,
                 "why": f"图位按视觉价值分配（{cap} 张）：本页的图像价值低于 "
                        f"{'、'.join(s for s, _ in ranked[:cap])}，本页由排版与数据承担注意力。"}
                for sid, _ in ranked[cap:]]
    # 跨页预算执行：落选页的判断卡当场改写（media 回 none + 焦点/构图重算），
    # 而不是「判断说要图、清单说没图位」两张皮。
    by_id = {p["id"]: p for p in pages}
    budget_adjustments = []
    for d in deferred:
        entry = by_id.get(d["slide_id"])
        if entry is not None:
            budget_adjustments.append(
                _rejudge_without_image(entry, text=texts.get(entry["id"], ""),
                                       world=world, budget_why=d["why"]))
    coherence = _coherence_pass(pages, world, texts)
    coherence["adjustments"] = (budget_adjustments + (coherence["adjustments"] or [])
                                or None)
    return {
        "deck": {
            "audience": audience or None,
            "decision": decision or None,
            "tension": tension or None,
            "quality": quality,
            "world": world,
            "theme": _theme_seed(world, brief.get("brand_colors")),
            "dna": dna,
            "coherence": coherence,
        },
        "pages": pages,
        "assets_hint": {
            "generate": [p["id"] for p in pages
                         if p["id"] in keep or p["id"] in declared_need],
            "cap": cap,
            "deferred": deferred or None},
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


def build_skeleton(bundle: dict) -> str:
    """plan bundle → build 模块骨架。确定性：同 bundle 必得同文本。

    骨架把**判断连同理由**写进注释（含被否掉的替代项），把几何留给作者。
    """
    deck = bundle.get("deck") or {}
    pages = bundle.get("pages") or []
    world = deck.get("world") or {}
    colors = theme_tokens((deck.get("theme") or {}).get("colors_seed") or {})
    dna = deck.get("dna") or {}
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
    if dna.get("matched"):
        facts.append(f"经验召回（DNA）: {dna['matched']} · 置信 {dna.get('confidence')}"
                     "——起点不是模板，按本稿内容重组")

    L = ['# -*- coding: utf-8 -*-',
         '"""plan → build 骨架：判断已由规划层做（含理由与被否掉的替代项），几何由你决定。',
         '',
         '每页注释结构：结论 / 权重 / 角色 / 焦点 / 构图（含为什么不是别的）/ 空间 / 媒体必要性',
         '落笔顺序：先把每页焦点元素放在它该在的地方，再放支撑信息，最后才考虑装饰。',
         '字段与阈值速查 → references/contract.md；判断校准 → references/judgment.md。',
         f'质量档: {deck.get("quality")} · 页数: {len(pages)}']
    L += [f'  {line}' for line in facts]
    L += ['', '有图页先执行 assets → 出图；图片元素必须写 asset_id（check 时绑定核验）。',
          '填完后一次收口：',
          '  python scripts/vao.py check <本文件> out.pptx --mode release '
          '--assets-manifest asset_manifest.json',
          '"""', '', 'SPEC = {',
          '    "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},',
          '    "theme": {',
          f'        "colors": {colors!r},',
          '        "fonts": {},   # TODO: {"cn": ..., "latin": ...}（家族 ≤2）',
          '    },',
          '    "slides": [']
    for pg in pages:
        j = pg.get("judgment") or {}
        claim = j.get("claim") or {}
        weight = j.get("information_weight") or {}
        role = j.get("visual_role") or {}
        focus = j.get("focus") or {}
        comp = j.get("composition") or {}
        spatial = j.get("spatial") or {}
        media = j.get("media") or {}
        prod = j.get("production") or {}
        L.append(f'        # ── {pg.get("id")} · 角色={role.get("role")} · '
                 f'证据={j.get("understanding", {}).get("evidence")} · '
                 f'媒体={_fmt_items([media.get("decision")], 1)}')
        if pg.get("ref"):
            L.append(f'        #    内容: {pg["ref"][:88]}')
        L.append(f'        #    结论[{claim.get("source")}]: '
                 f'{claim.get("text") or "（缺：先写一句可复述的结论，或删掉这一页）"}')
        L.append(f'        #      理由: {claim.get("why")}')
        L.append(f'        #    权重: 最大化 {_fmt_items(weight.get("maximize"), 2)}；'
                 f'弱化 {_fmt_items(weight.get("weaken"), 2)}；'
                 f'删除 {_fmt_items(weight.get("delete"), 2)}')
        L.append(f'        #    角色: {role.get("role")} — {role.get("why")}')
        L.append(f'        #    焦点: {focus.get("element_role")}（{focus.get("type")}）— '
                 f'{focus.get("why")}')
        L.append(f'        #    构图: {comp.get("chosen")} — {comp.get("why")}')
        L.append(f'        #    空间: 路径 {spatial.get("reading_path")} · 主区 '
                 f'{spatial.get("primary_zone")} · 留白职责 {spatial.get("whitespace_duty")}')
        L.append(f'        #    媒体: {media.get("decision")} — {media.get("necessity")}')
        if prod.get("must_place"):
            L.append('        #    必落元素: ' + "；".join(
                f'{x["role"]}({x["type"]})' for x in prod["must_place"]))
        if prod.get("density_target"):
            L.append(f'        #    密度目标: {prod["density_target"]}')
        if j.get("open_questions"):
            L.append('        #    ⚠ 未决: ' + "；".join(j["open_questions"]))
        if pg.get("declarations"):
            shown = ", ".join(f"{k}={v!r}" for k, v in list(pg["declarations"].items())[:6])
            L.append(f'        #    作者声明（原样生效）: {shown[:150]}')
        L.append('        {')
        L.append(f'            "id": {pg.get("id")!r},')
        intent = {"insight": claim.get("text") or "", "focus": focus.get("element_role") or ""}
        L.append(f'            "page_intent": {json.dumps(intent, ensure_ascii=False)},'
                 '  # 判断已给出；要改就改这里')
        if pg.get("anchor"):
            L.append(f'            "anchor": {json.dumps(pg["anchor"], ensure_ascii=False)},'
                     '  # 眉标固定上缘 / 页码固定象限（落成对应 role 的元素）')
        L.append('            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},')
        L.append('            "elements": [  # TODO：按上面的判断落元素')
        L.append('            ],')
        L.append('        },')
    L += ['    ],', '}', '']
    return "\n".join(L)