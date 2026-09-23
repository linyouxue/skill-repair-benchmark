"""Run a dependency-light SkillsBench smoke through a custom OpenRouter ACP agent.

This stages the repository's hello-world sanity task on the already-cached
``python:3.11-slim`` image and replaces only its network-heavy verifier wrapper
with the same two direct checks (file exists and exact content). The derived
task is for integration diagnosis, not a reportable SkillsBench score.

Run with the SkillsBench environment:

    ../skillsbench/.venv/bin/python repro_wrappers/run_skillsbench_openrouter_smoke.py
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import os
import shlex
import shutil
import urllib.parse
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLSBENCH_ROOT = REPO_ROOT.parent / "skillsbench"
AGENT_SOURCE = REPO_ROOT / "skillsbench_replay" / "openrouter_acp_agent.py"
AGENT_PATH = "/opt/causalflow/openrouter_acp_agent.py"
AGENT_NAME = "causalflow-openrouter-acp"
OFFICIAL_SANDBOX_USER = "agent"


def read_env_value(path: Path, name: str) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip("'\"")
    return ""


def container_proxy_env() -> dict[str, str]:
    """Forward host proxies, translating loopback for Docker containers."""

    forwarded: dict[str, str] = {}
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        value = os.environ.get(name) or os.environ.get(name.lower())
        if not value:
            continue
        parsed = urllib.parse.urlsplit(
            value if "://" in value else f"http://{value}"
        )
        if parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
            userinfo = ""
            if parsed.username:
                userinfo = urllib.parse.quote(parsed.username, safe="")
                if parsed.password:
                    userinfo += ":" + urllib.parse.quote(parsed.password, safe="")
                userinfo += "@"
            port = f":{parsed.port}" if parsed.port else ""
            netloc = f"{userinfo}host.docker.internal{port}"
            value = urllib.parse.urlunsplit(parsed._replace(netloc=netloc))
        forwarded[name] = value
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy")
    if no_proxy:
        forwarded["NO_PROXY"] = no_proxy
    return forwarded


def stage_task(skillsbench_root: Path) -> Path:
    source = skillsbench_root / "experiments" / "sanity-tasks" / "hello-world"
    target = (
        skillsbench_root
        / "jobs"
        / "causalflow_smoke"
        / "prepared"
        / "hello-world-python"
    )
    expected_parent = (
        skillsbench_root / "jobs" / "causalflow_smoke" / "prepared"
    ).resolve()
    target_resolved = target.resolve()
    if expected_parent not in target_resolved.parents:
        raise RuntimeError(f"refusing to stage outside expected jobs path: {target}")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    dockerfile = target / "environment" / "Dockerfile"
    lines = dockerfile.read_text().splitlines()
    lines[0] = "FROM python:3.11-slim"
    dockerfile.write_text("\n".join(lines) + "\n")

    # Equivalent to verifier/test_state.py, without apt/curl/uv downloads.
    verifier = target / "verifier" / "test.sh"
    verifier.write_text(
        "#!/bin/sh\n"
        "mkdir -p /logs/verifier\n"
        "python3 -c 'from pathlib import Path; "
        'p=Path("/app/hello.txt"); '
        'assert p.exists(); assert p.read_text().strip() == "Hello, world!"\'\n'
        "status=$?\n"
        'if [ "$status" -eq 0 ]; then echo 1 > /logs/verifier/reward.txt; '
        "else echo 0 > /logs/verifier/reward.txt; fi\n"
        "exit 0\n"
    )
    verifier.chmod(0o755)
    return target


def register_smoke_agent() -> None:
    from benchflow.agents.registry import register_agent

    encoded = base64.b64encode(AGENT_SOURCE.read_bytes()).decode("ascii")
    install_cmd = (
        "mkdir -p /opt/causalflow && "
        f"echo {shlex.quote(encoded)} | base64 -d > {AGENT_PATH} && "
        f"chmod +x {AGENT_PATH}"
    )
    register_agent(
        name=AGENT_NAME,
        install_cmd=install_cmd,
        launch_cmd=f"python3 -u {AGENT_PATH}",
        protocol="acp",
        requires_env=["OPENROUTER_API_KEY"],
        description="Dependency-light OpenRouter terminal agent for CausalFlow smoke",
        default_model="anthropic/claude-opus-4.7",
        acp_model_format="provider/model",
        supports_acp_set_model=True,
        install_timeout=30,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skillsbench-root", type=Path, default=DEFAULT_SKILLSBENCH_ROOT
    )
    parser.add_argument(
        "--model",
        default=os.environ.get(
            "CAUSALFLOW_MODEL", "anthropic/claude-opus-4.7"
        ),
    )
    parser.add_argument(
        "--jobs-label",
        default="openrouter_acp",
        help="Jobs subdirectory; use a new label to force a fresh rollout",
    )
    parser.add_argument("--stage-only", action="store_true")
    args = parser.parse_args()

    skillsbench_root = args.skillsbench_root.resolve()
    task_dir = stage_task(skillsbench_root)
    print(f"staged task: {task_dir}", flush=True)
    if args.stage_only:
        return 0

    api_key = os.environ.get("OPENROUTER_API_KEY") or read_env_value(
        REPO_ROOT / ".env", "OPENROUTER_SECRET_KEY"
    )
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY/OPENROUTER_SECRET_KEY is missing")
    register_smoke_agent()
    jobs_dir = skillsbench_root / "jobs" / "causalflow_smoke" / args.jobs_label
    from benchflow.evaluation import Evaluation, EvaluationConfig

    # Keep credentials in memory and let BenchFlow inject them through the
    # Docker API. They never appear in argv; config.json redacts secret envs.
    config = EvaluationConfig(
        agent=AGENT_NAME,
        model=args.model,
        environment="docker",
        concurrency=1,
        agent_env={
            "OPENROUTER_API_KEY": api_key,
            # BenchFlow's native-family preflight asks for this alias when the
            # requested model contains gpt/o-series identifiers.
            "OPENAI_API_KEY": api_key,
            **container_proxy_env(),
        },
        # BenchFlow verifier hardening kills processes owned by the sandbox
        # user.  Its supported/default isolation user is the non-root
        # ``agent`` account; root would also own the compose keepalive.
        sandbox_user=OFFICIAL_SANDBOX_USER,
        agent_idle_timeout=180,
        usage_tracking="off",
    )
    result = asyncio.run(
        Evaluation(
            tasks_dir=str(task_dir),
            jobs_dir=str(jobs_dir),
            config=config,
        ).run()
    )
    print(
        f"job={result.job_name} total={result.total} passed={result.passed} "
        f"failed={result.failed} errored={result.errored}",
        flush=True,
    )
    print(f"artifacts: {jobs_dir / result.job_name}", flush=True)
    return 0 if result.total and result.passed == result.total else 1


if __name__ == "__main__":
    raise SystemExit(main())
