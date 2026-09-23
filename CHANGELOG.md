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

