# 变更记录

## 7.3.2 · Memory Loop Closure（案史闭环 · 终审方向落地）

五轮复审后唯一合理的新投入：让 **案史记忆** 成为判断增长的通道（代码侧已收口）。
差距盘点：DNA 库 14 条、recall 已接入路由、文档指导齐全——但 release 一张张
PASS 落盘后**没有任何信号告诉系统"这一局值得沉淀"**，写入口长年闲置。

- `vao._dna_recall_hint`（新，~35 行）：release PASS 且 plan 的
  `dna.matched=None`（recall 找不到相邻案史，本局是新方向）时，输出追加
  **一行**沉淀提示。matched 非空全静默——库已覆盖的案子不堆提示。
- 纪律保持：**不自动写 DNA**（写坏的记忆比不写更贵——沉淀是判断动作）；不
  加新命令（沿用既有 `vao dna --add` 唯一写入口）；不加新状态/条目结构。
- 双向实测：bench 年案命中 `comparison_single_decision` → 提示静默
  （3 行输出，零膨胀）；全新"生物燃料初创路演"路径 → hint 正确亮起。
- 241 → 243 绿（+2 钉：集成 PASS 提示条件闸 + hint 门完备性：非PASS / 非
  release / matched / 无 plan 全静默）。

## 7.3.1 · Round 4 / Self-Audit of R3 （R3 引入镜像的自审清缴）

对第四轮七层复审先审自己：R3 的 `resolved` 决策对象当时落了**三份镜像**
（manifest 条目顶层 + 条目 meta + prompt 缓存每条 meta），违反"同一事实只存
一份"。本轮只清镜像与死物，零行为变化：

- `resolved` 单存储：meta 副本删除，manifest 条目顶层是唯一落盘处；prompt
  缓存失效判断从逐条 meta 检查改为**文件级 schema 门禁**（v1 旧缓存整票废）。
- `compile_cache.compile_reuse`：删除不可达的短指纹兼容分支（`len<64` 已在
  上游 return None——该 else 在逻辑上跑不到）。
- `primitives.IDENTITY_SCHEMA`：零引用死常量（v6.5 身份统一期占位，全库各
  消费者均自携具体 schema）。
- 全库零死亡函数 / 零存疑常量（第四轮普查），未深读的 5 个模块
  （compile_cache / intent_compiler / pipeline / design_intelligence /
  run_evidence）全部通过精读——职责单簿、无重复判断。

240 → 241 绿（+1 钉：resolved 单存储）

## 7.3.0 · Decision Quality Round / Visual Decision Object（决策期单源结算）

- `resolved` 单存储：meta 副本删除，manifest 条目顶层是唯一落盘处；prompt
  缓存失效判断从逐条 meta 检查改为**文件级 schema 门禁**（v1 旧缓存整票废）。
- `compile_cache.compile_reuse`：删除不可达的短指纹兼容分支（`len<64` 已在
  上游 return None——该 else 在逻辑上跑不到）。
- `primitives.IDENTITY_SCHEMA`：零引用死常量（v6.5 身份统一期占位，全库各
  消费者均自携具体 schema）。
- 全库零死亡函数 / 零存疑常量（第四轮普查），未深读的 5 个模块
  （compile_cache / intent_compiler / pipeline / design_intelligence /
  run_evidence）全部通过精读——职责单簿、无重复判断。

240 → 241 绿（+1 钉：resolved 单存储）。

第一轮结构减法（7.2.1/7.2.2）做完之后，第三轮做的是**判断升维**：把视觉语言
（光 / 动势 / 材质 / 融合）的结算从渲染期拼合，前移到决策期落盘。起因是三轮
复审中最贵的一块实测伤口——光语互斥的缝合把页面能量判断一起灭口了：
`energy=high` 与 `energy=low` 的 prompt 逐字节相同，页面能量判断被静默吞掉。

- **asset_prompt.resolve_asset_card（新，决策函数）**：一张卡的视觉语言一次
  判完。光语五来源封闭枚举：declared / direction / fallback /
  photo_discipline / phrase_fallback，一格条件一来源，互相不可能并存；
  结果 resolved 随清单落盘。
