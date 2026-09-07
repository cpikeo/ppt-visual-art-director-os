# -*- coding: utf-8 -*-
"""
Layer 4 · QA（质量评分层 · Design QA 100 分制）

职责：把「静态治理 + 编译诊断 + 渲染证据」组合为一份确定性回归报告——
满分 100，按规则扣分；passed 由调用方阈值决定。与旧包 health signal 同一立场：
**只验证规则合规与渲染完整性，不做审美评分**；分数用于 Release Gate 与迭代对比。

数据流（只读，不修改 spec）：
    spec ──→ guard.check_spec      静态治理（OS 硬约束）
         ──→ compile_deck          编译诊断（引擎 warnings）
         ──→ render_evidence      真实渲染证据（有环境时）

阈值全部由调用方传入（thresholds），缺省用保守默认值。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from primitives import DEFAULT_WIDTH, DEFAULT_HEIGHT
from guard import check_spec

# 扣分规则（确定性，非审美判断）：
# 每一项都是「OS 规则被违反」的量化，扣分可被调用方覆盖。
DEFAULT_PENALTIES = {
    "guard_error": 6.0,        # 越界等错误级静态问题（每项）
    "guard_warn": 2.5,         # 网格 / 重叠 / 容量 / Accent 超限（每项）
    "guard_hint": 0.1,         # 对齐 / 节奏提示（几乎不扣，仅留痕）
    "compile_warn": 1.5,       # 引擎编译诊断（每项，不含 [guard] 前缀）
    "render_gravity": 3.0,     # 渲染显著性质心与声明锚点漂移 > .28
    "render_accent": 3.0,      # 渲染强调色像素比 > .08（OS §06 Accent 克制）
    "render_occupancy": 3.0,   # 渲染占用率超过主题最小留白要求
    "render_margin": 2.0,      # 渲染边缘带不安静（内容贴近安全区边缘）
    "render_missing": 2.0,     # 无渲染环境（结构证据降级，轻微提示）
}
DEFAULT_THRESHOLDS = {
    "pass": 90.0,              # passed = score >= pass
    "gravity_drift": 0.28,     # 归一化漂移上限
    "accent_pixel": 0.08,      # 强调色像素比上限
    # 可选：主题 constraints.min_whitespace 或调用方 thresholds.min_whitespace
    # 指定最小留白比例；显式 thresholds 优先。
    # 可选：margin_occupancy 开启「边缘带安静度」检查（None=默认关闭，因为
    # 通栏图片背景会让边缘带合法地不安静，应只在纯色/结构背景主题开启）。
    "margin_occupancy": None,
}


def run_qa(spec: dict, output: str | Path, penalties: dict | None = None,
           thresholds: dict | None = None, guard_rules: dict | None = None,
           render_dir: str | Path | None = None, dpi: int = 96,
           render: bool = True) -> dict:
    """
    完整 QA：guard + compile + render（可选）。

    penalties / thresholds / guard_rules 由调用方传入，覆盖默认值（不写死参数）。
    render_dir 为 None 时使用 `<output>_render/` 稳定目录，保证渲染证据可被
    Release Manifest 的 render_evidence_path 记录与复核；无渲染环境自动降级。
    render=False 适合快速迭代布局，发布前必须恢复为 True。
    """
    import time
    from compiler import compile_deck

    pen = {**DEFAULT_PENALTIES, **(penalties or {})}
    thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    output_path = Path(output)
    t0 = time.time()

    # 1) 静态治理（guard_rules 独立传入，qa 不解读内部结构）
    guard = check_spec(spec, rules=guard_rules)

    # 2) 编译。Guard 已在本函数完成，关闭编译器内的重复静态扫描以减少一次全 deck 遍历。
    # 发布仍会在 compile_report 中保留 guard 摘要，口径由本函数唯一掌握。
    compile_report = compile_deck(spec, output_path, checks=False, guard_rules=guard_rules)
    compile_warnings = list(compile_report.get("warnings", []))

    # 3) 渲染证据（环境缺失时降级）
    render_dir = (Path(render_dir) if render_dir
                  else output_path.with_name(output_path.stem + "_render"))
    evidence = {"rendered": False, "reason": None, "pages": []}
    if render:
        try:
            from render_check import render_evidence
            evidence = render_evidence(output_path, spec, render_dir, dpi)
        except Exception as exc:
            evidence = {"rendered": False, "reason": f"render evidence failed: {exc}",
                        "pages": []}
    else:
        evidence = {"rendered": False, "reason": "render disabled for fast iteration",
                    "pages": []}

    # 4) 计分
    deduction = 0.0
    items: list[dict] = []
    deduction_by_domain = {"guard": 0.0, "compile": 0.0,
                           "render": 0.0, "config": 0.0}

    # hint 级条目按 rule 聚合（网格/节奏微调提示不逐条刷屏，数据仍在 guard.checks）
    hint_buckets: dict[str, dict] = {}
    for c in guard["checks"]:
        key = f"guard_{c['level']}"
        if key not in pen:
            continue
        deduction += pen[key]
        deduction_by_domain["guard"] += pen[key]
        if c["level"] == "hint":
            b = hint_buckets.setdefault(
                c["rule"], {"domain": "guard", "level": "hint", "rule": c["rule"],
                            "id": None, "count": 0, "penalty": pen[key],
                            "msg": f"{c['rule']} 微调提示（详见 guard.checks）"})
            b["count"] += 1
            continue
        items.append({"domain": "guard", "level": c["level"],
                      "rule": c["rule"], "id": c["id"], "msg": c["msg"],
                      "penalty": pen[key]})
    items.extend(hint_buckets.values())

    for w in compile_warnings:
        # 静态治理问题已在 guard 域计分，跳过 [guard] 前缀避免双重计分
        if w.startswith("[guard]"):
            continue
        deduction += pen["compile_warn"]
        deduction_by_domain["compile"] += pen["compile_warn"]
        items.append({"domain": "compile", "level": "warn",
                      "rule": "compiler", "id": None, "msg": w,
                      "penalty": pen["compile_warn"]})

    theme_constraints = dict((spec.get("theme") or {}).get("constraints") or {})
    min_whitespace = thr.get("min_whitespace", theme_constraints.get("min_whitespace"))
    if min_whitespace is not None:
        try:
            min_whitespace = float(min_whitespace)
            if not 0 <= min_whitespace <= 1:
                raise ValueError("min_whitespace must be between 0 and 1")
        except (TypeError, ValueError):
            items.append({"domain": "config", "level": "warn",
                          "rule": "min_whitespace", "id": None,
                          "msg": f"忽略无效的 min_whitespace={min_whitespace!r}（应为 0–1）",
                          "penalty": 0.0})
            min_whitespace = None

    margin_limit = thr.get("margin_occupancy")
    if margin_limit is not None:
        try:
            margin_limit = float(margin_limit)
        except (TypeError, ValueError):
            margin_limit = None
    for p in evidence.get("pages", []):
        # 边缘带安静度（默认关闭；纯色/结构背景主题可显式开启）
        if margin_limit is not None and "margin_occupancy" in p:
            if p.get("margin_occupancy", 0) > margin_limit:
                deduction += pen["render_margin"]
                deduction_by_domain["render"] += pen["render_margin"]
                items.append({"domain": "render", "level": "warn",
                              "rule": "margin_occupancy", "id": p.get("slide"),
                              "msg": (f"边缘带占用 {p['margin_occupancy']:.1%} > "
                                      f"{margin_limit:.0%}，内容可能贴近安全区边缘"),
                              "penalty": pen["render_margin"]})
        if min_whitespace is not None and "occupancy" in p:
            occupancy_limit = 1.0 - min_whitespace
            if p.get("occupancy", 0) > occupancy_limit:
                deduction += pen["render_occupancy"]
                deduction_by_domain["render"] += pen["render_occupancy"]
                items.append({"domain": "render", "level": "warn",
                              "rule": "min_whitespace", "id": p.get("slide"),
                              "msg": (f"页面占用率 {p['occupancy']:.1%} > "
                                      f"允许上限 {occupancy_limit:.1%}（最小留白 {min_whitespace:.1%}）"),
                              "penalty": pen["render_occupancy"]})
        if p.get("gravity_drift", 0) > thr["gravity_drift"]:
            deduction += pen["render_gravity"]
            deduction_by_domain["render"] += pen["render_gravity"]
            items.append({"domain": "render", "level": "warn",
                          "rule": "gravity_drift", "id": p.get("slide"),
                          "msg": (f"显著性质心偏离声明锚点 "
                                  f"{p['gravity_drift']:.2f} > {thr['gravity_drift']}"),
                          "penalty": pen["render_gravity"]})
        if p.get("accent_pixel_ratio", 0) > thr["accent_pixel"]:
            deduction += pen["render_accent"]
            deduction_by_domain["render"] += pen["render_accent"]
            items.append({"domain": "render", "level": "warn",
                          "rule": "accent_budget", "id": p.get("slide"),
                          "msg": (f"强调色像素 {p['accent_pixel_ratio']:.1%} > "
                                  f"{thr['accent_pixel']:.0%}（OS §06）"),
                          "penalty": pen["render_accent"]})

    if not evidence.get("rendered"):
        deduction += pen["render_missing"]
        deduction_by_domain["render"] += pen["render_missing"]
        items.append({"domain": "render", "level": "hint",
                      "rule": "render_missing", "id": None,
                      "msg": (f"无渲染环境（{evidence.get('reason')}），"
                              f"按结构证据降级"),
                      "penalty": pen["render_missing"]})

    score = max(0.0, 100.0 - deduction)
    failure_codes = []
    # 只有 error 级 Guard 检查才映射为阻断性失败码；warn/hint 只通过扣分影响
    # score，不改变发布状态（否则安全区余量提示等建议级检查会把整套 deck
    # 误判为 BLOCKED，违背「阻断错误 → BLOCKED」的状态优先级契约）。
    code_by_rule = {
        "overlap": "OVERLAP", "source_zone": "SOURCE_COLLISION",
        "chart_label_collision": "CHART_LABEL_COLLISION",
        "text_capacity": "TEXT_OVERFLOW", "contrast": "READABILITY_FAIL",
        "data_integrity": "DATA_INTEGRITY_FAIL", "safety": "GUARD_FAIL",
    }
    for check in guard["checks"]:
        if check.get("level") != "error":
            continue
        code = code_by_rule.get(check.get("rule"))
        if code and code not in failure_codes:
            failure_codes.append(code)
    if any(check.get("level") == "error" for check in guard["checks"]):
        if "GUARD_FAIL" not in failure_codes:
            failure_codes.append("GUARD_FAIL")
    if any("估算高度" in str(w) or "max_lines" in str(w) for w in compile_warnings):
        if "TEXT_OVERFLOW" not in failure_codes:
            failure_codes.append("TEXT_OVERFLOW")
    if not compile_report.get("passed", False):
        failure_codes.append("COMPILE_FAIL")
    if not evidence.get("rendered"):
        failure_codes.append("RENDER_UNAVAILABLE")
    blocking = bool(failure_codes and any(c in failure_codes for c in {
        "OVERLAP", "SOURCE_COLLISION", "CHART_LABEL_COLLISION", "TEXT_OVERFLOW",
        "READABILITY_FAIL", "DATA_INTEGRITY_FAIL", "COMPILE_FAIL", "GUARD_FAIL"}))
    passed = score >= thr["pass"] and not blocking
    status = "BLOCKED" if blocking else ("PREVIEW_ONLY" if not evidence.get("rendered") else ("PASS" if passed else "REVISE"))
    next_action = ("fix: " + ", ".join(failure_codes)) if failure_codes else "ready for Art Critic"
    return {
        "qa_version": "1.2",
        "score": round(score, 1),
        "passed": passed,
        "status": status,
        "threshold": thr["pass"],
        "deduction_by_domain": {k: round(v, 1) for k, v in deduction_by_domain.items()},
        "items": items,
        "guard": {"score": guard["score"], "checks": len(guard["checks"])},
        "compile": {"passed": compile_report.get("passed"),
                    "warnings": len(compile_warnings),
                    "slides": compile_report.get("slides"),
                    "file_bytes": compile_report.get("file_bytes")},
        "render": {"rendered": evidence.get("rendered"),
                   "reason": evidence.get("reason"),
                   "dir": str(render_dir) if render else None,
                   "pages": len(evidence.get("pages", []))},
        "render_evidence": evidence,
        "failure_codes": failure_codes,
        "blocking_items": sum(1 for it in items if it.get("level") == "error"),
        "affected_slides": sorted({str(it.get("id")) for it in items if it.get("id")}),
        "next_action": next_action,
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


def release_manifest(spec: dict, qa_report: dict, critic_report: dict | None = None,
                     *, compile_report: dict | None = None, theme_id: str | None = None,
                     render_evidence_path: str | None = None,
                     revision_count: int = 0, revision_log: list | None = None) -> dict:
    """按 production-contract.md「Release Manifest」契约确定性生成发布清单。

    状态合成规则：任一方 BLOCKED → BLOCKED；任一方 REVISE → REVISE；
    两者都 PASS 才为 PASS；其余（如缺少真实渲染证据）为 PREVIEW_ONLY。
    revision_log 只应引用失败码与页面 ID，不嵌入整份中间报告。
    """
    import hashlib
    import json
    from datetime import datetime, timezone

    canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, default=str)
    spec_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    qa_status = str(qa_report.get("status", "BLOCKED"))
    critic_status = str((critic_report or {}).get("status", "PREVIEW_ONLY"))
    if "BLOCKED" in (qa_status, critic_status):
        status = "BLOCKED"
    elif "REVISE" in (qa_status, critic_status):
        status = "REVISE"
    elif (qa_status, critic_status) == ("PASS", "PASS"):
        status = "PASS"
    else:
        status = "PREVIEW_ONLY"
    return {
        "source_spec_hash": spec_hash,
        "theme_id": theme_id or (spec.get("theme") or {}).get("id"),
        "slide_count": len(spec.get("slides") or []),
        "compile_report": compile_report or qa_report.get("compile"),
        "qa_report": qa_report,
        "critic_report": critic_report,
        "render_evidence_path": (render_evidence_path
                                 or (qa_report.get("render") or {}).get("dir")),
        "revision_count": int(revision_count),
        "revision_log": list(revision_log or []),
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------
# 可选 CLI： python qa.py build_mydeck.py output.pptx [--json] [--no-render]
# --------------------------------------------------------------------------
def main(argv):
    import importlib.util
    import json
    if len(argv) < 3:
        print("usage: python qa.py <build_module.py> <output.pptx> "
              "[--json] [--no-render] [--manifest]")
        return 1
    mod_path = Path(argv[1])
    spec_mod = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    mod = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    if spec is None:
        print("build module must define build_spec() or SPEC")
        return 1
    result = run_qa(spec, argv[2], render="--no-render" not in argv)
    if "--manifest" in argv:
        from art_critic import critique_deck
        critic = critique_deck(spec, result.get("render_evidence"))
        manifest = release_manifest(spec, result, critic)
        manifest_path = Path(argv[2]).with_suffix(".manifest.json")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"manifest: {manifest_path} (status={manifest['status']})")
    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"QA score={result['score']}/100 passed={result['passed']} "
              f"(threshold {result['threshold']})")
        for it in result["items"]:
            print(f"  [{it['domain']}/{it['level']:5s}] -{it['penalty']:.1f}  {it['msg']}")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
