import yaml
import numpy as np


def load_params(path: str = '/root/system_params.yaml') -> dict:
    with open(path, 'r') as f:
        params = yaml.safe_load(f)
    params = dict(params)
    params['inertia_matrix'] = np.diag(np.array(params['inertia'], dtype=float))
    return params
