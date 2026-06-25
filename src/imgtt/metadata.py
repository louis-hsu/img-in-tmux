import os
from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS


def get_metadata(path: Path) -> dict:
    result: dict = {
        "filename": path.name,
        "filesize": _format_size(os.path.getsize(path)),
    }

    try:
        with Image.open(path) as img:
            result["width"] = img.width
            result["height"] = img.height
            result["format"] = img.format
            result["mode"] = img.mode

            raw_exif = img.getexif()
            if raw_exif:
                tagged = {TAGS.get(tag_id, tag_id): v for tag_id, v in raw_exif.items()}
                parsed = _parse_exif(tagged)
                if parsed:
                    result["exif"] = parsed
    except Exception:
        pass

    return result


def _parse_exif(exif: dict) -> dict:
    result: dict = {}

    make = str(exif.get("Make", "")).strip()
    model = str(exif.get("Model", "")).strip()
    if model:
        result["camera"] = model if (make and model.startswith(make)) else f"{make} {model}".strip()

    lens = str(exif.get("LensModel", "")).strip()
    if lens:
        result["lens"] = lens

    focal = exif.get("FocalLength")
    if focal is not None:
        try:
            result["focal_length"] = f"{int(float(focal))}mm"
        except (TypeError, ValueError):
            pass

    fnumber = exif.get("FNumber")
    if fnumber is not None:
        try:
            result["aperture"] = f"f/{float(fnumber):.1f}"
        except (TypeError, ValueError):
            pass

    exposure = exif.get("ExposureTime")
    if exposure is not None:
        try:
            v = float(exposure)
            result["shutter"] = f"1/{int(1/v)}s" if v < 1 else f"{v:.1f}s"
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    iso = exif.get("ISOSpeedRatings")
    if iso is not None:
        result["iso"] = f"ISO {iso}"

    dt = exif.get("DateTimeOriginal") or exif.get("DateTime")
    if dt:
        result["datetime"] = str(dt)

    return result


def _format_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f}{unit}"
        nbytes //= 1024
    return f"{nbytes:.1f}TB"
