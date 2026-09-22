# 变更记录

## 7.1.0 · Case-led Audit / Medium Separation + Compact Asset Context

以 `PPT_CASE_003｜山止 SHANZHI` 15 页高端东方茶品牌融资路演为真实样本，复盘从 brief、资产生成、QC、编排到 release 的完整路径。

- 修正摄影资产被 `rice paper / 宣纸` 材质词误触发水墨闸门的问题；材质不再伪装成介质声明；
- 新增回归测试：摄影卡可以使用 rice paper 材质，但不会收到 `hand-painted ink-wash` 与 `no photographic shading` 的冲突指令；
- `vao.py assets` 默认只打印紧凑资产摘要，完整 prompt 改为显式 `--show-prompts`，避免把长 prompt/negative 清单灌入 Agent 对话；
- SKILL 增加图片首轮 QC 后的设计判断：一次定向修复仍不成立时，删除图片并改用 native composition；
- 生成骨架的构图 JIT 入口改指向 `references/design-judgment.md`，字段细节仍按需查 `design-system.md`；
- 版本统一为 `7.1.0`。

案例审计见 `AUDIT_2026-09_CASE003.md`。

## 7.0.0 · Practitioner Audit / One Production Contract

以 `PPT_CASE_004｜CIRCA 纪时酒庄` 为真实端到端样本，完成 Intelligence / Context /
Architecture / Execution / Design / Production / Verification 七层审核。

- 删除 route 里无消费者的 deck-level `intent_interpretation` 镜像；
- 删除 route 里无人读取的 chart/text budget 镜像，只保留资产调用预算；
- full-canvas solid background shape 获得窄范围空间层资格，不再与 source zone 冲突；
- check 在资产 I/O 之前发现缺少 `python-pptx`，避免无效 QC 轮次；
- `make` 改为 `check` 的兼容别名，消除旁路绑定/Guard/compile/ghost 链；
- 新增 `references/design-judgment.md`，SKILL 改为更短的 JIT 导航；
- 新增 `AUDIT_2026-09.md` 记录文件、函数、规则、Context、Command 与交互存废判断；
- selftest 仍作为 CI 回归，不进入 Agent 默认 Context。

实战证据、职责矩阵与停止条件见 `AUDIT_2026-09.md`。

## 6.5 · Context Diet + Zero-Loop Assets（上下文减法 34%、既有素材零回路、稳定指纹）

原则仍是 **删 > 合 > 简 > 复用 > 加**；这一版把刀口对准**作者每次都要付的上下文与回路**，
能力与判定口径一条未减：

### 一、上下文减法：SKILL + brief + 四份 references，124.0KB → 82.0KB（−33.9%）

| 文件 | 原 | 现 | 手法 |
|---|---|---|---|
| `SKILL.md` | 18,817 | 10,945 | 删与 references 重复的叙述；只留判断纪律 + 执行协议 |
| `templates/brief.yml` | 15,270 | 7,650 | 注释砍半；字段、必填项、语义零变化 |
| `asset-workflow.md` | 15,548 | 8,915 | 案例并入表格；迁移路线保留 |
| `design-system.md` | 21,835 | 15,877 | 全文重写：全部表格/字段/首轮值保留，叙述压缩 |
| `production-contract.md` | 18,621 | 12,809 | 权威表保留（含全部 10 个阻断码），重复论述删除 |
| `design-craft.md` | 21,758 | 13,643 | 案例保教训删过程；五判断/减法链/信号表逐条保留 |
| `design-intelligence.md` | 12,168 | 12,168 | 逐行读过：全是独特校准，不动 |

红线：**只删重复与固定答案，不删事实**——字段名、阈值、阻断码、契约行为逐条保留；
220 项文档契约钉（死引用/禁用旧词/阻断码全列/README 项数）全过。

### 二、既有素材零回路：assets 阶段自动登记（`asset_source` 从必填退化为注记）

v6.4.3 前，早于清单存在的字节必须人工在 slide 写 `asset_source` 才生效——这是实战里
最贵的一类漏洞（写了却不生效/忘了写→阻断→回路）。现在 `prepare` 时对**字节已存在**的
规划资产自动如实登记 existing（保留规划身份与 prompt，不退化成 `existing-<hash>`）；
`asset_source` 保留给版权/出处注记。实战验证（PPT_CASE_003，15 页 13 图）：plan+assets
一次调用 13/13 existing 零回路，check release 一次 PASS。

### 三、方向预览默认全量：≤24 页自动逐页（常规 deck 零采样损失）

`--ghost-pages` 默认 4 → 24；页数 ≤ 上限即全量预览，超出才采样。release 档证据范围
如实记录。

### 四、`plan_sha256` 稳定指纹：同输入重跑字节不变

旧实现混入时间戳等易变键，导致同一 plan 每次指纹不同、缓存永不命中。
`asset_workflow.stable_plan_sha` 排除全部运行态键（`workflow` 的时间戳/路径 +
`performance.planning_ms`——后者是实战验证时才抓到的第二个漏网键，两次 plan 指纹不等）；
骨架注释、清单、QC、spec 校验统一走它，自检新增「同一 brief 两次 plan 指纹必须相等」钉。
（教训入库：改指纹方案必须 grep 全部写入方与全部易变键——含 selftest 辅助代码。）

### 五、代码减法延续（Batch A）：16,812 → 15,201 行（−9.6%）

删无人消费的分支与重复实现（ghost 重复绘制路径、compiler 死参数、vao 冗余包装），
零行为变化项逐一由 220 项自检钉住。

## 6.4.4 · Editorial Data（数据是主角：系列色去重、accent 单占用、预览不发明装饰）

方向不是「更好看」，而是**少颜色不是色值表短，而是每个序列/扇区都拿得到自己的颜色**；
少装饰不是少画东西，而是预览别替产物发明边框。零新增 Guard Rule / Design Judgment /
Warning / Reference——全部落在执行层默认值与契约，并用两台仪器把结论钉住：
拆编译产物的离线图表审计（8 图形 × 深/浅两主题）与离线自检 217 项。

### 一、单一信号色主题下系列色不再重复（最贵的一条）

* 案源：`derive_tokens` 里 `premium = hx("premium") or hx("optional") or accent`——主题没声明
  第二信号色时 premium 回退成 accent，六档系列色退化为三个值、两两同色（实测 dark：
  `#C0A062`×2 / `#5A4A2B`×2 / `#D3C19F`×2）。后果不是「不好看」：4 段甜甜圈里两段完全同色，
  双序列折线画成一条线，读者看不出这是两组数据。夹具里那个 3 段甜甜圈三段**全是**
  `#D2542B`。
* 修法：单信号色主题 ⇒ 系列色改为该色相的一条明度阶梯（accent 起、向背景反方向逐档提亮）。
  相邻相对明度差实测 ≥0.05（dark 最小 0.062 / light 0.068），六档互不相同且都在背景可见范围内。
* 证据：审计「重复着色」列 8 例 → 0 例；4 段构成图数据色 2 → 4、3 序列折线 2 → 3。

### 二、accent 不再被两个消费者同时占用

* 案源：accent 既是「第 1 档系列色」又是「高亮色」。高亮在手时第一个序列与高亮同色——
  甜甜圈默认高亮第 0 段、第 1 段取 `series1 = accent`，两段同色；「高亮第 2 序列」同理。
* 修法：一处派生 `ctx.series_palette(count, highlight)`：高亮位 accent，非高亮从第 2 档起。
  多序列折线与构成图两条路径改成同一份派生，任何组合下不撞色（深层断言覆盖 hl × n 组合）。

### 三、预览不发明装饰

* 案源：ghost `_draw_chart` 给**每张**图表画圆角外框，而产物里 chartSpace / plotArea 都不描边
  （审计：0 例有框）；甜甜圈预览用 ink/secondary/muted，与产物的同色相阶梯毫无关系，
  作者会把「金色系深浅」读成一排中性灰。
