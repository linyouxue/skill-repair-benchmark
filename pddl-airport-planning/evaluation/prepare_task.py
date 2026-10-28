"""Export exactly one frozen group; never mount the complete package to Agent."""
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
    output.mkdir(parents=True)
    shutil.copyfile(package / "task.md", output / "task.md")
    environment = output / "environment"
    environment.mkdir()
    shutil.copyfile(package / "environment/Dockerfile", environment / "Dockerfile")
    shutil.copytree(package / "environment/skills", environment / "skills")
    if package.name == "pddl-airport-planning":
        shutil.copytree(selected / "inputs/airport", environment / "airport")
        shutil.copyfile(selected / "inputs/problem.json", environment / "problem.json")
    else:
        workspace = environment / "workspace"
        workspace.mkdir()
        shutil.copytree(package / "environment/workspace/src", workspace / "src")
        shutil.copyfile(package / "environment/workspace/pom.xml", workspace / "pom.xml")
        data = workspace / "data"
        data.mkdir()
        for filename in ["format.pdf", "ClusterData2011_2.md"]:
            shutil.copyfile(package / "environment/workspace/data" / filename, data / filename)
        for kind in ["job_events", "task_events"]:
            (data / kind).mkdir()
            source = list((selected / "inputs/data" / kind).glob("*.gz"))
            if len(source) != 1:
                raise ValueError("Expected one frozen event file of each kind")
            shutil.copyfile(source[0], data / kind / "part-00001-of-00500.csv.gz")
    verifier = output / "verifier"
    verifier.mkdir()
    for filename in ["test.sh", "native_grade.py", "score_pddl.py" if package.name.startswith("pddl") else "score_flink.py"]:
        shutil.copyfile(package / "verifier" / filename, verifier / filename)
    if package.name == "flink-query":
        for filename in ["expected.json", "negative_ids.json"]:
            shutil.copyfile(selected / "verifier" / filename, verifier / filename)
    (output / "EXPORT.json").write_text(json.dumps({"task_id": package.name, "group": group,
        "data_version": "pilot-v2", "scoring_version": "item-accuracy-v1",
        "original_task_prompt_and_skills_preserved": True, "only_selected_group_in_environment": True,
        "diagnosis_oracle_and_other_groups_excluded": True,
        "deploy_verifier_only_after_agent_exit": True, "model_calls": 0}, indent=2) + "\n")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True, choices=["group_01", "group_02", "group_03"])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(prepare(args.group, args.output))
