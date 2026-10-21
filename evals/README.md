# evals/ · 任务级评测层

`scripts/json/` 与 `evals/` 是**两条不同的轴**，不许互相替代：

| | `scripts/json/`（122 例） | `evals/`（7 例） |
|---|---|---|
| 测什么 | 这一页**判成什么**（角色/证据/形态/聚焦/构图） | 给一份 brief，**整条链产出了什么** |
| 输入 | 一段标题 + 正文 | 一份 brief（+ 可选 build 夹具） |
| 判定 | `bench.py` / `unseen_bench.py` 的断言 | `evals/grade.py` 的确定性断言 |
| 失败含义 | 判断规则错了 | 任务交付不了（PASS/图表/出处/预览） |
| 谁在守 | CI、守门审计（把判据调坏） | CI（本目录 + `run_summary.json` 断言） |

## 跑一轮

```bash
python evals/run_eval.py                     # with_skill + naive，写入 evals-workspace/iteration-1
python evals/run_eval.py --config with_skill --iteration 2
python evals/run_eval.py --only 5,6          # 只跑带产物夹具的两条
```

产物目录形状同时满足 skill-creator 的 `aggregate_benchmark.py` 与 `eval-viewer/generate_review.py`：

```
evals-workspace/iteration-N/eval-<id>-<name>/
  eval_metadata.json
  with_skill/run-1/{grading.json, timing.json, eval_metadata.json, outputs/}
  naive/run-1/…
```

```bash
# 统计（在 skill-creator 仓库里跑）
python -m scripts.aggregate_benchmark <repo>/evals-workspace/iteration-1 --skill-name ppt-visual-art-director-os
# 人评页（单文件 HTML，PNG 内联）
python eval-viewer/generate_review.py <repo>/evals-workspace/iteration-1 \
  --skill-name ppt-visual-art-director-os \
  --benchmark <repo>/evals-workspace/iteration-1/benchmark.json \
  --static <repo>/evals-workspace/iteration-1/review.html
```

## 两个配置是什么

- `with_skill`：完整判断层 + guard/编译/预览。
- `naive`：`baseline_build.py` 的**无判断直排**（标题 + 正文两段，不选角色、不写出处、
  不生成图表）。这是 **engine-baseline，不是 model-baseline**：没有模型参与，不能读成
  「人不用这个技能时会怎样」。它只衡量**判断层贡献了多少可测差异**。

`naive` 只在有 `build` 夹具的用例上跑——两条配置必须评同一层；否则「没东西可评」会被
统计成「评了 0 分」（第一版就是这样把 72.7% 算成了 20.9%）。

## 当前的数（iteration-1）

| 配置 | 全层 | release 层（两配置对齐） |
|---|---|---|
| with_skill | **50/50** | **11/11** |
| naive | 8/11（只跑 2 条） | 8/11 |

naive 失在两处：**原生图表数**（0）与**出处行**（0）。这两件都是判断层的产出，
不是排版层的产出——这也是这层评测存在的意义。

## 什么不算「通过」

- 断言全绿不等于视觉合格：构图好不好、密度对不对，仍然要人看（`review.html` + feedback）。
- 没有模型参与的运行**不产生 token 数据**（`total_tokens` 记为 `null`，基准里显示 0）。
  「省了多少 token」这类结论必须由带模型的对照给出，本层不下这个结论。
- 7 条用例只覆盖七种任务形态，不证明全部场景；新增用例必须先跑、先把期望冻结下来。

## 盲评（人打分）怎么接进来

机器断言只能证明「该有的都在」，证明不了「这页好不好看」。后者要人打分，但人要**盲**着打，
否则评的是版本名而不是产物。

```bash
python scripts/bench.py blind pack /tmp/pack out-a/ out-b/ --scrub-previews
# 评审目录：V01/V02（匿名）+ score_sheet.csv + README.txt；key 落在 /tmp/pack.key.json
python scripts/bench.py blind score r1.csv r2.csv r3.csv --key /tmp/pack.key.json
python tools/blind_to_comparison.py --key /tmp/pack.key.json --scores r1.csv r2.csv r3.csv \
    --out evals-workspace/iteration-2/comparison.json \
    --benchmark evals-workspace/iteration-2/benchmark.json \
    --analysis evals-workspace/iteration-2/analysis.json
```

- **为什么要 `--scrub-previews`**：ghost 预览 PNG 的文本块会带生成工具与作者痕迹；
  打包时重建图像清除元数据（像素不动），否则「盲」只盲了文件名。
- **为什么还要 `--benchmark`/`--analysis`**：`generate_review.py` 不读 `comparison.json`。
  盲评要点必须并进 `benchmark.json` 的 notes（人评页的 Benchmark 页读它），
  `comparison_summary` 写进 `analysis.json`。两步都是确定性搬运，不让模型转述分数。
- **证据强度**：`evals/fixtures/blind/*.csv` 是**手写夹具**，只用来验管道；
  `evals-workspace/blind-demo/` 里的页面同理。**没有任何真人评审记录**。
  评审不足 3 位或未达共识线时，翻译层写 `confidence: "low"` 并明说不能当版本结论。

## 人评回执怎么收口

```bash
# 人评页点 Submit All Reviews 会下载 feedback.json，放进本轮目录后：
python tools/feedback_intake.py evals-workspace/iteration-1
```

生成 `feedback_intake.md`（原话照抄 + 只有人能填的「归属层」列）与 `feedback_log.json`
（按 `run_id+timestamp` 去重）。三条纪律写死在代码里：空反馈记「无意见」但**不进通过数**；
未知 `run_id` 报警不静默丢弃；没有 `feedback.json` 时状态 `NO_FEEDBACK_FILE`（退 2）。
