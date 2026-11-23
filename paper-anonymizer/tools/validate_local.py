"""Offline controls on real inputs, including a painted-but-copyable submission."""
import argparse
from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf as pdf
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))
sys.path.insert(0, str(ROOT / "verifier"))
from prepare_task import SPLITS, prepare
from score_accuracy import score as grade


def make_submission(src, dest, spec, mode, skip=None):
    with pdf.open(src) as doc:
        for reg in spec["regions"]:
            if reg["kind"] == "preserve" or reg["id"] == skip:
                continue
            if mode == "first_page" and reg["pieces"][0][0] != 1:
                continue
            if mode == "byline_only" and reg["kind"] != "byline":
                continue
            for p, *coords in reg["pieces"]:
                rect = pdf.Rect(coords) + (-0.3,-0.3,0.3,0.3)
                if mode == "overlay":
                    doc[p-1].draw_rect(rect, color=None, fill=(0,0,0), overlay=True)
                else:
                    fill = (0,0,0) if mode == "black" else (1,1,1)
                    doc[p-1].add_redact_annot(rect, fill=fill, cross_out=False)
        if mode != "overlay":
            for page in doc:
                page.apply_redactions(images=2, graphics=0)
        doc.set_metadata({})
        doc.del_xml_metadata()
        doc.save(dest, garbage=4, deflate=True)


def brief(result):
    return {k: result[k] for k in ("correct", "total", "accuracy", "by_type")}


