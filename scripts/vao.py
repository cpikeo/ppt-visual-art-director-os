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
import re
import sys
import time
import types
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
# 方向预览是可选证据：剩余预算不足它（含 contact sheet）时宁可不渲染 —— 
# 一次超时的「交付」比没有预览的交付更糟。
GHOST_MIN_BUDGET_S = 4.0
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
    from primitives import json_read_cached
    manifest_file = Path(manifest_path).expanduser().resolve()
    payload = json_read_cached(manifest_file)
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
    bundle = build_plan_bundle(need)       # route + page intents: one in-process pass
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
        # 覆写保护：已填稿的骨架（elements 非空）被重跑 R1 冲掉 = 整份编排归零。
        # 实测作者只能靠「不传 --skeleton」规避；引擎应承担这个保护。
        if target.is_file():
            old = target.read_text(encoding="utf-8", errors="replace")
            if re.search(r'"elements"\s*:\s*\[\s*\{', old):
                safe = target.with_name(target.name + ".new.py")
                safe.write_text(build_skeleton_module(bundle), encoding="utf-8")
                print(f"skeleton: 检测到已填稿的 {target.name}，新骨架改写 {safe.name}（不覆盖作业稿）")
                return bundle
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
            # 「复用本稿已生成的图」：把清单身份带回既有素材条目（v6.4.3）。
            # 作者声明 asset_source 时，图常常就是**本稿 plan 已规划**的那一张
            # （迭代重出，或先生成后补清单）。身份不该因此退化成 existing-<hash>：
            # 认得出规划身份就保留规划 asset_id 与 prompt/negative——「还是那一张」
            # 得以成立，作者不必重抄一整套资产卡（否则下一次迭代会绕过链路）。
            planned = None
            try:
                _card_pv, _page_pv = _asset_page(brief, page_plan, raw, asset_id=f"asset-{sid}",
                                                 deck=plan)
                _fp = asset_fingerprint(_card_pv, _page_pv)
                planned = f"asset-{_fp.removeprefix('asset-')}"
            except Exception:      # noqa: BLE001 —— 规划身份只是加分项，算不出来不影响登记
                planned = None
            stem = Path(origin["path"]).stem
            if planned and (str(origin.get("asset_id") or "") == planned or stem == planned):
                aid = planned
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
                if planned and aid == planned:
                    try:
                        _built = build_asset_prompt(_card_pv, _page_pv,
                                                    ratio=str(raw.get("asset_ratio")
                                                              or brief.get("asset_ratio") or "16:9"),
                                                    asset_function=_page_pv["asset_function"])
                        assets[-1].update({"prompt": _built.get("prompt"),
                                           "negative": _built.get("negative"),
                                           "expected_filename": assets[-1].get("expected_filename")
                                           or f"{aid}{Path(origin['path']).suffix}",
                                           "planned_identity": True})
                    except Exception:      # noqa: BLE001
                        pass
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
        "speed": (result.get("execution") or {}).get("speed"),
        "budget": result.get("budget"),
        "preview": ({"scope": result["ghost_preview"].get("scope"),
                     "pages": result["ghost_preview"].get("count"),
                     "reused": result["ghost_preview"].get("reused")}
                    if result.get("ghost_preview") else None),
        "performance": result.get("performance", {}),
    }
    return packet


def _ghost(spec: dict, output_dir: str | Path, pages: list[int] | None = None,
           base_path: str | Path | None = None, image_bytes: dict | None = None,
           decoded: dict | None = None, *, speed: str = "strict", limit: int = 4) -> dict:
    """方向预览证据：默认全量，快速档按方向采样（封面/最复杂页/图片页/收尾）。

    采样不是「少看点」——是**把证据范围写清楚**：info 里带 scope 与 sampled_ids，
    清单按声明核对（采样页必须等于渲染页，且都在当前稿件的页集合内）。
    """
    from ghost import PAGE_CACHE_DIR, ghost_deck, make_contact_sheet, sample_pages
    fast = str(speed).lower() == "fast"
    slides = spec.get("slides") or []
    if pages is not None:
        wanted = [int(n) for n in pages]
        scope = "full" if len(wanted) >= len(slides) else "explicit_subset"
    elif fast:
        wanted = sample_pages(slides, limit=limit)
        scope = "full" if len(wanted) >= len(slides) else "sampled"
    else:
        wanted = list(range(1, len(slides) + 1))
        scope = "full"
    preview_spec = dict(spec)
    preview_spec["_image_bytes"] = image_bytes or {}
    # 底图解码复用：核验阶段（QC）已经解过的底图直接交给预览，同一轮里一张图只解一次。
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
    drawn_pages = [int(n) for n in (page_stats.get("rendered_pages") or [])]
    cached_pages = [int(n) for n in (page_stats.get("cached_pages") or [])]
    sampled_ids = [str(slides[n - 1].get("id")) for n in wanted
                   if 1 <= n <= len(slides) and isinstance(slides[n - 1], dict)]
    return {"type": "ghost_layout_preview", "dir": str(Path(output_dir)),
            "pages": [str(p) for p in paths], "count": len(paths),
            "pages_rendered": wanted, "page_count": len(slides),
            "scope": scope, "sampled_ids": sampled_ids,
            "contact_sheet": str(contact) if contact else None,
            "renderer": "PIL", "supersampled": not fast,
            # 这一轮真正画了几页 / 命中上一轮页缓存几页（迭代时改一页只画一页）。
            # 页号清单是唯一事实来源：当年这里写 `page_stats.get("rendered", len(paths))`，
            # 全部命中缓存时 rendered 键根本不存在，默认值把「一页没画」记成了「全画了」。
            "pages_drawn": len(drawn_pages),
            "pages_from_cache": len(cached_pages),
            "pages_drawn_numbers": drawn_pages,
            "pages_reused_numbers": cached_pages,
            # 联络表是页图的纯函数：页图没变就复制上一轮那张（字节相同）
            "contact_sheet_cached": bool(sheet_stats.get("sheet_cached")),
            "evidence_scope": "direction_and_structure_not_pixel_proof"}


