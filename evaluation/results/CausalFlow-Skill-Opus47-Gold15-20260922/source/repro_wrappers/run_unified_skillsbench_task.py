#!/usr/bin/env python3
"""Run one SkillsBench task through the shared skillrepair-v1 executor.

The wrapper exposes experiment identity and, for the ``method-skill``
condition, a complete external skill bundle.  Agent, sandbox, iteration
limits, timeouts, verifier handling, and evidence export remain owned by
BenchmarkExecutor.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SHARED_EXECUTOR_SRC = WORKSPACE_ROOT / "skill-repair-benchmark" / "src"
if str(SHARED_EXECUTOR_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_EXECUTOR_SRC))

from benchmark_executor import BenchmarkExecutor  # noqa: E402


def docker_install_proxy_url(value: str) -> str | None:
    """Translate a credential-free host-loopback HTTP proxy for Docker Desktop."""

    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return urlunsplit(
        (
            parsed.scheme,
            f"host.docker.internal:{parsed.port}",
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def configure_docker_install_proxy() -> bool:
    """Bridge SoCloud's loopback proxy only into the one-shot agent installer."""

    candidates = (
        os.environ.get("HTTPS_PROXY", ""),
        os.environ.get("https_proxy", ""),
        os.environ.get("HTTP_PROXY", ""),
        os.environ.get("http_proxy", ""),
    )
    proxy = next(
        (translated for raw in candidates if (translated := docker_install_proxy_url(raw))),
        None,
    )
    if proxy is None:
        return False

    from benchflow.agents.registry import AGENT_INSTALLERS

    original = AGENT_INSTALLERS["openhands"]
    marker = "BENCHFLOW_DOCKER_INSTALL_PROXY_ACTIVE"
    if marker in original:
        return True
    quoted = shlex.quote(proxy)
    AGENT_INSTALLERS["openhands"] = (
        f"export {marker}=1 HTTP_PROXY={quoted} HTTPS_PROXY={quoted} "
        f"http_proxy={quoted} https_proxy={quoted}; "
        f"unset ALL_PROXY all_proxy; {original}"
    )
    return True


def configure_verifier_proxy(mode: str) -> bool:
    """Expose the host HTTP proxy only to the final verifier process."""

    if mode != "explicit":
        return False
    candidates = (
        os.environ.get("HTTPS_PROXY", ""),
        os.environ.get("https_proxy", ""),
        os.environ.get("HTTP_PROXY", ""),
        os.environ.get("http_proxy", ""),
    )
    proxy = next(
        (translated for raw in candidates if (translated := docker_install_proxy_url(raw))),
        None,
    )
    if proxy is None:
        raise RuntimeError(
            "explicit verifier proxy requested, but no Docker-reachable host "
            "HTTP(S) proxy could be derived"
        )
    os.environ["BENCHMARK_EXECUTOR_VERIFIER_HTTP_PROXY"] = proxy
    os.environ["BENCHMARK_EXECUTOR_VERIFIER_HTTPS_PROXY"] = proxy
    os.environ["BENCHMARK_EXECUTOR_VERIFIER_NO_PROXY"] = (
        "localhost,127.0.0.1,::1,host.docker.internal,main"
    )
    return True


def normalize_host_environment() -> None:
    """Remove unrelated host variables known to break the pinned proxy CLI."""

    # The surrounding CausalFlow project historically stores the OpenRouter
    # credential as OPENROUTER_SECRET_KEY, while the shared executor requires
    # OPENROUTER_API_KEY. Load the project file and bridge the two names without
    # printing or persisting the credential anywhere else.
    load_dotenv(WORKSPACE_ROOT / ".env")
    if not os.environ.get("OPENROUTER_API_KEY"):
        legacy_key = os.environ.get("OPENROUTER_SECRET_KEY", "").strip()
        if legacy_key:
            os.environ["OPENROUTER_API_KEY"] = legacy_key

    # LiteLLM's Click option parser treats a generic DEBUG value as the value
    # of its boolean --debug flag.  Codex exports DEBUG=release, which makes the
    # proxy exit before the first provider request.
    os.environ.pop("DEBUG", None)

    # The managed Mac exports both HTTP(S) proxies and a SOCKS ALL_PROXY.  The
    # locked LiteLLM environment has no socksio extra, so prefer HTTP(S) here.
    for name in ("ALL_PROXY", "all_proxy"):
        if os.environ.get(name, "").lower().startswith(
            ("socks4://", "socks4a://", "socks5://", "socks5h://")
        ):
            os.environ.pop(name, None)

    # LiteLLM normally fetches its model-price map during import.  That lookup
    # is unrelated to task execution and can stall proxy startup behind the
    # managed host's mixed HTTP/SOCKS proxy configuration.  The locked LiteLLM
    # wheel ships the corresponding map, so force the deterministic local copy.
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("rollout_id")
    parser.add_argument("--condition", default="original-skill")
    parser.add_argument("--method-id", default="executor-audit")
    parser.add_argument("--stage", default="original-skill-rerun")
    parser.add_argument(
        "--skill-bundle",
        type=Path,
        help=(
            "complete model-visible skill directory; required for "
            "--condition method-skill and rejected for other conditions"
        ),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get(
            "BENCHMARK_MODEL", "openrouter/anthropic/claude-opus-4.7"
        ),
    )
    parser.add_argument(
        "--reasoning-effort",
        default=os.environ.get("BENCHMARK_REASONING_EFFORT", ""),
    )
    parser.add_argument(
        "--skillsbench-root",
        type=Path,
        default=Path(
            os.environ.get(
                "SKILLSBENCH_ROOT",
                str(WORKSPACE_ROOT.parent / "skillsbench"),
            )
        ),
    )
    parser.add_argument(
        "--jobs-root",
        type=Path,
        default=Path(
            os.environ.get(
                "BENCHMARK_JOBS_ROOT",
                str(WORKSPACE_ROOT / "runs"),
            )
        ),
    )
    parser.add_argument(
        "--verifier-proxy-mode",
        choices=("off", "explicit"),
        default="off",
        help="opt in to a verifier-only Docker bridge proxy",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    normalize_host_environment()
    configure_docker_install_proxy()
    configure_verifier_proxy(args.verifier_proxy_mode)
    reasoning_effort = args.reasoning_effort.strip() or None
    executor = BenchmarkExecutor(
        tasks_root=args.skillsbench_root / "tasks",
        jobs_root=args.jobs_root,
        model=args.model,
        reasoning_effort=reasoning_effort,
        protocol="skillrepair-v1",
        verifier_proxy_mode=args.verifier_proxy_mode,
    )
    result = executor.run(
        task_id=args.task_id,
        condition=args.condition,
        method_id=args.method_id,
        stage=args.stage,
        rollout_id=args.rollout_id,
        skill_bundle=args.skill_bundle,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.comparable else 2


if __name__ == "__main__":
    raise SystemExit(main())
