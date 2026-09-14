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

import argparse
import importlib.util
import json
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# 通用质量控制后缀（英文原样，模型侧不翻译）
# --------------------------------------------------------------------------
UNIVERSAL_QC: tuple[str, ...] = (
    "premium presentation design",
    "luxury editorial aesthetic",
    "minimal but sophisticated",
    "high-end visual identity",
    "professional keynote background",
    "cinematic lighting",
    "balanced negative space",
    "subtle depth",
    "clean composition",
    "no text",
    "no logo",
    "no watermark",
    "no letters",
    "no numbers",
    "no UI elements",
    "no clutter",
    "16:9 presentation background",
)

# 基础反向约束（与 UNIVERSAL_QC 的 no-* 项对应，供支持独立 negative 的模型使用）
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
# --------------------------------------------------------------------------
UNIVERSAL_CHEAP_REJECTS: tuple[str, ...] = (
    "generic stock photo", "cliché corporate imagery", "corporate handshake",
    "posed smiling people", "thumbs up",          # Stock Photo Feeling / 人物摆拍
    "clip art", "clipart illustration",           # Excessive Icons → 剪贴画感
    "neon glow", "cyberpunk",                     # Neon Cyberpunk（D06 禁项）
    "humanoid robot", "robot mascot",             # 机器人元素（D06 禁项）
    "glassmorphism", "frosted glass panels",      # Glassmorphism
    "tech blue gradient", "rainbow gradient",     # Excessive Gradients / 科技蓝渐变
    "plastic skin", "oversaturated colors",       # Cheap AI Aesthetic
    "heavy HDR", "AI artifacts",
)

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


INK_FAMILIES: tuple[str, ...] = ("song_elegance",)


def ink_gate_active(card: dict) -> bool:
    """资产卡是否已选择水墨语言（纯检测，供调用方/自检复用）。

    检测只扫调用方亲手写的图像语言段（subject/color/material/lighting/
    composition/style），**不扫** enhance_asset_card 自动注入的
    motion/texture 弱描述——微浮雕里一句 rice paper 是材质底味，
    不等于选择了水墨画；家族维度只订阅叙事即水墨的家族名（song_elegance）。
    zen_minimal 是「东方禅意极简」，不是水墨画家族，不自动点火。
    """
    if not isinstance(card, dict):
        return False
    fam = str(card.get("family") or card.get("direction_family") or "").lower()
    if fam in INK_FAMILIES:
        return True
    fields = [card.get(k) for k in ("subject", "color", "material",
                                    "lighting", "composition", "style")]
    blob = " ".join(str(x) for seg in fields for x in _as_list(seg)).lower()
    return any(t.lower() in blob for t in INK_TERMS)



# --------------------------------------------------------------------------
# 摄影写实纪律闸门（v4.21——摄影语言的执行质量保底，与水墨闸门同源同理）
# 资产卡语言为摄影（background 型、非水墨、非插画/3D/矢量）时注入少量正向
# 写实纪律：光有方向与衰减、空间有空气与真实尺度、质感有胶片性格。
# 闸门不做审美决策——拍还是画是调用方的事；它只压「选了摄影感却滑向
# 塑料商业图」的默认分布。廉价症状的反向清单住在 UNIVERSAL_CHEAP_REJECTS
# （heavy HDR / plastic skin / oversaturated / generic stock photo 已有案源），
# 这里只补过度锐化与均匀布光两条新案源（TerraForma 校准）。
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
    blob = " ".join(str(card.get(k) or "") for k in
                    ("style", "subject", "material")).lower()
    return not any(w in blob for w in _PHOTO_STYLE_EXCLUDE)


NEGATIVE_SPACE_PHRASES = {
    "left": "large clean negative space on the left side",
    "right": "large clean negative space on the right side",
    "top": "quiet empty area in the upper part",
    "bottom": "quiet empty area in the lower part",
    "center": "quiet calm center area, activity pushed to the edges",
}

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
}

