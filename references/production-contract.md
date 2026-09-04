# Production Contract

## Runtime architecture

```text
spec → compiler.py → elements.py / charts.py → primitives.py
     → guard.py → render_check.py → qa.py + art_critic.py
```

设计规划阶段读取参考文档并生成完整 `spec`；运行时阶段只处理 `spec`。编译器是编排层，不做设计决策，也不读取 `references/*.md`；元素与图表负责原生可编辑输出；Guard 负责静态硬约束；Render Check 负责像素证据；`qa.py` 负责确定性回归评分；`art_critic.py` 负责结构化审美判断。层间只通过 spec、RenderContext 和 JSON 报告沟通。

### Single-entry execution

优先调用 `qa.run_qa()` 完成一次性流水线：它只加载并调用所需模块、复用同一份 `guard_rules`，并返回 guard / compile / render 的摘要；不要在代理上下文中逐个读取脚本全文，也不要重复运行 `guard` 与 `compile`。仅在调试对应失败域时调用单模块 CLI。所有 CLI 支持 `--json` 时应优先使用 JSON 输出；日志只保留摘要、失败码、页面 ID 和修复建议。`render=False` 或 `--no-render` 只允许快速迭代，不代表发布通过；在没有其他阻断错误时状态为 `PREVIEW_ONLY`，若同时存在阻断错误则按状态优先级返回 `BLOCKED`。

## Stable API

```python
from compiler import compile_deck
report = compile_deck(spec, "output.pptx", checks=True, guard_rules=None)

from qa import run_qa
qa = run_qa(spec, "output.pptx", guard_rules=None, render_dir=None)

from art_critic import critique_deck
critic = critique_deck(spec, render_evidence=qa.get("render_evidence"), evidence_cards=None)
```

`compile_deck` 不自动缩字号、改色、重排、删除内容或替换图片。所有 warnings 必须进入报告。`run_qa` 的 `score` 只表示确定性合规，不得冒充审美分数；`passed` 只是数值门槛结果，最终发布依据是 `status`。编译前先完成 Guard；Guard 存在 error 时仍可为调试生成预览，但发布状态必须为 `BLOCKED`，不得被编译成功覆盖。

## Fill Contract

元素填充统一使用以下 schema；普通字符串仍作为兼容 shorthand：

```json
{"fill": {"type": "solid", "color": "surface", "opacity": 0.30}}
{"fill": {"type": "gradient", "gradient_type": "linear", "angle": 90,
  "stops": [{"position": 0, "color": "#FFFFFF", "opacity": 0.8},
            {"position": 1, "color": "#FFFFFF", "opacity": 0}]}}
{"fill": {"type": "none"}}
```

历史 `{"color": "#fff", "opacity": 0.3}` 和 `{"gradient": {"stops": [...]}}` 由 `elements.normalize_fill()` 兼容迁移后再渲染。无效 type、缺失 color、非法 stop 或无法解析的 token 必须抛出包含 Expected 格式的明确错误；不得静默改成默认蓝色。背景层仍可在 compiler 层安全回退，但必须将原始 warning 写入报告。

## Background Layer Contract

背景按需组织为 `Base → Image → Atmosphere/Light → Content Protection`。不要求每页启用全部层；每个启用层必须服务内容，不能遮蔽主体或抢夺第一注意点。推荐图片压暗 overlay：`{"type":"solid","color":"#000000","opacity":0.35}`。

## Spec minimum

```python
spec = {
  "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},
  "theme": {"colors": {...}, "fonts": {...}, "constraints": {...}},
  "strategy": {...},
  "direction": {...},
  "slides": [{
    "id": "s01", "page_intent": {...},
    "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
    "background": {...}, "elements": [...]
  }]
}
```

每页至少有 `page_intent.insight`、`focus`、`reading_order`、`energy`、`density`、`empty_space_role`、`page_family`、`rhythm_stage` 和 `continuity_token`；`direction` 应声明 `color_intent: [brand, emotion, hierarchy]`；每个图表至少有单位、期间、比较口径、数据状态、来源和一个强调点；每个图片至少有资产角色、主体、构图、留白锚点、裁切与溯源。布局可在五类页面家族间变化，但必须复用同一 canvas、12 列逻辑网格、8 单位基线、safe zones、source zone、type budget 与 accent budget。文本元素应声明 `max_lines`、`line_height`、`padding`；图表元素应声明 `label_collision_policy`，密集标签不得默认强行显示。

### Layout collision contract

所有可见对象都必须有数值 `x / y / width / height`。文本必须显式声明或可由默认值推导 `padding / line_height / max_lines`；标题、结论、图表标签和来源不得共享同一几何区域。相交规则如下：

1. text–text、text–chart、text–image 的有效墨迹相交即为 `OVERLAP`；默认不允许通过透明度或 z-order 豁免。
2. 需要前景遮挡时，必须在双方声明 `allow_overlap: true`、`overlap_reason` 和 `protected_zone`；来源区、关键结论和图表读数永不允许被遮挡。
3. 文本框外框不等于墨迹框：Guard 使用 `text_ink_ratio / text_ink_v` 估算，渲染 QA 再检查实际视觉占用。右对齐、居中和多行文本应声明 `ink_anchor`，否则按保守左上锚点检查。
4. 图表内部标签应使用 `label_safe_margin`、`label_gap` 和 `label_collision_policy: hide_redundant | move_outside | fail`；不得以缩小字体消除碰撞。无法安全放置时改用直接标注、减少类别、拆页或 `fail`。
5. 左下角 `source_zone` 是独立保留区，主体、图表、图片和装饰不得进入；来源需支持自动换行并在渲染后可读。

### Chart data contract

