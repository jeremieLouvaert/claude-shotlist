"""remix.py — turn a filled report.md into ComfyUI first/last-frame workflows.

Two phases:

  1. python remix.py <workdir> --brief "<transposition brief>" [--ar 16:9]
     Parses <workdir>/report.md's Shot prompts section and writes
     <workdir>/remix.md with three pending markers per shot
     (first_frame_prompt / last_frame_prompt / video_prompt) plus a global
     style_keeper marker. Claude fills them (same marker convention as
     report.md).

  2. python remix.py <workdir> --emit
     Parses the filled remix.md and writes:
       <workdir>/comfy/stills_workflow.json   (per shot: reference frame ->
                                               GeminiImage2Node x2 -> SaveImage)
       <workdir>/comfy/video_workflow.json    (per shot: first/last stills ->
                                               ByteDance2FirstLastFrameNode ->
                                               SaveVideo)
       <workdir>/comfy/input/shotNN_ref.<ext> (reference frames, renamed for
                                               ComfyUI's input folder)

The node graphs are built from scripts/comfy_templates.json — verbatim node
instances captured from a real install (widgets_values order is undocumented
API surface; captured templates load, transcribed ones drift). The emitter
only substitutes prompt text, filenames, seeds, aspect ratio and positions.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
from pathlib import Path

PENDING_RE = re.compile(r"<!--\s*pending Claude fill:.*?-->", re.DOTALL)
TEMPLATES_PATH = Path(__file__).parent / "comfy_templates.json"

# widget indices, verified against the captured templates
GEMINI_W_ASPECT = 4     # "16:9"
GEMINI_W_SEED = 2
LOADIMAGE_W_FILE = 0
STRING_W_TEXT = 0
SAVEIMAGE_W_PREFIX = 0
SAVEVIDEO_W_PREFIX = 0
BYTEDANCE_W_SEED = 6


def _pending(hint: str) -> str:
    return f"<!-- pending Claude fill: {hint} -->"


def _err(msg: str) -> None:
    print(f"[remix] {msg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- report parse

SHOT_HEAD_RE = re.compile(
    r"^### Shot (\d+) — \[(\d+:\d+)\] `([^`]+)`(?: \(~([\d.]+)s to next cut\))?",
    re.M,
)


def parse_report_shots(report_text: str) -> list[dict]:
    """Extract shot entries (number, timestamp, frame file, duration,
    image_prompt, motion_note) from a filled report.md."""
    section = report_text.split("## Shot prompts", 1)
    if len(section) < 2:
        _err("report.md has no '## Shot prompts' section")
    body = section[1].split("\n## ", 1)[0]
    shots = []
    heads = list(SHOT_HEAD_RE.finditer(body))
    for i, m in enumerate(heads):
        chunk = body[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(body)]
        def field(name: str) -> str:
            fm = re.search(rf"\*\*{name}:\*\*\s*(.+?)(?=\n- \*\*|\n###|\n##|\Z)", chunk, re.DOTALL)
            return fm.group(1).strip() if fm else ""
        shots.append({
            "n": int(m.group(1)),
            "ts": m.group(2),
            "frame": m.group(3),
            "dur": float(m.group(4)) if m.group(4) else None,
            "image_prompt": field("image_prompt"),
            "motion_note": field("motion_note"),
        })
    if not shots:
        _err("no '### Shot' entries found under Shot prompts")
    unfilled = [s["n"] for s in shots if PENDING_RE.search(s["image_prompt"] + s["motion_note"])]
    if unfilled:
        _err(f"report.md shots still have pending markers: {unfilled} — fill report.md first")
    return shots


# ---------------------------------------------------------------- remix.md

def write_remix(workdir: Path, brief: str, aspect: str) -> Path:
    report = workdir / "report.md"
    if not report.exists():
        _err(f"no report.md in {workdir}")
    text = report.read_text(encoding="utf-8")
    title_m = re.search(r"^title: (.+)$", text, re.M)
    title = title_m.group(1).strip() if title_m else workdir.name
    shots = parse_report_shots(text)

    lines = [
        "---",
        f"source_report: {report}",
        f"title: {title}",
        f"brief: {brief}",
        f"aspect_ratio: {aspect}",
        f"shots: {len(shots)}",
        "---",
        "",
        f"# Remix — {title}",
        "",
        f"_Transposition brief: **{brief}**. Target aspect ratio: **{aspect}**._",
        "",
        "_Fill every marker, then run `remix.py <workdir> --emit`. Each shot's",
        "original frame is fed to the stills generator as image conditioning, so",
        "prompts are INSTRUCTIONS AGAINST THE REFERENCE (\"replace the horses",
        "with…\", \"reframe to 16:9 extending the landscape…\"), not from-scratch",
        "scene descriptions. `video_prompt` drives Seedance between the locked",
        "first and last frame — describe the motion, not the look._",
        "",
        "## Global style",
        "",
        "- **style_keeper:** " + _pending(
            "one reusable sentence naming the original's grade, light and lens "
            "character, appended to every first/last frame prompt so the "
            "transposed stills stay in one world"
        ),
        "",
        "## Shots",
        "",
    ]
    for s in shots:
        dur = f" (~{s['dur']}s in the original)" if s["dur"] else ""
        lines += [
            f"### Shot {s['n']} — [{s['ts']}] `{s['frame']}`{dur}",
            "",
            f"- **original_brief:** {s['image_prompt']}",
            f"- **original_motion:** {s['motion_note']}",
            "- **first_frame_prompt:** " + _pending(
                "instruction against the reference frame: what to replace/keep, "
                "transposed subject, target aspect reframe; opening state of the shot"
            ),
            "- **last_frame_prompt:** " + _pending(
                "same, but the state at the END of the shot — what moved, "
                "arrived or changed; keep world and grade identical to first_frame_prompt"
            ),
            "- **video_prompt:** " + _pending(
                "motion between the two locked frames for Seedance: camera move, "
                "subject action, pacing; respect the original shot's rhythm"
            ),
            "",
        ]
    out = workdir / "remix.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"[remix] wrote {out} ({len(shots)} shots, {3 * len(shots) + 1} markers)")
    print("[remix] fill every marker, then: python remix.py "
          f"\"{workdir}\" --emit")
    return out


# ---------------------------------------------------------------- remix parse

def parse_remix(remix_text: str) -> tuple[dict, list[dict]]:
    if PENDING_RE.search(remix_text):
        n = len(PENDING_RE.findall(remix_text))
        _err(f"remix.md still has {n} pending markers — fill them before --emit")
    meta = {}
    fm = re.search(r"\A---\n(.*?)\n---", remix_text, re.DOTALL)
    if fm:
        for line in fm.group(1).splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    style_m = re.search(r"\*\*style_keeper:\*\*\s*(.+?)(?=\n## |\n### |\Z)", remix_text, re.DOTALL)
    meta["style_keeper"] = style_m.group(1).strip() if style_m else ""
    shots = []
    heads = list(SHOT_HEAD_RE.finditer(remix_text))
    for i, m in enumerate(heads):
        chunk = remix_text[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(remix_text)]
        def field(name: str) -> str:
            fm2 = re.search(rf"\*\*{name}:\*\*\s*(.+?)(?=\n- \*\*|\n###|\n##|\Z)", chunk, re.DOTALL)
            return " ".join(fm2.group(1).split()) if fm2 else ""
        shots.append({
            "n": int(m.group(1)),
            "frame": m.group(3),
            "first": field("first_frame_prompt"),
            "last": field("last_frame_prompt"),
            "video": field("video_prompt"),
        })
    if not shots:
        _err("no '### Shot' entries in remix.md")
    empty = [s["n"] for s in shots if not (s["first"] and s["last"] and s["video"])]
    if empty:
        _err(f"shots with empty prompt fields: {empty}")
    return meta, shots


# ---------------------------------------------------------------- graph builder

class Graph:
    """Minimal litegraph builder over captured node templates."""

    def __init__(self, templates: dict):
        self.t = templates
        self.nodes: list[dict] = []
        self.links: list[list] = []
        self.groups: list[dict] = []
        self._id = 0
        self._link = 0

    def add(self, kind: str, pos: list, widgets: dict | None = None) -> dict:
        n = copy.deepcopy(self.t[kind])
        self._id += 1
        n["id"] = self._id
        n["pos"] = list(pos)
        n["order"] = self._id
        n["mode"] = 0
        for inp in n.get("inputs", []):
            inp["link"] = None
        for outp in n.get("outputs", []):
            outp["links"] = []
        if widgets:
            for idx, val in widgets.items():
                n["widgets_values"][idx] = val
        self.nodes.append(n)
        return n

    def link(self, src: dict, out_name: str, dst: dict, in_name: str) -> None:
        oi = next(i for i, o in enumerate(src["outputs"]) if o["name"] == out_name)
        ii = next(i for i, o in enumerate(dst["inputs"]) if o["name"] == in_name)
        self._link += 1
        ltype = src["outputs"][oi].get("type", "*")
        self.links.append([self._link, src["id"], oi, dst["id"], ii, ltype])
        src["outputs"][oi]["links"].append(self._link)
        dst["inputs"][ii]["link"] = self._link

    def group(self, title: str, bounding: list) -> None:
        self.groups.append({
            "id": len(self.groups) + 1,
            "title": title,
            "bounding": bounding,
            "color": "#3f789e",
            "font_size": 24,
            "flags": {},
        })

    def dump(self) -> dict:
        return {
            "id": "00000000-0000-0000-0000-000000000000",
            "revision": 0,
            "last_node_id": self._id,
            "last_link_id": self._link,
            "nodes": self.nodes,
            "links": self.links,
            "groups": self.groups,
            "config": {},
            "extra": {},
            "version": 0.4,
        }


ROW_H = 900          # vertical space per shot group
COL = [0, 460, 1080, 1700]  # x positions: ref/prompts, (gap), gen, save


def build_stills(templates: dict, shots: list[dict], meta: dict) -> dict:
    g = Graph(templates)
    aspect = meta.get("aspect_ratio", "16:9")
    style = meta.get("style_keeper", "")
    for row, s in enumerate(shots):
        y = 60 + row * ROW_H
        nn = f"shot{s['n']:02d}"
        ref = g.add("LoadImage", [COL[0], y],
                    {LOADIMAGE_W_FILE: f"{nn}_ref{Path(s['frame']).suffix}"})
        for half, (key, dy) in enumerate((("first", 0), ("last", 420))):
            prompt_text = s[key] + (f"\n\nStyle: {style}" if style else "")
            p = g.add("PrimitiveStringMultiline", [COL[1], y + dy],
                      {STRING_W_TEXT: prompt_text})
            gen = g.add("GeminiImage2Node", [COL[2], y + dy],
                        {GEMINI_W_ASPECT: aspect,
                         GEMINI_W_SEED: 1000 * s["n"] + half})
            save = g.add("SaveImage", [COL[3], y + dy],
                         {SAVEIMAGE_W_PREFIX: f"remix/{nn}_{key}"})
            g.link(ref, "IMAGE", gen, "images")
            g.link(p, "STRING", gen, "prompt")
            g.link(gen, "IMAGE", save, "images")
        g.group(f"Shot {s['n']} — first + last frame",
                [COL[0] - 30, y - 50, COL[3] + 420, ROW_H - 60])
    return g.dump()


def build_video(templates: dict, shots: list[dict], meta: dict) -> dict:
    g = Graph(templates)
    for row, s in enumerate(shots):
        y = 60 + row * ROW_H
        nn = f"shot{s['n']:02d}"
        first = g.add("LoadImage", [COL[0], y], {LOADIMAGE_W_FILE: f"{nn}_first.png"})
        last = g.add("LoadImage", [COL[0], y + 420], {LOADIMAGE_W_FILE: f"{nn}_last.png"})
        p = g.add("StringConstantMultiline", [COL[1], y], {STRING_W_TEXT: s["video"]})
        gen = g.add("ByteDance2FirstLastFrameNode", [COL[2], y],
                    {BYTEDANCE_W_SEED: s["n"]})
        save = g.add("SaveVideo", [COL[3], y], {SAVEVIDEO_W_PREFIX: f"remix/{nn}"})
        g.link(first, "IMAGE", gen, "first_frame")
        g.link(last, "IMAGE", gen, "last_frame")
        g.link(p, "STRING", gen, "model.prompt")
        g.link(gen, "VIDEO", save, "video")
        g.group(f"Shot {s['n']} — Seedance first→last",
                [COL[0] - 30, y - 50, COL[3] + 420, ROW_H - 60])
    return g.dump()


def emit(workdir: Path) -> None:
    remix = workdir / "remix.md"
    if not remix.exists():
        _err(f"no remix.md in {workdir} — run with --brief first")
    meta, shots = parse_remix(remix.read_text(encoding="utf-8"))
    templates = json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))

    outdir = workdir / "comfy"
    indir = outdir / "input"
    indir.mkdir(parents=True, exist_ok=True)

    frames_dir = workdir / "frames"
    copied = 0
    for s in shots:
        src = frames_dir / s["frame"]
        if src.exists():
            shutil.copyfile(src, indir / f"shot{s['n']:02d}_ref{src.suffix}")
            copied += 1
        else:
            print(f"[remix] WARN: reference frame missing: {src}", file=sys.stderr)

    stills = outdir / "stills_workflow.json"
    video = outdir / "video_workflow.json"
    stills.write_text(json.dumps(build_stills(templates, shots, meta), indent=1),
                      encoding="utf-8", newline="\n")
    video.write_text(json.dumps(build_video(templates, shots, meta), indent=1),
                     encoding="utf-8", newline="\n")

    print(f"[remix] {len(shots)} shots")
    print(f"[remix] stills workflow: {stills}")
    print(f"[remix] video workflow:  {video}")
    print(f"[remix] reference frames: {indir} ({copied} copied)")
    print("[remix] next:")
    print("  1. copy comfy/input/* into ComfyUI's input folder, load stills_workflow.json, run")
    print("  2. pick the winning first/last still per shot, rename to shotNN_first.png / shotNN_last.png,")
    print("     drop them in ComfyUI's input folder, load video_workflow.json, run")


def main() -> None:
    ap = argparse.ArgumentParser(prog="remix",
                                 description="report.md -> ComfyUI first/last-frame workflows")
    ap.add_argument("workdir", help="the /shotlist working directory (holds report.md)")
    ap.add_argument("--brief", help="transposition brief; writes remix.md with pending markers")
    ap.add_argument("--ar", default="16:9", help="target aspect ratio (default 16:9)")
    ap.add_argument("--emit", action="store_true",
                    help="parse the filled remix.md and write the ComfyUI workflows")
    args = ap.parse_args()
    workdir = Path(args.workdir)
    if not workdir.is_dir():
        _err(f"not a directory: {workdir}")
    if args.emit:
        emit(workdir)
    elif args.brief:
        write_remix(workdir, args.brief, args.ar)
    else:
        _err("pass --brief \"...\" to create remix.md, or --emit to build the workflows")


if __name__ == "__main__":
    main()
