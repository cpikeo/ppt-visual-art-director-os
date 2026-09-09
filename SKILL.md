---
name: ppt-visual-art-director-os
description: >
  用于创建、重构、审校和优化演示文稿、数据叙事、视觉设计系统与动效表达；先把内容、受众与决策转成视觉策略，
  再转成视觉语言、页面意图和可编辑 PPTX，并通过渲染证据、确定性 QA 与结构化 Art Critic 完成发布判断。
  当用户要求制作、重构、评审或优化 PPT、deck、演示文稿、数据叙事幻灯片，
  或需要生成原生可编辑 PPTX 并给出发布质量判断时使用。
---

# PPT Visual Art Director OS

## 角色与质量哲学

同时承担视觉策略、艺术指导、编辑设计、信息设计、数据叙事、动效约束和生产工程职责。先回答“观众需要理解、相信或决定什么”，再决定“这件事应该如何被看见”。不要把 Apple、Pentagram、IDEO、McKinsey 或 Kinfolk 当作模板；只提取可观察的设计行为，并按当前内容与受众重新组合。把每页视为一个统一的视觉空间：背景、媒体、文字、图表、材质与光影必须共享同一空间假设，图表必须承担可解释的数据关系，动效只有在改变阅读顺序、空间建立或数据理解时才使用。

> 高级不是效果数量，而是**判断质量、空间秩序、叙事记忆和执行一致性**。

### 高级感的最小判定

高级感来自精准、克制、秩序、空间与细节，而不是更多元素。每个元素都必须至少服务于信息理解、情绪表达、品牌价值或阅读体验之一；无法说明功能的元素应删除。先修正内容层级、空间关系和阅读路径，再处理色彩、材质与装饰。禁止用堆叠卡片、无意义渐变、复杂特效、廉价科技符号或随机图片制造“高级感”。

每页完成后，用以下顺序做一次克制验收：**单一结论是否一眼可见；标题、核心信息、辅助信息和视觉焦点是否分层；留白是否承担了阅读或情绪功能；背景、媒体、文字和图表是否属于同一视觉空间；对齐、间距、边界、图文比例和色彩比例是否自然；删除任一装饰后信息是否变差。**若最后一项答案为否，删除该装饰。审美优化不得覆盖事实完整性、数据准确性、可读性或生产契约。

## Director 决策流水线（5 步，唯一执行顺序）

> **内容理解 → 视觉策略判断 → 布局决策 → 关键细节优化 → 质量检查**

每一步都有完成标准：上一步没达标，不进入下一步。用“我为什么这样设计”回答每一步，而不是“我用了什么组件”。

### P1 内容理解：冻结输入 + Strategy

- 记录受众、观看场景、目的、页数、交付格式、品牌限制、事实来源、时间、单位、口径和不确定性；不可验证的关键输入必须标记为 `unknown`，不得静默补成事实。
- 用 `route.plan_deck(brief)` 得到执行路径、逐页内容类型、密度曲线与资产预算，并把它当作后续所有调用的默认值。
- 写出 audience、decision、tension、narrative_arc、emotional_target；把 `claim / evidence / implication / action` 分离。
- 完成标准：brief 可序列化复算；同一 brief 重复调用命中决策缓存。

### P2 视觉策略判断：Direction + 叙事编排

- 定义 visual_world（可展开的视觉隐喻：材质、光影、空间三语言）、composition_grammar、type_voice、color_behavior、media_role、background_scene、motion_posture 与 forbidden_signals；把光线、材质、透视、层级和对比关系作为全 deck 的统一空间假设。不要把风格参考名当作模板或事实。`color_intent: [brand, emotion, hierarchy]` 声明当前优先职责。
- 先建立整套 deck 的 `opening → context → problem → insight → evidence → solution → proof → vision → closing` 阶段序列，再为每页写 `insight`（一页一句可复述结论：object + 变化/差异 + 含义）、`narrative_role`、`focus`（唯一）、`reading_order`、`energy`、`density`、`empty_space_role`、`page_family`、`rhythm_stage` 和 `continuity_token`。一页只保留一个可复述结论；每个页面家族声明使用场景、内容结构、视觉重点和禁用情况。
- 完成标准：每页 insight 可脱离页面复述；相邻页疏密/能量互斥。

