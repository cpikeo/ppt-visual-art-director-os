#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PPT Visual Art Director OS contract smoke tests."""
from __future__ import annotations
import importlib.util, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REFS = ROOT / "references"
SCRIPTS = ROOT / "scripts"
REQUIRED_REFS = {"design-intelligence.md", "design-system.md", "evidence-library.md", "themes.md", "production-contract.md"}
REQUIRED_SCRIPTS = {"compiler.py", "charts.py", "elements.py", "primitives.py", "guard.py", "render_check.py", "qa.py", "asset_prompt.py", "art_critic.py"}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_structure():
    missing = sorted([f for f in REQUIRED_REFS if not (REFS / f).exists()] + [f for f in REQUIRED_SCRIPTS if not (SCRIPTS / f).exists()])
    return {"status": "PASS" if not missing else "FAIL", "missing": missing}


def check_critic_with_render():
    """端到端 mock 渲染证据：5 维消费渲染证据的路径必须有 evidence 输出。
    防住"加了渲染证据消费代码但实际没生效"或"字段名漂移"等契约漂移。"""
    mod = load("art_critic", SCRIPTS / "art_critic.py")
    spec = {"direction": {"continuity_token": "tok",
                          "color_intent": ["brand", "emotion", "hierarchy"],
                          "composition_grammar": "evidence_field",
                          "background_scene": "cinematic"},
            "theme": {"colors": {"background": "#1B1B1B", "primary": "#FFFFFF",
                                 "accent": "#B23A2F", "ink": "#FFFFFF",
                                 "muted": "#888888", "secondary": "#CCCCCC"},
                      "constraints": {"accent_max": 0.05}},
            "slides": [{
                "id": "s01",
                "page_intent": {"insight": "测试页", "focus": "h",
                                "reading_order": ["conclusion"],
                                "energy": "high", "density": "sparse",
                                "empty_space_role": "create_authority",
                                "page_family": "HERO", "rhythm_stage": "opening",
                                "continuity_token": "tok"},
                "elements": [
                    {"type": "text", "id": "h", "x": 48, "y": 200, "width": 900,
                     "height": 200, "text": "X", "size": 56, "color": "ink",
                     "bold": True},
                ],
            }]}
    # 完整 mock：每个消费字段都给一个能触发 evidence 的值
    render = {"rendered": True, "pages": [{
        "brightness": 0.20,            # cinematic + 暗 → emotional_impact +1
        "saturated_pixel_ratio": 0.03,
        "edge_kurtosis_x": 5.5,        # 视觉对齐清晰 → alignment +1
        "edge_kurtosis_y": 6.2,
        "accent_pixel_ratio": 0.04,    # ≤ 主题 0.05 → contrast +1
        "gravity_drift": 0.05,         # 漂移小 → balance +1
        "saliency_split_lr": 0.1,
        "saliency_split_tb": 0.05,
        "occupancy": 0.30,             # sparse 健康 → rhythm 不触发
        "margin_occupancy": 0.02,
    }]}
    out = mod.critique_deck(spec, render_evidence=render)
    evs = out["slides"][0]["dimension_evidence"]
    consumed_dims = ("visual_hierarchy", "balance", "alignment", "contrast",
                     "rhythm", "emotional_impact")
    evidence_count = {d: len(evs.get(d, [])) for d in consumed_dims}
    # 至少 4 维应有 evidence（rhythm 健康时无 evidence 是设计正确行为）
    present = sum(1 for d in consumed_dims if evs.get(d))
    deck_avg_ok = all(d in out["deck_notes"]["dimension_averages"]
                      for d in mod.DIMENSIONS)
    fix_hint_ok = (not out["deck_notes"].get("systemic_weaknesses")
                   or all("fix_hint" in w
                          for w in out["deck_notes"]["systemic_weaknesses"]))
    ok = present >= 4 and deck_avg_ok and fix_hint_ok
    return {"status": "PASS" if ok else "FAIL",
            "consumed_dims_with_evidence": present,
            "evidence_per_dim": evidence_count,
            "dimension_averages_keys": list(out["deck_notes"]["dimension_averages"].keys()),
            "fix_hint_present": fix_hint_ok}


def check_templates_yaml():
    """防 YAML 回归：strategy_direction.yml 必须被严格 yaml.safe_load 解析成功。
    宽容解析（PyYAML 默认某些版本）能通过，但 CI 的 linter / 严格加载会拒绝
    ——这是 2024-09 上一轮精修遗留的脆弱点。"""
    try:
        import yaml
    except ImportError:
        return {"status": "SKIP", "reason": "PyYAML not installed"}
    path = ROOT / "templates" / "strategy_direction.yml"
    try:
        with open(path, encoding="utf-8") as f:
            tpl = yaml.safe_load(f)
    except Exception as exc:
        return {"status": "FAIL", "error": f"strict yaml.safe_load failed: {exc}"}
    if not isinstance(tpl, dict):
        return {"status": "FAIL", "error": "top-level must be a mapping"}
    rm = tpl.get("required_minimum")
    if not isinstance(rm, dict) or not rm:
        return {"status": "FAIL", "error": "required_minimum 块缺失或为空"}
    # 关键字段必须存在（即使值为空字符串）
    for k in ("strategy.audience", "slides[].page_intent.insight",
              "slides[].page_intent.focus", "slides[].source_zone.x"):
        if k not in rm:
            return {"status": "FAIL", "error": f"required_minimum 缺少关键字段 {k}"}
    return {"status": "PASS", "required_minimum_keys": len(rm)}


def check_references():
    names = {p.name for p in ROOT.rglob("*") if p.is_file()}
    refs = set()
    # 同时扫描文档与脚本（docstring/注释里的引用同样必须可解析）
    docs = list(ROOT.rglob("*.md")) + sorted(SCRIPTS.glob("*.py"))
    allow_missing = {"build_mydeck.py", "build_module.py", "build_card.py", "build_page.py"}
    for doc in docs:
        refs.update(re.findall(r"[\w./-]+\.(?:md|py)", doc.read_text(encoding="utf-8")))
    missing = sorted({r.split("/")[-1] for r in refs if ".." not in r and r.split("/")[-1] not in names and r.split("/")[-1] not in allow_missing})
    return {"status": "PASS" if not missing else "FAIL", "missing": missing}


def check_critic():
    mod = load("art_critic", SCRIPTS / "art_critic.py")
    spec = {"slides": [{"id": "s01", "page_intent": {"insight": "A", "focus": "title", "density": "sparse"}, "elements": [{"type": "text", "id": "title"}]}]}
    spec["slides"][0]["elements"] += [{"type": "shape", "shape": "rounded_rect", "id": f"card{i}"} for i in range(5)]
    out = mod.critique_deck(spec, {"rendered": True, "pages": [{"gravity_drift": 0.0, "accent_pixel_ratio": 0.01}]})
    required = {"critic_version", "deck_score", "status", "slides", "hard_gates", "deck_notes"}
    observations = " ".join(out["slides"][0]["observations"])
    ok = required <= set(out) and len(out["slides"]) == 1 and "卡片墙" in observations
    ok = ok and "dimension_evidence" in out["slides"][0]
    ok = ok and any(g.get("code") == "CARD_WALL" for g in out["hard_gates"])
    return {"status": "PASS" if ok else "FAIL", "status_value": out.get("status"),
            "card_wall_detected": "卡片墙" in observations,
            "gates": [g.get("code") for g in out["hard_gates"]]}


