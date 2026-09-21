"""PPT 编译引擎（单文件）· Elements → Charts → Compile 编排。

原 elements / charts / compile 编排三层合并：它们只被编译链消费，
分层文件带来 import 往返而无独立边界。对外契约不变：compile_deck / COMPILER_VERSION。
"""
from __future__ import annotations
import time
from pathlib import Path
import math
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_TICK_LABEL_POSITION, XL_MARKER_STYLE
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from primitives import (
    RenderContext, emu, pt, px_to_pt, DEFAULT_WIDTH, DEFAULT_HEIGHT, CHART_KINDS,
    CHART_LABEL_MIN_H, CHART_LABEL_MIN_COUNT,
    highlight_index, series_highlight_index,
    split_runs, is_cjk,
    insert_script_gaps,
    set_run_font, set_para_font, solid_fill, gradient_fill, stroke_color,
    align_of, anchor_of,
)


# ══════════════════ Layer 1 · Elements（元素层）══════════════════

SHAPE_TYPES = {
    "rect": MSO_SHAPE.RECTANGLE,
    "rounded_rect": MSO_SHAPE.ROUNDED_RECTANGLE,
    "ellipse": MSO_SHAPE.OVAL,
    "triangle": MSO_SHAPE.ISOSCELES_TRIANGLE,
    "diamond": MSO_SHAPE.DIAMOND,
    "pie": MSO_SHAPE.PIE,
}


def normalize_fill(value):
    """将标准与历史 fill 表达统一为内部契约；不解析主题 token。"""
    if value is None:
        return {"type": "none"}
    if isinstance(value, str):
        return {"type": "solid", "color": value}
    if not isinstance(value, dict):
        raise ValueError(
            "Invalid fill format. Expected a color token or "
            "{type: solid|gradient|none, ...}."
        )
    if "type" in value:
        kind = str(value["type"]).lower()
        if kind == "none":
            return {"type": "none"}
        if kind == "solid":
            if not value.get("color"):
                raise ValueError("Invalid solid fill: missing required field 'color'.")
            return {"type": "solid", "color": value["color"], "opacity": value.get("opacity")}
        if kind == "gradient":
            stops = value.get("stops")
            if not isinstance(stops, list) or len(stops) < 2:
                raise ValueError("Invalid gradient fill: 'stops' must contain at least two stops.")
            return {"type": "gradient", "stops": stops,
                    "angle": float(value.get("angle", 90)),
                    "gradient_type": value.get("gradient_type", "linear")}
        raise ValueError(f"Invalid fill type {value['type']!r}; expected solid, gradient, or none.")
    # Legacy: {"color": "#fff", "opacity": 0.3}
    if "color" in value:
        return {"type": "solid", "color": value["color"], "opacity": value.get("opacity")}
    # Legacy: {"gradient": {"stops": [[position, color, opacity], ...]}}
    if "gradient" in value:
        g = value["gradient"]
        if not isinstance(g, dict):
            raise ValueError("Invalid legacy gradient: expected an object.")
        return {"type": "gradient", "stops": g.get("stops", []),
                "angle": float(g.get("angle", 90)), "gradient_type": "linear"}
    raise ValueError(
        "Invalid fill format. Received a mapping without 'type' or legacy 'color'. "
        "Expected {type: 'solid', color: '#fff', opacity: 0.3}."
    )


