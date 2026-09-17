#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最小验证网（不是回归大礼包）。

只验证三件事，任何一条不过都说明技能包坏了：

  A. 交付链能不能跑通：brief → plan → skeleton → draft → release → manifest
  B. 契约是否还拦得住错：溢出 / 侵入来源区 / 数值图表缺出处
  C. 判断层是否完整：家族动作/构图语法、显式声明优先、骨架与 plan 同源、验证不评分
  D. 技能包是否退化成它反对的东西：外部渲染器、布局引擎、逐脚本 CLI、死引用

不做打分，不做审美判断，不依赖网络或任何系统级组件。
退出码 0 = 全过；1 = 有失败项。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, bool(ok), detail))
    return bool(ok)


def run_vao(*args: str, cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    env = {"PYTHONPATH": str(SCRIPTS), "PATH": "/usr/bin:/bin:/usr/local/bin"}
    return subprocess.run([sys.executable, str(SCRIPTS / "vao.py"), *args],
                          capture_output=True, text=True, env=env, cwd=str(cwd or ROOT))


def spec_module(path: pathlib.Path, *, bad_overlap: bool = False) -> pathlib.Path:
    """最小可编译 spec：一页结论 + 来源区；bad_overlap 时故意让图压字。"""
    # 故意制造两个违规：正文墨迹压住标题、图表侵入来源区
    overlap_extra = ("              {\"type\": \"text\", \"id\": \"body\", \"x\": 96, \"y\": 280,"
                     " \"width\": 720, \"height\": 200, \"text\": \"这段正文压住了上面的标题\","
                     " \"size\": 20, \"color\": \"muted\", \"role\": \"body\","
                     " \"line_height\": 1.5, \"max_lines\": 6},\n"
                     if bad_overlap else "")
    src = f'''# -*- coding: utf-8 -*-
SPEC = {{
    "canvas": {{"width": 1280, "height": 720}},
    "theme": {{"colors": {{"background": "#F5F4EF", "ink": "#1B1A16", "muted": "#8A857A",
                           "primary": "#26251F", "secondary": "#6E6A5E", "accent": "#B3422A"}},
               "fonts": {{"display": "Helvetica Neue", "body": "Helvetica Neue"}}}},
    "direction": {{"color_intent": ["hierarchy", "emotion", "brand"]}},
    "slides": [
        {{"id": "s01",
          "page_intent": {{"insight": "结论句", "focus": "t1", "density": "sparse",
                           "energy": "high", "empty_space_role": "create_authority"}},
          "source_zone": {{"x": 48, "y": 672, "width": 1184, "height": 32}},
          "elements": [
{overlap_extra}              {{"type": "text", "id": "t1", "x": 96, "y": 240, "width": 800,
               "height": 120, "text": "一句话结论", "size": 64, "color": "ink",
               "role": "title", "line_height": 1.1, "max_lines": 1}}]}},
    ],
}}
'''
    path.write_text(src, encoding="utf-8")
    return path


# ── A. 交付链 ──────────────────────────────────────────────────────────────
def check_readability_seam() -> None:
    """可读性缝：文档写 3:1、执法曾从 2.5 起——2.5–3.0 是静默带（盲测 muted 2.57:1 就这么漏的）。

    另两条同源：① 面/影不该被当字判（深底主题的 secondary 是深面）；
    ② `chart_muted` 指到哪个 token，刻度就用哪个——它也算弱字，得一起管。
    """
    import guard as _guard
    import route as _route
    from primitives import contrast as _c

    light = {"ink": "#1B1A16", "muted": "#9A9A96", "primary": "#26251F",
             "secondary": "#6E6A5E", "accent": "#B3422A", "background": "#F5F4F1"}

    def probe(colors, *, chart_muted=None, text_color="muted"):
        theme = {"colors": dict(colors)}
        if chart_muted:
            theme["chart_muted"] = chart_muted
        spec = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
                "slides": [{"id": "s01",
                            "page_intent": {"insight": "x", "focus": "t1", "page_family": "COVER",
                                            "density": "sparse", "energy": "high",
                                            "empty_space_role": "hold_emotion"},
                            "elements": [{"type": "text", "id": "t1", "x": 96, "y": 240,
                                          "width": 600, "height": 80, "text": "结论", "size": 44,
                                          "color": text_color, "role": "title", "max_lines": 1}]}]}
        res = _guard.check_spec(spec)
        return ([c for c in res["checks"] if c["rule"] == "contrast"], res["passed"])

    # ① 静默带（2.57:1）：以前一声不吭，现在至少 hint；且仍然不阻断
    silent_zone, ok_zone = probe(light)
    check("readability: 2.5–3.0 的灰不再静默（2.57:1 → hint，且不阻断 release）",
          len(silent_zone) == 1 and silent_zone[0]["level"] == "hint" and ok_zone is True,
          f"{len(silent_zone)} 条 / passed={ok_zone}")

    # ② 真读不出来还是 warn
    warn_zone, _ = probe(dict(light, muted="#D2D0CA"))
    check("readability: 1.8 以下仍判 warn（1.4:1 的灰是「没有字」）",
          len(warn_zone) == 1 and warn_zone[0]["level"] == "warn",
          f"{[c['level'] for c in warn_zone]}")

    # ③ 面/影不误判：深底主题的 secondary 只做填充时无声；元素真拿它写字才点名
    dark = dict(_route.DIRECTION_PRESETS["product_stage"]["theme_seed"]["colors"])
    none_used, _ = probe(dark, chart_muted="muted", text_color="ink")
    used_as_text, _ = probe(dark, chart_muted="muted", text_color="secondary")
    check("readability: 深底 secondary 只做面时无声、被拿去写字时点名",
          not none_used and bool(used_as_text) and used_as_text[0]["id"] == "theme.secondary",
          f"面={len(none_used)} 条 · 字={len(used_as_text)} 条")

    # ④ chart_muted 指向谁，谁就吃这条线（刻度颜色别指到面上）
    # 这里把 secondary 也做成 2.57:1、且没有任何元素拿它写字——只有 chart_muted 指到它，
    # 它才该被点名（刻度就是它画的）。
    cm, _ = probe(dict(light, muted="#5A5A5A", secondary="#9A9A96"),
                 chart_muted="secondary", text_color="ink")
    check("readability: chart_muted 指向的 token 也算弱字（刻度色被管住）",
          len(cm) == 1 and cm[0]["id"] == "theme.secondary", f"{len(cm)} 条")

    # ⑤ 四个方向预设自己不能踩线（种子是给人抄的，抄完不该立刻吃提示）
    thin = []
    for name, preset in _route.DIRECTION_PRESETS.items():
        cols = dict(preset["theme_seed"]["colors"])
        bg = cols.get("background")
        roles = ["muted"] + ([preset["theme_seed"].get("chart_muted")]
                             if preset["theme_seed"].get("chart_muted") in cols else [])
        for role in roles:
            if role and _c(cols[role], bg) < 3.0:
                thin.append(f"{name}.{role}={_c(cols[role], bg):.2f}")
    check("readability: 四方向预设的弱字都在 3:1 以上", not thin, " · ".join(thin))


