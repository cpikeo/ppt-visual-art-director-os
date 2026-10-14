# Assets（资产必要性 · 提示词 · QC）

资产决策不等于填图。图片工具不在本包：`vao.py plan` 判断确需图像时，在**同一次执行**
将 `asset_manifest.json` 写到计划目录（`--assets-out` 仅用于改路径），外部工具按契约准备
图像或登记已授权素材，`check` 完成 QC 与链核验。无图不生成空清单。

## 1. 计划字段与执行

设计判断只见 `../SKILL.md`；此文件说明如何消费 plan，不重新判断媒体必要性。
逐页 `asset: required|reuse|none` 为作者声明；`asset_subject` 为画面主体。
页面角色与证据可由作者声明 `role` / `evidence`（原样生效，非法值忽略并告警）。
图像只由作者声明产生（`asset: required|reuse`）；词表命中只写 hint 不出图。声明的图全部进入清单，不设自动额度。`assets_hint.generate` 即声明出图的页。
`asset_role: background|illustration` 分别传给背景/对象 QC；`asset_function` 记录页面用途。
`material / lighting / texture` 原样覆盖 plan 推导值；`medium` 与材质独立。
生成图始终是生成图，不能用 `witness` 字段把它升级为事实证词。

## 2. 顺序与责任

```
brief → plan（按需同次准备清单）→ 按清单批量备图/核权 → 编排 → release check（QC + 链核验 + 预览）
```

清单条目字段：`asset_id / slide_ids / decision / asset_role / prompt / negative /
ratio / safe_area / expected_filename / status`。默认 PNG；照片推荐同 stem JPEG
（q92 4:4:4），落位按 2× 交付。解析器先找确切文件名，再试同 stem 的 png/jpg/jpeg/webp；
多备选并存 = 歧义，须明确文件名。

## 3. 提示词输入

提示词消费 plan 的视觉世界与页级覆盖，不查询另一份风格表。
`energy: low|high` 与 `motion: still|reveal|spatial` 为执行参数；提示词与负向词在清单中留存。

## 4. 三条路径

| 路径 | 做法 |
|---|---|
| **生成** | 按清单 prompt / negative / ratio / safe_area 出图；QC 按实际像素判定 |
| **既有素材** | `asset_source: {kind: provided\|licensed\|original\|reuse, path, source}`；跳过生成，仍须 QC |
| **无图** | `decision: none`；注意力属于内容本身——排版、留白与数字承担这一页 |

## 5. QC 与核验

- QC 只判物理事实：安全区是否被纹理压到文字、对比是否够、可见像素/透明度、
  比例是否匹配（不符需裁切时显式 `asset_allow_crop: true`）、有效分辨率是否低于落位尺寸。
- 判定按「像素预算 + 判定实现」复用：同清单 + 同像素口径 + 同字节身份 ⇒ 不重测。
- 资产链核验：每张图 = QC 通过的那张 + 绑到正确的页 + 分辨率够 + 文件未被替换。
- `draft` 档坏图最多一次定向重出；`release` 档坏图直接 BLOCK（不为失败的稿子背书）。

`qc` 复用生产解析与判据，仅读不写；阻断退出码为 2。主体语义完整性与授权真实性仍需人工核验。
