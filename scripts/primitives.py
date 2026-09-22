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


_DIGEST_CACHE: dict[str, tuple[tuple[int, int], str]] = {}
DIGEST_CACHE_MAX = 512


def file_digest(path) -> str | None:
    """全文件字节 SHA-256（全库唯一实现，qa/asset_workflow/compile_cache 共用）。
    缺失/不可读返回 None——证据链把 None 当「文件不存在」处理，不当空串。

    同一进程内同一份字节只算一次（凭证 = size + mtime_ns，与读一次/缓存探测同一套口径）：
    发布证据链要在多处核对同一批产物（预览页、QC 引擎、锁定的产物），它们在一个进程里
    不会变——重算只是把同样的字节再读一遍。字节变了凭证立刻变，重算照旧。
    """
    try:
        target = Path(path).expanduser().resolve()
        stat = target.stat()
    except (OSError, TypeError, ValueError):
        return None
    key = str(target)
    stamp = (stat.st_size, stat.st_mtime_ns)
    hit = _DIGEST_CACHE.get(key)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    try:
        h = hashlib.sha256()
        with target.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        value = h.hexdigest()
    except (OSError, TypeError, ValueError):
        return None
    if len(_DIGEST_CACHE) >= DIGEST_CACHE_MAX:
        _DIGEST_CACHE.clear()
    _DIGEST_CACHE[key] = (stamp, value)
    return value

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
#   3) 「还是那一份」的凭证  stat_witness(path) + witness_matches(a, b, strict=)
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


def stat_witness(path) -> tuple[int | None, int | None]:
    """(size, mtime_ns)——「还是那一份」的快档凭证；读不到返回 (None, None)。"""
    try:
        stat = Path(path).stat()
    except (OSError, TypeError, ValueError):
        return (None, None)
    return (stat.st_size, stat.st_mtime_ns)


def byte_witness(path, *, digest: bool = False) -> dict:
    """规范化字节凭证 {size, mtime_ns, sha256?}：证据 / 缓存记录里只允许这一种写法。"""
    size, mtime_ns = stat_witness(path)
    witness: dict = {"size": size, "mtime_ns": mtime_ns}
    if digest:
        witness["sha256"] = file_digest(path)
    return witness


def witness_matches(a, b, *, strict: bool = False) -> bool:
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
    "compile": ("compiler.py", "primitives.py", "ghost.py"),   # 出 PPTX 的代码
    "preview": ("ghost.py",),                                  # 出预览像素的代码
    "measure": ("asset_prompt.py",),                           # 量像素的代码
}
_ENGINE_CACHE: dict[tuple[str, int | None], str] = {}


def engine_witness(scope: str) -> dict:
    """逐文件凭证：{文件: sha256}——报告里给人看「引擎由哪几份字节构成」。"""
    files = ENGINE_SCOPES.get(scope)
    if files is None:
        raise KeyError(f"未知引擎 scope: {scope}（合法值 {sorted(ENGINE_SCOPES)}）")
    root = Path(__file__).resolve().parent
    return {name: file_digest(root / name) for name in files}


def engine_fingerprint(scope: str, *, short: int | None = None) -> str:
    """引擎指纹（进程内一次）：同一份实现只有一个值。"""
    key = (scope, short)
    hit = _ENGINE_CACHE.get(key)
    if hit is not None:
        return hit
    value = identity(engine_witness(scope), schema=f"vao-engine-{scope}-v1", short=short)
    _ENGINE_CACHE[key] = value
    return value


# ── python-pptx 延迟加载（契约，别改回顶层 import）────────────────────
# 本层被 guard / normalizer / qa 复用，而它们**只处理 spec 数据**：draft 一轮
# 真正的判断成本是 2.8ms，pptx 的 import 却要 152ms（pptx.api → opc → oxml →
# xml.sax → urllib.request）。把整套 Presentation API 拖进「读数据」的路径是
# 架构错误，所以这里只在真的要用 pptx 对象时才解析（`_p()`，进程内缓存一次）。
# 自检 `check_draft_import_contract` 会断言 draft 进程内不得出现 pptx / lxml /
# compiler —— 谁把 `from pptx import ...` 放回本层顶部，立刻失败。
_PPTX: dict | None = None


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
# 图表 kind 的 schema 白名单与 Guard/compiler 共用；Guard 另维护容量上限，
# compiler 维护 native/shape 的实现映射，但未知 kind 不允许各层各自放行。
CHART_KINDS = frozenset({
    "kpi", "executive_kpi", "big_number", "big_number_row",
    "bar", "horizontal_bar", "column", "comparison_bar", "line", "trend",
    "single_trend_line", "area", "donut", "donut_composition", "pie",
    "waterfall", "ranked_bar", "progress_bar", "stacked_bar", "bubble",
    "process_flow", "timeline", "steps", "matrix", "architecture", "sparkline",
})

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


