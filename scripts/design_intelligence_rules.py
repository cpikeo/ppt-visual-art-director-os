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

# ── 密度带（与 guard._density_class 实测占用率判读一致）──────────────────
DENSITY_BANDS = {"sparse": (0.0, 0.60), "balanced": (0.65, 0.75),
                 "dense": (0.75, 0.85)}

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

# 复杂度家族（deck 级风险用 route 命名空间；必须 ⊆ FAMILY_MOVES，缺项由 selftest 兜住）
COMPLEX_LAYOUT_FAMILIES = {"FRAMEWORK", "COMPARISON", "TIMELINE",
                           "NARRATIVE", "EXECUTIVE_SUMMARY", "CASE_STUDY"}

# ── 作者可写的枚举字段与合法值（写错必须被点名，不能被静默忽略）────────
# 任何一处取值非法，对应判断都会静默失效：家族 → 媒体/动作/构图全回落；
# 留白职责 → 免检与锚点判断失效；能量/密度 → 节奏与带位判断失效。
EMPTY_SPACE_ROLES = ("protect_focus", "hold_emotion", "create_authority", "separate_chapter")
ENERGY_LEVELS = ("high", "medium", "low")

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
# ── 自适应色彩：方向种子（兜底骨架）。面积律（foundation 70 / supporting 20 /
# information 8 / accent 2）的槽位语义住在 design_intelligence 的 seed 别名逻辑里。
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

