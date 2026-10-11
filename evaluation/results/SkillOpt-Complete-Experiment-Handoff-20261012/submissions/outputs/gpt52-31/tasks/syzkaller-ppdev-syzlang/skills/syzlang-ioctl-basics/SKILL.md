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



When translating Linux driver headers (for example `include/uapi/linux/ppdev.h`) into syzlang, first identify which ioctl macro is used:

- `_IOR(...)` returns data from kernel to userspace, so model the argument as `ptr[out, type]`.
- `_IOW(...)` sends data from userspace into the kernel, so model the argument as `ptr[in, type]`.
- `_IOWR(...)` both reads and writes the structure, so model the argument as `ptr[inout, type]`.
- `_IO(...)` has no typed pointer payload. Most such ioctls use `intptr[0]`; if the driver expects a small integer value instead of a pointer, constrain it with a range such as `intptr[0:1]`.

The syzlang ioctl name should normally use a `$`-specialized suffix matching the command name from the header:
```
ioctl$PPCLAIM(fd fd_ppdev, cmd const[PPCLAIM], arg intptr[0])
```
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



Examples of common ioctl argument styles:
```
# _IO: no structured argument
ioctl$PPCLAIM(fd fd_ppdev, cmd const[PPCLAIM], arg intptr[0])

# integer-valued ioctl argument
ioctl$CMD(fd fd_type, cmd const[CMD], arg intptr[0:255])

# _IOR returning a 32-bit value
ioctl$PPGETMODE(fd fd_ppdev, cmd const[PPGETMODE], arg ptr[out, int32])
```
For ioctls using ifreq structure (from socket.txt):
```
ioctl$CMD(fd fd_type, cmd const[CMD], arg ptr[in, ifreq_t[flags[flag_set, int16]]])
```

## Struct Definitions



Kernel structs used by ioctls should be reproduced with matching field widths from the UAPI header. For example:
```
ppdev_frob_struct {
    mask    int32
    val     int32
}
```

Then use the struct with the correct pointer direction:
```
# _IOW: userspace provides values
ioctl$PPFCONTROL(fd fd_ppdev, cmd const[PPFCONTROL], arg ptr[in, ppdev_frob_struct])

# _IOWR: kernel may modify fields
ioctl$CMD(fd fd_ppdev, cmd const[CMD], arg ptr[inout, ppdev_frob_struct])
```
Structs must have typed fields:
```
struct_name {
    field1    type1
    field2    type2
}
```

## Flag Sets



Flag sets are commonly needed for device mode bits and ioctl option fields. Define the symbolic constants once and reuse them with the integer width expected by the kernel structure or ioctl:
```
ieee1284_mode_flags = IEEE1284_MODE_NIBBLE, IEEE1284_MODE_BYTE
ppdev_flags = PP_FASTWRITE, PP_FASTREAD
```

Use them with the correct base type width:
```
flags[ieee1284_mode_flags, int32]
flags[ppdev_flags, int32]
```

Choose the width from the kernel header definitions and struct fields rather than assuming `int16`.
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
