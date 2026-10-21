# MAINTENANCE · 判断层 / 执行层维护手册（规则台账）

这份文件回答三类问题，别的地方都不回答：

1. **这条规则住哪儿**（唯一 owner），谁在读，哪个测试在守；
2. **哪些数值是可调策略**（改 `policy.py` / `--policy` 就够），哪些是判断协议（改 `SKILL.md` 才算改）；
3. **哪些是已知缺口**（不得当成已验证能力）。

判断协议本身只在 [SKILL.md](SKILL.md)；执行契约只在 [references/contract.md](references/contract.md)；
资产链只在 [references/assets.md](references/assets.md)。本文件不写第二套判断，只写**归属与证据**。

## 1 · 分层边界

```
判断协议（散文）        SKILL.md §2–3                     为什么这样判断 / 反例 / 回退
可调策略（结构化数据）   scripts/policy.py + --policy json  多少算多 / 阈值 / 枚举 / 同分顺序
数据契约·输入           schemas/brief.schema.json           作者手写输入的字段、类型、枚举
数据契约·输出           schemas/plan.schema.json            plan 投影的形状、类型、必需、枚举
语义契约（代码）        intelligence.validate_brief/plan()  跨字段一致性 + 拼写分流（schema 表达不了的部分）
确定性推导（代码）      intelligence.py                     内容解析 → 评分 → 排序 → 决胜 → 理由
执行与硬门（代码）      verify.py / compiler.py / ghost.py / assets.py
回归与证据（测试）      selftest.py / bench.py / unseen_bench.py / tools/
```

一句话记住边界：**散文管「为什么」，策略管「多少」，schema 管「形状」，Python 管「算」，测试管「证据」。**

任何数值出现在 `intelligence.py` 的字面量里、又会被作者改写，就是放错了层——
`selftest` 的 `policy: 没有死键` 与 `policy: 覆盖真的改变判断` 两条反向验证它。

## 2 · 调用链（生产路径）

```
vao.py plan ├─ policy.load(--policy)          策略覆盖：校验后就地合并，失败退出 2
            ├─ intelligence.load_brief        唯一加载器（yml/json/py，同一份字节算摘要）
            ├─ intelligence.think             逐页判断（understand → claim → weight → role
            │                                  → focus → composition → spatial → typography
            │                                  → media → production → coherence → provenance）
            ├─ assets.build_manifest          同次判定出图 → 清单（无图不写空清单）
            ├─ compact_plan / 完整投影        瘦身默认；--full 保留完整推演
            └─ schema.validate_file           结构契约（读回磁盘上的那份字节）
               intelligence.validate_plan     语义契约（页数对齐 / chart_kind / 理由未丢）
vao.py check ├─ verify (normalize → guard)    硬错误拦截
             ├─ compiler (原生 PPTX + 缓存)   安全发布（同目录临时文件 + 原子替换）
             ├─ ghost (结构预览/取证)         方向证据，不冒充真实渲染
             └─ assets (QC + 链核验)         像素事实 + 来源/摘要
```

`check` 链路本轮**未改动**（P0 的保护要求）：硬门、资产链、编译缓存与发布机制原样保留，
只是多了 `plan` 侧的契约闸门。

## 3 · 规则台账（规则 → owner → 守它的测试）

