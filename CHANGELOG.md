# 变更记录

## 5.6.0 · 第五轮审计：规则层减法 + 图像留白从「画上去」回归「打出来」

一个真实案例（15 页茶品牌 A 轮路演，release PASS）暴露了两件事：**坐标写在提示词里，
模型会照字面画**；**包发明审美数字，再让 guard 判卷，在整幅画心页上必然误报**。
按「删除 → 合并 → 简化 → 复用」处理，不新增抽象：

**删除（guard.py −164 行）**

- 9 条品味规则（只发 warn/hint、从不构成门槛）：`accent_budget` `alignment_budget`
  `color_budget` `decoration_budget` `icon_consistency` `type_budget` `animation_budget`
  `rhythm` `title_semantics`——强调/留白/层级/节奏/标题语义都是设计判断，
  不该由固定阈值描述。设计契约清单同步收窄。
- `text_capacity` 的 warn 变体（「叙事行数偏多」）：与阻断级的溢出判定重叠，只留后者。
- 方向预设里 4 组 × 7 个审美数字（留白下限/字号级差/装饰面积/粗体占比/背景层/Accent 上限）：
  包不再替作者发明承诺。**能力未减**：作者把它写进 `spec.theme.constraints` 照旧被执法
  （`check_direction_seed` 覆盖），只是不再自动填。
- 死配置与残留：`_SAFE_ZONES`、`accent_area_max`、9 个无消费者的阈值局部量、
  8 个供已删规则用的累积量（`alignments` / `semantic_colors` / `decoration_area` /
  `icon_styles` / `font_levels` / `font_families` / `slide_accent_area` / `animation_types`）、
  2 个死函数（`_density_class` / `_looks_like_field_name`）、4 处未消费的局部与导入。
- `qc_policy` 双源合并：asset manifest 的策略改由 `asset_prompt.qc_policy()` 派生。
  此前清单与执法可以不一致（实测：`negative_space_ratio` 已降级，清单仍写 blocking）。

**能力升级（唯一新增逻辑）**

- **`hard_seam`（阻断）**：满高度列均值阶跃 + 阶跃一侧整带方差 < 1.2 灰阶 ⇒ 留白是被
  画出来的平板。物理判据，不是品味：真实光影边界一侧仍有材质纹理（实测 1.7–5.3），
  假面板 0.4–0.6。透明画布（Logo / 插画）豁免——平色在那里是设计本身。
- **`negative_space_ratio` 从阻断降为 advisory**：它量的「平坦块占比」恰好被假留白面板
  抬高——指标越漂亮，图越假。判断归设计智能，QC 只守物理事实。
- **资产提示词不再写坐标**：`safe_area_phrase` 改说材质与光的衰减（「quiet and unbroken,
  its tone coming from light falling off across the material」），不写 `x 6% y 8% w 34%`。
  根因证据：两张交付资产在 18% / 33% 画宽处出现 8 / 29 灰阶硬边，一侧整带标准差 0.8 / 0.6
  ——被圈出的坐标被模型画成了硬边平色板，还骗过了平坦块指标。通用反向同步补
  `flat painted panel` / `hard-edged rectangle of flat tone` / `visible seam or step edge`。
- QC 报告标签改为反映真实检查区域（右锚点曾打印成「安全区（left）」）。

**边界校正（第二轮）**

- 三个审美刻度改声明制：`hue_families_max` / `accent_hue_min` / `chart_label_scale_tol`
  不再带发明默认值（4 / 12° / 1.25）——颜色多不多、强调够不够、图表风格统不统一属设计判断，
  作者写进 `rules` 或 `theme.constraints` 才执法。白名单同步：删掉四个"写了等于没写"的键
  （`accent_max` / `decoration_area_max` / `font_families_max` / `font_levels_max`），
  补上三个真会被读的键。
- 删 `design_intelligence.color_plan.constraints`（4 键、零消费者）与 `CALIBRATION_LAWS`
  （10 行常量表，唯一读者随前者消失）。
- §21 词汇统一：对外只发布 **BLOCK / PASS / TRACE** 三态。`warn_summary` → `trace_summary`，
  verdict 里的 `warnings` 计数 → `trace`；TRACE 只记录证据，不触发修复、不进入对话。
- 自检补 5 条**否定边界**（§33）：审美永不阻断 / 未声明不执法（声明才执法）/ 证据≠错误 /
  Guard 只读不改稿 / 资产提示词零几何坐标 / 生产脚本不读 references——共 155 项。

**边界校正（第三轮：背景图 vs 插图）**

- 新增 `negative_space_anchor: none` / 显式空 `safe_area` 语义：版面不压文字时
  （整幅画心、半幅出血带），提示词不再索要安静面，QC 的相关检查记为不适用——
  没有文字压图，就没有安全区。此前它会静默回落到默认矩形，等于用一个不存在的
  文字层去要求模型留白。
- 无安全区时过滤空指令：`negative space reserved and aligned to the text-safe area`、
  `leading lines drawing the eye toward the negative-space anchor` 这类句子在
  "none" 下不再进提示词（一条空指令也不要）。
- `hard_seam` 与 `brightness_balance` 抽为共用函数（两条返回路径同一实现）。
- `design-system.md` 增加「背景图 vs 插图」判定行：有文字压图 → 背景层 + overlay；
  栏内配图 → 插图，必须让开元素与来源区。案例里正是插图越界来源区被 `SOURCE_COLLISION`
  拦住（背景层的豁免权不适用于插图）。

**验收**：自检 155/155 通过；案例重跑 release PASS，15 页产物与指纹链完整，
`trace_summary` 为空。



## 5.5.0 · 第四轮深度审计：spec 级二审层切除（Phase 15 三域证据驱动）

Phase 15 跨域盲测（城市研究 / 品牌融资 / 科技发布三套 deck，全部 release PASS、
反模板 8/8 差异成立）给出的证据：设计判断发生在**起草时**（作者=AI 直接写 SPEC），
spec 级「生成后再审」层在五轮生产中零消费（`--advisory` 默认关、从未开启）。
按「删除 → 合并 → 简化」处理：

**删除（净 -1049 行，其中 Python -1057）**

- `design_intelligence.pre_critic`（414 行）+ `risk_strategy`（140 行）：
  spec 级风险二审与策略翻译。唯一消费者是 `qa.run_qa` 的 `include_advisory`
  分支（默认关）。forecast_risk（plan 期，真实消费）保留全部政策能力。
- 9 个仅被二审层消费的私有 helper：`_theme_colors` `_hex_of` `_area`
  `_chart_accent_ratio` `_accent_share` `_risk` `_weighted_centroid`
  `_layout_fingerprint` `_overlap`。
- `calibration_laws()` 包装器 + `CALIBRATION_FAMILIES`（空壳 dict）：
  color_plan 直连 `CALIBRATION_LAWS` 唯一真源。
- `design_intelligence_rules` 九个孤儿常量：`RISK_CATALOG`(18 码目录)
  `LADDER_RUNGS` `LADDER_TOL` `TYPE_WEIGHTS` `BAR_FAMILY`
  `SMALL_ACCENT_CHART_SHARE` `TEXT_INK_FACTOR` `SHAPE_FILL_FACTOR`
  `ASYMMETRIC_OK_FAMILIES`。
