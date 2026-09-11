# Changelog（判定演进史与路线图 · 唯一档案）

## 演进元原则（v4.9 物质化：本档案各版本引用的「第 N 原则」即此表）

1. Design Judgment 优先于规则——判断系统化，不堆条款
2. 反过度设计——能不加就不加，能删则删
3. 减 token 提决策质量——上下文是一等优化指标
4. 禁固定配色/布局/风格模板——蒸馏经验，不固化模板
5. 世界级版式标准——克制 + 精准 + 质感
6. 图片先判功能再生成——图是解释，不是装饰
7. 审美判断与创意决策禁硬编码
8. 性能优先——主链单次、可缓存、并行有界
9. 最终标准：更少规则更强判断，更少代码更高审美，更少复杂度更高质量


## v4.19 发丝线与出图回路批（2026-09-11）：用户指控坐实 + 流程硬卡点

**修复**

- **F10 执行层·发丝线网格吸附（用户补丁指控，实证坐实）**：生产链第 0 级 Normalizer 的 `_snap_size` 只增不减（防容器溢出设计），副作用是 1px 细线被向上抬成 8px 色块——发丝线的视觉重量被基线网格「放大成方块」。修复：任一维 ≤2px 的发丝线 → **仅位置吸附网格，尺寸绝不吸附**；>2px 照吸不误；与 §02.1 网格顾问已久存的发丝线四维豁免同一口径（设计语言一致性：豁免依据是维度不是角色名）。实证：1184×1 分隔线 @97,100 → 1184×1 @96,104；2×560 标尺线 → 2×560 @104,80；普通色块 301×87 → 304×88 照吸；3px 粗线不豁免照旧上色块路。
- **F11 流程层·出图回路硬卡点（生图前必须走 asset_prompt）**：回溯 2026 实战链——实战 build 模块零引用 asset_prompt，四张图均为手写裸 prompt（dawn-summit 翻车案源）。v4.17 的水墨纪律闸门造好了却没有强制入口。修复为工作流硬卡点（文档级，不建运行时强制器——技能包的正确粒度）：SKILL.md 出图行升级为「每张图先走 asset_prompt 组装、CHECK OK 再出图，禁手写裸 prompt」。

自检 55/55 全 PASS（新增 hairline_grid 检查）；3 项渲染链 skipped（LibreOffice 缺席环境守卫）；hard 常量零漂移。

## v4.18 几何退化与决策桥批（2026-09-11）：不可见内容前置拦截 + 瘫尸清点

**案源**：第九轮八层深扫换三个没量过的缝——验证层几何链、决策层消费对账、代码层函数级清点。

**修复**

- **F8 验证层·几何退化前置拦截（guard）**：geometry 是元素存在的前提，而 x/y/width/height 缺项静默按 0、≤0、非数值（"300px"）三类形态，渲染后元素不可见却只留 -1.5 编译 warn——不可见的内容比重叠更隐蔽。修复：元素扫描块在坐标推导处前置 element_schema 级拦截（缺项/非数值非有限/≤0 三形态 → error），与 F4 字段形态同族「脏字段形态静默成本」。顺手修复：非数值 geometry 捅穿 full_bleed 计算的裸 float()（4400 年代的老裸奔，现在 try 降级，F8 先行报告）。
- **F9 决策层·family_hint 决策桥（production-contract 媒体行）**：F5 的 direction_seed.family_hint 全包 grep 零消费者——命名通道是写给自己看的。修复为契约桥（技能包的正确修法是文档契约而非运行时耦合）：媒体行补「资产卡 family 填 direction_seed.family_hint，水墨语言卡自动过纪律闸门」，v4.16 的订阅层从此接上 v4.17 的执行层。
- **V3 代码层·瘫尸清点（190 个公开函数）**：6 候选复核——add_text/add_image 活在 DISPATCH 映射表、run_job 活在 executor.map、__init__ 构造（reference 式调用不被 paren 扫描命中，四例侦察虚惊）；真瘫尸两具 9 行——primitives.text_role 与 ColorContext.paint_or，零调用零中文档提及，剔除。

**侦察方法论教训**：上一轮用 w/h 别名做几何探针险些酿出假修复——guard 与 compiler 的规范键是 x/y/width/height（production-contract 明文），探针必须用契约键。

自检 54/54 全 PASS（新增 geometry_degenerate 检查）；3 项渲染链 skipped（LibreOffice 缺席环境守卫）；hard 常量零漂移；速度链实测无变化（F8 为 µs 级字符串/数值解析）。

## v4.17 词边界与水墨纪律批（2026-09-11）：理解层堵漏 + 审美执行保底

**案源**：第八轮八层深扫侦察中坐实的两条——都出在「选择对、执行歪」的缝。

**修复**

