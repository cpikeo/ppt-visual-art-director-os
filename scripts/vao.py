#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VAO · 唯一生产入口（one entry, one deterministic pass）。

    THINK   plan    brief → 判断面（plan.json）+ build 骨架（+ 资产清单）
    BUILD   作者填骨架（构图/尺度/留白是设计判断，引擎不预设）
    VERIFY  check   normalize → guard 硬门 → compile → 可选关键页取证 → PASS/BLOCK

纪律：
  * 一次调用 = 一趟确定性批处理；无逐条修复循环、无 warning 对话。
  * 失败落盘修复包（按根因分组、内嵌明细），成功不写假失败。
  * 零外部渲染器、零 reference 读取；判断基准归 SKILL.md，执行归这里。
  * 速度只有两档：fast（默认，两分钟档）/ strict（全量证据档）。
    `--deadline` 可中止预览；release 缺证据即 BLOCK，不可跳过发布硬门。
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GHOST_MIN_BUDGET_S = 4.0
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_module(path, name: str = "vao_build"):
    """加载作者的 build 模块：总是执行磁盘当前源码（不写 __pycache__）。"""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(
            f"找不到 build 文件: {source}"
            "（先 `vao.py plan brief.yml --skeleton build.py` 生成骨架，填充后再 check）")
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"build 文件不是 UTF-8 文本：{source}（{exc.reason}）") from None
    try:
        code = compile(text, str(source), "exec")
    except SyntaxError as exc:
        raise ValueError(f"build 文件语法错误：{source}:{exc.lineno}:{exc.offset or 0} — {exc.msg}"
                         + (f"\n  {exc.text.rstrip()}" if exc.text else "")) from None
    # Python 模块须先注册再执行，dataclass/延迟注解会查询 __module__。
    from primitives import execute_module
    mod = execute_module(code, source, name)
    return mod, source


def load_spec(path):
    """读 build.py / JSON / YAML 编排稿，不加载 references。"""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(
            f"找不到 spec 文件: {source}"
            "（先 `vao.py plan brief.yml --skeleton build.py` 生成骨架，填充后再 check）")
    if source.suffix.lower() in {".json", ".yml", ".yaml"}:
        text = source.read_text(encoding="utf-8")
        if source.suffix.lower() == ".json":
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"spec JSON 解析失败：{source}:{exc.lineno}:{exc.colno}"
                                 f" — {exc.msg}") from None
        else:
            import yaml
            try:
                value = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                mark = getattr(exc, "problem_mark", None)
                where = f":{mark.line + 1}:{mark.column + 1}" if mark else ""
                raise ValueError(f"spec YAML 解析失败：{source}{where} — {exc}") from None
        if not isinstance(value, dict):
            raise ValueError(f"spec 顶层必须是对象，实际是 {type(value).__name__}：{source}")
        from primitives import assert_bounded_expansion
        assert_bounded_expansion(value, source=f"spec {source.name}")
        return value, source
    if source.suffix.lower() != ".py":
        raise ValueError("编排文件只接受 JSON/YAML，或作者明确指定的可信 .py 文件")
    mod, source = _load_module(source)
    if hasattr(mod, "build_spec"):
        try:
            value = mod.build_spec()
        except Exception as exc:
            raise ValueError(f"build_spec() 执行失败：{source} — "
                             f"{type(exc).__name__}: {exc}") from None
    elif hasattr(mod, "SPEC"):
        value = mod.SPEC
    else:
        raise ValueError(f"build 模块必须定义 build_spec() 或 SPEC：{source}")
    if not isinstance(value, dict):
        raise ValueError(f"build_spec() / SPEC 必须是 dict：{source}")
    return value, source


def _json_write(path, value):
    from primitives import json_write
    return json_write(path, value)


def bind_asset_manifest(spec, manifest_path, assets_dir=None):
    """把 asset_id 图片元素绑到清单文件（不改 build.py；缺图留给编译诊断）。"""
    from primitives import json_read_cached
    from assets import asset_entries, asset_root, resolve_asset
    manifest_file = Path(manifest_path).expanduser().resolve()
    payload = json_read_cached(manifest_file)
    by_id = {str(item["asset_id"]): item for item in asset_entries(payload)}
    root = asset_root(payload, manifest_file, assets_dir)
    bound, missing, missing_files = [], [], []
    result = copy.deepcopy(spec)

    def walk(value):
        if isinstance(value, dict):
            asset_id = value.get("asset_id")
            if asset_id and value.get("type") == "image":
                key = str(asset_id)
                item = by_id.get(key)
                if item:
                    src = resolve_asset(item, payload, manifest_file, assets_dir)
                    value["src"] = str(src)
                    if not src.is_file():
                        missing_files.append(str(src))
                    bound.append({"asset_id": key, "src": str(src)})
                else:
                    missing.append(key)
                    value.setdefault("src", f"__missing_asset__/{key}.png")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(result)

    # safe_area 闭环：清单里的压字区是成图依据，也必须落成版面事实，否则版面可以
    # 把字排到高亮上而无人发现（审计 E16）。页上没声明就继承清单；两处都写了却
    # 不一致 = 图按 A 留白、版按 B 排字，直接 BLOCK（这比缺图更隐蔽）。
    inherited, conflicts = [], []
    keys = ("x", "y", "width", "height")

    def _rect(value):
        if not isinstance(value, dict):
            return None
        try:
            return tuple(round(float(value[k]), 6) for k in keys)
        except (KeyError, TypeError, ValueError):
            return None

    for slide in result.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        sid = str(slide.get("id") or "?")
        for element in slide.get("elements") or []:
            if not isinstance(element, dict) or element.get("type") != "image":
                continue
            item = by_id.get(str(element.get("asset_id"))) or {}
            area = _rect(item.get("safe_area"))
            if area is None:
                continue                      # 空 safe_area = 不压字，版面自己保证
            declared = _rect(slide.get("safe_area"))
            if declared is None and slide.get("safe_area") not in (None, {}):
                continue                      # 写坏了交给 verify 的 safe_area_schema 报
            if declared is None:
                slide["safe_area"] = {k: float(item["safe_area"][k]) for k in keys}
                inherited.append(sid)
            elif declared != area:
                conflicts.append(
                    f"{sid}: 页声明 {dict(zip(keys, declared))} ≠ 清单 {dict(zip(keys, area))}"
                    "（图按清单留白，字却按页声明排）")
    report = {"manifest": str(manifest_file), "assets_dir": str(root), "bound": bound,
              "bound_count": len(bound), "missing_asset_ids": sorted(set(missing)),
              "missing_files": sorted(set(missing_files)),
              "safe_area_inherited": sorted(set(inherited)),
              "safe_area_conflicts": conflicts,
              "status": "PASS" if not missing and not missing_files and not conflicts else "BLOCK"}
    return result, report


