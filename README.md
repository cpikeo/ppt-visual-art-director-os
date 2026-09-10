# PPT Visual Art Director OS

> 一个面向高端商业演示的视觉艺术指导、信息设计与原生可编辑 PPTX 生产技能包。

## 项目定位

`ppt-visual-art-director-os` 不是普通的模板集合，也不是只负责绘制页面的脚本。它把内容理解、商业叙事、视觉策略、空间构图、编辑设计、数据表达、媒体治理和确定性质量检查组织成一条可执行的演示生产链。

它的核心原则是：先明确观众需要理解、相信或决定什么，再决定这件事应该如何被看见。高级感来自精准、克制、秩序、空间与细节，而不是更多装饰。每个元素都必须服务于信息理解、情绪表达、品牌价值或阅读体验；无法说明功能的元素应删除。

本项目适合战略汇报、董事会材料、商业提案、品牌发布、数据叙事、管理层报告、研究结论和高端主题演示等场景。它强调**商业逻辑优先、视觉空间统一、数据表达诚实、生产对象可编辑、发布结果可验证**。

## 核心能力

| 能力 | 说明 |
|---|---|
| 内容到视觉策略 | 将受众、决策、张力、证据和行动转化为 Strategy、Direction 与 Story Map |
| 页面级叙事 | 为每页定义单一 insight、narrative role、focus、reading order、energy、density 和 continuity token |
| 视觉空间设计 | 统一背景、媒体、文字、图表、材质、光线、版心、网格和安全区 |
| 信息与数据设计 | 选择诚实的图表关系，保留单位、期间、比较口径、来源和数据状态 |
| 原生可编辑输出 | 使用 `python-pptx` 生成可编辑文字、形状、图片和图表对象 |
| 确定性治理 | 通过 Guard、Compile、Render Evidence、QA 和 Art Critic 形成发布判断 |
| 最小修正 | 优先采用删除、简化、恢复空间、重构重心，再考虑媒体和装饰微调 |

## 设计标准

项目吸收高端产品发布、顶级咨询报告、专业财经媒体、编辑设计和品牌发布中的可观察行为，但不复制任何机构或品牌模板。引用风格只能帮助理解设计行为，不能替代内容判断。

### 高级感的最小判定

一页完成后，按以下顺序检查：

1. 单一结论是否一眼可见。
2. 标题、核心信息、辅助信息和视觉焦点是否清楚分层。
3. 留白是否承担了阅读、节奏或情绪功能。
4. 背景、媒体、文字和图表是否属于同一个视觉空间。
5. 对齐、间距、边界、图文比例和色彩比例是否自然。
6. 删除某个装饰后，信息表达是否变差；如果没有变差，就删除该装饰。

禁止使用堆叠卡片、无意义渐变、复杂特效、廉价科技符号或随机图片来制造高级感。审美优化不得覆盖事实完整性、数据准确性、可读性或生产契约。

## 静态案例

以下案例图片用于展示本技能包的视觉方向、空间品质与版式参考。它们是静态参考资产，不是固定模板；使用时仍应根据内容、受众、品牌和数据关系重新构图。

| 案例一 | 案例二 |
|---|---|
| ![静态案例一](assets/bb423798bd14650761b3e744dfcd9905.png) | ![静态案例二](assets/af927d8d95970a43eaec3f6cc67102aa.png) |

| 案例三 | 案例四 |
|---|---|
| ![静态案例三](assets/1c2f20c6a78cd5c41dd344397e986f5b.png) | ![静态案例四](assets/ffb347873654bd8176db4d7acbb3bd3d.png) |

案例图片的版权、字体、商标与再分发边界应以用户提供的授权为准；本项目许可证不自动扩展至这些外部资产。

## 目录结构

```text
ppt-visual-art-director-os/
├── SKILL.md
├── LICENSE.txt
├── README.md
├── requirements.txt
├── assets/
│   ├── 1c2f20c6a78cd5c41dd344397e986f5b.png
│   ├── af927d8d95970a43eaec3f6cc67102aa.png
│   ├── bb423798bd14650761b3e744dfcd9905.png
│   └── ffb347873654bd8176db4d7acbb3bd3d.png
├── references/
│   ├── benchmark-calibration.md
│   ├── design-intelligence.md
│   ├── design-system.md
│   ├── evidence-library.md
│   ├── production-contract.md
│   ├── scoring.md
│   └── themes.md
├── scripts/
│   ├── art_critic.py
│   ├── asset_prompt.py
│   ├── charts.py
│   ├── compiler.py
│   ├── elements.py
│   ├── ghost.py
│   ├── guard.py
│   ├── primitives.py
│   ├── qa.py
│   ├── render_check.py
│   ├── route.py
│   └── selftest.py
└── templates/
    └── strategy_direction.yml
```

## 推荐工作流

执行顺序以 `SKILL.md` 的 Director 五步流水线为准（一句话版）：

