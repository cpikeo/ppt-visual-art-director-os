# PPT Visual Art Director OS

**内容 → 逐页判断 → 原生可编辑 PPTX。** 单入口、一次判断、一次收口。

它是 Skill / 设计智能，不是设计系统、组件库、模板引擎或样式预设。它做的是**判断**：
这一页要让观众记住什么、为什么这样呈现、哪些东西必须删除。判断基准全部在 [SKILL.md](SKILL.md)。

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
```

brief 模板见 [templates/brief.yml](templates/brief.yml)。
素材判断与人工验收见 `SKILL.md §3 / §6`：先内容与构图，后选材；无图同样成立，不预设 3D、细线图标或配图数量。
素材执行字段、生成/既有素材路径与 QC 边界见 `references/assets.md`。

## 结构

```
scripts/
  vao.py              唯一入口（plan / check / qc）
  intelligence.py     设计判断：判断链、视觉世界推导、骨架生成
  assets.py           资产必要性 → 提示词 → 清单 → 像素 QC → 链核验
  verify.py           硬错误 Guard → PASS / BLOCK → 发布清单
  compiler.py         确定性 PPTX 编译（含编译缓存）
  primitives.py       最小原语（身份 / 字节 / 几何 / 颜色 / 文本测量 / 图表单一规范 CHART_SPEC）
  ghost.py            PIL 结构预览（关键页取证）
  bench.py            判断基准与盲评通道（不进生产入口）
  json/               judgment_cases.json（57 例判断回归）及四组冻结泛化 JSON（不进生产入口）
  selftest.py         核心自检
references/           contract.md（字段与失败码）、assets.md（资产链）
```

Context 按需读取：判断校准读 `SKILL.md §2–3`；写 spec 读 `references/contract.md`；
判定需要图像时才读 `references/assets.md`。`plan` 本身不读 references，也不调用模型。

## 质量边界

- **QA 只拦硬错误**：编译失败、内容缺失、溢出、越界、重叠、无效资产 / 图表、来源缺失（release）。
  输出只有 PASS / BLOCK；设计质量由逐页判断与作者审阅负责。
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

- `build.py` / Python brief 是**可信作者代码**，不是沙箱；不应执行未知来源 Python。
- 预览目录、编译缓存目录须专用，不能包含当轮输入/交付物或彼此嵌套；现存 symlink/hardlink 子项会被拒绝。路径冲突在诊断写入前拒绝，退出 2，以免“错误报告”覆盖原稿。
- release 完成安全路径预检后，先原子写入未完成的 BLOCKED 清单，再编译/预览；中断不能继续使用旧 PASS。Ctrl-C 退出 130，作者 `SystemExit(0)` 不算成功（CLI 退出 2）。SIGTERM/SIGKILL 没有补写诊断的保证；预检前被杀、同一输出并发与敌对目录竞态不在此保证内。
- 图片链须有真实 brief 文件、匹配的 SHA-256 与 `vao-asset-chain-v2` 标识；仅有路径或清单摘要不算来源凭据。brief 改变后须重跑 plan，而非手改摘要绕过来源链。
- 图表只能使用 `data` 或 `categories + series` 之一；旧 `data` 加冗余 `categories`、没有 `series` 的输入仍兼容。非法双载荷不再静默丢弃一个数据源。
- 图片透明通道和 `contain` 留白保留透明，`crop` 由 Guard / 编译 / ghost 共用校验与几何；ghost 仍只证明结构方向，不等于目标软件渲染。PNG 解码校验也不认证图片的事实或视觉正确性。
- 测试工具的 `--out` 不得覆盖案例/基线；盲评导出目录不能位于待评输入树内，映射 key 不能覆盖待评原件。多文件导出不是一个全局事务。盲评须使用空目录和新 key，防止残留旧版本；评分完整性按 key 全集核验，非有限数、未知版本与重复评分均拒绝。

### 判断基准

判断回归案例合并在 `scripts/json/judgment_cases.json`：保留四组共 57 个案例、各组来源说明以及七页规划回归输入。

```bash
python scripts/bench.py             # 57 个判断案例；任一失败返回非零
python scripts/selftest.py          # 同时检查负例退出码、缓存、素材复用和结构产物
```

判断基准只检查页面角色、证据形态、结论来源/文本、图像决策等字段；**不证明构图、断行或视觉美感**。历史分组、旧基线与已移除的样稿/审计记录可从 Git 历史恢复。

## 测试

```bash
python scripts/selftest.py   # 退出码即门槛；数量以实际输出为准
```

本工作树按用户要求移除了 `acceptance/`、`review/`、`audit/`、`benchmark/` 目录，
以及 `交付报告.md`、`泛化评测报告.md` 等报告工件；因此当前仓库**不包含样稿、
真实渲染、验收单或评测报告**。早期目录可在 Git 历史中找回；后期未进 Git 的工件
（成品样品、评测存档等）删除后不可恢复，本版不得据其宣称视觉验收结果。
`plan` 只输出设计判断与**空元素骨架**，作者须完成 BUILD；不得以本地自测通过宣称自主落版或目标 PowerPoint 视觉终验。

CI（`.github/workflows/ci.yml`）配置 ubuntu / windows × Python 3.10 / 3.12 / 3.13 自检、57 例判断回归、四组冻结泛化评测及 spec 档冒烟；另有 ubuntu / Python 3.10 的声明依赖下限组合。配置变更不代表远端已运行。
工作树中若有未推送的改动（见 [CHANGELOG](CHANGELOG.md) 最新条目），**只能按本地结果报告，不能把本地通过当作远端 CI 全绿**；
本地验证范围须以当次实际运行记录为准，不能由配置推断其他平台或依赖组合通过。

文件覆盖保护、可信 Python 输入、并发与中断边界见 [执行契约](references/contract.md#文件与信任边界)。

## 版本与历史

版本差异与验证边界见 [CHANGELOG.md](CHANGELOG.md)。历史数据、被删除的旧模块与旧经验记录可从 Git 历史恢复。

License: MIT（见 [LICENSE.txt](LICENSE.txt)）
