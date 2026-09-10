# v3.1 去工程化改造：QA / Critic / 缓存 / 风险预测

> 目标不是「少几行」，而是**一条事实只判一次、一次判断只有一种机制**。
> 本文是三样东西的档案：删了什么（附可核对的计数）、快了多少（附实测计时）、
> 什么必须留下（附保留理由）。改动的唯一动机来自使用侧的观察：验证层比生成层贵，
> 门控比判断多，而 Critic 本身只要 10ms。

## 1. 职责分层（改造前后的同构对照）

| | 改造前 | 改造后 |
|---|---|---|
| QA 的唯一问题 | 20 多个硬门槛 + 状态机 + 门控，回答「什么都判」 | **这份 PPT 能不能正确交付？** → `PASS` / `FAIL` / `WARNING`（`qa.verdict_of`） |
| Critic 的判据 | 设计价值 + 工程事实混判（`READABILITY_FAIL` / `CARD_WALL` / `MEDIA_UNJUSTIFIED` / `RHYTHM_FLAT` / `BACKGROUND_DISGUISED` 当硬门槛） | 只判设计价值；工程码降级为**证据与扣分**，报告用 `domain: design_value` + `delegated_to_qa` 显式移交（边界可被自检断言） |
| Pre-Critic | 「只提前发现、不改设计」的风险清单 | 并入 Design Intelligence = **Risk Prediction**：起草前 `forecast_risk(brief)` 出 5 条生成政策，落稿后 `risk_strategy(spec, report)` 出 `adjusted` 政策 / `pages` 逐页修单 / `generation` 顺序；仍是建议不是闸门 |
| 渲染时机 | 三档模式 + 稳定性门控 + 预检闸门 + 关键页并受影响页 | 三档：**draft/sketch 零渲染** → **review 只渲染变化页**（无上一版可比时回落关键页）→ **release 全量**；无门控 |
| 缓存 | 编译视图 / PDF / 页级指标 / Critic 结果 / route 决策 + 语义投影 + 版本闸 + `cache_version` 迁移 | **两处**：编译产物复用（`spec_view` 指纹 + PPTX 字节核验 + PDF 归属）与页级渲染指标缓存；失效判据只有内容核验 |
| 跨轮状态 | `studio_state.json`（含 Critic 结果、稳定计数、几何投影）+ `last_spec.json` + 渲染缓存 + 元数据 | `render/<out>_render/` 下三个文件：`last_spec.json`、`render_meta.json`、`render_cache.json` |

## 2. 删除清单（可核对）

| # | 被删机制 | 原位置 | 删除理由 |
|---|---|---|---|
| 1 | Critic 稳定性门控（连续两轮 clean + 几何未变才介入） | `qa._stability_decision` / `_load_studio_state` / `_save_studio_state` | Critic 12 页 ~10ms，不是成本瓶颈；门控换来的是状态机与「为什么这轮没有批评」的调试成本 |
| 2 | `studio_state.json`（Critic 结果缓存 + 稳定计数 + 版本校验） | `qa.py` 读写路径 | 同上；且结果缓存会把旧评分语义带进新判定 |
| 3 | `critic_version` 作为缓存失效闸 | `qa.py` / `art_critic.py` 缓存命中判定 | 失效判据统一为「内容核验」，版本号只是同一件事的近似写法 |
| 4 | `COMPILER_VERSION` 编译缓存版本闸 | `render_check.compile_reuse` | 编译器行为变了产物字节就变了，字节核验已经覆盖 |
| 5 | `cache_version` 迁移层 | `render_check.py` | 缓存只有一层，不需要跨版本迁移；旧文件一律视为未命中 |
| 6 | 语义投影 `geometry_only_hash` 作为门控输入 | `normalizer.geometry_only_hash` → `qa` 调用点 | 「哪些页要重渲染」已由 `classify_spec_change` 显式决定，不需要第二条判据（函数本身保留，仅供自检/工具用） |
| 7 | `PREFLIGHT_HARD_CODES` + `preflight_gate`（不干净不渲染） | `qa.py` | 与「Critic 是否稳定」并列的第二道渲染时机闸门，同一件事在渲染判定里已算过一次；预检保留为诊断报告 |
| 8 | `--mode express` 第四档速度链 | `qa.EXECUTION_MODES` / `route` / 文档 | 与 draft 的收益重合，多一档只多多一个口径 |
| 9 | Critic 对工程事实的立案权（5 个硬门槛码 + 对比度/峰度/网格/FOCUS_LEAD 的扣分权 + 文本计数与密度带扣分） | `art_critic.evaluate_*` / `hard_gates` | 与 QA 重复判定；两套分数各自漂移时无法回答「该信谁」 |
| 10 | 外部实测存储（校准 JSON + 配套测量脚本） | `memory/calibration_space.json` 与其测量脚本（均未随包分发） | 引用不到的证据文件既不参与判定，又制造文档悬空指针；律内联为 `design_intelligence.CALIBRATION_LAWS`（文件存在仍可覆盖） |

