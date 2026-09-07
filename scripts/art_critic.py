#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structured, read-only art criticism for PPT specs (v2.0).

v2 评分模型（与 v1 的关键差异）：
  * 每个维度从基准分 3（「达到声明契约」）出发，凭**可观察证据**加/扣分
    （delta ∈ [-2, +2]，最终钳制到 0–5）。v1 只扣不加，满分被数学性封顶
    在 80/100，PASS(≥90) 永远不可达——v2 修复了该缺陷。
  * 每个 delta 都写入 dimension_evidence，评分可逐条溯源复核。
  * hard_gates 携带 production-contract.md 失败码表中的真实码
    （INTENT_UNCLEAR / FOCUS_COMPETING / CARD_WALL / MEDIA_UNJUSTIFIED /
    RHYTHM_FLAT / CRITIC_LOW），不再只报笼统的 CRITIC_LOW。

本模块依然是启发式：审美判断不能化简为像素分数。它只把可观察结构、
页面意图契约和可选渲染证据转成可追踪的批评。
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

from primitives import DEFAULT_WIDTH, DEFAULT_HEIGHT, contrast

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
CAPTION_ROLES = {"caption", "annotation", "source", "label", "axis",
                 "data_label", "legend", "metadata", "method"}
MEDIA_ROLES = {"hero", "emotion", "proof", "context"}
STATEMENT_SIZE = 40   # 超过该字号的文字视为 Statement 级记忆锚点
FOCUS_LEAD = 1.25     # 焦点文字需领先第二大文字的比例（否则视为同级竞争信号）
MEDIA_CHART_MAX = 2   # 每页媒体/图表对象上限（超过即竞争性视觉信号）
TEXT_MAX = 8          # 每页文本对象上限（超过即碎片化阅读）
ROUNDED_MAX = 4       # 圆角容器上限（超过即卡片墙风险）
LR_SPLIT_MAX = 0.45   # 左右墨迹面积失衡阈值（未声明非对称构图时）
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


def _grid_bias_stats(elems: list[dict]) -> tuple[int, int]:
    """8 单位网格对齐：返回 (完全对齐对象数, 总对象数)。"""
    ok = 0
    for e in elems:
        if e.get("type") not in ("text", "chart", "native_chart", "image", "shape"):
            continue
        vals = [_num(e, k) for k in ("x", "y", "width", "height")]
        if all(abs(v - 8 * round(v / 8)) <= 1 for v in vals):
            ok += 1
    return ok, max(1, len([e for e in elems if e.get("type") in
                           ("text", "chart", "native_chart", "image", "shape")]))


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
    for e in elems:
        if e.get("type") == "text" and _num(e, "size") >= STATEMENT_SIZE:
            kinds.append(f"statement 尺度({_num(e, 'size'):.0f}px)")
        if e.get("type") in ("chart", "native_chart"):
            kind = str(e.get("chart_kind") or e.get("kind", ""))
            if kind in ("kpi", "executive_kpi", "big_number"):
                kinds.append("big_number 数据锚点")
        if e.get("type") == "image":
            fn = e.get("asset_function") or (e.get("asset") or {}).get("function")
            if fn in ("hero", "emotion", "proof") or str(e.get("role", "")) in MEDIA_ROLES:
                kinds.append(f"图像锚点({fn or e.get('role')})")
    if _field(slide, "density") == "sparse" and _field(slide, "empty_space_role") in (
            "protect_focus", "hold_emotion"):
        kinds.append("主动留白")
    if not kinds:
        return None
    return " + ".join(kinds)


