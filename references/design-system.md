# Design System（执行默认值 · 写 elements 前查）

本卷只回答两件事：**落地给什么值**（Spec 字段速查），以及**首轮就该设对、否则必然返工**的量。
判断往哪走在 `design-intelligence.md`，品味与案例在 `design-craft.md`，运行时门槛在
`production-contract.md`。这里没有版式库——能用固定阈值描述的东西住在代码里。

## 执行默认值

### Canvas

1280×720、16:9、12 列逻辑网格 + 8 单位基线。每页声明 `page_intent` 的
`insight / focus / page_family / density / energy`。黄金比例/三分/对称只是候选工具。
System 不要求相邻页必须变化；Intelligence 决定要变化之后，System 只负责稳定实现。

### Hierarchy

跨页连续只靠三锚：章标/眉标固定上缘、页码固定象限、来源区固定位置——锚不动，正文才可游走；
`evidence_field` 下标题、图表与来源共栏宽、共左缘。
五层：背景 → 环境/媒体 → 结构/标题 → 内容/数据 → 焦点；焦点层原则上只有一个元素。
标题写洞察，眉标只做弱导航；空间不够时减词、减类、拆页——压缩字号是最贵的退路。

### 字号阶梯（全库唯一真源）

分工：Intelligence 回答「是不是视觉主语」，本表回答「落哪一档」。相邻级差 ≥1.25×；
每页 ≤4 级、全 deck ≤6 级；取值优先落驻点。

| 级 | 驻点 | 区间 | 角色 |
|---|---|---|---|
| L4 Statement | 64 | 40–80 | 宣言、封面主张、KPI 主数字 |
| L3 Display | 44 | 40–56 | 页面主标题、Hero 结论 |
| L2 Title | 32 | 28–36 | 小节标题、图表标题 |
| L1 Lead | 22 | 20–24 | 导语、图表直接标注 |
| L0 Body | 17 | 16–20 | 正文 |
| L-1 Caption | 12.5 | 11–14 | 来源、注释、图例 |

行高：L4/L3 取 1.05–1.15，L2 取 1.15–1.25，L1/L0 取 1.3–1.5（中文取上限），Caption 1.2–1.3。
层级优先用字重/墨色表达，再动字号。中文：避头尾、全角标点、中西混排留 1/8–1/4 em、
禁两端对齐拉字距。

### Color

颜色同时承担 brand/emotion/hierarchy，`color_intent` 声明当前优先者。Accent 稀缺才有
强调（≤5%）；层级优先用同色相明度阶梯。黑底/金色/渐变本身不构成品质；饱和人格是内容
判断（见 intelligence §04），选定后纪律不变：色相族克制、强调稀缺、对比可读。
中性色带冷暖（暖纸面 + 冷灰轨道），忌纯灰；渐变是留白手法——同族低对比，互补等彩度
对撞会混出脏灰。Accent 的合法职责只有**指认**：指认答案、指认当前、指认印章、指认主题
（一次性语义标记）；不承担指认的 accent 即装饰。

### Background

按需组装 `Base → Image → Atmosphere/Light → Content Protection`，默认只开最少层。
答不出「场景 / 焦点 / 文字安全区」就回退 `solid_world`。保护层只保可读，不把图片盖死。

### Image

图须声明 `asset_role`（background 建立空间 / illustration 表达对象 / hybrid）与
`asset_function`（hero/proof/emotion/context/frame/separate）两轴，再声明主体/构图/
留白锚点/裁切/溯源。相关性 > 构图 > 光线 > 材质 > 风格。图不烘焙文字/Logo/水印/数据；
主体侵入文本区或改写重心时回退、重裁或换图。两侧职责一致：生成侧按 role 出图，编排侧
按 role 落位——有文字压图的全幅/半幅图 → `layer: background` + `overlay`（享背景层免检）；
立在栏内旁边配文的图 → 插图（必须让开元素与来源区）。把插图当背景纹理铺底压字＝角色说错。
交付编码：照片用 JPEG q92 4:4:4（视觉无损），不用 PNG——PNG 存照片多出的比特只买来等待；
只有图形/纯色/透明通道才用 PNG。落位按 2× 交付。

### Grouping（默认分组成本）

