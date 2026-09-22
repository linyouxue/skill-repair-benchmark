import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from drone_params import load_system_params


_GROUPS = [
    (slice(0, 3), ["x", "y", "z"], "Position"),
    (slice(3, 6), ["vx", "vy", "vz"], "Velocity"),
    (slice(6, 9), [r"$\phi$", r"$\theta$", r"$\psi$"], "Orientation"),
    (slice(9, 12), ["p", "q", "r"], "Angular velocity"),
    (slice(12, 15), ["ax", "ay", "az"], "Acceleration"),
]


def plot_quadrotor(state: np.ndarray, state_des: np.ndarray, time_vec: np.ndarray, save_dir: str) -> None:
    os.makedirs(save_dir, exist_ok=True)

    params = load_system_params("/root/system_params.yaml")
    dt = 1.0 / float(params["sample_rate"])

    state = np.asarray(state, dtype=float)
    state_des = np.asarray(state_des, dtype=float)
    time_vec = np.asarray(time_vec, dtype=float)

    fig1, ax1 = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
    fig2, ax2 = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
    fig3, ax3 = plt.subplots(5, 3, figsize=(16, 20), sharex=True)

    for gi, (sl, labels, title) in enumerate(_GROUPS):
        actual = state[sl, :]
        desired = state_des[sl, :]
        err = actual - desired
        cum = dt * np.cumsum(np.abs(err), axis=1)

        for j in range(3):
            ax1[gi, j].plot(time_vec, desired[j, :], "b", linewidth=1)
            ax1[gi, j].plot(time_vec, actual[j, :], "r", linewidth=1)
            ax1[gi, j].set_ylabel(labels[j])

            ax2[gi, j].plot(time_vec, err[j, :], "k", linewidth=1)
            ax2[gi, j].set_ylabel(labels[j])

            ax3[gi, j].plot(time_vec, cum[j, :], "k", linewidth=1)
            ax3[gi, j].set_ylabel(labels[j])

        ax1[gi, 0].set_title(title)
        ax2[gi, 0].set_title(title)
        ax3[gi, 0].set_title(title)

    for ax in ax1[-1, :]:
        ax.set_xlabel("time [s]")
    for ax in ax2[-1, :]:
        ax.set_xlabel("time [s]")
    for ax in ax3[-1, :]:
        ax.set_xlabel("time [s]")

    fig1.tight_layout()
    fig2.tight_layout()
    fig3.tight_layout()

    fig1.savefig(os.path.join(save_dir, "desired_vs_actual.png"))
    fig2.savefig(os.path.join(save_dir, "errors.png"))
    fig3.savefig(os.path.join(save_dir, "cumulative_errors.png"))

    plt.close(fig1)
    plt.close(fig2)
    plt.close(fig3)
