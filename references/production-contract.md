# Production Contract（运行时契约 · 唯一权威表）

三层各答一问：QA 判工程交付；Design Intelligence 按需预测（非闸门）；设计价值由人/AI 依 `references/design-craft.md` 判断（v4.15 起无机器评分）。QA 只做工程验证，同一事实只判一次。

## Contract Map（写 spec 前查这张表）

| 任务 | 契约（到此为止） |
|---|---|
| 文本 | `text` 放内容，样式平铺顶层（`size/color/bold/align/max_lines/line_height/padding`）；框高 ≥ 字号×行高×行数 |
| 填充 | `{"fill":{"type":"solid\|gradient\|none",...}}`；无效 fill 报编译错误，不静默回退 |
| 图表数据 | 每行 `label` + 有限 `value`；factual numeric chart 必须齐 `source/unit/period/basis`；draft warn、review/release error（`guard_rules` 可覆盖）；同 metric 同单位；标题写洞察 |
| 编译证据 | `semantic_compile_view` 是输入投影；`artifact_sha256`/`output_sha256` 是本次 PPTX 字节戳，前者不是 ZIP hash |
| focus | 每页唯一 `page_intent.focus`；焦点 ≥40px 或领先第二大字 1.25×；落任一轴线（1/4·1/3·1/2·2/3·3/4·0.382/0.618） |
| 密度节奏 | sparse ≤0.60 / balanced 0.65–0.75 / dense 0.75–0.85（几何占用）；相邻同密度页墨迹差 ≥0.10 |
| 记忆锚点 | ≥40px 文本 / 图表 `highlight` / 环心 KPI / `target` 线 / sparkline / hero 图（图表内部大数字不算） |
| 色彩 | 声明 `color_intent:[brand,emotion,hierarchy]`；Accent ≤5%（实测）；色相族 ≤4；Accent 与主色相差 ≥12° |
| 网格 | 1280×720，8 单位自动吸附；`grid_exempt:true` 可豁免 |
| 媒体 | 图须有功能（context/emotion/proof/hero）；数据/表格/流程/结构页不出图；背景画心免检需覆盖 ≥60% + 遮罩 ≥0.20；资产卡 `family` 填 `direction_seed.family_hint`（审美覆写命中即接桥），水墨语言卡自动过纪律闸门 |
| 资产 QC | `asset_prompt --qc` 只做定性 Issue+Suggestion；阻断项最多自动定向重出 1 次；不会自动触发 review/release，最终资格由 QA/Manifest 判定 |
| 可读性 | 实测文字 vs 下方像素：正文 <4.5:1 提示，任何角色 <3:1 阻断 |
| 风险策略 | 按需读 `forecast_risk`/`risk_strategy`；默认 QA 不运行建议，修正后验证 |
| 修订 | spec 按根因组批量修；draft 只做最小修复，advisory 先取 high-risk 根因 |
| 发布 | `--mode release`：QA ≥90 且 0 阻断 且全量像素（`release_eligible`）；报告盖 `source_spec_hash` |

## Calls（最小稳定 API）

```python
from qa import run_qa, verdict_of          # run_qa(spec,out,mode=...) 是唯一执行入口
qa = run_qa(spec, "o.pptx", mode="draft")  # 显式 draft；review/release 才渲染
from route import plan_deck, one_pass_plan # 内容 → 家族/密度/预算/执行模式
# 仅复杂/新建或明确要求时加载设计建议
from design_intelligence import analyze, forecast_risk, risk_strategy, color_plan
from layout_search import recommend        # 复杂页才做候选搜索
```

默认用 `pipeline.py` 单进程生成 Brief/route/layout/risk；plan 保留
`intent_interpretation` 的 explicit/inferred/conflicts。`run_qa` 内联
normalizer→guard→compile→render，不串行跑单脚本（独立诊断除外）。