| 步骤 | 做什么 |
|---|---|
| P1 内容理解 | 冻结输入（受众/决定/口径）+ `route.plan_deck`，不可验证标 `unknown` |
| P2 视觉策略判断 | Strategy + Direction + Story Map + Page Intent，一页一结论 |
| P3 布局决策 | 内容任务定家族 → 写 spec → 媒体闸门（数据页不出图） |
| P4 关键细节优化 | **1 根因 = 1 轮**：`director_verdict.batch.fix_this_round`（同根因杠杆）一次修完一次验证，`deferred` 排队下轮；顺序仍是删除→简化→空间→重心→媒体→装饰 |
| P5 质量检查 | 按执行模式：`--mode draft`（零渲染）→ `--mode review`（关键页∪受影响页，Critic 待布局稳定）→ `--mode release`（= `--manifest` 全量） |

一个最小文字元素示例（完整字段见 `references/production-contract.md` 的 Spec minimum）：

```python
{
    "type": "text",
    "id": "headline",
    "x": 48,
    "y": 48,
    "width": 720,
    "height": 80,
    "text": "单一、可复述的页面结论",
    "size": 32,
    "color": "text",
    "bold": True,
    "line_height": 1.15,
    "max_lines": 2,
    "padding": 0,
}
```

## 运行方式

### 安装依赖

建议使用虚拟环境：

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 先分路，再预检（默认入口）

不确定该用多大复杂度时，让决策层按内容分类，而不是先假设「最高质量」：

```bash
python3 scripts/route.py path/to/brief.yml --json      # 内容 → 路径 / 页面家族 / 密度 / 资产预算（含主题种子色板）
python3 scripts/guard.py path/to/build_mydeck.py --preflight   # 静态预检（0.2s 级，无需渲染）
python3 scripts/ghost.py path/to/build_mydeck.py out_dir       # 迭代预览缩略图（~1ms/页，无需 LibreOffice）
```

`ghost.py` 是迭代内环：不启动 LibreOffice / poppler，直接用 spec 几何 + 色板
粗排出画布缩略图，用于「一眼确认布局 / 色块关系 / 疏密方向」。它是确定性纯函数，
**不参与发布判定**——发布仍以 `render_check` 的真实 PPTX→PDF→PNG 像素证据为准。

`route.py` 只接受 `content_type / design_direction / quality_level`，返回该页的家族、密度、能量、字阶、图像决策与派生方向（背景、材质、光线、图表风格、动效、构图语法）；数据、表格、流程、结构页在闸门上直接判为「不出图」。`guard.py --preflight` 用与 Art Critic 同一组常量提前点名确定性硬门槛，返回 `slide / code / observation / minimal_fix`，因此一轮修改从「渲染 4 秒」压缩到「静态 0.2 秒」。

### 编译 PPTX

`compiler.py` 接受一个定义 `build_spec()` 或顶层 `SPEC` 的 Python 模块：

```bash
python3 scripts/compiler.py path/to/build_mydeck.py output.pptx
```

### 运行静态 Guard

```bash
python3 scripts/guard.py path/to/build_mydeck.py --json
```

### 运行完整 QA

```bash
# V2 三层执行架构（主接口；流程控制，与 Fast/Advanced 预算控制正交）
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --mode draft    # 创作链：Normalizer→Guard→Compile→PPTX，零渲染零 Critic（默认推荐起步）
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --mode review   # 审查链：关键页∪受影响页像素证据；布局稳定后 Critic 自动给 verdict（--critic force 可跳过门控）
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --mode release  # 发布链：全量渲染+QA+Critic+Release Manifest（唯一 PASS 口径）

# legacy 旗标仍是合法别名
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --quick         # ≡ --mode draft
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --key-pages     # ≡ --mode review
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --manifest      # ≡ --mode release
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --fast          # 便宜的全量渲染：dpi 72 + 预检闸门
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --preflight     # 只列可执行修正项

# Normalizer（生产链第 0 级）：网格/token/间距机械归一化，报告留痕、幂等、可退出
python3 scripts/normalizer.py path/to/build_mydeck.py                    # 只看报告
python3 scripts/normalizer.py path/to/build_mydeck.py --write n.json     # 导出归一化 spec
```

渐进层级只改变「测了多少」，不改变「放宽什么」：Level 1/2 的状态上限是 `REVISE`/`PREVIEW_ONLY`，`release_eligible=False`；`qa["performance"]` 与 `qa["render"]["coverage"]` 记录每轮实际测了什么。

渲染并行上限 2 worker，另有 PDF 复用与编译视图复用两层缓存（内容核验，`--no-cache` 绕过）；冷热路径像素质标逐位一致，实测数字口径见 `references/production-contract.md`。

`--fast` / `--preflight` 只改变采样密度与批评轮次，不改变任何阈值；每次运行返回 `performance`，使「省掉的轮次」可核对。

