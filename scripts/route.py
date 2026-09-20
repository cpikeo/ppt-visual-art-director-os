# -*- coding: utf-8 -*-
"""
Layer 0.7 · Route（视觉智能决策层 / Visual Intelligence Layer）

职责：把「内容类型 + 设计方向 + 质量等级」推导成页面级设计决策，替代逐页人工配置与
反复试错。它不做审美裁决（判断归 references/design-craft），也不持有主题（那是 spec.theme）。

对外只有两个函数（本模块无 CLI，生产入口只有 vao.py）：

    plan_page(page_intent, design_direction, quality_level) -> PagePlan
    plan_deck(brief) -> {"path", "pages", "theme", "assets", "budget",
                         "execution", "intent_interpretation", "warnings"}

brief 最小集（plan_deck 的唯一输入，yml / json / 定义 BRIEF 的模块均可）：

    audience: 董事会            decision: 追加品牌预算
    occasion: 2026 年终总结      design_direction: editorial_brand   # 可省；缺省走中性 quiet_minimal
    quality_level: fast|advanced                                   # 可省
    slides: ["封面：年度总结", {"id": "s04", "type": "data", "title": "增长结构"}]

设计约束（与 SKILL.md Decision Framework 一致）：
  * 纯函数、零配置、零外部依赖；不读写主题 Markdown，不产生文件。
  * 输出的是**建议与预算**，不改变 guard/compile/qa 的判定口径。
  * 只维护一张路由表；新增内容类型 = 在 ROUTES 加一行，不新增文件、不新增抽象层。
"""
from __future__ import annotations

import re

# ─────────────────────────────────────────────────────────────
# 内容类型词表（中英文关键词 → 内容类型）
# ─────────────────────────────────────────────────────────────
KEYWORDS: dict[str, tuple[str, ...]] = {
    "cover":        ("封面", "主题", "标题页", "cover", "title", "opening"),
    "agenda":       ("目录", "议程", "概览", "agenda", "contents", "summary"),
    "business":     ("经营", "业绩", "指标", "达成", "总结", "overview", "kpi", "okr",
                     "review", "复盘"),
    "statement":    ("判断", "观点", "结论", "原则", "主张", "statement", "insight",
                     "quote", "金句"),
    "data":         ("数据", "图表", "趋势", "增长", "占比", "转化", "同比", "环比",
                     "chart", "data", "revenue", "growth", "funnel"),
    "comparison":   ("对比", "前后", "竞品", "优劣", "vs", "compare", "benchmark"),
    "timeline":     ("时间轴", "里程碑", "历程", "阶段", "timeline", "roadmap",
                     "milestone"),
    "architecture": ("体系", "架构", "框架", "模型", "能力", "组织", "framework",
                     "architecture", "system", "structure"),
    "process":      ("流程", "步骤", "路径", "机制", "how", "process", "workflow",
                     "flow"),
    "product":      ("产品", "发布", "功能", "规格", "型号", "product", "feature",
                     "launch", "spec"),
    "brand_story":  ("品牌", "故事", "理念", "价值观", "缘起", "brand", "story",
                     "manifesto", "identity"),
    "case":         ("案例", "客户", "实证", "试点", "case", "study", "pilot"),
    "closing":      ("决定", "请求", "行动", "下一步", "展望", "结束", "close",
                     "ask", "next", "call to action", "vision"),
}

# ─────────────────────────────────────────────────────────────
# 路由表：content_type → 页面家族 / 密度 / 能量 / 素材策略 / 预算
#   asset: required 必须出图 · optional 默认不出图（作者逐页声明才出）· none 禁止出图
#   density 与渲染占用率目标同向（sparse .30 / balanced .55 / dense .75）
#   字阶不在路由表里：全库唯一真源是 design-system.md §字号阶梯的驻点表
#   （64/44/32/22/17/12.5），路由再发一份 type_scale 只会造出第二套口径
#   ——旧字段无消费者且 fast 档缩放值落在驻点之外，已删除。
# ─────────────────────────────────────────────────────────────
ROUTES: dict[str, dict] = {
    "cover":        dict(family="COVER", density="sparse", energy="high",
                         asset="required", asset_function="hero",
                         media=1, texts=4, empty_space="hold_emotion"),
    "brand_story":  dict(family="EDITORIAL", density="sparse", energy="medium",
                         asset="required", asset_function="emotion",
                         media=1, texts=4, empty_space="hold_emotion"),
    "product":      dict(family="HERO", density="balanced", energy="high",
                         asset="required", asset_function="hero",
                         media=1, texts=4, empty_space="protect_focus"),
    "case":         dict(family="CASE_STUDY", density="balanced", energy="medium",
                         asset="optional", asset_function="proof",
                         media=2, texts=4, empty_space="create_authority"),
    "statement":    dict(family="MINIMAL_STATEMENT", density="sparse", energy="low",
                         asset="optional", asset_function="emotion",
                         media=1, texts=4, empty_space="hold_emotion"),
    "closing":      dict(family="MINIMAL_STATEMENT", density="sparse", energy="medium",
                         asset="optional", asset_function="emotion",
                         media=1, texts=4, empty_space="hold_emotion"),
    "business":     dict(family="EXECUTIVE_SUMMARY", density="balanced", energy="medium",
                         asset="none", asset_function=None,
                         media=1, texts=4, empty_space="create_authority"),
    "agenda":       dict(family="EXECUTIVE_SUMMARY", density="balanced", energy="low",
                         asset="none", asset_function=None,
                         media=1, texts=5, empty_space="separate_chapter"),
    "data":         dict(family="DATA_STORY", density="balanced", energy="low",
                         asset="none", asset_function=None,
                         media=1, texts=4, empty_space="protect_focus"),
    "comparison":   dict(family="COMPARISON", density="balanced", energy="low",
                         asset="none", asset_function=None,
                         media=1, texts=4, empty_space="protect_focus"),
    "timeline":     dict(family="TIMELINE", density="balanced", energy="medium",
                         asset="none", asset_function=None,
                         media=1, texts=4, empty_space="separate_chapter"),
    "architecture": dict(family="FRAMEWORK", density="balanced", energy="medium",
                         asset="optional", asset_function="context",
                         media=1, texts=4, empty_space="separate_chapter"),
    "process":      dict(family="NARRATIVE", density="balanced", energy="medium",
                         asset="none", asset_function=None,
                         media=1, texts=4, empty_space="separate_chapter"),
}
DEFAULT_ROUTE = ROUTES["business"]

