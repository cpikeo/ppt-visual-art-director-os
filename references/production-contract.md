# Production Contract

## Runtime architecture

```text
spec → compiler.py → elements.py / charts.py → primitives.py
     → guard.py → render_check.py → qa.py + art_critic.py
```

设计规划阶段读取参考文档并生成完整 `spec`；运行时阶段只处理 `spec`。编译器是编排层，不做设计决策，也不读取 `references/*.md`；元素与图表负责原生可编辑输出；Guard 负责静态硬约束；Render Check 负责像素证据；`qa.py` 负责确定性回归评分；`art_critic.py` 负责结构化审美判断。层间只通过 spec、RenderContext 和 JSON 报告沟通。

### Single-entry execution

优先调用 `qa.run_qa()` 完成一次性流水线：它只加载并调用所需模块、复用同一份 `guard_rules`，并返回 guard / compile / render 的摘要；不要在代理上下文中逐个读取脚本全文，也不要重复运行 `guard` 与 `compile`。仅在调试对应失败域时调用单模块 CLI。所有 CLI 支持 `--json` 时应优先使用 JSON 输出；日志只保留摘要、失败码、页面 ID 和修复建议。`render=False` 或 `--no-render` 只允许快速迭代，不代表发布通过；在没有其他阻断错误时状态为 `PREVIEW_ONLY`，若同时存在阻断错误则按状态优先级返回 `BLOCKED`。

## Stable API

```python
from compiler import compile_deck
report = compile_deck(spec, "output.pptx", checks=True, guard_rules=None)

from qa import run_qa
qa = run_qa(spec, "output.pptx", guard_rules=None, render_dir=None)

from art_critic import critique_deck
critic = critique_deck(spec, render_evidence=qa.get("render_evidence"), evidence_cards=None)

from route import plan_deck, plan_page
plan = plan_deck(brief)                      # 内容 → 路径 / 家族 / 密度 / 资产预算 / 闸门（带决策缓存）
page = plan_page("data", "editorial_brand", "fast")   # 单页决策对象
route.cache_stats(); route.clear_cache()     # 修订循环是否还在重复推导，可核对

from qa import run_qa, key_pages
qa = run_qa(spec, "out.pptx", qa_level=3)    # 1=静态 2=关键页 3=全量（默认，发布口径）
qa = run_qa(spec, "out.pptx", qa_level=2, render_pages=plan["verification"]["pixel_page_ids"])
qa = run_qa(spec, "out.pptx", qa_level=3, dpi=72, workers=2)   # 便宜的完整渲染

from render_check import render_evidence
ev = render_evidence(pptx, spec, out_dir, dpi=96, pages=[1, 5, 12], workers=2,
                     use_cache=True)     # out_dir 稳定时可复用按页指标

from guard import check_spec
result = check_spec(spec)                    # result["preflight"] / ["preflight_codes"]
```

CLI 入口保持兼容，新增默认关闭的开关：`guard.py <module> --preflight`；`qa.py <module> <out.pptx> --fast | --preflight | --quick | --key-pages | --level N`；`render_check.py <pptx> <module> [out_dir] --pages 1,5 --dpi N --workers N`。`run_qa` 新增 `preflight_gate / qa_level / render_pages / workers`，`release_manifest` 新增 `verification` 关键字参数；全部带默认值，未传时与旧版行为一致。返回值只增不减。

`compile_deck` 不自动缩字号、改色、重排、删除内容或替换图片。所有 warnings 必须进入报告。`run_qa` 的 `score` 只表示确定性合规，不得冒充审美分数；`passed` 只是数值门槛结果，最终发布依据是 `status`。编译前先完成 Guard；Guard 存在 error 时仍可为调试生成预览，但发布状态必须为 `BLOCKED`，不得被编译成功覆盖。

## Fill Contract

元素填充统一使用以下 schema；普通字符串仍作为兼容 shorthand：

