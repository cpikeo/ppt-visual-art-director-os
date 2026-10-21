"""存废取证：死符号 / 重复实现 / 未用导入 / 重复案例 / 孤儿文件。

只回答「还有没有人用它」与「两份实现是不是逐字相同」这两个机械问题；
**不回答**「看起来没用」。删任何东西之前先跑它，把数字抄进变更说明。

    python tools/dead_code_audit.py            # 全量报告
    python tools/dead_code_audit.py --strict   # 有发现即以 1 退出（可进 CI）

判据与 MAINTENANCE.md「内容存废判据」一一对应：D1 死符号、D2 重复实现、
D3 未用导入、D4 重复案例输入、D5 孤儿文件。
"""
from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import pathlib
import re
import subprocess
import sys

TEXT_SUFFIX = {".py", ".md", ".yml", ".yaml", ".json", ".toml", ".txt"}


def tracked_files(root: pathlib.Path) -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True,
                             text=True, check=True).stdout
        return [line for line in out.splitlines() if line.strip()]
    except (OSError, subprocess.CalledProcessError):
        return [p.relative_to(root).as_posix() for p in sorted(root.rglob("*"))
                if p.is_file() and ".git" not in p.parts]


_CACHE: dict[tuple[str, str], str] = {}


def _read(root: pathlib.Path, rel: str) -> str:
    key = (str(root), rel)
    if key not in _CACHE:
        try:
            _CACHE[key] = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            _CACHE[key] = ""
    return _CACHE[key]


_CORPUS: dict[str, str] = {}


def _corpus(root: pathlib.Path, files: list[str]) -> dict[str, str]:
    global _CORPUS
    if not _CORPUS:
        _CORPUS = {rel: _read(root, rel) for rel in files
                   if pathlib.Path(rel).suffix in TEXT_SUFFIX}
    return _CORPUS


