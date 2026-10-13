## 9.14.0 · CASE_005 Cross-Case Reproduction & DNA Deposit（2026-10-13）

上一轮的结论（「契约齐全后 BUILD 侧迭代可从 4 轮收敛」）在本轮用**第二个真实
项目样本**复现验证：PPT_CASE_005 · 12 页高端巧克力 A 轮融资路演（Contemporary
Luxury × Editorial × Museum）。本轮**零生产代码改动**——只有 DNA 入库 +1 条与
CASE_005 全套产物，`selftest 186/186` 不变，`dna --check` 12 条 0 error。
这正是上一轮修复想要的证据形态：**代码不动，迭代次数自己降下来。**

### 跨案例对照（同链路、同纪律、不同项目）

| 环节 | CASE_004（修复前） | CASE_005（教训前置） |
|---|---|---|
| THINK | 2 次 plan（警告逼改标题/色彩映射） | **1 次 plan 零警告收敛** |
| 资产 QC | 2 轮出图 + 2 次校准 + 1 次翻面 | **2 轮出图（s01 首过；retry 全为真阳性）** |
| BUILD | 4 轮 check 收口 | **1 轮 release strict 一次收口 PASS** |
| 真全冷 | 1597ms（15 页 3 图） | **1398ms（12 页 3 图）** · 暖态 36ms |

- BUILD 的 3 处契约缺口（qc 比例判据、载荷两式、背景层豁免）在 CASE_005 里
  **一次都没有再触发**——上轮的 contract.md 两行契约与 qc 修复按预期消除了
  整类返工；剩余的出图轮次（2 轮）来自外部生成器的首稿构图质量（s02 密林虚化、
  s03 窗框结构压字），QC 全部判对、提示词按判据一次修正——这是必要成本，
  不是技能包缺陷。
- **DNA 入库 `image_page_contract_first`**（第 12 条）：图页三声明（压字区 /
  文字色 / 背景层）与复合图载荷契约前置，两个案例复现后按纪律入库——
  不再是「一条回归」而是有正反案例与量化对照的经验条目。
- CASE_005 产物经 ghost 联络表目检：≤4 色统一（米白/可可/旧铜金/橄榄绿）、
  图页文字全部落在声明压字区、数据图表单一高亮、跨页节奏
  editorial/asymmetric_tension/big_whitespace 交替成立。
- 诚实披露：同 CASE_004——沙箱无 Office 真实渲染层；图像为 AI 生成样本；
  盲评未做（单组产出无对照组）。

## 9.13.0 · CASE_004 Real-Project Ledger & QC-Loop Parity（2026-10-13）

上一轮定下的方向本轮执行：用**真实项目样本**（PPT_CASE_004 · 15 页高端红酒品牌
融资路演，Old World Wine × Quiet Luxury × 欧洲艺术馆）走完 THINK → 出图 → BUILD →
VERIFY 全链，把「BUILD 侧迭代次数」这个端到端最大变量第一次变成**有账本的证据**，
再按账本修掉真实返工源。**零新增模块**；代码只动 `vao.py` 一处判据 + 自测 +1 条
回归（186/186）+ contract.md 两行契约。

### 真实迭代账本（本轮实测）

- **THINK（2 次 plan = 预算内收敛）**：plan#1 逼出 3 个真实设计决策——话题式标题
  被拒判（警告正确：作者改写 2 个标题）、团队页 witness 判图被作者否决
  （`asset: none`，真实路演不放伪造人物照）、`brand_colors` 列表式映射把酒红放上
  ink → 作者改槽位式声明。plan 的判断面在把作者往更好的内容上推，不是噪音。
- **资产（2 轮出图 + 2 次声明校准，零对抗误报）**：第 1 轮 3 张全 retry——
  目视逐张核实：生成器把「负空间」画成平板色块（x=33% 画宽处 42 灰阶硬缝），
  **QC 判得对**。带判据重写提示词（负空间改由光衰减/失焦承载）第 2 轮摄影质量
  跃升，仍 retry——这次是作者没声明压字区，默认全高左带把真实纹理也计入。
  按 safe_area 声明校准（asset_id 不变，已出图不作废的承诺实测成立）s01/s02 即过；
  s04 两次收紧无效后裁图目检：判密的是**拱门弧线的明暗交界**——任何矩形落在拱门
  里都会被弧线切割。设计判断：文字本就不该压在弧线上，翻转为亮字压暗拱顶
  （`text_color: light` + 右侧压字区）→ accept。3/3 accept_with_advisory。
