# -*- coding: utf-8 -*-
"""
Layer 0 · Primitives（基础层）

职责：单位换算、色彩数学与色阶推导、字体绑定、几何，以及层间契约 `RenderContext`。

本层不知道 spec 的结构，不知道元素语义，不知道图表类型。
它只提供「怎么把一段文字/一个形状画到画布上」的最小能力。

依赖方向：primitives ← elements / charts ← compiler
本层不反向依赖任何上层，因此可独立演进。
"""
from __future__ import annotations

import hashlib
import math
import re
import sys
from pathlib import Path


def json_write(path, value, *, indent: int = 2, trailing_newline: bool = True,
               fsync: bool = False) -> Path:
    """原子 JSON 写入·全库唯一实现（同目录临时文件 + replace，中断不留半个文件）。

    indent/换行/fsync 是消费方（vao 报告 vs compile_cache 缓存）仅有的口味差；
    原子性语义只住这里。default=str：报告里允许出现 Path 等非 JSON 原生类型。
    """
    import json
    import os
    import tempfile
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    before_ns = None
    try:
        before_ns = target.stat().st_mtime_ns
    except OSError:
        pass
    fd, tmp = tempfile.mkstemp(prefix="." + target.name, dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=indent,
                                    default=str))
            if trailing_newline:
                handle.write("\n")
            if fsync:
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        Path(tmp).unlink(missing_ok=True)
    _stamp_after_write(target, before_ns)
    return target


def execute_module(code, source, name: str):
    """执行明确可信的作者模块；先注册，失败回滚，不使用 pyc。不是沙箱。"""
    import types
    mod = types.ModuleType(name)
    mod.__file__ = str(source)
    previous = sys.modules.get(name)
    sys.modules[name] = mod
    try:
        exec(code, mod.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    return mod


class PathConflictError(ValueError):
    """不能落修复包的路径冲突：诊断写入本身也可能覆盖输入。"""


def validate_io_paths(reads: dict, writes: dict, *, managed_dirs: dict | None = None) -> None:
    """写入前拒绝输入/输出及输出彼此别名（含现有符号链接与硬链接）。

    只检查本次明确的文件集合，不限制作者选择工作目录；不是不可信目录的沙箱。
    """
    inputs = [(name, Path(path).expanduser().resolve()) for name, path in reads.items() if path]
    outputs = [(name, Path(path).expanduser().resolve()) for name, path in writes.items() if path]

    def same(a, b):
        if a == b:
            return True
        try:
            return a.samefile(b)
        except OSError:
            return False

    for index, (name, path) in enumerate(outputs):
        for other, source in inputs + outputs[:index]:
            if same(path, source):
                raise PathConflictError(f"路径冲突：{name} 与 {other} 指向同一文件 {path}；未写入任何产物")

    # 预览会批量写入/清理页图，编译缓存有派生文件名：整个目录都必须专用。
    # 先做包含关系检查，再检查已有链接；不能等写进辅助文件后才发现它是输入。
    directories = [(name, Path(path).expanduser().resolve())
                   for name, path in (managed_dirs or {}).items() if path]
    for index, (name, directory) in enumerate(directories):
        for other, path in inputs + outputs:
            if path == directory or path.is_relative_to(directory):
                raise PathConflictError(f"路径冲突：{other} 位于 {name} 专用目录 {directory}；未写入任何产物")
        for other, path in directories[:index]:
            if directory == path or directory.is_relative_to(path) or path.is_relative_to(directory):
                raise PathConflictError(f"路径冲突：{name} 与 {other} 专用目录重叠；未写入任何产物")
        if directory.exists() and not directory.is_dir():
            continue  # 缓存目录被文件占位：调用方仍可诊断并回落完整编译，不覆盖它
        for child in directory.rglob("*"):
            if child.is_symlink() or (child.is_file() and child.stat().st_nlink > 1):
                raise PathConflictError(f"辅助目录含链接文件/目录，可能覆盖外部数据：{child}；未写入任何产物")


def _stamp_after_write(target: Path, before_ns: int | None) -> None:
    """写入后保证 mtime_ns 严格前进（本库的「字节变了吗」凭证是 size+mtime_ns）。

    文件系统的时间戳粒度可能粗到几毫秒（容器/网络盘实测 4ms），同一刻度内的两次写盘
    会拿到同一个 mtime——此时「读一次」的缓存与编译缓存探测都会误判成「没变」。
    写入者在这里把凭证往前推 1ns：不是伪造时间，而是让两次真实写盘可区分。
    """
    import os
    try:
        after_ns = target.stat().st_mtime_ns
        if before_ns is not None and after_ns <= before_ns:
            os.utime(target, ns=(before_ns + 1, before_ns + 1))
    except OSError:
        # 时间戳只服务缓存判定；推不动就退化为「按内容重算」，绝不因此让写盘失败。
        pass


def file_digest(path) -> str | None:
    """读取当前字节的 SHA-256；元数据不充当 strict 的内容凭证。

    同尺寸、恢复 mtime、同一 ctime 刻度内的写入在真实文件系统上都可能发生。
    同一轮已在手的摘要由调用方显式传递；不在进程全局猜测磁盘未变。
    """
    try:
        h = hashlib.sha256()
        with Path(path).expanduser().open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, TypeError, ValueError):
        return None


# ══════════════════════════════════════════════════════════════════════════
# 身份（Identity）：全库唯一的「同一事实 → 同一个值」入口
#
# 运行时只承认三类事实，每一类都只有一个 canonical 表达，别处不许再各写一遍
# json.dumps / hashlib.sha256（此前同一件事有 4–5 份独立实现，这正是重复劳动的源头）：
#
#   1) 值 / 内容的身份      identity(value, schema=...)     规范 JSON → sha256
#      记录级摘要（清单、计划、spec）传 schema=None，字节与历史一致；
#      缓存键传 schema 字符串，多一层键空间包裹，格式变更时改 schema 即可作废旧键。
#   2) 字节的身份           digest_bytes(blob) / file_digest(path)
#   3) 「还是那一份」的凭证  witness(path) + witness_same(a, b, strict=)
#      size + mtime_ns 是快档凭证，strict 时再比 sha256——**同一套口径**，
#      报告里也只允许一种写法：witness = {size, mtime_ns, sha256?}
#
# 还有第四类：**产出这些证据的代码**的身份 → engine_fingerprint(scope)。
# ══════════════════════════════════════════════════════════════════════════


def identity(value, *, schema: str | None = None, short: int | None = None) -> str:
    """规范 JSON → sha256（全库唯一实现）。

    `schema=None`：记录级摘要，字节与历史 `asset_workflow.digest` 完全一致——
    既有清单 / 计划里存的值不会因为这次统一而失效。
    `schema="..."`：缓存键空间，值被 {schema, value} 包裹——键的语义变更只需改 schema，
    不必去猜旧值当年是怎么算的。
    """
    import json
    payload = {"schema": schema, "value": value} if schema else value
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), default=str)
    except Exception:                       # 循环引用 / 不可序列化：退化到 repr，仍可辨版
        raw = repr(payload)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest if not short else digest[:int(short)]


def digest_bytes(blob: bytes | bytearray | memoryview) -> str:
    """内存字节的 sha256。字节在手上时用这个，不要各自 `hashlib.sha256(...)`。"""
    return hashlib.sha256(bytes(blob)).hexdigest()


def witness(path) -> dict:
    """规范化字节凭证 {size, mtime_ns}：证据 / 缓存记录里只允许这一种写法。

    读不到时给 None 值——调用方把 None 当「文件不存在」，不当空串。
    """
    try:
        stat = Path(path).stat()
        return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    except (OSError, TypeError, ValueError):
        return {"size": None, "mtime_ns": None}


def witness_same(a, b, *, strict: bool = False) -> bool:
    """两份凭证是不是同一份字节。

    快档只看 size + mtime_ns；`strict=True` 再比 sha256（缺任一侧的 sha256 即不算匹配）。
    判据只住在这里：调用点各自写 `a.get("file_size") == b.get(...)` 的那种事不再发生。
    """
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    if (a.get("size") is None or b.get("size") is None
            or a.get("size") != b.get("size") or a.get("mtime_ns") != b.get("mtime_ns")):
        return False
    if strict:
        sha_a, sha_b = a.get("sha256"), b.get("sha256")
        return bool(sha_a) and bool(sha_b) and sha_a == sha_b
    return True


# ── 引擎身份：产出证据的代码 ───────────────────────────────────────────────
# 一个 scope → 一份文件集合。指纹随实现一起变：文件字节变了，指纹就变。
# 缓存 / 证据只允许问「哪个 scope」，不允许自己列文件再各算一遍摘要。
ENGINE_SCOPES: dict[str, tuple[str, ...]] = {
    # 预览代码不参与 OOXML 编译；只动 ghost 不该废掉已验证的原生 PPTX。
    "compile": ("compiler.py", "primitives.py"),
    # 预览的颜色/排版原语来自 primitives；只看 ghost 会把原语变化误判为像素未变。
    "preview": ("ghost.py", "primitives.py"),
    "measure": ("assets.py", "primitives.py"),
}
_ENGINE_CACHE: dict[tuple[str, int | None], str] = {}


