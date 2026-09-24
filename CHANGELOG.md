## 9.6.2 · DNA Store Compaction（2026-09-24）

将 `feathered_safe_area_calm` 的可迁移做法并入 `image_must_inform`：保留安全区纹理处理的触发条件、羽化方案、边界、检索词与 PPT_CASE_004 实测证据，消除重复独立条目；DNA 总条目由 11 收敛到 10，不放宽数量上限。
修正 selftest 文案，使其准确表达「条目数（含经验例外）」；新增安全区经验召回回归。DNA store --check 为 10 条 / 0 error / 0 warning；selftest 122/122。

## 9.6.1 · Axis-Preserving Normalization（2026-09-24）

修复网格归一化把零宽竖线扩成网格宽度、在 PPTX 中变为轻微斜线的问题。
横线与竖线对称处理：合法零厚度轴保留为 0，只吸附轴位置；线长按中心归一。
真正的零长度线和其他退化尺寸继续交由 guard 拦截，不静默修成可见对象。
新增横 / 竖线零厚度边界、圆点同心、归一化幂等、零长线与退化矩形拦截，以及 PPTX connector 编译级回归测试。

## 9.6.0 · Concentric Normalization（2026-09-23）

修正归一化层越权改排版的一处根因：亚网格厚度被抬高、同心关系被吸附拆散。
**零新增模块 / 零新增 Warning / 零新增 QA 阶段**；判定口径与执行链不变。
selftest 110/110（+3 条归一化回归）。

- **发丝线不再被加粗**：`_snap_size` 对「小于一个网格的尺寸」原样透传。
  此前 `height:1` 的线被 `max(grid, …)` 抬成 4px——4× 的视觉重量改变，
  且无任何提示。线的厚度是作者的设计决定，不是需要被对齐的节奏。
- **同心关系不再漂移**：吸附由「逐字段独立」改为 `(x,width)` / `(y,height)`
  **成对**处理（`_snap_span`）。厚度 < 网格时吸附**中心**而非上边缘，
  因此「1px 轴线」与「骑在其上的对象」在吸附后必然仍共中线。
  此前两者各挪各的，中心最多漂 grid/2，产物里对象永远悬在线的一侧，
  而硬门全绿（几何合法、不重叠、不溢出、不越界）——错位一路走到交付。
- **尺寸被圆整时保住中心**：非网格厚度（6px 条、9px 点）被圆整到 8px 时，
  按中心重新定位而不是钉住上边缘——「改厚度」不该顺带把对象挪走。
- **逃生口**：元素写 `snap: false` 完全绕开吸附（作者声明永远压过机械变换）。
- 契约文档补一条作者须知：成对吸附 + 亚网格厚度保留 + `snap:false`。

## 9.5.0 · Intelligence Judgment Quality（2026-09-23）

修正理解层的语义识别与结论判断，使 Visual Art Director 在真实内容中产生更诚实的
focus、role、composition 与 media judgment；最短执行链、可编辑性、QA、性能与验证
体系不变。**零新增**（文件/模块/规则/Warning/Reference/Schema/评分/QA 阶段/渲染阶段）。
selftest 107/107；验收 23/23。

- 理解层：比较否定前缀（不超过→number）、材料/器物识别（窑釉陶瓷≠石材）、
  裸趋势词（涨跌掉至→series）、去两处子串误撞（学生、工程）、ask 意图（请批准/请决定）。
- 结论诚实：裸标题不再冒充结论；claim.why 逐页给命中依据（位置＋结论措辞＋数字），
  无结论时写明最接近者差在哪；focus 措辞去套话。
- 预览保真（像素验收前提）：ghost 恢复 CJK 粗体字面与元素字族——此前预览永远细体、
  永远无衬线，字重/世界差异在预览里不可见，与交付链不一致。
- 像素验收：Build/Pixel Evidence Pass（仓外 harness），5 域 × 6 页真实 build +
  可编辑 PPTX 抽查。

## 9.4.0 · 端到端根因收口（2026-09-23）