**净删除的账**：`qa.py` 1142 → 1039 行（-103）、`art_critic.py` 1219 → 1192（-27）、
`render_check.py` 1437 → 1425（-12）；同轮新增的能力也记在账上：
`design_intelligence.py` 1127 → 1365（+238：风险预测与策略 + 内联校准律）、`selftest.py` +79（新增 4 个检查项）。

## 3. 复杂度度量（四个口径，全部由脚本从 git 基线与工作区对数数出，不是估计）

| 口径 | 方法 | before | after | Δ |
|---|---|---|---|---|
| **机制表面积**（判定时机 / 门控 / 缓存闸） | `qa.py`+`art_critic.py`+`render_check.py`+`guard.py` 中命中 `EXECUTION_MODES\|PREFLIGHT\|preflight\|stability\|studio_state\|_CRITIC_CACHE\|cache_version\|COMPILER_VERSION\|critic_version\|hard_gates` 的行数 | 101 | 51 | **-49.5%** |
| 同一口径，只算被拆掉门控的两处（`qa.py` 59→13、`render_check.py` 5→1） | 同上 | 64 | 14 | **-78%** |
| 同一口径中被刻意保留的两处 | 同上（`art_critic.py` 18→18 只是 `hard_gates` 换了成员，`guard.py` 19→19 是预检诊断本身） | 37 | 37 | 0 |
| 函数体内分支数（`ast` 计 `If/For/While/BoolOp/Try/Except/comprehension`） | `qa.py` 373→336、`art_critic.py` 425→405 | 798 | 741 | **-7.1%** |
| 总行数 | `qa.py` + `art_critic.py` | 2361 | 2231 | -5.5% |
| 净删除 / 净新增（同一 diff） | `git diff --numstat`：qa.py 159 加 / 262 删，art_critic 80 / 107，render_check 6 / 18 | — | — | 删 387 · 加 245 |

复现口径：`git show HEAD:<file>` 与工作区同名文件各跑同一条正则 / 同一 `ast` 遍历计数，不是手估。

口径说明：**没有把总行数当成主要成果**。删掉的是「判断要不要判断」的机制层（-49.5%，只看被拆的两处 -78%），
留下来的分支是「怎么判断」的实质逻辑（-7%）；而总行数几乎不变，是因为腾出的预算被新能力
（风险预测与策略、`verdict_of`、三个新自检项）填上了。目标是 40–60% 的 QA/Critic 复杂度削减，
在机制口径上达成（-49.5% / -78%），在行数口径上不成立（-5.5%）——如实记录，不拿口径凑数。

## 4. 计时（12 页基准 deck，LibreOffice 25.2.3.2 + pdftoppm）

数据：基准输出 `bench/out/base/base_bench.json`（改造前）与 `bench/out/after/after_bench.json`（改造后终版，工作区路径，不随包分发），下表数字取终版那次运行；
同一份 12 页基准 deck、同一个基准驱动脚本（工作区 `bench/`，不随包分发），序列：draft → review → release → release(暖) → review(暖) → draft(暖) → release `--no-cache`）。