# ══════════════════════════════════════════════════════════════════
# THINK · plan
# ══════════════════════════════════════════════════════════════════
def run_plan(brief_path: str, out: str | None = None, skeleton: str | None = None,
             assets_out: str | None = None, assets_dir: str | None = None,
             asset_cache: str | None = None, lean: bool = True,
             policy_path: str | None = None) -> dict:
    started = time.perf_counter()
    timing: dict[str, float] = {}

    t = time.perf_counter()
    # 策略覆盖必须先于判断：`--policy` 是「同一个 brief、换一组阈值」的唯一入口。
    # 校验失败立即抛错（退出 2），不做部分生效——半套策略产生的 plan 无法复盘。
    if policy_path:
        import policy
        policy.load(policy_path)
        timing["policy_load_ms"] = round((time.perf_counter() - t) * 1000, 2)
    from intelligence import (build_skeleton, compact_plan, load_brief, think,
                              validate_brief, validate_plan)
    from datetime import datetime, timezone
    timing["module_import_ms"] = round((time.perf_counter() - t) * 1000, 2)

    t = time.perf_counter()
    brief, brief_sha256 = load_brief(brief_path, with_digest=True)
    timing["brief_load_ms"] = round((time.perf_counter() - t) * 1000, 2)

    # 输入契约先于判断：结构/类型/枚举错与「疑似写错的键名」在这里拦下（退出 2），
    # 不带着一个没人消费的键名去生成一份看起来正常的 plan。作者注解只进 warnings。
    t = time.perf_counter()
    brief_check = validate_brief(brief)
    timing["brief_contract_ms"] = round((time.perf_counter() - t) * 1000, 2)
    if brief_check["errors"]:
        raise ValueError(f"brief 违反输入契约（{len(brief_check['errors'])} 项）："
                         + "；".join(brief_check["errors"][:6]))
    for msg in brief_check["warnings"][:6]:
        print(f"VAO warning: {msg}", file=sys.stderr)

    t = time.perf_counter()
    bundle = think(brief)
    if brief_check["warnings"]:
        bundle.setdefault("warnings", [])
        bundle["warnings"] = [{"rule": "brief_contract", "scope": "deck", "msg": msg}
                              for msg in brief_check["warnings"]] + bundle["warnings"]
    timing["intelligence_ms"] = round((time.perf_counter() - t) * 1000, 2)
    if not bundle.get("pages"):
        raise ValueError("brief 里没有可路由的页面（slides 为空或每页都缺 title/content）："
                         "请至少给出一页的 title + content，再跑 plan")
    # 文件凭证直接从 load_brief 已读取的字节计算；解析与 SHA-256 共用一次读取。
    bundle["workflow"] = {"planned_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                          "brief_path": str(Path(brief_path).expanduser().resolve()),
                          "brief_file_sha256": brief_sha256}
    has_media = any((page["judgment"]["media"]["decision"] in ("required", "reuse"))
                    for page in bundle["pages"])
    from primitives import validate_io_paths
    # 判断一次即知道有没有图：确需图时同一次 plan 给清单，不要求作者重跑
    # 带 --assets-out 的第二条命令；无图则绝不写空清单。
    if has_media and not assets_out:
        assets_out = str(Path(out or brief_path).expanduser().with_name("asset_manifest.json"))
    if assets_out:
        bundle["workflow"]["assets_manifest_path"] = str(Path(assets_out).expanduser().resolve())

    # 所有已知写目标先检查，不能把 brief、清单、骨架或提示词缓存互相覆盖。
    # 骨架 .new.py 回退也纳入集合，避免覆盖输入后才报告冲突。
    source_paths = {"brief": brief_path}
    for i, item in enumerate(brief.get("slides") or []):
        origin = item.get("asset_source") if isinstance(item, dict) else None
        if isinstance(origin, dict) and origin.get("path"):
            path = Path(origin["path"]).expanduser()
            source_paths[f"asset_source[{i}]"] = (path if path.is_absolute() else
                                                  Path(brief_path).expanduser().resolve().parent / path)
    validate_io_paths(source_paths, {
        "plan": out, "skeleton": skeleton,
        "skeleton fallback": str(Path(skeleton).expanduser().with_name(
            Path(skeleton).name + ".new.py")) if skeleton else None,
        "assets manifest": assets_out, "asset cache": asset_cache if assets_out else None})
    if skeleton:
        target = Path(skeleton).expanduser()
        text = build_skeleton(bundle)
        compile(text, str(target), "exec")  # 验证语法，不执行作者文件
        existing = target.read_text(encoding="utf-8") if target.exists() else None
        if existing is not None and existing != text:
            target = target.with_name(target.name + ".new.py")
            existing = target.read_text(encoding="utf-8") if target.exists() else None
        if existing is not None and existing != text:
            raise FileExistsError(f"保留已有稿件：{target}；请指定新的 --skeleton 路径")
        target.parent.mkdir(parents=True, exist_ok=True)

    timing["asset_manifest_build_ms"] = 0.0
    timing["asset_manifest_prepare_ms"] = 0.0
    timing["asset_manifest_write_ms"] = 0.0
    if assets_out:
        # 清单若因无效声明而构造失败，不能先落 plan / 骨架，再让作者拿到
        # 一个声称已有清单、其实并不存在的半成品。原版真实复现了这种失败。
        t = time.perf_counter()
        from assets import build_manifest, prepare_manifest
        manifest = build_manifest(brief, bundle, cache_path=asset_cache)
        timing["asset_manifest_build_ms"] = round((time.perf_counter() - t) * 1000, 2)
        t = time.perf_counter()
        manifest = prepare_manifest(manifest, brief, bundle, brief_path, out,
                                    assets_out, assets_dir)
        timing["asset_manifest_prepare_ms"] = round((time.perf_counter() - t) * 1000, 2)
        t = time.perf_counter()
        _json_write(assets_out, manifest)
        timing["asset_manifest_write_ms"] = round((time.perf_counter() - t) * 1000, 2)

    t = time.perf_counter()
    if skeleton:
        if not target.exists():
            with target.open("x", encoding="utf-8") as handle:
                handle.write(text)
        bundle["workflow"]["skeleton_path"] = str(target.resolve())
    if out:
        # 落盘的永远是给作者/模型读的那一份：默认瘦身投影（决策全留，重复的说明句
        # 上提到 deck.legend）；`--full` 保留完整推演（被否决方案的理由、逐页说明）。
        # 返回给调用方的 bundle 始终是完整的——CLI 打印、遥测、资产链都读它。
        _json_write(out, compact_plan(bundle) if lean else bundle)
    timing["plan_artifact_write_ms"] = round((time.perf_counter() - t) * 1000, 2)

    # 契约校验（P1）：结构查 schema，含义查 intelligence.validate_plan。
    # 为什么在**写盘之后**再读回来查：验的是作者/模型真正拿到的那份字节，
    # 不是内存里那份「应该一样」的对象。不合法即抛错 → CLI 退出 2，
    # 不让一份违约的 plan 变成下游 BUILD 的输入。
    if out:
        t = time.perf_counter()
        from schema import validate_file
        schema_path = _plan_schema_path()
        if schema_path is None:
            # 契约文件缺失（只安装了模块副本、没有仓库目录）：结构校验降级为
            # 显式警告，语义校验照跑。不静默——降级本身要留在输出里。
            print("VAO warning: 未找到 schemas/plan.schema.json（结构契约未执行）；"
                  "请以仓库方式运行或设置 VAO_SCHEMA_DIR", file=sys.stderr)
            problems = []
        else:
            problems = validate_file(out, schema_path)
        problems += validate_plan(bundle)
        timing["plan_contract_ms"] = round((time.perf_counter() - t) * 1000, 2)
        if problems:
            raise ValueError(
                f"plan 违反数据契约（{len(problems)} 项）：" + "；".join(problems[:6]))
    else:
        problems = validate_plan(bundle)
        if problems:
            raise ValueError(
                f"plan 违反数据契约（{len(problems)} 项）：" + "；".join(problems[:6]))

    total_ms = round((time.perf_counter() - started) * 1000, 2)
    # 运行遥测只加在返回对象，不写入 plan.json：规划文件仍是确定性判断凭证。
    bundle["planning_ms"] = total_ms
    bundle["performance"] = {
        "module_import_ms": timing["module_import_ms"],
        "brief_load_ms": timing["brief_load_ms"],
        # 输入契约的成本同样要可见（与 plan_contract_ms 同一条理由）。
        "brief_contract_ms": timing.get("brief_contract_ms", 0.0),
        "intelligence_ms": timing["intelligence_ms"],
        # 契约闸门的成本必须可见：结构+语义校验是新增的一趟读盘 + 全量遍历，
        # 报不出这一项，「契约贵不贵」就只能靠猜。
        "plan_contract_ms": timing.get("plan_contract_ms", 0.0),
        "policy_load_ms": timing.get("policy_load_ms", 0.0),
        "plan_artifact_write_ms": timing["plan_artifact_write_ms"],
        "asset_manifest_build_ms": timing["asset_manifest_build_ms"],
        "asset_manifest_prepare_ms": timing["asset_manifest_prepare_ms"],
        "asset_manifest_write_ms": timing["asset_manifest_write_ms"],
        "reference_files_read": 0,
        "total_ms": total_ms,
    }
    return bundle


