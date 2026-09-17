#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VAO · single entry point for the Visual Art Director OS.

The repository keeps its internal modules separated for maintainability, but
production callers only need this file.  It deliberately does not read the
reference library, start a renderer, or turn warnings into an interactive
loop.  One invocation performs one deterministic batch:

    plan:      brief -> compact plan -> optional skeleton
    assets:    brief + plan -> deduplicated batch asset manifest
    asset-qc:  generated images -> one grouped QC report
    check:     normalize -> guard -> compile -> grouped repair packet
    run:       plan + check in one Python process
    preview:   spec -> ghost contact sheet (PIL only)

The AI/author fills the skeleton once.  If check fails, the packet contains
root-cause groups rather than a line-by-line stream.  After one grouped repair,
run the same command again; a clean draft goes directly to release.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_module(path: str | Path, name: str = "vao_build"):
    """Load a user build module exactly once, with stable relative imports."""
    source = Path(path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    spec = importlib.util.spec_from_file_location(name, str(source))
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载模块: {source}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
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
    if out:
        _json_write(out, bundle)
    if skeleton:
        target = Path(skeleton).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(build_skeleton_module(bundle), encoding="utf-8")
    return bundle


def _asset_page(brief: dict, page_plan: dict, raw_slide: Any, *, asset_id: str) -> tuple[dict, dict]:
    """brief + one route page → compact asset card + geometric page contract."""
    from asset_prompt import enhance_asset_card, normalize_safe_area

    raw = raw_slide if isinstance(raw_slide, dict) else {"content": str(raw_slide)}
    derived = page_plan.get("derived") or {}
    asset = page_plan.get("asset") or {}
    function = str(raw.get("asset_function") or asset.get("function") or "frame")
    anchor = str(raw.get("negative_space_anchor") or {
        "hero": "left", "emotion": "left", "context": "left",
        "proof": "right", "direct": "right"
    }.get(function, "left")).lower()
    safe_area = normalize_safe_area(raw.get("safe_area"), anchor)
    title = str(raw.get("title") or raw.get("content") or raw.get("text") or "visual context")
    subject = raw.get("asset_subject") or title[:180]
    direction = str(brief.get("design_direction") or "quiet editorial")
    visual_world = str(brief.get("visual_world") or brief.get("style_hint") or "")
    style = [direction]
    if visual_world:
        style.append(visual_world[:120])
    theme_colors = ((page_plan.get("theme_seed") or {}).get("colors")
                    if isinstance(page_plan.get("theme_seed"), dict) else {}) or {}
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
    reused_ids = set((plan.get("assets") or {}).get("reuse") or [])
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
    for i, page_plan in enumerate(route_pages):
        sid = str(page_plan.get("id") or f"s{i + 1:02d}")
        decision = str((page_plan.get("asset") or {}).get("decision") or "none")
        if decision == "none":
            skipped_pages.append({"slide_id": sid, "decision": "skip",
                                  "reason": "page family reserves attention for data/text"})
            continue
        raw = raw_slides[i] if i < len(raw_slides) else {}
        provisional = f"asset-{sid}"
        card, page = _asset_page(brief, page_plan, raw, asset_id=provisional)
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
            "renderer": "PIL", "supersampled": True, "not_pixel_proof": True}


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
        item = {"asset_id": entry.get("asset_id"), "slide_ids": entry.get("slide_ids") or [],
                "file": str(candidate), "qc": qc, "policy": decision}
        results.append(item)
        actions.setdefault(decision["action"], []).append(str(entry.get("asset_id")))
    report = {
        "schema": "vao-asset-qc-v1",
        "manifest": str(manifest_file),
        "phase": phase,
        "results": results,
        "summary": {k: len(v) for k, v in actions.items()},
        "retry_assets": actions.get("retry", []),
        "blocking_assets": actions.get("block", []) + actions.get("flag", []),
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
        else:
            print("  ✓ 无资产阻断；advisory 不进入对话")
        print(f"  report: {out_path}")
    return report, 0 if not report["blocking_assets"] else 2


def run_check(build_path: str, output: str, *, mode: str = "draft", 
              packet: str | None = None, preview: str | None = None,
              include_advisory: bool = False, json_output: bool = False,
              assets_manifest: str | None = None,
              assets_dir: str | None = None) -> tuple[dict, int]:
    """Run the complete static production path once; never invokes LibreOffice."""
    from guard import normalize_spec
    from qa import release_manifest, run_qa

    spec, build = load_spec(build_path)
    asset_binding = None
    if assets_manifest:
        spec, asset_binding = bind_asset_manifest(spec, assets_manifest, assets_dir)
    normalized, norm = normalize_spec(spec)
    output_path = Path(output).expanduser()
    t0 = time.perf_counter()
    result = run_qa(
        normalized, output_path,
        mode=mode,
        normalize=False,               # normalize exactly once at this boundary
        render=False,
        visual="native",               # PPTX + structural evidence, no external renderer
        include_advisory=include_advisory,
        spec_path=str(build),
    )
    if result.get("normalization") is None:
        result["normalization"] = norm
    result.setdefault("execution", {})["entrypoint"] = "vao.py"
    result["execution"]["reference_context"] = "none"
    result["execution"]["external_renderer"] = "disabled"
    result["execution"]["visual_evidence"] = "native"
    if asset_binding is not None:
        result["asset_binding"] = asset_binding
        result["execution"]["asset_manifest"] = asset_binding["manifest"]
        result["execution"]["asset_binding"] = asset_binding["status"]
    result.setdefault("performance", {})["vao_total_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    manifest_path = None
    if mode == "release":
        manifest = release_manifest(normalized, result)
        manifest_path = output_path.with_suffix(".manifest.json")
        _json_write(manifest_path, manifest)
        result["manifest_path"] = str(manifest_path)

    ghost = None
    if preview:
        ghost = _ghost(normalized, preview, base_path=build.parent)
        result["ghost_preview"] = ghost
    packet_path = Path(packet).expanduser() if packet else output_path.with_suffix(".repair.json")
    packet_value = _repair_packet(result, mode, build, output_path)
    _json_write(packet_path, packet_value)

    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        verdict = result.get("verdict") or {}
        print(f"VAO {mode}: {verdict.get('verdict', result.get('status'))} · "
              f"{result.get('status')} · {result.get('performance', {}).get('total_ms', '?')}ms")
        groups = (result.get("fix_plan") or {}).get("groups") or []
        if asset_binding and (asset_binding.get("missing_asset_ids") or asset_binding.get("missing_files")):
            ids = asset_binding.get("missing_asset_ids") or []
            files = asset_binding.get("missing_files") or []
            print("  fix[asset-binding] ×{} → 补齐 manifest 引用或重新生成资产: {}".format(
                len(ids) + len(files), "、".join(ids + files)))
        if groups:
            for group in groups:
                ids = "、".join(group.get("ids") or []) or "deck"
                print(f"  fix[{group.get('root_cause')}] ×{group.get('count', 0)} "
                      f"({ids}) → {group.get('fix', '')}")
        else:
            print("  ✓ 无阻断：不再进入 warning 修复对话，可直接 release")
        if ghost:
            print(f"  preview: {ghost['count']} 页 ghost → {ghost['dir']}")
            if ghost.get("contact_sheet"):
                print(f"  contact sheet: {ghost['contact_sheet']}")
        if manifest_path:
            print(f"  manifest: {manifest_path}")
        print(f"  repair packet: {packet_path}  (只含根因组，不含 reference 全文)")
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
    checks.update({"libreoffice": False, "external_renderer_policy": "disabled",
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
    aq.add_argument("--phase", choices=("draft", "review", "release"), default="draft")
    aq.add_argument("--out")
    aq.add_argument("--json", action="store_true")

    c = sub.add_parser("check", help="build.py → normalize → guard → compile → packet")
    c.add_argument("build")
    c.add_argument("output", nargs="?", default="deck.pptx")
    c.add_argument("--mode", choices=("sketch", "spec", "draft", "review", "release"), default="draft")
    c.add_argument("--packet")
    c.add_argument("--preview", help="write fast ghost PNGs to this directory")
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
    r.add_argument("--mode", choices=("sketch", "spec", "draft", "review", "release"), default="draft")
    r.add_argument("--packet")
    r.add_argument("--preview")
    r.add_argument("--advisory", action="store_true")
    r.add_argument("--json", action="store_true")

    v = sub.add_parser("preview", help="spec/build → ghost contact sheet; no PPTX render")
    v.add_argument("build")
    v.add_argument("--out", default="vao_preview")
    v.add_argument("--pages", help="1-based pages, e.g. 1,3,8")
    v.add_argument("--assets-manifest", help="bind image elements carrying asset_id")
    v.add_argument("--assets-dir", help="directory containing generated manifest filenames")

    sub.add_parser("doctor", help="check Python dependencies; LibreOffice is never required")
    return parser


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
              "install requirements.txt (no LibreOffice needed)", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"VAO error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
