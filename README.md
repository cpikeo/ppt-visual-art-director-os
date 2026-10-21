# PPT Visual Art Director OS

**内容 → 逐页判断 → 原生可编辑 PPTX。** 单入口、一次判断、一次收口。

它是 Skill / 设计智能，不是设计系统、组件库、模板引擎或样式预设。它做的是**判断**：
这一页要让观众记住什么、为什么这样呈现、哪些东西必须删除。判断基准全部在 [SKILL.md](SKILL.md)。

艺术指导以 Visual Art Director / Editorial Art Director 标准统筹全篇摄影、背景、插画、图表配图、
图标与装饰：**先理解内容与叙事，再确定视觉概念；先判断素材职责，再进行构图与执行。**
内容决定视觉，主张决定焦点，证据约束表达，构图组织关系，对比建立张力，统一塑造品质，
变化推进叙事，留白维持呼吸——不将艺术指导退化为风格套用、素材堆砌或规则化排版。

```
THINK（plan：判断一次做完）→ BUILD（作者落元素）→ VERIFY（check：一次收口）
```

## 快速开始

```bash
pip install -r requirements.txt          # Python 3.10+；无系统级依赖
python scripts/vao.py plan brief.yml --out plan.json --skeleton build.py
# 作者按骨架原文与判断落元素（骨架的 elements 为空；有图时按 asset_manifest.json 出图并写 asset_id）
python scripts/vao.py check build.py out.pptx --mode release --speed strict
python scripts/selftest.py               # 核心自检
# 阈值不适合这一份稿时（只写要改的键，未知键直接报错）：
python scripts/vao.py plan brief.yml --out plan.json --policy my_policy.json
```

brief 模板见 [templates/brief.yml](templates/brief.yml)。素材判断与人工验收见 `SKILL.md §3 / §6`；
素材执行字段、生成/既有素材路径与 QC 边界见 [references/assets.md](references/assets.md)；
字段契约、归一化、失败码与发布清单见 [references/contract.md](references/contract.md)。

## 结构

```
scripts/
  vao.py              唯一入口（plan / check / qc）
  intelligence.py     设计判断：判断链、视觉世界推导、骨架生成
  policy.py           可调策略的唯一结构化来源（权重 / 阈值 / 枚举 / 同分顺序）
  schema.py           数据契约校验器（零依赖 JSON Schema 子集）+ 契约文件自检
  assets.py           资产必要性 → 提示词 → 清单 → 像素 QC → 链核验
  verify.py           硬错误 Guard → PASS / BLOCK → 发布清单
  compiler.py         确定性 PPTX 编译（含编译缓存）
  primitives.py       最小原语（身份 / 字节 / 几何 / 颜色 / 文本测量 / 图表单一规范 CHART_SPEC）
  ghost.py            PIL 结构预览（关键页取证）
  bench.py            判断基准与盲评通道（不进生产入口）
  json/               judgment_cases.json（57 例判断回归）及五组冻结泛化 JSON（r1–r5，不进生产入口）
  selftest.py         核心自检
schemas/              brief.schema.json（输入契约）、plan.schema.json（输出契约）
references/           contract.md（字段、失败码、策略与契约）、assets.md（资产链）
MAINTENANCE.md        规则台账：每条规则住哪儿、谁在读、哪个测试在守、哪些是已知缺口
```

Context 按需读取：判断校准读 `SKILL.md §2–3`；写 spec 读 `references/contract.md`；
判定需要图像时才读 `references/assets.md`。`plan` 本身不读 references，也不调用模型。
要改阈值或查「这条规则谁负责」读 `MAINTENANCE.md`（它不是判断文档，是维护台账）。

## 质量边界

- **QA 只拦硬错误**：编译失败、内容缺失、溢出、越界、重叠、无效资产 / 图表、来源缺失（release）。
  输出只有 PASS / BLOCK；设计质量由逐页判断与作者审阅负责——规则通过或预览正常不替代审美验收。
- **分层各有闸门**：判断协议在 `SKILL.md`；可调数值在 `scripts/policy.py`（`--policy` 覆盖必须
  逐键校验，写错键名退出 2）；brief 进来看输入契约（`schemas/brief.schema.json`，写错
  `audiance`/`conten` 这类键名直接退出 2 并给候选），`plan.json` 落盘即过输出契约
  （`schemas/plan.schema.json`）与语义契约（`intelligence.validate_plan`），违约退出 2。每页 `judgment.provenance` 标明哪些
  决策是作者声明、哪些是算法推导、哪些只是词表提示（`pending_author` = 还不算判断）。
