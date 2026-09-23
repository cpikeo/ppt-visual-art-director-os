# -*- coding: utf-8 -*-
"""intelligence.py · 设计智能层（唯一决策链）

    Audience → Decision → Claim → Tension → Focus → Form → Space → Media → Spec

职责：把 brief 一次性变成「判断面」——机器给得出的事实（方向执行、主题种子、
媒体必要性判断+理由、证据缺口、锚点、统一契约）与逐页必答的判断问题
（本页唯一结论 / 视线第一落点 / 最诚实的形式 / 留白职责）。

本层**不给**布局、坐标、密度配额、构图模板：
  * `family` 只辅助路由（锚点词汇、媒体闸门、形态问题校准），不套用页面；
  * `density` 不预判——由作者写、或由成稿测量，规划层不再发明；
  * `asset` 必须经过必要性判断（置信度+理由），作者声明永远压过判断；
  * 相同内容不默认产生相同布局：规划产出的是问题，不是答案。

单趟规划、单份页事实：没有第二张路由表、没有对齐层、没有规划缓存。
依赖方向：本模块零包内依赖（DNA 库与表都住在这里）；assets / verify / vao 读它。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

SCHEMA = "vao-plan-v2"
DNA_STORE = Path(__file__).resolve().parent.parent / "memory" / "design_dna.json"

# ─────────────────────────────────────────────────────────────────────
# 1 · Brief 加载（唯一加载器：yml / json / 定义 BRIEF|NEED 的模块）
# ─────────────────────────────────────────────────────────────────────
def load_brief(path) -> dict:
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"需求文件不存在: {p}（brief 需为 .yml/.yaml/.json 或定义 BRIEF/NEED 的 .py）")
    if p.suffix in (".yml", ".yaml"):
        import yaml
        try:
            value = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = f":{mark.line + 1}:{mark.column + 1}" if mark else ""
            raise ValueError(f"brief YAML 解析失败：{p}{where} — "
                             f"{getattr(exc, 'problem', None) or exc}") from None
    elif p.suffix == ".json":
        try:
            value = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"brief JSON 解析失败：{p}:{exc.lineno}:{exc.colno} — {exc.msg}") from None
    elif p.suffix == ".py":
        import types
        mod = types.ModuleType("need_mod")
        mod.__file__ = str(p)
        exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), mod.__dict__)
        value = dict(mod.BRIEF) if hasattr(mod, "BRIEF") else (
            dict(mod.NEED) if hasattr(mod, "NEED") else None)
        if value is None:
            raise ValueError("brief 模块必须定义 BRIEF 或 NEED")
    else:
        raise ValueError("brief 只接受 .yml/.yaml/.json，或定义 BRIEF/NEED 的 .py")
    if not isinstance(value, dict):
        raise ValueError(f"brief 顶层必须是对象，实际是 {type(value).__name__}：{p}")
    return value


# ─────────────────────────────────────────────────────────────────────
# 2 · 方向（唯一方向表：结构 × 材质人格 × 种子色板，一条一行）
# ─────────────────────────────────────────────────────────────────────
# 每条 = 这副 deck 用什么质感说话（材质/光/图表手法）+ 四槽种子色板。
# 种子不是模板：落进 spec.theme 后仍由作者覆盖任意一项。
# 字体种子用跨平台安全名（思源黑体/思源宋体/Arial/Georgia）：苹果苹方、
# Helvetica Neue 只在 macOS 存在，别的系统会静默回落成完全不同的气质。
# 字体名缺失时 PowerPoint 自行替代，theme_fonts 检查只在键缺失时点名。
DIRECTIONS: dict[str, dict] = {
    "zen_minimal": dict(regime="light", background="solid_world", asym=False,
        material="handmade paper, mist, still water, shadowless light",
        light="flat even ambient", chart="hairline + direct label",
        motion="natural", texture=("eastern",),
        fonts={"cn": "Source Han Sans SC", "latin": "Arial"},
        seed={"foundation": "#F5F4F1", "supporting": "#9A9A96",
              "information": "#1E1E1C", "accent": "#6E6E6A"}),
    "editorial": dict(regime="light", background="atmospheric", asym=True,
        material="warm ivory paper, travertine and bronze, soft window light",
        light="single soft upper-left", chart="annotation field",
        motion="reveal", texture=("luxury", "architecture"),
        fonts={"cn": "Source Han Serif SC", "latin": "Georgia"},
        seed={"foundation": "#F2EDE4", "supporting": "#9A8C74",
              "information": "#403B32", "accent": "#9C5A2E"}),
    "quiet_luxury": dict(regime="light", background="solid_world", asym=False,
        material="champagne metal hairline, taupe stone, sea light through sheer curtain",
        light="single soft key", chart="hairline + direct label",
        motion="spatial", texture=("luxury",),
        fonts={"cn": "Source Han Sans SC", "latin": "Arial"},
        seed={"foundation": "#F1EDE6", "supporting": "#A99878",
              "information": "#37322A", "accent": "#B08D4F"}),
    "song_elegance": dict(regime="light", background="atmospheric", asym=True,
        material="rice paper, ink stone, tea-green silk, diffuse north light",
        light="diffuse north window", chart="hairline + direct label",
        motion="natural", texture=("eastern",),
        fonts={"cn": "Source Han Serif SC", "latin": "Georgia"},
        seed={"foundation": "#F3F1EA", "supporting": "#8B8D84",
              "information": "#22241F", "accent": "#5E7562"}),
    "nordic_quiet": dict(regime="light", background="solid_world", asym=False,
        material="lime plaster, pale oak, ceramic, low winter sun",
        light="low winter sun", chart="hairline + direct label",
        motion="spatial", texture=("architecture",),
        fonts={"cn": "Source Han Sans SC", "latin": "Arial"},
        seed={"foundation": "#EFECE6", "supporting": "#A79E90",
              "information": "#33302B", "accent": "#8A7A5F"}),
    "organic_systems": dict(regime="light", background="solid_world", asym=False,
        material="oat fiber, leaf vein macro, sage clay, soft top light",
        light="soft top light", chart="hairline + direct label",
        motion="natural", texture=("organic",),
        fonts={"cn": "Source Han Sans SC", "latin": "Arial"},
        seed={"foundation": "#EFEBE2", "supporting": "#A8A394",
              "information": "#3B3A33", "accent": "#7C8B6F"}),
    "evidence_field": dict(regime="light", background="solid_world", asym=False,
        material="newsprint white, ink black, one signal color, hard magazine grid",
        light="flat", chart="shared baseline + delta",
        motion="spatial", texture=("eastern",),
        fonts={"cn": "Source Han Sans SC", "latin": "Arial"},
        seed={"foundation": "#FFFFFF", "supporting": "#5A5A5A",
              "information": "#101010", "accent": "#2563EB"}),
    "product_stage": dict(regime="dark", background="dark_luminous", asym=False,
        material="glass + metal, one key light on a dark stage",
        light="one key light", chart="minimal kpi",
        motion="reveal", texture=("technology",),
        fonts={"cn": "Source Han Sans SC", "latin": "Arial"},
        seed={"foundation": "#0B0B0F", "supporting": "#3A3A42",
              "information": "#E4E4EA", "accent": "#3B82F6"}),
    "precision_minimal": dict(regime="light", background="solid_world", asym=False,
        material="titanium micro-brush, mist white stage, single product light",
        light="single product light", chart="minimal kpi",
        motion="tech", texture=("technology",),
        fonts={"cn": "Source Han Sans SC", "latin": "Arial"},
        seed={"foundation": "#F6F6F7", "supporting": "#9BA0A6",
              "information": "#1D1D1F", "accent": "#0071E3"}),
    "precision_tech": dict(regime="dark", background="solid_world", asym=False,
        material="optical glass, titanium edge, controlled blue signal on graphite",
        light="controlled signal light", chart="minimal kpi",
        motion="tech", texture=("technology",),
        fonts={"cn": "Source Han Sans SC", "latin": "Arial"},
        seed={"foundation": "#0D0F12", "supporting": "#3A4148",
              "information": "#F2F4F6", "accent": "#2E7BD6"}),
    "data_intelligence": dict(regime="dark", background="solid_world", asym=False,
        material="dark graphite evidence field, steel gray structure, one controlled accent",
        light="flat evidence field", chart="shared baseline + delta",
        motion="tech", texture=("technology",),
        fonts={"cn": "Source Han Sans SC", "latin": "Arial"},
        seed={"foundation": "#141619", "supporting": "#454B52",
              "information": "#EDEFF1", "accent": "#3E8E7E"}),
    "monochrome_noir": dict(regime="dark", background="solid_world", asym=True,
        material="black stone, single raking light shaft, graphite dust",
        light="single raking light shaft", chart="hairline + direct label",
        motion="spatial", texture=("architecture",),
        fonts={"cn": "Source Han Sans SC", "latin": "Arial"},
        seed={"foundation": "#101010", "supporting": "#4A4A4A",
              "information": "#F2F2F0", "accent": "#8C8C8C"}),
    "cinematic_narrative": dict(regime="dark", background="atmospheric", asym=True,
        material="amber dusk, coastal air, brass light, deep shadow",
        light="amber dusk key", chart="annotation field",
        motion="spatial", texture=("luxury", "architecture"),
        fonts={"cn": "Source Han Serif SC", "latin": "Georgia"},
        seed={"foundation": "#141210", "supporting": "#5C4A33",
              "information": "#EFE3CE", "accent": "#C08A3E"}),
    "nature_luxury": dict(regime="dark", background="atmospheric", asym=True,
        material="deep forest green, mist over water, wet stone, cold diffuse light",
        light="cold diffuse light", chart="hairline + direct label",
        motion="natural", texture=("organic", "architecture"),
        fonts={"cn": "Source Han Serif SC", "latin": "Georgia"},
        seed={"foundation": "#16211C", "supporting": "#4E6157",
              "information": "#EDEFE9", "accent": "#6FA08C"}),
}

# 自由文本方向的确定性归一（只做别名，不猜单个形容词）
DIRECTION_ALIASES = {
    "quiet_minimal": "zen_minimal", "quiet minimal": "zen_minimal",
    "minimal": "zen_minimal", "neutral": "zen_minimal",
    "editorial_brand": "editorial", "editorial brand": "editorial",
    "editorial storytelling": "editorial", "luxury_editorial": "editorial",
    "luxury editorial": "editorial",
    "quiet luxury x editorial storytelling": "editorial",
    "product stage": "product_stage",
    "evidence first": "evidence_field", "evidence_first": "evidence_field",
    "data intelligence": "data_intelligence",
    "song": "song_elegance", "宋韵": "song_elegance",
}


def canonical_direction(value):
    """方向归一 → (name, warning|None)。未知方向回落 zen_minimal 并留痕。"""
    raw = str(value or "").strip()
    if not raw:
        return "zen_minimal", None
    key = re.sub(r"\s+", " ", raw.lower().replace("×", " x ")).strip()
    if key in DIRECTIONS:
        return key, None
    if key in DIRECTION_ALIASES:
        return DIRECTION_ALIASES[key], None
    for alias, canonical in sorted(DIRECTION_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if len(alias) >= 8 and alias in key:
            return canonical, {"input": raw, "canonical": canonical, "rule": "direction_alias"}
    return "zen_minimal", {"input": raw, "canonical": "zen_minimal", "rule": "direction_fallback"}


# ─────────────────────────────────────────────────────────────────────
# 3 · 内容类型（只做路由提示：锚点词汇 / 媒体闸门 / 形态问题校准）
# ─────────────────────────────────────────────────────────────────────
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

TYPE_ALIASES = {
    "title": "cover", "hero": "cover", "opening": "cover", "封面": "cover",
    "editorial": "brand_story", "manifesto": "brand_story", "brand": "brand_story",
    "launch": "product", "product_story": "product", "release": "product",
    "case_study": "case", "proof": "case", "客户案例": "case",
    "quote": "statement", "insight": "statement", "金句": "statement",
    "data_story": "data", "chart": "data", "metric": "data", "数据页": "data",
    "compare": "comparison", "versus": "comparison", "对比": "comparison",
    "roadmap": "timeline", "milestone": "timeline", "时间轴": "timeline",
    "framework": "architecture", "structure": "architecture", "system": "architecture",
    "narrative": "process", "steps": "process", "流程": "process",
    "executive_summary": "business", "summary": "business", "overview": "business",
    "agenda": "agenda", "toc": "agenda", "目录": "agenda",
    "closing": "closing", "cta": "closing", "ending": "closing", "结束页": "closing",
}

_EXPLICIT_TYPE_KEYS = ("type", "family", "page_family", "content_type")

# 媒体模型（唯一真源）：家族 → (是否需要图, 置信度, 理由)。是判断不是闸门。
MEDIA_MODEL = {
    "HERO": (True, 0.95, "开场页：品牌情绪建立，画心承担第一印象"),
    "CLOSING": (True, 0.90, "收尾页：情绪收束，画心承担记忆点"),
    "STORY": (True, 0.85, "叙事页：图像承担 context / emotion 功能"),
    "STATEMENT": (False, 0.30, "宣言页：留白与字阶就是视觉锚点，加图反而稀释"),
    "SECTION": (False, 0.25, "章节页：结构即节奏，安静是功能"),
    "DATA": (False, 0.05, "数据页：图表已是视觉锚点，再叠图 = 双焦点竞争"),
    "STRUCTURE": (False, 0.02, "结构页：结构关系比图像更清晰，出图必输"),
    "PROCESS": (False, 0.05, "序列页：位置即步骤，序列自带视觉性"),
    "COMPARISON": (False, 0.08, "对比页：左右张力来自内容本身"),
    "EVIDENCE": (False, 0.10, "证据页：数字与来源的可信度不需要装饰"),
    "CASE_STUDY": (True, 0.45, "案例页：仅在图像能证明现场/人物/结果时使用 proof 媒体"),
}
# 内容类型 → 媒体家族（两轴命名的唯一映射）
FAMILY_ALIASES = {
    "COVER": "HERO", "DATA_STORY": "DATA", "MINIMAL_STATEMENT": "STATEMENT",
    "EDITORIAL": "STORY", "NARRATIVE": "STORY", "FRAMEWORK": "STRUCTURE",
    "TIMELINE": "PROCESS", "EXECUTIVE_SUMMARY": "EVIDENCE",
    "EVIDENCE_FIELD": "EVIDENCE", "CASE_STUDY": "CASE_STUDY",
    "HERO_COVER": "HERO", "SECTION_DIVIDER": "SECTION",
}
TYPE_TO_FAMILY = {
    "cover": "COVER", "brand_story": "EDITORIAL", "product": "HERO",
    "case": "CASE_STUDY", "statement": "MINIMAL_STATEMENT", "closing": "MINIMAL_STATEMENT",
    "business": "EXECUTIVE_SUMMARY", "agenda": "EXECUTIVE_SUMMARY", "data": "DATA_STORY",
    "comparison": "COMPARISON", "timeline": "TIMELINE", "architecture": "FRAMEWORK",
    "process": "NARRATIVE",
}
FAMILY_TOKENS = frozenset(MEDIA_MODEL) | frozenset(FAMILY_ALIASES) | frozenset(TYPE_TO_FAMILY.values())

# 证据型家族：没有真实 content 就不成立。标题是观点，不是证据。
EVIDENCE_TYPES = frozenset({"data", "comparison", "case", "business", "timeline"})

ENERGY_LEVELS = ("high", "medium", "low")
DENSITY_LEVELS = ("sparse", "balanced", "dense")


def normalize_family(raw) -> str:
    """家族名归一（内容家族 → 媒体家族），唯一映射源。"""
    up = str(raw or "").strip().upper()
    return FAMILY_ALIASES.get(up, up)


def _latin_word_match(text: str, term: str) -> bool:
    """CJK 用子串；拉丁整词（避免 history→story 误路由）。"""
    text, term = str(text or "").lower(), str(term or "").strip().lower()
    if not term:
        return False
    if any("\u4e00" <= ch <= "\u9fff" for ch in term):
        return term in text
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def detect_type(text: str) -> str:
    """关键词命中 → 内容类型提示；未命中回落 business（最常见汇报页）。只做提示。"""
    t = str(text or "").lower()
    best, best_hits = None, 0
    for ctype, kws in KEYWORDS.items():
        hits = sum(1 for k in kws if _latin_word_match(t, k))
        if hits > best_hits:
            best, best_hits = ctype, hits
    return best or "business"


def explicit_content_type(item):
    """作者显式声明的内容类型（归一后）；关键词嗅探永远不进这一步。"""
    if not isinstance(item, dict):
        return None
    for key in _EXPLICIT_TYPE_KEYS:
        raw = item.get(key)
        if raw is not None and str(raw).strip():
            token = str(raw).strip().lower()
            if ":" in token:
                token = token.split(":", 1)[1].strip()
            token = token.replace("-", "_").replace(" ", "_")
            if len(token) >= 2:
                if token in KEYWORDS:
                    return token
                if token in TYPE_ALIASES:
                    return TYPE_ALIASES[token]
                for alias, ctype in TYPE_ALIASES.items():
                    if alias in token or token in alias:
                        return ctype
    return None


# ─────────────────────────────────────────────────────────────────────
# 4 · 媒体判断（唯一实现：模型 + 页内事实 + 作者声明）
# ─────────────────────────────────────────────────────────────────────
def media_judgment(family_hint: str, *, declared_asset: str | None = None,
                   has_chart: bool = False) -> dict:
    """这页要不要图 → {decision, confidence, reason, source}。

    优先级：作者显式声明 > 页内事实（已有图表）> 家族媒体模型。
    """
    if declared_asset in ("required", "reuse", "none"):
        return {"decision": declared_asset, "confidence": 1.0,
                "source": "author", "reason": "作者显式声明（压过一切判断）"}
    family = normalize_family(family_hint)
    need, conf, reason = MEDIA_MODEL.get(family, (False, 0.20, "未知家族：默认不出图（媒体需要理由）"))
    if has_chart and need:
        need, conf = False, 0.08
        reason = "页内已有图表（视觉锚点被占用），再出图 = 双焦点竞争"
    elif has_chart:
        reason = "图表即视觉锚点，媒体预算应为 0"
    return {"decision": "required" if need else "none",
            "confidence": conf, "source": "model",
            "reason": reason, "family": family or "UNKNOWN"}


# ─────────────────────────────────────────────────────────────────────
# 5 · 色彩（单管线：方向种子 → 品牌覆盖 → 可读性兜底）
# ─────────────────────────────────────────────────────────────────────
_BRAND_SLOT_ALIAS = {"ink": "information", "primary": "information",
                     "information": "information",
                     "secondary": "supporting", "muted": "supporting",
                     "supporting": "supporting",
                     "accent": "accent",
                     "background": "foundation", "paper": "foundation",
                     "foundation": "foundation"}


def normalize_brand_colors(brand) -> dict:
    """brand_colors 唯一归一：{slot:#HEX} 或 [#主,#强调,#辅] → {slot:#HEX}。"""
    if isinstance(brand, dict):
        return {str(k).strip(): str(v).strip() for k, v in brand.items()
                if isinstance(v, str) and str(v).strip().startswith("#")
                and len(str(v).strip()) in (4, 7)}
    if isinstance(brand, (list, tuple)):
        hexes = [str(v).strip() for v in brand
                 if isinstance(v, str) and str(v).strip().startswith("#")
                 and len(str(v).strip()) in (4, 7)]
        return dict(zip(("primary", "accent", "secondary"), hexes))
    return {}


def color_seed(direction: str, brand) -> tuple[dict, str]:
    """方向种子 + 品牌覆盖 → 四槽种子。返回 (seed, source)。"""
    seed = dict(DIRECTIONS.get(direction, DIRECTIONS["zen_minimal"])["seed"])
    valid = normalize_brand_colors(brand)
    slots = {}
    for k, v in valid.items():
        slot = _BRAND_SLOT_ALIAS.get(str(k).strip())
        if slot and slot not in slots:
            slots[slot] = v
    if slots:
        seed.update(slots)
        return seed, "brand_colors"
    return seed, "direction_seed"


# ─────────────────────────────────────────────────────────────────────
# 6 · Design DNA（判断记忆：为什么有效，不是参数表）
# ─────────────────────────────────────────────────────────────────────
RESULT_MEMORY_KEYS = {"palette", "color", "colors", "font", "fonts",
                      "image_style", "layout", "layout_result"}
JUDGMENT_KEYS = {"hierarchy", "space", "media", "color_behavior",
                 "charts", "anchor_rule", "structure", "type_voice"}
DNA_SCHEMA_NOTE = ("经验库（非参数库）：每条 = pattern + design_problem + judgment（可迁移的"
                   "行为判断）+ works_because + avoid + when_not_to + proven（实测证据）。"
                   "judgment 只写行为判断，不写色值/字号/版式结果——结果放 proven。")
_HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{3,8}\b")


def _load_store(path=None, strict=False) -> dict:
    target = Path(path) if path else DNA_STORE
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("entries"), list):
            raise ValueError("经验库顶层必须是对象且 entries 必须是数组")
        return value
    except FileNotFoundError:
        return {"version": 1, "entries": []}
    except Exception as exc:
        if strict:
            raise
        return {"version": 1, "entries": [], "_load_error": f"{type(exc).__name__}: {exc}"}


