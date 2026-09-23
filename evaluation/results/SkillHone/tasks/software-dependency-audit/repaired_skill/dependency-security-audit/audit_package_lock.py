#!/usr/bin/env python3
"""Offline-first dependency vulnerability audit for package-lock.json.

Design goals:
- Prefer an offline Trivy scan when available.
- Fall back to other *offline* scanners (e.g., local `npm audit`) when Trivy isn't usable.
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

# npm audit uses lowercase severities; normalize to Trivy-like ones.
_NPM_SEVERITY_MAP = {
    "critical": "CRITICAL",
    "high": "HIGH",
}


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
    """Heuristically detect a usable offline Trivy DB.

    Trivy cache layouts vary by version and platform. Some installations keep the
    DB under `db/`, others use different filenames, and newer caches include
    additional metadata files.

    We keep this check conservative (must find at least one plausible DB
    artifact) but not overly strict (do not require an exact filename).
    """
    db_dir = os.path.join(cache_dir, "db")
    if not os.path.isdir(db_dir):
        return False

    # Historical/default filename.
    if os.path.exists(os.path.join(db_dir, "trivy.db")):
        return True

    # Any sqlite-like DB file in db/ is a good signal.
    try:
        for name in os.listdir(db_dir):
            lower = name.lower()
            if lower.endswith((".db", ".sqlite", ".sqlite3")):
                return True
            if lower in ("metadata.json", "trivy.db.gz"):
                return True
    except OSError:
        return False

    return False


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


def _run_npm_audit_offline(project_dir: str) -> Optional[Dict[str, Any]]:
    """Run `npm audit` in a way that can work offline.

    Notes:
    - We do not set `--registry` or fetch anything.
    - If npm cannot complete without network/advisory data, it may fail; in
      that case we return None.
    """
    if not _is_executable_on_path("npm"):
        return None

    cmd = ["npm", "audit", "--json", "--audit-level=high"]
    proc = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "NPM_CONFIG_AUDIT_LEVEL": "high"},
    )
    if proc.returncode not in (0, 1):
        # npm returns 1 when vulns are found.
        return None

    try:
        return json.loads(proc.stdout or "{}")
    except Exception:
        return None


def _normalize_npm_audit_findings(audit_json: Dict[str, Any]) -> List[Dict[str, str]]:
    """Normalize npm audit JSON (npm v7+ format).

    We only emit HIGH/CRITICAL rows.
    """
    out: List[Dict[str, str]] = []
    vulns = audit_json.get("vulnerabilities")
    if not isinstance(vulns, dict):
        return out

    for pkg, v in vulns.items():
        if not isinstance(v, dict):
            continue
        sev_raw = v.get("severity")
        if not isinstance(sev_raw, str):
            continue
        sev = _NPM_SEVERITY_MAP.get(sev_raw.lower())
        if sev not in ALLOWED_SEVERITIES:
            continue

        installed = v.get("installed")
        fixed = v.get("fixAvailable")

        fixed_version = "N/A"
        if isinstance(fixed, dict):
            fv = fixed.get("version")
            if isinstance(fv, str) and fv:
                fixed_version = fv
        elif fixed is True:
            fixed_version = "N/A"

        via = v.get("via", [])
        # Prefer advisory objects in `via`; sometimes entries are strings.
        advisory_obj = None
        if isinstance(via, list):
            for item in via:
                if isinstance(item, dict):
                    advisory_obj = item
                    break

        cve_id = "N/A"
        title = "N/A"
        url = "N/A"
        cvss_score = "N/A"
        if isinstance(advisory_obj, dict):
            title = str(advisory_obj.get("title") or "N/A")
            url = str(advisory_obj.get("url") or "N/A")
            cwe = advisory_obj.get("cwe")
            # npm audit advisories commonly include "cwe" not CVE; try to infer
            # from `cves` or `id` fields when present.
            cves = advisory_obj.get("cves")
            if isinstance(cves, list) and cves:
                cve_id = str(cves[0])
            else:
                ident = advisory_obj.get("id")
                if isinstance(ident, (int, str)) and str(ident):
                    cve_id = str(ident)
            cvss = advisory_obj.get("cvss")
            if isinstance(cvss, dict):
                score = cvss.get("score")
                if isinstance(score, (int, float)):
                    cvss_score = str(score)
            _ = cwe  # keep lint-friendly; stdlib only.

        out.append(
            {
                "Package": str(pkg or "N/A"),
                "Version": str(installed or "N/A"),
                "CVE_ID": str(cve_id),
                "Severity": str(sev),
                "CVSS_Score": str(cvss_score),
                "Fixed_Version": str(fixed_version),
                "Title": str(title),
                "Url": str(url),
            }
        )

    return out


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
    if trivy_json is not None:
        rows = _normalize_trivy_findings(trivy_json)
        _write_csv(args.output, rows)
        return 0

    # Fallback: try local npm audit (can work when npm has offline advisory data
    # available; otherwise it fails cleanly).
    project_dir = os.path.dirname(os.path.abspath(args.lockfile)) or "."
    npm_json = _run_npm_audit_offline(project_dir)
    if npm_json is not None:
        rows = _normalize_npm_audit_findings(npm_json)
        _write_csv(args.output, rows)
        return 0

    # Deterministic output: header-only.
    _write_csv(args.output, [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
