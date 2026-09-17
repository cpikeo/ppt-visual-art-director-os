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
    "PROCESS": (False, 0.05, "序列页：位置即步骤或时间，序列自带视觉性"),
    "COMPARISON": (False, 0.08, "对比页：左右张力来自内容本身"),
    "EVIDENCE": (False, 0.10, "证据页：数字与来源的可信度不需要装饰"),
    "CASE_STUDY": (True, 0.45, "案例页：仅在图像证明现场/人物/结果时使用 proof 媒体"),
}

# route 家族名 → 媒体模型家族（两套命名的一致层，唯一映射源）
# 覆盖要求：每个 route 家族都必须落在一行上，否则该家族静默退回「未知家族」——
# 判断看起来发生了，其实没有。缺项由 selftest 的 11/11 覆盖检查兜住。
FAMILY_ALIASES = {
    "COVER": "HERO", "DATA_STORY": "DATA", "MINIMAL_STATEMENT": "STATEMENT",
    "EDITORIAL": "STORY", "NARRATIVE": "STORY", "FRAMEWORK": "STRUCTURE",
    "TIMELINE": "PROCESS",
    "EXECUTIVE_SUMMARY": "EVIDENCE", "EVIDENCE_FIELD": "EVIDENCE",
    "CASE_STUDY": "CASE_STUDY",
    "HERO_COVER": "HERO", "SECTION_DIVIDER": "SECTION",
}

# ── 字阶驻点与视觉重量 ─────────────────────────────────────────────────
LADDER_RUNGS = (64.0, 44.0, 32.0, 22.0, 17.0, 12.5)  # 驻点字阶
LADDER_TOL = 2.0          # 驻点吸附容差（34 视作 32，避 ±1px 噪声）
TYPE_WEIGHTS = {"text": 1.0, "image": 1.2, "chart": 1.1,
                "native_chart": 1.1, "shape": 0.7}
# 声明型页面允许刻意偏轴——不对称是它们的语言，不是失衡（比较发生在媒体模型命名空间）
ASYMMETRIC_OK_FAMILIES = {"HERO", "CLOSING", "STATEMENT", "SECTION"}

# 复杂度家族（deck 级风险用 route 命名空间；必须 ⊆ FAMILY_MOVES，缺项由 selftest 兜住）
COMPLEX_LAYOUT_FAMILIES = {"FRAMEWORK", "COMPARISON", "TIMELINE",
                           "NARRATIVE", "EXECUTIVE_SUMMARY", "CASE_STUDY"}

# ── 作者可写的枚举字段与合法值（写错必须被点名，不能被静默忽略）────────
# 任何一处取值非法，对应判断都会静默失效：家族 → 媒体/动作/构图全回落；
# 留白职责 → 免检与锚点判断失效；能量/密度 → 节奏与带位判断失效。
EMPTY_SPACE_ROLES = ("protect_focus", "hold_emotion", "create_authority", "separate_chapter")
ENERGY_LEVELS = ("high", "medium", "low")

# ── Page Intent 骨架：家族 → 能量/密度/留白职责 ─────────────────────────

# ── 家族 → 叙事动作（"这页要完成什么"，不是"元素摆哪里"）────────────────
# 刻意只写任务与判断线索，不给坐标：几何与构图归生成侧的设计判断。
FAMILY_MOVES = {
    "HERO": "一个尺度压倒性的事实或形象；除它之外全部降级或删除",
    "COVER": "建立世界观：一句主张 + 一次材质/光线暗示，不放第二主题",
    "DATA_STORY": "结论在上，证据在中，口径与来源在下；一图一个论点",
    "EXECUTIVE_SUMMARY": "决策者只读这页也能行动：结论 → 依据 → 代价",
    "COMPARISON": "共同基线下的取舍：先给判断标准，再给两侧差异",
    "TIMELINE": "方向与节奏：起点、拐点、当前位；不罗列全部时点",
    "FRAMEWORK": "系统关系：层次与依存，用最小结构表达最多信息",
    "NARRATIVE": "路径与状态：谁在何时做什么，清晰到可执行",
    "EDITORIAL": "主张 + 证据并置；文字决定版心，图只服务这句话",
    "CASE_STUDY": "可信度来自细节：约束、取舍、结果与代价",
    "MINIMAL_STATEMENT": "只留一句能被复述的话；留白替这句话工作",
}
# 键集必须与 route.ROUTES[*]["family"] 一一对应：曾经用 STRUCTURE / PROCESS 命名，
# 全 deck 的架构页与流程页因此永远拿不到专属动作，只能吃兜底句。判断线索错位是最贵的错。

