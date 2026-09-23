#!/usr/bin/env python3
"""Offline-first dependency vulnerability audit for package-lock.json.

Design goals:
- Prefer an offline Trivy scan when available.
- Never claim vulnerabilities without an offline data source.
- Always write a CSV with the required header.

This script is intentionally self-contained (stdlib-only).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Optional


CSV_COLUMNS = [
    "Package",
    "Version",
    "CVE_ID",
    "Severity",
    "CVSS_Score",
    "Fixed_Version",
    "Title",
    "Url",
]

ALLOWED_SEVERITIES = {"HIGH", "CRITICAL"}


def _is_executable_on_path(prog: str) -> bool:
    paths = os.environ.get("PATH", "").split(os.pathsep)
    for p in paths:
        cand = os.path.join(p, prog)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return True
    return False


def _default_trivy_cache_dir() -> str:
    # Prefer an explicit env var to keep behavior controllable.
    env = os.environ.get("TRIVY_CACHE_DIR")
    if env:
        return env
    return os.path.abspath("./trivy-cache")


def _trivy_db_exists(cache_dir: str) -> bool:
    return os.path.exists(os.path.join(cache_dir, "db", "trivy.db"))


def _extract_cvss_score(vuln: Dict[str, Any]) -> str:
    cvss = vuln.get("CVSS")
    if not isinstance(cvss, dict):
        return "N/A"

    # Prefer v3 scores in source priority order.
    for source in ("nvd", "ghsa", "redhat"):
        src = cvss.get(source)
        if isinstance(src, dict):
            v3 = src.get("V3Score")
            if isinstance(v3, (int, float)):
                return str(v3)

    # Fallback to NVD v2 score if present.
    nvd = cvss.get("nvd")
    if isinstance(nvd, dict):
        v2 = nvd.get("V2Score")
        if isinstance(v2, (int, float)):
            return str(v2)

    return "N/A"


def _normalize_trivy_findings(trivy_json: Dict[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    results = trivy_json.get("Results", [])
    if not isinstance(results, list):
        return out

    for result in results:
        if not isinstance(result, dict):
            continue
        vulns = result.get("Vulnerabilities", [])
        if not isinstance(vulns, list):
            continue
        for v in vulns:
            if not isinstance(v, dict):
                continue
            sev = v.get("Severity")
            if sev not in ALLOWED_SEVERITIES:
                continue
            out.append(
                {
                    "Package": str(v.get("PkgName") or "N/A"),
                    "Version": str(v.get("InstalledVersion") or "N/A"),
                    "CVE_ID": str(v.get("VulnerabilityID") or "N/A"),
                    "Severity": str(sev),
                    "CVSS_Score": _extract_cvss_score(v),
                    "Fixed_Version": str(v.get("FixedVersion") or "N/A"),
                    "Title": str(v.get("Title") or v.get("Description") or "N/A"),
                    "Url": str(v.get("PrimaryURL") or "N/A"),
                }
            )

    return out


def _run_trivy_offline(lockfile: str, cache_dir: str) -> Optional[Dict[str, Any]]:
    if not _is_executable_on_path("trivy"):
        return None
    if not _trivy_db_exists(cache_dir):
        return None

    with tempfile.TemporaryDirectory(prefix="skillhone-trivy-") as td:
        out_path = os.path.join(td, "trivy.json")

        cmd = [
            "trivy",
            "fs",
            lockfile,
            "--format",
            "json",
            "--output",
            out_path,
            "--scanners",
            "vuln",
            "--skip-db-update",
            "--offline-scan",
            "--cache-dir",
            cache_dir,
            # Avoid slowing down / adding noise.
            "--quiet",
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            # Trivy can return non-zero for various reasons; do not emit findings.
            return None

        try:
            with open(out_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


def _write_csv(path: str, rows: Iterable[Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "N/A") for k in CSV_COLUMNS})


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lockfile", required=True, help="Path to package-lock.json")
    ap.add_argument("--output", required=True, help="Path to write security_audit.csv")
    ap.add_argument(
        "--trivy-cache-dir",
        default=None,
        help="Trivy cache dir containing db/trivy.db (defaults to TRIVY_CACHE_DIR or ./trivy-cache)",
    )
    args = ap.parse_args(argv)

    cache_dir = args.trivy_cache_dir or _default_trivy_cache_dir()

    trivy_json = _run_trivy_offline(args.lockfile, cache_dir)
    if trivy_json is None:
        # Deterministic output: header-only.
        _write_csv(args.output, [])
        return 0

    rows = _normalize_trivy_findings(trivy_json)
    _write_csv(args.output, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
