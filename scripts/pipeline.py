#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-process planning entry point for PPT Visual Art Director OS.

Planning is one process, one pass: brief → route/decisions → plan.json (+ optional
build skeleton).  Keeping it in-process preserves the decision cache and avoids
re-reading the same input; the output artifact is the only handoff to the
spec-writing author.

It stops before compiling: planning is cheap and must never trigger compilation,
image generation, or any external renderer.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Support both `python scripts/pipeline.py` and importing the module from repo root.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from intent_compiler import compile_brief
from route import align_pages, explicit_content_type, one_pass_plan, plan_deck


def build_plan_bundle(need: dict) -> dict:
    """Build brief, deck route, layouts and forecast with one route computation."""
    t0 = time.perf_counter()
    need = dict(need or {})
    plan = plan_deck(need)
    brief = compile_brief(need, route_plan=plan)
    intelligence = one_pass_plan(need, plan=plan)

    # 页事实完整性：brief slides / plan.pages / 意图 pages 三份同出一次 route，
    # id 必须一一对应。错配（页数不同、id 集合不同、被手工改过页序）一律留痕，
    # 因为它会让骨架把 A 页的家族与骨架接到 B 页的内容上——错得无声无息。
    plan_pages = plan.get("pages") or []
    intel_pages = intelligence.get("pages") or []
    raw_slides = need.get("slides") if isinstance(need.get("slides"), list) else []
    align_warnings = alignment_warnings(plan_pages, intel_pages, raw_slides)
    if align_warnings:
        plan["warnings"] = list(plan.get("warnings") or []) + align_warnings

    # one_pass_plan returns the same plan for API convenience.  Do not duplicate
    # the large object in the persisted bundle.
    bundle = {
        "schema": "vao-plan-v1",
        "source_hash": brief.get("source_hash"),
        "need": need,
        "brief": brief,
        "plan": plan,
        "deck_decision": intelligence.get("deck_decision"),
        "color_plan": intelligence.get("color_plan"),
        "forecast": intelligence.get("forecast"),
        "pages": intelligence.get("pages") or [],
        "performance": {
            "planning_ms": round((time.perf_counter() - t0) * 1000, 2),
            "route_calls": 1,
            "rendered": False,
            "compiled": False,
        },
    }
    return bundle


def alignment_warnings(plan_pages: list[dict], intel_pages: list[dict],
                       raw_slides: list | None = None) -> list[dict]:
    """页事实没按 id 对齐时的留痕：可见、可批量修，但**不阻断**路由。

    这里的错配是「骨架张冠李戴」的前因（A 页的家族/骨架接到 B 页内容），
    所以宁可吵一次也不能静默。
    """
    low = align_pages(plan_pages, intel_pages)
    out = []
    if low["mismatch"]:
        out.append({"rule": "page_alignment", "scope": "deck",
                    "msg": (f"路由页 {low['pages']} 页 / 意图页 {low['other_pages']} 页"
                            f"未按 id 对齐（id 缺失或页序被改）：本次退回位置配对，"
                            f"请重新生成 plan.json")})
    slides = raw_slides if isinstance(raw_slides, list) else []
    if slides and len(slides) != low["pages"]:
        out.append({"rule": "page_alignment", "scope": "deck",
                    "msg": (f"brief 声明 {len(slides)} 页，路由产出 {low['pages']} 页："
                            f"骨架只落 {min(len(slides), low['pages'])} 页，先对齐页数")})
    return out


def blend_toward(color: str, target: str, t: float = 0.55) -> str:
    """把一个色朝可读端拉，用于骨架的可读性兜底（失败时原样返回）。"""
    try:
        from primitives import blend
        return blend(color, target, t)
    except Exception:
        return target


