# Production Contract（运行时契约 · 权威表）

同一事实只判一次：

| 层 | 核心问题 | 是否阻断 |
|---|---|---|
| Contract / Guard | 文件/数据/结构正确、可编译、无溢出碰撞、资产链完整 | 是（10 个阻断码） |
| 留痕 / Risk | 可读性/节奏/图表论点风险 | 否（只进 `trace_summary`） |
| Intelligence / Craft | 审美、构图、节奏、应不应该这么设计 | 不属于 Contract |

**验证层不评分**：`guard.check_spec` 没有 score，不排序不评级；只查工程事实与作者自己写下
的数字（`constraints`）。审美不进门槛，也不以提示回灌作者。

## Contract Map（写 spec 前查表）

### 硬门（阻断）

| 任务 | 契约 |
|---|---|
| 文本 | 内容进 `text`，样式平铺顶层；框高 ≥ 字号×行高×行数（`TEXT_OVERFLOW`） |
| 填充 | Fill Contract；无效 fill 报编译错，不静默回退（`COMPILE_FAIL`） |
| 墨迹 | text–text/chart/image 相交即 `OVERLAP`；来源区永不许遮挡（`SOURCE_COLLISION`）；图表标签冲突走 `label_collision_policy`（`CHART_LABEL_COLLISION`），不缩字号 |
| 图表数据 | 每行 label + 有限 value；数值图齐 `source/unit/period/basis` 非空（draft 警告、release 阻断）；同 metric 同单位（`DATA_INTEGRITY_FAIL`） |
| 载荷 | schema 合法 ≠ 画得出来：行数据图须有可画行；`matrix` 要 points、`architecture` 要 layers、数字展示要元素级 value；空载荷阻断 |
| 空白 | `slides: []` 或零元素且无 background 的页阻断；有 background 的呼吸页合法 |
| 图表类型 | 白名单内且数据形态匹配（`CHART_TYPE_FAIL`） |
| 元素合法性 | schema / focus 唯一 / 几何合法（error 级归 `GUARD_FAIL`） |
| 资产链 | 先 assets 再出图，QC 记 SHA-256；retry/missing/block 退出 2；有图缺有效 QC 不编译（`ASSET_WORKFLOW_FAIL`）。详见 `asset-workflow.md` |
| 编译与发布 | `semantic_compile_view` 判要不要重编；`output_sha256` 判文件是不是它；release 门 = 0 阻断 + 资产链凭证 + 预览证据 + Manifest |

### 留痕信号（只留痕，不阻断，不逐条修复）

| 信号 | 度量 | 等级 |
|---|---|---|
| 密度节奏 | 枚举合法性才是工程事实；占用带实测只作参考 | `rhythm`（hint） |
| 色彩 | 色相族上限＝`constraints` 声明数字的执法，未声明不检查 | `palette_discipline` |
| 图表论点 | 差异主张 + 零基长度编码 + highlight/target + max/min <1.25× = 差异不可见 | `chart_argument`（warn） |
| 可读性 | 声明色弱化字 <3:1 提示、<1.8:1 警示；正文级 <4.5:1 是 `READABILITY_FAIL` 硬门 | `contrast` |
| 背景保护 | 全幅背景免检资格：`layer:background` + overlay ≥0.20 + 覆盖 ≥60% | `BG_UNPROTECTED` |
| 媒体策略 | 数据/表格/流程/结构页不出图 | route 媒体政策 |
| 网格 | 8 单位吸附（≤2px 或通栏豁免）；`grid_exempt:true` 豁免 | `grid` |

构图：plan 每页给 `composition.grammar` 提案——不给坐标版式，生成侧可整体推翻。
修订：照 `fix_plan` 根因组一轮批量改完（fix 内嵌契约行，零回读），一次改完再复跑。

### 速度档

| 项 | `--speed fast`（默认） | `--speed strict` |
|---|---|---|
| 资产 QC 像素域 | 长边 ≤1024 降采样；文字安全区纹理按原分辨率 | 全分辨率 |
| 图片读取/解码 | 每张各一次；QC 已解码底图经 `decode_seed` 供核验/编译/预览复用 | 同 |
| 图片变换 | 同图同盒一次；无变换透传原字节 | 同 |
| 编译缓存探测 | size+mtime 快探针；两档分域不跨档复用 | 整包 SHA-256 |
| 方向预览 | 页数 ≤`--ghost-pages`（默认 24，常规 deck 自动全量）时全量，否则采样；单倍采样 + 低压缩 | 全 deck 逐页；2× 超采样 |
| 包级后处理 | 媒体 STORED，XML DEFLATE | 同 |

判定口径两档完全相同（同一 check_spec、同一阈值、同一阻断码）；差异只进证据字段
（`pixel_profile` / `preview.scope` / `attestation_mode` / `verification.{speed,scope}`）。

