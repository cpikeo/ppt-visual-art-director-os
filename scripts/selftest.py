#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PPT Visual Art Director OS contract smoke tests."""
from __future__ import annotations
import importlib.util, json, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REFS = ROOT / "references"
SCRIPTS = ROOT / "scripts"
REQUIRED_REFS = {"design-intelligence.md", "design-system.md", "production-contract.md"}
REQUIRED_SCRIPTS = {"vao.py", "compiler.py", "primitives.py", "guard.py", "render_check.py", "compile_cache.py", "qa.py", "asset_prompt.py", "route.py", "pipeline.py", "ghost.py", "design_intelligence.py", "layout_search.py", "intent_compiler.py", "design_intelligence_rules.py"}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_structure():
    missing = sorted([f for f in REQUIRED_REFS if not (REFS / f).exists()] + [f for f in REQUIRED_SCRIPTS if not (SCRIPTS / f).exists()])
    return {"status": "PASS" if not missing else "FAIL", "missing": missing}
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
    # 不随包分发的引用：用户的构建模块占位名，以及工作区基准/尚未实现的路线图条目
    allow_missing = {"build.py", "build_mydeck.py", "build_vao.py", "build_module.py", "build_card.py",
                     "build_page.py", "build_probe.py", "build_bench_deck.py"}
    for doc in docs:
        refs.update(re.findall(r"[\w./-]+\.(?:md|py)", doc.read_text(encoding="utf-8")))
    missing = sorted({r.split("/")[-1] for r in refs if ".." not in r and r.split("/")[-1] not in names and r.split("/")[-1] not in allow_missing})
    return {"status": "PASS" if not missing else "FAIL", "missing": missing}
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
    mod = load("compiler", SCRIPTS / "compiler.py")
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
        for name in ("primitives", "guard", "compiler"):
            load(name, SCRIPTS / f"{name}.py")
        return {"status": "PASS"}
    except Exception as exc:
        return {"status": "FAIL", "error": repr(exc)}


def check_normalizer():
    """V2 生产链第 0 级：网格/token 归一化确定性、幂等、可退出、留痕。"""
    norm = load("guard", SCRIPTS / "guard.py")
    theme = {"colors": {"background": "#FAF7F0", "accent": "#8E2F28", "ink": "#191510",
                        "muted": "#6E675C"},
             "fonts": {"family": "SimSun", "latin": "Georgia"}}
    def slide(sid, el):
        return {"id": sid, "page_intent": {"insight": "结论", "focus": el["id"]},
                "elements": [el]}
    spec = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
            "slides": [
                slide("s01", {"type": "text", "id": "t1", "x": 61, "y": 52,
                              "width": 66, "height": 108, "text": "字", "size": 32,
                              "color": "#8e2f28", "font": "simsun ", "padding": 3,
                              "max_lines": 1}),
                slide("s02", {"type": "text", "id": "t2", "x": 48, "y": 48,
                              "width": 64, "height": 64, "text": "字", "size": 32,
                              "color": "accent", "grid_exempt": True, "padding": 0,
                              "max_lines": 1})]}
    new, rep = norm.normalize_spec(spec)
    t1 = new["slides"][0]["elements"][0]
    t2 = new["slides"][1]["elements"][0]
    ok = (t1["x"] == 64 and t1["y"] == 56 and t1["width"] == 72 and t1["height"] == 112
          and t1["color"] == "accent" and t1["font"] == "SimSun" and t1["padding"] == 4
          and rep["idempotent"] and rep["changed"] == 7
          and set(rep["by_rule"]) == {"grid_snap", "grid_snap_size", "color_hex_to_token",
                                      "font_token_alias", "spacing_snap"}
          # 豁免与已对齐元素不动
          and t2["x"] == 48 and t2["color"] == "accent"
          # 纯函数：入参未被修改
          and spec["slides"][0]["elements"][0]["x"] == 61
          and rep["hash_before"] != rep["hash_after"]
          and len(rep["items"]) == 7)
    # spec 级关闭网格
    spec2 = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
             "normalization": {"grid": False},
             "slides": [slide("s01", {"type": "text", "id": "t", "x": 61, "y": 52,
                                      "width": 66, "height": 108, "text": "字",
                                      "size": 32, "color": "ink", "max_lines": 1})]}
    _, rep2 = norm.normalize_spec(spec2)
    ok = ok and not any(i["rule"].startswith("grid") for i in rep2["items"])
    # geometry_only_hash：改 insight 不变，改 x 变
    gh1 = norm.geometry_only_hash(spec)
    spec3 = __import__("copy").deepcopy(spec)
    spec3["slides"][0]["page_intent"]["insight"] = "新结论"
    spec3["slides"][0]["page_intent"]["density"] = "dense"
    gh2 = norm.geometry_only_hash(spec3)
    spec4 = __import__("copy").deepcopy(spec)
    spec4["slides"][0]["elements"][0]["x"] = 100
    gh3 = norm.geometry_only_hash(spec4)
    ok = ok and gh1 == gh2 and gh1 != gh3
    return {"status": "PASS" if ok else "FAIL", "changed": rep["changed"],
            "by_rule": rep["by_rule"], "idempotent": rep["idempotent"]}


def check_execution_modes():
    """流程控制：模式档案完备、legacy 别名映射；判断叙事已退出运行时（v4.15）。"""
    qa_mod = load("qa", SCRIPTS / "qa.py")
    modes = qa_mod.EXECUTION_MODES
    ok = (set(modes) == {"spec", "sketch", "draft", "review", "release"}
          and modes["spec"]["render"] is False
          and modes["spec"].get("compile") is False
          and modes["draft"].get("compile", True) is True
          and modes["sketch"]["render"] is False
          and modes["sketch"]["qa_level"] == 1
          and modes["draft"]["render"] is False
          and modes["review"]["qa_level"] == 2
          and modes["release"]["qa_level"] == 3
          # critic 引擎已整体移除：模式档案不得再出现 critic 列（v4.15 回归锁）
          and all("critic" not in m for m in modes.values())
          # 模式档案里不再有 preflight_gate / 稳定性字段
          and all("preflight_gate" not in m and "stability" not in m
                  for m in modes.values())
          and qa_mod.mode_profile(None)["render"] is False
          and qa_mod.mode_profile("")["render"] is False)
    try:
        qa_mod.mode_profile("bogus")
        unknown_mode_ok = False
    except ValueError:
        unknown_mode_ok = True
    ok = ok and unknown_mode_ok       # 未知模式必须显式报错，不能宁严静默回落
    # API 默认也必须是 draft，而不是只有 CLI 看起来像 draft。
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        default_run = qa_mod.run_qa(
            {"canvas": {"width": 1280, "height": 720}, "slides": []},
            pathlib.Path(td) / "default.pptx")
        empty_run = qa_mod.run_qa(
            {"canvas": {"width": 1280, "height": 720}, "slides": []},
            pathlib.Path(td) / "empty-mode.pptx", mode="")
    ok = ok and (default_run.get("execution") or {}).get("mode") == "draft" \
        and (empty_run.get("execution") or {}).get("mode") == "draft" \
        and default_run.get("performance", {}).get("qa_level") == 1 \
        and not (default_run.get("render") or {}).get("rendered", False)
    # 已被删除的机制不得复活（Stability Gate / Studio 状态机 / Critic 结果缓存与引擎）
    ok = ok and not hasattr(qa_mod, "_stability_decision") \
        and not hasattr(qa_mod, "_load_studio_state") \
        and not hasattr(qa_mod, "PREFLIGHT_HARD_CODES") \
        and not hasattr(qa_mod, "critic_block") \
        and "critic" not in __import__("inspect").signature(
            qa_mod.run_qa).parameters \
        and "critic_report" not in __import__("inspect").signature(
            qa_mod.release_manifest).parameters
    # route 模式推荐：默认 draft、发布词 → release
    route_mod = load("route", SCRIPTS / "route.py")
    ok = ok and route_mod.recommend_mode({}) == "draft" \
        and route_mod.recommend_mode({"brief": "发布终版"}) == "release" \
        and route_mod.recommend_mode({"brief": "方向已确认"}) == "review"
    # QA 对外判定只有三个词：PASS / FAIL / WARNING
    v_pass = qa_mod.verdict_of("PASS", 98.0, [], [])
    v_warn = qa_mod.verdict_of("REVISE", 88.0, [{"level": "warn"}], ["X"])
    v_fail = qa_mod.verdict_of("BLOCKED", 70.0, [{"level": "error"}], ["GUARD_FAIL"])
    ok = ok and (v_pass["verdict"], v_warn["verdict"], v_fail["verdict"]) == (
        "PASS", "WARNING", "FAIL")
    return {"status": "PASS" if ok else "FAIL", "modes": sorted(modes),
            "verdicts": [v_pass["verdict"], v_warn["verdict"], v_fail["verdict"]]}


def check_state_footprint():
    """跨轮状态必须只剩一样：上一版 spec（用于「只渲染变化页」）。"""
    import tempfile
    qa_mod = load("qa", SCRIPTS / "qa.py")
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
        out = pathlib.Path(d) / "st.pptx"
        work = pathlib.Path(d) / "render"
        qa_mod.run_qa(spec, out, mode="draft", render_dir=work, dpi=60)
        allowed = {"last_spec.json", "render_meta.json", "render_cache.json"}
        files = sorted(f.name for f in work.iterdir()) if work.exists() else []
        first = set(files) <= allowed and "last_spec.json" in files
        # 第二轮（改一句声明）：仍不产生 studio_state / critic 缓存 / 几何状态文件
        import copy
        spec2 = copy.deepcopy(spec)
        spec2["slides"][0]["page_intent"]["insight"] = "换一句说法"
        r2 = qa_mod.run_qa(spec2, out, mode="draft", render_dir=work, dpi=60)
        files2 = sorted(f.name for f in work.iterdir()) if work.exists() else []
        leaked = [f for f in files2 if f not in allowed]
        ok = (first and not leaked and r2["execution"]["change_classes"]["deck"]
              == "narrative" and "critic" not in r2.get("execution", {})
              and "critic" not in r2)
    return {"status": "PASS" if ok else "FAIL", "files": files2, "leaked": leaked}


def check_change_classifier():
    """V2 语义缓存分类：改声明 → narrative；改几何 → page_render；改主题 → full。"""
    import copy as _copy
    qa_mod = load("qa", SCRIPTS / "qa.py")

    def base():
        return {"canvas": {"width": 1280, "height": 720},
                "theme": {"colors": {"ink": "#111111"}, "fonts": {"family": "SimSun"}},
                "slides": [
                    {"id": "s01", "page_intent": {"insight": "A", "focus": "t"},
                     "elements": [{"type": "text", "id": "t", "x": 48, "y": 48,
                                   "width": 400, "height": 64, "text": "字",
                                   "size": 32, "color": "ink", "max_lines": 1}]},
                    {"id": "s02", "page_intent": {"insight": "B", "focus": "u"},
                     "elements": [{"type": "text", "id": "u", "x": 48, "y": 200,
                                   "width": 400, "height": 64, "text": "字",
                                   "size": 32, "color": "ink", "max_lines": 1}]}]}
    old_spec = base()
    # ① 只改声明（insight/density/notes）→ narrative，不需要渲染
    s = base()
    s["slides"][0]["page_intent"]["insight"] = "新结论"
    s["slides"][0]["page_intent"]["density"] = "dense"
    s["slides"][1]["notes"] = "备注"
    r1 = qa_mod.classify_spec_change(old_spec, s)
    ok = (r1["deck"] == "narrative" and r1["pages"]["s01"] == "narrative"
          and r1["pages"]["s02"] == "narrative" and r1["render_needed"] == [])
    # ② 改一页几何 → 仅该页 page_render
    s = base()
    s["slides"][1]["elements"][0]["y"] = 208
    r2 = qa_mod.classify_spec_change(old_spec, s)
    ok = ok and (r2["deck"] == "pages" and r2["pages"]["s01"] == "unchanged"
                 and r2["pages"]["s02"] == "page_render" and r2["render_needed"] == [2])
    # ③ 改主题 → full_render（全部页都要复核）
    s = base()
    s["theme"]["colors"]["ink"] = "#222222"
    r3 = qa_mod.classify_spec_change(old_spec, s)
    ok = ok and r3["deck"] == "full_render" and r3["render_needed"] == [1, 2]
    # ④ 无上一版 → structure（全部按需渲染）
    r4 = qa_mod.classify_spec_change(None, base())
    ok = ok and r4["deck"] == "structure" and r4["render_needed"] == [1, 2]
    # ⑤ 页数变化 → structure
    s = base()
    s["slides"].append(s["slides"][1])
    s["slides"][2] = _copy.deepcopy(s["slides"][1]); s["slides"][2]["id"] = "s03"
    r5 = qa_mod.classify_spec_change(old_spec, s)
    ok = ok and r5["deck"] == "structure"
    # ⑥ focus 变化属于像素相关（缓存键包含 focus）→ page_render 而非 narrative
    s = base()
    s["slides"][0]["page_intent"]["focus"] = "other"
    r6 = qa_mod.classify_spec_change(old_spec, s)
    ok = ok and r6["pages"]["s01"] == "page_render"
    return {"status": "PASS" if ok else "FAIL", "cases": [r1["deck"], r2["deck"],
            r3["deck"], r4["deck"], r5["deck"], r6["pages"]["s01"]]}
def check_pre_critic():
    """Pre-Critic：六类历史失败在渲染前被预测；好 spec 零误报。"""
    di = load("design_intelligence", SCRIPTS / "design_intelligence.py")
    theme = {"colors": {"background": "#FAF7F0", "primary": "#2B241B",
                        "secondary": "#9A8F7C", "accent": "#8E2F28",
                        "ink": "#191510", "muted": "#6E675C"},
             "constraints": {"accent_max": 0.05}}

    def pi(insight, focus, family="DATA", density="sparse", role="protect_focus"):
        return {"insight": insight, "focus": focus, "reading_order": [focus],
                "energy": "medium", "density": density, "empty_space_role": role,
                "page_family": family, "rhythm_stage": "context",
                "continuity_token": "t"}

    bad = {"canvas": {"width": 1280, "height": 720}, "theme": theme, "slides": [
        {"id": "b1", "page_intent": pi("对比", "t", "STATEMENT"), "elements": [
            {"type": "text", "id": "t", "x": 48, "y": 104, "width": 880, "height": 64,
             "text": "标题", "size": 34, "color": "ink", "max_lines": 1},
            {"type": "text", "id": "lead", "x": 48, "y": 184, "width": 600, "height": 64,
             "text": "淡墨正文", "size": 16, "color": "secondary", "max_lines": 2}]},
        {"id": "b2", "page_intent": pi("构成", "c", "DATA", "balanced"), "elements": [
            {"type": "chart", "id": "c", "chart_kind": "donut", "x": 328, "y": 168,
             "width": 624, "height": 416, "highlight": 1,
             "data": [{"label": "A", "value": 52}, {"label": "B", "value": 48}],
             "source": "s", "unit": "%", "period": "2026", "basis": "x"}]},
        {"id": "b3", "page_intent": pi("溢出", "t3", "STATEMENT"), "elements": [
            {"type": "text", "id": "t3", "x": 48, "y": 108, "width": 488, "height": 64,
             "text": "一行肯定放不下的很长很长的标题文字要换行", "size": 40,
             "color": "ink", "line_height": 1.15, "max_lines": 2}]},
        {"id": "b4", "page_intent": pi("无锚", "t4", "SECTION", role="separate_chapter"),
         "elements": [
            {"type": "text", "id": "t4", "x": 48, "y": 108, "width": 880, "height": 56,
             "text": "小标题", "size": 34, "color": "ink", "max_lines": 1},
            {"type": "chart", "id": "lanes", "chart_kind": "steps", "x": 48, "y": 264,
             "width": 1184, "height": 320,
             "data": [{"label": "一", "value": 1}, {"label": "二", "value": 2}],
             "source": "s", "unit": "条", "period": "2027", "basis": "x"}]},
        {"id": "b5", "page_intent": pi("平A", "t5", "SECTION"), "elements": [
            {"type": "text", "id": "t5", "x": 48, "y": 104, "width": 880, "height": 64,
             "text": "静一", "size": 40, "color": "ink", "max_lines": 1}]},
        {"id": "b6", "page_intent": pi("平B", "t6", "SECTION"), "elements": [
            {"type": "text", "id": "t6", "x": 48, "y": 104, "width": 880, "height": 64,
             "text": "静二", "size": 40, "color": "ink", "max_lines": 1}]},
    ]}
    rep = di.pre_critic(bad)
    codes = {r["code"] for r in rep["risks"]}
    want = {"CONTRAST_FAIL_RISK", "ACCENT_OVERFLOW", "TEXT_OVERFLOW_RISK",
            "NO_MEMORY_ANCHOR", "FOCUS_AREA_RISK", "RHYTHM_FLAT_RISK"}
    ok = want <= codes and rep["summary"]["high"] >= 6
    ok = ok and all(r.get("root_cause") and r.get("prevention") for r in rep["risks"])
    ok = ok and rep.get("root_cause_summary") and all(
        set(c) >= {"root_cause", "risk_count", "representative_pages", "fix_first"}
        for c in rep["root_cause_summary"])
    ok = ok and rep["first_fix"]["root_cause"] in {
        r["root_cause"] for r in rep["risks"] if r["level"] == "high"}
    # 好 spec（单一 40px 锚点 + muted 正文 + 无图表）→ 0 high
    good = {"canvas": {"width": 1280, "height": 720}, "theme": theme, "slides": [
        {"id": "g1", "page_intent": pi("好页", "st", "STATEMENT"), "elements": [
            {"type": "text", "id": "st", "x": 240, "y": 312, "width": 800, "height": 96,
             "text": "静水深流", "size": 64, "color": "ink", "align": "center",
             "max_lines": 1}]}]}
    rep2 = di.pre_critic(good)
    ok = ok and rep2["summary"]["high"] == 0
    return {"status": "PASS" if ok else "FAIL",
            "predicted": sorted(want & codes), "false_alarms_good_spec": rep2["summary"]["high"]}