# 证据型家族：这些页没有真实 content 就不成立（数据 / 对比口径 / 案例细节 /
# 时间线事实）。content 为空时在 plan.warnings 与骨架注释里留痕 unresolved——
# 标题只是观点，不是证据；缺信息不是虚构的许可。
EVIDENCE_TYPES = frozenset({"data", "comparison", "case", "business", "timeline"})

# 显式声明的内容类型/家族 → 路由 key。作者写 `family: DATA_STORY` 或 `type: 数据`
# 都必须落到同一条路由；关键词嗅探只在作者什么都没写时才允许介入。
CONTENT_TYPE_ALIASES: dict[str, str] = {
    "title": "cover", "hero": "cover", "opening": "cover", "封面": "cover",
    "editorial": "brand_story", "manifesto": "brand_story", "brand": "brand_story",
    "launch": "product", "product_story": "product", "release": "product",
    "case_study": "case", "proof": "case", "客户案例": "case",
    "quote": "statement", "insight": "statement", "金句": "statement",
    "data_story": "data", "chart": "data", "metric": "data", "数据页": "data",
    "compare": "comparison", "versus": "comparison", "对比": "comparison",
    "roadmap": "timeline", "milestone": "timeline", "时间轴": "timeline",
    "framework": "architecture", "structure": "architecture", "system": "architecture",
    "narrative": "process", "steps": "process", "流程": "process",
    "executive_summary": "business", "summary": "business", "overview": "business",
    "agenda": "agenda", "toc": "agenda", "目录": "agenda",
    "closing": "closing", "cta": "closing", "ending": "closing", "结束页": "closing",
}

_EXPLICIT_TYPE_KEYS = ("type", "family", "page_family", "content_type")


def _canonical_content_type(value) -> str | None:
    """一个词 → 路由 key（认 ROUTES、别名表、包含匹配；不认识就 None，不猜）。"""
    token = str(value or "").strip().lower()
    if ":" in token:                       # 兼容 "family: data" 这类整串写法
        token = token.split(":", 1)[1]
    token = token.strip().replace("-", "_").replace(" ", "_")
    if len(token) < 2:
        return None
    if token in ROUTES:
        return token
    if token in CONTENT_TYPE_ALIASES:
        return CONTENT_TYPE_ALIASES[token]
    for alias, ctype in CONTENT_TYPE_ALIASES.items():
        if alias in token or (len(token) >= 2 and token in alias):
            return ctype
    return None


def explicit_content_type(item) -> str | None:
    """作者显式声明的内容类型（归一后）；没写返回 None。

    只有这里判定「作者说了什么」——关键词嗅探永远不进这一步。
    """
    if not isinstance(item, dict):
        return None
    for key in _EXPLICIT_TYPE_KEYS:
        raw = item.get(key)
        if _intent_value(raw):
            hit = _canonical_content_type(raw)
            if hit:
                return hit
    return None


# 设计方向 → 视觉推导（材质 / 光线 / 图表风格 / 背景策略）。只列可执行差异，不做形容词堆叠。
# theme_seed：该方向的「成品种子色板 + 字体」。种子不是模板——spec.theme 拿到种子后仍由
# primitives.derive_tokens 规则展开出完整色阶（panel/hairline/ramp/series…），调用方也仍可
# 覆盖任意一项。这里只解决「选了方向却还要自己手挑 hex」的空白，把方向落到一组调好的锚点色。
DIRECTION_PRESETS: dict[str, dict] = {
    "quiet_minimal": dict(
        background="solid_world", material="matte paper",
        light="flat even ambient", chart="hairline + direct label",
        motion="still", asym=False,
        theme_seed=dict(
            colors={"background": "#F5F4EF", "surface": "#FBFAF6",
                    "primary": "#26251F", "secondary": "#6E6A5E",
                    "accent": "#B3422A", "ink": "#1B1A16", "muted": "#8A857A"},
            fonts={"cn": "PingFang SC", "latin": "Helvetica Neue",
                   "display": "Helvetica Neue"},
            text_default="ink",
            chart_primary="primary", chart_secondary="accent", chart_muted="secondary",
            constraints={"accent_max": 0.05, "max_colors": 5, "whitespace_min": 0.62, 
                              "type_step_min": 1.25, "decoration_area_max": 0.06,
                              "bg_layers_max": 1, "bold_ratio_max": 0.50},
            color_intent=["hierarchy", "emotion", "brand"],
        )),
    "editorial_brand": dict(
        background="atmospheric", material="paper + ink wash",
        light="single soft upper-left", chart="annotation field",
        motion="reveal", asym=True,
        theme_seed=dict(
            colors={"background": "#FAF7F0", "surface": "#F4EFE6",
                    "primary": "#2B241B", "secondary": "#9A8F7C",
                    # 信号色用编辑红（oxblood）：与棕/沙色相区分，承担「唯一重点」；
                    # 金属金降为 premium，仅供克制的符号性点缀（不参与强调判定）。
                    "accent": "#8E2F28", "premium": "#A97E2F",
                    "ink": "#191510", "muted": "#7C7468"},
            fonts={"cn": "Songti SC", "latin": "Georgia", "display": "Georgia"},
            text_default="ink",
            chart_primary="primary", chart_secondary="accent", chart_muted="muted",
            constraints={"accent_max": 0.04, "max_colors": 5, "whitespace_min": 0.58,
                              "type_step_min": 1.25, "decoration_area_max": 0.08,
                              "bg_layers_max": 1, "bold_ratio_max": 0.45},
            color_intent=["brand", "emotion", "hierarchy"],
        )),
    "product_stage": dict(
        background="dark_luminous", material="glass + metal",
        light="one key light", chart="minimal kpi",
        motion="reveal", asym=False,
        theme_seed=dict(
            colors={"background": "#0B0B0F", "surface": "#15151A",
                    "primary": "#E4E4EA", "secondary": "#3A3A42",
                    "accent": "#3B82F6", "ink": "#F5F5F7", "muted": "#8E8E96"},
            fonts={"cn": "PingFang SC", "latin": "Helvetica Neue",
                   "display": "Helvetica Neue"},
            text_default="ink",
            chart_primary="primary", chart_secondary="accent", chart_muted="muted",
            constraints={"accent_max": 0.05, "max_colors": 5, "whitespace_min": 0.48,
                              "type_step_min": 1.30, "decoration_area_max": 0.12,
                              "bg_layers_max": 2, "bold_ratio_max": 0.65},
            color_intent=["emotion", "brand", "hierarchy"],
        )),
    "evidence_first": dict(
        background="solid_world", material="neutral surface",
        light="flat", chart="shared baseline + delta",
        motion="still", asym=False,
        theme_seed=dict(
            # 数据智能：纯中性结构（近黑墨 + 中性灰）+ 单一蓝信号。蓝是唯一的色相，
            # 结构色保持无彩度，让「蓝色」真正成为唯一重点信号（palette_discipline
            # 的 accent 角距离门禁因此通过，而非靠同族深浅堆出伪强调）。
            colors={"background": "#FFFFFF", "surface": "#F4F5F6",
                    "primary": "#1C1C1C", "secondary": "#5A5A5A",
                    "accent": "#2563EB", "ink": "#101010", "muted": "#6E6E6E"},
            fonts={"cn": "PingFang SC", "latin": "Helvetica Neue",
                   "display": "Helvetica Neue"},
            text_default="ink",
            chart_primary="primary", chart_secondary="accent", chart_muted="secondary",
            constraints={"accent_max": 0.05, "max_colors": 5, "whitespace_min": 0.52,
                              "type_step_min": 1.25, "decoration_area_max": 0.05,
                              "bg_layers_max": 1, "bold_ratio_max": 0.60},
            color_intent=["hierarchy", "brand", "emotion"],
        )),
}