# ══════════════════════════════════════════════════════════════════
# VERIFY · check（一趟：normalize → guard → compile → 预览 → 结论）
# ══════════════════════════════════════════════════════════════════
def _plan_schema_path():
    """plan 数据契约文件的位置（解析规则在 schema.contract_path，只写一份）。"""
    import schema as schema_mod
    return schema_mod.contract_path("plan.schema.json")


def _compile_step(spec, output_path, *, speed, spec_path=None,
                  image_bytes=None, digests=None, decoded=None):
    """缓存探测 → 必要时编译 → 产物凭证 → 缓存写入，各阶段独立计时。"""
    from primitives import compile_reuse, record_compile, spec_view, file_digest

    image_bytes = image_bytes if isinstance(image_bytes, dict) else {}
    digests = digests if isinstance(digests, dict) else {}
    cache_reason = "not_attempted"
    cache_root = output_path.with_name(output_path.stem + "_vao")
    view = None
    compile_report = None
    probe_error = None
    t_probe = time.perf_counter()
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        view = spec_view(spec, base_path=output_path.parent, spec_path=spec_path,
                         image_bytes=image_bytes, digests=digests)
        compile_report = compile_reuse(cache_root, output_path, view,
                                       fast_probe=(speed == "fast"), speed=speed)
        cache_reason = "hit" if compile_report is not None else "miss"
    except Exception as exc:
        # 缓存坏掉不能挡住编译，但也不能**无声**降级成「每次都重编」：把原因带进
        # 遥测，作者/CI 才看得出这是缓存故障而不是冷启动（此前只剩一个 probe_failed）。
        cache_reason = "probe_failed"
        probe_error = f"{type(exc).__name__}: {exc}"
        compile_report = None
        print(f"VAO warning: 编译缓存探测失败（本轮改为完整编译）：{probe_error}",
              file=sys.stderr)
    cache_probe_ms = (time.perf_counter() - t_probe) * 1000

    compile_ms = 0.0
    if compile_report is None:
        t_compile = time.perf_counter()
        from compiler import compile_deck      # 惰性导入：缓存命中路径不付 pptx 导入成本
        try:
            compile_report = compile_deck(spec, output_path,
                                          decode_seed=decoded,
                                          spec_path=str(spec_path) if spec_path else None,
                                          image_bytes=image_bytes, speed=speed)
        except ModuleNotFoundError as exc:
            if exc.name in {"pptx", "lxml", "PIL", "numpy"}:
                compile_report = {
                    "passed": False, "slides": len(spec.get("slides") or []),
                    "warnings": [f"缺少编译依赖 {exc.name!r}；请运行 "
                                 "python -m pip install -r requirements.txt"],
                    "file_bytes": None}
            else:
                raise
        compile_ms = (time.perf_counter() - t_compile) * 1000

    # strict cache probe 已对当前字节做过 SHA，可复用其摘要；fast 只用 size+mtime_ns
    # 见证缓存，因此仍须在发布前读取/哈希一次，维持产物凭证的完整性。
    t_attest = time.perf_counter()
    if compile_report.get("passed") and not compile_report.get("skipped"):
        try:
            expected_sha = compile_report.get("output_sha256")
            reused_sha = (expected_sha if compile_report.get("reused")
                          and speed != "fast"
                          and isinstance(expected_sha, str) and len(expected_sha) == 64 else None)
            stat = output_path.stat()
            actual_sha = reused_sha if reused_sha is not None else file_digest(output_path)
            if expected_sha and expected_sha != actual_sha:
                compile_report.setdefault("warnings", []).append(
                    "编译报告 output_sha256 与实际 PPTX 不一致")
                compile_report["passed"] = False
            compile_report["file_bytes"] = stat.st_size
            compile_report["output_sha256"] = actual_sha
            compile_report["output_path"] = str(output_path.resolve())
            compile_report["output_exists"] = True
        except (OSError, TypeError, ValueError):
            compile_report.setdefault("warnings", []).append(
                f"编译输出不存在或不可读取: {output_path}")
            compile_report["passed"] = False
            compile_report["output_exists"] = False
            compile_report["output_sha256"] = None
    attestation_ms = (time.perf_counter() - t_attest) * 1000

    cache_write_ms = 0.0
    cache_write_error = None
    if compile_report.get("passed") and compile_report.get("output_sha256") and compile_report.get("output_exists") \
            and cache_reason in ("miss", "probe_failed"):
        t_write = time.perf_counter()
        try:
            view = view if cache_reason == "miss" and view is not None else spec_view(
                spec, base_path=output_path.parent, spec_path=spec_path,
                image_bytes=image_bytes, digests=digests)
            if not record_compile(cache_root, output_path, view, compile_report):
                cache_write_error = "缓存元数据写盘失败（目录不可写 / 同名文件占位）"
        except Exception as exc:
            cache_write_error = f"{type(exc).__name__}: {exc}"
        if cache_write_error:
            # 写不进缓存不影响这一轮的产物，但会**静默**让每轮都重编——本库在
            # 预览缓存那边明确把这种「静默失效」当成坑（ghost.cache_write_failed）。
            # 留一行诊断，作者才看得出是缓存故障而不是冷启动。
            print(f"VAO warning: 编译缓存未能记录（本轮产物有效，下轮将重编）：{cache_write_error}",
                  file=sys.stderr)
        cache_write_ms = (time.perf_counter() - t_write) * 1000

    timing = {
        "cache_probe_ms": round(cache_probe_ms, 2),
        "compile_ms": round(compile_ms, 2),
        "attestation_ms": round(attestation_ms, 2),
        "cache_write_ms": round(cache_write_ms, 2),
        "cache_reason": cache_reason,
        "cache_probe_error": probe_error,
        "cache_write_error": cache_write_error,
        "cache_enabled": True,
        "cache_dir": str(cache_root),
    }
    return compile_report, timing