* 修法：外框只属于占位分支（ABSTRACT / 载荷缺失 =「我不画」的边界）；镜像图形不画框；
  扇区色与堆叠段色改走与产物同一份 `series_palette`，段内文字用同一套自动对比色。
* 顺带修掉一个静默回退：`color_to_hex` 返回不带 `#` 的 HEX，直接喂 `parse_token` 会解析失败
  并静默回退成灰——新增 `_rgba_color()` 直取 RGBColor，自检里钉住「预览扇区色与产物色阶同源」。

### 四、钉值变化的逐字节归因（不是回归）

两档钉值变了（fast `cdfa8581…` → `06899733…`、strict `29cb57fd…` → `0a8c1e18…`，各 +14 B）。
按纪律先归因再重钉：用改前副本重建，**旧钉值字节级复现**；两份产物只有
`ppt/charts/chart2.xml` 的 2 个色值不同（`#D2542B` → `#DE7555` / `#E79177`，即夹具那个甜甜圈的第 0/1 段），
该 part 压缩 834 → 848 B，其余 76 个 part 压缩字节逐一相同——+14 B 全部可归因。

### 五、第二轮：用 20 张图当测试稿暴露的四处「预览不同形」（同日补齐）

拿技能包做了 20 页图表样张（一图一页、20 种几何）当真实用例，预览与产物的差异立刻现形：

* **多序列折线被摊成一条**：ghost 把「类别 × 序列」摊成一维条画成**一条折线**
  （s04 财务三线，产物里是三条）。修法：多序列按序列分组画，颜色走与产物同一条链
  （`series_roles` → 角色色，否则系列色阶；高亮那条 accent + 加粗 + 末点圆点）。
* **面积图被画成折线**：产物里 `area` 是填充系列，预览必须填面。
* **每个顶点都落点**：产物只在 `line/trend` 的高亮点、`sparkline` 的两端落点，预览改成同一处。
* **单序列高亮不可见（真缺陷）**：主题没写 `chart_primary` 时，单序列图的基础色**就是**
  accent，于是四根柱全是 `#C0A062`，「高亮 Q4」什么也没说。修法沿用同一处方：
  有高亮且基础色 == accent 时，基础退到图表 primary 角色，**accent 只占一个位置**；
  折线的高亮标记也从 secondary 改到 accent（强调语义全库统一）。

自检 220 项（editorial 一段共 12 条断言，含本轮新增 3 条：多序列预览按序列分画、面积图是面不是线、单序列高亮与基础色不同）；
钉值再次逐字节归因（净 -3 B：`chart1`/`chart2` 的序列级默认填充 `#D2542B` → `#FFFFFF`，
未压缩大小不变）；年度总结稿同步重生成，只有 `chart1.xml` 一处色值变化（净 -2 B）。

### 不变量

自检 **220/220**（新增 13 条 editorial 断言）· 双档钉值重新钉住 · KPI 仍 1/1/0/0/0 ·
年度总结稿 release strict **PASS**、`release_eligible: true`、PPTX sha `f54f77466ea3dcf1…`（3,035,545 B，未变）
· 规则条数 / 判断面 / QA 判定口径一条未动。

## 6.4.3 · Practitioner Feedback（用实战暴露的问题修工具；不新增判断面）

这一轮没有新增 Guard Rule / Design Judgment / Reference，全部改动来自**真实交付一次年终总结稿**
时被踩到的问题：每一条都有案源、有取证、有回归钉子。产物字节、判定口径、规则条数不变。

### 一、方向预览不再画「假图」（最贵的一条）

* 案源：`big_number_row` / `steps` / `timeline` / `waterfall` 在预览里被一条通用柱图兜底画成
  「柱高 = 序号」的样子，作者按预览改了三页构图，而编译产物里根本没有那些柱子。
* 修法：预览覆盖契约——只画与产物 **mark 结构同形**的图形，没实现同形几何的类型如实写
  「预览不渲染此图形 · 以编译产物为准」。两类归属（镜像 / 抽象）必须覆盖图表类型全集。
* 顺带补齐同形镜像：数字行、步、轴、瀑布、进度条、排行条、堆叠条 + 原生柱族三向，
  并按编译器的数值列宽口径修掉「小尺度预览把数值挤出框外」。

### 二、资产 QC 的两条语义

* `brightness_balance` 改为**相对声明底色**：画面与底色亮度差 < 0.18 即同调，不判过暗/过亮。
  此前整幅暗色画心必然被判「整体过暗」——引擎在反对作者声明的方向（案源：四张夜景背景图
  亮度 0.09–0.11，作者按方向声明文字色后告警依旧）。
* `contrast_suitability` 认**声明的文字色**：`text_color` 写 `#RRGGBB` 与 `dark/light` 都生效。
  此前只认后两种字面词，写 hex 等于没写，安全区亮度落在 0.70–0.55 时会放过一行读不出来的浅字。
  解析唯一实现在 `primitives.text_is_dark`。

### 三、既有素材的身份不再断链

* 清单前已有的字节必须显式登记（`asset_source`），这条纪律不变；变的是**登记之后**：
  若该图正是本稿 plan 规划的那张（文件名 = 规划的 `asset_id`），清单保留规划身份与
  prompt/negative，不再退化成 `existing-<hash>`——否则稿件与清单只能靠肉眼对齐，
  下一次迭代就会绕过链路。
* 阻断信息点名校验失败时该走的那条路（此前只说「须显式标记」，不说怎么标记、文档在哪一节）。

### 四、把「段间契约」也测起来

* 新增端到端用例：`brief → plan → assets → 出图 → build → release` 一次走通，并钉住两件事——
  骨架发出的 plan 指纹与清单认的指纹是同一个；声明既有素材后身份保留。
* 实战中这段契约缺失让作者连卡三轮（骨架指纹 / 清单指纹 / 稿件抄错），补上后一次即可走通。
* 自检 207 项（原 202）；`references/production-contract.md` 增「方向预览的覆盖契约」与
  「资产 QC 的两条语义」两节。

## 6.4.2 · Evidence Validation + Ownership Closure（用真实语料验证，不用合成语料下结论）

这一轮**不删任何规则、不加任何判断**，只做三件事：真实 deck 语料测量、QA 归属收口、px→pt 单源化。
理由：v6.4.1 的规则存废结论建立在结构证据上（谁能被触发），而「值不值得留」必须用
**真实触发率 / 阻断率 / 修复后是否消失 / 是否翻转 release** 回答。

产物字节未变（fast `cdfa858160f3d327…` / strict `29cb57fd32b60507…`），自检 202/202，五 KPI = 1 / 1 / 0 / 0 / 0。

### 一、真实 deck 语料（五份真实稿 + 两组修订对照）

* 语料全部走真链路（brief → run 出 plan 与骨架 → 作者填充 → release 检查）：
  董事会复盘 / 产品发布 / 研究综述（打磨过的三份）+ 典型 AI 初稿（未打磨）+ 15 页回归夹具。
* 打磨过的三份：零阻断、零事实错误；唯一 warn 是标题断言了图表算不出的数字——真阳性且不阻断。
* 典型初稿：`data_provenance` / `chart_payload` / `data_integrity` 全为 error → BLOCKED；
  按根因一次改完 → PASS，且该稿 guard 层四条规则**全部消失**（拿到了「修复后消失」的真实证据）。
* 夹具的 `geom_occlude` ×2（眉标∩页码 62% / 100%）→ 收窄过宽的眉标框（不是挪页码：挪到右下角会撞图片）
  → 归零。顺带披露测量口径：warn 判的是**声明几何**（作者可解释的框），不是渲染后的字形墨迹。
* 真实语料上 31 条规则里 25 条零触发 → **错误面一条不动**；合成变体（39 个）覆盖 31/31 条只证「还能被触发」，
  与真实分布分开统计，不参与存废。
