# -*- coding: utf-8 -*-
"""Layer 4 · QA — 交付验证（回答且只回答一个问题：这份 PPT 能不能交付？）

验证不是重新设计，也不重新判定风格。本层只核对可机械判定的事实：

    文件完整性 / 页数 / 元素存在性 / 文本溢出与裁切 / 缺失素材 / 内容缺失 /
    来源与口径齐全 / 明显几何失败（越界、墨迹相交、标签压字）

设计价值（层级、节奏、气质、构图是否"对"）不属于本层——那是
`references/design-craft.md` 的判断，机器不打审美分。因此本层**没有分数**，
只有三种状态：

    PASS       无阻断项，可交付
    BLOCKED    存在阻断项；`fix_plan` 按根因分组，一次改完
    PREVIEW_ONLY  spec 模式（只诊断，不产出 PPTX）

非阻断证据只聚合留痕（`trace_summary`），不构成门槛、不进入对话——Evidence ≠ Error。

技能包不依赖任何外部渲染链路：产物是原生可编辑
PPTX，视觉方向证据由 `ghost.py` 的确定性结构预览给出。一次 check =
normalize → guard → compile → 分组修复包，全程单进程、零外部依赖。
"""
from __future__ import annotations

import time
from pathlib import Path

from primitives import file_digest, spec_fingerprint

# ── 执行模式（三个已足够：诊断 / 创作 / 交付）─────────────────────────────
# 简单任务走 draft，复杂任务才需要 release 的全量收口——深度由任务赢得，
# 不是所有任务都跑最重的流程。
MODES = {
    "spec": {
        "label": "Spec · 只诊断",
        "compile": False,
        "aim": "归一化 + Guard 判定，不写 PPTX、不落任何产物；改字段时的高频自查档",
    },
    "draft": {
        "label": "Draft · 创作（默认）",
        "compile": True,
        "aim": "Guard + Compile 一次通过，产出可编辑 PPTX 与分组修复包",
    },
    "release": {
        "label": "Release · 交付",
        "compile": True,
        "aim": "draft 的全部 + 数值图表出处硬门 + 结构与预览证据 + Release Manifest",
    },
}
DEFAULT_MODE = "draft"


def mode_profile(mode: str | None) -> dict:
    """未知/空 mode 一律回落 draft（少一个决策点，行为可预测）。"""
    key = str(mode or "").strip().lower() or DEFAULT_MODE
    prof = MODES.get(key)
    if prof is None:
        key, prof = DEFAULT_MODE, MODES[DEFAULT_MODE]
    return {"mode": key, **prof}


_RULE_CODES = {
    "overlap": "OVERLAP", "source_zone": "SOURCE_COLLISION",
    "chart_label_collision": "CHART_LABEL_COLLISION",
    "text_capacity": "TEXT_OVERFLOW", "contrast": "READABILITY_FAIL",
    "data_integrity": "DATA_INTEGRITY_FAIL",
    "data_provenance": "DATA_INTEGRITY_FAIL",
    "chart_type": "CHART_TYPE_FAIL",
    "safety": "GUARD_FAIL",
}

