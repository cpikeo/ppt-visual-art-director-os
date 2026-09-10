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

## 三层执行架构：创作链（快）→ 审查链（准）→ 发布链（严）

**默认路径是创作链，不是发布链。** 发布级流水线（全量渲染 + Critic + Manifest）只在终版交付时触发——初稿、方向探索、多方案对比永远不该付它的成本。CLI 不传 `--mode` 即为快速生成（零渲染、秒级、pre-critic 首屏）；显式 `--level N` / `--fast` 是「明确要测」的信号，维持 legacy 全量行为。Fast/Advanced 是**预算控制**（资产数/dpi/Critic 时机），Execution Mode 是**流程控制**（渲染不渲染、Critic 何时介入、状态给到哪一级），两者正交：

| Mode | 链 | 流程 | Critic | 时间目标 |
|---|---|---|---|---|
| `--mode draft`（默认 · 快速生成） | 创作链 | Route → P1–P3 → spec → **Normalizer → Guard → Compile → 可编辑 PPTX**，零渲染 | 恒不跑 | 秒级 |
| `--mode review` | 审查链 | Compile → **关键页 ∪ 本轮受影响页**渲染 → QA L2 | **布局稳定后自动**（连续两轮 clean 且像素相关投影未变） | 十秒级 |
| `--mode release` | 发布链 | 全量渲染 → QA L3 → Critic → Release Manifest | 恒全量 | 分钟级 |

- 升档条件：`to_review` = 用户确认方向 / 改了布局、主题、图表结构；`to_release` = 终版交付、发布前复核。`route.plan_deck(brief)["execution"]` 给出推荐模式与升档规则（默认 draft）。
- **状态上限**：draft ≤ PREVIEW_ONLY，review ≤ REVISE，只有 release 可 PASS（`release_eligible` 仅认 Level 3 全量像素证据）——阈值一个不降，只是把发布级验证留给发布时刻。
- **Critic 生命周期**：迭代期不跑（draft）；review 模式待布局稳定自动介入（结果按 spec 指纹缓存，布局再动不浪费、布局不动零重算）；发布前全量跑（release）。稳定 = 连续两轮无阻断且 `geometry_only_hash` 未变（干净且几何未变的 draft 轮同样计入，draft→review 可直通）；`PIXEL_COVERAGE_PARTIAL`/`RENDER_UNAVAILABLE` 是非发布模式预期码，不算「布局在动」。
- **语义变更分类**：`qa.classify_spec_change(old, new)` 把修改分为 `narrative`（只改声明/备注 → 不渲染）/ `page_render`（改了像素相关字段 → 渲染该页）/ `full_render`（主题/画布 → 全量）/ `structure`（页数变了）。review 渲染集 = key_pages ∪ 受影响页——「改一句 insight 不必重渲染」是显式决策，不是缓存副作用。

## Design Intelligence Layer（生成之前消灭设计错误）

> 执行链解决了「验证的重复」；本层解决「设计的重复」：**AI 不应该设计一次、验证很多次，
> 而应该在生成之前，大部分设计错误已被预测和消除。** 流程从
> 「生成→检查→发现→修复→再生成」升级为 **「理解 → 预测 → 决策 → 生成 → 一次通过」**。

### 四个引擎 + 一次汇合（Parallel Intelligence）

内容线（route）、视觉线（DNA）、风险线（Pre-Critic）互不依赖——不要串行等待；
`design_intelligence.analyze(brief, spec)` 一次调用汇合三线（spec 未起草时先拿
DNA+媒体模型，起草后再跑一次拿风险报告）。

| 引擎 | 回答的问题 | 入口 | 成本 |
|---|---|---|---|
| **Design DNA Memory** | 这类需求之前怎么做成功的？ | `recall_dna(brief)`（route 已内联，P1 即得） | ~0ms |
| **Media Decision Model** | 这页要不要图？（置信度+理由，不是布尔闸门） | `media_decision(page)` | ~0ms |
| **Page Quality Budget** | 这页追求什么样的好？（Hero 换情绪 / Data 求清晰） | `quality_budget(page)` | ~0ms |
| **Pre-Critic Engine** | 这个 spec 将会挂在哪里？（accent 超载/锚点缺失/对比度/焦点冲突/溢出/节奏趋平/密度失配/媒体误用） | `pre_critic(spec)`（draft/review 已内联） | ~1ms/页 |
| **Layout Search** | 这页的三种结构候选谁最优？（Grammar 生成 + 五维打分，不是模板） | `layout_search.search(intent, profile, dna, n=3)` | ~1ms/候选 |

