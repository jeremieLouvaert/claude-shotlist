#!/usr/bin/env python3
"""Generate the synthetic reference clips the shot-prompts work is tested on.

Three clips, all under 30s, with *known* hard-cut structure so scene-change
extraction has a predictable right answer:

  cuts_5shots.mp4   — 10s, five 2s shots (solid colors, hard cuts at
                      2/4/6/8s). Expected scene-change frames: 5
                      (frame 0 + 4 cuts).
  cuts_3shots.mp4   — 15s, three 5s shots (testsrc, smptebars, solid
                      color). Expected scene-change frames: 3.
  static.mp4        — 20s single solid color, no cuts. Expected: scene
                      extraction falls back to uniform sampling.
  cuts_12shots.mp4  — 24s, twelve 2s solid-color shots. Enough cuts to
                      clear watch.py's uniform_fallback_min=10, so a full
                      watch.py run stays on the scene-change path.

Videos are generated, not downloaded — reproducible, no copyright, no
network. Not committed to git; run this script to (re)create them here.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg failed ({' '.join(cmd[:6])}…): {result.stderr.strip()}")


def _solid(color: str, seconds: float, out: Path) -> None:
    _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c={color}:s=320x180:r=10:d={seconds}",
        "-pix_fmt", "yuv420p", str(out),
    ])


def _pattern(src: str, seconds: float, out: Path) -> None:
    _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"{src}=s=320x180:r=10:d={seconds}",
        "-pix_fmt", "yuv420p", str(out),
    ])


def _concat(parts: list[Path], out: Path) -> None:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c", "copy", str(out),
    ])
    lst.unlink()
    for p in parts:
        p.unlink()


def main() -> int:
    if shutil.which("ffmpeg") is None:
        print("ffmpeg not installed — cannot generate fixtures", file=sys.stderr)
        return 2

    # cuts_5shots.mp4 — five 2s solid-color shots
    colors = ["red", "green", "blue", "yellow", "magenta"]
    parts = []
    for i, c in enumerate(colors):
        p = HERE / f"_part5_{i}.mp4"
        _solid(c, 2.0, p)
        parts.append(p)
    _concat(parts, HERE / "cuts_5shots.mp4")

    # cuts_3shots.mp4 — three 5s shots with different generators
    parts = []
    p = HERE / "_part3_0.mp4"; _pattern("testsrc", 5.0, p); parts.append(p)
    p = HERE / "_part3_1.mp4"; _pattern("smptebars", 5.0, p); parts.append(p)
    p = HERE / "_part3_2.mp4"; _solid("darkslategray", 5.0, p); parts.append(p)
    _concat(parts, HERE / "cuts_3shots.mp4")

    # static.mp4 — one 20s shot, no cuts
    _solid("navy", 20.0, HERE / "static.mp4")

    # cuts_12shots.mp4 — twelve 2s solid-color shots
    palette = ["red", "green", "blue", "yellow", "magenta", "cyan",
               "orange", "purple", "white", "gray", "brown", "pink"]
    parts = []
    for i, c in enumerate(palette):
        p = HERE / f"_part12_{i}.mp4"
        _solid(c, 2.0, p)
        parts.append(p)
    _concat(parts, HERE / "cuts_12shots.mp4")

    for name in ("cuts_5shots.mp4", "cuts_3shots.mp4", "static.mp4", "cuts_12shots.mp4"):
        print(HERE / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
