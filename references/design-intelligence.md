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

**色彩派生顺序（判断，不是模板）**：`brief.brand_colors`（品牌色，route 入口即覆盖方向预设）> `visual_world` 的材质/光性判断（graphite+cold white 还是 warm white+organic gray，由内容决定，不由「科技=蓝」这类标签决定）> 方向预设种子（仅兜底骨架）。`color_behavior` 是行为判断（单一信号色 ≤5%、结构色无彩度……），永远不是具体色值；图表色走 `chart_palette` 语义角色（primary/secondary/neutral/accent/negative），由主题映射派生。

Direction 不是装饰偏好，而是对受众心理的假设。例如技术决策使用 `technical_clarity + evidence_field + direct_label`；品牌宣言可以使用 `calm_authority + cinematic_stage`，但数据页仍必须回退到低能量证据场。图片不是默认背景，图表不是默认组件，文字不是覆盖层；三者只有在承担明确的信息、情绪或证据功能时才进入 spec。

### Visual Concept（核心视觉隐喻）

Direction 里最重要的决定，是让 `visual_world` 成为一句**可展开的视觉隐喻**，而不是一组形容词。

- 错误（形容词堆叠）：`visual_world: "高端、科技、蓝色渐变背景"` —— 这只是「想要什么」，没有「怎么实现」。
- 正确（可展开的隐喻）：`visual_world: "深海玻璃生态：透明折射、柔性光场、层叠空间表达复杂系统的连接"` —— 它规定了材质（玻璃/折射）、光线（柔性光场）、空间（层叠）三个可落地的语言；任何一页的背景、图表、图片都能据此判断「是否属于这个世界」。

一个隐喻要成立，必须能回答三个问题：

1. **材质语言**：这个世界由什么材料构成？（纸 / 玻璃 / 金属 / 织物 / 光）
2. **光影语言**：光从哪来、什么性格？（单一硬光 = 产品舞台 / 柔和环境光 = 编辑 / 折射光 = 玻璃）
3. **空间语言**：元素之间是并列、层叠、还是纵深？（决定构图语法与留白角色）

隐喻是一致性的来源，也是「打破规则」时的判断依据：当一页不知道该怎么摆，问的不是「哪种布局好看」，而是「在这个世界里，这个信息应该处于什么位置」。

反例边界：隐喻不是装饰主题。不要为了「有一个隐喻」硬套意象（如给纯数据报告套「星空探索」）；当内容不需要空间隐喻时，`solid_world` + 编辑版心本身就是正确选择——诚实比意象重要。

## Content → Visual Language 映射

| 内容信号 | 感知目标 | 视觉动作 | 默认反例 |
|---|---|---|---|
| 单一关键结论 | 让观众迅速记住 | 大尺度标题、主动留白、唯一重心 | 多个 KPI、标题像字段名 |
| 复杂系统 | 让关系可扫描 | 分层、路径、连接线、稳定网格 | 图标墙、无方向卡片墙 |
| 证据与风险 | 让观众相信 | 直接标注、共同基线、来源可见、低能量 | 3D、装饰图、隐藏不确定性 |
| 人物/案例 | 建立具体感与信任 | 有语境摄影、主体留白、叙事顺序 | 泛化图库、无关肖像 |
| 高端品牌/发布 | 建立期待与记忆 | 单一 Hero、尺度张力、克制光线 | 金色铺满、产品堆叠 |
| 行动建议 | 让下一步明确 | 结论式标题、行动动词、限定条件 | 把建议做成装饰性标语 |

### 内容类型 → 路由（route.py）

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

**占用率口径**：存在两把尺子，各司其职，勿混用。

