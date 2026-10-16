"""Plot generation for a single command's trajectory."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def generate_plots(state, state_des, time_vec, save_dir, sample_rate):
    os.makedirs(save_dir, exist_ok=True)
    time_step = 1.0 / sample_rate

    groups = [
        ("Position [m]",         ["x", "y", "z"],                    slice(0, 3)),
        ("Velocity [m/s]",       ["vx", "vy", "vz"],                 slice(3, 6)),
        ("Orientation [rad]",    [r"$\phi$", r"$\theta$", r"$\psi$"], slice(6, 9)),
        ("Angular vel [rad/s]",  ["p", "q", "r"],                    slice(9, 12)),
        ("Accel [m/s^2]",        ["ax", "ay", "az"],                 slice(12, 15)),
    ]

    # Figure 1: desired vs actual
    fig, axes = plt.subplots(5, 3, figsize=(16, 20))
    for gi, (title, labels, sl) in enumerate(groups):
        for i in range(3):
            ax = axes[gi, i]
            ax.plot(time_vec, state_des[sl.start + i], "b-", label="desired")
            ax.plot(time_vec, state[sl.start + i],     "r-", label="actual", alpha=0.8)
            ax.set_title(f"{title}: {labels[i]}")
            ax.set_xlabel("time [s]")
            ax.grid(True)
            ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(save_dir, "desired_vs_actual.png"), dpi=100)
    plt.close(fig)

    # Figure 2: instantaneous error
    fig, axes = plt.subplots(5, 3, figsize=(16, 20))
    for gi, (title, labels, sl) in enumerate(groups):
        for i in range(3):
            ax = axes[gi, i]
            err = state[sl.start + i] - state_des[sl.start + i]
            ax.plot(time_vec, err, "k-")
            ax.set_title(f"Error {title}: {labels[i]}")
            ax.set_xlabel("time [s]")
            ax.grid(True)
    fig.tight_layout()
    fig.savefig(os.path.join(save_dir, "errors.png"), dpi=100)
    plt.close(fig)

    # Figure 3: cumulative absolute error
    fig, axes = plt.subplots(5, 3, figsize=(16, 20))
    for gi, (title, labels, sl) in enumerate(groups):
        for i in range(3):
            ax = axes[gi, i]
            err = state[sl.start + i] - state_des[sl.start + i]
            cum = time_step * np.cumsum(np.abs(err))
            ax.plot(time_vec, cum, "g-")
            ax.set_title(f"Cum |error| {title}: {labels[i]}")
            ax.set_xlabel("time [s]")
            ax.grid(True)
    fig.tight_layout()
    fig.savefig(os.path.join(save_dir, "cumulative_errors.png"), dpi=100)
    plt.close(fig)
