from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from system_params import load_params


def plot_trajectories(state: np.ndarray, state_des: np.ndarray, time_vec: np.ndarray, save_dir: str | Path) -> None:
    params = load_params("/root/system_params.yaml")
    time_step = 1.0 / float(params["sample_rate"])

    state = np.asarray(state, dtype=float)
    state_des = np.asarray(state_des, dtype=float)
    time_vec = np.asarray(time_vec, dtype=float)

    groups = [
        ("pos", ["x", "y", "z"], slice(0, 3)),
        ("vel", ["vx", "vy", "vz"], slice(3, 6)),
        ("rot", [r"$\phi$", r"$\theta$", r"$\psi$"], slice(6, 9)),
        ("omega", ["p", "q", "r"], slice(9, 12)),
        ("acc", ["ax", "ay", "az"], slice(12, 15)),
    ]

    save_dir = Path(save_dir)
    os.makedirs(save_dir, exist_ok=True)

    fig1, ax1 = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
    fig2, ax2 = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
    fig3, ax3 = plt.subplots(5, 3, figsize=(16, 20), sharex=True)

    for gi, (gname, labels, sl) in enumerate(groups):
        actual = state[sl, :]
        desired = state_des[sl, :]
        err = actual - desired
        cum = time_step * np.cumsum(np.abs(err), axis=1)

        for j in range(3):
            ax1[gi, j].plot(time_vec, desired[j, :], "b", linewidth=1)
            ax1[gi, j].plot(time_vec, actual[j, :], "r", linewidth=1)
            ax1[gi, j].set_ylabel(labels[j])
            ax1[gi, j].grid(True, alpha=0.3)

            ax2[gi, j].plot(time_vec, err[j, :], "k", linewidth=1)
            ax2[gi, j].set_ylabel(labels[j])
            ax2[gi, j].grid(True, alpha=0.3)

            ax3[gi, j].plot(time_vec, cum[j, :], "k", linewidth=1)
            ax3[gi, j].set_ylabel(labels[j])
            ax3[gi, j].grid(True, alpha=0.3)

    ax1[0, 0].set_title("Desired (blue) vs Actual (red)")
    ax2[0, 0].set_title("Error (actual - desired)")
    ax3[0, 0].set_title("Cumulative abs error")

    ax1[-1, 0].set_xlabel("t [s]")
    ax2[-1, 0].set_xlabel("t [s]")
    ax3[-1, 0].set_xlabel("t [s]")

    fig1.tight_layout()
    fig2.tight_layout()
    fig3.tight_layout()

    fig1.savefig(save_dir / "desired_vs_actual.png")
    fig2.savefig(save_dir / "errors.png")
    fig3.savefig(save_dir / "cumulative_errors.png")

    plt.close(fig1)
    plt.close(fig2)
    plt.close(fig3)