def engine_fingerprint(scope: str, *, short: int | None = None) -> str:
    """引擎指纹（进程内一次）：产出证据的代码变了，指纹就必须变。

    实现 = 该 scope 的文件集合逐文件 sha256 → 一次身份计算；没有第二级见证协议。
    截断由消费方按需处理（同一 scope 不再各算一份短指纹）。
    """
    key = (scope, short)
    hit = _ENGINE_CACHE.get(key)
    if hit is not None:
        return hit
    files = ENGINE_SCOPES.get(scope)
    if files is None:
        raise KeyError(f"未知引擎 scope: {scope}（合法值 {sorted(ENGINE_SCOPES)}）")
    root = Path(__file__).resolve().parent
    value = identity({name: file_digest(root / name) for name in files},
                     schema=f"vao-engine-{scope}-v1", short=short)
    _ENGINE_CACHE[key] = value
    return value


# ── 预览字体事实与身份（零 PIL / 零 Office 依赖）───────────────────────────
PREVIEW_FONT_CANDIDATES = {
    "latin": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/Library/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ),
    "latin_serif": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
        "/Library/Fonts/Times New Roman.ttf",
        "C:/Windows/Fonts/times.ttf",
    ),
    "cjk": (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/msyh.ttc",
    ),
    "cjk_serif": (
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/System/Library/Fonts/Songti.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ),
}
# 粗体候选：产物里 PowerPoint 逐 run 真加粗（set_run_font bold=True），预览此前
# **从不**换粗体字面（cjk 分支连 candidates 都不动），于是同一页「产物粗、预览细」，
# 字重反差在预览里根本看不见——保真缺口，与「预览宽容度必须 = 交付链」冲突。
PREVIEW_FONT_BOLD_CANDIDATES = {
    "latin": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ),
    "latin_serif": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
        "/Library/Fonts/Times New Roman Bold.ttf",
        "C:/Windows/Fonts/timesbd.ttf",
    ),
    "cjk": (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
    ),
    "cjk_serif": (
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
        "/System/Library/Fonts/Songti.ttc",
        "C:/Windows/Fonts/simsunb.ttf",
    ),
}


def preview_font_names(base: str, bold: bool) -> tuple:
    """加载与缓存身份共用同一个候选顺序；粗体失败仍可回落常规字面。"""
    return (PREVIEW_FONT_BOLD_CANDIDATES[base] if bold else ()) + PREVIEW_FONT_CANDIDATES[base]


_PREVIEW_FONT_STAMP: str | None = None


def preview_font_stamp(*, refresh: bool = False) -> str:
    """常规/粗体所有候选的 stat 身份；每轮入口刷新，页内直接复用。

    记录所有候选而非第一个存在的文件：前者可能损坏而由下一字面接手。
    字体对象层按本身份切换缓存与回落台账，不复用旧像素。
    """
    global _PREVIEW_FONT_STAMP
    if refresh or _PREVIEW_FONT_STAMP is None:
        parts = []
        for role in sorted(PREVIEW_FONT_CANDIDATES):
            for bold in (False, True):
                candidates = []
                for name in preview_font_names(role, bold):
                    try:
                        st = Path(name).stat()
                        state = (st.st_size, st.st_mtime_ns, st.st_ctime_ns)
                    except OSError:
                        state = None
                    candidates.append((name, state))
                parts.append((role, bold, candidates))
        stamp = repr(parts)
        _PREVIEW_FONT_STAMP = stamp
    return _PREVIEW_FONT_STAMP


# ── python-pptx 延迟加载（契约，别改回顶层 import）────────────────────
# 本层被 guard / normalizer / qa 复用，而它们**只处理 spec 数据**：draft 一轮
# 真正的判断成本是 2.8ms，pptx 的 import 却要 150ms（pptx.api → opc → oxml →
# xml.sax → urllib.request）。把整套 Presentation API 拖进「读数据」的路径是
# 架构错误，所以这里只在真的要用 pptx 对象时才解析（`_p()`，进程内缓存一次）。
# 颜色是唯一的跨层对象：ghost 预览（PIL）也走 parse_token，但只用元组与
# `str()`——因此 pptx 未加载时 `parse_token` / `fallback_ink` 产 RGB 等价对象
# （同是 3 元组、str() 同为 'RRGGBB'），**零导入**；pptx 已加载（编译进程内）
# 则照旧产真 RGBColor，`.rgb =` 边界的 isinstance 校验不受影响。规则：等价
# 对象只存在于没有 pptx 的进程里，那里没有任何代码会把它赋给 pptx API。
# 自检 `import_contract` 断言 draft/spec/纯预览进程内不得出现 pptx / lxml /
# compiler —— 谁把 `from pptx import ...` 放回本层顶部，立刻失败。
_PPTX: dict | None = None


class RGB(tuple):
    """RGBColor 的零导入等价对象（仅当 pptx 未加载时由 `_rgb_new` 产出）。

    与 pptx.dml.color.RGBColor 同为 0-255 三元组、str() 同为 'RRGGBB'；
    tuple 子类所以索引/迭代/相等与真对象一致。不要在 pptx 已加载的进程里
    手工构造它——编译边界（`*.rgb =`）做 isinstance 校验，只收真 RGBColor。
    """

    __slots__ = ()

    def __str__(self) -> str:
        return "%02X%02X%02X" % self


def _rgb_new(r: int, g: int, b: int):
    """按进程状态产颜色对象：pptx 已加载 → 真 RGBColor；否则等价元组（不导入）。"""
    if _PPTX is not None:
        return _PPTX["RGBColor"](r, g, b)
    if "pptx.dml.color" in sys.modules:
        return sys.modules["pptx.dml.color"].RGBColor(r, g, b)
    return RGB((int(r), int(g), int(b)))


def _p() -> dict:
    """pptx 符号表的延迟入口：只在编译/渲染路径被调用。"""
    global _PPTX
    if _PPTX is None:
        from pptx.util import Emu, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
        from pptx.oxml import parse_xml
        from pptx.oxml.ns import qn, nsdecls
        _PPTX = {"Emu": Emu, "Pt": Pt, "RGBColor": RGBColor,
                 "PP_ALIGN": PP_ALIGN, "MSO_ANCHOR": MSO_ANCHOR,
                 "parse_xml": parse_xml, "qn": qn, "nsdecls": nsdecls}
    return _PPTX

