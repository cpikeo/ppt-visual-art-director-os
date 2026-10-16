# Contract（执行契约 · 写 elements 前查）

落地给什么值、什么会被当场抓住。判断基准 → `../SKILL.md`；资产链 → `assets.md`。

## 判定边界

QA 只回答硬约束与凭证是否通过（PASS / BLOCK），不签署视觉终验（SKILL §6）。

- **拦（error → BLOCK）**：编译失败 · 内容缺失 · 空 deck/空页 · 溢出（框装不下 / 超 max_lines / 禁换行超宽）
  · 越界与退化几何 · 重叠与来源区侵入 · 无效图表类型 / 空载荷 / 非有限值（含 `matrix.points[].x/y`）/ 行标签缺失
  · 同指标跨页单位不一致 · release 缺来源/单位/期间/口径 · 认不出的色名 · 未消费或不可见的字段。
- **不拦（归作者判断）**：好不好看、密度、颜色克制度、字号与留白、构图平衡、图表类型是否选得对、
  口径文字怎么写。

## 文件与信任边界

- `.py` brief/build 是**明确可信的作者代码**，以当前进程权限执行，不是沙箱；不可信输入只用 JSON/YAML（YAML 走 safe_load），仍应限制文件大小与运行资源。
- `plan/check` 拒绝已知输入、原图与输出/修复包/清单/QC 报告彼此同路径，含现有符号链接与硬链接；路径冲突直接非零退出，不落可能覆盖输入的修复包。
- PPTX 保存与后处理均使用同目录唯一临时文件，完成后原子替换；失败保留旧完整包。旧包存在不代表本轮成功，交付须同时核对退出码、当前清单状态及 output_sha256。
- 单文件原子写入不等于整套产物事务：不支持多个任务并发写同一 output/preview/manifest；不要把工作目录交给不可信进程并发改符号链接。中断后须复跑完整 check。

## 文本测量边界

Guard 的字号、折行、字距与段距是**粗估**，不是目标字体的真实排版；中文禁则回退只在 ghost 折行模型里生效，
编译器写入的是原生文本，实际断行由目标 PowerPoint 与字体决定。ghost 有违例只提示人工复核；无违例也不证明 PPTX 正确（SKILL §6）。

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

brief 与 spec 的页面 `id` 全稿唯一；取证顺序跟随 `slides`，不按 ID 字典序重排。

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

`chart_kind` 的合法值、编译路由（原生/形状/大数字）、载荷形态、数值属性、截断上限
与预览口径只在 `primitives.CHART_SPEC` 定义一次（五维一表），Guard、编译器与预览
全部派生自它；本文不再抄录枚举与数值表——双写迟早漂移成「放行但截尾」。
`kpi/executive_kpi/big_number` 读元素级 `value`（数字展示），数值 `0` 是有效内容，不是缺失。
`pie/donut/donut_composition` 的数值须非负且每个构成序列的有效总和大于零；`pie` 只接受一个序列，不得静默隐藏其他系列。
数值图表齐 `source / unit / period / basis`（release 硬门）；
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
`matrix` 的每个点是 `{x, y, label}`：`x/y` 必须为有限数字（缺失或非数值由硬门拦下，
前端不会收到裸 `KeyError`）。
**目标线**（只由 `ranked_bar` 渲染）：`target` 为有限数字 + 可选 `target_label` 字符串，
在排行榜上画一条竖直参考线（门槛／「要到哪」），数值超出数据范围时按端点夹紧；
写非数字由硬门拒绝（声明了却画不出来 = 静默丢失）。其他 kind 不消费这两个字段，
写在那里只会得到一条 `chart_field_unconsumed` 告警。
**`highlight` 的命名空间**（`primitives.resolve_chart_highlight`，编译/预览/guard 同源）：
写**序列名** = 整条序列强调（accent + 加粗）；写**类别名** = 该类目上的数据点强调
（`data` 与 `categories + series` 两种载荷同义，落原生 `dPt`）；写**整数**时，多序列
（≥2 条）按序列索引、单序列按类别索引。都不命中则不猜（guard 发 `chart_highlight`
告警，产物与预览都不产生强调）。点级强调存在时，序列基础色不占用 accent。
带截断上限的 kind（见 `CHART_SPEC` 的 `limit`）超过上限时在编译前 BLOCK，不能静默丢尾项；
编译器与预览的截断与该表同源，不存在第二份数值。

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

## 执行模式与速度

