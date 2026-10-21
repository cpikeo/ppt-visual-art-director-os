"""小规模判断基准：固定案例 → 页级判断 → 字段比对 → 指标与回归。

用法：
  python3 scripts/bench.py                       # 跑基准，打印表格
  python3 scripts/bench.py --out bench.json      # 另存结果
  python3 scripts/bench.py --baseline <your-baseline.json>           # 可选：与外部基线对比

只检查**判断字段**（页面角色、证据形态、比较、结论来源、图像决策）。构图、字阶、
中文断行不在这里判：它们需要结构预览或目标软件，本基准不伪装成视觉验收。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import intelligence as intel

# 测试样本随最小技能包保留一份；历史各套案例与来源记录在同一文件中。
DEFAULT_CASES = Path(__file__).resolve().parent / "json" / "judgment_cases.json"
BRIEF = {"audience": "内部评审会", "decision": "批准下一步预算"}
# 判断错误的类别：用于「错误布局 / 错误图片 / 错误信息图表」的误判率。
MISJUDGE_FIELDS = {"media", "media_source", "comparison", "evidence", "evidence_not"}


# 语义词表：可被消融（去掉后看哪些判断会变）。数值权重是函数体内的字面量，不在此列。
ABLATABLE = ("_HUMAN_WORDS", "_SCENE_WORDS", "_WITNESS_WORDS", "_TOPIC_TAILS", "_TITLE_ASSERTION",
             "_CONCLUSION_WORDS", "_ASK_WORDS", "_COMPARISON_WORDS", "_SERIES_WORDS",
             "_SEQUENCE_WORDS", "_STRUCTURE_WORDS", "_CHANGE_WORDS", "_TOPIC_MARKERS",
             "_CREDENTIAL_WORDS", "_PHYSICAL_SUBJECTS")


def _actual(case: dict) -> dict:
    item = {"id": case["id"], "title": case["title"], "content": case.get("content", ""),
            **({"chart": True} if case.get("chart") else {}),
            **{k: case[k] for k in ("role", "evidence", "asset") if k in case}}
    world = intel.derive_world(BRIEF, [intel.understand(f"{case['title']} {case.get('content', '')}")])
    judged = intel.page_judgment(item, index=case["index"], total=case["total"],
                                 brief=BRIEF, world=world, warnings=[])
    u = judged["understanding"]
    # 观测面要与案例能断言的面一致：过去只管角色/证据/媒体，于是一整类「构图与主语」
    # 的判据在 bench 里根本没有量具（断言比到 None 永远红，或永远绿）。这里补采，
    # 断言语义仍由 _checks 一处实现，unseen_bench 与本函数共用同一批字段名。
    return {"role": judged["visual_role"]["role"], "evidence": u.get("evidence"),
            "comparison": bool(u.get("comparison")), "part_whole": bool(u.get("part_whole")),
            "claim": judged["claim"]["source"], "claim_text": judged["claim"].get("text"),
            "media": judged["media"]["decision"], "media_source": judged["media"]["source"],
            "media_suggested": judged["media"].get("suggested"),
            "focus": judged["focus"].get("element_role"),
            "composition": judged["composition"].get("chosen"),
            "primary": judged["typography"].get("lead"),
            "distinct": u.get("distinct_numerals"),
            "open_questions": judged.get("open_questions")}


def _checks(expect: dict, actual: dict) -> list[dict]:
    rows = []
    for key, want in expect.items():
        if key == "evidence_not":
            ok, shown = actual["evidence"] not in want, actual["evidence"]
            want_s = f"不是 {want}"
        elif key == "distinct_min":
            shown = actual.get("distinct") or 0
            ok, want_s = shown >= want, f"≥ {want}"
        elif key in ("claim_contains", "claim_not_contains", "primary_contains"):
            field = {"primary_contains": "primary"}.get(key, "claim_text")
            shown = str(actual.get(field) or "")
            hit = all(s in shown for s in want) if key == "primary_contains" \
                else all(s in shown for s in want)
            ok = (not hit) if key == "claim_not_contains" else hit
            want_s = ("不含 " if key == "claim_not_contains" else "含 ") + str(want)
        elif key == "claim_soft":
            shown = actual.get("claim")
            ok = shown in ("absent", "frame", None) or \
                any(s in str(actual.get("claim_text") or "") for s in want)
            want_s = f"absent/frame 或文本含 {want}"
        elif key == "claim_text":
            shown = actual.get("claim_text")
            ok, want_s = shown in want, f"∈ {want}"
        else:
            shown = actual[key]
            if isinstance(want, bool):
                ok, want_s = shown == want, str(want)
            else:
                ok, want_s = shown in want, f"∈ {want}"
        rows.append({"field": key if key != "evidence_not" else "evidence_not",
                     "expected": want_s, "actual": shown, "ok": bool(ok),
                     "misjudge_class": key in MISJUDGE_FIELDS})
    return rows


def run(cases_path: Path = DEFAULT_CASES) -> dict:
    import hashlib
    data_path = Path(cases_path)
    raw = data_path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    results = []
    for case in data["cases"]:
        actual = _actual(case)
        checks = _checks(case["expect"], actual)
        results.append({"id": case["id"], "suite": case.get("suite", "external"),
                        "category": case["category"], "severity": case["severity"],
                        "title": case["title"],
                        "actual": actual, "checks": checks,
                        "passed": all(c["ok"] for c in checks),
                        "why": case.get("why", "")})
    # 报告绑定案例文件身份：结果与「哪一份案例集的哪个版本」可互相追认，
    # 开发集、冻结集与未来独立集在报告层面不再混淆。
    return {"cases": results, "metrics": _metrics(results),
            "cases_identity": {"file": str(data_path),
                               "sha256_12": hashlib.sha256(raw).hexdigest()[:12]}}


def _metrics(results: list[dict]) -> dict:
    checks = [c for r in results for c in r["checks"]]
    mis = [c for c in checks if c["misjudge_class"]]
    critical = [r for r in results if r["severity"] == "critical"]
    return {
        "cases": len(results),
        "cases_passed": sum(r["passed"] for r in results),
        "accuracy": round(sum(c["ok"] for c in checks) / max(len(checks), 1), 3),
        "misjudge_rate_image_chart_structure": round(
            sum(not c["ok"] for c in mis) / max(len(mis), 1), 3),
        "critical_defect_rate": round(
            sum(not r["passed"] for r in critical) / max(len(critical), 1), 3),
        "critical_cases": len(critical),
    }


def ablate(names: list[str], cases_path: Path = DEFAULT_CASES) -> dict:
    """逐组去掉语义词表，重跑基准；返回指标与逐案例的通过状态变化。"""
    full = run(cases_path)
    full_status = {r["id"]: r["passed"] for r in full["cases"]}
    out = {}
    for name in names:
        original = getattr(intel, name)
        blank = () if isinstance(original, tuple) else re.compile(r"(?!x)x")
        setattr(intel, name, blank)
        try:
            rep_ = run(cases_path)
        finally:
            setattr(intel, name, original)
        changed = [r["id"] for r in rep_["cases"] if r["passed"] != full_status[r["id"]]]
        out[name] = {"metrics": rep_["metrics"], "changed_cases": changed,
                     "changed_to": {r["id"]: ("PASS" if r["passed"] else "FAIL")
                                    for r in rep_["cases"] if r["id"] in changed}}
    return {"full": full["metrics"], "ablations": out}


def regression(current: dict, baseline: dict) -> dict:
    """修复回归率：基线里通过、现在失败的案例占基线通过数的比例。"""
    base_pass = {r["id"] for r in baseline["cases"] if r["passed"]}
    now_pass = {r["id"] for r in current["cases"] if r["passed"]}
    now_ids = {r["id"] for r in current["cases"]}
    missing = sorted({r["id"] for r in baseline["cases"]} - now_ids)
    broke = sorted(base_pass - now_pass)
    fixed = sorted({r["id"] for r in baseline["cases"] if not r["passed"]} & now_pass)
    return {"regressed_cases": broke, "missing_cases": missing,
            "fixed_cases": fixed,
            "regression_rate": round(len(broke) / max(len(base_pass), 1), 3)}


# ── 盲评通道（R6）：视觉质量由人评，不写入自动化门。本模块只负责打乱、改名、汇总与一致性。
BLIND_DIMS = ("narrative", "focus", "composition", "typography", "completeness")
BLIND_DIMS_CN = {"narrative": "叙事", "focus": "焦点", "composition": "构图",
                 "typography": "中文排版", "completeness": "整体完成度"}
BLIND_SCALE = (1, 7)        # 评分量表：1 严重不足 … 4 及格线 … 7 优秀；量表外一律拒绝
BLIND_ICC_THRESHOLD = 0.5   # 启发式共识线，不是统计检验；不确定性看各维度 icc_ci95
HOW_TO_READ_BLIND = ("ICC 衡量评审者之间的一致性，不衡量设计质量：一致地高与一致地低都可能。"
                     "均值是本组评审的平均印象，不是客观质量；0.5 共识线是启发式阈值，不是统计检验。"
                     "mean 键为真实来源路径（含映射信息），本报告勿直接外发。")
# vao/bench 生成的流程工件：带着它们进评审目录，等于把作者/版本线索递给评审者。
_BLIND_STRIP_PATTERNS = (".git", "__pycache__", "*.pyc", "pages",   # pages = ghost 页缓存
                         "*manifest*.json", "ghost.meta.json", "*.key.json", "score_sheet.csv",
                         # 流水线工件同样会泄露身份：plan.json 写着逐页判断与作者路径，
                         # facts/grading 写着期望与配置名。评审目录里只留产物与预览。
                         "plan.json", "facts.json", "grading.json", "timing.json",
                         "eval_metadata.json", "baseline-spec.json", "run_summary.json",
                         "*.skill")


def _scrub_pptx_identity(path: Path) -> None:
    """原地重写 pptx，仅抹去 docProps/core.xml 的「谁/何时」身份字段。

    清得掉的是文件属性身份；作者写进画面、备注或文件名里的身份清不掉，
    由 pack 内 README 提醒送评人自检——不假装净化是彻底的。
    """
    import re
    import zipfile
    blank = [(re.compile(r"(<dc:creator>).*?(</dc:creator>)", re.S), r"\1\2"),
             (re.compile(r"(<cp:lastModifiedBy>).*?(</cp:lastModifiedBy>)", re.S), r"\1\2"),
             (re.compile(r"(<cp:lastPrinted>).*?(</cp:lastPrinted>)", re.S), r"\1\2"),
             (re.compile(r"(<cp:revision>).*?(</cp:revision>)", re.S), r"\1\2"),
             (re.compile(r"(<dcterms:created[^>]*>).*?(</dcterms:created>)", re.S), r"\1\2"),
             (re.compile(r"(<dcterms:modified[^>]*>).*?(</dcterms:modified>)", re.S), r"\1\2")]
    with zipfile.ZipFile(path) as zin:
        entries = [(info, zin.read(info.filename)) for info in zin.infolist()]
    with zipfile.ZipFile(path, "w") as zout:
        for info, data in entries:
            if info.filename == "docProps/core.xml":
                text = data.decode("utf-8")
                for pat, rep in blank:
                    text = pat.sub(rep, text)
                data = text.encode("utf-8")
            zout.writestr(info, data)


def _scrub_png_identity(path: Path) -> None:
    """重建像素，丢掉 PNG 的文本块（tEXt/iTXt/EXIF）——图像也会带作者与工具指纹。

    只抹元数据，不动像素：预览图是给人看结构的证据，改一个像素就等于改了证据。
    PIL 保存时会把 `im.info` 里的文本块一起写回，所以显式清空 info 再存。
    """
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    with Image.open(path) as im:
        im.load()
        clean = im.copy()
        clean.info.clear()
        clean.save(path, format="PNG", pnginfo=PngInfo())


def blind_pack(items: list[str], out_dir: Path, seed: int | None = None,
               *, scrub_previews: bool = False) -> dict:
    """打乱并改名待评版本；评审目录只留匿名件、空白评分表与评审须知，映射与溯源写进目录外的 key。

    匿名化的边界（诚实声明，不伪装彻底）：pptx 的「谁/何时」文件属性被抹去，
    vao/bench 流程工件（manifest/meta/key/页缓存）不进评审目录；作者写进画面
    内容、备注或文件名里的身份无法自动清除，README 提醒送评人自检。
    """
    import csv
    import hashlib
    import random
    import shutil
    import time
    from primitives import validate_io_paths, PathConflictError, json_write
    out_dir = Path(out_dir).expanduser().resolve()
    sources = [Path(item).expanduser().resolve() for item in items]
    key_path = out_dir.parent / (out_dir.name + ".key.json")
    # copytree 不得递归读入自己刚创建的输出；key 也不能写回待评输入树。
    for src in sources:
        if src.is_dir() and (out_dir == src or out_dir.is_relative_to(src)
                             or key_path.is_relative_to(src)):
            raise PathConflictError(f"盲评输出不能位于待评输入目录内：{src}")
    validate_io_paths({f"item {i}": src for i, src in enumerate(sources)},
                      {"blind key": key_path}, managed_dirs={"blind output": out_dir})
    # 合并复制会残留旧版本/旧评分，甚至泄露不属于本轮的素材；不擅自删除用户工作。
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"盲评输出目录非空；请使用新的目录以隔离本轮评审：{out_dir}")
    if key_path.exists():
        raise FileExistsError(f"保留已有盲评映射；请使用新的输出目录：{key_path}")
    # 未给种子时生成并记进 key：打乱顺序因此可复现、可审计，而不是「没人记得顺序怎么来的」。
    seed = random.SystemRandom().randrange(2 ** 31) if seed is None else seed
    rng = random.Random(seed)
    order = list(range(len(items)))
    rng.shuffle(order)
    out_dir.mkdir(parents=True, exist_ok=True)
    mapping, digest, rows = {}, {}, []
    for n, idx in enumerate(order, 1):
        src = sources[idx]
        code = f"V{n:02d}"
        if src.is_dir():
            shutil.copytree(src, out_dir / code, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(*_BLIND_STRIP_PATTERNS))
            for pptx in sorted((out_dir / code).rglob("*.pptx")):
                _scrub_pptx_identity(pptx)
            scrubbed = []
            if scrub_previews:
                for png in sorted((out_dir / code).rglob("*.png")):
                    _scrub_png_identity(png)
                    scrubbed.append(png.relative_to(out_dir / code).as_posix())
            digest[code] = {"type": "dir",
                            "packed_files": sum(1 for p in (out_dir / code).rglob("*") if p.is_file()),
                            "previews_scrubbed": scrubbed}
        else:
            dst = out_dir / f"{code}{src.suffix}"
            shutil.copyfile(src, dst)
            if src.suffix.lower() == ".pptx":
                _scrub_pptx_identity(dst)
            digest[code] = {"source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
                            "packed_sha256": hashlib.sha256(dst.read_bytes()).hexdigest()}
        mapping[code] = str(Path(items[idx]))  # 保留 key 中原有的作者路径表达
        rows.append(code)
    key = {"version_format": 2, "tool": "vao-bench-blind-pack/2",
           "packed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "seed": seed, "items": mapping, "sha256": digest,
           # key 按设计能反推身份（它就是为了揭盲而存在的），所以要把「别外发」写进文件本身，
           # 而不是只写在文档里——文件会被单独转发，文档不会。
           "identity_warning": ("本文件含代号→原路径映射（可反推配置），只给组织者；"
                                "发给评审者的只有评审目录内容（评分表 + README），"
                                "不含本文件。")}
    json_write(key_path, key)
    sheet = out_dir / "score_sheet.csv"
    header = ["reviewer", "item"] + list(BLIND_DIMS) + ["reason", "review_time"]
    with sheet.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for code in rows:
            writer.writerow(["", code] + [""] * len(BLIND_DIMS) + ["", ""])
    readme = out_dir / "README.txt"
    readme.write_text(
        f"盲评材料 · 打包于 {key['packed_at_utc']}\n"
        "\n"
        "评分：每版本每维度 1–7 分（1 严重不足 … 4 及格线 … 7 优秀），可为半分；量表外分数汇总时拒绝。\n"
        "维度：narrative 叙事 / focus 焦点 / composition 构图 / typography 中文排版 / completeness 整体完成度。\n"
        "纪律：每位评审复制本表单独填写、单独提交，互不看对方分数；review_time 列记录评审时间。\n"
        "至少 3 位完整评审才估计评审者一致性（ICC）；不足时汇总只报均值与缺口，不装作有共识。\n"
        "\n"
        "匿名化边界：已抹去 pptx 文件属性里的作者/时间（docProps/core.xml），已剔除 vao/bench\n"
        "流程工件（manifest/meta/key/页缓存）；作者写进画面、备注或文件名里的身份无法自动清除，\n"
        "送评前请自行检查。若需核验材料未被调包，key 文件记录了各版本的 sha256。\n"
        + ("\n预览图：各版本附 ghost 结构预览（preview-*.png），可先看结构再打开 pptx。\n"
           "预览图的文本块（tEXt/iTXt）已重建清除，像素未改——它是证据，不是成品。\n"
           if scrub_previews else ""),
        encoding="utf-8")
    return {"items": rows, "sheet": str(sheet), "key": str(key_path),
            "readme": str(readme), "scale": "1-7"}


def _icc_2_1(matrix: list[list[float]]) -> float | None:
    """ICC(2,1)：双向随机效应、单次测量的绝对一致性。matrix[target][rater]。

    实现对照 Shrout & Fleiss (1979) Table 1：ICC(2,1)=0.290、ICC(3,1)=0.715，逐位吻合。
    """
    n = len(matrix)
    k = len(matrix[0]) if n else 0
    if n < 2 or k < 2:
        return None
    grand = sum(sum(r) for r in matrix) / (n * k)
    row_m = [sum(r) / k for r in matrix]
    col_m = [sum(matrix[i][j] for i in range(n)) / n for j in range(k)]
    ssr = k * sum((m - grand) ** 2 for m in row_m)
    ssc = n * sum((m - grand) ** 2 for m in col_m)
    sst = sum((matrix[i][j] - grand) ** 2 for i in range(n) for j in range(k))
    sse = sst - ssr - ssc
    msr, msc = ssr / (n - 1), ssc / (k - 1)
    mse = sse / ((n - 1) * (k - 1)) if (n - 1) * (k - 1) else 0.0
    den = msr + (k - 1) * mse + k * (msc - mse) / n
    return None if den == 0 else (msr - mse) / den


def _icc_ci_bootstrap(mat: list[list[float]], replicates: int = 2000,
                      seed: int = 20261015) -> tuple[float, float] | None:
    """按「版本」重抽样的自助法 95% 区间；固定种子，可复现。

    版本少时区间必然宽——这是要暴露的不确定性，不是缺陷。半数以上重抽样
    不可估（矩阵退化）时放弃区间：给一个不可信的区间比不给更糟。
    """
    import random
    n = len(mat)
    if n < 2:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(replicates):
        sample = [mat[rng.randrange(n)] for _ in range(n)]
        v = _icc_2_1(sample)
        if v is not None and math.isfinite(v):
            vals.append(v)
    if len(vals) < replicates // 2:
        return None
    vals.sort()
    return vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))]


def _blind_key_items(key: dict) -> dict:
    """兼容两代 key：v2（溯源元数据 + items 嵌套）与 v1（平铺 code→路径）。"""
    items = key.get("items") if isinstance(key.get("items"), dict) else key
    if not items:
        raise ValueError("盲评 key 必须是非空版本映射")
    return items


def blind_score(sheet_paths: list[str], key_path: str) -> dict:
    """汇总多位评审的评分表：每版本每维度均值 + ICC(2,1)（含自助法 95% 区间）。

    只有 ≥3 位完整评审时估计一致性；不足时仍报告均值与缺口——证据不足要说明
    缺什么，而不是把已收到的数据一起扔掉。部分填写的行记数不统计，量表外拒绝。
    """
    import csv
    import io
    key = json.loads(Path(key_path).read_text(encoding="utf-8"))
    if not isinstance(key, dict) or not key:
        raise ValueError("盲评 key 必须是非空版本映射")
    items_map = _blind_key_items(key)
    by_reviewer: dict[str, dict[str, dict]] = {}
    partial_rows = 0
    for sp in sheet_paths:
        for row in csv.DictReader(io.StringIO(Path(sp).read_text(encoding="utf-8"), newline="")):
            reviewer = (row.get("reviewer") or "").strip()
            item = (row.get("item") or "").strip()
            if not item or not reviewer:
                continue
            if item not in items_map:
                raise ValueError(f"评分引用未知版本：{item}")
            vals = {d: (row.get(d) or "").strip() for d in BLIND_DIMS}
            filled = [d for d in BLIND_DIMS if vals[d]]
            if not filled:
                continue
            if len(filled) < len(BLIND_DIMS):
                partial_rows += 1  # 半填的行记数不统计：静默丢行会让缺口不可见
                continue
            try:
                parsed = {d: float(vals[d]) for d in BLIND_DIMS}
            except ValueError:
                raise ValueError(f"评分必须为数字：{reviewer}/{item}") from None
            if not all(math.isfinite(v) for v in parsed.values()):
                raise ValueError(f"评分必须为有限数字：{reviewer}/{item}")
            off_scale = {d: v for d, v in parsed.items()
                         if not (BLIND_SCALE[0] <= v <= BLIND_SCALE[1])}
            if off_scale:
                raise ValueError(f"评分须在 {BLIND_SCALE[0]}–{BLIND_SCALE[1]} 内："
                                 f"{reviewer}/{item} = {off_scale}")
            ratings = by_reviewer.setdefault(reviewer, {})
            if item in ratings:
                raise ValueError(f"重复评分：{reviewer}/{item}")
            ratings[item] = parsed
    reviewers = sorted(by_reviewer)
    items = sorted(items_map)  # 完整性以 key 为准，不以「恰好有人评分的版本」为准
    complete = [r for r in reviewers if set(by_reviewer[r]) == set(items)]
    report = {"reviewers": len(reviewers), "complete_reviewers": len(complete),
              "items": items, "scale": f"{BLIND_SCALE[0]}-{BLIND_SCALE[1]}",
              "partial_rows": partial_rows,
              "missing_items_by_reviewer": {r: sorted(set(items) - set(by_reviewer[r]))
                                            for r in reviewers if set(by_reviewer[r]) != set(items)},
              "ratings_count": {i: sum(1 for r in reviewers if i in by_reviewer[r]) for i in items},
              "dimensions": {}, "consensus": "NOT_ENOUGH_REVIEWERS",
              "identified_report": True, "how_to_read": HOW_TO_READ_BLIND}
    # 完全相同的评审向量 = 重复提交或疑似串通：标记不剔除（保留数据，交组织者复核）。
    dupes = [sorted((a, b)) for i, a in enumerate(complete) for b in complete[i + 1:]
             if by_reviewer[a] == by_reviewer[b]]
    if dupes:
        report["suspect_identical_reviewers"] = dupes
    if not complete:
        return report
    k = len(complete)

    def mean_of(d: str) -> dict:
        return {items_map.get(i, i): round(sum(by_reviewer[r][i][d] for r in complete) / k, 2)
                for i in items}

    if k < 3:
        for d in BLIND_DIMS:
            report["dimensions"][BLIND_DIMS_CN[d]] = {
                "mean": mean_of(d), "n_items": len(items), "k_raters": k,
                "note": "评审不足 3 位：不估计一致性，仅呈现均值与缺口"}
        return report
    consensus = True
    for d in BLIND_DIMS:
        mat = [[by_reviewer[r][i][d] for r in complete] for i in items]
        entry = {"mean": mean_of(d), "n_items": len(items), "k_raters": k, "icc": None}
        if len({v for row in mat for v in row}) == 1:
            # 零方差＝评审完全一致；ICC 不可估是数学事实，不是「无共识」。
            # 也可能意味着评审偷懒或串通——suspect 标记与 review_time 供组织者复核。
            entry["note"] = "全部分值相同：完全一致；ICC 因零方差不可估，请结合 suspect 标记复核是否独立"
        else:
            icc = _icc_2_1(mat)
            if icc is not None and math.isfinite(icc):
                entry["icc"] = round(icc, 3)
                # 阈值判定用原始值，但把结论显式写出来：读者不该拿四舍五入的
                # 显示值反推判定（0.50 显示、0.4999 判定的差一眼看得见）。
                entry["meets_threshold"] = icc >= BLIND_ICC_THRESHOLD
                lo, hi = _icc_ci_bootstrap(mat)
                entry["icc_ci95"] = None if lo is None else [round(lo, 3), round(hi, 3)]
                if len(items) < 5:
                    entry["note"] = "版本少：点估计不稳定，请以区间宽度理解"
                if icc < BLIND_ICC_THRESHOLD:
                    consensus = False
            else:
                consensus = False
                entry["note"] = "ICC 不可估（矩阵退化）"
        report["dimensions"][BLIND_DIMS_CN[d]] = entry
    report["consensus"] = "CONSENSUS_SUPPORTED" if consensus else "NO_CONSENSUS"
    report["icc_model"] = ("ICC(2,1) 双向随机、单次测度、绝对一致；0.5 共识线为启发式阈值，"
                           "非统计检验；区间为按版本重抽样的自助法估计")
    return report


def _print(report: dict) -> None:
    for r in report["cases"]:
        mark = "PASS" if r["passed"] else "FAIL"
        a = r["actual"]
        print(f"{mark} {r['id']} [{r['severity']:8}] {r['title'][:24]:24} "
              f"role={a['role']} ev={a['evidence']} cmp={a['comparison']} "
              f"claim={a['claim']} media={a['media']}")
        for c in r["checks"]:
            if not c["ok"]:
                print(f"      ✗ {c['field']}: 期望 {c['expected']}，实际 {c['actual']}")
    m = report["metrics"]
    print(f"\n案例通过 {m['cases_passed']}/{m['cases']} · 判断准确率 {m['accuracy']:.1%} · "
          f"图像/图表/结构误判率 {m['misjudge_rate_image_chart_structure']:.1%} · "
          f"严重缺陷率 {m['critical_defect_rate']:.1%}（{m['critical_cases']} 个 critical 案例）")
    if "regression" in report:
        g = report["regression"]
        print(f"修复回归率 {g['regression_rate']:.1%} · 回归 {g['regressed_cases'] or '无'} · "
              f"新修复 {g['fixed_cases'] or '无'}")


# ── 判据守门审计（测试的测试） ────────────────────────────────────────────
# 把 policy 里的一条判据**故意调坏**，看案例集会不会有人变红。
# 一个判据调坏却零案例报警 = 这条判据没有任何证据在守（覆盖缺口，不是「没问题」）。
# 反过来说：这也是删案例前必须查的一栏——只有「零守卫 + 零独有行 + 零独有期望」才可合并。
GUARD_MUTATIONS = {
    "份额判据关": {"evidence_shapes": {"share_min_numerals": 99}},
    "并列判据关": {"evidence_shapes": {"parallel_min_values": 9}},
    "面板判据关": {"evidence_shapes": {"panel_min_numerals": 99}},
    "比较降级": {"evidence_shapes": {"comparison_base": 0.1}},
    "结构失效": {"evidence_shapes": {"structure": 0.1}},
    "世界倾向关": {"composition": {"grammar_preference_bonus": 0.0}},
}


def _suite_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [{"index": 1, "total": 3, **c} for c in data.get("cases") or []]


def guard_audit(cases_path: Path, mutations: dict | None = None) -> dict:
    import policy
    cases = _suite_cases(cases_path)
    baseline_red = {c["id"] for c in cases
                    if any(not r["ok"] for r in _checks(c.get("expect") or {}, _actual(c)))}
    rows = {}
    for name, patch in (mutations or GUARD_MUTATIONS).items():
        policy.configure(patch)
        try:
            caught = [c["id"] for c in cases
                      if c["id"] not in baseline_red
                      and any(not r["ok"] for r in _checks(c.get("expect") or {}, _actual(c)))]
        finally:
            policy.reset()
        rows[name] = caught
    unguarded = [n for n, c in rows.items() if not c]
    return {"cases": cases_path.as_posix(), "cases_total": len(cases),
            "baseline_red": sorted(baseline_red), "guards": rows,
            "unguarded": unguarded,
            "ok": not unguarded and not baseline_red}


def main(argv=None) -> int:
    # 与生产入口共用 UTF-8 管道契约。Windows 的 cp1252 stdout 会在打印
    # 中文 FAIL 详情前抛 UnicodeEncodeError：退出码仍是 1，却不是真实负例结果。
    from vao import force_utf8_stdio
    force_utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["blind"]:
        if len(argv) >= 3 and argv[1] == "pack":
            try:
                items = [a for a in argv[3:] if not a.startswith("--")]
                result = blind_pack(items, Path(argv[2]),
                                    scrub_previews="--scrub-previews" in argv[3:])
            except (ValueError, OSError) as exc:
                print(f"bench error: {exc}", file=sys.stderr)
                return 2
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if len(argv) >= 4 and argv[1] == "score":
            try:
                result = blind_score(argv[3:], argv[2])
            except (ValueError, OSError) as exc:
                print(f"bench error: {exc}", file=sys.stderr)
                return 2
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        print("用法：bench.py blind pack <评审目录> <版本1> <版本2> ...\n"
              "      bench.py blind score <key.json> <评分表1.csv> <评分表2.csv> ...", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--ablate", action="store_true", help="逐组消融语义词表，打印指标变化")
    parser.add_argument("--guard-audit", action="store_true",
                        help="把 policy 判据逐条调坏，看案例集有没有人报警（零报警＝无人守）")
    args = parser.parse_args(argv)
    from primitives import validate_io_paths, json_write
    try:
        validate_io_paths({"cases": args.cases, "baseline": args.baseline}, {"report": args.out})
    except (ValueError, OSError) as exc:
        print(f"bench error: {exc}", file=sys.stderr)
        return 2
    if args.ablate:
        result = ablate(list(ABLATABLE), Path(args.cases))
        f = result["full"]
        print(f"完整基准：通过 {f['cases_passed']}/{f['cases']} · 准确率 {f['accuracy']:.1%} · "
              f"严重缺陷率 {f['critical_defect_rate']:.0%}")
        blind = []
        for name, a in result["ablations"].items():
            m = a["metrics"]
            ch = ", ".join(f"{k}→{v}" for k, v in a["changed_to"].items()) or "无变化"
            if not a["changed_cases"]:
                blind.append(name)
            print(f"  去掉 {name:20} 通过 {m['cases_passed']}/{m['cases']} · 准确率 {m['accuracy']:.1%} · 变化：{ch}")
        # 消融无变化不是「这个词表没用」，而是**这 57 例不判别这条路径**。
        # 把覆盖缺口直接打出来，避免把 100% 当成全路径验证。
        if blind:
            print(f"\n覆盖缺口：{len(blind)}/{len(result['ablations'])} 组语义词表消融后指标不变 "
                  f"（{', '.join(blind)}）——本案例集不判别这些路径，"
                  f"不得把它们计入「判断已被验证」。")
        if args.out:
            json_write(args.out, result)
        return 0
    if args.guard_audit:
        result = guard_audit(Path(args.cases))
        for name, caught in result["guards"].items():
            mark = "守" if caught else "⚠ 无人守"
            print(f"{name:10} {mark:8} {len(caught)} 个案例 → {caught[:6]}")
        if result["baseline_red"]:
            print(f"基线已红（不计入守卫）：{result['baseline_red']}")
        print(f"\n守门审计 {'PASS' if result['ok'] else 'FAIL'} · "
              f"{len(result['guards']) - len(result['unguarded'])}/{len(result['guards'])} 条判据有人守")
        if args.out:
            json_write(args.out, result)
        return 0 if result["ok"] else 1
    report = run(Path(args.cases))
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        report["regression"] = regression(report, baseline)
    _print(report)
    if args.out:
        json_write(args.out, report)
    reg = report.get("regression") or {}
    return 0 if (report["metrics"]["cases_passed"] == report["metrics"]["cases"]
                 and not reg.get("regressed_cases") and not reg.get("missing_cases")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