| 场景 | before | after | 说明（after 为终版一次运行的实测） |
|---|---|---|---|
| draft（零渲染，冷） | 0.29s | **0.29s** | 持平；差别在首屏内容：before 是「pre-critic 风险清单」，after 是「风险 → 5 条生成政策」+ 同一份风险码（可执行） |
| draft（暖） | 0.24s / 0.22s | **0.20s** | 最快的一档略快（少了 studio-state 与 critic 缓存的读写判定） |
| review（冷，首轮） | 2.39s | **2.37s** | 持平（渲染集同为 6 页）；差别在结论：before 输出 `critic: deferred（deferred_geometry_changed）`——这一轮拿不到任何批评；after 直接给 `critic 88.2/100 REVISE` |
| review（暖，同一 spec 复跑） | 1.20s | **2.37s** | **本轮唯一明确变慢处（+1.2s）**：渲染集 = 变化页，而可比对象是首轮的 key-pages 计划，于是这轮把剩下 6 页也测了 → `pixel=12/12 / status=PASS / critic 90.9`，但 `release_eligible=False`（发布资格仍归发布链）；before 停在 `REVISE 6/12` 且 Critic 仍 deferred |
| release（冷，全量渲染 + Critic + Manifest） | 2.58s | **2.57s** | 持平；after 首轮即 `verdict=PASS / status=PASS / critic 90.9 / manifest=PASS`，before 首轮 `critic 86.1`，要两轮才收敛到 90.9 |
| release（暖，命中缓存） | 0.27s | **0.29s** | 持平（省时的主战场本来就在页级缓存，未受影响） |
| release `--no-cache`（绝对冷轮） | 2.57s | **2.58s** | 持平；多出的风险预测 12 页约 12ms，落在噪声里 |
| 一次典型往返（review → 修正 → release） | 4.0s（review 2.4 + 再 review 1.2 + 暖 release 0.3） | 2.7s（review 2.4 + 暖 release 0.3） | 少一轮的原因是**结果更早可得**，不是渲染更快：门控删除后第一轮就有批评，不必等「连续两轮 clean」 |

**结论（诚实版）**：本轮改造**没有**做出「3–5× 提速」——基准里唯一的成本是 LibreOffice 渲染，
而它在改造前就已被页级缓存吃掉（暖轮 0.29s vs 冷轮 2.57s ≈ 8.9×）。改造买到的是三样别的东西：
① 每轮 QA 多一个 `verdict`（PASS/FAIL/WARNING）与一份可执行的**生成政策**，少一次「为什么这轮没有 Critic」的追问；
② 结论更早：review 首轮就有批评（before 首轮 `critic: deferred`），release 首轮即 `status=PASS` + `critic 90.9/100`（before 需两轮，86.1 → 90.9）；
③ 机制少一层：`render/` 目录少一个 `studio_state.json`（`check_state_footprint` 现把它当回归来断言），
缓存少三类（Critic 结果缓存、编译版本闸、`cache_version` 迁移层），执行模式从 4 档缩到 3 档。
若要 3–5× 的绝对提速，下一步在渲染器（pdftoppm → 直接消费 soffice 的 PNG / 或按页跳过 soffice），
不在验证层的门控里——这条已写进路线图。

## 5. 回归与自证

- `python3 scripts/selftest.py` → **52 项全 PASS**（改造前基线 49 项 PASS / 2 FAIL，两项失败是旧契约断言，已按 vNext 契约重写）。
- 反向断言（防止机制复活）：`check_execution_modes` 断言 `qa` 模块**不再有** `_stability_decision` / `_load_studio_state` / `PREFLIGHT_HARD_CODES`；
  `check_state_footprint` 断言 `render/` 目录只允许出现 `last_spec.json` / `render_meta.json` / `render_cache.json`；
  `check_critic` 断言工程码不在 `hard_gates` 且 `domain == "design_value"`、`delegated_to_qa` 完整；
  `check_compile_version_gate` 断言「陈旧的 compiler 戳不再让缓存失效，而被篡改的 PPTX 一定失效」。
