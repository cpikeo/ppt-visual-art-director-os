# Production Contract（运行时契约 · 权威表）

三层各答一问：**Guard/QA** 判工程交付（能不能交付）；**Design Intelligence** 按需预测（非闸门）；
**设计价值**由人/AI 依 `design-craft.md` 判断（有没有设计价值）。同一事实只判一次。

## Contract Map（写 spec 前查表）

| 任务 | 契约（到此为止） |
|---|---|
| 文本 | `text` 放内容，样式平铺顶层（`size/color/bold/align/max_lines/line_height/padding`）；框高 ≥ 字号×行高×行数 |
| 填充 | `{"fill":{"type":"solid\|gradient\|none",...}}`；无效 fill 报编译错，不静默回退 |
| 图表数据 | 每行 `label` + 有限 `value`；数值图表必须齐 `source/unit/period/basis`（draft 记警告、release 阻断）；同 metric 同单位；标题写洞察 |
| 载荷 | schema 合法 ≠ 画得出来：数值/行数据图表必须有可画的行（含非空 `label`），`matrix` 要 `points`、`architecture` 要 `layers`、`kpi/executive_kpi/big_number` 要元素级 `value`；空载荷当场阻断（空白页不出门） |
| 空白 | `slides: []` 或「零元素且无 `background`」的页 = 空白交付物，阻断；有 `background` 的呼吸页合法 |
| 编译证据 | `semantic_compile_view` 是输入投影（判要不要重编）；`artifact/output_sha256` 是本次 PPTX 字节戳（判文件是不是它） |
| focus | 每页唯一 `page_intent.focus`；焦点 ≥40px 或领先第二大字 1.25×；落任一轴线（1/4·1/3·1/2·2/3·3/4·0.382/0.618） |
| 密度节奏 | sparse ≤0.60 / balanced 0.65–0.75 / dense 0.75–0.85（几何占用）；相邻同密度页墨迹差 ≥0.10 |
| 记忆锚点 | ≥40px 文本 / 图表 `highlight` / 环心 KPI / `target` 线 / sparkline / hero 图（图表内部大数字不算） |
| 图表论点 | 差异类主张别用等长条：零基长度编码 + 声明 `highlight`/`target` + max/min <1.25× → `chart_argument` 点名（差异不可见，换 waterfall / 共同基线 / 大数字） |
| 色彩 | 声明 `color_intent:[brand,emotion,hierarchy]`；Accent ≤5%（实测）；色相族 ≤4 |
| 网格 | 1280×720，8 单位自动吸附；`grid_exempt:true` 豁免 |
| 媒体 | 图须有功能（context/emotion/proof/hero）；数据/表格/流程/结构页不出图；背景画心免检需覆盖 ≥60% + 遮罩 ≥0.20 |
| 构图 | plan 每页给一条 `composition.grammar`（视线如何被组织）；这是**提案**，生成侧可整体推翻——它不给坐标、不给版式 |
| 资产 QC | 先 `assets --plan` 再出图，QC 记录清单与图片 SHA-256；retry/missing/block 均退出 2；有图稿件缺有效 QC 则不编译。详见 `asset-workflow.md` |
| 可读性 | 声明色：弱化字（muted / `chart_muted` 指向的 token，含元素里真拿 secondary 写字的）<3:1 提示、<1.8:1 警示；正文级 <4.5:1 与元素级预估走 `pre_critic` 风险项（建议，不阻断 release） |
| 风险策略 | 按需读 `forecast_risk`/`risk_strategy`；默认 QA 不运行建议 |
| 修订 | 照 `fix_plan` 根因组一轮批量改完（内嵌契约行，零回读）；一次改完再复跑同档 |
| 发布 | `--mode release`：门 = 0 阻断 + 有图资产链凭证 + 产品凭证 + 预览证据 + Manifest（`release_eligible`）；非阻断项只进 `warn_summary`；盖 `source_spec_hash` |

## Calls（最小 API）

