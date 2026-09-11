# Production Contract（运行时契约 · 唯一权威表）

三层各答一问：QA 答「能不能正确交付」（PASS/FAIL/WARNING）；Critic 答「有没有高级设计价值」；Design Intelligence 答「该怎么做、会挂在哪里」。同一事实只判一次。

## Contract Map（写 spec 前查这张表）

| 任务 | 契约（到此为止） |
|---|---|
| 文本 | `text` 放内容，样式平铺顶层（`size/color/bold/align/max_lines/line_height/padding`）；框高 ≥ 字号×行高×行数 |
| 填充 | `{"fill":{"type":"solid\|gradient\|none",...}}`；无效 fill 报编译错误，不静默回退 |
| 图表数据 | 每行 `label` + 有限 `value`；`source/unit/period/basis` 缺一即 error；同 metric 全 deck 同单位；标题写洞察 |
| focus | 每页唯一 `page_intent.focus`；焦点 ≥40px 或领先第二大字 1.25×；落任一轴线（1/4·1/3·1/2·2/3·3/4·0.382/0.618） |
| 密度节奏 | sparse ≤0.60 / balanced 0.65–0.75 / dense 0.75–0.85（几何占用）；相邻同密度页墨迹差 ≥0.10 |
| 记忆锚点 | ≥40px 文本 / 图表 `highlight` / 环心 KPI / `target` 线 / sparkline / hero 图（图表内部大数字不算） |
| 色彩 | 声明 `color_intent:[brand,emotion,hierarchy]`；Accent ≤5%（实测）；色相族 ≤4；Accent 与主色相差 ≥12° |
| 网格 | 1280×720，8 单位自动吸附；`grid_exempt:true` 可豁免 |
| 媒体 | 图须有功能（context/emotion/proof/hero）；数据/表格/流程/结构页不出图；背景画心免检需覆盖 ≥60% + 遮罩 ≥0.20 |
| 可读性 | 实测文字 vs 下方像素：正文 <4.5:1 提示，任何角色 <3:1 阻断 |
| 风险策略 | 起草前读 `forecast_risk` 政策，落稿后按 `risk_strategy` 修单改；建议不是闸门 |
| 修订 | 1 根因 = 1 轮：修 `director_verdict.primary_lever` 同组杠杆，其余排队 |
| 发布 | `--mode release`：QA ≥90 且 Critic ≥90 且 0 阻断 且全量像素；报告盖 `source_spec_hash` |

## Calls（最小稳定 API）

```python
from qa import run_qa, verdict_of          # run_qa(spec,out,mode=...) 是唯一执行入口
qa = run_qa(spec, "o.pptx")                # 默认 draft；review/release 才渲染+Critic
from route import plan_deck, one_pass_plan # 内容 → 家族/密度/预算/执行模式
from design_intelligence import analyze, forecast_risk, risk_strategy, color_plan
from layout_search import recommend        # 标准家族直达，复杂页三候选
from art_critic import critique_deck       # 只在 review/release 消费
```

`run_qa` 内联 normalizer→guard→compile→render，不要再串行跑单脚本（除非看独立诊断）。CLI：`qa.py <build> <out> --mode spec|sketch|draft|review|release [--critic on|off] [--no-cache]`；`guard.py --preflight` 是诊断报告，不拦渲染。

## Spec minimum

```python
spec = {"canvas": {"width":1280,"height":720,"grid_columns":12,"grid_unit":8},
 "theme": {"colors":{...},"fonts":{...},"constraints":{...}},
 "strategy": {...}, "direction": {...},
 "slides": [{"id":"s01","page_intent":{...},
  "source_zone": {"x":48,"y":672,"width":1184,"height":32},
  "background": {...}, "elements": [...]}]}
```

每页 `page_intent` 含 `insight/focus/reading_order/energy/density/empty_space_role/page_family/rhythm_stage/continuity_token`；`direction` 含 `color_intent`。几何：所有可见对象数值 `x/y/width/height`；text–text/chart/image 墨迹相交即 `OVERLAP`（来源区/结论/读数永不许遮挡）；图表标签放不下用 `label_collision_policy:hide_redundant|move_outside|fail`，不缩字号。

图表色走语义角色（`theme.chart_palette`：primary/secondary/neutral/accent/negative；元素 `color_role/series_roles`；柱状负值自动染 negative）。背景画心声明 `layer:background` + 自带 `overlay` 内容保护，不计媒体预算；资格不足按普通对象判。

## Failure codes

| 代码 | 动作 |
|---|---|
| `INPUT_MISSING` `INTENT_UNCLEAR` `READABILITY_FAIL` `DATA_INTEGRITY_FAIL` `OVERLAP` `SOURCE_COLLISION` `CHART_LABEL_COLLISION` `TEXT_OVERFLOW` `COMPILE_FAIL` `GUARD_FAIL` | BLOCKED |
| `THEME_MISMATCH` `FOCUS_COMPETING` `MEDIA_UNJUSTIFIED` `RHYTHM_FLAT` `CARD_WALL` `CRITIC_LOW` `PIXEL_COVERAGE_PARTIAL` | REVISE |
| `RENDER_UNAVAILABLE` | PREVIEW_ONLY |
| `BG_UNPROTECTED` | warn（不阻断） |

状态优先级：阻断 → BLOCKED；无阻断缺渲染 → PREVIEW_ONLY；可修复 → REVISE；全满足 → PASS。Guard 的设计观察（`DESIGN_RULES` 17 项）权重恒 0：只提示评审视角，不扣分、不阻断、不以 error 出现。

## Release Manifest

`qa.py --mode release` 生成：`source_spec_hash`（QA/Critic 报告交叉校验，对不上 → BLOCKED）+ `verification`（qa_level/pixel 覆盖/release_eligible）+ `compile/qa/critic` 报告 + `revision_log`（observation/minimal_fix/recheck，引用失败码与页 ID）+ `status`。`revision_count` 来自真实修订流水。

实现口径以代码为真源；历史决策见 `CHANGELOG.md`（备查，不进入生成上下文）。
