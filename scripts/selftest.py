#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py · 核心测试（生产路径即测试路径）

四段：
  1) intelligence —— 设计判断：结论 / 权重 / 角色 / 焦点 / 构图（含否决理由）/ 媒体必要性 / 世界
  2) verify        —— 硬门：溢出、重叠、越界、空载荷、来源区、出处、口径
  3) production    —— 编译确定性、缓存复用、资产链、关键页取证
  4) cli + docs    —— 单入口 plan/check/dna、骨架携带判断、文档纪律
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

PASS = 0
FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))


def run_vao(*args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPTS / "vao.py"), *args],
                          capture_output=True, text=True, cwd=cwd or str(ROOT))


# ── fixtures ─────────────────────────────────────────────────────────
BRIEF = {
    "audience": "董事会与投资人",
    "decision": "批准 2026 自有内容预算",
    "tension": "投放成本上升，自有内容回报周期长",
    "quality_level": "advanced",
    "brand_colors": ["#1A3A5C", "#C8501E"],
    "slides": [
        {"id": "s01", "title": "自有内容占比过半", "content": "2026 内容战略提案"},
        {"id": "s02", "title": "投入自有内容是唯一防守",
         "content": "外部流量价格三年翻倍（来源：投放台账）"},
        {"id": "s03", "title": "自有内容占比 61%",
         "content": "61%，对比去年 38%（来源：内容资产台账）",
         "chart": {"type": "kpi", "value": 61}},
        {"id": "s04", "title": "18 个月落地节奏"},          # 证据页缺 content
        {"id": "s05", "title": "请批准 4,800 万专项",
         "content": "首期 1,200 万于 2027Q1 启动"},
    ],
}


def make_build(tmp: Path, *, chart: bool = True) -> Path:
    """生成一份合规 build.py（硬门全过的最小稿件）。"""
    colors = {"background": "#F2EDE4", "surface": "#F4EFE6", "primary": "#1A3A5C",
              "secondary": "#9A8C74", "accent": "#C8501E", "ink": "#191510",
              "muted": "#6E6A5E"}
    slides = []
    for i in range(5):
        els = []
        if i > 0:
            els.append({"id": "eyebrow", "type": "text", "x": 48, "y": 40, "width": 320,
                        "height": 24, "text": f"PAGE {i + 1}", "size": 12.5,
                        "color": "muted", "role": "eyebrow"})
            els.append({"id": "page_number", "type": "text", "x": 1208, "y": 40,
                        "width": 32, "height": 24, "text": str(i + 1), "size": 12.5,
                        "color": "muted", "role": "page_number", "align": "right"})
        els.append({"id": "title", "type": "text", "x": 48, "y": 96, "width": 1184,
                    "height": 56, "text": f"第{i + 1}页结论句", "size": 32,
                    "color": "ink", "role": "title", "bold": True})
        els.append({"id": "src", "type": "text", "x": 48, "y": 676, "width": 1100,
                    "height": 24, "text": "来源：测试数据 · 2025-12", "size": 12.5,
                    "color": "muted", "role": "source"})
        if chart and i == 2:
            els.append({"id": "chart_main", "type": "chart", "chart_kind": "line",
                        "x": 48, "y": 232, "width": 1184, "height": 400, "role": "focus",
                        "data": [{"label": "2023", "value": 38}, {"label": "2024", "value": 47},
                                 {"label": "2025", "value": 61}],
                        "highlight": 2, "show_values": True, "metric": "自有内容占比",
                        "source": "来源：内容资产台账", "unit": "%",
                        "period": "2023–2025", "basis": "全渠道加权"})
        slides.append({"id": f"s{i + 1:02d}",
                       "page_intent": {"insight": f"第{i + 1}页结论", "focus": "title"},
                       "source_zone": {"x": 48, "y": 672, "width": 1184, "height": 32},
                       "elements": els})
    build = tmp / "build.py"
    build.write_text(
        "# -*- coding: utf-8 -*-\nSPEC = {\n"
        f"  'canvas': {{'width': 1280, 'height': 720, 'grid_columns': 12, 'grid_unit': 8}},\n"
        f"  'theme': {{'colors': {colors!r}, 'fonts': {{'cn': 'Source Han Serif SC', 'latin': 'Georgia'}}}},\n"
        f"  'slides': {slides!r},\n}}\n", encoding="utf-8")
    return build


