# -*- coding: utf-8 -*-
"""编译缓存与轮次账本（唯一的本地状态文件层）。

两件小事，都为零成本判断服务：
  1) spec 的确定性投影 + 引擎指纹 + 产物字节戳一致时，跳过重复编译；
  2) 记录「同一产物上第几轮」，让轮次预算可见（账本是提示，不是门禁）。
故意不导入 PIL / numpy / python-pptx：判断"要不要重编"本身必须是零成本的。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from primitives import file_digest

CACHE_NAME = "compile_cache.json"
# 编译器/底层 primitives 改变时，即使 spec 投影不变，旧 PPTX 也不能继续冒充当前
# 引擎产物。把实现指纹放进 view，而不是依赖手工清缓存。
# ghost.py 也在内：预览是「交付证据」的一部分，渲染器改了还复用旧预览，
# 等于让作者看着上一版的证据做这一版的判断。
CACHE_ENGINE_FILES = ("compiler.py", "primitives.py", "ghost.py")
CACHE_VIEW_VERSION = 6
NON_GEOMETRIC_SLIDE_KEYS = (
    "page_intent", "source_zone", "notes", "speaker_notes", "comment",
    "comments", "annotations", "id", "label",
)
NON_GEOMETRIC_THEME_KEYS = (
    "constraints", "notes", "description", "name", "metadata",
    "provenance", "id",
)


def _file_sha(path: Path) -> str | None:
    """短指纹：缓存键用（截全文件 SHA-256 前 16 位，口径与完整指纹同源）。"""
    d = file_digest(path)
    return d[:16] if d else None


_file_sha_full = file_digest   # 完整 SHA-256：产物凭证不使用短缓存指纹


def _media_stamp(slide: dict | None, base_path: str | Path | None,
                 spec_path: str | Path | None = None, image_bytes: dict | None = None) -> list:
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
        blob = (image_bytes or {}).get(str(path))
        if blob is not None:
            stamps.append([str(path), len(blob), hashlib.sha256(blob).hexdigest()])
            continue
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


def _projection(obj: dict | None, drop: tuple) -> dict:
    return {k: v for k, v in (obj if isinstance(obj, dict) else {}).items()
            if k not in drop}


def _load_meta(work: Path) -> dict:
    try:
        value = json.loads((work / CACHE_NAME).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        # 损坏/半写入的 metadata 只使缓存失效，不应让 QA 或编译链崩溃。
        return {}


def _atomic_json_write(path: Path, value: dict) -> None:
    """原子写入（唯一实现住 primitives.json_write）；缓存文件加 fsync 防断电半页。"""
    from primitives import json_write
    json_write(path, value, indent=1, trailing_newline=False, fsync=True)


def _patch_meta(work: Path, **fields) -> None:
    try:
        meta = _load_meta(work)
        meta.update(fields)
        _atomic_json_write(work / CACHE_NAME, meta)
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
              spec_path: str | Path | None = None, image_bytes: dict | None = None) -> str:
    """spec → 确定性编译投影（决定"要不要重编"的唯一身份）。"""
    spec = spec if isinstance(spec, dict) else {}
    raw_canvas = spec.get("canvas")
    canvas = dict(raw_canvas) if isinstance(raw_canvas, dict) else {}
    theme = _projection(spec.get("theme"), NON_GEOMETRIC_THEME_KEYS)
    views = []
    raw_slides = spec.get("slides")
    if not isinstance(raw_slides, list):
        raw_slides = []
    for raw_slide in raw_slides:
        slide = raw_slide if isinstance(raw_slide, dict) else {}
        elements = slide.get("elements") if isinstance(slide.get("elements"), list) else []
        views.append({
            "background": _projection(slide, NON_GEOMETRIC_SLIDE_KEYS).get("background"),
            "elements": elements,
            "id": slide.get("id"),
            "media": _media_stamp(slide, base_path, spec_path, image_bytes),
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
    semantic_view = rec.get("semantic_view")
    if semantic_view != view or not rec.get("report"):
        return None
    # 旧记录没有完整产物凭证，不能让它冒充当前 compiler 的产物；
    # 宁可重编一次，也不把同大小的被替换 PPTX 认作命中。
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
    # 命中路径不再读整份 PPTX：完整戳优先复用报告中的 SHA，旧记录至少已过短戳核对。
    report["_cache_verified_sha256"] = (report.get("output_sha256")
                                        if len(stored_sha) < 64 else current_sha)
    return report


def record_compile(work: Path, pptx: Path, view: str, report: dict) -> None:
    output_sha = str((report or {}).get("output_sha256") or "")
    if len(output_sha) != 64:
        output_sha = _file_sha_full(pptx) or ""
    _patch_meta(work, compile={
        "semantic_view": view,
        "pptx_sha": output_sha,
        "pptx_name": Path(pptx).name,
        "report": {k: v for k, v in (report or {}).items() if k != "guard"},
    })


# --------------------------------------------------------------------------
# 轮次账本（round ledger）：把「交付用了几个 Agent 回合」变成可读的数
# --------------------------------------------------------------------------
# 动机：确定性链是毫秒级，慢的真相在**轮次面**
# ——六段串行阶段门把一次交付推到 8–20 轮。要压轮次，先得让每一步知道「这是第几轮、
# 预算还剩多少、现在该不该停」。此前 CLI 完全没有这个通道，发布清单里的
# revision_count 因此恒为 0。
#
# 口径：**一轮 = 同一产物上 spec 变了的一次 QA 调用**。同一 spec 复跑（缓存命中）
# 不记新轮——否则「复跑确认」会被记成浪费，作者反而不敢复核。
ROUNDS_NAME = "rounds.json"
# 预算只用于显示进度（CLI 的 "round n/6"）：让作者知道自己修到第几轮了。
# 它**不是门槛**——超轮不阻断、不改判定。曾经还算过一个 over_budget 布尔值，
# 但没有任何地方消费它：不消费的数据就不要计算，算了不用只会让人以为「有人在管」。
ROUND_BUDGET = 6                 # SKILL.md Round Budget 上限（仅显示）
ROUND_LOG_CAP = 24


def load_rounds(work) -> dict:
    """读轮次账本；坏文件按空账本处理（账本是提示，不是门禁，绝不炸链）。"""
    try:
        data = json.loads((Path(work) / ROUNDS_NAME).read_text(encoding="utf-8"))
    except Exception:
        return {"rounds": []}
    if not isinstance(data, dict) or not isinstance(data.get("rounds"), list):
        return {"rounds": []}
    return data


def note_round(work, *, mode: str, spec_hash: str, status: str | None = None,
               blocking: int | None = None, warnings: int | None = None) -> dict:
    """记一轮并返回账本摘要。返回值供 CLI 打印与 Manifest 取 revision_count。"""
    work = Path(work)
    data = load_rounds(work)
    rounds = data["rounds"]
    last = rounds[-1] if rounds else None
    new_round = not (isinstance(last, dict) and last.get("spec") == spec_hash)
    if new_round:
        rounds.append({"n": len(rounds) + 1, "mode": str(mode),
                       "spec": str(spec_hash), "status": status,
                       "blocking": blocking, "warnings": warnings})
        del rounds[:-ROUND_LOG_CAP]
    else:
        last.update(mode=str(mode), status=status, blocking=blocking, warnings=warnings)
    try:
        work.mkdir(parents=True, exist_ok=True)
        _atomic_json_write(work / ROUNDS_NAME, data)
    except Exception:
        pass                          # 写不进账本不该影响交付
    n = len(rounds)
    return {
        "n": n if new_round else max(n, 1),
        "new_round": new_round,
        "budget": ROUND_BUDGET,
        "revisions": max(0, n - 1),   # 首次出稿不算修订
        "log": [{"round": r.get("n"), "mode": r.get("mode"),
                 "status": r.get("status"), "blocking": r.get("blocking")}
                for r in rounds],
    }
