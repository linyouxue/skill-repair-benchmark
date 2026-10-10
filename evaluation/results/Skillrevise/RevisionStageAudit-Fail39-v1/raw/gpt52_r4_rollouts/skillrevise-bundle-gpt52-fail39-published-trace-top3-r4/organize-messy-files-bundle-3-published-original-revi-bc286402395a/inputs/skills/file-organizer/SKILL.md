# Classified File Mover (Deterministic)

## Purpose
Classify a discovered set of files from a user-specified source directory into a fixed set of pre-named category folders using lightweight content/metadata signals, then move each file exactly once without renaming or modifying content, and produce a verifier-friendly manifest plus post-move checks.

## When to Use
Use when the task requires sorting many existing files into exactly N provided categories (often 4 to 10), with strict rules such as move-only, no renames, no deletions, and a requirement that nothing is left unclassified or outside the category folders.

## Procedure
- 1) Confirm the contract and parameters (no action yet).
- Inputs you must obtain or discover:
- source_dir: the directory containing the files to sort.
- categories: the exact list of allowed destination folder names.
- catch_all_rule: what to do when uncertain (for example, assign to a specific category or an "Unsorted" category only if explicitly allowed).
- Checkpoint: restate the rules in one line: "move-only, no rename, no delete, only within source_dir scope, every file assigned to exactly one category."
- 2) Discover the environment and inventory the exact input set (execution anchor).
- Locate source_dir by listing the current workspace and navigating only after confirming it exists and is readable.
- Enumerate files to be processed (exclude directories unless the user explicitly wants recursive handling).
- Create a draft manifest in a verifier-visible location:
- Place it in source_dir or in the task-specified output root if provided; do not invent a new location.
- Record at minimum: original_path, filename, size_bytes, mtime, planned_category, confidence_note.
- Checkpoint: input_count is known and the draft manifest is readable.
- 3) Build a bounded classifier using discovery-first signals.
- Prefer the lightest available signals in this order:
- Filename and parent folder cues (fast, always available).
- If tools exist, extract small text samples for supported formats (PDF/DOCX/PPTX) using whatever is installed; discover tools first (for example, check for a pdf text extractor or a docx parser) rather than assuming commands.
- If extraction fails, fall back to filename cues only and mark low confidence.
- Decision point: ambiguous or multi-topic files.
- If the task requires exactly one category, choose the best-fit category and add a short reason in confidence_note.
- If a catch-all category is specified for uncertainty, use it and mark as uncertain; otherwise stop and ask for a rule, do not guess new categories.
- 4) Plan the move operations and validate before changing anything irreversible.
- Ensure every file has exactly one planned_category and it is one of categories.
- Ensure the destination category folders exist (create only the specified category folders inside the chosen root; do not create extra structure).
- Dry-run summary:
- counts per category
- list of uncertain files (if any) and which rule placed them
- Checkpoint: user approval when required by the task, otherwise proceed only if rules are already explicit.
- 5) Execute moves with collision safety, then verify (execution anchor).
- Move files (no rename/content edits).
- If a destination path already contains a file with the same name:
- Stop and ask for a collision rule, or move into a task-approved collision subfolder only if explicitly allowed.
- Do not auto-rename unless the contract explicitly permits it.
- Post-move verification:
- Re-enumerate source_dir: confirm none of the inventoried input files remain there.
- Re-enumerate category folders: confirm every inventoried file now exists under exactly one of the category folders.
- Finalize manifest:
- Update each row with final_path and final_category.
- Reload the manifest and validate: row_count == input_count, all categories valid, each original_path appears exactly once.
- If any check fails: stop, report the mismatches (missing, duplicated, still-in-source), and do not claim completion.

## Constraints / Pitfalls
- Never delete, deduplicate, rename, or modify file contents unless the task explicitly allows it; this workflow is move-only by default.
- Do not assume paths (for example, home/Downloads) or tools; discover the actual source_dir and available extractors first, and keep all outputs (manifest, logs) in verifier-visible paths tied to the discovered workspace or task-specified locations.