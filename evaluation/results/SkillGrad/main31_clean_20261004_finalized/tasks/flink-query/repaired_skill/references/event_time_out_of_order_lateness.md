# Event Time, Out-of-Order Arrival, and Lateness

Use this when implementing Flink (or similar stream processors) event-time logic with watermarks, timers, windows, and final-once emission under possible out-of-order arrival.

## Core idea

A record being *processed* is not evidence that event-time completeness is reached. **Only the watermark** (plus an explicit allowed lateness/grace) gives you a principled “we’ve seen everything up to time T” guarantee.

## Runnable Model: why monotone watermarks break under out-of-order arrival

```python
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class E:
    t: int
    v: int


def run(events: List[E], bounded_delay: int) -> List[Tuple[int, int]]:
    """Toy windowed sum that emits when watermark passes window_end.

    Windows: [0,10), [10,20), ...
    Watermark: max_t_seen - bounded_delay
    """
    max_t = -10**18
    wm = -10**18
    acc = {}
    out = []

    def win_end(t: int) -> int:
        return ((t // 10) + 1) * 10

    def maybe_emit():
        nonlocal out
        for wend in sorted(list(acc.keys())):
            if wend <= wm:
                out.append((wend, acc.pop(wend)))

    for e in events:
        max_t = max(max_t, e.t)
        wm = max_t - bounded_delay
        wend = win_end(e.t)
        acc[wend] = acc.get(wend, 0) + e.v
        maybe_emit()

    wm = 10**18
    maybe_emit()
    return out


if __name__ == "__main__":
    in_order = [E(1, 1), E(2, 1), E(11, 1)]
    out_of_order = [E(11, 1), E(1, 1), E(2, 1)]

    print("bounded_delay=0 (monotone assumption)")
    print(run(in_order, 0), run(out_of_order, 0))

    print("bounded_delay=10")
    print(run(in_order, 10), run(out_of_order, 10))
```

## Runtime Branches (choose one)

### Branch A — Ordering is provable

If you can prove monotone event times *per key after partitioning* (e.g., a source guarantee + stable keying), you may use monotone watermarks and simpler finalization.

### Branch B — Ordering is not provable (common)

Use bounded out-of-orderness watermarks and define:
- `max_out_of_order` (watermark delay)
- `allowed_lateness` (window/session grace)
- output mode: update vs final-once

## Verification

1. **Shuffle stability:** run the same input with a few different arrival orders; the output should be identical.
2. **No processing-order drops:** ensure you never drop an event just because a “terminal” event was seen earlier in processing order.

If verification fails:
- Replace monotone watermarking with bounded out-of-orderness.
- Move “final” emission to `close_time = end_time + allowed_lateness` (or accept updates/retractions).
- Keep per-key state until watermark passes close_time; do not clear state on seeing a terminal record in processing order.