数值图表的 `data` 必须是非空数组，每行至少包含 `label` 与有限数字 `value`；`display` 只负责已核验的展示格式，不参与计算。`highlight` 必须是有效整数索引；`progress_bar` 的 `max` 必须为正数；`pie`/`donut` 的非负有效值总和必须大于零；`ranked_bar`、`progress_bar`、`stacked_bar` 与 `bubble` 不接受负值。Guard 对这些条件返回 `data_integrity` 或 `chart_highlight`，Compile/Render 不得静默补零、截断负值或虚构单位。

图表渲染器遇到空数据时可以跳过该图表并写入 warning；遇到不可解析数值时可以仅为防止程序崩溃按零计算并保留 warning。**这两种容错只服务调试预览，不表示数据有效；Guard 的 `DATA_INTEGRITY_FAIL` 必须使最终状态为 `BLOCKED`，不得以容错后的图表发布。**瀑布图的零轴必须根据数据域映射，而不是固定在画布某一比例位置。

## Deterministic QA

继承现有 `guard.py` 的网格、越界、安全区、重叠、容量、Accent、节奏、文本、颜色、对齐、装饰、动画、对比度、叠加层和主题约束检查，并将 `overlap`、`source_zone`、`text_capacity`、`chart_label_collision` 视为优先级高于审美分数的布局问题。继承现有 `render_check.py` 的 occupancy、brightness、saliency centroid、accent pixel ratio、background luma 和 gravity drift 指标。

确定性评分建议仍用 100 分制，但只记录 `guard / compile / render` 域。`passed` 不能仅凭分数决定；硬错误、编译失败、来源缺失、渲染缺失、关键文本不可读或任何未获声明的遮挡时必须覆盖分数。报告必须返回 `failure_codes`、`blocking_items`、`affected_slides`、`next_action`、`status` 和 `elapsed_ms`，让下一次调用只处理受影响范围。`status` 的优先级固定为：阻断错误 → `BLOCKED`；无阻断但缺少真实渲染 → `PREVIEW_ONLY`；有可修复问题 → `REVISE`；全部发布条件满足 → `PASS`。

## Art Critic contract

`art_critic.py` 必须返回：

```json
{
  "critic_version": "1.0",
  "deck_score": 0,
  "status": "PASS|REVISE|BLOCKED|PREVIEW_ONLY",
  "hard_gates": [],
  "slides": [{
    "slide": "s01",
    "scores": {
      "visual_hierarchy": 0,
      "balance": 0,
      "alignment": 0,
      "contrast": 0,
      "rhythm": 0,
      "consistency": 0,
      "emotional_impact": 0,
      "memorability": 0,
      "professional_quality": 0
    },
    "observations": [],
    "minimal_fixes": [],
    "recheck": []
  }]
}
```

每项 0–5 分，报告必须包含可观察证据。建议权重为 Hierarchy 20、Balance 15、Alignment 10、Contrast 10、Rhythm 10、Consistency 10、Emotional Impact 10、Memorability 10、Professional Quality 5。Memorability 必须由可观察的视觉记忆锚点、独特构图动作或跨页连续性说明支撑。Art Critic 的 `status` 只表示审美批评结果：任何核心维度低于 3 或存在审美硬门槛时至少为 `REVISE`；它不替代 QA 的数据、编译、安全区和渲染发布门。最终 Release Manifest 的 `status` 必须综合 QA 与 Art Critic，只有两者都满足发布条件时才为 `PASS`。

## Failure codes

| 代码 | 含义 | 默认动作 |
|---|---|---|
| `INPUT_MISSING` | 受众、决定、来源或关键约束缺失 | BLOCKED |
| `INTENT_UNCLEAR` | 一页无法写出单一 insight | BLOCKED |
| `THEME_MISMATCH` | 主题人格与内容任务冲突 | REVISE Direction |
| `FOCUS_COMPETING` | 多个对象争夺 L4 | REVISE Composition |
| `READABILITY_FAIL` | 对比、字号、行数或安全区失败 | BLOCKED |
| `DATA_INTEGRITY_FAIL` | 单位、期间、来源或图表映射不完整 | BLOCKED |
| `MEDIA_UNJUSTIFIED` | 图片无信息功能或遮挡内容 | REVISE Media |
| `RHYTHM_FLAT` | 连续页面密度/重心/能量重复 | REVISE Story Map |
| `CARD_WALL` | 圆角容器过多或成为主要结构 | REVISE Composition |
| `RENDER_UNAVAILABLE` | 没有真实渲染证据 | PREVIEW_ONLY |
| `CRITIC_LOW` | 审美批评维度低于门槛 | REVISE |
| `OVERLAP` | 可见文本/图表/图片有效墨迹相交 | BLOCKED |
| `SOURCE_COLLISION` | 来源区被主体或页脚冲突侵入 | BLOCKED |
| `CHART_LABEL_COLLISION` | 图表标签、轴、图例或数值互相遮挡 | BLOCKED |
| `TEXT_OVERFLOW` | 实际或估算文字超出可读区域 | BLOCKED |
| `GUARD_FAIL` | Guard 发现未被专用错误码覆盖的硬错误 | BLOCKED |

## Release Manifest

最终输出必须记录 `source_spec_hash`、`theme_id`、`slide_count`、`compile_report`、`qa_report`、`critic_report`、`render_evidence_path`、`revision_count`、`revision_log`、`status` 和 `generated_at`。每次 revision 必须记录 observation、minimal_fix、recheck 结果，避免只写“已优化”。报告应能让另一位代理在不读取整套历史对话的情况下复现或定位失败；`revision_log` 只引用失败码与页面 ID，不嵌入重复源码或整份中间报告。