**Pre-Critic 纪律（关键）**：
- 风险报告在 draft 模式第一屏输出——**修复它的优先级高于一切渲染验证**；
- 每条风险带 `root_cause`（与 `director_verdict` 同一分类法）+ `prevention` +
  `predicted`（下游失败码）——直接对接「1 根因 = 1 轮」批量修正；
- 它用与 Critic/QA **同一套常量**做静态估计（不渲染）：预估是保守方向
  （宁可轻微高估不可漏报），`confidence` 标注可信度；
- release 模式不跑预测（有真实 Critic）——预测是给创作链和审查链用的。

**Design DNA 纪律**：DNA 是**设计经验记忆**，不是模板/组件/固定页面——它是
「看到需求就知道该怎么做」的可复用判断（空间/版式语法/色板策略/字声/媒体处理/
图表人格/禁用信号）。`record_dna()` **只在上游校验 PASS 后调用**（真实发布过的
经验才值得记忆）；recall 命中时按当前内容重组，禁止照抄。

**Layout Search 纪律**：Layout Grammar 四要素（支配性/负空间/视觉锚点/阅读路径）
参数化生成几何，按信息重量、焦点、数据关系合成——不是 Hero01/Chart02 组件库。
候选只在 **spec 级**比较（不生成三份 PPT），选优后进入 spec 起草。原型只是构图算子
的常用驻点（算子语法见 `design-intelligence.md`「构图算子」）：相邻两页不复用同一
算子组合；连续 deck 同家族同原型时，第三副须换构图语法，或在 `design_rationale`
声明品牌连续性。

**Smart Fit Resolver（auto_fit）**：文本溢出在 spec 层按阶梯吸附——
`padding→0 → line_height→1.05 → 字号 -2px 递降（下限 12）→ needs_rewrite`。
**显式 opt-in**（元素 `auto_fit: true`），未声明零改动；编译器行为不变（仍只警告）。

### Runtime Contract Map（字段级契约索引 · 先定位再动手）

写 spec 前查这一张表就够了；细节再按「读」列精确到小节取。**禁止靠 grep 全库找规则。**

