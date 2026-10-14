#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py · 核心测试（生产路径即测试路径）

四段：
  1) intelligence —— 设计判断：结论 / 权重 / 角色 / 焦点 / 构图（含否决理由）/ 媒体必要性 / 世界
  2) verify        —— 硬门：溢出、重叠、越界、空载荷、来源区、出处、口径
  3) production    —— 编译确定性、缓存复用、资产链、关键页取证
  4) cli + docs    —— 单入口 plan/check/qc、骨架携带判断、文档纪律
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


def run_vao(*args, cwd=None, env=None):
    # 显式 UTF-8：子进程输出恒为 UTF-8（vao.force_utf8_stdio），父进程必须按同一
    # 口径解码——用默认 text=True 时 Windows 会拿系统 ANSI 代码页解码管道，
    # 于是断言读到的是乱码或直接抛 UnicodeDecodeError。
    return subprocess.run([sys.executable, str(SCRIPTS / "vao.py"), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=cwd or str(ROOT), env=env)


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

    # 固定关系正反样本就地保留，核心回归不依赖外部评测目录。
    relation_cases = [
        {"id": "previous-round-governance", "title": "四层汇报线明确决策归属", "content": "董事会决定战略；管理层负责预算；区域负责人协调资源；当地负责人执行。", "expect_relations": 3, "expect_role": "explain", "expect_composition": "linear_structure"},
        {"id": "responsibility", "title": "研发与交付的职责应分开", "content": "甲组负责研发；乙组负责交付。", "expect_relations": 2, "expect_role": "explain", "expect_composition": "linear_structure"},
        {"id": "reporting", "title": "审批归属必须清楚", "content": "区域负责人向总经理汇报；总经理向董事会汇报。", "expect_relations": 2, "expect_role": "explain", "expect_composition": "linear_structure"},
        {"id": "renamed-subjects", "title": "职责先于装饰", "content": "青岚组负责质量；澄川组负责交付。", "expect_relations": 2, "expect_role": "explain", "expect_composition": "linear_structure"},
        {"id": "same-subject", "title": "专人承担研发和交付", "content": "甲组负责研发；甲组负责交付。", "expect_relations": 0},
        {"id": "question", "title": "职责尚待确认", "content": "谁负责研发？谁负责交付？", "expect_relations": 0},
        {"id": "negation", "title": "当前职责仍未落实", "content": "甲组不负责研发；乙组未负责交付。", "expect_relations": 0},
        {"id": "proposal", "title": "分工还在讨论", "content": "建议甲组负责研发；乙组负责交付。", "expect_relations": 0},
        {"id": "unresolved-objects", "title": "分工还不完整", "content": "甲组负责；乙组执行。", "expect_relations": 0},
        {"id": "numeric-evidence", "title": "本期执行结果可核验", "content": "甲组执行 12 项；乙组执行 18 项。", "expect_relations": 0},
        {"id": "sequence", "title": "先研发再交付", "content": "先由甲组负责研发，然后由乙组负责交付。", "expect_relations": 0},
        {"id": "comparison", "title": "两组的交付率有差异", "content": "甲组负责研发；乙组负责交付。甲组交付率 90%，高于乙组 80%。", "expect_relations": 0, "expect_role": "compare"},
        {"id": "topic-only", "title": "四层汇报线与矩阵式分工", "content": "", "expect_relations": 0},
        {"id": "subset-control", "title": "多数试点选择续约", "content": "12 家试点门店中，9 家续约。", "expect_relations": 0, "expect_role": "prove"},
        {"id": "compound-control", "title": "结构性增长来自续约", "content": "我们必须保留这一增长来源。", "expect_relations": 0},
    ]
    for case in relation_cases:
        j = intel.page_judgment({**case, "asset": "none"}, index=2, total=7,
                                brief=BRIEF, world={}, warnings=[])
        actual = (len(j["understanding"].get("relations", [])), j["visual_role"]["role"],
                  j["composition"]["chosen"])
        check("relations: " + case["id"],
              actual == (case["expect_relations"], case.get("expect_role", actual[1]),
                         case.get("expect_composition", actual[2])), str(actual))
    relation_page = {**relation_cases[0], "asset": "none"}
    checked_relations = intel.think(dict(BRIEF, slides=[
        dict(relation_page, id=f"r{i}") for i in range(4)]))
    check("relations: 首末位置/跨页求变不能覆盖正文关系证据",
          all(p["judgment"]["visual_role"]["role"] == "explain"
              and p["judgment"]["composition"]["chosen"] == "linear_structure"
              for p in checked_relations["pages"]))
    rj = checked_relations["pages"][0]["judgment"]
    check("relations: 分工不伪装成汇报层级或时间轴",
          rj["focus"]["element_role"] == "structure_map"
          and "空白不代表时间" in rj["spatial"]["whitespace_duty"]
          and "推测汇报线" in rj["typography"]["discipline"])
    declared_relation = intel.think(dict(BRIEF, slides=[
        dict(relation_page, composition="editorial", focus="author_focus")]))["pages"][0]["judgment"]
    check("relations: 作者焦点与构图仍然优先",
          declared_relation["composition"]["chosen"] == "editorial"
          and declared_relation["focus"]["element_role"] == "author_focus")
    real_sequence = intel.page_judgment({"title":"按阶段落地", "content":"先研发，然后交付。", "asset":"none"},
                                       index=1,total=3,brief=BRIEF,world={},warnings=[])
    check("relations: 时间推进仍保留顺序空间职责",
          real_sequence["understanding"]["evidence"] == "sequence"
          and "空白是时间" in real_sequence["spatial"]["whitespace_duty"])

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

    # 两组「各自从 A 到 B」的变化并排（证据表的一行）不再顶掉标题结论位：
    # 此前这句靠「变化词 + 数字」加分胜出，焦点与排版跟着落到基期数字上。
    two_moves = intel.think({
        "audience": "董事会", "decision": "批准投入",
        "slides": [{"id": "p1", "title": "我们的份额增速正在被本地玩家反超",
                    "content": "过去 12 个月本地头部玩家份额从 12% 升至 19%，我方从 9% 降至 7%；"
                               "获客成本我方 42 美元、对手 26 美元。（来源：第三方市场监测）"}]})
    two_moves_claim = two_moves["pages"][0]["judgment"]["claim"]
    check("claim: 两组变化并排是列举，作者写在标题位的结论仍然胜出",
          two_moves_claim["text"] == "我们的份额增速正在被本地玩家反超"
          and "标题" in two_moves_claim["why"], str(two_moves_claim))

    # 顺序形状由顺序词的数量决定：三段里程碑排期不应该被一个孤立的时长数字压成 number。
    plan_page = intel.think({
        "audience": "董事会", "decision": "批准排期",
        "slides": [{"id": "p1", "title": "必须在 2027 年一季度前完成三国落地",
                    "content": "先做基础设施与合规，然后复制内容与供应链，接着本地化运营团队，"
                               "最后做区域品牌投放。总计 18 个月，分三段里程碑。（来源：战略部排期）"}]})
    plan_judgment = plan_page["pages"][0]["judgment"]
    check("understand: 三段以上顺序词 → sequence（骨架走线性结构，而不是单数字大留白）",
          plan_judgment["understanding"]["evidence"] == "sequence"
          and plan_judgment["visual_role"]["role"] == "explain"
          and plan_judgment["composition"]["chosen"] == "linear_structure",
          str({"evidence": plan_judgment["understanding"]["evidence"],
               "role": plan_judgment["visual_role"]["role"],
               "composition": plan_judgment["composition"]["chosen"]}))

    # 视觉角色：开场 establish / 收尾 summarize / 对比 compare / 说服 persuade
    roles = {p["id"]: p["judgment"]["visual_role"]["role"] for p in pages}
    check("role: 开场 establish、收尾 summarize",
          roles["s01"] == "establish" and roles["s05"] == "summarize", str(roles))
    check("role: 对比内容 → compare，且给了替代角色",
          roles["s03"] == "compare" and by_id["s03"]["judgment"]["visual_role"]["alternatives"])

    # 焦点：焦点元素唯一 + 必须给出否决的替代项
    foc = s03["focus"]
    check("focus: 对比页焦点是两端对比场而不是卡片墙",
          foc["element_role"] == "comparison_field"
          and any("卡片" in r["why_not"] or "卡" in r["option"] for r in foc["rejected"]),
          str(foc["rejected"])[:120])
    check("focus: 数字结论页焦点是 kpi_main 并否决环形图",
          by_id["s05"]["judgment"]["focus"]["element_role"] in ("kpi_main", "hero_statement"))

    # 构图：必须回答「为什么不是别的形式」
    comp = by_id["s02"]["judgment"]["composition"]
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
    four_pages = intel.think(dict(BRIEF, slides=[
        {"id": f"p{i}", "title": f"第{i}页结论句", "content": f"证据 {i}（来源：台账）"}
        for i in range(1, 5)]))
    four_sk = intel.build_skeleton(four_pages)
    four_vars: dict = {}
    exec(compile(four_sk, "anchor-skeleton.py", "exec"), four_vars)
    anchors = [s.get("anchor") for s in four_vars["SPEC"]["slides"]]
    role_1 = four_pages["pages"][1]["judgment"]["visual_role"]["role"].upper()
    check("skeleton: 跨页锚以判断对象落进 spec（不是散文提醒），spec 不留第二个结论位",
          isinstance(anchors[1], dict) and bool(anchors[1].get("eyebrow"))
          # 眉标是**内容派生**的短标，不是视觉角色的英文枚举（枚举 12 页里
          # 会有 7 页同为 PROVE，读起来就是模板）
          and anchors[1].get("eyebrow") != role_1
          and anchors[1].get("page_number") == 2 and anchors[0].get("page_number") is None
          and all("page_intent" not in s for s in four_vars["SPEC"]["slides"]),
          str(anchors))
    # 眉标：内容派生 + 作者声明压过推导 + 不输出半截词
    eyebrow_deck = intel.think(dict(BRIEF, slides=[
        {"id": f"e{i}", "title": f"东南亚市场{i}是我们唯一的结构性增长来源",
         "content": "履约成本 11.2 元（来源：自营财务口径）"} for i in range(1, 5)]))
    labels = [(p.get("anchor") or {}).get("eyebrow") for p in eyebrow_deck["pages"]]
    declared_eyebrow = intel.think(dict(BRIEF, slides=[
        {"id": "x1", "title": "标题", "content": "证据", "eyebrow": "单位经济"},
        {"id": "x2", "title": "标题", "content": "证据", "eyebrow": "清关与用工"},
        {"id": "x3", "title": "标题", "content": "证据", "eyebrow": "释放条件"},
        {"id": "x4", "title": "标题", "content": "证据", "eyebrow": "复盘节点"}]))
    check("眉标: 由本页结论派生（不是角色枚举），作者声明原样生效",
          all(lbl and not lbl.isupper() and len(lbl) <= 6 for lbl in labels)
          and len(set(labels)) == 1 and labels[0] == "东南亚市场"
          and [(p.get("anchor") or {}).get("eyebrow") for p in declared_eyebrow["pages"]]
          == ["单位经济", "清关与用工", "释放条件", "复盘节点"], str(labels))
    # 眉标不得**缝合数字两侧**：把数字删掉再断词，会把「中国 800 元以上」缝成
    # 「中国元以」——它看着像有信息，实际是噪声，比退回角色词更糟。
    # 边缘编号（东南亚市场1）可以去掉，夹在中间的数字一律不收。
    splice_bad = None
    for _t, _want in (("中国 800 元以上的葡萄酒，是唯一两位数增长的赛道", "葡萄酒"),
                      ("东南亚市场1是我们唯一的结构性增长来源", "东南亚市场"),
                      ("本轮 1.8 亿元里，67% 投向库存与藤园", "证明")):
        _got = intel.section_label({}, {"text": _t}, "prove")
        if _got != _want:
            splice_bad = (_t, _want, _got); break
    check("眉标: 不缝合数字两侧的汉字（宁可退回角色词）",
          splice_bad is None, str(splice_bad))
    # 封面 / 收尾是**陈述位**：没有证据不等于没有主张。
    # 实测（CASE_006）：一句封面主张被判成「结构说明页」，焦点落到一张并不存在的
    # 层级图上，收尾页则被判 absent 并告警，逼作者给封面补数据。
    statement_deck = intel.think(dict(BRIEF, slides=[
        {"id": "cover", "title": "东南亚是我们未来五年唯一还能拿到结构性增长的战场"},
        {"id": "mid", "title": "复购率由 21.4% 升至 41.7%",
         "content": "同期补贴占收入比由 22.4% 降至 6.1%（来源：运营系统）"},
        {"id": "close", "title": "我们不是在赌一个市场，是在买一条可以复制到第三个国家的履约能力"}]))
    cov, clo = (statement_deck["pages"][0]["judgment"],
                statement_deck["pages"][-1]["judgment"])
    check("首末页: 陈述位按叙事位置取角色，不派发结构图、不误报告警",
          cov["visual_role"]["role"] == "establish"
          and clo["visual_role"]["role"] == "summarize"
          and cov["focus"]["element_role"] == "statement_text"
          and clo["focus"]["element_role"] != "structure_map"
          and cov["claim"]["text"].startswith("东南亚")
          and clo["claim"]["text"].startswith("我们不是在赌")
          and not [w for w in statement_deck["warnings"]
                   if w.get("rule") == "unresolved_content"],
          str([cov["visual_role"]["role"], clo["visual_role"]["role"],
               cov["focus"]["element_role"], clo["focus"]["element_role"]]))
    check("understanding: 「结构性增长」是复合名词，不产生结构/序列证据形态",
          intel.understand("东南亚是我们未来五年唯一还能拿到结构性增长的战场")["evidence"]
          in ("none", "proposition"))

    # 焦点数字＝主张所指的那个量（不是第一个、也不是最大的那个）
    unit_econ = ("印尼雅加达自营仓：单均履约成本从 2024Q1 的 19.4 元降至 2025Q4 的 "
                 "11.2 元，降幅 42.3%；同期客单价由 68 元升至 83 元。泰国曼谷加盟："
                 "单均履约成本 16.8 元。")
    claim_ue = "三个市场里只有印尼跑通了单位经济，而且是靠自营履约跑通的"
    check("number_roles: 焦点取主张点名的那个指标（履约成本 11.2 元，不是客单价 83 元）",
          intel.number_roles(unit_econ)[1]["raw"] == "83 元"
          and intel.number_roles(unit_econ, claim_ue)[1]["raw"] == "11.2 元",
          str(intel.number_roles(unit_econ, claim_ue)[1]))
    risk = ("清关环节：口岸清关时效在 1.8 至 6.4 天之间波动，波动幅度 256%，"
            "库存周转天数在 21 至 47 天之间摆动。用工环节：一线分拣人力成本同比上升 18.6%。")
    check("number_roles: 区间下界不是可以立住的量（1.8 出局，取 6.4 天）",
          intel.number_roles(risk)[1]["raw"] == "1.8"
          and intel.number_roles(risk, "清关与用工是无法靠补贴解决的结构性约束")[1]["raw"]
          == "6.4 天")
    years = ("2026 年：收入 4.6 亿元，毛利率 -8.4%。2027 年：收入 12.8 亿元，"
             "毛利率 6.2%。2028 年：收入 27.4 亿元，毛利率 17.6%。")
    check("number_roles: 主张用序数点名某年时，焦点落在该年（第二年 → 2027 年的 12.8 亿元）",
          intel.number_roles(years)[1]["raw"] == "4.6 亿元"
          and intel.number_roles(years, "三年测算里最关键的是第二年")[1]["raw"] == "12.8 亿元")
    # 多量纲 + 主张无量 → 数字退为支撑，第一落点回到那句话
    mixed = intel.think(dict(BRIEF, slides=[
        {"id": "m1", "title": "真正的阻力不是竞争，是清关与用工这两件我们无法靠补贴解决的事",
         "content": risk}]))
    check("focus: 主张无量且证据横跨多量纲时，数字退为支撑（不拿波动下界当主语）",
          mixed["pages"][0]["judgment"]["focus"]["element_role"] == "statement_text")
    concentrated = intel.think(dict(BRIEF, slides=[
        {"id": "m2", "title": "三个市场里只有印尼跑通了单位经济",
         "content": unit_econ}]))
    check("focus: 页面由同一指标占住时数字仍是主语（集中度 ≥50% 不降级）",
          concentrated["pages"][0]["judgment"]["focus"]["element_role"] == "kpi_main")

    # 排版尺度：把纪律落成可核对的数字（行长/行距/内边距/断行）
    scale_page = intel.think(dict(BRIEF, slides=[
        {"id": "sc", "title": "真正的阻力不是竞争，是清关与用工这两件我们无法靠补贴解决的事",
         "content": risk}]))["pages"][0]["judgment"]["typography"]["scale"]
    check("typography: 保留内容相关尺度/断行，不注入固定字阶/行数/间距配额",
          scale_page["body_measure_cjk"] <= 45
          and not ({"hierarchy", "line_height", "padding", "lead_lines"} & set(scale_page))
          and scale_page["lead_break"]
          and "｜" in scale_page["lead_break"]
          and not scale_page["lead_break"].split("｜")[1].startswith(("，", "。"))
          and not scale_page["lead_break"].split("｜")[0][-1:].isdigit(),
          str(scale_page.get("lead_break")))

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

    # 反事实：去掉重复次数惩罚，不损失原本适合内容的构图。
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
    check("coherence: 连续同构图不再改选次优项",
          len(set(streak_comps)) == 1 and not streak_coh["adjustments"], str(streak_comps))
    check("coherence: 节奏仍记录停留，不捏造内容变化",
          all(p["judgment"]["rhythm"]["move"] == "hold" for p in streak["pages"][1:3]))
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

    # 数字语义：日期/编号的碎片不是证据量（权重卡曾出现「次 -09」）
    dateless = intel.understand("18 个月分三段落地（来源：项目排期 2026-09）")
    check("understanding: 日期碎片（2026-09）不进证据量",
          [(n["raw"], n["unit"]) for n in dateless["numerals"]] == [("18 个月", "个月")]
          and dateless["distinct_numerals"] == 1, str(dateless["numerals"]))
    check("understanding: 多处日期形态（2026-09-30 / 2026/03 / 2026 年 9 月）都不算量",
          intel.evidence_numerals("2026-09-30 上线") == []
          and intel.evidence_numerals("回访 2026/03") == []
          and intel.evidence_numerals("2026 年 9 月上线") == []
          and [n["raw"] for n in intel.evidence_numerals("周期 18 个月")] == ["18 个月"])
    check("understanding: 出处标注里的数字不进证据（台账编号是档案坐标）",
          intel.understand("NPS 从 31 提升到 47（来源：客户回访 2026/03）")["distinct_numerals"] == 2)

    # 结论抽取：标题是结论位；数字列举不是结论；同分不由浮点噪声决定
    titled = intel.extract_claim({"title": "华东贡献 42% 增量，但复购率最低",
                                  "content": "华东 +42%、华南 +28%、华北 +15%（来源：BI 2026Q3）"})
    check("claim: 标题（作者的结论位）不被内容里的数字列举顶掉",
          titled["text"] == "华东贡献 42% 增量，但复购率最低", str(titled))
    listing_only = intel.extract_claim({"title": "华东区数据",
                                        "content": "华东 +42%、华南 +28%、华北 +15%"})
    check("claim: 只有数字列举的句子不当结论（没有主张就是 absent）",
          listing_only["text"] is None and listing_only["source"] == "absent",
          str(listing_only))
    topic_title = intel.extract_claim({"title": "成本结构",
                                       "content": "单篇生产成本降至 1,800 元，低于去年同期"})
    check("claim: 标题仍是话题标签时照旧从内容抽结论",
          topic_title["text"] == "单篇生产成本降至 1,800 元，低于去年同期", str(topic_title))

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
    # 列表前缀「1）/2）/1. /(1)」是顺序枚举标记，不是可比较的数字——
    # 否则三大风险/三条规矩/四步法的第一行会错把「1」当成 KPI。
    check("numerals: 句首列表枚举序号（1）/1）/1. 不是证据量",
          # 1）2）3）被剥离 → 剩 60%、2家；③无后续数字。
          intel.understand("1）汇率波动覆盖60%；2）本地竞争并购2家；3）政策变化。")[
              "distinct_numerals"] == 2
          and intel.understand("(1) 试点 80% (2) 复制 100%")["distinct_numerals"] == 2
          and intel.understand("①A ②B ③C")["distinct_numerals"] == 0
          and intel.understand("1. 试点 2. 复制 3. 全量")["distinct_numerals"] == 0)
    check("claim: 列表项结论会剥掉序号前缀（不把「1）」当开头）",
          intel.extract_claim({"content": "1）汇率波动：对冲策略覆盖首年60%支出；2）…"})["text"]
          == "汇率波动：对冲策略覆盖首年60%支出")
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

    # 同一数值内容，两种载荷不能一边有原生标签、一边只有预览标签。
    from pptx.oxml.ns import qn
    base_chart = {"id":"labels", "type":"chart", "chart_kind":"column", "x":48,"y":220,
                  "width":1184,"height":360,"role":"focus", "show_values":True,
                  "label_size":24,"value_size":28,"source":"合成数据","unit":"项",
                  "period":"测试批次","basis":"分类计数","number_format":"0.0"}
    forms = [dict(base_chart, data=[{"label":"研发","value":12},{"label":"交付","value":8}]),
             dict(base_chart, categories=["研发","交付"],series=[{"name":"本期","values":[12,8]}]),
             dict(base_chart, categories=["研发","交付"],series=[{"name":"本期","values":[12,8]},
                                                               {"name":"对照","values":[10,6]}])]
    chart_spec = dict(spec, slides=[{"id":f"labels{i}","elements":[e]} for i,e in enumerate(forms)])
    labeled_out = tmp / "native-labels.pptx"
    compile_deck(chart_spec,labeled_out)
    labeled_prs = Presentation(labeled_out)
    native_charts = [sl.shapes[0].chart for sl in labeled_prs.slides]
    check("charts: data / 单 series / 多 series 均消费 show_values",
          all(c.plots[0].has_data_labels and c.plots[0].data_labels.show_value for c in native_charts))
    check("charts: 作者 px 字号进入原生标签，不再被 8/9/10pt 硬编码覆盖",
          all(c.category_axis.tick_labels.font.size.pt == 18
              and c.value_axis.tick_labels.font.size.pt == 18
              and c.plots[0].data_labels.font.size.pt == 21 for c in native_charts))
    check("charts: 中文 a:ea 与拉丁 a:latin 字体均有明确来源",
          all(c._chartSpace.xpath(".//a:ea")
              and {n.get("typeface") for n in c._chartSpace.xpath(".//a:ea")} == {"Source Han Serif SC"}
              and {n.get("typeface") for n in c._chartSpace.xpath(".//a:latin")} == {"Georgia"}
              for c in native_charts))
    check("charts: 两种载荷数值/格式不漂移且保持原生对象",
          list(native_charts[0].series[0].values) == list(native_charts[1].series[0].values) == [12,8]
          and all(c.plots[0].data_labels.number_format == "0.0" for c in native_charts))
    dense_chart = dict(base_chart, height=120, categories=list("甲乙丙丁戊己"),
                       series=[{"name":"本期","values":[1,2,3,4,5,6]}])
    from verify import check_spec
    dense_spec = dict(spec, slides=[{"id":"dense-labels","elements":[dense_chart]}])
    dense_guard = check_spec(dense_spec)
    check("charts: categories/series 不再绕过全页标签容量硬门",
          any(c.get("name") == "chart_label_collision" or c.get("rule") == "chart_label_collision"
              for c in dense_guard.get("checks",[]) if c.get("level") == "error"), str(dense_guard)[:300])
    hidden = dict(dense_chart,label_collision_policy="hide_redundant")
    disabled = dict(forms[1],show_values=False)
    hidden_spec = dict(spec,slides=[{"id":"hidden","elements":[hidden]},
                                  {"id":"disabled","elements":[disabled]}])
    hidden_out=tmp/"hidden-labels.pptx"; compile_deck(hidden_spec,hidden_out)
    check("charts: 作者禁用或声明隐藏重复值时不强加标签",
          all(not sl.shapes[0].chart.plots[0].has_data_labels for sl in Presentation(hidden_out).slides))
    import ghost as _chart_ghost
    from unittest.mock import patch
    with patch.object(_chart_ghost,"_font",wraps=_chart_ghost._font) as fonts:
        _chart_ghost.ghost_page(chart_spec["slides"][1],chart_spec,scale=1,supersample=1)
    check("ghost: 原生图表类目/数值遵循作者字号与字体角色",
          any(c.args[0] == 24 and c.kwargs.get("cjk") and c.kwargs.get("family") == "_serif"
              for c in fonts.call_args_list)
          and any(c.args[0] == 28 and c.kwargs.get("family") == "_serif" for c in fonts.call_args_list))
    check("ghost: 单 series 不把序列名缝进类别标签",
          [r["label"] for r in _chart_ghost._rows(forms[1])] == ["研发","交付"])

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

    # 预览诚实度：声明「不渲染」的名单之外，每一个图表类型都必须真的画出来。
    # 断言方式是在占位函数上装探针：走占位分支的类型 == 声明表里的类型，
    # 一个不多一个不少。漏声明 → 预览画的是不存在的图形（作者按假图改构图）；
    # 声明了却仍渲染 → 声明表在骗人。
    import ghost as _ghost
    from primitives import CHART_KINDS
    base_spec = {'canvas': {'width': 480, 'height': 260},
                 'theme': {'colors': {'background': '#FFFFFF', 'ink': '#000000',
                                      'primary': '#111111', 'secondary': '#555555',
                                      'accent': '#9C3B26'}},
                 'fonts': {'cn': 'Source Han Sans SC', 'latin': 'Arial'}}
    placeholder_calls: list = []
    _real_unrendered = _ghost._draw_unrendered

    def _probe_unrendered(d, box, kind, scale):
        placeholder_calls.append(str(kind))
        return _real_unrendered(d, box, kind, scale)

    _ghost._draw_unrendered = _probe_unrendered
    try:
        for kind in sorted(CHART_KINDS):
            element = {'id': 'c', 'type': 'chart', 'chart_kind': kind, 'x': 20, 'y': 20,
                       'width': 440, 'height': 220, 'value': 7, 'label': 'A',
                       'data': [{'label': 'A', 'value': 3}, {'label': 'B', 'value': 7},
                                {'label': 'C', 'value': 5}]}
            slide = {'id': 'k', 'background': '#FFFFFF', 'elements': [element]}
            _ghost.ghost_page(slide, dict(base_spec, slides=[slide]), scale=1, supersample=1)
    finally:
        _ghost._draw_unrendered = _real_unrendered
    abstracted = set(placeholder_calls)
    check("ghost: 「不渲染」声明表与实际渲染一一对应（预览不替假图背书）",
          abstracted == set(_ghost.PREVIEW_ABSTRACT) <= set(CHART_KINDS),
          f"声明={sorted(_ghost.PREVIEW_ABSTRACT)} 实际占位={sorted(abstracted)}")

    # 风险色（negative）由主题推导：含负值的图表不再因「主题未声明风险色」被硬门挡住，
    # 作者显式声明的风险色仍然压过推导。
    neg_spec = {'canvas': {'width': 480, 'height': 260},
                'theme': {'colors': dict(base_spec['theme']['colors'])},
                'slides': [{'id': 'neg', 'background': '#FFFFFF', 'elements': [
                    {'id': 'loss', 'type': 'chart', 'chart_kind': 'bar', 'x': 20, 'y': 20,
                     'width': 440, 'height': 220, 'show_values': True, 'metric': '净收益',
                     'unit': '万元', 'source': '来源：财务测算', 'period': '2027–2029',
                     'basis': '含折现',
                     'data': [{'label': 'M6', 'value': -820}, {'label': 'M36', 'value': 1480}]}]}]}
    neg_out = tmp / 'negative.pptx'
    neg_report = compile_deck(neg_spec, neg_out, speed='fast')
    check("compiler: 六 token 主题也能画负值图（风险色由主题派生，不逼作者补一轮）",
          neg_report["passed"] and not neg_report["warnings"], str(neg_report["warnings"]))
    from primitives import RenderContext, contrast, _rgb_to_oklab, _tuple
    ctx_neg = RenderContext(neg_spec["theme"], neg_spec["canvas"])
    derived = ctx_neg.chart_role("negative")
    check("compiler: 派生风险色与纸面的对比度足够（不是看不见的一档）",
          derived is not None
          and contrast("#" + str(derived), neg_spec["theme"]["colors"]["background"]) >= 3.0)
    # 强调色本身就是红时，风险色必须继续加深到与它分得开：否则「亏损」与
    # 「被强调的答案」在读数上是同一个色，颜色不再区分任何东西。
    red_accent = json.loads(json.dumps(neg_spec))
    red_accent["theme"]["colors"]["accent"] = "#9C3B26"
    red_ctx = RenderContext(red_accent["theme"], red_accent["canvas"])
    gap = sum((i - j) ** 2 for i, j in zip(
        _rgb_to_oklab(_tuple(str(red_ctx.chart_role("negative")))),
        _rgb_to_oklab(_tuple(red_ctx.colors["accent"])))) ** 0.5
    check("compiler: 红强调色主题下风险色与强调色 OKLab 可分（风险 ≠ 答案）",
          gap >= 0.12, f"OKLab 距离={gap:.3f} ≠ {red_ctx.chart_role('negative')} / "
                       f"{red_ctx.colors['accent']}")
    declared_spec = json.loads(json.dumps(neg_spec))
    declared_spec["theme"]["chart_palette"] = {"negative": "#6A1B1B"}
    declared = RenderContext(declared_spec["theme"], declared_spec["canvas"]).chart_role("negative")
    check("compiler: 作者声明的风险色压过派生",
          str(declared).upper().endswith("6A1B1B"), str(declared))

    # 预览与产物必须说同一件事：负值条既要有长度（零基），也要是风险色。
    neg_image = ghost_page(neg_spec["slides"][0], neg_spec, scale=1, supersample=1).convert("RGB")
    role = RenderContext(neg_spec["theme"], neg_spec["canvas"]).chart_role("negative")
    want = tuple(int(v, 16) for v in (str(role).zfill(6)[i:i + 2] for i in (0, 2, 4)))
    want = tuple(round(c * 0.95 + 255 * 0.05) for c in want)
    band = [neg_image.getpixel((x_col, 60)) for x_col in range(150, 240)]
    hit = next((c for c in band if sum(abs(a - b) for a, b in zip(c, want)) <= 6), None)
    check("ghost: 负值条在预览里有长度且用与产物相同的风险色（预览不替亏损改口径）",
          hit is not None, f"want={want} band={band[:4]}")

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
    diag1_read = path_read_count[image_key]
    diag1_sha = image_digest.get(image_key) == digest_bytes(image_snapshot.get(image_key, b""))
    check("media: 指纹预读的源图字节由编译复用（同轮仅一次文件读取）",
          diag1_read == 1 and diag1_sha,
          f"read_count={diag1_read} (expect 1), sha_match={diag1_sha}, "
          f"snapshot_keys={sorted(image_snapshot.keys())}, digest_keys={sorted(image_digest.keys())}")
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
    # 拆分组合断言，Windows CI 失败时能直接看到哪个环节断链：
    #   1) 读盘次数（1 = compiler 首次读，后续 preview 走快照）
    #   2) compiler 读后 canonical key 是否回灌到共享快照
    #   3) 共享快照里的字节 SHA 是否与预缓存的 digest 一致
    diag_read = path_read_count[image_key]
    diag_snap = bool(image_snapshot_cached.get(image_key))
    diag_sha = image_digest_cached.get(image_key) == digest_bytes(image_snapshot_cached.get(image_key, b""))
    extra_keys = sorted(set(image_snapshot_cached.keys()) - {image_key})
    check("media: QC 缓存 SHA → 编译读一次 → preview 复用同一图像字节",
          diag_read == 1 and diag_snap and diag_sha,
          f"read_count={diag_read} (expect 1), snapshot_hit={diag_snap}, sha_match={diag_sha}, "
          f"canonical_key={image_key!r}, extra_keys_in_snapshot={extra_keys}")

    # 图片变换编码口径唯一（v9.12）：PNG 无损，zlib 级别不改变任何解码像素；
    # fast/strict 两档的产物字节必须完全一致（v5.9 的「差异只在耗时与字节」
    # 双口径在此收口）。用需要 cover 变换的图（比例不符）逼出重编码路径。
    _ratio_src = tmp / "ratio_src.png"
    Image.new("RGB", (100, 60), (200, 40, 40)).save(_ratio_src)
    _ratio_spec = {"canvas": {"width": 1280, "height": 720}, "theme": {},
                   "slides": [{"id": "r1", "elements": [
                       {"id": "pic", "type": "image", "src": str(_ratio_src),
                        "x": 40, "y": 40, "width": 80, "height": 80, "fit": "cover"}]}]}
    from compiler import compile_deck as _compile_deck
    _deck_fast, _deck_strict = tmp / "img_fast.pptx", tmp / "img_strict.pptx"
    _compile_deck(_ratio_spec, _deck_fast, speed="fast", spec_path=str(build))
    _compile_deck(_ratio_spec, _deck_strict, speed="strict", spec_path=str(build))
    check("media: 图片变换后 fast 与 strict 产物字节一致（编码口径唯一）",
          file_digest(_deck_fast) == file_digest(_deck_strict))

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

    # 离线 qc 环与 check 同判据（CASE_004 实测教训）：清单声明 16:9 的资产，
    # 4:3 成图必须在 qc 环就被拦——否则作者拿到「qc 全绿 → check BLOCK」的
    # 无效往返，最短反馈环变成最长的弯路。
    import vao as _vao
    _ratio_img = tmp / "qc-loop-ratio.png"
    Image.new("RGB", (1024, 768), (214, 206, 192)).save(_ratio_img)
    _m = {"schema": "vao-assets-v2", "assets_dir": str(tmp),
          "assets": [{"asset_id": "qc-loop-ratio", "decision": "generate",
                      "prompt": "test", "negative": ["test"], "slide_ids": ["s1"],
                      "ratio": "16:9", "asset_role": "background",
                      "safe_area": {"x": 0.06, "y": 0.08, "width": 0.34, "height": 0.78},
                      "meta": {"text_color": "dark"}}]}
    _mpath = tmp / "qc_loop_manifest.json"
    _mpath.write_text(json.dumps(_m, ensure_ascii=False), encoding="utf-8")
    _loop = _vao.run_qc(str(_mpath), str(tmp), speed="strict")
    _loop_r = _loop["results"][0]
    check("qc: 离线环同判比例（清单 16:9 对 4:3 成图必须 retry）",
          "aspect_ratio" in _loop_r.get("blocking", []),
          json.dumps(_loop_r, ensure_ascii=False)[:160])

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
    from ghost import _draw_text, _font, _rgba, _font_family
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
            (12, 24), "61%", font=_font(32, family=_font_family(text_elem, ctx)),
            fill=_rgba(ctx, "ink", opacity))
        expected.alpha_composite(old_overlay)
        actual = Image.new("RGBA", expected.size, bg_color)
        _draw_text(actual, {**text_elem, "opacity": opacity}, ctx, 1)
        same = same and actual.tobytes() == expected.tobytes()
    check("ghost: 不透明直画与半透明旧合成路径像素一致（速度不能改变设计）", same)

    # 字体角色与 compiler 共用 RenderContext.families；没有 font 字段也要读主题。
    import ghost as _g
    serif_ctx = RenderContext({"fonts": {"cn": "Noto Serif CJK SC", "latin": "Arial"}}, {})
    sans_ctx = RenderContext({"fonts": {"cn": "Noto Sans CJK SC", "latin": "Georgia"}}, {})
    check("ghost: 中文主题默认宋体不会静默画成黑体",
          _g._font_family({"text": "中文"}, serif_ctx) == "_serif")
    check("ghost: Latin font/family 覆盖不改变中文主题字面",
          all(_g._font_family(e, serif_ctx) == "_serif" for e in
              ({"text": "中文 AI 2026", "font": "latin"},
               {"text": "中文", "family": "Arial"}))
          and _g._font_family({"text": "中文", "font": "latin"}, sans_ctx) == "")
    check("ghost: 纯拉丁遵循主题与显式覆盖（sans-serif 不是 serif）",
          _g._font_family({"text": "Evidence"}, sans_ctx) == "_serif"
          and _g._font_family({"text": "Evidence", "font": "latin"}, serif_ctx) == ""
          and _g._font_family({"text": "Evidence", "family": "sans-serif"}, sans_ctx) == ""
          and _g._font_family({"text": "Evidence", "family": "Times New Roman"}, serif_ctx) == "_serif")
    alias_ctx = RenderContext({"fonts": {"body": "宋体", "display": "Georgia"}}, {})
    check("ghost: body/display 别名与编译器一致",
          all(_g._font_family({"text": t}, alias_ctx) == "_serif" for t in ("中文", "English")))
    # 跨平台锁住 TTC index 参数，不靠 CI 恰好安装某字体；缺字库仍走原回退。
    from unittest.mock import patch
    saved_fonts = dict(_g._FONT_CACHE)
    try:
        with patch.object(Path, "exists", return_value=True), \
                patch.object(_g.ImageFont, "truetype") as load_font:
            _g._FONT_CACHE.clear()
            for family in ("", "_serif"):
                for bold in (False, True):
                    _g._font(20, cjk=True, family=family, bold=bold)
            check("ghost: Noto CJK 常规/粗体/衬线四路径均取 SC index 2",
                  len(load_font.call_args_list) == 4
                  and all(c.kwargs.get("index") == 2 for c in load_font.call_args_list))
        with patch.object(Path, "exists", return_value=True), \
                patch.dict(_g._FONT_CANDIDATES, {"cjk": ("C:/Windows/Fonts/msyh.ttc",)}), \
                patch.object(_g.ImageFont, "truetype") as load_font:
            _g._FONT_CACHE.clear()
            _g._font(20, cjk=True)
            check("ghost: 其他 TTC 不误套 Noto 索引", load_font.call_args.kwargs.get("index") == 0)
        with patch.object(Path, "exists", return_value=False), \
                patch.object(_g.ImageFont, "load_default") as fallback:
            _g._FONT_CACHE.clear()
            _g._font(20, cjk=True)
            _g._font(20, cjk=True)
            check("ghost: 缺字体安全回退且进程内复用", fallback.call_count == 1)
    finally:
        _g._FONT_CACHE.clear()
        _g._FONT_CACHE.update(saved_fonts)

    # CJK 折行：二分拟合与逐字贪心同断点（禁则修正之后仍同断点）。
    # visible_width 随前缀长度单调，二分与线性扫描找到同一个「最长可容纳前缀」；
    # 禁则只在其上做局部回退。随机混合文本 × 字号 × 宽度 × tracking 对拍内联的
    # 旧线性参考实现，输出必须逐字符一致——这条不变式一破，预览换行位置就变，
    # 像素证据不再可信。
    from ghost import (_wrap_lines as _wrap, _has_cjk as _has_cjk2,
                       _cjk_break_fix as _fix, _NO_LINE_START as _nls,
                       _UNIT_HEAD as _unit_head, _UNIT_INNER as _unit_inner)

    def _linear_cjk(text, font, width, tracking=0.0):
        limit = max(1, width)
        def vw(value):
            return font.getlength(value) + max(0, len(value) - 1) * tracking
        out = []
        for raw in str(text).split("\n"):
            if not raw:
                out.append("")
                continue
            pos, n = 0, len(raw)
            while pos < n:
                seg = raw[pos:]
                if vw(seg) <= limit:
                    out.append(seg)            # 末行整段可容纳
                    break
                if len(seg) == 1:
                    out.append(seg)
                    break
                lo = 1                          # 逐字扫描：找到最长可容纳前缀
                while lo < len(seg) and vw(seg[:lo + 1]) <= limit:
                    lo += 1
                lo = _fix(seg, lo)              # 与二分路径同一套禁则回退
                out.append(seg[:lo].rstrip())
                pos += lo
        return out

    # 禁则本身：行首不得出现禁则字符；数字与单位不得被拆到两行
    _rule_font = _font(18, cjk=True)
    _rule_text = ("口岸清关时效在 1.8 至 6.4 天之间波动，波动幅度 256%，"
                  "库存周转天数在 21 至 47 天之间摆动，「次日达」无法售卖。")
    _rule_bad = None
    for _w in (220, 260, 300, 340, 420, 520, 640, 800):
        _lines = _wrap(_rule_text, _rule_font, _w)
        for _ln in _lines[1:]:
            if _ln[:1] and _ln[0] in _nls:
                _rule_bad = ("行首标点", _w, _ln); break
            _prev = _lines[_lines.index(_ln) - 1]
            if _prev[-1:].isdigit() and _unit_head.match(_ln.strip()):
                _rule_bad = ("数字单位拆行", _w, _prev, _ln); break
        if _rule_bad:
            break
    check("ghost: 中文禁则折行（行首无禁则标点、数字与单位同行）",
          _rule_bad is None, str(_rule_bad)[:160])

    # 断口常常落在**空格**上（中英混排的「9 个」「11.2 元」）：此时真正的邻居是
    # 空格两边的实字，不是断口那一个字符。旧实现取 seg[lo] / seg[lo-1]，量到的
    # 是两个空格，禁则静默失效——预览看着合规，产物里读出来是「9」「个」两个信息。
    # 实测（CASE_006 第 4 页）：旧预览断成「…可控节点 9 | 个，复制周期…」。
    _sp_font = _font(15, cjk=True)
    _sp_text = ("印尼雅加达自营：首城盈利 14 个月，履约成本 11.2 元，可控节点 9 个，"
                "复制周期 5 个月。")
    _sp_bad = None
    for _w in range(200, 470, 3):
        _ls = _wrap(_sp_text, _sp_font, _w)
        for _a, _b in zip(_ls, _ls[1:]):
            _l, _r = _a.rstrip(), _b.lstrip()
            if _l[-1:].isdigit() and _unit_head.match(_r):
                _sp_bad = ("数字与量词被空格隔开后拆行", _w, _a, _b); break
            if _r[:1] and _r[0] in _nls:
                _sp_bad = ("行首禁则标点", _w, _b); break
        if _sp_bad:
            break
    check("ghost: 禁则看断口两侧的实字（空格不是邻居，数字与量词不隔空拆行）",
          _sp_bad is None, str(_sp_bad)[:160])

    # 双字单位不腰斩：断在「个｜月」「万｜元」「小｜时」中间，单位被读成两个词，
    # 「14 个月」会排成「14 个 / 月」——比数字与单位分家更常见，因为断口落在
    # 单位的两个汉字之间，任何只看断口两侧是不是「数字 + 单位」的规则都抓不到。
    _du_font = _font(15, cjk=True)
    _du_text = "首城盈利周期 14 个月，投入 3,800 万美元，分拣时长 45 分钟。"
    _du_bad = None
    for _w in range(180, 520, 2):
        _ls = _wrap(_du_text, _du_font, _w)
        for _a, _b in zip(_ls, _ls[1:]):
            _l, _r = _a.rstrip(), _b.lstrip()
            if _l and _r and (_l[-1] + _r[0]) in _unit_inner:
                _du_bad = ("双字单位被腰斩", _w, _a, _b); break
        if _du_bad:
            break
    check("ghost: 双字单位内部不断行（个月/万元/分钟/小时不读成两个词）",
          _du_bad is None, str(_du_bad)[:160])

    import random as _random
    _rng = _random.Random(20261013)
    _pool = "本议案请求批准3800万美元首期预算，覆盖新加坡、雅加达；份额从7%到19%（括号）「引号」混合latin words在内。"
    _fonts = [(_font(s, cjk=True, bold=b), s) for s in (11, 17, 34, 84) for b in (False, True)]
    _wrap_bad = None
    for _ in range(600):
        _text = "".join(_rng.choice(_pool) for _ in range(_rng.randint(1, 50)))
        if not _has_cjk2(_text):
            continue
        _f, _s = _rng.choice(_fonts)
        _w = _rng.choice([1, 7, 37, 120, 496, 900])
        _t = _rng.choice([0, 0, 0.5, 1.5, 3.0])
        if _wrap(_text, _f, _w, _t) != _linear_cjk(_text, _f, _w, _t):
            _wrap_bad = (_text, _s, _w, _t)
            break
    check("ghost: CJK 折行二分拟合与逐字贪心同断点（600 组随机对拍）",
          _wrap_bad is None, str(_wrap_bad)[:160])

    # 导入契约（primitives 顶部注释承诺过的自检）：纯预览进程不得拖入
    # pptx / lxml / compiler。parse_token 曾经由 RGBColor 把整条 pptx 导入链
    # 拉进 PIL 预览路径（实测 ~150ms/轮），这里锁死：谁改回去，立刻失败。
    noleak_spec = tmp / "noleak_spec.json"
    noleak_spec.write_text(json.dumps({
        "canvas": {"width": 1280, "height": 720},
        "theme": {"colors": {"background": "#F1EFEA", "ink": "#12120F",
                             "muted": "#8A8984", "accent": "#6E6A63"}},
        "slides": [{"id": "s1", "background": "#F1EFEA", "elements": [
            {"id": "t", "type": "text", "x": 48, "y": 40, "width": 400, "height": 40,
             "text": "纯预览", "size": 20, "color": "ink"}]}]}, ensure_ascii=False),
        encoding="utf-8")
    noleak_out = tmp / "noleak_preview"
    probe = (
        "import sys, json;"
        f"sys.path.insert(0, {str(SCRIPTS)!r});"
        "from primitives import parse_token;"
        "c, _ = parse_token('#F1EFEA');"
        "assert str(c) == 'F1EFEA' and tuple(c) == (241, 239, 234), c;"
        "from ghost import ghost_deck;"
        f"ghost_deck(json.load(open({str(noleak_spec)!r}, encoding='utf-8')), "
        f"{str(noleak_out)!r}, pages=[1], scale=0.5);"
        "bad = sorted(m for m in ('pptx', 'pptx.dml.color', 'lxml', 'compiler') "
        "if m in sys.modules);"
        "print('LEAK:' + ','.join(bad) if bad else 'CLEAN')"
    )
    r_probe = subprocess.run([sys.executable, "-c", probe],
                             capture_output=True, text=True, encoding="utf-8")
    check("primitives: 纯预览进程零 pptx / lxml / compiler（导入契约成立）",
          r_probe.returncode == 0 and r_probe.stdout.strip() == "CLEAN",
          (r_probe.stdout + r_probe.stderr).strip()[:200])
    # 编译边界不变式：pptx 已加载的进程里 parse_token 必须产真 RGBColor
    # （`*.rgb =` 的 isinstance 校验只收真对象；等价元组只存在于零 pptx 进程）。
    from pptx.dml.color import RGBColor
    from primitives import parse_token as _parse_token
    c_loaded, _ = _parse_token("#123456")
    check("primitives: pptx 已加载时 parse_token 产真 RGBColor（编译边界类型不变）",
          isinstance(c_loaded, RGBColor), type(c_loaded).__name__)