def _image_justified(e: dict) -> bool:
    if e.get("type") != "image":
        return True
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
                render_page: dict | None) -> tuple[dict, dict[str, list[str]],
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
    charts = [e for e in elems if e.get("type") in ("chart", "native_chart")]
    images = [e for e in elems if e.get("type") == "image"]
    rounded = [e for e in elems if e.get("type") == "shape"
               and e.get("shape") in {"rounded_rect", "round_rect"}]
    colors = _theme_colors(spec)
    direction = spec.get("direction") or {}
    composition = str(direction.get("composition_grammar", ""))
    asym_declared = composition in {"soft_asymmetry", "cinematic_stage", "path_sequence"}
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
        fsize = _num(focus_el, "size")
        other_sizes = sorted((_num(t, "size") for t in texts if t is not focus_el),
                             reverse=True)
        lead = fsize / other_sizes[0] if other_sizes and other_sizes[0] > 0 else None
        if fsize >= STATEMENT_SIZE and (lead is None or lead >= FOCUS_LEAD):
            r.add("visual_hierarchy", +1,
                  f"焦点「{focus}」拥有 Statement 级尺度优势（{fsize:.0f}px"
                  + (f"，领先第二大文字 {lead:.1f}×" if lead else "，且无同级文字") + "）。")
        elif lead is not None and lead < FOCUS_LEAD:
            r.add("visual_hierarchy", -1,
                  f"焦点文字 {fsize:.0f}px 仅领先第二大文字 {lead:.1f}×（<{FOCUS_LEAD}×），存在同级信号竞争。",
                  "拉开标题与正文的尺度比，或降级竞争性文字。")
        if len(charts) + len(images) <= 1 and len(texts) <= 4 \
                and (not render_page or float(render_page.get("accent_pixel_ratio", 0) or 0) <= 0.05):
            r.add("visual_hierarchy", +1, "媒体信号受控（≤1 个图表/图片），焦点无同级竞争者。")
        famp = _area(focus_el)
        for e in elems:
            if e is focus_el:
                continue
            if _area(e) > max(2.0 * famp, 0.25 * cw * ch):
                r.add("visual_hierarchy", -1,
                      f"元素「{e.get('id', '?')}」面积超过焦点的 2 倍，可能争夺第一注意点。",
                      "缩小或裁切该对象，或重新声明 focus。")
                break
    if len(charts) + len(images) > MEDIA_CHART_MAX:
        r.add("visual_hierarchy", -1, "媒体/图表对象超过两个，存在竞争性视觉信号。",
              "保留承担核心叙事的一个媒体或图表，其余改为注释、拆页或删除。")
        gates.append({"code": "FOCUS_COMPETING", "slide": slide.get("id", index + 1),
                      "severity": "REVISE",
                      "reason": f"媒体/图表对象 {len(charts) + len(images)} 个 > 上限 {MEDIA_CHART_MAX}。"})
    if len(texts) > TEXT_MAX:
        r.add("visual_hierarchy", -1, "文本对象较多，页面可能依赖碎片化阅读。",
              "合并重复语句，确保一个文本框只承担一个语义角色。")
    if render_page and float(render_page.get("accent_pixel_ratio", 0) or 0) > 0.08:
        r.add("visual_hierarchy", -1, "渲染强调色像素比例偏高，信号可能失去稀缺性。",
              "把 Accent 收束到一个关键数字、节点或下划线。")

    # ---------- 平衡（15） ----------
    if render_page:
        drift = float(render_page.get("gravity_drift", 0) or 0)
        if drift > 0.28:
            r.add("balance", -2, f"渲染显著性质心漂移 {drift:.2f}，与声明重心不一致。",
                  "调整主视觉尺寸/位置或重新声明 gravity_anchor；不要用装饰补偿。")
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
    ok_grid, total = _grid_bias_stats(elems)
    if total >= 3 and ok_grid == total:
        r.add("alignment", +1, f"全部 {total} 个内容对象落在 8 单位网格（偏差 ≤1px）。")
    elif total >= 3 and ok_grid < total - 1:
        r.add("alignment", -1, f"{total - ok_grid}/{total} 个内容对象偏离 8 单位网格超过 1px。",
              "将坐标/尺寸吸附到 8 的倍数。")
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
        if k_avg >= 4.0:
            r.add("alignment", +1,
                  f"渲染边缘投影峰度 {k_avg:.1f}（x={kx:.1f}, y={ky:.1f}），"
                  f"视觉对齐形成清晰轴线。")
        elif k_avg >= 1.5:
            r.add("alignment", 0, "")  # 中性：可记录但不写观察
        elif k_avg > 0:
            r.add("alignment", -1,
                  f"渲染边缘投影峰度 {k_avg:.1f}（x={kx:.1f}, y={ky:.1f}），"
                  f"视觉对齐松散，缺少统一装订线/基线。",
                  "把元素左缘/顶缘吸附到少数轴线；删除不影响阅读的次级元素。")

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
        r.add("contrast", -1, f"muted 对背景对比 {muted_bg:.1f}:1 < 1.8:1，刻度/注释将不可读。",
              "把 muted 加深至 ≥3:1。")
    accent_bg = _hex_contrast(colors, "accent", "background")
    # 主题化 Accent 预算：让 spec.theme.constraints.accent_max 真正进入
    # critic 评分（之前硬编码 0.05/0.08 会与主题"自我声明的克制"脱节）。
    theme_constraints = (spec.get("theme") or {}).get("constraints") or {}
    try:
        theme_accent_max = float(theme_constraints.get("accent_max", 0.05))
    except (TypeError, ValueError):
        theme_accent_max = 0.05
    accent_ratio = float(render_page.get("accent_pixel_ratio", 0) or 0) if render_page else None
    if accent_ratio is not None and accent_ratio <= theme_accent_max and (accent_bg is None or accent_bg >= 3):
        r.add("contrast", +1, f"强调色像素 {accent_ratio:.1%} ≤ 主题上限 {theme_accent_max:.0%}，Accent 保持稀缺性。")
    if accent_ratio is not None and accent_ratio > theme_accent_max + 0.03:
        r.add("contrast", -1, f"强调色像素 {accent_ratio:.1%} > 主题上限 {theme_accent_max:.0%}，强调信号被稀释。")
    if ink_bg is not None and ink_bg >= 7 and (muted_bg is None or muted_bg >= 3):
        r.add("contrast", +1,
              f"正文对比 {ink_bg:.1f}:1 且 muted ≥3:1，可读性层级健康。")

    # ---------- 节奏（10） ----------
    density = _field(slide, "density")
    energy = _field(slide, "energy")
    if previous:
        prev_intent = _intent(previous)
        prev_density = prev_intent.get("density") or previous.get("density")
        prev_energy = prev_intent.get("energy") or previous.get("energy")
        if density and density == prev_density:
            r.add("rhythm", -1, "与上一页密度相同，跨页节奏可能趋平。",
                  "在不破坏叙事的前提下降低或提高空间密度，形成呼吸变化。")
        if density and prev_density and density != prev_density \
                and energy and prev_energy and energy != prev_energy:
            r.add("rhythm", +1, f"密度 {prev_density}→{density} 且能量 {prev_energy}→{energy}，节奏变化明确。")
        if density == prev_density and energy == prev_energy and energy:
            r.add("rhythm", -1, f"密度与能量均与上一页相同（{density}/{energy}）。",
                  "至少让密度或能量之一随叙事阶段变化。")
    # 声明 vs 渲染对照：仅当有真实渲染证据时启用。
    # design-intelligence.md 「留白节奏三型」：sparse ≈ 0.30 / balanced ≈ 0.55
    # / dense ≈ 0.75。声明 intent 与渲染 occupancy 偏离超过 ±0.20 视为节奏
    # 未执行（声明 sparse + 渲染 0.70 = 节奏虚挂；声明 dense + 渲染 0.30 =
    # 节奏空载）。这是 art_critic 节奏维度从「仅看声明值」升级为「声明 vs
    # 渲染对照」的关键补丁——9 维度反馈闭环由此一致。
    if render_page and "occupancy" in render_page:
        try:
            occ = float(render_page.get("occupancy") or 0)
        except (TypeError, ValueError):
            occ = None
        if occ is not None and density in ("sparse", "balanced", "dense"):
            target = {"sparse": 0.30, "balanced": 0.55, "dense": 0.75}[density]
            if abs(occ - target) > 0.20:
                if occ > target:
                    r.add("rhythm", -1,
                          f"声明 density={density} 但渲染占用 {occ:.0%}，"
                          f"偏离目标 {target:.0%} 达 +{occ - target:.0%}，"
                          f"页面比声明的更拥挤。",
                          "用留白、缩字或拆页降低占用；或把 density 上调一档。")
                else:
                    r.add("rhythm", -1,
                          f"声明 density={density} 但渲染占用 {occ:.0%}，"
                          f"偏离目标 {target:.0%} 达 {occ - target:.0%}，节奏空挂。",
                          f"补一个次级对象或图表，让占用接近 {target:.0%}。")

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
        r.add("professional_quality", -1, f"检测到 {len(rounded)} 个圆角容器，存在卡片墙或网页 UI 化风险。",
              "将容器改为空间分组、发丝线或字体层级；仅保留数据/KPI/特殊强调所需面板。")
        gates.append({"code": "CARD_WALL", "slide": slide.get("id", index + 1),
                      "severity": "REVISE",
                      "reason": f"圆角容器 {len(rounded)} 个 > 上限 {ROUNDED_MAX}。"})
    if len(charts) + len(images) > MEDIA_CHART_MAX:
        r.add("professional_quality", -1, "媒体/图表对象超过两个，页面信号密度过高。")
    if len(texts) > TEXT_MAX:
        r.add("professional_quality", -1, "文本对象较多，页面可能依赖碎片化阅读。")
    unjustified = [i for i in images if not _image_justified(i)]
    if unjustified:
        r.add("professional_quality", -1,
              f"{len(unjustified)} 张图片未声明资产功能（asset_function/role），媒体缺乏存在理由。",
              "声明图片的 context/emotion/proof/hero 功能，或删除无法说明功能的图片。")
        gates.append({"code": "MEDIA_UNJUSTIFIED", "slide": slide.get("id", index + 1),
                      "severity": "REVISE",
                      "reason": f"{len(unjustified)} 张图片未声明 asset_function / 媒体角色。"})
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
    flat_streak = 0
    flat_prev: tuple | None = None
    for i, slide in enumerate(slides):
        rp = render_pages[i] if i < len(render_pages) else None
        scores, evidence, observations, fixes, gates = _score_page(
            spec, slide, i, slides[i - 1] if i else None, rp)
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
        # RHYTHM_FLAT：连续 ≥3 页密度与能量完全重复
        stamp = (_field(slide, "density"), _field(slide, "energy"))
        if stamp == flat_prev and stamp != (None, None):
            flat_streak += 1
        else:
            flat_streak = 1
        flat_prev = stamp
        if flat_streak >= 3:
            hard_gates.append({"code": "RHYTHM_FLAT", "slide": slide.get("id", i + 1),
                               "severity": "REVISE",
                               "reason": f"连续 {flat_streak} 页密度/能量重复（{stamp[0]}/{stamp[1]}）。"})
        reports.append({"slide": slide.get("id", i + 1), "scores": scores,
                        "score": round(weighted, 1), "observations": observations,
                        "minimal_fixes": fixes,
                        "dimension_evidence": evidence,
                        "recheck": ["Guard", "Compile", "Render Evidence", "QA"]})
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
    deck_notes = {
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
    return {
        "critic_version": "2.0",
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