# 构图语法池：**描述视线如何被组织**，不给坐标、不给栅格、不给装饰。
# 生成侧可自由改写；这里的价值是给每个家族一个不同的起点，而不是一套固定版式。
COMPOSITION_POOL = {
    "scale_contrast": "一个尺度压倒性的主语（数字/形象/一句话），其余全部降级成注脚",
    "single_column": "单栏顺序阅读，行宽本身构成节奏；不做并置，避免多重第一落点",
    "split_field": "两个并列的场，用共同基线上的差异说话；不平均、不镜像",
    "grid_evidence": "网格化证据面：把多个事实放在同一视线高度上比较",
    "stacked_bands": "横向分层，每层收在一个结论上；层数由内容定，不由模板定",
    "axis_sequence": "一条轴线承载序列与阶段：位置即时间，间隔即权重",
    "edge_anchor": "元素贴边成锚，留白放在中间当主角；靠不对称取得张力",
    "quiet_center": "极小元素居于安静中心，留白承担全部表达",
    "figure_ground": "图与文互为底与图：文字成为画面的一部分，而不是压在图上",
    "radial_focus": "中心聚焦、四周退成背景；只在必要处使用，一次一副即可",
}
COMPOSITION_BY_FAMILY = {
    "COVER": ("scale_contrast", "figure_ground"),
    "HERO": ("scale_contrast", "edge_anchor"),
    "EDITORIAL": ("figure_ground", "single_column"),
    "DATA_STORY": ("grid_evidence", "quiet_center"),
    "EXECUTIVE_SUMMARY": ("stacked_bands", "single_column"),
    "COMPARISON": ("split_field", "grid_evidence"),
    "TIMELINE": ("axis_sequence", "stacked_bands"),
    "FRAMEWORK": ("grid_evidence", "radial_focus"),
    "NARRATIVE": ("stacked_bands", "edge_anchor"),
    "CASE_STUDY": ("split_field", "figure_ground"),
    "MINIMAL_STATEMENT": ("quiet_center", "scale_contrast"),
}

# ── 参考空间实测律（全局；内联唯一真源，无外部覆盖）─────
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
    "precision_minimal": dict(regime="light", sat="quiet", motion=("tech", "spatial"),
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
                   "product_stage": "precision_minimal",
                   "evidence_first": "data_intelligence"}

