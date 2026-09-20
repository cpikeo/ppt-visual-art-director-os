# -*- coding: utf-8 -*-
"""
asset_prompt.py · 视觉资产提示词组装器（纯函数层）

职责：把「资产卡（card）」+「页面版面参数（page）」拼接成**确定性**的英文提示词。

设计约束（与 PPT Design OS 架构一致）：
  * **不持有任何主题**：本文件不含任何 VP 人格、色板或资产卡数据。
    资产卡由调用方准备好后传入（必填段见 REQUIRED_SEGMENTS，溯源见 validate_asset_card）。
  * **不写死设计参数**：留白锚点、光向、能量全部由调用方传入；缺省时才用保守默认。
  * **不做设计决策**：只拼接与去重，不替调用方挑选资产卡或判断该不该出图。
  * 与 `compiler.py` 一样支持「参数模块 + CLI」两种调用方式。

组装顺序：
  subject → color → material → lighting → composition → motion → style
  → [留白锚点] → [光向] → [能量上限] → [资产功能]
  → Universal QC → 资产类型后缀
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

# --------------------------------------------------------------------------
# 通用质量控制后缀（英文原样，模型侧不翻译）
# --------------------------------------------------------------------------
# 组装时使用的紧凑质量尾段；泛化的 luxury/premium 词会稀释主体、空间和材质，
# 因此生产 prompt 只保留这组最小契约。旧 UNIVERSAL_QC 全量词库已无消费者，
# 按「死常量不保留」纪律删除；比例句由组装第 4 步按实际 ratio 生成。
PROMPT_QC_COMPACT: tuple[str, ...] = (
    "clean composition", "no text", "no logo", "no watermark",
    "no UI elements", "no clutter",
)

# 基础反向约束（与 PROMPT_QC_COMPACT 的 no-* 项对应，供支持独立 negative 的模型使用）
NEGATIVE_BASE: tuple[str, ...] = (
    "text",
    "letters",
    "numbers",
    "typography",
    "logo",
    "watermark",
    "UI elements",
    "clutter",
    "busy composition",
)

# --------------------------------------------------------------------------
# 通用廉价症状拦截层（F12/v4.20——负面清单走出文档、落在出图层）
# 包的避讳谱（Stock Photo Feeling / 人物摆拍 / Excessive Icons / Neon /
# 机器人元素 / Glassmorphism / 科技蓝渐变 / Cheap AI Aesthetic）此前只活在
# 审查语言里，出图层一条没拦——city skyline 卡可以大摇大摆端回一张图库握手照。
# 本表是**既有口味法的执行**，不是新口味：每个短语在负面清单中有案源。
# 守门纪律：排除廉价，不堆砌高级词——prompt 通胀（叠 luxury 词）不是质量门。
# 刻意缺席：「3d render」——illustration 正向本就要求 3D minimal，
# 3D Decoration 症状由水墨闸门按族拒绝，不进通用层（防自相矛盾）。
#
# v5.3 分层：全量负向清单对每张图无差别注入，会稀释对**这一张**真正要紧的
# 反向词——静物青瓷摄影并不需要「no humanoid robot」。按「画面里可能有什么」
# 分三层组装（见 build_asset_prompt 第 5 步）：
#   UNIVERSAL_CHEAP_REJECTS  恒注入（画幅失效/图库感/廉价 AI 感，任何主体都中招）
#   HUMAN_SCENE_REJECTS      主体可能出现人物时才注入（摆拍/握手/机器人）
#   TECH_STYLE_REJECTS       非水墨资产才注入（赛博朋克/玻璃拟态；水墨闸门有自己的反向清单）
# --------------------------------------------------------------------------
UNIVERSAL_CHEAP_REJECTS: tuple[str, ...] = (
    "generic stock photo",                        # Stock Photo Feeling
    "clip art", "clipart illustration",           # Excessive Icons → 剪贴画感
    "neon glow",                                  # Neon（D06 禁项）
    "tech blue gradient", "rainbow gradient",     # Excessive Gradients / 科技蓝渐变
    "plastic skin", "oversaturated colors",       # Cheap AI Aesthetic
    "heavy HDR", "AI artifacts",
    # 边框类：模型把「四周留白」误读成「加一圈画框 / 白边 / 黑边」是高频失效模式。
    # 实测：prompt 里写 generous margins on all four sides，就输出了一张竖构图
    # 带白边的 letterbox —— 画幅整段作废，这张图只能重出。这不是审美问题，
    # 是画幅失效，所以放进通用反向，不留给逐页去记。
    "white border", "black bars", "letterbox", "picture frame", "poster mockup",
    # 假留白面板：实测失效模式——「留白区」被画成一块硬边平色块，边界肉眼可见。
    # 与 letterbox 同类（画幅失效），因此进通用反向，不留给逐页去记。
    "flat painted panel", "hard-edged rectangle of flat tone", "visible seam or step edge",
)
HUMAN_SCENE_REJECTS: tuple[str, ...] = (
    "cliché corporate imagery", "corporate handshake",
    "posed smiling people", "thumbs up",          # 人物摆拍
    "humanoid robot", "robot mascot",             # 机器人元素（D06 禁项）
)
TECH_STYLE_REJECTS: tuple[str, ...] = (
    "cyberpunk",                                  # Neon Cyberpunk（D06 禁项）
    "glassmorphism", "frosted glass panels",      # Glassmorphism
)

# 主体可能涉及人物的词：命中任一即注入 HUMAN_SCENE_REJECTS。
# 宁可多注入（反向词不伤正向画面），不可漏注入（图库握手照是最贵的废图）。
PERSON_SUBJECT_TERMS: tuple[str, ...] = (
    "人", "用户", "客户", "团队", "员工", "创始", "肖像", "手部", "面部", "身影",
    "people", "person", "team", "founder", "user", "customer", "portrait",
    "hands", "face", "crowd", "audience", "silhouette",
)


def _term_hit(text: str, term: str) -> bool:
    """CJK 用子串；ASCII 用词边界（避免 handmade 命中 hand、user 命中 userland）。"""
    import re
    if all(ord(c) < 128 for c in term):
        return re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", text) is not None
    return term in text


def subject_implies_people(card: dict) -> bool:
    """主体/世界/风格语言里是否可能出现人物（决定人物场景反向词注不注入）。

    只扫 subject / world / style：material 与 texture 是材质语言
    （handmade paper 里有 hand，但那不是人手），不参与判定。
    """
    if not isinstance(card, dict):
        return False
    blob = " ".join(str(x) for k in ("subject", "world", "style")
                    for x in _as_list(card.get(k))).lower()
    return any(_term_hit(blob, t) for t in PERSON_SUBJECT_TERMS)

# --------------------------------------------------------------------------
# 水墨纪律闸门（F6/v4.17——材质语言的执行质量保底）
# 每当资产卡已经选择了水墨语言（subject/material/style 等含水墨词），
# 注入两组确定性短语：正向「工艺纪律」（让图像模型往真·水墨画法走）
# 与反向「廉价水墨症状」（把默认滑向商业图库/数字喷枪的概率压到最低）。
# 不做审美决策——是否用水墨是调用方的事；闸门只在「选择了却画得廉价」
# 这个失效模式上兜底（案源：2026-annual-review dawn-summit 首版翻车）。
# --------------------------------------------------------------------------
INK_TERMS: tuple[str, ...] = (
    "ink-wash", "ink wash", "inkwash", "sumi-e", "sumi e", "shui-mo",
    "shuimo", "水墨", "宣纸", "笔墨", "泼墨", "写意", "oriental ink",
    "chinese ink", "east asian ink", "rice paper",
)
INK_DISCIPLINE: tuple[str, ...] = (
    "hand-painted Chinese ink-wash (shui-mo / sumi-e) painting",
    "single deliberate brushwork, dry-brush gradients with visible stroke structure",
    "generous unpainted rice-paper ground, more than half the frame left empty",
    "limited ink tonal range of three to four values",
    "forms built from confident strokes, no photographic outlines or shading",
)
INK_CHEAP_REJECTS: tuple[str, ...] = (
    "photographic landscape", "stock photo scenery",
    "muddy gray ink pooling", "random paint splatter",
    "oversaturated red sun disc", "photorealistic animals",
    "clip-art bamboo", "digital airbrush gradients",
    "symmetric centered composition", "heavy vignette",
    "watercolor clip-art", "3d render", "postcard look",
)


def ink_gate_active(card: dict) -> bool:
    """资产卡是否已选择水墨语言（纯检测，供调用方/自检复用）。

    判据是**这张资产自己**的介质声明，不是整副 deck 的方向：

      * `medium`——最明确的信号（`chinese ink-wash painting` / `水墨`）；
      * subject / color / composition / style 里出现水墨词汇；
      * 逐页亲手写下的 material / lighting。

    不扫 enhance_asset_card 自动注入的 motion/texture 弱描述（微浮雕里一句
    rice paper 是材质底味，不等于选择了水墨画），也不扫方向默认值
    （`material_source == "direction"` 说的是整副 deck 用什么质感说话——
    一份宋韵里每张照片都拍在纸台上，不代表每张照片都是水墨画）。

    这里曾经还认一个方向族名白名单（song_elegance）：方向名送不进来时它永不命中，
    送进来之后又把全 deck 的摄影页一起拖成水墨——两头都是错的，已删除。
    """
    if not isinstance(card, dict):
        return False
    fields = [card.get("medium"), card.get("subject"), card.get("color"),
              card.get("composition"), card.get("style")]
    for key in ("material", "lighting"):
        if str(card.get(f"{key}_source") or "declared").lower() != "direction":
            fields.append(card.get(key))
    blob = " ".join(str(x) for seg in fields for x in _as_list(seg)).lower()
    return any(t.lower() in blob for t in INK_TERMS)



# --------------------------------------------------------------------------
# 摄影写实纪律闸门（v4.21——摄影语言的执行质量保底，与水墨闸门同源同理）
# 资产卡语言为摄影（background 型、非水墨、非插画/3D/矢量）时注入少量正向
# 写实纪律：光有方向与衰减、空间有空气与真实尺度、质感有胶片性格。
# 闸门不做审美决策——拍还是画是调用方的事；它只压「选了摄影感却滑向
# 塑料商业图」的默认分布。廉价症状的反向清单住在 UNIVERSAL_CHEAP_REJECTS
# （heavy HDR / plastic skin / oversaturated / generic stock photo 已有案源），
# 这里只补过度锐化与均匀布光两条新案源（高端品牌项目校准）。
# 守门纪律不变：排除廉价，不堆砌高级词——正向仅 3 句。
# --------------------------------------------------------------------------
_PHOTO_STYLE_EXCLUDE = ("illustration", "3d", "vector", "render", "painting",
                        "clipart", "ink", "sumi")
PHOTO_REALISM_DISCIPLINE: tuple[str, ...] = (
    "single natural light source with visible direction and gentle falloff",
    "subtle atmospheric perspective, faint air between planes",
    "true-to-life spatial scale, medium format film character, soft micro grain",
)
PHOTO_CHEAP_REJECTS: tuple[str, ...] = (
    "over-sharpened details", "uniform flat studio lighting",
)


def photo_gate_active(card: dict) -> bool:
    """资产卡是否已选择摄影语言（纯检测）。插画/3D/矢量/水墨卡不点火。"""
    if not isinstance(card, dict):
        return False
    if (card.get("asset_type") or "background") != "background":
        return False
    if ink_gate_active(card):
        return False
    medium = str(card.get("medium") or card.get("render_mode") or "").strip().lower()
    blob = " ".join(str(card.get(k) or "") for k in
                    ("style", "subject", "material", "lighting")).lower()
    if medium:
        # A declared medium wins.  "background" alone must not silently
        # turn an abstract/editorial card into a stock-photography prompt.
        return medium in {"photo", "photography", "photographic", "film"}
    return ("photograph" in blob or "photographic" in blob
            or "film" in blob) and not any(w in blob for w in _PHOTO_STYLE_EXCLUDE)


NEGATIVE_SPACE_PHRASES = {
    "left": "large clean negative space on the left side",
    "right": "large clean negative space on the right side",
    "top": "quiet empty area in the upper part",
    "bottom": "quiet empty area in the lower part",
    "center": "quiet calm center area, activity pushed to the edges",
}

# deck 级构图语法键名 → 可读英文构图语言。内部枚举键（evidence_field /
# soft_asymmetry …）对图像模型没有任何含义，裸键名进提示词是纯噪声，
# 还计入资产指纹（换个键名 = 整批重出图）。翻译只发生在这一处。
GRAMMAR_PHRASES: dict[str, str] = {
    "soft_asymmetry": "asymmetric editorial composition with deliberate off-center balance",
    "strict_grid": "disciplined grid composition with margins aligned to a strict module",
    "cinematic_stage": "cinematic staged composition with a single lit focal plane",
    "evidence_field": "calm evidence-field composition, subject and captions sharing one axis",
    "path_sequence": "sequential composition leading the eye along a clear path",
}


def grammar_phrase(value) -> str:
    """构图语法：键名翻译成可读语言；自由文本原样保留（显式写下的句子永远赢）。"""
    text = str(value or "").strip()
    if not text:
        return "asymmetric editorial composition"
    return GRAMMAR_PHRASES.get(text.lower(), text)


# 颜色 hex → 可读色名：图像模型对 #hex 基本不响应，颜色名才是可执行语言。
# 只做「色相族 + 明度/饱和修饰」三档，不做色名词典——够模型选对颜料即可。
_HUE_NAMES: tuple[tuple[float, str], ...] = (
    (15.0, "red"), (45.0, "orange"), (70.0, "yellow"), (100.0, "olive green"),
    (160.0, "green"), (200.0, "teal"), (255.0, "blue"), (290.0, "indigo"),
    (335.0, "magenta"), (361.0, "red"),
)


def hex_to_color_name(value) -> str | None:
    """'#5E7562' → 'muted green' 风格的可读色名；解析失败返回 None（调用方保留 hex）。"""
    import colorsys
    text = str(value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        return None
    try:
        r, g, b = (int(text[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return None
    mx, mn = max(r, g, b), min(r, g, b)
    chroma = mx - mn
    light = (mx + mn) / 2.0
    if chroma < 0.08:                      # 近无彩：按明度命名，不进色相桶
        if light >= 0.93:
            return "white"
        if light >= 0.72:
            return "pale gray"
        if light >= 0.38:
            return "neutral gray"
        if light >= 0.16:
            return "charcoal"
        return "near black"
    hue = colorsys.rgb_to_hls(r, g, b)[0] * 360.0
    sat = chroma / (2.0 - mx - mn) if light > 0.5 else (chroma / (mx + mn) if (mx + mn) > 0 else 0.0)
    name = next(n for upper, n in _HUE_NAMES if hue < upper)
    tone = "pale" if light >= 0.78 else "deep" if light <= 0.26 else ""
    mod = "muted" if sat < 0.28 else "vivid" if sat > 0.72 else ""
    return " ".join(p for p in (tone, mod, name) if p)


# Normalized safe zones are shared by prompt generation and asset QC.  The
# prompt receives both a human direction and the geometric fraction so a model
# can preserve a usable text field instead of merely hearing "leave space".
SAFE_AREA_PRESETS = {
    # "none"：版面不压文字（如整幅画心、半幅出血带）。此时不再注入任何
    # 「安静面」句式，QC 也不再拿默认矩形去检查——没有文字压图，就没有安全区。
    "none": {},
    "left": {"x": 0.06, "y": 0.08, "width": 0.34, "height": 0.78},
    "right": {"x": 0.60, "y": 0.08, "width": 0.34, "height": 0.78},
    "top": {"x": 0.08, "y": 0.06, "width": 0.84, "height": 0.27},
    "bottom": {"x": 0.08, "y": 0.67, "width": 0.84, "height": 0.25},
    "center": {"x": 0.30, "y": 0.28, "width": 0.40, "height": 0.44},
}


def normalize_safe_area(value=None, anchor: str = "left") -> dict:
    """Return a bounded x/y/width/height fraction for prompt and QC."""
    if anchor == "none" and not value:
        return {}
    if isinstance(value, dict) and not value:
        return {}                       # 显式空矩形 = 版面不压文字（无安全区）
    raw = value if isinstance(value, dict) else SAFE_AREA_PRESETS.get(anchor, SAFE_AREA_PRESETS["left"])
    try:
        x = max(0.0, min(1.0, float(raw.get("x", 0.0))))
        y = max(0.0, min(1.0, float(raw.get("y", 0.0))))
        w = max(0.01, min(1.0 - x, float(raw.get("width", 0.3))))
        h = max(0.01, min(1.0 - y, float(raw.get("height", 0.3))))
    except (TypeError, ValueError, AttributeError):
        return dict(SAFE_AREA_PRESETS.get(anchor, SAFE_AREA_PRESETS["left"]))
    return {"x": round(x, 4), "y": round(y, 4),
            "width": round(w, 4), "height": round(h, 4)}


def safe_area_phrase(area: dict, text_color: str | None = None) -> str:
    """留白指令，只用视觉语言，不写坐标。

    为什么删掉坐标（v5.6）：提示词里写「x 6%, y 8%, width 34%, height 78%」时，
    图像模型会给一个**字面答案**——把那块矩形画成硬边的平色面板。实测证据：两张交付
    资产在 33.1% / 17.9% 宽度处出现 28.6 / 9.7 灰阶的列均值阶跃，被圈住的一侧整带
    标准差只有 0.4 / 0.6 灰阶（真实材质留白是 1.7–5.3）。留白该描述材质与光的衰减，
    矩形坐标属于 QC 的内部量（safe_area 仍作为检查矩形）。空 area = 版面不压文字，
    此时一个字都不给，S 版面自己承担安静面。
    """
    if not area:
        return ""
    dark = str(text_color or "").lower() != "light"
    if dark:
        return ("the open side of the frame stays quiet and unbroken, its even tone coming from "
                "light falling off across the material, never from a painted block")
    return ("the open side of the frame stays dark and unbroken, its shadow coming from light "
            "falling away across the material, never from a painted block")


LIGHT_PHRASES = {
    "left": "soft directional light from the upper left",
    "right": "soft directional light from the upper right",
    "top": "soft even top light",
    "radial": "soft radial falloff from the center to the edges",
    "none": "flat even ambient light, no visible light source",
}

ENERGY_PHRASES = {
    "low": ("very low contrast, no dramatic highlights, no glowing edges, "
            "no strong vignette, no bokeh"),
    "medium": "controlled contrast, single soft light source, no hard specular highlights",
    "high": "one dramatic light source, cinematic contrast",
}

ASSET_FUNCTION_PHRASES = {
    "frame": "the image frames the message without competing with it",
    "separate": "the image separates sections while staying quiet",
    "direct": "the light leads the eye toward the main subject",
    "contextualize": "the image establishes context while keeping the foreground readable",
    "immersive": "immersive cinematic full-bleed background environment, soft atmospheric depth, spacious foreground for typography",
}

# 资产类型后缀
ASSET_TYPE_SUFFIX = {
    "background": (),  # 比例句（"16:9 presentation background"）由组装第 4 步按实际 ratio 生成
    "illustration": (
        "3D minimal illustration",
        "soft material",
        "editorial style",
        # 透明底只描述一次，避免 "transparent background" + "no background" 冗余矛盾表述
        "isolated on pure transparent background, clean cutout, no scenery behind",
    ),
    "icon": (
        "single line icon",
        "thin stroke",
        "consistent weight",
        "no fill",
        "minimal",
        "SVG style",
        "isolated on pure transparent background, clean cutout",
    ),
}

# 透明资产对比度防护：
# 透明底 + 主体色与幻灯片底色同明度 = 插图"无背景色"且"与主题色差相同"（零对比、被吞没）。
# 必须在 prompt 显式要求主体与底色形成明确明度差。脚本不持有主题，
# 故"从 foreground 角色取色"由调用方在 CARD.color 中保证（见 §6.1）。
ASSET_CONTRAST_GUARD = {
    "illustration": (
        "subject tone clearly contrasts with the slide background, bold readable silhouette",
        "no low-contrast wash that blends into the page",
    ),
    "icon": (
        "stroke tone clearly contrasts with the slide background",
    ),
}

# 卡片中参与组装的段（按 §6.2 顺序）
# `world` 是 deck 级视觉世界（材质 + 光影 + 空间的一句话），它进提示词当氛围语言，
# 但**不参与介质闸门扫描**——闸门问的是「这张资产选了什么语言」，那是资产级的事。
# `style` 仍是卡片级显式风格，照旧参与扫描。
CARD_SEGMENTS = ("subject", "color", "material", "lighting", "composition",
                 "motion", "style", "world")
REQUIRED_SEGMENTS = ("subject", "color", "material", "lighting", "composition")


# --------------------------------------------------------------------------
# 内部工具
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# 提示词智能三层：动势（Motion）/ 微浮雕（Micro Texture）/ 空间融合（Fusion）
# 图片不是静态素材：动势给视觉方向，微浮雕给近观质感，融合消灭「贴纸感」。
# 全部为弱描述子句；微浮雕纪律：微弱、低对比、近距可感知，禁止明显纹理。
# --------------------------------------------------------------------------
MOTION_LAYERS: dict[str, tuple[str, ...]] = {
    "spatial": (
        "leading lines drawing the eye toward the negative-space anchor",
        "architectural perspective receding to a single vanishing point",
        "flowing composition with deliberate asymmetric balance",
        "directional light raking across the frame from one side"),
    "natural": (
        "slow flowing water with silk-like motion blur",
        "organic curves and wind movement through foliage",
        "layered atmosphere with aerial depth and drifting mist",
        "gentle natural gesture implying quiet movement"),
    "tech": (
        "dynamic light trails with restrained velocity",
        "subtle energy flow along precision-machined edges",
        "spatial depth through layered translucent glass planes"),
}
TEXTURE_LAYERS: dict[str, tuple[str, ...]] = {
    "eastern": ("handmade paper fiber", "rice paper texture",
                "subtle ink diffusion at the edges", "natural mineral pigment grain"),
    "luxury": ("fine leather grain", "brushed metal micro texture",
               "soft stone surface", "premium packaging emboss with low relief"),
    "architecture": ("limestone micro texture", "board-formed concrete pore",
                     "glass reflection with faint refraction"),
    "technology": ("titanium micro brushing", "precision machining marks",
                   "anodized surface sheen"),
    "organic": ("leaf vein macro structure", "woven natural fiber",
                "moss and lichen micro detail"),
}
TEXTURE_DISCIPLINE: tuple[str, ...] = (
    "texture faint and low-contrast, perceivable only at close range",
    "no obvious pattern, no grunge, no heavy grain")
# 具象主体（hero 产品 / proof 实证）的清晰度与可辨识是硬要求：
# 「流水运动模糊 / 光轨」这类动势语言注进静物摄影就是废图指令。
# 键名展开时，静态主体改取各层的静态安全句（自由文本仍原样保留——作者显式写的永远赢）。
STATIC_MOTION_INDEX: dict[str, int] = {"spatial": 0, "natural": 3, "tech": 1}
STATIC_SUBJECT_FUNCTIONS = frozenset({"hero", "proof", "direct"})
FUSION_LAYERS: tuple[str, ...] = (
    "image melts into the layout background, no sticker edges, no hard rectangle",
    "negative space reserved and aligned to the text-safe area",
    "lighting direction consistent with the page light source",
    "depth hierarchy: foreground subject, midground material, background atmosphere",
    "foreground and background separated by gentle defocus")
FAMILY_MOTION: dict[str, tuple[str, ...]] = {
    "nature_luxury": ("natural", "spatial"), "nordic_quiet": ("spatial",),
    "monochrome_noir": ("spatial",), "zen_minimal": ("natural",),
    "luxury_editorial": ("spatial",), "precision_tech": ("tech",),
    "organic_systems": ("natural",), "cinematic_narrative": ("spatial", "natural"),
    "editorial_intelligence": ("spatial",), "quiet_luxury": ("spatial",),
    "song_elegance": ("natural",), "precision_minimal": ("tech", "spatial"),
    "data_intelligence": ("tech",),
}
FAMILY_TEXTURE: dict[str, tuple[str, ...]] = {
    "nature_luxury": ("organic", "architecture"), "nordic_quiet": ("architecture",),
    "monochrome_noir": ("architecture",), "zen_minimal": ("eastern",),
    "luxury_editorial": ("luxury", "architecture"), "precision_tech": ("technology",),
    "organic_systems": ("organic",), "cinematic_narrative": ("luxury", "architecture"),
    "editorial_intelligence": ("eastern",), "quiet_luxury": ("luxury",),
    "song_elegance": ("eastern",), "precision_minimal": ("technology",),
    "data_intelligence": ("technology",),
}


def _expand_layer(spec, table: dict, index: dict | None = None) -> list[str]:
    """把「层键名 or 自由文本」统一展开成可读语言。

    键名（`eastern` / `natural` / `luxury` …）查表取句：默认第一句；
    `index` 给出按层键的替代下标（静物主体避开运动模糊句，见 STATIC_MOTION_INDEX）。
    自由文本原样保留——调用方显式写下的句子永远赢，这是全包的既有纪律，
    不在这一层改变。方向族传下来的是键名（见 route._direction_execution），
    brief 里逐页写的是文本，两种写法都要能用，且展开只发生在这一处。
    """
    out: list[str] = []
    for item in _as_list(spec):
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in table:
            phrases = table[key]
            out.append(phrases[min((index or {}).get(key, 0), len(phrases) - 1)])
        else:
            out.append(text)
    return out


def enhance_asset_card(card: dict, family: str | None = None,
                       motion: list | tuple | None = None,
                       texture: list | tuple | None = None,
                       fusion: bool = True) -> dict:
    """纯函数：为资产卡注入动势/微浮雕/融合三层（确定性、去重、限量）。

    默认 motion 1 句、texture 1 句、fusion 1–2 句——
    提示词密度也是克制的一部分；调用方显式传入时永远赢。

    `family` 收的是**方向族名**（song_elegance / zen_minimal …），不是页面家族名：
    FAMILY_MOTION / FAMILY_TEXTURE 的键全是族名，传页面家族名会静默落进
    ("spatial",) / ("luxury",) 兜底——一份年报里每张图都吃「fine leather grain」。
    """
    out = dict(card)
    fam = family or str(card.get("family") or card.get("direction_family") or "")
    m_keys = FAMILY_MOTION.get(fam, ("spatial",))
    t_keys = FAMILY_TEXTURE.get(fam, ("luxury",))
    # 具象主体（hero/proof/direct）不吃运动模糊与光轨：动势语言只属于氛围类资产。
    static_subject = (str(card.get("asset_function") or "").lower()
                      in STATIC_SUBJECT_FUNCTIONS)
    m_index = STATIC_MOTION_INDEX if static_subject else None
    if motion is None:
        motion = _expand_layer(m_keys, MOTION_LAYERS, m_index)[:1]
    else:
        motion = _expand_layer(motion, MOTION_LAYERS, m_index)
    if texture is None:
        texture = _expand_layer(t_keys, TEXTURE_LAYERS)[:1]
    else:
        texture = _expand_layer(texture, TEXTURE_LAYERS)
    out["motion"] = list(motion)
    out["texture"] = list(texture) + list(TEXTURE_DISCIPLINE)
    if fusion:
        out["fusion"] = list(card.get("fusion") or FUSION_LAYERS[:2])
    return out


def _dedup(items, *, normalize_negative: bool = False):
    """保持顺序去重，忽略空白项与重复短语。

    `normalize_negative=True` 时忽略 `no ` 前缀（`"no text"` 与 `"text"` 视为同一条），
    用于反向提示词，避免同一约束以两种写法重复出现。
    """
    seen, out = set(), []
    for raw in items:
        if raw is None:
            continue
        text = str(raw).strip().strip(",.").strip()
        if not text:
            continue
        key = text.lower()
        if normalize_negative:
            key = key[3:] if key.startswith("no ") else key
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def validate_asset_card(card: dict) -> list[str]:
    """静态自检：返回问题列表（空列表 = 通过）。供调用方在出图前排查漏项。"""
    issues = []
    if not isinstance(card, dict):
        return ["card 必须是 dict"]
    for key in REQUIRED_SEGMENTS:
        if not _as_list(card.get(key)):
            issues.append(f"缺少必填段: {key}")
    asset_type = card.get("asset_type", "background")
    if asset_type not in ASSET_TYPE_SUFFIX:
        issues.append(f"未知 asset_type: {asset_type}"
                      f"（可选 {sorted(ASSET_TYPE_SUFFIX)}）")
    if not card.get("apc"):
        issues.append("缺少 apc：资产卡编号未溯源")
    if card.get("subject_source") == "title_fallback":
        issues.append("未声明 asset_subject：主体描述取自页面标题。"
                      "标题是观点（「这一年真正的收获，不是增速」），不是画面；"
                      "照着它出图会跑偏——补一句画面描述再出图。")
    subject_blob = " ".join(str(x) for x in _as_list(card.get("subject")))
    if any("\u4e00" <= ch <= "\u9fff" for ch in subject_blob):
        issues.append("subject 含中文：多数图像模型对英文主体的遵循度更高，"
                      "建议把画面描述改写为英文（清单保留原文供人核对；这是提醒，不阻断）")
    return issues


# --------------------------------------------------------------------------
# 主函数
# --------------------------------------------------------------------------
def build_asset_prompt(card: dict, page: dict | None = None, *,
                       ratio: str = "16:9",
                       include_qc: bool = True,
                       extra_negative=(),
                       negative_space: str | None = None,
                       light_direction: str | None = None,
                       energy: str | None = None,
                       asset_function: str | None = None,
                       separator: str = ", ") -> dict:
    """把资产卡与页面参数组装成确定性英文提示词。

    参数优先级：关键字参数 > `page` 字典 > 保守默认（left / left / low / frame）。
    `card` 与 `page` 均由调用方传入，本函数不持有任何主题数据。

    返回: {"prompt": str, "negative": str, "meta": {...}}
    """
    if not isinstance(card, dict):
        raise TypeError("card 必须是 dict")
    page = page or {}

    asset_type = card.get("asset_type") or "background"
    if asset_type not in ASSET_TYPE_SUFFIX:
        raise ValueError(f"未知 asset_type: {asset_type}")

    # 介质闸门只判一次，正向纪律与光照纪律、反向分层共用同一个结论。
    ink = ink_gate_active(card)
    photo = photo_gate_active(card)
    # 光照单一来源：逐页显式声明 > 介质纪律光语 > 方向/兜底光。三层同时注入会
    # 自相矛盾（flat even ambient vs one dramatic light source vs negative 的
    # no uniform flat studio lighting），模型只能对矛盾指令做平均——不可预测的
    # 光比没有光更贵。摄影资产由 PHOTO_REALISM_DISCIPLINE 独家给光；
    # 作者逐页写了 lighting 时以作者为准，方向光与句式光全部让位。
    lighting_declared = str(card.get("lighting_source") or "").lower() == "declared"
    photo_light_override = photo and not lighting_declared

    # --- 1. 资产卡主体段 -------------------------------------------------
    segments = []
    for key in CARD_SEGMENTS:
        if key == "lighting" and photo_light_override:
            continue        # 预设/兜底光让位给摄影写实光语，避免同帧两种光
        segments.extend(_as_list(card.get(key)))

    # --- 2. 有机层 / 叠加层描述（可选，只作为弱描述进入 prompt） --------
    layers = card.get("layers") or {}
    if isinstance(layers, dict):
        if layers.get("overlay"):
            segments.append(f"overlaid with {layers['overlay']}")
        if layers.get("organic_shapes"):
            segments.append(f"{layers['organic_shapes']} organic shapes")

    # --- 三层：动势 / 微浮雕 / 空间融合（enhance_asset_card 注入）---
    # 融合只对背景/框景类资产默认开启；icon、产品主体和明确分离的
    # 资产保留边界，避免「无贴纸边缘」变成所有图片的同一种质感。
    function_hint = str(asset_function or page.get("asset_function")
                         or card.get("asset_function") or "frame").lower()
    fusion_allowed = card.get("fusion_enabled")
    if fusion_allowed is None:
        fusion_allowed = asset_type == "background" or function_hint in {
            "frame", "separate", "context", "contextualize"
        }
    segments.extend(_as_list(card.get("motion"))[:1])
    texture = _as_list(card.get("texture"))
    # One material cue + one discipline cue is enough; prompt length is part
    # of visual direction and excess adjectives reduce model fidelity.
    segments.extend(texture[:2])
    if fusion_allowed:
        segments.extend(_as_list(card.get("fusion"))[:2])

    # --- 水墨纪律闸门：已选水墨语言 → 注入工艺纪律 + 廉价症状反向清单 ---
    if ink:
        segments.extend(INK_DISCIPLINE)
    if photo:
        # 光照单一来源的最后一块：作者逐页声明了 lighting 时，摄影写实层的
        # 光句（首句）也让位——介质句（大气透视/胶片质感）保留，那不是光。
        segments.extend(PHOTO_REALISM_DISCIPLINE[1:] if lighting_declared
                        else PHOTO_REALISM_DISCIPLINE)

    # --- 3. OS 强制三段 --------------------------------------------------
    anchor = str(negative_space or page.get("negative_space_anchor") or "left").lower()
    light = str(light_direction or page.get("light_direction") or "left").lower()
    level = str(energy or page.get("energy") or "low").lower()
    function = str(asset_function or page.get("asset_function") or function_hint).lower()
    area = normalize_safe_area(page.get("safe_area"), anchor)
    text_color = page.get("text_color") or page.get("safe_area_text_color")
    medium = str(card.get("medium") or card.get("render_mode") or "").strip().lower()

    if medium:
        segments.append(f"{medium} medium")
    if anchor in NEGATIVE_SPACE_PHRASES:
        segments.append(NEGATIVE_SPACE_PHRASES[anchor])
    # 光向/能量句式只在「光没有被介质纪律或作者声明接管」时注入（见函数头）。
    if not (photo_light_override or lighting_declared):
        if light in LIGHT_PHRASES:
            segments.append(LIGHT_PHRASES[light])
        if level in ENERGY_PHRASES:
            segments.append(ENERGY_PHRASES[level])
    if function in ASSET_FUNCTION_PHRASES:
        segments.append(ASSET_FUNCTION_PHRASES[function])
    segments.append(safe_area_phrase(area, text_color))

    # --- 4. Universal QC + 类型后缀 + 对比度防护 -------------------------
    if include_qc:
        # The old constant is intentionally kept as a reusable vocabulary, but
        # production uses a compact tail and resolves ratio at the call site.
        segments.extend(PROMPT_QC_COMPACT)
        segments.append(f"{ratio} presentation background")
    segments.extend(ASSET_TYPE_SUFFIX[asset_type])
    # 仅对透明资产（illustration / icon）追加对比度防护
    segments.extend(ASSET_CONTRAST_GUARD.get(asset_type, ()))

    # 无安全区（画心独占版面）时，凡是「把眼睛引向留白锚点 / 留白对齐到文字安全区」
    # 一类句子都是空指令——版面根本不压文字。提示词只留版面真正要用的话。
    if not area:
        segments = [x for x in segments
                    if not any(k in x for k in ("negative space", "negative-space",
                                                "text-safe area"))]
    prompt = separator.join(s_ for s_ in _dedup(segments) if s_)

    # --- 5. 反向提示词（分层组装：核心恒注入，场景层按画面可能有什么注入）---
    negatives = list(NEGATIVE_BASE) + list(UNIVERSAL_CHEAP_REJECTS) \
        + list(_as_list(card.get("negative"))) \
        + list(_as_list(extra_negative))
    if subject_implies_people(card):
        negatives.extend(HUMAN_SCENE_REJECTS)
    if not ink:
        negatives.extend(TECH_STYLE_REJECTS)   # 水墨闸门有自己的反向清单，不叠科技词
    if ink:
        negatives.extend(INK_CHEAP_REJECTS)
    if photo:
        negatives.extend(PHOTO_CHEAP_REJECTS)
    # 统一成 "no X" 写法，避免同一提示词里混用 "text" 与 "no charts"
    negative = ", ".join(
        term if term.lower().startswith("no ") else f"no {term}"
        for term in _dedup(negatives, normalize_negative=True)
    )

    return {
        "prompt": prompt,
        "negative": negative,
        "meta": {
            "apc": card.get("apc"),
            "theme_ref": card.get("theme_ref"),
            "asset_type": asset_type,
            "ratio": ratio,
            "negative_space_anchor": anchor,
            "safe_area": area,
            "text_color": text_color,
            "light_direction": light,
            "energy": level,
            "asset_function": function,
            "medium": medium or None,
            "fusion_enabled": bool(fusion_allowed),
            "issues": validate_asset_card(card),
        },
    }


def asset_fingerprint(card: dict, page: dict | None = None) -> str:
    """Stable visual-demand fingerprint used to deduplicate cross-page assets.

    Content copy is deliberately excluded: two pages can share one visual
    asset when their visual demand is the same.  The page id is never part of
    the key, so reuse is deterministic across deck revisions.
    """
    page = page if isinstance(page, dict) else {}
    keys = ("asset_type", "medium", "family", "subject", "color", "material",
            "lighting", "composition", "motion", "texture", "negative",
            "asset_function", "fusion_enabled", "style", "world")
    payload = {k: card.get(k) for k in keys if card.get(k) is not None}
    payload["negative_space_anchor"] = page.get("negative_space_anchor") or "left"
    payload["safe_area"] = normalize_safe_area(
        page.get("safe_area"), payload["negative_space_anchor"])
    payload["light_direction"] = page.get("light_direction") or "left"
    payload["energy"] = page.get("energy") or "low"
    payload["ratio"] = page.get("ratio") or "16:9"
    payload["text_color"] = page.get("text_color")
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return "asset-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


# --------------------------------------------------------------------------
# 图像轻量体检（出图后）：只找问题、给建议，不打分。
# Issue + Suggestion，绝不输出数值分数（评分是 QA/渲染层的职责，这里只做定性体检）。
# --------------------------------------------------------------------------
QC_BLOCK = 64                      # 局部纹理统计的块边长（px）
QC_FLAT_STD = 0.05                 # 块内标准差低于该值视为「平坦」（留白/均匀区）
QC_TEXTURE_STD = 0.075             # 文字安全区块内标准差高于该值视为「纹理过密」
QC_MIN_NEGATIVE_RATIO = 0.25       # 负空间占比下限
QC_BRIGHT_DARK = 0.12              # 整体过暗阈值
QC_BRIGHT_LIGHT = 0.88             # 整体过亮阈值
QC_BALANCE_GAP = 0.18              # 左右/上下亮度失衡阈值
QC_SUBJECT_MARGIN = 0.02           # 主体贴边判定阈值（主体质量占比达到此比例视为贴边）
QC_TEXT_RANGE = 0.30               # 安全区亮度需落在此范围外才同时支持深浅文字

# QC 是资产局部体检，不是整副 deck 的 QA。默认最多允许一次定向重出；
# review/release 只记录问题并交给人工/qa 处理，不由资产脚本自动升级流程。
ASSET_QC_MAX_RETRIES = 1
ASSET_QC_BLOCKING_CHECKS = frozenset({
    "text_safe_area", "subject_position", "hard_seam",
    "contrast_suitability", "image_dimensions", "aspect_ratio", "visibility",
})
# negative_space_ratio 从阻断降为 advisory：它量的是「平坦块占比」，而假留白面板
# 恰好增加平坦块——指标越漂亮，图越假。判断留给设计智能，QC 只守物理事实（硬缝）。
ASSET_QC_ADVISORY_CHECKS = frozenset({"brightness_balance", "negative_space_ratio"})


def qc_policy() -> dict:
    """asset manifest 的 qc_policy 唯一真源。

    清单里曾另写一份同义字典，于是「报告承诺什么」与「代码执行什么」可以不一致：
    实测 negative_space_ratio 已降级为 advisory，清单仍写 blocking。策略只有一个
    出口：谁改这里，清单和执法一起改。
    """
    return {**{c: "blocking" for c in sorted(ASSET_QC_BLOCKING_CHECKS)},
            **{c: "advisory" for c in sorted(ASSET_QC_ADVISORY_CHECKS)}}
# 「主体贴边被裁」这条判据是为**具象主体**设的：产品、人物、建筑被画框切掉，
# 一眼就是错的。而氛围/语境类资产的画面边界本来就该由材质与光填满——宣纸的
# 撕边、石面的颗粒、雾气的过渡延伸到画外是自然的，不是「被裁断的主体」。
# 实测过：三层手工纸特写与被摄主体的显著性占比都在 0.00–0.07 同一量级，
# 像素层面区分不了「材质延伸」与「具象主体」，所以判据只能取自声明的职能。
ASSET_QC_CONTEXT_FUNCTIONS = frozenset({"emotion", "context", "frame", "separate"})
ASSET_QC_PHASES = frozenset({"draft", "review", "release"})


def qc_retry_decision(qc: dict, *, attempt: int = 0,
                      phase: str = "draft", max_retries: int = ASSET_QC_MAX_RETRIES,
                      asset_function: str | None = None) -> dict:
    """把 image_qc 结果翻译成有界动作，不改变 run_qa 的 review/release 档位。

    ``attempt`` 从 0 开始。draft 只对影响文字安全区/构图可用性的检查自动
    允许一次定向重出；brightness_balance 仅建议。review/release 不自动重出，
    release 的阻断信号仍须由最终 QA/Manifest 消费，而不是由这层伪造通过。
    """
    phase = str(phase or "draft").strip().lower()
    if phase not in ASSET_QC_PHASES:
        raise ValueError(f"unknown asset QC phase {phase!r}; "
                         f"choose one of {', '.join(sorted(ASSET_QC_PHASES))}")
    try:
        attempt = max(0, int(attempt))
    except (TypeError, ValueError):
        attempt = 0
    try:
        requested = max(0, int(max_retries))
    except (TypeError, ValueError):
        requested = ASSET_QC_MAX_RETRIES
    retry_cap = min(requested, ASSET_QC_MAX_RETRIES)
    checks = qc.get("checks") or [] if isinstance(qc, dict) else []
    issues = [c for c in checks if isinstance(c, dict) and c.get("status") == "issue"]
    # 氛围/语境类资产不适用「主体贴边」：它们的画面边界本就由材质与光填满，
    # 边界延伸是自然的，不是被裁断的主体（判据见 ASSET_QC_CONTEXT_FUNCTIONS）。
    # 这一条省掉的是整整一轮「重出一张 → 还是过不了 → 换意象」的往返，
    # 而那个往返曾把设计判断也带偏：为了过检查去改意象，而不是因为意象该改。
    context_asset = str(asset_function or "").strip().lower() in ASSET_QC_CONTEXT_FUNCTIONS
    blocking = [c for c in issues
                if c.get("check") in ASSET_QC_BLOCKING_CHECKS
                and not (context_asset and c.get("check") == "subject_position")]
    advisory = [c for c in issues if c not in blocking]
    missing_file = isinstance(qc, dict) and qc.get("status") == "error"
    if missing_file:
        action = "block"
    elif not blocking:
        action = "accept" if not advisory else "accept_with_advisory"
    elif phase == "draft" and attempt < retry_cap:
        action = "retry"
    elif phase == "release":
        action = "block"
    else:
        action = "flag"
    return {
        "action": action,
        "retry": action == "retry",
        "attempt": attempt,
        "max_retries": retry_cap,
        "phase": phase,
        "blocking_checks": [c.get("check") for c in blocking],
        "advisory_checks": [c.get("check") for c in advisory],
        "manual_required": bool(blocking and action != "retry") or missing_file,
        "triggers_review": False,
        "triggers_release": False,
    }


# 安全区定义：文字通常落在声明锚点的对面/一侧（留白区），按锚点取一块矩形。
def _hard_seam_check(arr, alpha):
    """硬缝 / 假留白面板：满高度列均值阶跃 + 阶跃一侧整带几乎无方差。

    判据必须是物理量（阶跃 + 方差），不是品味：真实光影边界一侧仍有材质纹理
    （实测 1.7–5.3 灰阶标准差），假面板是 0.4–0.6。透明画布（Logo / 插画）上的
    平色是设计本身，不判。返回 (ok, issue, suggestion)。
    """
    import numpy as np          # 懒加载：纯组装路径不引入像素依赖（与 image_qc 同律）
    _STEP_MIN, _FLAT_MAX, _SHARE_MIN = 6.0 / 255.0, 1.2 / 255.0, 0.10
    opaque = bool((alpha >= 250).all()) if alpha is not None else True
    if not opaque or arr.shape[1] <= 2:
        return True, None, None
    step = np.abs(np.diff(arr.mean(axis=0)))
    seam = None
    for i in np.where(step > _STEP_MIN)[0]:
        for band in (arr[:, : i + 1], arr[:, i + 1:]):
            share = band.shape[1] / max(arr.shape[1], 1)
            if share > _SHARE_MIN and float(band.std()) < _FLAT_MAX:
                if seam is None or step[i] > seam[1]:
                    seam = (int(i), float(step[i]), float(band.std()), share)
    if not seam:
        return True, None, None
    return (False,
            f"留白被画成一块平板：x={seam[0]}（{seam[3]:.0%} 画宽）处有 "
            f"{seam[1] * 255:.0f} 灰阶硬边，一侧整带标准差仅 {seam[2] * 255:.1f}",
            "留白应来自光在材质上的衰减，不是一块硬边平色：去掉这块矩形区域，"
            "或改由光向 / 构图承担明暗过渡后重出")


def _balance_check(arr):
    """整体明暗 + 左右/上下失衡（只记录，不阻断）。"""
    mean = float(arr.mean())
    h, w = arr.shape
    if mean < QC_BRIGHT_DARK:
        return False, f"整体过暗（亮度 {mean:.2f}）", "提高整体曝光或提亮主体受光面，保留层次"
    if mean > QC_BRIGHT_LIGHT:
        return False, f"整体过亮（亮度 {mean:.2f}）", "压暗背景或收光圈，让主体与文字有落点"
    lr_gap = abs(float(arr[:, : w // 2].mean()) - float(arr[:, w // 2:].mean()))
    tb_gap = abs(float(arr[: h // 2, :].mean()) - float(arr[h // 2:, :].mean()))
    if lr_gap > QC_BALANCE_GAP or tb_gap > QC_BALANCE_GAP:
        return False, f"画面失衡（左右差 {lr_gap:.2f} / 上下差 {tb_gap:.2f}）", "平衡光源或主体分布，避免一侧明显压黑/过曝"
    return True, None, None


def image_qc(path: str, safe_area: str = "left", text_is_dark: bool | None = None,
             safe_rect: dict | None = None, *, image_bytes: bytes | None = None,
             expected_ratio: str | None = None, allow_crop: bool = False,
             background: str = "#FFFFFF") -> dict:
    """对一张出图结果做定性体检（Issue + Suggestion，不打分）。"""
    from PIL import Image  # 懒加载：纯组装路径不引入像素依赖
    import numpy as np

    import io
    from PIL import ImageColor
    p = Path(path)
    try:
        blob = image_bytes if image_bytes is not None else p.read_bytes()
        with Image.open(io.BytesIO(blob)) as opened:
            rgba = opened.convert("RGBA")
            w, h = rgba.size
            visible = rgba.getchannel("A").getextrema()[1] > 0
            alpha = np.asarray(rgba.getchannel("A"))
            bg = Image.new("RGBA", rgba.size, (*ImageColor.getrgb(background), 255))
            arr = np.asarray(Image.alpha_composite(bg, rgba).convert("L"), dtype=np.float32) / 255.0
    except (OSError, ValueError) as exc:
        return {"file": str(p), "status": "error", "issue": str(exc), "checks": []}
    if min(w, h) < 32:
        return {"file": str(p), "status": "issue", "dimensions": [w, h], "checks": [
            {"check": "image_dimensions", "status": "issue", "issue": "图片短边小于32px",
             "suggestion": "使用足够分辨率的图片；色块请用原生形状"}]}

    # 自适应块：目标 ~QC_BLOCK px/块，但以实际尺寸为准（<64px 的图不再越界）
    bh = max(1, h // QC_BLOCK)          # 行块数
    bw = max(1, w // QC_BLOCK)          # 列块数
    bhs, bws = h // bh, w // bw         # 每块像素高/宽
    crop = arr[: bh * bhs, : bw * bws]
    blk = crop.reshape(bh, bhs, bw, bws)
    blk_mean = blk.mean(axis=(1, 3))    # (bh, bw) 块均值
    blk_std = blk.std(axis=(1, 3))      # (bh, bw) 块内标准差

    checks = []

    def _add(check, ok, issue, suggestion):
        checks.append({"check": check, "status": "ok" if ok else "issue",
                       "issue": None if ok else issue,
                       "suggestion": None if ok else suggestion})

    _add("image_dimensions", True, None, None)
    _add("visibility", visible, "图片完全透明，无可见内容", "更换可见素材；透明Logo允许保留有效alpha")
    if expected_ratio:
        try:
            rw, rh = (float(v) for v in str(expected_ratio).split(":"))
            import math
            valid_ratio = math.isfinite(rw) and math.isfinite(rh) and rw > 0 and rh > 0
            ratio_ok = valid_ratio and abs((w / h) / (rw / rh) - 1) <= 0.05
        except (ValueError, ZeroDivisionError):
            valid_ratio = ratio_ok = False
        _add("aspect_ratio", bool(valid_ratio and (ratio_ok or allow_crop)),
             f"实际尺寸 {w}×{h} 与计划比例 {expected_ratio} 不符",
             "按计划重新出图；有意裁切时在brief声明 asset_allow_crop: true 并重建清单")
    normalized = normalize_safe_area(safe_rect, safe_area)
    if not normalized:
        # 没有文字压图：安全区相关检查不适用（不拿默认矩形硬判），物理检查照跑。
        _add("text_safe_area", True, None, None)
        _add("negative_space_ratio", True, None, None)
        _add("subject_position", True, None, None)
        _add("contrast_suitability", True, None, None)
        _add("hard_seam", *_hard_seam_check(arr, alpha))
        _add("brightness_balance", *_balance_check(arr))
        return {"file": str(p), "status": "ok", "dimensions": [w, h], "checks": checks,
                "safe_area": None, "note": "无文字压图：安全区检查不适用"}
    x0 = normalized["x"]
    y0 = normalized["y"]
    x1 = x0 + normalized["width"]
    y1 = y0 + normalized["height"]
    bh, bw = blk_std.shape
    sx0, sy0, sx1, sy1 = int(x0 * bw), int(y0 * bh), max(int(x1 * bw), 1), max(int(y1 * bh), 1)
    safe_std = blk_std[sy0:sy1, sx0:sx1]

    # 1. 文字安全区：纹理是否过密（会吃掉文字）
    busy = float((safe_std > QC_TEXTURE_STD).mean()) if safe_std.size else 0.0
    _add("text_safe_area", busy < 0.15,
         f"文字安全区（{safe_area}）内 {busy:.0%} 的块纹理过密",
         "主体/细节避开安全区，或局部压暗/压平该区域，保证文字落在均匀底上")

    # 2. 负空间比例：足够放文字、不憋
    flat_ratio = float((blk_std < QC_FLAT_STD).mean())
    _add("negative_space_ratio", flat_ratio >= QC_MIN_NEGATIVE_RATIO,
         f"负空间占比仅 {flat_ratio:.0%}（低于 {QC_MIN_NEGATIVE_RATIO:.0%}）",
         "增加留白：拉远主体、放大背景均匀面，或删减前景元素")

    # 3. 主体位置：主体是否侵入安全区 / 贴边（在块网格对齐的裁切域内计算）
    grid = np.kron(blk_mean, np.ones((bhs, bws), dtype=np.float32))
    sal = np.minimum(np.abs(crop - grid), 1.0)
    subj = sal > 0.20
    subj_ratio = float(subj.mean())
    in_safe = float(subj[sy0 * bhs:sy1 * bhs,
                         sx0 * bws:sx1 * bws].mean()) if subj_ratio else 0.0
    edge = max(float(subj[: bhs, :].mean()),
               float(subj[-bhs:, :].mean()),
               float(subj[:, : bws].mean()),
               float(subj[:, -bws:].mean()))
    if in_safe > 0.10:
        _add("subject_position", False,
             f"主体质量 {in_safe:.0%} 侵入文字安全区（{safe_area}）",
             "主体挪到安全区对面，把留白一侧留给文字")
    elif edge > QC_SUBJECT_MARGIN:
        _add("subject_position", False,
             f"主体 {edge:.0%} 贴边被裁",
             "主体整体入画，四边留出呼吸距离")
    else:
        _add("subject_position", True, None, None)

    # 4. 亮度平衡：整体明暗 + 左右/上下失衡
    _add("brightness_balance", *_balance_check(arr))

    # 5. 对比度适配：安全区能否同时给深浅文字留出对比
    safe_lum = crop[sy0 * bhs:sy1 * bhs, sx0 * bws:sx1 * bws].mean() \
        if safe_std.size else 0.5
    if text_is_dark is not None:
        ok = safe_lum > 0.55 if text_is_dark else safe_lum < 0.45
        _add("contrast_suitability", bool(ok),
             f"安全区亮度 {safe_lum:.2f} 支撑不了{'深' if text_is_dark else '浅'}色文字",
             "调整安全区明度：深色文字需亮底，浅色文字需暗底")
    else:
        _add("contrast_suitability", safe_lum > 1 - QC_TEXT_RANGE or safe_lum < QC_TEXT_RANGE,
             f"安全区亮度 {safe_lum:.2f} 处于中间带，深浅文字对比都不足",
             "把安全区推到亮端（>0.7）或暗端（<0.3），给文字明确落点")

    _add("hard_seam", *_hard_seam_check(arr, alpha))

    issue_count = sum(1 for c in checks if c["status"] == "issue")
    return {"file": str(p), "status": "issue" if issue_count else "ok", "dimensions": [w, h],
            "issue_count": issue_count, "checks": checks}


# --------------------------------------------------------------------------
# CLI：与 compiler.py 一致地读取参数模块
# --------------------------------------------------------------------------