def check_critic_pass_reachable():
    """v2 回归：合规且精致的 deck 必须能拿到 >=90 并 PASS（v1 封顶 ~78，PASS 不可达）。"""
    mod = load("art_critic", SCRIPTS / "art_critic.py")
    slides = []
    for i in range(2):
        slides.append({
            "id": f"s{i:02d}",
            "page_intent": {"insight": f"结论 {i}", "focus": f"t{i}",
                            "reading_order": ["conclusion", "source"],
                            "energy": "low" if i == 0 else "medium",
                            "density": "sparse" if i == 0 else "balanced",
                            "empty_space_role": "protect_focus" if i == 0 else "hold_emotion",
                            "page_family": "MINIMAL_STATEMENT", "rhythm_stage": "opening",
                            "continuity_token": "tok"},
            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
            "elements": [
                {"type": "text", "id": f"t{i}", "x": 48, "y": 48, "width": 720, "height": 96,
                 "text": f"洞察标题 {i}", "size": 44, "color": "ink", "bold": True,
                 "line_height": 1.15, "max_lines": 2, "padding": 0},
                {"type": "text", "id": f"b{i}", "x": 48, "y": 216, "width": 640, "height": 64,
                 "text": "正文两行说明", "size": 20, "color": "secondary",
                 "line_height": 1.4, "max_lines": 2, "padding": 0},
                {"type": "text", "id": f"src{i}", "role": "source", "x": 48, "y": 672,
                 "width": 480, "height": 32, "text": "来源：自检", "size": 12,
                 "color": "muted", "line_height": 1.3, "max_lines": 1, "padding": 0},
            ]})
    spec = {"direction": {"continuity_token": "tok",
                          "color_intent": ["brand", "emotion", "hierarchy"],
                          "composition_grammar": "strict_grid",
                          "background_scene": "solid_world"},
            "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111",
                                 "muted": "#555555", "accent": "#0B5FFF",
                                 "primary": "#111111", "surface": "#F5F5F5",
                                 "secondary": "#666666"}},
            "slides": slides}
    out = mod.critique_deck(spec, {"rendered": True, "pages": [
        {"gravity_drift": 0.05, "accent_pixel_ratio": 0.01},
        {"gravity_drift": 0.04, "accent_pixel_ratio": 0.01}]})
    ok = out["deck_score"] >= 90 and out["status"] == "PASS" and not out["hard_gates"]
    return {"status": "PASS" if ok else "FAIL", "deck_score": out["deck_score"],
            "status_value": out["status"], "critic_version": out["critic_version"]}


def check_render_metrics():
    """渲染证据 v1.1：锚点解析以声明意图优先；主题色 Accent 测量可用。"""
    import tempfile
    from PIL import Image
    mod = load("render_check", SCRIPTS / "render_check.py")
    slide = {"id": "s01", "page_intent": {"focus": "kpi", "insight": "A"},
             "gravity_anchor": None,
             "elements": [
                 {"type": "chart", "id": "kpi", "x": 500, "y": 250, "width": 280, "height": 180},
                 {"type": "text", "id": "title", "x": 48, "y": 48, "width": 300, "height": 80}]}
    source, anchor = mod.resolve_anchor(slide, 1280, 720)
    ok = source == "focus" and anchor["element"]["id"] == "kpi"
    slide2 = {"id": "s02", "page_intent": {"insight": "A",
                                           "gravity_anchor": {"x": 0.25, "y": 0.5, "radius": 0.1}},
              "elements": [{"type": "text", "id": "t", "x": 48, "y": 48, "width": 300, "height": 80}]}
    source2, anchor2 = mod.resolve_anchor(slide2, 1280, 720)
    ok = ok and source2 == "gravity_anchor" and abs(anchor2["x"] - 320) < 1
    with tempfile.TemporaryDirectory() as td:
        png = pathlib.Path(td) / "page.png"
        img = Image.new("RGB", (640, 360), (255, 255, 255))
        for x in range(320, 640):
            for y in range(180, 360):
                img.putpixel((x, y), (11, 95, 255))  # 主题 accent #0B5FFF 大色块
        img.save(png)
        m = mod.measure_image(png, accent_hex="#0B5FFF")
        ok = ok and m["accent_method"] == "theme" and 0.20 < m["accent_pixel_ratio"] < 0.30
        ok = ok and "saliency_split_lr" in m and "margin_occupancy" in m
        m2 = mod.measure_image(png)
        ok = ok and m2["accent_method"] == "saturation"
    return {"status": "PASS" if ok else "FAIL",
            "accent_ratio": m.get("accent_pixel_ratio"),
            "anchor_sources": [source, source2]}


def check_fill_contract():
    mod = load("elements", SCRIPTS / "elements.py")
    standard = mod.normalize_fill({"type": "solid", "color": "#ffffff", "opacity": 0.3})
    legacy = mod.normalize_fill({"color": "#ffffff", "opacity": 0.3})
    transparent = mod.normalize_fill({"type": "none"})
    invalid_message = ""
    try:
        mod.normalize_fill({"opacity": 0.3})
    except ValueError as exc:
        invalid_message = str(exc)
    ok = (standard["type"] == "solid" and legacy == standard and
          transparent["type"] == "none" and "Expected" in invalid_message)
    return {"status": "PASS" if ok else "FAIL", "legacy_migrated": legacy == standard, "invalid_is_explicit": bool(invalid_message)}


def check_imports():
    try:
        for name in ("primitives", "guard", "compiler", "art_critic"):
            load(name, SCRIPTS / f"{name}.py")
        return {"status": "PASS"}
    except Exception as exc:
        return {"status": "FAIL", "error": repr(exc)}


def check_pipeline():
    """端到端冒烟：真实编译两页 mini deck 并跑完整 QA（不依赖渲染环境）。"""
    import tempfile
    qa_mod = load("qa", SCRIPTS / "qa.py")

    def page(sid, title_y):
        return {
            "id": sid,
            "page_intent": {"insight": "一页一句可复述结论", "focus": f"{sid}_title",
                            "reading_order": ["conclusion", "source"], "energy": "low",
                            "density": "sparse", "empty_space_role": "protect_focus",
                            "page_family": "MINIMAL_STATEMENT", "rhythm_stage": "opening",
                            "continuity_token": "smoke-token"},
            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
            "elements": [
                {"type": "text", "id": f"{sid}_title", "x": 48, "y": title_y,
                 "width": 720, "height": 64, "text": "单一、可复述的页面结论",
                 "size": 32, "color": "ink", "bold": True, "line_height": 1.15,
                 "max_lines": 2, "padding": 0},
                {"type": "text", "id": f"{sid}_source", "role": "source",
                 "x": 48, "y": 672, "width": 480, "height": 32, "text": "来源：自检",
                 "size": 12, "color": "muted", "line_height": 1.3, "max_lines": 1, "padding": 0},
            ],
        }

    spec = {"canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},
            "theme": {"colors": {"background": "#FFFFFF", "surface": "#F5F5F5",
                                  "primary": "#111111", "secondary": "#666666",
                                  "accent": "#0B5FFF", "ink": "#1A1A1A", "muted": "#777777"},
                      "fonts": {"cn": "Microsoft YaHei", "latin": "Arial"}},
            "slides": [page("s01", 48), page("s02", 96)]}
    result = {"status": "FAIL"}
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "smoke.pptx"
        r = qa_mod.run_qa(spec, out, render=False)
        bad = {"OVERLAP", "SOURCE_COLLISION", "GUARD_FAIL", "COMPILE_FAIL", "DATA_INTEGRITY_FAIL"}
        ok = (out.exists() and out.stat().st_size > 0
              and r["status"] == "PREVIEW_ONLY" and r["blocking_items"] == 0
              and not bad & set(r["failure_codes"])
              and bool(r["compile"]["passed"]))
        manifest = qa_mod.release_manifest(spec, r, {"status": r["status"]})
        ok = ok and manifest["status"] == "PREVIEW_ONLY" and manifest["slide_count"] == 2 \
            and len(manifest["source_spec_hash"]) == 16
        result = {"status": "PASS" if ok else "FAIL", "qa_status": r["status"],
                  "codes": r["failure_codes"], "manifest_status": manifest["status"]}
    return result


