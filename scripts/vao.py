#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VAO · single entry point for the Visual Art Director OS.

Internal modules exist for maintainability; production callers only need this
file.  It never reads the reference library, never starts an external renderer,
and never turns a warning into a conversation.  One invocation = one
deterministic batch:

    plan:      brief -> compact plan -> optional skeleton
    assets:    brief + plan -> deduplicated batch asset manifest
    asset-qc:  generated images -> one grouped QC report
    check:     normalize -> guard -> compile -> preview evidence -> repair packet
    run:       plan + check in one Python process
    preview:   spec -> ghost contact sheet (PIL only, no office renderer)

The author fills the skeleton once.  If check fails, the packet contains
root-cause groups rather than a line-by-line stream.  After one grouped repair,
run the same command again; a clean draft goes directly to release.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
import types
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_module(path: str | Path, name: str = "vao_build"):
    """加载作者的 build 模块：**总是执行磁盘上的当前源码**。

    不用 importlib 的模块加载器：它会把字节码写进 `__pycache__` 并按
    「源码 mtime（秒）+ 文件大小」复用——同一秒内的两次修改、且长度不变时，
    会静默加载**旧字节码**，于是「改了 spec 却交付旧产物」。作者用编辑器保存
    两次只差一拍的文件是常态，这个坑不能留在交付链上。

    直接读源码 → compile → exec：结果只由当前文件内容决定，且不留任何缓存目录。
    """
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(
            f"找不到 build 文件: {source}"
            "（先 `vao.py run brief.yml --skeleton build.py` 生成骨架，填充后再 check）")
    code = compile(source.read_text(encoding="utf-8"), str(source), "exec")
    mod = types.ModuleType(name)
    mod.__file__ = str(source)
    mod.__dict__["__name__"] = name
    mod.__dict__["__builtins__"] = __builtins__
    exec(code, mod.__dict__)
    sys.modules.setdefault(name, mod)
    return mod, source


def load_spec(path: str | Path) -> tuple[dict, Path]:
    """Read a build.py, JSON, or YAML spec without loading references."""
    source = Path(path).expanduser().resolve()
    if source.suffix.lower() in {".json", ".yml", ".yaml"}:
        if source.suffix.lower() == ".json":
            value = json.loads(source.read_text(encoding="utf-8"))
        else:
            import yaml
            value = yaml.safe_load(source.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("spec 顶层必须是对象/dict")
        return value, source
    mod, source = _load_module(source)
    value = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    if not isinstance(value, dict):
        raise ValueError("build 模块必须定义 build_spec() 或顶层 SPEC，且返回对象")
    return value, source


def _json_write(path: str | Path, value: Any) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
                      encoding="utf-8")
    return target


def bind_asset_manifest(spec: dict, manifest_path: str | Path,
                        assets_dir: str | Path | None = None) -> tuple[dict, dict]:
    """Bind ``asset_id`` image elements to generated files without editing build.py.

    The manifest remains the source of truth for filenames.  This is deliberately
    a small pre-compile binding step: it does not invent page decisions or inject
    prompt text into the spec.  Missing references are reported as one grouped
    binding issue and are left as explicit missing paths for compiler diagnostics.
    """
    manifest_file = Path(manifest_path).expanduser().resolve()
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    entries = payload.get("assets") if isinstance(payload, dict) else None
    entries = entries if isinstance(entries, list) else []
    by_id = {str(item.get("asset_id")): item for item in entries
              if isinstance(item, dict) and item.get("asset_id")}
    bound: list[dict] = []
    missing: list[str] = []
    missing_files: list[str] = []
    result = copy.deepcopy(spec)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            asset_id = value.get("asset_id")
            if asset_id:
                key = str(asset_id)
                item = by_id.get(key)
                if item:
                    filename = str(item.get("expected_filename") or f"{key}.png")
                    src = (Path(assets_dir).expanduser().resolve() / filename
                           if assets_dir else Path(filename))
                    value["src"] = str(src) if assets_dir else filename
                    if assets_dir and not src.exists():
                        missing_files.append(str(src))
                    bound.append({"asset_id": key, "src": str(src),
                                  "slide_id": value.get("slide_id")})
                else:
                    missing.append(key)
                    value.setdefault("src", f"__missing_asset__/{key}.png")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(result)
    report = {"manifest": str(manifest_file), "assets_dir": str(Path(assets_dir).expanduser().resolve())
              if assets_dir else None, "bound": bound,
              "bound_count": len(bound), "missing_asset_ids": sorted(set(missing)),
              "missing_files": sorted(set(missing_files)),
              "status": "PASS" if not missing and not missing_files else "BLOCK"}
    return result, report


