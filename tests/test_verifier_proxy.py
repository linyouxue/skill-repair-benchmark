from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from benchflow.task.verifier_core import _redact_verifier_proxy_output
from benchmark_executor.verifier_proxy import (
    _TCP_PROBE_COMMAND,
    ENV_VERIFIER_HTTP_PROXY,
    ENV_VERIFIER_HTTPS_PROXY,
    ENV_VERIFIER_PROXY_MODE,
    VerifierProxyPreflight,
    resolve_verifier_proxy_settings,
)


def test_default_off_never_inherits_runner_proxy() -> None:
    """Guards this verifier-proxy change: ordinary runner proxy stays private."""
    private_runner_value = "http://private-runner-proxy.example:17890"

    settings = resolve_verifier_proxy_settings(
        source_env={
            "HTTP_PROXY": private_runner_value,
            "HTTPS_PROXY": private_runner_value,
        }
    )

    assert settings.mode == "off"
    assert settings.enabled is False
    assert settings.env == {}
    assert private_runner_value not in repr(settings.metadata)


def test_preflight_command_preserves_env_file_exit_cleanup() -> None:
    """Guards this proxy change: child probes must not bypass the EXIT trap."""
    assert "\n  exec python" not in f"\n{_TCP_PROBE_COMMAND}"
    assert "\n  exec nc" not in f"\n{_TCP_PROBE_COMMAND}"
    assert "\n  exec bash" not in f"\n{_TCP_PROBE_COMMAND}"


def test_inherit_is_explicit_and_emits_only_verifier_env() -> None:
    """Guards this verifier-proxy change: inheritance requires explicit opt-in."""
    endpoint = "http://proxy.example.test:8080"
    settings = resolve_verifier_proxy_settings(
        source_env={
            ENV_VERIFIER_PROXY_MODE: "inherit",
            "HTTP_PROXY": endpoint,
            "HTTPS_PROXY": endpoint,
            "NO_PROXY": "database",
            "no_proxy": "target,database",
        }
    )

    assert settings.mode == "inherit"
    assert settings.env["HTTP_PROXY"] == endpoint
    assert settings.env["http_proxy"] == endpoint
    assert settings.env["HTTPS_PROXY"] == endpoint
    assert settings.env["https_proxy"] == endpoint
    assert "database" in settings.env["NO_PROXY"]
    assert "target" in settings.env["NO_PROXY"]
    assert "host.docker.internal" in settings.env["NO_PROXY"]
    assert settings.env["no_proxy"] == settings.env["NO_PROXY"]
    assert settings.endpoints[0].host == "proxy.example.test"
    assert endpoint not in repr(settings.metadata)


def test_explicit_mode_ignores_runner_proxy() -> None:
    """Guards this verifier-proxy change: dedicated settings win deterministically."""
    runner_loopback = "http://127.0.0.1:17890"
    verifier_endpoint = "http://host.docker.internal:18080"
    settings = resolve_verifier_proxy_settings(
        source_env={
            ENV_VERIFIER_PROXY_MODE: "explicit",
            "HTTP_PROXY": runner_loopback,
            "HTTPS_PROXY": runner_loopback,
            ENV_VERIFIER_HTTP_PROXY: verifier_endpoint,
            ENV_VERIFIER_HTTPS_PROXY: verifier_endpoint,
        }
    )

    assert settings.env["HTTP_PROXY"] == verifier_endpoint
    assert runner_loopback not in settings.env.values()
    assert settings.metadata["endpoint_scopes"] == ["docker-host"]
    assert "host.docker.internal" not in repr(settings)
    assert "18080" not in repr(settings)
    assert "host.docker.internal" not in repr(settings.endpoints)
    assert "18080" not in repr(settings.endpoints)


