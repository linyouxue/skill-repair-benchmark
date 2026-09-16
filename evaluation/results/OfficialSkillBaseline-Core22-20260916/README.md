# Official Skill baseline — Core-22 representative runs

This directory archives one representative SkillsBench execution for each of 22 tasks used in the manual acceptance audit.

It is an **execution-evidence archive**, not a repair-method submission, so it intentionally does not contain a `submission.json` or any repaired Skill bundle.

## Selection policy

- The representative run must match the manually accepted PASS/FAIL label in `VALIDATION.json`.
- A completion-guard run is preferred when a matching run exists.
- If no matching guard run exists, the matching non-guard run is used.
- The full selected run evidence is retained: executor/result/config metadata, raw trajectories, trainer exports, verifier outputs, artifacts when present, timing/reward files, and the run-specific log when available.
- Official Skill bundle contents are excluded. In particular, `inputs/skills/**` and legacy `input-skill-bundle/**` are not archived here.

`MANIFEST.json` records source selection and provenance. `VALIDATION.json` records the accepted result and the observed result for every task. `STATUS.csv` is a compact tabular view.

## Layout

```text
OfficialSkillBaseline-Core22-20260916/
├── README.md
├── MANIFEST.json
├── VALIDATION.json
├── STATUS.csv
├── tasks/
│   └── <task-id>/
│       ├── run_selection.json
│       └── original_run/
│           ├── executor_request.json      # when emitted by that runner
│           ├── benchmark_result.json      # when emitted by that runner
│           ├── result.json
│           ├── config.json
│           ├── prompts.json
│           ├── results.jsonl
│           ├── rewards.jsonl
│           ├── timing.json
│           ├── agent/
│           ├── trajectory/
│           ├── trainer/
│           ├── verifier/
│           ├── artifacts/                 # when present
│           ├── logs/                      # run-specific outer log, when available
│           └── run_metadata/              # legacy runner metadata only
└── trajectory_timelines/
    ├── before/
    ├── after/
    ├── unknown/
    └── trajectory_timeline_index.json
```

The Markdown timelines were generated with the repository's `evaluation/results/export_trajectory.py`; raw JSONL remains the source of truth.

## Accepted task outcomes

| Task | Accepted outcome | Guard used in selected run |
|---|---|---:|
| `software-dependency-audit` | FAIL | yes |
| `suricata-custom-exfil` | PASS | no |
| `fix-erlang-ssh-cve` | PASS | no |
| `sec-financial-report` | FAIL | no |
| `weighted-gdp-calc` | PASS | no |
| `3d-scan-calc` | PASS | no |
| `r2r-mpc-control` | PASS | no |
| `lean4-proof` | PASS | no |
| `pddl-tpp-planning` | PASS | yes |
| `paratransit-routing` | FAIL | no |
| `threejs-to-obj` | PASS | no |
| `mario-coin-counting` | PASS | no |
| `video-silence-remover` | FAIL | no |
| `exoplanet-detection-period` | FAIL | no |
| `crystallographic-wyckoff-position-analysis` | PASS | no |
| `glm-lake-mendota` | PASS | no |
| `court-form-filling` | PASS | no |
| `pptx-reference-formatting` | PASS | yes |
| `sales-pivot-analysis` | PASS | no |
| `dialogue-parser` | FAIL | no |
| `python-scala-translation` | FAIL | no |
| `fix-visual-stability` | PASS | no |

`VALIDATION.json` reports 22/22 selected runs matching these accepted outcomes.

## Compatibility notes

### Legacy runner metadata

`weighted-gdp-calc`, `3d-scan-calc`, and `paratransit-routing` came from the older WSL runner. Their original per-task run directories are preserved, but runner-specific injection/debug files such as `forced-*`, `input-skill-*`, `benchflow-compat/`, PID files, and completion-prompt scaffolding were intentionally omitted during normalization. Only the actual task run plus `bench.log`, `health-summary.json`, `run-config.json`, and `task-manifest.json` are retained.

Those legacy `result.json` files predate `evaluation_condition`, so `export_trajectory.py` correctly places their readable timelines under `trajectory_timelines/unknown/` rather than inventing metadata.

### `sec-financial-report`

The primary GPT-5.2 Original-Skill server run, `sec-financial-report-original-skill-server-r003`, was not mirrored back to the local archive. The locally available valid FAIL run `sec-financial-report-round-1-r002` is therefore used as the representative failure evidence. It has the requested FAIL outcome, but its metadata identifies `condition=method-skill`; consequently the trajectory exporter places its readable timeline under `trajectory_timelines/after/`. This substitution is explicitly recorded in `MANIFEST.json`, `VALIDATION.json`, and the task's `run_selection.json`.

No official Skill bundle content from that run is included.