# 证据编号（Fig. 01/02…）已从锚点体系移除：它是论文/白皮书的引用装置，
# 前提是正文里有「见 Fig. 02」这样的交叉引用。演示文稿没有这种引用——
# 每页自己就是一个论点，读者不会翻回去找编号，
# 于是编号只是在来源行前面加一串谁也不看的字符，还占掉了本该留给口径的宽度。
# 页内导航由眉标（我在哪一章）+ 页码（我在第几页）承担，两个锚点已经够了。

ADVANCED_TRIGGERS = ("发布会", "品牌", "年报", "旗舰", "形象", "高端", "launch", "brand",
                     "keynote", "manifesto", "premium", "campaign")

# 自由文本方向必须先落到已知方向；否则「Quiet Luxury × Editorial Storytelling」
# 会静默回落 quiet_minimal，丢掉材质/字声判断。别名只做确定性归一，不新增设计模板。
DIRECTION_ALIASES = {
    "quiet minimal": "quiet_minimal", "quiet_minimal": "quiet_minimal",
    "minimal": "quiet_minimal", "neutral": "quiet_minimal",
    "editorial": "editorial_brand", "editorial brand": "editorial_brand",
    "editorial storytelling": "editorial_brand",
    "quiet luxury": "editorial_brand",
    "quiet luxury x editorial storytelling": "editorial_brand",
    "quiet_luxury": "editorial_brand", "luxury editorial": "editorial_brand",
    "product stage": "product_stage", "product_stage": "product_stage",
    "evidence first": "evidence_first", "evidence_first": "evidence_first",
    "data intelligence": "evidence_first",
}


def _color_family(value) -> dict | None:
    """取「色彩方向族」的定义（若 name 是 design_intelligence_rules.COLOR_DIRECTIONS 的一员）。

    两张表管的是不同维度，本函数是它们唯一的合流点：
      * `DIRECTION_PRESETS`（4 个）给**结构**——background / light / chart 手法 / 对称性 / 字体；
      * `COLOR_DIRECTIONS`（13 个）给**材质与人格**——material / motion / texture / 色板骨架。
    族名过去一律静默回落成 quiet_minimal，于是 song_elegance 这类姓氏根本送不到
    资产层——方向写了等于没写。介质（水墨/摄影）由每张资产自己的 medium 决定，
    方向族名只负责把材质、动势与纹理语言送达。
    """
    name = str(value or "").strip().lower()
    if not name:
        return None
    try:
        from design_intelligence_rules import COLOR_DIRECTIONS
    except ImportError:      # 判断层缺失时保持原行为，不把包带崩
        return None
    entry = COLOR_DIRECTIONS.get(name)
    return dict(entry) if isinstance(entry, dict) else None


