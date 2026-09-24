### [flink-query] Incorrect event-time stage logic (session/stage detection)
- signal: failure
- pattern: event-time-sessionization-spec-guard
- anchor: (none)
- gap: The implementation likely violated the prompt’s sessionization semantics for “longest stage per job”: it should be a per-job inactivity gap (10 minutes) over SUBMIT events in **event time microseconds**. Common misfires that match the observed output mismatch include: using processing time, using milliseconds instead of microseconds for timestamps/durations (10 minutes mis-scaled), sessionizing on the wrong key (taskId instead of jobId), not filtering to SUBMIT before sessionization, or emitting a max before the job-finish/end-of-stream boundary.
- proposed_change: Add an explicit rule/checklist to the Flink-query guidance: before implementing inactivity-based sessions/stages, restate and verify (1) keyBy(jobId), (2) filter SUBMIT events first, (3) assign event-time timestamps + watermarks using µs and convert 10 minutes to 600,000,000 µs, (4) apply session gap per keyed stream, (5) count SUBMITs per session and take max per job, and (6) only emit when completeness is guaranteed (job-finish signal or final watermark). If this keeps recurring, lift to an L3 reference “event-time sessionization checklist” with unit conversion and boundary conditions.

## WORKFLOW-THEMES

- (none this iteration)
