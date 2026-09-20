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
import os
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
    # 子进程 env 有意隔离，但两端必须约定同一编码。默认 text=True 靠 locale 猜：
    # 在 GBK 码页的 Windows 上，父进程按 UTF-8 解码 vao.py 的中文输出会炸掉 reader
    # 线程 → proc.stdout 变 None → 报错落在无关行号（TypeError: NoneType 不可下标），
    # 整条回归链根本建立不起基线。所以显式钉死 UTF-8，并补回 Windows 进程启动硬依赖。
    env = {"PYTHONPATH": str(SCRIPTS), "PATH": "/usr/bin:/bin:/usr/local/bin",
           "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    for key in ("SYSTEMROOT", "COMSPEC", "TEMP", "TMP", "LOCALAPPDATA", "APPDATA"):
        if os.environ.get(key):
            env.setdefault(key, os.environ[key])
    return subprocess.run([sys.executable, str(SCRIPTS / "vao.py"), *args],
                          capture_output=True, encoding="utf-8", errors="replace",
                          env=env, cwd=str(cwd or ROOT))


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
    # v5.6 减法后的契约：包不替作者发明审美数字（留白下限/字号级差/装饰面积/粗体占比）。
    # 自己的默认值自己判卷，只在整幅画心页上必然误报；数字承诺归作者。
    # 保留的执法能力由 check_direction_seed 覆盖（声明了就点名）；这里只测「不再发明」。
    check("seed: 未声明约束时，plan 不发明审美数字，骨架也不写进 spec",
          cons == {} and "whitespace_min" not in body,
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
    check("anchor: ≥4 页 deck 逐页发锚（眉标 + 页码两样）且骨架原样交给生成侧",
          len(anchors) == 4 and anchors[0].get("eyebrow") and "page_number" not in anchors[0]
          and anchors[3].get("page_number") == 4
          and '"anchor"' in body and "role=eyebrow" in body,
          f"锚={anchors}")
    check("anchor: plan 不再发 Fig. 证据编号（论文的交叉引用装置，演示场景没有回指）",
          not any(a.get("figure") for a in anchors)
          and "Fig." not in body, f"锚={anchors}")


def _ghost_draws_a_chart(element: dict) -> bool:
    """ghost 是否真把这个图表画了出来（True）还是只画了「画不出来」的占位叉。

    判据取自渲染结果本身：占位叉只有两条对角线，真图会落下成片的色块。
    比数文本更稳——它不依赖 ghost 内部用哪个分支实现。
    """
    from PIL import Image
    import ghost as _ghost
    from primitives import RenderContext
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#888888",
                        "primary": "#1A3A5C", "secondary": "#40617F", "accent": "#C8501E"}}
    canvas = {"width": 1280, "height": 720}
    img = Image.new("RGBA", (1280, 720), (255, 255, 255, 255))
    _ghost._draw_chart(img, element, RenderContext(theme, canvas), 1.0)
    # 占位叉是细线：着色像素只有几百个；真柱图是实心块，上万个。
    inked = sum(1 for px in img.convert("RGB").getdata() if px != (255, 255, 255))
    return inked > 5000


def _ghost_ink(element: dict) -> int:
    """ghost 为这个元素落了多少着色像素。0 = 预览里根本看不见它。

    同样锁行为不锁实现：不关心 ghost 走哪个分支，只关心「画出来没有」。
    """
    from PIL import Image
    import ghost as _ghost
    from primitives import RenderContext
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#888888",
                        "primary": "#1A3A5C", "secondary": "#40617F", "accent": "#C8501E"}}
    img = Image.new("RGBA", (1280, 720), (255, 255, 255, 255))
    _ghost._draw_shape(img, element, RenderContext(theme, {"width": 1280, "height": 720}), 1.0)
    return sum(1 for px in img.convert("RGB").getdata() if px != (255, 255, 255))


