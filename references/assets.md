# Assets（资产执行契约）

设计判断只见 `../SKILL.md`；此文件说明如何消费 plan 的资产决策。`vao.py plan` 判断确需图像时，在同一次执行将 `asset_manifest.json` 写到计划目录；外部工具按契约准备图像，`check` 完成 QC 与链核验。无图不生成空清单。

## 1. 计划字段

逐页 `asset: required|reuse|none` 为作者声明；`asset_subject` 为画面主体。图像只由作者声明产生（`asset: required|reuse`）；词表命中只写 hint 不出图。声明的图全部进入清单，不设自动额度。

- `asset_role: background|illustration|hybrid`：承载空间 / 表达对象 / 两者兼有。角色影响提示词与 QC。
- `asset_function`：页面用途（hero|proof|emotion|context|frame|separate）。
- `asset_reason`（可选）：记录删除素材会损失什么；进入骨架，不作为出图触发器。
- `asset_composition`（可选）：素材内部的景别、裁切、主体重心；覆盖资产构图句，不自动更改页面布局。
- `material / lighting / texture`：原样覆盖 plan 推导值。`texture: []` 关闭纹理。
- 生成图始终是生成图，不能用 `witness` 字段升级为事实证词。

## 2. 执行顺序

```
brief → plan（同次准备清单）→ 按清单批量备图/核权 → 编排 → release check（QC + 链核验 + 预览）
```

清单条目字段：`asset_id / slide_ids / decision / asset_role / prompt / negative / ratio / safe_area / expected_filename / status`。默认 PNG；照片推荐同 stem JPEG（q92 4:4:4），落位按 2× 交付。解析器先找确切文件名，再试同 stem 的 png/jpg/jpeg/webp；多备选并存 = 歧义。

## 3. 提示词

提示词消费 plan 与页级声明。`medium` 显式声明优先于上下文线索；光照声明、素材构图均保留。摄影只补物理可信性，不规定固定留白比例或景别。反向词只默认排除生产失效；明确禁项写 `negative` 或 deck 的 `avoid`。

背景可继承视觉世界的材质与融合；对象型插图不默认继承。需要时显式写 `material / lighting / texture`；确需融合再声明 `fusion_enabled: true`。`energy: low|high` 调整世界光语强弱。提示词缓存 v3，旧缓存重建。

图标语义与编排判断见 SKILL §3；当前不增加 `asset_role: icon` 或 SVG 编译器。

## 4. 三条路径

| 路径 | 做法 |
|---|---|
| **生成** | 按清单 prompt / negative / ratio / safe_area 出图；QC 按实际像素判定 |
| **既有素材** | `asset_source: {kind: provided\|licensed\|original\|reuse, path, source}`；跳过生成，仍须 QC |
| **无图** | `decision: none`；排版、留白与数字承担这一页 |

## 5. QC 与核验

- QC 只判物理事实：安全区是否被纹理压到文字、对比是否够、可见像素/透明度、比例是否匹配、有效分辨率是否低于落位尺寸。
- 两档均读取并哈希当轮字节，测量缓存不得仅凭 size/mtime 复用。
- 同一既有素材、同一 QC 契约跨页复用一个主条目与 `slide_ids`；安全区或字色不同则分别核验。
- 资产链核验：每张图 = QC 通过的那张 + 绑到正确的页 + 分辨率够 + 文件未被替换。
- `draft` 档坏图最多一次定向重出；`release` 档坏图直接 BLOCK。
- `qc` 复用生产解析与判据，仅读不写；阻断退出码为 2。

人工验收只用 `SKILL.md §3 / §6`，不在此维护第二套审美标准。

### 来源与缓存硬边界

图片链要求清单的 `workflow.schema` 精确为 `vao-asset-chain-v2`，`brief_path` 指向真实文件，`brief_file_sha256` 为匹配字节的 SHA-256。缺 brief / 缺摘要 / 伪造 schema 均不能用清单自洽性代替来源核验；修改 brief 后须重跑 plan。

像素 QC 可暖复用，但来源/工作流状态仍每轮核验。`crop` 与编译/ghost 共用校验和几何。