# ── 修复包（报告自足性）───────────────────────────────────────────────────
# 阻断码 → 首修动作 + 内嵌契约行。目标：修正轮照单一次改完，零文档回读。
FIX_CONTRACT_HINTS = {
    "OVERLAP": "文本/图表/图片/来源区墨迹不相交；挪几何或删元素，不缩字号。"
               "契约行：所有可见对象数值 x/y/width/height；墨迹相交即 OVERLAP。",
    "SOURCE_COLLISION": "来源区（source_zone）内只放 role∈{source,method,metadata} 的文字，"
                        "任何可见对象不得侵入。契约行：来源区永不许遮挡。",
    "CHART_LABEL_COLLISION": "用 label_collision_policy:hide_redundant|move_outside|fail 处置，"
                             "不缩字号。契约行：图表标签放不下用 policy。",
    "TEXT_OVERFLOW": "框高 ≥ 字号×行高×行数；减行数/减字数/加框高，三选一。"
                     "契约行：text 放内容，样式平铺顶层。",
    "READABILITY_FAIL": "声明色对比不足：加深文字色或加遮罩/底衬，不动构图。"
                        "契约行：正文 ≥4.5:1，任何角色 ≥3:1。",
    "DATA_INTEGRITY_FAIL": "每行 label + 有限 value；factual numeric chart 齐 "
                           "source/unit/period/basis。契约行：数据不可为构图造假。",
    "CHART_TYPE_FAIL": "图表类型在白名单内且数据形态匹配（占比≠趋势）。",
    "COMPILE_FAIL": "编译诊断给出具体元素与字段；按 warnings 修 schema，不绕过 Guard。",
    "GUARD_FAIL": "按 checks 中 error 级条目逐项修；element_schema/focus/几何合法性优先。",
}

# 状态由「有无阻断」决定；这些码是阻断性失败码集合。
BLOCKING_CODES = {"OVERLAP", "SOURCE_COLLISION", "CHART_LABEL_COLLISION",
                  "TEXT_OVERFLOW", "READABILITY_FAIL", "DATA_INTEGRITY_FAIL",
                  "CHART_TYPE_FAIL", "COMPILE_FAIL", "GUARD_FAIL", "ASSET_WORKFLOW_FAIL"}


def _rule_to_code(rule) -> str:
    return _RULE_CODES.get(rule, "GUARD_FAIL")


def build_fix_plan(failure_codes, guard_checks, compile_report) -> dict:
    """阻断项按根因分组：{root_cause, count, ids, samples, fix}。确定性、零新依赖。"""
    by_code: dict[str, dict] = {}

    def _g(code: str) -> dict:
        return by_code.setdefault(code, {"root_cause": code, "count": 0,
                                         "ids": [], "samples": []})

    for chk in guard_checks or []:
        if not isinstance(chk, dict) or chk.get("level") != "error":
            continue
        g = _g(_rule_to_code(chk.get("rule")))
        g["count"] += 1
        pid = str(chk.get("id") or "")
        if pid and pid not in g["ids"]:
            g["ids"].append(pid)
        if len(g["samples"]) < 3 and chk.get("msg"):
            g["samples"].append(str(chk["msg"])[:160])
    if isinstance(compile_report, dict) and not compile_report.get("passed", False) \
            and not compile_report.get("skipped"):
        g = _g("COMPILE_FAIL")
        g["count"] += 1
        for w in (compile_report.get("warnings") or [])[:3]:
            g["samples"].append(str(w)[:160])
    for code in failure_codes or []:
        if code in ("COMPILE_FAIL", "GUARD_FAIL"):
            continue          # 只在有真实条目时成组，空组只会稀释信号
        _g(code)
    groups = []
    for code in list(failure_codes or []) + [c for c in by_code if c not in (failure_codes or [])]:
        g = by_code.get(code)
        if g is None:
            continue
        if not g["count"] and code in ("COMPILE_FAIL", "GUARD_FAIL"):
            continue
        g["fix"] = FIX_CONTRACT_HINTS.get(code, "见 production-contract.md Contract Map 对应行")
        if not g["count"]:
            g["count"] = 1     # 至少一处根因待处理，不向 Agent 暴露误导性的 ×0
        if g not in groups:
            groups.append(g)
    return {"round_budget": "本轮一次修完全部组，修完直接复跑同档（每阶段 1 个修正轮；"
                            "零文档回读，修法以内嵌契约行为准）",
            "groups": groups}


