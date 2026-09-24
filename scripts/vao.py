#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VAO · 唯一生产入口（one entry, one deterministic pass）。

    THINK   plan    brief → 判断面（plan.json）+ build 骨架（+ 资产清单）
    BUILD   作者填骨架（构图/尺度/留白是设计判断，引擎不预设）
    VERIFY  check   normalize → guard 硬门 → compile → 可选关键页取证 → PASS/BLOCK

纪律：
  * 一次调用 = 一趟确定性批处理；无逐条修复循环、无 warning 对话。
  * 失败落盘修复包（按根因分组、内嵌明细），成功不写假失败。
  * 零外部渲染器、零 reference 读取；判断归 references/，执行归这里。
  * 速度只有两档：fast（默认，两分钟档）/ strict（全量证据档）。
    `--deadline` 可跳过可选预览证据，不可跳过核心正确性。
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import time
import types
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GHOST_MIN_BUDGET_S = 4.0
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_module(path, name: str = "vao_build"):
    """加载作者的 build 模块：总是执行磁盘当前源码（不写 __pycache__）。"""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(
            f"找不到 build 文件: {source}"
            "（先 `vao.py plan brief.yml --skeleton build.py` 生成骨架，填充后再 check）")
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"build 文件不是 UTF-8 文本：{source}（{exc.reason}）") from None
    try:
        code = compile(text, str(source), "exec")
    except SyntaxError as exc:
        raise ValueError(f"build 文件语法错误：{source}:{exc.lineno}:{exc.offset or 0} — {exc.msg}"
                         + (f"\n  {exc.text.rstrip()}" if exc.text else "")) from None
    mod = types.ModuleType(name)
    mod.__file__ = str(source)
    import builtins
    mod.__dict__["__builtins__"] = builtins
    exec(code, mod.__dict__)
    sys.modules.setdefault(name, mod)
    return mod, source


def load_spec(path):
    """读 build.py / JSON / YAML 编排稿，不加载 references。"""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(
            f"找不到 spec 文件: {source}"
            "（先 `vao.py plan brief.yml --skeleton build.py` 生成骨架，填充后再 check）")
    if source.suffix.lower() in {".json", ".yml", ".yaml"}:
        text = source.read_text(encoding="utf-8")
        if source.suffix.lower() == ".json":
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"spec JSON 解析失败：{source}:{exc.lineno}:{exc.colno}"
                                 f" — {exc.msg}") from None
        else:
            import yaml
            try:
                value = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                mark = getattr(exc, "problem_mark", None)
                where = f":{mark.line + 1}:{mark.column + 1}" if mark else ""
                raise ValueError(f"spec YAML 解析失败：{source}{where} — {exc}") from None
        if not isinstance(value, dict):
            raise ValueError(f"spec 顶层必须是对象，实际是 {type(value).__name__}：{source}")
        return value, source
    if source.suffix.lower() != ".py":
        raise ValueError("编排文件只接受 JSON/YAML，或作者明确指定的可信 .py 文件")
    mod, source = _load_module(source)
    if hasattr(mod, "build_spec"):
        try:
            value = mod.build_spec()
        except Exception as exc:
            raise ValueError(f"build_spec() 执行失败：{source} — "
                             f"{type(exc).__name__}: {exc}") from None
    elif hasattr(mod, "SPEC"):
        value = mod.SPEC
    else:
        raise ValueError(f"build 模块必须定义 build_spec() 或 SPEC：{source}")
    if not isinstance(value, dict):
        raise ValueError(f"build_spec() / SPEC 必须是 dict：{source}")
    return value, source


def _json_write(path, value):
    from primitives import json_write
    return json_write(path, value)


