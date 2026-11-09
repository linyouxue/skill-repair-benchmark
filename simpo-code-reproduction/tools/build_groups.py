"""Create the frozen tensors, or independently verify the existing references."""

import argparse
import json
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
import torch

PACKAGE = Path(__file__).resolve().parents[1]
TENSORS = ("policy_chosen_logps.pt", "policy_rejected_logps.pt")
ITEMS = 100


def load_tensors(directory: Path) -> tuple[np.ndarray, np.ndarray]:
    chosen, rejected = (
        torch.load(directory / name, map_location="cpu", weights_only=True).numpy()
        for name in TENSORS
    )
    for array in (chosen, rejected):
        if array.shape != (ITEMS,) or array.dtype != np.float32 or not np.isfinite(array).all():
            raise ValueError(f"Unexpected input tensor: {directory}")
    return chosen, rejected


def reference(chosen: np.ndarray, rejected: np.ndarray) -> np.ndarray:
    margin = 2.0 * (chosen.astype(np.float64) - rejected.astype(np.float64)) - 0.5
    return np.logaddexp(0.0, -margin).astype(np.float32)


def decimal_reference(chosen: np.ndarray, rejected: np.ndarray) -> np.ndarray:
    values = []
    with localcontext() as context:
        context.prec = 50
        for good, bad in zip(chosen, rejected, strict=True):
            # exp(-score) is inverse probability. Form their ratio first.
            inverse_good = (-Decimal(float(good))).exp()
            inverse_bad = (-Decimal(float(bad))).exp()
            penalty = Decimal("0.5").exp() * (inverse_good / inverse_bad) ** 2
            values.append(float((1 + penalty).ln()))
    return np.array(values, dtype=np.float64)


def build_group(directory: Path, seed: int, distributions: list[dict]) -> None:
    inputs = directory / "inputs"
    inputs.mkdir(parents=True, exist_ok=False)
    rng = np.random.Generator(np.random.PCG64(seed))
    for name, params in zip(TENSORS, distributions, strict=True):
        samples = rng.normal(params["mean"], params["std"], ITEMS)
        # Scores are log probabilities.
        array = np.minimum(samples, 0.0).astype(np.float32)
        torch.save(torch.from_numpy(array), inputs / name)
    verifier = directory / "verifier"
    verifier.mkdir()
    np.savez_compressed(verifier / "loss.npz", losses=reference(*load_tensors(inputs)))


def verify_group(inputs: Path, gt_path: Path) -> tuple[dict, set]:
    chosen, rejected = load_tensors(inputs)
    with np.load(gt_path, allow_pickle=False) as bundle:
        gt = bundle["losses"]
    computed = reference(chosen, rejected)
    independent = decimal_reference(chosen, rejected)
    if gt.shape != (ITEMS,) or not np.isfinite(gt).all():
        raise ValueError(f"Unexpected reference shape or values: {gt_path}")
    np.testing.assert_allclose(computed, independent, rtol=1e-7, atol=1e-9)
    np.testing.assert_allclose(gt, independent, rtol=1e-5, atol=1e-6)
    pairs = set(zip(chosen.tolist(), rejected.tolist(), strict=True))
    if len(pairs) != ITEMS:
        raise ValueError(f"Repeated tensor pair: {inputs}")
    return {
        "items_verified": ITEMS,
        "max_abs_error_gt_vs_decimal": float(np.max(np.abs(gt - independent))),
    }, pairs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Create new group directories")
    args = parser.parse_args()
    evaluation = PACKAGE / "evaluation"
    manifest = json.loads((evaluation / "manifest.json").read_text(encoding="utf-8"))
    reports = {}
    original = PACKAGE / "environment/SimPO/unit_test/tensors"
    reports["original"], seen = verify_group(original, PACKAGE / "verifier/loss.npz")
    if args.build:
        for group, info in manifest["groups"].items():
            build_group(evaluation / group, info["seed"], manifest["distributions"])
    for group in manifest["groups"]:
        directory = evaluation / group
        reports[group], pairs = verify_group(directory / "inputs", directory / "verifier/loss.npz")
        if seen & pairs:
            raise ValueError(f"Repeated input pair across splits: {group}")
        seen.update(pairs)
    print(json.dumps(reports, indent=2))