```json
{"fill": {"type": "solid", "color": "surface", "opacity": 0.30}}
{"fill": {"type": "gradient", "gradient_type": "linear", "angle": 90,
  "stops": [{"position": 0, "color": "#FFFFFF", "opacity": 0.8},
            {"position": 1, "color": "#FFFFFF", "opacity": 0}]}}
{"fill": {"type": "none"}}
```

历史 `{"color": "#fff", "opacity": 0.3}` 和 `{"gradient": {"stops": [...]}}` 由 `elements.normalize_fill()` 兼容迁移后再渲染。无效 type、缺失 color、非法 stop 或无法解析的 token 必须抛出包含 Expected 格式的明确错误；不得静默改成默认蓝色。背景层仍可在 compiler 层安全回退，但必须将原始 warning 写入报告。

## Background Layer Contract

背景按需组织为 `Base → Image → Atmosphere/Light → Content Protection`。不要求每页启用全部层；每个启用层必须服务内容，不能遮蔽主体或抢夺第一注意点。推荐图片压暗 overlay：`{"type":"solid","color":"#000000","opacity":0.35}`。

可执行合同（三条，全部由 Guard / Compiler / Art Critic 共享）：

1. 画心承担空间时声明 `layer: background`（或 `role: background|backdrop`）。`image` 元素可占满整页，**不再被要求拆成两侧留白盒**：它免于 overlap 与 source_zone 侵入检查。
2. 背景画心必须自带内容保护：`overlay`（Fill Contract）或 `content_protection.overlay`。缺失时 Guard 记 `BG_UNPROTECTED` warn，Critic 不给该页叠加可读性加分。声明了但解析不出不透明度的 overlay 按缺失处理（fail-closed）；覆盖率与保护层解析在 `primitives.py` 共享实现，Guard 与 Critic 同一结论。
3. 编译器把声明为背景层的画心稳定前置绘制（z-order 在最底），并在同一盒上追加保护层，因此作者无需记忆元素顺序；背景层不计入 `MEDIA_BUDGET_MAX`，其面积也不参与焦点压制判定。

`qa.py` 的渲染指标仍按像素测量：背景层允许边缘带合法不安静，但 `margin_occupancy` 只应在纯色 / 结构背景主题开启。

## Spec minimum

```python
spec = {
  "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},
  "theme": {"colors": {...}, "fonts": {...}, "constraints": {...}},
  "strategy": {...},
  "direction": {...},
  "slides": [{
    "id": "s01", "page_intent": {...},
    "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
    "background": {...}, "elements": [...]
  }]
}
```

每页至少有 `page_intent.insight`、`focus`、`reading_order`、`energy`、`density`、`empty_space_role`、`page_family`、`rhythm_stage` 和 `continuity_token`；`direction` 应声明 `color_intent: [brand, emotion, hierarchy]`；每个图表至少有单位、期间、比较口径、数据状态、来源和一个强调点；每个图片至少有资产角色、主体、构图、留白锚点、裁切与溯源。布局可在五类页面家族间变化，但必须复用同一 canvas、12 列逻辑网格、8 单位基线、safe zones、source zone、type budget 与 accent budget。文本元素应声明 `max_lines`、`line_height`、`padding`；图表元素应声明 `label_collision_policy`，密集标签不得默认强行显示。

### Layout collision contract

所有可见对象都必须有数值 `x / y / width / height`。文本必须显式声明或可由默认值推导 `padding / line_height / max_lines`；标题、结论、图表标签和来源不得共享同一几何区域。相交规则如下：