def _leaf_strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _leaf_strings(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _leaf_strings(x)


def recall_dna(brief: dict) -> dict:
    """brief → 最匹配的设计经验（确定性关键词打分）。DNA 是起点不是模板。"""
    parts = [str(v) for v in (brief or {}).values() if isinstance(v, (str, int, float))]
    slides = (brief or {}).get("slides")
    if isinstance(slides, list):
        for s in slides:
            if isinstance(s, dict):
                parts.extend(str(s[k]) for k in ("title", "content", "subject", "text")
                             if isinstance(s.get(k), str))
            elif isinstance(s, str):
                parts.append(s)
    low = " ".join(parts).lower()
    store = _load_store()
    load_error = store.get("_load_error")
    entries = [e for e in (store.get("entries") or []) if isinstance(e, dict)]
    scored = []
    for e in entries:
        signature = e.get("signature") if isinstance(e.get("signature"), dict) else {}
        keywords = signature.get("keywords") if isinstance(signature.get("keywords"), list) else []
        sig = [str(s).lower() for s in keywords if str(s).strip()]
        if not sig:
            continue
        hits = sum(1 for s in sig if s in low)
        scored.append((hits / len(sig), hits, e))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2].get("id", "")))
    broken = len(entries) - len(scored)
    broken_note = (f"；另有 {broken} 条经验缺 signature.keywords（永远不会命中），"
                   f"运行 python scripts/vao.py dna --check 查看") if broken else ""
    if not scored or scored[0][0] <= 0:
        note = ("无匹配 DNA：从方向种子起步，发布 PASS 后运行 "
                "python scripts/vao.py dna --add <条目>.json 沉淀这条经验")
        if load_error:
            note += f"；经验库读取失败，已安全降级（{load_error}）"
        return {"matched": None, "confidence": 0.0, "dna": None, "alternatives": [],
                "note": note + broken_note, "broken_entries": broken,
                **({"load_error": load_error} if load_error else {})}
    conf, hits, best = scored[0]
    legacy = best.get("dna") if isinstance(best.get("dna"), dict) else {}
    return {"matched": best.get("id"), "confidence": round(conf, 2),
            "dna": best.get("judgment") or best.get("dna"),
            "design_problem": best.get("design_problem"),
            "avoid": best.get("avoid") or legacy.get("forbidden"),
            "alternatives": [{"id": e.get("id"), "confidence": round(c, 2)}
                             for c, h, e in scored[1:3] if c > 0],
            "proven": best.get("proven"), "broken_entries": broken,
            "note": ("DNA 是起点不是模板：按当前内容与受众重组，禁止照抄" if conf < 0.6
                     else "高置信命中：以该经验为基线，只做内容级调整") + broken_note}


