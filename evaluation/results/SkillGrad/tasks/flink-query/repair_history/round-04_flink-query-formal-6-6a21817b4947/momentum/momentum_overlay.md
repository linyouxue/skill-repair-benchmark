### [flink-query] Stateful session/stage logic wrong (incorrect “longest stage task count”)
- signal: failure
- pattern: event-time-sessionization-spec-guard
- anchor: event-time-sessionization
- gap: The implementation likely violated the prompt’s required semantics for stage detection and counting: event-time (not processing-time) sessionization per **jobId** with a **10-minute inactivity gap** on **SUBMIT-only** events, with timestamps in **microseconds** and a correct watermark strategy. It also likely missed the required **two-level aggregation** (count SUBMIT records per stage, then max across stages per job) and/or used the wrong count semantics (e.g., `countDistinct(taskId)` instead of counting SUBMIT records including resubmits), producing deterministically wrong aggregates despite successful execution.
- proposed_change: Strengthen the L2 “Event-Time Sessionization / Stage Detection” operation to explicitly require: (1) filter SUBMIT before sessionization, (2) keyBy(jobId), (3) timestamp unit conversion constant (10 min = 600_000_000 µs) with an inline assertion/comment, (4) session windows or keyed state+event-time timers, (5) compute per-session count → per-job max, and (6) an explicit completeness rule for bounded sources (final watermark/end-of-stream) so results aren’t emitted early. Also add/strengthen a pointer to references/event-time-sessionization.md emphasizing the two-level aggregation + count semantics (no dedup unless asked).

## WORKFLOW-THEMES

- (none this iteration)
