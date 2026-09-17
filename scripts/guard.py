# -*- coding: utf-8 -*-
"""
Layer 0.5 · Guard（静态治理层）

职责：**工程正确性的静态层**——回答「这份 PPT 能不能正确交付」的前半段。
  error（阻断）：数据合同、结构合法性、文本溢出、越界、未声明遮挡、来源区冲突
  warn / hint（只提醒，不阻断）：网格贴合、Accent 面积、行长、圆角容器密度、
        跨页节奏——这些是「设计契约」，过度自动化会把创造力关进规则里，
        因此只作提醒；判断叙事归 references/design-craft，生成前策略归 design_intelligence。
本层是只读的：不修改 spec、不生成任何元素，也不打分——
只返回「检查结果」，供 Release Gate 回答一个问题：这份 PPT 能不能交付。

设计原则（与引擎一致）：
  - 纯函数，不持有主题，不写死参数；所有阈值由调用方经 `rules` 传入。
  - 检查的是「调用方声明的设计」是否违反 OS 的确定性规则，
    不做审美判断、不替调用方做设计决策。
  - 引擎不做设计决策：guard 只报告，由调用方决定是否整改。

依赖方向：primitives ← guard ← compiler / qa
本层不反向依赖任何上层，可独立演进。
"""
from __future__ import annotations

import math
import copy
import re
from typing import Any

from primitives import (AUX_TEXT_ROLES, DEFAULT_WIDTH, DEFAULT_HEIGHT, GRID_UNIT,
                        ELEMENT_TYPES, CHART_KINDS,
                          contrast, bg_coverage, bg_overlay_opacity, is_background_declared,
                         spec_fingerprint)
from design_intelligence_rules import (FAMILY_MOVES, FAMILY_ALIASES, MEDIA_MODEL, DENSITY_BANDS,
                                       EMPTY_SPACE_ROLES, ENERGY_LEVELS)

# 网格基准（OS §02.1：间距基准 8 / 12 列栅格 / 基线 8，所有主题共享）
GRID = GRID_UNIT   # 基线网格唯一来源：primitives.GRID_UNIT（normalizer/文档同源）

# ── 设计契约 = 观察，不扣分、不阻断────────────────────────────────
# Guard 是 PPT 的 compiler linter：它只回答「这份 spec 是不是合法、数据是不是真的、
# 文件能不能渲染、内容有没有被切掉」。「高级感」不在它的管辖范围——那属于
# Design Intelligence（设计价值维度的基元常量住 primitives）。
# 下面这些规则名保留在这里，只是为了让 Critic 与风险预测更快定位证据（同一份事实
# 不重算第二次），它们**不构成任何门槛**；阈值是参考刻度，
# 不是及格线。新增判断请先问一句：它能被一个固定阈值完全描述吗？
# 能 → 那是工程约束，放这里；不能 → 那是设计判断，去 design-craft.md + Critic 证据。
DESIGN_RULES = frozenset({
    "accent_budget", "alignment_budget", "animation_budget", "chart_highlight",
    "color_budget", "decoration_budget", "focus", "focus_scale", "icon_consistency",
    "organic_layer", "palette_discipline", "rhythm", "type_budget",
    "typography", "asset_contract", "chart_style_drift",
})

# 图表容量上限（OS §19 / USAGE §5.4）
NUMERIC_CHART_KINDS = {
    "bar", "horizontal_bar", "column", "comparison_bar", "line", "trend",
    "single_trend_line", "area", "donut", "donut_composition", "pie",
    "waterfall", "ranked_bar", "progress_bar", "stacked_bar", "bubble",
    # Metric displays still carry data semantics: finite values and provenance
    # apply even when the visual is shape/text rather than a native chart.
    "big_number_row", "sparkline",
}

CHART_LIMITS = {

    "kpi": 1, "executive_kpi": 1, "big_number": 1, "big_number_row": 5,
    "bar": 8, "horizontal_bar": 8, "column": 8, "comparison_bar": 8,
    "line": 8, "trend": 8, "single_trend_line": 8,
    "area": 8, "donut": 8, "donut_composition": 8, "pie": 8,
    "process_flow": 7, "timeline": 7, "steps": 6,
    "matrix": 12, "waterfall": 12, "architecture": 3, "bubble": 12,
    "ranked_bar": 8, "progress_bar": 6, "stacked_bar": 8, "sparkline": 12,
}
# 与 compiler 的原生/形状图表分发保持同一 schema 边界；未知 kind
# 先在 Guard 阻断，避免编译器只警告后留下半成品 PPTX。
SUPPORTED_CHART_KINDS = CHART_KINDS

# 载荷契约：schema 合法 ≠ 画得出来。缺载荷的图表会「PASS 出门、页面空白」，
# 这是最贵的漏洞——看起来做完了，其实什么都没画。这里只守「有没有东西可画」，
# 不管画得好不好（那是设计判断）。
ROWS_CHART_KINDS = (
    "bar", "horizontal_bar", "column", "comparison_bar", "line", "trend",
    "single_trend_line", "area", "donut", "donut_composition", "pie", "waterfall",
    "ranked_bar", "progress_bar", "stacked_bar", "sparkline", "big_number_row",
    "process_flow", "timeline", "steps", "bubble",
)
ELEMENT_METRIC_KINDS = ("kpi", "executive_kpi", "big_number")


def _is_grid_aligned(value: float) -> int:
    """到最近 8 倍数网格的偏差（0–4）。"""
    return int(round(abs(value - GRID * round(value / GRID))))


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x2E80 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF
            or 0xFF00 <= o <= 0xFF60 or 0x3000 <= o <= 0x303F)


# 行长上限住 primitives（单一口径的物理载体）。
_LINE_MEASURE_FALLBACK = {"LINE_MEASURE_CJK_MAX": 38, "LINE_MEASURE_LATIN_MAX": 75,
                          "LINE_MEASURE_FAIL_FACTOR": 2.0}
MEASURE_EXEMPT_ROLES = frozenset(AUX_TEXT_ROLES)   # 真源在 primitives（见其注释）


def _measure_limits() -> dict:
    """行长阈值，与 _bg_gate 同源同法。"""
    return _cached_gate("lm", _LINE_MEASURE_FALLBACK)


