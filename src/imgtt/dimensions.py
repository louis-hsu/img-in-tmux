import os
import subprocess
import sys


def get_terminal_size() -> tuple[int, int]:
    if "TMUX" in os.environ:
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

    try:
        size = os.get_terminal_size(sys.stderr.fileno())
        return size.columns, size.lines
    except (AttributeError, ValueError, OSError):
        pass

    return 80, 24