def validate_dna_entry(entry) -> tuple[list, list]:
    if not isinstance(entry, dict):
        return ["条目必须是对象（id / signature.keywords / judgment / pattern）"], []
    errors, warnings = [], []
    if not str(entry.get("id") or "").strip():
        errors.append("缺 id：稳定标识，用于去重与人工引用")
    if not str(entry.get("pattern") or "").strip():
        errors.append("缺 pattern：这条经验的模式名（一句话说清它解决什么）")
    judgment = entry.get("judgment")
    if not judgment or (isinstance(judgment, str) and not judgment.strip()):
        errors.append("缺 judgment：可迁移的行为判断（不是结果值）")
    signature = entry.get("signature") if isinstance(entry.get("signature"), dict) else {}
    keywords = [str(k).strip() for k in (signature.get("keywords") or []) if str(k).strip()]
    if not keywords:
        errors.append("缺 signature.keywords：召回只按关键词打分，空 = 永远命不中")
    if isinstance(judgment, dict):
        leaked = [str(k) for k in judgment if str(k) in RESULT_MEMORY_KEYS]
        if leaked:
            errors.append(f"judgment 里出现结果键 {leaked}：色值/字体/版式结果属于证据，"
                          "请移到 proven")
        unknown = sorted(str(k) for k in judgment
                         if str(k) not in JUDGMENT_KEYS and str(k) not in RESULT_MEMORY_KEYS)
        if unknown:
            errors.append(f"judgment 维度 {unknown} 不在合法维度内：{sorted(JUDGMENT_KEYS)}")
    hexes = sorted({h for leaf in _leaf_strings(judgment) for h in _HEX_COLOR.findall(leaf)})
    if hexes:
        errors.append(f"judgment 里写死了色值 {hexes}：判断要与具体值解耦")
    for key, why in (("design_problem", "当时面对什么矛盾"),
                     ("works_because", "为什么这个判断成立"),
                     ("avoid", "什么做法要避开"),
                     ("when_not_to", "什么情况下不适用")):
        if not entry.get(key):
            warnings.append(f"建议补 {key}（{why}）")
    if not entry.get("proven"):
        warnings.append("建议补 proven（project / qa / measurements）——没有证据的经验只是主张")
    return errors, warnings


