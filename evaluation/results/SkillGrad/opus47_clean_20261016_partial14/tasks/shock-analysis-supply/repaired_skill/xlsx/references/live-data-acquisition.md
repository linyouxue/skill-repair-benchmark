# Live data acquisition under a mandated source/tool

Trigger: the task names a specific online source (a URL, a named dataset
release, a vintage) and/or a specific acquisition tool (Playwright MCP
browser, a named Python/R package, a specific API). This chapter also
covers the related gap-at-end-of-dataset situation.

The failure mode this chapter prevents: the easy path (direct URL) breaks,
and the executor silently substitutes typed-in values from memory, often
with a fabricated provenance comment ("from package X" when package X was
never actually opened).

## The acquisition ladder

Climb in order. Do not skip rungs. A failure at rung N triggers rung N+1,
NOT a jump to typed-in hardcodes.

```
1. Direct download of the mandated URL
2. Extraction from the mandated named package / tarball / archive
3. Mandated browser automation (e.g. Playwright MCP) against the source site
4. Surface the blocker to the user — do NOT fabricate values
```

### Branch 1 — direct download

```python
import requests
r = requests.get(url, timeout=30)
r.raise_for_status()         # 404 / 5xx raises; proceed to rung 2
open(local_path, "wb").write(r.content)
```

### Branch 2 — named-package extraction

Only cite a package as the source if the extraction actually ran in this
session.

```python
import tarfile, io
with tarfile.open(archive_path) as tf:
    members = tf.getnames()
    target = next(m for m in members if m.endswith(expected_filename))
    data = tf.extractfile(target).read()
    # parse data (xlsx, csv, rds, etc.) — if parse fails, proceed to rung 3
```

### Branch 3 — mandated browser (Playwright MCP)

When the task names Playwright MCP (or any specific browser-automation
tool), a 404 on the direct URL is the trigger to switch here, not to
skip to hardcodes. The browser can reach pages that redirect, require
cookies, or hide the real download link behind a landing page.

```python
# Pseudocode — invoke the tool your harness exposes
page = mcp_browser.open(landing_page_url)
download_link = mcp_browser.find_link(page, text_contains="xlsx")
mcp_browser.download(download_link, to=local_path)
```

### Branch 4 — surface the blocker

If all mandated rungs fail, STOP. Write a note stating which rungs were
tried and how each failed. Do not type values from memory. Do not cite a
source you did not actually open.

## Horizon-gap branch — dataset ends before required horizon

Trigger: inspection (`template-inspection.md`) shows the template expects
coverage through year Y, but the mandated source ends at year X < Y.

Do NOT fill the gap with CAGR, linear interpolation, or any other
convenience formula. Instead:

```
a. Check for a newer vintage of the same source (next release, revised file)
b. Check whether the task implicitly points at a bridge/extension series
   (another variable in the same source, a national-accounts counterpart)
c. If neither (a) nor (b) resolves, leave cells blank with a comment
   "source ends YYYY; no authoritative extension found"
```

```python
from openpyxl.comments import Comment

if latest_year < required_horizon:
    # Try (a): list releases on the source's download page
    # Try (b): search the source's variable catalog for an explicit
    #          extension/bridge note tied to this variable
    # If both fail, write blanks + provenance comment:
    for yr in range(latest_year + 1, required_horizon + 1):
        cell = sheet.cell(row=target_row, column=year_to_col[yr])
        cell.value = None
        cell.comment = Comment(
            f"source {source_name} ends {latest_year}; "
            f"no authoritative extension found",
            "acquisition"
        )
```

## Provenance comments are mandatory

Every raw-data cell written from an external source carries a comment
naming the exact source actually used. Comments must be truthful: if you
got the value from the browser, say so; if you extracted from a tarball,
name the archive path and version.

```python
from openpyxl.comments import Comment

cell.value = raw_value
cell.comment = Comment(
    f"Source: {source_name} {vintage}; fetched {date} via {method}; "
    f"path={inside_archive_path or url}",
    "acquisition"
)
```

Forbidden provenance patterns:

- "From package X" when the archive was never opened in this session.
- "From URL Y" when Y returned 404 and the value came from somewhere else.
- No comment at all on a raw-data cell.

## Verification step

Before saving, iterate every cell written from an external source and
assert each has a provenance comment whose text names a source actually
touched in this session.

```python
touched_sources = {"<url_or_package_or_browser_url_actually_fetched>"}
problems = []
for coord in externally_sourced_cells:
    c = sheet[coord]
    if c.comment is None:
        problems.append((coord, "no comment"))
        continue
    text = c.comment.text
    if not any(src in text for src in touched_sources):
        problems.append((coord, f"comment cites unseen source: {text!r}"))
assert not problems, problems
```

**On failure:**

- If a cell has no comment, attach one now naming the source actually
  used; if you cannot name a source actually opened this session, DELETE
  the cell value and treat the field as a blocker (do not ship typed-in
  hardcodes).
- If a comment cites a source not in `touched_sources`, the comment is a
  false-provenance claim. Rewrite the comment to the real source, or if
  no real source exists, clear the value and comment and surface the
  blocker.
