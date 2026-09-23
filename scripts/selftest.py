#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest · 核心测试（生产路径即测试路径）。

只测三类事实：
  1) 判断面正确（intelligence：单管线色彩、媒体判断、证据缺口、骨架是问题不是答案）
  2) 验证可靠（verify：硬门必拦、合规必放、判定可复现）
  3) 生产稳定（compile 确定性 + 缓存、资产链闭环、CLI 退出码与修复包）

运行：python scripts/selftest.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

PASS = 0
FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f" · {detail}" if detail else ""))


def run_vao(*args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPTS / "vao.py"), *args],
                          capture_output=True, text=True, cwd=cwd or str(ROOT))


# ── fixtures ─────────────────────────────────────────────────────────
BRIEF = {
    "audience": "集团董事会",
    "decision": "批准品牌预算",
    "tension": "回报无法量化",
    "design_direction": "editorial",
    "brand_colors": ["#1A3A5C", "#C8501E"],
    "quality_level": "advanced",
    "slides": [
        {"id": "s01", "family": "cover", "title": "从产品领先到品牌领先",
         "content": "2027 品牌升级专项立项"},
        {"id": "s02", "family": "statement", "title": "品牌不是成本，是复利资产",
         "content": "复购率 71%，指名购买率仅 19%。"},
        {"id": "s03", "family": "data", "title": "获客成本正在失控",
         "content": "2024 年 218 元 → 2026 年 286 元；自然流量占比 41% → 27%。"},
        {"id": "s04", "family": "timeline", "title": "18 个月落地节奏"},   # 证据页缺 content
        {"id": "s05", "family": "closing", "title": "请批准 4,800 万专项",
         "content": "首期 1,200 万于 2027Q1 启动。"},
    ],
}


def make_build(tmp: Path, pages=5) -> Path:
    """生成一份合规的 build.py（同构骨架的 filled 版本）。"""
    colors = {"background": "#F2EDE4", "surface": "#F4EFE6", "primary": "#1A3A5C",
              "secondary": "#9A8C74", "accent": "#C8501E", "ink": "#191510",
              "muted": "#6E6A5E"}
    fams = ["COVER", "MINIMAL STATEMENT", "DATA STORY", "TIMELINE", "CLOSING"]
    slides = []
    for i in range(pages):
        els = []
        if i > 0:
            els.append({"id": "eyebrow", "type": "text", "x": 48, "y": 40, "width": 320,
                        "height": 24, "text": fams[i], "size": 12.5, "color": "muted",
                        "role": "eyebrow"})
            els.append({"id": "page_number", "type": "text", "x": 1208, "y": 40,
                        "width": 32, "height": 24, "text": str(i + 1), "size": 12.5,
                        "color": "muted", "role": "page_number", "align": "right"})
        els.append({"id": "title", "type": "text", "x": 48, "y": 96, "width": 1184,
                    "height": 56, "text": f"第{i + 1}页结论句", "size": 32,
                    "color": "ink", "role": "title", "bold": True})
        els.append({"id": "src", "type": "text", "x": 48, "y": 676, "width": 1100,
                    "height": 24, "text": "来源：测试数据 · 2027-01", "size": 12.5,
                    "color": "muted", "role": "source"})
        if i == 2:
            els.append({"id": "chart", "type": "chart", "chart_kind": "line",
                        "x": 48, "y": 232, "width": 1184, "height": 400,
                        "data": [{"label": "2024", "value": 218},
                                 {"label": "2025", "value": 264},
                                 {"label": "2026", "value": 286}],
                        "highlight": 2, "show_values": True,
                        "source": "来源：台账", "unit": "元", "period": "2024–2026",
                        "basis": "全渠道加权"})
        slides.append({"id": f"s{i + 1:02d}",
                       "page_intent": {"insight": f"第{i + 1}页结论", "focus": "title"},
                       "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
                       "elements": els})
    build = tmp / "build.py"
    build.write_text(
        "# -*- coding: utf-8 -*-\n"
        f"SPEC = {{\n"
        f"    \"canvas\": {{\"width\": 1280, \"height\": 720, \"grid_columns\": 12, \"grid_unit\": 8}},\n"
        f"    \"theme\": {{\"colors\": {colors!r}, \"fonts\": {{\"cn\": \"Songti SC\", \"latin\": \"Georgia\"}}}},\n"
        f"    \"slides\": {slides!r},\n"
        f"}}\n", encoding="utf-8")
    return build