def _gradient_stops(stops, ctx):
    normalized = []
    for item in stops:
        if isinstance(item, dict):
            pos = item.get("position", item.get("pos"))
            col = item.get("color")
            alpha = item.get("opacity", item.get("alpha"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            pos, col = item[0], item[1]
            alpha = item[2] if len(item) > 2 else None
        else:
            raise ValueError("Invalid gradient stop; expected object or [position, color, opacity].")
        if pos is None or col is None:
            raise ValueError("Invalid gradient stop: position and color are required.")
        resolved = ctx.colors.get(col, col)
        if ctx.paint(resolved)[0] is None:
            raise ValueError(f"Invalid fill color token {col!r} in gradient stop.")
        normalized.append((float(pos), resolved, float(alpha) if alpha is not None else None))
    return normalized


def apply_fill(shape_or_fill, value, ctx: RenderContext, fallback=None):
    """Apply the canonical Fill Contract; legacy shapes are normalized first."""
    fill = getattr(shape_or_fill, "fill", shape_or_fill)
    spec = normalize_fill(value)
    if spec["type"] == "none":
        fill.background()
        return
    if spec["type"] == "gradient":
        gradient_fill(fill, _gradient_stops(spec["stops"], ctx), spec["angle"])
        return
    color, token_alpha = ctx.paint(spec["color"])
    if color is None:
        if fallback:
            color, token_alpha = ctx.paint(fallback)
        if color is None:
            raise ValueError(
                f"Invalid fill color {spec['color']!r}. Expected a theme role or #RGB/#RRGGBB token."
            )
    opacity = spec.get("opacity")
    solid_fill(fill, color, float(opacity) if opacity is not None else token_alpha)


# --------------------------------------------------------------------------
# text
# --------------------------------------------------------------------------
def _validate_text_contract(element: dict) -> None:
    """Fail early when a text element uses fields not consumed by this layer."""
    eid = element.get("id", "?")
    if "text" not in element:
        hint = "；检测到 content，请改用 text" if "content" in element else ""
        raise ValueError(
            f"TEXT_FIELD_MISSING: text 元素 '{eid}' 缺少必需字段 'text'{hint}"
        )
    if "content" in element:
        raise ValueError(
            f"TEXT_FIELD_INVALID: text 元素 '{eid}' 使用了未消费字段 'content'，请改用顶层字段 'text'"
        )
    if "style" in element:
        raise ValueError(
            f"TEXT_STYLE_INVALID: text 元素 '{eid}' 使用了未消费的嵌套字段 'style'；"
            "请将 size、color、bold、line_height 等属性放到元素顶层"
        )


def add_text(slide, element: dict, ctx: RenderContext) -> None:
    _validate_text_contract(element)
    x, y, w, h = ctx.bounds(element)
    cn, latin = ctx.families(element)
    color = ctx.text_color(element.get("color"))
    alpha = None
    if element.get("color") is not None:
        _, alpha = ctx.paint(element.get("color"))
    if alpha is None and element.get("opacity") is not None:
        alpha = float(element["opacity"])
    pad = float(element.get("padding", 0))
    wrap = bool(element.get("wrap", True))
    lh = float(element.get("line_height", 1.35))
    size = float(element.get("size", 18))
    size_pt = px_to_pt(size)
    bold = bool(element.get("bold", False))
    italic = bool(element.get("italic", False))
    spacing = float(element.get("char_spacing", 0) or 0)
    uppercase = bool(element.get("uppercase", False))
    align = align_of(element.get("align"), PP_ALIGN.LEFT)

    tb = slide.shapes.add_textbox(Emu(emu(x)), Emu(emu(y)), Emu(emu(w)), Emu(emu(h)))
    tb.name = str(element.get("id", "text"))
    tf = tb.text_frame
    tf.clear()
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor_of(element.get("anchor"), MSO_ANCHOR.TOP)
    tf.margin_left = Emu(emu(pad))
    tf.margin_right = Emu(emu(pad))
    tf.margin_top = Emu(emu(pad))
    tf.margin_bottom = Emu(emu(pad))

    # 可选文本框底色（用于标签条 / 数据标牌）
    if element.get("fill"):
        apply_fill(tb, element["fill"], ctx)

    # 容量（行数/高度）在 guard 的 text_capacity 里判定到元素 id；渲染器只渲染，
    # 不再复算同一件事——同一事实两处判断时，两处都可能漂移。
    for i, line in enumerate(str(element.get("text", "")).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = pt(size * lh)
        if element.get("space_after") is not None:
            p.space_after = pt(float(element["space_after"]))
        if element.get("space_before") is not None:
            p.space_before = pt(float(element["space_before"]))
        if not line:
            continue
        for rv, iscjk in split_runs(insert_script_gaps(line)):
            run = p.add_run()
            run.text = rv
            set_run_font(run, cn if iscjk else latin, cn, size_pt, color,
                         bold, italic, spacing if not iscjk else None, alpha, uppercase)


# --------------------------------------------------------------------------
# shape
# --------------------------------------------------------------------------
def shape_text(shape, element: dict, ctx: RenderContext) -> None:
    """形状内文字：默认垂直居中。"""
    tf = shape.text_frame
    pad = emu(float(element.get("padding", 0)))
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Emu(pad)
    tf.word_wrap = bool(element.get("text_wrap", True))
    tf.vertical_anchor = anchor_of(element.get("text_anchor", "middle"), MSO_ANCHOR.MIDDLE)
    cn, latin = ctx.families(element)
    color = ctx.text_color(element.get("text_color"))
    alpha = element.get("text_opacity")
    size = float(element.get("text_size", 16))
    spacing = float(element.get("char_spacing", 0) or 0)
    p = tf.paragraphs[0]
    p.text = str(element.get("text", ""))
    p.alignment = align_of(element.get("align", "center"), PP_ALIGN.CENTER)
    p.line_spacing = pt(size * float(element.get("text_line_height", 1.25)))
    for run in p.runs:
        set_run_font(run, cn if is_cjk(run.text[:1] or " ") else latin, cn,
                     px_to_pt(size), color, bool(element.get("text_bold", False)),
                     False, spacing,
                     float(alpha) if alpha is not None else None,
                     bool(element.get("uppercase", False)))


def add_shape(slide, element: dict, ctx: RenderContext) -> None:
    x, y, w, h = ctx.bounds(element)
    kind = element.get("shape", "rect")
    stroke, stroke_alpha = ctx.paint(element.get("stroke"))
    if stroke_alpha is None and element.get("stroke_opacity") is not None:
        stroke_alpha = float(element["stroke_opacity"])
    sw = float(element.get("stroke_width", 1))

    if kind in ("line", "arrow"):
        c = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Emu(emu(x)), Emu(emu(y)),
            Emu(emu(x + w)), Emu(emu(y + h)))
        c.name = str(element.get("id", "line"))
        if stroke is not None:
            stroke_color(c.line, stroke, stroke_alpha, sw)
        return

    if kind not in SHAPE_TYPES:
        ctx.warn(f"shape '{element.get('id')}': 未知 shape={kind!r}，回落到 rect", element.get("id"))
        kind = "rect"
    s = slide.shapes.add_shape(
        SHAPE_TYPES[kind], Emu(emu(x)), Emu(emu(y)), Emu(emu(w)), Emu(emu(h)))
    s.name = str(element.get("id", "shape"))

    fill_value = element.get("fill")
    if isinstance(fill_value, (int, float)) and not isinstance(fill_value, bool):
        # fill_opacity 与角色名搭配使用
        fill_value = element.get("fill_role", "primary")
        color, _ = ctx.paint(fill_value)
        solid_fill(s.fill, color, float(element["fill"]))
    elif fill_value is not None:
        apply_fill(s, fill_value, ctx)
        if element.get("fill_opacity") is not None and not isinstance(fill_value, dict):
            color, _ = ctx.paint(fill_value)
            if color is not None:
                solid_fill(s.fill, color, float(element["fill_opacity"]))
    else:
        s.fill.background()

    if stroke is not None:
        stroke_color(s.line, stroke, stroke_alpha, sw)
    else:
        s.line.fill.background()

    if element.get("text"):
        shape_text(s, element, ctx)


# --------------------------------------------------------------------------
# image（cover / contain 裁切）
# --------------------------------------------------------------------------
def _resolve_src(element: dict, base_path: str | None,
                 spec_path: str | None = None) -> Path:
    src = Path(element["src"])
    if src.is_absolute():
        return src
    # 相对路径：先按输出目录解析（既有行为），再回退到 spec 文件所在目录
    # （作者更直觉的写法；两个都不存在时按输出目录报错，保持旧语义）。
    roots = [Path(base_path).parent if base_path else Path.cwd()]
    if spec_path:
        roots.append(Path(spec_path).parent)
    for root in roots:
        cand = (root / src).resolve()
        if cand.exists():
            return cand
    return (roots[0] / src).resolve()


# 图片落位管线（无临时文件、无重复变换）。
#
# 性能纪律（v5.9）：一张图进入 PPTX 的真实成本是「解码 + 变换 + 编码 + 写盘 +
# 再读回」，而磁盘上的临时 PNG 只是中间产物——它既不是交付物，也不能被凭证化。
# 因此变换结果直接以 bytes 交给 python-pptx（它按流头识别格式），落盘这一步整段消失。
#
# 两条硬规则：
#   1) 同一张图在同一盒子里只用变换一次（per-compile cache，键含全部变换参数）；
#   2) 不需要变换时不碰像素：源图与落位盒比例一致且未超采样到无意义倍数时直接透传。
#      渲染器会自己缩放；额外的解码/重采样/重编码买不到任何可见质量。
# 媒体超采样上限：1.0 = 落位尺寸即最终尺寸（与历史产物逐像素同规格）。
# 调大（如 2.0）会得到更耐放大的嵌入位图，代价是文件体积成倍增长；
# 交付规格是设计决定，速度优化不擅自改它。
MEDIA_MAX_OVERSAMPLE = 1.0


def _needs_alpha(img) -> bool:
    return img.mode in ("RGBA", "LA", "PA", "P") or "transparency" in img.info


def _fit_image_bytes(source, w: float, h: float, fit: str, crop=None,
                     bg: tuple | None = None, *, speed: str = "strict",
                     decode_cache: dict | None = None,
                     cache_key: str | None = None) -> bytes:
    """源图 → 落位尺寸的 PNG bytes（无临时文件）。source 可为路径或 bytes。"""
    import io
    from PIL import Image

    # 先把源读成 bytes：per-compile 缓存与流式读取都需要「可重复消费」的输入，
    # 直接对活流调用 Image.open 会让流位置前进，后续透传就会拿到半截字节。
    blob = _as_bytes(source)
    # 解码缓存：同一张源图落在多个盒子里时（全幅背景 + 局部插图 + 复用页），
    # 解码与「RGBA 合成 / 裁切」只做一次；后续的 crop/resize 都是纯函数式操作，
    # 共享同一张已解码底图不会互相污染。
    base = decode_cache.get(cache_key) if (decode_cache is not None and cache_key) else None
    if base is not None:
        img = base
        iw, ih = img.size
        crop = (lambda c: tuple(c) if c and any(c) else None)(crop)
        if crop is not None:
            cx0, cy0 = int(iw * crop[0]), int(ih * crop[1])
            cx1, cy1 = int(iw * (1 - crop[2])), int(ih * (1 - crop[3]))
            img = img.crop((cx0, cy0, cx1, cy1))
        return _encode_png(img, w, h, fit, bg, speed)
    with Image.open(io.BytesIO(blob)) as opened:
        iw, ih = opened.size
        l, t, r, b = (crop or (0, 0, 0, 0))
        crop = (l, t, r, b) if any((l, t, r, b)) else None
        sw, sh = (max(int(round(w)), 1), max(int(round(h)), 1))
        # 透传（不做任何像素工作）：无裁切、无透明混合、比例与盒子一致（±1%）、
        # 且源图既不需要放大也不超过 MEDIA_MAX_OVERSAMPLE 时，原字节就是正确的
        # 落位素材——渲染器自己会缩放到盒子，额外的解码/重采样/重编码买不到任何
        # 可见质量。比例不一致时必须做 cover/contain 变换（几何是设计决定）。
        aspect_ok = abs((iw / max(ih, 1)) / (sw / max(sh, 1)) - 1) <= 0.01
        fits = (sw * MEDIA_MAX_OVERSAMPLE >= iw and sh * MEDIA_MAX_OVERSAMPLE >= ih)
        if crop is None and not _needs_alpha(opened) and aspect_ok and fits:
            return blob                 # 原字节即正确素材：不解码、不重编码
        # JPEG 源：先 draft 到目标尺寸再解码（DCT 缩放解码，省掉整幅 4K 解码）。
        # PNG 源 draft 是空操作，因此这一步对任何格式都正确。
        if not _needs_alpha(opened):
            try:
                opened.draft("RGB", (sw, sh))
                iw, ih = opened.size
            except Exception:
                pass
        if crop is not None or _needs_alpha(opened):
            if _needs_alpha(opened):
                rgba = opened.convert("RGBA")
                background = Image.new("RGBA", rgba.size, (*(bg or (255, 255, 255)), 255))
                img = Image.alpha_composite(background, rgba).convert("RGB")
            else:
                img = opened.convert("RGB")
            if crop is not None:
                cx0, cy0 = int(iw * l), int(ih * t)
                cx1, cy1 = int(iw * (1 - r)), int(ih * (1 - b))
                img = img.crop((cx0, cy0, cx1, cy1))
        else:
            img = opened.convert("RGB")
    if decode_cache is not None and cache_key:
        decode_cache[cache_key] = img
    return _encode_png(img, w, h, fit, bg, speed)


def _encode_png(img, w: float, h: float, fit: str, bg: tuple | None,
                speed: str) -> bytes:
    """已解码底图 → 落位尺寸的 PNG bytes（cover / contain）。"""
    import io
    from PIL import Image
    iw, ih = img.size
    target_w = max(1, min(iw, int(round(w * MEDIA_MAX_OVERSAMPLE))))
    target_h = max(1, min(ih, int(round(h * MEDIA_MAX_OVERSAMPLE))))
    if fit == "contain":
        scale = min(target_w / iw, target_h / ih)
        nw, nh = max(int(round(iw * scale)), 1), max(int(round(ih * scale)), 1)
        if (nw, nh) != (iw, ih):
            img = _resize_quality(img, (nw, nh))
        canvas = Image.new("RGB", (target_w, target_h), bg if bg is not None else (255, 255, 255))
        canvas.paste(img, ((target_w - nw) // 2, (target_h - nh) // 2))
        img = canvas
    else:  # cover
        scale = max(target_w / iw, target_h / ih)
        nw, nh = max(int(round(iw * scale)), 1), max(int(round(ih * scale)), 1)
        if (nw, nh) != (iw, ih):
            img = _resize_quality(img, (nw, nh))
        left, top = (nw - target_w) // 2, (nh - target_h) // 2
        img = img.crop((left, top, left + target_w, top + target_h))
    buf = io.BytesIO()
    # 快速档用低压缩级别换编码时间：预览/交付质量不受影响（无损），
    # 只是文件略大——PNG 的无损性不随 compress_level 改变。
    img.save(buf, "PNG", compress_level=1 if speed == "fast" else 6)
    return buf.getvalue()


def _resize_quality(img, size):
    """高质量缩放：缩小时先用 BOX 预降采样再 LANCZOS 收尾（PIL reducing_gap），
    与纯 LANCZOS 的结果在肉眼与指标上都几乎不可分辨，但省掉大量重采样工作。
    放大时直接用 LANCZOS（reducing_gap 对放大无意义）。"""
    from PIL import Image
    if size[0] < img.width and size[1] < img.height:
        return img.resize(size, Image.LANCZOS, reducing_gap=2.0)
    return img.resize(size, Image.LANCZOS)


def _as_bytes(value) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if hasattr(value, "read"):
        position = value.tell() if hasattr(value, "tell") else None
        blob = value.read()
        if position is not None and hasattr(value, "seek"):
            try:
                value.seek(position)
            except Exception:
                pass
        return blob
    return Path(value).read_bytes()


def _content_protection_overlay(element: dict) -> dict | None:
    """取画心的内容保护叠加层：Fill Contract 或 content_protection.overlay。"""
    ov = element.get("overlay")
    if not ov:
        cp = element.get("content_protection")
        if isinstance(cp, dict):
            ov = cp.get("overlay") or cp.get("scrim") or cp.get("fill")
    return ov if isinstance(ov, (dict, str)) and ov else None


def add_image(slide, element: dict, ctx: RenderContext, base_path: str | None = None,
              spec_path: str | None = None) -> None:
    x, y, w, h = ctx.bounds(element)
    src = _resolve_src(element, base_path, spec_path)
    import io
    snapshot = getattr(ctx, "image_bytes", {}).get(str(src))
    if snapshot is None and getattr(ctx, "require_snapshot", False):
        ctx.warn(f"image '{element.get('id')}': 缺少核验字节快照", element.get("id"))
        return
    if snapshot is None and not src.exists():
        ctx.warn(f"image '{element.get('id')}': 找不到文件 {src}", element.get("id"))
        return

    fit = element.get("fit", "cover")
    crop = element.get("crop")
    blob = None
    if fit in ("cover", "contain") or crop:
        try:
            # contain 留白填充主题背景色，保证暗色主题下无白边。
            bg_rgb = ctx.color("background")
            bg_tuple = tuple(bg_rgb) if bg_rgb is not None else None
            crop_key = tuple(crop) if crop else ()
            cache = getattr(ctx, "image_transform_cache", None)
            key = (str(src), round(float(w), 2), round(float(h), 2), str(fit), crop_key, bg_tuple)
            blob = cache.get(key) if cache is not None else None
            if blob is None:
                source = io.BytesIO(snapshot) if snapshot is not None else src
                t0 = time.perf_counter()
                decode_cache = getattr(ctx, "image_decode_cache", None)
                if decode_cache is not None and str(src) in decode_cache:
                    ctx.timings["image_decode_reuses"] = ctx.timings.get("image_decode_reuses", 0) + 1
                blob = _fit_image_bytes(source, w, h, fit, crop, bg=bg_tuple,
                                        speed=getattr(ctx, "speed", "strict"),
                                        decode_cache=decode_cache,
                                        cache_key=str(src))
                ctx.timings["image_transform_ms"] = ctx.timings.get("image_transform_ms", 0.0) \
                    + (time.perf_counter() - t0) * 1000
                ctx.timings["image_transforms"] = ctx.timings.get("image_transforms", 0) + 1
                if cache is not None:
                    cache[key] = blob
            else:
                ctx.timings["image_transform_reuses"] = ctx.timings.get("image_transform_reuses", 0) + 1
        except Exception as exc:
            ctx.warn(f"image '{element.get('id')}': 裁切失败，按原图嵌入（{exc}）", element.get("id"))
            blob = None

    # 嵌入：blob 为本进程变换出的字节；无变换时直接给流/路径。
    # 异常不在这里吞掉——compile_deck 的元素级兜底负责记账（错误信息带 slide 与元素 id）。
    if blob is not None:
        pic = slide.shapes.add_picture(io.BytesIO(blob), Emu(emu(x)), Emu(emu(y)),
                                       Emu(emu(w)), Emu(emu(h)))
    else:
        stream = io.BytesIO(snapshot) if snapshot is not None else str(src)
        if isinstance(stream, io.BytesIO):
            stream.seek(0)
        pic = slide.shapes.add_picture(stream, Emu(emu(x)), Emu(emu(y)),
                                       Emu(emu(w)), Emu(emu(h)))
    pic.name = str(element.get("id", "image"))
    # Content Protection 层：紧随图片、覆盖同一盒，使文字可直接叠加而不牺牲可读性
    overlay = _content_protection_overlay(element)
    if overlay:
        shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(emu(x)), Emu(emu(y)),
                                    Emu(emu(w)), Emu(emu(h)))
        shp.name = f"{element.get('id', 'image')}__protection"
        try:
            shp.shadow.inherit = False
        except Exception:
            pass
        apply_fill(shp, overlay, ctx)
        shp.line.fill.background()


# ══════════════════ Layer 2 · Charts（图表层）══════════════════

NATIVE_CHART_TYPES = {
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "horizontal_bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "comparison_bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "line": XL_CHART_TYPE.LINE,
    "trend": XL_CHART_TYPE.LINE,
    "single_trend_line": XL_CHART_TYPE.LINE,
    "area": XL_CHART_TYPE.AREA,
    "donut": XL_CHART_TYPE.DOUGHNUT,
    "donut_composition": XL_CHART_TYPE.DOUGHNUT,
    "pie": XL_CHART_TYPE.PIE,
}
# 载荷是元素级（不是 data 行）的形状图：判「有没有东西可画」要看 points / layers
ELEMENT_PAYLOAD_CHARTS = {"matrix", "architecture"}

SHAPE_CHARTS = {
    "process_flow", "timeline", "steps", "matrix",
    "waterfall", "architecture", "bubble",
    # 编辑级图表：轨道 + 细线 + 直接标注，避免通用图表外观
    "ranked_bar", "progress_bar", "stacked_bar", "big_number_row",
    # 迷你趋势：去轴的折线 + 端点，用于 small multiples（一页对比多组趋势）
    "sparkline",
}


def _textbox(slide, name, x, y, w, h, text, size, color, ctx, element,
             align=PP_ALIGN.LEFT, bold=False, alpha=None):
    """图表内的可编辑文字块（垂直居中、零内边距）。"""
    cn, latin = ctx.families(element)
    tb = slide.shapes.add_textbox(Emu(emu(x)), Emu(emu(y)), Emu(emu(w)), Emu(emu(h)))
    tb.name = name
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor_of("middle")
    p = tf.paragraphs[0]
    p.alignment = align
    text = "" if text is None else str(text)
    if text.strip():
        p.text = text
        set_para_font(p, latin, cn, px_to_pt(size), color, bold)
    return tb


def chart_colors(element: dict, ctx: RenderContext):
    # Color Role System：元素可声明语义角色（color_role / secondary_role）取代
    # 具体色值——主题换了图表语义不变。显式 *_color 仍是逃生口（永远可覆盖）。
    primary = (ctx.chart_role(element["color_role"])
               if element.get("color_role") else None)
    if primary is None:
        primary = ctx.color(element.get("primary_color")
                            or ctx.theme.get("chart_primary", "accent"))
    if primary is None:
        primary = ctx.text_color("ink")
    secondary = (ctx.chart_role(element["secondary_role"])
                 if element.get("secondary_role") else None)
    if secondary is None:
        secondary = ctx.color(element.get("secondary_color")
                              or ctx.theme.get("chart_secondary", "secondary"))
    if secondary is None:
        secondary = primary
    ink = ctx.text_color(element.get("ink_color"))
    muted = ctx.color(element.get("muted_color")
                      or ctx.theme.get("chart_muted", "secondary"))
    if muted is None:
        muted = ctx.text_color("secondary" if "secondary" in ctx.colors else None)
    return primary, secondary, ink, muted


def _paint_negative_points(series, ctx: RenderContext, element: dict) -> None:
    """柱状序列里 <0 的点自动染 negative 角色色（元素可 negative_role=False 关闭）。

    风险语义由角色承担，不由色值承担：主题派生什么风险色，负值就是什么色。
    """
    if element.get("negative_role") is False:
        return
    try:
        vals = tuple(series.values or ())
        # 无负值就不解析角色——告警只在兜底真的被用到时才发声
        # （否则每个柱图都会因主题没声明 negative 而 COMPILE_FAIL）。
        if not any(v is not None and v < 0 for v in vals):
            return
        neg = ctx.chart_role("negative")
        if neg is None:
            return
        for i, v in enumerate(vals):
            if v is not None and v < 0:
                pt = series.points[i]
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = neg
    except Exception:
        pass


def _rows(element: dict) -> list[dict]:
    """统一解析 data；保留无效值状态，禁止把坏数据静默当作 0。"""
    data = element.get("data", []) or []
    rows = []
    for i, it in enumerate(data):
        if isinstance(it, dict) and "label" in it:
            raw = it.get("value")
            missing = raw is None
            invalid = False
            try:
                if isinstance(raw, bool):
                    raise ValueError
                num = float(raw) if raw is not None else 0.0
                invalid = not math.isfinite(num)
            except (TypeError, ValueError, OverflowError):
                num, invalid = 0.0, not missing
            if invalid:
                num = 0.0
            display = it.get("display")
            if display is None:
                display = raw if isinstance(raw, str) else (
                    int(num) if float(num).is_integer() else num)
            rows.append({"label": str(it["label"]), "value": num,
                         "display": display, "_index": i,
                         "missing": missing, "invalid": invalid})
        elif (isinstance(it, (int, float)) and not isinstance(it, bool)
              and math.isfinite(float(it))):
            rows.append({"label": str(i), "value": float(it), "display": it,
                         "_index": i, "missing": False, "invalid": False})
    return rows


def _set_donut_hole_size(plot, pct: int) -> None:
    """写 c:doughnutHoleSize。python-pptx 1.0.2 的 DoughnutPlot 是空类：
    plot.hole_size = N 只是无声的实例属性赋值，序列化时丢失（实测 XML 无此元素，
    渲染器回落到默认孔比）。直接写 XML 元素；按 CT_DoughnutChart 子元素顺序
    （varyColors, ser*, dLbls, firstSliceAng, doughnutHoleSize）置于其后。

    注意：PowerPoint 遵循该属性；部分阅读器会忽略（对照实验 30/62/90
    渲染孔比恒为其默认 ~0.50）——预览不变化属渲染器差异，不是本函数失效。"""
    from pptx.oxml.ns import qn
    el = plot._element
    tag = qn("c:doughnutHoleSize")
    for old in el.findall(tag):
        el.remove(old)
    node = el.makeelement(tag, {"val": str(int(pct))})
    fang = el.find(qn("c:firstSliceAng"))
    if fang is not None:
        fang.addnext(node)
    else:
        el.append(node)


def _display(row, element, fallback=""):
    """Prefer caller-authored display strings; never invent a unit."""
    if row.get("missing"):
        return str(element.get("missing_label", "—"))
    value = row.get("display")
    if value is not None:
        return str(value)
    return fallback if fallback != "" else str(row.get("value", ""))


def _label(shape, text, element, ctx, color, default_size=14):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor_of("middle")
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    text = "" if text is None else str(text)
    if text.strip():
        p.text = text
        cn, latin = ctx.families(element)
        size = float(element.get("label_size", default_size))
        set_para_font(p, latin, cn, px_to_pt(size), color, False)


# --------------------------------------------------------------------------
# 原生图表
# --------------------------------------------------------------------------
def _add_multi_series(slide, element: dict, ctx: RenderContext,
                      kind: str, x, y, w, h) -> None:
    """多序列原生图表（line/column/area）：categories + series[{name, values}]。

    与「类型枚举」互补而非取代：同一个 line geometry，通过 series/highlight/
    end_labels 组合出多序列趋势、末端直接标注等编辑式表达。每序列用系列色，
    highlight 指定的序列升级为 accent + 加粗 + 末端圆点。"""
    cn, latin = ctx.families(element)
    primary, secondary, ink, muted = chart_colors(element, ctx)
    eid = str(element.get("id", "chart"))
    categories = list(element.get("categories") or [])
    series_list = list(element.get("series") or [])
    parsed = []
    for s in series_list:
        if not isinstance(s, dict):
            ctx.warn(f"chart '{eid}': series 项必须是对象/dict，已跳过", eid)
            continue
        name = str(s.get("name", ""))
        vals = s.get("values")
        if not isinstance(vals, list) or not vals:
            ctx.warn(f"chart '{eid}': 序列 '{name}' 缺少 values，已跳过", eid)
            vals = []
        nums = []
        for v in vals:
            try:
                if isinstance(v, bool):
                    raise ValueError
                n = float(v)
                if not math.isfinite(n):
                    raise ValueError
                nums.append(n)
            except (TypeError, ValueError, OverflowError):
                nums.append(0.0)
                ctx.warn(f"chart '{eid}': 序列 '{name}' 含无法解析为数字的值，已按 0 计算", eid)
        parsed.append((name, nums))
    if not parsed or not categories:
        ctx.warn(f"chart '{eid}': 多序列图缺少 series 或 categories，已跳过", eid)
        return
    n_cat = len(categories)
    data = CategoryChartData()
    data.categories = categories
    for name, nums in parsed:
        data.add_series(name, nums[:n_cat] + [0.0] * max(0, n_cat - len(nums)))
    gf = slide.shapes.add_chart(
        NATIVE_CHART_TYPES[kind], Emu(emu(x)), Emu(emu(y)), Emu(emu(w)), Emu(emu(h)), data)
    gf.name = eid
    chart = gf.chart
    chart.has_legend = False
    chart.has_title = False
    try:
        chart.value_axis.has_major_gridlines = False
        chart.value_axis.format.line.fill.background()
        chart.value_axis.tick_labels.font.size = Pt(8)
        chart.value_axis.tick_labels.font.color.rgb = muted
        chart.value_axis.tick_labels.font.name = latin
        chart.category_axis.format.line.fill.background()
        chart.category_axis.tick_labels.font.size = Pt(10)
        chart.category_axis.tick_labels.font.color.rgb = ink
        chart.category_axis.tick_labels.font.name = latin
    except Exception:
        pass
    series_names = [name for name, _nums in parsed]
    hl = series_highlight_index(element, series_names, -1)
    end_labels = bool(element.get("end_labels", True))
    # 每序列可声明语义角色（series_roles: ["primary","negative",...]）——
    # 「这条序列是风险」是判断，不该写死成某个 hex。
    series_roles = element.get("series_roles") or []
    for i, series in enumerate(chart.series):
        role_color = (ctx.chart_role(str(series_roles[i]))
                      if i < len(series_roles) else None)
        color = role_color or (ctx.color("accent") if i == hl
                               else ctx.series_color(i))
        if kind in ("line", "trend", "single_trend_line"):
            series.format.line.color.rgb = color
            series.format.line.width = Pt(3.0 if i == hl else 1.75)
            series.smooth = bool(element.get("smooth", False))
            if i == hl or end_labels:
                try:
                    mk = series.points[-1].marker
                    mk.style = XL_MARKER_STYLE.CIRCLE
                    mk.size = 8 if i == hl else 6
                    mk.format.fill.solid()
                    mk.format.fill.fore_color.rgb = color
                    mk.format.line.color.rgb = color
                except Exception:
                    pass
        else:
            series.format.fill.solid()
            series.format.fill.fore_color.rgb = color
            series.format.line.fill.background()
            _paint_negative_points(series, ctx, element)
    try:
        chart.plots[0].gap_width = int(element.get("gap_width", 55))
    except Exception:
        pass


def add_native_chart(slide, element: dict, ctx: RenderContext) -> None:
    x, y, w, h = ctx.bounds(element)
    kind = str(element.get("chart_kind") or element.get("kind", ""))
    cn, latin = ctx.families(element)
    primary, secondary, ink, muted = chart_colors(element, ctx)
    eid = str(element.get("id", "chart"))

    # 多序列：series[{name, values}] 存在时走多序列渲染（同一 geometry 的多序列表达）。
    # 必须早于单序列的 rows 解析——多序列图没有 element["data"]，只有 series/categories。
    series_list = element.get("series")
    if isinstance(series_list, list) and series_list and isinstance(series_list[0], dict):
        _add_multi_series(slide, element, ctx, kind, x, y, w, h)
        return

    rows = _rows(element)
    if not rows:
        ctx.warn(f"chart '{element.get('id')}': 没有可渲染的数据行，已跳过", element.get("id"))
        return
    invalid = [r for r in rows if r.get("invalid")]
    if invalid:
        ctx.warn(f"chart '{element.get('id')}': {len(invalid)} 个数据值无法解析为有限数字，已按 0 计算；请修正原始数据", element.get("id"))
    data = CategoryChartData()
    data.categories = [r["label"] for r in rows]
    data.add_series(str(element.get("series_name", "")), [r["value"] for r in rows])
    gf = slide.shapes.add_chart(
        NATIVE_CHART_TYPES[kind], Emu(emu(x)), Emu(emu(y)),
        Emu(emu(w)), Emu(emu(h)), data)
    gf.name = eid
    chart = gf.chart
    chart.has_legend = False
    chart.has_title = False

    try:
        # 低噪声：去网格线、去轴线，弱化刻度
        chart.value_axis.has_major_gridlines = False
        chart.value_axis.format.line.fill.background()
        chart.value_axis.tick_labels.font.size = Pt(8)
        chart.value_axis.tick_labels.font.color.rgb = muted
        chart.value_axis.tick_labels.font.name = latin
        chart.category_axis.format.line.fill.background()
        chart.category_axis.tick_labels.font.size = Pt(10)
        chart.category_axis.tick_labels.font.color.rgb = ink
        chart.category_axis.tick_labels.font.name = latin
    except Exception:
        pass

    series = chart.series[0]
    try:
        if kind in ("line", "trend", "single_trend_line"):
            series.format.line.color.rgb = primary
            series.format.line.width = Pt(2.25)
            series.smooth = bool(element.get("smooth", False))
            # 折线图的唯一强调点：无标记则 highlight 形同虚设
            hl = highlight_index(element, rows, -1)
            if 0 <= hl < len(rows):
                try:
                    mk = series.points[hl].marker
                    mk.style = XL_MARKER_STYLE.CIRCLE
                    mk.size = 7
                    mk.format.fill.solid()
                    mk.format.fill.fore_color.rgb = secondary
                    mk.format.line.color.rgb = secondary
                except Exception:
                    pass
        else:
            series.format.fill.solid()
            series.format.fill.fore_color.rgb = primary
            series.format.line.fill.background()
            _paint_negative_points(series, ctx, element)
            try:
                chart.plots[0].gap_width = int(element.get("gap_width", 55))
            except Exception:
                pass

        hl = highlight_index(element, rows, -1)
        if 0 <= hl < len(rows):
            # 强调语义全库统一：高亮项 = accent（构成图/多序列/排行同理）。
            # 之前这里用 secondary，等于把「结论那一项」画得比其余更浅，
            # 与「一图一个强调」的设计判断相反。
            accent = ctx.color("accent")
            point = series.points[hl]
            point.format.fill.solid()
            point.format.fill.fore_color.rgb = accent
            try:
                point.format.line.color.rgb = accent
            except Exception:
                pass

        show_values = element.get("show_values", kind in ("comparison_bar", "bar", "column", "donut"))
        # Do not squeeze labels into a dense plot. The policy is explicit so the
        # caller can choose between removing redundant labels and failing QA.
        label_policy = str(element.get("label_collision_policy", "fail"))
        if (show_values and len(rows) >= CHART_LABEL_MIN_COUNT
                and h < CHART_LABEL_MIN_H):
            if label_policy == "hide_redundant":
                show_values = False
                ctx.warn(f"chart '{element.get('id')}': 标签空间不足，按 hide_redundant 隐藏重复数值", element.get("id"))
            else:
                ctx.warn(f"chart '{element.get('id')}': 标签空间不足；请拆图/减少类别，避免数值遮挡", element.get("id"))
        if show_values:
            plot = chart.plots[0]
            plot.has_data_labels = True
            plot.data_labels.show_value = True
            plot.data_labels.font.size = Pt(9)
            plot.data_labels.font.color.rgb = ink
            plot.data_labels.font.name = latin
            nf = element.get("number_format")
            if nf:
                try:
                    plot.data_labels.number_format = str(nf)
                    plot.data_labels.number_format_is_linked = False
                except Exception:
                    pass
            try:
                plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
            except Exception:
                pass
            # 直接标注已承担读数职责时隐藏值轴刻度（OS §19.3：直接标注够用时
            # 不保留第二套读数通道），进一步降噪。
            try:
                chart.value_axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
            except Exception:
                pass

        if kind in ("donut", "donut_composition", "pie"):
            if kind != "pie":
                _set_donut_hole_size(chart.plots[0], int(element.get("hole_size", 62)))
            hl = highlight_index(element, rows, 0)
            for i, point in enumerate(series.points):
                point.format.fill.solid()
                # 构成图各扇区用系列色区分（原先非高亮点统一 secondary，
                # 多类构成会糊成同色块）；高亮点保持 accent 语义。
                point.format.fill.fore_color.rgb = (
                    ctx.color("accent") if i == int(hl) else ctx.series_color(i))
            # 环心 KPI：把「总数/结论」放进甜甜圈的洞（叠加可编辑文本框，
            # 不破坏原生扇区的可编辑性）。这是高端 dashboard 的标志性动作：
            # 洞不再空着，而是承担「这一图到底说了什么」的单一读数。
            if kind in ("donut", "donut_composition"):
                center_value = element.get("center_value")
                center_label = element.get("center_label")
                if center_value is not None or center_label:
                    inner = min(w, h) * 0.46        # 洞可用直径（hole_size 默认 62%）
                    cx, cy = x + w / 2, y + h / 2
                # 几何：数值行框以孔心为中心（值即读数，必须上下居中），
                # 标签行框在数值下方、仍落在孔内（孔半径 ≈ inner/2）。
                if center_value is not None:
                    _textbox(slide, f"{eid}__center_value",
                             cx - inner / 2, cy - inner * 0.25,
                             inner, inner * 0.5,
                             str(center_value),
                             float(element.get("center_value_size", 30)),
                             ink, ctx, element, align=PP_ALIGN.CENTER, bold=True)
                if center_label:
                    _textbox(slide, f"{eid}__center_label",
                             cx - inner / 2, cy + inner * 0.27,
                             inner, inner * 0.18,
                             str(center_label),
                             float(element.get("center_label_size", 12)),
                             muted, ctx, element, align=PP_ALIGN.CENTER)
    except Exception as exc:
        # 不静默吞掉：图表样式块任何一步失败都可能悄悄丢掉环心 KPI / 孔比，
        # 至少要让报告里看得到（此前裸 pass，排障时图表可以无声缺件）。
        ctx.warn(f"chart '{element.get('id')}': 样式块异常 {type(exc).__name__}: {exc}", element.get("id"))


# --------------------------------------------------------------------------
# 形状化图表（战略图 / 流程 / 时间轴等，保持原生可编辑）
# --------------------------------------------------------------------------
def add_shape_chart(slide, element: dict, ctx: RenderContext, kind: str) -> None:
    x, y, w, h = ctx.bounds(element)
    cn, latin = ctx.families(element)
    primary, secondary, ink, muted = chart_colors(element, ctx)
    rows = _rows(element)
    eid = str(element.get("id", kind))
    # 元素级载荷的 kind（matrix→points / architecture→layers）不走数据行：
    # 用「必须有 data 行」的通用门拦它们，会让这两种 kind 永远画不出来——
    # 文档要求 points/layers、Guard 也只校验 points/layers，编译器却要 data = 三层口径打架。
    if not rows and kind not in ELEMENT_PAYLOAD_CHARTS:
        ctx.warn(f"chart '{element.get('id')}': 没有可渲染的数据行，已跳过", element.get("id"))
        return
    invalid = [r for r in rows if r.get("invalid")]
    if invalid:
        ctx.warn(f"chart '{element.get('id')}': {len(invalid)} 个数据值无法解析为有限数字，已按 0 计算；请修正原始数据", element.get("id"))

    if kind == "process_flow":
        n = min(len(rows), 7)
        node_w = w / max(n, 1) * 0.72
        gap = w / max(n, 1) * 0.28
        for i, row in enumerate(rows[:7]):
            nx = x + i * (node_w + gap)
            s = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Emu(emu(nx)), Emu(emu(y + h * 0.30)),
                Emu(emu(node_w)), Emu(emu(h * 0.32)))
            s.name = f"{eid}__node_{i}"
            s.fill.solid()
            fill_rgb = primary if i == 0 else secondary
            s.fill.fore_color.rgb = fill_rgb
            s.line.fill.background()
            # 按实际填充色选文字色（比 on_primary/on_secondary 更稳——
            # chart_secondary 可能映射到 accent，深浅与 secondary 相反）
            text_color = ctx.auto_text_for(fill_rgb)
            _label(s, row["label"], element, ctx, text_color, 14)
            if i < n - 1:
                c = slide.shapes.add_connector(
                    MSO_CONNECTOR.STRAIGHT, Emu(emu(nx + node_w)), Emu(emu(y + h * 0.46)),
                    Emu(emu(nx + node_w + gap)), Emu(emu(y + h * 0.46)))
                c.name = f"{eid}__edge_{i}"
                c.line.color.rgb = muted
                c.line.width = Emu(emu(1))
        return

    if kind == "timeline":
        n = min(len(rows), 7)
        axis_y = y + h * 0.52
        ax = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Emu(emu(x)), Emu(emu(axis_y)),
            Emu(emu(x + w)), Emu(emu(axis_y)))
        ax.name = f"{eid}__axis"
        ax.line.color.rgb = muted
        ax.line.width = Emu(emu(1))
        for i, row in enumerate(rows[:7]):
            cx = x + w * (i + 0.5) / n
            d = slide.shapes.add_shape(
                MSO_SHAPE.OVAL, Emu(emu(cx - 7)), Emu(emu(axis_y - 7)),
                Emu(emu(14)), Emu(emu(14)))
            d.name = f"{eid}__point_{i}"
            d.fill.solid()
            # OS §24：末节点为强调色（accent 是唯一强调语义，primary 通常已被标题占用）
            d.fill.fore_color.rgb = ctx.color("accent") if i == n - 1 else secondary
            d.line.fill.background()
            lb = slide.shapes.add_textbox(
                Emu(emu(cx - w / n / 2)), Emu(emu(axis_y + 16)),
                Emu(emu(w / n)), Emu(emu(h * 0.30)))
            lb.name = f"{eid}__label_{i}"
            p = lb.text_frame.paragraphs[0]
            p.text = row["label"]
            p.alignment = PP_ALIGN.CENTER
            set_para_font(p, latin, cn, px_to_pt(element.get("label_size", 13)), ink, False)
        return

    if kind == "steps":
        n = min(len(rows), 6)
        col_w = w / max(n, 1)
        for i, row in enumerate(rows[:6]):
            cx = x + i * col_w
            nb = slide.shapes.add_textbox(
                Emu(emu(cx)), Emu(emu(y)), Emu(emu(col_w * 0.9)), Emu(emu(44)))
            nb.name = f"{eid}__n_{i}"
            p = nb.text_frame.paragraphs[0]
            p.text = str(i + 1)
            p.alignment = PP_ALIGN.LEFT
            set_para_font(p, latin, cn, px_to_pt(element.get("num_size", 30)), secondary, True)
            tb = slide.shapes.add_textbox(
                Emu(emu(cx)), Emu(emu(y + 48)), Emu(emu(col_w * 0.9)), Emu(emu(h * 0.36)))
            tb.name = f"{eid}__t_{i}"
            p = tb.text_frame.paragraphs[0]
            p.text = row["label"]
            set_para_font(p, latin, cn, px_to_pt(element.get("title_size", 18)), ink, True)
            desc = str(row.get("desc", "") or "").strip()
            if desc:
                db = slide.shapes.add_textbox(
                    Emu(emu(cx)), Emu(emu(y + 48 + h * 0.36)),
                    Emu(emu(col_w * 0.9)), Emu(emu(h * 0.5)))
                db.name = f"{eid}__d_{i}"
                p = db.text_frame.paragraphs[0]
                p.text = desc
                p.line_spacing = pt(float(element.get("desc_size", 14)) * 1.3)
                set_para_font(p, latin, cn, px_to_pt(element.get("desc_size", 14)),
                              muted, False)
            if i < n - 1:
                c = slide.shapes.add_connector(
                    MSO_CONNECTOR.STRAIGHT, Emu(emu(cx + col_w * 0.9)), Emu(emu(y + 22)),
                    Emu(emu(cx + col_w)), Emu(emu(y + 22)))
                c.name = f"{eid}__c_{i}"
                c.line.color.rgb = muted
                c.line.width = Emu(emu(1))
        return

    if kind == "matrix":
        pts = element.get("points", []) or []
        pad_x, pad_y = w * 0.12, h * 0.12
        ox, oy = x + pad_x, y + h - pad_y
        pw, ph = w - pad_x * 1.25, h - pad_y * 1.35
        hx = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Emu(emu(ox)), Emu(emu(oy)), Emu(emu(ox + pw)), Emu(emu(oy)))
        hx.name = f"{eid}__x"
        hx.line.color.rgb = muted
        hx.line.width = Emu(emu(1))
        vy = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Emu(emu(ox)), Emu(emu(oy)), Emu(emu(ox)), Emu(emu(oy - ph)))
        vy.name = f"{eid}__y"
        vy.line.color.rgb = muted
        vy.line.width = Emu(emu(1))
        for i, p0 in enumerate(pts[:12]):
            nx = ox + float(p0["x"]) * pw
            ny = oy - float(p0["y"]) * ph
            d = slide.shapes.add_shape(
                MSO_SHAPE.OVAL, Emu(emu(nx - 7)), Emu(emu(ny - 7)), Emu(emu(14)), Emu(emu(14)))
            d.name = f"{eid}__p_{i}"
            d.fill.solid()
            d.fill.fore_color.rgb = primary if p0.get("highlight") else secondary
            d.line.fill.background()
            lb = slide.shapes.add_textbox(
                Emu(emu(nx + 8)), Emu(emu(ny - 9)), Emu(emu(120)), Emu(emu(22)))
            lb.name = f"{eid}__l_{i}"
            p = lb.text_frame.paragraphs[0]
            p.text = str(p0.get("label", ""))
            set_para_font(p, latin, cn, px_to_pt(11), ink, False)
        return

    if kind == "waterfall":
        # 小计段：row 带 subtotal/is_total/total 时，从零轴起画整段累计，
        # 其余仍是浮动增减（starts=cum, ends=cum+value）。瀑布因此能表达
        # 「明细 → 小计 → 明细」的桥接结构，而不是一列裸柱。
        cum = 0.0
        starts, ends, is_total = [], [], []
        for r in rows:
            total = bool(r.get("subtotal") or r.get("is_total") or r.get("total"))
            if total:
                starts.append(0.0)
                ends.append(cum)
                is_total.append(True)
            else:
                starts.append(cum)
                cum += r["value"]
                ends.append(cum)
                is_total.append(False)
        lo = min(0.0, *starts, *ends)
        hi = max(0.0, *starts, *ends)
        span = max(hi - lo, 1.0)
        plot_h = h * 0.62
        zero_y = y + h * 0.82 - (0.0 - lo) / span * plot_h
        ax = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Emu(emu(x)), Emu(emu(zero_y)),
            Emu(emu(x + w)), Emu(emu(zero_y)))
        ax.name = f"{eid}__axis"
        ax.line.color.rgb = muted
        ax.line.width = Emu(emu(1))
        n = max(len(rows), 1)
        bw = w / n * 0.46
        # 段间桥接虚线：把「上一段的末端」连到「下一段的起端」（浮动层级）。
        # 不跨过小计段——小计从零轴起，本就无需桥接。
        for i in range(len(rows) - 1):
            if is_total[i] or is_total[i + 1]:
                continue
            lvl = ends[i]  # == starts[i+1]
            ry = y + h * 0.82 - (lvl - lo) / span * plot_h
            x0 = x + w * (i + 0.5) / n + bw / 2
            x1 = x + w * (i + 1.5) / n - bw / 2
            if x1 <= x0:
                continue
            conn = slide.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT, Emu(emu(x0)), Emu(emu(ry)),
                Emu(emu(x1)), Emu(emu(ry)))
            conn.name = f"{eid}__conn_{i}"
            conn.line.color.rgb = muted
            conn.line.width = Emu(emu(1))
            try:
                conn.line.dash_style = MSO_LINE_DASH_STYLE.DASH
            except Exception:
                pass
        for i, r in enumerate(rows):
            left = x + w * (i + 0.5) / n - bw / 2
            top = max(starts[i], ends[i])
            bot = min(starts[i], ends[i])
            ry = y + h * 0.82 - (top - lo) / span * plot_h
            rh = max(5, (top - bot) / span * plot_h)
            b = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Emu(emu(left)), Emu(emu(ry)), Emu(emu(bw)), Emu(emu(rh)))
            b.name = f"{eid}__bar_{i}"
            b.fill.solid()
            if is_total[i]:
                b.fill.fore_color.rgb = ctx.color("accent")   # 小计用强调色
            else:
                b.fill.fore_color.rgb = primary if r["value"] >= 0 else secondary
            b.line.fill.background()
            lb = slide.shapes.add_textbox(
                Emu(emu(left - bw * 0.35)), Emu(emu(y + h * 0.82 + 10)),
                Emu(emu(bw * 1.7)), Emu(emu(24)))
            lb.name = f"{eid}__l_{i}"
            p = lb.text_frame.paragraphs[0]
            p.text = r["label"]
            p.alignment = PP_ALIGN.CENTER
            set_para_font(p, latin, cn, px_to_pt(11), ink if is_total[i] else muted,
                          bool(is_total[i]))
        return

    if kind == "architecture":
        layers = element.get("layers") or []
        if not (1 <= len(layers) <= 3):
            ctx.warn(f"chart '{element.get('id')}': architecture 缺少 layers，已跳过（不生成占位层名）", element.get("id"))
            return
        lh = h / len(layers) * 0.6
        for i, lt in enumerate(layers[:3]):
            ly = y + i * h / len(layers) + h / len(layers) * 0.2
            s = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Emu(emu(x + w * 0.12)), Emu(emu(ly)),
                Emu(emu(w * 0.76)), Emu(emu(lh)))
            s.name = f"{eid}__l_{i}"
            fill_rgb = primary if i == 0 else secondary
            s.fill.solid()
            s.fill.fore_color.rgb = fill_rgb
            s.line.fill.background()
            _label(s, str(lt), element, ctx, ctx.auto_text_for(fill_rgb), 15)
        return

    if kind == "ranked_bar":
        # 编辑级排行条：细线轨道 + 圆头条 + 直接数值标注
        data = sorted(rows, key=lambda r: r["value"], reverse=True)
        n = min(len(data), 8)
        data = data[:n]
        label_w = w * float(element.get("label_ratio", 0.24))
        bar_x = x + label_w + float(element.get("label_gap", 24))
        value_w = float(element.get("value_width", 70))
        row_h = h / max(n, 1)
        bar_h = max(6, min(float(element.get("bar_height", 12)), row_h * 0.34))
        # 轨道右缘要同时让出「端点圆点半径 + 间隙 + 数值列」，否则最长的一条
        # 会把数值推出图表边界。
        dot_d = bar_h + 6
        value_gap = float(element.get("value_gap", 10))
        bar_right = x + w - value_w - dot_d / 2 - value_gap
        span = max(bar_right - bar_x, 10)
        maxv = max((r["value"] for r in data), default=1) or 1
        track_c, track_a = ctx.paint("track")
        hairline_c, hairline_a = ctx.paint("hairline")
        hl = highlight_index(element, data, -1)
        # 目标线：在已知刻度（span/maxv）上画一条竖向参考线，标注目标位置。
        # 这是「证据叙事」的可视化语言——让「现在在哪」与「要到哪」可一眼对比。
        target = element.get("target")
        if target is not None:
            try:
                tv = float(target)
                tx = bar_x + span * max(0.0, min(1.0, tv / maxv))
                tl = slide.shapes.add_connector(
                    MSO_CONNECTOR.STRAIGHT, Emu(emu(tx)), Emu(emu(y + 4)),
                    Emu(emu(tx)), Emu(emu(y + h - 4)))
                tl.name = f"{eid}__target"
                tl.line.color.rgb = ctx.color("accent")
                tl.line.width = Emu(emu(1))
                try:
                    tl.line.dash_style = MSO_LINE_DASH_STYLE.DASH
                except Exception:
                    pass
                tlabel = element.get("target_label")
                if tlabel:
                    _textbox(slide, f"{eid}__target_label", tx + 6, y - 2,
                             value_w + 40, 20, str(tlabel), 11,
                             ctx.color("accent"), ctx, element, align=PP_ALIGN.LEFT)
            except (TypeError, ValueError):
                pass
        for i, r in enumerate(data):
            cy = y + row_h * (i + 0.5)
            track = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Emu(emu(bar_x)), Emu(emu(cy - 1)),
                Emu(emu(span)), Emu(emu(2)))
            track.name = f"{eid}__track_{i}"
            solid_fill(track.fill, track_c or hairline_c, track_a or hairline_a)
            track.line.fill.background()
            if r["value"] < 0:
                ctx.warn(f"chart '{element.get('id')}': ranked_bar 第 {i + 1} 行为负值，已不绘制负向长度", element.get("id"))
            bw = span * max(r["value"], 0) / maxv
            color = (ctx.color("accent") if hl in (i, r.get("_index")) else primary)
            bar = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Emu(emu(bar_x)), Emu(emu(cy - bar_h / 2)),
                Emu(emu(max(bw, 4))), Emu(emu(bar_h)))
            bar.name = f"{eid}__bar_{i}"
            solid_fill(bar.fill, color)
            bar.line.fill.background()
            # 端点圆点：编辑级排行的标志（条末端锚点，强化"读到端点"）
            dot_d = bar_h + 6
            dot = slide.shapes.add_shape(
                MSO_SHAPE.OVAL, Emu(emu(bar_x + max(bw, 4) - dot_d / 2)),
                Emu(emu(cy - dot_d / 2)), Emu(emu(dot_d)), Emu(emu(dot_d)))
            dot.name = f"{eid}__dot_{i}"
            solid_fill(dot.fill, color)
            dot.line.fill.background()
            _textbox(slide, f"{eid}__label_{i}", x, cy - row_h / 2, label_w, row_h,
                     r["label"], float(element.get("label_size", 13)), ink, ctx, element,
                     align=PP_ALIGN.RIGHT)
            # 数值必须绕开端点圆点，而不是绕开条末端：圆点半径 = dot_d/2 已经
            # 越过条末端，若只加固定 8px（< 半径）数值会被圆点压住。
            value_gap = float(element.get("value_gap", 10))
            _textbox(slide, f"{eid}__value_{i}",
                     bar_x + max(bw, 4) + dot_d / 2 + value_gap, cy - row_h / 2,
                     value_w, row_h, _display(r, element),
                     float(element.get("value_size", 12)), ink, ctx, element,
                     align=PP_ALIGN.LEFT, bold=True)
        return

    if kind == "progress_bar":
        # 进度条：轨道 + 填充 + 百分比直接标注
        n = min(len(rows), 6)
        data = rows[:n]
        row_h = h / max(n, 1)
        bar_h = max(6, min(float(element.get("bar_height", 10)), row_h * 0.22))
        label_w = w * float(element.get("label_ratio", 0.26))
        bar_x = x + label_w + 16
        value_w = float(element.get("value_width", 78))
        span = max(x + w - value_w - bar_x, 10)
        track_c, track_a = ctx.paint("track")
        for i, r in enumerate(data):
            cy = y + row_h * (i + 0.5)
            top = cy - bar_h / 2
            track = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Emu(emu(bar_x)), Emu(emu(top)),
                Emu(emu(span)), Emu(emu(bar_h)))
            track.name = f"{eid}__track_{i}"
            solid_fill(track.fill, track_c or ctx.color("faint"), track_a)
            track.line.fill.background()
            ceiling = float(r.get("max", element.get("max", 100))) or 100
            if r["value"] < 0:
                ctx.warn(f"chart '{element.get('id')}': progress_bar 第 {i + 1} 行为负值，已按 0% 绘制", element.get("id"))
            ratio = max(0.0, min(1.0, r["value"] / ceiling))
            if ratio > 0:
                fill = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE, Emu(emu(bar_x)), Emu(emu(top)),
                    Emu(emu(max(span * ratio, 4))), Emu(emu(bar_h)))
                fill.name = f"{eid}__fill_{i}"
                solid_fill(fill.fill, ctx.series_color(i) if element.get(
                    "multi_color") else ctx.color("accent"))
                fill.line.fill.background()
            _textbox(slide, f"{eid}__label_{i}", x, cy - row_h / 2, label_w, row_h,
                     r["label"], float(element.get("label_size", 13)), ink, ctx, element,
                     align=PP_ALIGN.RIGHT)
            _textbox(slide, f"{eid}__value_{i}", x + w - value_w, cy - row_h / 2,
                     value_w, row_h, _display(r, element, f"{ratio * 100:.0f}%"),
                     float(element.get("value_size", 12)), ink, ctx, element,
                     align=PP_ALIGN.RIGHT, bold=True)
        return

    if kind == "stacked_bar":
        # 堆叠条：分段 + 直接图例
        negative_rows = [i for i, r in enumerate(rows) if r["value"] < 0]
        if negative_rows:
            ctx.warn(f"chart '{element.get('id')}': stacked_bar 含负值行 {negative_rows}，负值不绘制", element.get("id"))
        total = sum(max(r["value"], 0) for r in rows) or 1
        bar_h = max(18, min(float(element.get("bar_height", 46)), h * 0.34))
        bar_y = y + (h - bar_h) / 2 - (h * 0.10 if element.get("legend") is not False else 0)
        cursor = x
        for i, r in enumerate(rows[:8]):
            seg = w * max(r["value"], 0) / total
            if seg <= 0:
                continue
            s = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Emu(emu(cursor)), Emu(emu(bar_y)),
                Emu(emu(seg)), Emu(emu(bar_h)))
            s.name = f"{eid}__seg_{i}"
            solid_fill(s.fill, ctx.series_color(i) if not element.get(
                "ramp") else ctx.ramp_color(i))
            s.line.fill.background()
            if element.get("show_values", True) and seg > 46:
                pct = r["value"] / total * 100
                _textbox(slide, f"{eid}__seg_label_{i}", cursor, bar_y, seg, bar_h,
                         _display(r, element, f"{pct:.0f}%"),
                         float(element.get("label_size", 12)),
                         ctx.auto_text_for(ctx.series_color(i) if not element.get("ramp") else ctx.ramp_color(i)),
                         ctx, element, align=PP_ALIGN.CENTER, bold=True)
            cursor += seg
        if element.get("legend") is not False:
            ly = bar_y + bar_h + 18
            item_w = 16 + 150
            # 图例与分段位置对应：每项居中于其分段下方（均布会让标签与色块错位）
            seg_starts, cur = [], x
            for r in rows[:8]:
                seg_starts.append((cur, w * max(r["value"], 0) / total))
                cur += w * max(r["value"], 0) / total
            xs = [s_ + sw_ / 2 - item_w / 2 for s_, sw_ in seg_starts]
            if xs and (xs[0] < x or xs[-1] + item_w > x + w or any(
                    xs[i] + item_w > xs[i + 1] for i in range(len(xs) - 1))):
                xs = None  # 分段过窄放不下时回落均布
            lx = x
            for i, r in enumerate(rows[:8]):
                cur_x = xs[i] if xs else lx
                dot = slide.shapes.add_shape(
                    MSO_SHAPE.OVAL, Emu(emu(cur_x)), Emu(emu(ly + 4)), Emu(emu(10)), Emu(emu(10)))
                dot.name = f"{eid}__dot_{i}"
                solid_fill(dot.fill, ctx.series_color(i) if not element.get(
                    "ramp") else ctx.ramp_color(i))
                dot.line.fill.background()
                _textbox(slide, f"{eid}__legend_{i}", cur_x + 16, ly - 4, 150, 22,
                         r["label"], 11, ink, ctx, element)
                lx = cur_x + item_w + 18
        return

    if kind == "big_number_row":
        # 指标行：大数字 + 说明 + 细线分隔
        n = min(len(rows) or len(element.get("items", [])), 5)
        items = rows[:5] or (element.get("items") or [])[:5]
        col_w = w / max(n, 1)
        for i, r in enumerate(items[:n]):
            cx = x + i * col_w
            vw = col_w - 22
            if i > 0:
                rule = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE, Emu(emu(cx - 11)), Emu(emu(y + h * 0.18)),
                    Emu(emu(1.5)), Emu(emu(h * 0.52)))
                rule.name = f"{eid}__rule_{i}"
                hc, ha = ctx.paint("hairline")
                solid_fill(rule.fill, hc or ctx.color("secondary"), ha or 0.28)
                rule.line.fill.background()
            _textbox(slide, f"{eid}__value_{i}", cx + 12, y + h * 0.14, vw, h * 0.40,
                     _display(r, element),
                     float(element.get("value_size", 52)),
                     ctx.color("primary"), ctx, element, bold=True)
            _textbox(slide, f"{eid}__label_{i}", cx + 12, y + h * 0.56, vw, h * 0.30,
                     r.get("label", ""), float(element.get("label_size", 14)),
                     ctx.color("muted"), ctx, element)
        return

    if kind == "bubble":
        negative_rows = [i for i, r in enumerate(rows) if r["value"] < 0]
        if negative_rows:
            ctx.warn(f"chart '{element.get('id')}': bubble 含负值行 {negative_rows}，负值按最小半径绘制", element.get("id"))
        vals = [max(r["value"], 0.01) for r in rows]
        lo, hi = min(vals), max(vals)
        span = max(hi - lo, 0.01)
        cols = math.ceil(math.sqrt(max(len(rows), 1)))
        cw = w / cols
        chh = h / math.ceil(len(rows) / cols)
        for i, r in enumerate(rows[:12]):
            rad = 18 + 34 * (vals[i] - lo) / span
            cx = x + cw * (i % cols + 0.5)
            cy = y + chh * (i // cols + 0.5)
            d = slide.shapes.add_shape(
                MSO_SHAPE.OVAL, Emu(emu(cx - rad)), Emu(emu(cy - rad)),
                Emu(emu(rad * 2)), Emu(emu(rad * 2)))
            d.name = f"{eid}__b_{i}"
            fill_rgb = (primary if i == highlight_index(element, rows, 0)
                        else secondary)
            d.fill.solid()
            d.fill.fore_color.rgb = fill_rgb
            d.line.fill.background()
            _label(d, r["label"], element, ctx, ctx.auto_text_for(fill_rgb), 11)
        return

    if kind == "sparkline":
        # 迷你趋势：去轴折线 + 端点圆点，用于 small multiples（一页多组趋势）。
        # 无轴、无网格、无刻度——只保留「形状」本身，读数交给相邻的直接标注。
        vals = [r["value"] for r in rows]
        n = len(vals)
        if n < 2:
            ctx.warn(f"chart '{element.get('id')}': sparkline 至少需要 2 个数据点", element.get("id"))
            return
        lo = min(vals)
        hi = max(vals)
        span = max(hi - lo, 1e-6)
        pad = float(element.get("pad", 4))
        lw = float(element.get("line_width", 2))
        color = ctx.color(element.get("color")) or primary
        px = [x + pad + (w - 2 * pad) * i / (n - 1) for i in range(n)]
        py = [y + h - pad - (vals[i] - lo) / span * (h - 2 * pad) for i in range(n)]
        base = element.get("baseline")
        if base is not None:
            try:
                by = y + h - pad - (float(base) - lo) / span * (h - 2 * pad)
                bl = slide.shapes.add_connector(
                    MSO_CONNECTOR.STRAIGHT, Emu(emu(x + pad)), Emu(emu(by)),
                    Emu(emu(x + w - pad)), Emu(emu(by)))
                bl.name = f"{eid}__base"
                bl.line.color.rgb = muted
                bl.line.width = Emu(emu(1))
            except (TypeError, ValueError):
                pass
        for i in range(n - 1):
            c = slide.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT, Emu(emu(px[i])), Emu(emu(py[i])),
                Emu(emu(px[i + 1])), Emu(emu(py[i + 1])))
            c.name = f"{eid}__seg_{i}"
            c.line.color.rgb = color
            c.line.width = Emu(emu(lw))
        # 端点圆点：强调「起点→终点」的变化量
        for i in (0, n - 1):
            d = slide.shapes.add_shape(
                MSO_SHAPE.OVAL, Emu(emu(px[i] - 3)), Emu(emu(py[i] - 3)),
                Emu(emu(6)), Emu(emu(6)))
            d.name = f"{eid}__dot_{i}"
            d.fill.solid()
            d.fill.fore_color.rgb = ctx.color("accent") if i == n - 1 else color
            d.line.fill.background()
        if element.get("show_last", True):
            _textbox(slide, f"{eid}__last", px[-1] + 6, py[-1] - 12,
                     float(element.get("last_width", 80)), 20,
                     _display(rows[-1], element),
                     float(element.get("last_size", 13)), ink, ctx, element,
                     align=PP_ALIGN.LEFT, bold=True)
        return


