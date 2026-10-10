# 13F TSV Analyzer (Quarter Folders)

## Purpose
Analyze SEC 13F quarter datasets provided as TSV files to compute fund-level summaries (e.g., AUM/total value, holdings counts), quarter-over-quarter holding changes, and cross-fund holders for a given CUSIP, with explicit discovery, validation, and verifier-aligned output checks.

## When to Use
Use this when the environment provides per-quarter folders (e.g., `/root/<quarter>/`) containing TSV exports such as `COVERPAGE.tsv`, `SUMMARYPAGE.tsv`, and `INFOTABLE.tsv`, and the task asks you to identify a manager/fund filing (by accession), compute aggregates, and/or produce a JSON artifact for a verifier.

## Procedure
- **1) Discover inputs and validate the data interface (checkpoint: files + headers).**
- Locate candidate quarter directories by listing the working area (do not assume fixed names beyond what you can see).
- For each quarter directory you will use, assert these files exist and are readable:
- `COVERPAGE.tsv` (manager/filing metadata)
- `SUMMARYPAGE.tsv` (fund totals)
- `INFOTABLE.tsv` (holdings rows)
- Inspect and record the header row (column names) for each file before coding any parsing logic; confirm you can find the columns you will rely on (examples of commonly required fields):
- COVERPAGE: accession identifier, manager name, report type, report period/date
- SUMMARYPAGE: accession identifier, total value/AUM field(s)
- INFOTABLE: accession identifier, CUSIP, VALUE (and optionally share count/type)
- If required columns are missing or renamed, stop and adapt mappings based on observed headers (do not guess).
- **2) Identify the correct accession(s) for a target manager (checkpoint: candidate list + tie-break decision).**
- Load `COVERPAGE.tsv` for the quarter and perform a search for the manager/fund name provided by the task.
- Prefer a robust matching method available in the environment (e.g., exact substring match first; if you use fuzzy matching, keep it bounded and explain tie-break rules).
- Produce a short ranked candidate list (e.g., top 5) showing: accession, manager name, report type, and report period/date (whatever columns exist to support disambiguation).
- Tie-break rules (apply in order, using only fields you actually observed in headers):
- Prefer filings whose report type indicates standard 13F holdings (if such a column exists).
- Prefer the quarter/report period matching the quarter folder you are analyzing.
- Prefer the closest manager legal name match; if top matches are close/ambiguous, require an explicit selection step rather than silently picking one.
- Validate the chosen accession by confirming it appears in BOTH `SUMMARYPAGE.tsv` and `INFOTABLE.tsv` for that quarter (non-zero row count in holdings).
- **3) Compute requested metrics with explicit definitions (checkpoint: recomputable aggregates).**
- Fund summary (single quarter):
- AUM/total value: compute from `SUMMARYPAGE.tsv` for the chosen accession using the task-defined field (do not assume units; if the dataset provides units/notes, capture them).
- Holdings count: define it explicitly (commonly distinct CUSIP count from `INFOTABLE.tsv` for that accession). Verify by printing: total rows vs distinct CUSIPs.
- Quarter-over-quarter changes (two quarters):
- Identify accessions for the same manager in each quarter using step 2.
- Aggregate holdings by CUSIP within each quarter (sum VALUE per CUSIP for the accession).
- Join on CUSIP and compute deltas: `delta = value_new - value_old`.
- Define and compute the requested ranking (e.g., top buys = largest positive deltas; top sells = most negative deltas), and state whether you rank by absolute delta or signed delta, exactly as required by the task.
- Cross-fund holders for a CUSIP (single quarter):
- Filter `INFOTABLE.tsv` for the target CUSIP (validate the CUSIP format against what appears in the data; do not transform unless required).
- Group by accession, sum VALUE, rank descending.
- Map accession to manager name via `COVERPAGE.tsv` and verify join completeness (no unexpected missing names).
- **4) Write verifier-aligned output and perform final path + schema checks (checkpoint: file exists + reload + key/type assertions).**
- Determine the required output path from task instructions; if explicitly given, write exactly there. If the task is silent, use the conventional path only if the platform requires it (e.g., `/root/answers.json`) and document the choice in-code/comments.
- Write the JSON in one shot (avoid partial writes). Then immediately:
- Check the file exists at the exact output path and is readable.
- Re-open and JSON-parse it.
- Validate the schema against the task requirements (derive required keys/types from the prompt or provided template; if unknown, fail fast and request clarification rather than inventing fields).
- If writing fails (permissions/missing directory), inspect the filesystem (mounts/permissions) and retry to the same required path; do not silently switch to a different directory.

## Constraints / Pitfalls
- Do not hard-code repository-specific scripts, fixed folder names, or column names without first verifying them from the actual TSV headers in the environment.
- Do not auto-select an accession when manager-name matching is ambiguous; require a candidate list + tie-break rules + explicit confirmation, and validate the accession exists in both SUMMARYPAGE and INFOTABLE before computing results.