def _module_names(tree: ast.Module) -> list[tuple[int, str]]:
    found = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.append((node.lineno, node.name))
        elif isinstance(node, ast.Assign):
            found += [(node.lineno, t.id) for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found.append((node.lineno, node.target.id))
    return [(line, name) for line, name in found if not name.startswith("__")]


_COUNTS: collections.Counter = collections.Counter()


def _counts(root: pathlib.Path, files: list[str]) -> collections.Counter:
    """整个仓库的标识符计数：一次扫完，之后每个符号的「有没有人提」都是 O(1)。

    32 位十六进制哈希、URL 片段里的词也算进去——宁可漏判死符号，不可误删。
    """
    global _COUNTS
    if not _COUNTS:
        for rel, text in _corpus(root, files).items():
            _COUNTS.update(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", text))
    return _COUNTS


def _references(name: str, own_file: str, root: pathlib.Path, files: list[str]) -> int:
    """定义处不算引用；注释/文档里出现**算**引用（活文档，删了要一起改）。"""
    counts = _counts(root, files)
    total = counts[name]
    own = _read(root, own_file)
    defs = re.findall(rf"^\s*(?:async\s+def|def|class)\s+{re.escape(name)}\b", own, flags=re.M)
    defs += re.findall(rf"^{re.escape(name)}\s*(?::[^=\n]+)?=", own, flags=re.M)
    return total - len(defs)


def dead_symbols(root: pathlib.Path, files: list[str]) -> dict[str, list[tuple[int, str]]]:
    out: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    for rel in files:
        if not rel.endswith(".py") or rel.startswith("tools/"):
            continue
        try:
            tree = ast.parse(_read(root, rel))
        except SyntaxError:
            continue
        for line, name in _module_names(tree):
            if _references(name, rel, root, files) == 0:
                out[rel].append((line, name))
    return dict(out)


def duplicate_functions(root: pathlib.Path, files: list[str]) -> list[list[str]]:
    bodies: dict[str, list[str]] = collections.defaultdict(list)
    for rel in files:
        if not rel.endswith(".py"):
            continue
        try:
            tree = ast.parse(_read(root, rel))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and len(node.body) >= 2:
                dump = ast.dump(ast.Module(body=node.body, type_ignores=[]))
                bodies[hashlib.sha256(dump.encode()).hexdigest()[:12]].append(
                    f"{rel}:{node.name}@{node.lineno}")
    return [v for v in bodies.values() if len(v) > 1]


def unused_imports(root: pathlib.Path, files: list[str]) -> list[str]:
    out = []
    for rel in files:
        if not rel.endswith(".py"):
            continue
        src = _read(root, rel)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        elsewhere = "\n".join(text for other, text in _corpus(root, files).items()
                             if other != rel)
        body_wo_imports = re.sub(r"^(?:from|import)\s.*?$", "", src, flags=re.M)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                    continue                          # 编译器指令，没有「使用」这回事
                for alias in node.names:
                    bound = (alias.asname or alias.name).split(".")[0]
                    if bound == "*":
                        continue
                    used_here = re.search(rf"\b{re.escape(bound)}\b", body_wo_imports)
                    used_elsewhere = re.search(rf"\.{re.escape(bound)}\b", elsewhere)
                    if not used_here and not used_elsewhere:
                        out.append(f"{rel}:{bound}")
    return sorted(set(out))


def duplicate_cases(root: pathlib.Path) -> list[list[str]]:
    seen: dict[str, list[str]] = collections.defaultdict(list)
    for path in sorted((root / "scripts" / "json").glob("*.json")):
        for case in json.loads(path.read_text(encoding="utf-8")).get("cases") or []:
            key = hashlib.sha256(f"{case.get('title','')}|{case.get('content','')}".encode()).hexdigest()
            seen[key].append(f"{path.stem}/{case['id']}")
    return [v for v in seen.values() if len(v) > 1]


def orphan_files(root: pathlib.Path, files: list[str]) -> list[str]:
    """仓库里的文件，在其它任何文件里都没被提到（扩展名无关）。"""
    haystack = "\n".join(_read(root, rel) for rel in files if pathlib.Path(rel).suffix in TEXT_SUFFIX)
    out = []
    for rel in files:
        if rel in (".gitignore", ".gitattributes") or rel.startswith("."):
            continue
        if pathlib.Path(rel).suffix == ".json" and rel.startswith("scripts/json/"):
            continue                                   # 案例集由 CI 目录扫描加载
        if pathlib.Path(rel).name not in haystack and rel not in haystack:
            out.append(rel)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[1]))
    parser.add_argument("--strict", action="store_true", help="有发现即以 1 退出")
    parser.add_argument("--json", dest="json_out", default=None)
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    files = tracked_files(root)
    report = {
        "D1_dead_symbols": {k: [f"{n}@{l}" for l, n in v]
                            for k, v in dead_symbols(root, files).items()},
        "D2_duplicate_functions": duplicate_functions(root, files),
        "D3_unused_imports": unused_imports(root, files),
        "D4_duplicate_cases": duplicate_cases(root),
        "D5_orphan_files": orphan_files(root, files),
    }
    print(f"取证范围：{len(files)} 个受版本控制的文件")
    print("D1 死模块级符号（定义之外零引用）")
    for rel, names in report["D1_dead_symbols"].items() or [("（无）", [])]:
        print(f"   {rel}: {', '.join(names) if names else '无'}")
    for key, title in (("D2_duplicate_functions", "D2 逐字相同的函数实现"),
                       ("D3_unused_imports", "D3 未使用的导入"),
                       ("D4_duplicate_cases", "D4 逐字相同的案例输入"),
                       ("D5_orphan_files", "D5 零引用的文件")):
        rows = report[key]
        print(f"{title}：{len(rows)}")
        for row in rows:
            print(f"   {row}")
    if args.json_out:
        pathlib.Path(args.json_out).write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    findings = sum(len(v) for v in report["D1_dead_symbols"].values()) + \
        sum(len(report[k]) for k in ("D2_duplicate_functions", "D3_unused_imports",
                                     "D4_duplicate_cases", "D5_orphan_files"))
    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
