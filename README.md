# PPT Visual Art Director OS

> 一个面向高端商业演示的视觉艺术指导、信息设计与原生可编辑 PPTX 生产技能包。

## 项目定位

`ppt-visual-art-director-os` 不是模板集合，也不是只负责绘制页面的脚本。它把内容理解、商业叙事、视觉策略、空间构图、编辑设计、数据表达、媒体治理和确定性质量检查组织成一条可执行的演示生产链——按「**理解内容 → 判断设计意图 → 预测视觉问题 → 选择设计策略 → 生成高质量页面**」一次通过，而不是生成后反复修复。

它强调**商业逻辑优先、视觉空间统一、数据表达诚实、生产对象可编辑、发布结果可验证**，适合战略汇报、董事会材料、商业提案、品牌发布、数据叙事、研究结论与高端主题演示。设计哲学、质量判定与执行纪律以 `SKILL.md` 为唯一权威：高级感来自精准、克制、秩序、空间与细节，而不是更多装饰。

## 核心能力

| 能力 | 说明 |
|---|---|
| 内容到视觉策略 | 将受众、决策、张力、证据和行动转化为 Strategy、Direction 与 Story Map |
| 页面级叙事 | 为每页定义单一 insight、narrative role、focus、reading order、energy、density 与 continuity token |
| 视觉空间设计 | 统一背景、媒体、文字、图表、材质、光线、版心、网格和安全区 |
| 信息与数据设计 | 选择诚实的图表关系，保留单位、期间、比较口径、来源和数据状态 |
| 原生可编辑输出 | 使用 `python-pptx` 生成可编辑文字、形状、图片和图表对象 |
| 确定性治理 | Guard、Compile、Render Evidence、QA、Art Critic 与**生成前 Pre-Critic 风险预测**形成发布判断 |
| 最小修正 | 优先采用删除、简化、恢复空间、重构重心，再考虑媒体和装饰微调 |

## 设计标准

项目吸收高端产品发布、顶级咨询报告、专业财经媒体、编辑设计和品牌发布中的可观察行为，但不复制任何机构或品牌模板；引用风格只能帮助理解设计行为，不能替代内容判断。「高级感的最小判定」六问验收、禁止事项与取舍优先级见 `SKILL.md` 与 `references/design-intelligence.md`（Design Judgment）。禁止使用堆叠卡片、无意义渐变、复杂特效、廉价科技符号或随机图片制造高级感；审美优化不得覆盖事实完整性、数据准确性、可读性或生产契约。

## 静态案例

以下案例图片展示本技能包的视觉方向、空间品质与版式参考。它们是静态参考资产，不是固定模板；使用时仍应根据内容、受众、品牌和数据关系重新构图。

| 案例一 | 案例二 |
|---|---|
| ![静态案例一](assets/bb423798bd14650761b3e744dfcd9905.png) | ![静态案例二](assets/af927d8d95970a43eaec3f6cc67102aa.png) |

| 案例三 | 案例四 |
|---|---|
| ![静态案例三](assets/1c2f20c6a78cd5c41dd344397e986f5b.png) | ![静态案例四](assets/ffb347873654bd8176db4d7acbb3bd3d.png) |

案例图片的版权、字体、商标与再分发边界以用户提供的授权为准；本项目许可证不自动扩展至这些外部资产。

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
├── memory/
│   └── design_dna.json          # Design Reasoning Memory（设计推理记忆）
├── references/
│   ├── benchmark-calibration.md
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
│   ├── design_intelligence.py   # V3：DNA / 媒体决策 / 质量预算 / Pre-Critic / auto_fit
│   ├── elements.py
│   ├── ghost.py
│   ├── guard.py
│   ├── layout_search.py         # V3：Layout Grammar 三候选 spec 级搜索
│   ├── normalizer.py            # V2：生产链第 0 级机械归一化
│   ├── primitives.py
│   ├── qa.py
│   ├── render_check.py
│   ├── route.py
│   └── selftest.py
└── templates/
    └── strategy_direction.yml
```

## 推荐工作流

执行顺序以 `SKILL.md` 的 Director 五步流水线为准：**P1 内容理解 → P2 视觉策略判断（Strategy / Direction / Page Intent，一页一结论）→ P3 布局决策（家族 + spec + 媒体闸门）→ P4 关键细节优化（1 根因 = 1 轮批量修正）→ P5 质量检查（draft / review / release 三模式）**。逐步完成标准、上下文路由与契约索引详见 `SKILL.md`。

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
python3 scripts/route.py path/to/brief.yml --json      # 内容 → 路径 / 页面家族 / 密度 / 资产预算（含 DNA 召回与主题种子色板）
python3 scripts/guard.py path/to/build_mydeck.py --preflight   # 静态预检（0.2s 级，无需渲染）
python3 scripts/ghost.py path/to/build_mydeck.py out_dir       # 迭代预览缩略图（~1ms/页，无需 LibreOffice）
```