def check_preflight_sync():
    """guard 预检与 art_critic 必须共用阈值，并提前点名同一批硬门槛。"""
    guard = load("guard", SCRIPTS / "guard.py")
    crit = load("art_critic", SCRIPTS / "art_critic.py")
    gates, source = guard._preflight_gates()
    synced = all(gates[k] == getattr(crit, k) for k in
                 ("STATEMENT_SIZE", "FOCUS_LEAD", "MEDIA_BUDGET_MAX", "TEXT_BUDGET_MAX",
                  "FOCUS_AREA_LEAD", "LR_SPLIT_MAX", "AXIS_TOLERANCE", "AXIS_LINES",
                  "GOLDEN_LINES"))

    def page(sid, intent, els):
        return {"id": sid, "page_intent": intent, "elements": els}

    def statement(size, sid="t"):
        return {"type": "text", "id": sid, "x": 96, "y": 200, "width": 608, "height": 40,
                "size": size, "text": "标题", "color": "ink"}

    cards = [{"type": "shape", "shape": "rounded_rect", "id": f"c{i}", "x": 96,
              "y": 300 + i * 48, "width": 400, "height": 40} for i in range(5)]
    spec = {"canvas": {"width": 1280, "height": 720}, "direction": {}, "slides": [
        # s01：focus 指向不存在的元素 + 无 insight
        page("s01", {"focus": "missing", "density": "sparse", "energy": "low"},
             [statement(24)] + cards),
        # s02：focus 有效但尺度低于 Statement 线；与前一页同密度
        page("s02", {"focus": "t", "density": "sparse", "energy": "low"},
             [statement(24)] + cards)]}
    out = guard.check_spec(spec)
    codes = {i["code"] for i in out.get("preflight") or []}
    per_slide: dict = {}
    for i in out.get("preflight") or []:
        per_slide.setdefault(i["slide"], set()).add(i["code"])
    want = {"INTENT_UNCLEAR", "FOCUS_UNBOUND", "FOCUS_SCALE", "CARD_WALL", "DENSITY_FLAT"}
    # 阈值同源 + 五类门槛全部提前点名，且两类 focus 判定落在各自正确的页面上
    ok = (source == "art_critic" and synced and want <= codes
          and {"INTENT_UNCLEAR", "FOCUS_UNBOUND"} <= per_slide.get("s01", set())
          and "FOCUS_SCALE" in per_slide.get("s02", set()))
    return {"status": "PASS" if ok else "FAIL", "gate_source": source,
            "thresholds_synced": synced, "codes": sorted(codes)}


def check_background_layer():
    """整幅画心 + 文字直接叠加：静态预检放行，编译器把背景层置底并补内容保护层。"""
    import tempfile
    from pptx import Presentation
    from PIL import Image
    guard = load("guard", SCRIPTS / "guard.py")
    comp = load("compiler", SCRIPTS / "compiler.py")
    img = pathlib.Path(tempfile.mkdtemp()) / "bg.png"
    Image.new("RGB", (320, 180), (238, 238, 238)).save(img)
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                        "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"}}
    spec = {"canvas": {"width": 1280, "height": 720}, "theme": theme, "slides": [{
        "id": "s01", "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
        "page_intent": {"insight": "A", "focus": "t", "density": "sparse", "energy": "high",
                        "empty_space_role": "hold_emotion"},
        "elements": [
            {"type": "text", "id": "t", "x": 96, "y": 288, "width": 1088, "height": 144,
             "size": 64, "text": "结论", "color": "ink", "max_lines": 1, "line_height": 1.1,
             "padding": 0},
            {"type": "text", "id": "src", "x": 48, "y": 672, "width": 640, "height": 32,
             "size": 12, "text": "来源", "color": "muted", "role": "source", "max_lines": 2,
             "line_height": 1.3, "padding": 0},
            {"type": "image", "id": "bg", "layer": "background", "src": str(img), "x": 0,
             "y": 0, "width": 1280, "height": 720, "asset_function": "hero",
             "overlay": {"type": "solid", "color": "#FFFFFF", "opacity": 0.5}}]}]}
    g = guard.check_spec(spec)
    clash = [c for c in g["checks"] if c["rule"] in ("overlap", "source_zone")]
    unprotected = [c for c in g["checks"] if "BG_UNPROTECTED" in str(c["id"])]
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "t.pptx"
        rep = comp.compile_deck(spec, out, checks=False)
        names = [sh.name for sh in Presentation(str(out)).slides[0].shapes]
    ok = (not clash and not unprotected and rep["passed"]
          and names[:2] == ["bg", "bg__protection"] and "t" in names)
    return {"status": "PASS" if ok else "FAIL", "clash": len(clash), "z_order": names[:3],
            "compile_warnings": rep["warnings"][:2]}


def check_route_layer():
    """决策层：内容类型 → 家族/密度/素材闸门；快速路径不出图，发布路径才出图。"""
    route = load("route", SCRIPTS / "route.py")
    fast = route.plan_page("data", "quiet_minimal", "fast")
    cover = route.plan_page("封面：年度总结", "editorial_brand", "advanced")
    deck = route.plan_deck({"occasion": "内部汇报",
                           "slides": ["封面 年度总结", "数据趋势", "图表占比",
                                      "结论判断", "请求决定"]})
    dens = [p["density"] for p in deck["pages"]]
    clash = any(dens[i] == dens[i - 1] for i in range(1, len(dens)))
    ok = (fast["page_family"] == "DATA_STORY" and fast["asset"]["decision"] == "none"
          and cover["content_type"] == "cover" and cover["asset"]["decision"] == "required"
          and deck["path"] == "fast" and deck["budget"]["max_asset_calls"] == 2
          and not clash and dens[0] == "sparse" and dens[-1] == "sparse")
    return {"status": "PASS" if ok else "FAIL", "fast_asset": fast["asset"]["decision"],
            "density_curve": dens, "path": deck["path"]}


def check_qa_performance_keys():
    """QA 必须回报分阶段耗时与预检条目数；预检 hint 不得二次扣分。"""
    import tempfile
    qa = load("qa", SCRIPTS / "qa.py")
    spec = {"canvas": {"width": 1280, "height": 720},
            "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111",
                                 "muted": "#777777", "primary": "#222222",
                                 "secondary": "#333333", "accent": "#AA0000"}},
            "slides": [{"id": "s01",
                        "page_intent": {"insight": "结论", "focus": "t", "density": "sparse",
                                        "energy": "high", "empty_space_role": "hold_emotion"},
                        "elements": [{"type": "text", "id": "t", "x": 96, "y": 200,
                                      "width": 608, "height": 112, "size": 48,
                                      "text": "结论", "color": "ink", "max_lines": 1,
                                      "line_height": 1.2, "padding": 0}]}]}
    with tempfile.TemporaryDirectory() as d:
        r = qa.run_qa(spec, pathlib.Path(d) / "t.pptx", render=False)
    perf = r.get("performance") or {}
    keys = {"total_ms", "guard_ms", "compile_ms", "render_ms", "slides", "preflight_items",
            "render_skipped"}
    ok = (keys <= set(perf) and (r.get("preflight") or {}).get("items") is not None
          and qa.DEFAULT_PENALTIES.get("preflight_hint") == 0.0
          and "preflight_gate" in r and perf["slides"] == 1)
    return {"status": "PASS" if ok else "FAIL",
            "perf": {k: perf.get(k) for k in ("guard_ms", "compile_ms", "render_ms")}}


