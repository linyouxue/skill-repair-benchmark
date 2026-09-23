"""Run a SkillsBench task with CausalFlow's lightweight ACP agent.

By default the task, Dockerfile, skill files, and verifier remain exactly as
shipped by SkillsBench. ``--skills-dir`` can replace only the deployed skill
directory for controlled skill-revision ablations. The lightweight agent avoids
JavaScript installation latency hiding the trajectory/graph integration being
evaluated.

Example:

    ../skillsbench/.venv/bin/python \
      repro_wrappers/run_skillsbench_openrouter_task.py dialogue-parser
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

try:
    from .prebuild_skillsbench_task import (
        inject_agent_python_fallback,
        inject_apt_mirror_profile,
    )
    from .run_skillsbench_openrouter_smoke import (
        DEFAULT_SKILLSBENCH_ROOT,
        OFFICIAL_SANDBOX_USER,
        REPO_ROOT,
        container_proxy_env,
        read_env_value,
        register_smoke_agent,
    )
except ImportError:  # Direct ``python repro_wrappers/<script>.py`` execution.
    from prebuild_skillsbench_task import (
        inject_agent_python_fallback,
        inject_apt_mirror_profile,
    )
    from run_skillsbench_openrouter_smoke import (
        DEFAULT_SKILLSBENCH_ROOT,
        OFFICIAL_SANDBOX_USER,
        REPO_ROOT,
        container_proxy_env,
        read_env_value,
        register_smoke_agent,
    )


SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
DOCKER_SYNTAX_RE = re.compile(r"(?m)^#\s*syntax=([^\s]+)\s*$")
PROXY_ENV_ALIASES = {
    "HTTP_PROXY": ("HTTP_PROXY", "http_proxy"),
    "HTTPS_PROXY": ("HTTPS_PROXY", "https_proxy"),
    "ALL_PROXY": ("ALL_PROXY", "all_proxy"),
    "NO_PROXY": ("NO_PROXY", "no_proxy"),
}


def resolve_task(skillsbench_root: Path, task_name: str) -> Path:
    tasks_root = (skillsbench_root / "tasks").resolve()
    task_dir = (tasks_root / task_name).resolve()
    if tasks_root not in task_dir.parents:
        raise ValueError(f"task must be below {tasks_root}: {task_name}")
    if not (task_dir / "task.md").is_file():
        raise FileNotFoundError(f"SkillsBench task not found: {task_dir}")
    return task_dir


def safe_component(value: str, label: str) -> str:
    if not SAFE_COMPONENT_RE.fullmatch(value):
        raise ValueError(
            f"{label} must contain only letters, numbers, dot, underscore, "
            f"or hyphen: {value!r}"
        )
    return value


def stage_task_with_network_proxy(
    *,
    source: Path,
    skillsbench_root: Path,
    jobs_label: str,
    proxy_env: Mapping[str, str],
    forward_build_proxy: bool,
    forward_verifier_proxy: bool,
    pip_index_url: str | None = None,
    apt_mirror_profile: str = "default",
    ensure_agent_python: bool = False,
) -> Path:
    """Copy a task and add opt-in build/verifier proxy templates.

    SkillsBench's verifier hardening intentionally starts tests with a clean
    environment.  That also removes host proxy variables, so verifiers that
    install pytest/uv can hang on otherwise healthy machines. Docker builds do
    not automatically inherit the agent environment either. The staged copy
    preserves the task prompt body, Dockerfile, skills, tests, and data
    byte-for-byte. It adds only compose build arguments and/or frontmatter
    verifier environment variables. Proxy values remain in process memory and
    are referenced through templates, so credentials are never written into
    the task copy.
    """

    import yaml

    target = (
        skillsbench_root
        / "jobs"
        / "causalflow_prepared"
        / source.name
        / jobs_label
    )
    if target.exists():
        raise FileExistsError(
            f"prepared task already exists: {target}; choose a new --jobs-label"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)

    proxy_templates: dict[str, str] = {}
    for canonical in PROXY_ENV_ALIASES:
        value = proxy_env.get(canonical)
        if not value:
            continue
        host_name = f"CAUSALFLOW_CONTAINER_{canonical}"
        os.environ[host_name] = value
        proxy_templates[canonical] = "${" + host_name + "}"

    if forward_verifier_proxy:
        task_md = target / "task.md"
        text = task_md.read_text()
        if not text.startswith("---\n"):
            raise ValueError(f"task frontmatter is missing: {task_md}")
        try:
            raw_frontmatter, body = text[4:].split("\n---\n", 1)
        except ValueError as exc:
            raise ValueError(f"task frontmatter is malformed: {task_md}") from exc
        frontmatter = yaml.safe_load(raw_frontmatter)
        if not isinstance(frontmatter, dict):
            raise ValueError(f"task frontmatter is not an object: {task_md}")
        verifier = frontmatter.setdefault("verifier", {})
        if not isinstance(verifier, dict):
            raise ValueError(f"verifier frontmatter is not an object: {task_md}")
        verifier_env = verifier.setdefault("env", {})
        if not isinstance(verifier_env, dict):
            raise ValueError(f"verifier.env is not an object: {task_md}")
        for canonical, template in proxy_templates.items():
            for alias in PROXY_ENV_ALIASES[canonical]:
                verifier_env[alias] = template
        serialized = yaml.safe_dump(
            frontmatter,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
        task_md.write_text(f"---\n{serialized}---\n{body}")

    if pip_index_url:
        dockerfile_path = target / "environment" / "Dockerfile"
        lines = dockerfile_path.read_text().splitlines(keepends=True)
        for index, line in enumerate(lines):
            if line.lstrip().upper().startswith("FROM "):
                lines.insert(index + 1, "ARG PIP_INDEX_URL\n")
                break
        else:
            raise ValueError(f"Dockerfile has no FROM instruction: {dockerfile_path}")
        dockerfile_path.write_text("".join(lines))

    if apt_mirror_profile != "default":
        dockerfile_path = target / "environment" / "Dockerfile"
        dockerfile_path.write_text(
            inject_apt_mirror_profile(
                dockerfile_path.read_text(), apt_mirror_profile
            )
        )

    if ensure_agent_python:
        dockerfile_path = target / "environment" / "Dockerfile"
        dockerfile_path.write_text(
            inject_agent_python_fallback(dockerfile_path.read_text())
        )

    if forward_build_proxy or pip_index_url:
        compose_path = target / "environment" / "docker-compose.yaml"
        compose = (
            yaml.safe_load(compose_path.read_text())
            if compose_path.exists()
            else {}
        )
        if compose is None:
            compose = {}
        if not isinstance(compose, dict):
            raise ValueError(f"compose file is not an object: {compose_path}")
        services = compose.setdefault("services", {})
        if not isinstance(services, dict):
            raise ValueError(f"compose services is not an object: {compose_path}")
        main = services.setdefault("main", {})
        if not isinstance(main, dict):
            raise ValueError(f"compose main service is not an object: {compose_path}")
        build = main.get("build")
        if build is None:
            build = {}
            main["build"] = build
        elif isinstance(build, str):
            build = {"context": build}
            main["build"] = build
        if not isinstance(build, dict):
            raise ValueError(f"compose main.build is invalid: {compose_path}")
        build_args = build.setdefault("args", {})
        if not isinstance(build_args, dict):
            raise ValueError(f"compose main.build.args is invalid: {compose_path}")
        for canonical, template in proxy_templates.items():
            for alias in PROXY_ENV_ALIASES[canonical]:
                build_args[alias] = template
        if pip_index_url:
            build_args["PIP_INDEX_URL"] = pip_index_url
        compose_path.write_text(
            yaml.safe_dump(
                compose,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
        )
    return target


def replace_staged_dockerfile_with_existing_image(
    *, task_dir: Path, image: str
) -> dict[str, str]:
    """Use an already validated local task image as the staged build base.

    This is an explicit reproducibility/performance option for reruns of the
    same SkillsBench task revision.  The task prompt, verifier, and deployed
    skills still come from the checked-out task; only the expensive environment
    build is replaced by a one-line ``FROM`` pointing at a locally inspected
    image.  The returned provenance is printed with the job logs.
    """

    if not image or any(character.isspace() for character in image):
        raise ValueError("--existing-task-image must be a non-empty image reference")
    try:
        inspected = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"cannot inspect existing task image {image!r}") from exc
    image_id = inspected.stdout.strip()
    if not image_id:
        raise RuntimeError(f"docker returned no image id for {image!r}")

    dockerfile = task_dir / "environment" / "Dockerfile"
    original = dockerfile.read_bytes()
    original_text = original.decode(errors="replace")
    workdirs = [
        line.strip()
        for line in original_text.splitlines()
        if line.lstrip().upper().startswith("WORKDIR ")
    ]
    preserved_workdir = f"{workdirs[-1]}\n" if workdirs else ""
    dockerfile.write_text(f"FROM {image}\n{preserved_workdir}")
    return {
        "reference": image,
        "image_id": image_id,
        "source_dockerfile_sha256": hashlib.sha256(original).hexdigest(),
    }


def use_preinstalled_scala_for_staged_verifier(task_dir: Path) -> None:
    """Replace only the architecture-specific Coursier bootstrap.

    ``python-scala-translation`` ships an x86-64 Coursier executable in its
    verifier.  It cannot start in an ARM64 container, even when the task image
    already contains the requested Scala 2.13.12 compiler and sbt.  This
    migration leaves the evaluator and every test unchanged; it merely uses
    pinned, preinstalled uv/Scala/sbt instead of downloading them again for
    every counterfactual branch.
    """

    verifier = task_dir / "verifier" / "test.sh"
    original = verifier.read_text()
    bootstrap = """apt-get update