def _ghost(spec, output_dir, pages=None, base_path=None, image_bytes=None,
           decoded=None, *, speed="strict", limit=24, output_sha=None,
           image_roots=None) -> dict:
    """关键页取证（PIL 结构预览；页级缓存内建于 ghost 模块）。

    只有产物/渲染器/选页/预览文件见证都一致，才复用整份证据。
    快档 stat、严档逐文件 SHA；输出 PNG 被改坏不能再以 PASS 复用。
    页级缓存仍负责修复而不重画未变化的页。
    两档同一渲染口径（1× 直接绘制）：预览在本尺寸上回答的是方向问题，
    2× 超采样只用 38% 的额外时间买到亚像素抗锯齿差，不改变任何判断依据。
    两档同一编码口径（PNG level 1）：zlib 级别不改变任何像素（PNG 无损），
    level 6 只把每轮冷预览多花 ~70ms 换 ~10% 更小的证据文件——证据的效力
    在像素与见证，不在压缩比；实测 12 页 + 联络表 338ms → 275ms。
    """
    from primitives import engine_fingerprint, file_digest, witness, witness_same, json_read_cached
    fast = str(speed).lower() == "fast"

    def preview_witness(path):
        current = witness(path)
        if current["size"] is None or not Path(path).is_file():
            return None
        if not fast:
            current["sha256"] = file_digest(path)
        return current
    explicit_pages = [int(n) for n in pages] if pages is not None else None
    # 缓存的证据范围也是输入：同一 PPTX 请求 2 页，不可复用旧的 5 页声明。
    request = {"pages": explicit_pages,
               "slide_ids": [str(s.get("id")) for s in (spec.get("slides") or [])
                             if isinstance(s, dict)],
               "key_page_limit": max(1, int(limit)) if fast and pages is None else None}
    target = Path(output_dir)
    marker = target / "ghost.meta.json"
    engine = engine_fingerprint("preview")
    from primitives import preview_font_stamp
    fonts = preview_font_stamp(refresh=True)
    if output_sha and marker.exists():
        try:
            cached = json_read_cached(marker)
        except (OSError, ValueError):
            cached = {}
        cached_pages = cached.get("pages") or []
        cached_sheet = cached.get("contact_sheet")
        stored = cached.get("file_witnesses") or {}

        def valid_preview(path):
            expected = stored.get(str(path)) if isinstance(stored, dict) else None
            # 改名/截断/文件替换先用 stat 拦，严档才花钱哈希现有预览。
            current = witness(path)
            if not Path(path).is_file() or not witness_same(expected, current):
                return False
            return fast or witness_same(expected,
                                        {**current, "sha256": file_digest(path)}, strict=True)

        same_request = (cached.get("output_sha256") == output_sha
                        and cached.get("engine") == engine
                        and cached.get("fonts") == fonts
                        and cached.get("renderer_speed") == str(speed)
                        and cached.get("request") == request)
        # 不匹配先退场：渲染器/选页变了时根本无需碰旧 PNG，更不必哈希。
        if (same_request and cached_pages and cached_sheet
                and all(valid_preview(p) for p in [*cached_pages, cached_sheet])):
            info = dict(cached)
            info["reused"] = True
            info["pages_drawn"] = 0
            info["pages_from_cache"] = int(info.get("count", len(cached_pages)) or 0)
            info["contact_sheet_cached"] = True
            return info
    # 字体身份已核对；只有缺失/失效时才实际绘图。
    from ghost import PAGE_CACHE_DIR, ghost_deck, key_selection, make_contact_sheet
    slides = spec.get("slides") or []
    roles = None
    if explicit_pages is not None:
        wanted = explicit_pages
        scope = "full" if len(wanted) >= len(slides) else "explicit_subset"
    elif fast:
        wanted, roles = key_selection(slides, limit=limit)
        scope = "full" if len(wanted) >= len(slides) else "key_pages"
    else:
        wanted = list(range(1, len(slides) + 1))
        scope = "full"
    preview_spec = dict(spec)
    preview_spec["_image_bytes"] = image_bytes if image_bytes is not None else {}
    preview_spec["_image_decoded"] = decoded if decoded is not None else {}
    if base_path:
        preview_spec["_base_path"] = str(Path(base_path).resolve())
    # 相对图片路径的解析根必须与编译侧同序（[输出目录, 稿件目录]），否则同名
    # 相对路径在两个目录各有一张图时，预览画的是另一张——预览≠产物。
    if image_roots:
        preview_spec["_image_roots"] = [str(Path(p).resolve()) for p in image_roots if p]
    rendered: list = []
    page_stats: dict = {}
    paths = ghost_deck(preview_spec, output_dir, pages=wanted,
                       scale=0.5, supersample=1, store=True,
                       png_compress_level=1, images_out=rendered,
                       stats=page_stats)
    sheet_stats: dict = {}
    contact = make_contact_sheet(paths, Path(output_dir) / "ghost-contact-sheet.png",
                                 images=rendered,
                                 png_compress_level=1,
                                 cache_dir=Path(output_dir) / PAGE_CACHE_DIR,
                                 stats=sheet_stats)
    rendered_ids = [str(slides[n - 1].get("id")) for n in wanted
                    if 1 <= n <= len(slides) and isinstance(slides[n - 1], dict)]
    info = {"type": "ghost_layout_preview", "dir": str(Path(output_dir)),
            "key_pages": (roles if scope == "key_pages" else None),
            "pages": [str(p) for p in paths], "count": len(paths),
            "slide_ids": rendered_ids,
            "pages_rendered": wanted, "page_count": len(slides),
            "scope": scope, "contact_sheet": str(contact) if contact else None,
            "renderer": "PIL",
            "pages_drawn": len(page_stats.get("rendered_pages") or []),
            "pages_from_cache": len(page_stats.get("cached_pages") or []),
            "contact_sheet_cached": bool(sheet_stats.get("sheet_cached")),
            "evidence_scope": "direction_and_structure_not_pixel_proof"}
    info["output_sha256"] = output_sha
    info["engine"] = engine
    info["fonts"] = fonts
    info["renderer_speed"] = str(speed)
    info["request"] = request
    # 字面回落必须随预览一起交付：本机缺 CJK 字面时页图仍会「成功」产出，
    # 但中文字形是缺的。预览记录不带这一条，读图的人无从分辨「排版如此」和
    # 「本机没字体」——那正是把结构预览当成真实排版的开端。
    from ghost import font_fallbacks
    fallbacks = font_fallbacks()
    if fallbacks:
        info["font_fallbacks"] = fallbacks
        print("VAO warning: 本机缺少预览字面 " + "、".join(sorted(fallbacks))
              + "；已回落到 PIL 默认位图字体（无中文字形），本轮页图只能当结构线看。",
              file=sys.stderr)
    # 声明了本机没有的家族同属一类失真：预览用的是替换字面，行宽/换行与
    # 「装了该字体的机器」不是一回事。逐家族记账，不重复刷屏。
    from ghost import font_substitutions
    substitutions = font_substitutions()
    if substitutions:
        info["font_substitutions"] = substitutions
        print("VAO warning: 声明的字体本机缺失，预览已替换：" + "；".join(
            f"{declared} → {actual}" for declared, actual in sorted(substitutions.items()))
            + "。字形与行宽只是近似，换行位置不可当作产物证据。", file=sys.stderr)
    # max_lines 截断同理：预览按声明收笔，产物（PowerPoint）不截断。页面上已有
    # 可见标记；台账让它进 meta，可按「页/元素」复核，不必逐页放大找那一行字。
    from ghost import text_truncations
    truncations = text_truncations()
    if truncations:
        info["text_truncations"] = truncations
        print("VAO warning: 预览有 " + str(len(truncations))
              + " 个文本被 max_lines 截断（页面已标记）；目标 PowerPoint 不截断，"
                "请核对框容量或放宽 max_lines。", file=sys.stderr)
    # bbox 完全出画布的元素：预览裁掉、产物同样不可见——不是预览失真，是稿子
    # 本身有观众看不到的元素。部分出血不算（那常是有意构图）。
    from ghost import out_of_canvas
    outside = out_of_canvas()
    if outside:
        info["out_of_canvas"] = outside
        print("VAO warning: " + "、".join(
            f"{pg} 页 {', '.join(ids)}" for pg, ids in sorted(outside.items()))
            + " 整体在画布外，观众不可见；若非有意放置请移回画布。", file=sys.stderr)
    # 页图与联络表是交付证据，不仅要存在，还得是上轮验证的那份字节。
    info["file_witnesses"] = {str(p): preview_witness(p)
                              for p in [*paths, *([contact] if contact else [])]}
    info["reused"] = False
    try:
        target.mkdir(parents=True, exist_ok=True)
        _json_write(marker, info)
    except (OSError, TypeError, ValueError) as exc:
        # 写不下 marker 只是失去「下轮复用」的机会，预览本身仍然有效；但静默失败会
        # 让下一轮莫名重画，所以留一行诊断（不改变本轮结论）。
        info["marker_write_error"] = f"{type(exc).__name__}: {exc}"
        print(f"VAO warning: 预览凭证写盘失败（本轮预览有效，下轮无法复用）：{exc}",
              file=sys.stderr)
    return info