- **BUILD（4 轮 check 收口）**：#1 作者脚本作用域错误；#2 图页叠字未声明背景层
  （合规路径 `layer:"background"` ≥60% 豁免）+ s11 框高差 2.5px；#3 复合图
  （`steps`/`big_number_row`）读元素级 `data` 载荷而非 `categories/series`；
  #4 release strict 一次收口 PASS。
- **缓存效率（真实修复轮实测）**：BLOCK→修复轮 ghost 页缓存 15/15 命中
  （6ms，只重画变化的页）；QC 报告复用 3/3（264ms → 11.8ms）；输出被删 → 编译
  缓存 fail-safe miss 重编（正确）；暖态整包 41.8ms；**真全冷（15 页 3 图）
  1597ms**（load 5 + qc 264 + compile 709 + ghost 596 + guard 4）。

### 按账本修掉的三处真实返工源

- **qc 离线环同判比例**：`vao.py qc` 此前不把清单 `ratio` 传给 `image_qc`，
  比例判据在「出图迭代最短反馈环」里失明——实测后果是「qc 全绿 → check BLOCK」
  的无效往返（本轮作者亲历）。修复后 4:3 冒充 16:9 在 qc 环即被拦（实测+回归
  `qc: 离线环同判比例`）。
- **contract.md 补「载荷两式」**：数值图表 `categories + series`，复合排版图
  （steps/process_flow/timeline/big_number_row/matrix/architecture）元素级
  `data:[{label,value,desc?}]`——BUILD #3 整轮返工的根源是契约没写。
- **contract.md 补「全幅影像叠字」**：`layer:"background"` + ≥60% 覆盖是图页
  排版的合法路径，不声明即 OVERLAP——BUILD #2 的 12 条碰撞告警源于此。

### 设计验收边界（诚实披露）

15 页成稿经 ghost 联络表 + 关键页单图人工目检：世界统一（米白/酒红/旧铜金/
炭黑 ≤4 色）、编辑排版与大留白成立、图页文字全部落在声明压字区内、数据图表
单一高亮 + 直读标签、s03 低产高亮论证方向正确。**未做**：PowerPoint 真实渲染
（沙箱无 Office）、第三方盲评；B 端文与图像为 AI 生成样本，非授权实景素材——
交付前需作者按 contract 完成第三、四层证据。

## 9.12.0 · Image Chain Measured & Encoding Unity（2026-10-13）

本轮先补齐一块从未测量过的证据：**含图稿的端到端基线**（6 页 3 图、16:9、strict）。
测量暴露的真瓶颈：含图 compile 1146ms（无图稿 265ms），其中 `_encode_png` 占 883ms
——`compress_level=1 if speed=="fast" else 6` 正是 9.10.0 在预览上删掉的**双口径**：
照片内容按 level 6 重编码，每张多付 ~400ms 只换 ~15% 更小的体积，解码像素完全相同
（PNG 无损）。**零新增模块、零新增规则、零新增检查层**；运行时只动 `compiler.py`
一处口径 + 文档，自测 +1 条回归（185/185）。

- **图片变换编码口径唯一（PNG level 1）**：与 9.10.0 同判据——证据与产物的效力
  在像素，不在压缩比。`_fit_image_bytes` / `_encode_png` 的 `speed` 参数随之删除
  （唯一消费者就是这个分支）。实测：含图稿全冷 **1752ms → 1201ms（−32%）**
  （compile 1146→595）；QC 报告温态再跑到 ~1100ms。
- **正确性对拍（双口径）**：新旧产物内嵌 3 张媒体**解码像素逐位一致**（文件字节
  因 zlib 级别不同而不同：2555KB → 3029KB，+18.5%——用体积换时间，诚实披露）；
  无图两夹具（12 页中文稿 + 富路径夹具）对上游 HEAD 的 PPTX **逐字节一致**、
  全部预览 PNG **解码像素逐位一致**（整栈 9.10+9.11+9.12 汇总验证）。
