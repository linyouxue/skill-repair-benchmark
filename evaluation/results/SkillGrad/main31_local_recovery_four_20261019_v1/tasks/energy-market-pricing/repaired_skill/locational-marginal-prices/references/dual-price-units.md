# Dual price units + sign: derive from the written constraint

Use this when extracting LMPs/MCPs from optimization duals, especially if your model mixes MW and per-unit.

## Core rule

A dual value has units of **$/unit-of-constraint-LHS**. To report $/MWh, you must:
1) write the exact constraint form, including sign and units,
2) map 1 unit of LHS to MW, then
3) apply the sign convention consistently.

## Recipe

### 1) Capture the constraint and its dual

```python
# Example: power balance at bus i (store the constraint objects)
con = balance_constraints[i]
dual = float(con.dual_value)
```

### 2) Branch on whether the constraint is in MW or per-unit

```python
baseMVA = float(baseMVA)

# Suppose your balance is: sum(Pg_MW) - Pd_MW == 0
balance_in_MW = True

if balance_in_MW:
    # dual is $/MW; common convention uses LMP = -dual
    lmp = -dual
else:
    # If balance is in pu, dual is $/pu.
    # 1 pu injection = baseMVA MW, so $/MW = ($/pu) / baseMVA.
    lmp = -dual / baseMVA
```

### 3) Verification: marginal-cost consistency check

Pick a bus that is not separated by congestion and identify a generator that is:
- online,
- not at a bound,
- setting the marginal energy price.

```python
def marginal_cost_quadratic(P_MW, c2, c1):
    return 2.0 * c2 * P_MW + c1

# Inputs from your solved dispatch and gencost parsing:
mc = marginal_cost_quadratic(P_MW=float(Pg_MW[g]), c2=float(c2[g]), c1=float(c1[g]))

# If generator g is marginal, LMP at its bus should be close.
assert abs(lmp_by_bus[gen_bus[g]] - mc) < 5.0, "LMP not consistent with marginal cost; re-check sign/units"
```

If the assertion fails:
- First re-check the written constraint direction/sign (equality vs moved-to-LHS).
- Then re-check MW vs per-unit conversion.
- Only after those are correct, consider degeneracy/non-unique duals (try another solver or add tiny regularization).
