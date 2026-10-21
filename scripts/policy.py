# -*- coding: utf-8 -*-
"""policy.py · 可调策略的**唯一结构化来源**（数据，不含算法）

分层纪律（与 SKILL.md §4 / references/contract.md「策略与契约」一致）：

| 层 | 谁管 | 这里放什么 |
|---|---|---|
| 判断协议 | `SKILL.md` | 原则、判断链、反例、冲突处理、验收口径（散文，不写数值） |
| 可调策略 | **本文件 / `policy.json`** | 权重、阈值、枚举、映射——只描述「多少算多」，不描述「怎么算」 |
| 确定性推导 | `intelligence.py` 等 | 内容解析、评分计算、候选排序、同分决胜、理由组装 |
| 数据契约 | `schemas/*.schema.json` | 结构、类型、必需字段、合法枚举；跨字段语义仍由 Python 查 |

**为什么不是 Markdown 表格**：阈值写在文档里就必然与代码分叉（改了文档不改代码，
或反过来）。文档只写判断协议，数值只在这里有一份；`selftest.py` 双重锁定：
① 每个键都被代码真正读取（无死键，见 `test_policy_contract`）；
② 外部 `policy.json` 覆盖必须逐键校验类型与取值范围，未知键直接报错（不静默忽略）。

**为什么不是 LLM**：这些量是「阅读密度、行长可读域、同分顺序」——它们必须可复现、
可审计。换成模型建议，同一份 brief 两轮就会给出不同的构图。

覆盖方式（作者/研究者调参，不改代码）：

    python scripts/vao.py plan brief.yml --out plan.json --policy my_policy.json

`my_policy.json` 只写要改的键（深度合并），并在 plan 的 `deck.policy` 里留下
生效策略的摘要与覆盖键清单——判断可追溯到「当时用的是哪一版策略」。
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────
# 默认策略（唯一来源；下列每个键都在 intelligence.py 里被读取）
# ─────────────────────────────────────────────────────────────────────
POLICY: dict = {
    "version": "2026.10-judgment-p2",

    # ── 枚举：合法取值与**同分决胜顺序** ────────────────────────────────
    # 顺序即优先级：证据形态打平时靠前的一方胜出（`max(..., -(index))`）。
    "enums": {
        "evidence": ["comparison", "series", "part_whole", "number", "structure",
                     "sequence", "proposition", "none"],
        "role": ["establish", "explain", "compare", "prove", "persuade", "summarize"],
        # 构图算子的平局顺序：空间优先（留白 → 数据场 → 线性 → 张力 → 编辑 → 图像）。
        # 它只在分数打平时生效，不能盖过内容判断。
        "composition": ["big_whitespace", "data_field", "linear_structure",
                        "asymmetric_tension", "editorial", "image_narrative"],
        # 视觉世界的构图纪律 → 同分倾向（0.75 分，不足以推翻内容判断）。
        # 键 = derive_world 实际会产出的三个纪律；此前还列了 grid / quiet /
        # spotlight / linear 四个**永不出现**的键（没有代码产出这些值），
        # 属于「看起来很完整」的死规则：改它们不改变任何判断。
        # `selftest.test_policy_contract` 锁定「产出的纪律 ⊆ 本表键」，
        # 新增世界纪律时必须同时给出倾向，否则那条纪律静默不生效。
        # 值写 null = 该纪律**明确不做同分倾向**（严格网格不偏袒任何算子，
        # 平局交给 enums.composition 的顺序）。写明 null 与「键不存在」不同：
        # 键的存在本身是「这条纪律被想过」的证据。
        "composition_grammar_preference": {
            "evidence_field": "data_field", "soft_asymmetry": "asymmetric_tension",
            "strict_grid": None,
        },
        "density": ["sparse", "balanced", "dense"],
        "rhythm": ["open", "build", "breathe", "turn", "hold", "close"],
        "emphasis": ["climax", "quiet", "lead", "support"],
        "media": ["required", "reuse", "none"],
        "focus_type": ["text", "chart", "image"],
        # 判断来源（SKILL §3 三态 + 两个事实来源）：author 作者声明 / judgment 算法推导 /
        # hint 词表提示（未决）／decision 由决定类型推导／frame 凭证帧（首末页）／
        # absent 内容本身缺席。后两个不是「谁定的」，是**没有判断者**的两种如实记录：
        # 少了它们，provenance_of 会把这些情况硬塞进三态，等于给出一个不存在的判断者。
        # 词汇与 schemas/plan.schema.json 的 enumProvenance 必须逐项一致（selftest 锁）。
        "provenance": ["author", "judgment", "hint", "decision", "frame", "absent"],
        "claim_source": ["declared", "extracted", "absent", "frame"],
        # 说明：以下枚举里，evidence / composition / density 的同分顺序被代码读取
        # （policy.enum(...)，顺序即优先级）；role / rhythm / emphasis / media /
        # focus_type / provenance / claim_source / tension_source 是**词汇表**：
        # 代码不按它们排序，但契约（schemas/plan.schema.json 的 $defs.enum*）与
        # 校验共用同一份词表；`selftest.test_policy_contract` 强制「每个枚举要么
        # 被代码读取、要么被契约引用」，两处都不占的枚举就是死词汇，直接红。
        "tension_source": ["author", "deck", "not_asserted"],
        # 构图 → 密度目标（生产规格；不是页面模板）
        "density_target_of_composition": {
            "big_whitespace": "sparse", "editorial": "balanced", "data_field": "dense",
            "image_narrative": "sparse", "linear_structure": "balanced",
            "asymmetric_tension": "balanced",
        },
    },

    # ── 构图：分数项（算法在 intelligence._composition_scores）─────────
    "composition": {
        "absent": -99.0,            # 「内容不成立」的算子分数：连候选都不是
        "grammar_preference_bonus": 0.75,
        # 平局重选时允许的分数差：只在「与前一页同构且分数接近」时换算子
        "avoid_tolerance": 0.5,
        # 阈值：多少个数字才算「一组证据」
        "evidence_field_min_numbers": 2,
        "evidence_field_multi_numbers": 3,
        "evidence_field_density_min": 6.0,
        "single_number": 1,
        "many_numbers_min": 3,
        "short_text_max": 40,       # 短文本（一句话页）
        "long_text_min": 60,        # 撑得起编辑节奏
        "very_long_text_min": 120,  # 编辑节奏的第二档
        "terms": {
            "image_present": 4.5, "image_establish_bonus": 1.5,
            "data_evidence_aligned": 3.0, "data_multi_numbers": 2.0,
            "data_density": 1.0, "data_comparison": 0.5,
            "whitespace_single_number": 3.0, "whitespace_part_whole": 3.25,
            "whitespace_persuade": 2.0, "whitespace_short_text": 1.0,
            "whitespace_many_numbers": -1.5, "whitespace_no_claim": 1.0,
            "whitespace_establish": 1.5, "whitespace_summarize": 1.5,
            "linear_relations": 4.5, "linear_evidence": 3.0,
            "asymmetric_comparison": 2.5, "asymmetric_role": 1.5,
            "asymmetric_numbers": 1.0,
            "editorial_long_text": 2.0, "editorial_summarize": 1.5,
            "editorial_no_numbers": 1.0, "editorial_very_long_text": 0.5,
        },
    },

    # ── 信息权重（三档）与删除候选 ───────────────────────────────────
    "information_weight": {
        # 高密度页判据：正文超过 110 字或不同数字 ≥5 个 → 列删除候选供作者裁决。
        # 阈值只决定「是否需要裁决」，不决定删什么。
        "dense_chars": 110,
        "dense_numerals": 5,
        # 贡献分 = overlap_weight × 与主张的二元组重合率 − number_penalty × 句内非主张数字数
        "overlap_weight": 2.0,
        "number_penalty": 0.25,
        "delete_candidates_max": 3,
        "delete_candidate_excerpt": 28,   # 候选句摘录长度（字）
        "maximize_secondary_max": 2,      # 主张里非主语量的最多上屏数
        "support_numerals_max": 4,        # 支撑数字最多上屏数
        "duplicate_min": 2,               # 同页同值出现几次算「重复」
        "excerpt_max": 26,                # 主张摘要长度（字）
    },

    # ── 证据形态：分数项与判据阈值（算法在 intelligence.understand）──────
    # 这些数决定「同一页里谁能胜出」：序列 0.55 起步、构成 0.92，不是风格，
    # 是可复核的先后。放在代码字面量里，作者想「我这版稿子对构成更保守」就只能改源码
    # ——那等于没有策略层。它们不描述**怎么算**（判据、正则、语义仍住 intelligence）。
    "evidence_shapes": {
        # comparison：两端对照/并列量；step×min(distinct, cap) 让「量越多越是比较」
        "comparison_base": 0.6, "comparison_step": 0.1, "comparison_step_cap": 3,
        # part_whole：算术/「其余/其中」坐实的构成，比仅凭语义措辞的构成更硬
        "part_whole_decomposed": 0.92, "part_whole_implied": 0.84,
        # series：同单位 + 时间轴；step×min(distinct, cap)
        "series_base": 0.55, "series_step": 0.08, "series_step_cap": 4,
        "series_from_arrow": 0.81,      # 两个量被箭头连起来：变化，不是步骤模板
        "number": 0.7,                  # 全页只有一个量
        # structure：强结构词/两个结构词/阈值列举/显式关系
        "structure": 0.65, "structure_from_relations": 0.9,
        "structure_hits_min": 2,
        # sequence：流程名或两个以上顺序标记
        "sequence_base": 0.6, "sequence_step": 0.05, "sequence_step_cap": 4,
        "sequence_hits_min": 2,
        "sequence_from_marker": 0.75,
        "sequence_phased_explicit": 0.9, "sequence_phased_implicit": 0.7,
        "proposition": 0.55,            # 只有「必须/决定/建议」这类结论词
        # 判据阈值（不是分数）
        "points_min": 2,                # 至少两个取值才谈得上形状
        "parallel_min_values": 3,       # 同单位 ≥3 个不同取值 = 并列可比量
        "share_min_numerals": 2,        # 单句份额陈述至少要有一个分子与分母量
        "pct_whole_sum": 100,           # 百分比构成：加总目标
        "pct_whole_tolerance": 0.5,     # 加总容差（四舍五入）
        "chart_comparison_max_years": 2,  # 有图且年份 <2 才按「比较」计分
        "panel_min_numerals": 3,        # 多指标面板（证据页，不是观点页）的最小量数
    },

    # ── 分解：子项相加等于整体的判据参数（算法在 _decomp_total）──────────
    "decomposition": {
        "min_unique_values": 4,   # 少于 4 个不同取值不可能有「三个子项 + 一个整体」
        "max_values": 8,          # 多于 8 个：算术巧合的概率高到不可用
        "min_parts": 3,           # 三项以上才算分解；两项相加在比率/日期里太常见
        "max_parts": 4,
        "sum_tolerance": 0.005,   # 相对容差：吸收四舍五入
    },

    # ── 输出体积：plan.json 是作者的上下文成本 ──────────────────────────
    "output": {
        # 同一句说明在 ≥2 页重复、且长于该值时才上提到 deck.legend；
        # 短句上提反而让作者来回跳（legend 只值一次阅读）。
        "legend_hoist_min_chars": 16,
    },

    # ── 焦点：数字是主语还是支撑 ──────────────────────────────────────
    "focus": {
        # 主张没点名任何量、证据横跨 ≥3 种量纲、且没有单一指标占住半页
        # → 数字退支撑位，第一落点回到那句话
        "support_only_units_min": 3,
        "support_only_concentration_max": 0.5,
        # 数字 ≥6 个：一条序列，不是两端对照（焦点交给图表而不是并置文本框）
        "chart_many_numbers_min": 6,
        # 主张 ≤42 字时，「立住那句话」比「摆一排数字」更像这一页的职责
        "short_claim_max": 42,
    },

    # ── 排版可读域（不是字阶模板）───────────────────────────────────
    "measure": {
        "max_cjk": 45,          # 一行超过 45 个汉字：投影尺度回扫丢行
        "min_cjk": 22,          # 少于 22 个：每行在半句处折断
        "lead_max_cjk": 20,     # 主张/标题每行上限：靠行数不靠缩放
        "long_text_chars": 220,   # ≥ 此长度：长文窄栏 30 字
        "mid_text_chars": 120,    # ≥ 此长度：中长文本 34 字
        "cjk_long": 30, "cjk_mid": 34, "cjk_short": 38,
        "rewrite_over_lead_lines": 2,   # 主张超过 N 行 × 每行上限 → 先改写
    },

    # ── 图表 kind 由证据形状推导（形状来自证据，不来自装饰）──────────
    "chart_kind": {
        "part_whole_donut_max": 5,      # 扇区 ≤5 才配环形；更多用横条
        "series_line_min_points": 3,    # 同单位 ≥3 点才是折线；2 点用柱
        "single_number_max": 1,         # 单一量 → kpi
    },

    # ── 生产规格 ────────────────────────────────────────────────────
    "production": {
        "must_not_max": 2,        # 明确禁令最多写几条（多写就变清单噪音）
    },
}

# 允许被覆盖的顶层分组（白名单：新增分组要先在这里登记，避免悄悄长出一个新层）
_GROUPS = ("enums", "composition", "information_weight", "evidence_shapes",
           "decomposition", "focus", "measure", "chart_kind", "production", "output")
# 覆盖文件的元键：不参与深度合并，只用于审计
_META_KEYS = ("note", "author", "updated", "_comment")

_OVERRIDES: dict = {}          # 当前生效的覆盖（已校验）


# ─────────────────────────────────────────────────────────────────────
# 校验与合并
# ─────────────────────────────────────────────────────────────────────
def _type_ok(value, default) -> bool:
    """覆盖值的类型必须与默认值同族（bool 不是 int：True 会静默变成 1）。"""
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(default, dict):
        return isinstance(value, dict)
    if isinstance(default, list):
        return isinstance(value, list)
    return isinstance(value, type(default))


def _walk_unknown(node, default, path="") -> list[str]:
    """覆盖键必须在默认策略里存在：写错一个键名等于没调，必须报错而不是静默忽略。"""
    unknown = []
    for key, value in node.items():
        if key in _META_KEYS:
            continue
        where = f"{path}.{key}" if path else key
        if not isinstance(default, dict) or key not in default:
            unknown.append(where)
            continue
        if isinstance(value, dict):
            unknown.extend(_walk_unknown(value, default[key], where))
    return unknown


def validate(overrides) -> dict:
    """校验覆盖文件；返回规范化后的副本。非法即 ValueError（不静默回落）。"""
    if not isinstance(overrides, dict):
        raise ValueError(f"策略覆盖必须是对象，实际是 {type(overrides).__name__}")
    bad_group = [k for k in overrides if k not in _GROUPS and k not in _META_KEYS]
    if bad_group:
        raise ValueError("策略覆盖含未知分组：" + "、".join(sorted(bad_group))
                         + f"（允许：{'、'.join(_GROUPS)}）")
    unknown = _walk_unknown({k: v for k, v in overrides.items() if k in _GROUPS}, POLICY)
    if unknown:
        raise ValueError("策略覆盖含未知键：" + "、".join(sorted(unknown))
                         + "（键名必须是 policy.py 默认策略里已有的键）")
    problems: list[str] = []

    def _check(node: dict, default: dict, path: str) -> None:
        for key, value in node.items():
            if key in _META_KEYS:
                continue
            where = f"{path}.{key}" if path else key
            base = default[key]
            if isinstance(base, dict) and isinstance(value, dict):
                _check(value, base, where)
                continue
            if not _type_ok(value, base):
                problems.append(f"{where}: 需要 {type(base).__name__}，实际 {type(value).__name__}")
                continue
            if isinstance(base, list) and base and all(isinstance(x, str) for x in base):
                if not all(isinstance(x, str) for x in value):
                    problems.append(f"{where}: 枚举列表只能写字符串")
            if isinstance(base, (int, float)) and not isinstance(base, bool) and value < 0 \
                    and base >= 0:
                problems.append(f"{where}: 阈值/权重不得为负（{value}）")

    _check({k: v for k, v in overrides.items() if k in _GROUPS}, POLICY, "")
    if problems:
        raise ValueError("策略覆盖不合法：" + "；".join(problems))

    # 枚举覆盖不许破坏「同分顺序」的自洽：构图枚举必须覆盖默认集合，
    # 否则平局决胜会因缺项落到默认值上，判断悄悄变了。
    for name, default in POLICY["enums"].items():
        if not isinstance(default, list):
            continue
        want = (overrides.get("enums") or {}).get(name)
        if isinstance(want, list) and set(want) != set(default):
            raise ValueError(f"策略覆盖 enums.{name} 必须与默认集合相同"
                             f"（顺序可调，成员不可增删）：差集 "
                             f"{sorted(set(want) ^ set(default))}")
    return copy.deepcopy({k: v for k, v in overrides.items() if k in _GROUPS})


def load(path) -> dict:
    """载入 policy.json 覆盖并**就地**合并进 POLICY；返回生效覆盖。"""
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"策略文件不存在：{p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"策略 JSON 解析失败：{p}:{exc.lineno}:{exc.colno} — {exc.msg}") from None
    configure(data)
    return data


def configure(overrides: dict) -> None:
    """校验后就地合并（就地：已 import 的模块持有的是同一份嵌套 dict）。"""
    clean = validate(overrides)
    for group, values in clean.items():
        if isinstance(values, dict):
            _merge(POLICY[group], values)
        else:                                   # pragma: no cover - 白名单里没有标量组
            POLICY[group] = values
    _OVERRIDES.clear()
    _OVERRIDES.update(clean)


def _merge(target: dict, values: dict) -> None:
    for key, value in values.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge(target[key], value)
        else:
            target[key] = value


def reset() -> None:
    """回到默认策略（测试用：覆盖必须是可撤销的，否则测试之间会互相污染）。"""
    for group, values in copy.deepcopy(_DEFAULTS).items():
        POLICY[group] = values
    _OVERRIDES.clear()


# ─────────────────────────────────────────────────────────────────────
# 溯源：每份 plan 记下「用的是哪一版策略、改过哪些键」
# ─────────────────────────────────────────────────────────────────────
def digest() -> str:
    """生效策略的稳定摘要（键序无关）。"""
    blob = json.dumps(POLICY, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def overrides_list() -> list[str]:
    """当前覆盖涉及的键路径（点号表示），进 plan 供作者核对。"""
    out: list[str] = []

    def _walk(node, path=""):
        for key, value in node.items():
            where = f"{path}.{key}" if path else key
            if isinstance(value, dict):
                _walk(value, where)
            else:
                out.append(where)

    _walk(_OVERRIDES)
    return sorted(out)


def summary() -> dict:
    """进 plan.deck.policy 的最小事实：版本、摘要、覆盖键、分组白名单。"""
    return {"version": POLICY["version"], "sha256": digest(),
            "overrides": overrides_list() or None,
            "tunable_groups": list(_GROUPS)}


def enum(name: str) -> list:
    """枚举取值（顺序即同分优先级）。未知名字直接报错——拼错会静默产生空列表。"""
    if name not in POLICY["enums"]:
        raise KeyError(f"policy 没有枚举 {name!r}（已有：{', '.join(POLICY['enums'])}）")
    return POLICY["enums"][name]


def group(name: str) -> dict:
    if name not in _GROUPS:
        raise KeyError(f"policy 没有分组 {name!r}（已有：{', '.join(_GROUPS)}）")
    return POLICY[name]


_DEFAULTS = copy.deepcopy(POLICY)
