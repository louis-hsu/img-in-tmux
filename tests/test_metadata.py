from pathlib import Path

import pytest

from imgtt.metadata import _format_size, _parse_exif, get_metadata


def test_png_no_exif(fixtures_dir: Path):
    meta = get_metadata(fixtures_dir / "no_exif.png")
    assert meta["filename"] == "no_exif.png"
    assert meta["width"] == 100
    assert meta["height"] == 80
    assert meta["format"] == "PNG"
    assert "exif" not in meta


def test_jpeg_basic_fields(fixtures_dir: Path):
    meta = get_metadata(fixtures_dir / "with_exif.jpg")
    assert meta["filename"] == "with_exif.jpg"
    assert meta["width"] == 200
    assert meta["height"] == 150
    assert meta["format"] == "JPEG"
    assert "filesize" in meta


def test_corrupt_file_no_crash(fixtures_dir: Path):
    meta = get_metadata(fixtures_dir / "corrupt.jpg")
    assert meta["filename"] == "corrupt.jpg"
    assert "filesize" in meta
    assert "width" not in meta


def test_format_size_bytes():
    assert _format_size(512) == "512.0B"


def test_format_size_kb():
    assert _format_size(2048) == "2.0KB"


def test_format_size_mb():
    assert _format_size(2 * 1024 * 1024) == "2.0MB"


def test_parse_exif_camera_dedup():
    exif = {"Make": "Apple", "Model": "Apple iPhone 15 Pro"}
    result = _parse_exif(exif)
    assert result["camera"] == "Apple iPhone 15 Pro"


def test_parse_exif_camera_concat():
    exif = {"Make": "Canon", "Model": "EOS R5"}
    result = _parse_exif(exif)
    assert result["camera"] == "Canon EOS R5"


def test_parse_exif_shutter_fraction():
    exif = {"ExposureTime": 1 / 120}
    result = _parse_exif(exif)
    assert result["shutter"].startswith("1/")


def test_parse_exif_shutter_long():
    exif = {"ExposureTime": 2.0}
    result = _parse_exif(exif)
    assert result["shutter"] == "2.0s"


def test_parse_exif_missing_fields():
    result = _parse_exif({})
    assert result == {}
