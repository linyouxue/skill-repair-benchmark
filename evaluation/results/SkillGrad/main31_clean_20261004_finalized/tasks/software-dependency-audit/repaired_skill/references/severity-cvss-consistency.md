# Severity/CVSS consistency for vulnerability reports

Use this chapter when you must emit both a severity label and a numeric CVSS score in the same output row. The goal is to avoid combining values that come from different sources or incompatible mappings.

## Procedure: select score + derive severity (or keep provenance)

### 1) Extract a CVSS score with provenance

Prefer CVSS v3/v3.1 when present. Keep `(score, version, source)` together.

```python
def pick_cvss_v3(cvss_block, source_priority=("nvd", "ghsa", "redhat")):
    """Return dict with score/version/source, or None."""
    if not isinstance(cvss_block, dict):
        return None

    for src in source_priority:
        entry = cvss_block.get(src)
        if not isinstance(entry, dict):
            continue
        score = entry.get("V3Score")
        if isinstance(score, (int, float)):
            return {"score": float(score), "version": "v3", "source": src}

    return None
```

### 2) Branch: decide how to emit Severity

- **Branch A (recommended)**: compute severity from the chosen numeric score.
- **Branch B**: emit severity from the same advisory source that supplied the score and include provenance columns.

```python
def cvss_v3_severity(score):
    if score is None:
        return "UNKNOWN"
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    if score > 0.0:
        return "LOW"
    return "NONE"


def build_score_and_severity(vuln, *, mode="derive", source_priority=("nvd", "ghsa", "redhat")):
    cvss_info = pick_cvss_v3(vuln.get("CVSS"), source_priority=source_priority)

    if cvss_info is None:
        # Runtime branch: no numeric CVSS available.
        # Keep the scanner label (if any) but mark provenance missing.
        return {
            "score": "N/A",
            "severity": vuln.get("Severity") or "UNKNOWN",
            "cvss_source": None,
            "cvss_version": None,
        }

    if mode == "derive":
        return {
            "score": cvss_info["score"],
            "severity": cvss_v3_severity(cvss_info["score"]),
            "cvss_source": cvss_info["source"],
            "cvss_version": cvss_info["version"],
        }

    # mode == "source": keep the chosen score but do not use an unrelated label.
    # If your scanner output does not provide per-source severity, you still
    # need a rule; deriving from score is usually the only consistent option.
    return {
        "score": cvss_info["score"],
        "severity": cvss_v3_severity(cvss_info["score"]),
        "cvss_source": cvss_info["source"],
        "cvss_version": cvss_info["version"],
    }
```

## Verification: block inconsistent rows

Run a consistency check over rows before finalizing the CSV.

```python
def find_inconsistent(rows):
    bad = []
    for r in rows:
        sev = (r.get("Severity") or "").upper()
        score = r.get("CVSS_Score")
        if not isinstance(score, (int, float)):
            continue

        # Runtime branch: mismatch heuristics based on standard CVSS v3 ranges.
        if sev == "CRITICAL" and score < 9.0:
            bad.append((r, "CRITICAL but score < 9"))
        if sev == "HIGH" and score >= 9.0:
            bad.append((r, "HIGH but score >= 9"))

    return bad


def verify_or_fix(rows):
    bad = find_inconsistent(rows)
    if not bad:
        return rows

    # Corrective action: re-build Severity from CVSS for all rows that have a numeric score.
    for r, _reason in bad:
        score = r.get("CVSS_Score")
        if isinstance(score, (int, float)):
            r["Severity"] = cvss_v3_severity(score)

    # Re-verify; if still inconsistent, escalate by attaching provenance columns
    # and/or failing the run so you can inspect the source selection.
    still_bad = find_inconsistent(rows)
    assert not still_bad, f"Severity/CVSS mismatches remain: {still_bad[:3]}"
    return rows
```

If the assertion fails:
1. Print a few offending rows including `CVE_ID`/package and any CVSS metadata.
2. Confirm your CVSS source selection is stable (single priority order) and that you didn’t parse a v2 score as v3.
3. If the scanner’s top-level severity must be preserved for policy reasons, add explicit provenance columns and stop deriving from numeric CVSS; otherwise, keep `mode="derive"`.
