# PPT Visual Art Director OS

**内容 → 逐页判断 → 原生可编辑 PPTX。** 单入口、一次判断、一次收口。

它是 **Skill / Agent Intelligence / Visual Art Director**——不是设计系统、不是组件库、
不是模板引擎、不是样式预设集合。它做的是**判断**：这一页要让观众记住什么、
为什么这样呈现、哪些东西必须删除。

```
THINK（plan：判断一次做完）→ BUILD（作者落元素）→ VERIFY（check：一次收口）
```

## 判断链（逐页一次）

```
Context → Audience → Decision → Claim → Tension → Information Weight → Visual Role
        → Focus → Spatial Structure → Composition → Typography → Media → Rhythm → Production
        → 整套回看（内容契合压过机械变化，图位执行不造图）
```

逐页判断带来源与理由；**确有竞争时**才记录被否掉的替代项，避免五条套话。
`plan.json` 是完整理由，骨架保留原文和行动摘要，不为生产重读整个 plan。
视觉世界（纸/墨/强调语义/材质/光/字体语气）由内容推导，不查风格预设表——
相同内容类型允许产生不同视觉结果。

## 生产路径

```bash
# 1 · THINK：先判断是否确需图片；若需图，同一次调用自动输出 asset_manifest.json
python scripts/vao.py plan brief.yml --out plan.json --skeleton build.py
# 2 · BUILD：按骨架原文与判断一次落完；有图时按清单批量出图/登记授权素材
# 3 · VERIFY：终稿全页取证选 strict；快速迭代可用 fast（只看关键页）
python scripts/vao.py check build.py out.pptx --mode release --speed strict
# 含图时为同一条 check 加 --assets-manifest <plan 输出的清单路径>
```

版本差异与关键验证边界见 [CHANGELOG.md](CHANGELOG.md)；完整旧记录可从 Git 历史恢复。
口径照旧：数字只对写明的样本与本机执行负责，不含外部出图或人工构图时间；
没有稳定证据的指标（例如常规稿的 cold 全链路）就写「没有证据」，不写结论。

## 架构（8 个模块 · 一条链）

```
scripts/
  vao.py          唯一生产入口（plan / check / qc / dna）
  intelligence.py 设计智能：判断链 + 视觉世界推导 + 骨架 + 经验记忆（DNA）
  assets.py       资产必要性 → 提示词 → 清单 → 像素 QC → 链核验
  verify.py       硬错误 Guard → PASS/BLOCK → 发布清单
  compiler.py     确定性 PPTX 编译（含编译缓存）
  primitives.py   最小生产原语（身份/字节/几何/颜色/文本测量）
  ghost.py        PIL 结构预览（关键页取证：封面/章节/画心/密数据/收尾）
  render_evidence.py  第三层证据：替代引擎（LibreOffice）实际排版 → 逐页页图 + 摘要
  selftest.py     核心测试（生产路径即测试路径）
```

四层证据不是一回事，谁在哪一层要写清楚：

```
selftest 代码测试 → ghost 结构预览（方向证据，近似字面）
                  → render_evidence 替代引擎实际渲染（真实排版，不是目标 PowerPoint）
                  → 目标 PowerPoint 打开/编辑/另存/重开 → 独立视觉验收
```

第三层缺渲染器时 `render_evidence.py` 明确回报「没有证据」，不会把结构预览
升格成真实渲染；`target_powerpoint / native_editing / independent_visual_review`
在任何自动化结果里都保持未验证。

- **QA 只拦硬错误**：编译失败 / 内容缺失 / 溢出 / 越界 / 重叠 / 无效资产 / 无效图表 /
  来源缺失（release）。输出只有 **PASS / BLOCK**；设计质量由逐页判断与作者审阅负责，
  PIL 结构预览不是 Office 像素忠实证明。
- **生产入口不依赖外部渲染器**：方向证据由 `ghost.py` 给出；实际 PPTX 须在目标 PowerPoint 验收，替代引擎渲染不能冒充目标环境证明。
- **一次算完多处复用**：编译缓存、资产判定复用、预览页缓存、单趟归一化。
- **产物采用原生对象**：文本、形状、图表不是整页截图；是否能在目标 PowerPoint 正常编辑，仍需打开、修改、另存、重开验证。

## Context 纪律（JIT）

