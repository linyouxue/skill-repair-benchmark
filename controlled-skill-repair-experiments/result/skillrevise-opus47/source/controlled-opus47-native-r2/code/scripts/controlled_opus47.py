"""Isolated controlled trials using the existing SkillRevise bundle/inner loops.

Operator preparation reads organizer assets. Only exported participant text and
runtime executor feedback enter the tool-free repair model. No historical Gold
trace, annotation, alternate condition, or learned cross-trial memory is loaded.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import asyncio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODEL = "tatu-anthropic/claude-opus-4-7"

def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

def write(p, value):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def runner(package):
    spec = importlib.util.spec_from_file_location("controlled_release_runner", package / "tools/runner.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def call(*argv):
    subprocess.run([str(x) for x in argv], check=True)

def verify_package(package):
    manifest = read(package / "SHA256SUMS.json")["files"]
    for name, entry in manifest.items():
        path = (package / name).resolve()
        if not path.is_relative_to(package.resolve()) or path.is_symlink():
            raise ValueError("Unsafe release path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Release content changed: " + name)
    return len(manifest)

def pin_code(work):
    paths = list((ROOT / "skillrevise").rglob("*.py")) + [Path(__file__), ROOT / "scripts/run_controlled_opus47.sh"]
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in paths if p.name != "local_llm_config.py"}
    target = work / "code_sha256.json"
    if target.exists():
        if read(target) != hashes:
            raise ValueError("Code differs from this batch; choose a fresh CONTROL_RUN_ROOT")
    else:
        write(target, hashes)
        for name in hashes:
            dest = work / "code" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, dest)

def build_images(home):
    """Dedicated image namespace: never reuse a 39-task image for a new condition."""
    from benchflow._utils.task_authoring import task_digest
    from benchflow.sandbox.docker import DockerSandbox
    from benchflow.task import Task
    def image_id(name):
        proc = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", name], capture_output=True, text=True)
        return proc.stdout.strip() if proc.returncode == 0 else None
    task_id = read(home / "manifest.json")["tasks"][0]["task_id"]
    task_dir = home / "tasks" / task_id
    digest = task_digest(task_dir)
    manifest = home / "images.json"
    if manifest.exists():
        old = read(manifest)["tasks"][task_id]
        if old["task_digest"] == digest and image_id(old["image"]) == old["image_id"]:
            print("Dedicated condition image ready:", old["image"], flush=True); return
    async def build():
        config = Task(task_dir).config.environment
        if config.docker_image and not (task_dir / "environment/Dockerfile").exists():
            call("docker", "pull", config.docker_image)
            return config.docker_image
        namespace = "controlled-" + hashlib.sha256(str(home.resolve()).encode()).hexdigest()[:16]
        sandbox = DockerSandbox(environment_dir=task_dir / "environment", environment_name=namespace,
            session_id=namespace, rollout_paths=None, task_env_config=config)
        await sandbox._run_pre_compose_hook()
        await sandbox._run_docker_compose_build()
        return sandbox._env_vars.main_image_name
    print("Building dedicated condition image (one attempt):", home.name, flush=True)
    image = asyncio.run(build())
    identity = image_id(image)
    if not identity: raise RuntimeError("Image build did not produce an inspectable image")
    write(manifest, {"schema_version": 1, "tasks": {task_id: {
        "image": image, "image_id": identity, "task_digest": digest}}})

def prepare_trial(package, work, trial_id):
    r = runner(package)
    task, trial = r.task_and_trial(package, trial_id)
    home = work / trial_id
    if (home / "state.json").exists():
        state = read(home / "state.json")
        r.validate_export(home / "input")
        if r.hashes(home / "tasks" / task["task_id"]) != state["task_hashes"]:
            raise ValueError("Prepared trial changed")
        return home
    if home.exists():
        raise ValueError("Incomplete preparation retained; choose a fresh CONTROL_RUN_ROOT: " + str(home))
    r.export_trial(package, trial_id, home / "input", "zh")
    source = r.inside(package, task["task_source"])
    target = home / "tasks" / task["task_id"]
    # Verifier/oracle belong only to the executor task tree, never repair prompts.
    r.copy_tree(source, target)
    if (target / "environment/skills").exists():
        exact = (target / "environment/skills").resolve()
        if not exact.is_relative_to(home.resolve()):
            raise ValueError("Unsafe task destination")
        shutil.rmtree(exact)
    r.copy_tree(home / "input/skills", target / "environment/skills")
    prompt = (home / "input/prompt.md").read_text(encoding="utf-8")
    hint = (home / "input/hint.txt").read_text(encoding="utf-8")
    write(home / "manifest.json", {"tasks": [{"task_id": task["task_id"],
        "family": "controlled", "instruction": prompt + "\n\nRepair-only location hint (not extra executor instructions):\n" + hint,
        "acceptance_criteria": [], "metadata": {"controlled_trial": trial_id}}]})
    write(home / "state.json", {"trial": trial, "task_hashes": r.hashes(target),
        "release_manifest_sha256": r.sha256(package / "SHA256SUMS.json"),
        "scope": "Existing SkillRevise SKILL.md-only replacement policy; attached scripts preserved unchanged",
        "hint_visible_to_repair_only": True, "shared_learned_memory": False})
    return home

def adapter(request_path, output, task_root, prebuilt):
    """REQUEST_JSON OUTPUT_DIRECTORY interface; task_root is operator-only config."""
    request_path, output = Path(request_path).resolve(), Path(output).resolve()
    source = request_path.parent
    request = read(request_path)
    if request.get("schema_version") != 1 or request.get("skills_dir") != "skills":
        raise ValueError("Unsupported participant request")
    for p in source.rglob("*"):
        if p.is_symlink(): raise ValueError("Participant symlinks prohibited")
    home = output.parent
    if source != (home / "input").resolve(): raise ValueError("Unexpected input root")
    if task_root.resolve() != (home / "tasks").resolve(): raise ValueError("Unexpected executor task root")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Candidate directory must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    # Use the real CLI composition: unchanged selector, diagnoser, principle
    # retriever/reviser, inner loop, verifier evaluation and bundle acceptance.
    import skillrevise.cli as cli
    import skillrevise.core.bundle_loop as bundle_module
    original_from_context = bundle_module._skill_from_context
    def native_markdown_skill(task, *, version):
        skill = original_from_context(task, version=version)
        skill.metadata["raw_format"] = True
        return skill
    # Official Skills use their own YAML/headings, not the synthetic template.
    # Enable the existing native-Markdown prompt/parser path only in this child.
    bundle_module._skill_from_context = native_markdown_skill
    from skillrevise.llm.client import CommandLLMClient
    from skillrevise.llm.multimodal import MultimodalPrompt
    class AuditedClient(CommandLLMClient):
        def complete(self, prompt, *, purpose):
            if isinstance(prompt, str):
                prompt = MultimodalPrompt([{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                    str(home / "requests"), {"trial_id": request["trial_id"]})
            return super().complete(prompt, purpose=purpose)
    cli.CommandLLMClient = AuditedClient
    OriginalBundleLoop = cli.BundleRepairLoop
    class SingleAttemptBundleLoop(OriginalBundleLoop):
        def __init__(self, **kwargs):
            super().__init__(**dict(kwargs, initial_evaluation_attempts=1))
    cli.BundleRepairLoop = SingleAttemptBundleLoop
    result = home / "result.json"
    argv = [str(home / "manifest.json"), "--manifest-kind", "generic",
        "--unified-tasks-root", str(task_root), "--unified-jobs-root", str(home / "jobs"),
        "--unified-candidates-root", str(home / "versions"), "--unified-model", MODEL,
        "--unified-prebuilt-images", str(prebuilt), "--unified-verifier-proxy-mode", "off",
        "--unified-method-id", "skillrevise-controlled-opus47-" + request["trial_id"],
        "--unified-skill-bundle-mode", "replace-original", "--unified-bundle-repair",
        "--unified-bundle-max-targets", "3", "--unified-bundle-accept-non-degrading",
        "--paper-protocol", "--author-mode", "template", "--diagnosis-mode", "llm",
        "--revision-mode", "llm-principle-bank", "--principle-retrieval", "bm25",
        "--max-revisions", "3", "--strict-llm", "--llm-command",
        f"{sys.executable} -m skillrevise.llm.command", "--llm-timeout", "1200",
        "--principle-bank-output", str(home / "principles_after.json"),
        "--output", str(result), "--summary-output", str(home / "summary.json")]
    write(home / "command.json", {"argv": argv, "model": MODEL,
        "repair_model": "claude-opus-4-7", "seed_memory": "fresh built-in generic seed principles per process",
        "target_file_scope": "SKILL.md only; no attached script edits"})
    sys.argv = ["skillrevise", *argv]; cli.main()
    row = read(result)["bundle_results"][0]
    selected = row.get("selected_trace") or row["initial_trace"]
    if selected.get("metadata", {}).get("reward") is None:
        raise RuntimeError("Infrastructure error; inspect result.json and jobs; not a valid repair failure")
    shutil.copytree(source / "skills", output / "skills")
    for name, text in row["selected_overrides"].items():
        dest = (output / "skills" / name).resolve()
        if not dest.is_relative_to(output / "skills") or dest.name != "SKILL.md":
            raise ValueError("Unsafe/unimplemented replacement")
        dest.write_text(text, encoding="utf-8")
    write(output / "response.json", {"trial_id": request["trial_id"],
        "selected_trace": selected, "source_result": str(result),
        "scope": "SKILL.md-only SkillRevise; non-markdown files unchanged",
        "target_repair_and_preservation_review": "pending manual review; task success alone is insufficient"})

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=["prepare", "build", "run", "status", "adapter", "gold"])
    p.add_argument("--package", type=Path, default=Path("/home/eraser/skill-repair-controlled-datasets-20261020"))
    p.add_argument("--work", type=Path, default=ROOT / "runs/controlled-opus47-20261030")
    p.add_argument("--trial", default="single-flink-query-RI-001")
    p.add_argument("--request", type=Path); p.add_argument("--output", type=Path)
    p.add_argument("--tasks-root", type=Path); p.add_argument("--prebuilt", type=Path)
    a = p.parse_args()
    if a.stage == "adapter":
        return adapter(a.request, a.output, a.tasks_root, a.prebuilt)
    verify_package(a.package)
    if a.stage != "status": pin_code(a.work)
    r = runner(a.package); catalog = r.catalog(a.package)
    ids = [x["trial_id"] for x in catalog["trials"]] if a.trial == "all" else [a.trial]
    failures = []
    summaries = []
    seen_gold = set()
    for trial_id in ids:
        if a.stage == "status":
            home = a.work / trial_id
            if (home / "result.json").exists():
                row = read(home / "result.json")["bundle_results"][0]
                initial = row["initial_trace"]
                selected = row.get("selected_trace") or initial
                summaries.append({"trial_id": trial_id,
                    "initial_reward": initial.get("metadata", {}).get("reward"),
                    "selected_reward": selected.get("metadata", {}).get("reward"),
                    "task_passed": selected.get("success"), "accepted_files": list(row.get("selected_overrides", {})),
                    "candidate_complete": (home / "candidate/response.json").exists(),
                    "target_repair_and_preservation_review": "pending manual review"})
            print(trial_id, "candidate_complete=" + str((home / "candidate/response.json").exists()),
                  "result_exists=" + str((home / "result.json").exists()), flush=True)
            continue
        if a.stage == "gold":
            task, _ = r.task_and_trial(a.package, trial_id)
            task_id = task["task_id"]
            if task_id in seen_gold: continue
            seen_gold.add(task_id)
            home = a.work / "gold_controls" / task_id
            if not (home / "manifest.json").exists():
                r.prepare_control(a.package, task_id, "full_gold", home / "prepared")
                r.copy_tree(home / "prepared/task", home / "tasks" / task_id)
                r.copy_tree(home / "prepared/skills", home / "tasks" / task_id / "environment/skills")
                write(home / "manifest.json", {"tasks": [{"task_id": task_id, "family": "controlled",
                    "instruction": (home / "prepared/task/task.md").read_text(encoding="utf-8")} ]})
            if (home / "result.json").exists():
                print("Gold control already recorded:", home, flush=True); continue
            build_images(home)
            call(sys.executable, "-m", "skillrevise.cli", home / "manifest.json", "--original-skill-only",
                 "--unified-tasks-root", home / "tasks", "--unified-jobs-root", home / "jobs",
                 "--unified-candidates-root", home / "unused-candidates", "--unified-model", MODEL,
                 "--unified-method-id", "controlled-gold-opus47", "--unified-verifier-proxy-mode", "off",
                 "--unified-prebuilt-images", home / "images.json", "--output", home / "result.json")
            continue
        home = prepare_trial(a.package, a.work, trial_id)
        image = home / "images.json"
        if a.stage == "build":
            build_images(home)
        elif a.stage == "run":
            if (home / "candidate/response.json").exists():
                print("Completed; skipping:", trial_id, flush=True); continue
            if not image.exists(): raise ValueError("Build this trial first: " + trial_id)
            if (home / "candidate").exists() and any((home / "candidate").iterdir()):
                print("Interrupted candidate retained; no automatic rerun:", home, flush=True)
                failures.append(trial_id); continue
            print("Starting isolated SkillRevise trial:", trial_id, flush=True)
            try:
                call(sys.executable, __file__, "adapter", "--request", home / "input/request.json",
                     "--output", home / "candidate", "--tasks-root", home / "tasks", "--prebuilt", image)
            except subprocess.CalledProcessError:
                failures.append(trial_id)
        else:
            print(trial_id, "candidate_complete=" + str((home / "candidate/response.json").exists()),
                  "image_manifest=" + str(image.exists()), flush=True)
    if failures:
        raise SystemExit("Incomplete trials (other trials continued): " + ", ".join(failures))
    if a.stage == "status":
        print(json.dumps(summaries, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