def check_progressive_qa():
    """Progressive QA：L1 不渲染 / L2 只测关键页且不可发布 / L3 全量；并行度硬上限 2。"""
    import tempfile
    from PIL import Image
    qa = load("qa", SCRIPTS / "qa.py")
    rc = load("render_check", SCRIPTS / "render_check.py")
    route = load("route", SCRIPTS / "route.py")
    art = load("art_critic", SCRIPTS / "art_critic.py")

    # 并行度：禁止无限并发（soffice + poppler 已接近吃满 2 核）
    capped = (rc.MAX_RENDER_WORKERS == 2 and rc._clamp_workers(64) <= 2
              and rc._clamp_workers(0) >= 1)
    # 分块：连续页压成区间，再按 worker 数二分，避免一个 worker 空转
    runs, workers = rc._plan_jobs([1, 2, 3, 4, 7, 8], 2)
    ok_runs = all(a <= b for a, b in runs) and workers <= 2 and sum(
        b - a + 1 for a, b in runs) == 6

    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                        "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"}}
    tmp = tempfile.mkdtemp()
    img = pathlib.Path(tmp) / "m.png"
    Image.new("RGB", (320, 180), (236, 236, 236)).save(img)

    def page(sid, y, els):
        return {"id": sid, "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 40},
                "page_intent": {"insight": f"{sid} 结论", "focus": "st", "density": "sparse",
                                "energy": "high", "empty_space_role": "hold_emotion"},
                "elements": [{"type": "text", "id": "st", "x": 400, "y": y, "width": 480,
                              "height": 120, "size": 48, "text": f"{sid} statement",
                              "color": "ink", "max_lines": 1, "line_height": 1.2,
                              "padding": 0}] + els}

    spec = {"canvas": {"width": 1280, "height": 720}, "theme": theme, "slides": [
        page("s01", 300, []),
        page("s02", 300, []),
        page("s03", 470, [{"type": "image", "id": "media", "src": str(img), "x": 400,
                           "y": 150, "width": 480, "height": 250,
                           "asset_function": "context"}]),
        page("s04", 300, [])]}

    picked = qa.key_pages(spec)
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "prog.pptx"
        r1 = qa.run_qa(spec, out, render_dir=pathlib.Path(d) / "r1", qa_level=1, dpi=60)
        r2 = qa.run_qa(spec, out, render_dir=pathlib.Path(d) / "r2", qa_level=2, dpi=60)
        r3 = qa.run_qa(spec, out, render_dir=pathlib.Path(d) / "r3", qa_level=3, dpi=60)
        c2 = art.critique_deck(spec, r2.get("render_evidence"))
    cov2 = (r2.get("render") or {}).get("coverage") or {}
    # 子集渲染必须按绝对页码对齐，不能把 s01 的指标串到 s02 上
    aligned = [p["index"] for p in (r2.get("render_evidence") or {}).get("pages") or []]
    ids = [p["slide"] for p in (r2.get("render_evidence") or {}).get("pages") or []]
    ok = (capped and ok_runs
          and r1["performance"]["render_skipped"] and r1["render"]["pages"] == 0
          and r1["status"] in ("PREVIEW_ONLY", "REVISE", "BLOCKED")
          and picked == [1, 3, 4] and r2["render"]["pages"] == 3
          and cov2.get("total_pages") == 4 and not r2["release_eligible"]
          and r2["status"] != "PASS" and aligned == [0, 2, 3] and ids == ["s01", "s03", "s04"]
          and r3["render"]["pages"] == 4 and r3["release_eligible"]
          and any(g.get("code") == "PIXEL_COVERAGE_PARTIAL" for g in c2["hard_gates"])
          and c2["deck_notes"]["pixel_coverage"]["rendered_pages"] == 3
          and "iteration_level" in route.plan_deck({"slides": ["封面 x"]})["verification"])
    return {"status": "PASS" if ok else "FAIL", "key_pages": picked,
            "l2_pages": r2["render"]["pages"], "l2_indices": aligned,
            "workers_cap": rc._clamp_workers(64), "planned_runs": runs,
            "l3_eligible": r3["release_eligible"], "statuses": [r1["status"], r2["status"],
                                                                 r3["status"]]}


def check_decision_cache():
    """决策缓存：同 brief 命中、结果确定性、调用方改动不回写缓存（修订循环不重复推导）。"""
    route = load("route", SCRIPTS / "route.py")
    brief = {"occasion": "内部汇报", "audience": "管理层",
             "slides": ["封面：季度总结", "数据：三条趋势", "对比 A vs B", "结论判断"]}
    route.clear_cache()
    a = route.plan_deck(brief)
    b = route.plan_deck(brief)
    import json
    key_a = json.dumps(a, sort_keys=True, default=str)
    key_b = json.dumps(b, sort_keys=True, default=str)
    a["pages"][0]["density"] = "MUTATED"
    c = route.plan_deck(brief)
    st = route.cache_stats()
    ok = (key_a == key_b and c["pages"][0]["density"] != "MUTATED"
          and st["hits"] >= 2 and st["misses"] == 1 and st["size"] <= st["max"]
          and route._quality("premium") == "advanced" and route._quality("quick") == "fast"
          and route._quality("nonsense") == "fast"
          and route.plan_page("data", "quiet_minimal", "premium")["asset"]["decision"] == "none")
    route.clear_cache()
    return {"status": "PASS" if ok else "FAIL", "stats": st,
            "premium_path": route.plan_deck({**brief, "quality_level": "premium"})["mode"]}


def check_render_cache():
    """渲染证据缓存：命中即免进程复用、改一页只重测一页、证据 PNG 仍可复核。"""
    import copy
    import tempfile
    import time
    rc = load("render_check", SCRIPTS / "render_check.py")
    comp = load("compiler", SCRIPTS / "compiler.py")
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                        "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"}}

    def page(sid, y):
        return {"id": sid, "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 40},
                "page_intent": {"insight": f"{sid} 结论", "focus": "st", "density": "sparse",
                                "energy": "high", "empty_space_role": "hold_emotion"},
                "elements": [{"type": "text", "id": "st", "x": 400, "y": y, "width": 480,
                              "height": 120, "size": 48, "text": f"{sid} statement",
                              "color": "ink", "max_lines": 1, "line_height": 1.2,
                              "padding": 0}]}

    spec = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
            "slides": [page("s01", 300), page("s02", 300)]}
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "cache.pptx"
        work = pathlib.Path(d) / "render"
        comp.compile_deck(spec, out, checks=False)
        cold = rc.render_evidence(out, spec, work, dpi=48)
        t = time.time()
        warm = rc.render_evidence(out, spec, work, dpi=48)
        warm_ms = (time.time() - t) * 1000
        spec2 = copy.deepcopy(spec)
        spec2["slides"][1]["elements"][0]["y"] = 420
        comp.compile_deck(spec2, out, checks=False)
        inc = rc.render_evidence(out, spec2, work, dpi=48)
        entries = json.loads((work / rc.RENDER_CACHE_NAME).read_text(encoding="utf-8"))["entries"]
        pngs_kept = all((work / e["png"]).exists() for e in entries.values() if e.get("png"))
        metrics_same = all(abs(a[k] - b[k]) < 1e-9
                           for a, b in zip(cold["pages"], warm["pages"])
                           for k in ("occupancy", "brightness", "gravity_drift"))
    ok = (cold["rendered"] and cold["coverage"]["cache_misses"] == 2
          and warm["rendered"] and warm["coverage"]["cache_hits"] == 2
          and warm["coverage"]["cache_misses"] == 0 and warm["coverage"]["workers"] == 0
          and warm_ms < 900 and all(p.get("cached") for p in warm["pages"])
          and inc["coverage"]["cache_hits"] == 1 and inc["coverage"]["cache_misses"] == 1
          and [p["slide"] for p in inc["pages"]] == ["s01", "s02"]
          and [bool(p.get("cached")) for p in inc["pages"]] == [True, False]
          and pngs_kept and metrics_same and len(entries) == 2)   # 旧键被裁掉，缓存不会无限增长)
    return {"status": "PASS" if ok else "FAIL", "warm_ms": round(warm_ms),
            "cold_misses": cold["coverage"]["cache_misses"],
            "incremental": [(p["slide"], bool(p.get("cached"))) for p in inc["pages"]],
            "entries": len(entries), "pngs_kept": pngs_kept, "metrics_same": metrics_same}


