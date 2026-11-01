from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Mapping

from skillrevise.core.env import env_flag_enabled, env_names, get_env, set_env_with_legacy
from skillrevise.llm.multimodal import MultimodalPrompt, provider_messages, validate_messages, write_json_gzip


DEFAULT_REVISION_LLM_PROVIDER = "openrouter"
DEFAULT_REVISION_LLM_API_KEY = ""
DEFAULT_REVISION_LLM_BASE_URL = ""
DEFAULT_REVISION_LLM_MODEL = ""
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 4096
DEFAULT_HTTP_TIMEOUT = 600
DEFAULT_HTTP_RETRY_ATTEMPTS = 3
DEFAULT_HTTP_RETRY_BASE_DELAY_SECONDS = 2.0
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"
LOCAL_CONFIG_MODULE = "skillrevise.local_llm_config"
PROXY_ENV_KEYS = {
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
}


class LLMCommandError(RuntimeError):
    """Raised when the external LLM wrapper cannot produce a completion."""


@dataclass
class LLMCommandConfig:
    provider: str
    model: str
    base_url: str
    api_key: str | None
    timeout_seconds: int
    retry_attempts: int
    retry_base_delay_seconds: float
    temperature: float
    max_tokens: int
    system_prompt: str
    effort: str | None = None
    seed: int | None = None
    thinking_mode: str | None = None
    anthropic_version: str = "2023-06-01"


def complete_prompt(prompt: str | MultimodalPrompt, env: Mapping[str, str] | None = None) -> str:
    config_env = _with_local_config(os.environ if env is None else env, use_local=env is None)
    config = load_config(config_env)
    if config.provider in {"openai", "openai-compatible", "openrouter"}:
        return complete_openai_compatible(prompt, config)
    if config.provider == "anthropic":
        return complete_anthropic(prompt, config)
    if config.provider == "ollama":
        return complete_ollama(prompt, config)
    raise LLMCommandError(
        f"Unsupported SKILL_REVISE_REVISION_LLM_PROVIDER={config.provider!r}. "
        "Use one of: openai, openrouter, anthropic, ollama."
    )


