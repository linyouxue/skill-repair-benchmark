#!/usr/bin/env python3
"""Use one config file to run Claude SkillsBench and CausalFlow commands."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "claude_opus47.env"


def read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SystemExit(f"配置文件不存在：{path}")
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit(f"配置行缺少等号：{raw}")
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip("\"'")
    return values


def expand_path(value: str) -> Path:
    expanded = Path(os.path.expandvars(value)).expanduser()
    return expanded.resolve() if expanded.is_absolute() else (ROOT / expanded).resolve()


def runtime_env(config_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    config = read_env_file(config_path)
    secrets = read_env_file(ROOT / ".env") if (ROOT / ".env").is_file() else {}
    env = os.environ.copy()
    env.update(secrets)
    env.update(config)
    if not env.get("OPENROUTER_API_KEY") and env.get("OPENROUTER_SECRET_KEY"):
        env["OPENROUTER_API_KEY"] = env["OPENROUTER_SECRET_KEY"]
    return env, config


def run(command: list[str], env: dict[str, str], dry_run: bool) -> int:
    print("$", shlex.join(command))
    if dry_run:
        return 0
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


def python_command(script: str, *args: str) -> list[str]:
    return [sys.executable, str(ROOT / script), *args]


def check_setup(env: dict[str, str]) -> int:
    errors: list[str] = []
    skillsbench_root = expand_path(env.get("SKILLSBENCH_ROOT", "../skillsbench"))
    checks = {
        "Python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "Docker CLI": shutil.which("docker") or "未找到",
        "SkillsBench": str(skillsbench_root),
        "模型（rollout）": env.get("BENCHMARK_MODEL", ""),
        "模型（CausalFlow）": env.get("CAUSALFLOW_MODEL", ""),
        "OpenRouter key": "已配置" if env.get("OPENROUTER_API_KEY") else "未配置",
    }
    if sys.version_info < (3, 12):
        errors.append("需要 Python 3.12 或更高版本")
    if not shutil.which("docker"):
        errors.append("未找到 docker 命令")
    else:
        probe = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode:
            errors.append("Docker daemon 不可用")
        else:
            checks["Docker Server"] = probe.stdout.strip()
    if not (skillsbench_root / "tasks").is_dir():
        errors.append(f"SkillsBench tasks 目录不存在：{skillsbench_root / 'tasks'}")
    if not env.get("OPENROUTER_API_KEY"):
        errors.append("请在 .env 中填写 OPENROUTER_API_KEY")
    if not (ROOT / "skill-repair-benchmark" / "src" / "benchmark_executor").is_dir():
        errors.append("交付包中的共享执行器源码不完整")
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if errors:
        print("\n检查未通过：")
        for item in errors:
            print(f"- {item}")
        return 2
    print("\n本地配置检查通过。此检查不会请求模型。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="离线检查路径、Docker 和 key 是否已配置")

    original = sub.add_parser("original", help="运行一条 Claude original-skill rollout")
    original.add_argument("--task-id", required=True)
    original.add_argument("--rollout-id")
    original.add_argument("--method-id")
    original.add_argument("--verifier-proxy-mode", choices=("off", "explicit"), default="off")

    prebuild = sub.add_parser("prebuild", help="预构建 CausalFlow 重放使用的任务镜像")
    prebuild.add_argument("--task-id", required=True)
    prebuild.add_argument("--image")
    prebuild.add_argument("--ensure-agent-python", action="store_true")

    audit = sub.add_parser("audit", help="双重重放共享执行器轨迹并生成审计文件")
    audit.add_argument("--task-id", required=True)
    audit.add_argument("--run-dir", type=Path, required=True)
    audit.add_argument("--image", required=True)
    audit.add_argument("--output", type=Path)

    diagnose = sub.add_parser("diagnose", help="对已有失败 rollout 运行完整 CausalFlow")
    diagnose.add_argument("--task-id", required=True)
    diagnose.add_argument("--run-dir", type=Path, required=True)
    diagnose.add_argument("--output", type=Path)
    diagnose.add_argument("--skills-dir", type=Path)
    diagnose.add_argument("--existing-image")
    diagnose.add_argument("--shared-executor-replay-audit", type=Path)
    diagnose.add_argument("--strict-replay-only", action="store_true")

    repair = sub.add_parser("repair", help="对失败轨迹运行单命令局部修复")
    repair.add_argument("--task-id", required=True)
    repair.add_argument("--run-dir", type=Path, required=True)
    repair.add_argument("--output", type=Path)
    repair.add_argument("--proposals", type=int, default=2)
    repair.add_argument("--image")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config.expanduser().resolve()
    env, config = runtime_env(config_path)
    if args.command == "check":
        return check_setup(env)

    skillsbench_root = expand_path(env.get("SKILLSBENCH_ROOT", "../skillsbench"))
    jobs_root = expand_path(env.get("BENCHMARK_JOBS_ROOT", "./runs"))
    output_root = expand_path(env.get("CAUSALFLOW_OUTPUT_ROOT", "./outputs"))
    task_dir = skillsbench_root / "tasks" / args.task_id
    if not task_dir.is_dir() and not args.dry_run:
        raise SystemExit(f"任务不存在：{task_dir}")

    if args.command == "original":
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rollout_id = args.rollout_id or f"{args.task_id}-opus47-r001-{timestamp}"
        method_id = args.method_id or config.get("METHOD_ID", "causalflow-claude-opus47")
        command = python_command(
            "repro_wrappers/run_unified_skillsbench_task.py",
            args.task_id,
            rollout_id,
            "--condition", "original-skill",
            "--method-id", method_id,
            "--stage", "original-skill",
            "--model", env.get("BENCHMARK_MODEL", "openrouter/anthropic/claude-opus-4.7"),
            "--skillsbench-root", str(skillsbench_root),
            "--jobs-root", str(jobs_root),
            "--verifier-proxy-mode", args.verifier_proxy_mode,
        )
        effort = env.get("BENCHMARK_REASONING_EFFORT", "").strip()
        if effort:
            command.extend(["--reasoning-effort", effort])
        print(f"预计运行目录：{jobs_root / method_id / rollout_id}")
        return run(command, env, args.dry_run)

    if args.command == "prebuild":
        image = args.image or f"causalflow-{args.task_id}:latest"
        command = python_command(
            "repro_wrappers/prebuild_skillsbench_task.py",
            "--task-dir", str(task_dir),
            "--tag", image,
        )
        if args.ensure_agent_python:
            command.append("--ensure-agent-python")
        return run(command, env, args.dry_run)

    run_dir = args.run_dir.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True) if not args.dry_run else None
    timeout = env.get("CAUSALFLOW_TIMEOUT", "900")

    if args.command == "audit":
        output = args.output or output_root / f"{args.task_id}-{run_dir.name}-replay-audit.json"
        command = python_command(
            "repro_wrappers/audit_shared_executor_replay.py",
            "--run-dir", str(run_dir),
            "--task-dir", str(task_dir),
            "--image", args.image,
            "--timeout", timeout,
            "--output", str(output.expanduser().resolve()),
        )
        return run(command, env, args.dry_run)

    if args.command == "diagnose":
        output = args.output or output_root / f"{args.task_id}-{run_dir.name}-causalflow.json"
        command = python_command(
            "repro_wrappers/run_skillsbench_full_causalflow.py",
            "--run-dir", str(run_dir),
            "--task-dir", str(task_dir),
            "--model", env.get("CAUSALFLOW_MODEL", "anthropic/claude-opus-4.7"),
            "--crs-interventions", env.get("CAUSALFLOW_CRS_INTERVENTIONS", "1"),
            "--repair-proposals", env.get("CAUSALFLOW_REPAIR_PROPOSALS", "3"),
            "--llm-max-tokens", env.get("CAUSALFLOW_LLM_MAX_TOKENS", "2048"),
            "--timeout", timeout,
            "--output", str(output.expanduser().resolve()),
        )
        if args.skills_dir:
            command.extend(["--skills-dir", str(args.skills_dir.expanduser().resolve())])
        if args.existing_image:
            command.extend(["--existing-image", args.existing_image])
        if args.shared_executor_replay_audit:
            command.extend([
                "--shared-executor-replay-audit",
                str(args.shared_executor_replay_audit.expanduser().resolve()),
            ])
        if args.strict_replay_only:
            command.append("--strict-replay-only")
        return run(command, env, args.dry_run)

    output = args.output or output_root / f"{args.task_id}-{run_dir.name}-local-repair.json"
    command = python_command(
        "repro_wrappers/run_skillsbench_causalflow_repair.py",
        "--run-dir", str(run_dir),
        "--task-dir", str(task_dir),
        "--repair-model", env.get("CAUSALFLOW_REPAIR_MODEL", "anthropic/claude-opus-4.7"),
        "--proposals", str(args.proposals),
        "--timeout", timeout,
        "--output", str(output.expanduser().resolve()),
    )
    if args.image:
        command.extend(["--image", args.image])
    return run(command, env, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