def check_cache_content_verify():
    """缓存命中必须逐字节核对证据 PNG；缺页只能记缺口，不许按序号猜页。"""
    import tempfile
    rc = load("render_check", SCRIPTS / "render_check.py")
    with tempfile.TemporaryDirectory() as d:
        work = pathlib.Path(d)
        a = work / "page-aaa111-r0-01.png"
        b = work / "page-bbb222-r0-02.png"
        a.write_bytes(b"pixel-A")
        b.write_bytes(b"pixel-B")
        sha_a = rc._file_sha(a)
        entry_ok = {"png": a.name, "png_sha": sha_a}
        same_exists_other_content = {"png": a.name, "png_sha": rc._file_sha(b)}
        legacy = {"png": a.name}                                   # 旧格式：无指纹
        hit_before = rc._png_present(work, entry_ok)               # 未篡改 → 应命中
        a.write_bytes(b"pixel-A-tampered")                          # 缓存被别页像素顶替
        res = {
            "sha_ok": bool(sha_a) and hit_before,
            "tamper_rejected": not rc._png_present(work, entry_ok),
            "hash_mismatch_rejected": not rc._png_present(work, same_exists_other_content),
            "legacy_rejected": not rc._png_present(work, legacy),
            "name_token_scoped": rc._png_name(work, 1, "aaa111") == a.name
                                 and rc._png_name(work, 2, "aaa111") is None
                                 and rc._png_name(work, 2, "bbb222") == b.name,
        }
    ok = all(res.values())
    return {"status": "PASS" if ok else "FAIL", **res}


def check_background_qualification():
    """layer=background 只是意图：面积不足或遮罩虚设即失去免检，并被点名。"""
    guard = load("guard", SCRIPTS / "guard.py")
    crit = load("art_critic", SCRIPTS / "art_critic.py")
    cw, ch = 1920, 1080
    smuggle = {"type": "image", "id": "sneak", "x": 96, "y": 380, "width": 1088,
               "height": 200, "layer": "background",
               "overlay": {"type": "solid", "color": "#000000", "opacity": 0.1}}
    legit = {"type": "image", "id": "bg", "x": 0, "y": 0, "width": 1920, "height": 1080,
             "layer": "background", "overlay": {"type": "solid", "color": "#000000",
                                                "opacity": 0.6}}
    bare = {"type": "image", "id": "bare", "x": 0, "y": 0, "width": 1920, "height": 1080,
            "layer": "background"}
    s_ok, s_why = crit.background_layer_ok(smuggle, cw, ch)
    l_ok, _ = crit.background_layer_ok(legit, cw, ch)
    b_ok, b_why = crit.background_layer_ok(bare, cw, ch)
    declared_only = crit.is_background_layer(smuggle) and not crit.bg_exempt(smuggle, cw, ch)
    spec = {"canvas": {"width": cw, "height": ch},
            "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111",
                                 "muted": "#777777", "primary": "#222222",
                                 "secondary": "#333333", "accent": "#AA0000"}},
            "slides": [{"id": "s01",
                        "page_intent": {"insight": "A", "focus": "t", "density": "sparse",
                                        "energy": "low", "empty_space_role": "hold"},
                        "elements": [dict(smuggle),
                                     {"type": "text", "id": "t", "x": 96, "y": 152,
                                      "width": 608, "height": 120, "size": 64,
                                      "text": "结论", "color": "ink", "max_lines": 1,
                                      "line_height": 1.2, "padding": 0},
                                     {"type": "chart", "id": "c1", "chart_kind": "bars",
                                      "x": 96, "y": 640, "width": 608, "height": 120,
                                      "data": [{"label": "A", "value": 1}], "unit": "次",
                                      "period": "2026", "basis": "示例口径"},
                                     {"type": "chart", "id": "c2", "chart_kind": "bars",
                                      "x": 768, "y": 640, "width": 400, "height": 120,
                                      "data": [{"label": "A", "value": 1}], "unit": "次",
                                      "period": "2026", "basis": "示例口径"}]}]}
    g = guard.check_spec(spec)
    disguised = [c for c in g["checks"] if "BACKGROUND_DISGUISED" in str(c.get("id"))
                 or c.get("rule") == "preflight" and "BACKGROUND_DISGUISED" in str(c.get("msg"))]
    media_over = [c for c in g.get("preflight") or [] if c["code"] == "MEDIA_BUDGET"]
    ok = (not s_ok and "10" in (s_why or "") and l_ok and not b_ok
          and declared_only and bool(disguised) and bool(media_over))
    return {"status": "PASS" if ok else "FAIL", "smuggle_reason": s_why,
            "bare_reason": b_why, "disguised": len(disguised),
            "media_budget_flag": len(media_over)}


def check_text_contrast_gate():
    """实测「文字 vs 其下方像素」：深底深字必须被量化，浅底深字不得误伤。"""
    import tempfile
    from PIL import Image
    rc = load("render_check", SCRIPTS / "render_check.py")
    crit = load("art_critic", SCRIPTS / "art_critic.py")
    qa = load("qa", SCRIPTS / "qa.py")
    dark = {"type": "image", "id": "x"}
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        bad, good = p / "bad.png", p / "good.png"
        Image.new("RGB", (320, 180), (14, 16, 15)).save(bad)
        Image.new("RGB", (320, 180), (244, 241, 234)).save(good)
        reg = [{"id": "st", "role": "", "color": "#15181A", "aux": False,
                "box": (0.05, 0.14, 0.56, 0.11)}]
        reg_light = [{"id": "st", "role": "", "color": "#1B221F", "aux": False,
                      "box": (0.05, 0.14, 0.56, 0.11)}]
        m_bad = rc.measure_image(bad, text_regions=reg)
        m_good = rc.measure_image(good, text_regions=reg_light)
    tc_bad, tc_good = m_bad.get("text_contrast_min"), m_good.get("text_contrast_min")
    spec = {"canvas": {"width": 1280, "height": 720},
            "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111",
                                 "muted": "#777777", "primary": "#222222",
                                 "secondary": "#333333", "accent": "#AA0000"}},
            "slides": [{"id": "s01",
                        "page_intent": {"insight": "A", "focus": "st", "density": "sparse",
                                        "energy": "low", "empty_space_role": "hold"},
                        "elements": [{"type": "text", "id": "st", "x": 96, "y": 152,
                                      "width": 608, "height": 120, "size": 64,
                                      "text": "结论", "color": "ink", "max_lines": 1,
                                      "line_height": 1.2, "padding": 0}]}]}
    ev = {"rendered": True, "pages": [dict(m_bad, slide="s01", index=0, page=1)]}
    c = crit.critique_deck(spec, ev)
    gate = [g for g in c["hard_gates"] if g["code"] == "READABILITY_FAIL"]
    ok = (tc_bad is not None and tc_bad < 1.5 and tc_good is not None and tc_good > 10
          and bool(gate) and gate[0]["severity"] == "BLOCKED"
          and qa.DEFAULT_THRESHOLDS["text_contrast_fail"] == 3.0
          and qa.DEFAULT_THRESHOLDS["text_contrast_warn"] == 4.5
          and "render_contrast" in qa.DEFAULT_PENALTIES)
    return {"status": "PASS" if ok else "FAIL", "dark_ratio": tc_bad,
            "light_ratio": tc_good, "gate": bool(gate)}


