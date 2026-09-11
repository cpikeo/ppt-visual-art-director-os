# -*- coding: utf-8 -*-
"""
Layer 4 · QA（工程验证层 · Engineering Correctness · 100 分制）

职责边界（**只回答一个问题：这份 PPT 能不能正确交付？**）：
    内容层  文本溢出 / 内容缺失 / 数据完整性 / 图表异常
    几何层  越界 / 重叠 / 安全区 / 对齐
    渲染层  字体替换 / 图片损坏 / PDF 与像素异常
输出只有三种判定：PASS / FAIL(→BLOCKED·REVISE) / WARNING（记分不阻断）。

它**不做审美评分**（层级、空间节奏、焦点、气质是判断叙事，归 references/design-craft）；分数只用于
Release Gate 与迭代对比。数据流（只读，不修改 spec）：
    spec ──→ guard.check_spec      静态治理（OS 硬约束）
         ──→ compile_deck          编译诊断（引擎 warnings）
         ──→ render_evidence      真实渲染证据（有环境时，按模式取子集）

阈值全部由调用方传入（thresholds），缺省用保守默认值。
"""
from __future__ import annotations

from pathlib import Path

from primitives import (spec_fingerprint,
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
    "preflight_hint": 0.0,     # guard 预检 hint：与 primitives 同口径的提前提醒，不扣分
    "design_advisory": 0.0,    # guard 的设计契约条目：观察，不是扣分项
}
DEFAULT_THRESHOLDS = {
    "pass": 90.0,              # passed = score >= pass
    "gravity_drift": 0.28,     # 归一化漂移上限
    # accent_pixel 缺省时回落主题 constraints.accent_max（见下方解析），
    # 不再硬编码 0.08——与 guard/route 同一把尺子（OS §06 Accent 克制）。
    "text_contrast_fail": 3.0,   # 实测文字对比低于此值 → 阻断（叠加不可读）
    "text_contrast_warn": 4.5,   # WCAG AA 正文门槛
    # 可选：主题 constraints.min_whitespace 或调用方 thresholds.min_whitespace
    # 指定最小留白比例；显式 thresholds 优先。
    # 可选：margin_occupancy 开启「边缘带安静度」检查（None=默认关闭，因为
    # 通栏图片背景会让边缘带合法地不安静，应只在纯色/结构背景主题开启）。
    "margin_occupancy": None,
}


# Level 2（review）最多测这么多页；再多与全量无异，失去渐进意义
KEY_PAGE_CAP = 6


# ════════════════════════════════════════════════════════════════════════
# 执行模式（流程控制）：draft 不渲染 · review 只测变化页 · release 全量 + Critic
# Mode 决定「渲染不渲染、Critic 何时介入、状态给到哪一级」；
# 与 Fast/Advanced（预算控制：资产数/dpi）正交，互不替代。
# 设计要点：**没有门控、没有状态机、没有第二套缓存**。
# Critic 只在 review / release 跑；draft / sketch 恒不跑。想跳过渲染的成本由
# 「不渲染 + 页级渲染缓存」承担，而不是由「先攒两轮干净再放行」承担。
# ════════════════════════════════════════════════════════════════════════
EXECUTION_MODES = {
    "sketch": {
        "label": "Sketch · 草图链",
        "qa_level": 1, "render": False,
        "aim": "结构探索：只守「错」（数据诚实性/结构合法性），不守「不好」——"
               "颜色分析/媒体检查/文字合同全部免除，变体迭代不被设计契约拦截",
        "deliver": "PPTX + ghost 预览建议；升 draft 时契约检查恢复",
    },
    "spec": {
        "label": "Spec Check · 零成本档",
        "qa_level": 1,
        "render": False,
        "compile": False,
        "aim": "只读 spec 数据：Normalizer + Guard + 风险预测与策略，零编译零渲染零 import pptx。"
               "用于「每改一版先看契约」的高频回环；产物是 PPTX 的轮次请走 draft",
        "deliver": "判定 + 风险政策（不产出 .pptx，也不写渲染目录）"
    },
    "draft": {
        "label": "Creative Draft · 创作链",
        "qa_level": 1, "render": False,
        "aim": "初稿/方向探索/多方案：结构合法 + 可编译 + 可编辑 PPTX，零渲染成本",
        "deliver": "PPTX + Guard 报告 + 风险预测与生成策略 + ghost 预览（~1ms/页）",
    },
    "review": {
        "label": "Design Review · 审查链",
        "qa_level": 2, "render": True,
        "aim": "方向确认：只渲染本轮变化页（无上一版可比时回落关键页）；像素证据直出可执行修正",
        "deliver": "子集像素证据 + verdict（遮挡/低对比/空页/失衡逐页点名）",
    },
    "release": {
        "label": "Release · 发布链",
        "qa_level": 3, "render": True,
        "aim": "终版发布：全量渲染 + QA + Release Manifest，唯一给发布资格（release_eligible）的一档",
        "deliver": "PPTX + QA JSON + Render Evidence + Manifest（+Revision Log）",
    },
}


