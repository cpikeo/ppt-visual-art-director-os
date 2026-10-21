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

from primitives import (CHAR_SPACING_MAX_PT,
                        CHART_KINDS, CHART_LABEL_MIN_COUNT, CHART_LABEL_MIN_H,
                        CHART_LIMITS, ELEMENT_VALUE_KINDS, NUMERIC_CHART_KINDS,
                        ROWS_CHART_KINDS, DEFAULT_HEIGHT, DEFAULT_WIDTH, ELEMENT_TYPES,
                        SLIDE_MAX_PX, SLIDE_MIN_PX, emu,
                        is_background_declared, spec_fingerprint, resolve_chart_highlight)

# 图表分类全部派生自 primitives.CHART_SPEC（单一权威）；本层只保留 Guard 的
# 呈现名，不再各写一份集合——分类漂移由 selftest 的 chart_spec 断言拦截。
SUPPORTED_CHART_KINDS = CHART_KINDS
# 行级渲染键（primitives.chart_rows 与各图形分支实际读取的键）；其余键即未消费字段。
ROW_RENDERED_KEYS = frozenset({"label", "value", "display", "desc", "subtotal", "is_total", "total", "max"})
ELEMENT_METRIC_KINDS = ELEMENT_VALUE_KINDS
RULE_SHAPES = frozenset({"line", "arrow"})
_COLOR_ROLE_FIELDS = ("color", "fill", "stroke", "border_color", "track_color",
                      "label_color", "background")


# ── 元素字段表（同源推导，不手抄）─────────────────────────────────────────
_CONSUMED_FIELDS_CACHE: set | None = None


# 经**动态键**读取的字段（`for field in ("source","unit",…)` + `e.get(field)`），
# 正则扫不到名字，只能显式列出；除此之外一律由源码推导，不手抄第二份表。
_DYNAMIC_FIELDS = frozenset({
    "source", "unit", "period", "basis", "metric",            # 图表出处硬门
    "color", "fill", "stroke", "border_color", "track_color",  # _COLOR_ROLE_FIELDS
    "label_color", "background", "accent", "fill_color",
})


def consumed_fields() -> frozenset:
    """渲染/校验链**实际读取**的元素字段名，从同目录模块源码扫出来。

    契约为「未消费字段会静默丢弃，所以必拦」，但把 300 多个字段手抄一份清单
    必然与渲染器漂移（多写一个字段 → 作者被误拦；少写一个 → 静默丢弃复活）。
    这里在首次调用时扫一遍 compiler / ghost / verify / primitives / assets 的
    `.get("x")` 与 `["x"]`，得到"渲染器真的会读的名字"集合；读不到文件时返回
    空集（该项检查自动跳过，绝不假拦）。扫描只做一次，缓存复用。
    """
    global _CONSUMED_FIELDS_CACHE
    if _CONSUMED_FIELDS_CACHE is not None:
        return frozenset(_CONSUMED_FIELDS_CACHE)
    import re as _re
    from pathlib import Path as _Path
    found: set = set()
    try:
        here = _Path(__file__).resolve().parent
        for name in ("compiler.py", "ghost.py", "verify.py", "primitives.py", "assets.py"):
            src = (here / name).read_text(encoding="utf-8")
            found |= set(_re.findall(r'\.get\(\s*["\'](\w+)["\']', src))
            found |= set(_re.findall(r'\[\s*["\'](\w+)["\']\s*\]', src))
    except OSError:
        found = set()
    _CONSUMED_FIELDS_CACHE = {k for k in found if k.isidentifier()} | set(_DYNAMIC_FIELDS)
    return frozenset(_CONSUMED_FIELDS_CACHE)


def _closest_fields(name: str, known: frozenset) -> list[str] | None:
    """近似字段名：拼写 / 下划线 / 词序写错时，给出作者可能想写的名字（至多两个）。

    给列表而不是单个名字：`font_size` 的候选是 `size` 与 `fonts`，`align_left` 的
    候选是 `align` 与 `left`——两条都合理时替作者拍板只会拍错。

    只认强信号，按强度取最优（不是第一个命中）：
      1 归一化后完全相等（maxlines ↔ max_lines）
      2 一个是另一个的复合词（align_left ↔ align、bold_weight ↔ bold）
      3 一方是另一方的词尾（font_size ↔ size、spacing ↔ char_spacing）
      4 字符相似度 ≥0.86（colour ↔ color）
    其余未知字段不当拼写错误——「没有这个功能」和「名字写错」要给两种诊断。
    内部键（下划线开头）不作为建议对象：那是实现细节，不是作者该写的名字。
    """
    import difflib
    flat = name.replace("_", "").lower()
    # 复合写法 `modifier_head`（text_size / char_spacing / space_before）里，作者
    # 想要的是**词头**那个字段：`font_size` 应指向 `size`，不是同名的 `fonts` 容器。
    head = name.split("_")[-1].lower()
    head_hit = [c for c in known if c == head and not c.startswith("_")]
    scored: list[tuple[float, str]] = []
    for cand in known:
        if cand.startswith("_"):
            continue
        cflat = cand.replace("_", "").lower()
        if not cflat:
            continue
        if cflat == flat:
            return [cand]
        score = 0.0
        if (flat.startswith(cflat) or cflat.startswith(flat)) and min(len(flat), len(cflat)) >= 3:
            score = 0.90 + 0.4 * len(cflat) / max(len(flat), len(cflat))
        elif (flat.endswith(cflat) or cflat.endswith(flat)) and min(len(flat), len(cflat)) >= 4:
            score = 0.88 + 0.4 * len(cflat) / max(len(flat), len(cflat))
        else:
            # 纯相似度分支才按长度接近度打折：复合词（bold_weight ↔ bold）是强信号，
            # 不该因为长短差被压到阈值以下；拼写错误（colour ↔ color）则越等长越可信。
            score = difflib.SequenceMatcher(None, flat, cflat).ratio() \
                - 0.04 * abs(len(cflat) - len(flat))
        if score >= 0.86:
            scored.append((score, cand))
    scored.sort(key=lambda t: (-t[0], t[1]))
    picks = [cand for _, cand in scored if cand not in head_hit][:max(0, 2 - len(head_hit))]
    return (head_hit + picks) or None