入口与按需加载见 `SKILL.md`——本表只留字段与契约。
**元素字段、`chart_kind` 全表与每页上限、role 白名单 → `design-system.md` §Spec 字段速查**
（写 elements 前查它，不必回读 `compiler.py`）。

- `vao.py plan` → `pipeline.build_plan_bundle`：骨架只序列化**已决策字段**（canvas / theme 种子 /
  page_intent / source_zone，注释里附该页家族、叙事动作、构图语法提案），`elements` 留空——
  几何归生成侧判断，零预设；页数与 brief 的 slides 一一对应。deck 级事实（theme 种子、
  `direction_execution` 的介质/光照/图表手法）只在顶层出现一次，不逐页复制。
- `vao.py dna` → 经验记忆：`--check` 体检（结构问题点名到条目）/ `--add <条目>.json`
  （校验 id / signature.keywords / judgment 维度后原子写入）。`judgment` 只写行为判断，
  色值/字号/版式结果放 `proven.measurements`——写坏的记忆不报错，只会永远命不中。
- `vao.py check` → `qa.run_qa`（normalize → guard → compile → 判定）+ ghost 预览 + 分组修复包；
  全程单进程，不串行跑单脚本，不启动任何外部渲染器。

报告自足：`fix_plan.groups[]` 按根因码分组阻断项（`count/ids/samples/fix`，fix 内嵌本表契约行）；
修正轮照单一次改完，零回读。`warn_summary` 按 (domain,rule,level) 聚合非阻断项，只记录。

## 执行模式（三个已足够）

| 模式 | 做什么 | 产物 |
|---|---|---|
| `spec` | 归一化 + Guard 判定，不编译、不落产物 | 判定报告 |
| `draft`（默认） | Guard + Compile，产出可编辑 PPTX 与分组修复包 | PPTX + 报告 + `_vao/` 缓存 |
| `release` | draft 全部 + 数值图表出处硬门 + ghost 方向证据 + Release Manifest | PPTX + 报告 + 预览 + Manifest |

深度由任务赢得：简单内容 draft 即交付；复杂数据与终版收口才用 release。

## Spec minimum

```python
spec = {"canvas": {"width":1280,"height":720,"grid_columns":12,"grid_unit":8},
 "theme": {"colors":{...},"fonts":{"cn":...,"latin":...},"constraints":{...}},   # 方向种子照抄
 "strategy": {...}, "direction": {"color_intent": [...]},
 "slides": [{"id":"s01","page_intent":{...},
  "source_zone": {"x":48,"y":672,"width":1184,"height":32},
  "elements": [...]}]}
```

`theme.fonts` 只读 `cn`/`latin`（`display`/`body` 是别名）；未声明则回落 Arial / Microsoft YaHei 并被 `theme_fonts` 点名。
每页可带 `anchor`（跨页锚：`eyebrow`/`page_number`/`figure`）：落成 `role=eyebrow` / `role=page_number` /
`caption` 元素后，`deck_anchor` 会查存在性、位置恒定性与编号连续性；不声明则不查。

`theme.constraints` 是方向的数字种子（accent 面积 / 留白下限 / 字号级差 / 装饰面积 / 背景层 / 粗体占比）：
plan 发下来的原样照抄进 spec，guard 按它执法；写错键名同样被点名。
每页 `page_intent` 含 insight/focus/reading_order/energy/density/empty_space_role/page_family；
几何：所有可见对象数值 `x/y/width/height`；text–text / chart / image 墨迹相交即 `OVERLAP`
（来源区永不许遮挡）。图表标签放不下用 `label_collision_policy:hide_redundant|move_outside|fail`，
不缩字号。光源以外的字段（如幻灯级 `background`）不存在——写了也会被静默忽略，别写。

来源区内文字 `role` 只允许 `{source, method, metadata}`（页码/编号等挂 `metadata`/`label`）；
其他角色触发 zone-invasion 错误。图片必须用 `asset_id` 绑定清单；绑定阶段采用与 QC 相同的路径解析器，再交给编译器。
生成图片目录优先 `--assets-dir`，其次清单声明目录；既有素材路径由来源声明给出。

