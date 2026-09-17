# Design System（执行默认值 · 写 elements 前查）

这份文件只回答两件事：**落地时给什么值**（Spec 字段速查），以及**首轮就该设对、否则必然返工**的几条量。
判断往哪走在 `design-intelligence.md`，品味与案例在 `design-craft.md`，运行时契约在 `production-contract.md`。
这里没有主题目录、没有版式库、没有照抄即成立的公式——能用一个固定阈值描述的东西住在代码里，不在这里。

判断顺序：语义与事实 → 一页一焦点 → 可读性 → 空间与重心 → 分组与对齐 → 跨页连续 → 图表降噪 → 装饰与动效。
下层手法不修上层问题。

## 执行默认值

### Canvas

1280×720、16:9、12 列逻辑网格 + 8 单位基线。每页声明 `page_intent` 的
`insight / focus / page_family / density / energy / empty_space_role`（可选 `reading_order`）。
黄金比例/三分/对称只是候选工具：内容关系说不通就放弃。
相邻两页换密度、重心或版式其一；全套走建立 → 聚焦 → 展开 → 证据 → 收束的空间曲线。

### Hierarchy

跨页连续只靠三个锚：章标/眉标固定上缘、页码固定象限、来源区固定位置——锚不动，正文才可游走；
`evidence_field` 构图语法下，标题、图表与来源共栏宽、共左缘。

五层：背景 → 环境/媒体 → 结构/标题 → 内容/数据 → 焦点；焦点层原则上只有一个元素。
字号阶梯见 `design-intelligence.md`（全库唯一真源，不要在别处另立一套）。
标题写洞察，眉标只做弱导航；空间不够时减词、减类、拆页——压缩字号是最贵的退路。

### Color

颜色同时承担 brand/emotion/hierarchy，`color_intent` 声明当前优先者。Accent 稀缺才有强调（≤5%）；
层级优先用同色相明度阶梯。黑底/金色/渐变本身不构成品质。

中性色带冷暖（暖纸面 + 冷灰轨道），忌纯灰；渐变是留白手法——同族低对比，互补等彩度对撞会混出脏灰。

Accent 的合法职责只有**指认**：指认答案（对比/推荐项）、指认当前（流程节点/最新值）、
指认印章（东方语义标记）、指认主题（色彩即内容主题本身时的一次性语义标记，如黑金策略封面金标题
——一次有效，重复即装饰）。不承担指认的 accent 即装饰。

### Background

按需组装 `Base → Image → Atmosphere/Light → Content Protection`，默认只开最少层。
答不出「场景 / 焦点 / 文字安全区」就回退 `solid_world`。保护层只保可读，不把图片盖死。

### Image

图须声明功能（context/emotion/proof/hero）+ 主体 / 构图 / 留白锚点 / 裁切 / 溯源。
相关性 > 构图 > 光线 > 材质 > 风格。图不烘焙文字/Logo/水印/数据；主体侵入文本区或改写重心时
回退、重裁或换图。

交付编码：照片类资产用 JPEG q92 4:4:4（视觉无损），不用 PNG——同一份 12 页稿实测由 2.23 MB 降到
1.78 MB，且 PNG 存照片多出的比特只买来等待；只有图形、纯色、需要透明通道时才用 PNG。落位按 2× 交付。

### Grouping（分组四语言，由强到弱）

场（48px+ 间距即边界）> 线（0.75–1px 发丝线）> 型（字号/字重/墨色层级）> 盒（卡片：同时花掉
间距/描边/底色三重预算）。卡片三准入：需物理容器语义（数据模块/KPI）、需与复杂背景隔离、
需被指认为独立对象；否则退回场/线/型。

### Charts

准确 > 清晰 > 美观 > 装饰。趋势折线、比较条形、构成 ≤5 类、桥接瀑布。一图一关系；
单位/期间/口径/来源齐备；直接标注优先于图例；一个强调点、三种语义色、八个类别封顶。
可读表达（环心 KPI / sparkline / 瀑布小计 / 目标线 / 末端标注）不新增数据通道。
精确值归表、形状归图：两者都要时表图并置，不用数据标签把图堆成表；
图不能被一句话领走时，图下加 Insight 行兜底——但先自问图是否画错了。
`highlight` 写索引或**类别名**都认（写「海外」比写「1」更接近判断本身）。

