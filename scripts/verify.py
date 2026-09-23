# -*- coding: utf-8 -*-
"""verify.py · QA（硬错误 Guard + 判定 + 发布清单）

QA 只回答一个问题：**这份 PPTX 能不能交付？**

只拦生产级硬错误——编译失败 / 内容缺失 / 溢出 / 越界 / 重叠 / 无效资产 /
无效图表与载荷 / 来源缺失（release）/ 发布凭证断裂。输出只有 PASS / BLOCK。

QA 不做：审美裁决、密度打分、自动重设计、无限修复、warning 对话。
设计判断属于 Design Intelligence（intelligence.py 的逐页判断卡），
执行契约属于 references/contract.md——两处都不在这里重复。
"""
from __future__ import annotations

import math
import re

from primitives import (CHART_KINDS, CHART_LABEL_MIN_COUNT, CHART_LABEL_MIN_H,
                        DEFAULT_HEIGHT, DEFAULT_WIDTH, ELEMENT_TYPES,
                        is_background_declared, spec_fingerprint)

NUMERIC_CHART_KINDS = {
    "bar", "horizontal_bar", "column", "comparison_bar", "stacked_bar",
    "line", "trend", "single_trend_line", "area", "donut", "donut_composition",
    "pie", "waterfall", "ranked_bar", "progress_bar", "bubble", "sparkline",
}
SUPPORTED_CHART_KINDS = CHART_KINDS
ROWS_CHART_KINDS = ("bar", "horizontal_bar", "column", "comparison_bar", "stacked_bar",
                    "line", "trend", "single_trend_line", "area", "donut",
                    "donut_composition", "pie", "waterfall", "ranked_bar",
                    "progress_bar", "bubble", "sparkline", "process_flow", "timeline",
                    "steps", "big_number_row")
ELEMENT_METRIC_KINDS = ("kpi", "executive_kpi", "big_number")
RULE_SHAPES = frozenset({"line", "arrow"})
_COLOR_ROLE_FIELDS = ("color", "fill", "stroke", "border_color", "track_color",
                      "label_color", "background")

# ──────────────────────────────────────────────────────────────────────
# 几何与容量（物理事实，不是审美判断）
# ──────────────────────────────────────────────────────────────────────
def _text_box_capacity(e: dict) -> dict | None:
    """文本能不能装进声明的盒子（容量判定的唯一方）。

    测量原语单源在 primitives（estimate_lines / insert_script_gaps / text_width），
    compiler.add_text 渲染用的是同一组原语：
      * 换行按 \\n 拆段，每段用 estimate_lines(插入中西细空格后的文本)；
      * 需要高度 = 总行数 × size × line_height（默认 1.35）；
      * 可用高度 = height − 2 × padding，容差 +1px。
    """
    try:
        size = float(e.get("size", 18))
        h = float(e.get("height", 0) or 0)
        w = float(e.get("width", 0) or 0)
        pad = float(e.get("padding", 0) or 0)
        lh = float(e.get("line_height", 1.35) or 1.35)
    except (TypeError, ValueError):
        return None
    if size <= 0 or h <= 0 or w <= 0 or not all(map(math.isfinite, (size, h, w, pad, lh))):
        return None
    from primitives import estimate_lines, insert_script_gaps, text_width
    wrap = e.get("wrap", True) is not False
    usable_w = w - 2 * pad
    if usable_w <= 0:
        return None
    lines = 0
    for raw_line in str(e.get("text", "")).split("\n"):
        if not raw_line:
            lines += 1
            continue
        lines += estimate_lines(insert_script_gaps(raw_line), usable_w, size, wrap)
    width_need = max((text_width(insert_script_gaps(t), size,
                                 float(e.get("char_spacing", 0) or 0))
                      for t in str(e.get("text", "")).split("\n")), default=0)
    need = lines * size * lh
    usable_h = h - 2 * pad
    declared_max = e.get("max_lines")
    over_max = (isinstance(declared_max, int) and not isinstance(declared_max, bool)
                and declared_max >= 1 and lines > declared_max)
    return {"lines": lines, "need": need, "usable": usable_h, "size": size,
            "line_height": lh, "max_lines": declared_max,
            "over_height": need > usable_h + 1, "over_max_lines": bool(over_max),
            "over_width": not wrap and width_need > usable_w + 2, "width_need": width_need}


def _element_rect(e: dict):
    try:
        x, y = float(e.get("x", 0)), float(e.get("y", 0))
        w, h = float(e.get("width", 0)), float(e.get("height", 0))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (x, y, w, h)):
        return None
    return x, y, w, h


def _is_rule_shape(e: dict) -> bool:
    return str(e.get("type")) == "shape" and str(e.get("shape") or "") in RULE_SHAPES


def _box(e: dict, text_ink_ratio: float = 1.0, text_ink_v: float = 1.0):
    """元素的有效墨迹盒：文本框不等于墨迹（按系数收窄）。"""
    x, y, w, h = float(e.get("x", 0)), float(e.get("y", 0)), \
        float(e.get("width", 0)), float(e.get("height", 0))
    if str(e.get("type")) == "text":
        w *= text_ink_ratio
        h *= text_ink_v
    return x, y, w, h


def _intersects_zone(e: dict, zone: dict) -> bool:
    x, y, w, h = _box(e)
    try:
        zx, zy = float(zone.get("x", 0)), float(zone.get("y", 0))
        zw, zh = float(zone.get("width", 0)), float(zone.get("height", 0))
    except (TypeError, ValueError):
        return False
    return (x < zx + zw) and (x + w > zx) and (y < zy + zh) and (y + h > zy)


def _overlap_allowed(a: dict, b: dict) -> bool:
    """作者显式声明的叠压是合法手法（重叠只拦无意的碰撞）。"""
    for x in (a, b):
        if x.get("overlap_ok") is True or x.get("layer") in ("background", "backdrop"):
            return True
    return False