def build_trace_summary(items) -> list:
    """非阻断项按 (domain, rule, level) 聚合：记录在案，不构成门槛、不逐条刷屏。

    聚合保留**可执行信息**：样本原文（不截短到看不懂）与涉及的元素 id。
    warning 不进对话，但当作者说「PASS 了，再打磨一轮」时，这份清单就是
    打磨的输入——没有 id 和原文的清单，只能告诉人「有问题」，不能告诉人「改哪」。
    """
    agg: dict[tuple, dict] = {}
    order: list[tuple] = []
    for it in items or []:
        if it.get("level") not in ("warn", "hint"):
            continue
        key = (it.get("domain"), it.get("rule"), it.get("level"))
        if key not in agg:
            agg[key] = {"domain": key[0], "rule": key[1], "level": key[2],
                        "count": 0, "ids": [], "samples": []}
            order.append(key)
        bucket = agg[key]
        bucket["count"] += int(it.get("count") or 1)
        for cid in ([it["id"]] if it.get("id") else []) + list(it.get("ids") or []):
            cid = str(cid)
            if cid and cid not in bucket["ids"] and len(bucket["ids"]) < 8:
                bucket["ids"].append(cid)
        for sample in ([it["msg"]] if it.get("msg") else []) + list(it.get("samples") or []):
            sample = str(sample)[:200]
            if sample not in bucket["samples"] and len(bucket["samples"]) < 3:
                bucket["samples"].append(sample)
    return [agg[k] for k in order]


def release_guard_rules(mode: str | None, guard_rules: dict | None = None) -> dict:
    """release 档的 Guard 证据要求（唯一真源）：数值图表出处升为硬门。"""
    rules = dict(guard_rules or {})
    if mode == "release" and "require_provenance" not in rules:
        rules["require_provenance"] = True
    return rules


