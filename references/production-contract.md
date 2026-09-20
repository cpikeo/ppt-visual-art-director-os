# Production Contract（运行时契约 · 权威表）

分层切干净（同一事实只判一次）：

| 层 | 核心问题 | 是否阻断 |
|---|---|---|
| **Contract / Guard** | 文件正确、数据正确、结构正确、可编译、无溢出、无碰撞、资产链完整 | **是**（10 个阻断码） |
| **Advisory / Risk** | 可读性风险、节奏风险、焦点风险、视觉异常（`DESIGN_RULES` 留痕 + forecast 预测） | 否（只进 `trace_summary`） |
| **Intelligence / Craft** | 高级感、审美、构图、节奏、视觉价值、应不应该这么设计 | 不属于 Contract |

**验证层不评分**：`guard.check_spec` 没有 score，不排序、不评级。焦点尺度、密度节奏、
accent 面积、色相族、记忆锚点这类**设计代理指标全部是 advisory 或风险预测**——给作者的
线索，不是交付门。变化不是目的，必要性才是目的。

## Contract Map（写 spec 前查表）

### 硬门（阻断）

| 任务 | 契约（到此为止） |
|---|---|
| 文本 | `text` 放内容，样式平铺顶层（`size/color/bold/align/max_lines/line_height/padding`）；框高 ≥ 字号×行高×行数（`TEXT_OVERFLOW`） |
| 填充 | `{"fill":{"type":"solid\|gradient\|none",...}}`；无效 fill 报编译错，不静默回退（`COMPILE_FAIL`） |
| 墨迹 | text–text / chart / image 相交即 `OVERLAP`；来源区永不许遮挡（`SOURCE_COLLISION`）；图表标签冲突走 `label_collision_policy`（`CHART_LABEL_COLLISION`），不缩字号 |
| 图表数据 | 每行 `label` + 有限 `value`；数值图表必须齐 `source/unit/period/basis` 且为非空白字符串（draft 记警告、release 阻断）；同 metric 同单位（`DATA_INTEGRITY_FAIL`） |
| 载荷 | schema 合法 ≠ 画得出来：数值/行数据图表必须有可画的行（含非空 `label`），`matrix` 要 `points`、`architecture` 要 `layers`、`kpi/executive_kpi/big_number` 要元素级 `value`；空载荷当场阻断（空白页不出门） |
| 空白 | `slides: []` 或「零元素且无 `background`」的页 = 空白交付物，阻断；有 `background` 的呼吸页合法 |
| 图表类型 | `chart_kind` 白名单内且数据形态匹配（占比≠趋势，`CHART_TYPE_FAIL`） |
| 元素合法性 | element_schema / focus 唯一 / 几何合法性（error 级归 `GUARD_FAIL`） |
| 资产链 | 先 `assets --plan` 再出图，QC 记录清单与图片 SHA-256；retry/missing/block 均退出 2；有图稿件缺有效 QC 则不编译（`ASSET_WORKFLOW_FAIL`）。详见 `asset-workflow.md` |
| 编译与发布证据 | `semantic_compile_view` 是输入投影（判要不要重编）；`artifact/output_sha256` 是本次 PPTX 字节戳（判文件是不是它）；release 门 = 0 阻断 + 资产链凭证 + 预览证据 + Manifest |

### Advisory / Risk（只留痕，不阻断，不逐条修复）

| 信号 | 度量（代码常量为准） | 等级 |
|---|---|---|
| 焦点优先级 | focus 落在**文字**上才度量：它应拿到页内最大字号；焦点也可以是图像、留白、小数字——字号只是手段之一 | `focus_scale`（hint） |
| 密度节奏 | `sparse/balanced/dense` 是输入语义（枚举合法性才是工程事实）；占用带（`DENSITY_BANDS`）实测只是参考，不是「必须和上页不同」的义务 | `rhythm`（hint，仅声明与结构同时重复才发） |
| 色彩 | 色相族 ≤4（`max_colors`）= `constraints` 声明数字的执法，未声明不检查；值为什么存在在 Intelligence | `palette_discipline`（warn/hint） |
| 图表论点 | 差异主张 + 零基长度编码 + 声明 `highlight`/`target` + max/min <1.25× = 差异不可见 | `chart_argument`（warn） |
| 可读性 | 声明色弱化字 <3:1 提示、<1.8:1 警示；正文级 <4.5:1 是 `READABILITY_FAIL` 硬门 | `contrast`（hint/warn）；error 级才是 `READABILITY_FAIL` |
| 背景保护 | 全幅背景图免检资格：`layer:background` + `overlay` ≥0.20 + 覆盖 ≥60%（`BG_MIN_*`） | `BG_UNPROTECTED`（warn/hint） |
| 媒体策略 | 数据/表格/流程/结构页不出图 | route 媒体政策（plan 侧不派图）+ forecast `media_shortage`（plan 期预测） |
| 网格 | 8 单位自动吸附（任一维 ≤2px 或通栏豁免）；`grid_exempt:true` 豁免 | 对齐事实进 `grid`/`line_measure`，比率不计分 |

构图：plan 每页给一条 `composition.grammar`（视线如何被组织）；这是**提案**——不给坐标、
不给版式，生成侧可整体推翻。
修订：照 `fix_plan` 根因组**一轮批量改完**（内嵌契约行，零回读），一次改完再复跑同档——
不逐条「修一个、回读一个」。
风险预测：`forecast_risk` 在 plan 期输出政策（起草前消费）；默认 QA 不运行建议。

## Calls（最小 API）

