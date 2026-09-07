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


def main():
    result = {"structure": check_structure(), "templates_yaml": check_templates_yaml(), "references": check_references(), "imports": check_imports(), "fill_contract": check_fill_contract(), "art_critic": check_critic(), "critic_with_render": check_critic_with_render(), "critic_pass_reachable": check_critic_pass_reachable(), "render_metrics": check_render_metrics(), "pipeline": check_pipeline()}
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