| 需要解决的问题 | 读取 |
|---|---|
| 判断卡确有缺口时的校准（焦点/留白/图像/图表/排版/节奏） | `SKILL.md` §2–3（唯一基准） |
| 落 spec 时查字段、元素契约、失败码 | `references/contract.md`（一次） |
| plan 判定确需图像媒体 | `references/assets.md`；无图稿跳过 |

`vao.py plan` 本身是确定性规划，不读 `references/`、不调用模型；brief 内容解析与 SHA-256
共用一次文件读取。正常生产预算是 **1 次 plan + 1 次 release check**，中间不跑
`qc`——release 那一次已经输出预览与发布清单。

## 设计经验记忆（DNA）

`memory/design_dna.json` 只保留**两条历史案例经验**及适用边界；其原始产物未随仓库
收录，当前标为未独立复验，不应把文字案源当成成品证据。通用设计原则只在 `SKILL.md`
维护，不在 DNA 重存配额；已被页级背景契约替代的旧 QC 绕行经验不再召回。
新的条目只收有可核验真实项目证据的例外/经验，关键词匹配不是设计有效性置信度。

```bash
python scripts/vao.py dna --check          # 体检
python scripts/vao.py dna --add entry.json # 沉淀（校验 + 去重 + 原子写入）
```

## 安装

Python 3.10+，零系统级组件：

```bash
pip install -r requirements.txt
python scripts/selftest.py   # 核心测试
```

## 接受基准（`acceptance/`）

一份 8 页的代表性真实成品基准，覆盖封面 / 观点页 / 复杂逻辑页 / 密集数据页 /
图表页 / 中文长文本页 / 图片叠字页 / 收尾页，数据与品牌均虚构：

```bash
cd acceptance
python ../scripts/vao.py check build.py out.pptx --mode release --speed strict \
    --assets-manifest asset_manifest.json --assets-dir assets --preview preview
python ../scripts/render_evidence.py out.pptx --out evidence
```

它同时是设计判断的回归现场：`scripts/selftest.py` 的 `design_judgment` 组把
这一套里出现过的每一次错判都钉成断言（日期被当成证据量、正文换指标顶掉标题结论、
序列坐标被判成跨量纲、请求量被终值压过、坐标进删除清单、单个「先」判成流程、
眉标截成「答案不」……）。差分记录见 `acceptance/REPORT.md`。

## 本轮可复验交付（9.18.0 候选版）

自动化回归与冒烟由 CI 每次 push 实跑：`scripts/selftest.py`（固定自检矩阵，
ubuntu / windows × py3.10 / 3.12 / 3.13，退出码即门槛）与 spec 档冒烟
（断言 `pptx` / `lxml` / `compiler` 不进 `sys.modules`）。结果与运行日志在
Actions 页可查，不在仓库内另存一份报告。

```bash
python scripts/selftest.py                                   # 核心自检矩阵
python scripts/vao.py check build.py out.pptx --mode release --speed strict
```

已声明：350 项自检通过、spec 冒烟通过、结构预览（`ghost.py`，PIL 结构预览，
不是 Office 像素忠实证明）给出方向证据，以及接受基准的**替代引擎实际渲染**
（LibreOffice 25.2，8 页逐页页图 + SHA-256，见 `acceptance/`），
——**自检全绿与替代引擎渲染都不等于视觉质量合格**。
未声明：目标 PowerPoint 视觉终验、原生编辑往返、独立盲评结论、端到端提速。
未声明项的状态见下方「当前验证边界」。

## 当前验证边界（9.17.1）

- **已做**：自动化回归、独立 spec 冒烟、结构预览（非 Office 像素证明）、本机计时基线。
- **已做（9.18.0 新增）**：替代引擎（LibreOffice）对接受基准 PPTX 的实际排版与
  逐页栅格化，凭证含引擎版本与逐页 SHA-256，并可重跑复验；同引擎重跑页图逐字节一致。
- **未做**：目标 Microsoft PowerPoint 的实际打开 / 编辑 / 另存 / 重开验收；
  独立评审者对匿名 A/B 候选的完成评审；真实品牌或产品场景的泛化验证。
  替代引擎渲染**不构成**目标环境验收：字体回落、自动轴范围与自动换行都可能不同。
- 未完成项不在仓库内留半成品证据目录；评审材料与解盲件按匿名批次在仓库外
  独立保存，评审批次一经发出不重编号、不改阅读顺序。
- 任何"更快""更好"的结论都必须先有独立评审通过的质量等价性；在它成立之前
  不声明提速，也不把版本号当作结果。
