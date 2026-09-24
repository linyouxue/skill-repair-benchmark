# syzlang-ioctl-authoring-workflow

## Purpose
Provide an environment-aware, checkpointed procedure to add or modify ioctl-related syzlang descriptions (ioctl variants, structs, flags) with validation or bounded fallback checks, ensuring edits land in the correct syzkaller descriptions tree.

## When to Use
Use when you must author or update syzkaller syzlang files for ioctl syscalls (new ioctl$VARIANT entries, supporting structs/flags/resources) and you need to ensure the changes are syntactically valid and applied to the correct on-disk description files in the current environment (which may be read-only or offline).

## Procedure
- 1) Discover the descriptions tree and the target file(s)
- Locate the syzkaller descriptions directory by discovery (do not assume a fixed path):
- Search for a "sys/linux" directory that contains multiple "*.txt" description files.
- If the task specifies an exact file path, treat it as the target and verify it exists.
- Checkpoint evidence: print the resolved path(s) you will edit (e.g., repo_root and sys/linux path) and confirm the target file is inside that tree.
- 2) Preflight: verify write access and avoid irreversible detours
- For each target file, verify it is writable (or the directory is writable if creating a new file):
- Perform a minimal write test adjacent to the target (create then remove a temporary file), or use an equivalent non-destructive permission check.
- If not writable:
- Do not attempt repo-wide hacks (e.g., editing go.mod, changing toolchains, relocating outputs).
- Stop and report the specific permission constraint and the exact path that is blocked; proceed only if the task provides an alternate writable location that the verifier will accept.
- Checkpoint evidence: write test succeeds (or fails with a captured permission error that triggers the stop/ask branch).
- 3) Author the ioctl description with strict local syntax rules
- Model ioctl lines using consistent patterns:
- cmd is typically const[CMD] (or flags[...] if appropriate).
- arg uses ptr[in|out|inout, type] when it is a pointer; use intptr[...] only for immediate-value style ioctls.
- Define structs with one field per line as: "field_name    field_type" (no leading punctuation, no empty field names).
- Add/update any required resources/flag sets only if the ioctl signature requires them.
- Checkpoint evidence: after edits, show a small excerpt of the changed lines from the target file(s).
- 4) Validate, then ground outputs at the exact edited path(s)
- Preferred validation (only if tools and environment support it):
- Check whether a syzkaller description validator is available in the environment (for example, a built syz-sysgen binary or a repo build target that validates descriptions).
- If available, run the narrowest validator that checks description parsing and require exit code 0.
- Bounded fallback if validator cannot run (offline toolchain mismatch, missing build tools, etc.):
- Do static sanity checks that catch common authoring errors:
- Grep for malformed struct field lines (e.g., lines in structs that do not match "name type" shape, or fields with missing names/types).
- Grep for ioctl lines missing required commas/parentheses, or ptr[...] missing direction.
- Record the exact blocker preventing full validation (e.g., toolchain download refused, version mismatch) and do not claim full validation passed.
- Final grounding check (must always run):
- Verify the exact target file path(s) exist and are readable.
- Print an excerpt (head/sed) from the exact path(s) containing the new/changed definitions.
- Checkpoint evidence: validator exit code 0 OR fallback checks produce no findings; and ls/read excerpt confirms content at the exact path(s).

## Constraints / Pitfalls
- Do not hard-code repository roots, description paths, or validation commands. Always discover paths and gate commands on tool availability and write permissions.
- Do not "fix" validation failures by editing unrelated repo/toolchain files (e.g., go.mod) unless the task explicitly requires it and you have confirmed you can write those files; otherwise, report the blocker and use the bounded static fallback.