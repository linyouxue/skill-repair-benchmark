# syzlang-ioctl-authoring-with-bounded-validation

## Purpose
Add or modify syzkaller syzlang ioctl descriptions with an environment-gated, checkpointed workflow that (a) edits the correct on-disk description files safely and (b) validates changes using repo tooling when feasible, otherwise stops with a clear blocker and minimal static checks.

## When to Use
Use when a task requires creating or updating syzkaller syzlang definitions related to ioctl (ioctl variants, structs, flags/resources) and you may need to run repo validation/build commands in an environment that can have git trust restrictions, Go toolchain incompatibilities, or limited network access.

## Procedure
- 1) Locate the edit targets (discovery checkpoint)
- Discover the syzkaller descriptions tree in the current workspace; do not assume a fixed path.
- Resolve the exact file path(s) you will edit and confirm they are under the descriptions tree (for example, a sys/* directory containing *.txt description files).
- Evidence: print the resolved repo root (or working directory), the descriptions directory, and the exact target file path(s).
- 2) Environment gate before any build/validator (decision checkpoint)
- Git trust gate:
- If the repo is a git work tree, run a lightweight git command (for example, git status) to detect "dubious ownership"/safe.directory failures.
- If it fails with a safe.directory-style error, prefer a repo-scoped, non-persistent workaround first (for example, using a temporary git config environment) rather than changing global git config; if you cannot proceed without global changes, stop and report the blocker.
- Go/toolchain gate (only if you plan to run Go-based validation or make targets):
- Record current Go version (go version) if available.
- Probe module compatibility from the repo (for example, inspect go.mod for a required go version and features like a tool block) and decide whether the current Go can parse it.
- Decision:
- If required validation/build depends on Go and the local Go cannot parse the module, do not start toolchain bootstrapping unless the task explicitly authorizes it AND the environment policy allows downloads; otherwise stop and report the incompatibility.
- Evidence: capture the git gate result and the Go compatibility decision (proceed vs stop).
- 3) Edit the syzlang with local, strict syntax rules (edit checkpoint)
- Make only the minimal required changes to the resolved target file(s).
- Use pointer types only when the ioctl argument is a pointer (ptr[in|out|inout,...]); use immediate integer types only for non-pointer arguments.
- Define structs with one field per line in "name type" form; no empty names, no stray punctuation.
- Evidence: show a small excerpt of the exact edited lines from the exact target path(s).
- 4) Validate with bounded execution and a single fallback (verify/recover checkpoint)
- Preferred path (only if gates pass and required tools are present):
- Run the narrowest repo-supported description validation/build command required by the task.
- Enforce a hard timeout and capture stdout/stderr to a log file; do not repeatedly poll a long-running process.
- If it fails or times out, print the exit/timeout status and the last N lines of the log, then stop (at most one retry is allowed, and only after fixing a specific gate detected in step 2).
- Bounded fallback (only when the validator/build cannot run due to a confirmed gate like missing tool, Go incompatibility, or blocked network):
- Run minimal static checks focused on common syzlang authoring errors in the edited file(s) (for example, malformed struct field lines, missing ptr direction, obviously malformed ioctl signature punctuation).
- Report the specific blocker that prevented full validation and do not claim the repo validation passed.
- Final grounding (always):
- Re-read the exact edited path(s) and print an excerpt that includes the new/changed definitions.
- Evidence: either (a) validator/build exit code 0 within the timeout, or (b) fallback checks show no findings plus a clearly stated blocker; in both cases, include the final excerpt from the edited file(s).

## Constraints / Pitfalls
- Do not attempt unbounded toolchain installation, dependency fetching, or repo-wide builds; only run build/validation commands after passing the environment gates, with a hard timeout and at most one gated retry.
- Do not change global machine state (global git config, system Go, system packages) unless the task explicitly authorizes it and you have confirmed it is necessary; prefer repo-scoped or temporary settings, otherwise stop and report the blocker.