def test_repository_dotenv_is_supported_by_public_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards this verifier-proxy change: documented .env setup is effective."""
    dotenv = tmp_path / "executor.env"
    dotenv.write_text(
        "BENCHMARK_EXECUTOR_VERIFIER_PROXY_MODE=explicit\n"
        "BENCHMARK_EXECUTOR_VERIFIER_HTTP_PROXY="
        "http://proxy-from-dotenv.example:8080\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BENCHFLOW_DOTENV_PATH", str(dotenv))

    settings = resolve_verifier_proxy_settings()

    assert settings.mode == "explicit"
    assert settings.env["HTTP_PROXY"] == "http://proxy-from-dotenv.example:8080"


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://127.0.0.1:7890",
        "http://localhost:7890",
        "http://[::1]:7890",
        "http://0.0.0.0:7890",
    ],
)
def test_container_loopback_proxy_is_rejected(endpoint: str) -> None:
    """Guards this verifier-proxy change against unusable container loopback."""
    with pytest.raises(ValueError, match="container loopback"):
        resolve_verifier_proxy_settings(
            mode="explicit",
            source_env={ENV_VERIFIER_HTTP_PROXY: endpoint},
        )


def test_proxy_url_credentials_are_rejected() -> None:
    """Guards this verifier-proxy change against credential URL leakage."""
    with pytest.raises(ValueError, match="must not embed proxy credentials"):
        resolve_verifier_proxy_settings(
            mode="explicit",
            source_env={
                ENV_VERIFIER_HTTP_PROXY: "http://user:password@proxy.example:8080"
            },
        )


def test_proxy_configuration_fails_closed() -> None:
    """Guards this verifier-proxy change against ambiguous or incomplete config."""
    with pytest.raises(ValueError, match="must be one of"):
        resolve_verifier_proxy_settings(mode="automatic", source_env={})
    with pytest.raises(ValueError, match="no runner HTTP_PROXY"):
        resolve_verifier_proxy_settings(mode="inherit", source_env={})
    with pytest.raises(ValueError, match="conflicting runner proxy values"):
        resolve_verifier_proxy_settings(
            mode="inherit",
            source_env={
                "HTTP_PROXY": "http://one.example:80",
                "http_proxy": "http://two.example:80",
            },
        )
    with pytest.raises(ValueError, match="unsupported proxy scheme"):
        resolve_verifier_proxy_settings(
            mode="explicit",
            source_env={ENV_VERIFIER_HTTP_PROXY: "ftp://proxy.example:21"},
        )


@pytest.mark.asyncio
async def test_preflight_sends_no_proxy_url_or_credentials_to_task() -> None:
    """Guards this verifier-proxy change: preflight receives only host and port."""
    calls: list[dict] = []

    class Sandbox:
        async def exec(self, command: str, **kwargs):
            calls.append({"command": command, **kwargs})
            return SimpleNamespace(return_code=0, stdout="", stderr="")

    settings = resolve_verifier_proxy_settings(
        mode="explicit",
        source_env={ENV_VERIFIER_HTTP_PROXY: "http://host.docker.internal:18080"},
    )
    await VerifierProxyPreflight(settings.endpoints)(Sandbox())

    assert len(calls) == 1
    assert calls[0]["env"] == {
        "BENCHMARK_EXECUTOR_PROXY_PROBE_HOST": "host.docker.internal",
        "BENCHMARK_EXECUTOR_PROXY_PROBE_PORT": "18080",
    }
    assert calls[0]["service"] == "main"
    assert "http://" not in repr(calls)
    assert calls[0]["user"] == "root"


@pytest.mark.asyncio
async def test_preflight_failure_is_clear_and_pre_agent() -> None:
    """Guards this verifier-proxy change: bad routing fails before model spend."""

    class Sandbox:
        async def exec(self, command: str, **kwargs):
            return SimpleNamespace(
                return_code=1, stdout="", stderr="connection refused"
            )

    settings = resolve_verifier_proxy_settings(
        mode="explicit",
        source_env={ENV_VERIFIER_HTTP_PROXY: "http://proxy.example.test:18080"},
    )
    with pytest.raises(RuntimeError, match=r"preflight failed.*machine-local") as exc:
        await VerifierProxyPreflight(settings.endpoints)(Sandbox())
    assert "proxy.example.test" not in str(exc.value)
    assert "18080" not in str(exc.value)


@pytest.mark.asyncio
async def test_preflight_uses_the_actual_verifier_service() -> None:
    """Guards this proxy change for target-side multi-container verifiers."""
    calls: list[dict] = []

    class Sandbox:
        async def exec(self, command: str, **kwargs):
            calls.append({"command": command, **kwargs})
            return SimpleNamespace(return_code=0, stdout="", stderr="")

    settings = resolve_verifier_proxy_settings(
        mode="explicit",
        source_env={ENV_VERIFIER_HTTP_PROXY: "http://proxy.example.test:18080"},
    )
    await VerifierProxyPreflight(settings.endpoints, service="target")(Sandbox())

    assert calls[0]["service"] == "target"


@pytest.mark.asyncio
async def test_preflight_exception_does_not_persist_endpoint() -> None:
    """Guards this verifier-proxy change when a sandbox exec itself raises."""

    class Sandbox:
        async def exec(self, command: str, **kwargs):
            raise RuntimeError("cannot reach proxy.example.test:18080")

    settings = resolve_verifier_proxy_settings(
        mode="explicit",
        source_env={ENV_VERIFIER_HTTP_PROXY: "http://proxy.example.test:18080"},
    )
    with pytest.raises(RuntimeError, match="preflight failed") as exc:
        await VerifierProxyPreflight(settings.endpoints)(Sandbox())
    assert "proxy.example.test" not in str(exc.value)
    assert "18080" not in str(exc.value)


def test_verifier_stdout_redacts_injected_proxy_endpoint(tmp_path: Path) -> None:
    """Guards this verifier-proxy change against stdout endpoint disclosure."""
    endpoint = "http://host.docker.internal:18080"
    bypass = "internal-service.example,localhost"
    output = tmp_path / "test-stdout.txt"
    output.write_text(
        f"HTTP_PROXY={endpoint}\nNO_PROXY={bypass}\n"
        "error: failed to download package\n",
        encoding="utf-8",
    )

    _redact_verifier_proxy_output(
        output,
        {"HTTP_PROXY": endpoint, "NO_PROXY": bypass},
    )

    saved = output.read_text(encoding="utf-8")
    assert endpoint not in saved
    assert bypass not in saved
    assert "[REDACTED_VERIFIER_PROXY]" in saved
    assert "failed to download package" in saved
