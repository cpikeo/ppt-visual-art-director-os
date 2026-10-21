"""engine-baseline：**不做判断**的对照排版。

它回答一个问题：「把同一份内容交给一个不看判断层的排版器，会得到什么？」
每页 = 标题 + 正文两段，居中阅读轴，不选角色、不选证据形态、不排焦点层级、不写出处、
不生成图表、不判断媒体必要性。除了 `canvas` 与 `theme` 之外，它只读 brief 的 title/content。

它不是 model-baseline：没有模型参与，也不代表「人不用这个技能时会怎样」。
它衡量的是**判断层本身贡献了多少可测差异**——所以报告里必须写明这一点。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

THEME = {
    "colors": {"background": "#F5F4F1", "ink": "#14140F", "muted": "#6A6A64",
               "primary": "#14140F", "secondary": "#6A6A64", "accent": "#14140F"},
    "fonts": {"cn": "Source Han Serif SC", "latin": "Georgia"},
}
CANVAS = {"width": 1280, "height": 720, "grid_columns": 12, "grid_unit": 8}


def _text(eid: str, x: int, y: int, w: int, h: int, text: str, size: int,
          *, bold: bool = False, color: str = "ink", role: str | None = None) -> dict:
    el = {"id": eid, "type": "text", "x": x, "y": y, "width": w, "height": h,
          "text": text, "size": size, "color": color, "font": "Georgia",
          "bold": bold, "align": "left"}
    if role:
        el["role"] = role
    return el


def build(brief: dict) -> dict:
    """brief → 无判断 spec。字段名与 build.py 完全一致，便于走同一条 check。"""
    slides = []
    for index, slide in enumerate(brief.get("slides") or [], start=1):
        sid = slide.get("id") or f"s{index:02d}"
        title = str(slide.get("title") or "")
        body = str(slide.get("content") or "")
        elements = [_text(f"{sid}_t", 96, 88, 1088, 140, title, 34, bold=True)]
        if body:
            elements.append(_text(f"{sid}_b", 96, 260, 1088, 340, body, 17, color="muted"))
        slides.append({"id": sid, "elements": elements})
    return {"canvas": CANVAS, "theme": THEME, "slides": slides}


def build_from_path(brief_path: str | Path) -> dict:
    import intelligence
    return build(intelligence.load_brief(brief_path))


if __name__ == "__main__":
    import json
    print(json.dumps(build_from_path(sys.argv[1] if len(sys.argv) > 1 else
                                     ROOT / "templates" / "brief.yml"),
                     ensure_ascii=False, indent=1))