`--deadline`（秒，默认 120，0/None 不设限）：核心阶段（资产核验→guard→编译→收口）永远
执行；可选证据（预览/contact sheet）预算不足时跳过并记 `budget.skipped`。release 档缺预览
证据即 BLOCKED（fail-closed）——超预算只得到诚实结论，不得到超时交付。

## Calls（最小 API）

元素字段、`chart_kind` 全表与 role 白名单 → `design-system.md` §Spec 字段速查。

- `plan`：骨架只序列化已决策字段（canvas/theme 种子/page_intent/source_zone + 注释里的
  家族/密度/媒体/构图判断项），`elements` 留空——几何归生成侧，零预设；deck 级事实只在
  顶层出现一次。
- `dna`：`--check` 体检 / `--add <条目>.json` 原子写入；`judgment` 只写行为判断，结果数字
  放 `proven.measurements`。
- `check`：normalize → guard → compile → `qa.verdict`（只读报告）+ ghost 预览 + 分组修复包；
  单进程，不串行脚本，不启动外部渲染器。

`fix_plan.groups[]` 按根因码分组（count/ids/samples/fix）；`trace_summary` 按
(domain,rule,level) 聚合非阻断项，只记录。

## 执行模式（三个已足够）

| 模式 | 做什么 | 产物 |
|---|---|---|
| `spec` | 归一化 + Guard，不编译 | 判定报告 |
| `draft`（默认） | Guard + Compile | PPTX + 报告 + 缓存 |
| `release` | draft 全部 + 出处硬门 + ghost 证据 + Manifest | PPTX + 报告 + 预览 + Manifest |

## 方向预览的覆盖契约

ghost 是**预览**，不是第二个渲染器。两条纪律：
1. **宽容度 ≤ 交付链**：预览认的键名/类型/载荷不得比 guard/compiler 更宽——写错的键在
   预览里也必须是「画不出来」，证据不替错误背书。
2. **自信度 ≤ 实现程度**：只画与产物同形的图形；没实现同形几何的类型如实写
   「不渲染此图形 · 以编译产物为准」，不画一个大概。

类型归属覆盖 `primitives.CHART_KINDS` 全集，两种归宿：`ghost.PREVIEW_MIRRORED`
（同形镜像：原生图表族 + 数字行/步/轴/瀑布/柱族 + 矩阵象限）与 `ghost.PREVIEW_ABSTRACT`
（流程/架构/气泡——空间关系是价值，粗近似会误导）。加一种图先回答它在预览里怎么活。
预览**不构成 QC**：release 门只认「预览证据存在且范围如实」。

## 图表表达的执行层默认值（Editorial Data）

「数据是主角、装饰让位」：少颜色、少边框、少网格，层级靠明度。以下为引擎已保证的事实
（离线图表审计可复算）：

| 事实 | 口径 |
|---|---|
| 无外框/无网格/无轴线 | chartSpace/plotArea 不描边；主次网格删除；轴 `line.fill.background()` |
| 无图例 | 读数责任交给直接标注（值标签默认开） |
| 高亮只有一个 | 高亮 = accent；只有被指定那根换色 |
| 负值只在声明时着色 | 主题无 negative 一律中性 |
| 系列色不重复 | 单信号色主题 = accent 起的同色相明度阶梯（相邻明度差 ≥0.05） |
| accent 只占一个位置 | `ctx.series_palette(count, highlight)` 一处派生，编译器与预览共用 |
| 预览不发明装饰 | 同形镜像不画产物没有的外框；扇区/段色与产物同一份派生 |

作者仍可覆盖：`gap_width / show_values / highlight / series_roles / series / theme.chart_palette`。
已知边界：多序列折线末端只画圆点不落序列名；>6 档序列复用色阶；`multi_color/ramp` 下
预览只镜像默认调色板。

## Spec minimum

```python
spec = {"canvas": {"width":1280,"height":720,"grid_columns":12,"grid_unit":8},
 "theme": {"colors":{...},"fonts":{"cn":...,"latin":...},"constraints":{...}},
 "strategy": {...}, "direction": {"color_intent": [...]},
 "slides": [{"id":"s01","page_intent":{...},
  "source_zone": {"x":48,"y":672,"width":1184,"height":32},
  "elements": [...]}]}
```

`theme.fonts` 只读 cn/latin；未声明回落 Arial / Microsoft YaHei 并被 `theme_fonts` 点名。
每页可带 `anchor`（eyebrow/page_number/figure）：落成对应 role 元素后 `deck_anchor` 查
存在性/位置恒定/编号连续；不声明不查。`theme.constraints` 是方向数字种子，plan 发下来
原样照抄，guard 按它执法，写错键名被点名。光源以外的幻灯级字段不存在——写了被静默忽略。
来源区 role 只允许 `{source, method, metadata}`。图片必须 `asset_id` 绑定清单，解析器与 QC
同一路径。生成图目录优先 `--assets-dir`；既有素材路径由来源声明给出。

