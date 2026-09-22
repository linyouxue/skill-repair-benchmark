#!/usr/bin/env python3
import importlib.util
import os
import sys

import atheris

REPO_ROOT = os.path.dirname(__file__)


def _load_module_from_path(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MISC = _load_module_from_path(
    "_minisgl_utils_misc",
    os.path.join(REPO_ROOT, "python", "minisgl", "utils", "misc.py"),
)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    a = fdp.ConsumeInt(8)
    b = fdp.ConsumeInt(8)
    allow_repl = fdp.ConsumeBool()

    try:
        _MISC.div_even(a, b if b != 0 else 0, allow_replicate=allow_repl)
    except (AssertionError, ZeroDivisionError):
        pass

    try:
        _MISC.div_ceil(a, b)
        _MISC.align_ceil(a, b)
        _MISC.align_down(a, b)
    except ZeroDivisionError:
        pass

    # call_if_main returns decorators; ensure returned callables can be invoked.
    name = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 16))
    discard = None if fdp.ConsumeBool() else fdp.ConsumeBool()

    deco = _MISC.call_if_main(name=name, discard=discard)

    def _f():
        return True

    wrapped = deco(_f)
    if callable(wrapped):
        wrapped()


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