总纲审查令执行轮：先追踪完整执行图找 Command/AI 交互膨胀的结构性根因，
再按「删除 > 合并 > 简化」收口。**零新增**（文件/模块/规则/Warning/Reference/
Schema 层/评分/缓存/QA 阶段/渲染/新抽象）。selftest 107/107；验收 23/23。

### §01 追踪结论（trace.py，仓外可复跑）
- 一次理解 / 一次判断 / 一次生产 / 一次验证已成立：12 页稿 think×1、
  understand 恰 1 次/页、冷编译×1、热复用 0 编译 0 渲染、BLOCK 在 guard 处
  熔断（0 编译 0 渲染 0 哈希）；修复=同一入口复跑，无 plan→asset→compile
  级联。CLI=plan×1+check×(1+修复轮数)；Agent 交互只剩填几何与按 packet 修。
- 真重复只剩 1 处：产物 PPTX 同轮哈希两次（_compile_step + release_manifest）
  → manifest 加 `output_verified`（同轮信任传入值，直接调用仍现算）。
  冷 release 11 次哈希→10 次，热复用 2 次→1 次。
- 证伪的嫌疑：brief 已一轮一算（v9.3）；ghost.py 跨 scope 各算一次是两个问题；
  预览图哈希是联络表缓存键（命中必需）；引擎指纹进程内缓存有效。

### 删除（全库消费者审计，零读者且零信息）
- 死 schema 戳：plan workflow、repair packet、think SCHEMA（+ 自测 pin →
  107 条）、DNA store schema_note。资产链/QC/缓存 schema 有强制门，保留。
- 死报告键：compile attestation_mode（reused 可推）、packet.facts（恒 {}）、
  缓存 _cache_probe×2（恒等于 output_sha256）、dependency_missing（文案已载明）。
- 死机制：warning_ids 全套（fix_plan 从未接线，id 硬编码 None 处不动）；
  skipped_stages（跳过原因到不了任何输出）；compile reason/slides 明细槽；
  verdict copier 收成 5 个被消费键。
- `warn()` 的 element_id 参数保留（调用点多，零运行时成本；存储已删）。

### 审计确认不动
- 职责硬边界成立：compiler/ghost 零 plan 读取；verify 零 warning；
  SKILL 6KB + 按需 references（JIT 表驱动）；无模板/组件/预设系统
  （CARD_SEGMENTS 是资产提示词结构，非设计模板）。
- performance/timing 遥测块保留：随 packet 给 agent，非 result 内 baggage。
- DNA 九条冻结依旧（转经验库需新匹配语义=新增规则，本轮禁止）。

## 9.3.0 · 结构减法 / 判断合并（2026-09-23）

消费者审计驱动的减法轮：**不新增文件 / 模块 / 规则 / Warning / Reference /
Schema 层 / 评分机制 / 缓存机制 / QA 阶段 / 渲染阶段 / 新抽象**。
selftest 108 条断言全绿；验收 23/23（含 v9.2 十三行为）。

### 唯一竞争证据（rejected 收口：最小改动）
- `focus.rejected` 与 `composition.rejected` 保留为 Intelligence 的唯一竞争判断证据；
  下游不再复制：`production.must_not` 只收 `information_weight.delete`（硬约束），
  skeleton 不再打印否决行；compiler/verify/ghost/assets 从不读 rejected（全库确认）。
- 构图 rejected 只留真实竞争：复用既有「内容成立」语义（score > 0，无竞争即 []），
  不新增阈值。focus.rejected 无分制且被防卡片墙断言消费，原样保留。

### 证据去重
- 删除 dict 级 `brief_sha256`（plan workflow + assets manifest 两处记录，零读取；
  dict 比对在 v9.2 已删，只剩记录）。文件级 `brief_file_sha256` 是 verify_sources
  的篡改口径，保留且仍 BLOCK（验收覆盖）。
- brief 文件哈希同一轮算两次（plan + prepare_manifest）→ 复用 plan 已算值；
  直接调用（bundle 无 workflow）时才现算。

### DNA 冻结
- 职责钉死：经验库不是第二套 judgment；存量九条冻结，只修错不扩写。
  完整转成经验条目留待 v9.4（需要新匹配语义，属新增规则，本轮禁止）。

