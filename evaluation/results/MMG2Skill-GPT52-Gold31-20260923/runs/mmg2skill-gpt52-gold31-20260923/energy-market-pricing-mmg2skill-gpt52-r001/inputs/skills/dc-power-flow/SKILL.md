---
name: dc-power-flow
description: Build and use the DC power-flow model (B matrix, slack angle, line flows,
  and thermal limits) with correct MATPOWER bus-number mapping.
---

## Steps
1. Create a **bus-number → 0‑indexed row** mapping (bus numbers may be non-contiguous):
   ```python
   bus_num_to_idx = {int(bus[i,0]): i for i in range(n_bus)}
   ```
2. Build the nodal susceptance matrix **B** from in-service branches using `X = branch[:,3]`:
   ```python
   B = np.zeros((n_bus, n_bus))
   for br in branches:
       f = bus_num_to_idx[int(br[0])]
       t = bus_num_to_idx[int(br[1])]
       x = br[3]
       if x != 0:
           b = 1.0/x
           B[f,f] += b; B[t,t] += b
           B[f,t] -= b; B[t,f] -= b
   ```
3. Add a **slack bus** angle reference (MATPOWER bus type 3):
   ```python
   slack_idx = next(i for i in range(n_bus) if int(buses[i,1]) == 3)
   constraints.append(theta[slack_idx] == 0)
   ```
4. Enforce **nodal DC balance** (in per-unit, consistent with `Pg_pu` and `Pd/baseMVA`):
   \[
   Pg_i - Pd_i = B_{i,:}\,\theta
   \]
5. Compute branch flow (MW) for reporting:
   ```python
   b = 1.0/br[3]
   flow_MW = b*(theta[f]-theta[t]) * baseMVA
   ```
6. Enforce branch thermal limits (RATE_A is `branch[:,5]`) as linear constraints:
   ```python
   rate = br[5]
   flow = b*(theta[f]-theta[t]) * baseMVA
   constraints += [flow <= rate, flow >= -rate]
   ```
## Expected Result
A consistent DC network model where bus angles determine line flows, thermal limits can bind, and flows/loading can be computed in MW/%.
