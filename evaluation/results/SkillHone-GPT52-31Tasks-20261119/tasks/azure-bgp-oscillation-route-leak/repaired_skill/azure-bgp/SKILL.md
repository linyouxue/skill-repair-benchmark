---
name: azure-bgp
description: "Analyze BGP oscillation (preference cycles) and route leaks (valley-free violations) in Azure Virtual WAN–style managed hub topologies. Detect cycles/leaks from small JSON inputs and classify candidate mitigations, preferring policy-level fixes while rejecting prohibited topology teardown."
---

# Azure BGP Oscillation & Route Leak Analysis

Analyze and resolve BGP oscillation and BGP route leaks in Azure Virtual WAN–style hub-and-spoke topologies (and similar cloud-managed BGP environments).

This skill trains an agent to:

- Detect preference cycles that cause BGP oscillation
- Identify valley-free violations that constitute route leaks
- Classify candidate mitigations by whether they actually resolve the *defined* problem
- Prefer allowed, policy-level mitigations (routing intent / route table propagation, export policy, communities, UDR) while rejecting prohibited “topology teardown” fixes

The focus is cloud-correct reasoning: you generally can’t “SSH into the router” in managed services, so you must reason in terms of routing policy, route propagation, and intent.

## Fast Success Recipe (Grader-Facing)

1. **List the input directory** (commonly `/app/data`) and identify:
   - `preferences.json` (for oscillation)
   - a route-leak event file (often `route_events.json`)
   - `possible_solutions.json` (for solution classification)
2. **Compute findings**:
   - **Oscillation:** find any cycle in the `prefer_via` pointer graph.
   - **Route leak:** flag any event where a route learned from `peer/provider` is exported to `peer/provider` (valley-free violation).
3. **Write the required report file** (commonly `/app/output/oscillation_report.json`) and **do not finish** until the file exists and is valid JSON.
   - Always emit **all required keys**; use empty lists when nothing is detected.
   - Preserve **exact solution strings** as `solution_results` keys (load the JSON and iterate; do not retype).

**Important:** Any JSON shown in the prompt is typically a *format example*, not the correct values for this instance. Do **not** copy booleans/ASNs from the example—derive them from the input files.

## When to Use This Skill

Use this skill when a task involves:

- Azure Virtual WAN, hub-and-spoke BGP, ExpressRoute, or VPN gateways
- Repeated route flapping or unstable path selection
- Unexpected transit, leaked prefixes, or valley-free violations
- Evaluating whether a proposed “fix” is valid/allowed in Azure-managed connectivity
- Producing a structured report (often a JSON artifact) from small input files

## Core Invariants (High Priority, but Prompt Overrides)

In many Azure managed connectivity scenarios (e.g., Virtual WAN inter-hub routing), the platform controls the underlying sessions.

- Prefer **routing policy / propagation control** over tearing down topology.
- Be cautious with advice like “disable the platform BGP session” when the session is provider-managed.

**Important:** Some tasks include “bad” options (disable peering, shut BGP, restart sessions) inside `possible_solutions.json` specifically so you can *classify* them.

- In Azure-managed Virtual WAN contexts, assume you **cannot** (or must not) fix control-plane issues by tearing down platform connectivity (disabling provider-managed sessions, disabling hub peering, removing connectivity). Treat these as **not resolving** unless the prompt explicitly frames them as allowed/hypothetical.
- If the prompt explicitly allows teardown/shutdown as an acceptable action, then classify by the prompt’s definition of “resolved” (while noting operational impact).

## Task-First Mental Model: Control Plane vs Data Plane

Many “solutions” only affect one plane:

- **Control plane (BGP advertisements + preferences):** determines what routes are learned/advertised and which path is *selected* by BGP.
- **Data plane (forwarding):** determines where packets actually go.

Automated graders often define “resolved” in control-plane terms (e.g., “break the preference cycle”, “stop advertising leaked routes”).

**Rule:** Follow the task’s stated resolution criteria, even if a mitigation would “stabilize forwarding” without fixing the control plane.

## Expected Inputs (Typical)

Tasks using this skill commonly provide small JSON files such as:

| File | Meaning |
|------|---------|
| `topology.json` | Directed adjacency graph (who can advertise to whom) |
| `relationships.json` | Economic relationship per directed edge (`provider`, `customer`, `peer`) |
| `local_pref.json` | Optional mapping from relationship type → weight (customer > peer > provider) |
| `preferences.json` | Optional explicit per-AS preferred next hop / “prefer_via” pointers |
| `route.json` | Prefix and origin ASN (often informational) |
| `route_events.json` / `route_leaks.json` | Observed advertisements/propagation events to validate valley-free violations |
| `possible_solutions.json` | Candidate fixes to classify |

Notes:
- Datasets vary: some include both directions for provider/customer edges, others only one direction. Prefer using the provided directionality, and infer the reverse only if the task expects symmetry.
- The “leak evidence” file may be named differently; look for a list of events that includes *advertiser*, *source/learned-from*, and *destination/export-to*.

## Reasoning Workflow (Executable Checklist)

### Step 0 — Read the Prompt Contract

Before analyzing, identify:

- The required output file path (often under `/app/output/`)
- The exact JSON schema/keys expected
- The definition of “resolved” for oscillation and leaks (tasks may define this explicitly)

### Step 1 — Load and Normalize Inputs

- Load all JSON inputs from the specified directory.
- Build a relationship lookup `rel[(a,b)] -> type`.
- If relationship types appear in multiple places (event fields vs `relationships.json`), prefer the canonical topology/relationships file when available.

### Step 2 — Detect BGP Oscillation (Preference Cycle)

**Definition:** Oscillation is possible when ASes form a *preference cycle* (e.g., each prefers a route via the other).

