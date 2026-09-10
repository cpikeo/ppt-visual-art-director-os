#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阈值校准闭环工具 —— references/benchmark-calibration.md 的可执行形态。

只测量、只建议、只记录；**不修改任何阈值常量**——改动由人复核后手工落进
art_critic.py / qa.py，并保留校准记录（改了什么、相关性从 X 到 Y）。

用法：
  # 1) 生成标注模板（slide id + 空分 + 锚定说明），人工只填 score 与 why
  python3 scripts/calibrate.py --init path/to/build_module.py --labels labels.json

  # 2) 标注完成后跑校准分析（复用 <pptx>_render/ 渲染证据目录，缓存命中即免渲染）
  python3 scripts/calibrate.py --labels labels.json --build path/to/build_module.py \\
         --pptx path/to/output.pptx [--report calibration_report]

labels.json：
  {"labeled_by": "姓名", "date": "YYYY-MM-DD",
   "pages": [{"slide": "s01", "score": 4.5, "why": "一句话理由"}, ...]}

score 锚定（0–5 整体审美分，只问「这一页好不好」）：
  5 = 直接可给董事会/客户，不改；3 = 可用但要改两处以上；1 = 重做比改快；
  2、4 = 过渡。不要按「守了多少条规则」打分——那是在给旧阈值背书。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# 当前默认阈值（与 benchmark-calibration.md 的表一致；仅用于报告对照，不改代码）
CURRENT_DEFAULTS = {
    "gravity_drift": 0.28,        # qa.py thresholds
    "accent_pixel_ratio": 0.08,   # qa.py thresholds
    "edge_kurtosis_avg": 4.0,     # art_critic.py（对齐加分线）
    "ANCHOR_DRIFT": 0.18,         # art_critic.py（无法逐页从证据取得，仅对照展示）
}
# 每个可逐页测量的特征的方向：lower_better = 值越小越好页越可能「好」
SWEEPABLE = {
    "gravity_drift": "lower_better",
    "accent_pixel_ratio": "lower_better",
    "edge_kurtosis_avg": "higher_better",
}
MIN_PAGES = 6          # 样本守门：低于此数不给出任何校准建议
MIN_BUCKET = 2         # 好(≥4)/差(≤2) 两桶各至少 N 页


