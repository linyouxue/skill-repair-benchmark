import os
import numpy as np
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


_GROUPS = [
    ('Position [m]',          [0, 1, 2],   ['x', 'y', 'z']),
    ('Velocity [m/s]',        [3, 4, 5],   ['vx', 'vy', 'vz']),
    ('Orientation [rad]',     [6, 7, 8],   [r'$\phi$', r'$\theta$', r'$\psi$']),
    ('Angular vel [rad/s]',   [9, 10, 11], ['p', 'q', 'r']),
    ('Acceleration [m/s²]',   [12, 13, 14], ['ax', 'ay', 'az']),
]


def _time_step_from_yaml():
    with open('/root/system_params.yaml') as f:
        p = yaml.safe_load(f)
    return 1.0 / p['sample_rate']


def plot_quadrotor(state, state_des, time_vec, save_dir):
    os.makedirs(save_dir, exist_ok=True)
    time_step = _time_step_from_yaml()

    fig1, ax1 = plt.subplots(5, 3, figsize=(16, 20))
    fig2, ax2 = plt.subplots(5, 3, figsize=(16, 20))
    fig3, ax3 = plt.subplots(5, 3, figsize=(16, 20))

    for gi, (title, rows, labels) in enumerate(_GROUPS):
        for ci, (row, lbl) in enumerate(zip(rows, labels)):
            actual = state[row]
            desired = state_des[row]
            err = actual - desired
            cum = time_step * np.cumsum(np.abs(err))

            ax1[gi, ci].plot(time_vec, desired, 'b-', label='desired')
            ax1[gi, ci].plot(time_vec, actual,  'r--', label='actual')
            ax1[gi, ci].set_title(f'{title} — {lbl}')
            ax1[gi, ci].set_xlabel('t [s]')
            ax1[gi, ci].legend()
            ax1[gi, ci].grid(True)

            ax2[gi, ci].plot(time_vec, err, 'k-')
            ax2[gi, ci].set_title(f'Error {title} — {lbl}')
            ax2[gi, ci].set_xlabel('t [s]')
            ax2[gi, ci].grid(True)

            ax3[gi, ci].plot(time_vec, cum, 'g-')
            ax3[gi, ci].set_title(f'Cumulative |error| {title} — {lbl}')
            ax3[gi, ci].set_xlabel('t [s]')
            ax3[gi, ci].grid(True)

    for fig in (fig1, fig2, fig3):
        fig.tight_layout()

    fig1.savefig(os.path.join(save_dir, 'desired_vs_actual.png'), dpi=80)
    fig2.savefig(os.path.join(save_dir, 'errors.png'), dpi=80)
    fig3.savefig(os.path.join(save_dir, 'cumulative_errors.png'), dpi=80)
    plt.close(fig1); plt.close(fig2); plt.close(fig3)
