# -*- coding: utf-8 -*-
"""
Layer 2.5 · Ghost（迭代预览栅格化）

职责：在**不启动 LibreOffice / poppler** 的前提下，把 spec 的几何与色板
快速粗排成画布尺寸的缩略图，供迭代期「看一眼方向对不对」。

它是确定性纯函数：同一 spec 必得同一像素。它**不是渲染证据**，不参与任何
发布判定——发布仍以 render_check 的真实 PPTX→PDF→PNG 为准（那才是「真实
渲染证据」）。它只回答一个问题：这一版布局、色块关系、疏密，方向对吗？

为什么需要它：渲染证据占整轮 89–96% 成本（soffice 1.7s + 逐页像素测量），
而大多数迭代只想确认「标题位置 / 焦点尺度 / 色块关系 / 疏密」是否对。
ghost 把这类判断从 ~4.7s 压到 ~5ms/页，把真渲染留给收口与发布。

用法（CLI）：
    python3 scripts/ghost.py build_mydeck.py out_dir
    python3 scripts/ghost.py build_mydeck.py out_dir --pages 1,5,12
或作为库：from ghost import ghost_deck, ghost_page
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from primitives import RenderContext, DEFAULT_WIDTH, DEFAULT_HEIGHT


def _resolve_color(ctx: RenderContext, token) -> tuple | None:
    """token → RGB tuple（None 表示透明/未声明）。复用 RenderContext 的主题解析。"""
    if token is None:
        return None
    if isinstance(token, (tuple, list)) and len(token) >= 3:
        return tuple(int(c) for c in token[:3])
    rgb, alpha = ctx.paint(token)
    if rgb is None:
        return None
    return tuple(int(c) for c in rgb)


def _draw_background(draw: ImageDraw.ImageDraw, bg, ctx: RenderContext, w: int, h: int):
    """背景：纯色 / 渐变（线性近似为三段过渡）。"""
    if isinstance(bg, dict) and str(bg.get("type", "")).lower() == "gradient":
        stops = bg.get("stops") or []
        cols = []
        for s in stops:
            if isinstance(s, dict):
                col = s.get("color")
            elif isinstance(s, (list, tuple)) and len(s) >= 2:
                col = s[1]
            else:
                col = None
            rgb = _resolve_color(ctx, col)
            if rgb:
                cols.append(rgb)
        if len(cols) >= 2:
            for i in range(3):
                t = i / 2
                c = tuple(int(cols[0][k] + (cols[-1][k] - cols[0][k]) * t) for k in range(3))
                draw.rectangle([0, h * i // 3, w, h * (i + 1) // 3 + 1], fill=c)
            return
    rgb = _resolve_color(ctx, bg if isinstance(bg, str) else (bg or {}).get("color"))
    if rgb is None:
        rgb = _resolve_color(ctx, "background") or (255, 255, 255)
    draw.rectangle([0, 0, w, h], fill=rgb)


def ghost_page(slide: dict, spec: dict, scale: float = 1.0) -> Image.Image:
    """单页缩略图。纯函数：只读 spec，不写盘、不起进程。"""
    canvas = spec.get("canvas") or {}
    cw = int(canvas.get("width", DEFAULT_WIDTH))
    ch = int(canvas.get("height", DEFAULT_HEIGHT))
    w, h = int(cw * scale), int(ch * scale)
    ctx = RenderContext(spec.get("theme"), canvas)
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    _draw_background(draw, slide.get("background"), ctx, w, h)

    def S(v: float) -> int:
        return int(round(v * scale))

    elements = list(slide.get("elements") or [])
    # 与 compiler 同口径：背景层先画（ghost 只按声明顺序，不重排 z-order）
    for e in elements:
        if not isinstance(e, dict):
            continue
        typ = e.get("type", "text")
        x, y = S(float(e.get("x", 0))), S(float(e.get("y", 0)))
        ew, eh = S(float(e.get("width", 0) or 0)), S(float(e.get("height", 0) or 0))
        if ew <= 0 or eh <= 0:
            continue
        if typ == "text":
            # 文字：按字号画一条「墨色横杠」在文本框顶部，杠厚 ≈ 字号，直观表达层级。
            size = float(e.get("size", 18))
            rgb = _resolve_color(ctx, e.get("color")) or _resolve_color(ctx, "ink") or (30, 30, 30)
            bar_h = max(2, min(int(size * scale * 1.1), eh))
            draw.rectangle([x, y, x + ew, y + bar_h], fill=rgb)
        elif typ == "shape":
            fill = e.get("fill")
            rgb = None
            if isinstance(fill, dict):
                rgb = _resolve_color(ctx, fill.get("color"))
            elif fill is not None:
                rgb = _resolve_color(ctx, fill)
            stroke = _resolve_color(ctx, e.get("stroke"))
            if rgb is None:
                rgb = stroke
            if rgb is None:
                rgb = _resolve_color(ctx, "secondary") or (180, 180, 180)
            draw.rectangle([x, y, x + ew, y + eh], fill=rgb,
                           outline=(0, 0, 0) if stroke else None)
        elif typ in ("chart", "native_chart"):
            # 图表：虚线框 + 类型标注，只表达「这里有一块数据」。
            rgb = _resolve_color(ctx, "primary") or _resolve_color(ctx, "accent") or (100, 100, 100)
            draw.rectangle([x, y, x + ew, y + eh], outline=rgb, width=2)
            draw.line([x, y + eh, x + ew, y], fill=rgb)
            draw.line([x, y, x + ew, y + eh], fill=rgb)
        elif typ == "image":
            # 图片：中灰占位（不读文件，只表达占位与裁切盒）。
            rgb = _resolve_color(ctx, "secondary") or (160, 160, 160)
            draw.rectangle([x, y, x + ew, y + eh], fill=rgb)
            draw.line([x, y, x + ew, y + eh], fill=(255, 255, 255))
            draw.line([x, y + eh, x + ew, y], fill=(255, 255, 255))
    return img


def ghost_deck(spec: dict, out_dir, pages: list[int] | None = None,
               scale: float = 0.5) -> list[Path]:
    """整副 deck 的缩略图序列 → PNG 文件列表。不依赖 LibreOffice / poppler。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    slides = spec.get("slides") or []
    wanted = [int(n) for n in pages] if pages else list(range(1, len(slides) + 1))
    paths: list[Path] = []
    for n in wanted:
        if not (1 <= n <= len(slides)):
            continue
        img = ghost_page(slides[n - 1], spec, scale=scale)
        p = out / f"ghost-{n:02d}.png"
        img.save(p, "PNG")
        paths.append(p)
    return paths


def main(argv) -> int:
    import importlib.util
    import json
    import sys
    args = list(argv)
    pages = None
    if "--pages" in args:
        i = args.index("--pages")
        pages = [int(x) for x in args[i + 1].split(",") if x.strip()]
        args = args[:i] + args[i + 2:]
    if len(args) < 3:
        print("usage: python ghost.py <build_module.py> <out_dir> [--pages 1,5,12]")
        return 1
    mod_path = Path(args[1])
    mod = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    m = importlib.util.module_from_spec(mod)
    mod.loader.exec_module(m)
    spec = m.build_spec() if hasattr(m, "build_spec") else getattr(m, "SPEC", None)
    if spec is None:
        print("build module must define build_spec() or SPEC")
        return 1
    paths = ghost_deck(spec, args[2], pages=pages)
    print(json.dumps({"pages": [str(p) for p in paths], "count": len(paths)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
