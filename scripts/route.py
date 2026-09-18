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
# 路由表：content_type → 页面家族 / 密度 / 能量 / 素材策略 / 字阶
#   asset: required 必须出图 · optional 视质量等级 · none 禁止出图（省时间、省 token）
#   density 与渲染占用率目标同向（sparse .30 / balanced .55 / dense .75）
# ─────────────────────────────────────────────────────────────
ROUTES: dict[str, dict] = {
    "cover":        dict(family="COVER", density="sparse", energy="high",
                         asset="required", asset_function="hero", type_scale=(64, 20, 12),
                         media=1, texts=4, empty_space="hold_emotion"),
    "brand_story":  dict(family="EDITORIAL", density="sparse", energy="medium",
                         asset="required", asset_function="emotion", type_scale=(48, 20, 12),
                         media=1, texts=4, empty_space="hold_emotion"),
    "product":      dict(family="HERO", density="balanced", energy="high",
                         asset="required", asset_function="hero", type_scale=(52, 18, 12),
                         media=1, texts=4, empty_space="protect_focus"),
    "case":         dict(family="CASE_STUDY", density="balanced", energy="medium",
                         asset="optional", asset_function="proof", type_scale=(44, 18, 12),
                         media=2, texts=4, empty_space="create_authority"),
    "statement":    dict(family="MINIMAL_STATEMENT", density="sparse", energy="low",
                         asset="optional", asset_function="emotion",
                         type_scale=(56, 20, 12), media=1, texts=4, empty_space="hold_emotion"),
    "closing":      dict(family="MINIMAL_STATEMENT", density="sparse", energy="medium",
                         asset="optional", asset_function="emotion",
                         type_scale=(56, 20, 12), media=1, texts=4, empty_space="hold_emotion"),
    "business":     dict(family="EXECUTIVE_SUMMARY", density="balanced", energy="medium",
                         asset="none", asset_function=None, type_scale=(44, 18, 12),
                         media=1, texts=4, empty_space="create_authority"),
    "agenda":       dict(family="EXECUTIVE_SUMMARY", density="balanced", energy="low",
                         asset="none", asset_function=None, type_scale=(40, 18, 12),
                         media=1, texts=5, empty_space="separate_chapter"),
    "data":         dict(family="DATA_STORY", density="balanced", energy="low",
                         asset="none", asset_function=None, type_scale=(44, 18, 12),
                         media=1, texts=4, empty_space="protect_focus"),
    "comparison":   dict(family="COMPARISON", density="balanced", energy="low",
                         asset="none", asset_function=None, type_scale=(44, 18, 12),
                         media=1, texts=4, empty_space="protect_focus"),
    "timeline":     dict(family="TIMELINE", density="balanced", energy="medium",
                         asset="none", asset_function=None, type_scale=(44, 18, 12),
                         media=1, texts=4, empty_space="separate_chapter"),
    "architecture": dict(family="FRAMEWORK", density="balanced", energy="medium",
                         asset="optional", asset_function="context",
                         type_scale=(48, 20, 12), media=1, texts=4,
                         empty_space="separate_chapter"),
    "process":      dict(family="NARRATIVE", density="balanced", energy="medium",
                         asset="none", asset_function=None, type_scale=(44, 18, 12),
                         media=1, texts=4, empty_space="separate_chapter"),
}
DEFAULT_ROUTE = ROUTES["business"]

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


def _alternative_route_key(item) -> str | None:
    """作者写的是英文家族名但表里没有时的兜底提示（不改写，只用于留痕）。"""
    if not isinstance(item, dict):
        return None
    raw = item.get("family") or item.get("type")
    return str(raw).strip() if _intent_value(raw) else None


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

# 证据类家族：这些页的主张靠证据支撑，按页序给 Fig. 编号（KPI 大数字是数字，不是图）。
FIGURE_FAMILIES = ("DATA_STORY", "COMPARISON", "CASE_STUDY", "TIMELINE")

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


