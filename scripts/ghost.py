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
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from primitives import (CHART_KINDS, RenderContext, DEFAULT_WIDTH, DEFAULT_HEIGHT, px_to_pt,
                        highlight_index, series_highlight_index, color_to_hex)


_FONT_CACHE: dict[tuple[str, int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
_FONT_CANDIDATES = {
    "latin": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/Library/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ),
    "latin_serif": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
        "/Library/Fonts/Times New Roman.ttf",
        "C:/Windows/Fonts/times.ttf",
    ),
    "cjk": (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/msyh.ttc",
    ),
    "cjk_serif": (
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/System/Library/Fonts/Songti.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ),
}
# 粗体候选：产物里 PowerPoint 逐 run 真加粗（set_run_font bold=True），预览此前
# **从不**换粗体字面（cjk 分支连 candidates 都不动），于是同一页「产物粗、预览细」，
# 字重反差在预览里根本看不见——保真缺口，与「预览宽容度必须 = 交付链」冲突。
_FONT_BOLD_CANDIDATES = {
    "latin": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ),
    "latin_serif": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
        "/Library/Fonts/Times New Roman Bold.ttf",
        "C:/Windows/Fonts/timesbd.ttf",
    ),
    "cjk": (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
    ),
    "cjk_serif": (
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
        "/System/Library/Fonts/Songti.ttc",
        "C:/Windows/Fonts/simsunb.ttf",
    ),
}


from primitives import is_cjk as _is_cjk   # 单一实现（范围与 guard 曾经不一致）


def _has_cjk(text: str) -> bool:
    return any(_is_cjk(c) for c in str(text))


def _font_family(element: dict, ctx: RenderContext) -> str:
    """元素字体 → 预览字面族。走主题字体表（与 compiler 同一张表），
    只分衬线/无衬线两个落点：预览不假装拥有字体，但不该把宋体页画成黑体页。"""
    fam = str(element.get("font") or "")
    if not fam:
        return ""
    fonts = getattr(ctx, "fonts", None) or {}
    resolved = str(fonts.get(fam, fam))
    return "_serif" if "serif" in resolved.lower() or "宋" in resolved or "song" in resolved.lower() else ""


def _font(size: float, *, cjk: bool = False, bold: bool = False,
          family: str = "") -> ImageFont.ImageFont:
    px = max(1, int(round(size)))
    base = ("cjk" if cjk else "latin") + ("_serif" if "_serif" in str(family) else "")
    key = (base, px, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = list(_FONT_CANDIDATES[base])
    if bold:
        candidates = list(_FONT_BOLD_CANDIDATES[base]) + candidates
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


def _rgba_color(color, opacity: float) -> tuple[int, int, int, int]:
    """RGBColor / #RRGGBB → RGBA 元组。

    刻意**不走 token 解析**：派生色（系列色阶）不是主题令牌，把它当令牌喂给
    ctx.paint 会解析失败并静默回退成灰——实测甜甜圈四段全灰，预览比产物更难读。
    """
    h = color_to_hex(color) or "888888"
    return (*(int(h[i:i + 2], 16) for i in (0, 2, 4)),
            max(0, min(255, int(float(opacity) * 255))))


def _series_groups(e: dict) -> list[tuple[str, list[float]]]:
    """多序列载荷 → 每序列一组 (name, values)；单序列载荷返回空。

    存在的理由：`_rows` 把「类别 × 序列」摊成一维条，这对分组柱是对的（产物里
    确实是按类别分组的柱），但对折线是错的——**三条序列会被画成一条折线**，
    预览看起来像「单一趋势」，而产物里是三条线（实测 s04 财务三线）。多序列的
    几何必须按序列分开画，与产物 `<c:ser>` 数量一一对应。
    """
    cats, series = e.get("categories"), e.get("series")
    if not (isinstance(cats, list) and cats and isinstance(series, list) and series
            and isinstance(series[0], dict)):
        return []
    out = []
    for s in series:
        if not isinstance(s, dict) or not isinstance(s.get("values"), list):
            continue
        vals = []
        for v in s["values"]:
            try:
                f = float(v)
                vals.append(f if math.isfinite(f) else 0.0)
            except (TypeError, ValueError):
                vals.append(0.0)
        out.append((str(s.get("name") or ""), vals))
    return out


def _series_plot_box(left: int, top: int, right: int, bottom: int, scale: float):
    """多序列折线的绘图区：让出类目标签的宽度（与产物一致，首末点不贴边）。"""
    gap = max(8, int(24 * scale))
    return left + gap, top + gap, right - gap, bottom - gap


def _scale_box(e: dict, scale: float) -> tuple[int, int, int, int]:
    return tuple(int(round(float(e.get(k, 0) or 0) * scale))
                 for k in ("x", "y", "width", "height"))


def _resolve_color(ctx: RenderContext, token) -> tuple[int, int, int] | None:
    if token is None:
        return None
    return _rgb(ctx, token, fallback=(0, 0, 0))


def _draw_gradient(img: Image.Image, box: tuple[int, int, int, int], ctx: RenderContext,
                   value: Any) -> None:
    """与产物 gradFill 同语义：stop 的 color + alpha 沿 angle 插值（0=左→右，90=上→下）。
    旧实现丢 alpha 且只走纵向——整幅画心的渐变 veil 在预览里变成不透明色块，
    作者被迫去翻产物 XML 才能看到真实页面。"""
    x, y, w, h = box
    stops = value.get("stops") if isinstance(value, dict) else None
    parsed = []
    for stop in stops or []:
        if isinstance(stop, dict):
            pos = stop.get("position", stop.get("pos"))
            token, alpha = stop.get("color"), stop.get("opacity", stop.get("alpha"))
        elif isinstance(stop, (list, tuple)) and len(stop) >= 2:
            pos, token = stop[0], stop[1]
            alpha = stop[2] if len(stop) > 2 else None
        else:
            continue
        color = _resolve_color(ctx, token)
        if color is None or pos is None:
            continue
        parsed.append((float(pos), color, 1.0 if alpha is None else float(alpha)))
    if len(parsed) < 2:
        return
    parsed.sort(key=lambda t: t[0])

    def _at(t: float):
        if t <= parsed[0][0]:
            p0 = p1 = parsed[0]
        elif t >= parsed[-1][0]:
            p0 = p1 = parsed[-1]
        else:
            p0, p1 = next((a, b) for a, b in zip(parsed, parsed[1:]) if a[0] <= t <= b[0])
        k = 0.0 if p0 is p1 else (t - p0[0]) / ((p1[0] - p0[0]) or 1.0)
        c = tuple(int(p0[1][i] + (p1[1][i] - p0[1][i]) * k) for i in range(3))
        return (*c, int(round((p0[2] + (p1[2] - p0[2]) * k) * 255)))

    horizontal = abs(float((value or {}).get("angle", 90)) % 180) < 45
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    n = max(1, int(w if horizontal else h))
    for i in range(n):
        fillc = _at(i / max(1, n - 1))
        if horizontal:
            d.line((x + i, y, x + i, y + h - 1), fill=fillc, width=1)
        else:
            d.line((x, y + i, x + w - 1, y + i), fill=fillc, width=1)
    img.alpha_composite(overlay)


def _fill(img: Image.Image, box: tuple[int, int, int, int], ctx: RenderContext,
          value: Any, radius: int = 0) -> None:
    if not value:
        return
    if isinstance(value, dict) and str(value.get("type", "")).lower() == "gradient":
        _draw_gradient(img, box, ctx, value)
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


def _wrap_lines(text: str, font, width: int, tracking: float = 0) -> list[str]:
    """按可见字宽折行；显式 tracking 与编译器字距同量纲（px）。"""
    limit = max(1, width)
    def visible_width(value):
        return font.getlength(value) + max(0, len(value) - 1) * tracking
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
                if line and visible_width(candidate) > limit:
                    result.append(line)
                    line = ""
                if not line and visible_width(word) > limit:
                    # 前面即使有普通单词，后一个长词也必须逐字切。
                    for ch in word:
                        if line and visible_width(line + ch) > limit:
                            result.append(line)
                            line = ch
                        else:
                            line += ch
                else:
                    line = word if not line else f"{line} {word}"
            result.append(line)
            continue
        line = ""
        for ch in raw:
            candidate = line + ch
            if line and visible_width(candidate) > limit:
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
    text_fill = e.get("fill")
    if text_fill and not (isinstance(text_fill, dict)
                          and str(text_fill.get("type", "")).lower() == "none"):
        _fill(img, (x, y, w, h), ctx, text_fill, radius=0)
    text = str(e.get("text", ""))
    if bool(e.get("uppercase")):
        text = text.upper()
    spacing_pt = float(e.get("char_spacing", 0) or 0)
    tracking = spacing_pt / 0.75 * scale
    if tracking:
        from primitives import insert_script_gaps
        text = insert_script_gaps(text)
    pad = int(round(float(e.get("padding", 0) or 0) * scale))
    size = float(e.get("size", 18) or 18) * scale
    font = _font(size, cjk=_has_cjk(text), bold=bool(e.get("bold")),
                 family=_font_family(e, ctx))
    color = _rgba(ctx, e.get("color") or "ink", e.get("opacity"), fallback=(24, 24, 24))
    lines = (_wrap_lines(text, font, w - 2 * pad, tracking)
             if bool(e.get("wrap", True)) else text.split("\n"))
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
    # 文字通常完全不透明：过去每个小字框都创建一张全画布 RGBA、再全幅合成。
    # 直接画到已不透明的页面像素完全一致；真正半透明的文字仍走原合成路径，
    # 不把 alpha=128 的替换当成 alpha_composite（否则会改变叠压与色阶）。
    opaque = color[3] == 255
    overlay = None if opaque else Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img if opaque else overlay, "RGBA")
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0] + max(0, len(line) - 1) * tracking
        if align in {"center", "middle"}:
            tx = x + (w - tw) / 2
        elif align in {"right", "end"}:
            tx = x + w - pad - tw
        else:
            tx = x + pad
        if tracking:
            # Pillow 不提供 tracking；仅显式声明字距的文本逐 glyph 落位。
            # 默认（绝大部分文字）维持一整行绘制、没有额外像素开销。
            cursor = tx
            for ch in line:
                d.text((int(cursor), int(cy)), ch, font=font, fill=color)
                cursor += font.getlength(ch) + tracking
        else:
            d.text((int(tx), int(cy)), line, font=font, fill=color)
        cy += line_height
    if overlay is not None:
        img.alpha_composite(overlay)


