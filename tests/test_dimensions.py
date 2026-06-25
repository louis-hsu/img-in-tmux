from unittest.mock import MagicMock, patch

from imgtt import dimensions
from imgtt.dimensions import (
    detect_size,
    get_terminal_size,
    tmux_passthrough_on,
    underlying_iterm,
)


def _patch(monkeypatch, *, tmux=False, fzf=None, pty=None, pane=None):
    if tmux:
        monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1234,0")
    else:
        monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setattr(dimensions, "_fzf_preview_size", lambda: fzf)
    monkeypatch.setattr(dimensions, "_pty_size", lambda: pty)
    monkeypatch.setattr(dimensions, "_tmux_pane_size", lambda: pane)


def test_pty_preferred_in_normal_pane(monkeypatch):
    # normal pane: pty == pane, not a popup
    _patch(monkeypatch, tmux=True, pty=(120, 40), pane=(120, 40))
    s = detect_size()
    assert (s.cols, s.rows) == (120, 40)
    assert s.source == "pty"
    assert s.in_tmux is True
    assert s.in_popup is False


def test_popup_detected_when_pty_smaller_than_pane(monkeypatch):
    # popup overlay (80x24) over a 200x50 pane
    _patch(monkeypatch, tmux=True, pty=(80, 24), pane=(200, 50))
    s = detect_size()
    assert (s.cols, s.rows) == (80, 24)  # popup's own size, not the pane
    assert s.in_popup is True


def test_popup_detected_on_single_axis(monkeypatch):
    _patch(monkeypatch, tmux=True, pty=(200, 24), pane=(200, 50))
    s = detect_size()
    assert s.in_popup is True


def test_fzf_preview_wins(monkeypatch):
    _patch(monkeypatch, tmux=True, fzf=(60, 20), pty=(200, 50), pane=(200, 50))
    s = detect_size()
    assert (s.cols, s.rows) == (60, 20)
    assert s.source == "fzf"
    assert s.in_popup is False


def test_tmux_fallback_when_no_pty(monkeypatch):
    _patch(monkeypatch, tmux=True, pty=None, pane=(150, 45))
    s = detect_size()
    assert (s.cols, s.rows) == (150, 45)
    assert s.source == "tmux"
    assert s.in_popup is False  # cannot compare without pty


def test_hardcoded_fallback(monkeypatch):
    _patch(monkeypatch, tmux=False, pty=None, pane=None)
    s = detect_size()
    assert (s.cols, s.rows) == (80, 24)
    assert s.source == "default"


def test_no_popup_outside_tmux(monkeypatch):
    # pty present, not in tmux -> never a popup
    _patch(monkeypatch, tmux=False, pty=(100, 30), pane=None)
    s = detect_size()
    assert s.in_popup is False
    assert s.in_tmux is False


def test_get_terminal_size_wrapper(monkeypatch):
    _patch(monkeypatch, tmux=True, pty=(111, 33), pane=(111, 33))
    assert get_terminal_size() == (111, 33)


def test_fzf_preview_size_reads_env(monkeypatch):
    monkeypatch.setenv("FZF_PREVIEW_COLUMNS", "70")
    monkeypatch.setenv("FZF_PREVIEW_LINES", "22")
    assert dimensions._fzf_preview_size() == (70, 22)


def test_fzf_preview_size_bad_env(monkeypatch):
    monkeypatch.setenv("FZF_PREVIEW_COLUMNS", "x")
    monkeypatch.setenv("FZF_PREVIEW_LINES", "22")
    assert dimensions._fzf_preview_size() is None


def test_tmux_pane_size_none_outside_tmux(monkeypatch):
    monkeypatch.delenv("TMUX", raising=False)
    assert dimensions._tmux_pane_size() is None


def test_underlying_iterm_true(monkeypatch):
    monkeypatch.setenv("LC_TERMINAL", "iTerm2")
    assert underlying_iterm() is True


def test_underlying_iterm_false(monkeypatch):
    monkeypatch.setenv("LC_TERMINAL", "WezTerm")
    assert underlying_iterm() is False
    monkeypatch.delenv("LC_TERMINAL", raising=False)
    assert underlying_iterm() is False


def test_passthrough_off_outside_tmux(monkeypatch):
    monkeypatch.delenv("TMUX", raising=False)
    assert tmux_passthrough_on() is False


def test_passthrough_on(monkeypatch):
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1,0")
    mock = MagicMock(returncode=0, stdout="on\n")
    with patch("subprocess.run", return_value=mock):
        assert tmux_passthrough_on() is True


def test_passthrough_off_when_disabled(monkeypatch):
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1,0")
    mock = MagicMock(returncode=0, stdout="off\n")
    with patch("subprocess.run", return_value=mock):
        assert tmux_passthrough_on() is False
