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
内容理解 → 受众 → 决策 → 结论抽取 → 信息权重 → 视觉角色
        → 焦点判定 → 构图推理 → 空间结构 → 媒体必要性 → 生产规格
        → 跨页校准（整套回看：节奏回拨 + 图位执行，不新增判断字段）
```

每个判断都带理由；每个形式选择都带**被否掉的替代项与理由**。视觉世界（纸/墨/强调语义/
材质/光/字体语气）由内容推导，不查风格预设表——相同内容类型允许产生不同视觉结果。

## 生产路径

```bash
# 1 · THINK
python scripts/vao.py plan brief.yml --out plan.json --skeleton build.py \
    --assets-out asset_manifest.json --assets-dir generated_assets
# 2 · BUILD：按清单出图（外部工具），按骨架注释落元素
# 3 · VERIFY
python scripts/vao.py check build.py out.pptx --mode release --assets-manifest asset_manifest.json
```

12 页稿件在本机实测：冷启动 release ≈ 0.4s，缓存命中 ≈ 0.03s（`--speed fast` 默认）。

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
  来源缺失（release）。输出只有 **PASS / BLOCK**。
- **不调用 LibreOffice / soffice / poppler**：方向证据由 `ghost.py` 的确定性结构预览给出。
- **一次算完多处复用**：编译缓存、资产判定复用、预览页缓存、单趟归一化。
- **PPT 全程原生可编辑**：文本、形状、图表在 PowerPoint 对象模型中可直接修改。

## Context 纪律（JIT）

| 需要解决的问题 | 读取 |
|---|---|
| 判断校准（焦点/留白/图像/图表/排版/节奏） | `references/judgment.md` |
| 精确 spec 字段、元素契约、失败码 | `references/contract.md` |
| 资产必要性、提示词、QC、既有文件 | `references/assets.md` |

## 设计经验记忆（DNA）

`memory/design_dna.json` 只记录「为什么某个设计判断有效」——九条高迁移原则，
不记坐标、不记色值、不记版式结果。规划时自动召回，release 通过后鼓励沉淀：

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