1. text–text、text–chart、text–image 的有效墨迹相交即为 `OVERLAP`；默认不允许通过透明度或 z-order 豁免。
2. 需要前景遮挡时，必须在双方声明 `allow_overlap: true`、`overlap_reason` 和 `protected_zone`；来源区、关键结论和图表读数永不允许被遮挡。
3. 文本框外框不等于墨迹框：Guard 使用 `text_ink_ratio / text_ink_v` 估算，渲染 QA 再检查实际视觉占用。右对齐、居中和多行文本应声明 `ink_anchor`，否则按保守左上锚点检查。
4. 图表内部标签应使用 `label_safe_margin`、`label_gap` 和 `label_collision_policy: hide_redundant | move_outside | fail`；不得以缩小字体消除碰撞。无法安全放置时改用直接标注、减少类别、拆页或 `fail`。
5. 左下角 `source_zone` 是独立保留区，主体、图表、图片和装饰不得进入；来源需支持自动换行并在渲染后可读。

### Chart data contract

数值图表的 `data` 必须是非空数组，每行至少包含 `label` 与有限数字 `value`；`display` 只负责已核验的展示格式，不参与计算。`highlight` 必须是有效整数索引；`progress_bar` 的 `max` 必须为正数；`pie`/`donut` 的非负有效值总和必须大于零；`ranked_bar`、`progress_bar`、`stacked_bar` 与 `bubble` 不接受负值。Guard 对这些条件返回 `data_integrity` 或 `chart_highlight`，Compile/Render 不得静默补零、截断负值或虚构单位。

图表渲染器遇到空数据时可以跳过该图表并写入 warning；遇到不可解析数值时可以仅为防止程序崩溃按零计算并保留 warning。**这两种容错只服务调试预览，不表示数据有效；Guard 的 `DATA_INTEGRITY_FAIL` 必须使最终状态为 `BLOCKED`，不得以容错后的图表发布。**瀑布图的零轴必须根据数据域映射，而不是固定在画布某一比例位置。

多序列图表走 `series` 字段（`series: [{name, values:[...]}, ...]` + `categories: [...]`），此时不需要 `data`；它与单序列 `data` 是同一 geometry 的两种数据表达，不是两种图表类型。`highlight` 在多序列下选中的是「升级为 accent + 加粗 + 末端圆点」的那个序列索引。

图表仍应诚实表达单一关系，但以下字段在不改变数据口径的前提下，扩展了同一关系的**可读表达**（全部原生可编辑）：

- `donut` / `donut_composition` 的 `center_value` / `center_label`：把「总数 / 结论」放进甜甜圈的洞（环心 KPI）。它不新增数据通道，只是把本应由图例承担的总读数放回视觉中心。
- `sparkline`：去轴迷你折线 + 端点圆点，用于 small multiples（一页多组趋势的「形状对比」）。读数由相邻的直接标注承担，sparkline 本身不伪造坐标轴。
- `waterfall` 的 `subtotal` / `is_total` / `total` 行标记：小计段从零轴起画整段累计，段间画桥接虚线。数据仍是逐行 `label` + 有限 `value`，只是「起点」语义由累计推导。
- `ranked_bar` 的 `target` / `target_label`：在已知刻度上画一条竖向目标参考线。它是可视化标注，不改变 `value` 的诚实性。

新增图表表达仍遵守同一份数据契约：负值、缺失、非有限值、空数据、无效高亮索引与无效构成总和必须在 Guard/Compile 阶段暴露，不得静默补零或伪造单位。

### Fact & metric governance（事实/口径治理）

「确定性」不只是数值有限、可编译，还必须是**口径可核验**。数值图表应显式声明 `source`（来源）、`unit`（单位）、`period`（期间）、`basis`（比较口径）、`data_status`（数据状态）；同一指标（用 `metric` 或 `series_name` 作跨页对齐键）必须在整套 deck 中保持单位一致。Guard 据此产出三类治理信号：

- `data_provenance`（warn，`require_provenance=True` 时 error）：数值图表缺少来源/单位/期间声明。来源不可省略；单位与期间必须显式，否则「万元 vs 亿元」「2026 vs FY26」这类口径漂移无法被发现。
- `metric_consistency`（单位不一致 = error；期间不一致 = warn；比较口径不一致 = hint）：同一 `metric` 跨页单位打架是最会「误导决策」的业务错误——同一指标必须同一单位，否则读成两套数字。
- `title_semantics`（hint）：`page_intent.insight` 退化成「字段名标题」（如「市场分析」）时提示改写为可复述结论。

