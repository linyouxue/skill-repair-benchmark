# Trivy HIGH/CRITICAL filtering vs CVSS extraction (exercise)

Trivy JSON commonly contains both:
- a scanner-provided severity label at `vuln["Severity"]`, and
- optional CVSS blocks under `vuln["CVSS"]` that may vary by source and may be missing.

Use this chapter when you must output **all HIGH/CRITICAL findings** while also reporting CVSS, without letting CVSS parsing change the inclusion set.

## Procedure (with runtime branches)

### 1) Choose the inclusion predicate

- **Branch A (most audits):** the task says “HIGH/CRITICAL vulnerabilities” (or similar) → include based on `vuln["Severity"]`.
- **Branch B:** the task defines inclusion by CVSS score/threshold → include based on CVSS, and explicitly state that you are using CVSS-derived severity/threshold.

### 2) Implement: filter by Trivy severity, extract CVSS separately

```python
import json

ALLOWED = {"HIGH", "CRITICAL"}
SOURCE_PRIORITY = ["nvd", "ghsa", "redhat"]


def pick_cvss_v3(vuln, sources=SOURCE_PRIORITY):
    cvss = vuln.get("CVSS") or {}
    if not isinstance(cvss, dict):
        return None, None
    for src in sources:
        block = cvss.get(src)
        if isinstance(block, dict):
            score = block.get("V3Score")
            if isinstance(score, (int, float)):
                return score, src
    return None, None


def iter_trivy_vulns(path):
    data = json.load(open(path, "r", encoding="utf-8"))
    for res in data.get("Results", []) or []:
        for v in res.get("Vulnerabilities", []) or []:
            yield v


def high_critical_rows(path):
    for v in iter_trivy_vulns(path):
        sev = (v.get("Severity") or "").upper()
        if sev in ALLOWED:  # inclusion independent of CVSS
            score, src = pick_cvss_v3(v)
            yield {
                "VulnerabilityID": v.get("VulnerabilityID"),
                "PkgName": v.get("PkgName"),
                "Severity": sev,
                "CVSS_V3": score if score is not None else "N/A",
                "CVSS_Source": src if src is not None else "N/A",
            }
```

### 3) Verification: detect omissions before finalizing output

Compute the expected identifier set from JSON using the inclusion predicate, then compare it to what you wrote.

```python
import csv


def idset_from_json(path):
    ids = set()
    for v in iter_trivy_vulns(path):
        if (v.get("Severity") or "").upper() in ALLOWED:
            ids.add((v.get("VulnerabilityID"), v.get("PkgName"), v.get("InstalledVersion")))
    return ids


def idset_from_csv(path):
    ids = set()
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ids.add((r.get("VulnerabilityID"), r.get("PkgName") or r.get("Package"), r.get("InstalledVersion") or r.get("Version")))
    return ids


def verify_subset(json_path, csv_path):
    expected = idset_from_json(json_path)
    actual = idset_from_csv(csv_path)

    missing = expected - actual
    extra = actual - expected

    if missing or extra:
        raise AssertionError(
            f"CSV does not match JSON filter. missing={len(missing)} extra={len(extra)}\n"
            f"Example missing: {next(iter(missing)) if missing else None}\n"
            f"Example extra: {next(iter(extra)) if extra else None}"
        )

# If verification fails:
# 1) Confirm you filtered by vuln['Severity'] (not CVSS-derived),
# 2) Confirm you did not accidentally deduplicate rows,
# 3) Regenerate the CSV and re-run verify_subset.
```

## Notes

- If you intentionally deduplicate (e.g., by `VulnerabilityID` only), update the identifier tuple consistently on both sides of the verification.
- CVSS structures can be missing or vary by source; absence of CVSS must never exclude a vulnerability when the task’s inclusion is scanner-severity based.
