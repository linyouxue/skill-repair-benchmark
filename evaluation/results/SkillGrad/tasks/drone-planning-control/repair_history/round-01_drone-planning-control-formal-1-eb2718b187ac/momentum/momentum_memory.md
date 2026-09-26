### sandbox-path-access | workflow | attempts to read evidence via disallowed absolute paths, preventing diagnosis and edits
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor fails before any domain work because it attempts to access evidence (trace/verifier/skill files) using absolute host paths (e.g., `/home/.../trace.jsonl`) that the sandbox blocks (“path escapes the allowed project root”), and then falls back to a relative filename that is not present in the current working directory. This yields an empty/blocked evidence phase, so no further actions are grounded.
- latest_executor_action: When evidence files cannot be read, stop domain reasoning and recover by operating strictly within the sandbox root: (1) list the current directory and expected artifact directories, (2) use only task-provided relative paths under the allowed root, and (3) if artifacts are located elsewhere, copy/relocate them into the allowed root rather than referencing external absolute paths. Only after trace/verifier artifacts are accessible should any skill diagnosis or edits proceed.
- remedy_log:
  - iter_0 | diagnosis: tool calls to `read_file` failed due to “path escapes the allowed project root” and “file not found”, blocking access to trace/verifier artifacts
            | patch: (none; iteration recorded for future addition of a sandbox-evidence-access rule in L2 workflow)
