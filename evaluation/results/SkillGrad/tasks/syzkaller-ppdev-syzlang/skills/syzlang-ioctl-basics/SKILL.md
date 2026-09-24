---
name: syzlang-ioctl-basics
description: Write syzlang ioctl syscall descriptions with correct pointer directions, resources, constants, and persisted deliverables.
---

# Syzlang Ioctl Basics

## DELIVERABLES FIRST (blocking)

If you have made **zero tool calls** in this run, your **next action** must be: create each required deliverable as a **non-empty stub at the exact requested path**, then pass the `ls -l` + `sed -n` checkpoint.

## Deliverables gate (blocking): write required files immediately, then iterate

1. Extract required deliverables from the prompt (exact paths + filenames).
2. Within the first 1–2 tool calls, create the parent directories and write **minimal non-empty stubs** for every required deliverable (so later build/triage work is never ungradeable).
3. **Blocking checkpoint (before any deeper work):** verify the *on-disk inventory* matches the required paths using `ls -l <paths...>` and preview contents with `sed -n '1,40p' <path>`.
4. If any required file is missing/empty or at the wrong path: **stop** and do only file creation/writes until the checkpoint passes.
5. After running any build step (`make descriptions`, etc.), re-check the same paths still exist and still contain your intended content.

```bash
mkdir -p /path/to/parent
printf '%s\n' '# stub' > /path/to/file.txt
ls -l /path/to/file.txt
sed -n '1,20p' /path/to/file.txt
```

Decision rule: treat deliverable presence as a hard precondition; do not spend iteration budget on build/triage until every required file exists and is non-empty at the exact requested path.

## Quick workflow: mirror a known-good ioctl, then specialize

1. Identify an existing ioctl variant closest to your target (same arg direction/shape).
2. Copy the pattern (syscall name, `$VARIANT` suffix, `cmd const[...]`, `ptr[...]`).
3. Define any new structs/resources before first use.
4. Ensure every `const[...]` used in the `.txt` has a value in a `.const` file or is extractable from headers.
5. Compile with `make descriptions` and fix the first error.

## Ioctl syscall shape

```text
ioctl$VARIANT(fd fd_type, cmd const[CMD], arg ptr[inout, data_type])
```

Decision rule: choose `ptr[in]` vs `ptr[out]` vs `ptr[inout]` based on what the kernel reads/writes; if unsure, start with `inout` only when the ioctl both consumes and produces fields.

## Common type patterns

```text
resource fd_type[fd]
flag_set = FLAG_A, FLAG_B
struct data_type {
\tfield\tint32
}
```

Read references/ioctl-arg-direction.md when you are unsure about `ptr[...]` direction or about representing “value” arguments (`intptr[...]` vs `ptr[...]`). Skip when the ioctl clearly takes a pure input struct or pure output buffer.

## Common Pitfalls

- Picking pointer direction from naming/guessing instead of what the kernel actually reads/writes.
- Using `const[CMD]` in the `.txt` without defining `CMD` for the relevant `arches`.
- Defining a struct/resource after it is first referenced (causes `unknown type`).
- Doing build/triage work before persisting required deliverables (missing/empty output inventory).
