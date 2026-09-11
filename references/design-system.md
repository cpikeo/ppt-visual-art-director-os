# Design System（执行默认值 · 落地时查）

判断顺序：语义与事实 → 一页一焦点 → 可读性 → 空间与重心 → 分组与对齐 → 跨页连续 → 图表降噪 → 装饰与动效。下层手法不修上层问题。

## Canvas

1280×720、16:9、12 列逻辑网格 + 8 单位基线。每页声明 `focus/gravity_anchor/empty_space_role/energy/density`。黄金比例/三分/对称只是候选工具：内容关系说不通就放弃。相邻两页换密度、重心或版式其一；全套走建立→聚焦→展开→证据→收束的空间曲线。

## Hierarchy

五层：背景 → 环境/媒体 → 结构/标题 → 内容/数据 → 焦点；焦点层原则上只有一个元素。字号阶梯见 `design-intelligence.md`（全库唯一真源）。标题写洞察，眉标只做弱导航；空间不够时减词、减类、拆页——压缩字号是最贵的退路。

## Color

颜色同时承担 brand/emotion/hierarchy，`color_intent` 声明当前优先者。Accent 稀缺才有强调（≤5%）；层级优先用同色相明度阶梯。黑底/金色/渐变本身不是高级感。 Accent 的合法职责只有指认：指认答案（对比/推荐项）、指认当前（流程节点/最新值）、指认印章（东方语义标记）、指认主题（色彩即内容主题本身时的一次性语义标记，如黑金策略封面金标题——一次有效，重复即装饰）——不承担指认的 accent 即装饰。

## Background

按需组装 `Base → Image → Atmosphere/Light → Content Protection`，默认只开最少层。答不出「场景/焦点/文字安全区」就回退 `solid_world`。保护层只保可读，不把图片盖死。

## Image

图须声明功能（context/emotion/proof/hero）+ 主体/构图/留白锚点/裁切/溯源。相关性 > 构图 > 光线 > 材质 > 风格。图不烘焙文字/Logo/水印/数据；主体侵入文本区或改写重心时回退、重裁或换图。

## Grouping（分组四语言，由强到弱）

场（48px+ 间距即边界）> 线（0.75–1px 发丝线）> 型（字号/字重/墨色层级）> 盒（卡片：同时花掉间距/边框/底色三重预算）。卡片三准入：需物理容器语义（数据模块/KPI）/ 需与复杂背景隔离 / 需被指认为独立对象；否则退回场/线/型。

## Charts

准确 > 清晰 > 美观 > 装饰。趋势折线、比较条形、构成 ≤5 类、桥接瀑布。一图一关系；单位/期间/口径/来源齐备；直接标注优先于图例；一个强调点、三种语义色、八个类别封顶。可读表达（环心 KPI/sparkline/瀑布小计/目标线/末端标注）不新增数据通道。 精确值归表、形状归图：两者都要时表图并置，不用数据标签把图堆成表；图不能被一句话领走时，图下加 Insight 行（→ Insight: …）兜底——但先自问图是否画错了。

## Motion

全套 ≤2 种姿态，默认 `still`；动效只在改变阅读顺序/空间建立/数据理解时启用。静态交付下内容层级独立成立。

## Anti-patterns（症状，不是禁令）

卡片墙/平均九宫格/过度阴影/图标堆砌/随机图库/竞争性高亮/伪 3D/背景压字/为填空加细节——看到症状先问「哪个判断缺席了」，再按「删 → 简化 → 恢复空间 → 重构重心 → 换媒体 → 微调装饰」修。

---

## Theme DNA（人格矩阵 · 选型时查）

主题只定义视觉人格：`perception_goal/spatial_grammar/typography_voice/color_behavior/media_behavior/chart_behavior/forbidden_signals` + 最小 token（colors/fonts/constraints）。选型比七维，不只比色板；只换色板的是变体，不是新主题。

### Mature themes

