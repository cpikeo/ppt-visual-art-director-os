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

### 6. 预检提示不计分，分阶段耗时可核对

- `guard.run_preflight()` 的条目以 `hint` 级注入，并单独使用
  `preflight_hint: 0.0` 权重：预检是「提前告诉你渲染会怎么判」，不是新的扣分项。
  若沿用 `guard_hint` 的 0.1，12 页 deck 新增一批同口径提示就可能把 98.4 的
  `PASS` 拉成 `REVISE`——评分口径必须随能力同步调整，而不是让新检查白拿扣分。
- 阈值唯一来源是 `art_critic` 导出的常量（`STATEMENT_SIZE / FOCUS_LEAD /
  MEDIA_BUDGET_MAX / TEXT_BUDGET_MAX / FOCUS_AREA_LEAD / ASYMMETRIC_GRAMMARS`），
  Guard 懒加载读取；两侧不一致时 selftest 的 `preflight_sync` 直接 FAIL。
- `qa["performance"]` 给出 `guard_ms / compile_ms / render_ms / preflight_items /
  render_skipped`。实测渲染占整轮 89–96%，因此判断「是否值得再跑一轮」应由
  静态预检负责；`preflight_gate` 命中硬码时跳过渲染，但被跳过的渲染本就
  不可能给出 `PASS`，判定不放宽。
- 背景层（`layer: background`）不计入 `MEDIA_BUDGET_MAX`，也不参与焦点压制：
  它服务空间而非信息，扣分应落在「有没有内容保护」上（`BG_UNPROTECTED` warn 仍计分）。

### 7. 渲染证据覆盖率决定发布资格（不扣分，但降级）

- `run_qa(..., qa_level=1|2|3)`：Level 1 不渲染、Level 2 只渲染关键页（`key_pages(spec)`
  或调用方给定页码）、Level 3 全量。三级共用同一阈值与同一 `pass` 门槛。
- Level < 3 或子集渲染时：`release_eligible=False`，`PASS` 被降为 `REVISE`，Critic 记
  `PIXEL_COVERAGE_PARTIAL`；**不新增扣分项**——证据不足是资格问题，扣设计分等于把
  「测得少」误报成「设计差」，也会让快速路径的分数不可比。
- 子集证据按 `index` 对齐（`render_evidence` 每页带绝对页码）；QA 与 Critic 都不按结果
  数组下标取页，避免未测页继承别人的 gravity/accent。
- 渲染证据按页缓存（`render_cache.json`）只去掉重复测量，不改变任何判定：缓存指标
  与冷测逐位相同（selftest 的 `render_cache` 断言这件事），且命中必须同时存在证据 PNG。
  `performance.cache_hits / cache_misses` 是「省掉了多少重复计算」的凭证。
- 渲染内部并行上限 2（`render_check.MAX_RENDER_WORKERS`，再按 CPU 收敛，页数 <4 关闭），
  「poppler 转换 → 像素测量」在同一 worker 内串成一条流水：实测 12 页 dpi 96 由
  6.10s → 4.51s（−26%），QA 分数与 Critic 判定逐位不变。

## v2.3 变更：一轮改稿的时间去哪了

先测量，再动手。12 页旗舰每轮的真实成本是：guard 2ms · `compile_deck` 179ms ·
`soffice` PPTX→PDF 1704ms · `pdftoppm` 80ms/页 · `measure_image` 72–75ms/页 ·
`run_qa` 热态全命中 176ms · `render_evidence` 全命中 2.7ms。四个结论：

- **重复发生在「轮与轮之间」，不在「页与页之间」**：Level 2 跑完接着跑 Level 3，会为
  6 个新页重付一整份 soffice 转换（2.57s）；把 `density` 从 sparse 改成 dense 这种
  不动像素的改稿，当时要重渲染 3 页。于是加了 PDF 复用与编译视图复用两段（口径见
  `production-contract.md`），而不是去并行一条无法拆开的串行链。
- **量测本身没有回归**：加与不加 `text_regions` 是 72ms 对 75ms——上一轮的文字对比
  链不是速度问题，就不为此改代码。同理放弃「把证据降到 640px 再量」的想法：阈值是在
  96dpi 上调出来的，省 250ms 换一次口径漂移不值。
- **缓存键必须覆盖「影响量测的输入」而非「影响像素的输入」**：`page_intent.focus`
  因此是唯一被点名单独并入键里的声明字段。这个洞是本轮自己写出来、又被自己的红队
  脚本抓到的（改 focus 后 `gravity_drift` 停在旧值），修完补了 `cache_projection` 自检。