def mode_profile(mode: str | None) -> dict:
    """mode 名 → 执行档案（未知/None 一律回落 release：宁严勿松）。"""
    return dict(EXECUTION_MODES.get(str(mode or "").strip().lower(), EXECUTION_MODES["release"]))


# ── 语义变更分类：把「改了什么」翻译成「要重跑什么」───────────────────
# 只影响声明/评分、不影响像素的页字段（render_check 页级缓存键同向排除）：
PIXEL_NEUTRAL_PAGE_FIELDS = (
    "insight", "narrative_role", "reading_order", "energy", "density",
    "empty_space_role", "page_family", "rhythm_stage", "continuity_token",
)


def _pixel_projection(slide: dict) -> str:
    """剥掉像素中性字段后的页投影（用于页级变更分类）。"""
    import copy, json
    s = copy.deepcopy(slide)
    s.pop("notes", None)
    s.pop("source_note", None)
    pi = s.get("page_intent")
    if isinstance(pi, dict):
        for f in PIXEL_NEUTRAL_PAGE_FIELDS:
            pi.pop(f, None)
    return json.dumps(s, ensure_ascii=False, sort_keys=True, default=str)


def classify_spec_change(old_spec: dict | None, new_spec: dict) -> dict:
    """上一版 spec → 本版 spec 的语义分类（确定性、纯函数）。

    返回：
      deck   : "identical" | "narrative" | "pages" | "structure" | "full_render"
               （theme/canvas 变 → full_render；页数/页 ID 变 → structure）
      pages  : {slide_id: "unchanged" | "narrative" | "page_render"}
      render_needed : 需要像素复核的 1-based 页码（page_render 类）
      summary: 各类计数
    消费方：review 模式的渲染集（把「要重测的页」缩到变化页）、
    「改了一句 insight 不必重渲染」的显式化。
    """
    import copy, json
    new_slides = new_spec.get("slides") or []
    if not isinstance(old_spec, dict) or not old_spec:
        return {"deck": "structure", "pages": {s.get("id"): "page_render"
                                                for s in new_slides if isinstance(s, dict)},
                "render_needed": [i + 1 for i in range(len(new_slides))],
                "summary": {"reason": "no_previous_spec"}}

    old_slides = old_spec.get("slides") or []
    old_by_id = {s.get("id"): s for s in old_slides if isinstance(s, dict)}
    new_ids = [s.get("id") for s in new_slides if isinstance(s, dict)]
    old_ids = list(old_by_id.keys())
    pages: dict[str, str] = {}
    render_needed: list[int] = []
    narrative_only = True
    for i, s in enumerate(new_slides):
        if not isinstance(s, dict):
            continue
        sid = s.get("id")
        prev = old_by_id.get(sid)
        if prev is None:
            cls = "page_render"          # 新页：必须出像素
        else:
            if _pixel_projection(prev) == _pixel_projection(s):
                diff = _intent_differs(prev, s)
                cls = "narrative" if diff else "unchanged"
            else:
                cls = "page_render"
        pages[str(sid)] = cls
        if cls == "page_render":
            render_needed.append(i + 1)
            narrative_only = False     # 只有像素级变更才打断「纯声明修改」
    if old_ids != new_ids:
        deck = "structure"
    elif json.dumps(old_spec.get("theme"), sort_keys=True, default=str) != \
            json.dumps(new_spec.get("theme"), sort_keys=True, default=str) or \
            json.dumps(old_spec.get("canvas"), sort_keys=True, default=str) != \
            json.dumps(new_spec.get("canvas"), sort_keys=True, default=str):
        deck = "full_render"            # 主题/画布：所有页的像素都可能变
    elif not render_needed and narrative_only:
        deck = "narrative" if any(v == "narrative" for v in pages.values()) else "identical"
    else:
        deck = "pages"
    if deck in ("structure", "full_render"):
        render_needed = [i + 1 for i in range(len(new_slides))]
    summary = {k: sum(1 for v in pages.values() if v == k)
               for k in ("unchanged", "narrative", "page_render")}
    summary["deck"] = deck
    return {"deck": deck, "pages": pages, "render_needed": sorted(render_needed),
            "summary": summary}


