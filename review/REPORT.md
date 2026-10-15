# PPT Visual Art Director OS｜9.29.1 本地优化与验收边界

**日期：2026-10-15｜基线：`5bfb09a673f7e229e4e8fc5c558d92275f2dc846`｜状态：工作区已修改，未提交/未推送。** 这是一份实际改动与可复跑证据报告，**不是** PowerPoint 视觉验收证书，也**不是**修复后远端 CI 全绿声明。原历史记录见 `../audit/REPORT.md`；它关于“尚未推送”的描述只对应当时的审计快照，不能当成今日远端状态。

## 1. 范围、调用链与权威事实

从公共 Git 仓库克隆并读取/解析 HEAD 跟踪的 **410 个文件**（其中历史审计文件 381 个）：文本按 UTF-8、Python 解析 AST、JSON 解析、PPTX ZIP 校验；逐文件路径/摘要/类型见 [inventory.json](inventory.json)，复现程序 [make_inventory.py](make_inventory.py)。这代表**文件覆盖清单，不代表重新执行了 381 份历史审计产物**。重点追查 `SKILL.md`、两份 `references`、九个脚本、依赖/打包/CI、四组既有基准、七页 brief/build/out.pptx、审计报告/性能与 CI 记录。

生产链：`vao.plan → intelligence（内容/主张/角色/构图候选）→ assets（仅有图片时）`；`vao.check → verify → compiler/python-pptx → ghost/PIL（结构预览）`。`primitives` 持有颜色/字体/图表契约，`SKILL.md` 仍是唯一设计哲学基准；本轮未新增第二套原则、生产入口、依赖、模板或默认视觉参数。BUILD 的几何与元素由作者填充，**plan 不自动落版**。

## 2. 真实评分：按可验证成熟度，不按宣传语

| 七项目标 | 得分 | 扣分依据 |
|---|---:|---|
| 1. 设计哲学与艺术指导 | **17/20** | 原则明确、作者判断优先；从原则到实际作品的闭环不完整。 |
| 2. 语义理解与设计判断 | **16/20** | 修复既有 brief 的主张/关系错误；有限的内部固定集不能代表未见领域泛化。 |
| 3. 视觉美感与艺术指导 | **5/10** | 仅看过手工样稿的 ghost 结构预览，未见目标 PowerPoint 实际渲染或独立评分；这不是实际美感分。 |
| 4. 构图与版面组织 | **10/15** | plan 已把并列职责改为结构，但生成骨架没有元素；手工构图不能证明自动落版。 |
| 5. 中文排版与阅读体验 | **6/10** | NBSP 与结构检查有效；字体回退、中文断行和投影可读性尚无目标软件证据。 |
| 6. 跨页叙事与视觉节奏 | **8/10** | 有逐页职责及整稿回看；缺独立评价与多种实际生成作品。 |
| 7. 图表、图像与真实性 | **12/15** | 原生图表、清单和来源边界清楚；真实素材/最终显示尚未核验。 |
| **合计** | **74/100（阶段性）** | **衡量技能包可验证成熟度，不是作品视觉品质百分位。** |

分开看：**设计方法约 85/100；工程可靠性约 86/100（本地证据，远端待验）；真正自主落版约 20/100；真实成品视觉品质：`NOT VERIFIED`，不填虚构分数。** 与此前 78 分的口径不同：本次把“自动 BUILD”与“目标软件终验”列为显式验收项，分数不能直接当作退步或提升。 

## 3. P0 根因：为什么 Windows 的“负例退出 1”仍失败