def check_line_measure():
    """行长（measure）是静态可判定的排版质量：超限提示，两倍超限阻断。"""
    guard = load("guard", SCRIPTS / "guard.py")
    lm_limits = guard._measure_limits()

    def text(eid, chars, size, width, role=None):
        e = {"type": "text", "id": eid, "x": 96, "y": 200, "width": width, "height": 120,
             "size": size, "text": "字" * chars, "color": "ink", "max_lines": 4,
             "line_height": 1.5, "padding": 0}
        if role:
            e["role"] = role
        return e

    over = guard.line_measure(text("a", 60, 20, 1088), lm_limits)       # 54 字/行 > 38
    fatal = guard.line_measure(text("b", 200, 10, 1088), lm_limits)     # 108 字/行 > 76
    aux = guard.line_measure(text("c", 200, 10, 1088, role="source"), lm_limits)
    ok_case = guard.line_measure(text("d", 24, 20, 608), lm_limits)
    spec = {"canvas": {"width": 1920, "height": 1080},
            "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111",
                                 "muted": "#777777", "primary": "#222222",
                                 "secondary": "#333333", "accent": "#AA0000"}},
            "slides": [{"id": "s01",
                        "page_intent": {"insight": "A", "focus": "b", "density": "sparse",
                                        "energy": "low", "empty_space_role": "hold"},
                        "elements": [text("a", 60, 20, 1088), text("b", 200, 10, 1088),
                                     text("c", 200, 10, 1088, role="source")]}]}
    g = guard.check_spec(spec)
    typo_err = [c for c in g["checks"] if c["rule"] == "typography" and c["level"] == "error"]
    typo_warn = [c for c in g["checks"] if c["rule"] == "typography" and c["level"] == "warn"]
    pre = [i for i in (g.get("preflight") or []) if i["code"] == "LINE_MEASURE"]
    lm_stats = g.get("line_measure") or {}
    ok = (over and over["over"] and not over["fatal"] and fatal and fatal["fatal"]
          and aux is None and ok_case and not ok_case["over"]
          and len(typo_err) == 1 and "b" in typo_err[0]["id"] and len(typo_warn) == 1
          and bool(pre) and lm_stats.get("checked") == 2 and lm_stats.get("over") == 2
          and (g.get("grid") or {}).get("adherence") is not None)
    return {"status": "PASS" if ok else "FAIL", "over": bool(over and over["over"]),
            "fatal_blocked": len(typo_err), "warn": len(typo_warn),
            "preflight": len(pre), "grid_adherence": (g.get("grid") or {}).get("adherence")}


def check_palette_discipline():
    """色彩系统纪律是 deck 级的事：单页合规不代表成套（色相族、强调色、脏渐变）。"""
    guard = load("guard", SCRIPTS / "guard.py")

    def el(eid, color, etype="text"):
        return {"type": etype, "id": eid, "x": 96, "y": 200, "width": 400, "height": 120,
                "size": 20, "text": "内容", "color": color}

    base = {"canvas": {"width": 1280, "height": 720},
            "theme": {"colors": {"background": "#FFFFFF", "surface": "#F7F5F0",
                                 "ink": "#111111", "muted": "#666666",
                                 "primary": "#22443D", "secondary": "#1F3A44",
                                 "accent": "#B0402F"}}}
    quiet = {**base, "slides": [
        {"id": f"s{i:02d}", "page_intent": {"insight": "A", "focus": "t", "density": d,
                                            "energy": e},
         "elements": [el("t", "primary"), el("u", "accent")]}
        for i, (d, e) in enumerate([("sparse", "low"), ("dense", "high")], 1)]}
    spread_hues = {**base, "slides": [
        {"id": "s01", "page_intent": {"insight": "A", "focus": "t", "density": "sparse",
                                       "energy": "low"},
         "elements": [el("t", "#CC0000"), el("a", "#00AA00"), el("b", "#0000CC"),
                      el("c", "#FFFF00"), el("d", "#FF00FF"), el("e", "#00FFFF")]}]}
    collide = {**base, "slides": quiet["slides"],
               "theme": {"colors": {**base["theme"]["colors"],
                                    "primary": "#2E5A54", "accent": "#39635C"}}}

    def gradient_page(fill):
        return {**base, "slides": [{"id": "s01",
                                    "page_intent": {"insight": "A", "focus": "t",
                                                     "density": "sparse", "energy": "low"},
                                    "elements": [
                                        {"type": "shape", "id": "t", "x": 96, "y": 200,
                                         "width": 400, "height": 120, "fill": fill},
                                        el("u", "primary")]}]}

    mud = gradient_page({"type": "gradient", "stops": [
        {"position": 0, "color": "#7A4B5D"}, {"position": 1, "color": "#4B6E57"}]})
    whisper = gradient_page({"type": "gradient", "stops": [
        {"position": 0, "color": "#F8F5EF"}, {"position": 1, "color": "#EBE5D9"}]})

    def rules(spec):
        return [c for c in guard.check_spec(spec)["checks"] if c["rule"] == "palette_discipline"]

    q, sp, co, mu, wh = rules(quiet), rules(spread_hues), rules(collide), rules(mud), rules(whisper)
    # 「宋瓷低对比同族渐变」是留白手法，不得被当成脏块；互补等彩度渐变才提示
    ok = (not q and len(sp) == 1 and sp[0]["level"] == "warn" and "色相族" in sp[0]["msg"]
          and any(co_item["level"] == "warn" and "强调色" in co_item["msg"]
                  for co_item in co)
          and len(mu) == 1 and mu[0]["level"] == "hint" and "互补" in mu[0]["msg"]
          and not wh)
    return {"status": "PASS" if ok else "FAIL", "quiet": len(q), "hues": len(sp),
            "accent_collision": len(co), "muddy": len(mu), "whisper_gradient": len(wh)}


def check_chart_style_drift():
    """同一图表类型跨页必须共用一套标签规格，否则差异只会读成「没对齐」。"""
    guard = load("guard", SCRIPTS / "guard.py")

    def chart(size, legend, sid):
        return {"type": "chart", "id": "ch", "chart_kind": "horizontal_bar", "x": 96,
                "y": 200, "width": 900, "height": 320, "label_size": size,
                "legend": legend, "data": {"labels": ["a", "b"], "values": [3, 5]},
                "label": sid}

    def spec(a, b, legend=(True, False)):
        la, lb = legend
        return {"canvas": {"width": 1280, "height": 720},
                "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111",
                                    "muted": "#666666", "primary": "#22443D",
                                    "secondary": "#1F3A44", "accent": "#B0402F"}},
                "slides": [{"id": "s01", "page_intent": {"insight": "A", "focus": "ch",
                                                         "density": "sparse", "energy": "low"},
                            "elements": [chart(a, la, "x")]},
                           {"id": "s02", "page_intent": {"insight": "B", "focus": "ch",
                                                         "density": "dense", "energy": "high"},
                            "elements": [chart(b, lb, "y")]}]}

    drift = [c for c in guard.check_spec(spec(13, 17))["checks"]
             if c["rule"] == "chart_style_drift"]
    same = [c for c in guard.check_spec(spec(13, 13, legend=(True, True)))["checks"]
            if c["rule"] == "chart_style_drift"]
    one = spec(13, 17)
    single = [c for c in guard.check_spec({**one, "slides": [one["slides"][0]]})["checks"]
              if c["rule"] == "chart_style_drift"]
    warn = [c for c in drift if c["level"] == "warn"]
    hint = [c for c in drift if c["level"] == "hint"]
    ok = (len(warn) == 1 and "标签字号" in warn[0]["msg"] and len(hint) == 1
          and not same and not single)
    return {"status": "PASS" if ok else "FAIL", "warn": len(warn), "legend_hint": len(hint),
            "consistent": len(same), "single_page": len(single)}


