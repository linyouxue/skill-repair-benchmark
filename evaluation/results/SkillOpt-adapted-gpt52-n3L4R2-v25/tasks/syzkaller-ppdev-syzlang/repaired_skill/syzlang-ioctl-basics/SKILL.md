---
name: syzlang-ioctl-basics
description: Syzkaller syzlang syntax basics for describing ioctl syscalls
---

# Syzlang Ioctl Basics

Syzkaller's description language (syzlang) describes syscalls for fuzzing.
Description files are located at `/opt/syzkaller/sys/linux/*.txt`.

## Syscall Syntax

Basic form:
```
syscall_name(arg1 type1, arg2 type2, ...) return_type
```

Specialized syscalls use `$` suffix:
```
syscall$VARIANT(args...) return_type
```

## Common Type Patterns

| Pattern | Meaning |
|---------|---------|
| `const[VALUE]` | Fixed constant value |
| `flags[flag_set, type]` | Bitfield from flag set |
| `ptr[direction, type]` | Pointer (in, out, inout) |
| `intptr[min:max]` | Integer pointer with range |
| `int8`, `int16`, `int32` | Fixed-size integers |
| `int16be`, `int32be` | Big-endian integers |
| `array[type]` | Variable-length array |
| `array[type, count]` | Fixed-length array |

## Ioctl Patterns

For ioctls with output:
```
ioctl$CMD(fd fd_type, cmd const[CMD], arg ptr[out, int32])
```

For ioctls with input:
```
ioctl$CMD(fd fd_type, cmd const[CMD], arg ptr[in, struct_type])
```

For simple value ioctls:
```
ioctl$CMD(fd fd_type, cmd const[CMD], arg intptr[0:1])
```

For ioctls using ifreq structure (from socket.txt):
```
ioctl$CMD(fd fd_type, cmd const[CMD], arg ptr[in, ifreq_t[flags[flag_set, int16]]])
```

## Struct Definitions

Structs must have typed fields:
```
struct_name {
    field1    type1
    field2    type2
}
```

## Flag Sets

Define reusable flag sets:
```
flag_set_name = FLAG1, FLAG2, FLAG3
```

Then use with `flags[flag_set_name, int16]`.

## Resources

File descriptor resources:
```
resource resource_name[fd]
```

## Read/Write Syscalls

For specialized read/write:
```
read$suffix(fd fd_type, buf ptr[out, buffer_type], count len[buf])
write$suffix(fd fd_type, buf ptr[in, buffer_type], count len[buf])
```

## Tips

1. Check existing files for patterns (e.g., `sys/linux/socket.txt`)
2. Run `make descriptions` after edits to validate syntax
3. Some constants only exist on certain architectures
4. Use `ptr[in, ...]` for input, `ptr[out, ...]` for output


## Worked ppdev modeling procedure

For a Linux parallel-port device, model the ABI from the installed UAPI headers rather than from ioctl numbers alone. Start the description with:

```syzlang
include <linux/ppdev.h>
include <linux/parport.h>

resource fd_ppdev[fd]

syz_open_dev$parport(dev ptr[in, string["/dev/parport#"]], flags flags[open_flags, int32]) fd_ppdev

ppdev_frob_struct {
    mask int8
    val  int8
}
```

`ppdev_frob_struct` must use the widths of the corresponding `unsigned char` fields in `linux/ppdev.h`; do not replace the fields with native-width `int` values. Reuse an existing correctly sized `timeval` type where the header ioctl argument is `struct timeval`.

Define the IEEE1284 mode, phase, and ppdev flag sets using the exact `.const` names exported by the target headers, and use the width required by the header (these sets are normally 32-bit integers):

```syzlang
ieee1284_mode_flags = /* every IEEE1284 mode symbol used by the header */
ieee1284_phase_flags = /* every IEEE1284 phase symbol used by the header */
ppdev_flags = /* every PP_* flag symbol used by the header */

# Use the appropriate set at each call site:
# flags[ieee1284_mode_flags, int32]
# flags[ieee1284_phase_flags, int32]
# flags[ppdev_flags, int32]
```

Do not invent the members or their values: enumerate them from `linux/ppdev.h` and `linux/parport.h`, preserve the exact spellings in the description, and put the same symbols in `dev_ppdev.txt.const` with `arches = amd64, 386`.

### Complete ioctl inventory and direction table

Enumerate exactly the 23 ppdev ioctl declarations present in the target `linux/ppdev.h`. For each one, record its `_IO`, `_IOR`, `_IOW`, or `_IOWR` form, command constant, header argument type, and syzlang signature before writing the description. The mapping rules are:

| Header declaration | Syzlang argument shape |
|---|---|
| `_IO(...)` | no pointed argument; use the fd and `cmd const[...]` with a zero/small `intptr` argument only if required by the local ioctl convention |
| `_IOR(..., scalar)` | `arg ptr[out, int8]`/`int32`/other fixed-width type matching the header |
| `_IOW(..., scalar)` | `arg ptr[in, int8]`/`int32`/other fixed-width type matching the header |
| `_IOR(..., struct)` | `arg ptr[out, header_matched_struct]` |
| `_IOW(..., struct)` | `arg ptr[in, header_matched_struct]` |
| `_IOWR(..., scalar or struct)` | `arg ptr[inout, header_matched_type]` |

For example, the forms for representative ppdev operations are:

```syzlang
ioctl$PPSETMODE(fd fd_ppdev, cmd const[PPSETMODE], arg ptr[in, int32])
ioctl$PPRSTATUS(fd fd_ppdev, cmd const[PPRSTATUS], arg ptr[out, int8])
ioctl$PPFCONTROL(fd fd_ppdev, cmd const[PPFCONTROL], arg ptr[in, ppdev_frob_struct])
ioctl$PPGETFLAGS(fd fd_ppdev, cmd const[PPGETFLAGS], arg ptr[out, int32])
ioctl$PPSETFLAGS(fd fd_ppdev, cmd const[PPSETFLAGS], arg ptr[in, int32])
```

Apply the same process to every remaining ppdev command, including the data/address operations, claim/release/yield/exclusive operations, data-direction and negotiation operations, time operations, mode/phase queries, and all status/control operations. The command names, numeric values, argument widths, and field layouts must match the installed header exactly; a description that merely compiles but omits one of the 23 commands or changes a pointer direction is incorrect. For no-argument `_IO` commands, follow existing syzkaller ioctl conventions in nearby descriptions and do not model a nonexistent pointer.

In `dev_ppdev.txt.const`, include every command and every mode, phase, and ppdev flag referenced by the description, with values extracted from the target headers for both `amd64` and `386`; do not hand-derive values from a guessed ioctl encoding. Finally run:

```bash
cd /opt/syzkaller
make descriptions
make all TARGETOS=linux TARGETARCH=amd64
```

Before accepting the result, compare the description's ioctl inventory against `linux/ppdev.h`, verify every `.const` symbol is defined for both requested architectures, and recheck each `_IO*` direction and fixed-width type against the header.