| 任务 | 关键规则（80% 情况到此为止） | 读（仅超纲时） |
|---|---|---|
| 文本元素 | 用 `text` 字段放内容，样式平铺顶层（`size/color/bold/align/max_lines/line_height/padding`）；禁 `content`、禁嵌套 `style`；框高 ≥ 字号×行高×行数（40px×1.15×2 行需 ≥92px）；行长 CJK ≤38 字/拉丁 ≤75，超 2× 阻断——缩字号不算修复，拆句或收窄版心才算 | production-contract.md §Spec |
| 填充 | `{"fill": {"type": "solid\|gradient\|none", ...}}`；无效 fill 按编译错误迁移，不会默认变蓝 | production-contract.md §Fill Contract |
| 图表数据 | 每行 `label` + 有限数值 `value`；`source/unit/period/basis` 分开声明、缺一即 error；同 metric 全 deck 单位一致；总和≤0 的构成图、非正进度上限、负值冒充正值都是 error；标题写洞察不写字段名 | production-contract.md §Chart data contract |
| focus | 每页唯一 `page_intent.focus`（绑定元素 id）；焦点文字需 ≥40px 或领先第二大文字 ≥1.25×；其他元素面积 ≤ max(2×焦点, 25%画布)；落任一版面轴线（1/4、1/3、1/2、2/3、3/4、0.382/0.618）记加分 | art_critic.py（`STATEMENT_SIZE/FOCUS_LEAD/FOCUS_AREA_LEAD/AXIS_LINES`） |
| 密度与节奏 | 占用带：sparse ≤0.60 / balanced 0.65–0.75 / dense 0.75–0.85（`_content_occupancy`）；相邻同密度页需实测墨迹差 ≥0.10，标签变了差 ≤0.03 判空转；连续三页同密度同能量 = RHYTHM_FLAT | art_critic.py（`RHYTHM_*`） |
| 记忆锚点 | 每页一个机器可指认锚点：≥40px 文本 / 图表 `highlight` / 环心 KPI / `target` 线 / sparkline / 瀑布小计 / image hero；图表内部大数值**不算**（检测器只看声明） | art_critic.py（`_memory_anchor`） |
| 色彩 | `color_intent: [brand, emotion, hierarchy]` 必须声明；Accent ≤5%（渲染实测）；色相族 ≤4（30° 一档）；Accent 与主/辅色相差 ≥12°；同图表类型跨页标签规格一致（>1.25× 判漂移） | guard.py 色彩纪律 + themes.md |
| 网格 | 1280×720，8 单位（`primitives.GRID_UNIT`）；**Normalizer 自动吸附**（x/y 就近、w/h 向上），手工对齐不再是你的职责；`grid_exempt: true` 可豁免 | normalizer.py + production-contract.md §Spec Normalizer |
| 媒体 | 图片须有功能（context/emotion/proof/hero）；数据/表格/流程/结构页永不出图；背景画心免检需覆盖 ≥60% + 遮罩 ≥0.20；每页媒体 ≤1、阅读文本 ≤4、圆角容器 ≤4（超即 Card Wall） | SKILL.md 媒体闸门 + asset_prompt.py |
| 可读性 | 渲染实测「文字 vs 其下方底」：正文 <4.5:1 提示，任何角色 <3.0:1 阻断（READABILITY_FAIL）——色板合法 ≠ 物理可读，只有像素证据能暴露 | qa.py（`text_contrast` 域） |
| 生成前风险 | draft/review 第一屏的 pre-critic 报告就是修单：8 类风险各带根因/预防/预测失败码；**先修 pre-critic 再谈渲染** | design_intelligence.py（`pre_critic`） |
| 设计经验 | `recall_dna(brief)`（route 内联）命中即用其空间/色板/图表人格/禁用信号做基线；`record_dna` 仅 PASS 后调用 | memory/design_dna.json |
| 版式选型 | 同页 3 候选 spec 级比较：`layout_search.search()` 五维打分（层级/留白/锚点/节奏/品牌契合），选优后起草；原型 = 构图算子的驻点，不是模板 | layout_search.py |
| 设计理由 | 每页可选一句 `design_rationale`（选择 × 理由 × 否决项，声明层）；修正时先验「意图是否被几何兑现」，`record_dna` 时作为决策出处 | design-intelligence.md §Design Intent |
| 文本溢出 | 预防优于警告：`auto_fit: true` 按阶梯吸附（padding→行高→字号→重写）；未声明者编译器仍只警告 | design_intelligence.py（`apply_fit_ladder`） |
| 修订 | 读 `director_verdict.primary_lever`；**1 根因 = 1 轮**：`batch.fix_this_round`（同根因杠杆）一次修完一次验证，`batch.deferred` 排队下轮；修完跑一轮 QA 再看下一条 | art_critic.py（`_director_verdict`） |
| 发布 | `qa.py --mode release`（= --manifest）：QA ≥90 **且** Critic ≥90 **且** 0 硬门槛 **且** 全量像素；revision_count 必须来自真实修订流水；报告盖 `source_spec_hash`，对不上 → BLOCKED | production-contract.md §Release Manifest |

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
- 媒体闸门：图片必须有功能（context / emotion / proof / hero）；只有 Hero、品牌叙事、情绪与产品页可要图，数据 / 表格 / 流程 / 结构页永远不给图。整幅背景画心声明 `layer: background` 并自带 `overlay` 内容保护，可不拆内容盒、不计入媒体预算；**免检需要资格**：覆盖 ≥60% 画布且遮罩不透明度 ≥0.20（或显式 `readability_exempt`），overlay 无法解析按缺失处理；资格不足的「伪背景」按普通内容对象对待，并被 `BACKGROUND_DISGUISED` 点名。每张图片仍须给出主体、镜头、构图、留白锚点与裁切要求。背景是空间与阅读引导，默认低能量，主刺激最多一项、辅刺激最多一项。卡片不是默认容器；优先使用空间分组、发丝线、字体层级和留白关系。布局允许 Executive / Editorial / Data Intelligence / Comparative / Narrative / Spatial 等语法，但同一 deck 共享网格、版心、来源区和安全区，仅改变重心、比例、阅读轴与留白角色。出图时序链：闸门通过后、compile 之前，只对 `route.assets.generate` 中的页面逐页调 `asset_prompt.py`（先 `validate_asset_card` 查漏项）组装提示词 → 喂图像模型 → 图落盘后才 compile；设计推导与资产两条线并行，只在 `qa.run_qa` 汇合一次。
- 完成标准：spec 可独立编译；无 `TEXT_FIELD_*` / `data_integrity` error。