- **F7 理解层·ASCII 词边界（intent_compiler）**：occasion/style 查表原是纯子串匹配，纯 ASCII 短词会嵌在无关英文单词里误命中——"frozen/dozen/citizen" 内含 "zen" → 一份冻资复盘被覆写成宣纸水墨世界；"history" 内含 "story"、"onboard" 内含 "board" 同病。修复：纯 ASCII 词走词边界匹配（容忍 s/es 复数尾巴：zen garden/reviews/boards 照常命中），CJK 词无分词边界保持子串。实测：冻资/公民参与/简史/入职四份英文简报全部回到正确世界，"zen garden" 与"东方水墨"照常命中。
- **F6 审美层·水墨纪律闸门（asset_prompt）**：用户新增约束「背景图插图拒绝低质量的水墨」。东方/水墨题材上图像模型默认分布是数字喷枪渐变+图库风景摄影（案源：dawn-summit 首版翻车）。修复：资产卡已选择水墨语言时（subject/material/style 等含水墨词，或 family ∈ {song_elegance, zen_minimal}），build_asset_prompt 自动注入①工艺纪律正向短语（单笔意笔触/干笔渐变/过半纸地留白/三到四墨阶/笔触成形式）②廉价症状反向清单（摄影风景/泥污灰墨/随机泼溅/过饱和红日/剪贴画竹鹤/中心对称/重暗角/数字喷枪渐变）。自动注入的 motion/texture 弱描述不作点火源，防止"只要米纸底味就被拉去画水墨画"的过触发。审美决策（用不用水墨）仍归调用方；闸门只保底"选择了却画得廉价"这一失效模式。
- **碎屑清扫（代码层）**：5 个文件 8 个死 import 剔除（qa: Any/DEFAULT_WIDTH/DEFAULT_HEIGHT；primitives: Path；layout_search: Any；ghost: _tuple/math；design_intelligence: STATEMENT_SIZE），跨文件重导引用零（grep 证尽后动手）。
- **判断层归档（design-craft.md 案例5）**：水墨气质的两种死法——材质语言不写死的默认坠落 + 廉价水墨可识别症状谱；写进代码的是失效模式不是口味。

**速度体检（实测，7 页 spec）**：guard 0.93ms / qa 纯验证 2.1ms / compile_deck 15.5ms（其中 80% 是 python-pptx 库自身的 save，属外部边界）——验证链全毫秒级，「秒级可答」硬约束无欠债；真正慢的两翼（图像生成、LibreOffice 渲染）在包外，已有 render_cache/workers 治理，本轮不虚构优化。

自检 53/53 全 PASS（新增 intent_boundaries / ink_gate 两检查）；3 项渲染链 skipped（LibreOffice 缺席环境守卫）；hard=5 零漂移。

## v4.16 实战反馈批（2026-09-11）：首次创作链压测后的两修

**案源**：上一轮真实创作链（2026 年终总结 PPT，水墨东方主题）暴露的 9 条过程问题中，根源在包侧的两条——其余 7 条为我的使用失误，已衰减为使用习惯而非修包。

**修复**

- **F4 元素级字段形态前置拦截（验证层）**：实战发现 `color: {"hex": "..."}` / `fill: True` / `slide.background.color` 传对象这类「看似合理的对象形态」会让编译期 `colors.get(dict)` → `TypeError: unhashable`，降级 -1.5 分 warn 了事——与 F1（未知 type 静默跳过）、F2（脏 rules 裸炸）同族。修复：guard.check_spec 的元素扫描块新增 `element_schema` 校验（元素配色/fill/slide.background 三个形态口径，dict/bool 一律 error 级），与 element_type 白名单同块、零新流程。
- **F5 审美风格覆写层（理解层）**：intent_compiler 对「东方/水墨/留白/电影感/静奢」审美词族零识别（实战打回通用 quiet editorial 默认）。修复：OCCASION world 之上新增 STYLE_OVERLAYS——occasion 管语义（什么场合）、style 管气质（什么美学），订阅 `design_intelligence_rules` 里已有的 family 叙事作为 family_hint 出口（song_elegance/cinematic_narrative/quiet_luxury 三条克制白名单）；显式 visual_world 永远赢；确定性（同输入同 Brief）。

**使用失误归档（不修包）**：build 模块 dict 括号缺失、guard check_spec 的 issues/warnings 键口误（探测虚惊）、heredoc 部分断言中断致 write 幻影（原子教训已沉淀：全 assert/一次 write）、ghost.py CLI 第二参为 positional 非 --out。

自检 51/51 全 PASS（新增 element_schema / intent_style 两检查）；3 项渲染链 skipped（LibreOffice 缺席环境守卫，与 v4.15 同）；hard=5 零漂移。

## v4.15 Critic 引擎移除批（2026-09-11）：过度设计归位——判断提炼为约束，代码回归治理

**案源**：用户裁定「QA + Critic 慢且过度设计」。实测解剖：治理本体 8ms/12 页 deck（guard 6ms + critic 2ms），真正耗时在 LibreOffice 渲染翼（10-30 s/deck，外部依赖）与输出 token 面（100+ 行杠杆）。收编裁定：**Critic 模块整体移除，9 维提炼为约束规范**。

**移除**

