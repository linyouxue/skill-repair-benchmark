"""Verifier-only proxy configuration for the shared benchmark executor.

Proxy values are resolved once in the trusted runner process, kept in memory,
and passed only to the final verifier ``sandbox.exec`` call.  They are never
added to the agent environment or the container's persistent environment.
"""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast
from urllib.parse import urlsplit

from benchflow._dotenv import load_dotenv_env

VerifierProxyMode = Literal["off", "inherit", "explicit"]


class _SandboxExec(Protocol):
    async def exec(self, command: str, **kwargs: Any) -> Any: ...


ENV_VERIFIER_PROXY_MODE = "BENCHMARK_EXECUTOR_VERIFIER_PROXY_MODE"
ENV_VERIFIER_HTTP_PROXY = "BENCHMARK_EXECUTOR_VERIFIER_HTTP_PROXY"
ENV_VERIFIER_HTTPS_PROXY = "BENCHMARK_EXECUTOR_VERIFIER_HTTPS_PROXY"
ENV_VERIFIER_ALL_PROXY = "BENCHMARK_EXECUTOR_VERIFIER_ALL_PROXY"
ENV_VERIFIER_NO_PROXY = "BENCHMARK_EXECUTOR_VERIFIER_NO_PROXY"

_MODES = frozenset({"off", "inherit", "explicit"})
_PROXY_NAMES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
_PROXY_SCHEME_DEFAULT_PORT = {
    "http": 80,
    "https": 443,
    "socks4": 1080,
    "socks4a": 1080,
    "socks5": 1080,
    "socks5h": 1080,
}
_EXPLICIT_NAMES = {
    "HTTP_PROXY": ENV_VERIFIER_HTTP_PROXY,
    "HTTPS_PROXY": ENV_VERIFIER_HTTPS_PROXY,
    "ALL_PROXY": ENV_VERIFIER_ALL_PROXY,
    "NO_PROXY": ENV_VERIFIER_NO_PROXY,
}
_REQUIRED_NO_PROXY = (
    "localhost",
    "127.0.0.1",
    "::1",
    "host.docker.internal",
    "main",
)


@dataclass(frozen=True, repr=False)
class ProxyEndpoint:
    """A non-secret endpoint used by the pre-agent TCP reachability check."""

    host: str
    port: int


@dataclass(frozen=True)
class VerifierProxySettings:
    """Resolved verifier proxy values plus safe-to-persist metadata."""

    mode: VerifierProxyMode
    env: dict[str, str] = field(repr=False)
    endpoints: tuple[ProxyEndpoint, ...] = field(repr=False)
    metadata: dict[str, object]

    @property
    def enabled(self) -> bool:
        return bool(self.env)


def _nonempty(source: Mapping[str, str], name: str) -> str | None:
    value = source.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _inherit_value(source: Mapping[str, str], name: str) -> str | None:
    upper = _nonempty(source, name)
    lower = _nonempty(source, name.lower())
    if upper is not None and lower is not None and upper != lower:
        raise ValueError(
            f"conflicting runner proxy values for {name} and {name.lower()}"
        )
    return upper or lower