### Motion

全套 ≤2 种姿态，默认 `still`；动效只在改变阅读顺序/空间建立/数据理解时启用。
静态交付下内容层级独立成立。

### Anti-patterns（症状，不是禁令）

卡片墙 / 平均九宫格 / 过度阴影 / 图标堆砌 / 随机图库 / 竞争性高亮 / 伪 3D / 背景压字 / 为填空加细节。
看到症状先问「哪个判断缺席了」，再按「删 → 简化 → 恢复空间 → 重构重心 → 换媒体 → 微调装饰」修。

---

## 方向（方向不是模板）

- 方向必须能回答三问：**什么材质 / 光从哪来、什么性格 / 元素并列还是层叠纵深**。
  内容不需要隐喻时，`solid_world` + 编辑版心就是正确答案——诚实比意象重要。
- 派生顺序：品牌色 > 材质与光性判断 > 方向种子（兜底）；图表色走语义角色，不写死色值。
- 代码里的种子只是起点，不是待抄的版式，但**名字要对得上**（brief 里写 `design_direction` 时）
  ——`route.DIRECTION_PRESETS` 有 4 个方向：`quiet_minimal / editorial_brand / product_stage /
  evidence_first`（各带 material/light/chart/motion/background 与 seed 色板字体）；
  `design_intelligence_rules.COLOR_DIRECTIONS` 有 13 个色彩方向族：`quiet_luxury / luxury_editorial /
  song_elegance / zen_minimal / nordic_quiet / monochrome_noir / cinematic_narrative / nature_luxury /
  organic_systems / precision_tech / precision_minimal / data_intelligence / editorial_intelligence`
  （给 regime/sat/motion 约束）。名字不在表里会回落到 `quiet_minimal` 并在 plan 里留痕。
  种子可整体推翻，品牌色永远优先。
- 换方向只换参数与家族表达，不改编译 API、数据口径与发布门。
- 一次只混一个维度（借排版人格，或借留白纪律）；说不清混的是什么就退回单方向。

## 首轮设对（会被代码当场抓到的量，返工最贵）

| 量 | 一次设对 | 谁抓你 |
|---|---|---|
| 强调色可辨 | Accent 与主/辅色**色相差 ≥12°**；暖纸 + 暖炭 + 金挤在同一色相族＝强调失效（出路：主色改冷石墨，或 accent 换异相色） | `accent_hue_min`（advisory） |
| 强调色不载文字 | 低饱和金在象牙底上约 2.7:1；金只做发丝线/方点/高亮端点/目标线 | `contrast`（元素里真拿 accent 写字才会被点名） |
| muted 可读 | 按 WCAG AA 取：浅底象牙 `#F6F5F1` → `#6E6A5F`（4.8:1）；深底深林绿 `#2E3B33` → `#A9B4AA`（5.5:1）。3.2:1 的「高级浅灰」投影上不可读；`chart_muted` 指到哪个 token，刻度就用哪个——别指到深面/浅面上 | `contrast`（<3:1 提示 / <1.8:1 警示） |
| 整幅背景图可读 | 二选一：① `layer:background` + `overlay`（opacity ≥0.20）+ 覆盖 ≥60%（享免检）；② 用**形状**做全幅渐变罩则必须烘焙进画心——形状无豁免，与 `source_zone` 相交即 `SOURCE_COLLISION`。分幅画心（图只占一栏）不需要罩 | `BG_*` / `SOURCE_COLLISION` |
| 发丝线对不上中心 | 位置吸附、尺寸不吸附（任一维 ≤2px 豁免）：水平细线光心恒在 `8k+0.75`，8px 方块在 `8k+4`，**二者不可能对中**。组合标记按单元素设计，靠长度变奏承担页型 | `grid_snap` + `alignment` |
| 焦点抢戏 | `page_intent.focus` 指向的元素若是文字，必须是**页内最大字号**（设计上再留 ≥1.25× 领先余量，见 `primitives.FOCUS_LEAD`）。页眉大字、超大页码、巨型图表标签都会把焦点偷走 | `focus_scale`（hint） |
| 字号落到驻点 | 只落 `64 / 44 / 32 / 22 / 17 / 12.5`；写 14、11.5 这类「差一点」的值，会让一页字阶从 4 涨到 6，层级失焦 | `type_budget`（hint）+ 阶梯归并 |

