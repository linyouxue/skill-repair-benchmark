# Verifier-Aligned Folder-Only Document Organization

## Purpose
Reorganize a set of existing documents into a required set of top-level subject folders at a task-stated root directory, using discovery-first checks, safe non-overwriting moves, bounded fallbacks for restricted environments, and a final audit that matches what filesystem verifiers typically assert (exact folder set at the exact root, no stray top-level items).

## When to Use
Use when the task requires sorting many files into a specific folder taxonomy and the primary acceptance condition is the final filesystem layout (for example: exactly N named folders at a specified root, with no files left outside them). Do not use when you must generate new content, rely on heavy OCR/parsing, or when the task explicitly allows extra reports/meta artifacts (this procedure defaults to creating none).

## Procedure
- 1) Extract the observable contract (stop if ambiguous)
- Identify: (a) the root directory the verifier will check, (b) the exact required top-level folder names and count, (c) whether any extra top-level items are allowed (usually no), (d) whether an "Unsorted"/"Other" bucket is allowed.
- Decision point: If the root directory is not explicitly stated and cannot be confirmed from local task files, stop and ask for clarification (do not guess a plausible subfolder).
- 2) Preflight root validation (execution anchor; no moves yet)
- Navigate to and list the chosen root directory using discovery (do not assume paths beyond what the task states).
- In a single terminal call (respect single-command tool limits; chain with && if needed), capture:
- Top-level listing of the root (names and whether each is a file/dir).
- Count of candidate input files under the root (or under a stated input subdirectory).
- Evidence checkpoint: You can read the root listing and it matches the task intent (this is the directory you are expected to modify). If permissions/mounts prevent reading or writing, stop and resolve that before proceeding.
- 3) Plan folder set and safety rules (no extra artifacts)
- Ensure the required subject folders exist as direct children of the root (create missing ones).
- Define collision policy before moving anything:
- Never overwrite.
- If a destination filename already exists, apply a deterministic rename (for example: append "_dup1", "_dup2", etc.) and continue.
- Strict rule: Do not create any additional top-level folders or files beyond the required subject folders unless the task explicitly allows it.
- 4) Classify with environment-supported methods (bounded fallback)
- Prefer no-install classification:
- Use filenames, extensions, and simple metadata (for example, `file`, `stat`, directory names) first.
- If text extraction tools are already present, you may sample a few files to improve classification, but do not require installs.
- Fallback branch (bounded):
- If you attempted to use a tool and it fails (missing tool, PEP668 blocks pip, interface errors), stop trying to install packages and revert to filename/metadata-based classification.
- If classification remains ambiguous and an "Unsorted"/"Other" bucket is allowed, place ambiguous items there. If it is not allowed, stop and request clarification rather than guessing.
- 5) Execute moves deterministically and safely
- Move files into exactly one required subject folder each.
- After moving a batch, re-check that:
- Sources are gone from their previous location (unless explicitly allowed).
- No file was overwritten; any collisions followed the deterministic rename rule.
- If any move fails (missing file, permission denied, unexpected path), stop immediately and re-validate assumptions about the root and input set before continuing.
- 6) Final verifier-aligned audit at the exact root (execution anchor; required before completion)
- Run a final single-command audit (chain with && if needed) that verifies:
- The root contains exactly the required subject folders as direct children (names and count match).
- There are zero loose files at the root (and no extra top-level folders), unless explicitly allowed.
- All documents are located under one of the required subject folders (and, if applicable, the allowed catch-all folder).
- Only declare completion if all final audit conditions pass at the task-stated root directory. If they do not pass, do not guess; fix the specific discrepancy and re-run the audit.

## Constraints / Pitfalls
- Do not create meta folders, manifests, reports, or hidden directories by default; many verifiers expect only the required subject folders at the root and nothing else.
- Do not assume you can install tools or run multi-command tool calls; treat installs as disallowed unless explicitly permitted, and always structure terminal usage as single-command calls (or a single chained command) to match tool interface constraints.