def _asset_qc_report(manifest_path: str, input_dir: str | None = None,
                     *, phase: str = "draft", speed: str = "strict",
                     output: str | None = None,
                     snapshots: dict | None = None,
                     decoded: dict | None = None,
                     digests: dict | None = None) -> tuple[dict, int]:
    """资产核验：一次判定，一条修法（draft 最多一次定向重出）。

    这是 `check` 内部的一步，不是独立入口——绑定、核验、结论必须在同一次
    执行里发生，否则分步执行会漂移（v5.7：asset-qc 与 check 合并）。

    性能纪律（v5.9）：
      * `speed="fast"` 时像素统计在整数箱降采样后的工作域进行（判据口径不变，
        每块仍 ≈QC_BLOCK 源像素）；严格档保持原分辨率。
      * 这里读到的图片字节就是本轮唯一一次读取：写进 `snapshots` 后，
        资产链核验与编译器直接消费同一份不可变字节（不再读第二遍）。
      * 每个资产的 size+mtime_ns 一并记入报告，供下游做「字节没变」的快路径判定。
    """
    from asset_prompt import (ROLE_AUTHORITATIVE_SOURCES, image_qc, qc_policy,
                              qc_profile, qc_retry_decision)

    from primitives import (digest_bytes, engine_fingerprint, json_read_cached,
                           text_is_dark,
                            witness_matches)
    from asset_workflow import QC_REPORT_SCHEMA
    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest = json_read_cached(manifest_file)
    from asset_workflow import (ACCEPTED, asset_entries, digest,
                                now, resolve_asset, verify_sources)
    profile = qc_profile(speed)
    # spec 档只诊断不产出：资产核验照常执行，但 QC 阶段必须是合法值
    # （此前 spec + --assets-manifest 会在 qc_retry_decision 里抛 unknown phase）。
    qc_phase = "draft" if str(phase).strip().lower() not in {"draft", "review", "release"} \
        else str(phase).strip().lower()
    # ── 上一轮判定的复用前提（缺一即重新测量）─────────────────────────────
    #   * 同一份清单（manifest_sha256）与同一阶段；
    #   * 同一像素预算（档位 / max_side）；
    #   * 同一判定实现（asset_prompt.py 的指纹——阈值或口径一改，旧判定作废）；
    #   * 每个资产的字节身份（size+mtime_ns，严格档再加 sha256）与判定输入一致。
    # 「复用」只在全部成立时发生，任一不成立即回到完整测量：快路径不是漏检路径。
    prev_report: dict = {}
    reuse_base: str | None = None
    prev_results: dict = {}
    try:
        from asset_workflow import file_digest
        prev_path = Path(output).expanduser() if output else manifest_file.with_name(
            manifest_file.stem + ".qc.json")
        if prev_path.exists():
            prev_report = json_read_cached(prev_path)
    except (OSError, ValueError, TypeError):
        prev_report = {}
    if prev_report:
        engine_now = engine_fingerprint("measure")
        if (prev_report.get("manifest_sha256") == digest(manifest)
                and prev_report.get("pixel_profile") == profile
                and prev_report.get("phase") == qc_phase
                and prev_report.get("qc_engine") == engine_now):
            reuse_base = "sha256" if profile.get("speed") == "strict" else "size+mtime_ns"
            prev_results = {str(r.get("asset_id")): r for r in (prev_report.get("results") or [])}
    reused_assets = 0
    workflow_issues = verify_sources(manifest)
    results = []
    actions: dict[str, list[str]] = {}
    pending: list[str] = []        # 还没生成（先出图再 QC），与「生成不合格」分开报
    strict_witness = (reuse_base == "sha256")
    for entry in asset_entries(manifest):
        candidate = resolve_asset(entry, manifest, manifest_file, input_dir)
        try:
            stat = candidate.stat()
            size, mtime_ns = stat.st_size, stat.st_mtime_ns
        except OSError:
            size, mtime_ns = None, None
        # 字节按需读、摘要按需算。快档若上一轮凭证已带 sha256 且字节身份一致，
        # 本轮**不需要字节**：判定看 size+mtime_ns，编译投影与资产链核验消费凭证里
        # 的 sha256，预览与编译都在各自缓存里。此前这里无条件读整批字节——热轮里
        # 50MB 读进来没有任何消费者，那不是证据，是习惯（同一事实只产生一次）。
        carried = (prev_results or {}).get(str(entry.get("asset_id"))) or {}
        carried_witness = carried.get("witness") or {}
        carried_sha = carried_witness.get("sha256")
        carried_ok = bool(not strict_witness and carried_sha
                          and witness_matches(carried_witness,
                                              {"size": size, "mtime_ns": mtime_ns}))

        def _bytes():
            return candidate.read_bytes() if candidate.is_file() else None

        blob = None if carried_ok else _bytes()
        image_sha = carried_sha if carried_ok else (digest_bytes(blob) if blob is not None else None)
        # 注：prepare 阶段已把「prepare 时字节已存在」的 generate 条目如实登记为
        # existing（origin.source 留痕），此处不再有「清单前已有同一图片」的阻断分支。
        if entry["decision"] == "generate" and (not entry.get("prompt") or not entry.get("negative")):
            workflow_issues.append(f"{entry['asset_id']}: 缺少 prompt / negative")
        if entry["decision"] == "existing":
            origin = entry.get("origin") or {}
            if origin.get("kind") not in {"provided", "licensed", "original", "reuse"} or not origin.get("source"):
                workflow_issues.append(f"{entry['asset_id']}: 既有素材缺少合法 kind / source 声明")
        safe = entry.get("safe_area") or {}
        text_color = ((entry.get("meta") or {}).get("text_color")
                      or (entry.get("page") or {}).get("text_color"))
        qc_inputs = {"safe_rect": safe, "text_color": text_color,
                     "ratio": entry.get("ratio"),
                     "allow_crop": entry.get("allow_crop") is True,
                     "background": entry.get("background_color") or "#FFFFFF",
                     "max_side": profile["max_side"]}
        previous = (prev_results or {}).get(str(entry.get("asset_id")))
        base_ok = bool(previous and reuse_base is not None and witness_matches(
            previous.get("witness") or {}, {"size": size, "mtime_ns": mtime_ns}))
        reused_qc = None
        if previous and reuse_base is not None:
            # 字节身份：判据只有一处（primitives.witness_matches）；严格档再比 sha256，
            # 用的是已经算出的那份摘要，不再对同一批字节算第二遍。
            same_bytes = witness_matches(
                previous.get("witness") or {},
                {"size": size, "mtime_ns": mtime_ns, "sha256": image_sha},
                strict=(reuse_base == "sha256"))
            if same_bytes and previous.get("qc_inputs") == qc_inputs:
                reused_qc = dict(previous.get("qc") or {})
        if reused_qc is None and blob is None:      # 判定要重测：此时像素是必需品
            blob = _bytes()
            if image_sha is None:
                image_sha = digest_bytes(blob) if blob is not None else None
        if blob is not None and snapshots is not None:
            # 唯一一次读取：核验与编译共用这份字节（不变量：内容不可变）。
            snapshots[str(candidate)] = blob
        if image_sha is not None and digests is not None:
            # 唯一一次哈希：下游（资产链核验 / 编译缓存投影）复用这份摘要，
            # 不再对同一批字节各算一遍（实测一轮曾算三遍，208MB）。
            digests[str(candidate)] = image_sha
        if reused_qc is not None:
            # 复用的是「判定」，不是「证据」：判定输入与字节身份都相同，像素级测量
            # （降采样域统计 + 原生分辨率安全区纹理）结果只会一模一样。省掉的是
            # 解码与统计——一轮 check 里最贵的两部分，且它每轮都在重复。
            qc = reused_qc
            qc["reused"] = True
            qc["reused_from"] = previous.get("checked_at")
            reused_assets += 1
        else:
            qc = image_qc(str(candidate), safe_rect=safe,
                          # 声明可以是 hex（产物里的真颜色）或 dark/light 语义词：
                          # 判定的唯一实现在 primitives，这里不做第二套解析。
                          text_is_dark=text_is_dark(text_color),
                          image_bytes=blob, expected_ratio=entry.get("ratio"),
                          allow_crop=entry.get("allow_crop") is True,
                          background=entry.get("background_color") or "#FFFFFF",
                          max_side=profile["max_side"],
                          decoded=decoded, decode_key=str(candidate))
        # 角色只有「作者说过的话」才对 QC 有发言权（declared / legacy）；
        # assumed 角色不得悄悄放宽或收紧任何一条判据。
        role_authority = (entry.get("asset_role")
                          if entry.get("asset_role_source") in ROLE_AUTHORITATIVE_SOURCES
                          else None)
        decision = qc_retry_decision(qc, attempt=int(entry.get("attempt", 0) or 0),
                                     phase=qc_phase, max_retries=entry.get("retry_budget", 1),
                                     asset_function=entry.get("asset_function"),
                                     asset_role=role_authority)
        missing = (qc.get("status") == "error")   # 文件不存在 ≠ 图片不合格：修法不同
        item = {"asset_id": entry.get("asset_id"), "slide_ids": entry.get("slide_ids") or [],
                "file": str(candidate),
                "qc_inputs": qc_inputs, "checked_at": now(),
                # 字节凭证（全库唯一写法）：只读一次也能证明「还是那一份」。
                # sha256 与整批资产共享同一份摘要（digests），不在这里另存一份。
                "witness": {"size": size, "mtime_ns": mtime_ns, "sha256": image_sha},
                "qc": qc, "policy": decision, "missing": missing}
        results.append(item)
        actions.setdefault(decision["action"], []).append(str(entry.get("asset_id")))
        if missing:
            pending.append(str(entry.get("asset_id")))
    report = {
        "schema": QC_REPORT_SCHEMA,         # v4：字节凭证统一为 witness{size,mtime_ns,sha256}

        "manifest": str(manifest_file),
        "qc_engine": engine_fingerprint("measure"),
        "manifest_sha256": digest(manifest), "checked_at": now(),
        "workflow_issues": workflow_issues,
        "status": "PASS" if not workflow_issues and all(
            (r.get("policy") or {}).get("action") in ACCEPTED for r in results) else "BLOCKED",
        "phase": qc_phase,
        "pixel_profile": profile,
        # 复用范围写进报告：证据不会假装自己刚量过一遍。
        "reuse": ({"assets": reused_assets, "witness": reuse_base}
                  if reused_assets else None),
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
    # 全部判定都复用的一轮不重写这份证据：文件上的 checked_at 回答的是「这些像素什么时候
    # 被量过」，不是「谁什么时候读过它」。重写会把时间戳刷成「刚量过」——一句假话，
    # 顺带改一次 mtime，逼下游把没变的字节再读一遍。判定内容不变 = 文件不必动。
    # 只对「引擎自己派生的报告路径」生效：作者显式指定了输出路径（`vao assets --out`）
    # 就是显式要一份文件，照写不误。
    if output or not (prev_report and reuse_base is not None and results
                      and reused_assets == len(results)):
        _json_write(out_path, report)
    # 静默：一次执行只输出一条结论（check 打印）。0 只代表「每个应生成的资产都被
    # 验证过且无阻断」；未生成 = 无法验证 = 不能当作通过。
    return report, 0 if report["status"] == "PASS" else 2


def _ghost_engine_stamp() -> str:
    """预览器指纹：唯一实现（primitives.engine_fingerprint 的 preview scope）。"""
    from primitives import engine_fingerprint
    return engine_fingerprint("preview", short=16)


def _ghost_cached(spec: dict, output_dir: str | Path, base: Path,
                  output_sha: str | None = None, image_bytes: dict | None = None,
                  decoded: dict | None = None,
                  *, speed: str = "strict", limit: int = 4) -> dict:
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
                and cached.get("renderer_speed") == str(speed)
                and sheet and not preview_issues(cached, page_ids)):
            info = dict(cached)
            info["reused"] = True
            return info
    info = _ghost(spec, output_dir, base_path=base, image_bytes=image_bytes,
                  decoded=decoded, speed=speed, limit=limit)
    # slide_ids = 实际渲染的页 id（证据核对用）；sampled_ids = 声明的采样范围。
    # 两者在采模式下必须相等——「声明渲染了哪几页」与「渲染了哪几页」不允许不一致。
    info["slide_ids"] = list(info.get("sampled_ids") or [])
    info["output_sha256"] = output_sha
    info["engine"] = engine
    info["renderer_speed"] = str(speed)
    info["reused"] = False
    info["file_sha256"] = {str(p): file_digest(p)
                            for p in info["pages"] + [info["contact_sheet"]] if p}
    _json_write(marker, info)
    return info