本治理只验证「口径是否声明且一致」，不替调用方核验「数值是否真实」——事实真实性由责任人对照来源确认；但缺少来源、口径打架这两类问题，现在会在 Guard 阶段被确定性点名，而不是等到董事会前才发现。

## Asset Contract

图像资产由 `scripts/asset_prompt.py` 生成确定性提示词：调用方传入资产卡（`CARD` 或 `build_card()`，含 `subject / color / material / lighting / composition / motion / style` 必填段与 `apc` 溯源编号）和页面参数（留白锚点、光向、能量、资产功能），脚本按固定顺序拼接并追加 Universal QC、类型后缀与透明资产对比度防护；`validate_asset_card()` 在出图前返回漏项清单。生成后的图像进入 spec 时仍须满足：`asset_function`（context / emotion / proof / hero）、主体、构图、留白锚点、裁切与溯源；Guard 对声明了 `asset` 的图像检查 `theme_ref / apc` 绑定与 negative 中的 no-text / no-logo / no-watermark 约束。图像不得烘焙文字、Logo、水印、数据或来源。

## Deterministic QA

继承现有 `guard.py` 的网格、越界、安全区、重叠、容量、Accent、节奏、文本、颜色、对齐、装饰、动画、对比度、叠加层、主题约束、最小字号（min_font）与焦点尺度（focus_scale）检查，并将 `overlap`、`source_zone`、`text_capacity`、`chart_label_collision` 视为优先级高于审美分数的布局问题。继承现有 `render_check.py` 的 occupancy、brightness、saliency centroid、saliency split、`saliency_method`（显著图实际算法：`cv2_spectral_residual` / `deterministic_fallback`，跨机器可比性的溯源）、accent pixel ratio（按主题 Accent 色距测量，缺失时回退饱和度启发）、margin occupancy、background luma、gravity drift，以及 `text_contrast_min`（正文级最坏值）/ `text_contrast_all_min`（含注记级）/ `text_contrast_worst`（该框 id、字色与实测底色）——后三项把「文字压在画上能不能读」从声明推断变成像素事实，其 fail / soft / pass 判定由 QA 与 Critic 共享同一实现（`primitives.text_contrast_verdict`）；锚点解析以 `page_intent.focus` → `gravity_anchor` → 启发式 的顺序对齐声明意图。

确定性评分建议仍用 100 分制，但只记录 `guard / compile / render` 域，并在 `deduction_by_domain` 中给出分域扣分明细。`passed` 不能仅凭分数决定；硬错误、编译失败、来源缺失、渲染缺失、关键文本不可读或任何未获声明的遮挡时必须覆盖分数。报告必须返回 `failure_codes`、`blocking_items`、`affected_slides`、`next_action`、`status` 和 `elapsed_ms`，让下一次调用只处理受影响范围。`status` 的优先级固定为：阻断错误 → `BLOCKED`；无阻断但缺少真实渲染 → `PREVIEW_ONLY`；有可修复问题 → `REVISE`；全部发布条件满足 → `PASS`。

### Static Preflight（先于渲染的同一批门槛）

`guard.run_preflight()` 只镜像 Art Critic 中**确定性可静态判定**的部分，阈值经懒加载直接取自 `art_critic` 导出常量（`gate_source: "art_critic"`；导入失败时用等值默认并标注 `guard`）。返回 `{slide, code, observation, minimal_fix, gate_source}`，码表：`INTENT_UNCLEAR`、`FOCUS_UNBOUND`、`FOCUS_SCALE`、`FOCUS_LEAD`、`FOCUS_DOMINATED`、`MEDIA_BUDGET`、`TEXT_BUDGET`、`CARD_WALL`、`CARD_DENSITY`（3–4 个圆角容器，未到硬门槛的提前提示，与 `CARD_WALL` 互斥点名）、`BG_UNPROTECTED`(warn)、`ASYMMETRIC_UNDECLARED`、`DENSITY_FLAT`、`RHYTHM_FLAT`。