# ── 风险目录：pre_critic 可发射的 12 族 18 码（元数据镜像）──────────────
# 判据逻辑在 pre_critic；本表是「它会说什么」的机器可读目录，供策略层与
# 自检消费（selftest 断言：实测发射码 ⊆ 本表）。level 标默认档，
# 个别码（RHYTHM_FLAT_RISK 双重趋平时）可在 high/med 间浮动。
RISK_CATALOG = {
    "ACCENT_OVERFLOW": {"family": "accent", "level": "high",
        "predicted": "accent_budget", "root_cause": "chart_selection/color_discipline",
        "prevention": "换图表（一图一关系）或 accent 只留一个元素", "confidence": 0.85,
        "strategy": ("color_policy", "本页 accent 只留 1 处（焦点数字或一个节点），其余回退主/辅色", "accent_area_max 收紧一档，构成类关系改 ranked_bar/大数字")},
    "ACCENT_TIGHT_RISK": {"family": "accent", "level": "med",
        "predicted": "accent_budget(临界)", "root_cause": "color_discipline",
        "prevention": "贴线值留余量：accent 只留一个强调元素", "confidence": 0.6,
        "strategy": ("color_policy", "贴线页把第二个强调元素改主色，留 20% 预算余量", "accent_area_max 收紧一档")},
    "NO_MEMORY_ANCHOR": {"family": "memory_anchor", "level": "high",
        "predicted": "CRITIC_LOW(memorability)", "root_cause": "memory_anchor",
        "prevention": "焦点文字 ≥40px，或图表声明 highlight/center_value/target", "confidence": 0.9,
        "strategy": ("focus_anchor", "焦点文字给到 ≥40px（Statement 级）或声明图表 highlight/center_value", "每页至少一个可指认锚点，写进页面骨架")},
    "CONTRAST_FAIL_RISK": {"family": "contrast", "level": "high",
        "predicted": "READABILITY_FAIL", "root_cause": "theme_contrast",
        "prevention": "加深文字 token 或换更浅的底", "confidence": 0.95,
        "strategy": ("type_color_policy", "把该文字 token 换成 primary/ink，或换更浅的底色", "正文 token 只允许 ≥4.5:1 的组合（工程下限由 QA 兜底）")},
    "CONTRAST_WARN_RISK": {"family": "contrast", "level": "med",
        "predicted": "text_contrast(warn)", "root_cause": "theme_contrast",
        "prevention": "正文级文字用对比 ≥4.5:1 的 token", "confidence": 0.8,
        "strategy": ("type_color_policy", "小字号正文改用对比 ≥4.5:1 的 token", "淡墨只用于装饰与注释，不承担正文")},
    "FOCUS_SCALE_RISK": {"family": "focus", "level": "med",
        "predicted": "CRITIC_LOW(visual_hierarchy)", "root_cause": "focus_anchor",
        "prevention": "拉开尺度比（焦点 ≥1.25× 第二大字）或降级竞争文字", "confidence": 0.85,
        "strategy": ("hierarchy_policy", "拉开尺度比：焦点 ≥1.25× 第二大文字，或降级竞争文字", "一页只允许一个层级顶点")},
    "FOCUS_AREA_RISK": {"family": "focus", "level": "high",
        "predicted": "CRITIC_LOW(visual_hierarchy)", "root_cause": "focus_anchor",
        "prevention": "焦点做大或收窄竞争对象", "confidence": 0.9,
        "strategy": ("hierarchy_policy", "焦点做大或收窄竞争对象面积；焦点改声明真实锚点", "媒体预算 ≤1/页，非焦点对象面积 ≤max(2×焦点,25%画布)")},
    "TEXT_OVERFLOW_RISK": {"family": "text_overflow", "level": "high",
        "predicted": "TEXT_OVERFLOW", "root_cause": "layout_collision",
        "prevention": "padding→行高→字号→重写（或声明 auto_fit）", "confidence": 0.95,
        "strategy": ("text_policy", "声明 auto_fit:true 让阶梯自动吸附，或先拆句/收窄版心", "text_budget 收紧一档，行长上限 38 字（CJK）")},
    "MEDIA_MISUSE_RISK": {"family": "media", "level": "high",
        "predicted": "MEDIA_UNJUSTIFIED", "root_cause": "media_governance",
        "prevention": "删除图片，或把页面改叙事/情绪定位", "confidence": 0.9,
        "strategy": ("media_policy", "删除本页图片（数据/表格/流程/结构页不出图），或改叙事/情绪定位", "媒体政策：图片只在 cover/brand/product/closing 生成")},
    "MEDIA_BUDGET_RISK": {"family": "media", "level": "med",
        "predicted": "CRITIC_LOW(visual_hierarchy)", "root_cause": "media_governance",
        "prevention": "一页一锚点：保留功能最强的一张", "confidence": 0.8,
        "strategy": ("media_policy", "一页一锚点：保留功能最强的一张图", "每页注意力媒体 ≤1")},
    "DENSITY_MISMATCH_RISK": {"family": "density", "level": "med",
        "predicted": "rhythm(空转/趋平)", "root_cause": "rhythm_density",
        "prevention": "按真实占用重新声明，或调整内容量兑现声明", "confidence": 0.6,
        "strategy": ("rhythm_policy", "按真实占用重新声明 density（标签必须兑现）", "疏密曲线重排：相邻页密度互斥")},
    "RHYTHM_FLAT_RISK": {"family": "rhythm", "level": "med",
        "predicted": "RHYTHM_FLAT", "root_cause": "rhythm_density",
        "prevention": "改动一页的密度/能量恢复呼吸", "confidence": 0.55,
        "strategy": ("rhythm_policy", "改动其中一页的内容量或留白，恢复呼吸", "疏密曲线重排：相邻页密度互斥")},
    "RHYTHM_FAKE_RISK": {"family": "rhythm", "level": "high",
        "predicted": "rhythm(空转)", "root_cause": "rhythm_density",
        "prevention": "标签变化必须伴随真实占用变化", "confidence": 0.55,
        "strategy": ("rhythm_policy", "标签变化必须伴随真实墨迹差 ≥0.10", "疏密曲线重排：相邻页密度互斥")},
    "BALANCE_SKEW_RISK": {"family": "balance", "level": "med",
        "predicted": "gravity_drift", "root_cause": "balance_composition",
        "prevention": "配平视觉重量，或声明刻意偏轴的构图理由", "confidence": 0.5,
        "strategy": ("composition_policy", "配平视觉重量（成组/加锚/镜像留白），或在 design_rationale 写明刻意偏轴", "构图算子：连续页至少换一个")},
    "TYPE_LADDER_RISK": {"family": "type_system", "level": "med",
        "predicted": "CRITIC_LOW(typography)", "root_cause": "type_system",
        "prevention": "并级：同层同字号，层次交给字重/墨色", "confidence": 0.6,
        "strategy": ("type_policy", "并级：同层信息同字号，层次交给字重/墨色", "字阶锁在驻点 64/44/32/22/17/12.5，页内 ≤4 级")},
    "LAYOUT_MONOTONE_RISK": {"family": "layout_monotony", "level": "med",
        "predicted": "RHYTHM_FLAT", "root_cause": "layout_monotony",
        "prevention": "相邻页至少换一个构图算子", "confidence": 0.5,
        "strategy": ("composition_policy", "相邻页至少改一个构图算子（切分/轴/尺度对偶）", "同家族连续 ≥3 页必须换构图语法或声明品牌连续性")},
    "CONTINUITY_BROKEN_RISK": {"family": "continuity", "level": "med",
        "predicted": "CRITIC_LOW(narrative)", "root_cause": "narrative_continuity",
        "prevention": "让线索在 ≥2 个关键位置复现，或撤掉声明", "confidence": 0.45,
        "strategy": ("continuity_policy", "让该记忆线在 ≥2 个关键位置复现（章节转场/收尾呼应），或撤掉声明", "记忆线成线：token 至少出现两次")},
    "TYPE_SCALE_DRIFT_RISK": {"family": "type_system", "level": "med",
        "predicted": "CRITIC_LOW(typography)", "root_cause": "type_system",
        "prevention": "deck 级归并到驻点字阶（64/44/32/22/17/12.5）", "confidence": 0.45,
        "strategy": ("type_policy", "全 deck 归并到驻点字阶", "字阶锁在驻点，页内 ≤4 级")},
    "INTENT_UNCLEAR": {"family": "focus", "level": "high",
        "predicted": "INTENT_UNCLEAR", "root_cause": "intent_clarity",
        "prevention": "先写一句 object+change+implication，再排版", "confidence": 0.95,
        "strategy": ("focus_anchor", "先补一句可复述结论（object+change+implication），再排版", "每页 page_intent.insight 必须可脱离页面复述")},
    "FOCUS_UNBOUND": {"family": "focus", "level": "med",
        "predicted": "CRITIC_LOW(visual_hierarchy)", "root_cause": "focus_anchor",
        "prevention": "把 focus 指向真实元素 id；唯一 L4 通常是结论文字", "confidence": 0.9,
        "strategy": ("focus_anchor", "把 focus 指向真实元素 id（通常结论文字）", "focus 必须对应页面真实元素，否则不落稿")},
    "CARD_WALL_RISK": {"family": "layout_monotony", "level": "med",
        "predicted": "CRITIC_LOW(visual_hierarchy)", "root_cause": "container_discipline",
        "prevention": "删容器，改发丝线+留白+字阶分组；只留数据/KPI 面板", "confidence": 0.7,
        "strategy": ("hierarchy_policy", "删圆角容器，改发丝线+留白+字阶分组；只留数据/KPI 面板", "圆角容器 ≤4/页，其余用发丝线+留白表达层级")},
    "TEXT_BUDGET_RISK": {"family": "text_overflow", "level": "med",
        "predicted": "CRITIC_LOW(visual_hierarchy)", "root_cause": "text_budget",
        "prevention": "合并重复语句：一个文本框只承担一个语义角色", "confidence": 0.6,
        "strategy": ("text_policy", "合并重复语句：一个文本框只承担一个语义角色", "阅读文本 ≤4/页（caption/annotation/source/axis 不计）")},
}

