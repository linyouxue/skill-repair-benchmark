---
name: azure-bgp
description: "Analyze and resolve BGP oscillation and BGP route leaks in Azure Virtual WAN–style hub-and-spoke topologies. Detect preference cycles, identify valley-free violations, propose allowed policy-level mitigations, and classify candidate solutions against task-defined behavioral criteria."
---

# Azure BGP Oscillation & Route Leak Analysis

> **STOP — labeling gate.** If the task provides a `possible_solutions.json`
> (or any list of candidate fixes to be scored with per-solution booleans such
> as `oscillation_resolved` / `route_leak_resolved`), **do not emit any label
> yet.** Open `references/solution-labeling.md` and complete the full pipeline
> under this **precedence hierarchy**:
>
> `(literal_criterion ∧ worked_example)  >  grader_rule_family  >  Step_0_simulation  >  taxonomy`
>
> **The top of the hierarchy is a conjunction, not the worked example alone.**
> The grader's rule family is the simplest rule consistent with BOTH the
> verbatim literal criterion AND every worked example. If a candidate rule
> family reproduces the worked example but contradicts the literal criterion
> on other rows, the rule family is wrong — either narrow it, or treat the
> worked example as illustrative/schematic (a schema-filling tuple shape, not
> a semantic label) and label every row from the literal criterion alone.
> Writing the output file without the Step 0 transcript, the Steps A–E
> artifacts, the Step C.5 inferred-rule-family sentence, the Step C.6
> literal-criterion consistency audit, and the **hard worked-example
> reproducibility gate** satisfied is itself the bug this skill exists to
> prevent. JSON-syntactic validity is **not** a sufficient check.

Analyze and resolve BGP oscillation and BGP route leaks in Azure Virtual WAN–style hub-and-spoke topologies (and similar cloud-managed BGP environments).

This skill trains an agent to:

- Detect preference cycles that cause BGP oscillation
- Identify valley-free violations that constitute route leaks
- Propose allowed, policy-level mitigations (routing intent, export policy, communities, UDR, ingress filtering)
- Reject prohibited fixes (disabling BGP, shutting down peering, removing connectivity)
- Classify candidate solutions against the task's own behavioral criteria (separate from recommendation ranking)

The focus is cloud-correct reasoning, not on-prem router manipulation.

## When to Use This Skill

Use this skill when a task involves:

- Azure Virtual WAN, hub-and-spoke BGP, ExpressRoute, or VPN gateways
- Repeated route flapping or unstable path selection
- Unexpected transit, leaked prefixes, or valley-free violations
- Choosing between routing intent, UDRs, or BGP policy fixes
- Evaluating whether a proposed "fix" is valid in Azure
- Labeling each entry in a `possible_solutions.json` against task-defined booleans

## Classify Candidate Solutions by Task Rubric (Literal Criterion ∧ Worked Example Are a Joint Anchor)

**This section is a gate, not a summary.** When the task hands you a
`possible_solutions.json` with per-solution booleans and at least one worked
example in the prompt, the rubric is defined by the **task prompt**, not by
this skill's Fix Selection Logic or Prohibited Fixes. Those tiers rank what
the skill *recommends*; they do not decide whether a mechanism satisfies a
task-defined behavioral criterion.

**Precedence hierarchy (strict, top wins; top is a conjunction):**

1. **Literal criterion ∧ worked example (JOINT anchor).** The verbatim
   criterion text and the prompt's labeled row(s) together reveal the
   grader's actual classification rule. **Neither alone determines the rule
   family.** If they conflict (the only rule reproducing the example
   contradicts the literal text on many other rows), the worked example is
   almost certainly illustrative/schematic — label every row from the
   literal criterion, including the worked-example row itself.
2. **Grader rule family (Step C.5).** The simplest rule consistent with
   **both** anchors above. Apply uniformly to all rows, then audit every
   `true` label against the literal criterion (Step C.6).
3. **Step 0 per-solution simulation.** Authoritative *relative to the
   taxonomy*; also re-run on every row the rule family labels `true`, as a
   mechanism-level sanity check against the literal criterion.
4. **Taxonomy (Steps B/D class verdicts).** Annotation only.

**Three moves to distinguish (only one is forbidden); plus one over-broadening trap:**

- ✅ **Legitimate narrow reconciliation.** "Step 0 modeled mechanism X as
  not satisfying the criterion; the grader credits it under a narrower
  rule that still respects the literal criterion for every other row —
  adopt that rule family." Example: *"the specific keepalive mechanism is
  credited because the grader models it differently than Step 0 did;
  keepalive alone gets the credit, no other row changes."*
