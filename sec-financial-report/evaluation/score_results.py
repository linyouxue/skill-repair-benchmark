"""Score an actual SEC output against one evaluation group's reference."""

import argparse
import json
from pathlib import Path
import sys

from prepare_task import PACKAGE, SPLITS, split_paths

sys.path.insert(0, str(PACKAGE / "verifier"))
from score_accuracy import load_reference, score


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True, choices=SPLITS)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = score(args.actual, load_reference(split_paths(args.group)[1]))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("accuracy", "correct_items", "denominator")}))
