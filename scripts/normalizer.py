# -*- coding: utf-8 -*-
"""
Layer 0.5 · Normalizer（机械归一化层 · 生产链第 0 级）

职责：在 Guard 之前，把 spec 里**机器可以无判断吸附**的机械偏差对齐到设计系统——
    ① 网格吸附（8 单位基线：x/y 就近取整，w/h 向上取整防溢出）
    ② 色彩 token 归一（别名/十六进制大小写 → 主题 token 规范形）
    ③ 字体 token 归一（大小写/空白 → 主题声明族名的规范拼写）
    ④ 间距归一（padding 等微间距吸附到 4 的倍数）

它**只做确定性的机械对齐**，不做任何设计判断：
    - 不补数据、不改文字、不动语义字段（insight/density/focus 原样保留）；
    - 每一处修改都写进 normalization 报告（slide/id/field/from/to/rule），没有静默修改；
    - 幂等：normalize(normalize(spec)) == normalize(spec)，报告内置二次校验；
    - 可退出：元素级 `grid_exempt: true`，或 spec 级 `normalization: {"grid": false}`。

为什么需要它：Guard 是「确认器」而不是「纠错器」——8px 网格、token 拼写这类
设计系统约束应该在进入检查之前就被对齐（否则 226 处坐标偏离 = 226 条警告，
每一条都要人/AI 手工修一轮）。归一化后，Guard 看到的就是设计系统的规范形，
它只负责确认「没有归一化解决不了的问题」（数据合同、遮挡、可读性语义）。

用法（CLI）：
    python3 scripts/normalizer.py build_mydeck.py            # 打印归一化报告
    python3 scripts/normalizer.py build_mydeck.py --write normalized.json
或作为库：
    from normalizer import normalize_spec
    spec, report = normalize_spec(spec)
"""
from __future__ import annotations

import copy
import math
import re
from pathlib import Path
from typing import Any

from primitives import GRID_UNIT, spec_fingerprint

# 微间距吸附步长（padding 这类字内呼吸不适合 8 的粗步长，用半步）
SPACING_STEP = 4

# 元素上参与色彩归一的字段名（含 fill 子对象内的 color）
_COLOR_FIELDS = ("color", "background", "border_color", "stroke", "accent",
                 "fill_color", "track_color", "label_color")
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

_REPORT_ITEM_CAP = 200   # 报告逐条明细上限（统计仍完整，防止巨型 spec 刷屏）


def _snap_pos(value: float, grid: int) -> int:
    """位置就近吸附（round-half-up，与版心设计的取整方向一致）。"""
    return int(math.floor(float(value) / grid + 0.5)) * grid


def _snap_size(value: float, grid: int) -> int:
    """尺寸向上吸附：只增不减，防止吸附后文字/图表溢出容器。"""
    v = float(value)
    n = math.ceil(v / grid) * grid
    return int(n) if n >= v else int(n) + grid  # 浮点边界：ceil(64.0/8)*8==64 直接命中


def _canonical_color(value: Any, tokens: dict[str, str]) -> tuple[Any, str | None]:
    """色彩值 → (规范值, 规则名)。tokens: {token名: 规范hex}。
    规则：token 别名（大小写/空白）→ 规范 token 名；hex → 大写规范形；
    与主题色完全同值的 hex → token 名（让「同一颜色」在 spec 里只有一个名字）。"""
    if not isinstance(value, str):
        return value, None
    raw = value.strip()
    if not raw:
        return value, None
    # ① token 别名 → 规范 token 名
    for name in tokens:
        if raw.lower() == name.strip().lower():
            return (name, "color_token_alias") if raw != name else (value, None)
    # ② hex → 规范大写形
    if _HEX_RE.match(raw):
        upper = raw.upper()
        # ③ 与主题色同值的 hex → token 名（单一事实来源）
        for name, hexv in tokens.items():
            if isinstance(hexv, str) and _HEX_RE.match(hexv.strip()) \
                    and hexv.strip().upper() == upper:
                return name, "color_hex_to_token"
        return (upper, "color_hex_case") if upper != raw else (value, None)
    return value, None


def _canonical_font(value: Any, families: list[str]) -> tuple[Any, str | None]:
    """字体声明 → 主题声明族名的规范拼写（大小写/空白差异归一）。"""
    if not isinstance(value, str) or not families:
        return value, None
    raw = value.strip()
    for fam in families:
        if raw.lower() == str(fam).strip().lower():
            return (fam, "font_token_alias") if raw != fam else (value, None)
    return value, None


