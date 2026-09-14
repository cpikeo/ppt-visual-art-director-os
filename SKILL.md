---
name: ppt-visual-art-director-os
description: >
  用于创建、重构、审校和优化演示文稿、数据叙事与视觉系统；先把内容、受众与决策转成视觉策略，
  再转成视觉语言、页面意图和可编辑 PPTX，并通过渲染证据与确定性 QA 完成交付判定。
  当用户要求制作、重构、评审或优化 PPT、deck、演示文稿、数据叙事幻灯片，
  或需要生成原生可编辑 PPTX 并给出交付质量判断时使用。
---

# PPT Visual Art Director OS

视觉艺术指导 + 信息设计 + 原生可编辑 PPTX 生产。成片品质 = 判断质量 × 空间秩序 × 叙事记忆 × 执行一致性。

## Design Intent First（最高优先级）

任何视觉决策之前，先回答四件事：

1. 这页想让观众理解什么？
2. 哪个信息必须留下？
3. 哪个信息可以删除？
4. 观众应该产生什么感受？

视觉形式是最后的结果，不是起点。禁止从主题库、DNA、案例库直接选风格——先解决问题，再选语言。

决策顺序：内容意义 → 受众心理 → 信息优先级 → 材质/光影/色彩 → Theme DNA（仅作灵感参考）→ 视觉输出。

## 10 Design Principles（唯一需要记住的东西）

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

- **QA（代码）** 只答「能不能正确交付」：溢出、越界、数据完整性、对比度底线、来源区。产出 PASS/FAIL/WARNING。
- **判断（你 + `references/design-craft.md`）** 答「有没有设计价值」：机器不打审美分，九维评审坐标系 + 七条判断原则 + 案例库是你的眼睛。
- **预测（`design_intelligence.pre_critic` + `risk.strategy`）** 答「会挂在哪里、先改什么」：建议，不是闸门。

判断优先级：事实与语义 > 可读性 > 内容任务 > 情绪 > 品牌。下层手法不修上层问题。

## Decision Framework（唯一的决策入口）

```
Audience / Decision / Evidence / Emotion
  → intent_compiler（意图压缩）→ Design Brief（~500 tokens）
  → Visual World / Composition / Typography / Media / Chart
```

```bash
python3 scripts/intent_compiler.py brief.yml --json   # 需求 → Design Brief
python3 scripts/route.py brief.yml --json             # 内容 → 家族 / 密度 / 资产预算
```

Brief 之后所有步骤只消费 Brief + Page Intent，不再回读原始需求。每页一个 `page_intent`：`insight`（一页一句可复述结论）+ `focus`（唯一）+ `reading_order` + `energy` + `density`。字段契约见 `references/production-contract.md`，判断依据见 `references/design-craft.md`。

## Color Decision Chain（色彩从内容推导，不查表）

品牌意义 → 行业语境 → 情绪温度 → 材质参照 → 光照条件 → 生成配色 → 配色校验。

`COLOR_DIRECTIONS` 家族种子只作审美边界与兜底，不是配色答案。禁止「科技 = 蓝紫」式的固定映射——先问材质与光：科技创新可以是冷静透明的雾灰蓝（玻璃），也可以是可靠工业的石墨黑（金属），可以是未来探索的深紫灰（夜空），可以是生命科技的植物灰绿（有机）。

## Director Pipeline（P1–P5，唯一执行顺序）

- **P1 理解**：冻结输入（受众/决策/口径/来源；不可验证标 `unknown`）→ 产出 Brief + Strategy。
- **P2 策略**：Direction（visual_world 一句话隐喻：材质/光影/空间）+ Story Map + 逐页 Page Intent。
- **P3 落地**：内容定 Family → 写 spec（数值几何 + `text` 字段，样式平铺顶层）→ 媒体闸门（图须有功能）→ compile 出可编辑 PPTX。
- **P4 修正**：1 根因 = 1 轮。只修本轮 `items` 里唯一/首个 error（或 `risk.strategy` 的首杠杆），其余排队；为分数调参数 = 把对的地方改坏。
- **P5 验证**：`qa.py --mode draft`（默认，零渲染）→ `review`（只渲染变化页）→ `release`（全量 + Manifest，唯一给发布资格）。

## Modes（流程控制；预算 Fast/Advanced 与其正交）

| Mode | 做什么 | 状态上限 |
|---|---|---|
| `spec` | 只判读：归一化 + Guard + 风险预测，不编译不写文件 | PREVIEW_ONLY |
| `sketch` | 结构探索：只守 error 级，秒级出 PPTX | SKETCH（不可发布） |
| `draft`（默认） | 创作链：Guard + Compile 出可编辑 PPTX，零渲染 | PREVIEW_ONLY |
| `review` | 只渲染变化页 + QA | PASS 可达，`release_eligible=False` |
| `release` | 全量渲染 + QA + Manifest | 唯一可发布 |

迭代期看方向用 `ghost.py`（~1ms/页），真渲染只留给收口与发布。

## Hard Boundaries（工程事实，不是品味）

- 事实与口径完整 > 构图 > 风格 > 装饰；数据不可为构图造假、为留白删减。
- 视觉复杂度必须服务阅读路径；说不清功能的装饰删除。
- 文本/图表/图片/来源区几何不相交；来源区独立保留，不被侵入。
- 图表声明 `source/unit/period/basis`；同一指标全 deck 同口径。
- 16:9、1280×720、8 单位网格（自动吸附）；字体家族 ≤2。

## Load Routing（按需加载，不要通读）

| 任务 | 读 | 调 |
|---|---|---|
| 新建/重构 deck | 本文件 + `references/design-intelligence.md` | `intent_compiler` → `route` → `layout_search` → `--mode draft` |
| 写 spec 字段 | `references/production-contract.md`（契约表） | `qa.py --mode spec` 先问代码 |
| 设计品味判断 | `references/design-craft.md` | —（判断依据，不是规则） |
| 主题参考（可选） | `references/design-system.md`（Theme DNA 节） | 只作材质/光影灵感，seed 落进 `spec.theme`（先走 Design Intent First + Color Decision Chain） |
| 出图 | 契约 asset 行 + `scripts/asset_prompt.py` | 每张图先走 asset_prompt 组装、CHECK OK 再出图（禁手写裸 prompt——裸 prompt 漠视纪律闸门）；出图后跑 `asset_prompt.py --qc <图>` 体检（亮度/留白/主体位置/文字区/对比度，Issue+Suggestion 不打分），有问题再重出 |
| 方向确认/改布局 | 契约对应行 | `ghost.py` 看方向 → `--mode review` |
| 发布 | 契约 Release Manifest | `qa.py --mode release` |

脚本按入口调用，不读源码；输出存 JSON 摘要。阈值唯一来源是代码常量，档位只改「测多少」不改「放宽什么」。