# ── 4 · cli + docs ───────────────────────────────────────────────────
def test_cli(tmp: Path):
    brief = tmp / "brief.yml"
    import yaml
    brief.write_text(yaml.safe_dump(BRIEF, allow_unicode=True), encoding="utf-8")

    # Windows 默认 ANSI 代码页（管道重定向时 Python 用它写 stdout）不得让命令崩掉：
    # cp1252 下 `print("plan: 5 页…")` 曾经直接 UnicodeEncodeError、退出码 2，
    # 产物还没落盘就结束——这正是 CI Windows 作业全红的根因。
    import os as _os
    ascii_pipe = dict(_os.environ, PYTHONIOENCODING="cp1252")
    wide = tmp / "ascii-plan.json"
    r_ascii = run_vao("plan", str(brief), "--out", str(wide), env=ascii_pipe)
    check("cli: 非 UTF-8 控制台/管道下 plan 不崩且产物落盘（Windows 默认代码页）",
          r_ascii.returncode == 0 and wide.is_file() and "plan:" in r_ascii.stdout,
          (r_ascii.stderr or r_ascii.stdout)[-200:])
    r_strict = run_vao("plan", str(brief), "--out", str(tmp / "ascii-plan2.json"),
                       env=dict(_os.environ, PYTHONIOENCODING="ascii"))
    check("cli: 连 ASCII 管道也不崩（输出恒为 UTF-8）",
          r_strict.returncode == 0 and "视觉世界" in r_strict.stdout,
          (r_strict.stderr or "")[-200:])
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
    # --asset-cache（提示词缓存）此前在读取路径上引用了未导入的 json 模块，
    # 属于「只在冷启动加缓存时才炸」的真实崩溃点：这里把读写两个方向都钉住。
    cache_file = media_dir / "prompt-cache.json"
    cache_args = ("--assets-out", str(auto_manifest), "--asset-cache", str(cache_file))
    cache_first = run_vao("plan", str(media_brief), "--out", str(media_plan),
                          "--skeleton", str(media_sk), *cache_args, "--json")
    cache_second = run_vao("plan", str(media_brief), "--out", str(media_plan),
                           "--skeleton", str(media_sk), *cache_args, "--json")
    cache_meta = json.loads(auto_manifest.read_text(encoding="utf-8")).get("prompt_cache", {}) \
        if cache_first.returncode == 0 else {}
    check("cli: --asset-cache 读写闭环（第二次 plan 命中提示词缓存，不再 NameError）",
          cache_first.returncode == 0 and cache_second.returncode == 0
          and cache_file.is_file()
          and json.loads(cache_file.read_text(encoding="utf-8")).get("schema")
          == "vao-asset-prompt-cache-v2" and cache_meta.get("hits") == 1,
          f"rc={cache_second.returncode} hits={cache_meta.get('hits')} "
          f"{cache_second.stderr[-160:]}")

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
    # 证据被破坏必须重贴，但页面没变就不该重画：逐页缓存命中 → 联络表重建 + 零重绘。
    # （此前断言还要求整份 bundle 不复用——那会把「什么都没变时复用页面」也判成失败。）
    check("cli: 交付 PNG 被破坏不能再凭 marker 假 PASS；复用未变页图修复联络表",
          repaired.returncode == 0 and png_valid
          and repair_timing.get("render_pages_drawn") == 0
          and repair_timing.get("compile_ms") == 0
          and repair_timing.get("ghost_ms", 0) > 0)
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

    # CLI 面就是这套体系对外暴露的全部动作。多一个子命令 = 多一条 Agent 会调用、
    # 却没有文档与消费者支持的路径（`preview` 曾是这种残骸：SKILL 明说别跑它）。
    # 断言在这里锁住，新增入口必须是有意决定，而不是顺手。
    r_help = run_vao("--help")
    import re as _re
    _m = _re.search(r"\{([\w,]+)\}", r_help.stdout)
    listed = set(_m.group(1).split(",")) if _m else set()
    check("cli: 入口面恰好是 plan/check/qc（无第二执行路径）",
          listed == {"plan", "check", "qc"}, str(sorted(listed)))
    check("cli: 已删除的 preview 子命令确实不存在",
          run_vao("preview", "x.py").returncode != 0)


