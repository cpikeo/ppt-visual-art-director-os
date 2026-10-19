# Contract（执行契约 · 写 elements 前查）

落地给什么值、什么会被当场抓住。判断基准 → `../SKILL.md`；资产链 → `assets.md`。

## 判定边界

QA 只回答硬约束与凭证是否通过（PASS / BLOCK），不签署视觉终验（SKILL §6）。

- **拦（error → BLOCK）**：编译失败 · 内容缺失 · 空 deck/空页 · 溢出（框装不下 / 超 max_lines / 禁换行超宽）
  · 越界与退化几何 · 重叠与来源区侵入 · 无效图表类型 / 空载荷 / 非有限值（含 `matrix.points[].x/y`）/ 行标签缺失
  · 同指标跨页单位不一致 · release 缺来源/单位/期间/口径 · 认不出的色名 · 未消费或不可见的字段。
- **不拦（归作者判断）**：好不好看、密度、颜色克制度、字号与留白、构图平衡、图表类型是否选得对、口径文字怎么写。

## 文件与信任边界

- `.py` brief/build 是**明确可信的作者代码**，以当前进程权限执行，不是沙箱；不可信输入只用 JSON/YAML（YAML 走 safe_load），仍应限制文件大小与运行资源。
- `plan/check` 拒绝已知输入、原图与输出/修复包/清单/QC 报告彼此同路径，含现有符号链接与硬链接；路径冲突直接非零退出。
- PPTX 保存与后处理均使用同目录唯一临时文件，完成后原子替换；失败保留旧完整包。交付须同时核对退出码、当前清单状态及 output_sha256。
- 单文件原子写入不等于整套产物事务：不支持多个任务并发写同一 output/preview/manifest。中断后须复跑完整 check。

## 文本测量边界

Guard 的字号、折行、字距与段距是**粗估**，不是目标字体的真实排版；中文禁则回退只在 ghost 折行模型里生效，编译器写入的是原生文本，实际断行由目标 PowerPoint 与字体决定。ghost 无违例也不证明 PPTX 正确（SKILL §6）。

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
`surface / dark_surface / premium / optional` 可显式声明；不写时由六 token 派生。衍生 token（`panel / hairline / series1–6 / on_* / negative` 等）一律自动算。
`negative` 是图表里 <0 那一段的语义色（损失 / 风险），按主题机械派生。**颜色只能写 #HEX 或 token 名**——写错名字会在产物里静默回落，所以必拦。

brief 与 spec 的页面 `id` 全稿唯一；取证顺序跟随 `slides`，不按 ID 字典序重排。

**元素信封**：`id`（非空、页内唯一）、`type`、`x/y/width/height`（必填）、`role`。

**归一化与网格**：几何按 4px 机械吸附，`(x,width)` 与 `(y,height)` **成对**处理——「一条细线 + 骑在它上面的对象」吸附后仍然同心，不需要手工凑偶数坐标。**厚度小于一个网格的尺寸原样保留**：`height:1` 的发丝线就是 1px。LINE / ARROW 的横线可用 `height:0`、竖线可用 `width:0`；归一化保留零厚度轴。`arrow` 从 `(x,y)` 指向 `(x+width,y+height)`，写入三角箭头；`line` 不带箭头。两轴皆零的零长度线及其他退化形状由 guard 拦截。需要完全绕开吸附时写 `snap: false`。
填充四写法：`"#RRGGBB"` · token 名 · `{type:solid,color,opacity}` · `{type:gradient,angle,stops≥2}` · `{type:none}`。**形状填充走 `fill`、描边走 `stroke`**。

| type | 专属字段 |
|---|---|
| `text` | `text size color align bold italic line_height max_lines wrap padding font family char_spacing uppercase opacity anchor space_before space_after` |
| `shape` | `shape`(rect/rounded_rect/ellipse/triangle/diamond/pie/line/arrow) `fill stroke stroke_width fill_role text padding text_size text_color text_bold text_wrap text_line_height text_opacity text_anchor` |
| `image` | `asset_id`（必需）`fit`(cover/contain) `crop asset_function overlay` |

**编辑级文字纪律**：`size/width/height/padding/space_before/space_after` 按画布 px 填；`line_height` 是相对倍数；`char_spacing` 以 pt 填。`theme.fonts.cn`（别名 `body`）决定中文字体，`latin`（别名 `display`）决定拉丁字体；现有 `font` token 与 `family` 元素字段只覆盖拉丁字体。形状内文字同样读 `padding`（缺省 0）。`fill: {type: none}` / 省略 `fill` = 真空心。PIL 是结构取证，字体字形/换行在 PowerPoint 上须另行校验。