渲染证据（Render Evidence）需要系统级依赖：LibreOffice（`soffice`）将 PPTX 转 PDF，`poppler-utils`（`pdftoppm`）将 PDF 转 PNG。缺少任一项时 `run_qa` 自动降级：不阻塞静态治理，但状态只能是 `PREVIEW_ONLY`，不能发布。`--no-render` 仅用于快速迭代布局，同样不代表发布通过。

具体参数和稳定 API 以 `references/production-contract.md` 为准。脚本不会替调用方自动缩字号、改色、重排、删除内容、伪造数据或替换图片。

### 运行自检

```bash
python3 scripts/selftest.py
```

自检覆盖目录结构、引用完整性（含脚本注释）、模块导入、填充契约、Art Critic 基础返回结构与硬门槛、PASS 可达性回归、渲染锚点解析与主题 Accent 测量，以及一次真实编译两页 mini deck 的 Guard → Compile → QA → Release Manifest 端到端冒烟。发布前仍应对真实 deck 执行完整 Guard、Render Evidence 和 QA。

## 质量与发布门

Deterministic QA 只判断可编译、可渲染、可读、可编辑、无越界、无失真和满足硬约束；Art Critic 独立判断层级、平衡、对齐、对比、节奏、一致性、情绪影响、记忆点和专业完成度。技术分数不能代替设计质量。Art Critic v2 采用证据驱动加减分（基准 3/5，凭可观察证据加减，全部写入 `dimension_evidence`），修复了旧版满分封顶导致 PASS 不可达的缺陷，并按失败码表输出硬门槛（`INTENT_UNCLEAR`、`FOCUS_COMPETING`、`CARD_WALL`、`MEDIA_UNJUSTIFIED`、`RHYTHM_FLAT`、`CRITIC_LOW`）。评分体系与调参口径见 `references/scoring.md`。

以下问题属于发布阻断项：关键文字不可读、文字溢出、未声明遮挡、来源区冲突、事实或数据不完整、图表失真、编译失败、资产侵入安全区以及真实渲染证据缺失。状态只允许为 `PASS`、`REVISE`、`BLOCKED` 或 `PREVIEW_ONLY`。

## 失败码与文字契约

文字元素缺少 `text` 时，Guard 返回 `TEXT_FIELD_MISSING`；使用 `content` 时返回 `TEXT_FIELD_INVALID`；使用嵌套 `style` 时返回 `TEXT_STYLE_INVALID`。编译层同步提供明确提示，避免文本框创建成功但文字内容静默为空。

## 设计边界

本项目不提供品牌资产授权、不替用户核验第三方图片、字体、数据或商标许可，也不把风格参考名称当作可复制模板。使用者必须自行确认输入材料、外部资产和依赖的适用授权。

本项目不会访问用户的外部账户，不会替调用方提交、发布或购买内容。所有输出都应在最终使用前由责任人检查事实、版式、字体、素材、版权和目标软件兼容性。

## 版本与验证状态

基于 v9 优化版整理为 `ppt-visual-art-director-os`：

- **v2.3 少跑一轮**：PDF / 编译视图两层复用 + deck 级色彩与图表纪律（色相族预算、强调角距离、脏渐变提示、图表样式漂移）+ 焦点落位轴线判定。
- **评分链路**：Art Critic v2.0（证据驱动加减分、真实失败码、PASS 可达）、Render Evidence v1.1、QA v1.2；`route.py` 决策层、Guard 静态预检、背景层直接叠加合同；`compile_deck / run_qa / critique_deck / release_manifest / check_spec` 向后兼容。
- **v2.4 Director 升级**：`director_verdict` 首要杠杆（`critic_version` 2.2）、3–4 容器 `CARD_DENSITY` 软压、三处判定收敛到 `primitives.py`、证据记 `saliency_method` 且缓存键升 v4。
- **v2.5 三层执行架构**：Execution Modes（draft/review/release 流程控制，发布级管线从默认路径降级为按需触发）；`normalizer.py` 生产链第 0 级（网格吸附/色彩字体 token 归一/间距吸附，Guard 从发现器变确认器）；SKILL.md Runtime Contract Map（字段级契约索引，从「grep 考古」到「一次定位」）；Revision Batch Intelligence（1 根因 = 1 轮批量修正）；Critic 稳定性门控（连续两轮 clean 且几何未变才介入，结果按 spec 指纹缓存）；语义变更分类器（narrative/page_render/full_render → 决定渲染集）。
- **验证**：30 项自检 PASS；12 页实测预检 0.2s，Level 1 迭代 0.03s，Level 2 冷 3.7s／热 0.0s，Level 3 冷 4.7s／复跑 0.0s，声明轮 0.01s；QA 98.4 / Critic 94.2 / Manifest 全部 PASS。
- **发布门可自证**：缓存内容核验、背景层免检资格、像素实测对比、报告清单互核——四类蒙混路径一律 fail closed。

## 许可证

本项目采用 MIT License。许可证仅覆盖本项目代码与文档本身；第三方字体、图片、数据、商标、外部引用和生成资产不当然包含在本项目授权内。详见 [LICENSE.txt](LICENSE.txt)。
