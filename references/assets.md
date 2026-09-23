# Assets（资产必要性 · 提示词 · QC）

资产决策不等于填图。图片工具不在本包：`vao.py plan --assets-out` 产出契约，
外部工具按契约出图，`check` 完成 QC 与链核验。

## 1. 必要性测试（先答这个，再谈风格）

**没有这张图，这一页会下降在哪里？** 只有两种答案成立：

| 答案 | 什么时候成立 |
|---|---|
| **witness（证词）** | 内容里有可指认的人 / 现场（回访、记录、课堂、车间…），且这一页靠「确有其事」成立 |
| **subject（主语）** | 开场建立世界：这一副讲的是**实体世界**（材质 + 光本身是内容），或在场的存在 |

答不出来的：**不出图**。装饰图、氛围图、无意义背景一律过不了这道测试；
页内已有图表（视觉锚点被占用）→ 媒体预算归零（双焦点竞争）；
纯信息/数据页（没有可指认的现场）→ 不出图，注意力归数字与排版。
**作者声明永远压过判断**：逐页 `asset: required|reuse|none`，或写 `asset_subject` 即视为要出图。

**图位按视觉价值分配，不按页序截断**：qualified 的页按 证词 > 建立 > 其余角色 排序取前
`cap` 张（fast=2 / advanced=4）；落选页在清单里留下理由（`assets_hint.deferred`）。

## 2. 四步落笔

```
需要资产吗 → 它是空间还是对象 → 它为什么存在 → 画面里究竟出现什么
（必要性）   （asset_role）      （asset_function） （asset_subject / material / lighting）
```

| 判断项 | background（建立空间） | illustration（表达对象） |
|---|---|---|
| 密度 / 主体 | 低 / 不要求 | 可中高 / 通常明确 |
| 文字关系 | 让空间 | 建立构图关系 |
| 裁切 | 可大幅 | 主体谨慎 |
| QC 重点 | 可读性 / 连续 / 负空间 | 主体完整 / 识别度 / 位置 |
| 默认风险 | 抢文字 | 抢主结论 |

**介质与材质分离**：`medium: photography` 决定写实摄影纪律；`material: rice paper`
只描述表面与触感，不会把摄影变成水墨。只有作者明确选择 ink-wash / sumi-e / 水墨时，
才进入水墨生成纪律。

## 3. 顺序与责任

```
brief → plan（--assets-out 产出清单）→ 按清单出图 → 编排 → check（QC + 链核验）→ release
```

清单条目字段：`asset_id / slide_ids / decision / asset_role / prompt / negative /
ratio / safe_area / expected_filename / status`。默认 PNG；照片推荐同 stem JPEG
（q92 4:4:4），落位按 2× 交付。解析器先找确切文件名，再试同 stem 的 png/jpg/jpeg/webp；
多备选并存 = 歧义，须明确文件名。

## 4. 视觉世界从哪来

提示词里的材质、光、动势、微浮雕由**视觉世界**给出（`intelligence.derive_world`：
受众语域 × 内容里的主题实体 × 证据形态）。没有风格预设表可查，也没有
「页面家族 → 材质」的映射：材质属于内容，不属于风格名。作者逐页写的
`material / lighting / texture` 逐字生效，压过世界推导。

- 光：世界给方向与质感；`energy: low|high` 只追加一句强弱，不追加同义句。
- 动势：`still`（默认）/ `reveal` / `spatial`——全套 ≤2 种。
- 微浮雕：一材质句 + 两句纪律（微弱、近距离才可感知；无图案、无 grunge）。

## 5. 三条路径

| 路径 | 做法 |
|---|---|
| **生成** | 按清单 prompt / negative / ratio / safe_area 出图；QC 按实际像素判定 |
| **既有素材** | `asset_source: {kind: provided\|licensed\|original\|reuse, path, source}`；跳过生成，仍须 QC |
| **无图** | `decision: none`；注意力属于内容本身——排版、留白与数字承担这一页 |

## 6. QC 与核验

- QC 只判物理事实：安全区是否被纹理压到文字、对比是否够、主体是否完整、
  比例是否匹配（不符需裁切时显式 `asset_allow_crop: true`）、有效分辨率是否低于落位尺寸。
- 判定按「像素预算 + 判定实现」复用：同清单 + 同像素口径 + 同字节身份 ⇒ 不重测。
- 资产链核验：每张图 = QC 通过的那张 + 绑到正确的页 + 分辨率够 + 文件未被替换。
- `draft` 档坏图最多一次定向重出；`release` 档坏图直接 BLOCK（不为失败的稿子背书）。