def series_highlight_index(element, names, default: int = -1) -> int:
    """多序列图表的 highlight：整数索引，或写序列名——与 highlight_index 同一语义，
    序列名就是 label 列表，直接复用（写名字被静默忽略的坑只修一次）。"""
    return highlight_index(element, [{"label": n} for n in (names or [])], default)


DEFAULT_WIDTH, DEFAULT_HEIGHT = 1280, 720

# 设计系统基线网格（8 单位）：guard 归一化确认、normalizer 吸附、SKILL.md 契约三方同源
GRID_UNIT = 8

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
    """未声明墨色时的安全值（RGBColor，需要 pptx → 延迟构造）。"""
    return _p()["RGBColor"](0x20, 0x20, 0x20)


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
    """拉丁词的整词匹配（CJK 用子串）。asset_prompt 的术语判定与 route 的 token 判定共用。"""
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


# 辅助文字角色：语义上是注记/来源/轴标签/页面家具（眉标·页码），可读性门槛按「非正文」处理
# （3:1），不参与正文级 4.5:1 判定。**这是唯一真源**：
# 从这里导入（此前两处各写一份，值相同但注释宣称的同源关系并不存在）。
AUX_TEXT_ROLES = frozenset({"source", "method", "metadata", "caption", "legend", "axis",
                            "data_label", "annotation", "page_number", "eyebrow"})


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


def bg_overlay_opacity(element: dict) -> tuple[float | None, str | None]:
    """背景层内容保护层的不透明度 → (opacity, 缺失原因)。

    按 overlay → content_protection.overlay → content_protection.scrim 的顺序取
    第一个可用声明；非空字符串简写视为完全不透明 1.0。
    返回 (None, "missing") 表示未声明；(None, "unparsable") 表示声明了但解析不出
    数值 —— fail-closed：解析不出即视为无保护（guard 与 QA 单一口径，
    旧实现里旁路判定曾按 1.0 放行——已封堵）。
    """
    e = element or {}
    srcs = [e.get("overlay")]
    cp = e.get("content_protection")
    if isinstance(cp, dict):
        srcs.append(cp.get("overlay"))
        srcs.append(cp.get("scrim"))
    for src in srcs:
        if src is None:
            continue
        if isinstance(src, str):
            if src.strip():
                return 1.0, None
            continue
        if isinstance(src, dict):
            try:
                return float(src.get("opacity", 1.0)), None
            except (TypeError, ValueError):
                return None, "unparsable"
    return None, "missing"


def bg_coverage(element: dict, cw: float, ch: float) -> float:
    """元素面积占画布比例（0–1，非法几何按 0）。背景层资格的第一道门：
    覆盖不够的「背景层」只是内容对象，不享受任何豁免。"""
    try:
        area = (float((element or {}).get("width", 0) or 0)
                * float((element or {}).get("height", 0) or 0))
    except (TypeError, ValueError):
        return 0.0
    try:
        denom = float(cw or 0) * float(ch or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, area / denom) if denom > 0 else 0.0



def with_alpha(hex_color: str, alpha: float) -> str:
    """生成 #RRGGBBAA（供色板推导使用）。"""
    a = max(0.0, min(1.0, alpha))
    return f"{_hex(_tuple(hex_color))}{format(int(round(a * 255)), '02X')}"


def parse_token(value):
    """-> (RGBColor | None, alpha | None)；支持 #RGB / #RRGGBB / #RRGGBBAA / none。"""
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
    if len(h) == 8:
        try:
            return _p()["RGBColor"].from_string(h[0:6].upper()), int(h[6:8], 16) / 255.0
        except Exception:
            return None, None
    if len(h) == 6:
        try:
            return _p()["RGBColor"].from_string(h.upper()), None
        except Exception:
            return None, None
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




