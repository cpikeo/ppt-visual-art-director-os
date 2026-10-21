"""确定性评分器：把 facts.json 映射成 skill-creator 认识的 grading.json。

为什么不用 LLM 打分：本技能的多数承诺是**可判定**的（能不能交付、有没有原生图表、
预览有没有截断、判断卡有没有主张）。用模型去判这些，等于把可复核证据换成不可复核意见。
需要人判断的那一层（视觉质量）走 `generate_review.py` 的静态页 + feedback.json，
本文件不冒充它。

字段契约（viewer / aggregate_benchmark 依赖，写错就白屏）：
    expectations[].text / .passed / .evidence
    summary.passed / .failed / .total / .pass_rate
"""
from __future__ import annotations

import json
import pathlib
import sys

# 断言种类 → 判定函数。新增种类必须同时加进 CHECKS 的 docstring 与 selftest 的词汇表检查。
PLAN_LAYER = {"plan_contract_clean", "pages", "page_role", "page_evidence", "page_media",
              "claim_present", "claim_absent", "warning_rule", "composition_present"}
RELEASE_LAYER = {"release_pass", "native_charts", "ghost_truncations", "ghost_out_of_canvas",
                 "pptx_bytes", "compiled_pages", "source_lines", "spec_charts"}
CHECK_KINDS = PLAN_LAYER | RELEASE_LAYER


def _page(facts: dict, page_id: str) -> dict | None:
    plan = facts.get("plan") or {}
    for page in plan.get("pages") or []:
        if page.get("id") == page_id:
            return page.get("judgment") or page
    return None


def _verdict(facts: dict) -> dict:
    return (facts.get("verdict") or {}).get("verdict") or {}


def _codes(facts: dict) -> list:
    return (facts.get("verdict") or {}).get("failure_codes") or []


def judge(kind: str, spec: dict, facts: dict) -> tuple[bool, str, str]:
    """返回 (passed, 期望的人话, 实际的人话)。证据必须能被人复读。"""
    if kind == "plan_contract_clean":
        plan = facts.get("plan") or {}
        errs = plan.get("contract", {}).get("errors") if isinstance(plan.get("contract"), dict) else None
        # plan 落盘时若违反契约，run_plan 会直接失败；此处复核 returncode 与 meta
        ok = facts.get("plan_returncode") == 0 and plan is not None
        return ok, "plan 落盘成功且通过契约", f"returncode={facts.get('plan_returncode')} pages={len(plan.get('pages') or []) if plan else 0}"

    if kind == "pages":
        pages = (facts.get("plan") or {}).get("pages") or []
        lo, hi = spec.get("min", 0), spec.get("max", 10 ** 6)
        return lo <= len(pages) <= hi, f"{lo}–{hi} 页", f"{len(pages)} 页"

    if kind == "page_role":
        page = _page(facts, spec["page"])
        role = ((page or {}).get("visual_role") or {}).get("role")
        return role in spec["in"], f"∈ {spec['in']}", str(role)

    if kind == "page_evidence":
        page = _page(facts, spec["page"])
        ev = ((page or {}).get("understanding") or {}).get("evidence")
        return ev in spec["in"], f"∈ {spec['in']}", str(ev)

    if kind == "page_media":
        page = _page(facts, spec["page"])
        decision = ((page or {}).get("media") or {}).get("decision")
        want = spec.get("in") or [spec.get("is")]
        return decision in want, f"∈ {want}", str(decision)

    if kind in ("claim_present", "claim_absent"):
        page = _page(facts, spec["page"])
        claim = (page or {}).get("claim") or {}
        has = bool(claim.get("text")) and claim.get("source") not in (None, "absent")
        return (has if kind == "claim_present" else not has), \
            ("有可复述主张" if kind == "claim_present" else "主张缺席"), \
            f"source={claim.get('source')} text={str(claim.get('text'))[:24]!r}"

    if kind == "warning_rule":
        warnings = (facts.get("plan") or {}).get("warnings") or []
        hit = [w for w in warnings if isinstance(w, dict) and w.get("rule") == spec["rule"]]
        return len(hit) >= spec.get("min", 1), f"≥{spec.get('min', 1)} 条 {spec['rule']}", \
            f"{len(hit)} 条 · 全部规则={[w.get('rule') for w in warnings][:5]}"

    if kind == "composition_present":
        page = _page(facts, spec["page"])
        chosen = ((page or {}).get("composition") or {}).get("chosen")
        return bool(chosen), "构图有落点", str(chosen)

    if kind == "release_pass":
        verdict = _verdict(facts)
        status = facts.get("verdict", {}).get("status")
        return status == "PASS", "release PASS", f"status={status} blocking={verdict.get('blocking')} codes={_codes(facts)[:3]}"

    if kind == "native_charts":
        count = ((facts.get("pptx") or {}).get("native_charts"))
        lo = spec.get("min", 0)
        return (count or 0) >= lo, f"≥{lo} 个原生图表", f"{count}"

    if kind == "ghost_truncations":
        facts_ghost = facts.get("ghost") or {}
        n = len(facts_ghost.get("truncations") or {})
        return n <= spec.get("max", 0), f"≤{spec.get('max', 0)} 处截断", \
            f"{n} 处 {list((facts_ghost.get('truncations') or {}))[:3]}"

    if kind == "ghost_out_of_canvas":
        facts_ghost = facts.get("ghost") or {}
        n = len(facts_ghost.get("out_of_canvas") or {})
        return n <= spec.get("max", 0), f"≤{spec.get('max', 0)} 个出画布元素", f"{n}"

    if kind == "pptx_bytes":
        size = (facts.get("pptx") or {}).get("bytes") or 0
        lo, hi = spec.get("min", 0), spec.get("max", 10 ** 9)
        return lo <= size <= hi, f"{lo}–{hi} 字节", f"{size}"

    if kind == "source_lines":
        roles = ((facts.get("spec") or {}).get("roles") or [])
        n = sum(1 for r in roles if "source" in r.lower())
        return n >= spec.get("min", 1), f"≥{spec.get('min', 1)} 条出处行", f"{n} 条（roles={roles[:6]}）"

    if kind == "spec_charts":
        n = (facts.get("spec") or {}).get("charts") or 0
        return n >= spec.get("min", 1), f"≥{spec.get('min', 1)} 个图表元素", f"{n}"

    if kind == "compiled_pages":
        pages = ((facts.get("verdict") or {}).get("timing") or {}).get("slides")
        lo = spec.get("min", 1)
        return (pages or 0) >= lo, f"≥{lo} 页编译", str(pages)

    raise ValueError(f"未知断言种类: {kind}")