def _text_box_capacity(e: dict) -> dict | None:
    """文本是否装得下：物理容量只在这里判断，错误字段不许静默放行。

    字距（char_spacing）以 pt 声明，段距由 compiler.pt(px) 写入；
    段前/段后只计相邻段间一次，末段的 space_after 不占可见文字高度。
    字体真实换行仍须在目标 Office 里验收。
    """
    try:
        size = float(e.get("size", 18))
        h = float(e.get("height", 0) or 0)
        w = float(e.get("width", 0) or 0)
        pad = float(e.get("padding", 0) or 0)
        lh = float(e.get("line_height", 1.35))
        spacing = float(e.get("char_spacing", 0) or 0)
        before = float(e.get("space_before", 0) or 0)
        after = float(e.get("space_after", 0) or 0)
    except (TypeError, ValueError, OverflowError):
        return {"invalid": "字号/内边距/行距/字距/段距必须是有限数字"}
    if not all(map(math.isfinite, (size, h, w, pad, lh, spacing, before, after))):
        return {"invalid": "字号/内边距/行距/字距/段距不得为 NaN 或无穷大"}
    if size <= 0 or pad < 0 or lh <= 0 or before < 0 or after < 0:
        return {"invalid": "字号和行高必须为正，内边距与段距不能为负"}
    declared_max = e.get("max_lines")
    if declared_max is not None and (isinstance(declared_max, bool)
                                     or not isinstance(declared_max, int)
                                     or declared_max < 1):
        return {"invalid": "max_lines 必须是正整数"}
    if h <= 0 or w <= 0:
        return None  # 盒子本身由 element_schema 的退化几何门拦截
    from primitives import estimate_lines, insert_script_gaps, text_width
    wrap = e.get("wrap", True) is not False
    usable_w = w - 2 * pad
    if usable_w <= 0:
        return {"invalid": "内边距占满文字框，可用宽度 ≤ 0"}
    paragraphs = str(e.get("text", "")).split("\n")
    lines = sum(estimate_lines(insert_script_gaps(p), usable_w, size, wrap, spacing)
                for p in paragraphs)
    width_need = max((text_width(insert_script_gaps(p), size, spacing)
                      for p in paragraphs), default=0)
    # space_before/after 与字号/盒子同为 spec px（compiler.pt(px) 才转 pt）。
    paragraph_gap = max(0, len(paragraphs) - 1) * (before + after)
    need = lines * size * lh + paragraph_gap
    usable_h = h - 2 * pad
    over_max = declared_max is not None and lines > declared_max
    return {"lines": lines, "need": need, "usable": usable_h, "size": size,
            "line_height": lh, "max_lines": declared_max,
            "paragraph_gap": paragraph_gap,
            # 行长（可读域）：中文一字约等于一个字号宽。取「栏宽能排多少字」与
            # 「内容实际排了多少字」的较小值——短标签放在宽框里并没有 88 字/行，
            # 真正要拦的是**排满时**一行超过 45 字。
            "measure_cjk": (min(usable_w, width_need) / size) if size else 0.0,
            "over_height": need > usable_h + 1, "over_max_lines": bool(over_max),
            "over_width": not wrap and width_need > usable_w + 2, "width_need": width_need}


def _coord(value):
    """坐标读数：bool 不是坐标。

    与 `_finite` / `_positive_num` / `_alpha_ok` / `_dim` 同口径——那几处早已把
    bool 当 schema 错误（`float(True) == 1.0` 是静默的 1 px，不是作者意图）。
    这里此前漏了同一道门：`x: True` → 1 px 能一路通过 guard、编译与发布，
    而 canvas.width: True 会被 `_positive_num` 拒——同一份稿件两套标准。
    """
    if isinstance(value, bool):
        raise ValueError("bool 不是坐标")
    return float(value)


def _element_rect(e: dict):
    try:
        x, y = _coord(e.get("x", 0)), _coord(e.get("y", 0))
        w, h = _coord(e.get("width", 0)), _coord(e.get("height", 0))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (x, y, w, h)):
        return None
    return x, y, w, h


def _is_rule_shape(e: dict) -> bool:
    return str(e.get("type")) == "shape" and str(e.get("shape") or "") in RULE_SHAPES


