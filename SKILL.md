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

## 按需加载

| 当前任务 | 首先读取 | 主要产出 |
|---|---|---|
| 新建或重构 deck | `scripts/route.py`（先分类）+ `references/design-intelligence.md` | 执行路径、页面家族与密度曲线、Strategy、Direction、Story Map、Page Intent |
| 落地视觉系统 | `references/design-system.md`、`references/themes.md` | Theme DNA、页面 spec、媒体 brief |
| 参考案例校准 | `references/evidence-library.md` | Evidence Cards、可执行规则、反例边界 |
| 评分与阈值调优 | `references/scoring.md`、`references/production-contract.md` | 评分口径、penalties/thresholds 调参、分域扣分明细 |
| 编译与发布 | `references/production-contract.md` | PPTX、Render Evidence、QA、Release Manifest |
| 图像资产 | `scripts/asset_prompt.py` 与生产契约中的 asset contract | 资产提示词、安全区、溯源 |

不要一次性加载全部主题、全部资产卡或全部脚本源码。**设计规划阶段必须读取所选主题在 `references/themes.md` 中的相关条目，并将其转换为 `spec.theme`；运行时编译阶段不读取主题 Markdown，只消费已经完成的 `spec`。**主题只改变视觉人格，不改变共性系统，也不得改写页面逻辑、数据口径或图表准确性。脚本默认按入口调用，不把源码全文复制进上下文：`compiler.py` 是唯一编译入口，`qa.py` 是完整质量流水线入口，`guard.py` 只在需要解释静态规则时直接调用，`render_check.py` 只在需要渲染证据时直接调用，`art_critic.py` 只在需要审美批评时直接调用；先读 `production-contract.md` 的对应小节，再运行脚本。

### 快速路径与上下文预算

1. **已有 spec / 只修布局**：只读取 `production-contract.md` 的 Spec、Layout Collision 和 Revision 小节，运行 `guard.py` → `compiler.py` → `qa.py`；不要读取全部主题与全部脚本。
2. **新建 deck**：先读取 `design-intelligence.md`；确定主题后，读取 `design-system.md` 与 `themes.md` 中对应主题条目，并把结果固化到 `spec.theme`；只在出现图片或图表时读取对应脚本说明。不要加载未选主题的完整内容。
3. **发布前审校**：直接运行 `qa.py` 的完整入口；仅当 QA 有 `render_missing` 或需要解释美学问题时，再补运行 `render_check.py` / `art_critic.py`。
4. **修改后**：只重跑受影响页面的编译、渲染与 QA；发布前必须再跑一次全 deck。任何脚本输出都保存为 JSON 摘要，避免把实现源码或重复诊断灌入上下文。

## 执行路径与验证层级

先分类再决定复杂度。路径与层级只改变**预算与测多少**，不改变任何阈值（阈值唯一来源：`art_critic.py` 导出常量，Guard 预检与之同源）。

| 决策 | Fast：内部汇报 / 数据 / 产品 / 年终总结 | Advanced：发布会 / 品牌 / 高端视觉 |
|---|---|---|
| 图像资产 | ≤2：cover / brand story / closing | ≤4：可加 statement / proof，逐页绑定留白锚点 |
| 数据·对比·流程·结构页 | 闸门同源：不出图、不给预算（背景画心不计入预算） | 同左 |
| 渲染与批评 | `--fast`（dpi 72），Critic 只在收口跑 | dpi 96，每轮改动都过 Critic |

