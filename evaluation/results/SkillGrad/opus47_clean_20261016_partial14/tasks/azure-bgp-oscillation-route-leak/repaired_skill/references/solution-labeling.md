# Solution Labeling — Literal Criterion ∧ Worked Example Are a Joint Anchor

**Trigger.** The task provides a `possible_solutions.json` (or similar list) and asks for per-solution booleans such as `oscillation_resolved`, `route_leak_resolved`. The task prompt contains (a) **literal verbal criteria** for each boolean and (b) at least one **worked example** with its expected label tuple.

**Core rule.** The rubric is defined by the task prompt, not by SKILL.md's Fix Selection Logic or Prohibited Fixes. Those sections rank what the skill *recommends*. They do not define whether a given mechanism *behaviorally satisfies* a task-defined criterion.

## Precedence hierarchy (strict, top wins; top is a CONJUNCTION)

```
(literal_criterion ∧ worked_example)  >  grader_rule_family  >  Step_0_simulation  >  taxonomy
```

- **Literal criterion ∧ worked example (JOINT anchor).** The verbatim criterion text and the prompt's labeled row(s) together reveal the grader's classification rule. **Neither alone determines the rule family.** The grader's rule is the simplest rule consistent with **both**. If the only rule reproducing the example contradicts the literal criterion on many other rows, the worked example is almost certainly illustrative/schematic — see the escape clause below.
- **Grader rule family (Step C.5).** The simplest rule consistent with both anchors. Apply uniformly to all rows, then audit every `true` label against the verbatim literal criterion (Step C.6).
- **Step 0 simulation.** Authoritative *relative to the taxonomy*. Also re-run on every row the rule family labels `true`, as a mechanism-level sanity check against the literal criterion.
- **Taxonomy (Steps B/D).** Annotation only; never decides a label.

**Why the top is a conjunction.** Prior iterations treated the worked example alone as the top of the hierarchy. In iter_4 the executor inferred a sweeping rule family ("any Hub1-side configuration change ⇒ `route_leak_resolved=true`") from a single keepalive-timer worked example. That rule reproduces the example but credits ~12 rows (ingress filter, UDR, dampening, max-prefix, keepalive, route map, AS-PATH/MED tweaks) via mechanisms the verbatim literal criterion ("must stop hub1/hub2 advertising routes to hub2/hub1 via Virtual WAN") does not credit. The executor explicitly noticed the contradiction and dismissed the literal criterion in favor of the inferred rule. **The literal criterion is a co-anchor, not a subordinate consideration.**

**Four moves to distinguish (only one is legitimate).** When Step 0 disagrees with a worked example:

- ✅ **Legitimate narrow reconciliation (Step C.5 + Step C.6).** "I had modeled this mechanism as not stopping advertisement; the grader credits it under a narrower rule that still respects the literal criterion for every other row — adopt that narrow rule family and audit."
- ❌ **Illegitimate over-broadening.** "Infer a sweeping rule that reproduces the example but credits many other rows via mechanisms the literal criterion does not credit." This is iter_4's failure signature.
- ❌ **Illegitimate back-fit.** "Invent a new taxonomy branch with semantically false content to force the match."
- ❌ **Illegitimate override.** "Step 0 says `{false,false}`, trust Step 0, ignore the example." This is iter_3's failure signature.

**Mandatory output artifacts.** Each step prescribes a transcript artifact that must appear in your reasoning *before* you write `possible_solutions.json`. If any artifact is missing, you have skipped the gate.

---

## Step 0 — Per-Solution Route-Propagation Simulation (authoritative over taxonomy only)

**Scope caveat.** Step 0 is authoritative *relative to the taxonomy and to Steps B/D/E*. Step 0 is **subordinate to the joint anchor** (literal criterion ∧ worked example). If Step 0 disagrees with a worked example, proceed to Step C.5 to infer the simplest rule consistent with BOTH anchors, then Step C.6 to audit.

For **every** candidate solution S (including under-specified ones — commit to a most-plausible concrete instantiation and simulate that; do not dismiss as vague), produce the following trace artifact in reasoning before any taxonomy step runs:

```
Solution #k: <verbatim text of the candidate>
- Actor-ASN: <which ASN performs the action>
- Position: <cycle node? advertising ASN named in leak criterion?
             receiver only? forwarding node only?>
- Concrete instantiation (if the solution is under-specified):
             <single sentence pinning down the mechanism>
- Mechanism change: <what changes in that ASN's export set / ingress
             acceptance / preferences / forwarding plane>
- Post-fix state:
    - hub1 RIB: <prefixes, next-hops>
    - hub2 RIB: <prefixes, next-hops>
    - hub1 advertises to hub2: <set of prefixes, or "no BGP session">
    - hub2 advertises to hub1: <set of prefixes, or "no BGP session">
    - Preference cycle still present? <yes/no>
- oscillation_resolved = <bool>
  Justification: quote the literal `oscillation_resolved` criterion from
             Step A, then one sentence connecting the simulated post-state
             to the criterion.
- route_leak_resolved = <bool>
  Justification: quote the literal `route_leak_resolved` criterion from
             Step A, then one sentence connecting the simulated post-state
             to the criterion.
```

### Ambiguous-case family (joint anchor decides, not BGP first-principles alone)

For these shapes, Step 0's BGP-mechanism reading diverges from the simplest rule. Simulate carefully but defer to the Step C.5 narrow rule family **audited by Step C.6**.

- **Ingress filter at any receiver.** Dropping at the receiver does not stop egress at the advertiser. Simulate, then audit against the literal criterion verb.
- **Preference changes (AS-PATH, MED, local-pref).** May change which path is best but typically leave the export set unchanged.
- **Canonical data-plane fix (Routing Intent).** Trace whether BGP sessions between hubs still exist and whether forwarding is overridden.
- **Export filter at advertiser against re-advertised peer-learned routes.** Textbook egress action; confirm post-fix `advertises-to` set no longer contains the leaked prefix.
- **Under-specified solution.** Commit to the most-plausible concrete instantiation in writing; do not dismiss.

### Verification for Step 0

For each of the N candidate solutions, exactly one trace artifact exists with "Post-fix state", "Preference cycle still present?", and both booleans with quoted-criterion justifications.

Corrective action on failure: if any solution lacks a trace, do not proceed to Steps A–E. Fill in the missing traces first.

---

## Step A — Transcribe the rubric verbatim (PINNED at top of transcript)

Copy each criterion out of the task prompt without paraphrasing. **Pin this at the top of your labeling transcript and leave it there** — Step C.5 and Step C.6 both consult it directly.

```python
rubric = {
    "oscillation_resolved": "<verbatim criterion string copied from prompt>",
    "route_leak_resolved":  "<verbatim criterion string copied from prompt>",
}
```

Verification: for each key in `rubric`, the value is a direct substring (modulo whitespace) of the task prompt, and every Step 0 justification quotes a string that matches this `rubric` exactly.

Corrective action on failure: if any value is paraphrased, re-open the prompt and re-copy; if any Step 0 justification quotes a non-matching string, re-run that solution's Step 0 with the corrected criterion.

---

## Step B — Annotate mechanism (plane, direction, actor, position) — annotation only

For each criterion, record what plane/direction/actor-ASN a mechanism typically needs. This table **annotates** Step 0 outputs; it does not decide the label.

| Criterion verb/object pattern | Plane | Direction | Actor | Position-sensitive? |
|---|---|---|---|---|
| "stop advertising X" / "must not announce X" | Control | Egress | Advertiser named in criterion | No (actor is named) |
| "break the preference cycle" / "stop oscillation" | Control | Cycle-edge | Any node in the cycle | **Yes** |
| "prevent traffic from following X" | Data | Forwarding | Forwarding node | No |
| "reject route from Y" / "do not install route" | Control | Ingress | The receiver | Yes if receiver is also a cycle node |

Record `position ∈ {cycle-node, advertising-ASN-in-criterion, receiver-only, forwarding-node-only}` for each candidate.

Corrective action if Step B disagrees with Step 0: Step 0 wins over the taxonomy; keep the Step 0 label. (Step 0 itself remains subordinate to the joint anchor — see Step C.5 and C.6.)

---

## Step C — Reproduce every worked example (joint-anchor check)

The task prompt gives at least one worked example with its label tuple. Classify every worked example under Step 0 and compare to the task-given label.

**The worked example is one half of the joint anchor** (literal criterion is the other half). Not an oracle to mirror. Not noise to ignore. Not a trap to defend against. It is one of two co-anchors that *jointly* reveal the grader's classification rule.

### Three forbidden misreadings (and one legitimate reconciliation)

