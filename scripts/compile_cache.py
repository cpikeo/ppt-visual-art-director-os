# -*- coding: utf-8 -*-
"""编译缓存与轮次账本（唯一的本地状态文件层）。

两件小事，都为零成本判断服务：
  1) spec 的确定性投影 + 引擎指纹 + 产物字节戳一致时，跳过重复编译；
  2) 记录「同一产物上第几轮」，让轮次预算可见（账本是提示，不是门禁）。
故意不导入 PIL / numpy / python-pptx：判断"要不要重编"本身必须是零成本的。
"""
from __future__ import annotations

import json
from pathlib import Path

from primitives import (digest_bytes, engine_fingerprint, file_digest, identity,
                        stat_witness, witness_matches)

CACHE_NAME = "compile_cache.json"
# 编译器/底层 primitives 改变时，即使 spec 投影不变，旧 PPTX 也不能继续冒充当前
# 引擎产物。把实现指纹放进 view，而不是依赖手工清缓存。
# ghost.py 也在内：预览是「交付证据」的一部分，渲染器改了还复用旧预览，
# 等于让作者看着上一版的证据做这一版的判断。
CACHE_VIEW_VERSION = 8        # v8：引擎指纹改由 primitives.engine_fingerprint 产出
NON_GEOMETRIC_SLIDE_KEYS = (
    "page_intent", "source_zone", "notes", "speaker_notes", "comment",
    "comments", "annotations", "id", "label",
)
NON_GEOMETRIC_THEME_KEYS = (
    "constraints", "notes", "description", "name", "metadata",
    "provenance", "id",
)


# 文件摘要只有一处实现（primitives.file_digest）：需要短指纹就显式切片，
# 需要完整凭证就用全值——不再维护 _file_sha / _file_sha_full 两套别名。


def _media_stamp(slide: dict | None, base_path: str | Path | None,
                 spec_path: str | Path | None = None, image_bytes: dict | None = None,
                 digests: dict | None = None) -> list:
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
        # 摘要优先：本轮 QC/核验已经算过的就不要再算（同一张图在 6 处落位会重复
        # 出现，此前每次出现都重哈希一遍 50MB 源图）。身份仍由同一个 sha256 决定。
        known = (digests or {}).get(str(path))
        if known is None and digests is not None:
            try:
                known = digests.get(str(path.resolve()))
            except OSError:
                known = None
        blob = (image_bytes or {}).get(str(path))
        if known is not None:
            size = len(blob) if blob is not None else None
            if size is None:
                try:
                    size = path.stat().st_size
                except OSError:
                    stamps.append([str(path), "missing"])
                    continue
            stamps.append([str(path), size, known])
            continue
        if blob is not None:
            stamp = digest_bytes(blob)
            if digests is not None:
                digests[str(path)] = stamp
            stamps.append([str(path), len(blob), stamp])
            continue
        try:
            stat = path.stat()
            # Path + stat alone still collides when a media file is replaced with
            # same-size content while preserving mtime. The short content digest
            # closes that correctness hole; the path prevents cross-directory aliasing.
            # 兜底路径才自己读字节；能拿到共享摘要的调用点在上面就返回了。
            stamps.append([str(path.resolve()), stat.st_size, stat.st_mtime_ns,
                           (file_digest(path) or "unreadable")[:16]])
        except (OSError, ValueError):
            stamps.append([str(path.resolve()), "missing"])
    return stamps


def _projection(obj: dict | None, drop: tuple) -> dict:
    return {k: v for k, v in (obj if isinstance(obj, dict) else {}).items()
            if k not in drop}


def _load_meta(work: Path) -> dict:
    """读缓存元数据（一轮里同一份只解析一次；写盘会改 mtime，缓存自然失效）。"""
    from primitives import json_read_cached
    try:
        # 返回浅拷贝：_patch_meta 会就地改这份 dict，共享对象不能被就地改写。
        value = json_read_cached(work / CACHE_NAME)
        return dict(value) if isinstance(value, dict) else {}
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


def _engine_stamp() -> str:
    """编译实现指纹：唯一实现在 primitives.engine_fingerprint（scope="compile"）。

    此前这里有第二份（列文件 + 逐文件 stat/sha），与预览器、度量器各算一套；
    现在「产出这段字节的代码是谁」只有一个答案。
    """
    return engine_fingerprint("compile")