def _normalize_once(spec: dict, *, grid: bool, colors: bool, fonts: bool,
                    spacing: bool) -> tuple[dict, dict[str, int], list[dict], list[dict]]:
    """单趟归一化（纯函数）：返回 (新 spec, 分规则计数, 逐条明细, 未解析项)。"""
    src = copy.deepcopy(spec)
    items: list[dict] = []
    by_rule: dict[str, int] = {}
    unresolved: list[dict] = []

    canvas = (src.get("canvas") or {})
    grid_unit = int(canvas.get("grid_unit") or GRID_UNIT)
    if grid_unit <= 0:
        grid_unit = GRID_UNIT
    # spec 级开关：normalization: {"grid": false} 整体关闭网格吸附
    spec_opt = (src.get("normalization") or {})
    do_grid = grid and spec_opt.get("grid", True) is not False

    theme = (src.get("theme") or {})
    color_tokens: dict[str, str] = {}
    if colors:
        for k, v in (theme.get("colors") or {}).items():
            if isinstance(k, str) and isinstance(v, str):
                color_tokens[k.strip()] = v.strip()
    font_families: list[str] = []
    if fonts:
        seen: set[str] = set()
        for v in (theme.get("fonts") or {}).values():
            if isinstance(v, str) and v.strip():
                key = v.strip().lower()
                if key not in seen:
                    seen.add(key)
                    font_families.append(v.strip())

    def _record(slide_id: str, el_id: str | None, field: str,
                old: Any, new: Any, rule: str) -> None:
        by_rule[rule] = by_rule.get(rule, 0) + 1
        if len(items) < _REPORT_ITEM_CAP:
            items.append({"slide": slide_id, "id": el_id, "field": field,
                          "from": old, "to": new, "rule": rule})

    def _normalize_element(slide_id: str, el: dict) -> None:
        el_id = el.get("id")
        # ① 网格吸附：只碰几何四元组，绝不碰语义
        if do_grid and not el.get("grid_exempt"):
            for f in ("x", "y"):
                v = el.get(f)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    snapped = _snap_pos(v, grid_unit)
                    if snapped != v:
                        _record(slide_id, el_id, f, v, snapped, "grid_snap")
                        el[f] = snapped
            for f in ("width", "height"):
                v = el.get(f)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    snapped = _snap_size(v, grid_unit)
                    if snapped != v:
                        _record(slide_id, el_id, f, v, snapped, "grid_snap_size")
                        el[f] = snapped
        # ② 色彩 token 归一
        if colors and color_tokens:
            for f in _COLOR_FIELDS:
                if f not in el:
                    continue
                new, rule = _canonical_color(el.get(f), color_tokens)
                if rule:
                    _record(slide_id, el_id, f, el.get(f), new, rule)
                    el[f] = new
            fill = el.get("fill")
            if isinstance(fill, dict) and "color" in fill:
                new, rule = _canonical_color(fill.get("color"), color_tokens)
                if rule:
                    _record(slide_id, el_id, "fill.color", fill.get("color"), new, rule)
                    fill["color"] = new
        # ③ 字体 token 归一
        if fonts and font_families:
            for f in ("font", "font_family"):
                if f not in el:
                    continue
                new, rule = _canonical_font(el.get(f), font_families)
                if rule:
                    _record(slide_id, el_id, f, el.get(f), new, rule)
                    el[f] = new
                elif isinstance(new, str) and new.strip() and rule is None \
                        and new.strip().lower() not in {x.lower() for x in font_families}:
                    unresolved.append({"slide": slide_id, "id": el_id, "field": f,
                                       "value": new, "kind": "font_not_in_theme"})
        # ④ 微间距吸附（padding → 4 的倍数）
        if spacing:
            v = el.get("padding")
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                snapped = int(math.ceil(float(v) / SPACING_STEP)) * SPACING_STEP
                if snapped != v:
                    _record(slide_id, el_id, "padding", v, snapped, "spacing_snap")
                    el["padding"] = snapped

    for slide in (src.get("slides") or []):
        if not isinstance(slide, dict):
            continue
        slide_id = slide.get("id")
        for el in (slide.get("elements") or []):
            if isinstance(el, dict):
                _normalize_element(str(slide_id), el)
    return src, by_rule, items, unresolved


