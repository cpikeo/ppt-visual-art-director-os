# -*- coding: utf-8 -*-
"""设计智能的机器口径（真源表 · 零依赖）。

本模块只放「能被固定阈值/查表完全描述」的东西：密度带、风险目录、
字阶驻点、取舍顺序、校准律、方向种子。它们以前散在文档 prose 里——
那种写法让 AI 把「查表」误当成「判断」。现在判断归文档（design-craft.md
+ design-intelligence.md），查表归这里。

依赖方向：design_intelligence ← 本模块。本模块不 import 任何包内模块、
零第三方依赖，因此永远不会触发 spec 档禁加载名单。
"""
from __future__ import annotations

# ── 密度带（与 primitives.content_occupancy 判读一致）───────────────────
DENSITY_BANDS = {"sparse": (0.0, 0.60), "balanced": (0.65, 0.75),
                 "dense": (0.75, 0.85)}

# ── 图表 accent 面积估算（按 chart_kind 物理形态校准，宁高估不漏报）───
# 构成图（donut/pie）：高亮扇区是实心大块 —— 环带 ≈62% bbox × 扇区占比
# 条形族：细轨道 + 圆头端点，实际着色 ≈7% bbox ×（高亮值/最大值）
# 点缀类（时间轴/步骤/大数字）：小面积强调
BAR_FAMILY = {"bar", "column", "horizontal_bar", "ranked_bar", "comparison_bar",
              "stacked_bar", "progress_bar", "waterfall"}
SMALL_ACCENT_CHART_SHARE = {"line": 0.02, "trend": 0.02,
                            "single_trend_line": 0.02, "area": 0.05,
                            "sparkline": 0.02, "timeline": 0.04, "steps": 0.04,
                            "process_flow": 0.04, "big_number": 0.08, "kpi": 0.08,
                            "executive_kpi": 0.08, "big_number_row": 0.06,
                            "matrix": 0.04}
TEXT_INK_FACTOR = 0.40    # 文本框 → 可见墨迹折算（accent 文字估算用）
SHAPE_FILL_FACTOR = 0.90  # 实心形状着色率

# ── DNA Schema：判断记忆键 vs 结果记忆键 ────────────────────────────────
RESULT_MEMORY_KEYS = {"palette", "color", "colors", "font", "fonts",
                      "image_style", "layout", "layout_result"}
JUDGMENT_KEYS = {"hierarchy", "space", "media", "color_behavior",
                 "charts", "anchor_rule", "structure", "type_voice"}

# ── 媒体决策模型：family → (need, confidence, reason) ──────────────────
MEDIA_MODEL = {
    "HERO": (True, 0.95, "开场页：品牌情绪建立，画心承担第一印象"),
    "CLOSING": (True, 0.90, "收尾页：情绪收束，画心承担记忆点"),
    "STORY": (True, 0.85, "叙事页：图像承担 context/emotion 功能"),
    "STATEMENT": (False, 0.30, "宣言页：留白与字阶就是视觉锚点，加图反而稀释"),
    "SECTION": (False, 0.25, "章节页：结构即节奏，安静是功能"),
    "DATA": (False, 0.05, "数据页：图表已是视觉锚点，再叠图 = 双焦点竞争"),
    "STRUCTURE": (False, 0.02, "结构页：结构关系比图像更清晰，出图必输"),
    "PROCESS": (False, 0.05, "流程页：步骤序列自带视觉性"),
    "COMPARISON": (False, 0.08, "对比页：左右张力来自内容本身"),
    "EVIDENCE": (False, 0.10, "证据页：数字与来源的可信度不需要装饰"),
}

# route 家族名 → 媒体模型家族（两套命名的一致层，唯一映射源）
FAMILY_ALIASES = {
    "COVER": "HERO", "DATA_STORY": "DATA", "MINIMAL_STATEMENT": "STATEMENT",
    "EDITORIAL": "STORY", "NARRATIVE": "STORY", "FRAMEWORK": "STRUCTURE",
    "EXECUTIVE_SUMMARY": "EVIDENCE", "EVIDENCE_FIELD": "EVIDENCE",
    "HERO_COVER": "HERO", "SECTION_DIVIDER": "SECTION",
}

# ── 字阶驻点与视觉重量 ─────────────────────────────────────────────────
LADDER_RUNGS = (64.0, 44.0, 32.0, 22.0, 17.0, 12.5)  # 驻点字阶
LADDER_TOL = 2.0          # 驻点吸附容差（34 视作 32，避 ±1px 噪声）
TYPE_WEIGHTS = {"text": 1.0, "image": 1.2, "chart": 1.1,
                "native_chart": 1.1, "shape": 0.7}