def load_config(env: Mapping[str, str]) -> LLMCommandConfig:
    provider = (get_env(env, "SKILL_REVISE_REVISION_LLM_PROVIDER", DEFAULT_REVISION_LLM_PROVIDER) or "").strip().lower()
    model = (
        get_env(env, "SKILL_REVISE_REVISION_LLM_MODEL")
        or DEFAULT_REVISION_LLM_MODEL
    ).strip()
    if not model:
        raise LLMCommandError(
            "Missing revision model. Set SKILL_REVISE_REVISION_LLM_MODEL "
            "or fill DEFAULT_REVISION_LLM_MODEL in llm_command.py."
        )

    purpose = get_env(env, "SKILL_REVISE_REVISION_LLM_PURPOSE", "general")
    system_prompt = get_env(
        env,
        "SKILL_REVISE_REVISION_LLM_SYSTEM_PROMPT",
        (
            "You are the LLM backend for SkillRevise. "
            "Follow the requested output format exactly and do not add unrelated commentary. "
            f"Current purpose: {purpose}."
        ),
    )

    return LLMCommandConfig(
        provider=provider,
        model=model,
        base_url=_base_url_for_provider(provider, env),
        api_key=_api_key_for_provider(provider, env),
        timeout_seconds=_env_int(env, "SKILL_REVISE_REVISION_LLM_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT),
        retry_attempts=max(
            1,
            _env_int(env, "SKILL_REVISE_REVISION_LLM_HTTP_RETRY_ATTEMPTS", DEFAULT_HTTP_RETRY_ATTEMPTS),
        ),
        retry_base_delay_seconds=max(
            0.0,
            _env_float(
                env,
                "SKILL_REVISE_REVISION_LLM_HTTP_RETRY_BASE_DELAY_SECONDS",
                DEFAULT_HTTP_RETRY_BASE_DELAY_SECONDS,
            ),
        ),
        temperature=_env_float(env, "SKILL_REVISE_REVISION_LLM_TEMPERATURE", DEFAULT_TEMPERATURE),
        max_tokens=_env_int(env, "SKILL_REVISE_REVISION_LLM_MAX_TOKENS", DEFAULT_MAX_TOKENS),
        system_prompt=system_prompt,
        effort=_optional_effort(env, "SKILL_REVISE_REVISION_LLM_EFFORT"),
        seed=_env_optional_int(env, "SKILL_REVISE_REVISION_LLM_SEED"),
        thinking_mode=_thinking_mode(env),
        anthropic_version=env.get("ANTHROPIC_VERSION", DEFAULT_ANTHROPIC_VERSION),
    )


def _with_local_config(env: Mapping[str, str], *, use_local: bool) -> dict[str, str]:
    if not use_local:
        return dict(env)
    merged = _load_local_config()
    merged.update({key: value for key, value in env.items() if value is not None})
    return merged


def _load_local_config() -> dict[str, str]:
    try:
        module = import_module(LOCAL_CONFIG_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == LOCAL_CONFIG_MODULE:
            return {}
        raise

    values: dict[str, str] = {}
    for key in (
        "SKILL_REVISE_REVISION_LLM_PROVIDER",
        "SKILL_REVISE_REVISION_LLM_MODEL",
        "SKILL_REVISE_REVISION_LLM_BASE_URL",
        "SKILL_REVISE_REVISION_LLM_API_KEY",
        "SKILL_REVISE_REVISION_LLM_TEMPERATURE",
        "SKILL_REVISE_REVISION_LLM_MAX_TOKENS",
        "SKILL_REVISE_REVISION_LLM_EFFORT",
        "SKILL_REVISE_REVISION_LLM_SEED",
        "SKILL_REVISE_REVISION_LLM_THINKING",
        "SKILL_REVISE_REVISION_LLM_HTTP_TIMEOUT",
        "SKILL_REVISE_REVISION_LLM_SYSTEM_PROMPT",
        "REVISION_OPENROUTER_API_KEY",
        "REVISION_OPENROUTER_BASE_URL",
    ):
        for candidate in env_names(key):
            value = getattr(module, candidate, "")
            if value not in {None, ""}:
                values[key] = str(value)
                break

    return values


def _thinking_mode(env: Mapping[str, str]) -> str | None:
    value = (get_env(env, "SKILL_REVISE_REVISION_LLM_THINKING") or "").strip().lower()
    if not value:
        return None
    if value not in {"enabled", "disabled"}:
        raise LLMCommandError(
            "SKILL_REVISE_REVISION_LLM_THINKING must be 'enabled' or 'disabled'."
        )
    return value


def complete_openai_compatible(prompt: str, config: LLMCommandConfig) -> str:
    if config.provider == "openai" and not config.api_key:
        raise LLMCommandError(
            "Missing SKILL_REVISE_REVISION_LLM_API_KEY for provider=openai."
        )
    if config.provider == "openrouter" and not config.api_key:
        raise LLMCommandError(
            "Missing REVISION_OPENROUTER_API_KEY or SKILL_REVISE_REVISION_LLM_API_KEY "
            "for provider=openrouter."
        )

    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": config.system_prompt},
            *provider_messages(prompt),
        ],
    }
    if _uses_openai_max_completion_tokens(config):
        payload["max_completion_tokens"] = config.max_tokens
    else:
        payload["max_tokens"] = config.max_tokens
    if not _omits_openai_chat_temperature(config):
        payload["temperature"] = config.temperature
    if config.effort:
        # Some OpenAI-compatible gateways expose Claude's effort control under
        # its native field name. It remains opt-in so existing OpenAI runs do
        # not receive an unsupported parameter.
        payload["effort"] = config.effort
    if config.seed is not None:
        payload["seed"] = config.seed
    if config.thinking_mode:
        payload["thinking"] = {"type": config.thinking_mode}
    url = _join_url(config.base_url, "chat/completions")
    last_error: LLMCommandError | None = None
    for attempt in range(1, config.retry_attempts + 1):
        response_data: dict[str, Any] | None = None
        try:
            response_data = _post_json(url, headers, payload, config.timeout_seconds)
            choices = response_data.get("choices") or []
            if not choices:
                detail = _describe_openai_compatible_error(response_data)
                raise LLMCommandError(
                    "OpenAI-compatible response did not contain choices."
                    + (f" {detail}" if detail else "")
                )
            first = choices[0]
            content = (first.get("message") or {}).get("content") or first.get("text")
            if not content:
                raise LLMCommandError(
                    "OpenAI-compatible response did not contain completion text."
                    f" {_describe_openai_choice(first)}"
                )
            return str(content).strip()
        except LLMCommandError as exc:
            last_error = exc
            if attempt >= config.retry_attempts or not _should_retry_openai_compatible_error(exc, response_data):
                raise
            _sleep_before_retry(config.retry_base_delay_seconds, attempt)
    assert last_error is not None
    raise last_error