def _canonical_direction(value) -> tuple[str, dict | None]:
    raw = str(value or "").strip()
    if not raw:
        return "quiet_minimal", None
    if raw in DIRECTION_PRESETS:
        return raw, None
    if _color_family(raw):
        return raw.lower(), None
    key = re.sub(r"\s+", " ", raw.lower().replace("×", " x ")).strip()
    if key in DIRECTION_ALIASES:
        return DIRECTION_ALIASES[key], None
    if _color_family(key):
        return key, None
    # 组合型方向允许命中最长语义片段，但不会任意猜测单个形容词。
    for alias, canonical in sorted(DIRECTION_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if len(alias) >= 8 and alias in key:
            return canonical, {"input": raw, "canonical": canonical, "rule": "direction_alias"}
    return "quiet_minimal", {"input": raw, "canonical": "quiet_minimal", "rule": "direction_fallback"}


def _keyword_hit(text: str, keyword: str) -> bool:
    """CJK 用子串；ASCII 用词边界，避免 history→story 等误路由。"""
    tok = str(keyword or "").strip().lower()
    if not tok:
        return False
    if all(ord(c) < 128 for c in tok):
        return re.search(rf"(?<![a-z0-9_]){re.escape(tok)}(?![a-z0-9_])", text) is not None
    return tok in text


def detect_type(text: str) -> str:
    """按关键词命中内容类型；未命中时回落到 business（最常见的汇报页）。"""
    t = str(text or "").lower()
    best, best_hits = None, 0
    for ctype, kws in KEYWORDS.items():
        hits = sum(1 for k in kws if _keyword_hit(t, k))
        if hits > best_hits:
            best, best_hits = ctype, hits
    return best or "business"


QUALITY_ALIASES = {"fast": "fast", "quick": "fast", "standard": "fast",
                   "advanced": "advanced", "premium": "advanced", "keynote": "advanced",
                   # benchmark 案例需要完整媒体预算与 review 证据，不应静默走 fast。
                   "benchmark": "advanced"}
MODE_LABEL = {"fast": "Fast Mode", "advanced": "Premium Mode"}


def _quality(quality_level) -> str:
    """归一质量等级：只认 fast / advanced，别名（quick、premium、keynote）映射过去，
    未知值落到 fast——「不确定时先走轻流程」比「默认最高复杂度」更符合成本约束。"""
    return QUALITY_ALIASES.get(str(quality_level or "").strip().lower(), "fast")


def plan_page(content_type: str, design_direction: str = "quiet_minimal",
              quality_level: str = "advanced") -> dict:
    """单页推导：内容类型 + 设计方向 + 质量等级 → 布局 / 密度 / 字阶 / 素材 / 图表口径。

    参数只有三个，其余全部由 ROUTES 与 DIRECTION_PRESETS 推导；调用方不应再逐页传
    color / mood / lighting / material / composition —— 那些是本页的输出，不是输入。
    """
    content_type = str(content_type or "")
    if content_type not in ROUTES:
        content_type = detect_type(content_type)
    r = ROUTES.get(content_type, DEFAULT_ROUTE)
    # 自由文本方向先规范化；未知方向仍安全回落，但由 plan_deck 留 warning。
    quality = _quality(quality_level)

    asset = r["asset"]
    if asset == "optional":
        # advanced ≠ 更多图片（契约：质量等级提升的是判断与证据预算，不是视觉数量）。
        # 可选页默认不出图——Native-First：出不出图由作者逐页声明决定
        # （asset: required / asset_subject，见 _plan_deck），或由生成侧判断后声明。
        # 曾经「advanced 把全部 optional 页升为 required」：那会把最适合纯排版的页
        # 强塞一张图 → 为放图改版式 → 多一次出图 + 多一轮 QC，审美与速度双输。
        asset = "none"
    if quality == "fast" and asset == "required" and r["asset_function"] in ("emotion",):
        asset = "reuse"          # 快速路径：复用已有画心，不再新出图

    return {
        "content_type": content_type,
        "mode": MODE_LABEL[quality],
        "page_family": r["family"],
        "density": r["density"],
        "energy": r["energy"],
        "empty_space_role": r["empty_space"],
        "media_budget": r["media"],
        "text_budget": r["texts"],
        "asset": {"decision": asset, "function": r["asset_function"],
                  "why": _asset_reason(content_type, asset)},
        # 焦点恒为结论句（statement 级）；元素 id 由生成侧决定，
        # 这里只给语义指向，不给坐标、不给命名模板。
        "focus": "statement",
    }


def _asset_reason(ctype: str, decision: str) -> str:
    if decision in ("required", "reuse"):
        return f"{ctype} 承担空间/情绪/实证职责，画心是内容的一部分"
    if decision == "none":
        return f"{ctype} 的注意力预算属于数据与结论，出图会争夺第一注意点"
    return f"{ctype} 出不出图由作者逐页声明决定（asset / asset_subject）"


_DECK_CACHE: dict[str, dict] = {}
MAX_DECK_CACHE = 32   # 只缓存整副 deck 的规划结果；有界，不演化成配置系统

# 方向的构图语法词表（与 design-intelligence.md §04 direction 的键一致）。
# 注意：它和页面级的 `design_intelligence.COMPOSITION_POOL`
# （scale_contrast / split_field / grid_evidence …）**不是同一套词**——
# 前者说「这副 deck 的轴线性格」（软偏轴还是硬网格），后者说「这一页怎么摆」。
# 两者同名不同义，brief 的 composition_grammar 指的是前者。
DIRECTION_COMPOSITION_GRAMMARS = (
    "soft_asymmetry", "strict_grid", "cinematic_stage", "evidence_field", "path_sequence",
)


def _execution_with_brief_overrides(direction: str, brief: dict | None) -> dict:
    """方向执行参数 + brief 里显式写下的构图语法 / 背景场景。

    这两个键与 `direction_execution` 的字段一一对应，所以 brief 写了就该生效：
    它们是「这副 deck 长什么样」的直接判断，预设只是起点。别的视觉字段
    （tone_hint / type_voice / color_behavior / media_policy / energy_curve）
    没有对应的消费点，已从 brief 契约里删除——留着只会让人写了以为生效。
    """
    execution = _direction_execution(direction)
    if not isinstance(brief, dict):
        return execution
    grammar = str(brief.get("composition_grammar") or "").strip()
    if grammar and grammar.lower() != "unknown" and grammar in DIRECTION_COMPOSITION_GRAMMARS:
        execution["composition_grammar"] = grammar
    scene = str(brief.get("background_scene") or "").strip()
    if scene and scene.lower() != "unknown":
        execution["background"] = scene
    return execution


def _direction_execution(direction: str) -> dict:
    """方向 → 执行参数（deck 级事实，逐页复制没有意义）。

    这些词是介质/光照/图表手法的描述，不是模板：它们约束「用什么质感说话」，
    不规定元素放在哪里。几何与构图永远归生成侧的设计判断。
    """
    d = DIRECTION_PRESETS.get(direction, DIRECTION_PRESETS["quiet_minimal"])
    fam = _color_family(direction) or {}
    motion_keys = tuple(fam.get("motion") or ())
    texture_keys = tuple(fam.get("texture") or ())
    return {
        "background": d["background"],
        # 族的材质语言优先于预设的骨架材质：宋韵要的是 rice paper，不是 matte paper。
        "material": str(fam.get("material") or d["material"]),
        "light": d["light"],
        "chart_style": d["chart"],
        # motion / texture 传**键名**，由 asset_prompt.enhance_asset_card 统一查表展开
        # —— 同一张表只允许有一个读者，避免两处各读一遍再各自漂移。
        "motion": (motion_keys or (d["motion"],))[0],
        "texture_keys": list(texture_keys),
        "composition_grammar": "soft_asymmetry" if d["asym"] else "evidence_field",
    }


def normalize_brand_colors(brand) -> dict:
    """brand_colors 的唯一归一入口：既收 {token: #HEX}，也收 [#HEX, ...]。

    templates/brief.yml 把 `brand_colors` 教成 YAML 列表（`["#1A3A5C", "#C8501E"]`），
    但派生侧只认 dict——照文档写会**静默**走回方向预设的灰阶，品牌色一个都不生效。
    「写了却没生效」是这份技能包最贵的一类漏洞（没有报错、没有痕迹，只有产物不对），
    因此在入口处收敛：

      * dict  → 原样按槽位名取（未知键与非色值忽略，行为不变）；
      * list  → 按**品牌色惯例序**落位：第 1 个是主色，第 2 个是强调色，
                第 3 个是辅色。这是有语义的顺序约定，不是 dict.values() 那种
                「插入顺序当语义」的猜测——列表本身就没有别的信息可用，
                而约定被写进了 brief 模板与 SKILL，作者可随时改用 dict 精确指定。

    只接受 #RGB / #RRGGBB；其余一律忽略。返回 {} 表示「品牌没给出可用色」。
    """
    if isinstance(brand, dict):
        return {str(k).strip(): str(v).strip() for k, v in brand.items()
                if isinstance(v, str) and str(v).strip().startswith("#")
                and len(str(v).strip()) in (4, 7)}
    if isinstance(brand, (list, tuple)):
        hexes = [str(v).strip() for v in brand
                 if isinstance(v, str) and str(v).strip().startswith("#")
                 and len(str(v).strip()) in (4, 7)]
        return {slot: value for slot, value
                in zip(("primary", "accent", "secondary"), hexes)}
    return {}


def _seed_from_brand(preset: dict, brand) -> dict:
    """品牌色优先：brief.brand_colors 覆盖方向预设色板。

    方向预设只保留结构与未覆盖的灰阶骨架；主色/accent/secondary 一旦品牌给出
    立即让位。接受 {token: #HEX} 与 [#HEX, ...] 两种写法（见
    `normalize_brand_colors`）；空 brand 原样返回。
    """
    valid = normalize_brand_colors(brand)
    if not valid:
        return preset
    seed = dict(preset)
    colors = dict(seed.get("colors") or {})
    colors.update(valid)
    seed["colors"] = colors
    seed["brand_derived"] = True
    seed["seed_note"] = ("色板由 brief.brand_colors 品牌优先派生；方向预设仅保留"
                         "结构与未覆盖的灰阶骨架——色值永远跟随品牌，不跟随方向标签")
    return seed


def plan_deck(brief: dict) -> dict:
    """整副 deck 的路径判定 + 逐页规划 + 素材预算 + 建议执行链（带决策缓存）。

    brief 最小集：{"audience","decision","occasion","slides":[str|dict], "quality_level"?}

    Decision Before Generation：一次推导供 guard / compile / qa 全流程消费；
    同一 brief 的重复调用（修订循环、多次调用同一进程）直接命中缓存，且返回深拷贝，
    调用方可以随意改结果而不污染缓存。
    """
    if not isinstance(brief, dict):
        raise TypeError("brief must be a mapping/dict")
    try:
        import copy as _copy
        import json as _json
        key = _json.dumps(brief, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError, OverflowError):  # 不可序列化 → 直接算，不缓存
        return _plan_deck(dict(brief))
    hit = _DECK_CACHE.get(key)
    if hit is not None:
        return _copy.deepcopy(hit)
    plan = _plan_deck(dict(brief))
    if len(_DECK_CACHE) >= MAX_DECK_CACHE:  # 有界缓存：先淘汰最早写入的一半
        for k in list(_DECK_CACHE)[: MAX_DECK_CACHE // 2]:
            _DECK_CACHE.pop(k, None)
    _DECK_CACHE[key] = plan
    return _copy.deepcopy(plan)


def _intent_value(value) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))