- **新不变式**：`media: 图片变换后 fast 与 strict 产物字节一致`——v5.9 起文档写明
  的「两条路径可见结果一致，差异只在耗时与字节」双口径在此收口，同 spec 两档
  编出**同一个** PPTX（实测+回归锁定）。
- **规模扩展性审计（新证据）**：36 页压力稿 plan 78ms（次线性）、冷态 check
  1269ms（compile 1.92×/ghost 2.82×/页数 3×，无超线性）；含图链的 QC 判据
  （安全区亮度、比例不符、retry 升级、防抖）在真实图上逐条实测有效——
  `qc` 离线体检不查比例而 check 查，为既有的口径分工，未改。

## 9.11.0 · Fast-Path rPr & Monotone Wrap Fit（2026-10-13）

同一固定任务（12 页中文董事会决策稿、7 次取中位、同机同条件）在 9.10.0 基线上
再测：冷态耗时仍集中在 compile（含 pptx 导入）与 ghost 两段，其中**段内第一热点**
分别是 `set_run_font` 的 XMLchemy 父链查找（~109ms/剖析）与 CJK 折行的逐字前缀
重复测量（`getlength` 1241 次 / 67ms）。本轮两项都以「输出逐字节 / 逐像素一致」
为前提收口，**零新增模块、零新增规则、零新增检查层**；自测 +1 条回归（184/184）。
实测：冷态 release **619ms → 513ms（−17%）**（compile 293→246、ghost 311→249）；
纯预览路径 **411ms → 348ms**；自 9.9.0 基线（709ms）累计 **−28%**。正确性对拍：
两份夹具的 **PPTX SHA-256 逐字节一致、全部预览 PNG 解码像素逐位一致**。

- **`set_run_font` 新建 rPr 快路径**：编译器创建的 run 恒为全新 rPr——子元素按
  OOXML schema 顺序直组（solidFill → latin，共享段补 ea → cs），属性按插入序
  直写（sz → b → i → spc），跳过 `get_or_change_to_solidFill` /
  `get_or_add_latin` 每次的 successor 链扫描（`_add_child` 1962 次、
  `first_child_found_in` 2217 次）。会触发 python-pptx 校验的输入（sz 越界 /
  非六位 HEX / family 为 None）当场拒绝或回退既有慢路径，失败语义不变；
  非 新建 rPr 一律走慢路径。产物逐字节相同（A/B SHA 对拍）。
- **CJK 折行二分拟合**：`visible_width` 随前缀长度单调不减（字形步进与
  tracking 均非负），「最长可容纳前缀」唯一——二分与逐字线性扫描找到的是
  **同一个断点**，被度量的字符串集合不同但每个判定上的谓词值相同，输出
  逐字符一致（600 组随机对拍进自测；4000 组仓外对拍含尾随空格 / 全角空格 /
  width=1 / tracking>0 边界）。文本测量从每行 O(L) 次调用降到 O(log L)，
  `getlength` 总耗时 67ms → ~20ms。**不采用**「按字符宽度累加」的近似方案：
  实测 PIL `getlength` 非可加（长行 ~3px 漂移），会移动断行位置——预览保真
  优先于速度。
- **回归**：`ghost: CJK 折行二分拟合与逐字贪心同断点`（内联旧线性参考实现，
  600 组随机对拍）。

## 9.10.0 · Preview Encoding Unity & pptx-Free Ghost（2026-10-13）

同一固定任务（12 页中文董事会决策稿、5 次取中位、同机同条件）先复测再动手：
冷态 release check 的耗时集中在 compile（含 pptx 导入）与 ghost 两段，QA/规划/缓存
段合计 <20ms，暖态 17ms——本轮只动测量出来的三处，**零新增模块、零新增规则、
零新增检查层**。运行时代码 3 个文件 +36/−17，自测 +2 条回归（183/183）。
实测：冷态 release **709ms → 619ms（−13%）**；纯预览路径（编译缓存命中、预览失效）
**561ms → 411ms（−27%）**；正确性以字节与像素双口径验证：两份夹具（12 页中文稿 +
富路径夹具：渐变/透明度/字距/斜体/大写/卡内文字/高亮柱图/负值/构成图/进度条）
编译产物 **PPTX 逐字节一致（SHA-256 相同）、全部预览 PNG 解码像素逐位一致**。