- 文档同步：`SKILL.md`（执行模式表 / 质量门 / 缓存与省时三句 / 路由表）、`README.md`（能力表、CLI、自检说明、版本史 v3.1）、
  `references/production-contract.md`（Responsibility Boundary 新增、Modes 表、门控删除说明、缓存清单、CLI 参数、性能键）、
  `references/design-intelligence.md`、`references/themes.md` 全部改口径；`check_references` 现在也能过（悬空脚本名已清）。

## 6. 保留清单（明确不删，及理由）

| 保留物 | 为什么留着 |
|---|---|
| `guard.py` 的 error 级检查（结构合法性、数据诚实性、`TEXT_FIELD_*`、越界） | 工程正确性唯一入口；设计契约类条目降为 warn/hint 诊断（`preflight_hint` 权重 0.0） |
| `normalizer.py`（网格/token/间距机械归一化） | 幂等、无判断、可退出；它消除的是「同一事实两种写法」，与门控无关 |
| `compiler.py` + `charts.py` 契约 | 唯一能把 spec 变成可编辑 PPTX 的地方；`COMPILER_VERSION` 保留为标识，但**不再参与缓存判定** |
| `route.py`（`plan_deck` / `one_pass_plan` / `deck_decision` / `recommend_mode`） | 决策入口，把风险政策在起草前固化一次，避免每页重算 |
| `memory/design_dna.json`（180 条判断记忆） | 判断记忆不是结果记忆（`record_dna` 拒收色值/实测字段）；省的是「重新想一遍」 |
| 质量预算 / 媒体决策 / Layout Grammar 搜索 / `auto_fit` | 都是生成期杠杆（改设计），不是判定期门控（改流程） |
| `classify_spec_change` + `last_spec.json` | review 只渲染变化页的依据；这是省时的来源，删了就退回全量渲染 |
| `source_spec_hash` 互证（QA / Critic / Manifest） | 与门控不同，它防的是「报告说谎」，不是「跑几次」 |
| `visual_calibration_score` | 只作判断辅助分（~0.3ms），不参与任何发布判定 |

## 7. 下一步（未做，附条件）

1. **渲染器提速（已量到底，结论：不做）**：冷轮的 2.9s 里 soffice 整份 PDF 转换 = 1.436s、pdftoppm
   栅格化 = 0.557s（tiff+lzw，2 chunks）。`soffice` 只能整份转换（无按页接口，实测 daemon/复用 profile
   后裸启动仍有 0.12s），换 JPEG 只省 ~8% 栅格化时间且仓库已判定 `RASTER_DEFAULT="tiff"`（像素一致性优先，
   见 `references/production-contract.md §Progressive QA`）。**唯一还能省的是「少转一次」**：review 与 release
   共用同一 `--render-dir` 时，第二轮直接命中 `render_meta` 的 `pptx_sha`，省掉 1.4s——已在实测里（0.30s）。
2. **规模阈值**：当每天 >1000 deck 时再考虑第二层缓存（跨 out_dir 共享页级指标），当前 out_dir 内两层足够。
3. **风险预测的闭环校准**：`forecast_risk` 的政策命中/落空目前只进日志；把它与 `qa["risk"]["strategy"]["adjusted"]` 的实际效果做差，
   才是下一个值得加的存储——而不是把门控加回来。


## 8. v3.2 实测（运行时浪费 + 认知负担）

同一份 12 页基准 deck（工作区 `bench/build_bench_deck.py`，不随包分发），LibreOffice 25.2.3.2 + pdftoppm，
best-of-4/5。数字都是本轮重跑的实测，不是引用 §4。

