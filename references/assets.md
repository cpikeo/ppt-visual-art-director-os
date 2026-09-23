# Assets（资产生产与发布契约）

资产决策不等于填图。图片工具不在本包；`vao.py plan --assets-out` 产出契约，
外部工具按契约出图，`check` 内部完成 QC 与链核验。

## 1. 媒体判断（决策在前）

按以下顺序判断，一页只问一次：

```
需要资产吗？ → 它是空间还是对象？ → 它为什么存在？ → 画面中究竟出现什么？
```

- **必要性**由规划层给出判断（置信度 + 理由，可推翻）：数据/结构/流程/对比/证据页
  注意力属于内容本身，再叠图 = 双焦点竞争；封面/收尾/叙事页画心承担第一印象。
  页内已有图表（视觉锚点被占用）→ 媒体预算归零。
- **作者声明永远压过判断**：逐页 `asset: required|reuse|none` 或写 `asset_subject`
  即视为要出图；声明不被预算截断、不被质量档改写。
- 两轴不互相推导、不发明组合枚举：`asset_role`＝是什么（background 建立空间 /
  illustration 表达对象 / hybrid 兼有）；`asset_function`＝为什么存在
  （hero/proof/emotion/context/frame/separate）；`asset_subject`＝出现什么；
  deck 级 `background_scene`＝页面背景世界，不回答「这张图是什么」。

| 判断项 | Background | Illustration |
|---|---|---|
| 职责 | 建立空间 | 表达对象 |
| 密度/主体 | 低 / 不要求 | 可中高 / 通常明确 |
| 文字关系 | 让空间 | 建立构图关系 |
| 裁切 | 可大幅 | 主体谨慎 |
| QC 重点 | 可读性/连续/负空间 | 主体完整/识别度/位置 |
| 默认风险 | 抢文字 | 抢主结论 |

`asset: required` ≠ 必须做主体图；看到 required 就自动塞图是禁止做法。
一页被标记为 advanced，不代表它必须有照片。

**介质与材质分离**：`medium: photography` 决定写实摄影纪律；`material: rice paper / 宣纸`
只描述表面与触感，不会把摄影变成水墨。只有作者明确选择 ink-wash / sumi-e / 水墨时，
才进入水墨生成纪律（单笔意笔触、干笔渐变、过半纸地留白、三到四墨阶）。

## 2. 顺序与责任

```
brief → plan（--assets-out 产出清单）→ 按清单出图 → 编排 → check（QC+链核验）→ release
```

| 步骤 | 执行者 | 产物 | 何时可继续 |
|---|---|---|---|
| 需求 | 作者 | brief | 主体/媒介/比例/留白明确 |
| 规划 | `vao.py plan` | plan.json + 骨架 + 资产清单 | brief 绑定 |
| 出图 | 外部生成工具 | 图像文件 | 按清单 prompt/negative/ratio/safe_area |
| 检查 | `vao.py check`（内部一步） | QC 报告 + 字节凭证 | 全部 accept / accept_with_advisory |
| 发布 | `check --mode release` | PPTX + 预览 + Manifest | 资产链/编译/来源/证据均有效 |

清单作业上下文十个字段：`asset_id / slide_ids / decision / asset_role / prompt /
negative / ratio / safe_area / expected_filename / status`。
默认文件名 PNG；照片推荐同 stem JPEG（照片用 JPEG q92 4:4:4，不用 PNG；只有图形/
纯色/透明通道才用 PNG）。落位按 2× 交付。解析器先找确切 `expected_filename`，
再试同 stem 的 png/jpg/jpeg/webp；多备选并存 = 歧义，须明确文件名。

## 3. 生成、既有、无图三条路径

**既有素材登记**（用户提供 / 图库 / 自制 / 复用）：

```yaml
asset_source:
  kind: provided  # provided | licensed | original | reuse
  path: images/tea.jpg
  source: "用户提供的产品照片；商业使用授权待核实"
```

相对 path 相对 brief 目录解析；产生 `decision=existing` 主条目并记 origin；
跳过生成，仍须 QC。`source` 是来源声明，不是版权审核。
**自动登记**：prepare 时约定路径已有字节的规划资产，自动转为 existing
（保留规划 asset_id / prompt / negative；QC 照常像素核验）——
不再出现「出图 → 阻断 → 补登记」回环。

**无图片**：编排稿无 `type=image` 时 `{"status":"SKIPPED","reason":"no_image_elements"}`；
原生图表/文本/形状不算外部图片；无「忽略图片检查」开关。

## 4. 编排如何绑定

图片元素必须写清单内 `asset_id`（`src` 由绑定器设置，不得替换）；每个使用页 id 必须
在主条目 `slide_ids` 内；多页可复用同一 asset_id。清单相对路径以清单目录为基准，
`--assets-dir` 相对 cwd。跨页锚与来源区契约见 `contract.md`。

`asset_role: background` 由 `layer: background` + overlay/content_protection
（或显式 `readability_exempt`）+ 覆盖 ≥60% 承担免检；illustration/hybrid 按具象主体
判定。把插图当背景纹理铺底压字 = 角色说错。

## 5. QC 与退出码（retry 是根因驱动）

- `accept / accept_with_advisory` 才通过；亮度平衡等建议不阻断。例外：`brightness_balance`
  构成**亮度断崖**（画面与声明底色落差 ≥0.50 且画面落在极端区）时升级为阻断。
- `contrast_suitability` 按声明文字色判定：`#RRGGBB` 或 dark/light 都认；浅字要求
  安全区暗、深字要求亮；没声明才退回中间带（阻断级）。
- `retry` = 仍需重出（退出码 2）。路径：失败 → 根因判断（prompt/subject/构图）→
  **一次**根因修正 → 重新 QC。draft 最多建议一次定向重出；不做原样重试循环。
- 页面仍然不需要这张图时，删除它，让原生编排承担页面；不要继续消耗生成轮次。

## 6. 哪些修改会使证据失效

| 修改 | 要重做什么 |
|---|---|
| 改 brief 内容/主体/比例/留白 | plan → assets → 必要时重出图 → QC |
| 手动改 plan | assets → 必要时重出图 → QC |
| 改清单 prompt/negative/filename/slide_ids | 重新 QC；语义变了还须重出图 |
| 改或重压缩图像 | 重新 QC |
| 只改 PPT 文本/原生图表 | 重新 check；资产证据仍有效 |
| 新增图片或复用页 | 先入计划/清单再 QC，不许绕过 asset_id |

## 7. 证据边界：Asset Integrity ≠ Design Quality

QC 只回答 Integrity（是不是被检查过的那张图：存在/可读/尺寸/比例/字节凭证/绑定/
清单一致），不回答 Design Quality（好不好：主体/构图/留白/光线/契合——归 judgment
加人眼）。QC 永不加 artistic/beauty/premium 评分。角色只改变问哪几个问题；
判据跟着承诺走，阈值不因角色放宽。本工具核对本地哈希与实查字节，不提供防篡改签名、
不证明授权；对外只能声称「资产链校验通过」。