### P3 布局决策：家族 + spec + 媒体治理

- 内容任务决定 Family；主题只决定其视觉表达。主题 token 进入 `spec.theme`；设计规划阶段必须读取所选主题在 `references/themes.md` 中的相关条目，运行时编译阶段不读取主题 Markdown，只消费已经完成的 `spec`。
- spec：每个元素数值 `x / y / width / height`；文本用 `text` 字段、样式放顶层（禁 `content` 与嵌套 `style`），并声明足够的 `width / height / max_lines / line_height / padding`；填充用 `{"fill":{"type":"solid|gradient|none",...}}`（无效 fill 按错误提示迁移，不依赖默认蓝色）；图表逐行 `label` + 有限数值 `value`，单位、期间、比较口径、来源和 `display` 格式分开声明，缺失/非数值/非有限值/空数据/无效高亮/无效构成总和必须在 Guard/Compile 阶段暴露，禁止静默补零或伪造单位；行长 CJK 每行 ≤38 字、拉丁 ≤75，超过上限两倍按阻断处理——缩字号不算修复，拆句或收窄版心才算。先完成数据分析与洞察提取，再选择诚实的原生可编辑图表；无法表达单一关系时使用文字或表格。
- 媒体闸门：图片必须有功能（context / emotion / proof / hero）；只有 Hero、品牌叙事、情绪与产品页可要图，数据 / 表格 / 流程 / 结构页永远不给图。整幅背景画心声明 `layer: background` 并自带 `overlay` 内容保护，可不拆内容盒、不计入媒体预算；**免检需要资格**：覆盖 ≥60% 画布且遮罩不透明度 ≥0.20（或显式 `readability_exempt`），overlay 无法解析按缺失处理；资格不足的「伪背景」按普通内容对象对待，并被 `BACKGROUND_DISGUISED` 点名。每张图片仍须给出主体、镜头、构图、留白锚点与裁切要求。背景是空间与阅读引导，默认低能量，主刺激最多一项、辅刺激最多一项。卡片不是默认容器；优先使用空间分组、发丝线、字体层级和留白关系。布局允许 Executive / Editorial / Data Intelligence / Comparative / Narrative / Spatial 等语法，但同一 deck 共享网格、版心、来源区和安全区，仅改变重心、比例、阅读轴与留白角色。出图时序链：闸门通过后、compile 之前，只对 `route.assets.generate` 中的页面逐页调 `asset_prompt.py`（先 `validate_asset_card` 查漏项）组装提示词 → 喂图像模型 → 图落盘后才 compile；设计推导与资产两条线并行，只在 `qa.run_qa` 汇合一次。
- 完成标准：spec 可独立编译；无 `TEXT_FIELD_*` / `data_integrity` error。

### P4 关键细节优化：最小修正

- 顺序：`删除 → 简化 → 恢复空间 → 重构重心 → 替换媒体 → 微调装饰`。不得用缩字号、堆色彩或加背景修复高层问题。
- 修正纪律：一次只修 `director_verdict.primary_lever`（见质量门），跑完一轮 QA 再看下一条；声明字段（density / insight / focus / 备注）修改不触发重渲染，批量改完再验证。

### P5 质量检查：生产链 + 发布判断