`ghost.py` 是迭代内环：不启动 LibreOffice / poppler，直接用 spec 几何 + 色板粗排出画布缩略图，用于「一眼确认布局 / 色块关系 / 疏密方向」。它是确定性纯函数，**不参与发布判定**——发布仍以 `render_check` 的真实 PPTX→PDF→PNG 像素证据为准。

`route.py` 只接受 `content_type / design_direction / quality_level`，返回该页的家族、密度、能量、字阶、图像决策与派生方向（背景、材质、光线、图表风格、动效、构图语法）；数据、表格、流程、结构页在闸门上直接判为「不出图」。`guard.py --preflight` 用与 Art Critic 同一组常量提前点名确定性硬门槛，返回 `slide / code / observation / minimal_fix`，因此一轮修改从「渲染 4 秒」压缩到「静态 0.2 秒」。

### 编译 PPTX

`compiler.py` 接受一个定义 `build_spec()` 或顶层 `SPEC` 的 Python 模块：

```bash
python3 scripts/compiler.py path/to/build_mydeck.py output.pptx
```

### 运行完整 QA

```bash
# 三层执行架构（主接口；流程控制，与 Fast/Advanced 预算控制正交）
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --mode draft    # 创作链：Normalizer→Guard→Compile→PPTX，零渲染零 Critic（默认起步）
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --mode review   # 审查链：关键页∪受影响页像素证据；布局稳定后 Critic 自动给 verdict
python3 scripts/qa.py path/to/build_mydeck.py output.pptx --mode release  # 发布链：全量渲染+QA+Critic+Release Manifest（唯一 PASS 口径）

# legacy 旗标仍是合法别名：--quick ≡ draft、--key-pages ≡ review、--manifest ≡ release；
# 另有 --fast（dpi 72 便宜全量）、--preflight（只列修正项）、--no-cache（绝对冷测）。

# Normalizer（生产链第 0 级）：网格/token/间距机械归一化，报告留痕、幂等、可退出
python3 scripts/normalizer.py path/to/build_mydeck.py                    # 只看报告
python3 scripts/normalizer.py path/to/build_mydeck.py --write n.json     # 导出归一化 spec
```

渐进层级只改变「测了多少」，不改变「放宽什么」：Level 1/2 的状态上限是 `REVISE`/`PREVIEW_ONLY`，`release_eligible=False`；`qa["performance"]` 与 `qa["render"]["coverage"]` 记录每轮实际测了什么。渲染并行上限 2 worker，另有 PDF 复用与编译视图复用两层缓存（内容核验，`--no-cache` 绕过）；实测数字口径见 `references/production-contract.md`。

渲染证据（Render Evidence）需要系统级依赖：LibreOffice（`soffice`）将 PPTX 转 PDF，`poppler-utils`（`pdftoppm`）将 PDF 转 PNG。缺少任一项时 `run_qa` 自动降级：不阻塞静态治理，但状态只能是 `PREVIEW_ONLY`，不能发布。

具体参数和稳定 API 以 `references/production-contract.md` 为准。脚本不会替调用方自动缩字号、改色、重排、删除内容、伪造数据或替换图片。

### 运行自检

```bash
python3 scripts/selftest.py
```

自检覆盖结构/引用完整性、Critic 返回结构与证据消费、PASS 可达性、Normalizer 幂等、执行模式与语义分类、V3 智能层（DNA / 版式搜索 / auto_fit）、端到端冒烟与红队项（缓存核验、对比门禁、清单自证等）。发布前仍应对真实 deck 执行完整 Guard、Render Evidence 和 QA。

## 质量与发布门

Deterministic QA 只判断可编译、可渲染、可读、可编辑、无越界、无失真和满足硬约束；Art Critic 独立判断层级、平衡、对齐、对比、节奏、一致性、情绪影响、记忆点和专业完成度（证据驱动加减分，全部可溯源）。技术分数不能代替设计质量。发布阻断项：关键文字不可读、文字溢出、未声明遮挡、来源区冲突、事实或数据不完整、图表失真、编译失败、资产侵入安全区、真实渲染证据缺失。状态只允许 `PASS`、`REVISE`、`BLOCKED`、`PREVIEW_ONLY`。失败码总表与 Manifest 验收规则见 `references/production-contract.md`。

## 失败码与文字契约

文字元素缺少 `text` 时 Guard 返回 `TEXT_FIELD_MISSING`；使用 `content` 返回 `TEXT_FIELD_INVALID`；嵌套 `style` 返回 `TEXT_STYLE_INVALID`。编译层同步给出明确提示，避免文本框创建成功但文字静默为空。

