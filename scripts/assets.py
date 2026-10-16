# -*- coding: utf-8 -*-
"""assets.py · 资产一体化：判断 → 卡 → 提示词 → 清单 → 像素 QC → 链核验

合并自 asset_prompt（提示词翻译 + 像素 QC）与 asset_workflow（清单与链核验）：
它们是同一条资产链的两半，拆成两个模块只制造 import 往返。

纪律：
  * 提示词组装是确定性翻译：不持有主题、不做设计决策（该不该出图由
    intelligence.media_necessity 判定，本层只翻译与核验）。
  * 链核验只回答：这张图是不是 QC 通过的那张、绑到正确的页、分辨率够。
    没有第二重哈希仪式。
"""
from __future__ import annotations

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
# 默认负向词只排除生产失效，不把某种风格、人物动作或题材判成“廉价”。
# 具体画面禁项由作者 negative / brief.avoid 给出；不从主体关键词扩张禁令。
# --------------------------------------------------------------------------
UNIVERSAL_CHEAP_REJECTS: tuple[str, ...] = (
    "AI artifacts", "unintended borders or letterboxing",
    "unintended flat painted panels", "unintended visible seams",
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
    "shuimo", "水墨", "笔墨", "泼墨", "写意", "oriental ink",
    "chinese ink", "east asian ink",
)
# Rice paper / 宣纸 is a material cue, not a medium declaration. A photograph
# can use it as a surface, so it must not activate painted-ink instructions.
# The old broad token caused photography cards in the SHANZHI case to receive
# contradictory "hand-painted ... no photographic shading" clauses.

INK_DISCIPLINE: tuple[str, ...] = (
    "ink-wash marks and pigment behavior consistent with the declared medium",
    "preserve the depicted forms and the declared composition through controlled brushwork",
)
INK_CHEAP_REJECTS: tuple[str, ...] = (
    "unintended muddy ink pooling", "unmotivated paint splatter",
    "unintended digital airbrush artifacts",
)


def ink_gate_active(card: dict) -> bool:
    """资产卡是否已选择水墨语言（纯检测，供调用方/自检复用）。

    显式 medium 优先；未声明时才看对象/构图/显式材质的介质线索。
    不扫描世界默认材质、纹理、动势或整稿方向，不把纸面摄影误作水墨。
    """
    if not isinstance(card, dict):
        return False
    medium = str(card.get("medium") or "").strip().lower()
    if medium:
        return any(t.lower() in medium for t in INK_TERMS)
    fields = [card.get("subject"), card.get("color"),
              card.get("composition"), card.get("style")]
    for key in ("material", "lighting"):
        if str(card.get(f"{key}_source") or "declared").lower() == "declared":
            fields.append(card.get(key))
    blob = " ".join(str(x) for seg in fields for x in _as_list(seg)).lower()
    return any(t.lower() in blob for t in INK_TERMS)



# --------------------------------------------------------------------------
# 摄影执行只补物理可信性；光照由逐页声明/世界/兜底统一结算。
# 不预设自然光、单光源、浅景深、胶片颗粒或摄影必须充当背景。
# --------------------------------------------------------------------------
_PHOTO_STYLE_EXCLUDE = ("illustration", "3d", "vector", "render", "painting",
                        "clipart", "ink", "sumi")
PHOTO_REALISM_DISCIPLINE: tuple[str, ...] = (
    "physically plausible illumination consistent with the depicted scene",
    "credible photographic geometry, scale and surface response",
    "faithful photographic detail without invented evidence",
)
PHOTO_CHEAP_REJECTS: tuple[str, ...] = (
    "over-sharpening artifacts",
)


def photo_gate_active(card: dict) -> bool:
    """检测摄影介质，不以背景/对象角色代替介质，也不覆盖显式其他介质。"""
    if not isinstance(card, dict):
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

# 插图的空间纪律与背景**不同**：背景要给文字让出整块低信息密度区，
# 插图只需要控制「主体 ↔ 文字」的关系，本身可以中高密度。
SUBJECT_TEXT_RELATION_PHRASES = {
    "left": "subject held toward the right so the left side of the frame stays open for the page's text",
    "right": "subject held toward the left so the right side of the frame stays open for the page's text",
    "top": "subject kept low in the frame so the upper area stays open for the page's text",
    "bottom": "subject kept high in the frame so the lower area stays open for the page's text",
    "center": "subject pulled away from the centre so a calm middle stays open for the page's text",
}

# 对象型插图的结构职责，不替作者选择介质、材质、透明底或画法。
ILLUSTRATION_STRUCTURE: tuple[str, ...] = (
    "single subject readable as an independent visual object",
    "clean separation from what surrounds it, nothing competing for attention",
)

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
        return ("the intended text area stays quiet and visually continuous with its surroundings, "
                "with an even tone suitable for dark type placed later; do not add a separate panel")
    return ("the intended text area stays quiet and visually continuous with its surroundings, "
            "with a dark tone suitable for light type placed later; do not add a separate panel")


LIGHT_PHRASES = {
    "left": "soft directional light from the upper left",
    "right": "soft directional light from the upper right",
    "top": "soft even top light",
    "radial": "soft radial falloff from the center to the edges",
    "none": "flat even ambient light, no visible light source",
}

ENERGY_PHRASES = {
    "low": "subdued lighting intensity and restrained contrast",
    "medium": "moderate lighting intensity and controlled contrast",
    "high": "stronger light contrast supporting the intended visual hierarchy",
}

# 能量调谐：视觉世界给光的**方向与质感**，页面判断只在 low/high 时追加一句
# 强弱。两者正交：能量永远没有改方向的权力。作者逐页写下的光句逐字赢，
# 能量不追加一个字。
ASSET_FUNCTION_PHRASES = {
    "frame": "the image frames the message without competing with it",
    "separate": "the image separates sections while staying quiet",
    "direct": "the image guides the eye toward the main subject",
    "contextualize": "the image establishes context while keeping the foreground readable",
    "immersive": "immersive full-bleed spatial field supporting the declared subject and page hierarchy",
}

# --------------------------------------------------------------------------
# Asset Role Separation（v5.7 · 背景图与插图的职责边界）
#
# 背景图是「承载页面空间」的资产，插图是「表达页面对象」的资产——两者不能用同一套
# 生成纪律。这一层只做一件事：把二者的差别变成可执行语言，不做第三个枚举系统。
#
# 二维模型（两个轴，互不替代）：
#
#                   为什么存在？（asset_function）
#               Hero  Proof  Emotion  Context  Frame  Separate
#   什么类型？   │      │       │        │       │       │
#   Background ──┼──────┼───────┼────────┼───────┼───────┤   空间 / 氛围 / 材质 / 光
#   Illustration ┼──────┼───────┼────────┼───────┼───────┤   对象 / 叙事 / 视觉符号
#   Hybrid ──────┼──────┼───────┼────────┼───────┼───────┤   同一资产确实同时承担两者
#
#   asset_role     = 这张资产**是什么**（背景 / 插图 / 混合）
#   asset_function = 这张资产**为什么存在**（主角 / 证据 / 情绪 / 环境 / 边界 / 独立）
#   asset_subject  = 画面里**具体出现什么**
#
# 禁止把 asset_role 做成更多 asset_function 枚举（background_hero / illustration_context …）
# —— 那会把一个二维判断摊平成组件/模板表，正是本包反对的退化方向。
#
# 两级不可互相偷换：
#   asset_role=background  ≠  asset_function=hero   （背景再漂亮也不是页面主角）
#   asset_role=illustration ≠  必须成为 hero        （插图可以只是 separate）
#
# 流水线位置：`asset_role` 解析结果直接就是**执行类型** `asset_type`——
# 一个语义只允许有一个字段，避免出现「声明了 asset_role 而 asset_type 仍然是
# background」这种写得却没生效的裂缝。
ASSET_ROLES: tuple[str, ...] = ("background", "illustration", "hybrid")
DEFAULT_ASSET_ROLE = "background"
# 解析来源（审计用）：declared 逐页显式声明 · assumed 未声明。
# 只有前者是**作者说过的话**——QC 只承认作者声明的角色；assumed 不得悄悄放宽任何判据。
ROLE_AUTHORITATIVE_SOURCES: tuple[str, ...] = ("declared",)


def resolve_asset_role(declared=None) -> tuple[str, str]:
    """逐页 asset_role → (执行类型 asset_type, 来源 declared|assumed)。

    未声明时**不猜**：角色恒有值（默认 background），但来源记为 `assumed`——
    只有作者写下的才算 declared。
    刻意不接受 asset_function 作为推导输入：角色不许被用途偷换
    （把 hero 当插图的推导会把摄影主体变成透明剪影，那不是判断，是串轴）。

    未知角色值 fail-closed：写了却读不懂，比没写更贵（作者会以为它生效了）。
    """
    role = str(declared or "").strip().lower()
    if role:
        if role not in ASSET_ROLES:
            raise ValueError(
                f"未知 asset_role: {declared!r}（合法值 {'|'.join(ASSET_ROLES)}）："
                "background=承载页面空间 / illustration=表达页面对象 / "
                "hybrid=同一资产确实同时承担两者。注意这与「用途/功能」不是同一轴："
                "判断卡上的 witness（现场证词）通常落成 illustration，主体特写同理；"
                "整页环境落成 background；两者都要才写 hybrid。")
        return role, "declared"
    return DEFAULT_ASSET_ROLE, "assumed"


# 角色纪律：正向的**生成纪律**，只讲职责，不讲风格（风格由 medium / material 决定）。
# 每个角色两句为限——提示词密度也是克制的一部分。
ROLE_DISCIPLINE: dict[str, tuple[str, ...]] = {
    "background": (
        "the frame is a visual environment, not a picture of a thing",
        "space, material and light carry the frame; no single dominant protagonist",
    ),
    "illustration": (
        "one clearly readable subject treated as an independent visual object",
        "internal relationships, scale and placement remain clear at the intended viewing size",
    ),
    "hybrid": (
        "one defined subject set inside a continuous spatial field",
        "subject and surroundings have clearly differentiated visual responsibilities",
    ),
    "icon": (),          # icon 有专属后缀，不叠加场景纪律
}

# 背景资产的空间纪律（背景图默认倾向）：大面积连续视觉场、不以具体物件竞争。
BACKGROUND_DISCIPLINE: tuple[str, ...] = (
    "one continuous tonal and material field with no competing objects",
)

