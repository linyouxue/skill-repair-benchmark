# syzkaller-description-build-loop

## Purpose
Provide a repeatable, environment-aware workflow to compile and (optionally) fully build syzkaller after editing syscall description files and their constants, with preflight checks and bounded fallbacks for common CI/container failures (git safe.directory, Go toolchain/version, restricted network).

## When to Use
Use this when you have changed syzkaller description sources (for example files under sys/*/*.txt and optional *.txt.const) and you need to validate that the descriptions compile (and optionally that the full project builds). Do not use this if you are not in a syzkaller repo or if the task only needs editing without compilation.

## Procedure
- 1) Discover the syzkaller repo root (do not assume a fixed path).
- Check the current directory and a small set of likely candidates provided by the environment/user.
- Confirm repo root by verifying BOTH files exist: `Makefile` and `go.mod`.
- Checkpoint evidence: you can point to a single directory that contains `Makefile` and `go.mod`. If not found, stop and ask for the repo location.
- 2) Preflight environment before running `make`.
- Git safety check (only if git is available):
- Run a minimal git command (for example `git rev-parse --show-toplevel` or `git status`) from the repo root.
- If you see "detected dubious ownership", do not proceed with builds.
- Decision: if you have permission to change global git config, add a safe.directory entry for the discovered repo root; otherwise stop and ask for a repo ownership fix or a safe.directory exception by the operator.
- Go toolchain check:
- Verify `go` is present (`go version`).
- If `go` errors or is missing, stop and request a usable Go installation.
- If `go version` is older than what the repo requires (common signal: `go: errors parsing go.mod` such as unknown block types), do not attempt repeated builds.
- Decision: use a newer preinstalled Go toolchain if available, or stop and request one. Avoid relying on auto-download if network access is restricted.
- Network/toolchain download risk:
- If the environment blocks outbound network, assume Go auto-downloads and module fetches may fail. Prefer a local toolchain and any pre-populated module cache/vendor if present.
- Checkpoint evidence: you have (a) a successful minimal git command or an approved remediation plan, and (b) a Go version that can parse the repo go.mod.
- 3) Choose the smallest build that satisfies the need (decision point).
- Default path: run descriptions-only validation after description edits.
- Only run full `make all` if:
- the task explicitly requires building binaries, OR
- description compilation succeeds but you need to ensure generated code compiles in this environment.
- 4) Execute with bounded monitoring and verify outputs.
- Run `make descriptions` from repo root with a time bound appropriate to the environment (do not let it run unbounded).
- Checkpoint evidence (success): command exits 0 and produces no new errors; optionally confirm generated outputs were updated by inspecting `git diff` (if available).
- If `make descriptions` fails, use one bounded fallback based on the error signature, then re-run only the smallest check (re-run `make descriptions`):
- If git "dubious ownership": apply the safe.directory remediation (if permitted), then re-run.
- If Go tries to download a toolchain and fails (connect refused/timeout): switch to a local/preinstalled Go toolchain (for example by setting `GOTOOLCHAIN=local` if appropriate in your environment) and re-run; if a newer Go is not present locally, stop and request it (do not loop).
- If go.mod parse error with current Go: select a newer Go toolchain present on the system and re-run; if none exists, stop and request a compatible toolchain.
- If the build appears stuck (no output for a long time): capture the last output lines and the active process info, abort the build, and stop with a clear request (for example: network access, module proxy, or prewarmed caches). Do not keep retrying indefinitely.
- Optional full build:
- If required, run `make all` only after `make descriptions` succeeds, using the same time-bound/diagnose rules.
- Verify success by exit code 0; on failure, stop after one bounded fallback based on the first error signature.

## Constraints / Pitfalls
- Do not hard-code repo paths (for example `/opt/syzkaller`) or assume network access for Go toolchain/module downloads; always discover the repo root and preflight Go/network constraints before running `make`.
- Do not apply irreversible global changes (for example `git config --global ... safe.directory`) without confirming the discovered repo path and that you have permission; if permission is unclear, stop and ask rather than guessing.