# imgtt

Display an image in your terminal alongside its media info (dimensions, format, and camera EXIF). Built for tmux, where it uses native sixel graphics that survive pane redraws.

## Features

- **Inline image preview** via [chafa](https://hpjansson.org/chafa/) — sixel in tmux, auto-detected best protocol elsewhere.
- **Media info** — filename, file size, dimensions, format, color mode.
- **Camera EXIF** — body, lens, focal length, aperture, shutter, ISO, capture time (when present).
- **tmux-aware sizing** — detects pane/fzf-preview dimensions and fits the image to them.
- **tmux sixel payload cap** — tmux silently drops sixels above a byte ceiling; imgtt limits colors and shrinks the render until the payload fits, so large/detailed images still display.

## Requirements

- Python ≥ 3.11
- [chafa](https://hpjansson.org/chafa/) (`brew install chafa`)
- A terminal with sixel support for in-tmux graphics (e.g. iTerm2, WezTerm, foot, xterm built with sixel)

## Install

Using [uv](https://docs.astral.sh/uv/):

```bash
uv tool install --force --reinstall .
```

This installs the `imgtt` executable to `~/.local/bin`. Ensure it is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Run without installing:

```bash
uv run imgtt <image>
```

## Usage

```bash
imgtt photo.jpg
```

```
options:
  --size PCT            Preview size as % of terminal dimensions (default: 70)
  --info-only          Print metadata only, skip image rendering
  --format FMT         Force chafa output format: sixel, symbols, kitty, iterm
  --size-probe         Print detected terminal/pane size and exit
  --debug              Write debug info to stderr
  --debug-file LOGFILE Write debug info to LOGFILE
```

### fzf preview

Browse a directory of images with live previews:

```bash
print -l -- *.JPG | fzf --preview 'imgtt {}'
```

> Use `print -l` or `find` (not `ls`) so colorized output does not pollute the filename passed to the preview.

## Environment

| Variable | Effect |
| --- | --- |
| `IMGTT_SIXEL_MAX_BYTES` | Override the tmux sixel payload ceiling (default `1300000`). |

## Development

```bash
uv run pytest -q
```

## License

MIT
