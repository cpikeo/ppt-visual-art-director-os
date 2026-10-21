# eval 夹具：一页原生柱状图（可编辑图表，不是图片）
T, L = "Source Han Serif SC", "Georgia"
def txt(eid, x, y, w, h, text, size, *, color="ink", role=None, bold=False, max_lines=None):
    el = {"id": eid, "type": "text", "x": x, "y": y, "width": w, "height": h, "text": text,
          "size": size, "color": color, "font": L, "bold": bold, "align": "left"}
    if role: el["role"] = role
    if max_lines: el["max_lines"] = max_lines
    return el
SPEC = {
  "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},
  "theme": {"colors": {"background": "#F1EFEA", "ink": "#12120F", "muted": "#5B574F",
                       "primary": "#1A3A5C", "secondary": "#6E6A63", "accent": "#C8501E"},
            "fonts": {"cn": T, "latin": L}},
  "slides": [
    {"id": "s01", "source_zone": {"x": 48, "y": 664, "width": 1184, "height": 32},
     "elements": [
       txt("s01_t", 96, 88, 1000, 110, "四城次日达占比：深圳已达 91%，成都仍停在 62%", 40, bold=True, max_lines=2),
       {"id": "s01_c", "type": "chart", "chart_kind": "column",
        "x": 96, "y": 232, "width": 760, "height": 380,
        "data": [{"label": "深圳", "value": 91}, {"label": "杭州", "value": 84},
                 {"label": "武汉", "value": 73}, {"label": "成都", "value": 62}],
        "source": "来源：运营月报 · 2024 全年 · 自营仓配口径", "unit": "%",
        "period": "2024", "basis": "自营仓配", "series_name": "次日达占比"},
       txt("s01_b", 896, 232, 288, 200,
           "成都的差距不在仓，在末端站点密度：每万人 0.7 个，深圳 1.9 个。", 18, max_lines=6),
       txt("s01_src", 96, 672, 760, 20, "来源：运营月报 · 2024 全年 · 自营仓配口径", 12, color="muted", role="source"),
     ]},
  ],
}
