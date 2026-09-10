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

## 执行架构：设计智能（判断）+ 工程验证（正确性）+ 设计批评（价值）

> **核心原则**：用 Design Intelligence 产生世界级设计，用 QA 保证不会失败，用 Critic 提供
> 少量高价值反馈。三层各答一个问题，**一个问题只由一层回答**：
> QA 答「能不能正确交付」（PASS / FAIL / WARNING）；Critic 答「有没有高级设计价值」；
> Design Intelligence 答「该怎么做、以及这样做会挂在哪里」。

**默认路径是创作链，不是发布链。** 发布级流水线（全量渲染 + Critic + Manifest）只在终版交付时触发——初稿、方向探索、多方案对比永远不该付它的成本。CLI 不传 `--mode` 即为快速生成（零渲染、秒级、风险预测与生成策略首屏）；显式 `--level N` / `--fast` 是「明确要测」的信号，维持 legacy 全量行为。Fast/Advanced 是**预算控制**（资产数/dpi），Execution Mode 是**流程控制**（渲染不渲染、Critic 何时介入、状态给到哪一级），两者正交：

| Mode | 链 | 流程 | Critic | 时间目标 |
|---|---|---|---|---|
| `--mode spec`（零成本档 · 只要判断） | 判读链 | python → Normalizer → Guard → 风险预测 —— **不 import 编译层、不写文件**（12 页实测 0.05s；「这样写会不会挂」用它问，别用 draft） | 恒不跑 | 零成本 |
| `--mode sketch`（显式 · 结构探索） | 草图链 | Route → spec → **Normalizer（只留 error 级）→ Compile → PPTX**——颜色分析/媒体检查/文字合同全部免除，变体迭代不被契约拦截 | 恒不跑 | 秒级 |
| `--mode draft`（默认 · 快速生成） | 创作链 | Route → P1–P3 → spec → **Normalizer → Guard → Compile → 可编辑 PPTX**，零渲染 | 恒不跑 | 亚秒级（12 页实测 <0.3s） |
| `--mode review` | 审查链 | Compile → **只渲染本轮变化页**（首次无对照时才用关键页）→ QA L2 | **恒跑**（一轮一次，无门控） | 十秒级 |
| `--mode release` | 发布链 | 全量渲染 → QA L3 → Critic → Release Manifest | 恒全量 | 分钟级 |

- 升档条件：`to_review` = 用户确认方向 / 改了布局、主题、图表结构；`to_release` = 终版交付、发布前复核。`route.plan_deck(brief)["execution"]` 给出推荐模式与升档规则（默认 draft）。
- **状态天花板**（阈值一个不降，只是把「测多少」交给模式）：`sketch` 最多 SKETCH、`draft` 最多 PREVIEW_ONLY（零渲染 → 必然 `PIXEL_COVERAGE_PARTIAL`）；`review` 与 `release` 同一判据——**只有像素证据覆盖全部页才可能是 PASS**。差别在发布资格：`release_eligible` 还要求发布链（`qa_level=3`）+ Release Manifest，所以 review 即使缓存把 12 页全测了（status=PASS）也是 `release_eligible=False`，`next_action` 会写明「发布需 `--mode release`」。
- **Critic 生命周期（一句话）**：`draft / sketch 不跑，review / release 跑`。没有稳定性门控、没有连续 clean 计数、没有 Critic 结果缓存、没有 `studio_state.json`——省时间的正确手段是「少渲染几页」+「页级渲染缓存」，不是把批评藏进状态机里；Critic 成本从来不是瓶颈（瓶颈是 LibreOffice/PDF/像素）。

### 四个引擎 + 一次汇合（Parallel Intelligence）

内容线（route）、视觉线（DNA）、风险线（预测→策略）互不依赖——不要串行等待；
`design_intelligence.analyze(brief, spec)` 一次调用汇合三线（**brief 阶段就返回
`forecast`：还没有 spec 时的风险向量与生成政策**；spec 落稿后再跑一次拿逐页预测与策略）。

执行次序因此是：`Design Intelligence → Risk Prediction → Generator → Critic`——
预测是**本层内部的子模块**，不是生产链上的第二道审核。

