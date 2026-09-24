---
name: locational-marginal-prices
description: Extract LMPs and reserve MCP from DC-OPF duals with correct sign/scaling,
  list binding lines (≥99% loading), and run the 20% thermal-limit counterfactual
  for line 64–1501.
---

## Steps
1. **Store references** to each nodal balance constraint so duals are available after solve:
   ```python
   balance_constraints = []
   for i in range(n_bus):
       pg_at_bus = cp.sum(cp.hstack([Pg[g] for g in range(n_gen) if gen_bus[g] == i])) if any(gen_bus[g]==i for g in range(n_gen)) else 0
       pd_pu = buses[i,2] / baseMVA
       con = (pg_at_bus - pd_pu == B[i,:] @ theta)
       balance_constraints.append(con)
       constraints.append(con)
   ```
2. Store the system reserve requirement constraint reference:
   ```python
   reserve_con = (cp.sum(Rg) >= reserve_requirement)  # Rg and requirement are MW
   constraints.append(reserve_con)
   ```
3. Solve (e.g., `solver=cp.CLARABEL`), then compute **LMPs** from balance duals with correct conversion:
   - For balance written as `generation_pu - load_pu == net_injection_pu`,
     \[
     \text{LMP}[\$/\text{MWh}] = -\frac{\lambda}{\text{baseMVA}}
     \]
   ```python
   lmp_by_bus = []
   for i in range(n_bus):
       lam = balance_constraints[i].dual_value
       lmp = 0.0 if lam is None else float(-lam / baseMVA)
       lmp_by_bus.append({"bus": int(buses[i,0]), "lmp_dollars_per_MWh": round(lmp, 2)})
   ```
4. Compute **reserve MCP** directly from the reserve constraint dual (already $/MW ≡ $/MWh for a 1‑hour product):
   ```python
   reserve_mcp = 0.0 if reserve_con.dual_value is None else float(reserve_con.dual_value)
   ```
5. Identify **binding/near-binding** lines using solved angles and RATE_A, with loading threshold ≥99%:
   ```python
   BINDING_THRESHOLD = 99.0
   binding_lines = []
   for br in branches:
       rate = br[5]
       if br[3] != 0 and rate > 0:
           f = bus_num_to_idx[int(br[0])]; t = bus_num_to_idx[int(br[1])]
           flow = (1.0/br[3]) * (theta.value[f]-theta.value[t]) * baseMVA
           if abs(flow)/rate*100 >= BINDING_THRESHOLD:
               binding_lines.append({"from": int(br[0]), "to": int(br[1]),
                                    "flow_MW": round(float(flow), 2),
                                    "limit_MW": round(float(rate), 2)})
   ```
6. Run the **counterfactual** by increasing the 64–1501 line’s RATE_A by 20% (match either direction), then re-solve:
   ```python
   for k in range(len(branches)):
       a,b = int(branches[k,0]), int(branches[k,1])
       if (a==64 and b==1501) or (a==1501 and b==64):
           branches[k,5] *= 1.20
           break
   ```
7. In the final comparison, set `congestion_relieved` based **only on the adjusted line** being binding in base but not binding in counterfactual (even if other lines become binding).
## Expected Result
Per-bus LMPs in realistic $/MWh magnitudes, a system reserve MCP, correct binding-line detection, and a consistent base vs. counterfactual comparison for relaxing line 64–1501.
