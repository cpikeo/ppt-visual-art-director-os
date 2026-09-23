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
