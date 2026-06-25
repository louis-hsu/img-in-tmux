from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from imgtt.renderer import (
    _sixel_max_bytes,
    check_chafa,
    format_info,
    render_image,
    resolve_format,
)


def test_check_chafa_found():
    with patch("shutil.which", return_value="/usr/bin/chafa"):
        assert check_chafa() is True


def test_check_chafa_missing():
    with patch("shutil.which", return_value=None):
        assert check_chafa() is False


def test_render_image_calls_chafa(tmp_path: Path):
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"fake")
    mock = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock) as mock_run:
        exit_code = render_image(fake_img, cols=56, rows=16)
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "chafa"
    assert "--size=56x16" in cmd
    assert "--passthrough=tmux" not in cmd
    # outside tmux: no --format flag at all (chafa auto-detects)
    assert not any(a.startswith("--format") for a in cmd)
    assert exit_code == 0


def test_render_image_sixel_in_tmux(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("IMGTT_SIXEL_MAX_BYTES", raising=False)
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"fake")
    payload = b"SIXELDATA"
    mock = MagicMock(returncode=0, stdout=payload)
    buf = MagicMock()
    with patch("subprocess.run", return_value=mock) as mock_run:
        with patch("imgtt.renderer.sys.stdout") as stdout:
            stdout.buffer = buf
            rc = render_image(fake_img, cols=56, rows=16, in_tmux=True)
    cmd = mock_run.call_args[0][0]
    assert "--format=sixels" in cmd
    # tmux sixel must cap colors to keep payload under tmux's byte ceiling
    assert "--colors=256" in cmd
    # font-ratio is symbol-only; must not distort sixel
    assert "--font-ratio=1/2" not in cmd
    # small payload written straight to stdout, no shrink
    buf.write.assert_called_once_with(payload)
    assert rc == 0


def test_render_image_format_override(tmp_path: Path):
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"fake")
    mock = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock) as mock_run:
        render_image(fake_img, cols=56, rows=16, in_tmux=True, fmt="iterm")
    cmd = mock_run.call_args[0][0]
    assert "--format=iterm" in cmd
    assert "--format=sixels" not in cmd


def test_render_image_symbols_gets_font_ratio(tmp_path: Path):
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"fake")
    mock = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock) as mock_run:
        render_image(fake_img, cols=56, rows=16, in_tmux=True, fmt="symbols")
    cmd = mock_run.call_args[0][0]
    assert "--format=symbols" in cmd
    assert "--font-ratio=1/2" in cmd
    assert "--colors=full" in cmd


def test_resolve_format():
    assert resolve_format(in_tmux=True, fmt=None) == "sixels"
    assert resolve_format(in_tmux=False, fmt=None) == "auto"
    assert resolve_format(in_tmux=True, fmt="symbols") == "symbols"
    assert resolve_format(in_tmux=False, fmt="iterm") == "iterm"


def test_resolve_format_popup_forces_symbols():
    # tmux popup cannot display sixel -> default to symbols
    assert resolve_format(in_tmux=True, fmt=None, in_popup=True) == "symbols"
    # explicit override still wins (user's escape hatch)
    assert resolve_format(in_tmux=True, fmt="iterm", in_popup=True) == "iterm"
    # popup flag irrelevant outside tmux
    assert resolve_format(in_tmux=False, fmt=None, in_popup=True) == "auto"


def test_render_in_popup_uses_symbols_not_sixel(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("IMGTT_SIXEL_MAX_BYTES", raising=False)
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"fake")
    mock = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock) as mock_run:
        render_image(fake_img, cols=56, rows=16, in_tmux=True, in_popup=True)
    cmd = mock_run.call_args[0][0]
    # symbols path: direct passthrough, no capture, font-ratio applied
    assert "--format=symbols" in cmd
    assert "--format=sixels" not in cmd
    assert "--font-ratio=1/2" in cmd
    assert mock_run.call_args.kwargs.get("stdout") is None


def test_sixel_max_bytes_default(monkeypatch):
    monkeypatch.delenv("IMGTT_SIXEL_MAX_BYTES", raising=False)
    assert _sixel_max_bytes() == 1_300_000


