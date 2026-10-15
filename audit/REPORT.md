# 仓库审计与本地交付报告

**日期：2026-10-15｜本地版本：9.29.0｜结论：代码与结构验证通过，真实视觉终验未完成。**

已直接修改 `/home/user/ppt-visual-art-director-os`，不是只交建议。未提交 commit、未推送、未触发远端工作流。

## 1. 交付与证据边界

- **实际 PPTX：** [7 页审计样稿](../acceptance/out.pptx)，61 个对象、56 个带文本框对象、1 个原生图表及内嵌 XLSX。
- **结构预览：** [7 页 ghost 联系表](../acceptance/out_preview/ghost-contact-sheet.png)。这是 PIL 结构预览，**不是 PowerPoint 截图**。
- **结构核验：** [pptx-structure.json](pptx-structure.json)。图表类别为“修改前 / 修改后”，数据为 7 / 12；页内对象名唯一；数字与单位的 NBSP 在原生文字中存在。
- **编辑结构往返：** 使用 python-pptx 读取、改写一个文本对象、保存、重开成功；产物为 `acceptance/edit-roundtrip.pptx`。**这不等于在 PowerPoint UI 内编辑成功。**
- **性能：** [performance.json](performance.json)，含 120 次 strict check 的原始计时、120 次对应 plan 记录引用、60 对前后产物与预览摘要比较。实际执行 plan 为 40 次，每次对应冷 / 暖 / 单页迭代三次 check；plan 耗时在各阶段记录中复用，不虚增 plan 运行次数。
- **测试：** [validation.json](validation.json) 保存命令、退出码、耗时和日志位置；[validation-run.log](validation-run.log) 为运行汇总。
- **判断：** 原有 26 案例、新边界 12 案例、后续迁移 6 案例；不把判断字段正确率写成视觉质量评分。

没有目标 PowerPoint、Windows 执行环境或独立评审者。因此不能声称所有交付门槛均已完成，也不能宣称达到国际顶级作品水准。下文将已完成、未完成严格分开。

## 2. P0 基线与故障复现

### 仓库与 CI

初始工作区为空，通过公开 Git HTTPS 克隆。初始 `main...origin/main` 干净，没有用户改动可覆盖。

