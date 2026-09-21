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
                          `media_decision` 在**还没有 spec** 时按家族路由媒体需要
                          预判该 deck 会在哪里出问题，并把结论直接翻译成生成政策
                          （文本预算 / 媒体预算 / 复杂度约束），在起草之前消费。
                          （历史：曾有 spec 级 pre_critic + risk_strategy 二审层——
                          三域生产实测零消费：判断发生在起草时，不在起草后；已删除。）

与既有层的关系（**职责边界，不重叠**）：本层负责「设计判断 + 未来风险」；
`guard.py` / `qa.py` 负责工程正确性（溢出、越界、重叠、数据合同、渲染完整性），
设计价值的判断叙事归 references/design-craft；
预测阈值同源于 primitives 常量：本层只加预测与策略，
不改任何判定标准，也不替代渲染证据。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

# 机器口径真源见 design_intelligence_rules（判断归文档，查表归代码）。
from design_intelligence_rules import (
    MEDIA_MODEL as _MEDIA_MODEL, FAMILY_ALIASES as _FAMILY_ALIASES,
    DIRECTION_ALIAS as _DIRECTION_ALIAS, FAMILY_TOKENS,
    JUDGMENT_KEYS, RESULT_MEMORY_KEYS, COLOR_DIRECTIONS)

DNA_STORE = Path(__file__).resolve().parent.parent / "memory" / "design_dna.json"

# 密度带与 accent 估算因子 → design_intelligence_rules（真源），经 import 复用。

# ════════════════════════════════════════════════════════════════════════
# ① Design DNA Memory
# ════════════════════════════════════════════════════════════════════════
def _load_store(path=None, strict: bool = False) -> dict:
    """文件不存在 = 合法初态（空库）；存在但解析失败 = 数据损坏。

    读路径回落空库（召回失败安全）；strict 写路径抛错——写方必须在
    「损坏时拒绝写入」的最高层兜底，否则空库会被整体写回、经验全灭。"""
    target = Path(path) if path else DNA_STORE
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("entries"), list):
            raise ValueError("经验库顶层必须是对象且 entries 必须是数组")
        if not all(isinstance(entry, dict) for entry in value["entries"]):
            raise ValueError("经验库 entries 必须全部是对象")
        return value
    except FileNotFoundError:
        return {"version": 1, "entries": []}
    except Exception as exc:
        if strict:
            raise
        # 召回可安全降级为空库，但把损坏/权限问题带到结果里；不能让
        # 「经验库读取失败」伪装成「没有经验」，否则判断链不可审计。
        return {"version": 1, "entries": [],
                "_load_error": f"{type(exc).__name__}: {exc}"}

def recall_dna(brief: dict) -> dict:
    """brief → 最匹配的设计经验（确定性关键词打分）。

    返回 {matched, confidence, dna, alternatives, note}。
    confidence = 命中签名词数 / 该条签名总词数（0–1）。无命中时返回最近邻 +
    「adapt」提示——DNA 是起点不是答案，Art Director 仍要按当前内容重组。
    """
    parts = [str(v) for v in (brief or {}).values()
             if isinstance(v, (str, int, float))]
    # slides 是内容主体：召回不看 title/content，经验就永远只看见骨架
    # 看不见内容——同场景不同措辞的 deck 会永远命不中。
    _slides = (brief or {}).get("slides")
    if isinstance(_slides, list):
        for _s in _slides:
            if isinstance(_s, dict):
                parts.extend(str(_s[k]) for k in ("title", "content", "subject", "text")
                             if isinstance(_s.get(k), str))
            elif isinstance(_s, str):
                parts.append(_s)
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
    # 缺 signature.keywords 的条目永远命不中：这不是「没有经验」，是「经验写坏了」，
    # 必须留痕，否则坏记忆会伪装成空库。
    broken = len(entries) - len(scored)
    broken_note = (f"；另有 {broken} 条经验缺 signature.keywords（永远不会命中），"
                   f"运行 python scripts/vao.py dna --check 查看") if broken else ""
    if not scored or scored[0][0] <= 0:
        note = ("无匹配 DNA：从主题种子起步，发布 PASS 后运行 "
                "python scripts/vao.py dna --add <条目>.json 沉淀这条经验")
        if load_error:
            note += f"；经验库读取失败，已安全降级（{load_error}）"
        return {"matched": None, "confidence": 0.0, "dna": None,
                "alternatives": [], "note": note + broken_note, "broken_entries": broken,
                **({"load_error": load_error} if load_error else {})}
    conf, hits, best = scored[0]
    alts = [{"id": e.get("id"), "confidence": round(c, 2)}
            for c, h, e in scored[1:3] if c > 0]
    legacy_dna = best.get("dna") if isinstance(best.get("dna"), dict) else {}
    return {"matched": best.get("id"), "confidence": round(conf, 2),
            "dna": (best.get("judgment") or best.get("dna")),
            "design_problem": best.get("design_problem"),
            "avoid": best.get("avoid") or legacy_dna.get("forbidden"),
            "alternatives": alts,
            "proven": best.get("proven"),
            "broken_entries": broken,
            "note": (("DNA 是起点不是模板：按当前内容与受众重组，禁止照抄" if conf < 0.6
                      else "高置信命中：以该经验为基线，只做内容级调整") + broken_note)}