- **build_asset_prompt 退化为纯序列化器**：不再做任何互斥调停；函数体内
  零决策常量引用（静态钉）。legacy 卡片缺 resolved 时当场补判——
  缺 resolved ≠ 错误（out-of-tree 独立调用继续成立，用户裁决 §6）。
- **ENERGY_LIGHT_VARIANTS（能量调谐表）**：只替换不强加，源限 4 组路由方向
  预设光语（强弱两头各一句，medium 保留原句）；declared 自由文本永远赢、
  能量不着一字。页面能量判断从此真的抵达像素——实测高能量封面页
  `energy_applied=true`，光语 =「even ambient light with one deliberate
  focal gradient」。
- **manifest 是唯一视觉决策源**：生成条目带 resolved；prompt 缓存升 v2，
  meta 里没有 resolved 的旧条目静默失效重算（旧 prompt 会掩盖能量调谐
  回到像素）。
- 行为 parity：275-fixture 差分矩阵，32/32 差异全是有意的能量调谐，0 意外；
  234 基线 → 240/240 绿（+6 钉）。

约束保持（用户施工指令）：不新增文件 / 不新增架构层 / 不新增 Guard·Warning·
Reference / 不与老 resolver 双路径并存。build_asset_prompt 与 resolve_asset_card
共存但只有一个决策者：build_asset_prompt 只做翻译或调用同一个结算函数。

## 7.2.2 · Practitioner Audit Round 2 / Conversation Diet（对话输出压缩）

第二轮复审（扫描验证 + 交互压缩），不新增能力面：

- **check 输出压缩**：PASS 路径 6 行 → 3 行（`PASS · PASS` 状态重复消除；
  「无阻断」「复用路径」并入状态行；manifest 与 repair packet 合并为一条
  artifacts 行）。BLOCKED 路径的 fix 行一行不省——那是唯一需要被读的。
- **run 输出压缩**：删除与 plan 完成行重复的 assets 完成行；run 产出合并为
  一条状态行（plan / skeleton / manifest+unique_calls 一次说完）。
- 顺带修复：资产链早期中止时模式名显示 None（现回落调用侧 mode）。
- 全库死亡函数扫描：生产模块零死亡函数（含排除 selftest 后）；
  `ghost.PREVIEW_MIRRORED` 经复核确认为契约锚（防图表类型被静默自动升级为
  同形镜像），保留。

## 7.2.1 · Practitioner Audit / Wound Sutures + Doc Truth（七层复审收口）

以对全库的七层端到端复审（Intelligence / Context / Architecture / Execution / Design /
Production / Verification）为据，只做缝合与减法，不新增能力面：

- **亮度断崖升级阻断（QC 物理判据缝合）**：资产实测亮度与声明底色落差 ≥0.50 且画面
  落在极端区时，`brightness_balance` 从 advisory 升级为 blocking。实证伤口：一张
  全黑封面图（亮度 0.00 vs 声明 #F5F4F1 的 0.90）可以 accept_with_advisory 出货，
  深字压黑图对比 ≈1.4:1、对话零信号。暗色沉浸方向声明的是深底色（|Δ| 天然 <0.5），
  豁免不需要额外标志——落差本身就是判据；draft 期仍允许一次定向重出。
- **光语互斥无条件化**：`build_asset_prompt` 的句式光（LIGHT_PHRASES / ENERGY_PHRASES）
  此前只在「photo 接管 / 作者显式声明」时让位，方向种子带来 lighting 时三条光语并存
  （实测封面 manifest：`flat even ambient` + `soft directional light` +
  `one dramatic light source` 同注）。现在卡片已有任何光语时句式光一律不注。
- **同文件双 I/O 合并**：失败路径先 `_stale_manifest_write` 再 `publish_failure` 两次写
  同一 manifest 的旁路已合并为一次落盘；`route._color_family` 同包 ImportError 死防御
  删除（真缺失时应大声失败而不是让 13 族色彩方向静默全灭）。
