#!/usr/bin/env python3
"""Atheris fuzz driver for minisgl.utils.misc integer helpers.

minisgl's package __init__ transitively imports huggingface_hub / torch /
flashinfer which are GPU-only and not available in this environment, so we
load the pure-Python leaf module (`utils/misc.py`) directly via importlib.
"""
import importlib.util
import os
import sys
import atheris

_MISC_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "python",
    "minisgl",
    "utils",
    "misc.py",
)

with atheris.instrument_imports():
    _spec = importlib.util.spec_from_file_location("minisgl_utils_misc", _MISC_PATH)
    misc = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(misc)

EXPECTED = (AssertionError, ZeroDivisionError, ValueError, OverflowError)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    a = fdp.ConsumeIntInRange(-(1 << 62), (1 << 62) - 1)
    b = fdp.ConsumeIntInRange(-(1 << 62), (1 << 62) - 1)
    flag = fdp.ConsumeBool()

    try:
        misc.div_even(a, b, allow_replicate=flag)
    except EXPECTED:
        pass

    try:
        misc.div_ceil(a, b)
    except EXPECTED:
        pass

    try:
        misc.align_ceil(a, b)
    except EXPECTED:
        pass

    try:
        misc.align_down(a, b)
    except EXPECTED:
        pass


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