def run_check(build_path: str, output: str, *, mode: str = "draft",
              packet: str | None = None, preview: str | None = None,
              json_output: bool = False,
              assets_manifest: str | None = None, assets_dir: str | None = None,
              asset_qc_report: str | None = None,
              speed: str = "fast", deadline: float | None = None,
              ghost_pages: int = 4) -> tuple[dict, int]:
    """Fresh run identity and fail-closed reports, including errors before schema checks.

    失败必须落盘（fail-closed），但**成功路径不再先写一份假失败**：
    此前每次 check 都先构造 BLOCKED 报告、写 repair packet、写 manifest，再覆盖它们。
    那是两次无效 I/O + 一次误导性的中间态（任何在这之间读文件的观察者都会看到
    「这一轮已经 BLOCKED」）。现在只在真失败（异常 / 判定为阻断）时写。
    """
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
    try:
        result, code = _run_check(build_path, output, mode=mode, packet=packet, preview=preview,
            json_output=json_output,
            assets_manifest=assets_manifest, assets_dir=assets_dir,
            asset_qc_report=asset_qc_report, run_id=run_id, speed=speed,
            deadline=deadline, ghost_pages=ghost_pages)
        if mode == "draft":
            _json_write(manifest_path, {"run_id": run_id, "mode": "draft",
                "status": result["status"], "release_eligible": False,
                "verification": {"release_eligible": False}, "qa_report": result,
                "next_action": ("成功草稿仍须 --mode release 完成发布检查" if code == 0
                                else result.get("next_action"))})
        return result, code
    except Exception as exc:
        result = fail_result({}, [f"输入或执行失败: {type(exc).__name__}: {exc}"])
        # 上一轮的 PASS 不能继承：失败一律留下 BLOCKED 凭证。
        result["stale_pass_write"] = _stale_manifest_write(manifest_path, run_id, result,
                                                          build_path, mode)
        publish_failure(result)
        if json_output:
            print(json.dumps(_repair_packet(result, mode, Path(build_path), output_path), ensure_ascii=False))
        else:
            print(f"VAO {mode}: BLOCKED · {result['next_action']}")
        return result, 2