# ── 经验写入路径 ───────────────────────────────────────────────────────
# 记忆是判断的沉淀，不是参数表：judgment 只写「可迁移的行为判断」，色值/字号/版式结果
# 属于证据，放 proven.measurements。写错的记忆不会报错，只会永远命不中——所以写入时挡。

DNA_SCHEMA_NOTE = ("经验库（非参数库）：每条 = pattern（模式名）+ design_problem（当时矛盾）+ "
                   "judgment（可迁移的行为判断）+ works_because（为什么成立）+ avoid + when_not_to + "
                   "proven（实测证据）。judgment 只写行为判断，不写色值/字号/版式结果——"
                   "结果是证据，放 proven.measurements。")

_HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{3,8}\b")

def validate_dna_entry(entry) -> tuple[list, list]:
    """一条经验 → (errors, warnings)。errors 拒绝写入，warnings 只提醒。"""
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
        errors.append("缺 signature.keywords：召回只按关键词打分，空 = 这条经验永远命不中")
    if isinstance(judgment, dict):
        leaked = [str(k) for k in judgment if str(k) in RESULT_MEMORY_KEYS]
        if leaked:
            errors.append(f"judgment 里出现结果键 {leaked}：色值/字体/版式结果属于证据，"
                          f"请移到 proven.measurements")
        unknown = sorted(str(k) for k in judgment
                         if str(k) not in JUDGMENT_KEYS and str(k) not in RESULT_MEMORY_KEYS)
        if unknown:
            errors.append(f"judgment 维度 {unknown} 不在合法维度内：{sorted(JUDGMENT_KEYS)}")
    hexes = sorted({h for leaf in _leaf_strings(judgment) for h in _HEX_COLOR.findall(leaf)})
    if hexes:
        errors.append(f"judgment 里写死了色值 {hexes}：判断要与具体值解耦，"
                      f"证据放 proven.measurements")
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
    """经验库体检：结构问题点名到条目，返回 {ok, entries, errors, warnings}。"""
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

def record_dna(entry, path=None, replace: bool = False) -> dict:
    """写入一条经验：校验 → 去重 → 原子替换。返回 {added, id, errors, warnings, …}。

    写坏记忆比不写更贵（它会被当成经验参与判断），因此：结构不合法一律拒收；
    库文件损坏时拒写（避免把空库整体写回、经验全灭）；写盘走临时文件 + 原子替换。
    """
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
        return {"added": False, "id": eid, "errors": ["同 id 条目已存在且内容不同："
                                                      "确认覆盖时加 --replace"],
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
            "warnings": warnings,
            "note": f"{action} {eid} · 经验库现有 {len(entries)} 条"}

