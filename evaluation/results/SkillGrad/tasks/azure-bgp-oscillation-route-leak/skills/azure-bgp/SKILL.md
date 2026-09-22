---
name: azure-bgp
description: "Detect Azure-style BGP oscillation and route leaks, then recommend policy-level mitigations while rejecting prohibited connectivity-disabling fixes."
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

**For oscillation:**

- **Filter routes learned from a peer before re-advertising** — Removes one edge of the preference cycle
- **Why this works**: In a cycle where Hub A prefers routes via Hub B and vice versa, filtering breaks one "leg":
  - If Hub A filters routes learned from Hub B before re-announcing, Hub B stops receiving routes via Hub A
  - Hub B can no longer prefer the path through Hub A because it no longer exists
  - The cycle collapses, routing stabilizes

**For route leaks:**

- **Enforce valley-free export rules** — Prevent announcing provider/peer-learned routes to peers/providers
- **Use communities** (e.g., `no-export`) where applicable
- **Ingress filtering** — Reject routes with invalid AS_PATH from peers
- **RPKI origin validation** — Cryptographically rejects BGP announcements from ASes that are not authorized to originate a given prefix, preventing many accidental and sub-prefix leaks from propagating

**Limitation:**
Does not control forwarding if multiple valid paths remain.

### Tier 3 — User Defined Routes (UDR)

**Applies to:**
- ✔ Oscillation
- ✔ Route leaks

**Purpose:**
Authoritative, static routing mechanism in Azure that explicitly defines the next hop for network traffic based on destination IP prefixes, overriding Azure system routes and BGP-learned routes.

**Routing Behavior:**
Enforces deterministic forwarding independent of BGP decision processes. UDRs operate at the data plane layer and take precedence over dynamic BGP routes.

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

## Common Pitfalls

- ❌ **Timer tuning or dampening fixes oscillation** — False. These reduce symptoms but don't break preference cycles.
- ❌ **Accepting fewer prefixes prevents route leaks** — False. Ingress filtering alone doesn't stop export of other leaked routes.
- ❌ **Removing peers is a valid mitigation** — False. This is prohibited in Azure.
- ❌ **Restarting gateways fixes root cause** — False. Only resets transient state.

## Output Expectations

A correct solution should:

1. Identify oscillation and/or route leak correctly
2. Explain why it occurs (preference cycle or valley-free violation)
3. Recommend allowed policy-level fixes
4. Explicitly reject prohibited fixes with reasoning

**Termination guard (must pass before ending the run): deliverable write + read-back verification**

Before *any* termination action, do the file-based deliverable steps as the last operation:

1. **Write:** write the deliverable to the **exact** required harness path (directory + filename).
2. **Verify:** read it back from disk, parse as JSON, and confirm it contains the **required top-level keys**.
3. **Block termination:** if either step did not just happen successfully, do **not** call `end_turn`; instead, write/verify again until it passes.

**Mandatory pre-termination template (fill in immediately before ending; do not skip):**

- deliverable_path: <exact required path>
- wrote_file_this_run: <yes/no>
- verified_parse_and_schema_this_run: <yes/no>

**Self-interrupt rule:** if you are about to end and any value above is `no`, treat that as an error state: stop, run the write+verify procedure, then re-fill the template with `yes` values.

Read references/write-and-verify-output-json.md when the task is graded by a required on-disk JSON artifact (exact path + schema).
Skip when the platform captures the final answer from chat text (no file-based deliverable).

## References

- RFC 4271 — Border Gateway Protocol 4 (BGP-4)
- Gao–Rexford model — Valley-free routing economics
