---
name: azure-bgp
description: "Analyze and resolve BGP oscillation and BGP route leaks in Azure Virtual WAN–style hub-and-spoke topologies (and similar cloud-managed BGP environments). Detect preference cycles, identify valley-free violations, and classify candidate mitigations against strict control-plane resolution criteria while rejecting prohibited fixes."
---

# Azure BGP Oscillation & Route Leak Analysis

Analyze and resolve BGP oscillation and BGP route leaks in Azure Virtual WAN–style hub-and-spoke topologies (and similar cloud-managed BGP environments).

This skill trains an agent to:

- Detect preference cycles that cause BGP oscillation
- Identify valley-free violations that constitute route leaks
- Classify candidate mitigations against a strict, control-plane resolution criterion
- Distinguish control-plane fixes (actually resolve) from data-plane / receiver-side workarounds (mask only)
- Reject prohibited fixes (disabling BGP, shutting down peering, removing connectivity)

The focus is cloud-correct reasoning and precise classification, not on-prem router manipulation.

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

Tasks using this skill typically provide small JSON files. Exact filenames vary per task; match semantics, not names:

| Typical file | Meaning |
|------|---------|
| `topology.json` | Directed BGP adjacency graph |
| `relationships.json` | Economic relationship per edge (provider, customer, peer) |
| `preferences.json` | Per-ASN preferred next-hop ASN (may cause oscillation) |
| `route.json` | Prefix and origin ASN |
| `route_events.json` / `route_leaks.json` | Evidence of advertisements and invalid propagation |
| `local_pref.json` | Relationship-type weights (customer > peer > provider) |
| `possible_solutions.json` | Candidate fixes to classify |

Discover inputs by listing the data directory and reading what is present rather than assuming a fixed set.

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

A route leak exists if either is true (inspect each advertisement event):

1. Route learned from a **provider** is exported to a **peer or provider**
2. Route learned from a **peer** is exported to a **peer or provider**

Record each leak as a (leaker, source, destination, source_type, destination_type) tuple from the advertisement event.

## Resolution Criteria (Strict — Do Not Soften)

Before classifying any candidate solution, fix these criteria in mind. They are strict and must be applied literally, not by analogy.

**A solution resolves OSCILLATION only if it breaks the preference cycle in the topology:**

- The configured per-ASN next-hop preference (`prefer_via`) of at least one AS in the cycle must be changed so that AS no longer prefers its cycle partner (e.g., explicit prefer-customer/prefer-provider reconfiguration, or an enforced preference hierarchy that de-prefers the partner).
- A policy operating **above** BGP (Virtual WAN routing intent that mandates central-hub-only hub-to-hub forwarding/advertisement) also counts, because it overrides the mutual hub preferences at a layer BGP selection cannot resist.

Any change that leaves every cycle AS still configured to prefer its cycle partner does **not** break the cycle. In particular, a sender-side export policy that blocks only a specific leaked route class on one edge does **not** by itself break a preference cycle: the configured `prefer_via` of the partner is unchanged, and the partner still receives other (e.g., customer-originated) advertisements that realize that same preference, so the preference edge remains. Only a change to the preference graph itself — or a routing-intent-above-BGP override — collapses the cycle.

**A solution resolves a ROUTE LEAK only if it, at the BGP control plane, stops the leaking AS from advertising the offending (non-valley-free) routes to the destination AS.**

- The leaker must change its **outbound export policy** (or a higher-level policy, like routing intent, that enforces non-advertisement) so the specific leaked route class is no longer announced across the offending edge.
- Receiver-side filtering, data-plane overrides, and administrative waits do **not** satisfy this criterion even when they neutralize the operational impact.

Apply both criteria independently per candidate: a solution may resolve one, both, or neither.

## Solution Classification (General Rules)

Classify every candidate solution by the mechanism it changes, not by its vocabulary. The following rules apply to any instance.

### Resolves oscillation (preference-cycle break in the topology)

- **Preference change on a cycle AS** — explicitly reconfiguring a cycle AS so it stops preferring its cycle partner (e.g., prefer customer/provider path instead of peer path, or change its `prefer_via` away from the partner).
- **Preference-hierarchy enforcement on a cycle AS** — a policy that pins a strict ordering (customer > provider > peer, etc.) in a way that removes the preference for the cycle partner.
- **Virtual WAN routing intent that enforces a single hub-to-hub forwarding/advertisement policy through the central hub** — only when the intent is configured so that direct hub-to-hub advertisement/transit is no longer used (both control- and forwarding-plane effect). This resolves oscillation because every hub ends up with a single, intent-mandated path and the mutual preference is overridden by policy at a layer above BGP selection.

