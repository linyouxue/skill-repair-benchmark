# URL provenance extraction for “shared/posted/sent” questions

Use this when the question requires evidence that a person shared a URL (not merely that the URL exists).

## Procedure

1. Decide the communication sources to scan: Slack messages + thread replies, meeting chat/transcript turns, email-like artifacts.
2. Extract URLs from text and attach provenance: `{url, author_id, artifact_id, timestamp, snippet}`.
3. If the question is restricted to a URL type (e.g., “demo links”), filter by domain/path patterns or by cross-checking against a catalog **after** extraction.
4. De-duplicate by canonical URL form (strip trailing punctuation; optionally normalize tracking params).

## Runnable Python sketch

```python
import re
from urllib.parse import urlsplit, urlunsplit

URL_RE = re.compile(r"https?://[^\s)\]}>\"']+")

def canonicalize(url: str) -> str:
    parts = urlsplit(url)
    # Drop fragment; keep query by default (can be adjusted per dataset)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/'), parts.query, ""))

def extract_url_events(records):
    events = []
    for r in records:
        text = r.get("text") or ""
        for raw in URL_RE.findall(text):
            url = canonicalize(raw.rstrip(".,;:)"]"))
            events.append({
                "url": url,
                "author_id": r.get("user_id") or r.get("speaker_id"),
                "artifact_id": r.get("id") or r.get("meeting_id"),
                "timestamp": r.get("timestamp"),
                "snippet": text[:200],
            })
    return events
```

## Runtime branch

- If **no URLs found** in communications: return an empty result and report “none evidenced in messages/transcripts”; do not backfill from a URL catalog.
- If **too many URLs found**: apply a post-filter (domain allowlist, “demo” path markers, or catalog cross-check) and keep provenance for those retained.

## Verification

For each returned URL, confirm there is at least one event with a non-null `author_id` and a snippet containing the URL.

- If verification fails: expand the communications scope (threads, adjacent meetings, other relevant channels) and re-run extraction; do not infer the sharer from unrelated metadata.