- **先预检再渲染**：`guard.py <module> --preflight`（12 页 0.2s）静态复现 Art Critic 的确定性门槛（焦点尺度与压制、媒体/文本预算、卡片墙、疏密与节奏、非对称声明），返回 `slide / code / observation / minimal_fix`；干净了才付渲染成本。
- **验证分级**：Level 1 `--quick`（不渲染，判结构）→ Level 2 `--key-pages`（只测封面、收尾、含图含表页）→ Level 3 全量（发布唯一口径）。Level 1/2 的状态上限是 `REVISE`，`release_eligible=False`，Critic 记 `PIXEL_COVERAGE_PARTIAL`。12 页实测：0.7s / 3.4s / 4.6s。
- **不重复计算**：三处复用只认一个判据——「会不会改变量到的数字」。① 页级像素缓存（键 = 本页投影 + 主题投影 + 画布 + dpi + 页内图片指纹 + 渲染器身份 + `page_intent.focus`）；② PPTX 逐字节未变则复用上一轮 PDF，不再调用 soffice（实测省 1.7s）；③ `page_intent` 的叙述字段 / `source_zone` / 备注既不产出像素也不参与量测，编译视图一致时连 `compile_deck` 都跳过。12 页实测：改一句 insight 后整轮 4.8s → 0.01s，Level 2 收口后升 Level 3 由 2.57s → 0.82s，绝对冷测仍 4.7s 且与热测指标逐位一致。`--no-cache` 一律绕过三处复用，也不写回任何记录。
- **并行硬上限 2**：渲染阶段 poppler 转换与像素测量串成一条流水、块间最多 2 worker（按 CPU 收敛，页数 <4 关闭）。设计推导与资产/渲染两条线只在 `qa.run_qa` 汇合一次，禁止逐页往返通信与循环等待。实测成本链为 guard 2ms → 编译 179ms → soffice 1.70s → pdftoppm 80ms/页 → 像素量测 75ms/页，除渲染外没有第二条可重叠的独立流，因此不再增设进程内线程。
- **色彩与图表纪律（deck 级）**：单页合规不等于成套。Guard 另核三件——全套色相族 ≤4（30° 一档，纸色与灰阶不计）、Accent 与主/辅色色相差 ≥12°（否则强调色只是主色的重复）、同一图表类型跨页共用一套标签规格（>1.25× 判漂移）。互补且等彩度的两色渐变提示「混成脏灰」，同族低对比渐变是留白手法、不打击。焦点落位：中心对齐中线/三分线/黄金分割线任一条时 Critic 记一次层级加分（已有正向证据不叠加），完全不上线只在预检提示、不判罚——高级设计是「在正确的位置留下正确的东西」，不是把留白填满。
- **方向即参数**：只传 `content_type / design_direction / quality_level`，色彩、材质、光线、图表风格、动效与构图语法由方向人格派生。升档需理由；不得用 Fast 路径跳过事实口径、防遮挡与图表数据合同。

## 强制决策流程

严格按以下顺序执行，不得先选模板、颜色或图片：

1. **冻结输入并分路**：记录受众、观看场景、目的、页数、交付格式、品牌限制、事实来源、时间、单位、口径和不确定性；用 `route.plan_deck(brief)` 得到执行路径、逐页内容类型、密度曲线与资产预算，并把它当作后续所有调用的默认值。
2. **建立 Strategy**：写出 audience、decision、tension、narrative_arc、emotional_target。把 `claim / evidence / implication / action` 分离。
3. **建立 Direction 与 Visual DNA**：定义 visual_world、composition_grammar、type_voice、color_behavior、media_role、background_scene、motion_posture 与 forbidden_signals；把光线、材质、透视、层级和对比关系作为全 deck 的统一空间假设。不要把风格参考名当作模板或事实。
4. **编排叙事**：先建立整套 deck 的 `opening → context → problem → insight → evidence → solution → proof → vision → closing` 阶段序列，再为每页写 `insight`、`narrative_role`、`focus`、`reading_order`、`energy`、`density`、`empty_space_role`、`rhythm_stage` 和 `continuity_token`。一页只保留一个可复述结论，并为页面家族声明使用场景、内容结构、视觉重点和禁用情况。
5. **选页面家族**：内容任务决定 Family；主题只决定其视觉表达。先定场景，再决定对象、图片、光线与材质。
6. **生成 spec**：主题 token 进入 `spec.theme`；页面内容、背景、图表、来源和叠加层进入 `slides[]`。先完成数据分析与洞察提取，再选择诚实的原生可编辑图表；无法表达单一关系时使用文字或表格。元素填充优先使用 `{"fill":{"type":"solid|gradient|none",...}}`；历史字符串与 `{color, opacity}` 可兼容，但无效 fill 必须按错误提示迁移，不能依赖默认蓝色。图表数据必须逐行提供 `label` 与有限数值 `value`，单位、期间、比较口径、来源和 `display` 格式分开声明；缺失、非数值、非有限值、空数据、无效高亮索引和无效构成总和必须在 Guard/Compile 阶段暴露，禁止静默补零或伪造单位。每个文本框还要声明足够的 `width / height / max_lines / line_height / padding`；不要把字号缩小当作溢出修复。行长按盒宽与字号可测：CJK 每行 ≤38 字、拉丁 ≤75，超过上限两倍按阻断处理——缩字号不算修复，拆句或收窄版心才算。
7. **治理媒体与背景**：图片必须有功能（context / emotion / proof / hero）且通过资产闸门——只有 Hero、品牌叙事、情绪与产品页可要图，数据 / 表格 / 流程 / 结构页永远不给图；整幅背景画心声明 `layer: background` 并自带 `overlay` 内容保护，可不拆内容盒、不计入媒体预算；**免检需要资格**：覆盖 ≥60% 画布且遮罩不透明度 ≥0.20（或显式 `readability_exempt`）。面积不够、遮罩虚设的「伪背景」按普通内容对象对待，并被 `BACKGROUND_DISGUISED` 点名。每张图片仍须给出主体、镜头、构图、留白锚点与裁切要求。背景是空间与阅读引导，不是填充；默认低能量，主刺激最多一项、辅刺激最多一项。卡片不是默认容器；优先使用空间分组、发丝线、字体层级和留白关系。布局应从内容选择版式，不从模板选择内容：允许 Executive / Editorial / Data Intelligence / Comparative / Narrative / Spatial 等布局语法，但同一 deck 要共享网格、版心、来源区和安全区，仅改变重心、比例、阅读轴与留白角色。
8. **执行生产链**：`Guard → Compile → Render Evidence → Deterministic QA → Art Critic → Revision`。最终渲染是判断依据；检查安全区、拥挤、重心、背景竞争、图表关系、低级设计错误和跨页一致性。任何修正后重新执行完整链路，并记录 observation、minimal_fix、recheck 与 revision_count（`revision_count` 必须来自真实修订流水，不是占位 0）。QA 与 Art Critic 报告各自盖 `source_spec_hash` 自证来源，Release Manifest 核对不通过就降为 `BLOCKED`：过期或旁路生成的「PASS」不能进入发布判定。
9. **最小修正**：`删除 → 简化 → 恢复空间 → 重构重心 → 替换媒体 → 微调装饰`。不得用缩字号、堆色彩或加背景修复高层问题。
10. **发布判断**：硬门槛优先于平均分。只有真实渲染证据存在、无阻断错误且所有必需报告完成时才可为 `PASS`；缺少真实渲染证据只能为 `PREVIEW_ONLY`；存在可修复问题为 `REVISE`，存在输入/事实/编译等阻断问题为 `BLOCKED`。状态只能使用 `PASS`、`REVISE`、`BLOCKED` 或 `PREVIEW_ONLY`。

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

