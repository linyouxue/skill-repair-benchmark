from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from params import SystemParams


def plot_quadrotor(state: np.ndarray, state_des: np.ndarray, time_vec: np.ndarray, save_dir: str, params: SystemParams) -> None:
    os.makedirs(save_dir, exist_ok=True)

    time_step = 1.0 / params.sample_rate

    groups = [
        (slice(0, 3), ["x", "y", "z"], "Position"),
        (slice(3, 6), ["vx", "vy", "vz"], "Velocity"),
        (slice(6, 9), [r"$\phi$", r"$\theta$", r"$\psi$"], "Orientation"),
        (slice(9, 12), ["p", "q", "r"], "Angular velocity"),
        (slice(12, 15), ["ax", "ay", "az"], "Acceleration"),
    ]

    def _subplot_grid(title: str):
        fig, axs = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
        fig.suptitle(title)
        return fig, axs

    fig1, axs1 = _subplot_grid("Desired vs Actual")
    fig2, axs2 = _subplot_grid("Errors (actual - desired)")
    fig3, axs3 = _subplot_grid("Cumulative absolute error")

    for gi, (sl, labels, group_title) in enumerate(groups):
        for ai in range(3):
            a = state[sl, :][ai, :]
            d = state_des[sl, :][ai, :]
            err = a - d
            cum = time_step * np.cumsum(np.abs(err))

            axs1[gi, ai].plot(time_vec, d, color="tab:blue", linewidth=1)
            axs1[gi, ai].plot(time_vec, a, color="tab:red", linewidth=1)
            axs1[gi, ai].set_ylabel(group_title if ai == 0 else "")
            axs1[gi, ai].set_title(labels[ai])

            axs2[gi, ai].plot(time_vec, err, color="tab:purple", linewidth=1)
            axs2[gi, ai].set_ylabel(group_title if ai == 0 else "")
            axs2[gi, ai].set_title(labels[ai])

            axs3[gi, ai].plot(time_vec, cum, color="tab:green", linewidth=1)
            axs3[gi, ai].set_ylabel(group_title if ai == 0 else "")
            axs3[gi, ai].set_title(labels[ai])

    for ax in axs1[-1, :]:
        ax.set_xlabel("t [s]")
    for ax in axs2[-1, :]:
        ax.set_xlabel("t [s]")
    for ax in axs3[-1, :]:
        ax.set_xlabel("t [s]")

    fig1.tight_layout()
    fig2.tight_layout()
    fig3.tight_layout()

    fig1.savefig(os.path.join(save_dir, "desired_vs_actual.png"), dpi=150)
    fig2.savefig(os.path.join(save_dir, "errors.png"), dpi=150)
    fig3.savefig(os.path.join(save_dir, "cumulative_errors.png"), dpi=150)

    plt.close(fig1)
    plt.close(fig2)
    plt.close(fig3)
