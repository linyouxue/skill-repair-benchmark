# syzkaller-description-build-loop

## Purpose
Guide the full edit-compile-verify loop for adding or modifying syzkaller syscall descriptions so that both edited sources and freshly generated build artifacts land under the discovered syzkaller root at the exact paths the verifier reads, even when the tree is partially read-only, the Go toolchain is older than go.mod requires, or the default Go module proxy is unreachable.

## When to Use
Trigger when a task asks to add, edit, or regenerate syzkaller syscall descriptions and then prove the build succeeds end-to-end. Applies regardless of which concrete descriptions file is edited, where the syzkaller checkout lives, or which toolchain the host provides.

## Procedure
- Discover and anchor paths: find a directory containing `Makefile`, `sys/linux/`, and `go.mod`; record it as `SYZ_ROOT`. Do not assume any fixed location. Read the `go` directive in `$SYZ_ROOT/go.mod` and record it as `GO_REQ`. The canonical path for all final evidence is `SYZ_ROOT`; nothing else counts as verified.
- Validate preconditions (all must pass before any build command):
- Per-output-dir writability: `mkdir -p "$SYZ_ROOT/bin" "$SYZ_ROOT/sys/linux/gen"` then `test -w "$SYZ_ROOT/bin" && test -w "$SYZ_ROOT/sys/linux/gen" && test -w "$SYZ_ROOT/sys/linux"`. If any fails, stop and report environment_mismatch; do not fall back to an overlay-only build, because the verifier reads `SYZ_ROOT`, not the overlay.
- Optional single bounded recovery when only some output dirs are non-writable: try one of (a) bind-mount or symlink a writable dir onto the missing output path, or (b) invoke `syz-sysgen` with explicit output flags that redirect generation into `SYZ_ROOT`. Re-run the writability probe; if it still fails, stop and report.
- Go toolchain: compare `go version` with `GO_REQ`. If older, install or extract a matching toolchain into a writable dir, prepend its `bin/` to `PATH`, and re-check.
- Module proxy: probe reachability (e.g., `go env GOPROXY` plus a trivial `go mod download -x`). If blocked, `export GOPROXY=https://goproxy.io,direct` and `export GOSUMDB=off`; re-probe once.
- Edit descriptions in `$SYZ_ROOT/sys/linux/`: author or modify `<name>.txt` and the paired `<name>.txt.const`. Define types before first use. Before saving per-arch const entries, grep an existing `.txt.const` in the same tree for the arch-qualifier pattern you intend to use and confirm at least one precedent exists; if none, re-check the grammar rather than proceeding by analogy.
- Record a build timestamp `TS=$(date +%s)` immediately before the build so freshness of generated files can be asserted later.
- Compile descriptions first: `cd "$SYZ_ROOT" && make descriptions`. Expected evidence: exit 0, and new or updated files under `$SYZ_ROOT/sys/linux/gen/`. Only after this passes, run `make all` if the task requires full binaries.
- Verify artifact placement at the canonical path (all must hold):
- `ls "$SYZ_ROOT"/sys/linux/<name>.txt "$SYZ_ROOT"/sys/linux/<name>.txt.const` succeeds.
- `find "$SYZ_ROOT/sys/linux/gen" -newermt "@$TS" -type f | head` is non-empty (generated files are freshly produced at the canonical root, not merely present).
- `grep -r <expected_symbol_from_edit> "$SYZ_ROOT/sys/linux/gen"` (or `"$SYZ_ROOT/executor/syscalls.h"` if the task writes there) returns at least one match.
- If the task implies binary outputs, check `ls "$SYZ_ROOT/bin"` contains artifacts newer than `TS`.
- Recover on failure (bounded, one branch per cause):
- `make descriptions` reports `unknown type` or `defined for none of the arches`: fix type ordering in `.txt` or add the missing arch key in `.txt.const`; re-run only `make descriptions`.
- Error references a network/proxy URL: re-apply the GOPROXY fallback above; retry once.
- Error references `go.mod` version or `unknown block type: tool`: re-apply the toolchain fallback; retry once.
- Permission error on `SYZ_ROOT/bin` or `SYZ_ROOT/sys/linux/gen` mid-build: do not retry under an overlay root; stop and report environment_mismatch.

## Constraints / Pitfalls
- Do not treat success in an overlay or temp directory as success at the canonical path; the verifier reads `SYZ_ROOT`, so freshness of generated files under `SYZ_ROOT/sys/linux/gen/` (and `SYZ_ROOT/bin/` when applicable) is the acceptance signal, not the presence of edited `.txt` sources.
- Do not run any `make` target before per-output-directory writability, Go version, and proxy preconditions are validated.
- Do not hardcode paths, Go versions, or proxy hostnames; discover `SYZ_ROOT`, read `GO_REQ` from `go.mod`, and probe the proxy.
- Do not author per-arch const syntax by analogy without grepping an existing `.txt.const` precedent in the same tree.
- Do not run `make all` before `make descriptions` succeeds.
- Keep every fallback bounded to one retry per cause; if the same precondition fails twice, stop and report the environment constraint rather than looping.