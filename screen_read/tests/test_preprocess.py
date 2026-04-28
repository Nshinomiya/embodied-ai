from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("PIL")
pytest.importorskip("cv2")
pytest.importorskip("numpy")

import numpy as np
from PIL import Image

from preprocess import (
    BLUR_VARIANCE_THRESHOLD,
    RESIZE_LONG_EDGE_MAX,
    measure_blur,
    resize_long_edge,
    strip_exif,
)


def _save_jpeg(path: Path, arr: np.ndarray, exif_bytes: bytes | None = None) -> None:
    img = Image.fromarray(arr)
    save_kwargs: dict = {"quality": 95}
    if exif_bytes is not None:
        save_kwargs["exif"] = exif_bytes
    img.save(path, format="JPEG", **save_kwargs)


def _make_sharp_array(size: int = 400) -> np.ndarray:
    """High-contrast checkerboard — large Laplacian variance."""
    rng = np.random.default_rng(seed=1)
    base = rng.integers(0, 2, size=(size // 8, size // 8), dtype=np.uint8) * 255
    tiled = np.kron(base, np.ones((8, 8), dtype=np.uint8))
    rgb = np.stack([tiled, tiled, tiled], axis=-1)
    return rgb


def _make_blurry_array(size: int = 400) -> np.ndarray:
    """Smooth gradient — near-zero Laplacian variance."""
    grad = np.linspace(0, 255, size, dtype=np.uint8)
    plane = np.tile(grad, (size, 1))
    rgb = np.stack([plane, plane, plane], axis=-1)
    return rgb


def test_measure_blur_flags_smooth_image_as_blurry(tmp_path: Path) -> None:
    path = tmp_path / "blurry.jpg"
    _save_jpeg(path, _make_blurry_array())
    result = measure_blur(path)
    assert result.is_blurry
    assert result.variance < BLUR_VARIANCE_THRESHOLD


def test_measure_blur_passes_sharp_image(tmp_path: Path) -> None:
    path = tmp_path / "sharp.jpg"
    _save_jpeg(path, _make_sharp_array())
    result = measure_blur(path)
    assert not result.is_blurry
    assert result.variance >= BLUR_VARIANCE_THRESHOLD


def test_resize_long_edge_shrinks_oversized_image(tmp_path: Path) -> None:
    path = tmp_path / "big.jpg"
    arr = _make_sharp_array(size=4096)
    _save_jpeg(path, arr)
    new_size = resize_long_edge(path)
    assert max(new_size) == RESIZE_LONG_EDGE_MAX
    with Image.open(path) as out:
        assert max(out.size) == RESIZE_LONG_EDGE_MAX


def test_resize_long_edge_skips_small_image(tmp_path: Path) -> None:
    path = tmp_path / "small.jpg"
    arr = _make_sharp_array(size=800)
    _save_jpeg(path, arr)
    before_bytes = path.read_bytes()
    new_size = resize_long_edge(path)
    assert max(new_size) <= RESIZE_LONG_EDGE_MAX
    assert path.read_bytes() == before_bytes


def test_strip_exif_removes_metadata(tmp_path: Path) -> None:
    path = tmp_path / "tagged.jpg"
    exif = Image.Exif()
    exif[0x010F] = "ACME Cameras"  # Make
    exif[0x0110] = "ScreenReader 1.0"  # Model
    _save_jpeg(path, _make_sharp_array(), exif_bytes=exif.tobytes())

    with Image.open(path) as before:
        assert dict(before.getexif())  # sanity: EXIF was actually written

    strip_exif(path)

    with Image.open(path) as after:
        assert not dict(after.getexif())


def test_strip_exif_pillow_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the no-exiftool branch even if the binary is on PATH."""
    path = tmp_path / "tagged.jpg"
    exif = Image.Exif()
    exif[0x010F] = "ACME Cameras"
    _save_jpeg(path, _make_sharp_array(), exif_bytes=exif.tobytes())

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    strip_exif(path)

    with Image.open(path) as after:
        assert not dict(after.getexif())