# 声明型页面允许刻意偏轴——不对称是它们的语言，不是失衡
ASYMMETRIC_OK_FAMILIES = {"HERO", "CLOSING", "STATEMENT", "SECTION"}

# ── Page Intent 骨架：家族 → 能量/密度/留白职责 ─────────────────────────
INTENT_PRESETS = {
    "HERO": {"energy": "high", "density": "sparse", "empty_space_role": "hold_emotion"},
    "STATEMENT": {"energy": "high", "density": "sparse", "empty_space_role": "create_authority"},
    "SECTION": {"energy": "medium", "density": "sparse", "empty_space_role": "separate_chapter"},
    "DATA": {"energy": "medium", "density": "balanced", "empty_space_role": "protect_focus"},
    "EVIDENCE": {"energy": "medium", "density": "dense", "empty_space_role": "protect_focus"},
    "COMPARISON": {"energy": "medium", "density": "balanced", "empty_space_role": "separate_chapter"},
    "PROCESS": {"energy": "medium", "density": "balanced", "empty_space_role": "protect_focus"},
    "STRUCTURE": {"energy": "low", "density": "balanced", "empty_space_role": "separate_chapter"},
    "STORY": {"energy": "medium", "density": "balanced", "empty_space_role": "hold_emotion"},
    "CLOSING": {"energy": "high", "density": "sparse", "empty_space_role": "hold_emotion"},
}

# ── 参考空间实测律（全局；可选 memory/calibration_space.json 覆盖）─────
CALIBRATION_LAWS = {
    "area_ratio": {"c1": 0.55, "c1_band": (0.35, 0.85), "c2": 0.21,
                   "c3": 0.11, "c4": 0.06},
    "hue_families_page_max": 1,          # 页级（主题级宽一档 → 2）
    "sat90": {"quiet_max": 0.35, "warm_material_max": 0.65},
    "brightness_regimes": {"dark": (0.05, 0.35), "light": (0.55, 0.97)},
    "negative_space_text_led": (0.40, 1.0),
    "photo_share": (0.18, 0.60),
    "type_edge_density": (0.016, 0.053),
}
CALIBRATION_FAMILIES: dict = {}

# ── 自适应色彩：比例目标 / 禁用 / 方向种子（兜底骨架）──────────────────
COLOR_RATIO_TARGETS = {"foundation": 0.70, "supporting": 0.20,
                       "information": 0.08, "accent": 0.02}
COLOR_FORBIDDEN = ("high-saturation gradients", "SaaS blue-purple",
                   "colorful card walls", "cheap tech glow", "rainbow palette")
