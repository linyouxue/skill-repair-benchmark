# Classify evaluative “insights” vs acknowledgements/logistics

Use this when asked who “provided insights” about strengths/weaknesses and the dataset contains only raw messages/transcript turns.

## Procedure

1. Define the target topic anchor (competitor/product name, feature set, or doc key) and filter to messages/turns that mention it.
2. Classify each candidate message as **evaluative insight** only if it contains a judgment (strength/weakness/pro/con/better/worse) or a concrete comparative claim.
3. Exclude acknowledgements (“thanks”, “+1”), pure questions without an answer, and logistics (“can you share”, scheduling).
4. Keep a snippet per included author.

## Runnable Python sketch

```python
import re

EVAL_RE = re.compile(r"\b(strengths?|weakness(es)?|pros?|cons?|better|worse|advantage|disadvantage)\b", re.I)
ACK_RE  = re.compile(r"^(\s)*(thanks|thank you|\+1|sgtm)\b", re.I)
LOG_RE  = re.compile(r"\b(meeting|schedule|sync|calendar|share the doc|link\?)\b", re.I)

def classify_message(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "empty"
    if ACK_RE.search(t):
        return "ack"
    if LOG_RE.search(t) and not EVAL_RE.search(t):
        return "logistics"
    if EVAL_RE.search(t):
        return "evaluative"
    return "other"

def insight_authors(messages, topic_re: re.Pattern):
    out = {}
    for m in messages:
        text = m.get("text", "")
        if not topic_re.search(text or ""):
            continue
        cls = classify_message(text)
        if cls == "evaluative":
            uid = m.get("user_id")
            out.setdefault(uid, []).append((m.get("id"), text[:180]))
    return out
```

## Runtime branch

- If **too few** messages classify as evaluative, widen the topic filter (aliases, related features) but **keep** the evaluative gate.
- If **too many** messages classify as evaluative, tighten by requiring explicit “strength/weakness/pro/con” terms and manually spot-check borderline cases.

## Verification

Random-sample a few included snippets: each must contain an explicit evaluative claim.

- If a sampled snippet is not evaluative: tighten `EVAL_RE` / add exclusions and re-run; do **not** add an author without a snippet that satisfies the gate.