### 审计确认无需动（不制造 diff）
- Compiler 从不读 plan 判断（只读 spec 几何/类型），已是哑执行器。
- Ghost 从不读 plan，只做结构取证；两处 identity 均为缓存键，有真实消费者。
- Verify 零 warning 输出（只有 error 进 fix_plan）；对话层已是 PASS/BLOCK + 根因组。
- 全库 272 个函数零死函数；release 链路已是一次读取 / 一次身份 / 一次哈希。
- `understanding` 占 plan 约 3%，内部回看 + 骨架标量 + selftest 形状断言消费，保留。

## 9.2.0 · 跨页校准 + 判断再瘦身（2026-09-23）

端到端深度审计后的减法升级：**不新增文件、不新增逐页判断字段、不新增 QA 规则**。
全部改动落在既有 8 个脚本与 3 份参考文献内；selftest 87 → **108** 条断言。

### 跨页智能（intelligence.py：唯一的 deck 级回看）
- **预算执行**：图位落选页的判断卡当场改写为不要图（media 回 none + 焦点/构图/
  空间/生产重算 + 未决事项去掉图像追问），不再「判断说要图、清单说没图位」。
- **节奏回拨**：连续 ≥3 页同构图时回拨中间页——只在内容允许第二选择时换，
  内容强烈要求同一构图就不换（内容契合压过节奏）；作者声明的构图不动；
  图像叙事不动（数量由预算管，不由节奏管）。
- **连落提醒**：焦点连续 ≥4 页同一落点时给作者一句提醒，不硬改焦点。
- 新增 `deck.coherence`（构图/密度/角色/媒体四条节奏序列 + adjustments + notes）：
  这是本轮唯一的 deck 级新增能力，无逐页新字段；骨架注释携带节奏与回拨。
- QA 零新增（刻意）：重复/断裂/失衡不是可交付性硬错误，做成 BLOCK 是错杀、
  做成 warn 是噪音——跨页事实归设计层（plan + 骨架），QA 边界不变。

### 判断校准（intelligence.py）
- **Claim**：超长句子减分（>64 字 −1.0，可复述才算记住）；absent 纪律不变。
- **数字**：字母紧贴的数字是编号不是证据（Q1/V2 不计数）；「2026 年」是时间
  坐标不是证据量（4 位年份 + 年 = year，与「3 年」时长区分）。
- **焦点**：承载结论的只取证据量（年份/编号不当第一落点）。
- **证据形态**：箭头链是顺序的形状（0.75，盖过孤立数字 0.7）。
- **构图**：体量取整页内容长度（空间需求，不是结论句长度）；无结论 + 弱证据页
  默认最少结构（big_whitespace +1.0）；作者未知构图不断规划（密度取中性）。
- **权重真正抵达生产**：删除清单进 `production.must_not`（「删：…」可执行禁令）。
- **世界**：整套证据性格取最常见的非空证据（「无证据」不再盖过真证据）；
  主题实体需要 deck 级证据（命中 ≥2 页，单页 deck 除外）——一页提「发布」，
  整套就变舞台，是误判。
- **声明即权威**：`asset_subject` 等价 required（注入判断输入，不只留在回显里）。

### 删除（审计确认零消费者 / 死分支 / 重复劳动）
- 判断卡：`media.why`（与 necessity 重复）、`media.confidence`、`claim.verify`、
  `spatial.layers`（每页相同的常量）、`spatial.layer_weight`（两值常量）、
  `production.thresholds`（每页相同的常量；指导值并入 contract.md 一行）、
  `composition.energy`（与 declarations.energy 重复）。
- 死分支：构图打分里的 `data/prose/mixed` 标签（证据形态永不取值）、
  `u.temporal`（永不设置）、骨架里的 `unity` 回显（think 永不产出）、
  `prepare_manifest` 的 v1 plan/brief 比对（schema 已是 v3，永不触发）、
  `normalize` 报告的 `idempotent: None` 恒定字段。