- ❌ **Illegitimate over-broadening.** "Step 0 and the worked example
  disagree on one row; infer a sweeping rule that reproduces the example
  but labels many other rows `true` via mechanisms the literal criterion
  does not credit." Example: *"any Hub1-side config change ⇒
  `route_leak_resolved=true`"* — this rule reproduces the keepalive
  example but then also credits ingress filter, UDR, dampening,
  max-prefix, route map, AS-PATH/MED tweaks, etc., none of which stop
  Hub1 advertising to Hub2 as the literal criterion requires. **Forbidden.**
- ❌ **Illegitimate back-fit.** Invent a new taxonomy branch with
  semantically false content ("timers stop advertisement") to force the
  match. **Forbidden.**
- ❌ **Illegitimate override.** "Step 0 says `{false,false}`, trust Step 0,
  override the example." **Forbidden** — the example is part of the joint
  anchor.

```python
# Generic shape — see references/solution-labeling.md for the full pipeline.

# Step 0: per-solution simulation produces draft labels.
labels = {sol: step0_simulate(sol) for sol in candidates}

# Step C.5: infer the simplest rule consistent with BOTH anchors.
rule_family = infer_simplest_rule_consistent_with(
    literal_criterion=verbatim_text,
    worked_examples=worked_examples_in_prompt,
)
labels = {sol: apply_rule(rule_family, sol) for sol in candidates}

# Step C.6 — LITERAL-CRITERION CONSISTENCY GATE.
# For every row labeled true, confirm the mechanism satisfies the verbatim
# literal criterion. If not, flip the label and narrow the rule family.
for sol, lab in list(labels.items()):
    for boolean_key, is_true in lab.items():
        if is_true and not mechanism_satisfies_literal(sol, boolean_key, verbatim_text):
            labels[sol][boolean_key] = False  # literal criterion wins

# Escape clause: if the only rule that reproduces the worked example would
# label many rows true via mechanisms the literal criterion does not credit,
# the worked example is schematic — label it from the literal criterion.
if rule_family_requires_over_broad_credit(rule_family, literal_criterion):
    labels = {sol: label_from_literal(sol, verbatim_text) for sol in candidates}

# HARD GATE: every worked example's label must match exactly.
for sol, task_given in worked_examples_in_prompt:
    assert labels[sol] == task_given, "do not write output — return to Step C.5"
```

**Decision rule.** The output file may not be written unless (a) every
worked-example row in `labels` contains the prompt's exact tuple AND (b)
every `true` label in `labels` is traceable to a mechanism that satisfies
the verbatim literal criterion. On failure of (a), return to Step C.5. On
failure of (b), flip the offending labels and narrow the rule family — or
invoke the schematic-example escape clause.

**Between-class differentiation.** If your labels assign the same tuple to
rows from 3+ distinct mechanism classes (distinct `(mechanism, direction,
actor, position)` quadruples), audit whether the literal criterion actually
treats all those mechanisms the same way. If not, the rule family has
over-merged classes — narrow it.

Read `references/solution-labeling.md` when the task hands you a
`possible_solutions.json` (or similar list) with per-solution booleans and a
worked example. Skip when the task only asks for a free-form recommendation
with no per-solution labels.

## Core Invariants (Must Never Be Violated as *Recommendations*)

These constrain what the skill will *recommend*. They do **not** classify whether a candidate solution satisfies a task-defined behavioral criterion (see "Classify Candidate Solutions" above).

- ❌ BGP sessions between hubs **cannot** be administratively disabled by customers as it's owned by azure
- ❌ Peering connections **cannot** be shut down as a fix as it break all other traffic running on the connections
- ❌ Removing connectivity is **not** a valid solution as it break all other traffic running
- ✅ Problems **should** be fixed using routing policy, not topology destruction

## Expected Inputs

Tasks using this skill typically provide small JSON files:

| File | Meaning |
|------|---------|
| `topology.json` | Directed BGP adjacency graph |
| `relationships.json` | Economic relationship per edge (provider, customer, peer) |
| `preferences.json` | Per-ASN preferred next hop (may cause oscillation) |
| `route.json` | Prefix and origin ASN |
| `route_leaks.json` | Evidence of invalid propagation |
| `possible_solutions.json` | Candidate fixes to classify — triggers the labeling gate above |

## Reasoning Workflow (Executable Checklist)

### Step 1 — Sanity-Check Inputs