- `primitives` 死基元群（v4.15 自已删除的批评层下沉的遗产，宿主已亡）：
  `filled_panels` `memory_anchor` `content_occupancy` `is_background_layer`
  `background_layer_ok` `bg_exempt`（guard 有自己的 `_bg_*` 实现）+
  `_slide_elems/_slide_field/_num_e/_area_e` + 11 个孤儿常量
  （`FOCUS_LEAD` `FOCUS_AREA_LEAD` `STATEMENT_SIZE` `MEDIA_ROLES`
  `MEDIA_BUDGET_MAX` `TEXT_BUDGET_MAX` `PANEL_MAX` `PANEL_MIN_SIDE`
  `PANEL_MAX_SHARE` `RHYTHM_INK_DELTA` `RHYTHM_INK_FLAT`）。
  guard 经 `_cached_gate` 直连的 `BG_MIN_*` / `LINE_MEASURE_*` 保留（活消费）。
- `qa.run_qa` 二审分支与 `result["risk"]`/`advisory_ms`/`risk_items` 字段；
  selftest 卡片墙三连测（判据函数已不存在）与 pre_critic 探针。

**不动的部分（有证据保留）**

- guard.py / compiler.py / ghost.py / asset_prompt.py 全量：五轮生产零误伤，
  「无明确证据不改」。guard 的 16 条 DESIGN_RULES advisory 保留——`--advisory`
  是设计契约诊断的唯一入口（selftest 断言开关有效性）。
- `apply_fit_ladder`：显式 opt-in（`auto_fit:true`）的授权吸附，非自动修复循环。
- `--polish`：请求式服务，有测试、有独立价值。

**文档同步**：production-contract（预测码三行改为 guard/forecast 实际语义）、
design-intelligence（布局指纹风险 → `forecast_risk.layout_monotony`）、
design-system（焦点度量去掉不存在的 1.25× 领先常量，改为 guard 实际逻辑）。

**合并（近重复扫描：191 函数 token 归一化配对，阈值 0.72，全库仅 4 对）**

- primitives 的 `json_write` = 原子 JSON 写入全库唯一实现（vao._json_write 与
  compile_cache._atomic_json_write 原是两份实现，现均委托；indent/fsync 是口味参数）。
- `series_highlight_index` 复用 `highlight_index`（序列名=label 列表，同一语义一份实现）。
- 其余 2 对为合法兄弟（几何谓词 inside/intersects）与嵌套包含误报，不动。

**回归**：selftest 151→148 项全过；三域 bench（urban/outdoor/tech）release
round 1/6 PASS；plan 输出字节级一致（仅删一句陈旧 note）。

## 5.4.9 · 第三轮深度审计：plan 输出字段级零消费者清理（输出 schema 减法）

5.3.0「删除全部零消费镜像字段」的同款方法，用在 5.4.x 期间重新长出来的 plan bundle
输出上。逐键追踪消费者（脚本 grep + 骨架序列化面 + 文档承诺面 + selftest 绑定面
四重核对）后删除：

**删除的零消费者输出键（生成后无人读、骨架不序列化、文档零承诺）**

- `deck_decision.density_curve` / `density_profile`：每页密度在 `plan.pages[].density`
  已有，曲线与直方图是镜像的镜像。
- `color_plan.ratio_targets` / `forbidden` / `derivation`：静态常量镜像与固定字符串
  ——每次 plan 输出同样的字节，零信息量。面积律（70/20/8/2）的槽位语义活在
  design_intelligence 的 seed 别名逻辑与其注释里，不需要随 plan 再发一份。
- `color_plan.motion_keys` / `texture_keys`：方向族的 motion/texture 由
  `direction_execution`（route）承载并被资产链真实消费；color_plan 里是第二份拷贝。
- `forecast.planned_mode`：`deck_decision.execution.mode` 的拷贝。
- `one_pass_plan` 返回的 `policy` 键与 pipeline 的透传：`forecast.policies` 的两跳
  纯转发，全库无人读 bundle.policy（forecast 内的 policies 本体保留——那是内容触发的
  plan 期判断脚手架，属「判断前移」）。

**随之删除的死代码**：`COLOR_RATIO_TARGETS` / `COLOR_FORBIDDEN` 常量（唯一消费者是
上述镜像键）、route 的 `Counter` 延迟 import。

**证据化确证不动的部分**

- AST 函数级克隆检测（14 脚本 × 292 函数，全量 dump 同构 + 前缀同构双扫描）：
  **零克隆对**——函数体级无重复逻辑。
- `color_plan.material_language`（pipeline 骨架回退消费）、`constraints`/`seed_skeleton`/
  `seed_source`/`family`（骨架与 selftest 消费）保留。
- DNA 经验库（memory/design_dna.json，v2 schema，真实判断条目）不做预填充升级：
  写坏的记忆比不写更贵，`proven` 必须来自实测——库由真实使用喂大，不伪造种子。

plan.json 每轮更瘦（调试读取的 token 更少），生产路径行为零变化：资产提示词、
骨架、guard、编译、发布凭证全部不受影响（bench② 资产指纹 `asset-f33af639f039`
在本版前后不变）。代码净 −15 行（三轮累计 −113）。

回归：selftest **152/152**；bench① release PASS 302ms；bench② 全链
（plan→assets→出图→asset-qc→check release）PASS 1198ms，指纹链按真实流程重建
（既有字节防伪机制如预期点火，删图重走 assets 后通过）。

## 5.4.8 · 第二轮深度审计：AST 全库可达性清零（行为零变更）

5.4.7 审计的继续深挖。方法升级：一次性 AST 分析全库 15 个脚本的模块级函数调用图
（从 vao/selftest 入口 + 模块加载根植，含 `from X import Y as Z` 别名与函数内延迟
import），297 个定义中初判 14 个不可达，修正别名盲区后收敛到 5 个，逐个全词边界
grep 复核（防动态调用/子串误配）后删除：

- `compiler.py::_safe_index` / `_highlight_index` / `_series_highlight`（死链三件套：
  highlight 解析早已去重到 `primitives.highlight_index` / `series_highlight_index`，
  本地旧拷贝只剩互相调用，无外部消费者）
- `guard.py::_filled_panel`（`primitives.filled_panels` 的单元素旧拷贝，di 用的是
  primitives 版；判据注释已随迁移保留在 primitives）
- `route.py::_alternative_route_key`（兜底留痕 helper，零调用点）

复核确证不删的部分（证据在案）：

- **guard 三个 focus 族不重复**：`focus_contract`（error/warn：focus 是否绑定到存在的
  元素——工程事实）、`focus`（hint：未声明）、`focus_scale`（hint：文字焦点尺度）
  ——绑定合法性 / 存在性 / 尺度是三个不同问题。
- **22 条 forecast 风险码全部有触发路径**：plan 期 `forecast_risk`（骨架，意图/结构类
  规则）+ check 期 `--advisory` 的 `pre_critic`（完整 spec，元素级规则，默认关闭、
  按需读取）。每条规则预测一个具体 guard 结果并带置信度——这是「判断前移」的实现，
  不是重复判断；selftest 仅绑定 `CARD_WALL_RISK`，其余按内容触发。
- **颜色解析微重复不合并**：primitives（口径真源）/ guard 色相族 6 行 / ghost PIL
  元组版各自目的不同（pptx / 分析 / 渲染），合并收益 < 回归风险。

