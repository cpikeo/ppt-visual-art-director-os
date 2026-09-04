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
| ![静态案例一](assets/1c2f20c6a78cd5c41dd344397e986f5b.png) | ![静态案例二](assets/af927d8d95970a43eaec3f6cc67102aa.png) |

| 案例三 | 案例四 |
|---|---|
| ![静态案例三](assets/bb423798bd14650761b3e744dfcd9905.png) | ![静态案例四](assets/ffb347873654bd8176db4d7acbb3bd3d.png) |

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
│   ├── design-intelligence.md
│   ├── design-system.md
│   ├── evidence-library.md
│   ├── production-contract.md
│   └── themes.md
├── scripts/
│   ├── art_critic.py
│   ├── asset_prompt.py
│   ├── charts.py
│   ├── compiler.py
│   ├── elements.py
│   ├── guard.py
│   ├── primitives.py
│   ├── qa.py
│   ├── render_check.py
│   └── selftest.py
└── templates/
    └── strategy_direction.yml
```

## 推荐工作流

### 1. 冻结输入

先记录受众、观看场景、目标决定、页数、交付格式、品牌限制、事实来源、时间、单位、比较口径和不确定性。不可验证的事实必须标记为 `unknown`，不得静默补全。

### 2. 建立 Strategy 与 Direction

将 `claim`、`evidence`、`implication` 和 `action` 分开。然后定义 `visual_world`、`composition_grammar`、`type_voice`、`color_behavior`、`media_role`、`background_scene`、`motion_posture` 和 `forbidden_signals`，使整套 deck 共享同一视觉人格和空间假设。

### 3. 编排 Story Map 与 Page Intent

先安排 `opening → context → problem → insight → evidence → solution → proof → vision → closing` 的叙事阶段，再定义每页的 insight、narrative role、focus、reading order、energy、density、empty space role、page family、rhythm stage 和 continuity token。每页只保留一个可复述结论。

### 4. 生成运行时 spec

主题、页面、背景、图表、来源、文本和叠加层进入统一 spec。所有可见元素必须具有数值 `x`、`y`、`width`、`height`。文字元素必须使用 `text` 字段，字号、颜色、字重、行高、内边距等样式属性放在元素顶层；禁止使用未消费的 `content` 或嵌套 `style`。

一个最小文字元素示例：

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

### 5. 执行生产链

生产链固定为：

```text
Guard → Compile → Render Evidence → Deterministic QA → Art Critic → Revision
```

优先使用 `qa.py` 的完整入口。仅在需要解释某一失败域时调用单独脚本。修改后先重跑受影响页面，发布前再重跑全 deck。

## 运行方式

### 安装依赖

建议使用虚拟环境：

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

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
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --json
```

具体参数和稳定 API 以 `references/production-contract.md` 为准。脚本不会替调用方自动缩字号、改色、重排、删除内容、伪造数据或替换图片。

### 运行自检

```bash
python3 scripts/selftest.py
```

自检覆盖目录结构、引用完整性、模块导入、填充契约和 Art Critic 基础返回结构。发布前仍应对真实 deck 执行完整 Guard、Render Evidence 和 QA。

## 质量与发布门

Deterministic QA 只判断可编译、可渲染、可读、可编辑、无越界、无失真和满足硬约束；Art Critic 独立判断层级、平衡、对齐、对比、节奏、一致性、情绪影响、记忆点和专业完成度。技术分数不能代替设计质量。

以下问题属于发布阻断项：关键文字不可读、文字溢出、未声明遮挡、来源区冲突、事实或数据不完整、图表失真、编译失败、资产侵入安全区以及真实渲染证据缺失。状态只允许为 `PASS`、`REVISE`、`BLOCKED` 或 `PREVIEW_ONLY`。

## 失败码与文字契约

文字元素缺少 `text` 时，Guard 返回 `TEXT_FIELD_MISSING`；使用 `content` 时返回 `TEXT_FIELD_INVALID`；使用嵌套 `style` 时返回 `TEXT_STYLE_INVALID`。编译层同步提供明确提示，避免文本框创建成功但文字内容静默为空。

## 设计边界

本项目不提供品牌资产授权、不替用户核验第三方图片、字体、数据或商标许可，也不把风格参考名称当作可复制模板。使用者必须自行确认输入材料、外部资产和依赖的适用授权。

本项目不会访问用户的外部账户，不会替调用方提交、发布或购买内容。所有输出都应在最终使用前由责任人检查事实、版式、字体、素材、版权和目标软件兼容性。

## 版本与验证状态

当前目录整理为 `ppt-visual-art-director-os`，基于 v9 优化版。已通过技能结构验证、Python 语法检查和项目自检；建议在具体项目中继续使用真实 deck 做渲染级回归。

## 许可证

本项目采用 MIT License。许可证仅覆盖本项目代码与文档本身；第三方字体、图片、数据、商标、外部引用和生成资产不当然包含在本项目授权内。详见 [LICENSE.txt](LICENSE.txt)。
