import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from imgtt.main import main


def test_size_probe_no_tmux(monkeypatch, capsys):
    monkeypatch.delenv("TMUX", raising=False)
    with patch("imgtt.main.get_terminal_size", return_value=(200, 50)):
        with patch("sys.argv", ["imgtt", "--size-probe"]):
            main()
    out = capsys.readouterr().out
    assert "200x50" in out
    assert "tmux: no" in out


def test_size_probe_in_tmux(monkeypatch, capsys):
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1234,0")
    with patch("imgtt.main.get_terminal_size", return_value=(120, 40)):
        with patch("sys.argv", ["imgtt", "--size-probe"]):
            main()
    out = capsys.readouterr().out
    assert "120x40" in out
    assert "tmux: yes" in out


def test_info_only_skips_chafa(fixtures_dir: Path, capsys):
    with patch("imgtt.main.get_terminal_size", return_value=(200, 50)):
        with patch("imgtt.main.check_chafa", return_value=True):
            with patch("imgtt.main.render_image") as mock_render:
                with patch("sys.argv", ["imgtt", "--info-only", str(fixtures_dir / "no_exif.png")]):
                    main()
    mock_render.assert_not_called()
    out = capsys.readouterr().out
    assert "no_exif.png" in out


def test_debug_writes_to_stderr(fixtures_dir: Path, capsys):
    with patch("imgtt.main.get_terminal_size", return_value=(200, 50)):
        with patch("imgtt.main.check_chafa", return_value=True):
            with patch("imgtt.main.render_image", return_value=0):
                # file before --debug so argparse doesn't consume path as debug value
                with patch("sys.argv", ["imgtt", str(fixtures_dir / "no_exif.png"), "--debug"]):
                    main()
    err = capsys.readouterr().err
    assert "[imgtt]" in err
    assert "pane size" in err
    assert "render size" in err


def test_debug_writes_to_file(fixtures_dir: Path, tmp_path: Path, capsys):
    log_file = tmp_path / "debug.log"
    with patch("imgtt.main.get_terminal_size", return_value=(200, 50)):
        with patch("imgtt.main.check_chafa", return_value=True):
            with patch("imgtt.main.render_image", return_value=0):
                with patch("sys.argv", ["imgtt", f"--debug-file={log_file}", str(fixtures_dir / "no_exif.png")]):
                    main()
    content = log_file.read_text()
    assert "[imgtt]" in content
    assert "pane size" in content
    assert capsys.readouterr().err == ""


def test_debug_does_not_consume_path(fixtures_dir: Path, capsys):
    # regression: --debug PATH must NOT treat PATH as a logfile to open("w");
    # PATH is the image. Truncating the image was a data-loss bug.
    img = fixtures_dir / "no_exif.png"
    before = img.read_bytes()
    with patch("imgtt.main.get_terminal_size", return_value=(200, 50)):
        with patch("imgtt.main.check_chafa", return_value=True):
            with patch("imgtt.main.render_image", return_value=0):
                with patch("sys.argv", ["imgtt", "--debug", str(img)]):
                    main()
    assert img.read_bytes() == before  # image untouched
    err = capsys.readouterr().err
    assert "[imgtt]" in err


def test_invalid_image_exits_1(tmp_path: Path, capsys):
    bad = tmp_path / "empty.jpg"
    bad.write_bytes(b"")  # 0-byte, not decodable
    with patch("imgtt.main.get_terminal_size", return_value=(80, 24)):
        with patch("imgtt.main.check_chafa", return_value=True):
            with patch("imgtt.main.render_image") as mock_render:
                with patch("sys.argv", ["imgtt", str(bad)]):
                    with pytest.raises(SystemExit) as exc:
                        main()
    assert exc.value.code == 1
    mock_render.assert_not_called()
    assert "not a valid image" in capsys.readouterr().err


def test_missing_file_exits_1(tmp_path: Path):
    with patch("imgtt.main.get_terminal_size", return_value=(80, 24)):
        with patch("imgtt.main.check_chafa", return_value=True):
            with patch("sys.argv", ["imgtt", str(tmp_path / "ghost.jpg")]):
                with pytest.raises(SystemExit) as exc:
                    main()
    assert exc.value.code == 1