def verdict(spec: dict, output: str | Path, *, mode: str | None = None,
            guard_report: dict, compile_report: dict,
            speed: str = "strict",
            runtime_facts: dict | None = None) -> dict:
    """判定层：**只消费报告**（guard_report + compile_report），不编译、不读产物字节。

    编排归调用方（vao：normalize → guard → compile → 预览 → 本函数 → 清单）。
    这条边界是 2026-09 审核定下的：QA 一旦自己触发编译，产物就可能在
    「判定输入的见证」之外被重建，职责也从「归因」滑向「生产」。
    """
    t0 = time.time()
    speed = "fast" if str(speed or "").strip().lower() == "fast" else "strict"
    prof = mode_profile(mode)
    mode = prof["mode"]
    facts = dict(runtime_facts or {})
    output_path = Path(output)
    do_compile = bool(prof["compile"])
    guard = guard_report if isinstance(guard_report, dict) else {}
    if not isinstance(spec, dict):
        # API 边界也要给出可消费的判定，而不是把 AttributeError 泄漏给调用方；
        # guard 仍是唯一的 schema 真源（它在编排层跑过，报告在这里被消费）。
        spec = {"slides": [], "_input_error": "spec 顶层必须是对象/dict"}
    guard_errors = [c for c in guard.get("checks", []) if c.get("level") == "error"]
    provenance_required = bool(facts.get("provenance_required", False))
    compile_warnings = list(compile_report.get("warnings", []))

    # 4) 判定：只有阻断项改变状态；分数与警告都不参与。
    items: list[dict] = []
    hint_buckets: dict[str, dict] = {}
    for c in guard.get("checks", []):
        if c.get("level") == "hint":
            # 聚合是为了不刷屏，不是为了**丢掉可执行的话**。此前这里把每条 hint
            # 的正文替换成 “{rule} 微调提示（详见 guard.checks）”——而 guard.checks
            # 根本不在修复包里（packet 只有 fix_plan / trace_summary），
            # 于是打磨阶段拿到的是一句「去看一个你看不到的东西」。
            # 现在：仍然按 rule 聚合计数，但保留真实样本与元素 id，
            # 让「PASS 之后再打磨一轮」有据可依。
            b = hint_buckets.setdefault(c["rule"], {
                "domain": "guard", "level": "hint", "rule": c["rule"], "id": None,
                "count": 0, "ids": [], "samples": []})
            b["count"] += 1
            cid = str(c.get("id") or "")
            if cid and cid not in b["ids"] and len(b["ids"]) < 8:
                b["ids"].append(cid)
            if c.get("msg") and len(b["samples"]) < 3:
                b["samples"].append(str(c["msg"])[:200])
            continue
        items.append({"domain": "guard", "level": c["level"], "rule": c["rule"],
                      "id": c.get("id"), "msg": c.get("msg")})
    for b in hint_buckets.values():
        b["msg"] = b["samples"][0] if b["samples"] else f"{b['rule']} 微调提示"
    items.extend(hint_buckets.values())
    # 编译期警告带上元素 id（compiler 记在等长的 warning_ids 里）——
    # 没有 id 的 fix_plan 分组只能说「有问题」，说不出「改哪个」。
    compile_warning_ids = list(compile_report.get("warning_ids") or [])
    for idx, w in enumerate(compile_warnings):
        wid = compile_warning_ids[idx] if idx < len(compile_warning_ids) else None
        items.append({"domain": "compile", "level": "warn", "rule": "compiler",
                      "id": wid, "msg": w})

    failure_codes: list[str] = []
    for check in guard.get("checks", []):
        if check.get("level") != "error":
            continue
        code = _rule_to_code(check.get("rule"))
        if code not in failure_codes:
            failure_codes.append(code)
    if any(check.get("level") == "error" for check in guard.get("checks")) \
            and "GUARD_FAIL" not in failure_codes:
        failure_codes.append("GUARD_FAIL")
    if not compile_report.get("passed", False):
        failure_codes.append("COMPILE_FAIL")
    blocking_codes = [c for c in failure_codes if c in BLOCKING_CODES]
    blocking_items = [it for it in items if it.get("level") == "error"]
    passed = not blocking_codes
    status = ("BLOCKED" if blocking_codes else
              "PREVIEW_ONLY" if not do_compile else "PASS")
    release_eligible = bool(status == "PASS" and mode == "release"
                            and compile_report.get("passed"))
    next_action = ("fix: " + ", ".join(failure_codes)) if failure_codes else "ready"
    if status == "PASS" and mode != "release":
        next_action = "ready · 交付前用 --mode release 收口（结构与预览证据 + Manifest）"

    result = {
        "qa_version": "5.0",
        # 自证戳：报告属于哪一份 spec（Normalizer 确定性吸附的证明链见 normalization）
        "source_spec_hash": spec_fingerprint(spec),
        "normalization": facts.get("normalization"),
        "execution": {"entrypoint": "vao.py", "mode": mode, "profile": prof["label"],
                      "speed": speed,
                      "compiled": do_compile, "provenance_required": provenance_required,
                      "external_renderer": "disabled",
                      "visual_evidence": "ghost_preview"},
        # §21 三态词汇：BLOCK（阻断发布）/ PASS（无阻断）/ TRACE（只记录证据，
        # 不触发修复、不进入对话）。这里不再出现模糊的 "warnings" 计数。
        "verdict": {"verdict": "BLOCKED" if blocking_codes else "PASS",
                    "status": status,
                    "blocking": len(blocking_items),
                    "trace": len([i for i in items if i.get("level") in ("warn", "hint")]),
                    "codes": failure_codes,
                    "question": "这份 PPT 能不能交付？"},
        "status": status,
        "passed": passed,
        "release_eligible": release_eligible,
        "blocking_items": len(blocking_items),
        "failure_codes": failure_codes,
        "affected_slides": sorted({str(it.get("id")) for it in blocking_items if it.get("id")}),
        "guard": {"checks": len(guard.get("checks", [])),
                  "errors": len(guard_errors)},
        "compile": {"passed": compile_report.get("passed"),
                    "skipped": compile_report.get("skipped"),
                    "reason": compile_report.get("reason"),
                    "performance": compile_report.get("performance"),
                    "trace": len(compile_warnings),
                    "slides": compile_report.get("slides"),
                    "file_bytes": compile_report.get("file_bytes"),
                    "semantic_compile_view": compile_report.get("semantic_compile_view"),
                    # 产物只有一个身份：output_sha256（此前还并存一个同值的
                    # artifact_sha256，同一事实存两遍，没有任何消费者）。
                    "output_sha256": compile_report.get("output_sha256"),
                    "output_path": compile_report.get("output_path"),
                    # 见证身份（size+mtime）：清单据此判断要不要重复整包哈希
                    "output_size": compile_report.get("output_size"),
                    "output_mtime_ns": compile_report.get("output_mtime_ns"),
                    "attestation_mode": compile_report.get("attestation_mode")},
        "fix_plan": build_fix_plan(failure_codes, guard.get("checks") or [], compile_report),
        "trace_summary": build_trace_summary(items),
        "next_action": next_action,
        "performance": {
            **{k: facts.get(k) for k in ("total_ms", "guard_ms", "compile_ms", "attestation_ms",
                                         "cache_reason", "cache_enabled", "cache_dir")},
            "speed_profile": speed,
            "slides": len(spec.get("slides") or []),
            "compile_reused": bool(compile_report.get("reused")),
        },
        "elapsed_ms": int(facts.get("total_ms") or int((time.time() - t0) * 1000)),
    }
    result["_effective_spec"] = spec  # consumed by vao before report serialization
    return result


