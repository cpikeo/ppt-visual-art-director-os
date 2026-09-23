# -*- coding: utf-8 -*-
"""verify.py · 验证层：硬错误 Guard → PASS/BLOCK 判定 → 发布清单

QA 只回答一个问题：这份 PPTX 能不能交付？
  * 只拦截生产级硬错误：schema/内容契约缺失、文字溢出、越界、墨迹重叠、
    图表载荷非法、数据诚信（单位口径打架、来源缺失升档）、资产链断裂、编译失败。
  * 作者写下数字约束（theme.constraints / rules）才执法；包不发明审美数字。
  * 非阻断证据只聚合留痕（trace），不构成门槛、不进对话——Evidence ≠ Error。
  * 生产输出只有 PASS / BLOCK；修复包按根因分组并内嵌 error 明细，一次修完。
  * 不重新设计 PPT、不打审美分、不产生修复循环。

合并自 guard（静态硬约束）与 qa（判定/清单）：它们是同一条验证链的两半，
拆开只制造"判定层读报告、报告层再认证报告"的循环。
"""
from __future__ import annotations

import math
import copy
import re
from typing import Any

from primitives import (AUX_TEXT_ROLES, CHART_LABEL_MIN_COUNT, CHART_LABEL_MIN_H,
                        DEFAULT_WIDTH, DEFAULT_HEIGHT, GRID_UNIT,
                        ELEMENT_TYPES, CHART_KINDS,
                        BG_MIN_COVERAGE, BG_MIN_PROTECT_OPACITY,
                        contrast, bg_coverage, bg_overlay_opacity, is_background_declared,
                        text_units, spec_fingerprint)
from intelligence import FAMILY_TOKENS, DENSITY_LEVELS, ENERGY_LEVELS

from primitives import is_cjk as _is_cjk   # 单一实现

# 图表容量上限（OS §19）：数值类 kind 集合与载荷契约（schema 合法 ≠ 画得出来）
NUMERIC_CHART_KINDS = {
    "bar", "horizontal_bar", "column", "comparison_bar", "line", "trend",
    "single_trend_line", "area", "donut", "donut_composition", "pie",
    "waterfall", "ranked_bar", "progress_bar", "stacked_bar", "bubble",
    "big_number_row", "sparkline",
}
SUPPORTED_CHART_KINDS = CHART_KINDS
ROWS_CHART_KINDS = (
    "bar", "horizontal_bar", "column", "comparison_bar", "line", "trend",
    "single_trend_line", "area", "donut", "donut_composition", "pie", "waterfall",
    "ranked_bar", "progress_bar", "stacked_bar", "sparkline", "big_number_row",
    "process_flow", "timeline", "steps", "bubble",
)
ELEMENT_METRIC_KINDS = ("kpi", "executive_kpi", "big_number")


