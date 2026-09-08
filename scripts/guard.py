# -*- coding: utf-8 -*-
"""
Layer 0.5 · Guard（静态治理层）

职责：把 SKILL.md 与 references/production-contract.md 的硬约束**自动化断言**——
网格、安全区、元素重叠、图表容量、Accent 面积、跨页节奏。
本层是只读的：不修改 spec、不生成任何元素，
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


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x2E80 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF
            or 0xFF00 <= o <= 0xFF60 or 0x3000 <= o <= 0x303F)


# 行长上限来自 art_critic（与审美评分同一口径）；独立运行时用文档化默认值。
_LINE_MEASURE_FALLBACK = {"LINE_MEASURE_CJK_MAX": 38, "LINE_MEASURE_LATIN_MAX": 75,
                          "LINE_MEASURE_FAIL_FACTOR": 2.0}
MEASURE_EXEMPT_ROLES = frozenset({"source", "method", "metadata", "caption", "legend",
                                  "axis", "data_label", "annotation", "page_number"})


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
    focus = field("focus") or slide.get("focus_subject_id")
    if focus:
        ids = [e.get("id") for e in slide.get("elements", []) if isinstance(e, dict)]
        if focus not in ids:
            add("focus", sid, "warn", f"focus={focus!r} 未对应页面元素")
    elif slide.get("elements"):
        add("focus", sid, "hint", "未声明 focus；无法验证唯一视觉主锚点")


# ══════════════════════════════════════════════════════════════
# Preflight（静态预检）：把 Art Critic 中**确定性的**结构判据前移到静态治理层
#
# 目的：让「焦点尺度、文本/媒体预算、重心失衡、卡片墙、节奏趋平」这些问题
# 在编译与渲染之前就被点名，避免用 3–6 轮渲染去试出同一件事。
# 阈值一律延迟读取 art_critic 的常量（单一口径）；art_critic 不在时回落到
# 文档化默认值，并在报告里标注 gate_source。预检条目为 hint 级：不改变
# guard/QA 的通过判定，只提供可执行的最小修正。
# ══════════════════════════════════════════════════════════════

_PREFLIGHT_DEFAULTS = {
    "STATEMENT_SIZE": 40, "FOCUS_LEAD": 1.25, "MEDIA_BUDGET_MAX": 1,
    "TEXT_BUDGET_MAX": 4, "FOCUS_AREA_LEAD": 2.0, "ROUNDED_MAX": 4,
    "LR_SPLIT_MAX": 0.45,
    "AXIS_TOLERANCE": 0.045, "AXIS_LINES": (0.25, 1 / 3, 0.5, 2 / 3, 0.75),
    "GOLDEN_LINES": (0.382, 0.618),
    "ASYMMETRIC_GRAMMARS": {"soft_asymmetry", "cinematic_stage", "path_sequence"},
    "CAPTION_ROLES": {"caption", "annotation", "source", "label", "axis",
                      "data_label", "legend", "metadata", "method"},
}


def _preflight_gates() -> tuple[dict, str]:
    """从 art_critic 读取真实评分阈值，保证预检与评分同源；失败时回落默认值。"""
    gates = dict(_PREFLIGHT_DEFAULTS)
    try:
        import art_critic as ac
        for k in ("STATEMENT_SIZE", "FOCUS_LEAD", "MEDIA_BUDGET_MAX", "TEXT_BUDGET_MAX",
                  "FOCUS_AREA_LEAD", "ROUNDED_MAX", "LR_SPLIT_MAX", "ASYMMETRIC_GRAMMARS",
                  "CAPTION_ROLES", "AXIS_TOLERANCE", "AXIS_LINES", "GOLDEN_LINES"):
            v = getattr(ac, k, None)
            if v is not None:
                gates[k] = v
        return gates, "art_critic"
    except Exception:
        return gates, "defaults"


def _is_bg_layer(e: dict) -> bool:
    """是否**声明**为背景层（只读意图，不判断资格）。"""
    return (str(e.get("layer", "")).lower() in {"background", "backdrop"}
            or str(e.get("role", "")).lower() in {"background", "backdrop"})


# 声明 layer=background 即可免检，等于给任何内容图发一张免死金牌；资格判定要求它
# 真的「承载空间」并给出阅读保护。阈值取自 art_critic（单一口径），不可用时回落。
_BG_FALLBACK = {"BG_MIN_COVERAGE": 0.60, "BG_MIN_PROTECT_OPACITY": 0.20}


_GATE_CACHE: dict = {}
_BG_GATE_CACHE: dict = {}


def _cached_gate(key: str, defaults: dict) -> dict:
    """懒解析 + 缓存 art_critic 阈值；按 key 分桶，互不污染。"""
    if key not in _GATE_CACHE:
        th = dict(defaults)
        try:
            import art_critic as ac
            for k in th:
                v = getattr(ac, k, None)
                if v is not None:
                    th[k] = v
        except Exception:
            pass
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
    try:
        area = float(e.get("width", 0) or 0) * float(e.get("height", 0) or 0)
    except (TypeError, ValueError):
        area = 0.0
    cover = area / max(1.0, float(cw) * float(ch))
    if cover < th["BG_MIN_COVERAGE"]:
        return False, (f"仅覆盖画布 {cover:.0%}（<{th['BG_MIN_COVERAGE']:.0%}）："
                       f"这是内容对象，不是空间层")
    if e.get("readability_exempt"):
        return True, None
    ov = e.get("overlay")
    if ov is None:
        cp = e.get("content_protection")
        if isinstance(cp, dict):
            ov = cp.get("overlay") or cp.get("scrim")
    if ov is None:
        return False, "未声明 overlay/content_protection：叠加文字的可读性无保障"
    try:
        op = 1.0 if (isinstance(ov, str) and ov) else float(
            (ov or {}).get("opacity", 1.0)) if isinstance(ov, dict) else None
    except (TypeError, ValueError, AttributeError):
        op = None
    if op is None:
        return False, "overlay 无法解析出 opacity"
    if op < th["BG_MIN_PROTECT_OPACITY"]:
        return False, (f"遮罩不透明度 {op:.2f} < {th['BG_MIN_PROTECT_OPACITY']:.2f}，"
                       f"形同虚设")
    return True, None


def _bg_exempt(e: dict, cw: float, ch: float) -> bool:
    """是否享受背景层豁免（声明 + 资格通过）。"""
    return _bg_qualified(e, cw, ch)[0]


def _ink_box(e: dict) -> tuple[float, float, float, float]:
    x, y = float(e.get("x", 0)), float(e.get("y", 0))
    w, h = max(0.0, float(e.get("width", 0))), max(0.0, float(e.get("height", 0)))
    if e.get("type") == "text":
        w, h = w * 0.55, h * 0.70
    return x, y, w, h


def run_preflight(spec: dict, cw: float, ch: float, add) -> list[dict]:
    """返回结构化预检项：{slide, code, observation, minimal_fix}。"""
    gates, gate_source = _preflight_gates()
    direction = spec.get("direction") or {}
    slides = spec.get("slides") or []
    items: list[dict] = []

    def flag(sid, code, observation, fix):
        rec = {"slide": sid, "code": code, "observation": observation, "minimal_fix": fix}
        items.append(rec)
        add("preflight", f"{sid}:{code}", "hint", f"{observation} → {fix}")

    for si, s in enumerate(slides):
        sid = s.get("id", f"slide_{si}")
        elems = [e for e in s.get("elements", []) if isinstance(e, dict)]
        intent = s.get("page_intent") if isinstance(s.get("page_intent"), dict) else {}

        def field(key):
            return intent.get(key) or s.get(key)

        texts = [e for e in elems if e.get("type") == "text"]
        reading = [t for t in texts if str(t.get("role", "")) not in gates["CAPTION_ROLES"]]
        media = [e for e in elems
                 if e.get("type") in ("chart", "native_chart", "image")
                 and not _bg_exempt(e, cw, ch)]

        insight = field("insight")
        if not (isinstance(insight, str) and insight.strip()):
            flag(sid, "INTENT_UNCLEAR", "页面没有可复述的单一 insight（Art Critic 会 BLOCKED）",
                 "先写一句 object + change + implication，再排版")

        focus_id = field("focus")
        focus_el = next((e for e in elems if e.get("id") == focus_id), None)
        if focus_el is None:
            flag(sid, "FOCUS_UNBOUND", f"focus={focus_id!r} 未对应页面元素",
                 "把 focus 指向真实元素 id；唯一 L4 通常是结论文字")
        else:
            fsize = float(focus_el.get("size") or 0)
            others = sorted((float(t.get("size") or 0) for t in texts if t is not focus_el),
                            reverse=True)
            if focus_el.get("type") == "text":
                if fsize < gates["STATEMENT_SIZE"]:
                    flag(sid, "FOCUS_SCALE",
                         f"焦点 {fsize:g}px 低于 Statement 线 {gates['STATEMENT_SIZE']}px，"
                         f"拿不到层级与记忆点加分",
                         "把结论提为 Statement 尺度（或把结论直接写进标题而非依赖图表）")
                elif others and others[0] > 0 and fsize / others[0] < gates["FOCUS_LEAD"]:
                    flag(sid, "FOCUS_LEAD",
                         f"焦点仅领先第二大文字 {fsize / others[0]:.2f}×"
                         f"（<{gates['FOCUS_LEAD']}×），存在同级竞争",
                         "拉开尺度比或降级竞争性文字")
                fare = _element_area(focus_el)
                big = [e for e in elems if e is not focus_el
                       and not _bg_exempt(e, cw, ch)
                       and _element_area(e) > max(gates["FOCUS_AREA_LEAD"] * fare,
                                                  0.25 * cw * ch)]
                if big:
                    flag(sid, "FOCUS_DOMINATED",
                         f"「{big[0].get('id')}」面积 > 焦点 {gates['FOCUS_AREA_LEAD']}×，可能夺走第一注意点",
                         "裁切/缩小该对象，或把焦点声明改给它（保持唯一）")
            # 落位是否「对齐过」：中心离最近轴线差一点 → 更像没想过，而不是刻意的非对称。
            # 对文字/图表/图片焦点一视同仁；只在完全不上线时提示，且不判罚——非对称构图
            # 本来就是合法语法，「哪儿都不靠」才是没决定的排版余数。
            try:
                _ax = _axis_offsets(focus_el, cw, ch, gates)
            except Exception:
                _ax = None
            if _ax and not _ax[0]:
                flag(sid, "FOCUS_PLACEMENT",
                     f"焦点中心 x={_ax[1][0]:.3f} y={_ax[1][1]:.3f} 距最近版面轴线 "
                     f"{_ax[2]:.3f}（> 容差 {gates['AXIS_TOLERANCE']:.3f}）",
                     "把焦点中心对齐到中线/三分线/黄金分割线之一，"
                     "或在 page_intent 写明这处偏移换来什么（留白/张力/呼应）")
        if len(media) > gates["MEDIA_BUDGET_MAX"]:
            flag(sid, "MEDIA_BUDGET",
                  f"争夺注意力的媒体/图表 {len(media)} 个 > 预算 {gates['MEDIA_BUDGET_MAX']}",
                  "保留承担核心关系的一个，其余改注释或拆页")
        if len(reading) > gates["TEXT_BUDGET_MAX"]:
            flag(sid, "TEXT_BUDGET", f"阅读文本 {len(reading)} 个 > 预算 {gates['TEXT_BUDGET_MAX']}",
                 "合并重复语句：一个文本框只承担一个语义角色")
        lm_limits = _measure_limits()
        for e in texts:
            lm = line_measure(e, lm_limits)
            if lm and lm["over"]:
                flag(sid, "LINE_MEASURE",
                     f"「{e.get('id', '?')}」每行约 {lm['per_line']:.0f} 字 > "
                     f"{lm['limit']}（{'CJK' if lm['cjk_led'] else '拉丁'}行长上限）",
                     "拆成两行/短句，或把宽度收到 "
                     f"{int(lm['limit'] * (float(e.get('size') or 0)))}px 以内")
        rounded = [e for e in elems if e.get("shape") in {"rounded_rect", "round_rect"}]
        if len(rounded) > gates["ROUNDED_MAX"]:
            flag(sid, "CARD_WALL", f"{len(rounded)} 个圆角容器（CARD_WALL 硬门槛）",
                 "删容器，改用发丝线 + 留白 + 字阶分组")
        # 整幅背景层：文字可直接叠加，但必须声明内容保护（否则可读性无保障）；
        # 资格不足的「伪背景」不再免检，并作为 error 点名（它会吃回媒体预算与遮挡检查）
        for e in elems:
            if e.get("type") == "image" and _is_bg_layer(e):
                ok, why = _bg_qualified(e, cw, ch)
                if not ok:
                    add("preflight", f"{sid}:BACKGROUND_DISGUISED", "error",
                        f"「{e.get('id', '?')}」声明 layer=background 但不具备空间层资格：{why} "
                        f"→ 改回普通媒体（计入预算与遮挡），或真的整幅承载并叠加遮罩")
                    items.append({"slide": sid, "code": "BACKGROUND_DISGUISED",
                                  "observation": f"内容对象伪装成背景层：{why}",
                                  "minimal_fix": "撤掉 layer=background 标签，或扩大覆盖并声明"
                                                 " overlay（opacity ≥0.20）/content_protection"})
                elif not (e.get("content_protection") or e.get("overlay")):
                    add("preflight", f"{sid}:BG_UNPROTECTED", "warn",
                        "整幅背景图未声明 content_protection/overlay：文字叠加后对比不可控 "
                        "→ 为画心叠加低能量遮罩（solid #000000, opacity 0.35）或改用分幅画心")
                    items.append({"slide": sid, "code": "BG_UNPROTECTED",
                                  "observation": "背景层未声明内容保护",
                                  "minimal_fix": "为叠加文字的画心声明 overlay/content_protection"})
        # 左右墨迹失衡 vs 构图语法声明
        left = right = 0.0
        for e in elems:
            if e.get("type") not in ("text", "chart", "native_chart", "image"):
                continue
            bx, by, bw, bh = _ink_box(e)
            mass = bw * bh
            if (bx + bw / 2) < cw / 2:
                left += mass
            else:
                right += mass
        total = left + right
        if total > 0:
            split = abs(left - right) / total
            light_heavy = (1.0 - split) / (1.0 + split) if split < 1 else 0.0
            grammar = str(direction.get("composition_grammar", ""))
            if (split > gates["LR_SPLIT_MAX"] and light_heavy > 0.15
                    and grammar not in gates["ASYMMETRIC_GRAMMARS"]):
                flag(sid, "ASYM_UNDECLARED",
                     f"左右墨迹失衡 {split:.0%} 但 composition_grammar={grammar!r}",
                     "回填轻侧，或在 direction 声明非对称语法（soft_asymmetry 等）")
        # 疏密曲线：声明密度需要与相邻页不同（否则 rhythm 扣分）
        if si:
            prev = slides[si - 1]
            pi = prev.get("page_intent") if isinstance(prev.get("page_intent"), dict) else {}
            pd = pi.get("density") or prev.get("density")
            pe = pi.get("energy") or prev.get("energy")
            if field("density") and field("density") == pd:
                flag(sid, "DENSITY_FLAT",
                     f"与 {prev.get('id', 's%02d' % (si - 1))} 同为 density={pd}",
                     "让相邻页疏密互斥（sparse↔balanced↔dense），或改用不同的重心")

    # 连续三页同密度同能量 = RHYTHM_FLAT 硬门槛
    streak, prev_stamp = 1, None
    for si, s in enumerate(slides):
        intent = s.get("page_intent") if isinstance(s.get("page_intent"), dict) else {}
        stamp = (intent.get("density") or s.get("density"),
                 intent.get("energy") or s.get("energy"))
        if stamp == prev_stamp and all(stamp):
            streak += 1
        else:
            streak = 1
        prev_stamp = stamp
        if streak == 3:
            flag(s.get("id", f"slide_{si}"), "RHYTHM_FLAT",
                 f"连续 3 页 density/energy 相同 {stamp}（Art Critic 硬门槛）",
                 "改动其中一页的密度或能量，恢复呼吸曲线")

    for it in items:
        it["gate_source"] = gate_source
    return items



# ══════════════════════════════════════════════════════════════
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


def _axis_offsets(el: dict, cw: float, ch: float, gates: dict):
    """(是否上线, (cx, cy), 最小轴距)：焦点中心与版面轴线的关系。

    中线 / 三分线 / 1/4 线 / 黄金分割线共用一份常量表（由 art_critic 提供，
    guard 预检与 critic 评分同一口径），任一轴对上即算「落位有意图」。
    """
    lines = tuple(gates.get("AXIS_LINES") or ()) + tuple(gates.get("GOLDEN_LINES") or ())
    if not lines:
        return None
    try:
        cx = (float(el.get("x") or 0) + float(el.get("width") or 0) / 2) / max(cw, 1)
        cy = (float(el.get("y") or 0) + float(el.get("height") or 0) / 2) / max(ch, 1)
    except (TypeError, ValueError):
        return None
    tol = float(gates.get("AXIS_TOLERANCE", 0.045))
    best = min(min(abs(v - a) for a in lines) for v in (cx, cy))
    return (best <= tol, (cx, cy), best)


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

    行长（typography）不走 rules：阈值与审美同源，读自 art_critic 的
    LINE_MEASURE_CJK_MAX / LINE_MEASURE_LATIN_MAX / LINE_MEASURE_FAIL_FACTOR，
    并用 MEASURE_EXEMPT_ROLES 豁免注记级角色；超限记 warn，超上限 2× 记 error。

    returns: {
      "passed": bool, "checks": [...], "warnings": [...], "score": int,
      "grid": {checked, aligned, adherence}, "line_measure": {checked, over, worst, worst_id}
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
    hue_families_max = int(rules.get("hue_families_max", 4))
    accent_hue_min = float(rules.get("accent_hue_min", 12))
    chart_label_scale_tol = float(rules.get("chart_label_scale_tol", 1.25))
    # §07 排版预算（hint 级软约束：提示层级过碎，不扣硬分）
    font_levels_max = int(rules.get("font_levels_max",
                                    constraints.get("font_levels_max", 4)))
    font_families_max = int(rules.get("font_families_max",
                                      constraints.get("font_families_max", 2)))
    # 可读性底线：注释/来源/标签类文字的最小字号（设计单位 px）
    min_font_size = float(rules.get("min_font_size", 10))
    focus_scale = bool(rules.get("focus_scale", True))

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
    lm_limits = _measure_limits()
    grid_stats = {"checked": 0, "aligned": 0}
    measure_stats = {"checked": 0, "over": 0, "worst": 0.0, "worst_id": None}
    accent_area = 0.0
    deck_hues: set[int] = set()
    chart_styles: dict[str, dict] = {}
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
                # 可读性底线：注释/来源/标签类文字不得低于最小字号（渲染后可读性复核）
                if role in {"caption", "annotation", "source", "label", "axis",
                            "data_label", "legend", "metadata", "method"}:
                    try:
                        if e.get("size") is not None and float(e["size"]) < min_font_size:
                            add("min_font", eid, "warn",
                                f"{role} 文字 {float(e['size']):g}px < 可读下限 "
                                f"{min_font_size:g}px；提高字号或改由更高层级角色承担")
                    except (TypeError, ValueError):
                        pass
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
                    add("typography", eid, "error",
                        f"每行约 {lm['per_line']:.0f} 字 > 上限 {lm['limit']} 的 "
                        f"{lm_limits['LINE_MEASURE_FAIL_FACTOR']:.1f}×"
                        f"（{'CJK' if lm['cjk_led'] else '拉丁'}行长失控，眼跳回失准 → 拆句或加宽盒）")
                elif lm["over"]:
                    measure_stats["over"] += 1
                    add("typography", eid, "warn",
                        f"每行约 {lm['per_line']:.0f} 字 > {lm['limit']}"
                        f"（编辑式排版建议 ≤{lm['limit']}），行尾扫读吃力")

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
                    if _inside_zone(e, source_zone):
                        add("source_zone", e.get("id", "?"), "error",
                            "主体对象侵入 source_zone；来源区必须独立保留")
                except (TypeError, ValueError):
                    pass
            if e.get("type") not in ("text", "chart", "native_chart", "image"):
                continue
            if _bg_exempt(e, cw, ch):
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

        # 焦点尺度：声明焦点为文字时，应获得页内最大字号（OS「一页一焦点」）
        if focus_scale:
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
    # 声明密度（设计意图）与结构密度（元素构成）分别比对：两者都重复才是
    # 真正的节奏趋平；仅结构重复但声明有变化时提示「渲染后复核真实留白」。
    if check_rhythm and len(slides) > 1:
        prev_struct = prev_declared = None
        for si, s in enumerate(slides):
            intent = s.get("page_intent") if isinstance(s.get("page_intent"), dict) else {}
            declared = intent.get("density") or s.get("density")
            cur, _ = _density_class(s)
            if prev_struct is not None:
                if cur == prev_struct and declared == prev_declared:
                    add("rhythm", s.get("id", f"slide_{si}"), "hint",
                        f"连续页面同为 {cur} 密度（OS §12，可拆页/留白调整）")
                elif cur == prev_struct and declared != prev_declared:
                    add("rhythm", s.get("id", f"slide_{si}"), "hint",
                        f"声明密度 {prev_declared}→{declared} 但结构密度未变（同为 {cur}），"
                        f"渲染后复核真实留白是否支撑节奏声明")
            prev_struct, prev_declared = cur, declared

    # ---- Preflight：与 Art Critic 同口径的静态预检（hint 级，不改变通过判定） ----
    preflight_items: list[dict] = []
    if bool(rules.get("preflight", True)):
        try:
            preflight_items = run_preflight(spec, cw, ch, add)
        except Exception as exc:                      # 预检永远不能阻断生产链
            preflight_items = []
            warnings.append(f"[preflight] skipped: {exc}")

    score = max(0, 100 - sum(
        4 if c["level"] == "error" else (2 if c["level"] == "warn" else 0)
        for c in checks))
    return {
        "passed": not any(c["level"] == "error" for c in checks),
        "checks": checks,
        "warnings": warnings,
        "score": score,
        # 可报告的对齐/行长事实：比率本身不扣分（新提示族不得计分），供人复核
        "grid": {**grid_stats,
                 "adherence": (round(grid_stats["aligned"] / grid_stats["checked"], 3)
                               if grid_stats["checked"] else None)},
        "line_measure": dict(measure_stats),
        # 预检：与 Art Critic 同口径的结构判据（渲染前给出，不计入 guard 分数）
        "preflight": preflight_items,
        "preflight_codes": sorted({i["code"] for i in preflight_items}),
    }


# --------------------------------------------------------------------------
# 可选 CLI： python guard.py build_mydeck.py
# --------------------------------------------------------------------------
def main(argv):
    import importlib.util
    from pathlib import Path
    if len(argv) < 2:
        print("usage: python guard.py <build_module.py> [--json] [--preflight]")
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
        print(f"score={result['score']} passed={result['passed']} "
              f"preflight={len(result.get('preflight') or [])}")
        if "--preflight" in argv:
            for i in result.get("preflight") or []:
                print(f"  {i['slide']:>6} {i['code']:17s} {i['observation']}")
                print(f"          fix → {i['minimal_fix']}")
            return 0 if result["passed"] else 2
        for c in result["checks"]:
            if c["level"] != "hint":
                print(f"  [{c['level']:5s}] {c['rule']:14s} {c['msg']}")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
