# -*- coding: utf-8 -*-
"""运行时事实模型（RunEvidence）与 COLD/HOT 契约。

一次运行只产出**一个** RunEvidence：所有身份与读数都写进它，报告、清单、预览证据
都从这里取。此前同一批事实散在 result / workflow / compile_report / ghost / budget
等若干临时 dict 里，谁都能写、谁都能读，于是同一个事实被反复表达（v6.2 审计：
文件摘要 ×5、幽灵来源 ×3、spec 家族 ×3 套独立实现）。现在只有这一处：

    input_identity    输入是谁     spec 投影指纹 + 构建文件字节凭证
    asset_identity    资产是谁     清单摘要 + 清单文件凭证
    digest            产物是谁     output_witness{size, mtime_ns, sha256}
    qc_identity       判定是谁     清单摘要 + 量像素的引擎指纹 + 取样参数
    render_identity   像素是谁     渲染器指纹 + 逐页身份（画布/主题/页/尺度）
    page_identity     页是谁       这一轮真画了哪几页、哪几页命中上一轮
    measurements      花了什么     各阶段耗时 + 解码 / 变换 / 读取计数
    reuse             复用了什么   每一条「还是那一份」的凭证与理由

字段名与内部结构由本模块唯一声明；报告只读它，不再各自拼装。身份值一律来自
primitives 身份层（identity / file_digest / byte_witness / engine_fingerprint），
本模块不自己算任何哈希。

────────────────────────────────────────────────────────────────────────────
COLD / HOT 契约（架构的一部分，不是性能技巧）
────────────────────────────────────────────────────────────────────────────

    COLD   identity → measure → evidence → compile → render
    HOT    identity → evidence → release

* COLD 是「这一轮重新建立事实」：量像素、编译产物、渲染页面。
* HOT 是「这一轮只取已有事实」：读凭证、取证据、发出去。**不测量、不编译、不渲染**。
* 判定（guard / QA 结论）**永远当场执行**：判断必须新鲜，它不是可以复用的证据。
* 允许复用 ≠ 放弃证明：HOT 成立的前提是每一步都给出凭证（见 `reuse`），
  凭证不足时该步自动落回 COLD 并记录原因（`cold_reasons`）。
* 任何新增步骤都必须回答：**属于 cold 还是 hot；为什么 hot path 需要重做。**
  答不出「为什么必须重做」的步骤不准放进 hot path——那说明它是 COLD 的活。
"""

from __future__ import annotations

EVIDENCE_VERSION = "vao-evidence-v1"

COLD_PATH = ("identity", "measure", "evidence", "compile", "render")
HOT_PATH = ("identity", "evidence", "release")
# 只有这三件事算「重新建立事实」：它们在 hot path 上出现即说明这一轮不是 HOT。
COLD_ONLY = ("measure", "compile", "render")

FIELDS = ("input_identity", "asset_identity", "digest", "qc_identity",
          "render_identity", "page_identity", "measurements", "reuse")