| 引擎 | 回答的问题 | 入口 | 成本 |
|---|---|---|---|
| **Design DNA Memory** | 这类需求之前怎么做成功的？ | `recall_dna(brief)`（route 已内联，P1 即得） | ~0ms |
| **Media Decision Model** | 这页要不要图？（置信度+理由，不是布尔闸门） | `media_decision(page)` | ~0ms |
| **Page Quality Budget** | 这页追求什么样的好？（Hero 换情绪 / Data 求清晰） | `quality_budget(page)` | ~0ms |
| **Risk Prediction + Strategy** | 起草前：这套内容会在哪里出问题，因此该用什么预算/政策起草？落稿后：这份 spec 将会挂在哪里，怎么改？ | `forecast_risk(brief)`（起草前）→ `pre_critic(spec)` + `risk_strategy(spec)`（修订时） | ~0.1ms/deck + ~1ms/页 |
| **Deck Decision + Intent Skeleton** | deck 级判断一次固化（弧线/密度曲线/媒体政策），页面骨架继承只填洞——AI 推理从 O(页数) 降到 O(1)+填空 | `route.deck_decision(brief)` + `design_intelligence.page_intent_skeleton(family, …)` | ~0ms |
| **Layout Search** | 这页的三种结构候选谁最优？（Grammar 生成 + 五维打分，不是模板） | `layout_search.search(intent, profile, dna, n=3)` | ~1ms/候选 |

### 契约索引（先定位再动手）

写 spec 前**不需要**读完任何文档：`references/production-contract.md §Runtime Contract Map`
是唯一权威表（元素/填充/图表/focus/密度/色彩/网格/媒体/可读性/发布…每行给关键规则 +
要读的小节）。**禁止靠 grep 全库找规则**；表里没有的语义，先 `qa.py --mode spec` 问代码。

## 设计判断：原则优先于规则

写这页之前先回答三件事（不需要读文档也能回答）：**这页唯一的主语是什么 / 留白在替谁工作 /
观众的眼睛按什么顺序走**。代码只在下面这些事实上替你把关，其余全靠你的判断：

- **只有一个主语**：其他元素要么能被降级（更小、更淡、更远），要么就该被删。「也很显眼但差一点」等于没降级。
- **留白要有名字**：`hold_attention / hold_emotion / create_breath / frame_focus`；说不出职责的大片空白是事故，
  而**有职责的大片空白常常是最贵的设计**。
- **对比优先于装饰，克制优先于丰富**：一处强调色、一套字阶、一根轴线。加东西很少能解决「不够好」，减东西经常能。
- **数据不许撒谎也不许藏**：口径/单位/期间先于样式；读者要心算才能确认结论，说明图画错了。
- **deck 是一个作品**：节奏、母题一致、一个可复述的记忆点都只在 deck 级存在。单页全 A 的 deck 可以整体平庸。
- **一轮只修一个根因**：`director_verdict.primary_lever`；`batch.deferred` 排队下轮。为分数调参数 = 把对的地方改坏。

案例（症状 → 判断 → 修法 → 证据）在 `references/design-craft.md §案例库`：卡片墙是回避不是层级、
同口径优先于同外观、留白当预算、一次只修一个根因。**这份手册没有「必须」清单——能被阈值判掉的
都已经在代码里了；剩下的靠你。**

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
- 先建立整套 deck 的 `opening → context → problem → insight → evidence → solution → proof → vision → closing` 阶段序列，再为每页写 `insight`（一页一句可复述结论：object + 变化/差异 + 含义）、`narrative_role`、`focus`（唯一）、`reading_order`、`energy`、`density`、`empty_space_role`、`page_family`、`rhythm_stage` 和 `continuity_token`；关键页补一句 `design_rationale`（为什么这样摆——选择 × 理由 × 否决项；声明层字段，修正时验证意图兑现，`record_dna` 沉淀时引用）。一页只保留一个可复述结论；每个页面家族声明使用场景、内容结构、视觉重点和禁用情况。
- 完成标准：每页 insight 可脱离页面复述；相邻页疏密/能量互斥。

### P3 布局决策：家族 + spec + 媒体治理

