# BGP Oscillation and Route Leak Classification

## Purpose
Given a small set of JSON inputs describing a hub-and-spoke BGP topology and a list of candidate solution strings, decide whether BGP oscillation and/or a route leak exist and, for each candidate solution, independently decide whether it mechanically resolves oscillation and whether it mechanically resolves the leak. Emit a single JSON report conforming to the task's schema.

## When to Use
Task provides topology, relationship, local-preference, and route/event JSON files plus a list of candidate fixes, and asks for a structured report classifying each fix.

## Procedure
- Discover inputs. List the input directory (do not assume filenames). Bind files by semantic role: adjacency graph, edge relationship (provider/customer/peer), per-ASN preferred next hop (e.g. `preferences.json` or `local_pref.json`), originated route, propagation events or leak evidence (e.g. `route_leaks.json` or `route_events.json`), and candidate solutions. Confirm relationship symmetry and that every ASN referenced exists.
- Detect conditions.
- Oscillation: build directed graph ASN -> preferred-next-hop ASN; any cycle (including a 2-cycle) implies oscillation.
- Route leak: a route learned from a provider or peer that is exported to a provider or peer violates valley-free. Hub re-advertising another hub's routes via the Virtual WAN hub counts as a leak when the task evidence shows such propagation.
- Classify each candidate solution using this rubric (independent booleans): | Category (match by semantics, not substring) | oscillation_resolved | route_leak_resolved | |---|---|---| | Virtual WAN routing intent enforcing single forwarding hierarchy | true | true | | Export filter on a hub that drops routes learned from the other hub before re-advertisement | true | true | | UDR pinning deterministic next hop | true | true | | Ingress filter / no-export community preventing hub-to-hub re-advertisement via VWAN | depends on whether it breaks the cycle edge | true | | RPKI origin validation only | false | partial: only if it blocks the specific leaked prefix | | BGP timer tuning, route dampening, device restart | false | false | | Disable BGP, shut down peering, remove connectivity | false | false (and flag as prohibited if legality is asked) | A solution resolves oscillation only if it removes at least one edge of the prefer_via cycle. A solution resolves the leak only if it stops the offending hub from re-advertising routes to the other hub via the VWAN hub.
- Write and verify. Write `/app/output/oscillation_report.json` with keys `oscillation_detected`, `route_leak_detected`, and `solutions` (list of `{solution, oscillation_resolved, route_leak_resolved}` preserving input order and strings). Reload the file and assert all keys, types, and that `route_leak_resolved` is `false` whenever `route_leak_detected` is `false`.

## Constraints / Pitfalls
- Do not match solutions by raw substring; map each string to a rubric category first, then read off the two bits.
- Keep legality judgments separate from mechanical resolution: a prohibited fix may still mechanically break a cycle; report the mechanical bits truthfully and only invoke the prohibition list when the task explicitly asks whether a fix is allowed.
- Do not hard-code input filenames or ASNs; derive them from discovery. If a referenced field is absent, record the gap and choose the most conservative boolean (false) for that criterion.