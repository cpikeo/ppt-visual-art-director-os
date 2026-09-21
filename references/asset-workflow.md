# 资产生产与发布契约 · v6.5

## 1. 顺序与责任

**brief → plan → assets → 按清单出图 → 编排 → check（含资产 QC）→ release**

| 步骤 | 入口 / 执行者 | 产物 | 何时可继续 |
|---|---|---|---|
| 需求 | 作者 | brief | 主体/媒介/比例/留白明确 |
| 规划 | `vao.py run`（或 `plan`） | plan + 骨架 | brief 与计划绑定，骨架保留计划指纹 |
| 资产契约 | 同一次 `run` | 资产清单 | brief 与已保存计划一致 |
| 出图 | 外部生成工具 | 图像文件 | 按清单 prompt / negative / ratio / safe_area |
| 检查 | `vao.py check`（内部一步） | QC 报告 + SHA-256 | 全部 accept / accept_with_advisory |
| 编排 | 作者 + `check --mode draft` | 原生可编辑 PPT | 图片带 asset_id，资产链有效 |
| 发布 | `check --mode release` | PPT + 预览 + Manifest | 资产链/编译/来源/发布证据均有效 |

六层分工（同一张图只被问一次）：Design Intelligence（为什么需要）→ Design Craft
（有没有设计价值）→ Asset Contract（应该是什么，本文）→ Asset QC（工程条件）→
PPT Production Contract（能不能交付）→ Release Manifest（发布证据）。
图片工具不在本包；`assets` 不生成图像，只产出契约。

## 2. `run` 是标准生产入口

```bash
# 规划 + 资产契约一次调用
python scripts/vao.py run brief.yml --plan-out plan.json --skeleton build_deck.py \
    --assets-out asset_manifest.json --assets-dir generated_assets
# 出图后极速交付（推荐单命令直出）：
python scripts/vao.py make build_deck.py out.pptx --preview preview
# 或标准发布（release 含 Manifest 证据链）：
python scripts/vao.py check build_deck.py out.pptx --mode release --assets-manifest asset_manifest.json
```

```
vao.py：make（单命令直出）· run（标准入口）· plan / assets（单段重跑）· check（编译/验证/发布）
        · preview（ghost 联络表）· dna（设计记忆）
```

- Skill 层只暴露 `vao.py`，不逐个调底层模块；`run --assets-out` 不跨越外部出图暂停点。
- 轮次由资产数量/QC 状态/根因修订决定，不为凑轮次增加调用；R1/R3 各一次、一次收口。
- 迭代构图先 `check --mode draft`，终稿必须回 release。

**v6.5 引擎保护（实测回环归零）**：
- **骨架覆写保护**：`--skeleton` 目标若已填稿（elements 非空），新骨架改写
  同名加 `.new` 后缀的旁路文件 并提示，不覆盖作业稿。
- **稳定计划指纹**：`plan_sha256` 只含内容、不含时间戳；仅重跑 R1 不再使骨架失效。
- **既有字节自动登记**：prepare 时约定路径已有字节的规划资产，自动转为
  `decision=existing`（`origin: {kind: original, source: 自动登记…}`），保留规划
  asset_id / prompt / negative；QC 照常像素核验。不再出现「出图 → 阻断 → 补登记」回环。

## 3. 生成、既有、无图三条路径

职责两行：资产只承担视觉叙事；PPT 原生对象承担信息。图片不烘焙正文/图表/Logo。

角色与用途两轴（不互相推导、不新增组合枚举）：`asset_role`＝是什么
（background 建立空间 / illustration 表达对象 / hybrid 兼有）；`asset_function`＝
为什么（hero/proof/emotion/context/frame/separate）；`asset_subject`＝出现什么；
deck 级 `background_scene`＝页面背景世界，不回答「这张图是什么」。

| 判断项 | Background | Illustration |
|---|---|---|
| 职责 | 建立空间 | 表达对象 |
| 密度/主体 | 低 / 不要求 | 可中高 / 通常明确 |
| 文字关系 | 让空间 | 建立构图关系 |
| 裁切 | 可大幅 | 主体谨慎 |
| QC 重点 | 可读性/连续/负空间 | 主体完整/识别度/位置 |
| 默认风险 | 抢文字 | 抢主结论 |

编排落点：`asset_role: background` 由 `layer: background` + overlay/content_protection
（或显式 `readability_exempt`）+ 覆盖 ≥60% 承担免检；illustration/hybrid 按具象主体
判定；插图安全区纹理密度为 advisory。`asset: required` ≠ 必须做主体图；看到
required 就自动塞图是禁止做法。