- **零消费者字段删除**：QC 决策的 `triggers_review / triggers_release`（恒 False、
  全库零读者）移除；`qa.release_manifest` 的「本稿有没有图」改吃资产链已算好的
  `image_count`，不再对 spec 二次扫描。
- **文档债三处**：README 砍半（删除与 SKILL/CHANGELOG 重复的版本叙事、命令表与
  目录树；不再维护会过期的数字——版本号唯一真源为 `pyproject.toml`，自检项数不再
  写进 README）；删除指向未随仓库分发之审计文档的死引用；`asset-workflow.md`
  的 QC schema 改为以代码常量 `QC_REPORT_SCHEMA` 为锚（此前写的是代码已拒收的
  旧 schema——旧 schema 串已入文档禁用词表，防回流）。
- 版本对齐：pyproject 升至 7.2.x 并自此成为唯一版本真源；CHANGELOG 补齐 7.2.0 条目。

## 7.2.0 · Seven-layer Audit / Zero-consumer Cleanup

以七层审核完成结构化减法（审计结论并入各条与回归网）：

- 删除意图层零消费者镜像（`compile_brief` 的 design_intent/strategy_seed 等嵌套镜像
  整体删除，同输入同 plan 行为不变）；
- 删除 ROUTES 死列、`recommend_mode` 死链、`run --build`、compiler 内置 guard 死路径
  与三个死/重复 guard 检查（checks/guard_rules 参数与内置 guard 块、slide 级
  safe_zones 无 producer 判定、geom_occlude 与两个重复判定）；
- QC 像素判定跨 draft→release 复用（phase 移出复用键，仅 retry 策略按阶段重算）——
  同一事实不再量两遍；
- README 里的版本叙事与本条目一致（既往版本史已下移 CHANGELOG）。

## 7.1.0 · Case-led Audit / Medium Separation + Compact Asset Context

以 `PPT_CASE_003｜山止 SHANZHI` 15 页高端东方茶品牌融资路演为真实样本，复盘从 brief、资产生成、QC、编排到 release 的完整路径。

- 修正摄影资产被 `rice paper / 宣纸` 材质词误触发水墨闸门的问题；材质不再伪装成介质声明；
- 新增回归测试：摄影卡可以使用 rice paper 材质，但不会收到 `hand-painted ink-wash` 与 `no photographic shading` 的冲突指令；
- `vao.py assets` 默认只打印紧凑资产摘要，完整 prompt 改为显式 `--show-prompts`，避免把长 prompt/negative 清单灌入 Agent 对话；
- SKILL 增加图片首轮 QC 后的设计判断：一次定向修复仍不成立时，删除图片并改用 native composition；
- 生成骨架的构图 JIT 入口改指向 `references/design-judgment.md`，字段细节仍按需查 `design-system.md`；
- 版本统一为 `7.1.0`。

案例审计结论已并入本版回归网（审计源文档未随仓库快照分发）。

## 7.0.0 · Practitioner Audit / One Production Contract

以 `PPT_CASE_004｜CIRCA 纪时酒庄` 为真实端到端样本，完成 Intelligence / Context /
Architecture / Execution / Design / Production / Verification 七层审核。

- 删除 route 里无消费者的 deck-level `intent_interpretation` 镜像；
- 删除 route 里无人读取的 chart/text budget 镜像，只保留资产调用预算；
- full-canvas solid background shape 获得窄范围空间层资格，不再与 source zone 冲突；
- check 在资产 I/O 之前发现缺少 `python-pptx`，避免无效 QC 轮次；
- `make` 改为 `check` 的兼容别名，消除旁路绑定/Guard/compile/ghost 链；
- 新增 `references/design-judgment.md`，SKILL 改为更短的 JIT 导航；
- 完成文件、函数、规则、Context、Command 与交互的存废判断（审计源文档未随仓库
  快照分发，结论并入各条与回归网）；
- selftest 仍作为 CI 回归，不进入 Agent 默认 Context。

实战证据与停止条件并入发布门槛与回归网。


---

