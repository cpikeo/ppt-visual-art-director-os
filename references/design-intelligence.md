# Design Intelligence Core（内容 → 意义 → 视觉策略 → 页面意图）

> **反模板原则（本卷第一条）：不要从页面类型推导页面长相。**
> 因为它是 Statement 不等于必须大字、Data 不等于必须图表、Case 不等于必须摄影、
> Framework 不等于必须卡片。家族 / 构图 / 母题 / 色彩 /
> 媒体都只是候选表达，不是内容的默认答案。**先判断内容为什么值得被这样看见，再决定
> 视觉形式。**

判断链（01–08 是判断，09–10 是移交）：

```
01 Strategy   观众需要理解、相信或决定什么
02 Meaning    这一页的洞察与证据等级
03 Intent     这一页的唯一视觉主语
04 Hypothesis 哪些表达能让主语被看见（候选 → 否决 → 最少选择）
05 Composition 尺度/位置/空间/对比/路径如何让它成立
06 Reduction  还能删掉、合并、降级什么
07 Rationale  为什么是这个设计而不是另一个
08 Continuity 为什么属于这套 deck
09 Execution  → vao.py（唯一生产入口）
10 Guard      → 只查工程事实，不判审美
```

职责边界（同一事实只判断一次）：

| 模块 | 唯一职责 |
|---|---|
| Design Brief | 用户知道什么、要求什么（契约，不是 prompt） |
| Design Intelligence（本文） | 为什么这样设计 |
| Design Craft | 如何判断好设计 |
| Design System | 字号/颜色/空间如何落地（数字阶梯全在那里） |
| Rules / Guard | 机器如何检查（`design_intelligence.py` / `design_intelligence_rules.py` / `guard.py`） |
| VAO | 如何快速执行（`vao.py`） |
| DNA | 哪些判断曾经有效（`memory/design_dna.json`） |

本文只留判断；页面得到的是家族与叙事动作，几何与构图由生成侧判断。

## 01·02 Strategy & Meaning（内容意义）

```yaml
strategy:
  audience: "受众、知识水平、观看距离、现场/异步"
  decision: "观看后要支持的决定"
  tension: "观众当前的疑问、风险或阻力"
  narrative_arc: [establish, explain, prove, recommend, close]
  emotional_target: "calm_authority | constructive_urgency | human_trust | technical_clarity"
  evidence_posture: "fact_led | hypothesis_led | exploratory"
```

材料先拆 `claim/evidence/implication/action`；每页 `insight = object + 变化/差异 + 含义`。证据等级 C/D 不配大号 KPI、强 Accent 或英雄图。

## 03 Intent — Page Intent（页面合同）

```yaml
page_intent:
  insight: "一页一句可复述结论"
  narrative_role: "establish | explain | compare | prove | recommend | close"
  focus: "唯一主焦点"
  reading_order: [conclusion, evidence, implication, source]
  energy: "low | medium | high"
  density: "sparse | balanced | dense"
  empty_space_role: "protect_focus | create_authority | separate_chapter | hold_emotion"
  page_family: "COVER | HERO | EDITORIAL | NARRATIVE | DATA_STORY | COMPARISON | FRAMEWORK | TIMELINE | EXECUTIVE_SUMMARY | CASE_STUDY | MINIMAL_STATEMENT"
  design_rationale: "可选：一句为什么这样摆（选择 × 理由 × 否决项）"
```

核心闭环：Insight → Focus → Reading Order → Visual Strategy → Composition → Rationale；
`design_rationale` 写不出的页面，布局是排列，还不是设计。每个视觉选择过反向问题：
**删除它，信息传达会不会变差？不会 → 删除。**

## 04 Visual Hypothesis（视觉策略：候选，不是答案）

```yaml
direction:
  visual_world: "一句话隐喻：材质 + 光影 + 空间（可展开、可落地）"
  composition_grammar: "soft_asymmetry | strict_grid | cinematic_stage | evidence_field | path_sequence"
  type_voice: "editorial_serif | neutral_sans | product_display | humanist_sans"
  color_behavior: "quiet_neutral | single_signal | warm_material | dark_luminous"
  media_role: "none | context | emotion | proof | hero"
  background_scene: "solid_world | atmospheric | cinematic"
  motion_posture: "still | reveal | progressive"
```