advisory 原始 risks 留作追溯，消费以 `root_cause_summary`/`risk_strategy.root_causes`
为先：每个根因给影响页、最多 3 个代表页和首修；`page_details` 不作逐页返工单。
semantic view 判输入/引擎身份，output/artifact SHA 判 PPTX 字节；QA 另记
`cache_reason`、`render_cache_reason`、`output_attestation_ms`。

## Case Authoring Preflight

复杂案例先 `qa.py --mode spec --json`，按根因批量修完
`element_schema/OVERLAP/DATA_INTEGRITY/READABILITY`，再一次 `draft --no-render`；
阶段门：strategy → spec → draft → advisory → review/release。同阶段独立资产 QC、
渲染页和 selftest 可有界并行，但不得并发写 PPTX/cache/revision log，也不得让 advisory 抢跑。

最小约束：geometry 均 `>0`；source/metadata ≥10px；图表 `value` 为有限数字、显示格式放
`display`；每页有 `page_family/focus/source_zone` 且对象不相交。结构通过才跑 advisory，
只修 high-risk/首个根因，不为清空软提示牺牲叙事留白。CLI：`qa.py <build> <out> --mode
spec|sketch|draft|review|release [--no-cache]`；`--advisory` 只产建议，不是发布闸门。

## Spec minimum

```python
spec = {"canvas": {"width":1280,"height":720,"grid_columns":12,"grid_unit":8},
 "theme": {"colors":{...},"fonts":{...},"constraints":{...}},
 "strategy": {...}, "direction": {...},
 "slides": [{"id":"s01","page_intent":{...},
  "source_zone": {"x":64,"y":640,"width":1152,"height":40},
  "background": {...}, "elements": [...]}]}
```

每页 `page_intent` 含 `insight/focus/reading_order/energy/density/empty_space_role/page_family/rhythm_stage/continuity_token`；`direction` 含 `color_intent`。几何：所有可见对象数值 `x/y/width/height`；text–text/chart/image 墨迹相交即 `OVERLAP`（来源区/结论/读数永不许遮挡）；图表标签放不下用 `label_collision_policy:hide_redundant|move_outside|fail`，不缩字号。

来源区（`source_zone`）内文字 `role` 只允许 `{source, method, metadata}`（页码、目录索引、编号等结构性文字挂 `metadata`/`label`）；用其他角色会触发全页 zone-invasion 错误。图像 `src` 相对路径按输出目录解析，找不到时回退到 spec 文件所在目录（绝对路径优先）。

Donut `hole_size` 已修复为真实写入 XML（此前 python-pptx 空类导致无声 no-op）；PowerPoint 遵循该值，LibreOffice 预览忽略（恒按默认孔比渲染）——以 PowerPoint 实际显示为准。

渲染器与交付事实（工程事实，不是品味）：① `char_spacing` 与 `opacity` 互斥——LibreOffice
对 spc ∧ run 级 alpha 并存的 run 静默丢弃尾部字形（XML 完整、仅预览/导出受害）；meta 行要
字距+压低存在感时，把透明度按局部底预混进实色 hex。② 单行 meta 行（眉标/章标/页码/落款）
`wrap=False` 且盒宽 ≥1.5× 估宽——第二行落盒外的裁切在预览里是沉默的。③ `page_intent.focus`
声明**视线第一落点**（英雄图/索引场/主数字），不是叙事主语；重力实测只认眼睛真正落的地方。
④ accent 须与照片色簇保持足够彩度距离（实测归一化 RGB 距离 <0.30 判同族）：大地色/灰调
照片世界里暖铜、赭血、灰蓝均阵亡，仅足彩度钴蓝级存活。

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

`qa.py --mode release` 生成 `source_spec_hash`、`verification`、含 semantic/artifact 证据的 `compile/qa`、`revision_log` 与 `status`；`revision_count` 来自真实流水。无 renderer 必须保持 `PREVIEW_ONLY`，不得以结构分数替代像素证据。

实现口径以代码为真源；历史决策见 `CHANGELOG.md`（备查，不进入生成上下文）。