> **归档说明**：以下为历史账本压缩归档（2026-09，v7.3.2 后）。每版本只保
> **主题 / 代码级变更 / 案源 / 度量**四样；跨版本反复强调的哲学散文
> （删除>合并>简化>复用>新增、「同事实一次」、「判断归设计者」等）不再逐版复
> 述——那是方法，不是版本内容。全部治理判断与字段的权威现住所：`references/`。

## 6.5 · Context Diet + Zero-Loop Assets（上下文减法 34%、既有素材零回路、稳定指纹）

- 入门 Context 124.0KB → 82.0KB（−33.9%）：SKILL 砍掉与 references 的重复叙事
  （18,817→10,945）、brief 模板注释砍半、design-system/production-contract/
  design-craft 重写压缩；design-intelligence 逐字保留。字段/阈值/阻断码零删。
- 既有素材零回路：`prepare` 对字节已存在的规划资产自动登记 existing（保留规划
  身份与 prompt，不退化成 existing-<hash>）；`asset_source` 退化为来源注记。
- 方向预览 `--ghost-pages` 默认 4→24：≤上限全量，超出才采样。
- `stable_plan_sha` 排除全部运行态键（workflow 时间戳 + performance.planning_ms）：
  同输入重跑两次 plan 指纹字节相等。
- 代码减法：16,812 → 15,201 行（−9.6%），死分支/重复实现删除，220 项钉全绿。

## 6.4.4 · Editorial Data（系列色去重、accent 单占用、预览不发明装饰）

- 单信号色主题：premium 曾回退=accent，六档系列退化为三对同色（4 段甜甜圈两段
  同色实测）→ 系列色改走该色相明度阶梯（相邻 Δ≥0.05）。案源审计「重复着色」8→0。
- accent 双占用：高亮=accent 且 `series1`=accent 使高亮段与首序列同色 → 一处派生
  `ctx.series_palette(count, highlight)`，两条渲染路径共吃。
- ghost 不再替产物发明装饰：外框只属于占位/ABSTRACT 分支（"我不画"的边界）；
  扇区/堆叠段色与产物同一份 `series_palette`；多序列折线按序列分画不再摊成一条；
  面积图填充；顶点只在高亮/两端落；单序列高亮且基色==accent 时基色退图表 primary。
- 顺带：`color_to_hex` 缺 # 致 parse_token 静默回退灰 → `_rgba_color()` 直取。
- 钉值变化逐字节归因后重钉（仅 chart part 两色值不同可归因）；自检 220 项。

## 6.4.3 · Practitioner Feedback（假预览 / 相对亮度 / 身份不断链）

- 预览覆盖契约（最贵一条）：big_number_row/steps/timeline/waterfall 曾被柱图兜底
  画成假图（作者按假预览改了三页构图）→ 只画与产物 mark 同形的图形，未实现的
  类型如实写「预览不渲染」；两类归属（镜像/抽象）覆盖图表类型全集+运行期兜底。
- `brightness_balance` 改相对声明底色（|Δ|<0.18 同调不判过暗）——此前暗色沉浸方向
  的四张夜景图全被在反对方向；
- `contrast_suitability` 认 hex text_color（解析唯一 `primitives.text_is_dark`）。
- 既有素材保留规划身份不降级 existing-<hash>；阻断信息点名补救路径。
- 端到端用例补「brief→release 一次走通 + 骨架/清单同源指纹」两钉。自检 207 项。

## 6.4.2 · Evidence Validation + Ownership Closure（真实语料、run_qa 移出 QA、px→pt 单源）

- 真实语料验证替代结构推断：5 份真实 deck 走真链路。打磨稿零阻断；典型 AI 初稿
  data_* → BLOCKED 一次根因修复 → PASS 且 guard 四规则全消失（"修复后消失"真证据）；
  31 条规则在真实分布上 25 条零触发 → 存废判断一张不动，合成变体只证可达。
- `run_qa` 不再自己触发编译：QA 只剩消费面（9 纯函数），编排归 vao 唯一入口。
- `PT_PER_PX = 0.75` + `px_to_pt()` 唯一换算（12 编译 + 2 预览调用点）；先证
  产物 SHA 一致再合并。同值常量其余分类为「同数不同事实」未并。