* 分桶（高频且不阻断且修复后自然消失 / 低频且不影响 release）本轮两桶皆空——空的原因是语料只有五份，
  不是判据失效；判据当前用于回答「下一步该看哪条规则」，不是「哪条能删」。

### 二、归属收口：run_qa 移出 QA

* QA 只剩消费面（9 个纯函数）：规则开关 + 裁决，输入全部由调用方传入；不再自己触发编译。
* 编排归 `vao`（唯一编译入口），QA 零导入执行层（compiler / compile_cache / pipeline），
  零几何/像素运算、零产物字节读取；保留的依赖只有 guard 的 checks 与资产 owner 的纯谓词。
* KPI 的 QA 探针从「登记一处已知重叠」改为**验证收口**：编排调用 0 处、唯一编排点存在、职责重叠 0 处。

### 三、px → pt 单源化

* `PT_PER_PX = 0.75` + `px_to_pt()` 成为唯一换算定义（编译 12 处 + 预览 2 处调用点）。
* 按既定门先证等价再合并：改前改后同参数各跑，**两档产物 SHA 与预览逐字节一致**；
  其余同值常量逐一分类为「同数不同事实」，未合并。

### 四、规模

* scripts 14,286 行 / 778,108 B / 357 函数（净增全部来自测量与验证入口，判定面不变：31 条规则 / 77 处发射点）。
* fresh fast 2,478 ms / HOT 38 ms；fresh strict 6,620 ms / HOT 117 ms。

## 6.4.1 · Convergence（职责单源 + 触发率仪表；不再扩大删除面）

这一轮不删规则，只做四件事：**单事实单归属、触发率仪表、去文档漂移、判断重复审计**。
验收口径也从「删了多少行」换成五个收敛指标（同一事实测量 1 次 / 判定 1 次 / 引擎意见 0 /
无消费者 Context 0 / QA 重新设计 0），外加审美指标（判断入口 ↑ / 引擎意见 ↓）。
产物字节未变（fast `cdfa858160f3d327…` / strict `29cb57fd32b60507…`），自检 201/201。

### 一、单事实单归属

* **双阈值探测器**扫出「同一数值被 ≥2 个模块当阈值用」14 处，逐条分类后确认 **3 处是真重复**，
  本轮回收到唯一实现：
  - 图表标签空间下限（`190` / 标签数 `6`）→ `primitives.CHART_LABEL_MIN_H` / `CHART_LABEL_MIN_COUNT`，
    `guard` 与 `compiler` 各自消费（原来两处各写一遍）；
  - 拉丁词整词匹配 → `primitives.latin_word_match`（`asset_prompt` 的术语判定与 `route` 的关键词
    判定此前逐字重复）；
  - 背景偏浅的判据 `0.5` → `primitives.LIGHT_BG_LUMINANCE` + `is_light()`（`pipeline` 的种子可读性
    兜底与 `primitives` 的 muted_soft 推导共用）。
* 其余 11 处是**同数字不同事实**（几何比例、sha256 长度、数学边界），逐条写明分类；
  头号去漂移候选是 px→pt 换算 `0.75` 的 13 处内联（渲染路径，需逐字节复核，留待下轮）。
* 目录/执行层首次审计结论：**Compiler 没有第二套设计判断**——34 个 warn 全是「声明不可执行」的
  事实兜底，唯一改变呈现的 `hide_redundant` **只在作者声明该政策时**发生。
* 查出**唯一**职责重叠：`run_qa` 在缺 `compile_report` 时自己调编译（属编排，不是判定）。
  记为移交候选，本轮不动刀。

### 二、Guard 触发率仪表（error 面暂停删除）

* 新增触发率遥测（住在夹具目录、不入库）：`rule → 触发稿数 / 阻断稿数 / 实例数 / 修复模拟清除 /
  覆盖缺口`，并支持 `--corpus <目录>` 接入真实语料（定义 BRIEF/NEED 的构建脚本或 spec 文件）。
* 首轮：语料 43 份（真实 1 · stale 3 · 合成 39），**规则可达性 32/32**；真实夹具抓到两条
  真事实（眉标与页码重叠 62% / 100%）；元素级 error 的机械修复 10/10 清除。
* 合成语料只用来证「规则可达」，**不作为任何删除依据**：真实稿的触发率要等真实语料。

### 三、Reference 去漂移（SKILL = 导航，reference = 唯一事实源）

* 实测 SKILL 已无阈值字面量；移除的是**契约/命令的双源**：三阶段与快速档的命令行 → 指针到
  `asset-workflow` §2；COLD/HOT 阶段块 → 指针到 `production-contract` §Cold/Hot。
* 文档跨文件重复条目 **3 → 0 段**（SKILL × 5 份 reference，段级比对）。
* 新增自检钉子：**SKILL 只做导航（不复制命令行与阈值字面量）**——漂移防线。

### 四、判断重复审计与收敛指标

* 五层链路逐层给出「有没有再判断一次」的结论与证据；引擎意见清单：现存 **0**、已撤销 **4**。
* 三个可复算仪表随本轮交付（归属审计 / 触发率遥测 / 收敛 KPI），口径写在各自文件顶部。

## 6.4.0 · Subtraction · Round 2（引擎只在两种时候发声）

Round 2 把所有执法规则逐条过了一遍：**trigger / fix / recurrence / release impact** 四项都站得住的
才留。结论收敛成一条判据，写进本轮契约：

> **引擎发声只有两种合法来源：① 事实（几何 / 内容：装不下、重叠、读不出来、声明缺失、键名不被读取）
> ② 作者自己声明的刻度（`theme.constraints` / `rules`）。** 两者之外不发第二意见——审美取舍、
> 编辑式口径、位置纪律、图例开关、类别多少算多，全归设计判断。

产物字节未变（fast `cdfa858160f3d327…` / strict `29cb57fd32b60507…` 均逐字节一致），
plan 内容与体积未变；自检 200/200。

### 一、撤掉「对作者选择的第二意见」（Guard）

* **行长执法整条删除**：`line_measure` 的两个出口（>上限的 warn、>2× 的 error）在实测里
  对**装得下**的文本框开火（12px / 1200px 宽盒、165 字单行宽度仍在框内），而「真装不下」
  由 `_text_box_capacity`（折行高度 / 不折行宽度 / 声明的 max_lines）判定——两者测同一件事，
  弱的那个还在误报。删函数、`LINE_MEASURE_*` 三个常量、返回面上的 `line_measure` 统计、
  以及 `MEASURE_EXEMPT_ROLES` 别名。
* **图表容量上限**（类别数 > 引擎表）删除：标签空间不足时渲染器本来就会 `hide_redundant`，
  容量不是发布障碍；连带删掉 `CHART_LIMITS` 表。
* **标签间距猜测层**（`label_gap` / `label_safe_margin` 「可能造成」贴线）删除：对作者写下的数字
  做猜测，不是观察到的碰撞。
* **图例开关 hint**、**眉标/页码位置纪律**（漂移 warn、不在上缘 hint、换象限 warn）删除。
  `deck_anchor` 只留两件事实：**声明了有没有落**、**编号是否连续**；位置追踪代码一并退化。
* **对比度 <3:1 的软档 hint** 删除（消息自己都写着「做装饰位没问题」= 引擎判不了用途）；
  `<1.8:1` 的「等于没有字」保留为 warn。

净账：规则 id 31（不变）· 发射点 84 → 77 · hint 5 → 1。减的是「同一事实说几次」，不是「查几件事」。

### 二、Guard × QA：写清允许清单

* QA 只有 8 个码由 guard 供给，且全部 N:1（多规则 → 一个根因码），其余码来自别的阶段的不同事实
  （编译报告 / 资产链 / 三态结论）。QA **不重新测量**，只把 error 归组进 `fix_plan`。
