# -*- coding: utf-8 -*-
"""
Layer 3.5 · Render Check（渲染证据层）

职责：把编译出的 PPTX **真实渲染成像素**，测量页面视觉证据——
占用率、边缘活动度、亮度、显著性质心、强调色像素比、背景亮度。
这是「只有真实渲染才能证明视觉质量」的实证层（借鉴 v6.2 render_evidence 思路），
但与引擎一样：不做设计决策、不修改 spec、所有阈值由调用方传入。

渲染链路（可用性检测，缺一环即优雅降级为结构证据）：
    soffice/libreoffice --headless → PDF
    → pdftoppm → PNG
    → PIL + numpy 测量（cv2 可用时显著图更准，不可用时用确定性回退）

无渲染环境时：rendered=False，QA 自动跳过渲染维度，不阻塞静态治理。
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from primitives import DEFAULT_WIDTH, DEFAULT_HEIGHT


def find_renderer() -> str | None:
    """定位 LibreOffice。Windows: soffice.exe；POSIX: soffice。"""
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for cand in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice", "/usr/local/bin/soffice",
    ):
        if Path(cand).exists():
            return cand
    return None


def render_to_images(pptx: Path, out_dir: Path, dpi: int = 96) -> tuple[list[Path], str | None]:
    """
    PPTX → PNG 序列。返回 (pages, reason)；reason=None 表示成功。
    无 LibreOffice / pdftoppm 时返回 ([], 原因)。
    """
    soffice = find_renderer()
    if soffice is None:
        return [], "no libreoffice"
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm is None:
        return [], "no pdftoppm"

    out_dir.mkdir(parents=True, exist_ok=True)
    profile = out_dir / "lo-profile"
    profile.mkdir(exist_ok=True)
    try:
        subprocess.run(
            [soffice, "--headless",
             f"-env:UserInstallation=file://{profile}",
             "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx)],
            check=True, capture_output=True, timeout=300)
    except Exception as exc:
        return [], f"libreoffice convert failed: {exc}"
    pdf = out_dir / f"{pptx.stem}.pdf"
    if not pdf.exists():
        return [], "pdf not produced"
    subprocess.run(
        [pdftoppm, "-png", "-r", str(dpi), str(pdf), str(out_dir / "page")],
        check=True, capture_output=True, timeout=300)
    pages = sorted(out_dir.glob("page-*.png"))
    return pages, None


# --------------------------------------------------------------------------
# 像素测量（PIL + numpy；cv2 可用时显著图更准）
# --------------------------------------------------------------------------
def _load_rgb(path: Path, max_side: int = 640) -> Any:
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("RGB")
    scale = min(1.0, max_side / max(im.size))
    if scale < 1:
        im = im.resize((max(1, int(im.width * scale)),
                        max(1, int(im.height * scale))), Image.Resampling.LANCZOS)
    return np.asarray(im).astype(np.float32)


def _saliency(arr: Any) -> Any:
    """显著图：局部对比 + 边缘能量 + 与背景的全局对比（确定性回退，不依赖 cv2）。"""
    import numpy as np
    try:
        import cv2
        bgr = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2BGR)
        sal = cv2.saliency.StaticSaliencySpectralResidual_create()[1].computeSaliency(bgr)[1]
        sal = sal.astype(np.float32)
        return sal / max(float(sal.max()), 1e-6)
    except Exception:
        pass
    g = arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114
    # 盒式模糊近似局部均值（局部对比项）
    from PIL import ImageFilter
    blur = np.asarray(Image.fromarray(g.astype(np.uint8)).filter(
        ImageFilter.BoxBlur(2))).astype(np.float32)
    local = np.abs(g - blur)
    gy, gx = np.gradient(g)
    edge = np.sqrt(gx * gx + gy * gy)
    # 全局对比项：与四角背景亮度的差异（均匀大色块也因此显著）
    corners = np.concatenate([g[:6, :6].ravel(), g[:6, -6:].ravel(),
                              g[-6:, :6].ravel(), g[-6:, -6:].ravel()])
    bg = float(np.median(corners))
    contrast = np.abs(g - bg)
    sal = local + 0.35 * edge + 0.60 * (contrast / max(np.max(contrast), 1e-6))
    p = np.percentile(sal, [5, 95])
    return np.clip((sal - p[0]) / max(p[1] - p[0], 1e-6), 0, 1)


def measure_image(path: Path) -> dict[str, Any]:
    """单页真实渲染测量。"""
    import numpy as np
    arr = _load_rgb(path)
    h, w, _ = arr.shape

    small = np.asarray(Image.fromarray(arr.astype(np.uint8)).resize(
        (96, 54), Image.Resampling.BILINEAR)).astype(np.float32)
    gray = small[..., 0] * 0.299 + small[..., 1] * 0.587 + small[..., 2] * 0.114
    brightness = float(gray.mean() / 255.0)
    gx = np.abs(np.diff(gray, axis=1)).mean()
    gy = np.abs(np.diff(gray, axis=0)).mean()
    edge = float(min(1.0, (gx + gy) / 55.0))

    corners = np.concatenate([gray[:6, :6].ravel(), gray[:6, -6:].ravel(),
                              gray[-6:, :6].ravel(), gray[-6:, -6:].ravel()])
    bg = float(np.median(corners))
    occupancy = float(np.mean(np.abs(gray - bg) > 10))

    sal = _saliency(arr)
    yy, xx = np.mgrid[0:sal.shape[0], 0:sal.shape[1]]
    total = float(sal.sum()) + 1e-6
    cx = float((xx * sal).sum() / total) / max(1, sal.shape[1] - 1)
    cy = float((yy * sal).sum() / total) / max(1, sal.shape[0] - 1)

    rgb = arr / 255.0
    mx = rgb.max(2)
    mn = rgb.min(2)
    sat = np.where(mx == 0, 0, (mx - mn) / np.maximum(mx, 1e-6))
    accent_pixels = float(np.mean(sat > 0.42))

    return {
        "brightness": round(brightness, 3),
        "edge": round(edge, 3),
        "occupancy": round(occupancy, 3),
        "saliency_centroid": [round(cx, 3), round(cy, 3)],
        "accent_pixel_ratio": round(accent_pixels, 3),
        "background_luma": round(bg / 255.0, 3),
    }


# --------------------------------------------------------------------------
# 综合证据：渲染 + 与 spec 声明的锚点对比（gravity drift）
# --------------------------------------------------------------------------
def _element_center(e: dict, cw: float, ch: float) -> tuple[float, float] | None:
    try:
        x = float(e.get("x", 0)) + float(e.get("width", 0)) / 2
        y = float(e.get("y", 0)) + float(e.get("height", 0)) / 2
        return x / cw, y / ch
    except (TypeError, ValueError):
        return None


def render_evidence(pptx: Path, spec: dict, out_dir: Path | None = None,
                    dpi: int = 96) -> dict[str, Any]:
    """
    编译产物 + spec → 每页渲染证据。
    返回 {"rendered": bool, "reason": str|None, "pages": [...]}
    pages[i] 与 spec.slides[i] 一一对应。
    """
    work = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="pptx-render-"))
    work.mkdir(parents=True, exist_ok=True)
    pages, reason = render_to_images(Path(pptx), work, dpi)
    if not pages:
        return {"rendered": False, "reason": reason, "pages": []}

    canvas = spec.get("canvas") or {}
    cw = float(canvas.get("width", DEFAULT_WIDTH))
    ch = float(canvas.get("height", DEFAULT_HEIGHT))
    slides = spec.get("slides") or []

    out = []
    for i, png in enumerate(pages):
        item = {"slide": (slides[i].get("id") if i < len(slides) else f"page_{i}"),
                "index": i, **measure_image(png)}
        # 与 spec 声明锚点对比：取第一锚点（id 含 hero/title/kpi 或首个 chart）
        if i < len(slides):
            elems = slides[i].get("elements", []) or []
            anchor = None
            for e in elems:
                if not isinstance(e, dict):
                    continue
                if e.get("type") in ("chart", "native_chart", "image") or \
                   str(e.get("id", "")).lower() in ("hero", "title", "kpi"):
                    anchor = e
                    break
            if anchor:
                c = _element_center(anchor, cw, ch)
                if c:
                    sc = item["saliency_centroid"]
                    drift = ((c[0] - sc[0]) ** 2 + (c[1] - sc[1]) ** 2) ** 0.5
                    item["anchor_id"] = anchor.get("id")
                    item["anchor_center"] = [round(c[0], 3), round(c[1], 3)]
                    item["gravity_drift"] = round(drift, 3)
        out.append(item)
    return {"rendered": True, "reason": None, "pages": out}


# --------------------------------------------------------------------------
# 可选 CLI： python render_check.py deck.pptx build_mydeck.py [out_dir]
# --------------------------------------------------------------------------
def main(argv):
    import json
    if len(argv) < 3:
        print("usage: python render_check.py <deck.pptx> <build_module.py> [out_dir]")
        return 1
    import importlib.util
    pptx = Path(argv[1])
    mod_path = Path(argv[2])
    spec_mod = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    mod = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    out = Path(argv[3]) if len(argv) > 3 else None
    result = render_evidence(pptx, spec, out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
