---
name: azure-bgp
description: Analyze and resolve BGP oscillation and BGP route leaks in Azure Virtual
  WAN–style hub-and-spoke topologies. Detect preference cycles, identify valley-free
  violations, and classify candidate solutions using principled rules — never hand-coded
  per-string verdicts.
---

# Azure BGP Oscillation & Route Leak Analysis
Analyze and resolve BGP oscillation and BGP route leaks in Azure Virtual WAN–style hub-and-spoke topologies (and similar cloud-managed BGP environments).
This skill trains an agent to:
- Detect preference cycles that cause BGP oscillation
- Identify valley-free violations that constitute route leaks
- Classify each candidate solution against the two task rules:
  1. **Oscillation resolved** iff the solution breaks the routing preference cycle in the topology
  2. **Route leak resolved** iff the solution stops hub1/hub2 from advertising routes to hub2/hub1 via Virtual WAN
- Reject prohibited fixes (disabling BGP, shutting down peering, removing connectivity)
## When to Use This Skill
Use this skill when a task involves:
- Azure Virtual WAN, hub-and-spoke BGP, ExpressRoute, or VPN gateways
- Repeated route flapping or unstable path selection
- Unexpected transit, leaked prefixes, or valley-free violations
- Choosing between routing intent, UDRs, or BGP policy fixes
- Evaluating whether a proposed "fix" is valid in Azure
## Core Invariants (Must Never Be Violated)
- ❌ BGP sessions between hubs **cannot** be administratively disabled by customers (owned by Azure)
- ❌ Peering connections **cannot** be shut down as a fix (breaks all other traffic)
- ❌ Removing connectivity is **not** a valid solution
- ✅ Problems **must** be fixed using routing policy, not topology destruction
**Any solution violating these rules is invalid — mark both `oscillation_resolved` and `route_leak_resolved` as false for such solutions.**
## Expected Inputs
| File | Meaning |
|------|---------|
| `topology.json` | Directed BGP adjacency graph |
| `relationships.json` | Economic relationship per edge (provider, customer, peer) |
| `preferences.json` | Per-ASN preferred next hop (may cause oscillation) |
| `local_pref.json` | Relationship type weight (used to reason about which relation wins) |
| `route.json` | Prefix and origin ASN advertised from vnet |
| `route_events.json` / `route_leaks.json` | Observed route propagation events (used to detect valley-free violations) |
| `possible_solutions.json` | Candidate fixes to classify |
Load and actually use each of these — do not leave `relationships.json`, `topology.json`, `local_pref.json`, or `route.json` inspected-but-unused. Cross-check the detected leak against `relationships.json` (e.g., confirm source_type of edge 65001→65002 and destination_type of edge 65002↔65003).
## Reasoning Workflow (Executable Checklist)
### Step 1 — Sanity-Check Inputs
- Every ASN referenced must exist in `topology.json`
- Relationship symmetry must hold:
  - `provider(A→B)` ⇔ `customer(B→A)`
  - `peer` must be symmetric
### Step 2 — Detect BGP Oscillation (Preference Cycle)
Build a directed graph `ASN → preferred next-hop ASN` from `preferences.json`. Any cycle (including 2-node) ⇒ oscillation. Emit the cycle as `oscillation_cycle` and its members as `affected_ases`.
```python
pref = {asn: prefer_via_asn, ...}
def find_cycle(start):
    path, seen, cur = [], {}, start
    while cur in pref:
        if cur in seen:
            return path[seen[cur]:]
        seen[cur] = len(path); path.append(cur); cur = pref[cur]
    return None
```
### Step 3 — Detect BGP Route Leak (Valley-Free Violation)
Valley-free rule:
| Learned from | May export to |
|--------------|---------------|
| Customer | Anyone |
| Peer | Customers only |
| Provider | Customers only |
A leak exists when a route learned from a **provider** or **peer** is exported to a **provider** or **peer**. Validate `source_type` / `destination_type` via `relationships.json` rather than trusting the event blob alone.
### Step 4 — Classify Each Candidate Solution by Rule (Not by String)
**Do not hand-author a per-string verdict table.** For each entry in `possible_solutions.json`, apply the two rules mechanically:
- `oscillation_resolved = True` **iff** the action removes at least one edge of the preference cycle detected in Step 2, or forces forwarding independent of the BGP decision so the cycle is inert. Concretely this requires one of:
  1. Overriding BGP path selection above BGP (Virtual WAN routing intent) — cycle becomes inert.
  2. Filtering/blocking the *export* of the cycled prefix on one hub so the opposite hub no longer receives it (an edge of the pref graph disappears).
  3. Changing local-preference / community handling on one hub such that its `pref[hub]` no longer points at the other hub in the cycle.
  4. A UDR whose next-hop replaces the BGP-chosen next-hop for the cycled prefix on at least one hub.
