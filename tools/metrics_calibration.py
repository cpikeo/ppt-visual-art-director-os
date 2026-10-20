# -*- coding: utf-8 -*-
"""三度量对拍：guard 估算 / ghost 折行 / LibreOffice 真排。

同一段文字在三个地方被数「会排几行」：guard（verify._text_box_capacity）、
ghost（预览折行）、PowerPoint。三者对不上时，guard 会放行一个会溢出的框，
或拦下一个其实排得下的框。

这里用 LibreOffice 当仲裁：一批探针 → 一次编译 → 一次渲染 → 用
`pdftotext -bbox` 读每个词的坐标，按基线聚成行。**不用像素行带**：中文单字
内部就有整行空白（「元」上下两横之间），按空白切带会把一个字算成两行。

LibreOffice 对 spAutoFit 的处理是「溢出就缩字」，行数因此不可比；缩字页会被
识别出来并剔除（`em < 0.97`），不计入一致率——那类页的真值只有 PowerPoint 能给。

依赖：libreoffice（soffice）、poppler-utils（pdftotext）、本机装有主题字体
（Noto Serif/Sans CJK）。缺依赖时以返回码 2 退出并说明，不假装跑过。

用法：
    python3 tools/metrics_calibration.py [--out report.json] [--widths 160,240,...]
    python3 tools/metrics_calibration.py --smoke      # CI 冒烟（32 探针，~1s）
"""

from __future__ import annotations

import argparse
import json
import shutil
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TEXTS = [
    # 真实稿件里的句子（来自 audit/sm 的 build_deck.py）
    ("deck_s02_title", "上海 6 家成熟店，单店模型已经稳定", 44, "serif"),
    ("deck_s02_note", "利润率按门店层面计，不含总部费用；租金含物业与公摊。", 17, "serif"),
    ("deck_s02_kpi", "11.8%", 84, "serif"),
    ("deck_s07_title", "两家店全部关停，净损失约 7,100 万日元", 44, "serif"),
    ("deck_s07_body", "投入 8,400 万日元；押金回收 60%、设备残值 25%，合计可回收 1,290 万。", 18, "serif"),
    ("deck_s08_ask", "请批准第一批 8,400 万日元的资本开支", 40, "serif"),
    ("cjk_short", "单店模型", 18, "serif"),
    ("cjk_body", "上海六家成熟店在同一套产品与人力配置下的单店模型已经稳定", 18, "serif"),
    ("cjk_body2", "东京核心商圈租金约为上海的百分之二点三倍，需重算单店盈亏平衡", 18, "serif"),
    ("cjk_long", "先让观众知道要判断什么，再给出证据：审阅者只在一处看到结论，其余都是支撑", 20, "sans"),
    ("mix_pct", "租金占营收 11.8%，门店利润率 21.4%，两项均为 2026 年 1–9 月均值", 18, "serif"),
    ("mix_money", "投入 8,400 万日元；押金回收 60%、设备残值 25%，合计可回收 1,290 万", 20, "sans"),
    ("latin", "Stores opened in two batches, each verified against the same unit model.", 18, "serif"),
    ("numbers", "ARPU 1,284 元 · NPS 61 · 复购率 38.2% · 客单价 34 元", 20, "sans"),
    ("title", "东京的租金会把利润率压到 12%", 44, "serif"),
    ("title2", "两家店全部关停，净损失约 7,100 万日元", 40, "serif"),
]

FONTS = {
    "serif": {"cn": "Noto Serif CJK SC", "latin": "Noto Serif CJK SC"},
    "sans": {"cn": "Noto Sans CJK SC", "latin": "Noto Sans CJK SC"},
}


def probes(widths):
    out = []
    for key, text, size, role in TEXTS:
        for w in widths:
            out.append({"id": f"{key}_{w}", "text": text, "size": size,
                        "width": w, "role": role})
    return out


def build_spec(items):
    slides = []
    for it in items:
        slides.append({"id": it["id"], "elements": [{
            "id": "t", "type": "text", "x": 40, "y": 40,
            "width": it["width"], "height": 640,
            "text": it["text"], "size": it["size"], "color": "ink",
            "line_height": 1.35}]})
    return {"canvas": {"width": 1280, "height": 720},
            "theme": {"colors": {"background": "#FFFFFF", "ink": "#111111",
                                 "muted": "#777777", "primary": "#111111",
                                 "secondary": "#777777", "accent": "#A2563F"},
                      "fonts": FONTS["serif"]},
            "slides": slides}


LINE_RE = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')