场（48px+ 间距即边界）> 线（0.75–1px 发丝线）> 型（字号/字重/墨色层级）> 盒（卡片：
同时花掉间距/描边/底色三重预算）。这是默认成本顺序，不是永远优先级——复杂数据页、
产品界面结构、财务表格里盒子可能就是正确语义容器。卡片三准入：需物理容器语义
（数据模块/KPI）、需与复杂背景隔离、需被指认为独立对象；三条都不成立退回场/线/型。

### Charts

准确 > 清晰 > 美观 > 装饰。类型路由的判断在 Intelligence/Craft（Chart = Visual Argument），
本段只给候选表达 + 工程安全边界：趋势常用折线、比较常用条形、构成 ≤5 类、桥接常用瀑布；
一图一关系；单位/期间/口径/来源齐备；直接标注优先于图例；一个强调点、三种语义色、
八个类别封顶。可读表达（环心 KPI / sparkline / 瀑布小计 / 目标线 / 末端标注）不新增数据
通道。精确值归表、形状归图：两者都要时表图并置，不用数据标签把图堆成表；图不能被一句
话领走时，图下加 Insight 行兜底——但先自问图是否画错了。`highlight` 写索引或类别名都认。

### Motion

全套 ≤2 种姿态，默认 `still`；动效只在改变阅读顺序/空间建立/数据理解时启用。
静态交付下内容层级独立成立。

### Anti-patterns（症状，不是禁令）

卡片墙 / 平均九宫格 / 过度阴影 / 图标堆砌 / 随机图库 / 竞争性高亮 / 伪 3D / 背景压字 /
为填空加细节。看到症状先问「哪个判断缺席了」，再沿唯一减法链修：
**删除 > 重组 > 排版 > 强化 > 装饰**（完整症状表见 `design-craft.md` §一）。

---

## 方向（方向不是模板）

- `route.DIRECTION_PRESETS` 4 个**结构预设**：`quiet_minimal / editorial_brand /
  product_stage / evidence_first`；`design_intelligence_rules.COLOR_DIRECTIONS` 13 个
  **色彩方向族**：`quiet_luxury / luxury_editorial / song_elegance / zen_minimal /
  nordic_quiet / monochrome_noir / cinematic_narrative / nature_luxury / organic_systems /
  precision_tech / precision_minimal / data_intelligence / editorial_intelligence`。
  两类名字都能写进 `design_direction`；族名带来自己的材质/动势/纹理语言与种子色板
  （结构骨架仍取预设；`texture` 以键名传下去由 `asset_prompt` 展开）。两类都不在表里
  回落 `quiet_minimal` 并留痕。种子可整体推翻，品牌色永远优先。
- 介质（水墨/摄影/插画）由**每张资产自己的 `medium`** 决定，不是方向：方向里的
  `material` 与 `visual_world` 说的是整副 deck 用什么质感说话。划错了，摄影页会被灌进
  水墨工艺纪律，与自己的 photography medium 自相矛盾。
- 换方向只换参数与家族表达，不改编译 API、数据口径与发布门。

## 首轮设对（会被代码当场抓住的量，返工最贵）

| 量 | 一次设对 | 谁抓你 |
|---|---|---|
| 强调色可辨 | Accent 与主/辅色色相差 ≥12°；暖纸+暖炭+金挤同族＝强调失效（主色改冷石墨或 accent 换异相）。写进 `theme.constraints.accent_hue_min` 才被执法 | `palette_discipline` |
| 强调色不载文字 | 低饱和金在象牙底约 2.7:1；金只做发丝线/方点/高亮端点/目标线 | `contrast` |
| muted 可读 | 按 WCAG AA：浅底象牙 `#F6F5F1` → `#6E6A5F`（4.8:1）；深底深林绿 `#2E3B33` → `#A9B4AA`（5.5:1）。`chart_muted` 指到哪个 token 刻度就用哪个 | `contrast` |
| 背景图 vs 插图 | 生成侧声明 `asset_role`；编排侧：压图全幅/半幅 → `layer: background` + `overlay`，栏内配图 → 插图让开元素与来源区。3:2 照片左半是平墙时改竖构图/填满画幅/出血做背景 | `SOURCE_COLLISION` / `BG_*` |
| 整幅背景图可读 | 二选一：① `layer:background` + `overlay`（opacity ≥0.20）+ 覆盖 ≥60%（享免检）；② 形状全幅渐变罩必须烘焙进画心（形状无豁免，与 `source_zone` 相交即 `SOURCE_COLLISION`）。分幅画心不需要罩 | `BG_*` / `SOURCE_COLLISION` |
| 发丝线对不上中心 | 位置吸附、尺寸不吸附（≤2px 豁免）：水平细线光心恒在 8k+0.75，8px 方块在 8k+4，二者不可能对中；组合标记按单元素设计，靠长度变奏承担页型 | `grid_snap` + `alignment` |
| 焦点不突出 | 焦点获得明确视觉优先级（图像/留白/孤立小数字/结构关系都可以）；落在文字上该拿页内最大字号；页眉大字/超大页码/巨型图表标签会偷走焦点 | 设计判断 |
| 字号落到驻点 | 只落 64/44/32/22/17/12.5；「差一点」的值让字阶从 4 涨到 6，层级失焦 | 设计判断 |