def _plan(brief_path: str, out: str | None = None, skeleton: str | None = None) -> dict:
    from pipeline import build_plan_bundle, build_skeleton_module
    from intent_compiler import _load_need

    need = _load_need(brief_path)
    bundle = build_plan_bundle(need)       # route/forecast/layout: one in-process pass
    if not bundle.get("pages"):
        # 0 页不是「轻量交付」，是死路：没有内容就没有可判断的对象。
        # 早失败并给出一句可执行的修法，胜过交回一个空计划让上层自己猜。
        raise ValueError("brief 里没有可路由的页面（slides 为空或每页都缺 title/content）："
                         "请至少给出一页的 title + content，再跑 plan")
    if out:
        _json_write(out, bundle)
    if skeleton:
        target = Path(skeleton).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(build_skeleton_module(bundle), encoding="utf-8")
    return bundle


def _asset_page(brief: dict, page_plan: dict, raw_slide: Any, *, asset_id: str,
                deck: dict | None = None) -> tuple[dict, dict]:
    """brief + one route page → compact asset card + geometric page contract."""
    from asset_prompt import enhance_asset_card, normalize_safe_area

    raw = raw_slide if isinstance(raw_slide, dict) else {"content": str(raw_slide)}
    deck = deck or {}
    derived = deck.get("direction_execution") or {}
    asset = page_plan.get("asset") or {}
    function = str(raw.get("asset_function") or asset.get("function") or "frame")
    anchor = str(raw.get("negative_space_anchor") or {
        "hero": "left", "emotion": "left", "context": "left",
        "proof": "right", "direct": "right"
    }.get(function, "left")).lower()
    safe_area = normalize_safe_area(raw.get("safe_area"), anchor)
    title = str(raw.get("title") or raw.get("content") or raw.get("text") or "visual context")
    subject = raw.get("asset_subject") or title[:180]
    direction = str(brief.get("design_direction") or brief.get("route_direction") or "")
    visual_world = str(brief.get("visual_world") or "")
    style = [s for s in (direction, visual_world[:120] if visual_world else "")
             if s and s.lower() != "unknown"]
    # 色值从**整副 deck 的主题**取（品牌优先派生过的那一份），不取方向预设的原始种子：
    # 素材必须跟着这份交付的色板走，而不是跟着方向标签走。
    deck_theme = deck.get("theme") if isinstance(deck.get("theme"), dict) else {}
    theme_colors = dict(deck_theme.get("colors") or {})
    color_cue = list(raw.get("asset_color") or [])
    if not color_cue:
        color_cue = ["neutral tonal range with one restrained accent"]
        if theme_colors.get("accent"):
            color_cue.append(f"accent color {theme_colors['accent']}")
    card = {
        "apc": f"APC-{str(asset_id).upper().replace('-', '_')}",
        "asset_type": raw.get("asset_type") or "background",
        "medium": raw.get("medium") or brief.get("asset_medium"),
        "family": str(page_plan.get("page_family") or "").lower(),
        "subject": [subject],
        "color": color_cue,
        "material": [str(derived.get("material") or raw.get("material") or "quiet matte surface")],
        "lighting": [str(derived.get("light") or raw.get("lighting") or "single soft directional light")],
        "composition": [str(derived.get("composition_grammar") or "asymmetric editorial composition")],
        "motion": [str(derived.get("motion"))] if derived.get("motion") else [],
        "style": style,
        "asset_function": function,
        "fusion_enabled": raw.get("fusion_enabled"),
        "negative": list(raw.get("negative") or []),
    }
    # Directional defaults are weak descriptors; explicit brief/card language wins.
    card = enhance_asset_card(card, family=card["family"],
                              motion=card["motion"] or None,
                              texture=raw.get("texture"),
                              fusion=card["fusion_enabled"] is not False)
    page = {
        "negative_space_anchor": anchor,
        "safe_area": safe_area,
        "text_color": raw.get("text_color") or raw.get("safe_area_text_color"),
        "light_direction": raw.get("light_direction") or "left",
        "energy": raw.get("energy") or page_plan.get("energy") or "low",
        "asset_function": function,
    }
    return card, page


