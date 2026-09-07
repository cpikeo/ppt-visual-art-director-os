# Scoring System（评分体系与优化建议）

本文档描述本 OS 的评分架构、v2 优化内容，以及后续可选的优化方向。
评分口径的权威约束见 `production-contract.md`；本文只做架构说明与建议。

## 评分体系总览

| 层 | 模块 | 分数语义 | 是否审美 |
|---|---|---|---|
| 静态治理 | `guard.py` | 内部 `score`（100 减扣），仅用于编译报告摘要 | 否（规则合规） |
| 编译诊断 | `compiler.py` | passed/warnings，不计分 | 否 |
| 渲染证据 | `render_check.py` | 像素指标（占用率、质心、Accent 像素比…），供 QA/Critic 消费 | 否（测量） |
| 确定性 QA | `qa.py` | 100 分制，guard/compile/render 三域扣分 + 阻断性失败码 | 否（合规 + 渲染完整性） |
| 结构化审美批评 | `art_critic.py` | 9 维度 × 0–5 加权成 deck_score(0–100) + 硬门槛 | 是（可溯源启发式） |

两个 100 分不得互相替代：QA 分数高不代表设计好，Critic 分数高不代表可发布。
Release Manifest 的 `status` 由 QA 与 Critic 状态合成：任一 BLOCKED → BLOCKED；
任一 REVISE → REVISE；两者 PASS 才 PASS；缺少真实渲染 → PREVIEW_ONLY。

## v2 优化内容（本次变更）

### 1. Art Critic 从「只扣不加」改为「证据驱动加减分」

- **问题**：v1 每个维度从 4 分出发只做减法，满分被数学性封顶在 80/100，
  PASS(≥90) 永远不可达——再完美的 deck 也只会得到 REVISE。
- **修复**：v2 从基准分 3（满足声明契约）出发，凭可观察证据加减
  （delta ∈ [-2, +2]，钳制 0–5）。每个 delta 写入 `dimension_evidence`，
  不加证据不得加分、不加观察不得扣分。回归自检（selftest.py
  `critic_pass_reachable`）锁定：合规且精致的 deck 可拿到 ≥90 并 PASS；
  卡片墙/无 insight/媒体无理由的页面会被正确拦截。
- **证据来源**：spec 几何（焦点尺度优势、墨迹左右失衡、左缘/顶缘轴线收束、
  8 网格吸附、字体家族/字号/对齐预算）、主题对比度（ink/muted/accent 对
  background）、渲染证据（质心漂移、主题 Accent 像素比）与跨页节奏。

### 2. 硬门槛携带失败码表中的真实码

`hard_gates` 从笼统的 `CRITIC_LOW` 细化为：

| 码 | 触发条件 | severity |
|---|---|---|
| `INTENT_UNCLEAR` | 页面缺少可复述的单一 insight | BLOCKED |
| `FOCUS_COMPETING` | 无唯一焦点 / 焦点无尺度优势且存在竞争 | REVISE |
| `CARD_WALL` | 圆角容器 > 4 或成为主要结构 | REVISE |
| `MEDIA_UNJUSTIFIED` | 图片未声明 asset_function / 媒体角色 | REVISE |
| `RHYTHM_FLAT` | 连续 ≥3 页密度与能量完全重复 | REVISE |
| `CRITIC_LOW` | 任一核心维度 < 3/5（reason 附维度证据） | REVISE |
| `RENDER_UNAVAILABLE` | 无真实渲染证据 | PREVIEW_ONLY |

### 3. 渲染证据对齐「声明意图」

- `render_check.resolve_anchor()` 新增：锚点解析顺序改为
  `page_intent.focus` → `gravity_anchor` → 启发式（id 含 hero/title/kpi 或
  首个图表/图片），并记录 `anchor_source`。此前漂移测量忽略声明焦点，
  评分与设计意图脱节。
- Accent 像素比改为**按主题 Accent 色距测量**（`accent_method: theme`），
  缺失主题色时回退饱和度启发（`accent_method: saturation`）；同时输出
  `saturated_pixel_ratio` 供对比。这使「Accent ≤5%」预算真正绑定主题，
  而不是把任何高饱和像素都算作强调色。
- 新增 `saliency_split_lr / saliency_split_tb`（显著图左右/上下质量分布，
  Critic 平衡维度的像素证据）与 `margin_occupancy`（边缘带安静度，
  安全区像素证据）。

### 4. QA 增加分域扣分明细与可选安全区规则