入口与按需加载见 `SKILL.md`——本表只留字段与契约。
**元素字段、`chart_kind` 全表与每页上限、role 白名单 → `design-system.md` §Spec 字段速查**
（写 elements 前查它，不必回读 `compiler.py`）。

- `vao.py plan` → `pipeline.build_plan_bundle`：骨架只序列化**已决策字段**（canvas / theme 种子 /
  page_intent / source_zone，注释里附该页家族、叙事动作、构图语法提案），`elements` 留空——
  几何归生成侧判断，零预设；页数与 brief 的 slides 一一对应。deck 级事实（theme 种子、
  `direction_execution` 的介质/光照/图表手法）只在顶层出现一次，不逐页复制。
- `vao.py dna` → 经验记忆：`--check` 体检 / `--add <条目>.json`（校验后原子写入）。
  `judgment` 只写行为判断，色值/字号/版式结果放 `proven.measurements`——写坏的记忆不报错，
  只会永远命不中。
- `vao.py check` → `qa.run_qa`（normalize → guard → compile → 判定）+ ghost 预览 + 分组修复包；
  全程单进程，不串行跑单脚本，不启动任何外部渲染器。

报告自足：`fix_plan.groups[]` 按根因码分组阻断项（`count/ids/samples/fix`，fix 内嵌本表契约行）；
修正轮照单一次改完，零回读。`trace_summary` 按 (domain,rule,level) 聚合非阻断项，只记录。

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
几何：所有可见对象数值 `x/y/width/height`。光源以外的字段（如幻灯级 `background`）不存在——写了也会被静默忽略，别写。

来源区内文字 `role` 只允许 `{source, method, metadata}`（页码/编号等挂 `metadata`/`label`）；
其他角色触发 zone-invasion 错误。图片必须用 `asset_id` 绑定清单；绑定阶段采用与 QC 相同的路径解析器，再交给编译器。
生成图片目录优先 `--assets-dir`，其次清单声明目录；既有素材路径由来源声明给出。

可读性与裁切（工程，不是品味）：① 单行 meta 行（眉标/章标/页码/落款）`wrap=False`
且盒宽 ≥1.5× 估宽——第二行落盒外的裁切是沉默的。② `page_intent.focus` 声明**视线第一落点**，
非叙事主语。③ 弱化字对比声明色 <3:1 / <1.8:1 走 hint/warn（亮度分级见 `design-system.md` 的 muted 行）。

图表色走语义角色（`color_role`，详见 design-system.md §图表字段五组；柱状负值自动染 negative）。
背景画心声明 `layer:background` + 自带 `overlay` 内容保护，不计媒体预算；资格不足按普通对象判。

## Failure codes

| 代码 | 状态 | 处理 |
|---|---|---|
| `OVERLAP` `SOURCE_COLLISION` `CHART_LABEL_COLLISION` `TEXT_OVERFLOW` `READABILITY_FAIL` `DATA_INTEGRITY_FAIL` `CHART_TYPE_FAIL` `COMPILE_FAIL` `GUARD_FAIL` `ASSET_WORKFLOW_FAIL` | BLOCKED | 必修：按 `fix_plan` 根因组一次改完 |
| 其他 warn/hint（`BG_UNPROTECTED`、`DESIGN_RULES` 16 条、节奏与对齐提示等） | PASS | 只进 `trace_summary`，不解释、不询问、不逐条修复 |

`guard.check_spec` 的返回只有 `passed / checks / advisory_rules / warnings / grid / line_measure`——
**没有 score，也不恢复 score**：一旦出现总分，系统会退化成规则 → 指标 → 分数 → 排名 →
模板化优化，反过来削弱设计智能。

状态优先级：有阻断 → BLOCKED；spec 档 → PREVIEW_ONLY；0 阻断 → PASS（`release_eligible`
仅在 release 档、编译通过且所有发布凭证有效时为真）。

## Release Manifest

`vao.py check --mode release` 生成：`source_spec_hash`、`validation`、`verification`
（外部渲染器状态 / 视觉证据类型 / 结构页数 / 预览页数 / `release_eligible`）、
`compile_report`（含 `output_sha256`）、`ghost_preview`、`revision_count` 与 `revision_log`、
`status`。清单校验三件事：报告盖的 spec 戳与当前 spec 一致；PPTX 字节戳与磁盘一致；
预览证据引用的页面都在当前 spec 里。口径以代码为真源。

## 资产前置与发布一致性（v5.1 / v5.1.1 条款，仍有效）

`ASSET_WORKFLOW_FAIL` 由 `vao.py check` 在编译前给出；修法是补齐/刷新证据链，
不是改字号或降低图像阈值。`spec` 模式同样校验有图稿件的资产依赖，但不编译。
纯文字/原生图形稿件记录 `SKIPPED / no_image_elements`，不是伪造“已检查”。
Release Manifest 的 `asset_workflow` 记录 `status`、brief/plan/清单/QC 指纹和报告位置；
QC 本身包含每张图片的 SHA-256。验证失败时两层 `release_eligible` 均为 false；
编译 PASS 不可代替完整流程 PASS。

- 以 auto_fit 后的有效 spec 同时编译、预览与盖指纹；不得各用一版输入。
- 图片采用核验 bytes 快照；预览必须有完整页 ID 及每个文件的 SHA-256。
- 有计划的稿件必须覆盖计划的全部页 ID/顺序，包括无图稿件。
- 每轮 check 分配 run_id；旧资格先失效，异常也写本轮失败报告。草稿不拥有发布资格。
- 文本容量检查覆盖 text 与 shape.text；禁止换行时同时检查宽度。静态估算不是 Office 字体像素证明。