def _box(e: dict, text_ink_ratio: float = 1.0, text_ink_v: float = 1.0):
    """元素的有效墨迹盒：文本框不等于墨迹（按系数收窄）。bool 同 `_coord` 拒绝。

    文本的**纵向**跨度按字号/行数/行距/垂直锚点算（`primitives.ink_span`），
    不再用「框高 × 缩系数」：底部对齐的大字号数字，墨迹其实贴在框底并向上
    展开，旧模型让它停在框内，实际会压穿下方一行说明。锚点与行距是作者
    写下的排版决定，guard 必须按同一语义判碰撞。
    """
    x, y, w, h = _coord(e.get("x", 0)), _coord(e.get("y", 0)), \
        _coord(e.get("width", 0)), _coord(e.get("height", 0))
    if str(e.get("type")) == "text":
        w *= text_ink_ratio
        cap = _text_box_capacity(e)
        if cap and not cap.get("invalid"):
            from primitives import ink_span, text_ink_height
            ink_h = text_ink_height(cap["lines"], cap["size"], cap["line_height"],
                                    cap["paragraph_gap"])
            pad = float(e.get("padding", 0) or 0)
            top, bottom = ink_span(y, h, pad, ink_h, e.get("anchor", "top"))
            return x, top, w, max(0.0, bottom - top)
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
    for key in ("width", "height"):
        if key in canvas and not _positive_num(canvas[key]):
            add("canvas_schema", "canvas", "error", f"canvas.{key} 必须是正的有限数字")
        elif key in canvas and not (SLIDE_MIN_PX <= float(canvas[key]) <= SLIDE_MAX_PX):
            # 编译期由 python-pptx 抛裸范围错误（实测 canvas 5377 → “value must be in
            # range(914400, 51206400)”）；阻断口径一致，但诊断必须是可修的。
            add("canvas_schema", "canvas", "error",
                f"canvas.{key}={float(canvas[key]):g}px 超出 PowerPoint 可表达的 1–56 英寸"
                f"（{SLIDE_MIN_PX:g}–{SLIDE_MAX_PX:g}px，96dpi）；整稿等比缩放后再交付")
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
    seen_slide_ids = set()
    for si, slide in enumerate(slides):
        if not isinstance(slide, dict):
            add("slide_schema", "slides", "error", "每个 slide 必须是对象/dict")
            continue
        sid = str(slide.get("id", f"slide_{si}"))
        if not sid.strip() or sid in seen_slide_ids:
            add("slide_schema", sid, "error", "页面 id 必须非空且全稿唯一（资产与预览凭证按 id 绑定）")
        seen_slide_ids.add(sid)
        if "elements" in slide and not isinstance(slide.get("elements"), list):
            add("slide_schema", sid, "error", "slide.elements 必须是数组/list")
        raw_elements = slide.get("elements")
        raw_elements = raw_elements if isinstance(raw_elements, list) else []
        for ei, element in enumerate(raw_elements):
            if not isinstance(element, dict):
                add("element_schema", f"{sid}[{ei}]", "error", "elements 每项必须是对象/dict，不得静默丢弃")
        drawable = [e for e in raw_elements if isinstance(e, dict)]
        if not drawable and not slide.get("background"):
            add("page_contract", sid, "error",
                "这一页没有任何元素，也没有 background：画面上什么都没有"
                "（要么给元素，要么给背景）")
        bg = slide.get("background")
        if isinstance(bg, dict) and isinstance(bg.get("color"), (dict, list, tuple)):
            add("element_schema", sid, "error",
                "slide.background.color 须为 #HEX 字符串或 theme token")
        seen_element_ids = set()
        for e in drawable:
            eid = str(e.get("id", ""))
            if not eid.strip() or eid in seen_element_ids:
                add("element_schema", sid, "error", "元素 id 必须非空且页内唯一（修复与焦点按 id 绑定）")
            seen_element_ids.add(eid)
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


def _alpha_ok(v) -> bool:
    """opacity 是否可安全写入 a:alpha（0–1 有限数；bool 视为 schema 错误）。"""
    if isinstance(v, bool):
        return False
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f) and 0.0 <= f <= 1.0


def _angle_ok(v) -> bool:
    """渐变 angle 是否为 ±360 内的有限数（越界会写出非法 OOXML ang）。"""
    if isinstance(v, bool):
        return False
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f) and abs(f) <= 360.0