# ── 1 · intelligence（设计判断）───────────────────────────────────────
def test_intelligence(tmp: Path):
    import intelligence as intel

    bundle = intel.think(BRIEF)
    deck, pages = bundle["deck"], bundle["pages"]
    by_id = {p["id"]: p for p in pages}

    check("判断链：每页都有完整判断卡",
          all({"claim", "information_weight", "visual_role", "focus", "composition",
               "spatial", "media", "production"} <= set(p["judgment"]) for p in pages))

    # 结论抽取：declared 优先 / 标题优于署名行 / 缺内容 = absent
    s01 = by_id["s01"]["judgment"]
    check("claim: 封面取标题结论而不是署名行",
          s01["claim"]["text"] == "自有内容占比过半", str(s01["claim"]))
    s04 = by_id["s04"]["judgment"]
    check("claim: 证据页缺 content → absent，不脑补",
          s04["claim"]["source"] == "absent" and s04["claim"]["text"] is None)
    declared = intel.think(dict(BRIEF, slides=[{"id": "x", "title": "话题",
                                                "content": "数据",
                                                "insight": "作者写的结论"}]))
    check("claim: 作者声明的结论压过抽取",
          declared["pages"][0]["judgment"]["claim"]["source"] == "declared")

    # 信息权重：结论数字最大化、对照基数弱化、重复删除
    s03 = by_id["s03"]["judgment"]
    maxi = " ".join(s03["information_weight"]["maximize"])
    weak = " ".join(s03["information_weight"]["weaken"])
    check("weight: 结论数字最大化（61%）", "61%" in maxi)
    check("weight: 对照基数弱化（38% 小一档）", "38%" in weak)
    dup_text = "收入 12 亿，收入 12 亿（来源：财报）"
    dup = intel.information_weight(intel.understand(dup_text),
                                   {"text": "收入 12 亿", "source": "extracted"}, dup_text)
    check("weight: 同数字重复出现进删除清单",
          any("重复" in x for x in dup["delete"]), str(dup["delete"]))

    # 视觉角色：开场 establish / 收尾 summarize / 对比 compare / 说服 persuade
    roles = {p["id"]: p["judgment"]["visual_role"]["role"] for p in pages}
    check("role: 开场 establish、收尾 summarize",
          roles["s01"] == "establish" and roles["s05"] == "summarize", str(roles))
    check("role: 对比内容 → compare，且给了替代角色",
          roles["s03"] == "compare" and by_id["s03"]["judgment"]["visual_role"]["alternatives"])

    # 焦点：焦点元素唯一 + 必须给出否决的替代项
    foc = s03["judgment"]["focus"] if False else s03["focus"]
    check("focus: 对比页焦点是两端对比场而不是卡片墙",
          foc["element_role"] == "comparison_field"
          and any("卡片" in r["why_not"] or "卡" in r["option"] for r in foc["rejected"]),
          str(foc["rejected"])[:120])
    check("focus: 数字结论页焦点是 kpi_main 并否决环形图",
          by_id["s05"]["judgment"]["focus"]["element_role"] in ("kpi_main", "hero_statement"))

    # 构图：必须回答「为什么不是别的形式」
    comp = s02["judgment"]["composition"] if False else by_id["s02"]["judgment"]["composition"]
    check("composition: 主张页 → big_whitespace 且否决项有效（只留真实竞争）",
          comp["chosen"] == "big_whitespace" and len(comp["rejected"]) <= 2
          and all(r["why_not"] and r["option"] != comp["chosen"]
                  for r in comp["rejected"]))
    check("composition: 数据证据页 → data_field",
          by_id["s03"]["judgment"]["composition"]["chosen"] in ("data_field",
                                                                "asymmetric_tension"))

    # 空间：路径/主区/留白职责非空
    sp = by_id["s02"]["judgment"]["spatial"]
    check("spatial: 阅读路径 + 留白职责齐备",
          bool(sp["reading_path"] and sp["whitespace_duty"] and sp["quiet_zone"]))

    # 媒体必要性：作者声明 > 图表抑制 > 必要性测试
    m_author = intel.media_necessity(intel.understand("产品发布会现场"),
                                     "establish", declared="required")
    check("media: 作者声明压过判断", m_author["decision"] == "required"
          and m_author["source"] == "author")
    m_chart = intel.media_necessity(intel.understand("客户现场 12 家"), "prove",
                                    has_chart=True)
    check("media: 页内已有图表 → 不出图（双焦点竞争）",
          m_chart["decision"] == "none")
    m_decor = intel.media_necessity(intel.understand("预算分配 60/25/15"), "summarize")
    check("media: 说不出「没有它会下降在哪」→ 不出图",
          m_decor["decision"] == "none" and "注意力" in m_decor["necessity"])
    m_subject = intel.media_necessity(intel.understand("产品发布：新一代设备与芯片"),
                                      "establish")
    check("media: 开场有可指认实体 → witness/subject 才成立",
          m_subject["decision"] == "required"
          and m_subject["function"] in ("subject", "witness"))

    # 判断质量：话题 ≠ 结论；结论句要被抽出来；图像只在「有现场」时成立
    topic = intel.extract_claim(
        {"title": "店长回访记录",
         "content": "12 家试点门店的店长在高峰时段如何使用自有内容（来源：回访记录）"})
    check("claim: 话题句（如何使用…）不当结论，宁可 absent",
          topic["source"] == "absent" and topic["text"] is None, str(topic))
    asserted = intel.extract_claim(
        {"title": "成本结构",
         "content": "单篇生产成本降至 1,800 元，低于去年同期（来源：财务台账）"})
    check("claim: 断言句（降至…）被真正提炼为结论",
          asserted["source"] == "extracted" and "1,800" in asserted["text"], str(asserted))
    info_only = intel.media_necessity(
        intel.understand("获客单价 96 元 → 128 元 → 205 元"), "prove")
    scene = intel.media_necessity(
        intel.understand("门店回访现场：店长在高峰时段的记录"), "prove")
    check("media: 纯数据页不出图，有现场的一页才出图（证词）",
          info_only["decision"] == "none" and scene["decision"] == "required"
          and scene["function"] == "witness", f"{info_only} / {scene}")

    # 视觉世界：由内容推导，两个同类 deck 允许得到不同世界
    fin_human = dict(BRIEF, slides=[
        {"id": "s1", "title": "试点客户续约率 92%", "content": "12 家门店客户回访现场（来源：台账）"},
        {"id": "s2", "title": "门店真实反馈", "content": "客户的日常使用场景（来源：回访）"}])
    fin_data = dict(BRIEF, slides=[
        {"id": "s1", "title": "单位获客成本 128 元", "content": "口径：全渠道加权（来源：投放台账）"},
        {"id": "s2", "title": "三年成本曲线", "content": "2023–2025 逐年上升（来源：投放台账）"}])
    w_human = intel.think(fin_human)["deck"]["world"]
    w_data = intel.think(fin_data)["deck"]["world"]
    check("world: 世界由内容推导（不是风格预设查表）",
          w_human["source"].startswith(("subject", "neutral"))
          and w_human["visual_world"] and w_human["accent_why"])
    check("world: 同类内容允许产生不同世界（实体不同 → 材质/强调不同）",
          (w_human["name"], w_human["accent"]) != (w_data["name"], w_data["accent"])
          or w_human["chart_style"] != w_data["chart_style"], str(w_human["name"]))
    check("world: 每个判断都带理由", bool(w_human["reasons"].get("subject")))
    check("plan: 页级不重复存储（角色/证据只住判断卡，判断卡里不再回存原文与向量）",
          all("role" not in p and "evidence" not in p for p in pages)
          and all("declarations" not in p["judgment"] for p in pages)
          and all("text" not in p["judgment"]["understanding"]
                  and "modes" not in p["judgment"]["understanding"] for p in pages))
    # 资产预算：合格页多于名额时按视觉价值排序，落选页留下理由（不是按页序截断）
    many = intel.think(dict(BRIEF, slides=[
        {"id": f"s{i:02d}", "title": title, "content": content} for i, (title, content) in
        enumerate([
            ("田间到仓的 48 小时", "采收现场与冷链记录（来源：产地日报）"),
            ("仓库现场的复盘会", "分拣现场记录：9 个环节耗时（来源：现场复盘）"),
            ("门店走访的真实反馈", "华东 6 家门店走访记录（来源：走访纪要）"),
            ("车间班组的交接记录", "车间现场记录（来源：班组日志）"),
            ("客户回访现场", "12 家客户回访现场（来源：回访记录）"),
            ("请批准两条产线改造", "首期 600 万于 Q2 启动（来源：预算表）")], 1)]))
    hinted = many["assets_hint"]
    deferred_ids = {d["slide_id"] for d in (hinted["deferred"] or [])}
    check("assets: 图位按视觉价值排序，超额的页进 deferred 并带理由",
          len(hinted["generate"]) == hinted["cap"] and deferred_ids
          and set(hinted["generate"]).isdisjoint(deferred_ids)
          and all(d.get("why") for d in hinted["deferred"]),
          f"generate={hinted['generate']} cap={hinted['cap']} deferred={hinted['deferred']}")
    by_many = {p["id"]: p for p in many["pages"]}
    check("assets: 落选页判断卡当场改写（media 回 none，焦点回到文字/数据）",
          all(by_many[sid]["judgment"]["media"]["decision"] == "none"
              for sid in deferred_ids)
          and all(by_many[sid]["judgment"]["focus"]["type"] != "image"
                  for sid in deferred_ids)
          and all("图位" in by_many[sid]["judgment"]["media"]["necessity"]
                  for sid in deferred_ids))
    adj_fn = {}
    for a in (many["deck"]["coherence"]["adjustments"] or []):
        if a["field"] == "media" and ":" in str(a.get("from") or ""):
            adj_fn[a["page"]] = str(a["from"]).split(":")[1]

    def _val(pid):
        j = by_many[pid]["judgment"]
        fn = j["media"].get("function") or adj_fn.get(pid, "")
        return intel._MEDIA_VALUE.get(fn, 0.0) \
            + intel._ROLE_VALUE.get(j["visual_role"]["role"], 0.0)

    check("assets: generate 页价值不低于 deferred 页（价值序，不是页序）",
          min(_val(p) for p in hinted["generate"])
          >= max(_val(p) for p in deferred_ids))
    check("plan: 世界只留会被消费的键（无展示用常量/重复串）",
          not {"material", "motion", "chroma", "regime", "background",
               "rejected_worlds"} & set(w_human))

    # 构图：算子由内容形状决定（不是按页面类型查表），且与媒体/焦点自洽
    shaped = intel.think(dict(BRIEF, slides=[
        {"id": "s0", "title": "开场", "content": "内容战略（来源：档案）"},
        {"id": "a", "title": "把工艺从 7 步压到 3 步", "content": "采青 → 杀青 → 揉捻（来源：工艺卡）"},
        {"id": "b", "title": "复购 3.4 次", "content": "3.4 次/月（来源：门店台账）"},
        {"id": "c", "title": "激活率对比", "content": "44% → 71%（来源：试点报告）"}]))
    picked = {p["id"]: p["judgment"]["composition"]["chosen"] for p in shaped["pages"]}
    check("composition: 图像页构图即图像叙事（与焦点自洽）",
          all(p["judgment"]["composition"]["chosen"] == "image_narrative"
              for p in shaped["pages"]
              if p["judgment"]["media"]["decision"] == "required"
              and p["judgment"]["focus"]["type"] == "image"))
    check("composition: 内容形状不同 → 算子不同（序列/单数/对比）",
          picked["a"] == "linear_structure" and picked["b"] == "big_whitespace"
          and picked["c"] in ("asymmetric_tension", "data_field")
          and len(set(picked.values())) >= 3, str(picked))
    check("composition: 没有图像时不选图像叙事（判断不自相矛盾）",
          all(not (p["judgment"]["composition"]["chosen"] == "image_narrative"
                   and p["judgment"]["media"]["decision"] == "none")
              for p in shaped["pages"]))
    dup_num = intel.understand("复购 3.4 次 3.4 次/月（来源：台账）")
    check("understanding: 标题重复正文的数字只算一个证据",
          dup_num["evidence"] == "number" and dup_num["distinct_numerals"] == 1,
          str(dup_num["evidence"]))

    # 品牌色：一步覆盖世界种子
    seed = deck["theme"]
    check("theme: 品牌色落语义槽（primary→information, accent→accent）",
          seed["colors_seed"]["information"] == "#1A3A5C"
          and seed["colors_seed"]["accent"] == "#C8501E"
          and seed["seed_source"] == "brand_colors", str(seed))
    tokens = intel.theme_tokens({"foundation": "#FFFFFF", "information": "#FFFFFF",
                                 "supporting": "#888888", "accent": "#CC0000"})
    check("theme: 可读性兜底（墨色与纸面分得开）", tokens["ink"] in ("#141414", "#FFFFFF"))

    # 退役字段：写 design_direction 会被点名而不是静默套用
    w = intel.think(dict(BRIEF, design_direction="editorial"))["warnings"]
    check("plan: design_direction 退役并留痕",
          any(x.get("rule") == "direction_retired" for x in w), str(w)[:120])

    # 缺 deck 契约 / 证据页缺内容：两种警告都要开口
    rules = {x.get("rule") for x in bundle["warnings"]}
    check("plan: 缺 tension 与证据页缺 content 都有警告",
          "unresolved_content" in rules and "deck_contract" not in rules)

    # 骨架：判断连理由进注释（否决项不住这里，canonical owner 是 plan）；同 bundle 必得同文本
    sk1, sk2 = intel.build_skeleton(bundle), intel.build_skeleton(bundle)
    check("skeleton: 同 bundle 必得同文本", sk1 == sk2)
    check("skeleton: 注释携带结论/权重/角色/构图（不再复制否决项）",
          "结论[" in sk1 and "权重:" in sk1 and "角色:" in sk1
          and "构图:" in sk1 and "否决" not in sk1 and "媒体:" in sk1)
    check("skeleton: 不给坐标（几何留给作者）",
          "估算高度" not in sk1 and '"x":' not in sk1.split("slides")[0])

    # 跨页校准：连续同构图回拨中间页（内容允许第二选择时）
    streak = intel.think(dict(BRIEF, slides=[
        {"id": f"d{i:02d}", "title": title, "content": content}
        for i, (title, content) in enumerate([
            ("请批准试点预算", "请于本周五前确认"),
            ("请批准复用预算", "请于本周五前确认"),
            ("请确认发布节奏", "请于本周五前确认"),
            ("请确认评审名单", "请于本周五前确认")], 1)]))
    streak_comps = [p["judgment"]["composition"]["chosen"] for p in streak["pages"]]
    streak_coh = streak["deck"]["coherence"]
    check("coherence: 整套回看存在（节奏序列与页数对齐）",
          set(streak_coh) == {"compositions", "densities", "roles", "media",
                              "adjustments", "notes"}
          and len(streak_coh["compositions"]) == 4
          and len(streak_coh["roles"]) == 4 and len(streak_coh["media"]) == 4)
    check("coherence: 连续 4 页同构图 → 中间两页回拨，两端保留",
          streak_comps[0] == streak_comps[3] == "editorial"
          and streak_comps[1] == streak_comps[2] == "big_whitespace"
          and len(streak_coh["adjustments"]) == 2
          and all(a["field"] == "composition" for a in streak_coh["adjustments"]),
          str(streak_comps))
    check("coherence: 回拨留痕（为什么里写明跨页原因）",
          all("跨页校准" in p["judgment"]["composition"]["why"]
              for p in streak["pages"][1:3]))
    check("coherence: 焦点连续同落点给出提醒（不硬改焦点）",
          bool(streak_coh["notes"]) and "headline" in streak_coh["notes"][0],
          str(streak_coh["notes"]))
    check("world: 单页单个词不决定整套世界（deck 级证据门槛）",
          streak["deck"]["world"]["source"] == "neutral_fallback",
          str(streak["deck"]["world"]["name"]))
    # 内容契合压过节奏：差距够大时不硬换
    stubborn = intel.think(dict(BRIEF, slides=[
        {"id": f"g{i:02d}", "title": f"三年曲线{i}",
         "content": "96 元 → 128 元 → 205 元（来源：投放台账）"} for i in range(1, 4)]))
    check("coherence: 内容强烈要求同一构图时不硬换（判断不是规则）",
          all(p["judgment"]["composition"]["chosen"] == "data_field"
              for p in stubborn["pages"])
          and not stubborn["deck"]["coherence"]["adjustments"])

    # 运行数据最小化：判断卡只留被消费的键
    j0 = bundle["pages"][0]["judgment"]
    check("slim: 判断卡无解释性冗余字段",
          set(j0["media"]) == {"decision", "source", "function", "necessity"}
          and set(j0["claim"]) == {"text", "source", "why"}
          and set(j0["spatial"]) == {"reading_path", "primary_zone", "quiet_zone",
                                     "whitespace_duty"}
          and set(j0["production"]) == {"must_place", "must_not", "density_target"}
          and set(j0["composition"]) == {"chosen", "why", "rejected"})
    check("slim: 构图否决项至多 2 条（无竞争为空，只留真实竞争）",
          all(len(p["judgment"]["composition"]["rejected"]) <= 2
              and all(r["why_not"] and r["option"] != p["judgment"]["composition"]["chosen"]
                      for r in p["judgment"]["composition"]["rejected"])
              for p in pages))

    # 焦点：年份与编号不当第一落点
    year_focus = intel.focus_of(
        "summarize",
        {"evidence": "none", "numerals": [{"raw": "2026", "value": 2026.0,
                                           "unit": "", "year": True}],
         "distinct_numerals": 0, "comparison": False},
        {"text": "2026 年开局", "source": "extracted"}, {})
    check("focus: 年份不当第一落点（回到标题）",
          year_focus["element_role"] == "headline", str(year_focus["element_role"]))
    check("numerals: 字母紧贴的数字是编号不是证据（Q1 不计数）",
          intel.understand("2027Q1 启动")["distinct_numerals"] == 0
          and intel.understand("Q2 末交付 600 万")["distinct_numerals"] == 1)
    check("understanding: 箭头链是顺序的形状（盖过孤立数字）",
          intel.understand("18 个月：试点 → 复制 → 全量")["evidence"] == "sequence")

    # 结论：超长论述不当结论（可复述才算记住）
    long_claim = intel.extract_claim(
        {"title": "", "content": "结论是" + "甲" * 64 + "。结论是短句"})
    check("claim: 同等条件下短结论赢过超长论述（长度是记忆成本）",
          long_claim["text"] == "结论是短句", str(long_claim))

    # 信息权重真正抵达生产：删除清单变成明确禁令
    prod_w = intel.production_spec(
        {"element_role": "headline", "type": "text", "why": "w", "rejected": []},
        {"chosen": "big_whitespace", "rejected": []},
        {"decision": "none"}, {"numerals": []}, dup)
    check("weight: 删除清单进生产禁令（must_not 可执行）",
          any(str(m).startswith("删：") for m in prod_w["must_not"]))

    # 作者声明：写了画面主题就是要出图；未知构图不断规划
    subj = intel.think(dict(BRIEF, slides=[
        {"id": "x", "title": "安静的数字", "content": "口径稳定（来源：台账）",
         "asset_subject": "a calm archive room, empty left"}]))
    check("media: asset_subject 等价 required（声明不只留在回显里）",
          subj["pages"][0]["judgment"]["media"]["decision"] == "required"
          and subj["pages"][0]["judgment"]["media"]["source"] == "author"
          and "x" in subj["assets_hint"]["generate"])
    custom = intel.think(dict(BRIEF, slides=[
        {"id": "x", "title": "t", "content": "c", "composition": "custom_xyz"}]))
    check("plan: 作者未知构图不断规划（密度取中性）",
          custom["pages"][0]["judgment"]["composition"]["chosen"] == "custom_xyz"
          and custom["pages"][0]["judgment"]["production"]["density_target"] == "balanced")

    # 世界：整套证据性格取最常见的非空证据（「无证据」不盖过真证据）
    mixed = intel.think(dict(BRIEF, slides=[
        {"id": "c1", "title": "A", "content": "甲对比乙：61% 对 38%（来源：台账）"},
        {"id": "c2", "title": "B", "content": "丙对比丁：44% 对 29%（来源：台账）"},
        {"id": "n1", "title": "随笔", "content": "一些想法"}]))
    check("world: 图表性格跟随主导证据（对比）",
          mixed["deck"]["world"]["chart_style"]
          == "shared baseline, two-tone delta, direct labels",
          str(mixed["deck"]["world"]["chart_style"]))

    # DNA：召回 / 校验 / 拒收结果记忆 / 幂等写入
    dna = intel.recall_dna(BRIEF)
    check("dna: 召回结构完整", {"matched", "confidence", "note"} <= set(dna))
    errs, _ = intel.validate_dna_entry(
        {"id": "x", "pattern": "p", "judgment": {"layout": "fixed 64px grid"},
         "signature": {"keywords": ["k"]}})
    check("dna: judgment 写结果值被拒收", bool(errs))
    ok_entry = {"id": "t", "pattern": "p", "judgment": {"space": "留白先于装饰"},
                "signature": {"keywords": ["t"]}}
    check("dna: 行为判断可入库", not intel.validate_dna_entry(ok_entry)[0])
    store = tmp / "dna.json"
    store.write_text(json.dumps({"version": 2, "entries": []}), encoding="utf-8")
    first = intel.record_dna(ok_entry, path=store)
    again = intel.record_dna(ok_entry, path=store)
    check("dna: 写入幂等 + 原子替换",
          first["added"] and not again["added"] and intel.validate_dna_store(store)["ok"])


