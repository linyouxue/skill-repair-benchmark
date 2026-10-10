# syz-extract-constants

## Purpose
Author and validate syzkaller syzlang constant definitions (`.const` companion files) so that syzlang descriptions compile and the full syzkaller build succeeds in the actual target tree, whether or not kernel source is present.

## When to Use
Use when adding or updating a syzlang `.txt` description that references kernel symbols (ioctls, flags, constants) and the build or verifier requires `make descriptions` and a full syzkaller build to pass. Applies to any syzkaller checkout layout; do not assume a fixed install path.

## Procedure
- Discover the syzkaller tree: locate it via the task description, `which syz-manager`, or by searching for a directory containing `sys/linux/` and a top-level `Makefile` with `descriptions` and `extract` targets. Record this path as `SYZ_DIR`. Do not hard-code `/opt/syzkaller`.
- Validate the build environment: run `test -w "$SYZ_DIR"` and attempt `mkdir -p "$SYZ_DIR/bin"`. If either fails, choose one bounded fallback and record which: (a) fix permissions if allowed (`sudo chown` / `chmod`), or (b) create a writable overlay by copying the tree with `cp -a --no-preserve=ownership "$SYZ_DIR" "$WORK_DIR/syzkaller"` and treat `$WORK_DIR/syzkaller` as the effective `SYZ_DIR` for the remainder of the workflow. Note explicitly in the task log that verification runs in the overlay.
- Validate inputs: confirm the `.txt` description exists under `$SYZ_DIR/sys/<os>/`. For every symbol referenced in the `.txt`, decide whether it will be sourced from kernel headers via `syz-extract` or defined manually. If using `syz-extract`, verify the headers it needs are reachable (`find <kernel_src> -name <header>.h`); if any header is missing, switch that symbol to the manual path.
- Author the `.const` file next to the `.txt` (`<name>.txt.const`):
- First line: `arches = <comma-separated arch list>` covering the architectures the description must support (use the full set for arch-independent symbols such as ioctls).
- One `NAME = <integer>` line per referenced symbol.
- For ioctls, compute values from the kernel encoding: `_IO(t,n) = (t<<8)|n`, `_IOR(t,n,s) = (2<<30)|(s<<16)|(t<<8)|n`, `_IOW(t,n,s) = (1<<30)|(s<<16)|(t<<8)|n`, `_IOWR(t,n,s) = (3<<30)|(s<<16)|(t<<8)|n`.
- Build and verify in `SYZ_DIR` (which may be the overlay):
- Run `make descriptions`. Expected signal: exit 0 and no `is defined for none of the arches` errors.
- Run the full build target required by the task (typically `make all` with `TARGETOS` / `TARGETARCH` as needed). Expected signal: exit 0 and `bin/` populated with `syz-*` binaries.
- Confirm the generated Go files reference the new symbols: `grep -l <SYMBOL> "$SYZ_DIR"/sys/<os>/gen/*.go`.
- Recover: if `make descriptions` reports an undefined symbol, add it to the `.const` file and re-run only that target. If `syz-extract` is attempted and fails due to missing headers, fall back to manual values and document the derivation.

## Constraints / Pitfalls
- Do not hard-code install paths, kernel source paths, or architecture lists; discover them per episode.
- Do not silently relocate outputs. If an overlay is used, state so and ensure the final verification evidence points to the tree the task actually requires; if the task mandates in-place success, prefer fixing permissions over copying.
- Keep the `.const` file minimal: only symbols actually referenced by the `.txt`. Do not import unrelated constants.
- Treat `make extract` as optional: only invoke it when kernel source is available and the required headers resolve; otherwise author values manually.
- Never commit example values from this skill as answers; recompute from the current kernel definitions for the target symbol.