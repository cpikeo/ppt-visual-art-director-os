# -*- coding: utf-8 -*-
"""schema.py · 数据契约校验器（零依赖的 JSON Schema 子集）

为什么自己写而不是引 jsonschema：技能包的红线是「spec 档不引入渲染/重量级依赖，
`pip install -r requirements.txt` 后即可用」。一个纯校验器 ~200 行，换来一条硬纪律：

**契约文件里出现本模块不认识的校验关键字，直接报错**（不静默忽略）。
静默忽略是契约最坏的失败模式——schema 里写了 `"minItems": 3` 却没人执行，
作者会以为自己被保护着。这里宁可拒绝加载，也不假装校验过。

支持的子集（足够表达 plan 契约；语义与 JSON Schema 2020-12 一致）：

    type · properties · required · additionalProperties(bool|schema) ·
    items · minItems · maxItems · enum · const · minLength · maxLength ·
    pattern · minimum · maximum · anyOf · oneOf · allOf · not · $ref · $defs

标注关键字（不执行、不报错）：$schema · $id · title · description ·
examples · default · deprecated · x-*（以 x- 开头的自定义注记）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ANNOTATIONS = {"$schema", "$id", "title", "description", "examples", "default",
               "deprecated", "$comment"}
SUPPORTED = {"type", "properties", "required", "additionalProperties", "items",
             "minItems", "maxItems", "enum", "const", "minLength", "maxLength",
             "pattern", "minimum", "maximum", "anyOf", "oneOf", "allOf", "not",
             "$ref", "$defs"}
_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


class SchemaError(ValueError):
    """契约文件本身不合法（不是数据不合法）。"""


# ─────────────────────────────────────────────────────────────────────
# 契约文件自检：不认识的关键字 = 不会被执行的承诺
# ─────────────────────────────────────────────────────────────────────
def audit_schema(node, path="$") -> list[str]:
    """返回契约里「不被本校验器执行」的关键字位置（空列表才允许使用）。"""
    problems: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            where = f"{path}.{key}"
            if key.startswith("x-") or key in ANNOTATIONS or key in SUPPORTED:
                pass
            else:
                problems.append(f"{where}: 未支持的校验关键字 {key!r}")
            if key in ("properties", "$defs") and isinstance(value, dict):
                for name, sub in value.items():
                    problems.extend(audit_schema(sub, f"{where}.{name}"))
            elif key in ("items", "additionalProperties", "not") and isinstance(value, dict):
                problems.extend(audit_schema(value, where))
            elif key in ("anyOf", "oneOf", "allOf") and isinstance(value, list):
                for index, sub in enumerate(value):
                    problems.extend(audit_schema(sub, f"{where}[{index}]"))
        if "type" in node:
            type_value = node["type"]
            names = type_value if isinstance(type_value, list) else [type_value]
            for name in names:
                if name not in _TYPES:
                    problems.append(f"{path}.type: 未知类型 {name!r}")
    return problems


def load(path) -> dict:
    """读取并自检契约文件；有问题即 SchemaError（不进入校验阶段）。"""
    p = Path(path).expanduser()
    if not p.is_file():
        raise SchemaError(f"契约文件不存在：{p}")
    try:
        schema = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"契约 JSON 解析失败：{p}:{exc.lineno}:{exc.colno} — {exc.msg}") from None
    problems = audit_schema(schema)
    if problems:
        raise SchemaError(f"契约 {p.name} 含不被执行的校验关键字：" + "；".join(problems[:6]))
    return schema


# ─────────────────────────────────────────────────────────────────────
# 校验
# ─────────────────────────────────────────────────────────────────────
def _resolve(ref: str, root: dict):
    if not ref.startswith("#/"):
        raise SchemaError(f"只支持文档内 $ref（#/…），实际 {ref!r}")
    node = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise SchemaError(f"$ref 指向不存在的定义：{ref}")
        node = node[part]
    return node


def _type_of(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (list, tuple)):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _type_ok(value, wanted: str) -> bool:
    actual = _type_of(value)
    if wanted == "number":
        return actual in ("number", "integer")
    return actual == wanted


def validate(value, schema: dict, *, root: dict | None = None, path: str = "$") -> list[str]:
    """返回**全部**违约项（不早退：一次报完，作者一轮改完）。"""
    root = root if root is not None else schema
    errors: list[str] = []

    if "$ref" in schema:
        return validate(value, _resolve(schema["$ref"], root), root=root, path=path)

    if "type" in schema:
        wanted = schema["type"]
        names = wanted if isinstance(wanted, list) else [wanted]
        if not any(_type_ok(value, name) for name in names):
            errors.append(f"{path}: 期望 {'/'.join(names)}，实际 {_type_of(value)}")
            return errors                     # 类型错了，后面的判据没有意义

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: 必须等于 {schema['const']!r}，实际 {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        shown = "、".join(map(str, schema["enum"][:8])) + ("…" if len(schema["enum"]) > 8 else "")
        errors.append(f"{path}: 合法值 {shown}，实际 {value!r}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: 长度需 ≥ {schema['minLength']}，实际 {len(value)}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: 长度需 ≤ {schema['maxLength']}，实际 {len(value)}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: 不匹配 {schema['pattern']}，实际 {value!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: 需 ≥ {schema['minimum']}，实际 {value}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: 需 ≤ {schema['maximum']}，实际 {value}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: 至少 {schema['minItems']} 项，实际 {len(value)}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: 至多 {schema['maxItems']} 项，实际 {len(value)}")
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(validate(item, schema["items"], root=root,
                                       path=f"{path}[{index}]"))

    if isinstance(value, dict):
        props = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in value:
                errors.append(f"{path}: 缺少必需字段 {key!r}")
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in props:
                errors.extend(validate(item, props[key], root=root, path=f"{path}.{key}"))
            elif extra is False:
                errors.append(f"{path}: 未知字段 {key!r}（拼错的字段名不会被下游消费）")
            elif isinstance(extra, dict):
                errors.extend(validate(item, extra, root=root, path=f"{path}.{key}"))

    if "allOf" in schema:
        for index, sub in enumerate(schema["allOf"]):
            errors.extend(validate(value, sub, root=root, path=path))
    if "anyOf" in schema:
        if not any(not validate(value, sub, root=root, path=path) for sub in schema["anyOf"]):
            errors.append(f"{path}: 不满足 anyOf 任一分支持有结构")
    if "oneOf" in schema:
        hits = sum(1 for sub in schema["oneOf"]
                   if not validate(value, sub, root=root, path=path))
        if hits != 1:
            errors.append(f"{path}: 需要恰好命中 oneOf 的 1 个分支，实际 {hits} 个")
    if "not" in schema and not validate(value, schema["not"], root=root, path=path):
        errors.append(f"{path}: 命中被禁止的结构（not）")
    return errors


def validate_file(path, schema_path) -> list[str]:
    """校验磁盘上的 JSON 文件；读不到文件也算违约（不静默通过）。"""
    target = Path(path).expanduser()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"{target}: 文件不存在"]
    except json.JSONDecodeError as exc:
        return [f"{target}:{exc.lineno}:{exc.colno}: JSON 解析失败 — {exc.msg}"]
    return validate(value, load(schema_path))

# ─────────────────────────────────────────────────────────────────────
# 契约漂移：产出物里有、契约里没声明的字段
# ─────────────────────────────────────────────────────────────────────
def _branch_properties(schema: dict, root: dict, into: dict) -> None:
    """把 anyOf/oneOf/allOf 各分支声明的属性并起来（键只要被**任一**分支声明就算声明）。"""
    if "$ref" in schema:
        _branch_properties(_resolve(schema["$ref"], root), root, into)
        return
    into.update(schema.get("properties") or {})
    for key in ("anyOf", "oneOf", "allOf"):
        for sub in schema.get(key) or []:
            _branch_properties(sub, root, into)


def _is_closed(schema: dict, root: dict) -> bool:
    """这条分支是否自称封闭（`additionalProperties: false`，可经 $ref / allOf 传递）。"""
    if "$ref" in schema:
        return _is_closed(_resolve(schema["$ref"], root), root)
    if schema.get("additionalProperties") is False:
        return True
    return any(_is_closed(sub, root) for sub in schema.get("allOf") or [])


def contract_gaps(value, schema: dict, *, root: dict | None = None,
                  path: str = "$", strict: bool = False) -> list[str]:
    """产出物里**契约没声明**的字段（契约漂移的最小探测器）。

    为什么需要它：`additionalProperties: false` 的对象收到未声明键时，`validate()`
    已经会报「未知字段」；但**新字段出现在这里之前**通常没人会想到去更新契约——
    本轮之前就发生过一次（`mixed_metrics` 加入 understanding 后瘦身投影被 anyOf
    判成「形状不对」，是 CI 才发现的）。这个函数把顺序倒过来：拿真实产出物去问
    契约「你都声明了吗」，缺口直接列出路径。

    `strict=False` 只查**自称封闭**（`additionalProperties: false`）的对象——
    那里出现未声明键就是真矛盾；`strict=True` 连开放对象也查（用于评审新契约）。
    """
    root = root if root is not None else schema
    gaps: list[str] = []
    if "$ref" in schema:
        return contract_gaps(value, _resolve(schema["$ref"], root), root=root,
                             path=path, strict=strict)
    branches = schema.get("anyOf") or schema.get("oneOf") or schema.get("allOf")
    if branches:
        merged: dict = {}
        _branch_properties(schema, root, merged)
        # 关键一步：并集之后按**封闭**处理。值命中的是某一条分支，而每条分支都自称
        # 封闭——不在并集里的键就是所有分支都不认识的键（契约漂移）。
        closed = any(_is_closed(sub, root) for sub in branches)
        schema = {k: v for k, v in schema.items()
                  if k not in ("anyOf", "oneOf", "allOf")}
        schema["properties"] = merged
        if closed:
            schema["additionalProperties"] = False
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            where = f"{path}.{key}"
            if key in props:
                gaps.extend(contract_gaps(item, props[key], root=root, path=where,
                                          strict=strict))
            elif extra is False:
                gaps.append(f"{where}: 契约未声明（该对象声明为封闭）")
            elif isinstance(extra, dict):
                gaps.extend(contract_gaps(item, extra, root=root, path=where, strict=strict))
            elif strict:
                gaps.append(f"{where}: 契约未声明（该对象为开放对象）")
    elif isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            gaps.extend(contract_gaps(item, schema["items"], root=root,
                                      path=f"{path}[{index}]", strict=strict))
    return gaps


def contract_path(name: str, *, required: bool = False):
    """契约文件的解析顺序：`VAO_SCHEMA_DIR` 优先，其次仓库布局，最后当前目录。

    返回 `Path`；找不到且 `required=False` 时返回 `None`（调用方必须把「契约没跑」
    说出口，不能悄悄当成通过——静默通过是契约最坏的失败模式）。
    """
    import os
    candidates = []
    env = os.environ.get("VAO_SCHEMA_DIR")
    if env:
        candidates.append(Path(env).expanduser() / name)
    here = Path(__file__).resolve().parent
    candidates += [here.parent / "schemas" / name, here / "schemas" / name,
                   Path.cwd() / "schemas" / name]
    found = next((p for p in candidates if p.is_file()), None)
    if found is None and required:
        raise SchemaError(f"契约文件不存在：{name}（已查 {len(candidates)} 个位置，"
                          f"可用 VAO_SCHEMA_DIR 指定）")
    return found


def declared_properties(schema: dict, name: str) -> set[str]:
    """`$defs.<name>` 里声明的属性名（用于反向检查：契约字段是否真的被产出）。"""
    defs = (schema.get("$defs") or {}).get(name) or {}
    return set((defs.get("properties") or {}).keys())
