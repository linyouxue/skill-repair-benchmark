# Event-Time Sessionization / “Stage” Detection Checklist (Flink/Kafka/Spark)

**Trigger:** The prompt describes *inactivity-based* grouping (session/stage) such as “10-minute gap,” “stage ends after no activity for X,” “session window,” “burst,” or “longest stage per entity,” especially when it mentions **event time**, **watermarks**, or timestamp units.

**Goal:** Implement sessionization that matches the spec exactly: correct keying, correct event subset, correct time units, correct event-time processing, correct *count semantics*, and correct emission/completeness conditions.

## 1) Translate prompt → executable semantics (write it down)

Capture these as concrete statements you can point to in code review:
- **Entity key**: which ID the inactivity gap applies to (e.g., jobId).
- **Event subset**: which events participate in the gap logic (e.g., SUBMIT-only).
- **Timestamp field + units**: which field is “event time” and whether it’s seconds/ms/µs.
- **Gap duration**: convert the inactivity threshold into the same units.
- **Per-session metric**: e.g., “count events in stage.”
- **Cross-session reduction**: e.g., “max stage count per entity.”
- **Count semantics**: count records vs distinct IDs vs distinct tasks (do *not* deduplicate unless explicitly asked).
- **Output timing**: when it is legal to emit final answers (end-of-stream, final watermark, explicit “job finished” event, etc.).

```python
# Runnable semantics capture + unit conversion helpers
from dataclasses import dataclass

@dataclass(frozen=True)
class Semantics:
    key_field: str
    event_type_field: str
    included_types: set[str]
    event_time_unit: str   # "seconds" | "millis" | "micros"
    inactivity_gap_seconds: int
    session_metric: str    # "count_records" | "count_distinct_id" | ...
    per_key_reduce: str    # "max" | "sum" | ...

UNIT_MULT = {"seconds": 1, "millis": 1_000, "micros": 1_000_000}

def gap_in_input_units(s: Semantics) -> int:
    return s.inactivity_gap_seconds * UNIT_MULT[s.event_time_unit]

s = Semantics(
    key_field="entity_id",
    event_type_field="event_type",
    included_types={"TYPE_A"},
    event_time_unit="micros",
    inactivity_gap_seconds=10 * 60,
    session_metric="count_records",
    per_key_reduce="max",
)

assert gap_in_input_units(s) == 600_000_000
```

## 2) Choose the mechanism (branch)

You usually have two families of implementations:

- **Branch A — Window API (session windows):** easiest when the framework supports event-time session windows and you can express the metric per session.
- **Branch B — Keyed state + timers:** use when you need custom stage boundaries, custom completeness rules, or when “session” is defined by a specific event subset and you must handle out-of-order events precisely.

```python
# Runnable branch selector (stand-in)
need_custom_emit = True
need_custom_stage_metric = True

if need_custom_emit or need_custom_stage_metric:
    print("Branch B: keyed state + event-time timers")
else:
    print("Branch A: event-time session windows")
```

## 3) Branch A: session windows (conceptual algorithm)

1. Filter to the event subset **before** session logic.
2. Assign event-time timestamps and watermarks using the **correct units**.
3. Key by the entity ID.
4. Apply session gap = inactivity threshold.
5. Compute per-session metric (e.g., count records), then per-entity max across sessions.

Verification step:
- If results are off by a constant factor or windows look too small/large, re-check **unit conversion** first.
- If results mix entities, re-check **keyBy**.
- If results are too small, check whether you accidentally used `countDistinct`/dedup.

## 4) Branch B: keyed state + event-time timers (conceptual algorithm)

Maintain per-key state:
- last_event_time
- current_stage_count
- max_stage_count

Process each event (after filtering and timestamp assignment):
- If `event_time - last_event_time > gap`: close stage → update max → start new stage.
- Else: increment current stage.
- Update last_event_time.
- Register an event-time timer at `last_event_time + gap` to close an “open” stage when inactivity passes.

Verification step:
- If you emit too early, add/verify a completion boundary (final watermark / explicit finish event). If you cannot guarantee completeness, emit an intermediate result explicitly labeled as such.

## 5) Verification checklist (must pass before finalizing)

```python
# Runnable verification checklist (stand-in assertions)
checks = {
    "filtered_before_session": True,
    "key_is_entity": True,
    "event_time_used": True,
    "gap_units_match": True,
    "two_level_aggregation": True,
    "count_semantics_match": True,
    "emission_is_complete": True,
}

failed = [k for k, v in checks.items() if not v]
if failed:
    raise SystemExit(
        "Sessionization spec mismatch: " + ", ".join(failed)
        + ". Fix in this order: units → filter → key → event-time assignment → aggregation levels → count semantics → emission boundary."
    )

print("Sessionization checks passed")
```

**Corrective action on failure:**
- **gap_units_match fails:** compute the gap in input units explicitly and add a test/constant with the converted value.
- **filtered_before_session fails:** move filtering upstream of timestamps/windowing/timers.
- **key_is_entity fails:** change the key selector to the entity the gap applies to; re-run.
- **event_time_used fails:** switch to event-time timestamps + watermarks; remove processing-time timers.
- **two_level_aggregation fails:** implement “per-session metric then per-key reduce” as two explicit steps.
- **count_semantics_match fails:** replace distinct/dedup counting with record counting unless the prompt explicitly requests deduplication.
- **emission_is_complete fails:** delay emission until a guaranteed completion signal (final watermark/end-of-stream/job-finish event) or document the result as provisional.