def check_focus_placement():
    """焦点落位：对齐任一版面轴线记一次层级加分，完全不上线只在预检提示（不罚分）。"""
    guard = load("guard", SCRIPTS / "guard.py")
    crit = load("art_critic", SCRIPTS / "art_critic.py")

    def page(x, sid="s01"):
        # 5 段阅读文本 → 「媒体信号受控」加分不会触发，本页唯一的层级加分只能来自落位
        body = [{"type": "text", "id": f"b{i}", "role": "body", "x": 96 + i * 20, "y": 700,
                 "width": 300, "height": 40, "size": 14, "text": "说明"} for i in range(5)]
        return {"id": sid, "page_intent": {"insight": "结论", "focus": "ch", "density": "sparse",
                                           "energy": "low", "empty_space_role": "hold"},
                "elements": [
                    {"type": "chart", "id": "ch", "chart_kind": "horizontal_bar", "x": x,
                     "y": 286, "width": 640, "height": 400,
                     "data": {"labels": ["a", "b"], "values": [3, 5]}},
                    {"type": "text", "id": "cap", "role": "caption", "x": 96, "y": 640,
                     "width": 400, "height": 40, "size": 11, "text": "来源：样例数据"}] + body}

    def deck(x):
        return {"canvas": {"width": 1920, "height": 1080},
                "theme": {"colors": {"background": "#FFFFFF", "surface": "#F7F5F0",
                                     "ink": "#111111", "muted": "#666666",
                                     "primary": "#22443D", "secondary": "#1F3A44",
                                     "accent": "#B0402F"}},
                "slides": [page(x)]}

    aligned, loose = deck(320), deck(544)      # 中心 x=0.333（三分线） / x=0.45（不上线）
    codes_on = {i["code"] for i in guard.check_spec(aligned).get("preflight") or []}
    codes_off = {i["code"] for i in guard.check_spec(loose).get("preflight") or []}
    cr_on = crit.critique_deck(aligned)
    cr_off = crit.critique_deck(loose)

    def axis_credit(res):
        return [e for s in res.get("slides") or []
                for e in (s.get("dimension_evidence") or {}).get("visual_hierarchy") or []
                if "对齐" in str(e) and str(e).startswith("+")]

    def size_debit(res):
        return [e for s in res.get("slides") or []
                for ev in (s.get("dimension_evidence") or {}).values() for e in ev or []
                if "仅领先第二大文字" in str(e)]

    # 附带回归：焦点是图表时不得用「文字尺度」扣分（旧版会算出 0px 的假竞争）
    ok = ("FOCUS_PLACEMENT" not in codes_on and "FOCUS_PLACEMENT" in codes_off
          and len(axis_credit(cr_on)) == 1 and not axis_credit(cr_off)
          and not size_debit(cr_on) and not size_debit(cr_off))
    return {"status": "PASS" if ok else "FAIL", "hint_on_aligned": "FOCUS_PLACEMENT" in codes_on,
            "hint_on_loose": "FOCUS_PLACEMENT" in codes_off,
            "credit": len(axis_credit(cr_on)), "text_scale_debit_on_chart_focus": len(size_debit(cr_on))}


def check_data_governance():
    """事实/口径治理：来源必填、跨页口径一致、字段名标题拦截。"""
    guard = load("guard", SCRIPTS / "guard.py")
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#666666",
                        "primary": "#1C1C1C", "secondary": "#5A5A5A", "accent": "#2563EB"}}

    def slide(sid, insight, elements):
        return {"id": sid, "page_intent": {"insight": insight, "focus": "x",
                                           "density": "balanced", "energy": "low",
                                           "empty_space_role": "hold"},
                "elements": elements}

    def chart(eid, metric=None, unit=None, period=None):
        e = {"type": "chart", "id": eid, "chart_kind": "bar", "x": 100, "y": 100,
             "width": 600, "height": 400,
             "data": [{"label": "A", "value": 10}, {"label": "B", "value": 20}]}
        if metric:
            e["metric"] = metric
        if unit:
            e["unit"] = unit
        if period:
            e["period"] = period
        return e

    canvas = {"width": 1280, "height": 720}
    # 1) 来源/单位/期间缺失 → data_provenance warn
    r1 = guard.check_spec({"canvas": canvas, "theme": theme,
                           "slides": [slide("s01", "营收增长", [chart("c1")])]})
    prov = [c for c in r1["checks"] if c["rule"] == "data_provenance"]
    # 2) 同一 metric 跨页单位打架 → metric_consistency error
    r2 = guard.check_spec({"canvas": canvas, "theme": theme, "slides": [
        slide("s01", "营收 10 亿", [chart("c1", metric="revenue", unit="亿元", period="2026")]),
        slide("s02", "营收 120 万", [chart("c2", metric="revenue", unit="万元", period="2026")])]})
    unit_conflict = [c for c in r2["checks"] if c["rule"] == "metric_consistency"
                     and c["level"] == "error"]
    # 3) 同一 metric 跨页期间打架 → warn（不 error）
    r3 = guard.check_spec({"canvas": canvas, "theme": theme, "slides": [
        slide("s01", "营收", [chart("c1", metric="revenue", unit="亿元", period="2026")]),
        slide("s02", "营收", [chart("c2", metric="revenue", unit="亿元", period="FY26")])]})
    period_conflict = [c for c in r3["checks"] if c["rule"] == "metric_consistency"
                       and "期间" in c["msg"]]
    # 4) 字段名标题 → title_semantics hint；结论式标题不触发
    r4 = guard.check_spec({"canvas": canvas, "theme": theme, "slides": [
        slide("s01", "市场分析", []),
        slide("s02", "市场已从规模驱动转向效率驱动", [])]})
    ts = [c for c in r4["checks"] if c["rule"] == "title_semantics"]
    ok = (prov and unit_conflict and period_conflict
          and len(ts) == 1 and ts[0]["id"] == "s01")
    return {"status": "PASS" if ok else "FAIL",
            "provenance_warns": len(prov), "unit_conflict_errors": len(unit_conflict),
            "period_conflict_warns": len(period_conflict), "fieldname_hints": len(ts)}


def check_multi_series():
    """多序列图表契约：series[{name, values}] + categories 不要求 data，highlight 是序列索引。"""
    guard = load("guard", SCRIPTS / "guard.py")
    comp = load("compiler", SCRIPTS / "compiler.py")
    import tempfile, pathlib
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#666666",
                        "primary": "#1C1C1C", "secondary": "#5A5A5A", "accent": "#2563EB"}}
    spec = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
            "slides": [{"id": "s01",
                        "page_intent": {"insight": "结论", "focus": "m1", "density": "balanced",
                                        "energy": "low", "empty_space_role": "hold"},
                        "elements": [{"type": "chart", "id": "m1", "chart_kind": "line",
                                      "x": 120, "y": 120, "width": 1000, "height": 400,
                                      "categories": ["Q1", "Q2", "Q3", "Q4"],
                                      "series": [{"name": "A", "values": [1, 2, 3, 4]},
                                                 {"name": "B", "values": [2, 3, 4, 5]}],
                                      "highlight": 1}]}]}
    g = guard.check_spec(spec)
    codes = {c["rule"] for c in g.get("checks") or []}
    msgs = "\n".join(g.get("warnings") or [])
    guard_ok = ("data_integrity" not in codes and "chart_highlight" not in codes
                and "缺少 data" not in msgs)
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "m.pptx"
        rep = comp.compile_deck(spec, out, checks=False)
    render_ok = rep["passed"] and "已跳过" not in "\n".join(rep["warnings"])
    return {"status": "PASS" if (guard_ok and render_ok) else "FAIL",
            "guard_ok": guard_ok, "render_ok": render_ok}


