#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VAO · single entry point for the Visual Art Director OS.

Internal modules exist for maintainability; production callers only need this
file.  It never reads the reference library, never starts an external renderer,
and never turns a warning into a conversation.  One invocation = one
deterministic batch:

    plan:      brief -> compact plan -> optional skeleton
    assets:    brief + plan -> deduplicated batch asset manifest
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
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"build 文件不是 UTF-8 文本：{source}（{exc.reason}）"
            "——请另存为 UTF-8，或改用 .json / .yml 传 spec") from None
    try:
        code = compile(text, str(source), "exec")
    except SyntaxError as exc:
        # 语法错误直接给「文件:行:列 + 那一行」，比抛裸 SyntaxError 少一次往返。
        raise ValueError(
            f"build 文件语法错误：{source}:{exc.lineno}:{exc.offset or 0} — {exc.msg}"
            + (f"\n  {exc.text.rstrip()}" if exc.text else "")) from None
    mod = types.ModuleType(name)
    mod.__file__ = str(source)
    mod.__dict__["__name__"] = name
    # builtins 必须取模块对象，不能直接抄 `__builtins__`：后者在 __main__ 里是
    # 模块、被 import 时却是 dict，两种形态都能跑但语义不同（dict 形态下
    # build 文件里的 `__builtins__` 会看到一份快照）。显式取同一个模块，
    # 让「python vao.py」与「import vao」两条路径行为完全一致。
    import builtins
    mod.__dict__["__builtins__"] = builtins
    exec(code, mod.__dict__)
    sys.modules.setdefault(name, mod)
    return mod, source