- 产物字节未变；自检 202/202；五 KPI = 1/1/0/0/0。

## 6.4.1 · Convergence（单事实单归属 · 触发率仪表 · 去文档漂移 · 重复判断审计）

- 双阈值探测：14 处疑似重复 → 3 处真重复回收单源（CHART_LABEL_MIN_* /
  latin_word_match / LIGHT_BG_LUMINANCE），11 处为同数不同事实。
- Keyboard探针结论：Compiler 无第二套设计判断（34 个 warn 全为事实兜底）；
  唯一编排泄漏 = run_qa 缺报告时自编（记移交，下轮处理）。
- 触发率遥测（不入库）+ 收敛 KPI（测量1次/判定1次/引擎意见0/无消费Context0）。
- Reference 去漂移：SKILL 只导航，段级重复条目 3→0，新增防漂移钉。自检 201/201。

## 6.4.0 · Subtraction · Round 2（引擎只在两种时候发声）

判据收敛：**发声只来自 ①事实（装不下/重叠/读不出/声明缺失/键名没被读）②作者声明的
刻度（theme.constraints / rules）**。
- 撤整条行长执法（line_measure 误报装得下文本；容量另由 text_capacity 判）、图表
  容量上限、标签间距猜测、图例/眉标位置纪律、对比度 <3:1 软档（<1.8 弱字 warn 留）。
  规则 id 31 不变（N:1 映射）、发射点 84→77、hint 5→1。
- Guard × QA 允许清单：一事实一次测量、一次判定、一次报告；同码可多规则供给，
  不许两条测量供同码。
- Reference 路由 JIT 到节：查门槛+报告字段 14.2KB → 3.3KB。自检 200/200。

## 6.3.0 · Subtraction（删掉写死的判断与没人读的字节）

- 删除查表式答案 43 条条目（FAMILY_MOVES / COMPOSITION_BY_FAMILY+POOL /
  QUALITY_BUDGETS 及三个函数）——第一候选会被照抄，改为骨架给「待判断」项；
  selftest 反向钉（骨架不得再出现表生成的答案）。
- 家族词汇单源 FAMILY_TOKENS；字宽模型去双口径（guard 与 primitives.text_units）；
  删 5 个零消费者 plan 字段（plan 49,694→37,462B，逐页意图块 −58%）；
  热轮零字节读（凭证带 sha256 时 50.3MB 一个字节不读，fast 热轮 57–61ms → 38–42ms）；
  require_snapshot fail-closed；BLOCKED 不复用。
- 审计方法入档：静态「没人调」在本库会误报（DISPATCH 表派发），须运行时覆盖。
- 自检 200/200，产物 SHA 未变。

## 6.2.0 · Same Fact Once（身份层单源 + 账本 + 冷/热写进契约）

- 身份四类目单源（primitives.identity / digest_bytes·file_digest / witness 三件套 /
  engine_fingerprint）；消掉 QC sha256 平铺副本与产物三平铺字段（→ output_witness）。
- RunEvidence 一次 check 一份事实；COLD/HOT 契约成文（HOT=零重做、凭证不足自动
  降级留因；判定永远新鲜）。假账修复：整份预览复用时不再记"都画了"（页号清单唯一）。
- 量过但不做（python-pptx 内部 sha1 / strict 逐资产 sha256 / COLD 解码）逐项留档。
- 自检 198/198；fast HOT 61ms / strict HOT 107ms；产物字节未变。

## 6.1.0 · Runtime Subtraction（同一份事实只做一次）

- JSON 一轮读一次；资产字节哈希 QC 一次供四层（208MB→68MB）；QC 判定可复用
  （清单 SHA + 像素口径 + qc_engine 指纹 + 资产字节身份，任一不成立完整测量，
  冷 2790ms → 复用 55ms）；逐页渲染缓存（改一页重画一页，联络表纯函数复制）；
  解码底图交接给编译器；证据不重写；json_write mtime 推进修复同刻度假凭证。