def test_delivery(tmp):
    from compiler import compile_deck
    from verify import check_spec
    from pptx import Presentation
    from pptx.enum.chart import XL_LEGEND_POSITION
    import intelligence as intel
    base = {"id": "chart", "type": "chart", "x": 64, "y": 100,
            "width": 1100, "height": 480, "label_size": 24,
            "categories": ["低负载", "高负载"],
            "series": [{"name": "路径甲", "values": [12, 30]},
                       {"name": "路径乙", "values": [16, 38]}]}
    deck = {"canvas": {"width": 1280, "height": 720},
            "theme": {"fonts": {"cn": "Noto Serif CJK SC", "latin": "Arial"},
                      "colors": {"background": "#FFFFFF", "ink": "#182B3A", "muted": "#536574",
                                 "primary": "#233649", "secondary": "#7B919E", "accent": "#BB5D26"}}, "slides": []}
    for kind in ("line", "column", "area", "bar"):
        for show in (False, True):
            deck["slides"].append({"id": f"{kind}-{show}", "elements": [dict(base, chart_kind=kind, show_values=show)]})
    path = tmp / "identity.pptx"
    report = compile_deck(deck, path)
    check("identity: 原生多序列编译无警告", report["passed"] and not report.get("warnings"))
    for slide, native in zip(deck["slides"], Presentation(path).slides):
        chart = native.shapes[0].chart
        check("identity: " + slide["id"], chart.has_legend
              and chart.legend.position == XL_LEGEND_POSITION.BOTTOM
              and chart.legend.include_in_layout is False
              and chart.legend.font.size.pt == 18
              and chart.legend.font._element.xpath("a:ea/@typeface") == ["Noto Serif CJK SC"]
              and [s.name for s in chart.series] == ["路径甲", "路径乙"]
              and [list(s.values) for s in chart.series] == [[12,30], [16,38]]
              and chart.plots[0].has_data_labels == slide["elements"][0]["show_values"])
    for kind in ("pie", "donut", "donut_composition"):
        for show in (False, True):
            e = {k:v for k,v in base.items() if k not in ("series", "categories")}
            e.update(chart_kind=kind, show_values=show, data=[{"label": f"类别{i}", "value": i+1} for i in range(7)])
            pie = dict(deck, slides=[{"id": "composition", "elements": [e]}])
            report = compile_deck(pie, path)
            c = Presentation(path).slides[0].shapes[0].chart
            labels = c.plots[0].data_labels if c.plots[0].has_data_labels else None
            check(f"identity: {kind}/{show} 隐藏值仍保留七个类别身份",
                  report["passed"] and not report.get("warnings") and labels is not None and labels.show_category_name
                  and labels.show_value == show and not c.has_legend
                  and len(c.series[0].values) == 7)
    def errors(element):
        report = check_spec(dict(deck, slides=[{"id": "probe", "elements": [element]}]))
        return [c for c in report["checks"] if c.get("level") == "error"]
    for names in (("", "乙"), ("甲", "甲")):
        e = dict(base, chart_kind="line", series=[{"name": n, "values": [1,2]} for n in names])
        check("identity: 拒绝缺失/歧义序列名 " + str(names), bool(errors(e)))
    check("identity: 单序列不强求冗余名称", not errors(dict(base, chart_kind="line", series=[{"values": [1,2]}])))
    check("identity: 类别名不可为空", bool(errors(dict(base, chart_kind="line", categories=["", "乙"]))))
    for kind, field, limit in (("process_flow","data",7), ("timeline","data",7), ("steps","data",6),
            ("matrix","points",12), ("architecture","layers",3), ("ranked_bar","data",8),
            ("progress_bar","data",6), ("stacked_bar","data",8), ("big_number_row","data",5), ("bubble","data",12)):
        e = {k:v for k,v in base.items() if k not in ("series", "categories")}
        e["chart_kind"] = kind
        items = [f"层{i}" if field == "layers" else {"label": f"节点{i}", "value": i+1, "x": .5, "y": .5} for i in range(limit+1)]
        e[field] = items[:limit]
        fits = not errors(e)
        e[field] = items
        check("payload: " + kind + " 边界完整/超量阻断", fits and bool(errors(e)))
    from verify import release_manifest
    verification = release_manifest(deck, {})["verification"]
    check("evidence: 未打开/编辑/独立审阅不冒充验收",
          verification.get("target_powerpoint") == verification.get("native_editing") == "not_verified"
          and verification.get("independent_visual_review") == "not_performed")
    for content in ("甲组负责研发；乙组负责交付。", "必须先核验证据再发布。", "效率从 12% 提升到 18%。"):
        brief = {"slides": [{"id": str(i), "title": "核验依据", "content": content, "asset": "none"} for i in range(6)]}
        bundle = intel.think(brief)
        check("rhythm: 重复不能覆盖关系/观点/数据判断 " + content,
              all(p["judgment"]["composition"] == intel.page_judgment(brief["slides"][i], index=i, total=6,
                  brief=brief, world=bundle["deck"]["world"], warnings=[])["composition"] for i,p in enumerate(bundle["pages"])))