删除后复跑可达性分析：**292/292 全部可达，零不可达函数**。
代码净 −69 行（compiler −36 / guard −25 / route −8）；两轮累计 −98 行。
回归：selftest **152/152**；bench① release PASS 187ms；bench② 全链 PASS 814ms。

## 5.4.7 · 全包深度审计：死代码清理 + 摘要函数合并（行为零变更）

按「删掉复杂度，而不是删掉能力」对全技能包做七层审计（Intelligence / Context /
Architecture / Execution / Design / Production / Verification），只实施确证零价值损失的部分。

**删除（死代码，全库零消费者确证）**

- `primitives.py` 死常量 ×11：`AXIS_LINES` / `GOLDEN_LINES` / `AXIS_NAMES` / `AXIS_TOLERANCE`
  （5.4.6「轴线幽灵」的代码源头）、`ANCHOR_DRIFT` / `LR_SPLIT_MAX` / `ASYMMETRIC_GRAMMARS`
  （语义活在 design_intelligence 实际检查处的字面量里，常量是已移除旧评审模块的遗骸）、
  `TEXT_MAX` / `MEDIA_CHART_MAX` / `ROUNDED_MAX` / `ROUNDED_SHAPES`（被 `TEXT_BUDGET_MAX` /
  `MEDIA_BUDGET_MAX` / `PANEL_MAX` 取代后无人引用）。
- `LAYOUT_MONOTONE_RISK` prevention 文案与 5.4.4 原则对齐：「相邻页至少改一个构图算子」→
  「连续同指纹就是变化的内容理由」（该风险仍是条件性诊断，触发逻辑未动）。

**合并（同一函数三份实现）**

- 全文件 SHA-256：`asset_workflow.file_digest` / `compile_cache._file_sha_full` /
  `qa._sha256_file` 三处逐字节同构 → `primitives.file_digest` 全库唯一实现，三处别名引用
  （asset_workflow re-export 保持 vao 的既有 import 路径）；`compile_cache._file_sha`
  （缓存键短指纹）改为截取 `file_digest` 前 16 位——短/全指纹从此同源，不会口径漂移。
  primitives 是最底层（stdlib + 懒加载 pptx），无循环依赖；draft import 契约不受影响。

**同步**

- SKILL.md §09：「标准四轮（无图两轮）」→「`run` 是标准生产入口；实际轮次由资产数量、
  QC 状态与根因修订决定，不为凑轮次增加无意义调用」（5.4.6 固定轮次契约删除的漏网点）。

**审计结论（确证有价值，不动）**

- 规则栈三层各司其职：10 阻断码（工程事实）/ `DESIGN_RULES` 16 条 advisory（留痕不阻断）/
  22 条 forecast 风险（plan 期前移预测，`risk_strategy` 按需读取，默认 QA 不运行）。
  逐族核对触发条件：`RHYTHM_FLAT`（相邻对占用差）/ `RHYTHM_FAKE`（标签空转）/
  `LAYOUT_MONOTONE`（≥3 页指纹 run）/ guard `rhythm` hint（spec 期真实几何、仅声明与结构
  同时重复才发）各有独立触发输入——是「判断前移 + 交付复核」，不是重复判断。
- Context：SKILL.md 275 行；§10 Context Economy 已是 just-in-time（「只读当前任务真正
  需要的那一份，永不为了保险预载全部」「Reference 是外部记忆，不是上下文负担」）。
- 调用链：`run` = plan+assets 合并点；`check` = normalize → guard → compile → preview
  单进程一次完成；没有只会传递信息的中间层。
- 死函数扫描的 4 个可疑对象（`alignment_warnings` / `blend_toward` / `load_rounds` /
  `ghost_page`）经入口可达性追踪全部存活（模块内活链调用），不删。

代码净变化 **−29 行**（6 文件）。回归：selftest **152/152**；bench① release PASS 251ms；
bench② 全链（plan→assets→asset-qc→release）PASS 1074ms。

## 5.4.6 · 运行时契约减法：审美代理指标全部退出硬门（纯文档，行为零变更）

对 `production-contract.md` 与 `asset-workflow.md` 做 Contract 减法。审计先行：逐项核对
代码等级后发现**代码分层本来就是对的**（`BLOCKING_CODES` 10 码 + `DESIGN_RULES` 16 条
全部 advisory 不进门槛 + forecast 风险预测非闸门），问题在文档——Contract Map 把三层混在
一张表里且不标等级，把 advisory 写成了硬门的样子。

**production-contract.md：三层切干净**

- 卷首分层表：**Contract/Guard**（文件/数据/结构正确、可编译、无溢出、无碰撞、资产链完整
  → 阻断）/ **Advisory-Risk**（可读性、节奏、焦点、视觉异常 → 只进 `warn_summary`）/
  **Intelligence-Craft**（高级感、审美、构图、节奏、视觉价值 → 不属于 Contract）。
- Contract Map 拆成**硬门表**（10 行，每行标注对应阻断码）与 **Advisory/Risk 表**（9 项
  设计代理指标，每项标注度量常量与等级）。焦点尺度（`FOCUS_LEAD` 1.25×，hint，仅文字焦点）、
  记忆锚点（`STATEMENT_SIZE` 40px，风险预测）、密度节奏（占用带 + `RHYTHM_INK_DELTA` 0.10，
  hint 且仅声明与结构同时重复才发）、Accent ≤5% / 色相族 ≤4（constraints 声明数字执法，
  warn）、媒体覆盖 ≥60%（`BG_MIN_*`，warn/hint）——全部明确为非阻断线索：
  **变化不是目的，必要性才是目的**。
- **删除文档幽灵「焦点落任一轴线（1/4·1/3·0.382/0.618）」**：审计确认 `AXIS_LINES` /
  `GOLDEN_LINES` / `ANCHOR_DRIFT` / `AXIS_TOLERANCE` 在 primitives 定义后**全库零消费者**，
  没有任何检查在读它们——文档却把它写成契约，作者会照着对齐一个不存在的检查。
- 「密度节奏」行明确 `sparse/balanced/dense` 是**输入语义**（声明枚举合法性才是工程事实），
  数字带只是预测参考值，不是「这页必须和上页不同」的义务。
- 保留并置顶：`composition.grammar` 提案定位（不给坐标、不给版式、可整体推翻）、
  `fix_plan` 根因聚类一轮批量修复、**没有 score 也不恢复 score**（总分会让系统退化成
  规则→指标→分数→排名→模板化优化）。
- v5.1 / v5.1.1 两段历史条款合并为一节；Spec minimum、Calls、执行模式、Release Manifest
  契约事实原样保留。

**asset-workflow.md：职责收敛 + 执行路径减法（v5.4.0 → v5.4.6）**

- **`run` 是标准生产入口**：补子命令心智图（run / plan / assets / asset-qc / check），
  Skill 层只暴露 `vao.py`。
- **删除「有图 4 轮 / 无图 2 轮」固定轮次契约**（README 标题同步）：实际轮次由资产数量、
  QC 状态和必要的根因修订决定，不得为满足固定轮次增加无意义调用——速度来自减少不必要的
  工作，不是规定必须跑几轮。