* 真正被清掉的是**同一事实的两级阈值**：装不下（行长 fatal vs 容量）、标签空间（error vs 间距 warn）、
  弱字对比度（<1.8 vs <3.0）、图表容量（warn vs 编译期处理）。
* 允许清单：**一个事实一次测量、一次判定、一次报告**；同码可由多规则供给（同根因），
  但**不允许两条独立测量供同一个码**。

### 三、Reference 走 JIT（按节，不按卷）

* 测量：5 份 reference 各有触发点（无死文件），但路由是文件级的——查一个码要读整卷。
* SKILL §09 的「什么时候读什么」表从 5 行改到 8 行、每行给到**节**（含此前只在命令段出现的
  资产工作流节）。单次任务读量：查门槛 + 报告字段 14.2 KB → 3.3 KB。
* `design-craft` §三 引言同步为代码真实口径（信号只在事实或声明刻度时发声）。

### 四、Design Judgment 防模板

* 抽查文档层的反模板纪律仍在（§反模板原则、§方向不是模板、§七 什么时候可以不照办），
  文档记录的是判断依据不是视觉答案；本轮又撤掉两处「把判断固化成坐标/上限」的执法。
* `chart_argument` 不再在消息里给视觉答案（原「改用 waterfall / big_number」），
  只陈述几何事实与 why，编码方式交回设计判断。

### 五、自检

5 处断言按新判据重钉，每条**同时**钉住新行为与「旧行为不得回归」：软档必须不再发声、
`chart_muted` 的能力保留在硬档上、位置漂移必须不发声、存在性与编号连续性仍各点名一次。
200/200（连跑两次），QC 等价性 exit 0。

## 6.3.0 · Subtraction（结构化减法：删掉写死的判断与没有消费者的字节）

这一轮的目标不是更大的 Skill，而是**更短、更可靠、更有判断力**的生产路径。顺序照旧：
**删除 > 合并 > 简化 > 复用 > 新增**。产物字节仍是验收条件
（15 页基准稿 `out.pptx` fast `cdfa858160f3d327…` / strict `29cb57fd32b60507…` 均未变）。

### 一、删掉「写死的设计判断」（Intelligence）

引擎此前把设计判断写成了查表答案：`FAMILY_MOVES`（家族 → 叙事动作）、
`COMPOSITION_BY_FAMILY` + `COMPOSITION_POOL`（家族 → 构图语法 + 备选）、
`QUALITY_BUDGETS`（家族 → 质量预算），共 **43 条目**，加上 `page_move` /
`composition_move` / `quality_budget` 三个函数。问题是这类表的**第一候选会被照抄**：
页面拿到的是一个先验结论，而不是从内容推出来的选择。现在：

* 骨架不再给「叙事动作 / 构图提案 + 备选」，改为给**判断项**（`构图: 待判断——先定这页唯一
  主语，再定它如何被看见`）；作者显式声明 `composition` 时原样透传。
* 只保留两类**可推翻**的查表：媒体需要与否（`MEDIA_MODEL`，带置信度与理由）、
  家族名解析（`FAMILY_ALIASES`，两套命名的唯一映射源）。
* selftest 反向钉住这一点：骨架里**不许**再出现表生成的答案（D1b）。

### 二、合并与简化（架构层）

* **家族词汇表归一处**：`FAMILY_TOKENS` = `MEDIA_MODEL` ∪ `FAMILY_ALIASES` ∪
  `COMPLEX_LAYOUT_FAMILIES`。此前 guard 校验、guard 提示、di 解析各自拼一遍
  「哪些写法算认识的家族」。注意 `resolve_family` 的语义（别名要归一到 di 家族名）
  由新检查守住，不能因为合并而改变。
* **字宽模型只剩一处**：guard 的行长判定自带 `1.0 / 0.5 em` 常数，与编译器的
  `primitives.text_units`（1.0 / 0.55）分叉——同一个物理事实两个口径。现在 guard
  按本段文本的平均字宽反推容量，口径与编译器一致（12 个探针读数变化 8 个，方向只会更保守，
  不再虚报行超限）。
* **删掉五个零消费者计划字段**：`media_budget` / `text_budget` / 逐页 `mode` / `index` /
  `declared_type`（`mode` 与 deck 级同一事实）。plan.json 49,694 → **37,462 B**（−24.6%），
  逐页意图块 11,178 → 4,682 B（−58%），骨架 18,427 → **16,813 B**。
* 清掉 4 处未用导入。

### 三、运行时减法（Execution）

* **热轮零字节读**：判定可复用且凭证已带 `sha256` 时，资产字节**一个都不读**——
  判定看 size+mtime_ns，编译投影与资产链核验消费凭证里的 sha256，编译与预览都在各自缓存里。
  此前热轮无条件把整批字节读进来（**50.3 MB**），没有任何消费者。热轮 fast
  57–61 ms → **38–42 ms**。
* **严格档不变**：strict 的判据本身就是现算的 sha256，照旧逐字节读数（selftest 新增一项
  钉住「不许靠凭证转抄」）。
* **`require_snapshot` 语义精确化**：给了字节就必须够用（缺一份＝不一致，fail closed）；
  一次也没给＝编译器自己读一次——那不是重复读，是必要的读。
* **BLOCKED 不再伪装成复用**：打印第三种结局「复用路径: 未成立 · 本轮 BLOCKED（原因）」，
  `RunEvidence.blocked()` 清空复用主张与凭证。失败不许用性能语言表达。

### 四、审计方法（可复用）

静态「没人调用」在本库会误报：编译器用 `DISPATCH` 表派发元素渲染器，`compiler.add_text` 等
四个函数静态无调用点、运行时每页都在跑（曾有 186 行被误判为死代码）。新增
运行时覆盖探针（一个跑六条流程、给每个函数包记录器的小脚本，住在夹具目录、不入库）：把每个模块的函数包一层记录器，跑 plan / assets / run /
check（冷+热）/ preview / dna 六条流程，再逐个用「表引用 / 回调 / 方法」复核。

### 五、验证

selftest **200/200**（新增 2 项：热轮零字节读、严格档必读）· `qc_equivalence` exit 0 ·
产物摘要未变 · 热轮契约 `ok · 阶段 identity,evidence,release` · 冷轮降级步骤全部带原因。

## 6.2.0 · Same Fact Once（同一事实只产生一次 · 可证明的复用）

这一轮**不追求更快**（fast 热路径 55–63 ms、strict 热路径 ~100 ms 已经够用），也不再
删能力：目标只有一个——让「为什么可以复用」变得更简单、更可证明。做法不是加抽象层，
而是把**已经存在的事实**统一起来：同一事实只产生一次，同一判断只执行一次，同一证据只
保存一次。产出字节仍然是验收条件（15 页基准稿 `out.pptx` 摘要未变）。

### 一、身份层：全库唯一入口（合并，不是新增能力）

审计发现同一件事被写了多遍：文件摘要 ≥5 处、幽灵来源 3 处、spec 家族 3 处，字节凭证
在三个地方各写一遍（平铺字段）。现在只有一处实现：

| 事实 | 唯一入口 | 收编掉的实现 |
|---|---|---|
| 值 / 内容身份 | `primitives` 的 `identity`（规范 JSON → sha256，`schema` 区分键空间） | 资产指纹、brief 来源摘要、页面键、联络表键、spec 指纹、编译视图、引擎指纹 |
| 字节身份 | `primitives` 的 `digest_bytes` / `file_digest` | 缓存层的短/全摘要别名、QA 的整包重算循环、多处内联 sha256 |
| 「还是那一份」的凭证 | `stat_witness` + `witness_matches` + `byte_witness` | QC 记录的三个平铺字段、编译缓存的 size/mtime 比较、资产核验的 size/mtime 比较 |
| 产出证据的代码身份 | `engine_fingerprint(scope)`（compile / preview / measure） | 编译引擎文件清单 + 指纹、渲染器指纹、QC 引擎指纹（各算各的，其中渲染器指纹有两份实现） |

