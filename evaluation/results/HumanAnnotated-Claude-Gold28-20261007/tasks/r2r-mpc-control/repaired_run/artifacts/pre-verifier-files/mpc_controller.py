#!/usr/bin/env python3
"""MPC controller for 6-section R2R web handling system."""

import json
import numpy as np
from r2r_simulator import R2RSimulator


def build_linearized_model(sim, x_ref, u_ref):
    """Build discrete-time linearized state-space model around (x_ref, u_ref).

    State:  x = [T1..T6, v1..v6]  (12)
    Input:  u = [u1..u6]          (6)
    """
    n = sim.num_sec
    EA, L, R, J, fb = sim.EA, sim.L, sim.R, sim.J, sim.fb
    dt = sim.dt

    T_ref = x_ref[:n]
    v_ref = x_ref[n:]

    A_c = np.zeros((2 * n, 2 * n))
    B_c = np.zeros((2 * n, n))

    # Tension dynamics rows (indices 0..n-1)
    for i in range(n):
        # ∂(dT_i)/∂T_i = -v_i / L
        A_c[i, i] = -v_ref[i] / L
        # ∂(dT_i)/∂v_i = EA/L - T_i/L
        A_c[i, n + i] = (EA - T_ref[i]) / L
        if i > 0:
            # ∂(dT_i)/∂T_{i-1} = v_{i-1}/L
            A_c[i, i - 1] = v_ref[i - 1] / L
            # ∂(dT_i)/∂v_{i-1} = -EA/L + T_{i-1}/L
            A_c[i, n + i - 1] = -(EA - T_ref[i - 1]) / L
        # i == 0: v_0, T_0 are constants => no dependency

    # Velocity dynamics rows (indices n..2n-1)
    for i in range(n):
        A_c[n + i, i] = -R**2 / J
        if i < n - 1:
            A_c[n + i, i + 1] = R**2 / J
        A_c[n + i, n + i] = -fb / J
        B_c[n + i, i] = R / J

    # Discretize via Euler (matches simulator's Euler integration)
    A_d = np.eye(2 * n) + dt * A_c
    B_d = dt * B_c
    return A_d, B_d


def finite_horizon_lqr_gain(A, B, Q, R, N):
    """Backward Riccati recursion. Returns first-step feedback gain K_0."""
    nx, nu = A.shape[0], B.shape[1]
    P = Q.copy()
    K0 = None
    for k in range(N - 1, -1, -1):
        K = np.linalg.solve(R + B.T @ P @ B, B.T @ P @ A)
        P = Q + A.T @ P @ (A - B @ K)
        if k == 0:
            K0 = K
    return K0, P


def main():
    sim = R2RSimulator("/root/system_config.json")
    n = sim.num_sec
    dt = sim.dt

    # Linearize around INITIAL reference operating point
    x_ref0, u_ref0 = sim.get_reference(0)
    A_d, B_d = build_linearized_model(sim, x_ref0, u_ref0)

    # Cost matrices
    T_ref_nom = x_ref0[:n]
    v_ref_nom = x_ref0[n:]
    q_T = 200.0 / T_ref_nom**2
    q_v = 1.0 / np.maximum(v_ref_nom, 1e-3)**2
    Q_diag = np.concatenate([q_T, q_v])
    Q = np.diag(Q_diag)
    R_diag = 0.05 * np.ones(n)
    R_cost = np.diag(R_diag)

    horizon_N = 15

    # MPC feedback gain (first step of finite-horizon LQR)
    K_mpc, _ = finite_horizon_lqr_gain(A_d, B_d, Q, R_cost, horizon_N)

    # Save controller parameters
    controller_params = {
        "horizon_N": int(horizon_N),
        "Q_diag": Q_diag.tolist(),
        "R_diag": R_diag.tolist(),
        "K_lqr": K_mpc.tolist(),
        "A_matrix": A_d.tolist(),
        "B_matrix": B_d.tolist(),
    }
    with open("/root/controller_params.json", "w") as f:
        json.dump(controller_params, f, indent=2)

    # Run closed-loop simulation
    np.random.seed(0)
    x = sim.reset()

    log = []
    sim_time = 6.0  # > 5 seconds
    n_steps = int(sim_time / dt)

    # Integral action for offset-free tracking of tensions
    u_I = np.zeros(n)
    gamma = 0.995
    c_I = 0.25

    for k in range(n_steps):
        x_ref, u_ref = sim.get_reference()
        T_meas = x[:n]
        T_ref = x_ref[:n]

        # MPC control deviation: delta_u = -K * (x - x_ref)
        delta_u = -K_mpc @ (x - x_ref)

        # Integral action on tension error
        u_I = gamma * u_I - c_I * dt * (T_meas - T_ref)
        u_I = np.clip(u_I, -2.0, 2.0)

        u = u_ref + delta_u + u_I

        log.append({
            "time": round(sim.get_time() + dt, 4),
            "tensions": x[:n].tolist(),
            "velocities": x[n:].tolist(),
            "control_inputs": u.tolist(),
            "references": x_ref.tolist(),
        })

        x = sim.step(u)

    with open("/root/control_log.json", "w") as f:
        json.dump({"phase": "control", "data": log}, f, indent=2)

    # Compute performance metrics
    data = log
    times = np.array([d["time"] for d in data])
    tensions = np.array([d["tensions"] for d in data])
    refs = np.array([d["references"] for d in data])
    T_refs = refs[:, :n]

    # Steady-state error: mean |T - T_ref| over last 1 second
    mask_ss = times >= (sim_time - 1.0)
    ss_err = float(np.mean(np.abs(tensions[mask_ss] - T_refs[mask_ss])))

    # Settling time (after step at t=0.5): time until mean absolute tracking error
    # stays below 2 N for the remainder of the simulation (matches the task's
    # steady-state error acceptance threshold).
    step_t = sim.step_time
    tol_band = 2.0
    settling_time = sim_time
    post_step_idx = np.where(times >= step_t)[0]
    for idx in post_step_idx:
        remaining_err = np.mean(np.abs(tensions[idx:] - T_refs[idx:]), axis=1)
        if np.all(remaining_err <= tol_band):
            settling_time = float(times[idx] - step_t)
            break

    max_tension = float(np.max(tensions))
    min_tension = float(np.min(tensions))

    metrics = {
        "steady_state_error": ss_err,
        "settling_time": settling_time,
        "max_tension": max_tension,
        "min_tension": min_tension,
    }
    with open("/root/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print("Controller parameters saved to controller_params.json")
    print("Control log saved to control_log.json")
    print(f"Metrics: {metrics}")


if __name__ == "__main__":
    main()
