# Contract（执行契约 · 写 elements 前查）

落地给什么值、什么会被当场抓住。判断基准 → `../SKILL.md`；资产链 → `assets.md`。

## 判定边界

QA 只回答自动化硬约束与凭证是否通过，只有 **PASS / BLOCK** 二态，不签署视觉终验。

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

## 文本测量边界

Guard 粗估字号、折行、字距、段距及内边距；不是目标字体的真实排版。plan 的
`typography.scale` 是启发式建议，不是适用于所有投影距离的物理定律或通过阈值。
排版判断只按 SKILL.md；实际字体、回退、禁则、裁切与可读性须另行渲染核验。

中文禁则回退目前只在 ghost 的折行模型中执行；编译器写入原生文本，实际折行由目标
PowerPoint 与字体决定，**两者不共享断行实现**。ghost 的违例可以提示人工复核，
不能推断 Office 必然有同样违例；ghost 没有违例也不能证明 PPTX 正确。证据分层以
`SKILL.md §6` 为准。

## Spec 字段速查

```python
spec = {
  "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},
  "theme":  {"colors": {…六 token…}, "fonts": {"cn": …, "latin": …}},  # 家族 ≤2
  "slides": [{"id": "s01",
              "anchor": {"eyebrow": "…", "page_number": 2},   # ≥4 页时由 plan 发给
              "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
              "elements": [ … ]}],
}
```

`theme.colors` 六 token：`background / ink / muted / primary / secondary / accent`。
`surface / dark_surface / premium / optional` 可显式声明；不写时由六 token 派生
（`panel / hairline / series1–6 / on_* / negative` 等衍生 token 一律自动算，别手写）。
`negative` 是图表里 <0 那一段的语义色（损失 / 风险），按主题机械派生；这一套世界
有自己的风险色相时再显式声明 `colors.negative` 或 `chart_palette.negative` 覆盖它。
plan 按视觉世界给出种子，作者可覆盖任意一项。**颜色只能写 #HEX 或 token 名**——写错名字会在产物里静默回落，所以必拦。

页面 `id` 全稿唯一；取证顺序跟随 `slides`，不按 ID 字典序重排。

**元素信封**：`id`（非空、页内唯一）、`type`、`x/y/width/height`（必填）、`role`。

**归一化与网格**（作者需要知道的唯一一条）：几何按 4px 机械吸附，`(x,width)` 与
`(y,height)` **成对**处理——所以「一条细线 + 骑在它上面的对象」吸附后仍然同心，
不需要手工凑偶数坐标。**厚度小于一个网格的尺寸原样保留**：`height:1` 的发丝线
就是 1px，不会被抬成 4px（此时吸附的是中心，不是上边缘）。LINE / ARROW 的
横线可用 `height:0`、竖线可用 `width:0`；归一化保留零厚度轴、只吸附该轴位置，
不会把竖线扩成斜线。`arrow` 从 `(x,y)` 指向 `(x+width,y+height)`，
在原生连接线的终点写入三角箭头；`line` 不带箭头。两轴皆零的零长度线及其他退化形状仍由 guard 拦截。
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
原生 PPT 字距。`theme.fonts.cn`（别名 `body`）决定中文字体，`latin`（别名 `display`）
决定拉丁字体；现有 `font` token 与 `family` 元素字段只覆盖拉丁字体，不覆盖中文。
ghost 文本框、形状内文字及本轮覆盖的原生图表标签复用同一角色解析，但仍用近似字面，
并非目标字体的忠实测量；其他形状化图表文字路径不在本轮覆盖范围。
每段之间的段前/段后间隔、折行后字距及框内边距都参与 Guard 容量计算；
不得靠 `max_lines` 把文字裁去。形状内文字**同样**读 `padding`（缺省 0），没有另一套
`text_padding` 字段。`fill: {type: none}` / 省略 `fill` = 真空心，不能让预览画成实心卡片。
PIL 是结构取证，字体字形/换行在 PowerPoint 上须另行校验；过载先删句改写，不压行距。

`chart_kind` 支持项（括号为历史建议数量；仅下述截断型硬限额由 Guard 执行）：bar/horizontal_bar/comparison_bar(8) · column(8) ·
line/trend/single_trend_line(8) · area(8) · donut/pie(8) · stacked_bar(8) · ranked_bar(8) ·
waterfall(12) · matrix(12) · bubble(12) · sparkline(12) · process_flow(7) · timeline(7) ·
steps(6) · progress_bar(6) · big_number_row(5) · architecture(3) · kpi/executive_kpi/big_number
（数字展示读元素级 `value`）。数值图表齐 `source / unit / period / basis`（release 硬门）；
同 `metric` 跨页必须同单位。原生数值图表的 `show_values`、`number_format`、
`label_collision_policy` 不因 `data` 或 `categories + series` 载荷改变；多序列的
容量计数为类别数 × 序列数。`label_size` 控制原生轴标签、`value_size` 控制数值标签，
均为画布 px（写入 PPTX 时乘 0.75 转 pt），中文字体来自 `theme.fonts.cn/body`。
多序列 `name` 必须非空且唯一，类别名非空；原生图表以底部非覆盖图例标识序列，
图例复用 `label_size` 和字体角色；`show_values: false` 只隐藏数值，不删除序列身份。
未声明时保留历史默认值，不把默认小字当成投影可读性证明；需作者按场景给出字号并
在目标 PowerPoint 检查长标签折行和遮挡。**载荷两式**：数值图表用 `categories + series[].values`；
复合排版图（`steps / process_flow / timeline / big_number_row / matrix / architecture`）
其中 matrix 用 `points`、architecture 用 `layers`，其余用 `data: [{label, value, desc?}]`——写错载荷编译期即拒（「没有可渲染的数据行」）。
截断型硬限额：process_flow/timeline 7、steps/progress_bar 6、ranked_bar/stacked_bar 8、
big_number_row 5、matrix/bubble 12、architecture 3；超过时在编译前 BLOCK，不能静默丢尾项。

