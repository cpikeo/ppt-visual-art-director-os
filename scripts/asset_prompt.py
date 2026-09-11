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
# OS 强制注入的三段（留白锚点 / 光向 / 能量；见 SKILL.md 媒体治理要求）
# --------------------------------------------------------------------------
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
    "song_elegance": ("natural",), "apple_future": ("tech", "spatial"),
    "data_intelligence": ("tech",),
}
FAMILY_TEXTURE: dict[str, tuple[str, ...]] = {
    "nature_luxury": ("organic", "architecture"), "nordic_quiet": ("architecture",),
    "monochrome_noir": ("architecture",), "zen_minimal": ("eastern",),
    "luxury_editorial": ("luxury", "architecture"), "precision_tech": ("technology",),
    "organic_systems": ("organic",), "cinematic_narrative": ("luxury", "architecture"),
    "editorial_intelligence": ("eastern",), "quiet_luxury": ("luxury",),
    "song_elegance": ("eastern",), "apple_future": ("technology",),
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
    negatives = list(NEGATIVE_BASE) + list(_as_list(card.get("negative"))) \
        + list(_as_list(extra_negative))
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


# ── Asset Intent Cache：缓存提示词智能，不缓存图片 ─────────────
# 出图的慢在图像模型本身；可复用的是「怎么写这条 prompt 的判断」（构图/光性/
# 留白/文字区），不是图片。validated prompt DNA 按 场景×视觉世界×主体 寻址；
# 色值不进 DNA（色彩由主题在版面层决定），构图与光性判断可以进。
PROMPT_DNA_STORE = Path(__file__).resolve().parent.parent / "memory" / "asset_prompt_dna.json"
_PROMPT_STRUCTURE_KEYS = {"composition", "lighting", "void", "anchor",
                          "text_zone", "material", "camera"}


def _prompt_key(scenario: str, visual_world: str = "", subject: str = "") -> str:
    toks = [str(x).strip().lower() for x in (scenario, visual_world, subject)
            if x and str(x).strip()]
    return " × ".join(toks)


def _load_prompt_store() -> dict:
    try:
        return json.loads(PROMPT_DNA_STORE.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "entries": []}


def recall_prompt_dna(scenario: str, visual_world: str = "",
                      subject: str = "") -> dict:
    """场景×视觉世界×主体 → 已验证的出图判断（构图/光性/留白/文字区）。

    返回 {matched, key, entry, note}。无精确命中时做 token 重叠 ≥2 的近邻
    提示（需适配，禁止照抄——主体一换，构图判断就要重估）。
    """
    key = _prompt_key(scenario, visual_world, subject)
    store = _load_prompt_store()
    entries = store.get("entries") or []
    for e in entries:
        if e.get("key") == key:
            return {"matched": e.get("key"), "key": key, "entry": e,
                    "note": "精确命中：构图/光性判断可复用，主体与构图的关系仍要按当前内容重估"}
    want = {t for t in key.split(" × ") if t}
    near = []
    for e in entries:
        have = {t for t in str(e.get("key", "")).split(" × ") if t}
        if len(want & have) >= 2:
            near.append(e)
    if near:
        return {"matched": None, "key": key, "entry": near[0],
                "note": "近邻命中（场景相近主体不同）：只借光性与材质判断，构图按当前主体重估"}
    return {"matched": None, "key": key, "entry": None,
            "note": "无 prompt DNA：按 asset contract 起草，发布 PASS 后 record_prompt_dna 沉淀这条判断"}


def record_prompt_dna(entry: dict) -> dict:
    """沉淀已验证的出图判断。entry = {scenario, visual_world?, subject?,
    prompt_structure: {composition|lighting|void|anchor|text_zone|material|camera ≥2 项},
    avoid?: [...], proven: {project, verdict?}}。拒收色值（色彩归主题，不归 prompt）。"""
    key = _prompt_key(entry.get("scenario", ""), entry.get("visual_world", ""),
                      entry.get("subject", ""))
    if not key:
        return {"ok": False, "reason": "需要 scenario（可附 visual_world / subject）"}
    st = entry.get("prompt_structure")
    if not isinstance(st, dict) or len(set(st) & _PROMPT_STRUCTURE_KEYS) < 2:
        return {"ok": False, "reason":
                "prompt_structure 需 ≥2 项：" + "/".join(sorted(_PROMPT_STRUCTURE_KEYS))}
    import re
    for k, v in st.items():
        if isinstance(v, str) and re.search(r"#[0-9a-fA-F]{3,8}\b", v):
            return {"ok": False, "reason":
                    f"prompt_structure.{k} 含色值：色彩由主题在版面层决定，"
                    "prompt DNA 只存构图/光性/材质判断（光性用语言描述，如 warm tungsten）"}
    if not (entry.get("proven") or {}).get("project"):
        return {"ok": False, "reason": "proven.project 必填——只有真实用过的判断才值得缓存"}
    store = _load_prompt_store()
    entries = [e for e in store.get("entries", []) if e.get("key") != key]
    entries.append({"key": key,
                    "scenario": entry.get("scenario"),
                    "visual_world": entry.get("visual_world"),
                    "subject": entry.get("subject"),
                    "prompt_structure": st,
                    "avoid": entry.get("avoid") or [],
                    "proven": entry.get("proven")})
    entries.sort(key=lambda e: str(e.get("key")))
    store = {"version": 1, "entries": entries}
    PROMPT_DNA_STORE.parent.mkdir(parents=True, exist_ok=True)
    PROMPT_DNA_STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1),
                                encoding="utf-8")
    return {"ok": True, "store": str(PROMPT_DNA_STORE), "entries": len(entries)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="PPT Design OS · 视觉资产提示词组装器")
    parser.add_argument("--recall", metavar="KEY",
                        help="提示词 DNA 召回：'场景|视觉世界|主体'（缓存判断，不缓存图片）")
    parser.add_argument("--record", metavar="ENTRY_JSON",
                        help="沉淀已验证的出图判断（JSON 文件：scenario/prompt_structure/proven）")
    parser.add_argument("card", nargs="?", help="资产卡参数模块（定义 CARD 或 build_card()）")
    parser.add_argument("--page", help="页面版面参数模块（定义 PAGE 或 build_page()）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--ratio", default="16:9", help="出图比例（默认 16:9）")
    parser.add_argument("--no-qc", action="store_true", help="不追加 Universal QC 后缀")
    args = parser.parse_args(argv)

    if args.recall:
        parts = [x.strip() for x in args.recall.split("|") if x.strip()]
        out = recall_prompt_dna(*parts)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    if args.record:
        entry = json.loads(Path(args.record).read_text(encoding="utf-8"))
        print(json.dumps(record_prompt_dna(entry), ensure_ascii=False, indent=2))
        return 0
    if not args.card:
        parser.error("需要 card 模块路径（或使用 --recall / --record）")
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