def _stale_manifest_write(manifest_path: Path, run_id: str, result: dict,
                          build_path: str, mode: str) -> bool:
    """把失败写进产物清单位（同一份路径），确保「上一轮 PASS」不会留在磁盘上冒充本轮。"""
    if mode == "spec":
        return False
    try:
        from asset_workflow import file_digest
        _json_write(manifest_path, {"run_id": run_id, "status": "BLOCKED",
            "release_eligible": False, "verification": {"release_eligible": False},
            "input_sha256": file_digest(Path(build_path).expanduser()),
            "qa_report": result, "validation": {"issues": [result.get("next_action")]}})
        return True
    except Exception:
        return False


def _compile_step(spec: dict, output_path: Path, *, mode: str, speed: str,
                  guard_errors: list, effective_rules: dict,
                  cache: bool = True, spec_path: str | None = None,
                  image_bytes: dict | None = None,
                  digests: dict | None = None,
                  decode_seed: dict | None = None,
                  t_guard_start: float | None = None) -> tuple[dict, dict]:
    """产物生产（编排层职责）：缓存探测 → 编译 → 产物凭证 → 缓存写入。

    2026-09 审核把这段从 qa 移到这里：**编译是执行层的事**，QA 只消费产物报告。
    原来的形状是「QA 发现没有 compile_report 就自己编译」——判定层因此同时是生产者，
    产物可能在「判定输入的见证」之外被重建。现在：vao 编译并出报告，QA 只读报告。
    返回 (compile_report, timing)：timing 是这一段的真实读数（判定层据此写报告）。
    """
    from compile_cache import compile_reuse, record_compile, spec_view
    from primitives import file_digest

    t_guard_end = time.perf_counter()
    t_guard_start = t_guard_end if t_guard_start is None else t_guard_start
    compile_report: dict | None = None
    semantic_view = None
    cache_reason = "not_compiled"
    cache_root = output_path.with_name(output_path.stem + "_vao")
    if cache:
        try:
            cache_root.mkdir(parents=True, exist_ok=True)
            semantic_view = spec_view(spec, base_path=output_path.parent,
                                      spec_path=spec_path, image_bytes=image_bytes,
                                      digests=digests)
            compile_report = compile_reuse(cache_root, output_path, semantic_view,
                                           fast_probe=(speed == "fast"), speed=speed)
            cache_reason = ("view_and_output_attestation_match"
                            if compile_report is not None else "cache_miss")
        except Exception:
            cache_reason = "cache_probe_failed"
            compile_report = None
    if compile_report is None:
        try:
            from compiler import compile_deck
            compile_report = compile_deck(spec, output_path, checks=False,
                                          decode_seed=decode_seed,
                                          guard_rules=effective_rules,
                                          spec_path=str(spec_path) if spec_path else None,
                                          image_bytes=image_bytes, speed=speed)
        except ModuleNotFoundError as exc:
            if exc.name in {"pptx", "lxml", "PIL", "numpy"}:
                compile_report = {
                    "passed": False, "slides": len(spec.get("slides") or []),
                    "warnings": [f"[dependency] 缺少编译依赖 {exc.name!r}；请运行 "
                                 "python -m pip install -r requirements.txt"],
                    "file_bytes": None, "dependency_missing": exc.name}
            else:
                raise
    t_attest = time.perf_counter()

    # 产物凭证：报告必须能对上磁盘上的那一份 PPTX，缓存报告不算证据。
    if not compile_report.get("skipped"):
        try:
            stat = output_path.stat()
            actual_bytes = stat.st_size
            actual_sha = compile_report.pop("_cache_verified_sha256", None) or file_digest(output_path)
            if compile_report.get("file_bytes") is not None \
                    and int(compile_report["file_bytes"]) != actual_bytes:
                compile_report.setdefault("warnings", []).append(
                    f"[output] 编译报告 file_bytes={compile_report['file_bytes']} "
                    f"与实际文件 {actual_bytes} 不一致")
                compile_report["passed"] = False
            expected_sha = compile_report.get("output_sha256")
            if expected_sha and actual_sha and expected_sha != actual_sha:
                compile_report.setdefault("warnings", []).append(
                    "[output] 编译报告 output_sha256 与实际 PPTX 不一致（文件可能被替换）")
                compile_report["passed"] = False
            if not actual_sha:
                compile_report.setdefault("warnings", []).append(
                    f"[output] 无法计算 PPTX SHA-256: {output_path}")
                compile_report["passed"] = False
            compile_report["file_bytes"] = actual_bytes
            compile_report["output_sha256"] = actual_sha
            compile_report["output_path"] = str(output_path.resolve())
            compile_report["output_exists"] = True
            # 见证信息：本轮读到的到底是哪一份字节。发布清单据此避免重复整包哈希
            # （stat 不一致时它仍会重新哈希——快路径不得成为漏检路径）。
            compile_report["output_size"] = actual_bytes
            compile_report["output_mtime_ns"] = stat.st_mtime_ns
            compile_report["attestation_mode"] = ("cache_view_match"
                                                 if compile_report.get("reused") else "content_hash")
        except (OSError, TypeError, ValueError):
            compile_report.setdefault("warnings", []).append(
                f"[output] 编译输出不存在或不可读取: {output_path}")
            compile_report["passed"] = False
            compile_report["output_exists"] = False
            compile_report["output_sha256"] = None
    if semantic_view is None and not compile_report.get("skipped"):
        try:
            from compile_cache import spec_view as _spec_view
            semantic_view = _spec_view(spec, base_path=output_path.parent,
                                       spec_path=spec_path, image_bytes=image_bytes)
        except Exception:
            semantic_view = None
    if semantic_view:
        # 输入投影与产物字节戳是两件事：前者判"要不要重编"，后者判"文件是不是它"。
        compile_report["semantic_compile_view"] = semantic_view
    if cache and semantic_view and compile_report.get("output_sha256") \
            and compile_report.get("output_exists"):
        record_compile(cache_root, output_path, semantic_view, compile_report)
    t_attest_end = time.perf_counter()
    timing = {"guard_ms": int((t_guard_end - t_guard_start) * 1000),
              "compile_ms": int((t_attest - t_guard_end) * 1000),
              "attestation_ms": int((t_attest_end - t_attest) * 1000),
              "cache_reason": cache_reason, "cache_enabled": bool(cache),
              "cache_dir": str(cache_root)}
    return compile_report, timing

