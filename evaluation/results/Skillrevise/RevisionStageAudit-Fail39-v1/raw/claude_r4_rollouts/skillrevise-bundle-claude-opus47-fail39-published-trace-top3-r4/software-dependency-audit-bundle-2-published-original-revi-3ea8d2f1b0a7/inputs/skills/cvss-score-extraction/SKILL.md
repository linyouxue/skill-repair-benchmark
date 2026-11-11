# Dependency Vulnerability Audit To CSV

## Purpose
Produce a security audit CSV from a dependency-vulnerability scan by discovering the scanner, running it, filtering HIGH/CRITICAL findings, and emitting the exact columns required by the task spec.

## When to Use
Task asks for a vulnerability or dependency audit written to a specified CSV path with a declared column list and severity filter (e.g., HIGH and CRITICAL).

## Procedure
- Read the task spec to extract: output path, exact column list and order, severity whitelist, and any field-mapping hints. Treat these as the verifier contract.
- Discover inputs and tools: locate dependency manifests (e.g., requirements/package files) and detect an available scanner (e.g., `trivy`, `grype`); if none present, install or fail loudly rather than fabricate rows.
- Run the scanner producing JSON; parse `Results[*].Vulnerabilities[*]`.
- For each vulnerability, apply the severity filter first, then map fields using discovery-based rules:
- CVSS_Score: iterate CVSS sub-keys in preference order (nvd, ghsa, redhat, then any remaining); prefer `V3Score`, fall back to `V2Score`; use `N/A` only if truly absent.
- Url: `PrimaryURL` if present, else `References[0]`, else `N/A`.
- Title: `Title` if non-empty, else first sentence of `Description`.
- Fixed_Version: `FixedVersion` string as-is; `N/A` if missing.
- Package, Version, CVE_ID, Severity: direct fields.
- Write the CSV with header equal to the task-declared columns in the declared order.
- Post-write verification anchor: reload the CSV with `csv.DictReader`, assert header equals declared columns, row count > 0, every row's Severity is in the whitelist, and no required cell is empty; print a one-line summary (`rows=N, header_ok=True, empty_cells=0`). Fail and repair before claiming completion.

## Constraints / Pitfalls
- Do not hard-code CVSS source order as a literal rule; iterate present sources.
- Do not include severities outside the task-declared whitelist.
- Do not leave required columns blank; use `N/A` only where semantically appropriate (missing score, missing fix).
- Do not invent columns, reorder them, or add trailing columns.
- Do not silently switch the output path if write fails; inspect permissions and retry at the declared path.