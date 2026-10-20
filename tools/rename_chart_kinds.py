#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 plan / build 里已退役的 chart_kind 批量改名成 canonical。

为什么需要它：旧名（executive_kpi / trend / horizontal_bar …）在 release 档已经是
硬门（`chart_kind_alias` → CHART_KIND_ALIAS）。手改容易漏掉**该名隐含的默认值**——
`horizontal_bar` 改成 `bar` 却不补 `show_values: false`，图上的数值标签会突然出现，
产物就变了。本工具把「改名 + 补默认」当成一次原子编辑。

支持两种输入，都用**字节偏移**做精确替换，不重排格式：
  *.py   —— ast 找「dict 里 chart_kind/kind 键 = 旧名字符串」的取值节点；
  *.json —— 自带一个只记偏移的 JSON 扫描器（stdlib json 不给位置）。

用法：
    python3 tools/rename_chart_kinds.py plan.json            # 干跑，打印 diff
    python3 tools/rename_chart_kinds.py plan.json --write    # 落盘
    python3 tools/rename_chart_kinds.py build.py out.json    # 一次多个文件
    python3 tools/rename_chart_kinds.py outline/ --write     # 递归目录

退出码：0 = 没有要改的（或已写入）· 1 = 干跑发现待改 · 2 = 输入不可读/不支持，
或改完仍有非字面量写法没改干净（会逐条打印，不会假装成功）。
"""
from __future__ import annotations

import argparse
import re
import ast
import difflib
import json
import sys
from pathlib import Path

DEFAULT_EXCLUDE = {"scripts", "tools", "tests", "__pycache__", ".git", ".venv"}
# 残留扫描用的宽松判据：`"chart_kind": "x"`（JSON / dict）、`chart_kind="x"`（kwargs）。
# 精确改写走 ast/扫描器；这里只负责「改完还有没有漏网的」，宁宽勿窄。
_QUOTE = "[" + chr(34) + chr(39) + "]"
_KIND_REF = re.compile(_QUOTE + "?(?:chart_kind|kind)" + _QUOTE + "?"
                       + "[ \t]*[=:][ \t]*" + _QUOTE + "([a-z_]+)" + _QUOTE)


def _aliases(scripts: Path) -> dict[str, tuple[str, dict]]:
    """退役名 → (canonical, 该名隐含的默认值)。9.38 起别名表已删除，这张表只剩
    迁移用途（primitives.RETIRED_CHART_KINDS 也不参与编译）。"""
    sys.path.insert(0, str(scripts))
    from primitives import RETIRED_CHART_KINDS
    return dict(RETIRED_CHART_KINDS)


def _apply(text: str, edits: list[tuple[int, int, str]]) -> str:
    """按字节偏移落编辑（edits 的 start/end 是 UTF-8 字节位置）。"""
    raw = text.encode("utf-8")
    for start, end, new in sorted(edits, key=lambda e: e[0], reverse=True):
        raw = raw[:start] + new.encode("utf-8") + raw[end:]
    return raw.decode("utf-8")


def _py_edits(text: str, aliases: dict):
    """ast：只改 dict 里 chart_kind/kind 的值，并在缺省时补隐含字段。

    注意字面量语法：.py 里要写 True/False（repr），.json 里是 true/false
    （json.dumps）。写混了不是格式问题，是 NameError / 非法 JSON。
    """
    tree = ast.parse(text)
    raw = text.encode("utf-8")
    line_starts: list[int] = [0]
    for line in raw.split(b"\n")[:-1]:
        line_starts.append(line_starts[-1] + len(line) + 1)

    def off(lineno: int, col: int) -> int:
        # ast 的 col_offset 是 UTF-8 字节偏移（CPython 文档保证），与 raw 一致。
        return line_starts[lineno - 1] + col

    edits: list[tuple[int, int, str]] = []
    renames: list[tuple[str, str, dict]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict) or not node.keys:
            continue
        keys = [k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        for key_node, val_node in zip(node.keys, node.values):
            if not (isinstance(key_node, ast.Constant)
                    and key_node.value in ("chart_kind", "kind")
                    and isinstance(val_node, ast.Constant)
                    and isinstance(val_node.value, str)):
                continue
            name = val_node.value.strip().lower()
            if name not in aliases:
                continue
            canonical, implied = aliases[name]
            start = off(val_node.lineno, val_node.col_offset)
            end = off(val_node.end_lineno, val_node.end_col_offset)
            edits.append((start, end, json.dumps(canonical)))  # 双引号字符串字面量
            missing = {k: v for k, v in implied.items() if k not in keys}
            if missing:
                body = "".join(f', "{k}": {v!r}' for k, v in missing.items())
                edits.append((end, end, body))
            renames.append((name, canonical, missing))

    # `dict(chart_kind="horizontal_bar", ...)` 这种关键字写法：同一个语义，另一种语法。
    # 不覆盖它，作者会看到「没有旧名」却在 release 被拦——工具的可信度比覆盖率更重要。
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        present = {kw.arg for kw in node.keywords if kw.arg}
        for kw in node.keywords:
            if kw.arg not in ("chart_kind", "kind"):
                continue
            if not (isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)):
                continue
            name = kw.value.value.strip().lower()
            if name not in aliases:
                continue
            canonical, implied = aliases[name]
            start = off(kw.value.lineno, kw.value.col_offset)
            end = off(kw.value.end_lineno, kw.value.end_col_offset)
            edits.append((start, end, json.dumps(canonical)))
            missing = {k: v for k, v in implied.items() if k not in present}
            if missing:
                body = "".join(f", {k}={v!r}" for k, v in missing.items())
                edits.append((end, end, body))
            renames.append((name, canonical, missing))
    return edits, renames


def _json_scan(text: str) -> list[tuple[int, list]]:
    """只记位置的 JSON 扫描：返回 [(对象起始, [(key, 值起点, 值终点, 值文本)])]。"""
    n = len(text)

    def ws(i: int) -> int:
        while i < n and text[i] in " \t\r\n":
            i += 1
        return i

    def string_end(i: int) -> int:
        j = i + 1
        while j < n:
            c = text[j]
            if c == "\\":
                j += 2
                continue
            if c == '"':
                return j + 1
            j += 1
        raise ValueError("字符串未闭合")

    found: list[tuple[int, list]] = []

    def value(i: int) -> int:
        i = ws(i)
        c = text[i]
        if c == "{":
            return obj(i)
        if c == "[":
            i = ws(i + 1)
            if text[i] == "]":
                return i + 1
            while True:
                i = ws(value(i))
                if text[i] == ",":
                    i = ws(i + 1)
                    continue
                if text[i] == "]":
                    return i + 1
                raise ValueError(f"数组格式异常 @{i}")
        if c == '"':
            return string_end(i)
        j = i
        while j < n and text[j] not in ",]} \t\r\n":
            j += 1
        return j

    def obj(i: int) -> int:
        start, members = i, []
        i = ws(i + 1)
        if text[i] == "}":
            found.append((start, members))
            return i + 1
        while True:
            i = ws(i)
            key_end = string_end(i)
            key = json.loads(text[i:key_end])
            i = ws(key_end)
            if text[i] != ":":
                raise ValueError(f"缺少冒号 @{i}")
            vstart = ws(i + 1)
            vend = value(vstart)
            members.append((key, vstart, vend, text[vstart:vend]))
            i = ws(vend)
            if text[i] == ",":
                i += 1
                continue
            if text[i] == "}":
                found.append((start, members))
                return i + 1
            raise ValueError(f"对象格式异常 @{i}")

    value(0)
    return found


def _json_edits(text: str, aliases: dict):
    """JSON 版：扫描器给的是**字符**下标，落编辑前换成字节偏移（与 _apply 一致）。"""
    chars: list[tuple[int, int, str]] = []
    renames: list[tuple[str, str, dict]] = []
    for _start, members in _json_scan(text):
        keys = {k for k, *_ in members}
        for key, vstart, vend, raw_value in members:
            if key not in ("chart_kind", "kind") or not raw_value.startswith('"'):
                continue
            try:
                name = json.loads(raw_value).strip().lower()
            except ValueError:
                continue
            if name not in aliases:
                continue
            canonical, implied = aliases[name]
            chars.append((vstart, vend, json.dumps(canonical)))
            missing = {k: v for k, v in implied.items() if k not in keys}
            if missing:
                body = "".join(f', {json.dumps(k)}: {json.dumps(v)}'
                               for k, v in missing.items())
                chars.append((vend, vend, body))
            renames.append((name, canonical, missing))

    def _b(i: int) -> int:
        return len(text[:i].encode("utf-8"))

    edits = [(_b(s), _b(e), new) for s, e, new in chars]
    return edits, renames


def _audit(root: Path, aliases: dict) -> int:
    """扫**输入文件**（.py/.json/.yml/.yaml）里还有没有退役名。

    文档（.md）不在此列：CHANGELOG 与契约本来就要写「哪些名字退役了」。
    默认跳过定义了这张表的 scripts/ 与 tools/——它们是规则的来源，不是使用者。
    """
    hits: list[tuple[Path, int, str]] = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in (".py", ".json", ".yml", ".yaml"):
            continue
        if set(path.parts) & {".git", ".venv", "node_modules", "__pycache__",
                              "scripts", "tools"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in _KIND_REF.finditer(text):
            if m.group(1) in aliases:
                hits.append((path, text.count("\n", 0, m.start()) + 1, m.group(1)))
    for path, line, name in hits:
        print(f"{path}:{line}: {name} → {aliases[name][0]}")
    if hits:
        print(f"迁移未完成：{len(hits)} 处退役名（{len({h[0] for h in hits})} 个文件）。")
        return 1
    print(f"迁移完成：{root} 下的输入文件没有退役 chart_kind。")
    return 0


def _files(targets: list[str]) -> list[Path]:
    out: list[Path] = []
    for t in targets:
        p = Path(t).expanduser()
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.suffix in (".py", ".json") and not (set(child.parts) & DEFAULT_EXCLUDE):
                    out.append(child)
        elif p.suffix in (".py", ".json"):
            out.append(p)
        else:
            print(f"跳过（只支持 .py / .json）：{p}", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="旧 chart_kind 批量改名（含隐含默认值）")
    ap.add_argument("paths", nargs="*", help="plan/build 文件或目录")
    ap.add_argument("--write", action="store_true", help="落盘；默认只打印 diff")
    ap.add_argument("--scripts", default=str(Path(__file__).resolve().parents[1] / "scripts"),
                    help="primitive 层所在目录（默认本仓库 scripts/）")
    ap.add_argument("--audit", metavar="ROOT", default="",
                    help="只审计不修改：扫描 ROOT 下的输入文件，有退役名则退出码 1")
    args = ap.parse_args()

    aliases = _aliases(Path(args.scripts).resolve())
    if args.audit:
        return _audit(Path(args.audit).expanduser().resolve(), aliases)
    pending = 0
    touched = 0
    unresolved = 0
    for path in _files(args.paths):
        try:
            text = path.read_text(encoding="utf-8")
            edits, renames = (_py_edits if path.suffix == ".py"
                              else _json_edits)(text, aliases)
        except (OSError, SyntaxError, ValueError) as exc:
            print(f"{path}: 读不了/解析失败（{exc}）", file=sys.stderr)
            return 2
        updated = _apply(text, edits) if edits else text
        # 改完再扫一遍：`dict(chart_kind="horizontal_bar")`、变量拼接、跨文件拼装
        # 这类写法 ast 认不出是字面量。宁可明说「还有几处要手工改」，也不能让作者
        # 以为工具跑过就干净了——release 门会照样拦下来。
        leftover = sum(1 for m in _KIND_REF.finditer(updated) if m.group(1) in aliases)
        if not edits and not leftover:
            continue
        if edits:
            pending += 1
            diff = list(difflib.unified_diff(text.splitlines(True), updated.splitlines(True),
                                             fromfile=str(path),
                                             tofile=str(path) + "（改后）", n=1))
            rendered = "".join(diff)
            print(rendered if rendered.endswith("\n") else rendered + "\n", end="")
            seen: set[str] = set()
            for old, canonical, missing in renames:
                if old in seen:
                    continue
                seen.add(old)
                extra = ("，补 " + ", ".join(f"{k}={v!r}" for k, v in missing.items())
                         if missing else "")
                print(f"  · {path}: {old} → {canonical}{extra}")
        if leftover:
            print(f"  ! {path}: 仍有 {leftover} 处未能自动改（不是 dict 字面量？）"
                  f"，请手工处理", file=sys.stderr)
            unresolved += 1
        if args.write and edits:
            path.write_text(updated, encoding="utf-8")
            touched += 1
    if args.write:
        print(f"已写入 {touched} 个文件。")
        return 2 if unresolved else 0
    if pending:
        print(f"干跑：{pending} 个文件待改（加 --write 落盘）。")
        return 1
    if unresolved:
        print(f"干跑：{unresolved} 个文件有旧名但无法自动改（不会动文件）。")
        return 1
    print("没有旧名，无需修改。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
