# 盲评链路演示（**合成评分，不是评审证据**）

这个目录只为一件事存在：证明「盲评包 → 统计 → `comparison.json` → 同一个人评页」这条
链路是通的，且中途没有让模型替人打分。

## 里面是什么

| 文件 | 来源 | 能不能当证据 |
|---|---|---|
| `comparison.json` | `tools/blind_to_comparison.py` 读 `evals/fixtures/blind/*.csv` 生成 | **不能**：分数是夹具里手写的 |
| `analysis.json` | 同一份 comparison 的确定性搬运（`comparison_summary` + 原话） | 不能，同上 |
| `benchmark.json` | `iteration-1/benchmark.json` 的副本 + 三条 `盲评（匿名 A/B）` notes | 统计部分是真的；notes 部分是合成的 |
| `review.html` | `generate_review.py --static` 用上面这份 benchmark 渲染 | 页面结构可看；Benchmark 页的盲评 notes 是合成数据 |
| `feedback.json` / `feedback_intake.md` / `feedback_log.json` | 手写两条人评回执跑 `tools/feedback_intake.py` | 回执是假的，只演示表格与去重 |

## 真实链路怎么跑

```bash
# 1. 打包（评审目录里只有匿名代号 + 空白评分表 + 说明；key 落在目录外）
python scripts/bench.py blind pack /tmp/pack-v1 <A 的产物目录> <B 的产物目录> --scrub-previews
# 2. 把 /tmp/pack-v1 发给 ≥3 位评审，各自填 score_sheet.csv 后单独回传
# 3. 统计
python scripts/bench.py blind score r1.csv r2.csv r3.csv --key /tmp/pack-v1.key.json
# 4. 翻译成人评页能读的两种文件
python tools/blind_to_comparison.py --key /tmp/pack-v1.key.json --scores r1.csv r2.csv r3.csv \
    --out evals-workspace/iteration-2/comparison.json \
    --benchmark evals-workspace/iteration-2/benchmark.json \
    --analysis evals-workspace/iteration-2/analysis.json
# 5. 人看
python /home/user/skill-creator/eval-viewer/generate_review.py evals-workspace/iteration-2 \
    --skill-name ppt-visual-art-director-os \
    --benchmark evals-workspace/iteration-2/benchmark.json --static evals-workspace/iteration-2/review.html
```

## 现在**没有**的东西（别把上面的链路读成已有结论）

- 没有真人评审：`iteration-1` 的 `review.html` 至今没有被任何人类看过一眼。
- 没有触发率测量（无 `claude` CLI / API key），触发层仍是「未测量」。
- 没有模型基线：naive 是引擎直排基线，不是「不加这个 skill 的模型」基线。
- 评审不足三位或未达共识线时，`comparison.json` 会写 `confidence: "low"` 并在
  `reasoning` 里明说「不能当版本优劣的结论」——这是设计行为，不是可忽略的提示。