def validate_dna_store(path=None) -> dict:
    store = _load_store(path)
    load_error = store.get("_load_error")
    if load_error:
        return {"ok": False, "entries": 0, "errors": [{"id": None, "reason": load_error}],
                "warnings": []}
    errors, warnings, seen = [], [], set()
    for i, entry in enumerate(store.get("entries") or []):
        eid = entry.get("id") if isinstance(entry, dict) else None
        label = str(eid) if eid else f"#{i}"
        if eid is not None and str(eid) in seen:
            errors.append({"id": label, "reason": "id 重复（同 id 只会在召回里互相遮蔽）"})
        seen.add(str(eid))
        e_errs, e_warns = validate_dna_entry(entry)
        errors += [{"id": label, "reason": m} for m in e_errs]
        warnings += [{"id": label, "reason": m} for m in e_warns]
    return {"ok": not errors, "entries": len(store.get("entries") or []),
            "errors": errors, "warnings": warnings}


def record_dna(entry, path=None, replace=False) -> dict:
    """写入一条经验：校验 → 去重 → 原子替换。写坏记忆比不写更贵。"""
    errors, warnings = validate_dna_entry(entry)
    if errors:
        return {"added": False, "id": (entry or {}).get("id") if isinstance(entry, dict) else None,
                "errors": errors, "warnings": warnings}
    target = Path(path) if path else DNA_STORE
    store = _load_store(target, strict=True)
    entries = [e for e in (store.get("entries") or []) if isinstance(e, dict)]
    eid = str(entry["id"]).strip()
    same = next((e for e in entries if str(e.get("id") or "").strip() == eid), None)
    if same is not None and not replace:
        if same == entry:
            return {"added": False, "id": eid, "entries": len(entries), "warnings": warnings,
                    "note": "同 id 且内容一致，已是库中条目（幂等，未改动）"}
        return {"added": False, "id": eid, "errors": ["同 id 条目已存在且内容不同：确认覆盖时加 --replace"],
                "warnings": warnings}
    if same is not None:
        entries[entries.index(same)] = entry
        action = "replaced"
    else:
        entries.append(entry)
        action = "added"
    store["entries"] = entries
    store["version"] = max(int(store.get("version") or 1), 2)
    store.setdefault("schema_note", DNA_SCHEMA_NOTE)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return {"added": True, "action": action, "id": eid, "entries": len(entries),
            "warnings": warnings, "note": f"{action} {eid} · 经验库现有 {len(entries)} 条"}


