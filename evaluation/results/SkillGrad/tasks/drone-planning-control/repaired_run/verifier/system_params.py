from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np
import yaml


def load_params(path: str | Path = "/root/system_params.yaml") -> Dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text())
    data = dict(data)
    data["inertia_matrix"] = np.diag(np.array(data["inertia"], dtype=float))
    data["inv_inertia_matrix"] = np.linalg.inv(data["inertia_matrix"])
    data["dt"] = 1.0 / float(data["sample_rate"])
    return data
