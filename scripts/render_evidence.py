# -*- coding: utf-8 -*-
"""第三层证据：用**替代引擎**把交付的 PPTX 真正渲染成逐页图像。

它不是第二个生产入口，也不出结论——`vao.py` 仍然是唯一生产入口，判定仍只有
`PASS / BLOCK`（由 verify 给出）。本模块只做一件事：把「这一份 PPTX 在某一个
真实排版引擎下画出来是什么样」变成可复验的凭证（页图 + 逐页 SHA-256 + 引擎指纹），
让下面这句话不再只是声明：

    结构预览（ghost，PIL 近似）≠ 真实排版引擎的实际呈现 ≠ 目标 PowerPoint 验收

证据分层（与 SKILL.md §6 一致）：

    selftest 代码测试
      → ghost 结构预览（方向证据，近似字面）
      → **本模块：替代引擎实际渲染**（真实排版引擎，但不是目标 PowerPoint）
      → 目标 Microsoft PowerPoint 打开/编辑/另存/重开
      → 独立视觉评审

本模块**不消费也不签署**最后两层：记录里 `target_powerpoint / native_editing /
independent_visual_review` 恒为未验证，任何自动化 PASS 都不能把它们升级。

用法：

    python scripts/render_evidence.py out.pptx --out evidence/
    python scripts/render_evidence.py build.py --out evidence/      # 现场编译再渲染

退出码：0 = 已产出页图凭证；3 = 环境里没有可用渲染器（**不是通过**，是没有证据）；
2 = 渲染或读输入失败。缺渲染器时不会写出一份看起来合格的凭证。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "vao-render-evidence-v1"

# 替代引擎的探测顺序：PATH 优先，然后各平台常见安装位置。找不到就是没有证据，
# 不静默降级成「看起来通过了」。
_SOFFICE_CANDIDATES = (
    "soffice",
    "/usr/bin/soffice",
    "/usr/lib/libreoffice/program/soffice",
    "/snap/bin/libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)
_RASTERIZERS = ("pdftoppm", "pdftocairo")

# 一句话讲清这份凭证的边界，随记录一起落盘（避免记录被判成目标环境证明）。
_CLAIM = ("本记录证明：该 PPTX 在下面这个替代引擎下被实际排版并逐页栅格化，"
          "页图与摘要可复验。它不证明目标 Microsoft PowerPoint 的排版结果，"
          "不证明原生编辑往返，也不构成视觉终验。")


def _find_soffice() -> str | None:
    for cand in _SOFFICE_CANDIDATES:
        if os.path.sep in cand or cand.endswith(".exe"):
            if Path(cand).exists():
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found
    return None


def renderer_fingerprint() -> dict:
    """渲染器指纹：名字/版本/路径。没有渲染器时返回 available=False（不是失败）。"""
    soffice = _find_soffice()
    if not soffice:
        return {"available": False, "engine": None, "version": None, "path": None,
                "rasterizer": None}
    version = None
    try:
        out = subprocess.run([soffice, "--version"], capture_output=True, text=True,
                             timeout=60, check=False)
        version = (out.stdout or out.stderr or "").strip().splitlines()[0] if (
            out.stdout or out.stderr) else None
    except (OSError, subprocess.SubprocessError):
        version = None
    raster = next((name for name in _RASTERIZERS if shutil.which(name)), None)
    return {"available": True, "engine": "libreoffice", "version": version,
            "path": str(soffice), "rasterizer": raster}


def _run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def _sha256(path: Path) -> str:
    from primitives import file_digest
    return file_digest(path) or ""


def _to_pdf(soffice: str, pptx: Path, work: Path, timeout: float) -> tuple[Path | None, str]:
    """PPTX → PDF。用私有 UserInstallation：不碰用户正在运行的 LO 实例。

    这一步在 Windows 上尤其重要——共用 profile 会让转换静默失败或挂住。
    """
    profile = work / "lo-profile"
    # as_uri() 是唯一跨平台正确的 file:// 形式（Windows 上要 file:///C:/…，
    # 手拼 "file://" + 盘符路径会被引擎当成无效 profile 而静默失败）。
    cmd = [soffice, "--headless", "--norestore", "--nolockcheck", "--nodefault",
           f"-env:UserInstallation={profile.resolve().as_uri()}",
           "--convert-to", "pdf", "--outdir", str(work), str(pptx)]
    try:
        done = _run(cmd, timeout)
    except subprocess.TimeoutExpired:
        return None, f"渲染超时（{timeout:.0f}s）"
    pdf = work / (pptx.stem + ".pdf")
    if not pdf.exists():
        tail = ((done.stderr or "") + (done.stdout or "")).strip()[-400:]
        return None, f"未产出 PDF：{tail or '引擎没有输出'}"
    return pdf, ""


def _to_pages(pdf: Path, out_dir: Path, dpi: int, rasterizer: str,
              timeout: float) -> tuple[list[Path], str]:
    prefix = out_dir / "page"
    if rasterizer == "pdftoppm":
        cmd = [rasterizer, "-r", str(dpi), "-png", str(pdf), str(prefix)]
    else:
        cmd = [rasterizer, "-png", "-r", str(dpi), str(pdf), str(prefix)]
    try:
        done = _run(cmd, timeout)
    except subprocess.TimeoutExpired:
        return [], f"栅格化超时（{timeout:.0f}s）"
    pages = sorted(out_dir.glob("page-*.png"),
                   key=lambda p: int("".join(ch for ch in p.stem if ch.isdigit()) or 0))
    if not pages:
        tail = ((done.stderr or "") + (done.stdout or "")).strip()[-400:]
        return [], f"未产出台图：{tail or '栅格化器没有输出'}"
    return pages, ""


def _image_size(path: Path) -> list[int] | None:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return [int(im.width), int(im.height)]
    except Exception:
        return None


def collect_evidence(source: str | Path, out_dir: str | Path, *, dpi: int = 96,
                     timeout: float = 300.0, keep_pdf: bool = True) -> dict:
    """渲染一份 PPTX（或现场编译一份 build.py）并记录逐页凭证。

    返回的字典就是落盘的 `render_evidence.json`：它只描述**观察到的事实**
    （引擎、版本、页数、每页摘要），不给出通过与否的判断。
    """
    started = time.perf_counter()
    src = Path(source).expanduser().resolve()
    out = Path(out_dir).expanduser().resolve()
    record: dict = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(src),
        "claim": _CLAIM,
        "status": None,
        "issues": [],
        "renderer": renderer_fingerprint(),
        "dpi": dpi,
        "pptx": None,
        "pdf": None,
        "pages": [],
        "unverified": {
            "target_powerpoint": "未验证：需要目标 Microsoft PowerPoint 打开该产物",
            "native_editing": "未验证：需要打开→修改→另存→重开确认原生对象可编辑",
            "independent_visual_review": "未验证：需要独立评审按 SKILL.md 停止信号逐页判断",
        },
        "timing_ms": {},
    }

    if not record["renderer"]["available"]:
        record["status"] = "UNAVAILABLE"
        record["issues"].append(
            "环境里没有可用渲染器（LibreOffice/soffice 未安装）：本轮**没有**第三层证据，"
            "这不是通过，也不能拿结构预览顶替。")
        return record

    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vao-render-") as td:
        work = Path(td)
        # 输入可以是交付的 PPTX，也可以是作者的 build.py（现场编译，便于回归）。
        pptx = src
        t0 = time.perf_counter()
        if src.suffix.lower() == ".py":
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import vao  # 与生产同一份编译路径，不另写一个编译器
            from compiler import compile_deck
            spec, _ = vao.load_spec(src)
            pptx = work / (src.stem + ".pptx")
            report = compile_deck(spec, str(pptx), spec_path=str(src))
            if not pptx.exists():
                record["status"] = "FAILED"
                record["issues"].append(f"编译未产出 PPTX：{report}")
                return record
            record["compiled_from"] = str(src)
        record["timing_ms"]["compile"] = round((time.perf_counter() - t0) * 1000, 2)
        if not pptx.exists():
            record["status"] = "FAILED"
            record["issues"].append(f"输入不存在：{pptx}")
            return record

        t0 = time.perf_counter()
        pdf, err = _to_pdf(record["renderer"]["path"], pptx, work, timeout)
        record["timing_ms"]["pdf"] = round((time.perf_counter() - t0) * 1000, 2)
        if pdf is None:
            record["status"] = "FAILED"
            record["issues"].append(err)
            record["pptx"] = {"path": str(pptx), "sha256": _sha256(pptx),
                              "size": pptx.stat().st_size}
            return record

        record["pptx"] = {"path": str(pptx), "sha256": _sha256(pptx),
                          "size": pptx.stat().st_size}
        record["pdf"] = {"sha256": _sha256(pdf), "size": pdf.stat().st_size}
        if keep_pdf:
            kept = out / (src.stem + ".render.pdf")
            shutil.copyfile(pdf, kept)
            record["pdf"]["path"] = str(kept)

        raster = record["renderer"]["rasterizer"]
        if not raster:
            # 没有栅格化器就不假装有页图：PDF 仍是一份真实排版证据，明确记录边界。
            record["status"] = "PDF_ONLY"
            record["issues"].append(
                "环境里没有 pdftoppm/pdftocairo：只保留 PDF 排版凭证，未产出逐页图像。")
            return record

        t0 = time.perf_counter()
        pages, err = _to_pages(kept if keep_pdf else pdf, out, dpi, raster, timeout)
        record["timing_ms"]["raster"] = round((time.perf_counter() - t0) * 1000, 2)
        if not pages:
            record["status"] = "FAILED"
            record["issues"].append(err)
            return record

        for index, page in enumerate(pages, 1):
            entry = {"index": index, "file": str(page), "sha256": _sha256(page),
                     "size": page.stat().st_size}
            size = _image_size(page)
            if size:
                entry["dimensions"] = size
            record["pages"].append(entry)

    record["status"] = "COLLECTED"
    record["timing_ms"]["total"] = round((time.perf_counter() - started) * 1000, 2)
    return record


def write_evidence(record: dict, out_dir: str | Path) -> Path:
    out = Path(out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    target = out / "render_evidence.json"
    target.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return target


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    parser = argparse.ArgumentParser(
        description="替代引擎真实渲染取证（第三层证据；不出 PASS/BLOCK）")
    parser.add_argument("source", help="交付的 .pptx，或作者的 build.py（现场编译）")
    parser.add_argument("--out", default="render_evidence", help="页图与凭证目录")
    parser.add_argument("--dpi", type=int, default=96)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--json", action="store_true", help="把完整记录打到 stdout")
    args = parser.parse_args(argv)

    record = collect_evidence(args.source, args.out, dpi=args.dpi, timeout=args.timeout)
    path = write_evidence(record, args.out)
    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=1))
    else:
        renderer = record["renderer"]
        print(f"render-evidence: {record['status']} · "
              f"{renderer.get('version') or '无渲染器'} · {len(record['pages'])} 页")
        print(f"  record: {path}")
        for issue in record["issues"]:
            print(f"  ! {issue}")
        if record["status"] == "COLLECTED":
            print("  边界：替代引擎的实际排版，不是目标 PowerPoint 验收；"
                  "target_powerpoint / native_editing / independent_visual_review 仍未验证。")
    if record["status"] in ("COLLECTED", "PDF_ONLY"):
        return 0
    if record["status"] == "UNAVAILABLE":
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