- `spec`：归一化 + 硬门，不编译。`draft`：硬门 + 编译 + 修复包。`release`：draft + 出处硬门 + 结构预览 + Manifest。
- `--speed fast`（默认）：资产 QC 降采样、编译缓存用 size+mtime 探针、预览只画关键页（封面/章节/画心/密数据/收尾）。
- `--speed strict`：全分辨率 QC、当前整包字节 SHA-256 核对、全页预览。**终稿用 strict**；fast 不能写成「全页已看过」。
- 阻断项与阈值两档相同；`--deadline`（默认 120s）只跳过可选预览，不跳过正确性。release 因时限跳过预览即 BLOCK，须补跑同一条 check。

缓存身份：JSON 以当前字节摘要复用解析；磁盘摘要不以 size/mtime 猜测未变。
同轮已经核验的字节/摘要由调用方显式传递；fast 的产物探针仍非防篡改凭证。
预览页与整套凭证都包含常规/粗体候选字体身份；每轮入口刷新字体集合，变更后重画。
字体身份使用候选路径与 stat，不是逐字 glyph 覆盖证明；真实字体排版仍须目标软件检查。

## Failure codes

`OVERLAP` `SOURCE_COLLISION` `CHART_LABEL_COLLISION` `TEXT_OVERFLOW` `DATA_INTEGRITY_FAIL`
`CHART_TYPE_FAIL` `COMPILE_FAIL` `GUARD_FAIL` `ASSET_WORKFLOW_FAIL`
→ BLOCKED，按 `fix_plan` 根因组一次改完（组内含明细，零回读）。

## Release Manifest

`check --mode release` 写出 `source_spec_hash / validation / verification / compile_report（含 output_sha256）/
ghost_preview / asset_workflow / status`。缺 spec 戳、PPTX 摘要或预览证据即不能 PASS；输入异常时覆盖旧 PASS 清单。
`release_eligible` 仅在 release、编译通过且凭证全有效时为真。`verification.target_powerpoint / native_editing /
independent_visual_review` 恒为未验证；工具不消费外部签署，也不自动升级它们。


### 安全发布与失败语义（未发布修复）

- 预览与编译缓存目录须独立于输入、PPTX、修复包、清单及另一辅助目录；现有 symlink/hardlink 子项拒绝。缓存目录被普通文件占位仍可诊断并回落完整编译，不覆盖占位文件。
- 路径冲突返回 2，且不写任何可能覆盖输入的诊断；因此这类冲突不得仅靠磁盘上的旧清单判定本轮结果。
- release 在安全路径/资产预检后先写 `status=BLOCKED, release_eligible=false` 的未完成清单；只有全链完成才能替换成 PASS。Ctrl-C 退出 130；可信作者 Python 内的 `SystemExit(0)` 使 CLI 失败（2），不是成功凭据。
- 原子写入是单文件保证，不是多产物全局事务或并发锁；预检前 SIGKILL、同输出并发及敌对 TOCTOU 未获保证。请为每个运行使用独立工作目录，并以当轮退出码及当轮凭证共同判定。
- 图表载荷 `data` 与 `series` 不能同时声明（即使空数组也不作静默优先级）；旧 `data` 加冗余 `categories`、没有 series 的输入继续兼容。
- 图片 `crop` 是 `[left, top, right, bottom]` 四个有限非 bool 数，单项 `[0,1)`、对边和 `<1`；`null` 等价四个 0。编译与 ghost 共用，缓存包含 crop。
- `ghost_preview` 中的物理文件须存在且非空；联络表缓存验证 PNG 可解码后才复用。此项不是图片内容签名、语义认证或真实 PowerPoint 视觉验收。

### 本轮完整性补强（e734d6a 后的本地审计修复）

- 行式图表的 `data` 每项须为对象且含非 null、非空白的 `label`；即使其他行可画，坏行也不能被静默丢弃。Guard 与独立 compiler 同时拒绝。
- 非 null `series` 声明与任何显式 `data` 键互斥（包括 `data: [] / null / false`）；只写 `data + categories`、不写 series 的旧形式不变。
- 编译报告失败时不发布部分 PPTX、不覆盖旧完整文件，也不为旧文件签署本轮摘要或记录本轮成功缓存。失败报告的 `output_exists=false` 表示「本轮未发布」，不保证磁盘上没有上次完整文件；以当轮退出码及清单为准。
- 未声明主题背景时保留 PowerPoint 默认背景；作者明确授权的 `hide_redundant` 不再单独制造编译失败。其他编译错误仍阻断，不删除诊断。
- 非对象预览 marker、错类型提示词缓存 entries 会回落重建；不是将坏业务输入视为有效，也不放宽任何图像 QC。
- 盲评导出必须使用空目录且不得覆盖已有 key；不合并旧版本、不删除旧评分。汇总以 key 的完整版本集计算完整评审人数，拒绝非有限评分、未知版本和同评审同版本重复评分。统计一致性不等于专业视觉验收。
