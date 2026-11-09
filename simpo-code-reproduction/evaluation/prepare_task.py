"""Export one frozen SimPO group as a native SkillsBench task."""

import argparse
import shutil
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
GROUPS = ("group_01", "group_02", "group_03")
TENSOR_PATH = Path("environment/SimPO/unit_test/tensors")
TENSOR_FILES = ("policy_chosen_logps.pt", "policy_rejected_logps.pt")


def prepare(group: str, output: Path) -> Path:
    if group not in GROUPS:
        raise ValueError(f"Unknown frozen group: {group}")
    selected = PACKAGE / "evaluation" / group
    inputs = selected / "inputs"
    reference = selected / "verifier/loss.npz"
    for file in (*[inputs / name for name in TENSOR_FILES], reference):
        if not file.is_file():
            raise FileNotFoundError(file)
    output = output.resolve()
    if output.is_relative_to(PACKAGE):
        raise ValueError("Export to a new directory outside the task package")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(PACKAGE / "task.md", output / "task.md")
    shutil.copytree(PACKAGE / "environment", output / "environment")
    shutil.copytree(PACKAGE / "verifier", output / "verifier")
    for name in TENSOR_FILES:
        shutil.copyfile(inputs / name, output / TENSOR_PATH / name)
    shutil.copyfile(reference, output / "verifier/loss.npz")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=GROUPS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.group, args.output))
