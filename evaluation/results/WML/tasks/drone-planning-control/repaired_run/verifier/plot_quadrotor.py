from __future__ import annotations

import os
from typing import Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import yaml


def _load_dt(params_path: str = "/root/system_params.yaml") -> float:
    with open(params_path, "r") as f:
        params = yaml.safe_load(f)
    sr = float(params["sample_rate"])
    return 1.0 / sr


def plot_quadrotor(state: np.ndarray, state_des: np.ndarray, time_vec: np.ndarray, *, save_dir: str):
    """Save trajectory, error, and cumulative absolute error figures."""
    os.makedirs(save_dir, exist_ok=True)

    dt = _load_dt()

    state = np.asarray(state, dtype=float)
    state_des = np.asarray(state_des, dtype=float)
    t = np.asarray(time_vec, dtype=float)

    groups = [
        (slice(0, 3), ["x", "y", "z"], "pos"),
        (slice(3, 6), ["vx", "vy", "vz"], "vel"),
        (slice(6, 9), [r"$\phi$", r"$\theta$", r"$\psi$"], "rot"),
        (slice(9, 12), ["p", "q", "r"], "omega"),
        (slice(12, 15), ["ax", "ay", "az"], "acc"),
    ]

    def _make_fig(title: str) -> Tuple[plt.Figure, np.ndarray]:
        fig, axs = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
        fig.suptitle(title)
        return fig, axs

    # Figure 1: desired vs actual
    fig1, axs1 = _make_fig("Desired vs Actual")
    for gi, (sl, labels, gname) in enumerate(groups):
        for ai in range(3):
            ax = axs1[gi, ai]
            ax.plot(t, state_des[sl, :][ai, :], "b", linewidth=1)
            ax.plot(t, state[sl, :][ai, :], "r", linewidth=1)
            ax.set_ylabel(f"{gname}:{labels[ai]}")
    axs1[-1, 1].set_xlabel("time [s]")
    fig1.tight_layout(rect=[0, 0, 1, 0.97])
    fig1.savefig(os.path.join(save_dir, "desired_vs_actual.png"))
    plt.close(fig1)

    # Figure 2: instantaneous errors
    err = state - state_des
    fig2, axs2 = _make_fig("Errors (actual - desired)")
    for gi, (sl, labels, gname) in enumerate(groups):
        for ai in range(3):
            ax = axs2[gi, ai]
            ax.plot(t, err[sl, :][ai, :], "k", linewidth=1)
            ax.set_ylabel(f"{gname}:{labels[ai]}")
    axs2[-1, 1].set_xlabel("time [s]")
    fig2.tight_layout(rect=[0, 0, 1, 0.97])
    fig2.savefig(os.path.join(save_dir, "errors.png"))
    plt.close(fig2)

    # Figure 3: cumulative absolute errors
    cum = dt * np.cumsum(np.abs(err), axis=1)
    fig3, axs3 = _make_fig("Cumulative absolute errors")
    for gi, (sl, labels, gname) in enumerate(groups):
        for ai in range(3):
            ax = axs3[gi, ai]
            ax.plot(t, cum[sl, :][ai, :], "g", linewidth=1)
            ax.set_ylabel(f"{gname}:{labels[ai]}")
    axs3[-1, 1].set_xlabel("time [s]")
    fig3.tight_layout(rect=[0, 0, 1, 0.97])
    fig3.savefig(os.path.join(save_dir, "cumulative_errors.png"))
    plt.close(fig3)