当前公开 [GitHub Actions #54（基线提交）](https://github.com/cpikeo/ppt-visual-art-director-os/actions/runs/38668276721) 状态是 failure：Windows 3.10/3.12/3.13 的 `Regression suite` 退出 1，Ubuntu 三格与 smoke 的页面未显示同类错误。**无法查看三个 Windows 作业的完整原始日志，不能声称已在 Windows 本机亲自复现其堆栈。**

用 `PYTHONIOENCODING=cp1252` 在 Linux 上重现相同的管道编码边界：修复前，对故意错误的基准案例运行 `bench.py`，进程返回 **1**，但 stdout **空**、stderr 为 `UnicodeEncodeError`；所以原断言 `returncode == 1 and 'FAIL' in stdout` 失败。原先 `vao.py` 已有 `force_utf8_stdio()`，`bench.py` 的 CLI 却未调用它。修复后复用同一方法，负例仍返回 **1**，stdout 含 `FAIL`、`impossible` 和实际值，stderr 为空。保留了故意错误的期望值，**没有放宽负例或绕过测试**。[失败堆栈](baseline-cp1252.stderr) · [修复后 stdout](negative-cp1252.stdout)。修复后真实 Windows CI 仍需推送/PR 触发后确认。

## 4. 修改清单与根因、风险、对应回归

| 文件 | 根因 → 最小修改 | 收益 / 剩余风险与验证 |
|---|---|---|
| `scripts/bench.py`、`scripts/selftest.py` | bench 子进程的系统 ANSI stdout 使 Unicode 诊断中断；CLI 复用 `vao.force_utf8_stdio()`，自测强制 cp1252 并同时断言退出码/完整 stdout/无编码错误；保留原不可能期望值。 | 本地模拟通过，**Windows 实机未验证**。 |
| `scripts/intelligence.py` | 否定的“流程/比较”词被当成肯定关系；一个 `_affirmed_relations` 投影服务关系、流程与比较，不清除真实箭头/数据。`不得超过` 按阈值而非比较处理。 | 关系错误消除；复杂否定/反事实仍是启发式。J01/J04/J08 与原基准回归。 |
| `scripts/intelligence.py` | 标题明确断言却被短正文/数字顶替；复用变化谓语/对比断言识别并给予作者标题适度优先，条件句“若批准则…”不算请求。 | 样稿 s05/s06 的主张恢复；不是无条件锁死标题，仍需人工确认。J02/J05/J07/J09。 |
| `scripts/intelligence.py` | 粘贴表格的“主体\n负责\n对象”原文因换行拆散；仅在中间行为明确关系词时恢复同一关系句。 | s03 两条真实职责恢复为结构，不补上下级。反例 J12 避免补造。 |
| `scripts/intelligence.py` | 泛称“患者”被当作可指认证词，误判证明页并要求证词行；仅具体个体/可指认现场有证词资格。 | 样稿 s02 从 `prove` 改为 `persuade`；具体人物依旧可提示。J13 与原基准回归。 |
| `scripts/bench.py`、`benchmark/semantic_transfer.json`、CI | 原基准只比 claim 来源，不能发现“结论被正文顶替”；增加 `claim_text` 比对和 13 个语义/反例，CI 增加一条基准。 | 首批 10 项修复前 **3/10**、修复后 10/10；后加的 3 项是**曝光后的回归**，最终 13/13。全部为内部固定集，**不是独立盲测**。[修复前](baseline-semantic-10.log) / [当前](semantic-bench.log)。 |
| `README.md`、`CHANGELOG.md`、`pyproject.toml` | 手工样稿/空骨架边界与版本陈述需同步；本地版本置 9.29.1，明确不自动 BUILD、未远端验证。 | 防止把手工成品或旧审计日志当作新能力；尚未提交/发布。 |
| `review/` | 最小再现工具与证据落盘，不进入生产入口。 | 包含文件清单、性能原始样本、能力边界与结构证据。 |

**单一事实来源：** 没改 `SKILL.md` 的设计原则；图表规范仍在 primitives，字体身份/禁则/素材绑定与缓存契约未分叉。新语义测试并非第二套审美准则。

## 5. 验证结果、命令和环境

环境：本地 Linux、CPython **3.10.22 / 3.12.15 / 3.13.16**；运行时依赖按 `requirements.txt` 安装。执行：

```bash
python -m compileall -q scripts
python scripts/selftest.py
python scripts/bench.py --baseline benchmark/baseline_9.26.json
python scripts/bench.py --cases benchmark/holdout.json
python scripts/bench.py --cases benchmark/transfer.json
python scripts/bench.py --cases benchmark/semantic_transfer.json
PYTHONIOENCODING=cp1252 python scripts/bench.py --cases /tmp/vao-bad-cases.json
python scripts/vao.py plan acceptance/brief.json --out review/acceptance-plan.json --skeleton review/acceptance-skeleton.py
python scripts/vao.py check acceptance/build.py review/acceptance-out.pptx --mode release --speed strict --json
python review/autonomy_probe.py
python review/compare_performance.py --before /tmp/vao-base-5bfb
```

| 本地测试 | 3.10 | 3.12 | 3.13 |
|---|---:|---:|---:|
| `selftest.py` | **460/460** | **460/460** | **460/460** |
| 主基准 / 原边界 / 原迁移 / 新语义 | **26/26 · 12/12 · 6/6 · 13/13** | 同左 | 同左 |
| `compileall`、`git diff --check` | PASS | PASS | PASS |

完整输出：[3.10](selftest-310.log)、[3.12](selftest-312.log)、[3.13](selftest-313.log)；各基准输出在本目录 `bench-*-{310,312,313}.log`。自测仍是**代码级成功**；没有 Windows 环境，本地三个 Linux 解释器不等于跨平台矩阵。当前改动未推送，**无修复后的 CI 链接**，不能确认远端全绿。

七页 `acceptance/build.py → review/acceptance-out.pptx` 的 `release strict` 是 **PASS（7 页）**；证据：[check JSON](acceptance-check.json)、[原生结构](structure-evidence.json)。61 个对象、1 个原生图表及内嵌工作簿、ZIP 无坏件、页内名称无重复、`186 公里` 原生文本含 NBSP；用 python-pptx 编辑一处、保存、重开可读。**这只验证结构编辑，不是 PowerPoint UI 编辑。** 样稿由仓库原有的作者手写 BUILD 编译，未以其证明本次语义修复带来了更美的画面。

## 6. 自动设计能力与真实视觉：证据边界

[三个领域的端到端能力探针](autonomy-probe.json)：教育 4 页、制造 6 页、医疗 8 页，均 `brief → plan` 成功；**原样生成的 skeleton 中元素数全部为 0**，`check --mode release --speed strict` 全部以 `GUARD_FAIL` **BLOCKED（退出 2）**。这是预期的诚实硬门，同时说明“系统无需作者即可自动生成完整设计稿”**尚不成立**。探针没有偷偷使用 `acceptance/build.py` 填版。[可复现脚本](autonomy_probe.py)。

查看了七页 [ghost 联系表](acceptance-out_preview/ghost-contact-sheet.png)：可作为构图/层级的**结构性方向线索**，不证明 PowerPoint 的字体、真实断行或投影尺度；预览中来源字小，值得在实际投影检查。当前环境**没有 Microsoft PowerPoint，也没有真实 PowerPoint 页面截图、UI 编辑/另存/重开结果**。因此逐页真实中文排版、图表标签遮挡、字体回退、投影可读性以及成品视觉水平一律标记 **`NOT VERIFIED — Target PowerPoint`**。`audit/blind-status.json` 为 0 评审，未形成视觉质量共识。历史报告曾链接的 `acceptance/out_preview/...` 与 `acceptance/edit-roundtrip.pptx` 未在此提交跟踪；本轮新生成的 ghost 仅在 `review/`，不可冒充旧链接或真实渲染。

## 7. 性能：交错配对，没有显著提速结论

[脚本](compare_performance.py)使用同解释器/相同依赖/相同手写 fixture 的基线 HEAD 归档与本地改版，**三轮交错配对**，每 CLI 新进程；`strict` 全页检查；冷=无应用缓存（**未清 OS 缓存**）、暖=相同输入、迭代=第一页标题等长实改。表中为 check 墙钟中位数（毫秒），不是完整 AI / 人工设计时间；原始每轮记录与摘要见 [performance-comparison.json](performance-comparison.json)。

| 任务 | 冷 前→后 | 暖 前→后 | 单页迭代 前→后 |
|---|---:|---:|---:|
| 5 页、含原生元素 | 431.74 → 394.03 | 57.82 → 57.10 | 338.20 → 335.71 |
| 15 页、含原生元素 | 641.56 → 649.33 | 60.71 → 61.69 | 493.04 → 489.43 |
| 15 页 + 合成插图 | 825.81 → 824.91 | 64.66 → 68.77 | 533.70 → 546.69 |

**27/27** 配对的 PPTX 与 ghost 联系表字节摘要相等；迭代每次只重画 1 页。样本仅 3 轮，毫秒级波动混有噪声，含图暖/迭代还略慢；**不宣称显著提速或返工减少**。语义规划改善来自不同判断输出，固定手工 spec 的 PPTX 字节相等不能证明视觉质量提升。BUILD 人工耗时与返工次数、真实美感评分均无实测。

## 8. 按优先级列出剩余问题

- **P0 未完成｜远端 CI：** 当前已知 [Actions #54](https://github.com/cpikeo/ppt-visual-art-director-os/actions/runs/38668276721) 的 Windows 3 格失败；本地修复需提交、推送/PR 并观察六格与 smoke 实际结果，再追查可能出现的其他 Windows 专属故障。未取得推送权限/Windows runner 的直接执行证据。
- **P0 未完成｜真实视觉终验：** 在目标 Microsoft PowerPoint 中逐页打开、渲染、编辑、保存、重开，并保留截图/版本/字体环境/可读性记录；当前全部 `NOT VERIFIED`。
- **P1 未完成｜自主 BUILD：** 需从判断到元素/坐标建立可评测生产链；先明确代理作者与系统自动落版的边界，不能用原有人手 BUILD 伪装自动设计。
- **P1 未完成｜独立质量评测：** 未见外部保密集或足够独立评审者；13 项固定内部数据仅用于回归，构图/排版/美感仍无独立证据。
- **P1 未完成｜返工/性能：** 自动段没有可靠提速，人工修改次数、审美对比和目标软件表现未测。
- **P2 待清理｜历史材料：** `audit/REPORT.md` 的部分产物链接与“未推送”状态已过时；应按历史快照标注，而不篡改原审计记录。

**交付结论：P0 的 Windows 故障机制在本地按同一编码边界复现并最小修复；语义判断对既有七页 brief 有可定位提升；三版 Linux 测试全过。远端 Windows/CI、自动落版、PowerPoint 视觉终验和独立美感比较仍未完成。**
