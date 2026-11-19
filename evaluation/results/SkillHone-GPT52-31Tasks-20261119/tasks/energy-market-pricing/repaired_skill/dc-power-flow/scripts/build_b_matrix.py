#!/usr/bin/env python3
"""Build susceptance matrices for DC power flow analysis.

This helper follows MATPOWER's DC formulation (`makeBdc`):
- Uses bus-number→index mapping (bus numbers may be non-contiguous).
- Includes transformer tap ratios (TAP, column 8). MATPOWER uses TAP=0 → 1.0.
- Includes phase shifter angles (SHIFT, column 9) in line flow calculations.
- Skips out-of-service branches (BR_STATUS, column 10 == 0).

Returned branch susceptances correspond to the effective series term:
    b_eff = (1 / x) / tap
and line flows are:
    Pf = b_eff * (theta_f - theta_t - shift_rad) * baseMVA

Note:
    Some formulations use a 1/tap^2 term on the diagonal for transformer models.
    MATPOWER's `makeBdc` uses b/tap in both diagonal and off-diagonal terms.
    Match the conventions of your dataset/toolchain.
"""

from __future__ import annotations

import math

import numpy as np


def _branch_status(br) -> int:
    """Return MATPOWER BR_STATUS (1=in service). Assume 1 if missing."""

    return int(br[10]) if len(br) > 10 else 1


def _branch_tap(br) -> float:
    """Return MATPOWER BR_TAP (tap=0 means 1.0)."""

    tap = float(br[8]) if len(br) > 8 else 0.0
    return 1.0 if tap == 0.0 else tap


def _branch_shift_rad(br) -> float:
    """Return MATPOWER SHIFT in radians (degrees in column 9)."""

    shift_deg = float(br[9]) if len(br) > 9 else 0.0
    return shift_deg * math.pi / 180.0


def build_susceptance_matrix(branches, buses):
    """Build the bus susceptance matrix from MATPOWER branch data.

    Args:
        branches: Array-like of branch rows (MATPOWER format)
                  Each row: [from_bus, to_bus, r, x, b, rateA, ..., tap, shift, status]
        buses: Array-like of bus rows (MATPOWER format). Used only for bus mapping.

    Returns:
        B: (n_bus x n_bus) bus susceptance matrix (per-unit)
        branch_susceptances: list[float], effective b_eff=(1/x)/tap per branch (per-unit)
        bus_num_to_idx: dict[int,int], mapping from bus number to 0-indexed position

    Important:
        This function does *not* return the phase-shift injection vector used in
        MATPOWER's DC model (Pbusinj). If you need phase shifters for nodal balance,
        compute them separately (see `dc-power-flow` skill).
    """

    n_bus = len(buses)

    # Create bus number to index mapping (handles non-contiguous bus numbering)
    bus_num_to_idx = {int(buses[i, 0]): i for i in range(n_bus)}

    B = np.zeros((n_bus, n_bus), dtype=float)
    branch_susceptances: list[float] = []

    for br in branches:
        # Maintain one susceptance per input branch row
        if _branch_status(br) == 0:
            branch_susceptances.append(0.0)
            continue

        f = bus_num_to_idx[int(br[0])]
        t = bus_num_to_idx[int(br[1])]
        x = float(br[3])
        tap = _branch_tap(br)

        b = (1.0 / x) / tap if x != 0.0 else 0.0
        branch_susceptances.append(b)

        if b == 0.0:
            continue

        # Diagonal: positive (sum of incident susceptances)
        B[f, f] += b
        B[t, t] += b
        # Off-diagonal: negative
        B[f, t] -= b
        B[t, f] -= b

    return B, branch_susceptances, bus_num_to_idx


def calculate_line_flows(branches, branch_susceptances, theta, baseMVA, bus_num_to_idx):
    """Calculate DC power flows and loading percentages on all branches.

    Args:
        branches: Array-like of branch rows
        branch_susceptances: list/array of effective b per branch from build_susceptance_matrix
        theta: bus voltage angles (radians), indexed by bus_num_to_idx mapping
        baseMVA: base power for per-unit conversion
        bus_num_to_idx: mapping from bus numbers to 0-indexed positions

    Returns:
        List[dict] with from, to, flow_MW, limit_MW, loading_pct
    """

    line_flows = []

    for idx, br in enumerate(branches):
        if _branch_status(br) == 0:
            # Keep one output row per input branch for easy indexing.
            limit_MW = float(br[5]) if len(br) > 5 else 0.0
            line_flows.append(
                {
                    "from": int(br[0]),
                    "to": int(br[1]),
                    "flow_MW": 0.0,
                    "limit_MW": limit_MW,
                    "loading_pct": 0.0,
                }
            )
            continue

        f = bus_num_to_idx[int(br[0])]
        t = bus_num_to_idx[int(br[1])]
        b = float(branch_susceptances[idx])

        shift_rad = _branch_shift_rad(br)
        flow_MW = b * (float(theta[f]) - float(theta[t]) - shift_rad) * float(baseMVA)

        limit_MW = float(br[5])  # RATE_A
        loading_pct = abs(flow_MW) / limit_MW * 100.0 if limit_MW > 0 else 0.0

        line_flows.append(
            {
                "from": int(br[0]),
                "to": int(br[1]),
                "flow_MW": flow_MW,
                "limit_MW": limit_MW,
                "loading_pct": loading_pct,
            }
        )

    return line_flows


if __name__ == "__main__":
    # Example usage: build a B matrix and report basic properties.
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: build_b_matrix.py <network.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    buses = np.array(data["bus"], dtype=float)
    branches = np.array(data["branch"], dtype=float)

    B, susceptances, bus_num_to_idx = build_susceptance_matrix(branches, buses)

    print(f"Built {B.shape[0]}x{B.shape[1]} susceptance matrix")
    print(f"Non-zero elements: {np.count_nonzero(B)}")
    print(f"Matrix is symmetric: {np.allclose(B, B.T)}")
