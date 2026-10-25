#!/usr/bin/env python3
"""Fail closed if a handoff package contains local credentials."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SECRET_NAME = re.compile(r"(?i)(api[_-]?key|token|secret|password|credential)")
HIGH_CONFIDENCE = (
    re.compile(rb"AKIA[A-Z0-9]{16}"),
    re.compile(rb"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"Bearer[ \t]+eyJ[A-Za-z0-9_.-]{20,}"),
)


def env_secrets(path: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    if not path.is_file():
        return result
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            line = line[1:].strip()
        if "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if SECRET_NAME.search(key) and len(value) >= 8 and "${" not in value and "<" not in value:
            result[key.strip()] = value.encode("utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--redact-exact", action="store_true")
    args = parser.parse_args()
    root = args.package_root.resolve()
    secrets = env_secrets(args.env)
    env_files: list[str] = []
    exact: dict[str, list[str]] = {name: [] for name in secrets}
    high_confidence_paths: set[str] = set()
    ignored_test_fixture_pattern_paths: set[str] = set()
    redacted_placeholder_paths: set[str] = set()
    scanned_files = 0
    scanned_bytes = 0

    redacted_files: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if path.name == ".env" or (
            path.name.startswith(".env.")
            and not path.name.endswith((".sample", ".example", ".template"))
        ):
            env_files.append(rel)
        scanned_files += 1
        overlap = b""
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                scanned_bytes += len(chunk)
                data = overlap + chunk
                if b"<REDACTED>" in data:
                    redacted_placeholder_paths.add(rel)
                for name, value in secrets.items():
                    if value in data and rel not in exact[name]:
                        exact[name].append(rel)
                if any(pattern.search(data) for pattern in HIGH_CONFIDENCE):
                    if rel.startswith("code/") and "/tests/" in rel:
                        ignored_test_fixture_pattern_paths.add(rel)
                    else:
                        high_confidence_paths.add(rel)
                overlap = data[-512:]

    exact = {name: paths for name, paths in exact.items() if paths}
    if args.redact_exact and exact:
        targets = sorted({item for paths in exact.values() for item in paths})
        for rel in targets:
            path = root / rel
            data = path.read_bytes()
            updated = data
            for value in secrets.values():
                updated = updated.replace(value, b"<REDACTED>")
            if updated != data:
                path.write_bytes(updated)
                redacted_files.append(rel)
        exact = {}
    payload = {
        "schema_version": "handoff-secret-audit-v1",
        "scanned_files": scanned_files,
        "scanned_bytes": scanned_bytes,
        "source_secret_variable_count": len(secrets),
        "included_env_files": env_files,
        "exact_local_secret_matches": exact,
        "redacted_exact_match_files": redacted_files,
        "redacted_placeholder_paths": sorted(redacted_placeholder_paths),
        "high_confidence_credential_pattern_paths": sorted(high_confidence_paths),
        "ignored_test_fixture_pattern_paths": sorted(ignored_test_fixture_pattern_paths),
        "passed": not env_files and not exact and not high_confidence_paths,
        "note": "Secret values are never written to this report.",
    }
    output = root / "metadata" / "SECURITY_SCAN.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
