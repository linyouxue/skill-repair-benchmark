"""Export one paper-anonymizer split for BenchmarkExecutor."""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ("train", "group_01", "group_02", "group_03", "group_04")


def prepare(split, output):
    if split not in SPLITS:
        raise ValueError(f"Unknown split: {split}")
    data = ROOT if split == "train" else ROOT / "evaluation" / split
    inputs = data / ("environment" if split == "train" else "inputs")
    reference = data / "verifier" / "expected_output.json"
    spec = json.loads(reference.read_bytes())
    papers = sorted(inputs.glob("paper*.pdf"))
    if spec["split"] != split or {p.name for p in papers} != set(spec["papers"]):
        raise ValueError(f"Inputs and reference disagree for {split}")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = output / "environment"
    verifier = output / "verifier"
    environment.mkdir()
    verifier.mkdir()
    for paper in papers:
        shutil.copyfile(paper, environment / paper.name)
    shutil.copytree(ROOT / "environment/skills", environment / "skills")
    for name in ("Dockerfile", "Verifier.Dockerfile", "docker-compose.yaml"):
        shutil.copyfile(ROOT / "environment" / name, environment / name)
    shutil.copyfile(reference, verifier / reference.name)
    for name in ("score_accuracy.py", "test.sh"):
        shutil.copyfile(ROOT / "verifier" / name, verifier / name)
    (verifier / "test.sh").chmod(0o755)
    shutil.copyfile(ROOT / "task.md", output / "task.md")
    items = sum(len(p["regions"]) + 1 for p in spec["papers"].values())
    manifest = {"task_id": "paper-anonymizer", "split": split, "papers": len(papers),
                "items": items, "output": "/root/redacted"}
    (output / "EXPORT.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=SPLITS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.split, args.output))