# --------------------------------------------------------------------------
# 图表分发
# --------------------------------------------------------------------------
def add_chart(slide, element: dict, ctx: RenderContext) -> None:
    kind = str(element.get("chart_kind") or element.get("kind", ""))

    if kind in ("kpi", "executive_kpi", "big_number"):
        add_kpi(slide, element, ctx)
        return
    if kind in SHAPE_CHARTS:
        add_shape_chart(slide, element, ctx, kind)
        return
    if kind not in CHART_KINDS:
        ctx.warn(f"chart '{element.get('id')}': 不支持的 chart_kind {kind!r}，已跳过", element.get("id"))
        return
    # schema 白名单已通过；实现映射仍决定是 native 还是可编辑 shape chart。
    if kind not in NATIVE_CHART_TYPES:
        ctx.warn(f"chart '{element.get('id')}': chart_kind {kind!r} 尚未实现，已跳过", element.get("id"))
        return
    add_native_chart(slide, element, ctx)


def add_kpi(slide, element: dict, ctx: RenderContext) -> None:
    """大数字：拆成 value / label 两个可编辑文本框。"""
    x, y, w, h = ctx.bounds(element)
    cn, latin = ctx.families(element)
    primary, _secondary, _ink, muted = chart_colors(element, ctx)
    eid = str(element.get("id", "kpi"))
    align = element.get("align", "left")

    value_text = str(element.get("value", "") or "").strip()
    label_text = str(element.get("label", "") or "").strip()

    vb = slide.shapes.add_textbox(
        Emu(emu(x)), Emu(emu(y)), Emu(emu(w)), Emu(emu(h * 0.62)))
    vb.name = f"{eid}__value"
    p = vb.text_frame.paragraphs[0]
    p.alignment = align_of(align, PP_ALIGN.LEFT)
    if value_text:
        p.text = value_text
        set_para_font(p, latin, cn, px_to_pt(element.get("value_size", 56)), primary, True)

    lb = slide.shapes.add_textbox(
        Emu(emu(x)), Emu(emu(y + h * 0.66)), Emu(emu(w)), Emu(emu(h * 0.30)))
    lb.name = f"{eid}__label"
    p2 = lb.text_frame.paragraphs[0]
    p2.alignment = align_of(align, PP_ALIGN.LEFT)
    if label_text:
        p2.text = label_text
        set_para_font(p2, latin, cn, px_to_pt(element.get("label_size", 16)), muted, False)