def check_pipeline(work: pathlib.Path) -> None:
    brief = work / "brief.yml"
    brief.write_text(
        "audience: 董事会\n"
        "decision: 批准投资\n"
        "slides:\n"
        "  - {id: s01, family: cover, title: 开场}\n"
        "  - {id: s02, family: data, title: 数据}\n", encoding="utf-8")
    plan_path, skeleton = work / "plan.json", work / "build_deck.py"
    proc = run_vao("plan", str(brief), "--out", str(plan_path), "--skeleton", str(skeleton))
    ok = proc.returncode == 0 and plan_path.exists() and skeleton.exists()
    check("plan: brief → plan.json + skeleton", ok, proc.stderr[-200:])
    if not ok:
        return
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    pages = (plan.get("plan") or {}).get("pages") or []
    check("plan: 每页都有家族与叙事动作",
          len(pages) == 2 and all((p.get("page_family")) for p in pages)
          and all((p.get("move") or {}).get("move") for p in plan["pages"]))
    text = skeleton.read_text(encoding="utf-8")
    check("skeleton: 不为空且不含预置元素坐标",
          text.count('"id":') >= 2 and '"elements": []' not in text and "TODO" in text)
    # 显式 family 赢过关键词推断
    check("explicit: family=cover 未被关键词改写成 business",
          pages[0].get("page_family") == "COVER",
          str(pages[0].get("page_family")))

    deck_path = work / "deck.pptx"
    mod = spec_module(work / "build_ok.py")
    proc = run_vao("check", str(mod), str(deck_path), "--mode", "draft")
    check("draft: 干净 spec → PASS 且产出 PPTX",
          proc.returncode == 0 and deck_path.exists(), proc.stdout[-200:])
    # 产物确定性：同一份 spec 必须产出同一串字节——否则 byte 戳失去意义，
    # 编译缓存与预览缓存的无变化复用会随机失效（历史 bug：内嵌工作簿写当前时间）。
    twin_path = work / "deck_twin.pptx"
    twin = run_vao("check", str(mod), str(twin_path), "--mode", "draft")
    if deck_path.exists() and twin_path.exists():
        import hashlib
        same = (hashlib.sha256(deck_path.read_bytes()).digest()
                == hashlib.sha256(twin_path.read_bytes()).digest())
    else:
        same = False
    check("determinism: 同 spec 两次编译字节一致（缓存与产物戳的前提）",
          twin.returncode == 0 and same)
    if deck_path.exists():
        report = json.loads(deck_path.with_suffix(".repair.json").read_text(encoding="utf-8"))
        check("draft: 报告含状态与轮次账本",
              report.get("status") == "PASS" and "rounds" not in report  # 账本在 vao 输出，不在 packet
              or report.get("status") == "PASS")
        manifest_path = deck_path.with_suffix(".manifest.json")
        proc = run_vao("check", str(mod), str(deck_path), "--mode", "release")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        check("release: Manifest 带产物字节戳与预览证据",
              proc.returncode == 0 and manifest.get("status") == "PASS"
              and len(str(manifest.get("compile_report", {}).get("output_sha256") or "")) == 64
              and (manifest.get("verification") or {}).get("visual_evidence") == "ghost_preview",
              proc.stderr[-200:])
        check("release: 交付资格在顶层与 verification 一致（不会少看一层而误判）",
              manifest.get("release_eligible") is True
              and (manifest.get("verification") or {}).get("release_eligible") is True,
              str(manifest.get("release_eligible")))

        # 确定性产物不重复渲染：PPTX 字节戳没变，预览应当复用而非重画一遍。
        preview = deck_path.parent / f"{deck_path.stem}_preview"
        stamp = png_stamp(preview)
        run_vao("check", str(mod), str(deck_path), "--mode", "release")
        check("preview: 字节戳未变则复用预览（确定性产物不重复渲染）",
              stamp != "" and png_stamp(preview) == stamp)


