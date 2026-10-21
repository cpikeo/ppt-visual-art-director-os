"""把仓库整理成**可分发的技能包**：只装技能运行与复核需要的东西，剥掉仓库自身的账本。

为什么要单独一步：`skill-creator` 的 `package_skill.py` 按目录原样打包，只排除
`__pycache__`/`node_modules`/`*.pyc`，**根级只有 `evals/` 会被排除**。直接拿仓库根去打，
会把 `.git/` 一起装进去——实测 8.77 MB / 109 条目里 70 条是 `.git/`，解压 9.87 MB，
而真实内容约 1.5 MB。审计流水账（CHANGELOG）、取证仪器（tools/）、冻结案例（scripts/json/）
属于**仓库资产**，不是技能运行时资产，进包只会让收件人以为它们也被调用。

用法：
    python tools/package_skill_staging.py                       # → dist/ppt-visual-art-director-os.skill
    python tools/package_skill_staging.py --skill-creator ~/skill-creator
    python tools/package_skill_staging.py --list                 # 只看会打进去什么

打包后用 `skill-creator/scripts/quick_validate.py` 复核；本脚本自己也会跑同一套校验。
"""
from __future__ import annotations

import argparse
import fnmatch
import pathlib
import re
import shutil
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 技能运行时 + 收件人复核需要的东西
INCLUDE_DIRS = ("scripts", "references", "schemas", "templates")
INCLUDE_FILES = ("SKILL.md", "README.md", "LICENSE.txt", "MAINTENANCE.md",
                 "pyproject.toml", "requirements.txt")
# 仓库账本与仪器：留在仓库里，不进包（理由见模块 docstring）
EXCLUDE_PATTERNS = (".git", ".github", "tools", "__pycache__", "*.pyc", ".DS_Store",
                    "CHANGELOG.md")
# 案例集是**证据**不是运行时资产：进包会让收件人以为技能会跑它们
EXCLUDE_RELATIVE = ("scripts/json",)


def _excluded(rel: pathlib.Path) -> bool:
    parts = rel.parts
    if any(fnmatch.fnmatch(part, pat) for part in parts for pat in EXCLUDE_PATTERNS):
        return True
    return any(rel.as_posix() == ex or rel.as_posix().startswith(ex + "/")
               for ex in EXCLUDE_RELATIVE)


def skill_name(root: pathlib.Path = ROOT) -> str:
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"^name:\s*(\S+)\s*$", text, re.M)
    if not match:
        raise SystemExit("SKILL.md 缺少 name 字段，无法确定包名")
    return match.group(1)


def collect(root: pathlib.Path = ROOT) -> list[pathlib.Path]:
    """返回相对技能根的路径列表（按目录顺序，稳定可复现）。"""
    picked: list[pathlib.Path] = []
    for name in INCLUDE_FILES:
        if (root / name).is_file():
            picked.append(pathlib.Path(name))
    for dirname in INCLUDE_DIRS:
        base = root / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(root)
                if not _excluded(rel):
                    picked.append(rel)
    return picked


def stage(files: list[pathlib.Path], root: pathlib.Path, target: pathlib.Path) -> None:
    """把文件拷进 <target>/<skill-name>/，保留相对路径。"""
    dest_root = target / skill_name(root)
    for rel in files:
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, dest)


def package(dest_root: pathlib.Path, out_dir: pathlib.Path,
            skill_creator: pathlib.Path | None) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{dest_root.name}.skill"
    if skill_creator is not None:
        sys.path.insert(0, str(skill_creator))
        try:
            from scripts.package_skill import package_skill
        except ImportError as exc:                     # 路径给了但不对
            raise SystemExit(f"无法从 {skill_creator} 导入 package_skill：{exc}")
        result = package_skill(dest_root, out_dir)
        if result is None:
            raise SystemExit("package_skill 失败（校验未通过，见上方输出）")
        return pathlib.Path(result)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(dest_root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(dest_root.parent))
    return target


def validate(dest_root: pathlib.Path, skill_creator: pathlib.Path | None) -> bool:
    if skill_creator is None:
        return True
    sys.path.insert(0, str(skill_creator))
    from scripts.quick_validate import validate_skill
    ok, message = validate_skill(dest_root)
    print(f"quick_validate: {message}")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out", default=str(ROOT / "dist"))
    parser.add_argument("--skill-creator", default=None,
                        help="skill-creator 仓库路径；给了就用它的 package_skill/quick_validate")
    parser.add_argument("--list", action="store_true", help="只列出会打进包的文件")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    files = collect(root)
    total = sum((root / rel).stat().st_size for rel in files)
    print(f"技能名: {skill_name(root)} · 文件 {len(files)} 个 · 未压缩 {total / 1e6:.2f} MB")
    if args.list:
        for rel in files:
            print(f"  {rel}")
        return 0

    skill_creator = pathlib.Path(args.skill_creator).expanduser().resolve() \
        if args.skill_creator else None
    with tempfile.TemporaryDirectory() as td:
        stage(files, root, pathlib.Path(td))
        dest_root = pathlib.Path(td) / skill_name(root)
        if not validate(dest_root, skill_creator):
            return 1
        artifact = package(dest_root, pathlib.Path(args.out).expanduser().resolve(), skill_creator)

    size = artifact.stat().st_size
    with zipfile.ZipFile(artifact) as zf:
        names = zf.namelist()
    git_entries = [n for n in names if "/.git/" in n]
    print(f"产物: {artifact} · {size / 1e6:.2f} MB · 条目 {len(names)} 个")
    if git_entries:
        print(f"⚠ 包里混入 {len(git_entries)} 个 .git 条目——staging 逻辑被破坏，不要分发")
        return 1
    print("包含（顶层）:", ", ".join(sorted({n.split('/')[1] for n in names if n.count('/') >= 1})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