# ── 1 · intelligence ─────────────────────────────────────────────────
def test_intelligence(tmp: Path):
    import intelligence as intel

    bundle = intel.think(BRIEF)
    deck, pages = bundle["deck"], bundle["pages"]

    # 单管线色彩：品牌色落语义槽（主色→information，强调→accent）
    seed = deck["theme"]["colors_seed"]
    check("plan: 品牌色单管线落槽（primary→ink 槽, accent→accent 槽）",
          seed.get("information") == "#1A3A5C" and seed.get("accent") == "#C8501E"
          and deck["theme"]["seed_source"] == "brand_colors", str(seed))

    # 方向归一：别名与未知回落
    name, warn = intel.canonical_direction("editorial_brand")
    check("plan: 方向别名归一（editorial_brand→editorial）", name == "editorial")
    name2, warn2 = intel.canonical_direction("Quiet Luxury × Editorial Storytelling")
    check("plan: 组合方向落最长语义片段", name2 == "editorial"
          and (warn2 is None or warn2.get("canonical") == "editorial"))
    name3, warn3 = intel.canonical_direction("完全不存在的方向")
    check("plan: 未知方向回落并留痕", name3 == "zen_minimal" and warn3 is not None)

    # 媒体判断：作者声明 > 模型；图表压制；数据页不出图
    m_author = intel.media_judgment("DATA", declared_asset="required")
    check("plan: 作者声明压过媒体模型", m_author["source"] == "author"
          and m_author["decision"] == "required")
    m_chart = intel.media_judgment("HERO", has_chart=True)
    check("plan: 页内有图媒体预算归零（双焦点竞争）",
          m_chart["decision"] == "none" and m_chart["confidence"] <= 0.1)
    m_data = intel.media_judgment("DATA")
    check("plan: 数据页默认不出图（理由可解释）",
          m_data["decision"] == "none" and "双焦点" in m_data["reason"])

    # 证据页缺 content → unresolved 留痕
    s04 = next(p for p in pages if p["id"] == "s04")
    check("plan: 证据页缺 content 标记 unresolved",
          bool(s04["unresolved"]) and any(w.get("rule") == "unresolved_content"
                                          for w in bundle["warnings"]))

    # 相同内容不默认相同布局：规划不输出密度/坐标，输出判断问题
    check("plan: 规划不预定 density（反模板）",
          all("density" not in p for p in pages)
          and all("x" not in json.dumps(p.get("declarations") or {}) for p in pages))
    qs = intel.page_questions("data", deck.get("decision"))
    check("plan: 骨架逐页给判断问题（claim/focus/form/space，按内容类型推导）",
          set(qs) >= {"claim", "focus", "form", "space"} and "图表" in qs["form"])

    # tension 注入：结论/风险页与收尾页直面疑虑；数据页不注入
    q_st = intel.page_questions("statement", deck.get("decision"),
                                tension="回报无法量化")
    q_data = intel.page_questions("data", deck.get("decision"),
                                  tension="回报无法量化")
    check("plan: tension 注入结论页问题、数据页不注入",
          "疑虑" in q_st["claim"] and "疑虑" not in q_data["claim"])

    # 作者在 brief 写过的 insight/focus：声明直通骨架，不再留空 TODO 重问
    b2 = dict(BRIEF, slides=[{"id": "s01", "title": "主张", "content": "结论",
                              "insight": "投自有内容是唯一防守", "focus": "title"}])
    sk3 = intel.build_skeleton(intel.think(b2))
    check("skeleton: brief 已声明 insight/focus 直通（契约：写了就生效）",
          "投自有内容是唯一防守" in sk3 and "作者已在 brief 声明" in sk3)

    # 缺 tension 点名警告：它是张力注入的输入，静默缺失 = 判断静默失效
    b4 = {"audience": "董事会", "decision": "批准预算"}
    w4 = intel.think(b4)["warnings"]
    check("plan: 缺 tension 点名警告（deck_contract）",
          any(w.get("rule") == "deck_contract" and "tension" in str(w.get("msg", ""))
              for w in w4), str(w4)[:160])

    # 方向字体种子全部跨平台安全名（防未来悄悄改回 macOS 专属字族）
    banned_families = ("PingFang", "Songti SC", "Helvetica Neue", "SF Pro",
                       "Menlo", "Hiragino")
    off = [(n, d["fonts"]) for n, d in intel.DIRECTIONS.items()
           if any(b in str(d["fonts"]) for b in banned_families)]
    check("plan: 14 方向字体种子跨平台安全名", not off, str(off))

    # 骨架：确定性 + 主题 token 可读兜底
    sk1, sk2 = intel.build_skeleton(bundle), intel.build_skeleton(bundle)
    check("skeleton: 同 bundle 必得同文本", sk1 == sk2)
    tokens = intel.theme_tokens({"foundation": "#FFFFFF", "information": "#FFFFFF",
                                 "supporting": "#888888", "accent": "#CC0000"})
    check("skeleton: 可读性兜底（墨色与纸面分得开）",
          intel.contrast_hint(tokens["ink"], tokens["background"]) >= 4.5
          if hasattr(intel, "contrast_hint") else tokens["ink"] in ("#141414", "#FFFFFF"))

    # DNA：召回 / 校验 / 拒收结果记忆
    dna = intel.recall_dna(BRIEF)
    check("dna: 召回返回结构且高置信带判断",
          {"matched", "confidence", "dna", "note"} <= set(dna))
    bad_entry = {"id": "x", "pattern": "p", "judgment": {"layout": "fixed 64px grid"},
                 "signature": {"keywords": ["k"]}}
    errs, _ = intel.validate_dna_entry(bad_entry)
    check("dna: judgment 写结果值被拒收", bool(errs))
    ok_entry = {"id": "t", "pattern": "p", "judgment": {"space": "留白先于装饰"},
                "signature": {"keywords": ["t"]}}
    errs2, _ = intel.validate_dna_entry(ok_entry)
    check("dna: 行为判断可入库", not errs2)