- **art_critic 模块（37 KB，整文件删除）**：九维评分/rubric/杠杆/director_verdict/diagnosis/root_cause 批打包一票勾销。
- **qa.py 双引擎收敛为单引擎**：`--critic` 旗标、critic_policy、critic_block、execution.critic、verdict.critic、critic 决策卡段（25 行 CLI 输出）、release_manifest 的 critic_report 参数/attest/双引擎状态合成全部切除。状态合成 = qa_report 单口径；manifest 契约字段 `critic_report` 移除（回归锁在 check_manifest_attestation 断言）。
- **Mode 档案三档不变**（spec/sketch/draft/review/release），critic 列整列删除；review/release 档 deliver 文案改写为像素事实。

**下沉（单一口径保真，零行为变化）**

- **primitives.py**：接管 STATEMENT_SIZE/FOCUS_LEAD/FOCUS_AREA_LEAD/MEDIA_*/TEXT_*/ROUNDED_MAX/LR_SPLIT_MAX/AXIS_*/CAPTION_ROLES/MEDIA_ROLES/BG_MIN_*/LINE_MEASURE_*/RHYTHM_INK_*/TEXT_CONTRAST_*/ASYMMETRIC_GRAMMARS/ANCHOR_DRIFT 常量与 is_background_layer/background_layer_ok/bg_exempt/content_occupancy/memory_anchor 函数（精确移植，一字不差，含 `_num_e` 容错语义——下沉前后对同一 spec/脏 size/脏宽度输出逐字节核对过）。
- **guard.py** 懒读取改直连（`_preflight_gates`/`_cached_gate` 的 `import art_critic` → `import primitives`，gate_source 标记 "primitives"）；回落双态消灭。
- **design_intelligence.py / layout_search.py** import 重指向 primitives（保下划线别名，零下游扰动）。
- **route.py** tiers 键 `art_critic` → `review`（tier 语义是审查档，不是模块名）。

**提炼（约束规范）**

- **references/design-craft.md 新增 §判断基线**：九维 + 权重 + 评审问句 + 常见失手四象限（表格 9 行），文首明言「代码不再替你打分」；>2 项失手 → revise 语义保留为**人的判断流程**，不是运行时。synthesize 判断与代码分离这条宪法的物理落地。

**自检调整**

- 移除 7 项打分对象检查（critic/critic_with_render/critic_pass_reachable/batch_verdict/rhythm_measured/focus_placement/director_upgrade）；
- check_manifest_attestation 重写为单引擎攻击面（幽灵页/改戳/无戳称 PASS 三场景）；check_execution_modes 追加 critic 全列回归锁；check_preflight_sync/check_background_qualification/check_text_contrast_gate 指路 primitives。
- **环境漂移自首**：LibreOffice 自本 sliding 沙箱缺席后，3 项渲染真实链检查（draft_import_contract/progressive_qa/render_cache）加 `skipped` 守卫（`soffice/libreoffice` 探测），环境完备时照常运行。

**数字**：自检 **49/49 全 PASS · 3 skipped（渲染器缺席）** ；hard=5 零漂移；scripts 从 14 → 13 个；包 288 → 253 KB（-35 KB）；QA+Critic 治理本体 8ms，慢的真相是渲染翼（外部依赖）——已用事实把「移除=提速」的直觉纠偏为「移除=去认知负担」。

## v4.14 四轮深扫批次（2026-09-11）：内脏模块首 fuzz + 品牌色词典合拢

**案源**：从未被 fuzz 的体内模块首测（art_critic 1244 行/intent_compiler/layout_search/asset_prompt/render_check 指标面）+ v4.9 V1 修复的残留裂缝追猎。

**修复**

- **F3 brand_colors 键名词典双路不对称（决策层接缝）**：路由侧 colors 词典收全 token、di 侧四槽（foundation/supporting/information/accent）白名单——`{"primary":"#0F2B46"}` 在 route 被标 brand_derived=True，在 di 白名单外过滤、seed_source=family_seed：**只给品牌主色（不给 accent）时品牌在本路静默丢失**。修复：通用 token 别名映射（ink/primary→foundation、secondary/muted→supporting、accent→accent；`slot not in valid` 防后者覆盖前者）；paper/background 与 information 槽语义不同——不扭。v4.9 的「未知键忽略」白名单精神保留（`{"x":...}` 仍回退 family_seed）。

**虚惊排除（16 项）**：art_critic 5 场恶意场景全优雅降级（空 spec/slides=None/无渲染证据/100 元素巨页/NaN+Inf 渲染指标——NaN 指标得 REVISE 不炸）；intent_compiler 5 场（空/9000 字/全英文/乱码/emoji）；layout_search 3 场（空 intent/未知家族回退 search/极端 density 容忍 family）；asset_prompt 3 场（空卡片/缺 type/全字段）；渲染指标 3 场（全黑 occ=0/全白 bright=1/纯 accent 页 accent_pixel_ratio=1.0 精确识别）；1×1 像素图 ValueError 为理论裂缝（pipeline 输入永远 ≥48dpi 整页，不会触达）——记录不修缮。

自检 56/56 全 PASS（新增 primary→foundation 别名断言）；hard_rule_lines=5 零漂移；zip 重新打包。

