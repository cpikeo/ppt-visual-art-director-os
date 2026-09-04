# -*- coding: utf-8 -*-
"""
Layer 0.5 · Guard（静态治理层）

职责：把 ppt-design-os.md 的硬约束**自动化断言**——网格、安全区、元素重叠、图表容量、
Accent 面积、跨页节奏。本层是只读的：不修改 spec、不生成任何元素，
只返回「检查结果 + 扣分建议」，供 QA 评分与 Release Gate 使用。

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
from typing import Any

from primitives import DEFAULT_WIDTH, DEFAULT_HEIGHT, contrast

# 网格基准（OS §02.1：间距基准 8 / 12 列栅格 / 基线 8，所有主题共享）
GRID = 8

# 图表容量上限（OS §19 / USAGE §5.4）
NUMERIC_CHART_KINDS = {
    "bar", "horizontal_bar", "column", "comparison_bar", "line", "trend",
    "single_trend_line", "area", "donut", "donut_composition", "pie",
    "waterfall", "ranked_bar", "progress_bar", "stacked_bar", "bubble",
}

CHART_LIMITS = {

    "kpi": 1, "executive_kpi": 1, "big_number": 1, "big_number_row": 5,
    "bar": 8, "horizontal_bar": 8, "column": 8, "comparison_bar": 8,
    "line": 8, "trend": 8, "single_trend_line": 8,
    "area": 8, "donut": 8, "donut_composition": 8, "pie": 8,
    "process_flow": 7, "timeline": 7, "steps": 6,
    "matrix": 12, "waterfall": 12, "architecture": 3, "bubble": 12,
    "ranked_bar": 8, "progress_bar": 6, "stacked_bar": 8,
}


def _is_grid_aligned(value: float) -> int:
    """到最近 8 倍数网格的偏差（0–4）。"""
    return int(round(abs(value - GRID * round(value / GRID))))


def _element_area(e: dict) -> float:
    try:
        return max(0.0, float(e.get("width", 0))) * max(0.0, float(e.get("height", 0)))
    except (TypeError, ValueError):
        return 0.0


def _text_units(spec: dict) -> int:
    total = 0
    for s in spec.get("slides", []):
        for e in s.get("elements", []):
            if isinstance(e, dict) and e.get("type") == "text":
                total += len(str(e.get("text", "")))
    return total


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
    """判断元素取值（颜色/填充/描边）是否引用某个主题角色或等于其字面色。"""
    if value is None:
        return False
    if isinstance(value, dict) and "gradient" in value:
        stops = value["gradient"].get("stops", value["gradient"])
        return any(_uses_role(item[1], role_name, theme) for item in stops)
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
    except (TypeError, ValueError):
        return False


def _box(e: dict, text_ink_ratio: float, text_ink_v: float) -> tuple[float, float, float, float]:
    """Return a conservative visible-ink box, not merely the text-frame box."""
    x, y = float(e.get("x", 0)), float(e.get("y", 0))
    w, h = max(0.0, float(e.get("width", 0))), max(0.0, float(e.get("height", 0)))
    if e.get("type") == "text":
        ratio = max(0.1, min(1.0, float(e.get("ink_width_ratio", text_ink_ratio))))
        vertical = max(0.1, min(1.0, float(e.get("ink_height_ratio", text_ink_v))))
        anchor = str(e.get("ink_anchor", "left_top"))
        if anchor in {"center", "middle"}:
            x += (w - w * ratio) / 2
            y += (h - h * vertical) / 2
        elif anchor in {"right", "right_top"}:
            x += w - w * ratio
        w, h = w * ratio, h * vertical
    return x, y, w, h


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
    """Validate declared page intent without inventing missing design decisions."""
    for key in ("page_family", "scene_type", "empty_space_role", "energy"):
        if not slide.get(key):
            add("page_contract", sid, "hint", f"缺少页面契约字段 {key}（建议声明以便可验证）")
    source_zone = slide.get("source_zone")
    if source_zone:
        if not isinstance(source_zone, dict):
            add("source_zone", sid, "error", "source_zone 必须是包含 x/y/width/height 的对象")
        else:
            try:
                zx, zy = float(source_zone["x"]), float(source_zone["y"])
                zw, zh = float(source_zone["width"]), float(source_zone["height"])
                if zw <= 0 or zh <= 0:
                    raise ValueError
                if zx < 0 or zy < 0 or zx + zw > canvas_width + 1 or zy + zh > canvas_height + 1:
                    add("source_zone", sid, "error", "source_zone 必须完整落在默认画布范围内")
            except (KeyError, TypeError, ValueError):
                add("source_zone", sid, "error", "source_zone 必须包含有效的 x/y/width/height 数值")
    focus = slide.get("focus_subject_id")
    if focus:
        ids = [e.get("id") for e in slide.get("elements", []) if isinstance(e, dict)]
        if focus not in ids:
            add("focus", sid, "warn", f"focus_subject_id={focus!r} 未对应页面元素")
    elif slide.get("elements"):
        add("focus", sid, "hint", "未声明 focus_subject_id；无法验证唯一视觉主锚点")


def check_spec(spec: dict, rules: dict | None = None) -> dict:
    """
    静态治理：对调用方传入的 spec 做 OS 硬约束断言。

    rules（可配置阈值，调用方传入；缺省用默认值。主题可在 `spec.theme.constraints`
    声明自身生产约束，未显式传入 rules 时自动生效——来自 VP 主题「生产约束」章节）:
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
      alignments_max : 每页文本主对齐方式上限（默认 2）
      decoration_area_max : 装饰面积上限（默认 .10）
      animation_types_max : 全套动画/切换类型上限（默认 2）
      font_levels_max     : 每页字号等级上限（默认 4，hint；可经 theme.constraints 传入）
      font_families_max   : 每页字体家族引用上限（默认 2，hint）

    returns: {
      "passed": bool, "checks": [...], "warnings": [...], "score": int
    }
    """
    rules = dict(rules or {})
    theme = spec.get("theme") or {}
    # 主题生产约束（来自 VP 主题「生产约束」章节，可被 rules 显式覆盖）
    constraints = dict(theme.get("constraints") or {})
    grid_bias = int(rules.get("grid_bias", 4))          # 非严格：≤4 仅提示
    safety_min = float(rules.get("safety_min", 48))
    overlap_ratio = float(rules.get("overlap_ratio", 0.12))
    text_ink_ratio = float(rules.get("text_ink_ratio", 0.55))
    text_ink_v = float(rules.get("text_ink_v", 0.70))
    accent_max = float(rules.get("accent_max",
                                 constraints.get("accent_max", 0.05)))
    accent_text_k = float(rules.get("accent_text_k", 0.30))
    max_charts = rules.get("max_charts", constraints.get("max_charts"))
    max_colors = rules.get("max_colors", constraints.get("max_colors"))
    check_rhythm = bool(rules.get("check_rhythm", True))
    narrative_lines_max = int(rules.get("narrative_lines_max", 6))
    semantic_colors_max = int(rules.get("semantic_colors_max", 3))
    alignments_max = int(rules.get("alignments_max", 2))
    decoration_area_max = float(rules.get("decoration_area_max", 0.10))
    animation_types_max = int(rules.get("animation_types_max", 2))
    # §07 排版预算（hint 级软约束：提示层级过碎，不扣硬分）
    font_levels_max = int(rules.get("font_levels_max",
                                    constraints.get("font_levels_max", 4)))
    font_families_max = int(rules.get("font_families_max",
                                      constraints.get("font_families_max", 2)))

    canvas = spec.get("canvas") or {}
    cw = float(canvas.get("width", DEFAULT_WIDTH))
    ch = float(canvas.get("height", DEFAULT_HEIGHT))
    slides = spec.get("slides") or []

    checks: list[dict] = []      # 每项: {"rule", "id", "level", "msg"}
    warnings: list[str] = []
    animation_types: set[str] = set()

    def add(rule, eid, level, msg):
        checks.append({"rule": rule, "id": eid, "level": level, "msg": msg})
        if level in ("warn", "error"):
            warnings.append(f"[{rule}] {msg}")

    if "grid_columns" in canvas:
        try:
            if int(canvas["grid_columns"]) != 12:
                add("grid", "canvas", "hint", "推荐使用 12 列逻辑网格；8 单位仅用于基线与间距")
        except (TypeError, ValueError):
            add("grid", "canvas", "error", "canvas.grid_columns 必须是整数")
    if "grid_unit" in canvas:
        try:
            if float(canvas["grid_unit"]) != GRID:
                add("grid", "canvas", "hint", f"推荐使用 {GRID} 单位基线网格")
        except (TypeError, ValueError):
            add("grid", "canvas", "error", "canvas.grid_unit 必须是数字")

    # ---- 每页 ----
    accent_area = 0.0
    for si, s in enumerate(slides):
        sid = s.get("id", f"slide_{si}")
        _check_page_contract(s, sid, add, cw, ch)
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
                if role not in {"source", "method", "annotation", "axis", "label", "data_label", "legend", "metadata"}:
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

            # §02.1 网格：坐标与尺寸偏离 8 倍数
            try:
                for axis, v in (("x", float(x)), ("y", float(y)),
                                ("width", float(w)), ("height", float(h))):
                    if not math.isfinite(v):
                        continue
                    bias = _is_grid_aligned(v)
                    # 发丝线/细线（≤2px）豁免尺寸维度
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

            # 安全区 / 越界（通栏条 width==cw 或 height==ch 豁免）
            full_bleed = (abs(float(w) - cw) < 1 or abs(float(h) - ch) < 1)
            if not full_bleed:
                try:
                    if float(x) < -1 or float(y) < -1 or \
                       float(x) + float(w) > cw + 1 or float(y) + float(h) > ch + 1:
                        add("safety", eid, "error", "元素越出画布边界")
                    elif float(x) < safety_min and float(x) > 0:
                        add("safety", eid, "hint",
                            f"x={float(x):.0f} < 安全区 {safety_min:.0f}")
                    elif float(y) < safety_min and float(y) > 0:
                        add("safety", eid, "hint",
                            f"y={float(y):.0f} < 安全区 {safety_min:.0f}")
                except (TypeError, ValueError):
                    pass

            # 背景安全区：仅检查内容承载对象；通栏背景/结构线不参与。
            safe_zones = s.get("safe_zones") or []
            if safe_zones and typ in ("text", "chart", "native_chart", "image"):
                if not any(_inside_zone(e, z) for z in safe_zones if isinstance(z, dict)):
                    add("safe_zone", eid, "warn", "内容对象未完整落入任何声明的文字安全区")

            # §06/§21 Accent 面积估算（含角色名与字面色两种写法）
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
                data = e.get("data") or []
                n = len(data) if isinstance(data, list) else 0
                limit = CHART_LIMITS.get(kind)
                if limit is not None and n > limit:
                    add("chart_capacity", eid, "warn",
                        f"{kind} 类别 {n} > 上限 {limit}（OS §19.4）")
                if kind in NUMERIC_CHART_KINDS:
                    if not isinstance(data, list) or not data:
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
                                value = float(raw)
                                if not math.isfinite(value):
                                    raise ValueError
                            except (TypeError, ValueError):
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
                if kind in ("donut", "donut_composition", "pie") and isinstance(data, list):
                    try:
                        if sum(max(float(r.get("value", 0)), 0) for r in data if isinstance(r, dict)) <= 0:
                            add("data_integrity", eid, "error",
                                "构成图的有效数值总和必须大于 0")
                    except (TypeError, ValueError):
                        pass
                if "highlight" in e:
                    try:
                        hi = int(e.get("highlight"))
                        if hi < 0 or hi >= n:
                            add("chart_highlight", eid, "warn",
                                f"highlight={hi} 超出数据范围 0–{max(n - 1, 0)}")
                    except (TypeError, ValueError):
                        add("chart_highlight", eid, "warn",
                            "highlight 必须是整数索引")
                # 图表标签是独立的可见对象：空间不足时不允许让渲染器硬塞进绘图区。
                show_values = e.get("show_values", kind in ("comparison_bar", "bar", "column", "donut"))
                label_policy = str(e.get("label_collision_policy", "fail"))
                try:
                    ew, eh = float(e.get("width", 0)), float(e.get("height", 0))
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

            # §06/§21 页面颜色角色收集（近似：引用色/填充/描边的唯一角色）
            for key in ("color", "fill", "stroke"):
                v = e.get(key)
                if isinstance(v, str) and v in theme.get("colors", {}):
                    page_colors.add(v)
                    if v not in {"background", "surface", "panel", "panel_soft", "panel_strong", "ink", "muted", "muted_soft", "hairline", "rule", "track", "faint", "veil", "on_dark", "on_accent"}:
                        semantic_colors.add(v)
                elif isinstance(v, str) and v.startswith("#"):
                    page_colors.add(v.upper())

        # ---- 元素重叠（text / chart / image 之间，形状不参与）----
        # 文本框 ≠ 墨迹：text 参与重叠时按 text_ink_ratio / text_ink_v
        # 收窄有效宽高（左对齐/顶端对齐假设；右对齐文本会少报，属可接受边界）。
        boxes = []
        source_zone = s.get("source_zone")
        for e in s.get("elements", []):
            if not isinstance(e, dict):
                continue
            if isinstance(source_zone, dict) and e.get("role") not in {"source", "method", "metadata"}:
                try:
                    if _inside_zone(e, source_zone):
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

        # ---- §3.1 视觉资产引擎契约：叠加层 / 有机层 / 资产合同 ----
        # 防御性：仅当 spec 实际声明相关字段时才校验，绝不臆造缺失设计决策。
        for e in s.get("elements", []):
            if not isinstance(e, dict):
                continue
            etyp = e.get("type")
            eid = e.get("id", "?")
            fill = e.get("fill")
            # 叠加层透明度（权威区间见 background-world-engine §3.1）
            if etyp == "shape" and isinstance(fill, dict):
                grad = fill.get("gradient")
                if isinstance(grad, dict):
                    for stop in (grad.get("stops") or []):
                        if isinstance(stop, (list, tuple)) and len(stop) >= 3:
                            try:
                                op = float(stop[2])
                            except (TypeError, ValueError):
                                continue
                            if op > 0.80 or op < 0.10:
                                add("overlay_opacity", eid, "warn",
                                    f"gradient 叠加透明度 {op:.0%} 超出 10%–80%（背景引擎 §3.1）")
                if "solid_color" in fill:
                    op = fill.get("opacity")
                    if isinstance(op, (int, float)) and (op > 0.70 or op < 0.20):
                        add("overlay_opacity", eid, "warn",
                            f"solid 叠加透明度 {op:.0%} 超出 20%–70%（背景引擎 §3.1）")
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

        # ---- 主题生产约束（来自 VP 主题「生产约束」章节） ----
        if max_charts is not None and chart_count > int(max_charts):
            add("theme_constraint", sid, "warn",
                f"每页图表 {chart_count} > 主题上限 {max_charts}")
        if max_colors is not None and len(page_colors) > int(max_colors):
            add("theme_constraint", sid, "hint",
                f"每页颜色 {len(page_colors)} > 主题上限 {max_colors}（仅统计引用角色/字面色）")

    if len(animation_types) > animation_types_max:
        add("animation_budget", "deck", "warn",
            f"全套动画/切换类型 {len(animation_types)} 种 > 上限 {animation_types_max}")

    # ---- 可读性底线：弱化文字（muted / secondary）对背景的对比度 ----
    # 刻度、注释、来源通常由 muted 承担；对比不足时整页"隐性不可读"，
    # 这是最常见也最容易被忽略的质量漏洞。只报告，不替调用方改色。
    _colors = theme.get("colors") or {}
    _bg = _colors.get("background")
    if isinstance(_bg, str) and _bg.startswith("#"):
        for _role in ("muted", "secondary"):
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
            elif _k < 2.5:
                add("contrast", f"theme.{_role}", "hint",
                    f"{_role} {_fg} 对背景对比 {_k:.1f}:1 偏低（建议 ≥3:1）")

    # ---- Accent 面积汇总 ----
    canvas_area = cw * ch
    if canvas_area > 0:
        ratio = accent_area / (canvas_area * max(len(slides), 1))
        if ratio > accent_max:
            add("accent_budget", "deck", "warn",
                f"全套平均 Accent 面积 {ratio:.1%} > 上限 {accent_max:.0%}（OS §06/§21）")

    # ---- §12 跨页节奏：连续页面不得同密度 ----
    if check_rhythm and len(slides) > 1:
        prev = None
        for si, s in enumerate(slides):
            cur, _ = _density_class(s)
            if prev is not None and cur == prev:
                add("rhythm", s.get("id", f"slide_{si}"), "hint",
                    f"连续页面同为 {cur} 密度（OS §12，可拆页/留白调整）")
            prev = cur

    score = max(0, 100 - sum(
        4 if c["level"] == "error" else (2 if c["level"] == "warn" else 0)
        for c in checks))
    return {
        "passed": not any(c["level"] == "error" for c in checks),
        "checks": checks,
        "warnings": warnings,
        "score": score,
    }


# --------------------------------------------------------------------------
# 可选 CLI： python guard.py build_mydeck.py
# --------------------------------------------------------------------------
def main(argv):
    import importlib.util
    from pathlib import Path
    if len(argv) < 2:
        print("usage: python guard.py <build_module.py> [--json]")
        return 1
    mod_path = Path(argv[1])
    spec_mod = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    mod = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    if spec is None:
        print("build module must define build_spec() or SPEC")
        return 1
    result = check_spec(spec)
    if "--json" in argv:
        import json
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"score={result['score']} passed={result['passed']}")
        for c in result["checks"]:
            print(f"  [{c['level']:5s}] {c['rule']:14s} {c['msg']}")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
