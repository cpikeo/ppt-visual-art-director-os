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

from primitives import (DEFAULT_WIDTH, DEFAULT_HEIGHT, spec_fingerprint,
                         text_contrast_verdict)
from guard import check_spec

# 扣分规则（确定性，非审美判断）：
# 每一项都是「OS 规则被违反」的量化，扣分可被调用方覆盖。
DEFAULT_PENALTIES = {
    "guard_error": 6.0,        # 越界等错误级静态问题（每项）
    "guard_warn": 2.5,         # 网格 / 重叠 / 容量 / Accent 超限（每项）
    "guard_hint": 0.1,         # 对齐 / 节奏提示（几乎不扣，仅留痕）
    "compile_warn": 1.5,       # 引擎编译诊断（每项，不含 [guard] 前缀）
    "render_gravity": 3.0,     # 渲染显著性质心与声明锚点漂移 > .28
    "render_accent": 3.0,      # 渲染强调色像素比 > 主题 accent_max（OS §06 Accent 克制）
    "render_occupancy": 3.0,   # 渲染占用率超过主题最小留白要求
    "render_margin": 2.0,      # 渲染边缘带不安静（内容贴近安全区边缘）
    "render_missing": 2.0,     # 无渲染环境（结构证据降级，轻微提示）
    "render_contrast": 3.0,    # 渲染实测「文字 vs 其下方像素」低于 WCAG AA（每项）
    "render_contrast_low": 1.5,  # 同上但仅偏软（3.0–4.5:1），只提示不阻断
    "preflight_hint": 0.0,     # guard 预检 hint：与 Art Critic 同口径的提前提醒，不扣分
}
DEFAULT_THRESHOLDS = {
    "pass": 90.0,              # passed = score >= pass
    "gravity_drift": 0.28,     # 归一化漂移上限
    # accent_pixel 缺省时回落主题 constraints.accent_max（见下方解析），
    # 不再硬编码 0.08——与 guard/route/art_critic 同一把尺子（OS §06 Accent 克制）。
    "text_contrast_fail": 3.0,   # 实测文字对比低于此值 → 阻断（叠加不可读）
    "text_contrast_warn": 4.5,   # WCAG AA 正文门槛
    # 可选：主题 constraints.min_whitespace 或调用方 thresholds.min_whitespace
    # 指定最小留白比例；显式 thresholds 优先。
    # 可选：margin_occupancy 开启「边缘带安静度」检查（None=默认关闭，因为
    # 通栏图片背景会让边缘带合法地不安静，应只在纯色/结构背景主题开启）。
    "margin_occupancy": None,
}


# 预检码 → Art Critic 硬门槛：命中这些项时渲染结果必然不是 PASS，先修再渲染
PREFLIGHT_HARD_CODES = {
    "INTENT_UNCLEAR": "BLOCKED",     # 无可复述 insight
    "FOCUS_UNBOUND": "REVISE",       # focus 未绑定元素 → FOCUS_COMPETING
    "CARD_WALL": "REVISE",           # 圆角容器超预算 → CARD_WALL
    "RHYTHM_FLAT": "REVISE",         # 连续三页同密度同能量
}


KEY_PAGE_CAP = 6   # Level 2 最多测这么多页；再多与全量无异，失去渐进意义


