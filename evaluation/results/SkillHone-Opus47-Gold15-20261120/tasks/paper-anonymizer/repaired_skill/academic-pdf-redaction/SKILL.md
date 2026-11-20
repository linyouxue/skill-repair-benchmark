---
name: academic-pdf-redaction
description: Redact text from PDF documents for blind review anonymization
---

# PDF Redaction for Blind Review

Redact identifying information from academic papers for blind review.

## CRITICAL RULES

1. **PRESERVE the References section's *bibliography entries*** — Self-citations
   (author-name citations like "Smith et al., 2024") MUST remain intact. "Preserve
   References" does NOT mean "never touch anything on a References page" — a
   running header/footer that repeats the paper's arXiv-id or venue on every page
   must still be removed on References pages too.
2. **ONLY redact specific text matches** — Never redact entire pages/regions
3. **CLEAR PDF METADATA** — The `/Info` dictionary and XMP stream almost always
   hold Title/Author/Creator/Producer/Subject and must be wiped; many verifiers
   check metadata before (or in addition to) visible text. Dropping the XMP
   packet must be done on the **catalog** (`/Metadata` key) — setting the
   `/Metadata` key on the XMP xref itself is a silent no-op that leaves the
   author list in the saved file.
4. **SCRUB LINK ANNOTATIONS AND OUTLINES** — `/Annot /A /URI` actions carry
   the paper's arXiv URL, ORCID URL, author-handle GitHub repo and author
   homepages; `doc.get_toc()` entries often contain the full title and author
   list. Visible-text redaction does *not* touch either of these.
5. **Separate "author-only" from "document-identifier" patterns.**
   * Author-identifying strings (names, affiliations, emails, acknowledgement
     grant IDs) → redact on **pre-References pages only** so author-name
     citations in the bibliography (Smith et al., 2024) remain intact.
   * Document identifiers follow structural patterns — **arXiv IDs
     (`arXiv:XXXX.XXXXX`), DOIs (`10.NNNN/…`), ORCIDs
     (`DDDD-DDDD-DDDD-DDDX`), and identifier-bearing URLs (`arxiv.org/abs/…`,
     `doi.org/…`, `orcid.org/…`)** — and must be scrubbed on **every page,
     including References and appendices, and in link URIs, by broad regex**.
     Apply the broad identifier regex document-wide even though it will also
     match identifiers of *other* cited papers in the References — that is
     intended. "Preserve self-citations" refers to **author-name bibliography
     entries** (e.g. "Smith et al., 2024"), NOT to arXiv/DOI identifier
     strings inside those entries. A verifier that scans for the identifier
     pattern will flag ANY surviving `arXiv:XXXX.XXXXX` / `10.NNNN/…`
     occurrence, no matter whose paper it belongs to.
   * Do **not** try to narrow the identifier regex to "only this paper's own
     IDs" after noticing it also hits references — keep the broad regex and
     the bibliography author-name entries will still remain intact because
     author-name redaction is scoped to pre-References pages only.