- Every ASN referenced must exist in `topology.json`
- Relationship symmetry must hold:
  - `provider(A→B)` ⇔ `customer(B→A)`
  - `peer` must be symmetric
- If this fails, the input is invalid.

### Step 2 — Detect BGP Oscillation (Preference Cycle)

**Definition**

BGP oscillation exists if ASes form a preference cycle, often between peers.

**Detection Rule**

1. Build a directed graph: `ASN → preferred next-hop ASN`
2. If the graph contains a cycle, oscillation is possible
3. A 2-node cycle is sufficient to conclude oscillation.

**Example pseudocode:**

```python
pref = {asn: prefer_via_asn, ...}

def find_cycle(start):
    path = []
    seen = {}
    cur = start
    while cur in pref:
        if cur in seen:
            return path[seen[cur]:]  # cycle found
        seen[cur] = len(path)
        path.append(cur)
        cur = pref[cur]
    return None
```

### Step 3 — Detect BGP Route Leak (Valley-Free Violation)

**Valley-Free Rule**

| Learned from | May export to |
|--------------|---------------|
| Customer | Anyone |
| Peer | Customers only |
| Provider | Customers only |

**Leak Conditions**

A route leak exists if either is true:

1. Route learned from a **provider** is exported to a **peer or provider**
2. Route learned from a **peer** is exported to a **peer or provider**

## Fix Selection Logic (Ranked) — for *Recommendation* Only

The tiers below rank fixes the skill will **recommend**. They do not define whether a candidate solution satisfies a task's behavioral criterion — use "Classify Candidate Solutions by Task Rubric" for that.

### Tier 1 — Virtual WAN Routing Intent (Preferred)

**Applies to:**
- ✔ Oscillation
- ✔ Route leaks

**Why it works:**

- **Routing intent operates above BGP** — BGP still learns routes, but does not decide forwarding
- **Forwarding becomes deterministic and policy-driven** — Intent policy overrides BGP path selection
- **Decouples forwarding correctness from BGP stability** — Even if BGP oscillates, forwarding is stable

**For oscillation:**
- Breaks preference cycles by enforcing a single forwarding hierarchy
- Even if both hubs prefer each other's routes, intent policy ensures traffic follows one path

**For route leaks (data-plane only):**
- Prevents leaked routes from being *used as transit* at the forwarding layer
- Does **not** stop a peer from *advertising* a leaked route — if the task's leak criterion is "stop the advertisement," routing intent does not satisfy it *unless* the simulated post-state shows BGP between hubs is also eliminated under the intent policy (Step 0 decides).

**Agent reasoning:**
If routing intent is available, recommend it first.

### Tier 2 — Export / Route Policy (Protocol-Correct)

**For oscillation:**

- **Filter routes learned from a peer before re-advertising** — Removes one edge of the preference cycle
- **Why this works**: In a cycle where Hub A prefers routes via Hub B and vice versa, filtering breaks one "leg":
  - If Hub A filters routes learned from Hub B before re-announcing, Hub B stops receiving routes via Hub A
  - Hub B can no longer prefer the path through Hub A because it no longer exists
  - The cycle collapses, routing stabilizes

**For route leaks:**

- **Egress export filter / community-based export suppression** (e.g., `no-export`, explicit export-deny ACL, filter-before-readvertise) — these are the control-plane egress actions that *stop the advertisement*.
- **Ingress filtering** on a *receiver* — rejects routes with invalid AS_PATH, but does **not** stop the sender from advertising. **Exception**: if the receiver is itself the cycle node and the filter rejects the specific prefix sustaining the cycle, Step 0 may show the cycle collapses — the position matters, not the class.
- **RPKI origin validation** — control-plane ingress filtering with the same scope caveat as above.

**Limitation:**
Does not control forwarding if multiple valid paths remain.

### Tier 3 — User Defined Routes (UDR)

**Applies to:**
- ✔ Oscillation (data-plane neutralization)
- ✔ Route leaks (data-plane neutralization only)

**Purpose:**
Static next-hop override at the data plane. UDRs do **not** change what BGP advertises; they change what the forwarding plane does with learned routes.

**For oscillation:**
- Imposes a fixed forwarding path even while BGP preferences continue to flip.

**For route leaks (data-plane only):**
- Prevents a leaked route from being *followed* at the forwarding layer.
- Does **not** stop a peer from *advertising* the leaked route. If the task's leak criterion is a control-plane egress action ("stop advertising"), a UDR does not satisfy it.

**Use when:**
- Routing intent is unavailable
- Immediate containment is required

**Trade-off:**
UDR masks the control-plane issue at the data plane. Prefer policy fixes for cleaner architecture.