def bind_asset_manifest(spec, manifest_path, assets_dir=None):
    """把 asset_id 图片元素绑到清单文件（不改 build.py；缺图留给编译诊断）。"""
    from primitives import json_read_cached
    from assets import asset_entries, asset_root, resolve_asset
    manifest_file = Path(manifest_path).expanduser().resolve()
    payload = json_read_cached(manifest_file)
    by_id = {str(item["asset_id"]): item for item in asset_entries(payload)}
    root = asset_root(payload, manifest_file, assets_dir)
    bound, missing, missing_files = [], [], []
    result = copy.deepcopy(spec)

    def walk(value):
        if isinstance(value, dict):
            asset_id = value.get("asset_id")
            if asset_id and value.get("type") == "image":
                key = str(asset_id)
                item = by_id.get(key)
                if item:
                    src = resolve_asset(item, payload, manifest_file, assets_dir)
                    value["src"] = str(src)
                    if not src.is_file():
                        missing_files.append(str(src))
                    bound.append({"asset_id": key, "src": str(src)})
                else:
                    missing.append(key)
                    value.setdefault("src", f"__missing_asset__/{key}.png")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(result)
    report = {"manifest": str(manifest_file), "assets_dir": str(root), "bound": bound,
              "bound_count": len(bound), "missing_asset_ids": sorted(set(missing)),
              "missing_files": sorted(set(missing_files)),
              "status": "PASS" if not missing and not missing_files else "BLOCK"}
    return result, report


