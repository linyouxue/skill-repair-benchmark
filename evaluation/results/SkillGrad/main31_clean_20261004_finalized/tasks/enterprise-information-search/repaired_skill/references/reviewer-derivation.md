# Reviewer derivation when explicit fields are missing

Use this when the question asks for reviewers/approvers/key reviewers but the primary artifact has no explicit reviewer-like fields.

## Procedure (tie everything to the target artifact)

1. Identify the target artifact’s stable key (doc/report/PR ID, or canonical URL).
2. Collect linked artifacts that can carry review activity: PR reviews, document feedback objects, Slack share messages and their threads, meeting transcripts that reference the doc/report.
3. Extract *candidate reviewers* only from attributable review evidence (feedback authors, thread repliers, transcript speakers who give critique/suggestions).
4. Exclude non-evidence roles: invited participants/attendees, FYI forwards, and people who only acknowledge (“+1”, “thanks”).
5. For each included reviewer, store an evidence pointer: `{artifact_id, location, snippet}`.

## Runnable Python sketch

```python
import re
from collections import defaultdict

ACK_RE = re.compile(r"^(\s)*(thanks|thank you|\+1|sgtm|looks good)\b", re.I)

def substantive(text: str) -> bool:
    if not text:
        return False
    if ACK_RE.search(text.strip()):
        return False
    # Generic “substantive” cue: contains a suggestion/critique marker.
    return bool(re.search(r"\b(should|could|recommend|concern|risk|issue|improve|missing)\b", text, re.I))

def derive_reviewers(doc_key, slack_msgs, transcript_turns, feedback_items):
    evidence = defaultdict(list)

    # Branch A: structured feedback objects exist
    if feedback_items:
        for fb in feedback_items:
            if fb.get("doc_key") != doc_key:
                continue
            uid = fb.get("author_id")
            if uid and substantive(fb.get("text", "")):
                evidence[uid].append((fb.get("id"), "feedback", fb.get("text", "")[:160]))

    # Branch B: use doc-share message threads / transcript turns
    else:
        for m in slack_msgs:
            if m.get("doc_key") != doc_key:
                continue
            if substantive(m.get("text", "")):
                evidence[m.get("user_id")].append((m.get("id"), "slack", m.get("text", "")[:160]))
        for t in transcript_turns:
            if t.get("doc_key") != doc_key:
                continue
            if substantive(t.get("text", "")):
                evidence[t.get("speaker_id")].append((t.get("meeting_id"), "meeting", t.get("text", "")[:160]))

    reviewers = [uid for uid, evs in evidence.items() if evs]
    return reviewers, evidence
```

## Verification (must pass before writing final IDs)

- Check that **every returned reviewer** has **≥1 evidence pointer** and that each pointer’s `doc_key` matches the target artifact.
- If verification fails: **do not broaden** to participants/attendees; instead expand linkage search (find the correct Slack share root, additional meetings, or missing feedback objects) and re-run derivation.
