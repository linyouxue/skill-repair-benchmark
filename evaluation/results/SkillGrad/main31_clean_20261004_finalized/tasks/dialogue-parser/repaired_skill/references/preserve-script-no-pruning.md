---
description: Preserve the full parsed dialogue script without pruning nodes/edges; compute reachability only as a diagnostic unless the task explicitly requests a reachable subgraph.
---

# Preserve full script (no pruning)

## Trigger

Read this when you are about to delete nodes/edges to:
- enforce reachability,
- “clean up” undefined targets by dropping edges,
- match a local sanity check.

## Procedure

1. **Build the full graph** from all declared sections and all declared transitions.
2. **Compute reachability as a report, not a transformation.** Keep the graph unchanged.
3. **If unreachable content exists**, decide based on the prompt/spec:
   - If the task asks for faithful parsing: keep unreachable nodes/edges.
   - If the task asks for reachable subgraph: prune, but only after you can justify the root and pruning rule.

```python
from collections import defaultdict, deque

def reachable_from(start_id, edges):
    adj = defaultdict(list)
    for e in edges:
        adj[e.source].append(e.target)

    seen, q = set(), deque([start_id])
    while q:
        cur = q.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        q.extend(adj.get(cur, ()))
    return seen

seen = reachable_from(start_id, edges)
unreachable_nodes = [n.id for n in nodes if n.id not in seen]
# Keep nodes/edges intact; report unreachable_nodes if needed.
```

## Runtime branch

- **If the evaluator requires reachability but not pruning:** raise/report the unreachable IDs and keep the full payload.
- **If the prompt explicitly requests a reachable subgraph:** prune *after* computing `seen`, and then verify that every remaining edge has both endpoints present.

## Verification

- After any pruning (only when requested), verify:
  - every edge’s `source` and `target` exist in the retained node ID set, and
  - the chosen root is correct per spec.

If verification fails: undo pruning and instead return the unpruned graph plus a diagnostic list of unreachable IDs.