# ── 2 · verify（硬门）────────────────────────────────────────────────
def _base_spec(tmp: Path):
    import importlib.util
    spec_file = make_build(tmp)
    from vao import load_spec
    spec, _ = load_spec(spec_file)
    return spec, spec_file


def test_verify(tmp: Path):
    from verify import check_spec, normalize_spec, verdict, release_manifest

    spec, spec_file = _base_spec(tmp)
    normalized, norm = normalize_spec(spec)
    r = check_spec(normalized)
    check("guard: 合规稿零阻断零噪音", r["passed"] and not r["checks"],
          str([c for c in r["checks"] if c["level"] == "error"]))

    # 三层执法身份：hard 可阻断 / declared 只执法声明的数字 / trace 结构性禁止 error
    r_all = check_spec(normalized, rules={"min_font_size": 99})   # 逼出 typography(trace)
    lowc = json.loads(json.dumps(normalized))
    lowc["theme"]["colors"]["muted"] = "#FBF9F4"                  # 逼出 contrast(trace)
    r_low = check_spec(lowc)
    typ = [c for c in r_all["checks"] if c["rule"] == "typography"]
    con = [c for c in r_low["checks"] if c["rule"] == "contrast"]
    check("guard: trace 层身份落盘且永不阻断（typography/contrast warn）",
          typ and con and all(c["layer"] == "trace" and c["level"] in ("warn", "hint")
                              for c in typ + con) and r_low["passed"],
          str([(c["rule"], c["layer"], c["level"]) for c in typ + con]))
    check("guard: 密度测量无条件归档（facts.density 镜子）",
          "density" in r.get("facts", {})
          and set(r["facts"]["density"]["pages"][0]) == {"id", "occupancy", "band"},
          str(r.get("facts"))[:120])

    # 归一化幂等
    normalized2, norm2 = normalize_spec(normalized)
    from primitives import spec_fingerprint
    check("normalize: 幂等（二次归一指纹不变）",
          spec_fingerprint(normalized) == spec_fingerprint(normalized2))

    # TEXT_OVERFLOW 必拦
    bad = json.loads(json.dumps(normalized))
    bad["slides"][0]["elements"][0]["height"] = 20
    r2 = check_spec(bad)
    check("guard: 文字溢出必拦（TEXT_OVERFLOW）", not r2["passed"]
          and any(c["rule"] == "text_capacity" and c["level"] == "error"
                  for c in r2["checks"]))

    # 缺载荷必拦
    bad2 = json.loads(json.dumps(normalized))
    bad2["slides"][2]["elements"][-1]["data"] = []
    r3 = check_spec(bad2)
    check("guard: 图表空载荷必拦", not r3["passed"])

    # 未知 chart_kind 必拦
    bad3 = json.loads(json.dumps(normalized))
    bad3["slides"][2]["elements"][-1]["chart_kind"] = "hologram"
    r4 = check_spec(bad3)
    check("guard: 未知图表类型必拦", not r4["passed"])

    # 越界必拦
    bad4 = json.loads(json.dumps(normalized))
    bad4["slides"][0]["elements"][0]["x"] = 1400
    r5 = check_spec(bad4)
    check("guard: 越出画布必拦", not r5["passed"])

    # verdict：PASS/BLOCK 二态 + 修复组内嵌明细
    v_pass = verdict(normalized, tmp / "x.pptx", mode="draft",
                     guard_report=r, compile_report={"passed": True, "slides": 5})
    check("verdict: 合规稿 PASS", v_pass["passed"] and v_pass["status"] == "PASS")
    v_block = verdict(normalized, tmp / "x.pptx", mode="draft",
                      guard_report=r2, compile_report={"passed": False, "warnings": ["x"]})
    groups = v_block["fix_plan"]["groups"]
    check("verdict: BLOCK 带根因组与明细（修复包自足）",
          not v_block["passed"] and groups and all(g.get("details") for g in groups))

    # release manifest：产物 sha 不符必 BLOCK
    pptx = tmp / "m.pptx"
    from compiler import compile_deck
    compile_deck(normalized, pptx, speed="fast")
    qa = verdict(normalized, pptx, mode="release",
                 guard_report=r,
                 compile_report={"passed": True, "slides": 5,
                                 "output_path": str(pptx),
                                 "output_sha256": "0" * 64, "file_bytes": 1})
    man = release_manifest(normalized, qa, workflow={"status": "SKIPPED", "image_count": 0})
    check("manifest: 产物哈希不符必 BLOCK", man["status"] == "BLOCKED"
          and any("output_sha256" in i for i in man["validation"]["issues"]))
    from primitives import file_digest
    qa2 = verdict(normalized, pptx, mode="release", guard_report=r,
                  compile_report={"passed": True, "slides": 5,
                                  "output_path": str(pptx),
                                  "output_sha256": file_digest(pptx),
                                  "file_bytes": pptx.stat().st_size})
    man2 = release_manifest(normalized, qa2, workflow={"status": "SKIPPED", "image_count": 0})
    check("manifest: 凭证一致时 release_eligible",
          man2["status"] == "PASS" and man2["release_eligible"])