| 规则 | 唯一 owner | 守在哪个测试 |
|---|---|---|
| 结论三态（作者主张／证据陈述／未决） | `intelligence.extract_claim` | `bench.py` 57 例 + `unseen_bench` r1–r5 |
| 证据形态判定与同分顺序 | `intelligence.understand` + `policy.enums.evidence` | 同上 |
| 分解（构成）的成立条件 | `intelligence._sums_to_total` + `understand` | `unseen_bench` U01–U03 |
| 焦点：图像 > 数字 > 句子 > 标题 | `intelligence.focus_of` | `selftest.test_design_judgment` |
| 数字归属（最近指标 + 续句继承） | `intelligence._numeral_metrics` | `unseen_bench` U01/U04/U05 |
| 对比谓语的宾语侧（含「不是」） | `intelligence._CLAIM_END_VERB` / `_CONTRAST_NEGATION` | `unseen_bench` U04 |
| 构图算子评分与平局 | `intelligence._composition_scores` + `policy.composition` | `selftest.test_policy_contract`（平局可调） |
| 排版可读域（行长上下限与主张行上限） | `policy.measure` | `selftest.test_boundary_typography` |
| 中文断行禁则 / 数字与单位 | `primitives.NO_LINE_*` / `UNIT_WORDS` / `wrap_lines` | `selftest.test_unit_lexicon` / `test_cjk_rhythm_regression` |
| 视觉世界推导（纸/墨/强调/字体） | `intelligence.derive_world` + `policy.enums.composition_grammar_preference` | `selftest.test_art_direction_linkage` |
| 媒体必要性（只由作者声明出图） | `intelligence.media_necessity` | `selftest.test_material_direction` |
| 跨页节奏与视觉分量 | `intelligence._coherence_pass` | `selftest.test_case004_regressions` |
| 判断来源三态（作者/推导/提示） | `intelligence.provenance_of` | `selftest.test_provenance` |
| 份额陈述（占+分母标签） | `intelligence._SHARE_LABEL` + `understand` | `selftest.test_share_and_total` |
| 分解的整体值（谁是整体） | `intelligence._decomp_total` | `selftest.test_share_and_total` |
| 多量并置（认不出形状） | `intelligence.understand` 的 `mixed_metrics` + `focus_of` | `selftest.test_mixed_metrics` |
| 括号内单位继承 | `intelligence._inherit_parenthetical_units` | `selftest.test_share_and_total`（numerals 段） |
| plan 结构契约 | `schemas/plan.schema.json` + `schema.py` | `selftest.test_plan_contract` + CI 契约步骤 |
| **brief 输入契约** | `schemas/brief.schema.json` + `intelligence.validate_brief` | `selftest.test_brief_contract` + CI 契约步骤 |
| **契约漂移（产出物 → 契约）** | `schema.contract_gaps` | `selftest.test_contract_drift` |
| **文档不许替策略发言** | `selftest.test_docs_policy_drift` | 本文件 + `SKILL.md` + `references/` 的数值扫描 |
| plan 语义契约 | `intelligence.validate_plan` | 同上 |
| 硬错误（溢出/越界/重叠/来源/单位） | `verify.py` | `selftest.test_verify`（未改动） |
| 原生编译与缓存复用 | `compiler.py` + `primitives.compile_reuse` | `selftest.test_production`（未改动） |
| 资产像素 QC / 链核验 / 来源 | `assets.py` | `selftest.test_deep_release` / `test_asset_*`（未改动） |

## 4 · 本轮清理的重复与死规则