- **清单字段两层化**：作业上下文只需九个字段（asset_id/slide_ids/decision/prompt/negative/
  ratio/safe_area/expected_filename/status）；指纹与生产控制（plan_sha256/brief_sha256/
  preexisting_sha256/attempt/retry_budget/run_id/版本）由运行时内部保存——
  **证据可以复杂，AI 的工作上下文不能复杂**。
- **retry 改根因驱动**：失败 → 判根因（prompt/subject/构图/asset requirement）→ 一次根因
  修正 → 重新 QC；`retry_budget` 只是生产控制上限，不是设计输入，不做次数循环。
- **资产职责两行化**：资产只承担视觉叙事（asset_function 六枚举）；PPT 原生对象承担信息
  （文字/数据/图表/表格/Logo）——图片不烘焙正文、图表、Logo。
- **§7 明确 Asset Integrity ≠ Design Quality**：QC 回答「PPT 用的是不是被检查的那张图」
  （存在/可读/尺寸/比例/SHA-256/绑定/清单），不回答「图够不够高级」（主体/构图/留白/
  光线/视觉世界契合归 Intelligence + Craft + 人眼）；QC 没有、也永远不加 artistic /
  beauty / prompt-adherence / premium 一类审美评分。
- §1 补六层分工表（Intelligence / Craft / Asset Contract / Asset QC / Production Contract /
  Release Manifest 各答一问）；证据链条款（§4 绑定 / §6 失效表 / §8 最低校验）原样保留。

字节账（诚实）：production-contract 10,599 → 11,864（+12%），asset-workflow 8,926 →
11,425（+28%）。增量全部是要求的分层结构（三层表 / advisory 等级表 / 六层分工 / 入口树 /
两层上下文 / Integrity-Quality 分离）；按**规则口径**算：硬门收敛到 10 码、9 项审美代理
指标 100% 降级为标注等级的 advisory、1 个幽灵指标删除、固定轮次契约删除——契约的
「不可争辩部分」变小了，文档变厚是因为把边界写明了。

遗留观察（未动代码）：primitives.py 的 `AXIS_LINES`/`GOLDEN_LINES`/`ANCHOR_DRIFT`/
`AXIS_TOLERANCE` 是零消费者死常量，可在后续版本清理。

回归：selftest **152/152**（含阻断码 10/10 列全断言）；bench① release PASS 205ms。
代码零改动。

## 5.4.5 · design-system.md 三层切分：System 不越权（纯文档，行为零变更）

按「**Intelligence 越来越聪明，System 越来越简单**」做 cross-file deduplication：

**删除/移走（执行层里的越权内容）**

- Canvas 叙事规则退出：「相邻两页换密度、重心或版式其一」与「全套走建立→聚焦→展开→
  证据→收束的空间曲线」删除，改为「**System 不要求相邻页面必须变化**；Intelligence 决定
  要变化之后，System 只负责把这个变化稳定实现」。空间曲线是 `narrative_arc` 代码默认
  （establish/explain/prove/recommend/close）的散文变体，Intelligence 的 Narrative Reference
  已有，属重复叙事。
- 卷首「判断顺序八连链」删除：判断排序在上游（Intelligence Design Judgment / Craft 五判断
  已覆盖），执行层不做审美排序。
- 方向节瘦身：与 Intelligence §04 重复的「方向三问」「派生顺序」删除；置顶声明「本段只管
  参数解析 → 默认值展开 → token/primitive 落地；为什么选方向在 Intelligence，方向高级吗
  在 Craft，System 不代答、不扩建预设库」。4 结构预设 + 13 色彩方向族注册表**原样保留**
  （代码消费的名字合同）。
- 「一次只混一个维度」移入 `design-craft.md` §Expression——设计判断不住执行层。
- 首轮设对「焦点抢戏」行改写：删除「focus 是文字必须页内最大字号」的绝对化表述，改为
  「Focus 应获得明确的视觉优先级，字号只是手段之一（图像/留白/孤立小数字/结构关系都可以
  是焦点）；仅当焦点落在文字元素上，代码才用最大字号 + ≥1.25× 领先度量」。代码行为零变更
  （`focus_scale` 本来就只对文字焦点触发、hint 级只留痕不阻断）。

**改写（去模板化）**

- Grouping「分组四语言，由强到弱」→「**默认分组成本**」：场>线>型>盒 是成本顺序不是永远
  优先级——复杂数据页、产品界面结构、财务表格里盒子可能就是正确的语义容器，防止「少卡片」
  重新变成「反卡片规则」。
- Charts：明记「**类型路由的判断在 Intelligence / Craft（Chart = Visual Argument），本段只给
  候选表达 + 工程安全边界**；System 保证被选中的类型正确、可读、可编辑地执行」——
  趋势=折线/比较=条形 不是路由表。

**新增（边界声明，各一句）**

- `constraints` 四层分工：Intelligence 决定值为什么存在 / Craft 判断越界是否有意设计 /
  System 只提供数字 / Guard 只问有没有越界。
- Theme 是运行时数据结构，不是设计知识库：永不加 layout / cards / hero / section / premium /
  visual_style 一类知识键。
- Anchor = **连续性基础设施，不是版式基础设施**（保持 deck 连续，不限制每页构图）。
- DNA 记录**决策经验，不是设计结果**：不记「64px 标题 + 米色背景 + 左对齐」，记「当内容
  只有一个战略结论且需要建立权威时，扩大 statement 与留白的比例比增加装饰更有效」。

字节账（诚实）：18,798 → 19,952（+6%）——删越权段 ~0.8KB，加六条边界声明 ~1.9KB。
Spec 字段速查、chart_kind 全表、首轮设对数字表、约束表逐字保留（那是 System 的本职）。
代码零改动。回归：selftest **152/152**；bench① release PASS 214ms。

## 5.4.4 · design-intelligence.md 减法收敛：更少的规则，更强的判断

按「判断正在重新变成规则」的风险审查收敛 Intelligence Core（文档为主，代码仅改一句输出文案）：

- **反模板原则置顶（本卷第一条）**：不要从页面类型推导页面长相——Statement 不等于必须大字、
  Data 不等于必须图表、Case 不等于必须摄影、Framework 不等于必须卡片；家族 / 构图 / 母题 /
  色彩 / 媒体都只是候选表达。先判断内容为什么值得被这样看见，再决定视觉形式。
- **十步判断链**（01 Strategy → 10 Guard；01–08 是判断，09–10 是移交 vao/guard）与
  **七模块职责边界表**（Brief / Intelligence / Craft / System / Rules / VAO / DNA，
  同一事实只判断一次）置顶成文。
- **Content → Visual 改名 Visual Hypothesis**：映射表保留但降格为「第一候选，不是默认答案」——
  流程永远是信号 → 感知目标 → 候选动作 → 否决不成立的 → 选最少且最有效的表达。
- **删除「相邻两页至少换一项算子」**：改为「变化要由内容、叙事或情绪的转折产生——重复有理由
  就保留，变化有理由就变，没理由不动」。连续页布局雷同仍由 `LAYOUT_MONOTONE_RISK`
  条件性点名（诊断保留）；`route.py` deck_decision.composition.rule 输出文案同步（唯一代码变更）。
- **九阶段降为 Narrative Reference**：明记不是每个 deck 必须完整走过、阶段可合并/跳过/重复/
  重排——叙事服务内容，而不是内容填入叙事。情绪弧线与页型节奏三手法合并去重
  （opening 建世界 / 章节重置 / 结尾回收原本各写了三遍）。