- **预览编码口径统一（PNG level 1）**：`strict` 此前按 level 6 编码证据 PNG，
  `fast` 按 level 1——同一像素两种文件口径。zlib 级别不改变任何解码像素（PNG 无损），
  level 6 只为每轮冷预览多付 ~70ms 换 ~10% 更小的证据文件；证据的效力在像素与
  见证（SHA-256/页缓存键照旧含编码口径，旧缓存自然失效），不在压缩比。
  两档统一为 1（`ghost_deck` / `make_contact_sheet` 默认值同步），12 页 + 联络表
  实测 338ms → 275ms。延续 9.9.0 的同一判断：预览在本尺寸回答方向问题，
  两档不该有两种口径。
- **ghost 彻底去 pptx 化**：`parse_token` 解析 #HEX 时经 `_p()["RGBColor"]` 把整条
  pptx 导入链（pptx.api → opc → oxml → xml.sax/urllib，实测 ~150ms）拉进 PIL 预览
  ——primitives 顶部注释承诺的「draft 进程零 pptx」契约实际从未成立，也没有那条
  `check_draft_import_contract` 自检。现在 `parse_token` / `fallback_ink` / 对比白黑
  在 pptx 未加载的进程产零导入等价对象 `RGB`（同 3 元组、str() 同为 'RRGGBB'），
  pptx 已加载（编译进程内）照旧产真 RGBColor——`*.rgb =` 边界的 isinstance 校验
  不受影响；等价对象只存在于没有任何 pptx 赋值路径的进程里。纯预览路径每轮
  省 ~150ms；冷态 release 不变（编译已付导入）。
- **set_run_font 直写 rPr**：python-pptx 的 `font.size / bold / italic / color.rgb /
  name` 每次访问都重走 run→rPr 父链与 ColorFormat 包装（大 deck 每 run 5+ 次）。
  改为一次 `get_or_add_rPr` 后按同一顺序直写 `sz/b/i/solidFill/latin`，写入序列与
  语义逐项一致，产物逐字节相同（夹具 SHA 对拍锁定）；编译段实测 −31ms。
- **导入契约第一次真的有测试**：`primitives` 纯预览进程零 pptx / lxml / compiler
  （子进程断言）+ pptx 已加载时 `parse_token` 必须产真 RGBColor（编译边界类型
  不变式），共 2 条回归。

## 9.9.0 · Measured Preview Cost & Two Judgment Corrections（2026-10-13）

先测量再动手的一次收口：固定任务（12 页中文董事会决策稿）上逐阶段计时，只改
测量出来的热点；**零新增模块、零新增规则、零新增检查层**。运行时代码 8 个文件 +77/−60（净 +17，其中一半是新增注释里的实测依据），自测 +64/−4（6 条回归）。
`selftest 181/181`（+6 条回归）。同一份 spec 冷态 release 检查实测
**1200ms → 866ms（−28%）**，其中预览段 795ms → 451ms（−43%）；编译段两档持平。

- **预览一次口径**：`strict` 此前按 2× 内部尺寸绘制再缩回，`fast` 用 1×——同一份稿子
  两档预览是两种渲染口径。12 页实测：2× 比 1× 多付 38% 的整轮预览时间
  （560ms → 256ms），像素差平均 |Δ|=1.96/255、>8 的占 4.4%，且**只有文本抗锯齿的权重
  差**（两张并排看同一张版式，几何/层级/留白/图形位置一致）。预览在本尺寸上回答的是
  方向问题，因此两档统一为请求尺寸直接绘制；`supersample` 参数保留给显式要高保真的
  调用方，默认值同步改 1。渲染器指纹含 ghost 源码，旧 2× 预览缓存自动失效，不会混用。
  预览证据不再宣称「已超采样」：`supersampled` 字段与 contract 表一起删掉。
- **两组变化并排不再顶掉作者写的结论**：`[本地从 12% 升至 19%，我方从 9% 降至 7%]`
  里有「变化词 + 两个数字」，此前在结论抽取里按主张计分，压过标题位上的结论句，
  焦点与整页排版跟着落到基期数字上。现在按形状判：**结论句／要决定的句子／比较措辞
  ＝主张（先判）；两组以上到达句并排＝证据表的一行**；单组「从 A 到 B」仍是关系句。