def load_spec(path: str | Path) -> tuple[dict, Path]:
    """Read a build.py, JSON, or YAML spec without loading references."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(
            f"找不到 spec 文件: {source}"
            "（先 `vao.py plan brief.yml --out plan.json --skeleton build.py` 生成骨架，填充后再 check）")
    if source.suffix.lower() in {".json", ".yml", ".yaml"}:
        text = source.read_text(encoding="utf-8")
        # 解析失败要带上「哪个文件、第几行」：顶层只打印异常类型时，
        # 作者拿到的是一句 ScannerError，还得自己回去数行。
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
                problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
                raise ValueError(f"spec YAML 解析失败：{source}{where} — {problem}") from None
        if not isinstance(value, dict):
            raise ValueError(f"spec 顶层必须是对象/dict，实际是 {type(value).__name__}：{source}")
        return value, source
    if source.suffix.lower() != ".py":
        raise ValueError("编排文件只接受 JSON/YAML，或作者明确指定的可信 .py 文件")
    mod, source = _load_module(source)
    if hasattr(mod, "build_spec"):
        try:
            value = mod.build_spec()
        except Exception as exc:
            # build_spec() 自己炸了要说清是**它**炸了，而不是报成「模块没定义 spec」。
            raise ValueError(f"build_spec() 执行失败：{source} — "
                             f"{type(exc).__name__}: {exc}") from None
    else:
        value = getattr(mod, "SPEC", None)
    if value is None:
        raise ValueError(f"build 模块既没有 build_spec()、也没有顶层 SPEC：{source}"
                         "（骨架默认给的是 SPEC = {...}，别改名）")
    if not isinstance(value, dict):
        raise ValueError(f"spec 顶层必须是对象/dict，实际是 {type(value).__name__}：{source}")
    if not isinstance(value.get("slides"), list):
        # slides 缺失/写错类型会一路走到「0 页 deck」，那是空文件不是轻量交付。
        raise ValueError(f"spec.slides 必须是数组/list，实际是 "
                         f"{type(value.get('slides')).__name__}：{source}")
    return value, source


def _json_write(path: str | Path, value: Any) -> Path:
    from primitives import json_write   # 原子写入唯一实现住 primitives
    return json_write(path, value)


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
    from asset_workflow import asset_entries, asset_root, resolve_asset
    by_id = {str(item["asset_id"]): item for item in asset_entries(payload)}
    root = asset_root(payload, manifest_file, assets_dir)
    bound: list[dict] = []
    missing: list[str] = []
    missing_files: list[str] = []
    result = copy.deepcopy(spec)

    def walk(value: Any) -> None:
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
    report = {"manifest": str(manifest_file), "assets_dir": str(root), "bound": bound,
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
    from asset_workflow import digest, now, file_digest
    bundle["workflow"] = {"schema": "vao-plan-chain-v1", "planned_at": now(),
                          "brief_path": str(Path(brief_path).resolve()),
                          "brief_sha256": digest(need),
                          "brief_file_sha256": file_digest(Path(brief_path).expanduser()),
                          "plan_path": str(Path(out).expanduser().resolve()) if out else None}
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
    from asset_prompt import (enhance_asset_card, grammar_phrase,
                              hex_to_color_name, normalize_safe_area,
                              resolve_asset_role)

    raw = raw_slide if isinstance(raw_slide, dict) else {"content": str(raw_slide)}
    deck = deck or {}
    derived = deck.get("direction_execution") or {}
    asset = page_plan.get("asset") or {}
    # 角色先于用途解析：asset_role（是什么）→ 执行类型 asset_type，一步到位。
    # 未声明不猜（默认 background + 来源 assumed）；未知值 fail-closed，不静默忽略。
    asset_role, asset_role_source = resolve_asset_role(raw.get("asset_role"),
                                                       raw.get("asset_type"))
    function = str(raw.get("asset_function") or asset.get("function") or "frame")
    anchor = str(raw.get("negative_space_anchor") or {
        "hero": "left", "emotion": "left", "context": "left",
        "proof": "right", "direct": "right"
    }.get(function, "left")).lower()
    safe_area = normalize_safe_area(raw.get("safe_area"), anchor)
    title = str(raw.get("title") or raw.get("content") or raw.get("text") or "visual context")
    subject = raw.get("asset_subject")
    subject_fallback = not subject
    if not subject:
        subject = title[:180]
    # 方向族名（song_elegance / zen_minimal / luxury_editorial …）是
    # FAMILY_TEXTURE / FAMILY_MOTION 的键；页面家族名（cover / data_story）
    # 在那两张表里从来命不中，静默落进 ("luxury",) 兜底。取 deck 的 canonical 值。
    direction_family = str(deck.get("design_direction") or "").strip().lower()
    visual_world = str(brief.get("visual_world") or "")
    if visual_world.lower() == "unknown":
        visual_world = ""
    # 色值从**整副 deck 的主题**取（品牌优先派生过的那一份），不取方向预设的原始种子：
    # 素材必须跟着这份交付的色板走，而不是跟着方向标签走。
    deck_theme = deck.get("theme") if isinstance(deck.get("theme"), dict) else {}
    theme_colors = dict(deck_theme.get("colors") or {})
    color_cue = list(raw.get("asset_color") or [])
    if not color_cue:
        color_cue = ["neutral tonal range with one restrained accent"]
        if theme_colors.get("accent"):
            # 图像模型对 #hex 基本不响应，颜色名才是可执行语言；hex 保留在括号里供人核对。
            accent_hex = str(theme_colors["accent"])
            accent_name = hex_to_color_name(accent_hex)
            color_cue.append(f"accent color {accent_name} ({accent_hex})" if accent_name
                             else f"accent color {accent_hex}")
    card = {
        "apc": f"APC-{str(asset_id).upper().replace('-', '_')}",
        # asset_type 只有一个来源：角色解析结果（asset_role 声明 > 旧 asset_type 直写
        # > assumed background）。二者不再各存一份——那会出现「声明了却仍是 background」
        # 的裂缝：提示词按背景纪律写，作者以为自己在出插图。
        "asset_type": asset_role,
        "asset_role": asset_role,
        "asset_role_source": asset_role_source,
        "medium": raw.get("medium") or brief.get("asset_medium"),
        "family": direction_family or str(page_plan.get("page_family") or "").lower(),
        "subject": [subject],
        "subject_source": "title_fallback" if subject_fallback else "declared",
        "color": color_cue,
        "material": [str(raw.get("material") or derived.get("material") or "quiet matte surface")],
        # 材质/光照的来源决定它们能不能替这张资产宣告介质：逐页显式写的算数，
        # 方向默认值是**整副 deck 的质感语言**（"rice paper, ink stone…"），
        # 一份宋韵里每张照片都拍在纸台上，不代表每张照片都是水墨画。
        "material_source": ("declared" if raw.get("material")
                            else "direction" if derived.get("material") else "fallback"),
        "lighting": [str(raw.get("lighting") or derived.get("light") or "single soft directional light")],
        "lighting_source": ("declared" if raw.get("lighting")
                            else "direction" if derived.get("light") else "fallback"),
        # 构图语法：内部键名（evidence_field …）由 grammar_phrase 翻译成可读语言，
        # 自由文本原样保留——裸键名对图像模型是纯噪声，还污染资产指纹。
        "composition": [grammar_phrase(derived.get("composition_grammar"))],
        "motion": [str(derived.get("motion"))] if derived.get("motion") else [],
        # deck 级视觉世界进提示词当氛围语言，但**不参与介质闸门扫描**：
        # 它描述整副 deck 的材质与光，不该替单张资产决定「这张是画还是照片」。
        # 放进独立的 world 段（曾是 style 的一员，于是写一次「宣纸」就把水墨纪律
        # 灌进了每一张摄影页）。
        "world": [visual_world[:160]] if visual_world else [],
        "asset_function": function,
        "fusion_enabled": raw.get("fusion_enabled"),
        # 逐页 negative 在前，deck 级 avoid 在后：brief 的「明确不做的几件事」
        # 对每张图都成立，否则它只是模板里一句没人消费的装饰。
        "negative": list(raw.get("negative") or []) + list(brief.get("avoid") or []),
    }
    # Directional defaults are weak descriptors; explicit brief/card language wins.
    # 逐页显式写下的 material/lighting/texture/asset_color 永远压过方向默认值；
    # 方向族带来的 texture_keys 是键名，由 enhance_asset_card 统一展开。
    card = enhance_asset_card(card, family=card["family"],
                              motion=card["motion"] or None,
                              texture=raw.get("texture") or derived.get("texture_keys"),
                              fusion=card["fusion_enabled"] is not False)
    page = {
        "negative_space_anchor": anchor,
        "safe_area": safe_area,
        "text_color": raw.get("text_color") or raw.get("safe_area_text_color"),
        "light_direction": raw.get("light_direction") or "left",
        "energy": raw.get("energy") or page_plan.get("energy") or "low",
        "asset_function": function,
        "ratio": str(raw.get("asset_ratio") or brief.get("asset_ratio") or "16:9"),
    }
    return card, page


def build_asset_manifest(brief: dict, bundle: dict | None = None,
                         cache_path: str | Path | None = None) -> dict:
    """Build one deduplicated, batch-ready asset manifest from a brief.

    This is the only place where route decisions become image-generation work.
    asset_prompt remains a pure translator; no reference files are read here.
    """
    from asset_prompt import asset_fingerprint, build_asset_prompt, qc_policy
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
        raw = raw_pairs[i][1] if i < len(raw_pairs) else {}
        origin = raw.get("asset_source") if isinstance(raw, dict) else None
        if origin:
            from asset_workflow import digest
            if not isinstance(origin, dict) or origin.get("kind") not in {"provided", "licensed", "original", "reuse"} or not origin.get("path") or not origin.get("source"):
                raise ValueError("asset_source 需要 kind(provided/licensed/original/reuse)、path、source")
            origin = dict(origin)
            op = Path(origin["path"]).expanduser()
            base = Path((bundle.get("workflow") or {}).get("brief_path") or ".").resolve().parent
            origin["path"] = str(op.resolve() if op.is_absolute() else (base / op).resolve())
            aid = "existing-" + digest(origin)[:16]
            previous = next((e for e in assets if e.get("asset_id") == aid), None)
            if previous:
                previous["slide_ids"].append(sid)
            else:
                from asset_prompt import normalize_safe_area
                assets.append({"asset_id": aid, "slide_ids": [sid], "decision": "existing",
                               "origin": origin, "asset_function": raw.get("asset_function", "context"),
                               # 既有素材不生成，故不解析角色；作者写了就原样留痕（不解释、不补齐）
                               "asset_role": str(raw.get("asset_role") or "").strip().lower() or None,
                               "asset_role_source": ("declared" if raw.get("asset_role") else None),
                               "safe_area": normalize_safe_area(raw.get("safe_area"), raw.get("negative_space_anchor", "left")),
                               "meta": {"text_color": raw.get("text_color")}, "retry_budget": 0,
                               "background_color": ((plan.get("theme") or {}).get("colors") or {}).get("background", "#FFFFFF")})
            continue
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
            "asset_role": card["asset_role"],
            "asset_role_source": card["asset_role_source"],
            "asset_function": page["asset_function"],
            "ratio": page["ratio"],
            "allow_crop": raw.get("asset_allow_crop") is True,
            "background_color": ((plan.get("theme") or {}).get("colors") or {}).get("background", "#FFFFFF"),
            "safe_area": page["safe_area"],
            "prompt": result["prompt"],
            "negative": result["negative"],
            "meta": result["meta"],
            "expected_filename": f"{asset_id}.png",
            "retry_budget": 1,
            "qc_policy": qc_policy(),
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
    packet = {
        "schema": "vao-repair-v1",
        "run_id": result.get("run_id"),
        "mode": mode,
        "build": str(build),
        "output": str(output),
        "verdict": result.get("verdict"),
        "status": result.get("status"),
        "blocking_items": result.get("blocking_items", 0),
        "failure_codes": result.get("failure_codes", []),
        "affected_slides": result.get("affected_slides", []),
        "fix_plan": result.get("fix_plan") or {"groups": []},
        # Trace stays machine-readable but out of the conversation packet (Evidence ≠ Error).
        "trace_summary": result.get("trace_summary", []),
        "asset_workflow": result.get("asset_workflow"),
        "release_eligible": result.get("release_eligible", False),
        "next_action": result.get("next_action"),
        "performance": result.get("performance", {}),
    }
    return packet


def _ghost(spec: dict, output_dir: str | Path, pages: list[int] | None = None,
           base_path: str | Path | None = None, image_bytes: dict | None = None) -> dict:
    from ghost import ghost_deck, make_contact_sheet
    preview_spec = dict(spec)
    preview_spec["_image_bytes"] = image_bytes or {}
    if base_path:
        preview_spec["_base_path"] = str(Path(base_path).resolve())
    paths = ghost_deck(preview_spec, output_dir, pages=pages, scale=0.5)
    contact = make_contact_sheet(paths, Path(output_dir) / "ghost-contact-sheet.png")
    return {"type": "ghost_layout_preview", "dir": str(Path(output_dir)),
            "pages": [str(p) for p in paths], "count": len(paths),
            "contact_sheet": str(contact) if contact else None,
            "renderer": "PIL", "supersampled": True,
            "evidence_scope": "direction_and_structure_not_pixel_proof"}


def _asset_qc_report(manifest_path: str, input_dir: str | None = None,
                     *, phase: str = "draft",
                     output: str | None = None) -> tuple[dict, int]:
    """资产核验：一次判定，一条修法（draft 最多一次定向重出）。

    这是 `check` 内部的一步，不是独立入口——绑定、核验、结论必须在同一次
    执行里发生，否则分步执行会漂移（v5.7：asset-qc 与 check 合并）。
    """
    from asset_prompt import ROLE_AUTHORITATIVE_SOURCES, image_qc, qc_retry_decision

    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    import hashlib
    from asset_workflow import (ACCEPTED, asset_entries, digest,
                                now, resolve_asset, verify_sources)
    workflow_issues = verify_sources(manifest)
    results = []
    actions: dict[str, list[str]] = {}
    pending: list[str] = []        # 还没生成（先出图再 QC），与「生成不合格」分开报
    for entry in asset_entries(manifest):
        candidate = resolve_asset(entry, manifest, manifest_file, input_dir)
        blob = candidate.read_bytes() if candidate.is_file() else None
        image_sha = hashlib.sha256(blob).hexdigest() if blob is not None else None
        if entry["decision"] == "generate" and image_sha and image_sha == entry.get("preexisting_sha256"):
            workflow_issues.append(f"{entry['asset_id']}: 清单前已有同一图片；须显式标记 existing/reuse")
        if entry["decision"] == "generate" and (not entry.get("prompt") or not entry.get("negative")):
            workflow_issues.append(f"{entry['asset_id']}: 缺少 prompt / negative")
        if entry["decision"] == "existing":
            origin = entry.get("origin") or {}
            if origin.get("kind") not in {"provided", "licensed", "original", "reuse"} or not origin.get("source"):
                workflow_issues.append(f"{entry['asset_id']}: 既有素材缺少合法 kind / source 声明")
        safe = entry.get("safe_area") or {}
        text_color = ((entry.get("meta") or {}).get("text_color")
                      or (entry.get("page") or {}).get("text_color"))
        qc = image_qc(str(candidate), safe_rect=safe,
                      text_is_dark=(True if text_color == "dark" else
                                    False if text_color == "light" else None),
                      image_bytes=blob, expected_ratio=entry.get("ratio"),
                      allow_crop=entry.get("allow_crop") is True,
                      background=entry.get("background_color") or "#FFFFFF")
        # 角色只有「作者说过的话」才对 QC 有发言权（declared / legacy）；
        # assumed 角色不得悄悄放宽或收紧任何一条判据。
        role_authority = (entry.get("asset_role")
                          if entry.get("asset_role_source") in ROLE_AUTHORITATIVE_SOURCES
                          else None)
        decision = qc_retry_decision(qc, attempt=int(entry.get("attempt", 0) or 0),
                                     phase=phase, max_retries=entry.get("retry_budget", 1),
                                     asset_function=entry.get("asset_function"),
                                     asset_role=role_authority)
        missing = (qc.get("status") == "error")   # 文件不存在 ≠ 图片不合格：修法不同
        item = {"asset_id": entry.get("asset_id"), "slide_ids": entry.get("slide_ids") or [],
                "file": str(candidate), "file_sha256": image_sha, "qc": qc, "policy": decision,
                "missing": missing}
        results.append(item)
        actions.setdefault(decision["action"], []).append(str(entry.get("asset_id")))
        if missing:
            pending.append(str(entry.get("asset_id")))
    report = {
        "schema": "vao-asset-qc-v3",
        "manifest": str(manifest_file),
        "manifest_sha256": digest(manifest), "checked_at": now(),
        "workflow_issues": workflow_issues,
        "status": "PASS" if not workflow_issues and all(
            (r.get("policy") or {}).get("action") in ACCEPTED for r in results) else "BLOCKED",
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
    report["report_path"] = str(out_path)
    _json_write(out_path, report)
    # 静默：一次执行只输出一条结论（check 打印）。0 只代表「每个应生成的资产都被
    # 验证过且无阻断」；未生成 = 无法验证 = 不能当作通过。
    return report, 0 if report["status"] == "PASS" else 2


def _ghost_engine_stamp() -> str | None:
    """渲染器指纹：预览复用必须同时命中产物字节戳与渲染器版本。"""
    from compile_cache import _file_sha
    return _file_sha(Path(__file__).resolve().parent / "ghost.py")


def _ghost_cached(spec: dict, output_dir: str | Path, base: Path,
                  output_sha: str | None = None, image_bytes: dict | None = None) -> dict:
    """方向预览证据：同一份 PPTX 只渲染一次（确定性产物 + 字节戳命中即复用）。

    复用前提是渲染器没变：ghost.py 的指纹也写进 marker，渲染器一改，
    旧预览立即失效——证据必须和当前引擎说同一件事。
    """
    from qa import preview_issues
    from asset_workflow import file_digest
    page_ids = [str(s.get("id")) for s in spec.get("slides", [])]
    target = Path(output_dir)
    marker = target / "ghost.meta.json"
    engine = _ghost_engine_stamp()
    if output_sha and marker.exists():
        try:
            cached = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = {}
        sheet = cached.get("contact_sheet")
        if (cached.get("output_sha256") == output_sha
                and cached.get("engine") == engine
                and sheet and not preview_issues(cached, page_ids)):
            info = dict(cached)
            info["reused"] = True
            return info
    info = _ghost(spec, output_dir, base_path=base, image_bytes=image_bytes)
    info["slide_ids"] = [str(s.get("id")) for s in (spec.get("slides") or [])
                         if isinstance(s, dict) and s.get("id")]
    info["output_sha256"] = output_sha
    info["engine"] = engine
    info["reused"] = False
    info["file_sha256"] = {str(p): file_digest(p)
                            for p in info["pages"] + [info["contact_sheet"]] if p}
    _json_write(marker, info)
    return info


def run_check(build_path: str, output: str, *, mode: str = "draft",
              packet: str | None = None, preview: str | None = None,
              json_output: bool = False,
              assets_manifest: str | None = None, assets_dir: str | None = None,
              asset_qc_report: str | None = None) -> tuple[dict, int]:
    """Fresh run identity and fail-closed reports, including errors before schema checks."""
    from uuid import uuid4
    from qa import fail_result
    from asset_workflow import file_digest
    run_id = uuid4().hex
    output_path = Path(output).expanduser()
    packet_path = Path(packet).expanduser() if packet else output_path.with_suffix(".repair.json")
    manifest_path = output_path.with_suffix(".manifest.json")
    def publish_failure(result):
        result["run_id"] = run_id
        result["input_sha256"] = file_digest(Path(build_path).expanduser())
        _json_write(packet_path, _repair_packet(result, mode, Path(build_path), output_path))
        if mode != "spec":
            _json_write(manifest_path, {"run_id": run_id, "status": "BLOCKED",
                "release_eligible": False, "verification": {"release_eligible": False},
                "input_sha256": result["input_sha256"], "qa_report": result,
                "validation": {"issues": [result["next_action"]]}})
    initial = fail_result({}, ["本轮检查尚未完成；不得复用上一轮 PASS"])
    publish_failure(initial)
    try:
        result, code = _run_check(build_path, output, mode=mode, packet=packet, preview=preview,
            json_output=json_output,
            assets_manifest=assets_manifest, assets_dir=assets_dir,
            asset_qc_report=asset_qc_report, run_id=run_id)
        if mode == "draft":
            _json_write(manifest_path, {"run_id": run_id, "mode": "draft", "status": result["status"],
                "release_eligible": False, "verification": {"release_eligible": False},
                "qa_report": result, "next_action": "成功草稿仍须 --mode release 完成发布检查" if code==0 else result["next_action"]})
        return result, code
    except Exception as exc:
        result = fail_result({}, [f"输入或执行失败: {type(exc).__name__}: {exc}"])
        publish_failure(result)
        if json_output:
            print(json.dumps(_repair_packet(result, mode, Path(build_path), output_path), ensure_ascii=False))
        else:
            print(f"VAO {mode}: BLOCKED · {result['next_action']}")
        return result, 2


def _run_check(build_path: str, output: str, *, mode: str = "draft",
              packet: str | None = None, preview: str | None = None,
              json_output: bool = False,
              assets_manifest: str | None = None,
              assets_dir: str | None = None,
              asset_qc_report: str | None = None,
              run_id: str | None = None) -> tuple[dict, int]:
    """一次执行完成交付验证：normalize → guard → compile → 预览证据 → 修复包。

    零外部渲染器、零 reference 读取、零逐条修复循环：一个进程，一份结论。
    release 档自动产出 ghost 预览作为方向证据（结构判定的可视化凭证）。
    """
    from compile_cache import note_round
    from guard import normalize_spec
    from qa import release_manifest, run_qa, fail_result

    spec, build = load_spec(build_path)
    from asset_workflow import verify_chain, blocked_result
    asset_binding = None
    binding_error = None
    asset_qc_result = None
    if assets_manifest:
        try:
            spec, asset_binding = bind_asset_manifest(spec, assets_manifest, assets_dir)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            binding_error = str(exc)
        # 资产核验在这里发生一次：分步执行会漂移，一次执行只给一条修法。
        if asset_qc_report is None:
            asset_qc_result, _ = _asset_qc_report(assets_manifest, assets_dir, phase=mode)
            asset_qc_report = (asset_qc_result or {}).get("report_path")
    snapshots = {}
    workflow = verify_chain(spec, assets_manifest, asset_qc_report, assets_dir, image_bytes=snapshots)
    if binding_error:
        workflow.setdefault("issues", []).append(binding_error)
        workflow["status"] = "BLOCKED"
    normalized, norm = normalize_spec(spec)
    output_path = Path(output).expanduser()
    t0 = time.perf_counter()
    if workflow["status"] == "BLOCKED":
        result = blocked_result(normalized, workflow)
    else:
        result = run_qa(normalized, output_path, mode=mode,
                        normalize=False,
                        spec_path=str(build), image_bytes=snapshots)
        normalized = result.pop("_effective_spec", normalized)
    result["run_id"] = run_id
    result["asset_workflow"] = workflow
    if asset_qc_result is not None:
        workflow["qc"] = {"status": asset_qc_result.get("status"),
                          "summary": asset_qc_result.get("summary")}
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
    if preview_dir and result.get("passed") and workflow["status"] != "BLOCKED":
        ghost = _ghost_cached(normalized, preview_dir, build.parent,
                              output_sha=(result.get("compile") or {}).get("output_sha256"), image_bytes=snapshots)
        result["ghost_preview"] = ghost

    manifest = None
    if mode == "release":
        manifest = release_manifest(normalized, result, ghost_preview=ghost)
        if manifest["status"] == "BLOCKED" and result.get("passed"):
            errors = manifest["validation"]["issues"] or ["发布凭证无效"]
            fail_result(result, errors)
            manifest = release_manifest(normalized, result, ghost_preview=ghost)
            manifest["validation"]["issues"] = errors

    # Record the final verdict, not the pre-manifest intermediate PASS.
    ledger = note_round(output_path.with_name(output_path.stem + "_vao"),
                        mode=mode, spec_hash=result.get("source_spec_hash"),
                        status=result.get("status"), blocking=result.get("blocking_items"),
                        warnings=len(result.get("trace_summary") or []))
    result["rounds"] = ledger
    manifest_path = None
    if manifest is not None:
        manifest.update(revision_count=ledger.get("revisions", 0), revision_log=ledger.get("log"))
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
            print("  ✓ 无阻断：证据只留痕（warn/hint 不进入对话）")
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
    """Prepare a plan/manifest OR check an existing build; never skip the asset pause."""
    build = args.build
    if build and getattr(args, "assets_out", None):
        raise ValueError("run --assets-out 只准备资产；不要同时 --build。先出图与QC，再 check 编排稿")
    if build:
        # Do not overwrite a plan already bound to image/QC evidence.
        bundle = None
    else:
        bundle = _plan(args.brief, args.plan_out, args.skeleton)
    if getattr(args, "assets_out", None):
        from intent_compiler import _load_need
        need = _load_need(args.brief)
        manifest = build_asset_manifest(need, bundle=bundle,
                                        cache_path=getattr(args, "asset_cache", None))
        from asset_workflow import prepare_manifest
        manifest = prepare_manifest(manifest, need, bundle, args.brief, args.plan_out,
                                    args.assets_out, getattr(args, "assets_dir", None))
        _json_write(args.assets_out, manifest)
        print(f"assets complete · unique_calls={manifest['asset_budget']['unique_generation_calls']} "
              f"· manifest={args.assets_out}")
    if not build:
        if not args.skeleton:
            print(json.dumps({"plan": bundle, "next": "有图先 assets → 出图 → 填骨架 → check（资产核验在 check 内部完成）"},
                             ensure_ascii=False, indent=2))
        else:
            print(f"plan complete · skeleton: {args.skeleton} · "
                  "有图先 assets → 出图 → 填骨架 → check（资产核验在 check 内部完成）")
        return 0
    manifest_for_check = getattr(args, "assets_manifest", None) or getattr(args, "assets_out", None)
    _, code = run_check(build, args.output, mode=args.mode, packet=args.packet,
                        preview=args.preview,
                        json_output=args.json, assets_manifest=manifest_for_check,
                        assets_dir=getattr(args, "assets_dir", None),
                        asset_qc_report=getattr(args, "asset_qc_report", None),
                        )
    return code


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
    a.add_argument("--plan", dest="plan_path", required=True,
                   help="必需：先由 vao.py plan 保存的 plan.json")
    a.add_argument("--out", default="asset_manifest.json")
    a.add_argument("--assets-dir",
                   help="图将被放到哪个目录（写进 manifest，check 默认据此找图并核验）")
    a.add_argument("--cache", help="prompt cache JSON; reuse identical visual-demand fingerprints")
    a.add_argument("--json", action="store_true")

    c = sub.add_parser("check", help="build.py → normalize/guard/compile/preview → packet")
    c.add_argument("build")
    c.add_argument("output", nargs="?", default="deck.pptx")
    c.add_argument("--mode", choices=("spec", "draft", "release"), default="draft")
    c.add_argument("--packet")
    c.add_argument("--preview", help="write ghost preview PNGs here (release writes them by default)")
    c.add_argument("--assets-manifest", help="bind image elements carrying asset_id")
    c.add_argument("--assets-dir", help="directory containing generated manifest filenames")
    c.add_argument("--asset-qc-report", help="QC报告；默认资产清单同目录的 <stem>.qc.json")
    c.add_argument("--json", action="store_true")

    r = sub.add_parser("run", help="prepare plan/assets OR check an existing build after QC")
    r.add_argument("brief")
    r.add_argument("--build")
    r.add_argument("--skeleton", default="build_vao.py")
    r.add_argument("--plan-out", default="plan.json")
    r.add_argument("--output", default="deck.pptx")
    r.add_argument("--assets-out", help="also emit deduplicated asset_manifest.json in this run")
    r.add_argument("--asset-cache", help="prompt cache JSON for --assets-out")
    r.add_argument("--assets-manifest", help="bind an existing asset manifest during check")
    r.add_argument("--assets-dir", help="directory containing generated manifest filenames")
    r.add_argument("--asset-qc-report", help="QC报告；默认资产清单同目录的 <stem>.qc.json")
    r.add_argument("--mode", choices=("spec", "draft", "release"), default="draft")
    r.add_argument("--packet")
    r.add_argument("--preview")
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
            from asset_workflow import prepare_manifest
            bundle = json.loads(Path(args.plan_path).expanduser().read_text(encoding="utf-8"))
            manifest = build_asset_manifest(need, bundle=bundle, cache_path=args.cache)
            manifest = prepare_manifest(manifest, need, bundle, args.brief, args.plan_path,
                                        args.out, getattr(args, "assets_dir", None))
            _json_write(args.out, manifest)
            if args.json:
                print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
            else:
                calls = (manifest.get("asset_budget") or {}).get("unique_generation_calls", 0)
                print(f"assets complete · unique_calls={calls} · manifest={args.out}")
                gen_items = [a for a in manifest.get("assets", []) if a.get("decision") == "generate"]
                if gen_items:
                    print("-" * 60)
                    print("  视觉资产提示词清单 (via asset_prompt.py)")
                    print("-" * 60)
                    for idx, a in enumerate(gen_items, 1):
                        sid = ",".join(a.get("slide_ids", []))
                        aid = a.get("asset_id")
                        fn = a.get("expected_filename")
                        ratio = a.get("ratio", "16:9")
                        prompt = a.get("prompt", "")
                        neg = a.get("negative", "")
                        print(f"[{idx}/{len(gen_items)}] Slide {sid} -> {fn} (ID: {aid})")
                        print(f"  Ratio: {ratio} | Safe Area: {a.get('safe_area')}")
                        print(f"  Prompt: {prompt}")
                        if neg:
                            print(f"  Negative: {neg}")
                        print("-" * 60)
            return 0
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
                                json_output=args.json,
                                assets_manifest=args.assets_manifest,
                                assets_dir=args.assets_dir,
                                asset_qc_report=args.asset_qc_report,
                                )
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