# ──────────────────────────────────────────────────────────────────────────
# 数学
# ──────────────────────────────────────────────────────────────────────────
def pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson 相关；样本 <2 或零方差返回 0.0（无法判断 = 不假装有判断）。"""
    n = len(xs)
    if n < 2 or n != len(ys):
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 1e-12 or syy <= 1e-12:
        return 0.0
    return sxy / (sxx ** 0.5 * syy ** 0.5)


# ──────────────────────────────────────────────────────────────────────────
# 证据采集
# ──────────────────────────────────────────────────────────────────────────
def _load_build(path: pathlib.Path) -> dict:
    import importlib.util
    spec_mod = importlib.util.spec_from_file_location("calib_build", str(path))
    mod = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    if not isinstance(spec, dict) or not spec.get("slides"):
        raise SystemExit(f"build module 未定义可用的 build_spec()/SPEC: {path}")
    return spec


def page_composites(critic_report: dict) -> dict[str, float]:
    """critic 每页 9 维加权分（0–100）→ 0–5，与人工整体分同尺度对照。"""
    from art_critic import DIMENSIONS, WEIGHTS
    out: dict[str, float] = {}
    for s in critic_report.get("slides") or []:
        scores = s.get("scores") or {}
        if not scores:
            continue
        weighted = sum(scores.get(d, 0) / 5 * WEIGHTS[d] for d in DIMENSIONS)
        out[str(s.get("slide"))] = round(weighted / 20.0, 3)
    return out


def collect_features(evidence: dict) -> dict[str, dict[str, float]]:
    """从渲染证据逐页抽取可校准特征（只取证据里真实存在的键）。"""
    out: dict[str, dict[str, float]] = {}
    for p in evidence.get("pages") or []:
        sid = str(p.get("slide"))
        feats: dict[str, float] = {}
        if p.get("gravity_drift") is not None:
            feats["gravity_drift"] = float(p["gravity_drift"])
        if p.get("accent_pixel_ratio") is not None:
            feats["accent_pixel_ratio"] = float(p["accent_pixel_ratio"])
        kx = float(p.get("edge_kurtosis_x") or 0)
        ky = float(p.get("edge_kurtosis_y") or 0)
        if kx or ky:
            feats["edge_kurtosis_avg"] = round((kx + ky) / 2, 3)
        if feats:
            out[sid] = feats
    return out


# ──────────────────────────────────────────────────────────────────────────
# 校准分析（纯函数，可独立测试）
# ──────────────────────────────────────────────────────────────────────────
def analyze(labels: dict, page_scores: dict[str, float],
            features: dict[str, dict[str, float]] | None = None) -> dict:
    """labels + critic 页分 (+ 逐页特征) → 相关性 / 错杀漏放 / 阈值反推建议。

    守门：样本 < MIN_PAGES 或 好/差桶任一 < MIN_BUCKET 时拒绝给建议——
    样本不足时任何「校准值」都是噪声拟合。
    """
    pages = [p for p in (labels.get("pages") or [])
             if isinstance(p, dict) and p.get("score") is not None]
    pairs = [(str(p["slide"]), float(p["score"])) for p in pages
             if str(p.get("slide")) in page_scores]
    matched = len(pairs)
    good = [(s, h) for s, h in pairs if h >= 4.0]
    bad = [(s, h) for s, h in pairs if h <= 2.0]
    result: dict = {
        "ok": False, "n_labeled": len(pages), "n_matched": matched,
        "n_good": len(good), "n_bad": len(bad),
    }
    if matched < MIN_PAGES or len(good) < MIN_BUCKET or len(bad) < MIN_BUCKET:
        result["reason"] = (
            f"样本不足（匹配 {matched} 页，好 {len(good)} / 差 {len(bad)}；"
            f"需 ≥{MIN_PAGES} 页且好/差各 ≥{MIN_BUCKET}）。先补标注，"
            f"再谈校准——样本不足时的任何『校准值』都是噪声拟合。")
        return result

    xs = [page_scores[s] for s, _ in pairs]
    ys = [h for _, h in pairs]
    r = pearson(xs, ys)
    # 错杀：人工 ≥4 但 critic 页分 <3（页级 CRITIC_LOW 线，会被判 REVISE）
    kills = [s for s, h in good if page_scores[s] < 3.0]
    # 漏放：人工 ≤2 但 critic 页分 ≥4（critic 认为很好）
    leaks = [s for s, h in bad if page_scores[s] >= 4.0]
    result.update({
        "ok": True,
        "pearson": round(r, 4),
        "pearson_target": 0.75,
        "kill_rate": round(len(kills) / max(1, len(good)), 4),
        "kill_slides": kills,
        "leak_rate": round(len(leaks) / max(1, len(bad)), 4),
        "leak_slides": leaks,
    })

    # 阈值反推：每个可测特征，在候选值上找把 好/差 分得最开的临界点
    sweeps = []
    feats = features or {}
    for name, direction in SWEEPABLE.items():
        vals_good, vals_bad = [], []
        for s, _ in good:
            v = (feats.get(s) or {}).get(name)
            if v is not None:
                vals_good.append(v)
        for s, _ in bad:
            v = (feats.get(s) or {}).get(name)
            if v is not None:
                vals_bad.append(v)
        if len(vals_good) < MIN_BUCKET or len(vals_bad) < MIN_BUCKET:
            continue
        lo = min(min(vals_good), min(vals_bad))
        hi = max(max(vals_good), max(vals_bad))
        if hi - lo < 1e-9:
            continue
        step = (hi - lo) / 11.0
        candidates = [lo + step * i for i in range(12)]
        best = None
        for t in candidates:
            if direction == "lower_better":
                acc_g = sum(1 for v in vals_good if v <= t) / len(vals_good)
                acc_b = sum(1 for v in vals_bad if v > t) / len(vals_bad)
            else:
                acc_g = sum(1 for v in vals_good if v >= t) / len(vals_good)
                acc_b = sum(1 for v in vals_bad if v < t) / len(vals_bad)
            acc = (acc_g + acc_b) / 2.0
            if best is None or acc > best[1]:
                best = (t, acc)
        sweeps.append({
            "feature": name,
            "current_default": CURRENT_DEFAULTS.get(name),
            "suggested": round(best[0], 4),
            "separation_accuracy": round(best[1], 4),
            "n_good": len(vals_good), "n_bad": len(vals_bad),
        })
    result["sweeps"] = sweeps
    result["notes"] = [
        "建议值只是『当前样本上的最佳分界』，不是真理；每次只动 1–3 个阈值并记录相关性变化。",
        "可读性/诚实性底线（对比度 3.0/4.5、行长、负值禁令）不参与校准——底线只升不降。",
        f"STATEMENT_SIZE / FOCUS_LEAD / LR_SPLIT_MAX / accent 色距需从 spec 静态特征逐页提取，"
        f"证据目录齐全后由 sweep 扩展承接（当前 {len(sweeps)} 项可测）。",
    ]
    return result


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────
def _markdown(result: dict, labels_path: pathlib.Path) -> str:
    if not result.get("ok"):
        return (f"# 校准分析（未执行）\n\n{result.get('reason', '')}\n"
                f"标注文件：{labels_path}\n")
    lines = [
        "# 阈值校准分析", "",
        f"- 标注样本：{result['n_matched']} 页（好 {result['n_good']} / 差 {result['n_bad']}）",
        f"- **Pearson(critic, 人工) = {result['pearson']}**（目标 ≥ {result['pearson_target']}）",
        f"- 错杀率 {result['kill_rate']:.1%}（人工≥4 被 critic 判 REVISE：{result['kill_slides'] or '无'}）",
        f"- 漏放率 {result['leak_rate']:.1%}（人工≤2 但 critic 页分≥4：{result['leak_slides'] or '无'}）",
        "",
        "## 阈值反推（当前样本最佳分界，仅供复核）", "",
        "| 特征 | 当前默认 | 建议值 | 好差分界准确率 | n(好/差) |",
        "|---|---|---|---|---|",
    ]
    for s in result.get("sweeps") or []:
        lines.append(f"| {s['feature']} | {s['current_default']} | {s['suggested']} | "
                     f"{s['separation_accuracy']:.1%} | {s['n_good']}/{s['n_bad']} |")
    lines += ["", "## 改动记录（人工填写）", "",
              "- 改了什么：", "- 相关性从 __ 到 __：", "- 复核人 / 日期：", ""]
    for n in result.get("notes") or []:
        lines.append(f"> {n}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="阈值校准闭环工具（只测量，不改动）")
    ap.add_argument("--init", metavar="BUILD",
                    help="从 build module 生成标注模板")
    ap.add_argument("--labels", required=True, help="labels.json 路径")
    ap.add_argument("--build", help="build module（分析时必填）")
    ap.add_argument("--pptx", help="已编译 PPTX（定位渲染证据目录）")
    ap.add_argument("--report", help="人读 Markdown 报告输出路径")
    args = ap.parse_args(argv)
    labels_path = pathlib.Path(args.labels)

    if args.init:
        spec = _load_build(pathlib.Path(args.init))
        template = {
            "labeled_by": "", "date": "",
            "pages": [{"slide": s.get("id"), "score": None, "why": ""}
                      for s in spec.get("slides") or []],
            "_anchoring": "5=直接可交付；3=可用但要改两处以上；1=重做比改快。只打整体分，不按规则打分。",
        }
        labels_path.parent.mkdir(parents=True, exist_ok=True)
        labels_path.write_text(json.dumps(template, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        print(f"标注模板已生成：{labels_path}（{len(template['pages'])} 页，填 score 与 why）")
        return 0

    if not args.build:
        print("分析需要 --build <build_module.py>（生成模板用 --init）")
        return 2
    spec = _load_build(pathlib.Path(args.build))
    labels = json.loads(labels_path.read_text(encoding="utf-8"))

    evidence = {"rendered": False, "pages": []}
    if args.pptx:
        from render_check import render_evidence
        pptx = pathlib.Path(args.pptx)
        out_dir = pptx.parent / (pptx.stem + "_render")
        evidence = render_evidence(pptx, spec, out_dir, use_cache=True)
    from art_critic import critique_deck
    critic = critique_deck(spec, render_evidence=evidence if evidence.get("rendered") else None)
    result = analyze(labels, page_composites(critic), collect_features(evidence))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.report:
        rp = pathlib.Path(args.report)
        rp.write_text(_markdown(result, labels_path), encoding="utf-8")
        print(f"报告已写入：{rp}")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
