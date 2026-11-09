"""Score the 100 loss positions without replacing the official verifier."""

import argparse
import json
from pathlib import Path
from zipfile import BadZipFile

import numpy as np

from prepare_task import GROUPS, PACKAGE

ITEMS = 100
RTOL = 1e-5
ATOL = 1e-6


def read_losses(path: Path) -> np.ndarray:
    with np.load(path, allow_pickle=False) as output:
        losses = output["losses"]
    if losses.shape != (ITEMS,) or losses.dtype.kind not in "fiu":
        raise ValueError("Expected a real-valued losses vector of shape (100,)")
    return losses


def score(actual: Path, reference: Path) -> dict:
    expected = read_losses(reference)
    if not np.isfinite(expected).all():
        raise ValueError("Reference losses must be finite")
    status = "scored"
    try:
        values = read_losses(actual)
    except FileNotFoundError:
        status = "missing_output"
    except (OSError, ValueError, KeyError, TypeError, EOFError, BadZipFile):
        status = "invalid_output"

    matches = np.zeros(ITEMS, dtype=bool)
    if status == "scored":
        matches = np.isfinite(values) & np.isclose(expected, values, rtol=RTOL, atol=ATOL)
    correct = int(matches.sum())
    return {
        "status": status,
        "accuracy": correct / ITEMS,
        "correct_count": correct,
        "expected_count": ITEMS,
        "incorrect_indices": np.flatnonzero(~matches).tolist(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=("original", *GROUPS), required=True)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    source = PACKAGE if args.group == "original" else PACKAGE / "evaluation" / args.group
    result = json.dumps(score(args.actual, source / "verifier/loss.npz"), indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8") as report:
            report.write(result)
    print(result, end="")
