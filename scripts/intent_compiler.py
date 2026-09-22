#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""需求加载器：yml / json / 定义 BRIEF|NEED 的 Python 模块。

（v7.2.0 审计：本层曾有 `compile_brief`——把 need+plan 重新标签成
design_intent/strategy_seed/direction_seed/slides_seed/unresolved/route 的
「Design Brief 结构」。全库零消费者：need 与 plan 本来就在 bundle 里，
嵌套输出只是一个没人读的镜像；source_hash 是 need 的第三种摘要，链绑定
实际用的是 brief_sha256=digest(need) + plan["need"] 快照。已整体删除，
同输入同 plan 的行为不变。）
"""
from __future__ import annotations

import json


def _load_need(path: str) -> dict:
    """读需求：yml / json / 定义 BRIEF|NEED 的 Python 模块。"""
    from pathlib import Path
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"需求文件不存在或不是文件: {p}"
                         "（brief 需为 .yml/.yaml/.json 或定义 BRIEF/NEED 的 .py）")
    if p.suffix in (".yml", ".yaml"):
        import yaml
        try:
            value = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            # 带上文件与行列：brief 是人手写的文件，解析错误必须能直接定位。
            mark = getattr(exc, "problem_mark", None)
            where = f":{mark.line + 1}:{mark.column + 1}" if mark else ""
            problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
            raise ValueError(f"brief YAML 解析失败：{p}{where} — {problem}") from None
        if not isinstance(value, dict):
            raise ValueError(f"brief 顶层必须是对象/dict，实际是 {type(value).__name__}：{p}")
        return value
    if p.suffix == ".json":
        try:
            value = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"brief JSON 解析失败：{p}:{exc.lineno}:{exc.colno}"
                             f" — {exc.msg}") from None
        if not isinstance(value, dict):
            raise ValueError(f"brief 顶层必须是对象/dict，实际是 {type(value).__name__}：{p}")
        return value
    if p.suffix.lower() != ".py":
        raise ValueError("brief 只接受 JSON/YAML，或作者明确指定的可信 .py 文件")
    # 与 vao._load_module 同法：读→compile→exec，不写 __pycache__、不复用旧
    # 字节码——需求文件是人会反复编辑的文件，陈旧代价不该由交付链承担。
    import types
    mod = types.ModuleType("need_mod")
    mod.__file__ = str(p)
    exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), mod.__dict__)
    if hasattr(mod, "BRIEF"):
        return dict(mod.BRIEF)
    if hasattr(mod, "NEED"):
        return dict(mod.NEED)
    raise ValueError("需求需为 yml / json 或定义 BRIEF / NEED 的模块")
