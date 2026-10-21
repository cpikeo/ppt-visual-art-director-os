"""案例的边际证据：每个案例独家覆盖了哪些行、整套件删掉会丢掉什么。

存废判据 D6 的取证工具。**注意它不能单独用来删案例**：
判断案例是「测量的样本」，行覆盖衡量的是「代码路径」，两者不同轴——
零独有行只说明这条路径别的案例也走过，不说明这个输入可以被替换。

    python tools/case_coverage.py                       # 全部套件
    python tools/case_coverage.py --suite generalization_cases_r4
    python tools/case_coverage.py --json out.json
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import pathlib
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import intelligence as I  # noqa: E402

BRIEF = {"audience": "内部评审会", "decision": "批准下一步预算"}


class Tracer:
    """行级追踪：只记 scripts/ 下文件的 (文件名, 行号)。"""

    def __enter__(self):
        self.lines: set[tuple[str, int]] = set()
        self._tracer = self._make()
        threading.settrace(self._tracer)
        sys.settrace(self._tracer)
        return self

    def _make(self):
        def local(frame, event, _arg):
            if event == "line" and frame.f_code.co_filename.startswith(str(SCRIPTS)):
                self.lines.add((pathlib.Path(frame.f_code.co_filename).name, frame.f_lineno))
            return local
        return local

    def __exit__(self, *_exc):
        sys.settrace(None)
        threading.settrace(None)


def run_case(case: dict) -> None:
    text = f"{case.get('title', '')} {case.get('content', '')}".strip()
    world = I.derive_world(BRIEF, [I.understand(text, content=case.get("content"))])
    I.page_judgment({"id": "p", "title": case.get("title", ""), "content": case.get("content", ""),
                     **({"chart": True} if case.get("chart") else {}),
                     **{k: case[k] for k in ("role", "evidence", "asset") if k in case}},
                    index=case.get("index", 1), total=case.get("total", 3),
                    brief=BRIEF, world=world, warnings=[])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suite", default=None, help="只看某一份案例集（文件名不含 .json）")
    parser.add_argument("--json", dest="json_out", default=None)
    args = parser.parse_args(argv)

    paths = sorted((SCRIPTS / "json").glob("*.json"))
    if args.suite:
        paths = [p for p in paths if p.stem == args.suite]
        if not paths:
            print(f"找不到案例集 {args.suite}", file=sys.stderr)
            return 2

    cov: dict[tuple[str, str], set] = {}
    for path in paths:
        for case in json.loads(path.read_text(encoding="utf-8")).get("cases") or []:
            with Tracer() as tracer:
                run_case(case)
            cov[(path.stem, case["id"])] = tracer.lines

    def unique(keys) -> set:
        own = set().union(*[cov[k] for k in keys]) if keys else set()
        rest = set().union(*[v for k, v in cov.items() if k not in keys])
        return own - rest if len(cov) > len(keys) else own

    by_suite: dict[str, list] = collections.defaultdict(list)
    for key in cov:
        by_suite[key[0]].append(key)
    print(f"案例 {len(cov)} · 套件 {len(by_suite)}")
    print("\n各套件的独有覆盖行（删掉这套就丢掉的行）")
    suites = {}
    for suite, keys in sorted(by_suite.items()):
        own = set().union(*[cov[k] for k in keys])
        uniq = unique(keys)
        suites[suite] = {"lines": len(own), "unique": len(uniq),
                         "unique_by_file": dict(collections.Counter(f for f, _ in uniq))}
        print(f"  {suite:<32} 行 {len(own):>4} · 独有 {len(uniq):>3}")

    zero = [f"{s}/{i}" for (s, i), lines in cov.items() if not unique([(s, i)])]
    low = {f"{s}/{i}": sorted(f"{f}:{l}" for f, l in unique([(s, i)]))
           for (s, i) in cov if 0 < len(unique([(s, i)])) <= 2}
    print(f"\n零独有行的案例：{len(zero)}")
    print(f"独有 1–2 行的案例：{len(low)}")
    for name, lines in list(low.items())[:10]:
        print(f"   {name}: {lines}")

    covered = set().union(*cov.values()) if cov else set()
    src = (SCRIPTS / "intelligence.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    stmt = {n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.stmt)
            and not isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef,
                                   ast.Expr, ast.Import, ast.ImportFrom, ast.Return))}
    hit = {l for f, l in covered if f == "intelligence.py"}
    print(f"\nintelligence.py 语句行 {len(stmt)} · 案例覆盖 {len(stmt & hit)} · "
          f"未覆盖 {len(stmt - hit)}")

    if args.json_out:
        pathlib.Path(args.json_out).write_text(json.dumps(
            {"suites": suites, "zero_unique": zero, "low_unique": low,
             "intelligence_statements": len(stmt), "intelligence_covered": len(stmt & hit)},
            ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