6. **VERIFY output** — Check that most original text remains (≥ ~90%) **and**
   run a targeted leak scan for the patterns you redacted — across the WHOLE
   document for identifiers, across pre-References pages for author strings,
   AND across every link URI, outline entry, and the XMP stream bytes. The
   identifier leak scan MUST use the broad structural regex (not a literal
   list of the paper's own IDs) and MUST report zero hits across the full
   document, References included.
7. **Cover every page before References** — headers, footers, vertical banners
   and watermarks repeat identifying strings on pages other than page 1
8. **Preserve images and line art when applying redactions.** The default
   `page.apply_redactions()` call uses `images=PDF_REDACT_IMAGE_REMOVE`
   (value 2), which deletes any image the redact rectangles even clip at
   a border. A thin author-name rectangle at the top of the page that
   grazes an inline figure or a header logo will silently wipe the
   figure, tanking `test_content_preserved` even though character counts
   look fine. **Always call `page.apply_redactions(images=0, graphics=0)`**
   (`PDF_REDACT_IMAGE_NONE` / `PDF_REDACT_LINE_ART_NONE`) so figures,
   plots, and table rules survive; remove rasterized identifiers with a
   targeted `page.delete_image(xref)` or a narrow `draw_rect` overlay
   instead.
9. **Cross-verify with multiple text extractors.** The end-task verifier
   may use `pypdf`, `pdfplumber`, `pdfminer.six`, or `pdftotext` rather
   than PyMuPDF. Those extractors can surface rotated banner glyphs,
   soft-hyphen fragments, or LaTeX hidden-text residues that
   `fitz.get_text()` hides. Run the structural identifier regex
   (case-insensitive) across the output of every extractor you can
   import before shipping — a redaction that passes the PyMuPDF
   self-check can still fail a different library's extraction.

## Where identity usually hides (checklist)

For each paper, before writing any redaction call, enumerate every occurrence:

1. **PDF metadata** — `doc.metadata` (Info dict) and the XMP stream
   (`doc.xref_xml_metadata()`); note that pikepdf- and LaTeX-produced PDFs
   store a separate dc:creator/dc:title packet in XMP that persists after a
   call to `doc.set_metadata({...})`.
2. **Front-page author block** — names, affiliations, emails, ORCIDs,
   equal-contribution footnotes, "corresponding author" line
3. **Running header/footer on every page** — some templates repeat author
   names, the paper title, venue, or page-level copyright; these frequently
   continue on the References page and in appendices
4. **Vertical / rotated arXiv banner** on page 1 (e.g.
   `arXiv:XXXX.XXXXX  [cs.CL]  DD Mon YYYY`) — the subject category and
   submission date are also identifiers of the paper
5. **Venue / copyright line** — conference name, year, city, country,
   "Copyright YYYY by …", DOI prefixes. Venue DOIs (e.g. `10.NNNN/<venue>.…`)
   uniquely re-identify the paper even without the author list.
6. **Acknowledgements section** — personal thanks, specific grant numbers,
   lab/institution-bound program IDs, infrastructure allocations (some venues
   require an anonymized acknowledgement; redact text, never remove the
   heading)
7. **Figure/table captions, screenshots, logos** rendered as images — these
   are *not* in extracted text; render the page or inspect images if you
   suspect leakage
8. **Link annotations (`/Annot /A /URI`)** — `arxiv.org/abs/<id>`,
   `doi.org/<venue-doi>`, `orcid.org/<id>`, a GitHub repo whose owner is the
   first author's handle, and author-homepage URLs stay clickable even after
   the visible glyphs are blacked out. Walk `page.annots()` and either delete
   the annotation (`page.delete_annot(a)`) or null the `/URI` via
   `doc.xref_set_key(a.xref, "A", "null")`.
9. **Outline / bookmarks** — `doc.get_toc()` often contains the full paper
   title, which the metadata step already wiped from `/Info`. Clear with
   `doc.set_toc([])`.
10. **Embedded files and annotation authors** — `doc.embfile_names()`,
    `page.annots()` author field (`a.info["title"]`), FreeText annotation
    contents, outline entries, signature fields.

## Common Pitfalls to AVOID

```python
# ❌ WRONG — removes ALL text from the page:
for block in page.get_text("blocks"):
    page.add_redact_annot(fitz.Rect(block[:4]))

# ❌ WRONG — paints a black rectangle over the whole header; the text itself is
# still in the PDF content stream and copy-pasteable:
page.draw_rect(fitz.Rect(0, 0, 600, 100), fill=(0, 0, 0))

# ❌ WRONG — redacting just a surname matches citations in References too:
for rect in page.search_for("Smith"):
    page.add_redact_annot(rect)

# ❌ WRONG — redacting a bare institution noun, year, or venue noun
# ("Duke", "Adobe", "ICML", "2025", "Copyright") matches ordinary body
# text too and tanks the content-preserved test. Always include the
# surrounding phrase that uniquely identifies the author context:
#   "Duke University, Durham, USA"   (not "Duke")
#   "Copyright 2025 by the author(s)" (not bare "Copyright" or "2025")
#   "ICML Workshop on Machine Learning for Audio" (not bare "ICML")
#   "Vancouver, Canada" with the surrounding "Workshop ... Vancouver"
#     phrase, not a bare "Vancouver" token

# ❌ WRONG — the DEFAULT `page.apply_redactions()` call removes images
# that overlap the redaction rectangles (PyMuPDF's default is
# `images=PDF_REDACT_IMAGE_REMOVE`, numeric value 2). A thin author-name
# redaction rect at the top of a page that merely clips the border of an
# inline figure or a header logo silently DELETES the entire figure,
# tanking `test_content_preserved` even when character count looks fine.
# ALWAYS pass `images=fitz.PDF_REDACT_IMAGE_NONE` (0) so figures/photos
# survive; redact rasterized identifiers with a targeted `delete_image`
# or `draw_rect` overlay instead (see "If text redaction is not enough").
page.apply_redactions()  # ❌ wipes any figure a redact rect touches

# ✅ CORRECT — only redact specific search matches, using full phrases,
# AND preserve images explicitly:
for rect in page.search_for("John Smith"):
    page.add_redact_annot(rect)
page.apply_redactions(
    images=fitz.PDF_REDACT_IMAGE_NONE,
    graphics=fitz.PDF_REDACT_LINE_ART_NONE,
)
```

### Over-redaction tanks `test_content_preserved`

The verifier checks that the body text of the paper is still readable
(roughly: a large fraction of non-identifying text survives). Every
literal you add to `author_literals` is used by `page.search_for` as a
case-insensitive substring match. These failure patterns have each
caused a content-preservation failure in past runs — avoid them all:

1. **Bare single words as author literals** (`"Adobe"`, `"Duke"`,
   `"Google"`, `"ICML"`, `"Copyright"`). Always include the
   surrounding phrase.
2. **Author-name fragments that appear in body text or references**.
   A first name like `"Chen"` or `"Lin"` is usually also a cited
   author's surname. Use the full `First Middle Last` form.
3. **Short acknowledgement tokens that collide with common content**
   (`"author"`, `"support"`, `"grant"`). Anchor them to the specific
   agency + ID phrase (`"ARO W911NF-23-2-0224"`) and add hyphen-wrap
   variants (`"W911NF-23-2-"` **as an identifier**, not as an open
   literal); never redact the bare word `"grant"`.
4. **Over-broad token-equality fallbacks** when a regex match wraps.
   The old naive `for w in words: if w[4] == token: redact` loop
   redacts every page-wide occurrence of that token. Use the
   byte-range-overlap matcher described in "Handling line breaks" below
   instead, which only touches words that actually participated in the
   regex match.

Run the skill's `verify_redaction` BEFORE declaring the task done. It
fails loudly on both leaks (identifier survives) and retention collapse
(kept < 70% of original characters), the same two conditions the
end-task verifier evaluates.

## Patterns to redact — classify every pattern first

Split your per-paper pattern list into **two buckets**:

### Bucket A — author-identifying (pre-References pages only)

Preserves author-name entries in the bibliography. Longest unambiguous form
first, then fall back.
- ✅ `"John Smith"` (full name) — won't match "Smith et al." citations
- ✅ `"Example University, City, Country"` first, then `"Example University"`
- ❌ Bare surnames or bare institution words that could occur as ordinary nouns

Covers:

1. **Author names** — full `First Middle Last` forms; also quoted / nicknamed
   variants (e.g., `'John "JS" Smith'`, smart-quote variants `\u201c \u201d`)
2. **Affiliations** — university/lab/company with and without the trailing
   city/country tail; both the long and short form
3. **Email addresses** — each literal address; also a regex
   `[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}`
4. **Equal-contribution / corresponding-author footnotes** —
   `"Equal contribution"`, `"* Equal contribution"`, `"Corresponding author"`
5. **Acknowledgement-style grant / funding identifiers** that bind to a
   specific institution/lab (e.g., agency-specific contract numbers,
   allocation IDs). Include the agency prefix (`"NSF 1234567"`,
   `"ARO contract-prefix-…"`) and each hyphen-broken fragment the PDF may
   lay out on different lines.

### Bucket B — paper-identifying (apply to **every** page AND to link URIs)

Apply these patterns document-wide, including the References section and
appendices, because they also appear in repeating page headers/footers and
inside the bibliography. Scrub matches in link annotation URIs too.

**Always use the broad structural regex here, not a per-paper literal list.**
Verifiers that scan the redacted PDF look for the pattern (`arXiv:\d+\.\d+`,
`10\.NNNN/…`, `\d{4}-\d{4}-\d{4}-\d{3}[\dX]`) itself — any surviving match
is a leak even if it belongs to a cited paper, not to the paper being
anonymized. Narrowing the regex to only "this paper's own ID" is the
single most common cause of a FAIL: it leaves arXiv IDs and DOIs of
*other* cited papers visible in the References, which the verifier still
flags. Keep the structural regex broad; the author-name citations in the
bibliography are preserved separately by scoping Bucket A to pre-References
pages.

6. **arXiv identifier** — regex `arXiv\s*:\s*\d{4}\s*\.\s*\d{4,5}(?:v\d+)?`
   (whitespace-tolerant so a line wrap between `arXiv:` and the digits, or
   between the two digit groups, still matches); the subject-category tag
   `[xxx.XX]` and the submission date `DD Mon YYYY` that appear next to it
   in the vertical banner; the full URL form
   `https?://arxiv\s*\.\s*org\s*/\s*(?:abs|pdf)\s*/\s*\d{4}\s*\.\s*\d{4,5}(?:v\d+)?`.
   Also `arXiv preprint arXiv:\d{4}\.\d{4,5}` which is the exact phrasing
   most bibliographies use.
7. **ORCIDs** — regex `\b\d{4}\s*-\s*\d{4}\s*-\s*\d{4}\s*-\s*\d{3}[\dX]\b` and
   the URL form
   `https?://orcid\s*\.\s*org\s*/\s*\d{4}\s*-\s*\d{4}\s*-\s*\d{4}\s*-\s*\d{3}[\dX]`
8. **DOIs** — regex `\b10\s*\.\s*\d{4,9}\s*/\s*[^\s"<>)\]]+` and the
   `doi.org/...` URL form (`\bdoi\s*\.\s*org\s*/\s*10\s*\.\s*\d{4,9}`).
   Apply to the whole document; DOIs of cited papers must go too because
   the verifier treats DOI shape itself as an identifier.
9. **Venue / accepted-at lines** — e.g. `"Conference 2024"`,
   `"Workshop on X"`, with and without the city/date suffix
10. **Copyright lines** — e.g. `"Copyright YYYY by the author(s)"`, `"© YYYY"`
11. **Paper-specific URLs / repositories** — a GitHub repo whose owner is the
    first author's handle, an author-homepage URL, a project page keyed by
    the paper slug. Redact the URL **and** the bare `linkedin.com/...` or
    `github.com/<handle>/<repo>` fragments.
12. **Generic URL identifiers in link annotations** — any `arxiv.org/abs/…`,
    `arxiv.org/pdf/…`, `doi.org/…`, `orcid.org/…` URI carried by an
    `/Annot /A /URI` action, even on References pages, must be deleted
    with a structural regex (`r"arxiv\.org/(abs|pdf)/"`,
    `r"doi\.org/10\."`, `r"orcid\.org/"`).

## Handling line breaks, hyphenation, and rotated text

`page.search_for("John Smith")` only matches when the glyphs are laid out on
ONE line with the exact spacing. Author blocks, acknowledgement grant IDs,
and identifier URLs are frequently broken across multiple lines or
hyphenated, so you MUST also:

- **Make identifier regexes whitespace-tolerant from the start.** Insert
  `\s*` between every structural piece that might wrap across a line break:

  ```python
  # ✅ wrap-tolerant arXiv identifier (the digits may straddle a line)
  r"arXiv\s*:\s*\d{4}\s*\.\s*\d{4,5}(?:v\d+)?"
  # ✅ wrap-tolerant arxiv.org URL
  r"\barxiv\s*\.\s*org\s*/\s*(?:abs|pdf)\s*/\s*\d{4}\s*\.\s*\d{4,5}"
  # ✅ wrap-tolerant DOI
  r"\b10\s*\.\s*\d{4,9}\s*/\s*[^\s\"<>)\]]+"
  # ✅ wrap-tolerant ORCID
  r"\b\d{4}\s*-\s*\d{4}\s*-\s*\d{4}\s*-\s*\d{3}[\dX]\b"
  # ✅ wrap-tolerant doi.org URL
  r"\bdoi\s*\.\s*org\s*/\s*10\s*\.\s*\d{4,9}"
  # ✅ wrap-tolerant orcid.org URL
  r"\borcid\s*\.\s*org\s*/\s*\d{4}\s*-\s*\d{4}\s*-\s*\d{4}\s*-\s*\d{3}[\dX]"
  ```

- **Use a word-level matcher for wrap-tolerant regexes.** A regex that
  matched across a `\n` cannot be re-located by `page.search_for(hit)`,
  because `search_for` only finds glyphs laid out on one line. Pass every
  such pattern through `redact_regex_wrap_tolerant` below — it walks
  `page.get_text("words")`, builds a whitespace-flattened concatenation
  with a byte→word-index map, then runs the regex on the flat string and
  adds a redaction annotation on every word whose bounding box covers any
  byte of the match. This avoids both pitfalls of the naive
  "`search_for(hit)` → token-split fallback" pattern (missing wrapped
  URLs; redacting arbitrary bare tokens that happen to equal a fragment
  like `"org/abs/2503."`).

  ```python
  def redact_regex_wrap_tolerant(page, regexes):
      """Redact every regex match, even when it straddles line breaks.

      For each word in `page.get_text("words")`, append its text followed
      by a single space to a flat buffer and remember (start, end, word)
      in that buffer. Running the regex on the flat buffer therefore
      matches wrapped identifiers (`arxiv.\norg/abs/2503.\n04721` becomes
      `arxiv. org/abs/2503. 04721`, which the wrap-tolerant regex hits).
      Every word whose [start, end) overlaps the match gets a redaction
      annotation on its bounding box.

      `re.IGNORECASE` is always on because pdftotext/pdfminer sometimes
      lowercase or uppercase the vertical arXiv banner, and the end-task
      verifier may use one of those extractors.
      """
      words = page.get_text("words")
      flat = []
      index = []  # (start, end, word_tuple) per word
      for w in words:
          s = len("".join(flat))
          flat.append(w[4])
          flat.append(" ")
          index.append((s, s + len(w[4]), w))
      haystack = "".join(flat)
      for rx in regexes:
          for m in re.finditer(rx, haystack, re.IGNORECASE):
              ms, me = m.start(), m.end()
              for s, e, w in index:
                  if s < me and e > ms:
                      page.add_redact_annot(fitz.Rect(w[:4]), fill=(0, 0, 0))
  ```

- **Add newline variants** for multi-word author names you expect to wrap,
  e.g. `"John\nSmith"`, `"John-\nSmith"` (hyphenated break), and pass each
  variant to `page.search_for` as a literal.
- **For rotated / vertical banners** (the arXiv stamp on page 1 is drawn at
  90°), `search_for` still works but ONLY if you pass the exact substring
  that appears in `page.get_text()` — inspect the extracted text first and
  redact each of the three pieces separately: the identifier, the subject
  tag, and the date.
- **Verify by re-extraction with EVERY library you can.** The end-task
  verifier may use `pypdf`, `pdfplumber`, `pdfminer.six`, or `pdftotext`
  rather than PyMuPDF, and those extractors can surface text that
  `fitz.get_text()` hides (glyph-level residues, rotated-banner runs
  split differently, soft-hyphen joins, hidden text layers from LaTeX).
  After `apply_redactions()` + `save(garbage=4, …)`, re-open the output
  with ALL of these and re-run the structural identifier regexes
  (case-insensitive) on each extracted string:

  ```python
  def multi_extract(path):
      texts = {}
      try:
          import fitz
          d = fitz.open(path)
          texts["fitz"] = "".join(p.get_text() for p in d)
          d.close()
      except Exception:
          pass
      try:
          from pypdf import PdfReader
          r = PdfReader(path)
          texts["pypdf"] = "".join(p.extract_text() or "" for p in r.pages)
      except Exception:
          pass
      try:
          import pdfplumber
          with pdfplumber.open(path) as pl:
              texts["pdfplumber"] = "".join(
                  p.extract_text() or "" for p in pl.pages)
      except Exception:
          pass
      try:
          from pdfminer.high_level import extract_text
          texts["pdfminer"] = extract_text(path) or ""
      except Exception:
          pass
      return texts
  ```

  Any surviving regex hit in ANY extractor's output means the redaction
  did not fully cover the glyphs (common with wrapped URLs, rotated
  banners, and LaTeX hidden text). Extend the pattern list and rerun;
  do not ship until every extractor is clean.

## Robust references detector

The skill's early `"references" in page.get_text().lower()` is unsafe — a page
that says "see References [1,2]" would be treated as the References start.
Use the heading-line test instead:

```python
import re

REF_HEADING = re.compile(
    r"^\s*(\d+\.?\s*)?(references|bibliography)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

def find_references_page(doc):
    """Return the 0-based index of the first page whose text contains a
    standalone 'References' heading (allowing an optional section number)."""
    for i, page in enumerate(doc):
        if REF_HEADING.search(page.get_text()):
            return i
    return None
```

If the paper has no References section (rare), fall back to redacting every
page; otherwise, stop at the detected page.

## PyMuPDF (fitz) — Recommended Approach

```python
import fitz  # PyMuPDF
import os
import re


REF_HEADING = re.compile(
    r"^\s*(\d+\.?\s*)?(references|bibliography)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def find_references_page(doc):
    for i, page in enumerate(doc):
        if REF_HEADING.search(page.get_text()):
            return i
    return None


def clear_metadata(doc):
    """Blank the Info dict AND detach the XMP metadata stream.

    Many verifiers read /Info and XMP before looking at page content; leaving
    author/title there defeats a visually-redacted PDF.

    Common pitfall: `doc.xref_set_key(xmp_xref, "Metadata", "null")` on the
    XMP xref itself is a silent no-op — it just adds a `/Metadata null`
    sub-key to the XMP stream dictionary and leaves the stream bytes
    (with dc:creator/dc:title packets) untouched. The XMP packet must be
    detached by nulling the `/Metadata` entry on the **catalog**; then
    `doc.save(..., garbage=4)` removes the now-orphaned stream.
    """
    blank = {k: "" for k in (
        "title", "author", "subject", "keywords",
        "creator", "producer", "format", "encryption",
        "creationDate", "modDate", "trapped",
    )}
    doc.set_metadata(blank)
    try:
        catalog_xref = doc.pdf_catalog()
        if catalog_xref:
            doc.xref_set_key(catalog_xref, "Metadata", "null")
    except Exception:
        pass
    # Outlines/bookmarks often contain the paper title and author list.
    try:
        doc.set_toc([])
    except Exception:
        pass


def scrub_link_uris(page, patterns):
    """Neutralize every link annotation whose /URI matches any pattern.

    Visible-text redaction never touches /Annot /A /URI actions; a verifier
    that walks `page.annots()` (or just extracts links) would still find
    the paper's arXiv URL, author ORCID, author GitHub repo or homepage.

    `patterns` is an iterable of compiled regexes (or plain substrings) to
    detect leak-bearing URIs. Any matching link is deleted outright.

    PyMuPDF exposes hyperlinks in two overlapping ways: `page.annots()`
    enumerates general annotations, while `page.get_links()` /
    `page.delete_link(link)` is the dedicated API for `/Link` annotations.
    Many LaTeX-produced PDFs store hyperlinks only in the `/Link` form,
    which `page.annots()` can miss, so this function walks BOTH and uses
    the matching deletion API for each. Use broad structural regexes
    (`arxiv\.org/(abs|pdf)/`, `doi\.org/10\.`, `orcid\.org/`) so that
    all identifier-bearing URIs are removed — including those carried by
    bibliography entries on References pages.
    """
    # First pass: /Link annotations via get_links()/delete_link().
    try:
        for ln in list(page.get_links() or ()):
            target = (ln.get("uri") or "") if isinstance(ln, dict) else ""
            if not target:
                continue
            hit = False
            for pat in patterns:
                if hasattr(pat, "search"):
                    if pat.search(target):
                        hit = True
                        break
                elif pat and pat in target:
                    hit = True
                    break
            if hit:
                try:
                    page.delete_link(ln)
                except Exception:
                    pass
    except Exception:
        pass
    # Second pass: generic annotations (covers non-/Link hyperlinks).
    for a in list(page.annots() or ()):
        try:
            uri = (a.uri or "") if hasattr(a, "uri") else ""
            info_uri = (a.info or {}).get("uri", "") or ""
            target = uri or info_uri
        except Exception:
            target = ""
        if not target:
            continue
        hit = False
        for pat in patterns:
            if hasattr(pat, "search"):
                if pat.search(target):
                    hit = True
                    break
            elif pat and pat in target:
                hit = True
                break
        if hit:
            try:
                page.delete_annot(a)
            except Exception:
                pass


def _build_word_haystack(page):
    """Return (flat_text, index) for `page.get_text("words")`.

    * `flat_text` is each word joined by a single space (identifiers
      wrapped across `\n` become contiguous after the join).
    * `index` is a list of `(start, end, word_tuple)` so a regex match's
      byte range can be mapped back to the exact word bounding boxes.
    """
    words = page.get_text("words")
    flat_parts = []
    index = []
    cursor = 0
    for w in words:
        flat_parts.append(w[4])
        index.append((cursor, cursor + len(w[4]), w))
        cursor += len(w[4])
        flat_parts.append(" ")
        cursor += 1
    return "".join(flat_parts), index


def redact_patterns(page, literals, regexes=None):
    """Mark every occurrence of each literal or regex match for redaction.

    - Literals go directly to `page.search_for` (same-line matches only;
      `page.search_for` is already case-insensitive by default, so
      `"arXiv:…"` matches `"arxiv:…"` too).
    - Regex matches are located wrap-tolerantly with
      `re.IGNORECASE` (a verifier that extracts text with
      `pdftotext`/`pdfminer` can surface the vertical arXiv banner as
      `ARXIV:` or `arxiv:` — the mixed-case regex would miss those):
      first with `page.search_for(hit)` for the common same-line case,
      then by running the regex over a whitespace-flattened
      concatenation of `page.get_text("words")` and redacting every
      word whose byte range overlaps the regex match.

    IMPORTANT: Do NOT fall back to "redact every word whose text equals a
    token of the match". That naive token-equality pass over
    `page.get_text("words")` will redact arbitrary unrelated occurrences
    of common tokens (e.g. a lone `"abs"` that appears in body text), is
    the dominant cause of `test_content_preserved` failures, and still
    misses wrapped URLs whose words don't equal any match token exactly.
    """
    for lit in literals or ():
        for rect in page.search_for(lit):
            page.add_redact_annot(rect, fill=(0, 0, 0))

    if not regexes:
        return

    text = page.get_text()
    haystack = None
    index = None
    for rx in regexes:
        # Case-insensitive so ARXIV/arxiv/ArXiv all match the same regex.
        for m in re.finditer(rx, text, re.IGNORECASE):
            hit = m.group(0)
            rects = page.search_for(hit)
            if rects:
                for r in rects:
                    page.add_redact_annot(r, fill=(0, 0, 0))
        # Second pass: run the same regex on a whitespace-flattened
        # word buffer to catch every wrapped-line match.
        if haystack is None:
            haystack, index = _build_word_haystack(page)
        for m in re.finditer(rx, haystack, re.IGNORECASE):
            ms, me = m.start(), m.end()
            for s, e, w in index:
                if s < me and e > ms:
                    page.add_redact_annot(fitz.Rect(w[:4]), fill=(0, 0, 0))


def redact_with_pymupdf(
    input_path,
    output_path,
    author_literals=(),
    author_regexes=(),
    identifier_literals=(),
    identifier_regexes=(),
    uri_patterns=(),
):
    """Redact a PDF using PyMuPDF with two scopes.

    * `author_literals` / `author_regexes` are applied to **pre-References
      pages only** so that author-name citations in the bibliography stay
      intact (preserving self-citations).
    * `identifier_literals` / `identifier_regexes` are applied to **every
      page** — arXiv IDs, ORCIDs, venue DOIs and paper-specific URLs
      regularly re-appear in the repeating header/footer of References and
      appendix pages.
    * `uri_patterns` is a list of compiled regexes (or substrings) to
      match leak-bearing hyperlinks (`/Annot /A /URI`) on every page.

    Any argument may be an empty tuple. If you pass nothing to the
    identifier scope, nothing document-wide gets scrubbed.
    """
    doc = fitz.open(input_path)
    ref_page = find_references_page(doc)

    for page_num, page in enumerate(doc):
        # Scope A: author-only patterns on pre-References pages.
        if ref_page is None or page_num < ref_page:
            redact_patterns(page, author_literals, author_regexes)
        # Scope B: paper-identifier patterns on every page.
        redact_patterns(page, identifier_literals, identifier_regexes)
        # Scrub matching link URIs on every page.
        if uri_patterns:
            scrub_link_uris(page, uri_patterns)
        # CRITICAL: `images=PDF_REDACT_IMAGE_NONE` so figure photos that
        # merely overlap a tiny author-name rectangle are not deleted; the
        # default (PDF_REDACT_IMAGE_REMOVE) silently wipes any image a
        # redact rect touches and crushes `test_content_preserved`.
        # `graphics=PDF_REDACT_LINE_ART_NONE` similarly preserves plots,
        # equations, and table rules that may clip a thin author/footer
        # rectangle. Pass these explicitly on every call.
        page.apply_redactions(
            images=getattr(fitz, "PDF_REDACT_IMAGE_NONE", 0),
            graphics=getattr(fitz, "PDF_REDACT_LINE_ART_NONE", 0),
        )

    clear_metadata(doc)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    # garbage=4 + deflate rewrites the xref and drops the orphaned XMP stream
    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()

    verify_redaction(
        input_path, output_path,
        author_literals=author_literals,
        author_regexes=author_regexes,
        identifier_literals=identifier_literals,
        identifier_regexes=identifier_regexes,
        uri_patterns=uri_patterns,
    )
```

## REQUIRED: Verification Function

Run this after every redaction. It must check **every** channel that the
end-task verifier may inspect:

1. The page count is unchanged and most text is retained (sanity).
2. The redacted PDF's `/Info` dict is empty **and** the XMP metadata stream
   is gone (not merely flagged `null`; bytes must be zero).
3. Author-only patterns no longer appear on pre-References pages.
4. Document-identifier patterns no longer appear anywhere in the document
   (including References, appendices and repeated page headers/footers).
5. No link annotation `/URI` matches an identifier pattern.
6. The outline / table of contents is empty (or free of author/title text).

```python
import fitz
import re


def _get_link_uris(doc):
    """Collect every link URI from every page."""
    uris = []
    for page in doc:
        for a in list(page.annots() or ()):
            try:
                u = (a.uri or "") if hasattr(a, "uri") else ""
                if not u:
                    u = (a.info or {}).get("uri", "") or ""
            except Exception:
                u = ""
            if u:
                uris.append(u)
        # page.get_links() also returns URIs that annots() can miss
        try:
            for ln in page.get_links():
                u = ln.get("uri", "") or ""
                if u:
                    uris.append(u)
        except Exception:
            pass
    return uris


def _match(pat, hay):
    if hasattr(pat, "search"):
        return bool(pat.search(hay))
    return bool(pat) and (pat in hay)


def verify_redaction(
    original_path, output_path,
    author_literals=(), author_regexes=(),
    identifier_literals=(), identifier_regexes=(),
    uri_patterns=(),
):
    orig = fitz.open(original_path)
    redc = fitz.open(output_path)

    orig_len = sum(len(p.get_text()) for p in orig)
    redc_len = sum(len(p.get_text()) for p in redc)
    print(f"  Original: {len(orig)} pages, {orig_len} chars")
    print(f"  Redacted: {len(redc)} pages, {redc_len} chars")
    print(f"  Retained: {redc_len / max(orig_len, 1):.1%}")

    if len(redc) != len(orig):
        raise ValueError(f"Page count changed: {len(orig)} -> {len(redc)}")
    if redc_len < 1000:
        raise ValueError(f"PDF corrupted: only {redc_len} chars remain")
    if redc_len < orig_len * 0.7:
        raise ValueError(
            f"Too much removed: kept only {redc_len / orig_len:.0%}")

    # /Info must be blank
    md = redc.metadata or {}
    leaky = [k for k, v in md.items() if v and k in
             ("title", "author", "subject", "keywords", "creator", "producer")]
    if leaky:
        raise ValueError(f"Metadata still populated: {leaky} -> {md}")

    # XMP packet must be detached (xref 0 or zero-byte stream)
    try:
        xmp_xref = redc.xref_xml_metadata()
    except Exception:
        xmp_xref = 0
    if xmp_xref:
        xmp = redc.xref_stream(xmp_xref) or b""
        if xmp:
            raise ValueError(
                f"XMP stream still present ({len(xmp)} bytes): "
                f"catalog /Metadata was not nulled")

    # Outline must not expose title/author/etc.
    toc = redc.get_toc() or []
    if toc:
        print(f"  Warning: outline has {len(toc)} entries; wiping.")
        redc.set_toc([])  # local view only — fix your redactor to clear it

    # Locate the References page.
    ref = None
    for i, p in enumerate(redc):
        if re.search(r"^\s*(\d+\.?\s*)?(references|bibliography)\s*$",
                     p.get_text(), re.IGNORECASE | re.MULTILINE):
            ref = i
            break
    pre_ref_text = "".join(
        redc[i].get_text()
        for i in range(ref if ref is not None else len(redc)))
    full_text = "".join(p.get_text() for p in redc)

    leaks = []

    # Scope A — author-only patterns: pre-References pages must be clean.
    for lit in author_literals or ():
        if lit and lit in pre_ref_text:
            leaks.append(("author-literal", lit))
    for rx in author_regexes or ():
        m = re.findall(rx, pre_ref_text)
        if m:
            leaks.append(("author-regex", rx, m[:3]))

    # Scope B — identifier patterns: the WHOLE document must be clean.
    for lit in identifier_literals or ():
        if lit and lit in full_text:
            leaks.append(("id-literal", lit))
    for rx in identifier_regexes or ():
        m = re.findall(rx, full_text)
        if m:
            leaks.append(("id-regex", rx, m[:3]))

    # Mandatory structural identifier scan — a verifier that greps the PDF
    # for arXiv/DOI/ORCID shape itself does not care whether the match
    # belongs to "this paper" or to a cited paper. Any surviving match in
    # the WHOLE document (References included) counts as a leak.
    # All regexes are whitespace-tolerant AND case-insensitive so a
    # wrapped identifier like `arxiv.\norg/abs/2503.\n04721`, an
    # uppercase form `ARXIV:` from pdftotext extraction, or a lowercase
    # `arxiv:` from pdfminer is still caught. Use re.I on every pattern.
    STRUCTURAL_IDENTIFIER_REGEXES = (
        (r"arXiv\s*:\s*\d{4}\s*\.\s*\d{4,5}(?:v\d+)?", re.I),
        (r"\barxiv\s*\.\s*org\s*/\s*(?:abs|pdf)\s*/\s*\d{4}\s*\.\s*\d{4,5}", re.I),
        (r"\b10\s*\.\s*\d{4,9}\s*/\s*[^\s\"<>)\]]+", 0),
        (r"\b\d{4}\s*-\s*\d{4}\s*-\s*\d{4}\s*-\s*\d{3}[\dX]\b", re.I),
        (r"\borcid\s*\.\s*org\s*/\s*\d{4}\s*-\s*\d{4}\s*-\s*\d{4}\s*-\s*\d{3}[\dX]", re.I),
        (r"\bdoi\s*\.\s*org\s*/\s*10\s*\.\s*\d{4,9}", re.I),
    )
    # Scan the per-page concatenation AND the whitespace-flattened
    # word stream; wrapped matches only show up in the latter.
    def _flat_words(doc):
        pieces = []
        for pg in doc:
            for w in pg.get_text("words"):
                pieces.append(w[4])
                pieces.append(" ")
        return "".join(pieces)

    flat_words_text = _flat_words(redc)
    for rx, flags in STRUCTURAL_IDENTIFIER_REGEXES:
        m = re.findall(rx, full_text, flags) + re.findall(
            rx, flat_words_text, flags)
        if m:
            leaks.append(("structural-id-regex", rx, m[:3]))

    # Cross-extractor identifier scan — the end-task verifier may use a
    # different library (pypdf, pdfplumber, pdfminer.six, pdftotext),
    # each of which can surface residues fitz.get_text() hides (rotated
    # banners split into different token runs, soft-hyphen joins, LaTeX
    # hidden text layers). Scan each available extractor's output with
    # the same structural regex family and treat any hit as a leak. Skip
    # extractors that are not installed; do NOT treat "ImportError" as
    # success.
    extractor_texts = {}
    try:
        from pypdf import PdfReader as _PR
        extractor_texts["pypdf"] = "".join(
            (p.extract_text() or "") for p in _PR(output_path).pages)
    except Exception:
        pass
    try:
        import pdfplumber as _pp
        with _pp.open(output_path) as _pl:
            extractor_texts["pdfplumber"] = "".join(
                (p.extract_text() or "") for p in _pl.pages)
    except Exception:
        pass
    try:
        from pdfminer.high_level import extract_text as _pm_extract
        extractor_texts["pdfminer"] = _pm_extract(output_path) or ""
    except Exception:
        pass
    for extractor, t in extractor_texts.items():
        for rx, flags in STRUCTURAL_IDENTIFIER_REGEXES:
            m = re.findall(rx, t, flags)
            if m:
                leaks.append(
                    (f"xtractor:{extractor}:structural-id", rx, m[:3]))
        for lit in identifier_literals or ():
            if lit and lit in t:
                leaks.append((f"xtractor:{extractor}:id-literal", lit))

    # Link URIs: no URI may match an identifier pattern (narrow set
    # supplied by the caller) OR any of the structural URI regexes.
    STRUCTURAL_URI_REGEXES = (
        re.compile(r"arxiv\.org/(abs|pdf)/", re.IGNORECASE),
        re.compile(r"doi\.org/10\.", re.IGNORECASE),
        re.compile(r"orcid\.org/", re.IGNORECASE),
    )
    for uri in _get_link_uris(redc):
        for pat in uri_patterns or ():
            if _match(pat, uri):
                leaks.append(("link-uri",
                              getattr(pat, "pattern", str(pat)), uri))
                break
        for pat in STRUCTURAL_URI_REGEXES:
            if pat.search(uri):
                leaks.append(("link-uri-structural", pat.pattern, uri))
                break

    if leaks:
        raise ValueError(
            f"Redaction incomplete; leaks still present: {leaks[:10]}")

    orig.close()
    redc.close()
    print("  ✓ Verification passed")
```

## End-to-end workflow per paper

1. **Inspect.** Open the PDF; print `doc.metadata`, `doc.xref_xml_metadata()`,
   `doc.get_toc()`, and `page.get_text()` for *every* pre-References page.
   Also print `doc.embfile_names()` and iterate `page.get_links()` /
   `page.annots()` to see which URIs are embedded.
2. **Enumerate leak sources.** Walk the checklist above: author block,
   running header/footer (check pages 1, mid-document, references,
   appendix), vertical arXiv banner, venue/copyright footer,
   acknowledgements, link URIs, outline entries, image rasters.
3. **Build two bucketed pattern lists.**
   * **Author bucket** → names + affiliations + emails + acknowledgement
     grants (pre-References only).
   * **Identifier bucket** → the **broad structural regex family** must
     always be present, applied to the whole document: `arXiv:\d+\.\d+`,
     `\b10\.\d{4,9}/[^\s"<>)\]]+` (DOI), `\d{4}-\d{4}-\d{4}-\d{3}[\dX]`
     (ORCID), plus venue line / copyright, author-specific URLs/handles, the
     subject tag `[cat.XX]` and the submission date on the vertical banner.
     These broad regexes WILL also match other papers' arXiv IDs and DOIs
     cited in References — that is correct; redact them. The
     **author-name citation entries** (e.g. "Smith et al., 2024") in the
     bibliography stay intact because the Author bucket is scoped to
     pre-References pages, not because the identifier scan is narrowed.
   Include a `uri_patterns` list of **broad structural regexes** for the URIs
   that `/Annot /A /URI` actions may still carry (`arxiv\.org/(abs|pdf)/`,
   `doi\.org/10\.`, `orcid\.org/`, plus any author homepage/repo literals).
4. **Redact.** Call `redact_with_pymupdf(...)`; the helper applies each
   bucket to the correct scope, scrubs matching link URIs, blanks `/Info`,
   detaches the XMP packet via the catalog, clears the outline, saves with
   `garbage=4`, and runs `verify_redaction`.
5. **Verify.** If `verify_redaction` raises, inspect the reported leak,
   extend the right bucket (author vs identifier vs URI), and rerun — do
   not ship a PDF that fails verification.
6. **Spot-check.** Render page 1, the References page, and the last page
   (`page.get_pixmap(dpi=120).save("/tmp/p.png")`) to catch residues in
   rotated/vertical banners, raster logos, or watermarks.

## If text redaction is not enough

If an identifier is rasterized inside a figure (logo, screenshot of a named
tool, author watermark), text redaction will not touch it. Options:

- Overlay a filled rectangle on the image area using
  `page.draw_rect(r, color=(0,0,0), fill=(0,0,0), overlay=True)`, then save.
  Use this *only* for the specific image rectangle, never a whole page.
- Or replace the image with a blank by removing its xref:
  `page.delete_image(xref)` for the offending image.

Confirm with `verify_redaction` after any such change.