def _deck_intent_interpretation(brief: dict, requested_direction, direction,
                                quality_input, quality, pages, warnings) -> dict:
    explicit_keys = ("audience", "decision", "occasion", "subject", "brief",
                     "design_direction", "quality_level", "slides")
    explicit = {k: brief.get(k) for k in explicit_keys
                if k in brief and _intent_value(brief.get(k))}
    inferred = {
        "design_direction": {"value": direction,
                              "basis": "explicit canonicalization" if "design_direction" in explicit
                                       else "default quiet_minimal"},
        "quality_level": {"value": quality,
                           "basis": "explicit alias" if "quality_level" in explicit
                                    else "occasion trigger / fast default"},
        "page_count": {"value": len(pages), "basis": "explicit slides list"},
        "execution_mode": {"value": recommend_mode(brief), "basis": "brief cost and risk signals"},
    }
    conflicts = []
    for w in warnings:
        if not isinstance(w, dict):
            continue
        rule = str(w.get("rule") or "")
        if rule in {"direction_alias", "direction_fallback"}:
            conflicts.append({"field": "design_direction", "explicit": requested_direction,
                              "inferred": direction, "reason": rule})
        elif rule == "quality_fallback":
            conflicts.append({"field": "quality_level", "explicit": quality_input,
                              "inferred": quality, "reason": rule})
    return {"explicit": explicit, "inferred": inferred, "conflicts": conflicts}