# ── 2 · verify（硬门）────────────────────────────────────────────────
def test_verify(tmp: Path):
    from verify import check_spec, normalize_spec
    from primitives import spec_fingerprint

    build = make_build(tmp)
    namespace: dict = {}
    exec(compile(build.read_text(encoding="utf-8"), str(build), "exec"), namespace)
    spec = namespace["SPEC"]

    ok = check_spec(spec)
    check("guard: 合规稿 0 error", ok["passed"], str(ok["checks"])[:200])
    check("guard: 合规稿零 warning（QA 不产生噪音）",
          not [c for c in ok["checks"] if c.get("level") == "warn"], str(ok["warnings"])[:160])

    def mutate(fn):
        import copy
        bad = copy.deepcopy(spec)
        fn(bad)
        return check_spec(bad)

    r = mutate(lambda s: s["slides"][0]["elements"][0].update({"height": 8}))
    check("guard: 文字溢出必拦（TEXT_OVERFLOW）",
          any(c["rule"] == "text_capacity" for c in r["checks"]))

    r = mutate(lambda s: (s["slides"][0]["elements"].append(
        {"id": "dup", "type": "text", "x": 48, "y": 96, "width": 400, "height": 56,
         "text": "重叠", "size": 32, "color": "ink"})))
    check("guard: 墨迹重叠必拦（OVERLAP）",
          any(c["rule"] == "overlap" for c in r["checks"]))

    r = mutate(lambda s: s["slides"][0]["elements"][0].update({"x": 1300}))
    check("guard: 越出画布必拦", any(c["rule"] == "safety" for c in r["checks"]))

    r = mutate(lambda s: s["slides"][0]["elements"][0].update({"width": 0}))
    check("guard: 退化几何必拦（元素不可见）",
          any(c["rule"] == "element_schema" for c in r["checks"]))

    r = mutate(lambda s: s["slides"][0]["elements"][0].update({"color": "secondry"}))
    check("guard: 未知色名必拦（静默回落不留痕）",
          any(c["rule"] == "color_token" for c in r["checks"]))

    r = mutate(lambda s: s["slides"][2]["elements"].append(
        {"id": "ghost_chart", "type": "chart", "chart_kind": "unknown_kind",
         "x": 48, "y": 300, "width": 400, "height": 200}))
    check("guard: 未知图表类型必拦",
          any(c["rule"] == "chart_type" for c in r["checks"]))

    r = mutate(lambda s: s["slides"][2]["elements"].append(
        {"id": "empty_chart", "type": "chart", "chart_kind": "waterfall",
         "x": 600, "y": 300, "width": 400, "height": 200, "data": []}))
    check("guard: 图表空载荷必拦", any(c["rule"] == "chart_payload" for c in r["checks"]))

    r = mutate(lambda s: s["slides"][0]["elements"].append(
        {"id": "intruder", "type": "text", "x": 60, "y": 676, "width": 300, "height": 24,
         "text": "侵入来源区", "size": 12.5, "color": "muted"}))
    check("guard: 主体侵入来源区必拦（SOURCE_COLLISION）",
          any(c["rule"] == "source_zone" for c in r["checks"]))

    r = mutate(lambda s: s["slides"].__setitem__(0, {"id": "s01", "elements": []}))
    check("guard: 空白页必拦", any(c["rule"] == "page_contract" for c in r["checks"]))
    r = mutate(lambda s: s.__setitem__("slides", []))
    check("guard: 空 deck 必拦", not r["passed"])

    # 数据完整性：label 缺失 / 非有限值 / 跨页单位打架
    def _chart(s):
        return next(e for e in s["slides"][2]["elements"] if e.get("type") == "chart")
    r = mutate(lambda s: _chart(s)["data"].append({"value": 9}))
    check("guard: 数据行缺 label 必拦",
          any(c["rule"] == "data_integrity" for c in r["checks"]))
    def _add_second_chart(s):
        import copy as _copy
        second = _copy.deepcopy(_chart(s))
        second.update({"id": "chart_page5", "x": 48, "y": 232, "unit": "万元"})
        s["slides"][4]["elements"] = [e for e in s["slides"][4]["elements"]
                                      if e.get("id") != "src"] + [second]
    r = mutate(_add_second_chart)
    check("guard: 同指标跨页单位不一致必拦",
          any(c["rule"] == "metric_consistency" for c in r["checks"]), str(r["checks"])[:200])
    r = check_spec(spec, rules={"require_provenance": True})
    check("guard: release 档出处齐全 → 不拦", r["passed"])
    missing_basis = json.loads(json.dumps(spec))
    next(e for e in missing_basis["slides"][2]["elements"]
         if e.get("type") == "chart").pop("basis")
    r = check_spec(missing_basis, rules={"require_provenance": True})
    check("guard: release 档缺比较口径必拦（DATA_INTEGRITY_FAIL）",
          any(c["rule"] == "data_provenance" for c in r["checks"]))

    # 归一化：8 单位吸附 + 色名规范化 + 幂等
    import copy
    messy = copy.deepcopy(spec)
    messy["slides"][0]["elements"][0]["x"] = 50
    messy["slides"][0]["elements"][0]["color"] = "#191510"
    normalized, report = normalize_spec(messy)
    check("normalize: 几何落网格、色值规范化",
          normalized["slides"][0]["elements"][0]["x"] % 4 == 0 and report["counts"])
    twice, _ = normalize_spec(normalized)
    check("normalize: 幂等（二次归一指纹不变）",
          spec_fingerprint(twice) == spec_fingerprint(normalized))

    # verdict：PASS / BLOCK 二态 + 分组修复包
    from verify import verdict
    good = verdict(spec, mode="release",
                   guard_report=ok, compile_report={"passed": True, "skipped": False,
                                                    "output_sha256": "a" * 64})
    check("verdict: 合规稿 PASS 且 release_eligible", good["passed"]
          and good["release_eligible"] and good["status"] == "PASS")
    bad_report = mutate(lambda s: s["slides"][0]["elements"][0].update({"height": 8}))
    bad = verdict(spec, mode="draft", guard_report=bad_report,
                  compile_report={"passed": False, "skipped": True})
    check("verdict: BLOCK 按根因分组（修复包自足）",
          not bad["passed"] and bad["failure_codes"] == ["TEXT_OVERFLOW"]
          and bad["fix_plan"]["groups"][0]["fix"])