- 重复劳动：每页 `understand` 算两次 → think 一次算好传入；DNA 存取自写
  JSON/原子写 → 并入 `primitives.json_read_cached/json_write`；verify 两趟
  页面扫描 → 单趟（碰撞/来源区/背景资格一次遍历）；ghost 关键页与职责标签
  各扫一遍结构 → `key_selection` 一次算完；`primitives`/`assets` 的自我 import；
  vao 失败路径的 `repair_packet` 算两次、`sys.modules["verify"]` 别名。
- 构图否决项 3 → 2 条（最强的两个替代）。
- 收口轮：`composition.label` + `rejected[].label`（chosen 键已唯一确定算子，
  中文释义只住文档，plan 不再输出）与 `COMPOSITIONS` 字典；`must_place[].why`
  （零消费者，且与 focus.why / media.necessity 逐字重复）；`_composition_rejections`
  的 `score <= -50` 死分支（-99 恒为末位，进不了 [:2]）；`BG_MIN_COVERAGE` /
  `BG_MIN_PROTECT_OPACITY`（注释声称的 `_cached_gate` 不存在，零消费）；
  `understand` 内 `numerals` / `evidence_numerals` 同文本扫两遍 → 一次扫描复用。

### 正确性修复（审计发现）
- CLI `plan` 打印 `视觉世界 … (None)`（9.1 删除 `regime` 后的残留引用）。
- 编译解码缓存：同源不同裁切会复用已裁切底图（二次裁切像素错误）——
  只缓存未裁切底图。

### 文档
- judgment.md：判断链补跨页校准一步 + §8 节奏纪律；contract.md：焦点落差/
  结论行数/正文下限指导值（原 runtime 常量的唯一去处）；assets.md：落选页
  改写语义；brief 模板：family 只是人读备注（规划不读）；SKILL/README 同步。

## 9.1.0 · 判断深化 + 重复删除（2026-09-23）

在 9.0.0 上继续深化：**不重设架构、不堆能力、不新增文件、不用质量换速度**。
全部改动落在既有 8 个脚本与 3 份参考文献内；端到端证据 16/16 通过。

### 判断层深化（intelligence.py）
- **Claim 真结算结论**：话题句（「会议纪要…」）不再冒充结论——话题标记 −2.5、
  标题化话题尾巴 −0.8、变化词 +0.8 参与打分；抽不出即 `absent` 并要求作者补写。
- **Information Weight 可删除**：`delete` 档真正可用（重复数字 / 装饰 / 说明性图片 /
  无结论图表 / 纯装饰容器），删除理由逐条落进判断卡。
- **Visual Role 内容先决**：ask→summarize、comparison→compare、series/number→prove、
  structure/sequence→explain、witness(human|scene)→prove；页面索引只做 establish/summarize 兜底。
- **Composition 只留判断**：构图打分表与理由合并为 `_composition_choice`，
  分数用完即弃，只输出 `chosen / why / rejected`（每页记录为什么不采用其它形式）。
- **同一内容 × 不同叙事目标 → 不同世界**（证据：document → stage）。
- 纸色从 3×7 固定色表改为 `blend(纸锚点, 强调, tint)` 推导；`_NEUTRAL_ACCENT` 改中性灰
  `#6E6A63`；`_MATERIAL_LEXICON` 收紧单字词（避免「现场」被「场」误命中）。
- 删：`derive_world` 的 `material/motion/chroma/regime/background/rejected_worlds`、
  页级 `role/evidence/declarations` 副本、`understanding.text/modes`、`unity/slots`、
  6 个未消费形参；`assets_hint` 只留 `{generate, cap, deferred}`。

### 资产智能（assets.py）
- 预算按**视觉价值 × 叙事重要性**排序（witness 3.0 / subject 2.0 + 角色价值），
  超额页进 `deferred[{slide_id, why}]`——不做按页序截断。
- 删 `read_json` 别名（与 `json_read_cached` 同实现）、`resolve_asset_role` 的 legacy 分支
  与 `"legacy"` 权威来源（全库无调用点）、卡片内 `motion`。

### Runtime（primitives / vao / verify / ghost / compiler）
- `_DIGEST_CACHE` + `_READ_CACHE` 合并为一份键空间 `_file_state`（resolve + stat 一次）；
  `file_digest` 与 `json_read_cached` 共用；4096 → 512 条上限。