def _plan_deck(brief: dict) -> dict:
    occasion = f"{brief.get('occasion','')} {brief.get('subject','')} {brief.get('brief','')}"
    quality_input = brief.get("quality_level")
    quality = _quality(quality_input) if quality_input else (
        "advanced" if any(k in occasion.lower() or k in occasion for k in ADVANCED_TRIGGERS)
        else "fast")
    quality_warning = None
    if quality_input and str(quality_input).strip().lower() not in QUALITY_ALIASES:
        quality_warning = {"input": quality_input, "canonical": quality,
                           "rule": "quality_fallback"}
    requested_direction = brief.get("design_direction") or "quiet_minimal"
    direction, direction_warning = _canonical_direction(requested_direction)

    raw = brief.get("slides")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise TypeError("brief.slides must be a list of page briefs")
    pages = []
    for i, item in enumerate(raw):
        text = (str(item.get("title") or "") + " " + str(item.get("content") or "")) if isinstance(
            item, dict) else str(item)
        declared_type = explicit_content_type(item)
        page = plan_page(declared_type or text, direction, quality)
        if isinstance(item, dict):
            # 显式声明赢过推断：密度/能量/留白职责以作者为准，冲突只留痕不改写。
            for field in ("density", "energy", "empty_space_role"):
                value = item.get(field)
                if _intent_value(value):
                    page[field] = str(value).strip()
                    if field == "density":
                        page["density_explicit"] = True
            if _intent_value(item.get("asset_function")):
                page.setdefault("asset", {})["function"] = str(item["asset_function"]).strip()
            # 契约规则 #1「写了的字段原样生效」——asset 声明不例外：
            # asset: required/reuse/none 直接改写决策；写了 asset_subject 即视为要出图。
            # （此前这两种声明落在 decision=none 的页上会被静默跳过——声明被吃掉，
            # 是最贵的一类契约违约：作者以为写了就生效。）
            declared_asset = str(item.get("asset") or "").strip().lower()
            if declared_asset in ("required", "reuse", "none"):
                page.setdefault("asset", {})["decision"] = declared_asset
                page["asset"]["why"] = "作者显式声明（逐页 asset 压过家族默认与质量等级）"
                page["asset"]["author_declared"] = True
            elif (_intent_value(item.get("asset_subject"))
                  and (page.get("asset") or {}).get("decision") == "none"):
                page.setdefault("asset", {})["decision"] = "required"
                page["asset"]["why"] = "作者声明了 asset_subject：这一页的画面是内容的一部分"
                page["asset"]["author_declared"] = True
            # 标题不代替内容：证据型家族页 content 为空 → 标成待判断项（不阻断）。
            # 缺信息不是虚构的许可——下游不得由标题脑补曲线、数字或案例细节。
            if (not str(item.get("content") or "").strip()
                    and page.get("content_type") in EVIDENCE_TYPES):
                page["content_missing"] = True
            if _intent_value(item.get("composition")):
                page["composition_explicit"] = str(item["composition"]).strip()
        page["index"] = i + 1
        page["id"] = (item.get("id") if isinstance(item, dict) and item.get("id")
                      else f"s{i + 1:02d}")
        page["declared_type"] = declared_type
        pages.append(page)
    # 逐页 intent_interpretation（显式/推断/冲突镜像）在 plan.pages 之外零消费：
    # 作者覆盖已直接生效在页面字段上（上面 density_explicit 等），冲突留痕
    # deck 级一份（plan.intent_interpretation）足够——每页再发一份约 500 字节
    # 的机器镜像只增大计划与骨架，不改变任何决策，已删除。
    _alternate_density(pages)

    # 预算上限只约束 **Skill 判断产生的**出图；作者逐页显式声明（asset: required /
    # asset_subject）永不被预算截断——执行策略吃掉契约声明是优先级倒置
    # （Declaration Priority：显式声明 > Skill 判断 > 兜底，预算属于执行器）。
    needed = [p for p in pages if p["asset"]["decision"] == "required"]
    declared = [p["id"] for p in needed if p["asset"].get("author_declared")]
    judged = [p["id"] for p in needed if not p["asset"].get("author_declared")]
    reused = [p["id"] for p in pages if p["asset"]["decision"] == "reuse"]
    cap = 2 if quality == "fast" else 4
    generate = declared + judged[:cap]
    assets = {"generate": generate, "generate_extra": judged[cap:], "reuse": reused,
              "skipped": [p["id"] for p in pages if p["asset"]["decision"] == "none"]}
    assets["planned_calls"] = len(generate)
    exec_mode = recommend_mode(brief)
    # V3：P1 就召回 Design DNA（经验线并行，不串行等待）。可选智能层失败可以降级，
    # 但必须留在 plan.warnings，不能把异常伪装成「无 DNA/无媒体判断」。
    intelligence_warnings = []
    try:
        from design_intelligence import recall_dna
        dna_hit = recall_dna(brief)
    except Exception as exc:
        intelligence_warnings.append({"rule": "design_intelligence", "scope": "deck",
                                      "error": f"{type(exc).__name__}: {exc}"})
        dna_hit = {"matched": None, "confidence": 0.0, "dna": None,
                   "note": "design_intelligence 不可用，按主题种子起步；详见 warnings"}
    # 逐页 media_confidence/media_reason/quality_budget 全库零消费（媒体决策
    # 已由 plan.assets 闸门 + 每页 asset.decision 承担），已随意图镜像一并删除。
    # 跨页锚（deck 级事实）：成套 deck 才需要连续性装置，短 deck 不发锚——为两页做家具是浪费。
    # 眉标用家族词汇原文（全场统一），页码从第 2 页起（封面不编号）。
    # 两样落成元素后由 guard 的 deck_anchor 查：在不在、是不是同一个位置。
    if len(pages) >= 4:
        for idx, pg in enumerate(pages):
            fam = str(pg.get("page_family") or "")
            anchor = {"eyebrow": fam.replace("_", " ") or "PAGE"}
            if idx > 0:
                anchor["page_number"] = idx + 1
            pg["anchor"] = anchor
    seed = DIRECTION_PRESETS.get(direction, DIRECTION_PRESETS["quiet_minimal"]).get("theme_seed", {})
    # 色彩方向族的种子骨架：只映射四个确有语义的槽位（纸面 / 墨色 / 强调），
    # secondary 与 muted 仍取预设——那两槽要过可读性底线，族表里的 supporting
    # 是「面料色」不是「字色」，直接搬来会写出 3:1 以下的弱字。
    _fam = _color_family(direction) or {}
    if (_fam.get("seed") or {}):
        _sk = dict(_fam["seed"])
        _colors = dict(seed.get("colors") or {})
        for slot, key in (("background", "foundation"), ("surface", "foundation"),
                          ("ink", "information"), ("primary", "information"),
                          ("accent", "accent")):
            if _sk.get(key):
                _colors[slot] = _sk[key]
        seed = dict(seed)
        seed["colors"] = _colors
    # Color Intelligence 入口：品牌色一到，方向预设立即让位。「科技=蓝」这类
    # 方向→色值的模板映射在入口处被切断；派生色阶由 OKLab derive_tokens 从种子展开。
    seed = _seed_from_brand(seed, brief.get("brand_colors")
                            if isinstance(brief, dict) else None)
    plan_warnings = ([w for w in (direction_warning, quality_warning) if w]
                     + intelligence_warnings
                     + [{"rule": "unresolved_content", "scope": pg.get("id"),
                         "msg": "content 缺失：证据型页面不能由标题脑补数据/案例——"
                                "补真实证据，或改成纯排版观点页，或删掉这一页"}
                        for pg in pages if pg.get("content_missing")])
    intent_interpretation = _deck_intent_interpretation(
        brief, requested_direction, direction, quality_input, quality, pages,
        plan_warnings)
    return {
        "path": quality,
        "mode": MODE_LABEL[quality],
        "dna": dna_hit,
        "execution": {"recommended": exec_mode,
                      "modes": ["spec", "draft", "release"],
                      "note": ("深度由任务赢得：简单任务走 draft 即交付；"
                               "只有终版收口才需要 release 的全量证据与 Manifest。")},
        "design_direction": direction,
        "direction_input": requested_direction,
        "quality_level": quality,
        "quality_input": quality_input,
        "warnings": plan_warnings,
        "intent_interpretation": intent_interpretation,
        "theme": seed,      # 整副 deck 的主题种子：落进 spec.theme（可被作者覆盖）
        "direction_execution": _execution_with_brief_overrides(direction, brief),  # 介质/光照/图表手法（deck 级）
        "pages": pages,
        "assets": assets,
        "budget": {"max_asset_calls": len(assets["generate"]),
                   # ↑ 预算数字是执行器内部策略（cap 已在上面约束 Skill 判断项），
                   # 对作者显式声明不设限；契约文档（brief 模板）不出现这些数字。
                   "max_charts_per_page": 1,
                   "max_text_objects_per_page": 4},
    }