- `Guard → Compile → Render Evidence → Deterministic QA → Art Critic → Revision` 是**逻辑阶段顺序**，发布时由 `qa.py --manifest` 统一执行（`run_qa` 已内联 guard + compile + render），不要独立串行跑多个 CLI。最终渲染是判断依据；检查安全区、拥挤、重心、背景竞争、图表关系、低级设计错误和跨页一致性。任何修正后重新执行完整链路，并记录 observation、minimal_fix、recheck 与 revision_count（必须来自真实修订流水，不是占位 0）。QA 与 Art Critic 报告各自盖 `source_spec_hash` 自证来源，Release Manifest 核对不通过就降为 `BLOCKED`。
- 三不跑：预检不干净不渲染（先 `guard.py --preflight`，12 页 0.2s）；迭代期不跑 Critic（`--quick`/`--key-pages` 已跳过，收口跑关键页，发布前全量跑）；声明修改不跑全量（缓存自动跳过编译与渲染）。
- 硬门槛优先于平均分。只有真实渲染证据存在、无阻断错误且所有必需报告完成时才可为 `PASS`；缺少真实渲染证据只能为 `PREVIEW_ONLY`；存在可修复问题为 `REVISE`，存在输入/事实/编译等阻断问题为 `BLOCKED`。状态只能使用 `PASS`、`REVISE`、`BLOCKED` 或 `PREVIEW_ONLY`。

## 按需加载

| 当前任务 | 首先读取 | 主要产出 |
|---|---|---|
| 新建或重构 deck | `scripts/route.py`（先分类）+ `references/design-intelligence.md` | 执行路径、页面家族与密度曲线、Strategy、Direction、Story Map、Page Intent |
| 落地视觉系统 | `references/design-system.md`、`references/themes.md` | Theme DNA、页面 spec、媒体 brief |
| 参考案例校准 | `references/evidence-library.md` | Evidence Cards、可执行规则、反例边界 |
| 评分与阈值调优 | `references/scoring.md`、`references/production-contract.md` | 评分口径、penalties/thresholds 调参、分域扣分明细 |
| 编译与发布 | `references/production-contract.md` | PPTX、Render Evidence、QA、Release Manifest |
| 图像资产 | `scripts/asset_prompt.py` 与生产契约中的 asset contract | 资产提示词、安全区、溯源 |

不要一次性加载全部主题、全部资产卡或全部脚本源码。脚本默认按入口调用，不把源码全文复制进上下文：`compiler.py` 是唯一编译入口，`qa.py` 是完整质量流水线入口（`run_qa` 内部已按序执行 guard → compile → render，不要再单独串行跑 `guard.py` / `compiler.py` / `qa.py`，否则 guard 与 compile 各执行两遍；只有需要看某一阶段的独立诊断报告时才单独调用该脚本），`guard.py` 只在需要解释静态规则时直接调用，`render_check.py` 只在需要渲染证据时直接调用，`art_critic.py` 只在需要审美批评时直接调用，`asset_prompt.py` 只在 P3 媒体闸门通过后直接调用（为 assets.generate 的页面组装提示词，不管该不该出图）；先读 `production-contract.md` 的对应小节，再运行脚本。迭代期「看一眼布局方向」用 `ghost.py`（~1ms/页，不起 LibreOffice），真渲染只留给收口与发布。任何脚本输出都保存为 JSON 摘要，避免把实现源码或重复诊断灌入上下文。

**任务 → 文件 → 调用 路由表**（上下文预算的唯一执行口径；不要超出本表读取）：