预检条目只用于提前修，不参与美学评分：`preflight_hint` 权重为 `0.0`，因此新增提示不会把 `PASS` 拉成 `REVISE`。命中 `PREFLIGHT_HARD_CODES`（`INTENT_UNCLEAR` → BLOCKED，`FOCUS_UNBOUND` / `CARD_WALL` / `RHYTHM_FLAT` → REVISE）时，`preflight_gate=True` 直接跳过渲染并给出 `next_action`，判定不因此放宽——被跳过的渲染永远不可能给出 PASS。

### Performance

`qa["performance"] = {total_ms, guard_ms, compile_ms, render_ms, slides, preflight_items, render_skipped, qa_level, render_workers, rendered_pages, requested_pages, cache_hits, cache_misses, cache_enabled, compile_reused}`；`qa["preflight_gate"] = {enabled, triggered, hits}`。渲染通常占整轮 90% 以上成本，因此这三项就是“少跑一轮”的可核对证据。性能数据只用于说明与调参，不参与发布状态。

## Progressive QA 与并行渲染

三个层级共用同一套阈值，差别只在**测了多少**，不在**放宽什么**：

| Level | 内容 | 成本（12 页实测，冷缓存） | 允许的状态 |
|---|---|---|---|
| 1 | 文件产出、元素存在、页数、静态治理与预检 | 0.7s | `PREVIEW_ONLY`（无渲染证据） |
| 2 | 只渲染关键页：封面、收尾、含图片/图表/背景画心的页 | 3.4–4.4s | 上限 `REVISE`（`release_eligible=False`） |
| 3 | 全量渲染 + 全部检查（默认，发布口径） | 4.6s | 可为 `PASS` |

- 选页：`qa.key_pages(spec)` 从 spec 推导；调用方也可显式传 `render_pages`，或用 `route.plan_deck(brief)["verification"]["pixel_page_ids"]` 复用决策层结果。`KEY_PAGE_CAP = 6`，避免关键页退化成全量。
- 覆盖率：`render_evidence["coverage"] = {rendered_pages, total_pages, rendered_ids, requested, workers, unrendered}`，并透传到 `qa["render"]["coverage"]`、`critic["deck_notes"]["pixel_coverage"]` 与 manifest 的 `verification`。
- 证据对齐：子集渲染的每页结果带绝对 `page` 与 `index`，QA 与 Critic 按 `index` 匹配（无 `index` 的旧证据退回位置匹配）。**禁止**按结果数组下标对齐——那会把已测页的指标串到未测页上。
- `PIXEL_COVERAGE_PARTIAL`（REVISE）：证据不全时无论分数高低都记入 `hard_gates`，并把 `PASS` 降级；覆盖全量后自动消失。

### 复用三段重复劳动（去掉重复渲染 / 重复转换 / 重复编译）

`render_evidence` 在 `out_dir` 里维护 `render_cache.json`：

