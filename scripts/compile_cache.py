# -*- coding: utf-8 -*-
"""轻量 PPTX 编译缓存。

这是 draft QA 唯一需要的缓存部分，故意不导入 PIL、numpy、LibreOffice
或 render_check。像素渲染缓存仍属于 review/release 的 render_check。
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

RENDER_META_NAME = "render_meta.json"
# 编译器/底层 primitives 改变时，即使 spec 的像素投影不变，旧 PPTX 也不能继续冒充
# 当前引擎产物。把实现指纹放进 view，而不是依赖手工清缓存。
CACHE_ENGINE_FILES = ("compiler.py", "primitives.py")
CACHE_VIEW_VERSION = 5
NON_PIXEL_SLIDE_KEYS = (
    "page_intent", "source_zone", "notes", "speaker_notes", "comment",
    "comments", "annotations", "id", "label",
)
NON_PIXEL_THEME_KEYS = (
    "constraints", "notes", "description", "name", "metadata",
    "provenance", "id",
)


def _file_sha(path: Path) -> str | None:
    """短指纹：用于页/PDF 缓存键与旧 metadata 兼容。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except Exception:
        return None


def _file_sha_full(path: Path) -> str | None:
    """完整 SHA-256：编译产物 attestation 不使用短缓存指纹。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _media_stamp(slide: dict | None, base_path: str | Path | None,
                 spec_path: str | Path | None = None) -> list:
    """图片指纹与 compiler 的相对路径解析保持同口径。

    build 模块常把素材放在自身目录，而输出 PPTX 写到另一个目录；只以
    output_dir 解析会把真实素材误记成 missing，造成缓存视图不稳定。
    """
    roots = [Path(base_path) if base_path else Path.cwd()]
    if spec_path:
        roots.append(Path(spec_path).parent)
    stamps = []
    slide = slide if isinstance(slide, dict) else {}
    elements = slide.get("elements", [])
    if not isinstance(elements, list):
        return stamps
    for element in elements or []:
        if not isinstance(element, dict):
            continue
        src = element.get("src")
        if not src and isinstance(element.get("asset"), dict):
            src = element["asset"].get("src")
        if not src:
            continue
        path = Path(str(src))
        if not path.is_absolute():
            candidates = [(root / path).resolve() for root in roots]
            path = next((candidate for candidate in candidates if candidate.exists()),
                        candidates[0])
        try:
            stat = path.stat()
            # Path + stat alone still collides when a media file is replaced with
            # same-size content while preserving mtime. The short content digest
            # closes that correctness hole; the path prevents cross-directory aliasing.
            stamps.append([str(path.resolve()), stat.st_size, stat.st_mtime_ns,
                           _file_sha(path) or "unreadable"])
        except (OSError, ValueError):
            stamps.append([str(path.resolve()), "missing"])
    return stamps


def _pixel_view(obj: dict | None, drop: tuple) -> dict:
    return {k: v for k, v in (obj if isinstance(obj, dict) else {}).items()
            if k not in drop}


def _load_meta(work: Path) -> dict:
    try:
        value = json.loads((work / RENDER_META_NAME).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        # 损坏/半写入的 metadata 只使缓存失效，不应让 QA 或编译链崩溃。
        return {}


def _atomic_json_write(path: Path, value: dict) -> None:
    """写临时文件后 replace，避免进程中断留下半个 render_meta.json。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp",
                                    dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=1)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def _patch_meta(work: Path, **fields) -> None:
    try:
        meta = _load_meta(work)
        meta.update(fields)
        _atomic_json_write(work / RENDER_META_NAME, meta)
    except (OSError, TypeError, ValueError):
        # cache metadata is an optimization; never hide the primary compile result
        pass


def _engine_stamp() -> list:
    """编译实现指纹（不导入 compiler，保持 spec/draft 的轻量边界）。"""
    result = []
    root = Path(__file__).resolve().parent
    for name in CACHE_ENGINE_FILES:
        path = root / name
        try:
            stat = path.stat()
            result.append([name, stat.st_size, stat.st_mtime_ns, _file_sha(path) or "unreadable"])
        except OSError:
            result.append([name, "missing"])
    return result


def spec_view(spec: dict | None, base_path: str | Path | None = None,
              spec_path: str | Path | None = None) -> str:
    """与 render_check 相同的编译像素投影，但不加载渲染依赖。"""
    spec = spec if isinstance(spec, dict) else {}
    raw_canvas = spec.get("canvas")
    canvas = dict(raw_canvas) if isinstance(raw_canvas, dict) else {}
    theme = _pixel_view(spec.get("theme"), NON_PIXEL_THEME_KEYS)
    views = []
    raw_slides = spec.get("slides")
    if not isinstance(raw_slides, list):
        raw_slides = []
    for raw_slide in raw_slides:
        slide = raw_slide if isinstance(raw_slide, dict) else {}
        elements = slide.get("elements") if isinstance(slide.get("elements"), list) else []
        views.append({
            "background": _pixel_view(slide, NON_PIXEL_SLIDE_KEYS).get("background"),
            "elements": elements,
            "id": slide.get("id"),
            "media": _media_stamp(slide, base_path, spec_path),
        })
    payload = json.dumps(
        {"canvas": canvas, "theme": theme, "slides": views,
         "engine": _engine_stamp(), "v": CACHE_VIEW_VERSION},
        ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def compile_reuse(work: Path, pptx: Path, view: str) -> dict | None:
    rec = _load_meta(work).get("compile") or {}
    if not isinstance(rec, dict) or not isinstance(rec.get("report"), dict):
        return None
    semantic_view = rec.get("semantic_view", rec.get("view"))
    if semantic_view != view or not rec.get("report"):
        return None
    # 旧 metadata 没有完整输出 attestation，不能让它冒充当前 compiler 的
    # 产物；宁可重编一次，也不把同大小的被替换 PPTX 认作命中。
    if not rec["report"].get("output_sha256"):
        return None
    stored_sha = str(rec.get("pptx_sha") or "")
    if len(stored_sha) >= 64:
        current_sha = _file_sha_full(pptx)
    else:
        # 旧 metadata 只存短指纹：仍可命中，但下一次 record_compile 会升级为完整戳。
        current_sha = _file_sha(pptx)
    if current_sha != stored_sha:
        return None
    if not Path(pptx).exists():
        return None
    report = dict(rec["report"])
    report["reused"] = True
    # QA 仍会输出 artifact SHA，但不必在同一热命中路径再次读取整份 PPTX。
    # 完整戳优先复用报告中的全 SHA；旧记录则至少已通过短戳核对。
    report["_cache_verified_sha256"] = (report.get("output_sha256")
                                        if len(stored_sha) < 64 else current_sha)
    return report


def record_compile(work: Path, pptx: Path, view: str, report: dict) -> None:
    output_sha = str((report or {}).get("output_sha256") or "")
    if len(output_sha) != 64:
        output_sha = _file_sha_full(pptx) or ""
    _patch_meta(work, compile={
        "semantic_view": view,
        # 保留旧 key 以便已有 render_meta.json 平滑升级；读取优先 semantic_view。
        "view": view,
        "pptx_sha": output_sha,
        "pptx_name": Path(pptx).name,
        "report": {k: v for k, v in (report or {}).items() if k != "guard"},
    })