def _draw_shape(img: Image.Image, e: dict, ctx: RenderContext, scale: float) -> None:
    x, y, w, h = _scale_box(e, scale)
    shape = str(e.get("shape", "rect")).lower()

    if shape in ("line", "arrow"):
        # 一维线直接沿起点→终点绘制。完全不透明时不为每条细轴分配整幅
        # 画布 RGBA、再逐像素合成；只有半透明笔触才需要离屏合成。
        stroke = e.get("stroke")
        if isinstance(stroke, dict) and str(stroke.get("type")) == "none":
            return
        color = _rgba(ctx, stroke or "hairline", e.get("stroke_opacity"),
                      fallback=(170, 170, 170))
        width = max(1, int(round(float(e.get("stroke_width", 1) or 1) * scale)))
        overlay = None if color[3] == 255 else Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(img if overlay is None else overlay, "RGBA").line(
            [(x, y), (x + w, y + h)], fill=color, width=width)
        if overlay is not None:
            img.alpha_composite(overlay)
        return

    if w <= 0 or h <= 0:
        return
    fill = e.get("fill")   # 缺 fill / {type:none} 在 OOXML 中都是透明，不能画假卡片
    radius = int(round(min(w, h) * 0.12)) if shape == "rounded_rect" else 0
    xy = (x, y, x + w, y + h)
    gradient = isinstance(fill, dict) and str(fill.get("type", "")).lower() == "gradient"
    fill_color = None
    if gradient:
        _fill(img, (x, y, w, h), ctx, fill, radius=radius)
    elif isinstance(fill, dict):
        if str(fill.get("type", "solid")).lower() != "none":
            fill_color = _rgba(ctx, fill.get("color"), fill.get("opacity"))
    elif isinstance(fill, (int, float)) and not isinstance(fill, bool):
        fill_color = _rgba(ctx, e.get("fill_role") or "primary", float(fill))
    elif fill is not None:
        fill_color = _rgba(ctx, fill, e.get("fill_opacity"))
    stroke = e.get("stroke")
    if isinstance(stroke, dict) and str(stroke.get("type", "")).lower() == "none":
        stroke = None
    sw = max(1, int(round(float(e.get("stroke_width", 1) or 1) * scale)))
    outline = _rgba(ctx, stroke, e.get("stroke_opacity"), fallback=(120, 120, 120)) if stroke else None
    overlay = (None if (fill_color is None or fill_color[3] == 255)
               and (outline is None or outline[3] == 255) else
               Image.new("RGBA", img.size, (0, 0, 0, 0)))
    d = ImageDraw.Draw(img if overlay is None else overlay, "RGBA")
    if fill_color:
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
    if overlay is not None:
        img.alpha_composite(overlay)
    if e.get("text"):
        # 形状内文字有自己的原生属性名（compiler.shape_text）：不要继承
        # 形状填充/透明度，也不能丢掉 text_bold/line_height/wrap。
        text_e = dict(e, type="text", fill=None, color=e.get("text_color") or "ink",
                      size=e.get("text_size", 16), padding=e.get("padding", 0),
                      anchor=e.get("text_anchor", "middle"), align=e.get("align", "center"),
                      opacity=e.get("text_opacity"), bold=e.get("text_bold", False),
                      wrap=e.get("text_wrap", True),
                      line_height=e.get("text_line_height", 1.25))
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
            fit = str(e.get("fit", "cover")).lower()
            radius = int(round(min(w, h) * 0.03)) if e.get("rounded") else 0
            # 同一张图在整副预览里只解码/适配一次（重复页/重复使用是常态）。
            # 键含源身份 + 落位尺寸 + 适配方式：不同盒子各自成立，同盒子直接命中。
            cache = getattr(ctx, "preview_image_cache", None)
            key = (str(path), w, h, fit, radius)
            fitted = cache.get(key) if cache is not None else None
            held = (getattr(ctx, "image_decoded", None) or {}).get(str(path))
            if held is not None:
                # 复用前确认这张底图不需要方向转置（核验阶段按原样解码，绘制要尊重 EXIF）。
                # JPEG/TIFF/WebP 的方向元数据在文件头部，读它不解码；PNG 的 eXIf 排在
                # IDAT 之后，问一次就等于把整幅图解一遍（4K 实测 210ms）——而复用的意义
                # 正是不解码。本管线交付的位图是 PNG，且编译器本来就不做 EXIF 转置，
                # 预览按原样贴与产物一致；其它格式一律走原路径，像素与今天完全相同。
                try:
                    with Image.open(io.BytesIO(blob) if blob is not None else path) as probe:
                        if str(probe.format or "").upper() != "PNG" and probe.getexif():
                            held = None
                except (OSError, ValueError):
                    held = None
            if fitted is None:
                if held is not None:
                    image = held if held.mode == "RGBA" else held.convert("RGBA")
                else:
                    with Image.open(io.BytesIO(blob) if blob is not None else path) as opened:
                        # exif_transpose 在无 EXIF 时是纯拷贝：先判空再转，省一次全图复制。
                        image = (ImageOps.exif_transpose(opened)
                                 if opened.getexif() else opened).convert("RGBA")
                if fit == "contain":
                    fitted = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                    image.thumbnail((w, h), Image.Resampling.LANCZOS)
                    fitted.alpha_composite(image, ((w - image.width) // 2,
                                                   (h - image.height) // 2))
                else:
                    fitted = ImageOps.fit(image, (w, h), method=Image.Resampling.LANCZOS,
                                          centering=(0.5, 0.5))
                if radius:
                    mask = Image.new("L", (w, h), 0)
                    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius, fill=255)
                    fitted.putalpha(mask)
                if cache is not None:
                    cache[key] = fitted
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



# ── 预览覆盖契约（v6.4.3）──────────────────────────────────────────────────
# ghost 是**结构取证**，不是第二个渲染器：它只画「与产物 mark 结构同形」的图形。
# 曾经这里有一条兜底分支，把任何合法但未实现的图表类型画成一排柱图。于是
# big_number_row / steps / timeline / waterfall 在预览里全是**假图**——作者看到的
# 图形在编译产物里根本不存在（实战案源：2026 年终总结 s03 / s06 / s10，作者按
# 假预览改了三页构图）。预览的宽容度必须 ≤ 交付链的宽容度，预览的自信度也必须
# ≤ 它真正实现的程度：宁可说「这里我不渲染」，也不拿一张假图顶替。
#
# 两种归宿，必须覆盖 CHART_KINDS 全集（结构断言在 selftest，运行期兜底走 ABSTRACT）：
PREVIEW_MIRRORED = frozenset({
    # 原生图表：预览与产物同族几何（同向、零基、同类标签）
    "bar", "horizontal_bar", "comparison_bar", "column",
    "line", "area", "trend", "single_trend_line", "sparkline",
    "donut", "pie", "donut_composition",
    # 结构类：按编译器的同一组比例画（数字行 / 步 / 轴）
    "big_number_row", "steps", "timeline", "waterfall",
    # 象限类：轴 + 点位 + 直接标注（v7.1.0 起真渲染，作者不必翻产物 XML）
    "matrix",
    "progress_bar", "ranked_bar", "stacked_bar",
    # 数字展示：元素级 value/label 两行
    "kpi", "executive_kpi", "big_number",
})
# 不渲染形状的类型：画布上只留一句实话（类型名 + 以产物为准）。
# 提升进 MIRRORED 需要一次单独决定（那意味着多维护一份同形几何）。
# 留在这边的都是**结构图**：它们的价值在空间关系（层级、象限、路线），粗近似
# 只会让作者按一个不存在的间距做判断——所以如实写「不渲染」，而不是画一个大概。
PREVIEW_ABSTRACT = frozenset({
    "process_flow", "architecture", "bubble",
})



def _draw_wrapped(d: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], width: int,
                  font, fill, line_gap: float = 1.3) -> None:
    """按像素宽度折行的小段文本（steps 的 desc 用；与 compiler 文本框同口径）。"""
    line_h = int(font.size * line_gap)
    dy = 0
    for line in _wrap_lines(text, font, width)[:4]:
        d.text((xy[0], xy[1] + dy), line, font=font, fill=fill, anchor="la")
        dy += line_h