- 键 = `sha256(本页 spec + canvas + dpi + 完整 theme + 页内图片 (name,size,mtime) + 渲染器路径 + 显著图后端 + 版本 v4)`；任何会影响本页像素的输入都进键，因此**其他页的改动不会让本页失效，而重新出图、换主题字、换 LibreOffice 或换显著图后端一定会**（cv2 与回退算法的质心/分片不可互换，跨机器共用证据目录时必须分键存放；旧 v3 键自然淘汰）。
- 命中还要求：条目记录的 `png` 文件仍在目录里，**且文件内容指纹 `png_sha` 一致**。只比文件名会把别页像素当本页复用（曾真实发生过：命中 12/重测 0，却返回错页指标）；旧格式（无 `png_sha`）条目一律不信任、直接重测。
- 每轮渲染使用唯一 PNG 前缀 `page-<token>-r<idx>-<绝对页码>.png`，只按绝对页码认领文件；缺页记入 `coverage.unrendered`，绝不按结果序号回退猜页——宁缺勿错。
- `use_cache=False` 的冷测不清空证据目录（只增加文件），因此一次冷测不会把别人的热缓存打回冷态。
- `out_dir` 一律先 `resolve()`：相对目录会拼成非法的 `file://relative/...` LibreOffice profile URI，导致 `soffice` 卡在 profile 锁上直到 300s 超时（`qa.py` 直接命令行调用时的旧行为，现已修）。
- 全部页命中时直接返回，不启动 LibreOffice/pdftoppm；写缓存时只保留当前 deck 的键（自动裁剪，不会长胖）。
- `coverage` 增加 `cache_hits / cache_misses`，`qa["performance"]` 透传同名两项，作为“这一轮省掉了多少”的凭证。
- 键的口径：页级投影按**排除法**取字段——`NON_PIXEL_SLIDE_KEYS`（`page_intent` / `source_zone` / 备注 / 评论）与 `NON_PIXEL_THEME_KEYS`（`constraints` / `notes` / `description` …）之外的全部字段都进键。排除法保证将来新增的视觉字段自动进键、不会漏测；唯一被点名保留的是 `page_intent.focus`：它不产出像素，却决定量哪个元素的墨量占比，所以必须进键，否则改 focus 会拿到上一版的 `coverage_ink`。`selftest.check_cache_projection` 会扫描 `compiler.py` 实际读取的 slide 键与 `primitives/charts/elements` 读取的 theme 键，任何被排除表屏蔽的渲染输入都会让自检失败。
- **PPTX→PDF 整份复用**：soffice 只能整份转换（实测 1.70s），而 Level 2→Level 3、改 dpi 抽查、只改声明的修订都不改变 pptx 字节。`render_meta.json` 记下 `pdf = {name, pptx_sha, renderer}`，命中条件仍是内容核验（pptx 逐字节一致 + 渲染器路径一致 + PDF 仍在且页数 > 0）。Level 2 后补齐全量：2.57s → 0.82s。
- **编译复用**：`spec_view(spec)` = 会被编译成像素的那部分（canvas + theme 投影 + 每页 background/elements/id + 图片 size·mtime）。它与磁盘上 pptx 的内容指纹双重核验后才允许跳过 `compile_deck`，跳过后 `file_bytes` 按磁盘实际值刷新，`compile_reused=True` 进 performance。只改 `density` / `insight` / `focus` / 备注的一轮：4.8s → 0.01s，且像素质标与独立冷测逐位相同。
- 冷测（`use_cache=False`）既不查也不写：不查以免读到旧值，不写以免一次「隔离测试」改变别人的热态。因此 `--no-cache` 之后紧跟的那一轮会照常重编译一次（0.7s）并重新记账，再往后才是 0.0s。
- 关闭：`run_qa(..., use_cache=False)` 或 `qa.py --no-cache`；换渲染器、怀疑陈旧时用它做绝对冷测。

**为什么不再加一条线程**：一轮全量的成本实测是 guard 2ms · 编译 179ms · soffice 1704ms · pdftoppm 241ms(1 页)/1002ms(12 页) · 像素量测 75ms/页 · 批评 2.7ms。PDF 与编译复用把「重复」拿掉之后，剩下的是一条无法拆开的串行重流；再加线程只会增加同步成本而不会减少工作量。因此「设计推导 / 资产·渲染」两条线的合同由 `route.py` 的 `pipelines` 分工表达（两条、互不通信、在 `run_qa` 汇合一次），`run_qa` 内部则只保留下面这一处并行：

并行只发生在渲染阶段内部：`_plan_jobs()` 把请求页压成连续区间并按 worker 数二分（避免一核空转），每个 worker 内「poppler 转换 → 像素测量」串行执行、块与块之间并行（去掉两次全局栅栏）。`MAX_RENDER_WORKERS = 2` 且再按 `os.cpu_count()` 收敛；页数 < 4 时自动降为串行（单次 pdftoppm ≈ 117ms，调度成本同量级）。不做无界并发、不做多进程池、不引入新依赖。