- `qa.py` 返回 `deduction_by_domain`（guard/compile/render/config 分域扣分），
  迭代时一眼看出分数丢在哪个域。
- 新增可选 `render_margin` 规则（thresholds `margin_occupancy`，默认关闭）：
  纯色/结构背景主题可开启「边缘带安静度」检查；通栏图片背景主题保持关闭，
  避免把合法的全出血背景误判为内容贴边。

### 5. Guard 增加两条可读性/焦点检查

- `min_font`（warn）：caption/annotation/source/label/axis/data_label/legend/
  metadata/method 类文字低于最小字号（默认 10px，可经 rules 覆盖）。
- `focus_scale`（hint）：声明焦点为文字但未获得页内最大字号。
- 节奏提示细化：声明密度变化但结构密度未变时，提示「渲染后复核真实留白」，
  而不是笼统的「连续同密度」。

## 使用建议

- 发布链路固定 `qa.py` 单入口；`render=False` 只允许快速迭代。
- 调参全部经 `penalties / thresholds / rules` 传入，不要改脚本默认值：
  - 团队无 LibreOffice 环境：`penalties={"render_missing": 0}`（环境问题
    已由 PREVIEW_ONLY 状态表达，不必再扣设计分）。
  - 纯色背景主题：`thresholds={"margin_occupancy": 0.05}` 开启边缘检查。
  - 图表密集的长 deck：可考虑给 QA 每域设扣分上限（见下方建议 1）。
- Critic 报告只读、不改 spec；`dimension_evidence` 是给人类复核的评分
  依据，修正时必须回应证据而不是追逐分数。

## 进一步优化建议（未实施，按收益排序）

1. **Critic 分维度 deck 汇总**（**高 ROI**，应优先实施）：当前只输出
   `deck_score` 与每页明细，迭代时不易看出整套 deck 在哪个维度整体偏弱。
   建议在 `deck_notes` 追加 `dimension_averages`（9 维加权平均）与
   `dimension_std`（9 维标准差），一行定位系统性短板与跨页不均。设计
   决策上的最大盲区不是「这一页不够好」，而是「整套 deck 在某维度
   整体偏弱却没被发现」。这一项能让用户在 5 秒内锁定下一步该读哪条
   reference 或调哪个阈值。
2. **QA 分域扣分上限**：60 页 deck 的 hint 级条目会线性累计，长 deck 比
   短 deck 更容易被扣到低分。建议在 `run_qa` 增加可选
   `penalties_cap={"guard": 30, "compile": 20, "render": 15}`，扣满即止，
   并在 items 中标注「已达上限」。
3. **光学对齐的渲染级复核**（**高 ROI**）：当前对齐证据是边缘轴线聚类
   （结构代理）。可基于已有渲染 PNG 做边缘投影（sobel + 投影直方图），
   验证「数学对齐」与「视觉对齐」的一致性，作为 Critic 对齐维度的渲染
   加分项。投入低（仅利用已有 PNG），但能让对齐维度从「结构证据」升级
   为「视觉证据」，对高级感评估极为关键。
4. **主题化 Accent 色距阈值**：`measure_image` 的色距阈值 0.30 对高饱和
   Accent（如 VP-007 蓝）与低饱和金属色（如 VP-004）灵敏度不同。建议
   将该阈值并入 `theme.constraints.accent_distance`，随主题声明。
5. **显著图算法版本锁定**：`render_check` 在有 cv2 时用 Spectral Residual、
   无 cv2 时用确定性回退，两者输出不可跨机器严格对比。建议在 evidence 中
   记录 `saliency_method`，CI 中固定依赖版本或强制回退算法。
6. **阈值校准闭环**：所有阈值（0.28 漂移、0.08 Accent、1.25× 焦点尺度
   领先…）来自经验默认值。建议用一批人工标注的 deck（好/中/差三档）做
   回归，校准各阈值与权重，并把标注样本放入仓库外的基准集。
7. **报告版本可比性**：`critic_version` / `qa_version` 已随本次升级，
   跨版本分数不可直接比较。建议在 revision_log 中记录评分器版本，
   Release Manifest 已具备 `generated_at`，可再加 `qa_version` 字段。

## 验证

`selftest.py` 覆盖：目录/引用完整性、模块导入、Fill 契约、Critic 返回
结构（含 CARD_WALL 门）、PASS 可达性回归、渲染锚点解析与主题 Accent
测量、两页 mini deck 的 Guard → Compile → QA → Release Manifest 冒烟。
发布前仍应对真实 deck 执行完整渲染级 QA 与 Art Critic。
