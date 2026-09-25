# SKILL.md

## When to use
Use this skill when you must **audit third-party dependencies from a lockfile** (here: a Node.js `package-lock.json`) and **report only HIGH/CRITICAL vulnerabilities** in a **CSV** with a fixed schema. Before acting, gather evidence from:
- The lockfile structure: how to enumerate **installed packages and resolved versions** (including nested/transitive deps).
- A vulnerability data source usable offline (e.g., cached advisories, local DB, locally available CLI scanners), and how it maps **package + version → vulnerability identifiers, severity, CVSS, fix versions, references**.
- Output contract: required columns and target output path.

## Possible Failure Modes
- **Auditing the wrong file or format** (e.g., `package.json` instead of `package-lock.json`) or mis-parsing lockfile version format differences.
- **Missing transitive dependencies** by scanning only top-level dependencies; many lockfiles include nested graphs that must be traversed.
- **Using declared version ranges** instead of the **installed/resolved version** recorded in the lockfile.
- **Including non-qualifying severities** (MEDIUM/LOW/UNKNOWN) or using inconsistent severity mapping between sources.
- **Reporting GHSA IDs only** when the contract requires a **CVE ID** (or leaving CVE blank when a mapping exists).
- **Omitting CVSS score or mixing scoring systems** without clarity (e.g., confusing “severity” label with numeric CVSS).
- **Wrong fixed version semantics** (e.g., copying “patched in” ranges verbatim vs selecting a minimal fixed version; or claiming a fix exists when it does not).
- **Duplicate rows** for the same package/version/vuln due to multiple paths in the dependency tree.
- **CSV formatting issues**: unescaped commas/newlines in titles/descriptions; wrong header order; wrong delimiter/encoding.
- **Non-reproducible/online-only lookup** when execution environment is offline; failing if network is blocked.
- **Overwriting unrelated files** or writing to the wrong output location.

## Possible procedures
1. **Ingest and parse the lockfile**
   - Load `/root/package-lock.json` as JSON and identify the section(s) containing resolved packages (lockfile versions differ; handle more than one schema).
   - Build a normalized list: `(package_name, installed_version)` for all unique packages, including transitive deps.
   - Decision point: if versions are missing/ambiguous, prefer the lockfile’s resolved `version` field; record evidence of where it was found.

2. **Normalize package coordinates**
   - Ensure names are in the ecosystem’s canonical form (e.g., scoped packages).
   - De-duplicate entries by `(name, version)` while retaining that they are installed.

3. **Query vulnerability intelligence (offline-capable)**
   - Choose a source/tool that can map `(name, version)` to known vulns and provides: CVE, severity, CVSS, fix version, title/summary, URL.
   - Decision point: if multiple sources disagree, pick a deterministic precedence order (e.g., prefer records with CVE + CVSS; otherwise fall back to the most authoritative available offline dataset).
   - Extract only items that qualify as **HIGH or CRITICAL** under the chosen source’s severity labeling.

4. **Shape results to the required schema**
   - For each qualifying vulnerability, populate:
     - `Package`, `Version` (installed), `CVE_ID`, `Severity`, `CVSS_Score`, `Fixed_Version` (or `N/A`), `Title`, `Url`.
   - If a vulnerability has multiple references, pick a single stable primary URL (e.g., NVD or the advisory’s canonical page).
   - If CVE is missing but can be mapped from an advisory ID in your data source, perform the mapping; otherwise decide whether to omit the record or mark CVE as unavailable based on the task contract (contract requires a CVE ID, so prioritize sources that provide it).

5. **Write `/root/security_audit.csv` robustly**
   - Use a CSV writer that properly escapes commas/newlines/quotes.
   - Write header exactly as specified and ensure deterministic row ordering (e.g., sort by `Package`, then `Version`, then `CVE_ID`) to reduce evaluator diffs.

6. **Recovery and sanity checks**
   - If the audit finds zero HIGH/CRITICAL issues, still write a valid CSV with only the header (unless instructed otherwise).
   - Handle parsing errors gracefully: confirm file exists, valid JSON, and expected keys; if not, re-check lockfile schema variants.

## Verification Checklist
- [ ] Parsed `/root/package-lock.json` successfully and extracted **installed** package versions (not ranges), including transitive deps.
- [ ] Vulnerability lookup is **offline-capable** (or confirmed environment permits required access) and results are traceable to a source.
- [ ] **Only HIGH and CRITICAL** severities included; no MEDIUM/LOW/UNKNOWN entries.
- [ ] Every row has all required columns in this exact order: `Package,Version,CVE_ID,Severity,CVSS_Score,Fixed_Version,Title,Url`.
- [ ] `CVE_ID` values are present and formatted as CVE identifiers; not just advisory IDs unless mapped to CVE.
- [ ] `CVSS_Score` is numeric (or a clearly defined numeric string) and corresponds to the cited source.
- [ ] `Fixed_Version` is a concrete version when available; otherwise exactly `N/A`.
- [ ] Titles/descriptions and URLs are correctly CSV-escaped; file opens cleanly in a CSV reader.
- [ ] No duplicate rows for the same `(Package, Version, CVE_ID)` unless justified by distinct vulnerabilities.
- [ ] Output written to **`/root/security_audit.csv`** and unrelated files/state are not modified.
- [ ] Confirm you did not copy concrete package facts from any retrieved examples; decisions are grounded in the current lockfile and chosen vulnerability dataset/tool.
