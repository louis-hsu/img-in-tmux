import argparse
import os
import sys
from pathlib import Path
from typing import TextIO

from imgtt.dimensions import get_terminal_size
from imgtt.metadata import get_metadata
from imgtt.renderer import (
    check_chafa,
    format_info,
    render_image,
    resolve_format,
)


def _dbg(msg: str, out: TextIO | None) -> None:
    if out is not None:
        print(f"[imgtt] {msg}", file=out, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Show image in terminal with media info")
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        default=None,
        help="Image file to display",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=70,
        metavar="PCT",
        help="Preview size as %% of terminal dimensions (default: 70)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Write debug info to stderr",
    )
    parser.add_argument(
        "--debug-file",
        metavar="LOGFILE",
        default=None,
        help="Write debug info to LOGFILE (created/overwritten)",
    )
    parser.add_argument(
        "--info-only",
        action="store_true",
        help="Print metadata only, skip image rendering",
    )
    parser.add_argument(
        "--size-probe",
        action="store_true",
        help="Print detected terminal/pane size and exit",
    )
    parser.add_argument(
        "--format",
        metavar="FMT",
        default=None,
        help="Force chafa output format: sixel, symbols, kitty, iterm (overrides auto-detect)",
    )
    args = parser.parse_args()

    debug_handle = None
    try:
        debug_out: TextIO | None = None
        if args.debug_file is not None:
            debug_handle = open(args.debug_file, "w")
            debug_out = debug_handle
        elif args.debug:
            debug_out = sys.stderr

        in_tmux = "TMUX" in os.environ
        term_cols, term_rows = get_terminal_size()

        if args.size_probe:
            print(f"terminal: {term_cols}x{term_rows}")
            print(f"tmux: {'yes' if in_tmux else 'no'}")
            return

        if args.file is None:
            parser.error("file is required")

        _dbg(f"tmux detected: {'yes' if in_tmux else 'no'}", debug_out)
        _dbg(f"pane size: {term_cols}x{term_rows}", debug_out)

        img_cols = max(1, int(term_cols * args.size / 100))
        img_rows = max(1, int(term_rows * args.size / 100))
        _dbg(f"render size: {img_cols}x{img_rows} ({args.size}%)", debug_out)

        if not check_chafa():
            print("Error: chafa not found. Install: brew install chafa", file=sys.stderr)
            sys.exit(1)

        if not args.file.exists():
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            sys.exit(1)

        if not args.file.is_file():
            print(f"Error: not a file: {args.file}", file=sys.stderr)
            sys.exit(1)

        metadata = get_metadata(args.file)
        # get_metadata swallows decode errors; absence of "format" means Pillow
        # could not open it (0-byte, truncated, or non-image). Fail cleanly.
        if "format" not in metadata:
            print(f"Error: not a valid image: {args.file}", file=sys.stderr)
            sys.exit(1)
        exif = metadata.get("exif", {})
        _dbg(f"exif found: {'yes' if exif else 'no'} ({len(exif)} fields)", debug_out)

        if not args.info_only:
            resolved = resolve_format(in_tmux, args.format)
            _dbg(f"format: {resolved} (tmux={in_tmux}, override={args.format})", debug_out)
            chafa_exit = render_image(
                args.file,
                img_cols,
                img_rows,
                in_tmux=in_tmux,
                fmt=args.format,
                log=(lambda m: _dbg(m, debug_out)) if debug_out is not None else None,
            )
            _dbg(f"chafa exit: {chafa_exit}", debug_out)

        print(format_info(metadata))

    finally:
        if debug_handle is not None:
            debug_handle.close()


if __name__ == "__main__":
    main()
