import base64
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

_ESC = b"\x1b"
_BEL = b"\x07"


def check_chafa() -> bool:
    return shutil.which("chafa") is not None


# Pixel-true formats: tmux 3.3+ captures sixel into its grid so it survives
# redraws. symbols is the half-block fallback (lower res but works anywhere).
_SYMBOL_FORMATS = {"symbols", "symbol"}
_SIXEL_FORMATS = {"sixels", "sixel"}

# tmux silently drops a sixel whose PAYLOAD exceeds ~1.4-2M bytes (observed on
# tmux 3.6b). Payload depends on pixel count AND image detail (truecolor runs),
# so a pixel-dimension cap is unreliable — a short-but-detailed image can blow
# the budget while a large-but-flat one survives. Two defenses:
#   1. cap colors: chafa defaults to truecolor; 256 colors cuts payload ~60%
#      with negligible quality loss on a terminal.
#   2. measure-and-shrink backstop: capture chafa's emitted bytes and, if still
#      over the ceiling, re-render at progressively smaller --size until under.
# Ceiling is env-overridable via IMGTT_SIXEL_MAX_BYTES for other tmux builds.
_SIXEL_COLORS = 256
_DEFAULT_SIXEL_MAX_BYTES = 1_300_000
_SHRINK_STEP = 0.9
_MIN_DIM = 10
_MAX_SHRINK_ATTEMPTS = 12


def _sixel_max_bytes() -> int:
    raw = os.environ.get("IMGTT_SIXEL_MAX_BYTES")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return _DEFAULT_SIXEL_MAX_BYTES


def resolve_format(
    in_tmux: bool,
    fmt: str | None,
    in_popup: bool = False,
    underlying_iterm: bool = False,
    in_fzf: bool = False,
    passthrough: bool = False,
) -> str:
    """Pick a render mode. Returns a chafa format name, "auto" (no --format),
    or "iterm_pt" (our own iTerm2 inline-image emitter over tmux passthrough)."""
    if fmt:
        # Honor explicit override. In tmux with passthrough available, route an
        # iterm request through our own emitter so it actually survives tmux
        # (chafa's passthrough wrapping is unreliable under redirected stdio).
        if fmt == "iterm" and in_tmux and passthrough:
            return "iterm_pt"
        return fmt
    # tmux popups cannot display any graphics (the overlay is drawn separately
    # from the pane grid where images live) — symbols is the only thing visible.
    if in_tmux and in_popup:
        return "symbols"
    # High-quality path: in a tmux fzf preview on iTerm2 we emit the native
    # truecolor inline-image protocol via passthrough. Gated to fzf because the
    # preview re-runs on each move, re-drawing the (untracked) passthrough image;
    # a one-shot invocation would be cleared on the next tmux redraw.
    if in_tmux and underlying_iterm and passthrough and in_fzf:
        return "iterm_pt"
    # In tmux, native sixel survives redraws (verified). Outside, "auto" tells
    # imgtt to omit --format so chafa picks the best protocol for the terminal.
    return "sixels" if in_tmux else "auto"


def render_iterm_passthrough(
    path: Path, cols: int, rows: int, log: Callable[[str], None] | None = None
) -> int:
    """Emit the iTerm2 inline-image protocol wrapped in tmux passthrough.

    Sends the original file bytes (base64) so iTerm2 decodes at native
    resolution and truecolor — matching yazi's quality, unlike palette-limited
    sixel. tmux does not store passthrough output, so there is no payload byte
    ceiling, but it is also not redrawn by tmux (see resolve_format gating).
    """
    try:
        data = path.read_bytes()
    except OSError as exc:
        if log:
            log(f"iterm read failed: {exc}")
        return 1
    b64 = base64.b64encode(data)
    header = (
        f"\x1b]1337;File=inline=1;size={len(data)};"
        f"width={cols};height={rows};preserveAspectRatio=1:"
    ).encode("ascii")
    inner = header + b64 + _BEL
    # tmux passthrough: ESC Ptmux; <payload, every ESC doubled> ESC \
    wrapped = _ESC + b"Ptmux;" + inner.replace(_ESC, _ESC + _ESC) + _ESC + b"\\"
    # tmux cannot see the passthrough image, so its cursor stays put and the
    # caller's info text would print over the image. Emit a tmux-visible
    # cursor-down (CUD) of the image's cell height so following text lands below
    # it. preserveAspectRatio means the image is at most `rows` cells tall.
    advance = f"\x1b[{rows}B\r".encode("ascii")
    if log:
        log(f"iterm passthrough: {len(data)} img bytes -> {len(wrapped)} wrapped, {cols}x{rows} cells")
    sys.stdout.buffer.write(wrapped + advance)
    sys.stdout.buffer.flush()
    return 0


