# -*- coding: utf-8 -*-
"""
Layer 0 · Primitives（基础层）

职责：单位换算、色彩数学与色阶推导、字体绑定、几何，以及层间契约 `RenderContext`。

本层不知道 spec 的结构，不知道元素语义，不知道图表类型。
它只提供「怎么把一段文字/一个形状画到画布上」的最小能力。

依赖方向：primitives ← elements / charts ← compiler
本层不反向依赖任何上层，因此可独立演进。
"""
from __future__ import annotations

import math
from pathlib import Path

# ── python-pptx 延迟加载（v3.2 契约，别改回顶层 import）────────────────────
# 本层被 guard / normalizer / qa 复用，而它们**只处理 spec 数据**：draft 一轮
# 真正的判断成本是 2.8ms，pptx 的 import 却要 152ms（pptx.api → opc → oxml →
# xml.sax → urllib.request）。把整套 Presentation API 拖进「读数据」的路径是
# 架构错误，所以这里只在真的要用 pptx 对象时才解析（`_p()`，进程内缓存一次）。
# 自检 `check_draft_import_contract` 会断言 draft 进程内不得出现 pptx / lxml /
# compiler —— 谁把 `from pptx import ...` 放回本层顶部，立刻失败。
_PPTX: dict | None = None


def _p() -> dict:
    """pptx 符号表的延迟入口：只在编译/渲染路径被调用。"""
    global _PPTX
    if _PPTX is None:
        from pptx.util import Emu, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
        from pptx.oxml import parse_xml
        from pptx.oxml.ns import qn, nsdecls
        _PPTX = {"Emu": Emu, "Pt": Pt, "RGBColor": RGBColor,
                 "PP_ALIGN": PP_ALIGN, "MSO_ANCHOR": MSO_ANCHOR,
                 "parse_xml": parse_xml, "qn": qn, "nsdecls": nsdecls}
    return _PPTX

# 1280 design px -> 13.333 in (12192000 EMU)
PX_TO_EMU = 9525
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1280, 720

# 设计系统基线网格（8 单位）：guard 归一化确认、normalizer 吸附、SKILL.md 契约三方同源
GRID_UNIT = 8

_ALIGN_KEYS = {"left", "center", "right", "justify"}
_ANCHOR_KEYS = {"top", "middle", "bottom"}
_ALIGN_FALLBACK = {None: "left", "": "left"}
_ANCHOR_FALLBACK = {None: "top", "": "top"}


_ALIGN_ATTR = {"left": "LEFT", "center": "CENTER", "right": "RIGHT",
               "justify": "JUSTIFY"}
_ANCHOR_ATTR = {"top": "TOP", "middle": "MIDDLE", "bottom": "BOTTOM"}


def align_of(value, fallback=None):
    """文本对齐：名字 → pptx 枚举（延迟解析）。未识别的名字交给 fallback。"""
    key = _ALIGN_FALLBACK.get(value, value)
    if key not in _ALIGN_KEYS:
        return fallback
    return getattr(_p()["PP_ALIGN"], _ALIGN_ATTR[key])


def anchor_of(value, fallback=None):
    """垂直锚点：名字 → pptx 枚举（延迟解析）。"""
    key = _ANCHOR_FALLBACK.get(value, value)
    if key not in _ANCHOR_KEYS:
        return fallback
    return getattr(_p()["MSO_ANCHOR"], _ANCHOR_ATTR[key])


# 渲染级安全回落（不是设计观点）：主题未声明字体时保证文件可渲染。
FALLBACK_CN = "Microsoft YaHei"
FALLBACK_LATIN = "Arial"


def color_to_hex(value) -> str | None:
    """RGBColor / #RRGGBB / "RRGGBB" → 六位大写 HEX；解析不出来返回 None。

    与 pptx 类型解耦：既接受真实的 RGBColor（可迭代/str()），也接受纯字符串，
    这样「取对比度」这类判断不依赖 pptx 是否已被加载。
    """
    if value is None:
        return None
    try:
        if isinstance(value, str):
            h = value.lstrip("#").upper()
            return h if len(h) == 6 else None
        if all(isinstance(x, int) for x in value):        # RGBColor 是 int 三元组
            return "".join(f"{c:02X}" for c in value)
    except Exception:
        pass
    try:
        h = str(value).lstrip("#").upper()
        return h if len(h) == 6 else None
    except Exception:
        return None