同时消掉两处**同一事实存两遍**：QC 报告里与 `sha256` 同值的平铺副本；产物记录里
`pptx_sha` / `pptx_size` / `pptx_mtime_ns` 三个平铺字段合并为 `output_witness`，
报告副本不再重复存一份 `output_sha256`。QC 报告升到 v4（核对方与写入方共用一个 schema 常量）。

### 二、运行时事实账本（`run_evidence.py`）

一次 `check` 只产出一份事实：**输入 / 资产 / 产物 / 判定 / 像素 / 页** 六类身份、
**读数**（各阶段耗时与解码 / 变换计数）、**复用**（每条「还是那一份」的凭证）与
**降级原因**。报告、发布清单、预览证据都从这一份账本取数，不再各自拼装临时字典。

### 三、冷 / 热写进契约

```
COLD   identity → measure → evidence → compile → render
HOT    identity → evidence → release
```

* HOT 的含义是**这一轮没有重做任何测量、编译、渲染**；成立的前提是每一步都有凭证。
* 凭证不足 → 该步自动落回 COLD 并写下原因（`cold_reasons`），不允许静默重做。
* 判定（guard / QA 结论）永远当场执行：判断必须新鲜，它不是可复用的证据。
* 新增步骤的准入问题：**属于 COLD 还是 HOT；为什么 HOT 需要重做。**答不出「为什么
  必须重做」的步骤，就不属于热路径。
* 账本自带契约自检（HOT 缺凭证 / COLD 无原因都会显式暴露）；`time_check` 直接打印
  本轮是 HOT 还是 COLD、以及每条复用凭证。

### 四、修掉一个假账（v6.1 引入）

逐页缓存命中**全部**页面时，证据里 `rendered` 键根本不存在，而统计写的是
`stats.get("rendered", len(paths))`——默认值把「这一轮一页都没画」记成了「全都画了」。
所以「改一页只重画一页」的账目在最省的那一轮反而是错的。现在页号清单是唯一事实来源：
本轮画了哪几页、哪几页命中上一轮，逐页可核对；整份预览证据复用时另记 `produced_by`
（这份证据当初是怎么产出的），不再冒充本轮的劳动。自检补上「全部命中时不许报成「都画了」」。

### 五、验收

- 自检 **198/198**（同一项数：本轮扩充既有回归项，不新增条目）。
- 基准脚本 qc_equivalence（交付工作区 bench/ 下）：退出码 0，fast 与 strict 在全部阻断性判据上一致。
- 15 页基准稿：`out.pptx` 5,361,497 B / `cdfa858160f3d327…` 未变（`--speed strict` 产物按档位不同：5,234,611 B）。
- 同一工作负载的字节账未变（与 6.1 的首次交付同量）：首次交付 68.3 MB 哈希 / 4 次解码 25.1 Mpx；
  热路径 2.2 MB 哈希 / 0 次解码 / 11 个文件各读一次。
- 耗时（基准脚本 time_check，交付工作区 bench/ 下）：`--speed fast` 首次交付 2.3 s · 只改稿子
  （资产未变）1.7 s（预览 0 页重画、4 页命中）· 同一稿子再交付 **61 ms（HOT）**；
  `--speed strict` 首次交付 6.5 s · 再交付 107 ms（HOT）。

### 六、量过但不做（有意的）

- **python-pptx 内部的 10.4 MB sha1**：本次查清归属——`pptx` 自己的图片去重
  （打包时 `get_or_add_image_part` / `_find_by_sha1` 调 `ImagePart.sha1`），不是我们的重复劳动；
  只能改库，不做。
- **严格档逐资产 sha256（50.3 MB）**：严格档的定义就是「整文件核对」，不是重复测量。
- **QC 判定复用轮多出的解码**：没有测量就没有解码种子，编译与预览各自解一遍是必要劳动
  （COLD 的定义）。

## 6.1.0 · Runtime Subtraction（运行时减法：同一份事实只做一次）

这一轮**不删能力、不删判据、不删上下文**，只做一件事：把一次 `check` 里重复发生的
工作拿掉——同一份 JSON 读一遍、同一批字节哈希一遍、同一张图解码一遍、同一页重画一遍、
同一份证据重写一遍。判据同样是一个问题：**这件事在这一次运行里是不是第二次做？**
输出字节不变是验收条件（基准 15 页稿的 `out.pptx` 摘要跨 5.9 / 6.0 / 6.1 三轮未变）。

### 一、读一次、哈希一次（把「读一次」从解析层补到全链）

| 改动 | 之前 | 之后 |
|---|---|---|
| 清单 / 计划 / 编译缓存元数据 | 同一份 JSON 一轮读 3 / 3 / 2 遍 | 各 1 遍（`primitives` 的读一次入口键归一化：相对路径与绝对路径指向同一份就认同一份） |
| 资产字节哈希 | QC 一轮算 4 遍（208 MB） | 1 遍（68 MB；其中 50 MB 是资产、10 MB 是 python-pptx 内部 sha1、7 MB 是产物） |
| 摘要传递 | 各层各算 | QC 算一次，核验 / 编译投影 / 发布证据共用同一份（`digests`） |
| 判定可复用的资产 | 仍重算摘要 | 沿用上一轮那份摘要（复用的前提正是字节身份一致；严格档的整文件核对也用它，不再算第二遍） |

### 二、资产 QC 判定复用（快路径不是漏检路径）

上一轮判定可复用的前提写进报告：同一份清单 `manifest_sha256` + 同一像素口径
`pixel_profile`（含档位与 `max_side`）+ 同一阶段 + **判定实现指纹** `qc_engine`
（`asset_prompt.py` 的摘要——阈值或口径一改，旧判定立即作废）+ 每个资产的字节身份
（`file_size` + `file_mtime_ns`；严格档再加整文件 sha256）+ 判定输入 `qc_inputs`。
任一不成立即回到完整测量。报告写明 `reuse: {assets, witness}`，复用项标 `qc.reused`。
实测：冷 2790 ms → 复用轮 55 ms；换一张图 → 3 复用 / 1 重测；改 `safe_area` → 不复用。

### 三、渲染不重画（逐页缓存）

预览按「页」而不是按「稿」缓存：页的身份 = 内容 + 画布 + 主题 + 渲染口径 + 渲染器指纹
（`pages/<key>.png`，上限 96 页，按 mtime 淘汰）。改一页只重画一页；渲染口径（超采样 /
压缩）或渲染器一改，键就变，旧像素不会被冒充。联络表是页图的纯函数——页图没变时直接
复制上一轮那张（**复制而非重存**：交付字节与上一轮完全相同），严格档 15 页实测省约 1.1s。
证据里写明「这一轮画了几页 / 命中页缓存几页 / 联络表是否复制」。

### 四、解码一次（核验解过的底图交给预览与编译）

像素核验本就要把出图解一遍（判亮度、纹理、安全区）。这一份**已解码底图**现在直接交给
下游：编译器不再解第二遍，预览也不再为了往 640×360 的页面上贴一张 4K 图解第二遍。
交接键是解析后的源路径，与「字节快照」同一套身份；超出持有上限或需要 EXIF 转置的
（PNG 的 eXIf 排在 IDAT 之后，查它等于整幅解码——预览与编译器都不做转置，两者一致）
一律落回原路径。实测：全量预览的真解码从 9 次 / 59.6 Mpx 降到 **4 次 / 25.1 Mpx**，
恰好等于源图总像素——一张图一次，没有再多。像素逐字节一致（自检钉住）。

### 五、证据不重写（时间戳不再说假话）