`background_scene` 说的是**整副 deck 的页面背景世界**：`solid_world`（原生色面 / 材质场 /
极简空间）· `atmospheric`（允许光、空气、材质、景深形成背景环境）· `cinematic`（允许完整
空间、场景与摄影叙事形成页面背景）。它**不判断「这一页有没有背景图」**——那是逐页
`asset` + `asset_role: background` 的事。四个概念各管一件事，不得互相替代：
`background_scene`＝页面背景世界 · `asset_role`＝这张资产是什么（背景/插图/hybrid）·
`asset_function`＝它为什么存在（hero/proof/emotion/context/frame/separate）·
`asset_subject`＝画面具体出现什么。

隐喻必须能回答：什么材质 / 光从哪来、什么性格 / 元素并列、层叠还是纵深。内容不需要隐喻时，`solid_world` + 编辑版心即正确选择——诚实比意象重要。色彩派生：品牌色 > 材质/光性判断 > 方向种子（兜底）；图表色走语义角色，不写死色值。

`color_behavior` 是**饱和与明度的人格**，不是品味标签：`quiet_neutral` 不是高级的同义词，四种人格平权；先问内容的情绪温度、行业语境与观看场景再选，选定后把纪律执行到底——克制 ≠ 低饱和：高饱和承担单一职责时同样克制，低饱和铺满而职责不清同样廉价。

**内容信号 → 视觉假设（第一候选，不是默认答案）：**

| 内容信号 | 感知目标 | 候选视觉动作（第一假设） | 反例 |
|---|---|---|---|
| 单一关键结论 | 记住 | 大尺度标题、主动留白、唯一重心 | 多 KPI、字段名标题 |
| 复杂系统 | 可扫描 | 分层、路径、稳定网格 | 图标墙、无方向卡片墙 |
| 证据与风险 | 相信 | 直接标注、共同基线、来源可见 | 3D、装饰图、藏不确定性 |
| 人物/案例 | 信任 | 有语境摄影、叙事顺序 | 泛化图库、无关肖像 |
| 品牌/发布 | 记忆 | 单一 Hero、尺度张力 | 金色铺满、产品堆叠 |
| 行动建议 | 明确 | 结论式标题、行动动词 | 装饰性标语 |

每行只是第一候选：同一个结论可以用大尺度呈现，也可以用极致克制、隐喻、空间关系或数据证据呈现。流程永远是**信号 → 感知目标 → 候选动作 → 否决不成立的 → 选最少且最有效的表达**。方向种子只是执行起点，饱和人格与视觉假设都是内容要回答的洞，不是默认答案。

内容类型 → 页面家族由 `route.py` 查表（13 类内容）；数据/表格/流程/结构页不出图。家族名以代码为准（11 个，见 `page_intent` 枚举），别在文档里另造一套词汇。

## 05 Composition（算子优先于原型）

先组合算子，再看落哪个原型附近：轴（对称/错位/偏置）/ 切分（不等分优先，等分只用于同坐标系对比）/ 尺度对偶（极大 × 极小）/ 叠压（背景与前景层叠建纵深）/ 动线（水平叙事·垂直庄重·对角张力）。光学补偿：Latin 与 CJK 同行抬 1–2px、容器内数字略高于数学中心、混排共 baseline。

**相邻页不要求机械换算子**：变化要由内容、叙事或情绪的转折产生——重复有理由就保留，变化有理由就变，没理由不动。连续页布局雷同由 plan 期 `forecast_risk.layout_monotony`（同家族连续 ≥3 页）点名，那时再成批换算子——这就是「有理由的变化」。

**构图判断三问**：视觉中心在哪（哪个元素承载最重墨量/尺度）？第一眼看到什么（第一视线落在主语上——落在装饰上即构图失手）？必然关系成立吗（删除任一元素表达是否改变；图是文的证据、文是图的观点，两者皆可删则皆应删）。非对称平衡合法，但要声明平衡靠什么承担对面（尺度/墨色/材质/留白之一）。

