#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Intent Compression Layer（意图压缩层）：需求 → Design Brief。

流程里的位置：需求 → 本层 → Design Brief → 生成侧一次性写 spec。
Brief 之后只消费 Brief + Page Intent，不再回读原始需求。

两条纪律：

1. **显式永远赢**：需求里写了的字段原样进入 Brief，本层不改写、不美化。
2. **不知道就写 unknown**：本层不持有场景→风格语汇表，不从"董事会/发布会/年报"
   这类关键词里挑视觉世界。视觉方向是内容判断的产物，不是查表结果；没声明就
   留成待判断项（`unresolved`），由作者按内容决定，而不是由一个默认值决定。

确定性：同输入必得同 Brief。本模块只在函数内懒加载 route（import 零成本）。
"""
from __future__ import annotations

import hashlib
import json

UNKNOWN = "unknown"


def _value(need: dict, *keys: str) -> str:
    for key in keys:
        raw = need.get(key)
        if raw is None:
            continue
        if isinstance(raw, (list, tuple, dict)):
            if raw:
                return raw
            continue
        text = str(raw).strip()
        if text:
            return text
    return ""


def compile_brief(need: dict | str, route_plan: dict | None = None) -> dict:
    """需求 → Design Brief（确定性；显式字段永远赢，未声明一律 unknown）。

    need 可为 dict（audience/decision/tension/occasion/subject/brief/slides/
    visual_world/tone_hint/媒体与构图声明/brand_colors）或一段自然语言。
    route_plan 可传入统一 pipeline 已算好的 route 结果，避免重复推导。
    返回 {design_intent, strategy_seed, direction_seed, slides_seed, unresolved,
    source_hash}。
    """
    if isinstance(need, str):
        need = {"subject": need}
    need = dict(need or {})
    if route_plan is None:
        from route import plan_deck
        route_plan = plan_deck({k: need.get(k, "") for k in
                                ("audience", "decision", "occasion", "subject",
                                 "brief", "purpose", "design_direction",
                                 "quality_level")}
                               | {"slides": need.get("slides") or []})
    plan = route_plan

    audience = _value(need, "audience") or UNKNOWN
    decision = _value(need, "decision", "goal") or UNKNOWN
    tension = _value(need, "tension") or UNKNOWN
    tone = _value(need, "tone_hint", "emotional_target", "tone") or UNKNOWN
    visual_world = _value(need, "visual_world") or UNKNOWN
    composition = _value(need, "composition_grammar", "layout") or UNKNOWN
    type_voice = _value(need, "type_voice") or UNKNOWN
    color_behavior = _value(need, "color_behavior") or UNKNOWN
    color_intent = need.get("color_intent") or []
    media_role = _value(need, "media_policy", "media_role") or "none"
    background_scene = _value(need, "background_scene") or UNKNOWN
    motion_posture = _value(need, "motion_posture") or "still"
    avoid = list(need.get("avoid") or [])

    slides_seed = [{"id": p.get("id") or f"s{i + 1:02d}",
                    "family": p.get("page_family") or p.get("family"),
                    "density": p.get("density"), "energy": p.get("energy"),
                    "empty_space_role": p.get("empty_space_role"),
                    "density_explicit": bool(p.get("density_explicit"))}
                   for i, p in enumerate(plan.get("pages", []))]

    # 未声明项：Brief 明说"这里还没有判断"，而不是悄悄塞一个默认值。
    unresolved = []
    for field, value in (("audience", audience), ("decision", decision),
                         ("tension", tension), ("tone", tone),
                         ("visual_world", visual_world),
                         ("composition_grammar", composition),
                         ("type_voice", type_voice),
                         ("color_behavior", color_behavior),
                         ("background_scene", background_scene)):
        if value == UNKNOWN:
            unresolved.append(field)

    brief = {
        "design_intent": {
            "goal": decision,
            "audience": audience,
            "tone": tone,
            "visual_world": visual_world,
            "energy_curve": _value(need, "energy_curve") or UNKNOWN,
            "media_policy": media_role,
            "avoid": avoid,
        },
        "strategy_seed": {
            "audience": audience,
            "decision": decision,
            "tension": tension,
            "narrative_arc": list(need.get("narrative_arc") or []),
            "emotional_target": tone,
            "evidence_posture": _value(need, "evidence_posture") or "fact_led",
        },
        "direction_seed": {
            "visual_world": visual_world,
            "composition_grammar": composition,
            "type_voice": type_voice,
            "color_behavior": color_behavior,
            "color_intent": list(color_intent),
            "media_role": media_role,
            "background_scene": background_scene,
            "motion_posture": motion_posture,
            # route_direction 是可直接执行的方向 canonical key（材质/光/种子的兜底锚点）；
            # 它是**起点**不是结论——explicit 的 visual_world 一到，判断以内容为准。
            "route_direction": plan.get("design_direction") or "quiet_minimal",
        },
        "slides_seed": slides_seed,
        "unresolved": unresolved,
        "route": {"path": plan.get("path"),
                  "direction": plan.get("design_direction"),
                  "warnings": plan.get("warnings") or [],
                  "execution": (plan.get("execution") or {}).get("recommended")},
    }
    brief["source_hash"] = hashlib.sha256(
        json.dumps(need, ensure_ascii=False, sort_keys=True,
                   default=str).encode()).hexdigest()[:12]
    return brief


def _load_need(path: str) -> dict:
    """读需求：yml / json / 定义 BRIEF|NEED 的 Python 模块。"""
    from pathlib import Path
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"需求文件不存在或不是文件: {p}"
                         "（brief 需为 .yml/.yaml/.json 或定义 BRIEF/NEED 的 .py）")
    if p.suffix in (".yml", ".yaml"):
        import yaml
        try:
            value = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            # 带上文件与行列：brief 是人手写的文件，解析错误必须能直接定位。
            mark = getattr(exc, "problem_mark", None)
            where = f":{mark.line + 1}:{mark.column + 1}" if mark else ""
            problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
            raise ValueError(f"brief YAML 解析失败：{p}{where} — {problem}") from None
        if not isinstance(value, dict):
            raise ValueError(f"brief 顶层必须是对象/dict，实际是 {type(value).__name__}：{p}")
        return value
    if p.suffix == ".json":
        try:
            value = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"brief JSON 解析失败：{p}:{exc.lineno}:{exc.colno}"
                             f" — {exc.msg}") from None
        if not isinstance(value, dict):
            raise ValueError(f"brief 顶层必须是对象/dict，实际是 {type(value).__name__}：{p}")
        return value
    if p.suffix.lower() != ".py":
        raise ValueError("brief 只接受 JSON/YAML，或作者明确指定的可信 .py 文件")
    # 与 vao._load_module 同法：读→compile→exec，不写 __pycache__、不复用旧
    # 字节码——需求文件是人会反复编辑的文件，陈旧代价不该由交付链承担。
    import types
    mod = types.ModuleType("need_mod")
    mod.__file__ = str(p)
    exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), mod.__dict__)
    if hasattr(mod, "BRIEF"):
        return dict(mod.BRIEF)
    if hasattr(mod, "NEED"):
        return dict(mod.NEED)
    raise ValueError("需求需为 yml / json 或定义 BRIEF / NEED 的模块")
