"""Build the private region index for the frozen source PDFs (PyMuPDF)."""
import argparse
import json
from pathlib import Path
import re

import pymupdf as pdf
from matched_references import matched

ROOT = Path(__file__).resolve().parents[1]


def all_lines(doc):
    result = {}
    for index, page in enumerate(doc, 1):
        for block in page.get_text("dict", flags=0)["blocks"]:
            for line_no, line in enumerate(block.get("lines", [])):
                text = "".join(s["text"] for s in line["spans"]).strip()
                if text:
                    key = (index, block["number"], line_no)
                    result[key] = (text, [index, *[round(n, 3) for n in line["bbox"]]])
    return result


def identity_words(doc, key):
    pg, block_no, line_no = key
    blocks = doc[pg-1].get_text("rawdict", flags=0)["blocks"]
    block = next(b for b in blocks if b["number"] == block_no)
    spans = block["lines"][line_no]["spans"]
    has_email = any("@" in "".join(c["c"] for c in s["chars"]) for s in spans)
    boxes = []
    for span in spans:
        chars = span["chars"]
        text = "".join(c["c"] for c in chars)
        for match in re.finditer(r"[^\W_]+", text):
            token = match.group()
            if (token.casefold() in {"and", "to", "correspondence", "email"}
                    or (token.isdecimal() and not (has_email and len(token) >= 4))):
                continue
            rect = pdf.Rect(chars[match.start()]["bbox"])
            for c in chars[match.start()+1:match.end()]:
                rect |= pdf.Rect(c["bbox"])
            boxes.append([pg, *[round(v,3) for v in rect]])
    assert boxes
    return boxes


def annotations(name, doc):
    lines = all_lines(doc)
    first = [(k, text, box) for k, (text, box) in lines.items() if k[0] == 1]
    abstract_top = next(box[2] for _, text, box in first if text.casefold() == "abstract")
    regions = []

    def add(kind, keys):
        pieces = [lines[key][1] for key in keys]
        assert pieces
        regions.append({"id": f"r{len(regions)+1:02}", "kind": kind, "pieces": pieces})

    def block(page, index, start, end):
        return [(page, index, i) for i in range(start, end+1)]

    for key, text, box in first:
        if key[1] > 0 and box[2] > 118 and box[4] < abstract_top + 3:
            add("byline", [key])
            regions[-1]["identity_words"] = identity_words(doc, key)
        elif (text == "Interspeech 2024" or "September 2024, Kos, Greece" in text
              or text.startswith(("10.21437/Interspeech.2024-", "arXiv:2509.26542v"))):
            add("publication", [key])
    if name == "paper2":
        add("acknowledgment", block(4,24,0,9) + block(5,0,0,2))
    if name == "paper3":
        add("correspondence_and_funding", block(1,6,1,4))
        add("publication", block(1,6,5,6))
    if name == "paper1":
        add("author_project_link", [(2,29,0)])
        uri, = doc[1].search_for("https://github.com/linyueqian/VERA")
        regions[-1]["pieces"] = [[2, *list(uri)]]

    # Sample a legible source line on every page, then spread remaining anchors
    # across the text. Spatial exclusion prevents a correct mask harming an anchor.
    candidates = {p: [] for p in range(1, len(doc)+1)}
    sensitive = [piece for region in regions for piece in region["pieces"]]
    for key, (text, box) in lines.items():
        pg = key[0]
        rect = pdf.Rect(box[1:])
        if not (len(text) >= 22 and rect.width >= 80 and 5 < rect.height < 24
                and rect.y0 > 65 and rect.y1 < doc[pg-1].rect.height-40
                and re.search(r"[A-Za-z]{4}", text)):
            continue
        if any(p[0] == pg and rect.intersects(pdf.Rect(p[1:]) + (-3,-3,3,3)) for p in sensitive):
            continue
        candidates[pg].append(box)
    protected = []
    count = max(len(regions), len(doc))
    title = next(box for _, text, box in first
                 if 50 < box[2] < 121 and len(text) >= 10 and box[4] < abstract_top)
    for pg, boxes in candidates.items():
        quota = count // len(doc) + int(pg <= count % len(doc))
        assert len(boxes) >= quota, (name, pg)
        for i in range(quota):
            piece = title if pg == 1 and i == 0 else boxes[(i+1)*len(boxes)//(quota+1)]
            protected.append({"id": f"k{len(protected)+1:02}", "kind": "preserve", "pieces": [piece]})
    return regions + protected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Replace frozen references after review")
    args = parser.parse_args()
    snapshot = json.loads((ROOT / "source/snapshot.json").read_bytes())
    labels = json.loads((ROOT / "source/line_labels.json").read_bytes())
    for split, papers in snapshot.items():
        folder = ROOT if split == "train" else ROOT / "evaluation" / split
        inputs = folder / ("environment" if split == "train" else "inputs")
        reference = folder / "verifier/expected_output.json"
        annotated = {}
        for paper in papers:
            with pdf.open(inputs / paper["file"]) as doc:
                regions = (annotations(paper["source_id"], doc) if split == "train"
                           else matched(doc, labels[paper["source_id"]], all_lines, identity_words))
                annotated[paper["file"]] = {"pages": len(doc), "regions": regions}
        result = {"split": split, "papers": annotated}
        if args.write:
            reference.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        elif result != json.loads(reference.read_bytes()):
            raise ValueError(f"Region annotations differ for {split}")
        print(f"{split}: {len(papers)} PDFs")


if __name__ == "__main__":
    main()