- 每轮 `spec_fingerprint` 一次，供 `verdict` / `release_manifest` / packet 共用。
- 预览引擎指纹改为完整 `engine_fingerprint("preview")`；预览标记删重复字段 `sampled_ids`。
- 删空转参数：`run_check(asset_qc_report=)`、`normalize_spec(fonts=)`、`verdict(output=)` 位置参、
  4 处 guard 未用形参、`ghost` 的未用 `scale`；删 `verify` 的 `hash_before/after` 死分支。
- `compiler.py` 仅删 `_textbox` 未用 `alpha`（不改渲染行为，PPTX 字节对拍一致）。

### 文档
- SKILL.md：核心次序改为「信息层级 > 空间秩序 > 排版 > 视觉表达 > 装饰」，
  补「高级感不是材料表」；judgment.md 同步；assets.md 收紧 witness/subject 判据与图位分配。
- selftest 80 → **87** 条断言（页级无重复存储 / 世界无可删键 / 话题句与断言句的 claim 判据 /
  纯数据页不出图 vs 现场页 witness / 图像页构图即图像叙事 / 图位按价值排序）。

## 9.0.0 · Design Intelligence 重构（2026-09-23）

一次端到端审核：结构化减法 + 判断层重写。总原则 `删除 > 合并 > 简化 > 复用 > 新增`。

### 判断层（intelligence.py）
- 决策链从「Brief → Question → Layout」升级为「内容理解 → 受众 → 决策 → 结论抽取 →
  信息权重 → 视觉角色 → 焦点判定 → 构图推理 → 空间结构 → 媒体必要性 → 生产规格」。
- 每个判断带 `why`；每个形式选择带 `rejected`（被否掉的替代项与理由）。
- 信息权重成为一等判断：必须最大化 / 必须弱化 / 必须删除，逐条给理由。
- 视觉角色成为一等判断：establish / explain / compare / prove / persuade / summarize。
- **删除隐藏设计系统**：14 条命名风格预设（DIRECTIONS）、方向别名表、家族媒体模型
  （MEDIA_MODEL / TYPE_TO_FAMILY）、通用判断问题模板全部移除。视觉世界由内容推导
  （受众语域 × 内容里的主题实体 × 证据形态），同类内容允许产生不同世界。
- 媒体判断改为必要性测试：答不出「没有它这一页会下降在哪里」即不出图，
  装饰图 / 氛围图 / 无意义背景在结构上无法通过。
- `page_questions` → 判断卡（`pages[].judgment`）；只在无法闭合时留 `open_questions`。
- `design_direction` 退役（写了会被点名），保留作者槽位：`visual_world` / `brand_colors` / 逐页声明。

### QA 层（verify.py 2046 → 936 行）
- 只保留硬错误：schema / 溢出 / 越界 / 退化几何 / 重叠 / 来源区 / 图表类型与载荷 /
  数据完整性 / 跨页口径 / 出处（release）/ 未知色名。PASS / BLOCK 二态不变。
- 删除声明执法层与留痕层（密度镜子、主题约束 10 键、色相族、图表风格漂移、字体提示、
  锚点提示、对比度软信号）——设计判断归设计层，QA 不再产生 warning 噪音。
- 归一化收敛为单趟幂等变换。

### 生产层
- `primitives` 身份/凭证 API 收敛：`stat_witness/byte_witness/witness_matches/engine_witness`
  → `witness/witness_same/engine_fingerprint`；删除未使用导出。
- `ghost` 采样改为**关键页取证**：封面 / 章节 / 画心 / 密数据 / 收尾，证据里标注职责。
- `assets` 去掉「页面家族 → 材质/动势」预设表；材质与光随视觉世界，能量只调强弱。
- 实测：12 页 release 冷启 0.4s、缓存命中 0.03s（2 分钟目标有大量余量）。

### 文档与记忆
- SKILL.md 收敛为六节（身份 / 哲学 / 判断 / Context / 执行 / QA 边界），具体规则外移或删除；
  references 4 → 3 份（precedent.md 删除，可迁移原则并入 judgment.md）。