def check_design_dna():
    """Design DNA：召回命中、置信度、record 沉淀回路（自清理）。"""
    di = load("design_intelligence", SCRIPTS / "design_intelligence.py")
    hit = di.recall_dna({"subject": "2026 企业年度总结", "brief": "东方高级 宋氏美学 留白 董事会"})
    ok = (hit["matched"] == "song_elegance_editorial" and hit["confidence"] > 0
          and "朱砂" in json.dumps(hit["dna"], ensure_ascii=False))
    miss = di.recall_dna({"subject": "完全无关的火星探测任务简报"})
    ok = ok and miss["matched"] is None
    # 通用场景词（年度总结）不是水墨特征词：不得把普通年度 deck 召回成水墨经验
    generic = di.recall_dna({"subject": "年度总结", "brief": "2026 年度业绩回顾与预算规划"})
    ok = ok and generic["matched"] != "song_elegance_editorial"
    # v2 判断记忆：合法条目入库；结果记忆（palette/色值/缺 design_problem）拒收
    rec = di.record_dna({"id": "__selftest_dna__", "signature": {"keywords": ["__t__"]},
                         "design_problem": "自测：探索期与契约期的节奏矛盾",
                         "judgment": {"space": "occupancy 0.4-0.6", "media": "图承担情绪不承担信息"},
                         "avoid": ["装饰图片"], "when_not_to": "非自测场景",
                         "proven": {"qa": 99.0}})
    ok = ok and rec["ok"]
    rej1 = di.record_dna({"id": "__bad__", "signature": {"keywords": ["__t__"]},
                          "design_problem": "p", "judgment": {"palette": "蓝色", "space": "s", "media": "m"}})
    rej2 = di.record_dna({"id": "__bad__", "signature": {"keywords": ["__t__"]},
                          "design_problem": "p", "judgment": {"color_behavior": "用 #0D0D0D", "space": "s"}})
    rej3 = di.record_dna({"id": "__bad__", "signature": {"keywords": ["__t__"]},
                          "judgment": {"space": "s", "media": "m"}})
    ok = ok and not rej1["ok"] and not rej2["ok"] and not rej3["ok"]
    ok = ok and not any(e["id"] == "__bad__"
                        for e in json.loads(di.DNA_STORE.read_text(encoding="utf-8"))["entries"])
    hit2 = di.recall_dna({"subject": "__t__ 项目"})
    ok = ok and hit2["matched"] == "__selftest_dna__"
    # 清理自测条目
    store = json.loads(di.DNA_STORE.read_text(encoding="utf-8"))
    store["entries"] = [e for e in store["entries"] if e["id"] != "__selftest_dna__"]
    di.DNA_STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    ok = ok and not any(e["id"] == "__selftest_dna__"
                        for e in json.loads(di.DNA_STORE.read_text(encoding="utf-8"))["entries"])
    # v4.9 V4：拒门递归——嵌套 dict 藏色值、全角＃色值同样拒收
    rej4 = di.record_dna({"id": "__bad__", "signature": {"keywords": ["__t__"]},
                          "design_problem": "p",
                          "judgment": {"space": "s", "media": {"note": "用 #FF0000"}}})
    rej5 = di.record_dna({"id": "__bad__", "signature": {"keywords": ["__t__"]},
                          "design_problem": "p",
                          "judgment": {"space": "用 ＃0D0D0D", "media": "m"}})
    ok = ok and not rej4["ok"] and not rej5["ok"]
    # v4.9 V2：经验库损坏 → record 拒写防整库覆盖毁灭（损坏≠不存在）
    raw = di.DNA_STORE.read_text(encoding="utf-8")
    try:
        di.DNA_STORE.write_text("{ \u635f坏", encoding="utf-8")
        broken = di.record_dna({"id": "__bad__", "signature": {"keywords": ["__t__"]},
                                "design_problem": "p",
                                "judgment": {"space": "s", "media": "m"}})
        ok = ok and not broken["ok"] and "拒绝写入" in broken["reason"]
    finally:
        di.DNA_STORE.write_text(raw, encoding="utf-8")
    ok = ok and bool(json.loads(di.DNA_STORE.read_text(encoding="utf-8"))["entries"])
    return {"status": "PASS" if ok else "FAIL", "matched": hit["matched"],
            "confidence": hit["confidence"]}


def check_layout_search():
    """Layout Search：确定性、排序合理、几何 8 网格对齐。"""
    ls = load("layout_search", SCRIPTS / "layout_search.py")
    intent = {"page_family": "CLOSING", "energy": "high", "density": "sparse"}
    c1 = ls.search(intent, {"title": True, "lead": False, "chart": False}, n=3)
    c2 = ls.search(intent, {"title": True, "lead": False, "chart": False}, n=3)
    ok = (len(c1) == 3 and c1[0]["score"] >= c1[1]["score"] >= c1[2]["score"]
          and c1[0]["archetype"] == "statement_center_stage"
          and c1[0]["rank"] == 1
          and all(set(c) >= {"archetype", "grammar", "score", "breakdown",
                             "elements", "rationale"} for c in c1)
          and json.dumps([{k: v for k, v in c.items() if k != "elapsed_ms"} for c in c1],
                         sort_keys=True, default=str)
          == json.dumps([{k: v for k, v in c.items() if k != "elapsed_ms"} for c in c2],
                        sort_keys=True, default=str))
    grid_ok = all(int(e["x"]) % 8 == 0 and int(e["width"]) % 8 == 0
                  for c in c1 for e in c["elements"])
    ok = ok and grid_ok
    # 数据页：full_width_evidence 应进前三（family fit 加分）
    d = ls.search({"page_family": "DATA", "energy": "medium", "density": "balanced"},
                  {"title": True, "lead": True, "chart": True, "stats": True}, n=3)
    ok = ok and any(c["archetype"] == "full_width_evidence" for c in d)
    return {"status": "PASS" if ok else "FAIL",
            "top_closing": c1[0]["archetype"], "top_closing_score": c1[0]["score"],
            "data_top3": [c["archetype"] for c in d]}


def check_media_and_budgets():
    """媒体决策模型 + 页面质量预算：置信度、理由、route 家族别名。"""
    di = load("design_intelligence", SCRIPTS / "design_intelligence.py")
    hero = di.media_decision({"page_intent": {"page_family": "COVER"}})
    data = di.media_decision({"page_intent": {"page_family": "DATA_STORY"}})
    data_chart = di.media_decision({"page_intent": {"page_family": "DATA_STORY"},
                                    "elements": [{"type": "chart", "id": "c"}]})
    ok = (hero["need_media"] and hero["confidence"] >= 0.9
          and not data["need_media"] and data["confidence"] <= 0.1
          and "图表" in data_chart["reason"] and data_chart["confidence"] <= 0.1)
    b_data = di.quality_budget({"page_intent": {"page_family": "DATA_STORY"}})
    b_hero = di.quality_budget({"page_intent": {"page_family": "COVER"}})
    ok = ok and ("contrast" in b_data["primary"] and "emotional_impact" in b_hero["primary"]
                 and b_data["media"] == "禁止" and b_hero["complexity"] == "high")
    return {"status": "PASS" if ok else "FAIL",
            "hero": (hero["need_media"], hero["confidence"]),
            "data": (data["need_media"], data["confidence"])}


def check_auto_fit():
    """Smart Fit Resolver：opt-in 阶梯吸附、未声明零改动、needs_rewrite。"""
    di = load("design_intelligence", SCRIPTS / "design_intelligence.py")
    spec = {"canvas": {"width": 1280, "height": 720}, "theme": {"colors": {}}, "slides": [
        {"id": "s1", "elements": [
            {"type": "text", "id": "opt", "x": 48, "y": 48, "width": 488, "height": 64,
             "text": "一行肯定放不下的很长很长的标题文字要换行两次", "size": 40,
             "line_height": 1.15, "max_lines": 2, "padding": 8, "auto_fit": True},
            {"type": "text", "id": "noopt", "x": 48, "y": 200, "width": 488, "height": 64,
             "text": "一行肯定放不下的很长很长的标题文字要换行两次", "size": 40,
             "line_height": 1.15, "max_lines": 2, "padding": 8}]}]}
    new, rep = di.apply_fit_ladder(spec)
    opt = new["slides"][0]["elements"][0]
    noopt = new["slides"][0]["elements"][1]
    ok = (rep["applied"] == 1 and opt["padding"] == 0 and opt["line_height"] == 1.05
          and opt["size"] < 40
          and noopt["size"] == 40 and noopt.get("padding") == 8   # 未声明零改动
          and len(rep["items"][0]["steps"]) >= 2)
    # 入参未被修改（纯函数）；没有 auto_fit 时不做无效 deepcopy。
    ok = ok and spec["slides"][0]["elements"][0]["size"] == 40
    plain = {"slides": [{"elements": [{"type": "text", "id": "plain"}]}]}
    same, nofit = di.apply_fit_ladder(plain)
    ok = ok and same is plain and nofit == {"applied": 0, "items": [], "needs_rewrite": []}
    return {"status": "PASS" if ok else "FAIL", "steps": rep["items"][0]["steps"]}


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
        manifest = qa_mod.release_manifest(spec, r)
        ok = ok and manifest["status"] == "PREVIEW_ONLY" and manifest["slide_count"] == 2 \
            and len(manifest["source_spec_hash"]) == 16
        result = {"status": "PASS" if ok else "FAIL", "qa_status": r["status"],
                  "codes": r["failure_codes"], "manifest_status": manifest["status"]}
    return result


