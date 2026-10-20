# Contract（执行契约 · 写 elements 前查一次）

落地给什么值、什么会被当场抓住。判断基准 → `../SKILL.md`；资产链 → `assets.md`。

## 判定边界

QA 只回答硬约束与凭证是否通过（PASS / BLOCK），不签署视觉终验（SKILL §6）。

- **拦（error → BLOCK）**：编译失败 · 内容缺失 · 空 deck / 空页 · 溢出（框装不下 / 超 `max_lines` / 禁换行超宽）· 越界与退化几何 · 重叠与来源区侵入 · 无效图表类型 / 空载荷 / 非有限值（含 `matrix.points[].x/y`）/ 行标签缺失 · 同指标跨页单位不一致 · release 缺来源 / 单位 / 期间 / 口径 · 认不出的色名 · **疑似写错的字段名**（写成「font_size」而字段是 `size`、「maxlines」而字段是 `max_lines`：渲染器不消费该名，写错等于静默丢弃）· 渐变 `stops` < 2。
- **告警不拦**：与任何已支持字段都对不上的未知字段（可能是作者自己的注解）、非 `ranked_bar` 上的 `target`、不可见的 `unit`。
- **不拦（归作者判断）**：好不好看、密度、颜色克制度、字号与留白、构图平衡、图表类型选得对不对、口径文字怎么写。

## Spec 字段速查

```python
spec = {
  "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},
  "theme":  {"colors": {…六 token…}, "fonts": {"cn": …, "latin": …}},   # 家族 ≤2
  "slides": [{"id": "s01",
              "anchor": {"eyebrow": "…", "page_number": 2},   # ≥4 页时由 plan 发
              "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
              "elements": [ … ]}],
}
```

`theme.colors` 六 token：`background / ink / muted / primary / secondary / accent`；`surface / dark_surface / premium / optional` 可显式声明，不写时由六 token 派生，其余衍生 token（`panel / hairline / series1–6 / on_* / negative`）一律自动算。`negative` 是图表中 <0 段的语义色。**颜色只能写 #HEX 或 token 名**——写错名字会在产物里静默回落，所以必拦。页 `id` 全稿唯一；取证顺序跟随 `slides`，不按 ID 字典序重排。

**元素信封**：`id`（非空、页内唯一）、`type`、`x/y/width/height`（必填）、`role`。

**归一化与网格**：`(x,width)` 与 `(y,height)` **成对**吸附到 4px 网格——尺寸被圆整时保住**中心**，所以边不一定是 4 的倍数，中心一定在网格上；细线与其上的对象吸附后仍同心，二次归一不再位移。**厚度小于一个网格的尺寸原样保留**（`height:1` 的发丝线就是 1px）；LINE / ARROW 横线可用 `height:0`、竖线可用 `width:0`。`arrow` 从 `(x,y)` 指向 `(x+width,y+height)` 并写三角箭头，`line` 不带箭头；两轴皆零的零长度线与其他退化形状被拦。完全绕过吸附写 `snap: false`。

填充四写法：`"#RRGGBB"` · token 名 · `{type:solid,color,opacity}` · `{type:gradient,angle,stops≥2}` · `{type:none}`。**形状填充走 `fill`、描边走 `stroke`**；`stroke` 只读色值，`{"type":"none"}` 为显式无描边；省略 `fill` 或 `{type:none}` = 真空心。

| type | 专属字段 |
|---|---|
| `text` | `text size color align bold italic line_height max_lines wrap padding font family char_spacing uppercase opacity anchor space_before space_after` |
| `shape` | `shape`(rect/rounded_rect/ellipse/triangle/diamond/pie/line/arrow) `fill stroke stroke_width fill_role text padding text_size text_color text_bold text_wrap text_line_height text_opacity text_anchor` |
| `image` | `asset_id`（必需）`fit`(cover/contain) `crop asset_function overlay layer` |

