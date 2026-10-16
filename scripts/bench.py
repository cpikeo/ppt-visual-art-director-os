"""小规模判断基准：固定案例 → 页级判断 → 字段比对 → 指标与回归。

用法：
  python3 scripts/bench.py                       # 跑基准，打印表格
  python3 scripts/bench.py --out bench.json      # 另存结果
  python3 scripts/bench.py --baseline <your-baseline.json>           # 可选：与外部基线对比

只检查**判断字段**（页面角色、证据形态、比较、结论来源、图像决策）。构图、字阶、
中文断行不在这里判：它们需要结构预览或目标软件，本基准不伪装成视觉验收。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import intelligence as intel

# 测试样本随最小技能包保留一份；历史各套案例与来源记录在同一文件中。
DEFAULT_CASES = Path(__file__).with_name("judgment_cases.json")
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
            "claim_text": judged["claim"].get("text"),
            "media": judged["media"]["decision"], "media_source": judged["media"]["source"],
            "media_suggested": judged["media"].get("suggested")}


def _checks(expect: dict, actual: dict) -> list[dict]:
    rows = []
    for key, want in expect.items():
        if key == "evidence_not":
            ok, shown = actual["evidence"] not in want, actual["evidence"]
            want_s = f"不是 {want}"
        else:
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
        results.append({"id": case["id"], "suite": case.get("suite", "external"),
                        "category": case["category"], "severity": case["severity"],
                        "title": case["title"],
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
    now_pass = {r["id"] for r in current["cases"] if r["passed"]}
    now_ids = {r["id"] for r in current["cases"]}
    missing = sorted({r["id"] for r in baseline["cases"]} - now_ids)
    broke = sorted(base_pass - now_pass)
    fixed = sorted({r["id"] for r in baseline["cases"] if not r["passed"]} & now_pass)
    return {"regressed_cases": broke, "missing_cases": missing,
            "fixed_cases": fixed,
            "regression_rate": round(len(broke) / max(len(base_pass), 1), 3)}


# ── 盲评通道（R6）：视觉质量由人评，不写入自动化门。本模块只负责打乱、改名、汇总与一致性。
BLIND_DIMS = ("narrative", "focus", "composition", "typography", "completeness")
BLIND_DIMS_CN = {"narrative": "叙事", "focus": "焦点", "composition": "构图",
                 "typography": "中文排版", "completeness": "整体完成度"}


def blind_pack(items: list[str], out_dir: Path, seed: int | None = None) -> dict:
    """打乱并改名待评版本。映射写入 out_dir 之外的 key 文件，评审目录里只有匿名件与空白评分表。"""
    import random
    import shutil
    from primitives import validate_io_paths, PathConflictError, json_write
    out_dir = Path(out_dir).expanduser().resolve()
    sources = [Path(item).expanduser().resolve() for item in items]
    key_path = out_dir.parent / (out_dir.name + ".key.json")
    # copytree 不得递归读入自己刚创建的输出；key 也不能写回待评输入树。
    for src in sources:
        if src.is_dir() and (out_dir == src or out_dir.is_relative_to(src)
                             or key_path.is_relative_to(src)):
            raise PathConflictError(f"盲评输出不能位于待评输入目录内：{src}")
    validate_io_paths({f"item {i}": src for i, src in enumerate(sources)},
                      {"blind key": key_path}, managed_dirs={"blind output": out_dir})
    # 合并复制会残留旧版本/旧评分，甚至泄露不属于本轮的素材；不擅自删除用户工作。
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"盲评输出目录非空；请使用新的目录以隔离本轮评审：{out_dir}")
    if key_path.exists():
        raise FileExistsError(f"保留已有盲评映射；请使用新的输出目录：{key_path}")
    rng = random.Random(seed)
    order = list(range(len(items)))
    rng.shuffle(order)
    out_dir.mkdir(parents=True, exist_ok=True)
    mapping, rows = {}, []
    for n, idx in enumerate(order, 1):
        src = sources[idx]
        code = f"V{n:02d}"
        dst = out_dir / f"{code}{src.suffix}"
        if src.is_dir():
            shutil.copytree(src, out_dir / code, dirs_exist_ok=True)
        else:
            shutil.copyfile(src, dst)
        mapping[code] = str(Path(items[idx]))  # 保留 key 中原有的作者路径表达
        rows.append(code)
    json_write(key_path, mapping)
    sheet = out_dir / "score_sheet.csv"
    header = ["reviewer", "item"] + list(BLIND_DIMS) + ["reason"]
    sheet.write_text(",".join(header) + "\n" +
                     "\n".join(f",{c},,,,,," for c in rows) + "\n", encoding="utf-8")
    return {"items": rows, "sheet": str(sheet), "key": str(key_path)}


def _icc_2_1(matrix: list[list[float]]) -> float | None:
    """ICC(2,1)：双向随机效应、单次测量的绝对一致性。matrix[target][rater]。"""
    n = len(matrix)
    k = len(matrix[0]) if n else 0
    if n < 2 or k < 2:
        return None
    grand = sum(sum(r) for r in matrix) / (n * k)
    row_m = [sum(r) / k for r in matrix]
    col_m = [sum(matrix[i][j] for i in range(n)) / n for j in range(k)]
    ssr = k * sum((m - grand) ** 2 for m in row_m)
    ssc = n * sum((m - grand) ** 2 for m in col_m)
    sst = sum((matrix[i][j] - grand) ** 2 for i in range(n) for j in range(k))
    sse = sst - ssr - ssc
    msr, msc = ssr / (n - 1), ssc / (k - 1)
    mse = sse / ((n - 1) * (k - 1)) if (n - 1) * (k - 1) else 0.0
    den = msr + (k - 1) * mse + k * (msc - mse) / n
    return None if den == 0 else (msr - mse) / den


def blind_score(sheet_paths: list[str], key_path: str) -> dict:
    """汇总多位评审的评分表：每版本每维度均值 + ICC(2,1)。一致性低时不宣称共识。"""
    import csv
    import io
    key = json.loads(Path(key_path).read_text(encoding="utf-8"))
    if not isinstance(key, dict) or not key:
        raise ValueError("盲评 key 必须是非空版本映射")
    by_reviewer: dict[str, dict[str, dict]] = {}
    for sp in sheet_paths:
        for row in csv.DictReader(io.StringIO(Path(sp).read_text(encoding="utf-8"), newline="")):
            if not row.get("item") or not row.get("reviewer"):
                continue
            if row["item"] not in key:
                raise ValueError(f"评分引用未知版本：{row['item']}")
            vals = {d: row.get(d) for d in BLIND_DIMS}
            if all(vals[d] not in (None, "") for d in BLIND_DIMS):
                parsed = {d: float(vals[d]) for d in BLIND_DIMS}
                if not all(math.isfinite(v) for v in parsed.values()):
                    raise ValueError(f"评分必须为有限数字：{row['reviewer']}/{row['item']}")
                ratings = by_reviewer.setdefault(row["reviewer"], {})
                if row["item"] in ratings:
                    raise ValueError(f"重复评分：{row['reviewer']}/{row['item']}")
                ratings[row["item"]] = parsed
    reviewers = sorted(by_reviewer)
    items = sorted(key)  # 完整性以 key 为准，不以「恰好有人评分的版本」为准
    complete = [r for r in reviewers if set(by_reviewer[r]) == set(items)]
    report = {"reviewers": len(reviewers), "complete_reviewers": len(complete),
              "items": items, "dimensions": {}, "consensus": "NOT_ENOUGH_REVIEWERS"}
    if len(complete) < 3:
        return report
    consensus = True
    for d in BLIND_DIMS:
        mat = [[by_reviewer[r][i][d] for r in complete] for i in items]
        icc = _icc_2_1(mat)
        means = {i: round(sum(by_reviewer[r][i][d] for r in complete) / len(complete), 2) for i in items}
        report["dimensions"][BLIND_DIMS_CN[d]] = {"icc": None if icc is None else round(icc, 3),
                                                  "mean": {key.get(i, i): means[i] for i in items}}
        if icc is None or not math.isfinite(icc) or icc < 0.5:
            consensus = False
    report["consensus"] = "CONSENSUS_WEAK_OR_OK" if consensus else "NO_CONSENSUS"
    return report


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
    # 与生产入口共用 UTF-8 管道契约。Windows 的 cp1252 stdout 会在打印
    # 中文 FAIL 详情前抛 UnicodeEncodeError：退出码仍是 1，却不是真实负例结果。
    from vao import force_utf8_stdio
    force_utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["blind"]:
        if len(argv) >= 3 and argv[1] == "pack":
            try:
                result = blind_pack(argv[3:], Path(argv[2]))
            except (ValueError, OSError) as exc:
                print(f"bench error: {exc}", file=sys.stderr)
                return 2
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if len(argv) >= 4 and argv[1] == "score":
            try:
                result = blind_score(argv[3:], argv[2])
            except (ValueError, OSError) as exc:
                print(f"bench error: {exc}", file=sys.stderr)
                return 2
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        print("用法：bench.py blind pack <评审目录> <版本1> <版本2> ...\n"
              "      bench.py blind score <key.json> <评分表1.csv> <评分表2.csv> ...", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--ablate", action="store_true", help="逐组消融语义词表，打印指标变化")
    args = parser.parse_args(argv)
    from primitives import validate_io_paths, json_write
    try:
        validate_io_paths({"cases": args.cases, "baseline": args.baseline}, {"report": args.out})
    except (ValueError, OSError) as exc:
        print(f"bench error: {exc}", file=sys.stderr)
        return 2
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
            json_write(args.out, result)
        return 0
    report = run(Path(args.cases))
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        report["regression"] = regression(report, baseline)
    _print(report)
    if args.out:
        json_write(args.out, report)
    reg = report.get("regression") or {}
    return 0 if (report["metrics"]["cases_passed"] == report["metrics"]["cases"]
                 and not reg.get("regressed_cases") and not reg.get("missing_cases")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
