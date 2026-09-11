#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Intent Compression Layer（意图压缩层）：需求 → Design Brief。

流程里的位置：用户需求 → 本层 → Design Brief（~500 tokens）→ 生成。
Brief 之后所有步骤只消费 Brief + Page Intent，不再回读原始需求——
后面每个 Agent 省掉的不是几行字，是「重新理解一遍需求」的整段推理。

确定性：同输入必得同 Brief（关键词查表 + route.plan_deck 复用家族路由，
零猜测、零随机）。本模块 import 零成本（只在函数内懒加载 route）。
"""
from __future__ import annotations

import hashlib
import json
import re


def _token_hit(text: str, token: str) -> bool:
    """词命中判定（F7/v4.17——词边界修复）。

    纯 ASCII 词走词边界匹配（容忍 s/es 复数尾巴），防止短词嵌在无关
    英文单词里误命中——frozen/citizen/dozen 内含 "zen"、history 内含
    "story"、onboard 内含 "board"，字串包含会把一份冻资复盘覆写成
    宣纸水墨世界。CJK 词无空格分词边界，保持子串匹配。
    """
    tok = str(token).strip().lower()
    if not tok:
        return False
    if all(ord(c) < 128 for c in tok):
        return re.search(
            rf"(?<![a-z0-9_]){re.escape(tok)}(?:e?s)?(?![a-z0-9_])",
            text) is not None
    return tok in text

# 场合 → 情绪与视觉世界（起点判断，不是模板；显式 tone_hint 永远赢）
OCCASION_WORLDS = {
    "board": {
        "match": ("董事会", "汇报", "战略", "决策", "年度总结", "年终", "board",
                  "review", "汇报"),
        "tone": "calm_authority",
        "visual_world": "quiet editorial evidence room: paper, soft daylight, one signal",
        "composition_grammar": "evidence_field", "type_voice": "neutral_sans",
        "color_behavior": "single_signal", "media_role": "none",
        "background_scene": "solid_world", "motion_posture": "still",
        "avoid": ["dashboard feeling", "cyberpunk glow", "decorative stock"],
    },
    "launch": {
        "match": ("发布", "launch", "keynote", "产品发布", "新品", "stage"),
        "tone": "constructive_urgency",
        "visual_world": "product stage: single object, controlled light, deep quiet",
        "composition_grammar": "cinematic_stage", "type_voice": "product_display",
        "color_behavior": "dark_luminous", "media_role": "hero",
        "background_scene": "cinematic", "motion_posture": "reveal",
        "avoid": ["data density", "card walls", "multi-focus pages"],
    },
    "story": {
        "match": ("品牌", "故事", "人文", "文化", "理念", "brand", "story",
                  "manifesto", "纪录", "杂志"),
        "tone": "human_trust",
        "visual_world": "documentary warmth: real light, material truth, breathing space",
        "composition_grammar": "soft_asymmetry", "type_voice": "humanist_sans",
        "color_behavior": "warm_material", "media_role": "emotion",
        "background_scene": "atmospheric", "motion_posture": "still",
        "avoid": ["tech gradients", "icon piles", "high-contrast blocks"],
    },
    "technical": {
        "match": ("数据", "技术", "架构", "分析", "复盘", "指标", "data", "tech",
                  "architecture", "metrics", "funnel"),
        "tone": "technical_clarity",
        "visual_world": "graphite evidence field: structure, baseline, direct labels",
        "composition_grammar": "strict_grid", "type_voice": "neutral_sans",
        "color_behavior": "quiet_neutral", "media_role": "none",
        "background_scene": "solid_world", "motion_posture": "still",
        "avoid": ["3d charts", "decorative gradients", "hidden uncertainty"],
    },
}
DEFAULT_WORLD = "board"

# 审美风格覆写层（v4.16 F5——订阅命名通道）：东方/电影/静奢等审美词命中后
# 在 occasion world 之上覆写美学字段。occasion 决定「这是什么场合」（语义），
# style 决定「想要什么气质」（美学）；显式 visual_world/audience 永远赢。
# 不是新生成机制——只是把已有 family 叙事（song_elegance/cinematic_narrative/
# quiet_luxury 已在 design_intelligence_rules）接入意图端订阅关键词。
STYLE_OVERLAYS = {
    "eastern_ink": {
        "match": ("东方", "水墨", "留白", "禅", "宋韵", "新中式", "卷轴", "宣纸",
                  "泼墨", "印章", "禅意", "泼墨山水", "eastern", "zen", "sumi",
                  "ink wash", "east asian"),
        "family_hint": "song_elegance",
        "visual_world": "sumi-e editorial: rice-paper ground, ink mountain ridge, "
                        "vast negative space, one vermilion accent",
        "composition_grammar": "soft_asymmetry",
        "type_voice": "serif_editorial",
        "color_behavior": "ink_restraint",
        "background_scene": "rice_paper_world",
        "avoid": ["cyberpunk glow", "tech gradient", "dashboard feeling",
                  "decorative stock", "neon", "card walls"],
    },
    "cinematic": {
        "match": ("电影感", "电影", "镜头感", "沉浸式", "胶片", "letterbox",
                  "cinematic", "film", "movie", "immersive"),
        "family_hint": "cinematic_narrative",
        "visual_world": "cinematic narrative: letterbox rhythm, deep quiet field, "
                        "controlled warm light, film grain",
        "composition_grammar": "cinematic_stage",
        "background_scene": "cinematic",
        "avoid": ["dashboard feeling", "card walls", "flat pastel"],
    },
    "quiet_luxury": {
        "match": ("静奢", "quiet luxury", "quiet_luxury", "素雅", "素净",
                  "雅叙", "老钱", "editorial luxury"),
        "family_hint": "quiet_luxury",
        "visual_world": "quiet luxury: wool and bone palette, generous margins, "
                        "understated material truth",
        "avoid": ["dashboard feeling", "accent spam", "logo wallpaper"],
    },
}


def _pick_world(need: dict) -> dict:
    text = " ".join(str(need.get(k) or "") for k in
                   ("occasion", "subject", "audience", "decision",
                    "tone_hint")).lower()
    for key, world in OCCASION_WORLDS.items():
        if any(_token_hit(text, m) for m in world["match"]):
            return {"world_key": key, **world}
    world = OCCASION_WORLDS[DEFAULT_WORLD]
    return {"world_key": DEFAULT_WORLD, **world}


def _apply_style_overlay(world: dict, need: dict) -> dict:
    """在 occasion world 之上应用审美覆写层（确定性查表，显式视觉声明永远赢）。"""
    text = " ".join(str(need.get(k) or "") for k in
                   ("occasion", "subject", "audience", "decision",
                    "tone_hint", "design_direction")).lower()
    for key, so in STYLE_OVERLAYS.items():
        if any(_token_hit(text, m) for m in so["match"]):
            w = dict(world)
            w["style_key"] = key
            for f in ("visual_world", "composition_grammar", "type_voice",
                      "color_behavior", "background_scene"):
                if f in so:
                    w[f] = so[f]
            w["avoid"] = sorted(set(world.get("avoid") or []) | set(so.get("avoid") or []))
            w["family_hint"] = so.get("family_hint")
            return w
    return dict(world)


def estimate_tokens(obj) -> int:
    """Brief 体积的启发式估计（CJK ≈1.6 / 字符，ASCII ≈0.35 / 字符）。"""
    text = obj if isinstance(obj, str) else json.dumps(
        obj, ensure_ascii=False, sort_keys=True, default=str)
    total = 0.0
    for ch in text:
        total += 1.6 if "\u4e00" <= ch <= "\u9fff" else 0.35
    return int(round(total))


def compile_brief(need: dict | str) -> dict:
    """需求 → Design Brief（确定性；显式字段永远赢过推断）。

    need 可为 dict（audience/decision/occasion/subject/slides/
    constraints/tone_hint/visual_world/brand_colors）或一段自然语言。
    返回 {design_intent, strategy_seed, direction_seed, slides_seed,
    token_estimate, source_hash}。
    """
    if isinstance(need, str):
        need = {"subject": need}
    need = dict(need or {})
    world = _apply_style_overlay(_pick_world(need), need)
    tone = str(need.get("tone_hint") or world["tone"])
    visual_world = str(need.get("visual_world") or world["visual_world"])

    # 家族/密度/能量复用 route 真源（本层不维护第二套路由表）
    from route import plan_deck
    plan = plan_deck({"audience": need.get("audience", ""),
                      "decision": need.get("decision", ""),
                      "occasion": need.get("occasion", ""),
                      "design_direction": need.get("design_direction", ""),
                      "quality_level": need.get("quality_level", ""),
                      "slides": need.get("slides") or []})
    slides_seed = [{"id": p.get("id") or p.get("content_type"),
                    "family": p.get("page_family") or p.get("family"),
                    "density": p.get("density"), "energy": p.get("energy"),
                    "empty_space_role": p.get("empty_space_role")}
                   for p in plan.get("pages", [])]

    brief = {
        "design_intent": {
            "goal": str(need.get("decision") or need.get("subject") or ""),
            "audience": str(need.get("audience") or "unknown"),
            "tone": tone,
            "visual_world": visual_world,
            "layout": f"{world['composition_grammar']} / {world['type_voice']} / "
                      f"{world['color_behavior']}",
            "energy_curve": "sparse-opening → dense-evidence → sparse-closing",
            "media_policy": world["media_role"],
            "avoid": list(world["avoid"]),
        },
        "strategy_seed": {
            "audience": str(need.get("audience") or "unknown"),
            "decision": str(need.get("decision") or "unknown"),
            "tension": str(need.get("tension") or "unknown"),
            "narrative_arc": ["establish", "explain", "prove", "recommend",
                              "close"],
            "emotional_target": tone,
            "evidence_posture": str(need.get("evidence_posture") or "fact_led"),
        },
        "direction_seed": {
            "visual_world": visual_world,
            "composition_grammar": world["composition_grammar"],
            "type_voice": world["type_voice"],
            "color_behavior": world["color_behavior"],
            "media_role": world["media_role"],
            "background_scene": world["background_scene"],
            "motion_posture": world["motion_posture"],
            **({"family_hint": world["family_hint"], "style_key": world["style_key"],
                "avoid": world["avoid"]} if world.get("style_key") else {}),
        },
        "slides_seed": slides_seed,
        "route": {"path": plan.get("path"),
                  "execution": (plan.get("execution") or {}).get("mode")},
    }
    brief["token_estimate"] = estimate_tokens(brief)
    brief["source_hash"] = hashlib.sha256(
        json.dumps(need, ensure_ascii=False, sort_keys=True,
                   default=str).encode()).hexdigest()[:12]
    return brief


def _load_need(path: str) -> dict:
    from pathlib import Path
    p = Path(path)
    if p.suffix in (".yml", ".yaml"):
        import yaml
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if p.suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("need_mod", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "BRIEF"):
        return dict(mod.BRIEF)
    if hasattr(mod, "NEED"):
        return dict(mod.NEED)
    raise ValueError("需求需为 yml / json 或定义 BRIEF / NEED 的模块")


def main(argv=None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1 if not argv else 0
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if argv[0] == "--demo":
        need = {"occasion": "2026 年度总结", "audience": "董事会",
                "decision": "批准关停亏损产品线",
                "slides": ["封面：年度总结",
                           {"id": "s02", "type": "data", "title": "增长结构"},
                           {"id": "s03", "type": "closing", "title": "下一步"}]}
    elif argv[0] == "--text":
        need = {"subject": " ".join(argv[1:])}
    else:
        need = _load_need(argv[0])
    brief = compile_brief(need)
    print(json.dumps(brief, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
