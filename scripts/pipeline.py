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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PPT Visual Art Director OS · one-process planning pipeline")
    parser.add_argument("brief", help="需求文件：yml / yaml / json / python module")
    parser.add_argument("--out", help="写入可复用 plan JSON；不传则输出到 stdout")
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
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        if not args.json:
            print(f"plan: {out} ({bundle['performance']['planning_ms']}ms)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
