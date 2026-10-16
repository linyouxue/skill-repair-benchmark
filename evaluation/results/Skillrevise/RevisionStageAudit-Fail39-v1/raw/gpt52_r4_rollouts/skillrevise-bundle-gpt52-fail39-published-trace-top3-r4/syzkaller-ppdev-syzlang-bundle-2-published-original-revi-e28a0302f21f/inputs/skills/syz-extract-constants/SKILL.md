# syz-author-ioctl-family-description-and-constants

## Purpose
Create or revise a syzkaller syzlang description for a Linux ioctl-based device so it is complete (all required ioctls), uses correct argument directionality, defines any needed constants (including arch-dependent ones when sizes differ), and passes the verifier-required in-place build/compile checks.

## When to Use
Use this workflow when a task asks you to implement or update a syzlang .txt (and optionally .const) for a Linux device header that defines multiple ioctl commands, and success depends on matching an exact required ioctl set/count and successfully running syzkaller description compilation in a specific repository path that the verifier will check.

## Procedure
- 1) Discover the ground-truth ioctl set (do not assume the count)
- Locate the authoritative header(s) in the current environment (prefer system headers like /usr/include over guessing kernel source locations).
- Extract the ioctl macro names for the target device into a plain list (one per line) and record the expected count.
- Checkpoint: You have an explicit list of required ioctl names and a numeric count derived from the header, not from memory.
- 2) Map each ioctl to a syzlang signature (gate on completeness)
- Open the existing syzlang .txt for the device and list the ioctl declarations currently implemented (names only).
- Diff header-derived names vs .txt names:
- If any header ioctls are missing, add them before doing any build steps.
- If extra ioctls exist that are not in the header list, do not delete blindly; confirm whether they come from another included header or task requirements.
- For each ioctl, determine directionality by inspecting the macro form and argument type:
- _IO: no payload.
- _IOR: output buffer (ptr[out, TYPE]).
- _IOW: input buffer (ptr[in, TYPE]).
- _IOWR: inout buffer (ptr[inout, TYPE]).
- Checkpoint: The .txt contains exactly the required ioctl name set (and matches any task-stated count), with ptr[in]/ptr[out]/ptr[inout] consistent with header semantics.
- 3) Define constants with arch awareness (only where needed)
- Prefer extraction from available headers or compiler preprocessing when possible; otherwise compute values carefully.
- Identify size-sensitive ioctls (any _IOR/_IOW/_IOWR whose third argument depends on sizeof(TYPE), e.g., structs like timeval that differ between 32-bit and 64-bit ABIs).
- For these, require per-arch constants or per-arch size handling; do not assume a single numeric value across all arches.
- Create or update the companion .const file next to the .txt only if the .txt references constants that are not already resolved by syzkaller.
- Checkpoint: Every constant referenced by the .txt is defined for the intended arches, and size-dependent constants are not incorrectly shared across incompatible ABIs.
- 4) Environment preflight for verifier-aligned build, then run the required compile step
- Identify the exact repository/workdir path and command(s) the task/verifier requires (do not substitute different paths or commands).
- Preflight before running anything that writes build artifacts:
- Confirm the required repo path exists.
- Confirm it is writable for build outputs (especially creation of ./bin or other build directories used by the required command).
- If not writable: stop and take one bounded fallback action that enables running the same required command in the same required location (for example: obtain appropriate permissions/escalation, or use the platform-supported mechanism to run the command with write access). Do not silently move the repo or run the build elsewhere unless the task explicitly allows it.
- Run the required syzkaller description build/compile command(s).
- Final checkpoint (verifier alignment):
- Confirm the edited .txt and .const exist and are readable at the exact task-specified paths.
- Confirm the required build command(s) completed successfully (exit code 0) in the required location.

## Constraints / Pitfalls
- Never claim completion without (a) a header-derived ioctl name list/count check against the .txt and (b) a successful in-place verifier-required build/compile run; "looks correct" is not acceptable.
- Do not hard-code environment assumptions (e.g., "no kernel source", fixed repo paths, or a single ioctl numeric value for all arches); always discover headers/tools/permissions first, and treat size-dependent ioctls as potentially arch-specific until validated.