- **顺序形状由顺序词的数量决定**：三段里程碑 + 「总计 18 个月」的排期页此前被单个
  时长数字压成 `number`（骨架走大留白，页序当页码排版）；现在多个顺序标记叠加
  （0.60 → 最高 0.80），该页判为 `sequence` → `linear_structure`，骨架给的是流程位。
- **骨架不再留第二个「结论位」**：`page_intent` 从骨架 spec 里删除——结论已经住在
  骨架的判断注释里（`claim` / `focus` / `why` 全在上面），spec 里再写一遍就多出一个
  作者会去改、而消费方按设计不读的字段（缓存也排除它）。跨页锚 `anchor` 保留并
  **以判断对象上下文落进 spec**（`role=eyebrow` / `role=page_number` 的元素由此派生）。
- **修掉一个只在冷启动加缓存时才炸的崩溃点**：`assets.py` 的 `build_manifest` 读提示词
  缓存时调用 `json.loads`，但该文件从未导入 `json`——`--asset-cache` 一旦有缓存条目
  就 `NameError`。补 import，并加回归：第二次 `plan --asset-cache` 必须命中
  （`hits == 1`）且缓存文件 schema 正确。
- **删除无人读的东西**：`timing.cache_ms`（旧性能字段，零消费者，`cache_probe_ms` 是
  唯一真名）；`verify.py` 里对 `page_intent` 的类型检查（消费方按设计不读该字段）；
  `compiler.py` 的死局部变量 `media_written`；`verify.py` 未使用的 `import re`；
  `primitives.warn()` 从未被读取的 `element_id` 参数（元素身份已写进消息文本本身）；
  `selftest` 两处恒 False 的死三元。

## 9.8.0 · Cross-Platform Delivery & Judgment Determinism（2026-10-13）

以「先跑通再谈」为顺序的一次收口：CI 的 Windows 作业连续多轮全红（GitHub API：三个
windows-latest 作业全部停在 Regression suite），本版先修掉这条跨平台断点，再修掉几处
会让设计判断走偏的确定性缺陷。**零新增模块、零新增规则、零新增检查层**；
`selftest 175/175`（+16 条回归），Windows 与 Ubuntu 不再有行为差异。

- **中文输出不再挑平台**：`vao.py` / `selftest.py` 的 stdout/stderr 恒为 UTF-8。
  Windows 上 stdout 被重定向（管道 / CI）时 Python 用系统 ANSI 代码页，cp1252 下
  `print("plan: 5 页…")` 直接 UnicodeEncodeError、退出码 2、产物未落盘——这就是
  Windows CI 的根因。`run_vao` 读子进程也显式按 UTF-8 解码，不再依赖 `text=True` 的
  平台默认。回归：cp1252 / ascii 管道下 plan 必须退出 0 且产物必须落盘。
- **日期碎片不再冒充证据量**：「2026-09」里的 `-09`、「2026/03」里的 `03`、
  「2026 年 9 月」里的 `9` 都不再进证据（此前实测让排期页的权重卡出现「次 -09」，
  并虚高证据密度）。区间的另一端（38-92）与多段版本号（1.2.3）同样不出量。
- **出处标注不进证据扫描**：`understand()` 早已把「（来源：…）」当档案坐标剥掉，
  但数字扫描用的是原文，台账编号与日期仍会渗进证据数量。现在扫描与判断同源。
- **结论抽取不再由浮点噪声裁决**：两个「2.8 分」曾是 1.2+1.6（标题）输给 0.8+1.6+0.4
  （首句）——差在 4e-16 的累积误差。评分先量化再比较，同分保持候选顺序；
  标题带主张（判断/变化/数字）时它是作者写下的结论位，数字**列举**句不再顶替它。
- **风险色由主题派生**：六 token 够用的契约在含负值的图表上不再自相矛盾。
  `negative` 由 `derive_tokens` 机械派生（通用风险红向本稿墨色拉近），
  作者显式声明仍压过推导；含负值的图不再「首轮 check 被挡 → 补一个色 → 再跑一轮」。
- **预览诚实度可断言**：删除从未被读取的 `PREVIEW_MIRRORED`（它让「覆盖全集」看起来
  已被保证），改为断言「声明不渲染的类型 == 实际走占位分支的类型」，一一对应。
