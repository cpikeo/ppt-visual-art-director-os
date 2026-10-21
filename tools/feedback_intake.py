"""把人评页导出的 `feedback.json` 收进来，变成一张可执行的待办表。

为什么不让工具自动分类：评审者写的是「末页那个数字看不清」，把它自动归到
「视觉/排版/判断」哪一层，是猜。工具只做三件确定的事：

1. **对齐**：`run_id` → 用例名 + 配置（with_skill / naive），避免"第 3 条反馈"这种无法追溯的记法。
2. **原话保留**：反馈文本逐字抄录，不改写、不摘要、不做情感判断。
3. **缺口显式**：空反馈不是"没问题"，是"这位评审对这条没意见"——分开记，不混进通过数。

输出：

- `<iteration>/feedback_intake.md` —— 给人看的待办表（`归属层` 一列留空，由人填）
- `<iteration>/feedback_log.json` —— 给机器看的追加日志（按 run_id+timestamp 去重）

用法：
    python tools/feedback_intake.py evals-workspace/iteration-1
    python tools/feedback_intake.py evals-workspace/iteration-1 --feedback ~/Downloads/feedback.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run_key(iteration_dir: pathlib.Path, run_dir: pathlib.Path) -> str:
    """与 eval-viewer 的 run_id 规则一致：相对路径把分隔符换成短横。"""
    return run_dir.relative_to(iteration_dir).as_posix().replace("/", "-")


def _load_runs(iteration_dir: pathlib.Path) -> dict[str, dict]:
    runs = {}
    for run_dir in sorted(iteration_dir.glob("eval-*/**/run-*")):
        if not run_dir.is_dir():
            continue
        metadata = {}
        for candidate in (run_dir / "eval_metadata.json",
                          run_dir.parent / "eval_metadata.json"):
            if candidate.is_file():
                metadata = json.loads(candidate.read_text(encoding="utf-8"))
                break
        config = run_dir.parent.name
        runs[_run_key(iteration_dir, run_dir)] = {
            "run_id": _run_key(iteration_dir, run_dir),
            "eval_id": metadata.get("eval_id"),
            "eval_name": metadata.get("eval_name") or run_dir.parent.parent.name,
            "config": config,
            "prompt": metadata.get("prompt", ""),
            "dir": str(run_dir.relative_to(iteration_dir)),
        }
    return runs


def _reviews(feedback: dict) -> list[dict]:
    reviews = feedback.get("reviews") if isinstance(feedback, dict) else None
    if not isinstance(reviews, list):
        raise SystemExit("feedback.json 里没有 reviews 数组（人评页导出的格式是 "
                         "{\"reviews\": [{\"run_id\", \"feedback\", \"timestamp\"}], \"status\"}）")
    out = []
    for item in reviews:
        if not isinstance(item, dict) or "run_id" not in item:
            raise SystemExit(f"反馈条目缺 run_id：{item!r}")
        out.append({"run_id": str(item["run_id"]),
                    "feedback": (item.get("feedback") or "").strip(),
                    "timestamp": item.get("timestamp") or ""})
    return out


def intake(iteration_dir: pathlib.Path, feedback_path: pathlib.Path | None = None) -> dict:
    runs = _load_runs(iteration_dir)
    path = feedback_path or (iteration_dir / "feedback.json")
    if not path.is_file():
        return {"status": "NO_FEEDBACK_FILE", "path": str(path), "runs": len(runs),
                "instruction": ("人评页点「Submit All Reviews」会下载 feedback.json；"
                                "把它放进本轮目录后重跑本工具")}
    data = json.loads(path.read_text(encoding="utf-8"))
    reviews = _reviews(data)

    unknown = [r["run_id"] for r in reviews if r["run_id"] not in runs]
    rows = []
    for review in reviews:
        run = runs.get(review["run_id"], {})
        empty = not review["feedback"]
        rows.append({**review, "eval_name": run.get("eval_name", "(未知用例)"),
                     "eval_id": run.get("eval_id"), "config": run.get("config", "?"),
                     "verdict": "无意见（按通过记录，不算证据）" if empty else "有具体意见",
                     "layer": "", "status": "未处理"})

    log_path = iteration_dir / "feedback_log.json"
    log = []
    if log_path.is_file():
        log = json.loads(log_path.read_text(encoding="utf-8"))
    seen = {(entry["run_id"], entry.get("timestamp")) for entry in log}
    added = 0
    for row in rows:
        if (row["run_id"], row.get("timestamp")) not in seen:
            log.append({**row, "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            added += 1
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    md = [f"# 人评回执 · {iteration_dir.name}", "",
          f"- 收到的反馈文件：`{path.name}` · 条目 {len(rows)} 条（新增 {added} 条）",
          f"- 其中无意见 {sum(1 for r in rows if not r['feedback'])} 条",
          f"- 状态：{data.get('status', '(未标注)')}",
          ""]
    if unknown:
        md += [f"> ⚠ {len(unknown)} 条 run_id 在本轮目录里找不到对应运行："
               + "、".join(f"`{u}`" for u in unknown)
               + "。可能是换了迭代目录——按 run_id 对齐，不要猜。", ""]
    empty_reviews = [r for r in rows if not r["feedback"]]
    if empty_reviews and len(empty_reviews) == len(rows):
        md += ["> 全部条目为空：按 skill-creator 的口径这算「看起来没问题」，",
               "> 但仍不等于视觉质量已验证——它只说明这位评审没提出具体意见。", ""]
    md += ["| run_id | 用例 | 配置 | 反馈（原话） | 归属层（人填） | 状态 |",
           "|---|---|---|---|---|---|"]
    for row in rows:
        text = row["feedback"].replace("|", "\\|").replace("\n", " ") or "—"
        md.append(f"| `{row['run_id']}` | {row['eval_name']} | {row['config']} | {text} |  | {row['status']} |")
    md += ["", "## 怎么处理这张表", "",
           "1. `归属层` 只有人能填：判断协议（SKILL）/ 可调策略（policy）/ 契约（schema）/ "
           "文案（文档）/ 视觉（人评）。工具不猜。",
           "2. 具体意见先进下一轮用例：能在 `evals/` 或 `scripts/json/` 里复现的，先加用例再改代码。",
           "3. 空反馈**不写进通过数**：它是「无意见」，不是「已验证」。",
           "4. 处理完把 `状态` 改成 已修 / 转下轮 / 不采用（写明理由）。"]
    intake_path = iteration_dir / "feedback_intake.md"
    intake_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return {"status": "OK", "reviews": len(rows), "empty": len(empty_reviews),
            "unknown_run_ids": unknown, "markdown": str(intake_path), "log": str(log_path),
            "added": added}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("iteration", help="形如 evals-workspace/iteration-1")
    parser.add_argument("--feedback", default=None, help="feedback.json 路径（默认在本轮目录里找）")
    args = parser.parse_args(argv)
    result = intake(pathlib.Path(args.iteration).expanduser().resolve(),
                    pathlib.Path(args.feedback).expanduser().resolve() if args.feedback else None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