def _bg_qualified(e: dict, cw: float, ch: float) -> tuple[bool, str | None]:
    """整幅背景资格：声明 layer=background/backdrop 且覆盖画布 ≥60%。"""
    if not is_background_declared(e):
        return False, None
    rect = _element_rect(e)
    if not rect:
        return False, "背景层几何无效"
    _, _, w, h = rect
    coverage = (w * h) / max(cw * ch, 1.0)
    if coverage < 0.60:
        return False, f"声明为背景层但只覆盖 {coverage:.0%} 画布（<60%）：伪背景按内容对象处理"
    return True, None


# ──────────────────────────────────────────────────────────────────────
# Guard（唯一执法身份：hard）
# ──────────────────────────────────────────────────────────────────────
def _invalid_spec_result(message: str) -> dict:
    check = {"rule": "spec_schema", "id": "spec", "level": "error", "msg": message}
    return {"passed": False, "checks": [check], "warnings": [message]}


def check_spec(spec: dict, rules: dict | None = None) -> dict:
    """硬门：结构 / 几何 / 容量 / 碰撞 / 数据 / 出处 / 资产。

    rules 只接受与物理事实有关的阈值（overlap_ratio / text_ink_ratio /
    text_ink_v / require_provenance）；审美数字不在这里发明。
    returns {"passed", "checks": [{rule,id,level,msg}], "warnings": [...]}
    """
    if not isinstance(spec, dict):
        return _invalid_spec_result("spec 顶层必须是对象/dict")
    if spec.get("_input_error"):
        return _invalid_spec_result(str(spec.get("_input_error")))
    for key in ("theme", "canvas"):
        if spec.get(key) not in (None, {}) and not isinstance(spec.get(key), dict):
            return _invalid_spec_result(f"spec.{key} 必须是对象/dict")
    if spec.get("slides") is not None and not isinstance(spec.get("slides"), list):
        return _invalid_spec_result("spec.slides 必须是数组/list")

    rules = dict(rules or {})
    theme = spec.get("theme") or {}
    overlap_ratio = float(rules.get("overlap_ratio", 0.12) or 0.12)
    text_ink_ratio = float(rules.get("text_ink_ratio", 0.55) or 0.55)
    text_ink_v = float(rules.get("text_ink_v", 0.70) or 0.70)
    require_provenance = bool(rules.get("require_provenance", False))
    canvas = spec.get("canvas") or {}
    cw = _dim(canvas.get("width"), DEFAULT_WIDTH)
    ch = _dim(canvas.get("height"), DEFAULT_HEIGHT)
    slides = spec.get("slides") or []

    checks: list[dict] = []
    warnings: list[str] = []

    def add(rule, eid, level, msg):
        checks.append({"rule": rule, "id": eid, "level": level, "msg": msg})
        if level in ("warn", "error"):
            warnings.append(f"[{rule}] {msg}")

    if not slides:
        add("slide_schema", "slides", "error",
            "spec 里没有任何页（slides 为空）；空 deck 不是可交付物")
    if "grid_columns" in canvas and not _positive_int(canvas.get("grid_columns")):
        add("canvas_schema", "canvas", "error", "canvas.grid_columns 必须是正整数")
    if "grid_unit" in canvas and not _positive_num(canvas.get("grid_unit")):
        add("canvas_schema", "canvas", "error", "canvas.grid_unit 必须是正的有限数字")

    known_tokens = set()
    if isinstance(theme.get("colors"), dict):
        known_tokens |= {str(k).strip() for k in theme["colors"]}
        try:
            from primitives import derive_tokens
            known_tokens |= set(derive_tokens(dict(theme["colors"])))
        except Exception:
            pass

    # ---- 单趟页面扫描（结构 → 碰撞/来源区/背景资格，同页元素只走一遍）----
    for si, slide in enumerate(slides):
        if not isinstance(slide, dict):
            add("slide_schema", "slides", "error", "每个 slide 必须是对象/dict")
            continue
        sid = str(slide.get("id", f"slide_{si}"))
        if "elements" in slide and not isinstance(slide.get("elements"), list):
            add("slide_schema", sid, "error", "slide.elements 必须是数组/list")
        drawable = [e for e in (slide.get("elements") or []) if isinstance(e, dict)]
        if not drawable and not slide.get("background"):
            add("page_contract", sid, "error",
                "这一页没有任何元素，也没有 background：画面上什么都没有"
                "（要么给元素，要么给背景）")
        if slide.get("page_intent") is not None and not isinstance(slide.get("page_intent"), dict):
            add("slide_schema", sid, "error", "slide.page_intent 必须是对象/dict")
        bg = slide.get("background")
        if isinstance(bg, dict) and isinstance(bg.get("color"), (dict, list, tuple)):
            add("element_schema", sid, "error",
                "slide.background.color 须为 #HEX 字符串或 theme token")
        for e in drawable:
            _check_element(e, sid, si, add, known_tokens, cw, ch,
                           require_provenance=require_provenance)
        _check_collisions(slide, add, cw, ch, overlap_ratio,
                          text_ink_ratio, text_ink_v)

    # ---- 跨页口径一致（口径打架会误导决策；对比度属设计判断，不在 QA）----
    _check_metric_units(slides, add)
    return {"passed": not any(c["level"] == "error" for c in checks),
            "checks": checks, "warnings": warnings}


def _dim(value, default):
    try:
        if isinstance(value, bool):
            raise ValueError
        v = float(value)
        return v if math.isfinite(v) and v > 0 else float(default)
    except (TypeError, ValueError, OverflowError):
        return float(default)


