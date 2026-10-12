# Timer-Driven Inactivity Sessionization (Event Time)

Use this when the problem definition says a session/stage **ends after a gap of inactivity** (no triggering events for X minutes). A pure “gap between consecutive events” check cannot close the final session because it only triggers when another event arrives.

## Goal

Maintain per-key session state driven by **event time + watermarks**:
- On each triggering event: update counters and (re)schedule an inactivity timer at `last_event_time + gap`.
- When the inactivity timer fires: close the session and reset.
- On a terminal condition (if the domain has one): force-close any open session and emit.

## Reference Algorithm (runnable Python model)

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

@dataclass
class Event:
    key: str
    event_time: int   # seconds since epoch in this toy model
    kind: str         # e.g., "TRIGGER" or "TERMINAL" or other

@dataclass
class State:
    current_count: int = 0
    max_count: int = 0
    last_trigger_time: Optional[int] = None
    inactivity_timer_time: Optional[int] = None


def process_events(events: List[Event], gap_s: int) -> Dict[str, int]:
    """Toy model of event-time inactivity sessionization.

    Processing is in *arrival order* to simulate out-of-order input. "Watermark"
    advances only up to (max_event_time_seen - allowed_out_of_order).
    """
    allowed_out_of_order_s = gap_s  # choose a bound; in Flink, this is your watermark delay
    states: Dict[str, State] = {}
    outputs: Dict[str, int] = {}

    max_event_time_seen = -10**18
    watermark = -10**18

    def maybe_fire_inactivity_timers():
        nonlocal watermark
        # Fire timers whose timestamp is <= watermark
        for k, st in list(states.items()):
            if st.inactivity_timer_time is not None and st.inactivity_timer_time <= watermark:
                # close current session
                st.max_count = max(st.max_count, st.current_count)
                st.current_count = 0
                st.last_trigger_time = None
                st.inactivity_timer_time = None

    for e in events:
        max_event_time_seen = max(max_event_time_seen, e.event_time)
        watermark = max_event_time_seen - allowed_out_of_order_s
        maybe_fire_inactivity_timers()

        st = states.setdefault(e.key, State())

        if e.kind == "TRIGGER":
            # Update session
            st.current_count += 1
            st.last_trigger_time = e.event_time
            # (Re)schedule inactivity timer at last_trigger_time + gap
            st.inactivity_timer_time = e.event_time + gap_s

        elif e.kind == "TERMINAL":
            # Force-close on terminal
            st.max_count = max(st.max_count, st.current_count)
            outputs[e.key] = st.max_count
            # Cleanup
            states.pop(e.key, None)

        else:
            # Non-trigger events do not affect session boundaries.
            pass

    # End-of-stream: advance watermark to infinity to flush timers in this model
    watermark = 10**18
    maybe_fire_inactivity_timers()

    # Note: without a terminal event, you would emit from a watermark-based close condition.
    return outputs


if __name__ == "__main__":
    gap = 10
    # Out-of-order arrival: trigger at t=5 arrives after trigger at t=12
    sample = [
        Event("jobA", 0, "TRIGGER"),
        Event("jobA", 12, "TRIGGER"),
        Event("jobA", 5, "TRIGGER"),
        Event("jobA", 30, "TERMINAL"),
    ]
    print(process_events(sample, gap_s=gap))
```

## Runtime Branches (implementation choices)

### Branch A — Use Flink Event-Time Session Windows

Use this when the metric can be computed from trigger events alone and you can tolerate window updates/retractions under lateness.

- Trigger: “I can express the problem as sessions over trigger events.”
- Approach: `keyBy(key).window(EventTimeSessionWindows.withGap(gap)).allowedLateness(...).aggregate(...)`.

### Branch B — Use a `KeyedProcessFunction` / `KeyedCoProcessFunction` with Timers

Use this when you must combine multiple event kinds (e.g., triggers + terminal events) or need custom per-session state.

- Trigger: “I need terminal-event gating, side outputs, or custom closure state.”
- Approach: maintain `ValueState` for counters and `ValueState` for the scheduled timer timestamp; on each trigger, delete old timer (if present) and register new timer at `last_trigger + gap`.

## Verification (must pass before finalizing)

1. **Final-session closure check:** Construct a case where the last session has triggers but **no subsequent trigger** after the inactivity gap; verify the implementation still closes that session (via timer firing or forced close) and the metric is non-zero.
2. **Out-of-order robustness check:** Randomly shuffle arrival order of events (keeping event_time values) and confirm output is stable under that shuffle.

If verification fails:
- If final-session closure fails: add/reschedule an event-time inactivity timer at `last_trigger_time + gap` and force-close on terminal.
- If results vary under shuffle: replace monotonic watermarks with bounded out-of-orderness, stop using “previous processed record” to infer event-time gaps, and ensure timer rescheduling handles late trigger updates.