- Design DNA 16 → 9 条高迁移原则（58KB → 5KB），字段不变、校验不变。
- brief 模板同步新契约（world / necessity / 退役字段说明）。

# Changelog

## 8.1.1 · P1 收尾 + 实战证据基线（2026-09-23）

按第二轮优化建议（audit/SUGGESTIONS_v2.md）落地。代码零结构变化，判断校准与教学面补全。

- brief 模板补 `insight`/`focus` 页级声明教学面（v8.1.0 新契约）。
- `deck_contract` 警告扩为三字段：缺 tension 现在点名（张力注入的输入静默缺失 = 判断静默失效）。
- SKILL.md 补记忆循环入口（`vao.py dna --add / --check`）。
- judgment.md §5 补色觉冗余校准一行（doc-only，验证层不加检查）。
- selftest 57 → **59**：缺 tension 警告断言、14 方向字体种子跨平台安全名锁定。
- git 基线建立（tag v8.1.0）；首轮实战证据入 battles/（三副 deck 全周期 + QC 校准探针 + 新 DNA）。

### 实战驱动的两处修正（battles/REPORT.md §2）
- `repair_packet` 透传 `facts`：密度镜子在 CLI 出口不再断链（stdout 仍精简，镜子住 packet）。
- 留白测量排除 `layer: background`（背景是纸不是墨）：满幅封面 occupancy 1.0→0.12，
  三 deck 读数与方向人格一致；背景层计数保留（层叠预算本职不变）。
- DNA 库 14 → **16**：`full_bleed_paper_not_ink`、`declared_paper_dark_image_contract`
  （均带完整 proven，战役复盘沉淀，`dna --add` 校验入库）。

## 8.1.0 · 三层执法身份 + 密度测量闭环 + 判断校准补全（2026-09-23）

按优化建议书（audit/SUGGESTIONS.md）落地，零新增模块，净变化 ≈ −200 行。
纪律不变：**删除 > 合并 > 简化 > 复用 > 新增**。

### 删除
- `data_claim_unsupported` 咨询项及其静态百分比匹配器 `_data_claim_mismatch`
  （标题-图表数值核对是设计判断，不是工程事实；warn 留痕只会训练「提示可以忽略」）。

### verify.py 第二刀：check_spec 三层执法身份
- `add(..., layer=)` 三级：**hard**（可 error，阻断）/ **declared**（只执法作者在
  `theme.constraints` 写下的数字）/ **trace**（咨询留痕，**结构性禁止 error**——
  误写会被压回 warn，永不进 blocking 与 fix_plan）。升级 trace 检查的唯一合法方式
  是挪出 trace 层并说明理由，防止未来迭代把 warn 悄悄升回门槛。
- 声明执法 + 密度测量抽成 `_declared_layer_checks`；色彩/图表漂移/对比度咨询尾巴
  抽成 `_trace_deck_checks`。检查项自带 `layer` 字段。

### 密度测量闭环（镜子，不是规则）
- 每页占用带（sparse/balanced/dense）+ 整副均值每轮无条件归档进
  `result.facts.density`（只进 JSON trace，不进对话、不设门槛）；
  `verdict` 透传 facts，`performance` 补 `qc_ms` 计量。

### 判断校准补全
- `page_questions(…, tension=)`：tension 参与页级判断——结论/风险页与收尾页的
  claim 问题追加「如何直面观众最大疑虑」；数据页不注入。
- 作者在 brief 页内写的 `insight`/`focus` 声明直通骨架 `page_intent`
  （写了就生效，不再留空 TODO 重问）——补齐「写了的字段原样生效」契约。
- 方向字体种子改跨平台安全名（思源黑体/思源宋体/Arial/Georgia；苹方/Helvetica Neue
  是 macOS 专属）；contract.md 补字体回落说明。
- precedent.md 新增 §2.5 正面走查（KPI/风险/收尾三例：claim→form 否决了什么→space 职责，
  纯判断理由、零坐标）；SKILL.md 新增 15 行「四问已回答」示例页。

### 测试与工程
- selftest 47 → **57**：新增资产链 CLI 回归组（合规图 release 全链 PASS、
  图变后 QC 重测零复用、坏图 draft=retry / release=block 阶段切换语义锁定）
  与三层身份/密度 facts/tension 注入/声明直通断言。
