"""Convert the curated Gold repair registry into evaluator defect records, offline."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLD_ROOT = REPO_ROOT / "data" / "core25"
DEFAULT_OUTPUT = GOLD_ROOT / "gold.json"
SKILL_TAGS = {
    "skill_missing_guidance",
    "skill_incorrect_guidance",
    "skill_ambiguous_guidance",
    "skill_conflict",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def text_value(value: object, name: str) -> str:
    require(
        isinstance(value, str) and bool(value.strip()),
        f"{name} must be a nonempty string",
    )
    return value


def resolve_from(base: Path, value: object, name: str) -> Path:
    return (base / text_value(value, name)).resolve()


def relative_reference(path: Path, base: Path) -> str:
    try:
        return Path(os.path.relpath(path.resolve(), base.resolve())).as_posix()
    except ValueError:  # Trusted Original on a different Windows drive.
        return path.resolve().as_posix()


def convert_gold(
    source: list,
    bundle_map: dict,
    *,
    map_base: Path,
    output_base: Path,
    benchmark_version: str,
) -> dict:
    """Preserve each curated RI as one defect; never infer labels from a patch."""
    text_value(benchmark_version, "benchmark_version")
    require(
        isinstance(source, list) and bool(source),
        "Gold repair source must be a nonempty list",
    )
    require(
        isinstance(bundle_map, dict) and isinstance(bundle_map.get("tasks"), list),
        "Bundle map must contain a tasks list",
    )
    mapped = {}
    for row in bundle_map["tasks"]:
        require(isinstance(row, dict), "Bundle map task must be an object")
        tid = text_value(row.get("task_id"), "bundle map task_id")
        require(tid not in mapped, f"Duplicate bundle map task: {tid}")
        mapped[tid] = row
    tasks = []
    seen = set()
    for task in source:
        require(isinstance(task, dict), "Gold repair task must be an object")
        tid = text_value(task.get("id"), "source task id")
        require(tid not in seen, f"Duplicate source task: {tid}")
        require(tid in mapped, f"Missing Original bundle mapping: {tid}")
        seen.add(tid)
        mapping = mapped[tid]
        original = resolve_from(
            map_base, mapping.get("original_bundle"), "original_bundle"
        )
        require(original.is_dir(), f"Original bundle not found: {original}")
        prompts_path = resolve_from(
            map_base, mapping.get("task_prompts"), "task_prompts"
        )
        prompts = json.loads(prompts_path.read_text(encoding="utf-8-sig"))
        require(
            isinstance(prompts, list)
            and bool(prompts)
            and all(isinstance(p, str) and p.strip() for p in prompts),
            f"Original prompts must be a nonempty list of strings: {prompts_path}",
        )
        defects = []
        defect_ids = set()
        for repair_id, item in task.items():
            if repair_id == "id":
                continue
            match = re.fullmatch(r"RI-(\d+)", repair_id)
            require(match is not None, f"Unexpected source field: {tid}/{repair_id}")
            require(
                isinstance(item, dict),
                f"Repair item must be an object: {tid}/{repair_id}",
            )
            defect_id = f"D{int(match.group(1)):03d}"
            require(
                defect_id not in defect_ids,
                f"Duplicate defect identity: {tid}/{defect_id}",
            )
            defect_ids.add(defect_id)
            tag = text_value(item.get("tag"), "tag")
            require(
                tag in SKILL_TAGS,
                f"Non-Skill root cause in curated Gold: {tid}/{repair_id}: {tag}",
            )
            description = text_value(
                item.get("descrip_skill_error"), "descrip_skill_error"
            )
            requirement = text_value(item.get("gold_repair"), "gold_repair")
            source_locations = item.get("skill_location")
            require(
                isinstance(source_locations, list) and bool(source_locations),
                f"Missing skill locations: {tid}/{repair_id}",
            )
            locations = []
            for loc in source_locations:
                require(isinstance(loc, dict), "skill_location entry must be an object")
                name = text_value(loc.get("skill_file"), "skill_file").replace(
                    "\\", "/"
                )
                name = name.removeprefix("skills/")
                file_path = PurePosixPath(name)
                require(
                    not file_path.is_absolute() and ".." not in file_path.parts,
                    f"Skill location must stay within Original: {tid}/{name}",
                )
                target = (original / name).resolve()
                require(
                    target.is_relative_to(original) and target.is_file(),
                    f"Gold location missing from Original: {tid}/{name}",
                )
                locations.append(
                    {
                        "file": file_path.as_posix(),
                        "section": text_value(
                            loc.get("skill_section"), "skill_section"
                        ),
                    }
                )
            defects.append(
                {
                    "defect_id": defect_id,
                    "description": description,
                    "locations": locations,
                    "repair_requirement": requirement,
                    "source_repair_id": repair_id,
                    "root_cause": tag,
                    "source_details": deepcopy(
                        {
                            k: v
                            for k, v in item.items()
                            if k not in {"tag", "descrip_skill_error", "gold_repair"}
                        }
                    ),
                }
            )
        require(bool(defects), f"No curated repair items for task: {tid}")
        tasks.append(
            {
                "task_id": tid,
                "original_bundle": relative_reference(original, output_base),
                "task_context": "\n\n".join(prompts),
                "defects": defects,
                "source_task_prompts": relative_reference(prompts_path, output_base),
                "source_notes": deepcopy(mapping.get("notes", [])),
            }
        )
    require(
        seen == set(mapped), "Bundle map must cover exactly the curated Gold task set"
    )
    return {
        "benchmark_version": benchmark_version,
        "gold_status": "converted-draft",
        "conversion_policy": "one curated RI per defect; descriptions and requirements preserved verbatim",
        "tasks": tasks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=GOLD_ROOT / "gold_repairs.json")
    parser.add_argument(
        "--bundle-map", type=Path, default=GOLD_ROOT / "bundle_sources.json"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--benchmark-version", default="core25-gold-defects-20260909-v1"
    )
    args = parser.parse_args(argv)
    try:
        require(
            not args.output.exists(),
            "Output exists; choose a new file/version rather than overwriting Gold",
        )
        source = json.loads(args.source.read_text(encoding="utf-8-sig"))
        bundle_map = json.loads(args.bundle_map.read_text(encoding="utf-8-sig"))
        gold = convert_gold(
            source,
            bundle_map,
            map_base=args.bundle_map.resolve().parent,
            output_base=args.output.resolve().parent,
            benchmark_version=args.benchmark_version,
        )
        gold["source_registry"] = relative_reference(args.source, args.output.parent)
        gold["source_bundle_map"] = relative_reference(
            args.bundle_map, args.output.parent
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"Converted {len(gold['tasks'])} tasks / {sum(len(t['defects']) for t in gold['tasks'])} defects: {args.output}"
        )
        return 0
    except (ValueError, OSError) as exc:
        print(f"Gold conversion error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