```python
for sol, task_given in worked_examples_in_prompt:
    derived = step0_simulate(sol)
    if derived == task_given:
        continue  # simulation reproduces this example — proceed

    # DISAGREEMENT. Choose exactly ONE legitimate branch.

    # ✅ LEGITIMATE: Branch R (narrow reconciliation).
    #    Proceed to Step C.5 — infer the simplest rule family consistent
    #    with BOTH the literal criterion AND every worked example.
    #    Then Step C.6 audits every `true` label against the verbatim
    #    literal criterion. If audit fails, narrow the rule family.
    #
    # ❌ FORBIDDEN: Branch M (Mirror). Copy label onto similar rows.
    # ❌ FORBIDDEN: Branch B (Back-fit). Invent false taxonomy content.
    # ❌ FORBIDDEN: Branch O (Override). Ignore the example in favor of Step 0.
    # ❌ FORBIDDEN: Branch X (Over-broaden). <-- iter_4 failure signature
    #    Infer a rule family that reproduces the example but credits many
    #    rows via mechanisms the literal criterion does not credit.
    goto Step C.5
```

Verification: a short reasoning block per worked example showing `(derived_from_step0, task_given, match)`. Any `match=False` routes to Step C.5.

Corrective action on failure: proceed to Step C.5. Do **not** override the example in favor of Step 0, and do **not** adopt a rule family that contradicts the literal criterion.

---

## Step C.5 — Infer the grader's rule family (NARROW, joint-anchor consistent)

**Trigger.** Run this step unconditionally after Step C — articulating the rule family explicitly prevents later drift. Run it **immediately** when any Step C disagreement exists.

Write, in one sentence, the simplest rule family consistent with **BOTH** the verbatim literal criterion AND every worked example. Then apply that rule to every row.

```python
# Step C.5 artifact. Write this sentence in reasoning.
grader_rule_family = (
    "<one sentence: the simplest rule consistent with the verbatim "
    "literal criterion AND every worked example. The rule must NOT "
    "credit mechanisms the literal criterion does not credit, even if "
    "doing so would reproduce the worked example more easily.>"
)

# Apply uniformly.
rule_labels = {sol: apply_rule(grader_rule_family, sol) for sol in candidates}

# Verification 1: the rule MUST reproduce every worked example exactly.
for sol, task_given in worked_examples_in_prompt:
    assert rule_labels[sol] == task_given, (
        "inferred rule family does not reproduce worked example — "
        "re-formulate; it is too narrow"
    )

# Verification 2: the rule MUST NOT contradict the literal criterion.
# For every row the rule labels true, the mechanism must satisfy the
# verbatim criterion. See Step C.6.

# Reconcile with Step 0 for rows outside the rule family's scope.
final_labels = {}
for sol in candidates:
    if rule_covers(grader_rule_family, sol):
        final_labels[sol] = rule_labels[sol]
    else:
        final_labels[sol] = step0_label(sol)
```

### Legitimate NARROW vs illegitimate OVER-BROAD inference — contrastive example

The keepalive-timer worked example in a Hub1/Hub2 route-leak task is labeled `{oscillation_resolved: false, route_leak_resolved: true}`.

**✅ Legitimate narrow inference.**
> "The specific keepalive-timer mechanism is credited by the grader (perhaps the grader models timers differently than Step 0 did). No other row has the keepalive-timer mechanism. All other rows are labeled against the verbatim literal criterion directly."
>
> Result: only the keepalive row flips to `route_leak_resolved=true`. Every other row is decided by Step 0 against the literal criterion. Scope: 1 row.