def check_single_process_pipeline():
    """规划链只算一次 route，并返回可复用的 bundle。"""
    try:
        pipeline = load("pipeline", SCRIPTS / "pipeline.py")
        need = {"audience": "管理层", "decision": "决定是否继续", "occasion": "季度复盘",
                "design_direction": "evidence_first",
                "slides": ["结论", "证据", "行动"]}
        bundle = pipeline.build_plan_bundle(need)
        pages = bundle.get("pages") or []
        ok = (bundle.get("schema") == "vao-plan-v1"
              and bundle.get("plan", {}).get("pages")
              and len(pages) == len(bundle["plan"]["pages"])
              and bundle["performance"].get("route_calls") == 1
              and bundle["performance"].get("rendered") is False
              and bundle["performance"].get("compiled") is False
              and bundle.get("brief", {}).get("source_hash"))
        return {"status": "PASS" if ok else "FAIL",
                "route_calls": bundle.get("performance", {}).get("route_calls"),
                "pages": len(pages)}
    except Exception as exc:
        return {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}


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
    # 回归：通用 overlap 路径必须真的执行；错误的 _box 参数曾被 TypeError
    # 静默吞掉，导致所有 text/chart/image 重叠检查失效。
    overlap_spec = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
                    "slides": [{"id": "o1", "elements": [
                        {"type": "text", "id": "a", "x": 100, "y": 100,
                         "width": 300, "height": 100, "text": "A", "color": "ink"},
                        {"type": "text", "id": "b", "x": 150, "y": 120,
                         "width": 300, "height": 100, "text": "B", "color": "ink"}]}]}
    overlap_report = guard.check_spec(overlap_spec)
    overlap_detected = any(c.get("rule") == "overlap" for c in overlap_report.get("checks", []))
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "t.pptx"
        rep = comp.compile_deck(spec, out, checks=False)
        names = [sh.name for sh in Presentation(str(out)).slides[0].shapes]
    ok = (not clash and not unprotected and overlap_detected and rep["passed"]
          and names[:2] == ["bg", "bg__protection"] and "t" in names)
    return {"status": "PASS" if ok else "FAIL", "clash": len(clash),
            "overlap_detected": overlap_detected, "z_order": names[:3],
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
    # 通用商业词（品牌/高端/年报）不得把 deck 推给宋体方向——拒绝排版/配色蔓延
    brand_deck = route.plan_deck({"occasion": "品牌发布会",
                                  "slides": ["封面", "产品", "收尾"]})
    benchmark = route.plan_deck({"occasion": "品牌年度报告",
                                 "quality_level": "benchmark",
                                 "design_direction": "Quiet Luxury × Editorial Storytelling",
                                 "slides": ["封面", "证据", "结语"]})
    false_story = route.detect_type("history of the company")
    ok = (fast["page_family"] == "DATA_STORY" and fast["asset"]["decision"] == "none"
          and cover["content_type"] == "cover" and cover["asset"]["decision"] == "required"
          and set(deck.get("intent_interpretation", {})) >= {"explicit", "inferred", "conflicts"}
          and all(set(p.get("intent_interpretation", {})) >= {"explicit", "inferred", "conflicts"}
                  for p in deck.get("pages", []))
          and deck["path"] == "fast" and deck["budget"]["max_asset_calls"] == 2
          and not clash and dens[0] == "sparse" and dens[-1] == "sparse"
          # 缺省方向 = 中性；宋体（editorial_brand）只在显式声明时用
          and brand_deck["design_direction"] == "quiet_minimal"
          # 自由文本方向与 benchmark 质量不得静默降级
          and benchmark["design_direction"] == "editorial_brand"
          and benchmark["quality_level"] == "advanced"
          and benchmark["path"] == "advanced"
          and false_story != "brand_story")
    return {"status": "PASS" if ok else "FAIL", "fast_asset": fast["asset"]["decision"],
            "density_curve": dens, "path": deck["path"],
            "brand_default_direction": brand_deck["design_direction"],
            "benchmark_direction": benchmark["design_direction"],
            "benchmark_quality": benchmark["quality_level"]}


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
        advisory = qa.run_qa(spec, pathlib.Path(d) / "advisory.pptx",
                             render=False, include_advisory=True)
        bad = {**spec, "slides": [{**spec["slides"][0],
                                    "elements": [{**spec["slides"][0]["elements"][0],
                                                   "width": 0}]}]}
        gated = qa.run_qa(bad, pathlib.Path(d) / "gated.pptx",
                          render=False, include_advisory=True)
    perf = r.get("performance") or {}
    keys = {"total_ms", "guard_ms", "compile_ms", "advisory_ms", "render_ms",
            "slides", "risk_items", "render_skipped", "cache_reason",
            "render_cache_reason", "output_attestation_ms", "semantic_compile_view_available",
            "artifact_attested", "provenance_required"}
    gate = (gated.get("risk") or {})
    ok = (keys <= set(perf) and "risk" not in r
          and "pre_critic" not in r
          and "risk" in advisory and "pre_critic" not in advisory
          and gate.get("skipped") is True
          and (gate.get("reason") == "engineering_gate")
          and "preflight" not in r             # 设计建议不属于默认 QA
          and perf["slides"] == 1
          and perf["cache_reason"] in {"cache_miss", "view_and_output_attestation_match"}
          and perf["artifact_attested"] is True
          and isinstance(r.get("compile", {}).get("semantic_compile_view"), str)
          and r.get("compile", {}).get("artifact_sha256") == r.get("compile", {}).get("output_sha256"))
    return {"status": "PASS" if ok else "FAIL",
            "perf": {k: perf.get(k) for k in ("guard_ms", "compile_ms", "render_ms")}}


def check_progressive_qa():
    """Progressive QA：L1 不渲染 / L2 只测关键页且不可发布 / L3 全量；并行度硬上限 2。
    依赖外部渲染器（LibreOffice + pdftoppm）：环境缺席时标 skipped（不美化、不阻塞）。"""
    import tempfile
    from PIL import Image
    if not (shutil.which("soffice") or shutil.which("libreoffice")):
        return {"status": "PASS", "skipped": "no LibreOffice in env"}
    qa = load("qa", SCRIPTS / "qa.py")
    rc = load("render_check", SCRIPTS / "render_check.py")
    route = load("route", SCRIPTS / "route.py")
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
        r1 = qa.run_qa(spec, out, mode="draft",
                        render_dir=pathlib.Path(d) / "r1", qa_level=1, dpi=60)
        r2 = qa.run_qa(spec, out, mode="review",
                        render_dir=pathlib.Path(d) / "r2", qa_level=2, dpi=60)
        r3 = qa.run_qa(spec, out, mode="release",
                        render_dir=pathlib.Path(d) / "r3", qa_level=3, dpi=60)
    cov2 = (r2.get("render") or {}).get("coverage") or {}
    # 子集渲染必须按绝对页码对齐，不能把 s01 的指标串到 s02 上
    aligned = [p["index"] for p in (r2.get("render_evidence") or {}).get("pages") or []]
    ids = [p["slide"] for p in (r2.get("render_evidence") or {}).get("pages") or []]
    v2_codes = set(r2.get("verdict", {}).get("codes") or [])
    ok = (capped and ok_runs
          and r1["performance"]["render_skipped"] and r1["render"]["pages"] == 0
          and r1["status"] in ("PREVIEW_ONLY", "REVISE", "BLOCKED")
          and picked == [1, 3, 4] and r2["render"]["pages"] == 3
          and cov2.get("total_pages") == 4 and not r2["release_eligible"]
          and r2["status"] != "PASS" and aligned == [0, 2, 3] and ids == ["s01", "s03", "s04"]
          and r3["render"]["pages"] == 4 and r3["release_eligible"]
          and ("PIXEL_COVERAGE_PARTIAL" in v2_codes or "PIXEL_COVERAGE_PARTIAL" in
               (r2.get("fixable_codes") or []))
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
    """渲染证据缓存：命中即免进程复用、改一页只重测一页、证据 PNG 仍可复核。
    依赖外部渲染器（LibreOffice + pdftoppm）：环境缺席时标 skipped（不美化、不阻塞）。"""
    import copy
    import shutil
    import tempfile
    import time
    rc = load("render_check", SCRIPTS / "render_check.py")
    comp = load("compiler", SCRIPTS / "compiler.py")
    # 即使没有 LibreOffice，也能验证 PDF 中间产物的完整性戳：旧 metadata
    # 只有 PPTX/renderer/页数时会接受被替换的 PDF，必须安全 miss。
    pdf_attestation = False
    with tempfile.TemporaryDirectory() as pdf_tmp:
        pdf_root = pathlib.Path(pdf_tmp)
        pdf_work = pdf_root / "render"
        pdf_work.mkdir()
        pdfx = pdf_root / "deck.pptx"
        pdff = pdf_work / "deck.pdf"
        renderer_stub = pdf_root / "soffice-stub"
        pdfx.write_bytes(b"pptx")
        pdff.write_bytes(b"pdf-original")
        renderer_stub.write_bytes(b"renderer")
        rc._patch_meta(pdf_work, pdf={"name": pdff.name,
                                      "pptx_sha": rc._file_sha(pdfx),
                                      "pdf_sha": rc._file_sha(pdff),
                                      "renderer": rc.renderer_identity(str(renderer_stub))})
        old_count = rc._pdf_page_count
        rc._pdf_page_count = lambda _path: 1
        try:
            pdf_hit = rc._pdf_is_reusable(pdfx, pdf_work, str(renderer_stub))
            pdff.write_bytes(b"pdf-tampered")
            pdf_miss = rc._pdf_is_reusable(pdfx, pdf_work, str(renderer_stub))
        finally:
            rc._pdf_page_count = old_count
        pdf_attestation = pdf_hit == pdff and pdf_miss is None
    if not (shutil.which("soffice") or shutil.which("libreoffice")):
        return {"status": "PASS" if pdf_attestation else "FAIL",
                "skipped": "no LibreOffice in env", "pdf_attestation": pdf_attestation}
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
    ok = (pdf_attestation
          and cold["rendered"] and cold["coverage"]["cache_misses"] == 2
          and warm["rendered"] and warm["coverage"]["cache_hits"] == 2
          and warm["coverage"]["cache_misses"] == 0 and warm["coverage"]["workers"] == 0
          and warm_ms < 900 and all(p.get("cached") for p in warm["pages"])
          and inc["coverage"]["cache_hits"] == 1 and inc["coverage"]["cache_misses"] == 1
          and [p["slide"] for p in inc["pages"]] == ["s01", "s02"]
          and [bool(p.get("cached")) for p in inc["pages"]] == [True, False]
          and pngs_kept and metrics_same and len(entries) == 2)   # 旧键被裁掉，缓存不会无限增长)
    return {"status": "PASS" if ok else "FAIL", "warm_ms": round(warm_ms),
            "pdf_attestation": pdf_attestation,
            "cold_misses": cold["coverage"]["cache_misses"],
            "incremental": [(p["slide"], bool(p.get("cached"))) for p in inc["pages"]],
            "entries": len(entries), "pngs_kept": pngs_kept, "metrics_same": metrics_same}


def check_render_request_bounds():
    """渲染请求边界：空集/全越界只能 SKIPPED，不得宣称 rendered=True。"""
    import tempfile
    rc = load("render_check_bounds", SCRIPTS / "render_check.py")
    spec = {"canvas": {"width": 1280, "height": 720},
            "slides": [{"id": "s01", "elements": []}]}
    with tempfile.TemporaryDirectory() as d:
        empty = rc.render_evidence(pathlib.Path(d) / "missing.pptx", spec,
                                   pathlib.Path(d) / "render", pages=[])
        invalid = rc.render_evidence(pathlib.Path(d) / "missing.pptx", spec,
                                     pathlib.Path(d) / "render2", pages=[0, 99, True])
    ok = (empty.get("rendered") is False and empty.get("skipped") is True
          and empty.get("coverage", {}).get("rendered_pages") == 0
          and invalid.get("rendered") is False and invalid.get("skipped") is True
          and invalid.get("coverage", {}).get("invalid_requested") == [0, 99, True])
    return {"status": "PASS" if ok else "FAIL",
            "empty_rendered": empty.get("rendered"),
            "invalid_rendered": invalid.get("rendered"),
            "invalid_requested": invalid.get("coverage", {}).get("invalid_requested")}


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
        metrics = {"brightness": 0.5, "edge": 0.1, "occupancy": 0.2,
                   "margin_occupancy": 0.1, "saliency_centroid": [0.5, 0.5],
                   "accent_pixel_ratio": 0.01, "saturated_pixel_ratio": 0.02,
                   "background_luma": 0.9, "optical_alignment": {}}
        entry_ok = {"png": a.name, "png_sha": sha_a, **metrics}
        same_exists_other_content = {"png": a.name, "png_sha": rc._file_sha(b), **metrics}
        legacy = {"png": a.name}                                   # 旧格式：无指纹/证据字段
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
    prim = load("primitives", SCRIPTS / "primitives.py")
    cw, ch = 1920, 1080
    smuggle = {"type": "image", "id": "sneak", "x": 96, "y": 380, "width": 1088,
               "height": 200, "layer": "background",
               "overlay": {"type": "solid", "color": "#000000", "opacity": 0.1}}
    legit = {"type": "image", "id": "bg", "x": 0, "y": 0, "width": 1920, "height": 1080,
             "layer": "background", "overlay": {"type": "solid", "color": "#000000",
                                                "opacity": 0.6}}
    bare = {"type": "image", "id": "bare", "x": 0, "y": 0, "width": 1920, "height": 1080,
            "layer": "background"}
    s_ok, s_why = prim.background_layer_ok(smuggle, cw, ch)
    l_ok, _ = prim.background_layer_ok(legit, cw, ch)
    b_ok, b_why = prim.background_layer_ok(bare, cw, ch)
    declared_only = prim.is_background_layer(smuggle) and not prim.bg_exempt(smuggle, cw, ch)
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
    disguised = [c for c in g["checks"] if "BACKGROUND_DISGUISED" in str(c.get("id"))]
    from design_intelligence import pre_critic as _pc
    _risks = _pc(spec)["risks"]
    media_over = [r for r in _risks if r["code"] in ("MEDIA_MISUSE_RISK", "MEDIA_BUDGET_RISK")]
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
    # 同一份证据只有一个出口：QA 判 fail/error（READABILITY_FAIL）
    prim = load("primitives", SCRIPTS / "primitives.py")
    qa_verdict = prim.text_contrast_verdict(
        dict(m_bad, slide="s01"), qa.DEFAULT_THRESHOLDS["text_contrast_fail"],
        qa.DEFAULT_THRESHOLDS["text_contrast_warn"])
    ok = (tc_bad is not None and tc_bad < 1.5 and tc_good is not None and tc_good > 10
          and qa_verdict["level"] == "fail"
          and qa.DEFAULT_THRESHOLDS["text_contrast_fail"] == 3.0
          and qa.DEFAULT_THRESHOLDS["text_contrast_warn"] == 4.5
          and "render_contrast" in qa.DEFAULT_PENALTIES)
    return {"status": "PASS" if ok else "FAIL", "dark_ratio": tc_bad,
            "light_ratio": tc_good,
            "qa_level_verdict": qa_verdict["level"]}


def check_element_schema():
    """F4/v4.16：元素级字段形态前置拦截——「看似合理的对象形态」
    （color/fill/bg 传 dict/bool）让编译期 unhashable 失色，spec 档必须当场 error。
    根因同族于 F1（未知 type 静默）与 F2（脏 rules 裸炸）：脏字段形态的静默成本。"""
    guard = load("guard", SCRIPTS / "guard.py")

    def _s(elements, bg=None):
        sl = {"id": "s01", "page_intent": {"insight": "A", "focus": "t", "density": "sparse"}}
        if bg is not None:
            sl["background"] = bg
        sl["elements"] = elements
        return {"slides": [sl]}

    dirty_color = guard.check_spec(_s([{"type": "text", "id": "t", "size": 14,
                                        "color": {"hex": "#111111"}}]))
    dirty_fill = guard.check_spec(_s([{"type": "shape", "id": "t", "fill": True}]))
    dirty_bg = guard.check_spec(_s([{"type": "text", "id": "t", "size": 14}],
                                    {"color": {"hex": "#FFFFFF"}}))
    clean = guard.check_spec(_s([{"type": "text", "id": "t", "text": "标题", "size": 14,
                                  "color": "#111111", "x": 96, "y": 80,
                                  "width": 800, "height": 40}], {"color": "#F3F1EA"}))

    def _es(o):
        return [w for w in o.get("warnings", []) if w.startswith("[element_schema]")]

    ok = (any("配色须为" in w for w in _es(dirty_color))
          and any("fill 须为" in w for w in _es(dirty_fill))
          and any("background.color" in w for w in _es(dirty_bg))
          and dirty_color.get("passed") is False and dirty_fill.get("passed") is False
          and dirty_bg.get("passed") is False
          and not _es(clean))
    return {"status": "PASS" if ok else "FAIL",
            "color_hits": len(_es(dirty_color)), "fill_hits": len(_es(dirty_fill)),
            "bg_hits": len(_es(dirty_bg))}


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
    # 行长「建议值」是编辑观点（typography / advisory）；超出 fail factor 是内容被切断
    # 的事实 → 归 text_capacity，可阻断（重定性）。
    cap_err = [c for c in g["checks"] if c["rule"] == "text_capacity" and c["level"] == "error"]
    typo_warn = [c for c in g["checks"] if c["rule"] == "typography" and c["level"] == "warn"]
    lm_stats = g.get("line_measure") or {}
    ok = (over and over["over"] and not over["fatal"] and fatal and fatal["fatal"]
          and aux is None and ok_case and not ok_case["over"]
          and len(cap_err) == 1 and "b" in cap_err[0]["id"] and len(typo_warn) == 1
          and lm_stats.get("checked") == 2 and lm_stats.get("over") == 2
          and (g.get("grid") or {}).get("adherence") is not None)
    return {"status": "PASS" if ok else "FAIL", "over": bool(over and over["over"]),
            "fatal_blocked": len(cap_err), "warn": len(typo_warn),
            "grid_adherence": (g.get("grid") or {}).get("adherence")}


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
    mismatch = json.loads(json.dumps(spec))
    mismatch["slides"][0]["elements"][0]["series"][1]["values"] = [2, 3]
    gm = guard.check_spec(mismatch)
    guard_ok = ("data_integrity" not in codes and "chart_highlight" not in codes
                and "缺少 data" not in msgs
                and any("长度" in c.get("msg", "") for c in gm.get("checks", [])))
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "m.pptx"
        rep = comp.compile_deck(spec, out, checks=False)
    render_ok = rep["passed"] and "已跳过" not in "\n".join(rep["warnings"])
    return {"status": "PASS" if (guard_ok and render_ok) else "FAIL",
            "guard_ok": guard_ok, "render_ok": render_ok,
            "length_mismatch_blocked": guard_ok}


def check_compile_cache_projection():
    """轻量编译缓存与渲染缓存保持同一像素投影，且不拖入渲染依赖。"""
    import ast
    import tempfile
    cc = load("compile_cache_contract", SCRIPTS / "compile_cache.py")
    rc = load("render_check_contract", SCRIPTS / "render_check.py")
    tree = ast.parse((SCRIPTS / "compile_cache.py").read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    imported = set()
    for node in imports:
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        else:
            imported.add(node.module or "")
    spec = {"canvas": {"width": 1280, "height": 720},
            "theme": {"colors": {"background": "#fff", "ink": "#111"},
                      "constraints": {"max_colors": 5}, "notes": "not pixels"},
            "slides": [{"id": "s01", "page_intent": {"insight": "A"},
                        "notes": "not pixels", "elements": [{"type": "text", "x": 10,
                        "y": 20, "width": 100, "height": 40, "text": "A"}]}]}
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        pptx = work / "deck.pptx"
        pptx.write_bytes(b"pptx-bytes")
        view_a = cc.spec_view(spec, base_path=work)
        view_b = rc.spec_view(spec, base_path=work)
        import hashlib
        report = {"passed": True, "slides": 1, "warnings": [],
                  "output_sha256": hashlib.sha256(b"pptx-bytes").hexdigest(),
                  "output_path": str(pptx), "guard": {"x": 1}}
        cc.record_compile(work, pptx, view_a, report)
        meta_compile = json.loads((work / cc.RENDER_META_NAME).read_text(encoding="utf-8")).get("compile", {})
        semantic_meta = meta_compile.get("semantic_view") == view_a
        hit = cc.compile_reuse(work, pptx, view_a)
        pptx.write_bytes(b"changed")
        miss_after_change = cc.compile_reuse(work, pptx, view_a) is None
        asset_root = work / "build-assets"
        asset_root.mkdir()
        media = asset_root / "media.png"
        media.write_bytes(b"1111")
        fixed = 1700000000
        import os as _os
        _os.utime(media, (fixed, fixed))
        media_spec = {"canvas": spec["canvas"], "slides": [{"id": "s01",
            "elements": [{"type": "image", "src": "media.png"}]}]}
        # output_dir 与 build module 目录不同：spec_path 必须让缓存看到真实素材，
        # 否则「缺失」会被错误地写进 view，后续图片替换也无法可靠失效。
        media_missing = cc.spec_view(media_spec, base_path=work)
        media_a = cc.spec_view(media_spec, base_path=work,
                               spec_path=asset_root / ("build" + ".py"))
        media.write_bytes(b"2222")
        _os.utime(media, (fixed, fixed))
        media_b = cc.spec_view(media_spec, base_path=work,
                               spec_path=asset_root / ("build" + ".py"))
        (work / cc.RENDER_META_NAME).write_text("[truncated", encoding="utf-8")
        cc.record_compile(work, pptx, view_a, report)
        metadata_valid = isinstance(json.loads((work / cc.RENDER_META_NAME).read_text()), dict)
        renderer = work / "renderer"
        renderer.write_bytes(b"v1")
        renderer_a = rc.renderer_identity(str(renderer))
        renderer.write_bytes(b"v2-upgraded")
        renderer_b = rc.renderer_identity(str(renderer))
    ok = (view_a == view_b and semantic_meta and hit and hit.get("reused") is True
          and miss_after_change and media_missing != media_a and media_a != media_b
          and metadata_valid and renderer_a != renderer_b
          and imported <= {"__future__", "hashlib", "json", "os",
                           "pathlib", "tempfile"})
    return {"status": "PASS" if ok else "FAIL", "same_view": view_a == view_b,
            "reuse_hit": bool(hit), "semantic_view_recorded": semantic_meta,
            "media_content_collision_rejected": media_a != media_b,
            "media_spec_path_resolved": media_missing != media_a,
            "metadata_atomic_recovered": metadata_valid, "renderer_upgrade_rejected": renderer_a != renderer_b,
            "imports": sorted(imported)}


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
                     for m in ("compiler.py", "primitives.py"))
    treads = set(re.findall(r"theme\.get\(['\"]([a-z_]+)['\"]", tsrc))
    tleak = treads & set(rc.NON_PIXEL_THEME_KEYS)
    ok = (base == same and base != focus_moved and base != pixel_moved and view_same
          and view_px and view_media and not leak and not tleak
          and bool(reads & {"background", "elements"}))
    return {"status": "PASS" if ok else "FAIL", "compiler_slide_keys": sorted(reads),
            "leaked_slide_keys": sorted(leak), "leaked_theme_keys": sorted(tleak)}
def check_manifest_attestation():
    """发布清单不得承认来历不明的报告：戳不符 / 无戳却称 PASS / 幽灵页面 → BLOCKED。
    （v4.15 单引擎：攻击面只剩 qa_report——证明链口径一律按 QA 报告走。）"""
    import hashlib
    import os
    import tempfile
    prim = load("primitives", SCRIPTS / "primitives.py")
    qa = load("qa", SCRIPTS / "qa.py")
    spec = {"canvas": {"width": 1280, "height": 720}, "slides": [{"id": "s01"}, {"id": "s02"}]}
    fp = prim.spec_fingerprint(spec)
    stable = fp == prim.spec_fingerprint({"slides": [{"id": "s01"}, {"id": "s02"}],
                                          "canvas": {"height": 720, "width": 1280},
                                          })
    differs = fp != prim.spec_fingerprint({**spec, "slides": [{"id": "s01"}]})
    fd, output_name = tempfile.mkstemp(prefix="manifest-attest-", suffix=".pptx")
    os.close(fd)
    output_path = pathlib.Path(output_name)
    output_path.write_bytes(b"editable-pptx-attestation")
    output_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
    good_qa = {"status": "PASS", "source_spec_hash": fp, "release_eligible": True,
               "execution": {"mode": "release"},
               "performance": {"qa_level": 3},
               "compile": {"passed": True, "output_path": str(output_path),
                           "output_sha256": output_sha},
               "render": {"rendered": True,
                          "coverage": {"rendered_pages": 2, "total_pages": 2,
                                       "rendered_ids": ["s01", "s02"]}},
               "render_evidence": {"rendered": True,
                                   "pages": [{"slide": "s01"}, {"slide": "s02"}]}}
    m0 = qa.release_manifest(spec, good_qa)
    m1 = qa.release_manifest(spec, {**good_qa, "render_evidence": {
        "pages": [{"slide": "s01"}, {"slide": "s02"}, {"slide": "ghost"}]}})
    m2 = qa.release_manifest(spec, {**good_qa, "source_spec_hash": "deadbeef00000000"})
    m3 = qa.release_manifest(spec, {k: v for k, v in good_qa.items() if k != "source_spec_hash"})
    m4 = qa.release_manifest(spec, {**good_qa, "release_eligible": False})
    try:
        output_path.unlink(missing_ok=True)
    except OSError:
        pass
    ok = (stable and differs and m0["status"] == "PASS" and not m0["validation"]["issues"]
          and m1["status"] == "BLOCKED" and m2["status"] == "BLOCKED"
          and m3["status"] == "BLOCKED" and m4["status"] == "BLOCKED"
          and m0["source_spec_hash"] == fp
          and "critic_report" not in m0)
    return {"status": "PASS" if ok else "FAIL", "clean": m0["status"],
            "ghost": m1["status"], "stale": m2["status"],
            "unstamped_pass": m3["status"], "ineligible_pass": m4["status"],
            "output_attestation": bool(good_qa["compile"].get("output_sha256"))}


def check_optical_alignment():
    """渲染级光学对齐复核：声明轴线的视觉峰位与数学坐标一致/偏移的数学正确性。"""
    import tempfile
    from PIL import Image, ImageDraw
    rc = load("render_check", SCRIPTS / "render_check.py")
    cw, ch = 320, 180
    slide = {"id": "s01", "elements": [
        {"type": "shape", "shape": "rect", "id": "a", "x": 40, "y": 40, "width": 80, "height": 60},
        {"type": "chart", "id": "b", "chart": "ranked_bar", "x": 160, "y": 40, "width": 100, "height": 100},
        {"type": "image", "id": "c", "x": 40, "y": 120, "width": 60, "height": 40},
    ]}
    lines = rc.declared_alignment_lines(slide, cw, ch)
    ok = len(lines["x"]) >= 4 and len(lines["y"]) >= 3

    def render(shift):
        with tempfile.TemporaryDirectory() as td:
            png = pathlib.Path(td) / "p.png"
            im = Image.new("RGB", (cw, ch), (255, 255, 255))
            d = ImageDraw.Draw(im)
            for (x, y, w, h) in [(40, 40, 80, 60), (160, 40, 100, 100), (40, 120, 60, 40)]:
                d.rectangle([x + shift, y + shift, x + w + shift, y + h + shift],
                            fill=(20, 20, 20))
            im.save(png)
            return rc.optical_alignment(png, slide, cw, ch).get("optical_alignment", {})

    good = render(0)
    bad = render(5)
    ok = ok and good.get("lines_checked", 0) >= 3 and good.get("aligned_share", 0) >= 0.9
    ok = ok and bad.get("aligned_share", 1.0) <= 0.5 and bad.get("max_shift_px", 0) >= 4.0
    # 无边界元素（纯文字页）→ 不产生度量（没有可验证的声明轴线）
    text_only = {"id": "s02", "elements": [
        {"type": "text", "id": "t", "x": 40, "y": 40, "width": 200, "height": 60}]}
    ok = ok and rc.optical_alignment(pathlib.Path("/nonexistent.png"), text_only, cw, ch) == {}
    return {"status": "PASS" if ok else "FAIL",
            "lines": {"x": len(lines["x"]), "y": len(lines["y"])},
            "aligned_good": good.get("aligned_share"),
            "aligned_shifted": bad.get("aligned_share"),
            "max_shift_px": bad.get("max_shift_px")}


def check_chart_color_roles():
    """Chart Color Role System：角色→主题映射链、旧扁平键兼容、负值兜底、元素 color_role。"""
    prim = load("primitives", SCRIPTS / "primitives.py")
    charts = load("compiler", SCRIPTS / "compiler.py")
    theme = {"colors": {"ink": "#111111", "primary": "#222222", "secondary": "#333333",
                        "muted": "#777777", "accent": "#AA0000", "risk": "#B00020"},
             "chart_palette": {"primary": "primary", "secondary": "accent",
                               "neutral": "muted", "accent": "accent", "negative": "risk"}}
    ctx = prim.RenderContext(theme, {})
    ok = (str(ctx.chart_role("negative")) == "B00020"
          and str(ctx.chart_role("primary")) == "222222"
          and str(ctx.chart_role("accent")) == "AA0000"
          and ctx.chart_role("bogus") is None)
    # 旧扁平键向后兼容（未声明 chart_palette 的主题仍走 chart_primary 等）
    legacy = {"colors": {"ink": "#111111", "primary": "#222222",
                         "secondary": "#333333", "accent": "#AA0000"},
              "chart_primary": "primary", "chart_secondary": "secondary"}
    ctx2 = prim.RenderContext(legacy, {})
    ok = ok and str(ctx2.chart_role("primary")) == "222222"
    # 未声明 negative → 通用风险红兜底 + 告警（最后手段，不是设计建议）
    ctx3 = prim.RenderContext({"colors": {"ink": "#111111", "accent": "#AA0000"}}, {})
    neg = ctx3.chart_role("negative")
    ok = ok and neg is not None and any("negative" in w for w in ctx3.warnings)
    # 元素声明 color_role 取代色值；显式色值逃生口仍在
    p, _s, _i, _m = charts.chart_colors({"color_role": "negative"}, ctx)
    p2, _s2, _i2, _m2 = charts.chart_colors({"primary_color": "#123456"}, ctx)
    ok = ok and str(p) == "B00020" and str(p2) == "123456"
    return {"status": "PASS" if ok else "FAIL", "negative_role": str(neg),
            "role_override": str(p)}


def check_brand_seed():
    """Color Intelligence 入口：brief.brand_colors 品牌优先覆盖方向预设。"""
    route = load("route", SCRIPTS / "route.py")
    preset = {"colors": {"accent": "#111111", "paper": "#FFFFFF"},
              "fonts": {"cn": "Source Han Serif", "latin": "Inter"}}
    brand = route._seed_from_brand(preset, {"accent": "#C8A24B", "primary": "#0F2B46"})
    ok = (brand["colors"]["accent"] == "#C8A24B"
          and brand["colors"]["primary"] == "#0F2B46"
          and brand["colors"]["paper"] == "#FFFFFF"
          and brand.get("brand_derived") is True)
    bad = route._seed_from_brand(preset, {"accent": "gold", "junk": "#12"})
    ok = ok and bad["colors"]["accent"] == "#111111" and "junk" not in bad["colors"]
    ok = ok and route._seed_from_brand(preset, None) is preset
    plan = route.plan_deck({"subject": "企业年度总结", "brief": "发布终版 董事会汇报",
                            "brand_colors": {"accent": "#C8A24B"}})
    ok = ok and plan["theme"]["colors"]["accent"] == "#C8A24B"
    return {"status": "PASS" if ok else "FAIL", "brand_accent": brand["colors"]["accent"],
            "plan_deck_theme_accent": plan["theme"]["colors"]["accent"]}


def check_layout_recommend():
    """两层布局决策：标准家族直达原型，复杂页（未分类/多焦点）才搜索。"""
    ls = load("layout_search", SCRIPTS / "layout_search.py")
    r1 = ls.recommend({"page_family": "DATA", "insight": "增长加速", "focus": "chart1"})
    ok = (r1["tier"] == "family" and r1["archetype"] == "full_width_evidence"
          and len(r1["elements"]) >= 3 and "note" in r1)
    r2 = ls.recommend({"page_family": None, "insight": "x"})
    ok = ok and r2["tier"] == "search" and len(r2["candidates"]) == 3
    r3 = ls.recommend({"page_family": "HERO", "secondary_focus": "logo"})
    ok = ok and r3["tier"] == "search" and "多焦点" in r3["reason"]
    r4 = ls.recommend({"page_family": "CLOSING", "focus": "st"})
    ok = ok and r4["tier"] == "family" and r4["archetype"] == "statement_center_stage"
    # 内容家族经归一层同样直达（COVER/DATA_STORY/TIMELINE 是真实项目的命名）
    r5 = ls.recommend({"page_family": "DATA_STORY", "focus": "c"})
    r6 = ls.recommend({"page_family": "TIMELINE", "focus": "tl"})
    ok = ok and r5["tier"] == "family" and r5["archetype"] == "full_width_evidence" \
        and r6["tier"] == "family" and r6["archetype"] == "quiet_progression"
    return {"status": "PASS" if ok else "FAIL", "data_fast_path": r1["archetype"],
            "complex_reason": r2["reason"],
            "content_family_fast_path": [r5["archetype"], r6["archetype"]]}


def check_pre_critic_v2():
    """v2.12 预测扩展：平衡/字阶/布局单调/记忆线/字阶漂移——渲染后才看见的，生成前点名。"""
    di = load("design_intelligence", SCRIPTS / "design_intelligence.py")
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "primary": "#222222",
                        "secondary": "#333333", "accent": "#AA0000", "muted": "#777777"}}

    def slide(sid, family, sizes, token):
        els = [{"type": "text", "id": f"t{k}", "x": 48, "y": 100 + k * 90,
                "width": 400, "height": 64, "text": f"文{k}", "size": s,
                "color": "ink", "max_lines": 1} for k, s in enumerate(sizes)]
        return {"id": sid,
                "page_intent": {"insight": sid, "focus": "t0", "reading_order": ["t0"],
                                "energy": "medium", "density": "balanced",
                                "empty_space_role": "protect_focus", "page_family": family,
                                "rhythm_stage": "body", "continuity_token": token},
                "elements": els}

    spec = {"canvas": {"width": 1280, "height": 720}, "theme": theme, "slides": [
        slide("m1", "DATA_STORY", [32, 22], "T"),            # 左侧堆叠 → 平衡
        slide("m2", "DATA_STORY", [64, 44, 32, 22, 17], "T"),  # 5 级 → 页级字阶
        slide("m3", "DATA_STORY", [30, 20], "X"),            # X 单次 → 记忆线断裂
        slide("m4", "TIMELINE", [26, 18], "T"),
        slide("m5", "TIMELINE", [40, 15], "T")]}             # 全 deck >8 字号 → 漂移
    rep = di.pre_critic(spec)
    codes = {r["code"] for r in rep["risks"]}
    want = {"BALANCE_SKEW_RISK", "TYPE_LADDER_RISK", "LAYOUT_MONOTONE_RISK",
            "CONTINUITY_BROKEN_RISK", "TYPE_SCALE_DRIFT_RISK"}
    ok = want <= codes and all(r.get("prevention") and r.get("root_cause")
                               for r in rep["risks"])
    # m2（5 个元素）打断指纹连续 → m3–m5 三连报单调；字号不入指纹，m1/m3/m4/m5 同指纹
    mono = next(r for r in rep["risks"] if r["code"] == "LAYOUT_MONOTONE_RISK")
    ok = ok and mono["slides"] == ["m3", "m4", "m5"]
    drift = next(r for r in rep["risks"] if r["code"] == "TYPE_SCALE_DRIFT_RISK")
    ok = ok and drift["slides"] == []         # deck 级风险不点名页
    # 声明型家族豁免：全左堆叠的 STATEMENT 页不报平衡（刻意偏轴是语言）
    exempt = {"canvas": {"width": 1280, "height": 720}, "theme": theme, "slides": [
        slide("e1", "MINIMAL_STATEMENT", [64], "T"),
        slide("e2", "MINIMAL_STATEMENT", [64], "T"),
        slide("e3", "MINIMAL_STATEMENT", [64], "T"),
        slide("e4", "DATA_STORY", [32], "T2")]}
    rep2 = di.pre_critic(exempt)
    ok = ok and not any(r["code"] == "BALANCE_SKEW_RISK" for r in rep2["risks"])
    return {"status": "PASS" if ok else "FAIL",
            "new_codes": sorted(want & codes),
            "monotone_pages": len(mono["slides"])}