可读性与裁切（工程，不是品味）：① 单行 meta 行（眉标/章标/页码/落款）`wrap=False`
且盒宽 ≥1.5× 估宽——第二行落盒外的裁切是沉默的。② `page_intent.focus` 声明**视线第一落点**，
非叙事主语。③ 弱化字必须自证对比：声明色对底色 <3:1 会被点名（hint/warn，静态按声明色判定；亮度分级见 `design-system.md` 的 muted 行）。

图表色走语义角色（primary/secondary/neutral/accent/negative；元素 `color_role`；柱状负值自动染 negative）。
背景画心声明 `layer:background` + 自带 `overlay` 内容保护，不计媒体预算；资格不足按普通对象判。

## Failure codes

| 代码 | 状态 | 处理 |
|---|---|---|
| `OVERLAP` `SOURCE_COLLISION` `CHART_LABEL_COLLISION` `TEXT_OVERFLOW` `READABILITY_FAIL` `DATA_INTEGRITY_FAIL` `CHART_TYPE_FAIL` `COMPILE_FAIL` `GUARD_FAIL` `ASSET_WORKFLOW_FAIL` | BLOCKED | 必修：按 `fix_plan` 根因组一次改完 |
| 其他 warn/hint（`BG_UNPROTECTED`、节奏与对齐提示等） | PASS | 只进 `warn_summary`，不解释、不询问、不逐条修复 |

`guard.check_spec` 的返回只有 `passed / checks / advisory_rules / warnings / grid / line_measure`——
**没有 score**。验证层不评分、不排序、不评级：打分等于用固定阈值重新裁决设计好坏。

状态优先级：有阻断 → BLOCKED；spec 档 → PREVIEW_ONLY；0 阻断 → PASS（`release_eligible`
仅在 release 档、编译通过且所有发布凭证有效时为真）。**没有分数**——分数会把良性观察变成事实闸门。

## Release Manifest

`vao.py check --mode release` 生成：`source_spec_hash`、`validation`、`verification`
（外部渲染器状态 / 视觉证据类型 / 结构页数 / 预览页数 / `release_eligible`）、
`compile_report`（含 `output_sha256`）、`ghost_preview`、`revision_count` 与 `revision_log`、
`status`。清单校验三件事：报告盖的 spec 戳与当前 spec 一致；PPTX 字节戳与磁盘一致；
预览证据引用的页面都在当前 spec 里。口径以代码为真源。


## v5.1 资产前置契约

`ASSET_WORKFLOW_FAIL` 由 `vao.py check` 在编译前给出；修法是补齐/刷新证据链，
不是改字号或降低图像阈值。`spec` 模式同样校验有图稿件的资产依赖，但不编译。
纯文字/原生图形稿件记录 `SKIPPED / no_image_elements`，不是伪造“已检查”。

Release Manifest 增加 `asset_workflow`，记录 `status`、brief/plan/清单/QC 指纹和报告位置；
QC 本身包含每张图片的 SHA-256。验证失败时顶层与 verification 内的
`release_eligible` 均为 false。编译 PASS 不可代替完整流程 PASS。


## v5.1.1 发布一致性修复

- 以 auto_fit 后的有效 spec 同时编译、预览与盖指纹；不得各用一版输入。
- 图片采用核验 bytes 快照；预览必须有完整页 ID 及每个文件的 SHA-256。
- 有计划的稿件必须覆盖计划的全部页 ID/顺序，包括无图稿件。
- 每轮 check 分配 run_id；旧资格先失效，异常也写本轮失败报告。草稿不拥有发布资格。
- 文本容量检查覆盖 text 与 shape.text；禁止换行时同时检查宽度。静态估算不是 Office 字体像素证明。
- 数值图表 source/unit/period/basis 必须为非空白字符串，不能用空格或任意对象充当来源。