def _run_check(build_path: str, output: str, *, mode: str = "draft",
              packet: str | None = None, preview: str | None = None,
              json_output: bool = False,
              assets_manifest: str | None = None,
              assets_dir: str | None = None,
              asset_qc_report: str | None = None,
              run_id: str | None = None,
              speed: str = "fast",
              deadline: float | None = None,
              ghost_pages: int = 4) -> tuple[dict, int]:
    """一次执行完成交付验证：normalize → guard → compile → 预览证据 → 修复包。

    零外部渲染器、零 reference 读取、零逐条修复循环：一个进程，一份结论。
    release 档自动产出 ghost 预览作为方向证据（结构判定的可视化凭证）。

    性能纪律（v5.9）：
      * 图片只读一次：资产核验读到的字节经 `snapshots` 直接进资产链核验、
        编译器与预览——同一份字节全链复用，不再有「QC 读一遍 / 核验再读一遍」。
      * `speed` 贯穿 QC / 编译 / 预览 / 缓存探测四层（见各模块 docstring）。
      * `deadline`（秒）是**本次调用的预算**：核心阶段（核验→guard→编译→收口）
        永远执行；可选阶段（方向预览采样、contact sheet）在预算不足时被跳过并留痕。
        这是「有预算的执行」，不是「未完成的交付」——跳过什么、为什么跳过都写进报告。
    """
    from compile_cache import note_round
    from guard import check_spec, normalize_spec
    from qa import mode_profile, release_guard_rules, release_manifest, verdict
    from run_evidence import RunEvidence

    started = time.perf_counter()
    # 这一轮的运行时事实：身份与读数都写进它，报告 / 清单 / 预览证据都从这里取。
    # 它是「为什么可以复用」的唯一账本，也是 COLD/HOT 契约的执行点。
    evidence = RunEvidence(run_id=run_id, mode=mode, speed=speed)
    deadline_at = (started + float(deadline)) if deadline else None
    budget = {"deadline_s": float(deadline) if deadline else None, "skipped": []}

    def remaining() -> float | None:
        return None if deadline_at is None else deadline_at - time.perf_counter()

    def defer(stage: str, why: str) -> None:
        budget["skipped"].append({"stage": stage, "reason": why})

    spec, build = load_spec(build_path)
    # Fail before touching image bytes: a missing compiler dependency is an
    # environment error, not an asset-QC problem. The case study exposed this
    # late failure as a wasteful extra turn after the full asset pass.
    if str(mode).lower() != "spec":
        import importlib.util
        missing = next((name for name in ("pptx",) if importlib.util.find_spec(name) is None), None)
        if missing:
            exc = ModuleNotFoundError(f"missing compiler dependency: {missing}")
            exc.name = missing
            raise exc
    from asset_workflow import verify_chain, blocked_result
    asset_binding = None
    binding_error = None
    asset_qc_result = None
    snapshots: dict = {}          # 本轮唯一一次读图：核验 / 编译 / 预览共用这份字节
    decoded: dict = {}            # 核验解码过的底图：编译期不再重复解码（所有权转移）
    digests: dict = {}            # 本轮唯一一次哈希：核验 / 编译投影共用这份摘要
    if assets_manifest:
        try:
            spec, asset_binding = bind_asset_manifest(spec, assets_manifest, assets_dir)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            binding_error = str(exc)
        # 资产核验在这里发生一次：分步执行会漂移，一次执行只给一条修法。
        if asset_qc_report is None:
            asset_qc_result, _ = _asset_qc_report(assets_manifest, assets_dir, phase=mode,
                                                  speed=speed, snapshots=snapshots,
                                                  decoded=decoded, digests=digests)
            asset_qc_report = (asset_qc_result or {}).get("report_path")
    workflow = verify_chain(spec, assets_manifest, asset_qc_report, assets_dir,
                            image_bytes=snapshots, digests=digests)
    if binding_error:
        workflow.setdefault("issues", []).append(binding_error)
        workflow["status"] = "BLOCKED"
    normalized, norm = normalize_spec(spec)
    from primitives import byte_witness, identity, spec_fingerprint
    evidence.identity("input", spec=spec_fingerprint(normalized),
                      build=str(Path(build_path).expanduser().name),
                      build_witness=byte_witness(build_path, digest=True))
    output_path = Path(output).expanduser()
    t0 = time.perf_counter()
    if workflow["status"] == "BLOCKED":
        result = blocked_result(normalized, workflow)
        first = next((i for i in (workflow.get("issues") or []) if str(i).strip()), "")
        evidence.blocked(str(first)[:120] or "资产链核验未通过")
    else:
        # 编排在这里：guard（一次）→ compile（一次，gate 通过才发生）→ 判定（只读报告）。
        # QA 不编译、不读产物字节：它的输入只有两份报告 + 本轮的运行时事实。
        prof = mode_profile(mode)
        effective_rules = release_guard_rules(prof["mode"], None)
        t_guard_start = time.perf_counter()
        guard_report = check_spec(normalized, rules=effective_rules)
        t_guard_end = time.perf_counter()
        guard_errors = [c for c in guard_report.get("checks", []) if c.get("level") == "error"]
        do_compile = bool(prof["compile"])
        cache_enabled = True
        if not do_compile:
            compile_report = {"passed": True, "skipped": True, "warnings": [],
                              "slides": len(normalized.get("slides") or []), "file_bytes": None,
                              "reason": "spec_mode_no_compile", "output_exists": False,
                              "output_sha256": None}
            cache_reason = "not_compiled"
            timing = {"guard_ms": int((t_guard_end - t_guard_start) * 1000), "compile_ms": 0,
                      "attestation_ms": 0, "cache_reason": cache_reason,
                      "cache_enabled": cache_enabled, "cache_dir": None}
        elif guard_errors:
            compile_report = {"passed": False, "skipped": True, "warnings": [],
                              "slides": len(normalized.get("slides") or []), "file_bytes": None,
                              "reason": "engineering_gate", "output_exists": False,
                              "output_sha256": None}
            timing = {"guard_ms": int((t_guard_end - t_guard_start) * 1000), "compile_ms": 0,
                      "attestation_ms": 0, "cache_reason": "guard_error",
                      "cache_enabled": cache_enabled, "cache_dir": None}
        else:
            compile_report, timing = _compile_step(
                normalized, output_path, mode=prof["mode"], speed=speed,
                guard_errors=guard_errors, effective_rules=effective_rules,
                cache=cache_enabled, spec_path=str(build), image_bytes=snapshots,
                digests=digests, decode_seed=decoded, t_guard_start=t_guard_start)
        timing["provenance_required"] = bool(effective_rules.get("require_provenance", False))
        timing["total_ms"] = int((time.perf_counter() - t_guard_start) * 1000)
        timing["normalization"] = norm        # 归一化在编排层发生过一次，判定层只记录事实
        result = verdict(normalized, output_path, mode=mode, guard_report=guard_report,
                         compile_report=compile_report, speed=speed, runtime_facts=timing)
        normalized = result.pop("_effective_spec", normalized)
    result["run_id"] = run_id
    result["asset_workflow"] = workflow
    if asset_qc_result is not None:
        reuse_assets = asset_qc_result.get("reuse") or {}
        workflow["qc"] = {"status": asset_qc_result.get("status"),
                          "summary": asset_qc_result.get("summary"),
                          "pixel_profile": asset_qc_result.get("pixel_profile"),
                          # 判定是这一轮量出来的还是复用的，写在运行报告里（证据文件是
                          # 「何时量过」的记录，运行报告才是「这一轮做了什么」）。
                          "reuse": asset_qc_result.get("reuse")}
        evidence.identity("asset", manifest=asset_qc_result.get("manifest"),
                          manifest_sha256=asset_qc_result.get("manifest_sha256"),
                          assets=[{"asset_id": r.get("asset_id"),
                                   "witness": r.get("witness")}
                                  for r in (asset_qc_result.get("results") or [])])
        evidence.identity("qc", engine=asset_qc_result.get("qc_engine"),
                          phase=asset_qc_result.get("phase"),
                          schema=asset_qc_result.get("schema"),
                          pixel_profile=asset_qc_result.get("pixel_profile"))
        if reuse_assets.get("assets"):
            evidence.reuse("measure",
                           f"资产判定复用 {reuse_assets['assets']} 项（清单摘要 + 量像素引擎 + 取样参数 + 逐资产字节凭证一致）",
                           witness=reuse_assets.get("witness"))
        else:
            evidence.downgrade("measure", "资产判定本轮完整测量（无满足前提的复用凭证）")
    if result.get("normalization") is None:
        result["normalization"] = norm
    result.setdefault("execution", {})["reference_context"] = "none"
    result["execution"]["speed"] = speed
    if asset_binding is not None:
        result["asset_binding"] = asset_binding
        result["execution"]["asset_manifest"] = asset_binding["manifest"]
        result["execution"]["asset_binding"] = asset_binding["status"]

    compile_claim = result.get("compile") or {}
    if compile_claim.get("output_path"):
        evidence.identity("digest", pptx=str(compile_claim.get("output_path")),
                          witness={"size": compile_claim.get("file_bytes"),
                                   "mtime_ns": compile_claim.get("output_mtime_ns"),
                                   "sha256": compile_claim.get("output_sha256")})
        perf = result.get("performance") or {}
        if perf.get("compile_reused"):
            evidence.reuse("compile",
                           f"产物未重编（{perf.get('cache_reason') or 'cache_hit'}）："
                           "spec 投影 + 引擎指纹 + 产物凭证一致",
                           witness="spec_view + output_witness")
        else:
            evidence.downgrade("compile",
                               f"产物本轮重编（{perf.get('cache_reason') or '缓存未命中'}）")

    # 预览证据：release 自动出（方向与结构凭证），draft 只在显式要求时出。
    # 预算判断放在这里：核心判定已经完成，剩下的是可选证据。
    ghost = None
    preview_dir = preview or (str(output_path.with_name(output_path.stem + "_preview"))
                             if mode == "release" else None)
    ghost_ok = result.get("passed") and workflow["status"] != "BLOCKED"
    if preview_dir and ghost_ok:
        left = remaining()
        if left is not None and left < GHOST_MIN_BUDGET_S:
            defer("ghost_preview", f"剩余预算 {left:.1f}s < {GHOST_MIN_BUDGET_S:.0f}s")
            result["ghost_preview"] = None
        else:
            t_ghost = time.perf_counter()
            ghost = _ghost_cached(normalized, preview_dir, build.parent,
                                  output_sha=(result.get("compile") or {}).get("output_sha256"),
                                  image_bytes=snapshots, decoded=decoded,
                                  speed=speed, limit=ghost_pages)
            budget["ghost_ms"] = round((time.perf_counter() - t_ghost) * 1000, 2)
            result["ghost_preview"] = ghost
    elif preview_dir and not ghost_ok:
        defer("ghost_preview", "本轮判定未通过：不产出预览证据（避免给失败的稿子留视觉背书）")

    if ghost:
        hot_render = bool(ghost.get("reused"))
        evidence.identity("render", engine=ghost.get("engine"), renderer=ghost.get("renderer"),
                          scope=ghost.get("scope"), supersampled=ghost.get("supersampled"),
                          # 每一页像素的身份就是预览证据里已经记下的那份摘要，不再另算一遍
                          page_digests={Path(k).name: v
                                        for k, v in (ghost.get("file_sha256") or {}).items()})
        drawn, cached = int(ghost.get("pages_drawn") or 0), int(ghost.get("pages_from_cache") or 0)
        # 逐页出处必须区分「这一轮画的」与「上一轮留下的证据原本是怎么来的」：
        # 复用整份证据时，本轮一页都没画——把它记成本轮画了 4 页就是假账。
        page = {"count": ghost.get("count"), "of": ghost.get("page_count"),
                "drawn_numbers": [] if hot_render else (ghost.get("pages_drawn_numbers") or []),
                "reused_numbers": (ghost.get("pages_rendered") or []) if hot_render
                                  else (ghost.get("pages_reused_numbers") or []),
                "contact_sheet_cached": ghost.get("contact_sheet_cached")}
        if hot_render:
            page["produced_by"] = {"drawn": drawn, "from_cache": cached,
                                   "drawn_numbers": ghost.get("pages_drawn_numbers") or []}
        evidence.identity("page", **page)
        if hot_render:
            evidence.reuse("render", "整份预览证据复用（产物凭证 + 渲染器指纹一致）",
                           witness="output_sha256 + engine")
        elif cached and not drawn:
            evidence.reuse("render",
                           f"{cached} 页全部命中上一轮像素（页身份 = 画布 + 主题 + 页 + 尺度 + 渲染器指纹）",
                           witness="content_sha256(page_key)")
        else:
            evidence.downgrade("render", f"本轮真画 {drawn} 页（{cached} 页命中页缓存）")

    manifest = None
    if mode == "release":
        manifest = release_manifest(normalized, result, ghost_preview=ghost)
        if manifest["status"] == "BLOCKED" and result.get("passed"):
            errors = manifest["validation"]["issues"] or ["发布凭证无效"]
            from qa import fail_result
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

    budget["elapsed_s"] = round(time.perf_counter() - started, 3)
    budget["vao_total_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    # 读数只在这里汇总一次：耗时与计数都进事实容器（报告读出的是同一份数）。
    perf_now = dict(result.get("performance") or {})
    perf_now.update((result.get("compile") or {}).get("performance") or {})
    evidence.measure("guard_ms", perf_now.get("guard_ms"), stage="stage")
    evidence.measure("compile_ms", perf_now.get("compile_ms"), stage="stage")
    evidence.measure("attestation_ms", perf_now.get("attestation_ms"), stage="stage")
    evidence.measure("render_ms", budget.get("ghost_ms"), stage="stage")
    evidence.measure("slides", perf_now.get("slides"), stage="count")
    evidence.measure("speed", speed, stage="count")
    for key in ("image_transforms", "image_transform_reuses", "image_decode_reuses",
                "image_transform_ms", "save_ms", "package_ms", "media_entries_stored"):
        if key in perf_now:
            evidence.measure(key, perf_now[key], stage="count")
    evidence.finish()
    result["evidence"] = evidence.as_dict()
    if evidence.data["contract"] != "ok" and isinstance(result.get("warnings"), list):
        # 契约是工程事实：HOT 无凭证 / COLD 无原因都说明账本漏记，必须显式暴露。
        for issue in evidence.contract_issues():
            result.setdefault("warnings", []).append(f"[evidence] {issue}")
    result["budget"] = budget
    result.setdefault("performance", {})["vao_total_ms"] = budget["vao_total_ms"]
    packet_path = Path(packet).expanduser() if packet else output_path.with_suffix(".repair.json")
    packet_value = _repair_packet(result, mode, build, output_path)
    _json_write(packet_path, packet_value)
    if json_output:
        print(json.dumps(packet_value, ensure_ascii=False, indent=2, default=str))
    else:
        _print_verdict(result, ledger, ghost, manifest_path, packet_path,
                       asset_binding, speed, budget)
    binding_block = bool(asset_binding and (asset_binding.get("missing_asset_ids")
                                             or asset_binding.get("missing_files")))
    return result, (0 if result.get("passed") and not binding_block else 2)


def _print_verdict(result, ledger, ghost, manifest_path, packet_path,
                   asset_binding, speed, budget) -> None:
    """一次执行一条结论（含速度档与预览范围）：不让作者在读输出时猜发生了什么。"""
    print(f"VAO {result.get('execution', {}).get('mode')}: "
          f"{result.get('verdict', {}).get('verdict')} · {result.get('status')} · "
          f"{result.get('performance', {}).get('total_ms', 0)}ms · "
          f"speed={speed} · round {ledger.get('n')}/{ledger.get('budget')}")
    # 复用路径写在人类读的这一行上：这一轮是 HOT（没重做测量/编译/渲染）还是 COLD、
    # 为什么必须重做——不必去翻证据字典才知道「为什么可以复用」。
    evidence = result.get("evidence") or {}
    path_kind = str(evidence.get("path") or "").upper()
    if path_kind == "NONE":
        # 第三種結局：这一轮没有产物，复用无从谈起——不拿性能语言掩盖失败。
        print(f"  复用路径: 未成立 · 本轮 BLOCKED（{evidence.get('blocked_reason') or '未通过核验'}）")
    elif path_kind == "HOT":
        print(f"  复用路径: HOT · measure/compile/render 全部复用"
              f"（{len(evidence.get('reuse') or [])} 条凭证，contract {evidence.get('contract')}）")
    elif path_kind:
        why = "；".join(f"{c.get('step')} {c.get('reason')}"
                        for c in evidence.get("cold_reasons") or [])
        print(f"  复用路径: COLD · {why or '本轮重新建立事实'}")
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
        scope = ghost.get("scope")
        label = (f"{ghost['count']} 页 ghost" if scope == "full"
                 else f"{ghost['count']}/{ghost.get('page_count', '?')} 页方向采样")
        print(f"  preview: {label} → {ghost['contact_sheet'] or ghost['dir']}{suffix}")
    for item in budget.get("skipped") or []:
        print(f"  defer[{item['stage']}]: {item['reason']}")
    if manifest_path:
        print(f"  manifest: {manifest_path}")
    print(f"  repair packet: {packet_path}")


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
                        speed=getattr(args, "speed", DEFAULT_SPEED),
                        deadline=getattr(args, "deadline", DEFAULT_DEADLINE),
                        ghost_pages=getattr(args, "ghost_pages", DEFAULT_GHOST_PAGES),
                        )
    return code


