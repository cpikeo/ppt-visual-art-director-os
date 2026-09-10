# -*- coding: utf-8 -*-
"""
Layer -1 · Design Intelligence（设计智能层——所有流程的大脑）

职责：把「生成 → 检查 → 发现问题 → 修复 → 再生成」升级为
    「理解 → 预测 → 决策 → 生成 → 一次通过」。

四个引擎（全部确定性、纯函数、可独立调用）：

  ① Design DNA Memory    设计经验记忆（不是模板/组件/固定页面——是「看到需求就知道
                          该怎么做」的可复用设计判断）。recall(brief) 在 P1 命中，
                          record(entry) 在 PASS 发布后沉淀——设计经验随使用累积。
  ② Media Decision Model 媒体决策模型：这页要不要图？置信度 + 理由（不是规则闸门
                          的布尔值）。「数据页不出图」从禁令变成可解释的判断。
  ③ Page Quality Budget  页面质量预算：不同页面家族追求不同的好——Hero 页允许
                          高复杂度换情绪，数据页把清晰与准确放第一位。
  ④ Risk Prediction Engine 风险预测（**不是独立审查环节，是本层内部的预测子模块**）：
                          `pre_critic(spec)` 用与 Critic/QA 同一套常量在渲染之前估计
                          accent 超载、锚点缺失、对比度、焦点冲突、文本溢出、节奏趋平、
                          密度失配、媒体误用；`risk_strategy(spec)` 把预测**翻译成生成
                          策略**（逐页媒体/文本/字阶/图表/构图调整 + 整套 deck 政策），
                          在起草之前消费。每条风险标注根因（与 Critic verdict 同一分类法）。

analyze(brief, spec) 把三条智能线（内容/视觉/风险与策略）汇合成一次调用——
内容分析、视觉分析、风险分析互不依赖，无需串行等待。

与既有层的关系（**职责边界，不重叠**）：本层负责「设计判断 + 未来风险」；
`guard.py` / `qa.py` 负责工程正确性（溢出、越界、重叠、数据合同、渲染完整性），
`art_critic.py` 负责设计价值（层级、空间节奏、信息焦点、审美一致性、品牌气质）。
预测阈值同源于 art_critic.py / qa.py 导出常量：本层只加预测与策略，
不改任何判定标准，也不替代渲染证据。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from primitives import DEFAULT_WIDTH, DEFAULT_HEIGHT, contrast, estimate_lines
from art_critic import (_memory_anchor, _content_occupancy, STATEMENT_SIZE,
                        FOCUS_LEAD, FOCUS_AREA_LEAD, RHYTHM_INK_DELTA,
                        RHYTHM_INK_FLAT)

DNA_STORE = Path(__file__).resolve().parent.parent / "memory" / "design_dna.json"

# ── 密度带（与 art_critic._content_occupancy 判读一致）─────────────────
DENSITY_BANDS = {"sparse": (0.0, 0.60), "balanced": (0.65, 0.75),
                 "dense": (0.75, 0.85)}
# 图表 accent 面积估算（按 chart_kind 物理形态校准，宁可轻微高估不可漏报）：
# 构成图（donut/pie）：高亮扇区是实心大块 —— 环带 ≈62% bbox × 扇区占比
# 条形族：细轨道 + 圆头端点，实际着色 ≈7% bbox ×（高亮值/最大值）
# 点缀类（时间轴/步骤/大数字）：小面积强调
_BAR_FAMILY = {"bar", "column", "horizontal_bar", "ranked_bar", "comparison_bar",
               "stacked_bar", "progress_bar", "waterfall"}
_SMALL_ACCENT = {"line": 0.02, "trend": 0.02, "single_trend_line": 0.02,
                 "area": 0.05, "sparkline": 0.02, "timeline": 0.04, "steps": 0.04,
                 "process_flow": 0.04, "big_number": 0.08, "kpi": 0.08,
                 "executive_kpi": 0.08, "big_number_row": 0.06, "matrix": 0.04}
_TEXT_INK_FACTOR = 0.40      # 文本框 → 可见墨迹的折算（accent 文字估算用）
_SHAPE_FILL_FACTOR = 0.90   # 实心形状着色率


# ════════════════════════════════════════════════════════════════════════
# ① Design DNA Memory
# ════════════════════════════════════════════════════════════════════════
def _load_store() -> dict:
    try:
        return json.loads(DNA_STORE.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "entries": []}


def recall_dna(brief: dict) -> dict:
    """brief → 最匹配的设计经验（确定性关键词打分）。

    返回 {matched, confidence, dna, alternatives, note}。
    confidence = 命中签名词数 / 该条签名总词数（0–1）。无命中时返回最近邻 +
    「adapt」提示——DNA 是起点不是答案，Art Director 仍要按当前内容重组。
    """
    text = " ".join(str(v) for v in (brief or {}).values() if isinstance(v, (str, int, float)))
    low = text.lower()
    scored = []
    for e in _load_store().get("entries", []):
        sig = [s.lower() for s in
               (e.get("signature", {}).get("keywords", []) or [])]
        if not sig:
            continue
        hits = sum(1 for s in sig if s in low)
        scored.append((hits / len(sig), hits, e))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2].get("id", "")))
    if not scored or scored[0][0] <= 0:
        return {"matched": None, "confidence": 0.0, "dna": None,
                "alternatives": [], "note": "无匹配 DNA：从主题种子起步，发布 PASS 后 record_dna 沉淀这条经验"}
    conf, hits, best = scored[0]
    alts = [{"id": e.get("id"), "confidence": round(c, 2)}
            for c, h, e in scored[1:3] if c > 0]
    return {"matched": best.get("id"), "confidence": round(conf, 2),
            "dna": (best.get("judgment") or best.get("dna")),
            "design_problem": best.get("design_problem"),
            "avoid": best.get("avoid") or best.get("dna", {}).get("forbidden"),
            "alternatives": alts,
            "proven": best.get("proven"),
            "note": ("DNA 是起点不是模板：按当前内容与受众重组，禁止照抄" if conf < 0.6
                     else "高置信命中：以该经验为基线，只做内容级调整")}


# ── DNA Schema v2：判断记忆，不是结果记忆 ──────────────────────────────
# 存「为什么这样设计」（可迁移的行为判断），不存「用了什么颜色/版式」（结果）。
# 结果记忆会让 AI 变模板（科技=蓝、金融=黑金）；判断记忆跨主题迁移。
# 色值与实测占比属于证据 → entry["proven"]；行为判断 → entry["judgment"]。
_RESULT_MEMORY_KEYS = {"palette", "color", "colors", "font", "fonts",
                       "image_style", "layout", "layout_result"}
_JUDGMENT_KEYS = {"hierarchy", "space", "media", "color_behavior",
                  "charts", "anchor_rule", "structure", "type_voice"}
_HEX_RE = None  # 惰性编译（模块导入零成本）


def _hex_re():
    global _HEX_RE
    if _HEX_RE is None:
        import re
        _HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    return _HEX_RE


def record_dna(entry: dict) -> dict:
    """发布 PASS 后沉淀设计经验（Schema v2 判断记忆；去重替换同 id 条目）。

    entry = {id, signature:{keywords:[...]},
             design_problem: str（这个场景的设计矛盾是什么）,
             judgment: {hierarchy|space|media|color_behavior|charts|
                        anchor_rule|structure|type_voice 中 ≥2 项},
             avoid: [...], when_not_to: str,
             proven: {qa, critic, revisions, project, measurements?}}
    拒收结果记忆：judgment 含 palette/font/版式结果字段或色值 → ok:False
    （色值与实测放 proven——判断进 judgment，证据进 proven）。
    只有真实发布过的经验才值得记忆——调用方应仅在上游校验 PASS 后调用。
    """
    store = _load_store()
    if not entry.get("id") or not entry.get("signature", {}).get("keywords"):
        return {"ok": False, "reason": "entry 需要 id 与 signature.keywords"}
    problem = entry.get("design_problem")
    if not isinstance(problem, str) or not problem.strip():
        return {"ok": False, "reason":
                "Schema v2 需要 design_problem（这个场景的设计矛盾是什么）——"
                "没有问题的判断是口号，不是经验"}
    judgment = entry.get("judgment")
    if not isinstance(judgment, dict) or len(set(judgment) & _JUDGMENT_KEYS) < 2:
        return {"ok": False, "reason":
                "Schema v2 需要 judgment（≥2 项：" + "/".join(sorted(_JUDGMENT_KEYS)) + "）"}
    bad = set(judgment) & _RESULT_MEMORY_KEYS
    if bad:
        return {"ok": False, "reason":
                f"judgment 含结果记忆字段 {sorted(bad)}：颜色/字体/版式结果会让 DNA "
                "变模板。可迁移的行为判断放 judgment，色值与实测放 proven"}
    for k, v in judgment.items():
        if isinstance(v, str):
            m = _hex_re().search(v)
            if m:
                return {"ok": False, "reason":
                        f"judgment.{k} 含色值 {m.group(0)}：色值是结果不是判断——"
                        "具体色随品牌/材质/语境派生，实测色值放 proven.measurements"}
    entries = [e for e in store.get("entries", []) if e.get("id") != entry["id"]]
    entries.append(entry)
    entries.sort(key=lambda e: str(e.get("id")))
    store["entries"] = entries
    store["version"] = store.get("version", 1)
    DNA_STORE.parent.mkdir(parents=True, exist_ok=True)
    DNA_STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    return {"ok": True, "store": str(DNA_STORE), "entries": len(entries)}


# ════════════════════════════════════════════════════════════════════════
# ② Media Decision Model
# ════════════════════════════════════════════════════════════════════════
_MEDIA_MODEL = {
    # family → (need, confidence, reason)
    "HERO": (True, 0.95, "开场页：品牌情绪建立，画心承担第一印象"),
    "CLOSING": (True, 0.90, "收尾页：情绪收束，画心承担记忆点"),
    "STORY": (True, 0.85, "叙事页：图像承担 context/emotion 功能"),
    "STATEMENT": (False, 0.30, "宣言页：留白与字阶就是视觉锚点，加图反而稀释"),
    "SECTION": (False, 0.25, "章节页：结构即节奏，安静是功能"),
    "DATA": (False, 0.05, "数据页：图表已是视觉锚点，再叠图 = 双焦点竞争"),
    "STRUCTURE": (False, 0.02, "结构页：结构关系比图像更清晰，出图必输"),
    "PROCESS": (False, 0.05, "流程页：步骤序列自带视觉性"),
    "COMPARISON": (False, 0.08, "对比页：左右张力来自内容本身"),
    "EVIDENCE": (False, 0.10, "证据页：数字与来源的可信度不需要装饰"),
}

# route 家族名 → 媒体模型家族（两套命名的一致层）
_FAMILY_ALIASES = {
    "COVER": "HERO", "DATA_STORY": "DATA", "MINIMAL_STATEMENT": "STATEMENT",
    "EDITORIAL": "STORY", "NARRATIVE": "STORY", "FRAMEWORK": "STRUCTURE",
    "EXECUTIVE_SUMMARY": "EVIDENCE", "EVIDENCE_FIELD": "EVIDENCE",
    "HERO_COVER": "HERO", "SECTION_DIVIDER": "SECTION",
}


def normalize_family(raw) -> str:
    """家族名归一（内容家族 COVER/DATA_STORY… → route/媒体家族 HERO/DATA…）。

    两套命名的单一映射源：media_decision / pre_critic / layout_search.recommend
    都经此归一，禁止各自维护别名表（漂移的别名表 = 判断不一致）。
    """
    up = str(raw or "").strip().upper()
    return _FAMILY_ALIASES.get(up, up)


def media_decision(page: dict) -> dict:
    """页面 → 媒体决策（置信度 + 理由，而非布尔闸门）。

    输入含 elements 时做覆盖判定：已有图表的页降为「图表即锚点」；
    已有 layer=background 画心时记「画心已承担」。"""
    raw = str((page.get("page_intent") or {}).get("page_family") or "").upper()
    family = normalize_family(raw)
    need, conf, reason = _MEDIA_MODEL.get(family, (False, 0.20, "未知家族：默认不出图（媒体需要理由）"))
    has_chart = any(isinstance(e, dict) and e.get("type") in ("chart", "native_chart")
                    for e in (page.get("elements") or []))
    has_bg = any(isinstance(e, dict) and e.get("layer") == "background"
                 for e in (page.get("elements") or []))
    if has_chart and need:
        need, conf = False, 0.08
        reason = "页内已有图表（视觉锚点被占用），再出图 = 双焦点竞争"
    elif has_chart:
        reason = "图表即视觉锚点，媒体预算应为 0"
    if has_bg:
        reason += "；背景画心已承担媒体职能（不计入预算但受免检资格约束）"
    return {"family": family or "UNKNOWN", "route_family": raw or None,
            "need_media": need, "confidence": conf, "reason": reason}


# ════════════════════════════════════════════════════════════════════════
# ③ Page Quality Budget
# ════════════════════════════════════════════════════════════════════════
QUALITY_BUDGETS = {
    "HERO": {"primary": ["emotional_impact", "memorability"],
             "complexity": "high", "media": "hero 画心允许",
             "aim": "第一印象与情绪定调——允许用复杂度换冲击力"},
    "CLOSING": {"primary": ["memorability", "emotional_impact"],
                "complexity": "low", "media": "情绪画心允许",
                "aim": "留一句可复述的话——越安静越有力"},
    "STATEMENT": {"primary": ["memorability", "visual_hierarchy"],
                  "complexity": "low", "media": "一般不需要",
                  "aim": "单一结论 + 尺度优势"},
    "DATA": {"primary": ["contrast", "alignment", "professional_quality"],
             "complexity": "medium", "media": "禁止",
             "aim": "清晰与准确优先——图表一个强调点，标签零碰撞"},
    "EVIDENCE": {"primary": ["professional_quality", "consistency"],
                 "complexity": "medium", "media": "禁止",
                 "aim": "证据链可信：来源/单位/口径齐全"},
    "STRUCTURE": {"primary": ["alignment", "visual_hierarchy"],
                  "complexity": "low", "media": "禁止",
                  "aim": "结构关系一眼可读"},
    "STORY": {"primary": ["emotional_impact", "consistency"],
              "complexity": "medium", "media": "叙事画心",
              "aim": "图像承担叙事，文字克制"},
    "SECTION": {"primary": ["rhythm", "balance"],
                "complexity": "low", "media": "不需要",
                "aim": "呼吸与转场——留白是功能"},
    "PROCESS": {"primary": ["alignment", "visual_hierarchy"],
                "complexity": "medium", "media": "禁止",
                "aim": "顺序与依赖清晰"},
    "COMPARISON": {"primary": ["balance", "contrast"],
                   "complexity": "medium", "media": "禁止",
                   "aim": "对比张力来自内容排布"},
}


def quality_budget(page: dict) -> dict:
    raw = str((page.get("page_intent") or {}).get("page_family") or "").upper()
    family = _FAMILY_ALIASES.get(raw, raw)
    b = dict(QUALITY_BUDGETS.get(family, {"primary": ["professional_quality"],
                                          "complexity": "medium", "media": "按需",
                                          "aim": "未声明家族：按通用标准"}))
    b["family"] = family or "UNKNOWN"
    b["route_family"] = raw or None
    return b


# ════════════════════════════════════════════════════════════════════════
# ④ Pre-Critic Engine
# ════════════════════════════════════════════════════════════════════════
def _theme_colors(spec: dict) -> dict:
    return dict(((spec.get("theme") or {}).get("colors") or {}))


def _hex_of(color: Any, colors: dict) -> str | None:
    if not isinstance(color, str):
        return None
    c = color.strip()
    if c.startswith("#"):
        return c
    return colors.get(c)          # token → hex


def _area(e: dict) -> float:
    try:
        return float(e.get("width", 0)) * float(e.get("height", 0))
    except (TypeError, ValueError):
        return 0.0


def _chart_accent_ratio(e: dict, colors: dict, cw: float, ch: float) -> float:
    """图表元素预估 accent 面积 / 画布面积（按物理形态校准的保守估计）。

    highlight 为 1-based 索引（与 charts 契约一致）；0/越界视为未声明。
    """
    kind = str(e.get("chart_kind") or e.get("kind") or "")
    area_ratio = _area(e) / max(1.0, cw * ch)
    hl = e.get("highlight")
    rows = e.get("data") or []
    vals = [abs(float(r.get("value"))) for r in rows
            if isinstance(r, dict) and isinstance(r.get("value"), (int, float))]
    hl_val = None
    if isinstance(hl, int) and 1 <= hl <= len(vals):
        hl_val = vals[hl - 1]
    if kind in ("donut", "donut_composition", "pie"):
        if hl_val is None:
            return 0.0                     # 未声明高亮：扇区走系列色，不计 accent
        sector = hl_val / (sum(vals) or 1.0)
        return area_ratio * 0.62 * sector
    if kind in _BAR_FAMILY:
        if hl_val is None or not vals:
            return 0.0
        return area_ratio * 0.07 * (hl_val / max(vals))
    return area_ratio * _SMALL_ACCENT.get(kind, 0.05)


def _accent_share(page: dict, colors: dict, cw: float, ch: float) -> float:
    accent_hex = (_hex_of("accent", colors) or "").upper()
    total = 0.0
    for e in (page.get("elements") or []):
        if not isinstance(e, dict):
            continue
        if e.get("layer") == "background":
            continue                       # 背景画心另行免检判定
        hexv = (_hex_of(e.get("color") or e.get("stroke"), colors) or "").upper()
        if e.get("type") in ("chart", "native_chart"):
            total += _chart_accent_ratio(e, colors, cw, ch)
        elif hexv and hexv == accent_hex:
            factor = _TEXT_INK_FACTOR if e.get("type") == "text" else _SHAPE_FILL_FACTOR
            total += _area(e) * factor / max(1.0, cw * ch)
    return total


def _est_overflow(e: dict) -> float | None:
    """文本元素预估溢出量（px）。无文本/无几何返回 None。"""
    text = e.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    for k in ("size", "width", "height"):
        if not isinstance(e.get(k), (int, float)):
            return None
    size = float(e["size"])
    lh = float(e.get("line_height") or 1.2)
    pad = float(e.get("padding") or 0)
    wrap = e.get("wrap") is not False
    lines = 0
    for seg in str(text).split("\n"):
        lines += estimate_lines(seg, float(e["width"]) - 2 * pad, size, wrap)
    need = lines * size * lh
    return need - (float(e["height"]) - 2 * pad)


def _risk(code, level, slides, why, prevention, predicted, cause, confidence):
    return {"code": code, "level": level, "slides": slides, "why": why,
            "prevention": prevention, "predicted": predicted,
            "root_cause": cause, "confidence": confidence}



# ── v2.12 预测扩展：把「渲染后才看得见」前移到生成前 ────────────────────
# gravity_drift 超标 / 字阶混乱 / 布局指纹连续重复 / 记忆线断裂——这四个失败
# 模式原来要等渲染证据才暴露；现在 spec 级静态估计就能点名（预测→决策→生成）。
LADDER_RUNGS = (64.0, 44.0, 32.0, 22.0, 17.0, 12.5)   # 驻点字阶（design-intelligence.md）
_LADDER_TOL = 2.0            # 驻点吸附容差（34 视作 32，避免 ±1px 噪声）
_TYPE_WEIGHTS = {"text": 1.0, "image": 1.2, "chart": 1.1,
                 "native_chart": 1.1, "shape": 0.7}
# 声明型页面（经 _FAMILY_ALIASES 含 COVER/MINIMAL_STATEMENT/SECTION_DIVIDER）
# 允许刻意偏轴——不对称是它们的语言，不是失衡
_ASYMMETRIC_OK = {"HERO", "CLOSING", "STATEMENT", "SECTION"}


def _weighted_centroid(elems: list[dict]):
    """墨量加权质心（文本 1.0 / 图 1.2 / 图表 1.1 / 形状 0.7；背景层不计）。"""
    wx = ws = 0.0
    for e in elems:
        try:
            w = _TYPE_WEIGHTS.get(str(e.get("type")), 0.8) \
                * float(e["width"]) * float(e["height"])
            wx += w * (float(e["x"]) + float(e["width"]) / 2.0)
            ws += w
        except (KeyError, TypeError, ValueError):
            continue
    return (wx / ws) if ws > 0 else None


def _layout_fingerprint(elems: list[dict]) -> tuple:
    """粗粒度布局指纹（类型 + 96px 网格桶）：识别「换字不换版」的连续重复。"""
    out = []
    for e in elems:
        try:
            out.append((str(e.get("type")), int(float(e.get("x", 0))) // 96,
                        int(float(e.get("y", 0))) // 96,
                        int(float(e.get("width", 0))) // 96,
                        int(float(e.get("height", 0))) // 96))
        except (TypeError, ValueError):
            continue
    return tuple(sorted(out))


# ── Page Intent Skeleton（v2.12）：标准家族的意图骨架，AI 只填洞 ──────────
# 生成速度的大头不是渲染（毫秒级），是每页重新推理。骨架把「家族决定得了的」
# （能量/密度/负空间职责/阅读序）确定性给出，AI 只填「内容决定得了的」
# （insight / focus）；显式覆盖永远赢。deck 级判断见 route.deck_decision。
INTENT_PRESETS = {
    "HERO": {"energy": "high", "density": "sparse", "empty_space_role": "hold_emotion"},
    "STATEMENT": {"energy": "high", "density": "sparse", "empty_space_role": "create_authority"},
    "SECTION": {"energy": "medium", "density": "sparse", "empty_space_role": "separate_chapter"},
    "DATA": {"energy": "medium", "density": "balanced", "empty_space_role": "protect_focus"},
    "EVIDENCE": {"energy": "medium", "density": "dense", "empty_space_role": "protect_focus"},
    "COMPARISON": {"energy": "medium", "density": "balanced", "empty_space_role": "separate_chapter"},
    "PROCESS": {"energy": "medium", "density": "balanced", "empty_space_role": "protect_focus"},
    "STRUCTURE": {"energy": "low", "density": "balanced", "empty_space_role": "separate_chapter"},
    "STORY": {"energy": "medium", "density": "balanced", "empty_space_role": "hold_emotion"},
    "CLOSING": {"energy": "high", "density": "sparse", "empty_space_role": "hold_emotion"},
}


def page_intent_skeleton(family: str, rhythm_stage: str = "body",
                         insight: str = "", focus: str | None = None,
                         **overrides) -> dict:
    """家族 → 页面意图骨架（确定性；insight/focus 由内容填，显式覆盖赢）。

    用法：skeleton = page_intent_skeleton("DATA_STORY", insight=…, focus="c1")，
    再按当前页内容覆写（如 CLOSING 页 energy="low" 做情绪收束）。
    未知家族给中性骨架（不猜）——家族判断本身是 Art Director 的职责。
    """
    fam = normalize_family(family)
    base = {"insight": insight, "focus": focus,
            "page_family": str(family or "").strip().upper(),
            "rhythm_stage": rhythm_stage}
    base.update(INTENT_PRESETS.get(fam, {"energy": "medium", "density": "balanced",
                                         "empty_space_role": "protect_focus"}))
    if focus:
        base["reading_order"] = [focus]
    base.update(overrides)     # 显式覆盖永远赢
    return base


def pre_critic(spec: dict) -> dict:
    """spec → 风险报告 + 生成策略（确定性，~10ms/页，零渲染零编译）。

    本函数是 **Design Intelligence 内部的预测子模块**，不是生产链上的独立审查
    环节：它的产物是「下一步该怎么设计」，不是「这一版能不能过」。因此
    ① 不阻断任何阶段（异常由调用方兜底）；② 与 Critic 的关系是时间差而非
    重复层——Critic 用真实渲染证据评「已经发生的」，本模块用几何/声明估计评
    「将要发生的」，同一套常量，跑在时间前面；③ 输出携带 `strategy`
    （`risk_strategy(spec, report)` 的结果），起草/修订时直接消费。

    每条风险：{code, level(high/med/low), slides, why, prevention,
    predicted(下游失败码), root_cause(与 Critic director_verdict 同分类法), confidence}。
    """
    t0 = time.time()
    colors = _theme_colors(spec)
    canvas = spec.get("canvas") or {}
    cw = float(canvas.get("width", DEFAULT_WIDTH))
    ch = float(canvas.get("height", DEFAULT_HEIGHT))
    accent_max = float((spec.get("theme") or {}).get("constraints", {}).get(
        "accent_max", 0.05)) or 0.05
    slides = spec.get("slides") or []
    risks: list[dict] = []
    pages_at_risk: set[str] = set()
    fps: list[tuple[str, tuple]] = []      # (页 id, 布局指纹)
    deck_sizes: set[float] = set()         # 全 deck 出现过的字号

    def _add(**kw):
        r = _risk(**kw)
        risks.append(r)
        pages_at_risk.update(str(s) for s in r["slides"])

    # ── 逐页预测 ─────────────────────────────────────────────────────
    prev = None
    for i, slide in enumerate(slides):
        sid = str(slide.get("id") or f"page_{i + 1}")
        elems = [e for e in (slide.get("elements") or []) if isinstance(e, dict)]
        pi = slide.get("page_intent") or {}

        # 1. accent 超载（V1 案例实录：donut 52% 扇区 6.7% > 4%）
        share = _accent_share(slide, colors, cw, ch)
        if share > accent_max:
            chart_kinds = [str(e.get("chart_kind")) for e in elems
                           if e.get("type") in ("chart", "native_chart")]
            cause = ("chart_selection" if chart_kinds else "color_discipline")
            prev_hint = (f"（构成图高亮扇区 ≈{share:.0%}——关系选错图表时，强调色必然超载："
                         f"改 ranked_bar/直接标注）" if chart_kinds else "（削减 accent 元素面积）")
            _add(code="ACCENT_OVERFLOW", level="high", slides=[sid],
                 why=f"预估 accent 像素 {share:.1%} > 主题上限 {accent_max:.0%}{prev_hint}",
                 prevention=("换图表（一图一关系：合计关系用 ranked_bar/大数字，构成关系才用环图）"
                             if cause == "chart_selection" else
                             "accent 只留一个元素；装饰回退主色/辅色"),
                 predicted="accent_budget", cause=cause, confidence=0.85)
        elif share > 0.8 * accent_max:
            _add(code="ACCENT_TIGHT_RISK", level="med", slides=[sid],
                 why=f"预估 accent 像素 {share:.1%} 已用预算 {share / accent_max:.0%}"
                     f"（上限 {accent_max:.0%}），渲染实测可能贴线",
                 prevention="accent 只留一个强调元素，其余回退主色/辅色——贴线值要留余量",
                 predicted="accent_budget(临界)", cause="color_discipline",
                 confidence=0.6)

        # 2. 记忆锚点缺失（V1 案例实录：s03/s06/s10 三页 CRITIC_LOW）
        if _memory_anchor(slide) is None:
            _add(code="NO_MEMORY_ANCHOR", level="high", slides=[sid],
                 why="全页无可指认记忆锚点（无 ≥40px 文本、无声明高亮/环心/目标线）",
                 prevention=("给焦点文字 ≥40px（Statement 级），或给图表声明 highlight/"
                             "center_value/target——真实存在的东西才可声明"),
                 predicted="CRITIC_LOW(memorability)", cause="memory_anchor",
                 confidence=0.9)

        # 3. 对比度风险（V1 案例实录：secondary 做 lead，纸底 2.98:1）
        bg = _hex_of("background", colors)
        worst = None
        for e in elems:
            if e.get("type") != "text":
                continue
            fg = _hex_of(e.get("color"), colors)
            if not fg or not bg:
                continue
            backing = bg
            # 文本压在实心形状上时以形状填充为底
            for s in elems:
                if s is e or s.get("type") not in ("shape",) or not s.get("fill"):
                    continue
                fill = s.get("fill") if isinstance(s.get("fill"), str) else \
                    (s.get("fill") or {}).get("color")
                if fill and _overlap(e, s):
                    bhex = _hex_of(fill, colors)
                    if bhex:
                        backing = bhex
            ratio = contrast(fg, backing)
            if worst is None or ratio < worst[1]:
                worst = (str(e.get("id")), ratio, float(e.get("size") or 16))
        if worst and worst[1] < 3.0:
            _add(code="CONTRAST_FAIL_RISK", level="high", slides=[sid],
                 why=f"「{worst[0]}」与底色预估对比 {worst[1]:.2f}:1 < 3.0:1 阻断线",
                 prevention="加深文字 token（如 secondary→muted/primary）或换更浅的底",
                 predicted="READABILITY_FAIL", cause="theme_contrast",
                 confidence=0.95)
        elif worst and worst[1] < 4.5 and worst[2] < 24:
            _add(code="CONTRAST_WARN_RISK", level="med", slides=[sid],
                 why=f"「{worst[0]}」{worst[2]:.0f}px 正文预估对比 {worst[1]:.2f}:1 < WCAG AA 4.5:1",
                 prevention="正文级文字用对比 ≥4.5:1 的 token（淡墨是装饰色不是可读色）",
                 predicted="text_contrast(warn)", cause="theme_contrast",
                 confidence=0.8)

        # 4. 焦点冲突（V1 案例实录：s10 主线图 378k > 25% 画布）
        focus_id = pi.get("focus")
        focus_el = next((e for e in elems if e.get("id") == focus_id), None)
        if focus_el is not None:
            fsize = focus_el.get("size") if focus_el.get("type") == "text" else None
            others = [float(e.get("size") or 0) for e in elems
                      if e is not focus_el and e.get("type") == "text"]
            if isinstance(fsize, (int, float)) and others and max(others) > 0 \
                    and fsize / max(others) < FOCUS_LEAD:
                _add(code="FOCUS_SCALE_RISK", level="med", slides=[sid],
                     why=f"焦点 {fsize:.0f}px 领先第二大文字 {fsize / max(others):.2f}× < {FOCUS_LEAD}×",
                     prevention="拉开尺度比（焦点 ≥1.25× 第二大文字）或降级竞争文字",
                     predicted="CRITIC_LOW(visual_hierarchy)", cause="focus_anchor",
                     confidence=0.85)
            for e in elems:
                if e is focus_el or e.get("layer") == "background":
                    continue
                if _area(e) > max(FOCUS_AREA_LEAD * _area(focus_el), 0.25 * cw * ch):
                    _add(code="FOCUS_AREA_RISK", level="high", slides=[sid],
                         why=f"「{e.get('id')}」面积 {_area(e) / 1000:.0f}k 超过 "
                             f"max(2×焦点, 25%画布)={max(FOCUS_AREA_LEAD * _area(focus_el), 0.25 * cw * ch) / 1000:.0f}k",
                         prevention="焦点做大（Statement 级）或收窄竞争对象；或焦点改声明真实锚点",
                         predicted="CRITIC_LOW(visual_hierarchy)", cause="focus_anchor",
                         confidence=0.9)

        # 5. 文本溢出（V1 案例实录：40px×1.15×2 行 = 92px > 64px 框）
        for e in elems:
            ov = _est_overflow(e)
            if ov is not None and ov > 1:
                _add(code="TEXT_OVERFLOW_RISK", level="high", slides=[sid],
                     why=f"「{e.get('id')}」预估高度超出文本框 {ov:.0f}px",
                     prevention=f"修复阶梯（优先级从上到下）：padding {e.get('padding', 0)}→0 → "
                                f"line_height {e.get('line_height', 1.2)}→1.05 → 字号降一级 → 重写文案拆行"
                                f"（声明 auto_fit:true 可由系统按此阶梯自动吸附）",
                     predicted="TEXT_OVERFLOW", cause="layout_collision",
                     confidence=0.95)

        # 6. 媒体误用
        md = media_decision(slide)
        images = [e for e in elems if e.get("type") == "image"]
        family = md["family"]
        if images and family in ("DATA", "STRUCTURE", "PROCESS", "COMPARISON", "EVIDENCE"):
            _add(code="MEDIA_MISUSE_RISK", level="high", slides=[sid],
                 why=f"{family} 页携带 {len(images)} 张图：{md['reason']}",
                 prevention="删除图片，或把页面改叙事/情绪定位（内容决定家族，家族决定媒体）",
                 predicted="MEDIA_UNJUSTIFIED", cause="media_governance",
                 confidence=0.9)
        elif len(images) > 1:
            _add(code="MEDIA_BUDGET_RISK", level="med", slides=[sid],
                 why=f"{len(images)} 张图 > 每页 1 个注意力媒体上限",
                 prevention="一页一锚点：保留功能最强的一张",
                 predicted="CRITIC_LOW(visual_hierarchy)", cause="media_governance",
                 confidence=0.8)

        # 7. 密度失配 + 8. 节奏趋平（V1 案例实录：Δ0.099 差 0.001 双扣）
        occ = _content_occupancy(elems, cw, ch)
        density = str(pi.get("density") or "").lower()
        band = DENSITY_BANDS.get(density)
        if band and not (band[0] - 0.06 <= occ <= band[1] + 0.10):
            _add(code="DENSITY_MISMATCH_RISK", level="med", slides=[sid],
                 why=f"声明 density={density}（带 {band[0]:.2f}–{band[1]:.2f}），"
                     f"几何占用估计 {occ:.2f} 在带外",
                 prevention="按真实占用重新声明，或调整内容量兑现声明（标签必须与现实一致）",
                 predicted="rhythm(空转/趋平)", cause="rhythm_density", confidence=0.6)
        if prev is not None:
            p_pi, p_occ = prev
            d_occ = abs(occ - p_occ)
            same_label = p_pi.get("density") == pi.get("density")
            both_same = same_label and p_pi.get("energy") == pi.get("energy")
            if same_label and d_occ < RHYTHM_INK_DELTA:
                level = "high" if both_same else "med"
                _add(code="RHYTHM_FLAT_RISK", level=level,
                     slides=[str(slides[i - 1].get("id")), sid],
                     why=f"相邻页同密度 {pi.get('density')}，占用差估计 {d_occ:.3f} < {RHYTHM_INK_DELTA}"
                         + ("，且能量相同（双重趋平）" if both_same else ""),
                     prevention="改动一页的密度/能量恢复呼吸；同密度相邻页需要真实墨迹差 ≥0.10"
                                "（宁可改声明为不同密度，也不虚增墨迹）",
                     predicted="RHYTHM_FLAT", cause="rhythm_density", confidence=0.55)
            elif not same_label and d_occ <= RHYTHM_INK_FLAT:
                _add(code="RHYTHM_FAKE_RISK", level="high",
                     slides=[str(slides[i - 1].get("id")), sid],
                     why=f"密度标签变了但占用差估计 {d_occ:.3f} ≤ {RHYTHM_INK_FLAT}（空转）",
                     prevention="标签变化必须伴随真实占用变化，否则视为空转扣分",
                     predicted="rhythm(空转)", cause="rhythm_density", confidence=0.55)
        # 9. 视觉平衡（v2.12：预测 gravity_drift——内容页墨量质心严重偏轴）
        vis = [e for e in elems if e.get("type") in _TYPE_WEIGHTS
               and e.get("layer") != "background" and e.get("role") != "background"]
        cx = _weighted_centroid(vis)
        if (cx is not None and len(vis) >= 2 and family not in _ASYMMETRIC_OK
                and abs(cx - cw / 2.0) > 0.18 * cw):
            _add(code="BALANCE_SKEW_RISK", level="med", slides=[sid],
                 why=f"墨量加权质心 x≈{cx:.0f}，偏离画布中轴 "
                     f"{abs(cx - cw / 2.0):.0f}px（>18% 画布宽）——视觉重量压在一侧",
                 prevention=("配平视觉重量（成组/加锚/镜像留白），或在 design_rationale "
                             "声明刻意偏轴的构图理由"),
                 predicted="gravity_drift", cause="balance_composition", confidence=0.5)

        # 10. 字阶纪律（v2.12：每页 ≤4 级；驻点 64/44/32/22/17/12.5）
        page_sizes = sorted({float(e["size"]) for e in elems
                             if e.get("type") == "text" and e.get("size")})
        if len(page_sizes) > 4:
            _add(code="TYPE_LADDER_RISK", level="med", slides=[sid],
                 why=f"本页 {len(page_sizes)} 个不同字号 {page_sizes}，超过每页 4 级上限",
                 prevention="并级：同层信息同字号，层次交给字重/墨色（驻点 64/44/32/22/17/12.5）",
                 predicted="CRITIC_LOW(typography)", cause="type_system", confidence=0.6)
        deck_sizes.update(page_sizes)
        fps.append((sid, _layout_fingerprint(elems)))

        prev = (pi, occ)

    # 11. 布局单调（v2.12）：连续 ≥3 页同布局指纹 = 换字不换版
    j = 0
    while j < len(fps):
        k = j
        while k + 1 < len(fps) and fps[k + 1][1] == fps[j][1] and fps[j][1]:
            k += 1
        if k - j >= 2 and fps[j][1]:
            _add(code="LAYOUT_MONOTONE_RISK", level="med",
                 slides=[fps[m][0] for m in range(j, k + 1)],
                 why=f"连续 {k - j + 1} 页布局指纹相同（换字不换版）——"
                     "读者会预判版式，注意力流失",
                 prevention="同根因批量换版式：相邻页至少改一个构图算子（切分/轴/尺度对偶）",
                 predicted="RHYTHM_FLAT", cause="layout_monotony", confidence=0.5)
        j = k + 1

    # 12. 记忆线断裂（v2.12）：token 只出现一次 = 线没有成线
    if len(slides) >= 4:
        token_pages: dict[str, list[str]] = {}
        for s in slides:
            tok = (s.get("page_intent") or {}).get("continuity_token")
            if tok:
                token_pages.setdefault(str(tok), []).append(str(s.get("id")))
        for tok, pages in token_pages.items():
            if len(pages) == 1:
                _add(code="CONTINUITY_BROKEN_RISK", level="med", slides=pages,
                     why=f"记忆线「{tok}」只在 1 页出现——单点不成线，读者无法当作导航线索",
                     prevention="让该线索在 ≥2 个关键位置复现（章节转场/收尾呼应），或撤掉声明",
                     predicted="CRITIC_LOW(narrative)", cause="narrative_continuity",
                     confidence=0.45)

    # 13. deck 级字阶漂移（v2.12）：全 deck 字号数失控
    if len(deck_sizes) > 8:
        off = sorted(s for s in deck_sizes
                     if all(abs(s - r) > _LADDER_TOL for r in LADDER_RUNGS))
        _add(code="TYPE_SCALE_DRIFT_RISK", level="med", slides=[],
             why=f"全 deck {len(deck_sizes)} 个不同字号（>8），字阶在漂移"
                 + (f"；其中 {len(off)} 个离驻点 >±{_LADDER_TOL:g}px" if off else ""),
             prevention="deck 级归并到驻点字阶（64/44/32/22/17/12.5），页内 ≤4 级；"
                        "字重与墨色先于字号",
             predicted="CRITIC_LOW(typography)", cause="type_system", confidence=0.45)

    by_cause: dict[str, list[str]] = {}
    for r in risks:
        by_cause.setdefault(r["root_cause"], []).append(r["code"])
    high = [r for r in risks if r["level"] == "high"]
    return {"risks": risks,
            "summary": {"high": len(high), "med": sum(1 for r in risks if r["level"] == "med"),
                        "low": 0, "pages_at_risk": len(pages_at_risk),
                        "total_pages": len(slides)},
            "by_root_cause": {k: sorted(set(v)) for k, v in sorted(by_cause.items())},
            "predicted_codes": sorted({r["predicted"] for r in high}),
            "pages_at_risk": sorted(pages_at_risk),
            "first_fix": ({"root_cause": high[0]["root_cause"],
                           "batch": [r["code"] for r in high
                                     if r["root_cause"] == high[0]["root_cause"]]}
                          if high else None),
            "elapsed_ms": int((time.time() - t0) * 1000)}


def forecast_risk(brief: dict) -> dict:
    """起草之前：brief → 风险预测（0–1 向量）→ 生成政策。

    这是「Risk Prediction 在 Design Intelligence 内部」的落点——不是生成前审核
    一次 spec，而是在**还没有 spec** 时就按内容路由预判该 deck 会在哪里出问题，
    并把结论变成预算：文本密度风险高 → 收紧 text_budget / 全局 auto_fit；
    图片不足风险高 → 提高 generate 预算；布局复杂风险高 → 降低并行构图算子。

    纯函数、零渲染、~0.1ms（复用 route 的决策缓存）。任何异常都返回「零风险 + 空政策」，
    绝不阻断生成（预测是加速器，不是门槛）。
    """
    out = {"risks": {}, "policies": {}, "notes": []}
    try:
        import route as _route
        plan = _route.plan_deck(brief if isinstance(brief, dict) else {})
    except Exception as exc:                       # 预测失败不阻断主链
        out["error"] = str(exc)
        out["notes"].append("route 不可用：跳过预测，按默认骨架起草")
        return out
    pages = plan.get("pages") or []
    n = max(1, len(pages))
    text_dense = sum(1 for p in pages
                     if str(p.get("density")) == "dense"
                     or int(p.get("text_budget") or 0) >= 4) / n
    media_short = sum(1 for p in pages
                      if str((p.get("asset") or {}).get("decision")) == "none") / n
    complex_layout = sum(1 for p in pages
                         if str(p.get("family")) in
                         ("FRAMEWORK", "COMPARISON", "TIMELINE", "NARRATIVE",
                          "PROCESS", "EXECUTIVE_SUMMARY")) / n
    mono = 0.0
    fams = [str(p.get("family")) for p in pages]
    streak = 1
    for i in range(1, len(fams)):
        streak = streak + 1 if fams[i] == fams[i - 1] else 1
        mono = max(mono, 1.0 if streak >= 3 else 0.0)
    flat = 0.0
    dens = [str(p.get("density")) for p in pages]
    for i in range(1, len(dens)):
        flat = max(flat, 0.8 if dens[i] == dens[i - 1] else 0.0)
    out["risks"] = {"hero_visual": round(min(1.0, media_short * 0.6 + 0.15), 3),
                    "text_density": round(min(1.0, text_dense), 3),
                    "media_shortage": round(min(1.0, media_short), 3),
                    "layout_complexity": round(min(1.0, complex_layout), 3),
                    "rhythm_flat": round(min(1.0, flat), 3),
                    "layout_monotony": round(mono, 3)}
    pol: dict[str, list[str]] = {}

    def _on(key, thr, *actions):
        if out["risks"][key] >= thr:
            pol.setdefault(key, []).extend(a for a in actions if a)

    _on("text_density", 0.34, "逐页 text_budget -1，正文统一声明 auto_fit:true",
        "行长上限收到 32 字（CJK），超出即拆句")
    _on("media_shortage", 0.5, "媒体政策：只在 cover/brand/product/closing 生成图片",
        "数据/结构页明确 zero-image，并把省下的预算换成锚点尺度")
    _on("hero_visual", 0.4, "含图页 ≤1 张且必须声明功能（context/emotion/proof/hero）")
    _on("layout_complexity", 0.4, "复杂家族一页只承担一个关系：优先分层/路径，放弃并列卡片",
        "构图算子先定（切分/轴/尺度对偶）再填内容")
    _on("rhythm_flat", 0.5, "疏密曲线重排：相邻页 density 互斥，能量至少一处随之变化")
    _on("layout_monotony", 0.99, "同家族连续 ≥3 页换构图语法，或在 design_rationale 声明品牌连续性")
    out["policies"] = pol
    out["planned_mode"] = (plan.get("execution") or {}).get("mode")
    out["notes"].append(f"{n} 页 · 预测来自内容路由（无渲染）；落 spec 后跑 pre_critic 复核")
    return out


# ════════════════════════════════════════════════════════════════════════
# ④b Risk → Strategy：把预测翻译成**生成策略**（vNext：预测层的出口是决策，不是审核）
#     原则：风险不是要「过一遍审核」，而是要在起草之前改掉生成参数。
#     纯函数、零改动 spec、零渲染；输出是给 AI 的决策块 + 可机读的逐页预算。
# ════════════════════════════════════════════════════════════════════════
_STRATEGY_BY_RISK = {
    # code → (策略键, 逐页动作, deck 级政策)
    "ACCENT_OVERFLOW": ("color_policy",
                        "本页 accent 只留 1 处（焦点数字或一个节点），其余回退主/辅色",
                        "accent_area_max 收紧一档，构成类关系改 ranked_bar/大数字"),
    "ACCENT_TIGHT_RISK": ("color_policy",
                          "贴线页把第二个强调元素改主色，留 20% 预算余量",
                          "accent_area_max 收紧一档"),
    "NO_MEMORY_ANCHOR": ("focus_anchor",
                         "焦点文字给到 ≥40px（Statement 级）或声明图表 highlight/center_value",
                         "每页至少一个可指认锚点，写进页面骨架"),
    "CONTRAST_FAIL_RISK": ("type_color_policy",
                           "把该文字 token 换成 primary/ink，或换更浅的底色",
                           "正文 token 只允许 ≥4.5:1 的组合（工程下限由 QA 兜底）"),
    "CONTRAST_WARN_RISK": ("type_color_policy",
                           "小字号正文改用对比 ≥4.5:1 的 token",
                           "淡墨只用于装饰与注释，不承担正文"),
    "FOCUS_SCALE_RISK": ("hierarchy_policy",
                         "拉开尺度比：焦点 ≥1.25× 第二大文字，或降级竞争文字",
                         "一页只允许一个层级顶点"),
    "FOCUS_AREA_RISK": ("hierarchy_policy",
                        "焦点做大或收窄竞争对象面积；焦点改声明真实锚点",
                        "媒体预算 ≤1/页，非焦点对象面积 ≤max(2×焦点,25%画布)"),
    "TEXT_OVERFLOW_RISK": ("text_policy",
                           "声明 auto_fit:true 让阶梯自动吸附，或先拆句/收窄版心",
                           "text_budget 收紧一档，行长上限 38 字（CJK）"),
    "MEDIA_MISUSE_RISK": ("media_policy",
                          "删除本页图片（数据/表格/流程/结构页不出图），或改叙事/情绪定位",
                          "媒体政策：图片只在 cover/brand/product/closing 生成"),
    "MEDIA_BUDGET_RISK": ("media_policy",
                          "一页一锚点：保留功能最强的一张图",
                          "每页注意力媒体 ≤1"),
    "DENSITY_MISMATCH_RISK": ("rhythm_policy",
                              "按真实占用重新声明 density（标签必须兑现）",
                              "疏密曲线重排：相邻页密度互斥"),
    "RHYTHM_FLAT_RISK": ("rhythm_policy",
                         "改动其中一页的内容量或留白，恢复呼吸",
                         "疏密曲线重排：相邻页密度互斥"),
    "RHYTHM_FAKE_RISK": ("rhythm_policy",
                         "标签变化必须伴随真实墨迹差 ≥0.10",
                         "疏密曲线重排：相邻页密度互斥"),
    "BALANCE_SKEW_RISK": ("composition_policy",
                          "配平视觉重量（成组/加锚/镜像留白），或在 design_rationale 写明刻意偏轴",
                          "构图算子：连续页至少换一个"),
    "TYPE_LADDER_RISK": ("type_policy",
                         "并级：同层信息同字号，层次交给字重/墨色",
                         "字阶锁在驻点 64/44/32/22/17/12.5，页内 ≤4 级"),
    "TYPE_SCALE_DRIFT_RISK": ("type_policy",
                              "全 deck 归并到驻点字阶",
                              "字阶锁在驻点，页内 ≤4 级"),
    "LAYOUT_MONOTONE_RISK": ("composition_policy",
                             "相邻页至少改一个构图算子（切分/轴/尺度对偶）",
                             "同家族连续 ≥3 页必须换构图语法或声明品牌连续性"),
    "CONTINUITY_BROKEN_RISK": ("continuity_policy",
                               "让该记忆线在 ≥2 个关键位置复现（章节转场/收尾呼应），或撤掉声明",
                               "记忆线成线：token 至少出现两次"),
}


def risk_strategy(spec: dict, report: dict | None = None) -> dict:
    """风险 → 生成策略（生成前消费的决策块；纯函数，不改 spec）。

    返回：
      adjusted      : 每条策略键的「当前值 → 建议值」，AI 起草/修订时直接采用
      pages         : 逐页调整清单（该页要改什么，为什么）
      generation    : 一句话生成指令（本轮起草的最小决策集）
      risk_scores   : 归一化风险向量（0–1，供对比不同方向/候选骨架）
      predicted     : 若不调整将命中的下游失败码（QA/Critic 侧）
    """
    report = report or pre_critic(spec)
    slides = [s for s in (spec.get("slides") or []) if isinstance(s, dict)]
    ids = [str(s.get("id") or f"page_{i + 1}") for i, s in enumerate(slides)]
    by_page: dict[str, list[dict]] = {sid: [] for sid in ids}
    policies: dict[str, dict] = {}
    predicted: set[str] = set()
    per_page_score: dict[str, float] = {sid: 0.0 for sid in ids}
    for r in report.get("risks") or []:
        weight = {"high": 1.0, "med": 0.5, "low": 0.25}.get(r.get("level"), 0.25)
        hit = [s for s in (r.get("slides") or []) if str(s) in by_page] or ids
        for sid in hit:
            by_page[sid].append(r)
            per_page_score[sid] += weight
        if r.get("predicted"):
            predicted.add(str(r["predicted"]).split("(")[0])
        key, page_action, deck_policy = _STRATEGY_BY_RISK.get(
            str(r.get("code")), ("general_policy", str(r.get("prevention") or ""), ""))
        slot = policies.setdefault(key, {"risk": str(r.get("code")), "page_actions": [],
                                         "deck_policies": []})
        if page_action and page_action not in slot["page_actions"]:
            slot["page_actions"].append(page_action)
        if deck_policy and deck_policy not in slot["deck_policies"]:
            slot["deck_policies"].append(deck_policy)

    n = max(1, len(ids))
    top_score = max(list(per_page_score.values()) + [0.0])
    pages = [{"slide": sid, "risk_weight": round(per_page_score[sid], 2),
              "risks": sorted({str(r.get("code")) for r in by_page[sid]}),
              "fix_first": (by_page[sid][0].get("prevention") if by_page[sid] else None)}
             for sid in ids if by_page[sid]]
    order = {"color_policy": 0, "text_policy": 1, "type_policy": 2, "media_policy": 3,
             "hierarchy_policy": 4, "focus_anchor": 5, "rhythm_policy": 6,
             "composition_policy": 7, "type_color_policy": 8, "continuity_policy": 9,
             "general_policy": 99}
    adjusted = {k: policies[k] for k in sorted(policies, key=lambda x: (order.get(x, 98), x))}
    summary = report.get("summary") or {}
    first = summary.get("high", 0)
    generation = (
        "按策略起草，不要先出稿再等检查：" + "；".join(
            f"{k}→{'、'.join(v['deck_policies'])}" for k, v in adjusted.items()
            if v["deck_policies"])[:600]
        if adjusted else "无预测风险：按页面骨架直接起草，一次通过")
    return {"adjusted": adjusted, "pages": pages,
            "generation": generation,
            "risk_scores": {sid: round(v / max(1e-6, top_score), 3)
                            for sid, v in per_page_score.items() if v},
            "predicted": sorted(predicted),
            "applied_before": "spec 起草/修订（不是渲染前的审核闸）",
            "summary": {"policies": len(adjusted), "pages_adjusted": len(pages),
                        "high": first, "total_pages": n}}



def _overlap(a: dict, b: dict) -> bool:
    try:
        return (float(a["x"]) < float(b["x"]) + float(b["width"])
                and float(b["x"]) < float(a["x"]) + float(a["width"])
                and float(a["y"]) < float(b["y"]) + float(b["height"])
                and float(b["y"]) < float(a["y"]) + float(a["height"]))
    except (KeyError, TypeError, ValueError):
        return False


# ════════════════════════════════════════════════════════════════════════
# Smart Fit Resolver（auto_fit 光学阶梯：显式 opt-in，永不默认）
# ════════════════════════════════════════════════════════════════════════
def apply_fit_ladder(spec: dict) -> tuple[dict, dict]:
    """对声明 auto_fit:true 且预估溢出的文本，按阶梯吸附（纯函数，留痕）。

    阶梯（与生产契约一致——缩字号是最后手段）：
        ① padding → 0   ② line_height → 1.05   ③ 字号 -2px 递降至 12px 下限
    仍溢出 → 记 needs_rewrite（文案级问题，机器不再退让）。
    未声明 auto_fit 的元素零改动（编译器仍只警告不修改——本函数是 spec 层的
    显式授权，不是编译器行为）。
    """
    import copy
    out = copy.deepcopy(spec)
    items: list[dict] = []
    for slide in (out.get("slides") or []):
        for e in (slide.get("elements") or []):
            if not isinstance(e, dict) or e.get("auto_fit") is not True:
                continue
            sid = slide.get("id")
            steps = []
            ov = _est_overflow(e)
            if ov is None or ov <= 1:
                continue
            if e.get("padding"):
                steps.append(f"padding {e['padding']}→0")
                e["padding"] = 0
            if _est_overflow(e) > 1 and float(e.get("line_height") or 1.2) > 1.05:
                steps.append(f"line_height {e['line_height']}→1.05")
                e["line_height"] = 1.05
            while _est_overflow(e) > 1 and float(e.get("size") or 16) > 12:
                e["size"] = float(e["size"]) - 2
                steps.append(f"size →{e['size']:.0f}")
            needs_rewrite = _est_overflow(e) > 1
            items.append({"slide": sid, "id": e.get("id"), "steps": steps,
                          "needs_rewrite": needs_rewrite})
    report = {"applied": len(items), "items": items,
              "needs_rewrite": [i["id"] for i in items if i["needs_rewrite"]]}
    return out, report


# ════════════════════════════════════════════════════════════════════════
# Parallel Intelligence：一次调用汇合三条智能线
# ════════════════════════════════════════════════════════════════════════
def analyze(brief: dict, spec: dict | None = None) -> dict:
    """内容线（brief）/ 视觉线（DNA）/ 风险线（预测 + 策略）单次汇合。

    Parallel Intelligence：三条判断互不依赖——不要「P1 完成才 P2、P2 完成才 P3」
    的串行等待。**spec 起草之前**就该拿到 `strategy`：无 spec 时用 `risk_strategy`
    的同类目（媒体/字阶/构图政策）从 brief 直接推导，有 spec 时按真实几何预测。
    """
    out = {"dna": recall_dna(brief)}
    if spec:
        rep = pre_critic(spec)
        out["pre_critic"] = rep
        out["strategy"] = risk_strategy(spec, rep)
        out["media"] = [{"slide": s.get("id"), **media_decision(s)}
                        for s in (spec.get("slides") or []) if isinstance(s, dict)]
        out["budgets"] = [{"slide": s.get("id"), **quality_budget(s)}
                          for s in (spec.get("slides") or []) if isinstance(s, dict)]
    else:
        out["forecast"] = forecast_risk(brief or {})
        out["note"] = ("spec 未提供：先按 forecast 的风险政策起草"
                       "（media/hierarchy/rhythm/typography 四条先定，再落 spec），"
                       "落稿后跑 analyze(brief, spec) 拿逐页预测与策略")
    return out


# ── CLI：python design_intelligence.py <build_module.py> [--dna|--risks|--analyze] ──
def main(argv):
    import importlib.util
    if len(argv) < 2:
        print("usage: python design_intelligence.py <build_module.py> "
              "[--forecast|--risks|--analyze|--record-dna id]")
        return 1
    mod_path = Path(argv[1])
    spec_mod = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    mod = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    if spec is None:
        print("build module must define build_spec() or SPEC")
        return 1
    if "--forecast" in argv:
        brief = getattr(mod, "BRIEF", {}) or {}
        fc = forecast_risk(brief if isinstance(brief, dict) else {})
        print(json.dumps(fc, ensure_ascii=False, indent=2))
        return 0
    if "--json" not in argv:
        # 摘要输出：风险 + 生成策略（策略先读，风险单是清单）
        rep = pre_critic(spec)
        strat = risk_strategy(spec, rep)
        s = rep["summary"]
        print(f"risk-prediction: {s['high']} high / {s['med']} med · "
              f"{s['pages_at_risk']}/{s['total_pages']} 页有风险 · {rep['elapsed_ms']}ms")
        for key, val in strat["adjusted"].items():
            for d in val["deck_policies"]:
                print(f"  [{key}] 政策 → {d}")
        for r in rep["risks"]:
            if r["level"] == "high":
                pages = "、".join(r["slides"])
                print(f"  [{r['code']:22s}] {pages}: {r['why']}")
                print(f"      prevent → {r['prevention'][:90]}")
        if not rep["risks"]:
            print("  ✓ 无可预测风险——按当前 spec 大概率一次通过")
        return 0
    print(json.dumps(analyze({}, spec), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))


# ════════════════════════════════════════════════════════════════════
# 参考空间律（Calibration Laws · 判断阈值，不是模板）
#
# 这些「带与律」原先来自外部实测存储（一个校准数据文件 + 一个测量脚本），
# 两者都不在本包内 —— 一个引用不到的证据文件只是装饰，还会让自检/文档
# 出现悬空指针。vNext 把律**内联为常量**：
# 判断阈值直接可读、可改、可核对，不再有第二套缓存/迁移层。
# 想恢复实测闭环：把测量结果写进 memory/calibration_space.json 即可被
# `calibration_laws()` 覆盖（文件存在才读；不存在零成本、零告警）。
# ════════════════════════════════════════════════════════════════════
CALIBRATION_LAWS = {
    "area_ratio": {"c1": 0.55, "c1_band": (0.35, 0.85), "c2": 0.21,
                   "c3": 0.11, "c4": 0.06},
    "hue_families_page_max": 1,          # 页级（主题级宽一档 → 2）
    "sat90": {"quiet_max": 0.35, "warm_material_max": 0.65},
    "brightness_regimes": {"dark": (0.05, 0.35), "light": (0.55, 0.97)},
    "negative_space_text_led": (0.40, 1.0),
    "photo_share": (0.18, 0.60),
    "type_edge_density": (0.016, 0.053),
}
CALIBRATION_FAMILIES: dict[str, dict] = {}
CALIBRATION_STORE = Path(__file__).resolve().parent.parent / "memory" / "calibration_space.json"
_CAL_CACHE: dict | None = None


def _load_calibration() -> dict:
    """可选覆盖：文件存在才读（不存在 = 用内联律，不是缺失、不报错）。"""
    global _CAL_CACHE
    if _CAL_CACHE is None:
        try:
            _CAL_CACHE = json.loads(CALIBRATION_STORE.read_text(encoding="utf-8"))
        except Exception:
            _CAL_CACHE = {}
    return _CAL_CACHE


def calibration_laws(family: str | None = None) -> dict:
    """全局律（内联常量）+ 可选家族带（来自可选覆盖文件）。

    家族带是证据（p10/p50/p90），不是目标模板；缺失时按全局律判读。
    """
    cal = _load_calibration()
    laws = dict(CALIBRATION_LAWS)
    laws.update({k: v for k, v in (cal.get("laws") or {}).items() if v is not None})
    fams = dict(CALIBRATION_FAMILIES)
    fams.update(cal.get("families") or {})
    if family and fams.get(family):
        laws["family_bands"] = fams[family]
        laws.update({k: v for k, v in fams[family].items() if k not in laws})
    laws["family_personality"] = fams
    laws["source"] = "inline" if not cal else "inline+override"
    return laws



# ── Adaptive Color Intelligence Engine ───────────────────────────────
# 方向 = 行为 + 材质/光性语言 + 种子骨架；种子只是兜底骨架，
# brand_colors 永远优先，visual_world 的材质判断永远优先于方向预设。
COLOR_RATIO_TARGETS = {"foundation": 0.70, "supporting": 0.20,
                       "information": 0.08, "accent": 0.02}
COLOR_FORBIDDEN = ("high-saturation gradients", "SaaS blue-purple",
                   "colorful card walls", "cheap tech glow", "rainbow palette")
COLOR_DIRECTIONS = {
    "luxury_editorial": dict(regime="light", sat="quiet", motion=("spatial",),
        texture=("luxury", "architecture"),
        material="warm ivory paper, travertine and bronze, soft window light",
        seed={"foundation": "#F2EDE4", "supporting": "#9A8C74", "information": "#403B32", "accent": "#9C5A2E"}),
    "song_elegance": dict(regime="light", sat="quiet", motion=("natural",),
        texture=("eastern",),
        material="rice paper, ink stone, tea-green silk, diffuse north light",
        seed={"foundation": "#F3F1EA", "supporting": "#8B8D84", "information": "#22241F", "accent": "#5E7562"}),
    "zen_minimal": dict(regime="light", sat="quiet", motion=("natural",),
        texture=("eastern",),
        material="handmade paper, mist, still water, shadowless light",
        seed={"foundation": "#F5F4F1", "supporting": "#9A9A96", "information": "#1E1E1C", "accent": "#6E6E6A"}),
    "nordic_quiet": dict(regime="light", sat="quiet", motion=("spatial",),
        texture=("architecture",),
        material="lime plaster, pale oak, ceramic, low winter sun",
        seed={"foundation": "#EFECE6", "supporting": "#A79E90", "information": "#33302B", "accent": "#8A7A5F"}),
    "quiet_luxury": dict(regime="light", sat="quiet", motion=("spatial",),
        texture=("luxury",),
        material="champagne metal hairline, taupe stone, sea light through sheer curtain",
        seed={"foundation": "#F1EDE6", "supporting": "#A99878", "information": "#37322A", "accent": "#B08D4F"}),
    "monochrome_noir": dict(regime="dark", sat="quiet", motion=("spatial",),
        texture=("architecture",),
        material="black stone, single raking light shaft, graphite dust",
        seed={"foundation": "#101010", "supporting": "#4A4A4A", "information": "#F2F2F0", "accent": "#8C8C8C"}),
    "cinematic_narrative": dict(regime="dark", sat="warm", motion=("spatial", "natural"),
        texture=("luxury", "architecture"),
        material="amber dusk, coastal air, brass light, deep shadow",
        seed={"foundation": "#141210", "supporting": "#5C4A33", "information": "#EFE3CE", "accent": "#C08A3E"}),
    "nature_luxury": dict(regime="dark", sat="quiet", motion=("natural", "spatial"),
        texture=("organic", "architecture"),
        material="deep forest green, mist over water, wet stone, cold diffuse light",
        seed={"foundation": "#16211C", "supporting": "#4E6157", "information": "#EDEFE9", "accent": "#6FA08C"}),
    "organic_systems": dict(regime="light", sat="quiet", motion=("natural",),
        texture=("organic",),
        material="oat fiber, leaf vein macro, sage clay, soft top light",
        seed={"foundation": "#EFEBE2", "supporting": "#A8A394", "information": "#3B3A33", "accent": "#7C8B6F"}),
    "precision_tech": dict(regime="mixed", sat="quiet", motion=("tech",),
        texture=("technology",),
        material="optical glass, titanium edge, controlled blue signal on graphite",
        seed={"foundation": "#0D0F12", "supporting": "#3A4148", "information": "#F2F4F6", "accent": "#2E7BD6"}),
    "apple_future": dict(regime="light", sat="quiet", motion=("tech", "spatial"),
        texture=("technology",),
        material="titanium micro-brush, mist white stage, single product light",
        seed={"foundation": "#F6F6F7", "supporting": "#9BA0A6", "information": "#1D1D1F", "accent": "#0071E3"}),
    "data_intelligence": dict(regime="dark", sat="quiet", motion=("tech",),
        texture=("technology",),
        material="dark graphite evidence field, steel gray structure, one controlled accent",
        seed={"foundation": "#141619", "supporting": "#454B52", "information": "#EDEFF1", "accent": "#3E8E7E"}),
    "editorial_intelligence": dict(regime="light", sat="quiet", motion=("spatial",),
        texture=("eastern",),
        material="newsprint white, ink black, one signal red, hard magazine grid",
        seed={"foundation": "#F7F6F3", "supporting": "#8E8E8C", "information": "#141414", "accent": "#C8102E"}),
}


_DIRECTION_ALIAS = {"quiet_minimal": "zen_minimal",
                    "editorial_brand": "luxury_editorial",
                    "product_stage": "apple_future",
                    "evidence_first": "data_intelligence"}


def color_plan(direction, brief: dict | None = None) -> dict:
    """自适应色彩智能：内容 × DNA × 情绪 → 比例目标 + 约束 + 种子骨架。

    派生顺序（判断，不是模板）：brand_colors > visual_world 材质/光性 >
    方向种子骨架。返回的约束来自参考空间实测律（色相族/饱和/明度域）。
    """
    brief = brief or {}
    fam = str(brief.get("color_family") or "")
    if not fam:
        raw = direction if isinstance(direction, str) else str(
            (direction or {}).get("family") or (direction or {}).get("design_direction") or "")
        fam = _DIRECTION_ALIAS.get(raw, raw)
    entry = COLOR_DIRECTIONS.get(fam) or COLOR_DIRECTIONS["quiet_luxury"]
    fam_key = fam if fam in COLOR_DIRECTIONS else "quiet_luxury"
    brief = brief or {}
    laws = calibration_laws(fam_key)
    personality = ((laws.get("family_personality") or {}).get(fam_key) or {})
    sat_cap = (laws.get("sat90") or {})
    brief = brief or {}
    brand = brief.get("brand_colors") or {}
    seed = dict(entry["seed"])
    seed_source = "family_seed"
    if isinstance(brand, dict) and brand:
        keys = ("foundation", "supporting", "information", "accent")
        vals = [v for v in brand.values() if isinstance(v, str)]
        for k, v in zip(keys, vals):
            seed[k] = v
        seed_source = "brand_colors"
    return {
        "family": fam_key,
        "ratio_targets": dict(COLOR_RATIO_TARGETS),
        "constraints": {
            "hue_families_page_max": laws.get("hue_families_page_max", 1),
            "sat90_max": sat_cap.get("warm_material_max", 0.65)
            if (personality.get("sat_class") or entry["sat"]) == "warm"
            else sat_cap.get("quiet_max", 0.35),
            "accent_area_max": 0.05,
            "brightness_regime": entry["regime"],
            "brightness_band": (laws.get("brightness_regimes") or {}).get(entry["regime"]),
        },
        "seed_skeleton": seed,
        "seed_source": seed_source,
        "material_language": entry["material"],
        "motion_keys": list(entry["motion"]),
        "texture_keys": list(entry["texture"]),
        "forbidden": list(COLOR_FORBIDDEN),
        "derivation": "brand_colors > visual_world material/light > family seed skeleton; "
                      "ratios follow measured area law (foundation c1 p50≈0.55, accent≤8%)",
    }


# ── Visual Calibration Score（静态，~1ms：生成即知是否达参考空间水准）──
_CAL_WEIGHTS = {"layout": 0.25, "typography": 0.20, "color": 0.20,
                "image": 0.15, "information": 0.20}


def _hue_family_of_hex(hexstr: str) -> int | None:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", hexstr or "")
    if not m:
        return None
    r, g, b = (int(m.group(1)[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    mx, mn = max(r, g, b), min(r, g, b)
    if mx <= 0.15 or (mx - mn) / max(mx, 1e-6) < 0.10:
        return None
    d = mx - mn or 1e-6
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return int(h * 60 // 30)


def _line_measure(text: str, lines: int) -> float:
    cjk = sum(1 for ch in text if ord(ch) > 0x2E7F)
    latin = len(text) - cjk
    return (cjk + latin / 2.0) / max(1, lines)


def visual_calibration_score(spec: dict, family: str | None = None) -> dict:
    """五维静态校准分（layout/typography/color/image/information，各 0–5）。

    对照参考空间实测律：密度声明兑现与相邻差、字阶驻点与行长、
    色相族/色彩职责、媒体闸门一致性、信息合同完整性。零渲染零编译。
    """
    t0 = time.time()
    laws = calibration_laws(family)
    slides = spec.get("slides") or []
    theme = spec.get("theme") or {}
    colors = theme.get("colors") or {}
    notes: list[str] = []
    n = max(1, len(slides))

    # layout：密度声明 vs 几何带；相邻同标签需真实几何差
    ok, prev = 0, None
    for s in slides:
        occ = _content_occupancy(s.get("elements") or [], DEFAULT_WIDTH, DEFAULT_HEIGHT)
        band = DENSITY_BANDS.get(str((s.get("page_intent") or {}).get("density") or ""))
        hit = bool(band) and band[0] <= occ <= band[1]
        if hit:
            ok += 1
        else:
            notes.append(f"layout: {(s.get('id') or '?')} 声明密度与几何占用不兑现")
        if prev is not None and abs(occ - prev) < 0.10:
            notes.append(f"layout: {(s.get('id') or '?')} 与上一页几何差 <0.10（节奏趋平风险）")
        prev = occ
    layout = 5.0 * ok / n - (0.5 if any("节奏" in x for x in notes) else 0.0)

    # typography：驻点 / 每页级数 / deck 级数 / 行长
    deck_sizes: set[float] = set()
    ty_ok = 0
    for s in slides:
        sizes = [round(float(e.get("size")), 1) for e in s.get("elements") or []
                 if e.get("type") == "text" and e.get("size") is not None]
        deck_sizes.update(sizes)
        off = [z for z in sizes if all(abs(z - r) > _LADDER_TOL for r in LADDER_RUNGS)]
        page_ok = (len(set(sizes)) <= 4 and not off)
        for e in s.get("elements") or []:
            if e.get("type") != "text" or not e.get("text"):
                continue
            lines = int(e.get("max_lines") or 1)
            if _line_measure(str(e["text"]), lines) > 38:
                page_ok = False
                notes.append(f"typography: {(e.get('id') or '?')} 行长 >38（拆句或收窄版心）")
        if page_ok:
            ty_ok += 1
    off_deck = [z for z in deck_sizes if all(abs(z - r) > _LADDER_TOL for r in LADDER_RUNGS)]
    typography = 5.0 * ty_ok / n
    if len(deck_sizes) > 6 or off_deck:
        typography -= 1.0
        notes.append("typography: 全 deck 字阶 >6 级或存在离驻点字号")

    # color：色相族 / 色彩职责声明 / accent 约束
    fams = {f for v in colors.values() if isinstance(v, str)
            for f in [_hue_family_of_hex(v)] if f is not None}
    color = 5.0
    page_max = int(laws.get("hue_families_page_max", 1)) + 1  # 主题级比页级宽一档
    if len(fams) > max(2, page_max):
        color -= 2.0
        notes.append(f"color: 主题色相族 {len(fams)} > 参考空间律")
    elif len(fams) > 2:
        color -= 1.0
    if not (theme.get("color_intent") or (spec.get("direction") or {}).get("color_intent")):
        color -= 1.0
        notes.append("color: 未声明 color_intent（brand/emotion/hierarchy 优先职责）")
    if float((theme.get("constraints") or {}).get("accent_max", 0.05)) > 0.05:
        color -= 1.0
        notes.append("color: accent 面积约束 >5%")

    # image：媒体闸门一致性（数据/表格/流程/结构页不得有图；有图须有功能/层资格）
    im_ok, im_pages = 0, 0
    for s in slides:
        imgs = [e for e in s.get("elements") or [] if e.get("type") == "image"]
        if not imgs:
            continue
        im_pages += 1
        dec = media_decision(s)
        good = dec.get("decision") not in ("none", None) or any(
            str(e.get("layer")) == "background" for e in imgs)
        if good and all(e.get("function") or e.get("layer") for e in imgs):
            im_ok += 1
        else:
            notes.append(f"image: {(s.get('id') or '?')} 图片缺功能/层资格或所在家族不应出图")
    image = 5.0 if not im_pages else 5.0 * im_ok / im_pages

    # information：insight / focus / source_zone / 叙事行数
    info_ok = 0
    for s in slides:
        intent = s.get("page_intent") or {}
        lines = sum(int(e.get("max_lines") or 1) for e in s.get("elements") or []
                    if e.get("type") == "text" and str(e.get("role") or "") not in
                    {"source", "method", "annotation", "axis", "label", "data_label",
                     "legend", "metadata"})
        good = bool(intent.get("insight")) and bool(intent.get("focus")) \
            and isinstance(s.get("source_zone"), dict) and lines <= 6
        if good:
            info_ok += 1
        else:
            notes.append(f"information: {(s.get('id') or '?')} 信息合同缺口"
                         "（insight/focus/source_zone/行数）")
    information = 5.0 * info_ok / n

    dims = {k: round(max(0.0, min(5.0, v)), 1) for k, v in
            (("layout", layout), ("typography", typography), ("color", color),
             ("image", image), ("information", information))}
    score = round(20.0 * sum(dims[k] * w for k, w in _CAL_WEIGHTS.items()), 1)
    return {"score": score, "dims": dims, "notes": notes[:12],
            "family": family, "laws_used": {
                "hue_families_page_max": laws.get("hue_families_page_max"),
                "area_ratio": laws.get("area_ratio"),
                "photo_share": laws.get("photo_share"),
                "source": laws.get("source")},
            "elapsed_ms": round((time.time() - t0) * 1000, 2)}