COLOR_DIRECTIONS = {
    "luxury_editorial": dict(regime="light", sat="quiet", motion=("spatial",),
        texture=("luxury", "architecture"),
        material="warm ivory paper, travertine and bronze, soft window light",
        seed={"foundation": "#F2EDE4", "supporting": "#9A8C74", "information": "#403B32", "accent": "#9C5A2E"}),
    "song_elegance": dict(regime="light", sat="quiet", motion=("natural",),
        texture=("eastern",),
        material="rice paper, ink stone, tea-green silk, diffuse north light",
        seed={"foundation": "#F3F1EA", "supporting": "#8B8D84", "information": "#22241F", "accent": "#5E7562"}),
    "zen_minimal": dict(regime="light", sat="quiet", motion=("natural",),
        texture=("eastern",),
        material="handmade paper, mist, still water, shadowless light",
        seed={"foundation": "#F5F4F1", "supporting": "#9A9A96", "information": "#1E1E1C", "accent": "#6E6E6A"}),
    "nordic_quiet": dict(regime="light", sat="quiet", motion=("spatial",),
        texture=("architecture",),
        material="lime plaster, pale oak, ceramic, low winter sun",
        seed={"foundation": "#EFECE6", "supporting": "#A79E90", "information": "#33302B", "accent": "#8A7A5F"}),
    "quiet_luxury": dict(regime="light", sat="quiet", motion=("spatial",),
        texture=("luxury",),
        material="champagne metal hairline, taupe stone, sea light through sheer curtain",
        seed={"foundation": "#F1EDE6", "supporting": "#A99878", "information": "#37322A", "accent": "#B08D4F"}),
    "monochrome_noir": dict(regime="dark", sat="quiet", motion=("spatial",),
        texture=("architecture",),
        material="black stone, single raking light shaft, graphite dust",
        seed={"foundation": "#101010", "supporting": "#4A4A4A", "information": "#F2F2F0", "accent": "#8C8C8C"}),
    "cinematic_narrative": dict(regime="dark", sat="warm", motion=("spatial", "natural"),
        texture=("luxury", "architecture"),
        material="amber dusk, coastal air, brass light, deep shadow",
        seed={"foundation": "#141210", "supporting": "#5C4A33", "information": "#EFE3CE", "accent": "#C08A3E"}),
    "nature_luxury": dict(regime="dark", sat="quiet", motion=("natural", "spatial"),
        texture=("organic", "architecture"),
        material="deep forest green, mist over water, wet stone, cold diffuse light",
        seed={"foundation": "#16211C", "supporting": "#4E6157", "information": "#EDEFE9", "accent": "#6FA08C"}),
    "organic_systems": dict(regime="light", sat="quiet", motion=("natural",),
        texture=("organic",),
        material="oat fiber, leaf vein macro, sage clay, soft top light",
        seed={"foundation": "#EFEBE2", "supporting": "#A8A394", "information": "#3B3A33", "accent": "#7C8B6F"}),
    "precision_tech": dict(regime="mixed", sat="quiet", motion=("tech",),
        texture=("technology",),
        material="optical glass, titanium edge, controlled blue signal on graphite",
        seed={"foundation": "#0D0F12", "supporting": "#3A4148", "information": "#F2F4F6", "accent": "#2E7BD6"}),
    "apple_future": dict(regime="light", sat="quiet", motion=("tech", "spatial"),
        texture=("technology",),
        material="titanium micro-brush, mist white stage, single product light",
        seed={"foundation": "#F6F6F7", "supporting": "#9BA0A6", "information": "#1D1D1F", "accent": "#0071E3"}),
    "data_intelligence": dict(regime="dark", sat="quiet", motion=("tech",),
        texture=("technology",),
        material="dark graphite evidence field, steel gray structure, one controlled accent",
        seed={"foundation": "#141619", "supporting": "#454B52", "information": "#EDEFF1", "accent": "#3E8E7E"}),
    "editorial_intelligence": dict(regime="light", sat="quiet", motion=("spatial",),
        texture=("eastern",),
        material="newsprint white, ink black, one signal red, hard magazine grid",
        seed={"foundation": "#F7F6F3", "supporting": "#8E8E8C", "information": "#141414", "accent": "#C8102E"}),
}
DIRECTION_ALIAS = {"quiet_minimal": "zen_minimal",
                   "editorial_brand": "luxury_editorial",
                   "product_stage": "apple_future",
                   "evidence_first": "data_intelligence"}

