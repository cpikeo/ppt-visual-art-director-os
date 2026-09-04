#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structured, read-only art criticism for PPT specs.

This module is intentionally heuristic: it does not pretend that aesthetic
judgment is reducible to a pixel score. It turns observable structure,
page-intent contracts, and optional render evidence into traceable critique.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

DIMENSIONS = (
    "visual_hierarchy", "balance", "alignment", "contrast",
    "rhythm", "consistency", "emotional_impact", "memorability",
    "professional_quality",
)
WEIGHTS = {
    "visual_hierarchy": 20, "balance": 15, "alignment": 10,
    "contrast": 10, "rhythm": 10, "consistency": 10,
    "emotional_impact": 10, "memorability": 10, "professional_quality": 5,
}


def _elements(slide: dict) -> list[dict]:
    return [e for e in slide.get("elements", []) if isinstance(e, dict)]


def spec_direction_token(slide: dict) -> str | None:
    return (slide.get("direction") or {}).get("continuity_token")


def _score_page(slide: dict, index: int, previous: dict | None,
                render_page: dict | None) -> tuple[dict, list[str], list[str]]:
    intent = slide.get("page_intent") or {}
    elems = _elements(slide)
    observations: list[str] = []
    fixes: list[str] = []
    scores = {d: 4 for d in DIMENSIONS}

    focus = intent.get("focus") or intent.get("focus_subject_id")
    if not focus:
        scores["visual_hierarchy"] -= 2
        observations.append("页面未声明唯一主焦点，无法验证第一注意点。")
        fixes.append("补写 focus，并删除或降级竞争性对象。")
    text = [e for e in elems if e.get("type") == "text"]
    charts = [e for e in elems if e.get("type") in {"chart", "native_chart"}]
    images = [e for e in elems if e.get("type") == "image"]
    rounded = [e for e in elems if e.get("type") == "shape" and e.get("shape") in {"rounded_rect", "round_rect"}]
    if len(rounded) > 4:
        scores["visual_hierarchy"] -= 1
        scores["professional_quality"] -= 1
        observations.append(f"检测到 {len(rounded)} 个圆角容器，存在卡片墙或网页 UI 化风险。")
        fixes.append("将容器改为空间分组、发丝线或字体层级；仅保留数据/KPI/特殊强调所需面板。")
    if len(charts) + len(images) > 2:
        scores["visual_hierarchy"] -= 1
        scores["professional_quality"] -= 1
        observations.append("媒体/图表对象超过两个，存在竞争性视觉信号。")
        fixes.append("保留承担核心叙事的一个媒体或图表，其余改为注释、拆页或删除。")
    if len(text) > 8:
        scores["visual_hierarchy"] -= 1
        scores["professional_quality"] -= 1
        observations.append("文本对象较多，页面可能依赖碎片化阅读。")
        fixes.append("合并重复语句，确保一个文本框只承担一个语义角色。")
    if intent.get("insight") is None:
        scores["professional_quality"] -= 2
        observations.append("缺少 page_intent.insight，视觉批评没有可验证的结论基准。")
        fixes.append("先写一条完整可复述的 insight，再调整版式。")
    if render_page:
        drift = float(render_page.get("gravity_drift", 0) or 0)
        if drift > 0.28:
            scores["balance"] -= 2
            observations.append(f"渲染显著性质心漂移 {drift:.2f}，与声明重心不一致。")
            fixes.append("调整主视觉尺寸/位置或重新声明 gravity_anchor；不要用装饰补偿。")
        if float(render_page.get("accent_pixel_ratio", 0) or 0) > 0.08:
            scores["contrast"] -= 1
            scores["professional_quality"] -= 1
            observations.append("渲染强调色像素比例偏高，信号可能失去稀缺性。")
            fixes.append("把 Accent 收束到一个关键数字、节点或下划线。")
    if previous:
        prev_density = (previous.get("page_intent") or {}).get("density")
        density = intent.get("density")
        if density and density == prev_density:
            scores["rhythm"] -= 1
            observations.append("与上一页密度相同，跨页节奏可能趋平。")
            fixes.append("在不破坏叙事的前提下降低或提高空间密度，形成呼吸变化。")
    continuity = intent.get("continuity_token") or (spec_direction_token(slide))
    if not continuity and not images and not charts and len(text) <= 1:
        scores["memorability"] -= 1
        observations.append("页面缺少可识别的视觉记忆锚点，可能只剩通用文字版式。")
        fixes.append("为本页选择一个可复现的记忆动作：尺度、裁切、线性符号、独特留白或数据标注方式。")
    if len(rounded) >= 3 and len(rounded) >= max(3, len(elems) // 2):
        scores["balance"] -= 1
        observations.append("页面主要结构由等质容器组成，可能缺少编辑式空间节奏。")
        fixes.append("打破均匀模块排列，建立一个主重心、一个次级关系和明确留白。")
    if not observations:
        observations.append("页面结构与声明意图基本一致，继续以渲染缩略图验证记忆点。")
    scores = {k: max(0, min(5, v)) for k, v in scores.items()}
    return scores, observations, fixes


def critique_deck(spec: dict, render_evidence: dict | None = None,
                  evidence_cards: list[dict] | None = None) -> dict:
    """Return a read-only structured critique; never mutates spec."""
    slides = spec.get("slides") or []
    render_pages = (render_evidence or {}).get("pages") or []
    reports = []
    total_weighted = 0.0
    hard_gates: list[dict] = []
    for i, slide in enumerate(slides):
        rp = render_pages[i] if i < len(render_pages) else None
        scores, observations, fixes = _score_page(slide, i, slides[i - 1] if i else None, rp)
        weighted = sum(scores[d] / 5 * WEIGHTS[d] for d in DIMENSIONS)
        total_weighted += weighted
        if scores["visual_hierarchy"] < 3 or scores["professional_quality"] < 3:
            hard_gates.append({"code": "CRITIC_LOW", "slide": slide.get("id", i + 1)})
        reports.append({"slide": slide.get("id", i + 1), "scores": scores,
                        "score": round(weighted, 1), "observations": observations,
                        "minimal_fixes": fixes,
                        "recheck": ["Guard", "Compile", "Render Evidence", "QA"]})
    count = max(1, len(slides))
    deck_score = round(total_weighted / count, 1)
    if not (render_evidence or {}).get("rendered", False):
        status = "PREVIEW_ONLY" if not hard_gates else "REVISE"
        hard_gates.append({"code": "RENDER_UNAVAILABLE", "slide": None})
    elif hard_gates:
        status = "REVISE"
    else:
        status = "PASS" if deck_score >= 90 else "REVISE"
    return {
        "critic_version": "1.0",
        "deck_score": deck_score,
        "status": status,
        "hard_gates": hard_gates,
        "evidence_cards_used": [c.get("reference_id") for c in (evidence_cards or []) if c.get("reference_id")],
        "slides": reports,
    }


if __name__ == "__main__":
    import json, sys
    path = sys.argv[1] if len(sys.argv) > 1 else "-"
    data = json.load(sys.stdin if path == "-" else open(path, encoding="utf-8"))
    print(json.dumps(critique_deck(data), ensure_ascii=False, indent=2))