def check_intent_style():
    """F5/v4.16：审美风格覆写层订阅命名通道——东方/电影/静奢词族命中
    song_elegance/cinematic_narrative/quiet_luxury 的 family_hint；
    occasion 语义不被覆写污染；确定性（同输入同 Brief）。"""
    import importlib.util as iu, hashlib, json
    spec = iu.spec_from_file_location("intent_compiler", SCRIPTS / "intent_compiler.py")
    ic = iu.module_from_spec(spec)
    import sys as _s
    _s.modules["intent_compiler"] = ic
    spec.loader.exec_module(ic)
    east = ic.compile_brief("2026 年终总结：沉浸式电影感 × 现代东方设计。留白。")
    cin = ic.compile_brief("年度发布会纪录片：镜头感强、胶片质感")
    lux = ic.compile_brief("安静奢华的品牌叙事")
    board = ic.compile_brief("董事会战略汇报：三个新市场竞局分析")
    h = lambda b: hashlib.sha256(json.dumps(b, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    ok = (east["direction_seed"].get("family_hint") == "song_elegance"
          and east["direction_seed"].get("style_key") == "eastern_ink"
          and "sumi-e" in east["direction_seed"]["visual_world"]
          and cin["direction_seed"].get("family_hint") == "cinematic_narrative"
          and cin["direction_seed"]["background_scene"] == "cinematic"
          and lux["direction_seed"].get("family_hint") == "quiet_luxury"
          and "accent spam" in (lux["direction_seed"].get("avoid") or [])
          and board["direction_seed"].get("family_hint") is None
          and h(ic.compile_brief("2026 年终总结：沉浸式电影感 × 现代东方设计。留白。")) == h(east))
    return {"status": "PASS" if ok else "FAIL",
            "east": east["direction_seed"].get("family_hint"),
            "cin": cin["direction_seed"].get("family_hint"),
            "lux": lux["direction_seed"].get("family_hint"),
            "board_plain": board["direction_seed"].get("family_hint") is None}


def check_intent_boundaries():
    """F7/v4.17：ASCII 词走词边界——frozen/citizen/dozen 内含 zen、
    history 内含 story、onboard 内含 board，不得触发东方覆写或
    错误场合；真实词命中（zen garden / 水墨 / history 显式 story）保持。"""
    import importlib.util as iu
    spec = iu.spec_from_file_location("intent_compiler", SCRIPTS / "intent_compiler.py")
    ic = iu.module_from_spec(spec)
    import sys as _s
    _s.modules["intent_compiler"] = ic
    spec.loader.exec_module(ic)
    frozen = ic.compile_brief("Quarterly review of frozen assets across a dozen markets")
    citizen = ic.compile_brief("Citizen engagement survey results")
    history = ic.compile_brief("A brief history of the firm and its capital structure")
    onboard = ic.compile_brief("Onboarding plan for new hires, quarterly cadence")
    zen = ic.compile_brief("Launch keynote for our zen garden wellness app")
    ink = ic.compile_brief("2026 年终总结：东方水墨气质，大量留白")
    ws = ic.compile_brief("希望版面留白多一点，重点突出")
    plain = ic.compile_brief("希望整体素雅一点，干净大方")
    ok = (frozen["direction_seed"].get("style_key") is None
          and "sumi-e" not in frozen["design_intent"]["visual_world"]
          and citizen["direction_seed"].get("style_key") is None
          and history["design_intent"]["visual_world"].startswith("quiet editorial")
          and onboard["design_intent"]["visual_world"].startswith("quiet editorial")
          and zen["direction_seed"].get("family_hint") == "song_elegance"
          and ink["direction_seed"].get("family_hint") == "song_elegance"
          # 「留白」是通用排版术语：不得触发水墨覆写（拒绝「生成的都是水墨」）
          and ws["direction_seed"].get("family_hint") is None
          # 「素雅/素净」是通用审美词：不得触发静奢覆写（拒绝风格蔓延）
          and plain["direction_seed"].get("family_hint") is None)
    return {"status": "PASS" if ok else "FAIL",
            "frozen": frozen["direction_seed"].get("style_key"),
            "citizen": citizen["direction_seed"].get("style_key"),
            "history_world": history["design_intent"]["visual_world"][:30],
            "zen": zen["direction_seed"].get("family_hint"),
            "ink": ink["direction_seed"].get("family_hint"),
            "whitespace_hint": ws["direction_seed"].get("family_hint"),
            "plain_hint": plain["direction_seed"].get("family_hint")}


def check_ink_gate():
    """F6/v4.17：水墨纪律闸门——选择了水墨语言的资产卡注入
    工艺纪律（正向）+ 廉价症状（反向）；非水墨卡零污染；
    song_elegance 家族名自动点火（zen_minimal 非水墨家族，不点火）；
    重复注入去重。"""
    import importlib.util as iu
    spec = iu.spec_from_file_location("asset_prompt", SCRIPTS / "asset_prompt.py")
    ap = iu.module_from_spec(spec)
    import sys as _s
    _s.modules["asset_prompt"] = ap
    spec.loader.exec_module(ap)
    ink_card = {"apc": "APC-INK-01", "asset_type": "background",
                "subject": ["ink mountain ridge above drifting mist"],
                "color": ["ink black and vermilion on rice paper"],
                "material": ["Chinese ink-wash on rice paper"],
                "lighting": ["dawn haze"],
                "composition": ["ridge line entering from lower right"]}
    out = ap.build_asset_prompt(ink_card)
    fam_card = dict(ink_card, family="song_elegance",
                    subject=["distant ridge"], material=["mineral pigment"],
                    color=["bone and ink"])
    fam_out = ap.build_asset_prompt(fam_card)
    neutral = {"apc": "APC-ABS-01", "asset_type": "background",
               "subject": ["abstract vertical gradient field"],
               "color": ["deep graphite"], "material": ["matte surface"],
               "lighting": ["soft top light"], "composition": ["asymmetric bands"]}
    neutral_out = ap.build_asset_prompt(neutral)
    p, n = out["prompt"].lower(), out["negative"].lower()
    ok = ("shui-mo" in p and "single deliberate brushwork" in p
          and "three to four values" in p
          and "no photographic landscape" in n
          and "no muddy gray ink pooling" in n and "no clip-art bamboo" in n
          and p.count("shui-mo") == 1
          and ap.ink_gate_active(ink_card)
          and "shui-mo" in fam_out["prompt"].lower()
          and not ap.ink_gate_active(neutral)
          # zen_minimal 是「东方禅意极简」非水墨：不自动点火（拒绝水墨蔓延）
          and not ap.ink_gate_active({"family": "zen_minimal", "subject": ["still water"]})
          and "shui-mo" not in neutral_out["prompt"].lower()
          and "photographic landscape" not in neutral_out["negative"].lower())
    return {"status": "PASS" if ok else "FAIL",
            "ink_injected": "shui-mo" in p,
            "rejects_injected": "no clip-art bamboo" in n,
            "fam_trigger": "shui-mo" in fam_out["prompt"].lower(),
            "neutral_clean": "shui-mo" not in neutral_out["prompt"].lower()}


def check_geometry_degenerate():
    """F8/v4.18：geometry 是元素存在的前提——缺 x/y/width/height（静默按 0）、
    ≤0、非数值，渲染后元素不可见，修复前只报编译 -1.5 warn。
    现在 element_schema 族 error 级前置拦截；full-bleed 与正常几何不受影响。"""
    import importlib.util as iu
    spec = iu.spec_from_file_location("guard", SCRIPTS / "guard.py")
    g = iu.module_from_spec(spec)
    import sys as _s
    _s.modules["guard"] = g
    spec.loader.exec_module(g)

    def _mk(elements):
        return g.check_spec({"slides": [{"id": "s01",
            "page_intent": {"insight": "A", "focus": "t", "density": "sparse"},
            "background": {"color": "#F3F1EA"}, "elements": elements}]})

    def _es(out):
        return [w for w in out.get("warnings", []) if "element_schema" in w]

    base = {"type": "text", "id": "t", "text": "内容必须被看见", "size": 14,
            "color": "#111111", "x": 96, "y": 80}
    miss = _mk([dict(base)])
    zero = _mk([dict(base, width=0, height=40)])
    neg = _mk([dict(base, width=300, height=-8)])
    nonnum = _mk([dict(base, width="300px", height=40)])
    nan = _mk([dict(base, x=float("nan"), width=300, height=40)])
    inf = _mk([dict(base, y=float("inf"), width=300, height=40)])
    boolean = _mk([dict(base, x=True, width=300, height=40)])
    good = _mk([dict(base, width=800, height=40)])
    miss_xy = _mk([{k: v for k, v in dict(base, width=800, height=40).items()
                    if k not in ("x", "y")}])
    ok = (any("geometry 缺项" in w for w in _es(miss)) and miss.get("passed") is False
          and any("geometry 缺项" in w for w in _es(miss_xy)) and miss_xy.get("passed") is False
          and any("geometry 退化" in w for w in _es(zero)) and zero.get("passed") is False
          and any("geometry 退化" in w for w in _es(neg)) and neg.get("passed") is False
          and any("非数值" in w for w in _es(nonnum)) and nonnum.get("passed") is False
          and any("非数值" in w for w in _es(nan)) and nan.get("passed") is False
          and any("非数值" in w for w in _es(inf)) and inf.get("passed") is False
          and any("非数值" in w for w in _es(boolean)) and boolean.get("passed") is False
          and not _es(good))
    return {"status": "PASS" if ok else "FAIL",
            "miss": miss.get("passed"), "zero": zero.get("passed"),
            "neg": neg.get("passed"), "nonnum": nonnum.get("passed"),
            "nan": nan.get("passed"), "inf": inf.get("passed"),
            "bool": boolean.get("passed"), "good_clean": not _es(good)}


def check_adversarial_contracts():
    """跨层对抗回归：轴向 full-bleed、安全区/来源区、唯一锚点与有限数据。"""
    import importlib.util as iu
    spec = iu.spec_from_file_location("guard_adversarial", SCRIPTS / "guard.py")
    g = iu.module_from_spec(spec)
    import sys as _s
    _s.modules["guard_adversarial"] = g
    spec.loader.exec_module(g)

    def run(elements, **slide):
        intent = slide.pop("page_intent", {"focus": "focus"})
        page = {"id": "s01", "page_intent": intent,
                "elements": elements, **slide}
        return g.check_spec({"canvas": {"width": 1280, "height": 720},
                             "slides": [page]}, include_advisory=False)

    def errors(out, rule=None):
        return [c for c in out.get("checks", []) if c.get("level") == "error"
                and (rule is None or c.get("rule") == rule)]

    text = lambda eid, x, y, w=40, h=30: {
        "type": "text", "id": eid, "text": "x", "x": x, "y": y,
        "width": w, "height": h, "size": 16}
    x_bleed_ok = run([text("focus", 0, 80, 1280, 40)])
    x_bleed_bad = run([text("focus", 40, 80, 1280, 40)])
    y_bleed_ok = run([text("focus", 80, 0, 40, 720)])
    y_bleed_bad = run([text("focus", 80, 40, 40, 720)])
    source_collision = run([text("focus", 250, 150, 100, 100)],
                           source_zone={"x": 100, "y": 100, "width": 200, "height": 100})
    duplicate_focus = run([text("focus", 80, 80), text("focus", 160, 80)])
    multi_focus = run([text("a", 80, 80)], page_intent={"focus": ["a", "b"]})
    bool_chart = run([{"type": "chart", "id": "focus", "x": 80, "y": 80,
                       "width": 400, "height": 240, "chart_kind": "ranked_bar",
                       "data": [{"label": "A", "value": True}]}])
    nested_provenance = run([{"type": "chart", "id": "focus", "x": 80, "y": 80,
                              "width": 400, "height": 240, "chart_kind": "ranked_bar",
                              "data": [{"label": "A", "value": 1}],
                              "provenance": {"source": "audit", "unit": "%",
                                             "period": "2025", "basis": "YoY"}}])
    bad_canvas = g.check_spec({"canvas": {"width": float("nan"), "height": True},
                               "slides": []}, include_advisory=False)
    malformed_slide = g.check_spec({"slides": [{"id": "s01", "elements": {},
                                                  "source_zone": {}}]},
                                    include_advisory=False)
    malformed = g.check_spec({"slides": "not-a-list"}, include_advisory=False)
    ok = (not errors(x_bleed_ok, "safety")
          and errors(x_bleed_bad, "safety")
          and not errors(y_bleed_ok, "safety")
          and errors(y_bleed_bad, "safety")
          and errors(source_collision, "source_zone")
          and errors(duplicate_focus, "element_schema")
          and errors(multi_focus, "focus_contract")
          and errors(bool_chart, "data_integrity")
          and not errors(nested_provenance, "data_provenance")
          and errors(bad_canvas, "canvas_schema")
          and errors(malformed_slide, "slide_schema")
          and errors(malformed_slide, "source_zone")
          and errors(malformed, "spec_schema"))
    return {"status": "PASS" if ok else "FAIL",
            "x_bleed_axis_safe": not errors(x_bleed_ok, "safety"),
            "x_bleed_cross_axis_blocked": bool(errors(x_bleed_bad, "safety")),
            "y_bleed_axis_safe": not errors(y_bleed_ok, "safety"),
            "y_bleed_cross_axis_blocked": bool(errors(y_bleed_bad, "safety")),
            "source_intersection_blocked": bool(errors(source_collision, "source_zone")),
            "duplicate_focus_blocked": bool(errors(duplicate_focus, "element_schema")),
            "multi_focus_blocked": bool(errors(multi_focus, "focus_contract")),
            "bool_chart_blocked": bool(errors(bool_chart, "data_integrity")),
            "malformed_canvas_blocked": bool(errors(bad_canvas, "canvas_schema")),
            "malformed_slide_blocked": bool(errors(malformed_slide, "slide_schema")),
            "empty_source_zone_blocked": bool(errors(malformed_slide, "source_zone")),
            "malformed_top_level_blocked": bool(errors(malformed, "spec_schema"))}


def check_hairline_grid():
    """F10/v4.19：发丝线补丁（用户指控坐实）——_snap_size 只增不减，
    1px 细线会被抬成 8px 色块。修复后：≤2px 任一维 → 仅位置吸附网格，
    尺寸绝不吸附；>2px 照常吸附；与 §02.1 网格 advis 的发丝线豁免同口径。"""
    import importlib.util as iu
    spec = iu.spec_from_file_location("guard", SCRIPTS / "guard.py")
    g = iu.module_from_spec(spec)
    import sys as _s
    _s.modules["guard"] = g
    spec.loader.exec_module(g)

    def mk(el):
        return {"canvas": {"width": 1280, "height": 720, "grid_unit": 8},
                "slides": [{"id": "s01",
                  "page_intent": {"insight": "A", "focus": "t", "density": "sparse"},
                  "background": {"color": "#F3F1EA"}, "elements": [el]}]}

    def norm(el):
        after, report = g.normalize_spec(mk(dict(el)))
        e = after["slides"][0]["elements"][0]
        size_rules = [i for i in report.get("items", []) if i["rule"] == "grid_snap_size"]
        return e, size_rules

    hline, hrules = norm({"type": "shape", "id": "r1", "role": "divider",
                          "x": 97, "y": 100, "width": 1184, "height": 1})
    vline, vrules = norm({"type": "shape", "id": "r2", "role": "rule",
                          "x": 101, "y": 83, "width": 2, "height": 560})
    block, brules = norm({"type": "shape", "id": "b1",
                          "x": 97, "y": 100, "width": 301, "height": 87})
    thick, trules = norm({"type": "shape", "id": "r3",
                          "x": 96, "y": 101, "width": 3, "height": 600})
    ok = (hline["height"] == 1 and hline["width"] == 1184
          and hline["x"] == 96 and hline["y"] == 104 and not hrules
          and vline["width"] == 2 and vline["x"] == 104 and not vrules
          and block["width"] == 304 and block["height"] == 88 and len(brules) == 2
          and thick["width"] == 8 and len(trules) == 1)
    return {"status": "PASS" if ok else "FAIL",
            "hline_h": hline["height"], "vline_w": vline["width"],
            "block": f"{block['width']}x{block['height']}",
            "thick_w": thick["width"], "hline_size_snaps": len(hrules)}


def check_cheap_rejects():
    """F12/v4.20：负面清单落在出图层——任意资产卡的 negative 必含
    廉价症状反向短语；与 illustration 正向 3D minimal 无矛盾；
    用户追加词条不被吞；两次构建字节一致（确定性）。"""
    import importlib.util as iu
    spec = iu.spec_from_file_location("asset_prompt", SCRIPTS / "asset_prompt.py")
    ap = iu.module_from_spec(spec)
    import sys as _s
    _s.modules["asset_prompt"] = ap
    spec.loader.exec_module(ap)
    card = {"apc": "APC-BG-01", "asset_type": "background",
            "subject": ["modern city skyline at dusk"],
            "color": ["deep navy and warm amber"],
            "material": ["atmospheric haze"],
            "lighting": ["city lights bokeh"],
            "composition": ["low horizon, vast sky"]}
    out = ap.build_asset_prompt(card)
    neg = out["negative"].lower()
    must = ["generic stock photo", "corporate handshake", "posed smiling people",
            "clip art", "neon glow", "cyberpunk", "humanoid robot",
            "glassmorphism", "tech blue gradient", "plastic skin",
            "oversaturated colors", "heavy hdr", "ai artifacts"]
    ill = ap.build_asset_prompt(dict(card, asset_type="illustration", apc="APC-IL-01"))
    extra = ap.build_asset_prompt(dict(card, negative=["drones"]),
                                  extra_negative=["lens dirt"])
    a = ap.build_asset_prompt(card)
    b = ap.build_asset_prompt(card)
    ok = (all(f"no {m}" in neg for m in must)
          and "no 3d render" not in ill["negative"].lower()
          and "3D minimal illustration" in ill["prompt"]
          and "no drones" in extra["negative"].lower()
          and "no lens dirt" in extra["negative"].lower()
          and a["prompt"] == b["prompt"] and a["negative"] == b["negative"])
    return {"status": "PASS" if ok else "FAIL",
            "hit": sum(f"no {m}" in neg for m in must), "total": len(must),
            "ill_3d_free": "no 3d render" not in ill["negative"].lower(),
            "deterministic": a["negative"] == b["negative"]}


def check_asset_qc_policy():
    """资产 QC 只做一次有界重出，不自动触发 review/release。"""
    import asset_prompt as ap
    bad = {"status": "issue", "checks": [
        {"check": "text_safe_area", "status": "issue"},
        {"check": "brightness_balance", "status": "issue"},
    ]}
    first = ap.qc_retry_decision(bad, attempt=0, phase="draft", max_retries=99)
    exhausted = ap.qc_retry_decision(bad, attempt=1, phase="draft")
    review = ap.qc_retry_decision(bad, attempt=0, phase="review")
    release = ap.qc_retry_decision(bad, attempt=0, phase="release")
    advisory = ap.qc_retry_decision(
        {"status": "issue", "checks": [{"check": "brightness_balance", "status": "issue"}]},
        phase="draft")
    try:
        ap.qc_retry_decision(bad, phase="qa")
        unknown = False
    except ValueError:
        unknown = True
    ok = (first["action"] == "retry" and first["max_retries"] == 1
          and not first["triggers_review"] and not first["triggers_release"]
          and exhausted["action"] == "flag" and exhausted["manual_required"]
          and review["action"] == "flag" and not review["retry"]
          and release["action"] == "block" and release["manual_required"]
          and advisory["action"] == "accept_with_advisory" and not advisory["retry"]
          and unknown)
    return {"status": "PASS" if ok else "FAIL",
            "first": first["action"], "exhausted": exhausted["action"],
            "release": release["action"]}


def check_shape_dialect():
    """F13/v4.21（release 像素档首战收网）：shape 顶层 color 无 fill →
    add_shape 只读 fill，内容凭空消失（2026 时间轴圆点/深色框实测）；
    line 无 stroke → 印章框边框凭空消失。error 级前置拦截。"""
    import importlib.util as iu
    spec = iu.spec_from_file_location("guard", SCRIPTS / "guard.py")
    g = iu.module_from_spec(spec)
    import sys as _s
    _s.modules["guard"] = g
    spec.loader.exec_module(g)

    def _mk(el):
        return g.check_spec({"slides": [{"id": "s01",
            "page_intent": {"insight": "A", "focus": "t", "density": "sparse"},
            "background": {"color": "#F3F1EA"},
            "elements": [{"type": "text", "id": "t", "text": "锚", "size": 20,
                          "color": "#111111", "x": 96, "y": 80, "width": 200, "height": 40},
                         el]}]})

    def _es(out):
        return [w for w in out.get("warnings", []) if "element_schema" in w]

    base = {"x": 96, "y": 200, "width": 240, "height": 24}
    c_nof = _mk({"type": "shape", "id": "a", **base, "color": "#999999"})
    l_nos = _mk({"type": "shape", "id": "b", **base,
                 "fill": {"type": "none"}, "line": {"color": "#999999", "width": 1}})
    good = _mk({"type": "shape", "id": "c", **base,
                "fill": {"type": "solid", "color": "#999999"},
                "stroke": "#999999", "stroke_width": 1})
    txt = _mk({"type": "text", "id": "d", "text": "文字顶层 color 合法",
               "size": 14, "color": "#222222", "x": 96, "y": 240,
               "width": 300, "height": 30})
    ok = (any("顶层 color" in w for w in _es(c_nof)) and c_nof.get("passed") is False
          and any("stroke" in w for w in _es(l_nos)) and l_nos.get("passed") is False
          and not _es(good) and not _es(txt))
    return {"status": "PASS" if ok else "FAIL",
            "color_dialect": c_nof.get("passed"), "line_dialect": l_nos.get("passed"),
            "fill_clean": not _es(good), "text_clean": not _es(txt)}


def check_contrast_fingerpoint():
    """F14/v4.21：注记级 aux 最坏值驱动 fail 时，verdict 的 worst 必须指认
    注记框而非阅读级框——旧行为让 1.33 的读数贴在 5.69 的元素上，
    人要修错对象（2026 实战被指向合格印章）。"""
    import importlib.util as iu
    spec = iu.spec_from_file_location("primitives", SCRIPTS / "primitives.py")
    p = iu.module_from_spec(spec)
    import sys as _s
    _s.modules["primitives"] = p
    spec.loader.exec_module(p)
    page = {"slide": "s07", "text_contrast_min": 5.69, "text_contrast_all_min": 1.33,
            "text_contrast_worst": {"id": "t_seal", "aux": False, "ratio": 5.69,
                                    "color": "#F3F1EA", "background": "#A63A2E"},
            "text_contrast_aux_worst": {"id": "t_src", "aux": True, "ratio": 1.33,
                                        "color": "#5A5C54", "background": "#C9C6BB"}}
    v1 = p.text_contrast_verdict(page, 3.0, 4.5)
    page2 = dict(page, text_contrast_min=1.2,
                 text_contrast_worst={"id": "body", "aux": False, "ratio": 1.2,
                                      "color": "#111111", "background": "#EEEEEE"})
    v2 = p.text_contrast_verdict(page2, 3.0, 4.5)
    ok = (v1["level"] == "fail" and v1["value"] == 1.33
          and v1["worst"].get("id") == "t_src"
          and v2["level"] == "fail" and v2["value"] == 1.2
          and v2["worst"].get("id") == "body")
    return {"status": "PASS" if ok else "FAIL",
            "aux_points_to": v1["worst"].get("id"), "reading_points_to": v2["worst"].get("id")}


def check_intent_skeleton():
    """v2.12 Page Intent Skeleton：家族骨架确定性生成，AI 只填洞，覆盖永远赢。"""
    di = load("design_intelligence", SCRIPTS / "design_intelligence.py")
    s = di.page_intent_skeleton("DATA_STORY", insight="增长加速", focus="c1")
    ok = (s["page_family"] == "DATA_STORY" and s["energy"] == "medium"
          and s["reading_order"] == ["c1"]
          and s["empty_space_role"] == "protect_focus")
    s2 = di.page_intent_skeleton("COVER", rhythm_stage="opening")
    ok = ok and s2["energy"] == "high" and s2["empty_space_role"] == "hold_emotion"
    ok = ok and di.page_intent_skeleton("DATA", energy="low")["energy"] == "low"
    ok = ok and di.page_intent_skeleton("MYSTERY")["density"] == "balanced"
    s3 = di.page_intent_skeleton("CLOSING", energy="low")   # 情绪收束的显式覆盖
    ok = ok and s3["energy"] == "low" and s3["empty_space_role"] == "hold_emotion"
    return {"status": "PASS" if ok else "FAIL",
            "data_story": s["empty_space_role"], "closing_override": s3["energy"]}


def check_deck_decision():
    """v2.12 Deck Decision Card：deck 级判断一次固化，确定性，页面继承。"""
    route = load("route", SCRIPTS / "route.py")
    brief = {"subject": "企业年度总结", "brief": "发布终版 董事会 企业年报",
             "brand_colors": {"accent": "#C8A24B"},
             "slides": [{"title": "封面", "content": "年度总结 发布会"},
                        {"title": "亮点", "content": "营收增长 42% 证据"},
                        {"title": "业务", "content": "三条业务线 数据 对比"},
                        {"title": "里程碑", "content": "时间线 阶段"},
                        {"title": "展望", "content": "战略 愿景 收束"}]}
    card = route.deck_decision(brief)
    ok = (card["narrative_arc"][0] == "establish" and card["narrative_arc"][-1] == "close"
          and len(card["density_curve"]) == 5
          and sum(card["density_profile"].values()) == 5
          and card["color"]["brand_derived"] is True
          and card["execution"]["mode"] == "release"
          and card["media_policy"]["generate"] >= 0
          and "visual_world" in card["slots"])
    card2 = route.deck_decision(brief)
    ok = ok and json.dumps(card, sort_keys=True, default=str) == \
        json.dumps(card2, sort_keys=True, default=str)
    return {"status": "PASS" if ok else "FAIL",
            "arc": card["narrative_arc"], "pages": len(card["density_curve"]),
            "deterministic": True}


def check_compile_version_gate():
    """编译缓存的失效判据 = 内容核验（视图指纹 + 产物字节），不再需要版本闸。"""
    import tempfile
    rc = load("render_check", SCRIPTS / "render_check.py")
    comp = load("compiler", SCRIPTS / "compiler.py")
    prim = load("primitives", SCRIPTS / "primitives.py")
    mapped_chart_kinds = {"kpi", "executive_kpi", "big_number"} \
        | set(comp.SHAPE_CHARTS) | set(comp.NATIVE_CHART_TYPES)
    ok = mapped_chart_kinds == set(prim.CHART_KINDS)
    with tempfile.TemporaryDirectory() as d:
        work = pathlib.Path(d)
        pptx = work / "a.pptx"
        pptx.write_bytes(b"fake")
        import hashlib
        rc.record_compile(work, pptx, "view1", {
            "passed": True, "warnings": [],
            "output_sha256": hashlib.sha256(b"fake").hexdigest(),
            "output_path": str(pptx)})
        rep = rc.compile_reuse(work, pptx, "view1")
        ok = ok and rep is not None and rep.get("reused") is True
        # vNext：不再读 COMPILER_VERSION——编译器行为变了产物字节就变了，
        # 下面的内容核验（pptx_sha）已经覆盖同一件事，版本闸是重复设计。
        rc._patch_meta(work, compile={**json.loads((work / "render_meta.json")
                                                    .read_text(encoding="utf-8"))["compile"],
                                      "compiler": "0.0-fossil"})
        ok = ok and rc.compile_reuse(work, pptx, "view1") is not None
        # 视图变化 → 作废
        ok = ok and rc.compile_reuse(work, pptx, "view2") is None
        # 产物被改（哪怕视图没变）→ 作废：内容核验是唯一也是足够的失效判据
        pptx.write_bytes(b"tampered")
        ok = ok and rc.compile_reuse(work, pptx, "view1") is None
    return {"status": "PASS" if ok else "FAIL",
            "compiler_version": getattr(comp, "COMPILER_VERSION", None)}


def check_sketch_mode():
    """v2.11 sketch 草图链：warn/hint 契约免除、无 pre-critic、SKETCH 状态、不可发布。"""
    import tempfile
    qa = load("qa", SCRIPTS / "qa.py")
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#CCCCCC",
                        "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"}}
    spec = {"canvas": {"width": 1280, "height": 720}, "theme": theme, "slides": [
        {"id": "s01", "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 40},
         "page_intent": {"insight": "探索方向", "focus": "st", "density": "sparse",
                         "energy": "high", "empty_space_role": "hold_emotion"},
         "elements": [{"type": "text", "id": "st", "x": 400, "y": 300, "width": 480,
                       "height": 120, "size": 48, "text": "sketch statement",
                       "color": "ink", "max_lines": 1, "line_height": 1.2, "padding": 0}]}]}
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "sk.pptx"
        sk = qa.run_qa(spec, out, mode="sketch", render_dir=pathlib.Path(d) / "r1", dpi=60)
        dr = qa.run_qa(spec, out, mode="draft", render_dir=pathlib.Path(d) / "r2", dpi=60)
        exists = out.exists()
    # muted #CCCCCC 对白底 <1.8:1 → draft 应有 warn；sketch 只留 error 级
    ok = (sk["status"] == "SKETCH" and dr["status"] == "PREVIEW_ONLY"
          and "risk" not in sk and "risk" not in dr
          and sk["guard"]["checks"] < dr["guard"]["checks"]
          and sk.get("release_eligible") is False and exists)
    return {"status": "PASS" if ok else "FAIL", "sketch_status": sk["status"],
            "guard_checks_sketch_vs_draft": f"{sk['guard']['checks']}/{dr['guard']['checks']}"}