## Art Critic contract

`art_critic.py` 必须返回：

```json
{
  "critic_version": "2.1",
  "deck_score": 0,
  "status": "PASS|REVISE|BLOCKED|PREVIEW_ONLY",
  "hard_gates": [{"code": "CRITIC_LOW", "slide": "s01",
                  "severity": "REVISE|BLOCKED|PREVIEW_ONLY", "reason": "..."}],
  "deck_notes": {"density_curve": [], "energy_curve": [], "rhythm_transitions": 0},
  "slides": [{
    "slide": "s01",
    "scores": {
      "visual_hierarchy": 0, "balance": 0, "alignment": 0, "contrast": 0,
      "rhythm": 0, "consistency": 0, "emotional_impact": 0,
      "memorability": 0, "professional_quality": 0
    },
    "dimension_evidence": {"visual_hierarchy": ["+1 焦点拥有 Statement 级尺度优势…"]},
    "observations": [], "minimal_fixes": [], "recheck": []
  }]
}
```

评分模型（v2）：每项 0–5 分，从基准分 3（「满足声明契约」）出发，凭**可观察证据**加分或扣分（delta ∈ [-2, +2]，钳制到 0–5）。每一个 delta 都必须写入 `dimension_evidence`，保证分数可逐条溯源复核；不加证据不得加分，不加观察不得扣分。v1 只扣不加导致满分被数学性封顶在 80/100、PASS(≥90) 不可达——v2 修复该缺陷，但 PASS 仍然要求 deck_score ≥ 90 且无任何硬门槛。3–4 个圆角容器时 `professional_quality` 记一次软扣分（未到 `CARD_WALL` 硬门槛，仍可 PASS）；`>4` 的硬门槛与 `ROUNDED_MAX=4` 不变。

`deck_notes.director_verdict`（加性字段，不参与评分）：`{headline, primary_lever, levers[≤3], gates_by_code}`，其中每条 lever 为 `{rank, kind, target, where, why, action, severity}`（kind ∈ gate / dimension / recurring）。它是「修哪个最值」的行动线：修正时一次只修 `primary_lever`，跑完一轮 QA 再看下一条，禁止逐条追分。纯函数、确定性，同输入必得同 verdict。

建议权重为 Hierarchy 20、Balance 15、Alignment 10、Contrast 10、Rhythm 10、Consistency 10、Emotional Impact 10、Memorability 10、Professional Quality 5。Memorability 必须由可观察的视觉记忆锚点、独特构图动作或跨页连续性说明支撑。`hard_gates` 必须携带失败码表中的真实码与 `severity`：`INTENT_UNCLEAR`（BLOCKED）、`FOCUS_COMPETING` / `CARD_WALL` / `MEDIA_UNJUSTIFIED` / `RHYTHM_FLAT` / `BACKGROUND_DISGUISED`（REVISE）、`READABILITY_FAIL`（BLOCKED，渲染实测文字对比 <3:1）、`CRITIC_LOW`（任何核心维度 < 3，REVISE）、`RENDER_UNAVAILABLE`（PREVIEW_ONLY）。Art Critic 的 `status` 只表示审美批评结果：任何核心维度低于 3 或存在审美硬门槛时至少为 `REVISE`，存在 BLOCKED 级硬门槛时为 `BLOCKED`；它不替代 QA 的数据、编译、安全区和渲染发布门。最终 Release Manifest 的 `status` 必须综合 QA 与 Art Critic，只有两者都满足发布条件时才为 `PASS`。

## Failure codes