全部判定都是复用的一轮，引擎不再重写 `asset_manifest.qc.json`：文件上的 `checked_at`
回答的是「这些像素什么时候被量过」，不是「谁什么时候读过它」。重写会把时间戳刷成
「刚量过」，顺带改一次 mtime，逼下游把没变的字节再读一遍。显式指定输出路径
（`vao assets --out`）时照写不误。

### 六、写入者保证凭证前进（修一个真实缺陷）

文件系统时间戳粒度可能粗到毫秒级（本容器实测 4 ms）。同一刻度内的两次写盘会拿到
**同一个 mtime**，而全库的「字节变了吗」凭证是 `size + mtime_ns`——于是自检里那条
「读一次」用例每隔一次失败（实测 5 次跑挂 3 次）。修法在唯一写入口
`primitives.py` 的 `json_write`：写盘后若 mtime 没有前进，就把它推到 1ns 之后。不是伪造时间，
是让两次真实写盘可区分；推不动就退化为按内容重算，绝不因此让写盘失败。

### 验收

- 自检 **198/198**（186 → 198：本轮新增 12 项运行时自检，最后一组是「同刻度内重写也
  立即重读」「预览复用已解码底图且像素逐字节一致」「联络表是页图的纯函数」）。
- 基准脚本 qc_equivalence（交付工作区 bench/ 下）：fast 与 strict 在所有阻断性判据上一致（退出码 0）。
- 15 页基准稿：`out.pptx` 5,361,497 B / `cdfa858160f3d327…` 未变（`--speed strict`
  产物按档位本就不同：5,234,611 B）。
- 耗时（同一台机器，冷/热对照用基准脚本 time_check（交付工作区 bench/ 下））：`--speed fast` 首次 2.1–2.5 s
  → 复跑 **55–63 ms**（编译 0 ms、预览证据复用、QC 判定复用）；`--speed strict` 首次
  6.2–6.4 s → 复跑 100 ms。哈希总量 208.3 MB → 68.3 MB（冷）、192.5 MB → 2.1 MB（热）。

## 6.0.0 · Subtraction & Judgment（结构化减法：让引擎停止给作者判卷）

这一轮只做三件事：**删掉没人消费的东西、合并重复表达的规则、把该由设计判断完成的事
交还给设计判断**。判据是一个问题：删掉它，最终结果会变差吗？答"不会"的一律删除。
判断层（guard 的硬门、route 的路由、design intelligence 的算子）**一条能力都没减**。

### 一、引擎不再用自己的第二套命名给作者判卷（真实缺陷，不是风格问题）

1. **眉标/页码：只查「有没有落」与「位置稳不稳」，不再比对字面。** 此前 guard 要求
   眉标文字必须与 plan 发放的词汇表逐字相同，于是作者写自己的说法（往往更贴内容）
   会在每一页被警告一次——15 页 deck 实测 **25 条警告**，把真正该看的信号（版面碰撞、
   行长超限）整个淹没。锚是导航：**在不在、动没动**是工程事实；**写什么词**是设计判断。
2. **家族词表改为「能被解析就算数」。** 照 `templates/brief.yml` 写 `family: cover` /
   `data` / `case` 的作者，此前会被逐页警告 15 次"不在合法取值内"——引擎认识的写法
   不认自己的文档。现在 route 家族、媒体模型命名空间、别名、brief 内容类型四种写法
   全部解析为合法；只有**谁也解析不出来**的词（拼错）才留痕，且按值去重。

两处合并后：15 页基准稿的留痕从 **40 条降到 5 条、4 个信号降到 3 个**，
修复包 `trace_summary` 从 1505 B 降到 **599 B**，剩下的三条全部是真问题
（行长超限 ×2、眉标与页码重叠 ×2、页码落位不统一 ×1）。

### 二、删除「引擎发明、无人读取」的字段与层

| 删除项 | 规模 | 为什么 |
|---|---|---|
| `empty_space_role`（留白职责） | 1 字段 × 每页 + 1 条校验规则 | route 发明、骨架填写、guard 校验合法性——**没有任何消费者**。它让作者在假字段上做假决定 |
| `rhythm_stage`（开场/正文/收尾） | 1 字段 × 每页 | 同上：写了没人读，只是骨架里多一行 |
| `reading_order` | 1 字段 | 就是 `focus` 的复述，两处写同一件事必然分叉 |
| `forecast_risk` 风险预测层 | 65 行 + plan 字段 + 文档 | 输出 `risks/policies` 全库无人消费；plan.json 正常流程不读，等于**预测了但没人听** |
| `EMPTY_SPACE_ROLES` 常量 | 1 表 | 随字段一起消失 |
| `strategy: {}` 空壳占位 | 骨架 1 行 | 骨架里的空 promise（无代码读取），只会让人去填它 |
| 重复的 CJK 判据 | 2 份实现 | guard 与 ghost 各存一份且**范围不一致**（0x3000 起 vs 0x2e80 起）——同一字符在预览与治理里可能是两种字符 |

净效果：`plan.json` −6.6%，骨架 −5.7%（头注释再减约三成），页面骨架的待填字段
从 7 个降到 5 个，其中真正需要判断的只有两个：`insight`（这页唯一结论）与 `focus`（第一落点）。

### 三、规则去重（不降门槛）

- `min_font` → 并入 `typography`：同一件事（文字可读性）不再有第二个规则名。
- `theme_fonts` 4 条 deck 级提示 → **1 条**（同一事实一次性说完，缺什么写什么）。
- `metric_consistency` error/warn/hint 三条 → **1 条**（同一指标的口径差异合并陈述；
  单位不一致仍是 error）。
- `page_contract` 的枚举点名保持 warn（"值不认识"是工程事实，不是"这页不合格"）。
- 规则名 **36 → 35**，调用点 **96 → 92**。

### 四、判断能力的两个升级（不是加规则）

1. **构图给备选，不只给起点**：骨架每页的构图意图现在同时列出**备选语法**
   （如 `语法=scale_contrast，备选 figure_ground，可推翻`）。判断需要选项——
   只给一条时，读者只能照抄；给了两条，读者才真的在做选择。
2. **待填槽位收敛到「一句结论 + 一个落点」**：删掉三个假字段之后，页面的设计决定
   只剩两个必须由人回答的问题，判断被迫集中在真正重要的地方（One Slide, One Idea）。

### 五、验证

离线回归网 **186/186 通过**（含两条新断言：brief 家族写法不得被误报；骨架必须带
构图备选与字段查表）。基准稿 release **PASS**，产物与改前**逐字节相同**
（sha `cdfa8581…`，5,361,497 B）——判定口径没有松动，产物的字节也没有变。


## 5.9.0 · Two-Minute Delivery（把秒级引擎从等待里解放出来）

动机是一条硬指标：**完整 PPT ≤120 秒收口（不含外部出图）**。在此之前，15 页 / 6 张
4K 图的一轮完整交付里，本地链路要花 ~10.7s：其中 85% 花在**重复劳动**上——
同一张图被反复解码、写到临时 PNG 再读回、整包 ZIP 二次压缩、全分辨率像素扫描、
全 deck 逐页 2× 超采样预览，以及同一份 PPTX 被哈希两次。

本轮**不删任何设计能力**：guard / route / design intelligence / 判断层一行未动，
新增的只是一个贯穿全链的速度档与预算纪律。

### 一、速度档（`--speed fast|strict`，默认 fast）

| | fast | strict |
|---|---|---|
| 资产 QC | 长边 ≤1024 整数箱降采样；**文字安全区纹理仍按原分辨率** | 全分辨率 |
| 编译缓存探测 | size + mtime_ns | 整包 SHA-256 |
| 方向预览 | 采样 ≤4 页（封面/最复杂页/图片页/收尾），单倍采样 | 全 deck 逐页，2× 超采样 |
| 产物哈希 | 同轮 stat 见证一次 | 同 |

