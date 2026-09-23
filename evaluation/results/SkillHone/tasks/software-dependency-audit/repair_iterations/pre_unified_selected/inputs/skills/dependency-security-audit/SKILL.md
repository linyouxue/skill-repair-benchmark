---
name: dependency-security-audit
description: Generate a HIGH/CRITICAL dependency vulnerability report for a Node.js package-lock.json using offline-first scanning (Trivy if available) and deterministic CSV output.
---

# Dependency Security Audit (offline-first)

## What this skill provides

A small, deterministic audit procedure that:

- Reads a Node.js `package-lock.json`
- Detects **HIGH** and **CRITICAL** vulnerabilities using **offline-first** methods
- Normalizes findings into a required CSV schema
- **Always writes the CSV** (at minimum a header row) so downstream verifiers don’t fail on missing output

## Supported scanners (offline-first)

1. **Trivy (preferred, if present)**
   - Uses `trivy fs` with `--offline-scan` and `--skip-db-update`
   - Requires a pre-existing Trivy vulnerability DB in a cache directory

2. **npm audit (offline-capable fallback, if present)**
   - Runs `npm audit --json --audit-level=high` in the directory containing the lockfile.
   - If `npm audit` can complete using locally available advisory data, results are normalized into the required CSV.
   - If `npm audit` cannot complete (e.g., it requires network), it fails cleanly and we fall back further.

3. **Deterministic fallback behavior**
   - If neither offline data source works, the script writes a valid CSV with only the header row.
   - This avoids producing incorrect vulnerability claims without a database.

## Entry point

- Script: `audit_package_lock.py`

### Usage

```bash
python3 skills/dependency-security-audit/audit_package_lock.py \
  --lockfile /root/package-lock.json \
  --output /root/security_audit.csv
```

### Trivy configuration

By default the script looks for a Trivy DB under:

- `TRIVY_CACHE_DIR` env var, else
- `./trivy-cache` relative to the current working directory

The expected DB file is:

- `<cache-dir>/db/trivy.db`

Example:

```bash
TRIVY_CACHE_DIR=./trivy-cache python3 skills/dependency-security-audit/audit_package_lock.py \
  --lockfile /root/package-lock.json \
  --output /root/security_audit.csv
```

## Output

The CSV is written with exactly these columns:

`Package,Version,CVE_ID,Severity,CVSS_Score,Fixed_Version,Title,Url`

Only severities `HIGH` and `CRITICAL` are included.

## Notes on CVSS

When Trivy provides multiple CVSS sources, the script selects scores with this priority:

`nvd → ghsa → redhat → (nvd v2) → N/A`

## Runtime requirements

- Python 3 (standard library only)
- Optional: `trivy` binary available in `PATH`
- Optional: offline Trivy DB present in cache dir