# ══════════════════════════════════════════════════════════════════
# THINK · plan
# ══════════════════════════════════════════════════════════════════
def run_plan(brief_path: str, out: str | None = None, skeleton: str | None = None,
             assets_out: str | None = None, assets_dir: str | None = None,
             asset_cache: str | None = None) -> dict:
    from intelligence import load_brief, think, build_skeleton
    from assets import build_manifest, prepare_manifest, now

    t0 = time.perf_counter()
    brief = load_brief(brief_path)
    bundle = think(brief)
    if not bundle.get("pages"):
        raise ValueError("brief 里没有可路由的页面（slides 为空或每页都缺 title/content）："
                         "请至少给出一页的 title + content，再跑 plan")
    # workflow 只留被消费的凭证：dict 级 brief 哈希零消费者（比对早删，只剩记录），已删；
    # brief 文件哈希是 verify_sources 的篡改口径，保留且只算一次。
    bundle["workflow"] = {"planned_at": now(),
                          "brief_path": str(Path(brief_path).expanduser().resolve()),
                          "brief_file_sha256": None}
    from primitives import file_digest
    bundle["workflow"]["brief_file_sha256"] = file_digest(Path(brief_path).expanduser())
    if out:
        _json_write(out, bundle)
    if skeleton:
        target = Path(skeleton).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        # 覆写保护：已填稿的骨架（elements 非空）不被重跑冲掉。
        if target.is_file():
            old = target.read_text(encoding="utf-8", errors="replace")
            if re.search(r'"elements"\s*:\s*\[\s*\{', old):
                safe = target.with_name(target.name + ".new.py")
                safe.write_text(build_skeleton(bundle), encoding="utf-8")
                print(f"skeleton: 检测到已填稿的 {target.name}，新骨架改写 {safe.name}（不覆盖作业稿）")
            else:
                target.write_text(build_skeleton(bundle), encoding="utf-8")
        else:
            target.write_text(build_skeleton(bundle), encoding="utf-8")
    if assets_out:
        manifest = build_manifest(brief, bundle, cache_path=asset_cache)
        manifest = prepare_manifest(manifest, brief, bundle, brief_path, out,
                                    assets_out, assets_dir)
        _json_write(assets_out, manifest)
    bundle["planning_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return bundle


# ══════════════════════════════════════════════════════════════════
# VERIFY · check（一趟：normalize → guard → compile → 预览 → 结论）
# ══════════════════════════════════════════════════════════════════
def _compile_step(spec, output_path, *, speed, spec_path=None,
                  image_bytes=None, digests=None, decoded=None):
    """产物生产：缓存探测 → 编译 → 产物凭证（一次哈希）→ 缓存写入。"""
    from primitives import compile_reuse, record_compile, spec_view, file_digest

    t0 = time.perf_counter()
    compile_report = None
    cache_reason = "not_attempted"
    cache_root = output_path.with_name(output_path.stem + "_vao")
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        view = spec_view(spec, base_path=output_path.parent, spec_path=spec_path,
                         image_bytes=image_bytes, digests=digests)
        compile_report = compile_reuse(cache_root, output_path, view,
                                       fast_probe=(speed == "fast"), speed=speed)
        cache_reason = "hit" if compile_report is not None else "miss"
    except Exception:
        cache_reason = "probe_failed"
        compile_report = None
    t_cache = time.perf_counter()
    if compile_report is None:
        from compiler import compile_deck      # 惰性导入：缓存命中路径不付 pptx 导入成本
        try:
            compile_report = compile_deck(spec, output_path,
                                          decode_seed=decoded,
                                          spec_path=str(spec_path) if spec_path else None,
                                          image_bytes=image_bytes, speed=speed)
        except ModuleNotFoundError as exc:
            if exc.name in {"pptx", "lxml", "PIL", "numpy"}:
                compile_report = {
                    "passed": False, "slides": len(spec.get("slides") or []),
                    "warnings": [f"缺少编译依赖 {exc.name!r}；请运行 "
                                 "python -m pip install -r requirements.txt"],
                    "file_bytes": None}
            else:
                raise
    t_compile = time.perf_counter()
    # 产物凭证：报告必须对得上磁盘上那一份 PPTX（一次哈希，无二级见证）。
    if not compile_report.get("skipped"):
        try:
            stat = output_path.stat()
            actual_sha = file_digest(output_path)
            expected_sha = compile_report.get("output_sha256")
            if expected_sha and expected_sha != actual_sha:
                compile_report.setdefault("warnings", []).append(
                    "编译报告 output_sha256 与实际 PPTX 不一致")
                compile_report["passed"] = False
            compile_report["file_bytes"] = stat.st_size
            compile_report["output_sha256"] = actual_sha
            compile_report["output_path"] = str(output_path.resolve())
            compile_report["output_exists"] = True
        except (OSError, TypeError, ValueError):
            compile_report.setdefault("warnings", []).append(
                f"编译输出不存在或不可读取: {output_path}")
            compile_report["passed"] = False
            compile_report["output_exists"] = False
            compile_report["output_sha256"] = None
        if compile_report.get("output_sha256") and compile_report.get("output_exists") \
                and cache_reason in ("miss", "probe_failed"):
            try:
                view = view if cache_reason == "miss" else spec_view(
                    spec, base_path=output_path.parent, spec_path=spec_path,
                    image_bytes=image_bytes, digests=digests)
                record_compile(cache_root, output_path, view, compile_report)
            except Exception:
                pass
    timing = {"cache_ms": int((t_cache - t0) * 1000),
              "compile_ms": int((t_compile - t0) * 1000),
              "attestation_ms": int((time.perf_counter() - t_compile) * 1000),
              "cache_reason": cache_reason, "cache_enabled": True,
              "cache_dir": str(cache_root)}
    return compile_report, timing


def _ghost(spec, output_dir, pages=None, base_path=None, image_bytes=None,
           decoded=None, *, speed="strict", limit=24, output_sha=None) -> dict:
    """关键页取证（PIL 结构预览；页级缓存内建于 ghost 模块）。

    整份证据复用凭证只有一个：产物 sha256 + 渲染器指纹 + 速度档一致 ⇒
    上一轮的预览就是这一轮的预览（页缓存保证 0 页重画；联络表本身也是
    页图的纯函数）。凭证不匹配（产物/渲染器变了）即重渲。
    """
    from ghost import PAGE_CACHE_DIR, ghost_deck, key_selection, make_contact_sheet
    from primitives import engine_fingerprint
    target = Path(output_dir)
    marker = target / "ghost.meta.json"
    engine = engine_fingerprint("preview")
    if output_sha and marker.exists():
        try:
            cached = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = {}
        if (cached.get("output_sha256") == output_sha and cached.get("engine") == engine
                and cached.get("renderer_speed") == str(speed) and cached.get("pages")):
            info = dict(cached)
            info["reused"] = True
            return info
    fast = str(speed).lower() == "fast"
    slides = spec.get("slides") or []
    roles = None
    if pages is not None:
        wanted = [int(n) for n in pages]
        scope = "full" if len(wanted) >= len(slides) else "explicit_subset"
    elif fast:
        wanted, roles = key_selection(slides, limit=limit)
        scope = "full" if len(wanted) >= len(slides) else "key_pages"
    else:
        wanted = list(range(1, len(slides) + 1))
        scope = "full"
    preview_spec = dict(spec)
    preview_spec["_image_bytes"] = image_bytes or {}
    preview_spec["_image_decoded"] = decoded or {}
    if base_path:
        preview_spec["_base_path"] = str(Path(base_path).resolve())
    rendered: list = []
    page_stats: dict = {}
    paths = ghost_deck(preview_spec, output_dir, pages=wanted,
                       scale=0.5, supersample=1 if fast else 2, store=True,
                       png_compress_level=1 if fast else 6, images_out=rendered,
                       stats=page_stats)
    sheet_stats: dict = {}
    contact = make_contact_sheet(paths, Path(output_dir) / "ghost-contact-sheet.png",
                                 images=rendered,
                                 png_compress_level=1 if fast else 6,
                                 cache_dir=Path(output_dir) / PAGE_CACHE_DIR,
                                 stats=sheet_stats)
    rendered_ids = [str(slides[n - 1].get("id")) for n in wanted
                    if 1 <= n <= len(slides) and isinstance(slides[n - 1], dict)]
    info = {"type": "ghost_layout_preview", "dir": str(Path(output_dir)),
            "key_pages": (roles if scope == "key_pages" else None),
            "pages": [str(p) for p in paths], "count": len(paths),
            "slide_ids": rendered_ids,
            "pages_rendered": wanted, "page_count": len(slides),
            "scope": scope, "contact_sheet": str(contact) if contact else None,
            "renderer": "PIL", "supersampled": not fast,
            "pages_drawn": len(page_stats.get("rendered_pages") or []),
            "pages_from_cache": len(page_stats.get("cached_pages") or []),
            "contact_sheet_cached": bool(sheet_stats.get("sheet_cached")),
            "evidence_scope": "direction_and_structure_not_pixel_proof"}
    info["output_sha256"] = output_sha
    info["engine"] = engine
    info["renderer_speed"] = str(speed)
    info["reused"] = False
    try:
        target.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    except (OSError, TypeError, ValueError):
        pass
    return info


def repair_packet(result: dict, mode: str, build, output) -> dict:
    """默认唯一面向作者的产物：BLOCK 时按根因分组（内嵌明细）；PASS 时一行结论。"""
    packet = {
        "mode": mode,
        "build": str(build),
        "output": str(output),
        "verdict": result.get("verdict"),
        "status": result.get("status"),
        "passed": result.get("passed"),
        "blocking_items": result.get("blocking_items", 0),
        "failure_codes": result.get("failure_codes", []),
        "affected_slides": result.get("affected_slides", []),
        "fix_plan": result.get("fix_plan") or {"groups": []},
        "asset_workflow": result.get("asset_workflow"),
        "release_eligible": result.get("release_eligible", False),
        "next_action": result.get("next_action"),
        "timing": result.get("performance"),
        # 无 facts 键：verdict 不产出自由事实，packet 只收口已定义的修复字段。
    }
    return packet


def run_check(build_path: str, output: str, *, mode: str = "draft",
              packet: str | None = None, preview: str | None = None,
              json_output: bool = False,
              assets_manifest: str | None = None, assets_dir: str | None = None,
              speed: str = "fast", deadline: float | None = None,
              ghost_pages: int = 5) -> tuple:
    """一次执行完成交付验证。失败落盘 fail-closed；成功不写假失败。"""
    started = time.perf_counter()
    output_path = Path(output).expanduser()
    packet_path = Path(packet).expanduser() if packet else output_path.with_suffix(".repair.json")
    mode = str(mode or "draft").strip().lower()

    def fail(exc: Exception) -> tuple:
        from verify import fail_result
        result = fail_result({}, [f"输入或执行失败: {type(exc).__name__}: {exc}"])
        result["performance"] = {"total_ms": round((time.perf_counter() - started) * 1000, 1)}
        packet_obj = repair_packet(result, mode, build_path, output_path)
        _json_write(packet_path, packet_obj)
        line = (json.dumps(packet_obj, ensure_ascii=False) if json_output else
                f"VAO {mode}: BLOCKED · {result['next_action']}\n  packet: {packet_path}")
        print(line)
        return result, 2

    try:
        spec, build = load_spec(build_path)
        if mode != "spec":
            import importlib.util
            missing = next((n for n in ("pptx",) if importlib.util.find_spec(n) is None), None)
            if missing:
                raise ModuleNotFoundError(f"missing compiler dependency: {missing}")
        from assets import (blocked_result, qc_report, verify_chain)
        from verify import (check_spec, mode_profile, normalize_spec,
                            release_guard_rules, verdict)
        from primitives import spec_fingerprint

        spec_hash = spec_fingerprint(spec)          # 本轮唯一一次 spec 身份

        snapshots: dict = {}   # 本轮唯一一次读图：QC / 核验 / 编译 / 预览共用
        decoded: dict = {}     # 核验解码过的底图：编译期不再重复解码
        digests: dict = {}     # 本轮唯一一次哈希
        asset_binding = None
        t_qc = time.perf_counter()
        if assets_manifest:
            spec, asset_binding = bind_asset_manifest(spec, assets_manifest, assets_dir)
        # 资产链：QC（若有清单）→ 核验。一次执行只给一条修法。
        workflow = {"status": "SKIPPED", "issues": [], "image_count": 0,
                    "reason": "no_manifest_provided"}
        if assets_manifest:
            qc_result, _ = qc_report(assets_manifest, assets_dir, phase=mode,
                                     speed=speed, snapshots=snapshots,
                                     decoded=decoded, digests=digests)
            workflow = verify_chain(spec, assets_manifest,
                                    qc_result.get("report_path"), assets_dir,
                                    image_bytes=snapshots, digests=digests)
            if asset_binding and (asset_binding.get("missing_asset_ids")
                                  or asset_binding.get("missing_files")):
                workflow["status"] = "BLOCKED"
                workflow.setdefault("issues", []).append(
                    "asset binding: " + "、".join(
                        asset_binding.get("missing_asset_ids", [])
                        + asset_binding.get("missing_files", [])))
        qc_ms = round((time.perf_counter() - t_qc) * 1000, 1) if assets_manifest else 0
        started_guard = time.perf_counter()
        if workflow.get("status") == "BLOCKED":
            result = blocked_result(spec, workflow)
            result["asset_workflow"] = workflow
            result["source_spec_hash"] = spec_hash
            _json_write(packet_path, repair_packet(result, mode, build, output_path))
            _print_line(result, None, None, packet_path, speed, mode, json_output)
            return result, 2
        normalized, norm = normalize_spec(spec)
        prof = mode_profile(mode)
        effective_rules = release_guard_rules(prof["mode"], None)
        guard_report = check_spec(normalized, rules=effective_rules)
        guard_ms = round((time.perf_counter() - started_guard) * 1000, 1)
        guard_errors = [c for c in guard_report.get("checks", []) if c.get("level") == "error"]
        timing = {"guard_ms": guard_ms, "qc_ms": qc_ms, "normalization": norm,
                  "provenance_required": bool(effective_rules.get("require_provenance", False)),
                  "speed": speed}
        if not prof["compile"]:
            compile_report = {"passed": True, "skipped": True, "warnings": [],
                              "file_bytes": None,
                              "output_exists": False, "output_sha256": None}
            timing.update(compile_ms=0, attestation_ms=0, cache_reason="not_compiled")
        elif guard_errors:
            compile_report = {"passed": False, "skipped": True, "warnings": [],
                              "file_bytes": None,
                              "output_exists": False, "output_sha256": None}
            timing.update(compile_ms=0, attestation_ms=0, cache_reason="guard_error")
        else:
            compile_report, compile_timing = _compile_step(
                normalized, output_path, speed=speed, spec_path=str(build),
                image_bytes=snapshots, digests=digests, decoded=decoded)
            timing.update(compile_timing)
        timing["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        result = verdict(normalized, mode=mode, guard_report=guard_report,
                         compile_report=compile_report, spec_hash=spec_hash,
                         runtime_facts={**timing, "asset_workflow": workflow})
        result["asset_workflow"] = workflow
        if asset_binding is not None:
            result["asset_binding"] = asset_binding

        # 预览证据：release 自动出；draft 只在显式要求时出；预算不足跳过
        # （无预览产物即跳过，不单独立账——skipped_stages 零消费者，已删）。
        ghost = None
        preview_dir = preview or (str(output_path.with_name(output_path.stem + "_preview"))
                                  if mode == "release" else None)
        if preview_dir and result.get("passed") and workflow.get("status") != "BLOCKED":
            left = None if not deadline else (deadline - (time.perf_counter() - started))
            if left is None or left >= GHOST_MIN_BUDGET_S:
                t_ghost = time.perf_counter()
                ghost = _ghost(normalized, preview_dir, base_path=build.parent,
                               image_bytes=snapshots, decoded=decoded,
                               speed=speed, limit=ghost_pages,
                               output_sha=(result.get("compile") or {}).get("output_sha256"))
                timing["ghost_ms"] = round((time.perf_counter() - t_ghost) * 1000, 1)
        result["performance"] = {**result.get("performance", {}),
                                 "ghost_ms": timing.get("ghost_ms"),
                                 "total_ms": timing["total_ms"]}

        manifest = None
        manifest_path = None
        if mode == "release":
            from verify import release_manifest
            manifest = release_manifest(normalized, result, ghost_preview=ghost,
                                        workflow=workflow, spec_hash=spec_hash,
                                        output_verified=True)
            if manifest["status"] == "BLOCKED" and result.get("passed"):
                from verify import fail_result
                errors = manifest["validation"]["issues"] or ["发布凭证无效"]
                fail_result(result, errors)
                manifest = release_manifest(normalized, result, ghost_preview=ghost,
                                            workflow=workflow, output_verified=True)
            manifest_path = output_path.with_suffix(".manifest.json")
            _json_write(manifest_path, manifest)
            result["manifest_path"] = str(manifest_path)
        _json_write(packet_path, repair_packet(result, mode, build, output_path))
        _print_line(result, ghost, manifest_path, packet_path, speed, mode, json_output)
        binding_block = bool(asset_binding and (asset_binding.get("missing_asset_ids")
                                                or asset_binding.get("missing_files")))
        return result, (0 if result.get("passed") and not binding_block else 2)
    except Exception as exc:
        return fail(exc)


def _print_line(result, ghost, manifest_path, packet_path, speed,
                mode, json_output) -> None:
    """一次执行一条结论；证据在文件里，对话里只有注意力预算内的几行。"""
    if json_output:
        print(json.dumps({"status": result.get("status"),
                          "verdict": result.get("verdict"),
                          "failure_codes": result.get("failure_codes"),
                          "fix_plan": result.get("fix_plan"),
                          "next_action": result.get("next_action"),
                          "timing": result.get("performance")},
                         ensure_ascii=False, default=str))
        return
    total = result.get("performance", {}).get("total_ms")
    ms = f" · {total / 1000:.2f}s" if isinstance(total, (int, float)) else ""
    if result.get("passed"):
        line = f"VAO {mode}: PASS{ms} · speed={speed}"
        comp = result.get("compile") or {}
        if comp.get("output_path"):
            size_kb = (comp.get("file_bytes") or 0) / 1024
            sha = str(comp.get("output_sha256") or "")[:12]
            reuse = "（缓存复用，未重编）" if comp.get("reused") else ""
            line += f"\n  pptx: {comp['output_path']} ({size_kb:.0f}KB · sha256 {sha}…){reuse}"
    else:
        groups = (result.get("fix_plan") or {}).get("groups") or []
        line = f"VAO {mode}: BLOCKED{ms} · {len(groups)} 组根因"
        for g in groups[:6]:
            ids = ",".join(str(i) for i in (g.get("ids") or [])[:6])
            line += (f"\n  [{g.get('root_cause')}] ×{g.get('count')}"
                     + (f" ({ids})" if ids else "") + f" → {g.get('fix', '')}")
        line += f"\n  packet: {packet_path}"
    if ghost:
        scope = ghost.get("scope")
        line += f"\n  preview: {ghost.get('count')} 页 ghost（{scope}）→ {Path(ghost['dir']).name}/"
    if manifest_path:
        line += f"\n  manifest: {manifest_path}"
    print(line)


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════
SPEED_PROFILES = {
    "fast": "两分钟交付档：像素统计降采样、图片只读一次、预览只画关键页、缓存快探",
    "strict": "严格档：全分辨率 QC、整包缓存核对、逐页预览（忽略 --ghost-pages）",
}
DEFAULT_SPEED = "fast"
DEFAULT_DEADLINE = 120.0
DEFAULT_GHOST_PAGES = 5      # fast 档只画关键页（封面/章节/画心/密数据/收尾）


def _add_speed_flags(parser):
    parser.add_argument("--speed", choices=tuple(SPEED_PROFILES), default=DEFAULT_SPEED,
                        help="fast（默认）= 两分钟交付档；strict = 全量证据档")
    parser.add_argument("--deadline", type=float, default=DEFAULT_DEADLINE,
                        help="本次调用墙钟预算（秒，默认 120）；预算不足时跳过可选预览并留痕")
    parser.add_argument("--ghost-pages", type=int, default=DEFAULT_GHOST_PAGES,
                        help="fast 档关键页数量上限（封面/章节/画心/密数据/收尾）；"
                             "strict 档逐页预览，此参数被忽略")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vao.py", description="PPT Visual Art Director OS · one fast entry point")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="THINK：brief → plan.json + build 骨架（+ 资产清单）")
    p.add_argument("brief")
    p.add_argument("--out", dest="plan_out", default="plan.json")
    p.add_argument("--skeleton")
    p.add_argument("--assets-out", help="同时产出资产清单（作者据此出图）")
    p.add_argument("--assets-dir", help="图将被放到哪个目录（写进清单，check 据此核验）")
    p.add_argument("--asset-cache", help="提示词缓存 JSON；相同视觉需求指纹直接复用")
    p.add_argument("--json", action="store_true", help="print the compact plan")

    c = sub.add_parser("check", help="VERIFY：build → normalize/guard/compile/preview → 结论")
    c.add_argument("build")
    c.add_argument("output", nargs="?", default="deck.pptx")
    c.add_argument("--mode", choices=("spec", "draft", "release"), default="draft")
    c.add_argument("--packet")
    c.add_argument("--preview", help="write ghost preview PNGs here (release writes them by default)")
    c.add_argument("--assets-manifest", help="bind image elements carrying asset_id")
    c.add_argument("--assets-dir", help="directory containing generated manifest filenames")
    c.add_argument("--json", action="store_true")
    _add_speed_flags(c)

    v = sub.add_parser("preview", help="spec/build → ghost contact sheet (PIL only)")
    v.add_argument("build")
    v.add_argument("--out", default="vao_preview")
    v.add_argument("--pages", help="1-based pages, e.g. 1,3,8（默认：全部页）")
    v.add_argument("--speed", choices=("fast", "strict"), default="fast")
    v.add_argument("--assets-manifest")
    v.add_argument("--assets-dir")

    q = sub.add_parser("qc", help="资产离线体检：同判据跑像素 QC + 策略，不写状态、不消耗 retry")
    q.add_argument("--assets-manifest", required=True)
    q.add_argument("--assets-dir", default=None)
    q.add_argument("--speed", choices=["fast", "strict"], default="fast")
    q.add_argument("--json", action="store_true")
    d = sub.add_parser("dna", help="设计经验记忆：--check 体检 / --add 沉淀一条")
    d.add_argument("--add")
    d.add_argument("--replace", action="store_true")
    d.add_argument("--check", action="store_true")
    d.add_argument("--json", action="store_true")
    return parser


def _dna(args) -> int:
    from intelligence import DNA_STORE, record_dna, validate_dna_store
    if args.add:
        src = Path(args.add).expanduser()
        if not src.is_file():
            print(f"VAO error: 条目文件不存在：{src}")
            return 2
        try:
            entry = json.loads(src.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"VAO error: 条目文件解析失败（{type(exc).__name__}: {exc}）")
            return 2
        result = record_dna(entry, replace=args.replace)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        elif result.get("errors"):
            print("dna: 拒绝写入 · " + "；".join(result["errors"]))
            for w in result.get("warnings") or []:
                print(f"  - {w}")
        else:
            print(f"dna: {result.get('note', 'ok')} · store={DNA_STORE}")
        return 2 if result.get("errors") else 0
    report = validate_dna_store()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"dna store: {'OK' if report['ok'] else 'BROKEN'} · {report['entries']} 条 · "
              f"{len(report['errors'])} error / {len(report['warnings'])} warning")
        for item in report["errors"]:
            print(f"  ✗ [{item['id']}] {item['reason']}")
        for item in report["warnings"]:
            print(f"  · [{item['id']}] {item['reason']}")
    return 0 if report["ok"] else 2


