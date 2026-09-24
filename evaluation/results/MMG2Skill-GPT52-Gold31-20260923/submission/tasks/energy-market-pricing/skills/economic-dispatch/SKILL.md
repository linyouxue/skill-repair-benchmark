---
name: economic-dispatch
description: Formulate and solve DC-OPF energy + spinning-reserve co-optimization
  with standard capacity coupling using MATPOWER `gen`/`gencost`.
---

## Steps
1. Load and validate MATPOWER arrays and reserve inputs:
   ```python
   buses = np.array(data["bus"]); gens = np.array(data["gen"])
   branches = np.array(data["branch"]); gencost = np.array(data["gencost"])
   reserve_capacity = np.array(data["reserve_capacity"])
   reserve_requirement = float(data["reserve_requirement"])
   ```
   (Sanity-check shapes like `(bus, gen, branch, gencost)` and reserve requirement magnitude.)
2. Map each generator to its bus index using bus-number mapping:
   ```python
   gen_bus = [bus_num_to_idx[int(g[0])] for g in gens]
   ```
3. Define decision variables:
   - `Pg` in **per-unit** (so `Pg_MW = Pg*baseMVA`)
   - `Rg` in **MW**
   ```python
   Pg = cp.Variable(n_gen)
   Rg = cp.Variable(n_gen)
   ```
4. Add generator bounds and reserve constraints (standard capacity coupling):
   ```python
   constraints = []
   for i in range(n_gen):
       constraints += [Pg[i] >= gens[i,9]/baseMVA, Pg[i] <= gens[i,8]/baseMVA]
       constraints += [Rg[i] >= 0, Rg[i] <= reserve_capacity[i]]
       constraints += [Pg[i]*baseMVA + Rg[i] <= gens[i,8]]  # coupling
   constraints.append(cp.sum(Rg) >= reserve_requirement)
   ```
5. Build total production cost using MATPOWER polynomial `gencost` (MODEL=2), with `P` in MW:
   ```python
   cost = 0
   for i in range(n_gen):
       ncost = int(gencost[i,3])
       P = Pg[i]*baseMVA
       if ncost >= 3:
           c2,c1,c0 = gencost[i,4], gencost[i,5], gencost[i,6]
           cost += c2*cp.square(P) + c1*P + c0
       elif ncost == 2:
           c1,c0 = gencost[i,4], gencost[i,5]
           cost += c1*P + c0
       else:
           cost += gencost[i,4] if ncost >= 1 else 0
   ```
6. Solve with a robust conic/QP solver (CLARABEL works well for this formulation):
   ```python
   prob = cp.Problem(cp.Minimize(cost), constraints)
   prob.solve(solver=cp.CLARABEL)
   ```
## Expected Result
An optimal dispatch `Pg` and reserve schedule `Rg` meeting all limits and reserve requirement, with an objective value in $/hour.