def fail_result(result: dict, problems: list[str], code: str = "GUARD_FAIL") -> dict:
    result.update(status="BLOCKED", passed=False, release_eligible=False)
    codes = result.setdefault("failure_codes", [])
    if code not in codes:
        codes.append(code)
    result["blocking_items"] = result.get("blocking_items", 0) + len(problems)
    result.setdefault("verdict", {}).update(verdict="BLOCKED", status="BLOCKED",
        blocking=result["blocking_items"], codes=codes)
    result.setdefault("fix_plan", {}).setdefault("groups", []).append({
        "root_cause": code, "ids": [], "count": len(problems), "samples": problems,
        "fix": "；".join(problems)})
    result["next_action"] = "fix: " + "；".join(problems)
    return result


def preview_issues(ghost: dict | None, page_ids: list[str]) -> list[str]:
    """Verify actual preview bytes, not only self-reported counts.

    `scope="sampled"`（v5.9 快速档）：预览按方向采样（封面 / 最复杂页 / 图片页 /
    收尾），此时要求「声明的采样页 == 实际渲染页 == 文件数」，且每一页都在当前
    稿件的页集合内。采样是**声明的证据范围**，不是缺失的证据——清单上写清
    `evidence_scope`，就不允许再冒充全量覆盖。
    """
    if not isinstance(ghost, dict):
        return ["缺少方向预览证据"]
    pages = ghost.get("pages") or []
    scope = str(ghost.get("scope") or "full")
    if scope == "sampled":
        expected = [str(x) for x in (ghost.get("sampled_ids") or [])]
        actual = [str(x) for x in (ghost.get("slide_ids") or [])]
        if (not expected or expected != actual or ghost.get("count") != len(expected)
                or len(pages) != len(expected) or len(set(pages)) != len(pages)):
            return ["采样预览的声明页与实际渲染页不一致（采样范围必须可核对）"]
        outside = [x for x in expected if x not in {str(p) for p in page_ids}]
        if outside:
            return ["采样预览引用了当前稿件之外的页面：" + "、".join(outside)]
    elif (ghost.get("slide_ids") != page_ids or ghost.get("count") != len(page_ids)
            or len(pages) != len(page_ids) or len(set(pages)) != len(pages)):
        return ["预览页 ID/数量没有完整覆盖当前稿件"]
    hashes = ghost.get("file_sha256") or {}
    files = pages + [ghost.get("contact_sheet")]
    issues = []
    for path in files:
        if not path or not hashes.get(str(path)) or file_digest(path) != hashes.get(str(path)):
            issues.append(f"预览文件缺失/被修改或缺少字节凭证: {path}")
    return issues


