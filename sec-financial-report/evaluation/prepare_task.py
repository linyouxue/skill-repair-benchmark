"""Export one held-out batch as a native task, keeping the executor API unchanged."""
import argparse
import json
from pathlib import Path
import shutil

PACKAGE = Path(__file__).resolve().parents[1]


def prepare(group, output, package=PACKAGE):
    package, output = Path(package).resolve(), Path(output).resolve()
    if group not in {"group_01", "group_02", "group_03"}:
        raise ValueError("Unknown frozen group")
    if output.exists():
        raise FileExistsError("Refusing to overwrite an export")
    selected = package / "evaluation" / group
    spec = json.loads((selected / "inputs/queries.json").read_text(encoding="utf-8"))
    previous, current = spec["baseline_period"], spec["current_period"]
    original = (package / "task.md").read_text(encoding="utf-8")
    frontmatter = original[:original.index("\n---", 4) + 4]
    prompt = f"""

Analyze the supplied SEC Form 13F data, comparing {previous} with {current}.
The tables are in `/root/{previous}` and `/root/{current}`. Read `/root/queries.json`
for the 20 independent query cases. Every case uses the same four questions:

1. Sum the current-quarter reported holdings VALUE (AUM under the original task's convention)
   for `summary_manager`.
2. Count its current-quarter stock holding rows, following the original
   `13f-analyzer` helper's evaluated TITLEOFCLASS selection and aggregation semantics.
   Do not silently broaden its stock universe or count distinct CUSIPs instead of rows.
3. For `change_manager`, return the five stock CUSIPs with the largest positive
   current-minus-baseline VALUE increases, in descending order. Aggregate by CUSIP
   after the same original stock selection; an absent CUSIP has value zero.
4. For `security`, return the three current-quarter fund manager names with the
   largest summed VALUE in that CUSIP, in descending order. Use all matching rows,
   with no stock-title or PUTCALL filter for this question.

Use the supplied CIKs and CUSIPs to disambiguate identities, preserving leading zeros.
The input cohort and full statistical conventions are described in
`/root/statistical_contract.json`. Dates in the ZIP publication window are different
from report quarters; the exported input already contains the declared report cohort.
Managers and securities can repeat across data rows; do not deduplicate positions.
VALUE is integer USD; do not multiply by 1000. The selected top rankings have no ties.

Write `/root/answers.json` as one JSON object keyed by the 20 `case_id` values.
For each case provide the original four-key answer object:

```json
{{
  "case_001": {{
    "q1_answer": 0,
    "q2_answer": 0,
    "q3_answer": ["cusip1", "cusip2", "cusip3", "cusip4", "cusip5"],
    "q4_answer": ["manager1", "manager2", "manager3"]
  }}
}}
```

The values above are schema placeholders. Include every supplied case. Scoring uses
ten answer slots per case: q1, q2, five ordered q3 slots, and three ordered q4 slots.
The original q1 rule accepts relative error strictly below 0.1%; q2 and CUSIPs must
match exactly, and manager names are case-insensitive with rank/order preserved.
Missing or invalid slots are wrong. Extra ranked entries and unknown case IDs count
as extra errors. Runtime is subject to the task timeout and is not a weighted score.
"""
    output.mkdir(parents=True)
    (output / "task.md").write_text(frontmatter + prompt, encoding="utf-8", newline="\n")
    environment = output / "environment"
    environment.mkdir()
    shutil.copytree(package / "environment/skills", environment / "skills")
    shutil.copytree(selected / "inputs/data", environment / "data")
    shutil.copyfile(selected / "inputs/queries.json", environment / "queries.json")
    shutil.copyfile(package / "environment/statistical_contract.json", environment / "statistical_contract.json")
    dockerfile = f"""FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv wget unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /root
RUN pip3 install --break-system-packages pandas==2.3.3 rapidfuzz==3.14.3
COPY data/ /root/
COPY queries.json statistical_contract.json /root/
RUN python3 -c "import gzip,pathlib; [(p.with_suffix('').write_bytes(gzip.decompress(p.read_bytes())),p.unlink()) for p in pathlib.Path('/root').glob('20??-q?/*.tsv.gz')]"
"""
    (environment / "Dockerfile").write_text(dockerfile, encoding="utf-8", newline="\n")
    verifier = output / "verifier"
    verifier.mkdir()
    for name in ["test.sh", "native_grade.py", "score_accuracy.py"]:
        shutil.copyfile(package / "verifier" / name, verifier / name)
    shutil.copyfile(selected / "verifier/reference_answers.json", verifier / "expected_output.json")
    (output / "EXPORT.json").write_text(json.dumps({"task_id": "sec-financial-report", "group": group,
        "dataset_version": spec["dataset_version"], "scoring_version": "sec-answer-accuracy-v1",
        "original_skill_bundle_preserved": True, "same_four_question_template": True,
        "original_prompt_byte_identical": False, "query_cases": len(spec["queries"]),
        "only_selected_group_in_environment": True, "deploy_verifier_only_after_agent_exit": True,
        "diagnosis_oracle_other_groups_excluded": True, "model_calls": 0}, indent=2) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True, choices=["group_01", "group_02", "group_03"])
    parser.add_argument("--output", required=True, type=Path, help="New native task directory; name it sec-financial-report")
    args = parser.parse_args()
    print(prepare(args.group, args.output))
