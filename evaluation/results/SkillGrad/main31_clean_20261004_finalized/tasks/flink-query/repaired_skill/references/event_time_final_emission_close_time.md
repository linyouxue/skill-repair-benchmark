# Final-Once Emission with Inactivity + Terminal Events (Close-Time Gating)

Use this when you must output **once per key** (final-only), but the domain definition includes both:
- an **inactivity/session** rule (e.g., "stage ends after X minutes with no TRIGGER"), and
- a **terminal** event or end timestamp (e.g., job FINISH/FAIL) that indicates completion.

## Core idea

A terminal record is *not* a completeness proof for inactivity-defined sessions. The robust pattern is to compute an explicit close time and emit only when the **watermark** has passed it:

`close_time = max(terminal_time, last_trigger_time + gap) + allowed_lateness`

This ensures:
- the last inactivity-defined session can close even if no later trigger arrives, and
- late/out-of-order triggers are still incorporated up to the allowed lateness.

## Runnable reference model (Python)

```python
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class Event:
    key: str
    t: int          # event time in seconds
    kind: str       # "TRIGGER" or "TERMINAL"

@dataclass
class State:
    current: int = 0
    max_stage: int = 0
    last_trigger_t: Optional[int] = None
    terminal_t: Optional[int] = None
    inactivity_timer_t: Optional[int] = None
    emit_timer_t: Optional[int] = None


def compute_close_time(st: State, gap_s: int, allowed_lateness_s: int) -> Optional[int]:
    if st.last_trigger_t is None and st.terminal_t is None:
        return None
    lt_plus_gap = None if st.last_trigger_t is None else st.last_trigger_t + gap_s
    base = max(x for x in [st.terminal_t, lt_plus_gap] if x is not None)
    return base + allowed_lateness_s


def run(events: List[Event], gap_s: int, max_out_of_order_s: int, allowed_lateness_s: int) -> Dict[str, int]:
    # watermark model: wm = max_event_time_seen - max_out_of_order
    states: Dict[str, State] = {}
    out: Dict[str, int] = {}

    max_t = -10**18
    wm = -10**18

    def fire_timers():
        nonlocal wm
        for k, st in list(states.items()):
            # Inactivity closure
            if st.inactivity_timer_t is not None and st.inactivity_timer_t <= wm:
                st.max_stage = max(st.max_stage, st.current)
                st.current = 0
                st.last_trigger_t = None
                st.inactivity_timer_t = None
                # recompute emission timer if terminal already known
                st.emit_timer_t = compute_close_time(st, gap_s, allowed_lateness_s)

            # Final emission
            if st.emit_timer_t is not None and st.emit_timer_t <= wm:
                # if a session is still open, close it before emitting
                st.max_stage = max(st.max_stage, st.current)
                out[k] = st.max_stage
                states.pop(k, None)

    for e in events:
        max_t = max(max_t, e.t)
        wm = max_t - max_out_of_order_s
        fire_timers()

        st = states.setdefault(e.key, State())
        if e.kind == "TRIGGER":
            st.current += 1
            st.last_trigger_t = e.t
            st.inactivity_timer_t = e.t + gap_s  # (re)schedule
            # emission timer might depend on last_trigger + gap
            st.emit_timer_t = compute_close_time(st, gap_s, allowed_lateness_s)

        elif e.kind == "TERMINAL":
            st.terminal_t = e.t
            st.emit_timer_t = compute_close_time(st, gap_s, allowed_lateness_s)

    # end-of-stream flush
    wm = 10**18
    fire_timers()
    return out


if __name__ == "__main__":
    # Case: last stage ends by inactivity before terminal, and no later trigger exists.
    # Arrival order is out-of-order to simulate real streams.
    events = [
        Event("job1", 0, "TRIGGER"),
        Event("job1", 12, "TRIGGER"),
        Event("job1", 5, "TRIGGER"),
        Event("job1", 40, "TERMINAL"),
    ]
    print(run(events, gap_s=10, max_out_of_order_s=10, allowed_lateness_s=5))
```

## Runtime branches (choose one)

### Branch A — You can model stages as session windows over trigger events

Use `EventTimeSessionWindows.withGap(gap)` + `allowedLateness(...)` to compute session sizes, then compute the per-key max. If you still must output only after a terminal event, join/gate the per-key max until the close time and then emit.

### Branch B — You need custom state/timers (multiple event kinds, custom closure)

Maintain per-key state:
- `current_stage_count`, `max_stage_count`, `last_trigger_time`, `terminal_time`
- `inactivity_timer_time` (at `last_trigger + gap`)
- `emit_timer_time` (at `close_time`)

On each trigger: reschedule inactivity timer and recompute `emit_timer_time`.
On terminal: set `terminal_time`, recompute `emit_timer_time`, and **do not emit immediately**.

## Verification

1. **Final-stage counterexample:** build a key where the last stage ends by inactivity and there is no subsequent trigger; verify the result counts that last stage.
2. **Shuffle robustness:** run the same events in multiple arrival orders; output must be identical.

If verification fails:
- If the final stage is missing: ensure an inactivity timer at `last_trigger + gap` exists and closes the current stage on fire.
- If output varies by arrival order: increase watermark delay (bounded out-of-orderness), stop using processing-order “previous event” for gap checks, and recompute timers/state when late triggers arrive.
