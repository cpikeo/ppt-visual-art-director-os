# Design Intelligence

## 目标

将内容信号转换为视觉决策，而不是从主题库反向寻找内容容器。每一个视觉选择都应能回答：它服务什么判断？它改变了观众的阅读路径还是情绪？它如何被渲染后的证据验证？页面应被当作统一的视觉空间，而不是背景、图片、文字和图表的拼贴；元素之间必须共享可解释的光线、材质、透视、层级和对比关系。

## Strategy 对象

```yaml
strategy:
  audience: "受众、知识水平、观看距离、现场/异步"
  decision: "观看后要支持的决定"
  tension: "观众当前的疑问、风险或阻力"
  narrative_arc: [establish, explain, prove, recommend, close]
  emotional_target: "calm_authority | constructive_urgency | human_trust | technical_clarity"
  evidence_posture: "fact_led | hypothesis_led | exploratory"
```

先把材料拆成 `claim / evidence / implication / action`，再写每页完整句式 `insight = object + change/difference + implication`。证据等级 A/B/C/D 决定视觉权重：C/D 不得伪装成大号 KPI、强 Accent 或英雄图片。

## Direction 对象

```yaml
direction:
  visual_world: "一句话描述整套 deck 的光线、材质、空间和情绪"
  composition_grammar: "soft_asymmetry | strict_grid | cinematic_stage | evidence_field | path_sequence"
  type_voice: "editorial_serif | neutral_sans | product_display | humanist_sans"
  color_behavior: "quiet_neutral | single_signal | warm_material | dark_luminous"
  media_role: "none | context | emotion | proof | hero"
  background_scene: "solid_world | atmospheric | cinematic"
  motion_posture: "still | reveal | progressive"
  forbidden_signals: ["无关图库", "卡片墙", "竞争性强调"]
```

Direction 不是装饰偏好，而是对受众心理的假设。例如技术决策使用 `technical_clarity + evidence_field + direct_label`；品牌宣言可以使用 `calm_authority + cinematic_stage`，但数据页仍必须回退到低能量证据场。图片不是默认背景，图表不是默认组件，文字不是覆盖层；三者只有在承担明确的信息、情绪或证据功能时才进入 spec。

## Content → Visual Language 映射

| 内容信号 | 感知目标 | 视觉动作 | 默认反例 |
|---|---|---|---|
| 单一关键结论 | 让观众迅速记住 | 大尺度标题、主动留白、唯一重心 | 多个 KPI、标题像字段名 |
| 复杂系统 | 让关系可扫描 | 分层、路径、连接线、稳定网格 | 图标墙、无方向卡片墙 |
| 证据与风险 | 让观众相信 | 直接标注、共同基线、来源可见、低能量 | 3D、装饰图、隐藏不确定性 |
| 人物/案例 | 建立具体感与信任 | 有语境摄影、主体留白、叙事顺序 | 泛化图库、无关肖像 |
| 高端品牌/发布 | 建立期待与记忆 | 单一 Hero、尺度张力、克制光线 | 金色铺满、产品堆叠 |
| 行动建议 | 让下一步明确 | 结论式标题、行动动词、限定条件 | 把建议做成装饰性标语 |

### 内容类型 → 路由（Layer 0.7）

`scripts/route.py` 把内容分类变成一次可复算的查表，不再靠调用方逐项传参。输入只有 `content_type / design_direction / quality_level`，输出一页的完整设计决策；缺省值即“未指定 = 由内容判断”，同输入必得同输出。

| 内容类型 | 页面家族 | 默认密度 / 能量 | 图像决策 | 资产理由 |
|---|---|---|---|---|
| 封面 / cover | COVER | sparse / high | required | 建立世界与情绪 |
| 业务总览 / business | EXECUTIVE_SUMMARY | balanced / medium | none | 结构承担阅读 |
| 数据 / 指标 / data | DATA_STORY | balanced / low | none | 图与数即视觉 |
| 对比 / comparison | COMPARISON | sparse 或 balanced / low | none | 并列关系需空白 |
| 时间线 / timeline | TIMELINE | balanced / medium | none | 轴即结构 |
| 流程 / process | PROCESS | balanced / medium | none | 路径即结构 |
| 架构 / 分层 / architecture | FRAMEWORK | balanced / medium | required(仅品牌叙事) | 空间隐喻可选 |
| 产品 / product | PRODUCT | sparse / high | required | 产品即主角 |
| 案例 / case | CASE_STUDY | sparse / medium | optional | 具体感 |
| 结论判断 / statement | MINIMAL_STATEMENT | sparse / low | optional | 语言本身即画面 |
| 收束 / closing | MINIMAL_STATEMENT | sparse / medium | optional | 情绪余量 |