def build_asset_manifest(brief: dict, bundle: dict | None = None,
                         cache_path: str | Path | None = None) -> dict:
    """Build one deduplicated, batch-ready asset manifest from a brief.

    This is the only place where route decisions become image-generation work.
    asset_prompt remains a pure translator; no reference files are read here.
    """
    from asset_prompt import asset_fingerprint, build_asset_prompt
    from pipeline import build_plan_bundle
    from route import align_pages

    if bundle is None:
        bundle = build_plan_bundle(brief)
    plan = bundle.get("plan") or {}
    route_pages = plan.get("pages") or []
    raw_slides = brief.get("slides") if isinstance(brief.get("slides"), list) else []
    prompt_cache: dict[str, dict] = {}
    cache_file = Path(cache_path).expanduser() if cache_path else None
    if cache_file:
        try:
            loaded = json.loads(cache_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                prompt_cache = loaded.get("entries") or {}
        except (OSError, ValueError, TypeError):
            prompt_cache = {}
    cache_hits = 0
    generation_ids = set((plan.get("assets") or {}).get("generate") or [])
    quality = str(plan.get("quality_level") or plan.get("path") or "fast")
    try:
        asset_cap = int((plan.get("budget") or {}).get("max_asset_calls")
                        or len(generation_ids) or 0)
    except (TypeError, ValueError):
        asset_cap = len(generation_ids)
    assets: list[dict] = []
    by_fingerprint: dict[str, dict] = {}
    generated_count = 0
    skipped_pages: list[dict] = []
    # brief slide ↔ 路由页同样按 id 认，不按位置：资产卡拿错文案就是张冠李戴。
    raw_pairs = align_pages(route_pages, raw_slides)["pairs"]
    for i, page_plan in enumerate(route_pages):
        sid = str(page_plan.get("id") or f"s{i + 1:02d}")
        decision = str((page_plan.get("asset") or {}).get("decision") or "none")
        if decision == "none":
            skipped_pages.append({"slide_id": sid, "decision": "skip",
                                  "reason": "page family reserves attention for data/text"})
            continue
        raw = raw_pairs[i][1] if i < len(raw_pairs) else {}
        provisional = f"asset-{sid}"
        card, page = _asset_page(brief, page_plan, raw, asset_id=provisional,
                                 deck=plan)
        fingerprint = asset_fingerprint(card, page)
        existing = by_fingerprint.get(fingerprint)
        if existing:
            existing["slide_ids"].append(sid)
            assets.append({"slide_id": sid, "decision": "reuse_generated",
                           "asset_id": existing["asset_id"], "fingerprint": fingerprint})
            continue
        should_generate = sid in generation_ids and generated_count < asset_cap
        # A route page outside the capped list can still reuse an already seen
        # fingerprint, but never silently creates an extra model call.
        if not should_generate:
            skipped_pages.append({"slide_id": sid, "decision": "budget_skip" if decision == "required" else "reuse",
                                  "reason": "asset budget or route policy", "fingerprint": fingerprint})
            continue
        asset_id = f"asset-{fingerprint.removeprefix('asset-')}"
        cached = prompt_cache.get(fingerprint)
        if isinstance(cached, dict) and cached.get("prompt") and cached.get("negative"):
            result = cached
            cache_hits += 1
        else:
            result = build_asset_prompt(
                card, page,
                ratio=str((raw.get("asset_ratio") if isinstance(raw, dict) else None)
                          or brief.get("asset_ratio") or "16:9"),
                asset_function=page["asset_function"],
            )
            prompt_cache[fingerprint] = result
        entry = {
            "asset_id": asset_id,
            "slide_ids": [sid],
            "decision": "generate",
            "fingerprint": fingerprint,
            "asset_type": card["asset_type"],
            "asset_function": page["asset_function"],
            "safe_area": page["safe_area"],
            "prompt": result["prompt"],
            "negative": result["negative"],
            "meta": result["meta"],
            "expected_filename": f"{asset_id}.png",
            "retry_budget": 1,
            "qc_policy": {"text_safe_area": "blocking",
                          "negative_space_ratio": "blocking",
                          "subject_position": "blocking",
                          "brightness_balance": "advisory"},
        }
        by_fingerprint[fingerprint] = entry
        assets.append(entry)
        generated_count += 1
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        _json_write(cache_file, {"schema": "vao-asset-prompt-cache-v1",
                                 "entries": prompt_cache})
    return {
        "schema": "vao-assets-v1",
        "source_hash": (bundle.get("source_hash") or
                         (bundle.get("brief") or {}).get("source_hash")),
        "design_direction": plan.get("design_direction"),
        "quality_level": quality,
        "asset_budget": {"planned_route_calls": len(generation_ids),
                         "unique_generation_calls": generated_count,
                         "max_asset_calls": asset_cap},
        "assets": assets,
        "skipped_pages": skipped_pages,
        "performance": {"reference_context": "none", "batch": True,
                        "deduplicated": max(0, len(generation_ids) - generated_count),
                        "prompt_cache_hits": cache_hits,
                        "prompt_cache_path": str(cache_file) if cache_file else None},
    }


def _repair_packet(result: dict, mode: str, build: Path, output: Path) -> dict:
    """The only AI-facing context emitted by default: blockers grouped by cause."""
    return {
        "schema": "vao-repair-v1",
        "mode": mode,
        "build": str(build),
        "output": str(output),
        "verdict": result.get("verdict"),
        "status": result.get("status"),
        "blocking_items": result.get("blocking_items", 0),
        "failure_codes": result.get("failure_codes", []),
        "affected_slides": result.get("affected_slides", []),
        "fix_plan": result.get("fix_plan") or {"groups": []},
        # Warnings stay machine-readable but out of the conversation packet.
        "warning_summary": result.get("warn_summary", []),
        "next_action": result.get("next_action"),
        "performance": result.get("performance", {}),
    }


def _ghost(spec: dict, output_dir: str | Path, pages: list[int] | None = None,
           base_path: str | Path | None = None) -> dict:
    from ghost import ghost_deck, make_contact_sheet
    preview_spec = dict(spec)
    if base_path:
        preview_spec["_base_path"] = str(Path(base_path).resolve())
    paths = ghost_deck(preview_spec, output_dir, pages=pages, scale=0.5)
    contact = make_contact_sheet(paths, Path(output_dir) / "ghost-contact-sheet.png")
    return {"type": "ghost_layout_preview", "dir": str(Path(output_dir)),
            "pages": [str(p) for p in paths], "count": len(paths),
            "contact_sheet": str(contact) if contact else None,
            "renderer": "PIL", "supersampled": True,
            "evidence_scope": "direction_and_structure_not_pixel_proof"}


def asset_qc(manifest_path: str, input_dir: str | None = None,
             *, phase: str = "draft", output: str | None = None,
             json_output: bool = False) -> tuple[dict, int]:
    """QC generated assets once, with at most one draft retry recommendation."""
    from asset_prompt import image_qc, qc_retry_decision

    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    root = Path(input_dir).expanduser().resolve() if input_dir else manifest_file.parent
    results = []
    actions: dict[str, list[str]] = {}
    pending: list[str] = []        # 还没生成（先出图再 QC），与「生成不合格」分开报
    for entry in manifest.get("assets") or []:
        if entry.get("decision") != "generate":
            continue
        filename = entry.get("expected_filename") or f"{entry.get('asset_id')}.png"
        candidate = root / filename
        if not candidate.exists():
            stem = Path(filename).stem
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                alt = root / f"{stem}{ext}"
                if alt.exists():
                    candidate = alt
                    break
        if not candidate.exists() and entry.get("path"):
            candidate = Path(str(entry["path"])).expanduser()
        safe = entry.get("safe_area") or {}
        text_color = ((entry.get("meta") or {}).get("text_color")
                      or (entry.get("page") or {}).get("text_color"))
        qc = image_qc(str(candidate), safe_rect=safe,
                      text_is_dark=(True if text_color == "dark" else
                                    False if text_color == "light" else None))
        decision = qc_retry_decision(qc, attempt=int(entry.get("attempt", 0) or 0),
                                     phase=phase, max_retries=entry.get("retry_budget", 1))
        missing = (qc.get("status") == "error")   # 文件不存在 ≠ 图片不合格：修法不同
        item = {"asset_id": entry.get("asset_id"), "slide_ids": entry.get("slide_ids") or [],
                "file": str(candidate), "qc": qc, "policy": decision,
                "missing": missing}
        results.append(item)
        actions.setdefault(decision["action"], []).append(str(entry.get("asset_id")))
        if missing:
            pending.append(str(entry.get("asset_id")))
    report = {
        "schema": "vao-asset-qc-v1",
        "manifest": str(manifest_file),
        "phase": phase,
        "results": results,
        "summary": {k: len(v) for k, v in actions.items()},
        "retry_assets": actions.get("retry", []),
        "blocking_assets": [a for a in actions.get("block", []) + actions.get("flag", [])
                            if a not in pending],
        "pending_assets": pending,
        "conversation_policy": "only blocking assets become one grouped repair/retry action",
    }
    out_path = Path(output).expanduser() if output else manifest_file.with_name(
        manifest_file.stem + ".qc.json")
    _json_write(out_path, report)
    if json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        summary = ", ".join(f"{k}×{v}" for k, v in report["summary"].items()) or "no generated assets"
        print(f"VAO asset-qc: {summary}")
        if report["retry_assets"]:
            print("  retry-once: " + ", ".join(report["retry_assets"]))
        if report["blocking_assets"]:
            print("  blocking-group: " + ", ".join(report["blocking_assets"]))
        if report["pending_assets"]:
            print("  not-generated: " + ", ".join(report["pending_assets"])
                  + "（先生成图再 QC，这不是图片质量问题）")
        if not report["blocking_assets"] and not report["pending_assets"]:
            print("  ✓ 无资产阻断；advisory 不进入对话")
        print(f"  report: {out_path}")
    # 0 只代表「每个应生成的资产都被验证过且无阻断」；未生成 = 无法验证 = 不能当作通过。
    return report, 0 if not report["blocking_assets"] and not report["pending_assets"] else 2


def _ghost_cached(spec: dict, output_dir: str | Path, base: Path,
                  output_sha: str | None = None) -> dict:
    """方向预览证据：同一份 PPTX 只渲染一次（确定性产物 + 字节戳命中即复用）。

    预览是确定性几何投影：产物字节戳没变，重画一遍只是把同一张图再做一次。
    """
    target = Path(output_dir)
    marker = target / "ghost.meta.json"
    if output_sha and marker.exists():
        try:
            cached = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = {}
        sheet = cached.get("contact_sheet")
        if cached.get("output_sha256") == output_sha and sheet and Path(sheet).exists():
            info = dict(cached)
            info["reused"] = True
            return info
    info = _ghost(spec, output_dir, base_path=base)
    info["slide_ids"] = [str(s.get("id")) for s in (spec.get("slides") or [])
                         if isinstance(s, dict) and s.get("id")]
    info["output_sha256"] = output_sha
    info["reused"] = False
    _json_write(marker, info)
    return info


def run_check(build_path: str, output: str, *, mode: str = "draft",
              packet: str | None = None, preview: str | None = None,
              include_advisory: bool = False, json_output: bool = False,
              assets_manifest: str | None = None,
              assets_dir: str | None = None) -> tuple[dict, int]:
    """一次执行完成交付验证：normalize → guard → compile → 预览证据 → 修复包。

    零外部渲染器、零 reference 读取、零逐条修复循环：一个进程，一份结论。
    release 档自动产出 ghost 预览作为方向证据（结构判定的可视化凭证）。
    """
    from compile_cache import note_round
    from guard import normalize_spec
    from qa import release_manifest, run_qa

    spec, build = load_spec(build_path)
    asset_binding = None
    if assets_manifest:
        spec, asset_binding = bind_asset_manifest(spec, assets_manifest, assets_dir)
    normalized, norm = normalize_spec(spec)
    output_path = Path(output).expanduser()
    t0 = time.perf_counter()
    result = run_qa(normalized, output_path, mode=mode,
                    normalize=False,           # 边界处只归一化一次
                    include_advisory=include_advisory,
                    spec_path=str(build))
    if result.get("normalization") is None:
        result["normalization"] = norm
    result.setdefault("execution", {})["reference_context"] = "none"
    if asset_binding is not None:
        result["asset_binding"] = asset_binding
        result["execution"]["asset_manifest"] = asset_binding["manifest"]
        result["execution"]["asset_binding"] = asset_binding["status"]

    # 预览证据：release 自动出（方向与结构凭证），draft 只在显式要求时出。
    ghost = None
    preview_dir = preview or (str(output_path.with_name(output_path.stem + "_preview"))
                             if mode == "release" else None)
    if preview_dir:
        ghost = _ghost_cached(normalized, preview_dir, build.parent,
                              output_sha=(result.get("compile") or {}).get("output_sha256"))
        result["ghost_preview"] = ghost

    # 轮次账本：一轮 = 同一产物上 spec 变了的一次执行；复跑同 spec 不记新轮。
    ledger = note_round(output_path.with_name(output_path.stem + "_vao"),
                        mode=mode, spec_hash=result.get("source_spec_hash"),
                        status=result.get("status"), blocking=result.get("blocking_items"),
                        warnings=len(result.get("warn_summary") or []))
    result["rounds"] = ledger

    manifest_path = None
    if mode == "release":
        manifest = release_manifest(normalized, result, ghost_preview=ghost,
                                    revision_count=ledger.get("revisions", 0),
                                    revision_log=ledger.get("log"))
        manifest_path = output_path.with_suffix(".manifest.json")
        _json_write(manifest_path, manifest)
        result["manifest_path"] = str(manifest_path)

    result.setdefault("performance", {})["vao_total_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    packet_path = Path(packet).expanduser() if packet else output_path.with_suffix(".repair.json")
    packet_value = _repair_packet(result, mode, build, output_path)
    _json_write(packet_path, packet_value)
    if json_output:
        print(json.dumps(packet_value, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"VAO {mode}: {result.get('verdict', {}).get('verdict')} · {result.get('status')} · "
              f"{result.get('performance', {}).get('total_ms', 0)}ms · "
              f"round {ledger.get('n')}/{ledger.get('budget')}")
        for group in (result.get("fix_plan") or {}).get("groups") or []:
            ids = "、".join(group.get("ids") or []) or "deck"
            print(f"  fix[{group.get('root_cause')}] ×{group.get('count', 0)} ({ids}) "
                  f"→ {group.get('fix', '')}")
        if asset_binding and (asset_binding.get("missing_asset_ids") or asset_binding.get("missing_files")):
            ids = asset_binding.get("missing_asset_ids") or []
            files = asset_binding.get("missing_files") or []
            print("  fix[asset-binding] ×{} → 补齐 manifest 引用或重新生成资产: {}".format(
                len(ids) + len(files), "、".join(ids + files)))
        if not (result.get("fix_plan") or {}).get("groups"):
            print("  ✓ 无阻断：warning 只留痕，不进入对话")
        if ghost:
            suffix = "（同产物复用，未重渲）" if ghost.get("reused") else ""
            print(f"  preview: {ghost['count']} 页 ghost → "
                  f"{ghost['contact_sheet'] or ghost['dir']}{suffix}")
        if manifest_path:
            print(f"  manifest: {manifest_path}")
        print(f"  repair packet: {packet_path}")
    binding_block = bool(asset_binding and (asset_binding.get("missing_asset_ids")
                                             or asset_binding.get("missing_files")))
    return result, (0 if result.get("passed") and not binding_block else 2)


def run_once(args: argparse.Namespace) -> int:
    """plan + optional check in one process, avoiding script-by-script startup."""
    bundle = _plan(args.brief, args.plan_out, None if args.build else args.skeleton)
    build = args.build
    if getattr(args, "assets_out", None):
        from intent_compiler import _load_need
        need = _load_need(args.brief)
        manifest = build_asset_manifest(need, bundle=bundle,
                                        cache_path=getattr(args, "asset_cache", None))
        _json_write(args.assets_out, manifest)
        print(f"assets complete · unique_calls={manifest['asset_budget']['unique_generation_calls']} "
              f"· manifest={args.assets_out}")
    if not build:
        if not args.skeleton:
            print(json.dumps({"plan": bundle, "next": "填充 --skeleton 后再执行 vao.py check"},
                             ensure_ascii=False, indent=2))
        else:
            print(f"plan complete · skeleton: {args.skeleton} · "
                  "填充 TODO 后执行 vao.py check build.py deck.pptx")
        return 0
    manifest_for_check = getattr(args, "assets_manifest", None) or getattr(args, "assets_out", None)
    _, code = run_check(build, args.output, mode=args.mode, packet=args.packet,
                        preview=args.preview, include_advisory=args.advisory,
                        json_output=args.json, assets_manifest=manifest_for_check,
                        assets_dir=getattr(args, "assets_dir", None))
    return code


def doctor() -> int:
    """Fast environment check; the only required external capability is Python packages."""
    checks = {}
    for name in ("pptx", "PIL", "yaml"):
        try:
            __import__(name)
            checks[name] = True
        except Exception:
            checks[name] = False
    checks.update({"external_renderer_policy": "disabled",
                   "references_loaded": False})
    ok = all(checks[k] for k in ("pptx", "PIL", "yaml"))
    print(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if ok else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vao.py", description="PPT Visual Art Director OS · one fast entry point")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="brief → plan.json / build skeleton")
    p.add_argument("brief")
    p.add_argument("--out", dest="plan_out")
    p.add_argument("--skeleton")
    p.add_argument("--json", action="store_true", help="print the compact plan")

    a = sub.add_parser("assets", help="brief → deduplicated batch asset manifest")
    a.add_argument("brief")
    a.add_argument("--plan", dest="plan_path", help="reuse an existing plan.json")
    a.add_argument("--out", default="asset_manifest.json")
    a.add_argument("--cache", help="prompt cache JSON; reuse identical visual-demand fingerprints")
    a.add_argument("--json", action="store_true")

    aq = sub.add_parser("asset-qc", help="generated asset folder → grouped QC report")
    aq.add_argument("manifest")
    aq.add_argument("--input", help="directory containing asset_id.png files")
    aq.add_argument("--phase", choices=("draft", "release"), default="draft")
    aq.add_argument("--out")
    aq.add_argument("--json", action="store_true")

    c = sub.add_parser("check", help="build.py → normalize/guard/compile/preview → packet")
    c.add_argument("build")
    c.add_argument("output", nargs="?", default="deck.pptx")
    c.add_argument("--mode", choices=("spec", "draft", "release"), default="draft")
    c.add_argument("--packet")
    c.add_argument("--preview", help="write ghost preview PNGs here (release writes them by default)")
    c.add_argument("--assets-manifest", help="bind image elements carrying asset_id")
    c.add_argument("--assets-dir", help="directory containing generated manifest filenames")
    c.add_argument("--advisory", action="store_true", help="explicit risk forecast; off by default")
    c.add_argument("--json", action="store_true")

    r = sub.add_parser("run", help="brief + build + check in one process")
    r.add_argument("brief")
    r.add_argument("--build")
    r.add_argument("--skeleton", default="build_vao.py")
    r.add_argument("--plan-out", default="plan.json")
    r.add_argument("--output", default="deck.pptx")
    r.add_argument("--assets-out", help="also emit deduplicated asset_manifest.json in this run")
    r.add_argument("--asset-cache", help="prompt cache JSON for --assets-out")
    r.add_argument("--assets-manifest", help="bind an existing asset manifest during check")
    r.add_argument("--assets-dir", help="directory containing generated manifest filenames")
    r.add_argument("--mode", choices=("spec", "draft", "release"), default="draft")
    r.add_argument("--packet")
    r.add_argument("--preview")
    r.add_argument("--advisory", action="store_true")
    r.add_argument("--json", action="store_true")

    v = sub.add_parser("preview", help="spec/build → ghost contact sheet (PIL only)")
    v.add_argument("build")
    v.add_argument("--out", default="vao_preview")
    v.add_argument("--pages", help="1-based pages, e.g. 1,3,8")
    v.add_argument("--assets-manifest", help="bind image elements carrying asset_id")
    v.add_argument("--assets-dir", help="directory containing generated manifest filenames")

    d = sub.add_parser("dna", help="design memory: --check store / --add one entry")
    d.add_argument("--add", help="append one DNA entry from a JSON file")
    d.add_argument("--replace", action="store_true", help="with --add: overwrite same-id entry")
    d.add_argument("--check", action="store_true", help="validate the store (default action)")
    d.add_argument("--json", action="store_true")

    sub.add_parser("doctor", help="check Python dependencies and policy state")
    return parser


def _dna(args) -> int:
    """经验记忆的入口：体检 / 追加一条。

    记忆写坏了不会报错，只会永远命不中——所以写入必须经过校验，且入口只有这一个。
    """
    from design_intelligence import DNA_STORE, record_dna, validate_dna_store
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
            for w in result.get("warnings") or []:
                print(f"  - {w}")
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "assets":
            from intent_compiler import _load_need
            need = _load_need(args.brief)
            if args.plan_path:
                bundle = json.loads(Path(args.plan_path).expanduser().read_text(encoding="utf-8"))
            else:
                from pipeline import build_plan_bundle
                bundle = build_plan_bundle(need)
            manifest = build_asset_manifest(need, bundle=bundle, cache_path=args.cache)
            _json_write(args.out, manifest)
            if args.json:
                print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"assets complete · unique_calls={manifest['asset_budget']['unique_generation_calls']} "
                      f"· manifest={args.out}")
            return 0
        if args.command == "asset-qc":
            _, code = asset_qc(args.manifest, args.input, phase=args.phase,
                               output=args.out, json_output=args.json)
            return code
        if args.command == "dna":
            return _dna(args)
        if args.command == "plan":
            bundle = _plan(args.brief, args.plan_out, args.skeleton)
            if args.json or not (args.plan_out or args.skeleton):
                print(json.dumps(bundle, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"plan complete · route_calls=1 · {bundle['performance']['planning_ms']}ms")
            return 0
        if args.command == "check":
            _, code = run_check(args.build, args.output, mode=args.mode,
                                packet=args.packet, preview=args.preview,
                                include_advisory=args.advisory, json_output=args.json,
                                assets_manifest=args.assets_manifest,
                                assets_dir=args.assets_dir)
            return code
        if args.command == "run":
            return run_once(args)
        if args.command == "preview":
            spec, _ = load_spec(args.build)
            binding = None
            if args.assets_manifest:
                spec, binding = bind_asset_manifest(spec, args.assets_manifest, args.assets_dir)
            pages = ([int(x) for x in args.pages.split(",") if x.strip()]
                     if args.pages else None)
            info = _ghost(spec, args.out, pages, base_path=Path(args.build).expanduser().resolve().parent)
            if binding:
                info["asset_binding"] = binding
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 2 if binding and binding["status"] == "BLOCK" else 0
        return doctor()
    except ModuleNotFoundError as exc:
        print(f"VAO error: missing Python dependency {exc.name!r}; "
              "install requirements.txt", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"VAO error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
