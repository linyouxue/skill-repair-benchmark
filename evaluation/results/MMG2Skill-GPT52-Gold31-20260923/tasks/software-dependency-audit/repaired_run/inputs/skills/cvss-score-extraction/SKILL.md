---
name: cvss-score-extraction
description: Extract a CVSS score from scanner vulnerability objects (e.g., Trivy
  JSON) with consistent source/field fallback.
---

## Steps
1. Read the vulnerability’s `CVSS` object (default to `{}` if missing or not a dict).
2. Prefer CVSS v3 scores when present; use the first available source in this priority order: `nvd` → `ghsa` → `redhat`.
3. If no v3 score exists, optionally fall back to `nvd` v2 (`V2Score`) if present; otherwise return `N/A`.
4. Validate the chosen score is numeric (`int`/`float`); otherwise return `N/A`.
5. (Optional for traceability in code) return both `score` and the `source` key used (e.g., `{'score': 7.5, 'source': 'ghsa', 'version': 'v3'}`), even if only `score` is written to the CSV.
## Expected Result
A numeric CVSS score (preferably v3/v3.1) is consistently selected from the best available source, or `N/A` if unavailable.