def complete_anthropic(prompt: str, config: LLMCommandConfig) -> str:
    if not config.api_key:
        raise LLMCommandError(
            "Missing SKILL_REVISE_REVISION_LLM_API_KEY for provider=anthropic."
        )

    payload = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "system": config.system_prompt,
        "messages": provider_messages(prompt, anthropic=True),
    }
    # Claude Opus 4.7 exposes effort through the native Anthropic
    # ``output_config`` object.  Thinking is explicitly opt-in here: callers
    # that request ``disabled`` must have it represented on the wire instead
    # of silently falling back to the provider default.
    if config.effort:
        payload["output_config"] = {"effort": config.effort}
    if config.thinking_mode:
        payload["thinking"] = {"type": config.thinking_mode}
    headers = {
        "Content-Type": "application/json",
        "x-api-key": config.api_key,
        "anthropic-version": config.anthropic_version,
    }
    url = _join_url(config.base_url, "messages")
    last_error: LLMCommandError | None = None
    for attempt in range(1, config.retry_attempts + 1):
        response_data: dict[str, Any] | None = None
        try:
            response_data = _post_json(url, headers, payload, config.timeout_seconds)
            text = _extract_anthropic_text(response_data)
            if not text:
                raise LLMCommandError(
                    "Anthropic response did not contain text content."
                    f" {_describe_anthropic_content_shape(response_data)}"
                )
            return text
        except LLMCommandError as exc:
            last_error = exc
            if attempt >= config.retry_attempts or not _should_retry_anthropic_error(exc, response_data):
                raise
            _sleep_before_retry(config.retry_base_delay_seconds, attempt)
    assert last_error is not None
    raise last_error


def _extract_anthropic_text(data: Mapping[str, Any]) -> str:
    parts = _extract_text_parts(data.get("content"))

    message = data.get("message")
    if not parts and isinstance(message, Mapping):
        parts.extend(_extract_text_parts(message.get("content")))

    choices = data.get("choices")
    if not parts and isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, Mapping):
                continue
            choice_message = choice.get("message")
            if isinstance(choice_message, Mapping):
                parts.extend(_extract_text_parts(choice_message.get("content")))
            parts.extend(_extract_text_parts(choice.get("text")))

    if not parts:
        for key in ("text", "completion", "output_text", "response"):
            parts.extend(_extract_text_parts(data.get(key)))

    return "".join(parts).strip()


def _extract_text_parts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        parts: list[str] = []
        parts.extend(_extract_text_parts(value.get("text")))
        parts.extend(_extract_text_parts(value.get("content")))
        delta = value.get("delta")
        if isinstance(delta, Mapping):
            parts.extend(_extract_text_parts(delta.get("text")))
            parts.extend(_extract_text_parts(delta.get("content")))
        return parts
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.extend(_extract_text_parts(item))
        return parts
    return []


