# -*- coding: utf-8 -*-
"""Fast, deterministic direction preview for VAO.

Ghost is not an Office renderer. It is a high-fidelity *art-direction* preview:
real text, real local images, typography hierarchy, color roles, charts and
layer order are represented without LibreOffice, poppler or a browser.
Rendering is supersampled and downsampled once so thin rules and rounded forms
remain clean at contact-sheet size.  It never invents decorative content.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from primitives import RenderContext, DEFAULT_WIDTH, DEFAULT_HEIGHT


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
    if w <= 0 or h <= 0:
        return
    shape = str(e.get("shape", "rect")).lower()
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
    path = _resolve_image(source, roots)
    if path:
        try:
            with Image.open(path) as opened:
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
    rows = e.get("rows") or e.get("data") or []
    return [r if isinstance(r, dict) else {"label": str(i + 1), "value": r}
            for i, r in enumerate(rows)] if isinstance(rows, list) else []


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
    kind = str(e.get("kind") or e.get("chart_kind") or e.get("chart_type") or "bar").lower()
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    ink = _rgba(ctx, e.get("color") or "primary", 0.78)
    muted = _rgba(ctx, "muted", 0.28)
    accent = _rgba(ctx, "accent", 0.92)
    d.rounded_rectangle((x, y, x + w, y + h), radius=max(2, int(8 * scale)), outline=muted,
                        width=max(1, int(scale)))
    pad = max(8, int(18 * scale))
    left, top, right, bottom = x + pad, y + pad, x + w - pad, y + h - pad
    if not rows:
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
        for i, val in enumerate(vals):
            end = start + 360 * val / total
            d.pieslice((left, top, right, bottom), start=start, end=end,
                       fill=colors[i % len(colors)])
            start = end
        hole = max(1, int(min(right - left, bottom - top) * 0.52))
        cx, cy = (left + right) // 2, (top + bottom) // 2
        bg = _rgb(ctx, "background", (255, 255, 255))
        d.ellipse((cx - hole // 2, cy - hole // 2, cx + hole // 2, cy + hole // 2), fill=(*bg, 255))
    else:
        gap = max(3, int(8 * scale))
        bw = max(2, int((right - left - gap * max(0, len(values) - 1)) / max(1, len(values))))
        for i, val in enumerate(values):
            bx = left + i * (bw + gap)
            by = bottom - int((val - lo) / span * (bottom - top))
            d.rounded_rectangle((bx, by, bx + bw, bottom), radius=max(1, int(4 * scale)),
                                fill=accent if i == max(range(len(values)), key=lambda n: values[n]) else ink)
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


def main(argv) -> int:
    args = list(argv)
    pages = None
    if "--pages" in args:
        i = args.index("--pages")
        pages = [int(x) for x in args[i + 1].split(",") if x.strip()]
        args = args[:i] + args[i + 2:]
    if len(args) < 3:
        print("usage: python ghost.py <build_module.py> <out_dir> [--pages 1,5,12]")
        return 1
    mod_path = Path(args[1]).resolve()
    mod_spec = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    if mod_spec is None or mod_spec.loader is None:
        return 1
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    if spec is None:
        print("build module must define build_spec() or SPEC")
        return 1
    spec = dict(spec)
    spec["_base_path"] = str(mod_path.parent)
    paths = ghost_deck(spec, args[2], pages=pages)
    contact = make_contact_sheet(paths, Path(args[2]) / "ghost-contact-sheet.png")
    print(json.dumps({"pages": [str(p) for p in paths], "count": len(paths),
                      "contact_sheet": str(contact) if contact else None}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