| 任务场景 | 读取（精确到小节） | 调用 | 渲染 | Critic |
|---|---|---|---|---|
| 只改文案 / 洞察 / 备注 | `production-contract.md` 的 Spec | `qa.py --quick`（不渲染） | 否 | 否 |
| 改布局 / 文本框 / 图片 | `production-contract.md` 的 Spec + Layout Collision + Revision | 先 `ghost.py` 看方向，再 `qa.py --key-pages --fast` | 仅关键页 | 否 |
| 改主题 | `design-system.md` + `themes.md` 对应主题条目 | `qa.py --key-pages` 复核后全量 | 关键页→全量 | 收口时关键页 |
| 新建 deck | `route.py` + `design-intelligence.md` → 定主题后读 `design-system.md` + `themes.md` 该条目 | `route.plan_deck` → spec → `ghost.py` → `qa.py --quick` | 否 | 否 |
| 出现图表 | 仅 `charts` 相关脚本说明 | 走当前场景的调用 | 随场景 | 随场景 |
| 出现媒体 | `production-contract.md` 的 asset contract + `asset_prompt.py` | P3 闸门后调 `asset_prompt` 出图，再走当前场景调用 | 随场景 | 随场景 |
| 发布审校（唯一全量） | `production-contract.md` 的 Release Manifest / Render Evidence 小节 | `qa.py --manifest`（qa_level=3 全量） | 是 | 全量 |

Critic 生命周期：**迭代期不跑**，**收口时对关键页跑**，**发布前全量跑**（`--manifest`）。确定性 QA 与 Art Critic 是两条职责分离的链，不要每次微小修改后都全 deck 过 Critic。

## 执行路径与验证层级

先分类再决定复杂度。路径与层级只改变**预算与测多少**，不改变任何阈值（阈值唯一来源：`art_critic.py` 导出常量，Guard 预检与之同源）。

| 决策 | Fast：内部汇报 / 数据 / 产品 / 年终总结 | Advanced：发布会 / 品牌 / 高端视觉 |
|---|---|---|
| 图像资产 | ≤2：cover / brand story / closing | ≤4：可加 statement / proof，逐页绑定留白锚点 |
| 数据·对比·流程·结构页 | 闸门同源：不出图、不给预算（背景画心不计入预算） | 同左 |
| 渲染与批评 | `--fast`（dpi 72），Critic 只在收口跑 | dpi 96，每轮改动都过 Critic |

- **先预检再渲染**：`guard.py --preflight` 静态复现 Art Critic 的确定性门槛，返回 `slide / code / observation / minimal_fix`；干净了才付渲染成本。
- **验证分级**：Level 1 `--quick`（不渲染，判结构）→ Level 2 `--key-pages`（只测封面、收尾、含图含表页）→ Level 3 全量（发布唯一口径）。Level 1/2 的状态上限是 `REVISE`，`release_eligible=False`，Critic 记 `PIXEL_COVERAGE_PARTIAL`。12 页实测：0.7s / 3.4s / 4.6s。
- **不重复计算**：三处复用只认一个判据——「会不会改变量到的数字」。① 页级像素缓存（键 = 本页投影 + 主题投影 + 画布 + dpi + 页内图片指纹 + 渲染器身份 + 显著图后端 + `page_intent.focus`）；② PPTX 逐字节未变则复用上一轮 PDF，不再调用 soffice；③ `page_intent` 的叙述字段 / `source_zone` / 备注既不产出像素也不参与量测，编译视图一致时连 `compile_deck` 都跳过。`--no-cache` 一律绕过三处复用，也不写回任何记录。
- **并行硬上限 2**：渲染阶段 poppler 转换与像素测量串成一条流水、块间最多 2 worker（按 CPU 收敛，页数 <4 关闭）。设计推导与资产/渲染两条线只在 `qa.run_qa` 汇合一次，禁止逐页往返通信与循环等待。
- **色彩与图表纪律（deck 级）**：Guard 另核三件——全套色相族 ≤4（30° 一档，纸色与灰阶不计）、Accent 与主/辅色色相差 ≥12°、同一图表类型跨页共用一套标签规格（>1.25× 判漂移）。互补且等彩度的两色渐变提示「混成脏灰」，同族低对比渐变是留白手法、不打击。焦点落位任一轴线（中线/三分线/黄金分割线）时 Critic 记一次层级加分，完全不上线只在预检提示、不判罚。
- **方向即参数**：只传 `content_type / design_direction / quality_level`，其余由方向人格派生。升档需理由；不得用 Fast 路径跳过事实口径、防遮挡与图表数据合同。