- 自检 186→198；fast hot 55–63ms；产物 SHA 跨三轮未变。

## 6.0.0 · Subtraction & Judgment（关掉引擎的第二套判卷）

- 真缺陷修复：眉标要求逐字匹配 plan 词汇 → 每页警告（15 页 25 条）→ 只查在不在/
  位置稳不稳；措辞归作者。家族词表"能解析即合法"，拼错才留痕。
- 删引擎发明无人读字段：empty_space_role / rhythm_stage / reading_order /
  forecast_risk 层（65 行）/ strategy:{ } 空壳等；页骨架待填 7→5 字段，真判断只余
  insight + focus 二问。规则去重：min_font→typography、theme_fonts 4→1、
  metric_consistency error/warn/hint→1；规则名 36→35、调用点 96→92。
- 构图给可推翻备选；自检 186/186；基准稿 release PASS 逐字节同。

## 5.9.0 · Two-Minute Delivery（速度档 + 预算纪律）

- `--speed fast|strict`：fast = ≤1024 箱式降采样（安全区纹理仍原生分辨率）+ 快探针
  + 采样预览；全链 10.74s → 2.70s（strict 6.41s）。
- 删六类重复劳动：图片只读/解码一次、内存直传不过盘、媒体 STORED 不二次压缩、
  采样预览不超采样、产物字节只证明一次、不再先写假失败再覆盖。
- 判定不放宽可验证：六类废图两档结论一致。`--deadline` 预算纪律，可选证据超预算
  留痕跳过，release 缺证据如实不可交付。自检 166→186。

## 5.8.0 · Structural Subtraction（规则 43→33）

- 四处同义判断并一处：asset-qc 并入 check（两步必漂移）、Smart Fit 阶梯整套删除
  （字号是设计判断，验证不代修复）、编译器不再复算 guard 已判容量、网格偏差检查
  删除（归一化才是真源）。
- 规则名 43→33（-23%、新增 0）：focus_scale 等 10 条删（判据=能否明显改善结果）。
- 旁路删除：--advisory、--polish、vao doctor。命令 7→6，guard.py −13%，
  自检 166/166。

## 5.7.0 · Asset Role Separation（背景图 vs 插图）

- 征兆：asset_type 从未出现在 brief 契约 → 每张资产静默按 background 处理
  （写了≠生效）。唯一新概念 `asset_role`（background/illustration/hybrid）×
  asset_function 两轴模型，拒绝组合枚举（防摊平成组件表）；
  解析唯一出口 resolve_asset_role，未知值 fail-closed，不接受 function 推导。
- 生成纪律按角色分化（空间连续场 vs 独立对象与文字关系），插图遇介质声明时
  类型后缀让位；融合按角色不按用途；无安全区时过滤整节空指令。
- QC 按承诺走：background 不判主体裁切、illustration 纹理密度降 advisory；
  阈值一律未动。自检 155→165。

## 5.6.0 · 第五轮审计：规则层减法 + 留白「打出来」

- 删 9 条品味规则（只 warn/hint 从不构成门槛）、4 组×7 方向预设审美数字
  （作者声明才执法）。guard.py −164 行。
- 新增 `hard_seam`（阻断）：留白被画成硬边平板的物理判据（阶跃+整带方差）；
  `negative_space_ratio` 降 advisory（指标被假面板抬高）；提示词不写坐标
  （实测坐标文字被模型画成平色面板）。安全区 `none` 语义 + 空指令过滤。
- 词汇统一三态 BLOCK/PASS/TRACE；补 5 条否定边界钉。自检 155/155。

## 5.5.0 · 第四轮审计：spec 级二审层切除（三域证据驱动）

- 删除 pre_critic（414 行）+ risk_strategy（140 行）+ 全部仅服务二审的 helper/常量
  （净 −1049 行）：五轮生产中二审层零消费，`--advisory` 默认关从未开启——
  设计判断发生在起草时。保留 forecast_risk（plan 期、真实消费）与 guard 硬门。
