# Changelog

仅记录行为差异、迁移事项与验证边界。已提交的详细历史见 Git；本次压缩前工作树副本随审计交付保存。

## 未发布 — 2026-10-16（基线 0422dc6；包版本仍为 9.33.0）

### 安全与交付完整性

- 拒绝 text 为 null/bool、非有限或越界 angle/opacity；编译写入点归一角度、夹紧 alpha、排序渐变 stops，避免非法 OOXML。
- brief/spec/manifest 拒绝展开超过 250,000 节点的文档，阻断 YAML 别名指数放大。
- 编译失败保留旧完整 PPTX，不发布半成品或为旧产物签署新成功凭证；release 先撤销旧 PASS。已知路径/链接别名预检、单文件原子发布与同轮资产字节快照继续保留。
- Guard/compiler 拒绝坏图表行、空标签与冲突载荷；旧 `data + categories` 输入仍兼容。坏缓存回落重建；盲评拒绝非法/漏评输入，导出不覆盖旧工作。

### 图像与设计兼容

- contain/cover 使用保持盒子比例的画布，修复小图拉伸失真；ghost contain 支持等比放大。
- QC/compiler/ghost 统一 EXIF 显示方向，旋转图不再透传未转置字节。
- 预览相对底图改为**按编译侧同序**解析（`[输出目录, 稿件目录]`，与 `compiler._resolve_src` / `primitives._media_stamp` 一致，vao 显式传入 `_image_roots`）：同名相对路径在两处各有一张图时，预览画的必须与产物贴的是同一张（审计实测两处根序分叉）。独立调用 `ghost_deck`（不带 `_image_roots`）保持 `_base_path` 优先的旧口径；pie 保持实心，仅 donut 族挖孔。
- 作者素材声明优先；对象不默认继承背景材质/光影。`asset_reason` / `asset_composition` 不触发配图额度；提示词缓存 v2→v3 重建，不自动删除旧图。

### 回归与 CI

- 五个案例 JSON 移至 `scripts/json/`；测试默认路径、CI 与文档同步，案例字节及冻结哈希不变。显式 `--cases scripts/文件名.json` 调用须改用新路径。

- 保留主集、r2、r3、r4 四组冻结案例（55 案例、134 断言），不改期望；CI 显式检查必需集存在，仍执行额外同前缀集，防止删除后静默漏测。
- CI 保留 Linux/Windows × Python 3.10/3.12/3.13 与 Linux 3.10 依赖下限组合；显式启用 UTF-8。
- 修正 selftest 对资产快照键和读图路径的比较，按 resolve 后身份核对；符号链接临时目录已复现旧测试误报。
- Linux 本地审计验证：selftest 637/637、bench 57/57；四组冻结断言分别 81/81、31/31、14/14、8/8。两页含图 strict 发布 PASS，干净样例 PPTX 与审计修复前字节一致；坏图等负例 BLOCKED exit 2。
- 远端历史 CI #64（e734d6a）为失败，Windows Regression suite 失败；公开日志下载要求管理员权限，根因未确认——**第二轮已定位并修复，见「Windows/CI 可移植性」**。本次改动尚未推送或完成远端矩阵验收，不宣称远端已变绿。

### 审计修复（同批，2026-10-16）

- **产物权限**：原子发布统一走 `primitives.atomic_replace`——`mkstemp` 的 0600 不再随 `os.replace` 变成产物权限（此前 plan/manifest/QC/缓存/预览 PNG/交付 PPTX 一律 0600，共享目录与 CI 收集 Permission denied；覆盖既有 0644 还会静默收窄）。目标已存在 → 保持原权限；不存在 → umask 默认，与 `open(path,"w")` 同纪律。
- **`--deadline 0`**：只有 `None` 才是「不限时」。此前 `not deadline` 把显式 0 秒预算静默升格为不限时，release 照常渲染预览并 PASS，而同语义的 `-5` 正确 BLOCK；现在 0 如实按「没有预算」处理（缺预览证据即 BLOCK）。
- **unit × show_values 死锁**：release 出处硬门要求数值图表写 unit，编译器却把「unit 在数值标签关闭时不可见」判为编译失败——两个门互相打架，唯一出口是强制打开数值标签。编译器不再拦截（只负责渲染）；guard 出非阻断告警 `chart_unit_invisible`，进发布清单 notes（标签按领域标注：可读域 / 单位可见性 / 非阻断）。
- **可修诊断**：坐标 bool（`x: True` 曾静默当 1px）与 `_positive_num`/`_finite`/`_alpha_ok` 同口径拒绝；canvas 超出 PowerPoint 可表达的 1–56 英寸（96–5376px，`SLIDE_MIN_PX`/`SLIDE_MAX_PX` 单源）给「整稿等比缩放」的可修诊断，不再透出 python-pptx 的裸 range 错误。
- 本轮复跑（审计修复后，Linux）：selftest 654/654（新增 17 条回归断言）、bench 57/57、四组冻结断言 81/31/14/8 不变；含图样例 release PASS 且 PPTX 字节与修复前一致（sha256 9c7bf5d0…）；SIGINT 中断不产出半成品、不留临时文件。远端矩阵仍未推送验证。