def release_manifest(spec: dict, qa_report: dict, *, compile_report: dict | None = None,
                     theme_id: str | None = None,
                     ghost_preview: dict | None = None,
                     revision_count: int = 0, revision_log: list | None = None,
                     verification: dict | None = None) -> dict:
    """按 production-contract.md「Release Manifest」契约确定性生成发布清单。

    清单是发布边界的最后一道证明：声称 PASS 的报告必须能被追溯到当前 spec，
    且编译产物字节戳与磁盘一致；预览证据引用的页面必须都在当前 spec 里。

    产物核对分两级（v5.9）：
      * **同进程 stat 守卫**：本轮刚读出的字节戳 + size/mtime 未变化 ⇒ 直接采信
        （q_report.attestation 已证明过这份字节，再哈希一次不增加任何安全性）；
      * **重哈希**：stat 与见证不一致、或报告来自别处 ⇒ 老实重读整包再核对。
    快路径不是漏检路径：任何不一致都会落回慢路径。
    """
    from datetime import datetime, timezone

    input_issue = None
    if not isinstance(spec, dict):
        input_issue = "spec 顶层必须是对象/dict"
        spec = {}
    if not isinstance(qa_report, dict):
        qa_report = {}
    spec_hash = spec_fingerprint(spec)
    issues: list[str] = [input_issue] if input_issue else []
    notes: list[str] = []
    slides = spec.get("slides") if isinstance(spec.get("slides"), list) else []
    page_ids = {str(s.get("id")) for s in slides if isinstance(s, dict) and s.get("id")}

    def _attest(report: dict | None, name: str) -> None:
        if not isinstance(report, dict) or not report:
            return
        claims_pass = str(report.get("status", "")).upper() == "PASS"
        got = report.get("source_spec_hash")
        if got and got != spec_hash:
            norm = report.get("normalization") or {}
            if norm.get("hash_before") == spec_hash and norm.get("hash_after") == got \
                    and norm.get("idempotent"):
                notes.append(f"{name} 验证的是当前 spec 的归一化形态"
                             f"（确定性吸附 {norm.get('changed', 0)} 处），证明链成立")
            else:
                issues.append(f"{name} 的 source_spec_hash={got} 与当前 spec {spec_hash} 不符"
                              "（报告来自另一版 spec）")
        elif not got and claims_pass:
            issues.append(f"{name} 声称 PASS 却没有 source_spec_hash，无法证明它由当前 spec 产出")

    _attest(qa_report, "qa_report")

    ghost = ghost_preview if isinstance(ghost_preview, dict) else None
    if ghost:
        ghost_pages = {str(Path(str(p)).stem) for p in (ghost.get("pages") or [])}
        ghost_ids = {str(x) for x in (ghost.get("slide_ids") or []) if x is not None}
        seen = ghost_ids or ghost_pages
        ghosted = sorted(x for x in seen if page_ids and x not in page_ids)
        if ghosted:
            issues.append("预览证据引用了当前 spec 之外的页面：" + "、".join(ghosted))
        if ghost.get("count") and len(ghost.get("pages") or []) < len(slides):
            notes.append(f"预览只覆盖 {ghost.get('count')}/{len(slides)} 页（--pages 子集），"
                         "结构判定不受影响")

    compile_claim = qa_report.get("compile")
    if isinstance(compile_claim, dict):
        output_path, output_sha = compile_claim.get("output_path"), compile_claim.get("output_sha256")
        if output_path or output_sha:
            if not output_path or not output_sha:
                issues.append("qa_report 的 PPTX 凭证不完整：需要 output_path 与 output_sha256")
            else:
                witnessed = (int(compile_claim.get("output_size") or -1),
                             int(compile_claim.get("output_mtime_ns") or -1))
                try:
                    stat = Path(output_path).stat()
                except (OSError, TypeError, ValueError):
                    stat = None
                if stat is not None and witnessed == (stat.st_size, stat.st_mtime_ns):
                    notes.append("产物字节戳由同一轮统计见证（size+mtime 未变），未重复整包哈希")
                else:
                    try:
                        # 凭证已经移动过 ⇒ 必须重算（file_digest 只在同一份字节上复用，
                        # 这里字节已变，同库唯一实现会真的读一遍）。
                        if file_digest(output_path) != output_sha:
                            issues.append("qa_report 的 PPTX output_sha256 与文件当前内容不一致")
                        else:
                            notes.append("产物字节戳在读取后发生变化，已重新整包哈希核对")
                    except (OSError, TypeError, ValueError):
                        issues.append(f"qa_report 的 PPTX output_path 不可读取: {output_path}")
    if str(qa_report.get("status", "")).upper() == "PASS":
        if not qa_report.get("release_eligible"):
            issues.append("qa_report 声称 PASS 但 release_eligible=false")
        if str((qa_report.get("execution") or {}).get("mode", "")).lower() != "release":
            issues.append("qa_report 声称 PASS 但 execution.mode 不是 release")
        if not isinstance(compile_claim, dict) or not compile_claim.get("passed"):
            issues.append("qa_report 声称 PASS 但 compile.passed 不为 true")
    ver = {"external_renderer": "disabled",
           "visual_evidence": "ghost_preview" if ghost else "structural_only",
           "visual_evidence_scope": (ghost or {}).get("scope", "full") if ghost else None,
           "structural_pages": len(page_ids),
           "ghost_pages": (ghost or {}).get("count") if ghost else 0,
           "speed": (qa_report.get("execution") or {}).get("speed"),
           "release_eligible": bool(qa_report.get("release_eligible"))}
    if isinstance(verification, dict):
        ver.update(verification)
    workflow = qa_report.get("asset_workflow") or {}
    # 「本稿有没有图」首先消费资产链已经算好的 image_count（同一事实只判一次）；
    # 工作流没跑过 / 没带计数时，才退回对 spec 的本地扫描——那是「有图却没
    # 核验」的兜底证明，不是常规路径。（v7.2.1 审计：此前这里对同一份 spec
    # 再扫一遍 image_elements，与 verify_chain 的扫描重复。）
    image_count = workflow.get("image_count")
    if image_count is None:
        from asset_workflow import image_elements
        image_count = sum(1 for _ in image_elements(spec))
    if image_count and workflow.get("status") != "PASS":
        issues.append("含图稿件缺少通过的 asset_workflow；不能把编译PASS当成资产流程PASS")
    if qa_report.get("passed"):
        issues.extend(preview_issues(ghost, [str(s.get("id")) for s in slides]))
    status = "BLOCKED" if issues else str(qa_report.get("status", "BLOCKED"))
    ver["release_eligible"] = bool(status == "PASS" and qa_report.get("release_eligible"))
    try:
        revision_num = int(revision_count)
    except (TypeError, ValueError, OverflowError):
        revision_num = 0
    return {
        "run_id": qa_report.get("run_id"),
        "source_spec_hash": spec_hash,
        "validation": {"issues": issues, "notes": notes, "page_count": len(page_ids)},
        "theme_id": theme_id or ((spec.get("theme") or {}).get("id")
                                  if isinstance(spec.get("theme"), dict) else None),
        "slide_count": len(slides),
        # 交付资格在顶层也出现一次：读 manifest 的人不会因为少看一层而误判可交付。
        # 两处必须是同一个值（ver 是唯一计算处）。
        "release_eligible": ver["release_eligible"],
        "asset_workflow": workflow,
        "verification": ver,
        "compile_report": compile_report or qa_report.get("compile"),
        "qa_report": qa_report,
        "ghost_preview": {"dir": (ghost or {}).get("dir"),
                          "contact_sheet": (ghost or {}).get("contact_sheet")} if ghost else None,
        "revision_count": revision_num,
        "revision_log": list(revision_log or []) if isinstance(revision_log, (list, tuple)) else [],
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
