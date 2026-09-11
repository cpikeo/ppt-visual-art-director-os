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
import time
from pathlib import Path
from typing import Any

from PIL import Image

from primitives import DEFAULT_WIDTH, DEFAULT_HEIGHT, AUX_TEXT_ROLES


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


MAX_RENDER_WORKERS = 2   # 并行上限：soffice/numpy 已接近吃满 2 核，更多线程只会互相抢占


RENDER_CACHE_NAME = "render_cache.json"
RENDER_META_NAME = "render_meta.json"      # 记录「这份 PDF 来自哪一份 PPTX」   # 与 page-*.png 同目录，可复核可删除


def _media_stamp(slide: dict | None, base_path: str | Path | None) -> list:
    """页内图片资产的 (文件名, 大小, mtime)：重新出图必然改变指纹，缓存自动失效。"""
    base = Path(base_path) if base_path else None
    stamps = []
    for e in (slide or {}).get("elements", []) or []:
        if not isinstance(e, dict):
            continue
        src = e.get("src")
        if not src and isinstance(e.get("asset"), dict):
            src = e["asset"].get("src")
        if not src:
            continue
        p = Path(str(src))
        if base is not None and not p.is_absolute():
            p = base / p
        try:
            st = p.stat()
            stamps.append([p.name, st.st_size, st.st_mtime_ns])
        except Exception:
            stamps.append([str(src), "missing"])
    return stamps


# 只影响判定、不影响本页像素的字段。编译器（compiler.py）实际只读 slide 的
# background / elements（id 仅用于诊断文案），RenderContext 读 theme 的 colors/fonts
# 与 chart_*/text_default；其余是声明与治理输入。把元数据排除在键外，改一句
# insight 或把 density 上调一档（本项目自己给出的最小修正）就不必再付一轮渲染。
# selftest 会拿编译器源码对拍这份名单，新增像素字段时立即点名。
# 例外：page_intent.focus 虽不产出像素，却决定量到的是哪个元素的墨量占比，
# 因此由 _slide_key 的 focus 参数单独并入键里，不在这里放行。
NON_PIXEL_SLIDE_KEYS = ("page_intent", "source_zone", "notes", "speaker_notes", "comment",
                        "comments", "annotations", "id", "label")
NON_PIXEL_THEME_KEYS = ("constraints", "notes", "description", "name", "metadata",
                        "provenance", "id")


def _pixel_view(obj: dict | None, drop: tuple) -> dict:
    return {k: v for k, v in (obj or {}).items() if k not in drop}


