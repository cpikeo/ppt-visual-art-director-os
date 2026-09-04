# -*- coding: utf-8 -*-
"""
asset_prompt.py · 视觉资产提示词组装器（纯函数层）

职责：把「资产卡（card）」+「页面版面参数（page）」拼接成**确定性**的英文提示词。

设计约束（与 PPT Design OS 架构一致）：
  * **不持有任何主题**：本文件不含任何 VP 人格、色板或资产卡数据。
    资产卡由调用方按 `references/visual-asset-engine.md` §3 读取后传入。
  * **不写死设计参数**：留白锚点、光向、能量全部由调用方传入；缺省时才用保守默认。
  * **不做设计决策**：只拼接与去重，不替调用方挑选资产卡或判断该不该出图。
  * 与 `compiler.py` 一样支持「参数模块 + CLI」两种调用方式。

组装顺序（见 visual-asset-engine.md §6.2）：
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
# 通用质量控制后缀（visual-asset-engine.md §2.2，英文原样，模型侧不翻译）
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
# OS 强制注入的三段（visual-asset-engine.md §2.3）
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

# 资产类型后缀（visual-asset-engine.md §5）
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

# 透明资产对比度防护（visual-asset-engine.md §1.3 #3）：
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="PPT Design OS · 视觉资产提示词组装器")
    parser.add_argument("card", help="资产卡参数模块（定义 CARD 或 build_card()）")
    parser.add_argument("--page", help="页面版面参数模块（定义 PAGE 或 build_page()）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--ratio", default="16:9", help="出图比例（默认 16:9）")
    parser.add_argument("--no-qc", action="store_true", help="不追加 Universal QC 后缀")
    args = parser.parse_args(argv)

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