## v4.13 八层深扫批次（2026-09-11）：fuzz 驱动，2 修 1 对齐 + 14 项虚惊排除

**案源**：理解/代码/执行/逻辑控制/实现/决策/编译/验证八层系统性 fuzz（边界注入+竞争场景+畸形输入，非抽查）。

**修复**

- **F1 未知元素类型静默丢失（实现层）**：`compiler.DISPATCH.get()` 未命中即 ctx.warn 跳过——元素在产物中完全消失；`qa --mode spec` 零成本档不加载编译层，告警无处可见；guard 独立使用时零旗标。修复：`primitives.ELEMENT_TYPES` 单真源（spec 档禁载编译层，集合不能住编译层）+ guard 白名单 error 级前置拦截（真实流水线 compile checks=True 已拦，此为最后一处缺口）。
- **F2 guard rules 注入无容错（验证层）**：`check_spec(rules={"grid_bias":"abc"})` 裸 ValueError 炸全链——rules 是调用方/主题生成物，没有资格让治理层崩溃。修复：`_rule_num` 容错 helper（None/非数值→回落默认），批量接管 16 处 int/float 转换点。

**对齐**

- **V6 docstring 精确化（0 行为变化）**：主题 constraints 自动生效承诺收敛为五项白名单（accent_max/max_charts/max_colors/font_levels_max/font_families_max），承诺即实现。

**虚惊排除（14 项）**：XML 注入全转义；emoji/零宽/CJK 免疫；chart 空 series/长度不齐/NaN 有旗标且产物容错；负坐标 error 拦截；normalizer 幂等（内置 idempotent 过）；route 分类器 5 竞争场景全对；决策缓存键序归一；forecast_risk 六维目录语义（非风险条数）；sketch 档 error 仍守；compile checks=True 对未知类型 fail-closed。

自检 56/56 全 PASS；hard_rule_lines=5 零漂移；zip 重新打包。

## v4.12 微规则归位（2026-09-11）：35 条回 archive，CHANGELOG 保持纯时间线

**用户二次裁定**：Appendix C（35 条微规则）放 `references/archive.md`。

- `references/archive.md` 复活为**单内容档案**：只装 35 条微规则全文 + 使用协议（备查，不进入生成上下文）；A/B/D 区不复活（v4.11 判删成立）。
- 本文件尾部附录撤下——微规则唯一家 = archive，双份即重复。
- 指针回指：design-system 全文 35 条引用、README 目录树、selftest 知识探针目标；历史条目中叙述该文件的引用恢复带后缀（文件既存，陈述复准）。
- v4.11 其余裁定不动：版本词只住本文件与 README；A/B/D 内容判死；包文件数回到 29。

自检 56/56 全 PASS；hard_rule_lines=5 零漂移；zip 重新打包。

## v4.11 单档案整顿（2026-09-11）：archive 并入本文件 + 版本词只住叙事文件

**用户裁定**：历史决策单一档案 = 本文件；版本号只允许出现在本文件与 README。

- **archive 4 → 0**：`references` 三件套减负一档。Appendix C（35 条微规则全文 + 使用协议）迁入本文件尾部附录（编号 1–35 完整，自检以「排印微距/行长 CJK 22–38/数据墨水比」三条知识探针断言保全）；A/B 区为正文重复口径注、D 区 v4.0 纪事与本文件 v4.0 条目重复——判删，防机制复活的职能已由反向断言承担（自检 `modes`/`state_footprint` 系列）。包文件 29 → 28。
- **指针同步**：design-system 全文 35 条引用改指本文件附录；design-intelligence Appendix B 引用句删除（机器口径在 design_intelligence_rules）；production-contract Appendix A 引用改指本文件；README 目录树减行；本文件历史条目中 6 处带后缀引用按纪律去后缀。自检 `references` 全绿。
- **版本词清理（45 处）**：9 个脚本 + selftest docstring + design-craft 的功能品牌词（v2.4/v2.11/v2.12/v3.1/v3.2/vNext/V3 ·）一律改无版本命名——代码与规格只写当下真理，时间戳会腐烂。保留：纯审计锚点（v4.9 系列，指向本文件条目）与数据/契约版本（COMPILER_VERSION、json schema version、critic_version 字段——对外契约与数据结构，非叙事）。

自检 56/56 全 PASS；hard_rule_lines=5 零漂移；zip 重新打包。

## v4.10 执行层审计批次（2026-09-11）：链路 E2E 验证 + 2 修 + 2 文献修正

**案源**：理解/代码/执行三层全链路审计（端到端真实链路：route→guard→compile→qa(draft/review/release)→critic→manifest，含闸门埋雷与 CLI 管道实证）。

**修复**

- **E1 `qa.py --mode release --json` 的 stdout 被 manifest/hint 文本污染**：json 主体被包裹在文本行后，`json.loads(stdout)` 在 char 0 必崩——机器管道消费（`| jq`/subprocess）在 release 档必断。修复：manifest 分支两个 print 加 `--json not in argv` 守卫（沿用同文件 Critic 分支既有的「--json 保持纯净」守则）。实证：修复前 `qa … --json | json.loads` 必崩，修复后 status/critic/release_eligible 全字段可解析。
- **E2 CLI 传 .json 输入时裸 AttributeError 无指引**：`importlib` 对非 .py 返回 spec=None 直接炸栈。修复：友好报错（指明入口读 .py build 模块，裸 spec 走 --mode spec）+ 退出码 1。