def _build_cmd(path: Path, cols: int, rows: int, resolved: str) -> list[str]:
    cmd = ["chafa", f"--size={cols}x{rows}"]
    # "auto" is not a real chafa format — omit the flag so chafa auto-detects.
    if resolved != "auto":
        cmd.append(f"--format={resolved}")
    # Cap colors for tmux sixel to keep the payload under tmux's byte ceiling.
    if resolved in _SIXEL_FORMATS:
        cmd.append(f"--colors={_SIXEL_COLORS}")
    # --font-ratio only affects symbol cell geometry; for pixel formats it can
    # distort aspect, so apply it solely in symbol mode.
    if resolved in _SYMBOL_FORMATS:
        cmd += ["--font-ratio=1/2", "--colors=full"]
    cmd.append(str(path))
    return cmd


def _render_sixel_capped(
    path: Path, cols: int, rows: int, resolved: str, log: Callable[[str], None] | None
) -> int:
    """Render sixel, shrinking --size until the payload fits tmux's byte cap."""
    max_bytes = _sixel_max_bytes()
    cur_cols, cur_rows = cols, rows
    payload: bytes | None = None
    for attempt in range(_MAX_SHRINK_ATTEMPTS):
        cmd = _build_cmd(path, cur_cols, cur_rows, resolved)
        if log:
            log(f"chafa cmd: {' '.join(cmd)}")
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if proc.returncode != 0:
            if log:
                log(f"chafa exit {proc.returncode} at {cur_cols}x{cur_rows}")
            return proc.returncode
        payload = proc.stdout
        n = len(payload)
        if log:
            log(f"sixel attempt {attempt}: {cur_cols}x{cur_rows} -> {n} bytes (cap {max_bytes})")
        if n <= max_bytes:
            break
        nc, nr = int(cur_cols * _SHRINK_STEP), int(cur_rows * _SHRINK_STEP)
        if nc < _MIN_DIM or nr < _MIN_DIM or (nc == cur_cols and nr == cur_rows):
            if log:
                log(f"sixel at floor {cur_cols}x{cur_rows}, emitting {n} bytes anyway")
            break
        cur_cols, cur_rows = nc, nr
    if payload is not None:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
    return 0


def render_image(
    path: Path,
    cols: int,
    rows: int,
    in_tmux: bool = False,
    fmt: str | None = None,
    in_popup: bool = False,
    underlying_iterm: bool = False,
    in_fzf: bool = False,
    passthrough: bool = False,
    log: Callable[[str], None] | None = None,
) -> int:
    resolved = resolve_format(in_tmux, fmt, in_popup, underlying_iterm, in_fzf, passthrough)
    # High-quality native iTerm2 inline image (truecolor, full res) over tmux.
    if resolved == "iterm_pt":
        return render_iterm_passthrough(path, cols, rows, log)
    # tmux sixel: capture bytes and enforce the payload ceiling by shrinking.
    if in_tmux and resolved in _SIXEL_FORMATS:
        return _render_sixel_capped(path, cols, rows, resolved, log)
    # All other paths: let chafa write directly to the terminal.
    cmd = _build_cmd(path, cols, rows, resolved)
    if log:
        log(f"chafa cmd: {' '.join(cmd)}")
    result = subprocess.run(cmd, stderr=subprocess.DEVNULL)
    return result.returncode


def format_info(metadata: dict) -> str:
    parts = [metadata.get("filename", "unknown")]
    for key in ("filesize", ):
        if key in metadata:
            parts.append(metadata[key])
    if "width" in metadata and "height" in metadata:
        parts.append(f"{metadata['width']}×{metadata['height']}")
    if "format" in metadata:
        parts.append(metadata["format"])
    if "mode" in metadata:
        parts.append(metadata["mode"])
    lines = ["  ".join(parts)]

    exif = metadata.get("exif", {})
    if exif:
        cam_parts = []
        for key in ("camera", "lens"):
            if key in exif:
                cam_parts.append(exif[key])

        settings = [exif[k] for k in ("focal_length", "aperture", "shutter", "iso") if k in exif]
        if settings:
            cam_parts.append(" · ".join(settings))

        if cam_parts:
            lines.append("  ".join(cam_parts))

        if "datetime" in exif:
            lines.append(exif["datetime"])

    return "\n".join(lines)
