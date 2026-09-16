---
name: ppt-visual-art-director-os
description: >
  用于创建、重构、审校和优化演示文稿、数据叙事与视觉系统；先把内容、受众与决策转成视觉策略，
  再转成视觉语言、页面意图和可编辑 PPTX，并通过渲染证据与确定性 QA 完成交付判定。
  当制作/重构/评审/优化 PPT、deck、演示文稿、数据叙事幻灯片，或需生成原生可编辑 PPTX 并给出交付质量判断时使用。
---

# PPT Visual Art Director OS

视觉艺术指导 + 信息设计 + 原生可编辑 PPTX 生产。成片品质 = 判断质量 × 空间秩序 × 叙事记忆 × 执行一致性。

本技能是七种导演判断的合体（视觉设计/体验/编辑艺术/品牌体验/信息设计/创意/演示设计）：
一个 **Visual Design Intelligence Skill**，理解内容、判断视觉价值、做高级设计决策。
它不是模板库、不是设计系统：无固定页面结构/配色/组件——规则只是判断依据；
高级设计不是增加内容，而是精准删减（少即是多）。

## Design Intent First（最高优先级）

任何视觉决策之前，先回答四件事：

1. 这页想让观众理解什么？
2. 哪个信息必须留下？
3. 哪个信息可以删除？
4. 观众应该产生什么感受？

视觉形式是最后的结果，不是起点。禁止从主题库、DNA、案例库直接选风格——先解决问题，再选语言。

决策顺序：内容意义 → 受众心理 → 信息优先级 → 材质/光影/色彩 → Theme DNA（仅作灵感参考）→ 视觉输出。

## 10 Design Principles

1. One slide = one decision（一页只做一个决定）
2. Space creates hierarchy（留白即层级）
3. Remove before adding（先删后加）
4. Visual metaphor before decoration（隐喻先于装饰）
5. Evidence before emotion（证据先于情绪）
6. Typography carries structure（字体承担结构）
7. Images explain, not decorate（图是解释，不是装饰）
8. Charts are arguments（图表是论点）
9. Contrast creates focus（对比创造焦点）
10. Restraint creates premium（收敛创造品质）

起草前只回答三件事：这页唯一的主语是什么 / 留白在替谁工作 / 观众的眼睛按什么顺序走。

## 三条腿（谁做什么，不要越界）

- **QA（代码）** 只答「能不能正确交付」：溢出、越界、数据完整性、对比度底线、来源区；产出 PASS/FAIL/WARNING，默认不跑 advisory。
- **判断（你 + `design-craft.md`）** 答「有没有设计价值」：机器不打审美分；九维坐标系 + 七条原则 + 案例库是你的眼睛。
- **预测（可选）** 仅新建/复杂 deck 或用户明确要求时调用。

判断优先级：事实与语义 > 可读性 > 内容任务 > 情绪 > 品牌。下层手法不修上层问题。

## Decision Framework（唯一的决策入口）

```
Audience / Decision / Evidence / Emotion
  → intent_compiler（意图压缩）→ Design Brief（~500 tokens）
  → Visual World / Composition / Typography / Media / Chart
```

Brief 后消费 `plan.json`（见 R1），不重启 route/layout；每页保留 `page_intent` 的
insight/focus/reading_order/energy/density；plan 区分 `intent_interpretation` 的
explicit/inferred/conflicts。契约与判断见 `production-contract.md` / `design-craft.md`。

## Color Decision Chain（色彩从内容推导，不查表）

品牌意义 → 行业语境 → 情绪温度 → 材质参照 → 光照条件 → 生成配色 → 配色校验。

`COLOR_DIRECTIONS` 家族种子只作审美边界与兜底，不是配色答案。禁止「科技 = 蓝紫」式的固定映射——先问材质与光：科技创新可以是雾灰蓝（玻璃），也可以是石墨黑（金属）或植物灰绿（有机）。

## Director Pipeline（P1–P5，唯一执行顺序）