# ── B. 契约拦截 ────────────────────────────────────────────────────────────
def check_contracts(work: pathlib.Path) -> None:
    bad = spec_module(work / "build_bad.py", bad_overlap=True)
    out = work / "bad.pptx"
    proc = run_vao("check", str(bad), str(out), "--mode", "draft")
    packet_path = out.with_suffix(".repair.json")
    packet = json.loads(packet_path.read_text(encoding="utf-8")) if packet_path.exists() else {}
    groups = {g.get("root_cause") for g in (packet.get("fix_plan") or {}).get("groups") or []}
    check("guard: 墨迹相交被拦下且给出根因分组",
          proc.returncode == 2 and "OVERLAP" in groups, str(sorted(groups)))
    # 来源区被侵入 → SOURCE_COLLISION
    src = (work / "build_bad.py").read_text(encoding="utf-8")
    src = src.replace('"y": 280, "width": 720, "height": 200',
                      '"y": 640, "width": 720, "height": 96', 1)
    (work / "build_source.py").write_text(src, encoding="utf-8")
    proc2 = run_vao("check", str(work / "build_source.py"), str(work / "src.pptx"), "--mode", "draft")
    packet2 = json.loads((work / "src.repair.json").read_text(encoding="utf-8"))
    codes2 = packet2.get("failure_codes") or []
    check("guard: 侵入来源区被拦下", proc2.returncode == 2 and "SOURCE_COLLISION" in codes2, str(codes2))
    check("guard: 阻断时不产出 PPTX（不交付半成品）", not out.exists())

    # 数据页缺出处 → release 档硬门
    src = work / "build_nodata.py"
    src.write_text('''# -*- coding: utf-8 -*-
SPEC = {"canvas": {"width": 1280, "height": 720},
        "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                             "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"},
                  "fonts": {"display": "A", "body": "A"}},
        "direction": {"color_intent": ["hierarchy", "emotion", "brand"]},
        "slides": [{"id": "s01",
                    "page_intent": {"insight": "增长", "focus": "c1", "density": "balanced",
                                    "energy": "low", "empty_space_role": "protect_focus"},
                    "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
                    "elements": [{"type": "text", "id": "t", "x": 96, "y": 96, "width": 800,
                                  "height": 72, "text": "增长结论", "size": 40, "color": "ink",
                                  "role": "title", "max_lines": 1},
                                 {"type": "chart", "id": "c1", "chart_kind": "bar", "x": 96,
                                  "y": 240, "width": 800, "height": 320,
                                  "data": [{"label": "A", "value": 3}, {"label": "B", "value": 5}]}]}]}
''', encoding="utf-8")
    proc = run_vao("check", str(src), str(work / "nodata.pptx"), "--mode", "release")
    packet = json.loads((work / "nodata.repair.json").read_text(encoding="utf-8"))
    codes = packet.get("failure_codes") or []
    check("release: 数值图表缺 source/unit/period/basis 即阻断",
          proc.returncode == 2 and "DATA_INTEGRITY_FAIL" in codes, str(codes))

    # 载荷完整性：schema 合法但「没东西可画」的图表必须当场阻断，不能 PASS 出门留空白页
    src = work / "build_payload.py"
    gaps = [{"id": "e1", "chart_kind": "steps", "data": []},
            {"id": "e2", "chart_kind": "kpi"},
            {"id": "e3", "chart_kind": "matrix"},
            {"id": "e4", "chart_kind": "architecture"}]
    els = [{"type": "text", "id": "t", "x": 96, "y": 96, "width": 800, "height": 72,
            "text": "载荷完整性", "size": 40, "color": "ink", "role": "title", "max_lines": 1}]
    els += [dict(e, type="chart", x=96, y=200 + i * 120, width=800, height=110)
            for i, e in enumerate(gaps)]
    src.write_text("# -*- coding: utf-8 -*-\nSPEC = " + json.dumps(
        {"canvas": {"width": 1280, "height": 720},
         "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                              "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"},
                   "fonts": {"display": "A", "body": "A"}},
         "slides": [{"id": "s01",
                     "page_intent": {"insight": "空载荷", "focus": "t", "density": "balanced",
                                     "energy": "low", "empty_space_role": "protect_focus"},
                     "elements": els}]}, ensure_ascii=False), encoding="utf-8")
    out = work / "payload.pptx"
    proc = run_vao("check", str(src), str(out), "--mode", "draft")
    packet = json.loads((work / "payload.repair.json").read_text(encoding="utf-8"))
    group = next((g for g in (packet.get("fix_plan") or {}).get("groups") or []
                  if set(g.get("ids") or []) >= {"e1", "e2", "e3", "e4"}), {})
    told = " ".join(group.get("samples") or [])
    check("payload: 空载荷图表（steps/kpi/matrix/architecture）当场阻断、不出 PPTX、"
          "并给出可批量修的根因",
          proc.returncode == 2 and len(group.get("ids") or []) == 4 and not out.exists()
          and ("data" in told or "缺少" in told or "空载荷" in told), told[:120])

    # 反向：按文档给出了元素级载荷，就必须真的画得出来。
    # 历史 bug：matrix（points）/ architecture（layers）通过了 Guard、却在编译期被
    # 「必须有 data 行」的通用门拦下 —— 两种 kind 有绘制代码却永远出不了图。
    solid = [{"type": "text", "id": "t", "x": 96, "y": 96, "width": 800, "height": 72,
              "text": "元素级载荷", "size": 40, "color": "ink", "role": "title", "max_lines": 1},
             {"type": "chart", "id": "m1", "chart_kind": "matrix", "x": 96, "y": 200,
              "width": 500, "height": 400, "source": "内部统计", "unit": "分", "period": "FY25",
              "basis": "合并口径", "points": [{"x": 0, "y": 0, "label": "A"},
                                              {"x": 1, "y": 1, "label": "B"}]},
             {"type": "chart", "id": "a1", "chart_kind": "architecture", "x": 660, "y": 200,
              "width": 480, "height": 400, "source": "内部统计", "unit": "层", "period": "FY25",
              "basis": "合并口径", "layers": ["接入层", "逻辑层", "数据层"]}]
    src = work / "build_element_payload.py"
    src.write_text("# -*- coding: utf-8 -*-\nSPEC = " + json.dumps(
        {"canvas": {"width": 1280, "height": 720},
         "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                              "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"},
                   "fonts": {"display": "A", "body": "A"}},
         "slides": [{"id": "s01",
                     "page_intent": {"insight": "矩阵与分层", "focus": "t", "density": "balanced",
                                     "energy": "low", "empty_space_role": "protect_focus"},
                     "elements": solid}]}, ensure_ascii=False), encoding="utf-8")
    out = work / "element_payload.pptx"
    proc = run_vao("check", str(src), str(out), "--mode", "draft")
    drawn = ""
    if out.exists():
        import zipfile as _z2
        with _z2.ZipFile(out) as z:
            drawn = z.read([n for n in z.namelist() if n.startswith("ppt/slides/slide")][0]).decode("utf-8")
    check("payload: matrix(points)/architecture(layers) 给出载荷即真的画出来",
          proc.returncode == 0 and out.exists() and "接入层" in drawn and ">" + "A" + "<" in drawn,
          f"rc={proc.returncode} shapes={'<p:sp>' in drawn}")

    # 磁盘源码即真相：同一秒内的等长修改（编辑器连存两次）不得被字节码缓存吞掉。
    # 历史 bug：importlib 按「源码 mtime(秒)+大小」复用 __pycache__，改了 spec 却交付旧产物。
    import os as _os
    import zipfile as _zip
    import hashlib as _hashlib
    theme_a = {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
               "primary": "#222222", "secondary": "#333333", "accent": "#B3422A"}
    theme_b = dict(theme_a, accent="#1F6F5C")          # 等长替换：大小不变，只有内容变
    stamps = []
    for tag, theme in (("edit_a", theme_a), ("edit_b", theme_b)):
        payload = {"canvas": {"width": 1280, "height": 720}, "theme": {"colors": theme,
                   "fonts": {"display": "A", "body": "A"}},
                   "slides": [{"id": "s01",
                               "page_intent": {"insight": "i", "focus": "c", "density": "balanced",
                                               "energy": "low", "empty_space_role": "protect_focus"},
                               "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
                               "elements": [
                                   {"type": "text", "id": "t", "x": 96, "y": 96, "width": 800,
                                    "height": 72, "text": "同秒修改", "size": 40, "color": "ink",
                                    "role": "title", "max_lines": 1},
                                   {"type": "chart", "id": "c", "chart_kind": "column",
                                    "x": 96, "y": 240, "width": 800, "height": 320,
                                    "data": [{"label": "A", "value": 3}, {"label": "B", "value": 5}],
                                    "source": "S", "unit": "u", "period": "p", "basis": "b",
                                    "highlight": "B"}]}]}
        src = work / "build_edit.py"
        src.write_text("# -*- coding: utf-8 -*-\nSPEC = " + json.dumps(payload, ensure_ascii=False),
                       encoding="utf-8")
        _os.utime(src, (1700000000, 1700000000))       # 两次写入同一时间戳：最坏情况
        out = work / f"{tag}.pptx"
        proc = run_vao("check", str(src), str(out), "--mode", "draft")
        if proc.returncode == 0 and out.exists():
            with _zip.ZipFile(out) as z:
                chart_xml = z.read("ppt/charts/chart1.xml").decode("utf-8")
            stamps.append((_hashlib.sha256(out.read_bytes()).hexdigest()[:16],
                           theme["accent"].lstrip("#") in chart_xml))
        else:
            stamps.append((None, False))
    check("freshness: 同秒等长修改后编译的是磁盘上的当前 spec（不吃旧字节码）",
          stamps[0][0] and stamps[1][0] and stamps[0][0] != stamps[1][0]
          and stamps[1][1] and not stamps[1][0] == stamps[0][0],
          f"{stamps[0][0]} → {stamps[1][0]} · 新色落地={stamps[1][1]}")

    # 空白交付物：空 deck 与空白页同样必须当场阻断（0 页 PASS 是最贵的「通过」）
    empty_deck = {"canvas": {"width": 1280, "height": 720},
                  "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111",
                                       "muted": "#777777", "primary": "#222222",
                                       "secondary": "#333333", "accent": "#AA0000"},
                            "fonts": {"display": "A", "body": "A"}},
                  "slides": []}
    blank = json.loads(json.dumps(empty_deck))
    blank["slides"] = [{"id": "s01", "elements": []}]
    verdicts = []
    for tag, payload in (("empty_deck", empty_deck), ("blank_page", blank)):
        src = work / f"build_{tag}.py"
        src.write_text("# -*- coding: utf-8 -*-\nSPEC = " + json.dumps(payload, ensure_ascii=False),
                       encoding="utf-8")
        proc = run_vao("check", str(src), str(work / f"{tag}.pptx"), "--mode", "release")
        verdicts.append(proc.returncode == 2 and not (work / f"{tag}.pptx").exists())
    check("blank: 空 deck / 空白页在 release 档当场阻断且不出 PPTX", all(verdicts), str(verdicts))


