import fcntl
import os
import struct
import subprocess
import sys
import termios
from typing import NamedTuple


class TermSize(NamedTuple):
    cols: int
    rows: int
    source: str  # "fzf" | "pty" | "tmux" | "default"
    in_tmux: bool
    in_popup: bool


def _fzf_preview_size() -> tuple[int, int] | None:
    """fzf exposes the preview window's own size; neither the pty nor tmux
    display-message report it correctly, so prefer it when present."""
    c = os.environ.get("FZF_PREVIEW_COLUMNS")
    r = os.environ.get("FZF_PREVIEW_LINES")
    if c and r:
        try:
            cols, rows = int(c), int(r)
            if cols > 0 and rows > 0:
                return cols, rows
        except ValueError:
            pass
    return None


def _pty_size() -> tuple[int, int] | None:
    """Size of the controlling terminal. In tmux this is the pane's pty, and
    inside a popup it is the popup's pty — so it is correct where tmux
    display-message is not. Read /dev/tty first (works even when stdout/stderr
    are redirected, e.g. fzf preview), then fall back to the std streams."""
    try:
        fd = os.open("/dev/tty", os.O_RDONLY | os.O_NOCTTY)
        try:
            data = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8)
            rows, cols, _, _ = struct.unpack("HHHH", data)
            if cols > 0 and rows > 0:
                return cols, rows
        finally:
            os.close(fd)
    except OSError:
        pass

    for stream in (sys.stdout, sys.stderr):
        try:
            size = os.get_terminal_size(stream.fileno())
            if size.columns > 0 and size.lines > 0:
                return size.columns, size.lines
        except (AttributeError, ValueError, OSError):
            pass
    return None


def _tmux_pane_size() -> tuple[int, int] | None:
    if "TMUX" not in os.environ:
        return None
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{pane_width}\n#{pane_height}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split("\n")
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    return None


def detect_size() -> TermSize:
    """Resolve the render area and classify the context.

    Priority: fzf preview env -> controlling-terminal pty -> tmux pane -> 80x24.
    A tmux popup is detected when the pty (the popup overlay) is smaller than the
    underlying pane reported by display-message; popups cannot display sixel, so
    callers use this to fall back to symbols.
    """
    in_tmux = "TMUX" in os.environ

    fzf = _fzf_preview_size()
    if fzf:
        return TermSize(fzf[0], fzf[1], "fzf", in_tmux, False)

    pty = _pty_size()
    pane = _tmux_pane_size()

    in_popup = bool(
        in_tmux and pty and pane and (pty[0] < pane[0] or pty[1] < pane[1])
    )

    if pty:
        return TermSize(pty[0], pty[1], "pty", in_tmux, in_popup)
    if pane:
        return TermSize(pane[0], pane[1], "tmux", in_tmux, False)
    return TermSize(80, 24, "default", in_tmux, False)


def get_terminal_size() -> tuple[int, int]:
    s = detect_size()
    return s.cols, s.rows


def underlying_iterm() -> bool:
    """Is the real terminal iTerm2? Inside tmux TERM_PROGRAM is "tmux", but
    iTerm2 sets LC_TERMINAL (passed through tmux) — the reliable signal."""
    return os.environ.get("LC_TERMINAL", "").lower() == "iterm2"


def tmux_passthrough_on() -> bool:
    """True when tmux's allow-passthrough option is enabled (required to forward
    graphics sequences to the real terminal)."""
    if "TMUX" not in os.environ:
        return False
    try:
        result = subprocess.run(
            ["tmux", "show", "-gv", "allow-passthrough"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            # "on" or "all" both enable passthrough; anything else is off.
            return result.stdout.strip() in ("on", "all")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False