def _alternate_density(pages: list[dict]) -> None:
    """疏密曲线：相邻页 density 相同则后一页让位。

    只在**双方都没被作者声明**时生效；作者写了 density 的页面一个都不动——
    判断权在内容，不在规则。
    """
    if not pages:
        return
    nxt = {"sparse": "balanced", "balanced": "dense", "dense": "balanced"}

    def _free(pg: dict) -> bool:
        """作者显式声明的密度不参与自动节奏调整——判断权在内容，不在规则。"""
        return not pg.get("density_explicit")

    # 只用家族自身的密度建议把相邻页拉开；被作者声明的页面完全不动。
    # （曾经把首末页强制改成 sparse——那是规则替作者做设计。已删除。）
    for i, cur in enumerate(pages[1:], start=1):
        prev = pages[i - 1]
        if _free(cur) and _free(prev) and cur["density"] == prev["density"]:
            cur["density"] = nxt[cur["density"]]


# --------------------------------------------------------------------------
# CLI： python route.py brief.yml [--json]      或      python route.py --demo
# --------------------------------------------------------------------------
# 执行模式关键词（确定性 sniff；显式 brief.execution_mode 永远优先）
_RELEASE_HINTS = ("终版", "发布", "定稿", "release", "final", "publish")
_REVIEW_HINTS = ("确认", "审阅", "审查", "review", "方向确认")


def recommend_mode(brief: dict) -> str:
    """brief → draft | review | release。

    默认是 draft（创作链）：初稿/探索/多方案不该付发布级流水线的成本。
    只有 brief 明说要终版发布、或用户已确认方向时才升档。
    显式 brief.execution_mode 优先；关键词 sniff 只做兜底。
    """
    explicit = str((brief or {}).get("execution_mode") or "").strip().lower()
    if explicit in ("draft", "creative", "a"):
        return "draft"
    if explicit in ("review", "design_review", "b"):
        return "review"
    if explicit in ("release", "final", "c"):
        return "release"
    occasion = " ".join(str((brief or {}).get(k) or "")
                        for k in ("occasion", "subject", "brief", "purpose", "task"))
    low = occasion.lower()
    if any(h in low for h in _RELEASE_HINTS):
        return "release"
    if any(h in low for h in _REVIEW_HINTS):
        return "review"
    return "draft"