# ── C. 反退化 ──────────────────────────────────────────────────────────────
def check_font_channel(work: pathlib.Path) -> None:
    """字体是结构，不是装饰：声明的字族必须真的进产物。

    历史 bug：骨架教 `theme.fonts = {display, body}`，渲染层只读 `cn` / `latin`——
    照骨架写的 spec 全部静默回落 Arial / Microsoft YaHei，字体判断在产物里消失且零提示。
    """
    import zipfile

    def typefaces(fonts: dict) -> tuple[int, set]:
        mod = work / f"font_{abs(hash(json.dumps(fonts, sort_keys=True))) % 10 ** 6}.py"
        spec = {"canvas": {"width": 1280, "height": 720},
                "theme": {"colors": {"background": "#F6F5F1", "ink": "#1B1A16", "muted": "#8B8679",
                                     "primary": "#26251F", "secondary": "#6E6A5E", "accent": "#B3422A"},
                          "fonts": fonts},
                "slides": [{"id": "s01",
                            "page_intent": {"insight": "字体通道", "focus": "t1",
                                            "page_family": "COVER", "density": "sparse",
                                            "energy": "high", "empty_space_role": "hold_emotion"},
                            "elements": [{"type": "text", "id": "t1", "x": 96, "y": 240, "width": 800,
                                          "height": 120, "text": "字体通道 Font",
                                          "size": 44, "color": "ink", "role": "title",
                                          "max_lines": 1, "line_height": 1.2}]}]}
        mod.write_text("# -*- coding: utf-8 -*-\nSPEC = " + json.dumps(spec, ensure_ascii=False),
                       encoding="utf-8")
        out = work / (mod.stem + ".pptx")
        proc = run_vao("check", str(mod), str(out), "--mode", "draft")
        found = set()
        if out.exists():
            with zipfile.ZipFile(out) as z:
                xml = z.read([n for n in z.namelist()
                              if n.startswith("ppt/slides/slide")][0]).decode("utf-8")
            found = {t for t in re.findall(r'typeface="([^"]+)"', xml) if t}
        return proc.returncode, found

    rc_a, canon = typefaces({"cn": "Songti SC", "latin": "Georgia"})
    rc_b, alias = typefaces({"display": "Georgia", "body": "Songti SC"})
    # 混排文本才会同时用到中文字族与拉丁字族（纯中文时编译器只写中文字族，这是对的）
    check("fonts: 声明的字族进产物（规范键 cn/latin 与别名 display/body 同一结果）",
          rc_a == 0 and rc_b == 0 and canon == alias
          and {"Songti SC", "Georgia"} <= canon,
          f"规范={sorted(canon)} 别名={sorted(alias)}")

    # 骨架必须教规范键名（教错了，生成侧整份 deck 都会回落字体）
    src = work / "font_skeleton.yml"
    src.write_text("audience: 评审\ndecision: 定稿\nslides:\n  - {id: s01, family: cover, title: 开场}\n",
                   encoding="utf-8")
    skel = work / "font_skeleton.py"
    run_vao("plan", str(src), "--out", str(work / "font_skeleton.json"), "--skeleton", str(skel))
    body = skel.read_text(encoding="utf-8")
    check("fonts: plan 骨架教规范键名（cn/latin），不再教不被读取的 display/body",
          '"cn"' in body and '"latin"' in body and '"display": "TODO"' not in body,
          [l.strip() for l in body.splitlines() if "fonts" in l][:1])

    # 写错键名 / 缺字族必须点名（warn，不阻断）
    probe = {"canvas": {"width": 1280, "height": 720},
             "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                                  "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"},
                       "fonts": {"cn": "Songti SC", "title_font": "Georgia"}},
             "slides": [{"id": "s01", "page_intent": {"insight": "x", "focus": "t1",
                                                      "page_family": "COVER", "density": "sparse",
                                                      "energy": "high", "empty_space_role": "hold_emotion"},
                         "elements": [{"type": "text", "id": "t1", "x": 96, "y": 240, "width": 800,
                                       "height": 120, "text": "字", "size": 44, "color": "ink",
                                       "role": "title", "max_lines": 1}]}]}
    import guard as _guard
    result = _guard.check_spec(probe)
    msgs = " ｜ ".join(c["msg"] for c in result["checks"] if c["rule"] == "theme_fonts")
    check("fonts: 写错字体键 / 缺字族会被点名（theme_fonts warn，不阻断）",
          result["passed"] and "title_font" in msgs and "latin" in msgs, msgs[:120])