**Detection rule (task-friendly):**

1. Build a directed graph `ASN → preferred next-hop ASN`.
   - If `preferences.json` exists, use it.
   - Otherwise, you may derive a preference order from `local_pref.json` + candidate next hops (only if the task expects you to).
2. If the graph contains any cycle, report `oscillation_detected: true` and output the cycle ASNs.

**Implementation tip:** following “next hop pointers” and checking for a repeated ASN finds cycles efficiently.

### Step 3 — Detect BGP Route Leak (Valley-Free Violation)

**Valley-free export rule (Gao–Rexford):**

| Route learned from | May export to |
|---|---|
| Customer | Anyone |
| Peer | Customers only |
| Provider | Customers only |

A route leak exists when an AS exports a route learned from a **peer/provider** to a **peer/provider**.

**Practical detection:**

For each observed event (advertiser exports route learned from source to destination):

- Determine `source_type` = relationship of *(source → advertiser)* (how advertiser learned it)
- Determine `destination_type` = relationship of *(advertiser → destination)* (how advertiser exported it)
- Flag a leak if `source_type in {peer, provider}` **and** `destination_type in {peer, provider}`

Only flag leaks you can justify from the provided relationship data.

### Step 4 — Classify Candidate Solutions (Resolution Semantics)

Tasks often ask you to fill booleans like `oscillation_resolved` and `route_leak_resolved` for each proposed solution.

#### 4A. What counts as **oscillation_resolved**

Mark **true** only if the solution satisfies the prompt’s resolution rule. Most tasks define oscillation resolution as:

- **Control-plane fix:** it must *break the routing preference cycle in the topology*.

Typical “cycle breakers” (must change the **preference graph** for the affected route(s), not just convergence timing):

- Explicitly changing routing preference so one hub/AS no longer prefers routes via the other
- Setting a deterministic preference hierarchy / local preference ordering that removes the cyclic dependency
- Adjusting **BGP decision attributes** that define preference ordering (e.g., LOCAL_PREF, AS-PATH length, MED) to impose a strict, non-cyclic ranking for the affected route(s)

**Not** cycle breakers by themselves:

- **Export-only** controls (no-export/export filters) that merely stop advertising to a neighbor but do **not** change how either hub prefers the remaining paths
- “Routing intent”/centralized forwarding policy **unless** the prompt explicitly defines it as changing hub-to-hub preference selection (many intents affect forwarding/propagation, not the `prefer_via` pointers)

Mark **false** for symptom mitigations that do not change the preference graph, e.g.:

- Timer tuning (keepalive/holdtime), “wait for convergence”, restarting sessions
- Route dampening (may reduce flaps but does not remove the cycle)
- ECMP/load-balancing
- Prefix-scoped filtering that does **not** affect the routes that participate in the cycle (e.g., filtering unrelated prefixes)
- Data-plane-only overrides (UDR) **unless** the prompt explicitly defines resolution as “forwarding is stable” rather than “cycle is broken”

#### 4B. What counts as **route_leak_resolved**

First, use the prompt’s definition. Two common cases:

1. **Root-cause definition (common):** “resolved” means the leaker stops violating valley-free export (i.e., the offending export no longer occurs).
2. **Containment definition (sometimes):** “resolved” means leaked routes no longer propagate/are accepted/used.

If the prompt says “stop advertising/exporting” (root-cause wording), then:

- Mark **true** for solutions that implement **export-side** controls:
  - Export policy / outbound route filters
  - `no-export` (or equivalent) communities applied/enforced on export
  - Route table propagation/association restrictions (e.g., Virtual WAN routing policy/intent *when described as controlling propagation*)
  - **Hard stop options (rare / usually disallowed):** removing the offending advertisement path (e.g., disabling the specific hub-to-hub peering/session) would stop advertising, but in Azure-managed contexts you should treat this as **not resolving** unless the prompt explicitly allows/hypothesizes teardown/shutdown.
- Mark **false** for fixes that are **import-only** or **orthogonal** to export behavior:
  - Ingress filtering (protects the receiver but does not stop the leaker advertising)
  - RPKI origin validation (validates origin authorization; does not stop the leaker exporting provider/peer-learned routes)
  - Max-prefix limits (resource protection; does not enforce valley-free export)

If the prompt instead says “stop being accepted/used”, import filtering or UDR may count.

#### 4C. Prohibited / invalid fixes (Azure-managed default)

In Azure Virtual WAN / managed hub scenarios, treat these as **not valid resolutions** unless the prompt explicitly allows them:

- Disable provider-managed BGP sessions
- Disable hub peering / remove connectivity
- “Restart devices/sessions” as a root-cause fix

(These may stop symptoms, but they are typically out of scope or disallowed in managed services and are commonly included as distractor options.)

### Step 5 — Emit the Required Report Artifact

- Write the JSON report to the required output path.
- Preserve *exact* solution strings as keys if the schema uses the solution text as the map key.
- Include every solution from `possible_solutions.json` in `solution_results`.

## Common Pitfalls (Grader-Relevant)

- ❌ Treating timer tuning, dampening, restarts, “wait for convergence”, or ECMP as resolving oscillation.
- ❌ Treating RPKI origin validation as fixing an *export* valley-free leak (RPKI checks origin authorization; it does not directly stop a customer exporting provider-learned routes).
- ❌ Marking ingress filtering as “route leak resolved” when the prompt requires the leaker to stop advertising.
- ❌ Marking “disable peering / shut session” options as resolving in Azure-managed contexts unless the prompt explicitly allows them.
- ❌ Changing/normalizing solution strings so they don’t match the input keys.

## References

- RFC 4271 — Border Gateway Protocol 4 (BGP-4)
- Gao–Rexford model — Valley-free routing economics
