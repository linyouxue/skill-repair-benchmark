"""Multi-variant OCR runner tuned for scanned receipts and similar documents.

The goal is to get one function that produces several complementary OCR
renderings for a single image so downstream extraction code can vote across
them. Running every variant for every image is expensive, so results are
cached on disk by (file content hash, variant key).

Only generic image/OCR preprocessing lives here. No task-specific keyword
tables, numeric formats, date formats, output schemas or filename lists
appear in this file.

Typical use::

    from receipt_ocr import ocr_variants, DEFAULT_VARIANTS

    for text, label in ocr_variants(path, variants=DEFAULT_VARIANTS):
        ...  # feed into generic extraction

For difficult images, call ``ocr_variants(path, variants=ALL_VARIANTS)``
to also try higher upscales and PSM 4.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageFilter, ImageOps

import pytesseract


# A variant is a reproducible recipe: a label, a preprocessing pipeline and
# a Tesseract PSM mode. Pipelines operate on a PIL Image and return a PIL
# Image. Keep them pure so the cache key stays stable.
@dataclass(frozen=True)
class Variant:
    label: str
    psm: int
    upscale: float = 1.0
    grayscale: bool = False
    autocontrast: bool = False
    sharpen: bool = False
    invert: bool = False


# Sensible default set: three complementary variants that together cover
# most printed receipts/documents without blowing up the OCR budget.
DEFAULT_VARIANTS: Tuple[Variant, ...] = (
    Variant(label="raw_psm3", psm=3),
    Variant(label="gray_ac_psm6", psm=6, grayscale=True, autocontrast=True),
    Variant(label="up2x_gray_ac_psm6", psm=6, upscale=2.0, grayscale=True, autocontrast=True),
)


# Extended set to try when the default variants disagree or produce no answer.
ALL_VARIANTS: Tuple[Variant, ...] = DEFAULT_VARIANTS + (
    Variant(label="up2x_gray_ac_psm4", psm=4, upscale=2.0, grayscale=True, autocontrast=True),
    Variant(label="up3x_gray_ac_psm6", psm=6, upscale=3.0, grayscale=True, autocontrast=True),
    Variant(label="up3x_gray_ac_psm4", psm=4, upscale=3.0, grayscale=True, autocontrast=True),
    Variant(label="gray_ac_sharp_psm6", psm=6, grayscale=True, autocontrast=True, sharpen=True),
    Variant(label="gray_ac_invert_psm6", psm=6, grayscale=True, autocontrast=True, invert=True),
)


def _preprocess(img: Image.Image, v: Variant) -> Image.Image:
    out = img
    if v.upscale and v.upscale != 1.0:
        new_size = (int(out.width * v.upscale), int(out.height * v.upscale))
        out = out.resize(new_size, Image.Resampling.LANCZOS)
    if v.grayscale:
        out = ImageOps.grayscale(out)
    if v.autocontrast:
        out = ImageOps.autocontrast(out)
    if v.sharpen:
        out = out.filter(ImageFilter.SHARPEN)
    if v.invert:
        # Only meaningful on single-channel images.
        out = ImageOps.invert(out.convert("L"))
    return out


def _cache_key(path: Path, v: Variant) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 16)
            if not chunk:
                break
            h.update(chunk)
    return f"{h.hexdigest()}_{v.label}_psm{v.psm}"


def ocr_variants(
    image_path,
    variants: Sequence[Variant] = DEFAULT_VARIANTS,
    cache_dir: Optional[str] = None,
    lang: str = "eng",
) -> List[Tuple[str, str]]:
    """Return ``[(text, label), ...]`` by running each variant on the image.

    ``cache_dir`` enables on-disk caching keyed by file content; passing
    ``None`` disables caching. The returned text is Tesseract's raw output
    (no normalisation) so extraction code can decide how to tokenise.
    """
    path = Path(image_path)
    cache_root: Optional[Path] = None
    if cache_dir:
        cache_root = Path(cache_dir)
        cache_root.mkdir(parents=True, exist_ok=True)

    img = Image.open(path)
    results: List[Tuple[str, str]] = []
    for v in variants:
        text: Optional[str] = None
        cache_path: Optional[Path] = None
        if cache_root is not None:
            cache_path = cache_root / f"{_cache_key(path, v)}.txt"
            if cache_path.exists():
                try:
                    text = cache_path.read_text(encoding="utf-8")
                except OSError:
                    text = None
        if text is None:
            processed = _preprocess(img, v)
            try:
                text = pytesseract.image_to_string(
                    processed, lang=lang, config=f"--psm {v.psm}"
                )
            except Exception as exc:  # pragma: no cover - diagnostic path
                text = ""
                print(f"[receipt_ocr] variant {v.label} failed on {path.name}: {exc}")
            if cache_path is not None:
                try:
                    cache_path.write_text(text, encoding="utf-8")
                except OSError:
                    pass
        results.append((text, v.label))
    return results


def run_single(image_path, psm: int = 6, preprocess: bool = True, upscale: float = 1.0) -> str:
    """Convenience wrapper: one OCR pass with simple knobs."""
    v = Variant(
        label="adhoc",
        psm=psm,
        upscale=upscale,
        grayscale=preprocess,
        autocontrast=preprocess,
    )
    img = Image.open(image_path)
    processed = _preprocess(img, v)
    return pytesseract.image_to_string(processed, config=f"--psm {psm}")


def iter_images(directory, extensions: Iterable[str] = (".jpg", ".jpeg", ".png", ".webp")) -> List[Path]:
    """Return sorted image paths inside *directory* with any of *extensions*."""
    exts = {e.lower() for e in extensions}
    return sorted(
        p for p in Path(directory).iterdir()
        if p.is_file() and p.suffix.lower() in exts
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a single OCR pass on one image.")
    parser.add_argument("image")
    parser.add_argument("--psm", type=int, default=6)
    parser.add_argument("--upscale", type=float, default=1.0)
    parser.add_argument("--no-preprocess", action="store_true")
    args = parser.parse_args()

    text = run_single(
        args.image,
        psm=args.psm,
        preprocess=not args.no_preprocess,
        upscale=args.upscale,
    )
    print(text)