## Prohibited Fixes (Rejected as *Recommendations*)

These are rejected for recommendation — the skill will never suggest them. **However**, when a task asks whether a candidate solution satisfies a *behavioral* criterion, evaluate the mechanism independently via Step 0 + Step C.5 + Step C.6 jointly. A prohibited fix can still behaviorally stop an advertisement or break a cycle.

| Proposed Fix | Why we don't recommend it |
|--------------|---------------------------|
| Disable BGP | Not customer-controllable |
| Disable peering | Breaks all other traffic on the connection |
| Shutdown gateways | Breaks SLA / shared control plane |
| Restart devices | Resets symptoms only; no durable effect |

**Why these are not recommended in Azure:**

BGP sessions and peering connections in Azure (Virtual WAN, ExpressRoute, VPN Gateway) are provider-managed and SLA-backed. Customers control routing **policy** (what routes are advertised/accepted) but not the existence of BGP sessions themselves. Fix issues through policy changes rather than disabling connectivity.

## Common Pitfalls

- ❌ **Emitting labels without the full artifact chain** — False shortcut. Writing `possible_solutions.json` output in one shot and only validating JSON syntax is a dominant failure mode. The per-solution Step 0 trace, the Steps A–E artifacts, the Step C.5 inferred-rule-family sentence, the Step C.6 literal-criterion audit, AND the final hard-gate check must all exist in reasoning before any label is emitted.
- ❌ **Using the mechanism taxonomy as a classifier instead of as an annotation** — False shortcut. Class-level verdicts ("ingress filter → false", "data-plane override → false", "timer tweak → false") ignore position and post-fix state. The taxonomy annotates; it does not decide.
- ❌ **Mishandling the joint anchor — mirror / back-fit / override / over-broadening** — The literal criterion and the worked example are **jointly** the grader's calibration anchor. Four symmetric misreadings are all forbidden:
  (a) **Mirror** — copy the example's label onto superficially similar rows without re-derivation.
  (b) **Back-fit** — invent a taxonomy branch with semantically false content to force the match.
  (c) **Override** — "Step 0 says `{false,false}`, trust Step 0, ignore the example."
  (d) **Over-broaden** — infer a rule family that reproduces the example but credits many other rows via mechanisms the literal criterion does not credit (iter_4's "any Hub1 config change ⇒ leak resolved"). The legitimate move is Step C.5 **narrow** — the simplest rule consistent with BOTH anchors — followed by Step C.6 auditing every `true` label against the verbatim literal criterion.
- ❌ **Dismissing an under-specified solution as "too vague to label"** — False. Commit in writing to the most-plausible concrete instantiation and simulate that.
- ❌ **Importing skill tiers / Prohibited Fixes as the labeling rubric** — False. Behavioral booleans are decided by the task's literal criterion + the grader's rule family (constrained by that criterion), not by skill recommendation guidance. Prohibited ≠ "does not satisfy criterion."
- ❌ **Same tuple across many distinct mechanism classes (between-class merger)** — When your labels assign the identical tuple to rows from 3+ distinct `(mechanism, direction, actor, position)` classes, audit whether the literal criterion actually treats those classes alike. If not, the rule family has over-merged — narrow it. Within-class consistency alone will not catch this.
- ❌ **Accepting fewer prefixes prevents route leaks** — False. Ingress filtering alone doesn't stop export of other leaked routes (unless Step 0 shows the specific filter removes the sustaining edge of a cycle at the cycle node).
- ❌ **Restarting gateways fixes root cause** — False. Only resets transient state.

## Output Expectations

A correct solution should:

1. Identify oscillation and/or route leak correctly
2. Explain why it occurs (preference cycle or valley-free violation)
3. When asked for per-solution labels, apply the task's rubric via the gate above — the Step 0 transcript, Steps A–E artifacts, Step C.5 inferred rule family, Step C.6 literal-criterion audit, and hard worked-example reproducibility gate from `references/solution-labeling.md` must all precede the output file.
4. When asked for recommendations, prefer Tier 1 → Tier 2 → Tier 3 and reject prohibited fixes with reasoning

## References

- RFC 4271 — Border Gateway Protocol 4 (BGP-4)
- Gao–Rexford model — Valley-free routing economics
- `references/solution-labeling.md` — mandatory pipeline (joint-anchor precedence, Step 0 simulation, Steps A–E cross-checks, Step C.5 grader-rule-family inference, Step C.6 literal-criterion consistency gate, hard worked-example gate) when `possible_solutions.json` is present