### 审计修复（第二轮，2026-10-16）

- **单张解码预算**：新增 `assets.QC_MAX_PIXELS`（1 亿像素，随 `qc_profile` 进 QC 档案）。`fast` 档只缩小统计工作域，原图仍要完整解码一次；实测本机 QC 峰值约 23–26MB/百万像素（4MP→142MB、9MP→243MB、16MP→417MB），一张 12000×12000（144MP）的图在 2GB 容器里把整轮 check 打到 OOM 被 SIGKILL——作者拿到的是「进程没了」。现在超过预算在**解码之前**（读 IHDR 后立即判）拦成可修诊断：「先降采样到预算内再登记」。线画在 100MP（8K 帧 33MP / 5000 万像素相机 50MP / 中画幅 100MP 都过）；Pillow 自身炸弹线为 178.9MP，其下的 89.5–178.9M 只警告不拦。该值是**策略线而非机器推导值**：内存受限的 runner 需自行调低（单源常量，QC 档案可见）。
- **资产失败原因直达修复包**：图读不出来（损坏/截断/超预算）时链路只报「无接受该图片的 QC 结果」，真正判词埋在 `results[].qc.issue`；现在把原始原因带进 `workflow_issues`（「图片不可用（…）」），作者不必再开第二个文件找根因。
- **字距越界**：`char_spacing` 以 pt 声明并写入 `a:rPr/@spc`，而 `@spc` 是 ST_TextPoint（±4000pt，1/100pt 计）。实测 `char_spacing: 1000000` 一路 PASS 并写出 `spc="100000000"`——非法 OOXML，PowerPoint 打开会进修复流程。guard 前置拒绝（可修诊断），`set_run_font` 按同一常量 `CHAR_SPACING_MAX_PT` 夹紧兜底。
- **目标线不再静默消失**：`target` / `target_label` 只由 `ranked_bar` 渲染，而编译器把转换异常吞掉——`target: "abc"` 的稿件 release 仍 PASS，产物里一根参考线都没有。现在非有限 `target` 由 guard 拒绝、编译器直接调用时也发声；其他 kind 上写这两个字段会得到 `chart_field_unconsumed` 告警（写了不生效必须留痕）。契约补记该字段的适用 kind。
- **提示词缓存键覆盖全部输入**：身份指纹刻意不含 `safe_area` / `text_color` / `ratio`（校准压字区不该让已出图改名），但 `build_asset_prompt` 读它们。按身份查缓存时，作者把压字区从左侧改到右侧再跑 plan，拿回旧提示词，而清单里的 `safe_area` 已是新值——清单与出图指令互相矛盾。`prompt_cache_key` 把提示词输入混进键（资产 id 与去重语义不变）。
- 本轮复跑（第二轮修复后，Linux）：selftest 676/676（本轮新增 22 条）、bench 57/57、四组冻结断言 81/31/14/8 不变；同一含图样例 PPTX 字节与基线 `aa47e2f` 一致（sha256 9c7bf5d0…），墙钟中位 0.42s vs 0.41s（+1.4%，噪声内）；元素保真度探针 22/22、EXIF 方向 1–8 全对、不可信资产 6 类畸形清单全部 rc=2 无 traceback。远端矩阵仍未推送验证。

### Windows / CI 可移植性（第二轮，2026-10-16）