- **一处去重**：`_text_contrast` 曾对同一区域取两次主色（先算对比再算最劣项），改为
  一次量测两处复用；`_png_sha` 更名 `_file_sha`，因为它同时服务于 PNG 与 PPTX 核验。

实测（2 核 / 12 页；「热」= 上一轮已记账）：

| 跑法 | v2.2 | v2.3 |
| --- | --- | --- |
| Level 1 迭代 | 0.7s | 0.03s |
| Level 2 关键页（冷） | 3.4s | 3.7s（未变：真冷测） |
| Level 2 收口 → Level 3 补齐全量 | 2.57s | 0.82s |
| 只改声明字段的一轮（QA+Critic 全链） | ~2.2–4.8s | 0.01s |
| 改一页元素坐标的一轮 | 4.8s（12 页全重测） | 3.2s（1 页重测 + 必要的重转换） |
| Level 3 绝对冷测 | 5.0–5.3s | 4.7s |

判定没有因此变松：冷热两条路径的 24 项像素质标逐位一致，`--no-cache` 既不查也不写。

## 审美判定的三处精度（同样是先测量后写规则）

- **色相族预算**（`palette_discipline`，warn）：全套语义色 ≤4 个 30° 色相族，纸色与
  灰阶不计。它管的是「每页都合规、合起来像七套主题」这种单页指标抓不到的塌法。
- **强调角距离**（同规则，warn）：`accent` 与 `primary`/`secondary` 色相差 <12° 时点名
  「强调色只是主色的重复」。同族深色堆叠拿不到唯一重点信号，是最常见的伪高级。
- **渐变是否混脏**（同规则，hint）：两端色相差在 150–210° 且彩度都居中时提示中段会
  灰成一块；`#F8F5EF → #EBE5D9` 这类同族低对比渐变是留白手法，**刻意不打击**。
- **图表样式漂移**（`chart_style_drift`，warn/hint）：同一 `chart_kind` 出现在 ≥2 页而
  `label_size` 相差 >1.25×，或图例开关一页开一关。
- **焦点落位**：中心（x 或 y 任一）对齐中线 / 三分线 / 1/4 线 / 黄金分割线（±0.045）时，
  Art Critic 给 `visual_hierarchy` 记一次加分（本轮已有正向层级证据则不叠加）；完全不上线
  只在 guard 预检出 `FOCUS_PLACEMENT` hint，不扣分。轴线常量放在 `art_critic`，guard 经
  `_preflight_gates()` 读取——提示与评分同源，不会长成两套标准。
- **一处误判修正**：焦点是图表/图片时，旧版会拿 `0px` 去比字号并扣「同级竞争」。尺度
  对比只在焦点本身是一段文字时成立，现已限定（`focus_placement` 自检覆盖该回归）。

旗舰在这批规则下保持安静：12 页全部对齐左列三分线（x=0.333）因而提示为零；色相族
4 / 上限 4；图表标签统一 13px；六处渐变是同族呼吸。QA 98.4 / Critic 94.2 /
Manifest PASS 与上一轮逐位一致——新门槛没有把做好的东西判成做坏。

## v2.2 变更：发布门完整性与审美证据

上一轮（v2.2）评分审计指出四件事：缓存会复用错页指标、`layer: background` 是无条件免死金牌、
没有任何地方实测「字压在画上能不能读」、清单承认来历不明的 PASS。它们属于**判定可信度**，
先修完再谈审美上限。

- **缓存按内容核验**：PNG 前缀带每轮唯一 token；命中条件加上 `png_sha` 一致；缺页只记缺口，
  取消按序号回退。`render_cache` 与新增的 `cache_content_verify` 两项自检分别断言
  「命中即同值」与「篡改像素必被拒、无指纹条目不信任」。
- **背景层免检需要资格**：`art_critic.background_layer_ok` 是唯一口径（覆盖 ≥`BG_MIN_COVERAGE`
  60% 画布，且 `overlay` 不透明度 ≥`BG_MIN_PROTECT_OPACITY` 0.20，或显式 `readability_exempt`）。
  guard 的媒体预算、焦点支配、重叠、来源区四处豁免全部改走资格判定，不合格即
  `BACKGROUND_DISGUISED`（error，阻断）+ 预检同码。