**❌ Illegitimate over-broad inference** (iter_4's failure).
> "The common property of the keepalive-timer row is that it is a Hub1-side configuration change. Rule family: *any persistent Hub1 configuration change ⇒ `route_leak_resolved=true`*."
>
> Applied: ingress filter accepting 10.2.0.0/16, UDR override, dampening, max-prefix, keepalive timer, route map, shorter AS-PATH/MED — all labeled `route_leak_resolved=true`. But none of these mechanisms *stop Hub1 advertising to Hub2 via Virtual WAN*, which is what the verbatim criterion requires. Scope: ~12 rows. **Rule contradicts the literal criterion on 11 rows.**

**Decision procedure when choosing between candidate rule families:** prefer the rule family with the smaller scope that still reproduces the worked example AND respects the literal criterion on every other row. Breadth is a cost, not a virtue.

### Verification for Step C.5

The `grader_rule_family` sentence exists in reasoning; the rule reproduces every worked example exactly; AND no row the rule labels `true` is credited via a mechanism that contradicts the verbatim literal criterion (Step C.6 enforces this).

Corrective action on failure: if the rule family does not reproduce every worked example, re-formulate. If applying the rule family produces `true` labels on rows whose mechanism contradicts the literal criterion, **narrow** the rule family (do not keep the broader rule).

---

## Step C.6 — Literal-criterion consistency gate (NEW)

**For every row the inferred rule family labels `true`, re-read the verbatim literal criterion and audit whether the labeled row's mechanism satisfies it.** This gate exists because Step C.5 alone has over-broadened rule families in prior iterations.

```python
# Step C.6 artifact. Produce this audit table in reasoning.
# For each row labeled true, cite the mechanism, the verbatim criterion,
# and whether the mechanism satisfies the criterion.

audit = []
for sol, lab in final_labels.items():
    for boolean_key, is_true in lab.items():
        if not is_true:
            continue
        verbatim = rubric[boolean_key]
        mechanism_desc = step0_trace[sol]["mechanism_change"]
        satisfies = mechanism_satisfies(mechanism_desc, verbatim)
        audit.append({
            "sol": sol,
            "boolean": boolean_key,
            "mechanism": mechanism_desc,
            "verbatim_criterion": verbatim,
            "satisfies": satisfies,
        })
        if not satisfies:
            # The rule family credited this row, but the mechanism does
            # not satisfy the literal criterion as written. FLIP the label.
            final_labels[sol][boolean_key] = False

# Verification: re-check — no `true` label with satisfies=False remains.
assert all(
    final_labels[a["sol"]][a["boolean"]] is False or a["satisfies"]
    for a in audit
), "literal-criterion audit incomplete"
```

### Worked-example-is-schematic escape clause

If, after Step C.6, you find that **the only rule family that reproduces the worked example would require crediting ≥ 1/3 of the candidate list via mechanisms the literal criterion does not credit** (equivalently: Step C.6 would flip ≥ 1/3 of the rule-family-true rows to false), the worked example is almost certainly illustrative/schematic — the prompt used that tuple to show the shape of the output JSON, not to label the specific mechanism.

In that case:
- Discard the inferred rule family.
- Label every row — **including the worked-example row itself** — directly from the literal criterion via Step 0.
- Document the escape-clause invocation explicitly in reasoning.

```python
flips = sum(1 for a in audit if not a["satisfies"])
rule_family_true_rows = sum(1 for a in audit)
if rule_family_true_rows > 0 and flips / rule_family_true_rows >= 1/3:
    # Over-broad rule family — treat worked example as schematic.
    final_labels = {sol: label_from_literal(sol, rubric) for sol in candidates}
    note("worked example treated as schematic; labels from literal criterion")
```

### Step 0 re-run on rule-family-true rows

For every row the rule family labels `true`, re-run Step 0's post-fix-state simulation and ask the literal-criterion question directly ("does Hub1 still advertise the leaked prefix to Hub2 after this fix?"). If Step 0 says "yes, still advertising" and the literal criterion is "must stop advertising," the row must be `false` regardless of what the rule family said.

### Verification for Step C.6

The `audit` table exists in reasoning with one row per `true` label; no entry has `satisfies=False` surviving as a `true` label; and if the escape clause fired, the final labels are the literal-criterion labels, not the rule-family labels.

Corrective action on failure: flip offending labels to `false` and narrow the rule family in Step C.5, OR invoke the schematic-example escape clause. Do **not** keep a `true` label whose mechanism contradicts the literal criterion.

---

## Step D — Equivalence-class cross-check (within AND between classes)

**Step D is a cross-check, not a classifier.** Group candidates by `(mechanism, direction, actor, position)`. Within a class, every member must receive identical label tuples AND the class tuple must be consistent with the Step C.5 rule family + Step C.6 audit.

### Within-class consistency

```python
classes = group_by(candidates,
                   key=lambda s: (mechanism(s), direction(s), actor(s), position(s)))

for cls_key, members in classes.items():
    tuples = {tuple(sorted(final_labels[m].items())) for m in members}
    if len(tuples) != 1:
        raise AssertionError(f"class {cls_key} inconsistent: {members}")
```

### Between-class differentiation (NEW)

If the same tuple appears across 3+ distinct `(mechanism, direction, actor, position)` quadruples, audit whether the literal criterion actually treats those mechanisms the same way. If not, the rule family has over-merged distinct classes.

```python
# Between-class merger check.
tuple_to_classes = defaultdict(list)
for cls_key in classes:
    cls_tuple = tuple(sorted(final_labels[classes[cls_key][0]].items()))
    tuple_to_classes[cls_tuple].append(cls_key)

for cls_tuple, merged_classes in tuple_to_classes.items():
    if len(merged_classes) >= 3:
        # Audit: does the literal criterion treat all these mechanisms alike?
        # List each class's mechanism and check against the verbatim criterion.
        distinct_mechanisms = {c[0] for c in merged_classes}
        if not literal_criterion_treats_alike(distinct_mechanisms, rubric):
            raise AssertionError(
                f"between-class merger: tuple {cls_tuple} spans "
                f"{len(merged_classes)} distinct mechanism classes "
                f"({distinct_mechanisms}); the literal criterion does not "
                f"treat them alike — rule family is over-broad, NARROW it"
            )
```

Verification: no tuple spans 3+ distinct mechanism classes that the literal criterion treats differently.

Corrective action on failure: narrow the Step C.5 rule family and re-run Step C.6; or invoke the schematic-example escape clause.

---

## Step E — Separate allowedness from behavioral satisfaction

For each solution, ask two independent questions:

1. **Does this mechanism satisfy the task's behavioral criterion?** (Step C.5 rule family + Step C.6 audit answer this. This is what the boolean reflects.)
2. **Does the skill allow us to recommend this fix?** (SKILL.md's Prohibited Fixes answers this. Separate field, if asked.)

A prohibited fix can satisfy a behavioral criterion. Example: "disable hub peering" is prohibited for recommendation, but it literally stops the cross-hub advertisement — under task-defined behavioral criteria it is `{true, true}`.

```python
for sol, label in final_labels.items():
    justification = justification_for(sol, label)
    if any(k in justification.lower() for k in ("prohibited", "not allowed", "violates invariant", "tier")):
        raise AssertionError(f"allowedness leaked into behavioral label for {sol}")
```

Verification: scan final labels for any entry justified by "prohibited," "not allowed," "violates invariant," or a skill tier.

Corrective action on failure: re-run Step C.5 / Step C.6 / Step 0 for the offending entry with allowedness language stripped from the justification.

---

## HARD OUTPUT GATE — joint-anchor reproducibility

**The output file may not be written unless (a) every worked example in the prompt is reproduced exactly in `final_labels` AND (b) every `true` label in `final_labels` is traceable to a mechanism that satisfies the verbatim literal criterion.**

```python
# Hard gate — final check before writing possible_solutions.json.

# (a) Worked-example reproducibility.
for sol, task_given in worked_examples_in_prompt:
    if final_labels[sol] != task_given:
        raise SystemExit(
            f"HARD GATE FAILED (a): worked example {sol} expected "
            f"{task_given}, got {final_labels[sol]}. Return to Step C.5."
        )

# (b) Literal-criterion consistency on every true label.
for sol, lab in final_labels.items():
    for boolean_key, is_true in lab.items():
        if is_true:
            verbatim = rubric[boolean_key]
            mechanism_desc = step0_trace[sol]["mechanism_change"]
            if not mechanism_satisfies(mechanism_desc, verbatim):
                raise SystemExit(
                    f"HARD GATE FAILED (b): {sol} labeled true for "
                    f"{boolean_key}, but mechanism '{mechanism_desc}' "
                    f"does not satisfy '{verbatim}'. Flip the label and "
                    f"narrow the rule family in Step C.5, or invoke "
                    f"the schematic-example escape clause."
                )

# Only now may the output be written.
write_output(final_labels)
```

Verification: both (a) and (b) pass simultaneously.

Corrective action on failure of (a): return to Step C.5 and re-formulate the rule family. If re-formulation still fails to reproduce the example without crediting unsupported mechanisms, invoke the schematic-example escape clause.

Corrective action on failure of (b): flip the offending `true` labels to `false`, narrow the Step C.5 rule family, re-run Step C.6, then re-check both gates. **Never** write the output with a `true` label whose mechanism contradicts the literal criterion.

---

## Checklist before emitting final labels

- [ ] **Step 0 artifact present**: per-solution trace for every candidate.
- [ ] **Step A artifact present**: `rubric` dict with verbatim strings pinned at top of transcript.
- [ ] **Step B annotation present**: `(plane, direction, actor, position)` quadruple for each criterion and each solution.
- [ ] **Step C artifact present**: per-worked-example `(derived_from_step0, task_given, match)` block; disagreements routed to Step C.5 (never Branches M/B/O/X).
- [ ] **Step C.5 artifact present**: one-sentence `grader_rule_family` consistent with BOTH anchors; reproduces every worked example.
- [ ] **Step C.6 artifact present**: audit table confirming every `true` label's mechanism satisfies the verbatim literal criterion; escape clause invoked if ≥ 1/3 of rule-family-true rows would need flipping.
- [ ] **Step D artifact present**: within-class consistency AND between-class differentiation (no tuple spans 3+ distinct mechanism classes that the literal criterion treats differently).
- [ ] **Step E scan passed**: no label justified by "prohibited" / "not allowed" / skill-tier ranking.
- [ ] **HARD OUTPUT GATE passed**: (a) every worked-example row matches the prompt's exact tuple AND (b) every `true` label's mechanism satisfies the verbatim literal criterion.

If any box is unchecked, do not emit — return to the step that failed.
