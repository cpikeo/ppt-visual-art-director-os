# Theme DNA Library

## Theme contract

主题只定义视觉人格，不重复网格、通用层级、图表准确性、通用反模式和发布门。每个主题提供：`identity`、`perception_goal`、`narrative_mode`、`spatial_grammar`、`composition_grammar`、`typography_voice`、`color_behavior`、`media_behavior`、`chart_behavior`、`motion_posture`、`forbidden_signals`，以及最小运行时 token：`colors`、`fonts`、`constraints`。

## Visual World Matrix

主题选择必须同时比较七个维度：`perception_goal`、`spatial_grammar`、`typography_voice`、`color_behavior`、`media_behavior`、`chart_behavior`、`forbidden_signals`。颜色只是 token，不是主题本身；如果两个主题只改变色板而没有改变空间、媒体或图表行为，则合并为一个主题变体。

## Mature themes

| ID | 人格 | 感知目标 | 空间/构图 | 排版/色彩 | 媒体/图表 | 适用内容 |
|---|---|---|---|---|---|---|
| VP-001 | Zen Minimalism | 安静、沉思、权威；让结论以低噪声方式被相信 | 单一开放空间，柔和非对称；主焦点偏置，留白承担节奏，不做平均分栏 | 中性无衬线，宽松行距；低饱和自然色，Accent 只标记一个转折或结论 | 背景用建筑光、纸面或石材细节，前中后景弱化；图表去边框、去冗余网格，直接标注单一趋势 | 原则、品牌哲学、轻量战略 |
| VP-002 | Song Elegance | 人文、含蓄、文化记忆；让证据像被细读而非被宣告 | 纵向游走与东方留白；以一条阅读轴串联标题、注释和主体，避免装饰性对称 | 人文衬线负责标题与引文，中性字体负责正文；墨色、纸色和极少朱砂只作语义标记 | 器物、山水、手工艺必须带真实环境与材质线索；图表采用注释式证据、细轴线和克制标记 | 文化、人文、品牌故事 |
| VP-003 | Swiss Modern | 精确、清晰、结构可信；让关系一眼可核验 | 严格列网格与左对齐模块；一个工程化主轴，尺寸、间距和层级保持可复用 | 中性无衬线，高识别度数字；中性底色配单一高对比信号色，禁止多色竞争 | 媒体强调对象结构、截面或系统关系；图表优先水平条、斜率、结构图，轴、单位和比较口径明确 | 企业、系统、结构化决策 |
| VP-004 | Luxury Editorial | 稀缺、精致、编辑感；让少量信息获得高价值注意力 | 杂志版心与非对称大图；主图承担视觉重心，文字与数据沿版心退让，不堆叠卡片 | 编辑衬线建立品位，中性正文保障阅读；暖中性为底，金属色只作一个符号性强调 | 高端对象摄影须有可感知材质与环境；图表减少类别、放大关键比较，采用编辑式标题与来源注 | 奢侈品、品牌叙事、产品故事 |
| VP-005 | Apple Minimal Future | 清洁、期待、产品信任；让功能关系显得自然而可控 | 产品舞台与精密留白；单一 Hero 配短路径说明，控制页面能量逐步上升 | 中性无衬线，清洁冷白与深色文字；蓝色或单一信号色只承担交互、状态或重点指标 | 产品媒体必须说明使用场景或空间关系；KPI、趋势和对比图表轻量化，隐藏重复读数通道 | 产品发布、功能演示 |
| VP-006 | Organic Architecture | 触感、自然、空间深度；让系统关系具有可感知的环境 | 有机层叠与建筑尺度；曲线、层次和留白形成连续路径，避免把有机形状做成装饰贴片 | 人文衬线配高可读无衬线；土色、自然绿和石色按层级使用，保持低饱和与材质一致 | 背景使用建筑、自然材料或光影过渡，主体前景清晰；图表优先关系、结构和路径表达，线条保持轻 | 空间、可持续、体验系统 |
| VP-007 | Data Intelligence | 清晰、可信、决策导向；让结论、证据和行动顺序明确 | 40/60 证据分栏与结论锚点；左侧结论、右侧证据或反之但全篇固定，数据页低能量 | 中性无衬线与高识别度数字；单一蓝色信号配中性灰，强调色只用于决策点 | 背景保持低干扰，使用结构纹理而非氛围图；图表直接标注、单位完整、比较口径清晰，优先条形、趋势和瀑布 | 战略、分析、管理层决策 |
| VP-008 | Luxury Brand Identity | 戏剧、稀缺、品牌记忆；让品牌符号成为唯一高峰 | 电影式大空间与尺度张力；一页一个品牌动作，使用前景遮挡、远景留白建立戏剧层次 | 高对比编辑字与克制正文；黑、象牙、金属只作层级和符号，不以金属渐变制造奢华 | 单一品牌/产品 Hero 必须有真实材质与光线逻辑；非仪表盘图表只保留能支撑宣言的一个关系 | 品牌发布、宣言、旗舰叙事 |
| VP-009 | Editorial Data Fusion | 研究、判断、编辑可信度；让数据像经过编辑审阅的证据 | 编辑栏式证据场；标题、来源、图表和注释共用栏宽，留白分隔论点而非填空 | 研究衬线用于观点与章节，中性正文与数字保障效率；编辑红或研究蓝只标记关键证据 | 纪实摄影必须有现场语境与来源；低噪声研究图表保留必要轴线、来源和方法注，不做装饰性数据墙 | 研究、洞察、趋势报告 |
| VP-010 | Human Experience | 温暖、具体、关系可信；让抽象策略落到真实的人与情境 | 温暖呼吸、路径与关系；以人物或关系节点作重心，保留可进入的空白区域 | 人文无衬线或柔和衬线，正文优先可读；暖中性色配一个关系或行动信号色 | 真实生活语境须表现人物与环境关系；图表优先简单路径、流程和对比，标签靠近语义对象但不碰撞 | 用户体验、服务、组织与社会议题 |