# 资产类型后缀
ASSET_TYPE_SUFFIX = {
    "background": (),  # UNIVERSAL_QC 已含 "16:9 presentation background"
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
CARD_SEGMENTS = ("subject", "color", "material", "lighting", "composition",
                 "motion", "style")
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
FUSION_LAYERS: tuple[str, ...] = (
    "negative space reserved and aligned to the text-safe area",
    "lighting direction consistent with the page light source",
    "depth hierarchy: foreground subject, midground material, background atmosphere",
    "image melts into the layout background, no sticker edges, no hard rectangle",
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


def enhance_asset_card(card: dict, family: str | None = None,
                       motion: list | tuple | None = None,
                       texture: list | tuple | None = None,
                       fusion: bool = True) -> dict:
    """纯函数：为资产卡注入动势/微浮雕/融合三层（确定性、去重、限量）。

    motion ≤3 句、texture ≤2 句（+纪律 2 句）、fusion ≤4 句——
    提示词密度也是克制的一部分；调用方显式传入时永远赢。
    """
    out = dict(card)
    fam = family or str(card.get("family") or card.get("direction_family") or "")
    m_keys = FAMILY_MOTION.get(fam, ("spatial",))
    t_keys = FAMILY_TEXTURE.get(fam, ("luxury",))
    if motion is None:
        pool: list[str] = []
        for k in m_keys:
            pool.extend(MOTION_LAYERS.get(k, ()))
        motion = pool[:3]
    if texture is None:
        pool = []
        for k in t_keys:
            pool.extend(TEXTURE_LAYERS.get(k, ()))
        texture = pool[:2]
    out["motion"] = list(motion)
    out["texture"] = list(texture) + list(TEXTURE_DISCIPLINE)
    if fusion:
        out["fusion"] = list(card.get("fusion") or FUSION_LAYERS[:4])
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

    # --- 1. 资产卡主体段 -------------------------------------------------
    segments = []
    for key in CARD_SEGMENTS:
        segments.extend(_as_list(card.get(key)))

    # --- 2. 有机层 / 叠加层描述（可选，只作为弱描述进入 prompt） --------
    layers = card.get("layers") or {}
    if isinstance(layers, dict):
        if layers.get("overlay"):
            segments.append(f"overlaid with {layers['overlay']}")
        if layers.get("organic_shapes"):
            segments.append(f"{layers['organic_shapes']} organic shapes")

    # --- 三层：动势 / 微浮雕 / 空间融合（enhance_asset_card 注入）---
    for key in ("motion", "texture", "fusion"):
        segments.extend(_as_list(card.get(key)))

    # --- 水墨纪律闸门：已选水墨语言 → 注入工艺纪律 + 廉价症状反向清单 ---
    if ink_gate_active(card):
        segments.extend(INK_DISCIPLINE)
    if photo_gate_active(card):
        segments.extend(PHOTO_REALISM_DISCIPLINE)

    # --- 3. OS 强制三段 --------------------------------------------------
    anchor = negative_space or page.get("negative_space_anchor") or "left"
    light = light_direction or page.get("light_direction") or "left"
    level = (energy or page.get("energy") or "low").lower()
    function = asset_function or page.get("asset_function") or "frame"

    if anchor in NEGATIVE_SPACE_PHRASES:
        segments.append(NEGATIVE_SPACE_PHRASES[anchor])
    if light in LIGHT_PHRASES:
        segments.append(LIGHT_PHRASES[light])
    if level in ENERGY_PHRASES:
        segments.append(ENERGY_PHRASES[level])
    if function in ASSET_FUNCTION_PHRASES:
        segments.append(ASSET_FUNCTION_PHRASES[function])

    # --- 4. Universal QC + 类型后缀 + 对比度防护 -------------------------
    if include_qc:
        segments.extend(UNIVERSAL_QC)
    segments.extend(ASSET_TYPE_SUFFIX[asset_type])
    # 仅对透明资产（illustration / icon）追加对比度防护
    segments.extend(ASSET_CONTRAST_GUARD.get(asset_type, ()))

    prompt = separator.join(_dedup(segments))

    # --- 5. 反向提示词 ----------------------------------------------------
    negatives = list(NEGATIVE_BASE) + list(UNIVERSAL_CHEAP_REJECTS) \
        + list(_as_list(card.get("negative"))) \
        + list(_as_list(extra_negative))
    if ink_gate_active(card):
        negatives.extend(INK_CHEAP_REJECTS)
    if photo_gate_active(card):
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
            "light_direction": light,
            "energy": level,
            "asset_function": function,
            "issues": validate_asset_card(card),
        },
    }


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

# 安全区定义：文字通常落在声明锚点的对面/一侧（留白区），按锚点取一块矩形。
_SAFE_ZONES = {
    "left":   (0.00, 0.00, 0.45, 0.55),
    "right":  (0.55, 0.00, 1.00, 0.55),
    "top":    (0.00, 0.00, 1.00, 0.40),
    "bottom": (0.00, 0.60, 1.00, 1.00),
}