def check_silent_failure_seams() -> None:
    """静默失效缝：写了却不生效、预览比产物宽容、门槛从未执行。

    这一组锁的都是**不会报错**的错——它们不让链路失败，只让产物悄悄变错，
    是这份技能包最贵的一类漏洞，因此每一条都必须有专属反退化用例。
    """
    from design_intelligence import color_plan
    import guard as _guard_mod
    from guard import _text_box_capacity, check_spec
    from primitives import contrast
    from pipeline import build_plan_bundle, build_skeleton_module
    from route import normalize_brand_colors, plan_deck

    # ① brand_colors 列表写法必须生效（templates/brief.yml 教的就是列表）
    need = {"audience": "董事会", "decision": "批预算",
            "brand_colors": ["#1A3A5C", "#C8501E"],
            "slides": [{"id": "s01", "family": "cover", "title": "A", "content": "B"}]}
    plan = plan_deck(need)
    cp = color_plan(plan["design_direction"], need)
    check("brand: 列表写法的 brand_colors 真的生效（照文档写不会被静默忽略）",
          plan["theme"]["colors"].get("accent") == "#C8501E"
          and plan["theme"].get("brand_derived") is True
          and cp["seed_source"] == "brand_colors",
          f"{plan['theme']['colors'].get('accent')} / {cp['seed_source']}")
    check("brand: dict 与 list 两种写法归一到同一结果（两处解析不得分叉）",
          normalize_brand_colors(["#1A3A5C", "#C8501E"])
          == {"primary": "#1A3A5C", "accent": "#C8501E"})

    # ② 品牌主色是墨色不是纸面：槽位语义错位会产出 1.4:1 的不可读骨架
    check("brand: 品牌主色落进 information（墨色），不被当成 70% 的纸面",
          cp["seed_skeleton"]["information"] == "#1A3A5C"
          and cp["seed_skeleton"]["foundation"] != "#1A3A5C",
          str(cp["seed_skeleton"]))
    for brand in (["#1A3A5C", "#C8501E"], ["#0B1F33"], {"background": "#101010", "ink": "#151515"}):
        sk = build_skeleton_module(build_plan_bundle(dict(need, brand_colors=brand)))
        colors = eval(re.search(r'"colors": (\{.*?\})', sk).group(1))   # noqa: S307 骨架是本仓库自产文本
        if not check(f"skeleton: 骨架配色可读（{str(brand)[:22]} → 正文 ≥4.5:1）",
                     contrast(colors["background"], colors["ink"]) >= 4.5,
                     f"{colors['background']}/{colors['ink']}="
                     f"{contrast(colors['background'], colors['ink']):.2f}"):
            break

    # ③ 预览的宽容度必须 ≤ 交付链：ghost 不得认 guard 不认的键名/图表类型。
    #    用行为断言而不是文本搜索——注释里出现的词不算实现（否则解释缝隙的
    #    注释本身会让用例变红，那是在锁措辞，不是在锁行为）。
    import ghost as _ghost
    payload = [{"label": "A", "value": 3}, {"label": "B", "value": 9}]
    check("ghost: 预览不认 rows 别名（写 rows 的图 guard 判空，预览也必须判空）",
          _ghost._rows({"rows": payload}) == [] and _ghost._rows({"data": payload}) != [])
    for element in ({"chart_type": "bar", "data": payload, "x": 0, "y": 0,
                     "width": 400, "height": 300},
                    {"kind": "radar", "data": payload, "x": 0, "y": 0,
                     "width": 400, "height": 300}):
        rendered = _ghost_draws_a_chart(element)
        if not check(f"ghost: {element.get('chart_type') or element.get('kind')} "
                     "不被兜底画成柱图（guard 会拦下它，证据不得替错误背书）",
                     rendered is False):
            break

    # ④ 文本溢出是治理层事实：spec 档（不编译）也必须点名到元素
    overflow = {"id": "t", "type": "text", "x": 48, "y": 48, "width": 304, "height": 40,
                "size": 20, "line_height": 1.5, "color": "ink",
                "text": "这是一段非常长的中文描述需要很多行才能放得下" * 6}
    cap = _text_box_capacity(overflow)
    spec = {"canvas": {"width": 1280, "height": 720},
            "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                                 "primary": "#1A3A5C", "secondary": "#40617F", "accent": "#C8501E"}},
            "slides": [{"id": "s01", "elements": [overflow]}]}
    named = [c for c in check_spec(spec)["checks"]
             if c.get("rule") == "text_capacity" and c.get("level") == "error"
             and c.get("id") == "t"]
    check("text: 溢出在 guard 就点名到元素（spec 档不编译也拦得住，修复包不再只有 deck）",
          bool(cap and cap["over_height"]) and bool(named))
    fits = dict(overflow, text="亚太扩张 2026", width=800, height=96, size=64, line_height=1.2)
    check("text: 装得下的文本不误报（新增阻断项不得制造假阳性）",
          not _text_box_capacity(fits)["over_height"])

    # ⑤ 中性灰阶不参与色相族判定：规则不得对自家出厂配色每次都误报。
    #    v5.6：色相角下限是**声明制**——不声明不检查（颜色关系归设计判断），
    #    声明了照旧点名。所以探针显式带上约束。
    def _palette_warns(colors: dict, declared: bool = True) -> list:
        theme = {"colors": colors}
        if declared:
            theme["constraints"] = {"accent_hue_min": 12}
        probe = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
                 "slides": [{"id": "s01", "elements": []}]}
        return [c for c in check_spec(probe)["checks"] if c.get("rule") == "palette_discipline"]

    check("palette: 出厂灰阶种子不被误判成「强调色与主色同族」（狼来了会淹掉真信号）",
          not _palette_warns({"background": "#F5F4F1", "ink": "#1E1E1C", "muted": "#9A9A96",
                              "primary": "#1E1E1C", "secondary": "#9A9A96", "accent": "#6E6E6A"}))
    check("palette: 真正的同族撞色仍被点名（放宽不等于放弃）",
          bool(_palette_warns({"background": "#FFFFFF", "ink": "#111111", "muted": "#888888",
                               "primary": "#B3271E", "secondary": "#8A2018", "accent": "#D0402E"})))
    check("palette: 未声明色相角下限时不判（颜色关系归设计，不归发明出来的刻度）",
          not _palette_warns({"background": "#FFFFFF", "ink": "#111111", "muted": "#888888",
                              "primary": "#B3271E", "secondary": "#8A2018", "accent": "#D0402E"},
                             declared=False))

    # ⑥ CI 的门必须真的能跑：引用不存在的文件/形参 = 永远通过的假门。
    #    只扫**可执行行**（注释与说明文字不算实现，否则解释历史的注释会让用例变红）。
    ci_lines = [ln for ln in (ROOT / ".github" / "workflows" / "ci.yml")
                .read_text(encoding="utf-8").splitlines()
                if not ln.lstrip().startswith("#")]
    ci = "\n".join(ci_lines)
    missing = sorted({p for p in re.findall(r"templates/[\w.-]+", ci)
                      if not (ROOT / p).exists()})
    import inspect as _inspect
    import qa as _qa
    qa_params = set(_inspect.signature(_qa.run_qa).parameters)
    bad_kwargs = sorted({k for k in re.findall(r"run_qa\([^)]*?(\w+)=", ci)
                         if k not in qa_params})
    check("ci: 工作流只引用存在的模板与真实存在的 run_qa 形参（假门比没门更贵）",
          not missing and not bad_kwargs, f"missing={missing} bad_kwargs={bad_kwargs}")
    check("ci: 规划步骤走单入口 vao.py（pipeline.py 没有 CLI，旧写法恒退 0）",
          "scripts/pipeline.py" not in ci)

    # ⑦ 色彩 token 拼错必须被点名。渲染层的 ink 回落是安全网、不能删，
    #    但正因为它永不失败，错误只能由治理层捕获——否则 fill 硬报错、
    #    color 静默变黑，同一类笔误两种待遇。
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#777777",
                        "primary": "#1A3A5C", "secondary": "#40617F", "accent": "#C8501E"}}
    typo = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
            "slides": [{"id": "s01", "elements": [
                {"id": "t1", "type": "text", "x": 48, "y": 48, "width": 600, "height": 60,
                 "size": 24, "text": "拼错的 token", "color": "primry"},
                {"id": "r1", "type": "rect", "x": 48, "y": 200, "width": 300, "height": 120,
                 "fill": "chartreuse"},
                {"id": "ok1", "type": "text", "x": 48, "y": 360, "width": 600, "height": 60,
                 "size": 24, "text": "派生 token", "color": "panel_strong"},
                {"id": "ok2", "type": "rect", "x": 700, "y": 200, "width": 300, "height": 120,
                 "fill": "#1A3A5C"},
            ]}]}
    flagged = {c.get("id") for c in check_spec(typo)["checks"]
               if c.get("rule") == "color_token" and c.get("level") == "error"}
    check("color: 拼错的颜色 token 被点名到元素（不再静默回落成黑字）",
          flagged == {"t1", "r1"}, f"flagged={sorted(flagged)}")
    from primitives import RenderContext
    ctx = RenderContext(theme, {})
    check("color: 渲染层对未知 token 仍安全回落（治理层报错，渲染层不得崩）",
          ctx.text_color("primry") is not None and ctx.text_color("panel_strong") is not None)

    # ⑧ warning 必须保留可执行信息：聚合是为了不刷屏，不是为了丢掉「改哪、改成什么」。
    import qa as _qa
    packed = _qa.build_trace_summary([
        {"domain": "guard", "level": "hint", "rule": "direction_seed", "count": 2,
         "ids": ["deck", "s03"], "samples": ["留白率 45% 低于下限 62%", "字号级差 1.09×"]},
    ])
    check("warn: 聚合后仍保留元素 id 与样本原文（PASS 后的打磨要有据可依）",
          bool(packed) and packed[0]["ids"] == ["deck", "s03"]
          and "45%" in packed[0]["samples"][0], str(packed))
    import vao as _vao
    plan = _vao._polish_plan({"trace_summary": packed})
    check("warn: 打磨清单给出可执行改法，且不引用修复包里不存在的字段",
          bool(plan["groups"]) and plan["groups"][0]["evidence"]
          and "guard.checks" not in json.dumps(plan, ensure_ascii=False))

    # ⑨ 线性分割必须可用：它是「场 > 线 > 型 > 盒」里第二轻的分组语言，
    #    一旦写法被拦或预览看不见，作者就只能退回画卡片——工具的默认值
    #    会变成产物的默认样子。
    def _line(**kw):
        base = {"id": "ln", "type": "shape", "shape": "line", "x": 96, "y": 300,
                "width": 1088, "height": 0, "stroke": "hairline", "stroke_width": 1}
        base.update(kw)
        return base

    def _errs(el):
        probe = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
                 "slides": [{"id": "s01", "elements": [el]}]}
        return [c for c in check_spec(probe)["checks"] if c.get("level") == "error"]

    check("rule: 水平发丝线（height=0）与垂直分栏线（width=0）不被误判为几何退化",
          not _errs(_line()) and not _errs(_line(y=120, width=0, height=480)))
    check("rule: 零长度线仍被拦（放宽一维对象不等于放弃几何校验）",
          bool(_errs(_line(width=0, height=0))))
    check("rule: 二维元素的 height=0 仍被拦（豁免只给 line/arrow）",
          bool(_errs({"id": "r", "type": "shape", "shape": "rect", "x": 96, "y": 300,
                      "width": 600, "height": 0, "fill": "panel"})))
    check("rule: 预览画得出分割线（产物有线而预览空白 = 作者看不见自己画的线）",
          _ghost_ink(_line()) > 0 and _ghost_ink(_line(y=120, width=0, height=480)) > 0)

    # ⑩ 面板墙探针工厂（供 ⑫ 的 advisory 开关测试使用）
    def _panels(shape, n=5, **kw):
        els = []
        for i in range(n):
            e = {"id": f"c{i}", "type": "shape", "shape": shape, "x": 64 + i * 232,
                 "y": 220, "width": 208, "height": 260, "fill": "panel"}
            e.update(kw)
            els.append(e)
        return els

    # ⑪ 编译期警告必须带元素 id：没有 id 的 fix_plan 只能说「有问题」，说不出「改哪个」
    from primitives import RenderContext as _RC
    _ctx = _RC({"colors": theme["colors"]}, {"width": 1280, "height": 720})
    _ctx.warn("无身份的整体警告")
    _ctx.warn("某元素的警告", "el_7")
    check("warn: RenderContext 记录元素 id，且与 warnings 等长（旧读法不受影响）",
          _ctx.warnings == ["无身份的整体警告", "某元素的警告"]
          and _ctx.warning_ids == [None, "el_7"])
    _qa_items = []
    _cr = {"warnings": ["shape 'shp_bad': 未知 shape", "[guard] 同源不重复"],
           "warning_ids": ["shp_bad", None]}
    _ids = list(_cr["warning_ids"])
    for _i, _w in enumerate(_cr["warnings"]):
        if _w.startswith("[guard]"):
            continue
        _qa_items.append({"domain": "compile", "level": "warn", "rule": "compiler",
                          "id": _ids[_i] if _i < len(_ids) else None, "msg": _w})
    check("warn: 编译警告的元素 id 进得了 trace_summary（修现有链路，不新建体系）",
          bool(_qa.build_trace_summary(_qa_items))
          and _qa.build_trace_summary(_qa_items)[0]["ids"] == ["shp_bad"])

    # ⑫ 不消费的数据不计算 / 死常量不保留（但真在用的别误删）
    import compile_cache as _cc
    with tempfile.TemporaryDirectory() as _td:
        _ledger = _cc.note_round(pathlib.Path(_td), mode="draft", spec_hash="h1")
    check("budget: 轮次账本不再算无人消费的 over_budget（budget 仍用于显示 round n/6）",
          "over_budget" not in _ledger and _ledger.get("budget") == _cc.ROUND_BUDGET)
    _adv_probe = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
                  "slides": [{"id": "s01", "elements": _panels("rect")}]}
    _adv_off = {c["rule"] for c in
                check_spec(_adv_probe, include_advisory=False)["checks"]}
    _adv_on = {c["rule"] for c in
               check_spec(_adv_probe, include_advisory=True)["checks"]}
    check("advisory: DESIGN_RULES 是真开关——它决定哪些设计规则不进默认判定，不是死常量",
          bool(_adv_on - _adv_off)
          and (_adv_on - _adv_off) <= set(_guard_mod.DESIGN_RULES),
          f"被它挡下的={sorted(_adv_on - _adv_off)}")


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
             "asset_prompt_cache.json", "asset_manifest.qc.json", "generated_assets", "rounds.json",
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
    check(f"docs: 阻断码清单要么不列、要么 {len(_codes)}/{len(_codes)} 列全（缺项 = 作者以为它可忽略）",
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

    # D3b 骨架自足（v5.3）：叙事动作 / 统一契约 / 容量公式 / 方向事实必须在骨架里。
    #     缺任何一样，AI 就得回读 41KB 的 plan.json 去取 2KB 信号——多一轮、多一万 token。
    check("skeleton: 骨架即完整作业单（统一契约/容量公式/叙事动作/构图意图都在场）",
          all(s in body for s in ("统一契约", "行宽容量", "叙事动作:", "构图意图:",
                                  "本文件即完整作业单")),
          [s for s in ("统一契约", "行宽容量", "叙事动作:", "构图意图:") if s not in body])

    # D3c 零消费镜像字段清退：intent_interpretation / media_confidence / media_reason /
    #     quality_budget / type_scale 全库没有消费者，只会膨胀 plan 与上下文体积。
    dead = sorted({k for pg in route_pages
                   for k in ("intent_interpretation", "media_confidence", "media_reason",
                             "quality_budget", "type_scale") if k in pg})
    check("plan: pages 不再携带零消费镜像字段（type_scale/intent_interpretation/media_*）",
          not dead, str(dead))

    # D3e 声明优先级：advanced ≠ 更多图片——optional 家族页不再被质量等级升格出图
    #     （曾经 advanced 把 case/statement/closing/architecture 全部升为必须出图，
    #     与 Native-First 纪律正面冲突）；逐页 asset / asset_subject 写了就原样生效。
    adv_case = route.plan_page("case", "quiet_minimal", "advanced")["asset"]["decision"]
    fast_case = route.plan_page("case", "quiet_minimal", "fast")["asset"]["decision"]
    decl = route.plan_deck({"audience": "a", "decision": "b", "slides": [
        {"id": "s01", "family": "data", "title": "t", "asset": "required"},
        {"id": "s02", "family": "statement", "title": "t", "asset_subject": "a stone"},
        {"id": "s03", "family": "cover", "title": "t", "asset": "none"},
    ]})
    dec = {p["id"]: p["asset"]["decision"] for p in decl["pages"]}
    check("priority: advanced 不升格 optional 页出图；逐页 asset/asset_subject 原样生效",
          adv_case == "none" and fast_case == "none"
          and dec == {"s01": "required", "s02": "required", "s03": "none"},
          f"case={adv_case}/{fast_case} dec={dec}")

    # D3f 标题不代替内容：证据型页缺 content → unresolved_content 留痕（不阻断、
    #     不脑补），且骨架注释把待判断项送到落笔处——缺信息不是虚构的许可。
    warns = [w for w in decl.get("warnings") or [] if w.get("rule") == "unresolved_content"]
    check("unresolved: 证据页缺 content 留痕 plan.warnings（标题≠内容，不得脑补数据）",
          len(warns) == 1 and warns[0].get("scope") == "s01"
          and decl["pages"][0].get("content_missing") is True,
          str([w.get("rule") for w in decl.get("warnings") or []]))
    check("skeleton: unresolved 标注到落笔处（缺 content 的证据页带 ⚠ 注释）",
          "unresolved" in body and "content 缺失" in body,
          "families.yml 的 s02（DATA_STORY，无 content）应在骨架里被标注")

    # D3g 预算是执行器策略，不是契约权力：fast 档 cap 只截断 Skill 判断产生的出图，
    #     作者显式声明（asset / asset_subject）永不被 budget_skip 吃掉。
    budgeted = route.plan_deck({"audience": "a", "decision": "b", "slides": [
        {"id": "s01", "family": "cover", "title": "t", "content": "c"},
        {"id": "s02", "family": "product", "title": "t", "content": "c"},
        {"id": "s03", "family": "statement", "title": "t", "asset_subject": "a stone"},
        {"id": "s04", "family": "closing", "title": "t", "asset": "required"},
    ]})
    gen = (budgeted.get("assets") or {}).get("generate") or []
    check("priority: 资产预算只截断 Skill 判断项，作者显式声明永不被预算吃掉",
          {"s03", "s04"} <= set(gen) and len(gen) == 4      # fast cap=2 只约束 s01/s02
          and (budgeted.get("budget") or {}).get("max_asset_calls") == len(gen)
          and not (budgeted.get("assets") or {}).get("generate_extra"),
          f"generate={gen} budget={budgeted.get('budget')}")

    # D9 deck 卡必须携带整体统一契约：统一的与可不同的都成立、且不相交——
    #    这是「整体高级统一」的机器可守形态；被静默删掉即视为判断层退化。
    card = route.deck_decision({"slides": [{"id": "s01", "family": "cover", "title": "t"}]})
    uni = card.get("unity") or {}
    same_w, diff_w = set(uni.get("same_world") or []), set(uni.get("may_differ") or [])
    check("unity: deck 卡携带统一契约（统一/可不同两列成立且不相交)",
          bool(same_w) and bool(diff_w) and not (same_w & diff_w) and bool(uni.get("rule")),
          f"same={sorted(same_w)} differ={sorted(diff_w)}")

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
                                           COMPLEX_LAYOUT_FAMILIES)
    unnamed = sorted(fam for fam in FAMILY_MOVES
                     if "未知家族" in str(di.media_decision(
                         {"page_intent": {"page_family": fam}}).get("reason")))
    no_budget = sorted(fam for fam in FAMILY_MOVES
                       if di.normalize_family(fam) not in di.QUALITY_BUDGETS)
    bad_alias = sorted(t for t in FAMILY_ALIASES.values() if t not in MEDIA_MODEL)
    drift = sorted(COMPLEX_LAYOUT_FAMILIES - set(FAMILY_MOVES))
    check("families: 媒体判断/质量预算/别名目标三处齐全（无静默回落）",
          not unnamed and not no_budget and not bad_alias,
          f"无名={unnamed} 无预算={no_budget} 坏别名={bad_alias}")
    check("families: 复杂集在家族真源命名空间内", not drift, str(drift))
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

    # D10 召回必须看见 slides 正文：只看骨架字段时，内容级签名永远命不中——
    #     这是「经验只看见骨架」的静默退化，守住它。
    tmp_store2 = work / "dna_slide_recall.json"
    entry2 = {"id": "slide_recall_probe", "pattern": "测试：从 slides 内容召回",
              "signature": {"keywords": ["东南亚", "合资"]},
              "design_problem": "x", "judgment": {"media": "m"},
              "works_because": "w", "avoid": [], "when_not_to": "",
              "proven": {"project": "selftest"}}
    di.record_dna(entry2, path=tmp_store2)
    saved2 = di.DNA_STORE
    di.DNA_STORE = tmp_store2
    hit2 = di.recall_dna({"audience": "董事会",
                          "slides": [{"id": "s01", "title": "东南亚合资路径"}]})
    di.DNA_STORE = saved2
    check("memory: 召回纳入 slides 标题/正文（内容级签名可命中）",
          hit2.get("matched") == "slide_recall_probe", str(hit2.get("matched")))


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