- **预览不再改写亏损**：横向条按**零基**编码（此前按最小值起算，最负的一条长度为 0，
  产物里却是一根可见的负向条），负值条落在零轴另一侧并染 negative 角色色——
  预览与产物第一次在「负值」这件事上说同一句话（6 页样稿实测 3.8% 像素改变，
  差异全部来自那一页的柱图）。
- **风险色与强调色必须分得开**：强调色本身是红时（最常见的品牌情形），派生风险色会与
  它撞成同一个读数；此时继续向墨色加深，直到 OKLab 距离 ≥0.12（对浅纸的对比度只增不减）。
  非红强调色不加深，避免把风险色做成一团黑。
- **构成图必须有名字**：图例是全局关闭的，甜甜圈/饼图此前只标数值——四个扇区就是
  四块没有名字的色块（作者构图时看不出哪一块是自有内容）。现在空间允许（≤6 类）
  时直接标类别名，预览同步（此前预览连数值也不标）。空间不够时退回「只有数值 +
  由作者用文字标注」的旧行为，不塞。
- **文档与实现对齐**：README 移除两个从未入库的审计文件链接（全历史 67 次提交中
  不存在），改为指向 CHANGELOG；pyproject 版本与 CHANGELOG 对齐；契约补
  `negative` 派生与「标题即结论位」两条；删掉 CLI 的 `preview` 子命令
  （SKILL 明说「不要再跑 preview」，README 却把它列为入口——Agent 读到就会跑一次
  重复渲染；selftest 现在锁住入口面恰好 plan/check/qc/dna）；删除 5 个零消费常量
  与其不成立的注释（AUX_TEXT_ROLES / GRID_UNIT / PREVIEW_MIRRORED / VISUAL_ROLES /
  _HEX_RE），把 judgment.md 与 SKILL 重复的「高级感」段落收成一处真源。
- **证据分层写进 SKILL**：代码测试 → 结构预览 → 真实渲染 → 专业视觉验收，
  四层各自的效力与边界写明（PASS 只覆盖前两层；测试通过不代表设计优秀）。
- 未改变：唯一入口、两个必跑命令、QA 的 PASS/BLOCK 二态、PPTX 原生可编辑性、
  Guard 阈值与失败码、DNA 条数（11 条，README 口径一致）。

## 9.7.0 · Declared Promise Drives QC（2026-09-24）

CASE_004（15 页红酒路演）端到端逆向审查后的生产性修复：把「作者声明」接通到它本该驱动的判据，删双口径、收敛经验，不新增规则与模板。

- **页级底色参与资产 QC**：brief 逐页 `background`（#HEX）进入 `_PAGE_DECLARATIONS` 透传清单；`_page_background_color` 使其成为亮度断崖判据的参照。暗色沉浸页不再被浅色纸面误判（此前声明在 spec 层存在、清单层丢失，判据与承诺脱节）。
- **指纹 v2**：`asset_fingerprint` 不再含 `safe_area` / `text_color`——二者是编排侧校准，由 QC 对成图复核；作者校准压字区不再使已出图作废（CASE_004 曾因此整体改名返工）。
- **text_safe_area 单口径**：fast/strict 两档统一走原生分辨率测量，删除「降采样域初值 + 原生覆盖」的双路径分歧。
- **证据不说谎**：ghost 的 ranked_bar 改走 `chart_primary_color` + `highlight_index`，与编译产物同一色链（此前硬编码强调色，预览替作者把答案色铺满所有条）。
- **stroke 容错**：`{"type":"none"}` = 显式无描边，dict 描边只读 color；不再把 dict 塞进 `paint()` 触发 unhashable 崩溃。
- **最短反馈环**：新增 `vao.py qc --assets-manifest`（复用 `image_qc` + `qc_retry_decision`，零状态、不消耗 retry），出图迭代不必跑全量 check 往返或自建 harness。
- **DNA 收敛 11→10**：`dual_chapter_tone_midpoint` 与 case004 条目合并为 `declared_promise_drives_qc`（页级底色 / 图像角色承诺 / 图表主色三处声明驱动判据）。
- 契约文档补「作者逃生口」六条（均为既有或本次接通的作者声明，非新规则）；brief 模板补 `background` 注释。

selftest 122/122；CASE_004 以升级后链路复跑 release(strict) 一次 PASS；`dna --check` 10 条 / 0 error。

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

