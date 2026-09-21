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

# 复杂度家族（deck 级风险用 route 命名空间；必须 ⊆ FAMILY_TOKENS，缺项由 selftest 兜住）
COMPLEX_LAYOUT_FAMILIES = {"FRAMEWORK", "COMPARISON", "TIMELINE",
                           "NARRATIVE", "EXECUTIVE_SUMMARY", "CASE_STUDY"}

# ── 家族词汇表（唯一真源）─────────────────────────────────────────────
# 引擎认得的所有家族写法：媒体模型的规范名 ∪ route 家族名 ∪ 别名键。
# 此前这份并集在三处各拼一遍（guard 校验 / di 解析 / route 提示），
# 于是「同一个家族名在这里认、在那里不认」只能靠人肉比对。
FAMILY_TOKENS = frozenset(MEDIA_MODEL) | frozenset(FAMILY_ALIASES) | COMPLEX_LAYOUT_FAMILIES


# ── 作者可写的枚举字段与合法值（写错必须被点名，不能被静默忽略）────────
# 任何一处取值非法，对应判断都会静默失效：家族 → 媒体/动作/构图全回落；
# 留白职责 → 免检与锚点判断失效；能量/密度 → 节奏与带位判断失效。
ENERGY_LEVELS = ("high", "medium", "low")

# 键集必须与 route.ROUTES[*]["family"] 一一对应：曾经用 STRUCTURE / PROCESS 命名，
# 全 deck 的架构页与流程页因此永远拿不到专属动作，只能吃兜底句。判断线索错位是最贵的错。

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