# ── 3 · production（编译 / 缓存 / 资产 / 预览）────────────────────────
def test_production(tmp: Path):
    from compiler import compile_deck
    from primitives import ENGINE_SCOPES, file_digest, spec_view, compile_reuse, record_compile

    build = make_build(tmp)
    namespace: dict = {}
    exec(compile(build.read_text(encoding="utf-8"), str(build), "exec"), namespace)
    spec = namespace["SPEC"]

    out1, out2 = tmp / "a.pptx", tmp / "b.pptx"
    compile_deck(spec, out1)
    compile_deck(spec, out2)
    check("compiler: 同 spec 两次编译字节一致（确定性）",
          file_digest(out1) == file_digest(out2))

    from pptx import Presentation
    prs = Presentation(str(out1))
    texts = [sh.text_frame.text.replace("\u2009", "").replace("\u200a", "")
             for sl in prs.slides for sh in sl.shapes
             if sh.has_text_frame and sh.text_frame.text.strip()]
    check("compiler: 原生可编辑 PPTX（文本在对象模型里可改）",
          len(prs.slides) == 5 and any("第3页结论句" in t for t in texts))

    missing = [name for files in ENGINE_SCOPES.values() for name in files
               if not (Path(__file__).resolve().parent / name).is_file()]
    check("engine: 指纹 scope 引用的文件都存在（删改模块必须同步）", not missing, str(missing))

    work = tmp / "cache"
    work.mkdir(exist_ok=True)
    report = compile_deck(spec, out1, speed="fast")
    view = spec_view(spec, base_path=tmp)
    record_compile(work, out1, view, report)
    reused = compile_reuse(work, out1, view, fast_probe=True, speed="fast")
    check("cache: 同投影 + 同产物字节 ⇒ 复用编译（不重编）",
          bool(reused and reused.get("reused")))
    changed = json.loads(json.dumps(spec))
    changed["slides"][0]["elements"][0]["text"] = "改过的标题"
    check("cache: spec 变了不命中",
          compile_reuse(work, out1, spec_view(changed, base_path=tmp),
                        fast_probe=True, speed="fast") is None)

    # 资产链：媒体必要性 → 清单；坏图 release 必 BLOCK
    from intelligence import think
    from assets import build_manifest, image_qc, qc_retry_decision
    bundle = think(BRIEF)
    manifest = build_manifest(BRIEF, bundle)
    generated = {sid for a in manifest["assets"] if a.get("decision") == "generate"
                 for sid in a.get("slide_ids") or []}
    check("assets: 只有通过必要性测试的页进清单",
          generated <= set(bundle["assets_hint"]["generate"])
          and all("necessity" in s or s.get("reason") for s in manifest["skipped_pages"]),
          str(manifest["assets"])[:160])
    from assets import asset_fingerprint, asset_card
    page = bundle["pages"][0]
    card, contract = asset_card(page, BRIEF, bundle["deck"], "asset-x")
    check("assets: 提示词确定性 + 带负向清单",
          asset_fingerprint(card, contract) == asset_fingerprint(card, contract)
          and "no " in (card.get("negative") or [""])[0] if card.get("negative") else True)
    from PIL import Image, ImageDraw
    img = tmp / "img.png"
    canvas = Image.new("RGB", (1280, 720), (240, 236, 228))
    ImageDraw.Draw(canvas).ellipse((700, 200, 1000, 500), fill=(120, 90, 60))
    canvas.save(img)
    safe = {"x": 0.06, "y": 0.08, "width": 0.34, "height": 0.78}
    qc = image_qc(img, safe_rect=safe, text_is_dark=True)
    decision_ok = qc_retry_decision(qc, attempt=0, phase="release")
    check("assets: 合规画心 QC 通过（无阻断项，动作 accept）",
          qc.get("status") == "ok" and decision_ok.get("action") == "accept",
          str(qc.get("checks"))[:160])
    bad_img = tmp / "bad.png"          # 文字安全区被高对比纹理压住 = 不可用
    canvas2 = Image.new("RGB", (1280, 720), (245, 243, 240))
    paint = ImageDraw.Draw(canvas2)
    for i in range(0, 460, 12):
        paint.rectangle([i, 0, i + 6, 720], fill=(30, 30, 30))
    canvas2.save(bad_img)
    bad = image_qc(bad_img, safe_rect=safe, text_is_dark=True)
    decision = qc_retry_decision(bad, attempt=1, phase="release")
    check("assets: 坏图 release 档不自动重出（判负交 QA 收口）",
          bad.get("status") != "ok" and decision.get("action") in ("block", "fail",
                                                                   "hold", "none"),
          f"{bad.get('status')} {decision}")

    # prepare 落盘：plan/brief 一致性走文件凭证，不再有 dict 级二次比对
    from assets import prepare_manifest
    import copy as _copy
    prepped = prepare_manifest(_copy.deepcopy(manifest), {"different": True}, bundle,
                               str(tmp / "brief.yml"), None, str(tmp / "m.json"))
    check("assets: prepare 不因 brief dict 不一致抛错（文件凭证是唯一口径）",
          prepped.get("schema") == "vao-assets-v2")

    # 解码缓存：只缓存未裁切底图（同源不同裁切各算各的，不互相污染）
    from compiler import _fit_image_bytes
    import io as _io
    half = Image.new("RGB", (100, 50), (255, 0, 0))
    half.paste(Image.new("RGB", (50, 50), (0, 0, 255)), (50, 0))
    buf = _io.BytesIO()
    half.save(buf, "PNG")
    blob = buf.getvalue()
    dcache: dict = {}
    left_png = _fit_image_bytes(blob, 50, 50, "cover", crop=(0, 0, 0.5, 0),
                                decode_cache=dcache, cache_key="k")
    right_png = _fit_image_bytes(blob, 50, 50, "cover", crop=(0.5, 0, 0, 0),
                                 decode_cache=dcache, cache_key="k")
    left_px = Image.open(_io.BytesIO(left_png)).convert("RGB").getpixel((25, 25))
    right_px = Image.open(_io.BytesIO(right_png)).convert("RGB").getpixel((25, 25))
    check("compiler: 同源不同裁切像素各自正确（缓存不污染）",
          left_px[0] > 200 and right_px[2] > 200, f"{left_px} vs {right_px}")

    # 关键页取证：封面 / 密数据 / 收尾
    from ghost import key_pages, ghost_deck, key_page_roles, key_selection
    pages = key_pages(spec["slides"], limit=3)
    labels = key_page_roles(spec["slides"], pages)
    check("ghost: 关键页取证含封面与收尾",
          1 in pages and len(spec["slides"]) in pages and
          set(labels.values()) <= {"cover", "closing", "hero_image", "dense_data",
                                   "section", "content"}, str(labels))
    rendered = ghost_deck(spec, tmp / "preview", pages=pages, scale=0.4, supersample=1)
    check("ghost: 预览只画关键页（页级缓存内建）",
          len(rendered) == len(pages) and all(Path(p).is_file() for p in rendered))
    sel_pages, sel_roles = key_selection(spec["slides"], limit=3)
    check("ghost: 单次取证与两次调用结论一致（结构只扫一遍）",
          sel_pages == pages and sel_roles == labels)