Note: A sender-side export filter that only suppresses a specific leaked route class (e.g., provider-learned routes) does **not** break the preference cycle. The partner's configured `prefer_via` still points at the leaker, and the partner continues to receive other advertisements (customer-originated, etc.) across the same edge that satisfy that preference. Treat such filters as leak fixes only, not as oscillation fixes.

### Resolves route leak (sender-side export stop)

- **Export policy on the leaking AS that drops / suppresses / does-not-announce the offending route class to the destination edge** (e.g., explicit "do not export provider-learned routes to peer X" expressed as an outbound filter/deny/drop rule). The offending UPDATE must no longer be sent by the leaker across the offending edge. Any mechanism that still transmits the UPDATE and relies on receiver / downstream behavior for suppression does **not** qualify.
- **Virtual WAN routing intent that removes direct hub-to-hub advertisement** — if the intent eliminates the hub-to-hub advertisement edge, the specific leak is prevented at the control plane.

Note on BGP communities (e.g., `NO_EXPORT`, `NO_ADVERTISE`, RFC 1997): a BGP community is a transitive attribute **carried on an UPDATE that is still sent**. Community-based "no-export" / "no-advertise" policies are **receiver-honored signalling**, not sender-side export stops:

- **Bare community *tagging*** — attaching NO_EXPORT (or similar) to the leaked route class — does **not** stop the sender from advertising. The leaker still transmits the UPDATE (with the community attached) to the direct peer; the community only asks the receiver (and downstream) not to re-propagate.
- **"Enforce no-export / no-advertise by BGP community"** — whenever the solution's advertised mechanism is a BGP community (rather than an outbound filter / deny / drop / suppression rule), the sender still emits the UPDATE across the offending edge. The leaker has not stopped announcing the route to the destination AS; it has only requested downstream non-propagation. Treat these as resolving **neither**.
- An outbound route policy only qualifies as a sender-side export stop when it actually *suppresses / drops / does-not-announce* the UPDATE on the offending edge (deny/drop/filter semantics). A community-matching rule only qualifies if it is *explicitly* used to **drop / deny / suppress** the outbound UPDATE — not to tag or set a community on it, and not to "enforce no-export" via community attachment.

In every community-based case the preference graph is unchanged, so none of these variants resolves oscillation on its own.

### Resolves neither (even if seemingly related)