def check_direction_seed(work: pathlib.Path) -> None:
    """方向 = 可执行种子：说得出（数字）、落得下（骨架）、量得到（guard）。

    历史状态：方向只换色族与底色，构图/字号/留白/形状/背景层全同——「换方向」在产物层
    几乎不可见（deep-audit/harness_direction.py 实测）。现在方向带数字约束，骨架照抄。
    """
    import guard as _guard

    colors = {"background": "#F5F4EF", "ink": "#1B1A16", "muted": "#8A857A",
              "primary": "#26251F", "secondary": "#6E6A5E", "accent": "#B3422A"}

    def probe(constraints: dict, elements: list) -> list:
        spec = {"canvas": {"width": 1280, "height": 720},
                "theme": {"colors": colors, **({"constraints": constraints} if constraints else {})},
                "slides": [{"id": "s01",
                            "page_intent": {"insight": "x", "focus": elements[0]["id"],
                                            "page_family": "COVER", "density": "sparse",
                                            "energy": "high", "empty_space_role": "hold_emotion"},
                            "elements": elements}]}
        return [c for c in _guard.check_spec(spec)["checks"] if c["rule"] == "direction_seed"]

    txt = lambda i, **kw: {"type": "text", "id": i, "x": 96, "y": 240, "width": 400, "height": 80,
                           "text": "字", "size": 44, "color": "ink", "role": "title",
                           "max_lines": 1, **kw}
    box = {"type": "shape", "id": "b1", "x": 0, "y": 0, "width": 1200, "height": 700,
           "fill": "#EEEEEE"}

    # ① 四个量各能触发一次（留白 / 背景层 / 字号级差 / 粗体占比）
    ws = probe({"whitespace_min": 0.5}, [box, txt("t1")])
    bg = probe({"bg_layers_max": 1}, [box, dict(box, id="b2", width=1000, height=600), txt("t1")])
    step = probe({"type_step_min": 1.25}, [txt("t1", size=44), txt("t2", y=400, size=48)])
    bold = probe({"bold_ratio_max": 0.4},
                 [txt(f"t{i}", y=100 + i * 100, width=300, height=60, bold=i < 4) for i in range(5)])
    check("seed: 方向种子五个量各能点名一次（留白 / 背景层 / 字号级差 / 粗体占比）",
          bool(ws) and bool(bg) and bool(step) and bool(bold),
          f"留白={len(ws)} 背景层={len(bg)} 级差={len(step)} 粗体={len(bold)}")

    # ② 未声明 = 不检查（手写 spec 不会被方向默认值吵到）
    check("seed: 未声明约束不检查、达标不吵（空约束 + 空气页都 0 条）",
          not probe({}, [txt("t1")]) and not probe({"whitespace_min": 0.5}, [txt("t1")]),
          "干净探针 0 条 direction_seed")

    # ③ 别名与键名点名：min_whitespace 仍可用，拼错的键必须被 theme_constraints 抓到
    alias = probe({"min_whitespace": 0.5}, [box, txt("t1")])
    spec_typo = {"canvas": {"width": 1280, "height": 720},
                 "theme": {"colors": colors, "constraints": {"accent_max": 0.05, "white_space": 0.5}},
                 "slides": [{"id": "s01",
                             "page_intent": {"insight": "x", "focus": "t1", "page_family": "COVER",
                                             "density": "sparse", "energy": "high",
                                             "empty_space_role": "hold_emotion"},
                             "elements": [txt("t1")]}]}
    typo = [c for c in _guard.check_spec(spec_typo)["checks"] if c["rule"] == "theme_constraints"]
    check("seed: min_whitespace 别名仍生效、写错的约束键被 theme_constraints 点名",
          bool(alias) and bool(typo) and _guard.check_spec(spec_typo)["passed"],
          f"别名={len(alias)} 条 · 未知键={len(typo)} 条")

    # ④ 方向 → plan → 骨架：种子必须原样落到生成侧手里
    brief = work / "seed_brief.yml"
    brief.write_text("audience: 官网访客\ndecision: 是否申请试用\nsubject: 产品发布\n"
                     "occasion: 发布会\ndesign_direction: product_stage\n"
                     "slides:\n  - {id: s01, family: cover, title: 开场}\n", encoding="utf-8")
    out = work / "seed_plan.json"
    skel = work / "seed_build.py"
    run_vao("plan", str(brief), "--out", str(out), "--skeleton", str(skel))
    plan = json.loads(out.read_text(encoding="utf-8")).get("plan") or {}
    cons = (plan.get("theme") or {}).get("constraints") or {}
    body = skel.read_text(encoding="utf-8")
    check("seed: 方向种子落进 plan.theme.constraints 并被骨架原样交给生成侧",
          cons.get("whitespace_min") == 0.48 and cons.get("bg_layers_max") == 2
          and "whitespace_min" in body and "guard 会照着它执法" in body,
          f"plan={sorted(cons)} · 骨架含种子={'whitespace_min' in body}")


def check_chart_argument(work: pathlib.Path) -> None:
    """论点可见性：零基长度编码 + 数值几乎等长 + 图自己标了重点 ⇒ 差异看不见。

    触发条件全是可判定的：不解析主张文本、不评分、不做审美裁决。几何读不出来就是读不出来。
    真实案例：盲测第 4 页把「差 14 个百分点」画成 104 与 118 两根条（1.13×）。
    """
    import guard as _guard

    colors = {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
              "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"}

    def probe(chart: dict, kind: str = "bar") -> list:
        spec = {"canvas": {"width": 1280, "height": 720}, "theme": {"colors": colors},
                "slides": [{"id": "s01",
                            "page_intent": {"insight": "净留存高出 14 个百分点", "focus": "c1",
                                            "page_family": "DATA_STORY", "density": "balanced",
                                            "energy": "low", "empty_space_role": "protect_focus"},
                            "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 40},
                            "elements": [dict({"type": "chart", "id": "c1", "chart_kind": kind,
                                               "x": 96, "y": 240, "width": 1088, "height": 320,
                                               "unit": "%", "period": "2026 H1", "basis": "同口径",
                                               "source": "客户成功系统"}, **chart)]}]}
        return [c for c in _guard.check_spec(spec)["checks"] if c["rule"] == "chart_argument"]

    flat = {"data": [{"label": "席位制", "value": 104}, {"label": "用量制", "value": 118}],
            "highlight": "用量制"}
    check("chart: 等长条 + 标了重点 ⇒ 差异不可见被点名（104 vs 118 = 1.13×）", bool(probe(flat)))
    check("chart: 没有重点信号 / 差异够大 / 非长度编码 / 声明了基线 ⇒ 不打扰",
          not probe({"data": flat["data"]})
          and not probe({"data": [{"label": "A", "value": 2.8}, {"label": "B", "value": 5.4}],
                         "highlight": "B"})
          and not probe(flat, kind="line")
          and not probe({**flat, "baseline": 100}),
          "四种「不该报警」的情形都安静")