# ── 风险目录：pre_critic 可发射的 12 族 18 码（元数据镜像）──────────────
# 判据逻辑在 pre_critic；本表是「它会说什么」的机器可读目录，供策略层与
# 自检消费（selftest 断言：实测发射码 ⊆ 本表）。level 标默认档，
# 个别码（RHYTHM_FLAT_RISK 双重趋平时）可在 high/med 间浮动。
RISK_CATALOG = {
    "ACCENT_OVERFLOW": {"family": "accent", "level": "high", "predicted": "accent_budget",
        "root_cause": "chart_selection/color_discipline",
        "prevention": "换图表（一图一关系）或 accent 只留一个元素", "confidence": 0.85},
    "ACCENT_TIGHT_RISK": {"family": "accent", "level": "med", "predicted": "accent_budget(临界)",
        "root_cause": "color_discipline",
        "prevention": "贴线值留余量：accent 只留一个强调元素", "confidence": 0.6},
    "NO_MEMORY_ANCHOR": {"family": "memory_anchor", "level": "high",
        "predicted": "CRITIC_LOW(memorability)", "root_cause": "memory_anchor",
        "prevention": "焦点文字 ≥40px，或图表声明 highlight/center_value/target",
        "confidence": 0.9},
    "CONTRAST_FAIL_RISK": {"family": "contrast", "level": "high",
        "predicted": "READABILITY_FAIL", "root_cause": "theme_contrast",
        "prevention": "加深文字 token 或换更浅的底", "confidence": 0.95},
    "CONTRAST_WARN_RISK": {"family": "contrast", "level": "med",
        "predicted": "text_contrast(warn)", "root_cause": "theme_contrast",
        "prevention": "正文级文字用对比 ≥4.5:1 的 token", "confidence": 0.8},
    "FOCUS_SCALE_RISK": {"family": "focus", "level": "med",
        "predicted": "CRITIC_LOW(visual_hierarchy)", "root_cause": "focus_anchor",
        "prevention": "拉开尺度比（焦点 ≥1.25× 第二大字）或降级竞争文字",
        "confidence": 0.85},
    "FOCUS_AREA_RISK": {"family": "focus", "level": "high",
        "predicted": "CRITIC_LOW(visual_hierarchy)", "root_cause": "focus_anchor",
        "prevention": "焦点做大或收窄竞争对象", "confidence": 0.9},
    "TEXT_OVERFLOW_RISK": {"family": "text_overflow", "level": "high",
        "predicted": "TEXT_OVERFLOW", "root_cause": "layout_collision",
        "prevention": "padding→行高→字号→重写（或声明 auto_fit）", "confidence": 0.95},
    "MEDIA_MISUSE_RISK": {"family": "media", "level": "high",
        "predicted": "MEDIA_UNJUSTIFIED", "root_cause": "media_governance",
        "prevention": "删除图片，或把页面改叙事/情绪定位", "confidence": 0.9},
    "MEDIA_BUDGET_RISK": {"family": "media", "level": "med",
        "predicted": "CRITIC_LOW(visual_hierarchy)", "root_cause": "media_governance",
        "prevention": "一页一锚点：保留功能最强的一张", "confidence": 0.8},
    "DENSITY_MISMATCH_RISK": {"family": "density", "level": "med",
        "predicted": "rhythm(空转/趋平)", "root_cause": "rhythm_density",
        "prevention": "按真实占用重新声明，或调整内容量兑现声明", "confidence": 0.6},
    "RHYTHM_FLAT_RISK": {"family": "rhythm", "level": "med",
        "predicted": "RHYTHM_FLAT", "root_cause": "rhythm_density",
        "prevention": "改动一页的密度/能量恢复呼吸", "confidence": 0.55},
    "RHYTHM_FAKE_RISK": {"family": "rhythm", "level": "high",
        "predicted": "rhythm(空转)", "root_cause": "rhythm_density",
        "prevention": "标签变化必须伴随真实占用变化", "confidence": 0.55},
    "BALANCE_SKEW_RISK": {"family": "balance", "level": "med",
        "predicted": "gravity_drift", "root_cause": "balance_composition",
        "prevention": "配平视觉重量，或声明刻意偏轴的构图理由", "confidence": 0.5},
    "TYPE_LADDER_RISK": {"family": "type_system", "level": "med",
        "predicted": "CRITIC_LOW(typography)", "root_cause": "type_system",
        "prevention": "并级：同层同字号，层次交给字重/墨色", "confidence": 0.6},
    "LAYOUT_MONOTONE_RISK": {"family": "layout_monotony", "level": "med",
        "predicted": "RHYTHM_FLAT", "root_cause": "layout_monotony",
        "prevention": "相邻页至少换一个构图算子", "confidence": 0.5},
    "CONTINUITY_BROKEN_RISK": {"family": "continuity", "level": "med",
        "predicted": "CRITIC_LOW(narrative)", "root_cause": "narrative_continuity",
        "prevention": "让线索在 ≥2 个关键位置复现，或撤掉声明", "confidence": 0.45},
    "TYPE_SCALE_DRIFT_RISK": {"family": "type_system", "level": "med",
        "predicted": "CRITIC_LOW(typography)", "root_cause": "type_system",
        "prevention": "deck 级归并到驻点字阶（64/44/32/22/17/12.5）", "confidence": 0.45},
}

# ── 取舍顺序（低层永不为高层让位；判断冲突时的仲裁表）─────────────────
TRADEOFF_ORDER = [
    {"id": "fact_semantics", "zh": "事实与语义",
     "rule": "数据不为构图造假、不为留白删减、不为美观换口径。无例外。"},
    {"id": "readability", "zh": "可读性",
     "rule": "与审美冲突时牺牲留白，不缩字号。"},
    {"id": "content_task", "zh": "内容任务",
     "rule": "比例/惯例说不通内容关系就放弃。"},
    {"id": "emotion", "zh": "情绪",
     "rule": "高潮页可主动打破节奏，需在 empty_space_role 说明。"},
    {"id": "brand", "zh": "品牌",
     "rule": "品牌规定的字体/色彩/构图优先于通用审美。"},
]


def risk_families() -> list[str]:
    """12 个风险族（目录去重视图）。"""
    seen: list[str] = []
    for meta in RISK_CATALOG.values():
        if meta["family"] not in seen:
            seen.append(meta["family"])
    return seen