def _contains_control(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def _is_container_loopback(host: str) -> bool:
    normalized = host.rstrip(".").lower()
    if normalized in {"localhost", "localhost.localdomain"} or normalized.endswith(
        ".localhost"
    ):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


def _endpoint(name: str, value: str) -> ProxyEndpoint:
    if _contains_control(value):
        raise ValueError(f"{name} contains control characters")
    parsed = urlsplit(value)
    if not parsed.scheme or parsed.hostname is None:
        raise ValueError(f"{name} must be an absolute proxy URL with a hostname")
    scheme = parsed.scheme.lower()
    if scheme not in _PROXY_SCHEME_DEFAULT_PORT:
        raise ValueError(
            f"{name} uses unsupported proxy scheme {parsed.scheme!r}; expected "
            f"one of {sorted(_PROXY_SCHEME_DEFAULT_PORT)}"
        )
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(
            f"{name} must not embed proxy credentials in the URL; use a "
            "bridge-restricted relay without URL userinfo"
        )
    if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError(f"{name} must not contain a path, query, or fragment")
    host = parsed.hostname
    if _is_container_loopback(host):
        raise ValueError(
            f"{name} points to {host!r}; container loopback is not the runner. "
            "Configure a proxy endpoint reachable from Docker, such as a "
            "bridge-only relay advertised through host.docker.internal."
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{name} contains an invalid port") from exc
    if port is None:
        port = _PROXY_SCHEME_DEFAULT_PORT[scheme]
    return ProxyEndpoint(host=host, port=port)


def _no_proxy_values(*raw_values: str | None) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for raw in (*raw_values, *_REQUIRED_NO_PROXY):
        if raw is None:
            continue
        if _contains_control(raw):
            raise ValueError("NO_PROXY contains control characters")
        for item in raw.split(","):
            item = item.strip()
            if not item:
                continue
            marker = item.lower()
            if marker not in seen:
                seen.add(marker)
                values.append(item)
    return ",".join(values)


def _endpoint_scope(host: str) -> str:
    """Return a non-identifying endpoint category for persisted metadata."""

    normalized = host.rstrip(".").lower()
    if normalized == "host.docker.internal":
        return "docker-host"
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return "hostname"
    return "private-network" if address.is_private else "public-network"


def resolve_verifier_proxy_settings(
    *,
    mode: str | None = None,
    source_env: Mapping[str, str] | None = None,
) -> VerifierProxySettings:
    """Resolve opt-in verifier proxy settings without persisting proxy URLs.

    ``off`` is the default even when the runner itself has proxy variables.
    ``inherit`` copies the runner's standard proxy variables after validation.
    ``explicit`` reads the dedicated ``BENCHMARK_EXECUTOR_VERIFIER_*`` values.
    """

    # Match BenchFlow's provider/task env precedence: a repository-local .env
    # is a fallback, while an explicit process export wins. Tests and advanced
    # callers can pass source_env to make resolution fully deterministic.
    source = {**load_dotenv_env(), **os.environ} if source_env is None else source_env
    selected = mode if mode is not None else _nonempty(source, ENV_VERIFIER_PROXY_MODE)
    normalized = (selected or "off").strip().lower()
    if normalized not in _MODES:
        raise ValueError(
            f"{ENV_VERIFIER_PROXY_MODE} must be one of {sorted(_MODES)}, "
            f"got {selected!r}"
        )
    resolved_mode = cast(VerifierProxyMode, normalized)

    if resolved_mode == "off":
        return VerifierProxySettings(
            mode="off",
            env={},
            endpoints=(),
            metadata={
                "mode": "off",
                "enabled": False,
                "scope": "verifier-process-only",
                "preflight": "disabled",
            },
        )

    logical: dict[str, str] = {}
    if resolved_mode == "inherit":
        for name in _PROXY_NAMES:
            value = _inherit_value(source, name)
            if value is not None:
                logical[name] = value
        logical["NO_PROXY"] = _no_proxy_values(
            _nonempty(source, "NO_PROXY"),
            _nonempty(source, "no_proxy"),
        )
    else:
        for name, source_name in _EXPLICIT_NAMES.items():
            value = _nonempty(source, source_name)
            if value is not None:
                logical[name] = value
        logical["NO_PROXY"] = _no_proxy_values(logical.get("NO_PROXY"))

    configured = [name for name in _PROXY_NAMES if logical.get(name)]
    if not configured:
        source_hint = (
            "runner HTTP_PROXY/HTTPS_PROXY/ALL_PROXY"
            if resolved_mode == "inherit"
            else "BENCHMARK_EXECUTOR_VERIFIER_HTTP_PROXY/HTTPS_PROXY/ALL_PROXY"
        )
        raise ValueError(
            f"verifier proxy mode {resolved_mode!r} is enabled but no {source_hint} "
            "value is configured"
        )

    endpoints: list[ProxyEndpoint] = []
    for name in configured:
        endpoints.append(_endpoint(name, logical[name]))
    unique_endpoints = tuple(
        dict.fromkeys((endpoint.host, endpoint.port) for endpoint in endpoints)
    )
    endpoint_objects = tuple(
        ProxyEndpoint(host=host, port=port) for host, port in unique_endpoints
    )

    verifier_env: dict[str, str] = {}
    for name, value in logical.items():
        verifier_env[name] = value
        verifier_env[name.lower()] = value

    scopes = sorted({_endpoint_scope(endpoint.host) for endpoint in endpoint_objects})
    return VerifierProxySettings(
        mode=resolved_mode,
        env=verifier_env,
        endpoints=endpoint_objects,
        metadata={
            "mode": resolved_mode,
            "enabled": True,
            "scope": "verifier-process-only",
            "configured_proxy_vars": configured,
            "endpoint_scopes": scopes,
            "endpoint_count": len(endpoint_objects),
            "preflight": "tcp-from-task-container-before-agent",
        },
    )


_TCP_PROBE_COMMAND = r"""
set -eu
if command -v python3 >/dev/null 2>&1; then
  python3 -c 'import os,socket; socket.create_connection((os.environ["BENCHMARK_EXECUTOR_PROXY_PROBE_HOST"], int(os.environ["BENCHMARK_EXECUTOR_PROXY_PROBE_PORT"])), 8).close()'
elif command -v python >/dev/null 2>&1; then
  python -c 'import os,socket; socket.create_connection((os.environ["BENCHMARK_EXECUTOR_PROXY_PROBE_HOST"], int(os.environ["BENCHMARK_EXECUTOR_PROXY_PROBE_PORT"])), 8).close()'
elif command -v nc >/dev/null 2>&1; then
  nc -z -w 8 "$BENCHMARK_EXECUTOR_PROXY_PROBE_HOST" "$BENCHMARK_EXECUTOR_PROXY_PROBE_PORT"
elif command -v bash >/dev/null 2>&1; then
  bash -c 'exec 3<>/dev/tcp/$BENCHMARK_EXECUTOR_PROXY_PROBE_HOST/$BENCHMARK_EXECUTOR_PROXY_PROBE_PORT; exec 3>&-; exec 3<&-'
else
  echo 'verifier proxy preflight requires python, nc, or bash in the task image' >&2
  exit 86
fi
""".strip()


@dataclass(frozen=True)
class VerifierProxyPreflight:
    """Check every proxy endpoint from the task container before agent spend."""

    endpoints: tuple[ProxyEndpoint, ...] = field(repr=False)
    service: str = "main"

    async def __call__(self, sandbox: _SandboxExec) -> None:
        execute = sandbox.exec
        for endpoint in self.endpoints:
            try:
                result = await execute(
                    _TCP_PROBE_COMMAND,
                    env={
                        "BENCHMARK_EXECUTOR_PROXY_PROBE_HOST": endpoint.host,
                        "BENCHMARK_EXECUTOR_PROXY_PROBE_PORT": str(endpoint.port),
                    },
                    user="root",
                    service=self.service,
                    timeout_sec=12,
                )
            except Exception:
                raise RuntimeError(
                    "verifier proxy preflight failed from the task container; "
                    "check the machine-local verifier proxy configuration"
                ) from None
            return_code = int(getattr(result, "return_code", 1))
            if return_code != 0:
                raise RuntimeError(
                    "verifier proxy preflight failed from the task container "
                    f"for endpoint scope {_endpoint_scope(endpoint.host)!r}; "
                    "check the machine-local verifier proxy configuration"
                )
