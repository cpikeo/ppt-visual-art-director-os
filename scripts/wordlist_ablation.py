#!/usr/bin/env python3
"""13 组「消融后指标不变」词表的定性：先证据，再谈删表。

方法（可复现、可审计）：
  1. 对每组词表准备 3–5 个**针对性反例**（不是随机句子：每个探测句都按该词表
     被使用的那条判断路径构造，见 PROBES 里每条的 note）；
  2. 同一批探测句在「保留词表」与「把该词表清空」两种状态下各跑一遍
     `intelligence.page_judgment`，比对**判断签名**（角色/证据/比较/构成/焦点/
     媒体决策/媒体功能/主张来源/主张文本）；
  3. 分类：
       DISCRIMINATING —— 至少一个探测句的判断发生改变：这条词表在真实输入上有
                         判别力，只是 57 例基准没测到 ⇒ 应补冻结案例（r7）。
       INERT          —— 所有探测句判断都不变：词表对行为没有可观测影响 ⇒ 删除候选，
                         但删之前必须在全部冻结集 + selftest 上验证并留档。
       UNREACHABLE    —— 探测句触发不了该路径（例如物理实体判定需要 deck 级统计），
                         标记为「未定性」，不得当成「无判别力」。

用法：python eval/wordlist_ablation.py [--json out.json]
退出码：始终 0（这是取证工具，不是门禁）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import intelligence as intel  # noqa: E402

BRIEF = {"audience": "内部评审会", "decision": "批准下一步预算"}
SIGNATURE_KEYS = ("role", "evidence", "comparison", "part_whole", "focus",
                  "composition", "media_decision", "media_function",
                  "grammar", "world_source", "must_place",
                  "claim_source", "claim_text")

# 每组：探测句（title, content）＋ 为什么这句能打中这条路径
PROBES: dict[str, list[dict]] = {
    "_HUMAN_WORDS": [
        # human 经 human_share 影响世界级 grammar：两页 deck 里一页有人、一页是
        # 纯数字页 → human_share=0.5；把人词表删掉则 human_share=0 而
        # number_share=0.5（既不 <0.3 也不 >0.6）→ strict_grid。单页探测永远
        # 观测不到这条（单页时 number_share<0.3 本来就给 soft_asymmetry）。
        {"title": "术后随访", "content": "12 位患者在术后 30 天完成回访，护士上门 8 次。",
         "deck": [("季度营收", "Q1 1200 万元，Q2 1350 万元。")],
         "note": "有人 + 纯数字页：human_share 决定 grammar"},
        {"title": "教师培训", "content": "老师 1800 人参加培训，学生覆盖 4.2 万人。",
         "deck": [("季度营收", "Q1 1200 万元，Q2 1350 万元。")],
         "note": "同上（另一组人物词）"},
    ],
    "_SCENE_WORDS": [
        {"title": "门店发生了什么", "content": "走访 6 家门店，记录了早高峰的动线。",
         "note": "场所词 + 证词词：scene=True 会推进媒体必要性"},
        {"title": "课堂观察", "content": "课堂 45 分钟，学生发言 11 次。",
         "note": "只有场所词、无证词词：有数字时 scene 应为 False（计数对象）"},
        {"title": "车间班次", "content": "车间 3 个班次，产量 1200 件。",
         "note": "场所词 + 数字：不得因为「车间」就派图"},
    ],
    "_WITNESS_WORDS": [
        {"title": "现场记录", "content": "走访 6 家门店，拍摄了 40 条现场记录。",
         "note": "证词词是 scene 的第二道门"},
        {"title": "回访结果", "content": "回访 120 家客户，满意度 86 分。",
         "note": "回访 + 数字：证词成立时 scene 仍为真"},
    ],
    "_TOPIC_TAILS": [
        {"title": "华东区数据记录", "content": "华东 6 省营收 12 亿元，同比 +18%。",
         "note": "「记录」收尾 = 话题标签，主张应回正文（结论位不被标题占）"},
        {"title": "改造流程说明", "content": "一期改造 3 个仓，单均成本下降 0.42 元。",
         "note": "「说明」收尾 = 标签"},
        {"title": "华东区数据", "content": "华东 6 省营收 12 亿元，同比 +18%。",
         "note": "负例：不是标签尾，标题可竞争结论位"},
    ],
    "_CONCLUSION_WORDS": [
        {"title": "增长已经失效", "content": "因此必须把预算从买量转向内容资产。",
         "note": "「因此/必须」是结论措辞，正文句应夺结论位"},
        {"title": "补贴结构", "content": "所以唯一可行的做法是把签约金改成留存工具。",
         "note": "「所以/唯一」结论措辞"},
    ],
    "_ASK_WORDS": [
        {"title": "预算事项", "content": "请批准 2026 年 3.2 亿元改造预算，分三期执行。",
         "note": "请求措辞 → focus=decision_ask，收束页焦点"},
        {"title": "请确认排期", "content": "请确认 4 月启动，二期 9 月进场。",
         "note": "请求 + 时间，无金额"},
    ],
    "_COMPARISON_WORDS": [
        {"title": "两端对照", "content": "我方复购率 34%，相比同业 26% 高出 8 个百分点。",
         "note": "「相比」是显式比较谓语"},
        {"title": "与对手的差距", "content": "清关时效在越南与印尼不同：1.8 天 / 6.4 天。",
         "note": "「与…不同」句形（这句同时被 _TWO_END_DIFF 覆盖，用于对照）"},
    ],

    "_SEQUENCE_WORDS": [
        # 弱标记（先/然后/接着）没有强流程名词、也没有数字时，形状只由词表提供。
        {"title": "区域推进次序", "content": "先做华东，然后做华南，接着做华北。",
         "note": "三个弱顺序词、无流程名词、无数字：sequence 只能来自词表"},
        {"title": "第一步立项，第二步试点，第三步推广", "content": "",
         "note": "对照：强流程词（步骤）也在 _SEQUENCE_STRONG 里，词表被它遮蔽"},
    ],
    "_STRUCTURE_WORDS": [
        {"title": "组织架构", "content": "公司分三层：总部、大区、门店。",
         "note": "结构词 → structure"},
        {"title": "体系与模块", "content": "这套体系包含四个模块，各自独立结算。",
         "note": "结构词 + 分类动作"},
    ],
    "_CHANGE_WORDS": [
        # 变化词在 `_is_data_listing` 里是「这一句不是数据列举」的判据：同一单位
        # 的两个数字 + 变化词 → 可当结论；去掉它，同单位双数字退回列举 → 结论
        # 判 absent（页面上会变成「没有结论」）。
        {"title": "", "content": "营收 1200 万元，同比增至 1350 万元。",
         "note": "同单位双数字 + 变化词：不是列举，可作结论"},
        {"title": "", "content": "门店 980 家，增加 1200 家。",
         "note": "同一判据的第二种措辞"},
    ],
    "_TOPIC_MARKERS": [
        {"title": "为什么门店改造能回本", "content": "改造后单店月均营收从 37.5 万元升至 45.2 万元。",
         "note": "「为什么」是疑问标记：主张应视为话题而非结论"},
        {"title": "如何把周期压到 24 周", "content": "交付周期从 32 周缩短到 24 周。",
         "note": "「如何」疑问标记"},
    ],
    "_PHYSICAL_SUBJECTS": [
        # 物理实体只对**建立页**（index 0）给素材提示：元媒体判定在 establish 分支里
        # 才读 physical（prove 分支要的是人物/场所词）。
        {"title": "刻蚀设备：国产替代进入规模交付期", "content": "", "index": 0,
         "note": "封面建立页 + metal_glass：physical 分支给 subject 提示"},
        {"title": "茶园与土壤：有机质三年提升", "content": "", "index": 0,
         "note": "封面建立页 + botanical"},
        {"title": "港口与航运：班次密度决定成本", "content": "", "index": 0,
         "note": "封面建立页 + water_sky"},
    ],
}


def _signature(item: dict) -> dict:
    # deck 缺省只有本页；_HUMAN_WORDS 这类经 human_share/number_share 影响
    # 世界级 grammar 的词表，必须给一个**两页以上**的 deck 才可能观测到差异。
    pages = [f"{item['title']} {item['content']}"] + [
        f"{t} {c}" for t, c in (item.get("_deck") or [])]
    world = intel.derive_world(BRIEF, [intel.understand(x) for x in pages])
    j = intel.page_judgment(item, index=int(item.get("_index", 1)), total=3,
                            brief=BRIEF, world=world, warnings=[])
    media = j.get("media") or {}
    return {"role": j["visual_role"]["role"],
            "composition": j["composition"]["chosen"],
            "grammar": world.get("composition_grammar"),
            "world_source": world.get("source"),
            "must_place": "|".join(f"{m['role']}:{m['type']}"
                                   for m in (j.get("production") or {}).get("must_place") or []),
            "evidence": j["understanding"].get("evidence"),
            "comparison": bool(j["understanding"].get("comparison")),
            "part_whole": bool(j["understanding"].get("part_whole")),
            "focus": j["focus"].get("element_role"),
            "media_decision": media.get("decision"),
            "media_function": media.get("function") or media.get("suggested"),
            "claim_source": j["claim"].get("source"),
            "claim_text": j["claim"].get("text")}


def _judge_for(probes: list[dict]) -> list[dict]:
    out = []
    for i, p in enumerate(probes):
        item = {"id": f"p{i}", "title": p["title"], "content": p["content"],
                "_index": p.get("index", 1), "_deck": p.get("deck")}
        item.update(p.get("extra") or {})
        out.append(_signature(item))
    return out


# 已删除的词表（连同删除依据）：探针仍保留，用于证明「删掉之后行为不变」。
DELETED = {
    "_SERIES_WORDS": {
        "verdict": "DELETED",
        "why": "序列的判据已经是形状（同量纲时间轴，或一条同量纲读数）。词表入口的两个分支"
               "都被它们覆盖：同量纲时第一条成立；不同量纲时第二条要求读数，而读数本身已直接"
               "成立。删除后 selftest 816/816、bench 57/57、七组冻结 177 断言全过。",
        "probes": [
            {"title": "季度营收", "content": "Q1 1200 万元，Q2 1350 万元，Q3 1480 万元。"},
            {"title": "营收从 800 万元增至 1200 万元；毛利率 38%", "content": ""},
            {"title": "三项指标同比",
             "content": "营收同比 +18%，毛利率同比 +3 个百分点，客单价同比 +6%。"},
        ],
    },
}


def run() -> dict:
    results = {}
    for name, meta in DELETED.items():
        got = _judge_for([{"title": p["title"], "content": p["content"]} for p in meta["probes"]])
        results[name] = {"verdict": meta["verdict"], "why": meta["why"],
                         "probes": len(meta["probes"]), "after_deletion": got, "diffs": []}
    for name, probes in PROBES.items():
        original = getattr(intel, name, None)
        if original is None:
            results[name] = {"verdict": "MISSING", "probes": 0, "diffs": []}
            continue
        with_words = _judge_for(probes)
        setattr(intel, name, () if isinstance(original, tuple) else frozenset())
        try:
            without_words = _judge_for(probes)
        finally:
            setattr(intel, name, original)
        diffs = []
        for p, a, b in zip(probes, with_words, without_words):
            changed = {k: [a[k], b[k]] for k in SIGNATURE_KEYS if a[k] != b[k]}
            if changed:
                diffs.append({"title": p["title"], "changed": changed, "note": p["note"]})
        reachable = any(v is not None for v in
                        [w["media_decision"] for w in with_words] +
                        [w["claim_source"] for w in with_words])
        verdict = ("DISCRIMINATING" if diffs
                   else ("INERT" if reachable else "UNREACHABLE"))
        results[name] = {"verdict": verdict, "probes": len(probes), "diffs": diffs,
                         "words": len(original), "sample_words": list(original)[:6]}
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="把取证结果写成 JSON（默认不写文件）")
    args = ap.parse_args()
    res = run()
    order = {"DISCRIMINATING": 0, "DELETED": 1, "UNREACHABLE": 2, "INERT": 3, "MISSING": 4}
    rows = sorted(res.items(), key=lambda kv: (order[kv[1]["verdict"]], kv[0]))
    counts = {}
    for name, r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        print(f"[{r['verdict']:14s}] {name:22s} 词 {r.get('words', 0):3d} · 探测 {r['probes']} · 差异 {len(r['diffs'])}")
        for d in r["diffs"][:3]:
            for k, (a, b) in d["changed"].items():
                print(f"      · {d['title'][:22]:24s} {k}: {a!r} → {b!r}")
    print("\n汇总：", " / ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"取证: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
