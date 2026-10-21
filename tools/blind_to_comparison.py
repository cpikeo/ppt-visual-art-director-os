"""把人工盲评的评分表导出成 skill-creator 的 `comparison.json`。

分工（不重叠）：

- `bench.py blind score` 是**统计**：每版本每维度均值、ICC(2,1) 与自助法区间、缺口。
- 本工具是**翻译**：把那份统计搬到 skill-creator 的字段上（`winner / reasoning / rubric /
  output_quality / expectation_results`），让盲评结果能进同一个人评页与分析流程。

翻译规则全部写死在下面的常量里，不做「看起来合理」的推断：

| comparison.json | 本项目的来源 |
|---|---|
| `rubric.*.content` | `narrative`（叙事）+ `completeness`（完成度），原值 1–7，不缩放 |
| `rubric.*.structure` | `focus`（焦点）+ `composition`（构图）+ `typography`（中文排版） |
| `rubric.*.overall_score` | 五维均值的均值，**保留 1–7 原尺度**并显式写明 `scale` |
| `output_quality.*.strengths/weaknesses` | 与对手相比领先/落后 ≥0.5 分的维度（比较式，不是绝对值） |
| `expectation_results` | **只有**给了 `--grading` 才写；没有断言就不编断言 |
| `identity` | 默认不写（盲评就该盲）；`--unblind` 才附 |

注意：skill-creator 的 `generate_review.py` **不读** `comparison.json`（那个文件是喂给
LLM analyzer 的）。要让人评页看到盲评结果，用本工具的 `annotate()` / `--benchmark`：
它把要点按固定前缀并进 `benchmark.json` 的 notes，并把 `comparison_summary` 写进
`analysis.json`——两步都是确定性搬运，不引入模型。

用法：
    python tools/blind_to_comparison.py --key pack.key.json --scores r1.csv r2.csv r3.csv
    python tools/blind_to_comparison.py ... --pair V01,V02 --out comparison.json --unblind
    python tools/blind_to_comparison.py ... --out cmp.json \
        --benchmark evals-workspace/iteration-1/benchmark.json \
        --analysis evals-workspace/iteration-1/analysis.json
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bench  # noqa: E402

CONTENT_DIMS = ("narrative", "completeness")
STRUCTURE_DIMS = ("focus", "composition", "typography")
DELTA = 0.5          # 维度差达到半档才算「优势/劣势」，避免把 0.1 分说成优点


def _means(report: dict, items_map: dict, code: str) -> dict:
    """从 blind_score 的报告里取出某版本的五维均值（报告按作者路径索引）。"""
    path = items_map.get(code, code)
    out = {}
    for dim, cn in bench.BLIND_DIMS_CN.items():
        entry = (report.get("dimensions") or {}).get(cn) or {}
        mean = (entry.get("mean") or {}).get(path)
        if mean is None:
            raise SystemExit(f"报告里没有 {code} 的「{cn}」均值：评审是否覆盖了全部版本？")
        out[dim] = float(mean)
    return out


def _rubric(scores: dict) -> dict:
    content = {d: scores[d] for d in CONTENT_DIMS}
    structure = {d: scores[d] for d in STRUCTURE_DIMS}
    return {
        "content": content,
        "structure": structure,
        "content_score": round(sum(content.values()) / len(content), 2),
        "structure_score": round(sum(structure.values()) / len(structure), 2),
        "overall_score": round(sum(scores.values()) / len(scores), 2),
    }


def _quality(scores: dict, other: dict) -> dict:
    better = [d for d in scores if scores[d] - other[d] >= DELTA]
    worse = [d for d in scores if other[d] - scores[d] >= DELTA]
    fmt = lambda dims, sign: [f"{bench.BLIND_DIMS_CN[d]} {sign}{abs(scores[d] - other[d]):.2f}"  # noqa: E731
                              for d in sorted(dims, key=lambda d: -abs(scores[d] - other[d]))]
    return {"score": round(sum(scores.values()) / len(scores), 2),
            "strengths": fmt(better, "+") or ["无显著领先维度（差距 < 半档）"],
            "weaknesses": fmt(worse, "-") or ["无显著落后维度（差距 < 半档）"]}


def _reasons(sheets: list[str]) -> dict:
    """逐条抄回评审写的原话（verbatim），不做归类也不做摘要。"""
    notes: dict[str, list[str]] = {}
    for path in sheets:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                item = (row.get("item") or "").strip()
                text = (row.get("reason") or "").strip()
                if item and text:
                    notes.setdefault(item, []).append(text)
    return notes


def build(key_path: str, sheets: list[str], pair: tuple[str, str] | None = None,
          unblind: bool = False, grading: dict | None = None) -> dict:
    key = json.loads(pathlib.Path(key_path).read_text(encoding="utf-8"))
    items_map = bench._blind_key_items(key)
    report = bench.blind_score(sheets, key_path)

    codes = sorted(items_map)
    if pair is None:
        if len(codes) != 2:
            raise SystemExit(f"盲评里有 {len(codes)} 个版本（{codes}）；两两比较必须显式给 --pair A,B")
        pair = (codes[0], codes[1])
    for code in pair:
        if code not in items_map:
            raise SystemExit(f"key 里没有版本 {code}")

    a, b = pair
    sa, sb = _means(report, items_map, a), _means(report, items_map, b)
    overall_a, overall_b = _rubric(sa)["overall_score"], _rubric(sb)["overall_score"]
    winner = "tie" if abs(overall_a - overall_b) < 1e-9 else ("A" if overall_a > overall_b else "B")

    reviewers = report.get("reviewers", 0)
    consensus = report.get("consensus")
    weak_evidence = reviewers < 3 or consensus not in ("CONSENSUS_SUPPORTED",)
    deltas = {d: round(sa[d] - sb[d], 2) for d in sa}
    reason_parts = [
        f"A={a} 总分 {overall_a} / B={b} 总分 {overall_b}（1–7 原尺度，五维均值）",
        "维度差（A−B）：" + "、".join(f"{bench.BLIND_DIMS_CN[d]} {deltas[d]:+.2f}" for d in sa),
        f"评审 {reviewers} 位，一致性={consensus}",
    ]
    if weak_evidence:
        reason_parts.append(
            "证据不足：不足三位完整评审或未达共识线，**这次比较不能当作版本优劣的结论**，"
            "只能当作下一轮改进的方向提示")
    if not any(abs(v) >= DELTA for v in deltas.values()):
        reason_parts.append("两版在所有维度上的差距都小于半档：不要据此宣称任一版本更好")
    notes = _reasons(sheets)

    result = {
        "winner": winner,
        "reasoning": "；".join(reason_parts),
        "rubric": {"A": _rubric(sa), "B": _rubric(sb)},
        "output_quality": {"A": _quality(sa, sb), "B": _quality(sb, sa)},
        "scale": "1-7（1 严重不足 / 4 及格线 / 7 优秀）· 均值，未做任何重新缩放",
        "confidence": "low" if weak_evidence else "normal",
        "reviewers": reviewers,
        "consensus": consensus,
        "dimension_means": {"A": sa, "B": sb},
        "reviewer_notes": notes,
        "source": {"key": pathlib.Path(key_path).name, "sheets": [pathlib.Path(s).name for s in sheets],
                   "tool": "blind_to_comparison/1"},
    }
    if unblind:
        result["identity"] = {"A": items_map.get(a), "B": items_map.get(b)}
        result["identity"]["note"] = ("仅有 --unblind 时才写；发给评审者或进人评页的那个版本必须不含本字段")
    if grading:
        result["expectation_results"] = grading
    return result


NOTE_PREFIX = "盲评（匿名 A/B）"


def annotate(comparison: dict, benchmark_path: str | None = None,
             analysis_path: str | None = None) -> dict:
    """把 blind 结果落到**同一个人评页**：写 analysis.json，并把要点并进 benchmark.json 的 notes。

    为什么要绕这一层：`generate_review.py` 只读 `grading.json` 与 `benchmark.json`，
    不读 `comparison.json`（后者原设计是喂给 LLM analyzer 的）。此处用确定性代码
    生成 `comparison_summary` 与 notes，不让模型参与搬运——结论和理由都还是统计与
    评审原话，只是换了读者能看到的入口。

    幂等：所有写入的 note 都带固定前缀，重复运行先删旧条再追加，不会越跑越长。
    """
    written = {}
    summary = {
        "winner": comparison["winner"],
        "winner_skill": (comparison.get("identity") or {}).get("A") or "未揭盲",
        "loser_skill": (comparison.get("identity") or {}).get("B") or "未揭盲",
        "comparator_reasoning": comparison["reasoning"],
    }
    doc = {
        "comparison_summary": summary,
        "winner_strengths": comparison["output_quality"]["A"]["strengths"],
        "loser_weaknesses": comparison["output_quality"]["B"]["weaknesses"],
        "confidence": comparison["confidence"],
        "reviewers": comparison["reviewers"],
        "consensus": comparison.get("consensus"),
        "scale": comparison["scale"],
        "rubric": comparison["rubric"],
        "reviewer_notes": comparison["reviewer_notes"],
        "generated_by": "tools/blind_to_comparison.py（确定性搬运，无模型参与）",
        "source": comparison.get("source"),
    }
    if analysis_path:
        pathlib.Path(analysis_path).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written["analysis"] = str(analysis_path)

    if benchmark_path:
        path = pathlib.Path(benchmark_path)
        bench_doc = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        notes = [n for n in (bench_doc.get("notes") or [])
                 if not (isinstance(n, str) and n.startswith(NOTE_PREFIX))]
        a, b = comparison["rubric"]["A"]["overall_score"], comparison["rubric"]["B"]["overall_score"]
        notes += [
            f"{NOTE_PREFIX}：A 总分 {a} / B 总分 {b}（1–7 原尺度，五维均值）→ winner={comparison['winner']}",
            f"{NOTE_PREFIX}：评审 {comparison['reviewers']} 位，一致性={comparison.get('consensus')}，"
            f"置信度={comparison['confidence']}",
        ]
        if comparison["confidence"] != "normal":
            notes.append(f"{NOTE_PREFIX}：评审不足三位或未达共识线，"
                         "这次比较只能当改进方向，不能当版本优劣结论")
        notes.append(f"{NOTE_PREFIX}：逐维均值与评审原话见 analysis.json；"
                     "评分材料是匿名代号，揭盲需要 key 文件")
        bench_doc["notes"] = notes
        path.write_text(json.dumps(bench_doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        written["benchmark"] = str(path)
    return written


def _grading_map(pairs: list[str]) -> dict:
    """--grading A=grading.json → 断言通过数；只做搬运，不改判定。"""
    out = {}
    for pair in pairs or []:
        code, _, path = pair.partition("=")
        if not path:
            raise SystemExit(f"--grading 需要形如 A=path/to/grading.json，收到 {pair!r}")
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        summary = data.get("summary") or {}
        out[code] = {"passed": summary.get("passed", 0), "total": summary.get("total", 0),
                     "pass_rate": summary.get("pass_rate", 0.0),
                     "details": [{"text": r.get("text"), "passed": r.get("passed")}
                                 for r in (data.get("expectations") or [])]}
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--key", required=True)
    parser.add_argument("--scores", nargs="+", required=True)
    parser.add_argument("--pair", default=None, help="A,B 两个盲评代号（默认要求恰好两个版本）")
    parser.add_argument("--out", default=None, help="写到哪里（默认打印）")
    parser.add_argument("--unblind", action="store_true", help="附上代号→原路径的映射（别发给评审者）")
    parser.add_argument("--grading", nargs="*", default=None, help="A=grading.json，附断言结果")
    parser.add_argument("--benchmark", default=None,
                        help="把要点并进这个人评页读的 benchmark.json（notes 分段替换，幂等）")
    parser.add_argument("--analysis", default=None, help="写 analysis.json（人评页/分析流程的入口）")
    args = parser.parse_args(argv)

    pair = tuple(x.strip() for x in args.pair.split(",")) if args.pair else None
    if pair and len(pair) != 2:
        raise SystemExit("--pair 需要两个代号，例如 V01,V02")
    result = build(args.key, args.scores, pair, args.unblind, _grading_map(args.grading))
    if args.benchmark or args.analysis:
        for label, path in annotate(result, args.benchmark, args.analysis).items():
            print(f"{label} → {path}")
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"comparison.json → {args.out}")
        print(f"winner={result['winner']} · confidence={result['confidence']} · "
              f"reviewers={result['reviewers']} · consensus={result['consensus']}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