def build_skeleton_module(bundle: dict) -> str:
    """plan bundle → build 模块骨架。

    边界（技能包 ≠ 设计系统）：只把**已决策的事实**序列化——canvas 契约值、
    color_plan 种子槽位映射、每页 id / page_intent 骨架 / source_zone。
    `elements` 一律留空：几何、构图、字阶、媒体是生成侧的设计判断，骨架不预设。
    同 plan 必得同文本（确定性）。生成侧填完后直接
    `python scripts/vao.py check build.py deck.pptx --mode draft`。
    """
    need = bundle.get("need") or {}
    plan = bundle.get("plan") or {}
    plan_pages = plan.get("pages") or []
    intel_pages = bundle.get("pages") or []
    # 骨架合并按 id 认页，不按位置：id 不可用时 align_pages 才退回位置配对，
    # 且 mismatch 已由 build_plan_bundle 写进 plan.warnings。
    pairs = align_pages(plan_pages, intel_pages)["pairs"]
    color = bundle.get("color_plan") or {}
    seed = color.get("seed_skeleton") or {}
    raw_slides = need.get("slides") if isinstance(need.get("slides"), list) else []

    def _slot(name: str, fallback: str) -> str:
        v = seed.get(name) if isinstance(seed, dict) else None
        return v if isinstance(v, str) and v.startswith("#") else fallback

    # 种子四槽 → theme.colors 六 token（SKILL「seed 落进 spec.theme」的机械映射）
    colors = {"background": _slot("foundation", "#FFFFFF"),
              "ink": _slot("information", "#111111"),
              "muted": _slot("supporting", "#777777"),
              "primary": _slot("information", "#222222"),
              "secondary": _slot("supporting", "#333333"),
              "accent": _slot("accent", "#AA0000")}
    # 可读性兜底：骨架是作者的起点，**起点不能是不可读的**。品牌色可以落错槽
    # （品牌方给的就是一个深色主色，却被当成纸面），这类错不会报语法错误，
    # 只会让整副 deck 从第一笔起就 1.4:1。这里不替作者做设计判断，只保证
    # 「墨色与纸面分得开」：正文级 4.5:1 达不到时，把 ink/primary 翻到
    # 同色相的可读端（白或近黑），并把原色降级为 accent 之外的次级信号。
    try:
        from primitives import contrast, luminance
        if contrast(colors["background"], colors["ink"]) < 4.5:
            readable = "#FFFFFF" if luminance(colors["background"]) < 0.5 else "#141414"
            colors["ink"] = readable
            if contrast(colors["background"], colors["primary"]) < 4.5:
                colors["primary"] = readable
            if contrast(colors["background"], colors["secondary"]) < 3.0:
                colors["secondary"] = blend_toward(colors["secondary"], readable)
            if contrast(colors["background"], colors["muted"]) < 3.0:
                colors["muted"] = blend_toward(colors["muted"], readable)
    except Exception:
        pass                      # 骨架生成永远不因配色兜底而失败
    # 约束只传作者写下的：路线预设不再替作者发明审美数字（留白下限/字号级差/
    # 装饰面积/粗体占比）。包发明一个 58% 留白下限、再让 guard 去执法，等于用
    # 自己的默认值给自己判卷——实测在整幅画心页上必然误报。设计判断归设计智能，
    # 数字承诺归作者：写了才带下去，才被执法。
    _CONSTRAINT_KEYS = ("max_colors", "max_charts", "font_levels_max", "font_families_max",
                        "whitespace_min", "type_step_min", "bg_layers_max", "bold_ratio_max",
                        "bg_layer_coverage")
    _plan_theme = plan.get("theme") if isinstance(plan.get("theme"), dict) else {}
    _plan_cons = _plan_theme.get("constraints") if isinstance(_plan_theme.get("constraints"), dict) else {}
    seed_cons = {k: _plan_cons[k] for k in _CONSTRAINT_KEYS if k in _plan_cons}

    from asset_workflow import digest
    # ── 骨架自足化：把 plan.json 里 AI 真正要用的 ~2KB 信号序列化进头注释 ──
    # （方向族事实 / 统一契约 / 待判断槽位 / DNA 命中）。plan.json 仍是链路凭证，
    # 但正常填稿流程不再需要读它——41KB≈1.2 万 token 只为取几行事实，不值。
    dex = plan.get("direction_execution") if isinstance(plan.get("direction_execution"), dict) else {}
    dd = bundle.get("deck_decision") if isinstance(bundle.get("deck_decision"), dict) else {}
    dna = plan.get("dna") if isinstance(plan.get("dna"), dict) else {}
    unity = dd.get("unity") if isinstance(dd.get("unity"), dict) else {}
    slots = dd.get("slots") if isinstance(dd.get("slots"), list) else []
    facts: list[str] = []
    mat = dex.get("material") or color.get("material_language")
    world_bits = [x for x in (
        f"材质/世界: {mat}" if mat else "",
        f"光: {dex.get('light')}" if dex.get("light") else "",
        f"图表手法: {dex.get('chart_style')}" if dex.get("chart_style") else "") if x]
    if world_bits:
        facts.append(" · ".join(world_bits))
    if unity.get("same_world"):
        facts.append("统一契约 · 全 deck 必须统一: " + " / ".join(map(str, unity["same_world"]))
                     + "；允许每页不同: " + " / ".join(map(str, unity.get("may_differ") or [])))
    if slots:
        facts.append("等你判断的槽位（SPEC/页面里已留 TODO）: " + " / ".join(map(str, slots)))
    if dna.get("matched"):
        facts.append(f"经验召回（DNA）: {dna['matched']} · 置信 {dna.get('confidence')}"
                     "——DNA 是起点不是模板，按本稿内容与受众重组")
        if dna.get("design_problem"):
            facts.append(f"  核心矛盾: {str(dna['design_problem'])[:76]}")
        if dna.get("avoid"):
            facts.append("  避讳: " + " / ".join(map(str, list(dna["avoid"])[:6])))
    L = ['# -*- coding: utf-8 -*-',
         '"""plan → build 骨架：只给出已决策的事实，零几何/样式预设。',
         '',
         '本文件即完整作业单：下面列出的事实、契约与公式已经齐了，正常流程不需要',
         '再读 plan.json（那是链路凭证，不是作业输入）。骨架刻意不给坐标：',
         '构图、尺度、留白由你按内容判断。',
         f'方向: {plan.get("design_direction")} · 质量: {plan.get("quality_level")}（{plan.get("mode")}）'
         f' · 页数: {len(raw_slides) or len(plan_pages)}']
    L += [f'  {line}' for line in facts]
    L += ['',
         '落笔清单（一次做完，不要回来补第二遍）：',
         '  1) 每页 page_intent.insight（本页唯一结论）与 focus（视线第一落点元素 id）',
         '  2) elements 平铺写：x/y/width/height 数值（8 的倍数）+ text + size/color/',
         '     bold/align/max_lines/line_height/padding；框高 ≥ 字号 × 行高(默认1.35) × 行数；',
         '     行宽容量 ≈ 盒宽/字号（CJK 每字 1.0，拉丁 ~0.55，中西边界自动加 0.2 细空格），',
         '     标题按 +20% 余量给宽；wrap=False 的单行文本盒宽 ≥ 1.5× 估算宽度',
         '  3) theme.fonts 写 {cn, latin}（家族 ≤2）；direction.color_intent: [brand, emotion, hierarchy]\n'
         '     theme.constraints 是方向发下来的数字下限/上限，照抄别改——guard 会照着它执法',
         '  4) 图表页齐 source/unit/period/basis；source_zone 内只放 role∈{source,method,metadata}',
         '  5) 文本/图表/图片/来源区墨迹不相交；内容过多时先删句、再改写，不要缩字号',
         '  6) 每页 anchor（眉标/页码）要落成元素：眉标 role=eyebrow（家族词汇原文）、'
         '页码 role=page_number；位置全 deck 一致。论文式证据编号已弃用——'
         '出处信息只进 source_zone 框（role=source/method/metadata）',
         '',
         '有图页先执行 assets → 出图；图片元素必须写 asset_id（核验在 check 内部完成）。',
         '填完后一次收口（release 含 Manifest 证据链）：',
         '  python scripts/vao.py check <本文件> out.pptx --mode release --assets-manifest asset_manifest.json',
         '首轮目标就是一次过 release；确需迭代构图时才先 --mode draft，终稿必须回到 release。',
         '"""',
         '',
         'SPEC = {',
         '    "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},',
         '    "theme": {',
         f'        "colors": {colors!r},',
         '        "fonts": {"cn": "TODO", "latin": "TODO"},   # 家族 ≤2；display/body 是等价别名',
         f'        "constraints": {seed_cons!r},   # 方向种子（数字约束）：写进 spec 才会被执法',
         '    },',
         '    "strategy": {},                      # TODO：P2 Strategy（受众/决策/张力/证据）',
         '    "direction": {"color_intent": []},  # TODO：[brand, emotion, hierarchy]',
         f'    "asset_workflow": {{"plan_sha256": {digest(bundle)!r}, "plan_path": {(bundle.get("workflow") or {}).get("plan_path")!r}}},',
         '    "slides": [']
    for i in range(len(raw_slides)):
        pg, intel = pairs[i] if i < len(pairs) else ({}, {})
        skel = dict(intel.get("skeleton") or {})
        skel["insight"] = ""          # 内容判断留给生成侧
        skel["focus"] = ""
        raw = raw_slides[i]
        # 页面身份以**作者写的 slide** 为准：骨架不能比 brief 少一页，也不能替它换 id。
        sid = str(raw["id"]) if isinstance(raw, dict) and raw.get("id") else str(
            pg.get("id") or f"s{i + 1:02d}")
        if isinstance(raw, dict):
            ref = " ".join(str(raw.get(k) or "") for k in ("title", "content")).strip()
            declared = explicit_content_type(raw)
            if declared:
                ref = f"{ref}（作者声明：{declared}）"
        else:
            ref = str(raw).strip()
        media = ((intel.get("media") or {}).get("decision")
                 or (pg.get("asset") or {}).get("decision") or "none")
        family = skel.get("page_family") or pg.get("page_family") or "TODO"
        comp = intel.get("composition") or {}
        move = str((intel.get("move") or {}).get("move") or "").strip()
        # 作者声明了资产角色就写在作业面上：填空的人据此决定这张图是整幅承载
        # （layer=background + overlay）还是立在栏内的独立视觉对象。
        role = (pg.get("asset") or {}).get("role")
        role_txt = f" · role={role}" if role else ""
        L.append(f'        # ── {sid} · family={family}'
                 f' · density={pg.get("density")} · energy={pg.get("energy")}'
                 f' · media={media}{role_txt}')
        if move:
            L.append(f'        #    叙事动作: {move}')
        if comp.get("intent") or comp.get("grammar"):
            grammar = comp.get("grammar") or "自由"
            intent_txt = str(comp.get("intent") or "").strip() or "（按家族惯例构图）"
            L.append(f'        #    构图意图: {intent_txt}（语法={grammar}，可推翻）')
        if ref:
            L.append(f'        #    内容参考: {ref[:90]}')
        if pg.get("content_missing"):
            L.append('        #    ⚠ 未决（unresolved）: content 缺失——标题不是证据，不得由它'
                     '脑补数据/案例；补真实证据，或改成纯排版观点页，或删掉这一页')
        L.append('        {')
        L.append(f'            "id": {sid!r},')
        L.append(f'            "page_intent": {json.dumps(skel, ensure_ascii=False)},'
                 '  # TODO: insight/focus')
        anc = pg.get("anchor") if isinstance(pg.get("anchor"), dict) else None
        if anc:
            L.append(f'            "anchor": {json.dumps(anc, ensure_ascii=False)},'
                     '  # 眉标固定上缘 / 页码固定象限（落成对应 role 的元素）')
        L.append('            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},')
        L.append('            "elements": [  # TODO：按本页构图语法落元素（几何与样式规则见文件头）')
        L.append('            ],')
        L.append('        },')
    L += ['    ],', '}', '']
    return "\n".join(L)




