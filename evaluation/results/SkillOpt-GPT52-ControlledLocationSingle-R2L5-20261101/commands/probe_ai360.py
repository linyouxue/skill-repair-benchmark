#!/usr/bin/env python3
"""Small, redacted readiness probe for the configured GPT-5.2 endpoint."""

from __future__ import annotations

import os
import sys

from openai import AuthenticationError, OpenAI


def main() -> None:
    base_url = os.environ.get("AI360_BASE_URL", "")
    api_key = os.environ.get("AI360_API_KEY", "")
    if not base_url or not api_key:
        print("AI360_PROBE_CONFIG_MISSING", file=sys.stderr)
        raise SystemExit(2)
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=30)
    try:
        response = client.chat.completions.create(
            model="openai/gpt-5.2",
            messages=[{"role": "user", "content": "Reply OK."}],
            max_tokens=16,
        )
    except AuthenticationError as exc:
        message = str(exc)
        if "1004" in message or "余额不足" in message:
            print("AI360_PROBE_BALANCE_INSUFFICIENT", file=sys.stderr)
            raise SystemExit(3) from None
        print("AI360_PROBE_AUTHENTICATION_FAILED", file=sys.stderr)
        raise SystemExit(4) from None
    except Exception as exc:  # noqa: BLE001 - readiness probe reports a redacted class
        print(f"AI360_PROBE_FAILED {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(5) from None
    if not response.choices:
        print("AI360_PROBE_EMPTY_RESPONSE", file=sys.stderr)
        raise SystemExit(6)
    print("AI360_PROBE_OK")


if __name__ == "__main__":
    main()