**编辑级文字纪律**：`size / width / height / padding / space_before / space_after` 按画布 px 填，`line_height` 是相对倍数，`char_spacing` 以 pt 填。字阶只有一张表（`primitives.TYPE_SCALE`，1280 宽画布；plan 的 `deck.type_scale` 与骨架注释都由它派生），编译器与预览的缺省字号也取自该表——不要在页内另造档位。`theme.fonts.cn`（别名 `body`）决定中文字体，`latin`（别名 `display`）决定拉丁字体；`font` token 与 `family` 元素字段只覆盖拉丁字体。PIL 是结构取证，字形与换行须在 PowerPoint 上另行校验。

`chart_kind` 的合法值、编译路由、载荷形态、数值属性、截断上限与预览口径只在 `primitives.CHART_SPEC` 定义一次，本文不抄录。kpi 读元素级 `value`，数值 `0` 是有效内容；pie / donut 的数值须非负且总和 > 0，pie 只接受一个序列。9.36 合并掉的七个旧名（executive_kpi / big_number / trend / single_trend_line / comparison_bar / horizontal_bar / donut_composition）**在 9.38 起不再可写**：guard 在任何档位都报 error（失败码 CHART_KIND_ALIAS），报错给出 canonical、该名当年隐含的默认值与改名命令。它们只留在退役表里供报错与迁移使用，不参与编译。批量改名：`python3 tools/rename_chart_kinds.py <plan.json|build.py> --write`（改名与补默认值一次原子完成，产物逐字节不变）；全量迁移审计：`python3 tools/rename_chart_kinds.py --audit .`（有旧名退出码 1）。数值图表齐 `source / unit / period / basis`（release 硬门），同 `metric` 跨页必须同单位。`label_size` 控原生轴标签、`value_size` 控数值标签（画布 px，写入 PPTX 乘 0.75 转 pt）；多序列 `name` 必须非空且唯一。

**载荷两式**：数值图表用 `categories + series[].values`；复合排版图（`steps / process_flow / timeline / big_number_row / matrix / architecture`）用 `data: [{label, value, desc?}]`（matrix 用 `points`、architecture 用 `layers`，`matrix` 每点为 `{x, y, label}`，x/y 须为有限数字）。两式不得同时声明。**目标线**只由 `ranked_bar` 渲染：`target` 为有限数字 + 可选 `target_label`，超出数据范围按端点夹紧；其他 kind 写这两个字段得到 `chart_field_unconsumed` 告警。**`highlight`**（`primitives.resolve_chart_highlight`）：写序列名 = 整条序列，写类别名 = 该数据点，写整数时多序列按序列索引、单序列按类别索引；不命中则不猜（guard 告警）。

**跨页锚**：`anchor.eyebrow` 由本页结论派生 3–6 字短标，作者可逐页声明压过。**首 / 末页是陈述位**：没有 content 也按作者写下的主张成立。

**来源区**：`source_zone` 内只放 `role ∈ {source, method, metadata}` 的文字，其他对象与之相交即 `SOURCE_COLLISION`。**全幅影像上叠字**：图元素声明 `layer: "background"` 且覆盖 ≥60% 画布（伪背景仍拦），其上文字按正常容量与安全区纪律落位。**`safe_area` 是执行项，不是提示词**：页上写 `safe_area: {x, y, width, height}`（0–1 归一化，相对整幅背景图）即视为压字区契约——其上每个文字元素的锚点（横向按 `align`、纵向按 `anchor`，缺省左/上）必须落在区内，越界报 `safe_area`；页上不写则由资产清单同名字段继承，两处都写却不一致直接 BLOCK（图按 A 留白、字按 B 排）。`{}` = 本页不压字；`role ∈ {source, method, metadata}` 的页脚小字与显式 `safe_area_exempt: true` 的元素不在此列。

## 作者逃生口