# 资产类型后缀
ASSET_TYPE_SUFFIX = {
    "background": (),  # 比例句（"16:9 presentation background"）由组装第 4 步按实际 ratio 生成
    # hybrid：同一资产确实同时承担「空间 + 对象」。非默认选项——只有真的两者都要时才用。
    "hybrid": (
        "single frame where one defined subject and its surrounding space are inseparable",
        "the subject remains primary while the surrounding field supports the page reading path",
    ),
    "illustration": ILLUSTRATION_STRUCTURE,
    "icon": (
        "one semantically recognizable symbol",
        "coherent visual weight, proportions and level of detail",
        "legible at its intended presentation size",
    ),
}

# 对象可辨认性防护，不要求透明底、粗轮廓或扁平着色。
ASSET_CONTRAST_GUARD = {
    "illustration": (
        "preserve legibility of the subject and its necessary internal detail against the page",
    ),
    "icon": (
        "symbol tone clearly contrasts with the slide background",
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
# 可选执行层：只展开调用方已选的动势/纹理/融合，不把质感叠加当成升级。
# --------------------------------------------------------------------------
MOTION_LAYERS: dict[str, tuple[str, ...]] = {
    "still": ("a single frozen moment, nothing moving in frame",),
    "reveal": ("motion implied only at the edges, the subject held sharp",),
    "spatial": ("gentle lateral movement through the space",),
}
TEXTURE_LAYERS: dict[str, tuple[str, ...]] = {
    "paper": ("handmade paper fiber", "rice paper texture"),
    "ink": ("pigment settling into fiber", "ink diffusion at the edges"),
    "stone": ("honed limestone micro texture", "board-formed concrete pore"),
    "structure": ("cast shadow line across a plane",),
    "metal": ("titanium micro brushing", "precision machining marks"),
    "glass": ("glass reflection with faint refraction",),
    "fiber": ("woven natural fiber", "oat fiber surface"),
    "leaf": ("leaf vein macro structure",),
    "water": ("wet stone sheen",),
    "mist": ("faint mist in the air between planes",),
    "textile": ("woven textile grain", "worn timber surface"),
    "clay": ("matte clay surface",),
    "stage": ("wet black floor reflection",),
    "screen": ("soft light spill on a dark surface",),
}
TEXTURE_DISCIPLINE: tuple[str, ...] = (
    "texture follows the declared medium, subject scale and material",
    "texture must not obscure necessary structure or the intended text area")
FUSION_LAYERS: tuple[str, ...] = (
    "image melts into the layout background, no sticker edges, no hard rectangle",
    "negative space reserved and aligned to the text-safe area",
    "lighting direction consistent with the page light source",
    "depth hierarchy: foreground subject, midground material, background atmosphere",
    "foreground and background separated by gentle defocus")


def _expand_layer(spec, table: dict) -> list[str]:
    """把「层键名 or 自由文本」统一展开成可读语言。

    执行键名查表取句：默认第一句；
    视觉世界传下来的是键名（still/reveal/spatial、paper/stone/metal…），
    brief 里逐页写的是自由文本，两种写法都要能用，且展开只发生在这一处：
    自由文本原样保留——调用方显式写下的句子永远赢。
    """
    out: list[str] = []
    for item in _as_list(spec):
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in table:
            out.append(table[key][0])
        else:
            out.append(text)
    return out


def enhance_asset_card(card: dict, motion: list | tuple | None = None,
                       texture: list | tuple | None = None,
                       fusion: bool | None = None) -> dict:
    """展开已选执行层；不把背景的表面/融合强加给对象素材。

    显式列表（含空列表）逐条保留；无纹理就不附加纹理纪律。
    背景默认可融合，对象/混合职责是否融合由作者决定。
    """
    out = dict(card)
    m_keys = motion if motion is not None else card.get("motion")
    t_keys = texture if texture is not None else card.get("texture")
    out["motion"] = _expand_layer(m_keys, MOTION_LAYERS)
    out["texture"] = _expand_layer(t_keys, TEXTURE_LAYERS)
    if out["texture"]:
        out["texture"] += list(TEXTURE_DISCIPLINE)
    if fusion is None:
        fusion = (card.get("asset_type") or "background") == "background"
    out["fusion"] = (list(_as_list(card["fusion"])) if "fusion" in card
                     else list(FUSION_LAYERS[:2])) if fusion else []
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
    declared_role = str(card.get("asset_role") or "").strip().lower()
    if declared_role and declared_role not in ASSET_ROLES:
        issues.append(f"未知 asset_role: {declared_role}"
                      f"（可选 {'|'.join(ASSET_ROLES)}）：background=承载空间 / "
                      "illustration=表达对象 / hybrid=两者兼有")
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
# 决策期结算（v7.3 · Visual Decision Object）
# --------------------------------------------------------------------------
RESOLVED_LIGHT_SOURCES: tuple[str, ...] = (
    "declared", "world", "fallback", "photo_discipline", "phrase_fallback")


def resolve_asset_card(card: dict, page: dict | None = None) -> dict:
    """一张资产卡的视觉语言，一次判完（纯函数，确定性）。

    只依赖 (card, page.tokens)：同一资产指纹 → 同一 resolved，结果随清单落盘，
    渲染期只翻译、不再调停——矛盾在结构上变得不可能。

    光语来源是一个**封闭枚举**（见 RESOLVED_LIGHT_SOURCES），每个来源只由
    一格条件赋值，互相不可能并存：

      declared          作者逐页显式声明 —— 逐字赢，能量不得触碰；
      world             视觉世界给光 —— 页面能量在 low/high 时追加一句强弱（不叠加同义句）；
      fallback          卡片有光语但既非声明也非方向（保守兜底）—— 冻结原文；
      photo_discipline  无既有光语的摄影卡才补物理可信性，不预设光源样式；
      phrase_fallback   卡片完全无光语时，句式光 + 能量句式一起兜底。

    返回 dict(card, resolved={...})；resolved 亦随资产清单落盘（manifest 是
    唯一视觉决策源）。
    """
    card = dict(card or {})
    page = page if isinstance(page, dict) else {}
    ink = ink_gate_active(card)
    photo = photo_gate_active(card)
    source = str(card.get("lighting_source") or "").strip().lower()
    declared = source == "declared"
    card_lights = [str(s).strip() for s in _as_list(card.get("lighting")) if str(s).strip()]
    energy = str(page.get("energy") or "low").strip().lower()
    light_dir = str(page.get("light_direction") or "left").strip().lower()

    light = {"from": None, "card_lines": [], "photo_lines": [], "ink_lines": [],
             "phrase": None, "energy_phrase": None,
             "energy": energy, "energy_applied": False}
    if ink:
        # 已选介质的执行说明不包含光语，不规定构图或固定留白。
        light["ink_lines"] = list(INK_DISCIPLINE)
    if photo:
        # 介质说明不再接管光照：作者/世界的光均沿同一优先级结算。
        light["photo_lines"] = list(PHOTO_REALISM_DISCIPLINE[1:])
    if declared:
        # 作者写了光照句子：逐字赢，能量不得触碰（不着一字）；
        # 写了来源却没写句子（罕见）：尊重声明的沉默，句式兜底光不许接管。
        light["from"] = "declared"
        light["card_lines"] = card_lights
    elif card_lights:
        light["card_lines"] = card_lights
        if source == "world":
            light["from"] = "world"
            # 世界给光的**方向与质感**，页面能量只在 low/high 时追加一句强弱——
            # 两件事正交，各自说话，不再有「预设键 → 变体句」的查表。
            phrase = ENERGY_PHRASES.get(energy)
            if energy in ("low", "high") and phrase:
                light["card_lines"] = card_lights + [phrase]
                light["energy_applied"] = True   # 页面能量判断真的抵达了像素
        else:
            light["from"] = "fallback"
    elif photo:
        light["from"] = "photo_discipline"
        light["photo_lines"] = list(PHOTO_REALISM_DISCIPLINE)
    else:
        light["from"] = "phrase_fallback"
        light["phrase"] = LIGHT_PHRASES.get(light_dir)
        light["energy_phrase"] = ENERGY_PHRASES.get(energy)

    card["resolved"] = {
        "v": 1,
        "light": light,
        # 动势 / 微浮雕 / 融合在 enhance_asset_card（决策期）已注入完毕，
        # 这里只是快照——渲染期以此为准，不再回头读卡面的原始字段。
        "motion": _as_list(card.get("motion")),
        "texture": _as_list(card.get("texture")),
        "fusion": _as_list(card.get("fusion")),
    }
    return card


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
    """把资产卡与页面参数**翻译**成确定性英文提示词（序列化器，无决策权）。

    视觉语言在决策期已经结算（`card.resolved`，见 resolve_asset_card）：
    本函数只把结论文本按序拼成 prompt/negative，**不再做任何光语互斥调停**。
    legacy 卡片（自检 / out-of-tree 独立调用）没有 resolved 时当场补判——
    用的是同一个结算函数，缺 resolved 不是错误，结论与决策期完全一致。

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

    # 介质闸门：分类（检测），负向分层也要用；它不是决策——决策在 resolved 里。
    ink = ink_gate_active(card)
    photo = photo_gate_active(card)
    # 唯一决策出口（v7.3）。光语来源/能量调谐/句式兜底的互斥结论已在
    # resolve_asset_card 一次性判完并（生产路径上）随清单落盘；这里只读结论。
    resolved = card.get("resolved")
    if not isinstance(resolved, dict) or not isinstance(resolved.get("light"), dict):
        eff = dict(page)
        if light_direction is not None:
            eff["light_direction"] = light_direction
        if energy is not None:
            eff["energy"] = energy
        resolved = resolve_asset_card(card, eff).get("resolved") or {}
    light_decision = resolved.get("light") if isinstance(resolved.get("light"), dict) else {}

    # --- 1. 资产卡主体段 -------------------------------------------------
    segments = []
    for key in CARD_SEGMENTS:
        if key == "lighting":
            # 光语只从结算结论读；作者/世界/兜底各归其位。
            segments.extend(_as_list(light_decision.get("card_lines")))
            continue
        segments.extend(_as_list(card.get(key)))

    # --- 2. 有机层 / 叠加层描述（可选，只作为弱描述进入 prompt） --------
    layers = card.get("layers") or {}
    if isinstance(layers, dict):
        if layers.get("overlay"):
            segments.append(f"overlaid with {layers['overlay']}")
        if layers.get("organic_shapes"):
            segments.append(f"{layers['organic_shapes']} organic shapes")

    # --- 三层：动势 / 微浮雕 / 空间融合（决策期 enhance_asset_card 已注入）---
    # 融合按**角色**定，不按用途定：空间资产要融进版面（消灭贴纸边），
    # 独立视觉对象要保住自己的边界。用途（frame/separate/context）不再决定这件事——
    # 那正是「插图被当成背景纹理」的来源。
    function_hint = str(asset_function or page.get("asset_function")
                         or card.get("asset_function") or "frame").lower()
    fusion_allowed = card.get("fusion_enabled")
    if fusion_allowed is None:
        fusion_allowed = asset_type == "background"
    segments.extend(_as_list(resolved.get("motion")) if isinstance(resolved, dict)
                    else _as_list(card.get("motion")))
    texture = _as_list(resolved.get("texture")) if isinstance(resolved, dict) \
        else _as_list(card.get("texture"))
    # 作者声明的多条纹理逐条保留；默认世界提示的限量在决策期完成。
    segments.extend(texture)
    if fusion_allowed:
        fusion_lines = _as_list(resolved.get("fusion")) if isinstance(resolved, dict) \
            else _as_list(card.get("fusion"))
        segments.extend(fusion_lines)

    # --- 介质纪律句：照决策期结论逐字搬运（水墨工艺 / 摄影写实，无调停）---
    segments.extend(_as_list(light_decision.get("ink_lines")))
    segments.extend(_as_list(light_decision.get("photo_lines")))

    # --- 3. OS 强制三段 --------------------------------------------------
    anchor = str(negative_space or page.get("negative_space_anchor") or "left").lower()
    light = str(light_direction or page.get("light_direction") or "left").lower()
    level = str(energy or page.get("energy") or "low").lower()
    function = str(asset_function or page.get("asset_function") or function_hint).lower()
    area = normalize_safe_area(page.get("safe_area"), anchor)
    text_color = page.get("text_color") or page.get("safe_area_text_color")
    medium = str(card.get("medium") or card.get("render_mode") or "").strip().lower()

    # 角色纪律：背景优先判断 空间 → 光 → 材质 → 负空间；插图优先判断 对象 → 轮廓 →
    # 尺度 → 位置 → 与文字的关系。同一张图只走其中一条链。
    segments.extend(ROLE_DISCIPLINE.get(asset_type, ()))
    if asset_type == "background":
        segments.extend(BACKGROUND_DISCIPLINE)
    if medium:
        segments.append(f"{medium} medium")
    # 留白锚点按角色说不同的话：背景承诺「干净的安静面」，插图只承诺
    # 「主体与文字的关系」——把插图的整块画面压成低密度是错的指令。
    space_phrases = (SUBJECT_TEXT_RELATION_PHRASES if asset_type == "illustration"
                     else NEGATIVE_SPACE_PHRASES)
    if anchor in space_phrases:
        segments.append(space_phrases[anchor])
    # 句式光兜底也是决策期结论（phrase_fallback 来源）：光没有被介质纪律、
    # 作者声明或卡片已有光语接管时，句式光 + 能量句式一起托底（见 resolve_asset_card）。
    if light_decision.get("phrase"):
        segments.append(light_decision["phrase"])
    if light_decision.get("energy_phrase"):
        segments.append(light_decision["energy_phrase"])
    if function in ASSET_FUNCTION_PHRASES:
        segments.append(ASSET_FUNCTION_PHRASES[function])
    segments.append(safe_area_phrase(area, text_color))

    # --- 4. Universal QC + 类型后缀 + 对比度防护 -------------------------
    if include_qc:
        # 质量尾段只描述生成边界；比例句尊重角色，不重选媒介。
        segments.extend(PROMPT_QC_COMPACT)
        label = "image" if asset_type == "hybrid" else asset_type
        segments.append(f"{ratio} presentation {label}")
    segments.extend(ASSET_TYPE_SUFFIX[asset_type])
    segments.extend(ASSET_CONTRAST_GUARD.get(asset_type, ()))

    # 无安全区（画心独占版面）时，凡是「把眼睛引向留白锚点 / 留白对齐到文字安全区 /
    # 把某一侧让给页面文字」一类句子都是空指令——版面根本不压文字。
    # 提示词只留版面真正要用的话。
    if not area:
        segments = [x for x in segments
                    if not any(k in x for k in ("negative space", "negative-space",
                                                "text-safe area", "page's text"))]
    prompt = separator.join(s_ for s_ in _dedup(segments) if s_)

    # --- 5. 反向提示词：生产失效 + 作者禁项 + 所选介质执行失效 ---
    negatives = list(NEGATIVE_BASE) + list(UNIVERSAL_CHEAP_REJECTS) \
        + list(_as_list(card.get("negative"))) \
        + list(_as_list(extra_negative))
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
            # resolved 决策对象不住在 meta（那是镜像）：manifest 条目顶层的
            # entry["resolved"] 是唯一落盘处（R4 审计：同一事实只存一份）。
            "apc": card.get("apc"),
            "theme_ref": card.get("theme_ref"),
            "asset_type": asset_type,
            # 角色与来源一并留痕：审计要能区分「作者说的」与「默认假设的」。
            "asset_role": asset_type,
            "asset_role_source": card.get("asset_role_source"),
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
    # safe_area / text_color 是编排侧校准（成图后的压字区 QC），不是视觉需求本身：
    # 作者校准压字区不应使已出图作废（CASE_004 证据：改 safe_area 触发指纹变化
    # → 资产整体改名 + 绑定返工）。它们仍进入清单，由 QC 对成图复核。
    payload["light_direction"] = page.get("light_direction") or "left"
    payload["energy"] = page.get("energy") or "low"
    payload["ratio"] = page.get("ratio") or "16:9"
    from primitives import identity
    return "asset-" + identity(payload, schema="vao-asset-fingerprint-v2", short=12)


# --------------------------------------------------------------------------
# 图像轻量体检（出图后）：只找问题、给建议，不打分。
# Issue + Suggestion，绝不输出审美分数；设计验收由作者按 SKILL 进行。
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
QC_TONE_MATCH_GAP = 0.18           # 画面与声明底色亮度差小于此值 = 同调（不判过暗/过亮）
# 亮度「断崖」：画面与声明底色差距 ≥0.5 且画面落在极端区（过暗/过亮）。
# 这不是方向，是事故——0.00 亮度的图当不了 #F5F4F1 的纸（v7.2.1 审计实证：
# 一张全黑封面图 accept_with_advisory 出货、深字压黑图对比 ≈1.4:1、零可见信号）。
# 断崖与方向的边界：暗色沉浸方向声明的是**深底色**，深图配深底 |Δ| 天然 <0.5，
# 豁免不需要任何额外标志——落差本身就是判据。
QC_TONE_CATASTROPHE_GAP = 0.50     # 画面与声明底色亮度差 ≥此值 = 断崖（升级阻断）

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


# 快速档工作域上限（长边，单位：像素）。整数箱式 reduce 后仍以 ≈QC_BLOCK 源像素为块，
# 于是判据的物理口径不变，只是不再对 4K 原图逐像素扫。
QC_FAST_MAX_SIDE = 1024

# 单张资产的解码上限（像素）。这不是判据，是资源边界：`fast` 只缩小统计工作域，
# 原图仍要被完整解码一次（安全区纹理与下游编译器都用原生像素）。实测本机 QC 峰值
# 约 23–26MB/百万像素（亮度域 + RGB/RGBA + float32 统计，含解释器基线 ~25MB）：
# 4MP→142MB、9MP→243MB、16MP→417MB；一张 12000×12000（144MP）在 2GB 容器里
# 把整轮 check 打到 OOM 被 SIGKILL——作者拿到的是「进程没了」，不是可修的诊断。
# 线画在 100MP：8K 帧 33MP、5000 万像素相机 50MP、中画幅 100MP 都能过，
# 再大就让作者先降采样。Pillow 自己的炸弹线是 178.9MP，中间那段（89.5–178.9M）
# 只警告不拦。注意这是**策略线**而非机器推导值：内存受限的 runner 需自行调低
# （单源常量，随 `qc_profile` 进 QC 档案，可审计）。
QC_MAX_PIXELS = 100_000_000


def qc_profile(speed: str = "strict") -> dict:
    """QC 像素预算的唯一出口：谁改档位，报告里的 qc_scale 一起改。"""
    fast = str(speed or "").strip().lower() == "fast"
    return {"speed": "fast" if fast else "strict",
            "max_side": QC_FAST_MAX_SIDE if fast else None,
            "max_pixels": QC_MAX_PIXELS,
            "block_px": QC_BLOCK}


def qc_policy() -> dict:
    """asset manifest 的 qc_policy 唯一真源。

    清单里曾另写一份同义字典，于是「报告承诺什么」与「代码执行什么」可以不一致：
    实测 negative_space_ratio 已降级为 advisory，清单仍写 blocking。策略只有一个
    出口：谁改这里，清单和执法一起改。
    亮度断崖（v7.2.1）：brightness_balance 平时是 advisory，但画面与声明底色
    是「断崖级断裂」（|Δ亮度| ≥ QC_TONE_CATASTROPHE_GAP 且画面在极端区）升级为
    blocking——这是物理事故不是方向，清单如实写明。
    """
    policy = {**{c: "blocking" for c in sorted(ASSET_QC_BLOCKING_CHECKS)},
              **{c: "advisory" for c in sorted(ASSET_QC_ADVISORY_CHECKS)}}
    policy["brightness_balance"] = \
        "advisory; blocking: tone_gap>=0.5（画面与声明底色断崖，非方向）"
    return policy
# 「主体贴边被裁」这条判据是为**具象主体**设的：产品、人物、建筑被画框切掉，
# 一眼就是错的。而氛围/语境类资产的画面边界本来就该由材质与光填满——宣纸的
# 撕边、石面的颗粒、雾气的过渡延伸到画外是自然的，不是「被裁断的主体」。
# 实测过：三层手工纸特写与被摄主体的显著性占比都在 0.00–0.07 同一量级，
# 像素层面区分不了「材质延伸」与「具象主体」，所以判据只能取自声明的职能。
ASSET_QC_CONTEXT_FUNCTIONS = frozenset({"emotion", "context", "frame", "separate"})
ASSET_QC_PHASES = frozenset({"draft", "review", "release"})


def qc_retry_decision(qc: dict, *, attempt: int = 0,
                      phase: str = "draft", max_retries: int = ASSET_QC_MAX_RETRIES,
                      asset_function: str | None = None,
                      asset_role: str | None = None) -> dict:
    """把 image_qc 结果翻译成有界动作，不改变 verdict 的 review/release 档位。

    ``attempt`` 从 0 开始。draft 只对影响文字安全区/构图可用性的检查自动
    允许一次定向重出；brightness_balance 仅建议（例外：亮度断崖在条目上
    自带 severity="blocking"，与静态策略表等效消费）。review/release 不自动
    重出，release 的阻断信号仍须由最终 QA/Manifest 消费，而不是由这层伪造通过。

    ``asset_role`` 只传**作者显式声明的**角色（未声明传 None）：QC 的判据跟着
    这张资产的承诺走——背景承诺「可与文字共存」，于是查可读性、连续性与负空间；
    插图承诺「自身作为视觉对象成立」，于是查主体完整性、识别度与位置关系。
    角色不是审美评分，它决定的是**问哪几个问题**。未声明时沿用既有
    asset_function 口径，不因新字段而放宽任何一条。
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
    # 「主体贴边被裁」这条判据为**具象主体**而设：产品、人物、建筑被画框切掉一眼就是错的。
    # 而空间资产的画面边界本来就该由材质与光填满——宣纸撕边、石面颗粒、雾的过渡延伸
    # 到画外是自然的，不是被裁断的主体。
    # 声明的角色优先（背景豁免 / 插图与 hybrid 必须成立）；未声明的沿用既有
    # asset_function 口径（emotion/context/frame/separate 豁免）——新字段不偷偷放宽旧判据。
    declared_role = str(asset_role or "").strip().lower()
    if declared_role in ("illustration", "hybrid"):
        subject_bearing = True
    elif declared_role == "background":
        subject_bearing = False
    else:
        subject_bearing = str(asset_function or "").strip().lower() \
            not in ASSET_QC_CONTEXT_FUNCTIONS
    blocking = [c for c in issues
                if (c.get("check") in ASSET_QC_BLOCKING_CHECKS
                    or c.get("severity") == "blocking")
                and not (not subject_bearing and c.get("check") == "subject_position")]
    # 插图的承诺是「主体与文字建立关系」，不是「整块画面保持低信息密度」：
    # 安全区纹理密度对插图降为 advisory——压字可读性由 contrast_suitability（亮度）
    # 与编排层的保护/遮罩负责。承诺变了，判据跟着变；背景资产的承诺没变，判据不动。
    if declared_role == "illustration":
        blocking = [c for c in blocking if c.get("check") != "text_safe_area"]
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
        "asset_role": declared_role or None,
        "blocking_checks": [c.get("check") for c in blocking],
        "advisory_checks": [c.get("check") for c in advisory],
        "manual_required": bool(blocking and action != "retry") or missing_file,
        # （v7.2.1 审计删除 triggers_review / triggers_release 两个恒 False
        # 字段：全库零消费者——升级流程由 verdict 与 Manifest 承担，这层不信号。）
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


QC_DECODE_HOLD_MAX_PX = 48_000_000     # 已解码底图持有上限（≈144MB RGB）
QC_DECODE_HOLD_MAX_IMAGES = 8


def _decode_hold_room(decoded: dict, px: int) -> bool:
    """还能不能再持有一张已解码底图：确定性上限，不做淘汰（按清单顺序先到先得）。

    超过上限就不再交底图——下游会照旧从字节快照解码。快路径只许更快，
    不许把内存变成新的失败模式。
    """
    if len(decoded) >= QC_DECODE_HOLD_MAX_IMAGES:
        return False
    used = sum(getattr(img, "width", 0) * getattr(img, "height", 0) for img in decoded.values())
    return used + px <= QC_DECODE_HOLD_MAX_PX


def _settle(native, handed: bool) -> None:
    """判据用完释放解码句柄；已交给下游的底图不在此列（所有权转移）。"""
    if not handed and native is not None:
        native.close()


def _native_safe_area_texture(opened, w: int, h: int, normalized: dict) -> float | None:
    """安全区纹理密度（原生分辨率，QC_BLOCK 方块口径与严格档逐字一致）。

    快速档的全局统计在降采样域进行，但「文字压在什么纹理上」这件事必须按原始
    像素量：箱式平均会把细密颗粒抹平，而它正是压字可读性最直接的风险。
    只裁安全区（通常 ≤1/3 画面）→ 代价有界，判据不失真。
    """
    try:
        import numpy as np
        x0, y0 = int(normalized["x"] * w), int(normalized["y"] * h)
        x1 = int((normalized["x"] + normalized["width"]) * w)
        y1 = int((normalized["y"] + normalized["height"]) * h)
        x1, y1 = max(x1, x0 + QC_BLOCK), max(y1, y0 + QC_BLOCK)
        # 先裁后转：只在安全区（≤1/3 画面）上做 L 转换，不复制整幅 4K。
        box = opened.crop((x0, y0, min(x1, w), min(y1, h))).convert("L")
        arr = np.asarray(box, dtype=np.float32) / 255.0
        bh, bw = arr.shape[0] // QC_BLOCK, arr.shape[1] // QC_BLOCK
        if bh < 1 or bw < 1:
            return None
        blocks = arr[: bh * QC_BLOCK, : bw * QC_BLOCK].reshape(
            bh, QC_BLOCK, bw, QC_BLOCK)
        std = blocks.std(axis=(1, 3))
        return float((std > QC_TEXTURE_STD).mean())
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _balance_check(arr, background: str | None = None):
    """整体明暗 + 左右/上下失衡（只记录，不阻断）。

    「过暗 / 过亮」只有相对声明底色才有意义（v6.4.3）：整幅暗色画心放在深墨底上，
    是方向本身而不是缺陷——绝对的亮度下限会把「暗色沉浸」这种方向一律判成问题
    （案源：年终总结稿 4 张夜景背景图亮度 0.09–0.11，全部收到「整体过暗」；
    连作者按方向声明 `text_color` 之后，这条告警仍在反对作者的方向）。
    判据改成**落差**：画面与声明底色的亮度差 ≥ QC_TONE_MATCH_GAP 才报（那是可见的
    分块）；同调画面只判左右/上下失衡。文字可读性不靠这条兜底——它由
    `contrast_suitability`（按声明的文字深浅判定，阻断级）负责，两处不再互相代偿。

    断崖升级（v7.2.1）：声明了底色时，|画面 − 声明底色| ≥ QC_TONE_CATASTROPHE_GAP
    且画面落在极端区，这条从 advisory 升级为 blocking——「暗色沉浸」方向声明的是
    深底色（|Δ| 小，两极对齐，照常不拦），断崖只拦「承诺的纸与交付的图物理断裂」。
    返回 (ok, issue, suggestion, severity)；severity 恒为 None 或 "blocking"。
    """
    mean = float(arr.mean())
    h, w = arr.shape
    bg_lum = None
    if background:
        try:
            from primitives import luminance
            bg_lum = float(luminance(str(background)))
        except Exception:      # noqa: BLE001 —— 脏色值当没声明，退回绝对判据
            bg_lum = None
    tone_matched = bg_lum is not None and abs(mean - bg_lum) < QC_TONE_MATCH_GAP
    if not tone_matched:
        catastrophe = (bg_lum is not None
                       and abs(mean - bg_lum) >= QC_TONE_CATASTROPHE_GAP)
        severity = "blocking" if catastrophe else None
        if mean < QC_BRIGHT_DARK:
            rel = f"（比声明底色 {bg_lum:.2f} {'亮' if mean > bg_lum else '暗'} " \
                  f"{abs(mean - bg_lum):.2f}）" if bg_lum is not None else ""
            note = "；落差 ≥ %.2f，资产与声明纸面物理断裂" % QC_TONE_CATASTROPHE_GAP \
                if catastrophe else ""
            return False, f"整体过暗（亮度 {mean:.2f}{rel}）{note}", \
                ("提高整体曝光或提亮主体受光面，保留层次"
                 + ("；或核对：这张图是否根本不是为本页底色出的" if catastrophe else "")), \
                severity
        if mean > QC_BRIGHT_LIGHT:
            rel = f"（比声明底色 {bg_lum:.2f} 亮 {abs(mean - bg_lum):.2f}）" \
                if bg_lum is not None else ""
            note = "；落差 ≥ %.2f，资产与声明纸面物理断裂" % QC_TONE_CATASTROPHE_GAP \
                if catastrophe else ""
            return False, f"整体过亮（亮度 {mean:.2f}{rel}）{note}", \
                ("压暗背景或收光圈，让主体与文字有落点"
                 + ("；或核对：这张图是否根本不是为本页底色出的" if catastrophe else "")), \
                severity
    lr_gap = abs(float(arr[:, : w // 2].mean()) - float(arr[:, w // 2:].mean()))
    tb_gap = abs(float(arr[: h // 2, :].mean()) - float(arr[h // 2:, :].mean()))
    if lr_gap > QC_BALANCE_GAP or tb_gap > QC_BALANCE_GAP:
        return False, f"画面失衡（左右差 {lr_gap:.2f} / 上下差 {tb_gap:.2f}）", \
            "平衡光源或主体分布，避免一侧明显压黑/过曝", None
    return True, None, None, None


def image_qc(path: str, safe_area: str = "left", text_is_dark: bool | None = None,
             safe_rect: dict | None = None, *, image_bytes: bytes | None = None,
             expected_ratio: str | None = None, allow_crop: bool = False,
             background: str = "#FFFFFF", max_side: int | None = None,
             decoded: dict | None = None, decode_key: str | None = None) -> dict:
    """对一张出图结果做定性体检（Issue + Suggestion，不打分）。

    `max_side`（v5.9 快速档）：像素统计在**整数箱式降采样**后的工作图上进行
    （PIL `reduce(f)`，块均值精确）；尺寸、可见性、比例、返回的 dimensions
    仍取自原图，块边长按 f 同步缩小，所以「每块 ≈64 源像素」这一物理口径不变。
    判据全部是「成块的亮度/纹理/阶跃」，在 4px 级箱平均下依然成立——像素级噪声
    本来就不构成可读性风险，而 4K 图上逐像素扫描是纯浪费。

    严格档（max_side=None）不降采样；报告里的 `qc_scale` 写明这次统计发生在哪个
    像素域，证据不会假装自己量的是原图。
    """
    from PIL import Image  # 懒加载：纯组装路径不引入像素依赖
    import numpy as np

    import io
    from PIL import ImageColor
    p = Path(path)
    try:
        blob = image_bytes if image_bytes is not None else p.read_bytes()
        opened = Image.open(io.BytesIO(blob))
        # 资源边界先于解码：PIL 的 size 只读头部，判完再花内存。
        # 必须排在 EXIF 转置之前——exif_transpose 会真的解码一次。
        declared_w, declared_h = opened.size
        if declared_w * declared_h > QC_MAX_PIXELS:
            opened.close()
            return {"file": str(p), "status": "error", "checks": [],
                    "issue": f"图片 {declared_w}×{declared_h} = "
                             f"{declared_w * declared_h:,} 像素，超过单张解码预算 "
                             f"{QC_MAX_PIXELS:,} 像素（整条流水线共用同一份原生像素）；"
                             "先降采样到预算内再登记，不要靠调大预算换内存"}
        # EXIF Orientation：产物与预览都按「显示方向」落像素（编译器把转置烘焙进
        # PNG，ghost 尊重 EXIF），QC 必须量同一坐标系——否则安全区纹理、主体位置、
        # 上报的 dimensions/ratio 全部基于旋转前的存储方向，门判的是错的像素。
        try:
            orient = opened.getexif().get(0x0112, 1)
        except Exception:
            orient = 1
        if isinstance(orient, int) and 2 <= orient <= 8:
            from PIL import ImageOps
            upright = ImageOps.exif_transpose(opened)
            opened.close()
            opened = upright
        w, h = opened.size
        # 快路径：不透明图直接以 L 通道工作——RGB→RGBA 转换、alpha 通道抽取、
        # alpha_composite 三步在整幅 4K 图上都是纯开销（判据只用亮度与是否可见）。
        transparent = opened.mode in ("RGBA", "LA", "PA", "P") or "transparency" in opened.info
        try:
            opened.load()  # 头部可识别不代表像素完整；解码失败同样属于资产错误
        except BaseException:
            opened.close()
            raise
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        return {"file": str(p), "status": "error", "issue": str(exc), "checks": []}

    # 整幅只解码一次（v5.9）：解码是 4K 源图上最贵的一步，而它被三个消费者需要——
    # 降采样工作域、原生分辨率安全区纹理、以及下游编译器要用的解码底图。
    # 此前会为了「原生分辨率安全区」把同一个 blob 解开第二遍，等于白付一次解码。
    native = opened
    native.fp = None                  # 像素已在内存：流句柄可放（底图可能被下游持有）
    handed = False
    scale = 1
    if max_side and max(w, h) > int(max_side):
        scale = max(1, -(-max(w, h) // int(max_side)))   # ceil 除法 → 整数箱
    native_grey = None
    if transparent:
        rgba = native.convert("RGBA")
        if scale > 1:
            rgba = rgba.reduce(scale)
        visible = rgba.getchannel("A").getextrema()[1] > 0
        ww, wh = rgba.size
        alpha = np.asarray(rgba.getchannel("A"))
        bg = Image.new("RGBA", (ww, wh), (*ImageColor.getrgb(background), 255))
        arr = np.asarray(Image.alpha_composite(bg, rgba).convert("L"),
                         dtype=np.float32) / 255.0
    else:
        visible = True
        native_grey = native.convert("L")
        grey = native_grey
        if scale > 1:
            grey = grey.reduce(scale)
        ww, wh = grey.size
        alpha = None
        arr = np.asarray(grey, dtype=np.float32) / 255.0
        # 交底图：不透明图的 RGB 底图正是编译器 _fit_image_bytes 需要的形态，
        # 交给它就不必在编译期把同一张 4K 图再解一遍（透明图要先合背景，不在此列）。
        if decoded is not None and decode_key:
            room = _decode_hold_room(decoded, w * h)
            if room:
                decoded[decode_key] = native if native.mode == "RGB" else native.convert("RGB")
                handed = True
    if min(w, h) < 32:
        _settle(native, handed)
        return {"file": str(p), "status": "issue", "dimensions": [w, h], "checks": [
            {"check": "image_dimensions", "status": "issue", "issue": "图片短边小于32px",
             "suggestion": "使用足够分辨率的图片；色块请用原生形状"}]}

    # 自适应块：目标 ~QC_BLOCK px/块（在工作域里随 reduce 同步缩小），
    # 但以实际尺寸为准（<64px 的图不再越界）
    block = max(1, QC_BLOCK // max(1, scale))
    bh = max(1, wh // block)            # 行块数
    bw = max(1, ww // block)            # 列块数
    bhs, bws = wh // bh, ww // bw       # 每块像素高/宽
    crop = arr[: bh * bhs, : bw * bws]
    blk = crop.reshape(bh, bhs, bw, bws)
    blk_mean = blk.mean(axis=(1, 3))    # (bh, bw) 块均值
    blk_std = blk.std(axis=(1, 3))      # (bh, bw) 块内标准差

    checks = []

    def _add(check, ok, issue, suggestion, severity=None):
        entry = {"check": check, "status": "ok" if ok else "issue",
                 "issue": None if ok else issue,
                 "suggestion": None if ok else suggestion}
        if severity and not ok:
            entry["severity"] = severity     # 条件级阻断（亮度断崖，v7.2.1）
        checks.append(entry)

    def hard_seam_result():
        """硬缝是宽面拓扑判据：降采样会抹掉真实材质起伏，制造假「平板」。

        复用已解码的 native；仅该阻断判据回看原分辨率，不重新读文件或解码。
        透明画布仍按原规则跳过，完全不透明的带 alpha 图按亮度测量。
        """
        seam_arr, seam_alpha = arr, alpha
        if scale > 1 and native is not None:
            if transparent:
                try:
                    alpha_min, _ = native.convert("RGBA").getchannel("A").getextrema()
                except (OSError, ValueError):
                    alpha_min = 0
                if alpha_min < 250:
                    return True, None, None
            try:
                # 不透明图上游已把原生像素转为 L；只降采样工作图，硬缝仍读
                # 同一张原生灰阶，不为一个判据再次转整幅 4K。
                seam_arr = np.asarray(native_grey if native_grey is not None
                                      else native.convert("L"), dtype=np.float32) / 255.0
                seam_alpha = None
            except (OSError, ValueError, MemoryError):
                # 内存极限时沿用已算出的工作域；不为可选精度让 QC 变成新失败点。
                seam_arr, seam_alpha = arr, alpha
        return _hard_seam_check(seam_arr, seam_alpha)

    _add("image_dimensions", True, None, None)
    _add("visibility", bool(visible), "图片完全透明，无可见内容", "更换可见素材；透明Logo允许保留有效alpha")
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
        _add("hard_seam", *hard_seam_result())
        _add("brightness_balance", *_balance_check(arr, background))
        _settle(native, handed)
        return {"file": str(p), "status": "ok", "dimensions": [w, h], "checks": checks,
                "qc_scale": scale, "qc_domain": [int(ww), int(wh)],
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
    # 文字安全区的纹理判据必须在**原生分辨率**上量：像素级细密纹理在箱式降采样后
    # 会被平均掉，而它恰是压字可读性最直接的杀手。只裁安全区一块（约占画面 1/3），
    # 成本与全图扫描不在一个量级——所以这一条快速档也不省。
    if native is not None:
        native_busy = _native_safe_area_texture(native, w, h, normalized)
        if native_busy is not None:
            busy = native_busy    # 单一口径：两档都在原生分辨率量，杜绝 fast/strict 分歧
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
    _add("brightness_balance", *_balance_check(arr, background))

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

    _add("hard_seam", *hard_seam_result())

    issue_count = sum(1 for c in checks if c["status"] == "issue")
    _settle(native, handed)
    return {"file": str(p), "status": "issue" if issue_count else "ok", "dimensions": [w, h],
            "issue_count": issue_count, "checks": checks,
            "qc_scale": scale, "qc_domain": [int(ww), int(wh)]}


# --------------------------------------------------------------------------
# CLI：与 compiler.py 一致地读取参数模块
# --------------------------------------------------------------------------


# ══════════════════════════════════════════════════════════════════
# 资产链（原 asset_workflow：清单 / 核验，删哈希抄写仪式）
# ══════════════════════════════════════════════════════════════════
from datetime import datetime, timezone
from pathlib import Path as _Path

from primitives import file_digest, json_read_cached, json_write

ACCEPTED = {"accept", "accept_with_advisory"}
ASSET_DECISIONS = {"generate", "existing"}
QC_REPORT_SCHEMA = "vao-asset-qc-v4"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def digest(value) -> str:
    """记录级摘要（唯一实现在 primitives.identity，不带 schema 保持历史兼容）。"""
    from primitives import identity
    return identity(value)


def asset_entries(manifest: dict) -> list:
    entries = [e for e in manifest.get("assets", []) if isinstance(e, dict)
               and e.get("decision") in ASSET_DECISIONS]
    ids = [e.get("asset_id") for e in entries]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("资产清单的主条目必须有唯一 asset_id；reuse_generated 不算主条目")
    return entries


def asset_root(manifest: dict, manifest_path, override=None) -> _Path:
    parent = _Path(manifest_path).expanduser().resolve().parent
    value = override or manifest.get("assets_dir") or manifest.get("output_dir")
    if not value:
        return parent
    root = _Path(value).expanduser()
    return (root.resolve() if override or root.is_absolute() else (parent / root).resolve())


def resolve_asset(entry: dict, manifest: dict, manifest_path, override=None) -> _Path:
    root = asset_root(manifest, manifest_path, override)
    if entry.get("decision") == "existing":
        raw = (entry.get("origin") or {}).get("path")
        if not raw:
            raise ValueError(f"existing 资产缺 origin.path: {entry.get('asset_id')}")
        p = _Path(raw).expanduser()
        return p.resolve() if p.is_absolute() else (
            _Path(manifest_path).expanduser().resolve().parent / p).resolve()
    filename = _Path(str(entry.get("expected_filename") or f"{entry['asset_id']}.png"))
    if filename.is_absolute() or ".." in filename.parts:
        raise ValueError("生成资产文件名必须位于 assets_dir 内，不能使用绝对路径或 ..")
    candidate = root / filename

    def confined(path):
        resolved = path.resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise ValueError("生成资产最终路径逃逸 assets_dir（含符号链接）")
        return resolved
    confined(candidate)
    if candidate.is_file():
        return confined(candidate)
    alternatives = [candidate.with_suffix(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")
                    if candidate.with_suffix(ext).is_file()]
    if len(alternatives) > 1:
        raise ValueError(f"同一 asset_id 有多个候选文件，请明确 expected_filename: {entry['asset_id']}")
    return confined(alternatives[0] if alternatives else candidate)


def image_elements(spec: dict):
    slides = spec.get("slides")
    if not isinstance(slides, list):
        raise ValueError("spec.slides 必须是数组")
    for slide in slides:
        if not isinstance(slide, dict) or not isinstance(slide.get("elements", []), list):
            raise ValueError("每页须为对象，elements 须为数组")
        for e in slide.get("elements", []):
            if not isinstance(e, dict):
                raise ValueError("elements 内每项须为对象")
            if e.get("type") == "image":
                yield str(slide.get("id")), e


def prepare_manifest(manifest: dict, need: dict, bundle: dict, brief_path,
                     plan_path, manifest_path, assets_dir=None) -> dict:
    """assets 落盘前的最后一步：凭证 + 「字节已存在即登记 existing」。

    plan/brief 一致性由 brief 文件凭证覆盖（verify_sources：文件变了就 BLOCK，
    dict 级再比一次是重复劳动；v1 的 need 镜像字段在 v3 里已不存在）。
    """
    if assets_dir:
        manifest["assets_dir"] = str(_Path(assets_dir).expanduser().resolve())
    manifest["schema"] = "vao-assets-v2"
    _plan_wf = bundle.get("workflow") or {} if isinstance(bundle, dict) else {}
    manifest["workflow"] = {
        "schema": "vao-asset-chain-v2", "prepared_at": now(),
        "brief_path": str(_Path(brief_path).expanduser().resolve()),
        # brief 文件同一轮只哈希一次：复用 plan workflow 已算好的值；
        # 直接调用（bundle 无 workflow）时才现算。dict 级 brief 哈希零消费者，已删。
        "brief_file_sha256": (_plan_wf.get("brief_file_sha256")
                              or file_digest(_Path(brief_path).expanduser())),
        "plan_path": str(_Path(plan_path).resolve()) if plan_path else None,
        "prompt_builder": "assets.build_asset_prompt",
    }
    for entry in asset_entries(manifest):
        if entry["decision"] != "generate":
            continue
        path = resolve_asset(entry, manifest, manifest_path)
        if file_digest(path) is None:
            continue            # 尚未出图：保持 generate，等外部工具按清单出图
        entry["decision"] = "existing"
        entry["origin"] = {"kind": "original", "path": str(path),
                           "source": "manifest prepare 时字节已存在，自动登记（规划身份保留）"}
    return manifest


def verify_sources(manifest: dict) -> list:
    """清单自洽性：schema + brief 文件凭证。不重复校验 plan（页绑定由核验直检）。"""
    wf = manifest.get("workflow") or {}
    if manifest.get("schema") != "vao-assets-v2" or wf.get("schema") != "vao-asset-chain-v2":
        return ["缺少 v2 资产链凭证；旧清单须从 brief → plan → assets 重新建立"]
    problems = []
    expected = wf.get("brief_file_sha256")
    if (not isinstance(expected, str) or len(expected) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in expected)):
        problems.append("缺少合法 brief_file_sha256；须从 brief 重新 plan 建立凭证")
    raw_hash = file_digest(wf.get("brief_path"))
    if raw_hash is None:
        problems.append("brief 文件缺失或不可读取；不能确认资产需求来源，须恢复原 brief 或重新 plan")
    elif isinstance(expected, str) and raw_hash != expected.lower():
        problems.append("brief 文件已变更（资产规划时的需求与现在不同）；建议重新 plan → assets")
    return problems


def _inspected_bytes_current(path, inspected: dict) -> bool:
    from primitives import witness, witness_same
    record = inspected.get("witness")
    if not isinstance(record, dict):
        return False
    return witness_same(record, witness(path))


def verify_chain(spec: dict, manifest_path=None, qc_path=None, assets_dir=None,
                 image_bytes: dict | None = None, digests: dict | None = None) -> dict:
    """资产链核验（唯一实现）：每张图 = QC 通过的那张 + 绑到正确的页 + 分辨率够。

    无图稿件直接 SKIPPED——没有第二重计划哈希仪式；有图稿件的保障由
    slide_ids 直绑 + QC 摘要比对给出，任何一项不成立即 BLOCK。
    """
    images = list(image_elements(spec))
    if not images:
        return {"status": "SKIPPED", "issues": [], "reason": "no_image_elements",
                "image_count": 0, "scope": "native_text_shapes_charts_only"}
    report = {"status": "BLOCKED", "image_count": len(images), "issues": [],
              "scope": "local_content_hash_chain_not_generator_attestation"}
    issues = report["issues"]
    if not manifest_path:
        issues.append("含图片的稿件必须传 --assets-manifest；不能用直接 src 绕过资产清单")
        return report
    try:
        path = _Path(manifest_path).expanduser().resolve()
        manifest = json_read_cached(path)
        issues.extend(verify_sources(manifest))
        entries = {e["asset_id"]: e for e in asset_entries(manifest)}
        qpath = _Path(qc_path).expanduser().resolve() if qc_path else path.with_name(path.stem + ".qc.json")
        qc = json_read_cached(qpath)
        manifest_sha = digest(manifest)
        qc_sha = digest(qc)
        report.update(manifest=str(path), manifest_sha256=manifest_sha,
                      qc_report=str(qpath), qc_sha256=qc_sha)
        if qc.get("schema") != QC_REPORT_SCHEMA or qc.get("manifest_sha256") != manifest_sha:
            issues.append("QC 缺少指纹或来自旧资产清单；重新 check 触发核验")
        if qc.get("status") != "PASS" or any(qc.get(k) for k in
                ("blocking_assets", "pending_assets", "retry_assets", "workflow_issues")):
            issues.append("资产 QC 尚未通过；retry / missing / block 均不能进入编排与发布")
        results = {e.get("asset_id"): e for e in qc.get("results", [])}
        report["verified_images"] = []
        for aid, entry in entries.items():
            actual = resolve_asset(entry, manifest, path, assets_dir)
            inspected = results.get(aid, {})
            preloaded = (image_bytes or {}).get(str(actual))
            if preloaded is not None and not _inspected_bytes_current(actual, inspected):
                preloaded = None
            from primitives import digest_bytes
            recorded = (inspected.get("witness") or {}).get("sha256")
            known = (digests or {}).get(str(actual))
            if known is not None and _inspected_bytes_current(actual, inspected) and recorded == known:
                sha = known
                blob = preloaded
            else:
                blob = preloaded if preloaded is not None else (
                    actual.read_bytes() if actual.is_file() else None)
                sha = digest_bytes(blob) if blob is not None else None
                if sha is not None and digests is not None:
                    digests[str(actual)] = sha
            if image_bytes is not None and blob is not None and recorded == sha:
                image_bytes[str(actual)] = blob
            report["verified_images"].append({"asset_id": aid, "source": str(actual), "sha256": sha})
            if not sha or recorded != sha:
                issues.append(f"{aid}: 图片缺失、损坏或在 QC 后被替换；重新 check")
            if (inspected.get("policy") or {}).get("action") not in ACCEPTED:
                # 资产读不出来（损坏 / 截断 / 超过解码预算）时，原因只写在 QC 报告的
                # results[].qc.issue 里，而这里只报「无接受结果」——作者得再开一个
                # 文件才知道到底哪里坏了。把 QoS 的原始判词带上来。
                qc_state = inspected.get("qc") if isinstance(inspected.get("qc"), dict) else {}
                detail = str(qc_state.get("issue") or "").strip()
                if str(qc_state.get("status")) == "error" and detail:
                    issues.append(f"{aid}: 图片不可用（{detail}）")
                else:
                    issues.append(f"{aid}: 无接受该图片的 QC 结果")
            if entry["decision"] == "generate":
                if not entry.get("prompt") or not entry.get("negative"):
                    issues.append(f"{aid}: 缺少生成提示词/负向提示词")
            else:
                origin = entry.get("origin") or {}
                if origin.get("kind") not in {"provided", "licensed", "original", "reuse"} or not origin.get("source"):
                    issues.append(f"{aid}: 既有素材缺少 origin.kind/source 来源声明")
        for sid, e in images:
            aid = e.get("asset_id")
            if aid not in entries:
                issues.append(f"{sid}/{e.get('id')}: 图片未绑定清单中的 asset_id")
                continue
            if sid not in entries[aid].get("slide_ids", []):
                issues.append(f"{sid}/{aid}: 使用页面未列入清单 slide_ids（页面与资产规划不一致）")
                continue
            dimensions = (results.get(aid, {}).get("qc") or {}).get("dimensions")
            if not isinstance(dimensions, list) or len(dimensions) != 2:
                issues.append(f"{sid}/{aid}: QC 缺少实际图片尺寸；重新检查")
            else:
                iw, ih = map(float, dimensions)
                from primitives import image_crop
                crop = image_crop(e.get("crop"))
                iw *= 1 - float(crop[0]) - float(crop[2])
                ih *= 1 - float(crop[1]) - float(crop[3])
                if min(iw, ih) <= 0:
                    issues.append(f"{sid}/{aid}: 裁切后无有效图像")
                else:
                    scale = (min if e.get("fit") == "contain" else max)(
                        float(e["width"]) / iw, float(e["height"]) / ih)
                    if scale > 1.01:
                        issues.append(f"{sid}/{aid}: 有效分辨率低于落位尺寸（放大 {scale:.2f} 倍）；"
                                      "换高分辨率素材或缩小落位")
            if _Path(str(e.get("src", ""))).resolve() != resolve_asset(entries[aid], manifest, path, assets_dir):
                issues.append(f"{sid}/{aid}: 编排图片路径与 QC 资产不一致")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        issues.append(f"资产链记录不可读取或格式不正确: {exc}")
    report["issues"] = list(dict.fromkeys(issues))
    report["status"] = "PASS" if not issues else "BLOCKED"
    if report["status"] == "PASS" and image_bytes is not None:
        report["compilation_input"] = "verified_in_memory_snapshot"
    return report


def blocked_result(spec: dict, workflow: dict) -> dict:
    """资产链阻断时的最小判定（由 verify 收口）：一条根因组，内嵌全部明细。"""
    issues = [str(i) for i in (workflow.get("issues") or []) if str(i).strip()]
    return {"passed": False, "status": "BLOCKED", "failure_codes": ["ASSET_WORKFLOW_FAIL"],
            "blocking_items": len(issues),
            "affected_slides": [],
            "blocking_detail": [{"rule": "asset_chain", "id": None, "level": "error",
                                 "msg": m} for m in issues],
            "fix_plan": {"policy": "本轮一次修完全部问题；出图后复跑同一条 check 命令。",
                         "groups": [{"root_cause": "ASSET_WORKFLOW_FAIL",
                                     "count": len(issues), "ids": [],
                                     "details": [{"id": None, "rule": "asset_chain",
                                                  "msg": m} for m in issues],
                                     "fix": "按明细出图/登记/重跑；图片必须是 QC 通过的那一张。"}]},
            "next_action": "fix: ASSET_WORKFLOW_FAIL",
            "slides": len(spec.get("slides") or []) if isinstance(spec, dict) else 0}


# ══════════════════════════════════════════════════════════════════
# 资产卡与清单规划（原 vao 内嵌段：规划 → 卡 → 批量清单）
# ══════════════════════════════════════════════════════════════════
_NEGATIVE_SPACE_ANCHOR = {"hero": "left", "emotion": "left", "context": "left",
                          "proof": "right", "direct": "right"}


def asset_card(page: dict, brief: dict, deck: dict, asset_id: str) -> tuple:
    """单份页事实（含作者声明）→ (资产卡, 页面几何契约)。

    角色先于用途：asset_role（是什么）→ asset_type，一步到位；
    未声明不猜（默认 background）；色值跟整副 deck 的种子走。
    """
    raw = page.get("declarations") or {}
    derived = deck.get("world") or {}
    asset_role, asset_role_source = resolve_asset_role(raw.get("asset_role"))
    function = str(raw.get("asset_function") or "frame")
    anchor = str(raw.get("negative_space_anchor")
                 or _NEGATIVE_SPACE_ANCHOR.get(function, "left")).lower()
    safe_area = normalize_safe_area(raw.get("safe_area"), anchor)
    title = str(raw.get("title") or page.get("ref") or "visual context")
    subject = raw.get("asset_subject")
    subject_fallback = not subject
    if not subject:
        subject = title[:180]
    direction_family = str(derived.get("name") or "").strip().lower()
    visual_world = str(brief.get("visual_world") or "")
    if visual_world.lower() == "unknown":
        visual_world = ""
    seed = ((deck.get("theme") or {}).get("colors_seed") or {})
    color_cue = list(raw.get("asset_color") or [])
    if not color_cue:
        color_cue = ["neutral tonal range with one restrained accent"]
        if seed.get("accent"):
            accent_hex = str(seed["accent"])
            accent_name = hex_to_color_name(accent_hex)
            color_cue.append(f"accent color {accent_name} ({accent_hex})" if accent_name
                             else f"accent color {accent_hex}")
    background = asset_role == "background"
    card = {
        "apc": f"APC-{str(asset_id).upper().replace('-', '_')}",
        "asset_type": asset_role,
        "asset_role": asset_role,
        "asset_role_source": asset_role_source,
        "medium": raw.get("medium") or brief.get("asset_medium"),
        "family": direction_family,
        "subject": [subject],
        "subject_source": "title_fallback" if subject_fallback else "declared",
        "color": color_cue,
        "material": [str(raw.get("material") or
                         (derived.get("visual_world") if background else None)
                         or "surface and rendering appropriate to the declared subject and medium")],
        "material_source": ("declared" if raw.get("material")
                            else "world" if background and derived.get("visual_world") else "fallback"),
        "lighting": [str(raw.get("lighting") or (derived.get("light") if background else None)
                         or "illumination only as appropriate to the declared medium and subject")],
        "lighting_source": ("declared" if raw.get("lighting")
                            else "world" if background and derived.get("light") else "fallback"),
        "composition": [str(raw.get("asset_composition") or
                             (grammar_phrase(derived.get("composition_grammar")) if background else
                              "preserve the subject's necessary structure and its intended page placement"))],

        "world": [visual_world[:160]] if background and visual_world else [],
        "asset_function": function,
        "fusion_enabled": raw.get("fusion_enabled"),
        "negative": list(raw.get("negative") or []) + list(brief.get("avoid") or []),
    }
    card = enhance_asset_card(
        card, motion=None,
        texture=(raw["texture"] if "texture" in raw else
                 list(derived.get("texture_keys") or [])[:1] if background else []),
        fusion=(card["fusion_enabled"] if card["fusion_enabled"] is not None else background))
    page_contract = {
        "negative_space_anchor": anchor,
        "safe_area": safe_area,
        "text_color": raw.get("text_color") or raw.get("safe_area_text_color"),
        "light_direction": raw.get("light_direction") or "left",
        "energy": raw.get("energy") or "low",
        "asset_function": function,
        "ratio": str(raw.get("asset_ratio") or brief.get("asset_ratio") or "16:9"),
    }
    card = resolve_asset_card(card, page_contract)
    return card, page_contract


def _media_of(page: dict) -> dict:
    """媒体必要性判断住在逐页判断卡里；缺失即 fail loudly（不静默当作出图 0 张）。"""
    page = page if isinstance(page, dict) else {}
    judgment = page.get("judgment") if isinstance(page.get("judgment"), dict) else {}
    media = judgment.get("media")
    if not isinstance(media, dict):
        raise ValueError(f"{page.get('id', '?')}: plan 缺少 media 必要性判断"
                         "（需 vao-plan-v3 的 plan.json：先跑 vao.py plan）")
    return media


def _page_background_color(page: dict, plan_deck: dict) -> str:
    """资产 QC 亮度判据的底色：页级声明的 background 优先于 deck 纸面。

    暗色沉浸页声明深底色时，QC 问的是「图与这一页的落差」，而不是与整副
    浅色纸面的落差——判据跟随作者声明（CASE_004：酒窖暗图曾因浅色纸面被
    误判亮度断崖）。只认 #HEX；其他写法回落纸面，不猜。
    """
    bg = str((page or {}).get("background") or "").strip()
    if bg.startswith("#") and len(bg) in (4, 7):
        return bg
    return (((plan_deck.get("theme") or {}).get("colors_seed")) or {}).get("foundation", "#FFFFFF")


def prompt_cache_key(fingerprint: str, card: dict, page: dict | None = None) -> str:
    """提示词缓存键 = 资产身份 + 提示词输入。

    身份（`asset_fingerprint`）**刻意**不含 safe_area / text_color / ratio——作者校准
    压字区不该让已出图改名（CASE_004）。但 `build_asset_prompt` 恰恰读这些字段：
    用身份键直接查提示词缓存时，作者把压字区从左侧改到右侧、再跑一次 plan，会拿回
    旧提示词，而清单里的 `safe_area` 已经是新值——清单描述与提示词互相矛盾，出图
    仍按旧指令留白。缓存属于实现细节，可以也应该知道「提示词读过什么」。
    """
    from primitives import identity
    page = page if isinstance(page, dict) else {}
    payload = {k: page.get(k) for k in ("negative_space_anchor", "safe_area", "text_color",
                                        "light_direction", "energy", "asset_function",
                                        "ratio")}
    payload["resolved"] = card.get("resolved")
    return f"{fingerprint}|{identity(payload, schema='vao-asset-prompt-input-v1', short=10)}"


def build_manifest(brief: dict, bundle: dict, cache_path=None) -> dict:
    """brief + 判断面 → 去重的批量资产清单（规划身份 = 指纹）。"""
    pages = bundle.get("pages") or []
    plan_deck = bundle.get("deck") or {}
    hint = bundle.get("assets_hint") or {}
    generation_ids = set(hint.get("generate") or [])
    prompt_cache: dict = {}
    cache_file = _Path(cache_path).expanduser() if cache_path else None
    if cache_file:
        try:
            loaded = json.loads(cache_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("schema") == "vao-asset-prompt-cache-v3":
                entries = loaded.get("entries")
                prompt_cache = entries if isinstance(entries, dict) else {}
        except (OSError, ValueError, TypeError):
            prompt_cache = {}
    cache_hits = 0
    cap = len(generation_ids)  # 作者声明的出图数；图像不设自动额度
    assets: list = []
    by_fingerprint: dict = {}
    by_existing: dict = {}
    generated_count = 0
    skipped_pages: list = []
    for page in pages:
        sid = str(page.get("id"))
        decision = str(_media_of(page).get("decision") or "none")
        raw = page.get("declarations") or {}
        origin = raw.get("asset_source")
        if origin:
            if not isinstance(origin, dict) or origin.get("kind") not in {
                    "provided", "licensed", "original", "reuse"} \
                    or not origin.get("path") or not origin.get("source"):
                raise ValueError("asset_source 需要 kind(provided/licensed/original/reuse)、path、source")
            origin = dict(origin)
            op = _Path(origin["path"]).expanduser()
            base = _Path((bundle.get("workflow") or {}).get("brief_path") or ".").resolve().parent
            origin["path"] = str(op.resolve() if op.is_absolute() else (base / op).resolve())
            entry = {"slide_ids": [sid], "decision": "existing",
                           "origin": origin,
                           "asset_function": raw.get("asset_function", "context"),
                           "asset_role": str(raw.get("asset_role") or "").strip().lower() or None,
                           "asset_role_source": ("declared" if raw.get("asset_role") else None),
                           "safe_area": normalize_safe_area(
                               raw.get("safe_area"), raw.get("negative_space_anchor", "left")),
                           "meta": {"text_color": raw.get("text_color")},
                           "retry_budget": 0,
                           "background_color": _page_background_color(raw, plan_deck)}
            # 同素材/同 QC 契约只测一次；不同压字区/底色不能被错误合并。
            aid = "existing-" + digest({k: v for k, v in entry.items() if k != "slide_ids"})[:16]
            if aid in by_existing:
                by_existing[aid]["slide_ids"].append(sid)
            else:
                entry["asset_id"] = aid
                by_existing[aid] = entry
                assets.append(entry)
            continue
        if decision == "none":
            skipped_pages.append({"slide_id": sid, "decision": "skip",
                                  "reason": _media_of(page).get("necessity", "")})
            continue
        provisional = f"asset-{sid}"
        card, page_contract = asset_card(page, brief, plan_deck, provisional)
        fingerprint = asset_fingerprint(card, page_contract)
        existing = by_fingerprint.get(fingerprint)
        if existing:
            # 视觉身份刻意不含 QC 声明（校准安全区不应让已出图改名），
            # 但不能因此把另一页的压字区/底色/角色静默丢掉。
            # 不新增生成身份或多份出图任务；异契约交作者登记 existing 后分别核验。
            same_qc = (
                existing.get("safe_area") == page_contract["safe_area"]
                and (existing.get("meta") or {}).get("text_color") == page_contract["text_color"]
                and existing.get("background_color") == _page_background_color(raw, plan_deck)
                and existing.get("allow_crop") == (raw.get("asset_allow_crop") is True)
                and existing.get("asset_role") == card["asset_role"]
                and existing.get("asset_role_source") == card["asset_role_source"])
            if not same_qc:
                raise ValueError(f"{sid}: 同一生成资产的跨页 QC 契约不同，不能合并；"
                                 "请先备图，再用逐页 asset_source 登记同一文件以分别核验")
            existing["slide_ids"].append(sid)
            assets.append({"slide_id": sid, "decision": "reuse_generated",
                           "asset_id": existing["asset_id"], "fingerprint": fingerprint})
            continue
        if sid not in generation_ids:
            skipped_pages.append({"slide_id": sid, "decision": "reuse",
                                  "reason": "未声明出图：词表提示不自动出图（需 asset: required）",
                                  "fingerprint": fingerprint})
            continue
        asset_id = f"asset-{fingerprint.removeprefix('asset-')}"
        # 键覆盖提示词的**全部输入**（见 prompt_cache_key）：只按身份查会复用过期提示词。
        cache_key = prompt_cache_key(fingerprint, card, page_contract)
        cached = prompt_cache.get(cache_key)
        if isinstance(cached, dict) and cached.get("prompt") and cached.get("negative"):
            result = cached
            cache_hits += 1
        else:
            result = build_asset_prompt(
                card, page_contract,
                ratio=str(raw.get("asset_ratio") or brief.get("asset_ratio") or "16:9"),
                asset_function=page_contract["asset_function"])
            prompt_cache[cache_key] = result
        entry = {
            "asset_id": asset_id,
            "slide_ids": [sid],
            "decision": "generate",
            "fingerprint": fingerprint,
            "asset_type": card["asset_type"],
            "asset_role": card["asset_role"],
            "asset_role_source": card["asset_role_source"],
            "asset_function": page_contract["asset_function"],
            "ratio": page_contract["ratio"],
            "resolved": card.get("resolved"),
            "allow_crop": raw.get("asset_allow_crop") is True,
            "background_color": _page_background_color(raw, plan_deck),
            "safe_area": page_contract["safe_area"],
            "prompt": result["prompt"],
            "negative": result["negative"],
            "meta": result["meta"],
            "expected_filename": f"{asset_id}.png",
            "retry_budget": 1,
            "qc_policy": qc_policy(),
        }
        by_fingerprint[fingerprint] = entry
        assets.append(entry)
        generated_count += 1
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        json_write(cache_file, {"schema": "vao-asset-prompt-cache-v3", "entries": prompt_cache})
    return {
        "schema": "vao-assets-v1",
        "visual_world": (plan_deck.get("world") or {}).get("name"),
        "quality_level": str(plan_deck.get("quality") or "fast"),
        "cap": cap,
        "assets": assets,
        "skipped_pages": skipped_pages,
        "deduplicated": max(0, len(generation_ids) - generated_count),
        "prompt_cache": {"hits": cache_hits,
                         "path": str(cache_file) if cache_file else None},
    }


# ══════════════════════════════════════════════════════════════════
# 资产 QC 报告（一次判定、一条修法；判定复用是真性能）
# ══════════════════════════════════════════════════════════════════
def qc_report(manifest_path, input_dir=None, *, phase="draft", speed="strict",
              snapshots=None, decoded=None, digests=None, persist=True):
    """资产核验：绑定 → 测量/复用 → 判定。draft 最多一次定向重出。"""
    from primitives import digest_bytes, engine_fingerprint, text_is_dark, witness_same
    manifest_file = _Path(manifest_path).expanduser().resolve()
    manifest = json_read_cached(manifest_file)
    profile = qc_profile(speed)
    qc_phase = "draft" if str(phase).strip().lower() not in {"draft", "review", "release"} \
        else str(phase).strip().lower()
    # 上一轮判定复用前提：同清单 + 同像素预算 + 同判定实现。
    prev_report: dict = {}
    reuse_base = None
    prev_results: dict = {}
    prev_path = manifest_file.with_name(manifest_file.stem + ".qc.json")
    try:
        if prev_path.exists():
            prev_report = json_read_cached(prev_path)
    except (OSError, ValueError, TypeError):
        prev_report = {}
    if prev_report:
        if (prev_report.get("manifest_sha256") == digest(manifest)
                and prev_report.get("pixel_profile") == profile
                and prev_report.get("qc_engine") == engine_fingerprint("measure")):
            reuse_base = "sha256"
            prev_results = {str(r.get("asset_id")): r for r in (prev_report.get("results") or [])}
    reused_assets = 0
    workflow_issues = verify_sources(manifest)
    results = []
    actions: dict = {}
    pending: list = []
    # 每轮按源路径读取/哈希一次，即使像素测量命中也交接真实快照。
    # stat 相同并不证明字节相同；fast 只降低像素统计预算，不降低资产身份保证。
    source_blobs: dict = {}
    source_hashes: dict = {}
    entries = asset_entries(manifest)
    if persist:
        from primitives import validate_io_paths
        validate_io_paths({"assets manifest": manifest_file,
                           "brief": (manifest.get("workflow") or {}).get("brief_path"),
                           **{f"asset {e['asset_id']}": resolve_asset(e, manifest, manifest_file, input_dir)
                              for e in entries}}, {"asset QC": prev_path})
    for entry in entries:
        candidate = resolve_asset(entry, manifest, manifest_file, input_dir)
        try:
            stat = candidate.stat()
            size, mtime_ns = stat.st_size, stat.st_mtime_ns
        except OSError:
            size, mtime_ns = None, None
        key = str(candidate)
        if key not in source_blobs:
            blob = candidate.read_bytes() if candidate.is_file() else None
            source_blobs[key] = blob
            source_hashes[key] = digest_bytes(blob) if blob is not None else None
        blob = source_blobs[key]
        image_sha = source_hashes[key]
        if entry["decision"] == "generate" and (not entry.get("prompt") or not entry.get("negative")):
            workflow_issues.append(f"{entry['asset_id']}: 缺少 prompt / negative")
        if entry["decision"] == "existing":
            origin = entry.get("origin") or {}
            if origin.get("kind") not in {"provided", "licensed", "original", "reuse"} \
                    or not origin.get("source"):
                workflow_issues.append(f"{entry['asset_id']}: 既有素材缺少合法 kind / source 声明")
        safe = entry.get("safe_area") or {}
        text_color = ((entry.get("meta") or {}).get("text_color")
                      or (entry.get("page") or {}).get("text_color"))
        qc_inputs = {"safe_rect": safe, "text_color": text_color,
                     "ratio": entry.get("ratio"),
                     "allow_crop": entry.get("allow_crop") is True,
                     "background": entry.get("background_color") or "#FFFFFF",
                     "max_side": profile["max_side"]}
        previous = (prev_results or {}).get(str(entry.get("asset_id")))
        reused_qc = None
        if previous and reuse_base is not None:
            same_bytes = witness_same(
                previous.get("witness") or {},
                {"size": size, "mtime_ns": mtime_ns, "sha256": image_sha},
                strict=True)
            if same_bytes and previous.get("qc_inputs") == qc_inputs:
                reused_qc = dict(previous.get("qc") or {})
        if blob is not None and snapshots is not None:
            snapshots[str(candidate)] = blob
        if image_sha is not None and digests is not None:
            digests[str(candidate)] = image_sha
        if reused_qc is not None:
            qc = reused_qc
            qc["reused"] = True
            qc["reused_from"] = previous.get("checked_at")
            reused_assets += 1
        else:
            qc = image_qc(str(candidate), safe_rect=safe,
                          text_is_dark=text_is_dark(text_color),
                          image_bytes=blob, expected_ratio=entry.get("ratio"),
                          allow_crop=entry.get("allow_crop") is True,
                          background=entry.get("background_color") or "#FFFFFF",
                          max_side=profile["max_side"],
                          decoded=decoded, decode_key=str(candidate))
        role_authority = (entry.get("asset_role")
                          if entry.get("asset_role_source") in ROLE_AUTHORITATIVE_SOURCES
                          else None)
        decision = qc_retry_decision(qc, attempt=int(entry.get("attempt", 0) or 0),
                                     phase=qc_phase, max_retries=entry.get("retry_budget", 1),
                                     asset_function=entry.get("asset_function"),
                                     asset_role=role_authority)
        missing = (qc.get("status") == "error")
        results.append({"asset_id": entry.get("asset_id"),
                        "slide_ids": entry.get("slide_ids") or [],
                        "file": str(candidate),
                        "qc_inputs": qc_inputs, "checked_at": now(),
                        "witness": {"size": size, "mtime_ns": mtime_ns, "sha256": image_sha},
                        "qc": qc, "policy": decision, "missing": missing})
        actions.setdefault(decision["action"], []).append(str(entry.get("asset_id")))
        if missing:
            pending.append(str(entry.get("asset_id")))
    report = {
        "schema": QC_REPORT_SCHEMA,
        "manifest": str(manifest_file),
        "qc_engine": engine_fingerprint("measure"),
        "manifest_sha256": digest(manifest), "checked_at": now(),
        "workflow_issues": workflow_issues,
        "status": "PASS" if not workflow_issues and all(
            (r.get("policy") or {}).get("action") in ACCEPTED for r in results) else "BLOCKED",
        "phase": qc_phase,
        "pixel_profile": profile,
        "reuse": ({"assets": reused_assets, "witness": reuse_base} if reused_assets else None),
        "results": results,
        "summary": {k: len(v) for k, v in actions.items()},
        "retry_assets": actions.get("retry", []),
        "blocking_assets": [a for a in actions.get("block", []) + actions.get("flag", [])
                            if a not in pending],
        "pending_assets": pending,
        "conversation_policy": "only blocking assets become one grouped repair/retry action",
    }
    out_path = prev_path
    report["report_path"] = str(out_path)
    phase_changed = bool(prev_report) and prev_report.get("phase") != qc_phase
    state_changed = (prev_report.get("status") != report["status"]
                     or prev_report.get("workflow_issues") != workflow_issues)
    if persist and (phase_changed or state_changed or not (prev_report and reuse_base is not None and results
                                         and reused_assets == len(results))):
        json_write(out_path, report)
    return report, 0 if report["status"] == "PASS" else 2