def _check_element(e: dict, sid: str, si: int, add, known_tokens, cw: float,
                   ch: float, *, require_provenance: bool = False) -> None:
    # 定位符带上页面 id：「focus」在全稿多页重复，修复包必须能指到具体哪一页。
    # 约定 `页面:元素`，修复包的 affected_slides 按此前缀归页。
    eid = f"{sid}:{e.get('id', f'[{si}]')}"
    # 未消费字段：作者写错的字段名会被渲染器静默丢弃（`font_size` 写了但标题还是
    # 默认字号，全部硬门照样 PASS）。契约把这一类列为必拦，判据分两档：
    #   近似已有字段（拼写/下划线/复合）→ error，并给出候选名（可修诊断）
    #   完全对不上的未知字段 → warn（可能是作者自己的注解，不该假拦）
    known = consumed_fields()
    if known:
        for key in sorted(set(e) - known):
            near = _closest_fields(key, known)
            if near:
                add("element_field_unknown", eid, "error",
                    f"字段 {key!r} 不被渲染器消费，疑似写错（可能是 {' / '.join(near)}）；"
                    "写错的字段会被静默丢弃，产物里看不到任何效果")
            else:
                add("element_field_unknown", eid, "warn",
                    f"字段 {key!r} 不被渲染器消费（会静默忽略）；"
                    "如需自定义注解请移出 elements，否则请对照 references/contract.md 的字段表")
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
        elif e["text"] is None:
            add("TEXT_FIELD_INVALID", eid, "error",
                "text 为 null；编译会得到字面 'None' 上屏——请写结论文字，或删掉该元素")
        elif "content" in e:
            add("TEXT_FIELD_INVALID", eid, "error",
                "text 元素使用了未消费字段 'content'，请改用顶层字段 'text'")
        if "style" in e:
            add("TEXT_STYLE_INVALID", eid, "error",
                "text 元素使用了未消费的嵌套字段 'style'；size/color/bold/line_height 放顶层")
    if isinstance(e.get("text"), bool):
        add("TEXT_FIELD_INVALID", eid, "error",
            f"text 收到布尔值 {e['text']!r}（YAML 把 yes/no/on/off/true/false 解析成 bool）；"
            "编译会得到字面 'True'/'False'——请写成带引号的字符串")

    # 透明度与渐变角是纯数值通道：越界值要么写出非法 OOXML（a:alpha 值域 0–100000、
    # a:lin/@ang 是 int32，PowerPoint 打开即进修复流程），要么被静默丢弃（>1 的
    # opacity 编译为完全不透明）。guard 在编译前拒绝并给出诊断。
    for key in ("opacity", "fill_opacity", "stroke_opacity", "text_opacity"):
        val = e.get(key)
        if val is not None and not _alpha_ok(val):
            add("element_schema", eid, "error",
                f"{key} 须为 0–1 的有限数，收到 {val!r}"
                "（负值会写出非法 a:alpha，>1 会被静默丢弃）")
    # 字距同理：char_spacing 以 pt 声明（contract §排版），写入 `a:rPr/@spc`
    # 的 1/100 pt 值。@spc 是 ST_TextPoint（±4000pt），越界是非法 OOXML。
    # 正常字距在 ±20pt 之内，这条线只拦「数量级写错」的输入。
    spacing_pt = e.get("char_spacing")
    if spacing_pt is not None and not isinstance(spacing_pt, bool):
        try:
            spacing_val = float(spacing_pt)
        except (TypeError, ValueError):
            add("element_schema", eid, "error",
                f"char_spacing 须为有限数字（pt），收到 {spacing_pt!r}")
        else:
            if math.isfinite(spacing_val) and abs(spacing_val) > CHAR_SPACING_MAX_PT:
                add("element_schema", eid, "error",
                    f"char_spacing={spacing_val:g}pt 超出 DrawingML 可表达范围 "
                    f"±{CHAR_SPACING_MAX_PT:g}pt（a:rPr/@spc 是 ST_TextPoint，"
                    "越界会写出非法 OOXML）；字距用 ±1–5pt 就够，请改回合理值")

    if isinstance(fill, dict):
        fop = fill.get("opacity")
        if fop is not None and not _alpha_ok(fop):
            add("element_schema", eid, "error",
                f"fill.opacity 须为 0–1 的有限数，收到 {fop!r}")
        if str(fill.get("type", "")).lower() == "gradient":
            ang = fill.get("angle")
            if ang is not None and not _angle_ok(ang):
                add("element_schema", eid, "error",
                    f"渐变 angle 须为 ±360 内的有限数，收到 {ang!r}"
                    "（越界值会写出非法 OOXML ang）")
            # 契约的填充四写法要求 stops≥2；只有一个 stop 的「渐变」不是渐变，
            # 编译器会抛 COMPILE_FAIL。同一判定在 guard 提前给出可修诊断：
            # 作者看到的是「补第二个 stop」，而不是一句编译异常。
            stops = fill.get("stops")
            if not isinstance(stops, list) or len(stops) < 2:
                add("element_schema", eid, "error",
                    f"渐变 stops 须为数组且至少 2 个（收到 {stops!r}）；"
                    "单一 stop 不是渐变，请补第二个 stop 或改用 {type: solid}")
            for s_i, stop in enumerate(fill.get("stops") or []):
                if isinstance(stop, dict):
                    sop = stop.get("opacity", stop.get("alpha"))
                elif isinstance(stop, (list, tuple)) and len(stop) > 2:
                    sop = stop[2]
                else:
                    sop = None
                if sop is not None and not _alpha_ok(sop):
                    add("element_schema", eid, "error",
                        f"渐变 stop[{s_i}] 透明度须为 0–1 的有限数，收到 {sop!r}")

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
            # 退化判据按**落盘量度**：EMU 是最小可表达单位，`emu(1e-9) == 0`——写进
            # pptx 与 width=0 完全相同，但 px 层 `> 0` 会让它溜过旧判据。实测
            # `width: 5e-5` 的文本框落在产物里是 0 EMU 宽，却一路 release PASS。
            qw, qh = emu(fw), emu(fh)
            if _is_rule_shape(e):
                if qw <= 0 and qh <= 0:      # 一维对象：线允许 height=0
                    add("element_schema", eid, "error",
                        "geometry 退化（线的 width 与 height 同时为 0 → 零长度不可见）"
                        f"；落盘 {qw}×{qh} EMU")
            elif qw <= 0 or qh <= 0:
                add("element_schema", eid, "error",
                    f"geometry 退化（width={fw:g}, height={fh:g} → 落盘 {qw}×{qh} EMU，"
                    "小于 1 EMU 的元素在产物里不可见）")
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
        if cap and cap.get("invalid"):
            add("text_capacity", eid, "error", cap["invalid"])
        elif cap and cap["over_height"]:
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
        # 行长是**可读域**问题，不是容量问题：装得下不等于读得下去。
        # 中文一行超过 45 字，投影/远距离回扫会丢行；分栏或收窄栏宽，不要缩字号。
        if (cap and not cap.get("invalid") and e.get("wrap", True) is not False
                and float(te.get("size", 18) or 18) <= 22
                and cap.get("measure_cjk", 0) > 45):
            add("text_measure", eid, "warn",
                f"[{sid}] 行长 {cap['measure_cjk']:.0f} 汉字/行 超出可读域 22–45"
                f"（字号 {cap['size']:g} × 可用栏宽 {cap['measure_cjk'] * cap['size']:.0f}px）："
                "分栏、收窄栏宽或拆成两条，不要缩字号")

    if typ == "image":
        from primitives import image_crop
        try:
            image_crop(e.get("crop"))
            if e.get("fit", "cover") not in ("cover", "contain"):
                raise ValueError("fit 只接受 cover|contain")
        except ValueError as exc:
            add("element_schema", eid, "error", str(exc))

    if typ in ("chart", "native_chart"):
        _check_chart(e, eid, add, require_provenance=require_provenance)


