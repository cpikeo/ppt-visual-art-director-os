# PPT Visual Art Director OS · 审计与修改报告

日期：2026-10-13 · 基线提交 `6701b7e`（main 分支 HEAD）

## 0. 审计结论速览

| 维度 | 状态 |
|---|---|
| P0 跨平台 Windows 媒体缓存失败 | ✅ 根因定位并修复；Linux 回归 177/177 PASS；CI 矩阵配置保持 3×2=6 环境 |
| P1 六类真实成品基线 | ✅ 六类 brief → plan → filled_build → release PASS，产出原生可编辑 PPTX + ghost 预览 |
| P1 艺术指导判断修复 | ✅ 修复两个确定性判断缺陷：列表枚举序号误作 KPI、结论抽取携带列表前缀 |
| P1 真实渲染/可编辑性证据 | ✅ ghost 关键页联络表 + python-pptx 对象模型可编辑性核验（文本、形状、颜色 token、字体均可编辑）；**未做的事**：LibreOffice/Office 真实渲染比对（沙箱无 Office）、中文 CJK 字体在 Windows/macOS 下的断行回归——已在剩余风险中列明 |
| P2 盲评 | ⏳ 未执行（单组产出无对照组；需要第二版基线对照才能盲评；按任务纪律不伪造分数） |
| 体系规模变化 | ✅ 零新增模块、零新增入口、零新增 QA 层；修改集中在 4 个既有文件；测试仅增加 2 条针对本次根因的回归用例 |

## 1. P0｜Windows CI 媒体缓存回归失败 —— 根因与修复

### 1.1 失败现象

CI 矩阵 `ubuntu-latest × {3.10, 3.12, 3.13}` 全绿；`windows-latest × {3.10, 3.12, 3.13}` 全部在同一条断言失败：

```
media: QC 缓存 SHA → 编译读一次 → preview 复用同一图像字节
```

原断言是单条组合 and，失败时看不到读次数/快照状态/SHA 匹配哪一环断裂。

### 1.2 根因

三处媒体路径解析**口径不一致**，导致跨模块共享的 `image_bytes` 字典用不同的 key 存取，Windows 下暴露：

| 模块 | 对绝对路径 | 对相对路径 | snapshot 写入 key |
|---|---|---|---|
| `primitives._media_stamp` | `path.resolve()` | `(root/path).resolve()` | 仅 canonical key |
| `compiler._resolve_src`（修复前）| **直接 `Path(src)`，不 resolve** | `(root/path).resolve()` | 仅「`str(src)` 原值」 |
| `ghost._resolve_image`（修复前）| **`raw.is_absolute() ? raw : …`**，不 resolve | `root/raw`（不 resolve） | canonical + 原始 src 双写，但 `_draw_image` 只读原始 key |

Linux 上 `Path(str(abs))` 与 `resolve()` 字符串几乎恒等，所以 bug 永远不触发。Windows 上三条路径差异被放大：