## 设计边界

本项目不提供品牌资产授权、不替用户核验第三方图片、字体、数据或商标许可，也不把风格参考名称当作可复制模板。使用者必须自行确认输入材料、外部资产和依赖的适用授权。

本项目不会访问用户的外部账户，不会替调用方提交、发布或购买内容。所有输出都应在最终使用前由责任人检查事实、版式、字体、素材、版权和目标软件兼容性。

## 版本与验证状态

判定演进史与路线图以本节为唯一档案（评分体系与调参见 `references/production-contract.md`）：

- **v2 评分可用**：Critic 从「只扣不加」改为证据驱动加减分（基准 3/5，逐条 `dimension_evidence`，PASS 可达）；硬门槛携带真实失败码；QA 分域扣分明细；渲染锚点对齐声明意图。
- **v2.2 判定可信**：缓存按内容核验（串页/篡改/无指纹一律拒绝）；背景层免检需要资格（`BACKGROUND_DISGUISED` 阻断）；文字对比按渲染像素实测（`READABILITY_FAIL`）；节奏看实测墨迹；QA / Critic 各盖 `source_spec_hash` 交叉校验。
- **v2.3 少跑一轮**：PDF / 编译视图两层复用（只改声明字段的一轮 4.8s → 0.01s）+ deck 级色彩与图表纪律（色相族预算、强调角距离、脏渐变提示、图表样式漂移）+ 焦点落位轴线判定。
- **v2.4 Director 升级**：`director_verdict` 首要杠杆（`critic_version` 2.2）、3–4 容器 `CARD_DENSITY` 软压、三处重复判定收敛到 `primitives.py`、证据记 `saliency_method` 且缓存键升 v4、SKILL 十步清单收敛为 Director 五步。
- **v2.5 三层执行架构**：Execution Modes（draft/review/release 流程控制，发布级管线按需触发）；`normalizer.py` 生产链第 0 级；SKILL.md Runtime Contract Map（字段级契约索引）；Revision Batch Intelligence（1 根因 = 1 轮）；Critic 稳定性门控；语义变更分类器。
- **v2.6 Design Intelligence（V3）**：`design_intelligence.py`（Design DNA 记忆 `memory/design_dna.json` / 媒体决策模型 / 页面质量预算 / **Pre-Critic 生成前风险预测**——V1 项目 6 轮渲染返工的失败类型，生成前 1ms 内全部预测到）+ `layout_search.py`（Layout Grammar 三候选 spec 级搜索）+ `auto_fit` 智能文本阶梯 + route 内联 DNA 召回；流程升级为「理解→预测→决策→生成→一次通过」。
- **v2.7 文档智能密度优化**：Markdown 全库唯一真源制（字阶归 `design-intelligence.md`、哲学与流程归 `SKILL.md`、历史归本节）；修复字阶三源矛盾；新增构图算子（反模板）、Design Intent 决策理由层、中文排印 Craft、分组语法（卡片准入三条件）、微距规则冲突仲裁、主题混血边界；评分参考文档实义字符 −52%；Design DNA 记忆升级为「问题→原因→决策→视觉结果→规律」推理链并补 `when_not_to` 反适用域。
- **v2.8 文档架构收敛（本轮）**：评分架构参考文档解散——评分体系总览与调参并入 `references/production-contract.md`（权威唯一），开放建议移入下方路线图；除本 README 外全部文档移除版本号叙事（架构按能力命名，演进史只在本文档）；`primitives.py` 同步清理一处指向已删文档的注释指针（零行为变更）；参考文档数 8 → 7。
- **v2.9 快速生成默认化（本轮）**：`qa.py` CLI 不传 `--mode` 时默认 draft（快速生成：零渲染、秒级、pre-critic 风险首屏），与 `route.recommend_mode` 默认及全部文档口径对齐；显式 `--level N` / `--fast` 维持 legacy 全量行为。
- **v2.10 渲染级光学对齐 + 校准闭环工具（本轮）**：`render_check.optical_alignment`（声明轴线视觉峰位带内匹配，键代次升 v6）→ Critic alignment 纯加分项（`critic_version` 2.3，跨版本不可比；结果缓存命中加版本校验，防跨算法陈旧判定）；`scripts/calibrate.py`（只测量不改动：标注模板 / Pearson / 错杀漏放 / 阈值反推 / 样本守门）。实测：deck2026 critic 90.9 → 91.1（9/11 页光学加分，2 处单线 4–6px 偏移被点名），QA/manifest 不变。
- **v2.11 判断记忆与角色化色彩（本轮）**：DNA Schema v2（design_problem + judgment + avoid；palette/色值等结果记忆字段拒收，实测证据入 proven——判断跨主题迁移，结果不）；品牌色优先（`brief.brand_colors` 入口即覆盖方向预设，「科技=蓝」式映射被切断）；Chart Color Role System（`theme.chart_palette` 语义角色 primary/secondary/neutral/accent/negative，元素 `color_role`/`series_roles`，柱状负值自动染 negative）；两层布局决策（`layout_search.recommend`：标准家族直达原型，复杂页才三候选搜索）；Asset Intent Cache（`recall_prompt_dna`/`record_prompt_dna`：缓存出图判断，不缓存图片、不存色值）；`--mode sketch` 草图链（探索期只守 error 级，设计契约免除，状态 SKETCH 不可发布）。回归：deck2026 四模式 sketch 98.0 / draft 97.5 / release 99.5·critic 91.1 与 v2.10 逐位一致（向后兼容零破坏）。
- **v2.12 推理降频与预测升级（本轮）**：**速度**——`route.deck_decision`（Deck Decision Card：叙事弧线/密度曲线/媒体政策/执行模式一次固化，页面继承）+ `design_intelligence.page_intent_skeleton`（家族意图骨架，AI 只填 insight/focus，覆盖永远赢）+ `layout_search.recommend` 内容家族经 `normalize_family` 归一直达快速通道（补 TIMELINE）；**智能**——pre-critic 新增 4 族 5 码（BALANCE_SKEW 墨量质心偏轴预测 gravity_drift、TYPE_LADDER 页级 >4 字号、TYPE_SCALE_DRIFT deck 级字阶漂移、LAYOUT_MONOTONE 连续 ≥3 页同布局指纹、CONTINUITY_BROKEN 记忆线单点不成线），deck2026 实测零误报 + 1 条真实发现（13 字号漂移）；**缺陷修复**——v2.11 负值染色在无负值时也解析 negative 角色导致误告警（编译缓存曾掩盖，沙箱轮换暴露）→ 惰性解析；编译缓存补 `COMPILER_VERSION` 版本闸（与 critic 版本闸同构）。回归：deck2026 四模式 98.0/97.5/99.5·91.1 PASS 与基线逐位一致。
- **验证**：51 项自检全 PASS；12 页基准实测预检 0.2s、Level 1 迭代 0.03s、Level 3 冷 4.7s／复跑 0.0s、声明轮 0.01s（QA 98.4 / Critic 94.2 / Manifest PASS）；真实项目「2026 年度总结」11 页 QA 99.5 / Critic 90.9 / 6 轮修订收敛。
- **发布门可自证**：缓存内容核验、背景层免检资格、像素实测对比、报告清单互核——四类蒙混路径一律 fail closed。

