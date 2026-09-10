# -*- coding: utf-8 -*-
"""
Layer -1.5 · Layout Search（V3 · 版式智能搜索——Layout Grammar，不是组件库）

职责：同一个页面意图，生成 N 个**结构候选**并打分排序——顶级设计师脑中的
「快速比较」，变成确定性的 spec 级搜索。成本 ~1ms/候选（不渲染、不编译）。

为什么是 Grammar 不是组件：
    组件库（Hero01/Chart02）= 固定模板 → 千页一面；
    Layout Grammar = 支配性 / 负空间 / 视觉锚点 / 阅读路径 四要素的组合规则
    → 按信息重量、焦点、数据关系**参数化生成**几何，每次都为当前内容服务。

评分五维（确定性）：
    hierarchy   焦点尺度优势能否成立（dominance 比例）
    whitespace  负空间是否承担功能（occupancy 落在意图密度带内）
    anchor      是否天然产生记忆锚点（≥40px statement / 图表高亮位）
    rhythm      对跨页呼吸的贡献（与意图 density 的匹配）
    brand_fit   与 Design DNA 的 layout_grammar / forbidden 匹配

用法：
    from layout_search import search
    cands = search(page_intent, content_profile, dna=dna_recalled, n=3)
    # cands[0] = {archetype, grammar, score, breakdown, elements(骨架几何), rationale}
"""
from __future__ import annotations

import time
from typing import Any

from primitives import DEFAULT_WIDTH, DEFAULT_HEIGHT
from art_critic import STATEMENT_SIZE, _content_occupancy
from design_intelligence import DENSITY_BANDS

_M = 48            # 版心安全边距（8 网格倍数）
_W, _H = DEFAULT_WIDTH, DEFAULT_HEIGHT