def _slide_key(slide: dict | None, canvas: dict, dpi: int, theme: dict | None,
               renderer: str | None, media: list | None = None,
               focus: str | None = None) -> str:
    """页级缓存键：影响本页像素的全部输入。

    包含渲染后的元素、主题（字体与色板是全 deck 的空间假设）、画布、dpi、页内图片
    指纹与渲染器身份；其他页的改动不会使本页失效——那正是迭代循环里被重复计算的部分。
    声明类字段（source_zone / 备注 / page_intent 的叙述部分）不在键里：它们只改判定
    不改量出来的数字，命中后仍按当前 spec 读取，因此既省时间也不留陈旧。唯一的例外是
    page_intent.focus——它决定量哪个元素的墨量占比，故必须进键（focus 参数）。
    切换 LibreOffice 版本后请清缓存（或传 use_cache=False）。
    """
    import hashlib
    import json
    payload = json.dumps({"slide": _pixel_view(slide, NON_PIXEL_SLIDE_KEYS),
                          "focus": str(focus or ""), "canvas": canvas, "dpi": int(dpi),
                          "theme": _pixel_view(theme, NON_PIXEL_THEME_KEYS),
                          "media": media or [], "renderer": renderer,
                          # 显著图后端进键：cv2 与回退算法的质心/分片不可互换，
                          # 跨机器共用证据目录时必须分键存放；v6 起并入光学对齐带内匹配（旧键自然淘汰）
                          "sal": _saliency_backend(), "v": 6},
                         ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _png_present(work: Path, entry: dict) -> bool:
    """缓存命中 = 证据 PNG 在原处 **且内容未变**。只比文件名会把别页像素当本页。"""
    name = entry.get("png")
    if not name:
        return False
    p = work / name
    if not p.exists():
        return False
    want = entry.get("png_sha")
    if not want:                      # 旧格式（无指纹）条目不信任 → 重测
        return False
    return _file_sha(p) == want


def _png_name(work: Path, page_no: int, token: str | None = None) -> str | None:
    """页码 → 本轮（同一 token 前缀）生成的证据图文件名（png 或 jpg）。

    快测用 JPEG 时产物是 .jpg；这里若只认 .png，JPEG 页会「测了却入不了缓存」，
    下一轮白白重测——缓存与光栅格式必须同一种格式感知。
    """
    pats = ([f"page-{token}-*.{e}" for e in RASTER_EXTS] if token
            else [f"page-*-*-*.{e}" for e in RASTER_EXTS])
    for pat in pats:
        for f in sorted(work.glob(pat)):
            digits = "".join(c for c in f.stem.rsplit("-", 1)[-1] if c.isdigit())
            if digits and int(digits) == page_no:
                return f.name
    return None


def _load_meta(work: Path) -> dict:
    try:
        import json
        return json.loads((work / RENDER_META_NAME).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _patch_meta(work: Path, **fields) -> None:
    """记不上只是下次多算一遍：元数据永远不是判定的依据。"""
    try:
        import json
        meta = _load_meta(work)
        meta.update(fields)
        (work / RENDER_META_NAME).write_text(
            json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def spec_view(spec: dict | None, base_path: str | Path | None = None) -> str:
    """「会被编译成像素的那部分 spec」的指纹：与缓存键同一套投影口径。

    只有这份指纹相同，才允许跳过编译与转换。它刻意**不包含** page_intent /
    source_zone / 备注等声明字段——改它们不改变像素，因此也不该重付一轮渲染；
    这些字段仍会被 guard / qa 按当前值读取，判定不会因此变松。
    """
    import hashlib
    import json
    spec = spec or {}
    canvas = dict(spec.get("canvas") or {})
    theme = _pixel_view(spec.get("theme"), NON_PIXEL_THEME_KEYS)
    views = []
    for s in (spec.get("slides") or []):
        views.append({"background": _pixel_view(s, NON_PIXEL_SLIDE_KEYS).get("background"),
                      "elements": (s or {}).get("elements") or [],
                      # 编译器有两条告警会带页号，故 id 也要进「编译视图」
                      "id": (s or {}).get("id"),
                      # 图片内容也进视图：换了底图就必须重编译，光看 src 路径不够
                      "media": _media_stamp(s, base_path)})
    payload = json.dumps({"canvas": canvas, "theme": theme, "slides": views, "v": 3},
                         ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _pdf_is_reusable(pptx: Path, work: Path, renderer: str | None) -> Path | None:
    """PPTX 与上次转换逐字节相同 → 复用已有 PDF。

    LibreOffice 只能整份转换（实测 1.7s），而 Level 2 → Level 3、换 dpi 抽查、
    或只看某几页的第二次运行，输入文件其实没变；没有这层复用，渐进 QA 每升一级
    都要把同一份 PDF 再转一遍。指纹按内容算，因此改一个字都会失效。
    """
    if not renderer:
        return None
    meta = _load_meta(work).get("pdf") or {}
    pdf = work / str(meta.get("name") or "")
    if (meta.get("pptx_sha") == _file_sha(pptx) and meta.get("renderer") == str(renderer)
            and pdf.exists() and _pdf_page_count(pdf) > 0):
        return pdf
    return None


def _pdf_record(pptx: Path, work: Path, pdf: Path, renderer: str | None) -> None:
    _patch_meta(work, pdf={"name": pdf.name, "pptx_sha": _file_sha(pptx),
                           "renderer": str(renderer or ""), "pptx_name": pptx.name})


def compile_reuse(work: Path, pptx: Path, view: str) -> dict | None:
    """本轮像素视图与已编译产物一致 → 返回上次编译报告，跳过 compile_deck。

    复用条件就是「编译的两项输入都没变」：spec 的像素视图指纹一致 + 磁盘上的
    PPTX 内容指纹未变。因此手动改过 PPTX、换过图片或删过文件都不会命中；
    编译器行为变了 → 产物字节变了 → 第二道关自动失效（不再需要
    COMPILER_VERSION 之类的版本闸：视图 + 内容核验已经覆盖同一件事）。
    `use_cache=False` 时调用方直接跳过本函数。
    """
    rec = _load_meta(work).get("compile") or {}
    if rec.get("view") != view or not rec.get("report"):
        return None
    if _file_sha(pptx) != rec.get("pptx_sha"):
        return None
    if not Path(pptx).exists():
        return None
    rep = dict(rec["report"])
    rep["reused"] = True
    return rep


def record_compile(work: Path, pptx: Path, view: str, report: dict) -> None:
    _patch_meta(work, compile={
        "view": view, "pptx_sha": _file_sha(pptx), "pptx_name": Path(pptx).name,
        "report": {k: v for k, v in (report or {}).items() if k != "guard"}})


def _load_cache(work: Path) -> dict[str, dict]:
    f = work / RENDER_CACHE_NAME
    if not f.exists():
        return {}
    try:
        import json
        data = json.loads(f.read_text(encoding="utf-8"))
        return data.get("entries") or {}
    except Exception:
        return {}          # 缓存损坏 → 静默按未命中处理，绝不影响判定


def _save_cache(work: Path, entries: dict[str, dict]) -> None:
    try:
        import json
        (work / RENDER_CACHE_NAME).write_text(
            json.dumps({"renderer": str(find_renderer() or ""),
                        "entries": entries}, ensure_ascii=False, indent=1),
            encoding="utf-8")
    except Exception:
        pass               # 写失败只是下次再算一遍


def _clamp_workers(workers) -> int:
    """并行度硬上限 MAX_RENDER_WORKERS，并按 CPU 数收敛（禁止无限并发）。"""
    try:
        w = int(workers)
    except (TypeError, ValueError):
        w = MAX_RENDER_WORKERS
    cpus = len(os.os.listdir('/sys/devices/system/cpu')) if False else None
    try:
        cpus = os.cpu_count() or 2
    except Exception:
        cpus = 2
    return max(1, min(MAX_RENDER_WORKERS, w, cpus))


# ─────────────────────────────────────────────────────────────────────────
# 部分渲染：拆页转 PDF（性能）
#
# LibreOffice 只能整份转换，而转换成本随页数线性增长（实测 1 页 0.52s、
# 3 页 0.76s、12 页 2.14s）。只重测 1–2 页时，把这几页拆成一个临时小 deck
# 再转，能省下整份转换的开销。
#
# 风险只有一个：页码映射搞错 = 把别页的像素当本页发布。因此本函数自带三道校验
# （小 deck 页数 == 请求页数、每页都有产物、页码按绝对编号回填），任一不过就
# 返回失败，调用方退回整份转换——宁可慢，不可错。
# ─────────────────────────────────────────────────────────────────────────
_RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
PARTIAL_MAX_RATIO = 0.5     # 需重测页数 ≤ 总页数的一半才值得拆
PARTIAL_MIN_SAVING = 4      # 至少省下 4 页的转换量才值得拆


def _partial_worth_it(need: list[int], total: int) -> bool:
    if not need or total <= 0 or not need or len(need) >= total:
        return False
    if len(need) > max(1, int(total * PARTIAL_MAX_RATIO)):
        return False
    return (total - len(need)) >= PARTIAL_MIN_SAVING


def _subset_deck(pptx: Path, pages: list[int]):
    """把 deck 拆成只含指定页的临时小 deck。返回 (小deck路径, {小页号: 原页号})。"""
    import shutil as _sh
    try:
        from pptx import Presentation
    except Exception:
        return None, None
    tmp = Path(tempfile.mkdtemp(prefix="pptx-subset-"))
    dst = tmp / "subset.pptx"
    try:
        _sh.copyfile(str(pptx), str(dst))
        prs = Presentation(str(dst))
        lst = prs.slides._sldIdLst
        keep = set(int(n) for n in pages)
        for i in range(len(lst) - 1, -1, -1):
            if (i + 1) not in keep:
                rid = lst[i].get(_RID)
                try:
                    prs.part.drop_rel(rid)
                except Exception:
                    pass
                del lst[i]
        prs.save(str(dst))
        # 校验一：小 deck 页数必须与请求页数严格相等
        if len(Presentation(str(dst)).slides) != len(keep):
            return None, None
        return dst, {i: n for i, n in enumerate(sorted(keep), start=1)}
    except Exception:
        try:
            _sh.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass
        return None, None


def _rename_evidence(work: Path, token: str, src_no: int, dst_no: int) -> None:
    """小 deck 的产物按小页号命名，回填成原页号，否则缓存会认成别页。"""
    for ext in RASTER_EXTS:
        for f in work.glob(f"page-{token}-*-{src_no:02d}.{ext}"):
            target = work / f"page-{token}-{f.stem.split('-')[2]}-{dst_no:02d}.{ext}"
            try:
                if target.exists():
                    target.unlink()
                f.rename(target)
            except OSError:
                pass


def _runs(page_numbers: list[int]) -> list[tuple[int, int]]:
    """把页码压成连续区间：[(start, end), ...]（1-based，含端点）。"""
    nums = sorted({int(n) for n in page_numbers})
    runs: list[tuple[int, int]] = []
    for n in nums:
        if runs and n == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], n)
        else:
            runs.append((n, n))
    return runs


MIN_CHUNK_PAGES = 2   # 每次 pdftoppm 约 60ms 进程启动成本，切太碎反而更慢

# ─────────────────────────────────────────────────────────────────────────
# 快测光栅化（性能）
#
# 实测 12 页含照片的 deck：-png 8.6s、-jpeg 0.8s —— PNG 慢在**编码**不在解码，
# 而我们要的只是统计量（亮度/边缘/占据率/主色/质心），JPEG q95 与 PNG 的偏差为：
# 对比度 ≤0.04、强调面积 0.000、重心 ≤0.015、占据率 ≤0.002 —— 远离阈值时可互换。
#
# 但「远离」必须被证明，不能假设：凡指标落在判定阈值 ±eps 内，就用无损 PNG 重测
# 该页再定稿（_near_threshold）。代价只发生在临界页上，典型 0–3 页。
# ─────────────────────────────────────────────────────────────────────────
JPEG_QUALITY = 95

# 光栅格式表：(pdftoppm 参数, 扩展名, 是否有损)
#
# 实测 12 页含照片的 deck：png 8.11s ｜ jpeg q95 0.78s ｜ tiff+lzw 0.99s ｜ tiff 无压缩 0.90s
# 逐页像素比对：tiff+lzw 与 png **最大差 0**（LZW 是无损压缩）。
# 结论：PNG 慢在 deflate，而不在渲染本身。既然无损也能做到 ~1s，
# 默认就该用无损格式——JPEG 那点优势（0.2s）不值得引入「有损 + 边缘复检」的复杂度。
# 扩展名曾散落在三处（命名/清理/改名），漏一处就会静默失效，故收敛成这张表。
RASTER_FORMATS = {
    "tiff": (["-tiff", "-tiffcompression", "lzw"], "tif", False),
    "png":  (["-png"], "png", False),
    "jpeg": (["-jpeg", "-jpegopt", f"quality={JPEG_QUALITY}"], "jpg", True),
}
RASTER_DEFAULT = "tiff"          # 默认：无损 + 快
RASTER_EXTS = tuple(e for _, e, _ in RASTER_FORMATS.values())


def _raster_args(raster: str):
    """光栅格式 → (pdftoppm 参数, 扩展名, 是否有损)。未知格式一律退回无损默认。"""
    return RASTER_FORMATS.get(str(raster or "").lower(), RASTER_FORMATS[RASTER_DEFAULT])

# 判定阈值 → 边缘带宽。贴着这些值的页必须无损复测，否则 JPEG 噪声可能翻判。
_RECHECK_THRESHOLDS = {
    "text_contrast_min":     (3.0, 4.5),
    "text_contrast_all_min": (3.0, 4.5),
    "gravity_drift":         (0.28,),
    "occupancy":             (0.60, 0.65, 0.75, 0.85),
}
_RECHECK_EPS = {
    "text_contrast_min": 0.15, "text_contrast_all_min": 0.15,
    "gravity_drift": 0.030, "occupancy": 0.020, "accent_pixel_ratio": 0.010,
}
_ACCENT_MAX_DEFAULT = 0.05


def _near_threshold(item: dict, accent_max: float | None = None) -> bool:
    """该页是否有指标贴着判定阈值？贴着就必须用无损 PNG 重测。

    宁可多测几页，不可让 JPEG 的编码噪声改变发布判定——省下的时间远没有
    一次误判昂贵。
    """
    if not isinstance(item, dict):
        return False
    thresholds = dict(_RECHECK_THRESHOLDS)
    thresholds["accent_pixel_ratio"] = (
        (float(accent_max),) if accent_max else (_ACCENT_MAX_DEFAULT,))
    for key, bounds in thresholds.items():
        v = item.get(key)
        if v is None:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        eps = _RECHECK_EPS.get(key, 0.02)
        for b in bounds:
            if abs(v - float(b)) <= eps:
                return True
    return False


def _plan_jobs(page_numbers: list[int], workers: int) -> tuple[list[tuple[int, int]], int]:
    """连续区间 + 按需二分，让 worker 数真正被用起来（区间少于 worker 时会有核空转）。"""
    runs = _runs(page_numbers)
    n = _clamp_workers(workers)
    while len(runs) < n:
        i = max(range(len(runs)), key=lambda k: runs[k][1] - runs[k][0])
        a, b = runs[i]
        if b - a + 1 < 2 * MIN_CHUNK_PAGES:
            break
        m = (a + b) // 2
        runs[i:i + 1] = [(a, m), (m + 1, b)]
    n = min(n, len(runs))
    return sorted(runs), n


def _convert_pages(pdf: Path, out_dir: Path, dpi: int, page_numbers: list[int],
                   workers: int = MAX_RENDER_WORKERS,
                   token: str | None = None) -> dict[int, Path]:
    """PDF → 指定页 PNG，返回 {页码: png}；某区间失败时仅该区间缺失（调用方按缺页降级）。"""
    return _run_pipeline(pdf, out_dir, dpi, page_numbers, workers, lambda n, png: png)


def _file_sha(path: Path) -> str | None:
    """文件内容指纹：缓存命中必须连像素一起核对，文件名相等不能算数。"""
    import hashlib
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except Exception:
        return None


def _run_token(src: Path, page_numbers: list[int]) -> str:
    """本轮渲染的唯一标识：文件 + 页集 + 时钟 → 短令牌（PNG 前缀与缓存写回共用）。"""
    import hashlib
    try:
        stamp = f"{src}|{src.stat().st_mtime_ns}|{page_numbers}|{time.time_ns()}"
    except Exception:
        stamp = f"{src}|{page_numbers}|{time.time_ns()}"
    return hashlib.sha1(stamp.encode("utf-8")).hexdigest()[:8]


def _run_pipeline(pdf: Path, out_dir: Path, dpi: int, page_numbers: list[int],
                  workers: int, work, token: str | None = None,
                  raster: str = "png") -> dict[int, Any]:
    """把「poppler 转换」与「逐页像素测量」放进同一个 worker：块间并行、块内串行。

    比先全部转换再全部测量少两道全局栅栏——第 1 块在测量时第 2 块已在转换。
    work(页码, png) 在线程内执行，因此只读、不写共享状态。
    """
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm is None or not page_numbers:
        return {}
    jobs, n_workers = _plan_jobs(page_numbers, workers)
    # 页数太少时并行不划算：单页 pdftoppm ≈ 117ms，线程调度成本与之同量级
    if len(page_numbers) < 4:
        n_workers = 1
    # 长区间优先派给空闲 worker，减少尾部等待（贪心，最简可靠）
    jobs = sorted(jobs, key=lambda r: -(r[1] - r[0] + 1))
    # 每轮一个唯一前缀：复用同一前缀会让本轮产物与上轮残留混进同一次 glob，页码映射
    # 随即错位——上一版的「命中 12/重测 0 却给出别页指标」正是这样发生的。
    token = token or _run_token(pdf, page_numbers)
    fmt_args, fmt, _lossy = _raster_args(raster)

    def run_job(idx_job):
        idx, (a, b) = idx_job
        stem = f"page-{token}-r{idx}"
        try:
            subprocess.run([pdftoppm] + fmt_args + ["-r", str(dpi), "-f", str(a), "-l", str(b),
                            str(pdf), str(out_dir / stem)], check=True, capture_output=True,
                           timeout=300)
        except Exception:
            return {}               # 该区间缺页 → coverage.unrendered 记录，不整轮报废
        wanted = set(range(a, b + 1))
        picked: list[tuple[int, Path]] = []
        for f in out_dir.glob(f"{stem}-*.{fmt}"):
            digits = "".join(ch for ch in f.stem.rsplit("-", 1)[-1] if ch.isdigit())
            if not digits:
                continue
            n = int(digits)
            # 只认绝对页码（pdftoppm 按文档页编号命名）。缺页就缺页，绝不按序号猜——
            # 猜错等于把别页的像素指标当本页发布。
            if n in wanted:
                picked.append((n, f))
        return {n: work(n, f) for n, f in sorted(picked)}

    bucketed = list(enumerate(jobs))
    results: dict[int, Any] = {}
    if n_workers <= 1:
        for mapping in map(run_job, bucketed):
            results.update(mapping)
        return results
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        for mapping in ex.map(run_job, bucketed):
            results.update(mapping)
    return results


# ─────────────────────────────────────────────────────────────────────────
# LibreOffice UserInstallation（profile）
#
# 旧行为：profile 建在渲染目录里。渲染目录一清（冷跑、--no-cache），profile 跟着
# 重建，每次都要多付一笔固定成本——实测 12 页转换：新建 profile 2.12s，复用 1.57s，
# 差 0.55s/次。profile 与 deck 无关，没有理由跟着渲染目录一起死。
#
# 改为跨 deck 共享的持久 profile，用文件锁串行化（同一 profile 不能被两个 soffice
# 同时写）。拿不到锁或共享目录不可用时，退回渲染目录内的私有 profile——
# 慢一点可以，转换失败不行。
# ─────────────────────────────────────────────────────────────────────────
_LO_PROFILE_ROOT = Path(tempfile.gettempdir()) / "ppt-vao-lo-profile"
_LO_LOCK_TIMEOUT = 120.0        # 等锁上限：一次转换约 2s，等得起
_LO_LOCK_STALE = 300.0          # 锁文件僵死阈值（进程被 kill 时兜底）


def _acquire_profile_lock(lock: Path, timeout: float) -> bool:
    """极简文件锁：O_EXCL 创建 + 僵死回收。拿到返回 True。"""
    import os as _os
    import time as _time
    deadline = _time.time() + max(0.0, float(timeout))
    while True:
        try:
            fd = _os.open(str(lock), _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
            try:
                _os.write(fd, str(_os.getpid()).encode())
            finally:
                _os.close(fd)
            return True
        except FileExistsError:
            try:                                   # 僵死锁：超时未更新即强删
                if _time.time() - lock.stat().st_mtime > _LO_LOCK_STALE:
                    lock.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if _time.time() >= deadline:
                return False
            _time.sleep(0.05)
        except OSError:
            return False


def _release_profile_lock(lock: Path) -> None:
    try:
        lock.unlink(missing_ok=True)
    except OSError:
        pass


def _choose_profile(out_dir: Path) -> tuple[Path, Path | None]:
    """返回 (profile 目录, 持有的锁文件 or None)。"""
    try:
        _LO_PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
        lock = _LO_PROFILE_ROOT / ".lock"
        if _acquire_profile_lock(lock, _LO_LOCK_TIMEOUT):
            return _LO_PROFILE_ROOT, lock
    except Exception:
        pass
    private = out_dir / "lo-profile"
    private.mkdir(exist_ok=True)
    return private, None


def _pdf_from_pptx(pptx: Path, out_dir: Path, keep_pngs=...) -> tuple[Path | None, str | None]:
    """PPTX → PDF（LibreOffice 单进程，整份文件，不可分页）。返回 (pdf, 失败原因)。

    LibreOffice 的 UserInstallation 需要绝对路径：相对目录会拼成非法 URI
    （file://relative/…），soffice 会卡在 profile 锁上直到超时（实测 300s），
    因此进来第一件事就是把输出目录绝对化。
    """
    out_dir = Path(out_dir).resolve()
    soffice = find_renderer()
    if soffice is None:
        return None, "no libreoffice"
    if shutil.which("pdftoppm") is None:
        return None, "no pdftoppm"
    out_dir.mkdir(parents=True, exist_ok=True)
    # 复用渲染目录时先清除历史页，避免页数变少的修订版混入上一版残留页，
    # 导致 pages 与 spec.slides 错位、重心漂移测错页。
    # keep_pngs=... → 清掉旧页（默认）；None → 完全不动（冷测不该把别人的热缓存打回冷）；
    # 集合 → 只保留被有效缓存条目引用且内容校验通过的证据文件。
    keep = None if keep_pngs is None else (set() if keep_pngs is ... else set(keep_pngs))
    for stale in (sorted([f for e in RASTER_EXTS for f in out_dir.glob(f"page-*.{e}")])
                  if keep is not None else []):
        if stale.name in keep:
            continue
        try:
            stale.unlink()
        except OSError:
            pass
    profile, lock = _choose_profile(out_dir)
    cmd = [soffice, "--headless",
           f"-env:UserInstallation=file://{profile}",
           "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except Exception as exc:
        first = str(exc)
        if lock is not None:              # 共享 profile 疑似损坏 → 私有 profile 重试
            _release_profile_lock(lock)
            try:
                private = out_dir / "lo-profile"
                private.mkdir(exist_ok=True)
                subprocess.run(
                    [soffice, "--headless",
                     f"-env:UserInstallation=file://{private}",
                     "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx)],
                    check=True, capture_output=True, timeout=300)
                return out_dir / f"{Path(pptx).stem}.pdf", None
            except Exception as exc2:
                return None, f"libreoffice convert failed: {first} / retry: {exc2}"
        return None, f"libreoffice convert failed: {first}"
    finally:
        if lock is not None:
            _release_profile_lock(lock)
    pdf = out_dir / f"{Path(pptx).stem}.pdf"
    if not pdf.exists():
        return None, "pdf not produced"
    return pdf, None




def _pdf_page_count(pdf: Path) -> int:
    """尽量准确地拿到页数；缺 pdfinfo 时回退到对象计数（不额外起进程）。"""
    info = shutil.which("pdfinfo")
    if info:
        try:
            out = subprocess.run([info, str(pdf)], capture_output=True, text=True,
                                 timeout=60).stdout
            for line in out.splitlines():
                if line.lower().startswith("pages:"):
                    return max(1, int(line.split(":", 1)[1].strip()))
        except Exception:
            pass
    try:
        data = Path(pdf).read_bytes()
        return max(1, data.count(b"/Type /Page") - data.count(b"/Type /Pages"))
    except Exception:
        return 1


# --------------------------------------------------------------------------
# 像素测量（PIL + numpy；cv2 可用时显著图更准）
# --------------------------------------------------------------------------
# render_check ↔ qa 共享契约：每页 page 字典里**至少包含这些键**。v4.15 起
# 消费侧归 qa/guard（函数从 primitives 取阈值）；字段增删须同步核对 qa 消费点，
# 否则会出现「字段写了但无人消费」的契约漂移。
PAGE_FIELDS = frozenset({
    "brightness", "edge", "occupancy", "margin_occupancy",
    "saliency_method",
    "saliency_centroid", "saliency_split_lr", "saliency_split_tb",
    "edge_kurtosis_x", "edge_kurtosis_y",
    "accent_pixel_ratio", "accent_method", "saturated_pixel_ratio",
    "background_luma",
    "gravity_drift", "anchor_id", "anchor_source", "anchor_center",
})
def _load_rgb(path: Path, max_side: int = 640) -> Any:
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("RGB")
    scale = min(1.0, max_side / max(im.size))
    if scale < 1:
        im = im.resize((max(1, int(im.width * scale)),
                        max(1, int(im.height * scale))), Image.Resampling.LANCZOS)
    return np.asarray(im).astype(np.float32)


def _saliency_backend() -> str:
    """显著图后端探测（import 级，用于缓存键）：cv2.saliency 可用即走 cv2 路径。
    import 已缓存，开销可忽略。注意这只是「会尝试哪条路」，实际走了哪条路由
    _saliency_with_method 如实记录在证据的 saliency_method 里。"""
    try:
        import cv2
        if hasattr(cv2, "saliency") and hasattr(
                cv2.saliency, "StaticSaliencySpectralResidual_create"):
            return "cv2_spectral_residual"
    except Exception:
        pass
    return "deterministic_fallback"


def _saliency_with_method(arr: Any, max_side: int = 256) -> tuple:
    """显著图 + 实际算法溯源 → (sal, method)。

    先降到 max_side（默认 256）再算：质心/左右上下分片是粗粒度指标，Spectral
    Residual 在 640px 全尺寸上跑几乎不改变归一化结果，却把 cv2 成本放大了
    数倍。降采样后质心与分片逐位稳定（selftest 的 render_metrics 断言）。
    method 只可能是 cv2_spectral_residual / deterministic_fallback —— 有 cv2 的
    机器与无 cv2 的机器算出的显著图不可严格对比，证据必须自带算法身份。"""
    import numpy as np
    h0, w0 = arr.shape[:2]
    if max(h0, w0) > max_side:
        scale = max_side / max(h0, w0)
        arr = np.asarray(Image.fromarray(arr.astype(np.uint8)).resize(
            (max(1, int(w0 * scale)), max(1, int(h0 * scale))),
            Image.Resampling.BILINEAR))
    try:
        import cv2
        bgr = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2BGR)
        sal = cv2.saliency.StaticSaliencySpectralResidual_create()[1].computeSaliency(bgr)[1]
        sal = sal.astype(np.float32)
        return sal / max(float(sal.max()), 1e-6), "cv2_spectral_residual"
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
    return np.clip((sal - p[0]) / max(p[1] - p[0], 1e-6), 0, 1), "deterministic_fallback"




def _dominant_color(patch) -> str:
    """区域主色：先按 16 级量化取众数（挡住字形像素），再取该桶内像素的均值。

    只取桶中心会有 ±8/通道的量化偏差，足以把 4.27:1 报成 4.5:1；桶内均值把误差压到
    1 以下，门禁才不会因量化噪声误判。
    """
    import numpy as np
    flat = patch.reshape(-1, 3)
    q = (flat // 16).astype(np.int32)
    idx = (q[:, 0] << 8) | (q[:, 1] << 4) | q[:, 2]
    d = int(np.bincount(idx).argmax())
    sel = flat[idx == d]
    r, g, b = (int(round(float(v))) for v in sel.mean(0))
    return f"#{r:02X}{g:02X}{b:02X}"


def _text_regions(slide: dict, cw: float, ch: float, theme: dict) -> list[dict]:
    """文字框 → 归一化区域 + 声明色，供「文字 vs 其下方像素」的实测对比度使用。"""
    colors = (theme or {}).get("colors") or {}
    out: list[dict] = []
    for e in (slide or {}).get("elements", []) or []:
        if not isinstance(e, dict) or e.get("type") != "text":
            continue
        raw = str(e.get("color") or "").strip()
        hexv = raw if raw.startswith("#") else str(colors.get(raw.lstrip("-").split(".")[-1], ""))
        if not hexv.startswith("#"):
            continue
        try:
            x, y = float(e.get("x", 0)), float(e.get("y", 0))
            w, h = float(e.get("width", 0) or 0), float(e.get("height", 0) or 0)
        except (TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        out.append({"id": e.get("id") or e.get("role") or "text",
                    "role": str(e.get("role") or ""), "color": hexv,
                    "aux": str(e.get("role") or "") in AUX_TEXT_ROLES,
                    "box": (x / cw, y / ch, w / cw, h / ch)})
    return out


def _text_contrast(arr, regions: list[dict]) -> dict[str, Any]:
    """每个文字框：框内主色当作底，与声明字色算 WCAG 对比 → 取最坏值。"""
    from primitives import contrast
    import numpy as np
    hh, ww, _ = arr.shape
    worst, reading_worst, all_r = None, None, []
    for reg in regions:
        x, y, bw, bh = reg["box"]
        x0, y0 = max(0, min(ww - 3, int(x * ww))), max(0, min(hh - 3, int(y * hh)))
        x1, y1 = max(x0 + 3, min(ww, int((x + bw) * ww))), max(y0 + 3, min(hh, int((y + bh) * hh)))
        patch = arr[y0:y1, x0:x1]
        if patch.size < 3 * 3 * 3:
            continue
        bg_hex = _dominant_color(patch)          # 每框只取一次主色
        try:
            ratio = float(contrast(reg["color"], bg_hex))
        except Exception:
            continue
        rec = {"id": reg["id"], "role": reg["role"], "aux": bool(reg.get("aux")),
               "ratio": round(ratio, 2), "color": reg["color"], "background": bg_hex}
        all_r.append(rec)
        if worst is None or rec["ratio"] < worst["ratio"]:
            worst = rec
        if not rec["aux"] and (reading_worst is None or rec["ratio"] < reading_worst["ratio"]):
            reading_worst = rec
    if not worst:
        return {}
    # 正文级与注记级分开报：正文按 WCAG AA 4.5:1 要求，注记/来源只需 3:1，
    # 否则每页那行 12px 来源标注会把噪声压过真实缺陷。
    return {"text_contrast_min": reading_worst["ratio"] if reading_worst else worst["ratio"],
            "text_contrast_worst": reading_worst or worst,
            "text_contrast_all_min": worst["ratio"],
            "text_contrast": [r["ratio"] for r in all_r]}


def declared_alignment_lines(slide: dict | None, cw: float, ch: float) -> dict:
    """从 spec 提取「数学上声明了对齐」的边界轴线（spec 坐标）。

    只取渲染时会画出真实边界的元素（shape / chart / image）——文字块的盒边界
    不画描边，峰位验证无从谈起；背景层画心占满画布、边缘无信息，一并跳过。
    返回 {"x": [...], "y": [...]}（浮点 spec 坐标），按 2px 簇去重取簇心。
    """
    xs: list[float] = []
    ys: list[float] = []
    for e in (slide or {}).get("elements") or []:
        if not isinstance(e, dict):
            continue
        if e.get("layer") in ("background",) or e.get("role") in ("background", "backdrop"):
            continue
        if str(e.get("type", "")) not in ("shape", "chart", "image"):
            continue
        try:
            x, y = float(e["x"]), float(e["y"])
            w, h = float(e["width"]), float(e["height"])
        except (KeyError, TypeError, ValueError):
            continue
        xs.extend((x, x + w))
        ys.extend((y, y + h))

    def _dedupe(vals: list[float]) -> list[float]:
        out: list[float] = []
        for v in sorted(vals):
            if not out or v - out[-1] > 2.0:
                out.append(v)
            else:
                out[-1] = (out[-1] + v) / 2.0
        return [round(v, 1) for v in out]

    return {"x": _dedupe(xs), "y": _dedupe(ys)}


def optical_alignment(png: Path, slide: dict | None,
                      cw: float, ch: float) -> dict[str, Any]:
    """渲染级光学对齐复核：验证「数学对齐」是否真的成为「视觉对齐」。

    对每根声明边界轴线（见 declared_alignment_lines），在全分辨率梯度投影上
    找 ±6px 窗口内的视觉峰位；峰位与数学坐标偏差 ≤2px 记对齐。窗口内没有
    真实边缘能量（元素未渲染出边界，如同底色填充）的线不计入 lines_checked
    ——只验证像素能验证的事。纯 PIL + numpy，确定性，不依赖 cv2。
    返回 {}（无声明线）或 {"optical_alignment": {...}}。
    """
    lines = declared_alignment_lines(slide, cw, ch)
    if len(lines["x"]) + len(lines["y"]) < 3:
        return {}
    try:
        from PIL import Image
        import numpy as np
        im = Image.open(png).convert("L")
    except Exception:
        return {}
    w_img, h_img = im.size
    gray = np.asarray(im).astype(np.float32)
    if gray.size == 0:
        return {}
    gy_arr, gx_arr = np.gradient(gray)
    mag = np.sqrt(gx_arr * gx_arr + gy_arr * gy_arr)
    col_proj = mag.sum(axis=0)
    row_proj = mag.sum(axis=1)

    def _check(proj, declared: list[float], total_px: int, spec_len: float):
        """匹配语义：『声明位置上有没有边缘』，而非『窗口内最强边缘在哪』。

        文字笔画/图表条会在 ±6px 内制造比元素边界更强的峰——按最强峰计距离
        会被劫持（实测：声明 x=48 处确有 4420 的边界峰，却被 6px 外 4767 的
        笔画峰抢走）。因此：带内（±tol）有真实边缘 = 对齐；窗口内有、带内没有
        = 偏移；窗口内连边缘都没有 = 不可验证（元素没渲染出边界，如同底色填充）。
        """
        scale = total_px / max(1.0, float(spec_len))
        win = max(3, int(round(6 * scale)))
        tol = max(1, int(round(2 * scale)))
        med = float(np.median(proj)) if proj.size else 0.0
        floor = 3.0 * max(med, 1e-6)
        checked = aligned = 0
        max_shift = 0.0
        for v in declared:
            c = int(round(v * scale))
            wlo, whi = max(0, c - win), min(len(proj), c + win + 1)
            blo, bhi = max(0, c - tol), min(len(proj), c + tol + 1)
            if whi - wlo < 2 or bhi - blo < 1:
                continue
            if float(proj[wlo:whi].max()) <= floor:
                continue          # 窗口内无真实边界能量 → 不可验证，不计入
            checked += 1
            if float(proj[blo:bhi].max()) > floor:
                aligned += 1     # 声明位置上就有边缘 → 数学对齐即视觉对齐
            else:
                delta = float(wlo + int(proj[wlo:whi].argmax())) - c
                max_shift = max(max_shift, abs(delta))
        return checked, aligned, max_shift

    cx, ax, sx = _check(col_proj, lines["x"], w_img, cw)
    cy, ay, sy = _check(row_proj, lines["y"], h_img, ch)
    checked = cx + cy
    if checked < 3:
        return {"optical_alignment": {"lines_checked": checked,
                                      "method": "gradient_projection"}}
    return {"optical_alignment": {
        "lines_checked": checked,
        "aligned_share": round((ax + ay) / checked, 3),
        "max_shift_px": round(max(sx, sy), 1),
        "method": "gradient_projection",
    }}


def measure_image(path: Path, accent_hex: str | None = None,
                  text_regions: list[dict] | None = None) -> dict[str, Any]:
    """单页真实渲染测量。

    accent_hex 提供时，强调色像素比按「与主题 Accent 色的色距」测量（比
    通用饱和度启发更贴近 Accent 预算语义）；未提供时回退为饱和度启发。
    text_regions 提供时追加「文字 vs 其下方像素」的最坏对比度——全页亮度一致
    地暗或亮都掩盖不了它（深底深字曾经一路通过到发布）。
    """
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

    # 安全区余量证据：边缘带（≈画布 5%）若与背景同样安静，说明内容未贴边。
    band = np.concatenate([gray[:3, :].ravel(), gray[-3:, :].ravel(),
                           gray[:, :5].ravel(), gray[:, -5:].ravel()])
    margin_occupancy = float(np.mean(np.abs(band - bg) > 10))

    sal, sal_method = _saliency_with_method(arr)
    yy, xx = np.mgrid[0:sal.shape[0], 0:sal.shape[1]]
    total = float(sal.sum()) + 1e-6
    cx = float((xx * sal).sum() / total) / max(1, sal.shape[1] - 1)
    cy = float((yy * sal).sum() / total) / max(1, sal.shape[0] - 1)

    half_w = sal.shape[1] // 2
    left = float(sal[:, :half_w].sum())
    right = float(sal[:, half_w:].sum())
    half_h = sal.shape[0] // 2
    top = float(sal[:half_h, :].sum())
    bottom = float(sal[half_h:, :].sum())

    # 边缘投影：把 sobel 强度沿水平/垂直方向求和，得到
    # "axis histograms"。对齐良好的页面：水平/垂直方向会出现清晰的
    # 收束峰（多数内容共享同一 x 或 y）；碎片化页面：分布平坦。
    # 这是「视觉对齐」的渲染证据，承接 OS 审查模式 §alignment 的量化依据
    # 仅靠结构聚类的盲点（数学对齐但视觉不齐无法识别）。
    gy_arr, gx_arr = np.gradient(gray)
    edge_mag = np.sqrt(gx_arr * gx_arr + gy_arr * gy_arr)
    # 行/列求和：横轴投影（沿 X 轴累积）反映「内容是否共享同一 Y」
    # 纵轴投影（沿 Y 轴累积）反映「内容是否共享同一 X」。
    col_proj = edge_mag.sum(axis=0)            # 长度 = w
    row_proj = edge_mag.sum(axis=1)            # 长度 = h
    # 峰度：值越大表示越集中（成轴），越小表示越分散（碎片）。
    def _kurtosis(proj: "np.ndarray") -> float:
        if proj.size < 4:
            return 0.0
        m = float(proj.mean())
        if m <= 1e-6:
            return 0.0
        s2 = float(((proj - m) ** 2).mean())
        if s2 <= 1e-6:
            return 0.0
        m4 = float(((proj - m) ** 4).mean())
        return m4 / (s2 * s2) - 3.0
    edge_kurtosis_x = float(_kurtosis(col_proj))   # 沿 X 投影的峰度 → 横向轴线感
    edge_kurtosis_y = float(_kurtosis(row_proj))   # 沿 Y 投影的峰度 → 纵向轴线感

    rgb = arr / 255.0
    mx = rgb.max(2)
    mn = rgb.min(2)
    sat = np.where(mx == 0, 0, (mx - mn) / np.maximum(mx, 1e-6))
    saturated_pixel_ratio = float(np.mean(sat > 0.42))
    if accent_hex:
        try:
            target = np.asarray([int(accent_hex.lstrip("#")[i:i + 2], 16) / 255.0
                                 for i in (0, 2, 4)], dtype=np.float32)
            dist = np.sqrt(((rgb - target) ** 2).sum(2))
            accent_pixels = float(np.mean(dist < 0.30))
            accent_method = "theme"
        except (ValueError, IndexError):
            accent_pixels = saturated_pixel_ratio
            accent_method = "saturation"
    else:
        accent_pixels = saturated_pixel_ratio
        accent_method = "saturation"

    return {
        "brightness": round(brightness, 3),
        "edge": round(edge, 3),
        "occupancy": round(occupancy, 3),
        "margin_occupancy": round(margin_occupancy, 3),
        "saliency_method": sal_method,
        "saliency_centroid": [round(cx, 3), round(cy, 3)],
        "saliency_split_lr": round((left - right) / (left + right + 1e-6), 3),
        "saliency_split_tb": round((top - bottom) / (top + bottom + 1e-6), 3),
        "edge_kurtosis_x": round(edge_kurtosis_x, 3),
        "edge_kurtosis_y": round(edge_kurtosis_y, 3),
        "accent_pixel_ratio": round(accent_pixels, 3),
        "accent_method": accent_method,
        "saturated_pixel_ratio": round(saturated_pixel_ratio, 3),
        "background_luma": round(bg / 255.0, 3),
        **(_text_contrast(arr, text_regions) if text_regions else {}),
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


def _apply_anchor(item: dict, slide: dict | None, cw: float, ch: float) -> dict:
    """把「声明锚点」与「实测像素质心」对照，写入 anchor_* / gravity_drift。

    纯算术、无进程，因此**缓存命中也要跑**：focus 与 gravity_anchor 属于声明而非像素，
    改它们不会（也不该）触发重渲染，但派生结果必须跟着当前声明走。
    """
    for k in ("anchor_id", "anchor_source", "anchor_center", "gravity_drift"):
        item.pop(k, None)
    if not isinstance(slide, dict):
        return item
    source, anchor = resolve_anchor(slide, cw, ch)
    if anchor is None:
        for e in slide.get("elements", []) or []:      # 启发式兜底
            if not isinstance(e, dict):
                continue
            if e.get("type") in ("chart", "native_chart", "image") or \
               str(e.get("id", "")).lower() in ("hero", "title", "kpi"):
                anchor = {"kind": "element", "element": e}
                break
        source = "heuristic" if anchor else None
    if anchor:
        if anchor["kind"] == "point":
            c = (anchor["x"] / cw, anchor["y"] / ch)
        else:
            c = _element_center(anchor["element"], cw, ch)
        if c and item.get("saliency_centroid"):
            sc = item["saliency_centroid"]
            item["anchor_id"] = (anchor.get("element") or {}).get("id")
            item["anchor_source"] = source
            item["anchor_center"] = [round(c[0], 3), round(c[1], 3)]
            item["gravity_drift"] = round(((c[0] - sc[0]) ** 2 + (c[1] - sc[1]) ** 2) ** 0.5, 3)
    return item


def _reuse_entry(entry: dict, n: int, slides: list, cw: float,
                 ch: float) -> dict[str, Any]:
    """缓存命中：像素质标直接复用，声明相关字段按当前 spec 重新推导。"""
    slide = slides[n - 1] if 0 < n <= len(slides) else None
    return _apply_anchor(dict(entry, page=n, index=n - 1, cached=True,
                              slide=(slide.get("id") if isinstance(slide, dict)
                                     else f"page_{n}")), slide, cw, ch)


def resolve_anchor(slide: dict, cw: float, ch: float) -> tuple[str | None, dict | None]:
    """按「声明意图优先」解析本页视觉锚点，返回 (source, anchor)。

    anchor = {"kind":"element","element":e} 或 {"kind":"point","x":px,"y":px}
    优先级：page_intent.focus / focus_subject_id → gravity_anchor → None（由
    render_evidence 回退到启发式）。声明意图是评分基准，启发式只是兜底。
    """
    intent = slide.get("page_intent") if isinstance(slide.get("page_intent"), dict) else {}
    focus = intent.get("focus") or slide.get("focus_subject_id") or slide.get("focus")
    if focus:
        for e in slide.get("elements", []) or []:
            if isinstance(e, dict) and e.get("id") == focus:
                return "focus", {"kind": "element", "element": e}
    ga = intent.get("gravity_anchor") or slide.get("gravity_anchor")
    if isinstance(ga, dict):
        try:
            x, y = float(ga.get("x")), float(ga.get("y"))
            if 0 <= x <= 1 and 0 <= y <= 1:
                x, y = x * cw, y * ch   # 归一化声明 → 像素
            return "gravity_anchor", {"kind": "point", "x": x, "y": y}
        except (TypeError, ValueError):
            pass
    return None, None


def render_evidence(pptx: Path, spec: dict, out_dir: Path | None = None,
                    dpi: int = 96, pages: list[int] | None = None,
                    workers: int = MAX_RENDER_WORKERS,
                    use_cache: bool = True,
                    raster: str = "auto") -> dict[str, Any]:
    """
    编译产物 + spec → 每页渲染证据。
    返回 {"rendered", "reason", "pages", "coverage"}；pages[i]["index"] 与
    spec.slides[i] 一一对应（按绝对页码对齐，不按结果位置——否则子集渲染会把
    已测页的指标串到未测页上）。

    pages：只测这些 1-based 页（None=全量）；workers：最多 2，块间并行；
    use_cache：命中 render_cache.json 的页直接复用指标，全部命中时连 LibreOffice
    都不启动。缓存键 = 该页内容 + 画布 + dpi + Accent + 渲染器身份，因此其他页的
    修改不会让本页失效；证据 PNG 保留在原目录，可随时复核。

    raster：光栅化格式。
      "auto"/"tiff"（默认）＝ TIFF+LZW，**无损且快**（比 PNG 快约 8×，像素完全等价），
                             无需任何复检，是发布判定的默认口径；
      "png"                 ＝ 无损 PNG（最慢，兼容性与存档性最好，取证/排障用）；
      "jpeg"                ＝ 有损快测，会对指标贴着判定阈值的页自动无损复检；
                              仅在超大 deck 追求极限速度时使用。
    """
    work = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="pptx-render-"))
    work.mkdir(parents=True, exist_ok=True)
    work = work.resolve()      # 证据目录统一绝对化：相对路径会让 LibreOffice 卡死
    slides = spec.get("slides") or []
    canvas = spec.get("canvas") or {}
    cw = float(canvas.get("width", DEFAULT_WIDTH))
    ch = float(canvas.get("height", DEFAULT_HEIGHT))
    theme = spec.get("theme") or {}
    accent_hex = str((theme.get("colors") or {}).get("accent") or "").strip() or None
    renderer = str(find_renderer() or "")
    base = Path(pptx).parent          # 与编译器同口径：相对 src 以产物所在目录为基准

    def _key(n: int) -> str:
        s = slides[n - 1] if n <= len(slides) else None
        return _slide_key(s, canvas, int(dpi), theme, renderer,
                          _media_stamp(s, base),
                          focus=str(((s or {}).get("page_intent") or {}).get("focus") or ""))

    keys = {n: _key(n) for n in range(1, len(slides) + 1)}
    cache = _load_cache(work) if use_cache else {}
    live: dict[int, dict] = {}
    if use_cache:
        for n, k in keys.items():
            entry = cache.get(k)
            if entry and _png_present(work, entry):
                live[n] = entry

    wanted = list(range(1, len(slides) + 1)) if not pages else sorted({int(n) for n in pages})
    need = [n for n in wanted if n not in live]
    if not need:                        # 全命中：一次进程都不起
        out = [_reuse_entry(live[n], n, slides, cw, ch) for n in wanted]
        return {"rendered": True, "reason": None, "pages": out,
                "coverage": {"rendered_pages": len(out), "total_pages": len(slides),
                             "rendered_ids": [p["slide"] for p in out],
                             "requested": wanted, "workers": 0,
                             "cache_hits": len(out), "cache_misses": 0,
                             "unrendered": None}}

    token = _run_token(Path(pptx), need)
    # 冷测（use_cache=False）不清空证据目录：清它会把别人的热缓存打回冷态。
    keep = None if not use_cache else {e["png"] for e in live.values() if e.get("png")}
    # 只重测少数页时，拆成小 deck 转 PDF（1 页 0.52s vs 整份 2.14s）
    mini_pdf, mini_map, mini_tmp = (None, None, None)
    reusable_full = _pdf_is_reusable(Path(pptx), work, renderer) if use_cache else None
    if reusable_full is None and use_cache and _partial_worth_it(need, len(slides)):
        mini_deck, mini_map = _subset_deck(Path(pptx), need)
        if mini_deck is not None:
            mini_tmp = mini_deck.parent
            mp, _ = _pdf_from_pptx(mini_deck, mini_tmp, keep_pngs=None)
            mini_pdf = mp
        if mini_pdf is None:                 # 拆失败 → 整份转换，正确性优先
            mini_map = None
            try:
                shutil.rmtree(mini_tmp, ignore_errors=True)
            except Exception:
                pass
            mini_tmp = None
    # PPTX 逐字节没变就先复用上一轮 PDF：soffice 只能整份转换（实测 1.7s），
    # 而 Level 2 → Level 3、改 dpi 抽查这类二次运行的输入文件并没有变化。
    pdf = reusable_full
    reason = None
    if pdf is None and mini_pdf is None:
        pdf, reason = _pdf_from_pptx(Path(pptx), work, keep_pngs=keep)
        if pdf is not None:
            _pdf_record(Path(pptx), work, pdf, renderer)
    if pdf is None and mini_pdf is None:
        return {"rendered": False, "reason": reason, "pages": []}
    total = _pdf_page_count(pdf) if pdf is not None else len(slides)
    need = [n for n in need if 1 <= n <= total]

    def _measure(n: int, png: Path) -> dict[str, Any]:
        """逐页像素测量 + 声明锚点对比（在 worker 线程内执行，只读 spec）。"""
        slide = slides[n - 1] if n - 1 < len(slides) else None
        item: dict[str, Any] = {"slide": (slide.get("id") if slide else f"page_{n}"),
                                "index": n - 1, "page": n,
                                **measure_image(png, accent_hex=accent_hex,
                                                text_regions=_text_regions(
                                                    slide, cw, ch, theme)),
                                **optical_alignment(png, slide, cw, ch)}
        return _apply_anchor(item, slide, cw, ch)

    # ── 光栅化：默认 tiff+lzw（无损且快）；jpeg 为有损快测，需临界复检 ──
    mode = str(raster or "auto").lower()
    if mode in ("auto", "lossless"):
        mode = RASTER_DEFAULT
    _, _, use_jpeg = _raster_args(mode)
    src_pdf = mini_pdf if mini_pdf is not None else pdf
    if mini_map:
        # 小 deck 的页号是局部的；work 收到的必须是**原页号**，否则指标串页
        def _work(n, png):
            return _measure(mini_map[n], png)
        want_pages = sorted(mini_map.keys())
    else:
        _work = _measure
        want_pages = need
    measured = _run_pipeline(src_pdf, work, dpi, want_pages, workers, _work, token,
                             raster=mode)
    # 校验二：拆页渲染时每一页都必须有产物，缺一页就整份重来（绝不拿别页顶替）
    if mini_map and (len(measured) != len(mini_map)):
        measured = {}
    if mini_map and measured:
        for k, n in mini_map.items():
            _rename_evidence(work, token, k, n)
        # 键从小 deck 页号回填为原页号：不回填会让「第 1 页拿到第 5 页的指标」
        measured = {mini_map.get(n, n): v for n, v in measured.items()}
    if not measured:
        if mini_pdf is not None:             # 拆页失败，退回整份
            try:
                shutil.rmtree(mini_tmp, ignore_errors=True)
            except Exception:
                pass
            mini_pdf, mini_map, mini_tmp = (None, None, None)
            if pdf is None:
                pdf, reason = _pdf_from_pptx(Path(pptx), work, keep_pngs=keep)
                if pdf is not None:
                    _pdf_record(Path(pptx), work, pdf, renderer)
            if pdf is None:
                return {"rendered": False, "reason": reason, "pages": []}
            measured = _run_pipeline(pdf, work, dpi, need, workers, _measure, token,
                                     raster=mode)
        if not measured:
            return {"rendered": False, "reason": "pdftoppm produced no pages", "pages": []}
    # ── 临界页无损复检：JPEG 编码噪声不得改变发布判定 ──
    rechecked: list[int] = []
    if use_jpeg and mode == "auto":
        acc_max = None
        for src in (spec.get("constraints") or {}, (theme.get("constraints") or {})):
            if isinstance(src, dict) and src.get("accent_max") is not None:
                try:
                    acc_max = float(src["accent_max"])
                except (TypeError, ValueError):
                    pass
                break
        marginal = sorted(n for n, it in measured.items() if _near_threshold(it, acc_max))
        if marginal:
            if mini_map:
                inv = {v: k for k, v in mini_map.items()}
                sub = sorted(inv[n] for n in marginal if n in inv)

                def _work2(n, png):
                    return _measure(mini_map[n], png)
                fixed_sub = _run_pipeline(src_pdf, work, dpi, sub, 1, _work2,
                                          token + "x", raster=RASTER_DEFAULT)
                for k, n in mini_map.items():
                    _rename_evidence(work, token + "x", k, n)
                fixed = {mini_map[k]: v for k, v in fixed_sub.items()}
            else:
                fixed = _run_pipeline(pdf, work, dpi, marginal, 1, _measure,
                                      token + "x", raster=RASTER_DEFAULT)
            for n, it in fixed.items():
                measured[n] = it      # 无损结果覆盖快测结果
            rechecked = sorted(fixed.keys())
    if mini_tmp is not None:
        try:
            shutil.rmtree(mini_tmp, ignore_errors=True)
        except Exception:
            pass
    if use_cache:                        # 只保留本 deck 的条目：自动裁剪，不会无限增长
        fresh = {}
        for n in measured:
            name = _png_name(work, n, token)
            if not name:                 # 找不到本轮 PNG → 不入库（宁缺勿错）
                continue
            fresh[keys[n]] = dict(measured[n], png=name,
                                  png_sha=_file_sha(work / name),
                                  raster=(mode if (use_jpeg and n not in rechecked)
                                          else (mode if not use_jpeg else RASTER_DEFAULT)))
        merged = {k: v for k, v in cache.items() if k in set(keys.values())}
        merged.update({k: v for k, v in fresh.items() if v.get("png_sha")})
        _save_cache(work, merged)
    out = []
    for n in sorted(wanted):
        if n in measured:
            out.append(dict(measured[n], cached=False))
        elif n in live:
            out.append(_reuse_entry(live[n], n, slides, cw, ch))
    gaps = [n for n in need if n not in measured]
    cached_n = sum(1 for p in out if p.get("cached"))
    return {"rendered": True,
            "reason": (f"missing rendered pages: {gaps}" if gaps else None),
            "pages": out,
            "coverage": {"rendered_pages": len(out), "total_pages": len(slides),
                         "rendered_ids": [p["slide"] for p in out],
                         "requested": wanted, "workers": _clamp_workers(workers),
                         "cache_hits": cached_n, "cache_misses": len(measured),
                         "unrendered": gaps or None,
                         "raster": mode,
                         "lossless_recheck": rechecked}}


# --------------------------------------------------------------------------
# 可选 CLI： python render_check.py deck.pptx build_mydeck.py [out_dir]
# --------------------------------------------------------------------------
def main(argv):
    import json
    flags = list(argv)
    opts = {"dpi": 96, "pages": None, "workers": MAX_RENDER_WORKERS}
    pos: list[str] = []
    i = 0
    while i < len(flags):
        a = flags[i]
        if a in ("--dpi", "--pages", "--workers") and i + 1 < len(flags):
            val = flags[i + 1]
            if a == "--pages":
                opts["pages"] = [int(x) for x in val.split(",") if x.strip()]
            elif a == "--dpi":
                opts["dpi"] = int(val)
            else:
                opts["workers"] = int(val)
            i += 2
            continue
        pos.append(a)
        i += 1
    if len(pos) < 3:
        print("usage: python render_check.py <deck.pptx> <build_module.py> [out_dir] "
              "[--dpi N] [--pages 1,5,12] [--workers 1|2]")
        return 1
    import importlib.util
    pptx = Path(pos[1])
    mod_path = Path(pos[2])
    spec_mod = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    mod = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    out = Path(pos[3]) if len(pos) > 3 else None
    result = render_evidence(pptx, spec, out, dpi=opts["dpi"], pages=opts["pages"],
                             workers=opts["workers"])
    print(json.dumps({"rendered": result["rendered"], "reason": result.get("reason"),
                      "coverage": result.get("coverage"), "pages": result["pages"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
