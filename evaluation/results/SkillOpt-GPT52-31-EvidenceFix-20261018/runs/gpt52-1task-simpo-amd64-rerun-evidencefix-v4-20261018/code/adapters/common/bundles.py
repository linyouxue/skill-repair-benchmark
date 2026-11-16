from __future__ import annotations

import difflib
import shutil
from pathlib import Path

from adapters.common.paths import original_skill_bundle


def copy_original_bundle(task_id: str, destination: Path) -> Path:
    source = original_skill_bundle(task_id)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing bundle: {destination}")
    shutil.copytree(source, destination, symlinks=False)
    return destination


def ensure_complete_skill_bundle(bundle_dir: Path) -> None:
    skill_files = sorted(bundle_dir.glob("*/SKILL.md"))
    if not skill_files:
        raise FileNotFoundError(
            f"Expected a complete SkillsBench skill bundle with */SKILL.md: {bundle_dir}"
        )


def write_bundle_diff(before_dir: Path, after_dir: Path, output_file: Path) -> None:
    before_files = {p.relative_to(before_dir) for p in before_dir.rglob("*") if p.is_file()}
    after_files = {p.relative_to(after_dir) for p in after_dir.rglob("*") if p.is_file()}
    lines: list[str] = []
    for rel_path in sorted(before_files | after_files):
        before_path = before_dir / rel_path
        after_path = after_dir / rel_path
        before_text = (
            before_path.read_text(encoding="utf-8", errors="replace").splitlines(True)
            if before_path.exists()
            else []
        )
        after_text = (
            after_path.read_text(encoding="utf-8", errors="replace").splitlines(True)
            if after_path.exists()
            else []
        )
        lines.extend(
            difflib.unified_diff(
                before_text,
                after_text,
                fromfile=f"before/{rel_path}",
                tofile=f"after/{rel_path}",
            )
        )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("".join(lines), encoding="utf-8")
