---
name: cvss-score-extraction
description: Extract a numeric CVSS score from vulnerability objects (e.g., Trivy JSON) with safe fallbacks across sources (NVD, GHSA, RedHat) and CVSS versions.
---

# CVSS Score Extraction from Vulnerability Data

This skill provides guidance (and reusable Python snippets) for extracting a **single CVSS base score** per vulnerability from scanner output.

## Why this matters

Many audit/reporting tasks require a **CVSS score** column. Scanner outputs often contain:

- Multiple sources (e.g., **NVD**, **GHSA**, **RedHat**, vendor feeds)
- Multiple versions (CVSS **v3** vs **v2**)
- Missing or non-numeric values

A robust extractor should:

1. Prefer CVSS **v3** when available.
2. Prefer more authoritative sources first (commonly **NVD → GHSA → RedHat**).
3. Fall back to other sources and then to CVSS **v2**.
4. Return a clear sentinel (`"N/A"`) when no numeric score exists.

## Typical Trivy JSON shape

Trivy commonly represents CVSS under a `CVSS` object on each vulnerability:

```json
{
  "VulnerabilityID": "CVE-2021-0000",
  "Severity": "HIGH",
  "CVSS": {
    "nvd": { "V3Score": 7.5, "V3Vector": "CVSS:3.1/..." },
    "ghsa": { "V3Score": 7.5 }
  }
}
```

Notes:

- Keys like `nvd`, `ghsa`, and `redhat` are commonly **lowercase**.
- Some entries may only provide `V2Score`.
- Some scanners add additional keys (treat them as lower-priority fallbacks).

## Recommended extraction logic (Python)

Return either a `float` or the string `"N/A"`.

```python
from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence, Union

PREFERRED_SOURCES: Sequence[str] = ("nvd", "ghsa", "redhat")


def _coerce_float(value: Any) -> Optional[float]:
    """Convert ints/floats/strings to float; return None if not parseable."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _iter_sources(cvss: dict, preferred_sources: Sequence[str]) -> Iterable[str]:
    """Yield CVSS source keys in preferred order, then remaining keys."""
    seen = set()
    for s in preferred_sources:
        if s in cvss:
            seen.add(s)
            yield s
    for s in sorted(k for k in cvss.keys() if k not in seen):
        yield s


def extract_cvss_score(vuln: dict, preferred_sources: Sequence[str] = PREFERRED_SOURCES) -> Union[float, str]:
    """Extract a best-effort CVSS base score from a vulnerability object."""
    cvss = vuln.get("CVSS") or {}
    if not isinstance(cvss, dict):
        return "N/A"

    # Prefer CVSS v3 scores.
    for src in _iter_sources(cvss, preferred_sources):
        entry = cvss.get(src)
        if isinstance(entry, dict):
            score = _coerce_float(entry.get("V3Score"))
            if score is not None:
                return score

    # Fallback to CVSS v2.
    for src in _iter_sources(cvss, preferred_sources):
        entry = cvss.get(src)
        if isinstance(entry, dict):
            score = _coerce_float(entry.get("V2Score"))
            if score is not None:
                return score

    return "N/A"
```

### Formatting for CSV output

If you need a stable string form (e.g., for CSV), format floats explicitly:

```python
score = extract_cvss_score(vuln)
cvss_str = "N/A" if score == "N/A" else f"{score:.1f}"
```

## Best practices

- **Do not crash on missing CVSS data**: always fall back to `"N/A"`.
- **Avoid hardcoding a single source**: scanner feeds vary.
- **Keep source priority configurable** when building reusable scripts.

## References

- [CVSS v3.1 Specification](https://www.first.org/cvss/v3.1/specification-document)
- [NVD](https://nvd.nist.gov/)
- [GitHub Security Advisories](https://github.com/advisories)