- **墨迹率**（`render_check.occupancy`）：渲染像素差值（96×54 采样、与角落底色比较），度量「非背景像素占比」。用于 `min_whitespace`（物理最小留白）与跨页 `ink_shift`（呼吸变化的真实墨迹差）。细线/细柱图表墨迹率天然极低，故**不用于** density 对照。
- **几何占用率**（Critic `_content_occupancy`）：Σ(非背景元素 bbox 面积) / 画布，度量「视觉密度」（内容对象占用的视觉空间）= `1 - 留白率`。density 对照据此换算（见「留白节奏」章）：sparse = 留白 ≥40%（几何占用 ≤60%，单边，越空越 sparse）、balanced = 留白 25–35%、dense = 留白 15–25%。声明 `balanced` / `dense` 前应让内容对象真实铺到对应比例，或把 density 下调一档；反之声明 `sparse` 时，留白多正是目标，不应被误判为「空挂」。

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
  design_rationale: "可选·声明层：一句「为什么这样摆」——选择 × 理由 × 否决了什么"
  page_family: "COVER | HERO | EXECUTIVE_SUMMARY | EDITORIAL | NARRATIVE | DATA_STORY | COMPARISON | FRAMEWORK | TIMELINE | DASHBOARD | MINIMAL_STATEMENT | CASE_STUDY | CLOSING"
