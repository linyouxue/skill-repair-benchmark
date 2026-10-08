from __future__ import annotations

import os

import matplotlib.pyplot as plt
import numpy as np
import yaml


_GROUPS = [
    (slice(0, 3), ["x", "y", "z"], "position"),
    (slice(3, 6), ["vx", "vy", "vz"], "velocity"),
    (slice(6, 9), [r"$\phi$", r"$\theta$", r"$\psi$"], "orientation"),
    (slice(9, 12), ["p", "q", "r"], "angular_velocity"),
    (slice(12, 15), ["ax", "ay", "az"], "acceleration"),
]


def plot_quadrotor(state: np.ndarray, state_des: np.ndarray, time_vec: np.ndarray, save_dir: str):
    params = yaml.safe_load(open("/root/system_params.yaml"))
    dt = 1.0 / float(params["sample_rate"])

    os.makedirs(save_dir, exist_ok=True)

    state = np.asarray(state, dtype=float)
    state_des = np.asarray(state_des, dtype=float)
    time_vec = np.asarray(time_vec, dtype=float).reshape(-1)

    def _make_fig(title: str):
        fig, axes = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
        fig.suptitle(title)
        return fig, axes

    # Figure 1: desired vs actual
    fig1, axes1 = _make_fig("Desired vs Actual")
    for gi, (sl, labels, gname) in enumerate(_GROUPS):
        for ai in range(3):
            ax = axes1[gi, ai]
            ax.plot(time_vec, state_des[sl, :][ai, :], "b", linewidth=1)
            ax.plot(time_vec, state[sl, :][ai, :], "r", linewidth=1)
            ax.set_ylabel(f"{gname}:{labels[ai]}")
    for ax in axes1[-1, :]:
        ax.set_xlabel("t [s]")
    fig1.tight_layout(rect=[0, 0.03, 1, 0.97])
    fig1.savefig(os.path.join(save_dir, "desired_vs_actual.png"))
    plt.close(fig1)

    # Figure 2: instantaneous error
    fig2, axes2 = _make_fig("Errors (actual - desired)")
    err = state - state_des
    for gi, (sl, labels, gname) in enumerate(_GROUPS):
        for ai in range(3):
            ax = axes2[gi, ai]
            ax.plot(time_vec, err[sl, :][ai, :], "k", linewidth=1)
            ax.set_ylabel(f"{gname}:{labels[ai]}")
    for ax in axes2[-1, :]:
        ax.set_xlabel("t [s]")
    fig2.tight_layout(rect=[0, 0.03, 1, 0.97])
    fig2.savefig(os.path.join(save_dir, "errors.png"))
    plt.close(fig2)

    # Figure 3: cumulative absolute error
    fig3, axes3 = _make_fig("Cumulative absolute errors")
    cum = dt * np.cumsum(np.abs(err), axis=1)
    for gi, (sl, labels, gname) in enumerate(_GROUPS):
        for ai in range(3):
            ax = axes3[gi, ai]
            ax.plot(time_vec, cum[sl, :][ai, :], "k", linewidth=1)
            ax.set_ylabel(f"{gname}:{labels[ai]}")
    for ax in axes3[-1, :]:
        ax.set_xlabel("t [s]")
    fig3.tight_layout(rect=[0, 0.03, 1, 0.97])
    fig3.savefig(os.path.join(save_dir, "cumulative_errors.png"))
    plt.close(fig3)