def deck_decision(brief: dict, plan: dict | None = None) -> dict:
    """Deck Decision Card：全 deck 判断一次，页面继承。

    生成速度的大头是「每页重新想」。这张卡把 deck 级判断（叙事弧线/方向/
    密度曲线/媒体政策/色彩行为/执行模式）一次固化，页面只做适配——
    意图用 design_intelligence.page_intent_skeleton 继承骨架后按内容覆写，
    页面拿到家族 + 叙事动作 + 意图骨架；构图由生成侧判断。
    纯确定性派生；卡上留的洞（visual_world / type_voice / 每页 insight）
    是内容级判断，仍是 Art Director 的职责。
    """
    plan = plan if plan is not None else plan_deck(brief)
    pages = plan.get("pages") or []
    n = len(pages)
    if n <= 3:
        arc = ["establish", "close"]
    elif n <= 6:
        arc = ["establish", "explain", "prove", "close"]
    elif n <= 10:
        arc = ["establish", "context", "explain", "prove", "recommend", "close"]
    else:
        arc = ["establish", "context", "explain", "explain", "prove", "prove",
               "recommend", "close"]
    density = [str(p.get("density") or "balanced") for p in pages]
    assets = plan.get("assets") or {}

    def _n(x):
        return len(x) if isinstance(x, (list, tuple, dict)) else 0

    return {
        "narrative_arc": arc,
        "visual": {"direction": plan.get("design_direction"),
                   "visual_world": None,      # 洞：一句话隐喻（材质/光影/空间）
                   "type_voice": None},       # 洞
        "composition": {"rule": "页面拿到家族与叙事动作；几何与构图由生成侧判断；"
                                "相邻页的变化要有内容理由（结构雷同由布局指纹风险点名）"},
        "media_policy": {"generate": _n(assets.get("generate")),
                         "reuse": _n(assets.get("reuse")),
                         "skipped": _n(assets.get("skipped"))},
        "color": {"brand_derived": bool((plan.get("theme") or {}).get("brand_derived")),
                  "behavior": "color_behavior 判断（非色值）；图表走 chart_palette 角色",
                  # 高级感 ≠ 低饱和默认：品牌没给色时，种子只是执行起点，
                  # 饱和人格是内容情绪要回答的洞——不允许把 quiet 隐式当「高级」。
                  "saturation_regime": ("brand_derived"
                                        if (plan.get("theme") or {}).get("brand_derived")
                                        else "undecided: quiet 只是种子起点，"
                                             "饱和人格按内容情绪/行业语境判断")},
        # 整体统一契约：统一的是世界，可不同的是页面。把「必须统一」写进
        # deck 卡，生成侧拿到的就不只是「可推翻」，还有「必须一致」。
        "unity": {"same_world": ["材质与光的逻辑", "排版声音", "锚点词汇",
                                 "图表性格", "色彩层级纪律"],
                  "may_differ": ["构图", "密度", "色重", "图片比例",
                                 "标题位置", "页面结构"],
                  "rule": "不同页面拥有不同的视觉表达，但仍属于同一个完整的视觉世界"},
        "execution": plan.get("execution"),
        "theme": plan.get("theme"),
        "slots": ["visual_world", "type_voice", "饱和人格（color_behavior）",
                  "每页 insight / focus"],
        "note": "卡是判断的锚点不是答案：页面意图用 page_intent_skeleton 继承后再按内容覆写",
    }






def one_pass_plan(brief: dict, plan: dict | None = None) -> dict:
    """Fast Visual Intelligence Pipeline · Stage 1+2 一次调用固化。

    plan 可由统一入口预先计算；传入后本函数不会再次调用 plan_deck，避免
    intent_compiler / route / forecast 在同一轮重复推导。

    返回 {plan, deck_decision, color_plan, pages:[{family, skeleton, move,
    media, budget}]}。生成侧拿到的是**判断线索**（家族、意图骨架、叙事动作、
    媒体闸门），不是预置坐标——几何与构图归生成侧的设计判断。
    """
    import design_intelligence as di
    plan = plan if plan is not None else plan_deck(brief)
    card = deck_decision(brief, plan=plan)
    color = di.color_plan(plan.get("design_direction"), brief)
    pages = []
    plan_pages = plan.get("pages") or []
    for idx, pg in enumerate(plan_pages):
        fam = pg.get("page_family") or ""
        intent = {"page_intent": {"page_family": fam, "density": pg.get("density")}}
        # 节奏位由位置决定（开篇/主体/收束），密度与能量由路由表决定——
        # 两者都来自 route，避免骨架自己再推一遍值。
        stage = ("opening" if idx == 0 else
                 "closing" if idx == len(plan_pages) - 1 else "body")
        composition = ({"family": fam, "grammar": pg["composition_explicit"],
                        "intent": "作者显式声明的构图语法", "alternatives": []}
                       if pg.get("composition_explicit")
                       else di.composition_move(fam, str(pg.get("density") or ""),
                                                str(pg.get("energy") or ""),
                                                str(pg.get("content_type") or "")))
        pages.append({
            # 身份随事实一起传下去：顶层意图页与 plan.pages 用同一个 id 配对，
            # 消费侧（骨架合并 / 资产生成）靠它对齐，不靠位置。
            "id": pg.get("id"),
            "family": fam,
            "skeleton": di.page_intent_skeleton(
                fam or "", stage, density=pg.get("density"),
                energy=pg.get("energy"),
                empty_space_role=pg.get("empty_space_role")),
            "move": di.page_move(fam or ""),
            "composition": composition,
            "media": di.media_decision(intent),
            "budget": di.quality_budget(intent),
        })
    forecast = None
    try:
        forecast = di.forecast_risk(brief, plan=plan)
    except Exception as exc:
        forecast = {"error": str(exc), "policies": {}}
    return {"plan": plan, "deck_decision": card, "color_plan": color,
            "forecast": forecast, "pages": pages}


def align_pages(plan_pages: list[dict], other_pages: list[dict]) -> dict:
    """两份页事实按 id 对齐（错配不静默）。

    `plan.pages`（路由事实）、`one_pass_plan` 顶层 pages（意图事实）、brief 的
    slides 三份都由同一次 route 产出，id 一一对应。位置配对只在 id 不可用时
    兜底：外部传入的 plan.json、手工改过页序的 bundle 都会在这里留下
    `mismatch=True`，由调用方决定报错还是告警——**不允许悄悄把 A 页的骨架
    接到 B 页的内容上**。

    返回 {pairs: [(plan_page, other_page)], by: "id"|"index", pages,
    other_pages, mismatch}；pairs 顺序 = plan_pages 顺序。
    """
    by_id: dict[str, dict] = {}
    for pg in other_pages:
        pid = pg.get("id") if isinstance(pg, dict) else None
        if isinstance(pid, str) and pid:
            by_id[pid] = pg
    pairs: list[tuple[dict, dict]] = []
    mismatch = len(plan_pages) != len(other_pages)
    for i, pg in enumerate(plan_pages):
        pid = pg.get("id") if isinstance(pg, dict) else None
        mate = by_id.pop(pid, None) if isinstance(pid, str) and pid else None
        if mate is None:
            mate = other_pages[i] if i < len(other_pages) else {}
            mismatch = True
        pairs.append((pg, mate))
    if by_id:                       # 对面有页没被认领：集合不一致
        mismatch = True
    return {"pairs": pairs, "by": "index" if mismatch else "id",
            "pages": len(plan_pages), "other_pages": len(other_pages),
            "mismatch": mismatch}