## Shared execution rules

所有主题共享同一套 Theme Contract 与运行时接口；以下规则只约束视觉执行，不新增字段。背景必须被当作空间叙事处理：先根据页面内容与情绪目标决定前景、中景、背景，再安排主体安全区与内容保护层。图像不得作为独立贴片，材质与纹理不得承担无意义装饰。图表必须继承主题的空间语言、排版节奏和色彩语义，同时遵守统一的数据准确性、标签安全、来源完整和低噪声原则。动效只采用符合主题人格的慢速、优雅、目的明确的显现或过渡，不改变编译器 API 与页面逻辑。

## Editorial default language（编辑感默认语言 · 全局微语言）

以下不是新主题，而是所有主题默认继承的「编辑感」最小执行语言——主题人格只决定它的浓淡。高级感来自克制的版心与重复出现的签名动作，而不是从某个主题反向复制版式。

### 1. 章节编号作为跨页连续锚点

封面、章节扉页、关键结论页可重复出现「编号 / 章节名 / 页码」三段式弱导航（字号 11–13px、字距 0.4–0.8pt、颜色 `muted`）。它不与标题竞争，但能让 8 页以上的 deck 在翻页时保持识别度。页码永远在同一象限（左下 / 右下）；不要每页换一个位置。

### 2. 编辑栏式证据场

`evidence_field` 语法下，标题、引文、图表和来源共用同一栏宽（按 12 列网格的 6/12 或 8/12 切割），用留白分隔论点而不是用卡片墙或边框。所有元素共享同一条左缘轴线（左对齐基线），右缘随内容自然收尾；切忌「九宫格 + 圆角容器」。

### 3. 一句主张 + 一段证据 + 一个来源

每页最多三段文字：「主张（Statement）」承担 H1，「证据（Evidence）」承担 H3/Body，「来源（Source）」承担 Caption + 链接。少于三段是合理的（封面、章节扉页只保留 Statement），多于三段必须拆页或并入图表标签。来源永远在左下角，固定 `x=48, y=672, width=1184, height=32` 区域，不被任何主体侵入。

### 4. 留白职责命名

每页必须显式声明 `empty_space_role`：

- `protect_focus`：保护单一主焦点的视觉权威
- `create_authority`：建立机构/编辑的可信距离
- `separate_chapter`：切分章节或叙事阶段
- `hold_emotion`：承载情绪或仪式感

留白是结构，不是「剩下没填满的地方」。同一 deck 中三种留白职责可循环出现，但同一职责不应连续 3 页重复。

### 5. 摄影叙事的比例纪律

含 Hero / 主体图的页面，图像宽度与标题栏宽度形成 1.618 / 1 / 0.618 之一的比例关系；不可用「图占半页 + 文字占半页」的对称切割。图像留白锚点（safe area for text）必须预先声明，文字不进入主体安全区。

## 主题混血与原型适配

- **混血边界**：一次只混一个维度——借 VP-004 的排版人格，**或**借 VP-001 的留白纪律，不得同时借色彩与空间语法两个以上维度；混血结果仍须通过主题矩阵七维自检，过不了就退回单主题。
- **原型适配**：主题 `composition_grammar` 与 Layout Search 原型存在天然适配（Zen Minimalism ↔ statement / editorial 非对称语法；cinematic 人格 ↔ stage / hero 语法；evidence_field ↔ 分栏证据原型）。不适配的组合（如 Zen 人格 × dashboard 式原型）不是禁令，但必须在 `design_rationale` 里说明为什么。

## Runtime translation

