from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILLOPT_ROOT = ROOT / "SkillOpt"
SKILLOPT_LITE_ROOT = ROOT / "SkillOpt-Lite"
SKILLSBENCH_ROOT = ROOT / "skillsbench"


def jpg_ocr_stat_package_root() -> Path:
    """Return the installed, versioned JPG experiment package.

    The upstream JPG package intentionally lives outside the mutable
    SkillsBench checkout: it carries the diagnosis windows, field verifier,
    result contract, and later generalization fixtures in addition to the
    native task files.  An explicit override is useful when reproducing a
    pinned checkout elsewhere.
    """
    override = os.environ.get("SKILLOPT_EVA_JPG_TASK_ROOT", "").strip()
    candidates = [
        Path(override).expanduser() if override else None,
        ROOT / "eval" / "skill-repair-benchmark" / "jpg-ocr-stat",
        ROOT / "skill-repair-benchmark" / "jpg-ocr-stat",
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "diagnosis" / "index.json").is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "The JPG experiment package is not installed. Expected "
        "eval/skill-repair-benchmark/jpg-ocr-stat or SKILLOPT_EVA_JPG_TASK_ROOT."
    )


def benchmark_executor_root() -> Path:
    for name in ("skill-repair-benchmark", "skill-repair-benchmark-main"):
        candidate = ROOT / name
        if (candidate / "src" / "benchmark_executor").is_dir():
            return candidate
    raise FileNotFoundError(
        "Benchmark executor not found. Expected skill-repair-benchmark/ under "
        f"{ROOT}"
    )


def tasks_root() -> Path:
    candidate = SKILLSBENCH_ROOT / "tasks"
    if not candidate.is_dir():
        raise FileNotFoundError(f"SkillsBench tasks directory not found: {candidate}")
    return candidate


def task_dir(task_id: str) -> Path:
    if task_id == "jpg-ocr-stat":
        return jpg_ocr_stat_package_root()
    candidate = tasks_root() / task_id
    if not candidate.is_dir():
        raise FileNotFoundError(f"Unknown task_id {task_id!r}: {candidate}")
    return candidate


def original_skill_bundle(task_id: str) -> Path:
    candidate = task_dir(task_id) / "environment" / "skills"
    if not candidate.is_dir():
        raise FileNotFoundError(f"Task has no original skill bundle: {candidate}")
    return candidate


def load_task_ids(path: Path | None = None) -> list[str]:
    list_path = path or ROOT / "configs" / "core25_tasks.txt"
    items: list[str] = []
    for line in list_path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            items.append(value)
    return items
