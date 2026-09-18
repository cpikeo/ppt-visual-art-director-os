# 资产生产与发布契约 · v5.1

## 1. 顺序与责任

**brief → plan → assets → 按清单生成图片 → asset-qc → PPT 编排 → release**

| 步骤 | 入口 / 执行者 | 产物 | 何时可继续 |
|---|---|---|---|
| 需求 | 作者 | brief | 明确主体、媒介、比例、构图与文字留白 |
| 规划 | `vao.py plan` | plan + 编排骨架 | brief 与计划绑定，骨架保留计划指纹 |
| 资产契约 | `vao.py assets --plan` | 资产清单 | 当前 brief 与已保存计划一致 |
| 出图 | 外部生成工具 / 执行者 | 图像文件 | 按清单提示词、负向提示词、比例与安全区生成 |
| 检查 | `vao.py asset-qc` | QC 报告 + 图片 SHA-256 | 全部资产 accept 或 accept_with_advisory |
| 编排 | 作者 + `vao.py check --mode draft` | 原生可编辑 PPT | 图片带 asset_id，资产链有效 |
| 发布 | `vao.py check --mode release` | PPT + 方向预览 + Manifest | 资产链、编译、来源与发布证据均有效 |

图片工具不在本包中。`assets` 不会自动生成图像，它在单一入口内部调用
`asset_prompt.build_asset_prompt`。执行者必须将输出提示词交给真实生成工具。
不得将“我手写了提示词”描述为“我调用了 asset_prompt”。

## 2. 最短完整命令

```bash
python scripts/vao.py plan brief.yml --out plan.json --skeleton build_deck.py
python scripts/vao.py assets brief.yml --plan plan.json --out asset_manifest.json --assets-dir generated_assets
# 外部工具按清单批量出图；完成后再运行：
python scripts/vao.py asset-qc asset_manifest.json --phase draft
# 填充骨架：图片元素必须带 asset_id
python scripts/vao.py check build_deck.py out.pptx --mode draft --assets-manifest asset_manifest.json
python scripts/vao.py check build_deck.py out.pptx --mode release --assets-manifest asset_manifest.json
```

`run --assets-out` 只是合并“规划 + 资产准备”，不会跨越外部出图/QC暂停点。
不得与 `--build` 同时使用。`run --build` 检查已编排稿，不会重写已有计划。

## 3. 生成、既有、无图三条路径

### 新生成图片

brief 的 slide 可写 `asset_subject / medium / asset_ratio / asset_function /
negative_space_anchor / safe_area / text_color / negative`。先据此规划，后产生清单。
图像不要烘焙正文、图表或 Logo；可编辑文本仍由 PPT 原生对象承担。

清单主条目包含 `asset_id`、`slide_ids`、`decision=generate`、`prompt`、`negative`、
`ratio`、`safe_area`、`expected_filename`、`retry_budget`。
默认文件名可为 PNG；照片推荐同 stem 的 JPEG。QC 与编排使用同一个解析器：
先找确切 expected_filename；不存在时尝试同 stem 的 png/jpg/jpeg/webp，
多个备选并存视为歧义，须明确文件名。

若准备清单时约定路径已有图片，会记录其指纹。该图片原样进入 QC 将阻断，
应登记为既有复用，不得将补写的清单伪装为先出计划后生成。
这只能发现约定路径的既有字节，不能发现所有目录中的历史图像，也不能阻止伪造日志。

### 用户提供、图库、自制与复用

在对应 slide 中声明：

```yaml
asset_source:
  kind: provided  # provided | licensed | original | reuse
  path: images/tea.jpg
  source: "用户提供的产品照片；商业使用授权待核实"
```

相对 path 相对 brief 所在目录解析。`assets` 产生 `decision=existing` 主条目，
记录 origin；跳过生成，但仍须 QC。`source` 是来源声明，不是本工具完成了版权审核。
复用过往生成图请用 `kind: reuse`，说明原出处及已知授权状态。

### 无图片

当编排稿没有 `type=image`，不要求清单与 QC，报告记录：

```json
{"status":"SKIPPED","reason":"no_image_elements","image_count":0}
```

原生图表、文本和形状不视为外部图片。不提供“忽略图片检查”的通用开关。

## 4. 编排如何绑定

保留 plan 生成的骨架中的 `asset_workflow.plan_sha256`。图片元素例如：

```python
{"id": "hero", "type": "image", "asset_id": "从清单复制的实际ID",
 "x": 720, "y": 112, "width": 480, "height": 480,
 "fit": "cover", "asset_function": "emotion"}
```

`src` 由绑定器设置，不能用其他文件路径替换。每个图片出现的 slide id 必须在
该主条目的 `slide_ids` 中。多页复用同一个 asset_id；复用标记不得遮蔽主条目文件信息。

清单路径记录相对目录时，以清单所在目录为基准；CLI `--assets-dir` 相对当前工作目录。
绝对路径可用于本地执行。项目迁移到另一台机器时，重新 plan/assets/QC 以建立当前路径凭证；
不要把旧机器路径错误地当成文件缺失或已验证。

## 5. 检查结果与退出码

- `asset-qc`: `accept / accept_with_advisory` 才通过；亮度平衡等建议不阻断。
- `retry` 表示仍需重出，不是通过；返回 2。完成重出后重新 QC。
- 缺图、解码失败、flag、block 或流程不一致同样返回 2。
- draft 最多建议一次定向重出；重出后将清单条目 `attempt` 置为 1，并重新 QC。
  修改 attempt 也会使旧 QC 指纹失效。
- `check` 各档在编译之前检查有图项目的资产链；不通过就不执行本轮编译。
- 自定义 QC 路径：`asset-qc --out` 与 `check --asset-qc-report` 配套使用。

以下情况以 `ASSET_WORKFLOW_FAIL` 聚合报告：无清单/无有效QC、待重试、未知asset_id、
未登记的使用页、图片字节变化、清单或计划过期、brief不一致、绑定路径不一致。
错误修复是刷新对应证据链，不是降低质量阈值或删除来源。

## 6. 哪些修改会使证据失效

| 修改 | 要重做什么 |
|---|---|
| 改 brief 中的内容、主体、比例、留白 | plan → assets → 必要时重新出图 → QC；更新骨架计划指纹 |
| 手动修改 plan | assets → 必要时重新出图 → QC；更新骨架计划指纹 |
| 修改清单 prompt / negative / filename / slide_ids / attempt | 重新 QC；提示词语义改变时还须重新出图 |
| 修改或重压缩图像文件 | 重新 QC，确保当前字节是被检查的版本 |
| 修改 PPT 文本 / 原生图表，计划与图片不变 | 重新 check；资产证据仍有效 |
| 新增图片或新增复用页 | 先纳入计划/清单，再 QC，不允许绕过 asset_id |

发布 Manifest 中资产链与 PPT 字节凭证是不同的两份证据；一份不能替代另一份。
`status=BLOCKED` 时，两层 `release_eligible` 均必须为 false。旧输出文件可能仍留在磁盘，
不要仅按“目录里存在PPT”判断本轮成功；应读取本轮退出码和 Manifest。

## 7. 证据边界

本工具核对的是本地内容哈希、已保存依赖关系以及实际检查的图像字节。
它不提供防篡改签名、不监控外部生成服务，也不能自动确认 prompt 的语义是否完全被遵守、
图片是否有足够艺术价值或来源是否真的授权。时间戳用于审计，不当作防伪或文件来源证明。
对外只能声称“资产链校验通过”，不能声称“工具证明了所有外部生成行为”。
