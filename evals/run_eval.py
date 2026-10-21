"""跑一轮任务级评测，产出 skill-creator 能直接吃的目录与文件。

目录形状（同时满足它的 aggregate_benchmark 与 eval-viewer）：

    <workspace>/iteration-<N>/eval-<id>-<name>/
        eval_metadata.json                 # 人看的用例信息
        with_skill/run-1/
            eval_metadata.json             # 副本：viewer 只在 run 目录或父目录找 prompt
            grading.json                   # text / passed / evidence
            timing.json
            outputs/plan.json, deck.pptx, preview-*.png, facts.json
        naive/run-1/…

两种配置：

- `with_skill`：完整判断层 + guard/编译/预览。
- `naive`：`evals/baseline_build.py` 的**无判断直排**。这是 engine-baseline，
  不是 model-baseline——没有模型参与，不能读成「人不用技能会怎样」。

用法：
    python evals/run_eval.py                      # 两种配置，iteration-1
    python evals/run_eval.py --config with_skill --iteration 2
    python evals/run_eval.py --only 5,6           # 只跑带产物的两条
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
sys.path.insert(0, str(EVALS))
sys.path.insert(0, str(ROOT / "scripts"))

import facts as facts_mod          # noqa: E402
import grade as grade_mod          # noqa: E402
import baseline_build              # noqa: E402

CONFIGS = ("with_skill", "naive")


def _metadata(case: dict) -> dict:
    return {"eval_id": case["id"], "eval_name": case["name"], "prompt": case["prompt"],
            "assertions": [c.get("label") or c["kind"] for c in case.get("checks") or []],
            "expected_output": case.get("expected_output", ""),
            "brief": case.get("brief"), "build": case.get("build")}


def run_case(case: dict, config: str, iteration_dir: pathlib.Path) -> dict:
    eval_dir = iteration_dir / f"eval-{case['id']}-{case['name']}"
    run_dir = eval_dir / config / "run-1"
    outputs = run_dir / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    meta = _metadata(case)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (run_dir / "eval_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    brief = ROOT / case["brief"]
    if config == "with_skill":
        build = ROOT / case["build"] if case.get("build") else None
        collected = facts_mod.collect(brief, run_dir, build)
    else:
        spec_path = run_dir / "outputs" / "baseline-spec.json"
        spec_path.write_text(json.dumps(baseline_build.build_from_path(brief),
                                        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        collected = facts_mod.collect(brief, run_dir, spec_path, run_plan=False)
        if not case.get("build"):
            collected["verdict"] = None          # 基线也只在有夹具的用例上比产物

    (run_dir / "outputs" / "facts.json").write_text(
        json.dumps(collected, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    graded = grade_mod.grade([case], {case["id"]: collected}, config)[0]
    (run_dir / "grading.json").write_text(
        json.dumps(graded, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    timing = {"total_tokens": None,
              "duration_ms": int((graded["timing"]["total_duration_seconds"] or 0) * 1000),
              "total_duration_seconds": graded["timing"]["total_duration_seconds"],
              "note": "确定性引擎运行，无模型参与；token 成本不适用"}
    (run_dir / "timing.json").write_text(json.dumps(timing, ensure_ascii=False, indent=1) + "\n",
                                         encoding="utf-8")
    # 预览目录不重复进 outputs（viewer 只列第一层文件）
    preview = outputs / "preview"
    if preview.is_dir():
        shutil.rmtree(preview)
    for meta_file in ("deck.manifest.json",):
        if (outputs / meta_file).exists():
            (outputs / meta_file).unlink()
    return graded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--config", choices=CONFIGS + ("both",), default="both")
    parser.add_argument("--workspace", default=str(ROOT / "evals-workspace"))
    parser.add_argument("--only", default=None, help="逗号分隔的 eval id")
    args = parser.parse_args(argv)

    data = json.loads((EVALS / "evals.json").read_text(encoding="utf-8"))
    cases = data["evals"]
    if args.only:
        wanted = {int(x) for x in args.only.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in wanted]

    iteration_dir = pathlib.Path(args.workspace).expanduser().resolve() / f"iteration-{args.iteration}"
    configs = CONFIGS if args.config == "both" else (args.config,)
    started = time.time()
    summary = {}
    for config in configs:
        rows = []
        for case in cases:
            # 配置间比较只在**同一层**上做：naive 基线没有判断层，而 release 层需要
            # 作者写的 build 夹具。没有夹具的用例只跑 with_skill，否则合并统计会把
            # 「没东西可评」记成「评了 0 分」——上一版就是这样把 72.7% 算成 20.9% 的。
            if config != "with_skill" and not case.get("build"):
                print(f"[{config:10}] eval-{case['id']} {case['name']:<16} 跳过（无 build 夹具，无法对齐 release 层）")
                continue
            graded = run_case(case, config, iteration_dir)
            rows.append(graded)
            print(f"[{config:10}] eval-{case['id']} {case['name']:<16} "
                  f"{graded['summary']['passed']}/{graded['summary']['total']} "
                  f"· {graded['timing']['total_duration_seconds']}s")
        evaluated = [r for r in rows if r["summary"]["total"]]
        passed = sum(r["summary"]["passed"] for r in evaluated)
        total = sum(r["summary"]["total"] for r in evaluated)
        summary[config] = {"passed": passed, "total": total,
                           "evaluated_evals": len(evaluated),
                           "skipped_evals": len(rows) - len(evaluated),
                           "pass_rate": round(passed / total, 4) if total else 0.0}
        print(f"[{config:10}] 合计 {passed}/{total} · {summary[config]['pass_rate']:.1%}"
              f"（评估 {len(evaluated)} 条，接口层不适用 {len(rows) - len(evaluated)} 条）")

    # 对齐比较：只取两种配置**都评过**的层（release）。跨配置比较必须同层，
    # 否则「with_skill 多评了 4 条 plan 断言」会被读成「判断层更差/更好」。
    aligned = {}
    for config in configs:
        p = t_ = 0
        for path in sorted(iteration_dir.glob(f"eval-*/{config}/run-1/grading.json")):
            grading = json.loads(path.read_text(encoding="utf-8"))
            for row in grading.get("expectations") or []:
                if row.get("layer") != "release":
                    continue
                p += int(bool(row.get("passed")))
                t_ += 1
        if t_:
            aligned[config] = {"passed": p, "total": t_, "pass_rate": round(p / t_, 4)}
    result = {"iteration": args.iteration, "workspace": str(iteration_dir),
              "aligned_release_layer": aligned,
              "seconds": round(time.time() - started, 2), "summary": summary,
              "baseline_kind": "engine-baseline（无判断直排，不是 model-baseline）"}
    (iteration_dir / "run_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
