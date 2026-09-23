---
name: map-optimization-strategy
description: Strategy for solving constraint optimization problems on spatial maps. Use when you need to place items on a grid/map to maximize some objective while satisfying constraints.
---

# Map-Based Constraint Optimization Strategy

A systematic approach to solving placement optimization problems on spatial maps. This applies to any problem where you must place items on a grid to maximize an objective while respecting placement constraints.

## Why Exhaustive Search Fails

Exhaustive search (brute-force enumeration of all possible placements) is the **worst approach**:

- Combinatorial explosion: Placing N items on M valid tiles = O(M^N) combinations
- Even small maps become intractable (e.g., 50 tiles, 5 items = 312 million combinations)
- Most combinations are clearly suboptimal or invalid

## The Three-Phase Strategy

### Phase 1: Prune the Search Space

**Goal:** Eliminate tiles that cannot contribute to a good solution.

Remove tiles that are:
1. **Invalid for any placement** - Violate hard constraints (wrong terrain, out of range, blocked)
2. **Dominated** - Another tile is strictly better in all respects
3. **Isolated** - Too far from other valid tiles to form useful clusters

```
Before: 100 tiles in consideration
After pruning: 20-30 candidate tiles
```

This alone can reduce search space by 70-90%.

### Phase 2: Identify High-Value Spots

**Goal:** Find tiles that offer exceptional value for your objective.

Score each remaining tile by:
1. **Intrinsic value** - What does this tile contribute on its own?
2. **Adjacency potential** - What bonuses from neighboring tiles?
3. **Cluster potential** - Can this tile anchor a high-value group?

Rank tiles and identify the top candidates. These are your **priority tiles** - any good solution likely includes several of them.

```
Example scoring:
- Tile A: +4 base, +3 adjacency potential = 7 points (HIGH)
- Tile B: +1 base, +1 adjacency potential = 2 points (LOW)
```

### Phase 3: Anchor Point Search

**Goal:** Find placements that capture as many high-value spots as possible.

1. **Select anchor candidates** - Tiles that enable access to multiple high-value spots
2. **Expand from anchors** - Greedily add placements that maximize marginal value
3. **Validate constraints** - Ensure all placements satisfy requirements
4. **Local search** - Try swapping/moving placements to improve the solution

For problems with a "center" constraint (e.g., all placements within range of a central point):
- The anchor IS the center - try different center positions
- For each center, the reachable high-value tiles are fixed
- Optimize placement within each center's reach

#### Make Phase 3 Operational (bounded search loop)

When maximizing an objective (not just finding *any* valid placement), do **not** stop after validating a single plausible configuration. Instead, run a **bounded** anchor search plus a small local-improvement loop.

1) **Enumerate anchor candidates (centers) in a bounded way**
- Build a set of feasible anchors from Phase 1 constraints.
- If this set is large, restrict to **top-K** anchors using a cheap proxy score (e.g., count of high-value tiles within the allowed radius, or sum of their tile scores).

2) **For each anchor, solve placements with a greedy pass**
- Fix the anchor.
- Recompute the candidate set within the anchor’s allowed range.
- Place items one-by-one by **marginal gain** (objective delta) while enforcing hard constraints after each addition (constraint propagation).

3) **Local improvement (small neighborhood search)**
Perform a limited number of improvement attempts so runtime stays predictable:
- Consider single-tile moves for one placed item to another candidate tile.
- Consider pairwise swaps of two placed items.
- Keep a change only if it improves the objective and remains valid.

Suggested bounds (tune to map size):
- `K_anchors = 10–30`
- `max_local_iters = 50–200`
- `max_neighbors_per_item = 10–30` (e.g., evaluate only the top-N alternative tiles by heuristic)

4) **Track best-so-far with a strict validator**
Maintain `best_solution` across anchors and local steps. Every time you accept a new best:
- Re-validate all placements against the hard constraints.
- Recompute the objective from the authoritative scoring rules.

**Fallback/verification step:** If the search budget is exhausted, return the best validated solution found so far (never an unvalidated intermediate). If results are unexpectedly low or unstable, increase K slightly or widen the local neighborhood, but keep the search bounded.

## Algorithm Skeleton

```python
def optimize_placements(map_tiles, constraints, num_placements):
    # Phase 1: Prune
    candidates = [t for t in map_tiles if is_valid_tile(t, constraints)]

    # Phase 2: Score and rank
    scored = [(tile, score_tile(tile, candidates)) for tile in candidates]
    scored.sort(key=lambda x: -x[1])  # Descending by score
    high_value = scored[:top_k]

    # Phase 3: Anchor search
    best_solution = None
    best_score = 0

    for anchor in get_anchor_candidates(high_value, constraints):
        solution = greedy_expand(anchor, candidates, num_placements, constraints)
        solution = local_search(solution, candidates, constraints)

        if solution.score > best_score:
            best_solution = solution
            best_score = solution.score

    return best_solution
```

## Key Insights

1. **Prune early, prune aggressively** - Every tile removed saves exponential work later

2. **High-value tiles cluster** - Good placements tend to be near other good placements (adjacency bonuses compound)

3. **Anchors constrain the search** - Once you fix an anchor, many other decisions follow logically

4. **Greedy + local search is often sufficient** - You don't need the global optimum; a good local optimum found quickly beats a perfect solution found slowly

5. **Constraint propagation** - When you place one item, update what's valid for remaining items immediately

## Common Pitfalls

- **Ignoring interactions** - Placing item A may change the value of placing item B (adjacency effects, mutual exclusion)
- **Over-optimizing one metric** - Balance intrinsic value with flexibility for remaining placements
- **Forgetting to validate** - Always verify final solution satisfies ALL constraints

- **Single-shot confirmation** - Validating one hand-picked layout is not an optimization strategy. Use a bounded anchor loop + local improvements to reliably find a better (or best-found) solution under a fixed time budget.

- **Shell heredoc + chaining mistakes** - If your executor/tool has a single-command constraint, either (a) write the output in one command and verify in a second command, or (b) chain only with operators that are part of the same shell command. When using a heredoc (`<<'PY'`), ensure the terminator line ends the command cleanly—do not append extra tokens on the terminator line.
