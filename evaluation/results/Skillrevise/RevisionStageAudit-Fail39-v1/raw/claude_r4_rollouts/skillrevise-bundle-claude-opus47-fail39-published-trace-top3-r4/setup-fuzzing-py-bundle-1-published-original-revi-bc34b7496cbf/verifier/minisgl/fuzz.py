"""Atheris fuzz driver for minisgl.

minisgl's top-level package transitively imports torch, flashinfer, and other
GPU-only wheels, so we load the pure-Python utility modules directly from the
source tree. This keeps the environment lightweight and still exercises
non-trivial branching inside the library.

Targets:
  * minisgl.utils.misc.div_even / div_ceil / align_ceil / align_down
  * minisgl.utils.registry.Registry
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import atheris

_PKG_ROOT = Path(__file__).resolve().parent / "python" / "minisgl"


def _load(mod_name: str, rel_path: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(mod_name, _PKG_ROOT / rel_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load without triggering the minisgl package __init__ (which pulls torch).
with atheris.instrument_imports():
    _misc = _load("minisgl_utils_misc", "utils/misc.py")
    _registry = _load("minisgl_utils_registry", "utils/registry.py")


div_even = _misc.div_even
div_ceil = _misc.div_ceil
align_ceil = _misc.align_ceil
align_down = _misc.align_down
Registry = _registry.Registry


from argparse import ArgumentTypeError

_EXPECTED = (
    AssertionError,
    ZeroDivisionError,
    ValueError,
    TypeError,
    KeyError,
    ArgumentTypeError,
)


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    choice = fdp.ConsumeIntInRange(0, 4)
    a = fdp.ConsumeIntInRange(-(1 << 20), 1 << 20)
    b = fdp.ConsumeIntInRange(-(1 << 20), 1 << 20)
    flag = fdp.ConsumeBool()

    try:
        if choice == 0:
            div_even(a, b, allow_replicate=flag)
        elif choice == 1:
            div_ceil(a, b)
        elif choice == 2:
            align_ceil(a, b)
        elif choice == 3:
            align_down(a, b)
        else:
            reg: Registry = Registry("fuzz")
            name1 = fdp.ConsumeUnicodeNoSurrogates(32)
            name2 = fdp.ConsumeUnicodeNoSurrogates(32)
            reg.register(name1)(lambda: a)
            # Hit the duplicate-register branch when name2 == name1.
            if name2 and name2 != name1:
                reg.register(name2)(lambda: b)
            # Exercise the __getitem__ miss/hit branches and assert_supported.
            _ = reg[name1]
            reg.assert_supported([name1, name2])
            reg.supported_names()
    except _EXPECTED:
        pass


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