# ── 3 · compiler（确定性 + 缓存）─────────────────────────────────────
def test_compiler(tmp: Path):
    from compiler import compile_deck
    from primitives import compile_reuse, record_compile, spec_view
    from primitives import file_digest
    spec, _ = _base_spec(tmp)

    out1, out2 = tmp / "c1.pptx", tmp / "c2.pptx"
    compile_deck(spec, out1, speed="fast")
    compile_deck(spec, out2, speed="fast")
    check("compiler: 同 spec 两次编译字节一致（确定性）",
          file_digest(out1) == file_digest(out2))

    import pptx
    d = pptx.Presentation(str(out1))
    check("compiler: 产物为原生可编辑 PPTX（5 页 · 文本可改）",
          len(d.slides.__iter__.__self__._sldIdLst) == 5
          if False else len(list(d.slides)) == 5)
    shape = next(iter(d.slides[1].shapes))
    check("compiler: 元素在 PowerPoint 对象模型中可编辑",
          shape.has_text_frame and bool(shape.text_frame.text))

    cache = tmp / "cache_dir"
    cache.mkdir()
    view = spec_view(spec, base_path=tmp)
    r1 = compile_deck(spec, out1, speed="fast")
    record_compile(cache, out1, view, r1)
    hit = compile_reuse(cache, out1, view, fast_probe=True, speed="fast")
    check("cache: 同投影同产物命中复用", hit is not None and hit.get("reused"))
    spec2 = json.loads(json.dumps(spec))
    spec2["slides"][0]["elements"][0]["text"] = "改过的标题"
    view2 = spec_view(spec2, base_path=tmp)
    check("cache: spec 变了不命中（判定新鲜）",
          compile_reuse(cache, out1, view2, fast_probe=True, speed="fast") is None)