**文献修正**

- `references/archive.md` 保留清单陈旧事实：design_dna.json「180 条」为 v4.0 前数字，实为 v4.5 起蒸馏精选条目制（8 条）——改为不随时间漂移的口径表述。
- `references/design-system.md` References [4] 死链修复：`mckinsey.com/（storytelling)`（全角括号+残括被拼进 URL，实测 404）→ URL 归位主域、注释以全角成对括号移出。同列 [1][2][3][5] 经实网验证全部 200 有效。

**判定（不修）**：lib `run_qa(mode=None)` 走 legacy 全量旧契约（usage 明示保留 `--level N` legacy），与 CLI 默认 draft 是两套受支持契约，仅记录认知项；`references/archive.md`（维护者考古档案，Appendix C 为 35 条微规则全文真源）与 `CHANGELOG.md`（演进史唯一时间线）均判定**有意义且不压缩**——不进生成上下文，压缩仅省包体积而损考古证据，收益不对等。

自检 56/56 全 PASS；hard_rule_lines=5 零漂移；zip 重新打包。

## v4.9 漏洞修复批次（2026-09-11）：深度审计 9 项实证漏洞的裁定与修复

**案源**：理解层+代码层双层深度审计（fuzz 实证，非静态扫描）。修复分级按宪法收口：必修 3、应修 2、可修 2，不修 3（记录给真实痛感驱动）。

**必修**

- **V1 brand_colors 双路语义分裂**：`scripts/design_intelligence.py` 的 `color_plan` 曾按 `dict.values()` 插入顺序 zip 强填四槽（抛弃键名），与 `scripts/route.py` 的键名驱动实现矛盾——同一 brief `{accent: #C8A24B}` 在两个派系里分别着色 accent/foundation。改为槽位白名单 + `#HEX` 校验的键名驱动；未知键/非色值忽略。`scripts/selftest.py` 同步四处新契约断言（含「错位回潮」反向断言）。
- **V2 record_dna 数据毁灭路径**：`_load_store()` catch-all 把「文件损坏」静默等同「文件不存在」，空库随后被整体写回。现在区分双态：缺文件=合法空库（读路径失败安全）；损坏→ strict 写路径拒绝写入并明示人工修复。
- **V3 song_elegance_editorial 签名自焚**：签名词表含「科技/品牌/brand/高级」四个泛词，而条目 `when_not_to` 自述科技发布会冲突——召回把自己召给反面场合（fuzz：科技公司年度总结 0.36 误召）。清洗为 10 个判据词后，该场景仅剩「年度总结」0.10 弱关联（<0.6 触发起点提示，行为合理）。

**应修**

- **V4 record_dna 拒门三路绕过**：嵌套 dict/list 藏色值、全角＃均可入库。新增 `_leaf_strings` 递归扫描 + 色值 regex 纳全角井号；fuzz 四路全拒（selftest 已钉断言）。
- **U2 accent 三元指认 vs monochrome 语义色例外**：`references/design-system.md` 指认三元扩为四元，补「指认主题」（色彩即内容主题时的一次性语义标记，一次有效、重复即装饰），与 `memory/design_dna.json` monochrome 条目语义色例外对齐。

**可修**

- **V5 calibration 损坏无声降律**：json 存在但解析失败时 stderr 警告一次并明示内置律兜底；`calibration_laws()` 的 source 改为按 laws/families 消费键精判，杜绝「文件存在但空覆盖」的 inline+override 谎报。
- **U1 九原则此前只在会话里**：v4.4–v4.8 各版本引用的「第 N 原则」无物质化定义，本档案头补齐九条元原则。

**不修（记录）**：guard `theme.constraints` 仅 3/17 项自动生效（V6）；check_design_dna 命中断言依赖 id 排序运气与「朱砂」措辞耦合（V7）；7/8 DNA 条目 `proven.qa=null` 的蒸馏身份缺口（U3，v4.5–v4.7 用户明确准入）。

自检 56/56 全 PASS（brand 四断言、V2/V4 拒门、calibration 链路全含）；hard_rule_lines=5 零漂移；五路径召回 matched 全对位。zip 重新打包。

## v4.8 死重终审（2026-09-11）：calibration_space 裁剪 + 全文件消费链核实

全文件逐一核实消费链后的唯一死重：`memory/calibration_space.json` 中 `boards`（10 套设计板原始测量明细 ~20KB）、`pooled_cells`（空壳）、`global`（零引用）三层。运行时 `calibration_laws()` 只消费 `laws`+`families`；原始明细信息已蒸馏入律，且被 v4.5–v4.7 三批 18 套样本超越——裁剪，provenance 留注。40KB → 10.4KB（−74%）。