# ─────────────────────────────────────────────────────────────────────
# 7 · 判断问题的逐页校准（形态问题随内容类型变化——规划给问题，不给答案）
# ─────────────────────────────────────────────────────────────────────
_FORM_QUESTIONS = {
    "cover": "开场承担第一印象：让标题成为全案主张的开场白，副题给场合与署名。先定那句话，再定它多大。",
    "statement": "一句话被记住：留白与字阶就是表达。先决定给多少沉默，再决定字多大。",
    "data": "数字只服务一个关系。先写结论（大数字/直接标注常胜过长篇图表），再决定是否用一张原生图表；不出图片。",
    "comparison": "对比的唯一决策点是什么？让一侧获得明确优先级，张力来自内容本身，不靠装饰。",
    "case": "哪个具体事实/人物/场景让主张可信？若没有图像能证明现场，就用排版与数字承担。",
    "business": "结构即内容：用字阶与留白切分条目，不添加视觉对象。",
    "agenda": "目录是路标：让读者三秒看到全案形状，字阶层级就是结构。",
    "architecture": "呈现体系关系（层级/顺序/流转）：结构比图像更清晰，先定关系再定形状。",
    "process": "位置即步骤、序列自带视觉性：让轴与间距说话，不堆图标。",
    "timeline": "时间是主语：节点密度服从叙事节奏，不为凑满而加节点。",
    "product": "产品自己说话：画心承担产品证据，文字只给最少必要信息。",
    "brand_story": "故事页：图像承担情绪，文字退到解说位；先定情绪，再定画面。",
    "closing": "行动请求要清楚到动词与对象：留白制造决定的分量。",
}

