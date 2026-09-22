import yaml
import numpy as np


def load_system_params(path: str = "/root/system_params.yaml") -> dict:
    with open(path, "r") as f:
        params = yaml.safe_load(f)

    params = dict(params)
    params["inertia_matrix"] = np.diag(np.array(params["inertia"], dtype=float))
    params["inertia_inv"] = np.linalg.inv(params["inertia_matrix"])
    params["dt"] = 1.0 / float(params["sample_rate"])

    arm = float(params["arm_length"])
    spread = float(params.get("motor_spread_angle", np.pi / 4))
    params["arm_length_effective"] = arm * float(np.sin(spread))

    cT = float(params["thrust_coefficient"])
    rpm_max = float(params["rpm_max"])
    rpm_min = float(params["rpm_min"])
    params["T_max"] = 4.0 * cT * rpm_max**2
    params["T_min"] = 4.0 * cT * rpm_min**2

    return params