SPEED_PROFILES = {
    "fast": ("两分钟交付档：像素统计降采样、图片只读一次、同图只变换一次、"
             "预览按方向采样、缓存快探、单次产物哈希"),
    "strict": ("严格档：全分辨率 QC、整包缓存核对、全 deck 逐页预览、逐张图片独立变换"),
}
DEFAULT_SPEED = "fast"
DEFAULT_DEADLINE = 120.0          # 本次调用可用的墙钟预算（秒）；0 / None 表示不设上限
DEFAULT_GHOST_PAGES = 24          # 快速档方向采样页数上限（≤24 页自动全量；PIL 全量渲染 ~2s，
                                  # 实测 15 页 deck 采样 4 页迫使作者另跑一次 strict = 纯调用浪费）


def _add_speed_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--speed", choices=tuple(SPEED_PROFILES), default=DEFAULT_SPEED,
                        help="fast（默认）= 两分钟交付档；strict = 全量证据档")
    parser.add_argument("--deadline", type=float, default=DEFAULT_DEADLINE,
                        help="本次调用墙钟预算（秒，默认 120）；预算不足时跳过可选证据阶段并留痕")
    parser.add_argument("--ghost-pages", type=int, default=DEFAULT_GHOST_PAGES,
                        help="方向预览采样页数上限（fast 档；页数不超过它时自动全量）")


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
    a.add_argument("--show-prompts", action="store_true",
                   help="print full prompt/negative text; default output stays compact")
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
    _add_speed_flags(c)

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
    _add_speed_flags(r)

    v = sub.add_parser("preview", help="spec/build → ghost contact sheet (PIL only)")
    v.add_argument("build")
    v.add_argument("--out", default="vao_preview")
    v.add_argument("--pages", help="1-based pages, e.g. 1,3,8（默认：全部页）")
    v.add_argument("--speed", choices=("fast", "strict"), default="fast",
                   help="fast 用低压缩编码与单倍采样（更快出图，判断力不变）")
    v.add_argument("--assets-manifest", help="bind image elements carrying asset_id")
    v.add_argument("--assets-dir", help="directory containing generated manifest filenames")

    d = sub.add_parser("dna", help="design memory: --check store / --add one entry")
    d.add_argument("--add", help="append one DNA entry from a JSON file")
    d.add_argument("--replace", action="store_true", help="with --add: overwrite same-id entry")
    d.add_argument("--check", action="store_true", help="validate the store (default action)")
    d.add_argument("--json", action="store_true")

    m = sub.add_parser("make", help="Compatibility alias → check (single production contract)")
    m.add_argument("build")
    m.add_argument("output", nargs="?", default="deck.pptx")
    m.add_argument("--assets-manifest", default=None, help="asset manifest; default: sibling asset_manifest.json")
    m.add_argument("--assets-dir", default=None, help="assets directory recorded by the manifest")
    m.add_argument("--preview", default="preview", help="preview output directory")
    m.add_argument("--mode", choices=("draft", "release"), default="release")
    _add_speed_flags(m)

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


