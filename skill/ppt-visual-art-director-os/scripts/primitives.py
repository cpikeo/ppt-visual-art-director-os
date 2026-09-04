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

from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml import parse_xml
from pptx.oxml.ns import qn, nsdecls

# 1280 design px -> 13.333 in (12192000 EMU)
PX_TO_EMU = 9525
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1280, 720

ALIGN = {
    None: PP_ALIGN.LEFT, "left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER,
    "right": PP_ALIGN.RIGHT, "justify": PP_ALIGN.JUSTIFY,
}
ANCHOR = {
    None: MSO_ANCHOR.TOP, "top": MSO_ANCHOR.TOP,
    "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM,
}
# 渲染级安全回落（不是设计观点）：主题未声明字体时保证文件可渲染。
FALLBACK_CN = "Microsoft YaHei"
FALLBACK_LATIN = "Arial"
FALLBACK_INK = RGBColor(0x20, 0x20, 0x20)


def emu(px) -> int:
    return int(round(float(px) * PX_TO_EMU))


def pt(px) -> Pt:
    # design px -> points（1 design px = 0.75 pt）
    return Pt(float(px) * 0.75)


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


def blend(a: str, b: str, t: float) -> str:
    ra, rb = _tuple(a), _tuple(b)
    t = max(0.0, min(1.0, t))
    return _hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


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
            return RGBColor.from_string(h[0:6].upper()), int(h[6:8], 16) / 255.0
        except Exception:
            return None, None
    if len(h) == 6:
        try:
            return RGBColor.from_string(h.upper()), None
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
    ramp = [blend(bg, accent, 0.32), blend(bg, accent, 0.58), accent,
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
    for old in clr_el.findall(qn("a:alpha")):
        clr_el.remove(old)
    el = clr_el.makeelement(qn("a:alpha"), {"val": str(int(round(alpha * 100000)))})
    clr_el.append(el)


def solid_fill(fill, color: RGBColor, alpha=None) -> None:
    fill.solid()
    fill.fore_color.rgb = color
    if alpha is not None and alpha < 1.0:
        xfill = fill.fore_color._xFill
        clr = xfill.find(qn("a:srgbClr")) if xfill is not None else None
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
        solid_fill(fill, parse_token(stops[0][1])[0] or FALLBACK_INK,
                   stops[0][2] if len(stops[0]) > 2 else None)
        return
    xml = (f'<a:gradFill {nsdecls("a")} rotWithShape="1">'
           f'<a:gsLst>{"".join(parts)}</a:gsLst>'
           f'<a:lin ang="{int(round(angle * 60000))}" scaled="1"/>'
           f'</a:gradFill>')
    spPr = fill._xPr
    for tag in ("a:noFill", "a:solidFill", "a:gradFill", "a:blipFill",
                "a:pattFill", "a:grpFill"):
        for el in spPr.findall(qn(tag)):
            spPr.remove(el)
    _insert_fill_in_order(spPr, parse_xml(xml))


def stroke_color(line, color: RGBColor, alpha=None, width=None) -> None:
    line.color.rgb = color
    if alpha is not None and alpha < 1.0:
        xfill = line.color._xFill
        clr = xfill.find(qn("a:srgbClr")) if xfill is not None else None
        if clr is not None:
            _append_alpha(clr, alpha)
    if width is not None:
        line.width = Emu(emu(width))


def no_line(line) -> None:
    line.fill.background()


# --------------------------------------------------------------------------
# 文本
# --------------------------------------------------------------------------
def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x3000 <= o <= 0x9FFF) or (0xFF00 <= o <= 0xFFEF) or (0x3040 <= o <= 0x30FF)


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
    """文本容量估算：CJK 计 1.0，拉丁计 0.53。"""
    return sum(1.0 if ord(c) > 127 else 0.53 for c in value)


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
    run.font.size = Pt(size_pt)
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
            sf.append(rPr.makeelement(qn("a:srgbClr"), {"val": str(color or FALLBACK_INK)}))
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

    def text_color(self, value=None) -> RGBColor:
        c = self.color(value)
        if c is not None:
            return c
        for role in (self.theme.get("text_default"), "ink", "primary"):
            if role:
                c = self.color(role)
                if c is not None:
                    return c
        return FALLBACK_INK

    def paint_or(self, value, fallback_role=None):
        """取色，取不到时回落到某个角色。"""
        c, a = self.paint(value)
        if c is None and fallback_role:
            c, a = self.paint(fallback_role)
        return c, a

    def series_color(self, index: int):
        """按顺序取系列色（循环使用）。"""
        return self.color(f"series{(index % 6) + 1}")

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
        if hasattr(fill_ref, "__class__") and fill_ref.__class__.__name__ == "RGBColor":
            try:
                fill_hex = "".join(f"{c:02X}" for c in fill_ref)
            except Exception:
                return self.text_color()
        else:
            color, _ = self.paint(fill_ref)
            if color is None:
                return self.text_color()
            try:
                fill_hex = "".join(f"{c:02X}" for c in color)
            except Exception:
                return self.text_color()
        candidates = []
        for role in ("ink", "on_dark", "primary", "background", "surface", "muted", "secondary", "accent"):
            c = self.color(role)
            if c:
                try:
                    candidates.append((role, "".join(f"{v:02X}" for v in c)))
                except Exception:
                    pass
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
            from pptx.dml.color import RGBColor
            return RGBColor(0xFF, 0xFF, 0xFF) if best_role == "white" else RGBColor(0x11, 0x11, 0x11)
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
