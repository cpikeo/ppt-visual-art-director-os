"""独立泛化评测（holdout-2）：验证既有判断能否迁移到未参与调试的内容。

用法：
  python3 scripts/unseen_bench.py                  # 校验冻结哈希 → 盲测 → 分桶报告
  python3 scripts/unseen_bench.py --out unseen.json

纪律（写进工具本身，不靠自觉）：
  1. 每次运行先校验 generalization_cases.json 的冻结哈希；期望被改动 → 拒绝运行（exit 2）。
  2. 本工具**只读不写**：不修 intelligence、不改案例；差异是泛化发现，进报告不进规则。
  3. 失败分四桶独立报告：严重误判 / 错误媒体决策 / 主张错位 / 因果误推。
  4. 单页案例统一走 page_judgment（生产 API），页位固定 index=1/total=3（证据页语义，
     避开封面/致谢的凭证特判）；多页案例走 think（整套叙事）。
与 scripts/bench.py 的 57 例（回归基准，可参与调试）互相独立：那边护住已修行为，
这边护住「没见过的内容」。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import intelligence as intel

CASES = Path(__file__).resolve().parent / "json" / "generalization_cases.json"
BRIEF = {"audience": "内部评审会", "decision": "批准下一步预算"}

CLASS_OF = {
    "role": "severe", "evidence": "severe", "evidence_not": "severe",
    "comparison": "severe", "part_whole": "severe", "primary": "severe",
    "primary_contains": "severe", "focus": "severe", "distinct_min": "severe",
    "media": "media", "media_source": "media", "media_suggested": "media",
    "claim": "claim", "claim_contains": "claim", "claim_soft": "claim",
    "claim_not_contains": "claim", "claim_text": "claim",
}
CLASS_NAMES = {"severe": "严重误判", "media": "错误媒体决策",
               "claim": "主张错位", "causal": "因果误推", "other": "其他"}


def _payload_hash(data: dict) -> str:
    payload = json.dumps({"cases": data.get("cases"), "narratives": data.get("narratives")},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _actual_single(case: dict) -> dict:
    item = {"id": case["id"], "title": case.get("title", ""), "content": case.get("content", "")}
    world = intel.derive_world(BRIEF, [intel.understand(f"{item['title']} {item['content']}")])
    judged = intel.page_judgment(item, index=1, total=3, brief=BRIEF, world=world, warnings=[])
    u = judged["understanding"]
    media = judged["media"]
    return {
        "role": judged["visual_role"]["role"],
        "evidence": u.get("evidence"),
        "comparison": bool(u.get("comparison")),
        "part_whole": bool(u.get("part_whole")),
        "claim": judged["claim"].get("source"),
        "claim_text": judged["claim"].get("text"),
        "media": media.get("decision"),
        "media_source": media.get("source"),
        "media_suggested": media.get("suggested") or media.get("function"),
        "focus": judged["focus"].get("element_role"),
        # 主语量的正式落点是 typography.lead（typography_of 的 focal＝primary['raw']）；
        # information_weight 只有 maximize/weaken/delete 三档列表，没有 lead 键。
        # （第一轮盲测误读 information_weight['lead'] 造成 2 处假阳性——量具修正，期望未动。）
        "primary": judged["typography"].get("lead"),
        "distinct": u.get("distinct_numerals"),
        "open_questions": judged.get("open_questions"),
    }


def _match(key: str, want, actual: dict) -> tuple[bool, str, str]:
    """返回 (ok, want_shown, actual_shown)。断言语义在文档里，不搞隐式匹配。"""
    if key == "evidence_not":
        shown = actual.get("evidence")
        return shown not in want, f"∉ {want}", str(shown)
    if key == "distinct_min":
        shown = actual.get("distinct") or 0
        return shown >= want, f"≥ {want}", str(shown)
    if key == "claim_contains":
        text = str(actual.get("claim_text") or "")
        return all(s in text for s in want), f"文本含 {want}", text or "(无)"
    if key == "claim_not_contains":
        text = str(actual.get("claim_text") or "")
        return not any(s in text for s in want), f"文本不含 {want}", text or "(无)"
    if key == "claim_soft":
        # 模糊主张口径：absent/frame 属可接受（不编）；有文本则必须原样保留关键词。
        if actual.get("claim") in ("absent", "frame", None):
            return True, f"absent/frame 或文本含 {want}", str(actual.get("claim"))
        text = str(actual.get("claim_text") or "")
        return any(s in text for s in want), f"absent/frame 或文本含 {want}", text
    if key == "primary_contains":
        text = str(actual.get("primary") or "")
        return all(s in text for s in want), f"主语含 {want}", text or "(无)"
    if key == "claim_text":
        shown = actual.get("claim_text")
        return shown in want, f"∈ {want}", str(shown)
    shown = actual.get(key)
    if isinstance(want, bool):
        return shown == want, str(want), str(shown)
    if isinstance(want, list):
        return shown in want, f"∈ {want}", str(shown)
    return shown == want, str(want), str(shown)


def _check_expect(expect: dict, classes: dict, actual: dict) -> list[dict]:
    rows = []
    for key, want in expect.items():
        ok, want_s, shown = _match(key, want, actual)
        rows.append({"field": key, "expected": want_s, "actual": shown, "ok": bool(ok),
                     "fail_class": classes.get(key) or CLASS_OF.get(key, "other")})
    return rows


def _run_narrative(n: dict) -> dict:
    pages = intel.think(n["brief"])
    by_id = {p["id"]: p for p in pages.get("pages", [])}
    rows, observed = [], {}
    exp = n["expect"]
    first = (pages.get("pages") or [{}])[0]
    rows.append({"field": "first_role", "expected": exp.get("first_role"),
                 "actual": (first.get("judgment", {}).get("visual_role", {}) or {}).get("role"),
                 "ok": (first.get("judgment", {}).get("visual_role", {}) or {}).get("role")
                       == exp.get("first_role"),
                 "fail_class": "severe"})
    media_all_ok = all(p.get("judgment", {}).get("media", {}).get("decision") == exp.get("media_all")
                       for p in pages.get("pages", []))
    rows.append({"field": "media_all", "expected": exp.get("media_all"),
                 "actual": [p.get("judgment", {}).get("media", {}).get("decision")
                            for p in pages.get("pages", [])],
                 "ok": media_all_ok, "fail_class": "media"})
    for pid, page_exp in (exp.get("pages") or {}).items():
        page = by_id.get(pid)
        if not page:
            rows.append({"field": pid, "expected": "页面存在", "actual": "缺失",
                         "ok": False, "fail_class": "severe"})
            continue
        j = page.get("judgment", {})
        u = j.get("understanding", {})
        actual = {
            "role": j.get("visual_role", {}).get("role"),
            "evidence": u.get("evidence"),
            "comparison": bool(u.get("comparison")),
            "part_whole": bool(u.get("part_whole")),
            "claim": j.get("claim", {}).get("source"),
            "claim_text": j.get("claim", {}).get("text"),
            "media": j.get("media", {}).get("decision"),
            "focus": j.get("focus", {}).get("element_role"),
            "primary": j.get("typography", {}).get("lead"),
            "open_questions": j.get("open_questions"),
        }
        observed[pid] = {k: actual.get(k) for k in ("role", "evidence", "claim", "claim_text")}
        for row in _check_expect(page_exp, n.get("classes", {}), actual):
            rows.append({"field": f"{pid}.{row['field']}", **{k: row[k] for k in
                         ("expected", "actual", "ok", "fail_class")}})
    observed["roles"] = [p.get("judgment", {}).get("visual_role", {}).get("role")
                         for p in pages.get("pages", [])]
    observed["compositions"] = [p.get("judgment", {}).get("composition", {}).get("chosen")
                                for p in pages.get("pages", [])]
    observed["rhythms"] = [p.get("judgment", {}).get("rhythm", {}).get("move")
                           for p in pages.get("pages", [])]
    return {"id": n["id"], "group": n.get("group"), "severity": n.get("severity"),
            "title": f"叙事（{len(n['brief'].get('slides', []))} 页）",
            "checks": rows, "observe": observed, "why": n.get("why", ""),
            "passed": all(r["ok"] for r in rows)}


def run(cases_path: Path = CASES) -> dict:
    data = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    frozen = (data.get("freeze") or {}).get("sha256_of_payload", "")
    live = _payload_hash(data)
    if not frozen or live != frozen:
        raise SystemExit(f"[FROZEN-CHECK] 评测集哈希不匹配：期望被改动或未冻结。\n"
                         f"  freeze = {frozen}\n  live   = {live}\n"
                         f"  泛化评测禁止对着结果改期望；确需重冻结请换 freeze 版本并留档。")
    results = []
    for case in data["cases"]:
        actual = _actual_single(case)
        rows = _check_expect(case["expect"], case.get("classes", {}), actual)
        results.append({"id": case["id"], "group": case.get("group"),
                        "severity": case.get("severity"), "title": case["title"],
                        "actual": {k: actual.get(k) for k in
                                   ("role", "evidence", "claim", "claim_text", "media",
                                    "focus", "primary", "distinct")},
                        "checks": rows,
                        "observe": {k: actual.get(k) for k in (case.get("observe") or [])},
                        "passed": all(r["ok"] for r in rows), "why": case.get("why", "")})
    for n in data.get("narratives", []):
        results.append(_run_narrative(n))
    return {"frozen_sha256": live, "cases": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--cases", default=None, help="评测集路径（默认 generalization_cases.json）")
    args = ap.parse_args()
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    from primitives import validate_io_paths, json_write
    try:
        validate_io_paths({"cases": args.cases or CASES}, {"report": args.out})
    except (ValueError, OSError) as exc:
        print(f"unseen_bench error: {exc}", file=sys.stderr)
        return 2
    report = run(Path(args.cases) if args.cases else CASES)
    buckets: dict[str, int] = {}
    fails = []
    for r in report["cases"]:
        for c in r["checks"]:
            if not c["ok"]:
                buckets[c["fail_class"]] = buckets.get(c["fail_class"], 0) + 1
                fails.append((r["id"], c))
        mark = "PASS" if r["passed"] else "FAIL"
        detail = ""
        if not r["passed"]:
            bad = [c for c in r["checks"] if not c["ok"]]
            detail = " · " + "; ".join(f"{c['field']} 期望 {c['expected']} 实得 {c['actual']}"
                                       for c in bad[:2])
        print(f"[{mark}] {r['id']} {r.get('title', '')[:24]}{detail}")
    total_checks = sum(len(r["checks"]) for r in report["cases"])
    n_fail = sum(buckets.values())
    print(f"\n断言 {total_checks - n_fail}/{total_checks} 通过 · 案例 "
          f"{sum(1 for r in report['cases'] if r['passed'])}/{len(report['cases'])} 全过")
    for cls, n in sorted(buckets.items()):
        print(f"  {CLASS_NAMES.get(cls, cls)}: {n}")
    if n_fail:
        print("\n差异明细（发现即报告，不回改期望）：")
        for cid, c in fails:
            print(f"  {cid}.{c['field']} [{CLASS_NAMES.get(c['fail_class'], c['fail_class'])}]"
                  f" 期望 {c['expected']} · 实得 {c['actual']}")
    if args.out:
        json_write(args.out, report, indent=1)
        print(f"\n结果: {args.out}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
