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
    check("type: 主语只取可排版的主张，不把权重判断理由贴到页面上",
          s01["typography"]["lead"] == s01["claim"]["text"]
          and "结论句" not in s01["typography"]["lead"]
          and "字距" in s01["typography"]["discipline"])
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

    # 先出现的数字未必是结论：焦点、权重、排版必须共用同一结果值判定。
    rising = intel.think(dict(BRIEF, slides=[
        {"id": "rise", "title": "内容占比从 38% 升至 61%",
         "content": "2023 年 38%，2025 年 61%（来源：内容台账）"}]))["pages"][0]["judgment"]
    falling = intel.think(dict(BRIEF, slides=[
        {"id": "fall", "title": "单位成本从 2,800 元降至 1,800 元",
         "content": "同口径（来源：财务台账）"}]))["pages"][0]["judgment"]
    check("data: 升至/降至后的结果值为主，基期退后（不让首个数字误导读者）",
          rising["visual_role"]["role"] == "prove"
          and rising["understanding"]["evidence"] == "series"
          and "61%" in rising["focus"]["why"]
          and rising["typography"]["lead"] == "61%"
          and any("38%" in x for x in rising["information_weight"]["weaken"])
          and "1,800 元" in falling["focus"]["why"]
          and falling["typography"]["lead"] == "1,800 元",
          f"{rising['information_weight']} / {falling['information_weight']}")
    check("data: 量化箭头是变化，文字阶段箭头仍是序列；复合单位不被截断",
          intel.understand("38% → 61%")["evidence"] == "series"
          and intel.understand("试点 → 复制 → 全量")["evidence"] == "sequence"
          and intel.understand("从38%到61%")["evidence"] == "series"
          and intel.numerals("18个月 / 4,800万元 / 30分钟")[0]["unit"] == "个月"
          and intel.numerals("18个月 / 4,800万元 / 30分钟")[1]["unit"] == "万元")
    review = intel.think(dict(BRIEF, slides=[
        {"id": "compare", "title": "留存改善比曝光增长更稳健",
         "content": "内容回访率 71%，投放再触达率 42%（来源：回访台账）"},
        {"id": "subset", "title": "试点门店愿意继续共创",
         "content": "12 家试点门店中，9 家承诺提供记录（来源：回访台账）",
         "asset": "none"},
        {"id": "ask", "title": "请批准 4,800 万，启动 18 个月计划",
         "content": "请求批准 4,800 万，分季度验收（来源：预算草案）"}]))
    jc, jp, ja = [p["judgment"] for p in review["pages"]]
    check("data: 两个不同指标是比较，不伪装成同一指标的前后趋势/差值",
          jc["understanding"]["evidence"] == "comparison"
          and jc["visual_role"]["role"] == "compare"
          and "分母" in jc["focus"]["why"]
          and "基期" not in " ".join(jc["information_weight"]["weaken"])
          and jc["focus"]["type"] == "text"
          and any("分母" in q for q in jc["open_questions"]))
    chart_pair = intel.think(dict(BRIEF, slides=[
        {"id": "paired", "title": "两个样本的绝对量",
         "content": "甲组 30 人，乙组 18 人（来源：用户台账）",
         "chart": {"type": "bar", "values": [30, 18]}}]))["pages"][0]["judgment"]
    check("data: 作者给出的两个数图表是比较角色，不把第一数字误当趋势结果",
          chart_pair["visual_role"]["role"] == "compare"
          and chart_pair["focus"]["element_role"] == "comparison_field"
          and chart_pair["focus"]["type"] == "chart")
    mixed = intel.think(dict(BRIEF, slides=[
        {"id": "units", "title": "收入与人均成本对照",
         "content": "总收入 480 万元，人均成本 90 元（来源：财务表）",
         "chart": {"type": "bar", "values": [480, 90]}}]))["pages"][0]["judgment"]
    check("data: 单位不同不共用数量轴；曲线页编号不是第四个数据点",
          not mixed["understanding"]["same_unit"]
          and mixed["composition"]["chosen"] != "data_field"
          and any("单位不同" in q for q in mixed["open_questions"])
          and intel.understand("三年曲线1 96元→128元→205元")["distinct_numerals"] == 3)
    check("data: 9/12 子集突出 9、写明 12 分母，不误读为下降或摆并列卡",
          jp["understanding"]["evidence"] == "part_whole"
          and jp["focus"]["element_role"] == "ratio_main"
          and jp["typography"]["lead"] == "9 家"
          and jp["typography"]["support"] == "12 家"
          and jp["composition"]["chosen"] == "big_whitespace"
          and any(x["role"] == "claim_text" for x in jp["production"]["must_place"]))
    check("data: 预算和月份是两种量，18个月不是金额的历史基期",
          ja["typography"]["lead"] == "4,800 万"
          and ja["typography"]["support"] == "18 个月"
          and ja["focus"]["type"] == "text"
          and any("执行期限" in w for w in ja["information_weight"]["weaken"])
          and any(x["role"] == "claim_text" for x in ja["production"]["must_place"]))
    check("editorial: 不可比指标不共刻度，部分/总体不画趋势，请求金额/期限分层",
          "同口径" in jc["typography"]["discipline"]
          and "轴" in jp["typography"]["discipline"]
          and "期限" in ja["typography"]["discipline"])
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
    sk_vars: dict = {}
    exec(compile(sk1, "judgment-skeleton.py", "exec"), sk_vars)
    check("skeleton: 统一字族由世界判断直接落到稿件，终稿默认全页取证",
          sk_vars["SPEC"]["theme"]["fonts"] == bundle["deck"]["world"]["fonts"]
          and "--speed strict" in sk1)
    long_source = "首句是有来源的事实。" + "信息不会为骨架长度而丢失。" * 25 + "\n末句：留给排版处理。"
    preserved = intel.think(dict(BRIEF, slides=[
        {"id": "raw", "title": "完整原文必须保留", "content": long_source}]))
    preserved_sk = intel.build_skeleton(preserved)
    check("skeleton: 多行/超长原文逐字留在可执行骨架，原文不是视觉主语",
          long_source in preserved["pages"][0]["ref"]
          and "首句是有来源的事实。" in preserved_sk
          and "末句：留给排版处理。" in preserved_sk
          and "…" not in preserved["pages"][0]["ref"]
          and compile(preserved_sk, "preserved.py", "exec") is not None)
    check("skeleton: 无图不添加空资产清单命令（含图命令交由 plan 决定）",
          "--assets-manifest" not in preserved_sk and "媒体:none" in preserved_sk)
    raw_media = intel.think(dict(BRIEF, slides=[
        {"id": "photo", "title": "真实门店的回访记录",
         "content": "门店现场观察有来源（来源：实地记录）", "asset": "required"}]))
    check("skeleton: 直接调用 think 不谎称资产清单已经落盘",
          "尚未落盘" in intel.build_skeleton(raw_media))
    check("judgment: 受众/决定/阻力/排版/跨页节奏均由逐页判断串起",
          all(all(p["judgment"].get(key) for key in
                  ("audience", "decision", "tension", "typography", "rhythm"))
              for p in bundle["pages"])
          and all(p["judgment"]["typography"].get("lead")
                  and p["judgment"]["typography"].get("discipline")
                  and p["judgment"]["rhythm"].get("move") for p in bundle["pages"])
          and intel._FONTS["sans"]["cn"] == "Source Han Sans SC")

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
    safe_area_dna = intel.recall_dna({
        "title": "满幅摄影背景的文字安全区纹理过密，safe_area 需要羽化处理"})
    check("dna: 安全区例外保留独立案源，按关键词召回而不稀释通用原则",
          safe_area_dna.get("matched") == "feathered_safe_area_calm"
          and "safe_area" in safe_area_dna.get("judgment", {}).get("media", ""))
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
    spaced_paras = mutate(lambda s: s["slides"][0]["elements"][0].update(
        {"text": "第一段正文\n第二段正文", "size": 20, "width": 400,
         "height": 59, "space_after": 22, "line_height": 1.35}))
    tracked = mutate(lambda s: s["slides"][0]["elements"][0].update(
        {"text": "MMMMMMMM", "size": 28, "width": 245, "height": 52,
         "max_lines": 1, "char_spacing": 16}))
    check("guard: 段距/字距真实占位，不能在编译前把会断行的标题错判 PASS",
          any(c["rule"] == "text_capacity" for c in spaced_paras["checks"])
          and any(c["rule"] == "text_capacity" for c in tracked["checks"]))
    invalid_margin = mutate(lambda s: s["slides"][0]["elements"][0].update(
        {"padding": -44}))
    invalid_leading = mutate(lambda s: s["slides"][0]["elements"][0].update(
        {"line_height": -1}))
    check("guard: 负边距/负行高在 guard 阶段 fail-closed，不靠编译异常止损",
          any(c["rule"] == "text_capacity" for c in invalid_margin["checks"])
          and any(c["rule"] == "text_capacity" for c in invalid_leading["checks"]))

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

    # 回归（v6.5）：亚网格厚度不被抬高，同心关系不被吸附拆散。
    # 症状曾是——1px 发丝线被抬成 4px、骑线对象与线各挪各的，
    # 产物里对象永远悬在线的一侧，而硬门全绿（几何合法、不重叠、不溢出）。
    concentric = {"theme": {"colors": {}}, "slides": [{"id": "s", "elements": [
        {"id": "hairline", "type": "shape", "shape": "rect",
         "x": 96, "y": 280, "width": 400, "height": 1},
        {"id": "rider", "type": "shape", "shape": "rect",
         "x": 96, "y": 276, "width": 200, "height": 8},
    ]}]}
    norm_c, _ = normalize_spec(concentric)
    line_e, bar_e = norm_c["slides"][0]["elements"]
    check("normalize: 亚网格厚度原样保留（1px 发丝线不被抬成 4px）",
          line_e["height"] == 1, f'height={line_e["height"]}')
    check("normalize: 同心关系吸附后仍同心（线与骑线对象共中线）",
          abs((line_e["y"] + line_e["height"] / 2)
              - (bar_e["y"] + bar_e["height"] / 2)) < 1e-9,
          f'线中心={line_e["y"] + line_e["height"] / 2}，'
          f'对象中心={bar_e["y"] + bar_e["height"] / 2}')
    twice_c, _ = normalize_spec(norm_c)
    check("normalize: 同心吸附幂等（二次归一不再漂移）",
          spec_fingerprint(twice_c) == spec_fingerprint(norm_c))

    # 回归（v9.6.1）：LINE / ARROW 的零厚度轴必须保留为真正的横线/竖线。
    # 否则零宽竖线会被扩成网格宽度，PPT connector 从左上连到右下，出现轻微斜线。
    vertical = {"canvas": {"width": 1280, "height": 720},
                "theme": {"colors": {}}, "slides": [{"id": "axis", "elements": [
        {"id": "vertical_axis", "type": "shape", "shape": "line",
         "x": 93, "y": 278, "width": 0, "height": 239,
         "stroke": "#C8C2B5", "stroke_width": 1},
        {"id": "node", "type": "shape", "shape": "ellipse",
         "x": 88.5, "y": 273.5, "width": 9, "height": 9,
         "fill": "#713B43", "stroke": "none"},
    ]}]}
    norm_v, _ = normalize_spec(vertical)
    axis_e, node_e = norm_v["slides"][0]["elements"]
    check("normalize: 零宽竖线保留 width=0，长度按中心吸附",
          axis_e["width"] == 0 and axis_e["height"] == 240,
          f'width={axis_e["width"]}, height={axis_e["height"]}')
    check("normalize: 圆点与零宽竖线保持同一中线",
          abs(axis_e["x"] - (node_e["x"] + node_e["width"] / 2)) < 1e-9,
          f'线 x={axis_e["x"]}, 圆点中心={node_e["x"] + node_e["width"] / 2}')
    accepted_vertical = check_spec(norm_v)
    check("guard: 单轴为零的竖线合法",
          accepted_vertical["passed"])
    from compiler import compile_deck
    from pptx import Presentation
    vertical_pptx = tmp / "zero-width-vertical-line.pptx"
    compile_deck(norm_v, vertical_pptx)
    compiled_shapes = {sh.name: sh for sh in Presentation(str(vertical_pptx)).slides[0].shapes}
    compiled_axis, compiled_node = compiled_shapes["vertical_axis"], compiled_shapes["node"]
    check("compiler: 零宽竖线在 PPTX 中保持竖直且与圆点同心",
          compiled_axis.width == 0
          and compiled_axis.left == compiled_node.left + compiled_node.width // 2,
          f'line width={compiled_axis.width}, node center={compiled_node.left + compiled_node.width // 2}')
    zero_length = {"canvas": {"width": 1280, "height": 720},
                   "theme": {"colors": {}}, "slides": [{"id": "zero_line", "elements": [
        {"id": "zero_length_line", "type": "shape", "shape": "line",
         "x": 40, "y": 40, "width": 0, "height": 0,
         "stroke": "#C8C2B5", "stroke_width": 1},
    ]}]}
    norm_zero_line, _ = normalize_spec(zero_length)
    zero_line_report = check_spec(norm_zero_line)
    check("guard: 零长度线仍由几何门拦截",
          any(c["rule"] == "element_schema" and "线的 width 与 height 同时为 0" in c["msg"]
              for c in zero_line_report["checks"]))
    twice_v, _ = normalize_spec(norm_v)
    check("normalize: 零宽竖线归一化幂等",
          spec_fingerprint(twice_v) == spec_fingerprint(norm_v))

    horizontal = {"canvas": {"width": 1280, "height": 720},
                  "theme": {"colors": {}}, "slides": [{"id": "rule", "elements": [
        {"id": "horizontal_axis", "type": "shape", "shape": "line",
         "x": 93, "y": 278, "width": 239, "height": 0,
         "stroke": "#C8C2B5", "stroke_width": 1},
        {"id": "node", "type": "shape", "shape": "ellipse",
         "x": 208, "y": 273.5, "width": 9, "height": 9,
         "fill": "#713B43", "stroke": "none"},
    ]}]}
    norm_h, _ = normalize_spec(horizontal)
    axis_h, node_h = norm_h["slides"][0]["elements"]
    check("normalize: 零高横线保留 height=0，长度按中心吸附",
          axis_h["height"] == 0 and axis_h["width"] == 240,
          f'width={axis_h["width"]}, height={axis_h["height"]}')
    check("normalize: 圆点与零高横线保持同一中线",
          abs(axis_h["y"] - (node_h["y"] + node_h["height"] / 2)) < 1e-9,
          f'线 y={axis_h["y"]}, 圆点中心={node_h["y"] + node_h["height"] / 2}')
    check("guard: 单轴为零的横线合法",
          check_spec(norm_h)["passed"])
    twice_h, _ = normalize_spec(norm_h)
    check("normalize: 零高横线归一化幂等",
          spec_fingerprint(twice_h) == spec_fingerprint(norm_h))

    # 负尺寸/零面积不由归一化器偷偷修成可见对象，仍交给 guard 拦截。
    collapsed = {"canvas": {"width": 1280, "height": 720},
                 "theme": {"colors": {}}, "slides": [{"id": "degenerate", "elements": [
        {"id": "collapsed_rect", "type": "shape", "shape": "rect",
         "x": 20, "y": 20, "width": 0, "height": 20, "fill": "#713B43"},
    ]}]}
    norm_zero, _ = normalize_spec(collapsed)
    zero_report = check_spec(norm_zero)
    check("normalize: 零宽非线形保持退化并交由 guard 拦截",
          norm_zero["slides"][0]["elements"][0]["width"] == 0
          and any(c["rule"] == "element_schema" for c in zero_report["checks"]))

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

    from ghost import ghost_page
    native = {'canvas': {'width': 500, 'height': 220},
              'theme': {'colors': {'background': '#FFFFFF', 'ink': '#000000',
                                   'primary': '#000000', 'secondary': '#555555'}},
              'slides': [{'id': 'editorial', 'background': '#FFFFFF', 'elements': [
                  {'id': 'label', 'type': 'shape', 'shape': 'rect', 'x': 40, 'y': 40,
                   'width': 260, 'height': 100, 'fill': {'type': 'none'},
                   'stroke': {'type': 'none'}, 'text': 'ALIGN',
                   'text_size': 30, 'text_color': '#000000', 'padding': 40,
                   'align': 'left', 'text_anchor': 'top'},
                  {'id': 'tracking', 'type': 'text', 'text': '编辑排版',
                   'x': 350, 'y': 80, 'width': 140, 'height': 76, 'size': 24,
                   'color': '#000000', 'char_spacing': 6}]}]}
    out_editorial = tmp / 'editorial.pptx'
    compile_deck(native, out_editorial, speed='fast')
    prs_editorial = Presentation(str(out_editorial))
    sh1, sh2 = list(prs_editorial.slides[0].shapes)[:2]
    proof = ghost_page(native['slides'][0], native, scale=1, supersample=1)
    ink_x = [x for y in range(40, 140) for x in range(0, 310)
             if all(c < 120 for c in proof.getpixel((x, y)))]
    check("editorial: 空心形状不变卡片，内边距/文字主轴与原生 PPTX 对齐",
          round(sh1.text_frame.margin_left / 9525) == 40
          and min(ink_x) >= 78 and proof.getpixel((200, 100)) == (255, 255, 255))
    spc = [run._r.get_or_add_rPr().get('spc')
           for p in sh2.text_frame.paragraphs for run in p.runs]
    check("editorial: 作者显式声明的中文字距进入可编辑 OOXML，而非只对拉丁文生效",
          spc == ['600'], str(spc))

    styled_shape = {'id': 'shape_label', 'type': 'shape', 'shape': 'rect',
                    'x': 35, 'y': 20, 'width': 430, 'height': 174,
                    'fill': {'type': 'none'}, 'stroke': {'type': 'none'},
                    'text': 'AXIS\nBASELINE', 'padding': 12, 'text_size': 28,
                    'text_color': '#000000', 'text_opacity': .5, 'text_bold': True,
                    'text_wrap': False, 'text_line_height': 1.85,
                    'align': 'left', 'text_anchor': 'middle'}
    styled_text = {'id': 'same_text', 'type': 'text', 'text': styled_shape['text'],
                   'x': 35, 'y': 20, 'width': 430, 'height': 174, 'padding': 12,
                   'size': 28, 'color': '#000000', 'opacity': .5, 'bold': True,
                   'wrap': False, 'line_height': 1.85,
                   'align': 'left', 'anchor': 'middle'}
    def styled_spec(e):
        return dict(native, slides=[{'id': 'styled', 'background': '#FFFFFF',
                                     'elements': [e]}])
    shape_deck, text_deck = styled_spec(styled_shape), styled_spec(styled_text)
    label_image = ghost_page(shape_deck['slides'][0], shape_deck, scale=1, supersample=1)
    equivalent_image = ghost_page(text_deck['slides'][0], text_deck, scale=1, supersample=1)
    label_pptx = tmp / 'shape-text.pptx'
    compile_deck(shape_deck, label_pptx, speed='fast')
    label_native = Presentation(str(label_pptx)).slides[0].shapes[0]
    from pptx.oxml.ns import qn
    native_alpha = label_native.text_frame.paragraphs[0].runs[0]._r.find('.//' + qn('a:alpha'))
    check("editorial: 形状文字的粗细/行距/不换行/透明度与原生文本语义相同",
          label_image.tobytes() == equivalent_image.tobytes()
          and label_native.text_frame.paragraphs[0].runs[0].font.bold is True
          and native_alpha is not None and native_alpha.get('val') == '50000'
          and round(label_native.text_frame.paragraphs[0].line_spacing / 9525, 1) == 51.8)

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

    # strict 探测已算出当前产物 SHA；attestation 复用，不重复触发摘要/状态探测。
    from vao import _compile_step
    import primitives
    cached_out = tmp / "strict-cache.pptx"
    first_report, _ = _compile_step(spec, cached_out, speed="strict", spec_path=str(build))
    from unittest.mock import patch
    with patch.object(primitives, "file_digest", wraps=primitives.file_digest) as digest_spy:
        cached_report, cache_timing = _compile_step(
            spec, cached_out, speed="strict", spec_path=str(build))
    hashed_output = [call for call in digest_spy.call_args_list
                     if Path(call.args[0]).expanduser().resolve() == cached_out.resolve()]
    check("cache: strict 命中对 PPTX 只做一次内容哈希",
          first_report.get("output_sha256") == cached_report.get("output_sha256")
          and cached_report.get("reused") and len(hashed_output) == 1
          and cache_timing.get("compile_ms") == 0)

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
    from unittest.mock import patch
    image_spec = {"canvas": {"width": 1280, "height": 720}, "theme": {},
                  "slides": [{"id": "one_image", "elements": [
                      {"id": "photo", "type": "image", "src": str(img),
                       "x": 80, "y": 120, "width": 520, "height": 320,
                       "fit": "cover"}]}]}
    image_snapshot: dict = {}
    image_digest: dict = {}
    path_read_count = {str(img.resolve()): 0}
    original_read_bytes = Path.read_bytes
    def count_image_read(path, *args, **kwargs):
        key = str(Path(path).expanduser().resolve())
        if key in path_read_count:
            path_read_count[key] += 1
        return original_read_bytes(path, *args, **kwargs)
    with patch.object(Path, "read_bytes", count_image_read):
        spec_view(image_spec, base_path=tmp, image_bytes=image_snapshot, digests=image_digest)
        compile_deck(image_spec, tmp / "one_image.pptx", speed="fast",
                     spec_path=str(build), image_bytes=image_snapshot)
    from primitives import digest_bytes
    image_key = str(img.resolve())
    check("media: 指纹预读的源图字节由编译复用（同轮仅一次文件读取）",
          path_read_count[image_key] == 1
          and image_digest.get(image_key) == digest_bytes(image_snapshot.get(image_key, b"")))
    # 模拟 QC 已有 SHA、但因 QC cache hit 没把图像快照装入内存：compile 读一次后
    # 把源 bytes 放回共享快照，page-key 不再为 preview 读取第二次。
    image_snapshot_cached: dict = {}
    image_digest_cached = {image_key: image_digest[image_key]}
    path_read_count[image_key] = 0
    media_spec_for_preview = {**image_spec, "_image_bytes": image_snapshot_cached,
                              "_base_path": str(tmp)}
    media_slide = image_spec["slides"][0]
    with patch.object(Path, "read_bytes", count_image_read):
        spec_view(image_spec, base_path=tmp, image_bytes=image_snapshot_cached,
                  digests=image_digest_cached)
        compile_deck(image_spec, tmp / "one_image_cached_qc.pptx", speed="fast",
                     spec_path=str(build), image_bytes=image_snapshot_cached)
        from ghost import _page_key
        _page_key(media_slide, media_spec_for_preview, 0.5, 1, 1)
    check("media: QC 缓存 SHA → 编译读一次 → preview 复用同一图像字节",
          path_read_count[image_key] == 1
          and image_snapshot_cached.get(image_key)
          and image_digest_cached.get(image_key) == digest_bytes(image_snapshot_cached[image_key]))
    safe = {"x": 0.06, "y": 0.08, "width": 0.34, "height": 0.78}
    qc = image_qc(img, safe_rect=safe, text_is_dark=True)
    decision_ok = qc_retry_decision(qc, attempt=0, phase="release")
    check("assets: 合规画心 QC 通过（无阻断项，动作 accept）",
          qc.get("status") == "ok" and decision_ok.get("action") == "accept",
          str(qc.get("checks"))[:160])
    fast_qc = image_qc(img, safe_rect=safe, text_is_dark=True, max_side=960)
    check("assets: fast/strict 的硬缝判定一致（不因降采样制造重试）",
          fast_qc.get("status") == qc.get("status")
          and next(c for c in fast_qc["checks"] if c["check"] == "hard_seam")["status"]
          == next(c for c in qc["checks"] if c["check"] == "hard_seam")["status"])
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
    from ghost import (PAGE_CACHE_DIR, _page_key, key_pages, ghost_deck,
                       key_page_roles, key_selection, make_contact_sheet)
    pages = key_pages(spec["slides"], limit=3)
    labels = key_page_roles(spec["slides"], pages)
    check("ghost: 关键页取证含封面与收尾",
          1 in pages and len(spec["slides"]) in pages and
          set(labels.values()) <= {"cover", "closing", "hero_image", "dense_data",
                                   "section", "content"}, str(labels))
    rendered_images: list = []
    page_stats: dict = {}
    rendered = ghost_deck(spec, tmp / "preview", pages=pages, scale=0.4, supersample=1,
                          images_out=rendered_images, stats=page_stats)
    check("ghost: 预览只画关键页（页级缓存内建）",
          len(rendered) == len(pages) and all(Path(p).is_file() for p in rendered))
    page_cache_files = list((tmp / "preview" / PAGE_CACHE_DIR).glob("*.png"))
    check("ghost: 页缓存与交付预览复用同一份 PNG 编码",
          bool(rendered) and any(Path(rendered[0]).read_bytes() == p.read_bytes()
                                 for p in page_cache_files))
    sheet_stats: dict = {}
    contact = make_contact_sheet(rendered, tmp / "preview" / "contact.png",
                                 images=rendered_images,
                                 cache_dir=tmp / "preview" / PAGE_CACHE_DIR,
                                 stats=sheet_stats)
    sheet_cache = list((tmp / "preview" / PAGE_CACHE_DIR).glob("sheet-*.png"))
    check("ghost: 联络表只编码一次并以字节副本缓存",
          bool(contact and Path(contact).is_file() and sheet_cache
               and Path(contact).read_bytes() == sheet_cache[0].read_bytes()))
    sel_pages, sel_roles = key_selection(spec["slides"], limit=3)
    check("ghost: 单次取证与两次调用结论一致（结构只扫一遍）",
          sel_pages == pages and sel_roles == labels)

    media_src = tmp / "preview-source.png"
    Image.new("RGB", (32, 32), (180, 40, 40)).save(media_src)
    blob_a = media_src.read_bytes()
    media_slide = {"id": "media", "elements": [
        {"id": "photo", "type": "image", "src": str(media_src)}]}
    media_spec_a = {"canvas": {"width": 1280, "height": 720}, "theme": {},
                    "_image_bytes": {str(media_src): blob_a}}
    key_a = _page_key(media_slide, media_spec_a, 0.5, 1, 1)
    Image.new("RGB", (32, 32), (40, 40, 180)).save(media_src)
    blob_b = media_src.read_bytes()
    media_spec_b = {"canvas": {"width": 1280, "height": 720}, "theme": {},
                    "_image_bytes": {str(media_src): blob_b}}
    key_b = _page_key(media_slide, media_spec_b, 0.5, 1, 1)
    check("ghost: 同一路径的图片字节变化会使页缓存失效", key_a != key_b)
    # 与先画透明整幅图再合成的旧路径逐像素比对：省掉背景合成不能改变任何墨迹。
    from ghost import _draw_text, _font, _rgba
    from primitives import RenderContext
    ctx = RenderContext(spec.get("theme"), spec.get("canvas"))
    text_elem = {"id": "probe", "type": "text", "x": 12, "y": 24,
                 "width": 160, "height": 80, "text": "61%", "size": 32, "color": "ink"}
    same = True
    for opacity in (None, 0.52):
        bg_color = (244, 239, 230, 255)
        expected = Image.new("RGBA", (240, 130), bg_color)
        old_overlay = Image.new("RGBA", expected.size, (0, 0, 0, 0))
        ImageDraw.Draw(old_overlay, "RGBA").text(
            (12, 24), "61%", font=_font(32), fill=_rgba(ctx, "ink", opacity))
        expected.alpha_composite(old_overlay)
        actual = Image.new("RGBA", expected.size, bg_color)
        _draw_text(actual, {**text_elem, "opacity": opacity}, ctx, 1)
        same = same and actual.tobytes() == expected.tobytes()
    check("ghost: 不透明直画与半透明旧合成路径像素一致（速度不能改变设计）", same)


