# SKILL.md

## When to use
Use this skill when a benchmark asks you to **reproduce a paper-defined loss function inside an existing codebase**, then **run a provided unit test with fixed tensors** to produce an **evaluator-consumable artifact** (e.g., an `.npz` file containing loss values). This applies when:
- A specific function/method (e.g., a trainer’s `*_loss`) must be implemented according to a **PDF paper** in the repo.
- You must **not modify the unit test**.
- You must **set up the Python environment** and **log reproducibility info** (Python version + `pip freeze`) to a specified file.
- Final evaluation depends on saving computed outputs to a specified path/format (e.g., `loss.npz` with a required key).

Before acting, gather:
- The target function signature and how it is called (inputs, expected shapes, reduction behavior).
- Any adjacent trainer utilities (e.g., log-prob computation, masking, label shifting, temperature/beta scaling, reference model usage).
- The loss definition from the paper: formula, constants, sign conventions, averaging, and any stabilizing transforms (e.g., `logsigmoid` vs `log(σ)`).
- Unit test expectations: output type/shape, device/dtype assumptions, and exact required file/key names.

## Possible Failure Modes
- **Wrong mathematical form vs. paper**: mixing up signs (maximize vs minimize), using `-logsigmoid(x)` vs `logsigmoid(-x)`, or swapping chosen/rejected terms.
- **Reduction mismatch**: returning per-token/per-example vs scalar; averaging across the wrong dimension (batch vs sequence vs pair count).
- **Masking/length handling errors**: failing to apply attention masks, including padding tokens, or mis-shifting labels for next-token prediction.
- **Incorrect log-prob aggregation**: using mean log-prob per token when the paper uses sum (or vice versa), or failing to normalize by length if required.
- **Device/dtype pitfalls**: mixing CPU/GPU tensors, float16 instability, or unintended dtype casts that change determinism.
- **Numerical instability**: using `torch.log(torch.sigmoid(x))` instead of `torch.nn.functional.logsigmoid(x)`; overflow with large magnitude logits.
- **Incorrect use of reference/baseline** (if applicable): forgetting a reference term, detaching incorrectly, or applying scaling (beta/temperature) in the wrong place.
- **Breaking the surrounding trainer contract**: changing method signature, returning extra values, or altering external behavior that unit tests rely on.
- **Artifact formatting mistakes**: saving the wrong key name in `.npz`, wrong array shape, wrong file path, or saving Python lists instead of NumPy arrays.
- **Reproducibility logging omitted**: not writing `python -VV` and `pip freeze` output to the required file, or writing to the wrong location.
- **Modifying the unit test**: any change invalidates the benchmark even if the loss is correct.

## Possible procedures
1. **Map the call chain and expected outputs**
   - Locate the target method implementation site and search for where it is invoked.
   - Identify expected return type: scalar tensor, vector of per-sample losses, or dictionary.
   - Inspect existing trainer patterns (other losses, helper functions for log-probs, masking).

2. **Extract the paper loss definition precisely**
   - From the PDF, capture:
     - The core expression (difference of scores/log-probs, margins, scaling constants).
     - Whether it is based on sequence-level log-likelihood sums or length-normalized averages.
     - Any “reference model” or baseline terms and whether they are detached.
     - The final reduction (mean over batch/pairs).
   - Note implementation-relevant details: stable functions recommended, temperature/beta placement.

3. **Implement with tensor-safe, vectorized PyTorch ops**
   - Prefer `torch.nn.functional.logsigmoid`, `softplus`, or equivalent stable forms.
   - Maintain consistent shapes:
     - Compute per-sequence scores from per-token log-probs using the exact aggregation specified.
     - Apply attention masks/label masks correctly before summing/averaging.
   - Keep gradients correct: avoid unintended `.detach()` unless the paper explicitly requires it.
   - Preserve existing trainer conventions: device, dtype, and return structure.

4. **Align reductions and normalization**
   - Decide (based on the paper and existing code) whether to:
     - Sum log-probs over valid tokens, then optionally normalize by token count.
     - Compute per-example losses then `mean()` across batch.
   - Add explicit comments for each reduction step to avoid silent mismatches.

5. **Run the provided unit test unmodified**
   - Execute exactly the unit test script the benchmark specifies.
   - Capture the produced loss tensor(s) from the test harness path (don’t “recompute differently” outside of it unless the benchmark instructs).

6. **Write evaluation artifact**
   - Convert losses to a NumPy array with deterministic ordering/shape.
   - Save to the required `.npz` path with the exact required key name.
   - Ensure the file contains exactly what the evaluator will load (e.g., `np.load(...)[key]` works).

7. **Log environment for reproducibility**
   - Write the outputs of:
     - `python -VV`
     - `python -m pip freeze`
   - into the required file path.
   - If multiple Python environments exist, ensure you’re logging the one used to run the unit test.

8. **Recovery / debugging loop**
   - If unit test fails or outputs differ:
     - Re-check sign conventions, scaling constants, and whether scores are sums vs averages.
     - Print/inspect intermediate tensors (shapes, min/max, masked token counts) without modifying the unit test (instrument the trainer code if allowed).
     - Validate that padding tokens contribute zero and that token counts match expectations.

## Verification Checklist
- [ ] Implemented only the targeted function/method; did not change unit test files or unrelated logic.
- [ ] Loss matches the paper’s formula: correct sign, scaling (beta/temperature/margin), and reference/baseline usage (if any).
- [ ] Correct masking/label shifting: padding tokens do not affect scores; aggregation uses the intended valid-token set.
- [ ] Correct reductions: per-example vs scalar behavior matches what the trainer/unit test expects.
- [ ] Numerically stable ops used (`logsigmoid`/`softplus`), no avoidable overflow/underflow.
- [ ] Unit test script runs successfully **as provided** in the benchmark.
- [ ] Saved output file exists at the required path, is a valid `.npz`, and contains the required key with the expected array shape/dtype.
- [ ] Wrote `python -VV` and `python -m pip freeze` outputs to the required reproducibility log file (from the same environment that ran the test).
- [ ] Did not copy concrete constants/paths/ids from unrelated retrieved examples; only used them for general tactics (file save/load discipline, reproducibility habits).