## Spec 字段速查（写 elements 前查）

`theme` 真正被读的键只有四个——多写的键无声忽略：

```python
theme = {"colors": {"background","surface","primary","secondary","ink","muted","accent","negative",
                    "premium","optional"},   # premium/optional：多序列图表的二级信号色（缺省回落 accent）
        "fonts": {"cn","latin"},          # display/body 是等价别名
        "constraints": {"whitespace_min": 0.55},   # 只写你真的要承诺的数字
        "chart_palette": {"primary","secondary","neutral","accent","negative"}}
```

未声明色 token 由 `primitives.derive_tokens` 从 base 色一次展开。`constraints` 是作者写下
的数字承诺（包不替作者发明审美数字），写进 spec 才被执法：

| 键 | 量的东西 |
|---|---|
| `whitespace_min` | deck 留白率下限（元素框并集之外占比） |
| `type_step_min` | 相邻字号级差下限 |
| `bg_layers_max` | 背景层数（≥60% 页面积的非文字元素） |
| `bold_ratio_max` | 显式加粗文本元素占比 |
| `max_charts` / `max_colors` | 每页图表数 / 颜色角色数上限 |
| `hue_families_max` | 全套色相族上限（30° 一档） |
| `accent_hue_min` | Accent 与主/辅色最小色相角 |
| `chart_label_scale_tol` | 同类图表跨页标签字号最大倍数 |

写错键名不报错但被 `theme_constraint` 点名。**未声明一律不检查**——底线之上交给设计判断。
字体键只有 `cn` / `latin` 被读；都不写会回落 Arial / Microsoft YaHei，`theme_fonts` 点名。

**元素信封**：`id`（页内唯一）、`type`、`x/y/width/height`（数值，落 8 网格；任一维 ≤2px
或通栏豁免）、`role`。填充四写法：`"#RRGGBB"` · theme token · `{type:solid,color,opacity}` ·
`{type:gradient,angle,stops×≥2}` · `{type:none}`（angle 0=左→右、90=上→下）。
**形状填充走 `fill`、描边走 `stroke`**——顶层 `color`/`line` 在形状上不生效。

| type | 专属字段 |
|---|---|
| `text` | `text size color align bold italic line_height max_lines wrap padding font family char_spacing uppercase opacity anchor space_before space_after fill` |
| `shape` | `shape`(rect/rounded_rect/ellipse/triangle/diamond/pie/line/arrow) `fill stroke stroke_width stroke_opacity fill_opacity fill_role text` |
| ↳ 线 | 一维对象：width/height 是向量分量。水平发丝线 `{"shape":"line","x":96,"y":300,"width":1088,"height":0,"stroke":"hairline","stroke_width":1}`；垂直分栏线 width=0。颜色走 `stroke`，粗细走 `stroke_width`；两轴同时 0 才是错 |
| `image` | `asset_id`（必需，清单绑定 src）`fit`(cover/contain) `crop asset_function overlay content_protection negative readability_exempt` |

`chart_kind` 全表（括号为每页上限）：原生 bar/horizontal_bar/comparison_bar(8) · column(8) ·
line/trend/single_trend_line(8) · area(8) · donut/donut_composition/pie(8)；形状
process_flow(7) · timeline(7) · steps(6) · matrix(12) · waterfall(12) · architecture(3) ·
bubble(12) · ranked_bar(8) · progress_bar(6) · stacked_bar(8) · big_number_row(5) ·
sparkline(12)。未知 kind 在 Guard 阻断；**缺载荷**同样阻断（空 data、matrix 无 points、
architecture 无 layers、数字展示无 value）——空白页不会出门。