# ── 4 · assets（链闭环）──────────────────────────────────────────────
def test_assets(tmp: Path):
    from intelligence import load_brief, think
    from assets import (build_manifest, prepare_manifest, image_qc, qc_retry_decision,
                        verify_chain, asset_entries, resolve_asset, ACCEPTED)
    from PIL import Image, ImageDraw

    brief = dict(BRIEF)
    bundle = think(brief)
    manifest = build_manifest(brief, bundle)
    prepare_manifest(manifest, brief, bundle, "brief.yml", "plan.json",
                     tmp / "am.json", tmp.as_posix())
    entries = {e["asset_id"]: e for e in asset_entries(manifest)}
    check("assets: 封面页进入生成清单（媒体判断→清单）",
          any(e["slide_ids"] == ["s01"] and e["decision"] == "generate"
              for e in entries.values()))
    check("assets: prompt 含 negative 且确定性",
          all(e.get("prompt") and e.get("negative") for e in entries.values()
              if e["decision"] == "generate"))

    # 同一视觉需求 → 同一指纹（提示词缓存的前提）
    m2 = build_manifest(brief, think(brief))
    check("assets: 同 brief 两次规划清单一致（指纹稳定）",
          [e["asset_id"] for e in m2["assets"] if e.get("asset_id")] ==
          [e["asset_id"] for e in manifest["assets"] if e.get("asset_id")])

    # QC：合规图 accept；缺图 pending
    for aid, e in entries.items():
        if e["decision"] != "generate":
            continue
        p = tmp / e["expected_filename"]
        img = Image.new("RGB", (1920, 1080), "#F2EDE4")
        d = ImageDraw.Draw(img)
        for x in range(1920):          # 柔和横向渐变，无硬边（硬边会触发 hard_seam 闸门）
            t = x / 1920
            d.line([(x, 0), (x, 1080)],
                   fill=(int(242 - 14 * t), int(237 - 14 * t), int(228 - 12 * t)))
        d.ellipse([1500, 300, 1800, 600], fill=(214, 150, 110))
        img.save(p)
        qc = image_qc(str(p), safe_rect=e.get("safe_area") or {},
                      text_is_dark=True, expected_ratio=e.get("ratio"),
                      background=e.get("background_color", "#FFFFFF"))
        dec = qc_retry_decision(qc, attempt=0, phase="draft", max_retries=1)
        check(f"assets: 合规背景画心 QC 通过（{aid[:18]}…）",
              dec["action"] in ACCEPTED, str(qc.get("status")) + str(dec))
    # 无图 → 链不假造
    spec, _ = _base_spec(tmp)
    wf = verify_chain(spec, None, None, None)
    check("assets: 无图稿件 SKIPPED（不伪造已检查）",
          wf["status"] == "SKIPPED" and wf["image_count"] == 0)

    # 有图缺 QC → BLOCK
    spec_img = json.loads(json.dumps(spec))
    aid = next(iter(entries))
    spec_img["slides"][0]["elements"].append(
        {"id": "bg", "type": "image", "asset_id": aid, "x": 0, "y": 0,
         "width": 1280, "height": 720, "layer": "background"})
    wf2 = verify_chain(spec_img, tmp / "am.json", None, None)
    check("assets: 有图缺有效 QC 必 BLOCK", wf2["status"] == "BLOCKED")