- **CI #64 根因确认**（原记录「根因未确认」）：`windows-latest` 的回归套件崩在 `test_deep_release`——它用 `os.path.relpath(blind_src, Path.cwd())` 构造相对路径，而 GitHub 的 Windows runner 工作区在 `D:`、临时目录在 `C:`，两棵根之间不存在相对路径：`ValueError: path is on mount 'C:', start on mount 'D:'`。测试死在 setup 而不是断言上。改为 `_portable_relpath()`：能相对就相对，做不到退回绝对路径（该检查要验的是「blind pack 不篡改传入的来源标识」，绝对路径同样成立）。本机用 `ntpath` 复现了该 ValueError，并让 `test_deep_release` 走兜底分支跑满 41/41；把助手换回原写法可复现同一崩溃（对照实验）。
- **Windows 没有 POSIX 权限位**：`test_atomic_publish` 原先断言 `st_mode == 0o644 / 0o664 / 0o600`；Windows 的 `stat` 只反映只读标志（`chmod` 之后一律报 `0o666`），这三条会在 Windows 腿误报。判据改成跨平台可证的形式——**覆盖前后权限不变**，数值相等只在 `os.name == "posix"` 时追加（检查数量不变，POSIX 覆盖不减）。
- **测试侧缺 encoding**：`selftest.py` 6 处 `read_text()` 读的是管线写出的 UTF-8 中文 JSON；未指定编码时，非 UTF-8 模式的 Windows（CI 之外的本机）会解码失败。补齐 `encoding="utf-8"`。生产代码经 AST 扫描确认没有同类问题（初筛 16 处 `open()` 全是 `Image.open`/zip 成员，非文本读取）。
- 本轮复跑（Windows 可移植性修复后，Linux）：selftest **680/680**、bench 57/57、四组冻结断言 81/31/14/8 不变、CI 的 spec 冒烟红线（禁 import pptx/lxml/compiler）本机逐字复刻通过。Windows 实机仍待 CI 矩阵验证，本地只做了条件模拟与平台文档级推论。


### 审计精简（本轮 Agent Mode）

- `vao.py`：骨架写盘前对目标文件的重复读取合并为一次（先读一次再比较），消除同一路径的二次 I/O。
- `primitives.py`：删除从未被任何模块调用的 `latin_word_match`（grep 全仓库无消费者），减法测试无质量损失。
- 本轮未改动判断基准、字段契约与测试期望；selftest 680/680、bench 57/57、四组冻结断言 81/31/14/8 全过。

### 审计修复（Agent Mode 续，2026-10-16）