| ID | 人格 | 感知目标 | 空间/构图 | 排版/色彩 | 媒体/图表 | 适用 |
|---|---|---|---|---|---|---|
| VP-001 | Zen Minimalism | 安静权威 | 开放空间、柔和非对称、主焦点偏置 | 中性无衬线宽行距；低饱和，Accent 只标一处转折 | 建筑光/纸面/石材弱景；图表去边框去网格，直接标注 | 原则、品牌哲学、轻战略 |
| VP-002 | Song Elegance | 人文含蓄 | 纵向游走、东方留白、单阅读轴 | 人文衬线标题 + 中性正文；墨纸色，朱砂只作语义标记 | 器物山水带真实环境材质；注释式图表、细轴克制标记 | 文化、人文、品牌故事 |
| VP-003 | Swiss Modern | 精确可信 | 严格列网格、左对齐、工程主轴 | 中性无衬线高识别数字；中性底 + 单一高对比信号 | 对象结构/截面/系统关系；水平条/斜率/结构图，口径明确 | 企业、系统、结构决策 |
| VP-004 | Luxury Editorial | 稀缺编辑感 | 杂志版心、非对称大图、主图即重心 | 编辑衬线 + 中性正文；暖中性底，金属只作符号强调 | 高端对象摄影重材质环境；减类别放大关键比较 | 奢侈品、品牌叙事 |
| VP-005 | Apple Minimal Future | 清洁期待 | 产品舞台、精密留白、单 Hero 短路径 | 中性无衬线冷白深字；信号色只担交互/状态/重点 | 产品媒体讲场景空间关系；KPI/趋势轻量化，藏重复读数 | 产品发布、功能演示 |
| VP-006 | Organic Architecture | 触感纵深 | 有机层叠、建筑尺度、连续路径 | 人文衬线 + 高可读无衬线；土绿石色低饱和 | 建筑/自然材料/光影过渡；关系结构路径表达，线轻 | 空间、可持续、体验 |
| VP-007 | Data Intelligence | 决策导向 | 40/60 证据分栏 + 结论锚点，全篇固定 | 中性无衬线高识别数字；单蓝信号配中性灰 | 低干扰背景结构纹理；条形/趋势/瀑布，直接标注口径齐 | 战略、分析、管理决策 |
| VP-008 | Luxury Brand Identity | 戏剧记忆 | 电影大空间、尺度张力、一页一品牌动作 | 高对比编辑字 + 克制正文；黑象牙金属作层级符号 | 单一 Hero 重材质光线逻辑；图表只留支撑宣言的一关系 | 品牌发布、宣言 |
| VP-009 | Editorial Data Fusion | 研究可信 | 编辑栏式证据场，留白分论点 | 研究衬线观点 + 中性正文数字；编辑红/研究蓝只标关键证据 | 纪实摄影重现场语境来源；低噪声图表留轴线来源方法注 | 研究、洞察、趋势 |
| VP-010 | Human Experience | 温暖具体 | 温暖呼吸、路径关系、人物作重心 | 人文无衬线/柔衬线，正文可读优先；暖中性 + 一行动信号 | 真实生活语境人物环境关系；简单路径流程对比 | 用户、服务、组织议题 |

### Editorial default（全局编辑微语言）

章节编号三段式（11–13px、muted）作跨页锚点，页码固定同一象限；`evidence_field` 下标题/图表/来源共栏宽、共左缘轴线；每页 ≤三段文字（主张 Statement + 证据 Body + 来源 Caption，来源固定左下 `x=48,y=672,w=1184,h=32`）；留白声明职责（protect_focus/create_authority/separate_chapter/hold_emotion），同职责不连续 3 页；Hero 图宽与标题栏取 1.618/1/0.618。 页脚箴言（motto）若启用，全套同一位置、同一句式、逐页复诵——箴言只在不变中生效；第二语言退为文化注释（竖排小字角落/副标），不与主信息争层级。

### 混血与适配

一次只混一个维度（借排版人格，或借留白纪律），过七维自检否则退回单主题。主题 `composition_grammar` 与版式原型不适配（如 Zen × dashboard）不是禁令，但须在 `design_rationale` 说明为什么。

### Runtime translation

```python
theme = {"colors": {"background":"#...","surface":"#...","primary":"#...",
  "secondary":"#...","accent":"#...","ink":"#...","muted":"#..."},
 "fonts": {"cn":"...","latin":"...","display":"..."},
 "constraints": {"accent_max":0.05,"max_colors":5,"min_whitespace":0.35},
 "chart_palette": {"primary":"...","secondary":"...","neutral":"...",
  "accent":"...","negative":"..."},
 "differentiation": {"perception_goal":"...","spatial_grammar":"...",
  "composition_grammar":"...","media_grammar":"...","chart_grammar":"..."}}
```