def _describe_anthropic_content_shape(data: Mapping[str, Any]) -> str:
    keys = ", ".join(sorted(str(key) for key in data.keys())[:8])
    content = data.get("content")
    if isinstance(content, list):
        block_shapes = []
        for block in content[:4]:
            if isinstance(block, Mapping):
                block_type = block.get("type")
                block_keys = ",".join(sorted(str(key) for key in block.keys())[:6])
                block_shapes.append(f"type={block_type!r};keys={block_keys}")
            else:
                block_shapes.append(type(block).__name__)
        shape = f"list[{'; '.join(block_shapes)}]"
    else:
        shape = type(content).__name__
    return f"Response keys: {keys or '<none>'}; content_shape={shape}."


def complete_ollama(prompt: str, config: LLMCommandConfig) -> str:
    if isinstance(prompt, MultimodalPrompt):
        raise LLMCommandError("JPG multimodal adapter requires OpenAI/OpenRouter or Anthropic transport")
    payload = {
        "model": config.model,
        "prompt": f"{config.system_prompt}\n\n{prompt}",
        "stream": False,
        "options": {"temperature": config.temperature},
    }
    data = _post_json(_join_url(config.base_url, "api/generate"), {"Content-Type": "application/json"}, payload, config.timeout_seconds)
    text = str(data.get("response", "")).strip()
    if not text:
        raise LLMCommandError("Ollama response did not contain response text.")
    return text


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    # Executor transcripts can occasionally contain an isolated UTF-16
    # surrogate (for example, from a tool's byte-oriented output).  Python's
    # default JSON encoder represents it as ``\\ud800`` etc., but strict
    # OpenAI-compatible APIs reject that invalid JSON string.  Replace only
    # those malformed code points before serializing; valid Unicode, including
    # Chinese text and valid emoji pairs, is retained.
    body = json.dumps(_sanitize_json_value(payload)).encode("utf-8")
    evidence_root = os.environ.get("SKILL_REVISE_HTTP_EVIDENCE_DIR")
    evidence = Path(evidence_root) / uuid.uuid4().hex if evidence_root else None
    if evidence:
        write_json_gzip(evidence / "request.json.gz", {
            "url": url.split("?", 1)[0], "payload": json.loads(body),
            "status": "prepared_before_http_dispatch", "authentication_headers_omitted": True,
        })
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            if evidence:
                write_json_gzip(evidence / "response.json.gz", {
                    "status": "http_response_received", "http_status": getattr(response, "status", 200),
                    "body": response_body,
                })
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        if evidence:
            write_json_gzip(evidence / "error.json.gz", {"status": "http_error", "http_status": exc.code, "body": error_body})
        raise LLMCommandError(f"LLM HTTP request failed with {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        if evidence:
            write_json_gzip(evidence / "error.json.gz", {"status": "transport_error", "error_type": type(exc).__name__})
        raise LLMCommandError(f"LLM HTTP request failed: {exc}") from exc

    try:
        data = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise LLMCommandError(f"LLM response was not valid JSON: {response_body[:500]}") from exc
    if not isinstance(data, dict):
        raise LLMCommandError("LLM response JSON was not an object.")
    return data


def _sanitize_json_value(value: Any) -> Any:
    """Make a JSON payload safe for strict Unicode parsers.

    ``surrogatepass`` preserves valid UTF-16 pairs while allowing us to
    identify isolated surrogate code points.  Decoding with ``replace`` turns
    only the latter into U+FFFD, which is valid JSON and UTF-8.
    """

    if isinstance(value, str):
        return value.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    if isinstance(value, Mapping):
        return {
            _sanitize_json_value(key): _sanitize_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_json_value(item) for item in value)
    return value


def _describe_openai_compatible_error(data: Mapping[str, Any]) -> str:
    error = data.get("error")
    if not isinstance(error, Mapping):
        keys = ", ".join(sorted(str(key) for key in data.keys())[:8])
        return f"Response keys: {keys}." if keys else ""
    parts = []
    for key in ("type", "code", "param"):
        value = error.get(key)
        if value not in {None, ""}:
            parts.append(f"{key}={str(value)[:120]}")
    message = error.get("message")
    if message:
        parts.append(f"message={str(message)[:240]}")
    return "Provider error: " + "; ".join(parts) + "." if parts else "Provider error."


def _describe_openai_choice(choice: Mapping[str, Any]) -> str:
    """Expose response shape without serializing model output or credentials."""

    parts = []
    finish_reason = choice.get("finish_reason")
    if finish_reason not in {None, ""}:
        parts.append(f"finish_reason={finish_reason}")
    message = choice.get("message")
    if isinstance(message, Mapping):
        fields = ", ".join(sorted(str(key) for key in message.keys())[:8])
        if fields:
            parts.append(f"message fields: {fields}")
        reasoning = message.get("reasoning_content")
        if reasoning:
            parts.append("reasoning_content was present")
    return " ".join(parts)


def _should_retry_openai_compatible_error(
    exc: LLMCommandError,
    data: Mapping[str, Any] | None,
) -> bool:
    text = str(exc).lower()
    non_retryable = (
        "invalid_api_key",
        "incorrect api key",
        "unauthorized",
        "authentication",
        "permission denied",
        "insufficient_quota",
        "quota",
        "billing",
        "credits",
        "missing revision",
        "missing skillrevise_revision_llm_api_key",
        "missing skill_revise_revision_llm_api_key",
        "missing revision_openrouter_api_key",
    )
    if any(marker in text for marker in non_retryable):
        return False
    retryable = (
        "did not contain choices",
        "did not contain completion text",
        "429",
        "rate limit",
        "rate_limit",
        "500",
        "502",
        "503",
        "504",
        "timeout",
        "timed out",
        "temporarily",
        "temporary",
        "overloaded",
        "unavailable",
        "try again",
        "upstream",
        "connection",
        "connection reset",
        "remote end closed",
        "remote disconnected",
        "ssl",
        "tls",
        "unexpected_eof",
        "unexpected eof",
        "eof occurred",
    )
    if any(marker in text for marker in retryable):
        return True
    if data is not None and not data.get("choices"):
        return True
    return False


def _should_retry_anthropic_error(
    exc: LLMCommandError,
    data: Mapping[str, Any] | None,
) -> bool:
    text = str(exc).lower()
    non_retryable = (
        "invalid_api_key",
        "incorrect api key",
        "unauthorized",
        "authentication",
        "permission denied",
        "insufficient_quota",
        "quota",
        "billing",
        "credits",
        "missing skillrevise_revision_llm_api_key",
        "missing skill_revise_revision_llm_api_key",
    )
    if any(marker in text for marker in non_retryable):
        return False
    retryable = (
        "did not contain text content",
        "did not contain completion text",
        "429",
        "rate limit",
        "rate_limit",
        "500",
        "502",
        "503",
        "504",
        "timeout",
        "timed out",
        "temporarily",
        "temporary",
        "overloaded",
        "unavailable",
        "try again",
        "upstream",
        "connection",
        "connection reset",
        "remote end closed",
        "remote disconnected",
        "ssl",
        "tls",
        "unexpected_eof",
        "unexpected eof",
        "eof occurred",
        "not valid json",
    )
    if any(marker in text for marker in retryable):
        return True
    if data is not None and not _extract_anthropic_text(data):
        return True
    return False


def _sleep_before_retry(base_delay_seconds: float, attempt: int) -> None:
    if base_delay_seconds <= 0:
        return
    time.sleep(base_delay_seconds * (2 ** (attempt - 1)))


def _base_url_for_provider(provider: str, env: Mapping[str, str]) -> str:
    explicit = get_env(env, "SKILL_REVISE_REVISION_LLM_BASE_URL") or DEFAULT_REVISION_LLM_BASE_URL
    if explicit:
        return explicit.rstrip("/")
    if provider == "openai":
        return DEFAULT_OPENAI_BASE_URL
    if provider == "openrouter":
        return (env.get("REVISION_OPENROUTER_BASE_URL") or DEFAULT_OPENROUTER_BASE_URL).rstrip("/")
    if provider == "openai-compatible":
        raise LLMCommandError(
            "provider=openai-compatible is not allowed in strict revision routing. "
            "Use SKILL_REVISE_REVISION_LLM_PROVIDER=openrouter/openai/anthropic/ollama."
        )
    if provider == "anthropic":
        return DEFAULT_ANTHROPIC_BASE_URL
    if provider == "ollama":
        return DEFAULT_OLLAMA_BASE_URL
    return ""


def _api_key_for_provider(provider: str, env: Mapping[str, str]) -> str | None:
    explicit = get_env(env, "SKILL_REVISE_REVISION_LLM_API_KEY") or DEFAULT_REVISION_LLM_API_KEY
    if explicit:
        return explicit
    if provider == "openrouter":
        return env.get("REVISION_OPENROUTER_API_KEY") or None
    if provider in {"openai", "openai-compatible"}:
        return None
    if provider == "anthropic":
        return None
    return None


def _join_url(base_url: str, suffix: str) -> str:
    return f"{base_url.rstrip('/')}/{suffix.lstrip('/')}"


def _uses_openai_max_completion_tokens(config: LLMCommandConfig) -> bool:
    if config.provider != "openai":
        return False
    return _is_openai_new_completion_model(config.model)


def _omits_openai_chat_temperature(config: LLMCommandConfig) -> bool:
    if config.provider != "openai":
        return False
    return _is_openai_new_completion_model(config.model)


def _is_openai_new_completion_model(model: str) -> bool:
    normalized = model.strip().lower()
    return normalized.startswith(("gpt-5", "o1", "o3", "o4"))


def _env_int(env: Mapping[str, str], key: str, default: int) -> int:
    value = get_env(env, key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise LLMCommandError(f"{key} must be an integer, got {value!r}.") from exc


def _env_optional_int(env: Mapping[str, str], key: str) -> int | None:
    value = get_env(env, key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise LLMCommandError(f"{key} must be an integer, got {value!r}.") from exc


def _optional_effort(env: Mapping[str, str], key: str) -> str | None:
    value = get_env(env, key)
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized not in {"low", "medium", "high", "max"}:
        raise LLMCommandError(
            f"{key} must be one of low, medium, high, max; got {value!r}."
        )
    return normalized


def _env_float(env: Mapping[str, str], key: str, default: float) -> float:
    value = get_env(env, key)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise LLMCommandError(f"{key} must be a float, got {value!r}.") from exc


def _bypass_proxy_enabled(env: Mapping[str, str]) -> bool:
    return env_flag_enabled(env, "SKILL_REVISE_BYPASS_PROXY") or env_flag_enabled(env, "SKILL_REVISE_NO_PROXY")


def _strip_proxy_from_process_env() -> None:
    for key in PROXY_ENV_KEYS:
        os.environ.pop(key, None)
    set_env_with_legacy(os.environ, "SKILL_REVISE_BYPASS_PROXY", "1")


def _configure_utf8_output() -> None:
    """Keep the JSON protocol valid on Windows terminals using a GBK code page."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


def main() -> None:
    _configure_utf8_output()
    if _bypass_proxy_enabled(os.environ):
        _strip_proxy_from_process_env()
    prompt = sys.stdin.read()
    try:
        if os.environ.get("SKILL_REVISE_LLM_INPUT_FORMAT") == "messages-v1":
            messages = json.loads(prompt)["messages"]
            validate_messages(messages)
            prompt = MultimodalPrompt(messages, os.environ.get("SKILL_REVISE_HTTP_EVIDENCE_DIR", ""))
        output = complete_prompt(prompt)
    except LLMCommandError as exc:
        print(f"skillrevise-llm error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(output)


if __name__ == "__main__":
    main()