def _check_chart(e: dict, eid: str, add, *, require_provenance: bool) -> None:
    """图表：类型白名单 → 载荷 → 数据完整性 → 标签空间 → 出处。"""
    kind = str(e.get("chart_kind") or e.get("kind", ""))
    if kind not in SUPPORTED_CHART_KINDS:
        add("chart_type", eid, "error",
            f"未知 chart_kind={kind!r}；合法值：{sorted(SUPPORTED_CHART_KINDS)}")
        return
    from primitives import CHART_SPEC
    has_series = e.get("series") is not None
    if has_series:
        if CHART_SPEC[kind]["renderer"] != "native":
            add("chart_payload", eid, "error", f"{kind} 只消费 data/元素级载荷，不支持 categories + series；不得静默丢弃序列")
            return
        if "data" in e:
            add("chart_payload", eid, "error", "data 与 categories + series 是替代载荷，不能同时声明并静默隐藏一份")
            return
        if (not isinstance(e.get("categories"), list) or not e["categories"]
                or not isinstance(e.get("series"), list) or not e["series"]
                or any(not isinstance(sr, dict) for sr in e["series"])):
            add("chart_payload", eid, "error", "多序列载荷必须有非空 categories 列表和 series 对象列表")
            return
    data = e.get("data", [])
    if not isinstance(data, list):
        add("chart_payload", eid, "error", "data 必须为数组/list")
        return
    if kind in ROWS_CHART_KINDS and not has_series:
        for di, row in enumerate(data):
            if (not isinstance(row, dict) or row.get("label") is None
                    or not str(row["label"]).strip()):
                add("chart_payload", f"{eid}[{di}]", "error",
                    "每个 data 行须为对象并含非空 label；不得静默丢行或把 null 当文字")
    if kind in ELEMENT_METRIC_KINDS and (e.get("value") is None or not str(e["value"]).strip()):
        add("chart_payload", eid, "error",
            f"{kind} 缺少元素级 value（大数字没有数字）")
    if kind == "matrix":
        points = e.get("points")
        if not (isinstance(points, list) and points):
            add("chart_payload", eid, "error", "matrix 缺少 points[{x,y,label}]；无点不绘图")
        else:
            # 契约硬门「非有限值」同样管 matrix 的 x/y：缺 x/y 时编译器只会抛裸
            # KeyError（COMPILE_FAIL 报错看不出哪里写错），guard 给出可修的诊断。
            for pi, p0 in enumerate(points):
                if not isinstance(p0, dict) or not _finite(p0.get("x")) or not _finite(p0.get("y")):
                    add("chart_payload", eid, "error",
                        f"matrix 点 [{pi}] 的 x/y 必须是有限数字（points[{{x,y,label}}]）")
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

    # 未消费字段门（审计：release 硬门放行了图表行上的 unit 等字段，渲染器静默丢弃）。
    # 行级只允许渲染器真正读取的键；作者想表达的单位/期间/口径放在元素级。
    if isinstance(data, list) and kind not in ("matrix", "architecture"):
        for di, row in enumerate(data):
            if isinstance(row, dict):
                extra = sorted(k for k in row if k not in ROW_RENDERED_KEYS)
                if extra:
                    add("chart_field_unconsumed", f"{eid}[{di}]", "error",
                        f"图表行字段 {extra} 不会被渲染（行级只消费 {sorted(ROW_RENDERED_KEYS)}）；"
                        "单位/期间/口径请写在图表元素级，否则是静默丢失")
    if "unit" in e and kind not in NUMERIC_CHART_KINDS:
        add("chart_field_unconsumed", eid, "warn",
            f"{kind} 不渲染元素级 unit；单位需写进数据 display 或删除，避免作者以为已显示")
    # 同类「写了不生效」：目标线只由 ranked_bar 画。作者在别的 kind 上写 target，
    # 会以为画上了参考线——实测 progress_bar + target 产物里一根线都没有。
    if kind != "ranked_bar" and (e.get("target") is not None or e.get("target_label")):
        add("chart_field_unconsumed", eid, "warn",
            f"{kind} 不渲染 target/target_label（只有 ranked_bar 会画目标线）；"
            "要么换用 ranked_bar，要么把目标写进数据 display 或正文，避免误以为已呈现")

    series = e.get("series")
    multi = isinstance(series, list) and bool(series) and isinstance(series[0], dict)
    categories = e.get("categories") or []
    n_cat = len(categories) if isinstance(categories, list) else 0
    n_series = len(series) if multi else 0
    # 这些形状图的实现只消费前 N 项；超量须拆页，不允许静默丢掉尾部证据。
    # 上限只在 primitives.CHART_SPEC 定义一次，编译/预览的截断与此同源。
    payload = e.get("points") if kind == "matrix" else e.get("layers") if kind == "architecture" else data
    if kind in CHART_LIMITS and isinstance(payload, list) and len(payload) > CHART_LIMITS[kind]:
        add("chart_payload", eid, "error",
            f"{kind} 有 {len(payload)} 项，当前实现最多完整呈现 {CHART_LIMITS[kind]} 项；拆图/拆页，不得截掉尾项")
    if multi:
        if any(c is None or not str(c).strip() for c in categories):
            add("data_integrity", eid, "error", "categories 中的类别名不得为空")
        if n_series > 1:
            names = [str(sr.get("name") or "").strip() if isinstance(sr, dict) else "" for sr in series]
            if not all(names) or len(set(names)) != len(names):
                add("data_integrity", eid, "error", "多序列必须声明非空且不重复的 name，以辨认数据归属")
    if kind in NUMERIC_CHART_KINDS:
        if multi:
            if not n_cat:
                add("data_integrity", eid, "error", "多序列图表缺少 categories")
            if kind == "pie" and n_series > 1:
                add("data_integrity", eid, "error", "pie 只能表达一个构成序列；多序列请拆图，不能隐藏其他系列")
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
                    elif kind in {"pie", "donut", "donut_composition"} and float(v) < 0:
                        add("data_integrity", f"{eid}[s{sidx}][{vi}]", "error",
                            f"{kind} 不接受负值构成；请改用可表达正负关系的图表")
                if kind in {"pie", "donut", "donut_composition"} and all(_finite(v) for v in vals):
                    if sum(max(0, float(v)) for v in vals) <= 0:
                        add("data_integrity", f"{eid}[s{sidx}]", "error", "构成序列的有效数值总和必须大于 0")
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
                elif kind in {"ranked_bar", "progress_bar", "stacked_bar", "bubble",
                                      "pie", "donut", "donut_composition"} \
                        and float(row["value"]) < 0:
                    add("data_integrity", f"{eid}[{di}]", "error",
                        f"{kind} 不接受负值；请改用可表达正负关系的图表")
            if kind == "progress_bar" and not _positive_num(e.get("max", 100)):
                add("data_integrity", eid, "error", "progress_bar 的 max 必须是正数")
            if kind == "progress_bar":
                for di, row in enumerate(data):
                    if isinstance(row, dict) and "max" in row \
                            and not _positive_num(row.get("max")):
                        add("data_integrity", f"{eid}[{di}]", "error",
                            "progress_bar 行级 max 必须是正数；它决定这一行的刻度，"
                            "写错会被渲染层静默回落到 100")
            # 目标线（`target`/`target_label`）只有 ranked_bar 渲染：竖直参考线表达
            # 「门槛/要到哪」。它是被消费的字段，非数字会让线**静默消失**——声明了
            # 就必须画得出来；其余 kind 不消费它，写在那里等于没写，得留痕。
            if kind == "ranked_bar" and e.get("target") is not None \
                    and not _finite(e.get("target")):
                add("data_integrity", eid, "error",
                    f"ranked_bar 的 target={e.get('target')!r} 不是有限数字；"
                    "目标线是「门槛/要到哪」的参考线，非数字会静默消失——请写成数值或删掉")
    if not multi and kind in ("donut", "donut_composition", "pie") and isinstance(data, list):
        total = 0.0
        for row in data:
            if isinstance(row, dict) and _finite(row.get("value")):
                total += max(float(row["value"]), 0)
        if total <= 0:
            add("data_integrity", eid, "error", "构成图的有效数值总和必须大于 0")

    if "highlight" in e:
        # 与 compiler/ghost 同一口径（primitives.resolve_chart_highlight）：序列名 →
        # 序列级；类别名 → 点级；整数按序列数/类别数分派。校验必须跟着实现走，
        # 否则「写错的强调」要么被静默吞掉、要么被误报。
        # 命名空间随载荷形态走：multi 用 categories + series 名；data 载荷的行标签
        # 就是唯一命名空间（与 resolve_chart_highlight 的整数分派一致）。
        names = ([str(sr.get("name", "")) for sr in series if isinstance(sr, dict)]
                 if multi else [])
        if multi:
            cats = [str(c) for c in categories] if isinstance(categories, list) else []
        else:
            cats = [str(r.get("label", "")) for r in data if isinstance(r, dict)]
        hi = e.get("highlight")
        si, pi = resolve_chart_highlight(e, cats, names)
        if si < 0 and pi < 0:
            upper = max(len(cats), len(names))
            shown = f"0–{upper - 1}" if upper else "数据范围"
            add("chart_highlight", eid, "warn",
                f"highlight={hi!r} 既不是索引也不匹配任何类别名/序列名（可用范围 {shown}），会被忽略")

    # 标签空间：标签是独立可见对象，空间不足不允许渲染器硬塞（不缩字号）
    n = n_cat * n_series if multi else (len(data) if isinstance(data, list) else 0)
    show_values = e.get("show_values", kind in ("comparison_bar", "bar", "column", "donut"))
    # 单位可见性：不是阻断项（作者的构图决定），但必须留痕。release 出处硬门要求
    # 数值图表声明 unit，而数值标签关闭时这一声明不会出现在图上——此前编译器把
    # 它升级成编译失败，于是「门要 unit」与「编译器拒绝不可见的 unit」互相打架，
    # 作者只有强制打开数值标签一条路，且修复包只报 COMPILE_FAIL 说不出冲突。
    # 现在：guard 出可执行告警（进发布清单 notes），作者自行选择标签或来源行承载单位。
    if (kind in NUMERIC_CHART_KINDS and isinstance(e.get("unit"), str)
            and e["unit"].strip() and not show_values):
        add("chart_unit_invisible", eid, "warn",
            f"{kind} 声明了 unit=「{e['unit'].strip()}」但数值标签关闭："
            "单位不会出现在图上；要显示请 show_values: true，"
            "否则请确认来源/正文行已写明单位")
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
# 明细是给人看的样例，计数才是权威：24 条足够说明「归一化动了什么」，
# 再多的重复条目只增加清单体积。超出部分不隐藏——changes_omitted 记账。
_REPORT_ITEM_CAP = 24