**清单作业上下文只要十个字段**：`asset_id / slide_ids / decision / asset_role /
prompt / negative / ratio / safe_area / expected_filename / status`
（`asset_role_source` 记 declared / legacy / assumed）。指纹与生产控制
（plan_sha256 / brief_sha256 / attempt / run_id / schema）由运行时保存，不围绕推理。
默认文件名 PNG；照片推荐同 stem JPEG。解析器先找确切 expected_filename，再试同
stem 的 png/jpg/jpeg/webp；多备选并存＝歧义，须明确文件名。

### 用户提供、图库、自制与复用

```yaml
asset_source:
  kind: provided  # provided | licensed | original | reuse
  path: images/tea.jpg
  source: "用户提供的产品照片；商业使用授权待核实"
```

相对 path 相对 brief 目录解析；`assets` 产生 `decision=existing` 主条目并记 origin；
跳过生成，仍须 QC。`source` 是来源声明，不是版权审核。复用过往生成图用 `kind: reuse`。

### 无图片

编排稿无 `type=image` 时报告 `{"status":"SKIPPED","reason":"no_image_elements",
"image_count":0}`；原生图表/文本/形状不算外部图片；无「忽略图片检查」开关。

## 4. 编排如何绑定

保留骨架 `asset_workflow.plan_sha256 / plan_path`；页面 ID 与顺序必须完整覆盖。
图片元素必须写清单内 `asset_id`（`src` 由绑定器设置，不得替换）；每个使用页 id 必须
在主条目 `slide_ids` 内；多页复用同一 asset_id。清单相对路径以清单目录为基准，
`--assets-dir` 相对 cwd；跨机器迁移须重新 plan/assets/QC 建立路径凭证。

## 5. 检查结果与退出码（retry 是根因驱动）

- `accept / accept_with_advisory` 才通过；亮度平衡等建议不阻断。
- `retry`＝仍需重出，返回 2。路径：失败 → 根因判断（prompt/subject/构图/requirement）
  → 一次根因修正 → 重新 QC。`retry_budget` 是控制上限，不是设计输入；不做原样重试循环。
- draft 最多建议一次定向重出；重出后 `attempt=1` 并重 QC（旧指纹失效）。
- 缺图/解码失败/flag/block/流程不一致同样返回 2；`check` 在编译前验资产链，不过不编译。
- QC 默认找清单同目录 `asset_manifest.qc.json`，或 `--asset-qc-report` 指定。

`ASSET_WORKFLOW_FAIL` 聚合：无清单/无有效 QC、待重试、未知 asset_id、未登记使用页、
图片字节变化、清单或计划过期、brief 不一致、绑定路径不一致。修复＝刷新证据链，
不是降阈值或删来源。

## 6. 哪些修改会使证据失效

| 修改 | 要重做什么 |
|---|---|
| 改 brief 内容/主体/比例/留白 | plan → assets → 必要时重出图 → QC；骨架指纹自动同步 |
| 手动改 plan | assets → 必要时重出图 → QC |
| 改清单 prompt/negative/filename/slide_ids/attempt | 重新 QC；语义变了还须重出图 |
| 改或重压缩图像 | 重新 QC |
| 只改 PPT 文本/原生图表 | 重新 check；资产证据仍有效 |
| 新增图片或复用页 | 先入计划/清单再 QC，不许绕过 asset_id |

编译与预览消费核验时捕获的不可变字节；Manifest 记核验版本哈希，源文件后变须重 QC。
`status=BLOCKED` 时 `release_eligible` 两层均 false；旧输出留在磁盘不代表本轮成功——
读退出码、run_id 与 Manifest。

## 7. 证据边界：Asset Integrity ≠ Design Quality

QC 只回答 Integrity（是不是被检查过的那张图：存在/可读/尺寸/比例/SHA-256/绑定/
清单一致/链完整），不回答 Design Quality（好不好：主体/构图/留白/光线/契合/叙事——
归 Intelligence 与 Craft 加人眼）。QC 永远不加 artistic/beauty/premium 评分。
角色只改变问哪几个问题：背景查可读/连续/负空间（不做主体裁切判定）；插图查主体
完整/识别/位置（安全区密度 advisory）。判据跟着承诺走，阈值不因角色放宽。
本工具核对本地哈希与实查字节，不提供防篡改签名、不监控外部服务、不证明授权；
对外只能声称「资产链校验通过」。

## 8. 最低校验与兼容性

- QC 报告 schema `vao-asset-qc-v3`；旧报告须重跑，不得只改名称。
- brief 指纹按字节复核；QC/发布阶段不重新执行 Python brief。
- 图片短边 ≥32px；计划比例偏差 ≤5%；裁切需求声明 `asset_allow_crop: true`。
- crop 后至少满足落位 1× 像素（1% 容差）；摄影建议 2× 交付。
- Alpha 图先按计划背景合成；全透明阻断，可见透明 Logo/图形合法。
- 生成文件 resolve 不得离开生成根目录（含符号链接）；existing 显式外部文件不受限。
- 预览复用核对每页与总览字节；缺失或变更即重建。
