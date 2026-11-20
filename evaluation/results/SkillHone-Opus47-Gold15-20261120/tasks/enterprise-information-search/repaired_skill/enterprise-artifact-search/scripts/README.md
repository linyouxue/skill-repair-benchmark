# Supporting scripts

Small generic helpers for the `enterprise-artifact-search` skill.

These scripts are deliberately **content-agnostic**: they do not know
about any particular product, employee, URL, or expected answer. They
only help the subagent get a lightweight view of a dataset without
loading large JSON bundles into the main agent's context.

## Files

- `explore_dataset.py` — print the structure of the dataset root, list
  product bundles and their top-level keys, and (optionally) run a
  case-insensitive keyword scan across a chosen bundle.

## Usage

```
python3 scripts/explore_dataset.py --root /root/DATA
python3 scripts/explore_dataset.py --root /root/DATA --product <ProductName> --keys
python3 scripts/explore_dataset.py --root /root/DATA --product <ProductName> \
    --scan "<keyword1>" "<keyword2>"
python3 scripts/explore_dataset.py --root /root/DATA --product <ProductName> \
    --chat-authors "<channel_substring>"
python3 scripts/explore_dataset.py --root /root/DATA --product <ProductName> \
    --flat-thread "<channel_substring>" --since 2026-05-15 \
    --keyword "<topic>" --keyword "<competitor>"
python3 scripts/explore_dataset.py --root /root/DATA --product <ProductName> \
    --feedback-bullets "<doc_id_substring>"
python3 scripts/explore_dataset.py --root /root/DATA --product <ProductName> \
    --url-shares "<url_substring>"
```

- `--scan` reports hit counts and small snippets per keyword across the
  bundle.
- `--chat-authors` lists per-message top-level and thread-reply author IDs
  for slack-style structures; use an empty string `""` to list every
  channel. Useful for "who provided insights / replied to <topic>"
  questions, where thread replies are frequently missed.
- `--flat-thread` prints sibling top-level messages in a channel ordered
  by timestamp, optionally starting at `--since` and highlighting one or
  more `--keyword` matches. Use this when `ThreadReplies` is empty but a
  conversation clearly unfolds as back-and-forth top-level messages in
  the same channel — a common pattern in these datasets. The subagent
  still decides which turns are substantive; this just surfaces the
  de-facto thread.
- `--feedback-bullets` prints the `feedback` / `feedback_items` /
  `comments` field of each matching document as a numbered bullet list,
  plus the bullet count. Use this to cap each version's reviewer set
  before matching bullets to source turns (Step 6 Tier 1).
- `--url-shares` lists every chat message (top-level or reply) whose
  body text contains the given URL substring. Use this for "shared by
  team members" URL questions: a catalog URL that never appears here
  was not actually shared.

The output is intended to be read by the subagent (not the main agent)
and then discarded; only extracted IDs and short evidence snippets
should ever reach the final answer.
