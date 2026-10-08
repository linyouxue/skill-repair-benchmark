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

Tasks using this skill typically provide small JSON files, but **you must follow the task prompt’s filenames and schemas** (do not assume a fixed set).

For this benchmark style, expect inputs under the specified data directory such as:

| File | Meaning |
|------|---------|
| `route.json` | Route advertisement information (who advertises what to whom; may include “via Virtual WAN” metadata) |
| `preferences.json` | Routing preferences between hubs/ASNs (used to build the preference-dependency graph for oscillation detection) |
| `local_pref.json` | Relationship-type weights or local-pref mapping used to classify links (e.g., provider/customer/peer) for valley-free/leak checks |
| `possible_solutions.json` | Candidate fixes to evaluate by simulating whether they (a) break the preference cycle and/or (b) stop hub-to-hub advertisement via Virtual WAN |

If additional files (e.g., topology/relationships) are present, treat them as optional helpers and merge them cautiously—never hardcode required filenames beyond what the task specifies.

## Reasoning Workflow (Executable Checklist)

### Step 1 — Sanity-Check Inputs

- Confirm all required task-specified files exist and parse as JSON.
- Identify the entity keys used (e.g., ASN integers vs hub IDs) and normalize them consistently.
- **Do best-effort validation, not hard failure**:
  - If a topology/relationship view is incomplete or asymmetric, continue with the information available.
  - When relationship direction is unclear, derive relationship *types* from the provided `local_pref.json`/weights as the source of truth and document any unknowns rather than declaring the input invalid.

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

### Tier 1 — Virtual WAN Routing Intent (Use Carefully)

**Important (benchmark correctness constraint):**
- A solution **resolves oscillation** only if it **breaks the routing-preference cycle** (i.e., removes/reorients at least one preference dependency so the preference graph is acyclic).
- A solution **resolves a route leak** only if it **stops hub1/hub2 from advertising routes to hub2/hub1 via Virtual WAN** (i.e., changes export/propagation behavior, not merely forwarding choice).

**What Routing Intent can and cannot do:**
- Routing Intent may make **forwarding** deterministic, but that does **not** automatically mean:
  - the BGP preference cycle is broken, or
  - the leak advertisements stop being propagated.

**How to evaluate it in this task:**
- Mark `oscillation_resolved = true` **only if** the intent/policy as described would change preferences such that the preference-dependency cycle disappears.
- Mark `route_leak_resolved = true` **only if** the intent/policy explicitly prevents hub-to-hub propagation/advertisement via Virtual WAN (e.g., disables inter-hub route propagation for the leaked prefixes, or applies an export filter/policy that stops re-advertisement).

If the solution text only claims “override forwarding” or “prefer a hub” without changing BGP preference dependencies or export behavior, treat it as **not resolved** for the corresponding control-plane issue.

### Tier 2 — Export / Route Policy (Protocol-Correct)

**For oscillation:**

- **Filter routes learned from a peer before re-advertising** — Removes one edge of the preference cycle
- **Why this works**: In a cycle where Hub A prefers routes via Hub B and vice versa, filtering breaks one "leg":
  - If Hub A filters routes learned from Hub B before re-announcing, Hub B stops receiving routes via Hub A
  - Hub B can no longer prefer the path through Hub A because it no longer exists
  - The cycle collapses, routing stabilizes

**Example (derive identifiers from input):**
If Hub/AS **A** filters routes learned from Hub/AS **B** before re-advertising them onward, then **B** can no longer select a path “via A” for those routes. This removes one dependency edge in the preference graph and can break the oscillation cycle **if** that edge was part of the cycle found from `preferences.json`.

**For route leaks:**

- **Enforce valley-free export rules** — Prevent announcing provider/peer-learned routes to peers/providers
- **Use communities** (e.g., `no-export`) where applicable
- **Ingress filtering** — Reject routes with invalid AS_PATH from peers
- **RPKI origin validation** — Cryptographically rejects BGP announcements from ASes that are not authorized to originate a given prefix, preventing many accidental and sub-prefix leaks from propagating

**Limitation:**
Does not control forwarding if multiple valid paths remain.

### Tier 3 — User Defined Routes (UDR)

**Benchmark constraint:** UDRs are primarily a **data-plane override**. In this task’s scoring rules:
- UDRs **do not resolve oscillation** unless they **break the routing-preference cycle** (UDRs usually do not change BGP preferences).
- UDRs **do not resolve route leaks** unless they **stop hub-to-hub advertisement via Virtual WAN** (UDRs usually do not change what routes are advertised).

**How to evaluate UDR solutions here:**
- If the proposal is purely “force next hop / override forwarding,” set:
  - `oscillation_resolved = false` (cycle still exists),
  - `route_leak_resolved = false` (leak advertisements still occur).
- Only mark resolved if the solution explicitly includes **control-plane policy changes** that eliminate the preference cycle and/or stop the inter-hub re-advertisement via Virtual WAN.

UDRs may still be useful operationally for containment, but containment ≠ resolution under the required criteria.

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

All are false.

## Output Expectations

A correct solution should:

1. Identify oscillation and/or route leak correctly
2. Explain why it occurs (preference cycle or valley-free violation)
3. Recommend allowed policy-level fixes
4. Explicitly reject prohibited fixes with reasoning

## References

- RFC 4271 — Border Gateway Protocol 4 (BGP-4)
- Gao–Rexford model — Valley-free routing economics
