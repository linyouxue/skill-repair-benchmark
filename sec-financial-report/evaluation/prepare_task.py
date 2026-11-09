"""Export one held-out batch as a native task, keeping the executor API unchanged."""
import argparse
import json
import re
from pathlib import Path
import shutil

PACKAGE = Path(__file__).resolve().parents[1]
# First frozen case in each group whose names resolve to the intended targets.
EVALUATION_CASES = {"group_01": "case_001", "group_02": "case_001", "group_03": "case_002"}


def prepare(group, output, package=PACKAGE):
    package, output = Path(package).resolve(), Path(output).resolve()
    if group not in EVALUATION_CASES:
        raise ValueError("Unknown frozen group")
    if output.exists():
        raise FileExistsError("Refusing to overwrite an export")
    selected = package / "evaluation" / group
    spec = json.loads((selected / "inputs/queries.json").read_text(encoding="utf-8"))
    previous, current = spec["baseline_period"], spec["current_period"]
    original = (package / "task.md").read_text(encoding="utf-8")
    case_id = EVALUATION_CASES[group]
    query = next(q for q in spec["queries"] if q["case_id"] == case_id)
    reference = json.loads((selected / "verifier/reference_answers.json").read_text(encoding="utf-8"))["cases"][case_id]
    manager = query["summary_manager"]["name"].strip()
    change_manager = query["change_manager"]["name"].strip()
    issuer = query["security"]["issuer"].strip()
    previous_label = f"Q{previous[-1]} {previous[:4]}"
    current_label = f"Q{current[-1]} {current[:4]}"
    replacements = {
        "q3 2025": current_label,
        "q2 2025": previous_label,
        "2025-q2": previous,
        "2025-q3": current,
        "Q2": previous_label,
        "Q3": current_label,
        "Renaissance Technologies founded by Jim Simons": manager,
        "renaissance technologies": manager,
        "Renaissance": manager,
        "Warren Buffett's Berkshire Hathaway": change_manager,
        "Berkshire Hathaway": change_manager,
        "Palantir": issuer,
    }
    prompt = re.sub("|".join(map(re.escape, replacements)), lambda match: replacements[match[0]], original)
    output.mkdir(parents=True)
    (output / "task.md").write_text(prompt, encoding="utf-8", newline="\n")
    environment = output / "environment"
    environment.mkdir()
    shutil.copytree(package / "environment/skills", environment / "skills")
    shutil.copytree(selected / "inputs/data", environment / "data")
    # Keep the original stock-name helper's fixed baseline path available.
    dockerfile = f"""FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv wget unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /root
RUN pip3 install --break-system-packages pandas==2.3.3 rapidfuzz==3.14.3
COPY data/ /root/
RUN python3 -c "import gzip,pathlib; [(p.with_suffix('').write_bytes(gzip.decompress(p.read_bytes())),p.unlink()) for p in pathlib.Path('/root').glob('20??-q?/*.tsv.gz')]"
RUN ln -s /root/{previous} /root/2025-q2
"""
    (environment / "Dockerfile").write_text(dockerfile, encoding="utf-8", newline="\n")
    verifier = output / "verifier"
    verifier.mkdir()
    for name in ["test.sh", "native_grade.py", "score_accuracy.py"]:
        shutil.copyfile(package / "verifier" / name, verifier / name)
    (verifier / "expected_output.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "EXPORT.json").write_text(json.dumps({"task_id": "sec-financial-report", "group": group,
        "dataset_version": spec["dataset_version"], "scoring_version": "sec-answer-accuracy-v1",
        "original_skill_bundle_preserved": True, "same_four_question_template": True,
        "original_output_format_preserved": True, "query_cases": 1, "answer_items": 10,
        "case_id": case_id, "baseline_period": previous, "current_period": current,
        "only_selected_group_in_environment": True, "deploy_verifier_only_after_agent_exit": True,
        "diagnosis_oracle_other_groups_excluded": True, "model_calls": 0}, indent=2) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True, choices=EVALUATION_CASES)
    parser.add_argument("--output", required=True, type=Path, help="New native task directory; name it sec-financial-report")
    args = parser.parse_args()
    print(prepare(args.group, args.output))
