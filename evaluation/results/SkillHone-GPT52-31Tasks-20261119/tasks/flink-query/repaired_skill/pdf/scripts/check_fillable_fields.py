import sys

# Script for Claude to run to determine whether a PDF has fillable form fields.
# See forms.md.


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_fillable_fields.py [input.pdf]", file=sys.stderr)
        return 2

    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as e:
        print(
            "ERROR: Python package `pypdf` is required for fillable-field detection, but it is not available.\n"
            "If you cannot install packages in this environment, treat the PDF as non-fillable and follow the\n"
            "\"Non-fillable fields\" workflow in forms.md.\n\n"
            f"Import error: {e}",
            file=sys.stderr,
        )
        return 2

    reader = PdfReader(sys.argv[1])
    if reader.get_fields():
        print("This PDF has fillable form fields")
    else:
        print("This PDF does not have fillable form fields; you will need to visually determine where to enter data")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