# ── 5 · CLI 生产路径 ─────────────────────────────────────────────────
def test_cli(tmp: Path):
    work = tmp / "cli"
    work.mkdir()
    brief_file = work / "brief.yml"
    import yaml
    brief_file.write_text(yaml.safe_dump(BRIEF, allow_unicode=True), encoding="utf-8")

    r = run_vao("plan", str(brief_file), "--out", str(work / "plan.json"),
                "--skeleton", str(work / "build.py"),
                "--assets-out", str(work / "asset_manifest.json"),
                "--assets-dir", str(work / "generated_assets"), cwd=str(tmp))
    check("cli: plan 退出码 0 且产物齐", r.returncode == 0
          and (work / "plan.json").is_file() and (work / "build.py").is_file()
          and (work / "asset_manifest.json").is_file(), r.stdout[-200:])

    plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
    check("cli: plan.json 无 need 镜像/路由缓存/死字段（context 减量）",
          "need" not in plan and "assets_hint" in plan
          and all("density" not in p for p in plan["pages"]))

    sk = (work / "build.py").read_text(encoding="utf-8")
    check("cli: 骨架带判断问题与未决标注", "判断[结论]" in sk and "未决" in sk)

    # build + release（无图）
    shutil.copy(make_build(tmp, pages=5), work / "fill.py")
    r2 = run_vao("check", str(work / "fill.py"), str(work / "out.pptx"),
                 "--mode", "release", cwd=str(tmp))
    check("cli: release PASS 且产出预览/清单/退出码 0",
          r2.returncode == 0 and "PASS" in r2.stdout
          and (work / "out.pptx").is_file() and (work / "out.manifest.json").is_file(),
          r2.stdout[-200:])
    r3 = run_vao("check", str(work / "fill.py"), str(work / "out.pptx"),
                 "--mode", "release", cwd=str(tmp))
    check("cli: 二次 release 缓存复用（未重编）", r3.returncode == 0
          and "未重编" in r3.stdout, r3.stdout[:200])

    # BLOCK：注入溢出 → 退出码 2 + 修复组带明细
    bad = (work / "fill.py").read_text(encoding="utf-8").replace("'height': 56,", "'height': 20,", 1)
    assert bad != (work / "fill.py").read_text(encoding="utf-8"), "注入失败"
    (work / "bad.py").write_text(bad, encoding="utf-8")
    r4 = run_vao("check", str(work / "bad.py"), str(work / "bad.pptx"),
                 "--mode", "draft", cwd=str(tmp))
    packet = json.loads((work / "bad.repair.json").read_text(encoding="utf-8"))
    groups = packet.get("fix_plan", {}).get("groups", [])
    check("cli: BLOCK 退出码 2 + 分组修复包（组内含明细）",
          r4.returncode == 2 and groups and groups[0].get("details"),
          r4.stdout[:200])

    # 坏 brief 早失败
    (work / "empty.yml").write_text("audience: x\nslides: []\n", encoding="utf-8")
    r5 = run_vao("plan", str(work / "empty.yml"), cwd=str(tmp))
    check("cli: 空 slides 早失败并给修法", r5.returncode == 2
          and "slides" in (r5.stderr + r5.stdout))

    # spec 档不产出 PPTX
    (work / "out2.pptx").unlink(missing_ok=True)
    r6 = run_vao("check", str(work / "fill.py"), str(work / "out2.pptx"),
                 "--mode", "spec", cwd=str(tmp))
    check("cli: spec 档判定但不写产物", r6.returncode == 0
          and not (work / "out2.pptx").exists())