def _make(args) -> int:
    """Compatibility alias for the one reliable production path.

    ``make`` used to duplicate binding, guard, compile and ghost logic and could
    release image decks without the manifest/QC chain. Keep the friendly command,
    but delegate everything to ``check`` so there is only one execution contract.
    """
    build_file = Path(args.build).expanduser().resolve()
    if not build_file.is_file():
        print(f"VAO make: error · build file not found: {args.build}", file=sys.stderr)
        return 2
    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = build_file.parent / output
    manifest = getattr(args, "assets_manifest", None)
    if manifest is None:
        sibling = build_file.parent / "asset_manifest.json"
        manifest = str(sibling) if sibling.is_file() else None
    _, code = run_check(
        str(build_file), str(output), mode=args.mode,
        preview=getattr(args, "preview", None),
        assets_manifest=manifest,
        assets_dir=getattr(args, "assets_dir", None),
        speed=getattr(args, "speed", "fast"),
        deadline=getattr(args, "deadline", None),
    )
    return code

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
                    print(f"asset cards: {len(gen_items)} generated · prompts stored in {args.out}")
                    for idx, a in enumerate(gen_items, 1):
                        sid = ",".join(a.get("slide_ids", []))
                        role = a.get("asset_role") or a.get("asset_type") or "?"
                        function = a.get("asset_function") or "?"
                        print(f"  [{idx}/{len(gen_items)}] {sid} → {a.get('asset_id')} "
                              f"{role}/{function} {a.get('ratio', '16:9')}")
                    if args.show_prompts:
                        print("-" * 60)
                        print("  full prompt cards")
                        print("-" * 60)
                        for a in gen_items:
                            print(f"[{','.join(a.get('slide_ids', []))}] {a.get('asset_id')}\n"
                                  f"  Prompt: {a.get('prompt', '')}\n"
                                  f"  Negative: {a.get('negative', '')}")
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
                                speed=args.speed, deadline=args.deadline,
                                ghost_pages=args.ghost_pages,
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
            info = _ghost(spec, args.out, pages, base_path=Path(args.build).expanduser().resolve().parent,
                          speed=args.speed)
            if binding:
                info["asset_binding"] = binding
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 2 if binding and binding["status"] == "BLOCK" else 0
        if args.command == "make":
            return _make(args)
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
