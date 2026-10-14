"""Same-input A/B evidence, not an aesthetic benchmark or an Office renderer.
Usage: python evaluation/font_fidelity/reproduce.py --before /path/to/baseline --after . --out /path/to/evidence --repeat 5
Requires only repository dependencies. Outputs synthetic seven-page specimen, raw CLI records,
PPTX package audit and structural previews. Each repetition uses a new application-cache directory;
OS disk caches are NOT flushed. Human/LLM authorship and external asset generation are NOT timed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time
import zipfile
from xml.etree import ElementTree as ET


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def fixture(root):
    # Original synthetic light target: tests image placement, not photographic credibility.
    from PIL import Image
    import numpy as np
    y, x = np.mgrid[0:1080, 0:1920]
    light = np.exp(-(((x - 1260) / 420) ** 2 + ((y - 440) / 480) ** 2))
    rgb = np.stack([35 + 115 * light, 54 + 125 * light, 73 + 105 * light], axis=-1)
    image = root / "synthetic-light.png"
    Image.fromarray(rgb.astype("uint8")).save(image)
    titles = ["先验收，再发布", "先明确证据的边界", "结构通过，不等于视觉通过",
              "返工集中在文字与关系", "文字必须完整承载主张", "图像与文字各有职责", "请批准目标环境复核"]
    contents = ["编辑级演示验收 · 合成测试样本", "看得见的证据，才允许支撑交付结论。",
                "代码测试确认可执行；结构预览确认方向；目标环境渲染确认实际呈现。",
                "合成问题台账：文字 12 项，图文关系 8 项，来源 4 项。",
                "试点周期 18 个月，预算 1.8 亿元；API v2.1 与中文同排。请将数字与单位作为完整信息读取。",
                "合成光照标靶只用于检验图像裁切与图文分离，不是现场证词。",
                "下一步：在目标 PowerPoint 打开原稿，核对字体、实际折行与投影可读性。"]
    brief = {"audience": "演示设计与质量负责人，现场评审", "decision": "批准目标 PowerPoint 复核",
             "tension": "不能用结构预览替代交付环境证据", "slides": []}
    for i, (title, content) in enumerate(zip(titles, contents), 1):
        brief["slides"].append({"id": f"s{i:02}", "title": title, "content": content, "asset": "none"})
    brief["slides"][5].update(asset="reuse", asset_role="illustration", asset_function="context",
        safe_area={}, background="#233649", asset_subject="Synthetic light target, not a photograph",
        asset_source={"kind": "original", "path": str(image), "source": "Original synthetic test target made by reproduce.py; no real scene or client data"})
    write(root / "brief.json", brief)
    return titles, contents


def spec(titles, contents, aid):
    def text(eid, value, x, y, w, h, size=26, **kw):
        return dict(id=eid, type="text", text=value, x=x, y=y, width=w, height=h,
                    size=size, color="ink", role="body", line_height=1.5, **kw)
    slides = []
    for i in range(7):
        elements = [text("folio", f"{i+1:02} / 07", 1096, 32, 136, 40, 18),
                    text("source", "合成测试样本 · 非客户成稿 / 非 Office 渲染证据", 48, 664, 1184, 40, 18)]
        elements[-1]["role"] = "source"
        if i in (0, 6):
            elements += [text("title", titles[i], 80, 192, 1120, 144, 64, bold=True),
                         text("body", contents[i], 84, 384, 1020, 120, 28)]
        elif i == 1:
            elements += [text("chapter", "01", 80, 132, 200, 152, 88, bold=True),
                         text("title", titles[i], 80, 340, 1100, 96, 48),
                         text("body", contents[i], 84, 488, 1100, 80, 28)]
        else:
            elements += [text("title", titles[i], 48, 88, 1184, 112, 44, bold=True)]
            if i == 2:
                elements += [text("lead", "结构 PASS", 48, 256, 456, 104, 54, bold=True),
                             text("body", "可执行、可检查、可复现。\n但字体回退与实际折行，\n仍需目标环境的证据。", 608, 260, 600, 260, 30)]
            elif i == 3:
                elements += [dict(id="chart", type="chart", chart_kind="column", x=48, y=240,
                    width=1184, height=368, role="focus", categories=["文字", "图文关系", "来源"],
                    series=[{"name": "问题数量", "values": [12, 8, 4]}], metric="合成问题数",
                    source="合成问题台账，不代表真实项目", unit="项", period="测试批次 A", basis="单类归因", show_values=True)]
            elif i == 4:
                elements += [text("body", "“先验证，再交付。”\n试点周期 18 个月，预算 1.8 亿元。\nAPI v2.1 与中文同排；\n「标点、数字与单位」完整可读。", 48, 248, 744, 340, 30, font="latin"),
                             text("aside", "骨、直、令、遍\n中文地域字形探针\nABC / 2026", 864, 264, 344, 256, 30),
                             text("latin", "Evidence before release", 864, 548, 344, 64, 22, family="Georgia")]
            elif i == 5:
                elements += [dict(id="image", type="image", asset_id=aid, x=48, y=240, width=704,
                                  height=396, fit="contain", role="witness"),
                             text("body", "图像区\n保留完整光照标靶。\n\n文字区\n不压图，不冒充现场证据。", 824, 252, 384, 376, 26)]
        for e in elements:
            if e["id"] == "title":
                e["role"] = "title"
        slides.append({"id": f"s{i+1:02}", "source_zone": {"x":48,"y":660,"width":1184,"height":48},
                       "page_intent": {"insight": titles[i], "focus": "title"}, "elements": elements})
    return {"canvas": {"width":1280,"height":720}, "theme": {
        "fonts": {"cn":"Noto Serif CJK SC","latin":"Arial"},
        "colors": {"background":"#F4F6F8","ink":"#182B3A","muted":"#536574",
                   "primary":"#233649","secondary":"#7B919E","accent":"#BB5D26"}}, "slides":slides}


def call(repo, args, log, expected=0):
    start = time.perf_counter()
    p = subprocess.run([sys.executable, str(repo / "scripts/vao.py"), *map(str,args)],
                       capture_output=True, text=True, encoding="utf-8", cwd=repo)
    wall = (time.perf_counter()-start)*1000
    record = {"args": list(map(str,args)), "wall_ms": wall, "returncode": p.returncode,
              "stdout":p.stdout, "stderr":p.stderr}
    write(log,record)
    if p.returncode != expected:
        raise RuntimeError(f"Failed; retained evidence: {log}\n{p.stdout}\n{p.stderr}")
    result = json.loads(p.stdout)
    return {"wall_ms":wall, "timing":result.get("timing", result.get("performance",{}))}


def audit(path):
    ns={"a":"http://schemas.openxmlformats.org/drawingml/2006/main",
        "p":"http://schemas.openxmlformats.org/presentationml/2006/main"}
    with zipfile.ZipFile(path) as z:
        names=sorted(n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml"))
        pages=[]
        for name in names:
            xml=ET.fromstring(z.read(name))
            pages.append({"name":name,"native_text_bodies":len(xml.findall(".//p:txBody",ns)),
                          "pictures":len(xml.findall(".//p:pic",ns)),
                          "runs":len(xml.findall(".//a:r",ns))})
        return {"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"pages":pages,
                "native_charts":len([n for n in z.namelist() if n.startswith("ppt/charts/chart") and n.endswith(".xml")]),
                "embedded_workbooks":len([n for n in z.namelist() if n.startswith("ppt/embeddings/")]),
                "xml_sha256":{n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.endswith(".xml")},
                "boundary":"OOXML native object audit only; no PowerPoint opening/editing verified"}


def cache_scenarios(before, after, root, titles, contents):
    """Upgrade invalidation, single-page change and strict tamper repair, via the same CLI."""
    import os
    d=root/"cache-checks"; d.mkdir(parents=True, exist_ok=False)
    call(before,["plan",root/"brief.json","--out",d/"plan.json","--json"],d/"plan-call.json")
    manifest=d/"asset_manifest.json"
    aid=json.loads(manifest.read_text())["assets"][0]["asset_id"]
    build=spec(titles,contents,aid); write(d/"build.json",build)
    args=["check",d/"build.json",d/"deck.pptx","--mode","release","--speed","strict","--assets-manifest",manifest,"--json"]
    call(before,args,d/"baseline.json")
    old_sha=hashlib.sha256((d/"deck.pptx").read_bytes()).hexdigest()
    upgrade=call(after,args,d/"upgrade.json")["timing"]
    compiler_unchanged = all((before/"scripts"/f).read_bytes() == (after/"scripts"/f).read_bytes()
                             for f in ("compiler.py", "primitives.py"))
    assert (upgrade["compile_ms"] == 0) == compiler_unchanged
    assert upgrade["render_pages_drawn"] == 7
    if compiler_unchanged:
        assert hashlib.sha256((d/"deck.pptx").read_bytes()).hexdigest() == old_sha
    warm=call(after,args,d/"warm.json")["timing"]
    assert warm["compile_ms"] == 0 and warm["render_pages_drawn"] == 0
    build["slides"][4]["elements"][2]["text"]="文字必须完整承载判断"
    write(d/"build.json",build)
    changed=call(after,args,d/"one-page-change.json")["timing"]
    assert changed["compile_ms"] > 0 and changed["render_pages_drawn"] == 1 and changed["render_pages_cached"] == 6
    page=d/"deck_preview/ghost-05.png"; stat=page.stat(); blob=bytearray(page.read_bytes())
    blob[-1] ^= 1; page.write_bytes(blob); os.utime(page,ns=(stat.st_atime_ns,stat.st_mtime_ns))
    repaired=call(after,args,d/"tampered-preview.json")["timing"]
    assert repaired["compile_ms"] == 0 and not repaired["render_bundle_reused"]
    assert repaired["render_pages_cached"] == 7
    # Fast with a two-page evidence budget still checks all seven pages.
    build["slides"][4]["elements"][3]["height"]=8
    write(d/"build.json",build)
    fast_args=["check",d/"build.json",d/"deck.pptx","--mode","release","--speed","fast",
               "--ghost-pages","2","--assets-manifest",manifest,"--json"]
    blocked=call(after,fast_args,d/"fast-hard-error.json",expected=2)
    result=json.loads(json.loads((d/"fast-hard-error.json").read_text())["stdout"])
    assert "TEXT_OVERFLOW" in result["failure_codes"] and blocked["timing"]["compile_ms"] == 0
    write(d/"assertions.json",{"upgrade_obeys_compiler_scope":True,"compiler_unchanged":compiler_unchanged,
        "warm_reuses_all":True,
        "one_page_change_redraws_one":True,"strict_detects_same_stat_tampering":True,
        "fast_checks_non_preview_capacity":True})


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--before",type=Path,required=True); p.add_argument("--after",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True); p.add_argument("--repeat",type=int,default=5)
    a=p.parse_args(); root=a.out.resolve(); root.mkdir(parents=True,exist_ok=True)
    if (root/"runs").exists():
        raise SystemExit("Use a fresh output directory: runs already exists (do not call warm caches cold).")
    titles,contents=fixture(root)
    rows=[]
    for i in range(a.repeat):
        order=("before","after") if i%2==0 else ("after","before")
        for label in order:
            repo=getattr(a,label).resolve(); d=root/"runs"/f"{label}-{i}"; d.mkdir(parents=True)
            plan=call(repo,["plan",root/"brief.json","--out",d/"plan.json","--skeleton",d/"skeleton.py","--json"],d/"plan-call.json")
            manifest=d/"asset_manifest.json"
            aid=json.loads(manifest.read_text())["assets"][0]["asset_id"]
            write(d/"build.json",spec(titles,contents,aid))
            args=["check",d/"build.json",d/"deck.pptx","--mode","release","--speed","strict","--assets-manifest",manifest,"--json"]
            cold=call(repo,args,d/"cold-call.json")
            warm=call(repo,args,d/"warm-call.json")
            row={"label":label,"iteration":i,"plan":plan,"cold":cold,"warm":warm,
                 "automation_wall_ms":plan["wall_ms"]+cold["wall_ms"]}
            rows.append(row); write(root/"measurements.json",rows)
            if i==0: write(d/"pptx-audit.json",audit(d/"deck.pptx"))
    summary={}
    for label in ("before","after"):
        batch=[r for r in rows if r["label"]==label]
        summary[label]={"automation_wall_ms":statistics.median(r["automation_wall_ms"] for r in batch)}
        for stage in ("plan","cold","warm"):
            summary[label][stage]={"wall_ms":statistics.median(r[stage]["wall_ms"] for r in batch),
                "timing":{k:statistics.median(r[stage]["timing"].get(k,0) for r in batch)
                          for k,v in batch[0][stage]["timing"].items() if isinstance(v,(int,float)) and not isinstance(v,bool)}}
    write(root/"summary.json",summary)
    write(root/"environment.json",{"platform":platform.platform(),"python":sys.version,
        "before":str(a.before.resolve()),"after":str(a.after.resolve()),"repetitions":a.repeat,
        "baseline_commit":"8b3d81e6aa05eb7ebeb1f06e096fc98e0620f0a5",
        "method":"alternating order, new application caches, warm OS caches, fresh process per CLI; author fixture assembly untimed; no AI/Office"})
    cache_scenarios(a.before.resolve(), a.after.resolve(), root, titles, contents)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