def check_deck_anchor(work: pathlib.Path) -> None:
    """跨页锚：plan 发锚 → 生成侧落元素 → guard 查「在不在 / 位置是否同一个 / 编号是否连续」。"""
    import guard as _guard

    colors = {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
              "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"}

    def page(sid, anchors, eyebrow_y=40, pn_xy=(1200, 680), fig=None, chart=False, eyebrow=True):
        els = []
        if eyebrow and anchors.get("eyebrow"):
            els.append({"type": "text", "id": "eb", "x": 96, "y": eyebrow_y, "width": 320,
                        "height": 24, "text": anchors["eyebrow"], "size": 12, "color": "muted",
                        "role": "eyebrow", "max_lines": 1})
        if anchors.get("page_number") is not None:
            els.append({"type": "text", "id": "pn", "x": pn_xy[0], "y": pn_xy[1], "width": 40,
                        "height": 24, "text": str(anchors["page_number"]), "size": 12,
                        "color": "muted", "role": "page_number", "max_lines": 1})
        if fig:
            els.append({"type": "text", "id": "fig", "x": 96, "y": 620, "width": 320, "height": 24,
                        "text": f"{fig} 客户成功系统 · 2026 H1", "size": 12, "color": "muted",
                        "role": "caption", "max_lines": 1})
        if chart:
            els.append({"type": "chart", "id": "c1", "chart_kind": "bar", "x": 96, "y": 200,
                        "width": 1000, "height": 320, "unit": "%", "period": "2026",
                        "basis": "同口径", "source": "系统",
                        "data": [{"label": "A", "value": 10}, {"label": "B", "value": 30}]})
        return {"id": sid, "page_intent": {"insight": "x", "focus": "eb", "page_family": "COVER",
                "density": "sparse", "energy": "high", "empty_space_role": "hold_emotion"},
                "anchor": anchors, "elements": els}

    def hits(slides):
        spec = {"canvas": {"width": 1280, "height": 720}, "theme": {"colors": colors},
                "slides": slides}
        return [c for c in _guard.check_spec(spec)["checks"] if c["rule"] == "deck_anchor"]

    A = {"eyebrow": "DATA STORY", "page_number": 2, "figure": "Fig. 01"}
    B = {"eyebrow": "COMPARISON", "page_number": 3, "figure": "Fig. 02"}
    check("anchor: 齐整的锚不吵；缺元素 / 眉标漂移 / 页码换象限 / 编号断链 各被点名一次",
          not hits([page("s01", A), page("s02", B)])
          and bool(hits([page("s01", A, eyebrow=False), page("s02", B)]))
          and bool(hits([page("s01", A), page("s02", B, eyebrow_y=64)]))
          and bool(hits([page("s01", A), page("s02", B, pn_xy=(1100, 640))]))
          and bool(hits([page("s01", A), page("s02", {"eyebrow": "X", "figure": "Fig. 05"})])),
          "五组探针")

    # plan → 骨架：≥4 页才发锚，且每页锚是「事实」不是开关
    brief = work / "anchor_brief.yml"
    brief.write_text("audience: 董事会\ndecision: 定稿\nsubject: 复盘\noccasion: 季度会\n"
                     "slides:\n"
                     "  - {id: s01, family: cover, title: 开场}\n"
                     "  - {id: s02, family: statement, title: 判断}\n"
                     "  - {id: s03, family: data, title: 证据}\n"
                     "  - {id: s04, family: closing, title: 收束}\n", encoding="utf-8")
    out = work / "anchor_plan.json"
    skel = work / "anchor_build.py"
    run_vao("plan", str(brief), "--out", str(out), "--skeleton", str(skel))
    plan = json.loads(out.read_text(encoding="utf-8")).get("plan") or {}
    pages = plan.get("pages") or []
    anchors = [p.get("anchor") or {} for p in pages]
    body = skel.read_text(encoding="utf-8")
    check("anchor: ≥4 页 deck 逐页发锚（眉标/页码/证据编号）且骨架原样交给生成侧",
          len(anchors) == 4 and anchors[0].get("eyebrow") and "page_number" not in anchors[0]
          and anchors[2].get("figure") == "Fig. 01" and anchors[3].get("page_number") == 4
          and '"anchor"' in body and "role=eyebrow" in body,
          f"锚={anchors}")