def normalize_spec(spec: dict, *, grid: bool = True, colors: bool = True,
                   fonts: bool = True, spacing: bool = True) -> tuple[dict, dict]:
    """spec → (归一化 spec, 归一化报告)。纯函数：不改入参，返回深拷贝。

    报告结构：
        applied          是否发生了修改
        hash_before/after 归一化前后指纹（发布链自证用）
        changed / by_rule 修改总数与分规则计数
        items            逐条明细（slide/id/field/from/to/rule，封顶 200 条）
        idempotent       内置二次归一化校验（必须为 True）
        unresolved       无法归一但值得注意的项（如未在主题声明的字体），只记录不改
    """
    src, by_rule, items, unresolved = _normalize_once(
        spec, grid=grid, colors=colors, fonts=fonts, spacing=spacing)
    # 幂等校验：对结果再归一化一次，必须零修改（保证缓存键与发布链稳定）。
    # 第二趟不再递归自检（_normalize_once 是单趟），只比对计数。
    _, by_rule_2, _, _ = _normalize_once(
        src, grid=grid, colors=colors, fonts=fonts, spacing=spacing)
    changed = sum(by_rule.values())
    report = {
        "applied": changed > 0,
        "hash_before": spec_fingerprint(spec),
        "hash_after": spec_fingerprint(src),
        "changed": changed,
        "by_rule": by_rule,
        "items": items,
        "idempotent": sum(by_rule_2.values()) == 0,
        "unresolved": unresolved[:_REPORT_ITEM_CAP],
    }
    return src, report


def geometry_only_hash(spec: dict) -> str:
    """像素相关投影的指纹：剥掉「只影响声明/评分、不影响像素」的字段后取指纹。

    用途：Critic 稳定性判定（连续两次 clean 且几何未变才值得跑 Critic）与
    语义变更分类。与 render_check 的页级缓存键同向：这些字段变了，页级缓存
    本来也不会失效——在这里显式说出来，避免「改了一句 insight 也重渲染」。
    """
    PIXEL_NEUTRAL_PAGE_FIELDS = (
        "insight", "narrative_role", "reading_order", "energy", "density",
        "empty_space_role", "page_family", "rhythm_stage", "continuity_token",
    )
    proj = copy.deepcopy(spec)
    for slide in (proj.get("slides") or []):
        if not isinstance(slide, dict):
            continue
        slide.pop("notes", None)
        slide.pop("source_note", None)
        pi = slide.get("page_intent")
        if isinstance(pi, dict):
            for f in PIXEL_NEUTRAL_PAGE_FIELDS:
                pi.pop(f, None)
    return spec_fingerprint(proj)


# --------------------------------------------------------------------------
# 可选 CLI： python normalizer.py <build_module.py> [--json] [--write out.json]
#                                    [--grid-off] [--colors-off] ...
# --------------------------------------------------------------------------
def main(argv):
    import importlib.util
    import json
    if len(argv) < 2:
        print("usage: python normalizer.py <build_module.py> [--json] "
              "[--write normalized.json] [--grid-off] [--colors-off] "
              "[--fonts-off] [--spacing-off]")
        return 1
    mod_path = Path(argv[1])
    spec_mod = importlib.util.spec_from_file_location("buildmod", str(mod_path))
    mod = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(mod)
    spec = mod.build_spec() if hasattr(mod, "build_spec") else getattr(mod, "SPEC", None)
    if spec is None:
        print("build module must define build_spec() or SPEC")
        return 1
    new, report = normalize_spec(spec,
                                 grid="--grid-off" not in argv,
                                 colors="--colors-off" not in argv,
                                 fonts="--fonts-off" not in argv,
                                 spacing="--spacing-off" not in argv)
    if "--write" in argv:
        i = argv.index("--write")
        out = Path(argv[i + 1]) if i + 1 < len(argv) else Path("normalized_spec.json")
        out.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"written: {out}")
    if "--json" in argv:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        rules = "、".join(f"{k}×{v}" for k, v in sorted(report["by_rule"].items()))
        print(f"normalizer: {report['changed']} 处机械偏差已吸附"
              + (f"（{rules}）" if rules else "")
              + (" · 幂等校验通过" if report["idempotent"] else " · 幂等校验失败！"))
        for it in report["items"][:20]:
            print(f"  {str(it['slide']):>5} {str(it['id']):<18} "
                  f"{it['field']:<12} {it['from']} → {it['to']}  [{it['rule']}]")
        if report["changed"] > len(report["items"][:20]):
            print(f"  … 其余 {report['changed'] - 20} 处见 --json")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