- **母题改为可选**：有则母题承担连续性（封面注册、章节放大、数据页退刻度、结尾收束），
  没有则由锚点、排版声音与图表性格承担；不是每页必须出现的装饰。
- **留白三型数字（≥60 / 40–60 / 25–45）删除**：只留「留白是结构不是残渣」+ `empty_space_role`
  四职责判断 + 口径警告（结构留白 = 元素框并集外占比）；数字执法归 `whitespace_min`
  与 design-system §约束。
- **字号阶梯整节迁出** → `design-system.md` §字号阶梯（全库唯一真源新址）：
  Intelligence 只回答「这个信息是不是页面的视觉主语」，System 与生产合同回答「落到哪个安全值」。
  四处指针同步（design-system / design-craft §五 / route.py 路由表注释 / primitives.py text_units）。
- **Page Intent 升级为核心闭环**：Insight → Focus → Reading Order → Visual Strategy →
  Composition → Rationale，外加反向问题（删除这个视觉选择，信息传达会不会变差？不会 → 删除）。
- 三个 YAML 契约块（strategy / direction / page_intent 枚举）**一字未动**——intent_compiler
  消费的字段合同。
- 字节账（诚实）：9,882 → 11,183（+13%）。删的是规则化内容 ~1.5KB（阶梯表、留白数字、
  机械算子句、母题强制、三段重复叙事散文），加的是三个导航结构 ~1.7KB（反模板卷首 /
  十步链 / 职责边界表），判断散文净压缩 ~0.9KB。硬规则与无条件义务清零，新增的全是判断脚手架。

回归：selftest **152/152**；bench① release PASS；bench② 全链（plan → assets → asset-qc →
check release）PASS 870ms。bench② 资产指纹随 plan 重生成自然变化（`asset-f33af639f039`），
属既有行为，非本版引入。

## 5.4.3 · design-craft.md 减法重构：Craft 不记数字（纯文档，行为零变更）

判断层文档按「**Craft = 判断问题 + 权衡方式 + 少量案例**」重构，三层权责成文：
**Craft 负责为什么这样判断；Intelligence/System 负责把判断转成设计决策；
Guard/Contract 负责哪些客观错误必须阻断**——Craft 不记数字，System 不替导演审美，
Guard 不判美不美。

- **Director Kernel 置顶**：先决定观众应该看到什么，再决定页面应该长什么样；
  先删除不必要的东西，再决定需要什么视觉表达。任何视觉选择都必须能解释它为什么服务当前内容。
- **减法链升格为核心操作系统**（§二第 10 条 → §一）：任何「高级感不足」默认先怀疑
  判断不足，而不是视觉元素不足；Anti-Design 症状全清单随迁（SKILL/design-system 指针同步）。
- **九维审查 → 五个导演级判断**（Focus / Composition / Reading / Expression / Continuity）：
  12 条判断原则的散文按归属并进五判断（主语与降级 → Focus；留白承重 → Composition；
  路径/少而准/数据诚信 → Reading；色彩人格/材质 → Expression；deck 是一个作品/统一与差异 →
  Continuity），修正纪律与审美标尺作为贯穿两条；旧第九维「交付状态」明确归 QA 代码判。
  更接近 Art Director 判断，而不是 QA checklist。
- **参考刻度数字全部退出**：5% / 1.25× / >4 / 40px / 10% / 22–38 字等阈值从本卷删除
  （逐项核实权威住所：门槛表 → production-contract，constraints/首轮设对 → design-system，
  行长/焦点常量 → primitives，节奏/装饰默认 → guard 常量），中列只留「代码测什么信号」，
  与五判断重复的行合并为信号索引。防的是模型把参考刻度重新背成隐形设计规则。
- **案例库一字未动**（案例 0/5/6 + 短案例 1–4）：症状 → 判断 → 修法 → 教训的「判断迁移」
  结构比规则更有价值，继续增加的是迁移而不是数量。
- 摄影 §四、Typography §五、§七「什么时候可以不照办」保留（字距光学值在代码层无住所，
  本卷是唯一权威，且非执法数字）。
- 指针同步：SKILL §04/§10、design-system:79、README 目录行、primitives.py:902 注释
  （旧「§判断基线/§二第 10–12 条」→ 新节号）。

回归：152/152 PASS（禁词扫描、死引用、阻断码全列三项文档自检均过）；代码零行为变更
（primitives 仅改注释）。字节数持平（20.1KB→19.9KB）是刻意结果：减的是结构冗余
（九维表与原则的重复、刻度数字），判断散文与案例是资产不是脂肪，全部保留。

## 5.4.2 · 契约语义收紧：声明与预算的权力边界

四处语义修正，其中一处是真实的代码级优先级倒置：

### 资产预算不得吃掉显式声明（代码修正）

`plan.assets.generate` 曾经对全部 required 页无差别 `[:cap]` 截断（fast 2 / advanced 4）：
作者逐页声明的 `asset: required` / `asset_subject` 落在预算外会被静默 budget_skip——
执行策略压过了契约声明，违反 Declaration Priority。现在：

- 路由页标记 `asset.author_declared`；`generate = 声明项(全保留) + Skill 判断项[:cap]`；
- `budget.max_asset_calls = len(generate)`（预算数字降级为执行器内部策略，
  只约束判断项）；`generate_extra` 只列被截断的判断项。
- 自检 +1：fast 档 2 声明 + 2 判断 → 4 项全保留，声明项永不 budget_skip。

### brief.yml 契约最终收敛（文档）

- `asset: required|reuse|none` 三值语义逐条写明；`asset_subject 非空等价于
  asset=required（除非另行显式写 asset）` 成为成文规则；reuse 与 asset_source 的
  分工说清（reuse=不生成新图；真实既有文件走 asset_source 登记 + QC）。
- `asset_function` 注释删除 `direct`——它是代码内部别名（asset_prompt 短语表可达），
  判断层从不产出、文档从未承诺，不进契约枚举。
- quality_level 注释删除「上限 2 / 上限 4」数字：Brief 表达"我知道什么"，
  预算数字是执行器策略；写进契约会诱导「advanced = 凑满 N 张图」的错误认知。
- 留痕事实来源写明：`plan.warnings` 是事实来源，骨架 ⚠ 注释是作业面拷贝，
  `brief.unresolved` 只记 deck 级未声明字段——三处不重叠、不重复处理。

### Priority determines authority, not creativity

写进 SKILL §01 与 brief 纪律：用户声明的是不可改变的意图（主体/介质/比例），
Skill 判断的是怎么把它做得高级（摆位、留白、光、层级、裁切、视觉世界一致性）。

回归：selftest **151 → 152 项**全过；无图/含图端到端基准复验通过
（release 首轮 PASS；资产指纹未变，旧图无需迁移）。

## 5.4.1 · SKILL.md 重构为决策系统（纯文档，行为零变更）

主 Skill 已经开始承担 production contract 的职责（阈值、凭证细节、命令注释越积越多）。
本次按「**主 Skill 负责大脑，reference 负责长期记忆，vao.py 负责执行**」重构：

