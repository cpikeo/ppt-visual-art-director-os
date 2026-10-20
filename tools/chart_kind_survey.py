# -*- coding: utf-8 -*-
"""chart_kind 等价性普查：哪些名字真的画同一张图？

用途：合并 alias 之前先量一次。对每个 `chart_kind` 用同一份载荷编译 + 预览，
分别对 **PPTX 字节**（产物）与 **预览 PNG 字节**（证据）取 SHA-256：

  · 两个 kind 的 (pptx, png) 都相同 → 真同义词，可以合并成一条；
  · PPTX 相同、PNG 不同 → 产物一样、预览分叉（更该修，不是合并能解决的）；
  · PPTX 不同 → 不是别名，别硬合（差异要么来自渲染，要么来自默认选项）。

用法：
    python3 tools/chart_kind_survey.py [--scripts DIR] [--json out.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

# 每类载荷形态各一份：value / rows / points / layers
VALUE_KINDS = {"kpi", "executive_kpi", "big_number"}
POINT_KINDS = {"matrix"}
LAYER_KINDS = {"architecture"}

ROWS = [{"label": "研发", "value": 42}, {"label": "交付", "value": 28},
        {"label": "运营", "value": 19}]
POINTS = [{"label": "甲", "x": 0.2, "y": 0.8}, {"label": "乙", "x": 0.6, "y": 0.4},
          {"label": "丙", "x": 0.9, "y": 0.6}]
LAYERS = ["接入层", "服务层", "数据层"]


def payload(kind: str) -> dict:
    if kind in VALUE_KINDS:
        return {"value": "61%", "label": "复购率", "unit": "%",
                "source": "用户台账", "period": "2026 H1", "basis": "去重用户"}
    if kind in POINT_KINDS:
        return {"points": POINTS, "source": "调研", "period": "2026 H1", "basis": "样本 n=120"}
    if kind in LAYER_KINDS:
        return {"layers": LAYERS, "source": "架构评审", "period": "2026 Q2", "basis": "现行版本"}
    return {"data": ROWS, "unit": "项", "source": "试点台账",
            "period": "2026 H1", "basis": "按类别计数"}


def spec_for(kind: str) -> dict:
    element = {"id": "c", "type": "chart", "chart_kind": kind,
               "x": 80, "y": 120, "width": 900, "height": 420,
               "label_size": 20, "value_size": 16, **payload(kind)}
    return {"canvas": {"width": 1280, "height": 720},
            "theme": {"colors": {"background": "#FFFFFF", "ink": "#141414",
                                 "muted": "#8B8883", "primary": "#141414",
                                 "secondary": "#8B8883", "accent": "#A2563F"},
                      "fonts": {"cn": "Noto Serif CJK SC", "latin": "Noto Serif CJK SC"}},
            "slides": [{"id": "s1", "elements": [element]}]}


def preview_png(spec: dict, kind: str, tmp: Path) -> bytes:
    """预览：与生产同一条路径（ghost_page），只截图表区域。"""
    import ghost
    img = ghost.ghost_page(spec["slides"][0], spec, scale=1, supersample=1)
    out = tmp / f"{kind}.png"
    img.convert("RGB").save(out)
    return out.read_bytes()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts", default=str(Path(__file__).resolve().parents[1] / "scripts"))
    ap.add_argument("--json", default="")
    ap.add_argument("--outdir", default="",
                    help="把每个 kind 的 pptx/png 留在该目录（前后对照用）")
    ap.add_argument("--compare", default="",
                    help="与基线 JSON 对拍：逐 kind 比 pptx/png 哈希与形状数")
    args = ap.parse_args()
    sys.path.insert(0, args.scripts)

    from compiler import compile_deck
    import primitives
    from primitives import CHART_SPEC
    # 本工具要能对着**旧版检出**跑基线（--scripts 指向另一个工作树）：旧版的合法
    # 输入集合里还有退役名，新版没有了。两版都只遍历「该版能编译的全部 kind」，
    # 对照才成立（旧版 26 行、新版 19 行，对拍按行名匹配）。
    CHART_KINDS = getattr(primitives, "CHART_KINDS", frozenset(CHART_SPEC))

    tmp = Path(tempfile.mkdtemp(prefix="chart-kind-"))
    outdir = Path(args.outdir).resolve() if args.outdir else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    # 遍历**合法输入**（canonical + 旧名）。只跑 canonical 会漏掉「旧名归一后
    # 是否仍与旧产物逐字节一致」这个问题——而那正是合并的安全边界。
    for kind in sorted(CHART_KINDS):
        canonical = kind
        spec = spec_for(kind)
        pptx = tmp / f"{kind}.pptx"
        report = compile_deck(spec, pptx)
        blob = pptx.read_bytes()
        png = preview_png(spec, kind, tmp)
        if outdir:
            (outdir / f"{kind}.pptx").write_bytes(blob)
            (outdir / f"{kind}.png").write_bytes(png)
        rows.append({
            "kind": kind,
            "canonical": canonical,
            "renderer": CHART_SPEC[canonical]["renderer"],
            "pptx_sha": hashlib.sha256(blob).hexdigest()[:16],
            "png_sha": hashlib.sha256(png).hexdigest()[:16],
            "warnings": report.get("warnings") or [],
            "shapes": len(__import__("pptx").Presentation(str(pptx)).slides[0].shapes),
        })

    # 按 (pptx, png) 分组
    groups: dict[tuple[str, str], list[str]] = {}
    pptx_only: dict[str, list[str]] = {}
    for r in rows:
        groups.setdefault((r["pptx_sha"], r["png_sha"]), []).append(r["kind"])
        pptx_only.setdefault(r["pptx_sha"], []).append(r["kind"])

    print(f"{'kind':18s} {'renderer':7s} {'pptx':16s} {'preview':16s} shapes  warnings")
    for r in rows:
        print(f"{r['kind']:18s} {r['renderer']:7s} {r['pptx_sha']:16s} "
              f"{r['png_sha']:16s} {r['shapes']:6d}  {'; '.join(r['warnings'])[:50]}")

    print("\n产物与预览都相同（真同义词）:")
    for (p, g), kinds in groups.items():
        if len(kinds) > 1:
            print(f"  pptx {p} · png {g} :: {' = '.join(kinds)}")
    print("\n产物相同、预览不同（预览分叉，需先修）:")
    for p, kinds in pptx_only.items():
        split = {g: ks for (pp, g), ks in groups.items() if pp == p}
        if len(kinds) > 1 and len(split) > 1:
            print(f"  pptx {p} :: " + " | ".join(f"{g}: {'='.join(ks)}"
                                                 for g, ks in split.items()))

    if args.compare:
        base = {r["kind"]: r for r in json.loads(Path(args.compare).read_text(encoding="utf-8"))}
        print(f"\n对拍基线 {args.compare}")
        print(f"{'kind':18s}{'→canonical':12s}{'产物':8s}{'预览':8s}{'形状':12s}")
        bad = 0
        for r in rows:
            b = base.get(r["kind"])
            if b is None:
                print(f"{r['kind']:18s}{r['canonical']:12s}（基线无此项）")
                continue
            same_p = b["pptx_sha"] == r["pptx_sha"]
            same_g = b["png_sha"] == r["png_sha"]
            bad += not (same_p and same_g)
            print(f"{r['kind']:18s}{r['canonical']:12s}"
                  f"{'一致' if same_p else '变了':8s}{'一致' if same_g else '变了':8s}"
                  f"{str(b.get('shapes')) + '→' + str(r.get('shapes')):12s}")
        print(f"结论：{len(rows) - bad}/{len(rows)} 个写法产物与预览均未变")

    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    print("工作目录:", tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
