---
name: syzlang-ioctl-basics
description: Describe Linux ioctl interfaces in syzkaller syzlang with correct directions, ABI-faithful argument types, and interface-coverage checks.
---

# Plan Before You Write

## Enumerate the interface, then reconcile counts

1. Enumerate the full interface from the named UAPI header: list every ioctl macro/symbol to describe, including ones tagged `OBSOLETE`/`DEPRECATED`.
2. Reconcile this list against any explicit requirement like “N total”; treat the header list as source-of-truth unless the prompt allows omissions.
3. After writing the `.txt`, checklist/diff: each header macro name should map to exactly one `ioctl$...` line, then re-count.

Read references/ioctl-coverage-reconcile.md when the task names a UAPI header as the source of truth and/or states an explicit total (e.g., “N ioctls total”). Skip when you are only editing a single existing ioctl entry.

# Ioctl Shapes in Syzlang

## Basic syscall syntax

```txt
ioctl$VARIANT(fd fd_type, cmd const[CMD_CONST], arg ptr[inout, some_type]) int32
```

## Direction: map `_IO*` macros to `ptr[...]`

- `_IOR(...)`: kernel writes to user → `ptr[out, ...]`
- `_IOW(...)`: user writes to kernel → `ptr[in, ...]`
- `_IOWR(...)`: both ways → `ptr[inout, ...]`

Decision rule: If the header uses `_IOR/_IOW/_IOWR`, treat that as authoritative unless the kernel implementation clearly contradicts it.

## ABI type fidelity: map C types conservatively

When the header’s `_IO*` type argument is a C scalar type (`int`, `unsigned int`, etc.), avoid fixed-width narrowing unless the ABI contract is explicit.

```txt
# Default “C int-sized” modeling:
ioctl$X(fd fd_type, cmd const[CMD], arg ptr[out, intptr]) int32

# Fixed-width only when verified ABI-stable:
ioctl$Y(fd fd_type, cmd const[CMD], arg ptr[in, int32]) int32
```

Decision rule: Default `int`/`unsigned int` to `intptr` (by value) or `ptr[in/out, intptr]` (by pointer). Use `int32/uint32` only when you can justify width/signedness across the declared arches.

Read references/ioctl-abi-type-mapping.md when the ioctl macro’s type argument is a C scalar (`int`, `unsigned int`, `long`, pointers) and you are unsure how to represent it in syzlang. Skip when the header uses a named struct type you can model directly.

## Structs and flags (quick patterns)

```txt
my_struct {
	field1	int32
	field2	flags[my_flags, intptr]
}

my_flags = FLAG_A, FLAG_B
```

# Common Pitfalls

- Treating “obsolete/deprecated” header symbols as safe to omit without checking an explicit “N total” requirement.
- Inferring ioctl direction from names/comments instead of `_IOR/_IOW/_IOWR` (or forgetting `inout` for `_IOWR`).
- Narrowing `int`/`unsigned int` to `int32` without verifying width/signedness across target architectures.