---

## Spec 字段速查（写 elements 前查）

`theme` 真正被读的键只有这四个——多写的键不会报错，只是**无声忽略**（写了等于没写）：

```python
theme = {"colors": {"background","surface","primary","secondary","ink","muted","accent","negative"},
        "fonts": {"cn","latin"},          # 规范键；display/body 是等价别名（骨架旧写法）
        "constraints": {"accent_max": 0.05, "whitespace_min": 0.62,   # 方向种子：见下
                        "type_step_min": 1.25, "decoration_area_max": 0.06,
                        "bg_layers_max": 1, "bold_ratio_max": 0.50},
        "chart_palette": {"primary","secondary","neutral","accent","negative"}}
```

未声明的色 token（panel / hairline / ramp1–5 / series1–6 / track / veil…）由 `primitives.derive_tokens`
从 base 色一次性展开；`constraints` 不做审美裁决，只做「说过的数字」的执法。

**`constraints` 是方向的数字部分**（plan 的 `theme.constraints` 原样落到 spec，骨架会照抄）：

| 键 | 量的东西 | 越界后果 |
|---|---|---|
| `accent_max` | 每页强调色面积 | 强调色铺开＝没有重点 |
| `whitespace_min` | deck 留白率下限（**元素框并集之外**的占比） | 页面被填满，读不出层次 |
| `type_step_min` | 相邻字号级差下限 | 级差太小读成「没对齐」 |
| `decoration_area_max` | 装饰面积上限 | 装饰抢走主焦点 |
| `bg_layers_max` | 背景层数（≥60% 页面积的非文字元素） | 层叠过多，前景浮不起来 |
| `bold_ratio_max` | 显式加粗的文本元素占比 | 全都加粗＝都没加粗 |

写错键名不会报错但**会被 `theme_constraints` 点名**（写了等于没写）。未声明的键不检查——
手写 spec 不会被方向默认值吵到。

**字体键只有 `cn` / `latin` 会被读**（`display` / `body` 认作别名）；两个都不写或写成别的名字，
产物会回落 Arial / Microsoft YaHei——字体判断在产物里彻底消失，`theme_fonts` 会点名它。

**元素信封**：`id`（页内唯一）、`type`、`x`/`y`/`width`/`height`（数值，落 8 网格；任一维 ≤2px 或通栏豁免）、
`role`。填充四种写法：`"#RRGGBB"` · theme token 名 · `{"type":"solid","color":…,"opacity":0–1}` ·
`{"type":"gradient","angle":0,"stops":[{…}×≥2]}` · `{"type":"none"}`；`angle` 0=左→右、90=上→下。
**形状的填充走 `fill`、描边走 `stroke`**——顶层 `color`/`line` 在形状上不生效（元素看起来没渲染）。

| type | 专属字段 |
|---|---|
| `text` | `text` `size` `color` `align` `bold` `italic` `line_height` `max_lines` `wrap` `padding` `font` `family` `char_spacing` `uppercase` `opacity` `anchor` `space_before` `space_after` `fill` |
| `shape` | `shape`(rect/rounded_rect/ellipse/triangle/diamond/pie/line/arrow) `fill` `stroke` `stroke_width` `stroke_opacity` `fill_opacity` `fill_role` `text` |
| `image` | `src` `fit`(cover/contain) `crop` `asset_function`(hero/emotion/proof/context) `overlay` `content_protection` `negative` `readability_exempt` |

`chart_kind` 全表（括号为每页上限）：原生 bar/horizontal_bar/comparison_bar(8) · column(8) ·
line/trend/single_trend_line(8) · area(8) · donut/donut_composition/pie(8)；形状 process_flow(7) ·
timeline(7) · steps(6) · matrix(12) · waterfall(12) · architecture(3) · bubble(12) · ranked_bar(8) ·
progress_bar(6) · stacked_bar(8) · big_number_row(5) · sparkline(12)。未知 kind 在 Guard 阻断；
**缺载荷**同样阻断（空 `data`、matrix 无 `points`、architecture 无 `layers`、数字展示无 `value`）
——空白页不会出门。

