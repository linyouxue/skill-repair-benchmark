from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml


def plot_results(state: np.ndarray, state_des: np.ndarray, time_vec: np.ndarray, save_dir: str) -> None:
    params = yaml.safe_load(Path("/root/system_params.yaml").read_text())
    sample_rate = float(params["sample_rate"])
    dt = 1.0 / sample_rate

    os.makedirs(save_dir, exist_ok=True)

    groups = [
        ("pos", ["x", "y", "z"], slice(0, 3)),
        ("vel", ["vx", "vy", "vz"], slice(3, 6)),
        ("rot", ["φ", "θ", "ψ"], slice(6, 9)),
        ("omega", ["p", "q", "r"], slice(9, 12)),
        ("acc", ["ax", "ay", "az"], slice(12, 15)),
    ]

    # Figure 1: desired vs actual
    fig1, axes = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
    for gi, (gname, labels, sl) in enumerate(groups):
        for ai in range(3):
            ax = axes[gi, ai]
            ax.plot(time_vec, state_des[sl, :][ai, :], color="tab:blue", linewidth=1.5)
            ax.plot(time_vec, state[sl, :][ai, :], color="tab:red", linewidth=1.0)
            ax.set_title(f"{gname}:{labels[ai]}")
            ax.grid(True, alpha=0.3)
    fig1.tight_layout()
    fig1.savefig(os.path.join(save_dir, "desired_vs_actual.png"))
    plt.close(fig1)

    # Figure 2: instantaneous errors
    err = state - state_des
    fig2, axes = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
    for gi, (gname, labels, sl) in enumerate(groups):
        for ai in range(3):
            ax = axes[gi, ai]
            ax.plot(time_vec, err[sl, :][ai, :], color="tab:purple", linewidth=1.2)
            ax.set_title(f"err {gname}:{labels[ai]}")
            ax.grid(True, alpha=0.3)
    fig2.tight_layout()
    fig2.savefig(os.path.join(save_dir, "errors.png"))
    plt.close(fig2)

    # Figure 3: cumulative absolute errors
    cum = dt * np.cumsum(np.abs(err), axis=1)
    fig3, axes = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
    for gi, (gname, labels, sl) in enumerate(groups):
        for ai in range(3):
            ax = axes[gi, ai]
            ax.plot(time_vec, cum[sl, :][ai, :], color="tab:green", linewidth=1.2)
            ax.set_title(f"cum |err| {gname}:{labels[ai]}")
            ax.grid(True, alpha=0.3)
    fig3.tight_layout()
    fig3.savefig(os.path.join(save_dir, "cumulative_errors.png"))
    plt.close(fig3)
