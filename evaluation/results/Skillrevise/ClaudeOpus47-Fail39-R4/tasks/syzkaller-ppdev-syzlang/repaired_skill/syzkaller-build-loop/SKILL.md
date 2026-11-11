# syzkaller-description-build-loop

## Purpose
Guide the full edit-compile-verify loop for adding or modifying syzkaller syscall descriptions so that final `.txt` and `.txt.const` artifacts land at the canonical path the verifier reads, even when the syzkaller tree is read-only, the Go toolchain is older than go.mod requires, or the default Go module proxy is unreachable.

## When to Use
Trigger when a task asks to add, edit, or regenerate syzkaller syscall descriptions and then prove the build succeeds. Applies regardless of which concrete descriptions file is edited, where the syzkaller checkout lives, or which Linux distro provides the toolchain.

## Procedure
- Discover: locate the syzkaller root (search for a directory containing `Makefile`, `sys/linux/`, and `go.mod`; do not assume `/opt/syzkaller`). Record it as `SYZ_ROOT`. Read the `go` directive in `$SYZ_ROOT/go.mod` and record the required Go version `GO_REQ`.
- Validate preconditions (all must pass before any build command):
- Writability: `test -w "$SYZ_ROOT"`. If not writable, create an overlay: `WORK=$(mktemp -d)`; `cp -a "$SYZ_ROOT"/. "$WORK"/`; set `BUILD_DIR="$WORK"`. Otherwise `BUILD_DIR="$SYZ_ROOT"`. Remember `SYZ_ROOT` is still the canonical verifier path.
- Go toolchain: compare `go version` with `GO_REQ`. If older, download and extract a matching toolchain to a writable dir and prepend its `bin/` to `PATH`; re-check `go version`.
- Module proxy: run a tiny `go env` plus a probe (`curl -sfI https://proxy.golang.org` or `go mod download -x` on a trivial dep). If unreachable, `export GOPROXY=https://goproxy.io,direct` and `export GOSUMDB=off`; re-probe.
- Edit descriptions inside `$BUILD_DIR/sys/linux/`: author or modify `<name>.txt` and the paired `<name>.txt.const` (same basename plus `.const`). Define types before first use.
- Compile descriptions first: `cd "$BUILD_DIR" && make descriptions`. Expected evidence: exit 0, updated `sys/linux/gen/*.go`, and symbols from your file visible via `grep` in `sys/linux/gen/` or `executor/syscalls.h`. Only after this passes, run `make all` if the task requires a full binary.
- Verify artifact placement at the canonical path:
- If `BUILD_DIR != SYZ_ROOT`, copy edited sources back: `cp "$BUILD_DIR"/sys/linux/<name>.txt "$BUILD_DIR"/sys/linux/<name>.txt.const "$SYZ_ROOT"/sys/linux/`. If the canonical path is read-only, stop and report; do not silently relocate the output.
- Final existence check: `ls "$SYZ_ROOT"/sys/linux/<name>.txt "$SYZ_ROOT"/sys/linux/<name>.txt.const` and `grep -q <expected_symbol> "$BUILD_DIR"/sys/linux/gen/` (or `executor/syscalls.h`). Both must succeed.
- Recover on failure (bounded, one branch each):
- `make descriptions` reports `unknown type` or `defined for none of the arches`: fix the `.txt` ordering or add the missing key to `.txt.const`; re-run only `make descriptions`.
- Build error references a network/proxy URL: re-apply the GOPROXY fallback above; retry once.
- Build error references `go.mod` version or `unknown block type: tool`: re-apply the toolchain fallback; retry once.

## Constraints / Pitfalls
- Do not run any `make` target before preconditions (writability, Go version, proxy) are validated; environment failures mid-build waste the iteration budget.
- Do not treat an overlay build directory as the final output location; the verifier reads `SYZ_ROOT/sys/linux/`, so always perform explicit copy-back and an existence check there.
- Do not hardcode `/opt/syzkaller`, a specific Go version, or `proxy.golang.org`; discover `SYZ_ROOT`, read `GO_REQ` from `go.mod`, and probe the proxy.
- Do not run `make all` before `make descriptions` succeeds; a failing codegen stage makes downstream errors misleading.
- Keep fallbacks bounded to one retry per cause; if the same precondition fails twice, stop and report the environment constraint rather than looping.