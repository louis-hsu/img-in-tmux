#!/usr/bin/env bash
# Run this INSIDE your iTerm2. It will test sixel/iterm both inside and outside tmux.
IMG="/Users/nshiu/Pictures/Manual_collection/CMU Snow/IMG_0020.JPG"

echo "================ ENV ================"
echo "TERM=$TERM  TMUX=${TMUX:-<none>}  TERM_PROGRAM=$TERM_PROGRAM"
echo

echo "================ TEST 1: chafa SIXEL (native, current context) ================"
echo "If blank -> sixel not rendering in this context"
chafa --format=sixel --size=40x30 "$IMG"
echo
echo "[press enter for next test]"; read _

echo "================ TEST 2: chafa ITERM protocol ================"
echo "iTerm2 native inline-image protocol"
chafa --format=iterm --size=40x30 "$IMG"
echo
echo "[press enter for next test]"; read _

echo "================ TEST 3: chafa SIXEL with tmux passthrough ================"
chafa --format=sixel --passthrough=tmux --size=40x30 "$IMG"
echo
echo "[press enter for next test]"; read _

echo "================ TEST 4: chafa ITERM with tmux passthrough ================"
chafa --format=iterm --passthrough=tmux --size=40x30 "$IMG"
echo
echo "================ DONE ================"
echo "Report which test numbers showed a real image."
