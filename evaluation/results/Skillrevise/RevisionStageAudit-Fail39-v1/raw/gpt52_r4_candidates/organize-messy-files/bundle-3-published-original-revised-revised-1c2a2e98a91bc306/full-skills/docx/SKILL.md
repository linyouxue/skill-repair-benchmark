# Verifier-Aligned Bulk Document Triage and Organization

## Purpose
Organize a directory of mixed-format documents into required subject folders while explicitly aligning all actions and audits to the verifier-expected output root, using reversible planning, collision-safe moves, and a final root-level audit that proves the expected filesystem layout.

## When to Use
Use when a task requires sorting many existing files into a specific folder taxonomy and success is judged by the final directory structure at a particular output root (often checked by an automated verifier). Do not use for editing document contents or producing new documents as the primary artifact.

## Procedure
- 1) Extract the explicit contract (stop if ambiguous)
- Parse the task statement for: required output root path (if any), required top-level folder names, whether an "Unsorted" bucket is allowed, and whether extra support files are allowed.
- If the output root is not explicitly stated, discover verifier-visible expectations by searching the workspace for relevant instructions (examples: README, task wrapper scripts, verifier files, config files). Use only what is present locally; do not guess.
- Decision point: If you still cannot determine the output root or required top-level layout, stop and request clarification rather than choosing a plausible subfolder.
- 2) Lock the output root before any irreversible action (execution anchor)
- Select the output root based on the contract in step 1.
- Create a meta directory under that root (for example, <output_root>/._meta/).
- Write <output_root>/._meta/root_lock.txt containing:
- The exact chosen output root path.
- Where it came from (task quote and/or discovered file path).
- A snapshot of the current top-level listing of <output_root>.
- Evidence checkpoint: root_lock.txt exists and is readable at the chosen <output_root>. If you cannot write there, investigate permissions/mounts and do not proceed with moves.
- 3) Pre-move inventory manifest (do not move yet)
- Identify the input set to reorganize (could be the output root itself or a stated input directory).
- Generate a manifest file under <output_root>/._meta/ (for example, manifest.tsv) listing at minimum: relative source path, size, extension.
- Evidence checkpoint: manifest exists, is readable, and total file count is known.
- Strict rule: Do not move/rename any file before the manifest is written and counted.
- 4) Classification strategy and move plan (dry-run first) (execution anchor)
- Discover available extraction tools (examples: pdftotext/pdfinfo, soffice, python). Prefer tools already present; avoid open-ended installation attempts.
- Sample a small set across file types and test extraction quality. If text extraction is weak, fall back to filename/metadata heuristics and increase use of "Unsorted" rather than guessing.
- Produce a move plan file under <output_root>/._meta/move_plan.tsv mapping each manifest item to exactly one destination folder under <output_root> (direct children only, unless the contract explicitly allows nesting).
- Evidence checkpoint: move_plan.tsv exists; planned item count equals manifest count; and all destination paths are under the locked <output_root>.
- 5) Apply moves safely (bounded and deterministic)
- Create required subject folders as direct children of <output_root> using the exact names from the contract.
- Apply the move plan:
- Do not overwrite existing files. On collision, stop and apply a deterministic rename rule (for example, add a short suffix) and record it in the plan and manifest.
- Move each source file at most once; do not duplicate unless the contract explicitly requests copies.
- If any move fails (permissions, missing file, unexpected path), stop and update the audit report with the failure; do not continue blindly.
- 6) Final verifier-aligned root audit (execution anchor, required before completion)
- Verify top-level layout at the exact <output_root>:
- List direct children of <output_root> and assert the required subject folders are present as direct children (not only inside a subfolder).
- Assert no unexpected extra top-level items exist beyond what the contract allows (including whether ._meta is allowed; if not allowed, place meta files where the contract permits or stop for clarification).
- Verify one-to-one file placement:
- Every manifest source appears exactly once somewhere under the subject folders.
- No manifest items remain at the original source location (unless explicitly allowed).
- No duplicates or missing files relative to the manifest.
- Write <output_root>/._meta/audit_report.txt summarizing: counts, missing, duplicates, leftovers, and the top-level listing.
- Only declare completion if the audit assertions pass at the locked <output_root>.

## Constraints / Pitfalls
- Never assume a plausible working subfolder is the verifier root. Do not move anything until the output root is explicitly identified and locked with written evidence under that exact path.
- Do not delete the manifest, move plan, or audit report by default. Keep them under a single meta directory within the allowed output area; remove only if the task explicitly forbids extra artifacts and you have an alternate verifier-allowed way to retain evidence.