def fallback_ink():
    """未声明墨色时的安全值（RGBColor，需要 pptx → 延迟构造）。"""
    return _p()["RGBColor"](0x20, 0x20, 0x20)


def emu(px) -> int:
    return int(round(float(px) * PX_TO_EMU))


def pt(px):
    # design px -> points（1 design px = 0.75 pt）
    return _p()["Pt"](float(px) * 0.75)


# --------------------------------------------------------------------------
# 色彩数学（纯函数，与主题无关）
# --------------------------------------------------------------------------
def _tuple(hex_color: str):
    h = str(hex_color).lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, int(round(c)))) for c in rgb))


# ---------------------------------------------------------------------------
# OKLab 感知均匀色彩空间（Björn Ottosson 2020）
# sRGB 是伽马编码的非线性空间：旧 blend 直接按通道线性插值，中档色会在
# 视觉上偏灰偏浊（「脏色」）——同一份色板，浅档与深档之间的过渡会糊。
# OKLab 的 L 轴近似感知亮度、a/b 轴近似红绿/黄蓝对立色，在 OKLab 里插值
# 得到的中档色明度更均匀、彩度更干净，是「高级感」在色彩层的最低成本来源。
# ---------------------------------------------------------------------------
_OKLAB_M1 = (0.4122214708, 0.5363325363, 0.0514459929)
_OKLAB_M2 = (0.2119034982, 0.6806995451, 0.1073969566)
_OKLAB_M3 = (0.0883024619, 0.2817188376, 0.6299787005)


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    c = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
    return max(0.0, min(1.0, c)) * 255.0


def _rgb_to_oklab(rgb: tuple) -> tuple:
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    l = _OKLAB_M1[0] * r + _OKLAB_M1[1] * g + _OKLAB_M1[2] * b
    m = _OKLAB_M2[0] * r + _OKLAB_M2[1] * g + _OKLAB_M2[2] * b
    s = _OKLAB_M3[0] * r + _OKLAB_M3[1] * g + _OKLAB_M3[2] * b
    l_, m_, s_ = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, a, b


def _oklab_to_rgb(L: float, a: float, b: float) -> tuple:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return (_linear_to_srgb(r), _linear_to_srgb(g), _linear_to_srgb(b))


def blend(a: str, b: str, t: float, space: str = "oklab") -> str:
    """两色混合。默认在 OKLab 感知空间插值（明度/彩度更均匀，中档不脏）；
    space="srgb" 回退到旧的逐通道线性插值（仅当调用方确需精确直通色时使用）。
    """
    ra, rb = _tuple(a), _tuple(b)
    t = max(0.0, min(1.0, t))
    if t <= 0.0:
        return a
    if t >= 1.0:
        return b
    if space == "srgb":
        return _hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))
    La, aa, ba = _rgb_to_oklab(ra)
    Lb, ab, bb = _rgb_to_oklab(rb)
    L = La + (Lb - La) * t
    am = aa + (ab - aa) * t
    bm = ba + (bb - ba) * t
    return _hex(_oklab_to_rgb(L, am, bm))


def mix_oklab(colors: list, weights: list | None = None) -> str:
    """多色在 OKLab 空间的加权混合（weights 归一化；缺省等权）。用于推导
    更干净的中性/中间档色。"""
    if not colors:
        return "#000000"
    if weights is None:
        weights = [1.0] * len(colors)
    total = sum(max(0.0, w) for w in weights) or 1.0
    L = a = b = 0.0
    for c, w in zip(colors, weights):
        Lc, ac, bc = _rgb_to_oklab(_tuple(c))
        w = max(0.0, w) / total
        L += Lc * w
        a += ac * w
        b += bc * w
    return _hex(_oklab_to_rgb(L, a, b))


