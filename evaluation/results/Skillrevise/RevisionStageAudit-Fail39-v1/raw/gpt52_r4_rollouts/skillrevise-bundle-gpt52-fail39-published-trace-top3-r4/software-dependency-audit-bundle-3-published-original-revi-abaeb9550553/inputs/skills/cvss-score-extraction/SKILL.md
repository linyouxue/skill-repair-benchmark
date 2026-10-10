# Dependency Security Audit CSV (Trivy JSON to CSV)

## Purpose
Produce a verifier-aligned security audit CSV by scanning a project for vulnerabilities, extracting CVE and CVSS data with stable fallbacks, filtering to the required severities, writing the CSV to the task-specified path, and validating the artifact and schema before finishing.

## When to Use
Use this when a task requires a machine-readable CSV deliverable (often at a specific path) summarizing HIGH/CRITICAL vulnerabilities from a dependency scan (commonly Trivy), including identifiers, package info, CVSS score selection, and remediation fields.

## Procedure
- Step 1: Discover the contract and inputs (do not assume)
- Identify the required output path and required CSV columns from the task statement; if either is not explicit, pause and infer from nearby task scaffolding (e.g., README, provided verifier script) or ask for clarification.
- Discover the dependency target(s): locate lockfiles/manifests by listing the working directory and searching for common files (package-lock.json, yarn.lock, pnpm-lock.yaml, requirements.txt, poetry.lock, Pipfile.lock, go.mod, Cargo.lock, Gemfile.lock).
- Check tool availability: confirm whether a scanner (prefer Trivy) exists in PATH; if not, look for an allowed alternative already present (do not install unless explicitly allowed).
- Step 2: Run a scan with a reproducible, inspectable output
- Run the scanner in a mode that emits structured output (JSON preferred) and captures dependency vulnerabilities for the discovered target.
- Save the raw scan output to a local file (path discovered at runtime); record how to reproduce it.
- Checkpoint: confirm the JSON file exists and is parseable (load it with a JSON parser). If parse fails, re-run with correct output flags or switch scanner mode.
- Step 3: Parse and normalize vulnerability records (schema-driven)
- Load the JSON and discover where vulnerabilities live (commonly Results[*].Vulnerabilities[*]); do not hard-code the nesting until confirmed by inspection of keys.
- For each vulnerability record, construct a normalized row object using the required CSV columns; typical fields include:
- Vulnerability ID (e.g., CVE), package name, installed version, fixed version (or "N/A"), severity, title/description, URL, CVSS score, CVSS version, CVSS source.
- CVSS selection rule (keep minimal, behavior-changing logic):
- Prefer CVSS v3/v3.1 base score when present; use source priority: nvd then ghsa then redhat (only among sources actually present in the record).
- If no v3 score exists, optionally fall back to v2 score from the highest-priority available source (commonly nvd) if the task allows; otherwise set "N/A".
- Accept only numeric scores (int/float); otherwise treat as missing and continue fallback.
- URL selection fallback:
- Prefer a primary URL field if present (often PrimaryURL).
- Else use the first item in a References list/array if present.
- Else set "N/A".
- Filtering decision point:
- Apply the task-required filter. If the requirement is "HIGH and CRITICAL only", filter by severity label (case-insensitive match).
- If the requirement is score-threshold-based, filter by numeric CVSS when available; if missing, fall back to severity label only if the task explicitly permits.
- Checkpoint: report counts (total vulns found, rows after filtering). If zero rows remain, keep going (still write a CSV with header), but note the reason.
- Step 4: Write CSV to the required path and validate (hard completion gate)
- Write the CSV to the exact task-specified output path. Do not silently change directories or substitute a different path.
- Use a CSV writer that quotes/escapes fields and writes a single header row matching the required column names exactly.
- Post-write validation (must pass before completion):
- Existence/readability: stat and read the file from the exact required path.
- Schema: parse the CSV back in and assert the header contains all required columns (and no unexpected header mismatches if the contract is exact).
- Content: assert every row satisfies the filter condition (e.g., severity in {HIGH, CRITICAL}); assert CVSS values are either numeric or "N/A" per schema.
- Sanity: if the scan reported at least one HIGH/CRITICAL vuln, assert row count > 0; otherwise allow 0 rows but keep header.
- If any validation fails: do not claim completion. Fix mapping, filter logic, or write location, then re-run Step 4.

## Constraints / Pitfalls
- Never assume JSON schema, vulnerability nesting, required CSV headers, or output path; always discover from task instructions and by inspecting the scan output before coding the parser.
- Do not complete until the CSV is written to the exact required path and passes a reload-and-assert validation (existence, header/schema, and filter correctness); printing to stdout or writing to an alternate path is not acceptable.