### P4 关键细节优化：最小修正

- 顺序：`删除 → 简化 → 恢复空间 → 重构重心 → 替换媒体 → 微调装饰`。不得用缩字号、堆色彩或加背景修复高层问题。
- 修正纪律：**1 根因 = 1 轮**。读 `director_verdict.primary_lever` 与 `verdict.batch`——`fix_this_round` 是 primary 同根因的全部杠杆（如主题对比度引发的 READABILITY + contrast 维度 + chart_muted 提示），一次修完、一次验证；`deferred` 是不同根因，严格排队下轮。归因不破坏：同组 = 同一个「为什么」。声明字段（density / insight / focus / 备注）修改不触发重渲染（`classify_spec_change` 判 narrative），批量改完再验证。

### P5 质量检查：生产链 + 发布判断

- `Normalizer → Guard → Compile → Render Evidence → Deterministic QA → Art Critic → Revision` 是**逻辑阶段顺序**；执行入口是**执行模式**：`qa.py --mode draft`（零渲染，默认）/ `--mode review`（关键页∪受影响页，Critic 待稳定）/ `--mode release`（= `--manifest`，全量 + Critic + Manifest），`run_qa` 已内联 normalizer + guard + compile + render，不要独立串行跑多个 CLI。最终渲染是判断依据；检查安全区、拥挤、重心、背景竞争、图表关系、低级设计错误和跨页一致性。任何修正后重新执行完整链路，并记录 observation、minimal_fix、recheck 与 revision_count（必须来自真实修订流水，不是占位 0）。QA 与 Art Critic 报告各自盖 `source_spec_hash` 自证来源，Release Manifest 核对不通过就降为 `BLOCKED`。
- 三不跑：预检不干净不渲染（先 `guard.py --preflight`，12 页 0.2s）；迭代期不跑 Critic（draft 恒不跑，review 待布局稳定自动介入，发布前 release 全量跑）；声明修改不跑全量（`classify_spec_change` 判 narrative → 编译与渲染全跳过）。
- 硬门槛优先于平均分。只有真实渲染证据存在、无阻断错误且所有必需报告完成时才可为 `PASS`；缺少真实渲染证据只能为 `PREVIEW_ONLY`；存在可修复问题为 `REVISE`，存在输入/事实/编译等阻断问题为 `BLOCKED`。状态只能使用 `PASS`、`REVISE`、`BLOCKED` 或 `PREVIEW_ONLY`。

## 按需加载

| 当前任务 | 首先读取 | 主要产出 |
|---|---|---|
| 新建或重构 deck | `scripts/route.py`（先分类）+ `references/design-intelligence.md` | 执行路径、页面家族与密度曲线、Strategy、Direction、Story Map、Page Intent |
| 落地视觉系统 | `references/design-system.md`、`references/themes.md` | Theme DNA、页面 spec、媒体 brief |
| 参考案例校准 | `references/evidence-library.md` | Evidence Cards、可执行规则、反例边界 |
| 评分与阈值调优 | `references/production-contract.md`（评分体系总览与调参）、`references/benchmark-calibration.md`（阈值校准方法） | 评分口径、penalties/thresholds 调参、系统性短板、阈值校准 |
| 编译与发布 | `references/production-contract.md` | PPTX、Render Evidence、QA、Release Manifest |
| 图像资产 | `scripts/asset_prompt.py` 与生产契约中的 asset contract | 资产提示词、安全区、溯源 |