| 问题 | 处理 | 证据 |
|---|---|---|
| `intelligence` 与 `primitives` 各维护一份量词表，判断认「27 处 / 12 项 / 3 条」而断行不认（可能断成「27｜处」） | 量词表以 `primitives.UNIT_WORDS` 为唯一来源并补齐 21 个词；`_NUM` 的 `万户/万单` 同步 | `selftest: units:*` 双向锁定；G22 的 token 从「18.6 万」变成「18.6 万单」 |
| `_sums_to_total` 只按单位分组：跨指标的算术巧合被读成构成 | 加「同指标的另一个**时间点**不能是该指标的组成部分」语义约束 | 新冻结集 U01（旧代码 7 条断言失败） |
| 指标归属有两套：逐数字最近归属 vs 从句继承，续句取值没有指标名 | 合并为 `_numeral_metrics`（唯一来源，两处共用） | U01：主语从序列开头 21% 变为终值 44% |
| 对比谓语只认「而不是/而非」，「靠的是履约不是补贴」的否定侧仍能当主语 | 加 `_CONTRAST_NEGATION`（`而是` 出现时不切分） | U04 护栏 + U01 修复 |
| `policy.enums.composition_grammar_preference` 里 4 个键永不出现（世界只产出 3 种纪律），其中 `grid` 与 `strict_grid` 还对不上 | 收敛为 3 个键并对不可偏袒者显式写 `null` | `selftest: policy: 世界纪律都有构图倾向` |
| `chart_kind` 理由写「n 个时间点」，实际是 n 个取值（多指标页会误导） | 改为「n 个取值」 | 快照对比：10 处文案同步更新 |
| 证据形态的分数（0.55/0.92/0.65…）与分解的算术参数写死在 `understand`/`_decomp_total` 里 | 搬进 `policy.evidence_shapes` / `policy.decomposition`；**行为等价** | 126 条快照逐字段对比：仅 `deck.policy` 指纹变化（sha256/version/分组数），判断 0 差异 |
| `policy.enums.provenance` 少 `frame`/`absent` 两个代码实际会产出的值，与契约 `enumProvenance` 分叉 | 补回并写清「这两个不是判断者，是如实记录」 | `selftest: policy: 枚举与契约 $defs 同源`（先红后绿） |
| brief 的未知键无人管：`audiance` 写错 → 受众静默为 None，整稿判断跟着失准 | 新增输入契约 + 编辑距离分流（疑似写错 → 拦；注解 → 告警） | `selftest.test_brief_contract`（14 条）+ CI 步骤 |
| 单句份额陈述（「占+分母标签」）被判 `structure`，焦点落到 `structure_map` | 识别分母标签 → `part_whole`/`ratio_main`；「占比」不算分母名 | `selftest: share:*`；bench T02 反向护栏 |
| `_sums_to_total` 只给布尔，下游猜「谁是整体」，理由把整体写成子集 | 抽出 `_decomp_total`（返回整体值），布尔版只做投影 | `selftest: total:*`；G20/R01 理由文案 |
| 页上有多个量却判 `evidence=none`：角色退 `persuade`、数字变氛围 | 记 `mixed_metrics` 事实 + 未决「补一句关系」；无人/无场所的证据页焦点并置 | `selftest: mixed:*`；bench J13 守住角色不被越权改 |
| 括号内紧贴右括号的量被当枚举前缀吞掉；括号内裸数不继承总量单位 | 序号只认 1–99 两位整数；括号内裸数继承紧邻带单位量的单位 | `selftest: numerals:*`；`total: 括号内裸数继承…` |

**保留的近似重复（不是重复，是两层含义）**：`_SCENE_WORDS`（场所词）⊃ `_WITNESS_WORDS`
（现场记录动作）。场所出现只说明「在哪里」，记录动作才构成「有人去看、去记」的证词线索；
两者的差集正是这条判断的依据，合并会丢失语义。

## 5 · 已知缺口与残余风险（不得当成已验证能力）

| 缺口 | 现象 | 为什么本轮不改 | 下一步 |
|---|---|---|---|
| 同单位双指标的**主语**对齐 | 「毛利率三个季度连续走高」＋「同期补贴率 8%→3%」：证据形态已判对（series），但主语仍落在补贴率的 3%（正文没有写出「毛利率」这个词，无法用词面归属） | 需要「主张指标 ↔ 无标签序列」的对齐策略，属于判断协议级改动，必须先在 `SKILL.md` 写清回退口径 | 提议：正文序列全部带时间坐标、且主张只点名一个指标时，整列归属该指标；先在下一份冻结集（r7）上验证 |
| **峰值/低谷两端**：「等待时长在 18 至 112 分钟之间摆动；午后峰值 112，早间低谷 18」 | 判不出两端对照（`_TWO_ENDS_JOINED` 不认「峰值/低谷」这种写法），落到 `mixed_metrics` 并置 | 加词表容易顺手把「区间摆动」读成两端比较；且同一页的区间（18 至 112）本身该先被解析成一个量 | 下一步：先让区间成为一个量（`18–112 分钟` 是一个取值），再判峰值/低谷两端；在下一份冻结集（r7）上验证 |
| 量纲归一（`2.4 亿元` vs `3,100 万元`） | `same_unit` 按**字面单位**比，同量纲不同写法判成不同单位 | 归一需要一张换算表 + 精度策略，属于新能力，不是修 bug；且「同量纲不同量级」是否可比仍要作者判 | 下一步：单位族表（currency/percent/weight…），只用于同一量纲判定，不改换算后的数值 |
| 目标 PowerPoint 实测 | 字体回落、中文断行、投影可读性 | 仓库不调用 PowerPoint（README 已声明） | 需要人工在目标 PowerPoint 打开/编辑/另存/重开，本文件不替代那份记录 |
| 独立盲评 | 视觉质量 | 无外部评审者 | `bench.py blind` 通道在，需真实评分者 |
| 渲染对拍 | `render-smoke.yml` 未在本轮运行（无 LibreOffice 环境） | 本地无渲染器 | 数字沿用基线：ghost 126/128、guard 122/128（不留低估） |