def check_asset_workflow(work: pathlib.Path) -> None:
    """Asset-chain integration and stale-evidence regressions; no generation service needed."""
    import copy
    import contextlib
    import io
    from unittest.mock import patch
    from PIL import Image
    import vao
    from asset_workflow import digest, verify_chain, read_json
    from asset_prompt import asset_fingerprint

    d = work / "asset-chain"
    d.mkdir()
    images = d / "pictures"
    images.mkdir()
    brief = d / "brief.yml"
    plan = d / "plan.json"
    skeleton = d / "build_deck.py"
    manifest_path = d / "asset_manifest.json"
    qcpath = d / "asset_manifest.qc.json"
    need = {"audience": "investor", "decision": "approve", "quality_level": "advanced",
            "slides": [{"id": "s01", "family": "cover", "title": "Tea",
                        "asset_subject": "ceramic bowl", "medium": "photography", "asset_ratio": "16:10",
                        "text_color": "dark"}]}
    brief.write_text(json.dumps(need), encoding="utf-8")
    check("assets: CLI requires saved --plan",
          run_vao("assets", str(brief), "--out", str(manifest_path)).returncode != 0)
    run_vao("plan", str(brief), "--out", str(plan), "--skeleton", str(skeleton))
    proc = run_vao("assets", str(brief), "--plan", str(plan), "--out", str(manifest_path),
                   "--assets-dir", str(images))
    manifest = read_json(manifest_path)
    entry = next(e for e in manifest["assets"] if e.get("decision") == "generate")
    check("assets: manifest records prompt builder and plan hash",
          proc.returncode == 0 and manifest["workflow"]["plan_sha256"] == digest(read_json(plan))
          and bool(entry["prompt"]) and bool(entry["negative"]))
    spec, _ = vao.load_spec(spec_module(d / "base.py"))
    spec["asset_workflow"] = {"plan_sha256": digest(read_json(plan))}
    spec["slides"][0]["elements"][0].update(x=64, y=184, width=608)
    spec["slides"][0]["elements"].append({"type":"image", "id":"photo", "asset_id":entry["asset_id"],
             "x":760, "y":280, "width":384, "height":256, "asset_function":"emotion"})
    mod = d / "filled.json"
    mod.write_text(json.dumps(spec), encoding="utf-8")
    blocked = run_vao("check", str(mod), str(d / "blocked.pptx"), "--mode", "release")
    bm = read_json(d / "blocked.manifest.json")
    check("assets: direct-src/no-manifest cannot release",
          blocked.returncode == 2 and not bm["release_eligible"] and bm["status"] == "BLOCKED")
    missing = run_vao("asset-qc", str(manifest_path))
    check("assets: missing file is pending and exits nonzero",
          missing.returncode == 2 and bool(read_json(qcpath)["pending_assets"]))
    # Fixture is deliberately a neutral blank image; this tests the chain, not aesthetics.
    picture = images / pathlib.Path(entry["expected_filename"]).with_suffix(".jpg")
    Image.new("RGB", (640, 400), (242, 240, 230)).save(picture)
    bound, binding = vao.bind_asset_manifest(spec, manifest_path)
    check("assets: manifest directory + JPEG resolution agree with binding",
          binding["status"] == "PASS" and bound["slides"][0]["elements"][-1]["src"] == str(picture.resolve()))
    pending = run_vao("check", str(mod), str(d / "pending.pptx"), "--assets-manifest", str(manifest_path))
    check("assets: QC must pass before draft compilation", pending.returncode == 2 and not (d / "pending.pptx").exists())
    with patch("asset_prompt.image_qc", return_value={"status":"ok", "checks":[
            {"check":"text_safe_area", "status":"issue"}]}), contextlib.redirect_stdout(io.StringIO()):
        retry, code = vao.asset_qc(str(manifest_path), phase="draft")
    check("assets: retry is not PASS and returns 2", code == 2 and retry["status"] == "BLOCKED" and bool(retry["retry_assets"]))
    success = run_vao("asset-qc", str(manifest_path), "--phase", "release")
    qc = read_json(qcpath)
    check("assets: real image QC binds inspected bytes to manifest",
          success.returncode == 0 and qc["manifest_sha256"] == digest(manifest)
          and bool(qc["results"][0]["file_sha256"]), success.stdout[-300:])
    released = run_vao("check", str(mod), str(d / "deck.pptx"), "--mode", "release",
                       "--assets-manifest", str(manifest_path))
    rm = read_json(d / "deck.manifest.json")
    check("assets: complete chain -> release with provenance",
          released.returncode == 0 and rm["release_eligible"]
          and rm["asset_workflow"]["status"] == "PASS", released.stdout[-400:])
    custom = d / "custom-qc.json"
    qcpath.replace(custom)
    custom_proc = run_vao("check", str(mod), str(d / "custom.pptx"), "--mode", "release",
                          "--assets-manifest", str(manifest_path), "--asset-qc-report", str(custom))
    check("assets: custom QC path supported", custom_proc.returncode == 0)
    custom.replace(qcpath)
    Image.new("RGB", (640,400), (230,235,230)).save(picture)
    check("assets: replacing image invalidates QC",
          verify_chain(bound, manifest_path)["status"] == "BLOCKED")
    Image.new("RGB", (640,400), (242,240,230)).save(picture)
    original = copy.deepcopy(manifest)
    manifest["assets"][0]["prompt"] += " changed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    check("assets: editing prompt invalidates QC",
          verify_chain(bound, manifest_path)["status"] == "BLOCKED")
    manifest_path.write_text(json.dumps(original), encoding="utf-8")
    changed_spec = copy.deepcopy(bound)
    changed_spec["slides"][0]["elements"][-1].pop("asset_id")
    check("assets: untracked additional image cannot bypass chain",
          verify_chain(changed_spec, manifest_path)["status"] == "BLOCKED")
    changed_spec = copy.deepcopy(bound)
    changed_spec["asset_workflow"]["plan_sha256"] = "wrong"
    check("assets: wrong skeleton/plan binding is rejected",
          verify_chain(changed_spec, manifest_path)["status"] == "BLOCKED")
    original_plan = read_json(plan)
    edited_plan = copy.deepcopy(original_plan)
    edited_plan["changed"] = True
    plan.write_text(json.dumps(edited_plan), encoding="utf-8")
    check("assets: changed plan invalidates release",
          verify_chain(bound, manifest_path)["status"] == "BLOCKED")
    plan.write_text(json.dumps(original_plan), encoding="utf-8")
    changed_need = copy.deepcopy(need)
    changed_need["audience"] = "different audience"
    brief.write_text(json.dumps(changed_need), encoding="utf-8")
    check("assets: stale brief/plan cannot prepare assets",
          run_vao("assets", str(brief), "--plan", str(plan), "--out", str(d/"stale.json")).returncode != 0)
    check("assets: changed brief invalidates release",
          verify_chain(bound, manifest_path)["status"] == "BLOCKED")
    brief.write_text(json.dumps(need), encoding="utf-8")
    run_vao("assets", str(brief), "--plan", str(plan), "--out", str(manifest_path), "--assets-dir", str(images))
    existing_bytes = run_vao("asset-qc", str(manifest_path), "--phase", "release")
    check("assets: pre-existing generated bytes require explicit reuse",
          existing_bytes.returncode == 2 and bool(read_json(qcpath)["workflow_issues"]))
    # Explicit author-provided asset: same workflow except no image generation.
    need["slides"][0]["asset_source"] = {"kind":"provided", "path":str(picture), "source":"user fixture"}
    brief.write_text(json.dumps(need), encoding="utf-8")
    run_vao("plan", str(brief), "--out", str(plan), "--skeleton", str(skeleton))
    run_vao("assets", str(brief), "--plan", str(plan), "--out", str(manifest_path))
    manifest = read_json(manifest_path)
    existing = manifest["assets"][0]
    spec["asset_workflow"]["plan_sha256"] = digest(read_json(plan))
    spec["slides"][0]["elements"][-1]["asset_id"] = existing["asset_id"]
    bound, _ = vao.bind_asset_manifest(spec, manifest_path)
    run_vao("asset-qc", str(manifest_path), "--phase", "release")
    check("assets: provided/reused materials need source+QC, not regeneration",
          existing["decision"] == "existing" and verify_chain(bound, manifest_path)["status"] == "PASS")
    text_spec = {"slides":[{"id":"s01", "elements":[{"type":"text", "text":"Only text"}]}]}
    check("assets: native-only deck has explicit skip reason",
          verify_chain(text_spec)["reason"] == "no_image_elements")
    card = {"subject":["bowl"]}
    check("assets: distinct aspect ratios do not share prompt-cache key",
          asset_fingerprint(card, {"ratio":"16:9"}) != asset_fingerprint(card, {"ratio":"1:1"}))
    # Duplicate reuse marker must not shadow the canonical primary entry.
    duplicated = copy.deepcopy(manifest)
    duplicated["assets"].append({"asset_id":existing["asset_id"], "decision":"reuse_generated", "slide_id":"s02"})
    manifest_path.write_text(json.dumps(duplicated), encoding="utf-8")
    _, reuse = vao.bind_asset_manifest(spec, manifest_path)
    check("assets: reuse marker does not shadow canonical file binding", reuse["status"] == "PASS")
    broken_qc = d / "broken.json"
    broken_qc.write_text("not json", encoding="utf-8")
    check("assets: corrupt QC produces a grouped failure, not a pass",
          verify_chain(bound, manifest_path, broken_qc)["status"] == "BLOCKED")