## 06 Reduction（留白职责与减法）

留白是结构，不是残渣：先问为什么留、支撑什么——保护焦点、建立权威、制造情绪还是分隔章节（`empty_space_role` 四职责）；说不清职责即事故，有职责的大片空白常常是最贵的设计。不要先算百分比：只有当作者把留白写成 `whitespace_min` 才成为被执法的承诺（v5.6 起包不再自动填这个数字），口径见 design-system.md §约束。减法链（删除 > 重组 > 排版 > 强化 > 装饰）见 design-craft.md §一。

## 07·08 Rationale & Continuity（叙事与整套）

**Narrative Reference（九阶段是参考，不是模板）**：opening 建世界（HERO，高/sparse）→ context 给背景（EDITORIAL）→ problem 让张力具体（NARRATIVE/COMPARISON）→ insight 给判断（STATEMENT，低/sparse）→ evidence 证明（DATA_STORY，低/dense 不拥挤）→ solution 展结构（FRAMEWORK）→ proof 给案例 → vision 放大意义（HERO）→ closing 定行动与记忆（STATEMENT）。高信息页之后跟留白或低能量页。**不是每个 deck 都必须完整走过九阶段，也不是每个阶段都独占一页：可合并、可跳过、可重复、可重排——叙事服务内容，而不是内容填入叙事。**

**情绪与节奏（四乐章 × 三手法，六套样本验证）**：章节过渡页是重置不是内容——全幅视觉 + 单 statement、密度归零，允许深色沉下去或浅色亮起来，负责换脑；内容页提供证据——浅、稳、可扫读；结尾页回收封面语言——同级 statement、同轴线，愿景句即落款，不放谢谢页与联系方式。深浅明暗交替都合法，唯一判据是服务叙事段落：深为沉情绪、浅为让证据说话、强为记忆点蓄势；说不出服务哪个段落的交替，是效果不是叙事。跨页连续性双锚：caps 眉标固定上缘、页码固定象限，锚不动正文才可游走。（Fig. 01/02 证据编号属论文引用装置，演示场景不用；`anchor` 是可执行项：plan 逐页发，guard 的 `deck_anchor` 守在不在 / 位置是否同一个 / 编号是否连续。）

**母题是可选的**：一套 deck 可以有一个图形母题（圆/光球/编号方块）；有则母题承担连续性——封面注册、章节页放大、数据页退成刻度、结尾页收束，母题之外的装饰全部删除；没有则由锚点、排版声音与图表性格承担。母题不是每套 deck 必须产出的项，更不是每页必须出现的装饰。**页型标签**全场统一词汇表：直接用 plan 给的 `page_family`，caps 小标固定页首；标签即节奏的可视化。（第二批六套样本验证）

**同一视觉世界（整体统一）**：统一的是世界，不是页面——同一材质与光的逻辑、排版声音、锚点词汇、图表性格、色彩纪律；在此之内每页可自由换构图、密度、色重、图片比例与标题位置，深色章节页与浅色内容页可以共存。判据是「把任何一页换进别的 deck 会立刻显得不属于」，而不是「每页看起来相同」。

字号阶梯（锚点 64/44/32/22/17/12.5）、行高区间与中西混排规则归 design-system.md §字号阶梯（全库唯一真源）。分工：Intelligence 回答「这个信息是不是页面的视觉主语」，System 与生产合同回答「落到哪个安全值」。

## Design Judgment（取舍优先级，低层永不为高层让位）

1. 事实与语义 > 一切（无例外）
2. 可读性 > 审美（冲突时牺牲留白，不缩字号）
3. 内容任务 > 视觉惯例（比例说不通就放弃比例）
4. 情绪 > 秩序（高潮页可主动打破节奏，需在 `empty_space_role` 说明）
5. 品牌 > 通用审美

打破规则的两个判据：它是主动决定（能一句话说清为什么，且新重心更明确），且一次只打破一条。机器口径（密度带/家族表/构图池）见 `design_intelligence_rules.py`。
