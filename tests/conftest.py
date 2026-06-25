import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image


def _make_png(path: Path, width: int = 100, height: int = 80) -> None:
    img = Image.new("RGB", (width, height), color=(100, 149, 237))
    img.save(path, format="PNG")


def _make_jpeg_with_exif(path: Path) -> None:
    import io
    import piexif

    img = Image.new("RGB", (200, 150), color=(255, 128, 0))
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: b"Apple",
            piexif.ImageIFD.Model: b"iPhone 15 Pro",
        },
        "Exif": {
            piexif.ExifIFD.FocalLength: (24, 1),
            piexif.ExifIFD.FNumber: (178, 100),
            piexif.ExifIFD.ExposureTime: (1, 120),
            piexif.ExifIFD.ISOSpeedRatings: 400,
            piexif.ExifIFD.DateTimeOriginal: b"2024:11:03 14:32:07",
        },
        "1st": {},
        "thumbnail": None,
        "GPS": {},
    }
    exif_bytes = piexif.dump(exif_dict)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes)
    path.write_bytes(buf.getvalue())


def _make_corrupt(path: Path) -> None:
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("fixtures")

    _make_png(d / "no_exif.png")
    _make_corrupt(d / "corrupt.jpg")

    try:
        import piexif
        _make_jpeg_with_exif(d / "with_exif.jpg")
    except ImportError:
        # piexif not available — make plain JPEG instead
        img = Image.new("RGB", (200, 150), color=(255, 128, 0))
        img.save(d / "with_exif.jpg", format="JPEG")

    return d