def image_qc(path: str, safe_area: str = "left", text_is_dark: bool | None = None) -> dict:
    """对一张出图结果做定性体检（Issue + Suggestion，不打分）。"""
    from PIL import Image  # 懒加载：纯组装路径不引入像素依赖
    import numpy as np

    p = Path(path)
    if not p.exists():
        return {"file": str(p), "status": "error",
                "issue": f"找不到图片: {p}",
                "suggestion": "确认路径后再跑", "checks": []}

    arr = np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0
    h, w = arr.shape

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

    x0, y0, x1, y1 = _SAFE_ZONES.get(safe_area, _SAFE_ZONES["left"])
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
    mean = float(arr.mean())
    too_dark = mean < QC_BRIGHT_DARK
    too_light = mean > QC_BRIGHT_LIGHT
    half_w = w // 2
    half_h = h // 2
    lr_gap = abs(float(arr[:, :half_w].mean()) - float(arr[:, half_w:].mean()))
    tb_gap = abs(float(arr[:half_h, :].mean()) - float(arr[half_h:, :].mean()))
    if too_dark:
        _add("brightness_balance", False, f"整体过暗（亮度 {mean:.2f}）",
             "提高整体曝光或提亮主体受光面，保留层次")
    elif too_light:
        _add("brightness_balance", False, f"整体过亮（亮度 {mean:.2f}）",
             "压暗背景或收光圈，让主体与文字有落点")
    elif lr_gap > QC_BALANCE_GAP or tb_gap > QC_BALANCE_GAP:
        _add("brightness_balance", False,
             f"画面失衡（左右差 {lr_gap:.2f} / 上下差 {tb_gap:.2f}）",
             "平衡光源或主体分布，避免一侧明显压黑/过曝")
    else:
        _add("brightness_balance", True, None, None)

    # 5. 对比度适配：安全区能否同时给深浅文字留出对比
    safe_lum = crop[sy0 * bhs:sy1 * bhs, sx0 * bws:sx1 * bws].mean() \
        if safe_std.size else 0.5
    if text_is_dark is not None:
        ok = safe_lum > 0.55 if text_is_dark else safe_lum < 0.45
        _add("contrast_suitability", bool(ok),
             f"安全区亮度 {safe_lum:.2f} 支撑不了{'深' if text_is_dark else '浅'}色文字",
             "调整安全区明度：深色文字需亮底，浅色文字需暗底")
    else:
        _add("contrast_suitability", safe_lum > QC_TEXT_RANGE or safe_lum < 1 - QC_TEXT_RANGE,
             f"安全区亮度 {safe_lum:.2f} 处于中间带，深浅文字对比都不足",
             "把安全区推到亮端（>0.7）或暗端（<0.3），给文字明确落点")

    issue_count = sum(1 for c in checks if c["status"] == "issue")
    return {"file": str(p), "status": "issue" if issue_count else "ok",
            "issue_count": issue_count, "checks": checks}


# --------------------------------------------------------------------------
# CLI：与 compiler.py 一致地读取参数模块
# --------------------------------------------------------------------------
def _load_card(module_path: str) -> dict:
    """从 .py 参数模块读取 CARD（或 build_card()）。"""
    path = Path(module_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"找不到参数模块: {path}")
    spec = importlib.util.spec_from_file_location("asset_card_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "build_card"):
        return module.build_card()
    if hasattr(module, "CARD"):
        return module.CARD
    raise AttributeError("参数模块需定义 CARD = {...} 或 build_card() -> dict")


def _load_page(module_path: str | None) -> dict:
    if not module_path:
        return {}
    path = Path(module_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"找不到页面参数模块: {path}")
    spec = importlib.util.spec_from_file_location("asset_page_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "build_page"):
        return module.build_page()
    if hasattr(module, "PAGE"):
        return module.PAGE
    raise AttributeError("页面参数模块需定义 PAGE = {...} 或 build_page() -> dict")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="PPT Design OS · 视觉资产提示词组装器")
    parser.add_argument("card", nargs="?", help="资产卡参数模块（定义 CARD 或 build_card()）")
    parser.add_argument("--page", help="页面版面参数模块（定义 PAGE 或 build_page()）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--ratio", default="16:9", help="出图比例（默认 16:9）")
    parser.add_argument("--no-qc", action="store_true", help="不追加 Universal QC 后缀")
    parser.add_argument("--qc", metavar="IMAGE", help="出图后体检：对图片做 Issue+Suggestion 定性检查（不打分）")
    parser.add_argument("--safe-area", default="left",
                        choices=list(_SAFE_ZONES), help="文字安全区锚点（默认 left）")
    parser.add_argument("--text", choices=["dark", "light"],
                        help="安全区预期文字颜色（dark=深色文字需亮底 / light=浅色文字需暗底）")
    args = parser.parse_args(argv)

    if args.qc:
        text_dark = {"dark": True, "light": False}.get(args.text)
        out = image_qc(args.qc, safe_area=args.safe_area, text_is_dark=text_dark)
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0
        print(f"image-qc: {out['file']} → {out['status']}"
              + (f"（{out['issue_count']} 项待改）" if out.get("issue_count") else ""))
        for c in out["checks"]:
            if c["status"] == "issue":
                print(f"  [x] {c['check']}: {c['issue']}")
                print(f"      → {c['suggestion']}")
            else:
                print(f"  [ok] {c['check']}")
        return 0 if out["status"] == "ok" else 1

    if not args.card:
        parser.error("需要 card 模块路径")
    try:
        card = _load_card(args.card)
        page = _load_page(args.page)
    except (FileNotFoundError, AttributeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2

    out = build_asset_prompt(card, page, ratio=args.ratio,
                             include_qc=not args.no_qc)

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    print("===== PROMPT =====")
    print(out["prompt"])
    print("\n===== NEGATIVE =====")
    print(out["negative"])
    issues = out["meta"]["issues"]
    print("\n===== CHECK =====")
    print("OK" if not issues else "ISSUES: " + "; ".join(issues))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
