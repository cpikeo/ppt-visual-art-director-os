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

## 历史变更摘要（v2–v2.3，归档）

- **v2 评分可用**：Critic 从「只扣不加」改为证据驱动加减分（基准 3/5，delta ±2，
  逐条写 `dimension_evidence`，PASS 可达）；硬门槛携带真实失败码（现行码表见
  `production-contract.md` 的 Failure codes）；渲染锚点对齐声明意图、Accent 按主题
  色距测量；QA 分域扣分明细；Guard 加 `min_font` / `focus_scale`；预检 hint 零权重、
  阈值以 `art_critic` 常量为唯一来源；Level 1–3 覆盖率降级（证据不足降资格不扣分）、
  按页渲染缓存、渲染并行上限 2。
- **v2.2 判定可信**：缓存按内容核验（串页/篡改/无指纹一律拒绝）；背景层免检需要资格
  （覆盖 ≥60% + 保护层 ≥0.20，否则 `BACKGROUND_DISGUISED` 阻断）；文字对比按渲染像素
  实测（<3:1 `READABILITY_FAIL` 阻断）；QA / Critic 各盖 `source_spec_hash`，
  Manifest 交叉校验；节奏看实测墨迹（`RHYTHM_INK_DELTA` / `RHYTHM_INK_FLAT`）；
  Guard 加行长门禁与网格 adherence 报告。
- **v2.3 少跑一轮**：PDF 复用 + 编译视图复用（只改声明字段的一轮 4.8s → 0.01s）；
  `page_intent.focus` 并入缓存键；`_text_contrast` 量测去重。精度侧：色相族 ≤4、
  强调角距离 ≥12°、脏渐变提示、图表样式漂移、焦点轴线加分（常量仍在 `art_critic`，
  Guard 预检同源读取）。

## v2.4 Director 升级（本次变更）

方向：从「规则执行器」升级为「视觉总监」——**在正确的地方做正确的判断**。本轮不新增文件、不新增依赖，
只做三件事：合并重复判定（稳定性）、给出首要杠杆（设计判断）、收敛迭代纪律（执行速度）。

### 1. 总监 verdict：修正时先修最重要的（质量 + 速度）

- **问题**：Critic 给出 9 维 × N 页的 evidence 与一串 hard_gates，Agent 逐条追修，轮数不可控。
  大多数轮数浪费在「修了次要问题」上，而不是「修得不对」。
- **修复**：`deck_notes.director_verdict = {headline, primary_lever, levers[≤3]}`——按
  BLOCKED 门 → REVISE 门 → 系统性短板维度 → 跨页高频修正的顺序排成行动线。
  修正纪律：**一次只修 `primary_lever`，跑完一轮 QA 再看下一条**。
- **性质**：纯加性字段，不参与评分，不改变任何阈值与状态机；纯函数，同输入必得同 verdict。
  `critic_version` 升为 2.2（卡片软压会改变 3–4 容器 deck 的分数，跨版本不可比）。

### 2. 克制加压：卡片提前半步拦截（可调阈值）

- 3–4 个圆角容器：Critic `professional_quality` 软扣 -1 + Guard 预检 `CARD_DENSITY` hint
  （与 `CARD_WALL` 互斥点名，不重复）；`>4` 的 `CARD_WALL` 硬门槛与 `ROUNDED_MAX=4` 不变，
  仍可 PASS——压力给在「接近墙」时，而不是等撞墙。
- 回归锁定：合规 deck 分数逐位不变（`critic_pass_reachable` 仍 PASS；3 卡 deck 83.0 → 82.5，
  干净 deck 84.5 → 84.5 零漂移）；5 卡仍触发 `CARD_WALL` 门。

### 3. 口径收敛：三套重复判定合并到 `primitives.py`

- 背景层覆盖率 + 保护层解析：Guard `_bg_qualified` 与 Critic `background_layer_ok` 此前各写一遍，
  边缘行为不一致（无法解析的 opacity 一边放行一边拦截）。现共享 `bg_coverage` /
  `bg_overlay_opacity`，统一为 fail-closed（解析不出视为无保护），两侧消息文案不变。
- 文字对比 verdict：QA 与 Critic 各写一遍 `min(正文, 注记)` 逻辑，现共享
  `text_contrast_verdict`（fail 看含注记最坏值，soft/pass 看正文级），消息与扣分逐位一致。
- 圆角容器计数：Guard 预检曾把非 shape 元素也计入，现与 Critic 统一为
  `rounded_containers`（渲染出来是容器才算），消除误报。
- 以上均为 Layer 0 纯函数，不读 spec、不读主题，无循环依赖；`check_cache_projection`
  的排除表同步扫描通过（新增 helper 不引入新的 `theme.get` 渲染输入）。

### 4. 渲染溯源：显著图算法进证据、进缓存键

- 认领此前「进一步优化建议 #5」：证据每页新增 `saliency_method`
  （`cv2_spectral_residual` / `deterministic_fallback`，如实记录实际走的算法）；
  缓存键新增显著图后端并升为 v4——有 cv2 与无 cv2 的机器算出的质心/分片不可互换，
  跨机器共用证据目录时必须分键存放。旧 v3 键自然淘汰，无需手动清缓存。

### 5. SKILL 瘦身：十步清单收敛为 Director 五步流水线

- `SKILL.md` 十步强制流程收敛为「内容理解 → 视觉策略判断 → 布局决策 →
  关键细节优化 → 质量检查」五步（所有 MUST 条款原样保留，只换组织方式，
  每步带完成标准）；路由表只留一张，「预检不干净不渲染 / 迭代期不跑 Critic /
  声明修改不跑全量」三条纪律收敛进 P5。LLM 侧的决策分叉是执行速度的真正瓶颈——
  脚本侧 guard 2ms / critic 2.7ms 已无可压，省轮数比省毫秒重要两个数量级。

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
5. **显著图算法版本锁定**（**已在 v2.4 实施**）：证据每页记录实际算法
   `saliency_method`，缓存键纳入显著图后端（v4）。剩余可选动作：CI 中固定依赖版本。
6. **阈值校准闭环**：所有阈值（0.28 漂移、0.08 Accent、1.25× 焦点尺度
   领先…）来自经验默认值。建议用一批人工标注的 deck（好/中/差三档）做
   回归，校准各阈值与权重，并把标注样本放入仓库外的基准集。标注规范、
   反推阈值与相关性验证的完整方法见 `references/benchmark-calibration.md`。
7. **报告版本可比性**：`critic_version` / `qa_version` 已随本次升级，
   跨版本分数不可直接比较。建议在 revision_log 中记录评分器版本，
   Release Manifest 已具备 `generated_at`，可再加 `qa_version` 字段。

## 验证

`selftest.py`（30 项）覆盖：目录/引用完整性、模块导入、Fill 契约、Critic 返回
结构（含 CARD_WALL 门）、PASS 可达性回归、渲染锚点解析与主题 Accent
测量、两页 mini deck 的 Guard → Compile → QA → Release Manifest 冒烟、Director 升级回归
（verdict 确定性 / 卡片软压分级 / 背景层口径统一），以及六项红队：
缓存内容核验（篡改 / 无指纹 / 串页一律拒绝）、背景层资格、文字对比门禁（深底深字 1.07:1 被阻断、
浅底深字 14.37:1 不误伤）、行长门禁（超限提示 / 2× 阻断 / 注记豁免）、节奏以实测墨迹为准
（标签与墨迹冲突时信墨迹）、清单自证校验（伪造、过期、无戳 PASS、幽灵页面各自 BLOCKED）。
发布前仍应对真实 deck 执行完整渲染级 QA 与 Art Critic。