```

页面家族路由为：`establish → COVER/HERO`，`context → EXECUTIVE_SUMMARY`，`explain → FRAMEWORK/TIMELINE`，`compare → COMPARISON`，`prove → DATA_STORY/DASHBOARD`，`case → CASE_STUDY`，`recommend/close → CLOSING`。布局表达可映射为 `Executive Strategy → EXECUTIVE_SUMMARY/DATA_STORY`、`Editorial Luxury → EDITORIAL/CASE_STUDY`、`Data Intelligence → DATA_STORY/DASHBOARD`、`Comparative Analysis → COMPARISON`、`Narrative Flow → NARRATIVE/TIMELINE`；这只是内容到空间的路由，不是新增模板。每个页面仍复用同一安全区、来源区、字阶和色彩语义。一张图只回答一个关系；没有诚实图表映射时使用文字或表格。图表先完成 `data analysis → insight extraction → visual encoding → chart design → reading optimization`，再进入生产；它必须表达一个可复述的数据关系，而不是作为装饰性对象填充页面。

### Design Intent（决策理由层）

`design_rationale` 是可选的声明字段，不参与渲染与评分；它回答「**为什么这样摆**」——采用的选择、理由、以及被否决的替代方案（例：「证据偏右置：延续上一页阅读轴；否决居中——会打断叙事动线」）。两个消费点：修正时先检查**意图是否被几何兑现**（声明的重心、轴线与 spec 是否一致），`record_dna` 沉淀时引用它作为决策出处。写不出 rationale 的页面，说明布局是排列，还不是设计。

## Composition Engine

先声明视觉重心，再分配空间。使用 **12 列逻辑网格 + 8 单位基线网格**：12 列用于决定栏宽和比例，8 单位用于坐标与间距落地；不要把网格当作审美本身。构图判断依次检查：主焦点是否可在缩略图找到；重心是否与 page intent 一致；留白是否有职责；信息密度是否服务于叙事阶段；相邻页面是否形成疏密与重心变化；是否存在可解释的比例关系（黄金比例可作为候选构图启发，不得强行套用）。

建议记录 `gravity_anchor: {x, y, radius}`、`occupancy_target`、`reading_path` 和 `continuity_token`。跨页连续性应保持同一组字体、线宽、来源位置和色彩语义，同时允许封面、证据页、结论页拥有不同能量。

### 构图算子（Composition Operators）

版式原型（Layout Search 的候选）只是算子组合的常用驻点，不是版式的边界。从意图推导构图时，先组合算子，再看结果落在哪个原型附近：

- **轴**：对称轴 / 错位轴（左右错半格）/ 偏置轴（0.382、1/3）——决定重心的「被决定感」。
- **切分**：不等分（黄金 / 三分 / 2:1）优先于等分；等分只在对比页（同坐标系 A/B）使用。
- **尺度对偶**：极大 × 极小（64px 宣言 × 12px 来源）是比「中字号群」更强的层级语言。
- **叠压**：背景画心与前景内容的层叠建立纵深——比并列摆放更像「同一个世界」，而不是「贴上去的元素」。
- **动线**：水平（叙事）/ 垂直（庄重）/ 对角（张力）——阅读路径的方向本身携带情绪。

两条反模板纪律：同一 deck 内相邻两页不复用同一算子组合（轴 × 切分 × 动线至少一项变化）；连续服务同一客户/系列的 deck，若与前一副同家族同原型，第三副应更换构图语法——品牌连续性例外，但须在 `design_rationale` 里声明。

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

先选字体人格，再选字号。默认最多两族：一族承担 display/editorial，一族承担正文与数据。标题优先表达洞察，1–2 行；正文短句 2–4 行；来源 1–2 行。中文正文不加装饰性字距，拉丁眉标可使用 0.4–1.2pt（行高与字号阶梯见下）。

回退顺序固定为：缩短标题 → 改变文本框宽度 → 改变构图 → 拆页；不得先缩小字号。文字框必须同时声明 `max_lines`、`line_height`、`padding` 和必要时的 `ink_anchor`，渲染后以实际可读性复核。若字体不可用，保持 x-height、笔画密度、衬线/无衬线人格与字重关系，不追求字面字体名一致。

### 字号阶梯（全库唯一真源）

字号不是区间堆叠，而是**带驻点的比例系统**：相邻级差 ≥1.25×（最小可感差异），每级有驻点与容许区间。design-system / themes / SKILL 一律引用本表，不再各自声明字号。

| 级 | 驻点 px | 区间 px | 典型角色 |
|---|---|---|---|
| L4 Statement | 64 | 40–80 | 宣言、封面主张、章节扉页、KPI 主数字 |
| L3 Display | 44 | 40–56 | 页面主标题、Hero 结论 |
| L2 Title | 32 | 28–36 | 小节标题、图表标题 |
| L1 Lead | 22 | 20–24 | 导语、图表直接标注 |
| L0 Body | 17 | 16–20 | 正文、说明文字 |
| L-1 Caption | 12.5 | 11–14 | 来源、注释、图例、眉标 |

四条纪律：

1. **Statement 是角色，不是字号**：承担页面唯一主张的元素即 Statement；机器锚点阈值为 40px（`STATEMENT_SIZE`），40–51px 的 Statement 只用于 dense 页，sparse 页的宣言应 ≥52px。
2. **每页 ≤4 级、全 deck ≤6 级**，取值优先落在驻点；任何偏离驻点的取值都必须能回答「这一级在强调什么」——不为「刚好放下」而设中间字号。
3. **行高**：L4/L3 1.05–1.15、L2 1.15–1.25、L1/L0 1.3–1.5（中文正文取上限，给字腔呼吸）、Caption 1.2–1.3。
4. **字重与墨色先于字号**：两级层级优先用「同字号 × Regular/Bold」或墨色/淡墨对比表达，再动字号——字号差是层级语言中最贵的一种，滥用会把阶梯顶穿。

### 中文排印（CJK Craft）

- **避头尾**：行首不得出现 `，。、；：？！》」』）` 等收尾标点，行尾不得出现 `《「『（` 等起始标点；spec 文本按此断行，不依赖渲染器默认行为。
- **标点策略**：中文标点全角、数字与拉丁半角；行尾长标点可悬挂或挤压（省略半角宽）；禁止两端对齐把字距拉开。
- **中西混排**：CJK 与拉丁/数字之间留 1/8–1/4 em 间隙（微距规则 1）；中文语境括号用全角，内嵌纯英文短语时可用半角但全页一致。
- **竖排**：仅东方语汇主题（VP-002 一系）且仅限短题（≤8 字）、右起；与横排的混用必须整页声明，不做半竖半横。
- **双轨字体**：中英分别声明 `fonts.cn` 与 `fonts.latin`；回退时保持 x-height、笔画密度与衬线人格一致，不追求字面字体名。

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

修正时先读 `deck_notes.director_verdict`，一次只修 `primary_lever`：总监先做「修哪个最值」的判断，
再谈「怎么修」。跑完一轮 QA 之后再看下一条杠杆；禁止把 Top3 一次全改——并行改三处，
出问题时无法归因，多出来的轮数比省掉的多。

## Design Judgment（何时打破规则）

规则是下限，不是上限。这套系统的所有约束——Accent ≤5%、一页一焦点、相邻页留白不重复、卡片 ≤4——都是「不出错」的保底，不是「出彩」的公式。世界级设计的决定性瞬间，恰恰发生在**规则互相冲突、必须做出取舍**的时候。学会在冲突中选对牺牲对象，才是从「执行规则」到「做视觉判断」的分水岭。

固定的取舍优先级（由高到低，低层永不为高层让位）：

1. **事实与语义 > 一切**：数据不能为构图造假、不能为留白删减、不能为美观换口径。这条没有例外。
2. **可读性 > 审美**：当「留白比例」与「文字可读」冲突，牺牲留白，不缩字号。
3. **内容任务 > 视觉惯例**：黄金比例、三分线、非对称都是候选语法，不是义务。内容关系说不通，就放弃比例。
4. **情绪 > 秩序**：opening 与 closing 这类情绪高潮页，可以主动打破「相邻页密度互斥」的节奏，用一次「重复的安静」制造仪式感——前提是这是**主动选择**，并在 `empty_space_role` 里说清为什么。
5. **品牌 > 通用审美**：品牌规定的字体/色彩/构图语法，优先于「更通用更好看」的默认审美。

「打破」的两个判据（缺一不可）：

- **它是主动决定，不是疏漏**：打破后要能一句话说清「我为什么在这里不守这条规则」，并且新的重心比守规则时更明确。守规则是「安全」，打破规则且更聚焦是「高级」；打破规则且更混乱，只是失败。
- **它只打破一条**：一次只牺牲一个约束，用其余所有约束的「更严格」来补偿。同时打破两条以上，通常意味着你已经不知道自己在做什么。

对 Art Critic 的含义：当检测到「违反某条规则」时，先问「这页是否用更明确的重心 + 更克制的其余部分做了补偿」，再决定扣分还是标记为「有意图的取舍」。规则捕获的是「没有意图的乱」，不是「有意图的破例」。

## V3 视觉校准与判断（参考空间校准闭环）

> 10 套世界级设计板（2026-09-10 用户提供）被**测量**而非被复制：切页
> （79 个页面单元）测出面积律、色相族、饱和域、明度域、负空间、图片占比
> 与排印密度。vNext 把这些实测律**内联为 `design_intelligence.CALIBRATION_LAWS`
> 常量**（原先存放在一个外部 JSON 里，连同测量脚本一起被删——引用不到的
> 证据文件既不参与任何判定，又制造悬空指针；想恢复实测闭环，把测量结果
> 写进 `memory/calibration_space.json` 就会被 `calibration_laws()` 覆盖）。
> 参考空间只校准判断阈值，任何布局/色板/组件的照抄仍按模板违规处理。

### 实测律（global，p50 除非注明）

| 律 | 实测 | 运行时用途 |
|---|---|---|
| 色彩面积律 | c1≈55% [35–85] / c2≈21% / c3≈11% / c4≈6% | 70/20/8/2 主张的实测形态：foundation 支配、accent 簇 ≤8%；`color_plan.ratio_targets` |
| 色相族 | 页 p90 = **1**（+中性不计） | `visual_calibration_score.color`；主题级宽一档至 2 |
| 饱和 | quiet 族 sat90 ≤0.35；warm-material 族 ≤0.65 | `color_plan.constraints.sat90_max` 按族人格切换 |
| 明度域 | dark 0.05–0.35 / light 0.55–0.97，逐 deck 一致 | 家族人格 regime；混排需面板结构 |
| 负空间 | 文字主导页 p50≈0.40；图片主导页可近 0（图片承担空间） | layout 维度的条件判读 |
| 图片占比 | image-led 页 18–60%；文字页 ≤20% | 媒体闸门后的构图预算 |
| 排印密度 | edge 0.016–0.053 | 信息维度的密度参照 |

### Adaptive Color Intelligence Engine

`color_plan(direction, brief)`：比例目标（70/20/8/2）+ 实测约束 + 种子骨架 +
材质/光性语言 + 禁用清单（高饱和渐变 / SaaS 蓝紫 / 彩色卡片墙 / 廉价科技光）。
派生顺序固定：`brief.brand_colors` > `visual_world` 的材质/光性判断 > 方向种子骨架。
14 个方向族 = 10 个实测族（nature_luxury / nordic_quiet / monochrome_noir /
zen_minimal / luxury_editorial / precision_tech / organic_systems /
cinematic_narrative / editorial_intelligence / quiet_luxury）+ 4 个主张族
（song_elegance / apple_future / data_intelligence 已实测同类并入 + 保留主张命名）。
route 的四个方向预设经 `_DIRECTION_ALIAS` 归一（quiet_minimal→zen_minimal 等）。

### Visual Calibration Score

`visual_calibration_score(spec)`：五维静态分（layout .25 / typography .20 /
color .20 / image .15 / information .20，各 0–5 → 百分制），~0.3ms。
对照的是**带与律**（密度兑现与相邻差、字阶驻点与行长、色相族与色彩职责、
媒体闸门一致性、信息合同完整性），不是对照某张参考图。
`draft` / `review` 轮内置它作为「生成即知水准」的轻量验证（`qa["calibration"]`）。

### 提示词智能三层（asset_prompt V3）

`enhance_asset_card(card, family)` 纯函数注入：
- **动势层**（≤3 句）：spatial（leading lines / 单灭点透视 / 非对称平衡 / 侧向掠光）、
  natural（丝质流水 / 风动植被 / 层叠大气）、tech（克制光轨 / 精密边缘能量流 / 玻璃层纵深）；
- **微浮雕层**（≤2 句 + 纪律 2 句）：eastern（纸纤维/宣纸/墨晕）、luxury（皮革纹/拉丝金属/
  软石/包装浮雕）、architecture（石灰岩/清水混凝土/玻璃折射）、technology（钛拉丝/机加工纹）、
  organic（叶脉/织物/苔藓）；纪律=微弱、低对比、近距可感知，禁明显纹理；
- **融合层**（≤4 句）：text-safe 负空间对齐、光向与页面光源一致、前中后景深层级、
  轻虚化分离、融入版面背景无贴纸边。

族 → 动势/材质键映射在 `FAMILY_MOTION` / `FAMILY_TEXTURE`；调用方显式传入永远赢。

### Fast Visual Intelligence Pipeline（速度）

`route.one_pass_plan(brief)` 一次调用固化 Stage 1+2（plan + deck_decision +
color_plan + 逐页 skeleton/layout/media/budget；冷 ~160ms、缓存 0.6ms）。
Stage 3 生成后 Stage 4 用 `--mode draft` 轻量验证（零渲染：guard 契约 + 结构/容量
判定 + 风险预测与策略 + 校准分，12 页 0.3s）；方向收敛走 review（只渲染变化页 +
Critic），发布走 release（全量 + Manifest）——**快的只是验证频次，不是标准**。

---

## 附录 A：引擎与模式细则（v3.2 从 SKILL.md 移入）

> 这些是**实现层细则**，写 spec 时不需要读；只在调引擎/排查行为时查。
> 判据没变，只是不再占用 SKILL 的首屏注意力。

**风险预测纪律（关键：出口是决策，不是审核）**：
- **先政策后稿**：起草之前读 `forecast_risk(brief)["policies"]`——文本密度高 → 先收紧
  `text_budget` 并全局 `auto_fit: true`；媒体不足 → 把省下的预算换成锚点尺度；构图复杂 →
  一页只承担一个关系。这些决定写进策略再生成，不要生成后靠 QA 反推；
- **风险即修单**：`risk_strategy(spec)["adjusted"]` 按策略键给出 `deck_policies`（整套政策）
  与 `page_actions`（逐页动作），`pages[]` 按 `risk_weight` 排序——一轮批量改完再验证；
- 每条风险带 `root_cause`（与 `director_verdict` 同一分类法）+ `prevention` +
  `predicted`（下游失败码）——直接对接「1 根因 = 1 轮」；
- 它用与 Critic/QA **同一套常量**做静态估计（不渲染）：预估是保守方向
  （宁可轻微高估不可漏报），`confidence` 标注可信度；
- 预测**从不阻断**任何阶段：不通过 ≠ 不许渲染，只是「先按策略改更划算」；
  异常时只记 `error`，主链照常跑。release 也跑预测（预测 vs 实测的差值本身是校准证据）。

**Design DNA 纪律（Schema v2：判断记忆，不是结果记忆）**：DNA 存「为什么这样设计」（design_problem + judgment：hierarchy/space/media/color_behavior/charts/anchor_rule/structure），不存「用了什么颜色/版式」（palette/font/色值字段一律拒收；实测色值与占比是证据，放 proven.measurements）。结果记忆会让 AI 变模板——科技=蓝、金融=黑金就是这么来的；判断记忆才跨主题迁移。DNA 不是模板/组件/固定页面——它是
「看到需求就知道该怎么做」的可复用判断（空间/版式语法/色板策略/字声/媒体处理/
图表人格/禁用信号）。`record_dna()` **只在上游校验 PASS 后调用**（真实发布过的
经验才值得记忆）；recall 命中时按当前内容重组，禁止照抄。

**Layout Search 纪律**：Layout Grammar 四要素（支配性/负空间/视觉锚点/阅读路径）
参数化生成几何，按信息重量、焦点、数据关系合成——不是 Hero01/Chart02 组件库。
候选只在 **spec 级**比较（不生成三份 PPT），选优后进入 spec 起草。原型只是构图算子
的常用驻点（算子语法见 `design-intelligence.md`「构图算子」）：相邻两页不复用同一
算子组合；连续 deck 同家族同原型时，第三副须换构图语法，或在 `design_rationale`
声明品牌连续性。

**Smart Fit Resolver（auto_fit）**：文本溢出在 spec 层按阶梯吸附——
`padding→0 → line_height→1.05 → 字号 -2px 递降（下限 12）→ needs_rewrite`。
**显式 opt-in**（元素 `auto_fit: true`），未声明零改动；编译器行为不变（仍只警告）。

### 执行模式细则（从 SKILL 移入，v3.2 减载）

- **渲染分级**：draft 完全不渲染（Guard + 几何 + 文本，<500ms）；review 只渲染 `classify_spec_change` 判定的变化页（改了 1 页就出 1 张 PNG，不是 12 张全量）；release 全量渲染 + 像素 QA。
- **语义变更分类**：`qa.classify_spec_change(old, new)` 把修改分为 `narrative`（只改声明/备注 → 不渲染）/ `page_render`（改了像素相关字段 → 只渲染该页）/ `full_render`（主题/画布 → 全量）/ `structure`（页数变了）。「改一句 insight 不必重渲染」是显式决策，不是缓存副作用；上一版 spec 存在 `<out>_render/last_spec.json`，是**唯一**保留的跨轮状态。

## Design Intelligence Layer（生成之前消灭设计错误）

> 执行链解决了「验证的重复」；本层解决「设计的重复」：**AI 不应该设计一次、验证很多次，
> 而应该在生成之前，大部分设计错误已被预测和消除。** 流程从
> 「生成→检查→发现→修复→再生成」升级为 **「理解 → 预测 → 决策 → 生成 → 一次通过」**。

### 渲染/复用/并行的实现口径（v3.2 从 SKILL 移入）

- **不重复计算**：两处复用只认一个判据——「会不会改变量到的数字」。① 编译产物复用（`spec_view` 编译视图指纹 + PPTX 字节核验 + PDF 归属）；② 页级像素缓存（键 = 本页投影 + 主题投影 + 画布 + dpi + 页内图片指纹 + 渲染器身份）。`page_intent` 的叙述字段 / `source_zone` / 备注既不产出像素也不参与量测，所以编译视图一致时 `compile_deck` 也跳过。`--no-cache` 一律绕过两处复用，也不写回任何记录。**没有第三种缓存**：Critic 结果缓存、语义投影缓存、版本闸与 `cache_version` 迁移已删。
- **并行硬上限 2**：渲染阶段 poppler 转换与像素测量串成一条流水、块间最多 2 worker（按 CPU 收敛，页数 <4 关闭）。设计推导与资产/渲染两条线只在 `qa.run_qa` 汇合一次，禁止逐页往返通信与循环等待。
- **色彩与图表纪律（deck 级）**：Guard 另核三件——全套色相族 ≤4（30° 一档，纸色与灰阶不计）、Accent 与主/辅色色相差 ≥12°、同一图表类型跨页共用一套标签规格（>1.25× 判漂移）。互补且等彩度的两色渐变提示「混成脏灰」，同族低对比渐变是留白手法、不打击。焦点落位任一轴线（中线/三分线/黄金分割线）时 Critic 记一次层级加分，完全不上线只在预检提示、不判罚。