**数字展示**（`kpi` / `executive_kpi` / `big_number`）不读 `data`，只读元素级
`value`（必填）`label`（建议填）`value_size` `label_size` `align`。

图表字段五组——**数据**：`data:[{label,value,display}]`，多序列用 `series:[{name,values}]+categories:[…]`。
**出处**（数值图必填）：`source` `unit` `period` `basis` `data_status`，可嵌套进 `provenance:{…}`；
跨页同 `metric`（缺省用 `series_name`）单位与期间一致。**配色**：`color_role`/`secondary_role` ∈
primary/secondary/neutral/accent/negative，逃生口 `primary_color`/`secondary_color`/`ink_color`/`muted_color`。
**强调**：`highlight`（索引或类别名/序列名）`target`+`target_label` `show_values`
`label_collision_policy`(hide_redundant/move_outside/fail)。**差异可见**：零基长度编码
（bar/column/horizontal_bar/comparison_bar/ranked_bar）里标了重点、两者又几乎等长（max/min <1.25×）
＝这页的「差多少」观众看不见，`chart_argument` 会点名——改 waterfall / big_number 直接写差值，
或索引化后放在共同基线上比长度。**版式**：`label_size` `value_size`
`label_ratio` `label_gap` `value_width` `value_gap` `bar_height` `gap_width`；环形另有
`hole_size`(默认 62) `center_value` `center_label`；折线另有 `smooth` `end_labels` `number_format`；
`big_number_row`/`stacked_bar` 另有 `items` `legend` `ramp` `multi_color` `max`。

`role` 决定三件事——行长豁免、注释类最小字号、能否进来源区。常用值：`title` `lead` `body` `caption`
`annotation` `label` `metadata` `source` `method` `axis` `data_label` `legend` `decoration`
`eyebrow`（眉标）`page_number`（页码）。

**跨页锚**：plan 给每页发一个 `anchor`（≥4 页的成套 deck 才有），生成侧把它落成元素：

```python
"anchor": {"eyebrow": "DATA STORY", "page_number": 4, "figure": "Fig. 02"}
```

- 眉标：`role="eyebrow"`，用 plan 的家族词汇原文，**固定上缘**（全 deck 同一个 y）；
- 页码：`role="page_number"`，**固定象限**（同一个 x/y），封面不编号；
- 证据编号：写进该页 `caption` 开头（`Fig. 01/02…`），**按页序连续**；只有证据类页（数据/对比/案例/时间线）有。

`guard.deck_anchor` 只查三件事：声明了有没有落、位置是不是同一个、编号连不连续。
**来源区内只放 `source`/`method`/`metadata`**；其他角色的对象只要与 `source_zone` 相交即
`SOURCE_COLLISION`（形状同样算；合格背景画心除外）。

---

## 经验记忆（判断的沉淀，不是参数表）

审美不从阈值反推里长出来，从被记录的判断里长出来。当使用者对某一页给出判断——「这页好 / 不好，
因为……」——把判断写成一条经验，用 `python scripts/vao.py dna --add entry.json` 入库（`--check` 体检）：
`id`（可召回的场合键）、`signature.keywords`（召回只按它打分，空 = 永远命不中）、
`pattern` / `when_not_to`（什么场合启用 / 收回）、`design_problem`（当时的张力）、
`judgment`（只写行为判断，维度限 `hierarchy/space/media/color_behavior/charts/anchor_rule/structure/type_voice`）、
`works_because` / `avoid`、`proven`（实测证据，数字放这里）。

写坏的记忆比不写更贵：它不报错，只会被静默忽略或误用。所以写入口只有这一个——`judgment` 里出现
色值/字体/版式结果会被拒收（那些属于 `proven.measurements`），库文件损坏时拒绝写入。

不做「标注 → 反推 → 改常量」的校准工程：那只会长出更多规则、更多评分维度与模板化输出。
guard/QA 的阈值只守**物理底线**（对比度、溢出、色距、accent 面积）：底线只升不调，
底线之上不存在「审美分数线」。