- **P1 理解**：冻结输入（受众/决策/口径/来源；不可验证标 `unknown`）→ 产出 Brief + Strategy。
- **P2 策略**：Direction（visual_world 一句话隐喻：材质/光影/空间）+ Story Map（情绪弧线：opening 建世界观 → 章节页制造变化 → 内容页给证据 → closing 成记忆点）+ 逐页 Page Intent。系统级判断（色彩/字阶/母题/节奏词汇）在此判一次，全稿继承。
- **P3 落地**：内容定 Family → spec 填入骨架（数值几何 + `text`，样式平铺顶层；只继承 P2 系统判断，不重议）→ 媒体闸门（图须有功能：先答「它证明这页哪句话」）→ compile 出 PPTX。
- **P4 修正+验证**：spec 写完直接 `draft`（Guard 即编译前阻断门；`spec` 档仅诊断）；照报告 `fix_plan`（根因分组+内嵌契约行）**一轮**修完，零文档回读；advisory 挂同轮 draft（`--advisory`），不独占轮次。
- **P5 收口**：方向确认后直接 `release`（全量渲染+Manifest；页级缓存让复跑只重渲变化页）；`review` 仅单页抽查。发布门 = 0 阻断 + 全量像素 + 完整性；score 与非阻断警告仅记录（`warn_summary`），不构成门槛。

## Modes（与 Fast/Advanced 预算正交）

| Mode | 做什么 | 状态上限 |
|---|---|---|
| `spec` | 诊断（**非阶段门**）：归一化 + Guard，不编译不写文件 | PREVIEW_ONLY |
| `sketch` | 结构探索：只守 error 级，秒级出 PPTX | SKETCH（不可发布） |
| `draft`（默认） | 验证①：Guard + Compile 出可编辑 PPTX，零渲染，报告含 fix_plan | PREVIEW_ONLY |
| `review` | 抽查（**非阶段门**）：只渲染指定/变化页 | PASS 可达，`release_eligible=False` |
| `release` | 验证②收口：全量渲染 + QA + Manifest | 唯一可发布 |

看方向用 `ghost.py`(~1ms/页)，真渲染留给收口。

## Round Budget（两代两验执行契约）

```
R1 规划     pipeline.py brief.yml --out plan.json --skeleton build_mydeck.py
R2 一次性生成 Strategy/Direction/全量 spec 填骨架；出图同轮批量发出，draft 前收齐 --qc
R3 验证①    qa.py build_mydeck.py out.pptx --mode draft
R4 修正轮   按 fix_plan 根因组一次改完（零回读）→ 复跑 draft
R5 收口     方向确认后直接 --mode release（复跑只重渲变化页）
```

预算 ≤6 轮，简单案例跳过 R4（=4 轮）；有 plan/spec 直接进 R3。
独立资产 QC/渲染页可有界并行，不并发写产物。

## Hard Boundaries（工程事实）

- 事实与口径完整 > 构图 > 风格 > 装饰；数据不可为构图造假、为留白删减。
- 视觉复杂度必须服务阅读路径；说不清功能的装饰删除。
- 文本/图表/图片/来源区不相交；页脚引用与页码同基线、左右对侧。
- 图表声明 `source/unit/period/basis`；同一指标全 deck 同口径；review/release 的 factual numeric chart 缺 provenance 即 error。
- 16:9、1280×720、8 单位网格；字体家族 ≤2；semantic view 只作缓存身份，PPTX 另盖 artifact SHA。

## Load Routing（按需加载）

默认按需读本文件与命中资料；README/CHANGELOG/archive/memory/assets/selftest 属非生产资料，禁入执行轮上下文。render/asset/layout 脚本只在对应阶段调用。**修正轮零文档回读**：以 `fix_plan` 内嵌契约行为准；契约表会话内只读一次。

| 任务 | 读 | 调 |
|---|---|---|
| 新建/重构 deck | 本文件 + `design-intelligence.md` | `pipeline.py --skeleton` 规划+骨架 → 一次性生成 → `draft` → `release`；复杂页才做 layout search |
| 写 spec 字段 | `production-contract.md` | `qa.py --mode spec` 先问代码 |
| 设计品味判断 | `design-craft.md` | 判断依据，不是规则 |
| 主题参考（可选） | `design-system.md`（Theme DNA） | 只作材质/光影灵感，seed 落进 `spec.theme` |
| 出图 | 契约 asset 行 + `asset_prompt.py` | R2 同轮批量出图→`--qc`；阻断最多定向重出 1 次，不自动升级 |
| 方向确认/改布局 | 契约对应行 | `ghost.py` 看方向（零渲染）；单页抽查用 `--mode review` |
| 发布 | 契约 Release Manifest | 方向确认后直接 `qa.py --mode release` |

按入口调用脚本；阈值以代码常量为准，档位不放宽规则。
