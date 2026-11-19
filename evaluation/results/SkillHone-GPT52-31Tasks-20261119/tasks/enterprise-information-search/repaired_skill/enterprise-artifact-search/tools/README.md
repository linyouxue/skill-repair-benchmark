# Tools (enterprise-artifact-search)

This directory contains optional **stdlib-only** helper scripts for tasks that ask you to retrieve structured facts from enterprise artifact bundles (docs/slack/meetings/PRs/URLs).

## `enterprise_search.py`

A reusable baseline that:
- parses `/root/question.txt` (often JSON-like, not strict JSON)
- searches product bundles under `/root/DATA/products`
- extracts only *grounded* `eid_...` IDs and external `http(s)://` URLs from artifacts
- writes `/root/answer.json` with the required `{answer: [...], tokens: "..."}` structure

### Usage

```bash
python3 skills/enterprise-artifact-search/tools/enterprise_search.py \
  --questions /root/question.txt \
  --data /root/DATA \
  --output /root/answer.json
```

### Design notes

- **Instance-agnostic**: no hard-coded product names, IDs, or URLs.
- **Performance-aware**: narrows candidate product files by cheap byte-substring checks before JSON parsing.
- **Schema-aware**: supports the common Slack event shape used in these datasets (including thread replies), and common `employee.json` formats.

If you need higher precision (e.g., report author vs. reviewer), follow the guidance in `SKILL.md` and add targeted extraction logic rather than broad heuristics.