- **Receiver-side ingress filters** (reject routes coming in from a peer, drop AS_PATHs containing certain ASNs on receive). These do not stop the sender's advertisement, so the leak is still happening. They also do not change any configured preference, so the preference cycle remains.
- **Data-plane overrides (UDR / next-hop pinning)**. UDRs are a forwarding-plane mechanism that pins a next-hop in the Azure data plane. BGP still learns the same routes, still advertises the same routes, and the preference graph is unchanged. Under the strict control-plane criterion, UDRs resolve neither oscillation (preference cycle persists) nor route leaks (advertisement continues). Note: UDRs can still be a useful operational workaround to stabilize forwarding, but they are not a cycle-break or an advertisement-stop.
- **Tie-breaker tweaks** — "prefer shorter AS-PATH", MED adjustments, and similar BGP selection knobs. These only influence tie-breaking within the standard BGP decision process. When a preference cycle is produced by explicit, policy-configured next-hop preferences on each AS, tie-breakers do not override those explicit preferences and therefore do not break the cycle. MED is also non-transitive across different ASes and typically ignored across peer/provider boundaries.
- **Narrow prefix accept filters that keep accepting the leaked prefix** — e.g., "only accept these prefixes from peer". These still accept the leaked prefix and do not affect the sender's export.
- **RPKI origin validation when the origin AS is legitimate** — RPKI rejects routes whose origin ASN is not authorized to announce the prefix. If the leak is produced by a *legitimate* origin being re-exported across a prohibited edge, RPKI accepts the origin and does nothing about the valley-free violation.
- **Dampening, keepalive/holdtime tuning, restart, waiting for convergence** — reduce symptoms or transient state only. Cycle and advertisement persist. Also: restarting a BGP session is operationally similar to a prohibited action in managed environments.
- **Prefix-count limits (max-prefix)** — may protect against prefix floods but do not address a specific valley-free violation or a preference cycle.
- **ECMP / load balancing across both cycle partners** — does not change preferences or exports; often makes forwarding ambiguous rather than fixing anything.
- **Vague "deploy a route map" / "centralized routing" statements without a specified policy** — if the candidate does not state which routes are filtered/preferred and in which direction, assume it resolves neither; vagueness is not a control-plane change.
- **Export filter in the wrong direction** — e.g., filtering routes *learned from the peer hub* before re-advertising when the actual leak is *provider-learned* routes to that peer hub. Filtering the wrong set of routes does not stop the specific offending advertisement and (crucially) does not break the cycle because the partner's preferred path, which comes from a different route class, is still advertised.
- **Any BGP community-based "no-export" / "no-advertise" policy on the leaker (bare tagging *or* "enforce no-export by BGP community")** — a community is a signalling attribute carried on an UPDATE that is **still sent** across the offending edge. Whether the solution is phrased as "attach NO_EXPORT" or as "configure a route policy to enforce no-export of <class> to <neighbor> by bgp community", the sender still transmits the UPDATE to the direct peer; the community only asks the receiver (and downstream) not to re-propagate. Under the strict "stop the leaker from advertising the offending routes to the destination AS" criterion, community-mediated suppression resolves **neither** the route leak (the offending UPDATE is still transmitted) nor the preference cycle (no `prefer_via` changes). Only an outbound policy that actually **denies / drops / suppresses** the UPDATE on the offending edge (e.g., "block / do not announce / filter out provider-learned routes to peer X" with deny/drop semantics) qualifies as a sender-side export stop.
- **Prohibited fixes** — disabling BGP, shutting down peering, taking gateways offline. Always neither (and violate the invariants).

### Classification checklist (apply to every candidate)

For each candidate solution, answer in order:

1. Is it a prohibited action (disable BGP/peering, shut down a gateway, restart a managed session, remove connectivity)? If yes → resolves **neither**; do not continue.
2. Does it alter a cycle AS's configured preference (its `prefer_via` or an equivalent hierarchy policy on that AS) so that AS no longer prefers its cycle partner? If yes → oscillation **resolved**. If no, **do not mark oscillation resolved** just because the solution helps with the leak — leak fixes and cycle fixes are independent.
3. Does it change the leaking AS's outbound export policy (or equivalent higher-level policy) so the specific offending route class is **no longer transmitted** across the offending edge — i.e., the sender actually **denies / drops / does-not-announce** the UPDATE (not merely tags or attaches a community to an UPDATE it still sends)? If yes → route leak **resolved**. This alone does **not** flip oscillation to resolved: the partner's `prefer_via` is unchanged and other route classes still traverse the same edge.
   - **Important community rule:** a BGP community (e.g., NO_EXPORT, NO_ADVERTISE) is an attribute carried on an UPDATE that is still transmitted. Any solution whose stated mechanism is "attach a community" or "enforce no-export of <class> to peer <X> by bgp community" leaves the UPDATE being sent; the community only asks the receiver and downstream not to re-propagate. Under the strict criterion "stop the leaker from advertising the offending routes to the destination AS", community-mediated no-export policies do **not** qualify. Treat them as resolving **neither** unless the solution *also* installs an outbound deny/drop/filter rule that actually suppresses the UPDATE for that class on that edge.
4. Does Virtual WAN routing intent eliminate direct hub-to-hub advertisement/forwarding in favor of a central hub? If yes → **both** resolved (it simultaneously overrides the cycle preferences and removes the direct hub-to-hub advertisement).
5. Otherwise (receiver-side ingress filter, UDR / data-plane override, tie-breaker tweak, RPKI with legitimate origin, dampening/timers/restart/wait, prefix-count limit, ECMP, vague route map, wrong-direction export filter, any BGP community-based no-export/no-advertise policy on the leaker that does not install an actual outbound deny/drop on the offending edge) → resolves **neither**.

Classify independently per axis — a solution may be `(oscillation_resolved=true, route_leak_resolved=false)` or vice versa. Do **not** mark both axes true unless the solution independently meets *both* criteria (preference change / intent-override AND sender-side export stop / intent-advertisement-removal).

## Fix Selection Logic (Ranked, Recommendation Order)

### Tier 1 — Virtual WAN Routing Intent (Preferred)

