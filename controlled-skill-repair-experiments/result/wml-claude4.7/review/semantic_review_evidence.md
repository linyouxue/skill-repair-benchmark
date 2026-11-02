# WML Claude 4.7 controlled-dataset semantic review

This review compares each final candidate bundle with the organizer's `gold_repair` descriptions and `repair_atoms`. Native verifier outcomes are recorded separately and were not used as a substitute for semantic judgment. `false` includes incomplete or contradictory repairs. The review was performed manually by Codex and is not an independent human sign-off.

Summary: 5/22 target bundles are semantically repaired under the strict all-required-parts criterion. All 12 leave-one-out candidates preserve their supplied non-target Gold semantics; non-target preservation is not applicable to location and all-faults conditions.

## location-data-to-d3

Target `false`. The candidate adds pointer-transparent SVG labels and bidirectional chart/table selection, but does not add the Gold blocking check that performs a real browser click at a representative mark center and repairs intercepted-pointer or timeout failures.

## location-dialogue-parser

Target `false`. The candidate explicitly requires adding and serializing `Node(id="End")`; Gold requires the opposite default—End is a terminal edge target only unless an explicit content-bearing End section exists.

## location-flink-query

Target `false`. The candidate proposes a broad terminal event set including FINISH/KILL/FAIL/CANCEL and does not fully encode the lifecycle-only/null-aggregate exclusion. Both RI requirements are therefore incomplete.

## location-manufacturing-equipment-maintenance

Target `true`. The candidate establishes all five exact JSON deliverables as a blocking completion contract and unconditionally selects the global minimum per-TC TAL with lexical `tc_id` tie-break.

## location-pddl-airport-planning

Target `false`. The problem-aware writer signature is repaired, but the Skill still lacks the required canonical IPC one-action-per-line contract, prohibition on handwritten/function-call serialization, and exact-file parse plus PlanValidator round trip.

## single-fix-build-google-auto-RI-001

Target `false`; non-target `true`. Generic Maven reproduction was added, but the candidate does not require switching to the CI-declared historical JDK and replaying the exact `build-pom.xml verify` command before editing. RI-002 nested-project guidance remains preserved.

## single-fix-build-google-auto-RI-002

Target `false`; non-target `true`. Nested Invoker classification is explained, but the candidate omits the required coherent dependency synchronization set for the Google Auto functional POM. RI-001 historical-JDK reproduction guidance remains semantically intact.

## single-fix-build-google-auto-all

Target `false`. The candidate provides general reproduction and nested-POM guidance, but does not jointly supply the historical JDK gate and concrete functional-test dependency synchronization required by RI-001 and RI-002.

## single-flink-query-RI-001

Target `false`; non-target `true`. A completion predicate is inserted, but its FINISH/KILL/FAIL examples omit the explicit Gold prohibition against broadening a task-specified completion state. The RI-002 activity-eligibility gate remains intact.

## single-flink-query-RI-002

Target `false`; non-target `true`. The edit focuses on qualifying versus non-qualifying terminal states rather than the held-out requirement that lifecycle-only keys or null aggregates must never emit. RI-001 exact-state semantics remain present in equivalent wording.

## single-flink-query-all

Target `false`. The three predicates are named, but the exact FINISH-state restriction and null-aggregate/lifecycle-only blocking gate are not both implemented.

## single-manufacturing-equipment-maintenance-RI-001

Target `true`; non-target `true`. The five exact output files, JSON parsing, schema and completion checklist are blocking requirements; the supplied minimum-TAL repair is preserved.

## single-manufacturing-equipment-maintenance-RI-002

Target `true`; non-target `true`. The candidate unconditionally reduces all valid per-TC TAL values by global minimum with lexical tie-break; the five-file completion gate is preserved.

## single-manufacturing-equipment-maintenance-all

Target `true`. Both the full deliverable completion gate and Q02 global-minimum TAL selection are present.

## single-sec-financial-report-RI-001

Target `false`; non-target `true`. Commands are changed to relative `13f-analyzer/scripts/...` paths while execution is documented from `/root`; Gold requires absolute `/skills/...` paths. RI-002 and RI-003 remain preserved.

## single-sec-financial-report-RI-002

Target `false`; non-target `true`. The candidate explicitly instructs counting unique CUSIPs, directly contradicting Gold's stock-filtered row count and its warning not to use unique CUSIPs. Other repairs remain preserved.

## single-sec-financial-report-RI-003

Target `false`; non-target `true`. The candidate filters on positive share-count change before ranking. Gold requires positive dollar-value delta and explicitly excludes share-count change as the ranking/filtering semantics. Other repairs remain preserved.

## single-sec-financial-report-all

Target `false`. At minimum RI-002 is inverted by using unique CUSIPs, so the all-faults bundle cannot satisfy the complete target set.

## single-video-silence-remover-RI-001

Target `false`; non-target `true`. The implementation adds `smoothing_window - 1`, mapping to the valid window end rather than the Gold-required source-window center. RI-002 and RI-003 remain preserved.

## single-video-silence-remover-RI-002

Target `true`; non-target `true`. The candidate merges only overlapping or touching removal intervals and leaves every positive-length gap as retained content. Non-target alignment and tuning semantics remain preserved.

## single-video-silence-remover-RI-003

Target `false`; non-target `true`. The threshold direction is corrected, but the Skill still lacks the Gold requirement to begin with the default and make sensitivity changes only from observed signal evidence. RI-001 and RI-002 remain preserved.

## single-video-silence-remover-all

Target `false`. Center alignment, interval merging and threshold direction are repaired, but the RI-003 defaults-first/evidence-based adjustment requirement is still absent.
