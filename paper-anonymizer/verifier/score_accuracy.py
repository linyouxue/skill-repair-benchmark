"""Grade the submitted PDFs against the private region index. No network or model."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
import pymupdf as pdf

ZOOM = pdf.Matrix(1.5, 1.5)


def render(page):
    pix = page.get_pixmap(matrix=ZOOM, colorspace=pdf.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def visible_text_centers(page):
    centers = []
    for block in page.get_text("rawdict", flags=0)["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span["chars"]:
                    if char["c"].strip():
                        x0, y0, x1, y1 = char["bbox"]
                        centers.append(((x0+x1)/2, (y0+y1)/2))
    return np.asarray(centers, dtype=float).reshape(-1, 2)


def crop(image, rect):
    box = (rect * ZOOM).irect & pdf.IRect(0, 0, image.shape[1], image.shape[0])
    return image[box.y0:box.y1, box.x0:box.x1]


def solid_mask(patch):
    inner = patch[1:-1, 1:-1] if min(patch.shape) > 3 else patch
    return bool(inner.size and ((inner >= 245).mean() >= 0.998 or (inner <= 10).mean() >= 0.998))


def cleared_word(rect, source, answer, chars, active_links):
    if any(rect.intersects(link) for link in active_links):
        return False
    x, y = chars.T
    if np.any((x >= rect.x0) & (x < rect.x1) & (y >= rect.y0) & (y < rect.y1)):
        return False
    before, after = crop(source, rect), crop(answer, rect)
    yy, xx = np.nonzero(before < 205)
    if not len(xx):
        return True
    # Size masks to printed ink, allowing smaller black boxes around individual
    # names and leaving punctuation and superscript affiliation numbers intact.
    tight = after[yy.min():yy.max()+1, xx.min():xx.max()+1]
    return solid_mask(tight)


def matches_piece(kind, rect, source, answer, chars, active_links, source_words):
    before, after = crop(source, rect), crop(answer, rect)
    ink = before < 200
    if not ink.any() or before.shape != after.shape:
        return False
    if kind == "preserve":
        diff = np.abs(before.astype(np.int16) - after.astype(np.int16))
        return bool(diff[ink].mean() <= 15 and diff.mean() <= 8)
    # Text underneath a painted rectangle remains extractable in normal PDFs.
    x, y = chars.T
    if np.any((x >= rect.x0) & (x < rect.x1) & (y >= rect.y0) & (y < rect.y1)):
        return False
    if any(rect.intersects(link) for link in active_links):
        return False
    # Every old glyph and its immediate background must be cleared or covered.
    # Shrink by a pixel to ignore antialiasing along the edge of a black mask.
    if solid_mask(after):
        return True
    # A line can use separate black masks for the individual words.
    words = [word & rect for word in source_words if (word.tl + word.br) / 2 in rect]
    return bool(words) and all(solid_mask(crop(answer, word)) for word in words)


def grade_paper(source, answer, spec):
    regions = spec["regions"]
    rows = {r["id"]: {"kind": r["kind"], "pieces": [False] * len(r["pieces"]), "correct": False}
            for r in regions}
    result = {"status": "missing", "regions": rows, "clean_metadata": False}
    if not answer.is_file():
        return result
    try:
        with pdf.open(source) as src, pdf.open(answer) as sub:
            if (not sub.is_pdf or sub.needs_pass or len(sub) != len(src)
                    or any(p.rect != q.rect or p.rotation != q.rotation for p, q in zip(src, sub))):
                result["status"] = "invalid_layout"
                return result
            for i, (old, new) in enumerate(zip(src, sub), 1):
                before, after = render(old), render(new)
                chars = visible_text_centers(new)
                active_links = [link["from"] for link in new.get_links() if link.get("uri") or link.get("file")]
                source_words = [pdf.Rect(w[:4]) for w in old.get_text("words")]
                for reg in regions:
                    for j, (p, *coords) in enumerate(reg["pieces"]):
                        if p == i:
                            if reg["kind"] == "byline":
                                passed = all(cleared_word(pdf.Rect(w[1:]), before, after, chars, active_links)
                                             for w in reg["identity_words"])
                            else:
                                passed = matches_piece(reg["kind"], pdf.Rect(coords), before, after, chars,
                                                       active_links, source_words)
                            rows[reg["id"]]["pieces"][j] = passed
            for row in rows.values():
                row["correct"] = all(row["pieces"])
            if not any(row["correct"] for row in rows.values() if row["kind"] == "preserve"):
                result["status"] = "no_preserved_content"
                for row in rows.values():
                    row["correct"] = False
                return result
            result["clean_metadata"] = (not any((sub.metadata or {}).get(k) for k in
                                                ("author", "title", "subject", "keywords"))
                                        and not sub.get_xml_metadata().strip())
            result["status"] = "graded"
    except (RuntimeError, ValueError, OSError):
        result["status"] = "unreadable"
        for row in rows.values():
            row["correct"] = False
    return result


def score(reference, source_dir, output):
    ref = reference["papers"]
    totals = {k: {"correct": 0, "total": 0} for k in ("redact", "preserve", "metadata")}
    papers = {}
    for name, spec in ref.items():
        source = source_dir / name
        if not source.is_file():
            raise FileNotFoundError(f"Missing verifier input: {source}")
        paper = grade_paper(source, output / name, spec)
        papers[name] = paper
        for row in paper["regions"].values():
            count = totals["preserve" if row["kind"] == "preserve" else "redact"]
            count["total"] += 1
            count["correct"] += int(row["correct"])
        totals["metadata"]["total"] += 1
        totals["metadata"]["correct"] += int(paper["clean_metadata"])
    correct = sum(t["correct"] for t in totals.values())
    total = sum(t["total"] for t in totals.values())
    return {"split": reference["split"], "correct": correct, "total": total, "accuracy": correct/total,
            "by_type": totals, "papers": papers}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=Path(__file__).with_name("expected_output.json"))
    parser.add_argument("--source-dir", type=Path, default=Path("/source"))
    parser.add_argument("--actual", type=Path, default=Path("/root/redacted"))
    parser.add_argument("--log-dir", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.log_dir.mkdir(parents=True, exist_ok=True)
    reward = args.log_dir / "reward.txt"
    reward.unlink(missing_ok=True)
    started = int(time.time() * 1000)
    report = score(json.loads(args.reference.read_bytes()), args.source_dir, args.actual)
    tests = []
    for name, paper in report["papers"].items():
        items = {key: row["correct"] for key, row in paper["regions"].items()}
        items["metadata"] = paper["clean_metadata"]
        for item, passed in items.items():
            tests.append({"name": f"{name}/{item}", "status": "passed" if passed else "failed"})
    total, passed = report["total"], report["correct"]
    summary = {"tests": total, "passed": passed, "failed": total - passed, "skipped": 0, "pending": 0,
               "other": 0, "start": started, "stop": int(time.time() * 1000)}
    ctrf = {"results": {"tool": {"name": "paper-anonymizer"}, "summary": summary, "tests": tests}}
    for name, value in (("accuracy.json", report), ("ctrf.json", ctrf)):
        (args.log_dir / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    reward.write_text(f"{report['accuracy']}\n", encoding="utf-8")
    print(f"{passed}/{total} ({report['accuracy']:.2%})")


if __name__ == "__main__":
    main()