## 6 · 怎么改一条规则（操作顺序）

0. 先问「这个数是什么」：**可调的量**（多少算多）→ `policy.py`；**判据/语义**→ 代码；
   写在文档里的数值一律不允许（`test_docs_policy_drift`，加白名单要写理由）。
1. 先判断它属于哪一层：协议（SKILL）/ 阈值（policy）/ 结构（schema）/ 算法（intelligence）。
2. 协议级：改 `SKILL.md`，在 `bench.py` 或 `unseen_bench` 里先加失败案例，再改代码。
3. 阈值级：只改 `policy.py` 的默认值，或写一份 `--policy` 覆盖；不要改算法，也不要在 Markdown 里写数值。
4. 结构级：改 `schemas/plan.schema.json`（输出）或 `schemas/brief.schema.json`（输入），
   跑 `selftest.test_plan_contract` / `test_brief_contract` / `test_contract_drift`。
   **新增产出字段的顺序**：先写契约声明 → 再写代码 → 最后跑漂移测试（本轮之前是反的）。
5. 算法级：改完必须给出**快照对比**（`snapshot` 脚本逐字段对比 before/after），并把新行为冻结进
   `scripts/json/generalization_cases_rN.json`（哈希先冻结，再跑）。
6. 任何「只是让测试变绿」的改动都退回：`selftest` 通过不是质量证据，只是回归证据。

## 7 · 内容存废判据（什么能删、什么不能删）

删除是**举证责任**：先跑取证工具、把数字抄进变更说明，再动手。判据 D1–D7 各有一条
可复跑的命令；任何一条为真也**只**解禁它对应的那个动作。

| 判据 | 问题 | 取证命令 | 解禁的动作 | 不解禁什么 |
|---|---|---|---|---|
| D1 死符号 | 模块级符号（或导入）在定义之外零引用，且不是测试注入缝 | `python tools/dead_code_audit.py`（D1/D3） | 删除该符号/导入 | 别名被 selftest 用 `patch.dict` 注入（如 `ghost._FONT_*_CANDIDATES`）时不算死代码，删了会让字体回退检查静默失效 |
| D2 重复实现 | 两个函数体逐字相同，或两条判据在语义上一模一样 | `python tools/dead_code_audit.py`（D2） | 合并为一份，保留调用点兼容 | 「写法不同、语义重复的近似对」要单独判断：`_SCENE_WORDS ⊃ _WITNESS_WORDS` 这种差集本身就是判据，不算重复 |
| D3 空操作代码 | 分支体只有 `pass`、条件恒不可达 | 把分支体换成**有副作用**的语句跑 `selftest` + 全部案例集，看它是否被命中 | 只有命中数为 0 才可删 | 命中数为 0 也未必是死代码：可能只是没有案例覆盖。要用「改成 `continue` 会不会改变基线快照」来判它的真实用途 |
| D4 重复案例输入 | 两份案例的标题+正文逐字相同 | `python tools/dead_code_audit.py`（D4） | 删掉重复的一份 | **期望相同不等于案例重复**：「设备手册的规格行」和「包装规范的规格行」判据相同、输入不同，删任何一个都在减少抽样面 |
| D5 孤儿文件 | 任何文件里都没提到它 | `python tools/dead_code_audit.py`（D5） | 删除或并入引用它的文档 | `tools/` 下的取证仪器**不以被引用为标准**：它们的价值是能重新产出证据（`dead_code_audit`、`case_coverage`、`chart_kind_survey`）。删仪器的唯一条件是「有更新的仪器替代同一份证据」 |
| D6 边际覆盖 | 某案例/套件不再独家覆盖任何代码行 | `python tools/case_coverage.py` | 只解禁「合并到同一份文件」这类整理 | **不解禁删除案例**。案例是测量样本，行覆盖衡量代码路径，两者不同轴：零独有行的案例照样可能是唯一守住某条判据的那一个 |
| D7 判据失守 | 把 policy 里的一条判据故意调坏，案例集里没有任何案例变红 | `python scripts/bench.py --guard-audit --cases scripts/json/generalization_cases_r6.json` | 反过来——这是**加**案例的理由 | 不能据此删任何东西；也不能把「零报警」读成「判据没问题」 |

