# -*- coding: utf-8 -*-
"""Fast, deterministic direction preview for VAO.

Ghost is not an Office renderer. It is a high-fidelity *art-direction* preview:
real text, real local images, typography hierarchy, color roles, charts and
layer order are represented with PIL alone — no office suite, no browser.
Rendering is supersampled and downsampled once so thin rules and rounded forms
remain clean at contact-sheet size.  It never invents decorative content.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from primitives import (CHART_KINDS, RenderContext, DEFAULT_WIDTH, DEFAULT_HEIGHT,
                        highlight_index)


_FONT_CACHE: dict[tuple[str, int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
_FONT_CANDIDATES = {
    "latin": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/Library/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ),
    "cjk": (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/msyh.ttc",
    ),
}


def _is_cjk(ch: str) -> bool:
    return bool(ch and ("\u2e80" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff"))


def _has_cjk(text: str) -> bool:
    return any(_is_cjk(c) for c in str(text))


def _font(size: float, *, cjk: bool = False, bold: bool = False) -> ImageFont.ImageFont:
    px = max(1, int(round(size)))
    key = ("cjk" if cjk else "latin", px, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = list(_FONT_CANDIDATES["cjk" if cjk else "latin"])
    if bold and not cjk:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ] + candidates
    loaded: ImageFont.ImageFont | None = None
    for name in candidates:
        try:
            if Path(name).exists():
                loaded = ImageFont.truetype(name, px)
                break
        except (OSError, ValueError):
            continue
    if loaded is None:
        loaded = ImageFont.load_default()
    _FONT_CACHE[key] = loaded
    return loaded


def _rgb(ctx: RenderContext, token, fallback=(128, 128, 128)) -> tuple[int, int, int]:
    if token is None:
        token = "secondary"
    if isinstance(token, dict):
        token = token.get("color") or token.get("value") or "secondary"
    if isinstance(token, (tuple, list)) and len(token) >= 3:
        return tuple(max(0, min(255, int(v))) for v in token[:3])
    try:
        rgb, _ = ctx.paint(token)
    except (TypeError, ValueError):
        rgb = None
    return tuple(int(v) for v in rgb) if rgb else fallback


def _rgba(ctx: RenderContext, token, opacity: float | None = None,
          fallback=(128, 128, 128)) -> tuple[int, int, int, int]:
    rgb = _rgb(ctx, token, fallback)
    alpha = 255 if opacity is None else max(0, min(255, int(float(opacity) * 255)))
    return (*rgb, alpha)


def _scale_box(e: dict, scale: float) -> tuple[int, int, int, int]:
    return tuple(int(round(float(e.get(k, 0) or 0) * scale))
                 for k in ("x", "y", "width", "height"))


def _resolve_color(ctx: RenderContext, token) -> tuple[int, int, int] | None:
    if token is None:
        return None
    return _rgb(ctx, token, fallback=(0, 0, 0))


def _draw_gradient(img: Image.Image, box: tuple[int, int, int, int], ctx: RenderContext,
                   value: Any, scale: float) -> None:
    x, y, w, h = box
    stops = value.get("stops") if isinstance(value, dict) else None
    colors = []
    for stop in stops or []:
        token = stop.get("color") if isinstance(stop, dict) else (stop[1] if len(stop) > 1 else None)
        color = _resolve_color(ctx, token)
        if color:
            colors.append(color)
    if len(colors) < 2:
        return
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    for iy in range(max(1, h)):
        t = iy / max(1, h - 1)
        c = tuple(int(colors[0][i] + (colors[-1][i] - colors[0][i]) * t) for i in range(3))
        d.line((x, y + iy, x + w, y + iy), fill=(*c, 255), width=1)
    img.alpha_composite(overlay)


def _fill(img: Image.Image, box: tuple[int, int, int, int], ctx: RenderContext,
          value: Any, radius: int = 0) -> None:
    if not value:
        return
    if isinstance(value, dict) and str(value.get("type", "")).lower() == "gradient":
        _draw_gradient(img, box, ctx, value, 1.0)
        return
    token = value.get("color") if isinstance(value, dict) else value
    opacity = value.get("opacity") if isinstance(value, dict) else None
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    xy = [box[0], box[1], box[0] + box[2], box[1] + box[3]]
    color = _rgba(ctx, token, opacity)
    if radius:
        d.rounded_rectangle(xy, radius=radius, fill=color)
    else:
        d.rectangle(xy, fill=color)
    img.alpha_composite(overlay)


def _wrap_lines(text: str, font, width: int) -> list[str]:
    """Wrap by measured width; keep Latin words intact and CJK rhythm clean."""
    limit = max(1, width)
    result: list[str] = []
    for raw in str(text).split("\n"):
        if not raw:
            result.append("")
            continue
        if not _has_cjk(raw):
            words = raw.split()
            line = ""
            for word in words:
                candidate = word if not line else f"{line} {word}"
                if line and font.getlength(candidate) > limit:
                    result.append(line)
                    line = word
                elif not line and font.getlength(candidate) > limit:
                    # A single long token is the only case where Latin may
                    # break; split it at measured glyph boundaries.
                    for ch in word:
                        if line and font.getlength(line + ch) > limit:
                            result.append(line)
                            line = ch
                        else:
                            line += ch
                else:
                    line = candidate
            result.append(line)
            continue
        line = ""
        for ch in raw:
            candidate = line + ch
            if line and font.getlength(candidate) > limit:
                result.append(line.rstrip())
                line = ch
            else:
                line = candidate
        result.append(line)
    return result or [""]


def _draw_text(img: Image.Image, e: dict, ctx: RenderContext, scale: float) -> None:
    x, y, w, h = _scale_box(e, scale)
    if w <= 0 or h <= 0:
        return
    # 文本框底色（标签条 / 染色列）：预览不画，就等于和产物说两件事。
    if e.get("fill"):
        _fill(img, (x, y, w, h), ctx, e["fill"], radius=0)
    text = str(e.get("text", ""))
    if bool(e.get("uppercase")):
        text = text.upper()
    pad = int(round(float(e.get("padding", 0) or 0) * scale))
    size = float(e.get("size", 18) or 18) * scale
    font = _font(size, cjk=_has_cjk(text), bold=bool(e.get("bold")))
    color = _rgba(ctx, e.get("color") or "ink", e.get("opacity"), fallback=(24, 24, 24))
    lines = _wrap_lines(text, font, w - 2 * pad) if bool(e.get("wrap", True)) else text.split("\n")
    max_lines = e.get("max_lines")
    if isinstance(max_lines, int) and max_lines > 0:
        lines = lines[:max_lines]
    line_height = float(e.get("line_height", 1.35) or 1.35) * size
    total_h = max(1, len(lines)) * line_height
    anchor = str(e.get("anchor", "top")).lower()
    if anchor in {"middle", "center"}:
        cy = y + (h - total_h) / 2
    elif anchor in {"bottom", "end"}:
        cy = y + h - total_h
    else:
        cy = y + pad
    align = str(e.get("align", "left")).lower()
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        if align in {"center", "middle"}:
            tx = x + (w - tw) / 2
        elif align in {"right", "end"}:
            tx = x + w - pad - tw
        else:
            tx = x + pad
        d.text((int(tx), int(cy)), line, font=font, fill=color)
        cy += line_height
    img.alpha_composite(overlay)


def _draw_shape(img: Image.Image, e: dict, ctx: RenderContext, scale: float) -> None:
    x, y, w, h = _scale_box(e, scale)
    shape = str(e.get("shape", "rect")).lower()

    if shape in ("line", "arrow"):
        # 线是一维对象：compiler 走 add_connector，从 (x,y) 画到 (x+w, y+h)，
        # 所以水平线 height=0 是**正确写法**。此前这里被 `w<=0 or h<=0` 提前 return——
        # 产物里有线、预览里没有，作者看不到自己刚画的分割线，只好退回画卡片。
        # 预览宽容度必须 = 交付链：compiler 画得出来的，预览就得画。
        stroke = e.get("stroke") or e.get("fill") or "hairline"
        color = _rgba(ctx, stroke, e.get("stroke_opacity") or e.get("opacity"),
                      fallback=(170, 170, 170))
        width = max(1, int(round(float(e.get("stroke_width", 1) or 1) * scale)))
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay, "RGBA").line([(x, y), (x + w, y + h)],
                                             fill=color, width=width)
        img.alpha_composite(overlay)
        return

    if w <= 0 or h <= 0:
        return
    fill = e.get("fill") or e.get("color")
    radius = int(round(min(w, h) * 0.12)) if shape == "rounded_rect" else 0
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    xy = (x, y, x + w, y + h)
    if isinstance(fill, dict) and str(fill.get("type", "")).lower() == "gradient":
        # Preserve the direction cue for gradients; the shape mask remains a
        # secondary preview detail and the compiler is the source of truth.
        _fill(img, (x, y, w, h), ctx, fill, radius=radius)
    else:
        fill_color = _rgba(ctx, fill or "secondary", e.get("opacity"), fallback=(150, 150, 150))
        if shape == "ellipse":
            d.ellipse(xy, fill=fill_color)
        elif shape == "triangle":
            d.polygon([(x + w // 2, y), (x + w, y + h), (x, y + h)], fill=fill_color)
        elif shape == "diamond":
            d.polygon([(x + w // 2, y), (x + w, y + h // 2),
                       (x + w // 2, y + h), (x, y + h // 2)], fill=fill_color)
        elif radius:
            d.rounded_rectangle(xy, radius=radius, fill=fill_color)
        else:
            d.rectangle(xy, fill=fill_color)
    stroke = e.get("stroke")
    sw = max(1, int(round(float(e.get("stroke_width", 1) or 1) * scale)))
    outline = _rgba(ctx, stroke, e.get("stroke_opacity"), fallback=(120, 120, 120)) if stroke else None
    if outline:
        if shape == "ellipse":
            d.ellipse(xy, outline=outline, width=sw)
        elif shape == "triangle":
            d.line([(x + w // 2, y), (x + w, y + h), (x, y + h), (x + w // 2, y)],
                   fill=outline, width=sw, joint="curve")
        elif shape == "diamond":
            d.line([(x + w // 2, y), (x + w, y + h // 2),
                    (x + w // 2, y + h), (x, y + h // 2), (x + w // 2, y)],
                   fill=outline, width=sw, joint="curve")
        elif radius:
            d.rounded_rectangle(xy, radius=radius, outline=outline, width=sw)
        else:
            d.rectangle(xy, outline=outline, width=sw)
    img.alpha_composite(overlay)
    if e.get("text"):
        text_e = dict(e, type="text", color=e.get("text_color") or "ink",
                      size=e.get("text_size", 16), padding=e.get("text_padding", 8),
                      anchor=e.get("text_anchor", "middle"), align=e.get("align", "center"))
        _draw_text(img, text_e, ctx, scale)


def _resolve_image(src: Any, roots: list[Path]) -> Path | None:
    if not src:
        return None
    raw = Path(str(src))
    candidates = [raw] if raw.is_absolute() else [r / raw for r in roots]
    return next((p for p in candidates if p.exists() and p.is_file()), None)


def _draw_image(img: Image.Image, e: dict, ctx: RenderContext, scale: float,
                roots: list[Path]) -> None:
    x, y, w, h = _scale_box(e, scale)
    if w <= 0 or h <= 0:
        return
    source = e.get("src") or ((e.get("asset") or {}).get("src") if isinstance(e.get("asset"), dict) else None)
    import io
    blob = getattr(ctx, "image_bytes", {}).get(str(Path(str(source))))
    path = Path(str(source)) if blob is not None else _resolve_image(source, roots)
    if path:
        try:
            with Image.open(io.BytesIO(blob) if blob is not None else path) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGBA")
                fit = str(e.get("fit", "cover")).lower()
                if fit == "contain":
                    fitted = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                    image.thumbnail((w, h), Image.Resampling.LANCZOS)
                    fitted.alpha_composite(image, ((w - image.width) // 2, (h - image.height) // 2))
                else:
                    fitted = ImageOps.fit(image, (w, h), method=Image.Resampling.LANCZOS,
                                          centering=(0.5, 0.5))
                radius = int(round(min(w, h) * 0.03)) if e.get("rounded") else 0
                if radius:
                    mask = Image.new("L", (w, h), 0)
                    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius, fill=255)
                    fitted.putalpha(mask)
                img.alpha_composite(fitted, (x, y))
        except (OSError, ValueError):
            path = None
    if not path:
        _fill(img, (x, y, w, h), ctx, {"type": "solid", "color": "secondary", "opacity": 0.12})
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay, "RGBA")
        line = _rgba(ctx, "muted", 0.55)
        d.rectangle((x, y, x + w, y + h), outline=line, width=max(1, int(scale)))
        d.line((x, y, x + w, y + h), fill=line, width=max(1, int(scale)))
        d.line((x, y + h, x + w, y), fill=line, width=max(1, int(scale)))
        img.alpha_composite(overlay)
    if e.get("overlay"):
        _fill(img, (x, y, w, h), ctx, e["overlay"])


def _rows(e: dict) -> list[dict]:
    """图表载荷：单序列读 `data`，多序列读 `categories` + `series[{name,values}]`。

    这里刻意**不**接受 `rows` 别名：ghost 曾按 `rows or data` 取值，于是写 `rows`
    的 spec 在预览里画得好好的，到 guard 却报「缺少 data」、编译出来是一张空图。
    预览比产物宽容，是最坏的一种不一致——它让作者照着一张不存在的证据做判断。

    反过来同样坏：compiler 的多序列路径（`series` + `categories`，走
    `NATIVE_CHART_TYPES`）画得出来，预览若只认 `data` 就会把一张正确的图显示成
    空框——**冤枉对的**。实测 `comparison_bar` + 双序列的产物里 `<c:ser>=2`、
    数据点齐全，而预览只画了一个叉。多序列在这里按「类别 × 序列」展开成一维条，
    与产物的分组柱语义一致；预览是方向证据，不承担像素级复刻。
    """
    rows = e.get("data")
    if isinstance(rows, list) and rows:
        return [r if isinstance(r, dict) else {"label": str(i + 1), "value": r}
                for i, r in enumerate(rows)]
    cats, series = e.get("categories"), e.get("series")
    if (isinstance(cats, list) and cats and isinstance(series, list) and series
            and isinstance(series[0], dict)):
        out: list[dict] = []
        for s in series:
            if not isinstance(s, dict) or not isinstance(s.get("values"), list):
                continue
            name = str(s.get("name") or "").strip()
            for cat, val in zip(cats, s["values"]):
                out.append({"label": f"{cat} · {name}" if name else str(cat), "value": val})
        return out
    return []


def _value(row: dict, default=0.0) -> float:
    for key in ("value", "y", "amount", "actual", "current"):
        try:
            value = float(row.get(key))
            if math.isfinite(value):
                return value
        except (TypeError, ValueError):
            continue
    return default


def _draw_chart(img: Image.Image, e: dict, ctx: RenderContext, scale: float) -> None:
    x, y, w, h = _scale_box(e, scale)
    if w <= 0 or h <= 0:
        return
    rows = _rows(e)
    # kind 的取法与 guard/compiler 同源：只认 chart_kind / kind 两个键，
    # 且**不默认成 bar**。ghost 曾把 chart_type 也当别名、未知时兜底画柱图：
    # 这会让「写错键名」与「写了未支持的图表」在预览里都显示成一张漂亮的柱图，
    # 而 guard 报 CHART_TYPE_FAIL、编译器直接跳过不画。预览的宽容度必须
    # ≤ 交付链的宽容度，否则证据会替错误背书。
    kind = str(e.get("chart_kind") or e.get("kind") or "").lower()
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    ink = _rgba(ctx, e.get("color") or "primary", 0.78)
    muted = _rgba(ctx, "muted", 0.28)
    accent = _rgba(ctx, "accent", 0.92)
    d.rounded_rectangle((x, y, x + w, y + h), radius=max(2, int(8 * scale)), outline=muted,
                        width=max(1, int(scale)))
    pad = max(8, int(18 * scale))
    left, top, right, bottom = x + pad, y + pad, x + w - pad, y + h - pad

    # 数字展示（kpi/executive_kpi/big_number）读的是元素级 value/label，不是 data 行。
    # 预览必须和产物说同一件事——否则「交付证据」会显示一个空框，与 PPTX 不符。
    if kind in ("kpi", "executive_kpi", "big_number"):
        value = str(e.get("value") or "").strip()
        label = str(e.get("label") or "").strip()
        big = _font(min(120.0, float(e.get("value_size", 56))) * scale * 0.75,
                    cjk=_has_cjk(value), bold=True)
        small = _font(float(e.get("label_size", 16)) * scale * 0.75, cjk=_has_cjk(label))
        cy = (top + bottom) // 2
        if value:
            d.text((left, cy), value, font=big, fill=accent, anchor="lm")
        if label:
            d.text((left, cy + int(46 * scale)), label, font=small, fill=ink, anchor="lm")
        img.alpha_composite(overlay)
        return

    # 未知/缺失 kind 与空载荷同样处理成「画不出来」的占位叉：交付链里它们
    # 都会被 guard 拦下（CHART_TYPE_FAIL / 空载荷），预览就不该替它们画出
    # 一张像样的图。合法 kind 的真源在 primitives.CHART_KINDS，与 guard 共用。
    if not rows or kind not in CHART_KINDS:
        d.line((left, bottom, right, top), fill=muted, width=max(1, int(scale)))
        d.line((left, top, right, bottom), fill=muted, width=max(1, int(scale)))
        img.alpha_composite(overlay)
        return
    values = [_value(r) for r in rows]
    lo, hi = min(0.0, min(values)), max(1.0, max(values))
    span = max(1e-9, hi - lo)
    if kind in {"line", "area", "trend"}:
        pts = []
        for i, val in enumerate(values):
            px = left + (right - left) * (i / max(1, len(values) - 1))
            py = bottom - (val - lo) / span * (bottom - top)
            pts.append((int(px), int(py)))
        if len(pts) > 1:
            d.line(pts, fill=accent, width=max(2, int(3 * scale)), joint="curve")
        for px, py in pts:
            d.ellipse((px - 3 * scale, py - 3 * scale, px + 3 * scale, py + 3 * scale), fill=accent)
    elif kind in {"donut", "pie", "ring"}:
        vals = [max(0, v) for v in values]
        total = sum(vals) or 1
        start = -90
        colors = [accent, ink, _rgba(ctx, "secondary", 0.7), _rgba(ctx, "muted", 0.5)]
        hl = highlight_index(e, rows, 0)
        for i, val in enumerate(vals):
            end = start + 360 * val / total
            d.pieslice((left, top, right, bottom), start=start, end=end,
                       fill=accent if i == hl else colors[(i + 1) % len(colors)])
            start = end
        hole = max(1, int(min(right - left, bottom - top) * 0.52))
        cx, cy = (left + right) // 2, (top + bottom) // 2
        bg = _rgb(ctx, "background", (255, 255, 255))
        d.ellipse((cx - hole // 2, cy - hole // 2, cx + hole // 2, cy + hole // 2), fill=(*bg, 255))
    elif kind in ("bar", "horizontal_bar", "comparison_bar"):
        # OOXML 里 barChart 的 barDir="bar" 是横向条：预览必须与产物同向，
        # 否则「方向证据」给的是错的（曾经把横向条画成竖柱）。
        # 类目轴在左侧：不给它留位置，预览就只剩一串没有主人的数字，
        # 而产物里 OOXML 是会把标签画出来的——预览必须说同一件事。
        gap = max(3, int(8 * scale))
        cfont = _font(10 * scale)
        cat_w = int(min(180 * scale, (right - left) * 0.34))
        bar_left = left + cat_w
        bh = max(2, int((bottom - top - gap * max(0, len(values) - 1)) / max(1, len(values))))
        hl = highlight_index(e, rows, -1)
        show_values = bool(e.get("show_values", True))
        vfont = _font(11 * scale)
        for i, val in enumerate(values):
            by = top + i * (bh + gap)
            bw2 = int((val - lo) / span * (right - bar_left))
            d.text((left, by + bh / 2), str(rows[i].get("label", ""))[:24],
                   font=cfont, fill=_rgba(ctx, "muted", 0.9), anchor="lm")
            d.rounded_rectangle((bar_left, by, bar_left + bw2, by + bh),
                                radius=max(1, int(4 * scale)),
                                fill=accent if i == hl else ink)
            if show_values:
                vtext = str(int(val)) if float(val).is_integer() else str(val)
                d.text((bar_left + bw2 + 4 * scale, by + bh / 2), vtext,
                       font=vfont, fill=ink, anchor="lm")
        d.line((bar_left, top, bar_left, bottom), fill=muted, width=max(1, int(scale)))
    else:
        gap = max(3, int(8 * scale))
        bw = max(2, int((right - left - gap * max(0, len(values) - 1)) / max(1, len(values))))
        hl = highlight_index(e, rows, -1)
        show_values = bool(e.get("show_values", True))
        vfont = _font(11 * scale)
        cfont = _font(10 * scale)
        for i, val in enumerate(values):
            bx = left + i * (bw + gap)
            by = bottom - int((val - lo) / span * (bottom - top))
            # 强调谁由 spec 决定；没声明就不强调（预览不替作者挑「最大的那条」）
            d.rounded_rectangle((bx, by, bx + bw, bottom), radius=max(1, int(4 * scale)),
                                fill=accent if i == hl else ink)
            # 直接标注与类目轴：产物里有，预览里就必须有。
            cx = (bx + bx + bw) / 2
            if show_values:
                vtext = str(int(val)) if float(val).is_integer() else str(val)
                d.text((cx, max(y + 2, by - 3 * scale)), vtext,
                       font=vfont, fill=ink, anchor="mb")
            d.text((cx, bottom + 3 * scale), str(rows[i].get("label", "")),
                   font=cfont, fill=_rgba(ctx, "muted", 0.9), anchor="mt")
        d.line((left, bottom, right, bottom), fill=muted, width=max(1, int(scale)))
    img.alpha_composite(overlay)


def _draw_background(img: Image.Image, bg: Any, ctx: RenderContext) -> None:
    if isinstance(bg, dict) and str(bg.get("type", "")).lower() == "gradient":
        _draw_gradient(img, (0, 0, img.width, img.height), ctx, bg, 1.0)
    else:
        color = _rgb(ctx, bg if bg else "background", (255, 255, 255))
        img.paste((*color, 255), (0, 0, img.width, img.height))


def ghost_page(slide: dict, spec: dict, scale: float = 1.0, *, supersample: int = 2) -> Image.Image:
    """Render one polished direction preview; no external renderer or invented copy."""
    canvas = spec.get("canvas") or {}
    cw = float(canvas.get("width", DEFAULT_WIDTH))
    ch = float(canvas.get("height", DEFAULT_HEIGHT))
    output_w, output_h = max(1, int(cw * scale)), max(1, int(ch * scale))
    factor = max(1, int(supersample))
    render_scale = scale * factor
    img = Image.new("RGBA", (max(1, int(cw * render_scale)), max(1, int(ch * render_scale))), (255, 255, 255, 255))
    ctx = RenderContext(spec.get("theme"), canvas)
    ctx.image_bytes = spec.get("_image_bytes") or {}
    _draw_background(img, slide.get("background"), ctx)
    roots = [Path.cwd(), Path(str(spec.get("_base_path") or ".")).expanduser()]
    elements = list(slide.get("elements") or [])
    elements.sort(key=lambda e: 0 if isinstance(e, dict) and (
        str(e.get("layer", "")).lower() in {"background", "backdrop"}
        or str(e.get("role", "")).lower() in {"background", "backdrop"}) else 1)
    for e in elements:
        if not isinstance(e, dict):
            continue
        typ = str(e.get("type", "text")).lower()
        if typ == "text":
            _draw_text(img, e, ctx, render_scale)
        elif typ == "shape":
            _draw_shape(img, e, ctx, render_scale)
        elif typ == "image":
            _draw_image(img, e, ctx, render_scale, roots)
        elif typ in {"chart", "native_chart"}:
            _draw_chart(img, e, ctx, render_scale)
    if img.size != (output_w, output_h):
        img = img.resize((output_w, output_h), Image.Resampling.LANCZOS)
    return img.convert("RGB")


def ghost_deck(spec: dict, out_dir, pages: list[int] | None = None,
               scale: float = 0.5) -> list[Path]:
    """Save polished per-page PNGs.  Return only page paths for API compatibility."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    slides = spec.get("slides") or []
    wanted = [int(n) for n in pages] if pages is not None else list(range(1, len(slides) + 1))
    paths: list[Path] = []
    for n in wanted:
        if not (1 <= n <= len(slides)):
            continue
        image = ghost_page(slides[n - 1], spec, scale=scale, supersample=2)
        path = out / f"ghost-{n:02d}.png"
        image.save(path, "PNG", optimize=True)
        paths.append(path)
    return paths


def make_contact_sheet(paths: list[Path], out_path: str | Path, *, columns: int = 2,
                       gap: int = 24, label_height: int = 34) -> Path | None:
    """Create a clean, presentation-ready overview without adding decoration to pages."""
    valid = [Path(p) for p in paths if Path(p).exists()]
    if not valid:
        return None
    with Image.open(valid[0]) as opened:
        first = opened.convert("RGB")
    cell_w, cell_h = first.size
    rows = math.ceil(len(valid) / max(1, columns))
    sheet = Image.new("RGB", (columns * cell_w + (columns + 1) * gap,
                               rows * (cell_h + label_height) + (rows + 1) * gap), (245, 244, 241))
    draw = ImageDraw.Draw(sheet)
    label_font = _font(16, cjk=False, bold=True)
    for i, path in enumerate(valid):
        row, col = divmod(i, max(1, columns))
        x = gap + col * (cell_w + gap)
        y = gap + row * (cell_h + label_height)
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        sheet.paste(image, (x, y))
        draw.text((x, y + cell_h + 8), f"PAGE {path.stem.split('-')[-1]}",
                  fill=(50, 48, 44), font=label_font)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, "PNG", optimize=True)
    return target




