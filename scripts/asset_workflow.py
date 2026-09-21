"""Asset-chain integrity helpers; internal module, production entry is vao.py.

Content hashes bind brief -> saved plan -> manifest -> inspected bytes -> deck.
These are local provenance checks, not signatures or proof of an external model call.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from primitives import file_digest   # 全库唯一实现；本模块 re-export 给 vao

ACCEPTED = {"accept", "accept_with_advisory"}
ASSET_DECISIONS = {"generate", "existing"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def digest(value) -> str:
    """记录级摘要（清单 / 计划 / 协议值）：唯一实现在 primitives.identity。

    传 schema=None 保持与历史值逐字节一致——既有清单里存着的摘要不会因为这次
    统一而失效。缓存键请改用带 schema 的身份，别复用记录摘要的键空间。
    """
    from primitives import identity
    return identity(value)


def read_json(path) -> dict:
    """读 JSON：同一份文件在一轮执行里只解析一次（size+mtime_ns 守卫）。

    plan.json（50KB）与 manifest 在一轮 check 里各被三层读；缓存只改变读取次数，
    不改变可见性——文件一变，stamp 就不匹配，照旧重读。
    """
    from primitives import json_read_cached
    return json_read_cached(path)


def asset_entries(manifest: dict) -> list[dict]:
    entries = [e for e in manifest.get("assets", []) if isinstance(e, dict)
               and e.get("decision") in ASSET_DECISIONS]
    ids = [e.get("asset_id") for e in entries]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("资产清单的主条目必须有唯一 asset_id；reuse_generated 不算主条目")
    return entries


def asset_root(manifest: dict, manifest_path, override=None) -> Path:
    parent = Path(manifest_path).expanduser().resolve().parent
    value = override or manifest.get("assets_dir") or manifest.get("output_dir")
    if not value:
        return parent
    root = Path(value).expanduser()
    # CLI override is relative to cwd; stored paths are relative to the manifest.
    return (root.resolve() if override or root.is_absolute() else (parent / root).resolve())


VOLATILE_PLAN_KEYS = ("workflow", "performance")  # 时间戳 / 本轮耗时：入指纹 = 每次重跑都失效

def stable_plan_sha(plan: dict) -> str:
    """plan 指纹只含内容、不含运行态。workflow（planned_at/plan_path）与 performance
    （planning_ms）入指纹的实测代价：仅重跑 R1 就让骨架指纹失效，作者被迫手动同步 sha。"""
    return digest({k: v for k, v in (plan or {}).items() if k not in VOLATILE_PLAN_KEYS})


def resolve_asset(entry: dict, manifest: dict, manifest_path, override=None) -> Path:
    root = asset_root(manifest, manifest_path, override)
    if entry.get("decision") == "existing":
        raw = (entry.get("origin") or {}).get("path")
        if not raw:
            raise ValueError(f"existing 资产缺 origin.path: {entry.get('asset_id')}")
        p = Path(raw).expanduser()
        return p.resolve() if p.is_absolute() else (Path(manifest_path).expanduser().resolve().parent / p).resolve()
    filename = Path(str(entry.get("expected_filename") or f"{entry['asset_id']}.png"))
    if filename.is_absolute() or ".." in filename.parts:
        raise ValueError("生成资产文件名必须位于 assets_dir 内，不能使用绝对路径或 ..")
    candidate = root / filename
    def confined(path):
        resolved = path.resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise ValueError("生成资产最终路径逃逸 assets_dir（含符号链接）")
        return resolved
    confined(candidate)
    if candidate.is_file():
        return confined(candidate)
    alternatives = [candidate.with_suffix(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")
                    if candidate.with_suffix(ext).is_file()]
    if len(alternatives) > 1:
        raise ValueError(f"同一 asset_id 有多个候选文件，请明确 expected_filename: {entry['asset_id']}")
    return confined(alternatives[0] if alternatives else candidate)


def prepare_manifest(manifest: dict, need: dict, bundle: dict, brief_path,
                     plan_path, manifest_path, assets_dir=None) -> dict:
    """Called by assets (and run --assets-out) after a plan is saved."""
    wf = bundle.get("workflow") or {}
    if not wf or wf.get("brief_sha256") != digest(need) or digest(bundle.get("need")) != digest(need):
        raise ValueError("ASSET_WORKFLOW_FAIL: plan 与当前 brief 不匹配或缺少流程凭证；先重新执行 vao.py plan")
    if not plan_path or not Path(plan_path).expanduser().is_file():
        raise ValueError("ASSET_WORKFLOW_FAIL: assets 需要先保存的 plan.json")
    if digest(read_json(plan_path)) != digest(bundle):
        raise ValueError("ASSET_WORKFLOW_FAIL: 磁盘 plan 与内存 plan 不一致")
    if assets_dir:
        manifest["assets_dir"] = str(Path(assets_dir).expanduser().resolve())
    manifest["schema"] = "vao-assets-v2"
    manifest["workflow"] = {
        "schema": "vao-asset-chain-v1", "prepared_at": now(),
        "brief_path": str(Path(brief_path).expanduser().resolve()), "brief_sha256": digest(need),
        "brief_file_sha256": wf.get("brief_file_sha256"),
        "plan_path": str(Path(plan_path).resolve()), "plan_sha256": stable_plan_sha(bundle),
        "prompt_builder": "asset_prompt.build_asset_prompt",
    }
    for entry in asset_entries(manifest):
        if entry["decision"] != "generate":
            continue
        path = resolve_asset(entry, manifest, manifest_path)
        if file_digest(path) is None:
            continue  # 尚未出图：保持 generate，等外部工具按清单出图
        # prepare 时字节已存在：如实登记为 existing（不补造生成历史），
        # 保留规划身份与 prompt/negative；QC 照常做像素与角色核验。
        # 实测回环成本：「出图 → 重跑 R1 → QC 阻断 → 补登记 → 再重跑」= 3+ 次调用；
        # 登记在 prepare 一步完成，链路凭证同样诚实（origin.source 写明自动登记）。
        entry["decision"] = "existing"
        entry["origin"] = {"kind": "original", "path": str(path),
                           "source": "manifest prepare 时字节已存在，自动登记（规划身份保留）"}
    return manifest


def verify_sources(manifest: dict) -> list[str]:
    wf = manifest.get("workflow") or {}
    problems = []
    if manifest.get("schema") != "vao-assets-v2" or wf.get("schema") != "vao-asset-chain-v1":
        return ["缺少 v2 资产链凭证；旧清单须从 brief → plan → assets 重新建立"]
    try:
        # Verification never executes a Python brief, even when the explicit plan command did.
        plan = read_json(wf["plan_path"])
        raw_hash = file_digest(wf["brief_path"])
        if not raw_hash or raw_hash != wf.get("brief_file_sha256"):
            problems.append("brief 文件已变更或缺少原始文件凭证；重新 plan → assets → QC")
        if digest(plan.get("need")) != wf.get("brief_sha256"):
            problems.append("计划中的需求快照与 brief 内容凭证不一致")
        if stable_plan_sha(plan) != wf.get("plan_sha256"):
            problems.append("plan 已变更；重新 assets → QC")
        if (plan.get("workflow") or {}).get("brief_sha256") != wf.get("brief_sha256"):
            problems.append("plan 与 brief 指纹不一致")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems.append(f"无法核对 brief / plan: {exc}")
    return problems


def image_elements(spec: dict):
    slides = spec.get("slides")
    if not isinstance(slides, list):
        raise ValueError("spec.slides 必须是数组")
    for slide in slides:
        if not isinstance(slide, dict) or not isinstance(slide.get("elements", []), list):
            raise ValueError("每页须为对象，elements 须为数组")
        for e in slide.get("elements", []):
            if not isinstance(e, dict):
                raise ValueError("elements 内每项须为对象")
            if e.get("type") == "image":
                yield str(slide.get("id")), e


def plan_issues(spec: dict, plan: dict) -> list[str]:
    expected = [str(p.get("id")) for p in (plan.get("plan") or {}).get("pages", [])]
    actual = [str(p.get("id")) for p in spec.get("slides", [])]
    return ([] if expected and actual == expected else
            [f"交付页 ID/顺序未覆盖当前计划：planned={expected}, actual={actual}；须更新计划而非静默缺页"])


# 资产 QC 报告的 schema：核对方声明契约，写入方（vao）引用同一个常量。
# v4：每个资产的字节凭证统一为 witness{size, mtime_ns, sha256}（此前是三个平铺字段）。
QC_REPORT_SCHEMA = "vao-asset-qc-v4"


def _inspected_bytes_current(path: Path, inspected: dict) -> bool:
    """QC 记录里的字节凭证是否仍与磁盘一致（判据只有一处：primitives.witness_matches）。

    缺凭证（旧 QC 报告）一律返回 False → 重读图片。快路径只在能被证明时生效。
    """
    from primitives import stat_witness, witness_matches
    record = inspected.get("witness")
    if not isinstance(record, dict):
        return False
    size, mtime_ns = stat_witness(path)
    return witness_matches(record, {"size": size, "mtime_ns": mtime_ns})


def verify_chain(spec: dict, manifest_path=None, qc_path=None, assets_dir=None,
                 image_bytes: dict | None = None, digests: dict | None = None) -> dict:
    """资产链核验。`digests` 是本轮已算过的图片摘要（QC 算过的），命中即不再重算。"""
    images = list(image_elements(spec))
    if not images:
        contract = spec.get("asset_workflow") or {}
        problems = []
        if manifest_path:
            manifest = read_json(manifest_path)
            problems.extend(verify_sources(manifest))
            plan = read_json(manifest["workflow"]["plan_path"])
            if contract.get("plan_sha256") != stable_plan_sha(plan):
                problems.append("纯原生稿件的计划凭证不一致")
            problems.extend(plan_issues(spec, plan))
        elif contract:
            if not contract.get("plan_path"):
                problems.append("有计划凭证但缺 plan_path；重新生成骨架或提供资产清单")
            else:
                plan = read_json(contract["plan_path"])
                if contract.get("plan_sha256") != stable_plan_sha(plan):
                    problems.append("计划已变更，请更新骨架")
                problems.extend(plan_issues(spec, plan))
                wf = plan.get("workflow") or {}
                if not wf.get("brief_file_sha256") or file_digest(wf.get("brief_path")) != wf["brief_file_sha256"]:
                    problems.append("计划引用的 brief 文件已变更或缺少凭证")
        return {"status": "BLOCKED" if problems else "SKIPPED", "issues": problems,
                "reason": "no_image_elements", "image_count": 0,
                "scope": "native_text_shapes_charts_only"}
    report = {"status": "BLOCKED", "image_count": len(images), "issues": [],
              "scope": "local_content_hash_chain_not_generator_attestation"}
    issues = report["issues"]
    if not manifest_path:
        issues.append("含图片的稿件必须传 --assets-manifest；不能用直接 src 绕过资产清单")
        return report
    try:
        path = Path(manifest_path).expanduser().resolve()
        manifest = read_json(path)
        issues.extend(verify_sources(manifest))
        issues.extend(plan_issues(spec, read_json(manifest["workflow"]["plan_path"])))
        expected_plan = (spec.get("asset_workflow") or {}).get("plan_sha256")
        actual_plan = (manifest.get("workflow") or {}).get("plan_sha256")
        if not expected_plan or expected_plan != actual_plan:
            # 骨架里那份指纹在重跑 plan 之后必然过期，而它长得和真的一样——
            # 报「不匹配」而不说该看哪儿，只会逼人去读源码。把权威位置直接报出来。
            issues.append(
                "SPEC.asset_workflow.plan_sha256 缺失或与资产清单不匹配。权威值在 "
                f"{path.name} → workflow.plan_sha256"
                + (f"（当前 {actual_plan}）" if actual_plan else "")
                + "；把它整段抄进 SPEC.asset_workflow，或重新执行 plan 生成新骨架")
        entries = {e["asset_id"]: e for e in asset_entries(manifest)}
        qpath = Path(qc_path).expanduser().resolve() if qc_path else path.with_name(path.stem + ".qc.json")
        qc = read_json(qpath)
        report.update(manifest=str(path), manifest_sha256=digest(manifest),
                      qc_report=str(qpath), qc_sha256=digest(qc),
                      plan_sha256=(manifest.get("workflow") or {}).get("plan_sha256"),
                      brief_sha256=(manifest.get("workflow") or {}).get("brief_sha256"))
        if qc.get("schema") != QC_REPORT_SCHEMA or qc.get("manifest_sha256") != digest(manifest):
            issues.append("QC 缺少指纹或来自旧资产清单；重新 asset-qc")
        if qc.get("status") != "PASS" or any(qc.get(k) for k in
                ("blocking_assets", "pending_assets", "retry_assets", "workflow_issues")):
            issues.append("资产 QC 尚未通过；retry / missing / block 均不能进入编排与发布")
        results = {e.get("asset_id"): e for e in qc.get("results", [])}
        report["verified_images"] = []
        # The complete manifest must still match the bytes inspected by QC.
        for aid, entry in entries.items():
            actual = resolve_asset(entry, manifest, path, assets_dir)
            inspected = results.get(aid, {})
            # 快路径（v5.9）：QC 刚读过的字节直接复用，不再读第二遍；但必须确认
            # 磁盘上还是同一份（size+mtime_ns 与 QC 记录一致）——「QC 之后被替换」
            # 必须落回重读，快路径不允许成为漏检路径。
            preloaded = (image_bytes or {}).get(str(actual))
            if preloaded is not None and not _inspected_bytes_current(actual, inspected):
                preloaded = None
            # 摘要复用：QC 已经对同一份字节算过一次 sha256（50MB 图片＝每次跑都要
            # 再付一遍的纯重复劳动）。命中缓存即不再重算——但**字节没变**这条前提
            # 仍由 `_inspected_bytes_current`（size+mtime_ns）证明，且必须与 QC 记录
            # 的 witness.sha256 相等（下面照旧比对）；任何不一致都会落回重读重算。
            from primitives import digest_bytes
            recorded = (inspected.get("witness") or {}).get("sha256")
            known = (digests or {}).get(str(actual))
            if known is not None and _inspected_bytes_current(actual, inspected) \
                    and recorded == known:
                sha = known
                blob = preloaded
            else:
                blob = preloaded if preloaded is not None else (
                    actual.read_bytes() if actual.is_file() else None)
                sha = digest_bytes(blob) if blob is not None else None
                if sha is not None and digests is not None:
                    digests[str(actual)] = sha
            if image_bytes is not None and blob is not None and recorded == sha:
                image_bytes[str(actual)] = blob  # immutable, compiler and preview consume these exact bytes
            report["verified_images"].append({"asset_id": aid, "source": str(actual), "sha256": sha})
            if not sha or recorded != sha:
                issues.append(f"{aid}: 图片缺失、损坏或在 QC 后被替换；重新 asset-qc")
            if (inspected.get("policy") or {}).get("action") not in ACCEPTED:
                issues.append(f"{aid}: 无接受该图片的 QC 结果")
            if entry["decision"] == "generate":
                if not entry.get("prompt") or not entry.get("negative"):
                    issues.append(f"{aid}: 缺少生成提示词/负向提示词")
            else:
                origin = entry.get("origin") or {}
                if origin.get("kind") not in {"provided", "licensed", "original", "reuse"} or not origin.get("source"):
                    issues.append(f"{aid}: 既有素材缺少 origin.kind/source 来源声明")
        for sid, e in images:
            aid = e.get("asset_id")
            if aid not in entries:
                issues.append(f"{sid}/{e.get('id')}: 图片未绑定清单中的 asset_id")
                continue
            dimensions = (results.get(aid, {}).get("qc") or {}).get("dimensions")
            if not isinstance(dimensions, list) or len(dimensions) != 2:
                issues.append(f"{sid}/{aid}: QC 缺少实际图片尺寸；重新检查")
            else:
                iw, ih = map(float, dimensions)
                crop = e.get("crop") or [0, 0, 0, 0]
                iw *= 1 - float(crop[0]) - float(crop[2])
                ih *= 1 - float(crop[1]) - float(crop[3])
                if min(iw, ih) <= 0:
                    issues.append(f"{sid}/{aid}: 裁切后无有效图像")
                else:
                    scale = (min if e.get("fit") == "contain" else max)(
                        float(e["width"]) / iw, float(e["height"]) / ih)
                    if scale > 1.01:
                        issues.append(f"{sid}/{aid}: 有效分辨率低于落位尺寸（放大 {scale:.2f} 倍）；换高分辨率素材或缩小落位")
            if sid not in entries[aid].get("slide_ids", []):
                issues.append(f"{sid}/{aid}: 使用页面未列入清单 slide_ids")
            # src has already been bound by vao; check that no alternate file leaks in.
            if Path(str(e.get("src", ""))).resolve() != resolve_asset(entries[aid], manifest, path, assets_dir):
                issues.append(f"{sid}/{aid}: 编排图片路径与 QC 资产不一致")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        issues.append(f"资产链记录不可读取或格式不正确: {exc}")
    report["issues"] = list(dict.fromkeys(issues))
    report["status"] = "PASS" if not issues else "BLOCKED"
    if report["status"] == "PASS" and image_bytes is not None:
        report["compilation_input"] = "verified_in_memory_snapshot"
    return report


def blocked_result(spec: dict, workflow: dict) -> dict:
    from primitives import spec_fingerprint
    problems = workflow.get("issues") or ["资产链不完整"]
    group = {"root_cause": "ASSET_WORKFLOW_FAIL", "count": len(problems), "ids": [],
             "samples": problems, "fix": "先 plan → assets → 出图；保留 asset_id 与 plan 指纹，再 check（资产核验在 check 内完成）"}
    return {"source_spec_hash": spec_fingerprint(spec), "status": "BLOCKED", "passed": False,
            "release_eligible": False, "blocking_items": len(problems),
            "failure_codes": ["ASSET_WORKFLOW_FAIL"], "affected_slides": [],
            "verdict": {"verdict": "BLOCKED", "status": "BLOCKED", "blocking": len(problems),
                        "codes": ["ASSET_WORKFLOW_FAIL"]},
            "compile": {"passed": False, "skipped": True, "reason": "asset_workflow_preflight"},
            "fix_plan": {"groups": [group]}, "trace_summary": [],
            "next_action": group["fix"], "performance": {}}
