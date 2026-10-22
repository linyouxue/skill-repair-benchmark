"""Produce the three required figures for a simulation run."""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import yaml


_GROUPS = [
    ('Position [m]',          slice(0, 3),  ['x', 'y', 'z']),
    ('Velocity [m/s]',        slice(3, 6),  ['vx', 'vy', 'vz']),
    ('Orientation [rad]',     slice(6, 9),  [r'$\phi$', r'$\theta$', r'$\psi$']),
    ('Ang. velocity [rad/s]', slice(9, 12), ['p', 'q', 'r']),
    ('Acceleration [m/s²]',   slice(12, 15),['ax', 'ay', 'az']),
]


def _grid(suptitle):
    fig, axes = plt.subplots(5, 3, figsize=(16, 20))
    fig.suptitle(suptitle)
    return fig, axes


def plot_results(state, state_des, time_vec, save_dir, params_path='/root/system_params.yaml'):
    with open(params_path) as f:
        p = yaml.safe_load(f)
    time_step = 1.0 / p['sample_rate']

    os.makedirs(save_dir, exist_ok=True)

    fig1, ax1 = _grid('Desired vs Actual')
    fig2, ax2 = _grid('Instantaneous Error (actual - desired)')
    fig3, ax3 = _grid('Cumulative Absolute Error')

    for row, (title, sl, labels) in enumerate(_GROUPS):
        actual = state[sl, :]
        desired = state_des[sl, :]
        err = actual - desired
        cum = time_step * np.cumsum(np.abs(err), axis=1)

        for col in range(3):
            ax1[row, col].plot(time_vec, desired[col], 'b', label='desired')
            ax1[row, col].plot(time_vec, actual[col], 'r', label='actual')
            ax1[row, col].set_title(f'{title} - {labels[col]}')
            ax1[row, col].set_xlabel('t [s]')
            ax1[row, col].grid(True)
            ax1[row, col].legend(loc='best', fontsize=8)

            ax2[row, col].plot(time_vec, err[col], 'k')
            ax2[row, col].set_title(f'{title} err - {labels[col]}')
            ax2[row, col].set_xlabel('t [s]')
            ax2[row, col].grid(True)

            ax3[row, col].plot(time_vec, cum[col], 'g')
            ax3[row, col].set_title(f'{title} cum|err| - {labels[col]}')
            ax3[row, col].set_xlabel('t [s]')
            ax3[row, col].grid(True)

    for fig in (fig1, fig2, fig3):
        fig.tight_layout(rect=[0, 0, 1, 0.98])

    fig1.savefig(os.path.join(save_dir, 'desired_vs_actual.png'), dpi=90)
    fig2.savefig(os.path.join(save_dir, 'errors.png'), dpi=90)
    fig3.savefig(os.path.join(save_dir, 'cumulative_errors.png'), dpi=90)
    plt.close(fig1); plt.close(fig2); plt.close(fig3)