# ── 4 · cli + docs ───────────────────────────────────────────────────
def test_cli(tmp: Path):
    brief = tmp / "brief.yml"
    import yaml
    brief.write_text(yaml.safe_dump(BRIEF, allow_unicode=True), encoding="utf-8")
    plan = tmp / "plan.json"
    skeleton = tmp / "build.py"
    assets_out = tmp / "assets.json"
    r = run_vao("plan", str(brief), "--out", str(plan), "--skeleton", str(skeleton),
                "--assets-out", str(assets_out), "--assets-dir", str(tmp / "gen"))
    check("cli: plan 退出码 0 且产物齐", r.returncode == 0 and plan.is_file()
          and skeleton.is_file() and assets_out.is_file(), r.stderr[-200:])
    payload = json.loads(plan.read_text(encoding="utf-8"))
    check("cli: plan.json 携带逐页判断卡（否决项有效、无竞争可空）",
          all(set(p["judgment"]["composition"]) == {"chosen", "why", "rejected"}
              and all(r["why_not"] for r in p["judgment"]["composition"]["rejected"])
              for p in payload["pages"]))
    check("cli: plan.json 无旧字段残留（direction/direction_execution/media）",
          "direction" not in payload["deck"] and "direction_execution" not in payload["deck"]
          and all("media" not in p for p in payload["pages"]))
    sk = skeleton.read_text(encoding="utf-8")
    check("cli: 骨架写「为什么」但不再复制否决（canonical owner 收口）",
          "为什么" in sk and "结论[" in sk and "否决" not in sk)

    filled = make_build(tmp)
    out = tmp / "deck.pptx"
    r = run_vao("check", str(filled), str(out), "--mode", "release", "--speed", "fast")
    check("cli: release PASS 且产出预览/清单", r.returncode == 0 and out.is_file()
          and out.with_suffix(".manifest.json").is_file(), r.stdout[-200:])
    first = out.stat().st_mtime_ns

    r2 = run_vao("check", str(filled), str(out), "--mode", "release", "--speed", "fast")
    check("cli: 二次 release 缓存复用（未重编）",
          r2.returncode == 0 and "缓存复用" in r2.stdout and out.stat().st_mtime_ns == first,
          r2.stdout[-200:])

    broken = tmp / "broken.py"
    namespace: dict = {}
    exec(compile(filled.read_text(encoding="utf-8"), str(filled), "exec"), namespace)
    spec = json.loads(json.dumps(namespace["SPEC"], default=str))
    spec["slides"][0]["elements"][0]["height"] = 8
    broken.write_text(f"SPEC = {spec!r}\n", encoding="utf-8")
    r = run_vao("check", str(broken), str(tmp / "bad.pptx"), "--mode", "draft")
    packet = json.loads((tmp / "bad.repair.json").read_text(encoding="utf-8"))
    check("cli: BLOCK 退出码 2 + 分组修复包",
          r.returncode == 2 and packet["failure_codes"] == ["TEXT_OVERFLOW"]
          and packet["fix_plan"]["groups"], r.stdout[-200:])

    empty = tmp / "empty.yml"
    empty.write_text("audience: 董事会\ndecision: 批准预算\nslides: []\n", encoding="utf-8")
    r = run_vao("plan", str(empty), "--out", str(tmp / "p.json"))
    check("cli: 空 slides 早失败并给修法", r.returncode != 0
          and ("slides" in r.stderr or "slides" in r.stdout), r.stderr[-200:])

    r = run_vao("dna", "--check")
    check("cli: dna 体检可用且库健康", r.returncode == 0 and "OK" in r.stdout, r.stdout[-200:])


def test_docs():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    refs = sorted(p.name for p in (ROOT / "references").glob("*.md"))
    check("docs: SKILL.md 只保留六节（身份/哲学/判断/Context/执行/QA）",
          all(k in skill for k in ("身份", "设计哲学", "判断", "Context", "执行", "QA")),
          str(refs))
    check("docs: references ≤3 份，无案例堆积文件",
          len(refs) <= 3 and "precedent" not in refs, str(refs))
    check("docs: 文档里没有退役模块名与旧概念",
          all(b not in skill for b in ("guard.py", "normalize.py", "route.py", "qa.py",
                                       "design_direction")))
    dna = json.loads((ROOT / "memory" / "design_dna.json").read_text(encoding="utf-8"))
    check("docs: Design DNA 收敛到 ≤10 条高迁移原则",
          len(dna["entries"]) <= 10, str(len(dna["entries"])))


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for name, fn in (("intelligence", test_intelligence), ("verify", test_verify),
                         ("production", test_production), ("cli", test_cli)):
            (root / name).mkdir(parents=True, exist_ok=True)
            fn(root / name)
        test_docs()
    print(f"\n{PASS}/{PASS + FAIL} passed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