**Applies to:**
- ✔ Oscillation
- ✔ Route leaks

**Why it works:**

- **Routing intent operates above BGP** — BGP still learns routes, but a policy above BGP controls what is forwarded and (when configured to) what is advertised hub-to-hub.
- **Decouples forwarding correctness from BGP stability** — when intent enforces that hub-to-hub traffic goes through the central hub only, both the preference cycle and the direct hub-to-hub leak path are neutralized at a layer above BGP.

**For oscillation:**
- Enforces a single forwarding hierarchy that overrides mutual hub preferences.

**For route leaks:**
- Prevents direct hub-to-hub transit of provider/peer-learned routes.

**Agent reasoning:**
If routing intent is available and is scoped to enforce central-hub-only advertisement/forwarding, recommend it first.

### Tier 2 — Export / Route Policy on the Sender (Protocol-Correct)

**For oscillation:**

- **Change a cycle AS's preference** — if a cycle AS stops preferring its cycle partner, the cycle is broken directly. This is the only Tier 2 lever that breaks a preference cycle; a sender-side export filter on a specific leaked route class does not, because the partner's configured preference and its remaining advertisements across the edge are unchanged.

**For route leaks:**

- **Enforce valley-free export rules on the leaker** — explicit outbound export policy that *denies / drops / does-not-announce* the offending route class on the offending edge (e.g., "block announcing provider-learned routes to peers/providers"). The UPDATE for the offending route class must stop being transmitted across the offending edge; the leaker simply ceases the announcement.

Note on BGP communities: any solution whose stated mechanism is a BGP community — **bare** tagging *or* a route policy that "enforces no-export of <class> to peer <X> by bgp community" — leaves the UPDATE being sent across the offending edge. Communities are downstream propagation hints, not advertisement stops. Treat all community-mediated "no-export" policies as **not** a Tier 2 route-leak fix on their own. Only an outbound rule that actually denies/drops/suppresses the UPDATE (not one that tags it) qualifies. Classify by whether the sender stops transmitting the UPDATE, not by whether a word like "enforce" or "policy" appears next to "community".

**Important direction rule:**

The export policy must act on the *leaker's outbound* and on the *offending route class*. Filtering a different class in the same direction, or filtering in the opposite direction (ingress on the receiver), does not satisfy the "stop advertising" criterion.

### Tier 3 — Operational Workarounds (NOT Classified as Resolutions)

Tools in this tier may stabilize operations but do **not** satisfy the strict control-plane criteria above. Recommend them explicitly as workarounds; do **not** classify them as resolving oscillation or the route leak.

- **User Defined Routes (UDR)** — data-plane next-hop pin. Can stabilize forwarding on the Azure data plane while BGP continues to misbehave. BGP preferences, cycles, and advertisements are unchanged, so UDRs do not meet either strict resolution criterion.
- **Receiver-side ingress filters** — may protect a specific receiver from acting on leaked routes, but the sender still advertises and the preference cycle persists.
- **RPKI origin validation** — valuable in general; only drops routes with an *invalid* origin. If the origin is legitimate (as is typical when the problem is valley-free export), RPKI changes nothing for this instance.

Prefer Tier 1 or Tier 2 actions for actual resolution.

## Prohibited Fixes (Must Be Rejected)

These solutions are **always invalid**:

| Proposed Fix | Reason |
|--------------|--------|
| Disable BGP | Not customer-controllable |
| Disable peering | prohibited operation and cannot solve the issue |
| Shutdown gateways | Breaks SLA / shared control plane |
| Restart devices / BGP sessions | Resets symptoms only; in managed environments the session is not customer-controllable |

**Required explanation:**

Cloud providers separate policy control from connectivity existence to protect shared infrastructure and SLAs.

**Why these are not allowed in Azure:**

BGP sessions and peering connections in Azure (Virtual WAN, ExpressRoute, VPN Gateway) **cannot be administratively shut down or disabled** by customers. This is a fundamental architectural constraint:

1. **Shared control plane**: BGP and peering are part of Azure's provider-managed, SLA-backed control plane that operates at cloud scale.
2. **Availability guarantees**: Azure's connectivity SLAs depend on these sessions remaining active.
3. **Security boundaries**: Customers control routing **policy** (what routes are advertised/accepted) but not the existence of BGP sessions themselves.
4. **Operational scale**: Managing BGP session state for thousands of customers requires automation that manual shutdown would undermine.