实测（15 页 · 6 处图片 · 4 张 4K 源图 · 冷缓存）：本地链路 **10.74s → 2.70s**；
strict 档同时从 10.74s 降到 6.41s（结构性优化对两档都生效）。
单看各阶段：资产核验 1.50s → 0.73s，编译+证明 4.45s → 1.20s，方向预览 4.66s → 0.66s。

### 二、删掉的重复劳动

1. **图片只读一次、只解码一次**。资产核验读到的字节写进 `snapshots`，资产链核验、
   编译器、方向预览共用同一份不可变字节（此前 QC 读一遍、核验再读一遍）。核验为了
   判「文字压在什么纹理上」必须解码整幅 4K，这份**已解码底图**随即交给编译器
   （所有权转移，`decode_seed`），编译期不再把同一张图解第二遍；核验内部也不再为了
   原生分辨率安全区把同一个 blob 解两遍。持图有确定性内存上限（48Mpx / 8 张），
   超限就不交底图、下游照旧从字节解码——快路径只许更快，不许把内存变成新的失败模式。
   快路径带 size+mtime 守卫：文件被换过就老实重读/重解，快路径不允许成为漏检路径。
   实测：同一份 PPTX 由「核验底图」编出来与由「字节重新解码」编出来**逐字节相同**。
2. **图片变换不再过磁盘**。`_fit_image` 写临时 PNG 再交回 python-pptx 的做法删除，
   改为进程内 bytes 直传；同一张图在同一盒子里只变换一次，跨盒子复用已解码底图，
   无变换时直接透传原字节（比例一致、不需放大、不超采样时）。4K 源图解码 + 重采样
   是唯一无法避免的成本，其余都省掉了。
3. **包级后处理不再二次压缩媒体**。PNG/JPEG/字体条目按 STORED 直存（它们本就不可
   再压缩），XML 仍走 DEFLATE；时间戳归零与 outerShdw/空 run 清理保持不变。
4. **方向预览不再逐页超采样**。`sample_pages` 按方向采样（封面 / 最复杂页 / 图片页 /
   收尾），单倍采样、低压缩 PNG、contact sheet 直接用内存页图（不再写盘再读回）。
   采样是**声明的证据范围**（`scope` / `sampled_ids`），扫码即核对，不冒充全量覆盖。
5. **产物字节只证明一次**。发布清单优先采信同轮见证的 size+mtime（未变即不重算）；
   stat 一旦不一致就回到整包哈希。缓存快探针同理。缓存另按**档位分域**：fast 与
   strict 编出的字节口径不同（PNG 编码级别），跨档位不复用，否则清单里的 `speed`
   会与产物的真实出身对不上。
6. **成功路径不再先写一份假失败**。`run_check` 曾先构造 BLOCKED 报告、写 repair
   packet、写 manifest，再执行真正的检查并覆盖它们。现在只在真失败时落盘
   （失败仍然 fail-closed，且会覆盖上一轮的 PASS 清单）。

### 三、判定口径没有放宽（可验证，不是声明）

- 安全区纹理判据回到**原生分辨率**测量（箱式降采样会抹平细密颗粒，而那正是压字
  最直接的风险）；等价性探针用六类「应当失败的图」逐条对比两档结论：干净 / 安全区
  过亮 / 硬缝假留白 / 主体贴边 / 结构化主体侵入 全部一致。唯一差异是
  **有意的**：均匀像素噪点不再被判成「主体侵入」（假阳性），同一张图仍被
  `text_safe_area` 阻断。
- 资产 QC 报告写明 `qc_scale` / `qc_domain`；预览写明 `scope`；编译报告写明
  `attestation_mode` 与 `performance`（变换次数、复用次数、编码与打包耗时）。

### 四、预算纪律（Agent 侧真正决定成败的地方）

`--deadline`（默认 120s）是本次调用的墙钟预算：核心阶段永远执行，可选证据在剩余预算
不足时被跳过并记入 `budget.skipped`；release 档缺预览证据如实记为不可交付。
`SKILL.md` §21 给出两分钟生产协议：一次规划 + 一次收口、单轮写完整个 deck、
warning 按根因批量修一轮、不运行 `selftest.py`、不预载全部 reference。

### 五、验证网 166 → 186 项

新增 `check_speed_profile`：档位默认值、QC 像素域留痕与原生安全区判据、无临时文件、
同图变换/解码复用计数、产物确定性、采样范围可核对、预算跳过留痕、发布清单证据范围、
QC 字节身份记录。全部为行为断言（读报告与产物），不锁实现。


## 5.8.0 · Structural Subtraction（结构化减法：删掉复杂度，不是删掉能力）

第六轮深度审计按用户当面指令执行：**删除 → 合并 → 简化 → 复用 → 最后才是新增**，
禁止为了"优化"增加系统复杂度。判断依据是四个问题：删掉 20% 代码，质量会下降吗？
删掉 30% 规则，设计判断会下降吗？删掉 30% context？减少 30% 调用？答"不会"的，
继续删。

### 一、四处同义判断合并成一处

1. **资产核验并回 `check`**。`vao.py asset-qc` 曾与 `check` 两步执行同一件事（绑定清单 →
   核验图片 → 给结论），两步之间必然漂移：`check` 拿到的是一份可能过期的 QC 报告，
   而"缺图/待重试/阻断"要在两次调用里各解释一遍。现在 `_asset_qc_report` 是 `check`
   内部的一步：一次执行完成绑定、核验、结论，`workflow.qc` 直接汇报状态与分组；
   独立命令、独立 `--advisory`/`--json` 参数与重复的摘要输出一并删除。
   缺图归入 `pending`（"还没生成"），不与"图不合格"混为一谈。
2. **验证层不再改写 spec**。Smart Fit 阶梯（`design_intelligence.apply_fit_ladder` +
   `_est_overflow` + `qa._has_auto_fit` + `result["auto_fit"]`）整套删除：它替作者把
   padding→0、line-height→1.05、字号 -2px 递降，直到"能塞进框里"。这与本包的核心纪律
   直接冲突——**字号是设计判断，不是布局的奴隶**；验证只回答"能不能交付"，
   溢出就报 `TEXT_OVERFLOW` 并点名元素，改法是加框高/减行数/删字，由作者决定。
3. **编译器不再复算 guard 已判定的事实**。`compiler.add_text` 曾自己再估一遍行数与高度
   并发 warn——同一事实两处判断，两处都可能漂移。容量现在只在 guard 的 `text_capacity`
   判一次（error 级、带元素 id）；`qa.py` 里"从编译 warning 反推 TEXT_OVERFLOW"的兜底
   随之删除。
4. **网格偏差检查删除**。`normalize_spec` 已经按 `grid_unit` 吸附坐标与尺寸，
   guard 再逐元素查一次"偏离 8 网格 N px"是同义兜底，只会把作者的合法微调报成提示。
   网格只有一个真源：归一化。

### 二、规则名 43 → 33（-23%）：消失 10 条，新增 0 条

`focus_scale`（焦点字号）、`organic_layer` / `asset_contract` /
`overlay_opacity`（幽灵资产引擎契约块：读的是编译器从不读取的元素级字段）、
`grid`（含"推荐 12 列 / 8 单位"两处值建议）、`optical_alignment`（色块-文字光学校准，
含 45 行 helper）、`overlap_declared`（已声明遮挡提示）、`focus`（未声明焦点提示）、
`geometry`（非数值坐标的告警兜底——`element_schema` 已以 error 级拦截，实测确认）、
`theme_constraints`（双名合并进 `theme_constraint`）。另删 `safety` 的两条边距提示
与 `page_contract` 的字段缺失提醒（error 级与值校验保留）。
判据只有一条：**它能否明显提升最终结果**。看不出来、AI 自己就能判、或只是把某个偏好
写进门槛的，删除。同时删除随之失去消费者的旋转钮（`grid_bias` / `safety_min`）、
常量（`CHART_FLAT_RATIO` 保留：它守的是"差异看不见"）与死 helper。