**数字展示**（kpi/executive_kpi/big_number）不读 data，只读元素级 `value`（必填）
`label value_size label_size align`。v7.1.0 起主色经 `chart_primary_color` 单源解析：
color_role > 逃生口 > 扁平键 > `chart_palette.primary` > accent——预览与产物同一条链。

图表字段五组——**数据**：`data:[{label,value,display}]`，多序列 `series+categories`。
**出处**（数值图必填）：`source unit period basis data_status`，可嵌套 `provenance`；跨页同
metric 单位与期间一致。**配色**：`color_role/secondary_role` ∈ primary/secondary/neutral/
accent/negative，逃生口 `*_color`。**强调**：`highlight`（索引或类别名）`target+target_label`
`show_values` `label_collision_policy`。**差异可见**：零基长度编码里标了重点又几乎等长
（max/min <1.25×）＝「差多少」看不见，`chart_argument` 点名——改 waterfall/big_number 直接
写差值，或索引化后放共同基线比长度。**版式**：`label_size value_size label_ratio label_gap
value_width value_gap bar_height gap_width`；环形 `hole_size/center_value/center_label`；折线
`smooth/end_labels/number_format`；`big_number_row/stacked_bar` 另有 `items legend ramp
multi_color max`。

`role` 决定注释类最小字号与能否进来源区。常用：`title lead body caption annotation label
metadata source method axis data_label legend decoration eyebrow page_number`。

**跨页锚**：plan 给每页发 `anchor`（≥4 页成套 deck 才有）：眉标 `role=eyebrow` 用 plan
家族词汇原文、固定上缘；页码 `role=page_number` 固定象限、封面不编号；证据编号
（Fig.01…）不用——演示无回指，编号只会挤掉来源行里真正该写的口径。
`guard.deck_anchor` 只查：声明了有没有落、编号连不连续（位置恒定是设计判断，
由统一契约承担，引擎不逐页执法）。
**来源区内只放 source/method/metadata**；其他角色对象与 `source_zone` 相交即
`SOURCE_COLLISION`（形状同样算；合格背景画心除外）。

---

## 经验记忆（判断的沉淀，不是参数表）

DNA 记录**决策经验**，不是设计结果：记「内容只有一个战略结论且需建立权威时，扩大
statement 与留白的比例比增加装饰更有效」（可迁移判断），不记「64px+米色+左对齐」
（结果，攒多了就是模板库）。入口唯一：`python scripts/vao.py dna --add entry.json`
（`--check` 体检）。字段：`id`（可召回场合键）、`signature.keywords`（召回只按它打分）、
`pattern/when_not_to`、`design_problem`、`judgment`（只写行为判断，维度限 hierarchy/space/
media/color_behavior/charts/anchor_rule/structure/type_voice）、`works_because/avoid`、
`proven`（实测证据，数字放这里）。`judgment` 里出现色值/字体/版式结果会被拒收；库损坏
拒绝写入。写坏的记忆比不写更贵——它不报错，只会被静默误用。新增 DNA 前，先判断
是否可以增强已有 DNA（`--replace` 加固 `proven`）；只有形成新的、跨项目可复用的
设计判断时才新增。

不做「标注 → 反推 → 改常量」的校准工程。guard/QA 阈值只守物理底线（对比度/溢出/色距/
accent 面积）：底线只升不调，底线之上不存在「审美分数线」。

### 出图前的页面契约

brief slide 先明确 `asset_role` / `asset_function`，再明确 `asset_subject` / `medium` /
`asset_ratio` / `negative_space_anchor` / `safe_area`，然后 plan → assets。角色是生成侧声明，
落位是编排侧判断；两者都写对，才不会「按插图出图、当背景使用」。比例/留白/文字明暗改变
时不复用旧提示词缓存。图片通过 QC 后才填入 elements；这一步只决定图片如何服务页面，
不强迫各页同一构图。

v5.1.1 图片有效性：短边 ≥32px，落位 ≥1× 有效像素；不得完全透明。计划比例默认校验，
有意裁切声明 `asset_allow_crop: true`。文字检查覆盖 shape 内 text_size/wrap/line_height，
并核对不换行文本的横向容量。