| 项 | 实测 | 说明 |
|---|---|---|
| `import qa` / `guard` / `art_critic` | 0.011s / 0.015s / 0.013s，**`pptx` 不在 `sys.modules`** | `primitives` 的 pptx/lxml 全部改懒加载（`_p()`）；判读链从此不碰编译层 |
| `qa.py --mode spec`（新增档） | **0.049s** | python 启动 + Normalizer + Guard + 风险预测，**不 import pptx/lxml/compiler、不写任何文件**（`ls <out_dir>` 为空）；`status=PREVIEW_ONLY`、`execution.compiled=false` |
| `qa.py --mode draft` | 0.169s（v3.1：0.29s） | 仍产出可编辑 PPTX：**46970 bytes、60 个 zip part 与 v3.2 前逐 part sha256 一致**（视觉输出零变化）；省下的 0.12s 全在 import 地板 |
| review / release（暖，同一 out_dir） | 0.250s / 0.302s | 缓存全命中，`release_eligible=True`；冷 release 2.91s（soffice 1.44s + pdftoppm 0.56s 主导） |
| 文档（always-read 面） | `SKILL.md` **33.9KB → 25.9KB（−23.9%）** | 契约表移入 `production-contract.md`（唯一权威）、引擎细则移入 `design-intelligence.md 附录 A`、三段复用实现细节移入本文件；SKILL 只留原则 + 指针 + 硬边界，并**新增**「设计判断：原则优先于规则」与案例库入口 |
| 设计法律 → 代码 | `guard.DESIGN_RULES`（17 项）标 `advisory` + `score_weight=0.0`，且**永不以 error 出现**；QA 侧 `design_advisory` 权重 0.0 | 基准 deck 的 4 条 rhythm/typography 提示从「每条扣 0.1」变为 **−0.0**；行长超出 fail factor 重定性为 `text_capacity`（内容被切断＝工程事实，仍可阻断），背景层资格改名 `background_layer` |
| Art Critic 主输出 | `diagnosis{question, assessment, strengths, risks, advice, score_semantics}` | 纯重排已有证据（零新增测量）；`deck_score` 保留但降级为**置信度**，「分数变化不得作为修订理由」写进契约与 `score_semantics` |
| 回归 | `python3 scripts/selftest.py` → **54/54 ALL PASS** | 新增 `[design_advisory]`（设计条目不扣分不阻断 + `spec` 档 compile=False）与 `[draft_import_contract]`（spec 探针禁加载名单 + release 必须加载 pptx + 共享 render_dir 复用证据） |

**未达成项（诚实记录）**：`production-contract.md` 41.5KB → **51.2KB（变大了）**——它是按需查的权威表，
本轮把 SKILL 的字段级契约表与 Guard/Critic 的定性说明搬了进去，同时只削掉 3.5KB 实现细节；
`references/` 总量因此没有下降。真正被裁掉的是**每次调用都要读的那一层**，这是速度收益的正确口径，
不是把知识删掉。若还要压 references，下一刀应该在 `themes.md`（13.6KB，方向族细则）与
`design-intelligence.md` 的 V3 校准节，判据同 v3.2：能由代码表达的移进常量与 selftest，
不能的留在 `design-craft.md`。

---

## 附录：三段复用的实现细节（v3.2 从 production-contract.md 移入）

> 契约只需知道判据（见 `references/production-contract.md §复用三段重复劳动`）；
> 这里保留实现口径与实测理由，供维护缓存时查。

### 复用三段重复劳动（去掉重复渲染 / 重复转换 / 重复编译）

`render_evidence` 在 `out_dir` 里维护 `render_cache.json`：