- 基线提交：`2ec0b0e792f0c318228b150a5b9fceab7046356c`。
- 提交时间：2026-10-15 09:15:50 +0800。
- 查询到的最新远端 CI：[run 38664692877](https://github.com/cpikeo/ppt-visual-art-director-os/actions/runs/38664692877)。
- Ubuntu 3.10 / 3.12 / 3.13 为 failure；Windows 三项与 spec smoke 为 success。
- 原始 API 响应保存在 `ci-before.json`、`ci-jobs-before.json`、`ci-annotations-before.json`。下载作业全文日志返回 403，不能声称已取得远端完整失败栈。
- 远端 CI **仍是旧提交的失败状态**；本地修改未推送，不能把本地测试写成远端全绿。

### 测试基线

本机 Debian 13 / Python 3.13.16 原样执行 `python scripts/selftest.py`：**416/416**，14.079 秒。见 `baseline-selftest.log`、`baseline-env.json`。

在原提交中模拟缺少粗体候选（原测试自身会清空常规候选），执行完整自测：**415/416，退出码 1**。唯一失败：

```text
[FAIL] ghost: 无字面可用时记账（预览不得静默丢掉中文字形） — {'cjk_serif': 2}
```

见 `repro-415.log`。这是与报告一致的断言故障复现，不冒充完全相同的 Ubuntu runner 镜像。

**根因：** 回退台账按 `(角色, 字号, 字重)` 的字体缓存未命中累计，并非每个角色恒为一次。标题与来源字号不同，缺字库时出现两次回退合法。测试断言却要求某个 CJK 角色恰好等于 1，且只隔离常规候选，漏隔离粗体候选，导致结果依赖宿主字体安装。

**修复：** 保留“必须记录中文回退”的断言，改为检查存在中文回退；另用独立受控字体加载测试精确锁定三个缓存项产生三次回退、重复命中不增加计数。TTC 索引测试明确注入自己的候选；候选身份测试也使用独立 fixture，不再借用宿主条件。

## 3. 修改清单：根因、收益与风险

| 文件 / 函数 | 操作 | 根因与实际收益 | 风险 / 对应验证 |
|---|---|---|---|
| `selftest.py` 字体组 | 修复、补测 | 去除“恰好一次”和宿主安装假设，保留回退告警与 SC TTC index=2 检验 | CJK 常规/粗体候选全空时整套 **445/445**；常规矩阵也执行受控坏字体测试 |
| `ghost.py` 字体候选、`_font_names`、`_font_stamp` | **迁移 / 合并**至 `primitives.py` | 稳定事实与加载逻辑共用候选顺序；预览代码不再独占暖路径所需事实 | ghost 使用同一字典的别名，不维护副本；暖路径零 PIL / ghost / Office 导入回归 |
| `primitives.preview_font_stamp`、`vao._ghost` | 修复缓存契约 | 原页缓存漏粗体；整套缓存根本不检查字体。现在两层均检查常规/粗体候选身份，每轮入口刷新 | 候选变更必须使整套与所有受影响页缓存失效；字形覆盖仍非此 stat 身份能证明 |
| `primitives.file_digest`、`json_read_cached` | **删除 `_file_state` 与元数据摘要复用层**；简化 | 同 size / mtime 覆盖、同时间刻度写入可命中旧摘要。摘要读当前字节；JSON 按内容摘要复用解析 | 增加必要读盘，不承诺所有路径更快；覆盖与原子替换回归，strict 产物仍只核对一次并显式复用 |
| `intelligence.understand` | 删除无依据推断、复用过滤结果 | 去掉“凑 100% 即整体”“三个同单位数字即趋势”“任意 `-` 即流程”；保留真实时间轴、端点变化与 ASCII 箭头；复合名词过滤只做一次 | 12 个固定边界由 **7/12 → 12/12**；原有 **26/26**；后续未再按个案调参的迁移集 **6/6** |
| `page_judgment` | 补一个未决项 | 构成候选要求作者继续核对分母、期间、互斥性，而非假装已证明整体 | 不替作者完成行业语义；非独立模型理解评测 |
| `intelligence.measure_of` | **删除未使用参数** `has_long_lead` | 全仓无参数消费者，静态检查确认未读取 | 现有 typography 回归覆盖；没有新增配置或默认字阶 |
| `assets.build_manifest` | **合并既有素材主条目** | 同一素材跨页原先生成重复 `asset_id`，随后 `asset_entries` 拒绝自己生成的清单。现在按来源与 QC 契约合并页绑定 | 不同安全区 / 底色等不合并；同图两页完整 plan → QC → release strict 回归 |
| `compiler` 两个原生图表分支 | 延迟依赖 | 工作簿写入器仅在确需原生图表时导入；无图表不载入 xlsxwriter | 导入契约回归；60 对 PPTX 字节一致，图表工作簿保留 |
| `bench.main` | 修复退出码 | 原先打印 FAIL 仍返回 0，不能作为 CI 门 | 不可能期望值的 fixture 必须退 1；未删负例 |
| `.github/workflows/ci.yml` | 复用既有矩阵补门 | 每个矩阵格执行原基准与两个边界集 | 修改后的远端矩阵未运行；只报告本地证据 |
| `SKILL.md` / 两份 references | 收敛而非另建规则库 | 审美 / 关系判断仍在 SKILL；执行字段、缓存事实与资产迁移边界在两份契约 | 没有新增“审美参数模板”或第二生产入口 |
| `benchmark/holdout.json`、`transfer.json` | 少量新增测试数据 | 覆盖医疗、教育、能源、制造、零售、治理、公共服务等关系形状 | 固定集不是全面跨行业泛化证明；暴露后只作为回归集 |

**未删除整个生产模块。** 七个模块各有真实消费者或独立职责；没有为减少文件数强行合并编译、核验与规划。没有新增模型调用、生产模块或运行时依赖。

## 4. 全仓架构与权威事实

静态清单见 `architecture-before.json` / `architecture-after.json`，逐脚本列出导入、局部依赖、函数区间、直接调用和顶层契约常量。这是 AST 清单，不是动态覆盖率，也不证明所有死代码都已穷尽。

```text
plan:  vao → intelligence → primitives
               └─ 按需 assets → primitives
check: vao → verify → primitives
         ├─ 含图 assets → primitives
         ├─ 必要时 compiler → primitives → python-pptx
         └─ 预览缓存失效时 ghost → primitives → PIL
```

模块级依赖图前后不变。改动发生在有效执行路径与事实所有权：

| 项目 | 修改前 | 修改后 |
|---|---|---|
| 字体候选事实 | ghost 两张表；stamp 只看常规首个存在文件 | primitives 两张表，加载与 stamp 同源；常规 / 粗体所有候选均入身份 |
| 暖整套预览 | 无字体身份检查 | primitives 轻量身份核对；命中不加载 ghost/PIL |
| 摘要身份 | `file_digest → _file_state → size/mtime 缓存` | 当前字节哈希；调用方显式传递已验结果 |
| JSON | 依据 size/mtime 复用对象 | 读取当前字节，内容相同才复用解析 |
| 证据名词过滤 | 同页多次调用 | understand 内一次，后续复用 |
| 既有资产 | 一页一个重复主条目 | 同素材同 QC 一份主条目 + 多页绑定 |
| 图表工作簿导入 | 编译器加载即付成本 | 原生图表实际需要时付成本 |

权威规范仍只有：

- **SKILL.md：** 设计哲学、受众 / 决策 / 主张 / 证据判断、页面意图、构图与跨页叙事。
- **references/contract.md：** spec / 物理执行 / 失败码 / 缓存身份契约。
- **references/assets.md：** 资产来源、绑定、QC 与跨页复用迁移。
- **primitives：** 字体事实、单位与文本禁则、几何 / 颜色 / 身份、CHART_SPEC；未在文档再抄一份图表枚举。
- **verify：** 硬门执法；不加入自动审美打分。

`vulture scripts --min-confidence 100` 最终无输出。该结果只说明未发现这一级高置信未使用项，不说明语义上不存在冗余。

## 5. 规模对比

口径：Python `splitlines()` 的物理行数，含注释 / 空白。生产与测试分别统计；不以行数压缩为成功指标。完整数值见 `size.json`，可用 `audit/analyze.py --before <原提交目录>` 重建。

| 分类 | 前 | 后 | 变化 |
|---|---:|---:|---:|
| 生产文件 | 7 | 7 | 0 |
| 生产行数 | 12,023 | 12,027 | +4 |
| 测试 / 判断基准脚本 | 2 | 2 | 0 |
| 测试脚本行数 | 3,146 | 3,272 | +126 |
| ghost | 1,737 | 1,669 | −68 |
| primitives | 1,551 | 1,599 | +48，包含字体事实迁移与不安全缓存删除 |
| intelligence | 2,772 | 2,783 | +11 |
| assets | 2,089 | 2,097 | +8 |
| compiler | 1,859 | 1,860 | +1 |
| vao | 959 | 963 | +4 |
| verify | 1,056 | 1,056 | 0 |

另有三个审计复现脚本 **316 行**；手工样稿与 plan 生成骨架两个 `.py` 共 **231 行**。它们作为支持材料单列，不藏进生产统计。运行时依赖仍为 python-pptx / Pillow / numpy / PyYAML 四项，无新增；uv 与 vulture 只用于本次工具环境。

## 6. P3 性能：公平交错实测，不宣称显著提速

### 环境与方法

- Debian GNU/Linux 13，x86_64，2 vCPU；Linux 6.1.158+ / glibc 2.41。
- Python 3.13.16；python-pptx 1.0.2、Pillow 12.3.0、numpy 2.3.5、PyYAML 6.0.3。
- 相同 fixture、相同解释器与依赖，**两版本预先同等 compileall**。不再比较基线现场编译源码与修改版现成 `.pyc`。
- 每任务 **5 轮配对交错**，轮次顺序 before→after / after→before 交替；每条 CLI 新进程。
- 冷：清空应用产物与缓存；**不清 OS 文件缓存**。暖：相同输入与输出；迭代：只把第一页标题“架构简单”改为“执行简单”，等长真实修改，不是尾随空格。
- 全部 `release --speed strict`，检查所有页。迭代每次只重画 1 页，其他页复用；没有减少硬门或取证页数。
- 无图 5 / 15 / 30 页任务含原生文字、形状与图表；代码内部任务名 `text*` **不表示纯文字**。含图为 15 页 + 一张 1920×1080 原创 PIL 合成插图，真实走 plan 清单 / 像素 QC / 绑定 / 编译 / 全页预览。
- 这是确定性生产段，不包含人工 / 模型 BUILD 思考耗时、外部图像生成耗时或目标软件验收，**不是完整 AI 制作总耗时**。

### check 外部墙钟中位数（ms；负数为减少）

| 任务 | 冷 前→后 | 暖 前→后 | 单页迭代 前→后 |
|---|---:|---:|---:|
| 无图 5 页 | 435.36 → 453.46（+4.16%） | 63.66 → 62.70（−1.51%） | 377.31 → 369.93（−1.96%） |
| 无图 15 页 | 747.00 → 742.42（−0.61%） | 70.71 → 68.68（−2.87%） | 551.27 → 544.36（−1.25%） |
| 无图 30 页 | 1239.30 → 1261.76（+1.81%） | 81.29 → 79.34（−2.40%） | 855.30 → 835.01（−2.37%） |
| 含图 15 页 | 951.77 → 962.02（+1.08%） | 75.79 → 79.01（+4.25%） | 615.43 → 641.97（+4.31%） |

plan 中位数，前→后：5 页 90.77→91.73 ms；15 页 107.47→108.12 ms；30 页 136.80→136.61 ms；含图 115.31→116.22 ms。`performance.json` 还记录实际配对的 plan+check 中位数，不能把两个独立中位数相加当成它。

**结论：没有可重复、足够大的端到端加速证据。** 小幅正负波动均如实列出，含图迭代有回退。不能宣传“显著提速”。本次减少的是具体无效工作与错误：重复过滤、不必要的无图表工作簿导入、重复既有资产条目、不可靠缓存层。必要完整性核对保留，额外读盘不掩盖。

探索中发现新增字体检查若直接导入 ghost/PIL，会让暖缓存慢约 36–41 ms；已将稳定字体事实迁到 primitives，最后一轮恢复轻量暖路径。探索数据不作为发布性能提升依据。

### 一致性与证据保留

- **120/120** 次 strict check PASS，每次全页；40 次 plan 成功。
- 60 对 before/after PPTX SHA-256 **全部相同**；60 对联系表 PNG 摘要 **全部相同**。
- 每个 warm 与自身 cold 的 PPTX 字节相同；每个迭代重画恰好 1 页。
- 这证明这些编译 fixture 未因优化改变输出，**不证明自动布局审美提高**。
- 为避免把缓存变成交付体积，重复页缓存与多数重复 PPTX 已删。保留全部原始运行日志、输入、摘要记录及 `performance/image15-4-{before,after}` 代表产物；复现脚本可重建其余产物。

## 7. 测试与回归证据

### 最终结果

| 执行 | 实际结果 | 边界 |
|---|---|---|
| Linux Python 3.10.22 | **445/445** | Debian 本地，不是 Ubuntu runner |
| Linux Python 3.12.15 | **445/445** | 同上 |
| Linux Python 3.13.16 | **445/445** | 同上 |
| CJK 常规 / 粗体候选全空，3.13 | **445/445** | 包括有意告警；不删断言、不屏蔽生产异常 |
| 原判断基准 | **26/26**，三个版本均通过 | 判断字段，不是美感 |
| 新固定边界 | **12/12**，修改前 7/12 | 期望在修复前按关系不变式写定；暴露后转回归集 |
| 后续迁移 | **6/6**，未再按这些个案调参 | 仍不是外部独立研究 |
| CI spec smoke 原始 run 块 | 三版本均通过，`FORBIDDEN MODULES: []` | 不加载 pptx / lxml / compiler |
| compileall / whitespace | 全部通过 | 不是类型 / 风格 / 视觉认证 |
| 7 页样稿 release strict | PASS；7/7 结构预览 | PowerPoint 未验证 |
| 同图两页资产复用 | plan → QC → release strict PASS | 独立 fixture，非真实证词图 |
| 判断 CLI 负例 | 退 1 | 失败不能伪装全绿 |

所有修复组都被现有全测或新增回归覆盖；首轮发现的测试 fixture 问题也真实留痕，不把试跑失败写成成功：

- 原新增含图性能 fixture 手写旧 v1 清单，生产正确 BLOCK；改用真实 `vao plan --assets-out` 生成 v2，**没有放松资产链**。
- 同图复用回归首次使用空主题，编译正确拒绝缺背景；给 fixture 提供明确背景后复验。
- 候选全空复验暴露 TTC 测试仍借宿主候选、暖缓存子进程与父进程候选不同；改为显式独立测试输入与相同候选传递，不放宽身份检查。

### 实际运行命令

```bash
# 原提交目录从 git archive 2ec0b0e... 导出，不覆盖当前修改。
python -m pip install -r requirements.txt -e .
python scripts/selftest.py
python scripts/bench.py --baseline benchmark/baseline_9.26.json --out audit/baseline-bench.json

# 最终本地三版本 + 原故障复现 + CJK 缺字库 + 实际 CI smoke 块
python audit/validate.py \
  --python /usr/local/bin/python \
  --python /home/user/.venv310/bin/python \
  --python /home/user/.venv312/bin/python \
  --before /home/user/vao-baseline

# 5 轮交错，完整 CLI，不绕过生产入口
python audit/reproduce.py --before /home/user/vao-baseline --rounds 5
python audit/analyze.py --before /home/user/vao-baseline
vulture scripts --min-confidence 100

python scripts/vao.py plan acceptance/brief.json --out acceptance/plan.json --skeleton acceptance/skeleton.py
python scripts/vao.py check acceptance/build.py acceptance/out.pptx --mode release --speed strict --json
python scripts/bench.py blind pack audit/blind acceptance/before.pptx acceptance/out.pptx
python scripts/bench.py blind score audit/blind.key.json audit/blind/score_sheet.csv
```

uv 下载的 3.10 / 3.12 解释器与临时虚拟环境不属于交付运行依赖。换机器复验需先准备对应解释器。

## 8. 作品、视觉检查与缺陷记录

### 已做

7 页样稿由手工内容与几何判断制作，不是让 skeleton 自动填满。叙事为：立场 → 两个常见关系误判 → 判断证据 → 生产链 → 中文排版 → 收束到真实验收。用一致对齐与字重建立秩序，数字页、关系页、流程说明页承担不同信息职责；没有为求变化强制换风格。

已查看完整 ghost 联系表：未观察到明显的标题碰撞、来源覆盖或页间错位。此观察只限结构预览。原生图表数据、内嵌工作簿、对象命名、NBSP、页面完整性和 strict 边界检查有机器证据。样稿以合成案例清楚标示医疗百分比，不伪装真实临床证据；测试图也明确是原创合成插图。

### 前后比较与盲评

`acceptance/before.pptx` 是原提交对**同一份本次新写的 BUILD 输入**编译的产物，不是冒充仓库历史上存在的旧设计稿。它与当前 `out.pptx` 字节相同，SHA-256：

```text
dd7d95193e7d7ba45259ebb0ee412bb0bd7931519a272dd923377bbd7a595445
```

因此本次能证明“这些编译输入不退化”，**不能证明前后样稿审美提升**。语义误判改善另由固定边界结果证明，不能混作美感分数。

匿名材料 `audit/blind/V01.pptx` / `V02.pptx` 与空白评分表已生成，映射另放 `blind.key.json`。没有评审者填表：`blind-status.json` 为 **0 位评审、NOT_ENOUGH_REVIEWERS**。未实际开展匿名视觉评审；叙事、语义准确性、焦点、构图、中文排版、跨页节奏与整体完成度都没有独立评审分数。

### 未做，必须保留

- 没有 PowerPoint 真实打开 / 渲染 / 编辑 / 另存 / 重开证据。
- 没有真实页面截图；所有 PNG 为 ghost。
- 没有验证目标字体完整字形、实际断行、长图表标签遮挡、字体 fallback、目标显示器投影可读性。
- 没有足够人数的独立匿名视觉评审，没有 ICC 共识结论。

## 9. 遗留风险与下一验收门

1. **Windows 与远端 Ubuntu 矩阵未跑。** 本地三个 Linux 解释器不能代替六个远端格；需要授权后由用户推送 / PR 触发。未擅自推送。
2. **真实成品视觉尚未终验。** 样稿整洁只是结构观察，不是国际顶级美感的证明。不得自动签署目标软件结论。
3. **确定性语义仍是启发式。** 已减少几种可重复误判，但没有通用行业推理引擎；共同分母、因果、分类互斥和数据真实性仍需作者。固定小样本 100% 不是泛化保证。
4. **未穷尽全仓冗余。** 已生成完整静态清单并删除确认无消费者参数 / 不可靠缓存层，但未证明所有历史补丁、未消费字段、隐含兼容都已消除。
5. **没有显著提速结论。** 含图迭代最后中位数略慢；完整模型 / 人工创作、外部资产生成与真实验收耗时未测。
6. **既有素材 ID 迁移。** 现在纳入 QC 契约；重新 plan 后旧手写 spec 需按新清单重绑，不能混用旧 ID。
7. **身份不是排版证明。** 字体候选 stat 不等于逐字 glyph 覆盖；fast metadata 探针不等于抗篡改。对并发外部文件替换也没有文件系统事务保证；生产期间应避免外部改写输入。
8. **测试字体警告是预期。** 故意缺字库 fixture 会写 warning；它们证明没有静默丢字，不应为了安静输出屏蔽。

**交付结论：本地实改、回归与确定性生产证据可交付；完整远端矩阵、目标 PowerPoint 和独立视觉终验仍待完成。**
