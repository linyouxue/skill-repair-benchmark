#!/usr/bin/env python3
import os
import sys
import tokenize

import atheris

REPO_ROOT = os.path.dirname(__file__)

# Support running from a repo checkout without installation.
for rel in ("src",):
    p = os.path.join(REPO_ROOT, rel)
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

with atheris.instrument_imports():
    import black
    import black.parsing
    from black import ASTSafetyError, InvalidInput


def _limited_src(fdp: atheris.FuzzedDataProvider, max_chars: int) -> str:
    n = fdp.ConsumeIntInRange(0, max_chars)
    return fdp.ConsumeUnicodeNoSurrogates(n)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    # Avoid pathological memory/time blowups.
    if len(data) > 1_000_000:
        return

    src = _limited_src(fdp, 8_000)

    mode = black.FileMode(
        line_length=fdp.ConsumeIntInRange(1, 200),
        string_normalization=fdp.ConsumeBool(),
        preview=fdp.ConsumeBool(),
        is_pyi=fdp.ConsumeBool(),
        magic_trailing_comma=fdp.ConsumeBool(),
    )

    # Exercise parser boundaries directly.
    try:
        black.parsing.lib2to3_parse(src)
        black.parsing.parse_ast(src)
    except (InvalidInput, SyntaxError, IndentationError, tokenize.TokenError, ValueError):
        pass

    try:
        out = black.format_str(src, mode=mode)
    except (InvalidInput, SyntaxError, IndentationError, tokenize.TokenError, ValueError):
        return

    # Correctness oracles when formatting succeeds.
    # ASTSafetyError is a known/expected outcome when AST parsing fails.
    try:
        black.assert_equivalent(src, out)
        black.assert_stable(src, out, mode=mode)
    except ASTSafetyError:
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