其余 26 个资产全部有活体消费链（见终审表）：无多余文件。自检 56/56 全 PASS（visual_calibration_v3 链路完好）；zip 重新打包。

## v4.7 第三批六套样本蒸馏（2026-09-11）：经验库边际饱和信号 + 权威发声页

第三批 6 套（White Space / 寺馆 / 黑金策略 / Editorial Intelligence / Future Civilization / Modern Renaissance）。多数观察已被 v4.5/v4.6 条目覆盖（饱和信号——经验库逼近完备），真正增量四处：

- **design_dna.json +1**：`executive_voice_authority`（领导发声页信任公式：大到可引用的第一人称引言 + 纪实人像 + 实名职衔，其余全删；实测召回 0.60）。
- **monochrome 条目边界增补**：语义色例外——色彩即内容主题时（黑金策略的金）可让封面标题用色一次，一次有效、重复即装饰（防 monochrome 误杀合法语义色）。
- **design-system.md §Color**：accent 合法职责三元——指认答案 / 指认当前 / 指认印章；不承担指认的 accent 即装饰（第三批 C01 蓝点只标记折线末端与当前节点验证）。
- **design-system.md §Charts**：表图双通道（精确值归表、形状归图，不把图堆成表）+ Insight 行兜底（图不能被一句话领走时加 → Insight 行，但先自问图是否画错）。
- **验证**：自检 56/56 全 PASS；hard_rule_lines 5；四路径 recall 零漂移。

## v4.6 第二批六套样本蒸馏（2026-09-11）：母题变奏与单通道色彩

用户提供第二批 6 套样本（Apple×Braun / Aesop×Kinfolk / FT 机构报告 / Hermès×Chanel×Pentagram / 宋式美术馆 / Human Future Intelligence）。验证既有判断（页首 caps 页型标签 = Deck Rhythm 可视化、单强调、全幅重置、结尾闭环），新增四条：

- **design_dna.json +1**：`monochrome_photo_carries_color`（版式退成黑白灰，色彩唯一住所是摄影——accent 的位置即照片的位置；实测召回 0.50，既有七条零漂移）。
- **design-intelligence.md §Deck Rhythm**：母题变奏（一套 deck 只设计一个图形母题：封面注册、章节放大、数据退刻度、结尾收束，母题承担全部装饰语言）+ 页型标签统一词汇表（COVER/NARRATIVE/DATA/STRATEGY/VISION/CLOSING）。
- **design-system.md §Theme DNA Editorial default**：页脚箴言（全套同位同句逐页复诵，箴言只在不变中生效）+ 第二语言退为文化注释（竖排小字角落，不作翻译堆叠）。
- **design-craft.md §一-5**：估算与外推必须带标记（EST./E），与实测区分——分不清估计与事实即撒谎。
- **验证**：自检 56/56 全 PASS；hard_rule_lines 5；四路径 recall 行为符合预期。

## v4.5 六套世界级样本蒸馏（2026-09-11）：Taste Calibration 首次真实输入

用户提供 6 套世界级 deck 样本（Apple×Swiss / 东方编辑 / FT 战略 / 奢侈品牌 / 未来 AI / 博物馆档案）+ 生成提示词。按第四原则处理：**提炼判断经验，不固化模板**——六套样本验证现 10 人格矩阵足以表达其风格（Concept 05 ≈ VP-008×VP-005 混血），故人格行零新增。

- **design_dna.json +2 条可召回经验**：`comparison_single_decision`（对比表只给答案染色，实测召回 0.67）、`timeline_named_eras`（时间轴以时期命名，实测 0.62）；既有召回零漂移（song 0.36，无关 miss 仍 None）。record 守门机制原生拒收参数化判断，新条目全部以行为判断+proven 证据形态入库。
- **design-intelligence.md §Deck Rhythm**：页型节奏三手法——章节过渡页全幅重置（负责换脑，不负责传递）；结尾页回收封面语言（愿景句即落款，不放谢谢页）；跨页连续性三锚（caps 眉标/页码象限/Fig. 编号全文连续）。
- **design-craft.md §三 案例 0**：六套样本的正面蒸馏（可观察行为 → 判断 → 迁移手法：大数字必带参照系 / 摄影全幅出血或呼吸边框二选一 / 对比页只染一格），落点声明「学样本不学皮」。
- **不做的**：不把 6 套转为 6 个新主题（违反反模板原则）；asset_prompt 词表零增补（cinematic/museum/texture 已被 TEXTURE_LAYERS 与 ENERGY 档覆盖，重复即债）。
- **验证**：自检 56/56 全 PASS；hard_rule_lines 4；四条 recall 路径行为符合预期。

## v4.4 品味校准哲学决议（2026-09-11）：拆除校准工程，品味走经验记忆

**决议**：不做「Critic 审美校准系统」类工程模块。理由（用户原则）：标注-反推-改常量的校准系统必然长出更多规则、更多评分维度、固定审美标准与模板化输出——AI 只会检查，不会设计。