def key_pages(spec: dict) -> list[int]:
    """Progressive QA Level 2 的选页：只有这些页的判断真的需要像素证据。

    规则刻意保守且可从 spec 复算：封面与收尾页（节奏/留白/首尾印象）、含图片或
    背景画心的页（叠加可读性与资产侵入）、含图表的页（占用率与标签密度）。
    纯文字结构页的 QA 结论在静态阶段已经确定，渲染它们不改变判断。
    """
    slides = spec.get("slides") or []
    picked: list[int] = []
    for i, s in enumerate(slides):
        n = i + 1
        if i == 0 or i == len(slides) - 1:
            picked.append(n)
            continue
        hit = False
        for e in s.get("elements") or []:
            if not isinstance(e, dict):
                continue
            t = str(e.get("type", ""))
            if t in ("image", "chart", "native_chart") or e.get("overlay") \
                    or e.get("content_protection"):
                hit = True
                break
        if hit:
            picked.append(n)
    if len(picked) > KEY_PAGE_CAP:   # 保留首尾 + 中段均匀取样，避免退化成全量
        mid = [n for n in picked if n not in (picked[0], picked[-1])]
        step = max(1, len(mid) // (KEY_PAGE_CAP - 2)) if len(mid) > 1 else 1
        picked = [picked[0]] + mid[::step][:KEY_PAGE_CAP - 2] + [picked[-1]]
    return sorted(set(picked))


def run_qa(spec: dict, output: str | Path, penalties: dict | None = None,
           thresholds: dict | None = None, guard_rules: dict | None = None,
           render_dir: str | Path | None = None, dpi: int = 96,
           render: bool = True, preflight_gate: bool = False,
           qa_level: int = 3, render_pages: list[int] | None = None,
           workers: int = 2, use_cache: bool = True,
           raster: str = "auto") -> dict:
    """
    完整 QA：guard + compile + render（可选）。

    penalties / thresholds / guard_rules 由调用方传入，覆盖默认值（不写死参数）。
    render_dir 为 None 时使用 `<output>_render/` 稳定目录，保证渲染证据可被
    Release Manifest 的 render_evidence_path 记录与复核；无渲染环境自动降级。

    复用（use_cache=True）覆盖三段重复劳动：按页指标缓存、PPTX→PDF 转换复用、以及
    「本轮会编译成像素的那部分 spec」未变时跳过编译本身。改 insight / density / focus
    这类声明字段不动像素，因此一整轮重跑只需几十毫秒；元素、图片或主题一变即失效。
    render=False 适合快速迭代布局，发布前必须恢复为 True。

    Progressive QA：qa_level=1 只看文件/元素/页数（不渲染），=2 只渲染关键页
    （`render_pages` 缺省时按 spec 自动挑选），=3（默认）全量渲染 + 全部检查。
    Level 1/2 的判定不会被用于发布：缺少全量像素证据时状态上限为 REVISE。

    use_cache=True（默认）复用渲染目录里按页内容寻址的指标：未改动的页不再重测，
    全部命中时连 LibreOffice 都不启动。判定口径不变——缓存键覆盖本页、主题、画布、
    dpi、页内图片指纹与渲染器身份；需要绝对冷测时传 use_cache=False 或 --no-cache。

    raster（默认 "auto"）：光栅化格式。JPEG 快测比 PNG 快约 10×，指标偏差在远离
    判定阈值时可忽略；"auto" 会在**指标贴着阈值**的页上自动改用无损 PNG 复测，
    因此判定与全程 PNG 一致。传 "png" 可强制全程无损（取证/排障）。
    """
    import time
    from compiler import compile_deck
    from render_check import compile_reuse, record_compile, spec_view

    pen = {**DEFAULT_PENALTIES, **(penalties or {})}
    thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    output_path = Path(output)
    t0 = time.time()

    # 1) 静态治理（guard_rules 独立传入，qa 不解读内部结构）
    t_guard = time.time()
    guard = check_spec(spec, rules=guard_rules)
    t_compile = time.time()

    # 2) 渲染证据目录先定下来：编译/PDF 的复用记录都放在这里
    render_dir = (Path(render_dir) if render_dir
                  else output_path.with_name(output_path.stem + "_render"))

    # 3) 编译。Guard 已在本函数完成，关闭编译器内的重复静态扫描以减少一次全 deck 遍历。
    # 发布仍会在 compile_report 中保留 guard 摘要，口径由本函数唯一掌握。
    # 先问一句「像素视图变了吗」：没变就连 compile 与 soffice 都省掉（决策先于生成）。
    compile_report = None
    view = None
    if use_cache:
        try:
            render_dir.mkdir(parents=True, exist_ok=True)
            view = spec_view(spec, base_path=output_path.parent)
            compile_report = compile_reuse(render_dir, output_path, view)
        except Exception:
            compile_report = None
    if compile_report is None:
        compile_report = compile_deck(spec, output_path, checks=False,
                                      guard_rules=guard_rules)
        if use_cache and view is not None:
            record_compile(render_dir, output_path, view, compile_report)
    else:
        try:
            compile_report["file_bytes"] = output_path.stat().st_size
        except OSError:
            pass
    t_render = time.time()
    compile_warnings = list(compile_report.get("warnings", []))

    # 4) 渲染证据（环境缺失时降级；按 Progressive 级别只测需要的页）
    evidence = {"rendered": False, "reason": None, "pages": []}
    skip_render_reason = None if render else "render_disabled"
    gate_hit: list[dict] = []
    try:
        qa_level = max(1, min(3, int(qa_level)))
    except (TypeError, ValueError):
        qa_level = 3
    if qa_level == 1 and render:
        render, skip_render_reason = False, "qa_level_1"
    if render and preflight_gate:
        codes = {i.get("code"): i for i in (guard.get("preflight") or [])
                 if i.get("code") in PREFLIGHT_HARD_CODES}
        if codes:
            # 不渲染：省掉一轮 soffice+poppler，同时把可执行修正直接交回调用方
            gate_hit = list(codes.values())
            skip_render_reason = "preflight_gate"
            render = False
    wanted_pages = None
    if render and qa_level == 2:
        # 调用方（或 route.plan_deck 的 verification.pixel_page_ids）给了页码就用它；
        # 否则按 spec 自己挑关键页——两条路径都能独立工作，不产生隐式依赖。
        wanted_pages = [int(n) for n in render_pages] if render_pages else key_pages(spec)
    if render:
        try:
            from render_check import render_evidence
            evidence = render_evidence(output_path, spec, render_dir, dpi,
                                       pages=wanted_pages, workers=workers,
                                       use_cache=use_cache,
                                       raster=raster)
            evidence.setdefault("coverage", {})
            evidence["coverage"].update({"qa_level": qa_level,
                                         "total_slides": len(spec.get("slides") or []),
                                         "workers": workers})
        except Exception as exc:
            evidence = {"rendered": False, "reason": f"render evidence failed: {exc}",
                        "pages": []}
    else:
        evidence = {"rendered": False, "reason": "render disabled for fast iteration",
                    "pages": [],
                    "coverage": {"qa_level": qa_level, "rendered_pages": 0,
                                 "total_pages": len(spec.get("slides") or [])}}

    slides_count = [x for x in (spec.get("slides") or [])]

    # 5) 计分
    deduction = 0.0
    items: list[dict] = []
    deduction_by_domain = {"guard": 0.0, "compile": 0.0,
                           "render": 0.0, "config": 0.0}

    # hint 级条目按 rule 聚合（网格/节奏微调提示不逐条刷屏，数据仍在 guard.checks）
    hint_buckets: dict[str, dict] = {}
    for c in guard["checks"]:
        key = f"guard_{c['level']}"
        if c.get("rule") == "preflight" and c["level"] == "hint":
            key = "preflight_hint"      # 预检提前给出，避免同一问题在渲染后二次扣分
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
    accent_max = thr.get("accent_pixel", theme_constraints.get("accent_max", 0.08))
    try:
        accent_max = float(accent_max)
        if not 0 < accent_max <= 1:
            raise ValueError("accent_pixel must be between 0 and 1")
    except (TypeError, ValueError):
        items.append({"domain": "config", "level": "warn",
                      "rule": "accent_budget", "id": None,
                      "msg": f"忽略无效的 accent_max={accent_max!r}（应为 0–1），回退 0.08",
                      "penalty": 0.0})
        accent_max = 0.08
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
                          "msg": (f"显著性质心偏离声明焦点"
                                  f"（{p.get('anchor_id') or '未声明'}）"
                                  f" {p['gravity_drift']:.2f} > {thr['gravity_drift']}"
                                  f"；锚点取 page_intent.focus，非 gravity_anchor"),
                          "penalty": pen["render_gravity"]})
        if p.get("accent_pixel_ratio", 0) > accent_max:
            deduction += pen["render_accent"]
            deduction_by_domain["render"] += pen["render_accent"]
            items.append({"domain": "render", "level": "warn",
                          "rule": "accent_budget", "id": p.get("slide"),
                          "msg": (f"强调色像素 {p['accent_pixel_ratio']:.1%} > "
                                  f"{accent_max:.0%}（OS §06）"),
                          "penalty": pen["render_accent"]})

    readability_fail = False
    for p in evidence.get("pages", []):
        # 渲染实测「文字 vs 字下面那块底」——全页亮度一致地暗/亮都掩盖不了它。
        # 判定在 primitives.text_contrast_verdict 共享：与 art_critic 同一结论。
        _tc = text_contrast_verdict(p, thr["text_contrast_fail"],
                                    thr["text_contrast_warn"])
        if _tc["level"] == "unknown":
            continue
        tc, worst = _tc["value"], _tc["worst"]
        if _tc["level"] == "fail":
            readability_fail = True
            deduction += pen["render_contrast"]
            deduction_by_domain["render"] += pen["render_contrast"]
            items.append({"domain": "render", "level": "error",
                          "rule": "text_contrast", "id": p.get("slide"),
                          "msg": (f"实测文字对比 {tc:.2f}:1 < {thr['text_contrast_fail']}:1"
                                  f"（「{worst.get('id', '?')}」字色 {worst.get('color')}"
                                  f" vs 局部底 {worst.get('background')}）"
                                  ),
                          "penalty": pen["render_contrast"]})
        elif tc < thr["text_contrast_warn"]:
            # tc 已是正文级最坏值：注记级低于 AA 但 ≥3:1 属允许范围，不提示
            deduction += pen["render_contrast_low"]
            deduction_by_domain["render"] += pen["render_contrast_low"]
            items.append({"domain": "render", "level": "warn",
                          "rule": "text_contrast", "id": p.get("slide"),
                          "msg": (f"实测文字对比 {tc:.2f}:1 < WCAG AA {thr['text_contrast_warn']}:1"
                                  f"（「{worst.get('id', '?')}」）"),
                          "penalty": pen["render_contrast_low"]})

    _t_end = time.time()
    perf = {
        "total_ms": int((_t_end - t0) * 1000),
        "guard_ms": int((t_compile - t_guard) * 1000),
        "compile_ms": int((t_render - t_compile) * 1000),
        "compile_reused": bool(compile_report.get("reused")),
        "render_ms": int((_t_end - t_render) * 1000),
        "slides": len(slides_count),
        "preflight_items": len(guard.get("preflight") or []),
        "render_skipped": bool(skip_render_reason),
        # 渐进级别与并行度：让「省掉了什么」可核对，而不是只报一个总时长
        "qa_level": qa_level,
        "render_workers": workers,
        "rendered_pages": len(evidence.get("pages") or []),
        "requested_pages": wanted_pages,
        # 重复计算的直接证据：命中越多，说明这一轮越没白跑
        # L1 不渲染 → 缓存语义不适用，报 0 而不是 None（报表里可直接求和）
        "cache_hits": ((evidence.get("coverage") or {}).get("cache_hits")
                       if evidence.get("rendered") else 0),
        "cache_misses": ((evidence.get("coverage") or {}).get("cache_misses")
                         if evidence.get("rendered") else 0),
        "cache_enabled": bool(use_cache),
    }

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
    if readability_fail and "READABILITY_FAIL" not in failure_codes:
        # 渲染层实测的可读性失败与静态 contrast 同级：阻断发布
        failure_codes.append("READABILITY_FAIL")
    if not compile_report.get("passed", False):
        failure_codes.append("COMPILE_FAIL")
    if not evidence.get("rendered"):
        failure_codes.append("RENDER_UNAVAILABLE")
    blocking = bool(failure_codes and any(c in failure_codes for c in {
        "OVERLAP", "SOURCE_COLLISION", "CHART_LABEL_COLLISION", "TEXT_OVERFLOW",
        "READABILITY_FAIL", "DATA_INTEGRITY_FAIL", "COMPILE_FAIL", "GUARD_FAIL"}))
    passed = score >= thr["pass"] and not blocking
    status = "BLOCKED" if blocking else ("PREVIEW_ONLY" if not evidence.get("rendered") else ("PASS" if passed else "REVISE"))
    # 像素证据覆盖率决定「能不能发布」：Level 1/2（或任何子集渲染）都不给发布级结论，
    # 判定阈值一律不放宽——只是把 PASS 留给 Level 3。
    coverage = evidence.get("coverage") or {}
    rendered_n = int(coverage.get("rendered_pages") or len(evidence.get("pages") or []))
    total_n = int(coverage.get("total_pages") or len(slides_count)) or 1
    partial_pixel = bool(evidence.get("rendered")) and rendered_n < total_n
    release_eligible = (status == "PASS" and rendered_n >= total_n
                        and not blocking and not partial_pixel)
    if status == "PASS" and not release_eligible:
        status = "REVISE"
    if partial_pixel:
        failure_codes = sorted(set(failure_codes) | {"PIXEL_COVERAGE_PARTIAL"})
    if gate_hit:
        next_action = "fix preflight before render: " + ", ".join(
            f"{i.get('slide')}:{i['code']}" for i in gate_hit)
        failure_codes = sorted(set(failure_codes) | {i["code"] for i in gate_hit})
    else:
        base = ("fix: " + ", ".join(failure_codes)) if failure_codes else "ready for Art Critic"
        next_action = (base + " · 发布前需 qa_level=3 全量像素复核"
                       if (partial_pixel or qa_level < 3) else base)
    return {
        "qa_version": "1.4",
        # 自证戳：报告属于哪一份 spec。清单会核对，防止拿旧报告/旁路产物冒充新结果
        "source_spec_hash": spec_fingerprint(spec),
        "score": round(score, 1),
        "passed": passed,
        "status": status,
        "threshold": thr["pass"],
        "deduction_by_domain": {k: round(v, 1) for k, v in deduction_by_domain.items()},
        "items": items,
        "guard": {"score": guard["score"], "checks": len(guard["checks"]),
                  "grid": guard.get("grid"), "line_measure": guard.get("line_measure")},
        "compile": {"passed": compile_report.get("passed"),
                    "warnings": len(compile_warnings),
                    "slides": compile_report.get("slides"),
                    "file_bytes": compile_report.get("file_bytes")},
        "render": {"rendered": evidence.get("rendered"),
                   "reason": evidence.get("reason"),
                   "dir": str(render_dir) if render else None,
                   "pages": len(evidence.get("pages", [])),
                   "coverage": coverage or None},
        "release_eligible": release_eligible,
        "render_evidence": evidence,
        "preflight": {"count": len(guard.get("preflight") or []),
                      "codes": guard.get("preflight_codes") or [],
                      "items": guard.get("preflight") or []},
        "performance": perf,
        "preflight_gate": {"enabled": preflight_gate, "triggered": bool(gate_hit),
                           "hits": gate_hit},
        "failure_codes": failure_codes,
        "blocking_items": sum(1 for it in items if it.get("level") == "error"),
        "affected_slides": sorted({str(it.get("id")) for it in items if it.get("id")}),
        "next_action": next_action,
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


def release_manifest(spec: dict, qa_report: dict, critic_report: dict | None = None,
                     *, compile_report: dict | None = None, theme_id: str | None = None,
                     render_evidence_path: str | None = None,
                     revision_count: int = 0, revision_log: list | None = None,
                     verification: dict | None = None) -> dict:
    """按 production-contract.md「Release Manifest」契约确定性生成发布清单。

    状态合成规则：任一方 BLOCKED → BLOCKED；任一方 REVISE → REVISE；
    两者都 PASS 才为 PASS；其余（如缺少真实渲染证据）为 PREVIEW_ONLY。
    revision_log 只应引用失败码与页面 ID，不嵌入整份中间报告。
    """
    from datetime import datetime, timezone

    spec_hash = spec_fingerprint(spec)
    issues: list[str] = []
    notes: list[str] = []
    page_ids = {str(s.get("id")) for s in (spec.get("slides") or []) if s.get("id")}

    def _attest(report: dict | None, name: str) -> None:
        """报告必须能被追溯到当前 spec：盖过戳的要一致，声称 PASS 的必须有戳。"""
        if not isinstance(report, dict) or not report:
            return
        claims_pass = str(report.get("status", "")).upper() == "PASS"
        got = report.get("source_spec_hash")
        if got and got != spec_hash:
            issues.append(f"{name} 的 source_spec_hash={got} 与当前 spec {spec_hash} 不符"
                          f"（报告来自另一版 spec，已过期或被替换）")
        elif not got:
            if claims_pass:
                issues.append(f"{name} 声称 PASS 却没有 source_spec_hash，无法证明它由当前 spec "
                              f"产出（旁路生成的报告不能作为发布证据）")
            else:
                notes.append(f"{name} 未盖 source_spec_hash（旧格式报告，仅记录不阻断）")

    _attest(qa_report, "qa_report")
    _attest(critic_report, "critic_report")

    def _pages(report: dict | None, name: str) -> None:
        if not isinstance(report, dict):
            return
        seen = {str(x.get("slide")) for x in (report.get("slides") or [])
                if isinstance(x, dict) and x.get("slide") is not None}
        cov = report.get("coverage") or (report.get("render") or {}).get("coverage") or {}
        seen |= {str(x) for x in (cov.get("rendered_ids") or []) if x is not None}
        seen |= {str(p.get("slide")) for p in (report.get("pages") or [])
                 if isinstance(p, dict) and p.get("slide") is not None}
        seen.discard("None")
        ghost = sorted(seen - page_ids) if page_ids else sorted(seen)
        if ghost:
            issues.append(f"{name} 引用了当前 spec 之外的页面：{'、'.join(ghost)}")

    if critic_report:
        _pages(critic_report, "critic_report")
        n_c = len(critic_report.get("slides") or [])
        if n_c and page_ids and n_c != len(page_ids):
            issues.append(f"critic_report 覆盖 {n_c} 页，与 spec 的 {len(page_ids)} 页不一致")
    if qa_report.get("render_evidence"):
        _pages(qa_report["render_evidence"], "qa render_evidence")

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
    cov = ((qa_report.get("render") or {}).get("coverage")
           or ((qa_report.get("render_evidence") or {}).get("coverage")) or {})
    ver = {
        "qa_level": (qa_report.get("performance") or {}).get("qa_level"),
        "pixel_pages": cov.get("rendered_pages"),
        "pixel_total": cov.get("total_pages"),
        "release_eligible": bool(qa_report.get("release_eligible")),
    }
    ver.update(verification or {})
    if issues:
        status = "BLOCKED"          # 报告与 spec 对不上时，任何 PASS 都不作数
    return {
        "source_spec_hash": spec_hash,
        "validation": {"issues": issues, "notes": notes, "page_count": len(page_ids)},
        "theme_id": theme_id or (spec.get("theme") or {}).get("id"),
        "slide_count": len(spec.get("slides") or []),
        "verification": ver,
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
        print("usage: python qa.py <build_module.py> <output.pptx> [--json] "
              "[--no-render] [--manifest] [--fast] [--preflight] "
              "[--quick | --key-pages | --level N] [--no-cache] "
              "[--raster auto|png|jpeg]")
        return 1
    mod_path = Path(argv[1])
    spec_mod = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    mod = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    if spec is None:
        print("build module must define build_spec() or SPEC")
        return 1
    fast = "--fast" in argv
    # --preflight 即启用闸门：静态可判定的硬门槛命中时直接跳过渲染
    gate = fast or "--preflight" in argv
    # Progressive QA：--quick=L1（不渲染）· --key-pages=L2（只测关键页）· 默认 L3 全量
    level = 3
    for i, a in enumerate(argv):
        if a in ("--quick", "--level1"):
            level = 1
        elif a in ("--key-pages", "--key", "--level2"):
            level = 2
        elif a == "--level" and i + 1 < len(argv):
            level = int(argv[i + 1])
    # --raster png|jpeg|auto：默认 auto（快测 + 临界页无损复检）
    raster = "auto"
    for i, a in enumerate(argv):
        if a == "--raster" and i + 1 < len(argv):
            raster = argv[i + 1].strip().lower()
        elif a == "--lossless":
            raster = "png"
    result = run_qa(spec, argv[2], render="--no-render" not in argv,
                    preflight_gate=gate, dpi=72 if fast else 96, qa_level=level,
                    use_cache="--no-cache" not in argv, raster=raster)
    if "--preflight" in argv:
        for i in (result.get("preflight") or {}).get("items", []):
            print(f"  {i['slide']:>6} {i['code']:17s} {i['observation']}")
            print(f"          fix → {i['minimal_fix']}")
        print(f"preflight: {result['performance']['preflight_items']} 项 · "
              f"guard {result['performance']['guard_ms']}ms · "
              f"compile {result['performance']['compile_ms']}ms · "
              f"render {result['performance']['render_ms']}ms"
              + (f" (skipped: {result['performance']['render_skipped']})"
                 if result['performance']['render_skipped'] else ""))
        return 0
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
        cov = (result.get("render") or {}).get("coverage") or {}
        print(f"QA score={result['score']}/100 passed={result['passed']} "
              f"(threshold {result['threshold']}) status={result['status']} "
              f"level={result['performance']['qa_level']} "
              f"pixel={cov.get('rendered_pages', result['render']['pages'])}/"
              f"{cov.get('total_pages', result['performance']['slides'])}"
              + ("" if result["release_eligible"] else " [非发布级]"))
        for it in result["items"]:
            print(f"  [{it['domain']}/{it['level']:5s}] -{it['penalty']:.1f}  {it['msg']}")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
