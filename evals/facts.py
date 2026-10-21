"""一次运行的事实采集：把「跑了一遍」变成一份可复核的 JSON。

设计纪律：

1. **不在评测器里重新实现判断**。plan 事实来自 `vao.py plan` 落盘的 plan.json，
   产物事实来自 `vao.py check --json` 的 verdict 与 pptx 本身，结构事实来自 `ghost`
   的四个公开登记表。评测器只**读事实**，不解释事实。
2. **时间用墙钟**：一次 CLI 调用 = 一次 subprocess，计时含解释器启动——这与作者真实
   体验一致（用户敲的就是这条命令）。
3. **没有模型就没有 token**：本文件不报 token（`total_tokens: null`），不假装有。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _run(cmd: list[str], cwd: pathlib.Path) -> dict:
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return {"cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout,
            "stderr": proc.stderr, "seconds": round(time.perf_counter() - started, 3)}


def native_chart_count(pptx_path: pathlib.Path) -> int | None:
    """产物里有几个**原生可编辑图表**（不是被压成图片的图）。"""
    try:
        from pptx import Presentation
    except ImportError:
        return None
    count = 0
    for slide in Presentation(str(pptx_path)).slides:
        for shape in slide.shapes:
            if getattr(shape, "has_chart", False):
                count += 1
    return count


def ghost_facts(spec_path: pathlib.Path, workdir: pathlib.Path) -> dict:
    """渲染一次预览，读四个公开登记表（截断/出画布/字面回落/字体替换）。

    在**子进程**外单独做一次，是为了不把 check 的产物流程拆开重写；代价是多画一次
    预览（约 0.1–0.3 s），换来的是「评测器不复制渲染逻辑」。
    """
    sys.path.insert(0, str(SCRIPTS))
    import ghost
    import vao
    spec = vao.load_spec(spec_path)
    out = workdir / "_ghost_facts"
    out.mkdir(parents=True, exist_ok=True)
    pages = ghost.ghost_deck(spec, out)
    return {"pages_drawn": len(pages),
            "truncations": ghost.text_truncations(),
            "out_of_canvas": ghost.out_of_canvas(),
            "font_fallbacks": ghost.font_fallbacks(),
            "font_substitutions": ghost.font_substitutions()}


def spec_summary(spec_path: pathlib.Path) -> dict:
    """编排名（spec）自己的可数事实：出处行、图表元素、文字量、显式角色。

    这些是**判断层的产出**（判断决定写不写出处、有没有图表、给谁 role），
    所以它们能区分「有判断」与「只是把字排开」——结构类断言（PASS/页数/体积）区分不了。
    """
    sys.path.insert(0, str(SCRIPTS))
    import vao
    loaded = vao.load_spec(spec_path)
    spec = loaded[0] if isinstance(loaded, tuple) else loaded     # load_spec 返回 (spec, path)
    slides = spec.get("slides") or []
    roles: list[str] = []
    charts = 0
    chars = 0
    for slide in slides:
        for element in slide.get("elements") or []:
            if element.get("type") == "chart":
                charts += 1
            if element.get("role"):
                roles.append(str(element["role"]))
            chars += len(str(element.get("text") or ""))
    return {"slides": len(slides), "roles": roles, "charts": charts, "text_chars": chars}


def collect(brief: pathlib.Path, run_dir: pathlib.Path,
            build: pathlib.Path | None = None, *, run_plan: bool = True) -> dict:
    """跑一条用例：plan 必跑；给了 build 才跑 release。返回事实字典。"""
    outputs = run_dir / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    plan_path = outputs / "plan.json"
    steps: list[dict] = []
    facts: dict = {"brief": str(brief), "steps": steps}

    if run_plan:
        plan_step = _run([sys.executable, str(SCRIPTS / "vao.py"), "plan", str(brief),
                          "--out", str(plan_path), "--json"], run_dir)
        steps.append({"name": "plan", **plan_step})
        facts["plan_returncode"] = plan_step["returncode"]
        facts["plan_seconds"] = plan_step["seconds"]
        facts["plan"] = (json.loads(plan_path.read_text(encoding="utf-8"))
                         if plan_path.exists() else None)
    else:
        facts["plan_returncode"] = None
        facts["plan_seconds"] = None
        facts["plan"] = None

    if build is None:
        facts["release"] = None
        return facts

    deck = outputs / "deck.pptx"
    preview = outputs / "preview"
    check_step = _run([sys.executable, str(SCRIPTS / "vao.py"), "check", str(build), str(deck),
                       "--mode", "release", "--speed", "strict", "--json",
                       "--preview", str(preview)], run_dir)
    steps.append({"name": "check", **check_step})
    verdict = None
    text = check_step["stdout"].strip()
    if text.startswith("{"):
        verdict = json.loads(text)
    facts["check_returncode"] = check_step["returncode"]
    facts["check_seconds"] = check_step["seconds"]
    facts["verdict"] = verdict
    facts["pptx"] = {
        "exists": deck.exists(),
        "bytes": deck.stat().st_size if deck.exists() else 0,
        "native_charts": native_chart_count(deck) if deck.exists() else None,
    }
    # 预览图平铺进 outputs/，viewer 只列 outputs 目录的第一层文件
    if preview.is_dir():
        for png in sorted(preview.glob("*.png")):
            target = outputs / f"preview-{png.name}"
            if not target.exists():
                target.write_bytes(png.read_bytes())
    try:
        facts["spec"] = spec_summary(build)
    except Exception as exc:                       # noqa: BLE001
        facts["spec"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        facts["ghost"] = ghost_facts(build, run_dir)
    except Exception as exc:                       # noqa: BLE001 - 采集失败要留痕，不吞
        facts["ghost"] = {"error": f"{type(exc).__name__}: {exc}"}
    return facts


if __name__ == "__main__":
    print(__doc__)
