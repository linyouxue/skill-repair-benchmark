"""Freeze 20-receipt execution batches; materialize only the requested inputs."""
import argparse
import json
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SIZES = {"train": 120, "validation": 40, "test": 40}
BATCH_SIZE = 20
SEED = 20261014


def split_root(split):
    return ROOT / (f"heldout/{split}" if split == "test" else f"development/{split}")


def read_batches(split):
    return json.loads((split_root(split) / "batches.json").read_text(encoding="utf-8"))["batches"]


def write_new_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def build():
    # Use filenames only: no labels, outcomes or method scores affect membership.
    plans = {}
    targets = []
    for split, size in SIZES.items():
        records = json.loads((split_root(split) / "image_manifest.json").read_text(encoding="utf-8"))
        names = sorted(row["filename"] for row in records)
        assert len(names) == size and len(set(names)) == size
        random.Random(f"{SEED}:{split}").shuffle(names)
        batches = [{"batch_id": f"batch_{number:02d}", "filenames": sorted(names[start:start+BATCH_SIZE])}
                   for number, start in enumerate(range(0, size, BATCH_SIZE), 1)]
        plans[split] = batches
        targets.append(split_root(split) / "batches.json")
        for batch in batches:
            targets.extend([ROOT / f"curator/oracles/batches/{split}/{batch['batch_id']}.json",
                            ROOT / f"grader/{split}/batches/{batch['batch_id']}/test_outputs.py",
                            ROOT / f"grader/{split}/batches/{batch['batch_id']}/test.sh"])
    if any(path.exists() for path in targets):
        raise RuntimeError("Batch files already exist; inspect current files before changing them.")
    for split, batches in plans.items():
        write_new_json(split_root(split) / "batches.json", {
            "split": split, "batch_size": BATCH_SIZE, "seed": SEED,
            "method": "filename_only_fixed_seed_shuffle_then_chunks",
            "same_skill_for_entire_round": True, "batches": batches})
        labels = {row["filename"]: row for row in json.loads((ROOT / f"curator/oracles/{split}.json").read_text(encoding="utf-8"))}
        for batch in batches:
            write_new_json(ROOT / f"curator/oracles/batches/{split}/{batch['batch_id']}.json",
                           [labels[name] for name in batch["filenames"]])
            grader = ROOT / f"grader/{split}/batches/{batch['batch_id']}"
            grader.mkdir(parents=True, exist_ok=True)
            for name in ["test_outputs.py", "test.sh"]:
                shutil.copyfile(ROOT / f"grader/{split}/{name}", grader / name)
    print(json.dumps({"batch_size": BATCH_SIZE, "batches": {split: len(rows) for split, rows in plans.items()}, "model_calls": 0}))


def materialize(split, batch_id, destination):
    matches = [row for row in read_batches(split) if row["batch_id"] == batch_id]
    if len(matches) != 1:
        raise ValueError("Unknown batch ID.")
    if destination.exists():
        raise FileExistsError("Destination already exists; refusing to overwrite it.")
    image_dir = destination / "dataset/img"
    image_dir.mkdir(parents=True)
    for name in matches[0]["filenames"]:
        shutil.copyfile(split_root(split) / "dataset/img" / name, image_dir / name)
    shutil.copyfile(ROOT / "reference_task/task.md", destination / "task.md")
    # No annotations, oracle, source mapping or other batches enter the workspace.
    print(json.dumps({"split": split, "batch_id": batch_id, "images": len(matches[0]["filenames"]), "original_task_copied": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build")
    materialize_parser = commands.add_parser("materialize")
    materialize_parser.add_argument("--split", required=True, choices=list(SIZES))
    materialize_parser.add_argument("--batch", required=True)
    materialize_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "build":
        build()
    else:
        materialize(args.split, args.batch, args.output)