apt-get install -y curl

curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh

# install scala
curl -fL https://github.com/coursier/coursier/releases/download/v2.1.25-M23/cs-x86_64-pc-linux.gz | gzip -d > cs && chmod +x cs && ./cs setup --yes

source $HOME/.local/bin/env
"""
    replacement = """# Use pinned verifier dependencies from the task image.
export PATH="/opt/scala-2.13.12/bin:/opt/sbt/bin:$PATH"
uv --version
scala -version
scalac -version
sbt --script-version
"""
    if bootstrap not in original:
        raise ValueError(
            f"expected x86-64 Coursier verifier bootstrap not found: {verifier}"
        )
    verifier.write_text(original.replace(bootstrap, replacement, 1))


def docker_frontend_is_local(reference: str) -> bool:
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", reference],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def select_docker_build_mode(requested: str, dockerfile: Path) -> str:
    if requested != "auto":
        return requested
    text = dockerfile.read_text(errors="replace")
    match = DOCKER_SYNTAX_RE.search(text)
    if not match or docker_frontend_is_local(match.group(1)):
        return "buildkit"
    unsupported_legacy = "RUN --mount=" in text or "RUN <<" in text
    return "buildkit" if unsupported_legacy else "legacy"


def write_causalflow_analyses(
    *, job_dir: Path, task_dir: Path
) -> list[Path]:
    """Convert every completed ATIF rollout in a job into a CausalFlow graph."""

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from skillsbench_replay.cli import analyze

    outputs: list[Path] = []
    for atif in sorted(job_dir.rglob("trainer/atif.json")):
        run_dir = atif.parent.parent
        try:
            payload = analyze(run_dir, task_dir)
        except Exception as exc:  # Preserve the benchmark result on analysis failure.
            print(f"causalflow_analysis_error run={run_dir} error={exc}", flush=True)
            continue
        output = run_dir / "causalflow_analysis.json"
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        outputs.append(output)
        summary = payload["summary"]
        print(
            "causalflow_analysis="
            f"{output} commands={summary['command_events']} "
            f"nodes={summary['graph_nodes']} edges={summary['graph_edges']}",
            flush=True,
        )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", default="dialogue-parser")
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
    parser.add_argument("--idle-timeout", type=int, default=300)
    parser.add_argument(
        "--agent-max-tokens",
        type=int,
        default=2_048,
        help=(
            "Maximum completion tokens for each OpenRouter agent turn. "
            "A finite cap prevents provider credit-limit rejection."
        ),
    )
    parser.add_argument(
        "--agent-max-tool-rounds",
        type=int,
        default=24,
        help="Maximum terminal-tool rounds in the lightweight ACP agent",
    )
    parser.add_argument(
        "--docker-build-mode",
        choices=("auto", "buildkit", "legacy"),
        default="auto",
        help=(
            "Docker build backend. auto uses the legacy local builder when a "
            "simple task references an unavailable BuildKit frontend image."
        ),
    )
    parser.add_argument(
        "--docker-build-proxy",
        choices=("auto", "on", "off"),
        default="auto",
        help=(
            "Forward the host proxy as Docker build arguments through a staged "
            "task copy. auto enables this when a host proxy exists."
        ),
    )
    parser.add_argument(
        "--verifier-proxy",
        choices=("auto", "on", "off"),
        default="auto",
        help=(
            "Forward the host proxy to verifier dependency downloads through "
            "a staged task copy. auto enables this when a host proxy exists."
        ),
    )
    parser.add_argument(
        "--pip-index-url",
        help=(
            "Optional HTTPS package index used only while building a staged "
            "task copy. Package names and pinned versions remain unchanged."
        ),
    )
    parser.add_argument(
        "--apt-mirror-profile",
        choices=("default", "tuna"),
        default="default",
        help="Optional network-only Debian mirror profile for the staged task copy",
    )
    parser.add_argument(
        "--with-task-skills",
        action="store_true",
        help="Deploy the task's bundled environment/skills directory",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        help=(
            "Deploy an explicit skills directory instead of the task-bundled "
            "directory. This is useful for isolated skill-revision ablations."
        ),
    )
    parser.add_argument(
        "--ensure-agent-python",
        action="store_true",
        help="Install python3 only when absent so the CausalFlow ACP can start",
    )
    parser.add_argument(
        "--existing-task-image",
        help=(
            "Use a locally validated image for this exact task revision as the "
            "staged Dockerfile base; records its immutable image ID and the "
            "source Dockerfile hash"
        ),
    )
    parser.add_argument(
        "--use-preinstalled-scala-verifier",
        action="store_true",
        help=(
            "For the Python-Scala task on ARM64, keep all official verifier "
            "tests but replace its x86-64 Coursier bootstrap with the pinned "
            "Scala/sbt toolchain already present in --existing-task-image"
        ),
    )
    args = parser.parse_args()
    if args.agent_max_tokens < 1:
        raise SystemExit("--agent-max-tokens must be positive")
    if args.agent_max_tool_rounds < 1:
        raise SystemExit("--agent-max-tool-rounds must be positive")

    skillsbench_root = args.skillsbench_root.resolve()
    safe_component(args.task, "task")
    safe_component(args.jobs_label, "jobs label")
    source_task_dir = resolve_task(skillsbench_root, args.task)
    task_dir = source_task_dir
    explicit_skills_dir = args.skills_dir.resolve() if args.skills_dir else None
    if explicit_skills_dir is not None and not explicit_skills_dir.is_dir():
        raise FileNotFoundError(f"skills directory not found: {explicit_skills_dir}")
    deploy_skills = args.with_task_skills or explicit_skills_dir is not None
    selected_skills_dir = (
        explicit_skills_dir
        if explicit_skills_dir is not None
        else source_task_dir / "environment" / "skills"
    )
    api_key = os.environ.get("OPENROUTER_API_KEY") or read_env_value(
        REPO_ROOT / ".env", "OPENROUTER_SECRET_KEY"
    )
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY/OPENROUTER_SECRET_KEY is missing")

    jobs_dir = (
        skillsbench_root / "jobs" / "causalflow_real" / args.task / args.jobs_label
    )
    proxy_env = container_proxy_env()
    forward_build_proxy = args.docker_build_proxy == "on" or (
        args.docker_build_proxy == "auto" and bool(proxy_env)
    )
    forward_verifier_proxy = args.verifier_proxy == "on" or (
        args.verifier_proxy == "auto" and bool(proxy_env)
    )
    if args.docker_build_proxy == "on" and not proxy_env:
        raise SystemExit("--docker-build-proxy=on requested, but no host proxy exists")
    if args.verifier_proxy == "on" and not proxy_env:
        raise SystemExit("--verifier-proxy=on requested, but no host proxy exists")
    if args.pip_index_url:
        parsed_index = urlsplit(args.pip_index_url)
        if (
            parsed_index.scheme != "https"
            or not parsed_index.netloc
            or parsed_index.username
            or parsed_index.password
        ):
            raise SystemExit("--pip-index-url must be a credential-free HTTPS URL")
    if (
        forward_build_proxy
        or forward_verifier_proxy
        or args.pip_index_url
        or args.apt_mirror_profile != "default"
        or args.ensure_agent_python
        or args.existing_task_image
        or args.use_preinstalled_scala_verifier
    ):
        task_dir = stage_task_with_network_proxy(
            source=source_task_dir,
            skillsbench_root=skillsbench_root,
            jobs_label=args.jobs_label,
            proxy_env=proxy_env,
            forward_build_proxy=forward_build_proxy,
            forward_verifier_proxy=forward_verifier_proxy,
            pip_index_url=args.pip_index_url,
            apt_mirror_profile=args.apt_mirror_profile,
            ensure_agent_python=args.ensure_agent_python,
        )
        print(
            f"prepared_task={task_dir} "
            f"build_proxy={'enabled' if forward_build_proxy else 'disabled'} "
            f"verifier_proxy={'enabled' if forward_verifier_proxy else 'disabled'} "
            f"pip_index={'enabled' if args.pip_index_url else 'default'} "
            f"apt_mirror={args.apt_mirror_profile}",
            flush=True,
        )
        if args.existing_task_image:
            provenance = replace_staged_dockerfile_with_existing_image(
                task_dir=task_dir,
                image=args.existing_task_image,
            )
            print(
                "existing_task_image="
                f"{provenance['reference']} image_id={provenance['image_id']} "
                "source_dockerfile_sha256="
                f"{provenance['source_dockerfile_sha256']}",
                flush=True,
            )
        if args.use_preinstalled_scala_verifier:
            if args.task != "python-scala-translation":
                raise SystemExit(
                    "--use-preinstalled-scala-verifier is limited to "
                    "python-scala-translation"
                )
            use_preinstalled_scala_for_staged_verifier(task_dir)
            print("verifier_scala_bootstrap=preinstalled_pinned_toolchain", flush=True)

    build_mode = select_docker_build_mode(
        args.docker_build_mode, task_dir / "environment" / "Dockerfile"
    )
    if build_mode == "legacy":
        os.environ["DOCKER_BUILDKIT"] = "0"
    print(f"docker_build_mode={build_mode}", flush=True)

    register_smoke_agent()
    from benchflow.evaluation import Evaluation, EvaluationConfig

    config = EvaluationConfig(
        agent="causalflow-openrouter-acp",
        model=args.model,
        environment="docker",
        concurrency=1,
        agent_env={
            "OPENROUTER_API_KEY": api_key,
            "OPENAI_API_KEY": api_key,
            "CAUSALFLOW_OPENROUTER_MAX_TOKENS": str(args.agent_max_tokens),
            "CAUSALFLOW_OPENROUTER_MAX_TOOL_ROUNDS": str(
                args.agent_max_tool_rounds
            ),
            **proxy_env,
        },
        # Match BenchFlow's official evaluation default.  Using ``root`` here
        # makes verifier hardening run ``pkill -u root`` and can terminate the
        # compose service's PID 1 before the official verifier starts.
        sandbox_user=OFFICIAL_SANDBOX_USER,
        agent_idle_timeout=args.idle_timeout,
        usage_tracking="auto",
        skills_dir=str(selected_skills_dir) if deploy_skills else None,
        skill_mode="with-skill" if deploy_skills else "no-skill",
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
    write_causalflow_analyses(
        job_dir=jobs_dir / result.job_name,
        task_dir=source_task_dir,
    )
    return 0 if result.total and result.passed == result.total else 1


if __name__ == "__main__":
    raise SystemExit(main())
