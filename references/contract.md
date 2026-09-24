# Contract（执行契约 · 写 elements 前查）

落地给什么值、什么会被当场抓住。判断校准 → `judgment.md`；资产链 → `assets.md`。

## 判定边界

QA 只回答「这份 PPTX 能不能交付」，只有 **PASS / BLOCK** 二态。

| 拦（error → BLOCK） | 不拦（设计判断，归你） |
|---|---|
| 编译失败 · 内容缺失 · 空 deck/空页 | 好不好看、密度高不高、颜色够不够克制 |
| 溢出（框装不下 / 超 max_lines / 禁换行超宽） | 字号选择、留白多少、字阶是否好听 |
| 越界（出画布）· 退化几何（元素不可见） | 构图是否平衡、层级是否够戏剧 |
| 重叠（有效墨迹 > 容忍）· 来源区被侵入 | 叠压是否成立（作者声明即合法手法） |
| 无效图表类型 / 空载荷 / 非有限值 / 行标签缺失 | 图表类型是否最合适（type 合规 ≠ 选得对） |
| 同指标跨页单位不一致 · release 档缺来源/单位/期间/口径 | 口径文字怎么写、放哪里 |
| 认不出的色名（渲染会静默回落）· 未消费字段 | 色相与彩度是否到位 |
| 形 / 线填充走了不被读的字段（元素不可见） | 用形状还是用线 |

**验证层不评分、不重新设计、不发明数字、不产生 warning 对话。** 非阻断信号不进对话，
只作为证据存在；发现问题时按 `fix_plan` 根因组一次改完。

## 排版的物理约束，不是模板字阶

先看判断卡的 `typography.lead / support / discipline`：谁应先被读到、基期/出处如何退后，
再定字体、字号、行距和断句。**没有 Statement/Display/Title 等固定档、放之四海的字号比、
粗体配额或指定行数。** 长文字先重写或删减，不能靠缩小到不可读来硬塞。

文本框须容纳真实文字；Guard 粗估包含折行、段距与两侧内边距，结构预览不是 Office
字体测量。终稿仍需在目标 PowerPoint 检查字体替代、换行与裁切。字号和行高取决于
阅读距离、信息长度、字体与投影条件；内容本身才是视觉权重的来源，不因满足一个数字比例
就变成好设计。

## Spec 字段速查

```python
spec = {
  "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},
  "theme":  {"colors": {…六 token…}, "fonts": {"cn": …, "latin": …}},  # 家族 ≤2
  "slides": [{"id": "s01",
              "page_intent": {"insight": "本页结论一句话", "focus": "第一落点元素 id"},
              "anchor": {"eyebrow": "…", "page_number": 2},   # ≥4 页时由 plan 发给
              "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
              "elements": [ … ]}],
}
```

`theme.colors` 六 token：`background / ink / muted / primary / secondary / accent`。
`surface / dark_surface / premium / optional` 可显式声明；不写时由六 token 派生
（`panel / hairline / series1–6 / on_*` 等衍生 token 一律自动算，别手写）。
plan 按视觉世界给出种子，作者可覆盖任意一项。**颜色只能写 #HEX 或 token 名**——写错名字会在产物里静默回落，所以必拦。

**元素信封**：`id`（页内唯一）、`type`、`x/y/width/height`（必填）、`role`。

**归一化与网格**（作者需要知道的唯一一条）：几何按 4px 机械吸附，`(x,width)` 与
`(y,height)` **成对**处理——所以「一条细线 + 骑在它上面的对象」吸附后仍然同心，
不需要手工凑偶数坐标。**厚度小于一个网格的尺寸原样保留**：`height:1` 的发丝线
就是 1px，不会被抬成 4px（此时吸附的是中心，不是上边缘）。LINE / ARROW 的
横线可用 `height:0`、竖线可用 `width:0`；归一化保留零厚度轴、只吸附该轴位置，
不会把竖线扩成斜线。两轴皆零的零长度线及其他退化形状仍由 guard 拦截。
需要完全绕开吸附时写 `snap: false`。
填充四写法：`"#RRGGBB"` · token 名 · `{type:solid,color,opacity}` ·
`{type:gradient,angle,stops≥2}` · `{type:none}`。**形状填充走 `fill`、描边走 `stroke`**。

| type | 专属字段 |
|---|---|
| `text` | `text size color align bold italic line_height max_lines wrap padding font family char_spacing uppercase opacity anchor space_before space_after` |
| `shape` | `shape`(rect/rounded_rect/ellipse/triangle/diamond/pie/line/arrow) `fill stroke stroke_width fill_role text padding text_size text_color text_bold text_wrap text_line_height text_opacity text_anchor` |
| `image` | `asset_id`（必需）`fit`(cover/contain) `crop asset_function overlay` |

