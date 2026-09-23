# PPT Visual Art Director OS

设计智能优先的 PPT 生产技能包：**内容 → 视觉策略 → 原生可编辑 PPTX**，单入口执行，最小验证。

它是 **Skill / Agent Intelligence / Visual Art Director**——不是设计系统、不是组件库、
不是模板引擎。它把「生成 → 检查 → 逐条修复 → 再生成」压缩为：

```
THINK（plan，一次）→ BUILD（作者填骨架）→ VERIFY（check，一次收口）
```

## 唯一决策链

```
Audience → Decision → Claim → Tension → Focus → Form → Space → Media → Spec
```

- `family` 只辅助路由（锚点词汇 / 媒体闸门 / 形态问题校准），不套用页面；
- `density` 由作者声明或成稿测量，规划层不预定——**相同内容不默认产生相同布局**；
- `asset` 必须经过必要性判断（置信度 + 理由），作者声明永远压过判断；
- 规划产出的是**逐页判断问题**（本页唯一结论 / 第一落点 / 最诚实的形式 / 留白职责），
  答案由内容决定；几何与构图永远归生成侧。

## 生产路径（约 2 分钟内完成 10–15 页）

```bash
# 1 · THINK：一次规划（判断面 plan.json + 骨架 build.py + 资产清单）
python scripts/vao.py plan brief.yml --out plan.json --skeleton build.py \
    --assets-out asset_manifest.json --assets-dir generated_assets

# 2 · BUILD：按清单 prompt/negative 出图（外部工具），填骨架
#      （先回答每页判断四问，再写元素；字段速查 → references/contract.md）

# 3 · VERIFY：一次收口（normalize → guard → compile → 预览 → PASS/BLOCK）
python scripts/vao.py check build.py out.pptx --mode release --assets-manifest asset_manifest.json
```

纯原生稿件不需要资产清单。`--mode draft` 用于迭代构图；干净稿直接 release。
速度档 `--speed fast`（默认）/ `strict` 只影响证据预算，不影响判定口径。

## 架构（8 个模块 · 一条链）

```
scripts/
  vao.py          唯一生产入口（plan / check / preview / dna）
  intelligence.py brief 加载 → 决策链 → 判断面 → 骨架（含 Design DNA 记忆）
  assets.py       资产判断 → 提示词 → 清单 → 像素 QC → 链核验
  verify.py       硬错误 Guard → PASS/BLOCK 判定 → 发布清单
  compiler.py     确定性 PPTX 编译（含编译缓存）
  primitives.py   最小生产原语（颜色/文本/几何/身份）
  ghost.py        PIL 结构预览（方向证据渲染器，零外部依赖）
  selftest.py     核心测试（生产路径即测试路径）
```

- **QA 只拦截生产级硬错误**：编译失败 / 内容缺失 / 溢出 / 越界 / 重叠 / 无效资产 /
  无效图表 / 来源缺失（release）。输出只有 **PASS / BLOCK**；warning 只进 trace，
  不进对话，不构成修复循环。
- **不调用 LibreOffice / soffice / poppler**：方向证据由 `ghost.py` 的确定性结构预览给出。
- **可复用即复用**：编译缓存（同投影 + 同产物字节戳 ⇒ 不重编）、资产判定复用
  （同清单 + 同像素口径 + 同字节身份 ⇒ 不重测）、预览页缓存（改一页只画一页）。
- **PPT 全程原生可编辑**：文本、形状、图表在 PowerPoint 对象模型中可直接修改。

## Context 纪律（JIT）

| 需要解决的问题 | 读取 |
|---|---|
| 设计判断、焦点、留白、字体、图像、图表、节奏 | `references/judgment.md` |
| 精确 spec 字段、元素契约、阻断码、速度档 | `references/contract.md` |
| 资产身份、提示词、QC、既有文件、裁切 | `references/assets.md` |
| 历史案例、DNA 沉淀/召回（仅明确需要时） | `references/precedent.md` |

## 设计经验记忆（DNA）

`memory/design_dna.json` 只记录「为什么某个设计判断有效」——不记坐标、固定颜色、
固定布局、组件模板。规划时自动召回；release PASS 后鼓励沉淀：

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