- **删除** calibrate 脚手架（288 行，零启用：标注样本集从未存在）与 design-system.md 原 §Threshold Calibration 方法论全文。
- **替代**：design-system.md 新增「Taste Calibration」——品味校准 = 设计经验增强：使用者给出「好/不好 + 为什么」→ 追加 `memory/design_dna.json` 经验条目（judgment 不参数化，数字只进 `proven`）。判断回流记忆与上下文，不沉积为代码。
- **Critic 阈值定位重申**：只守物理底线（对比度/溢出/色距/Accent 面积），只升不调；底线之上无审美分数线。DNA recall 与 visual_calibration（v3.0 参考空间，运行时在役）不受影响。
- **验证**：自检 56/56 全 PASS（−1：校准马具检查随脚手架同步拆除）；scripts 14 → 13；全库零 calibrate 残留 token。

## v4.3 代码架构合并（2026-09-11）：scripts 17 → 14，编译/治理双链收敛

- **编译引擎单文件化**：compiler + elements + charts → `compiler.py`（1545 行）。三者只被编译链消费，分层文件只剩 import 往返；对外契约 `compile_deck` / `COMPILER_VERSION` 不变，链内 import 3 模块 → 1。
- **治理层合一**：normalizer 整体并入 `guard.py`（`normalize_spec` 同文件直调）；其独立 CLI 由 `guard.py --preflight` 统一承接（preflight 本就先 normalize 后 check）。
- **不合并清单**（高价值独立边界，保留）：design_intelligence（大脑）、design_intelligence_rules（零依赖真源表）、route / layout_search（决策）、art_critic（审美）、qa（发布门）、render_check（渲染证据）、ghost（预览）、intent_compiler / asset_prompt（独立工具）。
- **运行次数审计结论**：主链已是单次链（normalize → guard → compile(checks=False) → render 页缓存/PDF 复用 → critic），无重复治理；fingerprint 5 处分职计算非冗余——第三原则现状即目标态。
- **验证**：自检 57/57 全 PASS；parity（guard / critic / normalize / compile 报告哈希 + PPTX 成员内容指纹[ZIP-mtime 免疫]）pre/post 逐位一致；12 页 draft 全链实测 93.8ms（normalize 1.9 / guard 3.1 / compile 84.6）。
- **指针同步**：selftest 4 处加载点与 REQUIRED_SCRIPTS、README 目录树、archive 历史表、CHANGELOG 旧条目；全库零悬空 token。

## v4.2 代码层过度设计审计（2026-09-11）：删除 6 处死代码 + 1 处豁免收紧

以反过度设计原则对 18 个脚本做 AST 级定义-引用审计（10,663 行运行时代码，不含 selftest）。结论：工程卫生整体优秀，过度设计基本不存在；发现的残余全部为「代际尸体」：

- `render_check.render_to_images`（22 行）：上一代公共 API，`render_evidence` 全库统一后零调用（含 CLI main）。
- `render_check._saliency`（4 行）：作者自注的兼容壳，唯一生产调用早已改走 `_saliency_with_method`。
- `guard._box` 第一版（15 行）：同文件 L675 同名定义覆盖，运行期永不可达。
- `primitives.mix_oklab / is_aux_text / no_line`（20 行）：全库零引用的孤儿导出。
- selftest `allow_missing` 移除 qa_worker 前瞻豁免：无引用的占位豁免是质量闸的自我开口。

**有意保留**（有实测依据的机制，非过度设计）：LO profile 锁（0.55s/次）、PDF 复用（1.7s/次）、页级缓存、saliency 双后端（OpenCV/确定性回退）、fit-cache 四件套。qa.py 巨型函数属欠分解而非过度设计，改动风险大于收益，不动。

验证：自检 57/57 全 PASS；guard preflight / intent_compiler（tokens 494、hash 稳定）冒烟一致；行为零变更（所删均为不可达代码）。

## v4.1 技能包结构压缩（2026-09-11）：文件 42 → 32，包体积 5.0MB → 0.93MB（−81%，zip 分发 ~0.3MB）