def _text_box_capacity(e: dict) -> dict | None:
    """文本能不能装进声明的盒子——**容量判定的唯一方**（compiler 只渲染，不再判容量）。

    测量原语单源在 primitives（estimate_lines / insert_script_gaps / text_width），
    compiler.add_text 渲染用的也是同一组原语，不存在第二份容量实现需要同步：
      * 换行按 \\n 拆段，每段用 estimate_lines(插入中西细空格后的文本)；
      * 需要高度 = 总行数 × size × line_height，默认行高 1.35；
      * 可用高度 = height − 2 × padding，容差 +1px。
    wrap=False 时每段恒为 1 行（同 estimate_lines）。返回 None 表示不适用。
    （v7.2.1 审计修正 docstring：旧版「与 compiler.add_text 逐字同源」已过时——
    容量判定早已全部收口到本函数，误导性的「双份」说法会诱使维护者两边对齐改。）
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
    raw_lines = str(e.get("text", "")).split("\n")
    width_need = max((text_width(insert_script_gaps(t), size, float(e.get("char_spacing", 0) or 0))
                      for t in raw_lines), default=0)
    need = lines * size * lh
    usable_h = h - 2 * pad
    declared_max = e.get("max_lines")
    over_max = (isinstance(declared_max, int) and not isinstance(declared_max, bool)
                and declared_max >= 1 and lines > declared_max)
    return {"lines": lines, "need": need, "usable": usable_h, "size": size,
            "line_height": lh, "max_lines": declared_max,
            "over_height": need > usable_h + 1, "over_max_lines": bool(over_max),
            "over_width": not wrap and width_need > usable_w + 2, "width_need": width_need}


def _element_area(e: dict) -> float:
    try:
        return max(0.0, float(e.get("width", 0))) * max(0.0, float(e.get("height", 0)))
    except (TypeError, ValueError):
        return 0.0


# 线性分割：一维对象，compiler 走 add_connector 而不是 add_shape。
# 它们的 width/height 是**向量分量**不是盒子尺寸，所以水平线 height=0 是正确写法。
RULE_SHAPES = frozenset({"line", "arrow"})


def _is_rule_shape(e: dict) -> bool:
    return (isinstance(e, dict) and e.get("type") == "shape"
            and str(e.get("shape", "")).lower() in RULE_SHAPES)


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


def _family_token_known(token: str) -> bool:
    """引擎是否能解析这个家族写法：canonical ∪ 媒体模型 ∪ 别名键 ∪ brief 内容类型。"""
    if not token:
        return True
    if token in FAMILY_TOKENS:
        return True
    try:
        from intelligence import explicit_content_type  # brief 词汇表（唯一真源在 intelligence）
        return bool(explicit_content_type({"type": token}))
    except Exception:
        return True        # 解析器不可用时不做判断（宁可沉默，也不冤枉合法写法）


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

    # 值校验：字段写了但值不存在 = 该页判断静默失效（家族 → 媒体/叙事动作/构图全回落；
    # 留白职责 → 免检与锚点判断失效；能量/密度 → 节奏判断失效）。点名到合法值，但不阻断——
    # 工程事实是「这个值引擎不认识」，不是「这页不合格」。
    # 家族词表：**引擎认识的所有写法都算数**——route 家族（COVER…）、媒体模型命名
    # 空间（HERO/DATA…）、别名键，以及 brief 里写的内容类型（cover / statement / data…，
    # 经 route 的别名表解析）。曾经只认前两类，于是照 templates/brief.yml 写 `family: cover`
    # 的作者会在首页面上被逐页警告 15 次：引擎在用自己的第二套命名给作者的合法写法判卷。
    # 只剩「谁也解析不出来」才是事实错误（拼错），且按值去重——同一个错不刷 15 行。
    for key, legal, shown in (
            ("energy", set(ENERGY_LEVELS), " / ".join(ENERGY_LEVELS)),
            ("density", set(DENSITY_LEVELS), " / ".join(DENSITY_LEVELS))):
        value = field(key)
        if not value:
            continue
        value = str(value).strip()
        if value not in legal:
            add("page_contract", sid, "warn",
                f"{key}={value!r} 不在合法取值内（{shown}）——本页会静默退回默认判断，"
                f"写入判断的值才会生效")
    family_value = field("page_family")
    if family_value:
        family_value = str(family_value).strip()
        token = family_value.upper()
        if not _family_token_known(token):
            add("page_contract", f"{sid}:FAMILY_UNKNOWN:{token}", "warn",
                f"page_family={family_value!r} 引擎不认识（可写："
                f"{' / '.join(sorted(FAMILY_TOKENS))}，或 brief 的内容类型 cover / data / case…）"
                f"——本页会静默退回默认判断")
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
    # 未声明 focus 不是工程错误：焦点可以落在图像/留白上，由设计判断负责。


# ══════════════════════════════════════════════════════════════
# Preflight（静态预检）：把 primitives 中**确定性的**结构判据前移到静态治理层
#
# 目的：让「焦点尺度、文本/媒体预算、重心失衡、卡片墙、节奏趋平」这些问题
# 在编译与渲染之前就被点名，避免用 3–6 轮渲染去试出同一件事。
# 阈值住在 primitives（单一口径，v4.15 直连，不再有懒读取回落双态）。
# 预检条目为 hint 级：不改变 guard/QA 的通过判定，只提供可执行的最小修正。
# ══════════════════════════════════════════════════════════════

def _bg_qualified(e: dict, cw: float, ch: float) -> tuple[bool, str | None]:
    """背景层免检资格：覆盖 ≥BG_MIN_COVERAGE 画布，且有真实保护层或显式免检声明。"""
    if not is_background_declared(e):
        return False, "未声明为背景层"
    cover = bg_coverage(e, cw, ch)
    if cover < BG_MIN_COVERAGE:
        return False, (f"仅覆盖画布 {cover:.0%}（<{BG_MIN_COVERAGE:.0%}）："
                       f"这是内容对象，不是空间层")
    # Native solid grounds are already their own readability protection. Treating
    # a full-canvas paper/charcoal shape as an unprotected image made authors add
    # a meaningless overlay and then collide with source_zone. Keep the exemption
    # narrow: only a large rectangle with a real fill qualifies.
    if (str(e.get("type", "")).lower() == "shape"
            and str(e.get("shape", "")).lower() == "rect"
            and e.get("fill") not in (None, "none", {"type": "none"})):
        return True, None
    if e.get("readability_exempt"):
        return True, None
    op, why = bg_overlay_opacity(e)
    if op is None:
        if why == "unparsable":
            return False, "overlay 无法解析出 opacity"
        return False, "未声明 overlay/content_protection：叠加文字的可读性无保障"
    if op < BG_MIN_PROTECT_OPACITY:
        return False, (f"遮罩不透明度 {op:.2f} < {BG_MIN_PROTECT_OPACITY:.2f}，"
                       f"形同虚设")
    return True, None


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
        if e.get("type") == "image" and is_background_declared(e):
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



def _check_deck_anchor(slides: list, ch: float, add) -> None:
    """跨页锚（眉标 / 页码 / 证据编号）：锚不动，正文才可游走。

    每页 anchor 由 plan 发下来（家族标签 / 页码），生成侧落成元素。只查一件事：
    **声明了有没有落**（编号成套同理）——这是工程事实（存在性）。位置纪律
    （眉标固定上缘、页码固定象限）是设计判断，住在 references，不由引擎执法：
    引擎点名「位置不统一」时，作者学到的是每页挪回去，而不是判断为什么挪。
    词本身不查：眉标写什么字是设计判断——引擎给的是一套建议词汇，作者可以换成
    自己的说法（自定词汇反而是更贴内容的导航）。此前按字面比对，等于用引擎的
    占位词给作者判卷：每一页都报一次，把真正的信号淹掉。
    """

    _missing: list[str] = []
    _figures: list[tuple[str, str]] = []
    for s in slides:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id", "?"))
        anc = s.get("anchor")
        if not isinstance(anc, dict) or not anc:
            continue
        elems = [e for e in (s.get("elements") or []) if isinstance(e, dict)]
        role_elems = lambda r: [e for e in elems if str(e.get("role", "")) == r]  # noqa: E731
        if anc.get("eyebrow") and not role_elems("eyebrow"):
            _missing.append(f"{sid} 眉标")
        if anc.get("page_number") is not None and not role_elems("page_number"):
            _missing.append(f"{sid} 页码")
        # 证据编号（Fig. 01…）不再由 plan 发放，也不再要求落成元素：
        # 它是论文的交叉引用装置，演示文稿里没有「见 Fig. 02」这种回指，
        # 编号就只是来源行前面一串没人读的字符。
        # 但作者显式声明了 figure 的老 deck 仍要保证编号成套——
        # 半套编号（有的页有、有的页没有）比没有编号更让人怀疑「是不是漏了证据」。
        if anc.get("figure"):
            _figures.append((sid, str(anc["figure"])))

    if _missing:
        add("deck_anchor", "deck", "warn",
            f"声明了锚但没有落到页面上：{'、'.join(_missing[:6])}"
            + ("…" if len(_missing) > 6 else "")
            + "——锚不是装饰，缺一页就断链")
    if len(_figures) >= 2:
        nums = []
        for _sid, label in _figures:
            m = re.search(r"(\d+)", label)
            nums.append(int(m.group(1)) if m else None)
        if None not in nums and nums != list(range(nums[0], nums[0] + len(nums))):
            add("deck_anchor", "deck", "warn",
                f"证据编号不连续：{[l for _, l in _figures]}——编号断链会让「还有没有证据」"
                f"变成猜谜；按页序重编 01…N")


def _invalid_spec_result(message: str) -> dict:
    """Return a stable guard report for malformed top-level inputs."""
    check = {"rule": "spec_schema", "id": "spec", "level": "error", "msg": message}
    return {"passed": False, "checks": [check],
            "warnings": [f"[spec_schema] {message}"],
            "grid": {"checked": 0, "aligned": 0, "adherence": None}}


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


def _declared_layer_checks(slides, cw, ch, *, add, whitespace_min,
                           bg_layers_max, type_step_min, bold_ratio_max,
                           bg_layer_cov) -> dict | None:
    """声明执法层：量测无条件进行（镜子），执法只在作者写下数字时发生。

    五个量都对得上「可执行」的定义：说得出、量得到、超了有点名。未声明不检查。
    返回密度事实（每页占用带 + 整副均值），只进 JSON trace，不参与判定。
    """
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
                    # 背景层是纸，不是墨：不入留白测量（否则满幅封面恒 dense，
                    # 镜子对修订就是误导）；背景层计数保留（那是它的本职）。
                    if str(_e.get("layer", "")) != "background":
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
    # 密度事实（镜子，不是规则）：占用带只是测量归档，不设门槛、不进对话，
    # 只进 JSON trace——作者下一轮修订时对照「哪几页真的挤」自行判断。
    _density = None
    if _ws_pages:
        _mean_occ = sum(1.0 - w for _, w in _ws_pages) / len(_ws_pages)
        _pages_f = []
        for _sid, _w in _ws_pages:
            _occ = 1.0 - _w
            _band = "sparse" if _occ < 0.35 else ("dense" if _occ > 0.60 else "balanced")
            _pages_f.append({"id": _sid, "occupancy": round(_occ, 3), "band": _band})
        _density = {"deck_mean_occupancy": round(_mean_occ, 3), "pages": _pages_f}
    for _rule, _scope, _level, _msg in _seed_hits:
        add(_rule, _scope, _level, _msg, layer="declared")
    return _density


def _trace_deck_checks(theme, slides, *, add, chart_styles, accent_hue_min,
                       chart_label_scale_tol) -> None:
    """咨询层（deck 级）：色彩系统 / 图表风格漂移 / 弱化文字对比度。

    这些是设计判断的投影，不是可执行的门槛——住进独立函数，add 的 trace
    层在结构上禁止 error，永不阻断、永不进 fix_plan。升级检查的唯一合法
    方式：挪回 check_spec 主体并在注释里说明理由。
    """
    pal = theme.get("colors") or {}
    acc = _hls(pal.get("accent"))
    # 中性色没有色相可言：#1E1E1C 与 #6E6E6A 的 HLS 色相都会算成 60°，
    # 于是「灰阶 accent + 灰阶 primary」被判成同族——而这恰恰是本技能包
    # 自己的 zen_minimal / 安静极简种子生成的骨架配色。规则对自家出厂配色
    # 每次都误报，作者学到的是「这条 warning 可以忽略」，真正的同族撞色
    # 反而被一起忽略。彩度低于 NEUTRAL_SAT 的色不参与色相族判定
    # （与 _hue_family 的中性判定同一口径）。
    if acc and acc[2] >= NEUTRAL_SAT:
        for role in ("primary", "secondary"):
            role_hls = _hls(pal.get(role))
            if not role_hls or role_hls[2] < NEUTRAL_SAT:
                continue          # 中性主色不与强调色争色相：这是纪律，不是冲突
            gap = _hue_gap(acc, role_hls)
            if accent_hue_min is not None and gap is not None and gap < accent_hue_min:
                add("palette_discipline", f"theme.{role}", "warn",
                    f"accent {pal.get('accent')} 与 {role} {pal.get(role)} 色相差 "
                    f"{gap:.0f}° < {accent_hue_min:.0f}°：强调色与主色同族，页面拿不到"
                    f"「唯一重点」信号——把强调色移出色相族，或改由明度/尺度承担强调", layer="trace")
    for kind, rec in sorted(chart_styles.items()):
        if len(rec["pages"]) < 2:
            continue
        sizes = rec["sizes"]
        if len(sizes) > 1:
            lo, hi = min(sizes), max(sizes)
            if (chart_label_scale_tol is not None and lo > 0
                    and hi / lo > chart_label_scale_tol):
                add("chart_style_drift", kind, "warn",
                    f"{kind} 出现在 {len(rec['pages'])} 页但标签字号 "
                    f"{lo:g}–{hi:g}px（>{chart_label_scale_tol:g}×）：同一图表类型应共用"
                    f"一套标签规格，差异只会读成没对齐", layer="trace")



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
                    f"刻度/注释将不可读（建议加深至 ≥3:1）", layer="trace")


def check_spec(spec: dict, rules: dict | None = None) -> dict:
    """
    静态治理：对调用方传入的 spec 做 OS 硬约束断言。

    rules（可配置阈值，调用方传入；缺省用默认值；脏输入一律回落默认不炸链。
    只做工程判定与「作者自己写下的数字」执法：结构、数据、几何、越界、来源、
    可读性底线、资产链。设计判断不设门槛，只以 trace 身份留痕（永不阻断）。
    主题约束 `spec.theme.constraints` 仅对 accent_max/max_charts/max_colors/
    font_levels_max/font_families_max 五项在未显式传入 rules 时生效）:
      overlap_ratio  : 元素重叠容忍上限（默认 .12）
      text_ink_ratio : 文本框参与重叠的有效宽度系数（默认 .55，文本框≠墨迹）
      text_ink_v     : 文本框参与重叠的有效高度系数（默认 .70，行高/padding 余量）
      accent_max     : Accent 面积占比上限（默认 .05；VP 主题多为 .03–.05）
      accent_text_k  : 文字面积折算系数（默认 .30，文本框 ≠ 墨迹面积）
      max_charts     : 每页图表总数上限（VP-007=3 / VP-009=2）
      max_colors     : 每页颜色角色数上限（VP 主题 4–5）
      hue_families_max    : 全套色相族上限（未声明不检查；30° 一档，纸色/灰阶不计）
      accent_hue_min      : Accent 与主/辅色的最小色相角（未声明不检查）
      chart_label_scale_tol: 同一图表类型跨页标签字号的最大倍数（未声明不检查）
      animation_types_max : 全套动画/切换类型上限（默认 2）
      font_levels_max     : 每页字号等级上限（默认 4，hint；可经 theme.constraints 传入）
      font_families_max   : 每页字体家族引用上限（默认 2，hint）
      min_font_size       : 注释/来源/标签类文字最小字号（默认 10；违反记在 typography）
      require_provenance  : 数值图表必须声明来源/单位/期间/比较口径（默认 False=warn，True=error）

    事实/口径治理（本版本新增，业务级）：
      data_provenance  : 数值图表缺 来源/单位/期间/比较口径 声明 → warn（require_provenance=True 时 error）
      metric_consistency: 同一 metric 跨页单位/期间/比较口径不一致 → 一条（单位不一致为 error）
      title_semantics  : insight 退化成「字段名标题」→ hint（提示改写为可复述结论）

    returns: {
      "passed": bool（无 error 即 True）,
      "checks": [{rule, id, level, msg, layer}, ...],
      "warnings": [...],
      "facts": {"density": {pages: [{id, occupancy, band}], deck_mean_occupancy}} | {}
    }
    layer 三级执法身份：hard（可 error，阻断）/ declared（只执法作者写下的数字）/
    trace（咨询留痕，结构性禁止 error）。blocking 判定只消费 error 级检查。
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
    overlap_ratio = _rule_num(rules, "overlap_ratio", 0.12, float)
    text_ink_ratio = _rule_num(rules, "text_ink_ratio", 0.55, float)
    text_ink_v = _rule_num(rules, "text_ink_v", 0.70, float)
    max_charts = rules.get("max_charts", constraints.get("max_charts"))
    max_colors = rules.get("max_colors", constraints.get("max_colors"))
    # 色相族数量 / Accent 色相角 / 图表标签字号漂移：都是设计判断（§09 的「颜色太多 /
    # 焦点是否准确 / 视觉语言是否统一」）。曾经各带一个发明出来的默认值（4 / 12° / 1.25），
    # 于是包按自己的刻度判作者的稿——颜色多不多、强调够不够、图表风格统不统一，
    # 该由设计判断。作者写进 rules / theme.constraints 才执法；不写就不检查。
    hue_families_max = _rule_num(rules, "hue_families_max",
                                 constraints.get("hue_families_max"), int)
    accent_hue_min = _rule_num(rules, "accent_hue_min",
                               constraints.get("accent_hue_min"), float)
    chart_label_scale_tol = _rule_num(rules, "chart_label_scale_tol",
                                      constraints.get("chart_label_scale_tol"), float)
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
    # 可读性底线：注释/来源/标签类文字的最小字号（设计单位 px）
    min_font_size = _rule_num(rules, "min_font_size", 10, float)
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

    def add(rule, eid, level, msg, *, layer="hard"):
        # layer = 执法身份：hard（可 error，阻断）/ declared（只执法作者写下的数字）/
        # trace（咨询留痕，结构性禁止 error——误写会被压回 warn，永不进 blocking 与
        # fix_plan）。升级一条 trace 检查的唯一合法方式：挪出 trace 层并说明理由。
        if layer == "trace" and level == "error":
            level = "warn"
        checks.append({"rule": rule, "id": eid, "level": level, "msg": msg,
                       "layer": layer})
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
        except (TypeError, ValueError, OverflowError):
            add("canvas_schema", "canvas", "error", "canvas.grid_columns 必须是正整数")
    if "grid_unit" in canvas:
        try:
            if isinstance(canvas["grid_unit"], bool):
                raise ValueError
            unit = float(canvas["grid_unit"])
            if not math.isfinite(unit) or unit <= 0:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            add("canvas_schema", "canvas", "error", "canvas.grid_unit 必须是正的有限数字")

    # ---- 色彩 token 拼写（deck 级预备：一次算出可用名字集）----
    # 渲染层对认不出的 token 一律**静默回落**（text_color → ink，是必要的渲染安全网，
    # 不能改）。但静默回落意味着 `color: "secondry"` 这类拼写错永远不会被发现：
    # 产物照出、颜色照错、没有任何痕迹。fill 走 apply_fill 会硬报错，color 却不会——
    # 同一类错误两种待遇。治理层把这个缝补上：认不出的名字点名到元素。
    _known_tokens = set()
    if isinstance(theme.get("colors"), dict):
        _known_tokens |= {str(k).strip() for k in theme["colors"]}
        try:
            from primitives import derive_tokens
            _known_tokens |= set(derive_tokens(dict(theme["colors"])))
        except Exception:
            pass

    def _unknown_color(value) -> str | None:
        """返回「认不出的 token 名」；None 表示可解析（hex / 已知 token / 非字符串）。"""
        if not isinstance(value, str):
            return None
        raw = value.strip()
        if not raw or raw.lower() in ("none", "transparent"):
            return None
        if raw.startswith("#"):
            # #RGB / #RRGGBB / #RRGGBBAA 之外的十六进制都是写坏的色值
            body = raw[1:]
            ok = len(body) in (3, 6, 8) and all(c in "0123456789abcdefABCDEF" for c in body)
            return None if ok else raw
        return None if raw in _known_tokens else raw

    # ---- 每页 ----
    deck_hues: set[int] = set()
    chart_styles: dict[str, dict] = {}
    chart_meta: list[dict] = []   # 事实/口径治理：收集每张数值图表的来源/单位/期间/口径
    for si, s in enumerate(slides):
        if not isinstance(s, dict):
            # 首轮 schema 扫描已记录错误；此处只跳过，保证后续检查不崩溃。
            continue
        sid = s.get("id", f"slide_{si}")
        _check_page_contract(s, sid, add, cw, ch)
        chart_count = 0
        page_colors: set[str] = set()
        for e in s.get("elements", []):
            if not isinstance(e, dict):
                continue
            eid = e.get("id", f"{sid}[{si}]")
            typ = str(e.get("type", "text"))
            role = str(e.get("role", ""))
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
                # 可读性底线：注释/来源/标签类文字不得低于最小字号（渲染后可读性复核）
                if role in {"caption", "annotation", "source", "label", "axis", "data_label",
                            "legend", "metadata", "method", "eyebrow", "page_number"}:
                    try:
                        if e.get("size") is not None and float(e["size"]) < min_font_size:
                            add("typography", eid, "warn",
                                f"{role} 文字 {float(e['size']):g}px < 可读下限 "
                                f"{min_font_size:g}px；提高字号或改由更高层级角色承担",
                                layer="trace")
                    except (TypeError, ValueError):
                        pass
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
                elif _is_rule_shape(e):
                    # 分割线/箭头是**一维对象**：一条水平发丝线的自然写法就是 height=0
                    # （compiler 走 add_connector，从 (x,y) 画到 (x+w, y+h)，渲染完美）。
                    # 按二维盒子的「w/h 必须 > 0」要求它，等于禁掉了线性分割的标准写法——
                    # 逼作者改用 1px 矩形，或干脆退回画卡片。
                    # 真正的退化是**两轴都为 0**（零长度的线看不见），只拦这一种。
                    if _fw <= 0 and _fh <= 0:
                        add("element_schema", eid, "error",
                            "geometry 退化（线的 width 与 height 同时为 0 → 零长度，不可见）；"
                            "水平线写 height=0，垂直线写 width=0")
                elif _fw <= 0 or _fh <= 0:
                    add("element_schema", eid, "error",
                        f"geometry 退化（width={_fw:g}, height={_fh:g} ≤ 0 "
                        "→ 元素渲染不可见）")

            # 色彩 token 拼写：认不出的名字在渲染层会被静默吞掉（回落 ink / 跳过描边），
            # 于是「配色写了没生效」不留任何痕迹。这里只判**名字认不认得**，
            # 不判颜色好不好看——后者是设计判断，不归治理层。
            if _known_tokens:
                for _field in ("color", "fill", "stroke", "border_color",
                               "track_color", "label_color", "background"):
                    if _field not in e:
                        continue
                    _val = e.get(_field)
                    if isinstance(_val, dict):     # Fill Contract：只看 solid 的色值
                        _val = _val.get("color") if _val.get("type") in (None, "solid") else None
                    _bad = _unknown_color(_val)
                    if _bad:
                        add("color_token", eid, "error",
                            f"{_field}={_bad!r} 既不是主题色角色、也不是合法 #HEX："
                            f"渲染层会静默回落（配色写了不生效，且不留痕迹）。"
                            f"可用角色：{sorted(_known_tokens)[:8]}…")

            # 文本框容量（静态版，与 compiler.add_text 同一套算法）：
            # 「估算高度超出文本框」此前**只有编译器**知道——于是 spec 档（不编译）
            # 完全看不见溢出，draft 档虽然被 COMPILE_FAIL 拦下，但修复包里
            # 拿不到元素 id（affected_slides 为空、ids 为空），Agent 只能回读
            # 编译 warning 的散文去猜是哪个框。溢出是内容完整性事实、不是审美判断，
            # 理应和 text_capacity 的行长失控同级，在治理层就点名到元素。
            if typ in {"text", "shape"} and str(e.get("text") or "").strip():
                te = e if typ == "text" else dict(e, size=e.get("text_size", 16),
                    wrap=e.get("text_wrap", True), line_height=e.get("text_line_height", 1.25))
                cap = _text_box_capacity(te)
                if cap and cap["over_height"]:
                    add("text_capacity", eid, "error",
                        f"估算高度 {cap['need']:.0f}px 超出文本框可用高度 "
                        f"{cap['usable']:.0f}px（{cap['lines']} 行 × 字号 {cap['size']:g} "
                        f"× 行高 {cap['line_height']:g}）：加框高 / 减行数 / 删字，不要缩字号")
                elif cap and cap["over_width"]:
                    add("text_capacity", eid, "error",
                        f"禁止换行的文字估算宽度 {cap['width_need']:.0f}px 超出文本框宽度；加宽或删字")
                elif cap and cap["over_max_lines"]:
                    add("text_capacity", eid, "error",
                        f"估算 {cap['lines']} 行 > 声明 max_lines {cap['max_lines']}"
                        "：文本会被截断或挤出框；删句、改写或放宽 max_lines")

            # 行长不再由引擎执法（2026-09 审核）：这一判定的两个出口都只是编辑观点——
            # 「每行 40 字以内」不是物理事实，而「超过上限 2×」在实测里也对**装得下**
            # 的文本框开火（探针：12px/1200px 盒，165 字单行宽度 1089px 仍在框内）。
            # 排版是否可读由设计判断与 design-craft 的取舍链负责；引擎只留物理事实：
            # 折行后装不装得下（_text_box_capacity 的 over_height / over_width / max_lines）。
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
            except (TypeError, ValueError):
                pass

            # （v7.2.0 审计：slide 级 safe_zones 无任何 producer——骨架/模板/文档
            # 都不发它，文字安全区由逐页资产的 safe_area 承担（QC 侧）。死检查删。）

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
                                f"几乎一样——同一长度尺度上看不出主张要传达的差。"
                                f"换何种编码由设计判断决定（差值绝对值、共同基线、索引化…）")
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
                    if (show_values and n >= CHART_LABEL_MIN_COUNT
                            and eh < CHART_LABEL_MIN_H):
                        level = "error" if label_policy == "fail" else "warn"
                        add("chart_label_collision", eid, level,
                            f"{kind} 含 {n} 个标签但高度 {eh:.0f}px 不足；应拆图/减少类别，不能缩小字体")
                except (TypeError, ValueError):
                    add("chart_label_collision", eid, "error",
                        "图表标签安全参数必须是数字")

            # 颜色角色的收集只为「作者声明的 max_colors / 色相族上限」服务。
            for key in ("color", "fill", "stroke"):
                v = e.get(key)
                if isinstance(v, str) and v in theme.get("colors", {}):
                    page_colors.add(v)
                    if v not in NEUTRAL_COLOR_ROLES:
                        fam = _hue_family(theme["colors"][v])
                        if fam is not None:
                            deck_hues.add(fam)
                elif isinstance(v, str) and v.startswith("#"):
                    page_colors.add(v.upper())
                    fam = _hue_family(v)
                    if fam is not None:
                        deck_hues.add(fam)

            if typ in ("chart", "native_chart"):
                if chart_label_scale_tol is not None:
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
                        provenance[meta_key] = v.strip() if isinstance(v, str) else None
                    missing = [label for meta_key, label in
                               (("source", "来源"), ("unit", "单位"),
                                ("period", "期间"), ("basis", "比较口径"))
                               if not provenance[meta_key]]
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
            if _bg_qualified(e, cw, ch)[0]:
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
                    # 已声明的空间遮挡是合法手法，不提示（是否遮挡关键内容由图看）。

        # 背景层资格（工程事实，非预测）：伪背景 error、无保护 warn
        _check_background_qualification(s, sid, cw, ch, add)

        # （v7.2.0 审计删除两个重复判定：geom_occlude 用原始声明框 ≥30% 重判
        # overlap error 已用墨迹口径 >12% + 豁免表判过的同一事实——声明框不是
        # 可见墨迹，粗口径只会对合法叠压（文本压在图形上）报噪音；
        # baseline_crossing 只认 fill:hairline/track 的填充矩形基线（legacy 写法），
        # 文档口径是 shape:line + stroke 发丝线（fill 为空），对合规 spec 永不触发。）

        # 焦点尺度：声明焦点为文字时，应获得页内最大字号（OS「一页一焦点」）
        # ---- 主题字体键（deck 级，逐页重复没意义，但每页都被它影响）----
        if si == 0:
            fonts = theme.get("fonts") if isinstance(theme.get("fonts"), dict) else None
            problems: list[str] = []
            if not fonts:
                problems.append("theme.fonts 未声明：产物会回落 Arial / Microsoft YaHei"
                                "（字体判断在产物里消失）")
            else:
                unknown = sorted(str(k) for k in fonts
                                 if str(k) not in ("cn", "latin", "display", "body"))
                if unknown:
                    problems.append(f"{unknown} 不是被读取的键（规范键 cn / latin）——写了等于没写")
                if not str(fonts.get("cn") or fonts.get("body") or "").strip():
                    problems.append("没有中文字族（cn/body）：中文会回落 Microsoft YaHei")
                if not str(fonts.get("latin") or fonts.get("display") or "").strip():
                    problems.append("没有拉丁字族（latin/display）：拉丁与数字会回落 Arial")
            if problems:
                add("theme_fonts", "deck", "warn", "；".join(problems),
                    layer="trace")

        # ---- 主题约束键：写错的名字要点名（同 theme_fonts 的做法）----
        if si == 0:
            _KNOWN_CONSTRAINTS = frozenset({
                "max_charts", "max_colors", "whitespace_min", "min_whitespace",
                "type_step_min", "bg_layers_max", "bg_layer_coverage", "bold_ratio_max",
                "hue_families_max", "accent_hue_min", "chart_label_scale_tol"})
            _unknown_cons = sorted(str(k) for k in constraints if str(k) not in _KNOWN_CONSTRAINTS)
            if _unknown_cons:
                add("theme_constraint", "deck", "warn",
                    f"theme.constraints 里的 {_unknown_cons} 不生效（可用的键："
                    f"max_charts / max_colors / whitespace_min / type_step_min / "
                    f"bg_layers_max / bg_layer_coverage / bold_ratio_max / hue_families_max / "
                    f"accent_hue_min / chart_label_scale_tol）——写了等于没写",
                    layer="trace")

        # ---- 主题生产约束（来自 VP 主题「生产约束」章节） ----
        if max_charts is not None and chart_count > int(max_charts):
            add("theme_constraint", sid, "warn",
                f"每页图表 {chart_count} > 主题上限 {max_charts}", layer="declared")
        if max_colors is not None and len(page_colors) > int(max_colors):
            add("theme_constraint", sid, "hint",
                f"每页颜色 {len(page_colors)} > 主题上限 {max_colors}（仅统计引用角色/字面色）",
                layer="declared")

    # 声明执法层 + 密度测量（镜子）：量测每轮进行，执法只在作者写下数字时发声
    _density = _declared_layer_checks(
        slides, cw, ch, add=add, whitespace_min=whitespace_min,
        bg_layers_max=bg_layers_max, type_step_min=type_step_min,
        bold_ratio_max=bold_ratio_max, bg_layer_cov=bg_layer_cov)

    _check_deck_anchor(slides, ch, add)

    # ---- 色彩系统纪律（deck 级）：单页合规不等于全套成套 ----
    if hue_families_max is not None and len(deck_hues) > hue_families_max:
        add("palette_discipline", "deck", "warn",
            f"全套使用 {len(deck_hues)} 个色相族（{HUE_BUCKET:.0f}° 一档）> 上限 "
            f"{hue_families_max}；颜色已不成系统——收拢为一组主辅色 + 一个强调色",
            layer="declared")
    # ---- 咨询层（deck 级）：色彩系统 / 图表风格漂移 / 对比度——只留痕，永不阻断 ----
    _trace_deck_checks(theme, slides, add=add, chart_styles=chart_styles,
                       accent_hue_min=accent_hue_min,
                       chart_label_scale_tol=chart_label_scale_tol)

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
        # 同一指标的跨页口径差异一次说完（单位=硬错；期间/比较口径=留痕）：
        # 拆成 error/warn/hint 三条时，读者要先在三条里找哪条是同一件事。
        if len(units) > 1 or len(periods) > 1 or len(basis) > 1:
            bits = []
            if len(units) > 1:
                bits.append(f"单位 {sorted(units)}（同一指标必须同一单位，否则读成两套数字）")
            if len(periods) > 1:
                bits.append(f"期间 {sorted(periods)}（若确实要对比不同期间，在 basis 里声明）")
            if len(basis) > 1:
                bits.append(f"比较口径 {sorted(basis)}（建议统一或显式声明差异）")
            add("metric_consistency", f"metric:{metric}",
                "error" if len(units) > 1 else "warn",
                f"指标「{metric}」跨页口径不一致：" + "；".join(bits))

    return {
        "passed": not any(c["level"] == "error" for c in checks),
        "checks": checks,
        "warnings": warnings,
        "facts": {"density": _density} if _density else {},
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


# ══════════════════════════════════════════════════════════════════
# 判定与发布清单（原 qa：只消费报告，PASS / BLOCK 二态）
# ══════════════════════════════════════════════════════════════════
import time as _time
from pathlib import Path as _Path

MODES = {
    "spec":    {"label": "Spec · 只诊断", "compile": False,
                "aim": "归一化 + Guard 判定，不写 PPTX"},
    "draft":   {"label": "Draft · 创作（默认）", "compile": True,
                "aim": "Guard + Compile 一次通过，产出可编辑 PPTX 与分组修复包"},
    "release": {"label": "Release · 交付", "compile": True,
                "aim": "draft 全部 + 数值图表出处硬门 + 结构预览证据 + 发布清单"},
}
DEFAULT_MODE = "draft"

_RULE_CODES = {
    "overlap": "OVERLAP", "source_zone": "SOURCE_COLLISION",
    "chart_label_collision": "CHART_LABEL_COLLISION",
    "text_capacity": "TEXT_OVERFLOW", "contrast": "READABILITY_FAIL",
    "data_integrity": "DATA_INTEGRITY_FAIL",
    "data_provenance": "DATA_INTEGRITY_FAIL",
    "chart_type": "CHART_TYPE_FAIL",
    "safety": "GUARD_FAIL",
}
FIX_HINTS = {
    "OVERLAP": "文本/图表/图片/来源区墨迹不相交；挪几何或删元素，不缩字号。",
    "SOURCE_COLLISION": "来源区（source_zone）内只放 role∈{source,method,metadata} 的文字。",
    "CHART_LABEL_COLLISION": "用 label_collision_policy:hide_redundant|move_outside|fail 处置，不缩字号。",
    "TEXT_OVERFLOW": "框高 ≥ 字号×行高×行数；减行数/减字数/加框高，三选一。",
    "READABILITY_FAIL": "声明色对比不足：加深文字色或加遮罩/底衬，不动构图。",
    "DATA_INTEGRITY_FAIL": "每行 label + 有限 value；数值图齐 source/unit/period/basis。",
    "CHART_TYPE_FAIL": "图表类型在白名单内且数据形态匹配（占比≠趋势）。",
    "COMPILE_FAIL": "按编译 warnings 修 schema，不绕过 Guard。",
    "GUARD_FAIL": "按下述明细逐条修：element_schema/focus/几何合法性优先。",
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
    """阻断项按根因分组，**组内携带 error 明细**——修复包自足，零回读。"""
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


def build_trace_summary(checks) -> list:
    """非阻断项按 rule 聚合留痕（不进对话，只进 JSON 证据）。"""
    agg: dict = {}
    order: list = []
    for c in checks or []:
        if not isinstance(c, dict) or c.get("level") not in ("warn", "hint"):
            continue
        key = (c.get("rule"), c.get("level"))
        if key not in agg:
            agg[key] = {"rule": key[0], "level": key[1], "count": 0, "samples": []}
            order.append(key)
        b = agg[key]
        b["count"] += 1
        if c.get("msg") and len(b["samples"]) < 3:
            b["samples"].append(str(c["msg"])[:200])
    return [agg[k] for k in order]


def release_guard_rules(mode, guard_rules=None):
    rules = dict(guard_rules or {})
    if mode == "release" and "require_provenance" not in rules:
        rules["require_provenance"] = True
    return rules


def verdict(spec, output, *, mode=None, guard_report, compile_report,
            runtime_facts=None) -> dict:
    """判定：只消费报告（guard + compile），不编译、不读产物字节。"""
    t0 = _time.time()
    prof = mode_profile(mode)
    mode = prof["mode"]
    facts = dict(runtime_facts or {})
    do_compile = bool(prof["compile"])
    guard = guard_report if isinstance(guard_report, dict) else {}
    _gfacts = guard.get("facts") if isinstance(guard.get("facts"), dict) else {}
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
    if blocking and "GUARD_FAIL" not in codes:
        codes.append("GUARD_FAIL")
    if compile_failed:
        codes.append("COMPILE_FAIL")
    codes = [c for c in codes if c in BLOCKING_CODES]
    passed = not codes
    status = "BLOCKED" if codes else ("PREVIEW_ONLY" if not do_compile else "PASS")
    release_eligible = bool(status == "PASS" and mode == "release" and cr.get("passed"))
    next_action = ("fix: " + ", ".join(codes)) if codes else (
        "ready · 交付前用 --mode release 收口" if mode != "release" else "ready")
    result = {
        "source_spec_hash": spec_fingerprint(spec),
        "normalization": facts.get("normalization"),
        "execution": {"entrypoint": "vao.py", "mode": mode, "profile": prof["label"],
                      "compiled": do_compile,
                      "provenance_required": bool(facts.get("provenance_required", False)),
                      "external_renderer": "disabled", "visual_evidence": "ghost_preview"},
        "verdict": {"verdict": "BLOCKED" if codes else "PASS", "status": status,
                    "blocking": len(blocking),
                    "trace": len([c for c in guard.get("checks", [])
                                  if c.get("level") in ("warn", "hint")]),
                    "codes": codes, "question": "这份 PPT 能不能交付？"},
        "status": status, "passed": passed, "release_eligible": release_eligible,
        "blocking_items": len(blocking), "failure_codes": codes,
        "affected_slides": sorted({str(c.get("id")).split(":")[0] for c in blocking
                                   if c.get("id")}),
        "blocking_detail": [{"rule": c.get("rule"), "id": c.get("id"),
                             "msg": str(c.get("msg") or "")[:220]} for c in blocking],
        "guard": {"checks": len(guard.get("checks", [])), "errors": len(blocking)},
        "compile": {k: cr.get(k) for k in
                    ("passed", "skipped", "reason", "warnings", "slides", "file_bytes",
                     "output_sha256", "output_path", "performance", "reused")},
        "fix_plan": build_fix_plan(guard, cr),
        "trace_summary": build_trace_summary(guard.get("checks")),
        "facts": _gfacts,
        "asset_workflow": facts.get("asset_workflow"),
        "next_action": next_action,
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
    if scope == "sampled":
        expected = [str(x) for x in (ghost.get("sampled_ids") or [])]
        actual = [str(x) for x in (ghost.get("slide_ids") or [])]
        if (not expected or expected != actual or ghost.get("count") != len(expected)
                or len(pages) != len(expected)):
            return ["采样预览的声明页与实际渲染页不一致"]
        outside = [x for x in expected if x not in {str(p) for p in page_ids}]
        if outside:
            return ["采样预览引用了当前稿件之外的页面：" + "、".join(outside)]
    elif (ghost.get("slide_ids") != [str(p) for p in page_ids]
          or ghost.get("count") != len(page_ids) or len(pages) != len(page_ids)):
        return ["预览页没有完整覆盖当前稿件"]
    return []


def release_manifest(spec, qa_report: dict, *, ghost_preview=None,
                     workflow: dict | None = None) -> dict:
    """发布清单：报告可追溯到当前 spec、产物字节与磁盘一致、预览页在稿内。

    产物核对只有一级：重算一次 SHA-256 与报告比对（10MB 级文件毫秒级），
    没有二级见证协议。
    """
    from datetime import datetime, timezone
    from primitives import file_digest

    spec = spec if isinstance(spec, dict) else {}
    qa_report = qa_report if isinstance(qa_report, dict) else {}
    spec_hash = spec_fingerprint(spec)
    issues: list = []
    notes: list = []
    slides = spec.get("slides") if isinstance(spec.get("slides"), list) else []
    page_ids = {str(s.get("id")) for s in slides if isinstance(s, dict) and s.get("id")}

    got = qa_report.get("source_spec_hash")
    if got and got != spec_hash:
        norm = qa_report.get("normalization") or {}
        if not (norm.get("hash_before") == spec_hash and norm.get("hash_after") == got
                and norm.get("idempotent")):
            issues.append("qa_report 来自另一版 spec（source_spec_hash 不符）")
    ghost = ghost_preview if isinstance(ghost_preview, dict) else None
    if ghost:
        ghost_issues = preview_issues(ghost, sorted(page_ids))
        issues.extend(ghost_issues)
        if ghost.get("count") and len(ghost.get("pages") or []) < len(slides):
            notes.append(f"预览覆盖 {ghost.get('count')}/{len(slides)} 页（方向采样）")
    compile_claim = qa_report.get("compile") if isinstance(qa_report.get("compile"), dict) else {}
    output_path, output_sha = compile_claim.get("output_path"), compile_claim.get("output_sha256")
    if output_path or output_sha:
        if not output_path or not output_sha:
            issues.append("PPTX 凭证不完整：需要 output_path 与 output_sha256")
        else:
            try:
                actual = file_digest(output_path)
                if actual != output_sha:
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
    if qa_report.get("passed"):
        issues.extend(preview_issues(ghost, sorted(page_ids)))
    status = "BLOCKED" if issues else str(qa_report.get("status", "BLOCKED"))
    release_eligible = bool(status == "PASS" and qa_report.get("release_eligible"))
    return {
        "schema": "vao-release-manifest-v2",
        "source_spec_hash": spec_hash,
        "validation": {"issues": issues, "notes": notes, "page_count": len(page_ids)},
        "slide_count": len(slides),
        "release_eligible": release_eligible,
        "asset_workflow": wf,
        "verification": {
            "external_renderer": "disabled",
            "visual_evidence": "ghost_preview" if ghost else "structural_only",
            "visual_evidence_scope": (ghost or {}).get("scope", "full") if ghost else None,
            "structural_pages": len(page_ids),
            "ghost_pages": (ghost or {}).get("count") if ghost else 0,
            "release_eligible": release_eligible},
        "compile_report": compile_claim,
        "qa_summary": {k: qa_report.get(k) for k in
                       ("status", "passed", "failure_codes", "blocking_items",
                        "performance", "execution")},
        "ghost_preview": ({"dir": ghost.get("dir"),
                           "contact_sheet": ghost.get("contact_sheet")} if ghost else None),
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