不要一次性加载全部主题、全部资产卡或全部脚本源码。脚本默认按入口调用，不把源码全文复制进上下文：`compiler.py` 是唯一编译入口，`qa.py` 是完整质量流水线入口（`run_qa` 内部已按序执行 guard → compile → render，不要再单独串行跑 `guard.py` / `compiler.py` / `qa.py`，否则 guard 与 compile 各执行两遍；只有需要看某一阶段的独立诊断报告时才单独调用该脚本），`guard.py` 只在需要解释静态规则时直接调用，`render_check.py` 只在需要渲染证据时直接调用，`art_critic.py` 只在需要审美批评时直接调用，`asset_prompt.py` 只在 P3 媒体闸门通过后直接调用（为 assets.generate 的页面组装提示词，不管该不该出图）；先读 `production-contract.md` 的对应小节，再运行脚本。迭代期「看一眼布局方向」用 `ghost.py`（~1ms/页，不起 LibreOffice），真渲染只留给收口与发布。任何脚本输出都保存为 JSON 摘要，避免把实现源码或重复诊断灌入上下文。

**任务 → 文件 → 调用 路由表**（上下文预算的唯一执行口径；不要超出本表读取）：

| 任务场景 | 读取（精确到小节；80% 情况查 Runtime Contract Map 即可） | 调用 | 渲染 | Critic |
|---|---|---|---|---|
| 初稿 / 探索 / 多方案 | Runtime Contract Map + `design-intelligence.md` | `route.plan_deck`（含 DNA 召回）→ `layout_search.search` 选版式 → spec（可 `auto_fit`）→ `qa.py --mode draft`（零渲染，**第一屏读 pre-critic 风险并先修**） | 否（方向用 `ghost.py`） | 否 |
| 只改文案 / 洞察 / 备注 | Runtime Contract Map「文本元素」行 | `qa.py --mode draft`（classifier 判 narrative，编译渲染全跳过） | 否 | 否 |
| 方向确认 / 改布局、主题、图表 | 对应 Map 行 + `production-contract.md` 的 Layout Collision + Revision | 先 `ghost.py` 看方向，再 `qa.py --mode review` | 关键页 ∪ 受影响页 | 稳定后自动 |
| 出现图表 | Map「图表数据」行 | 走当前场景的调用 | 随场景 | 随场景 |
| 出现媒体 | `production-contract.md` 的 asset contract + `asset_prompt.py` | P3 闸门后调 `asset_prompt` 出图，再走当前场景调用 | 随场景 | 随场景 |
| 发布审校（唯一全量） | `production-contract.md` 的 Release Manifest / Render Evidence 小节 | `qa.py --mode release`（qa_level=3 全量 + Manifest） | 是 | 全量 |

（legacy `--quick` / `--key-pages` / `--manifest` 仍是合法别名，语义分别等于 `--mode draft` / `--mode review` / `--mode release`。）

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

事实与语义完整优先于构图，构图优先于风格，风格优先于装饰。默认 16:9、1280×720、8 单位网格、最多 2 个字体家族、字号阶梯每页 ≤4 级（唯一真源见 `design-intelligence.md`）、3 个字重等级、每页唯一焦点层主焦点、Accent ≤5%、图表一个强调点、来源不可省略。数据页默认低能量；连续页面不得使用相同密度与相同重心；空间不足时拆页或删减，不压缩可读性。

数值图表必须显式声明 `source`（来源）、`unit`（单位）、`period`（期间）、`basis`（比较口径）；同一指标（`metric` / `series_name` 键）必须在整套 deck 中保持单位一致。标题写洞察不写字段名。

## 质量门

Deterministic QA 只判断可编译、可渲染、可读、可编辑、无越界、无失真和满足硬约束；Art Critic 另行判断层级、平衡、对齐、对比、节奏、一致性、情绪影响、记忆点和专业完成度。禁止用技术 QA 分数代替设计质量。任何来源遮挡、事实不完整、图表失真、关键文字不可读、资产侵入安全区、编译失败或主题与内容不匹配，均不得因分数高而发布。

修正时先读 `critic.deck_notes.director_verdict`：`headline` 是总监一句话判断，`primary_lever` 是本轮首要杠杆，`root_cause_groups` 是根因分组，`batch.fix_this_round` 是本轮同根因要批量修的杠杆集合，`batch.deferred` 是后续轮次；修完跑一轮 QA 再看下一条，禁止跨根因混修或逐条追分。

最终交付至少包含：可编辑 PPTX、QA JSON、Render Evidence（可用时）、Critic Report（含 verdict）、Revision Log 和 Release Manifest。