def run_qc(manifest_path: str, assets_dir: str | None = None,
           speed: str = "fast") -> dict:
    """资产离线体检：与 check 同一判据（image_qc + qc_retry_decision），
    但不写 QC 报告、不递增 attempt、不进 deck 结论。

    出图迭代的最短反馈环：作者改一张图，一条命令拿到阻断/建议清单，
    不必跑全量 check 往返，也不必自建 harness（CASE_004 证据）。
    """
    from assets import image_qc, qc_retry_decision, qc_profile
    mpath = Path(manifest_path).expanduser().resolve()
    man = json.loads(mpath.read_text(encoding="utf-8"))
    base = Path(assets_dir).expanduser() if assets_dir \
        else Path(man.get("assets_dir") or "generated_assets")
    if not base.is_absolute():
        base = mpath.parent / base
    prof = qc_profile(speed)
    results = []
    for a in man.get("assets") or []:
        aid = str(a.get("asset_id"))
        path = next((base / f"{aid}.{ext}" for ext in ("png", "jpg", "jpeg", "webp")
                     if (base / f"{aid}.{ext}").is_file()), None)
        if path is None:
            results.append({"asset_id": aid, "slide_ids": a.get("slide_ids"),
                            "status": "missing", "action": "block",
                            "blocking": ["missing"], "advisory": [], "issues": []})
            continue
        meta = a.get("meta") or {}
        qc = image_qc(str(path), safe_area="left",
                      text_is_dark=(meta.get("text_color") == "dark")
                      if meta.get("text_color") else None,
                      safe_rect=a.get("safe_area"),
                      background=a.get("background_color") or "#FFFFFF",
                      max_side=prof["max_side"])
        pol = qc_retry_decision(qc, attempt=0, phase="draft",
                                asset_function=a.get("asset_function"),
                                asset_role=a.get("asset_role"))
        results.append({"asset_id": aid, "slide_ids": a.get("slide_ids"),
                        "status": qc.get("status"), "action": pol["action"],
                        "blocking": pol["blocking_checks"],
                        "advisory": pol["advisory_checks"],
                        "issues": [c.get("issue") for c in qc.get("checks", [])
                                   if c.get("status") == "issue"]})
    return {"speed": prof["speed"], "assets_dir": str(base), "results": results}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            bundle = run_plan(args.brief, args.plan_out, args.skeleton,
                              assets_out=args.assets_out, assets_dir=args.assets_dir,
                              asset_cache=args.asset_cache)
            if args.json:
                print(json.dumps(bundle, ensure_ascii=False, indent=2, default=str))
            else:
                pages = bundle.get("pages") or []
                media_pages = [p["id"] for p in pages
                               if ((p.get("judgment") or {}).get("media") or {})
                               .get("decision") not in (None, "none")]
                world = bundle["deck"].get("world") or {}
                print(f"plan: {len(pages)} 页 · 视觉世界 {world.get('name')} "
                      f"· 质量 {bundle['deck']['quality']} · "
                      f"规划 {bundle.get('planning_ms', 0)}ms")
                if bundle.get("warnings"):
                    for w in bundle["warnings"][:4]:
                        print(f"  ⚠ {w.get('msg') or w}")
                if media_pages:
                    print(f"  媒体必要性判断：出图 {','.join(media_pages)}"
                          "（可用 --assets-out 产出清单）")
                coherence = bundle["deck"].get("coherence") or {}
                if coherence.get("adjustments"):
                    shown = "；".join(
                        f"{a['page']} {a['field']} {a['from']}→{a['to']}"
                        for a in coherence["adjustments"][:3])
                    print(f"  跨页校准：{len(coherence['adjustments'])} 处回拨（{shown}）")
                if args.plan_out:
                    print(f"  plan: {args.plan_out}"
                          + (f" · skeleton: {args.skeleton}" if args.skeleton else ""))
            return 0
        if args.command == "check":
            _, code = run_check(args.build, args.output, mode=args.mode,
                                packet=args.packet, preview=args.preview,
                                json_output=args.json,
                                assets_manifest=args.assets_manifest,
                                assets_dir=args.assets_dir,
                                speed=args.speed, deadline=args.deadline,
                                ghost_pages=args.ghost_pages)
            return code
        if args.command == "preview":
            spec, _ = load_spec(args.build)
            binding = None
            if args.assets_manifest:
                spec, binding = bind_asset_manifest(spec, args.assets_manifest, args.assets_dir)
            pages = ([int(x) for x in args.pages.split(",") if x.strip()]
                     if args.pages else None)
            info = _ghost(spec, args.out, pages,
                          base_path=Path(args.build).expanduser().resolve().parent,
                          speed=args.speed)
            if binding:
                info["asset_binding"] = binding
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 2 if binding and binding["status"] == "BLOCK" else 0
        if args.command == "qc":
            rep = run_qc(args.assets_manifest, args.assets_dir, args.speed)
            print(json.dumps(rep, ensure_ascii=False, indent=2))
            return 0
        if args.command == "dna":
            return _dna(args)
        return 2
    except ModuleNotFoundError as exc:
        print(f"VAO error: missing Python dependency {exc.name!r}; "
              "install requirements.txt", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"VAO error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