- 合并：json_write 单源、highlight 两函数归一。克隆扫描（191 函数）仅 4 对，2 对
  合法兄弟。selftest 151→148（卡片墙测同步删）· 三域 bench release round 1/6 PASS。

## 5.4.9 · 第三轮审计：plan 输出字段零消费者清理

- 删 plan bundle 镜像键（density_curve/ratio_targets/forbidden/derivation/
  motion_keys/texture_keys 等——「镜像的镜像」四重核对零消费）；随之死常量归零。
- AST 14 脚本 292 函数克隆检测：零克隆对；防假装饰条不预填 DNA（写坏的记忆更贵）。
- plan 更瘦、生产行为零变化（资产指纹在版前后不变）。自检 152/152。

## 5.4.8 · 第二轮审计：AST 可达性清零

- 全库 15 脚本模块级调用图：297 定义 → 删 5 个真不可达（compiler highlight 死链、
  guard 旧拷贝、route 兜底 helper）。复核保留：focus 三族不重复（绑定/存在/尺度）、
  22 条 forecast 全可达、颜色解析三向不合并（口径分离收益<回归风险）。
- 删除后 292/292 可达；累计 −98 行；自检 152/152。

## 5.4.7 · 全包首轮审计：死代码清理 + 摘要三合一

- primitives 死常量 ×11（AXIS_LINES 等轴线幽灵源头）；全文件 sha256 三份同构 →
  primitives.file_digest 单源；短/全指纹同源。
- 结论（不动）：规则三层各司其职（10 阻断码 / advisory / forecast 预见）；触发条件
  逐一存在；Context 已 JIT；调用链无中间层。−29 行；自检 152/152。

## 5.4.6 · 契约减法：审美代理指标退出硬门（纯文档）

- 代码分层本是对的，文档把三层混写 → Contract Map 拆硬门表（10 行）+ advisory 等级表
  （9 项全部标注等级）；删除文档幽灵指标「焦点落轴线」（代码零消费者的 AXIS_*
  系列）；「密度节奏」明记输入语义。
- 固定轮次契约删除（轮次由资产数/QC/根因决定）；清单字段两层化（作业上下文九字段 /
  凭证内部保存）；retry 根因驱动；Asset Integrity ≠ Design Quality 成文（QC 永不评美）。
- 字节账净增是分层结构换来的（边界写明），规则口径硬门收敛 10 码。自检 152/152。

## 5.4.5 · design-system.md 三层切分（纯文档）

- Canvas 叙事规则退出（System 不要求相邻页必变，变化由 Intelligence 决策）；
  方向节瘦身（注册表保留）；分组成本排序替代优先级（防"反卡片规则"复活）；
  图表「类型路由归判断层，System 保证被选中类型正确执行」锚定。
- 新增边界：constraints 四分工 / Theme 永不加知识键 / Anchor=连续性基础设施 /
  DNA 记判断不记结果。回归 152/152。

## 5.4.4 · design-intelligence.md 减法收敛

- 反模板原则卷首置顶；十步判断链 + 七模块职责表成文；「相邻必换算子」删除改为
  「变化需由内容/叙事给理由」；九阶段降为 Narrative Reference；母题可选；留白数字删除；
  字号阶梯迁往 design-system 唯一真源；Page Intent 升级为闭环。
- 硬规则与无条件义务清零，加的全是判断脚手架。回归 152/152。

## 5.4.3 · design-craft.md 减法重构（Craft 不记数字）

- Director Kernel 置顶；减法链升格核心操作系统（§一）；九维审查 → 五个导演级判断
  （Focus/Composition/Reading/Expression/Continuity）；参考刻度数字全部退出到权威
  住所，只留「代码测什么信号」；案例库一字未动。回归 152/152。

## 5.4.2 · 契约语义收紧：声明与预算的权力边界

- 真缺陷：预算 cap 曾截断作者显式 asset: required → declare 项全保留、cap 只管
  判断项（generate = declared ⊕ judged[:cap]）。
- brief 契约收敛：asset 三值语义成文、asset_subject 非空≡声明出图、删 quality_level
  「上限 N」数字（advanced 是预算不是审美等级）。声明优先级写入 SKILL §01：
  决定权威不决定创造。自检 151→152。