def _canonical_direction(value) -> tuple[str, dict | None]:
    raw = str(value or "").strip()
    if not raw:
        return "quiet_minimal", None
    if raw in DIRECTION_PRESETS:
        return raw, None
    key = re.sub(r"\s+", " ", raw.lower().replace("×", " x ")).strip()
    if key in DIRECTION_ALIASES:
        return DIRECTION_ALIASES[key], None
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
        asset = "required" if quality == "advanced" else "none"
    if quality == "fast" and asset == "required" and r["asset_function"] in ("emotion",):
        asset = "reuse"          # 快速路径：复用已有画心，不再新出图
    statement, body, caption = r["type_scale"]
    if quality == "fast":        # 快速路径收一档尺度，降低构图与裁切复杂度
        statement = max(40, int(statement * 0.85) // 4 * 4)

    return {
        "content_type": content_type,
        "mode": MODE_LABEL[quality],
        "page_family": r["family"],
        "density": r["density"],
        "energy": r["energy"],
        "empty_space_role": r["empty_space"],
        "media_budget": r["media"],
        "text_budget": r["texts"],
        "type_scale": {"statement": statement, "body": body, "caption": caption},
        "asset": {"decision": asset, "function": r["asset_function"],
                  "why": _asset_reason(content_type, asset)},
        # 焦点恒为 Statement 级结论（≥ STATEMENT_SIZE 且尺度领先 1.25×）；
        # 元素 id 由生成侧决定，这里只给尺度关系，不给坐标、不给命名模板。
        "focus": "statement",
    }


def _asset_reason(ctype: str, decision: str) -> str:
    if decision in ("required", "reuse"):
        return f"{ctype} 承担空间/情绪/实证职责，画心是内容的一部分"
    if decision == "none":
        return f"{ctype} 的注意力预算属于数据与结论，出图会争夺第一注意点"
    return f"{ctype} 可视质量等级决定，advanced 才出图"


_DECK_CACHE: dict[str, dict] = {}
MAX_DECK_CACHE = 32   # 只缓存整副 deck 的规划结果；有界，不演化成配置系统


def _direction_execution(direction: str) -> dict:
    """方向 → 执行参数（deck 级事实，逐页复制没有意义）。

    这些词是介质/光照/图表手法的描述，不是模板：它们约束「用什么质感说话」，
    不规定元素放在哪里。几何与构图永远归生成侧的设计判断。
    """
    d = DIRECTION_PRESETS.get(direction, DIRECTION_PRESETS["quiet_minimal"])
    return {
        "background": d["background"],
        "material": d["material"],
        "light": d["light"],
        "chart_style": d["chart"],
        "motion": d["motion"],
        "composition_grammar": "soft_asymmetry" if d["asym"] else "evidence_field",
    }


def _seed_from_brand(preset: dict, brand: dict | None) -> dict:
    """品牌色优先：brief.brand_colors（{token: #HEX}）覆盖方向预设色板。

    方向预设只保留结构与未覆盖的灰阶骨架；主色/accent/secondary 一旦品牌给出
    立即让位。只接受 #HEX 值（防把 token 名当色值写）；空 brand 原样返回。
    """
    if not isinstance(brand, dict) or not brand:
        return preset
    valid = {str(k).strip(): str(v).strip() for k, v in brand.items()
             if isinstance(v, str) and str(v).strip().startswith("#")
             and len(v.strip()) in (4, 7)}
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


_PAGE_INTENT_FIELDS = (
    "type", "family", "title", "content", "insight", "focus", "page_family",
    "content_type", "density", "energy", "empty_space_role", "narrative_role",
    "asset", "asset_function", "media", "reading_order",
)


def _page_intent_interpretation(item, text: str, explicit_type, page_plan: dict) -> dict:
    """保留页面意图的来源：显式输入、路由推断，以及两者的可见冲突。"""
    explicit = {}
    if isinstance(item, dict):
        explicit = {k: item.get(k) for k in _PAGE_INTENT_FIELDS
                    if k in item and _intent_value(item.get(k))}
    inferred = {
        "content_type": {"value": page_plan.get("content_type"),
                          "basis": "explicit declaration" if _intent_value(explicit_type)
                                   else "keyword detection"},
        "page_family": {"value": page_plan.get("page_family"), "basis": "content_type route"},
        "density": {"value": page_plan.get("density"), "basis": "content_type route"},
        "energy": {"value": page_plan.get("energy"), "basis": "content_type route"},
        "asset": {"value": (page_plan.get("asset") or {}).get("decision"),
                  "basis": "quality and content route"},
    }
    conflicts = []
    keyword_type = detect_type(text)
    if explicit_type and explicit_type != keyword_type:
        conflicts.append({"field": "content_type", "explicit": explicit_type,
                          "keyword_signal": keyword_type,
                          "reason": "关键词与显式声明不一致；显式声明生效（Content > Template），仅留痕"})
    for field in ("density", "energy", "empty_space_role"):
        if field in explicit and str(explicit[field]) != str(page_plan.get(field)):
            conflicts.append({"field": field, "explicit": explicit[field],
                              "inferred": page_plan.get(field),
                              "reason": "显式声明生效；推断值仅记录，不改写作者判断"})
    return {"explicit": explicit, "inferred": inferred, "conflicts": conflicts}


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
            if _intent_value(item.get("composition")):
                page["composition_explicit"] = str(item["composition"]).strip()
        page["index"] = i + 1
        page["id"] = (item.get("id") if isinstance(item, dict) and item.get("id")
                      else f"s{i + 1:02d}")
        page["declared_type"] = declared_type
        page["intent_interpretation"] = _page_intent_interpretation(
            item, text, declared_type, page)
        pages.append(page)
    _alternate_density(pages)
    for pg in pages:
        inferred = (pg.get("intent_interpretation") or {}).get("inferred") or {}
        if "density" in inferred:
            inferred["density"]["value"] = pg.get("density")
            inferred["density"]["basis"] = (
                "explicit declaration" if pg.get("density_explicit")
                else "content_type route + deck rhythm pass")

    needed = [p["id"] for p in pages if p["asset"]["decision"] in ("required",)]
    reused = [p["id"] for p in pages if p["asset"]["decision"] == "reuse"]
    cap = 2 if quality == "fast" else 4
    assets = {"generate": needed[:cap], "generate_extra": needed[cap:], "reuse": reused,
              "skipped": [p["id"] for p in pages if p["asset"]["decision"] == "none"]}
    assets["planned_calls"] = len(assets["generate"])
    exec_mode = recommend_mode(brief)
    # V3：P1 就召回 Design DNA（经验线并行，不串行等待）。可选智能层失败可以降级，
    # 但必须留在 plan.warnings，不能把异常伪装成「无 DNA/无媒体判断」。
    intelligence_warnings = []
    try:
        from design_intelligence import recall_dna, media_decision, quality_budget
        dna_hit = recall_dna(brief)
    except Exception as exc:
        intelligence_warnings.append({"rule": "design_intelligence", "scope": "deck",
                                      "error": f"{type(exc).__name__}: {exc}"})
        dna_hit = {"matched": None, "confidence": 0.0, "dna": None,
                   "note": "design_intelligence 不可用，按主题种子起步；详见 warnings"}
    for pg in pages:
        # 媒体判断：置信度 + 理由（闸门管预算，模型管判断）
        try:
            md = media_decision({"page_intent": {"page_family": pg.get("page_family"),
                                                 "density": pg.get("density")}})
            pg["media_confidence"] = md["confidence"]
            pg["media_reason"] = md["reason"]
            pg["quality_budget"] = quality_budget(
                {"page_intent": {"page_family": pg.get("page_family"),
                                 "density": pg.get("density")}})
        except Exception as exc:
            intelligence_warnings.append({
                "rule": "design_intelligence", "scope": pg.get("id"),
                "error": f"{type(exc).__name__}: {exc}"})
    # 跨页锚（deck 级事实）：成套 deck 才需要连续性装置，短 deck 不发锚——为两页做家具是浪费。
    # 眉标用家族词汇原文（全场统一），页码从第 2 页起（封面不编号），证据编号只给证据类页。
    # 这三样落成元素后由 guard 的 deck_anchor 查：在不在、是不是同一个位置、编号连不连续。
    if len(pages) >= 4:
        fig_no = 0
        for idx, pg in enumerate(pages):
            fam = str(pg.get("page_family") or "")
            anchor = {"eyebrow": fam.replace("_", " ") or "PAGE"}
            if idx > 0:
                anchor["page_number"] = idx + 1
            if fam in FIGURE_FAMILIES:
                fig_no += 1
                anchor["figure"] = f"Fig. {fig_no:02d}"
            pg["anchor"] = anchor
    seed = DIRECTION_PRESETS.get(direction, DIRECTION_PRESETS["quiet_minimal"]).get("theme_seed", {})
    # Color Intelligence 入口：品牌色一到，方向预设立即让位。「科技=蓝」这类
    # 方向→色值的模板映射在入口处被切断；派生色阶由 OKLab derive_tokens 从种子展开。
    seed = _seed_from_brand(seed, brief.get("brand_colors")
                            if isinstance(brief, dict) else None)
    plan_warnings = ([w for w in (direction_warning, quality_warning) if w]
                     + intelligence_warnings)
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
        "direction_execution": _direction_execution(direction),  # 介质/光照/图表手法（deck 级）
        "pages": pages,
        "assets": assets,
        "budget": {"max_asset_calls": cap,
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
    from collections import Counter
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
                                "相邻页至少换一个构图算子"},
        "density_curve": density,
        "density_profile": dict(sorted(Counter(density).items())),
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
            "forecast": forecast, "pages": pages,
            "policy": (forecast or {}).get("policies") or {}}


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
