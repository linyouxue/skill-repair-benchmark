"""Materialize one isolated SkillsBench task, without Docker builds or API calls."""
import argparse
import json
import shutil
from pathlib import Path

from score_results import GROUPS, ROOT, group_spec, load_groups


def within(path, parent):
    return path == parent or parent in path.parents


def prepare(group, output, skills=None, root=ROOT):
    root = Path(root).resolve()
    task_root = root.parent
    output = Path(output).resolve()
    reference_skills = task_root / "environment/skills"
    candidate = Path(skills).resolve() if skills is not None else reference_skills
    # Reject recursive copies before creating any output or touching a candidate.
    if output.exists() or within(output, task_root) or within(output, candidate):
        raise ValueError("Output must be a new directory outside the task and candidate Skill bundle")
    members = load_groups(root)[group]
    reference_files = {p.relative_to(reference_skills) for p in reference_skills.rglob("*") if p.is_file()}
    candidate_files = {p.relative_to(candidate) for p in candidate.rglob("*") if p.is_file()}
    if candidate_files != reference_files:
        raise ValueError("Supply the complete existing five-Skill bundle with its support files")
    editable = {p for p in reference_files if p.name == "SKILL.md"}
    if len(editable) != 5:
        raise ValueError("The reference task must contain exactly five original SKILL.md files")
    if any((candidate / p).is_symlink() for p in candidate_files):
        raise ValueError("Candidate Skill files must be ordinary local files")
    if any((candidate / p).read_bytes() != (reference_skills / p).read_bytes()
           for p in reference_files - editable):
        raise ValueError("Only the existing five SKILL.md files may differ")
    for member in members:
        if not (root / group / "images" / member["filename"]).is_file():
            raise ValueError("Frozen group image is missing")
    # Verify reference membership before producing a runnable task.
    from score_accuracy import read_oracle
    read_oracle(root / group / "stat_oracle.xlsx", group_spec(members))
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(task_root / "task.md", output / "task.md")
    environment = output / "environment"
    environment.mkdir()
    shutil.copy2(task_root / "environment/Dockerfile", environment / "Dockerfile")
    shutil.copytree(candidate, environment / "skills")
    image_dir = environment / "workspace/dataset/img"
    image_dir.mkdir(parents=True)
    for member in members:
        shutil.copy2(root / group / "images" / member["filename"], image_dir / member["filename"])
    shutil.copytree(task_root / "verifier", output / "verifier",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(root / group / "stat_oracle.xlsx", output / "verifier/stat_oracle.xlsx")
    (output / "verifier/receipt_spec.json").write_text(
        json.dumps(group_spec(members), indent=2) + "\n", encoding="utf-8")
    receipt = {"group": group, "receipts": 20, "fields": 40,
               "filenames": [m["filename"] for m in members],
               "skills_source": str(candidate), "model_calls": 0, "agent_started": False}
    (output / "preparation_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True, choices=GROUPS)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--skills", type=Path, help="Frozen complete final bundle; default is the original five Skills")
    args = parser.parse_args()
    print(prepare(args.group, args.output, args.skills))


if __name__ == "__main__":
    main()
