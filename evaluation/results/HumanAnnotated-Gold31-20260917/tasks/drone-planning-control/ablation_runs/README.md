# A16 drone-planning-control ablation runs

These runs were executed after the original HumanAnnotated Gold31 publication to audit whether the four historical drone defects should remain separate scoring defects.

The raw `acp_trajectory.jsonl` files are the source of truth. Each run directory follows the same core evidence layout as `repaired_run`: `benchmark_result.json`, `executor_request.json`, `result.json`, and `trajectory/acp_trajectory.jsonl`.

| Run | Repair/control under test | Official result | Reward | Interpretation |
|---|---|---:|---:|---|
| `drone-planning-control-a16-d001-only-r001` | Initial unified tuning/acceptance wording | FAIL, 16/30 | 0.533333 | Agent still returned a failing best-so-far candidate after a finite search; the intended hard gate was not actually enforced. |
| `drone-planning-control-a16-d001-v2-r001` | Strong blocking hard gate; no final failing candidate allowed | PASS, 30/30 | 1.0 | Establishes a fresh F→P route for the unified closed-loop tuning/acceptance mechanism, though the implementation also used a fuller rigid-body model. |
| `drone-planning-control-a16-d001-v3-r001` | Strong hard gate + simplified canonical rotational plant | FAIL, 17/30 | 0.566667 | Agent's own sweep reported all commands passing, but official oracle replay exposed remaining planner/controller/initial-state reproducibility mismatches. |
| `drone-planning-control-a16-d001-v4-r001` | Strong hard gate + benchmark reproducibility controls | PASS, 30/30 | 1.0 | Final clean ablation: official verifier 30/30 with the unified D001 repair while planner/controller/plant/initial-state conventions are held as experimental controls rather than separate Gold defects. |

Final Gold decision from this ablation series: historical D001 and D002 are merged into one per-command closed-loop tuning / hard-acceptance defect; historical D003 and D004 are removed from scoring Gold. The structured ground truth uses `defect_sets = [["D001"]]`.