def _snap_pos(value: float, grid: int) -> int:
    return int(round(value / grid)) * grid


def _on_grid(value: float, grid: int) -> bool:
    """是否已落在网格线上（浮点容差：中心常常是 x.5）。"""
    return abs(value / grid - round(value / grid)) < 1e-9


def _snap_size(value: float, grid: int) -> float:
    """尺寸落网格——但**亚网格厚度按原值保留**。

    为什么不再 `max(grid, ...)`（v6.5 修）：发丝线的厚度是作者的设计决定。
    把 1px 的线强行抬到 4px 是 4× 的视觉重量改变，而且没有任何提示——
    「归一化」越权改了排版，不是在对齐节奏。小于一个网格的尺寸一律原样透传；
    `0` 也原样透传：它可能是 LINE / ARROW 的合法零厚度轴；其他退化尺寸原样留给 guard 拦截。
    """
    if value < grid:
        # 0 是 LINE / ARROW 的合法零厚度轴；负尺寸与零面积则原样留给 guard 拦截。
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
      · LINE / ARROW 的零厚度轴 → 保留 0，只吸附轴坐标；竖线不会被扩成有宽度的斜线。
    幂等：第二趟输入的中心已在网格上，吸附是恒等变换。
    """
    size_n = _snap_size(size, grid)
    # 尺寸被改写时，保住中心——「把 6px 圆整到 8px」不该顺带把对象挪走。
    # 亚网格厚度（发丝线）同样走中心口径：它的上边缘没有对齐意义，中线才有。
    if size_n != size or 0 < size_n < grid:
        center = _snap_pos(pos + size / 2.0, grid)
        return center - size_n / 2.0, size_n
    if _on_grid(pos, grid):
        return pos, size_n
    # 边不在网格上、中心却在网格上：这是上一趟按中心吸附留下的几何（同心优先）。
    # 再按边吸附会挪走 ≤grid/2，把「归一化幂等」打破——而幂等是编译、预览与复验
    # 共用同一份几何的前提（随机 400 例实测：旧写法 307 例二次归一漂移，单次不动
    # 看不出来，但一旦有第二个消费者重新归一，对象就与 guard 认证的位置差 2px）。
    if _on_grid(pos + size_n / 2.0, grid):
        return pos, size_n
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
    """几何落 8/4 单位、颜色/字体名规范化。单趟机械变换：对已规范输入是恒等。

    报告只留**计数 + 有上限的样例**：`counts` 是权威数字，`changes` 是给人看的样本。
    逐条明细在二十页以上的稿子里能涨到上万字节，而它没有任何消费者（发布清单、
    修复包与骨架都只读 counts/规范化后的 spec）；此前超过 200 条还会**静默**
    截断——读者无从知道明细不全。现在把「一共多少条、省了多少条」写清楚。
    """
    import copy
    report = {"changes": [], "counts": {}, "changes_total": 0, "changes_omitted": 0}
    out = copy.deepcopy(spec) if isinstance(spec, dict) else {}
    theme = out.get("theme") or {}
    colors_map = theme.get("colors") if isinstance(theme.get("colors"), dict) else {}
    tokens = {str(k): str(v) for k, v in colors_map.items()} if colors else {}

    def record(scope, eid, field, old, new, rule):
        report["counts"][rule] = report["counts"].get(rule, 0) + 1
        report["changes_total"] += 1
        if len(report["changes"]) < _REPORT_ITEM_CAP:
            report["changes"].append({"scope": scope, "id": eid, "field": field,
                                      "from": old, "to": new, "rule": rule})
        else:
            report["changes_omitted"] += 1

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
                    # `_snap_size` 保留零厚度轴；`_snap_span` 只吸附其位置，
                    # 因而横线与竖线完全对称，线长仍按中心归一。
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
    "CHART_TYPE_FAIL": "图表类型在白名单内且数据形态匹配（占比≠趋势）；载荷不可为空、字段类型合法"
                       "（matrix 的点须为有限 x/y）。",
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
        # 可读域这类不阻断的缺陷（行长）不进对话（验证层约定），但必须留痕：
        # 发布清单把抄进 notes，一次发布验收就能看见，不必等到人工审片。
        "guard_warnings": [{"rule": c.get("rule"), "id": str(c.get("id") or ""),
                            "msg": str(c.get("msg") or "")[:220]}
                           for c in guard.get("checks", [])
                           if c.get("level") == "warn"][:8],
        # result.compile 只抄被消费的键（打印 + manifest）；其余明细槽零读取，不抄。
        "compile": {k: cr.get(k) for k in
                    ("passed", "file_bytes",
                     "output_sha256", "output_path", "reused")},
        "fix_plan": build_fix_plan(guard, cr),
        "asset_workflow": facts.get("asset_workflow"),
        "next_action": ("fix: " + ", ".join(codes)) if codes else (
            "ready · 交付前用 --mode release 收口" if mode != "release" else "ready"),
        "performance": {**{k: facts.get(k) for k in
                           ("load_spec_ms", "module_import_ms", "spec_identity_ms",
                            "asset_bind_ms", "qc_ms", "asset_chain_ms", "asset_count",
                            "asset_retry_count", "normalization_ms", "guard_ms",
                            "verdict_ms", "cache_probe_ms", "compile_ms",
                            "attestation_ms", "cache_write_ms", "cache_reason",
                            "cache_enabled")},
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
    if not isinstance(ghost, dict) or not ghost:
        return ["发布缺少结构预览证据；补跑 check，不得以 deadline 跳过发布取证"]
    pages = ghost.get("pages") or []
    expected = ghost.get("slide_ids") or []
    scope = ghost.get("scope")
    if (not isinstance(pages, list) or not isinstance(expected, list)
            or not expected or ghost.get("count") != len(expected)
            or len(pages) != len(expected)
            or len(set(map(str, expected))) != len(expected)
            or len(set(map(str, pages))) != len(pages)):
        return ["预览声明页、唯一文件与实际渲染页数不一致"]
    from pathlib import Path
    try:
        files = [*pages, ghost.get("contact_sheet")]
        if any(not p or not Path(p).is_file() or Path(p).stat().st_size == 0 for p in files):
            return ["结构预览页图或联络表缺失/为空；须重新取证"]
    except (OSError, TypeError, ValueError):
        return ["结构预览文件路径无效或不可读取"]
    if scope == "full":
        if expected != page_ids:
            return ["预览页没有按叙事顺序完整覆盖当前稿件"]
    elif scope in ("key_pages", "explicit_subset"):
        if any(x not in page_ids for x in expected):
            return ["预览取证引用了当前稿件之外的页面"]
        if scope == "key_pages" and set(ghost.get("key_pages") or {}) != set(expected):
            return ["关键页职责标签与取证页面不一致"]
    else:
        return ["未知预览覆盖范围"]
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
    page_ids = [str(s.get("id")) for s in slides if isinstance(s, dict)]

    got = qa_report.get("source_spec_hash")
    if got != spec_hash:
        issues.append("qa_report 来自另一版 spec（source_spec_hash 不符）")
    ghost = ghost_preview if isinstance(ghost_preview, dict) else None
    if qa_report.get("status") == "PASS" or ghost:
        issues.extend(preview_issues(ghost, page_ids))
        if ghost and ghost.get("count") and len(ghost.get("pages") or []) < len(slides):
            notes.append(f"预览覆盖 {ghost.get('count')}/{len(slides)} 页（关键页取证）")
    compile_claim = qa_report.get("compile") if isinstance(qa_report.get("compile"), dict) else {}
    output_path, output_sha = compile_claim.get("output_path"), compile_claim.get("output_sha256")
    if ghost and (not output_sha or ghost.get("output_sha256") != output_sha):
        issues.append("结构预览不属于当前 PPTX 字节（output_sha256 缺失或不符）")
    if output_path or output_sha or qa_report.get("status") == "PASS":
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
        if (qa_report.get("performance") or {}).get("speed_profile") == "strict" and ghost and ghost.get("scope") != "full":
            issues.append("strict 发布必须逐页取证，不能使用抽样预览")
        if not compile_claim.get("passed"):
            issues.append("qa_report 声称 PASS 但 compile.passed 不为 true")
    # 非阻断告警是证据：只进发布清单的 notes，不进对话、不改判定。
    # 标签按领域标注——行长（可读域）与单位可见性不是一回事，统一写 [可读域] 会把
    # 「unit 声明了却没显示」说成排版问题，作者按提示找不到真正该动的地方。
    for w in (qa_report.get("guard_warnings") or [])[:8]:
        label = {"text_measure": "可读域",
                 "chart_unit_invisible": "单位可见性"}.get(str(w.get("rule")), "非阻断")
        notes.append(f"[{label}] {w.get('msg')}")
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
            "ghost_pages": (ghost or {}).get("count") if ghost else 0,
            "target_powerpoint": "not_verified",
            "native_editing": "not_verified",
            "independent_visual_review": "not_performed"},
        # 双重结论：结构预览结论与目标软件结论分开写，不把结构通过读成视觉通过。
        "conclusions": [
            f"{'PASS' if status == 'PASS' else status} — "
            f"{'Structural Preview' if ghost else 'Structural Check'}",
            "NOT VERIFIED — Target PowerPoint"],
        "compile_report": compile_claim,
        "qa_summary": {k: qa_report.get(k) for k in
                       ("status", "passed", "failure_codes", "blocking_items",
                        "performance", "execution")},
        "ghost_preview": ({k: ghost.get(k) for k in
                           ("dir", "contact_sheet", "pages", "slide_ids", "count", "scope",
                            "key_pages", "pages_rendered", "file_witnesses",
                            "renderer", "output_sha256", "evidence_scope")} if ghost else None),
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
