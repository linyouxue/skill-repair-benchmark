# SKILL.md

## When to use
Use this skill when you need to add **new syzkaller syzlang descriptions** for a Linux device node that is currently missing coverage, including:
- A new `dev_*.txt` describing resources, openers, structs, ioctls, and flag bitmasks.
- A matching `dev_*.txt.const` defining **ioctl numbers and constant values** referenced by the `.txt`, for specific architectures.

Before editing, gather evidence from:
- The relevant **UAPI headers** (e.g., `include/uapi/linux/...` or the header referenced by the task) that define ioctl macros, structs, enums/flags.
- Existing syzkaller patterns in nearby `sys/linux/dev_*.txt` files (especially for ioctl-heavy devices) to match style and conventions.
- The required build checks (`make descriptions`, full build for at least one arch) to confirm the new descriptions integrate.

## Possible Failure Modes
- **Wrong ioctl directionality**: marking an argument `in` vs `out` incorrectly (common when ioctl macros encode `_IOR/_IOW/_IOWR`).
- **Not covering the full ioctl set**: missing some ioctls because they are conditionally defined, duplicated under aliases, or easy to overlook.
- **Mismatched ioctl numbers**: copying numeric values incorrectly instead of deriving them from the header macros; forgetting that syzkaller wants the *resolved numeric* values in `.const`.
- **Using constants in `.txt` not present in `.const`**: build will fail when constants referenced in syzlang have no definition for the specified arches.
- **Architecture scope mismatch**: forgetting to constrain `.const` to the required arches, or accidentally including arches with differing values.
- **Incorrect struct layout**: wrong field sizes/order (e.g., using `int32` vs `intptr`, padding issues) compared to the kernel header definition.
- **Bad resource/opener wiring**: returning a generic `fd` instead of a device-specific resource; wrong `syz_open_dev` path pattern.
- **Missing required includes**: omitting kernel header includes needed for types/consts used in the syzlang file.
- **Style/namespace collisions**: reusing names already defined elsewhere in syzkaller, or introducing ambiguous constant names.
- **Breaking unrelated descriptions**: editing shared files or global constants beyond the new device description.

## Possible procedures
1. **Scope the interface from headers**
   - Locate the device’s public header(s) defining:
     - ioctl macros (count them and list them)
     - structs used as ioctl payloads
     - flag/enum values (bitmasks, mode flags, etc.)
   - For each ioctl macro, determine:
     - ioctl number macro name
     - payload type (if any)
     - direction: `_IO` (no data), `_IOR` (kernel→user = `out`), `_IOW` (user→kernel = `in`), `_IOWR` (both = `inout`)

2. **Create the syzlang description file (`dev_*.txt`)**
   - Add required `include <...>` lines that correspond to the device’s UAPI headers.
   - Define a **device-specific fd resource** (e.g., `resource fd_device[fd]`) to keep syscalls/ioctls properly typed.
   - Add an **opener** using `syz_open_dev` with the correct path pattern and return type of the new resource.
     - Decision point: if the device naming is indexed (`...#`), prefer syzkaller’s indexed pattern support.
   - Define any structs used by ioctls in syzlang:
     - Mirror field names/order and choose matching syzlang integer sizes.
     - If the kernel struct uses `__u8/__u16/__u32/__u64`, map to `int8/16/32/64` (or `const[...]` where appropriate).
     - Add padding explicitly only if required by alignment and verified against header layout.
   - Describe each ioctl:
     - Use `ioctl$NAME(fd fd_device, cmd const[NAME], arg ...)`
     - Ensure `arg` direction matches `_IOR/_IOW/_IOWR` (e.g., `arg ptr[in, type]`, `ptr[out, type]`, `ptr[inout, type]`)
     - If an ioctl takes no payload, use just `(fd, cmd)` or an explicit `arg intptr` if required by syzkaller patterns for `_IO`.
   - Add **flag definitions** referenced by ioctls as `flags[...]`/`const[...]` patterns as used in syzkaller style.
     - Prefer grouping related flags under a dedicated `flags` type used by the ioctl argument type.

3. **Create the constants file (`dev_*.txt.const`)**
   - Limit to required architectures (only those requested by the task).
   - Add entries for:
     - Every ioctl number used in the `.txt`
     - Every flag/mode constant referenced in the `.txt`
   - Resolve numeric values by:
     - Computing from ioctl macros as defined in the headers (do not guess).
     - If necessary, use a small helper C snippet or rely on compiler preprocessing to print values per-arch.
   - Keep naming consistent between `.txt` and `.const` (exact identifier match).

4. **Integrate and iterate with builds**
   - Run `make descriptions` to validate parsing, constant resolution, and schema correctness.
   - Run a full build for at least one required arch (as specified by the task).
   - Recovery checks:
     - If the build complains about missing consts: search `.txt` for any `const[...]` and ensure each is defined in `.const` for the declared arches.
     - If it complains about unknown types: ensure the appropriate `include` is present or define the missing struct/flags in syzlang.
     - If ioctl signatures fail typechecking: confirm the fd resource type and pointer directions.

## Verification Checklist
- [ ] Two new files exist at the required paths: one `.txt` and one `.txt.const` (no edits to unrelated files unless necessary).
- [ ] The `.txt` contains:
  - [ ] Required `include <...>` lines for the device headers.
  - [ ] A dedicated `resource fd_*[fd]`.
  - [ ] An opener using `syz_open_dev` that returns the dedicated resource.
  - [ ] Definitions for all structs used by ioctls (field order and sizes match headers).
  - [ ] Ioctl descriptions covering the full required count, with **correct `in/out/inout`** pointer directions.
  - [ ] Flag/mode definitions referenced by the ioctls.
- [ ] The `.const` contains:
  - [ ] `arches = ...` exactly as required by the task.
  - [ ] Numeric definitions for every ioctl and constant referenced in the `.txt` (no missing identifiers).
- [ ] No concrete values, names, or artifacts are copied from unrelated retrieved examples; only reusable tactics are applied.
- [ ] Builds pass:
  - [ ] `make descriptions` succeeds with no missing const/type errors.
  - [ ] `make all TARGETOS=linux TARGETARCH=<required>` succeeds.
- [ ] Final sanity: open path pattern and fd resource usage ensure ioctls are only applicable to the intended device fds (prevents type leakage into other subsystems).