def check_round_governance():
    """v4.26 轮次治理批回归锁：门槛去分数化 + fix_plan 报告自足 + warn 聚合 + 骨架序列化。

    ① 状态/发布门只由阻断项决定：warn-only deck 在重罚分下 passed 仍为 True、
       score<90 只影响 verdict=WARNING 信号，不再拖动状态（消灭追警告轮）。
    ② fix_plan：阻断项按根因分组、内嵌契约行；干净 deck 组为空。
    ③ warn_summary：同规则聚合计数，不逐条刷屏。
    ④ skeleton：plan 已决策字段确定性序列化；elements 留空（技能包≠设计系统）。
    """
    import copy
    import tempfile
    qa = load("qa", SCRIPTS / "qa.py")
    pl = load("pipeline", SCRIPTS / "pipeline.py")
    fails = []
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#CCCCCC",
                        "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"}}

    def _page(sid):
        return {"id": sid,
                "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 40},
                "page_intent": {"insight": f"{sid} 结论", "focus": "st",
                                "density": "sparse", "energy": "high",
                                "empty_space_role": "hold_emotion"},
                "elements": [{"type": "text", "id": "st", "x": 400, "y": 300,
                              "width": 480, "height": 120, "size": 48,
                              "text": f"{sid} statement", "color": "ink",
                              "max_lines": 1, "line_height": 1.2, "padding": 0}]}

    # muted #CCCCCC 对白底 <1.8:1 → contrast warn（非阻断）
    spec = {"canvas": {"width": 1280, "height": 720}, "theme": copy.deepcopy(theme),
            "slides": [_page("s01"), _page("s02")]}
    with tempfile.TemporaryDirectory() as d:
        rep = qa.run_qa(copy.deepcopy(spec), pathlib.Path(d) / "w.pptx", mode="draft",
                        penalties={"guard_warn": 30.0},
                        render_dir=pathlib.Path(d) / "rw")
        warns = [it for it in rep["items"] if it["level"] == "warn"]
        if not warns:
            fails.append("expected_warn")
        if not (rep["passed"] is True and rep["score"] < 90):
            fails.append("gate_decoupling")       # 分数不再构成门槛
        if rep["verdict"]["verdict"] != "WARNING":
            fails.append("verdict_signal")        # WARNING 信号保留
        ws = rep["warn_summary"]
        if not ws or any(w["level"] not in ("warn", "hint") for w in ws):
            fails.append("warn_summary_scope")
        if len({(w["domain"], w["rule"]) for w in ws}) != len(ws):
            fails.append("warn_summary_not_aggregated")
        if rep["fix_plan"]["groups"]:
            fails.append("clean_deck_fix_plan_nonempty")

        bad = copy.deepcopy(spec)
        bad["slides"][0]["elements"].append(
            {"type": "text", "id": "clash", "x": 400, "y": 300, "width": 480,
             "height": 120, "size": 24, "text": "故意重叠", "color": "ink",
             "max_lines": 1, "line_height": 1.2, "padding": 0})
        rep2 = qa.run_qa(bad, pathlib.Path(d) / "b.pptx", mode="draft",
                         render_dir=pathlib.Path(d) / "rb")
        groups = {g["root_cause"]: g for g in rep2["fix_plan"]["groups"]}
        if "OVERLAP" not in groups or groups["OVERLAP"]["count"] < 1:
            fails.append("fix_plan_overlap_group")
        elif "不相交" not in groups["OVERLAP"].get("fix", ""):
            fails.append("fix_plan_contract_line")
        if not (rep2["passed"] is False and rep2["status"] == "BLOCKED"):
            fails.append("blocking_gate")

        # ④ skeleton：确定性 + 边界（elements 留空、page_intent 骨架已填）
        need = {"occasion": "董事会年度复盘", "audience": "董事会",
                "decision": "批准预算",
                "slides": ["封面：年度复盘", "执行摘要",
                           {"title": "产品线表现", "content": "四条产品线数据",
                            "type": "data"}]}
        text_a = pl.build_skeleton_module(pl.build_plan_bundle(copy.deepcopy(need)))
        text_b = pl.build_skeleton_module(pl.build_plan_bundle(copy.deepcopy(need)))
        if text_a != text_b:
            fails.append("skeleton_not_deterministic")
        ns = {}
        try:
            exec(compile(text_a, "skeleton", "exec"), ns)
        except Exception as exc:
            fails.append(f"skeleton_not_executable:{type(exc).__name__}")
            ns = {}
        sk_spec = ns.get("SPEC") or {}
        slides = sk_spec.get("slides") or []
        if len(slides) != 3:
            fails.append("skeleton_page_count")
        if any(s.get("elements") != [] for s in slides):
            fails.append("skeleton_elements_preset")   # 越界=设计系统，必须留空
        if any(not s.get("source_zone") or "insight" not in (s.get("page_intent") or {})
               or "focus" not in (s.get("page_intent") or {}) for s in slides):
            fails.append("skeleton_intent_missing")
        colors = (sk_spec.get("theme") or {}).get("colors") or {}
        if not {"background", "ink", "muted", "primary", "secondary", "accent"} <= set(colors):
            fails.append("skeleton_theme_tokens")
    return {"status": "PASS" if not fails else "FAIL", "fails": fails}