```python
theme = {
  "colors": {
    "background": "#...", "surface": "#...", "primary": "#...",
    "secondary": "#...", "accent": "#...", "ink": "#...", "muted": "#..."
  },
  "fonts": {"cn": "...", "latin": "...", "display": "..."},
  "text_default": "ink",
  "chart_primary": "primary", "chart_secondary": "accent", "chart_muted": "secondary",
  "constraints": {"accent_max": 0.05, "max_colors": 5, "min_whitespace": 0.35},
  "differentiation": {
    "perception_goal": "...", "narrative_mode": "...", "spatial_grammar": "...",
    "composition_grammar": "...", "media_grammar": "...",
    "chart_grammar": "...", "energy_motion": "..."
  }
}
```

换主题只应改变上述参数与页面家族的表达方式，不得改变编译器 API。运行时只读取现有 `colors`、`fonts`、`constraints` 与 `differentiation`；不得通过主题参数改写页面逻辑、数据口径或图表准确性。若主题不改变空间、媒体或图表行为，则将其视为主题变体，不新建人格。主题切换后必须保持同一安全区、标签安全、来源完整和发布门，并通过渲染结果确认背景与内容自然融合。

## 主题种子（route.py 的成品锚点）

`scripts/route.py` 的 `DIRECTION_PRESETS` 为每个设计方向（`quiet_minimal` / `editorial_brand` / `product_stage` / `evidence_first`）预置了一份 `theme_seed`：一组调好的 `colors`（background / surface / primary / secondary / accent / ink / muted）与 `fonts`，可直接落进 `spec.theme`。`plan_page` 与 `plan_deck` 都会返回这份种子。

种子是**起点锚点，不是终点模板**：`primitives.derive_tokens` 会从种子色机械展开完整色阶（panel / hairline / track / veil / ramp / series / on_dark / on_accent…），调用方也仍可覆盖任意一项。它的作用只是消除「选了方向却还要自己手挑 hex」的空白——方向不再是一段形容词，而是一组能直接渲染的锚点色。色彩插值在 OKLab 感知空间进行，因此派生出的中档色明度均匀、不偏灰偏浊。

## Calibrated family seeds（v3.0 · 行为 + 种子骨架）

种子只是兜底骨架：`brand_colors` 与 `visual_world` 的材质判断永远优先；
运行时消费 `design_intelligence.COLOR_DIRECTIONS`（单一真源），本表只读不复制。
regime/sat 人格来自 `memory/calibration_space.json` 的实测族带。

| family | regime | sat | 材质/光性语言 | 种子骨架（foundation/supporting/information/accent） |
|---|---|---|---|---|
| luxury_editorial | light | quiet | 暖象牙纸、洞石与青铜、柔窗光 | #F2EDE4 / #9A8C74 / #403B32 / #9C5A2E |
| song_elegance | light | quiet | 宣纸、墨石、茶绿丝、北向漫光 | #F3F1EA / #8B8D84 / #22241F / #5E7562 |
| zen_minimal | light | quiet | 手工纸、雾、止水、无影光 | #F5F4F1 / #9A9A96 / #1E1E1C / #6E6E6A |
| nordic_quiet | light | quiet | 石灰抹面、浅橡、陶、低冬阳 | #EFECE6 / #A79E90 / #33302B / #8A7A5F |
| quiet_luxury | light | quiet | 香槟金属发丝、taupe 石、纱帘海光 | #F1EDE6 / #A99878 / #37322A / #B08D4F |
| monochrome_noir | dark | quiet | 黑石、单束掠光、石墨尘 | #101010 / #4A4A4A / #F2F2F0 / #8C8C8C |
| cinematic_narrative | dark | warm | 琥珀暮色、海岸空气、黄铜光 | #141210 / #5C4A33 / #EFE3CE / #C08A3E |
| nature_luxury | dark | quiet | 深林绿、水面雾、湿石、冷漫光 | #16211C / #4E6157 / #EDEFE9 / #6FA08C |
| organic_systems | light | quiet | 燕麦纤维、叶脉微距、鼠尾草陶土 | #EFEBE2 / #A8A394 / #3B3A33 / #7C8B6F |
| precision_tech | mixed | quiet | 光学玻璃、钛边、石墨上受控蓝信号 | #0D0F12 / #3A4148 / #F2F4F6 / #2E7BD6 |
| apple_future | light | quiet | 钛微拉丝、雾白舞台、单品光 | #F6F6F7 / #9BA0A6 / #1D1D1F / #0071E3 |
| data_intelligence | dark | quiet | 深石墨证据场、钢灰结构、单一受控强调 | #141619 / #454B52 / #EDEFF1 / #3E8E7E |
| editorial_intelligence | light | quiet | 新闻纸白、墨黑、单一信号红、硬杂志网格 | #F7F6F3 / #8E8E8C / #141414 / #C8102E |
