#!/usr/bin/env python3
"""Generic structural explorer for an enterprise artifact dataset.

This helper is intentionally content-agnostic. It is used by the
`enterprise-artifact-search` skill's subagent to get a lightweight view
of a dataset root such as /root/DATA without loading large product
bundles into the main agent's context.

It does NOT:
  * know about any particular product, employee, URL, or expected answer;
  * decide what the "right" product or report is;
  * write any answer file.

It DOES:
  * list the dataset tree at a shallow depth;
  * list `metadata/` and `products/` contents when present;
  * print the top-level keys of a selected product bundle;
  * for each listed field, report its type, length (if applicable), and
    a very small sample preview;
  * optionally run case-insensitive keyword scans and report counts +
    tiny snippets, with no per-field value dumps.

Usage:
    python3 explore_dataset.py --root /root/DATA
    python3 explore_dataset.py --root /root/DATA --product <ProductName> --keys
    python3 explore_dataset.py --root /root/DATA --product <ProductName> \\
        --scan "<keyword1>" "<keyword2>"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Iterable


SNIPPET_LEN = 140
PREVIEW_ITEMS = 2


def _safe_listdir(path: str) -> list[str]:
    try:
        return sorted(os.listdir(path))
    except OSError as exc:
        print(f"! cannot list {path}: {exc}", file=sys.stderr)
        return []


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _preview(value: Any) -> str:
    try:
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)[:SNIPPET_LEN]
        return str(value)[:SNIPPET_LEN]
    except Exception:
        return "<unprintable>"


def print_tree(root: str) -> None:
    print(f"# dataset root: {root}")
    if not os.path.isdir(root):
        print(f"! not a directory: {root}")
        return
    for name in _safe_listdir(root):
        full = os.path.join(root, name)
        if os.path.isdir(full):
            children = _safe_listdir(full)
            print(f"  {name}/   ({len(children)} entries)")
            for child in children[:20]:
                print(f"    - {child}")
            if len(children) > 20:
                print(f"    ... (+{len(children) - 20} more)")
        else:
            try:
                size = os.path.getsize(full)
            except OSError:
                size = -1
            print(f"  {name}   ({size} bytes)")


def print_product_keys(root: str, product: str) -> dict | None:
    path = os.path.join(root, "products", f"{product}.json")
    if not os.path.isfile(path):
        print(f"! no product bundle at {path}")
        return None
    data = _load_json(path)
    if not isinstance(data, dict):
        print(f"! product bundle is not a JSON object: {type(data).__name__}")
        return None
    print(f"# product bundle: {path}")
    for key, value in data.items():
        if isinstance(value, list):
            print(f"  - {key}: list(len={len(value)})")
            for item in value[:PREVIEW_ITEMS]:
                if isinstance(item, dict):
                    sub_keys = list(item.keys())
                    print(f"      item keys: {sub_keys}")
                else:
                    print(f"      item: {_preview(item)}")
        elif isinstance(value, dict):
            print(f"  - {key}: dict(keys={list(value.keys())})")
        else:
            print(f"  - {key}: {type(value).__name__} = {_preview(value)}")
    return data


def _iter_strings(obj: Any) -> Iterable[tuple[str, str]]:
    """Yield (path, string) pairs from a nested structure, depth-first."""
    stack: list[tuple[str, Any]] = [("$", obj)]
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                stack.append((f"{path}.{key}", value))
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                stack.append((f"{path}[{idx}]", value))
        elif isinstance(node, str):
            yield path, node


def scan_keywords(data: Any, keywords: list[str]) -> None:
    if not keywords:
        return
    needles = [k.lower() for k in keywords]
    counts = {k: 0 for k in keywords}
    samples: dict[str, list[tuple[str, str]]] = {k: [] for k in keywords}
    for path, text in _iter_strings(data):
        low = text.lower()
        for k, needle in zip(keywords, needles):
            if needle in low:
                counts[k] += 1
                if len(samples[k]) < 3:
                    idx = low.find(needle)
                    start = max(0, idx - 40)
                    end = min(len(text), idx + len(needle) + 40)
                    samples[k].append((path, text[start:end]))
    print("# keyword scan")
    for k in keywords:
        print(f"  [{k}] hits={counts[k]}")
        for path, snippet in samples[k]:
            snippet = snippet.replace("\n", " ")
            print(f"    @ {path}: {snippet!r}")


def _collect_user_ids(obj: Any) -> list[str]:
    """Collect candidate user-like IDs from a nested chat structure.

    Matches typical fields: userId / user_id / author / created_by / owner.
    Returns IDs in first-seen order, de-duplicated.
    """
    seen: list[str] = []
    seen_set: set[str] = set()
    user_keys = {"userid", "user_id", "author", "created_by", "owner"}
    stack: list[Any] = [obj]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(k, str) and k.lower() in user_keys and isinstance(v, str):
                    if v not in seen_set:
                        seen.append(v)
                        seen_set.add(v)
                else:
                    stack.append(v)
        elif isinstance(node, list):
            for v in node:
                stack.append(v)
    return seen


def print_chat_thread_authors(data: Any, channel_substr: str | None = None) -> None:
    """Walk slack-like messages and print per-message authors and thread authors.

    Useful for "who provided insights" style questions. The subagent should
    then open the specific messages to confirm the content is substantive.
    """
    if not isinstance(data, dict):
        return
    messages: list[Any] = []
    for key in ("slack", "slack_messages", "chat", "chat_messages", "messages"):
        v = data.get(key)
        if isinstance(v, list):
            messages = v
            break
    if not messages:
        print("# no chat-like list found on this bundle")
        return
    print(f"# chat thread authors (channel_substr={channel_substr!r})")
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            continue
        channel = ""
        ch = msg.get("Channel") or msg.get("channel")
        if isinstance(ch, dict):
            channel = str(ch.get("name") or ch.get("channel") or "")
        elif isinstance(ch, str):
            channel = ch
        if channel_substr and channel_substr.lower() not in channel.lower():
            continue
        top_ids = _collect_user_ids(msg.get("Message") or msg.get("message") or msg)
        reply_ids = _collect_user_ids(
            msg.get("ThreadReplies")
            or msg.get("thread_replies")
            or msg.get("replies")
            or []
        )
        print(f"  [{i}] channel={channel!r} top_authors={top_ids} thread_authors={reply_ids}")


def _msg_fields(msg: dict) -> tuple[str, str, str, str, list]:
    """Return (channel_name, user_id, timestamp, text, replies) for a chat message.

    Tries the common field shapes used by enterprise slack-like exports.
    """
    ch = msg.get("Channel") or msg.get("channel") or {}
    if isinstance(ch, dict):
        channel = str(ch.get("name") or ch.get("channel") or "")
    else:
        channel = str(ch)
    body = msg.get("Message") or msg.get("message") or msg
    user_obj: Any = {}
    if isinstance(body, dict):
        user_obj = body.get("User") or body.get("user") or body
    if not isinstance(user_obj, dict):
        user_obj = {}
    user_id = str(
        user_obj.get("userId")
        or user_obj.get("user_id")
        or user_obj.get("author")
        or ""
    )
    timestamp = str(
        user_obj.get("timestamp")
        or user_obj.get("ts")
        or (msg.get("timestamp") if isinstance(msg, dict) else "")
        or ""
    )
    text = ""
    if isinstance(user_obj, dict):
        text = str(user_obj.get("text") or user_obj.get("Text") or "")
    if not text and isinstance(body, dict):
        text = str(body.get("text") or body.get("Text") or "")
    replies = msg.get("ThreadReplies") or msg.get("thread_replies") or msg.get("replies") or []
    if not isinstance(replies, list):
        replies = []
    return channel, user_id, timestamp, text, replies


def print_flat_thread(
    data: Any,
    channel: str,
    around: str | None = None,
    keywords: list[str] | None = None,
) -> None:
    """Print sibling top-level messages in `channel` ordered by timestamp.

    Many enterprise chat exports in this family store conversations as a
    flat list of top-level messages even when the natural structure is a
    thread: the "replies" to a share/OP arrive as separate top-level
    messages in the same channel, and `ThreadReplies` is often empty.

    `around` (optional) is an ISO-8601 prefix; messages with timestamps
    >= `around` are shown first, up to a small cap. `keywords` (optional)
    highlights hits so the subagent can quickly spot competitor/topic
    discussions. This helper does NOT decide who is a reviewer or insight
    provider — the subagent still inspects the printed turns for
    substantive content.
    """
    if not isinstance(data, dict):
        return
    messages: list[Any] = []
    for key in ("slack", "slack_messages", "chat", "chat_messages", "messages"):
        v = data.get(key)
        if isinstance(v, list):
            messages = v
            break
    if not messages:
        print("# no chat-like list found on this bundle")
        return
    rows: list[tuple[str, str, str, list]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        ch, user, ts, text, replies = _msg_fields(m)
        if channel and channel.lower() not in ch.lower():
            continue
        rows.append((ts, user, text, replies))
    rows.sort(key=lambda r: r[0])
    needles = [k.lower() for k in (keywords or []) if k]
    print(
        f"# flat thread in channel~{channel!r} around={around!r} "
        f"keywords={keywords or []} ({len(rows)} messages)"
    )
    start_idx = 0
    if around:
        for i, (ts, *_rest) in enumerate(rows):
            if ts >= around:
                start_idx = i
                break
    for ts, user, text, replies in rows[start_idx : start_idx + 80]:
        hit = ""
        if needles:
            low = text.lower()
            if any(n in low for n in needles):
                hit = " <<HIT>>"
        snippet = (text or "").replace("\n", " ")[:220]
        print(f"  {ts} [{user}] replies={len(replies)}{hit}: {snippet}")


def print_feedback_bullets(data: Any, doc_substr: str) -> None:
    """Print each document's feedback-like field as a list of bullets.

    The reviewer set for a version is bounded by the number of bullets in
    that version's feedback list (Step 6 Tier 1 of the Skill). Printing
    the bullets per version makes the upper bound explicit and lets the
    subagent check that single-anchor questions use only the chosen
    version's feedback.
    """
    if not isinstance(data, dict):
        return
    docs = data.get("documents") or data.get("docs") or []
    if not isinstance(docs, list):
        print("# no documents list on this bundle")
        return
    sub = (doc_substr or "").lower()
    feedback_keys = ("feedback", "feedback_items", "comments", "review_comments")
    printed = 0
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        did = str(doc.get("id") or "")
        if sub and sub not in did.lower():
            continue
        fb: Any = None
        fb_key = None
        for k in feedback_keys:
            if k in doc and doc[k]:
                fb = doc[k]
                fb_key = k
                break
        if fb is None:
            continue
        printed += 1
        print(f"# doc_id={did} feedback_key={fb_key}")
        bullets: list[str] = []
        if isinstance(fb, str):
            for raw in fb.split("\n"):
                line = raw.strip()
                if not line:
                    continue
                if line.startswith(("-", "*", "•")):
                    bullets.append(line.lstrip("-*• ").strip())
                else:
                    bullets.append(line)
        elif isinstance(fb, list):
            for item in fb:
                if isinstance(item, dict):
                    bullets.append(
                        str(
                            item.get("text")
                            or item.get("message")
                            or item.get("comment")
                            or item
                        )
                    )
                else:
                    bullets.append(str(item))
        print(f"  bullet_count={len(bullets)} (upper bound on reviewer count)")
        for i, b in enumerate(bullets[:20], 1):
            print(f"  [{i}] {b[:220]}")
    if printed == 0:
        print(f"# no documents matched substring {doc_substr!r}")


def print_url_shares(data: Any, url_substr: str) -> None:
    """List chat-like messages whose body text contains ``url_substr``.

    Useful for "shared by team members" URL questions: a URL that
    appears in the product bundle's `urls` catalog but is never pasted
    into chat was not actually shared by anyone. Only human-author turns
    (not the admin/bot) should count as a share.
    """
    if not isinstance(data, dict):
        return
    messages: list[Any] = []
    for key in ("slack", "slack_messages", "chat", "chat_messages", "messages"):
        v = data.get(key)
        if isinstance(v, list):
            messages = v
            break
    if not messages:
        print("# no chat-like list on this bundle")
        return
    needle = (url_substr or "").lower()
    if not needle:
        print("# url-shares: empty substring, nothing to search")
        return
    print(f"# url shares matching {url_substr!r}")
    hits = 0
    for m in messages:
        if not isinstance(m, dict):
            continue
        ch, user, ts, text, replies = _msg_fields(m)
        if needle in (text or "").lower():
            hits += 1
            snippet = text.replace("\n", " ")[:260]
            print(f"  TOP  {ts} [{user}] ch={ch}: {snippet}")
        for r in replies:
            if not isinstance(r, dict):
                continue
            ru = r.get("User") or r.get("user") or {}
            if isinstance(ru, dict):
                rt = str(ru.get("text") or ru.get("Text") or "")
                rid = str(ru.get("userId") or ru.get("user_id") or "")
                rts = str(ru.get("timestamp") or "")
            else:
                rt, rid, rts = "", "", ""
            if needle in rt.lower():
                hits += 1
                snippet = rt.replace("\n", " ")[:260]
                print(f"  REPL {rts} [{rid}] ch={ch}: {snippet}")
    print(f"# total shares: {hits}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="dataset root, e.g. /root/DATA")
    parser.add_argument(
        "--product",
        help="product name under <root>/products/<product>.json",
    )
    parser.add_argument(
        "--keys",
        action="store_true",
        help="print the top-level keys of the product bundle",
    )
    parser.add_argument(
        "--scan",
        nargs="*",
        default=[],
        help="case-insensitive keywords to count within the selected product bundle",
    )
    parser.add_argument(
        "--chat-authors",
        metavar="CHANNEL_SUBSTRING",
        default=None,
        help=(
            "print per-message top and thread authors in chat-like lists, "
            "optionally filtered by a channel-name substring (use '' for all)"
        ),
    )
    parser.add_argument(
        "--flat-thread",
        metavar="CHANNEL_SUBSTRING",
        default=None,
        help=(
            "print sibling top-level messages (a de-facto flat thread) in a "
            "channel, ordered by timestamp. Use with --since and --keyword "
            "to explore discussions whose ThreadReplies array is empty."
        ),
    )
    parser.add_argument(
        "--since",
        default=None,
        help="ISO-8601 timestamp prefix to start the --flat-thread window from",
    )
    parser.add_argument(
        "--keyword",
        action="append",
        default=[],
        help="keyword to highlight in --flat-thread output (repeatable)",
    )
    parser.add_argument(
        "--feedback-bullets",
        metavar="DOC_ID_SUBSTRING",
        default=None,
        help=(
            "print feedback-field bullets per matching document, with a "
            "bullet count (upper bound on that version's reviewer set)"
        ),
    )
    parser.add_argument(
        "--url-shares",
        metavar="URL_SUBSTRING",
        default=None,
        help=(
            "list chat messages whose body text contains URL_SUBSTRING; "
            "confirms that a catalog URL was actually shared by a team "
            "member in chat"
        ),
    )
    args = parser.parse_args(argv)

    print_tree(args.root)

    data = None
    if args.product and (
        args.keys
        or args.scan
        or args.chat_authors is not None
        or args.flat_thread is not None
        or args.feedback_bullets is not None
        or args.url_shares is not None
    ):
        data = print_product_keys(args.root, args.product)
    elif args.product:
        data = print_product_keys(args.root, args.product)

    if args.scan and data is not None:
        scan_keywords(data, args.scan)

    if args.chat_authors is not None and data is not None:
        print_chat_thread_authors(data, args.chat_authors or None)

    if args.flat_thread is not None and data is not None:
        print_flat_thread(data, args.flat_thread, args.since, args.keyword)

    if args.feedback_bullets is not None and data is not None:
        print_feedback_bullets(data, args.feedback_bullets)

    if args.url_shares is not None and data is not None:
        print_url_shares(data, args.url_shares)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
