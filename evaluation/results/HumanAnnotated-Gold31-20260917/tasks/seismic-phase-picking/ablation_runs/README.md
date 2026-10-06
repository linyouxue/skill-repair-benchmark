# A09 seismic-phase-picking ablation runs

This directory preserves the valid A09 screening evidence that was run after the original HumanAnnotated Gold31 publication.

The experiment asks whether the single `C03` atom — probability thresholding / local peaks / NMS — is sufficient by itself, against the historical successful WML-derived `M_E035` control.

| Run | Arm | Official result | Key metrics | Interpretation |
|---|---|---:|---|---|
| `a09-c03-prebuilt1-r004` | `A09/C03` single-atom screen | FAIL | P F1=0.730; S F1=0.566 | P meets the 0.700 requirement, but S remains below the 0.600 requirement. C03 alone is insufficient in this run. |
| `a09-m_e035-prebuilt1-r001` | `A09/M_E035` historical control | PASS | P F1=0.865; S F1=0.712 | The historical successful control remains above both task thresholds under the same task digest/model route. |

The earlier `a09-c03-prebuilt1-r001`–`r003` attempts are intentionally excluded from the formal trajectory index because they are non-experimental failures: disallowed config override, Docker address-pool exhaustion, and container working-directory failure respectively. The first valid C03 execution is `r004`.

Both retained runs were recorded by the older ablation harness with `experimental_controls.comparison_status = diagnostic-non-comparable`; that harness metadata is preserved verbatim in `executor_request.json`/`benchmark_result.json` rather than rewritten.

The raw `trajectory/acp_trajectory.jsonl` files are the source of truth. Verifier stdout is retained because it contains the phase-specific F1 values used to interpret the ablation.
