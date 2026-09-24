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
| `route_leaks.json` | Evidence of invalid propagation |
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

## Fix Selection Logic (Ranked)

> **Classification discipline (applies to every candidate solution).**
> When a task asks per-solution `(oscillation_resolved, route_leak_resolved)`, evaluate the two flags with **independent predicates**. Never let one flag become true as a side effect of the other.
>
> - `oscillation_resolved = True` **only if** the solution does at least one of:
>   1. Mutates or overrides a `prefer_via` entry in the preference graph (e.g., changes hub1's preference to stop preferring via hub2, sets a preference hierarchy that demotes the peer hub).
>   2. Filters the specific route **learned from the peer hub** before it is re-advertised or used, i.e., removes the exact edge in the cycle that the other side is preferring.
>   3. Imposes deterministic forwarding **above BGP** (Tier 1 routing intent, Tier 3 UDR) so BGP path selection no longer controls forwarding.
>
>   Solutions that only affect provider-sourced routes (export or ingress) leave both `prefer_via` entries and the peer-learned edge intact, so the mutual preference cycle still exists → oscillation is **not** resolved by them.
>
> - `route_leak_resolved = True` **only if** the solution stops hub1/hub2 from **advertising** provider/peer-learned routes to a non-customer (per Step 3's valley-free rule), or overrides forwarding such that the leaked route cannot be used for transit.

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

**For route leaks:**
- Prevents leaked peer routes from being used as transit
- When intent mandates hub-to-hub traffic goes through Virtual WAN (ASN 65001), leaked routes cannot be used
- Enforces valley-free routing by keeping provider routes in proper hierarchy

**Agent reasoning:**
If routing intent is available, recommend it first.

### Tier 2 — Export / Route Policy (Protocol-Correct)

Tier 2 mechanisms split into **two disjoint sub-classes**. When classifying a candidate solution, first identify which sub-class the solution's text describes; do not assume a policy in one sub-class also achieves the effect of the other.

#### 2a. Cycle-breaking filters (resolve oscillation, not the leak by themselves)

These modify the **peer-hub-learned** route or the preferring node's preference so the cycle edge disappears.

- **Update the preferring hub's `prefer_via`** so it no longer points at the other hub (mutates the cycle graph directly).
- **Set a route preference hierarchy** on a hub that demotes the peer hub below customer/Virtual-WAN routes (equivalent to overriding `prefer_via`).
- **Filter routes learned from the peer hub before re-advertising** (e.g., "filter routes learned from hub2 on hub1 before re-advertising"). Removes the leg the other hub prefers.

**Why this works:** In a cycle where Hub A prefers via Hub B and vice versa, removing the peer-learned edge from A means B no longer has "via A" as a candidate — the cycle collapses. Note this typically does **not** stop A from advertising its provider-learned routes onward, so it usually leaves the valley-free leak intact.

#### 2b. Leak-blocking export / ingress filters (resolve route leak, not oscillation by themselves)

These constrain what a hub **exports to a peer** (or what the peer accepts) for **provider- or peer-sourced** prefixes. They stop the valley-free violation but do **not** touch either hub's `prefer_via` entry, nor do they remove the specific peer-learned edge the other side prefers. The preference cycle survives.

- **Egress export policy that blocks provider-learned routes to a peer** (e.g., "block announcing provider routes from Virtual WAN to peer hub").
- **`no-export` community applied to provider-learned routes** before advertisement to a peer.
- **Ingress AS_PATH filter on the peer hub** rejecting routes whose AS_PATH traverses the Virtual WAN / provider ASN when received from the other hub.
- **RPKI origin validation** — treat as a categorical **leak-mitigation** mechanism per this skill's catalog. Do **not** downgrade it to "ineffective" by reasoning that the specific prefix's origin ASN happens to be legitimate; that is second-order simulation the classification task does not require.

**Limitation:** These stop the invalid advertisement or its acceptance, but the two hubs still mutually prefer each other in `preferences.json`, so oscillation is not resolved.

#### Label-vs-simulate rule

- If a candidate's text names a **well-known mitigation mechanism** (RPKI, `no-export`, valley-free export policy, ingress AS_PATH filter) and this skill's Tier 2 catalog assigns it to a category, apply the categorical label.
- Reserve prefix-level or numeric simulation for candidates whose text specifies a **concrete numeric constraint** (specific prefix list, max-prefix count, timer value) whose effect depends on the actual input route/topology.

### Tier 3 — User Defined Routes (UDR)

**Applies to:**
- ✔ Oscillation
- ✔ Route leaks

**Purpose:**
Authoritative, static routing mechanism in Azure that explicitly defines the next hop for network traffic based on destination IP prefixes, overriding Azure system routes and BGP-learned routes.

**Routing Behavior:**
Enforces deterministic forwarding independent of BGP decision processes. UDRs operate at the data plane layer and take precedence over dynamic BGP routes.

**For oscillation:**
- **Oscillation Neutralization** — Breaks the impact of BGP preference cycles by imposing a fixed forwarding path
- Even if vhubvnet1 and vhubvnet2 continue to flip-flop their route preferences, the UDR ensures traffic always goes to the same deterministic next hop

**For route leaks:**
- **Route Leak Mitigation** — Overrides leaked BGP routes by changing the effective next hop
- When a UDR specifies a next hop (e.g., prefer specific Virtual WAN hub), traffic cannot follow leaked peer routes even if BGP has learned them
- **Leaked Prefix Neutralization** — UDR's explicit next hop supersedes the leaked route's next hop, preventing unauthorized transit

**Use when:**
- Routing intent is unavailable
- Immediate containment is required

**Trade-off:**
UDR is a data-plane fix that "masks" the control-plane issue. BGP may continue to have problems, but forwarding is stabilized. Prefer policy fixes (routing intent, export controls) when available for cleaner architecture.

## Prohibited Fixes (Must Be Rejected)

These solutions are **always invalid**:

| Proposed Fix | Reason |
|--------------|--------|
| Disable BGP | Not customer-controllable |
| Disable peering | prohibited operation and cannot solve the issue |
| Shutdown gateways | Breaks SLA / shared control plane |
| Restart devices | Resets symptoms only |

**Required explanation:**

Cloud providers separate policy control from connectivity existence to protect shared infrastructure and SLAs.

**Why these are not allowed in Azure:**

BGP sessions and peering connections in Azure (Virtual WAN, ExpressRoute, VPN Gateway) **cannot be administratively shut down or disabled** by customers. This is a fundamental architectural constraint:

1. **Shared control plane**: BGP and peering are part of Azure's provider-managed, SLA-backed control plane that operates at cloud scale.
2. **Availability guarantees**: Azure's connectivity SLAs depend on these sessions remaining active.
3. **Security boundaries**: Customers control routing **policy** (what routes are advertised/accepted) but not the existence of BGP sessions themselves.
4. **Operational scale**: Managing BGP session state for thousands of customers requires automation that manual shutdown would undermine.

**Correct approach**: Fix BGP issues through **policy changes** (route filters, preferences, export controls, communities) rather than disabling connectivity.

## Common Pitfalls

- ❌ **Timer tuning or dampening fixes oscillation** — False. These reduce symptoms but don't break preference cycles.
- ❌ **Accepting fewer prefixes prevents route leaks** — False. Ingress filtering alone doesn't stop export of other leaked routes.
- ❌ **Removing peers is a valid mitigation** — False. This is prohibited in Azure.
- ❌ **Restarting gateways fixes root cause** — False. Only resets transient state.
- ❌ **A filter that stops the leak also breaks the oscillation** — False when the filter targets provider-sourced routes at export, or leaked routes at ingress AS_PATH inspection. Those filters do not touch either hub's `prefer_via` entry, so the mutual preference cycle remains. Only filters that remove the *peer-hub-learned* edge (or that mutate `prefer_via` / override forwarding) resolve oscillation.
- ❌ **RPKI is useless because this prefix's origin is already correct** — False for classification purposes. Treat RPKI as a categorical leak-mitigation mechanism unless the task explicitly requires simulating it on the concrete route.

All are false.

## Verification Step (before writing `solution_results`)

For each candidate solution, run this two-question checklist and record the answers:

1. **Oscillation check** — Does the solution (a) change a `prefer_via` entry, (b) filter the peer-hub-learned route before re-advertisement/use, or (c) enforce forwarding above BGP (Tier 1 or Tier 3)? If none, `oscillation_resolved = False`.
2. **Leak check** — Does the solution stop a hub from exporting provider-/peer-learned routes to a non-customer, or override forwarding so the leaked route cannot be used? If not, `route_leak_resolved = False`.

If a solution appears to satisfy both flags, confirm the two answers came from **different** properties of the solution (not the same property double-counted). If the same property is being used to satisfy both, re-check against the sub-class taxonomy in Tier 2a vs 2b.

## Output Expectations

A correct solution should:

1. Identify oscillation and/or route leak correctly
2. Explain why it occurs (preference cycle or valley-free violation)
3. Recommend allowed policy-level fixes
4. Explicitly reject prohibited fixes with reasoning

## References

- RFC 4271 — Border Gateway Protocol 4 (BGP-4)
- Gao–Rexford model — Valley-free routing economics
