"""Ground truth for page- and source-matched held-out PDFs."""
import re

import pymupdf as pdf


def line_keys(lines, selection):
    """Expand printed line addresses from the frozen, versioned PDF."""
    page, block, *bounds = selection
    if not bounds:
        return [k for k in lines if k[:2] == (page, block)]
    first, last = bounds
    return [(page, block, i) for i in range(first, last + 1)]


def protection_anchors(doc, lines, redactions, title, count):
    forbidden = {n: [] for n in range(1, len(doc) + 1)}
    for region in redactions:
        for n, *coords in region["pieces"]:
            forbidden[n].append(pdf.Rect(coords) + (-3, -3, 3, 3))
    keep = []
    for n, page in enumerate(doc, 1):
        quota = count // len(doc) + int(n <= count % len(doc))
        candidates = []
        for (pg, _, _), (text, box) in lines.items():
            if pg != n:
                continue
            rect = pdf.Rect(box[1:])
            if (len(text) >= 15 and re.search(r"[A-Za-z]{3}", text)
                    and rect.width >= 60 and 4 < rect.height < 30
                    and 32 < rect.y0 < page.rect.height - 35
                    and not any(rect.intersects(other) for other in forbidden[n])):
                candidates.append(box)
        selected = [title] if n == 1 else []
        eligible = [box for box in candidates if not any(
            pdf.Rect(box[1:]).intersects(pdf.Rect(other[1:])) for other in selected)]
        missing = quota - len(selected)
        if len(eligible) < missing:
            raise ValueError(f"Page {n} lacks enough text anchors")
        for i in range(missing):
            selected.append(eligible[(i + 1) * len(eligible) // (missing + 1)])
        for box in selected:
            assert not any(pdf.Rect(box[1:]).intersects(other) for other in forbidden[n])
            keep.append({"id": f"k{len(keep) + 1:02}", "kind": "preserve", "pieces": [box]})
    return keep


def matched(doc, spec, all_lines, identity_words):
    lines = all_lines(doc)
    redactions = []

    def add(kind, pieces, words=None):
        if not pieces:
            raise ValueError(f"Empty {kind} field in {spec}")
        region = {"id": f"r{len(redactions) + 1:02}", "kind": kind, "pieces": pieces}
        if words is not None:
            region["identity_words"] = words
        redactions.append(region)

    for selection in spec["byline"]:
        for key in line_keys(lines, selection):
            add("byline", [lines[key][1]], identity_words(doc, key))
    for kind, *selectors in spec["fields"]:
        pieces = []
        for selection in selectors:
            if isinstance(selection[1], str):
                page, literal = selection
                rect, = doc[page - 1].search_for(literal)
                pieces.append([page, *list(rect)])
            else:
                pieces.extend(lines[key][1] for key in line_keys(lines, selection))
        add(kind, pieces)
    title = lines[tuple(spec["title"])][1]
    # All splits retain the same number of preservation targets per source slot.
    keep_count = {23: 23, 5: 9, 12: 12}[len(doc)]
    return redactions + protection_anchors(doc, lines, redactions, title, keep_count)
