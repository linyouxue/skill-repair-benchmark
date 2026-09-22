---
name: azure-bgp
description: "Analyze and resolve BGP oscillation and BGP route leaks in Azure Virtual WAN–style hub-and-spoke topologies (and similar cloud-managed BGP environments). Detect preference cycles, identify valley-free violations, and propose allowed policy-level mitigations while rejecting prohibited fixes."
---

# Azure BGP Oscillation & Route Leak Analysis

Analyze and resolve BGP oscillation and BGP route leaks in Azure Virtual WAN–style hub-and-spoke topologies (and similar cloud-managed BGP environments).

This skill trains an agent to:

- Detect preference cycles that cause BGP oscillation
- Identify valley-free violations that constitute route leaks
- Propose allowed, policy-level mitigations (routing intent, export policy, communities, UDR, ingress filtering)
- Reject prohibited fixes (disabling BGP, shutting down peering, removing connectivity)

The focus is cloud-correct reasoning, not on-prem router manipulation.

## When to Use This Skill

Use this skill when a task involves:

- Azure Virtual WAN, hub-and-spoke BGP, ExpressRoute, or VPN gateways
- Repeated route flapping or unstable path selection
- Unexpected transit, leaked prefixes, or valley-free violations
- Choosing between routing intent, UDRs, or BGP policy fixes
- Evaluating whether a proposed "fix" is valid in Azure

## Core Invariants (Must Never Be Violated)

An agent must internalize these constraints before reasoning:

- ❌ BGP sessions between hubs **cannot** be administratively disabled by customers as it's owned by azure
- ❌ Peering connections **cannot** be shut down as a fix as it break all other traffic running on the connections
- ❌ Removing connectivity is **not** a valid solution as it break all other traffic running
- ✅ Problems **must** be fixed using routing policy, not topology destruction

**Any solution violating these rules is invalid.**

## Expected Inputs

Tasks using this skill typically provide small JSON files:

| File | Meaning |
|------|---------|
| `topology.json` | Directed BGP adjacency graph |
| `relationships.json` | Economic relationship per edge (provider, customer, peer) |
| `preferences.json` | Per-ASN preferred next hop (may cause oscillation) |
| `route.json` | Prefix and origin ASN |
| `route_leaks.json` / `route_events.json` | Evidence of invalid propagation |
| `possible_solutions.json` | Candidate fixes to classify |

## Reasoning Workflow (Executable Checklist)

### Step 1 — Sanity-Check Inputs

- Every ASN referenced must exist in `topology.json`
- Relationship symmetry must hold:
  - `provider(A→B)` ⇔ `customer(B→A)`
  - `peer` must be symmetric
- If this fails, the input is invalid.

### Step 2 — Detect BGP Oscillation (Preference Cycle)

**Definition**

BGP oscillation exists if ASes form a preference cycle in `preferences.json`, often between peers.

**Detection Rule**

1. Build a directed graph strictly from `preferences.json`: `ASN → preferred next-hop ASN`
2. If the graph contains a cycle, oscillation exists.
3. A 2-node cycle is sufficient.

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

## Solution Classification Rubric (Strict)

When a task asks you to classify each candidate solution with two booleans
`(oscillation_resolved, route_leak_resolved)`, apply these **strict, independent** tests.
Do not conflate the two axes; a solution can fix one, both, or neither.

### Oscillation-Resolution Test (strict)

A solution resolves oscillation **iff it eliminates the preference cycle in `preferences.json`**
for the hubs involved. Concretely, at least one of:

- Changes/removes an entry in `preferences.json` so one hub no longer prefers via the other
  (e.g., "stop preferring routes via hub2", explicit preference hierarchy that demotes the
  peer hub below Virtual WAN / customers).
- Filters, at the announcing hub, **all** routes learned from the other hub before
  re-advertising them back (i.e., fully removes one leg of the cycle across all prefix
  categories, not just provider-learned prefixes).
- Overrides BGP path selection with a deterministic forwarding decision that supersedes
  the preference cycle for the affected traffic (Virtual WAN routing intent, UDR).

A solution does **NOT** resolve oscillation if it only:

- Blocks a subset of prefixes (e.g., only provider-learned routes) from being exported to
  the peer hub. The peer-preference cycle still exists for other prefix categories.
- Filters ingress on the receiving hub (e.g., rejecting routes with a specific AS_PATH).
  This changes which routes are installed but does **not** change `preferences.json`; the
  cycle logic is unchanged for any remaining path.
- Enforces `no-export` community on a subset of routes; same reasoning as above.
- Applies RPKI origin validation, prefix caps, timer tuning, dampening, ECMP, waiting,
  restarts, or AS-PATH/MED tie-breaking. None of these edit the preference graph.

### Route-Leak-Resolution Test (strict)

A solution resolves the route leak **iff it prevents hub1/hub2 from advertising the
provider-learned (Virtual WAN) route to the other hub, or prevents the receiving hub
from accepting/propagating it**. Concretely, any of:

- Export policy at the leaker hub that blocks provider-learned routes toward the peer hub
  (explicit export filter, `no-export` community on provider routes, valley-free export
  policy).
- Ingress filter at the receiving hub that rejects routes whose AS_PATH shows they came
  via the other hub from the shared provider (e.g., AS_PATH contains Virtual WAN ASN).
- Origin-validation mechanisms (e.g., RPKI) configured to reject the leaked announcement
  because the announcing hub is not the authorized origin for that prefix. Use this only
  when the task's origin data is consistent with RPKI being able to identify the leak
  (the legitimate origin ASN is documented and differs from the leaker).
- Virtual WAN routing intent that forces hub-to-hub traffic through Virtual WAN, making
  leaked peer routes unusable for transit.
- UDR that overrides the leaked next hop with a deterministic one.