def pdf_lines(pdf: Path, pitch_pt) -> list[list[list[tuple]]]:
    """每一页 → 按基线聚类的词框。

    不用像素行带：中文单字内部就有整行空白（「元」上下两横之间），按空白切带
    会把一个字算成两行——这正是第一版仲裁器给标题2报 3 行的原因。PDF 里
    LibreOffice 自己给出了每个词的 y 坐标，按字距一行一簇，数簇即行数。
    """
    out = subprocess.run(["pdftotext", "-bbox", str(pdf), "-"],
                         check=True, capture_output=True, text=True).stdout
    pages, words = [], []
    for line in out.splitlines():
        if "<page " in line:
            words = []
        elif line.strip().startswith("</page>"):
            pages.append(words)
        else:
            m = LINE_RE.search(line)
            if m:
                x0, y0, x1, y1 = (float(v) for v in m.groups()[:4])
                words.append((x0, y0, x1, y1, m.group(5)))
    pitches = pitch_pt if isinstance(pitch_pt, (list, tuple)) else [pitch_pt] * len(pages)
    lines = []
    for page, pitch in zip(pages, pitches):
        tol = max(0.8, 0.45 * pitch)
        groups: list[list[tuple]] = []
        for w in sorted(page, key=lambda t: t[1]):
            if groups and abs(w[1] - groups[-1][0][1]) <= tol:
                groups[-1].append(w)
            else:
                groups.append([w])
        lines.append(groups)
    return lines


def effective_em(page_words, size_px: float) -> float | None:
    """从 PDF 词框反推「一个字有多宽」，用于识别 LibreOffice 的缩字自适配。

    Office 的 spAutoFit 在 LibreOffice 里被当成「溢出就缩字」：文本装不下时它
    把字号缩到刚好放得下，于是行数比真实排版少——这类页不能当排版真值用。
    判据：纯汉字词按 1.0 em 前进，量出的 em 小于 0.97×声明字号即视为已缩字。
    """
    from primitives import is_cjk
    best = None
    for x0, y0, x1, y1, text in page_words:
        if len(text) >= 2 and all(is_cjk(c) for c in text):
            em = (x1 - x0) / 0.75 / len(text)
            if best is None or len(text) > best[1]:
                best = (em, len(text))
    return (best[0] / size_px) if (best and size_px) else None


def pdf_flat(pdf: Path) -> list[list[tuple]]:
    """每页的词框（含文本），供缩字检测用。"""
    out = subprocess.run(["pdftotext", "-bbox", str(pdf), "-"],
                         check=True, capture_output=True, text=True).stdout
    pages, words = [], []
    for line in out.splitlines():
        if "<page " in line:
            words = []
        elif line.strip().startswith("</page>"):
            pages.append(words)
        else:
            m = LINE_RE.search(line)
            if m:
                x0, y0, x1, y1 = (float(v) for v in m.groups()[:4])
                words.append((x0, y0, x1, y1, m.group(5)))
    return pages


