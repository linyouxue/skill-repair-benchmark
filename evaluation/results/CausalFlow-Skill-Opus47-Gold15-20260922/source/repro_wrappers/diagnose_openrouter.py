"""Safely diagnose the local OpenRouter key and a minimal chat request.

The script never prints the raw API key. It reports only the key source, a
short SHA-256 fingerprint, account limits, HTTP status, and OpenRouter's safe
error fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from repro_wrappers.run_skillsbench_openrouter_smoke import (
        REPO_ROOT,
        read_env_value,
    )
except ModuleNotFoundError:  # Direct ``python repro_wrappers/...`` execution.
    from run_skillsbench_openrouter_smoke import REPO_ROOT, read_env_value

sys.path.insert(0, str(REPO_ROOT))

from skillsbench_replay.openrouter_acp_agent import describe_openrouter_http_error


API_ROOT = "https://openrouter.ai/api/v1"


def load_key() -> tuple[str, str]:
    env_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if env_key:
        return env_key, "OPENROUTER_API_KEY environment variable"
    file_key = read_env_value(REPO_ROOT / ".env", "OPENROUTER_SECRET_KEY")
    if file_key:
        return file_key, str(REPO_ROOT / ".env")
    raise SystemExit("No OPENROUTER_API_KEY or OPENROUTER_SECRET_KEY was found")


def request_json(
    url: str,
    api_key: str,
    *,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/benchflow-ai/skillsbench",
            "X-Title": "CausalFlow OpenRouter diagnostics",
            "X-OpenRouter-Metadata": "enabled",
        },
        method="POST" if payload is not None else "GET",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
            return response.status, body if isinstance(body, dict) else {}
        except urllib.error.HTTPError as exc:
            if attempt < 2 and exc.code in {429, 500, 502, 503, 504}:
                time.sleep(2 ** (attempt + 1))
                continue
            description = describe_openrouter_http_error(exc)
            return exc.code, {"diagnostic": description}
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            return 0, {"diagnostic": f"network_error={exc}"}
    raise AssertionError("unreachable")


def safe_error(payload: dict[str, Any]) -> str:
    if payload.get("diagnostic"):
        return str(payload["diagnostic"])
    error = payload.get("error")
    if not isinstance(error, dict):
        return "unknown error"
    return "; ".join(
        f"{name}={error[name]}"
        for name in ("code", "type", "message")
        if error.get(name) not in (None, "")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=os.environ.get(
            "CAUSALFLOW_MODEL", "anthropic/claude-opus-4.7"
        ),
    )
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument(
        "--reservation-probe-tokens",
        type=int,
        default=0,
        help=(
            "Request a tiny OK response while setting this maximum output-token "
            "reservation. This detects provider credit preauthorization failures."
        ),
    )
    args = parser.parse_args()

    api_key, source = load_key()
    fingerprint = hashlib.sha256(api_key.encode()).hexdigest()[:12]
    print(f"key_source={source}")
    print(f"key_length={len(api_key)} key_sha256_prefix={fingerprint}")

    key_status, key_payload = request_json(f"{API_ROOT}/key", api_key)
    print(f"key_endpoint_status={key_status}")
    if key_status == 200 and isinstance(key_payload.get("data"), dict):
        data = key_payload["data"]
        for name in (
            "label",
            "is_free_tier",
            "limit",
            "limit_remaining",
            "limit_reset",
            "usage",
            "expires_at",
        ):
            print(f"key_{name}={data.get(name)}")
    else:
        print(f"key_error={safe_error(key_payload)}")
        return 1

    credits_status, credits_payload = request_json(f"{API_ROOT}/credits", api_key)
    print(f"credits_endpoint_status={credits_status}")
    credits = credits_payload.get("data")
    if credits_status == 200 and isinstance(credits, dict):
        total_credits = credits.get("total_credits")
        total_usage = credits.get("total_usage")
        print(f"credits_total={total_credits}")
        print(f"credits_usage={total_usage}")
        if isinstance(total_credits, (int, float)) and isinstance(
            total_usage, (int, float)
        ):
            print(f"credits_remaining={total_credits - total_usage:.8f}")
    else:
        print(f"credits_error={safe_error(credits_payload)}")

    if args.skip_chat:
        return 0

    base_messages = [{"role": "user", "content": "Reply with OK only."}]
    if args.reservation_probe_tokens:
        if args.reservation_probe_tokens < 1:
            parser.error("--reservation-probe-tokens must be positive")
        reservation_payload = {
            "model": args.model,
            "messages": base_messages,
            "temperature": 0,
            "max_tokens": args.reservation_probe_tokens,
        }
        reservation_status, reservation_result = request_json(
            f"{API_ROOT}/chat/completions", api_key, payload=reservation_payload
        )
        print(f"reservation_probe_tokens={args.reservation_probe_tokens}")
        print(f"reservation_probe_status={reservation_status}")
        if reservation_status != 200:
            print(f"reservation_probe_error={safe_error(reservation_result)}")
            return 1
        print("diagnosis=requested output-token reservation is operational")
        return 0

    simple_payload = {
        "model": args.model,
        "messages": base_messages,
        "temperature": 0,
        "max_tokens": 8,
    }
    simple_status, simple_result = request_json(
        f"{API_ROOT}/chat/completions", api_key, payload=simple_payload
    )
    print(f"simple_chat_status={simple_status}")
    if simple_status != 200:
        print(f"simple_chat_error={safe_error(simple_result)}")
        return 1

    tool_payload = {
        "model": args.model,
        "messages": base_messages,
        "temperature": 0,
        "max_tokens": 16,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "noop",
                    "description": "A no-op diagnostic tool",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        "tool_choice": "auto",
    }
    tool_status, tool_result = request_json(
        f"{API_ROOT}/chat/completions", api_key, payload=tool_payload
    )
    print(f"tool_chat_status={tool_status}")
    if tool_status != 200:
        print(f"tool_chat_error={safe_error(tool_result)}")
        return 1
    print("diagnosis=key, simple chat, and tool-enabled chat are operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
