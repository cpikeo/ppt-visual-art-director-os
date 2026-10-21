# -*- coding: utf-8 -*-
"""真实落稿样本：按 plan（brief_numeric）的判断落四个页面的元素。

只用于回归与端到端计时：几何由本文件决定，判断来自 plan。
"""
T = "Source Han Serif SC"
L = "Georgia"

def txt(eid, x, y, w, h, text, size, *, color="ink", role=None, bold=False,
        align="left", max_lines=None, spacing=0):
    el = {"id": eid, "type": "text", "x": x, "y": y, "width": w, "height": h,
          "text": text, "size": size, "color": color, "font": L, "bold": bold,
          "align": align}
    if role:
        el["role"] = role
    if max_lines:
        el["max_lines"] = max_lines
    if spacing:
        el["char_spacing"] = spacing
    return el

SPEC = {
    "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},
    "theme": {"colors": {"background": "#F1EFEA", "ink": "#12120F", "muted": "#5B574F",
                         "primary": "#1A3A5C", "secondary": "#6E6A63", "accent": "#C8501E"},
              "fonts": {"cn": T, "latin": L}},
    "slides": [
        {"id": "s01", "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 32},
         "elements": [
             txt("s01_t", 96, 88, 900, 120, "复购率三年翻倍\n靠的是履约，不是补贴", 44, bold=True, max_lines=2),
             txt("s01_k", 96, 248, 420, 140, "44%", 88, color="primary", bold=True, max_lines=1),
             txt("s01_s", 96, 400, 420, 40, "2024 年复购率（2022 年 21%，2023 年 33%）", 14, color="muted"),
             txt("s01_b", 560, 248, 624, 160,
                 "同期补贴率从 8% 降到 3%：翻倍发生在补贴退坡的同时，履约时效才是可辩护的解释。", 18, max_lines=4),
             txt("s01_src", 96, 672, 700, 20, "来源：门店台账 · 口径：全渠道复购 · 期间：2022–2024", 12,
                 color="muted", role="source"),
         ]},
        {"id": "s02", "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 32},
         "elements": [
             txt("s02_t", 96, 88, 900, 100, "门店回访：复购发生在收货后第三天", 44, bold=True, max_lines=2),
             txt("s02_b", 96, 224, 560, 200,
                 "2024 年走访 12 家门店，店员反馈复购集中在收货后 48 到 72 小时；样本 36 单。", 18, max_lines=5),
             txt("s02_n", 720, 224, 464, 120, "12 家门店 · 36 单样本", 32, color="primary", bold=True, max_lines=2),
             txt("s02_src", 96, 672, 700, 20, "来源：门店走访记录 · 期间：2024 年 · 样本：36 单", 12,
                 color="muted", role="source"),
         ]},
        {"id": "s03", "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 32},
         "elements": [
             txt("s03_t", 96, 88, 900, 100, "履约成本占总成本 61%", 44, bold=True, max_lines=2),
             txt("s03_p", 96, 232, 420, 140, "11.2 元", 88, color="primary", bold=True, max_lines=1),
             txt("s03_pl", 96, 384, 420, 40, "履约成本 / 单均 · 占总成本 61%", 14, color="muted"),
             txt("s03_b", 560, 232, 624, 160,
                 "营销成本 4.1 元。分子与分母同屏：61% 才有分母，成本结构不是一张趋势线。", 18, max_lines=4),
             txt("s03_src", 96, 672, 700, 20, "来源：财务台账 · 口径：单均成本 · 期间：2024 年", 12,
                 color="muted", role="source"),
         ]},
        {"id": "s04", "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 32},
         "elements": [
             txt("s04_t", 96, 88, 900, 100, "请批准 800 万元用于长三角仓配扩容", 44, bold=True, max_lines=2),
             txt("s04_b", 96, 224, 900, 160,
                 "2025 年 Q3 前完成。目标是把复购的履约基础从门店端挪到区域仓，扩容后单均履约成本下降 0.8 元。",
                 18, max_lines=5),
             txt("s04_src", 96, 672, 700, 20, "来源：投资部 · 期间：2025 Q3 前 · 口径：资本开支", 12,
                 color="muted", role="source"),
         ]},
    ],
}