### 三、三条旁路删除

- `--advisory`（check/run）：设计诊断开关；`include_advisory` 参数、`DESIGN_RULES`
  白名单、`advisory_rules` 返回键、`§3.1 资产引擎契约`校验块（读的是编译器从不读取的
  元素级 `asset` / `organic_layer`）全部随之删除。验证层的判据只剩两类：**工程事实**
  与**作者自己写下的数字**。
- `--polish`：第三套修复指令（打磨手册 15 条 + `_polish_plan`）。修复包已经有唯一的
  指令通道 `fix_plan`，再挂一份"改了更好看"的清单只会让作者为了消掉提示改设计。
- `vao.py doctor`：依赖自检；`pip install -r requirements.txt` 已经会明确报错。

### 四、其它

- `estimate_tokens`（无人消费的体积提示）删除；`README`/`SKILL`/`references` 同步：
  命令表 7→6、生产顺序 4 步、`check` 说明含资产核验。
- 命令数 7→6；`check` 的参数少 3 个；scripts 总量 13092→12569 行（-4%），
  guard.py 2254→1956 行（-13%）；回归 **166/166 PASS**，三页 demo 全链 release PASS。

### 五、下一轮待办（未完成，不在本版）

压缩 context 层（SKILL.md 与 references 的重复表）、`route.py` 与 `asset_prompt.py`
的深层结构审计、以及"每页一次核心判断"的判断层复核。

## 5.7.0 · Asset Role Separation（背景图与插图的职责边界）

一次图像排查暴露的问题不是缺字段，而是**职责边界没建立**：`background_scene`、
`asset_function`、`asset_subject` 三者各说各话，`hero / proof / emotion / context /
frame / separate` 只定义了「资产用途」，没有告诉任何人**背景图是「承载页面空间」的资产，
插图是「表达页面对象」的资产**——两者不能用同一套生成与编排逻辑。于是必然出现：
背景图被当成一张大插图（被要求明确主体、被抠成透明剪影），插图被当成背景纹理
（被要求整块低密度、被融进版面底色）。

更硬的一层是代码：`asset_type`（真正的执行类型）**从未出现在 brief 契约里**，
于是 `vao._asset_page` 对每一张资产都取默认值 `background`——作者写 `asset_subject`、
写 `medium`、写 `asset_function`，全都改变不了「这张图会被当成背景资产处理」这个事实。
写得等于没写，没有报错、没有痕迹，只有产物不对。

**唯一的新概念：`asset_role`（两轴模型，不是第三个枚举系统）**

```
                    为什么存在？（asset_function）
                Hero   Proof   Emotion   Context   Frame   Separate
 什么类型？      │       │        │         │        │        │
 Background ─────┼───────┼────────┼─────────┼────────┼────────┤  建立空间
 Illustration ───┼───────┼────────┼─────────┼────────┼────────┤  表达对象
 Hybrid ─────────┼───────┼────────┼─────────┼────────┼────────┤  两者确实兼有
```

- 逐页 `asset_role: background | illustration | hybrid`——`asset_role` = 它**是什么**，
  `asset_function` = 它**为什么存在**，`asset_subject` = 画面里**具体出现什么**，
  `background_scene`（deck 级）= **页面背景世界**。四者职责不得混淆。
- 刻意**不新增** `background_hero` / `illustration_context` 一类组合枚举：组合就是两轴
  相乘，摊平成表就是把设计智能重新做成组件系统。
- 角色不许被用途偷换：`asset_role=background` ≠ `asset_function=hero`（背景再漂亮也不会
  自动成为页面主角）；`asset_role=illustration` ≠ 必须成为 hero（插图可以只是 `separate`）。
- 解析只有一个出口 `asset_prompt.resolve_asset_role()`：声明即 `declared`，旧 `asset_type`
  直写算 `legacy`，未声明记 `assumed`（默认 background，但与「作者说的」严格分开）。
  **未知角色值 fail-closed**——写了却读不懂比没写更贵，作者会以为它生效了。
  `resolve_asset_role` 不接受 `asset_function` 作输入：推导会把摄影主体变成透明剪影。

**生成纪律按角色分化（提示词层）**

- 背景：连续材质场 + 大面积负空间 + 不做主角；`negative_space_anchor` 承诺「干净的安静面」。
- 插图：独立视觉对象 + 明确轮廓/尺度/位置 + 与文字建立关系；锚点改为
  「主体让出这一侧给页面文字」，**不要求整块画面低密度**。
- 空间融合（fusion）改为按角色：`background`/`hybrid` 融进版面，`illustration` 保留自身边界
  （此前由 `asset_function` 决定——那正是「插图被当成背景纹理」的来源）。
- 插图遇已声明介质（photography / ink-wash / illustration …）时，透明剪影与
  「3D minimal illustration」风格预设让位给结构纪律——一张摄影插图不是抠图。
- 无安全区（版面不压文字）时，「让空间给文字」一类句式全部消失（插图同样适用）。

**QC 判据跟着承诺走（阈值一个没动）**

- `background`：不做主体裁切判定（空间资产的边界本就由材质与光填满），
  仍查可读性、连续性与负空间。
- `illustration` / `hybrid`：按具象主体判定（主体完整性、识别度、位置关系）；
  安全区**纹理密度**降为 advisory——插图的承诺是「与文字建立关系」，不是「整块画面
  保持低信息密度」，压字可读性由亮度对比与编排层保护负责。
- 未声明角色时沿用既有 `asset_function` 口径：新字段不放宽也不收紧任何一条旧判据。
  实测同一张「主体贴下边缘」的图：声明 `background` → advisory 通过，
  声明 `illustration` → 阻断。

**契约与文档（活的文档才拦得住错）**

- `templates/brief.yml` §03 重写为四步判断（需要资产？→ 建立空间还是表达对象？→
  为什么存在？→ 画面出现什么），并写明「`asset: required` ≠ 必须做一张主体图」、
  背景/插图各自的生成纪律、以及「不写 asset_subject 时不得凭 title 脑补具体对象」。
  §04 写明 `background_scene` 只管「页面背景世界」，不判断这一页有没有背景图。
- `SKILL.md` §12 改为 **Asset Decision ≠ Image Filling** + 四步链 + 两轴边界。
- `references/asset-workflow.md` §3 增加二维矩阵与「背景 / 插图编排区别」表
  （视觉密度 / 主体要求 / 文字关系 / 裁切 / 光线 / 细节 / 页面地位 / QC 重点 / 默认风险），
  §7 写明角色只改变「问哪几个问题」、不改变「不评分」；清单作业字段增加 `asset_role`
  （含 `asset_role_source`——出图的人要能看出这是作者说的角色还是默认假设的背景）。
- `references/design-system.md`（Image / 首轮设对：生成侧角色与编排侧 `layer` 要一致）、
  `references/design-intelligence.md`（四者职责）。
- 骨架每页注释带上作者声明的 `role=`，填空时就知道这张图是整幅承载还是立在栏内。

**刻意不做的事（防过度设计）**：不新增模块、不新增报告字段、不新增评分维度、
不新增 `asset_role` 之外的枚举，`background_scene` 不新增生成门（保持 deck 级世界声明，
判断归 Intelligence / Craft）。`plan`/`assets`/`check` 的命令行一条没改。

**验证**：`selftest` 155 → 165 项（新增角色分离 10 项：解析唯一出口 / 背景纪律 /
插图纪律 / 介质让位 / 融合按角色 / 空安全区 / 角色决定判据 / 插图纹理 advisory /
声明链与「用途不得推导角色」/ 契约文档在位）。全链烟测：brief → plan → 骨架 `role=`
→ 清单 `asset_role` + `asset_role_source` → asset-qc 按角色判定。

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
