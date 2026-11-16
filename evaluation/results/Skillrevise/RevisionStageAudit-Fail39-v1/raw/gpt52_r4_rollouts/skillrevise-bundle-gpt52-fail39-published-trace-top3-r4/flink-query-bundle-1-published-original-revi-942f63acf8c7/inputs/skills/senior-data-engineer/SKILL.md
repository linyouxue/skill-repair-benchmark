# Flink Repo Aligned Streaming Job Implementation

## Purpose
Implement or modify a Flink (typically Java) streaming/batch job inside an existing repository so it matches the repository entrypoints, IO utilities, and the verifier/test harness contract, while avoiding brittle assumptions about ordering, filesystem semantics, and event completeness.

## When to Use
Use when a task requires producing verifier-checked artifacts from a Flink job in a provided codebase (Maven/Gradle), especially when inputs/outputs are defined by repo scripts/tests and when mistakes often come from writing outputs to the wrong place, using custom IO/connectors, or assuming event-time ordering and terminal events.

## Procedure
- Step 1: Discover the contract before coding.
- Locate how the job is run and verified: read README, run scripts, CI config, and tests; inspect build files for main class/entrypoints.
- Extract and write down (a) the expected entrypoint and arguments, (b) required output path(s) and filename patterns, and (c) any output format/schema expectations found.
- If output path(s) are not explicitly stated, search for them in tests/verifier code; if still unknown, do not invent a new path. Keep it as unknown and prioritize finding the harness logic.
- Step 2: Ground input schema and semantics with a small sample.
- Identify the authoritative schema source (repo docs, model classes, parsing utilities). Prefer reusing existing parsers and POJOs over re-deriving indices.
- Run a small parse/inspect on a tiny input subset (or use an existing repo tool) to confirm:
- Column-to-field mapping and types (timestamps, ids, event_type enums).
- Whether timestamps are out-of-order in file order (check at least a few hundred rows).
- Whether terminal events needed by your logic (for example FINISH/KILL) actually appear in the provided subset; if not, design emission logic that does not require them.
- Decision point: If ordering is not guaranteed, choose bounded-out-of-orderness watermarks or processing-time timers; do not use monotonic watermarks unless you observed monotonicity in the sample and the task explicitly guarantees it.
- Step 3: Implement using repo-aligned IO and Flink safe primitives.
- Prefer existing repo IO utilities/sources/sinks and Flink supported connectors (FileSource/FileSink, TextOutputFormat equivalents) that work with parallelism and distributed filesystems.
- Implement core logic with explicit checkpoints:
- Keying: key by the entity the contract implies (for example job_id) and document the key choice in code comments.
- State/timers: use keyed state plus event-time or processing-time timers to close inactivity gaps; ensure you handle out-of-order events (late events policy) in a contract-aligned way.
- Emission: do not gate all outputs on optional events unless the contract proves they are always present; if ambiguous, implement a fallback close condition (for example inactivity timer) that still produces required aggregates.
- Avoid adding custom low-level IO (custom gzip readers, local FileOutputStream sinks) unless the repo contract explicitly requires it and you can prove verifier visibility.
- Step 4: Verify against the observable contract before finalizing.
- Build and run using the repo documented command (not an invented one). If a test target exists, run it.
- Output grounding check (exact paths):
- List the exact required output path(s) discovered in Step 1 and confirm non-empty output artifacts exist there (for example part files).
- If writing fails, diagnose mounts/permissions and align with the harness write route; do not silently switch to a different directory.
- Schema check:
- Reload the produced outputs and assert required columns/types/line format match what tests expect (delimiter, header/no header, ordering constraints if stated).
- Only then claim completion.

## Constraints / Pitfalls
- Do not assume event-time monotonicity or in-order arrival. Using monotonic watermarks without evidence is forbidden; default to bounded out-of-orderness or processing-time logic when ordering is unclear.
- Do not introduce custom sources/sinks or write to arbitrary local paths. Use repo-provided IO or Flink-supported file sinks and verify artifacts exist at the exact verifier-checked output path(s) before finishing.