- **`test_win_portability` 的错误前提**（Windows 腿）：「同盘符仍给出相对路径」拿 `tmp` 与 `Path.cwd()` 配对——windows-latest 的 tmp 在 `C:`、工作区在 `D:`，这对本身就是跨盘，恰好落进兜底分支，断言与前提相反（本机以 PureWindowsPath + ntpath 语义复现：该断言在目标平台上必失败）。同盘对改为**两头同根**构造（`work` vs `tmp`），并补一条 ntpath 同盘对的 Windows 语义断言；跨盘对仍用 ntpath 实错 + mock 复现。**生产逻辑未动**：`_portable_relpath` 的「能相对就相对」与 `blind_pack` 的「key 原样记录作者路径表达」保持原样。
- **数字与单位被「个」截断**：`_NUM` 的单位组把「个」当独立单位，「2.1 个点 / 5 个百分点 / 2 个季度」被解析成「2.1 个」＋游离汉字——主语量、判断理由与骨架里出现残缺量（审计实测：「提升 2.1 个点」的 lead 显示「2.1 个」，claim 理由写「数字「2.1 个」」）。「个」改为分类词＋计量名词同进同出（个百分点/百分点/个点/个季度/个星期/个小时/个人…），无名词跟随时仍是计数（「5 个」）。
- **目标/计划量冒充「当前状态」**：`_attributed_primary` 的同分末值与主张锚定不识别意图模态——「…2024 年 22%。计划：…目标把复捐率拉回 28%」的下降序列把 2025 目标量 28% 选成焦点，理由却写「是序列的当前值：先立住现状」（审计实测）。新增 `_INTENTION_MARK` 子句级情态判据，与条件从句同池出局：被申请的量（请批准…）不受限；整句都是意图时退回全体，不判空；「目标客户/目标市场/目标 PowerPoint/计划外支出」等复合名词不算意图标记。`number_roles` 的「当前状态（末值）」分支同步只在**现状值**里取末值。
- **计量短语在预览里被腰斩**：`ghost._UNIT_INNER` 原为手抄子集（漏「万美/方米/瓦时」及「个百分点/个点/个季度」的内部对），且 `_cjk_break_fix` 的单位回退只退一步——三字短语（「万｜美元」「个百｜分点」）单次回退后仍停在短语内部（fuzz 实测 width=264 断成「3,800 万｜美元」）。改为从 `UNIT_WORDS` 派生全部相邻对（删掉手抄子集），回退循环走到短语之外再由数字规则整体推下；`UNIT_WORDS` 补「个百分点/百分点/个点/个季度/个星期」。
- `intelligence._metric_of_clause` 的局部 `unit_head` 字符表更名 `unit_chars`，不再遮蔽从 primitives 导入的 `unit_head` 接口（名称冲突，无行为变化）。
- 回归新增 4 条断言（单位绑定 / 目标量不冒充现状 / 目标句回退与「目标客户」除外 / ntpath 同盘对）；删除 1 处无消费的测试内 import。
- 复跑（Linux）：selftest **684/684**（680＋新增 4）、bench 57/57、四组冻结断言 81/31/14/8 全部不变（冻结期望未动）；12 页中文代表性稿 release+strict PASS，PPTX 内数字-单位为 U+00A0 不断行空格（含「2.1 个百分点」）、原生图表可编辑、无越界、另存重开正常；spec 冒烟红线（禁 pptx/lxml/compiler）通过。性能对照（中位）：check 12 页 release+strict 68ms（持平）、plan 95→102ms（噪声带）、selftest 15.9→15.6s。Windows 实机仍待 CI 矩阵验证，本地只做了 ntpath/PureWindowsPath 条件模拟。

## 9.33.0 — 2026-10-15

- `resolve_chart_highlight` 统一序列/类别强调，类别强调写入原生 `dPt`；删除的 `series_highlight_index` 外部调用须迁移到返回 `(series_index, point_index)` 的新接口。
- matrix 坐标有限数硬门；修复临时包清理、空文本 split_runs、环心 KPI 预览、absent 归因及缓存写盘诊断。

## 9.32.0 — 2026-10-15

- 修正份额关系、逐数字主语、千分位与时间序列判断；同单位多数字不自动成为趋势。
- 区分作者主张、证据陈述与未决；不把标签数字升格结论、不补未知关系。冻结案例保持只读。

## 历史迁移索引

| 版本 | 关键差异 / 迁移 |
|---|---|
| 9.31–9.29 | 独立泛化与视觉证据分层；关系/主张纠偏；Windows 管道 UTF-8。移除旧验收工件，未提交产物不能从 Git 恢复。 |
| 9.28–9.25 | CHART_SPEC 单源；标签与容量契约、编译缓存跨速度档；删除未消费字段、候选与盲评通道。 |
| 9.24–9.22 | 页级修复定位；timeline 单位须写入实际绘制字段；图片由作者声明，无自动图位额度。 |
| 9.21–9.18 | 移除外部渲染链，生产入口收敛；判断/骨架瘦身；设计与结构证据分层。 |
| 9.17–9.15.1 | `plan --json` 返回摘要，完整判断读 plan_path；覆盖保护、发布凭证、多序列图例、截断门与 CJK SC 字面。 |
| 9.15–9.3 | 中文禁则、资产 QC、图像编码与字体性能、缓存/身份复用；历史图位配额不代表现行行为。 |
| 9.2–9.0 | 主张/角色与整稿回看；删除命名风格预设，QA 收窄为硬错误。 |
| 8.x–7.3.2 | 页级声明、修复包与 CI；合并判断/资产/验证入口；缓存及资产哈希链基线。 |

## 验证边界

- 代码测试、PPTX 结构、ghost 预览和真实 PowerPoint 显示/编辑验收相互独立；本环境未完成真实 PowerPoint 与专业视觉终验。
- 远端 CI 仅以实际作业结果为准；历史测试量、局部字节一致不代表所有稿件兼容或性能提速。
- Python brief/build 是可信作者代码而非沙箱；不保证同输出并发或敌对 TOCTOU。建议独立运行目录。