路由同时给出色阶（Statement / Body / Caption 三档）、`media_budget`、`text_budget`、`empty_space_role`、`needs_pixel_evidence`，并从方向人格派生背景、材质、光线、图表风格、动效姿态与构图语法。`needs_pixel_evidence` 只有一句话的含义：**这页的判断是否必须看像素**——封面与含画心的页为真，纯文字结构页为假；QA 因此可以在迭代期只渲染这几页（Level 2），而不是每轮把整副 deck 变成图片。整副规划结果带决策缓存：同一 brief 在修订循环里重复调用直接命中（`cache_stats()` 可核对命中数），返回深拷贝，调用方改动不会污染缓存。`plan_deck` 额外产出疏密曲线（相邻页密度互斥，与 Guard `DENSITY_FLAT` / Critic rhythm 同口径）与资产清单：`assets.generate / reuse / skipped / planned_calls` 对应路径预算（Fast ≤2，Advanced ≤4）。

**占用率口径**：`render_check` 的 occupancy 是渲染像素差值（96×54 采样、与角落底色比较），不是几何面积。浅色水墨画心几乎不占读数，因此声明 `balanced` / `dense` 前应以渲染值为准（±0.20 内），或在 `field()`、色带与文字块上增加真实墨迹，而不是改标签骗过节奏。

## 页面合同

```yaml
page_intent:
  insight: "一页一句可复述结论"
  narrative_role: "establish | explain | compare | prove | recommend | close"
  audience_question: "观众此刻最想知道什么"
  focus: "唯一主焦点"
  reading_order: [conclusion, evidence, implication, source]
  energy: "low | medium | high"
  density: "sparse | balanced | dense"
  empty_space_role: "protect_focus | create_authority | separate_chapter | hold_emotion"
  page_family: "COVER | HERO | EXECUTIVE_SUMMARY | EDITORIAL | NARRATIVE | DATA_STORY | COMPARISON | FRAMEWORK | TIMELINE | DASHBOARD | MINIMAL_STATEMENT | CASE_STUDY | CLOSING"
```

页面家族路由为：`establish → COVER/HERO`，`context → EXECUTIVE_SUMMARY`，`explain → FRAMEWORK/TIMELINE`，`compare → COMPARISON`，`prove → DATA_STORY/DASHBOARD`，`case → CASE_STUDY`，`recommend/close → CLOSING`。布局表达可映射为 `Executive Strategy → EXECUTIVE_SUMMARY/DATA_STORY`、`Editorial Luxury → EDITORIAL/CASE_STUDY`、`Data Intelligence → DATA_STORY/DASHBOARD`、`Comparative Analysis → COMPARISON`、`Narrative Flow → NARRATIVE/TIMELINE`；这只是内容到空间的路由，不是新增模板。每个页面仍复用同一安全区、来源区、字阶和色彩语义。一张图只回答一个关系；没有诚实图表映射时使用文字或表格。图表先完成 `data analysis → insight extraction → visual encoding → chart design → reading optimization`，再进入生产；它必须表达一个可复述的数据关系，而不是作为装饰性对象填充页面。

## Composition Engine

先声明视觉重心，再分配空间。使用 **12 列逻辑网格 + 8 单位基线网格**：12 列用于决定栏宽和比例，8 单位用于坐标与间距落地；不要把网格当作审美本身。构图判断依次检查：主焦点是否可在缩略图找到；重心是否与 page intent 一致；留白是否有职责；信息密度是否服务于叙事阶段；相邻页面是否形成疏密与重心变化；是否存在可解释的比例关系（黄金比例可作为候选构图启发，不得强行套用）。

建议记录 `gravity_anchor: {x, y, radius}`、`occupancy_target`、`reading_path` 和 `continuity_token`。跨页连续性应保持同一组字体、线宽、来源位置和色彩语义，同时允许封面、证据页、结论页拥有不同能量。

### 光学对齐

数学对齐 ≠ 视觉对齐。在以下情况必须做光学补偿：

- 大写拉丁字符与 CJK 字符同行时，Latin 视觉上偏低 1–2px，应在 baseline 或行高上抬。
- 圆角矩形 + 居中数字时，数字应在视觉中心而非数学中心（向上偏移 1–2% 高度）。
- 箭头、连线抵达矩形边缘时，连线终点应停在矩形描边的中线而非外缘。
- 同一行两种字号（如 24 标题 + 14 副标题）混排时，应共享同一 baseline，而非各自顶对齐。

执行上以 8 网格为骨架，局部以 1–2px 微调为校准；不要在 spec 中用奇数坐标，渲染后做光学验证。

### 留白节奏

留白不是空地，而是有名字的结构。三种节奏型可在一套 deck 中循环：

- **大留白（≥40% 画布）**：用于 opening、closing、insight，承担仪式感与权威。
- **标准留白（25–35%）**：用于 context、solution、proof，承担阅读舒适区。
- **紧致留白（15–25%）**：用于 evidence（数据页），承担信息密度但不拥挤。

相邻两页不得使用同一种留白型；连续三页不得同一种「留白职责」（`empty_space_role`）。

## Typography Engine

