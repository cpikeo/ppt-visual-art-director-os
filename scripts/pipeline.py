#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-process planning entry point for PPT Visual Art Director OS.

The old documented path launched intent_compiler, route and layout_search as
separate Python processes.  Each process lost the in-memory decision cache and
re-read the same input.  This entry point keeps the planning half in one
process and emits one reusable JSON artifact for the spec-writing agent.

It deliberately stops before compiling or rendering: planning is cheap and
should not accidentally trigger LibreOffice or image generation.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Support both `python scripts/pipeline.py` and importing the module from repo root.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from intent_compiler import _load_need, compile_brief
from route import one_pass_plan, plan_deck


def build_plan_bundle(need: dict) -> dict:
    """Build brief, deck route, layouts and forecast with one route computation."""
    t0 = time.perf_counter()
    need = dict(need or {})
    plan = plan_deck(need)
    brief = compile_brief(need, route_plan=plan)
    intelligence = one_pass_plan(need, plan=plan)

    # one_pass_plan returns the same plan for API convenience.  Do not duplicate
    # the large object in the persisted bundle.
    bundle = {
        "schema": "vao-plan-v1",
        "source_hash": brief.get("source_hash"),
        "need": need,
        "brief": brief,
        "plan": plan,
        "deck_decision": intelligence.get("deck_decision"),
        "color_plan": intelligence.get("color_plan"),
        "forecast": intelligence.get("forecast"),
        "pages": intelligence.get("pages") or [],
        "policy": intelligence.get("policy") or {},
        "performance": {
            "planning_ms": round((time.perf_counter() - t0) * 1000, 2),
            "route_calls": 1,
            "rendered": False,
            "compiled": False,
        },
    }
    return bundle