- 内容任务决定 Family；主题只决定其视觉表达。主题 token 进入 `spec.theme`；设计规划阶段必须读取所选主题在 `references/themes.md` 中的相关条目，运行时编译阶段不读取主题 Markdown，只消费已经完成的 `spec`。
- spec：每个元素数值 `x / y / width / height`（8 单位网格由 **Normalizer 自动吸附**——手工对齐不是你的职责，但语义几何如黄金分割落点仍由你决定）；文本用 `text` 字段、样式放顶层（禁 `content` 与嵌套 `style`），并声明足够的 `width / height / max_lines / line_height / padding`；填充用 `{"fill":{"type":"solid|gradient|none",...}}`（无效 fill 按错误提示迁移，不依赖默认蓝色）；图表逐行 `label` + 有限数值 `value`，单位、期间、比较口径、来源和 `display` 格式分开声明，缺失/非数值/非有限值/空数据/无效高亮/无效构成总和必须在 Guard/Compile 阶段暴露，禁止静默补零或伪造单位；行长 CJK 每行 ≤38 字、拉丁 ≤75，超过上限两倍按阻断处理——缩字号不算修复，拆句或收窄版心才算。先完成数据分析与洞察提取，再选择诚实的原生可编辑图表；无法表达单一关系时使用文字或表格。
- 媒体闸门：图片必须有功能（context / emotion / proof / hero）；只有 Hero、品牌叙事、情绪与产品页可要图，数据 / 表格 / 流程 / 结构页永远不给图。整幅背景画心声明 `layer: background` 并自带 `overlay` 内容保护，可不拆内容盒、不计入媒体预算；**免检需要资格**：覆盖 ≥60% 画布且遮罩不透明度 ≥0.20（或显式 `readability_exempt`），overlay 无法解析按缺失处理；资格不足的「伪背景」按普通内容对象对待，并被 `BACKGROUND_DISGUISED` 点名。每张图片仍须给出主体、镜头、构图、留白锚点与裁切要求。背景是空间与阅读引导，默认低能量，主刺激最多一项、辅刺激最多一项。卡片不是默认容器；优先使用空间分组、发丝线、字体层级和留白关系。布局允许 Executive / Editorial / Data Intelligence / Comparative / Narrative / Spatial 等语法，但同一 deck 共享网格、版心、来源区和安全区，仅改变重心、比例、阅读轴与留白角色。出图时序链：闸门通过后、compile 之前，只对 `route.assets.generate` 中的页面逐页调 `asset_prompt.py`（先 `validate_asset_card` 查漏项，再 `enhance_asset_card` 注入动势/微浮雕/融合三层）组装提示词 → 喂图像模型 → 图落盘后才 compile；设计推导与资产两条线并行，只在 `qa.run_qa` 汇合一次。
- 完成标准：spec 可独立编译；无 `TEXT_FIELD_*` / `data_integrity` error。

### P4 关键细节优化：最小修正

- 顺序：`删除 → 简化 → 恢复空间 → 重构重心 → 替换媒体 → 微调装饰`。不得用缩字号、堆色彩或加背景修复高层问题。
- 修正纪律：**1 根因 = 1 轮**。读 `director_verdict.primary_lever` 与 `verdict.batch`——`fix_this_round` 是 primary 同根因的全部杠杆（如主题对比度引发的 READABILITY + contrast 维度 + chart_muted 提示），一次修完、一次验证；`deferred` 是不同根因，严格排队下轮。归因不破坏：同组 = 同一个「为什么」。声明字段（density / insight / focus / 备注）修改不触发重渲染（`classify_spec_change` 判 narrative），批量改完再验证。

### P5 质量检查：生产链 + 发布判断

- `Normalizer → Guard → Compile → Render Evidence → Deterministic QA → Art Critic → Revision` 是**逻辑阶段顺序**；执行入口是**执行模式**：`qa.py --mode draft`（零渲染，默认）/ `--mode review`（只渲染变化页 + Critic）/ `--mode release`（= `--manifest`，全量 + Critic + Manifest），`run_qa` 已内联 normalizer + guard + compile + render，不要独立串行跑多个 CLI。最终渲染是判断依据；检查安全区、拥挤、重心、背景竞争、图表关系、低级设计错误和跨页一致性。任何修正后重新执行完整链路，并记录 observation、minimal_fix、recheck 与 revision_count（必须来自真实修订流水，不是占位 0）。QA 与 Art Critic 报告各自盖 `source_spec_hash` 自证来源，Release Manifest 核对不通过就降为 `BLOCKED`。
- 省时间的三条（就这些，没有第四条）：① 迭代期不渲染也不跑 Critic（draft/sketch 零渲染、零 Critic）；② review 只渲染变化页（`classify_spec_change` 判 narrative → 该页连编译都跳过）；③ 静态预检先看（`guard.py --preflight`，12 页 0.2s）——它是**诊断报告**，不是拦渲染的闸门（vNext 已删 `preflight_gate`：让「不干净不渲染」这条规则去管渲染时机，换来的只是多一个状态分支）。
- 缓存只有两处（vNext 的全部缓存家当）：编译产物复用（`spec_view` 指纹 + PPTX 字节核验 + PDF 复用）与页级渲染指标缓存。`COMPILER_VERSION` 式版本闸、Critic 结果缓存、`studio_state.json`、多版本迁移都不再需要——内容核验已经覆盖同一件事。
- 硬门槛优先于平均分。只有真实渲染证据存在、无阻断错误且所有必需报告完成时才可为 `PASS`；缺少真实渲染证据只能为 `PREVIEW_ONLY`；存在可修复问题为 `REVISE`，存在输入/事实/编译等阻断问题为 `BLOCKED`。状态只能使用 `PASS`、`REVISE`、`BLOCKED` 或 `PREVIEW_ONLY`。