def check_cache_projection():
    """缓存键的投影口径：动像素的必须进键，只动判定的不进；且排除表不得屏蔽渲染输入。"""
    import re
    rc = load("render_check", SCRIPTS / "render_check.py")

    def spec(body):
        return {"canvas": {"width": 1280, "height": 720},
                "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111",
                                     "muted": "#666666", "primary": "#22443D",
                                     "accent": "#B0402F"},
                          "fonts": {"title": "Noto Serif CJK SC"},
                          "constraints": {"max_colors": 5}},
                "slides": [body]}

    def slide(**over):
        s = {"id": "s01", "background": "#FFFFFF", "label": "封面",
             "page_intent": {"insight": "A", "focus": "t", "density": "sparse"},
             "source_zone": {"x": 0, "y": 600}, "notes": "旧说明",
             "elements": [{"type": "text", "id": "t", "x": 96, "y": 200, "width": 400,
                           "height": 120, "size": 20, "text": "标题", "color": "ink"}]}
        s.update(over)
        return s

    canvas = spec({})["canvas"]
    theme = spec({})["theme"]
    k = lambda s, focus="t": rc._slide_key(s, canvas, 96, theme, "soffice", [], focus=focus)
    base = k(slide())
    same = k(slide(**{"page_intent": {"insight": "换一句说法", "focus": "t",
                                       "density": "dense"},
                      "notes": "改了备注", "source_zone": {"x": 9, "y": 9}}))
    focus_moved = k(slide(), focus="chart")
    pixel_moved = k(slide(elements=[{"type": "text", "id": "t", "x": 136, "y": 200,
                                      "width": 400, "height": 120, "size": 20,
                                      "text": "标题", "color": "ink"}]))
    view_same = rc.spec_view(spec(slide(notes="新备注"))) == rc.spec_view(spec(slide()))
    view_px = rc.spec_view(spec(slide(elements=[]))) != rc.spec_view(spec(slide()))
    view_media = rc.spec_view(spec(slide(id="s99"))) != rc.spec_view(spec(slide()))

    # 排除表与真实代码保持同步：编译器读到的 slide 级键若被排除，缓存就会漏测
    src = (SCRIPTS / "compiler.py").read_text(encoding="utf-8")
    reads = set(re.findall(r"slide_spec\.get\(['\"]([a-z_]+)['\"]", src))
    allowed = {"id", "label", "page_intent", "source_zone", "notes", "speaker_notes",
               "comment", "comments", "annotations"}
    leak = {rkey for rkey in reads if rkey in set(rc.NON_PIXEL_SLIDE_KEYS)} - allowed
    tsrc = "\n".join((SCRIPTS / m).read_text(encoding="utf-8")
                     for m in ("compiler.py", "primitives.py", "charts.py", "elements.py"))
    treads = set(re.findall(r"theme\.get\(['\"]([a-z_]+)['\"]", tsrc))
    tleak = treads & set(rc.NON_PIXEL_THEME_KEYS)
    ok = (base == same and base != focus_moved and base != pixel_moved and view_same
          and view_px and view_media and not leak and not tleak
          and bool(reads & {"background", "elements"}))
    return {"status": "PASS" if ok else "FAIL", "compiler_slide_keys": sorted(reads),
            "leaked_slide_keys": sorted(leak), "leaked_theme_keys": sorted(tleak)}


def check_rhythm_measured():
    """节奏判定看实测墨迹：标签相同但留白真变了 = 成立；标签交替而墨迹不动 = 扣分。"""
    crit = load("art_critic", SCRIPTS / "art_critic.py")
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                        "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"}}

    def page(sid, density):
        return {"id": sid,
                "page_intent": {"insight": f"{sid} 结论", "focus": "st", "density": density,
                                "energy": "medium", "empty_space_role": "hold"},
                "elements": [{"type": "text", "id": "st", "x": 96, "y": 152, "width": 608,
                              "height": 120, "size": 64, "text": "结论", "color": "ink",
                              "max_lines": 1, "line_height": 1.2, "padding": 0}]}

    def score(d1, d2, o1, o2):
        spec = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
                "slides": [page("s01", d1), page("s02", d2)]}
        ev = {"rendered": True,
              "pages": [{"slide": "s01", "index": 0, "page": 1, "occupancy": o1,
                         "edge": 0.3, "brightness": 0.9},
                        {"slide": "s02", "index": 1, "page": 2, "occupancy": o2,
                         "edge": 0.3, "brightness": 0.9}]}
        return crit.critique_deck(spec, ev)["slides"][1]["scores"].get("rhythm", 5)

    same_big = score("sparse", "sparse", 0.15, 0.45)   # 标签相同、墨迹差 0.30 → 不扣反加
    one_label_big = score("sparse", "balanced", 0.15, 0.45)   # 只动一个标签但墨迹真动 → 加分
    alt_flat = score("sparse", "dense", 0.30, 0.31)    # 标签交替、墨迹不动 → 扣
    same_flat = score("sparse", "sparse", 0.30, 0.31)  # 双同且墨迹不动 → 扣更多
    # 只验序关系：实测墨迹变化必须盖过标签启发——标签相同而墨迹真变要拿到高于基线的节奏分；
    # 标签变了但墨迹不动，与标签墨迹都不动一样，不得分。
    ok = (same_big >= crit.BASELINE and same_big > same_flat and alt_flat < same_big
          and alt_flat <= same_flat + 1 and one_label_big >= crit.BASELINE + 1)
    return {"status": "PASS" if ok else "FAIL", "same_label_big_ink": same_big,
            "one_label_big_ink": one_label_big,
            "alt_label_flat_ink": alt_flat, "same_label_flat_ink": same_flat}


def check_manifest_attestation():
    """发布清单不得承认来历不明的报告：戳不符 / 无戳却称 PASS / 幽灵页面 → BLOCKED。"""
    prim = load("primitives", SCRIPTS / "primitives.py")
    qa = load("qa", SCRIPTS / "qa.py")
    spec = {"canvas": {"width": 1280, "height": 720}, "slides": [{"id": "s01"}, {"id": "s02"}]}
    fp = prim.spec_fingerprint(spec)
    stable = fp == prim.spec_fingerprint({"slides": [{"id": "s01"}, {"id": "s02"}],
                                          "canvas": {"height": 720, "width": 1280},
                                          })
    differs = fp != prim.spec_fingerprint({**spec, "slides": [{"id": "s01"}]})
    good_qa = {"status": "PASS", "source_spec_hash": fp, "release_eligible": True,
               "render": {"coverage": {"rendered_pages": 2, "total_pages": 2,
                                      "rendered_ids": ["s01", "s02"]}},
               "render_evidence": {"pages": [{"slide": "s01"}, {"slide": "s02"}]}}
    good_cr = {"status": "PASS", "deck_score": 95.0, "source_spec_hash": fp,
               "slides": [{"slide": "s01"}, {"slide": "s02"}]}
    m0 = qa.release_manifest(spec, good_qa, good_cr)
    m1 = qa.release_manifest(spec, good_qa, {"status": "PASS", "deck_score": 99.0,
                                             "slides": [{"slide": "sX"}]})
    m2 = qa.release_manifest(spec, good_qa, {**good_cr, "source_spec_hash": "deadbeef00000000"})
    m3 = qa.release_manifest(spec, {k: v for k, v in good_qa.items() if k != "source_spec_hash"},
                             good_cr)
    m4 = qa.release_manifest(spec, good_qa, {**good_cr, "slides": good_cr["slides"][:1]})
    ok = (stable and differs and m0["status"] == "PASS" and not m0["validation"]["issues"]
          and m1["status"] == "BLOCKED" and len(m1["validation"]["issues"]) >= 2
          and m2["status"] == "BLOCKED" and m3["status"] == "BLOCKED"
          and m4["status"] == "BLOCKED"
          and m0["source_spec_hash"] == fp)
    return {"status": "PASS" if ok else "FAIL", "clean": m0["status"],
            "forged": m1["status"], "stale": m2["status"], "unstamped_pass": m3["status"],
            "page_mismatch": m4["status"]}


def main():
    result = {"structure": check_structure(), "templates_yaml": check_templates_yaml(), "references": check_references(), "imports": check_imports(), "fill_contract": check_fill_contract(), "art_critic": check_critic(), "critic_with_render": check_critic_with_render(), "critic_pass_reachable": check_critic_pass_reachable(), "render_metrics": check_render_metrics(), "pipeline": check_pipeline(),
            "preflight_sync": check_preflight_sync(), "background_layer": check_background_layer(),
            "route_layer": check_route_layer(), "qa_performance": check_qa_performance_keys(),
            "progressive_qa": check_progressive_qa(), "decision_cache": check_decision_cache(),
            "render_cache": check_render_cache(),
            "cache_content_verify": check_cache_content_verify(),
            "background_qualification": check_background_qualification(),
            "text_contrast_gate": check_text_contrast_gate(),
            "line_measure": check_line_measure(),
            "rhythm_measured": check_rhythm_measured(),
            "palette_discipline": check_palette_discipline(),
            "chart_style_drift": check_chart_style_drift(),
            "focus_placement": check_focus_placement(),
            "data_governance": check_data_governance(),
            "multi_series": check_multi_series(),
            "cache_projection": check_cache_projection(),
            "manifest_attestation": check_manifest_attestation()}
    ok = all(v["status"] == "PASS" for v in result.values())
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("PPT Visual Art Director OS selftest")
        for k, v in result.items():
            print(f"[{k}] {v['status']}", v.get("error", v.get("missing", "")))
        print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)

if __name__ == "__main__":
    main()