def check_visual_calibration_v3():
    """V3 校准闭环：律内联唯一真源、色彩引擎确定、比例自洽、草稿链与提示词三层生效。"""
    import design_intelligence as di
    import asset_prompt as ap
    import route as rt
    fails = []
    # 参考空间律是**内联常量**（vNext：不再有外部存储与测量脚本的悬空依赖）
    laws = di.calibration_laws("cinematic_narrative")
    if di.CALIBRATION_LAWS.get("hue_families_page_max") != 1 \
            or laws.get("hue_families_page_max") != 1:
        fails.append("内联律缺失或被覆盖异常")
    if not (di.CALIBRATION_LAWS.get("area_ratio") or {}).get("c1"):
        fails.append("面积律缺失")
    if di.calibration_laws().get("source") != "inline":
        fails.append("校准律应为内联唯一真源（无外部覆盖层）")
    a = di.color_plan("cinematic_narrative")
    b = di.color_plan("cinematic_narrative")
    if a != b:
        fails.append("color_plan 非确定")
    if abs(sum(a["ratio_targets"].values()) - 1.0) > 1e-9:
        fails.append("比例目标和≠1")
    branded = di.color_plan("evidence_first", {"brand_colors": {"accent": "#123456"}})
    if branded["seed_source"] != "brand_colors" or branded["seed_skeleton"]["accent"] != "#123456":
        fails.append("brand_colors 未优先")
    if branded["seed_skeleton"]["foundation"] == "#123456":
        fails.append("键名语义错位：accent 被填进 foundation（v4.8 分裂 bug 回潮）")
    unkn = di.color_plan("evidence_first", {"brand_colors": {"x": "#123456"}})
    if unkn["seed_source"] == "brand_colors":
        fails.append("未知槽位键不应接管色板")
    nothex = di.color_plan("evidence_first", {"brand_colors": {"accent": "gold"}})
    if nothex["seed_source"] == "brand_colors":
        fails.append("非 #HEX 色值不应被接受")
    prim = di.color_plan("evidence_first", {"brand_colors": {"primary": "#0F2B46"}})
    if prim["seed_source"] != "brand_colors" or prim["seed_skeleton"]["foundation"] != "#0F2B46":
        fails.append("primary→foundation 别名失效（只给主色的品牌不应静默丢失）")
    if di.color_plan("quiet_minimal")["family"] != "zen_minimal":
        fails.append("direction alias 失效")
    opp = rt.one_pass_plan({"audience": "a", "decision": "d", "occasion": "o",
                            "slides": ["封面", "结论"]})
    if not opp.get("color_plan") or not opp["pages"] or "skeleton" not in opp["pages"][0]:
        fails.append("one_pass_plan 结构错误")
    card = ap.enhance_asset_card({"asset_type": "background", "subject": "x",
                                  "family": "zen_minimal"})
    if not card.get("motion") or not card.get("texture") or not card.get("fusion"):
        fails.append("三层注入缺失")
    if not any("close range" in t for t in card["texture"]):
        fails.append("微浮雕纪律缺失")
    prompt = ap.build_asset_prompt(card)["prompt"]
    if "sticker" not in prompt or "text-safe" not in prompt:
        fails.append("融合层未进提示词")
    return {"status": "PASS" if not fails else "FAIL", "missing": fails}


