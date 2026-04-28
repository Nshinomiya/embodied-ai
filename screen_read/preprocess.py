"""Pre-OCR image preprocessing for screen-read.

Implements the F-9 / F-10 / F-14 requirements:

* **Blur detection** — Laplacian-variance check (threshold 100).
* **EXIF stripping** — ``exiftool -all=`` when available, with a Pillow
  re-encode fallback for environments without exiftool.
* **Resize** — clamp the long edge to ``RESIZE_LONG_EDGE_MAX`` to keep
  cloud-OCR cost within the per-page budget.
* **Capture cooldown** — single source of truth for the inter-shot delay.

Heavy dependencies (Pillow / OpenCV / NumPy) are imported lazily so the
``merge`` module — and its tests — keep working without the
``preprocess`` extra installed.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

BLUR_VARIANCE_THRESHOLD = 100.0
RESIZE_LONG_EDGE_MAX = 2000
RESIZE_LONG_EDGE_MIN = 1600
CAPTURE_COOLDOWN_SECONDS = 0.5


@dataclass
class BlurCheck:
    variance: float
    is_blurry: bool


def measure_blur(image_path: str | Path) -> BlurCheck:
    """Return Laplacian variance + a blurry/sharp verdict.

    Lower variance ⇒ less edge energy ⇒ blurrier image. The 100.0
    threshold matches the requirements doc and is a starting point;
    expect to tune against real captures.
    """
    import cv2

    path = str(image_path)
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"failed to read image: {path}")
    variance = float(cv2.Laplacian(img, cv2.CV_64F).var())
    return BlurCheck(variance=variance, is_blurry=variance < BLUR_VARIANCE_THRESHOLD)


def strip_exif(image_path: str | Path) -> None:
    """Remove all EXIF/metadata in place.

    Prefers ``exiftool -all=`` (lossless on JPEG). Falls back to a
    Pillow re-encode that drops the EXIF block by reconstructing the
    image without it.
    """
    path = Path(image_path)
    if shutil.which("exiftool"):
        subprocess.run(
            ["exiftool", "-overwrite_original", "-all=", str(path)],
            check=True,
            capture_output=True,
        )
        return
    _strip_exif_with_pillow(path)


def _strip_exif_with_pillow(path: Path) -> None:
    from PIL import Image

    with Image.open(path) as src:
        src.load()
        clean = Image.new(src.mode, src.size)
        clean.paste(src)
        fmt = src.format
    save_kwargs: dict = {}
    if fmt == "JPEG":
        save_kwargs["quality"] = 95
    clean.save(path, format=fmt, **save_kwargs)


def resize_long_edge(image_path: str | Path, max_long_edge: int = RESIZE_LONG_EDGE_MAX) -> tuple[int, int]:
    """Shrink so the long edge ≤ ``max_long_edge``. Never upscales.

    Returns the resulting ``(width, height)``. If the image is already
    within bounds, the file is left untouched.
    """
    from PIL import Image

    path = Path(image_path)
    with Image.open(path) as src:
        src.load()
        width, height = src.size
        long_edge = max(width, height)
        if long_edge <= max_long_edge:
            return width, height
        scale = max_long_edge / long_edge
        new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
        resized = src.resize(new_size, Image.LANCZOS)
        fmt = src.format
        save_kwargs: dict = {}
        if fmt == "JPEG":
            save_kwargs["quality"] = 95
        resized.save(path, format=fmt, **save_kwargs)
        return new_size