# --------------------------------------------------------------------------
# 读一次（单进程内的读缓存）
# --------------------------------------------------------------------------
# 一轮 check 里同一份 JSON 会被多个层读（绑定、核验、缓存投影各一次）：plan.json
# 50KB 读三遍、manifest 读三遍。文件不大，但这种「同一份事实读三遍」正是运行时
# 重复劳动的来源，而且三处各解析一次 JSON 迟早会有一处读到半写入的状态。
# 判据是身份而不是时间：size + mtime_ns 变了就失效（写入方全是原子写 + fsync）。
# 进程级、上限 64 条：只服务一轮执行，不跨运行做新鲜度假设。
_READ_CACHE: dict[str, tuple[tuple[int, int], object]] = {}
READ_CACHE_MAX = 64


def json_read_cached(path) -> dict:
    """读 JSON 一次，随后复用（size+mtime_ns 守卫）。失败一律重读，不吞异常。"""
    import json
    # 键必须归一化：同一个文件被不同层用相对/绝对路径指向时，缓存要认出它们是同一份，
    # 否则「读一次」退化成一个调用点一份缓存（实测就是这样，manifest 被读了两遍）。
    try:
        target = Path(path).expanduser().resolve()
    except OSError:
        target = Path(path)
    key = str(target)
    try:
        stat = target.stat()
        stamp = (stat.st_size, stat.st_mtime_ns)
    except OSError:
        _READ_CACHE.pop(key, None)
        raise
    hit = _READ_CACHE.get(key)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须为对象: {path}")
    if len(_READ_CACHE) >= READ_CACHE_MAX:
        _READ_CACHE.clear()
    _READ_CACHE[key] = (stamp, value)
    return value


# --------------------------------------------------------------------------
# 文本
# --------------------------------------------------------------------------
def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x3000 <= o <= 0x9FFF) or (0xFF00 <= o <= 0xFFEF) or (0x3040 <= o <= 0x30FF)


# 中西混排间隙：CJK 与拉丁/数字紧贴是中文排版的廉价感来源。在脚本切换处
# 插入 U+2009 THIN SPACE（≈1/5 em），作为渲染层的排版打磨——不改变作者的
# spec 文本（Guard 仍按原文本测行长），只改变最终落到页面上的视觉效果。
HAIR_SPACE = "\u2009"


def _is_latin_alnum(ch: str) -> bool:
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ("0" <= ch <= "9")


def insert_script_gaps(text: str) -> str:
    """在 CJK 与拉丁字母/数字的边界插入细空格；空格与标点不触发。"""
    if not text or len(text) < 2:
        return text
    out = []
    for i, ch in enumerate(text):
        if i > 0:
            prev = text[i - 1]
            if (_is_latin_alnum(ch) and is_cjk(prev)) or \
                    (_is_latin_alnum(prev) and is_cjk(ch)):
                out.append(HAIR_SPACE)
        out.append(ch)
    return "".join(out)