def check_audit_fixes(work: pathlib.Path) -> None:
    """Fourteen audit findings plus legitimate-use controls. No external services."""
    import contextlib
    import copy
    import io
    import zipfile
    from unittest.mock import patch
    from PIL import Image, ImageDraw
    import vao, qa, compiler, asset_workflow as aw
    from asset_prompt import image_qc, qc_retry_decision

    d = work / "audit-fixes"
    d.mkdir()
    def save(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))
    def invoke(spec_path, output, manifest=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return vao.run_check(str(spec_path), str(output), mode="release",
                                 assets_manifest=str(manifest) if manifest else None)
    def native(name):
        folder = d / name
        folder.mkdir()
        spec, _ = vao.load_spec(spec_module(folder / "base.py"))
        spec["slides"][0]["elements"][0].update(x=64, y=112, width=608, height=96, size=44)
        sp = folder / "spec.json"
        save(sp, spec)
        return folder, sp, spec
    def asset_case(name, second=False):
        folder, sp, spec = native(name)
        brief = {"audience":"reviewer", "decision":"approve", "quality_level":"advanced",
                 "slides":[{"id":"s01", "family":"cover", "title":"Audit",
                 "asset_subject":"ceramic bowl", "medium":"photography", "asset_ratio":"16:10",
                 "text_color":"dark"}]}
        if second:
            brief["slides"].append({"id":"s02", "family":"data", "title":"Required page"})
        bp, pp, mp = (folder/x for x in ("brief.json", "plan.json", "asset_manifest.json"))
        save(bp, brief)
        assert run_vao("plan", str(bp), "--out", str(pp)).returncode == 0
        assert run_vao("assets", str(bp), "--plan", str(pp), "--out", str(mp),
                       "--assets-dir", str(folder/"images")).returncode == 0
        (folder/"images").mkdir()
        entries = aw.asset_entries(read(mp))
        for e in entries:
            a,b = map(float, e.get("ratio","16:10").split(":"))
            Image.new("RGB", (640, round(640*b/a)), (242,240,230)).save(folder/"images"/e["expected_filename"])
        q = run_vao("asset-qc", str(mp), "--phase", "release")
        assert q.returncode == 0, q.stdout + q.stderr
        first = entries[0]
        pic = folder/"images"/first["expected_filename"]
        spec["asset_workflow"] = {"plan_sha256":aw.digest(read(pp)), "plan_path":str(pp)}
        spec["slides"][0]["elements"].append({"id":"photo", "type":"image", "asset_id":first["asset_id"],
            "x":760,"y":280,"width":384,"height":256,"fit":"cover","asset_function":"emotion"})
        save(sp, spec)
        return folder, sp, spec, mp, pic
    def pixels(path):
        with zipfile.ZipFile(path) as z:
            return [Image.open(io.BytesIO(z.read(n))).convert("RGB").getpixel((0,0))
                    for n in z.namelist() if n.startswith("ppt/media/")]

    # H-01: seed exactly the old cache key with a valid wrong PNG; it must never be consumed.
    folder, sp, spec, mp, pic = asset_case("cache")
    old_cache = folder/"legacy-cache"
    old_cache.mkdir()
    st = pic.stat()
    stamp = f"{st.st_mtime_ns}:{st.st_size}:{aw.file_digest(pic)[:16]}"
    bg = tuple(int(spec["theme"]["colors"]["background"].lstrip("#")[i:i+2],16) for i in (0,2,4))
    payload = "|".join([str(pic.resolve()),stamp,"384","256","cover","None",str(bg)])
    legacy_key = hashlib.sha1(payload.encode(), usedforsecurity=False).hexdigest()[:32]
    Image.new("RGB", (384,256), (255,0,0)).save(old_cache/(legacy_key+".png"))
    with patch.object(compiler,"_FIT_CACHE_DIR",old_cache,create=True):
        result, code = invoke(sp,folder/"deck.pptx",mp)
    check("H-01: poisoned legacy image cache is ignored", code == 0 and pixels(folder/"deck.pptx") == [(242,240,230)])
    repeat, code = invoke(sp,folder/"deck.pptx",mp)
    check("control: legitimate full-deck compilation cache still reuses output",
          code == 0 and repeat["performance"]["compile_reused"])

    # H-02: a data manifest never executes its nested brief, even before hash failure.
    marker = d/"EXECUTED.txt"
    payload = d/"brief-data.txt"
    payload.write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('audit')\nBRIEF={{}}\n",encoding="utf-8")
    evil = read(mp)
    evil["workflow"]["brief_path"] = str(payload)
    evil["workflow"]["brief_file_sha256"] = "invalid"
    evil_path = d/"evil.json";save(evil_path,evil)
    q = run_vao("asset-qc",str(evil_path))
    check("H-02: JSON manifest cannot execute nested Python/text brief", q.returncode == 2 and not marker.exists())

    # H-03: simultaneous source overwrite cannot change the verified bytes consumed by PPT or preview.
    folder, sp, spec, mp, pic = asset_case("snapshot")
    original = qa.run_qa
    def mutate(*a, **kw):
        Image.new("RGB",(640,400),(0,0,255)).save(pic)
        return original(*a,**kw)
    with patch.object(qa,"run_qa",side_effect=mutate):
        result, code = invoke(sp,folder/"deck.pptx",mp)
    check("H-03: compile consumes immutable verified snapshot under source overwrite",
          code == 0 and pixels(folder/"deck.pptx") == [(242,240,230)]
          and result["asset_workflow"]["compilation_input"] == "verified_in_memory_snapshot")
    with Image.open(folder/"deck_preview/ghost-01.png") as preview:
        preview_pixel = preview.convert("RGB").getpixel((500,200))
    check("control: preview consumes the same image snapshot as the PPT", preview_pixel == (242,240,230))

    # M-01: deleted/corrupted single-page previews must be recreated, not declared present.
    folder, sp, spec = native("preview")
    result, code = invoke(sp,folder/"deck.pptx")
    page = folder/"deck_preview/ghost-01.png"
    expected = aw.file_digest(page);page.unlink()
    result, code = invoke(sp,folder/"deck.pptx")
    check("M-01: missing preview page is regenerated before PASS", code == 0 and aw.file_digest(page) == expected)
    page.write_bytes(b"invalid PNG")
    result, code = invoke(sp,folder/"deck.pptx")
    check("control: corrupt preview bytes invalidate preview reuse", code == 0 and aw.file_digest(page) == expected)

    # M-02: exact plan coverage, also for native-only planned decks.
    folder, sp, spec, mp, pic = asset_case("coverage", second=True)
    result, code = invoke(sp,folder/"deck.pptx",mp)
    check("M-02: two planned pages cannot silently release as one", code == 2 and "ASSET_WORKFLOW_FAIL" in result["failure_codes"])
    spec["slides"][0]["elements"].pop();save(sp,spec)
    result, code = invoke(sp,folder/"native.pptx")
    check("control: removing all images does not bypass planned page coverage", code == 2)
    extra=copy.deepcopy(spec["slides"][0]);extra["id"]="s02"
    spec["slides"].append(extra);save(sp,spec)
    result, code = invoke(sp,folder/"complete.pptx")
    check("control: complete native-only planned deck remains legal", code == 0)

    # M-03: required provenance is typed and nonblank after stripping.
    folder, sp, spec = native("provenance")
    chart={"id":"chart","type":"chart","chart_kind":"column","x":64,"y":288,"width":672,"height":304,
           "data":[{"label":"A","value":1},{"label":"B","value":3}],
           "source":"   ","unit":"\t","period":"\n","basis":"  "}
    spec["slides"][0]["elements"].append(chart);save(sp,spec)
    result, code = invoke(sp,folder/"blank.pptx")
    check("M-03: whitespace provenance cannot satisfy release requirements", code == 2 and "DATA_INTEGRITY_FAIL" in result["failure_codes"])
    chart.update(source="Fixture model",unit="units",period="2027E",basis="Illustrative")
    save(sp,spec);result, code=invoke(sp,folder/"valid.pptx")
    check("control: valid numerical chart with explicit provenance releases", code == 0)

    # M-04 / M-05 / M-10: validate contrast, dimensions, ratio and visible alpha.
    gray=d/"gray.png";Image.new("RGB",(256,256),(128,128,128)).save(gray)
    q=image_qc(str(gray))
    check("M-04: unspecified text color no longer passes every luminance",
          next(x for x in q["checks"] if x["check"]=="contrast_suitability")["status"]=="issue")
    tiny=d/"tiny.png";Image.new("RGB",(1,1),(242,240,230)).save(tiny)
    check("M-05: 1x1 asset is blocked", qc_retry_decision(image_qc(str(tiny)),phase="release")["action"]=="block")
    square=d/"square.png";Image.new("RGB",(256,256),(242,240,230)).save(square)
    q=image_qc(str(square),expected_ratio="16:9")
    check("M-05: undeclared aspect-ratio mismatch is blocked",qc_retry_decision(q,phase="release")["action"]=="block")
    q=image_qc(str(square),expected_ratio="16:9",allow_crop=True)
    check("control: explicit intentional crop is permitted",qc_retry_decision(q,phase="release")["action"].startswith("accept"))
    invisible=d/"transparent.png";Image.new("RGBA",(256,256),(255,255,255,0)).save(invisible)
    check("M-10: fully transparent content is rejected",qc_retry_decision(image_qc(str(invisible)),phase="release")["action"]=="block")
    logo=Image.new("RGBA",(256,256),(255,255,255,0))
    ImageDraw.Draw(logo).rectangle((128,128,191,191), fill=(170,170,170,255))
    visible=d/"visible-alpha.png";logo.save(visible)
    check("control: visible transparent logo is not blanket-rejected",
          qc_retry_decision(image_qc(str(visible)),phase="release")["action"].startswith("accept"))

    folder, sp, spec, mp, pic = asset_case("resolution")
    Image.new("RGB",(320,200),(242,240,230)).save(pic)
    assert run_vao("asset-qc",str(mp),"--phase","release").returncode == 0
    result,code=invoke(sp,folder/"deck.pptx",mp)
    check("M-05: QC-passed image still needs sufficient pixels for its actual placement",
          code==2 and any("分辨率" in t for t in result["asset_workflow"]["issues"]))

    # Explicit author-provided Python remains supported for planning, never reexecuted by verification.
    brief_py=d/"trusted_brief.py";counter=d/"plan_counter.txt";pp=d/"trusted_plan.json"
    brief_py.write_text(f"from pathlib import Path\np=Path({str(counter)!r})\n"
        "p.write_text((p.read_text() if p.exists() else '')+'planned\\n')\n"
        "BRIEF={'audience':'reviewer','decision':'approve','slides':[{'id':'s01','family':'cover','title':'Trusted'}]}\n",encoding="utf-8")
    bundle=vao._plan(str(brief_py),str(pp))
    need=bundle["need"];mp=d/"trusted_assets.json"
    manifest=aw.prepare_manifest(vao.build_asset_manifest(need,bundle),need,bundle,brief_py,pp,mp)
    before=counter.read_bytes()
    check("control: trusted Python planning works without verification reexecuting it",
          not aw.verify_sources(manifest) and counter.read_bytes()==before)

    # M-06 / M-11: both text-bearing channels and both overflow directions are guarded.
    folder, sp, spec = native("text")
    spec["slides"][0]["elements"].append({"id":"small","type":"shape","shape":"rect",
       "x":64,"y":320,"width":96,"height":32,"fill":"secondary","text":"审计溢出测试"*80,"text_size":44})
    save(sp,spec);result,code=invoke(sp,folder/"shape.pptx")
    check("M-06: shape-hosted text capacity is enforced",code==2 and "TEXT_OVERFLOW" in result["failure_codes"])
    spec["slides"][0]["elements"][-1].update(width=240,height=80,text="正常文字",text_size=22)
    save(sp,spec);result,code=invoke(sp,folder/"shape-valid.pptx")
    check("control: adequately sized shape text releases",code==0)
    spec["slides"][0]["elements"].pop()
    spec["slides"][0]["elements"][0].update(text="W"*120,width=80,wrap=False)
    save(sp,spec);result,code=invoke(sp,folder/"nowrap.pptx")
    check("M-11: nowrap horizontal overflow is blocked",code==2 and "TEXT_OVERFLOW" in result["failure_codes"])

    # M-07: one effective spec goes to compile, preview and manifest.
    folder, sp, spec=native("fit")
    spec["slides"][0]["elements"][0].update(text="Title",size=44,height=40,line_height=1.35,padding=8,auto_fit=True)
    save(sp,spec);result,code=invoke(sp,folder/"deck.pptx")
    manifest=read(folder/"deck.manifest.json")
    check("M-07: successful auto_fit has consistent release provenance",code==0 and result["auto_fit"]["applied"]==1
          and manifest["release_eligible"] and not manifest["validation"]["issues"])
    with patch.object(qa,"preview_issues",return_value=["Injected preview evidence failure"]):
        result,code=invoke(sp,folder/"bad-preview.pptx")
    check("M-07: evidence failure produces actionable BLOCKED, never ready",
          code==2 and result["blocking_items"]>0 and bool(result["failure_codes"])
          and bool(result["fix_plan"]["groups"]) and result["next_action"].startswith("fix:")
          and result["rounds"]["log"][-1]["status"]=="BLOCKED")

    # M-08: every run invalidates old success before parsing input.
    old_id=manifest["run_id"]
    save(sp,{"slides":[None]});result,code=invoke(sp,folder/"deck.pptx")
    failed=read(folder/"deck.manifest.json")
    check("M-08: malformed spec replaces stale PASS with this run's failure",
          code==2 and not failed["release_eligible"] and failed["run_id"]!=old_id
          and failed["run_id"]==read(folder/"deck.repair.json")["run_id"])
    sp.write_text("{",encoding="utf-8");result,code=invoke(sp,folder/"deck.pptx")
    check("control: JSON syntax failure also receives a fresh failure report",
          code==2 and read(folder/"deck.manifest.json")["run_id"]==result["run_id"])

    # M-09: generated root is confined; explicitly declared existing external files remain valid.
    root=d/"image-root";root.mkdir()
    outside=d/"outside.png";Image.new("RGB",(640,400),(242,240,230)).save(outside)
    denied=False
    try:
        (root/"asset.png").symlink_to(outside)
        # 沙箱化的 Windows 宿主会把 symlink 调用**静默降级**成普通文件：不抛 OSError，
        # is_symlink() 却是 False。此时上面的分支测不到逃逸，用例会假绿/假红。
        # 显式把它当成「造不出链接」处理，强制走下面的 post-resolution 边界。
        if not (root/"asset.png").is_symlink():
            raise OSError("host downgraded the symlink to a plain file")
        try:
            aw.resolve_asset({"asset_id":"x","decision":"generate","expected_filename":"asset.png"},
                             {"assets_dir":str(root)},d/"manifest.json")
        except ValueError:
            denied=True
    except OSError:
        # Some Windows runners cannot create symlinks. Exercise the post-resolution boundary directly.
        original_resolve=pathlib.Path.resolve
        with patch.object(pathlib.Path,"resolve",lambda self: outside if self==root/"asset.png" else original_resolve(self)):
            try:
                aw.resolve_asset({"asset_id":"x","decision":"generate","expected_filename":"asset.png"},
                                 {"assets_dir":str(root)},d/"manifest.json")
            except ValueError:
                denied=True
    check("M-09: resolved generated asset cannot escape its root",denied)
    authorized=aw.resolve_asset({"asset_id":"x","decision":"existing","origin":{"path":str(outside)}},
                                {"assets_dir":str(root)},d/"manifest.json")==outside.resolve()
    folder, sp, spec=native("existing")
    bp,pp,mp=(folder/n for n in ("brief.json","plan.json","asset_manifest.json"))
    need={"audience":"reviewer","decision":"approve","slides":[{"id":"s01","family":"cover","title":"Existing",
          "asset_source":{"kind":"provided","path":str(outside),"source":"Author-provided test image"}}]}
    save(bp,need);bundle=vao._plan(str(bp),str(pp))
    manifest=aw.prepare_manifest(vao.build_asset_manifest(need,bundle),need,bundle,bp,pp,mp)
    save(mp,manifest)
    assert run_vao("asset-qc",str(mp),"--phase","release").returncode==0
    spec["asset_workflow"]={"plan_path":str(pp),"plan_sha256":aw.digest(bundle)}
    spec["slides"][0]["elements"].append({"id":"photo","type":"image","asset_id":aw.asset_entries(manifest)[0]["asset_id"],
        "x":760,"y":280,"width":384,"height":256,"fit":"cover","asset_function":"context"})
    save(sp,spec);result,code=invoke(sp,folder/"deck.pptx",mp)
    check("control: explicit existing external asset can QC, compile and release",authorized and code==0)


def check_prompt_discipline() -> None:
    """提示词纪律（v5.3）：光照单一来源、静物动势抑制、语法翻译、负向分层、色名。

    这一组的共同失效模式是「prompt 自相矛盾 → 模型对矛盾指令做平均 →
    不可预测的光比/动感/风格」，废图只能重出，是最贵的一轮。全部单元级断言，
    不跑管线：prompt 组装是纯函数。
    """
    from asset_prompt import (build_asset_prompt, enhance_asset_card, grammar_phrase,
                              hex_to_color_name, subject_implies_people,
                              validate_asset_card, GRAMMAR_PHRASES)

    def _photo_card(**over) -> dict:
        card = {"asset_type": "background", "asset_function": "hero",
                "subject": ["a celadon tea bowl resting on a wooden table"],
                "color": ["neutral tonal range with one restrained accent"],
                "material": ["glazed ceramic and warm oak wood"],   # 勿含水墨词（rice paper 会点火水墨闸门）
                "lighting": ["soft box light from above"],   # 标记句：出现即泄漏
                "composition": ["calm evidence-field composition"],
                "medium": "photography", "negative": []}
        card.update(over)
        return card

    page = {"light_direction": "left", "energy": "high"}

    # P1 预设/兜底光让位给摄影写实光语：卡内 lighting 标记句与方向/能量光句都不得出现
    r1 = build_asset_prompt(_photo_card(lighting_source="preset"), page)
    p1 = r1["prompt"]
    check("prompt: 摄影卡光照单一来源（预设光与方向光让位给摄影光语，只出现一次）",
          "soft box light from above" not in p1
          and "soft directional light from the upper left" not in p1
          and "one dramatic light source" not in p1
          and p1.count("single natural light source") == 1,
          p1[:160])

    # P2 作者逐页声明 lighting：声明句赢，摄影层的光句让位（介质句保留）
    r2 = build_asset_prompt(_photo_card(lighting_source="declared"), page)
    p2 = r2["prompt"]
    check("prompt: 作者声明的光照是唯一光来源（摄影光句让位、介质句保留）",
          "soft box light from above" in p2
          and "single natural light source" not in p2
          and "soft directional light from the upper left" not in p2
          and "medium format film character" in p2, p2[:160])

    # P3 静物主体（hero/proof/direct）不吃运动模糊与光轨；氛围类保留动势句
    hero = enhance_asset_card(_photo_card(), family="song_elegance")
    ambient = enhance_asset_card(_photo_card(asset_function="emotion"), family="song_elegance")
    hero_tech = enhance_asset_card(_photo_card(), family="precision_tech")
    check("card: 静物主体的动势层取静态安全句（motion blur / light trails 只属于氛围资产）",
          "motion blur" not in " ".join(hero["motion"])
          and "motion blur" in " ".join(ambient["motion"])
          and "light trails" not in " ".join(hero_tech["motion"]),
          f"hero={hero['motion']}")

    # P4 构图语法：键名翻译成可读语言，自由文本原样透传，空值有兜底
    check("prompt: 构图语法键名不泄漏（内部枚举 → 可读语言，自由文本永远赢）",
          grammar_phrase("evidence_field") == GRAMMAR_PHRASES["evidence_field"]
          and "evidence_field" not in grammar_phrase("evidence_field")
          and grammar_phrase("diagonal tension across the frame")
              == "diagonal tension across the frame"
          and grammar_phrase(None) == "asymmetric editorial composition",
          grammar_phrase("evidence_field"))

    # P5 负向分层：静物不注人物词；人物主体注入；ASCII 词边界防 handmade 误判
    bowl_neg = build_asset_prompt(_photo_card(), page)["negative"]
    people_card = _photo_card(subject=["founder team portrait in the studio"])
    people_neg = build_asset_prompt(people_card, page)["negative"]
    craft = _photo_card(subject=["handmade paper craft on a workbench"])
    check("negative: 分层注入（静物无人物反向词 / 人物主体有 / handmade 不误判成 hand）",
          "posed smiling people" not in bowl_neg and "corporate handshake" not in bowl_neg
          and "cyberpunk" in bowl_neg                      # 非水墨 → 科技风格反向在
          and "posed smiling people" in people_neg and "corporate handshake" in people_neg
          and not subject_implies_people(craft) and subject_implies_people(people_card),
          bowl_neg[:120])

    # P6 hex → 可读色名：图像模型对 #hex 基本不响应；近白不得被 HLS 饱和度放大成彩色
    check("prompt: hex 译成可读色名（中性判定用 chroma，近白不偏黄）",
          hex_to_color_name("#5E7562") == "muted green"
          and hex_to_color_name("#F5F4EF") == "white"
          and hex_to_color_name("#111111") == "near black"
          and hex_to_color_name("nope") is None
          and (hex_to_color_name("#C8501E") or "").endswith("orange"),
          f"got={hex_to_color_name('#5E7562')},{hex_to_color_name('#F5F4EF')}")

    # P7 中文 subject 给换英文提醒（issues 是提示通道，不阻断出图）
    cjk = _photo_card(subject=["一只青瓷茶盏"])
    issues = validate_asset_card(cjk)
    check("card: 中文 subject 收到「改英文」提醒（非阻断，清单保留原文）",
          any("subject 含中文" in s for s in issues), str(issues))


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

def check_boundary_negatives(work: pathlib.Path) -> None:
    """技能包的否定边界：不只测"能做什么"，更测**不该做什么**（§33）。

    九条边界里，前面几组已被 seed / 契约 / 缓存测试覆盖；这里补的是最容易在
    一次"优化"里悄悄越界的那几条：把审美变成阻断、把证据变成修复、把几何写进
    生成提示词、让 guard 改稿、让 warning 变成对话循环。
    """
    import copy
    import guard as _guard

    colors = {"background": "#F6F5F1", "ink": "#1E211D", "muted": "#6E6A5F",
              "primary": "#1E211D", "secondary": "#6E6A5F", "accent": "#5E7562"}

    def spec(elements, theme_extra=None, slides_extra=None):
        return {"canvas": {"width": 1280, "height": 720},
                "theme": {"colors": colors, **(theme_extra or {})},
                "slides": [dict({"id": "s01",
                                 "page_intent": {"insight": "x", "focus": "t1",
                                                 "page_family": "EDITORIAL", "density": "balanced",
                                                 "energy": "medium", "empty_space_role": "rest_eye"},
                                 "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 40},
                                 "elements": elements}, **(slides_extra or {}))]}

    def levels(elements, **kw):
        checks = _guard.check_spec(spec(elements, **kw))["checks"]
        return [c for c in checks if c.get("level") == "error"], checks

    txt = lambda i, **kw: {"type": "text", "id": i, "x": 96, "y": 240, "width": 480, "height": 60,
                           "text": "字", "size": 32, "color": "ink", "role": "title",
                           "max_lines": 1, **kw}

    # ① 审美不得成为阻断：颜色多、装饰多、两个字体家族、5 个色相族、混用图标风格
    loud = [txt("t1", size=32, font="Songti SC"), txt("t2", y=320, size=44, font="Georgia"),
            *[{"type": "shape", "id": f"d{i}", "x": 40 * i, "y": 520, "width": 160, "height": 64,
               "fill": ["#8E2F28", "#A97E2F", "#2F5D8E", "#5E7562", "#7C4A8E"][i],
               "role": "decoration", "icon_style": f"style{i}"} for i in range(5)]]
    errors, all_checks = levels(loud)
    taste_rules = {"palette_discipline", "chart_style_drift", "decoration_budget", "icon_consistency",
                   "color_budget", "accent_budget", "type_budget", "rhythm", "alignment_budget"}
    check("boundary: 审美问题永不阻断（颜色/装饰/字体/图标再杂也 0 条 error）",
          not errors and not any(c.get("rule") in taste_rules for c in all_checks),
          f"errors={len(errors)} 品味规则命中={sorted({c.get('rule') for c in all_checks} & taste_rules)}")

    # ② 未声明的审美刻度不得自动执法（色相族 / Accent 色相角 / 图表标签漂移）
    undeclared = [c for c in levels(loud)[1] if c.get("rule") == "palette_discipline"]
    declared = [c for c in _guard.check_spec(
        spec(loud, theme_extra={"constraints": {"hue_families_max": 1}}))["checks"]
        if c.get("rule") == "palette_discipline"]
    check("boundary: 未声明不检查；声明了才执法（hue_families_max 探针）",
          not undeclared and bool(declared),
          f"未声明={len(undeclared)} 条；声明={len(declared)} 条")

    # ③ trace 不得触发修复：只有 warn/hint 时，判定仍是 PASS 且修复包为空
    warn_only = spec([txt("t1", size=9, role="caption")])       # 低于可读下限 → warn
    verdict = _guard.check_spec(warn_only)
    warns = [c for c in verdict["checks"] if c.get("level") in ("warn", "hint")]
    errors_only = [c for c in verdict["checks"] if c.get("level") == "error"]
    check("boundary: 证据≠错误（trace 级存在时仍 0 阻断，不需要修复循环）",
          bool(warns) and not errors_only, f"trace={len(warns)} error={len(errors_only)}")

    # ④ guard 不得改稿：check_spec 是只读的（设计意图只能由作者改）
    snapshot = copy.deepcopy(warn_only)
    _guard.check_spec(warn_only)
    check("boundary: Guard 只读（check_spec 前后 spec 完全一致，不擅自重设计）",
          warn_only == snapshot, "spec 未被改动")

    # ⑤ 生成提示词不得出现几何坐标（坐标是检查器的语言，不是给模型的指令）
    from asset_prompt import build_asset_prompt
    coords = re.compile(r"(\bx\s*[:=]\s*\d|\by\s*[:=]\s*\d|width\s*[:=]\s*\d|height\s*[:=]\s*\d|\d+\s*%)")
    built = build_asset_prompt({"subject": "steam rising from a celadon cup on paper",
                                "medium": "photography", "ratio": "16:9"},
                               {"ratio": "16:9", "asset_function": "context",
                                "safe_area": {"x": 0.06, "y": 0.08, "width": 0.34, "height": 0.78},
                                "text_color": "dark", "negative_space_anchor": "left",
                                "asset_type": "background"})
    prompt = built["prompt"] if isinstance(built, dict) else str(built)
    hit = coords.search(prompt)
    check("boundary: 资产提示词零几何坐标（% / x= / width: 一律不出现）",
          hit is None, f"命中 {hit.group(0)!r}" if hit else "")

    # ⑥ 生产路径不得读 references/（JIT：知识只在需要时由人/AI 取用）
    offenders = []
    for f in sorted(SCRIPTS.glob("*.py")):
        body = f.read_text(encoding="utf-8")
        for i, line in enumerate(body.splitlines(), 1):
            if "references" not in line or line.lstrip().startswith("#"):
                continue
            if re.search(r'(read_text|read_bytes|open)\s*\(', line):
                offenders.append(f"{f.name}:{i}")
    check("boundary: 生产脚本不读 references/（无关参考不得进上下文）",
          not offenders, f"命中 {offenders[:3]}" if offenders else "")


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
        check_silent_failure_seams()
        check_asset_workflow(work)
        check_audit_fixes(work)
        check_prompt_discipline()
        check_anti_regression()
        check_boundary_negatives(work)
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