def _leaf_strings(v):
    """递归产出 judgment 值内全部叶子字符串（嵌套 dict/list 藏不了色值）。"""
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _leaf_strings(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _leaf_strings(x)

# ════════════════════════════════════════════════════════════════════════
# ② Media Decision Model
# ════════════════════════════════════════════════════════════════════════
# 媒体模型与家族别名表 → design_intelligence_rules（MEDIA_MODEL/FAMILY_ALIASES）。

def normalize_family(raw) -> str:
    """家族名归一（内容家族 COVER/DATA_STORY… → route/媒体家族 HERO/DATA…）。

    两套命名的单一映射源：media_decision / normalize_family
    都经此归一，禁止各自维护别名表（漂移的别名表 = 判断不一致）。
    """
    up = str(raw or "").strip().upper()
    return _FAMILY_ALIASES.get(up, up)

def media_decision(page: dict) -> dict:
    """页面 → 媒体决策（置信度 + 理由，而非布尔闸门）。

    输入含 elements 时做覆盖判定：已有图表的页降为「图表即锚点」；
    已有 layer=background 画心时记「画心已承担」。"""
    page = page if isinstance(page, dict) else {}
    raw_intent = page.get("page_intent") if isinstance(page.get("page_intent"), dict) else {}
    raw = str(raw_intent.get("page_family") or "").upper()
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

# ── Page Intent Skeleton（标准家族的意图骨架，AI 只填洞 ──────────
# 生成速度的大头不是渲染（毫秒级），是每页重新推理。骨架把「家族决定得了的」
# （能量/密度/负空间职责/阅读序）确定性给出，AI 只填「内容决定得了的」
# （insight / focus）；显式覆盖永远赢。deck 级判断见 route.deck_decision。

def resolve_family(family: str) -> str:
    """家族名解析：route 家族名（COVER / DATA_STORY …）优先，其次 di 归一名（HERO / DATA …）。

    两套命名空间都必须认。只认一套时，表里的条目会静默落空、整页退回兜底句——
    那是最贵的错：判断看起来发生了，其实没有。
    """
    raw = str(family or "").strip().upper()
    if raw in FAMILY_TOKENS:
        return raw
    fam = normalize_family(family)
    if fam in FAMILY_TOKENS:
        return fam
    return raw

def page_intent_skeleton(family: str, insight: str = "", focus: str | None = None,
                         **overrides) -> dict:
    """家族 + 已决策的密度/能量 → 页面意图骨架（确定性；不给的值就不写）。

    density / energy 由 route 的路由表决定，这里**不再自持第二张表**：两处各写一份，
    迟早会给出互相矛盾的两页（曾经 s02 的注释说 low、骨架说 high）。
    insight / focus 由生成侧按内容填；显式覆盖永远赢。

    刻意只有两个待填槽：**这页的唯一结论**（insight）与**视线第一落点**（focus）。
    曾经还有 rhythm_stage / empty_space_role / reading_order 三个字段——引擎自己
    发明、没人读取（reading_order 就是 focus 的复述）。写的人要在三个空字段里做
    三个假决定，读的人多读三行：删掉它们，判断反而更集中在真正重要的那句上。
    """
    base = {"insight": insight, "focus": focus,
            "page_family": str(family or "").strip().upper()}
    base.update({k: v for k, v in overrides.items() if v not in (None, "")})
    return base

def color_plan(direction, brief: dict | None = None) -> dict:
    """自适应色彩智能：内容 × DNA × 情绪 → 比例目标 + 约束 + 种子骨架。

    派生顺序（判断，不是模板）：brand_colors > visual_world 材质/光性 >
    方向种子骨架。返回的约束来自参考空间实测律（色相族/饱和/明度域）。
    """
    brief = brief if isinstance(brief, dict) else {}
    fam = str(brief.get("color_family") or "")
    if not fam:
        raw = direction if isinstance(direction, str) else str(
            (direction or {}).get("family") or (direction or {}).get("design_direction") or "")
        fam = _DIRECTION_ALIAS.get(raw, raw)
    entry = COLOR_DIRECTIONS.get(fam) or COLOR_DIRECTIONS["quiet_luxury"]
    fam_key = fam if fam in COLOR_DIRECTIONS else "quiet_luxury"
    brief = brief or {}
    brand = brief.get("brand_colors") or {}
    seed = dict(entry["seed"])
    seed_source = "family_seed"
    # 列表写法（templates/brief.yml 教的就是列表）与 dict 写法收敛到同一口径：
    # route._seed_from_brand 是唯一归一入口，两处各写一份解析必然分叉——
    # 那正是「品牌色在 plan.theme 生效、在 color_plan 却没生效」这类半生效 bug 的来源。
    from route import normalize_brand_colors
    brand = normalize_brand_colors(brand)
    if brand:
        # 键名驱动（v4.9 V1）：品牌声明的是「槽位名 → 色值」；槽位白名单 +
        # #HEX 校验，未知键与非色值一律忽略。禁止按值序强填——dict.values()
        # 的插入顺序不是语义，accent 被塞进 foundation 即此类 bug。
        # 通用 token 别名（v4.14 F3）：品牌方常以 ink/primary/secondary/muted
        # 表达主辅色——路由侧 colors 词典收全 token、本侧四槽是语义骨架，
        # 不做别名则「只给 primary 的品牌」在本路静默失效。
        #
        # 槽位语义必须按**面积律**对齐（COLOR_RATIO_TARGETS）：
        #   foundation  70% = 纸面/背景     information 8% = 文字墨色
        #   supporting  20% = 辅助层        accent      2% = 唯一强调
        # 因此 ink/primary（品牌的墨色与主色，用来写字）归 information，
        # background/paper 才归 foundation。此前 ink/primary → foundation 是
        # 语义倒置：品牌给一个深蓝主色，会被当成 70% 的背景铺满整页，
        # 再配上近黑的 information，得到对比度 1.4 的不可读版面——
        # 而且不报错（色值确实"生效"了，只是落错了槽）。
        _ALIAS = {"ink": "information", "primary": "information",
                  "information": "information",
                  "secondary": "supporting", "muted": "supporting",
                  "supporting": "supporting",
                  "accent": "accent",
                  "background": "foundation", "paper": "foundation",
                  "foundation": "foundation"}
        valid = {}
        for k, v in brand.items():
            slot = _ALIAS.get(str(k).strip())
            if (slot and isinstance(v, str) and v.strip().startswith("#")
                    and len(v.strip()) in (4, 7) and slot not in valid):
                valid[slot] = v.strip()
        if valid:
            seed.update(valid)
            seed_source = "brand_colors"
    return {
        "family": fam_key,
        "seed_skeleton": seed,
        "seed_source": seed_source,
        "material_language": entry["material"],
    }