- 逐页 `eyebrow: "…"` 压过派生（跨页锚位置仍须全 deck 一致）。
- 页级 `background`（#HEX）参与资产 QC 亮度判据。
- 形状类图表主叙事色默认强调色；用 `primary_color` / `color_role` 把非高亮系列压回墨色。
- `plan --skeleton` 不覆盖不同内容的现有文件，改写 `<name>.new.py`；`plan --json` 只回摘要与 `plan_path`（完整判断读文件一次）。
- `vao.py qc --assets-manifest m.json`：离线像素体检，不写状态、不消耗 retry。

## 执行模式与速度

- `spec`：归一化 + 硬门，不编译（零 python-pptx）。`draft`：硬门 + 编译 + 修复包。`release`：draft + 出处硬门 + 结构预览 + 发布清单。
- `--speed fast`（默认）：资产 QC 降采样、编译缓存 size+mtime 探针、预览只画关键页。`--speed strict`：全分辨率 QC、整包字节 SHA-256、全页预览，**终稿用 strict**。
- 两档阻断项与阈值相同；`--deadline`（默认 120s）只跳过可选预览，不跳过正确性——release 因时限跳过预览即 BLOCK。

## Failure codes

`OVERLAP` `SOURCE_COLLISION` `CHART_LABEL_COLLISION` `TEXT_OVERFLOW` `DATA_INTEGRITY_FAIL` `CHART_TYPE_FAIL` `COMPILE_FAIL` `GUARD_FAIL` `ASSET_WORKFLOW_FAIL` → BLOCKED，按 `fix_plan` 根因组一次改完（组内含明细，零回读）。

## 文件、信任与发布

- `.py` brief/build 是**明确可信的作者代码**，以当前进程权限执行，不是沙箱；不可信输入只用 JSON/YAML（YAML 走 safe_load），仍应限制文件大小与资源。
- `plan/check` 拒绝已知输入、原图与输出/修复包/清单/QC 报告彼此同路径（含现有 symlink 与 hardlink），冲突直接非零退出；预览与编译缓存目录须独立于输入与交付物并互不嵌套。
- PPTX 保存与后处理用同目录唯一临时文件，完成后原子替换；失败保留旧完整包。编译报告失败时不发布部分 PPTX，不为旧文件签署本轮成功凭证。
- release 先写 `status=BLOCKED` 的未完成清单，全链完成才替换为 PASS；中断后须复跑完整 check。Ctrl-C 退出 130，作者 `SystemExit(0)` 使 CLI 失败（2）。SIGTERM/SIGKILL 与并发写同一 output 不在保证内。
- 交付须同时核对**退出码 + 当前清单状态 + output_sha256**；单文件原子写入不等于整套产物事务。
- 清单键：`source_spec_hash / validation / verification / compile_report（含 output_sha256）/ ghost_preview / asset_workflow / status`；缺 spec 戳、PPTX 摘要或预览证据即不能 PASS。`verification.target_powerpoint / native_editing / independent_visual_review` 恒为未验证。

## 文本测量边界

Guard 与 ghost 共用**同一套**折行与度量（`primitives.wrap_lines` / `measure_text`）：能解析到主题字体时用真字面宽度，解析不到才回落到宽度表（只高估不低估）。两边只差「一个字有多宽」这一件事，不再各写一份判据。禁则（行首标点、数字与单位、行尾句读点悬挂半个字）与行首空白不计宽都在这一处生效。

与 LibreOffice 回放对拍 128 个探针（`tools/metrics_calibration.py`，逐行读 PDF 词框）：ghost 126/128 行数一致；guard 122/128，**不留低估**，6 个偏差全部是「多算一行」。guard 的余量只加在窄栏（每行不足 12 字时让出 0.1 个字宽，见 `verify.GUARD_NARROW_*`）：窄栏里 ±0.1 em 的字形误差就足以跨过换行阈值，宽栏里同样的绝对误差被摊薄，再加余量只会把能排下的句子判成溢出。剩余分歧集中在极窄栏（≤9 字/行）与 Office 的标点压缩细则。

编译器写的是原生文本，最终断行仍由目标 PowerPoint 与字体决定；ghost 无违例不证明 PPTX 正确（SKILL §6）。
