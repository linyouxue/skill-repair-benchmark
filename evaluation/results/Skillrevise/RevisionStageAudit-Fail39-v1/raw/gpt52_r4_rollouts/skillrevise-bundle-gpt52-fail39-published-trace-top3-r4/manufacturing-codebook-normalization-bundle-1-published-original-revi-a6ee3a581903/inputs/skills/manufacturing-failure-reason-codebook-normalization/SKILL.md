# manufacturing-failure-reason-codebook-normalization

## Purpose
Normalize engineer-written manufacturing/test failure reasons into standardized codebook-backed predictions (pred_code and pred_label), with station-scope enforcement and a confidence value, while ensuring outputs are produced in verifier-visible locations and validated before completion.

## When to Use
Use this when a task provides (or implies) (a) free-text failure reason fields in logs/records and (b) one or more product-specific codebooks, and expects a structured output artifact (often a JSON/CSV) mapping each record (or record segment) to exactly one normalized code (or UNKNOWN) plus label and confidence.

## Procedure
- 0) Gate on harness/tool constraints (decision point).
- If the current instructions say to only invoke a specific tool, or forbid terminal/file editing, or require ending immediately after a tool result: do not run any filesystem commands or multi-step processing. Produce only the minimal allowed response for that phase.
- Otherwise proceed with the steps below.
- 1) Discover the environment inputs and expected output contract (checkpoint).
- Identify where inputs live by listing the working directory and searching for likely log files and codebooks (do not assume filenames or paths).
- Identify the required output path and format from the task statement, repo README, or provided verifier script/config. If not explicitly given, discover the conventional output directory used by the harness (e.g., an output mount) and record the resolved path you will write to.
- 2) Validate inputs before transformation (checkpoint).
- Confirm you can open and parse the logs (CSV/JSON) and codebooks (CSV/JSON/YAML) with the available tools/libraries in the environment.
- Confirm key fields needed for matching exist (at minimum: raw reason text; some notion of product/model; station or test stage). If fields are missing or ambiguous, stop and request clarification or implement a conservative mapping that defaults to UNKNOWN rather than guessing.
- 3) Build a reusable codebook index with station scope (implementation step).
- Parse each codebook into entries with: code, label, optional keywords/examples, and optional station scope list.
- Build a lookup that can return candidate entries for a given record based on product/model context when available.
- Enforce station scope as a hard filter: if an entry declares allowed stations, it is only eligible when the record station matches one of them (normalize station strings consistently).
- 4) Normalize each record (or segment) to exactly one code (decision points).
- Segmentation: only split a record into multiple segments if the required output schema expects per-segment outputs, or if the input clearly contains multiple independent failure reasons separated by reliable delimiters. Otherwise keep a single segment.
- Candidate selection: for each segment, generate candidates from the relevant codebook subset and apply the station-scope filter.
- Matching rule (keep simple and implementable): choose the candidate with strongest textual support from segment text against code/label/keywords/examples using a deterministic similarity method available in the environment (e.g., token overlap plus a basic fuzzy similarity).
- UNKNOWN rule: if no station-compatible candidates exist, or the best match evidence is weak/ambiguous, output pred_code = "UNKNOWN" and pred_label = "".
- Tie handling: if multiple station-compatible candidates are effectively tied, break ties deterministically using stable record context (e.g., record id plus segment index) so reruns are reproducible.
- 5) Emit the required artifact at the verifier-visible path (checkpoint).
- Write outputs to the exact required path discovered in step 1. Do not silently choose a different directory if writing fails.
- If writing fails, inspect and resolve the specific cause (missing mount, permissions, wrong directory) and retry writing to the required path; only change the path if the task/verifier documentation explicitly allows it.
- 6) Final verification anchor: existence + readability + parse (hard stop).
- Re-open the output file from the exact required path and confirm:
- It exists and is readable.
- It parses (e.g., valid JSON/CSV).
- It contains the required columns/keys (at minimum: id/segment identifier, pred_code, pred_label, confidence if required).
- If any check fails, fix and repeat this step before claiming completion.

## Constraints / Pitfalls
- Never assume specific filenames (e.g., test_center_logs.csv) or output locations; always discover them from the environment/task and then verify the final artifact at that exact path.
- Do not implement complex scoring, distribution-level calibration, or untestable heuristics unless the task explicitly requires them; prefer a simple deterministic matcher with a conservative UNKNOWN fallback when evidence is weak or station scope disallows a code.