**编辑级文字纪律（物理契约，不是字号模板）**：`size/width/height/padding/space_before/space_after`
按画布 px 填；`line_height` 是相对倍数；显式 `char_spacing` 以 pt 填，中文与拉丁文字均写入
原生 PPT 字距。每段之间的段前/段后间隔、折行后字距及框内边距都参与 Guard 容量计算；
不得靠 `max_lines` 把文字裁去。形状内文字**同样**读 `padding`（缺省 0），没有另一套
`text_padding` 字段。`fill: {type: none}` / 省略 `fill` = 真空心，不能让预览画成实心卡片。
PIL 是结构取证，字体字形/换行在 PowerPoint 上须另行校验；过载先删句改写，不压行距。

`chart_kind` 白名单（括号为每页上限）：bar/horizontal_bar/comparison_bar(8) · column(8) ·
line/trend/single_trend_line(8) · area(8) · donut/pie(8) · stacked_bar(8) · ranked_bar(8) ·
waterfall(12) · matrix(12) · bubble(12) · sparkline(12) · process_flow(7) · timeline(7) ·
steps(6) · progress_bar(6) · big_number_row(5) · architecture(3) · kpi/executive_kpi/big_number
（数字展示读元素级 `value`）。数值图表齐 `source / unit / period / basis`（release 硬门）；
同 `metric` 跨页必须同单位。

**来源区**：`source_zone` 内只放 `role ∈ {source, method, metadata}` 的文字，
其他对象与之相交即 `SOURCE_COLLISION`。**跨页锚**：`role=eyebrow` 与 `role=page_number`，
位置全 deck 一致（plan 在 ≥4 页时逐页发）。

## 作者逃生口（生产实证 · 写 spec / 出图前查）

- 页级 `background`（#HEX）参与资产 QC 亮度判据：暗色沉浸页声明深底色，
  断崖判据问「图与这一页的落差」，不问与整副纸面的落差。
- 形状类图表（ranked_bar 等）主叙事色默认强调色；作者用 `primary_color` /
  `color_role` 把非高亮系列压回墨色——强调色只指一个答案，不铺面。
- `stroke` 只读色值；`{"type":"none"}` = 显式无描边（与 fill 同形写法对齐）。
- `plan --skeleton` 检测到已填稿（elements 非空）改写 `<name>.new.py`，不覆写作业稿。
- 资产指纹不含 `safe_area` / `text_color`：校准压字区不使已出图作废；
  二者仍进清单，QC 对成图复核。
- `vao.py qc --assets-manifest m.json`：离线像素体检（与 check 同判据），
  不写状态、不消耗 retry——出图迭代的最短反馈环。

## 执行模式与速度

| 模式 | 做什么 | 产物 |
|---|---|---|
| `spec` | 归一化 + 硬门，不编译 | 判定报告 |
| `draft` | 硬门 + 编译 | PPTX + 修复包 |
| `release` | draft 全部 + 出处硬门 + 结构预览证据 + Manifest | PPTX + 预览 + Manifest |

| 项 | `--speed fast`（默认） | `--speed strict` |
|---|---|---|
| 资产 QC 像素域 | 长边降采样；安全区原分辨率 | 全分辨率 |
| 编译缓存探测 | size+mtime 快探针 | 整包 SHA-256 |
| 结构预览 | 关键页取证（封面/章节/画心/密数据/收尾，默认 5 页） | 全 deck 逐页 2× 超采样 |

阻断项与阈值两档相同，但快档的多数像素统计在整数箱平均后的工作域，边界案例可能与原生
分辨率结果不同；文字安全区纹理和硬缝仍看原图。需逐页视觉取证的终稿选 `strict`；
`fast` 仅取关键页，不要写成「全页已看过」。`--deadline`（默认 120s）只会跳过可选预览，
不跳过核心正确性；一旦预览因时限跳过，必须在最终交付前明确补足人工视觉审阅。

## Failure codes

`OVERLAP` `SOURCE_COLLISION` `CHART_LABEL_COLLISION` `TEXT_OVERFLOW` `DATA_INTEGRITY_FAIL`
`CHART_TYPE_FAIL` `COMPILE_FAIL` `GUARD_FAIL` `ASSET_WORKFLOW_FAIL`
→ BLOCKED，按 `fix_plan` 根因组一次改完（组内含明细，零回读）。

## Release Manifest

`check --mode release` 生成 `source_spec_hash / validation / verification / compile_report
（含 output_sha256）/ ghost_preview / asset_workflow / status`。校验三件事：报告盖的 spec 戳与
当前一致；PPTX 字节戳与磁盘一致（一次哈希比对）；预览证据引用的页面都在当前 spec 内。
`release_eligible` 仅在 release 档、编译通过且凭证全有效时为真。
