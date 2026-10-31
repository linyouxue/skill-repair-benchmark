"""SkillHone runner for the three published Skill Repair tasks.

Preparation and inspection are free. Only `run` can call BenchmarkExecutor;
it requires SKILLHONE_ALLOW_EXECUTION=1 and an explicit BENCHMARK_MODEL.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

TASKS = {
    "jpg-ocr-stat": {"groups": ["group_02"], "parent_iterations": 65},
    "pddl-airport-planning": {"groups": ["group_02"], "parent_iterations": 60},
    "flink-query": {"groups": ["group_01", "group_02", "group_03"], "parent_iterations": 60},
}
IGNORES = shutil.ignore_patterns("__pycache__", "*.pyc")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], encoding="utf-8", capture_output=True, check=True)
    return result.stdout.strip()


def commit_repo(root):
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    (Path(root) / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    git(root, "config", "core.autocrlf", "false")
    git(root, "add", ".")
    return git(root, "-c", "user.name=Local integration", "-c", "user.email=local@invalid",
               "commit", "-m", "Freeze integration inputs")


def files(root):
    root = Path(root)
    result = {}
    for path in root.rglob("*"):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"Symlink is not an ordinary bundle file: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path
    return result


def verify_bundle(candidate, reference):
    actual, original = files(candidate), files(reference)
    if set(actual) != set(original):
        raise ValueError("Candidate must contain the complete original bundle, with no added files")
    editable = {name for name in original if Path(name).name == "SKILL.md"}
    if not editable:
        raise ValueError("Bundle has no SKILL.md")
    for name, source in original.items():
        if name not in editable and actual[name].read_bytes() != source.read_bytes():
            raise ValueError(f"Only existing SKILL.md bodies may change: {name}")
    for name in editable:
        actual[name].read_text(encoding="utf-8")
    return len(editable)


def export_group(package, group, output):
    # Use each published exporter unchanged, in an independent process. In
    # particular, do not reconstruct graders or expose their reference values.
    subprocess.run([sys.executable, str(package / "evaluation/prepare_task.py"),
                    "--group", group, "--output", str(output)], check=True,
                   stdout=subprocess.DEVNULL)


def prepare(source, output, executor_root):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    source_commit = git(source, "rev-parse", "HEAD")
    if git(source, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Published source checkout has tracked changes")
    output.mkdir(parents=True)
    receipts = []
    for task_id, settings in TASKS.items():
        package = source / task_id
        base = output / task_id
        skill, evaluation = base / "skill", base / "eval"
        skill.mkdir(parents=True)
        evaluation.mkdir()
        shutil.copytree(package / "environment/skills", skill / "skills", ignore=IGNORES)
        # These are original TRAINING inputs and permitted historical feedback,
        # explicitly authorized by the local protocol. No evaluation, oracle,
        # verifier, held-out image or gold file is copied into the repair repo.
        training = skill / "training-context"
        training.mkdir()
        shutil.copy2(package / "task.md", training / "task.md")
        shutil.copytree(package / "environment", training / "environment",
                        ignore=shutil.ignore_patterns("skills", "__pycache__", "*.pyc"))
        shutil.copytree(package / "diagnosis", training / "diagnosis", ignore=IGNORES)
        instructions = (
            "Repair only the existing skills/**/SKILL.md bodies; preserve all support files.\n"
            "Read training-context/task.md, original inputs under training-context/environment, "
            "and every complete stream in training-context/diagnosis/index.json. "
            "These are the original training failure and permitted feedback, not held-out data. "
            "Do not truncate records or invent missing historical artifacts. "
            "No per-window API or coverage schema is required. "
            "For JPG, inspect actual original image pixels using image-capable tools; paths "
            "or base64 rendered as plain text do not prove multimodal consumption. "
            "Do not inspect evaluation repositories or hidden scoring resources.\n"
        )
        (skill / "TRAINING.md").write_text(instructions, encoding="utf-8")
        commit_repo(skill)
        seed = git(skill, "rev-parse", "HEAD")
        shutil.copytree(package / "environment/skills", evaluation / "reference_skills", ignore=IGNORES)
        probe_task = evaluation / "tasks/probe" / task_id
        probe_task.mkdir(parents=True)
        shutil.copy2(package / "task.md", probe_task / "task.md")
        for name in ("environment", "verifier"):
            shutil.copytree(package / name, probe_task / name, ignore=IGNORES)
        question = (package / "task.md").read_text(encoding="utf-8") + "\n\n" + instructions
        probe = {"question": question, "verification": "Use the original task's continuous reward.",
                 "task_dir": f"tasks/probe/{task_id}", "group": "original"}
        (evaluation / "probe.jsonl").write_text(json.dumps(probe, ensure_ascii=False) + "\n", encoding="utf-8")
        tests = []
        for group in settings["groups"]:
            target = evaluation / "tasks/test" / group / task_id
            export_group(package, group, target)
            tests.append({"question": f"Frozen {task_id} {group}; evaluate only after Skill selection.",
                          "verification": "Use the exported task's unchanged continuous reward.",
                          "task_dir": target.relative_to(evaluation).as_posix(), "group": group})
        (evaluation / "test.jsonl").write_text("".join(json.dumps(row) + "\n" for row in tests), encoding="utf-8")
        config = {"task_id": task_id, "source_commit": source_commit,
                  "seed_commit": seed, "executor_root": Path(os.path.relpath(Path(executor_root).resolve(), evaluation)).as_posix(),
                  "parent_iterations": settings["parent_iterations"], "repetitions": 1,
                  "synthetic": False, "formal_model_and_repetitions_not_yet_selected": True,
                  "test_is_final_only": True}
        write_json(evaluation / "campaign.json", config)
        shutil.copy2(__file__, evaluation / "adapter.py")
        commit_repo(evaluation)
        index = read_json(training / "diagnosis/index.json")
        receipts.append({"task_id": task_id, "source_commit": source_commit,
                         "skill_repo": str(skill), "eval_repo": str(evaluation),
                         "streams": [{"name": s["name"], "records": s["records"]} for s in index["streams"]],
                         "groups": settings["groups"], "model_calls": 0})
    write_json(output / "preparation.json", receipts)
    return receipts


def load_cases(evaluation, split):
    if split not in {"probe", "pr_val", "test"}:
        raise ValueError("Unknown SkillHone split")
    rows = [json.loads(line) for line in (evaluation / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("Split has no cases")
    for row in rows:
        path = (evaluation / row["task_dir"]).resolve()
        if not path.is_relative_to((evaluation / "tasks").resolve()):
            raise ValueError("Case must resolve inside eval/tasks")
        for name in ("task.md", "environment", "verifier"):
            if not (path / name).exists():
                raise FileNotFoundError(path / name)
    return rows


def executor_cap(executor_root):
    path = Path(executor_root) / "src/benchflow/benchmark_executor.py"
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MAX_PARENT_ITERATIONS_PER_STEP" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("Cannot read the local executor's parent-iteration cap")


def executor_location(evaluation, config):
    return (Path(evaluation) / config["executor_root"]).resolve()


def budget_ready(config, actual):
    return actual == config["parent_iterations"] or (
        actual == 60 and config.get("task_id") == "jpg-ocr-stat"
        and config["parent_iterations"] == 65
        and config.get("execution_budget_scope") == "jpg-isolated-worker-65"
    )


def activate_worker_budget(request):
    import benchflow.benchmark_executor as policy
    if request["parent_iterations"] == policy.MAX_PARENT_ITERATIONS_PER_STEP:
        return
    if not budget_ready(request, policy.MAX_PARENT_ITERATIONS_PER_STEP) or Path(request["task_dir"]).name != "jpg-ocr-stat":
        raise ValueError("Loaded executor budget differs from the task's required budget")
    # This is a separately spawned JPG worker. The shared source and every
    # PDDL/Flink process retain their canonical default of 60.
    from benchflow.acp import runtime
    policy.MAX_PARENT_ITERATIONS_PER_STEP = 65
    runtime.MAX_PARENT_ITERATIONS_PER_STEP = 65
    from benchmark_executor import result as result_contract
    result_contract.MAX_PARENT_ITERATIONS_PER_STEP = 65


def check(evaluation, skill):
    evaluation, skill = Path(evaluation).resolve(), Path(skill).resolve()
    config = read_json(evaluation / "campaign.json")
    count = verify_bundle(skill / "skills", evaluation / "reference_skills")
    # The optimizer may edit Skill bodies, but it must not rewrite the provided
    # training evidence or use files outside the permitted existing bundle.
    changed = git(skill, "diff", "--name-only", config["seed_commit"], "--")
    permitted = {"skills/" + name for name in files(evaluation / "reference_skills") if Path(name).name == "SKILL.md"}
    if any(name not in permitted for name in changed.splitlines()):
        raise ValueError("Candidate changed files outside the existing Skill bodies")
    if git(skill, "ls-files", "--others", "--exclude-standard"):
        raise ValueError("Candidate has untracked files")
    cases = {s: len(load_cases(evaluation, s)) for s in ("probe", "test") if (evaluation / f"{s}.jsonl").is_file()}
    actual = executor_cap(executor_location(evaluation, config))
    return {"task_id": config["task_id"], "skill_count": count, "cases": cases,
            "expected_parent_iterations": config["parent_iterations"], "executor_parent_iterations": actual,
            "execution_budget_ready": budget_ready(config, actual),
            "execution_budget_scope": config.get("execution_budget_scope", "shared-default"),
            "model_calls": 0, "training_context_present": (skill / "training-context").is_dir()}


def worker(request_file, response_file):
    request = read_json(request_file)
    root = Path(request["executor_root"]).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root / "src"))
    activate_worker_budget(request)
    if request.get("execution_budget_scope") == "jpg-isolated-worker-65":
        from jpg_runtime_20261030 import setup_worker
        setup_worker()
    from benchmark_executor import BenchmarkExecutor
    from benchflow.benchmark_executor import MAX_PARENT_ITERATIONS_PER_STEP
    if MAX_PARENT_ITERATIONS_PER_STEP != request["parent_iterations"]:
        raise ValueError("Loaded executor budget differs from the task's required budget")
    task = Path(request["task_dir"])
    executor = BenchmarkExecutor(tasks_root=task.parent, jobs_root=request["jobs_root"],
                                 model=request["model"], reasoning_effort=request["reasoning_effort"],
                                 protocol="skillrepair-v1")
    result = executor.run(task_id=task.name, condition="method-skill",
                          skill_bundle=request["skill_bundle"], method_id="skillhone",
                          stage=request["stage"], rollout_id=request["rollout_id"])
    reward = result.reward
    if not result.execution_ok or reward is None:
        raise RuntimeError(f"Executor did not produce a valid scored rollout: {result.artifacts.result_json}")
    if isinstance(reward, bool) or not math.isfinite(reward) or not 0 <= reward <= 1:
        raise ValueError("Invalid native reward")
    write_json(response_file, {"reward": reward, "passed": result.task_passed is True,
               "result_json": str(result.artifacts.result_json),
               "agent_iterations": result.agent_iterations,
               "n_skill_invocations": result.skill_exposure.native_skill_invocations,
               "skill_preload_verified": result.skill_exposure.verified,
               "execution_budget_scope": request.get("execution_budget_scope", "shared-default"),
               "parent_iterations": request["parent_iterations"],
               "cost_usd": result.cost_usd})


def run(evaluation, skill, split, output):
    evaluation, skill, output = Path(evaluation).resolve(), Path(skill).resolve(), Path(output).resolve()
    if os.environ.get("SKILLHONE_ALLOW_EXECUTION") != "1":
        raise RuntimeError("Execution disabled. Preparation/checks do not authorize paid rollouts; set SKILLHONE_ALLOW_EXECUTION=1 only for an authorized run.")
    model = os.environ.get("BENCHMARK_MODEL")
    if not model:
        raise ValueError("Select an explicit BENCHMARK_MODEL; no provider/model default is assumed")
    report = check(evaluation, skill)
    if not report["execution_budget_ready"]:
        raise ValueError(f"Budget mismatch: task requires {report['expected_parent_iterations']}, local executor has {report['executor_parent_iterations']}")
    config = read_json(evaluation / "campaign.json")
    if split not in config.get("allowed_splits", ["probe", "pr_val", "test"]):
        raise ValueError("Split is outside this campaign's authorized scope")
    executor_root = executor_location(evaluation, config)
    repetitions = config["repetitions"]
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("Repetitions must be a positive integer")
    if output.exists():
        raise FileExistsError(output)
    cache = None
    if config.get("reuse_probe_results") and split == "probe":
        if config["task_id"] != "jpg-ocr-stat" or config.get("execution_budget_scope") != "jpg-isolated-worker-65":
            raise ValueError("Probe reuse is restricted to the authorized JPG campaign")
        cache = Path(config["probe_cache_dir"]) / (git(skill, "rev-parse", "HEAD") + ".json")
        if cache.exists():
            saved = read_json(cache)
            if saved.get("executed_model") != model or saved.get("parent_iterations") != 65:
                raise ValueError("Cached probe model or budget differs")
            for trace in saved["traces"]:
                source = Path(trace["result_json"])
                if not source.is_file() or not (source.parent / "artifacts/pre-verifier-workspace.tar.gz").is_file():
                    raise ValueError("Cached probe has lost its actual scored artifacts")
            reused = dict(saved, reused_probe_from=str(cache), new_model_calls_by_reuse=0)
            write_json(output, reused)
            return {key: reused[key] for key in ("task_id", "split", "score", "n_total", "synthetic_contract_check")}
    work = output.parent / (output.stem + "-rollouts")
    work.mkdir(parents=True, exist_ok=False)
    results = []
    for ordinal, case in enumerate(load_cases(evaluation, split)):
        for repeat in range(repetitions):
            identity = f"{config['task_id']}-{split}-{ordinal}-{repeat}-{uuid.uuid4().hex[:10]}"
            request = {"executor_root": str(executor_root), "task_dir": str((evaluation / case["task_dir"]).resolve()),
                       "task_id": config["task_id"],
                       "execution_budget_scope": config.get("execution_budget_scope", "shared-default"),
                       "jobs_root": str(work / "jobs"), "model": model,
                       "reasoning_effort": os.environ.get("BENCHMARK_REASONING_EFFORT"),
                       "parent_iterations": config["parent_iterations"], "skill_bundle": str(skill / "skills"),
                       "stage": f"{split}-{case['group']}-repeat-{repeat+1}", "rollout_id": identity}
            request_file, response_file = work / f"{identity}.request.json", work / f"{identity}.response.json"
            write_json(request_file, request)
            # Every rollout has a separate process and a stable explicit cwd.
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "_worker", str(request_file), str(response_file)],
                           cwd=executor_root, check=True)
            result = read_json(response_file)
            result.update(group=case["group"], repeat=repeat+1,
                          category="passed" if result["passed"] else "wrong-answer")
            results.append(result)
    result = {"score": sum(r["reward"] for r in results) / len(results),
              "n_total": len(results), "n_passed": sum(r["passed"] for r in results),
              "traces": results, "task_id": config["task_id"], "split": split,
              "synthetic_contract_check": config["synthetic"],
              "metric": "mean_native_continuous_reward", "source_commit": config["source_commit"]}
    result.update(executed_model=model, parent_iterations=config["parent_iterations"])
    write_json(output, result)
    if cache is not None:
        write_json(cache, result)
    return {key: result[key] for key in ("task_id", "split", "score", "n_total", "synthetic_contract_check")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    for name in ("source", "output", "executor-root"):
        prepare_parser.add_argument("--" + name, required=True, type=Path)
    for command in ("check", "run"):
        sub = commands.add_parser(command)
        sub.add_argument("--eval", type=Path, default=Path.cwd())
        sub.add_argument("--skill", type=Path, required=True)
        if command == "run":
            sub.add_argument("--split", required=True, choices=["probe", "pr_val", "test"])
            sub.add_argument("--output", required=True, type=Path)
    sub = commands.add_parser("_worker")
    sub.add_argument("request")
    sub.add_argument("response")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.source, args.output, args.executor_root)
    elif args.command == "check":
        result = check(args.eval, args.skill)
    elif args.command == "run":
        result = run(args.eval, args.skill, args.split, args.output)
    else:
        worker(args.request, args.response)
        return
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
