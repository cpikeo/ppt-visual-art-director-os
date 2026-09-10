#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structured, read-only art criticism for PPT specs (v3).

**职责边界（vNext）：Critic 只回答「这套设计有没有高级价值」，不回答
「这份 PPT 能不能正确交付」。** 后者是 QA（工程验证层）的唯一职责。

  管：视觉层级 · 空间节奏 · 信息焦点 · 审美一致性 · 品牌气质 · 记忆点
  不管（一律交给 QA）：overflow · 重叠 · 越界 · 安全区 · 字体大小/字阶数量 ·
        对比度硬底线 · 圆角容器计数 · 渲染完整性
  因此这些**不再出现在 Critic 的 hard_gates 里**：READABILITY_FAIL /
  BACKGROUND_DISGUISED / MEDIA_UNJUSTIFIED / CARD_WALL / RHYTHM_FLAT。
  它们仍作为「设计扣分证据」存在（卡片墙、图无功能、伪背景都伤审美），
  但发布判定只由 QA 的失败码决定——同一件事不由两层各判一次。
  渲染像素证据只用于**加分**（做对了才承认）：Critic 不用像素做工程扣罚，
  那是 QA 的确定性判据；两套口径互相拆台是上一版的主要复杂度来源。

评分模型（相对 v1）：
  * 每个维度从基准分 3（「达到声明契约」）出发，凭**可观察证据**加/扣分
    （delta ∈ [-2, +2]，最终钳制到 0–5）。v1 只扣不加，满分被数学性封顶
    在 80/100，PASS(≥90) 永远不可达——v2 修复了该缺陷。
  * 每个 delta 都写入 dimension_evidence，评分可逐条溯源复核。
  * hard_gates 只保留设计判断类的真实码：FOCUS_COMPETING / INTENT_UNCLEAR /
    CRITIC_LOW（维度 <3/5），并携带 production-contract.md 失败码表口径。

本模块依然是启发式：审美判断不能化简为像素分数。它只把可观察结构、
页面意图契约和可选渲染证据转成可追踪的批评。
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

from primitives import (DEFAULT_WIDTH, DEFAULT_HEIGHT, contrast, spec_fingerprint,
                         bg_coverage, bg_overlay_opacity, is_background_declared,
                         rounded_containers, text_contrast_verdict)

DIMENSIONS = (
    "visual_hierarchy", "balance", "alignment", "contrast",
    "rhythm", "consistency", "emotional_impact", "memorability",
    "professional_quality",
)
WEIGHTS = {
    "visual_hierarchy": 20, "balance": 15, "alignment": 10,
    "contrast": 10, "rhythm": 10, "consistency": 10,
    "emotional_impact": 10, "memorability": 10, "professional_quality": 5,
}
BASELINE = 3          # 基准分：满足「声明契约」的最低审美合格线
PASS_SCORE = 90       # deck_score >= 90 才允许 PASS（与 production-contract 一致）
# 评分行为版本：3.0 = 职责分离（工程判定交还 QA、像素证据只做加分、门控瘦身）。
# 跨版本分数不可比；它只是报告上的戳，不再参与任何缓存失效逻辑
# （vNext 已删除 Critic 结果缓存，因此不需要版本闸）。
CRITIC_VERSION = "3.1"
CAPTION_ROLES = {"caption", "annotation", "source", "label", "axis",
                 "data_label", "legend", "metadata", "method"}
MEDIA_ROLES = {"hero", "emotion", "proof", "context"}
STATEMENT_SIZE = 40   # 超过该字号的文字视为 Statement 级记忆锚点
FOCUS_LEAD = 1.25     # 焦点文字需领先第二大文字的比例（否则视为同级竞争信号）
MEDIA_CHART_MAX = 2   # 每页媒体/图表对象上限（超过即竞争性视觉信号）
TEXT_MAX = 8          # 每页文本对象上限（超过即碎片化阅读）
ROUNDED_MAX = 4       # 圆角容器上限（超过即卡片墙风险）
LR_SPLIT_MAX = 0.45   # 左右墨迹面积失衡阈值（未声明非对称构图时）
# 版面轴线：中线 / 三分线 / 1/4 线 / 黄金分割线。guard 预检与这里的评分共用一份常量，
# 因此「提示对齐」与「给对齐加分」永远不会变成两套标准。
AXIS_TOLERANCE = 0.045
AXIS_LINES = (0.25, 1 / 3, 0.5, 2 / 3, 0.75)
GOLDEN_LINES = (0.382, 0.618)
AXIS_NAMES = {0.25: "1/4 线", 1 / 3: "三分线", 0.5: "中线", 2 / 3: "三分线",
              0.75: "1/4 线", 0.382: "黄金分割线", 0.618: "黄金分割线"}
# ── 视觉层级预算（原先内联在评分分支里；抽出后 guard.py 预检与 critic 评分共享同一口径，
#    不再需要代理去读源码才知道门槛。改这里即同时改变评分与预检，不会出现两套标准。）
MEDIA_BUDGET_MAX = 1   # 每页争夺注意力的媒体上限：≤1 时判定为「焦点无同级竞争者」
TEXT_BUDGET_MAX = 4    # 每页「阅读文本」上限（低权重来源/图例不计入，见 _reading_texts）
FOCUS_AREA_LEAD = 2.0  # 其他元素面积不得超过焦点面积的倍数
# 背景层资格：声明 layer=background 只是意图，必须真的「承载空间」才享受免检，
# 否则任何内容图都能靠一个标签同时躲开媒体预算与遮挡检查。
BG_MIN_COVERAGE = 0.60          # 至少覆盖 60% 画布面积
BG_MIN_PROTECT_OPACITY = 0.20   # 内容保护层最低不透明度
# 行长（measure）：排版质量的最小可测代理
LINE_MEASURE_CJK_MAX = 38       # 每行 CJK 字数上限（编辑式排版经验值 22–38）
LINE_MEASURE_LATIN_MAX = 75     # 每行拉丁字符上限
LINE_MEASURE_FAIL_FACTOR = 2.0  # 超过上限 2× 视为不可读
RHYTHM_INK_DELTA = 0.10    # 相邻页实测占用率差 ≥0.10 视为节奏成立
RHYTHM_INK_FLAT = 0.03     # 标签变了但占用率差 ≤0.03 视为空转
TEXT_CONTRAST_FAIL = 3.0   # 渲染实测文字对比度低于此值 → 阻断（叠加不可读）
TEXT_CONTRAST_WARN = 4.5   # WCAG AA 正文门槛
ASYMMETRIC_GRAMMARS = {"soft_asymmetry", "cinematic_stage", "path_sequence"}
ANCHOR_DRIFT = 0.18   # 几何重心与声明锚点的归一化偏移阈值（无渲染证据时）

# art_critic 期望从 render_check 消费的字段子集（render_check.PAGE_FIELDS 的子集）。
# 这是 render_check ↔ art_critic 的显式契约——只读这一份就知道 critic 用
# 了什么渲染证据。新增渲染字段时不需要更新这里；删除渲染字段时必须同步
# 移除本表对应评分逻辑，避免出现"该字段已删但 critic 还在读"的 KeyError。
CONSUMED_RENDER_FIELDS = frozenset({
    "gravity_drift",         # balance：渲染质心与声明锚点漂移
    "edge_kurtosis_x",       # alignment：横向 sobel 投影峰度
    "edge_kurtosis_y",       # alignment：纵向 sobel 投影峰度
    "accent_pixel_ratio",    # contrast + visual_hierarchy：Accent 稀缺性
    "occupancy",             # rhythm：声明 vs 渲染密度对照
    "brightness",            # emotional_impact：场景亮度合理性
    "saturated_pixel_ratio", # emotional_impact：编辑式安静判定辅助
})


def _elements(slide: dict) -> list[dict]:
    return [e for e in slide.get("elements", []) if isinstance(e, dict)]


def _intent(slide: dict) -> dict:
    return slide.get("page_intent") if isinstance(slide.get("page_intent"), dict) else {}


def _field(slide: dict, key: str, default=None):
    """page_intent 优先，兼容字段直接挂在 slide 顶层的历史写法。"""
    intent = _intent(slide)
    v = intent.get(key)
    return v if v not in (None, "") else (slide.get(key) if slide.get(key) not in (None, "") else default)


def _canvas(spec: dict) -> tuple[float, float]:
    c = spec.get("canvas") or {}
    return float(c.get("width", DEFAULT_WIDTH)), float(c.get("height", DEFAULT_HEIGHT))