- `route_leak_resolved = True` **iff** the action stops the *leaker* (hub1 or hub2) from *advertising* the provider/peer-learned route to the other hub via Virtual WAN. Concretely this requires one of:
  1. Virtual WAN routing intent that suppresses hub-to-hub transit of these routes.
  2. An **egress / export** filter, community (`no-export`, `no-advertise`), or route-map on the leaker that drops the prefix before it is announced to Virtual WAN / the other hub.
  3. Disabling the specific advertisement / re-origination of provider-learned routes toward the peer hub.
Rules of thumb the agent must apply when classifying:
- ❌ **Ingress filtering on the receiver hub does NOT resolve the leak** — the leaker still advertises. It may reduce impact but fails the "stop hub advertising" rule.
- ❌ **`no-export`/community/export-block that only affects announcement does NOT by itself resolve oscillation** — the local-pref cycle on hub1/hub2 is unchanged unless the export block also removes the prefix from the peer hub's RIB (in which case the pref edge disappears and it *does* resolve oscillation). Reason about whether the export target is the other hub in the cycle before deciding.
- ❌ **UDR only resolves the leak if it prevents the leaker from advertising**; a UDR that merely redirects next-hop on the receiver stabilizes forwarding but does not stop the advertisement, so `route_leak_resolved=False`.
- ❌ **Timer tuning, dampening, keepalive/holdtime changes, gateway restarts, session resets** resolve neither.
- ❌ **Disabling BGP, shutting peering, removing connectivity** are prohibited invariants ⇒ both False.
- ✅ **Virtual WAN routing intent** typically resolves both.
- ✅ **Export filter / route-map / community on the leaker hub toward the other hub** resolves the leak; it also resolves oscillation *only when* the filtered prefix is the one driving the pref cycle.
For every candidate, write down which of the concrete mechanisms above it matches, and derive the two booleans from that — do not intuit them from the sentence.
## Fix Selection Logic (Ranked)
### Tier 1 — Virtual WAN Routing Intent
Operates above BGP. Resolves both oscillation and route leaks by making forwarding deterministic and suppressing hub-to-hub transit of leaked routes.
### Tier 2 — Export / Route Policy on the Leaker
Egress filters, communities (`no-export`), or route-maps applied on the *advertising* hub. Resolves the leak. Resolves oscillation *iff* the removed export is the edge feeding the pref cycle.
### Tier 3 — User Defined Routes (UDR)
Data-plane override. Resolves oscillation by pinning next-hop. Resolves the leak *only if* the UDR is placed such that the leaking hub no longer originates the advertisement — otherwise leak persists at the control plane.
## Prohibited Fixes (Must Be Rejected)
| Proposed Fix | Reason |
|--------------|--------|
| Disable BGP | Not customer-controllable |
| Disable / shutdown peering | Breaks all other traffic; not allowed |
| Shutdown gateways | Breaks SLA / shared control plane |
| Restart devices / reset sessions | Resets symptoms only |
| Timer / keepalive / holdtime tuning | Does not break the pref cycle or stop advertisement |
## Output Expectations
Produce `/app/output/oscillation_report.json` with:
- `oscillation_detected`, `oscillation_cycle`, `affected_ases` from Step 2
- `route_leak_detected`, `route_leaks[]` from Step 3, each with `leaker_as`, `source_as`, `destination_as`, `source_type`, `destination_type`
- `solution_results`: one entry per solution string in `possible_solutions.json`, with `oscillation_resolved` and `route_leak_resolved` derived by Step 4's rules (not hand-coded)
## References
- RFC 4271 — BGP-4
- Gao–Rexford model — Valley-free routing economics
