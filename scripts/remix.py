"""remix.py — turn a filled report.md into ComfyUI first/last-frame workflows.

Two phases:

  1. python remix.py <workdir> --brief "<transposition brief>" [--ar 16:9]
     Parses <workdir>/report.md's Shot prompts section and writes
     <workdir>/remix.md with three pending markers per shot
     (first_frame_prompt / last_frame_prompt / video_prompt) plus a global
     style_keeper marker. Claude fills them (same marker convention as
     report.md).

  2. python remix.py <workdir> --emit [--stills-engine nano|gpt]
                                      [--video-engine seedance|omni]
     Parses the filled remix.md and writes ONE combined workflow:
       <workdir>/comfy/remix_workflow.json    section A (stills): reference
                                              frame -> Nano Banana Pro AND
                                              gpt-image-2 per first/last (the
                                              non-chosen engine emitted muted);
                                              section B (video): picked stills ->
                                              Seedance first/last AND Gemini
                                              Video Omni (one muted) -> SaveVideo
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
GEMINI_W_MODEL = 1      # "gemini-3-pro-image-preview" (Nano Banana Pro)
GEMINI_W_ASPECT = 4     # "16:9"
GEMINI_W_SEED = 2
GPT_W_MODEL = 1         # "gpt-image-2"
GPT_W_WIDTH = 3
GPT_W_HEIGHT = 4
LOADIMAGE_W_FILE = 0
STRING_W_TEXT = 0
SAVEIMAGE_W_PREFIX = 0
SAVEVIDEO_W_PREFIX = 0
BYTEDANCE_W_MODEL = 0   # "Seedance 2.0" evidenced; 2.5 emitted on request
BYTEDANCE_W_SEED = 6
OMNI_W_SEED = 4

MODE_ACTIVE = 0
MODE_MUTED = 2          # litegraph "never" — toggle in the UI to switch engines

# 16:9-family custom sizes for gpt-image-2's Custom preset
GPT_SIZES = {"16:9": (2560, 1440), "9:16": (1440, 2560), "1:1": (2048, 2048),
             "4:3": (2304, 1728), "3:2": (2496, 1664), "21:9": (2688, 1152)}


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
        "_Fill every marker, then run `remix.py <workdir> --emit`.",
        "`first_frame_prompt` is an INSTRUCTION AGAINST THE REFERENCE FRAME",
        "(\"replace the horses with…\", \"reframe to 16:9 extending the",
        "landscape…\"). `last_frame_prompt` is an instruction against the",
        "APPROVED FIRST FRAME — the still you pick becomes its conditioning",
        "image, so describe only what changes by the end of the shot; that is",
        "what keeps subjects consistent within a shot. `video_prompt` drives",
        "the video model between the locked frames — motion, not look._",
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
                "instruction against the APPROVED FIRST FRAME (it is the "
                "conditioning image, not the reference): what moved, arrived or "
                "changed by the END of the shot; keep everything else identical"
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

    def add(self, kind: str, pos: list, widgets: dict | None = None,
            mode: int = MODE_ACTIVE) -> dict:
        n = copy.deepcopy(self.t[kind])
        self._id += 1
        n["id"] = self._id
        n["pos"] = list(pos)
        n["order"] = self._id
        n["mode"] = mode
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


ROW_H = 1960                     # vertical space per shot row (2 halves x 2 engines)
SCOL = [0, 460, 1080, 1720, 2360]   # stills: ref / prompt / gen / vault / save
VX = 3300                        # video section x offset
VCOL = [VX, VX + 460, VX + 1080, VX + 1720, VX + 2360]
HALF_DY = 980                    # first vs last half offset
ENG_DY = 460                     # engine A vs engine B offset within a half


def _vaulted(g: "Graph", gen: dict, out_name: str, prompt_node: dict,
             cond_imgs: list, xv: float, xs: float, y: float,
             mode: int) -> dict:
    """Wrap a generation node in the hash-vault caching triad
    (DeterministicHashVault -> HashVaultSave -> LazyAPISwitch), keyed on the
    prompt string plus the conditioning image(s). Returns the LazyAPISwitch
    whose final_output downstream savers should consume."""
    dhv = g.add("DeterministicHashVault", [xv, y], mode=mode)
    hvs = g.add("HashVaultSave", [xv, y + 170], mode=mode)
    las = g.add("LazyAPISwitch", [xs - 420, y + 60], mode=mode)
    g.link(prompt_node, "STRING", dhv, "payload_string")
    for i, img in enumerate(cond_imgs[:4]):
        g.link(img, "IMAGE", dhv, "any_input" if i == 0 else f"any_input_{i + 1}")
    g.link(dhv, "hash_key", hvs, "hash_key")
    g.link(gen, out_name, hvs, "api_output")
    g.link(dhv, "cached_data", las, "cached_data")
    g.link(dhv, "is_cached", las, "is_cached")
    g.link(hvs, "api_output", las, "api_data")
    return las


def build_combined(templates: dict, shots: list[dict], meta: dict,
                   stills_engine: str, video_engine: str,
                   seedance_model: str) -> dict:
    g = Graph(templates)
    aspect = meta.get("aspect_ratio", "16:9")
    style = meta.get("style_keeper", "")
    gw, gh = GPT_SIZES.get(aspect, GPT_SIZES["16:9"])
    n_rows = len(shots)

    for row, s in enumerate(shots):
        y = 120 + row * ROW_H
        nn = f"shot{s['n']:02d}"

        # ---- stills pass 1: FIRST frame from the reference; pass 2: LAST frame
        # conditioned on the APPROVED first frame (shotNN_first.png), so the
        # transposed subjects stay consistent within the shot.
        ref = g.add("LoadImage", [SCOL[0], y],
                    {LOADIMAGE_W_FILE: f"{nn}_ref{Path(s['frame']).suffix}"})
        approved_first = g.add("LoadImage", [SCOL[0], y + HALF_DY],
                               {LOADIMAGE_W_FILE: f"{nn}_first.png"})
        for half, (key, cond) in enumerate((("first", ref), ("last", approved_first))):
            hy = y + half * HALF_DY
            prompt_text = s[key] + (f"\n\nStyle: {style}" if style else "")
            p = g.add("PrimitiveStringMultiline", [SCOL[1], hy],
                      {STRING_W_TEXT: prompt_text})

            nano_mode = MODE_ACTIVE if stills_engine == "nano" else MODE_MUTED
            gpt_mode = MODE_ACTIVE if stills_engine == "gpt" else MODE_MUTED

            nano = g.add("GeminiImage2Node", [SCOL[2], hy],
                         {GEMINI_W_MODEL: "gemini-3-pro-image-preview",
                          GEMINI_W_ASPECT: aspect,
                          GEMINI_W_SEED: 1000 * s["n"] + half},
                         mode=nano_mode)
            g.link(cond, "IMAGE", nano, "images")
            g.link(p, "STRING", nano, "prompt")
            nano_out = _vaulted(g, nano, "IMAGE", p, [cond],
                                SCOL[3], SCOL[4], hy, nano_mode)
            nano_save = g.add("SaveImage", [SCOL[4], hy],
                              {SAVEIMAGE_W_PREFIX: f"remix/{nn}_{key}_nano"},
                              mode=nano_mode)
            g.link(nano_out, "final_output", nano_save, "images")

            gpt = g.add("OpenAIGPTImageNodeV2", [SCOL[2], hy + ENG_DY],
                        {GPT_W_WIDTH: gw, GPT_W_HEIGHT: gh},
                        mode=gpt_mode)
            g.link(cond, "IMAGE", gpt, "model.images.image_1")
            g.link(p, "STRING", gpt, "prompt")
            gpt_out = _vaulted(g, gpt, "IMAGE", p, [cond],
                               SCOL[3], SCOL[4], hy + ENG_DY, gpt_mode)
            gpt_save = g.add("SaveImage", [SCOL[4], hy + ENG_DY],
                             {SAVEIMAGE_W_PREFIX: f"remix/{nn}_{key}_gpt"},
                             mode=gpt_mode)
            g.link(gpt_out, "final_output", gpt_save, "images")

        g.group(f"Shot {s['n']} — STILLS: pass 1 first from ref, pass 2 last "
                f"from approved first (unmute one engine)",
                [SCOL[0] - 30, y - 60, SCOL[4] + 450, ROW_H - 80])

        # ---- video row: picked stills -> Seedance + Omni, one muted
        first = g.add("LoadImage", [VCOL[0], y], {LOADIMAGE_W_FILE: f"{nn}_first.png"})
        last = g.add("LoadImage", [VCOL[0], y + HALF_DY],
                     {LOADIMAGE_W_FILE: f"{nn}_last.png"})
        vp = g.add("StringConstantMultiline", [VCOL[1], y], {STRING_W_TEXT: s["video"]})

        sd_mode = MODE_ACTIVE if video_engine == "seedance" else MODE_MUTED
        omni_mode = MODE_ACTIVE if video_engine == "omni" else MODE_MUTED

        sd = g.add("ByteDance2FirstLastFrameNode", [VCOL[2], y],
                   {BYTEDANCE_W_MODEL: seedance_model, BYTEDANCE_W_SEED: s["n"]},
                   mode=sd_mode)
        g.link(first, "IMAGE", sd, "first_frame")
        g.link(last, "IMAGE", sd, "last_frame")
        g.link(vp, "STRING", sd, "model.prompt")
        sd_out = _vaulted(g, sd, "VIDEO", vp, [first, last],
                          VCOL[3], VCOL[4], y, sd_mode)
        sd_save = g.add("SaveVideo", [VCOL[4], y],
                        {SAVEVIDEO_W_PREFIX: f"remix/{nn}_seedance"}, mode=sd_mode)
        g.link(sd_out, "final_output", sd_save, "video")

        omni = g.add("GeminiVideoOmni", [VCOL[2], y + ENG_DY],
                     {OMNI_W_SEED: s["n"]}, mode=omni_mode)
        g.link(first, "IMAGE", omni, "model.images.image_1")
        g.link(last, "IMAGE", omni, "model.images.image_2")
        g.link(vp, "STRING", omni, "model.prompt")
        omni_out = _vaulted(g, omni, "VIDEO", vp, [first, last],
                            VCOL[3], VCOL[4], y + ENG_DY, omni_mode)
        omni_save = g.add("SaveVideo", [VCOL[4], y + ENG_DY],
                          {SAVEVIDEO_W_PREFIX: f"remix/{nn}_omni"}, mode=omni_mode)
        g.link(omni_out, "final_output", omni_save, "video")

        g.group(f"Shot {s['n']} — VIDEO first→last (unmute one engine)",
                [VCOL[0] - 30, y - 60, VCOL[4] + 450, ROW_H - 80])

    total_h = 120 + n_rows * ROW_H
    g.group("A — STILLS: generate first/last frames per shot",
            [SCOL[0] - 60, -40, SCOL[4] + 510, total_h])
    g.group("B — VIDEO: animate the picked stills",
            [VCOL[0] - 60, -40, VCOL[4] + 510, total_h])
    return g.dump()


def emit(workdir: Path, stills_engine: str = "nano", video_engine: str = "seedance",
         seedance_model: str = "Seedance 2.5") -> None:
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

    out = outdir / "remix_workflow.json"
    out.write_text(json.dumps(build_combined(templates, shots, meta,
                                             stills_engine, video_engine,
                                             seedance_model), indent=1),
                   encoding="utf-8", newline="\n")

    print(f"[remix] {len(shots)} shots -> one combined workflow")
    print(f"[remix] workflow: {out}")
    print(f"[remix] engines: stills={stills_engine} (other muted), "
          f"video={video_engine} (other muted) — toggle by muting/unmuting in the UI")
    print(f"[remix] reference frames: {indir} ({copied} copied)")
    print("[remix] next:")
    print("  1. copy comfy/input/* into ComfyUI's input folder, load remix_workflow.json")
    print("  2. run section A pass 1: FIRST frames generate from the references")
    print("  3. pick winners, rename to shotNN_first.png, drop in ComfyUI input")
    print("  4. run section A pass 2: LAST frames generate FROM the approved firsts (consistency)")
    print("  5. pick winners, rename to shotNN_last.png, drop in ComfyUI input")
    print("  6. run section B (VIDEO) — clips land in output/remix/")


def main() -> None:
    ap = argparse.ArgumentParser(prog="remix",
                                 description="report.md -> ComfyUI first/last-frame workflows")
    ap.add_argument("workdir", help="the /shotlist working directory (holds report.md)")
    ap.add_argument("--brief", help="transposition brief; writes remix.md with pending markers")
    ap.add_argument("--ar", default="16:9", help="target aspect ratio (default 16:9)")
    ap.add_argument("--emit", action="store_true",
                    help="parse the filled remix.md and write the ComfyUI workflow")
    ap.add_argument("--stills-engine", choices=["nano", "gpt"], default="nano",
                    help="active stills engine: nano (Nano Banana Pro) or gpt (gpt-image-2); the other is emitted muted")
    ap.add_argument("--video-engine", choices=["seedance", "omni"], default="seedance",
                    help="active video engine: seedance (ByteDance first/last) or omni (Gemini Video Omni); the other is emitted muted")
    ap.add_argument("--seedance-model", default="Seedance 2.5",
                    help='Seedance model widget value (default "Seedance 2.5"; only "Seedance 2.0" is evidenced in captures — pick in the UI if the dropdown rejects it)')
    args = ap.parse_args()
    workdir = Path(args.workdir)
    if not workdir.is_dir():
        _err(f"not a directory: {workdir}")
    if args.emit:
        emit(workdir, args.stills_engine, args.video_engine, args.seedance_model)
    elif args.brief:
        write_remix(workdir, args.brief, args.ar)
    else:
        _err("pass --brief \"...\" to create remix.md, or --emit to build the workflows")


if __name__ == "__main__":
    main()