def grade(evals: list[dict], facts_by_eval: dict, config: str) -> list[dict]:
    """对每个用例产出 grading.json 内容（不落盘，由 run_eval 决定路径）。"""
    results = []
    for case in evals:
        facts = facts_by_eval[case["id"]]
        rows, skipped = [], []
        for check in case.get("checks") or []:
            kind = check["kind"]
            layer = "plan" if kind in PLAN_LAYER else "release"
            if layer == "plan" and config != "with_skill":
                skipped.append({"kind": kind, "why": "基线配置不产判断（无 plan 判断层）"})
                continue
            if layer == "release" and (facts.get("release") is None and not facts.get("verdict")):
                skipped.append({"kind": kind, "why": "本用例没有 build 夹具，不产产物"})
                continue
            passed, want, shown = judge(kind, check, facts)
            rows.append({"text": f"[{case['name']}] {check.get('label') or kind}: 期望 {want}",
                         "passed": bool(passed), "evidence": f"实际 {shown}",
                         "layer": layer})
        passed = sum(1 for r in rows if r["passed"])
        total = len(rows)
        results.append({
            "eval_id": case["id"],
            "eval_name": case["name"],
            "config": config,
            "expectations": rows,
            "skipped": skipped,
            "summary": {"passed": passed, "failed": total - passed, "total": total,
                        "pass_rate": round(passed / total, 4) if total else 0.0},
            "execution_metrics": {
                "tool_calls": {"vao_cli": len(facts.get("steps") or [])},
                "total_tool_calls": len(facts.get("steps") or []),
                "total_steps": len(facts.get("steps") or []),
                "files_created": _files(facts),
                "errors_encountered": int(facts.get("check_returncode") not in (None, 0))
                + int(facts.get("plan_returncode") not in (None, 0)),
                # 这里必须是**模型输出**的字符数。本项目没有模型参与，所以是 0；
                # 产物字节单独记 artifact_bytes——写进 output_chars 会被
                # aggregate_benchmark 当成 token 数（上一版就把 46KB 报成了 46635 tokens）。
                "output_chars": 0,
                "artifact_bytes": (facts.get("pptx") or {}).get("bytes") or 0,
                "transcript_chars": 0,
            },
            "timing": {
                "plan_seconds": facts.get("plan_seconds"),
                "check_seconds": facts.get("check_seconds"),
                "total_duration_seconds": round((facts.get("plan_seconds") or 0)
                                                + (facts.get("check_seconds") or 0), 3),
            },
            "user_notes_summary": {
                "uncertainties": _uncertainties(facts, config),
                "needs_review": [],
                "workarounds": [],
            },
        })
    return results


def _files(facts: dict) -> list[str]:
    names = []
    if facts.get("plan"):
        names.append("plan.json")
    if (facts.get("pptx") or {}).get("exists"):
        names.append("deck.pptx")
    if facts.get("ghost", {}).get("pages_drawn"):
        names.append(f"preview x{ facts['ghost']['pages_drawn'] }")
    return names


def _uncertainties(facts: dict, config: str) -> list[str]:
    notes = ["token 成本不适用：本轮为确定性引擎运行，无模型参与（total_tokens 记为 0）"]
    if config != "with_skill":
        notes.append("基线是 engine-baseline（无判断层直排），不是 model-baseline；"
                     "它衡量的是判断层带来的差异，不代表「人不用技能时会怎样」")
    if (facts.get("ghost") or {}).get("error"):
        notes.append(f"预览事实采集失败：{facts['ghost']['error']}")
    if (facts.get("ghost") or {}).get("font_substitutions"):
        notes.append("预览发生了字体替换，换行位置不可当作产物证据")
    return notes


def main(argv: list[str] | None = None) -> int:
    """CLI：grade.py <evals.json> <facts.json> --config with_skill → 打印 grading.json"""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("evals")
    parser.add_argument("facts")
    parser.add_argument("--config", default="with_skill")
    args = parser.parse_args(argv)
    data = json.loads(pathlib.Path(args.evals).read_text(encoding="utf-8"))
    facts = json.loads(pathlib.Path(args.facts).read_text(encoding="utf-8"))
    result = grade(data["evals"], {k: v for k, v in facts.items()}, args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
