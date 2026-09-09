# -*- coding: utf-8 -*-
"""
Layer 0.7 · Route（视觉智能决策层 / Visual Intelligence Layer）

职责：把「内容类型 + 设计方向 + 质量等级」推导成页面级设计决策，替代逐页人工配置与
逐轮渲染试错。它不做审美裁决（那是 art_critic），也不持有主题（那是 spec.theme）。

对外只有两个函数：

    plan_page(content_type, design_direction, quality_level) -> PagePlan
    plan_deck(brief) -> {"path", "pages", "assets", "workflow", "budget"}

brief 最小集（plan_deck 的唯一输入，yml / json / 定义 BRIEF 的模块均可）：

    audience: 董事会            decision: 追加品牌预算
    occasion: 2026 年终总结      design_direction: editorial_brand   # 可省，按 occasion 推断
    quality_level: fast|advanced                                   # 可省
    slides: ["封面：年度总结", {"id": "s04", "type": "data", "title": "增长结构"}]

CLI：``python3 scripts/route.py brief.yml --json``（``--demo`` 用内置示例 deck 验证行为）。

设计约束（与 SKILL.md「Less System, More Intelligence」一致）：
  * 纯函数、零配置、零外部依赖；不读写主题 Markdown，不产生文件。
  * 输出的是**建议与预算**，不改变 guard/compile/qa 的判定口径。
  * 只维护一张路由表；新增内容类型 = 在 ROUTES 加一行，不新增文件、不新增抽象层。
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────
# 内容类型词表（中英文关键词 → 内容类型）
# ─────────────────────────────────────────────────────────────
KEYWORDS: dict[str, tuple[str, ...]] = {
    "cover":        ("封面", "主题", "标题页", "cover", "title", "opening"),
    "agenda":       ("目录", "议程", "概览", "agenda", "contents", "summary"),
    "business":     ("经营", "业绩", "指标", "达成", "总结", "overview", "kpi", "okr",
                     "review", "复盘"),
    "statement":    ("判断", "观点", "结论", "原则", "主张", "statement", "insight",
                     "quote", "金句"),
    "data":         ("数据", "图表", "趋势", "增长", "占比", "转化", "同比", "环比",
                     "chart", "data", "revenue", "growth", "funnel"),
    "comparison":   ("对比", "前后", "竞品", "优劣", "vs", "compare", "benchmark"),
    "timeline":     ("时间轴", "里程碑", "历程", "阶段", "timeline", "roadmap",
                     "milestone"),
    "architecture": ("体系", "架构", "框架", "模型", "能力", "组织", "framework",
                     "architecture", "system", "structure"),
    "process":      ("流程", "步骤", "路径", "机制", "how", "process", "workflow",
                     "flow"),
    "product":      ("产品", "发布", "功能", "规格", "型号", "product", "feature",
                     "launch", "spec"),
    "brand_story":  ("品牌", "故事", "理念", "价值观", "缘起", "brand", "story",
                     "manifesto", "identity"),
    "case":         ("案例", "客户", "实证", "试点", "case", "study", "pilot"),
    "closing":      ("决定", "请求", "行动", "下一步", "展望", "结束", "close",
                     "ask", "next", "call to action", "vision"),
}

# ─────────────────────────────────────────────────────────────
# 路由表：content_type → 页面家族 / 密度 / 能量 / 素材策略 / 字阶
#   asset: required 必须出图 · optional 视质量等级 · none 禁止出图（省时间、省 token）
#   density 与 art_critic 的渲染占用率目标同向（sparse .30 / balanced .55 / dense .75）
# ─────────────────────────────────────────────────────────────
ROUTES: dict[str, dict] = {
    "cover":        dict(family="COVER", density="sparse", energy="high",
                         asset="required", asset_function="hero", type_scale=(64, 20, 12),
                         media=1, texts=4, empty_space="hold_emotion"),
    "brand_story":  dict(family="EDITORIAL", density="sparse", energy="medium",
                         asset="required", asset_function="emotion", type_scale=(48, 20, 12),
                         media=1, texts=4, empty_space="hold_emotion"),
    "product":      dict(family="HERO", density="balanced", energy="high",
                         asset="required", asset_function="hero", type_scale=(52, 18, 12),
                         media=1, texts=4, empty_space="protect_focus"),
    "case":         dict(family="CASE_STUDY", density="balanced", energy="medium",
                         asset="optional", asset_function="proof", type_scale=(44, 18, 12),
                         media=2, texts=4, empty_space="create_authority"),
    "statement":    dict(family="MINIMAL_STATEMENT", density="sparse", energy="low",
                         asset="optional", asset_function="emotion",
                         type_scale=(56, 20, 12), media=1, texts=4, empty_space="hold_emotion"),
    "closing":      dict(family="MINIMAL_STATEMENT", density="sparse", energy="medium",
                         asset="optional", asset_function="emotion",
                         type_scale=(56, 20, 12), media=1, texts=4, empty_space="hold_emotion"),
    "business":     dict(family="EXECUTIVE_SUMMARY", density="balanced", energy="medium",
                         asset="none", asset_function=None, type_scale=(44, 18, 12),
                         media=1, texts=4, empty_space="create_authority"),
    "agenda":       dict(family="EXECUTIVE_SUMMARY", density="balanced", energy="low",
                         asset="none", asset_function=None, type_scale=(40, 18, 12),
                         media=1, texts=5, empty_space="separate_chapter"),
    "data":         dict(family="DATA_STORY", density="balanced", energy="low",
                         asset="none", asset_function=None, type_scale=(44, 18, 12),
                         media=1, texts=4, empty_space="protect_focus"),
    "comparison":   dict(family="COMPARISON", density="balanced", energy="low",
                         asset="none", asset_function=None, type_scale=(44, 18, 12),
                         media=1, texts=4, empty_space="protect_focus"),
    "timeline":     dict(family="TIMELINE", density="balanced", energy="medium",
                         asset="none", asset_function=None, type_scale=(44, 18, 12),
                         media=1, texts=4, empty_space="separate_chapter"),
    "architecture": dict(family="FRAMEWORK", density="balanced", energy="medium",
                         asset="optional", asset_function="context",
                         type_scale=(48, 20, 12), media=1, texts=4,
                         empty_space="separate_chapter"),
    "process":      dict(family="NARRATIVE", density="balanced", energy="medium",
                         asset="none", asset_function=None, type_scale=(44, 18, 12),
                         media=1, texts=4, empty_space="separate_chapter"),
}
DEFAULT_ROUTE = ROUTES["business"]

# 设计方向 → 视觉推导（材质 / 光线 / 图表风格 / 背景策略）。只列可执行差异，不做形容词堆叠。
# theme_seed：该方向的「成品种子色板 + 字体」。种子不是模板——spec.theme 拿到种子后仍由
# primitives.derive_tokens 规则展开出完整色阶（panel/hairline/ramp/series…），调用方也仍可
# 覆盖任意一项。这里只解决「选了方向却还要自己手挑 hex」的空白，把方向落到一组调好的锚点色。
DIRECTION_PRESETS: dict[str, dict] = {
    "quiet_minimal": dict(
        background="solid_world", material="matte paper",
        light="flat even ambient", chart="hairline + direct label",
        motion="still", asym=False,
        theme_seed=dict(
            colors={"background": "#F5F4EF", "surface": "#FBFAF6",
                    "primary": "#26251F", "secondary": "#6E6A5E",
                    "accent": "#B3422A", "ink": "#1B1A16", "muted": "#8A857A"},
            fonts={"cn": "PingFang SC", "latin": "Helvetica Neue",
                   "display": "Helvetica Neue"},
            text_default="ink",
            chart_primary="primary", chart_secondary="accent", chart_muted="secondary",
            constraints={"accent_max": 0.05, "max_colors": 5, "min_whitespace": 0.35},
            color_intent=["hierarchy", "emotion", "brand"],
        )),
    "editorial_brand": dict(
        background="atmospheric", material="paper + ink wash",
        light="single soft upper-left", chart="annotation field",
        motion="reveal", asym=True,
        theme_seed=dict(
            colors={"background": "#FAF7F0", "surface": "#F4EFE6",
                    "primary": "#2B241B", "secondary": "#9A8F7C",
                    # 信号色用编辑红（oxblood）：与棕/沙色相区分，承担「唯一重点」；
                    # 金属金降为 premium，仅供克制的符号性点缀（不参与强调判定）。
                    "accent": "#8E2F28", "premium": "#A97E2F",
                    "ink": "#191510", "muted": "#7C7468"},
            fonts={"cn": "Songti SC", "latin": "Georgia", "display": "Georgia"},
            text_default="ink",
            chart_primary="primary", chart_secondary="accent", chart_muted="secondary",
            constraints={"accent_max": 0.04, "max_colors": 5, "min_whitespace": 0.40},
            color_intent=["brand", "emotion", "hierarchy"],
        )),
    "product_stage": dict(
        background="dark_luminous", material="glass + metal",
        light="one key light", chart="minimal kpi",
        motion="reveal", asym=False,
        theme_seed=dict(
            colors={"background": "#0B0B0F", "surface": "#15151A",
                    "primary": "#E4E4EA", "secondary": "#3A3A42",
                    "accent": "#3B82F6", "ink": "#F5F5F7", "muted": "#8E8E96"},
            fonts={"cn": "PingFang SC", "latin": "Helvetica Neue",
                   "display": "Helvetica Neue"},
            text_default="ink",
            chart_primary="primary", chart_secondary="accent", chart_muted="secondary",
            constraints={"accent_max": 0.05, "max_colors": 5, "min_whitespace": 0.40},
            color_intent=["emotion", "brand", "hierarchy"],
        )),
    "evidence_first": dict(
        background="solid_world", material="neutral surface",
        light="flat", chart="shared baseline + delta",
        motion="still", asym=False,
        theme_seed=dict(
            # 数据智能：纯中性结构（近黑墨 + 中性灰）+ 单一蓝信号。蓝是唯一的色相，
            # 结构色保持无彩度，让「蓝色」真正成为唯一重点信号（palette_discipline
            # 的 accent 角距离门禁因此通过，而非靠同族深浅堆出伪强调）。
            colors={"background": "#FFFFFF", "surface": "#F4F5F6",
                    "primary": "#1C1C1C", "secondary": "#5A5A5A",
                    "accent": "#2563EB", "ink": "#101010", "muted": "#6E6E6E"},
            fonts={"cn": "PingFang SC", "latin": "Helvetica Neue",
                   "display": "Helvetica Neue"},
            text_default="ink",
            chart_primary="primary", chart_secondary="accent", chart_muted="secondary",
            constraints={"accent_max": 0.05, "max_colors": 5, "min_whitespace": 0.30},
            color_intent=["hierarchy", "brand", "emotion"],
        )),
}

ADVANCED_TRIGGERS = ("发布会", "品牌", "年报", "旗舰", "形象", "高端", "launch", "brand",
                     "keynote", "manifesto", "premium", "campaign")


def detect_type(text: str) -> str:
    """按关键词命中内容类型；未命中时回落到 business（最常见的汇报页）。"""
    t = (text or "").lower()
    best, best_hits = None, 0
    for ctype, kws in KEYWORDS.items():
        hits = sum(1 for k in kws if k in t)
        if hits > best_hits:
            best, best_hits = ctype, hits
    return best or "business"


QUALITY_ALIASES = {"fast": "fast", "quick": "fast", "standard": "fast",
                   "advanced": "advanced", "premium": "advanced", "keynote": "advanced"}
MODE_LABEL = {"fast": "Fast Mode", "advanced": "Premium Mode"}


def _quality(quality_level) -> str:
    """归一质量等级：只认 fast / advanced，别名（quick、premium、keynote）映射过去，
    未知值落到 fast——「不确定时先走轻流程」比「默认最高复杂度」更符合成本约束。"""
    return QUALITY_ALIASES.get(str(quality_level or "").strip().lower(), "fast")


def plan_page(content_type: str, design_direction: str = "editorial_brand",
              quality_level: str = "advanced") -> dict:
    """单页推导：内容类型 + 设计方向 + 质量等级 → 布局 / 密度 / 字阶 / 素材 / 图表口径。

    参数只有三个，其余全部由 ROUTES 与 DIRECTION_PRESETS 推导；调用方不应再逐页传
    color / mood / lighting / material / composition —— 那些是本页的输出，不是输入。
    """
    if content_type not in ROUTES:
        content_type = detect_type(content_type)
    r = ROUTES.get(content_type, DEFAULT_ROUTE)
    d = DIRECTION_PRESETS.get(design_direction, DIRECTION_PRESETS["editorial_brand"])
    quality = _quality(quality_level)

    asset = r["asset"]
    if asset == "optional":
        asset = "required" if quality == "advanced" else "none"
    if quality == "fast" and asset == "required" and r["asset_function"] in ("emotion",):
        asset = "reuse"          # 快速路径：复用已有画心，不再新出图
    statement, body, caption = r["type_scale"]
    if quality == "fast":        # 快速路径收一档尺度，降低构图与裁切复杂度
        statement = max(40, int(statement * 0.85) // 4 * 4)

    pixel = asset == "required" or r["family"] == "COVER"
    return {
        "content_type": content_type,
        "mode": MODE_LABEL[quality],
        "needs_pixel_evidence": pixel,
        "page_family": r["family"],
        "density": r["density"],
        "energy": r["energy"],
        "empty_space_role": r["empty_space"],
        "media_budget": r["media"],
        "text_budget": r["texts"],
        "type_scale": {"statement": statement, "body": body, "caption": caption},
        "asset": {"decision": asset, "function": r["asset_function"],
                  "why": _asset_reason(content_type, asset)},
        "derived": {
            "background": d["background"],
            "material": d["material"],
            "light": d["light"],
            "chart_style": d["chart"],
            "motion": d["motion"],
            "composition_grammar": "soft_asymmetry" if d["asym"] else "evidence_field",
        },
        # 该方向的成品种子色板/字体：直接落进 spec.theme，derive_tokens 据此展开完整色阶。
        # 种子可被调用方覆盖；它是「起点的锚点」，不是「终点的模板」。
        "theme_seed": d.get("theme_seed", {}),
        "focus": "statement",     # 焦点恒为 Statement 级结论（≥ STATEMENT_SIZE 且领先 1.25×）
    }


def _asset_reason(ctype: str, decision: str) -> str:
    if decision in ("required", "reuse"):
        return f"{ctype} 承担空间/情绪/实证职责，画心是内容的一部分"
    if decision == "none":
        return f"{ctype} 的注意力预算属于数据与结论，出图会争夺第一注意点"
    return f"{ctype} 可视质量等级决定，advanced 才出图"


_DECK_CACHE: dict[str, dict] = {}
_CACHE_STATS = {"hits": 0, "misses": 0}
MAX_DECK_CACHE = 32   # 只缓存整副 deck 的规划结果；有界，不演化成配置系统


def cache_stats() -> dict:
    """决策缓存命中情况（用于核对「修订循环里是否还在重复推导」）。"""
    return {**_CACHE_STATS, "size": len(_DECK_CACHE), "max": MAX_DECK_CACHE}


def clear_cache() -> None:
    _DECK_CACHE.clear()
    _CACHE_STATS["hits"] = _CACHE_STATS["misses"] = 0


def plan_deck(brief: dict) -> dict:
    """整副 deck 的路径判定 + 逐页规划 + 素材预算 + 建议执行链（带决策缓存）。

    brief 最小集：{"audience","decision","occasion","slides":[str|dict], "quality_level"?}

    Decision Before Generation：一次推导供 guard / compile / qa / critic 全流程消费；
    同一 brief 的重复调用（修订循环、多次调用同一进程）直接命中缓存，且返回深拷贝，
    调用方可以随意改结果而不污染缓存。
    """
    try:
        import copy as _copy
        import json as _json
        key = _json.dumps(brief, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:                      # 不可序列化 → 直接算，不缓存
        return _plan_deck(dict(brief))
    hit = _DECK_CACHE.get(key)
    if hit is not None:
        _CACHE_STATS["hits"] += 1
        return _copy.deepcopy(hit)
    _CACHE_STATS["misses"] += 1
    plan = _plan_deck(dict(brief))
    if len(_DECK_CACHE) >= MAX_DECK_CACHE:  # 有界缓存：先淘汰最早写入的一半
        for k in list(_DECK_CACHE)[: MAX_DECK_CACHE // 2]:
            _DECK_CACHE.pop(k, None)
    _DECK_CACHE[key] = plan
    return _copy.deepcopy(plan)


def _plan_deck(brief: dict) -> dict:
    occasion = f"{brief.get('occasion','')} {brief.get('subject','')} {brief.get('brief','')}"
    quality = _quality(brief["quality_level"]) if brief.get("quality_level") else (
        "advanced" if any(k in occasion.lower() or k in occasion for k in ADVANCED_TRIGGERS)
        else "fast")
    direction = brief.get("design_direction") or (
        "editorial_brand" if quality == "advanced" else "quiet_minimal")

    raw = brief.get("slides") or []
    pages = []
    for i, item in enumerate(raw):
        ctype = item.get("type") if isinstance(item, dict) else None
        text = (item.get("title", "") + " " + item.get("content", "")) if isinstance(
            item, dict) else str(item)
        plan = plan_page(ctype or text, direction, quality)
        plan["index"] = i + 1
        plan["id"] = (item.get("id") if isinstance(item, dict) and item.get("id")
                      else f"s{i + 1:02d}")
        pages.append(plan)
    _alternate_density(pages)

    needed = [p["id"] for p in pages if p["asset"]["decision"] in ("required",)]
    reused = [p["id"] for p in pages if p["asset"]["decision"] == "reuse"]
    cap = 2 if quality == "fast" else 4
    assets = {"generate": needed[:cap], "generate_extra": needed[cap:], "reuse": reused,
              "skipped": [p["id"] for p in pages if p["asset"]["decision"] == "none"]}
    assets["planned_calls"] = len(assets["generate"])
    workflow = ["route → 冻结输入（受众/决定/口径）",
                "布局迭代用 Level 1（不渲染）/ Level 2（只测关键页）；"
                "发布必须 Level 3 全量：qa.py <build> out.pptx --quick | --key-pages | 默认",
                f"guard 预检（静态，~0.01s/页）：python3 scripts/guard.py <build> --preflight",
                "修完预检再编译：python3 scripts/compiler.py <build> out.pptx",
                ("快速路径 QA：python3 scripts/qa.py <build> out.pptx --fast --manifest"
                 if quality == "fast" else
                 "发布 QA：python3 scripts/qa.py <build> out.pptx --manifest（含渲染证据 + Critic）")]
    if quality == "advanced":
        workflow.append("资产：仅对 assets.generate 中的页面调用图像模型，逐页绑定留白锚点")
    # 哪些页面值得付渲染成本：首尾页 + 需要画心的页（图表与遮挡由 QA 从 spec 兜底挑选）
    pixel_ids = sorted({p["id"] for p in pages if p["needs_pixel_evidence"]}
                       | ({pages[0]["id"], pages[-1]["id"]} if pages else set()))
    seed = DIRECTION_PRESETS.get(direction, DIRECTION_PRESETS["editorial_brand"]).get("theme_seed", {})
    return {
        "path": quality,
        "mode": MODE_LABEL[quality],
        "design_direction": direction,
        "theme": seed,      # 整副 deck 的主题种子：落进 spec.theme（可覆盖）
        "pages": pages,
        "assets": assets,
        "verification": {
            "iteration_level": 1,                    # 迭代期先看结构，不必每轮渲染
            "release_level": 3,                      # 发布必须全量像素证据
            "pixel_page_ids": pixel_ids,
            "pixel_pages": len(pixel_ids),
            "reason": ("迭代用 Level 1 静态判定 + 关键页渲染；发布用 Level 3 全量"
                       if quality == "fast" else
                       "发布级 deck：关键页先测，收口仍需 Level 3 全量复核"),
        },
        # 两线程执行模型（严格上限 2）：设计推导与资产/渲染互不等待，只在 QA 处汇合一次。
        # 没有回环：Thread2 从不回头要求 Thread1 重新推导；修正由预检/QA 的结论驱动。
        "pipelines": {
            "workers": 2,
            "design": ["route", "guard --preflight", "spec 修正（只按预检项改，不重排全篇）"],
            "asset_render": ["asset_prompt → 图像模型（仅 assets.generate）", "compiler",
                             f"render + measure（workers=2，Level {2 if quality == 'fast' else 3}）"],
            "join": "qa.run_qa（唯一同步点：静态结论 + 渲染证据在此合并计分）",
            "exchange": "单一 spec / plan JSON；禁止逐页往返通信",
            "forbidden": ["无限并发", "渲染等待预检的循环依赖", "每轮都跑全量 Critic"],
        },
        "budget": {"max_asset_calls": cap,
                   "max_charts_per_page": 1,
                   "max_text_objects_per_page": 4,
                   "render_dpi": 72 if quality == "fast" else 96,
                   "render_workers": 2,
                   "art_critic": quality == "advanced"},
        "workflow": workflow,
    }


def _alternate_density(pages: list[dict]) -> None:
    """疏密曲线：相邻页 density 互斥（与 guard DENSITY_FLAT / art_critic rhythm 同口径）。

    优先级：首尾保留大留白（opening/closing 的仪式感）→ 中部自动避让 →
    若末页与前页冲突，改前页而不是改末页，避免为了规则牺牲收束感。
    """
    if not pages:
        return
    nxt = {"sparse": "balanced", "balanced": "dense", "dense": "balanced"}
    pages[0]["density"] = "sparse"
    pages[-1]["density"] = "sparse"
    body = pages[1:-1]
    for i, cur in enumerate(body):
        prev = pages[i]
        if cur["density"] == prev["density"]:
            cur["density_declared_conflict"] = cur["density"]
            cur["density"] = nxt[cur["density"]]
    if len(pages) > 1 and pages[-1]["density"] == pages[-2]["density"]:
        pages[-2]["density_declared_conflict"] = pages[-2]["density"]
        pages[-2]["density"] = nxt[pages[-2]["density"]]


# --------------------------------------------------------------------------
# CLI： python route.py brief.yml [--json]      或      python route.py --demo
# --------------------------------------------------------------------------
def _load_brief(path: str) -> dict:
    from pathlib import Path
    p = Path(path)
    if p.suffix in (".yml", ".yaml"):
        import yaml
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if p.suffix == ".json":
        import json
        return json.loads(p.read_text(encoding="utf-8"))
    if p.suffix == ".py":
        import importlib.util
        spec = importlib.util.spec_from_file_location("briefmod", str(p))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.BRIEF if hasattr(mod, "BRIEF") else mod.build_brief()
    raise ValueError("brief 需为 yml / json 数据文件或定义 BRIEF 的模块")


def main(argv=None) -> int:
    import json
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 1
    brief = {"slides": []} if argv[0] == "--demo" else _load_brief(argv[0])
    if argv[0] == "--demo":
        brief = {"occasion": "2026 年终总结 · 品牌与市场", "audience": "董事会",
                 "slides": ["封面：2026 年度总结", "全年经营概览与四项 KPI",
                            "预算结构对比 2024-2026", "增长的三处摩擦",
                            "核心判断：品牌是本金，投放是利息", "数据：品牌搜索与线索转化趋势",
                            "渠道效率排行", "三层内容体系", "年度 campaign 案例",
                            "活动前后对比", "2027 目标", "请求两项决定"]}
    print(json.dumps(plan_deck(brief), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
