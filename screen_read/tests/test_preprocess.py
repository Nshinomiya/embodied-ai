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
    BRIGHTNESS_MEAN_THRESHOLD,
    BRIGHTNESS_STD_THRESHOLD,
    RESIZE_LONG_EDGE_MAX,
    measure_blur,
    measure_brightness,
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


def test_measure_brightness_flags_dark_image(tmp_path: Path) -> None:
    """暗い画像（mean < BRIGHTNESS_MEAN_THRESHOLD）は low_contrast 判定。"""
    path = tmp_path / "dark.jpg"
    rng = np.random.default_rng(seed=2)
    arr = rng.integers(0, 30, size=(400, 400), dtype=np.uint8)  # mean ~15
    rgb = np.stack([arr, arr, arr], axis=-1)
    _save_jpeg(path, rgb)
    result = measure_brightness(path)
    assert result.is_low_contrast
    assert result.mean < BRIGHTNESS_MEAN_THRESHOLD


def test_measure_brightness_flags_low_std_image(tmp_path: Path) -> None:
    """全体的にフラットな画像（std < BRIGHTNESS_STD_THRESHOLD）も low_contrast。"""
    path = tmp_path / "flat.jpg"
    arr = np.full((400, 400), 128, dtype=np.uint8)  # uniform mid-gray
    rgb = np.stack([arr, arr, arr], axis=-1)
    _save_jpeg(path, rgb)
    result = measure_brightness(path)
    assert result.is_low_contrast
    assert result.std < BRIGHTNESS_STD_THRESHOLD


def test_measure_brightness_passes_well_lit_image(tmp_path: Path) -> None:
    """十分明るくコントラストもある画像は通過する。"""
    path = tmp_path / "well_lit.jpg"
    arr = _make_sharp_array()  # 0/255 checkerboard: mean ~127, std ~127
    _save_jpeg(path, arr)
    result = measure_brightness(path)
    assert not result.is_low_contrast
    assert result.mean >= BRIGHTNESS_MEAN_THRESHOLD
    assert result.std >= BRIGHTNESS_STD_THRESHOLD


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