# ══════════════════ Layer 3 · Compiler（编排层）══════════════════

COMPILER_VERSION = "1.1"

import sys

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from pptx import Presentation  # noqa: E402

# 元素类型 → 绘制层函数（编排层只做映射，改绘制实现不影响此表）
DISPATCH = {
    "text": add_text,
    "shape": add_shape,
    "image": add_image,
    "chart": add_chart,
    "native_chart": add_chart,
}


_FIXED_ZIP_STAMP = (1980, 1, 1, 0, 0, 0)   # ZIP epoch：产物字节与编译时刻无关
_EMBEDDED_OOXML = (".xlsx", ".xlsm", ".docx", ".pptx")


def _normalize_embedded_ooxml(blob: bytes) -> bytes:
    """内嵌 OOXML（图表工作簿）去时间化。

    python-pptx 每次编译都把内嵌工作簿的 `dcterms:created/modified` 写成「当前时间」，
    于是同一份 spec 隔一秒编译就得到不同字节：产物戳失去意义、编译缓存与预览缓存
    的无变化复用随机失效。这里把内嵌包的时间戳与 core 时间统一压到固定值，
    让「相同的输入」真的产出「相同的字节」。任何异常都退回原字节（不冒险改坏产物）。
    """
    import io as _io
    import re as _re
    import zipfile as _zip
    stamp = _re.compile(r"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)")
    try:
        with _zip.ZipFile(_io.BytesIO(blob)) as zin:
            buf = _io.BytesIO()
            with _zip.ZipFile(buf, "w", _zip.ZIP_DEFLATED) as zout:
                for sub in zin.infolist():
                    data = zin.read(sub.filename)
                    if sub.filename == "docProps/core.xml":
                        text = data.decode("utf-8")
                        fixed = stamp.sub(r"\g<1>1980-01-01T00:00:00Z\g<2>", text)
                        data = fixed.encode("utf-8")
                    sub.date_time = _FIXED_ZIP_STAMP
                    zout.writestr(sub, data)
            return buf.getvalue()
    except Exception:
        return blob


