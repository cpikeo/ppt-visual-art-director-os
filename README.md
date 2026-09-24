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

真实 [端到端 Before/After 审计](PERFORMANCE_AUDIT.md) 区分进程 wall/CPU、分阶段耗时、
命令次数、I/O、图片 QC/缓存和逐页视觉证据；只对测试环境与样本负责，不含外部 AI 出图或人工设计时间。

## 架构（8 个模块 · 一条链）

```
scripts/
  vao.py          唯一生产入口（plan / check / preview / dna）
  intelligence.py 设计智能：判断链 + 视觉世界推导 + 骨架 + 经验记忆（DNA）
  assets.py       资产必要性 → 提示词 → 清单 → 像素 QC → 链核验
  verify.py       硬错误 Guard → PASS/BLOCK → 发布清单
  compiler.py     确定性 PPTX 编译（含编译缓存）
  primitives.py   最小生产原语（身份/字节/几何/颜色/文本测量）
  ghost.py        PIL 结构预览（关键页取证：封面/章节/画心/密数据/收尾）
  selftest.py     核心测试（生产路径即测试路径）
```

- **QA 只拦硬错误**：编译失败 / 内容缺失 / 溢出 / 越界 / 重叠 / 无效资产 / 无效图表 /
  来源缺失（release）。输出只有 **PASS / BLOCK**；设计质量由逐页判断与作者审阅负责，
  PIL 结构预览不是 Office 像素忠实证明。
- **不调用 LibreOffice / soffice / poppler**：方向证据由 `ghost.py` 的确定性结构预览给出。
- **一次算完多处复用**：编译缓存、资产判定复用、预览页缓存、单趟归一化。
- **PPT 全程原生可编辑**：文本、形状、图表在 PowerPoint 对象模型中可直接修改。

## Context 纪律（JIT）

| 需要解决的问题 | 读取 |
|---|---|
| 判断卡确有缺口时的校准（焦点/留白/图像/图表/排版/节奏） | `references/judgment.md`（按需） |
| 落 spec 时查字段、元素契约、失败码 | `references/contract.md`（一次） |
| plan 判定确需图像媒体 | `references/assets.md`；无图稿跳过 |

`vao.py plan` 本身是确定性规划，不读 `references/`、不调用模型；brief 内容解析与 SHA-256
共用一次文件读取。正常生产预算是 **1 次 plan + 1 次 release check**，不在中间再跑
`qc`/`preview`；release 已输出关键页预览与发布清单。

## 设计经验记忆（DNA）

`memory/design_dna.json` 记录判断有效的条件、失效边界与可验证出处；当前有**九条通用
原则 + 两条真实案例经验**，不记坐标/色值/版式结果。DNA 是经验库不是第二套
judgment：通用原则冻结、只修错；新的条目只收经真实项目验证的例外/经验。

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