def _intent_differs(a: dict, b: dict) -> bool:
    """两页的像素中性字段（声明/备注）是否有差异。"""
    import copy, json
    def keep(s: dict) -> dict:
        c = {k: s.get(k) for k in ("notes", "source_note")}
        pi = s.get("page_intent")
        if isinstance(pi, dict):
            c["page_intent"] = {k: pi.get(k) for k in PIXEL_NEUTRAL_PAGE_FIELDS}
        return c
    return json.dumps(keep(a), sort_keys=True, default=str) != \
        json.dumps(keep(b), sort_keys=True, default=str)


# ── 上一版 spec（唯一保留的跨轮状态）──────────────────────────────────
# 只服务一件事：把「本轮改了哪几页」算出来，从而 review 只渲染变化页。
# 没有状态机、没有连续干净计数、没有 Critic 结果缓存——那些是 Stability Gate
# 的配套件，收益不足以付它引入的持久化/版本/调试成本（已删除）。
LAST_SPEC_NAME = "last_spec.json"


def _load_last_spec(render_dir: Path) -> dict | None:
    import json
    try:
        return json.loads((Path(render_dir) / LAST_SPEC_NAME).read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_last_spec(render_dir: Path, spec: dict) -> None:
    import json
    try:
        Path(render_dir).mkdir(parents=True, exist_ok=True)
        (Path(render_dir) / LAST_SPEC_NAME).write_text(
            json.dumps(spec, ensure_ascii=False, default=str), encoding="utf-8")
    except Exception:
        pass     # 它是加速器不是契约：写不进就退化为「无从对比」，本轮按关键页渲染


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


def verdict_of(status: str, score: float, items: list[dict],
               failure_codes: list[str]) -> dict:
    """QA 的对外判定只有三个词：PASS / FAIL / WARNING（契约）。

    `status` 保留给发布链的细粒度状态机（PASS / REVISE / BLOCKED / PREVIEW_ONLY /
    SKETCH）；`verdict` 是给 AI 与人的一行结论：
      PASS     —— 能正确交付（无阻断、无警告）
      WARNING  —— 能交付但有待办（只影响分数不影响发布）
      FAIL     —— 不能交付（阻断项必须先修）
    """
    blocking = [i for i in items if i.get("level") == "error"]
    warnings = [i for i in items if i.get("level") == "warn"]
    if blocking or status == "BLOCKED":
        verdict = "FAIL"
    elif warnings or status in ("REVISE", "PREVIEW_ONLY", "SKETCH") or score < 90:
        verdict = "WARNING"
    else:
        verdict = "PASS"
    return {"verdict": verdict, "status": status, "score": round(float(score), 1),
            "blocking": len(blocking), "warnings": len(warnings),
            "codes": list(failure_codes),
            "question": "这份 PPT 能不能正确交付？"}


_verdict_of = verdict_of     # 内部短名


def run_qa(spec: dict, output: str | Path, penalties: dict | None = None,
           thresholds: dict | None = None, guard_rules: dict | None = None,
           render_dir: str | Path | None = None, dpi: int = 96,
           render: bool | None = None,
           qa_level: int | None = None, render_pages: list[int] | None = None,
           workers: int = 2, use_cache: bool = True,
           raster: str = "auto", mode: str | None = None,
           normalize: bool = True,
           compile: bool | None = None) -> dict:
    """
    完整 QA：guard + compile + render（可选）。

    penalties / thresholds / guard_rules 由调用方传入，覆盖默认值（不写死参数）。
    render_dir 为 None 时使用 `<output>_render/` 稳定目录，保证渲染证据可被
    Release Manifest 的 render_evidence_path 记录与复核；无渲染环境自动降级。

    复用（use_cache=True）只覆盖两处——缓存全部家当：
      ① 页级渲染指标缓存（键 = 本页像素视图 + 主题 + 画布 + dpi + 图片指纹 + 渲染器）
      ② 编译/PDF 复用（PPTX 逐字节未变 → 不再调 soffice；像素视图未变 → 不再编译）
    改 insight / density 这类声明字段不动像素，因此一整轮重跑只需几十毫秒。
    `--no-cache` 一律绕过，也不写回任何记录。

    Progressive QA：qa_level=1 只看文件/元素/页数（不渲染），=2 只渲染关键页
    （`render_pages` 缺省时按 spec 自动挑选），=3（默认）全量渲染 + 全部检查。
    发布资格与证据完整是两件事：证据不全（子集渲染）→ status 降到 REVISE；
    证据齐但链不是 release（`qa_level < 3`）→ status 可为 PASS，但 `release_eligible=False`，
    因为 Release Manifest 只在发布链生成。

    raster（默认 "auto"）：光栅化格式。JPEG 快测比 PNG 快约 10×，指标偏差在远离
    判定阈值时可忽略；"auto" 会在**指标贴着阈值**的页上自动改用无损 PNG 复测，
    因此判定与全程 PNG 一致。传 "png" 可强制全程无损（取证/排障）。

    执行模式（流程控制）：mode=sketch|draft|review|release。render/qa_level 传 None
    时由 mode 档案派生（不传 mode 则维持旧行为：全量渲染、L3）。
    判断叙事已退出运行时（v4.15）：审美维度的措辞归 references/design-craft.md
    §判断基线，本函数只产契约判定与像素事实。

    normalize=True（默认）：入口先过 Normalizer（生产链第 0 级，现并入 guard.py）。
    归一化是确定性的，报告记录 hash_before/after——release_manifest 依此接受
    「原始 spec ↔ 归一化 spec」的证明链。传 False 可跳过（spec 已归一化时省一次深拷贝）。

    （v4.15 起 Critic 引擎已退出运行时：9 维判断叙事归 references/design-craft。）
    """
    import time

    pen = {**DEFAULT_PENALTIES, **(penalties or {})}
    thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    output_path = Path(output)
    t0 = time.time()

    # 0) Normalizer（生产链第 0 级）：机械偏差吸附后再进入 Guard/Compile/Render。
    #    归一化确定性 + 报告留痕（hash_before/after），发布清单据此接受证明链。
    norm_report = None
    if normalize:
        from guard import normalize_spec
        spec, norm_report = normalize_spec(spec)

    # 0.2) Smart Fit Resolver（显式 opt-in）：auto_fit:true 的文本按阶梯
    #      吸附（padding→line_height→字号），留痕；未声明者零改动（编译器仍只警告）。
    from design_intelligence import apply_fit_ladder
    spec, fit_report = apply_fit_ladder(spec)

    # 0.5) 执行模式档案：None 参数由 mode 派生；显式实参永远优先（API 兼容）
    prof = mode_profile(mode) if mode else None
    if prof:
        if render is None:
            render = prof["render"]
        if qa_level is None:
            qa_level = prof["qa_level"]
    if render is None:
        render = True
    if qa_level is None:
        qa_level = 3
    # 编译契约：spec 档（或显式 compile=False）完全不碰 pptx/compiler —— 判
    # 「spec 是否合理」是数据工作，不该付 152ms 的 import 成本。需要 PPTX 产物时
    # 用 draft（它只 import 编译层，不渲染）。
    do_compile = compile if compile is not None else bool(
        (prof or {}).get("compile", True))
    if not do_compile:
        render = False
    else:
        from compiler import compile_deck
        from render_check import compile_reuse, record_compile, spec_view

    # 0.4) 风险预测（Design Intelligence 内部的预测子模块）：产出的不是「能不能过」，
    #      而是「下一轮该怎么改」——risks + strategy 一起给出，供起草/修订消费。
    #      它不阻断任何阶段（release 也跑：预测 vs 实测的差异本身就是有用的对照）。
    risk_report = None
    try:
        from design_intelligence import pre_critic, risk_strategy
        risk_report = pre_critic(spec)
        risk_report["strategy"] = risk_strategy(spec, risk_report)
    except Exception as exc:      # 预测层失败不阻断主链（它是大脑不是门槛）
        risk_report = {"error": str(exc), "risks": [], "summary": {}, "strategy": None}

    # 渲染证据目录先定下来（编译/PDF/页级指标缓存与上一版 spec 都住在这里）
    render_dir = (Path(render_dir) if render_dir
                  else output_path.with_name(output_path.stem + "_render"))
    last_spec = (_load_last_spec(render_dir)
                 if (use_cache and do_compile) else None)

    # 1) 静态治理（guard_rules 独立传入，qa 不解读内部结构）
    t_guard = time.time()
    guard = check_spec(spec, rules=guard_rules)
    # sketch 档：只守「错」（error 级），不守「不好」（warn/hint）——探索期免除
    # 设计契约（颜色/媒体/文字合同都在 warn/hint 层），数据诚实性与结构合法性
    # 仍在（取舍序：事实与语义 > 一切，不参与降档）。
    if mode == "sketch":
        guard = {**guard, "checks": [c for c in guard.get("checks", [])
                                     if c.get("level") == "error"]}
    t_compile = time.time()

    # 2) 编译。Guard 已在本函数完成，关闭编译器内的重复静态扫描以减少一次全 deck 遍历。
    # 发布仍会在 compile_report 中保留 guard 摘要，口径由本函数唯一掌握。
    # 先问一句「像素视图变了吗」：没变就连 compile 与 soffice 都省掉（决策先于生成）。
    compile_report = None
    view = None
    if not do_compile:
        t_compile = time.time()
        compile_report = {"passed": True, "skipped": True, "warnings": [],
                          "slides": len(spec.get("slides") or []), "file_bytes": None,
                          "reason": "mode_spec_no_compile"}
    elif use_cache:
        try:
            render_dir.mkdir(parents=True, exist_ok=True)
            view = spec_view(spec, base_path=output_path.parent)
            compile_report = compile_reuse(render_dir, output_path, view)
        except Exception:
            compile_report = None
    if do_compile and compile_report is None:
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
    try:
        qa_level = max(1, min(3, int(qa_level)))
    except (TypeError, ValueError):
        qa_level = 3
    if qa_level == 1 and render:
        render, skip_render_reason = False, "qa_level_1"
    # 语义变更分类：上一版 spec → 本版 spec，哪些页需要像素复核。
    # draft 不渲染用不到；release 恒全量；只有 review 用它把渲染集缩到「变化页」。
    change_classes = classify_spec_change(last_spec, spec) if last_spec else None
    wanted_pages = None
    if render and qa_level == 2:
        if render_pages:
            # 调用方（或 route.plan_deck 的 verification.pixel_page_ids）给了页码就用它
            wanted_pages = [int(n) for n in render_pages]
        elif change_classes is not None:
            # 已知上一版：只渲染「像素真的变了」的页——改一句 insight 不重渲染，
            # 是显式决策，不是缓存副作用。纯声明修改（deck=narrative/identical）
            # 时渲染集为空，页级缓存在 review 里也就无从失效。
            wanted_pages = sorted({int(n) for n in (change_classes.get("render_needed") or [])})
        else:
            # 没有上一版可比（首次 review / 冷跑 / --no-cache）：退回关键页
            wanted_pages = key_pages(spec)
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
    # guard 的设计契约条目是「观察」——guard 侧已 advisory/权重 0，这里同样
    # 不扣分（它们与 primitives 同口径，重复扣分等于把审美写成 QA 分数）。
    hint_buckets: dict[str, dict] = {}
    for c in guard["checks"]:
        key = f"guard_{c['level']}"
        if c.get("advisory"):
            key = "design_advisory"     # 权重 0.0：只进报告，不进分数
        elif c.get("rule") == "preflight" and c["level"] == "hint":
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
        # 判定在 primitives.text_contrast_verdict 共享：跨层同一结论。
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
    status = "BLOCKED" if blocking else (
        "SKETCH" if mode == "sketch" else
        ("PREVIEW_ONLY" if not do_compile else
         ("PREVIEW_ONLY" if not evidence.get("rendered")
          else ("PASS" if passed else "REVISE"))))
    # 像素证据覆盖率决定「能不能发布」：Level 1/2（或任何子集渲染）都不给发布级结论，
    # 判定阈值一律不放宽：像素证据不全 → 不给 PASS（`PIXEL_COVERAGE_PARTIAL`）。
    # 但「发布资格」与「证据完整」是两件事：非 release 链即使本轮把 12 页
    # 全测了（页级缓存让这件事几乎免费），status 可以是 PASS，`release_eligible`
    # 仍为 False——发布需要 Release Manifest，那是 release 链独有的产物。
    coverage = evidence.get("coverage") or {}
    rendered_n = int(coverage.get("rendered_pages") or len(evidence.get("pages") or []))
    total_n = int(coverage.get("total_pages") or len(slides_count)) or 1
    partial_pixel = bool(evidence.get("rendered")) and rendered_n < total_n
    release_eligible = (status == "PASS" and rendered_n >= total_n
                        and not blocking and not partial_pixel
                        and (mode is None or qa_level >= 3))
    if status == "PASS" and partial_pixel:
        status = "REVISE"        # 证据不全才降级；证据全但链不对，只削发布资格
    if partial_pixel:
        failure_codes = sorted(set(failure_codes) | {"PIXEL_COVERAGE_PARTIAL"})
    base = ("fix: " + ", ".join(failure_codes)) if failure_codes else "ready for review"
    _risk_fix = ((risk_report or {}).get("strategy") or {}).get("generation")
    if _risk_fix:
        base += " · 先按风险策略修（design_intelligence.risk_strategy）"
    if not release_eligible and status == "PASS":
        base += " · 证据已完整，但发布需 --mode release（Release Manifest 只在发布链生成）"
    next_action = (base + " · 发布前需 qa_level=3 全量像素复核"
                   if partial_pixel else base)

    # ── 记下本版 spec，供下一轮变更分类（唯一的跨轮状态；--no-cache 不读不写；
    #    spec 档不落任何文件：它连渲染目录都不该出现）
    if use_cache and do_compile:
        _save_last_spec(render_dir, spec)

    exec_block = {
        "mode": mode,
        "compiled": do_compile,
        "profile": prof["label"] if prof else None,
        "change_classes": change_classes,
        "render_plan_pages": wanted_pages,
    }

    return {
        "qa_version": "3.2",
        # 自证戳：报告属于哪一份 spec。清单会核对，防止拿旧报告/旁路产物冒充新结果
        "source_spec_hash": spec_fingerprint(spec),
        "normalization": norm_report,
        "auto_fit": fit_report,
        # 风险预测 + 生成策略（Design Intelligence 的预测子模块；不是审核闸）
        "risk": risk_report,
        "pre_critic": risk_report,          # 兼容别名（同对象，不复制）
        "execution": exec_block,
        "verdict": _verdict_of(status, score, items, failure_codes),
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
        "failure_codes": failure_codes,
        "blocking_items": sum(1 for it in items if it.get("level") == "error"),
        "affected_slides": sorted({str(it.get("id")) for it in items if it.get("id")}),
        "next_action": next_action,
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


def release_manifest(spec: dict, qa_report: dict,
                     *, compile_report: dict | None = None, theme_id: str | None = None,
                     render_evidence_path: str | None = None,
                     revision_count: int = 0, revision_log: list | None = None,
                     verification: dict | None = None) -> dict:
    """按 production-contract.md「Release Manifest」契约确定性生成发布清单。

    状态合成规则（v4.15 单引擎）：BLOCKED/REVISE/PASS/PREVIEW_ONLY 直接取 qa_report。
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
            # V2：归一化是确定性纯函数——报告盖的是「归一化 spec」的戳时，
            # 用报告内留痕的 hash_before 建立原始 spec → 归一化 spec 的证明链。
            norm = report.get("normalization") or {}
            if norm.get("hash_before") == spec_hash and norm.get("hash_after") == got \
                    and norm.get("idempotent"):
                notes.append(f"{name} 验证的是当前 spec 的归一化形态"
                             f"（normalizer 确定性吸附 {norm.get('changed', 0)} 处），"
                             f"证明链成立")
            else:
                issues.append(f"{name} 的 source_spec_hash={got} 与当前 spec {spec_hash} 不符"
                              f"（报告来自另一版 spec，已过期或被替换）")
        elif not got:
            if claims_pass:
                issues.append(f"{name} 声称 PASS 却没有 source_spec_hash，无法证明它由当前 spec "
                              f"产出（旁路生成的报告不能作为发布证据）")
            else:
                notes.append(f"{name} 未盖 source_spec_hash（旧格式报告，仅记录不阻断）")

    _attest(qa_report, "qa_report")

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

    if qa_report.get("render_evidence"):
        _pages(qa_report["render_evidence"], "qa render_evidence")

    qa_status = str(qa_report.get("status", "BLOCKED"))
    status = qa_status          # v4.15 单引擎：QA 判定即发布判定
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
              "[--mode spec|sketch|draft|review|release] [--no-compile] "
              "[--no-normalize] [--no-render] [--fast] [--preflight] "
              "[--quick | --key-pages | --manifest | --level N] [--no-cache] "
              "[--raster auto|png|jpeg] [--json]\n"
              "  执行模式：spec=零成本档（只读 spec：不 import pptx、不编译、不渲染）· "
"      sketch=草图链（契约免除）· draft=创作链（零渲染，初稿探索）· "
              "review=审查链（只测变化页 + Critic）· release=发布链（全量+Critic+Manifest，唯一给发布资格的一档）\n"
              "  默认：不传 --mode 即 draft（零渲染秒级 + 风险预测与生成策略首屏）\n"
              "  --level N / --fast 维持 legacy 全量\n"
              "  --no-compile：任何模式下只判 spec（不写 PPTX、不 import 编译层）\n"
              "  legacy：--quick≡--mode draft · --key-pages≡--mode review · "
              "--manifest≡--mode release")
        return 1
    mod_path = Path(argv[1])
    spec_mod = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    if spec_mod is None or spec_mod.loader is None:
        print(f"qa.py: 无法加载 {mod_path}——本入口读的是 .py build 模块"
              "（定义 build_spec() 或 SPEC），不是 .json；"
              "裸 spec baseline 校验请用 --mode spec。")
        return 1
    mod = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    if spec is None:
        print("build module must define build_spec() or SPEC")
        return 1
    fast = "--fast" in argv
    # 执行模式：legacy 旗标映射为模式别名；--level N 可在模式内微调
    mode = None
    for i, a in enumerate(argv):
        if a == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1].strip().lower()
        elif a in ("--quick", "--level1"):
            mode = mode or "draft"
        elif a in ("--key-pages", "--key", "--level2"):
            mode = mode or "review"
        elif a == "--manifest":
            mode = mode or "release"
    level = None
    for i, a in enumerate(argv):
        if a == "--level" and i + 1 < len(argv):
            level = int(argv[i + 1])
    # 默认生成走创作链（draft）：不传 mode 即零渲染秒级产出可编辑 PPTX +
    # 风险预测/生成策略首屏。显式 --level N / --fast 是「明确要测」的信号，
    # 维持 legacy 全量行为，不因默认值被降级。
    if mode is None and level is None and not fast:
        mode = "draft"
    do_normalize = "--no-normalize" not in argv
    # --no-compile：只判 spec（任何模式下有效）。spec 档隐含它。
    no_compile = "--no-compile" in argv or mode == "spec"
    # --raster png|jpeg|auto：默认 auto（快测 + 临界页无损复检）
    raster = "auto"
    for i, a in enumerate(argv):
        if a == "--raster" and i + 1 < len(argv):
            raster = argv[i + 1].strip().lower()
        elif a == "--lossless":
            raster = "png"
    # 生产链第 0 级：Normalizer 在一切之前（Guard 只确认，不负责发现机械偏差）。
    # CLI 只归一化一次，后续 run_qa/critic/manifest 共用同一份归一化 spec。
    if do_normalize:
        from guard import normalize_spec
        spec, norm = normalize_spec(spec)
        # 摘要只进人类输出；--json 必须保持纯净（机器消费契约）
        if norm["changed"] and "--json" not in argv:
            rules = "、".join(f"{k}×{v}" for k, v in sorted(norm["by_rule"].items()))
            print(f"normalizer: {norm['changed']} 处机械偏差已吸附（{rules}）"
                  + ("" if norm["idempotent"] else " · 幂等校验失败！"))
    else:
        norm = None
    prof = mode_profile(mode) if mode else None
    result = run_qa(spec, argv[2],
                    render=False if "--no-render" in argv else None,
                    dpi=72 if fast else 96,
                    qa_level=level, use_cache="--no-cache" not in argv,
                    raster=raster, mode=mode, normalize=False,
                    compile=False if no_compile else None)
    if norm and result.get("normalization") is None:
        result["normalization"] = norm      # CLI 已归一化：报告仍要留痕（证明链）
    if "--preflight" in argv:
        for i in (result.get("preflight") or {}).get("items", []):
            print(f"  {i['slide']:>6} {i['code']:17s} {i['observation']}")
            print(f"          fix → {i['minimal_fix']}")
        print(f"preflight: {result['performance']['preflight_items']} 项 · "
              f"guard {result['performance']['guard_ms']}ms · "
              f"compile {result['performance']['compile_ms']}ms"
              + ("（spec 档：未编译未渲染）" if not result["execution"]["compiled"] else "") + " · "
              f"render {result['performance']['render_ms']}ms"
              + (f" (skipped: {result['performance']['render_skipped']})"
                 if result['performance']['render_skipped'] else ""))
        return 0
    want_manifest = "--manifest" in argv or (mode == "release")
    if want_manifest:
        manifest = release_manifest(spec, result)
        manifest_path = Path(argv[2]).with_suffix(".manifest.json")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        # --json 保持纯净（同 §Critic 分支守则）：manifest 落盘为凭，
        # 文本行只在人类可读模式打印 stdout，机器管道直接 json.loads 不得被污染。
        if "--json" not in argv:
            print(f"manifest: {manifest_path} (status={manifest['status']})")
        # 修订流水提示：占位 0 不再静默通过——发布链要求真实流水
        if not manifest.get("revision_count") and "--json" not in argv:
            print("hint: revision_count=0（发布清单应携带真实修订流水："
                  "observation → minimal_fix → recheck × N 轮）")
    # 风险预测 → 生成策略（首屏）：先按策略改，再谈渲染。它是决策输入，不是审核闸。
    if mode in ("sketch", "draft", "review", "release") and "--json" not in argv:
        pc = result.get("risk") or {}
        s = pc.get("summary") or {}
        strat = pc.get("strategy") or {}
        if s:
            print(f"risk-prediction: {s.get('high', 0)} high / {s.get('med', 0)} med · "
                  f"{s.get('pages_at_risk', 0)}/{s.get('total_pages', '?')} 页有风险")
            for key, val in (strat.get("adjusted") or {}).items():
                for d in val.get("deck_policies") or []:
                    print(f"  [{key}] 政策 → {d}")
            for r in (pc.get("risks") or []):
                if r.get("level") == "high":
                    print(f"  [{r['code']:22s}] {'、'.join(r['slides'])}: {r['why'][:80]}")
                    print(f"      prevent → {r['prevention'][:86]}")
        fit = result.get("auto_fit") or {}
        if fit.get("applied"):
            print(f"auto-fit: {fit['applied']} 处按阶梯吸附"
                  + (f"（{len(fit.get('needs_rewrite', []))} 处需重写文案）"
                     if fit.get("needs_rewrite") else ""))

    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        cov = (result.get("render") or {}).get("coverage") or {}
        vd = result.get("verdict") or {}
        print(f"QA verdict={vd.get('verdict')} score={result['score']}/100 "
              f"status={result['status']} "
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