def spec_view(spec: dict | None, base_path: str | Path | None = None,
              spec_path: str | Path | None = None, image_bytes: dict | None = None,
              digests: dict | None = None) -> str:
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
            "media": _media_stamp(slide, base_path, spec_path, image_bytes, digests),
        })
    # 视图身份只由一个入口产出（身份层）：引擎指纹 + 版本 + 语义投影。
    return identity({"canvas": canvas, "theme": theme, "slides": views,
                     "engine": _engine_stamp(), "v": CACHE_VIEW_VERSION},
                    schema="vao-compile-view-v8", short=24)


def compile_reuse(work: Path, pptx: Path, view: str, *, fast_probe: bool = False,
                  speed: str | None = None) -> dict | None:
    """编译复用探测：语义投影一致 + 产物还是那一份，才允许跳过重编。

    `fast_probe=True`（v5.9 快速档）用 size+mtime_ns 取代整包哈希。这不是放宽正确性
    要求，而是把成本放对位置：探测的职责是「这一份还要不要重编」，不是「证明交付
    字节」——后者由 attestation 一次完成。任何写盘动作都会改变 mtime_ns（纳秒级，
    同尺寸替换也躲不过），因此快探测只会在「文件真的没被动过」时命中。
    strict 档保留整包内容核对，用于发布链的终极证明。
    """
    rec = _load_meta(work).get("compile") or {}
    if not isinstance(rec, dict) or not isinstance(rec.get("report"), dict):
        return None
    semantic_view = rec.get("semantic_view")
    if semantic_view != view or not rec.get("report"):
        return None
    # 档位也是产物口径的一部分：fast 与 strict 编出的 PPTX 字节不同（PNG 编码级别），
    # 跨档位复用会让清单里的 speed 与产物的真实出身对不上。同档位才复用，
    # 旧记录没有 performance.speed 时按 strict 记，宁可重编一次。
    if speed is not None:
        recorded = str(((rec.get("report") or {}).get("performance") or {}).get("speed")
                       or "strict")
        if recorded != str(speed):
            return None
    # 产物凭证：全库唯一写法 output_witness{size, mtime_ns, sha256}。记录里只存一份
    # （报告副本不再重复存 output_sha256），命中时再回填给报告。
    witness = rec.get("output_witness") or {}
    stored_sha = str(witness.get("sha256") or "")
    # 旧记录没有完整产物凭证，不能让它冒充当前 compiler 的产物；
    # 宁可重编一次，也不把同大小的被替换 PPTX 认作命中。
    if len(stored_sha) < 64:
        return None
    if not Path(pptx).exists():
        return None
    if fast_probe:
        size, mtime_ns = stat_witness(pptx)
        if not witness_matches(witness, {"size": size, "mtime_ns": mtime_ns}):
            return None
        report = dict(rec["report"])
        report["reused"] = True
        report["_cache_probe"] = "size+mtime_ns"
        # 见证即已存记录：报告里那份 SHA 对应的是同一 size/mtime 的字节。
        report["_cache_verified_sha256"] = stored_sha
        report["output_sha256"] = stored_sha
        return report
    current_sha = file_digest(pptx)
    if current_sha != stored_sha:
        return None
    report = dict(rec["report"])
    report["reused"] = True
    report["_cache_probe"] = "content_sha256"
    report["_cache_verified_sha256"] = current_sha
    report["output_sha256"] = current_sha
    return report


def record_compile(work: Path, pptx: Path, view: str, report: dict) -> None:
    output_sha = str((report or {}).get("output_sha256") or "")
    if len(output_sha) != 64:
        output_sha = file_digest(pptx) or ""
    size, mtime_ns = stat_witness(pptx)
    _patch_meta(work, compile={
        "semantic_view": view,
        "compile_speed": str(((report or {}).get("performance") or {}).get("speed") or "strict"),
        # 产物凭证只存这一份：size+mtime_ns 是快探针的见证，sha256 是严格档的见证。
        "output_witness": {"size": size, "mtime_ns": mtime_ns, "sha256": output_sha},
        "pptx_name": Path(pptx).name,
        # 报告副本里不再重复存 output_sha256 —— 同一事实只保存一次，命中时回填。
        "report": {k: v for k, v in (report or {}).items()
                   if k not in ("guard", "output_sha256")},
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