## 按需加载

| 当前任务 | 首先读取 | 主要产出 |
|---|---|---|
| 新建或重构 deck | `scripts/route.py`（先分类）+ `references/design-intelligence.md` | 执行路径、页面家族与密度曲线、Strategy、Direction、Story Map、Page Intent |
| 落地视觉系统 | `references/design-system.md`、`references/themes.md` | Theme DNA、页面 spec、媒体 brief |
| 参考案例校准 | `references/evidence-library.md` | Evidence Cards、可执行规则、反例边界 |
| **设计品味本身**（层级/留白/节奏/强调/图表性格） | `references/design-craft.md`（原则 + 刻度 + 案例，无「必须」清单） | 判断依据，不是新规则 |
| 评分与阈值调优 | `references/production-contract.md`（评分体系总览与调参）、`references/benchmark-calibration.md`（阈值校准方法） | 评分口径、penalties/thresholds 调参、系统性短板、阈值校准 |
| 编译与发布 | `references/production-contract.md` | PPTX、Render Evidence、QA、Release Manifest |
| 图像资产 | `scripts/asset_prompt.py` 与生产契约中的 asset contract | 资产提示词、安全区、溯源 |

不要一次性加载全部主题、全部资产卡或全部脚本源码。脚本默认按入口调用，不把源码全文复制进上下文：`compiler.py` 是唯一编译入口，`qa.py` 是完整质量流水线入口（`run_qa` 内部已按序执行 guard → compile → render，不要再单独串行跑 `guard.py` / `compiler.py` / `qa.py`，否则 guard 与 compile 各执行两遍；只有需要看某一阶段的独立诊断报告时才单独调用该脚本），`guard.py` 只在需要解释静态规则时直接调用，`render_check.py` 只在需要渲染证据时直接调用，`art_critic.py` 只在需要审美批评时直接调用，`asset_prompt.py` 只在 P3 媒体闸门通过后直接调用（为 assets.generate 的页面组装提示词，不管该不该出图）；先读 `production-contract.md` 的对应小节，再运行脚本。迭代期「看一眼布局方向」用 `ghost.py`（~1ms/页，不起 LibreOffice），真渲染只留给收口与发布。任何脚本输出都保存为 JSON 摘要，避免把实现源码或重复诊断灌入上下文。

**任务 → 文件 → 调用 路由表**（上下文预算的唯一执行口径；不要超出本表读取）：

| 任务场景 | 读取（精确到小节；80% 情况查 production-contract.md §Runtime Contract Map 即可） | 调用 | 渲染 | Critic |
|---|---|---|---|---|
| 纯结构探索（多变体快比） | `production-contract.md §Execution Modes` | `layout_search.recommend`（标准家族直达）→ spec → `--mode sketch`（契约免除，秒级）；比完升 draft 过契约 |
| 初稿 / 探索 / 多方案 | `design-intelligence.md`（+ 超纲才查契约表） | `route.one_pass_plan`（含 DNA 召回 + `forecast_risk` 政策）→ 按政策起草 → `layout_search` 选版式 → spec（可 `auto_fit`）→ `qa.py --mode draft`（零渲染，首屏读**风险策略**并按它改） | 否（方向用 `ghost.py`） | 否 |
| 只改文案 / 洞察 / 备注 | `production-contract.md §Runtime Contract Map`「文本元素」行 | `qa.py --mode draft`（classifier 判 narrative，编译渲染全跳过） | 否 | 否 |
| 方向确认 / 改布局、主题、图表 | `production-contract.md` 的 Layout Collision + Revision + 契约表对应行 | 先 `ghost.py` 看方向，再 `qa.py --mode review` | 只渲染变化页（首轮无对照时用关键页） | 跑（恒一轮一次） |
| 出现图表 | `production-contract.md §Runtime Contract Map`「图表数据」行 | 走当前场景的调用 | 随场景 | 随场景 |
| 出现媒体 | `production-contract.md` 的 asset contract + `asset_prompt.py` | P3 闸门后调 `asset_prompt` 出图，再走当前场景调用 | 随场景 | 随场景 |
| 发布审校（唯一全量） | `production-contract.md` 的 Release Manifest / Render Evidence 小节 | `qa.py --mode release`（qa_level=3 全量 + Manifest） | 是 | 全量 |

（legacy `--quick` / `--key-pages` / `--manifest` 仍是合法别名，语义分别等于 `--mode draft` / `--mode review` / `--mode release`。）

