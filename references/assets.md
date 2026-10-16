# Assets（资产必要性 · 提示词 · QC）

资产决策不等于填图。图片工具不在本包：`vao.py plan` 判断确需图像时，在**同一次执行**
将 `asset_manifest.json` 写到计划目录（`--assets-out` 仅用于改路径），外部工具按契约准备
图像或登记已授权素材，`check` 完成 QC 与链核验。无图不生成空清单。

## 1. 计划字段与执行

设计判断只见 `../SKILL.md`；此文件说明如何消费 plan，不重新判断媒体必要性。
逐页 `asset: required|reuse|none` 为作者声明；`asset_subject` 为画面主体。
页面角色与证据可由作者声明 `role` / `evidence`（原样生效，非法值忽略并告警）。
图像只由作者声明产生（`asset: required|reuse`）；词表命中只写 hint 不出图。声明的图全部进入清单，不设自动额度。`assets_hint.generate` 即声明出图的页。
`asset_role: background|illustration|hybrid` 分别为承载空间、表达对象、两者兼有；角色影响提示词与 QC，
不是摄影/插画的介质分类。`asset_function` 记录页面用途，不等于素材必要性的理由。
`asset_reason` 可选，记录删除素材会损失什么；已声明 asset 时，理由进入逐页媒体判断与骨架，不作为出图触发器或硬门。
`asset_composition` 可选，记录素材内部的景别、裁切、主体重心与图文关系，覆盖资产构图句；
它不是页面坐标，也不会自动更改页面布局或 QC 安全区。
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

提示词消费 plan 与页级声明，不再替作者选择 3D 插图、细线空心图标、自然光摄影或胶片颗粒。
`medium` 的显式声明优先于上下文介质线索；光照声明、素材构图与多条 texture 自由文本均保留。
摄影只补物理可信性，水墨只补所选介质的执行说明，不规定固定留白比例、景别或色阶数。
反向词只默认排除生产失效，不按人物关键词禁止握手、机器人或某类风格；明确禁项写 `negative` 或 deck 的 `avoid`。

背景可继承视觉世界的材质、纹理及融合；对象型插图不默认继承这些材质、光影和表面效果，也不默认透明底或背景融合。
需要时显式写 `material / lighting / texture`；确需融合再声明 `fusion_enabled: true`。`texture: []`、`safe_area: {}` 可分别关闭纹理、压字安全区。
`asset_composition` 指定主体位置时，同步核对 `negative_space_anchor / safe_area`，程序不猜几何。
`energy: low|high` 调整世界光语强弱，不覆盖作者光照；`motion: still|reveal|spatial` 仅在资产卡明确传入时展开，
不是新增的 brief 顶层字段。提示词与负向词在清单中留存，外部生成前核对它们确实只描述要生成的那张画面。
提示词缓存升为 v3，旧 v2 缓存重建；不自动删除或判废已经准备的素材，旧图仍需按 SKILL 人工复核。

图标的语义、家族与编排判断见 SKILL；这不是“每页图标槽位”。已有合适图标或简单原生可编辑形状优先，
不要用字体缺失的字符冒充可靠符号。当前生产清单不增加 `asset_role: icon` 或 SVG 编译器：需要栅格符号时按
`illustration` 声明介质/主体并登记 PNG 等受支持图片，明确其图像不可拆编辑；文字、标注及简单几何仍用原生元素。
直接调用提示词构建器的 `asset_type: icon` 也不预设线性或实心风格。

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
- 两档均读取并哈希当轮字节，测量缓存不得仅凭 size/mtime 复用；同一源图不同 QC 契约共用单轮字节快照，但分别测量/判定。fast 仍只降低像素统计预算。
- 同一生成视觉需求跨页若声明不同安全区、字色、底色、裁切或角色契约，当前不自动合并，plan 会明确拒绝；先备图，再用逐页 `asset_source` 登记同一文件，即可分别 QC。单页校准不改变原视觉指纹。
- 同一既有素材、同一 QC 契约跨页复用一个主条目与 `slide_ids`；安全区、底色或文字色不同则分别核验。既有素材 ID 现在包含 QC 契约，旧 spec 需随重新 plan 的清单重绑。
- 资产链核验：每张图 = QC 通过的那张 + 绑到正确的页 + 分辨率够 + 文件未被替换。
- `draft` 档坏图最多一次定向重出；`release` 档坏图直接 BLOCK（不为失败的稿子背书）。

`qc` 复用生产解析与判据，仅读不写；阻断退出码为 2。主体语义完整性与授权真实性仍需人工核验。

人工验收与修复只用 `SKILL.md §3 / §6`，不在此维护第二套审美标准；像素 QC 通过不证明语义、图标家族或整稿构图正确。


### 来源与缓存状态的硬边界（未发布修复）

图片链要求清单的 `workflow.schema` 精确为 `vao-asset-chain-v2`，`brief_path` 指向真实文件，
`brief_file_sha256` 为匹配其字节的 64 位十六进制 SHA-256（大小写均可）。缺 brief / 缺摘要 / 伪造 schema
均不能用清单自洽性代替来源核验；修改 brief 后须重跑 plan。
像素 QC 可暖复用，但来源/工作流状态仍每轮核验；状态或工作流问题变化时同步磁盘报告，不保留旧 PASS。

RGBA 透明区与 `contain` 留白不强制变白；真实页底色透出，显式背景合成仍遵循原声明。
`crop` 与编译/ghost 使用同一校验和几何（详见 contract）；这不是“图像解释关系正确”或适合当前叙事的自动判定。
PNG 损坏缓存重建、原子发布只保证工程完整性，不保证一张可解码图的来源事实与设计价值。