def check_anti_regression() -> None:
    py_files = sorted(SCRIPTS.glob("*.py"))
    text = {p.name: p.read_text(encoding="utf-8") for p in py_files}
    banned = ("soffice", "libreoffice", "pdftoppm", "render_check", "layout_search")
    hits = {n: [b for b in banned if b in t.lower()] for n, t in text.items()}
    hits = {n: h for n, h in hits.items() if h and n != "selftest.py"}
    check("no-renderer: 代码里不再有外部渲染器与布局引擎", not hits, str(hits))

    cli = [n for n, t in text.items()
           if n not in ("vao.py", "selftest.py") and '__name__ == "__main__"' in t]
    check("single-entry: 只有 vao.py 暴露 CLI", not cli, str(cli))

    # 文档死引用（README/SKILL/references 里提到的仓库文件必须存在）
    # 仓库里真实存在的文件名（凡是文档提到的作业文件，必须能找到）
    known = {p.name for p in ROOT.rglob("*") if p.is_file()}
    allow = {"build_deck.py", "build_mydeck.py", "build.py", "brief.yml", "plan.json",
             "out.pptx", "out.repair.json", "deck.pptx", "asset_manifest.json",
             "asset_prompt_cache.json", "generated_assets", "rounds.json",
             "compile_cache.json", "manifest.json", "out.manifest.json", "entry.json"}
    missing = set()
    for doc in list(ROOT.glob("*.md")) + list((ROOT / "references").glob("*.md")):
        for ref in re.findall(r"[\w./-]+\.(?:md|py|yml|json)", doc.read_text(encoding="utf-8")):
            name = ref.split("/")[-1]
            if name in allow or ref.startswith(("http", "pip")) or name in known:
                continue
            missing.add(ref)
    check("docs: 文档不引用不存在的文件", not missing, str(sorted(missing)))

    types = pathlib.Path(ROOT / "templates" / "brief.yml")
    check("templates: 单一 brief 契约存在", types.exists())

    # 文档只写代码真的认得的词汇：文档里出现「不存在的字段/枚举/规则码」，
    # 作者会照着写，然后被无声忽略——这是最贵的一类文档债。
    legacy = ("gravity_anchor", "vp-00", "perception_goal", "spatial_grammar",
              "typography_voice", "media_behavior", "chart_behavior", "forbidden_signals",
              "differentiation", "fact_basis_mismatch", "invalid_data", "batch.deferred",
              "hold_attention", "frame_focus", "art_critic", "layout_search", "render_check")
    docs = list(ROOT.glob("*.md")) + list((ROOT / "references").glob("*.md"))
    drift = {d.name: [w for w in legacy if w in d.read_text(encoding="utf-8").lower()]
             for d in docs}
    drift = {n: w for n, w in drift.items() if w}
    check("docs: 文档不出现代码未实现的字段/枚举/规则码（防止照着写被静默忽略）",
          not drift, str(drift))

    # 文档列阻断码时必须列全：少一条 = 作者以为它可忽略
    import qa as _qa
    _codes = set(_qa.BLOCKING_CODES)
    partial = {}
    for d in [ROOT / "SKILL.md", ROOT / "references" / "production-contract.md"]:
        txt = d.read_text(encoding="utf-8")
        named = {c for c in _codes if c in txt}
        if named and named != _codes:
            partial[d.name] = sorted(_codes - named)
    check("docs: 阻断码清单要么不列、要么 9/9 列全（缺项 = 作者以为它可忽略）",
          not partial, str(partial))


# ── D. 判断层完整性（技能包的价值在这里，退化也最先在这里） ────────────────
def check_judgment_layer(work: pathlib.Path) -> None:
    import design_intelligence as di
    import guard
    import qa
    import route

    # D1 每个家族都必须拿到专属叙事动作与构图语法：表里错一个键，
    #    整类页面会静默退回兜底句——判断看起来发生了，其实没有。
    generic = "先决定这页唯一的主语"
    moves = {fam: di.page_move(fam).get("move") or "" for fam in
             {r["family"] for r in route.ROUTES.values()}}
    weak_moves = sorted(f for f, m in moves.items() if not m or m.startswith(generic))
    grammars = {fam: di.composition_move(fam, "balanced", "medium").get("grammar")
                for fam in {r["family"] for r in route.ROUTES.values()}}
    weak_comp = sorted(f for f, g in grammars.items()
                       if g not in di.COMPOSITION_POOL)
    check("families: 每个家族都有专属叙事动作与构图语法",
          not weak_moves and not weak_comp, f"moves={weak_moves} composition={weak_comp}")

    # D2 显式声明优先：family / type / 中文 / 整串写法都要落到同一条路由
    cases = {"cover": "cover", "DATA_STORY": "data", "数据": "data",
             "FRAMEWORK": "architecture", "narrative": "process", "对比": "comparison"}
    wrong = {raw: route.explicit_content_type({"family": raw})
             for raw, want in cases.items()
             if route.explicit_content_type({"family": raw}) != want}
    check("explicit-type: 显式 family/type 归一后不被关键词改写", not wrong, str(wrong))

    # D3 骨架与 plan 同源：页数一致、density/energy 一致（两处各写一份必分叉）
    brief = work / "families.yml"
    brief.write_text(
        "audience: 评审\ndecision: 定稿\nslides:\n"
        "  - {id: s01, family: cover, title: 开场}\n"
        "  - {id: s02, family: DATA_STORY, title: 数据}\n"
        "  - {id: s03, family: framework, title: 体系, density: balanced}\n"
        "  - {id: s04, family: closing, title: 收束}\n", encoding="utf-8")
    plan_path, skel = work / "fam_plan.json", work / "fam_build.py"
    run_vao("plan", str(brief), "--out", str(plan_path), "--skeleton", str(skel))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    route_pages = (plan.get("plan") or {}).get("pages") or []
    body = skel.read_text(encoding="utf-8")
    header = re.findall(r"# ── (s\d+) · family=(\S+) · density=(\S+) · energy=(\S+)", body)
    same = (len(route_pages) == 4 and len(header) == 4
            and all(str(pg.get("density")) == d and str(pg.get("energy")) == e
                    for (sid, _f, d, e), pg in zip(header, route_pages)))
    check("skeleton: 页数与 plan 一致，density/energy 同源",
          same and body.count('"id":') == 4, f"pages={len(route_pages)} header={len(header)}")
    check("plan: 每页带 composition（构图语法提案，零坐标）",
          all((pg.get("composition") or {}).get("grammar") for pg in plan.get("pages") or []))

    # D4 验证不评分：guard / qa 的结果里不得再出现分数或评级
    spec = {"canvas": {"width": 1280, "height": 720},
            "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                                 "primary": "#222222", "secondary": "#333333", "accent": "#AA0000"},
                      "fonts": {"display": "A", "body": "A"}},
            "slides": [{"id": "s01", "elements": []}]}
    guard_result = guard.check_spec(spec)
    qa_result = qa.run_qa(spec, work / "score_probe.pptx", mode="spec")
    scored = [k for k in ("score", "grade", "rating") if k in guard_result or k in qa_result]
    check("no-score: 验证层不产出分数/评级（只回答能不能交付）", not scored, str(scored))

    # D5 家族链路三处判断必须齐全：媒体判断（含别名）、质量预算、构图起点。
    #    任何一处少一条，那一类页面就会静默退回默认——判断看起来发生了，其实没有。
    from design_intelligence_rules import (FAMILY_MOVES, FAMILY_ALIASES, MEDIA_MODEL,
                                           ASYMMETRIC_OK_FAMILIES, COMPLEX_LAYOUT_FAMILIES)
    unnamed = sorted(fam for fam in FAMILY_MOVES
                     if "未知家族" in str(di.media_decision(
                         {"page_intent": {"page_family": fam}}).get("reason")))
    no_budget = sorted(fam for fam in FAMILY_MOVES
                       if di.normalize_family(fam) not in di.QUALITY_BUDGETS)
    bad_alias = sorted(t for t in FAMILY_ALIASES.values() if t not in MEDIA_MODEL)
    drift = sorted(ASYMMETRIC_OK_FAMILIES - set(MEDIA_MODEL)) + \
        sorted(COMPLEX_LAYOUT_FAMILIES - set(FAMILY_MOVES))
    check("families: 媒体判断/质量预算/别名目标三处齐全（无静默回落）",
          not unnamed and not no_budget and not bad_alias,
          f"无名={unnamed} 无预算={no_budget} 坏别名={bad_alias}")
    check("families: 家族常量不越界（豁免集/复杂集都在真源命名空间内）", not drift, str(drift))
    check("composition: 构图起点表与家族真源同集（两处各写一份必分叉）",
          set(di.COMPOSITION_BY_FAMILY) == set(FAMILY_MOVES),
          str(sorted(set(di.COMPOSITION_BY_FAMILY) ^ set(FAMILY_MOVES))))

    # D6 枚举值写错必须点名：家族（含只被媒体模型认识的命名空间）/留白职责/能量/密度。
    #    同时确认它是 warn 而非 error——「值不认识」是工程事实，不是「这页不合格」。
    probe = {"id": "s01",
             "page_intent": {"insight": "结论句", "focus": "t1", "page_family": "CLOSING",
                             "empty_space_role": "quiet_center", "energy": "mediumish",
                             "density": "airy"},
             "elements": [{"type": "text", "id": "t1", "x": 96, "y": 240, "width": 800,
                           "height": 120, "text": "一句话结论", "size": 64, "color": "ink",
                           "role": "title", "line_height": 1.1, "max_lines": 1}]}
    probe_spec = {"canvas": spec["canvas"], "theme": spec["theme"], "slides": [probe]}
    checks = guard.check_spec(probe_spec).get("checks") or []
    named = " ｜ ".join(c.get("msg", "") for c in checks if c.get("rule") == "page_contract")
    fields = [f for f in ("page_family", "empty_space_role", "energy", "density")
              if f"{f}=" in named]
    levels = {c.get("level") for c in checks
              if c.get("rule") == "page_contract" and "不在合法取值内" in str(c.get("msg"))}
    check("enums: 非法家族/留白职责/能量/密度会被点名（warn，不阻断交付）",
          len(fields) == 4 and levels == {"warn"} and guard.check_spec(probe_spec).get("passed"),
          f"fields={fields} levels={levels}")

    # D7 经验库结构自检：坏条目要能被点名，而不是永远静默命不中
    report = di.validate_dna_store()
    check("memory: 出厂经验库结构合法（0 error）",
          bool(report["ok"]), str(report["errors"][:2]))

    # D8 记忆写路径闭环：写入 → 召回 → 幂等 → 拒收坏条目 → 库文件不可写时拒写
    tmp_store = work / "dna_probe.json"
    entry = {"id": "selftest_roundtrip", "pattern": "测试：视线先于元素",
             "signature": {"keywords": ["视线", "composition", "构图"]},
             "design_problem": "先摆元素再想视线", "judgment": {"structure": "先定视线路径再落元素"},
             "works_because": "视线是读者的实际顺序", "avoid": ["先排版后补叙事"],
             "when_not_to": "纯对照页", "proven": {"project": "selftest"}}
    first = di.record_dna(entry, path=tmp_store)
    again = di.record_dna(entry, path=tmp_store)
    rejected = di.record_dna(dict(entry, id="bad", judgment={"vibes": "x"}), path=tmp_store)
    saved = di.DNA_STORE
    di.DNA_STORE = tmp_store
    hit = di.recall_dna({"title": "构图与视线", "subject": "composition"})
    di.DNA_STORE = saved
    check("memory: 写入→召回→幂等→拒收坏条目（写坏的记忆比不写更贵）",
          first.get("added") and not again.get("added") and again.get("note", "").startswith("同 id")
          and not rejected.get("added") and hit.get("matched") == "selftest_roundtrip",
          f"first={first.get('added')} again={again.get('added')} rejected={rejected.get('added')} ")
    check("memory: 库文件损坏时拒绝写入（不把空库写回、经验不灭）",
          _dna_write_guard(work), "写坏库 → record_dna 应抛错并保持文件原样")


