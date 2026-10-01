import importlib.metadata as metadata
import sys

assert sys.version_info[:3] == (3, 10, 19), sys.version
expected = {
    "pytest": "8.4.1",
    "pytest-json-ctrf": "0.3.5",
    "numpy": "1.24.2",
    "torch": "2.1.2+cpu",
    "transformers": "4.39.3",
    "trl": "0.9.6",
    "rich": "11.2.0",
    "peft": "0.9.0",
    "accelerate": "0.29.2",
    "datasets": "2.18.0",
}
for name, wanted in expected.items():
    actual = metadata.version(name)
    assert actual == wanted, (name, actual, wanted)

import accelerate  # noqa: E402,F401
import datasets  # noqa: E402,F401
import numpy  # noqa: E402,F401
import peft  # noqa: E402,F401
import torch  # noqa: E402
import transformers  # noqa: E402,F401
import trl  # noqa: E402,F401

assert torch.__version__ == "2.1.2+cpu"
assert torch.cuda.is_available() is False
print("python=" + sys.version.split()[0])
print("package_versions=PASS")
print("imports=PASS")
print("torch_cpu=PASS")