- **结构**：19 节决策系统（WHY → HOW TO THINK → HOW TO EXECUTE → WHEN TO STOP），
  18.1KB（5.2 原版）→ 12.1KB；相对 5.3 瘦身版再 -8%。
- **去重**：`Judgment > Rules` / 最高原则 / 最高设计目标 / Director 终检的语义重叠
  收敛为各司一职（01 优先级、19 停止规则、Core Philosophy 收束句）。
- **数字出主 Skill**：焦点 1.25×、Accent ≤5%、字体家族 ≤2、轮次预算 ≤6 等具体阈值
  移交给权威住所（production-contract §门槛表 / design-system §constraints 表与
  首轮设对表；轮次预算本就是 CLI 显示值）。主 Skill 只留工程事实
  （16:9 / 1280×720 / 可编辑 / 不篡改 / 不溢出 / 可追溯）。
- **三产物职责表**（新增 §11）：骨架 = 作业单（唯一反复看的文件）、
  manifest = 出图契约 + QC 凭证、plan.json = 链路凭证（正常流程不读）——
  堵死「AI 反复读 plan.json / manifest 找信息」的轮次浪费。
- **合并而非丢弃 5.4 契约资产**：Declaration Priority 阶梯、标题不代替内容
  （unresolved_content）、逐页 asset/asset_subject 写了就生效、凭证纪律，
  全部保留并归入对应节。
- Native-First 的「1~2 张 Hero」从硬规则软化为判断参考（内容要求即可增减）。

回归：151/151 PASS；阻断码 10/10 列全（自检强制）；文档死引用与
「代码不认的词」两项自检均过；代码零改动。

## 5.4.0 · 需求契约：声明优先级、unresolved 与 advanced 语义

一句话哲学：**人负责声明意图，Skill 负责做判断；明确的永不覆盖，未知的不擅自猜测。**
本次不增命令、不增模块，只把契约语义修正到位。

### Declaration Priority（写进 SKILL.md 核心逻辑）

```
逐页显式声明 > deck 级显式声明 > 品牌约束 > 设计方向默认 > Skill 判断 > 保守兜底
```

永不倒置。direction 是起点不是模板；Skill 判断只做选择，不虚构需求。

### 逐页 asset 声明原样生效（修复一处静默违约）

此前逐页 `asset: required` 无人读取、`asset_subject` 落在 decision=none 的页上会被
静默跳过——「写了的字段原样生效」在出图这件事上不成立。现在：

- `asset: required|reuse|none` 直接改写该页决策，压过家族默认与质量等级；
- 在默认不出图的页上写 `asset_subject` 视为声明出图（decision → required）。

### advanced ≠ 更多图片

`plan_page` 曾经把所有 `optional` 家族页（case / statement / closing / architecture）
在 advanced 档升格为必须出图：最适合纯排版的页被强塞一张图 → 为放图改版式 →
多出一次生成 + 一轮 QC，审美与速度双输，且与 Native-First 纪律（15 页至多 1~2 张
Hero 图）正面冲突。现在 optional 一律默认不出图，出图由逐页声明决定；
advanced 提升的是判断与证据预算（资产调用上限 2→4），不是视觉数量。
`design-craft.md` §七 早就写着「fast / advanced 是预算，不是审美等级」——代码终于同意。

### 标题不代替内容（unresolved 补上逐页一环）

deck 级未声明字段一直会进 `brief.unresolved`（intent_compiler）；但证据型页
（data / comparison / case / business / timeline）缺 `content` 时无人留痕，
生成侧可能由标题「收入增长」脑补出折线图与同比数字。现在：

- `plan.pages[].content_missing` 标记 + `plan.warnings` 增 `rule=unresolved_content`
  （scope=页 id，非阻断）；
- 骨架在对应页注释 `⚠ 未决（unresolved）: content 缺失——标题不是证据…`，
  把待判断项送到落笔处（v5.3 起 AI 正常流程不读 plan.json，警告必须长在骨架里）。

### templates/brief.yml 收敛为分节契约

01 核心契约（audience/decision/tension）· 02 页面叙事 · 03 逐页视觉声明（集中文档化，
含新增 `asset` 旋钮与「lighting 写了即唯一光源」「hero/proof 静物不注动势」语义）·
04 deck 级视觉世界 · 05 品牌 · 06 视觉方向 · 07 质量等级。头部纪律写明
「写了生效 / 没写不猜 / 不虚构需求 / 声明优先级」；执行命令同步 5.3 的 4 轮流程；
删除「advanced 会把可选页升为必须出图」的过时说明。

### 回归网

- selftest **148 → 151 项**：+priority（advanced 不升格 + 逐页声明生效）、
  +unresolved（warnings 留痕）、+skeleton（⚠ 注释到落笔处）。
- 既有断言零改动通过：M-02 页覆盖、H 系列凭证链、audit 用例均不依赖升格语义。

## 5.3.0 · 轮次与提示词质量（不增命令、不增模块、不增规则）

实测基准表明本地计算不是瓶颈（全链路 <2s）：贵的是 AI 轮次、上下文体积与出图稳定性。
本版只修这三样，判断层文档（design-craft / design-intelligence）一字未改。

### 出图提示词去矛盾（5 处 → 0）

1. **光照单一来源**：摄影卡由摄影写实光语独家给光（卡片预设光、方向光句、能量光句全部让位）；
   作者逐页声明 `lighting` 时以作者为唯一光源（摄影层的光句也让位，介质句保留）。
   此前三层光照同帧注入，模型只能对矛盾指令做平均——不可预测的光比没有光更贵。
2. **静物动势抑制**：hero / proof / direct 主体的 motion 层取静态安全句
   （motion blur、light trails 只属于氛围类资产）。自由文本仍原样保留。
3. **构图语法翻译**：内部枚举键（`evidence_field` / `soft_asymmetry` …）在提示词层翻译成
   可读英文构图语言；裸键名对图像模型是纯噪声，还污染资产指纹。
4. **色名可读化**：`#hex` → `muted green (#5E7562)`（图像模型对 hex 基本不响应）；
   中性判定用 chroma 而非 HLS 饱和度（近白 `#F5F4EF` 不再被误判成 pale yellow）；
   中文 subject 收到非阻断的「改英文」提醒（自动中译英被否决：翻译错主体比混排更贵）。
5. **负向提示分层**：核心恒注入组 + 主体可能出现人物时的人物场景组 + 非水墨卡的科技风格组。
   全量负向无差别注入会稀释对这一张图真正要紧的反向词；ASCII 词按词边界匹配
   （`handmade` 不再误判成 `hand`）。

### 轮次合并与骨架自足化

- `run --plan-out --skeleton --assets-out` 一次调用完成规划 + 资产契约：
  标准流程**有图 4 轮（此前 6~8）、无图 2 轮**。
- 骨架升级为**完整作业单**：头注释带方向族材质/光/图表手法、统一契约、待判断槽位、
  DNA 命中与避讳、容量公式（行宽 ≈ 盒宽/字号，CJK 1.0 / 拉丁 ~0.55 / 细空格 0.2，
  标题 +20% 余量）；每页注释带叙事动作与构图意图；尾命令直达 `--mode release`。
  正常流程不再需要读 plan.json（每项目省 ~41KB ≈ 1.2 万 token 上下文）。
- 修复骨架清单自相矛盾：删除「证据编号写进 caption 开头」（与证据编号弃用指引冲突，
  出处信息只进 source_zone）。

