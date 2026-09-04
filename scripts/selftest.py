#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PPT Visual Art Director OS contract smoke tests."""
from __future__ import annotations
import importlib.util, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REFS = ROOT / "references"
SCRIPTS = ROOT / "scripts"
REQUIRED_REFS = {"design-intelligence.md", "design-system.md", "evidence-library.md", "themes.md", "production-contract.md"}
REQUIRED_SCRIPTS = {"compiler.py", "charts.py", "elements.py", "primitives.py", "guard.py", "render_check.py", "qa.py", "asset_prompt.py", "art_critic.py"}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_structure():
    missing = sorted([f for f in REQUIRED_REFS if not (REFS / f).exists()] + [f for f in REQUIRED_SCRIPTS if not (SCRIPTS / f).exists()])
    return {"status": "PASS" if not missing else "FAIL", "missing": missing}


def check_references():
    names = {p.name for p in ROOT.rglob("*") if p.is_file()}
    refs = set()
    for md in ROOT.rglob("*.md"):
        refs.update(re.findall(r"[\w./-]+\.(?:md|py)", md.read_text(encoding="utf-8")))
    missing = sorted({r.split("/")[-1] for r in refs if ".." not in r and r.split("/")[-1] not in names and r.split("/")[-1] not in {"build_mydeck.py"}})
    return {"status": "PASS" if not missing else "FAIL", "missing": missing}


def check_critic():
    mod = load("art_critic", SCRIPTS / "art_critic.py")
    spec = {"slides": [{"id": "s01", "page_intent": {"insight": "A", "focus": "title", "density": "sparse"}, "elements": [{"type": "text", "id": "title"}]}]}
    spec["slides"][0]["elements"] += [{"type": "shape", "shape": "rounded_rect", "id": f"card{i}"} for i in range(5)]
    out = mod.critique_deck(spec, {"rendered": True, "pages": [{"gravity_drift": 0.0, "accent_pixel_ratio": 0.01}]})
    required = {"critic_version", "deck_score", "status", "slides"}
    observations = " ".join(out["slides"][0]["observations"])
    ok = required <= set(out) and len(out["slides"]) == 1 and "卡片墙" in observations
    return {"status": "PASS" if ok else "FAIL", "status_value": out.get("status"), "card_wall_detected": "卡片墙" in observations}


def check_fill_contract():
    mod = load("elements", SCRIPTS / "elements.py")
    standard = mod.normalize_fill({"type": "solid", "color": "#ffffff", "opacity": 0.3})
    legacy = mod.normalize_fill({"color": "#ffffff", "opacity": 0.3})
    transparent = mod.normalize_fill({"type": "none"})
    invalid_message = ""
    try:
        mod.normalize_fill({"opacity": 0.3})
    except ValueError as exc:
        invalid_message = str(exc)
    ok = (standard["type"] == "solid" and legacy == standard and
          transparent["type"] == "none" and "Expected" in invalid_message)
    return {"status": "PASS" if ok else "FAIL", "legacy_migrated": legacy == standard, "invalid_is_explicit": bool(invalid_message)}


def check_imports():
    try:
        for name in ("primitives", "guard", "compiler", "art_critic"):
            load(name, SCRIPTS / f"{name}.py")
        return {"status": "PASS"}
    except Exception as exc:
        return {"status": "FAIL", "error": repr(exc)}


def main():
    result = {"structure": check_structure(), "references": check_references(), "imports": check_imports(), "fill_contract": check_fill_contract(), "art_critic": check_critic()}
    ok = all(v["status"] == "PASS" for v in result.values())
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("PPT Visual Art Director OS selftest")
        for k, v in result.items():
            print(f"[{k}] {v['status']}", v.get("error", v.get("missing", "")))
        print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)

if __name__ == "__main__":
    main()