def _dna_write_guard(work: pathlib.Path) -> bool:
    """库文件损坏时，record_dna 必须拒写且不改动文件。"""
    import design_intelligence as di
    broken = work / "dna_broken.json"
    broken.write_text("{ 这不是 JSON", encoding="utf-8")
    before = broken.read_text(encoding="utf-8")
    ok = False
    try:
        di.record_dna({"id": "x", "pattern": "p", "judgment": {"media": "m"},
                       "signature": {"keywords": ["k"]}}, path=broken)
    except Exception:
        ok = True
    return ok and broken.read_text(encoding="utf-8") == before


def png_stamp(directory: pathlib.Path) -> str:
    """预览目录里所有 PNG 的字节戳：判断这一轮有没有重新渲染。"""
    h = hashlib.sha256()
    for path in sorted(pathlib.Path(directory).glob("*.png")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def check_doc_counts() -> None:
    """文档里的自检项数必须等于实际项数。

    这一类漂移没有代码会报错（数字只是散文），但读者会照它判断「验证网有多大」。
    放在最后一项执行：此时 RESULTS 已含除本项以外的全部检查，总数 = len(RESULTS) + 1。
    """
    import re as _re
    total = len(RESULTS) + 1
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    stated = {int(m) for m in _re.findall(r"(\d+)\s*项", readme)}
    check(f"docs: README 里的自检项数与实际一致（实际 {total} 项）",
          stated == {total}, f"README 写着 {sorted(stated)}")

def main() -> int:
    work = pathlib.Path(tempfile.mkdtemp(prefix="vao-selftest-"))
    try:
        check_readability_seam()
        check_pipeline(work)
        check_contracts(work)
        check_judgment_layer(work)
        check_font_channel(work)
        check_direction_seed(work)
        check_chart_argument(work)
        check_deck_anchor(work)
        check_anti_regression()
        check_doc_counts()
    finally:
        shutil.rmtree(work, ignore_errors=True)
    width = max(len(n) for n, _, _ in RESULTS)
    failed = 0
    for name, ok, detail in RESULTS:
        failed += 0 if ok else 1
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {name:<{width}}"
        if not ok and detail:
            line += f"  ← {detail}"
        print(line)
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