### plan 瘦身（零消费字段清退）

- `ROUTES` / `plan_page` 删除 `type_scale`：字阶唯一真源是 design-intelligence.md 的
  驻点阶梯（64/44/32/22/17/12.5），路由的第二套口径无消费者，fast 档缩放值还落在驻点之外。
- `plan.pages` 删除逐页 `intent_interpretation` 镜像与 `media_confidence` / `media_reason` /
  `quality_budget` 循环（grep 确认全库零消费；作者覆盖已直接生效在页面字段上，
  冲突留痕 deck 级一份足够）。判断层函数本身保留，bundle 级 intel 页仍在消费。

### 文档与微优化

- `SKILL.md` 18.1KB → 13.1KB（-28%）：卡片三准入全段、Anti-Design 全清单、Fig.01 论证段
  压成指针（全文权威住所：design-craft.md §二 / design-system.md §Grouping）；
  README 版本叙事归档进本文件；asset-workflow §2 命令同步 4 轮流程；
  brief.yml 模板的 `asset_subject` 示例改英文并写明理由。
- `vao.py` asset-qc 循环体内的 `import hashlib` 提到函数头；
  删除已被 `PROMPT_QC_COMPACT` 取代的 `UNIVERSAL_QC` 死词表（18 条）。

### 回归网

- selftest **139 → 148 项**：+7 提示词纪律（光照单源 ×2 / 静物动势 / 语法翻译 /
  负向分层 / 色名 / 中文 subject 提醒）+2 骨架自足与 plan 零消费字段清退。
- 凭证链语义不变（指纹 / fail-closed / reuse 防伪 / QC v3）。提示词变更 → 指纹变更 →
  旧清单失效属契约内行为；旧图登记 `reuse` 迁移，旧 QC 不自动升级。

## 5.2.0 · 用实战返工换速度（判断层一字未改）

一次 11 页真实交付（宋氏美学 × 现代东方年度总结）暴露出 15 个问题，其中 4 个是**静默失效**：
不报错、结果错、且每次都逼人回到源码里找口径。本次只修这些根因。

**没有动的**：`SKILL.md` / `design-craft.md` / `design-intelligence.md` 的**一个字都没改**
——判断层是资产，不是负债。不增命令、不增模块、不增规则、不增检查器。

省下来的返工（按实测）：

| 根因 | 本次代价 | 修法 |
|---|---|---|
| 介质判定看错了层 | 3 张废图 + 多轮 QC 分析 | 介质回归**资产级声明** |
| 方向族名送不到 | 全程手写材质/纹理覆盖 | 13 个色彩族名可作 `design_direction` |
| deck 级世界语言污染单张介质 | 1 次全流程重跑 | `visual_world` 与介质判定解耦 |
| 「主体贴边」判了氛围图 | 多出 3 张图、意象被迫改 | 按 `asset_function` 分级 |
| 预览画不出多序列 | 1 次「以为产物是空图」的误判 | ghost 认 `series` + `categories` |
| 隐式旋钮没进契约 | ~5 次读源码 | brief 模板补齐 |
| 指纹报错不说位置 / 白边废图 | 各 1 轮 | 报错给权威位置；边框进通用反向 |

### 介质判定回归「资产级」（最贵的一条）

`ink_gate_active` 原本认一个方向族名白名单（`song_elegance`）。它两头都错：

- 方向名送不进来时（见下条），它**永不命中**——库里唯一的水墨闸门是一段死代码；
- 方向名送进来之后，`card["family"]` 带着族名，于是**全 deck 的摄影页一起被判定为水墨**，
  提示词里出现水墨工艺纪律与 `photography medium` 并存的自相矛盾。

现在判据只有资产的介质声明：`medium`（最明确）、subject、逐页显式写下的材质。
方向默认值不算——它说的是「整副 deck 用什么质感说话」（一份宋韵里每张照片也可能拍在
纸台上），不替某一张图宣告它是画。`INK_FAMILIES` 常量随之删除。

### 方向族名可送达

`design_direction` 只认 4 个结构预设，`design_intelligence_rules.COLOR_DIRECTIONS` 的
13 个族名一律静默回落成 `quiet_minimal`。现在族名被接受，并带来它自己的
材质 / 动势 / 纹理语言与种子色板（结构骨架仍取预设，品牌色仍优先，`texture` 以键名
传下去由 `asset_prompt` 展开）。

配套：`vao.py` 的 `card["family"]` 从**页面家族名**（`cover`/`data_story`）改为**方向族名**
——`FAMILY_TEXTURE` / `FAMILY_MOTION` 的键一直是族名，传页面家族名只会静默落进
`("luxury",)` 兜底，于是每张宋韵资产都吃「fine leather grain」。

### 其余修复

- **deck 级世界语言与单张介质解耦**：`visual_world` 从 `style` 段移到 `world` 段——
  照旧进提示词当氛围语言，但不再参与闸门扫描；方向枚举也不再泄漏进提示词。
- **QC 按职能分级**：`asset_function ∈ {emotion, context, frame, separate}` 时，
  「主体贴边被裁」降为建议。该判据是为**具象主体**设的，而氛围/语境资产的画面边界
  本就该由材质与光填满。实测三层手工纸特写与静物的显著性占比同在 0.00–0.07 量级
  ——像素层面区分不了「材质延伸」与「被裁断的主体」，判据只能取自声明的职能。
- **ghost 支持多序列图表**：`_rows` 同时认 `data` 与 `categories`+`series`。
  实测 `comparison_bar` + 双序列的产物里 `<c:ser>=2`、数据点齐全，而预览只画一个叉
  ——预览「冤枉对的」与「背书错的」同样是证据失效。横向条同时补上类目轴标签。
- **brief 契约补齐**：补 `material` / `lighting` / `texture` / `asset_color` /
  `safe_area` / `negative` / `asset_type`（它们一直是「显式传入永远赢」的旋钮，却没写进模板）；
  接上 `composition_grammar` / `background_scene` / `avoid`；
  **删除 6 个零消费字段**（`tone_hint` / `type_voice` / `color_behavior` / `media_policy` /
  `energy_curve` / `evidence_posture`）——留着只会让人写了以为生效。
- **报错可执行**：`plan_sha256` 不匹配时直接报出权威位置（`asset_manifest.json` →
  `workflow.plan_sha256`），不再只说「不匹配」；缺 `asset_subject` 时 QC 提示
  「主体描述取自页面标题（标题是观点，不是画面）」。
- **通用反向补边框类**：`white border` / `black bars` / `letterbox` / `picture frame` /
  `poster mockup`。模型把「四周留白」误读成「加一圈画框」是高失效模式，画幅会整段作废。

### 迁移

无需迁移：没有命令、字段或文件的新增与删除（brief 里被删的 6 个字段本来就不生效，
写与不写等价）。`plan` / `assets` 的产物 schema 未变。

回归：**139/139 PASS**。

## 5.1.2 · 设计判断层补位（Anti-Design / 减法链 / 审美标尺）

本次只动判断与文档，不新增命令、依赖、检查器或流程。SKILL.md 净字节 **−16 B**：
加进三组判断的同时，把重复的工程凭证细节让位给 `references/production-contract.md`
——加的是判断，减的是篇幅。

### 判断层