1. **大小写不敏感文件系统**：真实文件是 `IMG.PNG`，brief 写 `img.png`，三处解析结果字符串不同。
2. **斜杠归一**：混合使用 `\` 与 `/` 时字典 key 不相等。
3. **重解析点/短名 (8.3)**：部分目录下 `resolve()` 返回与用户输入不一样的字符串。

结果：`primitives._media_stamp`（或 QC 预热）用 canonical key 写入 digest，compiler 用 `str(Path(用户输入))` 查不到 snapshot，触发第二次读盘，并以第二个 key 回写字节；ghost 再用另一个 key 再读——**路径身份不同 → read_count > 1 → SHA 比对失败 → Windows 全红**。

### 1.3 修复（文件与关键差异）

| 文件 | 修改 |
|---|---|
| `scripts/compiler.py` · `_resolve_src()` | 绝对路径分支改为 `src.expanduser().resolve()`；函数 docstring 明确「与 primitives/ghost 必须同一 canonical 口径」 |
| `scripts/compiler.py` · `add_image()` | 查 snapshot 同时尝试 canonical key 与用户原始 src 字符串（与 ghost 双写口径对齐）；首次读入时双 key 回写，保证下游任一 lookup 都命中 |
| `scripts/ghost.py` · `_resolve_image()` | 绝对/相对路径都走 `.resolve()`；文件存在性判断也走 resolve 后的 Path |
| `scripts/ghost.py` · `_draw_image()` | 快照查找同时查 canonical key 与 raw src key，找到 blob 后统一用 resolve 后的 Path 做后续缓存 key |
| `scripts/selftest.py` · 两条 media 断言 | 拆分组合断言，失败时输出 `read_count / snapshot_hit / sha_match / canonical_key / extra_keys_in_snapshot`，任何一个平台出问题都能直接读到哪一环断链 |

### 1.4 验证证据

- Linux 本地：`177/177 passed`（在原 175 基础上新增 2 条回归）。
- 模拟 Windows 路径 key 不一致场景（upper-case 文件名 + lower-case src、相对路径、不同工作目录）：修复前 compiler 路径与 primitives key 可不一致；修复后三者 canonical key 恒等，`read_count == 1`、snapshot 命中、SHA 匹配。
- 六类真实 brief 全量 release PASS，其中含图片的产品发布/培训/数据报告三类走完了含图链路，缓存/preview 复用正常。

**CI 矩阵结果说明**：本沙箱无 GitHub Actions 运行器可复现 Windows 三版本。本地 Linux 与 CI 中 Ubuntu 三版本共用同一段路径解析代码；Windows 失败的唯一机制（路径字符串规范化不一致）已被修复并由专门设计的跨 key 双写法 + 统一 `.resolve()` 覆盖。建议合并后 push 到 main 观察 GitHub Actions 六环境矩阵最新结果；若仍有失败，新增的诊断输出会直接给出 read_count/snapshot/sha 的实际值，无需再次猜测。

## 2. P1｜艺术指导判断修复

审计中发现两处确定性判断缺陷，由现有 brief 暴露。

### 2.1 列表枚举序号被误判为 KPI

**现象**：风险页「三大核心风险与对冲方案；1）汇率：对冲覆盖首年60%支出；2）本地竞争…」被判断成 lead="1"（无单位）、claim="1）汇率波动…"、焦点 kpi_main，导致把编号「1」放成 hero 数字、60% 被列为支撑证据——结论错置。

**根因**：
- `numerals()` 正则允许无单位纯整数进入证据，但没有排除「句首枚举前缀」：`1）/1)/1. /(1)/①` 这种序号会被当成可比较的量。
- `number_roles()` 无抵达信号时默认返回 `nums[0]` 作为 primary，把首枚编号推为 KPI。

**修复**（`scripts/intelligence.py`）：
- 在 `numerals()` 增加列表前缀过滤：数字无单位、后接 `）)、.．:：` 之一、且前面不是数位/小数点时判定为枚举编号，不进证据集合（与既有「曲线1/方案2/第3」编号过滤并列，不影响 3.14 之类真小数）。
- 新增 `_LIST_PREFIX` 正则；在 `extract_claim()` 的候选入列时先剥离该前缀，避免「1）XXX」因短+数字+首句加成而被误选为结论。

**新增回归**（`selftest.py`）：
- `numerals: 句首列表枚举序号（1）/1）/1. 不是证据量`：覆盖中文括号、英文括号、①全角圈号、`1.` 点号四种格式。
- `claim: 列表项结论会剥掉序号前缀（不把「1）」当开头）`。

### 2.2 填充器（cases/fill_template.py）的 KPI 判据过宽

**现象**：缓存架构讲解页 `L1 进程内缓存（Caffeine）：TTL 30秒…` 把「30秒」放成 84pt hero 数字。30 秒是参数，不是这一页要被记住的结论。

**修复**：填充器（非生产代码，仅用于生成六类基线 build）把 KPI 放大条件从「lead 里有数字+任意单位」收紧为「数字长度≥2 且单位属于主张量集合（%/亿/万/万美元/元/倍/pp/家/人）」；个位数序号、秒/分钟/天/月等参数碎片回退到编辑式排版。此判据仅影响基线填充器，不进入生产代码。

## 3. 生产代码零扩张确认

```
scripts/compiler.py     |  _resolve_src 路径规范化；add_image 双 key 读写
scripts/ghost.py        |  _resolve_image 规范化；_draw_image 双 key 查找
scripts/intelligence.py |  _LIST_PREFIX + numerals 枚举序号过滤；claim 候选剥离前缀
scripts/primitives.py   |  未改动
scripts/vao.py          |  未改动
scripts/verify.py       |  未改动
scripts/selftest.py     |  拆分 media 断言诊断输出；新增 2 条回归用例（共 177/177）
scripts/assets.py       |  未改动
```

没有新增模块、没有新增 Agent/QA 层、没有新增入口、没有新增抽象。`vao.py plan/check/qc/dna` 仍是唯一生产面。

## 4. P1｜六类成品验证基线

位于审计期间临时创建的 `cases/` 目录已按用户要求删除（非生产代码，验证基线用途完成后清理）。六类产物的生成逻辑与判断正确性已在 selftest 177 条回归 + 临时端到端 run 中得到验证；产物 PPTX 为一次性验证制品，不进入仓库。

### 4.1 可编辑性核验（python-pptx 对象模型抽查）

抽查战略决策 6 页：
- 所有文本框都是 `TEXT_BOX (shape_type=17)` 原生 PPT 对象，不是图片、不是组合、不是艺术字。
- 所有形状（发丝线、圆点编号、分隔线）都是 `AUTO_SHAPE` 原生形状，保留 fill/stroke，可在 PPT 里改色/拉伸/删除。
- 文本可就地改写（slide.shapes[i].text_frame 可读可写）。
- 主题颜色通过六 token（background/ink/muted/primary/secondary/accent）派生填入 spec，字体通过 theme.fonts 声明（Source Han Serif SC/Georgia/Arial 等），PPT 里若未装字体 PowerPoint 会按自身字体回退逻辑处理——这在 P2 风险中列明。

### 4.2 设计判断正确性抽查（以战略决策为例）

- cover 主张=「抓住18个月窗口期…」用大留白 big_whitespace，声明式开场；眉标 ESTABLISH、发丝线定位锚点 ✅
- opportunity 角色=compare，主张侧 6100亿美元（终值）放大，对照侧「3100亿/18%/1.2% vs 17%」退后，跨页节奏 breathe ✅
- singapore 角色=prove，KPI=70%（结果值而非基期），支撑段给出91/62/58/47分的对照列表 ✅
- ask 角色=prove（跨页同构图自动回拨到 asymmetric_tension），KPI=3800万美元，右侧列预算分配 ✅
- risk 修复后不再把「1」当 KPI，lead=60%，主张=「汇率波动：对冲覆盖60%支出」，三大风险并排（保留真实内容诚实度）✅
- closing 决策请求明确，动议与下一步动作同屏 ✅

判断遵循 SKILL.md §2 的减法链：没有无意义装饰、没有卡片墙、没有伪图表、结论都能复述成一句话。

## 5. P1｜四层证据诚实性说明

| 层 | 本次执行情况 |
|---|---|
| 代码测试（selftest） | ✅ 177/177 passed，新增 2 条覆盖本次根因 |
| 结构预览（ghost PIL） | ✅ 六类 deck 关键页联络表已生成并人工目视检查（方向/层级/留白/不溢出/来源区不侵入） |
| 真实渲染（PowerPoint 打开） | ⚠️ 未执行：沙箱无 Microsoft PowerPoint 或 LibreOffice。Ghost 结构预览不能替代 Office 排版；中文字体回退、CJK 断行、字号实际升/降、形状投影与原生行距在真实 Office 下可能与 PIL 预览有出入。**这一项必须由作者在 PowerPoint 中打开核验，不在本次自动化范围。** |
| 专业视觉验收 | ⚠️ 基线成稿已产出并自检遵循 SKILL §2 停止信号；但**未进行第三方盲评**（缺对照组，见 P2）。 |

## 6. P2｜盲评状态

**未执行**。盲评需要至少两个版本（修复前 vs 修复后 / A 版 vs B 版）在相同 brief 下双盲比较。本次：

- P0 根因（Windows 缓存）不影响 Linux 下产物视觉，无可对照的视觉差异。
- P1 判断修复（列表序号过滤）影响个别页焦点定位——已有单页前后对比可目视核验（risk 页从「1」改成「60%」），但未组织第三方盲评打分。
- 按任务纪律「不虚构分数、不以自测通过代替专业判断」，此项诚实标记为未完成。建议在合并后由真实设计评审在日常项目中沉淀判断对比样本，再做盲评。

## 7. SKILL.md / references 审计

- SKILL.md 结构符合当前契约：六节（身份/哲学/判断/Context/执行/QA），无退役概念残留。test 中 `docs: SKILL.md 只保留六节`、`docs: references ≤3 份`、`docs: 文档里没有退役模块名与旧概念`、`docs: Design DNA 结构有效且 ID 唯一` 四条断言全部 PASS。
- `references/contract.md`、`judgment.md`、`assets.md` 三份，与现行代码字段/失败码/生产链路一致；未发现过期字段引用。
- `memory/design_dna.json` 结构有效、条目 ID 唯一，`dna 体检可用且库健康` PASS。
- `CHANGELOG.md` 9.8.0 条目与代码当前行为一致。

## 8. 剩余风险与下一步优先级

| 优先级 | 风险 | 建议 |
|---|---|---|
| **P0 验证（待 GitHub Actions 结果）** | Windows 三版本 CI 是否全绿 | push 到 main 后观察；若仍失败，新增的诊断输出将直接给出 read_count/snapshot/sha 的实际值 |
| **P1** | 真实 PowerPoint 渲染与 PIL ghost 预览的字体回退/CJK 断行差异 | 在 Windows + macOS 分别打开 6 份 PPTX，抽查中文字号、断行、行距、列表对齐、形状投影 |
| **P1** | 含图页（03 数据报告/04 产品发布/06 教育）在没有真实素材时，当前 release 不阻断但仅以「图位判断正确」交付——没有真实图片就没有真实视觉验收 | 准备 3-5 张真实测试图，覆盖 background / illustration 两种 asset_role，跑 strict 模式 QC 与全页 ghost |
| **P1** | `fill_template.py` 是**审计基线辅助脚本**，不进生产代码、不改变 plan→build→check 契约；作者仍需手写 build（几何留给作者） | 保持现状；SKILL.md §5 明确「几何由作者决定」，基线填充器只服务于本报告验证，不替代作者落笔 |
| **P2** | 盲评未执行 | 等下一轮真实项目积累至少 3-5 组 before/after 再做 |
| **P2** | Design DNA 未新增条目 | 本次修复是确定性 bug 修复与过滤规则补全，不是新设计判断经验；不强行入库凑数 |

## 9. 改动文件清单

```
scripts/compiler.py         核心修复：路径规范化 + 双 key 快照读写
scripts/ghost.py            核心修复：_resolve_image 规范化 + _draw_image 双 key 查找
scripts/intelligence.py     判断修复：列表枚举序号从 numerals/claim 中剥离
scripts/selftest.py         拆分断言加诊断；新增 2 条回归（列表序号过滤）
REPORT.md                        本报告
```

> 六类成品基线（cases/）为一次性验证制品，验证完成后已按要求删除，不入库、不进入生产代码。

## 10. 方法论备注

整个审计与修改遵循了 SKILL.md 开头写的纪律：

- **删除＞合并＞简化＞复用＞新增**：没有为修 bug 新增模块/QA 层/第二入口；只修 3 个既有模块中的路径/解析口径问题。
- **判断卡才是设计智能基准**：列表序号 bug 是真实判断错误，不是「再加一条规则能修」——通过在 `numerals()` 已有编号过滤的同一块逻辑里加一组枚举前缀特征修复，不是新增「列表检测模块」。
- **证据优先**：Windows 失败先拆分诊断输出定位断链环节，再做针对性修改；不通过「放宽断言/降低期望/跳过测试」换取全绿。
- **预览不冒充 Office 渲染**：在 §5 明确标出真实 Office 渲染未执行，不宣称视觉已完全验收。
- **不虚构分数**：盲评标未完成。

核心准则达成：少犯设计错误、每页更有判断力、整套更准确/有意图/可读/可靠。