def _draw_unrendered(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int], kind: str,
                     scale: float) -> None:
    """预览不渲染的图形类型：留一句实话，不画想象出来的形状。"""
    left, top, right, bottom = box
    cx, cy = (left + right) // 2, (top + bottom) // 2
    name = _font(px_to_pt(12.5 * scale), cjk=False)
    note = _font(px_to_pt(11 * scale), cjk=True)
    d.text((cx, cy - int(10 * scale)), kind.upper(), font=name, fill=(150, 150, 150, 200),
           anchor="mb")
    d.text((cx, cy + int(10 * scale)), "预览不渲染此图形 · 以编译产物为准",
           font=note, fill=(150, 150, 150, 200), anchor="mt")


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
    # 外框**只属于占位分支**（见下方 ABSTRACT / 载荷缺失两处）：它是「这里我不画」
    # 的边界，不是装饰。同形镜像的图形一律不画框——产物里的图表本来就没有外框
    # （chartSpace / plotArea 描边实测为无），预览替它加一个圆角框，等于让作者
    # 按一个不存在的边框改构图。
    def placeholder_frame() -> None:
        d.rounded_rectangle((x, y, x + w, y + h), radius=max(2, int(8 * scale)),
                            outline=muted, width=max(1, int(scale)))

    pad = max(8, int(18 * scale))
    left, top, right, bottom = x + pad, y + pad, x + w - pad, y + h - pad

    # 数字展示（kpi/executive_kpi/big_number）读的是元素级 value/label，不是 data 行。
    # 预览必须和产物说同一件事——否则「交付证据」会显示一个空框，与 PPTX 不符。
    if kind in ("kpi", "executive_kpi", "big_number"):
        value = str(e.get("value") or "").strip()
        label = str(e.get("label") or "").strip()
        big = _font(px_to_pt(min(120.0, float(e.get("value_size", 56))) * scale),
                    cjk=_has_cjk(value), bold=True)
        small = _font(px_to_pt(float(e.get("label_size", 16)) * scale), cjk=_has_cjk(label))
        cy = (top + bottom) // 2
        if value:
            # 与编译产物同一条解析链（chart_primary_color），预览不另立主色。
            prim = ctx.chart_primary_color(e)
            d.text((left, cy), value, font=big,
                   fill=_rgba_color(prim, 0.95) if prim is not None else accent, anchor="lm")
        if label:
            d.text((left, cy + int(46 * scale)), label, font=small, fill=ink, anchor="lm")
        img.alpha_composite(overlay)
        return

    if kind == "matrix":
        # 同形镜像 compiler matrix：轴 + 点位 + 直接标注；点色同走 primary/secondary，
        # 象限论证在预览里可见，作者不必再去翻产物 XML。
        pts = e.get("points") or []
        pad_x, pad_y = w * 0.12, h * 0.12
        ox, oy = x + pad_x, y + h - pad_y
        pw, ph = w - pad_x * 1.25, h - pad_y * 1.35
        d.line((ox, oy, ox + pw, oy), fill=muted, width=max(1, int(scale)))
        d.line((ox, oy, ox, oy - ph), fill=muted, width=max(1, int(scale)))
        prim = ctx.chart_primary_color(e) or ctx.color("primary")
        sec = ctx.color(ctx.theme.get("chart_secondary", "secondary")) or prim
        lf = _font(px_to_pt(11 * scale), cjk=True)
        for p0 in pts[:12]:
            nx = ox + float(p0.get("x", 0.5)) * pw
            ny = oy - float(p0.get("y", 0.5)) * ph
            col = (_rgba_color(prim, 0.95) if p0.get("highlight")
                   else _rgba_color(sec, 0.8))
            r = max(3, int(7 * scale))
            d.ellipse((nx - r, ny - r, nx + r, ny + r), fill=col)
            d.text((nx + r + 2, ny), str(p0.get("label", "")), font=lf, fill=ink, anchor="lm")
        img.alpha_composite(overlay)
        return

    # 未知/缺失 kind 与空载荷同样处理成「画不出来」的占位叉：交付链里它们
    # 都会被 guard 拦下（CHART_TYPE_FAIL / 空载荷），预览就不该替它们画出
    # 一张像样的图。合法 kind 的真源在 primitives.CHART_KINDS，与 guard 共用。
    # 合法但不渲染形状的类型放在最前：matrix / architecture 走的是 points / layers
    # 不是 data 行，用「空载荷叉」表示它们，与「载荷真的缺失」是两件事——预览不能
    # 把「我不画」说成「你画不出来」（前者是预览的边界，后者是稿件的缺陷）。
    if kind in PREVIEW_ABSTRACT:
        placeholder_frame()
        _draw_unrendered(d, (left, top, right, bottom), kind, scale)
        img.alpha_composite(overlay)
        return
    if not rows or kind not in CHART_KINDS:
        placeholder_frame()
        d.line((left, bottom, right, top), fill=muted, width=max(1, int(scale)))
        d.line((left, top, right, bottom), fill=muted, width=max(1, int(scale)))
        img.alpha_composite(overlay)
        return
    values = [_value(r) for r in rows]
    lo, hi = min(0.0, min(values)), max(1.0, max(values))
    span = max(1e-9, hi - lo)
    groups = _series_groups(e)
    if len(groups) > 1 and kind in {"line", "area", "trend", "single_trend_line"}:
        # 与产物同形：每条序列一条线（产物里 <c:ser> = 序列数）。
        # 颜色也按产物同一条链取：series_roles 声明的用角色色，否则用系列色阶；
        # 高亮的那条（highlight = 序列索引/名字）走 accent + 加粗 + 末点圆点。
        names = [n for n, _v in groups]
        hl = series_highlight_index(e, names, -1)
        roles = e.get("series_roles") or []
        palette = ctx.series_palette(len(groups), hl)
        pl, pt, pr, pb = _series_plot_box(left, top, right, bottom, scale)
        lo2 = min([0.0] + [v for _n, vs in groups for v in vs])
        hi2 = max([1.0] + [v for _n, vs in groups for v in vs])
        span2 = max(1e-9, hi2 - lo2)
        for gi, (_name, vals) in enumerate(groups):
            if not vals:
                continue
            role = (ctx.chart_role(str(roles[gi])) if gi < len(roles) else None)
            col = _rgba_color(role if role is not None else palette[gi],
                              0.95 if gi == hl else 0.75)
            pts = []
            for i, val in enumerate(vals):
                px = pl + (pr - pl) * (i / max(1, len(vals) - 1))
                py = pb - (val - lo2) / span2 * (pb - pt)
                pts.append((int(px), int(py)))
            if kind == "area":
                # 面积图在产物里是**填充**系列：预览同样填面，不用折线冒充。
                base = int(pb - (0.0 - lo2) / span2 * (pb - pt))
                d.polygon(pts + [(pts[-1][0], base), (pts[0][0], base)],
                          fill=(*col[:3], 70 if gi != hl else 110))
                d.line(pts, fill=col, width=max(1, int((3 if gi == hl else 1.75) * scale)),
                       joint="curve")
            else:
                d.line(pts, fill=col, width=max(2, int((3 if gi == hl else 1.75) * scale)),
                       joint="curve")
            ex, ey = pts[-1]
            rr = max(2, int((4 if gi == hl else 3) * scale))
            d.ellipse((ex - rr, ey - rr, ex + rr, ey + rr), fill=col)
        img.alpha_composite(overlay)
        return
    if kind in {"line", "area", "trend", "single_trend_line", "sparkline"}:
        pts = []
        for i, val in enumerate(values):
            px = left + (right - left) * (i / max(1, len(values) - 1))
            py = bottom - (val - lo) / span * (bottom - top)
            pts.append((int(px), int(py)))
        # 基础色与编译器同一条规则：图表的 primary 若就是 accent 而本图又有强调点，
        # 基础让位到 primary 角色，accent 只留给强调（见 compiler 的 hl0/base）。
        hlm0 = highlight_index(e, rows, -1)
        base = accent
        if 0 <= hlm0 < len(pts):
            prim_role = (ctx.chart_role(e["color_role"]) if e.get("color_role") else None)
            prim = prim_role or ctx.color(e.get("primary_color")
                                          or ctx.theme.get("chart_primary", "accent"))
            if prim is not None and tuple(prim) == tuple(ctx.color("accent") or ()):
                alt = ctx.chart_role("primary") or ctx.color("primary") or ctx.color("accent")
                base = _rgba_color(alt, 0.92) if alt is not None else accent
        # 面积图在产物里是**填充**系列（fill + 无描边）：预览用折线冒充它，
        # 等于把「一块面」说成「一条线」——同形镜像的第一条就是不换几何。
        if kind == "area" and len(pts) > 1:
            d.polygon(pts + [(pts[-1][0], bottom), (pts[0][0], bottom)], fill=accent)
            img.alpha_composite(overlay)
            return
        if len(pts) > 1:
            d.line(pts, fill=base, width=max(2, int(3 * scale)), joint="curve")
        # 落点只在产物也落点的地方：产物给 line/trend 的高亮点（或无）、给
        # sparkline 的两端。曾经每个顶点都画点——产物身上没有那些点。
        if kind == "sparkline":
            marks = {0, len(pts) - 1}
        else:
            hlm = highlight_index(e, rows, -1)
            marks = {int(hlm)} if 0 <= hlm < len(pts) else set()
        for mi in marks:
            px, py = pts[mi]
            d.ellipse((px - 3 * scale, py - 3 * scale, px + 3 * scale, py + 3 * scale), fill=accent)
    elif kind in {"donut", "pie", "donut_composition"}:
        vals = [max(0, v) for v in values]
        total = sum(vals) or 1
        start = -90
        # 扇区色与产物同源（ctx.series_palette = 编译器构成图用的那一份派生）：
        # 预览曾用 ink/secondary/muted，与产物里的同色相明度阶梯毫无关系——作者会
        # 把「金色系深浅」误读成「中性灰」。
        hl = int(highlight_index(e, rows, 0))
        palette = [_rgba_color(c, 0.92) for c in ctx.series_palette(len(vals), hl)]
        for i, val in enumerate(vals):
            end = start + 360 * val / total
            d.pieslice((left, top, right, bottom), start=start, end=end, fill=palette[i])
            start = end
        hole = max(1, int(min(right - left, bottom - top) * 0.52))
        cx, cy = (left + right) // 2, (top + bottom) // 2
        bg = _rgb(ctx, "background", (255, 255, 255))
        d.ellipse((cx - hole // 2, cy - hole // 2, cx + hole // 2, cy + hole // 2), fill=(*bg, 255))
    elif kind in {"bar", "horizontal_bar", "comparison_bar"}:
        # OOXML 里 barChart 的 barDir="bar" 是横向条：预览必须与产物同向，
        # 否则「方向证据」给的是错的（曾经把横向条画成竖柱）。
        # 类目轴在左侧：不给它留位置，预览就只剩一串没有主人的数字，
        # 而产物里 OOXML 是会把标签画出来的——预览必须说同一件事。
        gap = max(3, int(8 * scale))
        cfont = _font(10 * scale, cjk=any(_has_cjk(r.get("label", "")) for r in rows))
        cat_w = int(min(180 * scale, (right - left) * 0.34))
        bar_left = left + cat_w
        bh = max(2, int((bottom - top - gap * max(0, len(values) - 1)) / max(1, len(values))))
        hl = highlight_index(e, rows, -1)
        show_values = bool(e.get("show_values", True))
        vfont = _font(11 * scale)
        # 多序列（comparison_bar）：条色按**序列**取，不能全体墨色——产物里每条
        # <c:ser> 有自己的色（series_roles → series_palette），预览全涂墨色等于把
        # 「山外 vs 同业」读成一堆同色条，作者看到的证据与产物不是同一件事。
        n_groups = max(1, len(groups))
        per_group = max(1, (len(rows) + n_groups - 1) // n_groups)
        roles = e.get("series_roles") or []
        gpalette = ctx.series_palette(n_groups,
                                      series_highlight_index(e, [n for n, _v in groups], -1))
        for i, val in enumerate(values):
            by = top + i * (bh + gap)
            bw2 = int((val - lo) / span * (right - bar_left))
            d.text((left, by + bh / 2), str(rows[i].get("label", ""))[:24],
                   font=cfont, fill=_rgba(ctx, "muted", 0.9), anchor="lm")
            if n_groups > 1:
                gi = min(i // per_group, n_groups - 1)
                role = (ctx.chart_role(str(roles[gi])) if gi < len(roles) else None)
                col = _rgba_color(role if role is not None else gpalette[gi], 0.95)
            else:
                col = accent if i == hl else ink
            d.rounded_rectangle((bar_left, by, bar_left + bw2, by + bh),
                                radius=max(1, int(4 * scale)), fill=col)
            if show_values:
                vtext = str(int(val)) if float(val).is_integer() else str(val)
                d.text((bar_left + bw2 + 4 * scale, by + bh / 2), vtext,
                       font=vfont, fill=ink, anchor="lm")
        d.line((bar_left, top, bar_left, bottom), fill=muted, width=max(1, int(scale)))
    elif kind == "column":
        # 原生竖柱：与产物同向、同零基、同类目标签（此前它是靠兜底分支"蒙对"的，
        # 现在显式声明——蒙对与实现是两件事，前者随时会因为别人的改动失真）。
        gap = max(3, int(8 * scale))
        bw = max(2, int((right - left - gap * max(0, len(values) - 1)) / max(1, len(values))))
        hl = highlight_index(e, rows, -1)
        show_values = bool(e.get("show_values", True))
        vfont = _font(11 * scale)
        cfont = _font(10 * scale, cjk=any(_has_cjk(r.get("label", "")) for r in rows))
        for i, val in enumerate(values):
            bx = left + i * (bw + gap)
            by = bottom - int((val - lo) / span * (bottom - top))
            d.rounded_rectangle((bx, by, bx + bw, bottom), radius=max(1, int(4 * scale)),
                                fill=accent if i == hl else ink)
            cx = (bx + bx + bw) / 2
            if show_values:
                vtext = str(int(val)) if float(val).is_integer() else str(val)
                d.text((cx, max(y + 2, by - 3 * scale)), vtext,
                       font=vfont, fill=ink, anchor="mb")
            d.text((cx, bottom + 3 * scale), str(rows[i].get("label", "")),
                   font=cfont, fill=_rgba(ctx, "muted", 0.9), anchor="mt")
        d.line((left, bottom, right, bottom), fill=muted, width=max(1, int(scale)))
    elif kind == "big_number_row":
        # 与 compiler 同形：值一行 + 标签一行 + 列间发丝竖线（不是柱子！）
        n = min(len(rows), 5)
        col_w = w / max(n, 1)
        vfont = _font(px_to_pt(float(e.get("value_size", 52)) * scale), bold=True)
        lfont = _font(px_to_pt(float(e.get("label_size", 14)) * scale), cjk=True)
        for i, row in enumerate(rows[:n]):
            cx = x + i * col_w
            if i > 0:
                rx = int(cx - 11 * scale)
                d.rectangle((rx, int(y + h * 0.18), rx + max(1, int(1.5 * scale)),
                             int(y + h * 0.18 + h * 0.52)), fill=muted)
            shown = row.get("display")
            val = str(shown) if shown is not None else str(row.get("value", ""))
            d.text((int(cx + 12 * scale), int(y + h * 0.14 + h * 0.20)), val,
                   font=vfont, fill=ink, anchor="lm")
            d.text((int(cx + 12 * scale), int(y + h * 0.56 + h * 0.10)),
                   str(row.get("label", ""))[:18], font=lfont,
                   fill=_rgba(ctx, "muted", 0.9), anchor="lm")
    elif kind == "steps":
        # 与 compiler 同形：序号 + 标题 + 说明 + 列间连接线
        n = min(len(rows), 6)
        col_w = w / max(n, 1)
        nfont = _font(px_to_pt(float(e.get("num_size", 30)) * scale), bold=True)
        tfont = _font(px_to_pt(float(e.get("title_size", 18)) * scale), cjk=True, bold=True)
        dfont = _font(px_to_pt(float(e.get("desc_size", 14)) * scale), cjk=True)
        for i, row in enumerate(rows[:n]):
            cx = x + i * col_w
            d.text((int(cx), int(y)), str(i + 1), font=nfont,
                   fill=_rgba(ctx, "secondary", 0.9), anchor="la")
            d.text((int(cx), int(y + 48 * scale)), str(row.get("label", ""))[:16],
                   font=tfont, fill=ink, anchor="la")
            desc = str(row.get("desc", "") or "").strip()
            if desc:
                _draw_wrapped(d, desc, (int(cx), int(y + 48 * scale + h * 0.36)),
                              int(col_w * 0.9), dfont, _rgba(ctx, "muted", 0.9))
            if i < n - 1:
                d.line((int(cx + col_w * 0.9), int(y + 22 * scale),
                        int(cx + col_w), int(y + 22 * scale)),
                       fill=muted, width=max(1, int(scale)))
    elif kind == "timeline":
        # 与 compiler 同形：一条轴 + 节点圆点 + 居中标签（末节点为强调色）
        n = min(len(rows), 7)
        axis_y = y + h * 0.52
        d.line((left, int(axis_y), right, int(axis_y)), fill=muted, width=max(1, int(scale)))
        lfont = _font(px_to_pt(float(e.get("label_size", 13)) * scale), cjk=True)
        for i, row in enumerate(rows[:n]):
            cx = x + w * (i + 0.5) / n
            rad = max(3, int(7 * scale))
            fill = accent if i == n - 1 else _rgba(ctx, "secondary", 0.85)
            d.ellipse((int(cx - rad), int(axis_y - rad), int(cx + rad), int(axis_y + rad)),
                      fill=fill)
            d.text((int(cx), int(axis_y + 16 * scale)), str(row.get("label", ""))[:14],
                   font=lfont, fill=ink, anchor="ma")
    elif kind == "waterfall":
        # 与 compiler 同形：浮动柱（starts→ends）+ 零轴 + 小计整段 + 段间桥接虚线。
        cum = 0.0
        starts, ends, is_total = [], [], []
        for row in rows:
            total = bool(row.get("subtotal") or row.get("is_total") or row.get("total"))
            if total:
                starts.append(0.0); ends.append(cum); is_total.append(True)
            else:
                starts.append(cum); cum += _value(row); ends.append(cum)
                is_total.append(False)
        lo = min(0.0, *starts, *ends)
        hi = max(0.0, *starts, *ends)
        span = max(hi - lo, 1.0)
        plot_h = h * 0.62
        def _py(v):
            return y + h * 0.82 - (v - lo) / span * plot_h
        d.line((left, int(_py(0.0)), right, int(_py(0.0))), fill=muted,
               width=max(1, int(scale)))
        n = max(len(rows), 1)
        bw = w / n * 0.46
        lfont = _font(px_to_pt(11 * scale), cjk=True)
        for i, row in enumerate(rows):
            bx = x + w * (i + 0.5) / n - bw / 2
            top = max(starts[i], ends[i]); bot = min(starts[i], ends[i])
            ry = _py(top); rh = max(5 * scale, (top - bot) / span * plot_h)
            d.rectangle((int(bx), int(ry), int(bx + bw), int(ry + rh)),
                        fill=(accent if is_total[i] else
                              (ink if (row.get("value") or 0) >= 0 else _rgba(ctx, "secondary", 0.8))))
            d.text((int(bx + bw / 2), int(y + h * 0.82 + 10 * scale)),
                   str(row.get("label", ""))[:12], font=lfont,
                   fill=ink if is_total[i] else _rgba(ctx, "muted", 0.9), anchor="ma")
            if i < len(rows) - 1 and not (is_total[i] or is_total[i + 1]):
                x0 = x + w * (i + 0.5) / n + bw / 2
                x1 = x + w * (i + 1.5) / n - bw / 2
                yy = int(_py(ends[i]))
                d.line((int(x0), yy, int(x1), yy), fill=muted, width=max(1, int(scale)))
    elif kind in {"progress_bar", "ranked_bar"}:
        # 与 compiler 同形：标签列 + 轨道 + 圆头填充 + 直接数值（ranked 按值降序）
        data = rows[: (8 if kind == "ranked_bar" else 6)]
        if kind == "ranked_bar":
            data = sorted(data, key=lambda r: _value(r), reverse=True)
        label_w = w * float(e.get("label_ratio", 0.24))
        bar_x = x + label_w + float(e.get("label_gap", 24)) * scale
        # 数值列按 canvas 单位留宽（与 compiler 的 value_width 同口径），
        # 再乘 scale 落到像素域——用固定像素留宽会在小尺度预览里把数值挤出框外。
        value_w = float(e.get("value_width", 78)) * scale
        track_right = max(right - value_w, bar_x + 10)
        row_h = h / max(len(data), 1)
        bar_h = max(4, min(float(e.get("bar_height", 12)) * scale, row_h * 0.34))
        top_value = max([_value(r) for r in data] or [1.0]) or 1.0
        # 与产物同一条色链：主叙事色走 chart_primary_color，高亮行才取强调色；
        # 预览把强调色铺满所有条＝证据在替作者说谎（CASE_004 证据）。
        prim = ctx.chart_primary_color(e) or ink
        hl = highlight_index(e, data, -1) if kind == "ranked_bar" else -1
        lfont = _font(px_to_pt(12 * scale), cjk=True)
        vfont = _font(px_to_pt(11 * scale), cjk=False)
        for i, row in enumerate(data):
            cy = y + row_h * (i + 0.5)
            span = max(track_right - bar_x, 10)
            filled = span * max(0.0, _value(row)) / (top_value if kind == "ranked_bar" else 100.0)
            if kind == "progress_bar":
                d.rounded_rectangle((int(bar_x), int(cy - bar_h / 2), int(track_right), int(cy + bar_h / 2)),
                                    radius=max(1, int(bar_h / 2)), fill=_rgba(ctx, "muted", 0.22))
            d.text((int(x), int(cy)), str(row.get("label", ""))[:14],
                   font=lfont, fill=ink, anchor="lm")
            bar_color = accent if (kind != "ranked_bar"
                                   or hl in (i, row.get("_index"))) else prim
            d.rounded_rectangle((int(bar_x), int(cy - bar_h / 2), int(bar_x + filled), int(cy + bar_h / 2)),
                                radius=max(1, int(bar_h / 2)), fill=bar_color)
            dot = bar_h + max(2, int(6 * scale))
            d.ellipse((int(bar_x + filled - dot / 2), int(cy - dot / 2),
                       int(bar_x + filled + dot / 2), int(cy + dot / 2)), fill=bar_color)
            shown = row.get("display")
            d.text((int(right), int(cy)),
                   str(shown) if shown is not None else str(_value(row)), font=vfont,
                   fill=ink, anchor="rm")
    elif kind == "stacked_bar":
        # 与 compiler 同形：一条整宽堆叠条 + 段内百分比 + 直接图例
        vals = [max(_value(r), 0.0) for r in rows[:8]]
        total = sum(vals) or 1.0
        bar_h = max(10, min(float(e.get("bar_height", 46)), h * 0.34))
        bar_y = y + (h - bar_h) / 2 - h * 0.10
        cursor = float(x)
        # 段色与产物同源：compiler 的堆叠条在 ramp=true 时走 ctx.ramp_color(i)（明度阶梯
        # 由浅到深），未声明 ramp 时才走 series_color(i)。预览此前**只**用 series 阶梯，
        # 于是同一张图在预览里是「深→浅」、在产物里是「浅→深」——同一份数据两种颜色顺序，
        # 而段内文字色又是按预览那块色算的，产物里的对比度结论跟着一起错。
        # 预览是方向证据：它必须说与产物同一件事。
        _seg_colors = [(ctx.ramp_color(i) if e.get("ramp") else ctx.series_color(i))
                       for i in range(len(vals))]
        palette = [_rgba_color(c, 0.95) for c in _seg_colors]
        for i, val in enumerate(vals):
            seg = w * val / total
            if seg <= 0:
                continue
            d.rectangle((int(cursor), int(bar_y), int(cursor + seg), int(bar_y + bar_h)),
                        fill=palette[i])
            if seg > 46 * scale:
                d.text((int(cursor + seg / 2), int(bar_y + bar_h / 2)),
                       f"{val / total:.0%}", font=_font(px_to_pt(11 * scale)),
                       fill=_rgba_color(ctx.auto_text_for(_seg_colors[i]), 0.95),
                       anchor="mm")
            cursor += seg
        lfont = _font(px_to_pt(10 * scale), cjk=True)
        for i, row in enumerate(rows[:8]):
            lx = x + i * (w / max(len(vals), 1))
            d.text((int(lx), int(bar_y + bar_h + 10 * scale)), str(row.get("label", ""))[:12],
                   font=lfont, fill=_rgba(ctx, "muted", 0.9), anchor="la")
    else:
        # 契约之外的 kind：运行期兜底同样不发明图形（结构断言在 selftest）。
        _draw_unrendered(d, (left, top, right, bottom), kind, scale)
    img.alpha_composite(overlay)


def _draw_background(img: Image.Image, bg: Any, ctx: RenderContext) -> None:
    if isinstance(bg, dict) and str(bg.get("type", "")).lower() == "gradient":
        _draw_gradient(img, (0, 0, img.width, img.height), ctx, bg)
    else:
        color = _rgb(ctx, bg if bg else "background", (255, 255, 255))
        img.paste((*color, 255), (0, 0, img.width, img.height))


def ghost_page(slide: dict, spec: dict, scale: float = 1.0, *, supersample: int = 2,
               image_cache: dict | None = None) -> Image.Image:
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
    # 核验阶段已经为一整批底图付过解码（同一份字节 + 同一个路径身份），预览直接用，
    # 不必为了往 640×360 的页面上贴一张 4K 图再解一遍。键与 _image_bytes 完全一致。
    ctx.image_decoded = spec.get("_image_decoded") or {}
    ctx.preview_image_cache = image_cache if image_cache is not None else {}
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


def _page_shape(slide) -> dict:
    """一页的结构事实：元素数、图片面积、数值载荷、最大字号。用于挑关键页。"""
    elements = slide.get("elements") if isinstance(slide, dict) else []
    elements = elements if isinstance(elements, list) else []
    image_area = data_rows = 0.0
    max_size = 0.0
    for e in elements:
        if not isinstance(e, dict):
            continue
        try:
            size = float(e.get("width", 0)) * float(e.get("height", 0))
        except (TypeError, ValueError):
            size = 0.0
        if e.get("type") == "image":
            image_area += size
        if e.get("type") in ("chart", "native_chart"):
            rows = e.get("data") if isinstance(e.get("data"), list) else []
            data_rows += max(len(rows), len(e.get("series") or []) or 0, 1)
        try:
            max_size = max(max_size, float(e.get("size") or 0))
        except (TypeError, ValueError):
            pass
    return {"elements": len(elements), "image_area": image_area,
            "data_rows": data_rows, "max_size": max_size}


def _label_pages(slides: list, pages: list[int], shapes: list[dict]) -> dict[str, str]:
    """给取到的关键页贴职责标签（证据要说明「看到了什么」）。"""
    total = len(slides)
    out: dict[str, str] = {}
    for n in pages:
        shape = shapes[n - 1] if 1 <= n <= total else {}
        if n == 1:
            label = "cover"
        elif n == total:
            label = "closing"
        elif shape.get("image_area"):
            label = "hero_image"
        elif shape.get("data_rows"):
            label = "dense_data"
        elif shape.get("elements", 9) <= 3:
            label = "section"
        else:
            label = "content"
        slide = slides[n - 1] if 1 <= n <= total else {}
        sid = str(slide.get("id")) if isinstance(slide, dict) and slide.get("id") else f"p{n}"
        out[sid] = label
    return out


def key_selection(slides: list, limit: int = 5) -> tuple[list[int], dict[str, str]]:
    """关键页 + 职责标签一次算完（页面结构只扫一遍）。

    取证口径：封面 / 章节 / 画心 / 密数据 / 收尾（1-based，确定性）。
    方向证据要的是「世界、结构、容量、落点」四件事被看到，不是每一页都被 raster。
    页数不超过 limit 时返回全部页（此时是全量证据，不是采样）。
    """
    total = len(slides)
    if total == 0:
        return [], {}
    limit = max(1, int(limit))
    shapes = [_page_shape(s) for s in slides]
    if total <= limit:
        pages = list(range(1, total + 1))
    else:
        picks: list[int] = [1, total]

        def _pick(index: int) -> None:
            if 1 <= index <= total and index not in picks and len(picks) < limit:
                picks.append(index)

        others = [i for i in range(2, total)]             # 1-based，去掉封面与收尾
        section = next((i for i in others
                        if shapes[i - 1]["elements"] <= 3 and shapes[i - 1]["max_size"] >= 32), None)
        if section:
            _pick(section)
        hero = max(others, key=lambda i: (shapes[i - 1]["image_area"], -i)) if others else None
        if hero and shapes[hero - 1]["image_area"] > 0:
            _pick(hero)
        dense = max(others, key=lambda i: (shapes[i - 1]["data_rows"],
                                           shapes[i - 1]["elements"], -i)) if others else None
        if dense and shapes[dense - 1]["data_rows"] > 0:
            _pick(dense)
        for i in others:                                   # 补足：按元素数降序
            if len(picks) >= limit:
                break
            _pick(i)
        pages = sorted(picks)
    return pages, _label_pages(slides, pages, shapes)


def key_pages(slides: list, limit: int = 5) -> list[int]:
    """关键页取证（1-based，确定性）：封面 / 章节 / 画心 / 密数据 / 收尾。"""
    pages, _ = key_selection(slides, limit)
    return pages


def key_page_roles(slides: list, pages: list[int]) -> dict[str, str]:
    """给取到的关键页贴职责标签（证据要说明「看到了什么」）。"""
    return _label_pages(slides, pages, [_page_shape(s) for s in slides])


PAGE_CACHE_DIR = "pages"          # 逐页渲染缓存（只缓存被渲染过的页）
PAGE_CACHE_MAX = 96               # 上限：迭代几轮之后自动淘汰最旧的




def _engine_stamp() -> str:
    """渲染器指纹：唯一实现在 primitives.engine_fingerprint（scope="preview"）。

    页面缓存必须随渲染器一起失效（缓存的是像素，像素由它决定）；进程内算一次。
    """
    from primitives import engine_fingerprint
    return engine_fingerprint("preview")


def _page_media_stamp(slide: dict, spec: dict) -> list:
    """页面缓存必须包含图片字节身份，而不只是 src 路径。

    QA 传入本轮已读过的 snapshots 时只在内存里哈希，不重读图片；独立 preview
    则对未快照的文件走统一 file_digest。相同源图跨页只算一次。
    """
    from primitives import digest_bytes
    cache = spec.get("_preview_media_digest_cache")
    if not isinstance(cache, dict):
        cache = {}
        spec["_preview_media_digest_cache"] = cache
    image_bytes = spec.get("_image_bytes")
    if not isinstance(image_bytes, dict):
        image_bytes = {}
        spec["_image_bytes"] = image_bytes
    digests = spec.get("_image_digests") or {}
    roots = [Path(spec.get("_base_path") or Path.cwd()), Path.cwd()]
    stamps = []
    for element in (slide.get("elements") or []):
        if not isinstance(element, dict) or element.get("type") != "image":
            continue
        src = element.get("src")
        if not src and isinstance(element.get("asset"), dict):
            src = element["asset"].get("src")
        if not src:
            stamps.append([str(element.get("id") or "?"), "missing"])
            continue
        path = Path(str(src)).expanduser()
        if not path.is_absolute():
            candidates = [(root / path).resolve() for root in roots]
            path = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])
        else:
            path = path.resolve()
        key = str(path)
        if key not in cache:
            known = digests.get(key)
            blob = image_bytes.get(key)
            if blob is None:
                blob = image_bytes.get(str(src))
            if known:
                sha = str(known)
            else:
                if blob is None:
                    try:
                        blob = path.read_bytes()
                    except OSError:
                        blob = None
                    if blob is not None:
                        # preview 也复用为 key 读取的字节，避免随后绘制再读同一图片。
                        image_bytes[key] = blob
                        image_bytes[str(src)] = blob
                sha = digest_bytes(blob) if blob is not None else None
            cache[key] = sha or "missing"
        stamps.append([str(element.get("id") or "?"), key, cache[key]])
    return stamps


def _page_key(slide: dict, spec: dict, scale: float, supersample: int,
              compress_level: int) -> str:
    """一页预览的身份：内容/画布/主题/图像字节/渲染口径/渲染器指纹。

    页面或其引用图像没变才可复用——同一 src 路径下图片字节换了也必须重画。
    """
    from primitives import identity
    return identity({
        "canvas": spec.get("canvas"), "theme": spec.get("theme"), "page": slide,
        "media": _page_media_stamp(slide, spec),
        "scale": round(float(scale), 4), "supersample": int(supersample),
        "compress": int(compress_level), "engine": _engine_stamp(),
    }, schema="vao-preview-page-v1", short=20)


def ghost_deck(spec: dict, out_dir, pages: list[int] | None = None,
               scale: float = 0.5, *, supersample: int = 2,
               store: bool = True, png_compress_level: int = 6,
               images_out: list | None = None, page_cache: bool = True,
               stats: dict | None = None) -> list[Path]:
    """Save per-page PNGs.  Return only page paths for API compatibility.

    `supersample=1` + `png_compress_level=1`（快速档）：预览是给人看一眼的方向证据，
    先用 2× 内部尺寸绘制再缩回、再用最优压缩找最小 PNG，都买不到「方向对不对」的
    判断力，只是在给 CPU 找活干。`images_out` 让调用方拿到内存里的页图，
    拼 contact sheet 时不必再把 PNG 从磁盘读回来。

    逐页缓存（v6.1）：页面的身份 = 内容 + 画布 + 主题 + 渲染口径 + 渲染器指纹。
    命中即直接读回上一轮的页图，不再绘制——迭代时改一页只重画一页。
    缓存只影响「画不画」，不影响「画什么」：键里没有的东西不会改变像素。
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cache_dir = out / PAGE_CACHE_DIR
    if page_cache:
        # 目录必须先存在：否则 save 会抛 OSError，被下面的兜底吞掉，缓存静默失效
        # （实测就是这样：计数显示「画了 15 页、命中 0 页」，磁盘上一个文件都没有）。
        cache_dir.mkdir(parents=True, exist_ok=True)
    slides = spec.get("slides") or []
    wanted = [int(n) for n in pages] if pages is not None else list(range(1, len(slides) + 1))
    paths: list[Path] = []
    image_cache: dict = {}
    for n in wanted:
        if not (1 <= n <= len(slides)):
            continue
        slide = slides[n - 1]
        key = _page_key(slide, spec, scale, supersample, png_compress_level) if page_cache else None
        cached_file = (cache_dir / f"{key}.png") if key else None
        image = None
        drawn = False
        cache_valid = False
        if cached_file is not None and cached_file.exists():
            try:
                with Image.open(cached_file) as handle:
                    image = handle.convert("RGB")
                image.load()
                cache_valid = True
            except (OSError, ValueError):
                image = None                    # 坏缓存文件 = 没缓存，重画
        if image is None:
            image = ghost_page(slide, spec, scale=scale, supersample=supersample,
                               image_cache=image_cache)
            drawn = True
            if cached_file is not None and store:
                try:
                    image.save(cached_file, "PNG", compress_level=int(png_compress_level))
                    cache_valid = True
                except OSError:
                    # 写不进去只影响下一次命中，不影响这一轮的像素；但必须可见——
                    # 「缓存静默失效」会让所有人以为它在工作（这个坑已经踩过一次）。
                    if stats is not None:
                        stats["cache_write_failed"] = stats.get("cache_write_failed", 0) + 1
        if images_out is not None:
            images_out.append(image)
        if stats is not None:
            stats["rendered" if drawn else "cached"] = stats.get(
                "rendered" if drawn else "cached", 0) + 1
            # 逐页明细：复用要能按页核对（哪几页是这一轮真画的），不能只有一个总数
            stats.setdefault("rendered_pages" if drawn else "cached_pages", []).append(n)
        if store:
            path = out / f"ghost-{n:02d}.png"
            copied = False
            if cached_file is not None and cache_valid and cached_file.is_file():
                try:
                    # 缓存 PNG 已编码：复制字节作为交付预览，避免同一像素再编码一次。
                    shutil.copyfile(cached_file, path)
                    copied = True
                except OSError:
                    pass
            if not copied:
                image.save(path, "PNG", compress_level=int(png_compress_level))
            paths.append(path)
    if store:
        # 这层是可交付的页图集合，不是页缓存：请求 5→2 页时把旧 3 张从输出
        # 目录移走，否则浏览目录的人会看到本轮未验证的过期证据。缓存仍留在 pages/。
        wanted_names = {p.name for p in paths}
        for stale in out.glob("ghost-[0-9]*.png"):
            if stale.name not in wanted_names:
                try:
                    stale.unlink()
                except OSError:
                    pass
    if page_cache:
        _prune_page_cache(cache_dir)
    return paths


def _prune_page_cache(cache_dir: Path, keep: int = PAGE_CACHE_MAX) -> None:
    """淘汰最旧的页缓存：缓存是加速器，不该变成磁盘上的无形资产。"""
    try:
        files = sorted(cache_dir.glob("*.png"), key=lambda f: f.stat().st_mtime_ns, reverse=True)
    except OSError:
        return
    for stale in files[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass


def _sheet_cache_key(valid: list[Path], columns: int, gap: int, label_height: int,
                     compress_level: int) -> str:
    """整张联络表的身份：页图字节（顺序）、页名（图上印的 PAGE 标签）、版式与压缩口径、
    渲染器指纹。键里没有的东西不会改变像素——所以键相同就不必重贴一遍。"""
    from primitives import file_digest, identity
    pages = [[p.name, file_digest(p)] for p in valid]
    return identity([pages, int(columns), int(gap), int(label_height),
                     int(compress_level), _engine_stamp()],
                    schema="vao-contact-sheet-v1", short=20)


def make_contact_sheet(paths: list[Path], out_path: str | Path, *, columns: int = 2,
                       gap: int = 24, label_height: int = 34,
                       images: list | None = None,
                       png_compress_level: int = 6,
                       cache_dir: str | Path | None = None,
                       stats: dict | None = None) -> Path | None:
    """Create a clean, presentation-ready overview without adding decoration to pages.

    `images`（可选）：调用方手里已经有页图时直接用，避免「写 PNG → 再读回 PNG」
    这一趟纯 I/O 往返（每页一次解码 + 一次编码）。

    `cache_dir`（可选）：页图逐页缓存所在的目录。联络表是页图的纯函数——页图没变时
    它的像素也不会变，直接把上一轮那张复制过来（严格档 15 页重贴实测 ~1.1s）。
    复制而非重存，是为了让交付出来的字节与上一轮完全相同。
    """
    valid = [Path(p) for p in paths if Path(p).exists()]
    if not valid:
        return None
    target = Path(out_path)
    cached = None
    if cache_dir is not None:
        cached = Path(cache_dir) / ("sheet-"
                                    + _sheet_cache_key(valid, columns, gap,
                                                       label_height, png_compress_level)
                                    + ".png")
        if cached.is_file():
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(cached, target)
                if stats is not None:
                    stats["sheet_cached"] = True
                return target
            except OSError:
                cached = None          # 复制不成 = 没缓存，照旧重建
    in_memory = list(images or [])
    if len(in_memory) != len(valid):
        in_memory = []
    if in_memory:
        cell_w, cell_h = in_memory[0].size
    else:
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
        if in_memory:
            image = in_memory[i].convert("RGB")
        else:
            with Image.open(path) as opened:
                image = opened.convert("RGB")
        sheet.paste(image, (x, y))
        draw.text((x, y + cell_h + 8), f"PAGE {path.stem.split('-')[-1]}",
                  fill=(50, 48, 44), font=label_font)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, "PNG", compress_level=int(png_compress_level))
    if stats is not None:
        stats["sheet_cached"] = False
    if cached is not None:
        try:
            cached.parent.mkdir(parents=True, exist_ok=True)
            # 联络表像素只编码一次；缓存副本直接复制 PNG 字节。
            shutil.copyfile(target, cached)
        except OSError:
            # 写不进缓存只影响下一次命中，不影响这一轮的像素；但要看得见。
            if stats is not None:
                stats["sheet_cache_write_failed"] = stats.get(
                    "sheet_cache_write_failed", 0) + 1
    return target
