"""assemble.py — cut the generated remix clips into a film with the
reference's rhythm, plus a CMX3600 EDL for finishing in an NLE.

  python assemble.py <workdir> --clips <dir> [--out <file>] [--audio <bed>]

<workdir> holds the filled remix.md (shot order + per-shot durations).
--clips is where the generated videos live (ComfyUI's output/remix/, or a
folder of downloads) — clips are matched per shot by the "shotNN" token in
the filename, newest file wins. Each clip is trimmed FROM THE HEAD to its
shot's reference duration (the head is the locked first frame; the tail is
where the video model drifts), normalized to the first clip's resolution
and frame rate, and hard-cut in shot order. When a shot has no reference
duration (hero-only reports), the full clip is used.

Outputs, next to the remix: <workdir>/assembly/final.mp4 (override with
--out), <workdir>/assembly/final.edl (same cut as a CMX3600 EDL — imports
into Resolve/Premiere), and the trimmed per-shot parts in
<workdir>/assembly/parts/ for hand editing.

Audio: --audio <file> lays the bed under the cut (trimmed to the film);
without it the film is silent. Beat-matching stays human work.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}


def _err(msg: str) -> None:
    print(f"[assemble] {msg}", file=sys.stderr)
    sys.exit(1)


def _run(cmd: list) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        _err(f"command failed: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")


def parse_shots(remix_path: Path) -> list[dict]:
    sys.path.insert(0, str(Path(__file__).parent))
    import remix as remix_mod
    text = remix_path.read_text(encoding="utf-8")
    if remix_mod.PENDING_RE.search(text):
        _err("remix.md still has pending markers — finish the remix first")
    _meta, shots = remix_mod.parse_remix(text)
    return shots


def find_clip(clips_dir: Path, n: int) -> Path | None:
    token = f"shot{n:02d}"
    cands = [p for p in clips_dir.rglob("*")
             if p.suffix.lower() in VIDEO_EXTS and token in p.name.lower()]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def probe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
         "-show_format", str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        _err(f"ffprobe failed on {path}")
    d = json.loads(r.stdout)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    num, den = (v.get("r_frame_rate") or "24/1").split("/")
    fps = float(num) / float(den or 1)
    return {"w": int(v["width"]), "h": int(v["height"]), "fps": fps,
            "dur": float(d["format"].get("duration", 0))}


def tc(seconds: float, fps: float) -> str:
    f = int(round(seconds * fps))
    fi = int(round(fps))
    return (f"{f // (3600 * fi):02d}:{f // (60 * fi) % 60:02d}:"
            f"{f // fi % 60:02d}:{f % fi:02d}")


def write_edl(path: Path, events: list[dict], fps: float, title: str) -> None:
    lines = [f"TITLE: {title}", "FCM: NON-DROP FRAME", ""]
    for i, e in enumerate(events, 1):
        lines.append(
            f"{i:03d}  AX       V     C        "
            f"{tc(0, fps)} {tc(e['dur'], fps)} "
            f"{tc(e['rec_in'], fps)} {tc(e['rec_in'] + e['dur'], fps)}")
        lines.append(f"* FROM CLIP NAME: {e['name']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> None:
    ap = argparse.ArgumentParser(prog="assemble",
                                 description="cut generated remix clips to the reference's rhythm")
    ap.add_argument("workdir", help="directory holding the filled remix.md")
    ap.add_argument("--clips", required=True,
                    help="directory with the generated clips (searched recursively, shotNN in filename)")
    ap.add_argument("--out", default=None, help="output file (default <workdir>/assembly/final.mp4)")
    ap.add_argument("--audio", default=None, help="music bed to lay under the cut")
    args = ap.parse_args()

    workdir = Path(args.workdir)
    remix_path = workdir / "remix.md"
    if not remix_path.exists():
        _err(f"no remix.md in {workdir}")
    clips_dir = Path(args.clips)
    if not clips_dir.is_dir():
        _err(f"not a directory: {clips_dir}")

    shots = parse_shots(remix_path)
    outdir = Path(args.out).parent if args.out else workdir / "assembly"
    parts_dir = outdir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    out_file = Path(args.out) if args.out else outdir / "final.mp4"

    plan, missing = [], []
    for s in shots:
        clip = find_clip(clips_dir, s["n"])
        (plan if clip else missing).append((s, clip))
    if missing:
        print(f"[assemble] WARN: no clip found for shots "
              f"{[s['n'] for s, _ in missing]} — cutting without them", file=sys.stderr)
    if not plan:
        _err("no clips matched any shot")

    target = probe(plan[0][1])
    print(f"[assemble] target format: {target['w']}x{target['h']} @ {target['fps']:.3f}fps "
          f"(from {plan[0][1].name})")

    events, parts, rec = [], [], 0.0
    for s, clip in plan:
        info = probe(clip)
        dur = min(s["dur"], info["dur"]) if s.get("dur") else info["dur"]
        part = parts_dir / f"shot{s['n']:02d}.mp4"
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-t", f"{dur:.3f}",
               "-vf",
               f"scale={target['w']}:{target['h']}:force_original_aspect_ratio=decrease,"
               f"pad={target['w']}:{target['h']}:(ow-iw)/2:(oh-ih)/2,"
               f"fps={target['fps']:.5f},format=yuv420p",
               "-an", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
               str(part)]
        _run(cmd)
        parts.append(part)
        events.append({"name": clip.name, "dur": dur, "rec_in": rec})
        rec += dur
        print(f"[assemble] shot {s['n']:02d}: {clip.name} -> {dur:.2f}s")

    concat_list = outdir / "concat.txt"
    concat_list.write_text(
        "".join(f"file '{p.resolve().as_posix()}'\n" for p in parts),
        encoding="utf-8", newline="\n")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
           "-i", str(concat_list)]
    if args.audio:
        cmd += ["-i", args.audio, "-map", "0:v", "-map", "1:a",
                "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "copy", str(out_file)]
    _run(cmd)

    edl_file = out_file.with_suffix(".edl")
    write_edl(edl_file, events, target["fps"], out_file.stem)

    print(f"[assemble] film: {out_file} ({rec:.2f}s, {len(parts)} shots)")
    print(f"[assemble] EDL:  {edl_file} (import into Resolve/Premiere to finish by hand)")
    print(f"[assemble] parts: {parts_dir}")


if __name__ == "__main__":
    main()