def line_measure(e: dict, limits: dict) -> dict | None:
    """声明排版 → 每行字数与上限。返回 None 表示不适用（非文字/太小/来源级角色）。

    行长用「盒宽可容纳的字数」与「声明换行的最长一行」取小：前者是潜在行长，
    后者是实际行数，两者都短才安全——这仍是纯静态判定，不依赖渲染。
    """
    if str(e.get("type", "text")) != "text" or str(e.get("role", "")) in MEASURE_EXEMPT_ROLES:
        return None
    try:
        fs, bw = float(e.get("size") or 0), float(e.get("width") or 0)
    except (TypeError, ValueError):
        return None
    if fs < 8 or bw < 32:
        return None
    txt = str(e.get("text") or "")
    if not txt.strip():
        return None
    cjk = sum(1 for c in txt if _is_cjk(c))
    latin = len(txt) - cjk
    is_cjk_led = cjk >= max(4, latin // 2)
    # CJK 等宽：1 字 ≈ 1 em；拉丁按 0.5 em 估（混合文本偏保守）
    cap = bw / fs * (1.0 if is_cjk_led else 2.0)
    longest = max((len(ln.strip()) for ln in txt.split("\n")), default=0)
    per_line = min(longest, cap) if longest else 0.0
    limit = limits["LINE_MEASURE_CJK_MAX"] if is_cjk_led else limits["LINE_MEASURE_LATIN_MAX"]
    return {"per_line": round(per_line, 1), "capacity": round(cap, 1), "limit": limit,
            "cjk_led": is_cjk_led,
            "over": per_line > limit, "fatal": per_line > limit * limits["LINE_MEASURE_FAIL_FACTOR"]}


def _element_area(e: dict) -> float:
    try:
        return max(0.0, float(e.get("width", 0))) * max(0.0, float(e.get("height", 0)))
    except (TypeError, ValueError):
        return 0.0


# 零基长度编码：长度差就是读数的图。差异太小时，读者看到的是「一样长」。
ZERO_BASED_LENGTH_KINDS = frozenset({"bar", "column", "horizontal_bar",
                                     "comparison_bar", "ranked_bar"})
CHART_FLAT_RATIO = 1.25   # 最大/最小 < 此值 ⇒ 条长读起来一样


def _ink_union(rects: list[tuple[float, float, float, float]]) -> float:
    """矩形并集面积（扫描线，确定性）——留白率的唯一分子口径。

    用**元素框**而不是渲染像素：留白指「没有被元素框占住的空间」，框内空白由
    排版密度去管。像素级空白（文字之间那些）是另一个量，两个数不能互相换算，
    也不能拿来互相验证。
    """
    xs = sorted({v for r in rects for v in (r[0], r[2])})
    total = 0.0
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        if x1 <= x0:
            continue
        bands = sorted((r[1], r[3]) for r in rects if r[0] <= x0 and r[2] >= x1)
        if not bands:
            continue
        h = 0.0
        cs, ce = bands[0]
        for lo, hi in bands[1:]:
            if lo > ce:
                h += ce - cs
                cs, ce = lo, hi
            else:
                ce = max(ce, hi)
        h += ce - cs
        total += (x1 - x0) * h
    return total


def _element_rect(e: dict, cw: float, ch: float) -> tuple[float, float, float, float] | None:
    """元素框 → 画布内矩形；无几何/零面积返回 None。"""
    try:
        x, y = float(e.get("x", 0)), float(e.get("y", 0))
        w, h = float(e.get("width", 0)), float(e.get("height", 0))
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    r = (max(0.0, x), max(0.0, y), min(cw, x + w), min(ch, y + h))
    return r if r[2] > r[0] and r[3] > r[1] else None


def _density_class(slide: dict) -> tuple[str, float]:
    """借鉴 v6.2 classify_density 的确定性密度分类（仅用于节奏检查）。"""
    elems = [e for e in slide.get("elements", []) if isinstance(e, dict)]
    chars = sum(len(str(e.get("text", ""))) for e in elems if e.get("type") == "text")
    types = [str(e.get("type")) for e in elems]
    charts = sum(t in {"chart", "native_chart"} for t in types)
    images = types.count("image")
    n = len(elems)
    score = n * 6.5 + min(chars, 1200) / 48 + charts * 15 + images * 7
    if score < 26:
        return "sparse", score
    if score < 55:
        return "balanced", score
    if score < 84:
        return "dense", score
    return "overloaded", score


def _uses_role(value, role_name: str, theme: dict) -> bool:
    """判断元素取值（颜色/填充/描边）是否引用某个主题角色或等于其字面色。

    同时兼容三种写法：
      * 字符串：角色名或 #HEX；
      * Fill Contract：{"type":"solid","color":...} / {"type":"gradient","stops":[...]}；
      * 历史写法：{"color":...,"opacity":...} / {"gradient":{"stops":[...]}.
    """
    if value is None:
        return False
    if isinstance(value, dict):
        if value.get("type") == "solid":
            return _uses_role(value.get("color"), role_name, theme)
        if value.get("type") == "gradient":
            stops = value.get("stops") or []
            return any(_uses_role(
                item.get("color") if isinstance(item, dict) else
                (item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else None),
                role_name, theme) for item in stops)
        if value.get("type") == "none":
            return False
        if "gradient" in value:
            grad = value["gradient"] or {}
            stops = grad.get("stops", grad) if isinstance(grad, dict) else grad
            return any(_uses_role(item[1], role_name, theme)
                       for item in stops if isinstance(item, (list, tuple)) and len(item) > 1)
        if "color" in value:
            return _uses_role(value.get("color"), role_name, theme)
        return False
    if not isinstance(value, str):
        return False
    if value == role_name:
        return True
    colors = theme.get("colors", {}) or {}
    target = colors.get(role_name)
    return bool(target and isinstance(target, str) and value.upper() == target.upper())


def _inside_zone(e: dict, zone: dict) -> bool:
    try:
        ex, ey = float(e.get("x", 0)), float(e.get("y", 0))
        ew, eh = float(e.get("width", 0)), float(e.get("height", 0))
        zx, zy = float(zone.get("x", 0)), float(zone.get("y", 0))
        zw, zh = float(zone.get("width", 0)), float(zone.get("height", 0))
        return ex >= zx and ey >= zy and ex + ew <= zx + zw and ey + eh <= zy + zh
    except (TypeError, ValueError, OverflowError):
        return False


def _intersects_zone(e: dict, zone: dict) -> bool:
    """Any positive-area collision, not only full containment."""
    try:
        ex, ey = float(e.get("x", 0)), float(e.get("y", 0))
        ew, eh = float(e.get("width", 0)), float(e.get("height", 0))
        zx, zy = float(zone.get("x", 0)), float(zone.get("y", 0))
        zw, zh = float(zone.get("width", 0)), float(zone.get("height", 0))
        return (ew > 0 and eh > 0 and zw > 0 and zh > 0
                and ex < zx + zw and ex + ew > zx
                and ey < zy + zh and ey + eh > zy)
    except (TypeError, ValueError, OverflowError):
        return False



def _overlap_allowed(a: dict, b: dict) -> bool:
    """Allow only an explicit, reasoned visual overlap; protected content never yields."""
    if a.get("allow_overlap") is not True or b.get("allow_overlap") is not True:
        return False
    if not str(a.get("overlap_reason", "")).strip() or not str(b.get("overlap_reason", "")).strip():
        return False
    protected = {"source", "method", "annotation", "axis", "label", "data_label", "legend", "metadata", "conclusion", "headline"}
    return not ({str(a.get("role", "")), str(b.get("role", ""))} & protected)


def _check_page_contract(slide: dict, sid: str, add,
                         canvas_width: float = DEFAULT_WIDTH,
                         canvas_height: float = DEFAULT_HEIGHT) -> None:
    """Validate declared page intent without inventing missing design decisions.

    契约字段位于 `page_intent`（见 production-contract.md Spec minimum）；
    兼容历史写法：字段直接挂在 slide 顶层时同样接受。
    """
    intent = slide.get("page_intent") if isinstance(slide.get("page_intent"), dict) else {}

    def field(key):
        return intent.get(key) or slide.get(key)

    for key in ("page_family", "empty_space_role", "energy"):
        if not field(key):
            add("page_contract", sid, "hint", f"缺少页面契约字段 {key}（建议声明以便可验证）")

    # 值校验：字段写了但值不存在 = 该页判断静默失效（家族 → 媒体/叙事动作/构图全回落；
    # 留白职责 → 免检与锚点判断失效；能量/密度 → 节奏判断失效）。点名到合法值，但不阻断——
    # 工程事实是「这个值引擎不认识」，不是「这页不合格」。
    known_families = set(FAMILY_MOVES) | set(MEDIA_MODEL) | set(FAMILY_ALIASES)
    for key, legal, shown in (
            ("page_family", known_families, " / ".join(sorted(FAMILY_MOVES))),
            ("empty_space_role", set(EMPTY_SPACE_ROLES), " / ".join(EMPTY_SPACE_ROLES)),
            ("energy", set(ENERGY_LEVELS), " / ".join(ENERGY_LEVELS)),
            ("density", set(DENSITY_BANDS), " / ".join(DENSITY_BANDS))):
        value = field(key)
        if not value:
            continue
        value = str(value).strip()
        if value not in legal:
            add("page_contract", sid, "warn",
                f"{key}={value!r} 不在合法取值内（{shown}）——本页会静默退回默认判断，"
                f"写入判断的值才会生效")
        elif key == "page_family" and value not in FAMILY_MOVES \
                and FAMILY_ALIASES.get(value, value) not in FAMILY_MOVES:
            # 媒体模型命名空间（DATA / STORY / CLOSING …）只供媒体与质量预算使用，
            # 没有叙事动作与构图起点——用它等于丢掉半个家族判断，必须点名而不是静默兜底。
            add("page_contract", sid, "warn",
                f"page_family={value!r} 只有媒体/预算判断，叙事动作与构图起点会退回兜底；"
                f"route 家族才有完整判断：{' / '.join(sorted(FAMILY_MOVES))}")
    source_zone = slide.get("source_zone")
    if source_zone is not None:
        if not isinstance(source_zone, dict):
            add("source_zone", sid, "error", "source_zone 必须是包含 x/y/width/height 的对象")
        else:
            try:
                _raw_zone = [source_zone["x"], source_zone["y"],
                             source_zone["width"], source_zone["height"]]
                if any(isinstance(v, bool) for v in _raw_zone):
                    raise ValueError
                zx, zy, zw, zh = (float(v) for v in _raw_zone)
                if not all(math.isfinite(v) for v in (zx, zy, zw, zh)):
                    raise ValueError
                if zw <= 0 or zh <= 0:
                    raise ValueError
                if zx < 0 or zy < 0 or zx + zw > canvas_width + 1 or zy + zh > canvas_height + 1:
                    add("source_zone", sid, "error", "source_zone 必须完整落在默认画布范围内")
            except (KeyError, TypeError, ValueError, OverflowError):
                add("source_zone", sid, "error", "source_zone 必须包含有效的 x/y/width/height 数值")
    elements = slide.get("elements") if isinstance(slide.get("elements"), list) else []
    ids = [str(e.get("id")) for e in elements if isinstance(e, dict) and e.get("id") is not None]
    seen_ids = set()
    duplicate_ids = []
    for _id in ids:
        if _id in seen_ids and _id not in duplicate_ids:
            duplicate_ids.append(_id)
        seen_ids.add(_id)
    if duplicate_ids:
        add("element_schema", sid, "error",
            f"元素 id 必须唯一；重复 id={duplicate_ids!r}")
    focus = field("focus") or slide.get("focus_subject_id")
    if isinstance(focus, (list, tuple, set, dict)):
        add("focus_contract", sid, "error",
            f"focus 必须是单一元素 id；收到 {type(focus).__name__}（多焦点请显式改用 secondary_focus）")
    elif focus:
        focus_matches = [e for e in elements if isinstance(e, dict)
                         and str(e.get("id")) == str(focus)]
        if not focus_matches:
            add("focus_contract", sid, "warn", f"focus={focus!r} 未对应页面元素")
        elif len(focus_matches) != 1:
            add("focus_contract", sid, "error",
                f"focus={focus!r} 必须唯一；当前匹配 {len(focus_matches)} 个元素")
    elif elements:
        add("focus", sid, "hint", "未声明 focus；无法验证唯一视觉主锚点")


# ══════════════════════════════════════════════════════════════
# Preflight（静态预检）：把 primitives 中**确定性的**结构判据前移到静态治理层
#
# 目的：让「焦点尺度、文本/媒体预算、重心失衡、卡片墙、节奏趋平」这些问题
# 在编译与渲染之前就被点名，避免用 3–6 轮渲染去试出同一件事。
# 阈值住在 primitives（单一口径，v4.15 直连，不再有懒读取回落双态）。
# 预检条目为 hint 级：不改变 guard/QA 的通过判定，只提供可执行的最小修正。
# ══════════════════════════════════════════════════════════════

def _is_bg_layer(e: dict) -> bool:
    """是否**声明**为背景层（只读意图，不判断资格）。判定在 primitives 共享。"""
    return is_background_declared(e)


# 声明 layer=background 即可免检，等于给任何内容图发一张免死金牌；资格判定要求它
# 真的「承载空间」并给出阅读保护。阈值住 primitives（单一口径）。
_BG_FALLBACK = {"BG_MIN_COVERAGE": 0.60, "BG_MIN_PROTECT_OPACITY": 0.20}


_GATE_CACHE: dict = {}
_BG_GATE_CACHE: dict = {}


def _cached_gate(key: str, defaults: dict) -> dict:
    """阈值住 primitives（v4.15 直连）；按 key 缓存，互不污染。"""
    if key not in _GATE_CACHE:
        import primitives as pr
        th = dict(defaults)
        for k in th:
            v = getattr(pr, k, None)
            if v is not None:
                th[k] = v
        _GATE_CACHE[key] = th
    return dict(_GATE_CACHE[key])


def _bg_gate() -> dict:
    """背景层资格阈值（逐元素调用，只解析一次）。"""
    return _cached_gate("bg", _BG_FALLBACK)


def _bg_qualified(e: dict, cw: float, ch: float) -> tuple[bool, str | None]:
    """背景层免检资格：覆盖 ≥BG_MIN_COVERAGE 画布，且有真实保护层或显式免检声明。"""
    if not _is_bg_layer(e):
        return False, "未声明为背景层"
    th = _bg_gate()
    cover = bg_coverage(e, cw, ch)          # 覆盖率与保护层解析在 primitives 共享，
    if cover < th["BG_MIN_COVERAGE"]:       # 与 primitives 同一实现，不再各自算一遍
        return False, (f"仅覆盖画布 {cover:.0%}（<{th['BG_MIN_COVERAGE']:.0%}）："
                       f"这是内容对象，不是空间层")
    if e.get("readability_exempt"):
        return True, None
    op, why = bg_overlay_opacity(e)
    if op is None:
        if why == "unparsable":
            return False, "overlay 无法解析出 opacity"
        return False, "未声明 overlay/content_protection：叠加文字的可读性无保障"
    if op < th["BG_MIN_PROTECT_OPACITY"]:
        return False, (f"遮罩不透明度 {op:.2f} < {th['BG_MIN_PROTECT_OPACITY']:.2f}，"
                       f"形同虚设")
    return True, None


def _bg_exempt(e: dict, cw: float, ch: float) -> bool:
    """是否享受背景层豁免（声明 + 资格通过）。"""
    return _bg_qualified(e, cw, ch)[0]


# ══════════════════════════════════════════════════════════════
def _check_background_qualification(slide: dict, sid: str, cw: float, ch: float,
                                    add) -> None:
    """背景层资格判定（工程事实，非预测）：伪背景 error、无保护 warn。

    原住 run_preflight；预检层并入 risk_prediction 后，资格判定留在 guard 主链
    ——它是阻断性工程检查（BACKGROUND_DISGUISED/BG_UNPROTECTED），不是预测。
    """
    for e in (slide.get("elements") or []):
        if not isinstance(e, dict):
            continue
        if e.get("type") == "image" and _is_bg_layer(e):
            ok, why = _bg_qualified(e, cw, ch)
            if not ok:
                add("background_layer", f"{sid}:BACKGROUND_DISGUISED", "error",
                    f"「{e.get('id', '?')}」声明 layer=background 但不具备空间层资格：{why} "
                    f"→ 改回普通媒体（计入预算与遮挡），或真的整幅承载并叠加遮罩")
            elif not (e.get("content_protection") or e.get("overlay")):
                add("background_layer", f"{sid}:BG_UNPROTECTED", "warn",
                    "整幅背景图未声明 content_protection/overlay：文字叠加后对比不可控 "
                    "→ 为画心叠加低能量遮罩（solid #000000, opacity 0.35）或改用分幅画心")


# 色彩系统纪律（deck 级）：单页颜色数已经由 color_budget / theme_constraint 管住，
# 但「每一页都合规、合起来却不成系统」是 AI 组稿最常见的塌法：色相越铺越开、
# 强调色与主色同族所以强调不出来、两色渐变混成脏灰。这里只做三件能测的事。
# ══════════════════════════════════════════════════════════════

NEUTRAL_COLOR_ROLES = {"background", "surface", "panel", "panel_soft", "panel_strong",
                       "ink", "muted", "muted_soft", "hairline", "rule", "track", "faint",
                       "veil", "on_dark", "on_accent"}
HUE_BUCKET = 30.0            # 30° 一个色相族：同族内的深浅视为一套颜色
NEUTRAL_SAT = 0.06           # 低于此彩度不计色相族（纸色与灰阶不是颜料）


def _hls(hexv) -> tuple[float, float, float] | None:
    """#RRGGBB → (h°, l, s)；解析不了返回 None（宁可不判，也不猜）。"""
    s = str(hexv or "").strip().lstrip("#")
    if len(s) != 6:
        return None
    try:
        r, g, b = (int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    import colorsys
    h, l, sa = colorsys.rgb_to_hls(r, g, b)
    return h * 360.0, l, sa


# ---------------------------------------------------------------------------
# 标题语义检测（title_semantics）：拦截「字段名当标题」
# 设计哲学要求「标题写洞察，不写'市场分析''项目进展'等字段名」；但这是唯一一条
# 至今没有确定性检查拦截的哲学。字段名标题 = 短名词短语 + 字段名后缀、且不含
# 任何判断动词/比较词；命中时给 hint（不扣分，与预检同立场：提前告诉你会被 Art
# Critic 判「意图不清」，而不是替你重写）。
# ---------------------------------------------------------------------------
FIELD_NAME_SUFFIXES = (
    "分析", "概览", "总览", "概况", "现状", "情况", "说明", "简介", "介绍",
    "数据", "明细", "清单", "列表", "报告", "总结", "回顾", "展望", "规划",
    "目标", "指标", "结构", "对比", "趋势", "格局", "分布", "排名", "排行",
    "图谱", "框架", "模型", "流程", "历程", "沿革", "全景", "全貌", "画像",
)
# 判断词：出现任一，说明这行字已经是一个可复述的结论，不再是字段名
_INSIGHT_VERBS = (
    "是", "为", "达", "超", "涨", "降", "增", "减", "领先", "落后", "占比",
    "贡献", "驱动", "来自", "源于", "高于", "低于", "第一", "唯一", "突破",
    "收窄", "扩大", "转", "现", "成", "应", "需", "将", "已", "最", "更",
)


def _looks_like_field_name(text: str) -> bool:
    """判定一段标题/insight 是否退化成「字段名」。只做保守判定：宁漏勿错。"""
    t = (text or "").strip()
    if not t or len(t) > 8:            # 字段名很短；长句必然是结论
        return False
    if not t.endswith(FIELD_NAME_SUFFIXES):
        return False
    if any(v in t for v in _INSIGHT_VERBS):
        return False                   # 含判断词 → 已是结论
    return True


def _hue_gap(a, b) -> float | None:
    if not a or not b:
        return None
    d = abs(a[0] - b[0]) % 360.0
    return min(d, 360.0 - d)


def _hue_family(hexv) -> int | None:
    c = _hls(hexv)
    if not c or c[2] < NEUTRAL_SAT:
        return None
    return int(c[0] // HUE_BUCKET) % int(360 // HUE_BUCKET)


def _stop_color(stop):
    if isinstance(stop, dict):
        return stop.get("color")
    if isinstance(stop, (list, tuple)) and len(stop) > 1:
        return stop[1]
    return None


def _gradient_muck(fill) -> str | None:
    """两色渐变是否会「混出脏灰」：色相接近互补 + 两端彩度都居中。

    刻意不打击低对比的同族渐变（#F8F5EF→#EBE5D9 这类纸面呼吸是东方留白手法，
    不是脏）；只有互补混色才会让中段失去方向感。
    """
    if not isinstance(fill, dict):
        return None
    stops = fill.get("stops")
    if not isinstance(stops, (list, tuple)):
        g = fill.get("gradient")
        stops = g.get("stops") if isinstance(g, dict) else None
    if not isinstance(stops, (list, tuple)) or len(stops) < 2:
        return None
    c1, c2 = _hls(_stop_color(stops[0])), _hls(_stop_color(stops[-1]))
    if not c1 or not c2:
        return None
    gap = _hue_gap(c1, c2)
    if gap is None or not (150.0 <= gap <= 210.0):
        return None
    if not all(0.08 <= s <= 0.40 and 0.20 <= l <= 0.80 for _, l, s in (c1, c2)):
        return None
    return (f"两端 {_stop_color(stops[0])}↔{_stop_color(stops[-1])} 色相差 {gap:.0f}°"
            f"（互补）且彩度居中")


def _box(e: dict, text_ink_ratio: float = 1.0,
         text_ink_v: float = 1.0) -> tuple:
    try:
        x, y = float(e.get("x", 0)), float(e.get("y", 0))
        w, h = float(e.get("width", 0) or 0), float(e.get("height", 0) or 0)
    except (TypeError, ValueError):
        return (0.0, 0.0, 0.0, 0.0)
    if e.get("type") == "text":
        w *= float(text_ink_ratio)
        h *= float(text_ink_v)
    return (x, y, w, h)


def _geometry_occlusion(slide: dict):
    """文字框两两重叠检测：覆盖率超过 30% 即认定为遮挡。

    只查文字——图形/图片的有意叠压（画心、蒙版、色块衬底）是设计手法，
    文字压文字则一定是失误。返回 [(id_a, id_b, 覆盖率), ...]。
    """
    # 先把每个文本框的几何缓存下来；原实现每个 pair 都重复 _box，
    # 文字数量一多会把 O(n²) 的比较再乘上一层字典/float 解析成本。
    texts = []
    for e in (slide.get("elements") or []):
        if not isinstance(e, dict) or e.get("type") != "text":
            continue
        if not (e.get("text") or "").strip():
            continue
        x, y, w, h = _box(e)
        texts.append((e.get("id") or e.get("role") or "text", x, y, w, h))
    out = []
    for i, a in enumerate(texts):
        _, ax, ay, aw, ah = a
        for b in texts[i + 1:]:
            _, bx, by, bw, bh = b
            ox = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
            oy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
            inter = ox * oy
            if inter <= 0:
                continue
            smaller = min(aw * ah, bw * bh)
            if smaller <= 0:
                continue
            ratio = inter / smaller
            if ratio >= 0.30:
                out.append((a[0], b[0], ratio))
    return out


def _optical_pair_alignment(slide: dict):
    """小色块（图例块/圆点）与右侧紧贴文字必须垂直光学居中。

    真实案例：10px 图例块与 12px 文字各写各的 y，渲染后文字上浮、色块下沉，
    人眼立刻读作「没对齐」。柱条(h≤16)与端点读数同理。静态几何即可预防。"""
    out = []
    els = [e for e in slide.get("elements") or [] if isinstance(e, dict)]
    texts = [e for e in els if str(e.get("type", "text")) == "text"]
    for e in els:
        if e.get("type") != "shape" or \
                e.get("shape") not in ("rect", "rounded_rect", "oval"):
            continue
        try:
            w = float(e.get("width", 0)); h = float(e.get("height", 0))
            ex = float(e.get("x", 0)); ey = float(e.get("y", 0))
        except (TypeError, ValueError):
            continue
        if not (0 < min(w, h) <= 16):
            continue
        right, cy = ex + w, ey + h / 2
        for t in texts:
            try:
                tx = float(t.get("x", 0)); ty = float(t.get("y", 0))
                th = float(t.get("height", 0))
            except (TypeError, ValueError):
                continue
            # 同一行才算配对：水平紧贴 + 垂直范围相交，避免跨行误配
            if not (right <= tx <= right + 24):
                continue
            if not (ty < ey + h and ty + th > ey):
                continue
            # 编译器文本顶锚+autofit：光学中心按行高模型算，而非声明盒中心
            size = float(t.get("size", 12) or 12)
            lh = float(t.get("line_height", 1.4) or 1.4)
            single = (t.get("wrap") is False) or (t.get("max_lines") == 1)
            lines = 1.0 if single else max(1.0, round(th / (size * lh)) if size * lh else 1.0)
            delta = abs((ty + lines * size * lh / 2) - cy)
            out.append((e.get("id"), t.get("id"), delta, tx - right))
    return out


def _baseline_crossings(slide: dict):
    """柱体不得穿过基线：hairline 细线若落在某柱体内部（非底边），
    渲染即读作「柱底越过坐标线」。真实案例：尺寸吸附把柱底抬过基线。"""
    out = []
    els = [e for e in slide.get("elements") or [] if isinstance(e, dict)]
    rules = [e for e in els if e.get("type") == "shape"
             and float(e.get("height", 9)) <= 2 and float(e.get("width", 0)) > 50
             and e.get("fill") in ("hairline", "track")]
    bars = [e for e in els if e.get("type") == "shape"
            and e.get("shape") in ("rect", "rounded_rect")
            and float(e.get("height", 0)) > 24]
    for b in bars:
        bx, by = float(b.get("x", 0)), float(b.get("y", 0))
        bw, bh = float(b.get("width", 0)), float(b.get("height", 0))
        for r in rules:
            rx, ry = float(r.get("x", 0)), float(r.get("y", 0))
            rw = float(r.get("width", 0))
            if rx < bx + bw and rx + rw > bx and by + 1 < ry < by + bh - 1:
                # track 型细线本就是柱内轨道（成对条形），只有穿过底边附近才算病
                if r.get("fill") == "track" and ry < by + bh - 6:
                    continue
                out.append((b.get("id"), r.get("id"), ry - (by + bh)))
    return out


def _chart_values(chart: dict):
    """取图表里的全部数值（兼容 data 行与 series 两种写法）。"""
    vals = []
    for row in (chart.get("data") or []):
        if isinstance(row, dict) and isinstance(row.get("value"), (int, float)):
            vals.append(float(row["value"]))
    for srs in (chart.get("series") or []):
        if isinstance(srs, dict):
            for v in (srs.get("values") or []):
                if isinstance(v, (int, float)):
                    vals.append(float(v))
    return vals


def _data_claim_mismatch(slide: dict):
    """标题里的百分比，能否由本页图表数据推出？

    支持三种等价算法：直接等于某值、占总量百分比、占最大值百分比。
    任一命中即视为主张成立（不同图表的口径本就不同，不宜只认一种）。
    """
    import re
    charts = [e for e in (slide.get("elements") or [])
              if isinstance(e, dict) and e.get("type") in ("chart", "native_chart")]
    if not charts:
        return []
    texts = [e for e in (slide.get("elements") or [])
             if isinstance(e, dict) and e.get("type") == "text"
             and (e.get("text") or "").strip()]
    if not texts:
        return []
    # 主张句 = 字号最大的**句子**，不是最大的数字。
    # 反例：KPI 页里 44px 的「↓ 34%」比 40px 的标题还大，若按字号直接取，
    # 会把指标值当成主张去图表里找，凭空造出一条误报。故要求 ≥8 个字符。
    candidates = [e for e in texts if len(str(e.get("text") or "").strip()) >= 8]
    if not candidates:
        return []
    head = max(candidates, key=lambda e: float(e.get("size") or 0))
    head_txt = str(head.get("text") or "")
    claims = [float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s*%", head_txt)]
    if not claims:
        return []
    out = []
    for chart in charts:
        vals = _chart_values(chart)
        if not vals:
            continue
        total = sum(vals) or 1.0
        vmax = max(vals) or 1.0
        for n in claims:
            cands = [abs(v - n) for v in vals]
            cands += [abs(100.0 * v / total - n) for v in vals]
            cands += [abs(100.0 * v / vmax - n) for v in vals]
            best = min(cands)
            if best > 0.6:                     # 容差 0.6：容得下四舍五入
                nearest = min(
                    [100.0 * v / total for v in vals] +
                    [100.0 * v / vmax for v in vals] + list(vals),
                    key=lambda x: abs(x - n))
                out.append((chart.get("id") or "chart", f"{n:g}%", f"{nearest:.1f}"))
    return out


def _rule_num(rules: dict, key: str, default, cast=float):
    """rules 阈值容错读取：None/非数值/脏输入一律回落默认（不炸全链）——
    rules 来自主题约束或调用方生成物，没有资格让治理层崩溃。"""
    v = rules.get(key, default)
    if v is None:
        return default
    try:
        return cast(v)
    except (TypeError, ValueError):
        return default


def _invalid_spec_result(message: str) -> dict:
    """Return a stable guard report for malformed top-level inputs."""
    check = {"rule": "spec_schema", "id": "spec", "level": "error", "msg": message}
    return {"passed": False, "checks": [check], "advisory_rules": sorted(DESIGN_RULES),
            "warnings": [f"[spec_schema] {message}"],
            "grid": {"checked": 0, "aligned": 0, "adherence": None},
            "line_measure": {"checked": 0, "over": 0, "worst": 0.0, "worst_id": None}}


def _weak_text_roles(theme: dict, slides: list) -> set[str]:
    """会被判「弱化文字」的角色：主题声明的弱字 + 元素里真拿来写字的弱色。

    muted 是本包约定的弱字（刻度/注释/来源）；`chart_muted` 指到哪个 token，那个 token
    就是图表刻度与标签的颜色来源（compiler 照它画），指到面/影上等于刻度白写。secondary
    只有在元素里真当 text 颜色用时才算字——否则它是面（深底主题的 secondary 就是深面，
    #3A3A42 on #0B0B0F 只有 1.74:1，拿它当字才该被拦下）。
    """
    colors = theme.get("colors") or {}
    roles = {"muted"}
    chart_muted = theme.get("chart_muted")
    if isinstance(chart_muted, str) and chart_muted.strip() in colors:
        roles.add(chart_muted.strip())
    for slide in (slides if isinstance(slides, list) else []):
        if not isinstance(slide, dict):
            continue
        for e in (slide.get("elements") or []):
            if not isinstance(e, dict) or not (e.get("text") or e.get("type") == "text"):
                continue
            for role in ("muted", "secondary"):
                if _uses_role(e.get("color"), role, theme):
                    roles.add(role)
    return roles & {"muted", "secondary"}


def check_spec(spec: dict, rules: dict | None = None,
               *, include_advisory: bool = True) -> dict:
    """
    静态治理：对调用方传入的 spec 做 OS 硬约束断言。

    rules（可配置阈值，调用方传入；缺省用默认值；脏输入一律回落默认不炸链。
    include_advisory=False 时跳过设计契约诊断；工程错误（结构、数据、几何、
    越界、来源和可读性底线）仍保留。独立 guard CLI 默认保留 advisory，便于诊断。
    主题约束 `spec.theme.constraints` 仅对 accent_max/max_charts/max_colors/
    font_levels_max/font_families_max 五项在未显式传入 rules 时生效）:
      grid_bias      : 网格偏差最大容忍（0–4，0=必须严格 8 倍数）
      safety_min     : 安全区最小边距（默认 48，通栏条豁免）
      overlap_ratio  : 元素重叠容忍上限（默认 .12）
      text_ink_ratio : 文本框参与重叠的有效宽度系数（默认 .55，文本框≠墨迹）
      text_ink_v     : 文本框参与重叠的有效高度系数（默认 .70，行高/padding 余量）
      accent_max     : Accent 面积占比上限（默认 .05；VP 主题多为 .03–.05）
      accent_text_k  : 文字面积折算系数（默认 .30，文本框 ≠ 墨迹面积）
      max_charts     : 每页图表总数上限（VP-007=3 / VP-009=2）
      max_colors     : 每页颜色角色数上限（VP 主题 4–5）
      check_rhythm   : 是否检查跨页节奏（默认 True）
      narrative_lines_max : 每页叙事文字行数上限（默认 6）
      semantic_colors_max : 每页语义色相上限（默认 3）
      hue_families_max    : 全套色相族上限（默认 4；30° 一档，纸色/灰阶不计）
      accent_hue_min      : Accent 与主/辅色的最小色相角（默认 12°，低于此强调不成其为强调）
      chart_label_scale_tol: 同一图表类型跨页标签字号的最大倍数（默认 1.25）
      alignments_max : 每页文本主对齐方式上限（默认 2）
      decoration_area_max : 装饰面积上限（默认 .10）
      animation_types_max : 全套动画/切换类型上限（默认 2）
      font_levels_max     : 每页字号等级上限（默认 4，hint；可经 theme.constraints 传入）
      font_families_max   : 每页字体家族引用上限（默认 2，hint）
      min_font_size       : 注释/来源/标签类文字最小字号（默认 10，warn）
      focus_scale         : 焦点文字应获得页内最大字号（默认 True，hint）
      require_provenance  : 数值图表必须声明来源/单位/期间/比较口径（默认 False=warn，True=error）

    事实/口径治理（本版本新增，业务级）：
      data_provenance  : 数值图表缺 来源/单位/期间/比较口径 声明 → warn（require_provenance=True 时 error）
      metric_consistency: 同一 metric（metric/series_name 键）跨页单位/期间/口径不一致 → error/warn/hint
      title_semantics  : insight 退化成「字段名标题」→ hint（提示改写为可复述结论）

    行长（typography）不走 rules：阈值住 primitives
    LINE_MEASURE_CJK_MAX / LINE_MEASURE_LATIN_MAX / LINE_MEASURE_FAIL_FACTOR，
    并用 MEASURE_EXEMPT_ROLES 豁免注记级角色；超限记 warn，超上限 2× 记 error。

    returns: {
      "passed": bool, "checks": [...], "warnings": [...],
      "grid": {checked, aligned, adherence}, "line_measure": {checked, over, worst, worst_id}
    }
    """
    if not isinstance(spec, dict):
        return _invalid_spec_result("spec 顶层必须是对象/dict")
    if spec.get("_input_error"):
        return _invalid_spec_result(str(spec.get("_input_error")))
    if spec.get("theme") not in (None, {}) and not isinstance(spec.get("theme"), dict):
        return _invalid_spec_result("spec.theme 必须是对象/dict")
    if spec.get("canvas") not in (None, {}) and not isinstance(spec.get("canvas"), dict):
        return _invalid_spec_result("spec.canvas 必须是对象/dict")
    if spec.get("slides") is not None and not isinstance(spec.get("slides"), list):
        return _invalid_spec_result("spec.slides 必须是数组/list")

    rules = dict(rules or {})
    theme = spec.get("theme") or {}
    # 主题生产约束（来自 VP 主题「生产约束」章节，可被 rules 显式覆盖）
    constraints = dict(theme.get("constraints") or {})
    grid_bias = _rule_num(rules, "grid_bias", 4, int)          # 非严格：≤4 仅提示
    safety_min = _rule_num(rules, "safety_min", 48, float)
    overlap_ratio = _rule_num(rules, "overlap_ratio", 0.12, float)
    text_ink_ratio = _rule_num(rules, "text_ink_ratio", 0.55, float)
    text_ink_v = _rule_num(rules, "text_ink_v", 0.70, float)
    accent_max = _rule_num(rules, "accent_max", constraints.get("accent_max", 0.05), float)
    accent_text_k = _rule_num(rules, "accent_text_k", 0.30, float)
    max_charts = rules.get("max_charts", constraints.get("max_charts"))
    max_colors = rules.get("max_colors", constraints.get("max_colors"))
    check_rhythm = bool(rules.get("check_rhythm", True))
    narrative_lines_max = _rule_num(rules, "narrative_lines_max", 6, int)
    semantic_colors_max = _rule_num(rules, "semantic_colors_max", 3, int)
    alignments_max = _rule_num(rules, "alignments_max", 2, int)
    decoration_area_max = _rule_num(rules, "decoration_area_max",
                                    constraints.get("decoration_area_max", 0.10), float)
    animation_types_max = _rule_num(rules, "animation_types_max", 2, int)
    hue_families_max = _rule_num(rules, "hue_families_max", 4, int)
    accent_hue_min = _rule_num(rules, "accent_hue_min", 12, float)
    chart_label_scale_tol = _rule_num(rules, "chart_label_scale_tol", 1.25, float)
    # §07 排版预算（hint 级软约束：提示层级过碎，不扣硬分）
    # 方向种子（数字约束）：未声明 = 不检查；声明了就按声明执法。
    # whitespace/bg_layers/bold_ratio/type_step 都是「方向要可执行」缺的那几个量，
    # 由 plan 的主题种子写进 spec.theme.constraints（骨架代为落笔）。
    whitespace_min = _rule_num(rules, "whitespace_min",
                               constraints.get("whitespace_min",
                                               constraints.get("min_whitespace")), float)
    bg_layers_max = _rule_num(rules, "bg_layers_max", constraints.get("bg_layers_max"), int)
    bold_ratio_max = _rule_num(rules, "bold_ratio_max", constraints.get("bold_ratio_max"), float)
    type_step_min = _rule_num(rules, "type_step_min", constraints.get("type_step_min"), float)
    banner_cov = constraints.get("bg_layer_coverage")
    bg_layer_cov = _rule_num({}, "k", banner_cov, float) if banner_cov is not None else 0.60
    font_levels_max = int(rules.get("font_levels_max",
                                    constraints.get("font_levels_max", 4)))
    font_families_max = int(rules.get("font_families_max",
                                      constraints.get("font_families_max", 2)))
    # 可读性底线：注释/来源/标签类文字的最小字号（设计单位 px）
    min_font_size = _rule_num(rules, "min_font_size", 10, float)
    focus_scale = bool(rules.get("focus_scale", True))
    require_provenance = bool(rules.get("require_provenance", False))

    canvas = spec.get("canvas") or {}
    canvas_issues: list[str] = []
    def _canvas_dim(key: str, default: float) -> float:
        raw = canvas.get(key, default)
        try:
            if isinstance(raw, bool):
                raise ValueError
            value = float(raw)
            if not math.isfinite(value) or value <= 0:
                raise ValueError
            return value
        except (TypeError, ValueError, OverflowError):
            canvas_issues.append(f"canvas.{key} 必须是正的有限数字")
            return float(default)
    cw = _canvas_dim("width", DEFAULT_WIDTH)
    ch = _canvas_dim("height", DEFAULT_HEIGHT)
    slides = spec.get("slides") or []

    checks: list[dict] = []      # 每项: {"rule", "id", "level", "msg"}
    warnings: list[str] = []
    animation_types: set[str] = set()

    def add(rule, eid, level, msg):
        # QA 默认只验证工程事实；设计契约仍可由独立 guard 或显式 advisory 读取。
        if not include_advisory and rule in DESIGN_RULES:
            return
        checks.append({"rule": rule, "id": eid, "level": level, "msg": msg})
        if level in ("warn", "error"):
            warnings.append(f"[{rule}] {msg}")

    for _canvas_issue in canvas_issues:
        add("canvas_schema", "canvas", "error", _canvas_issue)

    # 空 deck：没有页就没有可判断、可交付的对象。0 页 PASS 是最贵的一种「通过」——
    # 上游按 PASS 继续走，交付的是空气。
    if not slides:
        add("slide_schema", "slides", "error",
            "spec 里没有任何页（slides 为空）；空 deck 不是可交付物")

    # 元素类型白名单（F1）：未知 type 在编译期被静默跳过 = 内容丢失；
    # spec 零成本档不加载编译层，此处是唯一前置拦截。集合单真源 primitives.ELEMENT_TYPES。
    for _sl in slides:
        if not isinstance(_sl, dict):
            add("slide_schema", "slides", "error", "每个 slide 必须是对象/dict")
            continue
        # 元素字段形态（F4——v4.15 实战裂缝）：「看似合理的对象形态」会让编译期
        # unhashable 失色/报错，spec 档应当场拦截；与 element_type 白名单同族。
        _sid = str(_sl.get("id", "?"))
        if "elements" in _sl and not isinstance(_sl.get("elements"), list):
            add("slide_schema", _sid, "error", "slide.elements 必须是数组/list")
        # 空白页：既没有元素、也没有背景——画面上什么都没有。
        # （有 background 的「纯色/整图呼吸页」是合法的编辑式手法，不在此列。）
        _els = _sl.get("elements")
        _drawable = [e for e in _els if isinstance(e, dict)] if isinstance(_els, list) else []
        if not _drawable and not _sl.get("background"):
            add("page_contract", _sid, "error",
                "这一页没有任何元素，也没有 background：画面上什么都没有，"
                "不是可交付内容（要么给元素，要么给背景）")
        if "page_intent" in _sl and _sl.get("page_intent") is not None \
                and not isinstance(_sl.get("page_intent"), dict):
            add("slide_schema", _sid, "error", "slide.page_intent 必须是对象/dict")
        _bgs = _sl.get("background")
        if isinstance(_bgs, dict) and isinstance(_bgs.get("color"), (dict, list, tuple)):
            add("element_schema", str(_sl.get("id", "?")), "error",
                "slide.background.color 须为 #HEX 字符串或 theme token（对象形态会让编译期失守）")
        for _el in (_sl.get("elements") or []):
            if not isinstance(_el, dict):
                continue
            _et = str(_el.get("type", "text"))
            _eid = str(_el.get("id", "?"))
            if _et not in ELEMENT_TYPES:
                add("element_type", _eid, "error",
                    f"未知元素类型 {_et!r}（编译期将静默跳过；合法类型：{sorted(ELEMENT_TYPES)}）")
                continue
            _c = _el.get("color")
            if isinstance(_c, (dict, list, tuple, set)):
                add("element_schema", _eid, "error",
                    f"元素配色须为 #HEX 字符串或 theme token 名，收到 {type(_c).__name__}（编译期 unhashable 失色）")
            # 形状方言静默丢弃（F13/v4.21——release 像素档实战收网）：
            # 顶层 color 仅文字元素使用；add_shape 只读 fill/stroke。
            # 「形状 + 顶层 color 无 fill」= 填充凭空消失（2026 时间轴圆点、
            # 章节深色框三例实测）；「line 无 stroke」= 边框凭空消失（印章框实测）。
            if _et == "shape":
                if _el.get("color") is not None and "fill" not in _el:
                    add("element_schema", _eid, "error",
                        "形状填充须走 fill（颜色字符串或 {type: solid, ...}）；"
                        "顶层 color 在形状上被静默丢弃 → 元素渲染不可见")
                if _el.get("line") is not None and "stroke" not in _el:
                    add("element_schema", _eid, "error",
                        "形状边框须走 stroke/stroke_width；顶层 line 字段被静默丢弃")
            _f = _el.get("fill")
            if _f is not None and not isinstance(_f, str) and (
                    isinstance(_f, bool) or not (isinstance(_f, dict) and ("type" in _f or "color" in _f))):
                add("element_schema", _eid, "error",
                    "fill 须为 {type: solid|gradient|none, ...} dict 或缺省（bool/其他形态为非法 schema）")

    if "grid_columns" in canvas:
        try:
            if isinstance(canvas["grid_columns"], bool):
                raise ValueError
            columns = int(canvas["grid_columns"])
            if columns <= 0:
                raise ValueError
            if columns != 12:
                add("grid", "canvas", "hint", "推荐使用 12 列逻辑网格；8 单位仅用于基线与间距")
        except (TypeError, ValueError, OverflowError):
            add("canvas_schema", "canvas", "error", "canvas.grid_columns 必须是正整数")
    if "grid_unit" in canvas:
        try:
            if isinstance(canvas["grid_unit"], bool):
                raise ValueError
            unit = float(canvas["grid_unit"])
            if not math.isfinite(unit) or unit <= 0:
                raise ValueError
            if unit != GRID:
                add("grid", "canvas", "hint", f"推荐使用 {GRID} 单位基线网格")
        except (TypeError, ValueError, OverflowError):
            add("canvas_schema", "canvas", "error", "canvas.grid_unit 必须是正的有限数字")

    # ---- 每页 ----
    lm_limits = _measure_limits()
    grid_stats = {"checked": 0, "aligned": 0}
    measure_stats = {"checked": 0, "over": 0, "worst": 0.0, "worst_id": None}
    accent_area = 0.0
    deck_hues: set[int] = set()
    chart_styles: dict[str, dict] = {}
    chart_meta: list[dict] = []   # 事实/口径治理：收集每张数值图表的来源/单位/期间/口径
    for si, s in enumerate(slides):
        if not isinstance(s, dict):
            # 首轮 schema 扫描已记录错误；此处只跳过，保证后续检查不崩溃。
            continue
        sid = s.get("id", f"slide_{si}")
        _check_page_contract(s, sid, add, cw, ch)
        # 标题语义：insight 若是字段名，提示改写为可复述结论（与 OS 审查语义同源）
        _intent = s.get("page_intent") if isinstance(s.get("page_intent"), dict) else {}
        _insight = _intent.get("insight") or s.get("insight")
        if isinstance(_insight, str) and _looks_like_field_name(_insight):
            add("title_semantics", sid, "hint",
                f"insight「{_insight}」读起来是字段名而非洞察；标题应写可复述的"
                f"结论（对象 + 变化/差异 + 含义），例如把「市场分析」写成「市场已从"
                f"规模驱动转向效率驱动」")
        chart_count = 0
        slide_accent_area = 0.0
        page_colors: set[str] = set()
        semantic_colors: set[str] = set()
        alignments: set[str] = set()
        narrative_lines = 0
        decoration_area = 0.0
        icon_styles: set[str] = set()
        font_levels: set[float] = set()
        font_families: set[str] = set()
        for e in s.get("elements", []):
            if not isinstance(e, dict):
                continue
            eid = e.get("id", f"{sid}[{si}]")
            typ = str(e.get("type", "text"))
            role = str(e.get("role", ""))
            if include_advisory:
                if e.get("animation") or e.get("transition"):
                    animation_types.add(str(e.get("animation") or e.get("transition")))
                if e.get("icon_style"):
                    icon_styles.add(str(e.get("icon_style")))
            if typ == "text":
                if "text" not in e:
                    hint = "；检测到 content，请改用 text" if "content" in e else ""
                    add("TEXT_FIELD_MISSING", eid, "error",
                        f"text 元素缺少必需字段 'text'{hint}")
                elif "content" in e:
                    add("TEXT_FIELD_INVALID", eid, "error",
                        "text 元素使用了未消费字段 'content'，请改用顶层字段 'text'")
                if "style" in e:
                    add("TEXT_STYLE_INVALID", eid, "error",
                        "text 元素使用了未消费的嵌套字段 'style'；请将 size、color、bold、line_height 等属性放到元素顶层")
                if include_advisory:
                    alignments.add(str(e.get("align", "left")))
                    # §07 排版预算：字号等级 / 字体家族引用
                    try:
                        if e.get("size") is not None:
                            font_levels.add(round(float(e["size"]), 1))
                    except (TypeError, ValueError):
                        pass
                    fref = e.get("font") or e.get("family")
                    if isinstance(fref, str) and fref:
                        font_families.add(fref)
                # 可读性底线：注释/来源/标签类文字不得低于最小字号（渲染后可读性复核）
                if role in {"caption", "annotation", "source", "label", "axis", "data_label",
                            "legend", "metadata", "method", "eyebrow", "page_number"}:
                    try:
                        if e.get("size") is not None and float(e["size"]) < min_font_size:
                            add("min_font", eid, "warn",
                                f"{role} 文字 {float(e['size']):g}px < 可读下限 "
                                f"{min_font_size:g}px；提高字号或改由更高层级角色承担")
                    except (TypeError, ValueError):
                        pass
                if role not in {"source", "method", "annotation", "axis", "label", "data_label",
                                "legend", "metadata", "eyebrow", "page_number"}:
                    declared = e.get("max_lines")
                    if isinstance(declared, int) and declared > 0:
                        narrative_lines += declared
                    else:
                        narrative_lines += max(1, str(e.get("text", "")).count("\n") + 1)
            if role == "decoration" or e.get("decorative") is True:
                decoration_area += _element_area(e)
            x = e.get("x", 0)
            y = e.get("y", 0)
            w = e.get("width", 0)
            h = e.get("height", 0)

            # 几何退化前置拦截（F8/v4.18——geometry 是元素存在的前提）：
            # 缺 x/y/width/height 静默按 0 计、≤0、非数值——渲染后元素
            # 不可见却只报 -1.5 编译 warn。不可见的内容比溢出更隐蔽，
            # 与 element_schema 同族（脏字段形态静默成本），error 级。
            _mx, _my, _mw, _mh = e.get("x"), e.get("y"), e.get("width"), e.get("height")
            _missing = [k for k, _v in (("x", _mx), ("y", _my),
                                        ("width", _mw), ("height", _mh)) if _v is None]
            if _missing:
                add("element_schema", eid, "error",
                    f"geometry 缺项 {', '.join(_missing)}"
                    "（契约必填；缺省按 0 计 → 元素渲染不可见）")
            else:
                try:
                    _bool_geometry = any(isinstance(_v, bool)
                                         for _v in (_mx, _my, _mw, _mh))
                    _d = [float(_v) for _v in (_mx, _my, _mw, _mh)]
                    _finite = (not _bool_geometry
                               and all(math.isfinite(_v) for _v in _d))
                    _fw, _fh = _d[2], _d[3]
                except (TypeError, ValueError, OverflowError):
                    _fw = _fh = None
                    _finite = False
                if not _finite:
                    add("element_schema", eid, "error",
                        "geometry 非数值/非有限（x/y/width/height 必须是数字）")
                elif _fw <= 0 or _fh <= 0:
                    add("element_schema", eid, "error",
                        f"geometry 退化（width={_fw:g}, height={_fh:g} ≤ 0 "
                        "→ 元素渲染不可见）")

            # §02.1 网格：坐标与尺寸偏离 8 倍数
            # 发丝线（≤2px）与通栏元素（宽/高等于画布）四个维度一并豁免：这类对象的
            # 位置由「居中一条线 / 铺满画布」决定，按 8 倍数要求它是伪误差。
            thin = False
            try:
                thin = (float(w) <= 2 or float(h) <= 2
                        or abs(float(w) - cw) < 1 or abs(float(h) - ch) < 1)
            except (TypeError, ValueError):
                pass
            try:
                for axis, v in (("x", float(x)), ("y", float(y)),
                                ("width", float(w)), ("height", float(h))):
                    if not math.isfinite(v) or thin:
                        continue
                    bias = _is_grid_aligned(v)
                    grid_stats["checked"] += 1
                    grid_stats["aligned"] += 1 if bias == 0 else 0
                    if axis in ("height", "width") and float(e.get(axis, 0)) <= 2:
                        continue
                    if bias > grid_bias:
                        add("grid", eid, "warn",
                            f"{axis}={v:.0f} 偏离 8 网格 {bias}px（OS §02.1）")
                    elif bias > 0:
                        add("grid", eid, "hint",
                            f"{axis}={v:.0f} 偏离 8 网格 {bias}px（微调对齐更稳）")
            except (TypeError, ValueError):
                add("geometry", eid, "warn", "坐标/尺寸非数值，无法校验")

            # §03.2 行长：超长行是「排版不专业」最常见的硬伤，此前只被 grid 顺带扫到
            lm = line_measure(e, lm_limits)
            if lm:
                measure_stats["checked"] += 1
                if lm["per_line"] > measure_stats["worst"]:
                    measure_stats["worst"] = lm["per_line"]
                    measure_stats["worst_id"] = eid
                if lm["fatal"]:
                    measure_stats["over"] += 1      # 超限含被阻断的那些：比率要能对上
                    # 行长的「建议值」是编辑观点（typography，advisory）；但超出 3× 意味着
                    # 文本被切断——那是内容完整性事实，归 text_capacity，可以阻断。
                    add("text_capacity", eid, "error",
                        f"每行约 {lm['per_line']:.0f} 字 > 上限 {lm['limit']} 的 "
                        f"{lm_limits['LINE_MEASURE_FAIL_FACTOR']:.1f}×"
                        f"（{'CJK' if lm['cjk_led'] else '拉丁'}行长失控，眼跳回失准 → 拆句或加宽盒）")
                elif lm["over"]:
                    measure_stats["over"] += 1
                    add("typography", eid, "warn",
                        f"每行约 {lm['per_line']:.0f} 字 > {lm['limit']}"
                        f"（编辑式排版建议 ≤{lm['limit']}），行尾扫读吃力")

            # 安全区 / 越界：通栏只豁免对应轴，不能因为 width==cw 就跳过 y，
            # 也不能因为 height==ch 就放过 x。旧逻辑用 OR 整体豁免，错误的 full-bleed
            # 盒子会越出画布却不报错。
            # 非数值 geometry 已被 F8 element_schema 拦截降级，这里不再硬炸。
            try:
                _fx, _fy = float(x), float(y)
                _fw, _fh = float(w), float(h)
                bleed_x = abs(_fw - cw) < 1 and abs(_fx) <= 1
                bleed_y = abs(_fh - ch) < 1 and abs(_fy) <= 1
                x_out = not bleed_x and (_fx < -1 or _fx + _fw > cw + 1)
                y_out = not bleed_y and (_fy < -1 or _fy + _fh > ch + 1)
                if x_out or y_out:
                    add("safety", eid, "error", "元素越出画布边界")
                elif _fx < safety_min and _fx > 0:
                    add("safety", eid, "hint",
                        f"x={_fx:.0f} < 安全区 {safety_min:.0f}")
                elif _fy < safety_min and _fy > 0:
                    add("safety", eid, "hint",
                        f"y={_fy:.0f} < 安全区 {safety_min:.0f}")
            except (TypeError, ValueError):
                pass

            # 背景安全区：仅检查内容承载对象；通栏背景/结构线不参与。
            safe_zones = s.get("safe_zones") or []
            if safe_zones and typ in ("text", "chart", "native_chart", "image"):
                if not any(_inside_zone(e, z) for z in safe_zones if isinstance(z, dict)):
                    add("safe_zone", eid, "warn", "内容对象未完整落入任何声明的文字安全区")

            # §06/§21 Accent 面积估算是设计 advisory；默认工程 QA 不扫描颜色角色。
            if include_advisory:
                fill = e.get("fill")
                if _uses_role(fill, "accent", theme):
                    accent_area += _element_area(e)
                    slide_accent_area += _element_area(e)
                if _uses_role(e.get("stroke"), "accent", theme):
                    accent_area += _element_area(e) * 0.08   # 描边≈面积的零头
                    slide_accent_area += _element_area(e) * 0.08
                if typ == "text" and _uses_role(e.get("color"), "accent", theme):
                    accent_area += _element_area(e) * accent_text_k
                    slide_accent_area += _element_area(e) * accent_text_k

            # §19 图表容量与数据完整性
            if typ in ("chart", "native_chart"):
                chart_count += 1
                kind = str(e.get("chart_kind") or e.get("kind", ""))
                if kind not in SUPPORTED_CHART_KINDS:
                    add("chart_type", eid, "error",
                        f"未知 chart_kind={kind!r}；合法值：{sorted(SUPPORTED_CHART_KINDS)}")
                data = e.get("data") or []
                # 载荷完整性：没有可画的东西就不是「设计选择」，而是内容缺失。
                if kind in ELEMENT_METRIC_KINDS:
                    if not str(e.get("value") or "").strip():
                        add("chart_payload", eid, "error",
                            f"{kind} 缺少元素级 value（大数字没有数字）；"
                            "label 建议同时声明")
                    elif not str(e.get("label") or "").strip():
                        add("chart_payload", eid, "warn",
                            f"{kind} 没有 label：数字会被误读，建议补一行说明")
                # 论点可见性（差异类主张）：图是不是把「差多少」画出来了。
                # 只查一个可判定的组合——零基长度编码 + 数值几乎等长 + 图自己标了重点。
                # 不解析主张文本，不做审美裁决：几何读不出来就是读不出来。
                if (kind in ZERO_BASED_LENGTH_KINDS
                        and (e.get("highlight") or e.get("target") is not None)
                        and e.get("baseline") is None):
                    vals: list[float] = []
                    for point in (data if isinstance(data, list) else []):
                        if isinstance(point, dict):
                            try:
                                vals.append(float(point.get("value")))
                            except (TypeError, ValueError):
                                continue
                    for series in (e.get("series") or []) if isinstance(e.get("series"), list) else []:
                        if isinstance(series, dict):
                            for v in (series.get("values") or []):
                                try:
                                    vals.append(float(v))
                                except (TypeError, ValueError):
                                    continue
                    vals = [v for v in vals if math.isfinite(v)]
                    if len(vals) >= 2 and min(vals) > 0:
                        ratio = max(vals) / min(vals)
                        if ratio < CHART_FLAT_RATIO:
                            add("chart_argument", eid, "warn",
                                f"最大 {max(vals):g} 与最小 {min(vals):g} 只差 "
                                f"{(ratio - 1) * 100:.0f}%（{ratio:.2f}×），从 0 起算的条长读起来"
                                f"几乎一样——这页的「差多少」观众看不见。改用 waterfall / "
                                f"big_number 直接写差值，或把二者放到共同基线（索引化）再比长度")
                elif kind == "matrix":
                    points = e.get("points")
                    if not (isinstance(points, list) and points):
                        add("chart_payload", eid, "error",
                            "matrix 缺少 points[{x,y,label}]；无点不绘图")
                    else:
                        for pi, point in enumerate(points[:12]):
                            if not isinstance(point, dict):
                                add("chart_payload", f"{eid}[{pi}]", "error",
                                    "matrix point 必须是 {x,y,label} 对象")
                                continue
                            try:
                                px, py = float(point.get("x")), float(point.get("y"))
                                if not (math.isfinite(px) and math.isfinite(py)):
                                    raise ValueError
                            except (TypeError, ValueError, OverflowError):
                                add("chart_payload", f"{eid}[{pi}]", "error",
                                    "matrix point 的 x/y 必须是 0–1 的有限数字")
                                continue
                            if not (0.0 <= px <= 1.0 and 0.0 <= py <= 1.0):
                                add("chart_payload", f"{eid}[{pi}]", "warn",
                                    f"matrix point x={px:g} y={py:g} 超出 0–1 绘图区，会被画到框外")
                            if not str(point.get("label") or "").strip():
                                add("chart_payload", f"{eid}[{pi}]", "warn",
                                    "matrix point 没有 label，读者不知道它是谁")
                elif kind == "architecture":
                    layers = e.get("layers")
                    clean = [str(x).strip() for x in layers[:3]] if isinstance(layers, list) else []
                    if not clean or not all(clean):
                        add("chart_payload", eid, "error",
                            "architecture 必须声明 layers（1–3 条非空层名）；"
                            "没有层名就不画，也不生成占位文字")
                elif kind in ROWS_CHART_KINDS:
                    usable = [r for r in data if isinstance(r, dict)
                              and str(r.get("label") or "").strip()]
                    multi_series = (isinstance(e.get("series"), list) and bool(e.get("series"))
                                    and isinstance(e.get("series")[0], dict))
                    if not multi_series and not usable:
                        add("chart_payload", eid, "error",
                            f"{kind} 需要 data 行（每行含非空 label）；空载荷会画出空白页")
                n = len(data) if isinstance(data, list) else 0
                # 多序列：series[{name, values}] + categories。类别数 = len(categories)，
                # highlight 语义是「序列索引」而非「数据行索引」；此时不再要求 data。
                series_list = e.get("series")
                multi = (isinstance(series_list, list) and bool(series_list)
                         and isinstance(series_list[0], dict))
                categories = e.get("categories") or []
                n_cat = len(categories) if isinstance(categories, list) else 0
                n_series = len(series_list) if multi else 0
                limit = CHART_LIMITS.get(kind)
                if limit is not None and (n_cat if multi else n) > limit:
                    add("chart_capacity", eid, "warn",
                        f"{kind} 类别 {(n_cat if multi else n)} > 上限 {limit}（OS §19.4）")
                if kind in NUMERIC_CHART_KINDS:
                    if multi:
                        if n_cat == 0 or n_series == 0:
                            add("data_integrity", eid, "error",
                                "多序列图表缺少 categories 或 series")
                        else:
                            # 变量必须避开外层的 si / s：同名会覆盖「当前页」，
                            # 使本轮后续所有用 s 的检查（source_zone、overlap、
                            # 几何自检…）拿到序列字典而非页面——那些检查会静默失效。
                            for _sidx, _srs in enumerate(series_list):
                                vals = _srs.get("values") if isinstance(_srs, dict) else None
                                if not isinstance(vals, list) or not vals:
                                    add("data_integrity", f"{eid}[s{_sidx}]", "error",
                                        f"series[{_sidx}] 缺少 values")
                                    continue
                                if len(vals) != n_cat:
                                    add("data_integrity", f"{eid}[s{_sidx}]", "error",
                                        f"series[{_sidx}] values 长度 {len(vals)} 与 categories 长度 {n_cat} 不一致"
                                        "（编译器不得静默补零/截断）")
                                for vi, v in enumerate(vals):
                                    try:
                                        if isinstance(v, bool):
                                            raise ValueError
                                        value = float(v)
                                        if not math.isfinite(value):
                                            raise ValueError
                                    except (TypeError, ValueError, OverflowError):
                                        add("data_integrity", f"{eid}[s{_sidx}][{vi}]", "error",
                                            f"series[{_sidx}] value={v!r} 不是有限数字")
                    elif not isinstance(data, list) or not data:
                        add("data_integrity", eid, "error",
                            "数值图表缺少 data，无法验证或渲染")
                    else:
                        for di, row in enumerate(data):
                            if not isinstance(row, dict) or "label" not in row:
                                add("data_integrity", f"{eid}[{di}]", "error",
                                    "图表数据行必须包含 label")
                                continue
                            if str(row.get("label", "")).strip() == "":
                                add("data_integrity", f"{eid}[{di}]", "error",
                                    "图表数据 label 不得为空")
                            raw = row.get("value")
                            if raw is None:
                                add("data_integrity", f"{eid}[{di}]", "error",
                                    "图表数据 value 缺失；缺失值请显式说明，不得静默补零")
                                continue
                            try:
                                if isinstance(raw, bool):
                                    raise ValueError
                                value = float(raw)
                                if not math.isfinite(value):
                                    raise ValueError
                            except (TypeError, ValueError, OverflowError):
                                add("data_integrity", f"{eid}[{di}]", "error",
                                    f"图表数据 value={raw!r} 不是有限数字")
                                continue
                            if kind in {"ranked_bar", "progress_bar", "stacked_bar", "bubble"} and value < 0:
                                add("data_integrity", f"{eid}[{di}]", "error",
                                    f"{kind} 不接受负值 value={value:g}；请改用可表达正负关系的图表")
                        if kind == "progress_bar":
                            ceiling = e.get("max", 100)
                            try:
                                if float(ceiling) <= 0:
                                    raise ValueError
                            except (TypeError, ValueError):
                                add("data_integrity", eid, "error",
                                    "progress_bar 的 max 必须是正数")
                if not multi and kind in ("donut", "donut_composition", "pie") and isinstance(data, list):
                    try:
                        if sum(max(float(r.get("value", 0)), 0) for r in data if isinstance(r, dict)) <= 0:
                            add("data_integrity", eid, "error",
                                "构成图的有效数值总和必须大于 0")
                    except (TypeError, ValueError):
                        pass
                if "highlight" in e:
                    try:
                        hi = int(e.get("highlight"))
                        # 多序列：highlight 是序列索引；单序列：数据行索引
                        upper = n_series if multi else n
                        if hi < 0 or hi >= upper:
                            add("chart_highlight", eid, "warn",
                                f"highlight={hi} 超出数据范围 0–{max(upper - 1, 0)}")
                    except (TypeError, ValueError):
                        names = ([str(sr.get("name", "")) for sr in (e.get("series") or [])
                                  if isinstance(sr, dict)] if multi else
                                 [str(r.get("label", "")) for r in data
                                  if isinstance(r, dict)])
                        if str(e.get("highlight")).strip() not in names:
                            add("chart_highlight", eid, "warn",
                                f"highlight={e.get('highlight')!r} 既不是索引也不匹配任何"
                                "类别名/序列名，会被忽略（画面上不会出现强调）")
                # 图表标签是独立的可见对象：空间不足时不允许让渲染器硬塞进绘图区。
                show_values = e.get("show_values", kind in ("comparison_bar", "bar", "column", "donut"))
                label_policy = str(e.get("label_collision_policy", "fail"))
                try:
                    eh = float(e.get("height", 0))
                    label_gap = float(e.get("label_gap", 8))
                    label_margin = float(e.get("label_safe_margin", 12))
                    if show_values and n >= 6 and eh < 190:
                        level = "error" if label_policy == "fail" else "warn"
                        add("chart_label_collision", eid, level,
                            f"{kind} 含 {n} 个标签但高度 {eh:.0f}px 不足；应拆图/减少类别，不能缩小字体")
                    if label_gap < 6 or label_margin < 8:
                        add("chart_label_collision", eid, "warn",
                            "图表 label_gap / label_safe_margin 过小，可能造成标签贴线或贴边")
                except (TypeError, ValueError):
                    add("chart_label_collision", eid, "error",
                        "图表标签安全参数必须是数字")

            # §06/§21 页面颜色角色与图表风格属于设计 advisory；默认 QA 不扫描。
            if include_advisory:
                for key in ("color", "fill", "stroke"):
                    v = e.get(key)
                    if isinstance(v, str) and v in theme.get("colors", {}):
                        page_colors.add(v)
                        if v not in NEUTRAL_COLOR_ROLES:
                            semantic_colors.add(v)
                            fam = _hue_family(theme["colors"][v])
                            if fam is not None:
                                deck_hues.add(fam)
                    elif isinstance(v, str) and v.startswith("#"):
                        page_colors.add(v.upper())
                        fam = _hue_family(v)
                        if fam is not None:
                            deck_hues.add(fam)
                _mud = _gradient_muck(e.get("fill"))
                if _mud:
                    add("palette_discipline", eid, "hint",
                        f"{typ}「{eid}」填充渐变{_mud}；插值中段会灰成脏块——"
                        f"改成同族明度阶，或补色时把两端拉开明度")
            if typ in ("chart", "native_chart"):
                if include_advisory:
                    rec = chart_styles.setdefault(
                        str(e.get("chart_kind") or e.get("kind") or typ),
                        {"pages": set(), "sizes": set(), "legend": set()})
                    rec["pages"].add(sid)
                    try:
                        rec["sizes"].add(round(float(e.get("label_size")), 1))
                    except (TypeError, ValueError):
                        pass
                    if "legend" in e:
                        rec["legend"].add(bool(e.get("legend")))
                # ---- 事实/口径治理（业务级）----
                # 来源不可省略、单位/期间/比较口径必须分开声明：这是数据叙事的
                # 底线（SKILL.md 硬边界）。缺省 warn（可经 rules 升 error），但一旦
                # 声明了就必须跨页一致——口径打架是「会误导决策」的业务错误，记 error。
                if kind in NUMERIC_CHART_KINDS:
                    provenance = {}
                    nested_provenance = e.get("provenance") if isinstance(
                        e.get("provenance"), dict) else {}
                    for meta_key, label in (("source", "来源"), ("unit", "单位"),
                                            ("period", "期间"), ("basis", "比较口径"),
                                            ("data_status", "数据状态")):
                        v = e.get(meta_key)
                        if v in (None, ""):
                            v = nested_provenance.get(meta_key)
                        provenance[meta_key] = str(v).strip() if v not in (None, "") else None
                    missing = [label for meta_key, label in
                               (("source", "来源"), ("unit", "单位"),
                                ("period", "期间"), ("basis", "比较口径"))
                               if provenance[meta_key] is None]
                    if missing:
                        add("data_provenance", eid,
                            "error" if require_provenance else "warn",
                            f"数值图表缺少 {'/'.join(missing)} 声明；来源不可省略、"
                            f"单位与期间必须显式（防止跨页口径漂移）")
                    # 指标键：metric / series_name 是同一指标跨页对齐的锚
                    metric_key = (e.get("metric") or e.get("series_name"))
                    if isinstance(metric_key, str) and metric_key.strip():
                        chart_meta.append({
                            "id": eid, "slide": sid,
                            "metric": metric_key.strip(),
                            "unit": provenance["unit"],
                            "period": provenance["period"],
                            "basis": provenance["basis"],
                        })

        # ---- 元素重叠（text / chart / image 之间，形状不参与）----
        # 文本框 ≠ 墨迹：text 参与重叠时按 text_ink_ratio / text_ink_v
        # 收窄有效宽高（左对齐/顶端对齐假设；右对齐文本会少报，属可接受边界）。
        boxes = []
        source_zone = s.get("source_zone")
        for e in s.get("elements", []):
            if not isinstance(e, dict):
                continue
            if _bg_exempt(e, cw, ch):
                # 合格背景层由空间与阅读保护负责，不按内容对象计算几何冲突
                continue
            if isinstance(source_zone, dict) and e.get("role") not in {"source", "method", "metadata"}:
                try:
                    if _intersects_zone(e, source_zone):
                        add("source_zone", e.get("id", "?"), "error",
                            "主体对象侵入 source_zone；来源区必须独立保留")
                except (TypeError, ValueError):
                    pass
            if e.get("type") not in ("text", "chart", "native_chart", "image"):
                continue
            try:
                bx, by, bw, bh = _box(e, text_ink_ratio, text_ink_v)
                boxes.append((e, e.get("id", "?"), bx, by, bw, bh))
            except (TypeError, ValueError):
                continue
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                ae, _, ax, ay, aw, ah = a
                be, _, bx, by, bw, bh = b
                ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
                iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
                inter = ix * iy
                if inter <= 0:
                    continue
                smaller = min(max(aw * ah, 1.0), max(bw * bh, 1.0))
                ratio = inter / smaller
                if ratio > overlap_ratio:
                    if not _overlap_allowed(ae, be):
                        add("overlap", f"{a[1]}∩{b[1]}", "error",
                            f"有效墨迹重叠 {ratio:.0%} > 容忍 {overlap_ratio:.0%}；需拆分、缩短或重新布局")
                    else:
                        add("overlap_declared", f"{a[1]}∩{b[1]}", "hint",
                            "存在已声明的空间遮挡；发布前须以渲染证据确认未遮挡关键内容")

        # 新增克制约束：只报告，不替调用方改稿。
        if narrative_lines > narrative_lines_max:
            add("text_capacity", sid, "warn",
                f"叙事文字估算 {narrative_lines} 行 > 上限 {narrative_lines_max}；应提炼或拆页")
        if include_advisory:
            if len(alignments) > alignments_max:
                add("alignment_budget", sid, "warn",
                    f"页面使用 {len(alignments)} 种文本对齐方式 > 上限 {alignments_max}")
            if len(semantic_colors) > semantic_colors_max:
                add("color_budget", sid, "warn",
                    f"页面语义色 {len(semantic_colors)} 种 > 上限 {semantic_colors_max}（中性灰度不计）")
            if cw * ch > 0 and decoration_area / (cw * ch) > decoration_area_max:
                add("decoration_budget", sid, "warn",
                    f"装饰面积 {decoration_area / (cw * ch):.1%} > 上限 {decoration_area_max:.0%}")
            if len(icon_styles) > 1:
                add("icon_consistency", sid, "warn", "页面混用多种图标风格")
        # 背景层资格（工程事实，非预测）：伪背景 error、无保护 warn
        _check_background_qualification(s, sid, cw, ch, add)

        # ── 几何自检：三级门禁都不查元素互相遮挡，只能静态补 ──
        # 真实案例：图例(1096–1232) 与页码(1112–1232) 100% 重叠，guard / QA /
        # Critic 全数通过，人眼才发现。遮挡一旦发生，页面等于少了一处信息。
        occlusions = _geometry_occlusion(s)
        for a_id, b_id, ratio in occlusions:
            add("geom_occlude", sid, "warn",
                f"「{a_id}」与「{b_id}」重叠 {ratio:.0%}（互相遮挡，"
                f"其中一方信息实际不可读；挪开或删掉其一）")

        # ── 光学对齐：小色块与紧贴文字必须垂直居中、间距一致 ──
        _pairs = _optical_pair_alignment(s)
        _gaps = []
        for a_id, b_id, delta, gap in _pairs:
            if delta > 3:
                add("optical_alignment", sid, "warn",
                    f"色块「{a_id}」与右侧文字「{b_id}」垂直偏差 {delta:.1f}px"
                    f"（小色块/圆点与文字须光学居中，否则读作未对齐）")
            if not 4 <= gap <= 20:
                add("optical_alignment", sid, "warn",
                    f"色块「{a_id}」与文字「{b_id}」间距 {gap:.0f}px 异常"
                    f"（舒适区 4–20px）")
            else:
                _gaps.append((a_id, b_id, gap))
        if len(_gaps) >= 2 and max(g for *_, g in _gaps) - min(g for *_, g in _gaps) > 2:
            add("optical_alignment", sid, "warn",
                "页内色块-文字间距不一致（"
                + "、".join(f"「{b}」{g:.0f}px" for _, b, g in _gaps)
                + "；图例/读数对应组的间距应处处相等）")

        # ── 柱体不得穿过基线（柱底压线是编辑式图表的契约）──
        for b_id, r_id, over in _baseline_crossings(s):
            add("baseline_crossing", sid, "warn",
                f"柱体「{b_id}」底边越过基线「{r_id}」{-over:.0f}px"
                f"（柱底应与基线共边，不得穿过）")

        # ── 主张 vs 图表：标题里的百分比必须能在图上算出来 ──
        # 真实案例：标题写「自有内容 61%」，图表单位是「指数点」，68/180=37.8%，
        # 主张与证据不符；另一页「Q4 占 38%」而实际 142/486=29%。这类错误
        # 静态就能判定，不该拖到发布评审才发现。
        for cid, claim, got in _data_claim_mismatch(s):
            add("data_claim_unsupported", sid, "warn",
                "标题声称 " + str(claim) + "，但图表「" + str(cid) + "」里算不出该值"
                + (f"（最接近的是 {got}）" if got else "")
                + "；主张必须能被页内证据推出")

        if include_advisory:
            # §07 排版预算（hint 级：字号等级过碎会让层级失焦，提示收拢）
            if len(font_levels) > font_levels_max:
                add("type_budget", sid, "hint",
                    f"页面使用 {len(font_levels)} 个字号等级 > 上限 {font_levels_max}（OS §07，建议收拢层级）")
            if len(font_families) > font_families_max:
                add("type_budget", sid, "hint",
                    f"页面引用 {len(font_families)} 个字体家族 > 上限 {font_families_max}（OS §07）")

            # Accent 预算按页检查；全套平均值在页间检查后再计算。
            if cw * ch > 0 and slide_accent_area / (cw * ch) > accent_max:
                add("accent_budget", sid, "warn",
                    f"本页 Accent 面积 {slide_accent_area / (cw * ch):.1%} > 上限 {accent_max:.0%}")

        # 焦点尺度：声明焦点为文字时，应获得页内最大字号（OS「一页一焦点」）
        if include_advisory and focus_scale:
            intent = s.get("page_intent") if isinstance(s.get("page_intent"), dict) else {}
            focus_id = intent.get("focus") or s.get("focus_subject_id") or s.get("focus")
            if focus_id:
                focus_el = next((e for e in s.get("elements", [])
                                 if isinstance(e, dict) and e.get("id") == focus_id), None)
                if focus_el and focus_el.get("type") == "text":
                    try:
                        fsize = float(focus_el.get("size") or 0)
                        others = [float(e.get("size") or 0) for e in s.get("elements", [])
                                  if isinstance(e, dict) and e.get("type") == "text"
                                  and e is not focus_el]
                        if others and max(others) > fsize:
                            add("focus_scale", sid, "hint",
                                f"焦点文字 {fsize:g}px 小于页内最大文字 {max(others):g}px，"
                                f"主焦点未获得尺度优势")
                    except (TypeError, ValueError):
                        pass

        if include_advisory:
            # ---- §3.1 视觉资产引擎契约：叠加层 / 有机层 / 资产合同 ----
            # 防御性：仅当 spec 实际声明相关字段时才校验，绝不臆造缺失设计决策。
            for e in s.get("elements", []):
                if not isinstance(e, dict):
                    continue
                etyp = e.get("type")
                eid = e.get("id", "?")
                fill = e.get("fill")
                # 叠加层透明度（权威区间见 production-contract.md Background Layer Contract）
                if etyp == "shape" and isinstance(fill, dict):
                    # 兼容 Fill Contract（{"type":"gradient","stops":[...]}）与历史
                    # {"gradient":{"stops":[...]}} 两种写法
                    grad = fill if fill.get("type") == "gradient" else (
                        fill.get("gradient") if isinstance(fill.get("gradient"), dict) else None)
                    if isinstance(grad, dict):
                        for stop in (grad.get("stops") or []):
                            op = stop.get("opacity") if isinstance(stop, dict) else (
                                stop[2] if isinstance(stop, (list, tuple)) and len(stop) >= 3 else None)
                            try:
                                op = float(op) if op is not None else None
                            except (TypeError, ValueError):
                                op = None
                            if op is not None and (op > 0.80 or op < 0.10):
                                add("overlay_opacity", eid, "warn",
                                    f"gradient 叠加透明度 {op:.0%} 超出 10%–80%")
                    # 兼容 {"type":"solid","opacity":...} 与历史 {"solid_color":...}
                    if fill.get("type") == "solid" or "solid_color" in fill:
                        op = fill.get("opacity")
                        if isinstance(op, (int, float)) and (op > 0.70 or op < 0.20):
                            add("overlay_opacity", eid, "warn",
                                f"solid 叠加透明度 {op:.0%} 超出 20%–70%")
                # 有机层（organize_layer）
                ol = e.get("organic_layer")
                if ol is None and isinstance(fill, dict):
                    ol = fill.get("organic_layer")
                if isinstance(ol, dict) and ol.get("enabled", True):
                    op = ol.get("opacity")
                    if isinstance(op, (int, float)) and (op > 0.35 or op < 0.05):
                        add("organic_layer", eid, "warn",
                            f"有机层透明度 {op:.0%} 超出 5%–35%（背景引擎 §3.1）")
                    if not ol.get("purpose"):
                        add("organic_layer", eid, "warn",
                            "有机层 purpose 为空（不得为纯装饰 blob）")
                # 资产合同（仅校验已显式声明 asset 元的图像）
                asset = e.get("asset")
                if isinstance(asset, dict):
                    if not asset.get("theme_ref") and not asset.get("apc"):
                        add("asset_contract", eid, "warn",
                            "图像资产未绑定 VP 人格（theme_ref/apc 缺失），色彩可能偏离 spec.theme.colors")
                    neg = asset.get("negative") or []
                    if neg and not any(
                            k in str(x).lower()
                            for x in neg for k in ("text", "logo", "watermark")):
                        add("asset_contract", eid, "hint",
                            "资产 negative 未包含 no-text / no-logo / no-watermark 约束")

        # ---- 主题字体键（deck 级，逐页重复没意义，但每页都被它影响）----
        if si == 0:
            fonts = theme.get("fonts") if isinstance(theme.get("fonts"), dict) else None
            if not fonts:
                add("theme_fonts", "deck", "warn",
                    "theme.fonts 未声明：产物会回落 Arial / Microsoft YaHei（字体判断在产物里消失）")
            else:
                unknown = sorted(str(k) for k in fonts if str(k) not in ("cn", "latin", "display", "body"))
                if unknown:
                    add("theme_fonts", "deck", "warn",
                        f"theme.fonts 里的 {unknown} 不是被读取的键（规范键 cn / latin，"
                        f"display / body 是别名）——写了等于没写")
                if not str(fonts.get("cn") or fonts.get("body") or "").strip():
                    add("theme_fonts", "deck", "warn",
                        "theme.fonts 没有中文字族（cn/body）：中文会回落 Microsoft YaHei")
                if not str(fonts.get("latin") or fonts.get("display") or "").strip():
                    add("theme_fonts", "deck", "warn",
                        "theme.fonts 没有拉丁字族（latin/display）：拉丁与数字会回落 Arial")

        # ---- 主题约束键：写错的名字要点名（同 theme_fonts 的做法）----
        if si == 0:
            _KNOWN_CONSTRAINTS = frozenset({
                "accent_max", "max_charts", "max_colors", "font_levels_max", "font_families_max",
                "whitespace_min", "min_whitespace", "type_step_min", "decoration_area_max",
                "bg_layers_max", "bg_layer_coverage", "bold_ratio_max"})
            _unknown_cons = sorted(str(k) for k in constraints if str(k) not in _KNOWN_CONSTRAINTS)
            if _unknown_cons:
                add("theme_constraints", "deck", "warn",
                    f"theme.constraints 里的 {_unknown_cons} 不生效（可用的键："
                    f"accent_max / max_charts / max_colors / font_levels_max / font_families_max / "
                    f"whitespace_min / type_step_min / decoration_area_max / bg_layers_max / "
                    f"bold_ratio_max）——写了等于没写")

        # ---- 主题生产约束（来自 VP 主题「生产约束」章节） ----
        if max_charts is not None and chart_count > int(max_charts):
            add("theme_constraint", sid, "warn",
                f"每页图表 {chart_count} > 主题上限 {max_charts}")
        if max_colors is not None and len(page_colors) > int(max_colors):
            add("theme_constraint", sid, "hint",
                f"每页颜色 {len(page_colors)} > 主题上限 {max_colors}（仅统计引用角色/字面色）")

    # ---- 方向种子（deck 级）：方向发下来的数字约束，谁来执法 ----
    # 五个量都对得上「可执行」的定义：说得出、量得到、超了有点名。未声明不检查。
    _seed_hits: list[tuple[str, str, str, str]] = []

    def _seed(scope: str, level: str, msg: str) -> None:
        _seed_hits.append(("direction_seed", scope, level, msg))

    if cw > 0 and ch > 0:
        _area = cw * ch
        _ws_pages: list[tuple[str, float]] = []
        _bg_pages: list[tuple[str, int]] = []
        _type_gaps: list[tuple[str, float]] = []
        _bold_elems = _text_elems = 0
        for _s in slides:
            if not isinstance(_s, dict):
                continue
            _sid = str(_s.get("id", "?"))
            _rects: list[tuple[float, float, float, float]] = []
            _sizes: set[float] = set()
            _layers = 0
            for _e in (_s.get("elements") or []):
                if not isinstance(_e, dict):
                    continue
                _r = _element_rect(_e, cw, ch)
                if _r:
                    _rects.append(_r)
                    if (str(_e.get("type", "text")) != "text"
                            and _element_area(_e) / _area >= bg_layer_cov):
                        _layers += 1
                if str(_e.get("type", "text")) == "text":
                    _text_elems += 1
                    if _e.get("bold") is True or str(_e.get("weight", "")).lower() in (
                            "bold", "700", "800", "900"):
                        _bold_elems += 1
                    try:
                        _sz = float(_e.get("size") or 0)
                    except (TypeError, ValueError):
                        _sz = 0.0
                    if _sz > 0:
                        _sizes.add(_sz)
            if _rects:
                _ws_pages.append((_sid, 1.0 - _ink_union(_rects) / _area))
            if _layers:
                _bg_pages.append((_sid, _layers))
            _st = sorted(_sizes)
            if len(_st) >= 2:
                _type_gaps.append((_sid, min(b / a for a, b in zip(_st, _st[1:]) if a > 0)))

        if whitespace_min is not None and _ws_pages:
            _mean_ws = sum(w for _, w in _ws_pages) / len(_ws_pages)
            _worst = min(_ws_pages, key=lambda t: t[1])
            if _mean_ws < whitespace_min:
                _seed("deck", "warn",
                      f"留白率 {_mean_ws:.0%} < 方向下限 {whitespace_min:.0%}"
                      f"（最挤的一页是 {_worst[0]} {_worst[1]:.0%}）：元素框已经占满版面，"
                      f"要么砍内容，要么把整页拆成两页")
            else:
                _thin = [(sid_, w) for sid_, w in _ws_pages if w < whitespace_min][:3]
                if _thin:
                    _seed("deck", "hint",
                          f"留白率整体达标（均值 {_mean_ws:.0%}），但这几页低于下限 "
                          f"{whitespace_min:.0%}：" + "、".join(f"{a} {b:.0%}" for a, b in _thin))
        if bg_layers_max is not None:
            for _sid, _n in _bg_pages:
                if _n > bg_layers_max:
                    _seed(_sid, "warn",
                          f"背景层 {_n} 层（≥{bg_layer_cov:.0%} 页面积的非文字元素）"
                          f" > 上限 {bg_layers_max}：层叠越多，前景越难突出")
        if type_step_min is not None and _type_gaps:
            _sid, _g = min(_type_gaps, key=lambda t: t[1])
            if _g < type_step_min - 1e-9:
                _seed(_sid, "hint",
                      f"字号相邻级差 {_g:.2f}× < {type_step_min:.2f}×：级差太小读起来是「没对齐」"
                      f"而不是「有层级」——拉开到 {type_step_min:g}× 以上，或改用字重/墨色区分")
        if bold_ratio_max is not None and _text_elems >= 4:
            _ratio = _bold_elems / _text_elems
            if _ratio > bold_ratio_max:
                _seed("deck", "warn",
                      f"粗体占比 {_ratio:.0%} > 上限 {bold_ratio_max:.0%}"
                      f"（{_bold_elems}/{_text_elems} 个文本元素显式加粗）：全都加粗等于都没加粗，"
                      f"层级要让给字号与墨色")
    for _rule, _scope, _level, _msg in _seed_hits:
        add(_rule, _scope, _level, _msg)

    if include_advisory:
        # ---- 跨页锚（眉标 / 页码 / 证据编号）：锚不动，正文才可游走 ----
        # 每页 anchor 由 plan 发下来（家族标签 / 页码 / Fig. 编号），生成侧落成元素。
        # 这里查三件事：声明了没有落、落的位置是不是同一个、证据编号是不是连续。
        _anc_decl: list[tuple[str, dict]] = []
        _missing: list[str] = []
        _eb_pos: list[tuple[float, float]] = []
        _pn_pos: list[tuple[float, float]] = []
        _figures: list[tuple[str, str]] = []
        for s in slides:
            if not isinstance(s, dict):
                continue
            sid = str(s.get("id", "?"))
            anc = s.get("anchor")
            if not isinstance(anc, dict) or not anc:
                continue
            _anc_decl.append((sid, anc))
            elems = [e for e in (s.get("elements") or []) if isinstance(e, dict)]
            role_elems = lambda r: [e for e in elems if str(e.get("role", "")) == r]  # noqa: E731
            has_visual = any(str(e.get("type", "")) in ("chart", "native_chart", "image")
                             for e in elems)
            if anc.get("eyebrow"):
                cand = role_elems("eyebrow")
                if not cand:
                    _missing.append(f"{sid} 眉标")
                else:
                    for e in cand:
                        try:
                            _eb_pos.append((float(e.get("x", 0)), float(e.get("y", 0))))
                        except (TypeError, ValueError):
                            pass
                    want = str(anc["eyebrow"]).strip().upper()
                    if not any(str(e.get("text", "")).strip().upper() == want for e in cand):
                        add("deck_anchor", sid, "warn",
                            f"眉标与声明不一致：声明「{anc['eyebrow']}」，实际 "
                            f"{[str(e.get('text', ''))[:24] for e in cand]}——眉标是导航，"
                            f"必须用 plan 给的词汇表原文")
            if anc.get("page_number") is not None:
                cand = role_elems("page_number")
                if not cand:
                    _missing.append(f"{sid} 页码")
                else:
                    for e in cand:
                        try:
                            _pn_pos.append((float(e.get("x", 0)), float(e.get("y", 0))))
                        except (TypeError, ValueError):
                            pass
                    want = str(anc["page_number"]).strip()
                    if not any(str(e.get("text", "")).strip() == want for e in cand):
                        add("deck_anchor", sid, "warn",
                            f"页码与声明不一致：声明 {want}，实际 "
                            f"{[str(e.get('text', ''))[:12] for e in cand]}")
            if anc.get("figure"):
                _figures.append((sid, str(anc["figure"])))
                if has_visual:
                    fig = str(anc["figure"]).strip()
                    if not any(str(e.get("text", "")).strip().startswith(fig) for e in elems):
                        _missing.append(f"{sid} 证据编号 {fig}")

        if _missing:
            add("deck_anchor", "deck", "warn",
                f"声明了锚但没有落到页面上：{'、'.join(_missing[:6])}"
                + ("…" if len(_missing) > 6 else "")
                + "——锚不是装饰，缺一页就断链")
        if len({(round(x, 3), round(y, 3)) for x, y in _eb_pos}) > 1:
            add("deck_anchor", "deck", "warn",
                f"眉标落在 {len({(round(x, 3), round(y, 3)) for x, y in _eb_pos})} 个不同位置"
                f"（{sorted({(round(x), round(y)) for x, y in _eb_pos})}）：眉标要固定上缘，"
                f"位置一动，读者就得每页重新找它")
        if _eb_pos and min(y for _, y in _eb_pos) > 0.12 * ch:
            add("deck_anchor", "deck", "hint",
                f"眉标最低一处在 y={min(y for _, y in _eb_pos):.0f}（> 12% 页高）："
                f"眉标属于页面家具，习惯在上缘")
        if len({(round(x, 3), round(y, 3)) for x, y in _pn_pos}) > 1:
            add("deck_anchor", "deck", "warn",
                f"页码落在 {len({(round(x, 3), round(y, 3)) for x, y in _pn_pos})} 个不同位置"
                f"（{sorted({(round(x), round(y)) for x, y in _pn_pos})}）：页码要固定象限")
        if len(_figures) >= 2:
            nums = []
            for _sid, label in _figures:
                m = re.search(r"(\d+)", label)
                nums.append(int(m.group(1)) if m else None)
            if None not in nums and nums != list(range(nums[0], nums[0] + len(nums))):
                add("deck_anchor", "deck", "warn",
                    f"证据编号不连续：{[l for _, l in _figures]}——编号断链会让「还有没有证据」"
                    f"变成猜谜；按页序重编 01…N")

        if len(animation_types) > animation_types_max:
            add("animation_budget", "deck", "warn",
                f"全套动画/切换类型 {len(animation_types)} 种 > 上限 {animation_types_max}")

        # ---- 色彩系统纪律（deck 级）：单页合规不等于全套成套 ----
        if len(deck_hues) > hue_families_max:
            add("palette_discipline", "deck", "warn",
                f"全套使用 {len(deck_hues)} 个色相族（{HUE_BUCKET:.0f}° 一档）> 上限 "
                f"{hue_families_max}；颜色已不成系统——收拢为一组主辅色 + 一个强调色")
        pal = theme.get("colors") or {}
        acc = _hls(pal.get("accent"))
        if acc:
            for role in ("primary", "secondary"):
                gap = _hue_gap(acc, _hls(pal.get(role)))
                if gap is not None and gap < accent_hue_min:
                    add("palette_discipline", f"theme.{role}", "warn",
                        f"accent {pal.get('accent')} 与 {role} {pal.get(role)} 色相差 "
                        f"{gap:.0f}° < {accent_hue_min:.0f}°：强调色与主色同族，页面拿不到"
                        f"「唯一重点」信号——把强调色移出色相族，或改由明度/尺度承担强调")
        for kind, rec in sorted(chart_styles.items()):
            if len(rec["pages"]) < 2:
                continue
            sizes = rec["sizes"]
            if len(sizes) > 1:
                lo, hi = min(sizes), max(sizes)
                if lo > 0 and hi / lo > chart_label_scale_tol:
                    add("chart_style_drift", kind, "warn",
                        f"{kind} 出现在 {len(rec['pages'])} 页但标签字号 "
                        f"{lo:g}–{hi:g}px（>{chart_label_scale_tol:g}×）：同一图表类型应共用"
                        f"一套标签规格，差异只会读成没对齐")
            if len(rec["legend"]) > 1:
                add("chart_style_drift", kind, "hint",
                    f"{kind} 的图例开关在不同页不一致（{sorted(rec['legend'])}）：统一为全开或全关")

    # ---- 事实/口径跨页一致性（业务级，deck 级）：同一指标的单位/期间/口径必须全 deck 一致 ----
    # 单页各自合规、跨页口径打架，是金融/董事会材料最隐蔽也最致命的错误：
    # 「营收 Q1 用万元、Q3 用亿元」「2026 与 FY26 混用」这类，确定性检查可以抓。
    by_metric: dict[str, dict] = {}
    for m in chart_meta:
        by_metric.setdefault(m["metric"], {}).setdefault("units", set()).add(m["unit"])
        by_metric.setdefault(m["metric"], {}).setdefault("periods", set()).add(m["period"])
        by_metric.setdefault(m["metric"], {}).setdefault("basis", set()).add(m["basis"])
        by_metric[m["metric"]].setdefault("slides", []).append(m["slide"])
    for metric, rec in sorted(by_metric.items()):
        units = {u for u in rec["units"] if u}
        periods = {p for p in rec["periods"] if p}
        basis = {b for b in rec["basis"] if b}
        if len(units) > 1:
            add("metric_consistency", f"metric:{metric}", "error",
                f"指标「{metric}」跨页单位不一致 {sorted(units)}："
                f"同一指标必须同一单位，否则读成两套数字")
        if len(periods) > 1:
            add("metric_consistency", f"metric:{metric}", "warn",
                f"指标「{metric}」跨页期间口径不一致 {sorted(periods)}："
                f"确认是否确实要对比不同期间（若是，应在 basis 中声明比较口径）")
        if len(basis) > 1:
            add("metric_consistency", f"metric:{metric}", "hint",
                f"指标「{metric}」跨页比较口径不一致 {sorted(basis)}，建议统一或显式声明差异")

    # ---- 可读性底线：弱化文字（muted / secondary）对背景的对比度 ----
    # 刻度、注释、来源通常由 muted 承担；对比不足时整页"隐性不可读"，
    # 这是最常见也最容易被忽略的质量漏洞。只报告，不替调用方改色。
    # 两条线合成一条口径：hint = 3:1（契约文档承诺的线）、warn = 1.8:1（真读不出来）。
    # 旧实现 hint 从 2.5:1 起，2.5–3.0 之间静默放过——正是"看着还行、投影上消失"的灰。
    # 只判**可能在承载文字**的 token：与 ink 同侧的才算字，另一侧是面/影
    # （深底主题的 secondary 就是深面，拿它当字才不该通过）。
    _colors = theme.get("colors") or {}
    _bg = _colors.get("background")
    _weak_roles = _weak_text_roles(theme, slides)
    if isinstance(_bg, str) and _bg.startswith("#"):
        for _role in sorted(_weak_roles):
            _fg = _colors.get(_role)
            if not (isinstance(_fg, str) and _fg.startswith("#")):
                continue
            try:
                _k = contrast(_fg, _bg)
            except Exception:
                continue
            if _k < 1.8:
                add("contrast", f"theme.{_role}", "warn",
                    f"{_role} {_fg} 对背景对比 {_k:.1f}:1 < 1.8:1，"
                    f"刻度/注释将不可读（建议加深至 ≥3:1）")
            elif _k < 3.0:
                add("contrast", f"theme.{_role}", "hint",
                    f"{_role} {_fg} 对背景对比 {_k:.1f}:1 < 3:1：做装饰位没问题，"
                    f"做文字（刻度/注释/小字）会消失，换 ink/primary 或加深该 token")

    if include_advisory:
        # ---- Accent 面积汇总 ----
        canvas_area = cw * ch
        if canvas_area > 0:
            ratio = accent_area / (canvas_area * max(len(slides), 1))
            if ratio > accent_max:
                add("accent_budget", "deck", "warn",
                    f"全套平均 Accent 面积 {ratio:.1%} > 上限 {accent_max:.0%}（OS §06/§21）")

    if include_advisory:
        # ---- §12 跨页节奏：连续页面不得同密度 ----
        # 只在**声明与结构同时重复**时提示：那是一个可测的冗余信号（连着两页
        # 同权重），提示作者换构图算子或留白。反过来「声明变了但结构计数没变」
        # 不发——结构密度是元素构成代理，量不出真实留白（实测：大留白的英雄页
        # 会被计成 dense、97% 空白的文字页会被计成 overloaded），拿它去质疑
        # 作者的密度声明等于让作者为一个测不准的数改稿；而「渲染后复核真实留白」
        # 是静态工具给不出的证据，属设计判断，归 design-craft.md 与像素复核。
        if check_rhythm and len(slides) > 1:
            prev_struct = prev_declared = None
            for si, s in enumerate(slides):
                if not isinstance(s, dict):
                    prev_struct = prev_declared = None
                    continue
                intent = s.get("page_intent") if isinstance(s.get("page_intent"), dict) else {}
                declared = intent.get("density") or s.get("density")
                cur, _ = _density_class(s)
                if prev_struct is not None and cur == prev_struct and declared == prev_declared:
                    add("rhythm", s.get("id", f"slide_{si}"), "hint",
                        f"连续页面同为 {cur} 密度（OS §12，可拆页/换构图算子/加留白）")
                prev_struct, prev_declared = cur, declared


    # 设计契约条目：标为 advisory（不进门槛）——它们进报告、进证据，不进任何分数。
    # 验证层不评分：打分等于用固定阈值重新裁决设计好坏，那是 Art Director 的职责。
    for c in checks:
        if c.get("rule") in DESIGN_RULES:
            c["advisory"] = True
    return {
        "passed": not any(c["level"] == "error" for c in checks),
        "checks": checks,
        "advisory_rules": sorted(DESIGN_RULES),
        "warnings": warnings,
        # 可报告的对齐/行长事实：比率本身不扣分（新提示族不得计分），供人复核
        "grid": {**grid_stats,
                 "adherence": (round(grid_stats["aligned"] / grid_stats["checked"], 3)
                               if grid_stats["checked"] else None)},
        "line_measure": dict(measure_stats),
    }






# ══════════════════ Normalizer（机械归一化 · 生产链第 0 级）══════════════════
# 原 normalizer 模块整体并入：治理层统一 CLI 为 guard.py（normalize 是其第一步）。

SPACING_STEP = 4
_COLOR_FIELDS = ("color", "background", "border_color", "stroke", "accent",
                 "fill_color", "track_color", "label_color")
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_REPORT_ITEM_CAP = 200   # 报告逐条明细上限（统计仍完整，防止巨型 spec 刷屏）
def _snap_pos(value: float, grid: int) -> int:
    """位置就近吸附（round-half-up，与版心设计的取整方向一致）。"""
    return int(math.floor(float(value) / grid + 0.5)) * grid
def _snap_size(value: float, grid: int) -> int:
    """尺寸向上吸附：只增不减，防止吸附后文字/图表溢出容器。"""
    v = float(value)
    n = math.ceil(v / grid) * grid
    return int(n) if n >= v else int(n) + grid  # 浮点边界：ceil(64.0/8)*8==64 直接命中
def _canonical_color(value: Any, tokens: dict[str, str]) -> tuple[Any, str | None]:
    """色彩值 → (规范值, 规则名)。tokens: {token名: 规范hex}。
    规则：token 别名（大小写/空白）→ 规范 token 名；hex → 大写规范形；
    与主题色完全同值的 hex → token 名（让「同一颜色」在 spec 里只有一个名字）。"""
    if not isinstance(value, str):
        return value, None
    raw = value.strip()
    if not raw:
        return value, None
    # ① token 别名 → 规范 token 名
    for name in tokens:
        if raw.lower() == name.strip().lower():
            return (name, "color_token_alias") if raw != name else (value, None)
    # ② hex → 规范大写形
    if _HEX_RE.match(raw):
        upper = raw.upper()
        # ③ 与主题色同值的 hex → token 名（单一事实来源）
        for name, hexv in tokens.items():
            if isinstance(hexv, str) and _HEX_RE.match(hexv.strip()) \
                    and hexv.strip().upper() == upper:
                return name, "color_hex_to_token"
        return (upper, "color_hex_case") if upper != raw else (value, None)
    return value, None
def _canonical_font(value: Any, families: list[str]) -> tuple[Any, str | None]:
    """字体声明 → 主题声明族名的规范拼写（大小写/空白差异归一）。"""
    if not isinstance(value, str) or not families:
        return value, None
    raw = value.strip()
    for fam in families:
        if raw.lower() == str(fam).strip().lower():
            return (fam, "font_token_alias") if raw != fam else (value, None)
    return value, None
def _normalize_once(spec: dict, *, grid: bool, colors: bool, fonts: bool,
                    spacing: bool) -> tuple[dict, dict[str, int], list[dict], list[dict]]:
    """单趟归一化（纯函数）：返回 (新 spec, 分规则计数, 逐条明细, 未解析项)。"""
    src = copy.deepcopy(spec)
    items: list[dict] = []
    by_rule: dict[str, int] = {}
    unresolved: list[dict] = []

    canvas = (src.get("canvas") or {})
    grid_unit = int(canvas.get("grid_unit") or GRID_UNIT)
    if grid_unit <= 0:
        grid_unit = GRID_UNIT
    # spec 级开关：normalization: {"grid": false} 整体关闭网格吸附
    spec_opt = (src.get("normalization") or {})
    do_grid = grid and spec_opt.get("grid", True) is not False

    theme = (src.get("theme") or {})
    color_tokens: dict[str, str] = {}
    if colors:
        for k, v in (theme.get("colors") or {}).items():
            if isinstance(k, str) and isinstance(v, str):
                color_tokens[k.strip()] = v.strip()
    font_families: list[str] = []
    if fonts:
        seen: set[str] = set()
        for v in (theme.get("fonts") or {}).values():
            if isinstance(v, str) and v.strip():
                key = v.strip().lower()
                if key not in seen:
                    seen.add(key)
                    font_families.append(v.strip())

    def _record(slide_id: str, el_id: str | None, field: str,
                old: Any, new: Any, rule: str) -> None:
        by_rule[rule] = by_rule.get(rule, 0) + 1
        if len(items) < _REPORT_ITEM_CAP:
            items.append({"slide": slide_id, "id": el_id, "field": field,
                          "from": old, "to": new, "rule": rule})

    def _normalize_element(slide_id: str, el: dict) -> None:
        el_id = el.get("id")
        # ① 网格吸附：只碰几何四元组，绝不碰语义
        if do_grid and not el.get("grid_exempt"):
            for f in ("x", "y"):
                v = el.get(f)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    snapped = _snap_pos(v, grid_unit)
                    if snapped != v:
                        _record(slide_id, el_id, f, v, snapped, "grid_snap")
                        el[f] = snapped
            # 发丝线（任一维 ≤2px）：视觉重量必须保留——_snap_size 只增不减，
            # 会把 1px 细线抬成 8px 色块。仅位置吸附网格，尺寸绝不吸附，
            # 与 §02.1 网格检查的发丝线四维豁免同一口径。
            _thin = False
            try:
                _thin = (float(el.get("width")) <= 2
                         or float(el.get("height")) <= 2)
            except (TypeError, ValueError):
                pass
            if not _thin:
                for f in ("width", "height"):
                    v = el.get(f)
                    if not isinstance(v, (int, float)) or isinstance(v, bool):
                        continue
                    if el.get("type") == "shape":
                        # 形状柱/色块按「远边就近吸附」取尺寸：与基线/邻块
                        # 共享的边保持精确对齐（柱底压线这类细节的根因修复）；
                        # 吸附后不足一格才回退只增不减。
                        #
                        # 基准必须是**位置吸附后**的原点（x/y 已在上一步吸附完），
                        # 不能混用吸附前的旧边：混用时 far 按旧边选格、长度却减去
                        # 新边，块体会被静默缩小最多 7px（违反本节「只增不减」），
                        # 且缩小量与画布相位有关、不可预期。selftest.hairline_grid
                        # 的 block 用例锁的正是这条（301×87 → 304×88，而非 304×80）。
                        axis = "y" if f == "height" else "x"
                        base = el.get(axis)
                        if isinstance(base, (int, float)) and not isinstance(base, bool):
                            far = _snap_pos(float(base) + float(v), grid_unit)
                            snapped = far - float(base)
                            if snapped < grid_unit:
                                snapped = _snap_size(v, grid_unit)
                            snapped = int(snapped)
                        else:
                            snapped = _snap_size(v, grid_unit)
                    else:
                        # 文本/图表容器：只增不减，防溢出
                        snapped = _snap_size(v, grid_unit)
                    if snapped != v:
                        _record(slide_id, el_id, f, v, snapped, "grid_snap_size")
                        el[f] = snapped
        # ② 色彩 token 归一
        if colors and color_tokens:
            for f in _COLOR_FIELDS:
                if f not in el:
                    continue
                new, rule = _canonical_color(el.get(f), color_tokens)
                if rule:
                    _record(slide_id, el_id, f, el.get(f), new, rule)
                    el[f] = new
            fill = el.get("fill")
            if isinstance(fill, dict) and "color" in fill:
                new, rule = _canonical_color(fill.get("color"), color_tokens)
                if rule:
                    _record(slide_id, el_id, "fill.color", fill.get("color"), new, rule)
                    fill["color"] = new
        # ③ 字体 token 归一
        if fonts and font_families:
            for f in ("font", "font_family"):
                if f not in el:
                    continue
                new, rule = _canonical_font(el.get(f), font_families)
                if rule:
                    _record(slide_id, el_id, f, el.get(f), new, rule)
                    el[f] = new
                elif isinstance(new, str) and new.strip() and rule is None \
                        and new.strip().lower() not in {x.lower() for x in font_families}:
                    unresolved.append({"slide": slide_id, "id": el_id, "field": f,
                                       "value": new, "kind": "font_not_in_theme"})
        # ④ 微间距吸附（padding → 4 的倍数）
        if spacing:
            v = el.get("padding")
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                snapped = int(math.ceil(float(v) / SPACING_STEP)) * SPACING_STEP
                if snapped != v:
                    _record(slide_id, el_id, "padding", v, snapped, "spacing_snap")
                    el["padding"] = snapped

    for slide in (src.get("slides") or []):
        if not isinstance(slide, dict):
            continue
        slide_id = slide.get("id")
        for el in (slide.get("elements") or []):
            if isinstance(el, dict):
                _normalize_element(str(slide_id), el)
    return src, by_rule, items, unresolved
def normalize_spec(spec: dict, *, grid: bool = True, colors: bool = True,
                   fonts: bool = True, spacing: bool = True) -> tuple[dict, dict]:
    """spec → (归一化 spec, 归一化报告)。纯函数：不改入参，返回深拷贝。

    报告结构：
        applied          是否发生了修改
        hash_before/after 归一化前后指纹（发布链自证用）
        changed / by_rule 修改总数与分规则计数
        items            逐条明细（slide/id/field/from/to/rule，封顶 200 条）
        idempotent       内置二次归一化校验（必须为 True）
        unresolved       无法归一但值得注意的项（如未在主题声明的字体），只记录不改
    """
    # 在复制/扫描前只计算一次输入指纹；无变更时输出指纹必然相同，避免
    # 再做一次完整 JSON 序列化。
    hash_before = spec_fingerprint(spec)
    src, by_rule, items, unresolved = _normalize_once(
        spec, grid=grid, colors=colors, fonts=fonts, spacing=spacing)
    changed = sum(by_rule.values())
    # 没有任何修改时，结果与输入相同，幂等性已由定义保证；不再为每轮
    # 高密度 deck 做第二次 deepcopy + 全字段扫描。发生修改时仍保留完整二次校验。
    if changed:
        _, by_rule_2, _, _ = _normalize_once(
            src, grid=grid, colors=colors, fonts=fonts, spacing=spacing)
        idempotent = sum(by_rule_2.values()) == 0
    else:
        idempotent = True
    report = {
        "applied": changed > 0,
        "hash_before": hash_before,
        "hash_after": hash_before if not changed else spec_fingerprint(src),
        "changed": changed,
        "by_rule": by_rule,
        "items": items,
        "idempotent": idempotent,
        "unresolved": unresolved[:_REPORT_ITEM_CAP],
    }
    return src, report
