# DeepSeek V4 Pro — 10 original-skill task results (2026-10-08)

This publication records **10 independent interpretable original-skill evaluations** of the original GPT/Claude-consistent task shortlist under a fixed DeepSeek V4 Pro + OpenHands harness, plus cross-model atomic-mechanism reviews. It **does not** claim that the ten tasks have common defects in all four models. No DeepSeek fresh Skill repair or F→P Gold was generated.

## Canonical outcomes

| Measure | Result |
|---|---|
| Selected tasks | 10 |
| Canonical independent Original PASS | **2** |
| Canonical independent Original FAIL | **8** |
| DeepSeek mechanisms also seen in previous models | **4 atomic findings across 3 tasks** (PDDL, Python→Scala, Flink) |
| Fresh DeepSeek Skill repairs | **0** |

The historical Flink r001 was **3/3 PASS but reference-contaminated** (oracle/checker/expected material consulted). Its frozen score is retained in `excluded_reference_contaminated/flink-query-r001/benchmark_result.json` and **is not counted** in the canonical 2/10. The replacement r002 blocked answer access, got **2/3 FAIL**, and is the published `tasks/flink-query/original_run`. No hidden reference contents from r001 are republished.

DeepSeek `seismic-phase-picking` passed **2/2** although `termination_reason=max_iterations`; task score and termination are distinct. `dynamic-object-aware-egomotion` passed **11/11**. `shock-analysis-supply` failed **1/9** under an environment missing the task-requested Playwright MCP and with external source-access barriers; this is an attribution confound, not proof of model-only or Skill-only failure.

## Evidence structure

```text
HumanAnnotated-DeepSeekV4Pro-10Tasks-20261008/
  README.md / STATUS.csv / EXCLUSIONS.json / submission.json / MANIFEST.json
  tasks/<task-id>/original_skill/              Full frozen Skill bundle from run inputs
  tasks/<task-id>/original_run/                Canonical scores, requests, ACP, LLM, trainer input, verifier, real pre-verifier outputs
  trajectory_timelines/before/                 10 deterministic chronological tool-action projections
  trajectory_timelines/trajectory_timeline_index.json
  evidence/                                    Original campaign audit, atomic comparison, health and Flink isolation evidence
  excluded_reference_contaminated/flink-query-r001/    Frozen historical score, **not** an independent PASS
```

`trajectory/acp_trajectory.jsonl` remains readable and byte-identical to the actual run; `trajectory/llm_trajectory.jsonl.gz` and `results.jsonl.gz` are gzip-compressed from immutable source bytes to reduce repository size. `MANIFEST.json` lists the exact source locations, source/publication SHA-256 hashes, and sizes. Real pre-verifier exported files are preserved in `artifacts/pre-verifier-inputs.tar.gz`; derived verifier-only copies and redundant `agent`/`trainer` trace replicas are not duplicated. Original historical absolute paths inside immutable result metadata are provenance, not new publication paths.

## How to interpret consistency

See [atomic audit](evidence/atomic-consistency-audit-20261008.json), [cross-model report](evidence/cross-model-consistency-20261008.md), and the [clean Flink run audit](evidence/flink-noanswers-audit-r002-20261008.json). The four reproduced atomic mechanisms are **PDDL plan serialization**, **Scala project/package contract discovery**, **Scala real project validation**, and **Flink output of jobs without qualifying SUBMIT activity**. The two Scala findings are related, not independent instances. The Flink observation has DeepSeek/Gemini Original support and GPT repair-intermediate diagnostic support; it is **not** a four-model-Original consensus.

Other previously annotated defects may be untriggered, reached under different trajectories, or censored by early failures; `FAIL` on the same task does not by itself mean the same Skill defect. The report does not rewrite GPT, Claude, or Gemini Gold labels and does not imply DeepSeek has an F→P repair result.

## Protocol / provenance

- Model: official `deepseek/deepseek-v4-pro`, provider-level thinking enabled/high, max output 32768. OpenHands ACP `reasoning_effort=null` does not imply the provider effort was disabled.
- Frozen task/Original Skill/verifier, OpenHands `skillrepair-v1`, 60 parent-iteration budget and one shared-budget text-only continuation; `n_skill_invocations=0` is not proof that preloaded Skill bodies were absent.
- No new model calls, scores, reruns, or verifier modifications were made during publication. Local source evidence remains unchanged.
- For Flink r002, answer-access restrictions are an explicit environment intervention and are recorded in the isolation receipt. Do not compare its isolation condition with unconstrained original runs as a single-variable model benchmark.

[Canonical result table](STATUS.csv) · [Submission record](submission.json) · [File provenance](MANIFEST.json) · [Read-only source report](evidence/local-report.md)
