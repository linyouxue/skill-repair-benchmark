"""Export one frozen split in the existing native SkillsBench task layout."""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
YEARS = {"train": 2023, "group_01": 2023, "group_02": 2025, "group_03": 2025}


def task_prompt(year):
    prompt = (ROOT / "task.md").read_text(encoding="utf-8")
    return prompt.replace(str(YEARS["train"]), str(year))


def prepare(split, output):
    year = YEARS[split]
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Choose a new task directory: {output}")
    data = ROOT if split == "train" else ROOT / f"evaluation/{split}"
    source_inputs = data / ("environment" if split == "train" else "inputs")
    inputs, verifier = output / "environment", output / "verifier"
    inputs.mkdir(parents=True)
    for name in ("test-rar.xlsx", "gold-prices.xlsx"):
        shutil.copyfile(source_inputs / name, inputs / name)
    shutil.copytree(ROOT / "environment/skills", inputs / "skills")
    for name in ("Dockerfile", "Verifier.Dockerfile", "docker-compose.yaml"):
        shutil.copyfile(ROOT / "environment" / name, inputs / name)
    verifier.mkdir()
    shutil.copyfile(data / "verifier/expected_output.json", verifier / "expected_output.json")
    for name in ("test.sh", "score_accuracy.py"):
        shutil.copyfile(ROOT / "verifier" / name, verifier / name)
    (verifier / "test.sh").chmod(0o755)
    (output / "task.md").write_text(task_prompt(year), encoding="utf-8", newline="\n")
    (output / "EXPORT.json").write_text(json.dumps({
        "task_id": "reserves-at-risk-calc", "split": split, "year": year, "items": 43,
        "output": "/root/output/rar_result.xlsx",
    }, indent=2) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=YEARS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(prepare(args.split, args.output))