def test_sixel_max_bytes_env_override(monkeypatch):
    monkeypatch.setenv("IMGTT_SIXEL_MAX_BYTES", "555")
    assert _sixel_max_bytes() == 555


def test_sixel_max_bytes_bad_env_falls_back(monkeypatch):
    monkeypatch.setenv("IMGTT_SIXEL_MAX_BYTES", "notanumber")
    assert _sixel_max_bytes() == 1_300_000


def test_render_sixel_shrinks_when_over_cap(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IMGTT_SIXEL_MAX_BYTES", "100")
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"fake")
    big = MagicMock(returncode=0, stdout=b"x" * 200)
    small = MagicMock(returncode=0, stdout=b"x" * 50)
    buf = MagicMock()
    with patch("subprocess.run", side_effect=[big, small]) as mock_run:
        with patch("imgtt.renderer.sys.stdout") as stdout:
            stdout.buffer = buf
            rc = render_image(fake_img, cols=100, rows=50, in_tmux=True)
    assert mock_run.call_count == 2
    first_cmd = mock_run.call_args_list[0][0][0]
    second_cmd = mock_run.call_args_list[1][0][0]
    assert "--size=100x50" in first_cmd
    # shrunk by 0.9: 100->90, 50->45
    assert "--size=90x45" in second_cmd
    # only the in-budget payload is emitted
    buf.write.assert_called_once_with(b"x" * 50)
    assert rc == 0


def test_render_sixel_no_shrink_when_small(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("IMGTT_SIXEL_MAX_BYTES", raising=False)
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"fake")
    mock = MagicMock(returncode=0, stdout=b"x" * 500)
    buf = MagicMock()
    with patch("subprocess.run", return_value=mock) as mock_run:
        with patch("imgtt.renderer.sys.stdout") as stdout:
            stdout.buffer = buf
            rc = render_image(fake_img, cols=126, rows=59, in_tmux=True)
    assert mock_run.call_count == 1
    cmd = mock_run.call_args[0][0]
    assert "--size=126x59" in cmd
    buf.write.assert_called_once_with(b"x" * 500)
    assert rc == 0


def test_render_no_capture_outside_tmux(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("IMGTT_SIXEL_MAX_BYTES", raising=False)
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"fake")
    mock = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock) as mock_run:
        render_image(fake_img, cols=126, rows=59, in_tmux=False)
    cmd = mock_run.call_args[0][0]
    # outside tmux: direct passthrough, no PIPE capture, no shrink
    assert "--size=126x59" in cmd
    assert mock_run.call_args.kwargs.get("stdout") is None


def test_format_info_minimal():
    meta = {"filename": "img.png", "filesize": "1.2MB", "width": 800, "height": 600, "format": "PNG", "mode": "RGB"}
    output = format_info(meta)
    assert "img.png" in output
    assert "800×600" in output
    assert "PNG" in output
    assert "RGB" in output


def test_format_info_with_exif():
    meta = {
        "filename": "photo.jpg",
        "filesize": "3.4MB",
        "width": 4032,
        "height": 3024,
        "format": "JPEG",
        "mode": "RGB",
        "exif": {
            "camera": "iPhone 15 Pro",
            "focal_length": "24mm",
            "aperture": "f/1.8",
            "shutter": "1/120s",
            "iso": "ISO 400",
            "datetime": "2024:11:03 14:32:07",
        },
    }
    output = format_info(meta)
    assert "iPhone 15 Pro" in output
    assert "24mm" in output
    assert "ISO 400" in output
    assert "2024:11:03 14:32:07" in output


def test_format_info_no_exif():
    meta = {"filename": "screen.png", "filesize": "200.0KB", "width": 1920, "height": 1080, "format": "PNG", "mode": "RGB"}
    output = format_info(meta)
    lines = output.strip().split("\n")
    assert len(lines) == 1


def test_size_calculation():
    term_cols, term_rows = 200, 50
    size_pct = 70
    img_cols = max(1, int(term_cols * size_pct / 100))
    img_rows = max(1, int(term_rows * size_pct / 100))
    assert img_cols == 140
    assert img_rows == 35