class RunEvidence:
    """运行时事实的唯一容器（dict 模型，不做任何计算）。

    用法：
        ev = RunEvidence(run_id=..., mode=..., speed=...)
        ev.identity("input", spec=..., build=...)
        ev.reuse("compile", "产物未重编（投影 + 引擎指纹 + 产物凭证一致）", witness="size+mtime_ns")
        ev.downgrade("render", "本轮真画 4 页（页身份未命中）")
        ev.measure("compile_ms", 1180)
        result["evidence"] = ev.as_dict()
    """

    def __init__(self, *, run_id: str | None = None, mode: str = "draft",
                 speed: str = "fast") -> None:
        self.run_id = run_id
        self.mode = mode
        self.speed = speed
        self.data: dict = {name: {} for name in FIELDS}
        self.data["reuse"] = []
        self.data["cold_reasons"] = []
        self.data["path"] = "hot"          # 先假设可复用；任何一步真的重做就降级为 cold

    # ── 身份（只接受身份层算出的值）────────────────────────────────────────
    def identity(self, field: str, **values) -> "RunEvidence":
        """记一组身份。field 取 input / asset / digest / qc / render / page。"""
        key = f"{field}_identity" if field != "digest" else "digest"
        if key not in self.data:
            raise KeyError(f"未知身份字段: {field}（合法值 input/asset/digest/qc/render/page）")
        self.data[key].update(values)
        return self

    # ── 测量（耗时 / 计数）────────────────────────────────────────────────
    def measure(self, key: str, value, *, stage: str | None = None) -> "RunEvidence":
        bucket = self.data["measurements"]
        if stage:
            bucket.setdefault(stage, {})[key] = value
        else:
            bucket[key] = value
        return self

    # ── 复用与降级：同一件事只有两种合法结局 ────────────────────────────────
    def reuse(self, fact: str, why: str, *, witness: str | dict | None = None) -> "RunEvidence":
        """某一步被证明「还是那一份」：记 fact（哪一步）、why（为什么可以复用）、witness（凭证）。"""
        entry = {"step": fact, "why": why}
        if witness is not None:
            entry["witness"] = witness
        # 同一步骤只保留一条（重复登记说明调用点写重了）
        self.data["reuse"] = [e for e in self.data["reuse"] if e.get("step") != fact]
        self.data["reuse"].append(entry)
        return self

    def downgrade(self, step: str, why: str) -> "RunEvidence":
        """某一步没能复用：落回 COLD 并记录原因（路径随之变成 cold）。"""
        if step not in COLD_ONLY:
            raise ValueError(f"只有 {COLD_ONLY} 属于 cold-only 步骤，收到 {step}")
        self.data["path"] = "cold"
        self.data["cold_reasons"].append({"step": step, "reason": why})
        return self

    def blocked(self, reason: str) -> "RunEvidence":
        """这一轮没有产出：不主张任何复用。

        BLOCKED 的稿子没有产物，也就没有「复用」可言——此时打印 HOT/COLD 是
        用性能语言掩盖一个失败。把它写成第三种事实：未成立，并给出阻断原因。
        """
        self.data["status"] = "blocked"
        self.data["blocked_reason"] = reason
        self.data["path"] = "none"
        self.data["cold_reasons"] = []
        self.data["reuse"] = []
        return self

    # ── 收口 ──────────────────────────────────────────────────────────────
    def finish(self) -> "RunEvidence":
        self.data["version"] = EVIDENCE_VERSION
        self.data["run_id"] = self.run_id
        self.data["mode"] = self.mode
        self.data["speed"] = self.speed
        self.data["stages"] = list(
            HOT_PATH if self.data["path"] == "hot" else () if self.data["path"] == "none"
            else COLD_PATH)
        self.data["reused_steps"] = [e["step"] for e in self.data["reuse"]]
        self.data["cold_steps"] = sorted({c["step"] for c in self.data["cold_reasons"]})
        self.data["contract"] = "ok" if not self.contract_issues() else "violated"
        return self

    def contract_issues(self) -> list:
        """契约自检：只在真实违反时返回非空（正常运行恒为空）。

        * HOT 不得出现在 cold-only 步骤上做过事；
        * HOT 的复用必须有凭证（witness）；
        * COLD 的每一步降级都必须有原因（无原因的降级＝偷偷重做）。
        """
        issues = []
        if self.data["path"] == "none":       # 未成立：既没有冷步骤，也不主张复用
            return issues
        if self.data["path"] == "hot":
            done = {c["step"] for c in self.data["cold_reasons"]}
            if done:
                issues.append(f"HOT 路径上出现了 cold-only 步骤：{sorted(done)}")
            for entry in self.data["reuse"]:
                if "witness" not in entry:
                    issues.append(f"复用「{entry['step']}」没有凭证：{entry['why']}")
        else:
            for cold in self.data["cold_reasons"]:
                if not str(cold.get("reason") or "").strip():
                    issues.append(f"cold 步骤「{cold.get('step')}」没有记录重做原因")
        return issues

    def as_dict(self) -> dict:
        return self.data
