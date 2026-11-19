#!/usr/bin/env python3
"""fetch_url.py

Dependency-free URL downloader for spreadsheet workflows.

Why this exists:
- Some environments don't have curl/wget/requests.
- Some CDNs return an HTML "Access Denied" page when you spoof a browser User-Agent.
- Proxy environment variables can break downloads.

This script uses Python's standard library (urllib) to download a URL to a file,
optionally bypassing proxies and performing lightweight file-signature checks.

It is intentionally generic: pass any URL and output path.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


def _build_opener(*, no_proxy: bool) -> urllib.request.OpenerDirector:
    if no_proxy:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def _sniff_prefix(path: Path, n: int = 512) -> bytes:
    with path.open("rb") as f:
        return f.read(n)


def _looks_like_html(prefix: bytes) -> bool:
    try:
        s = prefix.decode("utf-8", errors="ignore").lstrip().lower()
    except Exception:
        return False
    return s.startswith("<html") or s.startswith("<!doctype html")


def _verify_signature(*, path: Path, expect: str) -> Optional[str]:
    if expect == "none":
        return None

    prefix = _sniff_prefix(path)

    if expect in {"xlsx", "zip"}:
        if not prefix.startswith(b"PK\x03\x04"):
            if _looks_like_html(prefix):
                return "download looks like HTML, not a ZIP-based file (.xlsx/.zip)"
            return "file does not look like a ZIP container (missing PK\\x03\\x04 header)"

    if expect == "pdf":
        if not prefix.startswith(b"%PDF"):
            if _looks_like_html(prefix):
                return "download looks like HTML, not a PDF"
            return "file does not look like a PDF (missing %PDF header)"

    if expect in {"csv", "text"}:
        # Heuristic: reject obvious HTML.
        if _looks_like_html(prefix):
            return "download looks like HTML, not text/csv"

    return None


def fetch(
    url: str,
    out_path: Path,
    *,
    timeout: float,
    no_proxy: bool,
    user_agent: Optional[str],
) -> dict:
    opener = _build_opener(no_proxy=no_proxy)

    headers = {}
    # NOTE: Leaving User-Agent unset lets urllib send its default.
    # Some hosts block spoofed browser UAs; only set one if necessary.
    if user_agent is not None and user_agent != "":
        headers["User-Agent"] = user_agent

    req = urllib.request.Request(url, headers=headers)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".part")

    sha256 = hashlib.sha256()
    size = 0

    try:
        with opener.open(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            content_type = resp.headers.get("Content-Type")

            with tmp_path.open("wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha256.update(chunk)
                    size += len(chunk)

    except urllib.error.HTTPError as e:
        return {
            "ok": False,
            "error": f"HTTP error {e.code}: {e.reason}",
            "hint": "If you see 403/Access Denied, try removing custom User-Agent and/or bypassing proxies (--no-proxy).",
        }
    except urllib.error.URLError as e:
        return {
            "ok": False,
            "error": f"URL error: {e.reason}",
            "hint": "If your environment sets HTTP(S)_PROXY, try --no-proxy.",
        }

    tmp_path.replace(out_path)

    return {
        "ok": True,
        "status": status,
        "content_type": content_type,
        "bytes": size,
        "sha256": sha256.hexdigest(),
        "path": str(out_path),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Download a URL to a file (stdlib-only).")
    p.add_argument("url", help="HTTP(S) URL to download")
    p.add_argument("out", help="Output file path")
    p.add_argument(
        "--expect",
        default="none",
        choices=["none", "xlsx", "zip", "csv", "text", "pdf"],
        help="Lightweight file signature check",
    )
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument(
        "--no-proxy",
        action="store_true",
        help="Bypass proxy environment variables (HTTP_PROXY/HTTPS_PROXY)",
    )
    p.add_argument(
        "--user-agent",
        default=None,
        help="Optional User-Agent header. Leave unset unless required.",
    )

    args = p.parse_args()

    out_path = Path(args.out)

    result = fetch(
        args.url,
        out_path,
        timeout=args.timeout,
        no_proxy=args.no_proxy,
        user_agent=args.user_agent,
    )

    if result.get("ok"):
        sig_err = _verify_signature(path=out_path, expect=args.expect)
        if sig_err:
            print(
                (
                    "{\n"
                    f"  \"ok\": false,\n"
                    f"  \"error\": \"{sig_err}\",\n"
                    f"  \"path\": \"{result.get('path')}\",\n"
                    f"  \"bytes\": {result.get('bytes')}\n"
                    "}"
                )
            )
            raise SystemExit(2)

        print(
            (
                "{\n"
                "  \"ok\": true,\n"
                f"  \"status\": {result.get('status')},\n"
                f"  \"content_type\": {repr(result.get('content_type'))},\n"
                f"  \"bytes\": {result.get('bytes')},\n"
                f"  \"sha256\": \"{result.get('sha256')}\",\n"
                f"  \"path\": \"{result.get('path')}\"\n"
                "}"
            )
        )
        return

    # Failure
    err = result.get("error", "Unknown error")
    hint = result.get("hint")
    print("{\n" f"  \"ok\": false,\n" f"  \"error\": \"{err}\"" + (f",\n  \"hint\": \"{hint}\"" if hint else "") + "\n}")
    raise SystemExit(2)


if __name__ == "__main__":
    main()