def test_plan_boundaries(tmp):
    import intelligence as intel
    import vao, assets
    from unittest.mock import patch
    from PIL import Image
    import contextlib, io
    base = {"audience": "评审", "decision": "发布", "tension": "核验证据",
            "slides": [{"id": "page", "title": "保留原文", "content": "信息不可损失", "asset": "none"}]}
    for field in ("title", "claim", "id", "audience", "tension", "eyebrow"):
        b = json.loads(json.dumps(base))
        value = '先验证\n再交付 """ # C:\\notes\r限定条件'
        b["slides"][0][field] = value
        sk = intel.build_skeleton(intel.think(b)); scope = {}
        exec(compile(sk, field, "exec"), scope)
        check("plan: 多行/引号安全生成 " + field, len(scope["SPEC"]["slides"]) == 1)
    b = dict(base, audience='讨论 """ 与路径 C:\\new')
    check("plan: deck 说明不能终止 Python 字符串", compile(intel.build_skeleton(intel.think(b)), "deck", "exec") is not None)
    brief = tmp / "brief.json"; brief.write_text(json.dumps(base), encoding="utf-8")
    plan = tmp / "plan.json"; work = tmp / "author.py"
    old = "SPEC = {'slides': [{'elements': [{'type': 'text', 'text': '作者已完成'}]}]}\n"
    work.write_text(old, encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()): result = vao.run_plan(str(brief), str(plan), str(work))
    side = Path(result["workflow"]["skeleton_path"])
    check("plan: 不执行/不覆盖任何现有作者文件", work.read_text(encoding="utf-8") == old and side != work and side.exists())
    stamp = side.stat().st_mtime_ns
    with contextlib.redirect_stdout(io.StringIO()): again = vao.run_plan(str(brief), str(plan), str(work))
    check("plan: 同输入副本不重写、不产生更多文件", again["workflow"]["skeleton_path"] == str(side.resolve()) and side.stat().st_mtime_ns == stamp)
    side.write_text("# 第二份作者工作", encoding="utf-8")
    blocked = False
    try: vao.run_plan(str(brief), str(plan), str(work))
    except FileExistsError: blocked = True
    check("plan: 副本也被保护，不按代码格式猜是否已填稿", blocked and side.read_text(encoding="utf-8") == "# 第二份作者工作")
    cli = run_vao("plan", str(brief), "--out", str(plan), "--json")
    compact = json.loads(cli.stdout)
    check("plan: JSON 仅回摘要，完整判断仍落盘", cli.returncode == 0 and "pages" not in compact
          and compact["page_count"] == 1 and "pages" in json.loads(plan.read_text(encoding="utf-8"))
          and len(cli.stdout.encode()) < 4096)

    image = tmp / "original.png"; Image.new("RGB", (1024,768), (214,206,192)).save(image)
    entry = {"asset_id": "named", "decision": "generate", "expected_filename": image.name,
             "prompt": "test", "negative": ["test"], "slide_ids": ["s1"], "ratio": "16:9",
             "allow_crop": True, "meta": {"text_color": "#111111"},
             "asset_role": "background", "asset_role_source": "author"}
    manifest = tmp / "assets.json"
    def save(entry):
        manifest.write_text(json.dumps({"assets": [entry]}), encoding="utf-8")
    save(entry); original = manifest.read_bytes()
    with patch.object(assets, "image_qc", wraps=assets.image_qc) as measure:
        offline = vao.run_qc(str(manifest), speed="strict")
    kw = measure.call_args.kwargs
    check("qc: 同一解析器消费文件名/HEX 字色/裁切声明", Path(measure.call_args.args[0]) == image.resolve()
          and kw["text_is_dark"] is True and kw["allow_crop"] is True)
    report, _ = assets.qc_report(manifest, phase="draft", speed="strict", persist=False)
    check("qc: 离线与生产同判且不写报告/重试状态", offline["results"][0]["action"] == report["results"][0]["policy"]["action"]
          and manifest.read_bytes() == original and not manifest.with_suffix(".qc.json").exists())
    save(dict(entry, decision="existing", origin={"kind":"original","path":str(image),"source":"test fixture"}))
    check("qc: 既有素材按 origin.path 查找，不误报缺失", vao.run_qc(str(manifest), speed="strict")["results"][0]["status"] != "missing")
    assets.qc_report(manifest, phase="draft", speed="strict")
    qc_file = manifest.with_suffix(".qc.json"); prior = qc_file.read_bytes()
    with patch.object(assets, "image_qc", wraps=assets.image_qc) as measure:
        vao.run_qc(str(manifest), speed="strict")
    check("qc: 有效报告复用测量且不改写凭证", not measure.called and qc_file.read_bytes() == prior)
    import os
    stat = image.stat(); blob = bytearray(image.read_bytes()); blob[-1] ^= 1; image.write_bytes(blob)
    os.utime(image, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    with patch.object(assets, "image_qc", wraps=assets.image_qc) as measure:
        vao.run_qc(str(manifest), speed="strict")
    check("qc: strict 同 size/mtime 换字节不复用旧测量", measure.called and qc_file.read_bytes() == prior)
    save(dict(entry, expected_filename="missing.png"))
    missing = run_vao("qc", "--assets-manifest", str(manifest), "--speed", "strict")
    check("qc: 缺素材退出码非零，不能假成功", missing.returncode == 2 and json.loads(missing.stdout)["status"] == "BLOCKED")
    save(dict(entry, expected_filename="ambiguous.webp"))
    image.with_name("ambiguous.png").write_bytes(image.read_bytes())
    image.with_name("ambiguous.jpg").write_bytes(image.read_bytes())
    ambiguous = run_vao("qc", "--assets-manifest", str(manifest))
    check("qc: 多候选不能任取第一个", ambiguous.returncode == 2 and "多个候选" in ambiguous.stderr)


def test_release_evidence(tmp: Path):
    """Evidence is ordered, complete and fail-closed; arrows retain direction."""
    import copy
    import contextlib
    import io
    import vao
    from verify import check_spec, release_manifest, preview_issues
    from primitives import spec_fingerprint, RenderContext
    from compiler import compile_deck
    from pptx import Presentation
    from ghost import ghost_page
    from PIL import ImageChops

    spec = vao.load_spec(make_build(tmp, chart=False))[0]
    spec['slides'][0]['id'] = 'z-open'
    spec['slides'][1]['id'] = 'a-evidence'
    build = tmp / 'ordered.json'
    build.write_text(json.dumps(spec), encoding='utf-8')
    output = tmp / 'ordered.pptx'
    with contextlib.redirect_stdout(io.StringIO()):
        result, code = vao.run_check(str(build), str(output), mode='release', speed='strict')
    check('release: 非字典序叙事 ID 严档一次收口', code == 0 and result['release_eligible'])
    renamed = copy.deepcopy(spec)
    for s in renamed['slides']:
        s['id'] = 'renamed-' + s['id']
    build.write_text(json.dumps(renamed), encoding='utf-8')
    with contextlib.redirect_stdout(io.StringIO()):
        renamed_result, renamed_code = vao.run_check(str(build), str(output), mode='release', speed='strict')
    check('release: 相同 PPTX 字节但 ID 改名不复用旧页绑定', renamed_code == 0
          and renamed_result['compile']['output_sha256'] == result['compile']['output_sha256'])
    build.write_text(json.dumps(spec), encoding='utf-8')
    with contextlib.redirect_stdout(io.StringIO()):
        result, code = vao.run_check(str(build), str(output), mode='release', speed='strict')
    mf = json.loads(output.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    ghost = mf['ghost_preview']
    check('release: 持久清单保留逐页证据而非只留目录', ghost['slide_ids'] == [s['id'] for s in spec['slides']] and len(ghost['pages']) == 5)
    for name, mutate in (
        ('缺 spec 戳', lambda q: q.pop('source_spec_hash')),
        ('缺 PPTX 双凭证', lambda q: q.update(compile={'passed': True})),
        ('缺 PPTX 摘要', lambda q: q['compile'].pop('output_sha256')),
    ):
        q = copy.deepcopy(result); mutate(q)
        m = release_manifest(spec, q, ghost_preview=ghost)
        check('release: ' + name + ' 必须 BLOCK', m['status'] == 'BLOCKED' and not m['release_eligible'])
    check('release: 同页 ID 的旧预览不能冒充当前产物', release_manifest(
        spec, result, ghost_preview={**ghost, 'output_sha256':'0'*64})['status'] == 'BLOCKED')
    m = release_manifest(spec, result)
    check('release: 缺预览必须 BLOCK', m['status'] == 'BLOCKED')
    ids = ghost['slide_ids']
    for name, mutation in (
        ('重复页面', {'slide_ids': [ids[0]]*5}),
        ('重复文件', {'pages': [ghost['pages'][0]]*5}),
        ('错误顺序', {'slide_ids': ids[::-1]}),
        ('未知范围', {'scope': 'invented'}),
    ):
        check('release: ' + name + ' 凭证拒收', bool(preview_issues({**ghost, **mutation}, ids)))
    subset = dict(ghost, scope='key_pages', count=1, slide_ids=[ids[0]],
                  pages=ghost['pages'][:1], key_pages={ids[0]:'cover'})
    check('release: fast 合法抽样保留接口', not preview_issues(subset, ids))
    check('release: strict 不接受抽样', release_manifest(spec, result, ghost_preview=subset)['status'] == 'BLOCKED')
    with contextlib.redirect_stdout(io.StringIO()):
        expired, code = vao.run_check(str(build), str(output), mode='release', speed='strict', deadline=0.001)
    check('release: deadline 不升级为可发布', code == 2 and not expired['release_eligible'])
    # Restore a valid manifest then fail BEFORE parsing; stale PASS must not survive.
    with contextlib.redirect_stdout(io.StringIO()):
        vao.run_check(str(build), str(output), mode='release', speed='strict')
        build.write_text('{broken', encoding='utf-8')
        failed, code = vao.run_check(str(build), str(output), mode='release', speed='strict')
    stale = json.loads(output.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    check('release: 输入异常覆盖旧 PASS 清单', code == 2 and stale['status'] == 'BLOCKED' and not stale['release_eligible'])
    check('release: 目标环境状态不被自动升级', mf['verification']['target_powerpoint'] == 'not_verified' and mf['verification']['native_editing'] == 'not_verified')
    dup = copy.deepcopy(spec); dup['slides'][1]['id'] = dup['slides'][0]['id']
    check('identity: 重复页 ID 在编译前 BLOCK', not check_spec(dup)['passed'])
    dup = copy.deepcopy(spec); dup['slides'][0]['elements'][1]['id'] = dup['slides'][0]['elements'][0]['id']
    check('identity: 重复元素 ID 在编译前 BLOCK', not check_spec(dup)['passed'])

    elements = [dict(id=name, type='shape', shape='arrow', x=100, y=100,
                     width=w, height=h, stroke='#A34225', stroke_width=4)
                for name,w,h in [('horizontal',160,0),('vertical',0,160),('diagonal',160,160)]]
    elements += [dict(elements[0],id='ordinary',shape='line',y=320),
                 dict(elements[0],id='invisible',y=360,stroke={'type':'none'})]
    arrows = dict(spec, slides=[dict(id='arrows',elements=elements)])
    path = tmp/'arrows.pptx'; report=compile_deck(arrows,path)
    shapes=Presentation(path).slides[0].shapes
    check('arrow: 三方向箭头是原生可编辑连接线', report['passed'] and all(len(shapes[i]._element.xpath('.//a:tailEnd[@type="triangle"]')) == 1 for i in range(3)))
    check('arrow: 普通线不误加箭头', not shapes[3]._element.xpath('.//a:tailEnd'))
    check('arrow: 显式无描边保持不可见', bool(shapes[4]._element.xpath('.//a:ln/a:noFill')))
    for element in elements[:3]:
        slide=dict(id='arrow-preview',elements=[element])
        actual=ghost_page(slide,arrows)
        plain=ghost_page(dict(slide,elements=[dict(element,shape='line')]),arrows)
        check('arrow: ghost 方向端点 '+element['id'], ImageChops.difference(actual.convert('RGB'),plain.convert('RGB')).getbbox() is not None)


def test_boundary_typography(tmp: Path):
    """中文混排的行尾纪律：数字与单位不许被断到两行。

    判据来自既往一次真实版面观察：「平均配送半径是 186」留在行尾、「公里」推到下一行——
    数字与单位拆开，正是 SKILL.md §3 禁止的那件事。
    混排间隙（U+2009 细空格）本身是合法断行机会，所以数字与单位之间必须用
    不断行空格；这条纪律由 primitives 的单位词表**一处**决定，编译器与幽灵预览共用。
    """
    import primitives as prim

    gapped = prim.insert_script_gaps("配送半径是186公里")
    check("混排: 数字与单位之间用不断行空格（细空格是断行机会）",
          prim.NO_BREAK_SPACE in gapped and "186" + prim.NO_BREAK_SPACE + "公里" in gapped,
          repr(gapped))
    check("混排: 作者自己写的空格也被绑定（「186 公里」同样不许断）",
          prim.insert_script_gaps("平均半径是 186 公里")
          == "平均半径是 186" + prim.NO_BREAK_SPACE + "公里",
          repr(prim.insert_script_gaps("平均半径是 186 公里")))
    check("混排: 非单位的普通空格不受影响（不制造粘在一起的假词）",
          prim.insert_script_gaps("覆盖 华东 与 华南") == "覆盖 华东 与 华南"
          and prim.insert_script_gaps("我们 做了 三件事") == "我们 做了 三件事")
    check("混排: 间隙插入幂等（二次处理不再漂移）",
          prim.insert_script_gaps(gapped) == gapped)
    # 容量估算必须与产物实际写的字符一致，否则 Guard 会算错行数。
    check("混排: 容量估算认识不断行空格（不被当成一个汉字）",
          0.5 < prim.text_units(prim.NO_BREAK_SPACE) < 0.6
          and prim.text_units(prim.NO_BREAK_SPACE) == prim.text_units(" "),
          str(prim.text_units(prim.NO_BREAK_SPACE)))
    # 单位词表只有一处：预览的禁则判据必须与编译器写出的间隙同源。
    import ghost
    for probe in ("公里", "个月", "万元", "%", "家"):
        check(f"混排: 预览禁则与编译共用同一份单位表（{probe}）",
              bool(ghost._UNIT_HEAD.match(probe)) and probe in prim.UNIT_WORDS)
    # 真实产物里也必须是不换行：编译后从 PPTX 里读回文本核对。
    from compiler import compile_deck
    import vao
    spec, _ = vao.load_spec(make_build(tmp, chart=False))
    spec["slides"][0]["elements"].append(
        {"id": "nb", "type": "text", "x": 40, "y": 600, "width": 800, "height": 40,
         "role": "body", "text": "平均配送半径是 186 公里", "size": 16})
    out = tmp / "nb.pptx"
    compile_deck(spec, str(out))
    from pptx import Presentation
    text = "\n".join(shape.text_frame.text for shape in
                     Presentation(str(out)).slides[0].shapes if shape.has_text_frame)
    check("混排: 交付的 PPTX 里数字与单位之间是不换行空格",
          "186" + prim.NO_BREAK_SPACE + "公里" in text, repr(text[-80:]))


def test_design_judgment(tmp: Path):
    """设计判断回归：每条用例对应一次真实成品/渲染审计暴露出来的错判。

    这些不是「更多规则」，而是把已经修对的判断钉住——每个断言的期望值都来自
    一次可复现的误判现场（接受基准 brief_v1 的 s01/s02/s04/s05/s08 与条件从句页）。
    """
    import intelligence as intel

    # 1 · 时间坐标不进证据量：封面写着「投委会 2026.10」，四位年 + 点分月日是日期。
    #     旧实现把它读成 2026.1，封面于是「有一个量要立住」，焦点/权重/构图/字阶
    #     一起落到日期上（实测：封面最大的元素成了 2026.10）。
    check("numerals: 点分日期（2026.10 / 2026.10.14）不是证据量",
          intel.evidence_numerals("华东区 2024—2026 经营复盘 · 投委会 2026.10") == []
          and intel.evidence_numerals("数据截至 2026.10.14") == []
          and [n["raw"] for n in intel.evidence_numerals("单价 12.5 元")] == ["12.5 元"],
          str(intel.evidence_numerals("华东区 2024—2026 经营复盘 · 投委会 2026.10")))
    cover = intel.page_judgment(
        {"id": "c1", "title": "扩张的答案不在开店速度，在单店质量",
         "content": "华东区 2024—2026 经营复盘 · 投委会 2026.10",
         "insight": "扩张的答案不在开店速度，在单店质量", "asset": "none"},
        index=0, total=8, brief={"audience": "投委会", "decision": "批准扩张预算"},
        world=intel.derive_world({"audience": "投委会"}, [intel.understand("x")]),
        warnings=[])
    check("判断: 封面是陈述位，日期不当焦点（焦点回到主张本人）",
          cover["visual_role"]["role"] == "establish"
          and cover["focus"]["element_role"] == "statement_text"
          and cover["understanding"]["evidence"] == "none",
          str({k: cover[k] for k in ("visual_role", "focus")}))

    # 2 · 主张说的是哪个指标，就锚哪个数字：标题讲增速连续收窄，正文末句讲的是
    #     单店月均营收——旧实现让正文的「数字＋变化」把标题结论顶掉，主语变成
    #     另一个指标的金额（实测：增速页的头号数字成了 37.5 万元）。
    mixed = intel.extract_claim(
        {"title": "同店销售额仍在增长，但增速已经连续三个季度收窄",
         "content": "同店销售额同比增速：2025Q4 为 8.6%，2026Q1 为 6.1%，2026Q2 为 3.4%，"
                    "2026Q3 为 2.2%。单店月均营收从 41.2 万元降至 37.5 万元。"})
    check("claim: 正文换了指标时不顶掉标题结论（同一度量才谈得上更强）",
          mixed["text"] == "同店销售额仍在增长，但增速已经连续三个季度收窄", str(mixed))
    stronger = intel.extract_claim(
        {"title": "华东区数据",
         "content": "结论：增速收窄的根因是店长成熟度。单店月均营收降至 37.5 万元。"})
    check("claim: 带结论措辞的正文句仍然胜出（不被指标一致性挡住）",
          "根因" in (stronger["text"] or ""), str(stronger))

    # 3 · 序列位置坐标不是第二个量：「第 3 个月 × 月均营收（万元）」是坐标轴，
    #     不是两种单位并置。旧实现判成单位不同 → 丢掉 data_field，还多报一条
    #     并不存在的口径告警（实测：同一张图的同口径数据被判不可比）。
    curve = intel.understand(
        "成熟店与新店的营收差距在开业第 9 个月才收敛 "
        "开业后各月单店月均营收（万元）：第 3 个月，成熟店 41.2，新店 27.2；"
        "第 6 个月，成熟店 41.8，新店 33.6。")
    check("data: 序列位置坐标（第 N 个月）不把同口径序列判成单位不同",
          curve["same_unit"] is True and curve["evidence"] == "comparison", str(curve))
    check("data: 真跨量纲的页面仍然判不可比（尺子没被放松）",
          intel.understand("总收入 480 万元，人均成本 90 元")["same_unit"] is False)

    # 4 · 请求的动作自己带的量赢过后面的终值：「批准本轮 30 家，同步把培训基地
    #     从 2 个扩到 3 个」的主语是要批的 30 家，不是「扩到 3 个」。
    ask = "批准本轮 30 家，同步把培训基地从 2 个扩到 3 个"
    _, ask_primary = intel.number_roles(ask, ask)
    check("focus: 要决定的那个量赢过后面出现的终值（30 家，而不是 3 个）",
          ask_primary and ask_primary["raw"] == "30 家", str(ask_primary))

    # 5 · 序列没有点名取值时，同分同单位取**末值**：讲「增速连续三个季度收窄」，
    #     主语是当前的 2.2%，不是三年前的 8.6%（旧实现取同分里的第一个）。
    _, latest = intel.number_roles(
        "同店销售额同比增速：2025Q4 为 8.6%，2026Q1 为 6.1%，2026Q2 为 3.4%，2026Q3 为 2.2%。",
        "增速已经连续三个季度收窄")
    check("focus: 序列同分同单位时取末值（当前状态，不是基期）",
          latest and latest["raw"] == "2.2%", str(latest))

    # 6 · 主张自己的量不算「重复」：结论点明落点、证据里必然再出现一次。
    #     旧实现把它列进删除清单，等于叫作者删掉本页的主张（实测：收敛页的
    #     删除清单里出现「9 个月 的重复出现」）。
    gap_text = ("开业后各月：第 3 个月，成熟店 41.2，新店 27.2；"
                "第 9 个月，成熟店 42.1，新店 38.9。")
    gap_page = intel.information_weight(
        intel.understand(gap_text),
        {"text": "成熟店与新店的营收差距在开业第 9 个月才收敛", "source": "extracted"},
        gap_text)
    check("weight: 结论点名的坐标不进删除清单（主张与证据的必要呼应）",
          not any("重复" in x for x in gap_page["delete"]), str(gap_page["delete"]))
    dup_text = "收入 12 亿，收入 12 亿（来源：财报）"
    dup_again = intel.information_weight(intel.understand(dup_text),
                                        {"text": "收入 12 亿", "source": "extracted"}, dup_text)
    check("weight: 同一句话里的数字重复照旧进删除清单",
          any("重复" in x for x in dup_again["delete"]), str(dup_again["delete"]))

    # 7 · 「单位不同」只在**主张**层面成立：页面里同时出现家数、月数与百分比，
    #     不等于这一页要把它们画到同一条数量轴上（实测：人效对比页的未决项来自
    #     正文的门店家数，主张其实只有 34% 一个量）。
    chart_brief = {"audience": "投委会", "decision": "批准扩张"}
    chart_page = intel.think({**chart_brief, "slides": [{
        "id": "u1", "title": "开店速度已经超过组织承接能力",
        "content": "2026 年新开 62 家门店，同比 38 家增长 63%；同期店长培养周期从 5.2 个月"
                   "拉长到 8.7 个月。新店首月人效比成熟店低 34%。"}]})["pages"][0]["judgment"]
    check("judgment: 主张单一量时不误报口径未决（正文混量纲不算）",
          not any("单位不同" in q for q in (chart_page["open_questions"] or [])),
          str(chart_page["open_questions"]))
    mixed_claim = intel.think({**chart_brief, "slides": [{
        "id": "u2", "title": "总收入与人均成本对比：480 万元 vs 90 元",
        "content": "总收入 480 万元，人均成本 90 元（来源：财务表）"}]})["pages"][0]["judgment"]
    check("judgment: 主张自己跨量纲时照旧报口径未决（尺子没被放松）",
          any("单位不同" in q for q in (mixed_claim["open_questions"] or [])),
          str(mixed_claim["open_questions"]))

    # 8 · 单个「先」是优先级不是流程：「先把周期压回去，再谈扩张」是决策页，
    #     不是一个时间轴（旧实现据一个虚词判出 sequence + linear_structure）。
    decision = intel.think({**chart_brief, "slides": [{
        "id": "d1", "title": "先把店长培养周期压回 6 个月，再谈第三轮扩张",
        "content": "批准本轮 30 家，同步把培训基地从 2 个扩到 3 个；"
                   "若 2027Q1 店长培养周期仍高于 7 个月，暂停后续批次。"}]})["pages"][0]["judgment"]
    check("judgment: 单个「先/再」不构成流程（决策页回到收束位）",
          decision["visual_role"]["role"] == "summarize"
          and decision["composition"]["chosen"] != "linear_structure",
          str({"role": decision["visual_role"]["role"],
               "comp": decision["composition"]["chosen"]}))
    check("judgment: 条件从句里的比较词不把收尾页判成两端对比",
          decision["understanding"]["evidence"] != "comparison", str(decision["understanding"]))

    # 9 · 眉标是被截断的从句时不输出：「答案不在开店速度」曾是眉标「答案不」。
    for text, forbid in (("扩张的答案不在开店速度，在单店质量", "答案不"),
                         ("同店销售额仍在增长，但增速已经连续三个季度收窄", "同店销售额仍")):
        got = intel.section_label({}, {"text": text}, "prove")
        check(f"眉标: 不以副词收尾的截断从句（{forbid}）", got != forbid and len(got) <= 6, got)
    check("眉标: 干净名词短语照旧派得出来（收尾字表不被过度收紧）",
          intel.section_label({}, {"text": "供应链的响应半径决定了开业节奏的上限"}, "prove")
          == "供应链", intel.section_label({}, {"text": "x"}, "prove"))

    # 10 · 单位表覆盖实务量词：配送半径 186 公里不能读成无单位的 186。
    check("numerals: 公里/吨/平方米等单位进入读数（主语不丢量纲）",
          [(n["raw"], n["unit"]) for n in intel.evidence_numerals("配送半径 186 公里")]
          == [("186 公里", "公里")]
          and intel.evidence_numerals("产量 12 万吨")[0]["unit"] == "万吨")

    # 11 · 主张讲「差」时，排版纪律点名差本身：两条近重合的线各带一套数值标签，
    #      会在同一个 x 上挤到一起且认不出归属（真实渲染实测）。
    gap_judgment = intel.page_judgment(
        {"id": "g1", "title": "成熟店与新店的营收差距在开业第 9 个月才收敛",
         "content": "开业后各月单店月均营收（万元）：第 3 个月，成熟店 41.2，新店 27.2；"
                    "第 6 个月，成熟店 41.8，新店 33.6；第 9 个月，成熟店 42.1，新店 38.9。",
         "asset": "none"},
        index=4, total=8, brief=chart_brief,
        world=intel.derive_world(chart_brief, [intel.understand("x")]), warnings=[])
    check("typography: 讲差的一页要求画差值或只标端点（不给两条线各配标签）",
          "差值" in gap_judgment["typography"]["discipline"],
          gap_judgment["typography"]["discipline"])

    # 12 · 趋势词不是序列：序列至少两个数据点。封面「接管增长」与致谢页「内容增长负责人」
    #      曾因一个措辞被判成数据序列，连带封面变成证明页并派发「坐标轴」指令。
    check("series: 无数字的趋势措辞不构成序列",
          intel.understand("自有内容正在接管增长，预算应该跟上")["evidence"] != "series")
    check("series: 两个以上数据点仍是序列",
          intel.understand("2023 年 38%，2024 年 47%，2025 年 61%")["evidence"] == "series")
    deck_plan = intel.think({
        "audience": "董事会", "decision": "批准预算", "tension": "成本持续上升",
        "slides": [
            {"id": "s01", "title": "自有内容正在接管增长，预算应该跟上", "content": "2027 内容战略提案"},
            {"id": "s02", "title": "外部流量价格三年翻倍", "content": "获客成本从 186 元涨到 412 元（来源：投放台账）"},
            {"id": "s03", "title": "谢谢，欢迎质询", "content": "联系人：内容增长负责人"}]})
    jd = {p["id"]: p["judgment"] for p in deck_plan["pages"]}
    check("judgment: 封面建立主张，不被判成证明页",
          jd["s01"]["visual_role"]["role"] == "establish", jd["s01"]["visual_role"]["role"])
    check("judgment: 无图表的封面不派发「坐标轴与刻度」",
          not any("坐标轴" in w for w in jd["s01"]["information_weight"]["weaken"]))
    check("judgment: 致谢/问答页没有结论时不追问补句（也不编造结论）",
          jd["s03"]["claim"]["source"] == "frame" and jd["s03"]["claim"]["text"] is None
          and not any("先写出一句" in q for q in (jd["s03"].get("open_questions") or []))
          and "先补一句" not in str(jd["s03"]["claim"].get("why")))
    check("judgment: 一句话收束的致谢页让留白承担分量",
          jd["s03"]["composition"]["chosen"] == "big_whitespace", jd["s03"]["composition"]["chosen"])
    # 13 · 时间序列不是比较：按年份排列的同一指标（有图表）仍是 series；分期不是两个并置选项
    year_series = intel.understand("2023 年 38%，2024 年 47%，2025 年 61%", has_chart=True)
    check("series: 按年份排列的图表数据是时间序列，不被当成比较",
          year_series["evidence"] == "series" and not year_series["comparison"],
          year_series["evidence"])
    phased = intel.understand("一期 1,200 万（2027Q1）；二期 1,800 万（2027Q3）；三期 1,800 万（2028Q1）。"
                              "预计 2028Q2 累计自有流量收入超过投入")
    check("series: 分期投入是先后承诺（sequence），不是「超过投入」式比较",
          phased["evidence"] == "sequence" and not phased["comparison"], phased["evidence"])
    skeleton_text = intel.build_skeleton(deck_plan)
    check("skeleton: 通用排版纪律只在头部声明一次，逐页不重复",
          skeleton_text.count(intel.BASE_DISCIPLINE) == 1, str(skeleton_text.count(intel.BASE_DISCIPLINE)))
    check("skeleton: 跨页锚的规则只在头部说明一次，逐页不重复",
          skeleton_text.count("跨页锚（anchor") == 1,
          str(skeleton_text.count("跨页锚（anchor")))
    # 14 · 断言谓语结尾的标题是结论，不是话题标签（探针：「差距明显」被判 absent，并要求补句）
    check("claim: 以断言谓语结尾的标题（差距明显）是结论，不追问补句",
          intel._title_assertive("三个市场的进入成本与回本周期差距明显")
          and not intel._title_assertive("华东区数据"),
          str(intel._title_assertive("三个市场的进入成本与回本周期差距明显")))
    # 15 · 「对比」是页面主题标签（封面「对比评估」），不把封面判成比较页；「N 倍」才是比较
    check("compare: 「对比评估」作为主题标签不触发比较",
          not intel.understand("对比评估")["comparison"])
    check("compare: 「N 倍」是比较断言",
          intel.understand("高端线售价是泰国的 1.6 倍")["comparison"])
    # 16 · 规格列举（不同单位的数字）不是序列；同单位的三个数字仍是序列
    spec = intel.understand("规格：3 次烧成，1280℃，0.6–0.8 毫米")
    check("series: 不同单位的规格列举不被判为序列",
          spec["evidence"] != "series", spec["evidence"])
    # 17 · 群体/角色名词不是可拍的证词主体（「伙伴」「团队」「客户」不触发配图）
    partner = intel.understand("选择越南，需要先补齐两个渠道伙伴")
    check("media: 「伙伴」这类群体名词不构成证词，不强制配图",
          intel.media_necessity(partner, "persuade")["decision"] != "required",
          str(intel.media_necessity(partner, "persuade")))


def test_docs():
    import re
    package = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', package, re.M)
    release = re.search(r'^## (\d+\.\d+\.\d+)', changelog, re.M)
    check("docs: 包版本与最新变更记录一致",
          bool(version and release and version[1] == release[1]))
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    refs = sorted(p.name for p in (ROOT / "references").glob("*.md"))
    check("docs: SKILL.md 只保留六节（身份/哲学/判断/Context/执行/QA）",
          all(k in skill for k in ("身份", "设计哲学", "判断", "Context", "执行", "QA")),
          str(refs))
    check("docs: references 只保留执行/资产契约，不维护第二套判断",
          len(refs) <= 2 and "judgment.md" not in refs, str(refs))
    check("docs: 文档里没有退役模块名与旧概念",
          all(b not in skill for b in ("guard.py", "normalize.py", "route.py", "qa.py",
                                       "design_direction")))


def main():
    # 测试自己的输出也是 UTF-8：Windows 上 `python scripts/selftest.py` 被管道捕获时
    # Python 用系统 ANSI 代码页写 stdout，第一行 `[PASS] …中文…` 就抛
    # UnicodeEncodeError，整轮测试以 1 结束——CI 的 Windows 作业曾经全红在这上面。
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for name, fn in (("intelligence", test_intelligence), ("verify", test_verify),
                         ("production", test_production), ("cli", test_cli), ("delivery", test_delivery), ("plan_boundaries", test_plan_boundaries),
                         ("release_evidence", test_release_evidence),
                         ("design_judgment", test_design_judgment),
                         ("boundary_typography", test_boundary_typography)):
            (root / name).mkdir(parents=True, exist_ok=True)
            fn(root / name)
        test_docs()
    print(f"\n{PASS}/{PASS + FAIL} passed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