**跨页锚的眉标**：`anchor.eyebrow` 由本页结论派生短标（3–6 字，写「这一段在论证里的
位置」，不写页面类型），作者可在 brief 里逐页声明 `eyebrow` 原样压过派生。
**首 / 末页是陈述位**：没有 content 也按作者写下的那句主张成立，不会因为没有证据而
告警或退回 absent——封面与收尾的证据在别的页上。

**来源区**：`source_zone` 内只放 `role ∈ {source, method, metadata}` 的文字，
其他对象与之相交即 `SOURCE_COLLISION`。**跨页锚**：`role=eyebrow` 与 `role=page_number`，
位置全 deck 一致（plan 在 ≥4 页时逐页发）。**全幅影像上叠字**：图元素声明
`layer: "background"` 且覆盖 ≥60% 画布（伪背景仍拦），其上文字按正常容量与
安全区纪律落位；不声明的图按内容对象参与碰撞检查——叠字即 `OVERLAP`。

## 作者逃生口（生产实证 · 写 spec / 出图前查）

- 逐页 `eyebrow: "单位经济"`：眉标文本；写了就压过派生（跨页锚位置仍须全 deck 一致）。
- 页级 `background`（#HEX）参与资产 QC 亮度判据：暗色沉浸页声明深底色，
  断崖判据问「图与这一页的落差」，不问与整副纸面的落差。
- 形状类图表（ranked_bar 等）主叙事色默认强调色；作者用 `primary_color` /
  `color_role` 把非高亮系列压回墨色——强调色只指一个答案，不铺面。
- `stroke` 只读色值；`{"type":"none"}` = 显式无描边（与 fill 同形写法对齐）。
- `plan --skeleton` 不覆盖任何不同内容的现有文件，改写 `<name>.new.py`；同内容不重写，副本也冲突则停止。`workflow.skeleton_path` 是实际路径。
- `plan --json` 只回摘要与 `plan_path`；完整判断读该文件一次。`typography.scale` 只保留内容相关的栏宽建议与语义断行，不提供固定字阶配额。
- 资产指纹不含 `safe_area` / `text_color`：校准压字区不使已出图作废；
  二者仍进清单，QC 对成图复核。
- `vao.py qc --assets-manifest m.json`：离线像素体检（与 check 同判据），
  不写状态、不消耗 retry——出图迭代的最短反馈环。

## 第三层证据（替代引擎实际渲染）

```bash
python scripts/render_evidence.py out.pptx --out evidence/   # 交付产物
python scripts/render_evidence.py build.py --out evidence/   # 现场编译再渲染
```

只采集事实：引擎与版本、页数与逐页 SHA-256、PDF 摘要；`status` 为
`COLLECTED`（已取证）/ `PDF_ONLY`（无栅格化器，只有 PDF 排版凭证）/
`UNAVAILABLE`（无渲染器 = **没有证据**）/ `FAILED`。退出码 0 / 0 / 3 / 2。
它不产出 PASS/BLOCK，不写发布清单，不改变 `release_eligible`；
`target_powerpoint / native_editing / independent_visual_review` 恒为未验证。

边界：替代引擎（LibreOffice）的真实排版 ≠ 目标 PowerPoint 排版（字体回落、
自动轴范围、自动换行都可能不同），它是排障与方向核验，不是视觉终验。

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
| 结构预览 | 关键页取证（封面/章节/画心/密数据/收尾，默认 5 页） | 全 deck 逐页 |

阻断项与阈值两档相同，但快档的多数像素统计在整数箱平均后的工作域，边界案例可能与原生
分辨率结果不同；文字安全区纹理和硬缝仍看原图。需逐页结构取证的终稿选 `strict`；
`fast` 仅取关键页，不要写成「全页已看过」。`--deadline`（默认 120s）只会跳过可选预览，
不跳过核心正确性；release 预览因时限跳过即 BLOCK，须补跑同一条 check。
严格档必须完整覆盖全部页面；快速档允许清单明确记录的关键页抽样。

## Failure codes

`OVERLAP` `SOURCE_COLLISION` `CHART_LABEL_COLLISION` `TEXT_OVERFLOW` `DATA_INTEGRITY_FAIL`
`CHART_TYPE_FAIL` `COMPILE_FAIL` `GUARD_FAIL` `ASSET_WORKFLOW_FAIL`
→ BLOCKED，按 `fix_plan` 根因组一次改完（组内含明细，零回读）。

## Release Manifest

`check --mode release` 生成 `source_spec_hash / validation / verification / compile_report
（含 output_sha256）/ ghost_preview / asset_workflow / status`。校验三件事：报告盖的 spec 戳与
当前一致；PPTX 字节戳与磁盘一致（一次哈希比对）；预览证据的唯一页面/文件数与声明一致，完整取证按叙事顺序覆盖当前 spec。
缺 spec 戳、PPTX 路径/摘要或预览均不能 PASS。输入异常也覆盖旧 PASS 清单，
磁盘可能保留旧 PPTX，但它不再代表当前输入的有效交付。
`release_eligible` 仅在 release 档、编译通过且凭证全有效时为真。

`verification.target_powerpoint/native_editing/independent_visual_review` 明确记录未验证状态；
此工具不消费外部签署，也不会因自动化 PASS 自动升级它们。替代引擎记录与人工审阅须单独附上。