| 代码 | 含义 | 默认动作 |
|---|---|---|
| `INPUT_MISSING` | 受众、决定、来源或关键约束缺失 | BLOCKED |
| `INTENT_UNCLEAR` | 一页无法写出单一 insight | BLOCKED |
| `THEME_MISMATCH` | 主题人格与内容任务冲突 | REVISE Direction |
| `FOCUS_COMPETING` | 多个对象争夺 L4 | REVISE Composition |
| `READABILITY_FAIL` | 对比、字号、行数或安全区失败 | BLOCKED |
| `DATA_INTEGRITY_FAIL` | 单位、期间、来源或图表映射不完整 | BLOCKED |
| `MEDIA_UNJUSTIFIED` | 图片无信息功能或遮挡内容 | REVISE Media |
| `RHYTHM_FLAT` | 连续页面密度/重心/能量重复 | REVISE Story Map |
| `CARD_WALL` | 圆角容器过多或成为主要结构 | REVISE Composition |
| `RENDER_UNAVAILABLE` | 没有真实渲染证据 | PREVIEW_ONLY |
| `CRITIC_LOW` | 审美批评维度低于门槛 | REVISE |
| `OVERLAP` | 可见文本/图表/图片有效墨迹相交 | BLOCKED |
| `SOURCE_COLLISION` | 来源区被主体或页脚冲突侵入 | BLOCKED |
| `CHART_LABEL_COLLISION` | 图表标签、轴、图例或数值互相遮挡 | BLOCKED |
| `TEXT_OVERFLOW` | 实际或估算文字超出可读区域 | BLOCKED |
| `COMPILE_FAIL` | 编译器未能产出 PPTX 或报告了未消化警告 | BLOCKED |
| `GUARD_FAIL` | Guard 发现未被专用错误码覆盖的硬错误 | BLOCKED |
| `BG_UNPROTECTED` | 背景画心未声明 `overlay` / `content_protection` | warn（扣分，不阻断） |
| `PIXEL_COVERAGE_PARTIAL` | 渲染证据只覆盖部分页（Progressive Level 1/2） | REVISE，不可发布 |

## Release Manifest

最终输出必须记录 `source_spec_hash`、`validation`（`issues` / `notes` / `page_count`）、`theme_id`、`slide_count`、`verification`（`qa_level` / `pixel_pages` / `pixel_total` / `release_eligible`）、`compile_report`、`qa_report`、`critic_report`、`render_evidence_path`、`revision_count`、`revision_log`、`status` 和 `generated_at`。可直接调用 `qa.release_manifest()` 或 `qa.py --manifest` 确定性生成（状态合成：任一环节 `BLOCKED` 即 `BLOCKED`，任一 `REVISE` 即 `REVISE`，QA 与 Art Critic 同时满足发布条件才为 `PASS`）。每次 revision 必须记录 observation、minimal_fix、recheck 结果，避免只写“已优化”。报告应能让另一位代理在不读取整套历史对话的情况下复现或定位失败；`revision_log` 只引用失败码与页面 ID，不嵌入重复源码或整份中间报告；`revision_count` 必须来自真实修订流水（每跑一轮生产链记一条），不能是恒为 0 的占位。

清单不是汇总器，而是**验收员**：`release_manifest()` 用同一算法（`primitives.spec_fingerprint`）重算当前 spec 的指纹，并对两份报告交叉校验——

- 报告带了 `source_spec_hash` 但与当前 spec 不符 → 记入 `validation.issues`，状态强制 `BLOCKED`（拿旧版报告的 PASS 冒充新版结果）；
- 报告声称 `PASS` 却没有 `source_spec_hash` → 同样 `BLOCKED`（旁路生成的“合格”不能作为发布证据）；未声称 PASS 的旧格式报告只记 `notes`，不阻断；
- 报告引用的页面 ID 不在当前 spec 内，或 Critic 覆盖页数与 `slide_count` 不一致 → `BLOCKED`。

`source_spec_hash` 因此是 `run_qa` 与 `critique_deck` 返回值中的固定字段；绕过这两个函数手工拼装报告，最多只能得到非 PASS 的清单状态。
