import numpy as np


def build_prop_matrix(params):
    d  = params['arm_length']
    cT = params['thrust_coefficient']
    cQ = params['moment_scale']
    # X-frame allocation from [F, Mx, My, Mz] to rpm^2 for motors 1..4
    return np.array([
        [ cT,      cT,      cT,      cT     ],
        [ 0.0,    d*cT,     0.0,   -d*cT    ],
        [-d*cT,   0.0,     d*cT,    0.0     ],
        [-cQ,     cQ,     -cQ,      cQ      ],
    ])


def motor_model(F_desired, M_desired, rpm_current, params):
    """
    Return (F_actual, M_actual, rpm_dot).
    F_desired: scalar total thrust; M_desired: (3,) moment vector; rpm_current: (4,)
    """
    P = build_prop_matrix(params)
    b = np.array([F_desired, M_desired[0], M_desired[1], M_desired[2]])
    rpm_sq_des = np.linalg.solve(P, b)
    rpm_sq_des = np.clip(rpm_sq_des, 0.0, None)
    rpm_des = np.sqrt(rpm_sq_des)
    rpm_des = np.clip(rpm_des, params['rpm_min'], params['rpm_max'])

    km = params['motor_constant']
    rpm_dot = km * (rpm_des - rpm_current)

    rpm_sq_actual = rpm_current ** 2
    wrench = P @ rpm_sq_actual
    F_actual = wrench[0]
    M_actual = wrench[1:]
    return F_actual, M_actual, rpm_dot
