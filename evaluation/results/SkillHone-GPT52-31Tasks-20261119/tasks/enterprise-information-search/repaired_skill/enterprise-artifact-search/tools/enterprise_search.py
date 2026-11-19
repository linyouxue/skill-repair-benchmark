#!/usr/bin/env python3
"""Enterprise Artifact Search helper (stdlib-only).

This script is intentionally **reusable** and **instance-agnostic**:
- Reads questions from a JSON-like file (default: /root/question.txt)
- Searches enterprise product bundles under <DATA>/products (default: /root/DATA/products)
- Extracts grounded employee IDs and external URLs from artifacts
- Writes /root/answer.json in the required strict JSON shape:

  {
    "q1": {"answer": ["..."], "tokens": "..."},
    "q2": {"answer": ["..."], "tokens": "..."}
  }

Notes
-----
- `answer` is ALWAYS a list (even if one item).
- `tokens` is ALWAYS a string.
- Token values are estimated unless you supply true token counts elsewhere.

Design goals
------------
- Fast: loads only the product bundles that appear relevant to each question.
- Robust: handles common schema variants (Slack events + thread replies, employee
  directory as dict keyed by eid_*, urls list, documents list, meeting transcripts).
- Quiet by default: avoids printing large artifacts (token-efficient).

IMPORTANT: Do NOT hard-code any product names, IDs, URLs, or instance values.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple


DEFAULT_DATA_DIR = Path("/root/DATA")
DEFAULT_PRODUCTS_DIR = DEFAULT_DATA_DIR / "products"
DEFAULT_METADATA_DIR = DEFAULT_DATA_DIR / "metadata"
DEFAULT_QUESTION_PATH = Path("/root/question.txt")
DEFAULT_OUTPUT_PATH = Path("/root/answer.json")


# --- Regex helpers ---

_EID_RE = re.compile(r"\beid_[0-9a-f]{8}\b")
_URL_RE = re.compile(r"https?://[^\s>\)\]\"']+")

# Many datasets in this family use Force-suffixed product names.
_PRODUCT_TOKEN_RE = re.compile(r"\b([A-Z][A-Za-z0-9]+Force)\b")

# "utterranceID" is misspelled in some datasets.
_UTTERANCE_ID_KEYS = ("utterranceID", "utteranceID", "message_id", "id")

# Speaker lines in meeting transcripts often look like: "Jane Doe: ..."
_SPEAKER_LINE_RE = re.compile(r"^([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)+):\s*(.*)$")


def dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def est_tokens_from_text(text: str, *, floor: int = 200) -> str:
    """Pragmatic estimator: ~4 chars/token for English-ish text and JSON.

    Adds a conservative floor to avoid unrealistically tiny values.
    """

    est = int(math.ceil(len(text or "") / 4))
    if est < floor:
        est = floor
    return str(est)


def is_external_url(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    # Common internal archive links in these datasets.
    if "sf-internal.slack.com" in lowered:
        return False
    return True


def extract_urls(text: str) -> List[str]:
    urls: List[str] = []
    for m in _URL_RE.finditer(text or ""):
        url = m.group(0).rstrip(".,;:!?\"")
        urls.append(url)
    return urls


def parse_iso_dt(val: Any) -> Optional[_dt.datetime]:
    if not isinstance(val, str) or not val:
        return None
    # Handle trailing Z.
    s = val.replace("Z", "+00:00")
    try:
        dt = _dt.datetime.fromisoformat(s)
        # Normalize to naive UTC so mixed aware/naive values compare safely.
        if dt.tzinfo is not None:
            dt = dt.astimezone(_dt.timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


# --- Questions parsing ---


def parse_questions(text: str) -> Dict[str, str]:
    """Parse question.txt which is often JSON-like but not strict JSON.

    Supports:
    - strict JSON: {"q1": "...", "q2": "..."}
    - loose JSON-like values without quotes (common in these tasks).
    """

    text = (text or "").strip()
    if not text:
        return {}

    # 1) Try strict JSON first.
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            out: Dict[str, str] = {}
            for k, v in obj.items():
                ks = str(k)
                if not ks.startswith("q"):
                    continue
                out[ks] = str(v)
            return out
    except Exception:
        pass

    # 2) Line-oriented fallback.
    out: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line in ("{", "}"):
            continue
        # Drop trailing commas.
        if line.endswith(","):
            line = line[:-1]
        m = re.match(r'"?(q\d+)"?\s*:\s*(.*)$', line)
        if not m:
            continue
        key = m.group(1)
        val = m.group(2).strip()
        # Remove wrapping quotes if present.
        if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            val = val[1:-1]
        out[key] = val
    return out


# --- Employee directory ---


def load_employee_directory(metadata_dir: Path) -> Tuple[Set[str], Dict[str, List[str]]]:
    """Return (valid_eids, name->eids mapping)."""

    path = metadata_dir / "employee.json"
    if not path.exists():
        return set(), {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set(), {}

    valid: Set[str] = set()
    name_to_eids: Dict[str, List[str]] = {}

    def add(eid: Any, name: Any) -> None:
        if not isinstance(eid, str) or not eid.startswith("eid_"):
            return
        valid.add(eid)
        if isinstance(name, str) and name.strip():
            key = name.strip().lower()
            name_to_eids.setdefault(key, []).append(eid)

    if isinstance(data, dict):
        for k, v in data.items():
            eid: Any = k if isinstance(k, str) and k.startswith("eid_") else None
            name: Any = None
            if isinstance(v, dict):
                eid = eid or v.get("employee_id") or v.get("eid") or v.get("id")
                name = v.get("name") or v.get("full_name")
            add(eid, name)
    elif isinstance(data, list):
        for v in data:
            if not isinstance(v, dict):
                continue
            add(v.get("employee_id") or v.get("eid") or v.get("id"), v.get("name") or v.get("full_name"))

    # De-dupe per-name lists.
    for k, eids in list(name_to_eids.items()):
        name_to_eids[k] = dedupe_preserve_order(eids)

    return valid, name_to_eids


def resolve_people_to_eids(
    people: Iterable[str],
    *,
    valid_eids: Set[str],
    name_to_eids: Dict[str, List[str]],
) -> List[str]:
    out: List[str] = []

    for raw in people:
        if not raw:
            continue
        s = raw.strip()

        # Direct eid.
        if _EID_RE.fullmatch(s):
            if not valid_eids or s in valid_eids:
                out.append(s)
            continue

        # Embedded @eid_... mention.
        m = _EID_RE.search(s)
        if m:
            eid = m.group(0)
            if not valid_eids or eid in valid_eids:
                out.append(eid)
            continue

        # Name -> eid.
        key = s.lstrip("@").strip().lower()
        eids = name_to_eids.get(key, [])
        if not eids:
            continue
        # Prefer unique mapping; otherwise include all and let downstream de-dupe.
        out.extend(eids)

    return dedupe_preserve_order(out)


# --- Slack parsing ---


@dataclass(frozen=True)
class SlackUtterance:
    channel: str
    timestamp: str
    user_id: str
    utterance_id: str
    text: str
    is_reply: bool


def _coerce_str(val: Any) -> str:
    return val if isinstance(val, str) else ""


def _get_utterance_id(user: Dict[str, Any], ev: Dict[str, Any]) -> str:
    for k in _UTTERANCE_ID_KEYS:
        v = user.get(k)
        if isinstance(v, str) and v:
            return v
    v2 = ev.get("id")
    return v2 if isinstance(v2, str) else ""


def iter_slack_utterances(product_data: Any) -> Iterator[SlackUtterance]:
    """Yield Slack-ish utterances across common schema variants.

    Supports:
    - list-of-events: [{Channel:{name}, Message:{User:{...}}, ThreadReplies:[{User:{...}}]}]
    - dict-with-channels: {"channels": [{"name": ..., "messages": [...]}, ...]}
    """

    if not isinstance(product_data, dict):
        return

    slack = product_data.get("slack")

    # Variant 1: list of events.
    if isinstance(slack, list):
        for ev in slack:
            if not isinstance(ev, dict):
                continue
            chan = ev.get("Channel")
            chan_name = ""
            if isinstance(chan, dict):
                chan_name = _coerce_str(chan.get("name"))

            msg = ev.get("Message")
            if isinstance(msg, dict) and isinstance(msg.get("User"), dict):
                user = msg["User"]
                yield SlackUtterance(
                    channel=chan_name,
                    timestamp=_coerce_str(user.get("timestamp")),
                    user_id=_coerce_str(user.get("userId")),
                    utterance_id=_get_utterance_id(user, ev),
                    text=_coerce_str(user.get("text")),
                    is_reply=False,
                )

            replies = ev.get("ThreadReplies")
            if isinstance(replies, list):
                for rep in replies:
                    if not isinstance(rep, dict) or not isinstance(rep.get("User"), dict):
                        continue
                    u = rep["User"]
                    yield SlackUtterance(
                        channel=chan_name,
                        timestamp=_coerce_str(u.get("timestamp")),
                        user_id=_coerce_str(u.get("userId")),
                        utterance_id=_get_utterance_id(u, rep),
                        text=_coerce_str(u.get("text")),
                        is_reply=True,
                    )
        return

    # Variant 2: dict of channels.
    if isinstance(slack, dict):
        channels = slack.get("channels")
        if isinstance(channels, list):
            for ch in channels:
                if not isinstance(ch, dict):
                    continue
                chan_name = _coerce_str(ch.get("name") or ch.get("channel") or ch.get("channel_name"))
                messages = ch.get("messages") or ch.get("Events")
                if not isinstance(messages, list):
                    continue
                for m in messages:
                    if not isinstance(m, dict):
                        continue
                    user = m.get("User")
                    if not isinstance(user, dict):
                        continue
                    yield SlackUtterance(
                        channel=chan_name,
                        timestamp=_coerce_str(user.get("timestamp")),
                        user_id=_coerce_str(user.get("userId") or user.get("id")),
                        utterance_id=_get_utterance_id(user, m),
                        text=_coerce_str(user.get("text")),
                        is_reply=False,
                    )


def is_bot_user(user_id: str) -> bool:
    if not user_id:
        return True
    lowered = user_id.lower()
    return lowered in {"slack_admin_bot", "admin_bot", "bot"} or lowered.endswith("_bot")


# --- Product selection ---


def iter_product_files(products_dir: Path) -> List[Path]:
    return sorted([p for p in products_dir.glob("*.json") if p.is_file()])


def extract_product_mentions(question: str) -> List[str]:
    return dedupe_preserve_order(_PRODUCT_TOKEN_RE.findall(question or ""))


def build_anchor_terms(question: str) -> List[str]:
    """Derive a small set of likely-on-disk anchor terms."""

    q = question or ""
    terms: List[str] = []

    # A few common phrases.
    for phrase in [
        "Market Research Report",
        "competitor",
        "strength",
        "weakness",
        "demo",
        "URL",
        "reviewer",
        "author",
    ]:
        if phrase.lower() in q.lower():
            terms.append(phrase)

    # Capitalized tokens (products/competitors).
    for tok in re.findall(r"\b[A-Z][A-Za-z0-9_.-]+\b", q):
        if tok in {"Find", "IDs", "ID", "URLs", "URL"}:
            continue
        terms.append(tok)

    return dedupe_preserve_order(terms)[:12]


def grep_like_bytes(path: Path, needles: Sequence[str]) -> bool:
    try:
        data = path.read_bytes()
    except Exception:
        return False
    for n in needles:
        if not n:
            continue
        try:
            if n.encode("utf-8") in data:
                return True
        except Exception:
            continue
    return False


def resolve_product_files_for_question(question: str, product_files: Sequence[Path]) -> List[Path]:
    stems = {p.stem.lower(): p for p in product_files}
    mentions = extract_product_mentions(question)
    resolved = [stems[m.lower()] for m in mentions if m.lower() in stems]
    if resolved:
        return resolved

    ql = (question or "").lower()
    for stem, p in stems.items():
        if stem and stem in ql:
            return [p]

    anchors = build_anchor_terms(question)
    candidates = [p for p in product_files if grep_like_bytes(p, anchors)]
    return candidates[:5] if candidates else list(product_files)[:5]


def safe_json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# --- Pattern C: demo URLs ---


def extract_demo_urls(product_data: Dict[str, Any], *, competitor_terms: Set[str]) -> Tuple[List[str], List[str]]:
    urls_out: List[str] = []
    evidence: List[str] = []

    # 1) Structured urls list.
    urls = product_data.get("urls")
    if isinstance(urls, list):
        for entry in urls:
            if not isinstance(entry, dict):
                continue
            url = entry.get("link") or entry.get("url") or entry.get("href")
            if not isinstance(url, str):
                continue
            if not is_external_url(url):
                continue

            blob = " ".join(
                _coerce_str(entry.get(k))
                for k in ("id", "name", "title", "description", "category", "type")
            ).lower()
            looks_demo = "demo" in blob or "demo" in url.lower()
            if not looks_demo:
                continue

            if url not in urls_out:
                urls_out.append(url)
                evidence.append((entry.get("description") or entry.get("title") or str(entry.get("id")) or "")[:240])

    # 2) Slack messages with external demo links.
    for utt in iter_slack_utterances(product_data):
        if is_bot_user(utt.user_id):
            continue
        if not utt.text:
            continue
        if "http" not in utt.text:
            continue

        # Prefer links in competitor context, but allow generic demo shares.
        text_l = utt.text.lower()
        comp_hit = any(t.lower() in text_l for t in competitor_terms) if competitor_terms else False
        demo_hit = "demo" in text_l
        if not (comp_hit or demo_hit):
            continue

        for url in extract_urls(utt.text):
            if not is_external_url(url):
                continue
            if url not in urls_out:
                urls_out.append(url)
                evidence.append(utt.text[:240])

    return urls_out, evidence[:6]


# --- Pattern B: competitor strengths/weakness insights ---


_COMP_NAME_PATTERNS = [
    re.compile(r"reading about ([A-Za-z0-9_.-]+),\s+a competitor product", re.I),
    re.compile(r"about ([A-Za-z0-9_.-]+),\s+a competitor product", re.I),
    re.compile(r"\b([A-Za-z0-9_.-]+),\s+a competitor product", re.I),
]

_INSIGHT_KW = re.compile(
    r"\b(strengths?|weakness(?:es)?|pros|cons|advantage|disadvantage|better|worse|gap|differentiator|"
    r"limitation|limitations|challenge|risk|drawback|opportunity|tradeoff|compare|comparison|vs\.?|"
    r"privacy|data quality|integration|setup cost|learning curve)\b",
    re.I,
)

_FEATURE_KW = re.compile(
    r"\b(offers?|integrates?|integration|supports?|capabilit(?:y|ies)|feature|"
    r"machine learning|real-time|dashboard|analytics|a/b|ab testing|journey mapping)\b",
    re.I,
)

_THANKSISH_RE = re.compile(r"^(thanks|thank you|great point|good point)\b", re.I)


def extract_competitor_terms(product_data: Dict[str, Any]) -> Set[str]:
    terms: Set[str] = set()

    # From slack text patterns.
    for utt in iter_slack_utterances(product_data):
        text = utt.text or ""
        if "competitor" not in text.lower():
            continue
        for pat in _COMP_NAME_PATTERNS:
            m = pat.search(text)
            if m:
                terms.add(m.group(1))

    # From structured urls ids like "<name>_com_demo".
    urls = product_data.get("urls")
    if isinstance(urls, list):
        for entry in urls:
            if not isinstance(entry, dict):
                continue
            eid = entry.get("id")
            if isinstance(eid, str) and eid.endswith("_com_demo"):
                base = eid[: -len("_com_demo")]
                if base:
                    # Keep a simple token; original casing unknown.
                    terms.add(base)

    return {t for t in terms if t}


def is_insight_message(text: str, *, competitor_terms: Set[str]) -> bool:
    if not text:
        return False

    lower = text.lower()

    # Must reference a competitor term if we have any.
    if competitor_terms:
        if not any(t.lower() in lower for t in competitor_terms):
            return False

    # Exclude pure link drops.
    stripped = _URL_RE.sub("", text).strip()
    if len(stripped) < 30 and "http" in lower:
        return False

    # Exclude brief acknowledgements.
    if _THANKSISH_RE.match(stripped):
        return False

    return bool(_INSIGHT_KW.search(text) or (_FEATURE_KW.search(text) and len(stripped) >= 60))


def extract_insight_contributors(
    product_data: Dict[str, Any],
    *,
    valid_eids: Set[str],
    competitor_terms: Set[str],
) -> Tuple[List[str], List[str]]:
    contributors: List[str] = []
    evidence: List[str] = []

    for utt in iter_slack_utterances(product_data):
        if is_bot_user(utt.user_id):
            continue
        if not utt.user_id.startswith("eid_"):
            continue
        if valid_eids and utt.user_id not in valid_eids:
            continue
        if not is_insight_message(utt.text, competitor_terms=competitor_terms):
            continue
        contributors.append(utt.user_id)
        evidence.append(utt.text[:240])

    return dedupe_preserve_order(contributors), evidence[:6]


# --- Pattern A: report authors + key reviewers ---


def iter_documents(product_data: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    docs = product_data.get("documents")
    if isinstance(docs, list):
        for d in docs:
            if isinstance(d, dict):
                yield d


def is_market_research_report(doc: Dict[str, Any]) -> bool:
    t = " ".join(
        str(doc.get(k) or "")
        for k in ("type", "document_type", "title")
    )
    return "market research report" in t.lower()


def choose_best_doc(docs: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not docs:
        return None

    def score(d: Dict[str, Any]) -> Tuple[int, _dt.datetime]:
        ident = str(d.get("id") or d.get("doc_id") or "").lower()
        title = str(d.get("title") or "").lower()
        s = 0
        if "final" in ident or "final" in title:
            s += 30
        if "latest" in ident or "latest" in title:
            s += 20
        if "draft" in ident or "draft" in title:
            s -= 10
        dt = (
            parse_iso_dt(d.get("date"))
            or parse_iso_dt(d.get("updated_at"))
            or parse_iso_dt(d.get("created_at"))
            or _dt.datetime.min
        )
        return s, dt

    return max(docs, key=score)


def normalize_people_field(val: Any) -> List[str]:
    """Normalize a person-ish field to a list of strings (ids or names)."""

    out: List[str] = []

    if val is None:
        return out

    if isinstance(val, str):
        s = val.strip()
        if s:
            out.append(s)
        return out

    if isinstance(val, list):
        for item in val:
            out.extend(normalize_people_field(item))
        return out

    if isinstance(val, dict):
        # Prefer explicit IDs.
        for k in ("employee_id", "eid", "id", "userId"):
            v = val.get(k)
            if isinstance(v, str) and v:
                out.append(v)
                return out
        # Otherwise fall back to name.
        name = val.get("name") or val.get("full_name")
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
        return out

    return out


_FEEDBACK_KW = re.compile(r"\b(add|include|expand|clarif|should|could|suggest|recommend|consider|improve|need to|please)\b", re.I)


def extract_reviewers_from_transcript(
    transcript: str,
    *,
    name_to_eids: Dict[str, List[str]],
    valid_eids: Set[str],
) -> Tuple[List[str], List[str]]:
    reviewers: List[str] = []
    evidence: List[str] = []

    if not transcript:
        return reviewers, evidence

    for line in transcript.splitlines():
        m = _SPEAKER_LINE_RE.match(line.strip())
        if not m:
            continue
        speaker = m.group(1).strip()
        text = (m.group(2) or "").strip()
        if not text:
            continue
        if not _FEEDBACK_KW.search(text):
            continue

        eids = resolve_people_to_eids([speaker], valid_eids=valid_eids, name_to_eids=name_to_eids)
        if not eids:
            continue
        reviewers.extend(eids)
        evidence.append(f"{speaker}: {text}"[:240])

    return dedupe_preserve_order(reviewers), evidence[:6]


def extract_authors_and_reviewers(
    product_data: Dict[str, Any],
    *,
    valid_eids: Set[str],
    name_to_eids: Dict[str, List[str]],
) -> Tuple[List[str], List[str]]:
    evidence: List[str] = []

    mr_docs = [d for d in iter_documents(product_data) if is_market_research_report(d)]
    if not mr_docs:
        return [], evidence

    doc = choose_best_doc(mr_docs)
    if not doc:
        return [], evidence

    doc_id = str(doc.get("id") or doc.get("doc_id") or "")
    doc_title = str(doc.get("title") or "")

    # Author(s)
    author_fields = [
        doc.get("author"),
        doc.get("authors"),
        doc.get("created_by"),
        doc.get("owner"),
    ]
    authors_raw: List[str] = []
    for f in author_fields:
        authors_raw.extend(normalize_people_field(f))
    authors = resolve_people_to_eids(authors_raw, valid_eids=valid_eids, name_to_eids=name_to_eids)

    # Reviewer(s): explicit fields first.
    reviewer_fields = [
        doc.get("reviewers"),
        doc.get("key_reviewers"),
        doc.get("approvers"),
        doc.get("requested_reviewers"),
        doc.get("requestedReviewers"),
    ]
    reviewers_raw: List[str] = []
    for f in reviewer_fields:
        reviewers_raw.extend(normalize_people_field(f))

    # Feedback may be a list of attributed entries.
    fb = doc.get("feedback")
    if isinstance(fb, list):
        for item in fb:
            if isinstance(item, dict):
                reviewers_raw.extend(normalize_people_field(item.get("employee_id") or item.get("userId") or item.get("author") or item.get("reviewer")))

    reviewers = resolve_people_to_eids(reviewers_raw, valid_eids=valid_eids, name_to_eids=name_to_eids)

    # Fallback: meeting transcript speakers who give feedback.
    if not reviewers:
        meetings = product_data.get("meeting_transcripts")
        if isinstance(meetings, list):
            for mt in meetings:
                if not isinstance(mt, dict):
                    continue
                blob = "\n".join(
                    str(mt.get(k) or "")
                    for k in ("title", "transcript", "summary")
                )
                blob_l = blob.lower()
                if "market research report" not in blob_l:
                    continue
                if doc_id and doc_id.lower() not in blob_l and doc_title and doc_title.lower() not in blob_l:
                    # Still allow when only the generic phrase exists.
                    pass

                r, ev = extract_reviewers_from_transcript(
                    str(mt.get("transcript") or ""),
                    name_to_eids=name_to_eids,
                    valid_eids=valid_eids,
                )
                reviewers.extend(r)
                evidence.extend(ev)

    reviewers = dedupe_preserve_order(reviewers)

    # Final: authors first, then reviewers (de-dupe across).
    combined = dedupe_preserve_order([*authors, *reviewers])

    if doc_id or doc_title:
        evidence.insert(0, f"doc: {doc_id or doc_title}"[:240])

    return combined, evidence[:6]


# --- Orchestrator ---


def classify_question(question: str) -> str:
    q = (question or "").lower()

    # Disambiguate when a question contains both “competitor” and “url/demo”.
    # If URLs/demos are explicitly requested, prioritize the URL extractor.
    if "url" in q or "urls" in q or "http" in q or "link" in q or "demo" in q:
        return "demo_urls"

    if "market research report" in q or "reviewer" in q or "reviewers" in q or "author" in q or "authors" in q:
        return "report_reviewers"

    if "strength" in q or "weakness" in q or "competitor" in q or "insight" in q:
        return "competitor_insights"

    return "generic"


def solve_question(
    qtext: str,
    *,
    product_files: Sequence[Path],
    valid_eids: Set[str],
    name_to_eids: Dict[str, List[str]],
) -> Tuple[List[str], List[str]]:
    """Return (answers, evidence_snippets)."""

    qtype = classify_question(qtext)
    targets = resolve_product_files_for_question(qtext, product_files)

    # Load the first relevant product bundle; most questions are scoped to one product.
    for p in targets:
        try:
            data = safe_json_load(p)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue

        competitor_terms = extract_competitor_terms(data)

        if qtype == "demo_urls":
            ans, ev = extract_demo_urls(data, competitor_terms=competitor_terms)
            return ans, ev
        if qtype == "competitor_insights":
            ans, ev = extract_insight_contributors(
                data,
                valid_eids=valid_eids,
                competitor_terms=competitor_terms,
            )
            return ans, ev
        if qtype == "report_reviewers":
            ans, ev = extract_authors_and_reviewers(
                data,
                valid_eids=valid_eids,
                name_to_eids=name_to_eids,
            )
            return ans, ev

        # Generic fallback: try to extract any grounded eids and external urls.
        out: List[str] = []
        ev: List[str] = []
        want_urls = "url" in (qtext or "").lower() or "demo" in (qtext or "").lower()
        for utt in iter_slack_utterances(data):
            if is_bot_user(utt.user_id):
                continue
            if want_urls:
                for url in extract_urls(utt.text):
                    if is_external_url(url):
                        out.append(url)
                        ev.append(utt.text[:240])
            else:
                if utt.user_id.startswith("eid_") and (not valid_eids or utt.user_id in valid_eids):
                    out.append(utt.user_id)
                    ev.append(utt.text[:240])
                for eid in _EID_RE.findall(utt.text or ""):
                    if not valid_eids or eid in valid_eids:
                        out.append(eid)
        return dedupe_preserve_order(out), ev[:6]

    return [], []


def write_answer_json(
    questions: Dict[str, str],
    answers: Dict[str, List[str]],
    evidence_by_q: Dict[str, List[str]],
    out_path: Path,
) -> None:
    out: Dict[str, Dict[str, Any]] = {}

    def q_sort_key(k: str) -> int:
        m = re.match(r"q(\d+)", k)
        return int(m.group(1)) if m else 10**9

    for qk in sorted(questions.keys(), key=q_sort_key):
        ans_list = answers.get(qk, [])
        # Token estimate uses question + small evidence snippets + answer.
        token_basis = (questions.get(qk, "") + "\n" + "\n".join(evidence_by_q.get(qk, [])) + "\n" + json.dumps(ans_list, ensure_ascii=False))
        out[qk] = {"answer": ans_list, "tokens": est_tokens_from_text(token_basis)}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--questions", type=Path, default=DEFAULT_QUESTION_PATH)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    ap.add_argument("--verbose", action="store_true", help="Print brief progress to stderr")
    args = ap.parse_args(argv)

    data_dir = args.data
    products_dir = data_dir / "products"
    metadata_dir = data_dir / "metadata"

    if not args.questions.exists():
        print(f"ERROR: questions file not found: {args.questions}", file=sys.stderr)
        return 2

    raw_q = args.questions.read_text(encoding="utf-8")
    questions = parse_questions(raw_q)
    if not questions:
        print("ERROR: failed to parse questions", file=sys.stderr)
        return 2

    product_files = iter_product_files(products_dir)
    valid_eids, name_to_eids = load_employee_directory(metadata_dir)

    answers: Dict[str, List[str]] = {}
    evidence_by_q: Dict[str, List[str]] = {}

    for qk, qtext in questions.items():
        ans, ev = solve_question(
            qtext,
            product_files=product_files,
            valid_eids=valid_eids,
            name_to_eids=name_to_eids,
        )
        answers[qk] = ans
        evidence_by_q[qk] = ev

    write_answer_json(questions, answers, evidence_by_q, args.output)

    if args.verbose:
        print(f"Wrote {args.output}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