def _postprocess_package(output_path, *, media_stored: bool = True) -> dict:
    """包级后处理（一次解包，一次写回）：

    1. 主题投影：默认 Office 主题的 effectStyleLst 携带 outerShdw，部分阅读器
       会无视 spPr 的空 effectLst 仍套用投影 → 直接在 theme XML 移除 outerShdw。
    2. 空 run：`<a:t></a:t>` 是「有对象、没内容」的痕迹，部分阅读器会渲染成空行/
       占位方框。统一剔除空 run（不删形状），让每个残留对象都有来源。
    3. 时间戳归零：python-pptx 写 zip 时用「当前本地时间」做条目时间；内嵌图表工作簿
       更是把 `dcterms:created/modified` 写成当前时间。同一份 spec 隔一秒编译就得到
       不同字节——产物戳失去意义，编译缓存与预览缓存的无变化复用随机失效。
       外层与内嵌包一并压到固定时间，产物字节只由内容决定。

    `media_stored`（v5.9 起默认开）：图片/字体等**已经压缩过**的二进制条目按
    STORED 直存。此前整包一律 DEFLATED，于是 5–40MB 的 PNG/JPEG 被完整解压再
    重新压缩一遍，纯属浪费——它们几乎不可再压缩，只是把交付链拖慢。
    XML 仍走 DEFLATE（体积敏感，且本来就是小文本）。
    """
    import re as _re
    import time as _time
    import zipfile as _zip
    import shutil as _shutil
    path = Path(output_path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    empty_run = _re.compile(r"<a:r>(?:(?!</a:r>).)*?<a:t(?:\s[^>]*)?>\s*</a:t>"
                            r"(?:(?!</a:r>).)*?</a:r>", _re.S)
    t0 = _time.perf_counter()
    media_written = media_passthrough = 0
    with _zip.ZipFile(path) as zin, _zip.ZipFile(tmp, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            compression = _zip.ZIP_DEFLATED
            if item.filename.endswith(_EMBEDDED_OOXML):
                data = _normalize_embedded_ooxml(data)
            if media_stored and not item.filename.endswith((".xml", ".rels")) \
                    and not item.filename.endswith(_EMBEDDED_OOXML):
                # 媒体/字体：直存。字节完全相同，只是不再做无收益的二次压缩。
                compression = _zip.ZIP_STORED
                media_passthrough += 1
            if item.filename.endswith(".xml") and item.filename.startswith("ppt/"):
                text = data.decode("utf-8")
                stripped = text
                if item.filename.startswith("ppt/theme/"):
                    stripped = _re.sub(r"<a:outerShdw\b.*?</a:outerShdw>", "", stripped,
                                       flags=_re.S)
                if "<a:r>" in stripped:
                    stripped = empty_run.sub("", stripped)
                if stripped != text:
                    data = stripped.encode("utf-8")
            item.date_time = _FIXED_ZIP_STAMP
            item.compress_type = compression
            zout.writestr(item, data)
    _shutil.move(str(tmp), str(path))
    return {"package_ms": round((_time.perf_counter() - t0) * 1000, 2),
            "media_entries_stored": media_passthrough}


def compile_deck(spec: dict, output_path, checks: bool = True,
                 guard_rules: dict | None = None, spec_path: str | None = None,
                 image_bytes: dict | None = None, speed: str = "strict",
                 decode_seed: dict | None = None) -> dict:
    """
    把设计 spec 编译为原生可编辑 PPTX。

    spec（全部由调用方传入，引擎不持有任何主题）：
      canvas : {"width":1280,"height":720}            可选
      theme  : {"colors":{...},"fonts":{...},...}      设计身份
      slides : [{"id","background","elements":[...]}]  页面与元素

    checks=True（默认）时先做静态治理（engine/guard.py，OS 硬约束断言），
    静态问题以 [guard] 前缀并入 warnings；guard_rules 可配置治理阈值。
    返回契约不变：{"passed","slides","warnings","file_bytes"}；
    启用 checks 时追加 "guard"（治理明细），旧调用不受影响。

    speed="fast"（v5.9）时：图片变换用低压缩级别编码，包级后处理仍做
    （时间戳与 XML 规格不变，产物仍确定性），只是不再为媒体条目重复压缩。
    speed="strict" 保留原压缩级别。两条路径的**可见结果一致**，差异只在耗时与字节。
    """
    output_path = Path(output_path)
    _spec_warning = None
    if not isinstance(spec, dict):
        _spec_warning = "spec 顶层必须是对象/dict，已按空 spec 处理"
        spec = {}
    raw_canvas = spec.get("canvas")
    canvas = dict(raw_canvas) if isinstance(raw_canvas, dict) else {}
    if raw_canvas is not None and not isinstance(raw_canvas, dict):
        _spec_warning = "spec.canvas 必须是对象/dict，已使用默认画布"
    canvas_warnings = []
    for key, default in (("width", DEFAULT_WIDTH), ("height", DEFAULT_HEIGHT)):
        try:
            value = float(canvas.get(key, default))
            if not math.isfinite(value) or value <= 0:
                raise ValueError
            canvas[key] = value
        except (TypeError, ValueError, OverflowError):
            canvas[key] = default
            canvas_warnings.append(f"canvas.{key} 非法，已回落 {default}")
    theme = spec.get("theme") if isinstance(spec.get("theme"), dict) else {}

    ctx = RenderContext(theme, canvas)
    ctx.image_bytes = image_bytes or {}
    # 「核验字节快照」是**给了就必须够用**：调用方声明「这些字节已经读过一遍」时，
    # 缺一份就说明读取与使用不是同一批事实（不许悄悄再读一遍掩盖不一致）。
    # 但「一次也没给」是合法情形——判定被复用时本来就没有读字节，此时编译器
    # 自己读文件（一次读，不是重复读）。空 dict 与「没给」在这一点上等价。
    ctx.require_snapshot = bool(image_bytes)
    # 速度档与 per-compile 图片变换缓存：同一张图在同一盒子里只变换一次。
    ctx.speed = "fast" if str(speed).lower() == "fast" else "strict"
    ctx.image_transform_cache = {}
    # 解码底图：资产核验阶段已经为核验解码过一次（`decode_seed`，键为解析后的源路径），
    # 同一张 4K 图在这里就不必再解一遍——这是全链最后一块重复解码。
    ctx.image_decode_cache = dict(decode_seed) if decode_seed else {}
    ctx.timings = {}
    if _spec_warning:
        ctx.warn(_spec_warning)
    for _warning in canvas_warnings:
        ctx.warn(_warning)

    guard = None
    if checks:
        from guard import check_spec
        guard = check_spec(spec, rules=guard_rules)
        for w in guard["warnings"]:
            ctx.warn(f"[guard] {w}")

    prs = Presentation()
    prs.slide_width = Emu(emu(canvas["width"]))
    prs.slide_height = Emu(emu(canvas["height"]))
    blank = prs.slide_layouts[6]

    slides = spec.get("slides") or []
    if not isinstance(slides, list):
        ctx.warn("spec.slides 必须是数组/list，已按空 deck 处理")
        slides = []
    for si, slide_spec in enumerate(slides):
        slide = prs.slides.add_slide(blank)
        if not isinstance(slide_spec, dict):
            ctx.warn(f"slide[{si}] 必须是对象/dict，已保留空白页")
            continue
        bg = slide_spec.get("background", ctx.colors.get("background"))
        applied = False
        if bg is not None:
            # 支持纯色 / 带透明度 / 渐变背景（渐变用于营造方向性光影空间）
            try:
                apply_fill(slide.background, bg, ctx)
                applied = True
            except Exception as exc:
                ctx.warn(f"slide[{si}] '{slide_spec.get('id')}': "
                         f"background={bg!r} 渲染失败（{exc}）")
        # 安全网：仅当主应用失败时才回落到纯色。
        # 注意必须用「成功标志」而不是检查 <p:cSld> 直接子元素——
        # 否则会把已正确写入 <p:bgPr> 的渐变误判为空并用纯色覆盖。
        if not applied:
            try:
                apply_fill(slide.background, "background", ctx)
            except Exception as exc:
                ctx.warn(f"slide[{si}] 背景回退失败（{exc}）")

        _raw_elements = slide_spec.get("elements") or []
        if not isinstance(_raw_elements, list):
            ctx.warn(f"slide[{si}].elements 必须是数组/list，已按空页处理")
            _raw_elements = []
        _ordered = list(_raw_elements)
        # z-order 安全网：声明为 background/backdrop 层的画心永远先绘制，
        # 使文字与图表稳定位于其上；作者无需记忆元素顺序。
        _ordered.sort(key=lambda e: 0 if isinstance(e, dict) and (
            str(e.get("layer", "")).lower() in {"background", "backdrop"}
            or str(e.get("role", "")).lower() in {"background", "backdrop"}) else 1)
        for ei, element in enumerate(_ordered):
            if not isinstance(element, dict):
                ctx.warn(f"slide[{si}].elements[{ei}]: 元素必须是对象/dict，已跳过")
                continue
            fn = DISPATCH.get(str(element.get("type", "text")))
            if fn is None:
                ctx.warn(f"slide[{si}].elements[{ei}]: 未知 type="
                         f"{element.get('type')!r}，已跳过")
                continue
            try:
                if fn is add_image:
                    fn(slide, element, ctx, str(output_path), spec_path)
                else:
                    fn(slide, element, ctx)
            except Exception as exc:  # 只记录，不静默改稿
                ctx.warn(f"slide[{si}].elements[{ei}] ({element.get('id')}): {exc}",
                         element.get("id") if isinstance(element, dict) else None)

        # Quiet-luxury 硬约束：主题默认 effectStyleLst 会给一切形状/连接线/图片
        # 继承标准 Office 投影，编辑式版面会显得廉价。统一移除继承，
        # 深度感交给色阶、留白与细线，而不是投影。
        for _shp in slide.shapes:
            try:
                _shp.shadow.inherit = False
            except Exception:
                pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    t_save = time.perf_counter()
    prs.save(str(output_path))
    save_ms = (time.perf_counter() - t_save) * 1000
    package = _postprocess_package(output_path)
    report = {
        "passed": len(ctx.warnings) == 0,
        "slides": len(slides),
        "warnings": list(ctx.warnings),
        # 与 warnings 等长的元素 id（无身份处为 None）：让 qa 的 fix_plan
        # 能按元素分组，而不是从文案里正则猜 id。旧读法读 warnings 即可，不受影响。
        "warning_ids": list(ctx.warning_ids),
        "file_bytes": output_path.stat().st_size,
        "output_path": str(output_path),
        "output_exists": output_path.exists(),
    }
    if guard is not None:
        report["guard"] = {"checks": guard["checks"],
                           "passed": guard["passed"]}
    # 编译内部计时：让「慢在哪里」是数出来的，不是猜出来的（进 repair packet.performance）。
    report["performance"] = {
        "speed": ctx.speed,
        "image_transform_ms": round(ctx.timings.get("image_transform_ms", 0.0), 2),
        "image_transforms": ctx.timings.get("image_transforms", 0),
        "image_transform_reuses": ctx.timings.get("image_transform_reuses", 0),
        "image_decode_reuses": ctx.timings.get("image_decode_reuses", 0),
        "save_ms": round(save_ms, 2),
        "package_ms": package["package_ms"],
        "media_entries_stored": package["media_entries_stored"],
    }
    return report