- 键 = `sha256(本页 spec + canvas + dpi + 完整 theme + 页内图片 (name,size,mtime) + 渲染器路径 + 显著图后端 + 键代次标识)`；任何会影响本页像素的输入都进键，因此**其他页的改动不会让本页失效，而重新出图、换主题字、换 LibreOffice 或换显著图后端一定会**（cv2 与回退算法的质心/分片不可互换，跨机器共用证据目录时必须分键存放；旧代次键自然淘汰）。
- 命中还要求：条目记录的 `png` 文件仍在目录里，**且文件内容指纹 `png_sha` 一致**。只比文件名会把别页像素当本页复用（曾真实发生过：命中 12/重测 0，却返回错页指标）；旧格式（无 `png_sha`）条目一律不信任、直接重测。
- 每轮渲染使用唯一 PNG 前缀 `page-<token>-r<idx>-<绝对页码>.png`，只按绝对页码认领文件；缺页记入 `coverage.unrendered`，绝不按结果序号回退猜页——宁缺勿错。
- `use_cache=False` 的冷测不清空证据目录（只增加文件），因此一次冷测不会把别人的热缓存打回冷态。
- `out_dir` 一律先 `resolve()`：相对目录会拼成非法 LibreOffice profile URI，`soffice` 将卡在 profile 锁上直至超时。
- 全部页命中时直接返回，不启动 LibreOffice/pdftoppm；写缓存时只保留当前 deck 的键（自动裁剪，不会长胖）。
- `coverage` 增加 `cache_hits / cache_misses`，`qa["performance"]` 透传同名两项，作为“这一轮省掉了多少”的凭证。
- 键的口径：页级投影按**排除法**取字段——`NON_PIXEL_SLIDE_KEYS`（`page_intent` / `source_zone` / 备注 / 评论）与 `NON_PIXEL_THEME_KEYS`（`constraints` / `notes` / `description` …）之外的全部字段都进键。排除法保证将来新增的视觉字段自动进键、不会漏测；唯一被点名保留的是 `page_intent.focus`：它不产出像素，却决定量哪个元素的墨量占比，所以必须进键，否则改 focus 会拿到上一版的 `coverage_ink`。`selftest.check_cache_projection` 会扫描 `compiler.py` 实际读取的 slide 键与 `primitives/charts/elements` 读取的 theme 键，任何被排除表屏蔽的渲染输入都会让自检失败。
- **PPTX→PDF 整份复用**：soffice 只能整份转换（实测 1.70s），而 Level 2→Level 3、改 dpi 抽查、只改声明的修订都不改变 pptx 字节。`render_meta.json` 记下 `pdf = {name, pptx_sha, renderer}`，命中条件仍是内容核验（pptx 逐字节一致 + 渲染器路径一致 + PDF 仍在且页数 > 0）。Level 2 后补齐全量：2.57s → 0.82s。
- **编译复用**：`spec_view(spec)` = 会被编译成像素的那部分（canvas + theme 投影 + 每页 background/elements/id + 图片 size·mtime）。它与磁盘上 pptx 的内容指纹双重核验后才允许跳过 `compile_deck`，跳过后 `file_bytes` 按磁盘实际值刷新，`compile_reused=True` 进 performance。只改 `density` / `insight` / `focus` / 备注的一轮：4.8s → 0.01s，且像素质标与独立冷测逐位相同。
- 冷测（`use_cache=False`）既不查也不写：不查以免读到旧值，不写以免一次「隔离测试」改变别人的热态；`--no-cache` 之后紧跟的一轮会照常重编译（0.7s），再往后才是 0.0s。
- 关闭：`run_qa(..., use_cache=False)` 或 `qa.py --no-cache`；换渲染器、怀疑陈旧时用它做绝对冷测。

**为什么不再加一条线程**：一轮全量实测成本 = guard 2ms · 编译 179ms · soffice 1704ms · pdftoppm 241ms(1 页)/1002ms(12 页) · 像素量测 75ms/页 · 批评 2.7ms。复用把「重复」拿掉之后，剩下的是无法拆开的串行重流，再加线程只增同步成本。因此「设计推导 / 资产·渲染」两线由 `route.py` 的 `pipelines` 分工表达（互不通信、在 `run_qa` 汇合一次），`run_qa` 内部只保留下述一处并行：

并行只发生在渲染阶段内部：`_plan_jobs()` 把请求页压成连续区间并按 worker 数二分（避免一核空转），每个 worker 内「poppler 转换 → 像素测量」串行执行、块与块之间并行（去掉两次全局栅栏）。`MAX_RENDER_WORKERS = 2` 且再按 `os.cpu_count()` 收敛；页数 < 4 时自动降为串行（单次 pdftoppm ≈ 117ms，调度成本同量级）。不做无界并发、不做多进程池、不引入新依赖。