def repair_packet(result: dict, mode: str, build, output) -> dict:
    """结构化修复包：默认只在 BLOCK 时落盘；显式 --packet 可要求额外导出。"""
    packet = {
        "mode": mode,
        "build": str(build),
        "output": str(output),
        "verdict": result.get("verdict"),
        "status": result.get("status"),
        "passed": result.get("passed"),
        "blocking_items": result.get("blocking_items", 0),
        "failure_codes": result.get("failure_codes", []),
        "affected_slides": result.get("affected_slides", []),
        "fix_plan": result.get("fix_plan") or {"groups": []},
        "asset_workflow": result.get("asset_workflow"),
        "release_eligible": result.get("release_eligible", False),
        "next_action": result.get("next_action"),
        "timing": result.get("performance"),
        # 无 facts 键：verdict 不产出自由事实，packet 只收口已定义的修复字段。
    }
    return packet


def run_check(build_path: str, output: str, *, mode: str = "draft",
              packet: str | None = None, preview: str | None = None,
              json_output: bool = False,
              assets_manifest: str | None = None, assets_dir: str | None = None,
              speed: str = "fast", deadline: float | None = None,
              ghost_pages: int = 5) -> tuple:
    """一次执行完成交付验证。失败落盘 fail-closed；成功不写假失败。"""
    started = time.perf_counter()
    output_path = Path(output).expanduser()
    packet_path = Path(packet).expanduser() if packet else output_path.with_suffix(".repair.json")
    mode = str(mode or "draft").strip().lower()
    from primitives import validate_io_paths, PathConflictError
    # 必须在 fail() 之外：冲突时连诊断文件也不能写，否则错误路径本身会毁稿。
    qc_path = (Path(assets_manifest).expanduser().with_name(
        Path(assets_manifest).stem + ".qc.json") if assets_manifest else None)
    writes = {"PPTX": output_path, "repair packet": packet_path,
              "release manifest": output_path.with_suffix(".manifest.json") if mode == "release" else None,
              "asset QC": qc_path}
    preview_dir = preview or (str(output_path.with_name(output_path.stem + "_preview"))
                              if mode == "release" else None)
    managed_dirs = {"preview": preview_dir,
                    "compile cache": output_path.with_name(output_path.stem + "_vao")
                    if mode != "spec" else None}
    validate_io_paths({"build": build_path, "assets manifest": assets_manifest}, writes,
                      managed_dirs=managed_dirs)

    def fail(exc: Exception) -> tuple:
        from verify import fail_result
        result = fail_result({}, [f"输入或执行失败: {type(exc).__name__}: {exc}"])
        result["performance"] = {"total_ms": round((time.perf_counter() - started) * 1000, 1)}
        if mode == "release":
            from verify import release_manifest
            manifest_path = output_path.with_suffix(".manifest.json")
            manifest = release_manifest({"slides": []}, result, workflow={"image_count": 0})
            manifest["validation"]["issues"].append(str(exc))
            _json_write(manifest_path, manifest)
            result["manifest_path"] = str(manifest_path)
        packet_obj = repair_packet(result, mode, build_path, output_path)
        _json_write(packet_path, packet_obj)
        line = (json.dumps(packet_obj, ensure_ascii=False) if json_output else
                f"VAO {mode}: BLOCKED · {result['next_action']}\n  packet: {packet_path}")
        print(line)
        return result, 2

    try:
        t_load = time.perf_counter()
        spec, build = load_spec(build_path)
        load_spec_ms = round((time.perf_counter() - t_load) * 1000, 2)

        t_import = time.perf_counter()
        # spec / 无图暖命中不加载资产层，也不预先探测 pptx：编译缺失时由
        # _compile_step 在真正需要编译的那一刻给出明确诊断。
        from verify import (check_spec, mode_profile, normalize_spec,
                            release_guard_rules, verdict)
        from primitives import spec_fingerprint
        module_import_ms = round((time.perf_counter() - t_import) * 1000, 2)

        t_identity = time.perf_counter()
        spec_hash = spec_fingerprint(spec)          # 本轮唯一一次 spec 身份
        spec_identity_ms = round((time.perf_counter() - t_identity) * 1000, 2)

        snapshots: dict = {}   # 本轮唯一一次读图：QC / 核验 / 编译 / 预览共用
        decoded: dict = {}     # 核验解码过的底图：编译期不再重复解码
        digests: dict = {}     # 本轮唯一一次哈希
        slides = spec.get("slides")
        has_images = (isinstance(slides, list) and any(
            isinstance(slide, dict) and isinstance(slide.get("elements"), list)
            and any(isinstance(e, dict) and e.get("type") == "image"
                    for e in slide["elements"]) for slide in slides))
        source_paths = {"build": build, "assets manifest": assets_manifest}
        if has_images:
            # 即使缺清单而将被阻断，修复包/预览也不许覆盖声明的原图。
            # 同时保护编译与结构预览采用的相对路径候选；不导入 Office 引擎。
            roots = {build.parent, output_path.resolve().parent, Path.cwd()}
            for si, slide in enumerate(slides):
                if not isinstance(slide, dict) or not isinstance(slide.get("elements"), list):
                    continue
                for ei, element in enumerate(slide["elements"]):
                    if not isinstance(element, dict) or element.get("type") != "image":
                        continue
                    raw = element.get("src") or ((element.get("asset") or {}).get("src")
                                                  if isinstance(element.get("asset"), dict) else None)
                    if raw:
                        path = Path(str(raw)).expanduser()
                        for ri, root in enumerate(roots):
                            source_paths[f"raw image {si}/{ei}/{ri}"] = path if path.is_absolute() else root / path
        validate_io_paths(source_paths, writes, managed_dirs=managed_dirs)
        asset_binding = None
        asset_bind_ms = 0.0
        if has_images and assets_manifest:
            t_bind = time.perf_counter()
            spec, asset_binding = bind_asset_manifest(spec, assets_manifest, assets_dir)
            asset_bind_ms = round((time.perf_counter() - t_bind) * 1000, 2)
        if has_images and assets_manifest:
            from primitives import json_read_cached
            from assets import asset_entries, resolve_asset
            payload = json_read_cached(assets_manifest)
            validate_io_paths({**source_paths,
                               "brief": (payload.get("workflow") or {}).get("brief_path"),
                               **{f"asset {e['asset_id']}": resolve_asset(
                                   e, payload, assets_manifest, assets_dir)
                                  for e in asset_entries(payload)}}, writes, managed_dirs=managed_dirs)

        if mode == "release":
            # 路径/资产来源预检完成后立即撤销旧发布资格。编译或预览中断时，
            # 即使进程被终止，也不能让上一轮 PASS 冒充本轮完成。
            from verify import fail_result, release_manifest
            pending = fail_result({"source_spec_hash": spec_hash}, ["本轮 release 核验尚未完成；须完整复跑 check"])
            _json_write(output_path.with_suffix(".manifest.json"),
                        release_manifest(spec, pending, spec_hash=spec_hash))

        # 只有实际使用图片才读取清单与像素；漏传清单的图片在编译前直接阻断。
        workflow = {"status": "SKIPPED", "issues": [], "image_count": 0,
                    "reason": "no_image_elements"}
        qc_result: dict = {}
        qc_ms = asset_chain_ms = 0.0
        if has_images and assets_manifest:
            from assets import qc_report, verify_chain
            t_qc = time.perf_counter()
            qc_result, _ = qc_report(assets_manifest, assets_dir, phase=mode,
                                     speed=speed, snapshots=snapshots,
                                     decoded=decoded, digests=digests)
            qc_ms = round((time.perf_counter() - t_qc) * 1000, 2)
            t_chain = time.perf_counter()
            workflow = verify_chain(spec, assets_manifest,
                                    qc_result.get("report_path"), assets_dir,
                                    image_bytes=snapshots, digests=digests)
            if asset_binding and (asset_binding.get("missing_asset_ids")
                                  or asset_binding.get("missing_files")
                                  or asset_binding.get("safe_area_conflicts")):
                workflow["status"] = "BLOCKED"
                workflow.setdefault("issues", []).append(
                    "asset binding: " + "、".join(
                        asset_binding.get("missing_asset_ids", [])
                        + asset_binding.get("missing_files", [])
                        + asset_binding.get("safe_area_conflicts", [])))
            asset_chain_ms = round((time.perf_counter() - t_chain) * 1000, 2)
        elif has_images and mode != "spec":
            from assets import verify_chain
            t_chain = time.perf_counter()
            workflow = verify_chain(spec)  # 含图但无清单：不编译伪合格 PPTX
            asset_chain_ms = round((time.perf_counter() - t_chain) * 1000, 2)

        if workflow.get("status") == "BLOCKED":
            from assets import blocked_result
            result = blocked_result(spec, workflow)
            result["asset_workflow"] = workflow
            result["source_spec_hash"] = spec_hash
            result["performance"] = {
                "load_spec_ms": load_spec_ms, "module_import_ms": module_import_ms,
                "spec_identity_ms": spec_identity_ms, "asset_bind_ms": asset_bind_ms,
                "qc_ms": qc_ms, "asset_chain_ms": asset_chain_ms,
                "qa_ms": round(qc_ms + asset_chain_ms, 2),
                "asset_count": len(qc_result.get("results") or []),
                "asset_retry_count": len(qc_result.get("retry_assets") or []),
                "asset_qc_reused": sum(1 for item in (qc_result.get("results") or [])
                                        if (item.get("qc") or {}).get("reused")),
                "image_source_snapshots": len(snapshots),
                "image_snapshot_bytes": sum(len(blob) for blob in snapshots.values()
                                             if isinstance(blob, (bytes, bytearray, memoryview))),
                "image_decode_seed_entries": len(decoded),
                "compile_ms": 0, "ghost_ms": 0,
                "render_pages": 0, "render_pages_drawn": 0,
                "render_pages_cached": 0, "render_bundle_reused": False,
                "contact_sheet_cached": False, "render_skipped": "asset_blocked",
                "total_ms": round((time.perf_counter() - started) * 1000, 2),
            }
            manifest_path = None
            if mode == "release":
                from verify import release_manifest
                manifest_path = output_path.with_suffix(".manifest.json")
                _json_write(manifest_path, release_manifest(spec, result, workflow=workflow,
                                                           spec_hash=spec_hash))
                result["manifest_path"] = str(manifest_path)
            _json_write(packet_path, repair_packet(result, mode, build, output_path))
            _print_line(result, None, manifest_path, packet_path, speed, mode, json_output)
            return result, 2

        t_normalize = time.perf_counter()
        normalized, norm = normalize_spec(spec)
        normalization_ms = round((time.perf_counter() - t_normalize) * 1000, 2)
        prof = mode_profile(mode)
        effective_rules = release_guard_rules(prof["mode"], None)
        t_guard = time.perf_counter()
        guard_report = check_spec(normalized, rules=effective_rules)
        guard_ms = round((time.perf_counter() - t_guard) * 1000, 2)
        guard_errors = [c for c in guard_report.get("checks", []) if c.get("level") == "error"]
        timing = {
            "load_spec_ms": load_spec_ms,
            "module_import_ms": module_import_ms,
            "spec_identity_ms": spec_identity_ms,
            "asset_bind_ms": asset_bind_ms,
            "qc_ms": qc_ms,
            "asset_chain_ms": asset_chain_ms,
            "asset_count": len(qc_result.get("results") or []),
            "asset_retry_count": len(qc_result.get("retry_assets") or []),
            "normalization_ms": normalization_ms,
            "guard_ms": guard_ms,
            "normalization": norm,
            "provenance_required": bool(effective_rules.get("require_provenance", False)),
            "speed": speed,
        }
        if not prof["compile"]:
            compile_report = {"passed": True, "skipped": True, "warnings": [],
                              "file_bytes": None,
                              "output_exists": False, "output_sha256": None}
            timing.update(cache_probe_ms=0, compile_ms=0,
                          attestation_ms=0, cache_write_ms=0,
                          cache_reason="not_compiled")
        elif guard_errors:
            compile_report = {"passed": False, "skipped": True, "warnings": [],
                              "file_bytes": None,
                              "output_exists": False, "output_sha256": None}
            timing.update(cache_probe_ms=0, compile_ms=0,
                          attestation_ms=0, cache_write_ms=0,
                          cache_reason="guard_error")
        else:
            compile_report, compile_timing = _compile_step(
                normalized, output_path, speed=speed, spec_path=str(build),
                image_bytes=snapshots, digests=digests, decoded=decoded)
            timing.update(compile_timing)
        t_verdict = time.perf_counter()
        result = verdict(normalized, mode=mode, guard_report=guard_report,
                         compile_report=compile_report, spec_hash=spec_hash,
                         runtime_facts={**timing, "asset_workflow": workflow})
        timing["verdict_ms"] = round((time.perf_counter() - t_verdict) * 1000, 2)
        result["asset_workflow"] = workflow
        if asset_binding is not None:
            result["asset_binding"] = asset_binding

        # 预览证据：release 自动出；draft 只在显式要求时出；预算不足跳过。
        # 不另起 preview 命令，release 的一次 check 已产出页图与联络表。
        ghost = None
        render_skip_reason = "not_requested"
        if preview_dir:
            if not result.get("passed"):
                render_skip_reason = "verdict_blocked"
            elif workflow.get("status") == "BLOCKED":
                render_skip_reason = "asset_blocked"
            else:
                # 只有 None 才是「不限时」：0 与负值是「没有预算了」。用 `not deadline`
                # 判断会把显式声明的 0 秒预算静默升格成不限时——release 于是照常
                # 渲染预览并给出 PASS，而同一语义的 -5 却正确 BLOCK（实测复现）。
                left = None if deadline is None else (deadline - (time.perf_counter() - started))
                if left is None or left >= GHOST_MIN_BUDGET_S:
                    render_skip_reason = None
                    t_ghost = time.perf_counter()
                    ghost = _ghost(normalized, preview_dir, base_path=build.parent,
                                   image_bytes=snapshots, decoded=decoded,
                                   speed=speed, limit=ghost_pages,
                                   output_sha=(result.get("compile") or {}).get("output_sha256"),
                                   image_roots=[output_path.resolve().parent, build.parent])
                    timing["ghost_ms"] = round((time.perf_counter() - t_ghost) * 1000, 2)
                    timing["render_pages"] = int(ghost.get("count", 0) or 0)
                    timing["render_pages_drawn"] = int(ghost.get("pages_drawn", 0) or 0)
                    timing["render_pages_cached"] = int(ghost.get("pages_from_cache", 0) or 0)
                    timing["render_bundle_reused"] = bool(ghost.get("reused"))
                    timing["contact_sheet_cached"] = bool(ghost.get("contact_sheet_cached"))
                else:
                    render_skip_reason = "deadline"
        if "ghost_ms" not in timing:
            timing["ghost_ms"] = 0.0
            timing["render_pages"] = 0
            timing["render_pages_drawn"] = 0
            timing["render_pages_cached"] = 0
            timing["render_bundle_reused"] = False
            timing["contact_sheet_cached"] = False
            timing["render_skipped"] = render_skip_reason
        result["performance"] = {**result.get("performance", {}), **timing}

        manifest = None
        manifest_path = None
        manifest_ms = 0.0
        if mode == "release":
            from verify import release_manifest
            t_manifest = time.perf_counter()
            manifest = release_manifest(normalized, result, ghost_preview=ghost,
                                        workflow=workflow, spec_hash=spec_hash,
                                        output_verified=True)
            if manifest["status"] == "BLOCKED" and result.get("passed"):
                from verify import fail_result
                errors = manifest["validation"]["issues"] or ["发布凭证无效"]
                fail_result(result, errors)
                manifest = release_manifest(normalized, result, ghost_preview=ghost,
                                            workflow=workflow, output_verified=True)
            manifest_ms = round((time.perf_counter() - t_manifest) * 1000, 2)
            manifest_path = output_path.with_suffix(".manifest.json")
            result["manifest_path"] = str(manifest_path)
        timing["release_manifest_ms"] = manifest_ms
        timing["asset_qc_reused"] = sum(1 for item in (qc_result.get("results") or [])
                                         if (item.get("qc") or {}).get("reused"))
        timing["image_source_snapshots"] = len(snapshots)
        timing["image_snapshot_bytes"] = sum(len(blob) for blob in snapshots.values()
                                             if isinstance(blob, (bytes, bytearray, memoryview)))
        timing["image_decode_seed_entries"] = len(decoded)
        timing["qa_ms"] = round(sum(float(timing.get(k, 0) or 0) for k in
                                    ("qc_ms", "asset_chain_ms", "normalization_ms",
                                     "guard_ms", "verdict_ms", "release_manifest_ms")), 2)
        # total_ms 覆盖 load → QA → compile/cache → render → release manifest；
        # artifact JSON 写入另由进程 wall time覆盖，不把临时文件 flush 算成 QA。
        timing["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        result["performance"].update(timing)
        if manifest is not None:
            manifest["qa_summary"]["performance"] = dict(result["performance"])
            _json_write(manifest_path, manifest)
        binding_block = bool(asset_binding and (asset_binding.get("missing_asset_ids")
                                                or asset_binding.get("missing_files")
                                                or asset_binding.get("safe_area_conflicts")))
        passed = bool(result.get("passed") and not binding_block)
        if packet or not passed:
            _json_write(packet_path, repair_packet(result, mode, build, output_path))
        else:
            # PASS 没有修复内容；清除上次 BLOCK 的默认文件，避免文件冗余或过期误导。
            try:
                packet_path.unlink(missing_ok=True)
            except OSError as exc:
                print(f"VAO warning: 无法清理过期修复包 {packet_path}: {exc}", file=sys.stderr)
        _print_line(result, ghost, manifest_path, packet_path, speed, mode, json_output)
        return result, (0 if passed else 2)
    except PathConflictError:
        raise  # 不得让 fail() 把诊断写回刚发现冲突的输入文件
    except KeyboardInterrupt as exc:
        try:
            fail(exc)
        except Exception as failure:
            print(f"VAO error: 中断状态无法落盘: {failure}", file=sys.stderr)
        raise
    except SystemExit as exc:
        return fail(exc)  # 作者代码 sys.exit(0) 不是工作流成功
    except Exception as exc:
        return fail(exc)


def _print_line(result, ghost, manifest_path, packet_path, speed,
                mode, json_output) -> None:
    """一次执行一条结论；证据在文件里，对话里只有注意力预算内的几行。"""
    if json_output:
        print(json.dumps({"status": result.get("status"),
                          "verdict": result.get("verdict"),
                          "failure_codes": result.get("failure_codes"),
                          "fix_plan": result.get("fix_plan"),
                          "next_action": result.get("next_action"),
                          "timing": result.get("performance")},
                         ensure_ascii=False, default=str))
        return
    total = result.get("performance", {}).get("total_ms")
    ms = f" · {total / 1000:.2f}s" if isinstance(total, (int, float)) else ""
    if result.get("passed"):
        line = f"VAO {mode}: PASS{ms} · speed={speed}"
        comp = result.get("compile") or {}
        if comp.get("output_path"):
            size_kb = (comp.get("file_bytes") or 0) / 1024
            sha = str(comp.get("output_sha256") or "")[:12]
            reuse = "（缓存复用，未重编）" if comp.get("reused") else ""
            line += f"\n  pptx: {comp['output_path']} ({size_kb:.0f}KB · sha256 {sha}…){reuse}"
    else:
        groups = (result.get("fix_plan") or {}).get("groups") or []
        line = f"VAO {mode}: BLOCKED{ms} · {len(groups)} 组根因"
        for g in groups[:6]:
            ids = ",".join(str(i) for i in (g.get("ids") or [])[:6])
            line += (f"\n  [{g.get('root_cause')}] ×{g.get('count')}"
                     + (f" ({ids})" if ids else "") + f" → {g.get('fix', '')}")
        line += f"\n  packet: {packet_path}"
    if ghost:
        scope = ghost.get("scope")
        line += f"\n  preview: {ghost.get('count')} 页 ghost（{scope}）→ {Path(ghost['dir']).name}/"
    if manifest_path:
        line += f"\n  manifest: {manifest_path}"
    print(line)


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════
SPEED_PROFILES = {
    "fast": "两分钟交付档：像素统计降采样、图片只读一次、预览只画关键页、缓存快探",
    "strict": "严格档：全分辨率 QC、整包缓存核对、逐页预览（忽略 --ghost-pages）",
}
DEFAULT_SPEED = "fast"
DEFAULT_DEADLINE = 120.0
DEFAULT_GHOST_PAGES = 5      # fast 档只画关键页（封面/章节/画心/密数据/收尾）


def _add_speed_flags(parser):
    parser.add_argument("--speed", choices=tuple(SPEED_PROFILES), default=DEFAULT_SPEED,
                        help="fast（默认）= 两分钟交付档；strict = 全量证据档")
    parser.add_argument("--deadline", type=float, default=DEFAULT_DEADLINE,
                        help="本次调用墙钟预算（秒，默认 120）；预算不足时跳过可选预览并留痕")
    parser.add_argument("--ghost-pages", type=int, default=DEFAULT_GHOST_PAGES,
                        help="fast 档关键页数量上限（封面/章节/画心/密数据/收尾）；"
                             "strict 档逐页预览，此参数被忽略")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vao.py", description="PPT Visual Art Director OS · one fast entry point")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="THINK：brief → plan.json + build 骨架（+ 资产清单）")
    p.add_argument("brief")
    p.add_argument("--out", dest="plan_out", default="plan.json")
    p.add_argument("--skeleton")
    p.add_argument("--assets-out", help="同时产出资产清单（作者据此出图）")
    p.add_argument("--assets-dir", help="图将被放到哪个目录（写进清单，check 据此核验）")
    p.add_argument("--asset-cache", help="提示词缓存 JSON；相同视觉需求指纹直接复用")
    p.add_argument("--json", action="store_true", help="print the compact plan")
    p.add_argument("--full", action="store_true",
                   help="落盘完整推演（默认瘦身：决策全留，重复说明句上提到 deck.legend）")
    p.add_argument("--policy", dest="policy_path", default=None,
                   help="策略覆盖 JSON（深度合并进 policy.py 的默认策略；未知键直接报错）")

    c = sub.add_parser("check", help="VERIFY：build → normalize/guard/compile/preview → 结论")
    c.add_argument("build")
    c.add_argument("output", nargs="?", default="deck.pptx")
    c.add_argument("--mode", choices=("spec", "draft", "release"), default="draft")
    c.add_argument("--packet")
    c.add_argument("--preview", help="write ghost preview PNGs here (release writes them by default)")
    c.add_argument("--assets-manifest", help="bind image elements carrying asset_id")
    c.add_argument("--assets-dir", help="directory containing generated manifest filenames")
    c.add_argument("--json", action="store_true")
    _add_speed_flags(c)

    q = sub.add_parser("qc", help="资产离线体检：同判据跑像素 QC + 策略，不写状态、不消耗 retry")
    q.add_argument("--assets-manifest", required=True)
    q.add_argument("--assets-dir", default=None)
    q.add_argument("--speed", choices=["fast", "strict"], default="fast")
    q.add_argument("--json", action="store_true")
    return parser


def run_qc(manifest_path: str, assets_dir: str | None = None,
           speed: str = "fast") -> dict:
    """资产离线体检：与 check 同一判据（image_qc + qc_retry_decision），
    但不写 QC 报告、不递增 attempt、不进 deck 结论。

    出图迭代的最短反馈环：作者改一张图，一条命令拿到阻断/建议清单，
    不必跑全量 check 往返，也不必自建 harness（CASE_004 证据）。
    """
    from assets import qc_report, asset_root, qc_profile
    mpath = Path(manifest_path).expanduser().resolve()
    man = json.loads(mpath.read_text(encoding="utf-8"))
    report, _ = qc_report(mpath, assets_dir, phase="draft", speed=speed, persist=False)
    return {"speed": qc_profile(speed)["speed"],
            "assets_dir": str(asset_root(man, mpath, assets_dir)),
            "status": report["status"], "workflow_issues": report["workflow_issues"],
            "results": [{"asset_id": r["asset_id"], "slide_ids": r["slide_ids"],
                         "status": "missing" if r["missing"] else r["qc"]["status"],
                         "action": r["policy"]["action"],
                         "blocking": r["policy"]["blocking_checks"],
                         "advisory": r["policy"]["advisory_checks"],
                         "issues": [c.get("issue") for c in r["qc"].get("checks", [])
                                    if c.get("status") == "issue"]}
                        for r in report["results"]]}


def force_utf8_stdio() -> None:
    """CLI 输出恒为 UTF-8——Windows 上这是正确性问题，不是外观问题。

    Windows 的 Python 只在写**控制台**时用 UTF-16 控制台 API；一旦 stdout 被重定向
    （管道 / CI / 另一个进程捕获），编码回落到系统 ANSI 代码页：中文 Windows 是
    cp936，英文是 cp1252。后者的 `print("plan: 5 页…")` 直接抛 UnicodeEncodeError，
    整条命令以退出码 2 结束，产物还没写完就没了（实测复现）。
    UTF-8 是本包对所有文件的既有口径（brief / build.py / JSON / 预览），
    这里只是让**输出**与它一致，重定向方得到稳定可解析的字节。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):   # 非文本流 / 已被替换的流
            pass


def main(argv=None) -> int:
    force_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            bundle = run_plan(args.brief, args.plan_out, args.skeleton, lean=not args.full,
                              assets_out=args.assets_out, assets_dir=args.assets_dir,
                              asset_cache=args.asset_cache, policy_path=args.policy_path)
            if args.json:
                print(json.dumps({"plan_path": str(Path(args.plan_out).expanduser().resolve()),
                                  "page_count": len(bundle["pages"]),
                                  "workflow": bundle["workflow"], "warnings": bundle.get("warnings"),
                                  "performance": bundle["performance"]}, ensure_ascii=False, default=str))
            else:
                pages = bundle.get("pages") or []
                media_pages = [p["id"] for p in pages
                               if ((p.get("judgment") or {}).get("media") or {})
                               .get("decision") not in (None, "none")]
                world = bundle["deck"].get("world") or {}
                print(f"plan: {len(pages)} 页 · 视觉世界 {world.get('name')} "
                      f"· 规划 {bundle.get('planning_ms', 0)}ms")
                if bundle.get("warnings"):
                    for w in bundle["warnings"][:4]:
                        print(f"  ⚠ {w.get('msg') or w}")
                if media_pages:
                    print(f"  媒体必要性判断：出图 {','.join(media_pages)} · "
                          f"清单 {bundle.get('workflow', {}).get('assets_manifest_path')}")
                coherence = bundle["deck"].get("coherence") or {}
                if coherence.get("adjustments"):
                    shown = "；".join(
                        f"{a['page']} {a['field']} {a['from']}→{a['to']}"
                        for a in coherence["adjustments"][:3])
                    print(f"  跨页校准：{len(coherence['adjustments'])} 处回拨（{shown}）")
                if args.plan_out:
                    print(f"  plan: {args.plan_out}"
                          + (f" · skeleton: {bundle['workflow']['skeleton_path']}" if args.skeleton else ""))
            return 0
        if args.command == "check":
            _, code = run_check(args.build, args.output, mode=args.mode,
                                packet=args.packet, preview=args.preview,
                                json_output=args.json,
                                assets_manifest=args.assets_manifest,
                                assets_dir=args.assets_dir,
                                speed=args.speed, deadline=args.deadline,
                                ghost_pages=args.ghost_pages)
            return code
        if args.command == "qc":
            rep = run_qc(args.assets_manifest, args.assets_dir, args.speed)
            print(json.dumps(rep, ensure_ascii=False, indent=2))
            return 0 if rep["status"] == "PASS" else 2
        return 2
    except KeyboardInterrupt:
        print("VAO interrupted: 本轮未完成；不得使用旧 PASS 作为本轮交付凭证", file=sys.stderr)
        return 130
    except SystemExit as exc:
        print(f"VAO error: 作者代码中止执行（SystemExit {exc.code!r}）；本轮未完成", file=sys.stderr)
        return 2
    except ModuleNotFoundError as exc:
        print(f"VAO error: missing Python dependency {exc.name!r}; "
              "install requirements.txt", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"VAO error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
