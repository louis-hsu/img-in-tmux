import os
from unittest.mock import MagicMock, patch

import pytest

from imgtt.dimensions import get_terminal_size


def test_tmux_pane_size(monkeypatch):
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1234,0")
    mock = MagicMock(returncode=0, stdout="120\n40\n")
    with patch("subprocess.run", return_value=mock):
        cols, rows = get_terminal_size()
    assert cols == 120
    assert rows == 40


def test_tmux_subprocess_failure_falls_back(monkeypatch):
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1234,0")
    mock = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=mock):
        with patch("os.get_terminal_size") as mock_tsize:
            mock_tsize.return_value = MagicMock(columns=160, lines=45)
            cols, rows = get_terminal_size()
    assert cols == 160
    assert rows == 45


def test_tmux_timeout_falls_back(monkeypatch):
    import subprocess
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1234,0")
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("tmux", 2)):
        with patch("os.get_terminal_size") as mock_tsize:
            mock_tsize.return_value = MagicMock(columns=80, lines=24)
            cols, rows = get_terminal_size()
    assert cols == 80
    assert rows == 24


def test_stderr_fd_used_outside_tmux(monkeypatch):
    monkeypatch.delenv("TMUX", raising=False)
    with patch("os.get_terminal_size") as mock_tsize:
        mock_tsize.return_value = MagicMock(columns=200, lines=50)
        cols, rows = get_terminal_size()
    assert cols == 200
    assert rows == 50


def test_hardcoded_fallback(monkeypatch):
    monkeypatch.delenv("TMUX", raising=False)
    with patch("os.get_terminal_size", side_effect=OSError):
        cols, rows = get_terminal_size()
    assert cols == 80
    assert rows == 24