# ════════════════════════════════════════════════════════════════════════
# Layout Grammar 原型（参数化生成器：dominance / negative_space / anchor / path）
# ════════════════════════════════════════════════════════════════════════
def _snap(v: float) -> int:
    return int(v // 8 * 8)


ARCHETYPES: dict[str, dict] = {
    "statement_center_stage": {
        "grammar": "单一宣言居中 + 放射负空间（dominance 0.8 / path: 单点）",
        "traits": {"dominance": 0.85, "anchor": "center statement",
                   "path": "single", "whitespace": "radial"},
        "fit": {"families": {"HERO", "CLOSING", "STATEMENT", "SECTION"},
                "dna": ["statement stage", "cinematic", "宣言", "极简"]},
    },
    "editorial_asymmetric": {
        "grammar": "左文右证非对称（40/60 分割 + 发丝线，dominance 0.5 / path: Z 型）",
        "traits": {"dominance": 0.50, "anchor": "left column head",
                   "path": "z-shape", "whitespace": "columnar"},
        "fit": {"families": {"STORY", "EVIDENCE", "STATEMENT", "COMPARISON"},
                "dna": ["editorial asymmetric", "杂志", "editorial"]},
    },
    "full_width_evidence": {
        "grammar": "结论在上 + 通栏证据在中 + 统计行在下（dominance 0.4 / path: 自上而下）",
        "traits": {"dominance": 0.40, "anchor": "chart highlight",
                   "path": "top-down", "whitespace": "horizontal bands"},
        "fit": {"families": {"DATA", "EVIDENCE", "PROCESS"},
                "dna": ["FT editorial", "exhibit", "通栏"]},
    },
    "split_emphasis": {
        "grammar": "大数字左 / 证据右（dominance 0.6 / path: 左右互证）",
        "traits": {"dominance": 0.60, "anchor": "big number",
                   "path": "left-right", "whitespace": "split"},
        "fit": {"families": {"DATA", "EVIDENCE", "COMPARISON"},
                "dna": ["大数字", "keynote", "contrast"]},
    },
    "cinematic_stage": {
        "grammar": "背景画心 + overlay 保护 + 单一文字层（dominance 0.9 / path: 沉浸）",
        "traits": {"dominance": 0.90, "anchor": "image hero",
                   "path": "immersive", "whitespace": "in-image"},
        "fit": {"families": {"HERO", "STORY", "CLOSING"},
                "dna": ["cinematic stage", "画心", "沉浸"]},
    },
    "quiet_progression": {
        "grammar": "横向步骤/时间轴 + 大留白上下（dominance 0.35 / path: 左→右）",
        "traits": {"dominance": 0.35, "anchor": "progression node",
                   "path": "left-to-right", "whitespace": "banded"},
        "fit": {"families": {"PROCESS", "SECTION", "STRUCTURE"},
                "dna": ["timeline", "步骤", "progression"]},
    },
}


def _synthesize(arch: str, profile: dict) -> list[dict]:
    """原型 × 内容画像 → 骨架几何（8 网格对齐；id 语义固定，尺寸按内容参数化）。"""
    has_title = bool(profile.get("title"))
    has_lead = bool(profile.get("lead"))
    has_chart = bool(profile.get("chart"))
    has_stats = bool(profile.get("stats"))
    els: list[dict] = []

    if arch == "statement_center_stage":
        y = _snap(_H * 0.38)
        els.append({"type": "text", "id": "statement", "x": _snap(_W * 0.14),
                    "y": y, "width": _snap(_W * 0.72), "height": 96,
                    "size": 64, "align": "center"})
        if has_lead:
            els.append({"type": "text", "id": "lead", "x": _snap(_W * 0.30),
                        "y": y + 136, "width": _snap(_W * 0.40), "height": 56,
                        "size": 16, "align": "center"})
    elif arch == "editorial_asymmetric":
        col = _snap(_W * 0.40)
        if has_title:
            els.append({"type": "text", "id": "title", "x": _M, "y": 120,
                        "width": col - _M - 24, "height": 64, "size": 40})
        if has_lead:
            els.append({"type": "text", "id": "lead", "x": _M, "y": 208,
                        "width": col - _M - 24, "height": 96, "size": 16})
        if has_chart:
            els.append({"type": "chart", "id": "chart", "x": col + 24, "y": 120,
                        "width": _W - _M - col - 24, "height": 440})
        if has_stats:
            els.append({"type": "text", "id": "stats", "x": _M, "y": 552,
                        "width": col - _M - 24, "height": 56, "size": 32})
    elif arch == "full_width_evidence":
        if has_title:
            els.append({"type": "text", "id": "title", "x": _M, "y": 104,
                        "width": 880, "height": 64, "size": 40})
        if has_lead:
            els.append({"type": "text", "id": "lead", "x": _M, "y": 184,
                        "width": 600, "height": 64, "size": 16})
        if has_chart:
            h = 328 if has_stats else 408
            els.append({"type": "chart", "id": "chart", "x": _M, "y": 264,
                        "width": _W - 2 * _M, "height": h})
        if has_stats:
            els.append({"type": "text", "id": "stats", "x": _M, "y": 616,
                        "width": _W - 2 * _M, "height": 56, "size": 40})
    elif arch == "split_emphasis":
        if has_title:
            els.append({"type": "text", "id": "title", "x": _M, "y": 104,
                        "width": 880, "height": 64, "size": 32})
        els.append({"type": "text", "id": "big_number", "x": _M, "y": 240,
                    "width": _snap(_W * 0.36), "height": 160, "size": 96})
        if has_chart:
            els.append({"type": "chart", "id": "chart", "x": _snap(_W * 0.42),
                        "y": 240, "width": _W - _M - _snap(_W * 0.42), "height": 368})
        if has_stats:
            els.append({"type": "text", "id": "stats", "x": _M, "y": 608,
                        "width": _W - 2 * _M, "height": 48, "size": 24})
    elif arch == "cinematic_stage":
        els.append({"type": "image", "id": "backdrop", "layer": "background",
                    "x": 0, "y": 0, "width": _W, "height": _H})
        if has_title:
            els.append({"type": "text", "id": "title", "x": _M, "y": _snap(_H * 0.42),
                        "width": _W - 2 * _M, "height": 96, "size": 56})
        if has_lead:
            els.append({"type": "text", "id": "lead", "x": _M, "y": _snap(_H * 0.42) + 120,
                        "width": 600, "height": 48, "size": 18})
    elif arch == "quiet_progression":
        if has_title:
            els.append({"type": "text", "id": "title", "x": _M, "y": 104,
                        "width": 880, "height": 64, "size": 40})
        if has_lead:
            els.append({"type": "text", "id": "lead", "x": _M, "y": 184,
                        "width": 600, "height": 48, "size": 16})
        if has_chart:
            els.append({"type": "chart", "id": "chart", "x": _M, "y": 328,
                        "width": _W - 2 * _M, "height": 200})
    return els


def _score(cand_els: list[dict], arch: str, intent: dict, profile: dict,
           dna: dict | None) -> dict:
    """候选骨架 → 五维打分（0–1，确定性）。"""
    spec_traits = ARCHETYPES[arch]["traits"]
    sizes = [float(e.get("size") or 0) for e in cand_els if e.get("type") == "text"]
    occ = _content_occupancy(cand_els, _W, _H)

    # hierarchy：焦点尺度优势（最大字 vs 次大字的比例映射）
    if len(sizes) >= 2:
        ratio = max(sizes) / max(1e-6, sorted(sizes)[-2])
        hierarchy = min(1.0, (ratio - 1.0) / 1.25 + 0.5)     # 1.25× ≈ 0.74
    else:
        hierarchy = 0.9                                        # 单一文本层天然纯粹

    # whitespace：占用是否落进意图密度带（越居中越高）
    band = DENSITY_BANDS.get(str(intent.get("density") or "sparse"), (0.0, 0.60))
    mid = (band[0] + band[1]) / 2
    span = max(0.08, (band[1] - band[0]) / 2)
    whitespace = max(0.0, 1.0 - abs(occ - mid) / (span * 2.2))

    # anchor：骨架是否天然含锚点（≥40px statement / 画心 / 图表位）
    anchor = (1.0 if any(s >= STATEMENT_SIZE for s in sizes)
              or any(e.get("layer") == "background" for e in cand_els)
              or any(e.get("type") == "chart" for e in cand_els) else 0.2)

    # rhythm：dominance 与 energy 的匹配（高能量页要高支配性，低能量页要安静）
    energy = str(intent.get("energy") or "medium")
    dom = float(spec_traits["dominance"])
    want = {"high": 0.75, "medium": 0.5, "low": 0.3}[energy]
    rhythm = max(0.0, 1.0 - abs(dom - want) / 0.6)

    # brand_fit：DNA layout_grammar 关键词命中 + forbidden 规避
    fit = 0.55
    if dna:
        gram = str(dna.get("layout_grammar") or "").lower()
        hits = sum(1 for kw in ARCHETYPES[arch]["fit"]["dna"] if kw.lower() in gram)
        fit = min(1.0, 0.45 + 0.25 * hits)
        forbidden = [str(f).lower() for f in (dna.get("forbidden") or [])]
        if any(f in ARCHETYPES[arch]["grammar"].lower() for f in forbidden):
            fit = max(0.0, fit - 0.4)
    total = round((hierarchy * 0.25 + whitespace * 0.2 + anchor * 0.2
                   + rhythm * 0.15 + fit * 0.2) * 100, 1)
    return {"score": total,
            "breakdown": {"hierarchy": round(hierarchy, 2),
                          "whitespace": round(whitespace, 2),
                          "anchor": round(anchor, 2),
                          "rhythm": round(rhythm, 2),
                          "brand_fit": round(fit, 2),
                          "est_occupancy": round(occ, 2)}}


def search(intent: dict, profile: dict | None = None,
           dna: dict | None = None, n: int = 3) -> list[dict]:
    """页面意图 + 内容画像 → Top-N 结构候选（确定性，spec 级，~1ms/候选）。

    profile: {title:bool, lead:bool, chart:bool, stats:bool}（缺省按意图推断）
    dna: recall_dna(brief)["dna"]——品牌契合度由此而来
    返回按总分降序：[{archetype, grammar, score, breakdown, elements, rationale}]
    """
    t0 = time.time()
    profile = dict(profile or {})
    family = str(intent.get("page_family") or "").upper()
    profile.setdefault("title", True)
    profile.setdefault("lead", family not in ("HERO", "CLOSING"))
    profile.setdefault("chart", family in ("DATA", "EVIDENCE", "PROCESS",
                                           "COMPARISON", "STRUCTURE"))
    profile.setdefault("stats", family == "DATA")
    cands = []
    for arch, meta in ARCHETYPES.items():
        fam_fit = family in meta["fit"]["families"] if family else True
        els = _synthesize(arch, profile)
        sc = _score(els, arch, intent, profile, dna)
        cands.append({
            "archetype": arch,
            "grammar": meta["grammar"],
            "family_fit": fam_fit,
            "score": sc["score"] + (6.0 if fam_fit else 0.0),
            "breakdown": sc["breakdown"],
            "elements": els,
            "rationale": (f"{meta['traits']['anchor']} 承担锚点 · "
                          f"支配性 {meta['traits']['dominance']:.2f} · "
                          f"预估占用 {sc['breakdown']['est_occupancy']:.2f}"),
        })
    cands.sort(key=lambda c: (-c["score"], c["archetype"]))
    for i, c in enumerate(cands[:n], 1):
        c["rank"] = i
    out = cands[:n]
    for c in out:
        c["elapsed_ms"] = int((time.time() - t0) * 1000)
    return out


# ── CLI：python layout_search.py <build_module.py> [page_id] ────────────────────
def main(argv):
    import importlib.util
    import json
    if len(argv) < 2:
        print("usage: python layout_search.py <build_module.py> [page_id] [--json]")
        return 1
    mod_path = Path = __import__("pathlib").Path(argv[1])
    spec_mod = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    mod = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    if spec is None:
        print("build module must define build_spec() or SPEC")
        return 1
    page_id = argv[2] if len(argv) > 2 and not argv[2].startswith("-") else None
    slide = next((s for s in spec.get("slides", [])
                  if s.get("id") == page_id), (spec.get("slides") or [{}])[0])
    intent = slide.get("page_intent") or {}
    from design_intelligence import recall_dna
    dna = recall_dna({"brief": json.dumps(spec.get("direction") or {}),
                      "theme": json.dumps((spec.get("theme") or {}).get("colors") or {})})["dna"]
    cands = search(intent, dna=dna, n=3)
    if "--json" in argv:
        print(json.dumps(cands, ensure_ascii=False, indent=2))
        return 0
    print(f"layout search · {slide.get('id')} · family={intent.get('page_family')} "
          f"density={intent.get('density')} energy={intent.get('energy')}")
    for c in cands:
        print(f"  #{c['rank']} {c['archetype']:24s} {c['score']:5.1f} 分  {c['rationale']}")
        print(f"      {c['grammar']}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
