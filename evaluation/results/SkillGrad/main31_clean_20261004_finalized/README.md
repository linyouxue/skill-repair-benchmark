# SkillGrad MAIN31 finalized publication

The effective submission contains **28 finalized tasks: LOCAL25 + SERVER3**.
The three SERVER additions are `lab-unit-harmonization`,
`dynamic-object-aware-egomotion`, and `syzkaller-ppdev-syzlang`.
The original 27 task results and submission entries are preserved.

Syzkaller is finalized PASS at S2 under frozen protocol v2 and
`vllm/gpt-5.2`. Its original D0 diagnosis is preserved verbatim. S2 PASS does
not establish that the original diagnosis or final-turn lint repair was correct;
the independent audit's diagnostic-quality limitations remain in force.

The three remaining non-finalized tasks are Azure BGP, energy-market pricing,
and Druid. They are not included. The server paper-anonymizer ownership conflict
is also excluded; its trusted LOCAL result remains effective.

## Publication allowlist

Each task contains its exact repaired Skill and original/repaired run evidence.
For each run, only the original publication-allowlisted files are distributed:

- `executor_request.json`
- `result.json`
- `benchmark_result.json`
- `trajectory/acp_trajectory.jsonl`

Official Markdown timelines and the index provide 28 before/28 after pairs.
LLM trajectories, training `results.jsonl`, rewards/timing sidecars, scoring/CTRF,
verifier stdout, verifier implementation, Gold/oracle, private configuration,
caches and discarded histories are excluded from the current publication tree.
Full canonical evidence is retained privately on the server and in the recovery
export. The private complete S0/S2 artifact gate passed 2/2; the allowlisted public
package is not a self-contained training release.

Earlier PR commits included files outside this allowlist, including hidden test
identifiers in scoring output. They have been removed from the current tree;
earlier GitHub commits may remain accessible. No obvious credentials were found
by the recorded scan; this is not a guarantee that all historical disclosures
have been erased.

## Gold/version mapping pending human review

The existing complete Gold is `evaluation/data/skillsbench87/gold.json`, version
`manual-gold-defects-20260917-v25`, containing 31 tasks and 57 defects.
All 28 submitted task IDs are within that Gold. The inherited submission label
`core25-gold-defects-20260909-v1` instead refers to the Core25 Gold with 7 tasks
and 14 defects, so it must not be presented as a complete MAIN31 scoring target.

This PR preserves the inherited `benchmark_version`, frozen Gold, protocol and
formal results. Proposed correction only: after explicit review, align publication
metadata and the documented evaluation target with the existing complete Gold,
using its explicit path/version. Do not change frozen scoring contents or infer
new scores from this metadata correction.

Human review is required before merging. Current-tree allowlist compliance is
restored, but Gold metadata alignment and historical disclosure remain review items.
