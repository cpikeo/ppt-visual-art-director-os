# Design Intelligence Core（内容 → 意义 → 视觉策略 → 页面意图）

判断顺序：先回答「观众需要理解、相信或决定什么」，再决定「这件事应该如何被看见」。路由/风险/色彩的机器口径在 `design_intelligence.py` 与 `design_intelligence_rules.py`，本文只留判断。

## Strategy（内容意义）

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

## Direction（视觉策略）

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

隐喻必须能回答：什么材质 / 光从哪来、什么性格 / 元素并列、层叠还是纵深。内容不需要隐喻时，`solid_world` + 编辑版心即正确选择——诚实比意象重要。色彩派生：品牌色 > 材质/光性判断 > 方向种子（兜底）；图表色走语义角色，不写死色值。

## Content → Visual 映射

| 内容信号 | 感知目标 | 视觉动作 | 反例 |
|---|---|---|---|
| 单一关键结论 | 记住 | 大尺度标题、主动留白、唯一重心 | 多 KPI、字段名标题 |
| 复杂系统 | 可扫描 | 分层、路径、稳定网格 | 图标墙、无方向卡片墙 |
| 证据与风险 | 相信 | 直接标注、共同基线、来源可见 | 3D、装饰图、藏不确定性 |
| 人物/案例 | 信任 | 有语境摄影、叙事顺序 | 泛化图库、无关肖像 |
| 品牌/发布 | 记忆 | 单一 Hero、尺度张力 | 金色铺满、产品堆叠 |
| 行动建议 | 明确 | 结论式标题、行动动词 | 装饰性标语 |

内容类型 → 页面家族由 `route.py` 查表（cover/business/data/comparison/timeline/process/architecture/product/case/statement/closing）；数据/表格/流程/结构页不出图。

## Page Intent（页面合同）

```yaml
page_intent:
  insight: "一页一句可复述结论"
  narrative_role: "establish | explain | compare | prove | recommend | close"
  focus: "唯一主焦点"
  reading_order: [conclusion, evidence, implication, source]
  energy: "low | medium | high"
  density: "sparse | balanced | dense"
  empty_space_role: "protect_focus | create_authority | separate_chapter | hold_emotion"
  page_family: "COVER | HERO | EDITORIAL | NARRATIVE | DATA_STORY | COMPARISON | FRAMEWORK | TIMELINE | DASHBOARD | MINIMAL_STATEMENT | CASE_STUDY | CLOSING"
  design_rationale: "可选：一句为什么这样摆（选择 × 理由 × 否决项）"
```

`design_rationale` 写不出的页面，说明布局是排列，还不是设计。

## 字号阶梯（全库唯一真源）

相邻级差 ≥1.25×；每页 ≤4 级、全 deck ≤6 级；取值优先落驻点。

| 级 | 驻点 | 区间 | 角色 |
|---|---|---|---|
| L4 Statement | 64 | 40–80 | 宣言、封面主张、KPI 主数字 |
| L3 Display | 44 | 40–56 | 页面主标题、Hero 结论 |
| L2 Title | 32 | 28–36 | 小节标题、图表标题 |
| L1 Lead | 22 | 20–24 | 导语、图表直接标注 |
| L0 Body | 17 | 16–20 | 正文 |
| L-1 Caption | 12.5 | 11–14 | 来源、注释、图例 |

行高：L4/L3 取 1.05–1.15，L2 取 1.15–1.25，L1/L0 取 1.3–1.5（中文取上限），Caption 取 1.2–1.3。层级优先用字重/墨色表达，再动字号。中文：避头尾、全角标点、中西混排留 1/8–1/4 em、禁两端对齐拉字距。

## 构图（算子优先于原型）

先组合算子，再看落哪个原型附近：轴（对称/错位/偏置）/ 切分（不等分优先，等分只用于同坐标系对比）/ 尺度对偶（极大 × 极小）/ 叠压（背景与前景层叠建纵深）/ 动线（水平叙事·垂直庄重·对角张力）。相邻两页至少换一项算子。光学补偿：Latin 与 CJK 同行抬 1–2px、容器内数字略高于数学中心、混排共 baseline。

留白三型循环：大（≥40%，opening/closing/insight）/ 标准（25–35%，context/solution/proof）/ 紧致（15–25%，evidence）。留白说不清职责即事故；有职责的大片空白常常是最贵的设计。

## Deck Rhythm（九阶段一句话）

opening 建世界（HERO，高/sparse）→ context 给背景（EDITORIAL）→ problem 让张力具体（NARRATIVE/COMPARISON）→ insight 给判断（STATEMENT，低/sparse）→ evidence 证明（DATA_STORY，低/dense 不拥挤）→ solution 展结构（FRAMEWORK）→ proof 给案例 → vision 放大意义（HERO）→ closing 定行动与记忆（STATEMENT）。高信息页之后跟留白或低能量页。

页型节奏三手法（六套世界级样本验证）：**章节过渡页是重置不是内容**——全幅视觉 + 单 statement、密度归零，负责换脑；**结尾页回收封面语言**——同级 statement、同轴线，愿景句即落款，不放谢谢页与联系方式；**跨页连续性三锚**——caps 眉标固定上缘、页码固定象限、证据编号（Fig./01–04）全文连续。锚不动，正文才可游走。

**母题变奏（motif variation）**：一套 deck 只设计一个图形母题（圆/光球/编号方块），用它的变奏承担全部装饰语言——封面注册母题，章节页放大，数据页退成刻度，结尾页收束；母题之外的装饰元素全部删除。**页型标签**全场统一词汇表（COVER / NARRATIVE / DATA / STRATEGY / VISION / CLOSING，caps 小标固定页首），标签即节奏的可视化。（第二批六套样本验证）

## Design Judgment（取舍优先级，低层永不为高层让位）

1. 事实与语义 > 一切（无例外）
2. 可读性 > 审美（冲突时牺牲留白，不缩字号）
3. 内容任务 > 视觉惯例（比例说不通就放弃比例）
4. 情绪 > 秩序（高潮页可主动打破节奏，需在 `empty_space_role` 说明）
5. 品牌 > 通用审美

打破规则的两个判据：它是主动决定（能一句话说清为什么，且新重心更明确），且一次只打破一条。机器口径（风险目录/密度带/取舍表）见 `design_intelligence_rules.py`。