def check_design_advisory():
    """v3.2 契约：guard 里的设计契约条目是「观察」，不扣分、不阻断、不参与判定。

    Guard 是 PPT 的 compiler linter。高级感由 Design Intelligence 预测、references/design-craft 判断。
    """
    guard = load("guard", SCRIPTS / "guard.py")
    from qa import EXECUTION_MODES as M, mode_profile
    design = guard.DESIGN_RULES
    ok = (isinstance(design, frozenset) and len(design) >= 16
          and {"palette_discipline", "rhythm", "focus", "type_budget",
               "accent_budget", "asset_contract", "chart_style_drift"} <= design)
    ok = ok and "spec" in M and M["spec"]["render"] is False \
        and M["spec"].get("compile") is False
    ok = ok and mode_profile("spec").get("compile") is False \
        and mode_profile("draft").get("compile", True) is True
    # 造一条只会触发设计契约（warn）的 deck：不得被扣分、不得 passed=False
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                        "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"}}

    def el(eid, x, color, etype="text"):
        d = {"type": etype, "id": eid, "x": x, "y": 200, "width": 400, "height": 120,
             "size": 20, "color": color}
        if etype == "text":
            d.update(text="内容" * 4, max_lines=2, line_height=1.4, padding=0)
        return d

    spec = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
            "slides": [
                {"id": "s01",
                 "page_intent": {"insight": "结论一", "focus": "a", "density": "dense",
                                 "energy": "high", "empty_space_role": "hold"},
                 "elements": [el("a", 96, "accent"), el("b", 560, "accent"),
                              el("c", 96, "ink", "rounded_rect"),
                              el("d", 560, "ink", "rounded_rect"),
                              el("e", 960, "ink", "rounded_rect")]},
                {"id": "s02",
                 "page_intent": {"insight": "结论二", "focus": "a", "density": "dense",
                                 "energy": "high", "empty_space_role": "hold"},
                 "elements": [el("a", 96, "accent"), el("b", 560, "accent")]}]}
    g = guard.check_spec(spec)
    adv = [c for c in g["checks"] if c.get("advisory")]
    scored = [c for c in g["checks"] if not c.get("advisory") and c["level"] in ("error", "warn")]
    # 关闭 advisory 不只是 add() 丢弃结果：设计扫描本身也不能运行。
    old_gradient_muck = guard._gradient_muck
    try:
        guard._gradient_muck = lambda *_args: (_ for _ in ()).throw(
            AssertionError("advisory gradient scan should be skipped"))
        core = guard.check_spec(spec, include_advisory=False)
    finally:
        guard._gradient_muck = old_gradient_muck
    core_adv = [c for c in core["checks"] if c.get("advisory")]
    ok = ok and (len(adv) > 0 and not core_adv
                 and all(c["score_weight"] == 0.0 for c in adv))
    ok = ok and (g["score"] == 100 - sum(4 if c["level"] == "error" else 2 for c in scored))
    # 设计条目可以 warn，但绝不允许以 error 出现（error = 阻断 = 把审美写成了门槛）
    ok = ok and all(not c.get("advisory") for c in g["checks"] if c["level"] == "error")
    # 只有 advisory 命中时，guard 仍 passed（设计问题不得阻断发布判定）
    only_design = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
                   "slides": [{"id": "s01",
                               "page_intent": {"insight": "市场分析", "focus": "a",
                                               "density": "sparse", "energy": "low",
                                               "empty_space_role": "hold"},
                               "elements": [el("a", 400, "ink")]}]}
    g2 = guard.check_spec(only_design)
    ok = ok and g2["passed"] is True and all(
        c.get("advisory") for c in g2["checks"] if c["rule"] in design)
    return {"status": "PASS" if ok else "FAIL", "design_rules": len(design),
            "advisory_hits": len(adv), "scored_hits": len(scored),
            "design_only_score": g2["score"]}