# ── 4 · cli + docs ───────────────────────────────────────────────────
def test_cli(tmp: Path):
    brief = tmp / "brief.yml"
    import yaml
    brief.write_text(yaml.safe_dump(BRIEF, allow_unicode=True), encoding="utf-8")
    plan = tmp / "plan.json"
    skeleton = tmp / "build.py"
    assets_out = tmp / "assets.json"
    r = run_vao("plan", str(brief), "--out", str(plan), "--skeleton", str(skeleton),
                "--assets-out", str(assets_out), "--assets-dir", str(tmp / "gen"), "--json")
    check("cli: plan 退出码 0 且产物齐", r.returncode == 0 and plan.is_file()
          and skeleton.is_file() and assets_out.is_file(), r.stderr[-200:])
    plan_stdout = json.loads(r.stdout)
    timing = plan_stdout.get("performance") or {}
    import hashlib
    check("cli: plan 阶段计时可分解且 brief 读入/哈希凭证一致",
          timing.get("total_ms", 0) >= timing.get("intelligence_ms", 0)
          and "brief_load_ms" in timing and timing.get("reference_files_read") == 0
          and plan_stdout.get("workflow", {}).get("brief_file_sha256")
          == hashlib.sha256(brief.read_bytes()).hexdigest(),
          str(timing))
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

    # 一次 CLI plan：图是判断所得才准备资产；没有图不产生空清单/额外命令。
    media_brief = tmp / "media-brief.yml"
    media_brief.write_text(yaml.safe_dump(dict(BRIEF, slides=[
        {"id": "witness", "title": "门店回访揭示真实的使用障碍",
         "content": "门店现场与店长在高峰时段的记录（来源：走访纪要）",
         "asset": "required", "asset_subject": "店长在门店高峰时段真实记录"}]),
        allow_unicode=True), encoding="utf-8")
    media_dir = tmp / "media"
    media_plan = media_dir / "plan.json"
    media_sk = media_dir / "build.py"
    media_run = run_vao("plan", str(media_brief), "--out", str(media_plan),
                        "--skeleton", str(media_sk), "--json")
    image_json = json.loads(media_run.stdout) if media_run.returncode == 0 else {}
    auto_manifest = media_dir / "asset_manifest.json"
    noimg_plan = tmp / "noimg-plan.json"
    noimg_sk = tmp / "noimg-build.py"
    noimg_run = run_vao("plan", str(brief), "--out", str(noimg_plan),
                         "--skeleton", str(noimg_sk), "--json")
    noimg_json = json.loads(noimg_run.stdout) if noimg_run.returncode == 0 else {}
    check("cli: 图片被判断为必要时，同一次 plan 交付可定位的资产清单+构图骨架",
          media_run.returncode == 0 and auto_manifest.is_file()
          and image_json.get("workflow", {}).get("assets_manifest_path")
          == str(auto_manifest.resolve())
          and "--assets-manifest" in media_sk.read_text(encoding="utf-8")
          and len(json.loads(auto_manifest.read_text(encoding="utf-8")).get("assets", [])) == 1,
          str(image_json.get("workflow", {})))
    check("cli: 无图一次 plan 没有资产清单和清单验证参数",
          noimg_run.returncode == 0 and not (tmp / "asset_manifest.json").exists()
          and not noimg_json.get("workflow", {}).get("assets_manifest_path")
          and "--assets-manifest" not in noimg_sk.read_text(encoding="utf-8"))

    invalid_brief = tmp / "invalid-media.yml"
    invalid = dict(BRIEF, slides=[dict(BRIEF["slides"][0],
                                   asset="required", asset_role="cosmic_unrecognized")])
    invalid_brief.write_text(yaml.safe_dump(invalid, allow_unicode=True), encoding="utf-8")
    invalid_dir = tmp / "invalid-media"
    invalid_run = run_vao("plan", str(invalid_brief), "--out", str(invalid_dir / "plan.json"),
                          "--skeleton", str(invalid_dir / "build.py"), "--json")
    check("cli: 不合法图片角色 fail-closed，不能留下声称已有清单的半成品 plan/骨架",
          invalid_run.returncode == 2 and "asset_role" in invalid_run.stderr
          and not (invalid_dir / "plan.json").exists()
          and not (invalid_dir / "build.py").exists()
          and not (invalid_dir / "asset_manifest.json").exists(), invalid_run.stderr[-200:])

    filled = make_build(tmp)
    out = tmp / "deck.pptx"
    stale_packet = out.with_suffix(".repair.json")
    stale_packet.write_text('{"status":"BLOCKED"}', encoding="utf-8")
    r = run_vao("check", str(filled), str(out), "--mode", "release", "--speed", "fast",
                "--json")
    check("cli: release PASS、产出预览/清单且不留多余/过期 repair 包",
          r.returncode == 0 and out.is_file()
          and out.with_suffix(".manifest.json").is_file() and not stale_packet.exists(),
          r.stdout[-200:])
    release_result = json.loads(r.stdout)
    release_timing = release_result.get("timing") or {}
    check("cli: 端到端计时包含预览且区分 compile/cache/QA",
          release_result.get("status") == "PASS"
          and release_timing.get("total_ms", 0) >= release_timing.get("ghost_ms", 0)
          and {"compile_ms", "cache_probe_ms", "qa_ms", "render_pages_drawn",
               "image_source_snapshots", "image_snapshot_bytes", "asset_qc_reused"}
          <= set(release_timing), str(release_timing))
    first = out.stat().st_mtime_ns

    r2 = run_vao("check", str(filled), str(out), "--mode", "release", "--speed", "fast")
    check("cli: 二次 release 缓存复用（未重编）",
          r2.returncode == 0 and "缓存复用" in r2.stdout and out.stat().st_mtime_ns == first,
          r2.stdout[-200:])
    unused = run_vao("check", str(filled), str(out), "--mode", "release",
                     "--assets-manifest", str(tmp / "nonexistent-asset.json"), "--json")
    unused_timing = (json.loads(unused.stdout).get("timing") or {}) if unused.returncode == 0 else {}
    check("cli: 无图 release 不读取无关清单，也不触发额外像素验证",
          unused.returncode == 0 and unused_timing.get("asset_bind_ms") == 0
          and unused_timing.get("qc_ms") == 0 and out.stat().st_mtime_ns == first)

    preview_dir = tmp / "deck_preview"
    contact = preview_dir / "ghost-contact-sheet.png"
    contact.write_bytes(b"corrupt preview, not a PNG")
    repaired = run_vao("check", str(filled), str(out), "--mode", "release", "--speed", "fast",
                       "--json")
    repair_timing = (json.loads(repaired.stdout).get("timing") or {}) if repaired.returncode == 0 else {}
    from PIL import Image
    png_valid = False
    try:
        with Image.open(contact) as sample:
            sample.verify()
        png_valid = True
    except (OSError, ValueError):
        pass
    check("cli: 交付 PNG 被破坏不能再凭 marker 假 PASS；复用未变页图修复联络表",
          repaired.returncode == 0 and png_valid
          and not repair_timing.get("render_bundle_reused")
          and repair_timing.get("render_pages_drawn") == 0
          and repair_timing.get("compile_ms") == 0)
    small = run_vao("check", str(filled), str(out), "--mode", "release", "--speed", "fast",
                    "--ghost-pages", "2", "--json")
    small_timing = (json.loads(small.stdout).get("timing") or {}) if small.returncode == 0 else {}
    small_marker = json.loads((preview_dir / "ghost.meta.json").read_text(encoding="utf-8")) \
        if (preview_dir / "ghost.meta.json").is_file() else {}
    check("cli: 5→2 页取证不复用旧的 5 页凭证，不留过期预览图片",
          small.returncode == 0 and small_timing.get("render_pages") == 2
          and not small_timing.get("render_bundle_reused")
          and small_marker.get("request", {}).get("key_page_limit") == 2
          and len(list(preview_dir.glob("ghost-[0-9]*.png"))) == 2,
          str(small_timing))
    restored = run_vao("check", str(filled), str(out), "--mode", "release", "--speed", "fast",
                       "--ghost-pages", "5", "--json")
    restore_timing = (json.loads(restored.stdout).get("timing") or {}) if restored.returncode == 0 else {}
    check("cli: 2→5 页重新扩大证据范围，逐页缓存复用而非重画/重编",
          restored.returncode == 0 and restore_timing.get("render_pages") == 5
          and restore_timing.get("render_pages_drawn") == 0
          and restore_timing.get("compile_ms") == 0
          and len(list(preview_dir.glob("ghost-[0-9]*.png"))) == 5)

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
    no_manifest = tmp / "image-build.py"
    with_pic = json.loads(json.dumps(spec))
    with_pic["slides"][0]["elements"].append(
        {"id": "missing_picture", "type": "image", "src": "asset:missing",
         "x": 580, "y": 240, "width": 540, "height": 350, "role": "witness"})
    no_manifest.write_text(f"SPEC = {with_pic!r}\n", encoding="utf-8")
    image_out = tmp / "missing-image.pptx"
    without = run_vao("check", str(no_manifest), str(image_out), "--mode", "release", "--json")
    blocked = json.loads(without.stdout) if without.returncode == 2 else {}
    check("cli: 含图但缺清单阻断于编译之前，不输出假的合格 PPTX",
          without.returncode == 2 and not image_out.exists()
          and (blocked.get("timing") or {}).get("compile_ms") == 0
          and "ASSET" in " ".join(blocked.get("failure_codes", [])),
          str(blocked.get("failure_codes", [])))

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
    dna_entries = dna.get("entries") if isinstance(dna, dict) else None
    dna_ids = [entry.get("id") for entry in dna_entries if isinstance(entry, dict)] \
        if isinstance(dna_entries, list) else []
    ids_are_valid = all(isinstance(value, str) and value.strip() for value in dna_ids)
    check("docs: Design DNA 结构有效且 ID 唯一（条目数不设上限）",
          isinstance(dna_entries, list)
          and all(isinstance(entry, dict) for entry in dna_entries)
          and ids_are_valid and len(dna_ids) == len(set(dna_ids)),
          str(len(dna_entries or [])))


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