- **文字对比按像素实测**：`measure_image(..., text_regions=)` 在每个文字框内取主色（16 级量化取
  众数后取桶内均值：既避开字形像素，又不因量化误差把 4.27:1 报成 4.5:1），与声明字色算 WCAG
  对比。QA 新增阈值 `text_contrast_fail` 3.0 / `text_contrast_warn` 4.5 与扣分
  `render_contrast` 3.0 / `render_contrast_low` 1.5；低于 3:1 无论角色一律 error →
  `READABILITY_FAIL` 阻断。注记级角色（`primitives.AUX_TEXT_ROLES`：来源 / 图例 / 轴标签 /
  数据标注 / 方法 / 元数据 / 页码）只受 3:1 约束，免得每页那行 12px 来源标注把噪声压过真实缺陷。
  Critic 的 contrast 维度消费同一指标，深底深字在审美侧一样掉分。
- **清单交叉校验**：`primitives.spec_fingerprint` 统一算法；`run_qa`（v1.4）与 `critique_deck`
  （v2.1）各盖 `source_spec_hash`；`release_manifest` 核对戳、页面集合与页数，任一条不符 →
  `status=BLOCKED` + `validation.issues`。
- **节奏看实测墨迹**：`_score_page` 现在拿得到上一页的实测 occupancy；差值 ≥`RHYTHM_INK_DELTA`
  0.10 视为呼吸成立（标签相同也加回，且不再因「密度能量双同」扣分；只改了一个标签但墨迹真的
  动了，同样按实测记加分——前提是同一事实不重复发糖），≤`RHYTHM_INK_FLAT` 0.03 视为空转标签
  （标签变了也扣分）。这条关掉「改字段就拿节奏分」的口子，同时不再误伤真在换气的页。
- **行长与网格可报告**：guard 新增 `typography` 规则（`line_measure()`：CJK ≤38 字/行、拉丁 ≤75、
  超 2× 阻断；注记级角色豁免）并镜像为预检 `LINE_MEASURE` 提示；`guard` 返回新增 `grid.adherence`
  与 `line_measure` 统计，QA 原样透传。两个比率**不新增扣分项**：`grid_adherence` 只报告，
  `typography` 只在超限（warn）与严重超限（error）时计分。Critic 的 8 网格判定与 guard 同口径——
  发丝线（≤2px）与通栏元素不再算偏离。
- 成本口径：`use_cache=False` 不再清空证据目录（冷测不把热缓存打回冷态）；Level 1 的
  `cache_hits / cache_misses` 报 0 而不是 `null`。

## 使用建议

- 发布链路固定 `qa.py` 单入口；`render=False` 只允许快速迭代。
- 调参全部经 `penalties / thresholds / rules` 传入，不要改脚本默认值：
  - 团队无 LibreOffice 环境：`penalties={"render_missing": 0}`（环境问题
    已由 PREVIEW_ONLY 状态表达，不必再扣设计分）。
  - 纯色背景主题：`thresholds={"margin_occupancy": 0.05}` 开启边缘检查。
  - 图表密集的长 deck：可考虑给 QA 每域设扣分上限（见下方建议 1）。
- 路径选择只改预算与验证深度：Fast 路径（`--fast`）与 Advanced 路径共用同一阈值与
  同一 `pass` 门槛；不要因为分数好看而临时升档，也不要因为赶时间而降低阈值。
- 迭代节奏建议：改布局用 `--quick`（Level 1，<1s）；查视觉用 `--key-pages`（Level 2）；
  只在收口与发布时跑 Level 3 + Critic。Level 1/2 的分数只用于看趋势，不能引用为发布结论。
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

`selftest.py`（23 项）覆盖：目录/引用完整性、模块导入、Fill 契约、Critic 返回
结构（含 CARD_WALL 门）、PASS 可达性回归、渲染锚点解析与主题 Accent
测量、两页 mini deck 的 Guard → Compile → QA → Release Manifest 冒烟，以及本轮六项红队：
缓存内容核验（篡改 / 无指纹 / 串页一律拒绝）、背景层资格、文字对比门禁（深底深字 1.07:1 被阻断、
浅底深字 14.37:1 不误伤）、行长门禁（超限提示 / 2× 阻断 / 注记豁免）、节奏以实测墨迹为准
（标签与墨迹冲突时信墨迹）、清单自证校验（伪造、过期、无戳 PASS、幽灵页面各自 BLOCKED）。
发布前仍应对真实 deck 执行完整渲染级 QA 与 Art Critic。