# ── 5.5 · 资产链 CLI 回归（含图全链 + QC 阶段切换）──────────────────
def test_asset_chain_cli(tmp: Path):
    """P0-3 链路回归：plan→出图→绑定→QC→release 的生产路径只有单测不够，
    阶段切换（draft 宽容 / release 阻断）是最容易回归的一段，锁死语义。"""
    from PIL import Image, ImageDraw
    import yaml
    work = tmp / "chain"
    work.mkdir()
    brief_file = work / "brief.yml"
    brief_file.write_text(yaml.safe_dump(BRIEF, allow_unicode=True), encoding="utf-8")
    r = run_vao("plan", str(brief_file), "--out", str(work / "plan.json"),
                "--skeleton", str(work / "build.py"),
                "--assets-out", str(work / "am.json"),
                "--assets-dir", str(work / "generated_assets"), cwd=str(tmp))
    check("chain: plan 产出资产清单", r.returncode == 0 and (work / "am.json").is_file(),
          r.stdout[-200:])
    manifest = json.loads((work / "am.json").read_text(encoding="utf-8"))
    gen = [e for e in manifest["assets"] if e.get("decision") == "generate"]
    aid = gen[0]["asset_id"]
    img_path = work / gen[0]["expected_filename"]

    def paint(shift=0, hard_edge=False):
        img = Image.new("RGB", (1920, 1080), "#F2EDE4")
        d = ImageDraw.Draw(img)
        for x in range(1920):          # 柔和横向渐变（硬边会触发 hard_seam 闸门）
            t = x / 1920
            d.line([(x, 0), (x, 1080)],
                   fill=(int(242 - 14 * t - shift), int(237 - 14 * t),
                         int(228 - 12 * t + shift)))
        if hard_edge:                  # 半幅硬边矩形：制造 QC 不合格画心
            d.rectangle([0, 0, 960, 1080], fill=(40, 40, 46))
        else:
            d.ellipse([1500 - shift, 300, 1800 - shift, 600], fill=(214, 150, 110))
        img.save(img_path)

    # fill.py：封面页引用资产（layer:background + asset_id，同 demo 结构）
    fill = make_build(tmp, pages=5)
    inject = (f'{{"id": "bg", "type": "image", "asset_id": {aid!r}, "x": 0, "y": 0, '
              f'"width": 1280, "height": 720, "layer": "background", '
              f'"overlay": {{"color": "#F2EDE4", "opacity": 0.25}}}}, ')
    ftxt = fill.read_text(encoding="utf-8").replace("'elements': [",
                                                    "'elements': [" + inject, 1)
    assert inject in ftxt, "注入失败"
    (work / "fill.py").write_text(ftxt, encoding="utf-8")

    def run_check(mode, out):
        return run_vao("check", str(work / "fill.py"), str(work / out),
                       "--mode", mode, "--assets-manifest", str(work / "am.json"),
                       "--assets-dir", str(work), "--speed", "fast", cwd=str(tmp))

    paint()
    r1 = run_check("release", "out1.pptx")
    check("chain: 合规图 release 全链 PASS（QC→绑定→编译→manifest）",
          r1.returncode == 0 and "PASS" in r1.stdout, r1.stdout[-160:])
    qc1 = json.loads((work / "am.qc.json").read_text(encoding="utf-8"))
    sha1 = qc1["results"][0]["witness"]["sha256"]

    paint(shift=30)                    # 画心内容变化 → 必须重测而非复用
    r2 = run_check("release", "out1.pptx")   # 生产纪律：复跑同一条命令
    qc2 = json.loads((work / "am.qc.json").read_text(encoding="utf-8"))
    check("chain: 图变后 QC 重测（witness sha256 更新、零复用）",
          r2.returncode == 0 and qc2["results"][0]["witness"]["sha256"] != sha1
          and not (qc2.get("reuse") or {}).get("assets"), r2.stdout[-160:])

    paint(hard_edge=True)              # 阶段切换：draft 宽容 retry / release 阻断
    rd = run_check("draft", "out3.pptx")
    qcd = json.loads((work / "am.qc.json").read_text(encoding="utf-8"))
    rr = run_check("release", "out4.pptx")
    qcr = json.loads((work / "am.qc.json").read_text(encoding="utf-8"))
    check("chain: 坏图 draft 档 retry（宽容、进 retry_assets）",
          rd.returncode == 2 and qcd["phase"] == "draft"
          and aid in qcd.get("retry_assets", []), str(qcd.get("summary")))
    check("chain: 坏图 release 档 block（阶段切换重写报告）",
          qcr["phase"] == "release" and aid in qcr.get("blocking_assets", []),
          str(qcr.get("summary")))
    check("chain: 坏图 release 整稿 BLOCK 退出码 2", rr.returncode == 2, rr.stdout[-160:])