def check_draft_import_contract():
    """Spec runtime contract（v3.2）：判「spec 是否合理」不该把 python-pptx 拖进来。

    spec 档 = Normalizer + Guard（风险建议仅显式 advisory），实测一轮毫秒级；而 pptx 的 import 链
    （pptx.api → opc → oxml → xml.sax → urllib.request）要约 150ms。谁把
    `from pptx import ...` 放回 primitives 顶部、或让 spec 档偷偷编译，立刻失败。
    另锁两件事：② release 必须真的把 pptx 拉起来（防止靠「删掉编译路径」骗过 ①）；
    ③ 同一 render 目录跨模式复用（review 接着 release 的证据跑，不再起 LibreOffice）。
    """
    import subprocess
    import tempfile
    # spec 档红线只有一条：pptx / lxml / 编译 / 渲染缺席。v4.15 起 art_critic 引擎
    # 整体移除，基元常量在 primitives 直连——惰性 import 胶水层一道不留。
    banned = ("pptx", "lxml", "compiler", "elements", "charts",
              "render_check", "numpy", "cv2")
    probe_tmpl = (
        "import sys, importlib.util\n"
        "sys.path.insert(0, %s)\n"
        "import qa\n"
        "m = importlib.util.spec_from_file_location('b', %s)\n"
        "mod = importlib.util.module_from_spec(m); m.loader.exec_module(mod)\n"
        "spec = mod.build_spec() if hasattr(mod, 'build_spec') else mod.SPEC\n"
        "r = qa.run_qa(spec, %s, mode=%s, render_dir=%s)\n"
        "bad = sorted({n for n in sys.modules for b in %s if n == b or n.startswith(b + '.')})\n"
        "print('RESULT', bad, r['status'], r['execution']['compiled'])\n"
    )

    def probe_for(scripts, build, out, mode, work, banned_list):
        args = [repr(str(x)) for x in (scripts, build, out, mode, work)]
        args.append(repr(list(banned_list)))
        return probe_tmpl % tuple(args)

    def _page(sid):
        return {"id": sid,
                "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 40},
                "page_intent": {"insight": f"{sid} 结论", "focus": "st", "density": "sparse",
                                "energy": "high", "empty_space_role": "hold_emotion"},
                "elements": [{"type": "text", "id": "st", "x": 400, "y": 300, "width": 480,
                              "height": 120, "size": 48, "text": f"{sid} statement",
                              "color": "ink", "max_lines": 1, "line_height": 1.2,
                              "padding": 0}]}

    spec = {"canvas": {"width": 1280, "height": 720},
            "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111",
                                 "muted": "#777777", "primary": "#222222",
                                 "secondary": "#333333", "accent": "#AA0000"}},
            "slides": [_page("s01"), _page("s02")]}
    fails = {}
    with tempfile.TemporaryDirectory() as d:
        build = pathlib.Path(d) / "build_probe.py"
        build.write_text("SPEC = " + repr(spec) + "\n", encoding="utf-8")
        work = pathlib.Path(d) / "render"
        # ① spec 档：零编译 + 零 pptx/lxml/compiler import
        out = pathlib.Path(d) / "spec.pptx"
        code = probe_for(SCRIPTS, build, out, "spec", work, banned)
        r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, cwd=str(ROOT), timeout=300)
        line = [l for l in (r.stdout or "").splitlines() if l.startswith("RESULT")]
        if r.returncode or not line:
            fails["spec"] = f"exit {r.returncode} {(r.stderr or '')[-160:]}"
        else:
            body = line[-1][len("RESULT"):].strip()
            loaded_s, _, rest = body.partition("]")
            loaded = eval(loaded_s + "]") if loaded_s.strip() else []
            if loaded:
                fails["spec"] = f"loaded {loaded}"
            elif not rest.split()[-1:] == ["False"]:
                fails["spec"] = f"compiled flag: {rest.strip()}"
            elif out.exists():
                fails["spec"] = "spec 档不应产出 PPTX"
        # ② release：pptx 必须被加载（编译路径没被误删）
        out2 = pathlib.Path(d) / "rel.pptx"
        code = probe_for(SCRIPTS, build, out2, "release", work, ["pptx"])
        r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, cwd=str(ROOT), timeout=600)
        if "pptx" not in (r.stdout or ""):
            fails["release_loads_pptx"] = "release 未加载 pptx：" + ((r.stdout or r.stderr)[-160:])
        # ③ draft 缓存命中时，新的 Python 进程也不应加载 compiler/python-pptx。
        #    这是 draft 高频调用能否真正变快的关键，而不只是少一个 JSON 字段。
        cache_probe = (
            "import sys, pathlib, json, importlib.util\n"
            "sys.path.insert(0, %s)\n"
            "import qa\n"
            "m = importlib.util.spec_from_file_location('b', %s)\n"
            "mod = importlib.util.module_from_spec(m); m.loader.exec_module(mod)\n"
            "p = pathlib.Path(%s)\n"
            "r = qa.run_qa(mod.SPEC, p / 'cached.pptx', mode='draft', render_dir=p / 'cached-render')\n"
            "print('CACHE', r['performance']['compile_reused'], 'compiler' in sys.modules, 'design_intelligence' in sys.modules, 'render_check' in sys.modules)\n"
        )
        cache_probe_code = cache_probe % (repr(str(SCRIPTS)), repr(str(build)),
                                           repr(str(pathlib.Path(d) / "cache-work")))
        first = subprocess.run([sys.executable, "-c", cache_probe_code], capture_output=True,
                               text=True, cwd=str(ROOT), timeout=300)
        second = subprocess.run([sys.executable, "-c", cache_probe_code], capture_output=True,
                                text=True, cwd=str(ROOT), timeout=300)
        if (first.returncode or second.returncode
                or "CACHE False True False False" not in (first.stdout or "")
                or "CACHE True False False False" not in (second.stdout or "")):
            fails["draft_cache_import"] = {"first": (first.stdout or first.stderr)[-200:],
                                            "second": (second.stdout or second.stderr)[-200:]}
        # ④ 跨模式复用同一 render 目录：release 已渲染 → review 不再起 soffice
        #    （依赖外部渲染器：LibreOffice 缺席时本段跳过，①②③ 不受环境限制）
        qa_mod = load("qa", SCRIPTS / "qa.py")
        if not (shutil.which("soffice") or shutil.which("libreoffice")):
            return ({"status": "PASS", "skipped": "render reuse needs LibreOffice",
                     "cache_probe": "checked"} if not fails else
                    {"status": "FAIL", "violations": fails})
        r_rel = qa_mod.run_qa(spec, pathlib.Path(d) / "shared.pptx", mode="release",
                              render_dir=work, dpi=60)
        r_rev = qa_mod.run_qa(spec, pathlib.Path(d) / "shared.pptx", mode="review",
                              render_dir=work, dpi=60)
        pp, pr = r_rel["performance"], r_rev["performance"]
        reuse = (pr.get("cache_hits", 0) > 0
                 and pr.get("render_ms", 10 ** 9) < max(400, pp.get("render_ms", 0) // 2))
        if not reuse:
            fails["render_dir_reuse"] = {"release_render_ms": pp.get("render_ms"),
                                        "review_render_ms": pr.get("render_ms"),
                                        "review_cache_hits": pr.get("cache_hits")}
        allowed = {"last_spec.json", "render_meta.json", "render_cache.json"}
        state_leak = []
        if work.exists():
            for f in sorted(x.name for x in work.iterdir()):
                if f in allowed or f.endswith((".tif", ".png", ".jpg", ".pdf", ".pptx")):
                    continue
                if f.startswith(("page-", "slide-")):
                    continue
                state_leak.append(f)
        if state_leak:
            fails["extra_state_files"] = state_leak
    return ({"status": "PASS", "banned": list(banned), "probe": "spec/release/render-reuse"}
            if not fails else {"status": "FAIL", "violations": fails})


def check_intent_compiler():
    """v4.0 意图压缩层：需求 → Design Brief（确定性、可预算、可复算）。"""
    import io
    from contextlib import redirect_stdout
    ic = load("intent_compiler", SCRIPTS / "intent_compiler.py")
    need = {"occasion": "2026 年度总结", "audience": "董事会",
            "decision": "批准关停亏损产品线",
            "slides": ["封面：年度总结",
                       {"id": "s02", "type": "data", "title": "增长结构"},
                       {"id": "s03", "type": "closing", "title": "下一步"}]}
    b1, b2 = ic.compile_brief(need), ic.compile_brief(need)
    ok = (b1 == b2 and set(b1) >= {"design_intent", "strategy_seed",
                                   "direction_seed", "slides_seed",
                                   "token_estimate", "source_hash"})
    ok = ok and b1["design_intent"]["tone"] == "calm_authority"
    ok = ok and b1["token_estimate"] <= 800
    ok = ok and [s["family"] for s in b1["slides_seed"]] == [
        "COVER", "DATA_STORY", "MINIMAL_STATEMENT"]
    # 显式覆盖永远赢；自然语言输入可编译
    b3 = ic.compile_brief({**need, "tone_hint": "human_trust"})
    ok = ok and b3["design_intent"]["tone"] == "human_trust"
    b4 = ic.compile_brief("做一个科技公司年度总结，给董事会看")
    ok = ok and b4["design_intent"]["audience"] == "unknown"
    # 直接 intent 编译与完整 pipeline 的 route 输入必须等价；subject/brief/purpose
    # 不能在压缩层丢失，否则同一需求会得到不同 content_type/page family。
    context_need = {"occasion": "董事会汇报", "subject": "brand story",
                     "brief": "历史与现场证据", "purpose": "批准下一步",
                     "audience": "董事会", "slides": ["故事"]}
    direct = ic.compile_brief(context_need)
    from route import plan_deck as _plan_deck
    expected_plan = _plan_deck(context_need)
    ok = ok and direct["route"]["path"] == expected_plan["path"]
    ok = ok and direct["slides_seed"][0]["family"] == expected_plan["pages"][0]["page_family"]
    lux = ic.compile_brief({"occasion": "年度报告", "subject": "品牌叙事",
                            "design_direction": "Quiet Luxury × Editorial Storytelling",
                            "slides": ["封面"]})
    ok = ok and lux["direction_seed"]["route_direction"] == "editorial_brand"
    ok = ok and lux["route"]["direction"] == lux["direction_seed"]["route_direction"]
    # import 零成本：route 只在函数内懒加载
    top = ic.__file__ and pathlib.Path(ic.__file__).read_text(encoding="utf-8")
    ok = ok and "\nfrom route" not in top and "\nimport route" not in top
    # CLI --demo 可执行
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ic.main(["--demo"])
    ok = ok and rc == 0 and json.loads(buf.getvalue())["token_estimate"] > 0
    return {"status": "PASS" if ok else "FAIL",
            "tokens": b1["token_estimate"], "hash": b1["source_hash"]}


def check_rules_module():
    """v4.0 机器口径真源：查表归代码，且与逻辑同值、与目录互证。"""
    import ast
    rules = load("design_intelligence_rules",
                 SCRIPTS / "design_intelligence_rules.py")
    di = load("design_intelligence", SCRIPTS / "design_intelligence.py")
    # 零依赖：只允许 from __future__
    tree = ast.parse((SCRIPTS / "design_intelligence_rules.py").read_text(
        encoding="utf-8"))
    imports = [n for n in ast.walk(tree)
               if isinstance(n, (ast.Import, ast.ImportFrom))]
    ok = all(isinstance(n, ast.ImportFrom) and n.module == "__future__"
             for n in imports)
    # 同值（搬移零漂移；load() 不注册 sys.modules 故判 == 不判 is）
    # 目录形状：22 码 / 12 族 / 取舍 5 阶固定序；每条含 strategy 三元组（单一注册表）
    ok = ok and rules.DENSITY_BANDS == di.DENSITY_BANDS
    ok = ok and rules.CALIBRATION_LAWS == di.CALIBRATION_LAWS
    ok = ok and rules.COLOR_DIRECTIONS == di.COLOR_DIRECTIONS
    ok = ok and rules.INTENT_PRESETS == di.INTENT_PRESETS
    ok = ok and rules.JUDGMENT_KEYS == di._JUDGMENT_KEYS
    ok = ok and rules.MEDIA_MODEL == di._MEDIA_MODEL
    ok = ok and len(rules.RISK_CATALOG) == 22
    ok = ok and len(rules.risk_families()) == 12
    ok = ok and all(set(m) >= {"family", "level", "predicted", "root_cause",
                               "prevention", "confidence", "strategy"}
                    for m in rules.RISK_CATALOG.values())
    ok = ok and all(isinstance(m.get("strategy"), tuple)
                    and len(m["strategy"]) == 3
                    for m in rules.RISK_CATALOG.values())
    ok = ok and [t["id"] for t in rules.TRADEOFF_ORDER] == [
        "fact_semantics", "readability", "content_task", "emotion", "brand"]
    # 实测发射码 ⊆ 目录（adversarial battery 触发 6+ 码）
    theme = {"colors": {"background": "#FAF7F0", "primary": "#2B241B",
                        "secondary": "#9A8F7C", "accent": "#8E2F28",
                        "ink": "#191510", "muted": "#6E675C"},
             "constraints": {"accent_max": 0.05}}

    def pi(insight, focus, family="DATA", density="sparse",
           role="protect_focus"):
        return {"insight": insight, "focus": focus, "reading_order": [focus],
                "energy": "medium", "density": density,
                "empty_space_role": role, "page_family": family,
                "rhythm_stage": "context", "continuity_token": "t"}

    bad = {"canvas": {"width": 1280, "height": 720}, "theme": theme, "slides": [
        {"id": "b1", "page_intent": pi("对比", "t", "STATEMENT"), "elements": [
            {"type": "text", "id": "t", "x": 48, "y": 104, "width": 880,
             "height": 64, "text": "标题", "size": 34, "color": "ink",
             "max_lines": 1},
            {"type": "text", "id": "lead", "x": 48, "y": 184, "width": 600,
             "height": 64, "text": "淡墨正文", "size": 16, "color": "secondary",
             "max_lines": 2}]},
        {"id": "b2", "page_intent": pi("构成", "c", "DATA", "balanced"),
         "elements": [
            {"type": "chart", "id": "c", "chart_kind": "donut", "x": 328,
             "y": 168, "width": 624, "height": 416, "highlight": 1,
             "data": [{"label": "A", "value": 52},
                      {"label": "B", "value": 48}],
             "source": "s", "unit": "%", "period": "2026", "basis": "x"}]},
        {"id": "b3", "page_intent": pi("溢出", "t3", "STATEMENT"), "elements": [
            {"type": "text", "id": "t3", "x": 48, "y": 108, "width": 488,
             "height": 64, "text": "一行肯定放不下的很长很长的标题文字要换行",
             "size": 40, "color": "ink", "line_height": 1.15,
             "max_lines": 2}]},
        {"id": "b4", "page_intent": pi("无锚", "t4", "SECTION",
                                      role="separate_chapter"), "elements": [
            {"type": "text", "id": "t4", "x": 48, "y": 108, "width": 880,
             "height": 56, "text": "小标题", "size": 34, "color": "ink",
             "max_lines": 1},
            {"type": "chart", "id": "lanes", "chart_kind": "steps", "x": 48,
             "y": 264, "width": 1184, "height": 320,
             "data": [{"label": "一", "value": 1},
                      {"label": "二", "value": 2}],
             "source": "s", "unit": "条", "period": "2027", "basis": "x"}]},
        {"id": "b5", "page_intent": pi("平A", "t5", "SECTION"), "elements": [
            {"type": "text", "id": "t5", "x": 48, "y": 104, "width": 880,
             "height": 64, "text": "静一", "size": 40, "color": "ink",
             "max_lines": 1}]},
        {"id": "b6", "page_intent": pi("平B", "t6", "SECTION"), "elements": [
            {"type": "text", "id": "t6", "x": 48, "y": 104, "width": 880,
             "height": 64, "text": "静二", "size": 40, "color": "ink",
             "max_lines": 1}]},
        # 追加 4 页：触发 preflight 并入 pre_critic 的 4 码，防「发射但未注册」回潮
        {"id": "b7", "page_intent": pi("", "t7", "STATEMENT"), "elements": [
            {"type": "text", "id": "t7", "x": 48, "y": 104, "width": 880,
             "height": 64, "text": "无洞察标题", "size": 40, "color": "ink",
             "max_lines": 1}]},
        {"id": "b8", "page_intent": pi("幽灵焦点", "ghost", "STATEMENT"), "elements": [
            {"type": "text", "id": "t8", "x": 48, "y": 104, "width": 880,
             "height": 64, "text": "标题", "size": 40, "color": "ink",
             "max_lines": 1}]},
        {"id": "b9", "page_intent": pi("卡片墙", "t9", "STRUCTURE",
                                       role="separate_chapter"), "elements": [
            {"type": "text", "id": "t9", "x": 48, "y": 104, "width": 880,
             "height": 64, "text": "标题", "size": 40, "color": "ink",
             "max_lines": 1}] +
            [{"type": "shape", "id": f"r{i}", "shape": "rounded_rect",
              "x": 48 + i * 120, "y": 300, "width": 100, "height": 100}
             for i in range(5)]},
        {"id": "b10", "page_intent": pi("文本碎片", "t10_0", "STATEMENT"), "elements": [
            {"type": "text", "id": f"t10_{i}", "x": 48, "y": 104 + i * 56,
             "width": 880, "height": 48, "text": f"第{i}句", "size": 20,
             "color": "ink", "max_lines": 1} for i in range(5)]},
    ]}
    emitted = {r["code"] for r in di.pre_critic(bad)["risks"]}
    want = {"CONTRAST_FAIL_RISK", "ACCENT_OVERFLOW", "TEXT_OVERFLOW_RISK",
            "NO_MEMORY_ANCHOR", "FOCUS_AREA_RISK", "RHYTHM_FLAT_RISK",
            "INTENT_UNCLEAR", "FOCUS_UNBOUND", "CARD_WALL_RISK", "TEXT_BUDGET_RISK"}
    ok = ok and want <= emitted and emitted <= set(rules.RISK_CATALOG)
    return {"status": "PASS" if ok else "FAIL",
            "codes": len(rules.RISK_CATALOG),
            "families": len(rules.risk_families()),
            "emitted_covered": len(emitted)}


def check_judgment_diet():
    """v4.0 判断密度预算：AI 必读面只许瘦不许胖（防规则回潮）。"""
    import re
    sizes = {f: (ROOT / f).stat().st_size for f in
             ("SKILL.md", "references/production-contract.md",
              "references/design-intelligence.md")}
    ok = (sizes["SKILL.md"] <= 8192
          and sizes["references/production-contract.md"] <= 8192
          and sizes["references/design-intelligence.md"] <= 10240)
    # 硬规则行（基线 98）≤ 30；知识保全：35 条微规则附录在 CHANGELOG 可找到，不许删
    hard = 0
    for f in ("SKILL.md", "references/production-contract.md",
              "references/design-intelligence.md", "references/design-system.md",
              "references/design-craft.md"):
        text = (ROOT / f).read_text(encoding="utf-8")
        hard += sum(1 for ln in text.splitlines()
                    if re.search("禁止|必须|不得|不允许|严禁", ln))
    ok = ok and hard <= 30
    archived_rules = (ROOT / "references/archive.md").read_text(encoding="utf-8")
    ok = ok and ("Evidence Micro-Rules" in archived_rules
                 and "行长 CJK 22–38 字" in archived_rules
                 and "数据墨水比" in archived_rules)
    return {"status": "PASS" if ok else "FAIL", "sizes": sizes,
            "hard_rule_lines": hard}

def check_degenerate_inputs():
    """退化输入不崩溃：空 spec / slides=None / 畸形元素 / 未知家族 → 优雅降级。"""
    import design_intelligence as di
    guard = load("guard", SCRIPTS / "guard.py")
    ok = True

    def _no_crash(name, fn):
        nonlocal ok
        try:
            fn()
        except Exception as e:
            ok = False
            print(f"  [degenerate_inputs] {name} 崩溃: {type(e).__name__}: {e}")

    _no_crash("pre_critic({})", lambda: di.pre_critic({}))
    _no_crash("pre_critic(slides=None)", lambda: di.pre_critic({"slides": None}))
    _no_crash("pre_critic(malformed elem)", lambda: di.pre_critic(
        {"slides": [{"id": "x", "elements": [{"type": "text"}]}]}))
    _no_crash("guard.check_spec({})", lambda: guard.check_spec({}))
    _no_crash("color_plan(unknown)", lambda: di.color_plan("unknown_xyz"))
    _no_crash("risk_strategy({})", lambda: di.risk_strategy({}))
    _no_crash("media_decision(empty)", lambda: di.media_decision({"elements": []}))
    # 未知家族 → quiet_luxury 兜底（不是 crash、不是静默空返回）
    cp = di.color_plan("unknown_xyz")
    ok = ok and cp.get("family") == "quiet_luxury"
    return {"status": "PASS" if ok else "FAIL"}


def main():
    result = {"structure": check_structure(), "templates_yaml": check_templates_yaml(), "references": check_references(), "imports": check_imports(), "fill_contract": check_fill_contract(), "render_metrics": check_render_metrics(), "pipeline": check_pipeline(),
               "single_process_pipeline": check_single_process_pipeline(),
               "normalizer": check_normalizer(),
               "modes": check_execution_modes(),
               "state_footprint": check_state_footprint(),
               "design_advisory": check_design_advisory(),
               "draft_import_contract": check_draft_import_contract(),
               "classifier": check_change_classifier(),
               "pre_critic": check_pre_critic(),
               "design_dna": check_design_dna(),
               "layout_search": check_layout_search(),
               "media_budgets": check_media_and_budgets(),
               "auto_fit": check_auto_fit(),
               "visual_calibration_v3": check_visual_calibration_v3(),
               "degenerate_inputs": check_degenerate_inputs(),
            "background_layer": check_background_layer(),
            "route_layer": check_route_layer(), "qa_performance": check_qa_performance_keys(),
            "progressive_qa": check_progressive_qa(), "decision_cache": check_decision_cache(),
            "render_cache": check_render_cache(),
            "render_request_bounds": check_render_request_bounds(),
            "cache_content_verify": check_cache_content_verify(),
            "background_qualification": check_background_qualification(),
            "text_contrast_gate": check_text_contrast_gate(),
            "line_measure": check_line_measure(),
            "palette_discipline": check_palette_discipline(),
            "chart_style_drift": check_chart_style_drift(),
            "data_governance": check_data_governance(),
            "multi_series": check_multi_series(),
            "compile_cache_projection": check_compile_cache_projection(),
            "cache_projection": check_cache_projection(),
            "manifest_attestation": check_manifest_attestation(), "element_schema": check_element_schema(), "intent_style": check_intent_style(),
        "intent_boundaries": check_intent_boundaries(), "ink_gate": check_ink_gate(),
        "geometry_degenerate": check_geometry_degenerate(),
        "adversarial_contracts": check_adversarial_contracts(),
        "hairline_grid": check_hairline_grid(),
            "shape_dialect": check_shape_dialect(), "contrast_fingerpoint": check_contrast_fingerpoint(),
        "cheap_rejects": check_cheap_rejects(), "asset_qc_policy": check_asset_qc_policy(),
            "optical_alignment": check_optical_alignment(),
            "chart_color_roles": check_chart_color_roles(),
            "brand_seed": check_brand_seed(),
            "layout_recommend": check_layout_recommend(),
            "sketch_mode": check_sketch_mode(),
            "round_governance": check_round_governance(),
            "pre_critic_v2": check_pre_critic_v2(),
            "intent_skeleton": check_intent_skeleton(),
            "deck_decision": check_deck_decision(),
            "compile_version_gate": check_compile_version_gate(),
            "intent_compiler": check_intent_compiler(),
            "rules_module": check_rules_module(),
            "judgment_diet": check_judgment_diet()}
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