Critic 生命周期一句话：**draft/sketch 不跑，review 与 release 跑**（`--critic on|off` 可显式覆盖）。确定性 QA 与 Art Critic 是两条职责分离的链，不要每次微小修改后都全 deck 过 Critic，也不要给 Critic 加门控或缓存来「省」它的成本。

## 执行路径与预算（不改阈值，只改「测多少」）

| 决策 | Fast：内部汇报 / 数据 / 产品 / 年终总结 | Advanced：发布会 / 品牌 / 高端视觉 |
|---|---|---|
| 图像资产 | ≤2：cover / brand story / closing | ≤4：可加 statement / proof，逐页绑定留白锚点 |
| 数据·对比·流程·结构页 | 闸门同源：不出图、不给预算（背景画心不计入预算） | 同左 |
| 渲染与批评 | `--fast`（dpi 72）；Critic 只在 review/release 跑 | dpi 96；Critic 同在 review/release 跑 |

- **档位不是质量等级**：`spec`（0.05s，只问「会不会挂」）→ `draft`（出可编辑 PPTX）→ `review`（只渲染变化页）
  → `release`（全量 + Manifest，唯一给发布资格的一档）。阈值唯一来源是 `art_critic.py` 导出常量，任何档位都不降。
- **预检是诊断，不是闸门**：`guard.py --preflight` 静态复现可机械判定的设计契约，返回
  `slide / code / observation / minimal_fix`；它不拦渲染，也不参与美学评分（权重 0）。
- **方向即参数**：只传 `content_type / design_direction / quality_level`，其余由方向人格派生；升档需理由，
  不得用 Fast 路径跳过发布判断。

## 最小输入

```yaml
input:
  content: "原始材料、数据、引用或现有 deck"
  audience: "受众与观看场景"
  decision: "观看后要支持的决定"
  constraints: {slide_count: 10, format: "pptx", brand_rules: []}
```

决策对象结构 → `references/design-intelligence.md`；spec 字段、脚本 API、失败码、发布门 →
`references/production-contract.md`。**别把两份文档当手册通读**：契约表定位到行，超纲才进小节。

## 硬边界（唯一清单 · 违反即由 QA 阻断）

- 文本、图表、图片与来源区之间保留明确几何安全距离；正文与正文的有效墨迹不得相交。
- 数值图表必须显式声明 `source` / `unit` / `period` / `basis`；同一指标全 deck 单位与口径一致。
- 图表脚本只做确定性渲染与防御性校验：**不补事实、不改数据、不自动缩字号、不用装饰掩盖拥挤**。
- 颜色方向必须说明 `color_intent: [brand, emotion, hierarchy]` 当前优先职责；卡片只用于数据模块、
  核心指标或特殊强调（不是默认容器）。
- 默认 16:9、1280×720、8 单位网格（Normalizer 自动吸附，手工对齐不是你的职责）、字体家族 ≤2。
- 优先级次序：事实与语义完整 > 构图 > 风格 > 装饰。

以上答的是「能不能交付」。**没被违反不等于设计合格**——及格线之上的判断在 `references/design-craft.md`。

## 质量门（两层，各答一个问题）

**QA = Engineering Correctness**：只答「能不能正确交付」→ `PASS / FAIL / WARNING`（`qa.verdict_of`）。
范围 = 内容层（溢出/缺失/数据/图表异常）+ 几何层（越界/重叠/安全区/对齐）+ 渲染层
（字体替换/图片损坏/像素异常）+ 物理可读底线（文字压在图上不可读）。

**Critic = Design Value**：只答「这套设计有没有高级价值」，主输出是 `diagnosis`
（`assessment / strengths / risks / advice`）；`deck_score` 是**置信度**，**分数变化不得作为修订理由**——
理由只能是 `dimension_evidence` 里的具体事实。它不管 overflow / contrast / overlap / font-size
（这些在 `delegated_to_qa` 里显式移交）。

**Guard 不判审美（v3.2）**：`guard.DESIGN_RULES` 的 17 条是 `advisory`（权重 0、永不 error），只告诉你
「评审会往哪儿看」。把它们当及格线刷分，是把设计做平最快的方法。

**Design Intelligence Anti-Engineering Principle**：任何设计判断若能被固定阈值完全描述，就不是设计智能
而是工程约束——那种东西住进代码（阈值常量），不住进你的记忆。所以本文件剩下的「必须」都是
可直接执行的工程规则，不是品味条款。

最终交付至少包含：可编辑 PPTX、QA JSON、Render Evidence（可用时）、Critic Report（含 verdict）、Revision Log 和 Release Manifest。