- **删除 assets/**：4.5MB 静态参考图全库零引用（代码内 `assets` 均为数据字段名），分发死重清除。
- **references 活跃文档 7 → 4**：themes / evidence-library / benchmark-calibration 三份文档并入 `design-system.md`（落地时查合一，原文零删节、章节降级收纳）；contract / intelligence / craft 保留独立路由。
- **archive 4 → 1**：`references/archive.md` 收编 production-notes / intelligence-notes / evidence-micro-rules / OPTIMIZATION 四个附录。
- **指针同步**：SKILL 路由表、README 目录树、craft / contract / intelligence 内引用、selftest `REQUIRED_REFS` 与 diet 扫描名单、archive 断言；历史文档内旧文件名按新容器改述。
- **验证**：自检 57/57 全 PASS（含 render_cache / draft_import_contract / progressive_qa 真渲染路径）；硬规则行仍为 4；运行时行为零变更。

## v4.0 判断密度重构（本轮）：从规则驱动到判断驱动

目标：工程复杂度让位给设计智能密度。AI 初始理解 token 降至 ~30%，规则行 −70%，运行时行为零变更（parity SHA 对齐，自检 51/54 与基线一致，3 项差异均为沙箱缺渲染环境）。

- **SKILL.md 25.9KB → ~5KB**：只留 10 原则 + Decision Framework + P1–P5 + Modes + 硬边界 + 路由表。
- **production-contract.md 51KB → ~5KB**：只留契约表/调用/最小 spec/失败码/Manifest；实现口径与历史移入 `references/archive.md`。
- **design-intelligence.md 33KB → ~6KB**：只留 Strategy/Direction/Page Intent/字阶/构图/节奏/取舍；引擎细则移入 `references/archive.md`，机器口径移入 `scripts/design_intelligence_rules.py`。
- **Intent Compression Layer**：新增 `scripts/intent_compiler.py`（需求 → Design Brief ~500 tokens）+ `templates/design_brief.yml`；Brief 之后不回读原始需求。
- **规则 −70%**：硬规则行 98 → ≤30；「禁止/必须」改写为判断句（视觉复杂度必须服务阅读路径）。
- **Memory 经验化**：`design_dna.json` 改写为经验口吻（矛盾 → 判断 → 教训），schema 与召回键不变。
- **QA/Critic**：实测两模块零重复代码块（v3.1 已分层），运行时保持原样（代码不进 AI 上下文）；瘦的是契约面：QA=Can deliver，Critic=Is it memorable。
- **归档**：OPTIMIZATION 纪事 → `references/archive.md`；README 版本史移入本文件。

## 路线图（开放优化建议）

1. ~~光学对齐渲染级复核~~ **已完成**。
2. **QA 分域扣分上限**：`penalties_cap={"guard":30,"compile":20,"render":15}`，扣满即止。
3. **accent 色距阈值主题化**：并入 `theme.constraints.accent_distance`。
4. ~~阈值校准闭环~~（**v4.4 否决**：校准工程注定长成固定审美与模板化；品味校准改建为 design_dna 经验条目，见 `design-system.md` §Taste Calibration）。
5. **报告版本可比性**：revision_log 记评分器版本，Manifest 加 `qa_version`。
6. **CI 依赖版本锁定**：固定依赖版本保跨机器分数可比。

## 历史

- **v2 评分可用**：Critic 证据驱动加减分（基准 3/5，PASS 可达）；硬门槛带真实失败码；QA 分域扣分明细。
- **v2.2 判定可信**：缓存内容核验；背景层免检资格；文字对比像素实测；QA/Critic 交叉校验。
- **v2.3 少跑一轮**：PDF/编译视图两层复用 + deck 级色彩图表纪律 + 焦点落位轴线判定。
- **v2.4 Director 升级**：`director_verdict` 首要杠杆；CARD_DENSITY 软压；SKILL 收敛为 Director 五步。
- **v2.5 三层执行架构**：draft/review/release；normalizer 第 0 级（今并入 guard）；Revision Batch Intelligence；Critic 稳定性门控；语义变更分类。
- **v2.6 Design Intelligence（V3）**：DNA 记忆 / 媒体决策 / 质量预算 / Pre-Critic 风险预测 + `layout_search.py` + auto_fit + route DNA 召回。
- **v2.7 文档智能密度优化**：唯一真源制；字阶矛盾修复；构图算子/Design Intent/中文排印/分组语法/仲裁/混血边界；DNA 推理链 + `when_not_to`。
- **v2.8 文档架构收敛**：评分体系并入 production-contract；文档去版本号叙事；参考文档 8 → 7。
- **v2.9 快速生成默认化**：`qa.py` 默认 draft。
- **v2.10 光学对齐 + 校准闭环**：`render_check.optical_alignment` → Critic alignment 加分；calibrate 脚手架（v4.4 因哲学否决拆除）。
- **v2.11 判断记忆与角色化色彩**：DNA Schema v2；品牌色优先；Chart Color Role System；两层布局决策；Asset Intent Cache；`--mode sketch`。
- **v2.12 推理降频与预测升级**：`deck_decision` + `page_intent_skeleton` + 家族直达；pre-critic 新增 4 族 5 码；负值染色惰性解析；编译缓存版本闸。
- **v3.0 参考空间校准闭环**：10 套设计板 79 单元实测律；`color_plan` + `visual_calibration_score` + `one_pass_plan`；提示词三层。
- **v3.1 QA/Critic 去工程化**：职责分层（QA=PASS/FAIL/WARNING，Critic=设计价值）；风险预测并入智能层；删门控/缓存/状态机；渲染三级。（纪事后并入本文件，不另设档案）。
- **v3.2 减认知负担 + 去运行时浪费**：primitives 懒加载；`--mode spec` 零成本档；SKILL 33.9→25.9KB；`DESIGN_RULES` advisory 化；Critic 主输出 `diagnosis`。
- **验证口径**：自检全 PASS；12 页基准 draft 0.29s / release 冷 2.58s；真实项目 11 页 QA 99.5 / Critic 90.9 / 6 轮收敛。发布门可自证：缓存核验、背景资格、像素对比、报告互核一律 fail closed。

---