_FOCUS_QUESTION = "视线第一落点是哪个元素？它必须承担本页结论，而不是装饰、页码或眉标。"
_SPACE_QUESTION = "本页留白承担什么：保护焦点 / 承载情绪 / 制造权威感 / 分隔章节？说不出职责的空白是排版事故。"
_CLAIM_TEMPLATE = "本页要让观众理解的唯一结论（一句完整的话，能复述；与全案主张「{claim}」相连）。"
# 天然与全案张力对话的页：结论/主张页必须立住主张，风险页必须直面疑虑。
_TENSION_TYPES = ("statement", "risk")


def page_questions(content_type: str, decision: str | None = None,
                   tension: str | None = None) -> dict:
    """逐页必答的判断问题（claim/focus/form/space）。

    规划产出问题，答案由内容决定——相同内容不默认产生相同布局。
    form 问题随内容类型校准；claim 问题绑定全案决策；结论/风险页与收尾页
    追加张力之问——deck 级的 tension 要在页面上有落点，不能只停在 brief 里。
    """
    claim = decision or "（未声明的全案决策）"
    q = {
        "claim": _CLAIM_TEMPLATE.format(claim=claim[:40]),
        "focus": _FOCUS_QUESTION,
        "form": _FORM_QUESTIONS.get(content_type,
                                    "让洞察可见的最低戏剧化表达是什么？先删到不能再删。"),
        "space": _SPACE_QUESTION,
    }
    tension = str(tension or "").strip()
    if tension and content_type in _TENSION_TYPES:
        q["claim"] += (f" 本页如何直面观众最大疑虑「{tension[:36]}」"
                       "——回应了疑虑，主张才立得住；回避它，页面再漂亮也不可信。")
    return q


# ─────────────────────────────────────────────────────────────────────
# 8 · 单趟规划（think）：brief → 判断面 + 单份页事实
# ─────────────────────────────────────────────────────────────────────
ADVANCED_TRIGGERS = ("发布会", "品牌", "年报", "旗舰", "形象", "高端", "launch", "brand",
                     "keynote", "manifesto", "premium", "campaign")
QUALITY_ALIASES = {"fast": "fast", "quick": "fast", "standard": "fast",
                   "advanced": "advanced", "premium": "advanced", "keynote": "advanced",
                   "benchmark": "advanced"}

# 逐页可声明字段（写了原样生效，规划只带过去不解释）
# insight/focus 是四问的前两问：作者在 brief 里写了答案，骨架就不再留空 TODO 重问——
# 「写了的字段原样生效」是本包对作者的第一契约。
_PAGE_DECLARATIONS = ("density", "energy", "asset", "asset_role", "asset_function",
                      "asset_subject", "medium", "material", "lighting", "texture",
                      "asset_color", "safe_area", "text_color", "negative_space_anchor",
                      "asset_ratio", "asset_allow_crop", "asset_source", "composition",
                      "insight", "focus")


