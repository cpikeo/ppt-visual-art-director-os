"""小规模判断基准：固定案例 → 页级判断 → 字段比对 → 指标与回归。

用法：
  python3 scripts/bench.py                       # 跑基准，打印表格
  python3 scripts/bench.py --out bench.json      # 另存结果
  python3 scripts/bench.py --baseline benchmark/baseline_9.21.json   # 计算回归率

只检查**判断字段**（页面角色、证据形态、比较、结论来源、图像决策）。构图、字阶、
中文断行不在这里判：它们需要结构预览或目标软件，本基准不伪装成视觉验收。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import intelligence as intel

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "benchmark" / "cases.json"
BRIEF = {"audience": "内部评审会", "decision": "批准下一步预算"}
# 判断错误的类别：用于「错误布局 / 错误图片 / 错误信息图表」的误判率。
MISJUDGE_FIELDS = {"media", "media_source", "comparison", "evidence", "evidence_not"}


# 语义词表：可被消融（去掉后看哪些判断会变）。数值权重是函数体内的字面量，不在此列。
ABLATABLE = ("_HUMAN_WORDS", "_SCENE_WORDS", "_WITNESS_WORDS", "_TOPIC_TAILS", "_TITLE_ASSERTION",
             "_CONCLUSION_WORDS", "_ASK_WORDS", "_COMPARISON_WORDS", "_SERIES_WORDS",
             "_SEQUENCE_WORDS", "_STRUCTURE_WORDS", "_CHANGE_WORDS", "_TOPIC_MARKERS",
             "_CREDENTIAL_WORDS", "_PHYSICAL_SUBJECTS")


def _actual(case: dict) -> dict:
    item = {"id": case["id"], "title": case["title"], "content": case.get("content", ""),
            **({"chart": True} if case.get("chart") else {}),
            **{k: case[k] for k in ("role", "evidence", "asset") if k in case}}
    world = intel.derive_world(BRIEF, [intel.understand(f"{case['title']} {case.get('content', '')}")])
    judged = intel.page_judgment(item, index=case["index"], total=case["total"],
                                 brief=BRIEF, world=world, warnings=[])
    u = judged["understanding"]
    return {"role": judged["visual_role"]["role"], "evidence": u.get("evidence"),
            "comparison": bool(u.get("comparison")), "claim": judged["claim"]["source"],
            "media": judged["media"]["decision"], "media_source": judged["media"]["source"]}


def _checks(expect: dict, actual: dict) -> list[dict]:
    rows = []
    for key, want in expect.items():
        if key == "evidence_not":
            ok, field, shown = actual["evidence"] not in want, "evidence", actual["evidence"]
            want_s = f"不是 {want}"
        else:
            field = key
            shown = actual[key]
            if isinstance(want, bool):
                ok, want_s = shown == want, str(want)
            else:
                ok, want_s = shown in want, f"∈ {want}"
        rows.append({"field": key if key != "evidence_not" else "evidence_not",
                     "expected": want_s, "actual": shown, "ok": bool(ok),
                     "misjudge_class": key in MISJUDGE_FIELDS})
    return rows


def run(cases_path: Path = DEFAULT_CASES) -> dict:
    data = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    results = []
    for case in data["cases"]:
        actual = _actual(case)
        checks = _checks(case["expect"], actual)
        results.append({"id": case["id"], "category": case["category"],
                        "severity": case["severity"], "title": case["title"],
                        "actual": actual, "checks": checks,
                        "passed": all(c["ok"] for c in checks),
                        "why": case.get("why", "")})
    return {"cases": results, "metrics": _metrics(results)}


def _metrics(results: list[dict]) -> dict:
    checks = [c for r in results for c in r["checks"]]
    mis = [c for c in checks if c["misjudge_class"]]
    critical = [r for r in results if r["severity"] == "critical"]
    return {
        "cases": len(results),
        "cases_passed": sum(r["passed"] for r in results),
        "accuracy": round(sum(c["ok"] for c in checks) / max(len(checks), 1), 3),
        "misjudge_rate_image_chart_structure": round(
            sum(not c["ok"] for c in mis) / max(len(mis), 1), 3),
        "critical_defect_rate": round(
            sum(not r["passed"] for r in critical) / max(len(critical), 1), 3),
        "critical_cases": len(critical),
    }


def ablate(names: list[str], cases_path: Path = DEFAULT_CASES) -> dict:
    """逐组去掉语义词表，重跑基准；返回指标与逐案例的通过状态变化。"""
    full = run(cases_path)
    full_status = {r["id"]: r["passed"] for r in full["cases"]}
    out = {}
    for name in names:
        original = getattr(intel, name)
        blank = () if isinstance(original, tuple) else re.compile(r"(?!x)x")
        setattr(intel, name, blank)
        try:
            rep_ = run(cases_path)
        finally:
            setattr(intel, name, original)
        changed = [r["id"] for r in rep_["cases"] if r["passed"] != full_status[r["id"]]]
        out[name] = {"metrics": rep_["metrics"], "changed_cases": changed,
                     "changed_to": {r["id"]: ("PASS" if r["passed"] else "FAIL")
                                    for r in rep_["cases"] if r["id"] in changed}}
    return {"full": full["metrics"], "ablations": out}


def regression(current: dict, baseline: dict) -> dict:
    """修复回归率：基线里通过、现在失败的案例占基线通过数的比例。"""
    base_pass = {r["id"] for r in baseline["cases"] if r["passed"]}
    now_fail = {r["id"] for r in current["cases"] if not r["passed"]}
    broke = sorted(base_pass & now_fail)
    fixed = sorted({r["id"] for r in baseline["cases"] if not r["passed"]}
                   - now_fail)
    return {"regressed_cases": broke,
            "fixed_cases": fixed,
            "regression_rate": round(len(broke) / max(len(base_pass), 1), 3)}


def _print(report: dict) -> None:
    for r in report["cases"]:
        mark = "PASS" if r["passed"] else "FAIL"
        a = r["actual"]
        print(f"{mark} {r['id']} [{r['severity']:8}] {r['title'][:24]:24} "
              f"role={a['role']} ev={a['evidence']} cmp={a['comparison']} "
              f"claim={a['claim']} media={a['media']}")
        for c in r["checks"]:
            if not c["ok"]:
                print(f"      ✗ {c['field']}: 期望 {c['expected']}，实际 {c['actual']}")
    m = report["metrics"]
    print(f"\n案例通过 {m['cases_passed']}/{m['cases']} · 判断准确率 {m['accuracy']:.1%} · "
          f"图像/图表/结构误判率 {m['misjudge_rate_image_chart_structure']:.1%} · "
          f"严重缺陷率 {m['critical_defect_rate']:.1%}（{m['critical_cases']} 个 critical 案例）")
    if "regression" in report:
        g = report["regression"]
        print(f"修复回归率 {g['regression_rate']:.1%} · 回归 {g['regressed_cases'] or '无'} · "
              f"新修复 {g['fixed_cases'] or '无'}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--ablate", action="store_true", help="逐组消融语义词表，打印指标变化")
    args = parser.parse_args(argv)
    if args.ablate:
        result = ablate(list(ABLATABLE), Path(args.cases))
        f = result["full"]
        print(f"完整基准：通过 {f['cases_passed']}/{f['cases']} · 准确率 {f['accuracy']:.1%} · "
              f"严重缺陷率 {f['critical_defect_rate']:.0%}")
        for name, a in result["ablations"].items():
            m = a["metrics"]
            ch = ", ".join(f"{k}→{v}" for k, v in a["changed_to"].items()) or "无变化"
            print(f"  去掉 {name:20} 通过 {m['cases_passed']}/{m['cases']} · 准确率 {m['accuracy']:.1%} · 变化：{ch}")
        if args.out:
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    report = run(Path(args.cases))
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        report["regression"] = regression(report, baseline)
    _print(report)
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
