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
import inspect as _inspect
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
                           "energy": "high"}},
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
    """可读性缝（2026-09 审核后）：只剩两条硬事实，软档一律不执法。

    ① **读不出来的字**（<1.8:1）点名 warn——这不是品味，是「等于没有字」；
    ② 面/影不该被当字判（深底主题的 secondary 是深面），只有真拿去写字才点名。
    曾经还有一条 <3:1 的 hint（含 chart_muted 指到的 token）：已撤——
    「刻度色够不够深」是设计判断（muted 做装饰/刻度是正当选择），
    阈值写在 references 的取舍链里，引擎不再对作者的选择发第二意见。
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
                                            "density": "sparse", "energy": "high"},
                            "elements": [{"type": "text", "id": "t1", "x": 96, "y": 240,
                                          "width": 600, "height": 80, "text": "结论", "size": 44,
                                          "color": text_color, "role": "title", "max_lines": 1}]}]}
        res = _guard.check_spec(spec)
        return ([c for c in res["checks"] if c["rule"] == "contrast"], res["passed"])

    # ① 软档不再发声（2.57:1）：不点名、也不阻断——「muted 做刻度还是做装饰」归设计判断
    silent_zone, ok_zone = probe(light)
    check("readability: 2.5–3.0 的灰不再由引擎点名（软档撤销；仍不阻断 release）",
          not silent_zone and ok_zone is True,
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

    # ④ chart_muted 指向谁，谁就被当字判（刻度就是它画的）：指到读不出来的灰要点名。
    # 这里把 secondary 做成 1.4:1、且没有任何元素拿它写字——只有 chart_muted 指到它，
    # 它才该被点名。
    cm, _ = probe(dict(light, muted="#5A5A5A", secondary="#D2D0CA"),
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
    check("plan: 每页都有家族与媒体判断（表驱动叙事动作已删，不得回来）",
          len(pages) == 2 and all((p.get("page_family")) for p in pages)
          and all(p.get("asset", {}).get("decision") for p in pages)
          and not any("move" in p for p in pages))
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
                                    "energy": "low"},
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
                                     "energy": "low"},
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
                                     "energy": "low"},
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
                                               "energy": "low"},
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
                                            "energy": "high"},
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
                                                      "energy": "high"},
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
                                            "energy": "high"},
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
                                             "density": "sparse", "energy": "high"},
                             "elements": [txt("t1")]}]}
    typo = [c for c in _guard.check_spec(spec_typo)["checks"] if c["rule"] == "theme_constraint"]
    check("seed: min_whitespace 别名仍生效、写错的约束键被 theme_constraint 点名",
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
                                            "energy": "low"},
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
    """跨页锚：plan 发锚 → 生成侧落元素 → guard 只查「在不在 / 编号是否连续」。

    位置纪律（眉标固定上缘、页码固定象限）已从引擎撤出（2026-09 审核）：它是设计判断，
    写在 references；引擎点名只会让作者每页把眉标挪回坐标，而不是判断为什么挪。
    """
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
                "density": "sparse", "energy": "high"},
                "anchor": anchors, "elements": els}

    def hits(slides):
        spec = {"canvas": {"width": 1280, "height": 720}, "theme": {"colors": colors},
                "slides": slides}
        return [c for c in _guard.check_spec(spec)["checks"] if c["rule"] == "deck_anchor"]

    A = {"eyebrow": "DATA STORY", "page_number": 2, "figure": "Fig. 01"}
    B = {"eyebrow": "COMPARISON", "page_number": 3, "figure": "Fig. 02"}
    check("anchor: 齐整的锚不吵；缺元素 / 编号断链各点名一次；位置漂移不再执法",
          not hits([page("s01", A), page("s02", B)])
          and bool(hits([page("s01", A, eyebrow=False), page("s02", B)]))
          and bool(hits([page("s01", A), page("s02", {"eyebrow": "X", "figure": "Fig. 05"})]))
          and not hits([page("s01", A), page("s02", B, eyebrow_y=64)])
          and not hits([page("s01", A), page("s02", B, pn_xy=(1100, 640))]),
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



def _ghost_ink_chart(element: dict) -> int:
    """ghost 为这个**图表**元素落了多少着色像素（与 _ghost_ink 同口径，走图表分支）。"""
    from PIL import Image
    import ghost as _ghost
    from primitives import RenderContext
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#888888",
                        "primary": "#1A3A5C", "secondary": "#40617F", "accent": "#C8501E"}}
    img = Image.new("RGBA", (1280, 720), (255, 255, 255, 255))
    _ghost._draw_chart(img, element, RenderContext(theme, {"width": 1280, "height": 720}), 1.0)
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

    # ③b 预览覆盖契约（v6.4.3）：每种合法图表类型要么「同形镜像」，要么明确
    #     「预览不渲染」——没有第三种归宿。曾经未实现的类型落到一条通用柱图兜底，
    #     于是 big_number_row / steps / timeline / waterfall 在预览里是**假图**
    #     （案源：年终总结稿按假预览改了三页构图）。这条断言是防复发的钉子：
    #     往 primitives.CHART_KINDS 里加一种图，就必须先回答它在预览里怎么活。
    from primitives import CHART_KINDS as _KINDS
    _mirror, _abstract = _ghost.PREVIEW_MIRRORED, _ghost.PREVIEW_ABSTRACT
    check("ghost: 预览覆盖契约覆盖全部图表类型（新增类型必须表态，不许落进假图兜底）",
          _mirror | _abstract == set(_KINDS) and not (_mirror & _abstract),
          f"缺 {sorted(set(_KINDS) - _mirror - _abstract)} · 多 "
          f"{sorted((_mirror | _abstract) - set(_KINDS))} · 重叠 {sorted(_mirror & _abstract)}")
    # 行为上没有「像柱图」这种中间态：抽象类型的着色量必须远小于同数据的真柱图。
    _cols = {"x": 0, "y": 0, "width": 700, "height": 360, "label_size": 12,
             "data": [{"label": "A", "value": 3}, {"label": "B", "value": 9}]}
    _wf, _col = dict(_cols, chart_kind="waterfall"), dict(_cols, chart_kind="column")
    check("ghost: 不渲染的类型不冒充柱图（waterfall 的着色量不可能是真柱图量级）",
          _ghost_ink_chart(_wf) * 3 < _ghost_ink_chart(_col),
          f"{_ghost_ink_chart(_wf)} vs {_ghost_ink_chart(_col)}")

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
    qa_params = set(_inspect.signature(_qa.verdict).parameters)

    def _call_kwargs(text: str, fn: str) -> set[str]:
        """取 `fn(...)` 整个调用里的关键字（按括号配平，别在第一个 ) 处停）——
        正则 `[^)]*` 会在嵌套调用前截断，漏掉的形参就是「假门」的来源。"""
        out: set[str] = set()
        for m in re.finditer(rf"\b{fn}\(", text):
            i, depth = m.end(), 1
            while i < len(text) and depth:
                depth += (text[i] == "(") - (text[i] == ")")
                i += 1
            out |= set(re.findall(r"(\w+)=", text[m.end():i]))
        return out

    bad_kwargs = sorted({k for k in _call_kwargs(ci, "verdict") | _call_kwargs(ci, "run_qa")
                         if k not in qa_params})
    check("ci: 工作流只引用存在的模板与真实存在的 verdict 形参（假门比没门更贵）",
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
    check("warn: 聚合后仍保留元素 id 与样本原文（改哪个、为什么，仍然说得出）",
          bool(packed) and packed[0]["ids"] == ["deck", "s03"]
          and "45%" in packed[0]["samples"][0], str(packed))
    import vao as _vao
    packet = _vao._repair_packet({"trace_summary": packed}, "draft",
                                 pathlib.Path("b.py"), pathlib.Path("o.pptx"))
    check("warn: 修复包只有一条指令通道（fix_plan；不再有第三份打磨清单）",
          bool(packet.get("fix_plan")) and "polish_plan" not in packet
          and "trace_summary" in packet)

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
    # ⑬ 验证层不评分、也不发设计提示：guard 只查工程事实与作者写下的数字。
    #     这一条防的是「优化时把审美悄悄装回门槛/提示」——一旦回来，
    #     AI 就会为了消掉提示去改设计（那正是本包反对的循环）。
    _adv_probe = {"canvas": {"width": 1280, "height": 720}, "theme": theme,
                  "slides": [{"id": "s01", "elements": _panels("rect")}]}
    _design_hint_rules = {"focus_scale", "organic_layer", "asset_contract",
                          "chart_style_drift", "overlay_opacity"}
    _probe_rules = {c["rule"] for c in check_spec(_adv_probe)["checks"]}
    check("verification: 设计诊断已整套移除（无 DESIGN_RULES、无 include_advisory、无审美提示）",
          not hasattr(_guard_mod, "DESIGN_RULES")
          and "include_advisory" not in _inspect.signature(check_spec).parameters
          and not (_probe_rules & _design_hint_rules),
          f"残留={sorted(_probe_rules & _design_hint_rules)}")


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

    # SKILL 是**导航层**：命令行与阈值只允许住在 references（唯一事实源）。
    # 双源事实会漂移——命令行改一处忘一处，作者照 SKILL 抄到的是过期命令；
    # 这条钉子守的是「SKILL 只告诉去哪里，不复制事实」。
    _skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    _cmd = [l for l in _skill.split("\n") if re.search(r"python\s+scripts/vao\.py", l)]
    _thr = sorted(set(re.findall(r"\d(?:\.\d+)?:1|\b\d+px\b", _skill)))
    check("docs: SKILL 只做导航（不复制命令行与阈值字面量，事实源在 references）",
          not _cmd and not _thr, f"命令行 {len(_cmd)} 行 · 阈值 {_thr}")

    # 归属：QA 是纯消费层——不编译、不读产物字节、不导入执行/缓存层。
    # （2026-09 审核：`run_qa` 曾在缺 compile_report 时自己编译，判定层因此也是生产者。）
    import ast as _ast
    _qa_src = (ROOT / "scripts" / "qa.py").read_text(encoding="utf-8")
    _qa_tree = _ast.parse(_qa_src)
    _imports = {n.module for n in _ast.walk(_qa_tree)
                if isinstance(n, _ast.ImportFrom) and n.module}
    _banned_imports = sorted(_imports & {"compiler", "compile_cache", "guard"})
    _verdict_fn = next(n for n in _qa_tree.body
                       if isinstance(n, _ast.FunctionDef) and n.name == "verdict")
    _verdict_calls = {c.func.attr if isinstance(c.func, _ast.Attribute) else
                      (c.func.id if isinstance(c.func, _ast.Name) else "")
                      for c in _ast.walk(_verdict_fn) if isinstance(c, _ast.Call)}
    _reads_artifact = sorted(_verdict_calls & {"stat", "read_bytes", "file_digest", "open"})
    check("ownership: QA 只消费报告（不编译、不读产物字节、不导入执行/缓存/校验层）",
          not _banned_imports and not _reads_artifact,
          f"imports={_banned_imports} verdict 里的产物读={_reads_artifact}")

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

    # D1 每个家族都必须被媒体判断解析：解析不到 = 静默退回默认，
    #    判断看起来发生了，其实没有。（叙事动作/构图语法不再由家族查表给出——
    #    那是把设计判断写成先验答案；D1b 反过来守住「不许预置答案」。）
    unresolved = sorted(fam for fam in {r["family"] for r in route.ROUTES.values()}
                        if "未知家族" in str(di.media_decision(
                            {"page_intent": {"page_family": fam}}).get("reason")))
    check("families: 每个 route 家族都能被媒体判断解析（无静默回落）",
          not unresolved, str(unresolved))

    # D1b 骨架只给事实与判断项，不给设计答案：叙事动作不再由表生成；
    #     构图只有作者显式声明时才出现，否则是待判断项。
    probe_plan = route.one_pass_plan(
        {"subject": "s", "slides": [{"id": "s01", "family": "data", "title": "t"}]})
    probe_intel = (probe_plan.get("pages") or [{}])[0]
    authored = route.one_pass_plan(
        {"subject": "s", "slides": [{"id": "s01", "family": "data", "title": "t",
                                     "composition": "single_column"}]})
    authored_comp = ((authored.get("pages") or [{}])[0].get("composition") or {})
    check("judgment: 意图层不产出表驱动叙事动作/构图答案（声明优先，未声明留白）",
          "move" not in probe_intel and "budget" not in probe_intel
          and not (probe_intel.get("composition") or {}).get("grammar")
          and authored_comp.get("grammar") == "single_column",
          f"默认={sorted(probe_intel)} 声明={authored_comp}")

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
    check("plan: composition 只在作者显式声明时出现（不预置构图答案，零坐标）",
          all(not (pg.get("composition") or {}).get("grammar")
              for pg in plan.get("pages") or [])
          and all(not (pg.get("composition") or {}).get("x") for pg in plan.get("pages") or []))

    # D3b 骨架自足：统一契约 / 方向事实 / 构图判断项必须在骨架里。
    #     缺任何一样，AI 就得回读 plan.json 去取信号——多一轮、多一万 token。
    # 自足的定义是「不用回读 plan.json / 不用读源码」；字段与阈值的查表指向
    # design-system.md（JIT：公式不再内联进骨架），设计判断留白而不是替作者写完。
    need = ("统一契约", "构图: 待判断", "design-system.md", "本文件即完整作业单")
    forbid = ("叙事动作:", "构图意图:", "备选")   # 表生成的答案不得回到骨架
    check("skeleton: 骨架即完整作业单（统一契约/构图判断项/字段查表在场，且不含预置答案）",
          all(s in body for s in need) and not any(s in body for s in forbid),
          [s for s in need if s not in body] + [s for s in forbid if s in body])

    # D3c 零消费镜像字段清退：intent_interpretation / media_confidence / media_reason /
    #     quality_budget / type_scale / move / budget 全库没有消费者，只会膨胀 plan 与
    #     上下文体积。表驱动判词（move / composition 答案 / quality_budget）已整层删除——
    #     这条检查保证它们不会以「镜像字段」的形式回来。
    dead = sorted({k for pg in route_pages
                   for k in ("intent_interpretation", "media_confidence", "media_reason",
                             "quality_budget", "type_scale", "move", "budget") if k in pg})
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
    # QA 现在是纯消费层：判定吃两份报告，不再自己 guard / compile。
    qa_result = qa.verdict(spec, work / "score_probe.pptx", mode="spec",
                           guard_report=guard_result,
                           compile_report={"passed": True, "skipped": True, "warnings": [],
                                           "slides": 1, "file_bytes": None,
                                           "reason": "spec_mode_no_compile",
                                           "output_exists": False, "output_sha256": None})
    scored = [k for k in ("score", "grade", "rating") if k in guard_result or k in qa_result]
    check("no-score: 验证层不产出分数/评级（只回答能不能交付）", not scored, str(scored))

    # D5 家族链路三处判断必须齐全：媒体判断（含别名）、质量预算、构图起点。
    #    任何一处少一条，那一类页面就会静默退回默认——判断看起来发生了，其实没有。
    from design_intelligence_rules import (FAMILY_TOKENS, FAMILY_ALIASES, MEDIA_MODEL,
                                           COMPLEX_LAYOUT_FAMILIES)
    unnamed = sorted(fam for fam in MEDIA_MODEL
                     if "未知家族" in str(di.media_decision(
                         {"page_intent": {"page_family": fam}}).get("reason")))
    bad_alias = sorted(t for t in FAMILY_ALIASES.values() if t not in MEDIA_MODEL)
    outside = sorted((set(FAMILY_ALIASES) | COMPLEX_LAYOUT_FAMILIES) - set(FAMILY_TOKENS))
    missing = sorted(set(MEDIA_MODEL) - set(FAMILY_TOKENS))
    check("families: 媒体判断覆盖每个家族名（无静默回落），别名目标必须落在媒体模型内",
          not unnamed and not bad_alias, f"无名={unnamed} 坏别名={bad_alias}")
    check("families: FAMILY_TOKENS 即全部家族写法（别名/复杂集不出词汇表）",
          not outside and not missing, f"越界={outside} 缺少={missing}")

    # D6 枚举值写错必须点名：家族（含只被媒体模型认识的命名空间）/留白职责/能量/密度。
    #    同时确认它是 warn 而非 error——「值不认识」是工程事实，不是「这页不合格」。
    probe = {"id": "s01",
             "page_intent": {"insight": "结论句", "focus": "t1", "page_family": "closing",
                             "energy": "mediumish", "density": "airy"},
             "elements": [{"type": "text", "id": "t1", "x": 96, "y": 240, "width": 800,
                           "height": 120, "text": "一句话结论", "size": 64, "color": "ink",
                           "role": "title", "line_height": 1.1, "max_lines": 1}]}
    probe_spec = {"canvas": spec["canvas"], "theme": spec["theme"], "slides": [probe]}
    checks = guard.check_spec(probe_spec).get("checks") or []
    named = " ｜ ".join(c.get("msg", "") for c in checks if c.get("rule") == "page_contract")
    fields = [f for f in ("energy", "density") if f"{f}=" in named]
    levels = {c.get("level") for c in checks
              if c.get("rule") == "page_contract" and "不在合法取值内" in str(c.get("msg"))}
    # 家族写 brief 的词（closing / cover / data…）是合法写法，不得被当成错值；
    # 只有引擎解析不出来的词才是事实错误。这条反向断言是防「引擎拿第二套命名给作者判卷」回潮。
    unknown_family = dict(probe)
    unknown_family["page_intent"] = {**probe["page_intent"], "page_family": "not_a_family"}
    unknown_checks = guard.check_spec({**probe_spec, "slides": [unknown_family]}).get("checks") or []
    unknown_named = any(c.get("rule") == "page_contract" for c in unknown_checks)
    check("enums: 能量/密度写错被点名；brief 家族写法（closing/cover…）不再被误报",
          len(fields) == 2 and levels == {"warn"} and guard.check_spec(probe_spec).get("passed")
          and unknown_named, f"fields={fields} levels={levels} unknown={unknown_named}")

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
    missing, missing_code = vao._asset_qc_report(str(manifest_path))
    check("assets: missing file is pending and exits nonzero",
          missing_code == 2 and bool(read_json(qcpath)["pending_assets"]))
    # Fixture is deliberately a neutral blank image; this tests the chain, not aesthetics.
    picture = images / pathlib.Path(entry["expected_filename"]).with_suffix(".jpg")
    Image.new("RGB", (640, 400), (242, 240, 230)).save(picture)
    bound, binding = vao.bind_asset_manifest(spec, manifest_path)
    check("assets: manifest directory + JPEG resolution agree with binding",
          binding["status"] == "PASS" and bound["slides"][0]["elements"][-1]["src"] == str(picture.resolve()))
    (images / pathlib.Path(entry["expected_filename"]).with_suffix(".jpg")).unlink()
    pending = run_vao("check", str(mod), str(d / "pending.pptx"), "--assets-manifest", str(manifest_path))
    check("assets: 一次 check 同时完成绑定与资产核验（缺图即阻断，不编译）",
          pending.returncode == 2 and not (d / "pending.pptx").exists()
          and bool(read_json(qcpath)["pending_assets"])
          and not read_json(d / "pending.manifest.json")["release_eligible"])
    # 缺图是「还没生成」，不是「图不合格」：报 pending 而不是 retry。
    check("assets: 缺图归入 pending（生成与返工分得开）",
          bool(read_json(qcpath)["pending_assets"])
          and not read_json(qcpath)["retry_assets"])
    Image.new("RGB", (640, 400), (242, 240, 230)).save(picture)
    with patch("asset_prompt.image_qc", return_value={"status":"ok", "checks":[
            {"check":"text_safe_area", "status":"issue"}]}), contextlib.redirect_stdout(io.StringIO()):
        retry, code = vao._asset_qc_report(str(manifest_path), phase="draft")
    check("assets: retry is not PASS and returns 2", code == 2 and retry["status"] == "BLOCKED" and bool(retry["retry_assets"]))
    _, success_code = vao._asset_qc_report(str(manifest_path), phase="release")
    qc = read_json(qcpath)
    check("assets: real image QC binds inspected bytes to manifest",
          success_code == 0 and qc["manifest_sha256"] == digest(manifest)
          and bool((qc["results"][0].get("witness") or {}).get("sha256")))
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
    existing_bytes, existing_code = vao._asset_qc_report(str(manifest_path), phase="release")
    check("assets: pre-existing generated bytes require explicit reuse",
          existing_code == 2 and bool(read_json(qcpath)["workflow_issues"]))
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
    vao._asset_qc_report(str(manifest_path), phase="release")
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



def check_production_path(work: pathlib.Path) -> None:
    """作者真正走的那条路：brief → plan → assets → 出图 → build → check(release)。

    为什么单独有这一条（v6.4.3）：上面那些用例都在验证**各段的判据**，而实战翻车
    发生在**段与段之间的契约**上——骨架把 plan 指纹发给作者，作者填完稿才发现资产清单
    的指纹与它不一致，一次修复要重走 plan→assets→改稿三遍（年终总结稿实际卡了 3 次）。
    契约测试走完整链路，把「段间契约」也钉住：
      ① 骨架的 asset_workflow 指纹必须就是清单认的那一个（不是「差不多」）；
      ② 作者重出图后按文档声明 asset_source，清单必须**保留规划身份**（同一 asset_id +
         prompt），而不是退化成 existing-<hash> ——身份断了，稿件与清单就靠肉眼对齐；
      ③ 这条链的终点是 release PASS + release_eligible，而不是「能编译」。
    """
    import contextlib
    import io
    from PIL import Image
    import vao

    def read_json(path):
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))

    d = work / "production-path"
    images = d / "generated_assets"
    images.mkdir(parents=True)
    brief = {"audience": "team", "decision": "approve the plan", "quality_level": "advanced",
             "design_direction": "editorial brand", "brand_colors": {"background": "#12141A",
             "ink": "#EDEAE4", "accent": "#C0A062", "muted": "#75716A", "secondary": "#A8A39B"},
             "slides": [{"id": "s01", "family": "cover", "title": "Production path",
                         "asset": "required", "asset_role": "background",
                         "asset_subject": "a still night lake", "medium": "photography",
                         "text_color": "#EDEAE4"}]}
    (d / "brief.json").write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    plan, skeleton, manifest = d / "plan.json", d / "build.py", d / "asset_manifest.json"
    run_vao("plan", str(d / "brief.json"), "--out", str(plan), "--skeleton", str(skeleton))
    run_vao("assets", str(d / "brief.json"), "--plan", str(plan), "--out", str(manifest),
            "--assets-dir", str(images))
    first = read_json(manifest)["assets"][0]
    # 出图（按清单的 expected_filename 落到约定路径）
    generated = images / first["expected_filename"]
    Image.new("RGB", (1376, 768), (14, 15, 17)).save(generated)
    # ② 重出图后按文档声明既有素材：身份必须保留
    brief["slides"][0]["asset_source"] = {"kind": "original", "path": str(generated),
                                          "source": "本稿自制（按清单 prompt 生成）"}
    (d / "brief.json").write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    run_vao("plan", str(d / "brief.json"), "--out", str(plan), "--skeleton", str(skeleton))
    run_vao("assets", str(d / "brief.json"), "--plan", str(plan), "--out", str(manifest),
            "--assets-dir", str(images))
    # ① 骨架发给作者的指纹 = 清单认的指纹（作者照抄的就是它，两处必须同一个）
    skel_plan = re.search(r"plan_sha256\D+([0-9a-f]{64})",
                          skeleton.read_text(encoding="utf-8")).group(1)
    check("production path: 骨架的 plan 指纹与资产清单一致（作者照抄即成立）",
          skel_plan == (read_json(manifest).get("workflow") or {}).get("plan_sha256"),
          f"骨架 {skel_plan[:12]} vs 清单 "
          f"{str((read_json(manifest).get('workflow') or {}).get('plan_sha256'))[:12]}")
    entry = read_json(manifest)["assets"][0]
    check("production path: 声明的既有素材保留规划身份（同一 asset_id + prompt，不退化成 existing-<hash>）",
          entry["decision"] == "existing" and entry["asset_id"] == first["asset_id"]
          and bool(entry.get("prompt")),
          f"{first['asset_id']} → {entry['asset_id']} · prompt={bool(entry.get('prompt'))}")

    # ③ 终点：release PASS —— 按骨架写最小 build，链路必须一次走通
    spec = {"canvas": {"width": 1280, "height": 720},
            "theme": {"colors": {"background": "#12141A", "ink": "#EDEAE4",
                                 "primary": "#EDEAE4", "secondary": "#A8A39B",
                                 "muted": "#75716A", "accent": "#C0A062"},
                      "fonts": {"cn": "Songti SC", "latin": "Georgia"}},
            "direction": {"color_intent": ["brand"]},
            "asset_workflow": {"plan_sha256": skel_plan, "plan_path": str(plan)},
            "slides": [{"id": "s01", "page_intent": {"insight": "one still night",
                         "focus": "bg", "page_family": "COVER", "density": "sparse",
                         "energy": "high"},
                        "anchor": {"eyebrow": "COVER"},
                        "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
                        "elements": [
                            {"type": "image", "id": "bg", "asset_id": entry["asset_id"],
                             "x": 0, "y": 0, "width": 1280, "height": 720, "fit": "cover",
                             "layer": "background", "role": "background",
                             "asset_function": "emotion",
                             "overlay": {"type": "solid", "color": "#12141A", "opacity": 0.4}},
                            {"type": "text", "id": "t", "role": "eyebrow", "x": 96, "y": 48,
                             "width": 400, "height": 24, "text": "COVER", "size": 12.5,
                             "color": "muted", "line_height": 1.2}]}]}
    build = d / "build.py"
    build.write_text("SPEC = " + repr(spec), encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        result, code = vao.run_check(str(build), str(d / "out.pptx"), mode="release",
                                     assets_manifest=str(manifest), speed="fast",
                                     preview=str(d / "preview"))
    released = read_json(d / "out.manifest.json") if (d / "out.manifest.json").exists() else {}
    check("production path: brief → plan → assets → build → release 一次走通（PASS + release_eligible）",
          code == 0 and result.get("status") == "PASS" and bool(released.get("release_eligible")),
          f"code={code} status={result.get('status')} eligible={released.get('release_eligible')} "
          f"codes={result.get('failure_codes')}")


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
    def invoke(spec_path, output, manifest=None, speed="fast"):
        with contextlib.redirect_stdout(io.StringIO()):
            return vao.run_check(str(spec_path), str(output), mode="release",
                                 assets_manifest=str(manifest) if manifest else None,
                                 speed=speed)
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
        assert vao._asset_qc_report(str(mp), phase="release")[1] == 0
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
    crossed, code = invoke(sp,folder/"deck.pptx",mp,speed="strict")
    check("cache: 跨档位不复用产物（清单里的 speed 必须与产物出身一致）",
          code == 0 and not crossed["performance"]["compile_reused"],
          str(crossed["performance"].get("compile_reused")))

    # H-02: a data manifest never executes its nested brief, even before hash failure.
    marker = d/"EXECUTED.txt"
    payload = d/"brief-data.txt"
    payload.write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('audit')\nBRIEF={{}}\n",encoding="utf-8")
    evil = read(mp)
    evil["workflow"]["brief_path"] = str(payload)
    evil["workflow"]["brief_file_sha256"] = "invalid"
    evil_path = d/"evil.json";save(evil_path,evil)
    q = run_vao("check",str(sp),str(folder/"evil.pptx"),"--assets-manifest",str(evil_path))
    check("H-02: JSON manifest cannot execute nested Python/text brief", q.returncode == 2 and not marker.exists())

    # H-03: simultaneous source overwrite cannot change the verified bytes consumed by PPT or preview.
    folder, sp, spec, mp, pic = asset_case("snapshot")
    # 编译编排已从 qa 移到 vao（2026-09 审核）：覆盖窗口就在这里——编译进行中
    # 源图被换掉，产物与预览仍必须用核验过的内存快照。
    import vao as _vao
    original = _vao._compile_step
    def mutate(*a, **kw):
        Image.new("RGB",(640,400),(0,0,255)).save(pic)
        return original(*a,**kw)
    with patch.object(_vao,"_compile_step",side_effect=mutate):
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
    assert vao._asset_qc_report(str(mp), phase="release")[1] == 0
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
    save(sp,spec);result,code=invoke(sp,folder/"deck.pptx")
    manifest=read(folder/"deck.manifest.json")
    check("M-07: one effective spec reaches compile, preview and manifest",
          code==0 and manifest["release_eligible"] and not manifest["validation"]["issues"])
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
    assert vao._asset_qc_report(str(mp), phase="release")[1] == 0
    spec["asset_workflow"]={"plan_path":str(pp),"plan_sha256":aw.digest(bundle)}
    spec["slides"][0]["elements"].append({"id":"photo","type":"image","asset_id":aw.asset_entries(manifest)[0]["asset_id"],
        "x":760,"y":280,"width":384,"height":256,"fit":"cover","asset_function":"context"})
    save(sp,spec);result,code=invoke(sp,folder/"deck.pptx",mp)
    check("control: explicit existing external asset can QC, compile and release",authorized and code==0)


def _ghost_border_ink_chart(element: dict, kind_theme: dict | None = None) -> int:
    """图表元素**外框线**上有多少着色像素（灰底白纸，1.0 倍）。

    锁行为不锁实现：不关心 ghost 走哪个分支，只关心「它有没有替产物画框」。
    """
    from PIL import Image
    import ghost as _ghost
    from primitives import RenderContext
    theme = {"colors": {"background": "#FFFFFF", "ink": "#111111", "muted": "#888888",
                        "primary": "#1A3A5C", "secondary": "#40617F", "accent": "#C8501E"}}
    img = Image.new("RGBA", (1280, 720), (255, 255, 255, 255))
    _ghost._draw_chart(img, element, RenderContext(theme, {"width": 1280, "height": 720}), 1.0)
    px = img.convert("RGB").load()
    x, y = int(element["x"]), int(element["y"])
    w, h = int(element["width"]), int(element["height"])
    ink = 0
    for i in range(x, x + w + 1):
        ink += (px[i, y] != (255, 255, 255)) + (px[i, y + h] != (255, 255, 255))
    for j in range(y, y + h + 1):
        ink += (px[x, j] != (255, 255, 255)) + (px[x + w, j] != (255, 255, 255))
    return ink


def _ghost_palette_hit(element: dict, colors: dict, count: int, highlight: int,
                       tol: int = 20) -> int:
    """预览里出现了几档系列色（用来抓「派生色被当令牌解析 → 静默回退灰」）。

    只认像素：把元素的绘图区抠出来，逐个色阶找容差内的像素。底图画成主题背景色
    （预览真实的合成底色），容差留出扇区 0.92 不透明度带来的一点点偏移。
    """
    from PIL import Image
    import ghost as _ghost
    from primitives import RenderContext, color_to_hex
    theme = {"colors": colors}
    bg = tuple(int(colors["background"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    img = Image.new("RGBA", (1280, 720), (*bg, 255))
    ctx = RenderContext(theme, {"width": 1280, "height": 720})
    el = dict(element, x=60, y=120, width=700, height=340)
    _ghost._draw_chart(img, el, ctx, 1.0)
    px = set(img.convert("RGB").crop((60, 120, 760, 460)).getdata())
    hit = 0
    for c in ctx.series_palette(count, highlight):
        h = color_to_hex(c)
        want = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        if any(all(abs(p[k] - want[k]) <= tol for k in range(3)) for p in px):
            hit += 1
    return hit


def _chart_xml(path: pathlib.Path) -> list[str]:
    import zipfile
    with zipfile.ZipFile(path) as z:
        return [z.read(n).decode("utf-8", "ignore")
                for n in sorted(z.namelist()) if re.match(r"ppt/charts/chart\d+\.xml$", n)]


def check_editorial_chart_defaults(work: pathlib.Path) -> None:
    """Editorial Data 的执行层默认值（v6.4.4）。

    少颜色不是「色值表短」，而是**每个序列/扇区都拿得到自己的颜色**；少装饰不是
    「少画点东西」，而是预览别替产物发明边框。四条断言全部落在产物与像素上：

      ① 单信号色主题（只声明 accent，premium 缺省回退）下六档系列色互不相同，
         相邻相对明度差 ≥0.05（深/浅两主题都成立）。
      ② 高亮在手时，accent 只出现在高亮位，其余序列一律不撞色。
      ③ 产物：4 段构成图 = 4 个不同扇区色；3 序列折线 = 3 个不同序列色。
      ④ 预览：同形镜像的图形外框线上 0 着色像素（产物本身无框）；占位分支仍带框。
    """
    import contextlib
    import io
    import json as _json
    import zipfile
    from primitives import RenderContext, luminance as _lum, color_to_hex
    import vao as _vao

    themes = {
        "dark": {"background": "#0E0F11", "ink": "#EAEAE7", "primary": "#EAEAE7",
                 "secondary": "#A5A6A1", "muted": "#6E6F6B", "accent": "#C0A062"},
        "light": {"background": "#F7F6F2", "ink": "#1B1A16", "primary": "#1B1A16",
                  "secondary": "#6E6A5E", "muted": "#8A8578", "accent": "#8E2F28"},
    }

    # ── ① 单信号色主题：六档互不相同 + 相邻明度差够 ────────────────────────
    worst, details = 1.0, []
    for name, colors in themes.items():
        ctx = RenderContext({"colors": colors})
        hexes = [color_to_hex(c) for c in ctx.series_palette(6)]
        lums = [_lum(h) for h in hexes]
        gaps = [round(b - a, 3) for a, b in zip(lums, lums[1:])]
        worst = min(worst, min(gaps))
        details.append(f"{name} {len(set(hexes))}色 最小ΔL {min(gaps):.3f}")
        check(f"editorial: {name} 主题六档系列色互不相同（同色 = 序列无从区分）",
              len(set(hexes)) == 6 and hexes[0] == color_to_hex(ctx.color("accent")),
              " ".join(hexes))
    check("editorial: 六档系列色相邻相对明度差 ≥0.05（两主题都成立）",
          worst >= 0.05, "；".join(details))

    # ── ② 高亮不与任何序列撞色 ─────────────────────────────────────────────
    collide = []
    for name, colors in themes.items():
        ctx = RenderContext({"colors": colors})
        for hl in (0, 1, 2):
            for n in (2, 3, 4):
                pal = [color_to_hex(c) for c in ctx.series_palette(n, hl)]
                if len(set(pal)) != n:
                    collide.append(f"{name}/hl={hl}/n={n}")
        if len(set(color_to_hex(c) for c in ctx.series_palette(6, -1))) != 6:
            collide.append(f"{name}/无高亮")
    check("editorial: 高亮在手时 accent 只出现在高亮位（不与非高亮序列撞色）",
          not collide, " ".join(collide))

    # ── ③ 产物：扇区/序列各自拿到自己的颜色 ────────────────────────────────
    def compile_one(kind_extra: dict, out: pathlib.Path) -> str:
        spec = {"canvas": {"width": 1280, "height": 720},
                "theme": {"colors": themes["dark"]}, "direction": {"color_intent": ["hierarchy"]},
                "slides": [{"id": "s01",
                            "page_intent": {"insight": "x", "focus": "c1",
                                            "page_family": "DATA_STORY", "density": "balanced",
                                            "energy": "low"},
                            "elements": [dict({"type": "chart", "id": "c1", "x": 96, "y": 200,
                                               "width": 1000, "height": 340, "unit": "%",
                                               "period": "2026", "basis": "同口径",
                                               "source": "示例", "metric": "m1"}, **kind_extra)]}]}
        sp = out.with_suffix(".json")
        sp.write_text(_json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            _vao.run_check(str(sp), str(out), mode="draft", speed="fast", deadline=120.0)
        return (_chart_xml(out) or [""])[0]

    d = work / "editorial"
    d.mkdir()
    donut_xml = compile_one({"chart_kind": "donut",
                             "data": [{"label": f"类{i}", "value": 20 + i} for i in range(4)]},
                            d / "donut.pptx")
    slices = sorted(set(re.findall(r"<c:dPt>.*?<a:solidFill><a:srgbClr val=\"([0-9A-F]{6})\"",
                                   donut_xml, re.S)))
    check("editorial: 产物里 4 段构成图 = 4 个不同扇区色（此前第 1/2 段同色）",
          len(slices) == 4, " ".join(slices))

    line_xml = compile_one({"chart_kind": "line", "categories": ["Q1", "Q2", "Q3"],
                            "series": [{"name": "甲", "values": [9, 12, 16]},
                                       {"name": "乙", "values": [5, 6, 7]},
                                       {"name": "丙", "values": [2, 3, 4]}]},
                           d / "line.pptx")
    strokes = sorted(set(re.findall(r"<c:ser>.*?<a:solidFill><a:srgbClr val=\"([0-9A-F]{6})\"",
                                    line_xml, re.S)))
    check("editorial: 产物里 3 序列折线 = 3 个不同序列色（此前第 1/2 条同色）",
          len(strokes) == 3, " ".join(strokes))

    # ── ④ 预览不发明装饰：镜像图形无框，占位分支仍带框 ──────────────────────
    box = {"x": 96, "y": 200, "width": 1000, "height": 340}
    mirrored = dict(box, type="chart", id="c1", chart_kind="bar",
                    data=[{"label": "甲", "value": 12}, {"label": "乙", "value": 30}])
    abstract = dict(box, type="chart", id="c2", chart_kind="process_flow",
                    data=[{"label": "甲", "value": 1}, {"label": "乙", "value": 2}])
    empty = dict(box, type="chart", id="c3", chart_kind="bar", data=[])
    check("editorial: 预览不替产物发明外框（镜像图形外框线 0 着色像素）",
          _ghost_border_ink_chart(mirrored) == 0, str(_ghost_border_ink_chart(mirrored)))
    donut_el = {"type": "chart", "id": "c4", "chart_kind": "donut",
                "data": [{"label": f"类{i}", "value": 20 + i} for i in range(4)]}
    painted = _ghost_palette_hit(donut_el, themes["dark"], 4, 0)
    check("editorial: 预览扇区色与产物色阶同源（不是灰块——派生色被当令牌会静默回退）",
          painted >= 3, f"命中 {painted}/4 档")
    stacked_el = {"type": "chart", "id": "c5", "chart_kind": "stacked_bar",
                  "data": [{"label": "甲", "value": 45}, {"label": "乙", "value": 35},
                           {"label": "丙", "value": 20}]}
    stacked_hit = _ghost_palette_hit(stacked_el, themes["dark"], 3, -1)
    check("editorial: 预览堆叠条段色与产物色阶同源（此前是 secondary/primary 一排灰）",
          stacked_hit >= 2, f"命中 {stacked_hit}/3 档")

    check("editorial: 占位分支仍带边界（ABSTRACT / 载荷缺失的框是「我不画」的意思）",
          _ghost_border_ink_chart(abstract) > 0 and _ghost_border_ink_chart(empty) > 0,
          f"abstract={_ghost_border_ink_chart(abstract)} empty={_ghost_border_ink_chart(empty)}")


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


def check_asset_role_separation() -> None:
    """角色分离（v5.7）：背景图与插图的职责边界，不是第三个枚举系统。

    这一组回答的是两个具体的失效：**背景图被当成一张大插图**（被要求明确主体、
    被抠成透明剪影）与**插图被当成背景纹理**（被要求整块低密度、被融进版面底色）。
    角色只有一个出口（asset_role → 执行类型 asset_type），用途不得偷换角色，
    生成纪律与 QC 判据都跟着角色走——而判据只改变「问哪几个问题」，阈值一个没动。
    纯函数级断言 + 一条声明链集成。
    """
    import route as _route
    import vao as _vao
    from asset_prompt import (ASSET_ROLES, ROLE_AUTHORITATIVE_SOURCES, build_asset_prompt,
                              enhance_asset_card, qc_retry_decision, resolve_asset_role)

    # R1 角色解析：未声明不猜（background/assumed）；声明即 declared；未知值 fail-closed
    fail_closed = False
    try:
        resolve_asset_role("bg")
    except ValueError:
        fail_closed = True
    check("role: 解析唯一出口（未声明=background/assumed · 声明=declared · 旧 asset_type=legacy）",
          resolve_asset_role(None) == ("background", "assumed")
          and resolve_asset_role("illustration") == ("illustration", "declared")
          and resolve_asset_role(None, "icon") == ("icon", "legacy")
          and fail_closed and set(ASSET_ROLES) == {"background", "illustration", "hybrid"},
          f"{resolve_asset_role(None)} / {resolve_asset_role('illustration')} / fail_closed={fail_closed}")

    def _card(**over) -> dict:
        card = {"apc": "APC-ROLE", "asset_type": "background", "asset_function": "hero",
                "subject": ["a celadon tea bowl on a wooden table"],
                "color": ["neutral tonal range with one restrained accent"],
                "material": ["glazed ceramic and warm oak"], "lighting": ["soft box light"],
                "composition": ["calm evidence-field composition"],
                "medium": "photography", "negative": []}
        card.update(over)
        return card

    page = {"negative_space_anchor": "left", "light_direction": "left", "energy": "low",
            "safe_area": {"x": 0.06, "y": 0.08, "width": 0.34, "height": 0.78},
            "text_color": "dark"}

    # R2 背景的生成纪律：连续视觉场 + 大面积负空间；不给「主体给文字让位」句式
    bg = build_asset_prompt(_card(), page)["prompt"]
    check("prompt: 背景走空间纪律（连续材质场 / 大面积负空间；不出现主体让位句式）",
          "large clean negative space on the left side" in bg
          and "visual environment, not a picture of a thing" in bg
          and "continuous tonal and material field" in bg
          and "open for the page's text" not in bg, bg[:120])

    # R3 插图的生成纪律：独立视觉对象 + 主体↔文字关系；不要求整块画面低密度
    illus = build_asset_prompt(_card(asset_type="illustration"), page)["prompt"]
    check("prompt: 插图走对象纪律（独立视觉对象 + 与文字建立关系；不要求整块负空间）",
          "independent visual object" in illus
          and "stays open for the page's text" in illus
          and "large clean negative space" not in illus
          and "visual environment, not a picture of a thing" not in illus, illus[:120])

    # R4 介质已声明时，插图不吃透明剪影与风格预设（一张摄影插图不是抠图）
    no_medium = {k: v for k, v in _card(asset_type="illustration").items() if k != "medium"}
    cutout = build_asset_prompt(no_medium, page)["prompt"]
    check("prompt: 插图介质已声明时风格词让位（无 3D/透明剪影，保留独立对象结构）",
          "3D minimal illustration" not in illus
          and "isolated on pure transparent background" not in illus
          and "clean separation from what surrounds it" in illus
          and "3D minimal illustration" in cutout, illus[:120])

    # R5 空间融合按角色：空间资产融进版面，独立视觉对象保住边界
    # （融合句由 enhance_asset_card 注入——按生产路径建卡，别测一张没经过增强的卡）
    melt = "image melts into the layout background"

    def _enhanced(**over) -> dict:
        return enhance_asset_card(_card(**over), family="quiet_minimal")

    fused_bg = build_asset_prompt(_enhanced(), page)
    fused_hybrid = build_asset_prompt(_enhanced(asset_type="hybrid"), page)
    fused_il = build_asset_prompt(_enhanced(asset_type="illustration"), page)
    check("prompt: 空间融合按角色（background/hybrid 融入版面；illustration 保留自身边界）",
          fused_bg["meta"]["fusion_enabled"] and fused_hybrid["meta"]["fusion_enabled"]
          and not fused_il["meta"]["fusion_enabled"]
          and melt in fused_bg["prompt"] and melt in fused_hybrid["prompt"]
          and melt not in fused_il["prompt"],
          f"bg={fused_bg['meta']['fusion_enabled']} il={fused_il['meta']['fusion_enabled']}")

    # R6 无安全区（版面不压文字）时，「给页面文字让空间」的句子是空指令
    no_area = build_asset_prompt(_card(asset_type="illustration"),
                                 {**page, "safe_area": {}})["prompt"]
    check("prompt: 无安全区时「让空间给文字」句式全部消失（插图同样适用）",
          "page's text" not in no_area and "negative space" not in no_area, no_area[:120])

    def _qc(*names: str) -> dict:
        return {"status": "issue",
                "checks": [{"check": n, "status": "issue"} for n in names]}

    # R7 声明的角色决定问哪几个问题（未声明则沿用旧口径，新字段不放宽旧判据）
    bg_pos = qc_retry_decision(_qc("subject_position"), phase="release",
                              asset_role="background", asset_function="hero")
    il_pos = qc_retry_decision(_qc("subject_position"), phase="release",
                               asset_role="illustration")
    hy_pos = qc_retry_decision(_qc("subject_position"), phase="release", asset_role="hybrid")
    legacy_pos = qc_retry_decision(_qc("subject_position"), phase="release",
                                   asset_function="emotion")
    check("QC: 角色决定判据（background 免主体裁切判定；illustration/hybrid 不豁免；未声明走旧口径）",
          bg_pos["action"].startswith("accept") and il_pos["action"] == "block"
          and hy_pos["action"] == "block" and legacy_pos["action"].startswith("accept")
          and il_pos["asset_role"] == "illustration",
          f"{bg_pos['action']}/{il_pos['action']}/{hy_pos['action']}/{legacy_pos['action']}")

    # R8 插图的安全区纹理密度降为 advisory；背景承诺没变，判据不动
    il_tex = qc_retry_decision(_qc("text_safe_area"), phase="release", asset_role="illustration")
    bg_tex = qc_retry_decision(_qc("text_safe_area"), phase="release", asset_role="background")
    check("QC: 插图的安全区纹理密度为 advisory（背景仍阻断——判据跟着承诺走，阈值不动）",
          il_tex["action"] == "accept_with_advisory"
          and il_tex["advisory_checks"] == ["text_safe_area"] and bg_tex["action"] == "block")

    # R9 声明链：brief 的 asset_role 一路落到 plan / 卡片，且不被 function 推导
    brief = {"design_direction": "quiet_minimal", "slides": [
        {"id": "s01", "family": "cover", "title": "封面", "asset": "required",
         "asset_role": "illustration", "asset_function": "hero",
         "asset_subject": "a celadon tea bowl standing on its own"}]}
    plan = _route.plan_deck(brief)
    card, _ = _vao._asset_page(brief, plan["pages"][0], brief["slides"][0],
                               asset_id="asset-role-probe", deck=plan)
    brief2 = {"design_direction": "quiet_minimal", "slides": [
        {"id": "s01", "family": "cover", "title": "封面", "asset": "required",
         "asset_function": "hero", "asset_subject": "mist over still water"}]}
    plan2 = _route.plan_deck(brief2)
    card2, _ = _vao._asset_page(brief2, plan2["pages"][0], brief2["slides"][0],
                                asset_id="asset-role-probe-2", deck=plan2)
    check("role: 声明链（plan.asset.role → 卡片执行类型；hero 用途不得把角色推成插图）",
          (plan["pages"][0]["asset"] or {}).get("role") == "illustration"
          and card["asset_type"] == "illustration" and card["asset_role_source"] == "declared"
          and card["asset_function"] == "hero"
          and card2["asset_type"] == "background" and card2["asset_role_source"] == "assumed"
          and ROLE_AUTHORITATIVE_SOURCES == ("declared", "legacy"),
          f"{card['asset_type']}/{card['asset_role_source']} vs {card2['asset_type']}/{card2['asset_role_source']}")

    # R10 契约活在文档里：声明字段与四步判断必须写在作者看得见的地方
    brief_yml = (ROOT / "templates" / "brief.yml").read_text(encoding="utf-8")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    refs = ROOT / "references"
    workflow_doc = (refs / "asset-workflow.md").read_text(encoding="utf-8")
    check("docs: 角色分离写进契约（brief.yml 声明 asset_role；SKILL 四步判断不填图）",
          "asset_role: background" in brief_yml
          and "Asset Decision ≠ Image Filling" in skill
          and "asset_role" in workflow_doc)


def check_speed_profile(work: pathlib.Path) -> None:
    """速度档（v5.9）：两分钟交付档的每条机制都必须可测，否则它会悄悄退化。

    这里锁行为不锁实现：预算被不被尊重、同图变换了几次、预览声明了什么范围、
    图片被读了几遍——都能从报告与产物上读出来，而不是靠读源码相信。
    """
    import copy
    import hashlib
    import json
    from PIL import Image
    import numpy as np
    import ghost as _ghost
    import qa as _qa
    import vao as _vao
    import asset_prompt as _ap
    from asset_prompt import QC_FAST_MAX_SIDE, image_qc
    from compiler import compile_deck
    from asset_workflow import digest, read_json

    d = work / "speed"
    d.mkdir()

    # ── 1) 档位与默认值 ──────────────────────────────────────────────────
    help_txt = run_vao("check", "--help").stdout
    check("speed: check 暴露 fast/strict 两档且默认 fast",
          "--speed {fast,strict}" in help_txt and _vao.DEFAULT_SPEED == "fast"
          and _vao.DEFAULT_DEADLINE == 120.0,
          _vao.DEFAULT_SPEED)

    # ── 2) QC 像素预算：降采样但留痕；安全区仍按原生分辨率判 ────────────────
    w_px, h_px = 2048, 1152      # 大于 QC_FAST_MAX_SIDE，才能验证「降采样档」的行为
    xs = np.linspace(0, 1, w_px)[None, :]
    lum = 0.16 + 0.05 * xs + np.random.default_rng(3).normal(0, 0.02, size=(h_px, w_px))
    noisy = np.repeat(np.clip(lum, 0, 1)[..., None], 3, axis=2)
    noisy[:, :int(w_px * 0.34)] = np.clip(
        noisy[:, :int(w_px * 0.34)] + np.random.default_rng(4).normal(
            0, 0.16, size=(h_px, int(w_px * 0.34), 1)), 0, 1)
    probe = d / "busy.png"
    Image.fromarray((noisy * 255).astype("uint8"), "RGB").save(probe)
    fast_qc = image_qc(str(probe), safe_area="left", expected_ratio="16:9",
                       max_side=QC_FAST_MAX_SIDE)
    strict_qc = image_qc(str(probe), safe_area="left", expected_ratio="16:9", max_side=None)
    check("speed: 快速档在降采样域统计并写明像素域（qc_scale / qc_domain）",
          fast_qc["qc_scale"] > 1 and fast_qc["qc_domain"][0] < w_px
          and strict_qc["qc_scale"] == 1 and fast_qc["dimensions"] == [w_px, h_px],
          f"fast={fast_qc.get('qc_scale')} strict={strict_qc.get('qc_scale')}")
    fast_bad = {c["check"] for c in fast_qc["checks"] if c["status"] == "issue"}
    strict_bad = {c["check"] for c in strict_qc["checks"] if c["status"] == "issue"}
    check("speed: 文字安全区纹理仍按原生分辨率判（细密噪点照样阻断）",
          "text_safe_area" in fast_bad and "text_safe_area" in strict_bad,
          f"fast={sorted(fast_bad)} strict={sorted(strict_bad)}")
    check("speed: 快速档不把均匀像素噪点误判成主体（唯一有意差异）",
          "subject_position" in strict_bad and "subject_position" not in fast_bad,
          f"fast={sorted(fast_bad)} strict={sorted(strict_bad)}")

    # ── 3) 编译：无临时文件 · 同图同盒只变换一次 · 产物确定性 ──────────────
    builds = d / "builds"
    builds.mkdir()
    picture = builds / "photo.png"
    Image.fromarray((np.clip(np.repeat(
        (0.2 + 0.5 * np.linspace(0, 1, 1600)[None, :] + np.random.default_rng(5).normal(
            0, 0.05, size=(900, 1600)))[..., None], 3, axis=2), 0, 1) * 255).astype("uint8"),
        "RGB").save(picture)
    blob = picture.read_bytes()
    spec = {"canvas": {"width": 1280, "height": 720},
            "theme": {"colors": {"background": "#0D0F12", "ink": "#FFFFFF"}},
            "slides": [{"id": "s01", "elements": [
                {"type": "image", "id": "hero", "src": str(picture), "x": 0, "y": 0,
                 "width": 512, "height": 288, "fit": "cover"},
                {"type": "image", "id": "hero-again", "src": str(picture), "x": 0, "y": 0,
                 "width": 512, "height": 288, "fit": "cover"},
                {"type": "image", "id": "hero-other-box", "src": str(picture), "x": 0, "y": 320,
                 "width": 256, "height": 288, "fit": "cover"},
            ]}]}
    snapshots = {str(picture): blob}
    out_a = builds / "a.pptx"
    report_a = compile_deck(spec, out_a, checks=False, image_bytes=snapshots, speed="fast")
    perf = report_a.get("performance") or {}
    check("compile: 同图同盒只变换一次（换盒子才另算一次、解码底图仍复用）",
          perf.get("image_transforms") == 2 and perf.get("image_transform_reuses") == 1
          and perf.get("image_decode_reuses") == 1, str(perf))
    out_b = builds / "b.pptx"
    compile_deck(spec, out_b, checks=False, image_bytes=snapshots, speed="fast")
    check("compile: 同 spec 同档位两遍编译字节一致（确定性未因提速而丢）",
          hashlib.sha256(out_a.read_bytes()).hexdigest()
          == hashlib.sha256(out_b.read_bytes()).hexdigest())
    leftovers = sorted(p.name for p in builds.iterdir()
                       if p.suffix in {".tmp", ".png"} and p.name != picture.name)
    check("compile: 图片变换不留中间文件（进程内字节直传）",
          not leftovers and "tempfile" not in (SCRIPTS / "compiler.py").read_text(encoding="utf-8"),
          str(leftovers))
    # 解码一次：核验把底图交给编译，编译期不再解第二遍——产物必须一个字节都不差
    decoded = {}
    handoff_qc = image_qc(str(picture), safe_rect={"x": 0.0, "y": 0.0,
                                                   "width": 0.4, "height": 1.0},
                          max_side=QC_FAST_MAX_SIDE, decoded=decoded,
                          decode_key=str(picture))
    held = decoded.get(str(picture))
    check("assets: 核验交出已解码底图（原生分辨率 · RGB · 流句柄已放）",
          held is not None and held.mode == "RGB" and held.size == (1600, 900)
          and held.fp is None and handoff_qc.get("qc_scale") == 2,
          f"held={bool(held)} scale={handoff_qc.get('qc_scale')}")
    capped = {f"k{i}": held for i in range(_ap.QC_DECODE_HOLD_MAX_IMAGES)}
    image_qc(str(picture), max_side=QC_FAST_MAX_SIDE, decoded=capped, decode_key="overflow")
    check("assets: 已解码底图有内存上限（快路径不把内存变成新的失败模式）",
          "overflow" not in capped, str(sorted(capped)))
    out_d = builds / "d.pptx"
    seeded = compile_deck(spec, out_d, checks=False, image_bytes=snapshots,
                          decode_seed=decoded, speed="fast")
    seeded_perf = seeded.get("performance") or {}
    check("compile: 复用核验底图不改产物字节（同一份像素，少解一遍）",
          hashlib.sha256(out_d.read_bytes()).hexdigest()
          == hashlib.sha256(out_a.read_bytes()).hexdigest()
          and seeded_perf.get("image_decode_reuses", 0) >= 1,
          f"reuses={seeded_perf.get('image_decode_reuses')}")

    out_c = builds / "c.pptx"
    strict_report = compile_deck(spec, out_c, checks=False, image_bytes=snapshots, speed="strict")
    import zipfile
    with zipfile.ZipFile(out_a) as za, zipfile.ZipFile(out_c) as zc:
        check("compile: fast/strict 产物结构一致（条目与页数相同，只是压缩口径不同）",
              sorted(za.namelist()) == sorted(zc.namelist())
              and report_a["slides"] == strict_report["slides"] == 1)

    # ── 4) 方向预览：确定性采样 + 范围可核对 ──────────────────────────────
    dense = [{"id": f"s{i:02d}", "elements": [{"type": "text", "id": f"t{i}"}] * (i % 5 + 1)}
             for i in range(1, 16)]
    dense[6]["elements"] = [{"type": "image", "id": "img"}] + dense[6]["elements"]
    picks = _ghost.sample_pages(dense, limit=4)
    check("ghost: 采样确定性、含封面与收尾、且不超上限",
          picks == _ghost.sample_pages(dense, limit=4) and len(picks) == 4
          and picks[0] == 1 and picks[-1] == 15, str(picks))
    check("ghost: 页数不超过上限时是全量证据（不是采样）",
          _ghost.sample_pages(dense[:3], limit=4) == [1, 2, 3])
    mismatched = {"pages": ["g1.png", "g2.png"], "count": 2, "scope": "sampled",
                  "sampled_ids": ["s01"], "slide_ids": ["s01", "s02"]}
    check("ghost: 采样范围可核对（声明页 ≠ 渲染页即报问题）",
          bool(_qa.preview_issues(mismatched, ["s01", "s02", "s03"])))

    # ── 5) 预算纪律：核心阶段照跑，可选证据在预算不足时留痕跳过 ─────────────
    brief = d / "brief.yml"
    brief.write_text(json.dumps({
        "audience": "investor", "decision": "approve",
        "slides": [{"id": "s01", "family": "cover", "title": "Speed",
                    "asset_subject": "ceramic bowl", "medium": "photography",
                    "asset_ratio": "16:10", "text_color": "dark"}]}), encoding="utf-8")
    plan = d / "plan.json"
    skeleton = d / "build_deck.py"
    manifest_path = d / "asset_manifest.json"
    pictures = d / "pictures"
    run_vao("plan", str(brief), "--out", str(plan), "--skeleton", str(skeleton))
    run_vao("assets", str(brief), "--plan", str(plan), "--out", str(manifest_path),
            "--assets-dir", str(pictures))
    manifest = read_json(manifest_path)
    entry = next(e for e in manifest["assets"] if e.get("decision") == "generate")
    pictures.mkdir(exist_ok=True)
    Image.new("RGB", (640, 400), (242, 240, 230)).save(
        pictures / pathlib.Path(entry["expected_filename"]).with_suffix(".jpg"))
    spec_mod, _ = _vao.load_spec(spec_module(d / "base.py"))
    spec_mod["asset_workflow"] = {"plan_sha256": digest(read_json(plan))}
    spec_mod["slides"][0]["elements"].append(
        {"type": "image", "id": "photo", "asset_id": entry["asset_id"],
         "x": 760, "y": 280, "width": 384, "height": 240})
    filled = d / "filled.json"
    filled.write_text(json.dumps(spec_mod), encoding="utf-8")

    tight = run_vao("check", str(filled), str(d / "tight.pptx"), "--mode", "release",
                    "--assets-manifest", str(manifest_path), "--deadline", "0.001")
    packet = read_json(d / "tight.repair.json")
    skipped = [s.get("stage") for s in (packet.get("budget") or {}).get("skipped") or []]
    check("budget: 预算不足时跳过可选证据并留痕（不超时、不静默通过）",
          tight.returncode == 2 and "ghost_preview" in skipped
          and not read_json(d / "tight.manifest.json")["release_eligible"], str(skipped))

    # ── 6) 有图链在快速档跑通：预览范围 + 单次哈希见证 + 字节身份 ───────────
    released = run_vao("check", str(filled), str(d / "deck.pptx"), "--mode", "release",
                       "--assets-manifest", str(manifest_path))
    rm = read_json(d / "deck.manifest.json")
    ver = rm.get("verification") or {}
    check("release: 快速档跑通并在清单里标注证据范围与档位",
          released.returncode == 0 and rm["release_eligible"]
          and ver.get("visual_evidence_scope") in {"full", "sampled"}
          and ver.get("speed") == "fast", released.stdout[-300:])
    check("release: 产物字节戳由同一轮见证，不重复整包哈希",
          any("未重复整包哈希" in n for n in (rm["validation"].get("notes") or [])),
          str(rm["validation"].get("notes"))[:200])
    qc = read_json(d / "asset_manifest.qc.json")
    check("assets: QC 记录字节凭证（witness{size,mtime_ns,sha256}）供快路径守卫",
          all(isinstance((r.get("witness") or {}).get("size"), int)
              and isinstance((r.get("witness") or {}).get("mtime_ns"), int)
              for r in qc["results"])
          and (qc.get("pixel_profile") or {}).get("speed") == "fast")

    # ── 7) 文档：速度档与预算纪律必须写进主 Skill ──────────────────────────
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    check("docs: SKILL 写明两档速度、预算纪律与单次收口",
          "--speed fast" in skill and "strict" in skill and "--deadline" in skill)


def check_runtime_reuse(work: pathlib.Path) -> None:
    """运行时减法（v6.1）：每份字节只读一次、每张图只解一次、每个判定只做一次。

    这里锁的是「复用的前提」而不是「复用的实现」：什么时候可以省、什么时候必须重做，
    全部从报告与产物上读出来。少做一次测量是优化，该做却漏做是缺陷——两类都要拦住。
    """
    import contextlib
    import io
    import json as _json
    
    import asset_workflow as _aw
    import compile_cache as _cc
    import ghost as _ghost
    import primitives as _pr
    import vao as _vao

    d = work / "runtime"
    d.mkdir()
    assets = d / "assets"
    assets.mkdir()

    # ── 1) 读一次：同一份 JSON 在同一个进程里只解析一遍，改了必须重读 ──────────
    # 两次写盘必须可区分：文件系统时间戳粒度可能粗到毫秒级（本机实测 4ms），
    # 若同一刻度内的两次写盘拿到同一个 mtime，「变了吗」的凭证就失效了。
    # 这里连续写两遍（不 sleep），逼出最坏情况：写入者必须保证凭证前进。
    doc = d / "doc.json"
    _pr.json_write(doc, {"v": 1}, indent=0, trailing_newline=False)
    first = _pr.json_read_cached(doc)
    again = _pr.json_read_cached(doc)
    stamp_1 = doc.stat().st_mtime_ns
    _pr.json_write(doc, {"v": 2}, indent=0, trailing_newline=False)
    stamp_2 = doc.stat().st_mtime_ns
    after = _pr.json_read_cached(doc)
    check("runtime: 同一份 JSON 读一次即复用（同刻度内重写也立即重读）",
          first is again and first["v"] == 1 and after["v"] == 2 and after is not first
          and stamp_2 > stamp_1, f"mtime {stamp_1} → {stamp_2}")

    # ── 1b) 底图解码交接：预览复用核验阶段解过的像素，且像素与原路径逐字节一致 ──
    # 「省一次解码」只有在像素不变时才算省——所以这里同时钉住两件事：
    # 交接命中时不再解码，且渲染出的页图与原路径（从字节解码）逐字节相同。
    from PIL import Image as _PILImage
    import hashlib as _hashlib2
    import io as _io
    import pathlib as _pathlib

    picture2 = assets / "photo2.png"
    _PILImage.new("RGB", (320, 200), (60, 90, 120)).save(picture2)
    held: dict = {}
    with _PILImage.open(picture2) as opened:
        held[str(picture2)] = opened.convert("RGB")
    blobs = {str(picture2): picture2.read_bytes()}
    one_page = {"canvas": {"width": 640, "height": 360}, "theme": {},
                "slides": [{"id": "p1", "elements": [
                    {"type": "image", "id": "im", "x": 40, "y": 40, "width": 400, "height": 240,
                     "src": str(picture2), "fit": "cover"}]}]}

    def _render_preview(use_handoff: bool, tag: str):
        spec = dict(one_page)
        spec["_image_bytes"] = blobs
        if use_handoff:
            spec["_image_decoded"] = held
        counter = {"decodes": 0}
        real_load = _ghost.Image.Image.load

        def counted_load(self):
            # 与审计同一口径：只有真的从字节解出像素才计一次（load 幂等）。
            if self.__dict__.get("_im") is None:
                counter["decodes"] += 1
            return real_load(self)

        _ghost.Image.Image.load = counted_load
        try:
            page = _ghost.ghost_page(spec["slides"][0], spec, scale=0.5, supersample=1)
        finally:
            _ghost.Image.Image.load = real_load
        buffer = _io.BytesIO()
        page.save(buffer, "PNG", compress_level=1)
        return _hashlib2.sha256(buffer.getvalue()).hexdigest(), counter["decodes"]

    px_hold, decodes_hold = _render_preview(True, "hold")
    px_plain, decodes_plain = _render_preview(False, "plain")
    check("runtime: 预览复用已解码底图（命中不再解码，像素逐字节一致）",
          decodes_hold == 0 and decodes_plain >= 1 and px_hold == px_plain,
          f"交接解码 {decodes_hold} 次 / 原路径 {decodes_plain} 次 · 页图 {px_hold[:12]}…")

    # ── 2) 字节一次、摘要一次：共享摘要不改变缓存身份（决定要不要重编的投影）───
    from PIL import Image
    picture = assets / "photo.png"
    Image.new("RGB", (640, 360), (240, 238, 232)).save(picture)
    blob = picture.read_bytes()
    import hashlib
    specs = {"canvas": {"width": 1280, "height": 720},
             "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111"}},
             "slides": [{"id": "s01", "elements": [
                 {"type": "image", "id": "im", "src": str(picture), "x": 0, "y": 0,
                  "width": 640, "height": 360}]}]}
    plain = _cc.spec_view(specs, base_path=d, image_bytes={str(picture): blob})
    shared = _cc.spec_view(specs, base_path=d, image_bytes={str(picture): blob},
                           digests={str(picture): hashlib.sha256(blob).hexdigest()})
    check("runtime: 共享摘要不改缓存身份（同一份字节 → 同一个语义投影）", plain == shared)

    # ── 3) 资产 QC：判定复用 / 四类失效条件 ────────────────────────────────
    brief = d / "brief.yml"
    brief.write_text(_json.dumps({
        "audience": "investor", "decision": "approve",
        "slides": [{"id": "s01", "family": "cover", "title": "Runtime",
                    "asset_subject": "ceramic bowl"}]}), encoding="utf-8")
    plan, manifest = d / "plan.json", d / "asset_manifest.json"
    run_vao("plan", str(brief), "--out", str(plan), "--skeleton", str(d / "build.py"))
    run_vao("assets", str(brief), "--plan", str(plan), "--out", str(manifest),
            "--assets-dir", str(assets))
    entry = next(e for e in _aw.read_json(manifest)["assets"] if e.get("decision") == "generate")
    image = assets / pathlib.Path(entry["expected_filename"]).with_suffix(".jpg")
    Image.new("RGB", (1280, 800), (242, 240, 230)).save(image)

    qc_path = manifest.with_name(manifest.stem + ".qc.json")
    calls = {"n": 0}
    real_qc = _vao.image_qc if hasattr(_vao, "image_qc") else None
    import asset_prompt as _ap
    real_image_qc = _ap.image_qc

    def counted(*a, **k):
        calls["n"] += 1
        return real_image_qc(*a, **k)

    _ap.image_qc = counted
    try:
        first_report, _ = _vao._asset_qc_report(str(manifest), str(assets), phase="release",
                                                speed="fast")
        first_calls = calls["n"]
        second_report, _ = _vao._asset_qc_report(str(manifest), str(assets), phase="release",
                                                 speed="fast")
    finally:
        _ap.image_qc = real_image_qc
    check("runtime: 资产 QC 判定可复用（第二轮不再做像素测量）",
          first_calls >= 1 and calls["n"] == first_calls
          and (second_report.get("reuse") or {}).get("assets") == len(second_report["results"]),
          f"calls={calls['n']} reuse={second_report.get('reuse')}")

    # ── 3b) 字节按需读：热轮（判定复用 + 凭证带 sha256）一个字节都不读 ──────
    #      此前无条件读整批资产：热轮里 50MB 读进来没有任何消费者——
    #      判定看 size+mtime_ns，编译与核验消费凭证里的 sha256。
    reads = {"n": 0, "bytes": 0}
    real_read_bytes = _pathlib.Path.read_bytes

    def counted_read(self):
        data = real_read_bytes(self)
        if self.name == image.name:
            reads["n"] += 1
            reads["bytes"] += len(data)
        return data

    _pathlib.Path.read_bytes = counted_read
    try:
        hot_report, _ = _vao._asset_qc_report(str(manifest), str(assets), phase="release",
                                              speed="fast")
    finally:
        _pathlib.Path.read_bytes = real_read_bytes
    hot_item = (hot_report.get("results") or [{}])[0]
    check("runtime: 热轮不读资产字节（判定复用 + 凭证带 sha256 → 无消费者）",
          reads["n"] == 0 and bool((hot_item.get("witness") or {}).get("sha256"))
          and bool((hot_report.get("reuse") or {}).get("assets")),
          f"读 {reads['n']} 次 / {reads['bytes']} B")

    # ── 3c) 严格档相反：判据本身就是「现算的 sha256」→ 每次逐字节读数 ──────
    strict_reads = {"n": 0}

    def counted_strict(self):
        data = real_read_bytes(self)
        if self.name == image.name:
            strict_reads["n"] += 1
        return data

    _pathlib.Path.read_bytes = counted_strict
    try:
        strict_report, _ = _vao._asset_qc_report(str(manifest), str(assets), phase="release",
                                                 speed="strict")
    finally:
        _pathlib.Path.read_bytes = real_read_bytes
    check("runtime: 严格档仍逐字节读数（判据是现算 sha256，不靠凭证转抄）",
          strict_reads["n"] >= 1, f"读 {strict_reads['n']} 次")

    # 失效 1：图片字节变了 → 必须重测
    image.write_bytes(image.read_bytes() + b"\x00")
    calls["n"] = 0
    _ap.image_qc = counted
    try:
        third_report, _ = _vao._asset_qc_report(str(manifest), str(assets), phase="release",
                                                speed="fast")
    finally:
        _ap.image_qc = real_image_qc
    check("runtime: 图片字节变了 → 判定不复用（重新测量）",
          calls["n"] >= 1 and (third_report.get("reuse") or {}).get("assets", 0) == 0,
          f"calls={calls['n']} reuse={third_report.get('reuse')}")

    # 失效 2：判定输入变了 → 必须重测
    changed = _aw.read_json(manifest)
    for e in changed["assets"]:
        if e.get("decision") == "generate":
            e["safe_area"] = {"x": 0.55, "y": 0.1, "width": 0.35, "height": 0.8}
    manifest.write_text(_json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    calls["n"] = 0
    _ap.image_qc = counted
    try:
        fourth_report, _ = _vao._asset_qc_report(str(manifest), str(assets), phase="release",
                                                 speed="fast")
    finally:
        _ap.image_qc = real_image_qc
    check("runtime: 判定输入变了（safe_area）→ 判定不复用",
          calls["n"] >= 1 and (fourth_report.get("reuse") or {}).get("assets", 0) == 0,
          f"calls={calls['n']}")

    # 失效 3：档位不同 → 各档保留自己的判定（严格档还要整文件核对）
    strict_report, _ = _vao._asset_qc_report(str(manifest), str(assets), phase="release",
                                             speed="strict")
    check("runtime: 跨档位不复用判定（fast/strict 各留自己的像素口径）",
          (strict_report.get("reuse") or {}).get("assets", 0) == 0
          and (strict_report.get("pixel_profile") or {}).get("speed") == "strict")

    # ── 4) 预览：页面没变就不重画 ──────────────────────────────────────────
    page = {"id": "p1", "elements": [{"type": "text", "id": "t", "x": 80, "y": 80,
                                      "width": 600, "height": 80, "text": "Runtime",
                                      "size": 40, "color": "ink", "role": "title"}]}
    spec_one = {"canvas": {"width": 1280, "height": 720},
                "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111"}},
                "slides": [page]}
    preview_dir = d / "prev"
    stats_a: dict = {}
    within_a: list = []
    _ghost.ghost_deck(spec_one, preview_dir, supersample=1, png_compress_level=1,
                      images_out=within_a, stats=stats_a)
    stats_b: dict = {}
    within_b: list = []
    _ghost.ghost_deck(spec_one, preview_dir, supersample=1, png_compress_level=1,
                      images_out=within_b, stats=stats_b)
    cache_files = sorted((preview_dir / _ghost.PAGE_CACHE_DIR).glob("*.png"))
    check("runtime: 页面没变不重画（逐页缓存命中，且像素与首轮一致）",
          stats_a.get("rendered") == 1 and stats_b.get("cached") == 1
          and len(cache_files) == 1 and within_a[0].tobytes() == within_b[0].tobytes(),
          f"a={stats_a} b={stats_b} files={len(cache_files)}")

    # 三页稿件：改中间一页 → 只应重画那一页
    def _page(pid, text):
        return {**page, "id": pid,
                "elements": [{**page["elements"][0], "text": text}]}

    spec_three = {"canvas": spec_one["canvas"], "theme": spec_one["theme"],
                  "slides": [_page("p1", "A"), _page("p2", "B"), _page("p3", "C")]}
    _ghost.ghost_deck(spec_three, preview_dir, supersample=1, png_compress_level=1)
    spec_changed = _json.loads(_json.dumps(spec_three))
    spec_changed["slides"][1]["elements"][0]["text"] = "B 改过了"
    stats_c: dict = {}
    _ghost.ghost_deck(spec_changed, preview_dir, supersample=1, png_compress_level=1, stats=stats_c)
    check("runtime: 改一页只重画那一页（同一轮里其余页命中缓存）",
          stats_c.get("rendered") == 1 and stats_c.get("cached") == 2, str(stats_c))

    # 联络表：页图的纯函数——页图没变就复制上一轮那张（不是重贴一遍）
    sheet_dir = d / "sheet"
    (sheet_dir / "pages").mkdir(parents=True, exist_ok=True)
    for stale in (sheet_dir / "pages").glob("*.png"):
        stale.unlink()
    sheet_a: dict = {}
    info_a = _vao._ghost(spec_three, sheet_dir, base_path=d, speed="strict")
    sheet_a["sha"] = _hashlib2.sha256(_pathlib.Path(info_a["contact_sheet"]).read_bytes()).hexdigest()
    sheet_a["cached"] = info_a.get("contact_sheet_cached")
    info_b = _vao._ghost(spec_three, sheet_dir, base_path=d, speed="strict")
    sheet_b = _hashlib2.sha256(_pathlib.Path(info_b["contact_sheet"]).read_bytes()).hexdigest()
    check("runtime: 联络表是页图的纯函数（页图没变 → 复制上一轮，字节一致）",
          sheet_a["cached"] is False and info_b.get("contact_sheet_cached") is True
          and sheet_a["sha"] == sheet_b,
          f"首轮 重贴={sheet_a['cached']} · 二轮 复制={info_b.get('contact_sheet_cached')}"
          f" · {sheet_b[:12]}…")

    # 失效：渲染口径变了（超采样档）→ 缓存不得冒充另一种像素
    stats_d: dict = {}
    _ghost.ghost_deck(spec_changed, preview_dir, supersample=2, png_compress_level=6, stats=stats_d)
    check("runtime: 渲染口径变了（超采样/压缩）→ 不复用旧页图",
          stats_d.get("cached", 0) == 0 and stats_d.get("rendered") == 3, str(stats_d))

    # ── 5) 证据里看得到「省了什么」─────────────────────────────────────────
    hot_spec = {"canvas": spec_one["canvas"], "theme": spec_one["theme"],
                "slides": spec_changed["slides"]}
    ghost_info = _vao._ghost(hot_spec, d / "prev2", base_path=d, speed="fast", limit=4)
    # 同一份稿子再跑一次：这一轮一页都没画（全部命中页缓存）。以前这里报成「画了 3 页」——
    # `stats.get("rendered", len(paths))` 在全命中时拿默认值，把「没画」记成了「全画」。
    ghost_hot = _vao._ghost(hot_spec, d / "prev2", base_path=d, speed="fast", limit=4)
    check("runtime: 预览证据写明这一轮画了几页 / 命中几页"
          "（全部命中时不许报成「都画了」）",
          isinstance(ghost_info.get("pages_drawn"), int)
          and isinstance(ghost_info.get("pages_from_cache"), int)
          and ghost_info["pages_drawn"] + ghost_info["pages_from_cache"] == ghost_info["count"]
          and ghost_hot["pages_drawn"] == 0
          and ghost_hot["pages_from_cache"] == ghost_hot["count"]
          and ghost_hot["pages_drawn_numbers"] == [],
          f"首轮 {ghost_info['pages_drawn']}/{ghost_info['pages_from_cache']}"
          f" · 二轮 {ghost_hot['pages_drawn']}/{ghost_hot['pages_from_cache']}")


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
                                                 "energy": "medium"},
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
        check_production_path(work)
        check_audit_fixes(work)
        check_editorial_chart_defaults(work)
        check_prompt_discipline()
        check_asset_role_separation()
        check_anti_regression()
        check_boundary_negatives(work)
        check_speed_profile(work)
        check_runtime_reuse(work)
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
