# Product grounding (anti-distractor) for enterprise artifact search

Use this chapter when multiple artifacts share similar titles/types across different products/projects and “first hit wins” is likely.

## Procedure

1. **Collect candidates broadly**: title/type matches plus linked shares/mentions.
2. **Compute grounding signals** for each candidate (at least 4 signals; require 2+ to accept).
3. **Reject distractors**: if another scope is repeatedly named and target scope is not independently supported.
4. **Select best version** among valid candidates (latest/final/date/most-referenced).

```python
from datetime import datetime

def score_grounding(candidate):
    signals = {
        "container": bool(candidate.get("in_target_container")),
        "explicit_mention": bool(candidate.get("mentions_target")),
        "scoped_channel_or_meeting": bool(candidate.get("scoped_channel")),
        "path_convention": bool(candidate.get("scoped_path")),
    }
    score = sum(signals.values())
    return score, signals

def pick_best(valid):
    def key(c):
        if c.get("is_latest"):
            return (3, datetime.max)
        if c.get("is_final"):
            return (2, datetime.max)
        d = c.get("date")
        dt = datetime.fromisoformat(d) if d else datetime.min
        return (1, dt)
    return sorted(valid, key=key, reverse=True)[0]

# Branch: accept vs reject
score, signals = score_grounding(candidate)
if score < 2:
    verdict = "REJECT_DISTRACTOR"
else:
    verdict = "ACCEPT"
```

## Verification

After selecting an artifact, **re-check**: does the chosen artifact contain at least one direct scope marker (explicit mention, scoped channel/meeting, or container metadata)?

- If **fail**: broaden search for additional candidates and re-run grounding; do not proceed to entity extraction.
