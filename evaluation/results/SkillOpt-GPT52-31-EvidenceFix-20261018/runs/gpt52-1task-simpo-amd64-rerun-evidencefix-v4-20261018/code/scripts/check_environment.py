#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.common.paths import (  # noqa: E402
    SKILLOPT_LITE_ROOT,
    SKILLOPT_ROOT,
    SKILLSBENCH_ROOT,
    benchmark_executor_root,
    load_task_ids,
    task_dir,
)

def load_project_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def expand_env_refs() -> None:
    for key, value in list(os.environ.items()):
        if value.startswith("${") and value.endswith("}"):
            ref = value[2:-1]
            os.environ[key] = os.environ.get(ref, value)


def present(value: str) -> bool:
    stripped = str(value or "").strip()
    return bool(stripped) and "<" not in stripped and not stripped.startswith("${")


def check_command(command: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
        )
    except Exception as exc:
        return False, str(exc)
    return result.returncode == 0, result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-missing-api-key", action="store_true")
    args = parser.parse_args()
    load_project_env()
    expand_env_refs()

    checks: list[tuple[str, bool, str]] = []
    checks.append(("root", ROOT.is_dir(), str(ROOT)))
    checks.append(("SkillOpt", SKILLOPT_ROOT.is_dir(), str(SKILLOPT_ROOT)))
    checks.append(("SkillOpt-Lite", SKILLOPT_LITE_ROOT.is_dir(), str(SKILLOPT_LITE_ROOT)))
    checks.append(("skillsbench", SKILLSBENCH_ROOT.is_dir(), str(SKILLSBENCH_ROOT)))
    try:
        executor = benchmark_executor_root()
        checks.append(("benchmark-executor", True, str(executor)))
    except Exception as exc:
        checks.append(("benchmark-executor", False, str(exc)))

    for command in (["python3", "--version"], ["uv", "--version"], ["git", "--version"], ["docker", "--version"]):
        ok, detail = check_command(command)
        checks.append((" ".join(command), ok, detail))

    for var in ("BENCHMARK_MODEL", "SKILLOPT_MODEL", "SKILLOPT_API_BASE", "SKILLSBENCH_ROOT", "BENCHMARK_JOBS_ROOT"):
        value = os.environ.get(var, "")
        checks.append((var, present(value), value or "missing"))

    provider = os.environ.get("MODEL_PROVIDER", "").strip().lower() or "ai360"
    checks.append(("MODEL_PROVIDER", True, provider))

    tatu_key = os.environ.get("TATU_API_KEY", "").strip()
    tatu_base = os.environ.get("TATU_BASE_URL", "").strip()
    tatu_model = os.environ.get("TATU_MODEL", "").strip() or os.environ.get("SKILLOPT_MODEL", "").strip()
    ai360_key = os.environ.get("AI360_API_KEY", "").strip() or os.environ.get("LLM_API_KEY", "").strip()
    ai360_base = os.environ.get("AI360_BASE_URL", "").strip() or os.environ.get("LLM_API_BASE", "").strip()
    ai360_model = os.environ.get("AI360_MODEL", "").strip() or os.environ.get("SKILLOPT_MODEL", "").strip()

    if provider == "tatu":
        key_ok = present(tatu_key) or args.allow_missing_api_key
        base_ok = present(tatu_base) or args.allow_missing_api_key
        model_ok = present(tatu_model) or args.allow_missing_api_key
        checks.append(("TATU_API_KEY", key_ok, "set" if present(tatu_key) else "missing; allowed for offline smoke only"))
        checks.append(("TATU_BASE_URL", base_ok, tatu_base or "missing; allowed for offline smoke only"))
        checks.append(("TATU_MODEL", model_ok, tatu_model or "missing; allowed for offline smoke only"))
    else:
        key_ok = present(ai360_key) or args.allow_missing_api_key
        base_ok = present(ai360_base) or args.allow_missing_api_key
        model_ok = present(ai360_model) or args.allow_missing_api_key
        checks.append(("AI360_API_KEY", key_ok, "set" if present(ai360_key) else "missing; allowed for offline smoke only"))
        checks.append(("AI360_BASE_URL", base_ok, ai360_base or "missing; allowed for offline smoke only"))
        checks.append(("AI360_MODEL", model_ok, ai360_model or "missing; allowed for offline smoke only"))

    missing_tasks = []
    for task_id in load_task_ids():
        try:
            task_dir(task_id)
        except FileNotFoundError:
            missing_tasks.append(task_id)
    checks.append(("core25 tasks present", not missing_tasks, ", ".join(missing_tasks) if missing_tasks else "ok"))

    width = max(len(name) for name, _, _ in checks)
    failed = False
    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        print(f"{status:4} {name:<{width}} {detail}")
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