## 路线图（开放优化建议）

1. ~~光学对齐的渲染级复核~~ **已完成**：`render_check.optical_alignment`——声明轴线（shape/chart/image 边界）带内匹配（±2px 有真实边缘=对齐、窗口内有带内无=偏移、无边缘=不可验证），≥3 根可验证且一致率 ≥75% 记 Critic alignment 加分；实测 deck2026 9/11 页获加分并暴露 2 处单线 4–6px 偏移。
2. **QA 分域扣分上限**：长 deck 的 hint 级条目线性累计，60 页比 12 页更容易被扣到低分。建议 `run_qa` 增加可选 `penalties_cap={"guard": 30, "compile": 20, "render": 15}`，扣满即止并在 items 标注「已达上限」。
3. **accent 色距阈值主题化**：`measure_image` 的色距阈值对高饱和 Accent 与低饱和金属色灵敏度不同；面积预算已主题化（`accent_max`），色距阈值建议并入 `theme.constraints.accent_distance`。
4. **阈值校准闭环**（决定审美上限）：工具已就位（`scripts/calibrate.py`：标注模板 / Pearson 与错杀漏放 / 逐特征阈值反推 / 样本守门），方法见 `references/benchmark-calibration.md`。**待人工标注**：deck2026 的 11 页模板已生成（`calibration_labels.json`），凑齐好:中:差 ≈ 1:1:1 的 30 页即可首轮校准——这是「分数好看」与「审美可信」之间唯一尚未打通的环节。
5. **报告版本可比性**：`critic_version` / `qa_version` 已随每次升级演进，跨版本分数不可直接比较。建议 revision_log 记录评分器版本，Release Manifest 增加 `qa_version` 字段。
6. **CI 依赖版本锁定**：显著图等测量行为依赖 cv2 可用性（已进证据与缓存键），CI 固定依赖版本可让跨机器分数可比。

## 许可证

本项目采用 MIT License。许可证仅覆盖本项目代码与文档本身；第三方字体、图片、数据、商标、外部引用和生成资产不当然包含在本项目授权内。详见 [LICENSE.txt](LICENSE.txt)。