def luminance(hex_color: str) -> float:
    def ch(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (_tuple(hex_color))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# 辅助文字角色：语义上是注记/来源/轴标签，可读性门槛按「非正文」处理（3:1），
# 不参与正文级 4.5:1 判定。guard 的行长豁免与渲染层对比度分级共用这一份名单。
AUX_TEXT_ROLES = frozenset({"source", "method", "metadata", "caption", "legend", "axis",
                            "data_label", "annotation", "page_number"})


def text_role(element: dict) -> str:
    return str((element or {}).get("role") or "")


def is_aux_text(element: dict) -> bool:
    return text_role(element) in AUX_TEXT_ROLES


def spec_fingerprint(spec: dict) -> str:
    """spec 的规范化内容指纹（16 hex）。

    报告用它自证来源：QA / Art Critic 各盖一次，Release Manifest 核对后才会承认
    其中的 PASS。没有一致指纹的「合格」不能进入发布判定。
    """
    import hashlib
    import json
    try:
        canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:                       # 循环引用/不可序列化：退化到键集合，仍可辨版
        keys = sorted(str(k) for k in (spec or {}).keys())
        slides = (spec or {}).get("slides") or []
        canonical = repr((keys, len(slides), [str(s.get("id")) for s in slides if isinstance(s, dict)]))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# 跨层共享判定（v2.4 Director 升级：guard / qa / art_critic 在此收敛为单一口径）
#
# 纯函数：只收显式参数，不读 spec 结构、不读主题 —— 因此 Layer 0 可承载。
# 上层只保留「消息文案 + 严重级别」的呈现权，不再各自实现一遍判定逻辑。
# 同一事实在两处判出两种结论的口径漂移，只能在这里修，不在上层打补丁。
# --------------------------------------------------------------------------
BACKGROUND_LAYERS = frozenset({"background", "backdrop"})
ROUNDED_SHAPES = frozenset({"rounded_rect", "round_rect"})


def is_background_declared(element: dict) -> bool:
    """元素是否**声明**为背景层（只读意图，不判断资格）。"""
    e = element or {}
    return (str(e.get("layer", "")).lower() in BACKGROUND_LAYERS
            or str(e.get("role", "")).lower() in BACKGROUND_LAYERS)


def bg_overlay_opacity(element: dict) -> tuple[float | None, str | None]:
    """背景层内容保护层的不透明度 → (opacity, 缺失原因)。

    按 overlay → content_protection.overlay → content_protection.scrim 的顺序取
    第一个可用声明；非空字符串简写视为完全不透明 1.0。
    返回 (None, "missing") 表示未声明；(None, "unparsable") 表示声明了但解析不出
    数值 —— fail-closed：解析不出即视为无保护（guard 与 art_critic 口径统一，
    此前 critic 会按 1.0 放行）。
    """
    e = element or {}
    srcs = [e.get("overlay")]
    cp = e.get("content_protection")
    if isinstance(cp, dict):
        srcs.append(cp.get("overlay"))
        srcs.append(cp.get("scrim"))
    for src in srcs:
        if src is None:
            continue
        if isinstance(src, str):
            if src.strip():
                return 1.0, None
            continue
        if isinstance(src, dict):
            try:
                return float(src.get("opacity", 1.0)), None
            except (TypeError, ValueError):
                return None, "unparsable"
    return None, "missing"


def bg_coverage(element: dict, cw: float, ch: float) -> float:
    """元素面积占画布比例（0–1，非法几何按 0）。背景层资格的第一道门：
    覆盖不够的「背景层」只是内容对象，不享受任何豁免。"""
    try:
        area = (float((element or {}).get("width", 0) or 0)
                * float((element or {}).get("height", 0) or 0))
    except (TypeError, ValueError):
        return 0.0
    try:
        denom = float(cw or 0) * float(ch or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, area / denom) if denom > 0 else 0.0


def rounded_containers(elements) -> list[dict]:
    """真正的圆角容器：type == "shape" 且 shape 为 rounded_rect / round_rect。

    v2.4 收敛：guard 预检曾把任何带 shape 属性的元素都计入，与 critic 口径不一致；
    非 shape 元素渲染出来并不是容器，计入只是误报。现统一按「渲染出来是容器」计数。
    """
    return [e for e in (elements or [])
            if isinstance(e, dict) and e.get("type") == "shape"
            and e.get("shape") in ROUNDED_SHAPES]


def text_contrast_verdict(render_page: dict | None, fail: float = 3.0,
                          warn: float = 4.5) -> dict:
    """渲染实测「文字 vs 其下方像素」的最坏对比度 verdict。

    返回 {"level", "value", "worst"}：level ∈ fail / soft / pass / unknown；
    value 是触发该结论的对比度；worst 是正文级最坏框记录（id/字色/实测底色）。
    fail 线看含注记的最坏值（注记允许低于 AA 但不能低于 3:1 —— 看不见就是看不见）；
    soft / pass 看正文级最坏值。qa.py 与 art_critic.py 共用：同一页、同一证据，
    永远得出同一结论（此前两处各写一遍 min() 逻辑，行为一致但无法保证永远一致）。
    """
    page = render_page or {}

    def _f(v):
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    reading = _f(page.get("text_contrast_min"))
    worst_all = _f(page.get("text_contrast_all_min"))
    worst = page.get("text_contrast_worst") or {}
    hard = (reading if worst_all is None
            else (min(reading, worst_all) if reading is not None else worst_all))
    if hard is not None and hard < fail:
        return {"level": "fail", "value": hard, "worst": worst}
    if reading is not None and reading < warn:
        return {"level": "soft", "value": reading, "worst": worst}
    if reading is not None:
        return {"level": "pass", "value": reading, "worst": worst}
    return {"level": "unknown", "value": None, "worst": worst}


def with_alpha(hex_color: str, alpha: float) -> str:
    """生成 #RRGGBBAA（供色板推导使用）。"""
    a = max(0.0, min(1.0, alpha))
    return f"{_hex(_tuple(hex_color))}{format(int(round(a * 255)), '02X')}"


def parse_token(value):
    """-> (RGBColor | None, alpha | None)；支持 #RGB / #RRGGBB / #RRGGBBAA / none。"""
    if value is None:
        return None, None
    t = str(value).strip()
    if t.lower() in ("none", "transparent"):
        return None, None
    if not t.startswith("#"):
        return None, None
    h = t[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 8:
        try:
            return _p()["RGBColor"].from_string(h[0:6].upper()), int(h[6:8], 16) / 255.0
        except Exception:
            return None, None
    if len(h) == 6:
        try:
            return _p()["RGBColor"].from_string(h.upper()), None
        except Exception:
            return None, None
    return None, None


def derive_tokens(base: dict) -> dict:
    """
    从基础色**机械推导**完整色阶系统 —— 与具体主题无关，任何主题传入都成立。

    这是视觉层次的主要来源：轨道、细线、弱化层、面板微差、色阶、系列色，
    全部由 5 个基础色推导，用透明度制造纵深（而非阴影）。
    """
    def hx(key, fallback=None):
        v = base.get(key) or fallback
        return v if isinstance(v, str) and v.startswith("#") else None

    bg = hx("background") or hx("paper")
    surface = hx("surface") or bg
    primary = hx("primary")
    secondary = hx("secondary") or primary
    accent = hx("accent") or secondary
    premium = hx("premium") or hx("optional") or accent
    ink = hx("ink") or primary
    muted = hx("muted") or secondary
    if not (bg and primary):
        return {}

    out = {}

    def put(key, color, alpha=None):
        if not color:
            return
        out[key] = with_alpha(color, alpha) if alpha is not None else color

    # 层叠表面：与背景拉开极微弱的明度差，形成面板层次
    put("panel", blend(bg, primary, 0.06))
    put("panel_strong", blend(bg, primary, 0.13))
    put("panel_soft", blend(bg, primary, 0.03))
    put("tint", blend(bg, accent, 0.14))

    # 线条 / 轨道 / 弱化层（靠透明度制造层次，而非阴影）
    put("hairline", muted, 0.28)
    put("rule", ink, 0.18)
    put("track", muted, 0.20)
    put("faint", muted, 0.42)
    put("veil", bg, 0.82)
    # muted_soft：浅底上 alpha 会把浅灰推近背景（不可读）；
    # 改为「朝文字色方向微调」，跨主题都保证可读。
    if luminance(bg) > 0.5:  # 浅色主题：muted 向 primary 靠拢（变深）
        put("muted_soft", blend(muted, primary, 0.25))
    else:                    # 深色主题：muted 向 ink 靠拢（变浅）
        put("muted_soft", blend(muted, ink, 0.20))

    # 色阶：单色相明度阶梯（OS §21.1「顺序数据用同一色相的明度阶梯」）。
    # 以 accent 为基相，由浅入深 5 档；灰度打印下仍靠明度差可辨。
    # 中间档（ramp1 / ramp2）按背景明度向更「聚焦」方向拉：
    #   - 浅色主题：ramp1/ramp2 加重（往 ink 靠），让浅底上的中档色块不漂浮
    #   - 深色主题：ramp1/ramp2 提亮（往 bg/inverse 靠），让深底上的中档有重量
    # 末档（ramp5）保持向 ink 推，跨主题稳定。设计意图：让 5 档色阶在
    # 任何主题下「相邻明度差都 ≥ 1.5 个 JND」，避免「看像同一个色」。
    if luminance(bg) > 0.5:
        # 浅色主题：浅档用 accent 自重而非 blend(bg)，避免被背景稀释
        ramp = [blend(bg, accent, 0.40), blend(bg, accent, 0.68), accent,
                blend(accent, ink, 0.42), blend(accent, ink, 0.72)]
    else:
        # 深色主题：浅档往浅色拉（用 ink 提亮而非 bg，避免与背景重合）
        ramp = [blend(bg, accent, 0.22), blend(bg, accent, 0.48), accent,
                blend(accent, ink, 0.42), blend(accent, ink, 0.72)]
    for i, v in enumerate(ramp, 1):
        put(f"ramp{i}", v)

    # 多分类系列色：全部分布在主题信号色及其深浅变体上——
    # 不再用 ink/muted 当填充（黑灰块既沉重又与文字争夺语义）。
    # 深浅目标随背景明度翻转：浅底=深档向 ink、浅档向 bg；
    # 深底=深档向纯黑、浅档向 ink（保证任何主题下相邻系列明度可分）。
    light_bg = luminance(bg) > 0.5
    deep_target = ink if light_bg else "#000000"
    tint_target = bg if light_bg else ink
    series = [
        accent,                              # 1 主信号
        premium,                             # 2 次信号（异色相）
        blend(accent, deep_target, 0.42),    # 3 主信号加深
        blend(premium, deep_target, 0.42),   # 4 次信号加深
        blend(accent, tint_target, 0.45),    # 5 主信号提亮
        blend(premium, tint_target, 0.45),   # 6 次信号提亮
    ]
    for i, v in enumerate(series, 1):
        put(f"series{i}", v)

    # 特殊表面上的文字色：按对比度自动择优
    pool = [c for c in (bg, surface, primary, secondary, accent, ink) if c]
    dark = hx("dark_surface") or min(pool, key=luminance)
    put("dark_surface", dark)
    put("on_dark", max(pool, key=lambda c: contrast(c, dark)))
    candidates = [c for c in (ink, bg, "#FFFFFF", "#111111") if c]
    put("on_accent", max(candidates, key=lambda c: contrast(c, accent)))

    # 填充色上的文字色：按对比度自动择优，避免「白底白字/黑底黑字」
    # （之前 process_flow 第一个节点在 obsidian 下 fill=primary=#F1F0EB
    #   而 text=ink=#F1F0EB，白底白字不可见。）
    for role, surface in (("on_primary", primary), ("on_secondary", secondary)):
        if not surface: continue
        put(role, max(pool, key=lambda c: contrast(c, surface)))
    return out


# --------------------------------------------------------------------------
# 填充 / 描边（支持透明度与渐变）
# --------------------------------------------------------------------------
def _append_alpha(clr_el, alpha: float) -> None:
    qn = _p()["qn"]
    for old in clr_el.findall(qn("a:alpha")):
        clr_el.remove(old)
    el = clr_el.makeelement(qn("a:alpha"), {"val": str(int(round(alpha * 100000)))})
    clr_el.append(el)


def solid_fill(fill, color, alpha=None) -> None:
    fill.solid()
    fill.fore_color.rgb = color
    if alpha is not None and alpha < 1.0:
        xfill = fill.fore_color._xFill
        clr = xfill.find(_p()["qn"]("a:srgbClr")) if xfill is not None else None
        if clr is not None:
            _append_alpha(clr, alpha)


def _insert_fill_in_order(parent, fill_el) -> None:
    """
    按 OOXML 模式在正确位置插入 fill 元素。

    模式要求：fill 出现在 xfrm/geometry 之后、effects/3D 之前。
    对于 `<p:bgPr>` 没有 pre-fill 子元素，所以插在最前。
    对于 `<p:spPr>` 需要跳过 xfrm/prstGeom/custGeom。
    这样才能避免「effectLst 排在 gradFill 前面」导致的渲染器忽略渐变。
    """
    qn = _p()["qn"]
    pre_fill = {qn("a:xfrm"), qn("a:custGeom"), qn("a:prstGeom")}
    for i, child in enumerate(parent):
        if child.tag in pre_fill:
            continue
        parent.insert(i, fill_el)
        return
    parent.append(fill_el)


def gradient_fill(fill, stops, angle=90.0) -> None:
    """
    stops: [(pos 0–1, "#RRGGBB", alpha|None), ...]  至少 2 个
    angle: 0 = 左→右，90 = 上→下
    """
    parts = []
    for pos, color, alpha in stops:
        rgb = parse_token(color)[0]
        if rgb is None:
            continue
        alpha_xml = ""
        if alpha is not None and alpha < 1.0:
            alpha_xml = f'<a:alpha val="{int(round(alpha * 100000))}"/>'
        parts.append(
            f'<a:gs pos="{int(round(max(0.0, min(1.0, pos)) * 100000))}">'
            f'<a:srgbClr val="{rgb}">{alpha_xml}</a:srgbClr></a:gs>')
    if len(parts) < 2:
        solid_fill(fill, parse_token(stops[0][1])[0] or fallback_ink(),
                   stops[0][2] if len(stops[0]) > 2 else None)
        return
    P = _p()
    xml = (f'<a:gradFill {P["nsdecls"]("a")} rotWithShape="1">'
           f'<a:gsLst>{"".join(parts)}</a:gsLst>'
           f'<a:lin ang="{int(round(angle * 60000))}" scaled="1"/>'
           f'</a:gradFill>')
    spPr = fill._xPr
    for tag in ("a:noFill", "a:solidFill", "a:gradFill", "a:blipFill",
                "a:pattFill", "a:grpFill"):
        for el in spPr.findall(P["qn"](tag)):
            spPr.remove(el)
    _insert_fill_in_order(spPr, P["parse_xml"](xml))


def stroke_color(line, color, alpha=None, width=None) -> None:
    line.color.rgb = color
    if alpha is not None and alpha < 1.0:
        xfill = line.color._xFill
        clr = xfill.find(_p()["qn"]("a:srgbClr")) if xfill is not None else None
        if clr is not None:
            _append_alpha(clr, alpha)
    if width is not None:
        line.width = _p()["Emu"](emu(width))


def no_line(line) -> None:
    line.fill.background()


# --------------------------------------------------------------------------
# 文本
# --------------------------------------------------------------------------
def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x3000 <= o <= 0x9FFF) or (0xFF00 <= o <= 0xFFEF) or (0x3040 <= o <= 0x30FF)


# 中西混排间隙：CJK 与拉丁/数字紧贴是中文排版的廉价感来源。在脚本切换处
# 插入 U+2009 THIN SPACE（≈1/5 em），作为渲染层的排版打磨——不改变作者的
# spec 文本（Guard 仍按原文本测行长），只改变最终落到页面上的视觉效果。
HAIR_SPACE = "\u2009"


def _is_latin_alnum(ch: str) -> bool:
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ("0" <= ch <= "9")


def insert_script_gaps(text: str) -> str:
    """在 CJK 与拉丁字母/数字的边界插入细空格；空格与标点不触发。"""
    if not text or len(text) < 2:
        return text
    out = []
    for i, ch in enumerate(text):
        if i > 0:
            prev = text[i - 1]
            if (_is_latin_alnum(ch) and is_cjk(prev)) or \
                    (_is_latin_alnum(prev) and is_cjk(ch)):
                out.append(HAIR_SPACE)
        out.append(ch)
    return "".join(out)


def split_runs(text: str):
    """按 CJK / 拉丁切分，保证中英文混排各自使用正确字体。"""
    runs = []
    cur = text[0]
    cur_cjk = is_cjk(cur)
    for ch in text[1:]:
        c = is_cjk(ch)
        if c == cur_cjk:
            cur += ch
        else:
            runs.append((cur, cur_cjk))
            cur, cur_cjk = ch, c
    runs.append((cur, cur_cjk))
    return runs


def text_units(value: str) -> float:
    """文本容量估算：CJK 字符计 1.0（全角方块），拉丁字符计 0.55。
    0.55 取自 Helvetica / Inter 等常见无衬线字体在 14–20px 时
    拉丁字母平均宽度与 CJK 字符宽度的经验比值（0.50–0.58 区间的中位）。
    修正点：原 0.53 在大字号下偏低估，密集正文的容量估算易「乐观」，
    表现为 Guard 通过、渲染溢出。把 0.55 设为默认后，估算与渲染
    可读性复核的对齐误差更小（参见 design-intelligence.md Typography
    Engine 的"回退顺序"）。
    中西混排细空格（HAIR_SPACE）计 0.2，使插入脚本间隙后的估算与渲染一致。"""
    total = 0.0
    for c in value:
        if c == HAIR_SPACE:
            total += 0.2
        elif ord(c) > 127:
            total += 1.0
        else:
            total += 0.55
    return total


def estimate_lines(text: str, width: float, size: float, wrap: bool = True) -> int:
    if not text or not wrap:
        return 1
    usable = max(width / max(size, 0.01), 1)
    return max(1, math.ceil(text_units(text) / usable))


def set_run_font(run, latin_family, cjk_family, size_pt, color, bold=False,
                 italic=False, spacing=None, alpha=None, uppercase=False):
    """
    spacing: 字距（pt，转换为 1/100 pt）
    alpha  : 文字透明度（用于弱化文字，而非换色）
    """
    text = run.text or ""
    if uppercase:
        text = text.upper()
        run.text = text
    P = _p()
    qn = P["qn"]
    run.font.size = P["Pt"](size_pt)
    run.font.bold = bool(bold)
    run.font.italic = bool(italic)
    if color is not None:
        run.font.color.rgb = color
    run.font.name = latin_family
    rPr = run._r.get_or_add_rPr()
    if spacing:
        rPr.set("spc", str(int(round(float(spacing) * 100))))
    if alpha is not None and alpha < 1.0:
        sf = rPr.find(qn("a:solidFill"))
        if sf is None:
            sf = rPr.makeelement(qn("a:solidFill"), {})
            rPr.append(sf)
            sf.append(rPr.makeelement(qn("a:srgbClr"), {"val": str(color or fallback_ink())}))
        clr = sf.find(qn("a:srgbClr"))
        if clr is not None:
            _append_alpha(clr, alpha)
    for tag, fam in (("a:ea", cjk_family), ("a:cs", cjk_family)):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", fam)


def set_para_font(p, latin, cn, size_pt, color, bold, spacing=None, alpha=None):
    for run in p.runs:
        set_run_font(run, latin, cn, size_pt, color, bold, False, spacing, alpha, False)
    if not p.runs:
        run = p.add_run()
        run.text = ""
        set_run_font(run, latin, cn, size_pt, color, bold, False, spacing, alpha, False)


# --------------------------------------------------------------------------
# 层间契约
# --------------------------------------------------------------------------
class RenderContext:
    """
    所有绘制层读取主题的**唯一**入口。

    主题（spec.theme）在此归一化，并机械推导出完整色阶；
    elements / charts 只通过 ctx 取色取字。
    因此：换主题只改变 ctx 的内容，不触及任何绘制层实现。
    """

    def __init__(self, theme: dict | None = None, canvas: dict | None = None):
        theme = dict(theme or {})
        canvas = dict(canvas or {})
        self.theme = theme
        base = dict(theme.get("colors") or {})
        # 派生色阶在前，显式声明优先（调用方永远可以覆盖任何派生结果）
        self.colors = {**derive_tokens(base), **base}
        self.fonts = dict(theme.get("fonts") or {})
        self.canvas = {
            "width": float(canvas.get("width", DEFAULT_WIDTH)),
            "height": float(canvas.get("height", DEFAULT_HEIGHT)),
        }
        self.warnings: list[str] = []

    # -- 颜色 -------------------------------------------------------------
    def paint(self, value):
        """-> (RGBColor | None, alpha | None)"""
        token = self.colors.get(value, value)
        return parse_token(token)

    def color(self, value):
        return self.paint(value)[0]

    def text_color(self, value=None):
        c = self.color(value)
        if c is not None:
            return c
        for role in (self.theme.get("text_default"), "ink", "primary"):
            if role:
                c = self.color(role)
                if c is not None:
                    return c
        return fallback_ink()

    def paint_or(self, value, fallback_role=None):
        """取色，取不到时回落到某个角色。"""
        c, a = self.paint(value)
        if c is None and fallback_role:
            c, a = self.paint(fallback_role)
        return c, a

    def series_color(self, index: int):
        """按顺序取系列色（循环使用）。"""
        return self.color(f"series{(index % 6) + 1}")

    # -- 图表角色色（Chart Color Role System）─────────────────────────
    # 图表不写死色值，声明语义角色：primary=主叙事 / secondary=对比 /
    # neutral=语境 / accent=高亮 / negative=风险。角色由 theme.chart_palette
    # 映射到具体色——主题换了，spec 的图表语义不变、色值随主题派生。
    # 解析链：chart_palette[role] → 旧扁平键（chart_primary 等，向后兼容）→
    # colors token。negative 未声明时用通用风险红兜底并告警（最后手段，
    # 不是设计建议——主题作者应显式派生风险色）。
    _CHART_ROLE_FALLBACK = {
        "primary": ("chart_primary", "primary"),
        "secondary": ("chart_secondary", "secondary"),
        "neutral": ("chart_muted", "secondary"),
        "accent": ("accent",),
        "negative": ("negative",),
    }
    _NEGATIVE_FALLBACK = "#B3261E"   # 通用风险红：仅主题未声明 negative 时兜底

    def chart_role(self, role: str):
        """语义角色 → 具体色（RGBColor | None）。角色不认识时返回 None。"""
        role = str(role or "").strip().lower()
        palette = self.theme.get("chart_palette")
        chain = []
        if isinstance(palette, dict) and palette.get(role):
            chain.append(palette[role])
        chain += list(self._CHART_ROLE_FALLBACK.get(role, ()))
        for ref in chain:
            if not ref:
                continue
            c = self.color(ref)
            if c is not None:
                return c
        if role == "negative":
            msg = ("theme 未声明 negative 角色（chart_palette.negative 或 colors.negative），"
                   "负值用通用风险红兜底——请为主题显式派生一个风险色")
            if msg not in self.warnings:
                self.warnings.append(msg)
            return self.color(self._NEGATIVE_FALLBACK)
        return None

    def ramp_color(self, index: int):
        return self.color(f"ramp{max(1, min(5, index + 1))}")

    def auto_text_for(self, fill_ref):
        """
        给定填充色（角色名 / #HEX / RGBColor），从主题池中选对比度最高的文字色。
        这比 on_primary/on_secondary 更稳——后者只对单一角色计算，
        而 chart_secondary 实际可能映射到 accent，深浅与 secondary 相反。
        """
        if fill_ref is None:
            return self.text_color()
        color = fill_ref if color_to_hex(fill_ref) else (self.paint(fill_ref)[0])
        fill_hex = color_to_hex(color)
        if not fill_hex:
            return self.text_color()
        candidates = []
        for role in ("ink", "on_dark", "primary", "background", "surface", "muted", "secondary", "accent"):
            c = self.color(role)
            if c:
                hex_val = color_to_hex(c)
                if hex_val:
                    candidates.append((role, hex_val))
        candidates.append(("white", "FFFFFF"))
        candidates.append(("black", "111111"))
        best_role, best_c = None, 0.0
        for role, hex_val in candidates:
            try:
                k = contrast("#" + hex_val, "#" + fill_hex)
            except Exception:
                continue
            if k > best_c:
                best_c, best_role = k, role
        if best_role in ("white", "black"):
            rgb = _p()["RGBColor"]
            return rgb(0xFF, 0xFF, 0xFF) if best_role == "white" else rgb(0x11, 0x11, 0x11)
        return self.color(best_role) or self.text_color()

    # -- 字体 -------------------------------------------------------------
    def families(self, element: dict):
        cn = self.fonts.get("cn") or FALLBACK_CN
        latin = self.fonts.get("latin") or FALLBACK_LATIN
        f = element.get("font")
        if isinstance(f, str) and f:
            fam = self.fonts.get(f, f)
            if isinstance(fam, str) and fam:
                latin = fam
        if element.get("family"):
            latin = str(element["family"])
        return cn, latin

    # -- 几何 -------------------------------------------------------------
    def bounds(self, element: dict):
        x = float(element["x"])
        y = float(element["y"])
        w = float(element["width"])
        h = float(element["height"])
        return x, y, w, h

    def warn(self, message: str) -> None:
        self.warnings.append(message)
