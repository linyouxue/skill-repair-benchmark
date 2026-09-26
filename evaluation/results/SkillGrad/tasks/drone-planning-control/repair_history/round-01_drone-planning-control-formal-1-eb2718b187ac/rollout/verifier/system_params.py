from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


def load_params(path: str | Path = "/root/system_params.yaml") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        params = yaml.safe_load(f)
    return params
