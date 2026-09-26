from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import yaml


def plot_trajectories(
    state: np.ndarray,
    state_des: np.ndarray,
    time_vec: np.ndarray,
    save_dir: str | os.PathLike,
):
    state = np.asarray(state)
    state_des = np.asarray(state_des)
    time_vec = np.asarray(time_vec)

    with open('/root/system_params.yaml', 'r', encoding='utf-8') as f:
        params = yaml.safe_load(f)
    time_step = 1.0 / float(params['sample_rate'])

    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    labels = [
        ['x', 'y', 'z'],
        ['vx', 'vy', 'vz'],
        [r'$\phi$', r'$\theta$', r'$\psi$'],
        ['p', 'q', 'r'],
        ['ax', 'ay', 'az'],
    ]

    groups = [(0, 3), (3, 6), (6, 9), (9, 12), (12, 15)]

    def make_fig():
        return plt.subplots(5, 3, figsize=(16, 20), sharex=True)

    fig1, ax1 = make_fig()
    fig2, ax2 = make_fig()
    fig3, ax3 = make_fig()

    for gi, (a, b) in enumerate(groups):
        actual = state[a:b, :]
        desired = state_des[a:b, :]
        err = actual - desired
        cumulative = time_step * np.cumsum(np.abs(err), axis=1)

        for j in range(3):
            ax1[gi, j].plot(time_vec, desired[j, :], 'b', linewidth=1)
            ax1[gi, j].plot(time_vec, actual[j, :], 'r', linewidth=1)
            ax1[gi, j].set_ylabel(labels[gi][j])

            ax2[gi, j].plot(time_vec, err[j, :], 'k', linewidth=1)
            ax2[gi, j].set_ylabel(labels[gi][j])

            ax3[gi, j].plot(time_vec, cumulative[j, :], 'k', linewidth=1)
            ax3[gi, j].set_ylabel(labels[gi][j])

    ax1[0, 0].set_title('Desired (blue) vs Actual (red)')
    ax2[0, 0].set_title('Error (actual - desired)')
    ax3[0, 0].set_title('Cumulative |error|')

    for j in range(3):
        ax1[-1, j].set_xlabel('t [s]')
        ax2[-1, j].set_xlabel('t [s]')
        ax3[-1, j].set_xlabel('t [s]')

    fig1.tight_layout()
    fig2.tight_layout()
    fig3.tight_layout()

    fig1.savefig(save_dir / 'desired_vs_actual.png')
    fig2.savefig(save_dir / 'errors.png')
    fig3.savefig(save_dir / 'cumulative_errors.png')

    plt.close(fig1)
    plt.close(fig2)
    plt.close(fig3)