def _intent_value(value) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def think(brief: dict) -> dict:
    """唯一规划入口：一次计算，产出判断面与单份页事实。确定性、零文件写入。"""
    brief = brief if isinstance(brief, dict) else {}
    warnings: list[dict] = []

    # ── deck 级判断（一次固化，页面继承）──────────────────────────────
    audience = str(brief.get("audience") or "").strip()
    decision = str(brief.get("decision") or "").strip()
    tension = str(brief.get("tension") or "").strip()
    if not audience or not decision or not tension:
        missing = "/".join(name for name, val in
                           (("audience", audience), ("decision", decision),
                            ("tension", tension)) if not val)
        parts = []
        if not audience or not decision:
            parts.append("先回答「谁看 + 看完要做什么决定」，其余判断都从这两个答案推出")
        if not tension:
            parts.append("tension 缺失：结论/风险/收尾页会失去「直面观众疑虑」之问"
                         "（只写疑虑本身，不写解决方案）")
        warnings.append({"rule": "deck_contract", "scope": "deck",
                         "msg": "brief 缺 " + missing + "：" + "；".join(parts)})

    occasion = f"{brief.get('occasion','')} {brief.get('subject','')} {brief.get('brief','')}"
    quality_input = brief.get("quality_level")
    quality = QUALITY_ALIASES.get(str(quality_input or "").strip().lower()) if quality_input else (
        "advanced" if any(k in occasion.lower() or k in occasion for k in ADVANCED_TRIGGERS)
        else "fast")
    if quality_input and str(quality_input).strip().lower() not in QUALITY_ALIASES:
        warnings.append({"input": quality_input, "canonical": quality, "rule": "quality_fallback"})

    direction, direction_warning = canonical_direction(brief.get("design_direction"))
    if direction_warning:
        warnings.append(direction_warning)
    d = DIRECTIONS[direction]
    seed, seed_source = color_seed(direction, brief.get("brand_colors"))

    # 经验召回（P1 并行：可选智能层失败可降级，但必须留痕）
    try:
        dna = recall_dna(brief)
    except Exception as exc:
        warnings.append({"rule": "design_intelligence", "scope": "deck",
                         "error": f"{type(exc).__name__}: {exc}"})
        dna = {"matched": None, "confidence": 0.0, "dna": None,
               "note": "design_intelligence 不可用；按方向种子起步"}

    # ── 逐页判断（单份页事实）─────────────────────────────────────────
    raw = brief.get("slides")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise TypeError("brief.slides must be a list of page briefs")
    pages = []
    for i, item in enumerate(raw):
        is_dict = isinstance(item, dict)
        text = (str(item.get("title") or "") + " " + str(item.get("content") or "")) if is_dict else str(item)
        sid = (item.get("id") if is_dict and item.get("id") else f"s{i + 1:02d}")
        declared_type = explicit_content_type(item)
        content_type = declared_type or detect_type(text)
        family = TYPE_TO_FAMILY.get(content_type, "EXECUTIVE_SUMMARY")

        # 作者逐页声明：原样带过去（不解释、不改写、不校验枚举之外的任何事）
        declarations = {k: item[k] for k in _PAGE_DECLARATIONS
                        if is_dict and _intent_value(item.get(k))}
        # asset_subject 非空等价 asset=required（显式声明）
        if "asset_subject" in declarations and str(declarations.get("asset") or "").lower() not in (
                "required", "reuse", "none"):
            declarations["asset"] = "required"

        # 媒体判断（唯一实现）：作者声明 > 家族模型
        media = media_judgment(family, declared_asset=str(declarations.get("asset") or "").lower() or None)
        if media["source"] == "author":
            media["reason"] = "作者显式声明（压过一切判断）"

        # 证据型页面缺 content：标题不是证据，不得脑补
        unresolved = bool(content_type in EVIDENCE_TYPES
                          and not str(item.get("content") or "").strip() if is_dict else False)
        if unresolved:
            warnings.append({"rule": "unresolved_content", "scope": sid,
                             "msg": "content 缺失：证据型页面不能由标题脑补数据/案例——"
                                    "补真实证据，或改成纯排版观点页，或删掉这一页"})

        # 跨页锚（≥4 页成套）：眉标用家族词汇原文，页码从第 2 页起
        anchor = None
        if len(raw) >= 4:
            anchor = {"eyebrow": family.replace("_", " ") or "PAGE"}
            if i > 0:
                anchor["page_number"] = i + 1

        pages.append({
            "id": sid,
            "ref": text.strip()[:120],
            "content_type": content_type,
            "content_type_source": "declared" if declared_type else "hint",
            "family": family,                     # 仅辅助路由：锚点词汇 / 媒体闸门 / 问题校准
            "media": media,
            "unresolved": unresolved or None,
            "anchor": anchor,
            "declarations": declarations,
            # 判断问题不落盘：由 build_skeleton 按内容类型推导（page_questions），
            # 规划产出问题、骨架承载问题——plan.json 是链路凭证，不是阅读材料。
        })

    # ── 资产预算：只约束 Skill 判断产生的出图；作者声明永不被截断 ────────
    judged_required = [p["id"] for p in pages
                       if p["media"]["decision"] == "required" and p["media"]["source"] == "model"]
    declared_required = [p["id"] for p in pages
                         if p["media"]["decision"] in ("required", "reuse")
                         and p["media"]["source"] == "author"]
    cap = 2 if quality == "fast" else 4
    generate = declared_required + judged_required[:cap]

    return {
        "schema": SCHEMA,
        "deck": {
            "audience": audience or None,
            "decision": decision or None,
            "tension": tension or None,
            "quality": quality,
            "direction": direction,
            "direction_execution": {
                "background": d["background"], "material": d["material"], "light": d["light"],
                "chart_style": d["chart"], "motion": d["motion"],
                "texture_keys": list(d["texture"]),
                "composition_grammar": "soft_asymmetry" if d["asym"] else "evidence_field",
            },
            "regime": d["regime"],
            "fonts": dict(d["fonts"]),
            "theme": {"colors_seed": seed, "seed_source": seed_source},
            "dna": dna,
            # 统一契约：统一的是世界，可不同的是页面
            "unity": {
                "same_world": ["材质与光的逻辑", "排版声音", "锚点词汇", "图表性格", "色彩层级纪律"],
                "may_differ": ["构图", "密度", "色重", "图片比例", "标题位置", "页面结构"],
                "rule": "不同页面拥有不同的视觉表达，但仍属于同一个完整的视觉世界",
            },
            "slots": ["visual_world（视觉世界一句话）", "type_voice（字体语气）",
                      "color_behavior（饱和人格：quiet 只是种子，不是高级的默认值）",
                      "每页 claim / focus"],
        },
        "pages": pages,
        "assets_hint": {"generate": generate, "cap": cap,
                        "skipped": [p["id"] for p in pages if p["media"]["decision"] == "none"]},
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────
# 9 · 主题 token（种子四槽 → theme.colors 六 token + 可读性兜底）
# ─────────────────────────────────────────────────────────────────────
def theme_tokens(seed: dict, fonts: dict | None = None) -> dict:
    """四槽种子 → spec.theme.colors 六 token；起点保证可读（墨色与纸面分得开）。"""
    colors = {"background": seed.get("foundation", "#FFFFFF"),
              "ink": seed.get("information", "#111111"),
              "muted": seed.get("supporting", "#777777"),
              "primary": seed.get("information", "#222222"),
              "secondary": seed.get("supporting", "#333333"),
              "accent": seed.get("accent", "#AA0000")}
    try:
        from primitives import blend, contrast, is_light

        def _blend_toward(color, target, t=0.55):
            try:
                return blend(color, target, t)
            except Exception:
                return target
        if contrast(colors["background"], colors["ink"]) < 4.5:
            readable = "#141414" if is_light(colors["background"]) else "#FFFFFF"
            colors["ink"] = readable
            if contrast(colors["background"], colors["primary"]) < 4.5:
                colors["primary"] = readable
            if contrast(colors["background"], colors["secondary"]) < 3.0:
                colors["secondary"] = _blend_toward(colors["secondary"], readable)
            if contrast(colors["background"], colors["muted"]) < 3.0:
                colors["muted"] = _blend_toward(colors["muted"], readable)
    except Exception:
        pass
    return colors


# ─────────────────────────────────────────────────────────────────────
# 10 · 骨架构建（plan → build 模块；只序列化已决策事实 + 判断问题）
# ─────────────────────────────────────────────────────────────────────
def build_skeleton(bundle: dict) -> str:
    """plan bundle → build 模块骨架。确定性：同 bundle 必得同文本。

    骨架刻意不给坐标与构图：几何、尺度、留白由作者按内容判断。
    """
    deck = bundle.get("deck") or {}
    pages = bundle.get("pages") or []
    seed = (deck.get("theme") or {}).get("colors_seed") or {}
    colors = theme_tokens(seed)
    dex = deck.get("direction_execution") or {}
    dna = deck.get("dna") or {}
    unity = deck.get("unity") or {}

    facts: list[str] = []
    facts.append(f"受众: {deck.get('audience') or '未声明'} · 决策: {deck.get('decision') or '未声明'}"
                 + (f" · 张力: {deck['tension']}" if deck.get('tension') else ""))
    world = [x for x in (f"材质/世界: {dex.get('material')}" if dex.get("material") else "",
                         f"光: {dex.get('light')}" if dex.get("light") else "",
                         f"图表手法: {dex.get('chart_style')}" if dex.get("chart_style") else "") if x]
    if world:
        facts.append(" · ".join(world))
    if unity.get("same_world"):
        facts.append("统一契约 · 全 deck 必须统一: " + " / ".join(map(str, unity["same_world"]))
                     + "；允许每页不同: " + " / ".join(map(str, unity.get("may_differ") or [])))
    if deck.get("slots"):
        facts.append("等你判断的槽位: " + " / ".join(map(str, deck["slots"])))
    if dna.get("matched"):
        facts.append(f"经验召回（DNA）: {dna['matched']} · 置信 {dna.get('confidence')}"
                     "——DNA 是起点不是模板，按本稿内容与受众重组")
        if dna.get("design_problem"):
            facts.append(f"  核心矛盾: {str(dna['design_problem'])[:76]}")
        if dna.get("avoid"):
            facts.append("  避讳: " + " / ".join(map(str, list(dna["avoid"])[:6])))

    L = ['# -*- coding: utf-8 -*-',
         '"""plan → build 骨架：只给已决策的事实与必答的判断问题，零几何/样式预设。',
         '',
         '构图、尺度、留白由你按内容判断——相同内容不默认相同布局。',
         f'方向: {deck.get("direction")} · 质量: {deck.get("quality")} · 页数: {len(pages)}']
    L += [f'  {line}' for line in facts]
    L += ['',
          '落笔清单（一次做完）：',
          '  1) 每页先回答 page_intent 四问（claim/focus/form/space 见各页注释），再写元素；',
          '  2) elements 平铺写：x/y/width/height（8 的倍数）+ text + 样式平铺顶层。',
          '     当场被抓的量：框高 ≥ 字号 × 行高 × 行数；行高按字阶（不写默认 1.35）；',
          '     标题按 +20% 余量给宽；内容过多先删句改写，不缩字号。',
          '  3) theme.fonts 写 {cn, latin}；数值图表齐 source/unit/period/basis；',
          '     每页 anchor 落成元素：眉标 role=eyebrow + 页码 role=page_number，位置全 deck 一致；',
          '     出处只进 source_zone 框（role=source/method/metadata）。',
          '  字段与阈值速查 → references/contract.md（写 elements 前读一次）；',
          '  判断校准 → references/judgment.md。',
          '',
          '有图页先执行 assets → 出图；图片元素必须写 asset_id（check 时绑定核验）。',
          '填完后一次收口：',
          '  python scripts/vao.py check <本文件> out.pptx --mode release --assets-manifest asset_manifest.json',
          '"""',
          '',
          'SPEC = {',
          '    "canvas": {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8},',
          '    "theme": {',
          f'        "colors": {colors!r},',
          f'        "fonts": {{}},   # TODO: {{"cn": ..., "latin": ...}}（家族 ≤2）',
          '    },',
          '    "direction": {"color_intent": []},  # TODO：[brand, emotion, hierarchy]',
          '    "slides": [']
    last_i = len(pages) - 1
    for idx, pg in enumerate(pages):
        # 张力之问的落点：结论/风险页天然对话张力；最后一页（收尾）负责把疑虑了结
        pg_tension = deck.get("tension") if (
            pg.get("content_type") in _TENSION_TYPES or idx == last_i) else None
        q = page_questions(pg.get("content_type") or "", deck.get("decision"),
                           tension=pg_tension)
        media = pg.get("media") or {}
        decl = pg.get("declarations") or {}
        media_txt = (f"media={media.get('decision')}（{media.get('reason')}）"
                     if media else "")
        L.append(f'        # ── {pg.get("id")} · 内容类型={pg.get("content_type")}'
                 f'（{pg.get("content_type_source")}）· family 提示={pg.get("family")} · {media_txt}')
        if pg.get("ref"):
            L.append(f'        #    内容参考: {pg["ref"][:90]}')
        if pg.get("unresolved"):
            L.append('        #    ⚠ 未决: content 缺失——标题不是证据，不得脑补数据/案例；'
                     '补真实证据，或改成观点页，或删掉这一页')
        for key, label in (("claim", "结论"), ("focus", "焦点"), ("form", "形式"), ("space", "留白")):
            if q.get(key):
                L.append(f'        #    判断[{label}]: {q[key]}')
        if decl:
            shown = ", ".join(f"{k}={decl[k]!r}" for k in list(decl)[:6])
            L.append(f'        #    作者声明（原样生效）: {shown[:150]}')
        L.append('        {')
        L.append(f'            "id": {pg.get("id")!r},')
        # 作者在 brief 里写过的答案不再要求重答（写了的字段原样生效）
        intent = {"insight": str(decl.get("insight") or ""),
                  "focus": str(decl.get("focus") or ""),
                  "page_family": pg.get("family")}
        if intent["insight"] or intent["focus"]:
            L.append(f'            "page_intent": {json.dumps(intent, ensure_ascii=False)},'
                     '  # 作者已在 brief 声明，核对后沿用；要改就改 brief')
        else:
            L.append(f'            "page_intent": {json.dumps(intent, ensure_ascii=False)},'
                     '  # TODO: insight=本页结论 / focus=第一落点元素 id')
        if pg.get("anchor"):
            L.append(f'            "anchor": {json.dumps(pg["anchor"], ensure_ascii=False)},'
                     '  # 眉标固定上缘 / 页码固定象限（落成对应 role 的元素）')
        L.append('            "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},')
        L.append('            "elements": [  # TODO：按本页判断落元素（字段规则见文件头）')
        L.append('            ],')
        L.append('        },')
    L += ['    ],', '}', '']
    return "\n".join(L)