- 迁移 CI workflow（selftest 矩阵 + spec 档零 python-pptx 红线冒烟）。
- design_dna.json 补 `lo_spc_alpha_glyph_drop` 的 proven（dna --check 0 warning）；
  .gitignore 收紧 demo 证据最小集（成品 PPTX + 联络表入库，页级渲染不入库）。

## 8.0.0 · 结构化减法 + Design Intelligence 重构（2026-09-22）

端到端审计后的重构：**删除 > 合并 > 简化 > 复用 > 新增**。
能力不降、模块 13 → 8、references 6 → 4、规划 4 趟 → 1 趟、判定输出 PASS/BLOCK 二态。

### 删除（能力不降）
- `run_evidence.py`（COLD/HOT 证据簿记的簿记）、`intent_compiler.py`（只剩重复加载器）、
  `design_intelligence_rules.py`（表并入 intelligence）、轮次账本（round 1/6 与 revision_log）、
  `make`/`run` 子命令（别名与组合）、骨架 plan_sha256 抄写仪式、
  manifest 多级见证协议（一次哈希比对足够）、plan.json 的 need 镜像与零消费者字段
  （`focus:"statement"`、`asset.why`、`narrative_arc`、`saturation_regime`、`mode/path`）、
  `_DECK_CACHE`、`align_pages`/`alignment_warnings` 对齐机器、
  ROUTES 固定 density/energy 预判与 `_alternate_density` 自动改写（反模板）。

### 合并（职责真正重复才合并）
- `route + design_intelligence + design_intelligence_rules + intent_compiler + pipeline`
  → **`intelligence.py`**：brief 加载 → 单趟决策链 → 单份页事实 → 骨架。
- `asset_prompt + asset_workflow + vao 资产段` → **`assets.py`**：判断/卡/提示词/清单/QC/核验一体。
- `guard + qa` → **`verify.py`**：硬门 → 判定 → 清单；修复组内嵌 error 明细（修复包自足）。
- `compile_cache` → 并入 **`compiler.py`**（轮次账本删，缓存语义保留）。
- references 六份 → 四份：`judgment.md`（判断）/ `contract.md`（字段+硬门+失败码）/
  `assets.md`（资产链）/ `precedent.md`（案例+DNA）。

### Design Intelligence 升级
- 唯一核心决策链 `Audience → Decision → Claim → Tension → Focus → Form → Space →
  Media → Spec`；规划产出逐页**判断问题**而非布局答案。
- 两套方向表（DIRECTION_PRESETS × COLOR_DIRECTIONS）合并为一张 `DIRECTIONS`
  （结构 × 材质 × 种子一条一行）；品牌色单管线（方向种子 → 品牌覆盖 → 可读性兜底）。
- 媒体判断唯一实现 `media_judgment`：作者声明 > 页内事实（已有图表）> 家族模型，
  置信度 + 理由可解释；`density/energy` 不再由标题词预定。
- 13 个内容类型的形态问题逐页校准（骨架注释给出本页的判断问题）。

### 性能
- 规划 4 趟（plan_deck + one_pass_plan + deck_decision + color_plan）→ 1 趟（think，~25ms/12页）。
- 12 页原生稿 release：cold ~0.9s / warm ~0.15s（编译缓存）；快档默认全量预览 ≤24 页。
- plan.json 体积 −~40%（单份页事实 + 死字段清除）。

### 兼容性
- build.py/JSON/YAML 编排稿格式不变；brief 契约不变（`quality_level`、逐页声明、
  `asset_source` 原样生效）；`design_direction` 增加自由文本别名归一。
- DNA 库（memory/design_dna.json）格式不变，14 条既有经验原样可用。
- `run` 由 `plan --assets-out` 覆盖；`make` 删除（`check --mode release` 即原语义）。

## 7.3.2（基线）
- 结构化审计版：243 项自检、compile/asset-QC/预览三层缓存、资产链内容哈希核验、
  spec/draft/release 三档、ghost 方向预览。此版本为本次重构的对照基线。