def main() -> int:
    ap = argparse.ArgumentParser()
    # 默认值必须跟着仓库走：写死 /home/user/... 的工具在别的机器/CI 上直接跑不起来
    # （本项目真发生过：工具本地全绿、换目录就找不到模块）。
    ap.add_argument("--scripts",
                    default=str(Path(__file__).resolve().parents[1] / "scripts"))
    ap.add_argument("--out", default="")
    ap.add_argument("--widths", default="160,240,320,400,480,560,640,720")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--max-ghost-mismatch", type=int, default=2,
                    help="冒烟档允许的 ghost 不一致上限（默认 2：都是极窄栏，"
                         "真值只有 PowerPoint 能给；超了说明预览开始说谎）")
    ap.add_argument("--smoke", action="store_true",
                    help="CI 冒烟：固定 8 段 × 4 档宽，只把**危险方向**当失败"
                         "（guard 低估 = 放行会溢出的框）")
    args = ap.parse_args()
    missing = [exe for exe in ("soffice", "pdftotext") if not shutil.which(exe)]
    if missing:
        print("缺少依赖：" + "、".join(missing)
              + "（Debian/Ubuntu: apt-get install libreoffice-impress poppler-utils）",
              file=sys.stderr)
        return 2
    sys.path.insert(0, args.scripts)

    import ghost
    import primitives as P
    from compiler import compile_deck
    from verify import _text_box_capacity

    if args.smoke and args.widths == "160,240,320,400,480,560,640,720":
        # 冒烟子集：混合混排、数字+单位、长句、极窄栏各覆盖一段，宽度取
        # 极窄/窄/中/宽四档。选样标准是「曾经出过事的形状」，不是均匀抽样。
        args.widths = "160,240,400,640"
    widths = [int(x) for x in args.widths.split(",")]
    items = probes(widths)
    if args.smoke:
        keep = {"deck_s07_title", "deck_s07_body", "mix_pct", "mix_money",
                "cjk_body2", "cjk_long", "numbers", "title"}
        items = [it for it in items if it["id"].rsplit("_", 1)[0] in keep]
    spec = build_spec(items)

    work = Path(tempfile.mkdtemp(prefix="metrics-"))
    pptx = work / "probes.pptx"
    compile_deck(spec, pptx)
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
                    "--outdir", str(work), str(pptx)],
                   check=True, capture_output=True, timeout=600)
    # 每页的预期行距（PDF pt）：size(px) * 0.75 * line_height；21px 正文与 44px 标题
    # 的行距差 2.4 倍，用同一个容差会把正文两行并成一行（第一版就这样报了 office=1）。
    pitches = [it["size"] * 0.75 * 1.35 for it in items]
    pages = pdf_lines(work / "probes.pdf", pitches)
    page_flat = pdf_flat(work / "probes.pdf")
    assert len(pages) == len(items), (len(pages), len(items))

    ctx = P.RenderContext(spec["theme"], spec["canvas"])
    rows = []
    for idx, (it, page) in enumerate(zip(items, pages)):
        e = {"id": "t", "type": "text", "x": 40, "y": 40, "width": it["width"],
             "height": 640, "text": it["text"], "size": it["size"],
             "color": "ink", "line_height": 1.35}
        cap = _text_box_capacity(e, spec["theme"])
        bucket, family = ghost._font_family(e, ctx)
        font = ghost._font(it["size"], cjk=ghost._has_cjk(it["text"]),
                           family=bucket, family_name=family)
        ghost_lines = len(ghost._wrap_lines(it["text"], font, it["width"]))
        office = len(page)
        em = effective_em(page_flat[idx], it["size"])
        rows.append({**it, "guard": cap["lines"], "ghost": ghost_lines,
                     "office": office, "em": round(em, 3) if em else None,
                     # LibreOffice 溢出时缩字，行数不可比：这类探针不计入一致率，
                     # 单独报出来（真值只有 PowerPoint 能给）。
                     "shrunk": bool(em and em < 0.97),
                     "guard_ok": cap["lines"] == office and not (em and em < 0.97),
                     "ghost_ok": ghost_lines == office and not (em and em < 0.97)})

    valid = [r for r in rows if not r["shrunk"]]
    bad_g = [r for r in valid if not r["guard_ok"]]
    bad_h = [r for r in valid if not r["ghost_ok"]]
    print(f"探针 {len(rows)}（缩字排除 {len(rows)-len(valid)}）· "
          f"guard 一致 {len(valid)-len(bad_g)}/{len(valid)} · ghost 一致 {len(valid)-len(bad_h)}/{len(valid)}")
    if bad_g:
        print("\nguard ≠ 真排：")
        for r in bad_g:
            print(f"  {r['id']:20s} guard={r['guard']} office={r['office']} "
                  f"ghost={r['ghost']}  {r['text'][:20]}")
    if bad_h:
        print("\nghost ≠ 真排：")
        for r in bad_h:
            print(f"  {r['id']:20s} ghost={r['ghost']} office={r['office']} "
                  f"guard={r['guard']}  {r['text'][:20]}")
    if args.out:
        Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    if args.smoke:
        # 冒烟只认「危险」：guard 报的行数少于真排，意味着放行一个会溢出的框。
        # 高估（多报一行）只会让作者删一句能排下的话，是安全方向，不计失败。
        under = [r for r in valid if r["guard"] < r["office"]]
        print(f"\n冒烟：{len(valid)} 个有效探针 · guard 低估 {len(under)} 个"
              f" · ghost 不一致 {len(bad_h)}/{args.max_ghost_mismatch}（上限）")
        for r in under:
            print(f"  低估 {r['id']:20s} guard={r['guard']} office={r['office']}")
        for r in bad_h:
            print(f"  ghost {r['id']:20s} ghost={r['ghost']} office={r['office']}")
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        else:
            print("工作目录:", work)
        # 两条门槛：guard 低估必须为 0（放行溢出框是最坏的错）；
        # ghost 不一致是棘轮——已知的极窄栏分歧给额度，多一个就红。
        return 1 if under or len(bad_h) > args.max_ghost_mismatch else 0
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print("工作目录:", work)
    return 0 if not bad_g and not bad_h else 1


if __name__ == "__main__":
    raise SystemExit(main())