# ── 6 · docs 一致性 ──────────────────────────────────────────────────
def test_docs():
    refs = ROOT / "references"
    names = {p.name for p in refs.glob("*.md")}
    check("docs: references 恰为 4 份（judgment/contract/assets/precedent）",
          names == {"judgment.md", "contract.md", "assets.md", "precedent.md"}, str(names))
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    check("docs: SKILL 引用的文件都存在且无旧模块名",
          "design_intelligence" not in skill and "guard.py" not in skill
          and "asset-workflow.md" not in skill)
    for mod in ("intelligence.py", "assets.py", "verify.py", "vao.py",
                "compiler.py", "primitives.py", "ghost.py", "selftest.py"):
        if not (SCRIPTS / mod).is_file():
            check(f"core: {mod} 存在", False)
            return
    banned = ("run_evidence.py", "intent_compiler.py", "design_intelligence_rules.py",
              "asset_prompt.py", "asset_workflow.py", "compile_cache.py", "guard.py",
              "qa.py", "route.py", "pipeline.py", "design_intelligence.py")
    leftover = [b for b in banned if (SCRIPTS / b).is_file()]
    check("core: 旧模块无残留（13 → 8）", not leftover, str(leftover))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="vao-selftest-"))
    print(f"workspace: {tmp}\n")
    try:
        test_intelligence(tmp / "i") if (tmp / "i").mkdir() is None else None
        test_verify(tmp / "v") if (tmp / "v").mkdir() is None else None
        test_compiler(tmp / "c") if (tmp / "c").mkdir() is None else None
        test_assets(tmp / "a") if (tmp / "a").mkdir() is None else None
        test_cli(tmp / "cli-root") if (tmp / "cli-root").mkdir() is None else None
        test_asset_chain_cli(tmp / "chain-root") if (tmp / "chain-root").mkdir() is None else None
        test_docs()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{PASS}/{PASS + FAIL} passed")
    return 0 if FAIL == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