换主题只换参数与家族表达，不改编译 API、数据口径与发布门。`route.DIRECTION_PRESETS` 的 `theme_seed` 是起点锚点（`derive_tokens` 展开全色阶，可覆盖）；方向族种子骨架以 `design_intelligence.COLOR_DIRECTIONS` 为真源，品牌色永远优先。

---

## Evidence（证据 → 原则 → 动作 → 边界）

引用协议：观察行为 → 提炼原则 → 写成动作 → 明确反例。每条引用补记来源/日期/强度；链失效降为 low，只作方向启发。

### Evidence Cards

| ID | 可观察行为 | 原则 | 边界 |
|---|---|---|---|
| EVD-APPLE-001 | 发布语境以单一产品/能力 + 清晰章节组织注意力 | 发布页单一 Hero、一页一结论 | 不用于数据附录/多结论页 |
| EVD-PENTA-001 | 跨媒介身份一致性（字体/比例/线条/图形语法） | 品牌转译为系统行为，不只取 logo 色板 | 一致 ≠ 每页同构图 |
| EVD-IDEO-001 | Inspiration → Ideation → Implementation + 原型迭代 | 方向冻结前理解受众场景；至少一轮渲染→批评→修正 | 以人为本 ≠ 每页放人物照 |
| EVD-MCK-001 | 叙事先行建立理解与行动 | 结论先行，标题写洞察，顺序服务行动 | 不省略来源/限定/不确定性 |
| EVD-KINFOLK-001 | 编辑化留白、摄影语境、材质节奏 | 留白 + 统一摄影语言 + 稳定版心建气质 | 编辑感 ≠ 暖色衬线随机照 |

### Craft Judgments（35 条微距蒸馏为 12 条判断）

排版：中西混排留 1/8–1/4 em 间隙；大标题 Latin 微收、CJK 不加距；眉标加正字距显精致；行高标题贴紧、正文给呼吸；一页只有一个最大字号。
构图：留白按页角色取型（仪式/舒适/密度）；图文取 1.618/1/0.618；焦点落轴；来源固定同一象限。
色彩图表：Accent 稀缺（≤5%）且与主色拉开距离；层级用明度阶梯；图表直接标注、一个强调点、零轴诚实。

全文 35 条见 `archive.md` Appendix C（备查，不进上下文）。证据只影响 Direction 与 Critic 判断，不覆盖事实、可读性与品牌规则。

### References

[1] https://www.apple.com/apple-events/ · [2] https://www.pentagram.com/brand-identity · [3] https://www.ideo.com/ · [4] https://www.mckinsey.com/ （storytelling） · [5] https://www.kinfolk.com/

---

## Taste Calibration（品味校准 · 经验增强，不是工程系统）

审美不从阈值反推里长出来，从被记录的判断里长出来。本包不做「标注 → 反推 → 改常量」的校准工程：它只会长出更多规则、更多评分维度、固定审美标准与模板化输出，最终让 AI 只会检查、不会设计。

**做法**：当使用者对某一页给出判断——「这页好 / 不好，因为……」——把判断追加为 `memory/design_dna.json` 的一条经验条目，沿用现有 schema：

| 字段 | 写什么 |
|---|---|
| `id` | 可召回的场合键（如 `song_elegance_editorial`） |
| `pattern` / `when_not_to` | 什么场合启用 / 什么场合收回 |
| `design_problem` | 这页当时面对的张力 |
| `judgment` | 一句话级别的判断（不参数化，不写成阈值） |
| `works_because` / `avoid` | 为什么成立 / 什么会毁掉它 |
| `proven` | 实测证据（可选；数字放这里，不放判断句里） |

Critic 的静态阈值只守**物理底线**（对比度、溢出、色距、Accent 面积）：底线只升不调；底线之上不存在「审美分数线」。判断由 DNA 经验 + 当次上下文完成，校准不沉积为代码，评分维度不增加。