def _num(e: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(e.get(key, default))
    except (TypeError, ValueError):
        return default


def _area(e: dict) -> float:
    return max(0.0, _num(e, "width")) * max(0.0, _num(e, "height"))


def _content_occupancy(elems: list[dict], cw: float, ch: float) -> float:
    """内容几何占用率 = Σ(非背景元素 bbox 面积) / 画布面积。

    density 的「留白」语义是「视觉密度」——内容对象占用的视觉空间，故用几何
    占用率（= 1 - 留白率）。不用墨迹率 occupancy：细线/细柱图表的墨迹像素
    天然极低（一条占画布 70% 的折线，墨迹率可能只有 8%），会系统性低估图表页
    的视觉密度。墨迹率仍由 min_whitespace / 跨页 ink_shift 各自承担。
    """
    area = sum(_area(e) for e in elems if not bg_exempt(e, cw, ch))
    return min(1.0, area / max(1.0, cw * ch))


def _ink_area(e: dict) -> float:
    """文本框≠墨迹：正文按 0.55×0.70 折算可见墨迹面积。"""
    if e.get("type") == "text":
        return _area(e) * 0.55 * 0.70
    return _area(e)


def _center(e: dict) -> tuple[float, float]:
    return (_num(e, "x") + _num(e, "width") / 2,
            _num(e, "y") + _num(e, "height") / 2)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _focus_element(slide: dict) -> tuple[dict | None, str | None]:
    focus = _field(slide, "focus") or slide.get("focus_subject_id")
    if not focus:
        return None, focus
    for e in _elements(slide):
        if e.get("id") == focus:
            return e, focus
    return None, focus


def _theme_colors(spec: dict) -> dict:
    return dict((spec.get("theme") or {}).get("colors") or {})


def _hex_contrast(colors: dict, fg: str, bg: str) -> float | None:
    a, b = colors.get(fg), colors.get(bg)
    if isinstance(a, str) and a.startswith("#") and isinstance(b, str) and b.startswith("#"):
        try:
            return float(contrast(a, b))
        except Exception:
            return None
    return None


def _alignment_stats(elems: list[dict]) -> dict:
    """内容对象左缘/顶缘的共享轴线统计（编辑式光学对齐的结构代理）。

    左缘收束（共用装订线）与顶缘成组是编辑排版中最可观察的对齐行为；
    右缘随文本宽度自然离散，不参与轴线判定，避免误报。
    """
    left, top = Counter(), Counter()
    for e in elems:
        if e.get("type") not in ("text", "chart", "native_chart", "image", "shape"):
            continue
        left[int(round(_num(e, "x")))] += 1
        top[int(round(_num(e, "y")))] += 1
    n = max(1, sum(left.values()))
    left_cluster = max(left.values()) if left else 0
    top_cluster = max(top.values()) if top else 0
    return {"objects": n, "distinct_left": len(left), "distinct_top": len(top),
            "left_cluster": left_cluster, "top_cluster": top_cluster}


def _grid_bias_stats(elems: list[dict], cw: float | None = None,
                     ch: float | None = None) -> tuple[int, int]:
    """8 单位网格对齐：返回 (对齐对象数, 参与判定的对象数)。

    豁免与 guard 的 grid 规则同口径：发丝线（任一边 ≤2px）与通栏元素（边长=画布）
    的位置由「居中一条线 / 铺满」决定，按 8 倍数要求它是伪误差，既不该扣分也不该
    计入分母——否则同一件事在 guard 是豁免、在审美是扣分，两套口径互相拆台。
    """
    content = [e for e in elems if e.get("type") in
               ("text", "chart", "native_chart", "image", "shape")]

    def exempt(e: dict) -> bool:
        w, h = _num(e, "width"), _num(e, "height")
        if w <= 2 or h <= 2:
            return True
        for side, canvas in ((w, cw), (h, ch)):
            if canvas and abs(side - float(canvas)) < 1:
                return True
        return False

    pool = [e for e in content if not exempt(e)]
    ok = 0
    for e in pool:
        vals = [_num(e, k) for k in ("x", "y", "width", "height")]
        if all(abs(v - 8 * round(v / 8)) <= 1 for v in vals):
            ok += 1
    return ok, len(pool)


def _lr_split(elems: list[dict], cw: float) -> float:
    """左右半幅墨迹面积失衡度 0–1（0=完全均衡）。"""
    left = sum(_ink_area(e) for e in elems if _center(e)[0] < cw / 2)
    right = sum(_ink_area(e) for e in elems if _center(e)[0] >= cw / 2)
    total = left + right
    if total <= 0:
        return 0.0
    return abs(left - right) / total


def _mass_centroid(elems: list[dict], cw: float, ch: float) -> tuple[float, float] | None:
    """墨迹面积加权质心（归一化 0–1）。"""
    total = 0.0
    mx = my = 0.0
    for e in elems:
        if e.get("type") not in ("text", "chart", "native_chart", "image"):
            continue
        w = _ink_area(e)
        cx, cy = _center(e)
        total += w
        mx += cx * w
        my += cy * w
    if total <= 0:
        return None
    return mx / total / cw, my / total / ch


def _axis_hit(el: dict, cw: float, ch: float) -> tuple[str, str] | None:
    """元素中心是否落在版面上：命中返回 (坐标, 轴线名)。任一轴对齐即算落位有意图——
    编辑式版面常把焦点钉在某一列上而让另一轴自由，那是语法，不是失误。"""
    try:
        pts = (("x", (float(el.get("x") or 0) + float(el.get("width") or 0) / 2) / max(cw, 1)),
               ("y", (float(el.get("y") or 0) + float(el.get("height") or 0) / 2) / max(ch, 1)))
    except (TypeError, ValueError):
        return None
    for axis, v in pts:
        for a in AXIS_LINES + GOLDEN_LINES:
            if abs(v - a) <= AXIS_TOLERANCE:
                return (f"{axis}={v:.3f}", AXIS_NAMES.get(a, "版面轴线"))
    return None


def _declared_anchor(slide: dict, cw: float, ch: float) -> tuple[float, float, float] | None:
    """page_intent.gravity_anchor → 归一化 (x, y, radius)；兼容像素与归一化两种声明。"""
    ga = _field(slide, "gravity_anchor")
    if not isinstance(ga, dict):
        return None
    try:
        x, y = float(ga.get("x")), float(ga.get("y"))
        r = float(ga.get("radius", 0.18 * max(cw, ch)))
        if 0 <= x <= 1 and 0 <= y <= 1:
            rx = r if r > 1 else r / max(cw, ch)
            return x, y, min(1.0, max(0.02, rx))
        return x / cw, y / ch, min(1.0, max(0.02, r / max(cw, ch)))
    except (TypeError, ValueError):
        return None


def _memory_anchor(slide: dict) -> str | None:
    """识别页面可复现的视觉记忆锚点（可观察，不臆造）。"""
    elems = _elements(slide)
    kinds = []
    spark_count = 0
    for e in elems:
        if e.get("type") == "text" and _num(e, "size") >= STATEMENT_SIZE:
            kinds.append(f"statement 尺度({_num(e, 'size'):.0f}px)")
        if e.get("type") in ("chart", "native_chart"):
            kind = str(e.get("chart_kind") or e.get("kind", ""))
            if kind in ("kpi", "executive_kpi", "big_number"):
                kinds.append("big_number 数据锚点")
            # 数据叙事锚点（design-system §图表「一眼读到结论」的可读表达，非装饰）：
            # 只有 spec 显式声明了这些叙事动作才计，普通 bar/line 不算锚点。
            if e.get("highlight") is not None:
                kinds.append("高亮强调点")
            if e.get("target") is not None or e.get("target_label"):
                kinds.append("目标线叙事")
            if kind in ("donut", "donut_composition") and (
                    e.get("center_value") is not None or e.get("center_label")):
                kinds.append("环心结论")
            if kind == "sparkline":
                spark_count += 1
            data = e.get("data")
            if isinstance(data, list) and any(
                    isinstance(d, dict) and d.get("subtotal") for d in data):
                kinds.append("瀑布桥接")
        if e.get("type") == "image":
            fn = e.get("asset_function") or (e.get("asset") or {}).get("function")
            if fn in ("hero", "emotion", "proof") or str(e.get("role", "")) in MEDIA_ROLES:
                kinds.append(f"图像锚点({fn or e.get('role')})")
    if spark_count >= 2:
        kinds.append(f"small multiples({spark_count} 组形状对比)")
    if _field(slide, "density") == "sparse" and _field(slide, "empty_space_role") in (
            "protect_focus", "hold_emotion"):
        kinds.append("主动留白")
    if not kinds:
        return None
    return " + ".join(kinds)


def is_background_layer(e: dict) -> bool:
    """是否**声明**为背景层（不判断资格）。判定在 primitives 共享。"""
    return is_background_declared(e)


def background_layer_ok(e: dict, cw: float | None = None,
                        ch: float | None = None) -> tuple[bool, str | None]:
    """背景层免检资格：面积占比够大 + 有真实内容保护（或显式声明免检）。

    返回 (合格?, 不合格原因)。不合格的背景层按普通媒体对待：计入媒体预算、参与
    遮挡与来源区检查——这是「用 layer 标签躲检」的唯一封堵点，guard 预检与此同源。
    """
    if not is_background_layer(e):
        return False, "未声明为背景层"
    if cw and ch:
        cover = bg_coverage(e, cw, ch)      # 覆盖率与保护层解析在 primitives 共享，
        if cover < BG_MIN_COVERAGE:         # guard 的资格判定走同一实现
            return False, f"仅覆盖画布 {cover:.0%}（<{BG_MIN_COVERAGE:.0%}），不是空间层而是内容对象"
    if e.get("readability_exempt"):
        return True, None
    op, why = bg_overlay_opacity(e)
    if op is None:
        if why == "unparsable":             # v2.4 fail-closed：解析不出按无保护处理
            return False, "overlay 无法解析出 opacity（解析不出即视为无保护）"
        return False, "未声明 overlay/content_protection：叠加文字的可读性无保障"
    if op < BG_MIN_PROTECT_OPACITY:
        return False, (f"内容保护层不透明度 {op:.2f} < {BG_MIN_PROTECT_OPACITY:.2f}，"
                       f"遮罩形同虚设")
    return True, None


def bg_exempt(e: dict, cw: float | None = None, ch: float | None = None) -> bool:
    """是否享受背景层豁免（声明 + 资格通过）。"""
    return background_layer_ok(e, cw, ch)[0]


def _reading_texts(texts: list[dict]) -> list[dict]:
    """区分「阅读内容」与「低权重导航」：来源、图例、轴标签承担方法学职责，
    不是碎片化阅读的来源，因此不占文本预算（OS §防遮挡：它们属于独立低权重区域）。
    """
    return [t for t in texts if str(t.get("role", "")) not in CAPTION_ROLES]


def _image_justified(e: dict) -> bool:
    if e.get("type") != "image":
        return True
    if is_background_layer(e):
        return bool(e.get("content_protection") or (e.get("overlay") or {})) \
            or bool(e.get("readability_exempt"))
    if e.get("asset_function") or str(e.get("role", "")) in MEDIA_ROLES:
        return True
    asset = e.get("asset")
    return isinstance(asset, dict) and bool(asset.get("function") or asset.get("asset_function"))


class _Rubric:
    """按维度累积证据：每条证据 = (delta, note, fix)。"""

    def __init__(self) -> None:
        self.deltas: dict[str, list[dict]] = {d: [] for d in DIMENSIONS}

    def add(self, dim: str, delta: int, note: str, fix: str | None = None) -> None:
        item = {"delta": delta, "note": note}
        if fix:
            item["fix"] = fix
        self.deltas[dim].append(item)

    def scores(self) -> dict[str, int]:
        return {d: max(0, min(5, BASELINE + sum(i["delta"] for i in ev)))
                for d, ev in self.deltas.items()}

    def debits(self) -> list[dict]:
        out = []
        for ev in self.deltas.values():
            for i in ev:
                if i["delta"] < 0:
                    out.append(i)
        return out

    def evidence(self) -> dict[str, list[str]]:
        return {d: [f"{i['delta']:+d} {i['note']}" for i in ev]
                for d, ev in self.deltas.items() if ev}


def _score_page(spec: dict, slide: dict, index: int, previous: dict | None,
                render_page: dict | None,
                prev_render_page: dict | None = None) -> tuple[dict, dict[str, list[str]],
                                                                list[str], list[str], list[dict]]:
    # 契约校验：当 render_page 存在时，CONSUMED_RENDER_FIELDS 中应至少
    # 有 1 个键被声明（否则等价于「无渲染证据」）。缺字段不扣分——只让
    # 对应评分路径自然降级为结构证据。生产环境可借此发现"渲染管线
    # 静默失败"（比如某次 measure_image 改动导致字段名漂移）。
    if render_page is not None:
        if not any(k in render_page for k in CONSUMED_RENDER_FIELDS):
            render_page = None
    cw, ch = _canvas(spec)
    intent = _intent(slide)
    elems = _elements(slide)
    texts = [e for e in elems if e.get("type") == "text"]
    _charts = [e for e in elems if e.get("type") in ("chart", "native_chart")]
    charts = [e for e in _charts
              if str(e.get("chart_kind") or e.get("kind", "")) != "sparkline"]
    sparklines = [e for e in _charts
                  if str(e.get("chart_kind") or e.get("kind", "")) == "sparkline"]
    images = [e for e in elems if e.get("type") == "image"]
    media = [e for e in charts + images if not bg_exempt(e, cw, ch)]
    # small multiples：一组 sparkline 是「一个关系」的降噪呈现，只占一个媒体席位，
    # 不按逐个竞争焦点计（否则 4 个迷你趋势线会被误判为 4 个争夺注意力的图表）。
    if sparklines:
        media.append({"_kind": "sparkline_group"})
    # 主题化 Accent 预算：让 spec.theme.constraints.accent_max 进入全部分数维度，
    # 不再在 visual_hierarchy 与 contrast 两处各写一个不同的硬编码阈值。
    _theme_constraints = (spec.get("theme") or {}).get("constraints") or {}
    try:
        theme_accent_max = float(_theme_constraints.get("accent_max", 0.05))
    except (TypeError, ValueError):
        theme_accent_max = 0.05
    disguised = [e for e in images if is_background_layer(e) and not bg_exempt(e, cw, ch)]
    reading = _reading_texts(texts)
    rounded = rounded_containers(elems)   # 与 guard 预检同一计数：渲染出来是容器才算
    colors = _theme_colors(spec)
    direction = spec.get("direction") or {}
    composition = str(direction.get("composition_grammar", ""))
    asym_declared = composition in ASYMMETRIC_GRAMMARS
    focus_el, focus = _focus_element(slide)
    insight = intent.get("insight") if isinstance(intent.get("insight"), str) else None
    insight_ok = bool(insight and insight.strip())

    r = _Rubric()
    gates: list[dict] = []

    # ---------- 视觉层级（20） ----------
    if not focus:
        r.add("visual_hierarchy", -2, "页面未声明唯一主焦点，无法验证第一注意点。",
              "补写 focus，并删除或降级竞争性对象。")
        gates.append({"code": "FOCUS_COMPETING", "slide": slide.get("id", index + 1),
                      "severity": "REVISE",
                      "reason": "页面未声明唯一主焦点（page_intent.focus 缺失）。"})
    elif focus_el is None:
        r.add("visual_hierarchy", -2, f"focus={focus!r} 未对应页面元素。",
              "修正 focus 使其指向真实元素 id。")
        gates.append({"code": "FOCUS_COMPETING", "slide": slide.get("id", index + 1),
                      "severity": "REVISE",
                      "reason": f"focus={focus!r} 未对应任何页面元素。"})
    else:
        fsize = _num(focus_el, "size") if focus_el.get("type") == "text" else None
        other_sizes = sorted((_num(t, "size") for t in texts if t is not focus_el),
                             reverse=True)
        # 尺度对比只在「焦点是一段文字」时成立：焦点是图表/图片时拿 0px 去比字号
        # 会算出一条不存在的同级竞争，扣分点到的根本不是同一件事。
        lead = (fsize / other_sizes[0] if fsize is not None and other_sizes
                and other_sizes[0] > 0 else None)
        # 尺度比只做**正向**证据：字阶是否够大是工程可读性问题（QA 的
        # min_font / text_capacity 负责），Critic 只承认「层级被做出来了」。
        if (fsize is not None and fsize >= STATEMENT_SIZE
                and (lead is None or lead >= FOCUS_LEAD)):
            r.add("visual_hierarchy", +1,
                  f"焦点「{focus}」拥有 Statement 级尺度优势（{fsize:.0f}px"
                  + (f"，领先第二大文字 {lead:.1f}×" if lead else "，且无同级文字") + "）。")
        if len(media) <= MEDIA_BUDGET_MAX and len(reading) <= TEXT_BUDGET_MAX \
                and (not render_page or float(render_page.get("accent_pixel_ratio", 0) or 0) <= theme_accent_max):
            r.add("visual_hierarchy", +1, "媒体信号受控（≤1 个图表/图片），焦点无同级竞争者。")
        famp = _area(focus_el)
        for e in elems:
            if e is focus_el or bg_exempt(e, cw, ch):
                continue
            if _area(e) > max(FOCUS_AREA_LEAD * famp, 0.25 * cw * ch):
                r.add("visual_hierarchy", -1,
                      f"元素「{e.get('id', '?')}」面积超过焦点的 2 倍，可能争夺第一注意点。",
                      "缩小或裁切该对象，或重新声明 focus。")
                break
        # 落位是否被决定过：中心对齐任一版面轴线就给一分。只罚「哪儿都不靠」的是预检
        # （hint，不计分），这里只承认做对的事；且本轮已有正向层级证据时不再叠加。
        if not any(i["delta"] > 0 for i in r.deltas.get("visual_hierarchy", [])):
            hit = _axis_hit(focus_el, cw, ch)
            if hit:
                r.add("visual_hierarchy", +1,
                      f"焦点「{focus}」中心 {hit[0]} 对齐{hit[1]}：位置是被决定的，"
                      f"不是排版余数。")
    if disguised:
        r.add("visual_hierarchy", -2,
              "、".join(f"「{e.get('id', '?')}」" for e in disguised)
              + f"声明为背景层但不具备空间层资格（需覆盖 ≥{BG_MIN_COVERAGE:.0%} 画布"
                f"且带 ≥{BG_MIN_PROTECT_OPACITY:.2f} 不透明度保护层），按内容对象计入媒体预算。",
              "要么真正整幅承载空间并叠加保护层，要么改回普通媒体并让出预算与遮挡检查。")
    if len(media) > MEDIA_CHART_MAX:
        r.add("visual_hierarchy", -1, "媒体/图表对象超过两个，存在竞争性视觉信号。",
              "保留承担核心叙事的一个媒体或图表，其余改为注释、拆页或删除。")
    if render_page and float(render_page.get("accent_pixel_ratio", 0) or 0) > theme_accent_max + 0.03:
        r.add("visual_hierarchy", -1, "渲染强调色像素比例偏高，信号可能失去稀缺性。",
              "把 Accent 收束到一个关键数字、节点或下划线。")

    # ---------- 平衡（15） ----------
    if render_page:
        drift = float(render_page.get("gravity_drift", 0) or 0)
        if drift > 0.28:
            # 锚点来源必须写明：resolve_anchor() 的优先级是 page_intent.focus
            # → gravity_anchor。只写「声明重心」会让人去改 gravity_anchor，
            # 而焦点声明存在时改它完全无效（实测为此白跑数轮迭代）。
            _anchor_id = str(render_page.get("anchor_id") or "").strip()
            _src = str(render_page.get("anchor_source") or "").strip()
            _who = (f"锚点是「{_anchor_id}」（来自 {_src}）" if _anchor_id
                    else "锚点未声明，按启发式取主视觉")
            r.add("balance", -2,
                  f"渲染显著性质心漂移 {drift:.2f}，与声明焦点不一致；{_who}。",
                  "让结论真正变重（放大标题/主视觉、收短正文），或改声明 focus 到"
                  "真正承担结论的元素；焦点已声明时改 gravity_anchor 无效，"
                  "也不要用装饰补偿。")
        else:
            r.add("balance", +1, f"渲染质心与声明锚点基本一致（漂移 {drift:.2f} ≤ 0.28）。")
    else:
        anchor = _declared_anchor(slide, cw, ch)
        centroid = _mass_centroid(elems, cw, ch)
        if anchor and centroid:
            drift = _dist(anchor[:2], centroid)
            if drift <= ANCHOR_DRIFT:
                r.add("balance", +1, f"几何墨迹质心与声明 gravity_anchor 一致（偏移 {drift:.2f}）。")
            else:
                r.add("balance", -1, f"几何质心偏离声明锚点 {drift:.2f} > {ANCHOR_DRIFT}。",
                      "调整布局重心或重新声明 gravity_anchor。")
    split = _lr_split(elems, cw)
    light_heavy = (1.0 - split) / (1.0 + split) if split < 1.0 else 0.0
    # 轻侧几乎为空（<15% 重侧墨迹）时视为主动的单栏/留白构图，不算失衡；
    # 仅当两侧都有内容却明显偏沉、且未声明非对称语法时才扣分。
    if split > LR_SPLIT_MAX and light_heavy > 0.15 and not asym_declared:
        r.add("balance", -1, f"左右墨迹面积失衡 {split:.0%}（轻侧仅占重侧 {light_heavy:.0%}，未声明非对称构图语法）。",
              "用留白或次级对象回填轻侧，或声明 composition_grammar 为非对称语法。")
    if len(rounded) >= 3 and len(rounded) >= max(3, len(elems) // 2):
        r.add("balance", -1, "页面主要结构由等质容器组成，可能缺少编辑式空间节奏。",
              "打破均匀模块排列，建立一个主重心、一个次级关系和明确留白。")
    if _field(slide, "density") == "sparse" and _field(slide, "empty_space_role"):
        r.add("balance", +1,
              f"留白承担了明确职责（{_field(slide, 'empty_space_role')} / {_field(slide, 'density')}）。")

    # ---------- 对齐（10） ----------
    stats = _alignment_stats(elems)
    n_objects = stats["objects"]
    if n_objects >= 2 and stats["left_cluster"] >= max(2, n_objects // 2):
        r.add("alignment", +1,
              f"{stats['left_cluster']}/{n_objects} 个内容对象共享同一左缘轴线（装订线收束）。")
    elif n_objects >= 4 and stats["distinct_left"] > max(3, n_objects // 2):
        r.add("alignment", -1, f"内容左缘出现 {stats['distinct_left']} 条轴线，装订线失焦。",
              "把元素左缘收敛到少数 8 网格轴线，先做结构对齐再谈光学对齐。")
    if stats["top_cluster"] >= 2:
        r.add("alignment", +1, f"{stats['top_cluster']} 个内容对象共享同一顶缘基线。")
    ok_grid, total = _grid_bias_stats(elems, cw, ch)
    # 网格是 Normalizer 的职责（机械吸附），贴合与否不在审美维度里扣分；
    # 全部命中只说明「版面有秩序」，记一次正向证据即可。
    if total >= 3 and ok_grid == total:
        r.add("alignment", +1, f"全部 {total} 个内容对象落在 8 单位网格（偏差 ≤1px）。")
    aligns = {str(e.get("align", "left")) for e in texts}
    if len(aligns) > 2:
        r.add("alignment", -1, f"页面混用 {len(aligns)} 种文本对齐方式，轴向不稳定。",
              "统一为一个主对齐方式加一个受控例外。")
    # 视觉对齐：若渲染证据给出边缘投影峰度（edge_kurtosis_*），
    # 这是 sobel 强度沿轴投影的尖锐度——高表示多数内容共享同一
    # 装订线 / 基线（编辑式对齐），低表示碎片化分布。仅当存在
    # 真实渲染证据时启用，避免在没有 PNG 的情况下做无意义的扣分。
    if render_page is not None:
        kx = float(render_page.get("edge_kurtosis_x", 0) or 0)
        ky = float(render_page.get("edge_kurtosis_y", 0) or 0)
        k_avg = (kx + ky) / 2 if (kx or ky) else 0.0
        # 像素级「对齐松散」只作参考，不作扣分：装订线失焦在结构证据（左缘轴线
        # 统计）里已经判过；同一事实扣两次是旧版最大的重复。
        if k_avg >= 4.0:
            r.add("alignment", +1,
                  f"渲染边缘投影峰度 {k_avg:.1f}（x={kx:.1f}, y={ky:.1f}），"
                  f"视觉对齐形成清晰轴线。")
        # 渲染级光学对齐复核：验证「数学对齐」是否成为「视觉对齐」——每根
        # 声明轴线（shape/chart/image 边界）的视觉峰位与 spec 坐标偏差 ≤2px。
        # 纯加分项：一致率高证明数学对齐即视觉对齐；图像页内部边缘天然离轴，
        # 低一致率不扣分（原始指标留在渲染报告里供人复核）。
        opt = (render_page or {}).get("optical_alignment") or {}
        if int(opt.get("lines_checked") or 0) >= 3 and opt.get("aligned_share") is not None:
            share = float(opt["aligned_share"])
            shift = float(opt.get("max_shift_px") or 0.0)
            if share >= 0.75:
                r.add("alignment", +1,
                      f"渲染级光学对齐复核：{int(opt['lines_checked'])} 根声明轴线中 "
                      f"{share:.0%} 的视觉峰位与数学坐标一致（最大偏移 {shift:.1f}px）"
                      f"——数学对齐即视觉对齐。")

    # ---------- 对比（10） ----------
    ink_bg = _hex_contrast(colors, "ink", "background")
    if ink_bg is not None:
        if ink_bg < 4.5:
            r.add("contrast", -2, f"正文 ink 对背景对比 {ink_bg:.1f}:1 < 4.5:1，正文阅读吃力。",
                  "加深 ink 或提亮背景至 ≥4.5:1。")
        elif ink_bg < 7:
            r.add("contrast", -1, f"正文 ink 对背景对比 {ink_bg:.1f}:1 偏弱（建议 ≥7:1）。")
    muted_bg = _hex_contrast(colors, "muted", "background")
    if muted_bg is not None and muted_bg < 1.8:
        r.add("contrast", -1, f"muted 对背景对比 {muted_bg:.1f}:1 < 1.8:1，"
                              f"次级信息与底糊成一片，版面失去层次气质。",
              "把 muted 与背景拉开（≥3:1），或让次级信息改用更重的 token。")
    accent_bg = _hex_contrast(colors, "accent", "background")
    accent_ratio = float(render_page.get("accent_pixel_ratio", 0) or 0) if render_page else None
    if accent_ratio is not None and accent_ratio <= theme_accent_max and (accent_bg is None or accent_bg >= 3):
        r.add("contrast", +1, f"强调色像素 {accent_ratio:.1%} ≤ 主题上限 {theme_accent_max:.0%}，Accent 保持稀缺性。")
    if accent_ratio is not None and accent_ratio > theme_accent_max + 0.03:
        r.add("contrast", -1, f"强调色像素 {accent_ratio:.1%} > 主题上限 {theme_accent_max:.0%}，强调信号被稀释。")
    if ink_bg is not None and ink_bg >= 7 and (muted_bg is None or muted_bg >= 3):
        r.add("contrast", +1,
              f"正文对比 {ink_bg:.1f}:1 且 muted ≥3:1，可读性层级健康。")
    # 渲染层实测文字对比：**只加分不扣分**。低于工程底线的情况由
    # qa.text_contrast 域以 READABILITY_FAIL 阻断（同一份证据，一个出口）；
    # Critic 在这里的角色是「反差是否被当成表达手段用」，不是复测可读性。
    _tc = text_contrast_verdict(render_page, TEXT_CONTRAST_FAIL, TEXT_CONTRAST_WARN)
    _tcv = _tc["value"]
    if _tc["level"] in ("pass", "soft") and _tcv >= TEXT_CONTRAST_WARN:
        r.add("contrast", +1, f"叠加文字最坏对比 {_tcv:.1f}:1 ≥ {TEXT_CONTRAST_WARN}:1，"
                              f"明暗关系在像素层兑现了。")
    elif _tc["level"] in ("fail", "soft"):
        r.add("contrast", 0, f"叠加文字最坏对比 {_tcv:.2f}:1 偏软"
                             f"（工程底线由 QA 判定，此处不重复记分）")

    # ---------- 节奏（10） ----------
    density = _field(slide, "density")
    energy = _field(slide, "energy")
    if previous:
        prev_intent = _intent(previous)
        prev_density = prev_intent.get("density") or previous.get("density")
        prev_energy = prev_intent.get("energy") or previous.get("energy")
        # 实测墨迹差：标签相同但真实留白变化明显 = 节奏其实成立（旧口径会误伤）；
        # 标签交替但墨迹几乎不变 = 空转标签（旧口径看不见）。
        ink_shift = None
        if render_page and prev_render_page and "occupancy" in render_page \
                and "occupancy" in prev_render_page:
            try:
                ink_shift = abs(float(render_page["occupancy"])
                                - float(prev_render_page["occupancy"]))
            except (TypeError, ValueError):
                ink_shift = None
        # 「同密度同能量」不再逐条扣分——它已经在预测层（pre_critic 的
        # RHYTHM_FLAT_RISK）变成了生成策略；Critic 只对**实测**负责：
        # 墨迹真的动了 = 呼吸成立（加分）；标签变了而墨迹不动 = 空转（扣分）。
        if density and density == prev_density and ink_shift is not None \
                and ink_shift >= RHYTHM_INK_DELTA:
            r.add("rhythm", +1, f"密度标签相同但实测占用率相差 {ink_shift:.2f}，"
                                f"呼吸变化真实存在。",
                  "保持这种由墨迹承担的节拍，而不是只改标签。")
        elif density and prev_density and density != prev_density \
                and energy and prev_energy and energy != prev_energy:
            r.add("rhythm", +1, f"密度 {prev_density}→{density} 且能量 {prev_energy}→{energy}，节奏变化明确。")
        if ink_shift is not None and density != prev_density and ink_shift <= RHYTHM_INK_FLAT:
            r.add("rhythm", -1, f"密度标签从 {prev_density} 改为 {density}，但实测占用率只差 "
                                f"{ink_shift:.2f}（≤{RHYTHM_INK_FLAT}），节奏是虚挂的。",
                  "用真实内容量或留白兑现节拍，而不是改 density 字段。")
        elif (ink_shift is not None and ink_shift >= RHYTHM_INK_DELTA
              and not any(i["delta"] > 0 for i in r.deltas.get("rhythm", []))):
            # 只改了一个标签、但墨迹真的动了 0.10 以上：按实测给节奏记账（同一事实不
            # 重复发糖：已有加分就跳过）。否则「标签齐不齐」仍比「页面是否真的在呼吸」
            # 更有话语权。
            r.add("rhythm", +1, f"实测占用率与上一页相差 {ink_shift:.2f}（≥{RHYTHM_INK_DELTA}），"
                                f"跨页呼吸成立。",
                  "保持这种由内容量与留白承担的节拍。")
    # 「density 声明是否兑现」属于预测层的策略调整（pre_critic 的
    # DENSITY_MISMATCH_RISK），不在审美评分里重复扣一次；这里只在有实测证据时
    # 看跨页呼吸（上方 ink_shift 分支）。

    # ---------- 一致性（10） ----------
    fams = {str(e.get("font") or e.get("family", "")) for e in texts if e.get("font") or e.get("family")}
    if len(fams) > 2:
        r.add("consistency", -1, f"页面引用 {len(fams)} 个字体家族 > 上限 2。",
              "收拢到 display 与正文两族字体。")
    sizes = {round(_num(t, "size"), 1) for t in texts if _num(t, "size") > 0}
    if len(sizes) > 4:
        r.add("consistency", -1, f"页面使用 {len(sizes)} 个字号等级 > 上限 4，层级失焦。",
              "收拢字号层级，复用既有等级而非新增。")
    if previous:
        prev_sz = (previous.get("source_zone") or {}).get("x")
        cur_sz = (slide.get("source_zone") or {}).get("x")
        if cur_sz is not None and prev_sz is not None and abs(cur_sz - prev_sz) < 1:
            r.add("consistency", +1, "来源区位置与上一页保持一致。")
        elif cur_sz is not None and prev_sz is not None:
            r.add("consistency", -1, "来源区位置与上一页不同，跨页基线漂移。",
                  "固定 source_zone 的位置与尺寸。")
    cont = _field(slide, "continuity_token") or \
        (direction.get("continuity_token") if isinstance(direction, dict) else None)
    if cont and (previous or index == 0):
        r.add("consistency", +1, f"页面声明 continuity_token（{cont}），跨页连续性可追踪。")

    # ---------- 情绪影响（10） ----------
    if not insight_ok:
        r.add("emotional_impact", -2, "缺少 page_intent.insight，页面没有可共鸣的结论。",
              "先写一条完整可复述的 insight，再调整版式。")
        gates.append({"code": "INTENT_UNCLEAR", "slide": slide.get("id", index + 1),
                      "severity": "BLOCKED",
                      "reason": "页面缺少可复述的单一 insight。"})
    color_intent = direction.get("color_intent") or []
    bg_scene = str(direction.get("background_scene", "") or
                   (slide.get("background") or {}).get("scene", ""))
    has_emotion_media = any(i.get("asset_function") in ("emotion", "hero") or
                            str(i.get("role", "")) in ("emotion", "hero")
                            for i in images)
    if "emotion" in color_intent and (has_emotion_media or bg_scene in ("atmospheric", "cinematic")):
        r.add("emotional_impact", +1, "情绪职责由媒体/场景承担，而非装饰色。")
    if _field(slide, "empty_space_role") in ("hold_emotion", "protect_focus") \
            and _field(slide, "density") in ("sparse", "balanced"):
        r.add("emotional_impact", +1,
              f"留白承担情绪/注意力职责（{_field(slide, 'empty_space_role')}）。")
    # 渲染 vs 情绪场景对照：深色 + 高饱和通常意味着「戏剧/产品发布」；
    # 浅色 + 低饱和通常意味着「编辑式安静」。这是 art_critic 情绪维度
    # 从「仅看声明」升级为「声明 vs 渲染」的第二步。仅在有真实渲染
    # 证据时启用，缺证据时不扣分也不加分。
    if render_page and "brightness" in render_page:
        try:
            bri = float(render_page.get("brightness") or 0)
        except (TypeError, ValueError):
            bri = None
        if bri is not None:
            sat_ratio = float(render_page.get("saturated_pixel_ratio", 0) or 0)
            if bg_scene == "cinematic" and bri < 0.30:
                r.add("emotional_impact", +1,
                      f"渲染亮度 {bri:.0%} 配合 cinematic 场景，深色基调支撑戏剧/产品发布情绪。")
            elif bg_scene == "solid_world" and bri > 0.75 \
                    and _field(slide, "density") == "sparse" and sat_ratio < 0.05:
                r.add("emotional_impact", +1,
                      f"渲染亮度 {bri:.0%} 配合 solid_world + sparse，编辑式安静气质成立。")

    # ---------- 记忆点（10） ----------
    anchor_desc = _memory_anchor(slide)
    if anchor_desc:
        r.add("memorability", +1, f"存在可复现的视觉记忆锚点：{anchor_desc}。")
    else:
        r.add("memorability", -1, "页面缺少可识别的视觉记忆锚点，可能只剩通用文字版式。",
              "为本页选择一个可复现的记忆动作：尺度、裁切、线性符号、独特留白或数据标注方式。")
    if cont and anchor_desc:
        r.add("memorability", +1, f"记忆锚点（{anchor_desc[:24]}…）与 continuity_token 绑定。")

    # ---------- 专业完成度（5） ----------
    if len(rounded) > ROUNDED_MAX:
        r.add("professional_quality", -2, f"检测到 {len(rounded)} 个圆角容器，已成卡片墙（网页 UI 化）。",
              "将容器改为空间分组、发丝线或字体层级；仅保留数据/KPI/特殊强调所需面板。")
    elif len(rounded) >= 3:
        # 未到硬门槛，但已偏离「卡片不是默认容器」：软扣分 + 与预检 CARD_DENSITY 同源提示
        r.add("professional_quality", -1,
              f"检测到 {len(rounded)} 个圆角容器，接近卡片墙（>{ROUNDED_MAX} 即硬门槛）。",
              "删容器，改用空间分组、发丝线或字体层级；仅保留数据/KPI/特殊强调所需面板。")
    unjustified = [i for i in images if not _image_justified(i)]
    if unjustified:
        r.add("professional_quality", -1,
              f"{len(unjustified)} 张图片未声明资产功能（asset_function/role），媒体缺乏存在理由。",
              "声明图片的 context/emotion/proof/hero 功能，或删除无法说明功能的图片。")
    decoration = sum(_area(e) for e in elems
                     if e.get("role") == "decoration" or e.get("decorative") is True)
    if cw * ch > 0 and decoration / (cw * ch) > 0.10:
        r.add("professional_quality", -1, "装饰面积超过页面 10%，违背克制原则。",
              "删除无法说明功能的装饰。")
    if insight_ok and focus_el is not None and len(fams) <= 2 and len(sizes) <= 4 \
            and len(aligns) <= 2:
        r.add("professional_quality", +1, "意图声明、焦点、字体预算与对齐预算均达到契约要求。")
    if render_page is not None:
        r.add("professional_quality", +1, "具备真实渲染证据闭环，专业完成度可被复核。")

    scores = r.scores()
    debit_items = r.debits()
    observations = [i["note"] for i in debit_items]
    fixes = list(dict.fromkeys(i["fix"] for i in debit_items if i.get("fix")))
    if not observations:
        observations.append("页面结构与声明意图基本一致，继续以渲染缩略图验证记忆点。")

    return scores, r.evidence(), observations, fixes, gates


# ── 职责移交表（vNext）：这些码**只属于 QA**，Critic 不再重复判罚 ──────────
# 列在这里是给自己看的纪律，也是给下游可核对的契约：报告里以 `delegated_to_qa`
# 原样输出，任何人质疑「Critic 为什么不管溢出/对比度」都能一眼看到答案。
DELEGATED_TO_QA = (
    "READABILITY_FAIL",        # 实测文字对比 <3:1 阻断 → qa.text_contrast 域
    "TEXT_OVERFLOW",           # 文本溢出 → guard.text_capacity / 编译器 warning
    "OVERLAP", "SOURCE_COLLISION", "CHART_LABEL_COLLISION",   # 几何层 → guard
    "DATA_INTEGRITY_FAIL",     # 数据合同 → guard.data_integrity
    "COMPILE_FAIL", "GUARD_FAIL",
    "BACKGROUND_DISGUISED",    # 伪背景按普通对象计入媒体/遮挡检查 → guard + QA
    "MEDIA_UNJUSTIFIED",       # 媒体功能缺失 → guard.asset_contract（Critic 仍作设计扣分）
    "CARD_WALL",               # 容器密度 → 计分 + 预测层策略，不设为发布门槛
    "RHYTHM_FLAT",             # 跨页趋平 → 预测层策略（pre_critic），不设为发布门槛
    "RENDER_UNAVAILABLE", "RENDER_INCOMPLETE", "PIXEL_COVERAGE_PARTIAL",
)

# 失败码 → 总监级最小行动（一句话，不复述整条 evidence；verdict 只给方向，细节看各页 minimal_fix）
_GATE_ACTIONS = {
    "INTENT_UNCLEAR": "先为该页写一句 object + 变化/差异 + 含义的可复述 insight，再排版。",
    "FOCUS_COMPETING": "确立唯一主焦点并给它尺度优势，删除或降级竞争性对象。",
    "CARD_WALL": "删容器，改用发丝线 + 留白 + 字阶分组；只保留数据/KPI/特殊强调所需面板。",
    "MEDIA_UNJUSTIFIED": "为图片声明 context/emotion/proof/hero 功能，或删除无法说明功能的图片。",
    "RHYTHM_FLAT": "改动其中一页的密度或能量，恢复呼吸曲线。",
    "CRITIC_LOW": "按该页 dimension_evidence 逐条回应，先修扣分最多的维度。",
    "READABILITY_FAIL": "加深遮罩或改文字色：让文字与局部背景至少拉开 4.5:1。",
    "BACKGROUND_DISGUISED": "撤掉 layer=background 标签，或扩大覆盖并声明 overlay（opacity ≥0.20）。",
    "RENDER_UNAVAILABLE": "补真实渲染证据后重新判定（当前结论按结构证据降级）。",
    "RENDER_INCOMPLETE": "检查渲染管线字段是否漂移，补全像素证据后重新判定。",
    "PIXEL_COVERAGE_PARTIAL": "发布前跑 Level 3 全量像素复核。",
}


# ════════════════════════════════════════════════════════════════════════
# Revision Batch Intelligence（V2）：修正纪律从「1 问题 = 1 轮」升级为
# 「1 根因 = 1 轮」。同根因的杠杆（如主题对比度引发的 READABILITY + contrast
# 维度 + chart_muted 提示）一次批量修复、一次验证——归因仍然清晰，因为它们
# 本来就是同一个原因；不同根因（布局 vs 记忆锚点）严格分轮。
# ════════════════════════════════════════════════════════════════════════
_ROOT_CAUSE_BY_DIMENSION = {
    "visual_hierarchy": "focus_anchor", "balance": "composition",
    "alignment": "geometry_grid", "contrast": "theme_contrast",
    "rhythm": "rhythm_density", "consistency": "cross_page_consistency",
    "emotional_impact": "narrative_emotion", "memorability": "memory_anchor",
    "professional_quality": "finish_detail",
}
_ROOT_CAUSE_BY_CODE = {
    "DATA_INTEGRITY_FAIL": "data_contract", "READABILITY_FAIL": "theme_contrast",
    "OVERLAP": "layout_collision", "SOURCE_COLLISION": "layout_collision",
    "CHART_LABEL_COLLISION": "layout_collision", "TEXT_OVERFLOW": "layout_collision",
    "FOCUS_UNBOUND": "focus_anchor", "FOCUS_COMPETING": "focus_anchor",
    "FOCUS_DOMINATED": "focus_anchor", "CARD_WALL": "card_clutter",
    "RHYTHM_FLAT": "rhythm_density", "DENSITY_FLAT": "rhythm_density",
    "MEDIA_UNJUSTIFIED": "media_governance", "BACKGROUND_DISGUISED": "media_governance",
    "MEDIA_BUDGET": "media_governance", "INTENT_UNCLEAR": "narrative_intent",
    "PIXEL_COVERAGE_PARTIAL": "evidence_coverage", "RENDER_UNAVAILABLE": "evidence_coverage",
    "RENDER_INCOMPLETE": "evidence_coverage",
}
_ROOT_CAUSE_KEYWORDS = (   # 复现修正（自由文本）的确定性关键词归类
    ("对比", "theme_contrast"), ("可读", "theme_contrast"),
    ("网格", "geometry_grid"), ("对齐", "geometry_grid"), ("坐标", "geometry_grid"),
    ("锚", "memory_anchor"), ("记忆", "memory_anchor"),
    ("密度", "rhythm_density"), ("节奏", "rhythm_density"), ("疏密", "rhythm_density"),
    ("焦点", "focus_anchor"), ("层级", "focus_anchor"),
    ("卡片", "card_clutter"), ("容器", "card_clutter"),
    ("留白", "composition"), ("重心", "composition"), ("平衡", "composition"),
    ("来源", "data_contract"), ("单位", "data_contract"), ("口径", "data_contract"),
    ("图片", "media_governance"), ("资产", "media_governance"),
)


def _root_cause_of(lever: dict) -> str:
    """杠杆 → 根因桶（确定性）。CRITIC_LOW 从 reason 里解析维度名再映射。"""
    target = str(lever.get("target") or "")
    if lever.get("kind") == "dimension":
        return _ROOT_CAUSE_BY_DIMENSION.get(target, "finish_detail")
    if lever.get("kind") == "gate":
        if target == "CRITIC_LOW":
            reason = str(lever.get("why") or "")
            for d, cause in _ROOT_CAUSE_BY_DIMENSION.items():
                if d in reason:
                    return cause
            return "finish_detail"
        return _ROOT_CAUSE_BY_CODE.get(target, "unclassified_gate")
    if lever.get("kind") == "recurring":
        text = f"{lever.get('target', '')} {lever.get('why', '')} {lever.get('action', '')}"
        for kw, cause in _ROOT_CAUSE_KEYWORDS:
            if kw in text:
                return cause
        return "cross_page_recurring"
    return "unclassified"


def _director_verdict(reports, hard_gates, deck_notes, deck_score, status) -> dict:
    """总监 verdict：deck 级单一首要判断 + 按价值排序的修正杠杆（Top 3）。

    不是新评分 —— 只是把已有的 hard_gates / 维度均值 / 高频扣分 evidence 按
    「修哪个最值」排成一条行动线。修正纪律：一次只修 primary_lever，跑完一轮
    QA 再看下一条。这就是「在有限复杂度下创造最高视觉价值」的执行形态，也是
    减少修正轮数（执行速度）最直接的一步：先修最重要的，而不是逐条追分。
    纯函数、确定性：同输入必得同 verdict。
    """
    gates = [g for g in (hard_gates or []) if isinstance(g, dict)]
    sev_rank = {"BLOCKED": 0, "REVISE": 1, "PREVIEW_ONLY": 2}
    gates.sort(key=lambda g: (sev_rank.get(g.get("severity"), 3),
                              str(g.get("code")), str(g.get("slide"))))
    by_code: dict[str, dict] = {}
    for g in gates:
        code = str(g.get("code") or "UNKNOWN")
        slot = by_code.setdefault(code, {"code": code, "severity": g.get("severity"),
                                         "slides": [], "reasons": []})
        if g.get("slide") is not None:
            slot["slides"].append(g.get("slide"))
        if g.get("reason") and g["reason"] not in slot["reasons"]:
            slot["reasons"].append(g["reason"])

    def _where(slides: list) -> str:
        uniq = sorted({str(s) for s in slides})
        return ("、".join(uniq[:4]) + (" 等" if len(uniq) > 4 else "")) or "整套 deck"

    levers: list[dict] = []
    for code, slot in sorted(by_code.items(),
                             key=lambda kv: (sev_rank.get(kv[1]["severity"], 3), kv[0])):
        levers.append({"kind": "gate", "target": code,
                       "where": _where(slot["slides"]),
                       "why": slot["reasons"][0] if slot["reasons"] else "",
                       "action": _GATE_ACTIONS.get(
                           code, "按该页 minimal_fix 逐条修正后重跑 QA。"),
                       "severity": slot["severity"]})
    for w in (deck_notes.get("systemic_weaknesses") or [])[:2]:
        levers.append({"kind": "dimension", "target": w.get("dimension"),
                       "where": "整套 deck",
                       "why": f"该维度 deck 均值 {w.get('average')}，系统性偏弱",
                       "action": w.get("fix_hint", ""),
                       "severity": "REVISE"})
    fix_pages: dict[str, list] = {}
    for r in reports or []:
        for f in r.get("minimal_fixes") or []:
            fix_pages.setdefault(str(f), []).append(r.get("slide"))
    for fix, slides in sorted(fix_pages.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(slides) >= 2:      # 同一修正出现在 ≥2 页：修一处赚多页，值得置顶
            levers.append({"kind": "recurring", "target": "跨页高频问题",
                           "where": _where(slides),
                           "why": f"同一修正出现在 {len(slides)} 页",
                           "action": fix, "severity": "REVISE"})
            break
    # V2：根因分组——同根因的杠杆归入一组，本轮只修 primary 所在组
    for item in levers:
        item["root_cause"] = _root_cause_of(item)
    groups: dict[str, dict] = {}
    for item in levers:
        g = groups.setdefault(item["root_cause"], {
            "cause": item["root_cause"], "levers": [], "pages": set(),
            "max_severity": 3})
        g["levers"].append(item)
        for tok in str(item.get("where") or "").replace(" 等", "").split("、"):
            if tok and tok != "整套 deck":
                g["pages"].add(tok)
        sev = {"BLOCKED": 0, "REVISE": 1, "PREVIEW_ONLY": 2}.get(
            str(item.get("severity")), 3)
        g["max_severity"] = min(g["max_severity"], sev)
    sev_rank = {"BLOCKED": 0, "REVISE": 1, "PREVIEW_ONLY": 2}
    _sev_name = {0: "BLOCKED", 1: "REVISE", 2: "PREVIEW_ONLY", 3: "REVISE"}
    root_cause_groups = sorted(
        ({"cause": g["cause"], "count": len(g["levers"]),
          "pages": sorted(g["pages"]),
          "severity": _sev_name[g["max_severity"]],
          "targets": [str(l.get("target")) for l in g["levers"]]}
         for g in groups.values()),
        key=lambda g: (sev_rank.get(g["severity"], 3), -g["count"], g["cause"]))

    top = levers[:3]
    for i, item in enumerate(top, 1):
        item["rank"] = i
    primary = top[0] if top else None
    # primary 所在根因组置顶：组序与「本轮修什么」一致，读报告不用二次对齐
    if primary and primary.get("root_cause"):
        rc = primary["root_cause"]
        root_cause_groups = ([g for g in root_cause_groups if g["cause"] == rc]
                             + [g for g in root_cause_groups if g["cause"] != rc])
    if status == "PASS":
        headline = f"发布就绪（{deck_score:.1f} 分）：无阻断门槛，保持当前克制度即可。"
    elif primary and primary["kind"] == "gate" and primary["severity"] == "BLOCKED":
        headline = (f"先修 {primary['where']} 的 {primary['target']}（BLOCKED），"
                    f"其余都是次要问题。")
    elif primary:
        headline = (f"首要杠杆是{primary['where']}的{primary['target']}："
                    f"{primary['action']}")
    else:
        headline = "无明确杠杆：按页修 minimal_fix 后重跑 QA。"
    # V2 批量修正：primary 所在根因组的全部杠杆本轮一并修（一次验证）；
    # 其余根因组排队后续轮次。归因不破坏：同组 = 同一个「为什么」。
    primary_cause = primary.get("root_cause") if primary else None
    fix_this_round = [l for l in levers if l.get("root_cause") == primary_cause] \
        if primary_cause else []
    deferred = [{"cause": g["cause"], "count": g["count"], "pages": g["pages"]}
                for g in root_cause_groups if g["cause"] != primary_cause]
    batch = {
        "fix_this_round": fix_this_round,
        "deferred": deferred,
        "discipline": ("1 根因 = 1 轮：同根因杠杆本轮批量修复、一次验证；"
                       "不同根因分轮——归因清晰与往返最少同时成立。"),
    } if primary_cause else None
    return {"headline": headline, "primary_lever": primary, "levers": top,
            "gates_by_code": sorted(by_code),
            "root_cause_groups": root_cause_groups, "batch": batch}


def _diagnosis(reports: list[dict], hard_gates: list[dict], deck_notes: dict,
               director: dict, deck_score: float, status: str) -> dict:
    """设计诊断（v3.2）：Critic 的主输出是「判断」，分数只是置信度。

    纯重排已有证据——不新增任何测量。四条：
      strengths 这条 deck 已经做对的设计决策（值得保留）
      risks     正在损害层级 / 节奏 / 记忆点的模式
      evidence  指到页码与实测数字（可复核，不是形容词）
      advice    下一步的设计杠杆（来自 director_verdict，不来自阈值差值）
    """
    avg = deck_notes.get("dimension_averages") or {}

    def _note(dim: str, pick: str = "last") -> str:
        """引用已有的证据条目（不新算）：优势取最后一次正证据，风险取第一条负证据。"""
        notes = []
        for rp in reports:
            ev = (rp.get("dimension_evidence") or {}).get(dim) or []
            if ev:
                notes.append(str(ev[0] if pick == "first" else ev[-1]))
        return (notes[-1 if pick == "last" else 0] if notes else "")[:160]

    ranked = sorted(avg.items(), key=lambda kv: -kv[1])
    strengths = [{"dimension": d, "average": round(v, 2), "basis": _note(d, "last")}
                 for d, v in ranked[:3] if v >= 3.5]
    risks = [{"dimension": d, "average": round(v, 2), "basis": _note(d, "first")}
             for d, v in ranked[-2:] if v < 3.5]
    for g in hard_gates:
        risks.append({"gate": g.get("code"), "where": g.get("slide") or "整套 deck",
                      "basis": str(g.get("reason") or "")[:160]})
    advice = []
    for lever in (director.get("levers") or [])[:3]:
        advice.append({"lever": lever.get("target") or lever.get("kind"),
                       "where": lever.get("where"), "action": lever.get("action")})
    if not advice and director.get("primary_lever"):
        pl = director["primary_lever"]
        advice.append({"lever": pl.get("target") or pl.get("kind"),
                       "where": pl.get("where"), "action": pl.get("action")})
    return {
        "question": "这套设计有没有高级价值？（工程正确性由 QA 判：见 qa.verdict）",
        "assessment": director.get("headline") or f"{status}（置信度 {deck_score}）",
        "strengths": strengths,
        "risks": risks,
        "advice": advice,
        "score_semantics": ("deck_score 是**置信度**：证据条数与维度均值有多可信，"
                             "不是质量目标。不得把分数调到某个数当作修订理由——"
                             "理由只能是 evidence 里的具体事实。"),
    }


def critique_deck(spec: dict, render_evidence: dict | None = None,
                  evidence_cards: list[dict] | None = None) -> dict:
    """Return a read-only structured critique; never mutates spec.

    hard_gates 项 = {code, slide, severity, reason}；severity ∈
    {BLOCKED, REVISE, PREVIEW_ONLY}，与 production-contract.md 失败码表一致。
    """
    slides = spec.get("slides") or []
    render_pages = (render_evidence or {}).get("pages") or []
    rendered = bool((render_evidence or {}).get("rendered", False))
    reports = []
    total_weighted = 0.0
    hard_gates: list[dict] = []
    # 证据按 index 对齐：子集渲染（Progressive QA Level 2）时位置对齐会把指标串到
    # 别的页面上；旧证据没有 index 时才退回位置对齐。
    by_index: dict[int, dict] = {}
    for p in render_pages:
        if isinstance(p, dict) and p.get("index") is not None:
            try:
                by_index[int(p["index"])] = p
            except (TypeError, ValueError):
                pass
    indexed = bool(by_index)
    for i, slide in enumerate(slides):
        rp = (by_index.get(i) if indexed
              else (render_pages[i] if i < len(render_pages) else None))
        prev_rp = (by_index.get(i - 1) if indexed and i > 0
                   else (render_pages[i - 1] if i > 0 and i - 1 < len(render_pages) else None))
        scores, evidence, observations, fixes, gates = _score_page(
            spec, slide, i, slides[i - 1] if i else None, rp, prev_rp)
        weighted = sum(scores[d] / 5 * WEIGHTS[d] for d in DIMENSIONS)
        total_weighted += weighted
        # production-contract.md Art Critic contract：任何核心维度低于 3 至少 REVISE
        low_dims = [d for d in DIMENSIONS if scores[d] < 3]
        if low_dims:
            last_note = {d: (evidence.get(d) or ["（无证据）"])[-1] for d in low_dims}
            hard_gates.append({"code": "CRITIC_LOW", "slide": slide.get("id", i + 1),
                               "severity": "REVISE",
                               "reason": "维度低于 3/5：" +
                                         "；".join(f"{d}:{last_note[d]}" for d in low_dims)})
        hard_gates.extend(g for g in gates
                          if not any(h.get("code") == g.get("code") and
                                     h.get("slide") == g.get("slide") for h in hard_gates))
        reports.append({"slide": slide.get("id", i + 1), "scores": scores,
                        "score": round(weighted, 1), "observations": observations,
                        "minimal_fixes": fixes,
                        "dimension_evidence": evidence,
                        "recheck": ["QA（工程判定）", "Critic（设计判定）"]})
    count = max(1, len(slides))
    deck_score = round(total_weighted / count, 1)
    if not rendered:
        status = "PREVIEW_ONLY"
        hard_gates.append({"code": "RENDER_UNAVAILABLE", "slide": None,
                           "severity": "PREVIEW_ONLY",
                           "reason": "缺少真实渲染证据，审美判断按结构证据降级。"})
    else:
        # 渲染证据完整性：rendered=True 但 pages 没有任何 CONSUMED 字段
        # 视为「渲染管线静默失败」（measure_image 改动导致字段名漂移
        # 等）。降级为 PREVIEW_ONLY 而非 PASS——这是契约漂移的早期信号。
        rendered_usable = False
        for p in render_pages:
            if isinstance(p, dict) and any(k in p for k in CONSUMED_RENDER_FIELDS):
                rendered_usable = True
                break
        if not rendered_usable:
            status = "PREVIEW_ONLY"
            hard_gates.append({"code": "RENDER_INCOMPLETE", "slide": None,
                               "severity": "PREVIEW_ONLY",
                               "reason": ("rendered=True 但 pages 缺少任何被 "
                                          "critic 消费的渲染字段——渲染管线"
                                          "可能静默失败或字段名漂移。")})
        else:
            # rendered=True 且 rendered_usable=True：后面按分数判定
            status = None
    if status is not None:
        # PREVIEW_ONLY 已确定（rendered 缺失或渲染证据不完整）
        pass
    elif any(g.get("severity") == "BLOCKED" for g in hard_gates):
        status = "BLOCKED"
    elif hard_gates or deck_score < PASS_SCORE:
        status = "REVISE"
    else:
        status = "PASS"
    # 像素证据只覆盖部分页时不允许发布级判断：Progressive QA 是提速迭代用的，
    # 不是放宽门槛用的——未渲染的页缺少 gravity/accent/occupancy 证据。
    # 无论分数高低都记录该项，避免「恰好分数不够 → 看不出证据不全」。
    coverage = (render_evidence or {}).get("coverage") or {}
    cov_pages = int(coverage.get("rendered_pages") or 0)
    cov_total = int(coverage.get("total_pages") or 0)
    if rendered and coverage and cov_pages < cov_total:
        hard_gates.append({"code": "PIXEL_COVERAGE_PARTIAL", "slide": None,
                           "severity": "REVISE",
                           "reason": (f"像素证据仅覆盖 {cov_pages}/{cov_total} 页；"
                                      f"发布需 Level 3 全量复核。")})
        if status == "PASS":
            status = "REVISE"
    _curves = [(_field(x, "density"), _field(x, "energy")) for x in slides]
    _streak = _max_streak = 1
    for _i in range(1, len(_curves)):
        _streak = _streak + 1 if (_curves[_i] == _curves[_i - 1]
                                 and _curves[_i] != (None, None)) else 1
        _max_streak = max(_max_streak, _streak)
    deck_notes = {
        "rhythm_streak": ({"pages": _max_streak, "note":
                            "连续同密度同能量的最长段；是否要改由策略层决定"
                            "（预测层的 RHYTHM_FLAT_RISK），Critic 不判罚"}
                           if _max_streak >= 3 else None),
        "pixel_coverage": coverage or None,
        "density_curve": [_field(s, "density") for s in slides],
        "energy_curve": [_field(s, "energy") for s in slides],
        "rhythm_transitions": sum(
            1 for i in range(1, len(slides))
            if _field(slides[i], "density") != _field(slides[i - 1], "density")
            or _field(slides[i], "energy") != _field(slides[i - 1], "energy")),
    }
    # 9 维度跨 deck 汇总（design-intelligence.md：让系统性短板 5 秒内可见）。
    # 这是单纯按页评分的最大盲点——单页合格但整套 deck 在某维度
    # 系统性偏弱时，deque 平均分能立刻定位。聚合用均值；标准差暴露
    # 跨页不均（std 越大表示各页发挥越参差，节奏性越弱）。
    # 中位数比均值更抗离群值：1 页 0 分 + 5 页 5 分时，均值 4.17
    # 但中位数 5——只有中位数能告诉用户"多数页都合格，只有 1 页
    # 严重失败"。两个聚合都保留，迭代时按场景选读。
    dim_averages: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    for r in reports:
        for d in DIMENSIONS:
            dim_averages[d].append(float(r["scores"].get(d, BASELINE)))
    deck_notes["dimension_averages"] = {
        d: round(sum(v) / len(v), 2) for d, v in dim_averages.items() if v
    }
    deck_notes["dimension_medians"] = {
        d: round(sorted(v)[len(v) // 2] if len(v) % 2
                 else (sorted(v)[len(v) // 2 - 1] + sorted(v)[len(v) // 2]) / 2, 2)
        for d, v in dim_averages.items() if v
    }
    deck_notes["dimension_std"] = {
        d: round((sum((x - sum(v) / len(v)) ** 2 for x in v) / len(v)) ** 0.5, 2)
        for d, v in dim_averages.items() if v
    }
    # 取 9 维中均值最低的 2 维作为「系统性短板」提示，附在 deck_notes。
    # 每条 weakness 携带可执行的最小修复方向（指向 references 中已有章节
    # 或本次 critic 已经产生的 evidence），避免迭代时只看到"分数低"但
    # 不知道下一步该读哪条 reference 或调哪个阈值。
    if deck_notes["dimension_averages"]:
        weak = sorted(deck_notes["dimension_averages"].items(),
                      key=lambda kv: kv[1])[:2]
        fix_hints = {
            "visual_hierarchy": "检查每页 focus 是否唯一；删除或降级与焦点同级的竞争性元素。",
            "balance": "检查 gravity_anchor 与渲染 centroid 漂移；调整非对称时声明 composition_grammar。",
            "alignment": "检查左缘/顶缘是否收敛到少数轴线；如启用渲染证据，看 edge_kurtosis 是否 ≥4。",
            "contrast": "检查 ink ≥7:1、muted ≥3:1；accent_max 是否在主题 constraints 中声明。",
            "rhythm": "检查相邻页 density/energy 是否变化；声明 vs 渲染 occupancy 偏离不应 >0.20。",
            "consistency": "检查字体家族 ≤2、字号等级 ≤4、source_zone 位置跨页一致。",
            "emotional_impact": "检查 insight 是否可复述；空场景声明了 color_intent=emotion 但无媒体承担。",
            "memorability": "检查 statement 尺度（≥40px）或主动留白（sparse + protect_focus/hold_emotion）。",
            "professional_quality": "检查 rounded_rect ≤4、媒体无 asset_function、装饰面积 ≤10%。",
        }
        deck_notes["systemic_weaknesses"] = [
            {"dimension": k, "average": v,
             "fix_hint": fix_hints.get(k, "参考 design-intelligence.md 与 references 章节。")}
            for k, v in weak if v < 3.5
        ]
    deck_notes["director_verdict"] = _director_verdict(
        reports, hard_gates, deck_notes, deck_score, status)
    diagnosis = _diagnosis(reports, hard_gates, deck_notes,
                           deck_notes["director_verdict"], deck_score, status)
    return {
        # v3.2：主输出是诊断（assessment/strengths/risks/advice），分数降为置信度
        "diagnosis": diagnosis,
        "critic_version": CRITIC_VERSION,
        # 自证戳：与 QA 同一算法；发布清单据此判断报告是否来自当前 spec
        "source_spec_hash": spec_fingerprint(spec),
        "domain": "design_value",             # 工程正确性（engineering_correctness）属 QA
        "delegated_to_qa": list(DELEGATED_TO_QA),
        "deck_score": deck_score,
        "status": status,
        "hard_gates": hard_gates,
        "deck_notes": deck_notes,
        "evidence_cards_used": [c.get("reference_id") for c in (evidence_cards or [])
                                if c.get("reference_id")],
        "slides": reports,
    }


if __name__ == "__main__":
    import json, sys
    path = sys.argv[1] if len(sys.argv) > 1 else "-"
    data = json.load(sys.stdin if path == "-" else open(path, encoding="utf-8"))
    print(json.dumps(critique_deck(data), ensure_ascii=False, indent=2))