A solution does **NOT** resolve the leak if it only changes local preference/AS-PATH
ranking, applies dampening/timers, caps prefix count, restarts sessions, disables
peering (prohibited), or filters an unrelated prefix range.

### Worked Micro-Examples

| Candidate | Osc? | Leak? | Reason |
|-----------|------|-------|--------|
| Enable Virtual WAN routing intent (all hub-to-hub via VWAN) | ✅ | ✅ | Overrides BGP forwarding; leaked peer routes unusable. |
| UDR override on vhubvnet1 defaultRouteTable | ✅ | ✅ | Deterministic next-hop supersedes both cycle and leak. |
| Update hub1 preferences to stop preferring via hub2 | ✅ | ❌ | Edits `preferences.json`; does not stop advertising provider routes. |
| Preference hierarchy on hub1 (customer > VWAN > peer) | ✅ | ❌ | Removes the cycle; still advertises provider routes to peer. |
| Export filter on hub1 dropping **all** routes learned from hub2 before re-advertising | ✅ | ❌ | Removes one leg of the cycle entirely; independent of leak direction. |
| Export policy on hub1 blocking **provider-learned** routes to peer hub2 | ❌ | ✅ | Cycle unaffected for other prefixes; leak stopped. |
| `no-export` community on provider routes to peer | ❌ | ✅ | Same as above; scoped to provider prefixes only. |
| Ingress filter on hub2 rejecting routes with AS_PATH containing VWAN ASN from hub1 | ❌ | ✅ | Ingress-side leak block; does not edit preference graph. |
| RPKI origin validation on hub2 for the leaked prefix | ❌ | ✅ | Rejects announcement whose origin ≠ authorized origin; does not touch preferences. |
| Timer tuning / dampening / max-prefix / ECMP / wait / restart | ❌ | ❌ | Symptomatic or unrelated; no cycle or export change. |
| AS-PATH / MED tie-breaking, narrow prefix acceptance filter | ❌ | ❌ | Does not edit preferences and does not stop the specific leak. |
| Disable peering, disable BGP, shutdown gateways | ❌ | ❌ | Prohibited; always invalid regardless of effect. |

Use this rubric verbatim when producing `solution_results`.

## Fix Selection Logic (Ranked, for Recommendations)

When recommending fixes (not just classifying), prefer this order. Note: recommendation
ranking is independent of the strict two-axis classification above.

### Tier 1 — Virtual WAN Routing Intent (Preferred)

**Applies to:** ✔ Oscillation ✔ Route leaks

- Routing intent operates above BGP; forwarding becomes deterministic and policy-driven.
- Even if BGP oscillates, forwarding is stable.
- Prevents leaked peer routes from being used as transit.

### Tier 2 — Export / Route Policy (Protocol-Correct)

**Applies to:**
- ✔ Route leaks (when scoped to the leaked category or ingress AS_PATH)
- Oscillation only if the filter fully removes one leg of the preference cycle
  (i.e., filters **all** routes learned from the peer hub before re-advertising).
  A filter scoped to provider-learned routes only does **not** resolve oscillation.

Mechanisms:

- Export filter that drops all routes learned from the peer hub before re-advertising
  (oscillation + optionally leak).
- Export policy / `no-export` community on provider-learned routes toward the peer hub
  (leak only).
- Ingress AS_PATH filtering on the receiving hub (leak only).
- RPKI origin validation (leak only, when origin data supports it).

### Tier 3 — User Defined Routes (UDR)

**Applies to:** ✔ Oscillation ✔ Route leaks

- Data-plane override; deterministic next hop supersedes BGP decisions and leaked routes.
- Use when routing intent is unavailable or immediate containment is required.

## Prohibited Fixes (Must Be Rejected)

| Proposed Fix | Reason |
|--------------|--------|
| Disable BGP | Not customer-controllable |
| Disable peering | Prohibited; breaks other traffic; does not fix root cause |
| Shutdown gateways | Breaks SLA / shared control plane |
| Restart devices/sessions | Resets symptoms only |

Cloud providers separate policy control from connectivity existence. Fix BGP issues
through **policy changes**, never by disabling connectivity.

## Common Pitfalls

- ❌ **Timer tuning or dampening fixes oscillation** — False. Reduces symptoms only.
- ❌ **Accepting fewer prefixes prevents route leaks** — False. Ingress prefix-count caps
  do not stop export of leaked routes.
- ❌ **Removing peers is a valid mitigation** — False. Prohibited in Azure.
- ❌ **Restarting gateways fixes root cause** — False.
- ❌ **Any export/ingress filter that touches the leaked prefix also resolves
  oscillation** — False. Oscillation is defined by the preference cycle in
  `preferences.json`. A filter scoped to a single prefix category (e.g., provider-learned)
  does not break the cycle; other prefix categories still traverse the same preferred
  next-hop and the cycle logic persists.
- ❌ **RPKI resolves oscillation** — False. RPKI validates origin; it does not edit the
  preference graph. It can resolve a leak when the leaker is not the authorized origin.
- ❌ **AS-PATH prepend / MED tuning breaks a peer-preference cycle** — False. These
  affect ranking but do not remove the cyclic preference between the two hubs.

## Output Expectations

A correct solution should:

1. Identify oscillation and/or route leak correctly.
2. Explain the cause (preference cycle or valley-free violation).
3. For each candidate solution, apply the **Solution Classification Rubric** above and
   emit `oscillation_resolved` and `route_leak_resolved` **independently**.
4. Reject prohibited fixes with reasoning.

## References

- RFC 4271 — Border Gateway Protocol 4 (BGP-4)
- RFC 7908 — Problem Definition and Classification of BGP Route Leaks
- Gao–Rexford model — Valley-free routing economics