## 5.4.1 · SKILL.md 重构为决策系统（纯文档）

- 19 节决策系统（WHY→THINK→EXECUTE→STOP）；数字出主 Skill（阈值移送权威住所，
  只留工程事实）；三产物职责表堵死反复读 plan/manifest 的轮次浪费；
  5.4 契约资产合并归入。18.1KB→12.1KB。

## 5.4.0 · 需求契约：声明优先级、unresolved 与 advanced 语义

- 声明优先级阶梯成文（用户 deck 显式 > 品牌 > 方向默认 > Skill 判断 > 保守兜底，
  永不倒置）。
- 两处真缺陷：逐页 asset: required 无人读取；证据型页缺 content 无留痕（会被
  标题脑补数字）→ 两者强生效 + plan.warnings/骨架 ⚠ 暴露。
- advanced ≠ 更多图片：optional 家族不再升格必出（fast 预算 vs 审美等级解耦）。
- brief.yml 收敛分节契约（01–07）。自检 148→151。

## 5.3.0 · 轮次与提示词质量（不增命令/模块/规则）

- 提示词去矛盾：光照单一来源、静物 motion 静态化、语法键翻译、hex→色名（chroma
  判中性）、负向分层。run 一次完成 plan+skeleton+assets；骨架自足化（头注释带
  方向族事实/统一契约/容量公式/DNA，正常流程零读 plan.json）；plan 再瘦身。
- SKILL −28%；不在文本里栈 entry 的命令保持 4 轮有图流程。自检 139→148。

## 5.2.0 · 用实战返工换速度（判断层一字未改）

- 11 页宋氏美学实案暴露 15 问题（4 静默失效），最贵：介质判定不走资产级声明 +
  方向族名送不到 → ink 全 deck 摄影页判水墨。修法：判据只认 medium/资产级材质；
  13 族名作 design_direction 直达；world 段解耦、QC 按 asset_function 分级、
  ghost 支持多序列、brief 补齐旋钮+删 6 零消费字段、报错可执行、通用反向补边框。
- 无需迁移；自检 139/139。

## 5.1.2 · 设计判断层补位（Anti-Design / 减法链 / 审美标尺）

- 判断层：Anti-Design 反模式清单成文（"所有东西都设计得很明显"最该避免）；
  减法链 `删除>重组>排版>强化>装饰` 全库统一；审美标尺=校准判断的参照系不是版式库；
  最高原则块（Content→form / Context→color …）。
- 修复：selftest Windows 编码崩溃（编码两端固定 UTF-8 + 进程环境补齐）；
  M-09 symlink 静默降级边界钉。SKILL 净 −16B。回归 139/139。

## 5.1.1 · 修复深度审计发现（P1×3 / P2×11）

- H-01/02/03：删共享图片适配磁盘缓存；QC 不隐式执行 brief；核验读图片为不可变
  bytes。M-01..M-11：预览 SHA-256 校验、页 ID/序核对（无图也查）、来源口径非空、
  对比度恒真条件、QC 尺寸+比例+落位、容量覆盖形状内文字、auto_fit spec 共同输入、
  run_id 失效前置、生成资产路径禁锢、透明图按背景合成 QC。+29 回归检查。
- QC v3 升级不冒充旧检查；本地哈希链非数字签名。

## 5.1.0 · Asset-first workflow（本地修改版）

- 先图后规划流程缺口收口：标准顺序 brief→plan→assets→出图→asset-qc→编排→release；
  `assets --plan` 必需；清单/QC 通过内容 SHA-256 绑定；src 未绑定清单不许直接进编译；
  修复 QC 重试仍报成功、BLOCKED 与 release_eligible=true 并存、复用标记覆盖主资产
  记录等问题。新增 asset_workflow.py（内层唯一）；QC 缓存指纹含比例/明暗/风格。
- 兼容注意：有图旧稿须建立计划+清单+有效 QC（已有图登记 reuse）；旧清单/QC 不自动
  升级；本地哈希链非外部服务证明。
