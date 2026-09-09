# Worked Example（参考 spec 样例）

本文档给出一个**完整、可编译**的 spec 样例，演示生产契约中所有关键字段的正确写法。
它是「脚手架」而非「模板」：照抄它只会得到一个具体场景的 deck；真正要学的是**每个
字段回答什么判断**——换一个内容与受众，字段值应随之重写，而不是复用这套坐标。

样例场景：向董事会汇报「2026 品牌是复利资产」，三页精简版。

## 1. 主题（用 route 的成品种子，可覆盖）

```python
# 从 route 取 editorial_brand 的成品种子，再按品牌微调 accent
from route import DIRECTION_PRESETS
theme = dict(DIRECTION_PRESETS["editorial_brand"]["theme_seed"])
theme["colors"]["accent"] = "#8E2F28"   # 覆盖为品牌红
```

种子只提供「起点锚点」：`derive_tokens` 会据此展开 panel/hairline/track/ramp/series
等 30+ 派生色；覆盖任意一项即可微调，不必从头手挑整条色阶。

## 2. 完整 spec（含事实/口径治理字段）

```python
spec = {
  "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},
  "theme": theme,
  "strategy": {
    "audience": "董事会（8 人，近距离投屏）",
    "decision": "批准追加品牌预算",
    "tension": "品牌投入短期无直接转化，股东质疑其必要性",
    "narrative_arc": ["establish", "prove", "recommend"],
    "emotional_target": "calm_authority",
    "evidence_posture": "fact_led",
  },
  "direction": {
    "visual_world": "纸面与墨色，柔和的左上单一光源，编辑级留白",
    "composition_grammar": "evidence_field",
    "type_voice": "editorial_serif",
    "color_behavior": "quiet_neutral",
    "media_role": "none",
    "background_scene": "solid_world",
    "motion_posture": "still",
    "color_intent": ["hierarchy", "emotion", "brand"],
    "forbidden_signals": ["卡片墙", "无意义渐变", "装饰性图标"],
  },
  "slides": [
    {
      "id": "s01",
      "page_intent": {
        "insight": "品牌是本金，投放是利息：三年里品牌搜索贡献了 60% 的复购",
        "narrative_role": "establish",
        "audience_question": "品牌投入到底值不值？",
        "focus": "st",
        "reading_order": ["conclusion", "source"],
        "energy": "high", "density": "sparse",
        "empty_space_role": "hold_emotion",
        "page_family": "MINIMAL_STATEMENT",
        "rhythm_stage": "opening",
        "continuity_token": "folio-01",
      },
      "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
      "elements": [
        {"type": "shape", "id": "rule", "shape": "rect",
         "x": 96, "y": 270, "width": 4, "height": 160,
         "fill": {"type": "solid", "color": "accent"}},
        {"type": "text", "id": "st", "x": 124, "y": 288, "width": 720, "height": 140,
         "text": "品牌是本金，投放是利息", "size": 60, "color": "ink", "bold": True,
         "max_lines": 2, "line_height": 1.1, "padding": 0},
      ],
    },
    {
      "id": "s02",
      "page_intent": {
        "insight": "品牌搜索贡献了 60% 的复购，且曲线在加速",
        "narrative_role": "prove",
        "audience_question": "证据是什么？",
        "focus": "ch",
        "reading_order": ["conclusion", "evidence", "source"],
        "energy": "low", "density": "balanced",
        "empty_space_role": "protect_focus",
        "page_family": "DATA_STORY",
        "rhythm_stage": "evidence",
        "continuity_token": "folio-02",
      },
      "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
      "elements": [
        {"type": "text", "id": "h2", "x": 96, "y": 96, "width": 640, "height": 50,
         "text": "品牌搜索贡献 60% 复购", "size": 30, "color": "ink", "bold": True},
        # 多序列折线：series 表达多序列，highlight 选中的序列升级为 accent + 末端圆点
        # 事实/口径治理：metric 作跨页对齐键，unit/period/basis/source 显式声明
        {"type": "chart", "id": "ch", "chart_kind": "line",
         "x": 120, "y": 180, "width": 1040, "height": 380,
         "categories": ["Q1", "Q2", "Q3", "Q4"],
         "series": [
           {"name": "品牌搜索", "values": [10, 18, 28, 42]},
           {"name": "投放点击", "values": [20, 22, 24, 26]},
         ],
         "highlight": 0,
         "metric": "品牌搜索", "unit": "万次", "period": "2026 Q1–Q4",
         "basis": "同比口径", "data_status": "审计后", "source": "市场部《2026 品牌追踪》"},
      ],
    },
    {
      "id": "s03",
      "page_intent": {
        "insight": "建议追加 1200 万品牌预算，投向品牌搜索，预期复购 +8%",
        "narrative_role": "recommend",
        "audience_question": "该怎么做？",
        "focus": "ask",
        "reading_order": ["conclusion", "source"],
        "energy": "medium", "density": "sparse",
        "empty_space_role": "create_authority",
        "page_family": "MINIMAL_STATEMENT",
        "rhythm_stage": "closing",
        "continuity_token": "folio-03",
      },
      "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
      "elements": [
        {"type": "text", "id": "ask", "x": 96, "y": 300, "width": 800, "height": 120,
         "text": "追加 1200 万，投向品牌搜索", "size": 48, "color": "ink", "bold": True,
         "max_lines": 2, "line_height": 1.1, "padding": 0},
      ],
    },
  ],
}
```

## 3. 每个字段回答什么判断（学这个，不抄坐标）

| 字段 | 回答的问题 | 换内容时怎么变 |
|---|---|---|
| `strategy.tension` | 观众此刻的阻力是什么 | 阻力变了，`direction` 的情绪假设要跟着变 |
| `direction.composition_grammar` | 版面用什么空间语法 | 数据页回退 `evidence_field`，品牌页可用 `cinematic_stage` |
| `page_intent.insight` | 这一页唯一可复述结论 | 每页重写，写「对象+变化+含义」，不写字段名 |
| `page_intent.focus` | 哪个元素是第一注意点 | 必须指向真实元素 id |
| `chart.metric` | 这个指标跨页的「身份证」 | 同一指标必须全 deck 同名，单位一致 |
| `chart.unit/period/basis/source` | 数字口径与出处 | 缺省会被 `data_provenance` 点名 |
| `continuity_token` | 跨页连续性锚点 | 页码/章节号等签名，全 deck 稳定 |

## 4. 验证这条链

```bash
python3 scripts/guard.py build_mydeck.py --preflight   # 静态预检，0.2s 级
python3 scripts/ghost.py build_mydeck.py out_dir        # 迭代缩略图，~1ms/页
python3 scripts/compiler.py build_mydeck.py out.pptx    # 编译
python3 scripts/qa.py build_mydeck.py out.pptx --manifest  # 发布：渲染证据 + QA + Critic
```