**Correct approach**: Fix BGP issues through **policy changes** (outbound deny/drop/filter policies that actually stop transmitting the offending UPDATE on the offending edge, preferences/`prefer_via` changes on cycle ASes, or Virtual WAN routing intent) rather than disabling connectivity. Any BGP community-based mechanism — bare community tagging *or* a policy phrased as "enforce no-export of <class> to peer <X> by bgp community" — still transmits the UPDATE across the offending edge; the community is a signalling attribute asking the receiver/downstream not to re-propagate. Community-mediated no-export therefore does **not** satisfy the sender-side export-stop criterion unless it is paired with an actual outbound deny/drop that stops the UPDATE.

## Common Pitfalls

- ❌ **Timer tuning or dampening fixes oscillation.** False. They reduce symptoms but don't break preference cycles.
- ❌ **Ingress / receive-side filtering "resolves" the leak.** False. It can neutralize local impact but does not stop the sender from advertising, which is the strict criterion.
- ❌ **UDR fixes the preference cycle or the leak.** False. UDR is a data-plane override. BGP preferences and advertisements are unchanged. Classify as resolving neither.
- ❌ **Accepting fewer prefixes prevents route leaks.** False. Ingress filtering alone doesn't stop export of other leaked routes and leaves the advertisement in place.
- ❌ **AS-PATH / MED tweaks break a configured preference cycle.** False. Standard tie-breakers operate *inside* the BGP decision process and are overridden by explicit per-ASN next-hop preferences. MED is also non-transitive across different ASes.
- ❌ **RPKI origin validation stops a valley-free leak with a legitimate origin.** False. RPKI only drops routes with an *invalid* origin.
- ❌ **Removing peers is a valid mitigation.** False. This is prohibited in Azure.
- ❌ **Restarting gateways fixes root cause.** False. Only resets transient state.
- ❌ **Filtering routes learned from the peer always breaks the cycle.** False. A wrong-direction filter — e.g., filtering routes *learned from the peer hub* while the actual leak is provider-learned routes being exported to that peer hub — does not stop the offending advertisement and does not change any `prefer_via`. Resolves neither.
- ❌ **A sender-side export filter that blocks a leaked route class also breaks the preference cycle.** False. It stops the specific leaked advertisement (so it can resolve the leak), but the partner's configured `prefer_via` still points at the leaker and other route classes (e.g., customer-originated routes) continue to be advertised across the same edge. Classify as `oscillation_resolved=false`, `route_leak_resolved=true` unless the solution also changes a cycle AS's preference.
- ❌ **Any BGP community-based "no-export" / "no-advertise" policy on the leaker stops the leak.** False. Whether the solution is phrased as bare tagging ("attach NO_EXPORT to the leaked route class") or as a route policy ("enforce no-export of provider routes to peer X by bgp community"), the leaker still transmits the UPDATE across the offending edge with the community attached; the community only asks the *receiver* (and downstream neighbors) not to re-propagate. The leaker's advertisement to the destination AS is unchanged, so under the strict control-plane criterion this does not satisfy "stop advertising" and it does not change any `prefer_via`. Classify community-mediated no-export solutions as `oscillation_resolved=false`, `route_leak_resolved=false` unless they are explicitly combined with an outbound deny/drop/filter rule that actually suppresses the UPDATE on the offending edge. A solution qualifies as a leak fix only when its stated mechanism is an *outbound* **deny / drop / block / do-not-announce / filter-out** rule for the offending route class on the offending edge (e.g., "block announcing provider routes to peer X"); that is a true sender-side export stop and resolves the leak (`route_leak_resolved=true`), though it still leaves `prefer_via` unchanged (`oscillation_resolved=false`).

All of the above are false under the strict resolution criteria.

## Output Expectations

A correct solution should:

1. Identify oscillation and/or route leak correctly, including the cycle ASNs and leak tuples.
2. Explain why each occurs (specific preference cycle; specific valley-free violation).
3. For each candidate solution, apply the classification checklist independently per axis and produce a (oscillation_resolved, route_leak_resolved) pair.
4. Explicitly reject prohibited fixes with the architectural reasoning.
5. Preserve the exact candidate solution strings as keys in the output; do not paraphrase or alter them.

## References

- RFC 4271 — Border Gateway Protocol 4 (BGP-4)
- Gao–Rexford model — Valley-free routing economics
