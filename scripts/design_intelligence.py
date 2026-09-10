# -*- coding: utf-8 -*-
"""
Layer -1 · Design Intelligence（V3 · 设计智能层——所有流程的大脑）

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
  ④ Pre-Critic Engine    生成前风险预测：用与 Critic/QA 同一套常量，在渲染之前
                          估计 accent 超载、锚点缺失、对比度、焦点冲突、文本溢出、
                          节奏趋平、密度失配、媒体误用——每条风险标注根因（与 V2
                          Revision Batch Intelligence 同一分类法），修正建议直连
                          「1 根因 = 1 轮」。

analyze(brief, spec) 把三条智能线（内容/视觉/风险）汇合成一次调用——对应 V3 的
Parallel Intelligence：内容分析、视觉分析、风险分析互不依赖，无需串行等待。

与既有层的关系：Normalizer 吸附机械偏差（无判断），Guard 确认合同（当前事实），
Pre-Critic 预测下游失败（未来风险）——三者互补，阈值全部同源于
art_critic.py / qa.py 导出常量：V3 只加预测，不改任何判定标准。
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
            "dna": best.get("dna"), "alternatives": alts,
            "proven": best.get("proven"),
            "note": ("DNA 是起点不是模板：按当前内容与受众重组，禁止照抄" if conf < 0.6
                     else "高置信命中：以该经验为基线，只做内容级调整")}


def record_dna(entry: dict) -> dict:
    """发布 PASS 后沉淀设计经验（去重替换同 id 条目）。

    entry = {id, signature:{keywords:[...]}, dna:{...}, proven:{qa, critic, revisions, project}}
    只有真实发布过的经验才值得记忆——调用方应仅在上游校验 PASS 后调用。
    """
    store = _load_store()
    if not entry.get("id") or not entry.get("signature", {}).get("keywords"):
        return {"ok": False, "reason": "entry 需要 id 与 signature.keywords"}
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


def media_decision(page: dict) -> dict:
    """页面 → 媒体决策（置信度 + 理由，而非布尔闸门）。

    输入含 elements 时做覆盖判定：已有图表的页降为「图表即锚点」；
    已有 layer=background 画心时记「画心已承担」。"""
    raw = str((page.get("page_intent") or {}).get("page_family") or "").upper()
    family = _FAMILY_ALIASES.get(raw, raw)
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



def pre_critic(spec: dict) -> dict:
    """spec → 生成前风险报告（确定性，~10ms/页，零渲染零编译）。

    每条风险：{code, level(high/med/low), slides, why, prevention,
    predicted(下游失败码), root_cause(与 V2 批量修订同分类法), confidence}。
    与 Critic 的关系：Critic 用真实渲染证据评「已经发生的」；Pre-Critic 用几何/
    声明估计评「将要发生的」——同一套常量，跑在时间前面。
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
        prev = (pi, occ)

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
    """内容线（brief）/ 视觉线（DNA）/ 风险线（Pre-Critic）单次汇合。

    对应 V3 Parallel Intelligence：三条判断互不依赖——不再「P1 完成才 P2、
    P2 完成才 P3」的串行等待；spec 已存在时风险线立即运行，否则返回 DNA+
    媒体模型供 spec 起草（起草后再跑一次 analyze 拿风险报告）。
    """
    out = {"dna": recall_dna(brief)}
    if spec:
        out["pre_critic"] = pre_critic(spec)
        out["media"] = [{"slide": s.get("id"), **media_decision(s)}
                        for s in (spec.get("slides") or []) if isinstance(s, dict)]
        out["budgets"] = [{"slide": s.get("id"), **quality_budget(s)}
                          for s in (spec.get("slides") or []) if isinstance(s, dict)]
    else:
        out["note"] = "spec 未提供：先用 dna + brief 起草，再跑 analyze(brief, spec) 拿风险报告"
    return out


# ── CLI：python design_intelligence.py <build_module.py> [--dna|--risks|--analyze] ──
def main(argv):
    import importlib.util
    if len(argv) < 2:
        print("usage: python design_intelligence.py <build_module.py> "
              "[--risks|--analyze|--record-dna id]")
        return 1
    mod_path = Path(argv[1])
    spec_mod = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    mod = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    if spec is None:
        print("build module must define build_spec() or SPEC")
        return 1
    if "--json" not in argv:
        # 摘要输出
        rep = pre_critic(spec)
        s = rep["summary"]
        print(f"pre-critic: {s['high']} high / {s['med']} med · "
              f"{s['pages_at_risk']}/{s['total_pages']} 页有风险 · {rep['elapsed_ms']}ms")
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