def verify(work):
    ref, inputs = {}, {}
    for split in SPLITS:
        exported = prepare(split, work / split / "tasks" / "paper-anonymizer")
        inputs[split] = exported / "environment"
        ref[split] = json.loads((exported / "verifier/expected_output.json").read_bytes())["papers"]
        assert not list(inputs[split].rglob("expected_output.json"))
        assert sorted(p.name for p in inputs[split].glob("*.pdf")) == sorted(ref[split])

    def score(split, output):
        return grade({"split": split, "papers": ref[split]}, inputs[split], output)

    sources = json.loads((ROOT / "source/snapshot.json").read_bytes())
    names = [paper["source_id"] for group in sources.values() for paper in group]
    assert set(ref) == set(sources) == set(SPLITS)
    assert len(names) == len(set(names)) == 21
    for split, papers in ref.items():
        for name, paper in papers.items():
            with pdf.open(inputs[split] / name) as original:
                assert len(original) == paper["pages"]
    out = {}
    for group, papers in ref.items():
        counts = Counter(r["kind"] for s in papers.values() for r in s["regions"])
        blocks = 2 if group in ("group_01", "group_03") else 1
        per_block = 25 if group in ("group_02", "group_03") else 20
        assert [p["pages"] for p in papers.values()] == [23, 5, 12] * blocks
        assert [p["source_family"] for p in sources[group]] == ["arxiv", "interspeech", "icml_workshop"] * blocks
        assert counts["preserve"] == 44 * blocks
        targets = sum(counts.values()) - counts["preserve"]
        assert targets == per_block * blocks
        outside = targets - counts["byline"]
        if group == "group_04":
            assert (outside, targets) == (13, 20)
        else:
            assert outside * 5 == targets * 2
        for start in range(0, len(papers), 3):
            triplet = list(papers.values())[start:start + 3]
            assert sum(r["kind"] != "preserve" for spec in triplet for r in spec["regions"]) == per_block
        for spec in papers.values():
            covered_pages = {piece[0] for r in spec["regions"] if r["kind"] == "preserve" for piece in r["pieces"]}
            assert covered_pages == set(range(1, spec["pages"] + 1))
        out[group] = {"source_papers": len(papers), "pages": sum(s["pages"] for s in papers.values()),
                      "field_counts": dict(counts)}
        modes = ["oracle", "unchanged", "first_page"]
        if group in ("train", "group_04"):
            modes.append("byline_only")
        for mode in modes:
            folder = work / group / mode
            folder.mkdir(parents=True)
            if mode == "unchanged":
                folder = inputs[group]
            else:
                for name, spec in papers.items():
                    make_submission(inputs[group] / name, folder / name, spec, mode)
            res = score(group, folder)
            red = res["by_type"]["redact"]
            if mode == "oracle" and res["correct"] != res["total"]:
                raise AssertionError((group, mode, [(n,k,v) for n,p in res["papers"].items()
                                      for k,v in p["regions"].items() if not v["correct"]][:12]))
            if mode == "unchanged":
                assert red["correct"] == 0 and res["by_type"]["preserve"]["correct"] == counts["preserve"]
            if mode == "first_page":
                misses = sum(r["kind"] != "preserve" and r["pieces"][0][0] > 1
                             for spec in papers.values() for r in spec["regions"])
                assert red["total"] - red["correct"] == misses
                if group in ("train", "group_04"):
                    assert misses == 2
            if mode == "byline_only":
                assert red["correct"] == counts["byline"] and res["total"] - res["correct"] == outside
            out[group][mode] = brief(res)
        missing = score(group, work / "empty")
        assert missing["correct"] == 0
        out[group]["missing"] = brief(missing)
    group = "group_02"
    folder = work / group / "oracle"
    name, spec = next((name, spec) for name, spec in ref[group].items() if spec["pages"] == 5)
    src = inputs[group] / name
    dest = folder / name
    saved = dest.read_bytes()
    old = out[group]["oracle"]["total"]
    dest.unlink()
    make_submission(src, dest, spec, "oracle", skip=spec["regions"][0]["id"])
    assert score(group, folder)["correct"] == old-1
    dest.unlink()
    make_submission(src, dest, spec, "overlay")
    row = score(group, folder)["papers"][name]
    assert all(not v["correct"] for v in row["regions"].values() if v["kind"] != "preserve")
    dest.unlink()
    make_submission(src, dest, spec, "black")
    assert score(group, folder)["correct"] == old
    # Flatten the original rendered page: copying is impossible but the names
    # still read normally. Exercise the image check on a text-free participant.
    with pdf.open(src) as original, pdf.open() as raster:
        for page in original:
            out_page = raster.new_page(width=page.rect.width, height=page.rect.height)
            pix = page.get_pixmap(matrix=pdf.Matrix(1.5,1.5), colorspace=pdf.csGRAY)
            out_page.insert_image(out_page.rect, pixmap=pix)
        raster.save(dest, deflate=True)
    row = score(group, folder)["papers"][name]
    assert row["status"] == "graded"
    assert all(not v["correct"] for v in row["regions"].values() if v["kind"] != "preserve")
    with pdf.open(stream=saved, filetype="pdf") as doc:
        keep = next(r for r in spec["regions"] if r["kind"] == "preserve")
        pg, *box = keep["pieces"][0]
        doc[pg-1].add_redact_annot(pdf.Rect(box), fill=(1,1,1))
        doc[pg-1].apply_redactions()
        doc.save(dest, garbage=4)
    assert score(group, folder)["correct"] == old-1
    with pdf.open(stream=saved, filetype="pdf") as doc:
        doc.set_metadata({"author":"unremoved author"}); doc.save(dest)
    assert score(group, folder)["correct"] == old-1
    with pdf.open() as blank, pdf.open(src) as doc:
        for page in doc:
            blank.new_page(width=page.rect.width, height=page.rect.height)
        blank.save(dest)
    assert score(group, folder)["papers"][name]["status"] == "no_preserved_content"
    dest.write_bytes(b"invalid document")
    assert score(group, folder)["papers"][name]["status"] == "unreadable"
    out["negative_checks"] = {"one_missed_field_costs_one_point": True, "overlay_rejected": True,
                              "one_dirty_metadata_costs_one_point": True, "blank_rejected": True,
                              "corrupt_rejected": True, "true_black_redaction_accepted": True,
                              "visible_raster_names_rejected": True, "one_erased_keep_costs_one_point": True}
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "tools/validation.json")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="paper-anon-check-") as folder:
        result = verify(Path(folder))
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    for group, info in result.items():
        if "oracle" in info:
            print(group, info["oracle"]["correct"], "/", info["oracle"]["total"], flush=True)