文本、图表、图片与来源区之间必须保留明确的几何安全距离。正文与正文的有效墨迹不得相交；正文与图表/图片即使外框相交也必须显式声明 `allow_overlap: true` 和 `overlap_reason`，否则按碰撞处理。来源、方法、轴标签和图例属于独立低权重区域，不得被主体覆盖。图表若使用直接标注，就关闭重复图例或坐标读数；标签密度超过可读阈值时拆图、减少类别或改用表格，不自动压缩字体。可读性不只按声明色对撞：渲染后逐页实测「文字 vs 其下方那块底」，正文级低于 4.5:1 提示、任何角色低于 3.0:1 阻断（`READABILITY_FAIL`）。跨页节奏同样以实测墨迹为准：占用率真的变了就算成立，只改 `density` 标签而墨迹不动要扣分。渲染后优先修正 `READABILITY_FAIL`、`OVERLAP`、`SOURCE_COLLISION`，再处理风格。

## 图表执行边界

图表脚本只负责**确定性渲染与防御性校验**，不替用户补充事实、不自动改写数据、不自动缩字号、不用装饰掩盖拥挤。原生图表保留编辑能力；形状化图表只用于原生图表难以诚实表达的关系。直接标注与坐标轴承担同一读数职责时只保留一条通道；标签必须避开线、节点、轴和其他标签。瀑布图零轴必须按数据范围映射，构成图总和必须大于零，进度图上限必须为正数，排序/气泡/堆叠图不得将负值悄悄当作正值。

## 硬边界

颜色方向必须说明 `color_intent: [brand, emotion, hierarchy]` 中当前优先职责。卡片只允许用于数据模块、核心指标或特殊强调；圆角容器超过 4 个或成为主要结构时，必须触发 Card Wall Critic。

事实与语义完整优先于构图，构图优先于风格，风格优先于装饰。默认 16:9、1280×720、8 单位网格、最多 2 个字体家族、4 个字号等级、3 个字重等级、每页一个 L4 主焦点、Accent ≤5%、图表一个强调点、来源不可省略。数据页默认低能量；连续页面不得使用相同密度与相同重心；空间不足时拆页或删减，不压缩可读性。

## 质量门

Deterministic QA 只判断可编译、可渲染、可读、可编辑、无越界、无失真和满足硬约束；Art Critic 另行判断层级、平衡、对齐、对比、节奏、一致性、情绪影响、记忆点和专业完成度。禁止用技术 QA 分数代替设计质量。任何来源遮挡、事实不完整、图表失真、关键文字不可读、资产侵入安全区、编译失败或主题与内容不匹配，均不得因分数高而发布。

最终交付至少包含：可编辑 PPTX、QA JSON、Render Evidence（可用时）、Critic Report、Revision Log 和 Release Manifest。