- **验证层次不是一回事**：代码测试（selftest）→ 产物结构检查 → 结构预览（ghost，方向证据，不是真实渲染）
  → 目标 PowerPoint 打开 / 编辑 / 另存 / 重开（本仓库未验证）→ 专业视觉验收。自动化结果里后两层恒为未验证。
  本仓库不调用 PowerPoint，也不使用 LibreOffice 等替代引擎渲染。
- **速度**：`fast`（默认）只取关键页预览，`strict` 全页取证。实测数字见 CHANGELOG。
- **模块分工**（审查标准，不是文件拆分清单）：

  | 模块 | 负责 | 不负责 |
  |---|---|---|
  | `SKILL.md` | 设计哲学、判断原则、主流程、质量标准 | 冗长实现细节 |
  | `intelligence.py` | 内容理解、页面角色、视觉策略与依据 | 无边界的关键词堆积 |
  | `vao.py` | 组织任务、协调生成与验收 | 重复实现其他模块的判断 |
  | `verify.py` | 硬错误、交付完整性、结构安全 | 把文件有效等同于审美优秀 |
  | `ghost.py` | 快速结构预览与可观察缺陷 | 冒充目标软件的真实渲染 |
  | `selftest.py` / `bench.py` | 回归测试；判断基准（准确率、误判、回归） | 只验证代码能执行 |

### 执行安全与兼容边界

完整条款（路径冲突、原子写入、退出码、中断语义、清单键）见
[执行契约 · 文件、信任与发布](references/contract.md#文件信任与发布)。三条纪律先记住：

- `build.py` / Python brief 是**可信作者代码**，不是沙箱；不可信输入只走 JSON / YAML。
- 预览与编译缓存目录独立于输入与交付物；路径冲突在诊断写入前拒绝（退出 2），以免错误报告覆盖原稿。
- 图片链须有真实 brief 文件、匹配的 SHA-256 与 `vao-asset-chain-v2`；brief 改变后须重跑 plan。

### 判断基准

判断回归案例在 `scripts/json/judgment_cases.json`：四组共 57 个案例、各组来源说明与七页规划回归输入。
判断基准只检查页面角色、证据形态、结论来源/文本、图像决策等字段；**不证明构图、断行或视觉美感**。
`bench.py --ablate` 逐组去掉语义词表重跑：**消融后指标不变 = 该维度未被这 57 例覆盖**，
报告时不得把 100% 当成全路径验证（见 CHANGELOG 第三轮审计）。

```bash
python scripts/bench.py             # 57 个判断案例；任一失败返回非零
python scripts/bench.py --ablate    # 词表消融：找出「基准没测到」的判断路径
python scripts/unseen_bench.py --cases scripts/json/generalization_cases_r5.json
                                    # 冻结判断回归（跨指标凑和 / 真分解 / 时间点 / 否定谓语 / 量词）
python scripts/selftest.py          # 负例退出码、缓存、素材复用、策略契约、plan 契约与结构产物
```

历史分组、旧基线与已移除的样稿/审计记录可从 Git 历史恢复。

## 测试

```bash
python scripts/selftest.py   # 退出码即门槛；数量以实际输出为准
```

本工作树按用户要求移除了 `acceptance/`、`review/`、`audit/`、`benchmark/` 目录与报告工件，
因此当前仓库**不包含样稿、真实渲染、验收单或评测报告**；本版不得据 Git 历史中的工件宣称视觉验收结果。
`plan` 只输出设计判断与**空元素骨架**，作者须完成 BUILD；不得以本地自测通过宣称自主落版或目标 PowerPoint 视觉终验。

CI（`.github/workflows/ci.yml`）配置 ubuntu / windows × Python 3.10 / 3.12 / 3.13 自检、57 例判断回归、
四组冻结泛化评测及 spec 档冒烟；另有 ubuntu / Python 3.10 的声明依赖下限组合。**配置变更不代表远端已运行。**
工作树中若有未推送的改动（见 [CHANGELOG](CHANGELOG.md) 最新条目），只能按本地结果报告。

## 版本与历史

版本差异与验证边界见 [CHANGELOG.md](CHANGELOG.md)。历史数据与被删除的旧模块可从 Git 历史恢复。

License: MIT（见 [LICENSE.txt](LICENSE.txt)）
