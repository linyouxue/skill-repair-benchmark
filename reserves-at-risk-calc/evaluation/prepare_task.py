"""Export one frozen split in the existing native SkillsBench task layout."""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
YEARS = {"train": 2025, "group_01": 2025, "group_02": 2023, "group_03": 2023}
ORIGINAL_SOURCE = "download global commodity excel database from https://www.imf.org/en/research/commodity-prices,"
FROZEN_SOURCE = "open the frozen IMF commodity workbook at /root/data/gold-prices.xlsx,"


def task_prompt(year):
    prompt = (ROOT / "diagnosis/task_prompt.md").read_text(encoding="utf-8")
    if prompt.count(ORIGINAL_SOURCE) != 1:
        raise ValueError("Unexpected upstream prompt")
    return (prompt.replace(ORIGINAL_SOURCE, FROZEN_SOURCE)
            .replace("2025", str(year))
            .replace("  service: main", "  service: verifier", 1)
            .replace("build_timeout_sec: 600.0", "build_timeout_sec: 1800.0"))


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
