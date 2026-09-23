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

## 字阶与行高与字号（作者用，不是门槛）

字号阶梯（相邻级差 ≥1.25×，每页 ≤4 级）：Statement 64（40–80）· Display 44 ·
Title 32 · Lead 22 · Body 17 · Caption 12.5。
行高：大标题 1.05–1.15；小节 1.15–1.25；正文 1.3–1.5（中文取上限）；注释 1.2–1.3。
文本框必须装得下：`框高 ≥ 字号 × 行高 × 行数`（估算口径与编译器同一套原语）。
焦点与正文落差 ≥2.5×（字阶或面积取一）；结论至多 2 行；正文下限 16px。

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
填充四写法：`"#RRGGBB"` · token 名 · `{type:solid,color,opacity}` ·
`{type:gradient,angle,stops≥2}` · `{type:none}`。**形状填充走 `fill`、描边走 `stroke`**。

| type | 专属字段 |
|---|---|
| `text` | `text size color align bold italic line_height max_lines wrap padding font family char_spacing uppercase opacity anchor` |
| `shape` | `shape`(rect/rounded_rect/ellipse/triangle/diamond/pie/line/arrow) `fill stroke stroke_width fill_role text` |
| `image` | `asset_id`（必需）`fit`(cover/contain) `crop asset_function overlay` |

`chart_kind` 白名单（括号为每页上限）：bar/horizontal_bar/comparison_bar(8) · column(8) ·
line/trend/single_trend_line(8) · area(8) · donut/pie(8) · stacked_bar(8) · ranked_bar(8) ·
waterfall(12) · matrix(12) · bubble(12) · sparkline(12) · process_flow(7) · timeline(7) ·
steps(6) · progress_bar(6) · big_number_row(5) · architecture(3) · kpi/executive_kpi/big_number
（数字展示读元素级 `value`）。数值图表齐 `source / unit / period / basis`（release 硬门）；
同 `metric` 跨页必须同单位。

**来源区**：`source_zone` 内只放 `role ∈ {source, method, metadata}` 的文字，
其他对象与之相交即 `SOURCE_COLLISION`。**跨页锚**：`role=eyebrow` 与 `role=page_number`，
位置全 deck 一致（plan 在 ≥4 页时逐页发）。

## 执行模式与速度

| 模式 | 做什么 | 产物 |
|---|---|---|
| `spec` | 归一化 + 硬门，不编译 | 判定报告 |
| `draft` | 硬门 + 编译 | PPTX + 修复包 |
| `release` | draft 全部 + 出处硬门 + 关键页预览证据 + Manifest | PPTX + 预览 + Manifest |

| 项 | `--speed fast`（默认） | `--speed strict` |
|---|---|---|
| 资产 QC 像素域 | 长边降采样；安全区原分辨率 | 全分辨率 |
| 编译缓存探测 | size+mtime 快探针 | 整包 SHA-256 |
| 结构预览 | 关键页取证（封面/章节/画心/密数据/收尾，默认 5 页） | 全 deck 逐页 2× 超采样 |

判定口径两档完全相同；`--deadline`（默认 120s）只跳过可选预览证据，不跳过核心正确性。

## Failure codes

`OVERLAP` `SOURCE_COLLISION` `CHART_LABEL_COLLISION` `TEXT_OVERFLOW` `DATA_INTEGRITY_FAIL`
`CHART_TYPE_FAIL` `COMPILE_FAIL` `GUARD_FAIL` `ASSET_WORKFLOW_FAIL`
→ BLOCKED，按 `fix_plan` 根因组一次改完（组内含明细，零回读）。

## Release Manifest

`check --mode release` 生成 `source_spec_hash / validation / verification / compile_report
（含 output_sha256）/ ghost_preview / asset_workflow / status`。校验三件事：报告盖的 spec 戳与
当前一致；PPTX 字节戳与磁盘一致（一次哈希比对）；预览证据引用的页面都在当前 spec 内。
`release_eligible` 仅在 release 档、编译通过且凭证全有效时为真。
