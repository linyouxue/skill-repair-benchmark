import importlib.util
import sys
import argparse


import atheris


def _load_module_from_path(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_REGISTRY_MOD = _load_module_from_path(
    "minisgl_utils_registry", "python/minisgl/utils/registry.py"
)
_MISC_MOD = _load_module_from_path("minisgl_utils_misc", "python/minisgl/utils/misc.py")


def _consume_text(fdp: atheris.FuzzedDataProvider, max_len: int) -> str:
    try:
        return fdp.ConsumeUnicodeNoSurrogates(max_len)
    except AttributeError:
        return fdp.ConsumeBytes(max_len).decode("utf-8", errors="ignore")


def TestOneInput(data: bytes) -> None:
    data = data[:8192]
    fdp = atheris.FuzzedDataProvider(data)

    which = fdp.ConsumeIntInRange(0, 1)

    try:
        if which == 0:
            Registry = _REGISTRY_MOD.Registry
            reg = Registry("item")

            for _ in range(fdp.ConsumeIntInRange(0, 5)):
                name = _consume_text(fdp, 32)
                if not name:
                    continue
                try:
                    reg.register(name)(object())
                except KeyError:
                    pass

            key = _consume_text(fdp, 32)
            if fdp.ConsumeBool():
                reg.assert_supported(key)
            else:
                reg[key]
        else:
            a = fdp.ConsumeIntInRange(-2**31, 2**31 - 1)
            b = fdp.ConsumeIntInRange(-2**16, 2**16 - 1)
            if fdp.ConsumeBool():
                _MISC_MOD.div_even(a, b, allow_replicate=fdp.ConsumeBool())
            elif fdp.ConsumeBool():
                _MISC_MOD.div_ceil(a, b)
            elif fdp.ConsumeBool():
                _MISC_MOD.align_ceil(a, b)
            else:
                _MISC_MOD.align_down(a, b)
    except (
        argparse.ArgumentTypeError,
        AssertionError,
        ZeroDivisionError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