先选字体人格，再选字号。默认最多两族：一族承担 display/editorial，一族承担正文与数据。标题优先表达洞察，1–2 行；正文短句 2–4 行；来源 1–2 行。标题短句行高 1.05–1.15，正文 1.3–1.5；中文正文不加装饰性字距，拉丁眉标可使用 0.4–1.2pt。中英混排分别调用 CJK 与 Latin 字体，避免仅靠同一字体覆盖所有字符。

回退顺序固定为：缩短标题 → 改变文本框宽度 → 改变构图 → 拆页；不得先缩小字号。文字框必须同时声明 `max_lines`、`line_height`、`padding` 和必要时的 `ink_anchor`，渲染后以实际可读性复核。若字体不可用，保持 x-height、笔画密度、衬线/无衬线人格与字重关系，不追求字面字体名一致。

### 字号阶梯（建议）

| 角色 | 设计单位 px | 适用 |
|---|---|---|
| L4 Statement | 52–80 | 封面/章节扉页单句主张 |
| L3 Display | 42–64 | Hero 标题、关键结论 |
| L2 Title | 30–42 | 页面主标题、Section H1 |
| L1 Lead | 22–28 | Lead 段、图表标签 |
| L0 Body | 16–20 | 正文、说明文字 |
| L-1 Caption | 12–14 | 来源、注释、图例 |

跨页字号等级数 ≤ 4。同一页内字号等级数 ≤ 4（OS §07）。任何尺寸变化都应回应「视觉权重」的差异，不因「刚好放下」而缩字。

## Deck Rhythm Model

单页成立不等于整套 deck 成立。为整套演示建立阶段序列，并让能量、密度、重心和页面家族随叙事推进而变化：

| 阶段 | 主要任务 | 推荐页面家族 | 能量/密度 |
|---|---|---|---|
| opening | 建立世界与问题 | HERO / MINIMAL_STATEMENT | high / sparse |
| context | 给出必要背景 | EDITORIAL / FRAMEWORK | medium / balanced |
| problem | 让张力具体化 | NARRATIVE / COMPARISON | medium / balanced |
| insight | 提出关键判断 | MINIMAL_STATEMENT | low–medium / sparse |
| evidence | 证明判断 | DATA STORY | low / dense但不拥挤 |
| solution | 展示方案结构 | FRAMEWORK / NARRATIVE | medium / balanced |
| proof | 给出案例或结果 | DATA STORY / EDITORIAL | low–medium / balanced |
| vision | 放大未来意义 | HERO / EDITORIAL | high / sparse |
| closing | 明确行动与记忆 | MINIMAL_STATEMENT | low–high / sparse |

至少为每页记录 `rhythm_stage`、`energy`、`density`、`gravity_anchor` 和 `continuity_token`。连续页面不得同时重复阶段、密度、重心和主刺激；高信息页之后优先安排留白或低能量页。所谓“电影感”只能通过阶段顺序、信息揭示、能量曲线和视觉记忆锚点实现，不能靠炫技转场。

## Family Contract

页面家族必须同时声明四件事：`use_when` 使用场景、`content_structure` 内容结构、`visual_focus` 视觉重点、`do_not_use_when` 禁用情况。推荐路由如下：

| Family | 使用场景 | 内容结构 | 视觉重点 | 禁用情况 |
|---|---|---|---|---|
| HERO | 发布、章节、单一对象 | 一句主张 + 一个主体 | 尺度、方向、留白 | 多结论、密集证据 |
| EDITORIAL | 品牌、观点、案例 | 眉标 + 叙事标题 + 语境媒体 | 版心、非对称、编辑节奏 | 需要精确比较的页面 |
| NARRATIVE | 体验、过程、转折 | 起点 → 变化 → 含义 | 阅读路径与时间/空间推进 | 无明确顺序或关系 |
| DATA STORY | 论证、管理层决策 | 洞察标题 + 单一关系 + 来源 | 直接标注、共同基线、低噪声 | 无可靠数据或多关系混在一图 |
| COMPARISON | 选择、前后、差异 | 相同坐标系的 A/B | 对称或可控非对称、差异信号 | 比较口径不一致 |
| FRAMEWORK | 系统、方法、能力模型 | 3–5 个层级/模块 | 结构与连接可扫描 | 超过 7 个同级节点 |
| MINIMAL_STATEMENT | 原则、结论、行动 | 一句结论 + 必要限定 | 大留白、单重心、权威感 | 需要展示详细证据 |

如果页面无法满足一个 Family 的内容结构，应改用文字、拆页或重构，而不是强行增加容器。黄金比例、非对称、编辑版心和 Dashboard 均是可选语法；选择必须由内容关系和观看场景解释。

## Critic 读取顺序

Art Critic 必须同时读取 Strategy、Direction、Page Intent、spec 与渲染证据。只描述可观察问题，例如“标题、图表和右上数字同时抢第一注意点”，不要写“感觉不高级”而不给原因。每条问题至少包含 `observation / violated_intent / severity / minimal_fix / recheck`。
