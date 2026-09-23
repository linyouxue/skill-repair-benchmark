"""Prebuild an unchanged SkillsBench task environment from a temporary copy.

The optional package-index argument changes only the source used by pip during
Docker build.  It does not alter package names, pinned versions, task inputs,
skills, or verifier files, and the original task directory is never modified.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit


def inject_pip_index_arg(dockerfile_text: str) -> str:
    lines = dockerfile_text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.lstrip().upper().startswith("FROM "):
            lines.insert(index + 1, "ARG PIP_INDEX_URL\n")
            return "".join(lines)
    raise ValueError("Dockerfile has no FROM instruction")


def inject_apt_mirror_profile(dockerfile_text: str, profile: str) -> str:
    """Add a network-only Debian/Ubuntu mirror layer after the first FROM/ARG."""

    if profile == "default":
        return dockerfile_text
    if profile != "tuna":
        raise ValueError(f"unsupported apt mirror profile: {profile}")
    lines = dockerfile_text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.lstrip().upper().startswith("FROM "):
            continue
        insert_at = index + 1
        while insert_at < len(lines) and lines[insert_at].lstrip().upper().startswith(
            "ARG "
        ):
            insert_at += 1
        lines.insert(
            insert_at,
            "RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then "
            "sed -i "
            "'s|http://deb.debian.org/debian-security|http://mirrors.tuna.tsinghua.edu.cn/debian-security|g; "
            "s|http://security.debian.org/debian-security|http://mirrors.tuna.tsinghua.edu.cn/debian-security|g; "
            "s|http://deb.debian.org/debian|http://mirrors.tuna.tsinghua.edu.cn/debian|g' "
            "/etc/apt/sources.list.d/debian.sources; fi; "
            "if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then "
            "sed -i "
            "'s|http://ports.ubuntu.com/ubuntu-ports|http://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports|g; "
            "s|http://archive.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g; "
            "s|http://security.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' "
            "/etc/apt/sources.list.d/ubuntu.sources; fi\n",
        )
        return "".join(lines)
    raise ValueError("Dockerfile has no FROM instruction")


def docker_build_proxy_env() -> dict[str, str]:
    """Translate host loopback proxies into addresses visible during build."""

    forwarded: dict[str, str] = {}
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        value = os.environ.get(name) or os.environ.get(name.lower())
        if not value:
            continue
        parsed = urlsplit(value if "://" in value else f"http://{value}")
        if parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
            userinfo = ""
            if parsed.username:
                userinfo = quote(parsed.username, safe="")
                if parsed.password:
                    userinfo += ":" + quote(parsed.password, safe="")
                userinfo += "@"
            port = f":{parsed.port}" if parsed.port else ""
            value = urlunsplit(
                parsed._replace(netloc=f"{userinfo}host.docker.internal{port}")
            )
        forwarded[name] = value
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy")
    if no_proxy:
        forwarded["NO_PROXY"] = no_proxy
    return forwarded


def inject_agent_python_fallback(dockerfile_text: str) -> str:
    """Add Python only when the task image lacks the ACP runtime executable."""

    suffix = "\n" if dockerfile_text.endswith("\n") else "\n\n"
    return (
        dockerfile_text
        + suffix
        + "# CausalFlow ACP runtime only; task dependencies stay unchanged.\n"
        + "RUN if ! command -v python3 >/dev/null 2>&1; then "
        + "apt-get update && apt-get install -y --no-install-recommends "
        + "python3 ca-certificates && rm -rf /var/lib/apt/lists/*; fi\n"
    )


def inject_cached_uv_installer(
    dockerfile_text: str, staged_environment: Path, task_id: str,
) -> str:
    """Use the same pinned uv release in a temporary build context only."""

    if task_id != "fix-build-agentops":
        return dockerfile_text
    original = "RUN curl -LsSf https://astral.sh/uv/0.9.22/install.sh | sh"
    if dockerfile_text.count(original) != 1:
        raise ValueError("fix-build-agentops uv installer does not match pinned 0.9.22")
    archive = Path.home() / ".cache/benchmark-executor/uv-0.9.22-linux-x86_64.tar.gz"
    if not archive.is_file():
        raise FileNotFoundError(f"pinned build uv archive is missing: {archive}")
    staged_name = ".causalflow-uv-0.9.22.tar.gz"
    shutil.copyfile(archive, staged_environment / staged_name)
    replacement = (
        f"COPY {staged_name} /tmp/{staged_name}\n"
        "RUN mkdir -p /root/.local/bin && "
        f"tar -xzf /tmp/{staged_name} -C /root/.local/bin "
        "--strip-components=1 --no-same-owner && "
        "test \"$(/root/.local/bin/uv --version | cut -d ' ' -f 2)\" = 0.9.22 && "
        "test \"$(/root/.local/bin/uvx --version | cut -d ' ' -f 2)\" = 0.9.22 && "
        f"rm /tmp/{staged_name}"
    )
    return dockerfile_text.replace(original, replacement, 1)


def inject_apt_download_support(dockerfile_text: str, staged_environment: Path, task_id: str) -> str:
    """Preserve already downloaded packages and tolerate transient proxy drops."""
    if task_id not in {"data-to-d3", "shock-analysis-supply"}:
        return dockerfile_text
    cache = Path.home() / f".cache/benchmark-executor/apt-{task_id}"
    packages = list(cache.glob("*.deb"))
    addition = (
        "RUN printf '%s\\n' '#clear APT::Update::Post-Invoke;' "
        "'Acquire::Retries \"5\";' 'Acquire::http::Timeout \"30\";' "
        "'Acquire::https::Timeout \"30\";' 'Acquire::http::Pipeline-Depth \"0\";' "
        "> /etc/apt/apt.conf.d/zz-causalflow-downloads\n"
    )
    if packages:
        staged_cache = staged_environment / ".causalflow-apt-cache"
        staged_cache.mkdir(exist_ok=True)
        for package in packages:
            if package.is_file() and not package.is_symlink():
                shutil.copyfile(package, staged_cache / package.name)
        addition += "COPY .causalflow-apt-cache/ /var/cache/apt/archives/\n"
    lines = dockerfile_text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.lstrip().upper().startswith("FROM "):
            lines.insert(index + 1, addition)
            return "".join(lines)
    raise ValueError("Dockerfile has no FROM instruction")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument(
        "--pip-index-url",
        default="https://pypi.tuna.tsinghua.edu.cn/simple",
    )
    parser.add_argument(
        "--apt-mirror-profile",
        choices=("default", "tuna"),
        default="default",
    )
    parser.add_argument(
        "--docker-build-proxy",
        choices=("auto", "on", "off"),
        default="auto",
        help="Forward the host proxy as Docker build arguments",
    )
    parser.add_argument(
        "--ensure-agent-python",
        action="store_true",
        help="Install python3 only when absent so the CausalFlow ACP can start",
    )
    parser.add_argument("--proxy-lowercase", action="store_true",
                        help="Also pass lowercase build proxy variables for apt")
    args = parser.parse_args()

    task_dir = args.task_dir.resolve()
    environment_dir = task_dir / "environment"
    dockerfile_path = environment_dir / "Dockerfile"
    if not dockerfile_path.is_file():
        raise SystemExit(f"Dockerfile not found: {dockerfile_path}")

    parsed_index = urlsplit(args.pip_index_url)
    if (
        parsed_index.scheme != "https"
        or not parsed_index.netloc
        or parsed_index.username
        or parsed_index.password
    ):
        raise SystemExit("--pip-index-url must be a credential-free HTTPS URL")

    with tempfile.TemporaryDirectory(prefix="causalflow-prebuild-") as raw_temp:
        staged_environment = Path(raw_temp) / "environment"
        shutil.copytree(environment_dir, staged_environment)
        staged_dockerfile = staged_environment / "Dockerfile"
        dockerfile_text = inject_pip_index_arg(staged_dockerfile.read_text())
        dockerfile_text = inject_apt_mirror_profile(
            dockerfile_text, args.apt_mirror_profile
        )
        if args.ensure_agent_python:
            dockerfile_text = inject_agent_python_fallback(dockerfile_text)
        dockerfile_text = inject_cached_uv_installer(
            dockerfile_text, staged_environment, task_dir.name
        )
        dockerfile_text = inject_apt_download_support(dockerfile_text, staged_environment, task_dir.name)
        staged_dockerfile.write_text(dockerfile_text)
        env = os.environ.copy()
        env["DOCKER_BUILDKIT"] = "0"
        command = [
            "docker",
            "build",
            "--build-arg",
            f"PIP_INDEX_URL={args.pip_index_url}",
        ]
        proxy_env = docker_build_proxy_env()
        forward_proxy = args.docker_build_proxy == "on" or (
            args.docker_build_proxy == "auto" and bool(proxy_env)
        )
        if args.docker_build_proxy == "on" and not proxy_env:
            raise SystemExit(
                "--docker-build-proxy=on requested, but no host proxy exists"
            )
        if forward_proxy:
            for name, value in proxy_env.items():
                command.extend(["--build-arg", f"{name}={value}"])
                if args.proxy_lowercase:
                    command.extend(["--build-arg", f"{name.lower()}={value}"])
        command.extend(["--tag", args.tag, str(staged_environment)])
        completed = subprocess.run(
            command,
            env=env,
            check=False,
        )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