def _positive_int(value) -> bool:
    try:
        return not isinstance(value, bool) and int(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _positive_num(value) -> bool:
    try:
        return not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _unknown_color(value, known_tokens) -> str | None:
    """认不出的 token 名（渲染层会静默回落，于是「写了不生效」不留痕迹）。"""
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or raw.lower() in ("none", "transparent"):
        return None
    if raw.startswith("#"):
        body = raw[1:]
        ok = len(body) in (3, 6, 8) and all(c in "0123456789abcdefABCDEF" for c in body)
        return None if ok else raw
    return None if raw in known_tokens else raw


def _check_element(e: dict, sid: str, si: int, add, known_tokens, cw: float,
                   ch: float, *, require_provenance: bool = False) -> None:
    eid = str(e.get("id", f"{sid}[{si}]"))
    typ = str(e.get("type", "text"))
    if typ not in ELEMENT_TYPES:
        add("element_type", eid, "error",
            f"未知元素类型 {typ!r}（编译期会静默跳过；合法类型：{sorted(ELEMENT_TYPES)}）")
        return
    color = e.get("color")
    if isinstance(color, (dict, list, tuple, set)):
        add("element_schema", eid, "error",
            f"元素配色须为 #HEX 字符串或 theme token，收到 {type(color).__name__}")
    if typ == "shape":
        if e.get("color") is not None and "fill" not in e:
            add("element_schema", eid, "error",
                "形状填充须走 fill；顶层 color 在形状上被静默丢弃 → 元素不可见")
        if e.get("line") is not None and "stroke" not in e:
            add("element_schema", eid, "error",
                "形状描边须走 stroke/stroke_width；顶层 line 字段被静默丢弃")
    fill = e.get("fill")
    if fill is not None and not isinstance(fill, str) and (
            isinstance(fill, bool)
            or not (isinstance(fill, dict) and ("type" in fill or "color" in fill))):
        add("element_schema", eid, "error",
            "fill 须为 {type: solid|gradient|none, ...} dict、#HEX 或缺省")

    if typ == "text":
        if "text" not in e:
            hint = "；检测到 content，请改用 text" if "content" in e else ""
            add("TEXT_FIELD_MISSING", eid, "error", f"text 元素缺少必需字段 'text'{hint}")
        elif "content" in e:
            add("TEXT_FIELD_INVALID", eid, "error",
                "text 元素使用了未消费字段 'content'，请改用顶层字段 'text'")
        if "style" in e:
            add("TEXT_STYLE_INVALID", eid, "error",
                "text 元素使用了未消费的嵌套字段 'style'；size/color/bold/line_height 放顶层")

    # 几何：缺项 / 非有限 / 退化 —— 不可见的内容比溢出更隐蔽
    missing = [k for k in ("x", "y", "width", "height") if e.get(k) is None]
    if missing:
        add("element_schema", eid, "error",
            f"geometry 缺项 {', '.join(missing)}（契约必填；缺省按 0 计 → 元素不可见）")
    else:
        rect = _element_rect(e)
        if rect is None:
            add("element_schema", eid, "error",
                "geometry 非数值/非有限（x/y/width/height 必须是数字）")
        else:
            fx, fy, fw, fh = rect
            if _is_rule_shape(e):
                if fw <= 0 and fh <= 0:      # 一维对象：线允许 height=0
                    add("element_schema", eid, "error",
                        "geometry 退化（线的 width 与 height 同时为 0 → 零长度不可见）")
            elif fw <= 0 or fh <= 0:
                add("element_schema", eid, "error",
                    f"geometry 退化（width={fw:g}, height={fh:g} ≤ 0 → 元素不可见）")
            if rect:
                bleed_x = abs(fw - cw) < 1 and abs(fx) <= 1
                bleed_y = abs(fh - ch) < 1 and abs(fy) <= 1
                if (not bleed_x and (fx < -1 or fx + fw > cw + 1)) or \
                        (not bleed_y and (fy < -1 or fy + fh > ch + 1)):
                    add("safety", eid, "error", "元素越出画布边界")

    if known_tokens:
        for field in _COLOR_ROLE_FIELDS:
            if field not in e:
                continue
            value = e.get(field)
            if isinstance(value, dict):
                value = value.get("color") if value.get("type") in (None, "solid") else None
            bad = _unknown_color(value, known_tokens)
            if bad:
                add("color_token", eid, "error",
                    f"{field}={bad!r} 既不是主题色角色、也不是合法 #HEX："
                    f"渲染层会静默回落（配色写了不生效）。可用角色：{sorted(known_tokens)[:8]}…")

    if typ in ("text", "shape") and str(e.get("text") or "").strip():
        te = e if typ == "text" else dict(e, size=e.get("text_size", 16),
                                          wrap=e.get("text_wrap", True),
                                          line_height=e.get("text_line_height", 1.25))
        cap = _text_box_capacity(te)
        if cap and cap["over_height"]:
            add("text_capacity", eid, "error",
                f"估算高度 {cap['need']:.0f}px 超出文本框可用高度 {cap['usable']:.0f}px"
                f"（{cap['lines']} 行 × 字号 {cap['size']:g} × 行高 {cap['line_height']:g}）："
                "加框高 / 减行数 / 删字，不要缩字号")
        elif cap and cap["over_width"]:
            add("text_capacity", eid, "error",
                f"禁止换行的文字估算宽度 {cap['width_need']:.0f}px 超出文本框宽度"
                f"{cap['usable']:.0f}px；加宽或删字")
        elif cap and cap["over_max_lines"]:
            add("text_capacity", eid, "error",
                f"估算 {cap['lines']} 行 > 声明 max_lines {cap['max_lines']}："
                "文本会被截断或挤出框；删句、改写或放宽 max_lines")

    if typ in ("chart", "native_chart"):
        _check_chart(e, eid, add, require_provenance=require_provenance)


def _check_chart(e: dict, eid: str, add, *, require_provenance: bool) -> None:
    """图表：类型白名单 → 载荷 → 数据完整性 → 标签空间 → 出处。"""
    kind = str(e.get("chart_kind") or e.get("kind", ""))
    if kind not in SUPPORTED_CHART_KINDS:
        add("chart_type", eid, "error",
            f"未知 chart_kind={kind!r}；合法值：{sorted(SUPPORTED_CHART_KINDS)}")
        return
    data = e.get("data") or []
    if kind in ELEMENT_METRIC_KINDS and not str(e.get("value") or "").strip():
        add("chart_payload", eid, "error",
            f"{kind} 缺少元素级 value（大数字没有数字）")
    if kind == "matrix":
        points = e.get("points")
        if not (isinstance(points, list) and points):
            add("chart_payload", eid, "error", "matrix 缺少 points[{x,y,label}]；无点不绘图")
    elif kind == "architecture":
        layers = e.get("layers")
        clean = [str(x).strip() for x in layers[:3]] if isinstance(layers, list) else []
        if not clean or not all(clean):
            add("chart_payload", eid, "error",
                "architecture 必须声明 layers（1–3 条非空层名）；没有层名就不画")
    elif kind in ROWS_CHART_KINDS:
        multi = (isinstance(e.get("series"), list) and bool(e.get("series"))
                 and isinstance(e["series"][0], dict))
        usable = [r for r in data if isinstance(r, dict) and str(r.get("label") or "").strip()]
        if not multi and not usable:
            add("chart_payload", eid, "error",
                f"{kind} 需要 data 行（每行含非空 label）；空载荷会画出空白页")

    series = e.get("series")
    multi = isinstance(series, list) and bool(series) and isinstance(series[0], dict)
    categories = e.get("categories") or []
    n_cat = len(categories) if isinstance(categories, list) else 0
    n_series = len(series) if multi else 0
    if kind in NUMERIC_CHART_KINDS:
        if multi:
            if not n_cat:
                add("data_integrity", eid, "error", "多序列图表缺少 categories")
            for sidx, sr in enumerate(series):
                vals = sr.get("values") if isinstance(sr, dict) else None
                if not isinstance(vals, list) or not vals:
                    add("data_integrity", f"{eid}[s{sidx}]", "error",
                        f"series[{sidx}] 缺少 values")
                    continue
                if n_cat and len(vals) != n_cat:
                    add("data_integrity", f"{eid}[s{sidx}]", "error",
                        f"series[{sidx}] values 长度 {len(vals)} 与 categories 长度 {n_cat} 不一致")
                for vi, v in enumerate(vals):
                    if not _finite(v):
                        add("data_integrity", f"{eid}[s{sidx}][{vi}]", "error",
                            f"series[{sidx}] value={v!r} 不是有限数字")
        elif not isinstance(data, list) or not data:
            add("data_integrity", eid, "error", "数值图表缺少 data，无法验证或渲染")
        else:
            for di, row in enumerate(data):
                if not isinstance(row, dict) or "label" not in row:
                    add("data_integrity", f"{eid}[{di}]", "error",
                        "图表数据行必须包含 label")
                    continue
                if not str(row.get("label", "")).strip():
                    add("data_integrity", f"{eid}[{di}]", "error", "图表数据 label 不得为空")
                if row.get("value") is None:
                    add("data_integrity", f"{eid}[{di}]", "error",
                        "图表数据 value 缺失；缺失值请显式说明，不得静默补零")
                    continue
                if not _finite(row.get("value")):
                    add("data_integrity", f"{eid}[{di}]", "error",
                        f"图表数据 value={row.get('value')!r} 不是有限数字")
                elif kind in {"ranked_bar", "progress_bar", "stacked_bar", "bubble"} \
                        and float(row["value"]) < 0:
                    add("data_integrity", f"{eid}[{di}]", "error",
                        f"{kind} 不接受负值；请改用可表达正负关系的图表")
            if kind == "progress_bar" and not _positive_num(e.get("max", 100)):
                add("data_integrity", eid, "error", "progress_bar 的 max 必须是正数")
    if not multi and kind in ("donut", "donut_composition", "pie") and isinstance(data, list):
        total = 0.0
        for row in data:
            if isinstance(row, dict) and _finite(row.get("value")):
                total += max(float(row["value"]), 0)
        if total <= 0:
            add("data_integrity", eid, "error", "构成图的有效数值总和必须大于 0")

    if "highlight" in e:
        names = ([str(sr.get("name", "")) for sr in (series or []) if isinstance(sr, dict)]
                 if multi else [str(r.get("label", "")) for r in data if isinstance(r, dict)])
        hi = e.get("highlight")
        try:
            idx = int(hi)
            upper = n_series if multi else (len(data) if isinstance(data, list) else 0)
            if idx < 0 or idx >= upper:
                add("chart_highlight", eid, "warn",
                    f"highlight={hi} 超出数据范围 0–{max(upper - 1, 0)}")
        except (TypeError, ValueError):
            if str(hi).strip() not in names:
                add("chart_highlight", eid, "warn",
                    f"highlight={hi!r} 既不是索引也不匹配任何类别名/序列名，会被忽略")

    # 标签空间：标签是独立可见对象，空间不足不允许渲染器硬塞（不缩字号）
    n = len(data) if isinstance(data, list) else 0
    show_values = e.get("show_values", kind in ("comparison_bar", "bar", "column", "donut"))
    try:
        height = float(e.get("height", 0))
        if show_values and n >= CHART_LABEL_MIN_COUNT and height < CHART_LABEL_MIN_H:
            level = "error" if str(e.get("label_collision_policy", "fail")) == "fail" else "warn"
            add("chart_label_collision", eid, level,
                f"{kind} 含 {n} 个标签但高度 {height:.0f}px 不足；应拆图/减少类别，不能缩小字体")
    except (TypeError, ValueError):
        add("chart_label_collision", eid, "error", "图表标签安全参数必须是数字")

    if kind in NUMERIC_CHART_KINDS:
        nested = e.get("provenance") if isinstance(e.get("provenance"), dict) else {}
        missing = []
        for key, label in (("source", "来源"), ("unit", "单位"), ("period", "期间"),
                           ("basis", "比较口径")):
            value = e.get(key) or nested.get(key)
            if not (isinstance(value, str) and value.strip()):
                missing.append(label)
        if missing and require_provenance:
            add("data_provenance", eid, "error",
                f"数值图表缺少 {'/'.join(missing)} 声明；来源不可省略、单位与期间必须显式")


def _finite(value) -> bool:
    try:
        return not isinstance(value, bool) and math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _check_collisions(slide: dict, add, cw: float, ch: float,
                      overlap_ratio: float, text_ink_ratio: float, text_ink_v: float) -> None:
    """重叠 / 来源区侵入 / 背景资格（同页元素一次遍历，背景覆盖只算一次）。"""
    source_zone = slide.get("source_zone")
    boxes = []
    for e in (slide.get("elements") or []):
        if not isinstance(e, dict):
            continue
        if is_background_declared(e):
            qualified, note = _bg_qualified(e, cw, ch)
            if not qualified and note:
                add("background_layer", e.get("id", "?"), "error", note)
            if qualified:
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
            rect = _box(e, text_ink_ratio, text_ink_v)
        except (TypeError, ValueError):
            continue
        boxes.append((e, e.get("id", "?"), *rect))
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            ae, _, ax, ay, aw, ah = a
            be, _, bx, by, bw, bh = b
            inter = max(0.0, min(ax + aw, bx + bw) - max(ax, bx)) * \
                max(0.0, min(ay + ah, by + bh) - max(ay, by))
            if inter <= 0:
                continue
            smaller = min(max(aw * ah, 1.0), max(bw * bh, 1.0))
            ratio = inter / smaller
            if ratio > overlap_ratio and not _overlap_allowed(ae, be):
                add("overlap", f"{a[1]}∩{b[1]}", "error",
                    f"有效墨迹重叠 {ratio:.0%} > 容忍 {overlap_ratio:.0%}；"
                    "需拆分、缩短或重新布局")


def _check_metric_units(slides: list, add) -> None:
    seen: dict[str, dict] = {}
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        sid = str(slide.get("id", "?"))
        for e in (slide.get("elements") or []):
            if not isinstance(e, dict) or str(e.get("type")) not in ("chart", "native_chart"):
                continue
            kind = str(e.get("chart_kind") or e.get("kind", ""))
            if kind not in NUMERIC_CHART_KINDS:
                continue
            metric = str(e.get("metric") or e.get("series_name") or "").strip()
            unit = e.get("unit")
            if not metric or not isinstance(unit, str) or not unit.strip():
                continue
            rec = seen.setdefault(metric, {"units": set(), "pages": []})
            rec["units"].add(unit.strip())
            rec["pages"].append(sid)
    for metric, rec in sorted(seen.items()):
        if len(rec["units"]) > 1:
            add("metric_consistency", f"metric:{metric}", "error",
                f"指标「{metric}」跨页单位不一致 {sorted(rec['units'])}"
                f"（同一指标必须同一单位，否则读者读成两套数字）")


# ══════════════════════════════════════════════════════════════════
# Normalizer（机械归一化 · 生产链第 0 级；单趟、幂等）
# ══════════════════════════════════════════════════════════════════
SPACING_STEP = 4
_COLOR_FIELDS = ("color", "background", "border_color", "stroke", "accent",
                 "fill_color", "track_color", "label_color")
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_REPORT_ITEM_CAP = 200


def _snap_pos(value: float, grid: int) -> int:
    return int(round(value / grid)) * grid


def _snap_size(value: float, grid: int) -> float:
    """尺寸落网格——但**亚网格厚度按原值保留**。

    为什么不再 `max(grid, ...)`（v6.5 修）：发丝线的厚度是作者的设计决定。
    把 1px 的线强行抬到 4px 是 4× 的视觉重量改变，而且没有任何提示——
    「归一化」越权改了排版，不是在对齐节奏。小于一个网格的尺寸一律原样透传；
    退化（≤0）仍由 guard 的 geometry 硬门拦截，这里不代偿。
    """
    if 0 < value < grid:
        return value
    return max(grid, int(round(value / grid)) * grid)


def _snap_span(pos: float, size: float, grid: int) -> tuple:
    """把一维（位置, 尺寸）落到网格上，**同心关系优先于边缘对齐**。

    根因（v6.5 修）：位置与尺寸各自独立吸附时，中心会漂移最多 grid/2。
    作者让一条 1px 轴线与一个骑在它上面的对象共享同一条中线，吸附后
    线挪了、对象没挪——产物里对象永远悬在线的一侧，而 guard 看不出问题
    （几何合法、不重叠、不溢出），于是错位一路走到交付。

    规则：
      · 厚度 ≥ 一个网格 → 位置与尺寸照常吸附（版面节奏由网格主导）
      · 厚度 < 一个网格（发丝线、细轴）→ 吸附**中心**，厚度原样保留
        这样「1px 线的中心」与「8px 对象的中心」落在同一条网格线上，必然同心。
    幂等：第二趟输入的中心已在网格上，吸附是恒等变换。
    """
    size_n = _snap_size(size, grid)
    # 尺寸被改写时，保住中心——「把 6px 圆整到 8px」不该顺带把对象挪走。
    # 亚网格厚度（发丝线）同样走中心口径：它的上边缘没有对齐意义，中线才有。
    if size_n != size or 0 < size_n < grid:
        center = _snap_pos(pos + size / 2.0, grid)
        return center - size_n / 2.0, size_n
    return _snap_pos(pos, grid), size_n


def _canonical_color(value, tokens: dict) -> tuple:
    if not isinstance(value, str):
        return value, None
    raw = value.strip()
    if raw in tokens:
        return tokens[raw], f"{raw}→{tokens[raw]}"
    short = raw[:-1] if len(raw) == 4 else None
    if raw.startswith("#") and len(raw) == 4:
        return "#" + "".join(c * 2 for c in raw[1:]), f"{raw}→{short}*2"
    return value, None


def normalize_spec(spec: dict, *, grid: bool = True, colors: bool = True) -> tuple[dict, dict]:
    """几何落 8/4 单位、颜色/字体名规范化。单趟机械变换：对已规范输入是恒等。"""
    import copy
    report = {"changes": [], "counts": {}}
    out = copy.deepcopy(spec) if isinstance(spec, dict) else {}
    theme = out.get("theme") or {}
    colors_map = theme.get("colors") if isinstance(theme.get("colors"), dict) else {}
    tokens = {str(k): str(v) for k, v in colors_map.items()} if colors else {}

    def record(scope, eid, field, old, new, rule):
        report["counts"][rule] = report["counts"].get(rule, 0) + 1
        if len(report["changes"]) < _REPORT_ITEM_CAP:
            report["changes"].append({"scope": scope, "id": eid, "field": field,
                                      "from": old, "to": new, "rule": rule})

    grid_step = SPACING_STEP
    for slide in (out.get("slides") or []):
        if not isinstance(slide, dict):
            continue
        sid = str(slide.get("id", "?"))
        for e in (slide.get("elements") or []):
            if not isinstance(e, dict):
                continue
            eid = str(e.get("id", "?"))
            if grid and e.get("snap") is not False:
                # 成对吸附：(x, width) 与 (y, height) 各作为一维整体处理，
                # 中心关系不被拆散（逐字段独立吸附会让同心对象漂开）。
                for pos_f, size_f in (("x", "width"), ("y", "height")):
                    pos, size = e.get(pos_f), e.get(size_f)
                    if isinstance(pos, bool) or not isinstance(pos, (int, float)):
                        continue
                    if isinstance(size, bool) or not isinstance(size, (int, float)):
                        new_pos = _snap_pos(float(pos), grid_step)
                        if new_pos != pos:
                            record(sid, eid, pos_f, pos, new_pos, "grid")
                            e[pos_f] = new_pos
                        continue
                    # 线是一维对象：厚度方向本就允许 0，不参与尺寸吸附
                    if size_f == "height" and _is_rule_shape(e):
                        new_pos = _snap_pos(float(pos), grid_step)
                        if new_pos != pos:
                            record(sid, eid, pos_f, pos, new_pos, "grid")
                            e[pos_f] = new_pos
                        continue
                    new_pos, new_size = _snap_span(float(pos), float(size), grid_step)
                    if new_pos != pos:
                        record(sid, eid, pos_f, pos, new_pos, "grid")
                        e[pos_f] = new_pos
                    if new_size != size:
                        record(sid, eid, size_f, size, new_size, "grid")
                        e[size_f] = new_size
            for field in _COLOR_FIELDS:
                value = e.get(field)
                if isinstance(value, str):
                    new, note = _canonical_color(value, tokens)
                    if note:
                        record(sid, eid, field, value, new, "color")
                        e[field] = new
                elif isinstance(value, dict) and isinstance(value.get("color"), str):
                    new, note = _canonical_color(value["color"], tokens)
                    if note:
                        record(sid, eid, f"{field}.color", value["color"], new, "color")
                        value["color"] = new
    return out, report


# ══════════════════════════════════════════════════════════════════
# 判定与发布清单（PASS / BLOCK 二态）
# ══════════════════════════════════════════════════════════════════
import time as _time

MODES = {
    "spec": {"label": "Spec · 只诊断", "compile": False,
             "aim": "归一化 + 硬门判定，不写 PPTX"},
    "draft": {"label": "Draft · 创作（默认）", "compile": True,
              "aim": "硬门 + 编译一次通过，产出可编辑 PPTX 与分组修复包"},
    "release": {"label": "Release · 交付", "compile": True,
                "aim": "draft 全部 + 出处硬门 + 结构预览证据 + 发布清单"},
}
DEFAULT_MODE = "draft"

_RULE_CODES = {
    "overlap": "OVERLAP", "source_zone": "SOURCE_COLLISION",
    "chart_label_collision": "CHART_LABEL_COLLISION",
    "text_capacity": "TEXT_OVERFLOW",
    "data_integrity": "DATA_INTEGRITY_FAIL", "data_provenance": "DATA_INTEGRITY_FAIL",
    "metric_consistency": "DATA_INTEGRITY_FAIL",
    "chart_type": "CHART_TYPE_FAIL", "chart_payload": "CHART_TYPE_FAIL",
    "background_layer": "GUARD_FAIL", "color_token": "GUARD_FAIL",
    "element_type": "GUARD_FAIL", "element_schema": "GUARD_FAIL",
    "safety": "GUARD_FAIL", "page_contract": "GUARD_FAIL", "slide_schema": "GUARD_FAIL",
    "spec_schema": "GUARD_FAIL", "canvas_schema": "GUARD_FAIL",
    "TEXT_FIELD_MISSING": "GUARD_FAIL", "TEXT_FIELD_INVALID": "GUARD_FAIL",
    "TEXT_STYLE_INVALID": "GUARD_FAIL",
}
FIX_HINTS = {
    "OVERLAP": "文本/图表/图片/来源区墨迹不相交；挪几何或删元素，不缩字号。",
    "SOURCE_COLLISION": "来源区（source_zone）内只放 role∈{source,method,metadata} 的文字。",
    "CHART_LABEL_COLLISION": "用 label_collision_policy:hide_redundant|move_outside|fail 处置，不缩字号。",
    "TEXT_OVERFLOW": "框高 ≥ 字号×行高×行数；减行数/减字数/加框高，三选一。",
    "DATA_INTEGRITY_FAIL": "每行 label + 有限 value；数值图齐 source/unit/period/basis；同指标同单位。",
    "CHART_TYPE_FAIL": "图表类型在白名单内且数据形态匹配（占比≠趋势）；载荷不可为空。",
    "COMPILE_FAIL": "按编译 warnings 修 schema，不绕过硬门。",
    "GUARD_FAIL": "按下述明细逐条修：schema / 越界 / 退化几何 / 未知类型优先。",
    "ASSET_WORKFLOW_FAIL": "按 asset_workflow.issues 修：出图 / 登记 / 重新核验。",
}
BLOCKING_CODES = set(FIX_HINTS)


def mode_profile(mode):
    key = str(mode or "").strip().lower() or DEFAULT_MODE
    prof = MODES.get(key)
    if prof is None:
        key, prof = DEFAULT_MODE, MODES[DEFAULT_MODE]
    return {"mode": key, **prof}


def _rule_to_code(rule):
    return _RULE_CODES.get(rule, "GUARD_FAIL")


def build_fix_plan(guard_report, compile_report) -> dict:
    """阻断项按根因分组，组内携带 error 明细——修复包自足，零回读。"""
    groups: dict = {}

    def _g(code):
        return groups.setdefault(code, {"root_cause": code, "count": 0,
                                        "ids": [], "details": []})
    for chk in (guard_report or {}).get("checks", []):
        if not isinstance(chk, dict) or chk.get("level") != "error":
            continue
        g = _g(_rule_to_code(chk.get("rule")))
        g["count"] += 1
        pid = str(chk.get("id") or "")
        if pid and pid not in g["ids"]:
            g["ids"].append(pid)
        if len(g["details"]) < 12:
            g["details"].append({"id": pid, "rule": chk.get("rule"),
                                 "msg": str(chk.get("msg") or "")[:220]})
    cr = compile_report if isinstance(compile_report, dict) else {}
    if cr and not cr.get("passed", False) and not cr.get("skipped"):
        g = _g("COMPILE_FAIL")
        g["count"] += 1
        for w in (cr.get("warnings") or [])[:6]:
            if len(g["details"]) < 12:
                g["details"].append({"id": None, "rule": "compiler", "msg": str(w)[:220]})
    for code, g in groups.items():
        g["fix"] = FIX_HINTS.get(code, "")
    return {"policy": "本轮一次修完全部组，修完复跑同一条 check 命令；不逐条对话。",
            "groups": list(groups.values())}


def release_guard_rules(mode, guard_rules=None):
    rules = dict(guard_rules or {})
    if mode == "release" and "require_provenance" not in rules:
        rules["require_provenance"] = True
    return rules


def verdict(spec, *, mode=None, guard_report, compile_report,
            runtime_facts=None, spec_hash: str | None = None) -> dict:
    """判定：只消费报告（硬门 + 编译），不编译、不读产物字节。

    `spec_hash` 由调用方传入时直接复用（一轮执行只算一次 spec 身份）。
    """
    t0 = _time.time()
    prof = mode_profile(mode)
    mode = prof["mode"]
    facts = dict(runtime_facts or {})
    do_compile = bool(prof["compile"])
    guard = guard_report if isinstance(guard_report, dict) else {}
    if not isinstance(spec, dict):
        spec = {"slides": [], "_input_error": "spec 顶层必须是对象/dict"}
    blocking = [c for c in guard.get("checks", []) if c.get("level") == "error"]
    cr = compile_report if isinstance(compile_report, dict) else {}
    compile_failed = not cr.get("passed", False)
    codes: list = []
    for c in blocking:
        code = _rule_to_code(c.get("rule"))
        if code not in codes:
            codes.append(code)
    if compile_failed and not cr.get("skipped"):
        codes.append("COMPILE_FAIL")
    codes = [c for c in codes if c in BLOCKING_CODES]
    passed = not codes
    status = "BLOCKED" if codes else ("PREVIEW_ONLY" if not do_compile else "PASS")
    release_eligible = bool(status == "PASS" and mode == "release" and cr.get("passed"))
    result = {
        "source_spec_hash": spec_hash or spec_fingerprint(spec),
        "normalization": facts.get("normalization"),
        "execution": {"entrypoint": "vao.py", "mode": mode, "profile": prof["label"],
                      "compiled": do_compile,
                      "provenance_required": bool(facts.get("provenance_required", False)),
                      "visual_evidence": "ghost_preview"},
        "verdict": {"verdict": "BLOCKED" if codes else "PASS", "status": status,
                    "blocking": len(blocking), "codes": codes,
                    "question": "这份 PPT 能不能交付？"},
        "status": status, "passed": passed, "release_eligible": release_eligible,
        "blocking_items": len(blocking), "failure_codes": codes,
        "affected_slides": sorted({str(c.get("id")).split(":")[0].split("[")[0]
                                   for c in blocking if c.get("id")}),
        "blocking_detail": [{"rule": c.get("rule"), "id": c.get("id"),
                             "msg": str(c.get("msg") or "")[:220]} for c in blocking],
        "guard": {"checks": len(guard.get("checks", [])), "errors": len(blocking)},
        # result.compile 只抄被消费的键（打印 + manifest）；其余明细槽零读取，不抄。
        "compile": {k: cr.get(k) for k in
                    ("passed", "file_bytes",
                     "output_sha256", "output_path", "reused")},
        "fix_plan": build_fix_plan(guard, cr),
        "asset_workflow": facts.get("asset_workflow"),
        "next_action": ("fix: " + ", ".join(codes)) if codes else (
            "ready · 交付前用 --mode release 收口" if mode != "release" else "ready"),
        "performance": {**{k: facts.get(k) for k in
                           ("guard_ms", "qc_ms", "compile_ms", "attestation_ms",
                            "cache_reason", "cache_enabled")},
                        "speed_profile": facts.get("speed"),
                        "slides": len(spec.get("slides") or []),
                        "compile_reused": bool(cr.get("reused"))},
        "elapsed_ms": int((_time.time() - t0) * 1000),
    }
    return result


def fail_result(result: dict, problems: list, code: str = "GUARD_FAIL") -> dict:
    result.update(status="BLOCKED", passed=False, release_eligible=False)
    codes = result.setdefault("failure_codes", [])
    if code not in codes:
        codes.append(code)
    result["blocking_items"] = result.get("blocking_items", 0) + len(problems)
    result.setdefault("verdict", {}).update(verdict="BLOCKED", status="BLOCKED",
                                            blocking=result["blocking_items"], codes=codes)
    result.setdefault("fix_plan", {"policy": "", "groups": []})["groups"].append({
        "root_cause": code, "ids": [], "count": len(problems),
        "details": [{"id": None, "rule": code, "msg": str(p)[:220]} for p in problems],
        "fix": FIX_HINTS.get(code, "；".join(str(p) for p in problems))})
    result["next_action"] = "fix: " + "；".join(str(p) for p in problems[:3])
    return result


def preview_issues(ghost, page_ids: list) -> list:
    """预览证据自洽：声明页 = 渲染页 = 文件数，且每页都在当前稿件内。"""
    if not isinstance(ghost, dict):
        return []
    pages = ghost.get("pages") or []
    scope = str(ghost.get("scope") or "full")
    if scope == "key_pages":          # 关键页取证：渲染页数 = 职责标签数 = 文件数，且都在稿内
        expected = [str(x) for x in (ghost.get("slide_ids") or [])]
        labels = [str(x) for x in (ghost.get("key_pages") or {})]
        if (not expected or ghost.get("count") != len(expected)
                or len(pages) != len(expected) or len(labels) != len(expected)):
            return ["关键页取证的声明页与实际渲染页不一致"]
        outside = [x for x in expected if x not in {str(p) for p in page_ids}]
        if outside:
            return ["关键页取证引用了当前稿件之外的页面：" + "、".join(outside)]
    elif (ghost.get("slide_ids") != [str(p) for p in page_ids]
          or ghost.get("count") != len(page_ids) or len(pages) != len(page_ids)):
        return ["预览页没有完整覆盖当前稿件"]
    return []


def release_manifest(spec, qa_report: dict, *, ghost_preview=None,
                     workflow: dict | None = None, spec_hash: str | None = None,
                     output_verified: bool = False) -> dict:
    """发布清单：报告可追溯到当前 spec、产物字节与磁盘一致、预览页在稿内。

    output_verified=True：调用方同一轮已哈希过产物字节，信任传入值，跳过二次读盘。"""
    from datetime import datetime, timezone
    from primitives import file_digest

    spec = spec if isinstance(spec, dict) else {}
    qa_report = qa_report if isinstance(qa_report, dict) else {}
    spec_hash = spec_hash or spec_fingerprint(spec)
    issues: list = []
    notes: list = []
    slides = spec.get("slides") if isinstance(spec.get("slides"), list) else []
    page_ids = {str(s.get("id")) for s in slides if isinstance(s, dict) and s.get("id")}

    got = qa_report.get("source_spec_hash")
    if got and got != spec_hash:
        issues.append("qa_report 来自另一版 spec（source_spec_hash 不符）")
    ghost = ghost_preview if isinstance(ghost_preview, dict) else None
    if ghost:
        issues.extend(preview_issues(ghost, sorted(page_ids)))
        if ghost.get("count") and len(ghost.get("pages") or []) < len(slides):
            notes.append(f"预览覆盖 {ghost.get('count')}/{len(slides)} 页（关键页取证）")
    compile_claim = qa_report.get("compile") if isinstance(qa_report.get("compile"), dict) else {}
    output_path, output_sha = compile_claim.get("output_path"), compile_claim.get("output_sha256")
    if output_path or output_sha:
        if not output_path or not output_sha:
            issues.append("PPTX 凭证不完整：需要 output_path 与 output_sha256")
        elif output_verified:
            pass  # 同一轮 _compile_step 刚哈希过同一字节：信任传入值，不二次读盘
        else:
            try:
                if file_digest(output_path) != output_sha:
                    issues.append("PPTX output_sha256 与磁盘文件不一致")
            except (OSError, TypeError, ValueError):
                issues.append(f"PPTX 不可读取: {output_path}")
    if str(qa_report.get("status", "")).upper() == "PASS":
        if not qa_report.get("release_eligible"):
            issues.append("qa_report 声称 PASS 但 release_eligible=false")
        if str((qa_report.get("execution") or {}).get("mode", "")).lower() != "release":
            issues.append("qa_report 声称 PASS 但 execution.mode 不是 release")
        if not compile_claim.get("passed"):
            issues.append("qa_report 声称 PASS 但 compile.passed 不为 true")
    wf = workflow if isinstance(workflow, dict) else (qa_report.get("asset_workflow") or {})
    image_count = wf.get("image_count")
    if image_count is None:
        from assets import image_elements
        image_count = sum(1 for _ in image_elements(spec))
    if image_count and wf.get("status") != "PASS":
        issues.append("含图稿件缺少通过的资产链核验；编译 PASS 不能代替资产 PASS")
    status = "BLOCKED" if issues else str(qa_report.get("status", "BLOCKED"))
    return {
        "schema": "vao-release-manifest-v2",
        "source_spec_hash": spec_hash,
        "validation": {"issues": issues, "notes": notes, "page_count": len(page_ids)},
        "slide_count": len(slides),
        "release_eligible": bool(status == "PASS" and qa_report.get("release_eligible")),
        "asset_workflow": wf,
        "verification": {
            "visual_evidence": "ghost_preview" if ghost else "structural_only",
            "visual_evidence_scope": (ghost or {}).get("scope", "full") if ghost else None,
            "structural_pages": len(page_ids),
            "ghost_pages": (ghost or {}).get("count") if ghost else 0},
        "compile_report": compile_claim,
        "qa_summary": {k: qa_report.get(k) for k in
                       ("status", "passed", "failure_codes", "blocking_items",
                        "performance", "execution")},
        "ghost_preview": ({"dir": ghost.get("dir"),
                           "contact_sheet": ghost.get("contact_sheet")} if ghost else None),
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