三条硬门槛（任何删除动作都不得越过）：

1. `selftest.py` 必须保持全绿，且**检查条数不减**（减条数等于删掉回归证据）。
2. 差分快照（`snapshot` 逐字段对比）必须显示零差异——除非本次变更本就声明为行为变更，
   并在案例集里先冻结新旧两个结果。
3. 删掉的东西如果承载着历史决策，先把决策写进 `CHANGELOG.md`，再删实现；证据不进回收站。

**本轮判决（可复核）**

| 对象 | 证据 | 判决 |
|---|---|---|
| `ghost.py:_NO_LINE_END`、`primitives.py:PREVIEW_ABSTRACT_KINDS`、`vao.py: import os` | D1/D3：定义之外零引用；删后快照零差异、`selftest` 全绿 | 已删 |
| `intelligence.py` 的 `pass` 分支 | D3 正控：把分支体换成写文件后跑全量，命中 37 次；改成 `continue` 会让「由7增至12」这类正常量被拒 | 删掉空分支，保留它想说明的判据（写在注释里） |
| `ghost.py` 的 `_FONT_*_CANDIDATES` 别名 | 被 `selftest` 的 `patch.dict` 使用（同一份字典对象，改它真的会改变预览） | 保留，并加注释说明是注入缝 |
| 116 个既有判断案例 | D6：102 个零独有行；D7：0/6 条判据有人守 | **保留**，同时补 6 个守门案例（r6）。广度不足不能靠删广度过关 |
| `tools/` 三个一次性仪器 | D5 会被判成孤儿 | 保留（复验路径），并要求它们可跨平台运行 |

> 一句话：**能删的是「没人再需要它的证据」；不能删的是「还有人靠它作证」。**
> 「行数变少」不是成就，「同样的证据用更少的重复产出」才是。

## 8 · 技能包作为交付物的三条边界（2026-10-21 补）

| 层 | 唯一来源 | 谁在读 | 谁在守 | 已知边界 |
|---|---|---|---|---|
| **触发** | `SKILL.md` frontmatter 的 `description`（702 字，含 when-to-use 与不做边界） | 装载技能的运行时；它决定「会不会被调起」 | `quick_validate`（长度/字符/键白名单）+ `test_docs`（版本一致） | **触发率未测量**：本环境无 `claude` CLI，`run_loop` 跑不了。只声明「描述里有 when」，不声明「更容易被调起」 |
| **任务级评测** | `evals/evals.json`（7 条 prompt + 机器断言） | `evals/run_eval.py` → `evals/grade.py`；统计交给 skill-creator 的 `aggregate_benchmark` | `test_evals`（形状/词汇/断言会红）+ CI 步骤（with_skill 必须全绿，naive 必须更低） | 对照是 **engine-baseline**（无判断直排），**不是 model-baseline**；无模型就没有 token 结论 |
| **分发** | `tools/package_skill_staging.py` 的白名单 | 收件人的 `quick_validate` / 解压 | 脚本自带 `.git` 混入检查 + 体积/条目数对比 | 包里没有 `evals/`、`tools/`、`scripts/json/`：它们是仓库资产，不是运行资产 |

**断言的自我要求**（来自 `skill-creator/agents/grader.md`）：一条永远为真的断言比没有断言更糟，
因为它制造假信心。因此 `test_evals` 里有一条反向检查——把同一批断言喂给**伪造的坏产物**，
必须变红；`evals/run_eval.py` 的两种配置也必须拉开分差，否则 CI 失败。