可读性与裁切（工程，不是品味）：① 单行 meta 行 `wrap=False` 且盒宽 ≥1.5× 估宽——第二行落
盒外的裁切是沉默的；② `focus` 声明视线第一落点，非叙事主语；③ 弱化字对比 hint/warn 分级。
图表色走语义角色；背景画心 `layer:background` + 自带 overlay 不计媒体预算，资格不足按普通
对象判。

## 资产 QC 的两条语义

| 判据 | 语义（以代码常量为准） |
|---|---|
| `brightness_balance` | 相对声明底色：与 `background_color` 亮度差 < 0.18 = 同调，不判过暗/过亮；落差够大才报可见分块。左右/上下失衡照常判。文字可读性归 `contrast_suitability` |
| `contrast_suitability` | 按声明文字色判定：`#RRGGBB` 或 dark/light 都认（解析唯一实现 `primitives.text_is_dark`）；浅字要求安全区暗（<0.45）、深字要求亮（>0.55）；没声明才退回中间带（阻断级） |

既有素材登记：早于清单存在的字节可在 slide 写 `asset_source` 显式登记；v7.0.0 起 prepare 时
字节已存在的规划资产**自动如实登记为 existing**（保留规划身份与 prompt，见
`asset-workflow.md` §2）。

## Cold / Hot 与运行时事实

一次 `check` 只产一份运行时事实账本（`result.evidence`）：身份/读数/复用与降级原因；
报告、发布清单、预览证据都从账本取数。

| 路径 | 步骤 | 含义 |
|---|---|---|
| COLD | identity → measure → evidence → compile → render | 重新建立事实 |
| HOT | identity → evidence → release | 只取已有事实（不测量/编译/渲染） |

复用必须带凭证（资产判定/产物/预览各自的摘要+指纹+字节凭证）；凭证不足落回 COLD 并在
`evidence.cold_reasons` 写明，不许静默重做。同一事实只有一个身份，全部由 `primitives.py`
身份层产出。新增步骤的准入问题：**属于 COLD 还是 HOT；为什么 HOT 需要重做。**

## Failure codes

| 代码 | 状态 | 处理 |
|---|---|---|
| `OVERLAP` `SOURCE_COLLISION` `CHART_LABEL_COLLISION` `TEXT_OVERFLOW` `READABILITY_FAIL` `DATA_INTEGRITY_FAIL` `CHART_TYPE_FAIL` `COMPILE_FAIL` `GUARD_FAIL` `ASSET_WORKFLOW_FAIL` | BLOCKED | 按 `fix_plan` 根因组一次改完 |
| 其他 warn/hint | PASS | 只进 `trace_summary`，不解释、不询问、不逐条修复 |

`guard.check_spec` 返回只有 passed/checks/warnings/grid——没有 score，也不恢复 score。
状态优先级：有阻断 → BLOCKED；spec 档 → PREVIEW_ONLY；0 阻断 → PASS（`release_eligible`
仅 release 档、编译通过且发布凭证全有效时为真）。

## Release Manifest

`check --mode release` 生成：`source_spec_hash`、`validation`、`verification`（外部渲染器
状态/视觉证据类型/结构页数/预览页数/release_eligible）、`compile_report`（含 output_sha256）、
`ghost_preview`、`revision_count/log`、`status`。校验三件事：报告盖的 spec 戳与当前一致；
PPTX 字节戳与磁盘一致；预览证据引用的页面都在当前 spec 里。

## 资产前置与发布一致性（仍有效）

`ASSET_WORKFLOW_FAIL` 在编译前给出；修法是补齐/刷新证据链，不是改字号或降图像阈值。
`spec` 模式同样校验资产依赖但不编译。纯原生稿件记 `SKIPPED / no_image_elements`，不伪造
「已检查」。Release Manifest 的 asset_workflow 记 status 与 brief/plan/清单/QC 指纹；QC 含
每图 SHA-256。验证失败时两层 release_eligible 均 false；编译 PASS 不可代替完整流程 PASS。

- 以作者交付的那一版 spec 同时编译、预览与盖指纹；验证不改写 spec。
- 图片采用核验 bytes 快照；预览必须有完整页 ID 及每文件 SHA-256。
- 有计划的稿件必须覆盖计划全部页 ID/顺序，包括无图稿件。
- 每轮 check 分配 run_id；旧资格先失效，异常也写本轮失败报告；草稿不拥有发布资格。
- 文本容量检查覆盖 text 与 shape.text；禁止换行时同时检查宽度。静态估算不是 Office 字体像素证明。