# 1280 design px -> 13.333 in (12192000 EMU)
PX_TO_EMU = 9525
# 元素类型单真源（compiler.DISPATCH 的键与此对齐；guard 白名单校验引用它。
# spec 档禁加载编译层，集合不能住在编译层——未知 type 会在编译期被静默跳过，
# 必须在治理层前置拦截）。
ELEMENT_TYPES = frozenset({"text", "shape", "image", "chart", "native_chart"})
# 图表单一规范（全库唯一权威）：每个 kind 只在这里定义一次五维事实——
#   renderer  编译路由：native（原生图表）/ shape（可编辑形状图）/ kpi（元素级大数字）
#   payload   载荷形态：rows（data 行，可多序列）/ points / layers / value（元素级）
#   numeric   是否数值图（出处硬门、单位与有限值校验的适用面）
#   limit     截断型硬限额（实现只能完整呈现前 N 项）；None = 不截断
#   preview   ghost 口径：mirrored（同形绘制）/ abstract（只留占位实话，不画假图）
# 此前这五维分别抄在 verify（3 个集合 + limits 字典）、compiler（3 个集合 + 8 处
# 截断字面量）、ghost（占位表 + 6 处截断字面量）与 contract.md（两段枚举）里，
# 任一处漏改就出现「guard 放行但编译截尾 / 预览与产物不一致」。现在各层只派生、
# 不再各写一份；增删 kind 只改这一张表（selftest 的 chart_spec 断言锁定派生关系）。
CHART_SPEC: dict[str, dict] = {
    "kpi":               {"renderer": "kpi",    "payload": "value",  "numeric": False, "limit": None, "preview": "mirrored"},
    "executive_kpi":     {"renderer": "kpi",    "payload": "value",  "numeric": False, "limit": None, "preview": "mirrored"},
    "big_number":        {"renderer": "kpi",    "payload": "value",  "numeric": False, "limit": None, "preview": "mirrored"},
    "big_number_row":    {"renderer": "shape",  "payload": "rows",   "numeric": False, "limit": 5,    "preview": "mirrored"},
    "bar":               {"renderer": "native", "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "horizontal_bar":    {"renderer": "native", "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "column":            {"renderer": "native", "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "comparison_bar":    {"renderer": "native", "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "line":              {"renderer": "native", "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "trend":             {"renderer": "native", "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "single_trend_line": {"renderer": "native", "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "area":              {"renderer": "native", "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "donut":             {"renderer": "native", "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "donut_composition": {"renderer": "native", "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "pie":               {"renderer": "native", "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "waterfall":         {"renderer": "shape",  "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
    "ranked_bar":        {"renderer": "shape",  "payload": "rows",   "numeric": True,  "limit": 8,    "preview": "mirrored"},
    "progress_bar":      {"renderer": "shape",  "payload": "rows",   "numeric": True,  "limit": 6,    "preview": "mirrored"},
    "stacked_bar":       {"renderer": "shape",  "payload": "rows",   "numeric": True,  "limit": 8,    "preview": "mirrored"},
    "bubble":            {"renderer": "shape",  "payload": "rows",   "numeric": True,  "limit": 12,   "preview": "abstract"},
    "process_flow":      {"renderer": "shape",  "payload": "rows",   "numeric": False, "limit": 7,    "preview": "abstract"},
    "timeline":          {"renderer": "shape",  "payload": "rows",   "numeric": False, "limit": 7,    "preview": "mirrored"},
    "steps":             {"renderer": "shape",  "payload": "rows",   "numeric": False, "limit": 6,    "preview": "mirrored"},
    "matrix":            {"renderer": "shape",  "payload": "points", "numeric": False, "limit": 12,   "preview": "mirrored"},
    "architecture":      {"renderer": "shape",  "payload": "layers", "numeric": False, "limit": 3,    "preview": "abstract"},
    "sparkline":         {"renderer": "shape",  "payload": "rows",   "numeric": True,  "limit": None, "preview": "mirrored"},
}
CHART_KINDS = frozenset(CHART_SPEC)
NUMERIC_CHART_KINDS = frozenset(k for k, v in CHART_SPEC.items() if v["numeric"])
ROWS_CHART_KINDS = tuple(k for k, v in CHART_SPEC.items() if v["payload"] == "rows")
ELEMENT_VALUE_KINDS = tuple(k for k, v in CHART_SPEC.items() if v["payload"] == "value")
ELEMENT_PAYLOAD_KINDS = frozenset(k for k, v in CHART_SPEC.items()
                                  if v["payload"] in ("points", "layers"))
CHART_LIMITS = {k: v["limit"] for k, v in CHART_SPEC.items() if v["limit"] is not None}
PREVIEW_ABSTRACT_KINDS = frozenset(k for k, v in CHART_SPEC.items()
                                   if v["preview"] == "abstract")


def chart_rows(element: dict) -> list[dict]:
    """图表 data 行的唯一规范化（compiler 与 ghost 共用，口径不再分叉）。

    保留无效值状态（missing / invalid），禁止把坏数据静默当作 0；
    `desc` 说明行必须保留——丢弃它会让下游的说明分支成为死代码。
    多序列（categories + series）的展开是预览的呈现适配，不在此处：
    原生路径按序列消费，预览按「类别 × 序列」压平（见 ghost._rows）。
    """
    data = (element or {}).get("data", []) or []
    rows = []
    for i, it in enumerate(data):
        if isinstance(it, dict) and "label" in it:
            raw = it.get("value")
            missing = raw is None
            invalid = False
            try:
                if isinstance(raw, bool):
                    raise ValueError
                num = float(raw) if raw is not None else 0.0
                invalid = not math.isfinite(num)
            except (TypeError, ValueError, OverflowError):
                num, invalid = 0.0, not missing
            if invalid:
                num = 0.0
            display = it.get("display")
            if display is None:
                display = raw if isinstance(raw, str) else (
                    int(num) if float(num).is_integer() else num)
            rows.append({"label": str(it["label"]), "value": num,
                         "display": display, "desc": it.get("desc"), "_index": i,
                         "missing": missing, "invalid": invalid})
        elif (isinstance(it, (int, float)) and not isinstance(it, bool)
              and math.isfinite(float(it))):
            rows.append({"label": str(i), "value": float(it), "display": it,
                         "_index": i, "missing": False, "invalid": False})
    return rows

def highlight_index(element, rows, default: int = -1) -> int:
    """强调项解析：整数索引，或直接写类别名。

    作者更可能说「强调海外」而不是「强调第 1 项」；写名字却被静默忽略
    （或渲染层自作主张强调最大值），就是「看起来在判断、其实没判断」。
    编译器与预览渲染器共用这一个语义。
    """
    raw = element.get("highlight") if isinstance(element, dict) else None
    if raw is None:
        return default
    text = str(raw).strip()
    for i, row in enumerate(rows or []):
        if isinstance(row, dict) and str(row.get("label", "")).strip() == text:
            try:
                return int(row.get("_index", i))
            except (TypeError, ValueError):
                return i
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def resolve_chart_highlight(element, categories=None, series_names=None) -> tuple[int, int]:
    """categories + series 载荷上 highlight 的双命名空间消歧（全库唯一口径）。

    返回 (series_index, point_index)，未命中一侧为 -1（不会两侧同时命中）。一个
    字段同时被序列名与类别名认领，不给消歧就必然出现「写了强调却静默不落」或
    预览/产物各说各话（9.31.1 登记缺口的根因）。命名先于数字：

    1. 命中**序列名** → 序列级强调（该序列走 accent + 加粗）；
    2. 命中**类别名** → 数据点强调（该类目在每条序列上的点落 accent，与单序列
       data 路径的逐点强调同一语义）；
    3. 整数：多序列（≥2 条）指序列索引，单序列（含单条 series 的写法）指数据点
       索引（与 `highlight_index` 在 data 载荷上的既有契约一致）；
    4. 都不命中（名字写错、索引越界、非数字）→ (-1, -1)，由调用方按「不静默」
       原则处置（guard 发 chart_highlight 告警，不替作者猜强调对象）。

    这是全库唯一的 highlight 入口：旧的 `series_highlight_index`（只认序列名/索引）
    已被它吸收并删除——同一件事两个入口，迟早在某一层分叉成两套语义。
    """
    if not isinstance(element, dict):
        return -1, -1
    raw = element.get("highlight")
    if raw is None:
        return -1, -1
    text = str(raw).strip()
    names = [str(n).strip() for n in (series_names or [])]
    cats = [str(c).strip() for c in (categories or [])]
    for i, name in enumerate(names):
        if name and name == text:
            return i, -1
    for i, cat in enumerate(cats):
        if cat and cat == text:
            return -1, i
    try:
        idx = int(raw)
    except (TypeError, ValueError):
        return -1, -1
    if len(names) >= 2:
        return (idx, -1) if 0 <= idx < len(names) else (-1, -1)
    return (-1, idx) if 0 <= idx < len(cats) else (-1, -1)


DEFAULT_WIDTH, DEFAULT_HEIGHT = 1280, 720

_ALIGN_KEYS = {"left", "center", "right", "justify"}
_ANCHOR_KEYS = {"top", "middle", "bottom"}
_ALIGN_FALLBACK = {None: "left", "": "left"}
_ANCHOR_FALLBACK = {None: "top", "": "top"}


_ALIGN_ATTR = {"left": "LEFT", "center": "CENTER", "right": "RIGHT",
               "justify": "JUSTIFY"}
_ANCHOR_ATTR = {"top": "TOP", "middle": "MIDDLE", "bottom": "BOTTOM"}


def align_of(value, fallback=None):
    """文本对齐：名字 → pptx 枚举（延迟解析）。未识别的名字交给 fallback。"""
    key = _ALIGN_FALLBACK.get(value, value)
    if key not in _ALIGN_KEYS:
        return fallback
    return getattr(_p()["PP_ALIGN"], _ALIGN_ATTR[key])


def anchor_of(value, fallback=None):
    """垂直锚点：名字 → pptx 枚举（延迟解析）。"""
    key = _ANCHOR_FALLBACK.get(value, value)
    if key not in _ANCHOR_KEYS:
        return fallback
    return getattr(_p()["MSO_ANCHOR"], _ANCHOR_ATTR[key])


# 渲染级安全回落（不是设计观点）：主题未声明字体时保证文件可渲染。
FALLBACK_CN = "Microsoft YaHei"
FALLBACK_LATIN = "Arial"


def color_to_hex(value) -> str | None:
    """RGBColor / #RRGGBB / "RRGGBB" → 六位大写 HEX；解析不出来返回 None。

    与 pptx 类型解耦：既接受真实的 RGBColor（可迭代/str()），也接受纯字符串，
    这样「取对比度」这类判断不依赖 pptx 是否已被加载。
    """
    if value is None:
        return None
    try:
        if isinstance(value, str):
            h = value.lstrip("#").upper()
            return h if len(h) == 6 else None
        if all(isinstance(x, int) for x in value):        # RGBColor 是 int 三元组
            return "".join(f"{c:02X}" for c in value)
    except Exception:
        pass
    try:
        h = str(value).lstrip("#").upper()
        return h if len(h) == 6 else None
    except Exception:
        return None


def fallback_ink():
    """未声明墨色时的安全值（RGBColor 语义；pptx 未加载时为等价对象，不导入）。"""
    return _rgb_new(0x20, 0x20, 0x20)


def image_crop(value) -> tuple:
    """四边裁切比例的物理契约；不允许负裁切伪造有效像素。"""
    if value is None:
        return (0.0, 0.0, 0.0, 0.0)
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("crop 必须为四个有限比例 [left, top, right, bottom]")
    try:
        if any(isinstance(v, bool) for v in value):
            raise ValueError
        crop = tuple(float(v) for v in value)
        if (any(not math.isfinite(v) or not 0 <= v < 1 for v in crop)
                or crop[0] + crop[2] >= 1 or crop[1] + crop[3] >= 1):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ValueError("crop 每边须在 [0,1) 且有限，对边之和必须小于 1") from None
    return crop


def emu(px) -> int:
    return int(round(float(px) * PX_TO_EMU))


# ── 单事实单源（Convergence 2026-09）：以下三个量曾经在别的模块里被重写一遍 ──
LIGHT_BG_LUMINANCE = 0.5     # 背景偏浅的判据（浅底推导 muted_soft / 种子可读性兜底共用）
CHART_LABEL_MIN_H = 190      # 图表标签空间的物理下限（guard 判「装不下」、compiler 判「要不要按政策隐藏」）
CHART_LABEL_MIN_COUNT = 6    # 触发上一条所需的标签数（少于这个数标签本来就放得下）


def text_is_dark(value) -> bool | None:
    """声明的文字色 → 「深字 / 浅字」二值；没声明或读不懂时返回 None。

    为什么必须收在一处（v6.4.3）：QC 的对比度判据要的是「这行字是深的还是浅的」，
    而作者可能写 `text_color: "#E9E4D9"`（产物里真正的颜色）或 `dark` / `light`
    （语义词）。此前只认后两种——写 hex 时声明被静默忽略，判据退回「中间带」规则，
    安全区亮度落在 0.70–0.55 之间就会放过一行**读不出来的浅字**。
    与 `is_light` 同源：同一个亮度阈值，不再各写一份。
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    low = raw.lower()
    if low == "dark":
        return True
    if low == "light":
        return False
    if low.startswith("#") and len(low) in (4, 7):
        try:
            return not is_light(low)
        except Exception:      # noqa: BLE001 —— 脏色值不炸全链，当没声明处理
            return None
    return None


def is_light(hex_color: str) -> bool:
    """背景是否偏浅：唯一判据，浅底/深底的分支都走这里。"""
    return luminance(hex_color) > LIGHT_BG_LUMINANCE


def latin_word_match(text: str, term: str) -> bool:
    """拉丁词的整词匹配（CJK 用子串）。资产层术语判定与色彩 token 判定共用。"""
    import re
    if all(ord(c) < 128 for c in term):
        return re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", text) is not None
    return term in text


# design px → pt：96 DPI 下 1 design px = 0.75 pt。**唯一真源**。
# 需要浮点 pt 的地方（字号写入 set_para_font 等）用 px_to_pt()；
# 需要 Pt 长度对象的地方（直接塞给 python-pptx 属性）用 pt()。
PT_PER_PX = 0.75


def px_to_pt(px) -> float:
    """design px → pt 的纯数值换算（不构造 Pt 对象）。"""
    return float(px) * PT_PER_PX


def pt(px):
    """design px → Pt 长度对象（内部走 px_to_pt，换算只有一处）。"""
    return _p()["Pt"](px_to_pt(px))


# --------------------------------------------------------------------------
# 色彩数学（纯函数，与主题无关）
# --------------------------------------------------------------------------
def _tuple(hex_color: str):
    h = str(hex_color).lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, int(round(c)))) for c in rgb))


# ---------------------------------------------------------------------------
# OKLab 感知均匀色彩空间（Björn Ottosson 2020）
# sRGB 是伽马编码的非线性空间：旧 blend 直接按通道线性插值，中档色会在
# 视觉上偏灰偏浊（「脏色」）——同一份色板，浅档与深档之间的过渡会糊。
# OKLab 的 L 轴近似感知亮度、a/b 轴近似红绿/黄蓝对立色，在 OKLab 里插值
# 得到的中档色明度更均匀、彩度更干净，是「高级感」在色彩层的最低成本来源。
# ---------------------------------------------------------------------------
_OKLAB_M1 = (0.4122214708, 0.5363325363, 0.0514459929)
_OKLAB_M2 = (0.2119034982, 0.6806995451, 0.1073969566)
_OKLAB_M3 = (0.0883024619, 0.2817188376, 0.6299787005)


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    c = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
    return max(0.0, min(1.0, c)) * 255.0


def _rgb_to_oklab(rgb: tuple) -> tuple:
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    l = _OKLAB_M1[0] * r + _OKLAB_M1[1] * g + _OKLAB_M1[2] * b
    m = _OKLAB_M2[0] * r + _OKLAB_M2[1] * g + _OKLAB_M2[2] * b
    s = _OKLAB_M3[0] * r + _OKLAB_M3[1] * g + _OKLAB_M3[2] * b
    l_, m_, s_ = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, a, b


def _oklab_to_rgb(L: float, a: float, b: float) -> tuple:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return (_linear_to_srgb(r), _linear_to_srgb(g), _linear_to_srgb(b))


def blend(a: str, b: str, t: float, space: str = "oklab") -> str:
    """两色混合。默认在 OKLab 感知空间插值（明度/彩度更均匀，中档不脏）；
    space="srgb" 回退到旧的逐通道线性插值（仅当调用方确需精确直通色时使用）。
    """
    ra, rb = _tuple(a), _tuple(b)
    t = max(0.0, min(1.0, t))
    if t <= 0.0:
        return a
    if t >= 1.0:
        return b
    if space == "srgb":
        return _hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))
    La, aa, ba = _rgb_to_oklab(ra)
    Lb, ab, bb = _rgb_to_oklab(rb)
    L = La + (Lb - La) * t
    am = aa + (ab - aa) * t
    bm = ba + (bb - ba) * t
    return _hex(_oklab_to_rgb(L, am, bm))




def luminance(hex_color: str) -> float:
    def ch(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (_tuple(hex_color))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def spec_fingerprint(spec: dict) -> str:
    """spec 的规范化内容指纹（16 hex）。

    报告用它自证来源：QA 盖章，Release Manifest 核对后才会承认
    其中的 PASS。没有一致指纹的「合格」不能进入发布判定。
    """
    try:
        return identity(spec, schema="vao-spec-content-v1", short=16)
    except Exception:                       # 循环引用/不可序列化：退化到键集合，仍可辨版
        keys = sorted(str(k) for k in (spec or {}).keys())
        slides = (spec or {}).get("slides") or []
        return identity((keys, len(slides),
                         [str(s.get("id")) for s in slides if isinstance(s, dict)]),
                        schema="vao-spec-shape-v1", short=16)


# --------------------------------------------------------------------------
# 跨层共享判定（Director：guard / qa 在此收敛为单一口径）
#
# 纯函数：只收显式参数，不读 spec 结构、不读主题 —— 因此 Layer 0 可承载。
# 上层只保留「消息文案 + 严重级别」的呈现权，不再各自实现一遍判定逻辑。
# 同一事实在两处判出两种结论的口径漂移，只能在这里修，不在上层打补丁。
# --------------------------------------------------------------------------
BACKGROUND_LAYERS = frozenset({"background", "backdrop"})


def is_background_declared(element: dict) -> bool:
    """元素是否**声明**为背景层（只读意图，不判断资格）。"""
    e = element or {}
    return (str(e.get("layer", "")).lower() in BACKGROUND_LAYERS
            or str(e.get("role", "")).lower() in BACKGROUND_LAYERS)


def with_alpha(hex_color: str, alpha: float) -> str:
    """生成 #RRGGBBAA（供色板推导使用）。"""
    a = max(0.0, min(1.0, alpha))
    return f"{_hex(_tuple(hex_color))}{format(int(round(a * 255)), '02X')}"


def parse_token(value):
    """-> (RGBColor | RGB | None, alpha | None)；支持 #RGB / #RRGGBB / #RRGGBBAA / none。

    pptx 未加载的进程（纯预览）返回零导入等价对象 RGB，见 `_rgb_new`。
    """
    if value is None:
        return None, None
    t = str(value).strip()
    if t.lower() in ("none", "transparent"):
        return None, None
    if not t.startswith("#"):
        return None, None
    h = t[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None, None
    if len(h) == 8:
        try:
            return _rgb_new(r, g, b), int(h[6:8], 16) / 255.0
        except Exception:
            return None, None
    if len(h) == 6:
        return _rgb_new(r, g, b), None
    return None, None


def derive_tokens(base: dict) -> dict:
    """
    从基础色**机械推导**完整色阶系统 —— 与具体主题无关，任何主题传入都成立。

    这是视觉层次的主要来源：轨道、细线、弱化层、面板微差、色阶、系列色，
    全部由 5 个基础色推导，用透明度制造纵深（而非阴影）。
    """
    def hx(key, fallback=None):
        v = base.get(key) or fallback
        return v if isinstance(v, str) and v.startswith("#") else None

    bg = hx("background") or hx("paper")
    surface = hx("surface") or bg
    primary = hx("primary")
    secondary = hx("secondary") or primary
    accent = hx("accent") or secondary
    premium = hx("premium") or hx("optional") or accent
    ink = hx("ink") or primary
    muted = hx("muted") or secondary
    if not (bg and primary):
        return {}

    out = {}

    def put(key, color, alpha=None):
        if not color:
            return
        out[key] = with_alpha(color, alpha) if alpha is not None else color

    # 层叠表面：与背景拉开极微弱的明度差，形成面板层次
    put("panel", blend(bg, primary, 0.06))
    put("panel_strong", blend(bg, primary, 0.13))
    put("panel_soft", blend(bg, primary, 0.03))
    put("tint", blend(bg, accent, 0.14))

    # 线条 / 轨道 / 弱化层（靠透明度制造层次，而非阴影）
    put("hairline", muted, 0.28)
    put("rule", ink, 0.18)
    put("track", muted, 0.20)
    put("faint", muted, 0.42)
    put("veil", bg, 0.82)
    # muted_soft：浅底上 alpha 会把浅灰推近背景（不可读）；
    # 改为「朝文字色方向微调」，跨主题都保证可读。
    if luminance(bg) > 0.5:  # 浅色主题：muted 向 primary 靠拢（变深）
        put("muted_soft", blend(muted, primary, 0.25))
    else:                    # 深色主题：muted 向 ink 靠拢（变浅）
        put("muted_soft", blend(muted, ink, 0.20))

    # 色阶：单色相明度阶梯（OS §21.1「顺序数据用同一色相的明度阶梯」）。
    # 以 accent 为基相，由浅入深 5 档；灰度打印下仍靠明度差可辨。
    # 中间档（ramp1 / ramp2）按背景明度向更「聚焦」方向拉：
    #   - 浅色主题：ramp1/ramp2 加重（往 ink 靠），让浅底上的中档色块不漂浮
    #   - 深色主题：ramp1/ramp2 提亮（往 bg/inverse 靠），让深底上的中档有重量
    # 末档（ramp5）保持向 ink 推，跨主题稳定。设计意图：让 5 档色阶在
    # 任何主题下「相邻明度差都 ≥ 1.5 个 JND」，避免「看像同一个色」。
    if luminance(bg) > 0.5:
        # 浅色主题：浅档用 accent 自重而非 blend(bg)，避免被背景稀释
        ramp = [blend(bg, accent, 0.40), blend(bg, accent, 0.68), accent,
                blend(accent, ink, 0.42), blend(accent, ink, 0.72)]
    else:
        # 深色主题：浅档往浅色拉（用 ink 提亮而非 bg，避免与背景重合）
        ramp = [blend(bg, accent, 0.22), blend(bg, accent, 0.48), accent,
                blend(accent, ink, 0.42), blend(accent, ink, 0.72)]
    for i, v in enumerate(ramp, 1):
        put(f"ramp{i}", v)

    # 多分类系列色：全部分布在主题信号色及其深浅变体上——
    # 不再用 ink/muted 当填充（黑灰块既沉重又与文字争夺语义）。
    # 深浅目标随背景明度翻转：浅底=深档向 ink、浅档向 bg；
    # 深底=深档向纯黑、浅档向 ink（保证任何主题下相邻系列明度可分）。
    light_bg = luminance(bg) > 0.5
    deep_target = ink if light_bg else "#000000"
    tint_target = bg if light_bg else ink
    if premium == accent:
        # 主题只声明一个信号色（premium 缺省时回退到 accent）——此时原来那六档
        # 只剩三个不同值，每对相邻序列**完全同色**（实测 dark：series1=series2=
        # #C0A062、series3=series4=#5A4A2B、series5=series6=#D3C19F）。后果是
        # 4 段甜甜圈里两段一模一样、双序列折线画成一条线：读者看不出「这是两组
        # 数据」。单信号色主题下序列只能靠明度分层，改为该色相的一条明度阶梯：
        # accent 起、向背景反方向逐档提亮，相邻相对明度差实测 ≥0.06（dark 0.062 /
        # light 0.068），六档互不相同且都落在背景可见范围内。
        series = [accent] + [blend(accent, tint_target, t)
                             for t in (0.18, 0.34, 0.50, 0.66, 0.82)]
    else:
        series = [
            accent,                              # 1 主信号
            premium,                             # 2 次信号（异色相）
            blend(accent, deep_target, 0.42),    # 3 主信号加深
            blend(premium, deep_target, 0.42),   # 4 次信号加深
            blend(accent, tint_target, 0.45),    # 5 主信号提亮
            blend(premium, tint_target, 0.45),   # 6 次信号提亮
        ]
    for i, v in enumerate(series, 1):
        put(f"series{i}", v)

    # 风险色（negative）：图表里 <0 的点只有一个语义——损失。它也必须由主题推导，
    # 否则「六 token 就够」的契约在含负值的图上不成立：作者写完六 token、首轮 check
    # 被硬门挡住，只为补一个引擎自己就能算出来的槽位再跑一轮。
    # 推导口径：以通用风险红为语义锚（保住「红＝损失」的普适读法），向本稿墨色拉近，
    # 落进这一套纸/墨的色相深度里——不是一张从别的稿子飞来的红。
    # 再走一步：强调色本身就是红时，「风险」与「答案」会撞成同一个颜色，于是颜色
    # 不再区分任何东西。此时继续向墨色加深，直到与 accent 在 OKLab 上分得开
    # （阈值取 0.12：实测同族红 t=0.22 只有 0.047，读数上就是同一个色；t≥0.46 起
    #  可辨，且对浅纸的对比度只增不减）。非红强调色在 t=0.22 就已分得开，不加深。
    def _oklab_gap(a: str, b: str) -> float:
        try:
            x, y = _rgb_to_oklab(_tuple(a)), _rgb_to_oklab(_tuple(b))
            return sum((i - j) ** 2 for i, j in zip(x, y)) ** 0.5
        except Exception:
            return 1.0
    risk = blend("#B3261E", ink, 0.22)
    for _t in (0.34, 0.46, 0.58):
        if _oklab_gap(risk, accent) >= 0.12:
            break
        risk = blend("#B3261E", ink, _t)
    put("negative", risk)

    # 特殊表面上的文字色：按对比度自动择优
    pool = [c for c in (bg, surface, primary, secondary, accent, ink) if c]
    dark = hx("dark_surface") or min(pool, key=luminance)
    put("dark_surface", dark)
    put("on_dark", max(pool, key=lambda c: contrast(c, dark)))
    candidates = [c for c in (ink, bg, "#FFFFFF", "#111111") if c]
    put("on_accent", max(candidates, key=lambda c: contrast(c, accent)))

    # 填充色上的文字色：按对比度自动择优，避免「白底白字/黑底黑字」
    # （之前 process_flow 第一个节点在 obsidian 下 fill=primary=#F1F0EB
    #   而 text=ink=#F1F0EB，白底白字不可见。）
    for role, surface in (("on_primary", primary), ("on_secondary", secondary)):
        if not surface: continue
        put(role, max(pool, key=lambda c: contrast(c, surface)))
    return out


# --------------------------------------------------------------------------
# 填充 / 描边（支持透明度与渐变）
# --------------------------------------------------------------------------
def _append_alpha(clr_el, alpha: float) -> None:
    qn = _p()["qn"]
    for old in clr_el.findall(qn("a:alpha")):
        clr_el.remove(old)
    el = clr_el.makeelement(qn("a:alpha"), {"val": str(int(round(alpha * 100000)))})
    clr_el.append(el)


def solid_fill(fill, color, alpha=None) -> None:
    fill.solid()
    fill.fore_color.rgb = color
    if alpha is not None and alpha < 1.0:
        xfill = fill.fore_color._xFill
        clr = xfill.find(_p()["qn"]("a:srgbClr")) if xfill is not None else None
        if clr is not None:
            _append_alpha(clr, alpha)


def _insert_fill_in_order(parent, fill_el) -> None:
    """
    按 OOXML 模式在正确位置插入 fill 元素。

    模式要求：fill 出现在 xfrm/geometry 之后、effects/3D 之前。
    对于 `<p:bgPr>` 没有 pre-fill 子元素，所以插在最前。
    对于 `<p:spPr>` 需要跳过 xfrm/prstGeom/custGeom。
    这样才能避免「effectLst 排在 gradFill 前面」导致的渲染器忽略渐变。
    """
    qn = _p()["qn"]
    pre_fill = {qn("a:xfrm"), qn("a:custGeom"), qn("a:prstGeom")}
    for i, child in enumerate(parent):
        if child.tag in pre_fill:
            continue
        parent.insert(i, fill_el)
        return
    parent.append(fill_el)


def gradient_fill(fill, stops, angle=90.0) -> None:
    """
    stops: [(pos 0–1, "#RRGGBB", alpha|None), ...]  至少 2 个
    angle: 0 = 左→右，90 = 上→下
    """
    parts = []
    for pos, color, alpha in stops:
        rgb = parse_token(color)[0]
        if rgb is None:
            continue
        alpha_xml = ""
        if alpha is not None and alpha < 1.0:
            alpha_xml = f'<a:alpha val="{int(round(alpha * 100000))}"/>'
        parts.append(
            f'<a:gs pos="{int(round(max(0.0, min(1.0, pos)) * 100000))}">'
            f'<a:srgbClr val="{rgb}">{alpha_xml}</a:srgbClr></a:gs>')
    if len(parts) < 2:
        solid_fill(fill, parse_token(stops[0][1])[0] or fallback_ink(),
                   stops[0][2] if len(stops[0]) > 2 else None)
        return
    P = _p()
    xml = (f'<a:gradFill {P["nsdecls"]("a")} rotWithShape="1">'
           f'<a:gsLst>{"".join(parts)}</a:gsLst>'
           f'<a:lin ang="{int(round(angle * 60000))}" scaled="1"/>'
           f'</a:gradFill>')
    spPr = fill._xPr
    for tag in ("a:noFill", "a:solidFill", "a:gradFill", "a:blipFill",
                "a:pattFill", "a:grpFill"):
        for el in spPr.findall(P["qn"](tag)):
            spPr.remove(el)
    _insert_fill_in_order(spPr, P["parse_xml"](xml))


def stroke_color(line, color, alpha=None, width=None) -> None:
    line.color.rgb = color
    if alpha is not None and alpha < 1.0:
        xfill = line.color._xFill
        clr = xfill.find(_p()["qn"]("a:srgbClr")) if xfill is not None else None
        if clr is not None:
            _append_alpha(clr, alpha)
    if width is not None:
        line.width = _p()["Emu"](emu(width))




# 内容身份复用 JSON 解析，不以 size/mtime 推断字节相同。
_JSON_CACHE: dict[str, tuple[str, dict]] = {}


def json_read_cached(path) -> dict:
    """读取当前字节；内容相同时复用解析结果。失败不缓存。"""
    import json
    target = Path(path).expanduser().resolve()
    raw = target.read_bytes()
    digest = digest_bytes(raw)
    key = str(target)
    hit = _JSON_CACHE.get(key)
    if hit is not None and hit[0] == digest:
        return hit[1]
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须为对象: {path}")
    if len(_JSON_CACHE) >= 512:
        _JSON_CACHE.clear()
    _JSON_CACHE[key] = (digest, value)
    return value


# --------------------------------------------------------------------------
# 文本
# --------------------------------------------------------------------------
def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x3000 <= o <= 0x9FFF) or (0xFF00 <= o <= 0xFFEF) or (0x3040 <= o <= 0x30FF)


# CJK 断行禁则（全库唯一来源）：行首禁则（标点不能领行）与行尾禁则（开括号/
# 引号不能收尾）。此前 ghost 与 intelligence 各抄一份逐字相同的字符串，改一处
# 漏一处就会让「预览的断行」与「判断的断行建议」分叉；现在两层都从这里取。
NO_LINE_START_CJK = "，。、；：？！）〉》」』】〕｝·…—～”’"
NO_LINE_END_CJK = "（《「『【〔｛“‘"

# 中西混排间隙：CJK 与拉丁/数字紧贴是中文排版的廉价感来源。在脚本切换处
# 插入 U+2009 THIN SPACE（≈1/5 em），作为渲染层的排版打磨——不改变作者的
# spec 文本（Guard 仍按原文本测行长），只改变最终落到页面上的视觉效果。
HAIR_SPACE = "\u2009"
# 数字与单位之间改用**不断行**空格：U+2009 是合法的断行机会，中文排版里就出现
# 过「…平均配送半径是 186 ｜公里」——数字被留在行尾、单位掉到下一行（既往一次
# 版面观察）。U+00A0 是不允许断行的空格，视觉上仍是同一个间隙。单位词表（UNIT_WORDS）是它的唯一来源。
NO_BREAK_SPACE = "\u00a0"
# 单位词：只用于「不让断行」，不参与任何度量或口径判断。长词在前由匹配器保证。
UNIT_WORDS = (
    "亿美元", "万美元", "亿元", "万元", "万户", "万单", "万人", "万家", "万次",
    "个月", "分钟", "小时", "公里", "千米", "平方米", "平米", "立方米",
    "千瓦时", "千瓦", "公斤", "千克", "毫米", "厘米", "毫升", "美元",
    "吨", "克", "米", "升", "元", "万", "亿", "家", "人", "个", "台", "名",
    "位", "件", "次", "天", "月", "年", "分", "秒", "倍", "万元",
    "%", "％", "pp",
)
_UNIT_HEAD_RE = re.compile("^(?:" + "|".join(
    re.escape(w) for w in sorted(set(UNIT_WORDS), key=len, reverse=True)) + ")")


def unit_head(text: str) -> bool:
    """右侧是否以单位词开头（数字与单位不拆行的判据）。"""
    return bool(text) and bool(_UNIT_HEAD_RE.match(str(text)))


def _is_latin_alnum(ch: str) -> bool:
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ("0" <= ch <= "9")


# 「186 公里」这类作者自己写下的普通空格也是断行机会：数字与单位之间改成
# 不断行空格。只动紧贴数字之后的、且右侧以单位词开头的那一个空格。
_NUMBER_UNIT_SPACE = re.compile(r"(?<=\d) (?=[^\s])")


def bind_number_units(text: str) -> str:
    """数字与单位之间的空格改为不断行空格；其余字符原样保留。"""
    if not text:
        return text

    def _swap(match):
        tail = str(text)[match.end():match.end() + 3]
        return NO_BREAK_SPACE if unit_head(tail) else match.group(0)

    return _NUMBER_UNIT_SPACE.sub(_swap, text)


def insert_script_gaps(text: str) -> str:
    """在 CJK 与拉丁字母/数字的边界插入间隙；空格与标点不触发。

    数字与单位之间用 `NO_BREAK_SPACE`（右侧以单位词开头时），其余边界用
    `HAIR_SPACE`——单位永不被断到下一行，混排间隙照旧。
    """
    if not text or len(text) < 2:
        return bind_number_units(text)
    text = bind_number_units(text)
    out = []
    for i, ch in enumerate(text):
        if i > 0:
            prev = text[i - 1]
            if (_is_latin_alnum(ch) and is_cjk(prev)) or \
                    (_is_latin_alnum(prev) and is_cjk(ch)):
                # 数字 → 单位：不断行（判据在**左侧是数字**、右侧以单位词开头）。
                digit_then_unit = prev.isdigit() and unit_head(text[i:])
                out.append(NO_BREAK_SPACE if digit_then_unit else HAIR_SPACE)
        out.append(ch)
    return "".join(out)


def split_runs(text: str):
    """按 CJK / 拉丁切分，保证中英文混排各自使用正确字体。

    空串返回空列表：此前 `text[0]` 直接抛 IndexError，而它是公开原语，
    调用方（编译器的段落循环）靠 `if not line: continue` 恰好避开——把「没崩」
    建立在调用方的守卫上，等于给下一个调用方埋雷。
    """
    if not text:
        return []
    runs = []
    cur = text[0]
    cur_cjk = is_cjk(cur)
    for ch in text[1:]:
        c = is_cjk(ch)
        if c == cur_cjk:
            cur += ch
        else:
            runs.append((cur, cur_cjk))
            cur, cur_cjk = ch, c
    runs.append((cur, cur_cjk))
    return runs


def text_units(value: str) -> float:
    """文本容量估算：CJK 字符计 1.0（全角方块），拉丁字符计 0.55。
    0.55 取自 Helvetica / Inter 等常见无衬线字体在 14–20px 时
    拉丁字母平均宽度与 CJK 字符宽度的经验比值（0.50–0.58 区间的中位）。
    修正点：原 0.53 在大字号下偏低估，密集正文的容量估算易「乐观」，
    表现为 Guard 通过、渲染溢出。把 0.55 设为默认后，估算与渲染
    可读性复核的对齐误差更小；字段契约见 references/contract.md。
    注意该估算不是 Office 字体的精确度量，终稿仍须人工验收。
    中西混排细空格（HAIR_SPACE）计 0.2，使插入脚本间隙后的估算与渲染一致。"""
    total = 0.0
    for c in value:
        if c == HAIR_SPACE:
            total += 0.2
        elif c == NO_BREAK_SPACE:
            total += 0.55          # 与普通空格同占位，单位不被算成第 N 个汉字
        elif ord(c) > 127:
            total += 1.0
        else:
            total += 0.55
    return total


def text_width(text: str, size: float, spacing: float = 0) -> float:
    """Conservative single-line estimate; not an Office font renderer."""
    units = 0.0
    for c in text:
        units += (0.2 if c == HAIR_SPACE else 0.55 if c == NO_BREAK_SPACE
                  else 1.0 if ord(c) > 127 else
                  0.95 if c in "MW@#%&" else 0.3 if c in "ilI.,:;!'| " else 0.6)
    return units * size + max(0, len(text) - 1) * max(0, spacing) / 0.75


def estimate_lines(text: str, width: float, size: float, wrap: bool = True,
                   spacing: float = 0) -> int:
    """估算段内折行；只在作者显式加字距时多算字形与 tracking 的占位。

    未加字距的路径保持旧判据。字距用同一物理口径：spec/OOXML 是 pt，
    几何是 px，1px=0.75pt。大写宽字母用 text_width 的保守估算，
    不许靠通用拉丁平均 0.55em 让已经加宽的词假装装得下。
    """
    if not text or not wrap:
        return 1
    used = text_units(text) * size
    if spacing > 0:
        used = max(used, text_width(text, size, spacing))
    return max(1, math.ceil(used / max(width, size)))


def set_run_font(run, latin_family, cjk_family, size_pt, color, bold=False,
                 italic=False, spacing=None, alpha=None, uppercase=False):
    """
    spacing: 字距（pt，转换为 1/100 pt）
    alpha  : 文字透明度（用于弱化文字，而非换色）
    """
    text = run.text or ""
    if uppercase:
        text = text.upper()
        run.text = text
    P = _p()
    qn = P["qn"]
    # 一次拿到 rPr。python-pptx 的 font.size / font.color… 每次访问都重新走
    # run→rPr 的 get_or_add 与 ColorFormat 包装；大 deck（每 run 5+ 次父链查找）
    # 实测占编译段 ~1/3，是第一热点。
    rPr = run._r.get_or_add_rPr()
    if len(rPr) == 0:
        # 快路径：全新 rPr（编译器创建的 run 恒为新建）。子元素按 OOXML schema
        # 顺序直组（solidFill → latin，随后共享段补 ea → cs），属性按插入序直写
        # （sz → b → i → spc）——与 XMLchemy get_or_* 在空 rPr 上的追加结果
        # 逐字节相同（A/B SHA 对拍锁定）。会触发 python-pptx 校验的输入
        # （sz 越界 / 非六位 HEX）当场拒绝或回退慢路径，失败语义不变。
        sz = P["Pt"](size_pt).centipoints
        color_hex = str(color) if color is not None else ""
        if 100 <= sz <= 400000 and (color is None or len(color_hex) == 6) \
                and latin_family is not None and cjk_family is not None:
            rPr.set("sz", str(sz))
            rPr.set("b", "1" if bold else "0")
            rPr.set("i", "1" if italic else "0")
            if color is not None:
                sf = rPr.makeelement(qn("a:solidFill"), {})
                sf.append(sf.makeelement(qn("a:srgbClr"), {"val": color_hex}))
                rPr.append(sf)
            latin_el = rPr.makeelement(qn("a:latin"), {})
            latin_el.set("typeface", latin_family)
            rPr.append(latin_el)
        else:
            rPr.sz = P["Pt"](size_pt).centipoints
            rPr.b = bool(bold)
            rPr.i = bool(italic)
            if color is not None:
                rPr.get_or_change_to_solidFill().get_or_change_to_srgbClr().val = str(color)
            rPr.get_or_add_latin().typeface = latin_family
    else:
        rPr.sz = P["Pt"](size_pt).centipoints
        rPr.b = bool(bold)
        rPr.i = bool(italic)
        if color is not None:
            rPr.get_or_change_to_solidFill().get_or_change_to_srgbClr().val = str(color)
        rPr.get_or_add_latin().typeface = latin_family
    if spacing:
        rPr.set("spc", str(int(round(float(spacing) * 100))))
    if alpha is not None and alpha < 1.0:
        sf = rPr.find(qn("a:solidFill"))
        if sf is None:
            sf = rPr.makeelement(qn("a:solidFill"), {})
            rPr.append(sf)
            sf.append(rPr.makeelement(qn("a:srgbClr"), {"val": str(color or fallback_ink())}))
        clr = sf.find(qn("a:srgbClr"))
        if clr is not None:
            _append_alpha(clr, alpha)
    for tag, fam in (("a:ea", cjk_family), ("a:cs", cjk_family)):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", fam)


def set_para_font(p, latin, cn, size_pt, color, bold, spacing=None, alpha=None):
    for run in p.runs:
        set_run_font(run, latin, cn, size_pt, color, bold, False, spacing, alpha, False)
    if not p.runs:
        run = p.add_run()
        run.text = ""
        set_run_font(run, latin, cn, size_pt, color, bold, False, spacing, alpha, False)


# --------------------------------------------------------------------------
# 层间契约
# --------------------------------------------------------------------------
class RenderContext:
    """
    所有绘制层读取主题的**唯一**入口。

    主题（spec.theme）在此归一化，并机械推导出完整色阶；
    elements / charts 只通过 ctx 取色取字。
    因此：换主题只改变 ctx 的内容，不触及任何绘制层实现。
    """

    def __init__(self, theme: dict | None = None, canvas: dict | None = None):
        theme = dict(theme or {})
        canvas = dict(canvas or {})
        self.theme = theme
        base = dict(theme.get("colors") or {})
        # 派生色阶在前，显式声明优先（调用方永远可以覆盖任何派生结果）
        self.colors = {**derive_tokens(base), **base}
        self.fonts = dict(theme.get("fonts") or {})
        self.canvas = {
            "width": float(canvas.get("width", DEFAULT_WIDTH)),
            "height": float(canvas.get("height", DEFAULT_HEIGHT)),
        }
        self.warnings: list[str] = []
        # 与 warnings 等长的元素 id（没有身份的条目为 None）。
        # 两个列表必须同步增长——所以除 warn() 外不要直接 append warnings。

    # -- 颜色 -------------------------------------------------------------
    def paint(self, value):
        """-> (RGBColor | RGB | None, alpha | None)（RGB = pptx 未加载时的等价对象）"""
        token = self.colors.get(value, value)
        return parse_token(token)

    def color(self, value):
        return self.paint(value)[0]

    def text_color(self, value=None):
        c = self.color(value)
        if c is not None:
            return c
        for role in (self.theme.get("text_default"), "ink", "primary"):
            if role:
                c = self.color(role)
                if c is not None:
                    return c
        return fallback_ink()



    def _series_ladder(self, index: int):
        """主题没有派生出色阶时的机械补档（`derive_tokens` 要求纸与主色成对，缺一整体不派生）。

        口径与 `derive_tokens` 的单信号色分支同一条：以本稿信号色为基相，按背景明度
        向反方向逐档拉开，相邻档相对明度差 ≥0.06，灰度打印下仍可辨。
        这是「引擎推导」而不是「兜底告警」——与 negative 色同一条原则。

        为什么必须非 None（实测）：系列色为 None 时编译器把 None 写进
        `series.format.line.color.rgb`，触发 python-pptx 的 RGBColor 断言；
        于是整条序列的线宽、端点标记全都落不下去，交付在 release 档被判
        COMPILE_FAIL——而作者只是少声明了一个主色。颜色是引擎的职责，
        不该把「主题没写」变成「整页图表编译失败」。
        """
        def _hex_of(value):
            raw = self.colors.get(value)
            if isinstance(raw, str) and raw.startswith("#"):
                return raw
            c = self.color(value)
            return _hex(c) if c is not None else None

        base = _hex_of("accent") or _hex_of("primary") or _hex_of("ink")
        if base is None:
            return fallback_ink()
        bg = _hex_of("background")
        ink = _hex_of("ink")
        if bg and luminance(bg) > 0.5:
            target = ink or "#FFFFFF"
        else:
            target = ink or "#000000"
        step = (0.0, 0.18, 0.34, 0.50, 0.66, 0.82)[index % 6]
        color, _alpha = parse_token(base if step == 0.0 else blend(base, target, step))
        return color if color is not None else fallback_ink()

    def series_color(self, index: int):
        """按顺序取系列色（循环使用）；主题未派生色阶时按明度阶梯机械补档。"""
        return self.color(f"series{(index % 6) + 1}") or self._series_ladder(index)

    def series_palette(self, count: int, highlight: int = -1, *, skip_accent: bool = False) -> list:
        """一次算完一组序列色：高亮位用 accent，其余按明度阶梯顺次取。

        accent 同时是「第 1 档系列色」和「高亮色」。高亮存在时若不跳过第 1 档，
        第一个序列会与高亮序列拿到同一个 accent（实测：4 段甜甜圈里 highlight
        默认第 0 段、第 1 段取 series1=accent → 两段同色；「高亮第 2 序列」时
        第 1 序列同样撞色）。accent 的强调语义也一并被稀释。
        非高亮序列从第 2 档起，任何组合下都不与高亮撞色。
        任何一档都保证拿到颜色（见 `_series_ladder`）。

        skip_accent=True：accent 预留给**数据点级**强调（resolve_chart_highlight
        的 point 一侧），序列全体从第 2 档起取色——「强调色只占一个位置」，
        与单序列 data 路径的基础色退位是同一条纪律。
        """
        step = 1 if (highlight >= 0 or skip_accent) else 0
        out = []
        for i in range(max(0, int(count))):
            color = self.color("accent") if i == highlight else self.series_color(i + step)
            out.append(color if color is not None else self.series_color(i + step))
        return out

    # -- 图表角色色（Chart Color Role System）─────────────────────────
    # 图表不写死色值，声明语义角色：primary=主叙事 / secondary=对比 /
    # neutral=语境 / accent=高亮 / negative=风险。角色由 theme.chart_palette
    # 映射到具体色——主题换了，spec 的图表语义不变、色值随主题派生。
    # 解析链：chart_palette[role] → 旧扁平键（chart_primary 等，向后兼容）→
    # colors token。negative 由 derive_tokens 机械派生（不是兜底告警），
    # 作者显式声明 colors.negative / chart_palette.negative 时压过推导。
    _CHART_ROLE_FALLBACK = {
        "primary": ("chart_primary", "primary"),
        "secondary": ("chart_secondary", "secondary"),
        "neutral": ("chart_muted", "secondary"),
        "accent": ("accent",),
        "negative": ("negative",),
    }

    def chart_role(self, role: str):
        """语义角色 → 具体色（RGBColor | None）。角色不认识时返回 None。"""
        role = str(role or "").strip().lower()
        palette = self.theme.get("chart_palette")
        chain = []
        if isinstance(palette, dict) and palette.get(role):
            chain.append(palette[role])
        chain += list(self._CHART_ROLE_FALLBACK.get(role, ()))
        for ref in chain:
            if not ref:
                continue
            c = self.color(ref)
            if c is not None:
                return c
        return None

    def chart_primary_color(self, element: dict | None):
        """图表主叙事默认色：color_role > 逃生口 > 扁平键 > chart_palette.primary > accent。
        单一真源——compiler.chart_colors 与 ghost 预览同读此处，杜绝两条解析链漂移。"""
        el = element or {}
        if el.get("color_role"):
            c = self.chart_role(el["color_role"])
            if c is not None:
                return c
        palette = self.theme.get("chart_palette")
        return self.color(
            el.get("primary_color")
            or self.theme.get("chart_primary")
            or (palette.get("primary") if isinstance(palette, dict) else None)
            or "accent")

    def ramp_color(self, index: int):
        return self.color(f"ramp{max(1, min(5, index + 1))}")

    def auto_text_for(self, fill_ref):
        """
        给定填充色（角色名 / #HEX / RGBColor），从主题池中选对比度最高的文字色。
        这比 on_primary/on_secondary 更稳——后者只对单一角色计算，
        而 chart_secondary 实际可能映射到 accent，深浅与 secondary 相反。
        """
        if fill_ref is None:
            return self.text_color()
        color = fill_ref if color_to_hex(fill_ref) else (self.paint(fill_ref)[0])
        fill_hex = color_to_hex(color)
        if not fill_hex:
            return self.text_color()
        candidates = []
        for role in ("ink", "on_dark", "primary", "background", "surface", "muted", "secondary", "accent"):
            c = self.color(role)
            if c:
                hex_val = color_to_hex(c)
                if hex_val:
                    candidates.append((role, hex_val))
        candidates.append(("white", "FFFFFF"))
        candidates.append(("black", "111111"))
        best_role, best_c = None, 0.0
        for role, hex_val in candidates:
            try:
                k = contrast("#" + hex_val, "#" + fill_hex)
            except Exception:
                continue
            if k > best_c:
                best_c, best_role = k, role
        if best_role in ("white", "black"):
            return _rgb_new(0xFF, 0xFF, 0xFF) if best_role == "white" else _rgb_new(0x11, 0x11, 0x11)
        return self.color(best_role) or self.text_color()

    # -- 字体 -------------------------------------------------------------
    def families(self, element: dict):
        # theme.fonts 的规范键是 cn / latin；display / body 是等价别名（历史写法：
        # 骨架与早期夹具用过它们）。别名必须在这里认——否则写了 display 的 spec
        # 会静默回落 FALLBACK 字体，字体判断在产物里彻底消失且毫无提示。
        cn = self.fonts.get("cn") or self.fonts.get("body") or FALLBACK_CN
        latin = self.fonts.get("latin") or self.fonts.get("display") or FALLBACK_LATIN
        f = element.get("font")
        if isinstance(f, str) and f:
            fam = self.fonts.get(f, f)
            if isinstance(fam, str) and fam:
                latin = fam
        if element.get("family"):
            latin = str(element["family"])
        return cn, latin

    # -- 几何 -------------------------------------------------------------
    def bounds(self, element: dict):
        x = float(element["x"])
        y = float(element["y"])
        w = float(element["width"])
        h = float(element["height"])
        return x, y, w, h

    def warn(self, message: str) -> None:
        """记一条编译期警告（字符串列表；唯一读法是 compile_report["warnings"]）。

        element 身份已经写进消息文本本身；不再收一个没人读的参数（vulture 实测
        该参数从未被实现读取，属于「接口长得像有消费者」的假象）。
        """
        self.warnings.append(message)

# （历史：此块曾住背景层免检阈值 BG_MIN_COVERAGE / BG_MIN_PROTECT_OPACITY，
#   注释声称 guard 经 _cached_gate 读取——该函数不存在，两个常量零消费，已清。）




# ══════════════════ 编译缓存判定（身份/指纹操作；零 pptx 依赖）══════════════════

# 语义投影 + 引擎指纹 + 产物字节戳一致 ⇒ 跳过重复编译。判断"要不要重编"零成本。
CACHE_NAME = "compile_cache.json"
CACHE_VIEW_VERSION = 8
NON_GEOMETRIC_SLIDE_KEYS = (
    "page_intent", "source_zone", "notes", "speaker_notes", "comment",
    "comments", "annotations", "id", "label",
)
NON_GEOMETRIC_THEME_KEYS = (
    "constraints", "notes", "description", "name", "metadata",
    "provenance", "id",
)


def _media_stamp(slide, base_path, spec_path=None, image_bytes=None, digests=None):
    """图片指纹与编译器的相对路径解析同口径；未快照时读一次并把字节交给编译器。"""
    roots = [Path(base_path) if base_path else Path.cwd()]
    if spec_path:
        roots.append(Path(spec_path).parent)
    image_bytes = image_bytes if isinstance(image_bytes, dict) else {}
    digests = digests if isinstance(digests, dict) else {}
    stamps = []
    slide = slide if isinstance(slide, dict) else {}
    elements = slide.get("elements", [])
    if not isinstance(elements, list):
        return stamps
    for element in elements or []:
        if not isinstance(element, dict):
            continue
        src = element.get("src")
        if not src and isinstance(element.get("asset"), dict):
            src = element["asset"].get("src")
        if not src:
            continue
        path = Path(str(src)).expanduser()
        if not path.is_absolute():
            candidates = [(root / path).resolve() for root in roots]
            path = next((c for c in candidates if c.exists()), candidates[0])
        else:
            path = path.resolve()
        key = str(path)
        known = digests.get(key)
        blob = image_bytes.get(key)
        if known is not None:
            size = len(blob) if blob is not None else None
            if size is None:
                try:
                    size = path.stat().st_size
                except OSError:
                    stamps.append([key, "missing"])
                    continue
            stamps.append([key, size, known])
            continue
        if blob is None:
            try:
                blob = path.read_bytes()
            except (OSError, ValueError):
                stamps.append([key, "missing"])
                continue
            image_bytes[key] = blob
        stamp = digest_bytes(blob)
        digests[key] = stamp
        stamps.append([key, len(blob), stamp])
    return stamps


def _projection(obj, drop):
    return {k: v for k, v in (obj if isinstance(obj, dict) else {}).items()
            if k not in drop}


def _load_meta(work):
    try:
        value = json_read_cached(Path(work) / CACHE_NAME)
        return dict(value) if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _patch_meta(work, **fields) -> bool:
    """把字段并进缓存元数据；返回是否真的写下去了。

    写不进缓存（磁盘满 / 目录不可写 / 同名文件占位）不影响本轮产物，但会让每轮都
    **静默重编**——调用方据此出一行诊断，否则「缓存坏了」与「冷启动」长得一模一样。
    """
    try:
        meta = _load_meta(work)
        meta.update(fields)
        json_write(Path(work) / CACHE_NAME, meta, indent=1, trailing_newline=False, fsync=True)
        return True
    except (OSError, TypeError, ValueError):
        return False


def spec_view(spec, base_path=None, spec_path=None, image_bytes=None, digests=None):
    """spec → 确定性编译投影（决定"要不要重编"的唯一身份）。"""
    spec = spec if isinstance(spec, dict) else {}
    raw_canvas = spec.get("canvas")
    canvas = dict(raw_canvas) if isinstance(raw_canvas, dict) else {}
    theme = _projection(spec.get("theme"), NON_GEOMETRIC_THEME_KEYS)
    views = []
    raw_slides = spec.get("slides")
    if not isinstance(raw_slides, list):
        raw_slides = []
    for raw_slide in raw_slides:
        slide = raw_slide if isinstance(raw_slide, dict) else {}
        elements = slide.get("elements") if isinstance(slide.get("elements"), list) else []
        views.append({
            "background": _projection(slide, NON_GEOMETRIC_SLIDE_KEYS).get("background"),
            "elements": elements,
            "id": slide.get("id"),
            "media": _media_stamp(slide, base_path, spec_path, image_bytes, digests),
        })
    return identity({"canvas": canvas, "theme": theme, "slides": views,
                     "engine": engine_fingerprint("compile"), "v": CACHE_VIEW_VERSION},
                    schema="vao-compile-view-v8", short=24)


def compile_reuse(work, pptx, view, *, fast_probe=False, speed=None):
    """语义投影一致 + 产物字节戳一致 ⇒ 复用编译报告；否则 None。

    `speed` 不参与缓存身份：编译器从不按 speed 分支（图片管线两档同口径），
    fast/strict 产物逐字节一致已由 selftest 锁定（含需要 cover 重编码的图）。
    此前按 speed 分区让「strict 终稿后切 fast 迭代」必然整稿重编（实测多付
    一次完整编译），买到的只是把同一个字节再算一遍。`speed` 参数保留只为
    调用兼容与报告口径回填——复用报告的 speed 改写为本轮请求值，缓存里
    记录的编译档仍留在 compile_speed 遥测中可查。
    """
    rec = _load_meta(work).get("compile") or {}
    if not isinstance(rec, dict) or not isinstance(rec.get("report"), dict):
        return None
    if rec.get("semantic_view") != view or not rec.get("report"):
        return None
    output_witness = rec.get("output_witness") or {}
    stored_sha = str(output_witness.get("sha256") or "")
    if len(stored_sha) < 64 or not Path(pptx).exists():
        return None

    def _report(sha):
        report = dict(rec["report"])
        report.update(reused=True, output_sha256=sha)
        if speed is not None:
            perf = dict(report.get("performance") or {})
            perf["speed"] = str(speed)
            report["performance"] = perf
        return report

    if fast_probe:
        if not witness_same(output_witness, witness(pptx)):
            return None
        return _report(stored_sha)
    current_sha = file_digest(pptx)
    if current_sha != stored_sha:
        return None
    return _report(current_sha)


def record_compile(work, pptx, view, report) -> bool:
    """记录本轮编译凭证；返回是否写盘成功（False = 下轮无法复用，调用方应出声）。"""
    output_sha = str((report or {}).get("output_sha256") or "")
    if len(output_sha) != 64:
        output_sha = file_digest(pptx) or ""
    file_witness = witness(pptx)
    recorded = _patch_meta(work, compile={
        "semantic_view": view,
        "compile_speed": str(((report or {}).get("performance") or {}).get("speed") or "strict"),
        "output_witness": {**file_witness, "sha256": output_sha},
        "pptx_name": Path(pptx).name,
        "report": {k: v for k, v in (report or {}).items()
                   if k not in ("guard", "output_sha256")},
    })
    return recorded
