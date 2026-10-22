# civ6lib: Civ6 District Placement and Adjacency Optimization

## Purpose
Reusable workflow and rules reference for Civilization 6 (Gathering Storm) district placement optimization tasks: load a map, generate legal district placements, maximize total adjacency, and emit a verifier-aligned JSON artifact. Rules tables are a cheatsheet; the Procedure is the executable contract.

## When to Use
Trigger when a task provides a Civ6 map (typically a .Civ6Map SQLite file or an equivalent tile dump) and asks for district placements, adjacency bonuses, or legality validation for one or more cities under Gathering Storm rules.

## Procedure
- ### Checkpoint 1 - Discover (environment and inputs)
- Read the task statement for: input map path, city center coordinate(s), population(s), required output path, required JSON schema, and any district-set constraints. Do not assume values from prior tasks.
- Locate the library beside this skill: find `placement_rules.py`, `adjacency_rules.py`, and the hex utilities module in the same package directory (do not hardcode `src.hex_utils`; discover with a directory listing).
- If the input is a .Civ6Map SQLite file, discover its schema with `sqlite3 <file> ".schema"`. Expect tables like `Plots`, `PlotFeatures`, `PlotResources`, `PlotRivers`, `Map`. Confirm column names before querying.
- Expected signal: a printed schema listing and a resolved import path for the library modules. ### Checkpoint 2 - Validate inputs and build Tile grid
- Build a `{(x,y): Tile}` dict covering the full map. For each plot populate terrain, feature, resource, elevation/hills, and river edges.
- River edges: Civ6 encodes river presence per plot edge direction (commonly E, SE, SW for one plot and the mirrored W, NW, NE on the neighbor). Decode by consulting the discovered `PlotRivers` columns; mirror edges to adjacent tiles so both sides agree. Verify by spot-checking: a river edge on tile A toward direction d must appear on neighbor(A,d) in the opposite direction.
- Instantiate `PlacementRules` and `AdjacencyCalculator` via the library's `get_*` factories. Pass city_center and population read from the task, not from any example in this skill.
- Expected signal: `len(tiles)` equals map width*height; a few sampled tiles print with plausible terrain/features/rivers. ### Checkpoint 3 - Act (ranked search with pruning)
- Enumerate candidate tiles per required district:
- Filter by universal placement rules (distance <= 3 from city center, not mountain/NW/strategic/luxury, unoccupied).
- Filter by district-specific rules (Harbor/Water Park on coast adjacent to land, Aqueduct adjacency+fresh water, Dam on floodplain river, Encampment/Preserve not adjacent to city center, etc.).
- Score each candidate by an upper-bound adjacency estimate (count neighboring mountains, rivers, wonders, resources, and max possible district-neighbors) and sort descending.
- Run backtracking over the ranked candidates:
- Respect specialty-district cap `1 + floor((pop-1)/3)` and uniqueness rules.
- Account for feature destruction: placing a district removes Woods/Rainforest/Marsh/bonus resources on that tile, which can lower a later district's bonus. Recompute, do not cache stale adjacency.
- Prune when (current_total + sum of remaining upper bounds) <= best_known_total.
- Expected signal: monotonically improving `best_known_total` printed per improvement. ### Checkpoint 4 - Emit output JSON
- Write placements and adjacency to the exact path specified by the task, using the exact field names from the task's schema. Compute per-district bonuses with `AdjacencyCalculator` on the final tile state (after all placements, so district-neighbor bonuses are mutual).
- Expected signal: file exists and parses as JSON. ### Checkpoint 5 - Verify (post-write reload)
- Reload the written JSON. Assert, in code, all of the following before claiming completion:
- Each placement passes `PlacementRules.validate_placement` against the final tile state.
- Specialty district count <= `1 + floor((pop-1)/3)`; uniqueness rules hold.
- Recomputed total adjacency equals the stored total; each stored per-district bonus equals the recomputed value (remember: minor +0.5 sources are floored per source type, then summed).
- Expected signal: printed line `post-write validation: OK`. On failure, repair placements and rewrite; do not finalize. ### Checkpoint 6 - Recover (time-budget fallback)
- Before starting backtracking, write a greedy baseline JSON (place each required district on its top-ranked legal tile, recomputing after each placement). This guarantees a valid artifact exists.
- If the search exceeds the configured wall-clock budget, keep the best valid solution found and re-run Checkpoint 5 on it. Never leave the output path with an invalid or partial file. ## Library API (reference, no instance values) ```python from civ6lib import ( DistrictType, Tile, PlacementRules, get_placement_rules, AdjacencyCalculator, get_adjacency_calculator, validate_district_count, validate_district_uniqueness, ) rules = get_placement_rules(tiles, city_center=<from_task>, population=<from_task>) calc  = get_adjacency_calculator(tiles) ``` ## Rules Cheatsheet (Gathering Storm) ### Universal district placement
- Within 3 tiles of city center; not on mountain, natural wonder, strategic or luxury resource, or occupied tile.
- Placing a district destroys Woods, Rainforest, Marsh, and bonus resources on that tile (affects neighbors' adjacency). ### District-specific
- Harbor / Water Park: coast or lake, adjacent to land.
- Aerodrome / Spaceport: flat land.
- Encampment / Preserve: not adjacent to city center.
- Aqueduct: adjacent to city center AND adjacent to Mountain/River/Lake/Oasis.
- Dam: on floodplains, river crosses 2+ edges of the tile. ### Specialty cap and uniqueness
- Max specialty districts = `1 + floor((pop-1)/3)`.
- Non-specialty (do not count): Aqueduct/Bath, Neighborhood/Mbanza, Canal, Dam, Spaceport.
- One per city: Campus, Holy Site, Theater Square, Commercial Hub, Harbor, Industrial Zone, Entertainment Complex, Water Park, Encampment, Aerodrome, Preserve.
- One per civ: Government Plaza, Diplomatic Quarter. ### Adjacency (key cases)
- Campus: +2 Geothermal Fissure/Reef, +1 Mountain, +0.5 Rainforest, +0.5 District (each floored separately).
- Holy Site: +2 Natural Wonder, +1 Mountain, +0.5 Woods, +0.5 District.
- Theater Square: +2 Wonder, +2 Entertainment Complex/Water Park, +0.5 District.
- Commercial Hub: +2 if on river (binary), +2 Harbor, +0.5 District.
- Harbor: +2 City Center, +1 coastal resource (Fish/Crabs/Whales/Pearls), +0.5 District.
- Industrial Zone: +2 Aqueduct/Dam/Canal, +1 Quarry/Strategic, +0.5 Mine, +0.5 Lumber Mill, +0.5 District (each type floored separately).
- Government Plaza: +1 to each adjacent specialty district; itself has no adjacency bonus.
- No adjacency: Entertainment Complex, Water Park, Encampment, Aerodrome, Spaceport, Preserve, Government Plaza.
- Counts for +0.5-per-district: Campus, Holy Site, Theater Square, Commercial Hub, Harbor, Industrial Zone, Entertainment Complex, Water Park, Encampment, Aerodrome, Spaceport, Government Plaza, Diplomatic Quarter, Preserve, City Center, Aqueduct, Dam, Canal, Neighborhood.

## Constraints / Pitfalls
- Floor each minor (+0.5) source type separately, then sum; never floor the combined count.
- Discover the hex utilities module path from the library package layout; do not import from a hardcoded `src.*` path.
- Read city_center, population, required districts, output path, and JSON field names from the task statement each time; do not reuse values from examples in this skill.
- Mirror river edges across adjacent tiles after parsing; a one-sided river encoding will corrupt Commercial Hub and Dam legality.
- Always write a schema-valid greedy baseline before running the pruned search, and re-run the Checkpoint 5 reload-and-assert on the final file before claiming completion.
- Recompute adjacency on the final tile state after all placements (features destroyed by earlier placements must not inflate later bonuses).