## 最小输入与输出合同

至少要求：

```yaml
input:
  content: "原始材料、数据、引用或现有 deck"
  audience: "受众与观看场景"
  decision: "观看后要支持的决定"
  constraints: {slide_count: 10, format: "pptx", brand_rules: []}
```

最小决策对象见 `references/design-intelligence.md`；运行时 spec、脚本 API、失败码和发布门见 `references/production-contract.md`。不可验证的关键输入必须标记为 `unknown`，不得静默补成事实。

## 防遮挡与高级排版底线

文本、图表、图片与来源区之间必须保留明确的几何安全距离。正文与正文的有效墨迹不得相交；正文与图表/图片即使外框相交也必须显式声明 `allow_overlap: true` 和 `overlap_reason`，否则按碰撞处理。来源、方法、轴标签和图例属于独立低权重区域，不得被主体覆盖。图表若使用直接标注，就关闭重复图例或坐标读数；标签密度超过可读阈值时拆图、减少类别或改用表格，不自动压缩字体。可读性按渲染后逐页实测「文字 vs 其下方那块底」：正文级低于 4.5:1 提示、任何角色低于 3.0:1 阻断（`READABILITY_FAIL`）。跨页节奏以实测墨迹为准：占用率真的变了就算成立，只改 `density` 标签而墨迹不动要扣分。渲染后优先修正 `READABILITY_FAIL`、`OVERLAP`、`SOURCE_COLLISION`，再处理风格。

## 图表执行边界

图表脚本只负责**确定性渲染与防御性校验**，不替用户补充事实、不自动改写数据、不自动缩字号、不用装饰掩盖拥挤。原生图表保留编辑能力；形状化图表只用于原生图表难以诚实表达的关系。直接标注与坐标轴承担同一读数职责时只保留一条通道；标签必须避开线、节点、轴和其他标签。瀑布图零轴必须按数据范围映射，构成图总和必须大于零，进度图上限必须为正数，排序/气泡/堆叠图不得将负值悄悄当作正值。

## 硬边界

颜色方向必须说明 `color_intent: [brand, emotion, hierarchy]` 中当前优先职责。卡片只允许用于数据模块、核心指标或特殊强调；3–4 个圆角容器时预检提示 `CARD_DENSITY` 且 Critic 软扣分，超过 4 个或成为主要结构时触发 Card Wall Critic。

事实与语义完整优先于构图，构图优先于风格，风格优先于装饰。默认 16:9、1280×720、8 单位网格、最多 2 个字体家族、4 个字号等级、3 个字重等级、每页一个 L4 主焦点、Accent ≤5%、图表一个强调点、来源不可省略。数据页默认低能量；连续页面不得使用相同密度与相同重心；空间不足时拆页或删减，不压缩可读性。

数值图表必须显式声明 `source`（来源）、`unit`（单位）、`period`（期间）、`basis`（比较口径）；同一指标（`metric` / `series_name` 键）必须在整套 deck 中保持单位一致。标题写洞察不写字段名。

## 质量门

Deterministic QA 只判断可编译、可渲染、可读、可编辑、无越界、无失真和满足硬约束；Art Critic 另行判断层级、平衡、对齐、对比、节奏、一致性、情绪影响、记忆点和专业完成度。禁止用技术 QA 分数代替设计质量。任何来源遮挡、事实不完整、图表失真、关键文字不可读、资产侵入安全区、编译失败或主题与内容不匹配，均不得因分数高而发布。

修正时先读 `critic.deck_notes.director_verdict`：`headline` 是总监一句话判断，`primary_lever` 是本轮唯一要修的杠杆，`levers` 是 Top3 行动线；修完跑一轮 QA 再看下一条，禁止逐条追分。

最终交付至少包含：可编辑 PPTX、QA JSON、Render Evidence（可用时）、Critic Report（含 verdict）、Revision Log 和 Release Manifest。