def split_runs(text: str):
    """按 CJK / 拉丁切分，保证中英文混排各自使用正确字体。"""
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
    可读性复核的对齐误差更小（字号阶梯与回退顺序参见 design-system.md
    §字号阶梯、design-craft.md §五）。
    中西混排细空格（HAIR_SPACE）计 0.2，使插入脚本间隙后的估算与渲染一致。"""
    total = 0.0
    for c in value:
        if c == HAIR_SPACE:
            total += 0.2
        elif ord(c) > 127:
            total += 1.0
        else:
            total += 0.55
    return total


def text_width(text: str, size: float, spacing: float = 0) -> float:
    """Conservative single-line estimate; not an Office font renderer."""
    units = 0.0
    for c in text:
        units += (0.2 if c == HAIR_SPACE else 1.0 if ord(c) > 127 else
                  0.95 if c in "MW@#%&" else 0.3 if c in "ilI.,:;!'| " else 0.6)
    return units * size + max(0, len(text) - 1) * max(0, spacing) / 0.75


def estimate_lines(text: str, width: float, size: float, wrap: bool = True) -> int:
    if not text or not wrap:
        return 1
    usable = max(width / max(size, 0.01), 1)
    return max(1, math.ceil(text_units(text) / usable))


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
    # python-pptx 的 run.font 是描述符；同一 run 重复取它会反复走 XML
    # 父链查找。缓存一次对象，属性写入语义不变但可明显降低大 deck 编译成本。
    font = run.font
    font.size = P["Pt"](size_pt)
    font.bold = bool(bold)
    font.italic = bool(italic)
    if color is not None:
        font.color.rgb = color
    font.name = latin_family
    rPr = run._r.get_or_add_rPr()
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
        self.warning_ids: list[str | None] = []

    # -- 颜色 -------------------------------------------------------------
    def paint(self, value):
        """-> (RGBColor | None, alpha | None)"""
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



    def series_color(self, index: int):
        """按顺序取系列色（循环使用）。"""
        return self.color(f"series{(index % 6) + 1}")

    def series_palette(self, count: int, highlight: int = -1) -> list:
        """一次算完一组序列色：高亮位用 accent，其余按明度阶梯顺次取。

        accent 同时是「第 1 档系列色」和「高亮色」。高亮存在时若不跳过第 1 档，
        第一个序列会与高亮序列拿到同一个 accent（实测：4 段甜甜圈里 highlight
        默认第 0 段、第 1 段取 series1=accent → 两段同色；「高亮第 2 序列」时
        第 1 序列同样撞色）。accent 的强调语义也一并被稀释。
        非高亮序列从第 2 档起，任何组合下都不与高亮撞色。
        """
        step = 1 if highlight >= 0 else 0
        return [self.color("accent") if i == highlight else self.series_color(i + step)
                for i in range(max(0, int(count)))]

    # -- 图表角色色（Chart Color Role System）─────────────────────────
    # 图表不写死色值，声明语义角色：primary=主叙事 / secondary=对比 /
    # neutral=语境 / accent=高亮 / negative=风险。角色由 theme.chart_palette
    # 映射到具体色——主题换了，spec 的图表语义不变、色值随主题派生。
    # 解析链：chart_palette[role] → 旧扁平键（chart_primary 等，向后兼容）→
    # colors token。negative 未声明时用通用风险红兜底并告警（最后手段，
    # 不是设计建议——主题作者应显式派生风险色）。
    _CHART_ROLE_FALLBACK = {
        "primary": ("chart_primary", "primary"),
        "secondary": ("chart_secondary", "secondary"),
        "neutral": ("chart_muted", "secondary"),
        "accent": ("accent",),
        "negative": ("negative",),
    }
    _NEGATIVE_FALLBACK = "#B3261E"   # 通用风险红：仅主题未声明 negative 时兜底

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
        if role == "negative":
            msg = ("theme 未声明 negative 角色（chart_palette.negative 或 colors.negative），"
                   "负值用通用风险红兜底——请为主题显式派生一个风险色")
            if msg not in self.warnings:
                self.warn(msg)        # 走 warn()，保持 warnings / warning_ids 等长
            return self.color(self._NEGATIVE_FALLBACK)
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
            rgb = _p()["RGBColor"]
            return rgb(0xFF, 0xFF, 0xFF) if best_role == "white" else rgb(0x11, 0x11, 0x11)
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

    def warn(self, message: str, element_id=None) -> None:
        """记一条编译期警告。element_id 可选，但**给了就能进 fix_plan 分组**。

        修的是现有链路，不是新建一套：warnings 仍是字符串列表（compile_report
        与所有下游读法不变），只是额外把元素 id 记进 warning_ids，
        让 qa 能把「哪一个元素」填进修复包，而不是让 id 埋在文案里被正则猜。
        """
        self.warnings.append(message)
        self.warning_ids.append(str(element_id) if element_id else None)

# ── 物理底线阈值（guard 经 _cached_gate 直连读取，单一口径住这里）────────────
# （历史：此块曾住 art_critic 下沉的整套「设计判断基元」——焦点领先/记忆锚点/
#   卡片墙/节奏墨差等常量与几何函数。spec 级二审层删除后全部零消费，已清。）
BG_MIN_COVERAGE = 0.60           # 背景层免检：至少覆盖 60% 画布面积
BG_MIN_PROTECT_OPACITY = 0.20    # 内容保护层最低不透明度