`chart_kind` 的合法值、编译路由、载荷形态、数值属性、截断上限与预览口径只在 `primitives.CHART_SPEC` 定义一次；本文不抄录——双写迟早漂移。
`kpi/executive_kpi/big_number` 读元素级 `value`，数值 `0` 是有效内容。`pie/donut/donut_composition` 的数值须非负且有效总和大于零；`pie` 只接受一个序列。
数值图表齐 `source / unit / period / basis`（release 硬门）；同 `metric` 跨页必须同单位。`label_size` 控制原生轴标签、`value_size` 控制数值标签（画布 px，写入 PPTX 乘 0.75 转 pt）。多序列 `name` 必须非空且唯一。**载荷两式**：数值图表用 `categories + series[].values`；复合排版图（`steps / process_flow / timeline / big_number_row / matrix / architecture`）用 `data: [{label, value, desc?}]`，其中 matrix 用 `points`、architecture 用 `layers`。`matrix` 每个点是 `{x, y, label}`：`x/y` 必须为有限数字。
**目标线**（只由 `ranked_bar` 渲染）：`target` 为有限数字 + 可选 `target_label`；超出数据范围按端点夹紧；写非数字由硬门拒绝。其他 kind 写这两个字段会得到 `chart_field_unconsumed` 告警。
**`highlight` 的命名空间**（`primitives.resolve_chart_highlight`，同源）：写**序列名** = 整条序列强调；写**类别名** = 该类目数据点强调；写**整数**时多序列按序列索引、单序列按类别索引。不命中则不猜（guard 发告警）。
带截断上限的 kind 超过上限时编译前 BLOCK，不能静默丢尾项。

**跨页锚的眉标**：`anchor.eyebrow` 由本页结论派生短标（3–6 字），作者可在 brief 里逐页声明原样压过。**首 / 末页是陈述位**：没有 content 也按作者写下的主张成立。

**来源区**：`source_zone` 内只放 `role ∈ {source, method, metadata}` 的文字，其他对象与之相交即 `SOURCE_COLLISION`。**全幅影像上叠字**：图元素声明 `layer: "background"` 且覆盖 ≥60% 画布（伪背景仍拦），其上文字按正常容量与安全区纪律落位。

## 作者逃生口

- 逐页 `eyebrow: "…"`：写了就压过派生（跨页锚位置仍须全 deck 一致）。
- 页级 `background`（#HEX）参与资产 QC 亮度判据。
- 形状类图表主叙事色默认强调色；作者用 `primary_color` / `color_role` 把非高亮系列压回墨色。
- `stroke` 只读色值；`{"type":"none"}` = 显式无描边。
- `plan --skeleton` 不覆盖不同内容的现有文件，改写 `<name>.new.py`。
- `plan --json` 只回摘要与 `plan_path`；完整判断读该文件一次。
- `vao.py qc --assets-manifest m.json`：离线像素体检，不写状态、不消耗 retry。

## 执行模式与速度

- `spec`：归一化 + 硬门，不编译。`draft`：硬门 + 编译 + 修复包。`release`：draft + 出处硬门 + 结构预览 + Manifest。
- `--speed fast`（默认）：资产 QC 降采样、编译缓存用 size+mtime 探针、预览只画关键页。
- `--speed strict`：全分辨率 QC、整包字节 SHA-256 核对、全页预览。**终稿用 strict**。
- 阻断项与阈值两档相同；`--deadline`（默认 120s）只跳过可选预览，不跳过正确性。release 因时限跳过预览即 BLOCK。

## Failure codes

`OVERLAP` `SOURCE_COLLISION` `CHART_LABEL_COLLISION` `TEXT_OVERFLOW` `DATA_INTEGRITY_FAIL`
`CHART_TYPE_FAIL` `COMPILE_FAIL` `GUARD_FAIL` `ASSET_WORKFLOW_FAIL`
→ BLOCKED，按 `fix_plan` 根因组一次改完（组内含明细，零回读）。

## Release Manifest

`check --mode release` 写出 `source_spec_hash / validation / verification / compile_report（含 output_sha256）/ ghost_preview / asset_workflow / status`。缺 spec 戳、PPTX 摘要或预览证据即不能 PASS。`verification.target_powerpoint / native_editing / independent_visual_review` 恒为未验证。

### 安全发布与失败语义

- 预览与编译缓存目录须独立于输入与交付物；现有 symlink/hardlink 子项拒绝。路径冲突返回 2。
- release 先写 `status=BLOCKED` 的未完成清单；只有全链完成才能替换成 PASS。Ctrl-C 退出 130；可信作者 `SystemExit(0)` 使 CLI 失败（2）。
- 图表载荷 `data` 与 `series` 不能同时声明。
- 图片 `crop` 是 `[left, top, right, bottom]` 四个有限非 bool 数；`null` 等价四个 0。
- 行式图表的 `data` 每项须为对象且含非空 `label`；坏行不能被静默丢弃。
- 编译报告失败时不发布部分 PPTX，不为旧文件签署本轮成功凭证。
- 盲评导出必须使用空目录且不得覆盖已有 key；汇总以 key 的完整版本集计算。
