import os
import numpy as np
import matplotlib.pyplot as plt


def plot_quadrotor(state: np.ndarray, state_des: np.ndarray, time_vec: np.ndarray, save_dir: str):
    os.makedirs(save_dir, exist_ok=True)

    state = np.array(state, dtype=float)
    state_des = np.array(state_des, dtype=float)
    t = np.array(time_vec, dtype=float)

    groups = [
        ('pos', ['x', 'y', 'z'], slice(0, 3)),
        ('vel', ['vx', 'vy', 'vz'], slice(3, 6)),
        ('rot', [r'$\phi$', r'$\theta$', r'$\psi$'], slice(6, 9)),
        ('omega', ['p', 'q', 'r'], slice(9, 12)),
        ('acc', ['ax', 'ay', 'az'], slice(12, 15)),
    ]

    def _grid_fig(title):
        fig, axes = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
        fig.suptitle(title)
        return fig, axes

    fig1, axes1 = _grid_fig('Desired vs Actual')
    for i, (_name, labels, sl) in enumerate(groups):
        for j in range(3):
            ax = axes1[i, j]
            ax.plot(t, state_des[sl, :][j, :], 'b', linewidth=1)
            ax.plot(t, state[sl, :][j, :], 'r', linewidth=1)
            ax.set_ylabel(labels[j])
            if i == 4:
                ax.set_xlabel('t [s]')
    fig1.tight_layout(rect=[0, 0, 1, 0.97])
    fig1.savefig(os.path.join(save_dir, 'desired_vs_actual.png'))
    plt.close(fig1)

    fig2, axes2 = _grid_fig('Errors (actual - desired)')
    err = state - state_des
    for i, (_name, labels, sl) in enumerate(groups):
        for j in range(3):
            ax = axes2[i, j]
            ax.plot(t, err[sl, :][j, :], 'k', linewidth=1)
            ax.set_ylabel(labels[j])
            if i == 4:
                ax.set_xlabel('t [s]')
    fig2.tight_layout(rect=[0, 0, 1, 0.97])
    fig2.savefig(os.path.join(save_dir, 'errors.png'))
    plt.close(fig2)

    fig3, axes3 = _grid_fig('Cumulative absolute errors')
    dt = float(t[1] - t[0]) if len(t) > 1 else 0.0
    cum = dt * np.cumsum(np.abs(err), axis=1)
    for i, (_name, labels, sl) in enumerate(groups):
        for j in range(3):
            ax = axes3[i, j]
            ax.plot(t, cum[sl, :][j, :], 'g', linewidth=1)
            ax.set_ylabel(labels[j])
            if i == 4:
                ax.set_xlabel('t [s]')
    fig3.tight_layout(rect=[0, 0, 1, 0.97])
    fig3.savefig(os.path.join(save_dir, 'cumulative_errors.png'))
    plt.close(fig3)