def build_skeleton_module(bundle: dict) -> str:
    """plan bundle → build 模块骨架（v4.26 轮次治理批）。

    边界（技能包 ≠ 设计系统）：只把 plan.json 里**已决策的事实**序列化——
    canvas 契约值、color_plan 种子槽位映射、每页 id/page_intent 骨架/source_zone。
    `elements` 一律留空：几何、构图、字阶、媒体是生成侧的设计判断，骨架不预设。
    同 plan 必得同文本（确定性）。生成侧填完 TODO 直接 `qa.py --mode draft`。
    """
    need = bundle.get("need") or {}
    plan = bundle.get("plan") or {}
    plan_pages = plan.get("pages") or []
    intel_pages = bundle.get("pages") or []
    color = bundle.get("color_plan") or {}
    seed = color.get("seed_skeleton") or {}
    constraints = color.get("constraints") or {}
    raw_slides = need.get("slides") if isinstance(need.get("slides"), list) else []

    def _slot(name: str, fallback: str) -> str:
        v = seed.get(name) if isinstance(seed, dict) else None
        return v if isinstance(v, str) and v.startswith("#") else fallback

    # 种子四槽 → theme.colors 六 token（SKILL「seed 落进 spec.theme」的机械映射）
    colors = {"background": _slot("foundation", "#FFFFFF"),
              "ink": _slot("information", "#111111"),
              "muted": _slot("supporting", "#777777"),
              "primary": _slot("information", "#222222"),
              "secondary": _slot("supporting", "#333333"),
              "accent": _slot("accent", "#AA0000")}
    try:
        accent_max = float(constraints.get("accent_area_max", 0.05))
    except (TypeError, ValueError):
        accent_max = 0.05

    L = ['# -*- coding: utf-8 -*-',
         '"""pipeline.py --skeleton 生成骨架：plan.json 已决策字段序列化，零布局/样式预设。',
         '',
         'TODO（填完直接 qa.py --mode draft；spec 档是诊断工具，不是阶段门）：',
         '  1) 每页 page_intent.insight（本页唯一结论）与 focus（视线第一落点元素 id）',
         '  2) 每页 elements：数值几何 x/y/width/height（8 的倍数）+ text + 样式平铺顶层',
         '  3) theme.fonts（字体家族 ≤2）与 direction.color_intent:[brand,emotion,hierarchy]',
         '  4) 图表页齐 source/unit/period/basis；source_zone 内 role∈{source,method,metadata}',
         '"""',
         '',
         'SPEC = {',
         '    "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},',
         '    "theme": {',
         f'        "colors": {colors!r},',
         '        "fonts": {"display": "TODO", "body": "TODO"},',
         f'        "constraints": {{"accent_max": {accent_max}}},',
         '    },',
         '    "strategy": {},                      # TODO：P2 Strategy（受众/决策/张力/证据）',
         '    "direction": {"color_intent": []},  # TODO：[brand, emotion, hierarchy]',
         '    "slides": [']
    for i, pg in enumerate(plan_pages):
        intel = intel_pages[i] if i < len(intel_pages) else {}
        skel = dict(intel.get("skeleton") or {})
        skel["insight"] = ""          # 内容判断留给生成侧
        skel["focus"] = ""
        sid = str(pg.get("id") or f"s{i + 1:02d}")
        raw = raw_slides[i] if i < len(raw_slides) else ""
        if isinstance(raw, dict):
            ref = " ".join(str(raw.get(k) or "") for k in ("title", "content")).strip()
        else:
            ref = str(raw).strip()
        media = ((intel.get("media") or {}).get("decision")
                 or (pg.get("asset") or {}).get("decision") or "none")
        L.append(f'        # ── {sid} · family={skel.get("page_family") or pg.get("page_family")}'
                 f' · density={pg.get("density")} · energy={pg.get("energy")} · media={media}')
        if ref:
            L.append(f'        #    内容参考: {ref[:90]}')
        L.append('        {')
        L.append(f'            "id": {sid!r},')
        L.append(f'            "page_intent": {json.dumps(skel, ensure_ascii=False)},'
                 '  # TODO: insight/focus')
        L.append('            "source_zone": {"x": 64, "y": 640, "width": 1152, "height": 40},')
        L.append('            "background": {"color": "background"},')
        L.append('            "elements": [')
        L.append('                # TODO：x/y/width/height 全数值（8 的倍数）；text 放内容；')
        L.append('                # 样式平铺顶层（size/color/bold/align/max_lines/line_height/padding）；')
        L.append('                # 框高 ≥ 字号×行高×行数；文本/图表/图片/来源区墨迹不相交。')
        L.append('            ],')
        L.append('        },')
    L += ['    ],', '}', '']
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PPT Visual Art Director OS · one-process planning pipeline")
    parser.add_argument("brief", help="需求文件：yml / yaml / json / python module")
    parser.add_argument("--out", help="写入可复用 plan JSON；不传则输出到 stdout")
    parser.add_argument("--skeleton",
                        help="另写 build 模块骨架：plan 已决策字段序列化，elements 留空待填")
    parser.add_argument("--json", action="store_true",
                        help="stdout 输出完整 JSON（默认同样输出 JSON，保留兼容旗标）")
    args = parser.parse_args(argv)

    try:
        need = _load_need(args.brief)
        bundle = build_plan_bundle(need)
    except ModuleNotFoundError as exc:
        parser.error(f"缺少依赖 {exc.name!r}；请运行 python -m pip install -r requirements.txt")
        return 2
    except Exception as exc:
        parser.error(f"无法生成计划：{type(exc).__name__}: {exc}")
        return 2

    text = json.dumps(bundle, ensure_ascii=False, indent=2, default=str)
    wrote_file = False
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        wrote_file = True
        if not args.json:
            print(f"plan: {out} ({bundle['performance']['planning_ms']}ms)")
    if args.skeleton:
        sk = Path(args.skeleton)
        sk.parent.mkdir(parents=True, exist_ok=True)
        sk.write_text(build_skeleton_module(bundle), encoding="utf-8")
        wrote_file = True
        if not args.json:
            print(f"skeleton: {sk} ({len((bundle.get('plan') or {}).get('pages') or [])} 页，"
                  f"elements 留空；填完 TODO 直接 qa.py --mode draft)")
    if not wrote_file or args.json:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
