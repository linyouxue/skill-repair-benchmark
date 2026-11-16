"""Export one Flink v2 split in the native SkillsBench task layout."""
import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
SPLITS = ("repair", "scale", "stages", "combined")
EVENT_DATA = Path("environment/workspace/data")
EVENTS = ("job_events", "task_events")
GRADER_DATA = ("expected.json", "negative_ids.json", "stage_job_ids.json")


def prepare(split: str, output: Path) -> Path:
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Choose an output directory outside the task package")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(ROOT / "task.md", output / "task.md")
    shutil.copytree(ROOT / "environment", output / "environment")
    shutil.copytree(ROOT / "verifier", output / "verifier")
    if split != "repair":
        data = ROOT / "evaluation" / split
        for event in EVENTS:
            part = Path(event) / "part-00001-of-00500.csv.gz"
            shutil.copy2(data / "inputs/data" / part, output / EVENT_DATA / part)
        for name in GRADER_DATA:
            shutil.copy2(data / "verifier" / name, output / "verifier" / name)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=SPLITS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(prepare(args.split, args.output))