- **Anti-Design（主动避免）**：SKILL.md 与 `design-craft.md` 首次给出显式反模式清单——
  模板感 / UI Dashboard 感 / 卡片墙 / 组件堆叠 / 过度圆角 / 过多阴影 / 过多渐变 /
  无意义图标与线条 / 过度 3D / 过度装饰 / 过度留白 / 为高级而高级 / 为变化而变化 /
  AI 机械布局 / 每页同一结构。并点明最该避免的是**「所有东西都设计得很明显」**：
  世界级设计允许视觉保持安静。
- **减法链统一**：`删除 > 重组 > 排版 > 强化 > 装饰` 成为跨内容与视觉的唯一修法顺序，
  取代原先分成两截的表述（SKILL.md 管内容层、`design-system.md` 管装饰层）。
- **审美标尺**：Apple Keynote / Pentagram / Swiss Typography / Financial Times / Bloomberg /
  Kinfolk / Monocle / Wallpaper* / IDEO 明确为**校准判断力的参照系**——学它为什么这样决定，
  不学它长什么样；参考案例不得变成下一份 PPT 的版式、色板或组件。
- **最高原则块**补入 `Content determines form / Meaning determines hierarchy /
  Context determines color / Information determines layout / Aesthetic determines selection /
  Narrative determines rhythm`。

### 修复（回归网此前在 Windows 上从未真正跑起来）

两个缺陷都是静默失效型，前者掩盖了后者：

- **selftest 在非 UTF-8 码页的 Windows 上直接崩溃**：`run_vao` 使用完全隔离的 env，
  且 `text=True` 靠 locale 猜编码——子进程按 GBK 输出中文时父进程按 UTF-8 解码，
  reader 线程抛 `UnicodeDecodeError` → `proc.stdout` 变 `None` → 报错落在无关行号
  （`TypeError: 'NoneType' object is not subscriptable`），**基线根本无法建立**。
  现固定两端 UTF-8 并加 `errors="replace"`，同时补回 Windows 进程启动硬依赖
  （`SYSTEMROOT` / `COMSPEC` / `TEMP` / `TMP` / `LOCALAPPDATA` / `APPDATA`）。
- **M-09 用例在沙箱化 Windows 上失效**：宿主会把 `symlink_to()` **静默降级**为普通文件
  （不抛 `OSError`，`is_symlink()` 却是 `False`），用例因此落进「链接创建成功」分支，
  又因 `resolve()` 本就不越界而失败。现检测到降级即强制走 post-resolution 边界分支。

回归：**139/139 PASS**。Linux / macOS 行为不变，仅是健壮性补强。

## 5.1.1 · 修复深度审计发现（本地修改版）

修复 3 项 P1、11 项 P2；不增加生产命令、运行依赖、服务、签名系统或数据库。

- **H-01**：删除共享的图片适配磁盘缓存；保留按输入/产物指纹校验的整份 PPT 编译缓存。
- **H-02**：QC/发布阶段只读 brief 原始字节与计划内需求快照，绝不隐式执行 brief。明确指定的可信 `.py` 仍可用于规划与编排；未知后缀拒绝。
- **H-03**：核验时读取图片为不可变 bytes；编译和方向预览共用该快照。源文件随后变化不会替换本轮交付内容。
- **M-01**：单页预览与总览均保存/校验 SHA-256；缺失或被替换则重建。
- **M-02**：绑定计划的稿件核对完整页 ID 与顺序，无图稿件也不例外。
- **M-03**：数值图表来源口径必须是非空白字符串。
- **M-04**：修正未指定文字明暗时的恒真对比度条件。
- **M-05**：QC 检查短边、计划比例；编排检查裁切后的有效像素是否足够支撑落位。
- **M-06 / M-11**：形状内文字纳入容量检查；禁止换行文字增加水平宽度检查。
- **M-07**：auto_fit 后的有效 spec 成为编译、预览、发布的共同输入；失败状态和修复建议统一归并。
- **M-08**：每次 check 建立 run_id，先使旧发布资格失效；异常也原子写入本轮失败报告。
- **M-09**：生成资产最终路径必须仍在 assets_dir 内；明确登记的 existing 外部素材仍允许。
- **M-10**：透明图片按计划背景合成后 QC；全透明内容拒绝，可见透明素材不一律拒绝。

新增 29 个回归检查，覆盖上述问题和正常缓存、透明 Logo、有意裁切、原生稿件等合法用法。

### 迁移说明

旧 QC 报告不能冒充新检查结果。请重新 plan → assets → asset-qc；已有素材登记为 reuse，
不需要为了迁移强制重生成。QC 报告版本升级为 `vao-asset-qc-v3`，资产清单保留 v2，
新增原始 brief 文件指纹。骨架保留 plan_path 与 plan_sha256。

图像质量底线：短边至少32px；与计划比例相对偏差不超过5%，有意裁切可在 brief 声明
`asset_allow_crop: true`；实际落位不允许明显超过有效像素尺寸（1%浮点容差）。
这些是最低有效性检查，不是艺术质量评分。

本地字节快照和哈希仍不是数字签名，也不是对不可信 Python 执行的沙箱。

## 5.1.0 · Asset-first workflow（本地修改版）

本次针对“先自由生成图片、后补PPT规划，却误称完整执行技能包”的流程缺口修改。
这是基于仓库的本地改进版，未向上游仓库推送，也不代表上游已发布同名版本。

### 流程

- 标准顺序明确为 brief → plan → assets → 按清单出图 → asset-qc → PPT 编排 → release。
- `assets --plan` 改为必需；核对当前 brief 与已保存 plan。
- 图片清单内部调用 asset_prompt 的提示词构建函数；外部图片生成仍由执行者调用。
- 纯原生内容明确记录跳过；已有图像通过来源登记与 QC，无需强制重生成。

### 运行时

- 新增内部 `asset_workflow.py`，不增加第二个生产CLI。
- 计划与骨架、资产清单、QC报告、实际图像以内容 SHA-256 绑定。
- 图片须声明 asset_id 与使用页；无清单/无QC不能直接通过 src 进入编译。
- 统一 QC 与绑定的图片目录及 JPEG/PNG 解析，修复复用标记覆盖主资产记录的问题。
- 修正 QC 重试仍返回成功的漏洞；retry/missing/block 均返回非零。
- 发布结果增加资产流程凭证；修复 BLOCKED 与 release_eligible=true 可能并存的状态。
- 图片比例、文本明暗与风格进入提示词缓存指纹，避免不同需求错误复用。
- 明确重跑资产准备时不能将已有字节冒充本轮新生成图片。

### 文档与验证

- 更新 SKILL、README、生产契约、设计系统、brief模板。
- 新增资产工作流说明、迁移说明及证据边界。
- 增加资产流程集成/回归测试；测试使用本地图片夹具，不调用在线图片服务。
- 修正既有 CI 中的失效规划命令与不存在的模板引用，改走真实 vao.py 入口。

### 兼容性注意

- 无图片稿件的检查命令不变。
- 有图片的旧稿不能再仅凭图片路径发布：须建立计划、清单与有效 QC；已有图登记为 reuse。
- 旧版资产清单/QC 不自动升级，不补造原先未执行的步骤。
- 本地哈希链不是外部图片服务调用证明，也不构成图像授权审核。
