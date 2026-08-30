# Decisions — shot-prompts fork

Log of calls that override, extend, or interpret the upstream framework's
structure. Upstream: taoufik123-collab/claude-watch @ 7711231 (MIT), itself
based on bradautomates/claude-video (MIT).

## 2026-08-30 — Shot Prompts schema

**Placement.** `## Shot prompts` sits between `## Editorial profile` and
`## Quotable moments`. Rationale: it is derived from the same visual
evidence as the editorial profile, and inserting between two existing
sections (rather than appending) keeps the ingest-facing tail sections
(Entities / Concepts / Transcript / All frames) at their upstream
positions. The Obsidian ingest path reads sections by heading, not offset,
so the ride-along is safe either way.

**Granularity: shots require shots.** One entry per extracted frame *only
when sampling mode is scene-change* — in that mode every frame is a shot
boundary by construction (frame 0 + every `gt(scene,0.3)` hit). When
`extract_scene_change` fell back to uniform sampling (static/screen-recorded
source), per-shot prompts would be fiction: entries then cover **hero frames
only**, under an explicit italic note saying why. Empty frame list emits the
section with a note and no entries. Detection reuses watch.py's own check:
`frames[0].get("source") == "scene-change"`.

**Entry format.**

```
### Shot <n> — [MM:SS] `<frame filename>` (~<d>s to next cut)

- **image_prompt:** <!-- pending Claude fill: ... -->
- **motion_note:** <!-- pending Claude fill: ... -->
```

Field names `image_prompt` / `motion_note` exactly as specced. The
`~Xs to next cut` duration is computed deterministically (next frame's
timestamp, or video end for the last shot) and omitted when video duration
is unknown. Markers reuse the existing `_pending()` helper verbatim so the
Step-4 marker walk and the "unfilled markers" failure mode in SKILL.md
apply to the new section with zero changes.

**Flag semantics — an interpretation, logged.** The brief says both "a
first-class Shot Prompts section to every /watch run" (default ON,
`--no-shot-prompts` to opt out) and "behavior for anyone not using the new
flag stays byte-identical". Both cannot be literally true. Interpretation
taken: *existing sections' bytes and logic are untouched on every run, and
a run with `--no-shot-prompts` produces a report byte-identical to
upstream.* Verified by diffing `git show HEAD:scripts/report.py` output
against the new emitter with the flag off, same payload.

**No frontmatter change.** The section is discoverable by heading and by
its pending markers; adding a frontmatter key would change bytes for the
flag-off case (frontmatter is emitted unconditionally) or complicate the
byte-identity contract for no consumer that needs it today.

**API shape.** `write_report(..., include_shot_prompts: bool = True)` —
keyword arg with default True, so the one internal caller (watch.py) and
the upstream tests keep working unchanged; watch.py passes
`include_shot_prompts=not args.no_shot_prompts`.

**Fixtures are synthetic, not downloaded.** The 2–3 sub-30s reference clips
are generated locally with ffmpeg (`testsrc`/`smptebars`/solid color
concatenated with hard cuts at known timestamps), giving a *known* scene
count to assert against — no copyright exposure, no network, reproducible
by `scripts/tests/fixtures/make_fixtures.py`. Binary videos are not
committed; the generator is.

## 2026-08-30 — ffmpeg ≥ 8 compat fix in frames.py (upstream deviation)

Upstream `extract_scene_change` passes `-vsync vfr`, which ffmpeg removed
in v8 ("Unrecognized option 'vsync'") — scene extraction is dead on current
ffmpeg (verified against ffmpeg 9.0.1: the fixture run failed before the
fix, passed after). Changed to `-fps_mode vfr` with an automatic retry
using the legacy `-vsync vfr` when stderr says fps_mode is unknown
(ffmpeg < 5.1). Behavior-preserving; this is the one change inside
existing extraction logic, made because the feature cannot run at all
without it on a current install. The two ffmpeg-dependent upstream tests
went skip → pass with it.

## 2026-08-30 — fixture expectations are measured, not assumed

ffmpeg's scene detector at threshold 0.3 does not fire on every synthetic
hard cut (the 5×2s solid-color clip yields 4 boundaries, not 5; the 12-shot
clip yields 10 through the full watch.py path). Tests therefore assert the
report *schema* against fixed frame lists, and the fixture pipeline is
validated by running it and recording what the instrument actually returns
— per-cut detection accuracy is the detector's property, not this fork's,
and pinning exact detector output would make the tests break on ffmpeg
upgrades for reasons unrelated to the report logic.


## 2026-08-30 — Identity: /shotlist, interface-level only

**Call (Jérémie's, this session): the fork ships under its own name** —
command `/shotlist`, repo `claude-shotlist` — and the README is rewritten
around the creative-direction use case rather than staying additive. Upstream
`/watch` keeps its name and its story; this tool's story is the per-shot brief.

**Depth of the rename: interface, not runtime.** SKILL.md, `commands/`,
`.claude-plugin/`, `.codex-plugin/`, hook status lines, build artifact
(`dist/shotlist.skill`) and README carry the new identity. `scripts/*.py` are
byte-identical to 0.3.0 — `[watch]` stderr prefixes, `prog="watch"`,
`~/.config/watch/.env`, the `watch-` tempdir prefix and the `raw/watched/`
vault staging path all stay. Rationale: the 0.3.0 contract ("existing behavior
untouched") extends naturally to "runtime untouched by a naming pass"; config
and staging paths are compat surfaces users may already have; and keeping the
runtime diff against upstream at exactly one commit's worth of features makes
future upstream merges tractable. Cosmetic string renames inside scripts are
deferred until a functional change touches those files anyway.

**Vault env var:** `$SHOTLIST_VAULT_DIR` preferred, `$WATCH_VAULT_DIR` honored
as fallback — resolution is a SKILL.md instruction, not code, so the compat
shim costs one line.

**No invented URLs.** The fork has no published GitHub home yet, so
`homepage`/`repository` fields were removed from SKILL.md frontmatter and both
plugin manifests rather than pointed at upstream (misdirecting) or at a
guessed username (fiction). README install section says "not yet published"
and uses `<this-repo>` placeholders. To restore when the repo is created.

**Remote/folder:** `origin` renamed to `upstream` (we cannot push to
taoufik's repo); working folder renamed `CanvasCamp/claude-shotlist`.


## 2026-08-30 — Measured: letterboxed sources under-score scene detection

On a real 9:16 Instagram reel whose picture occupies a ~4:5 window inside
a black canvas (static caption overlay), ffmpeg's `gt(scene,0.3)` fired
zero times across ~9 true hard cuts. Measured directly on the downloaded
file: every cut scored 0.09–0.15, because the scene score is computed
over the whole frame and the unchanging letterbox + caption pixels
dilute it below threshold. The uniform fallback then engaged and the
report correctly declared hero-only prompts — documented degrade, wrong
diagnosis in the emitted note ("static or screen-recorded source").

Recorded as instrument behavior, not fixed. Candidate for 0.5.0:
detect letterbox (ffmpeg `cropdetect`) and crop before scene scoring,
and/or soften the fallback note to name letterboxing as a possible
cause. Threshold tuning alone is the wrong fix — 0.3 is fine on
full-frame sources, and lowering it globally would over-fire elsewhere.

## 2026-08-30 — Usage note: cosmos.so saves resolve via their og-metadata

cosmos.so element URLs have no yt-dlp extractor (generic extractor
errors out). The element page's own og/meta block names the original
post URL (e.g. an Instagram reel), which the pipeline handles normally.
Until a pre-resolver exists, the operator hop is: fetch the cosmos page,
read the original-post URL from its metadata, run /shotlist on that.
Candidate for 0.5.0: a docs line in SKILL.md's failure-modes table, or a
small resolver in download.py for known moodboard hosts.


## 2026-08-30 — Remix stage (0.5.0): report → ComfyUI first/last-frame workflows

**The feature.** A filled `report.md` plus a transposition brief ("horses →
Land Rover, CanvasCamp × Patagonia people, 16:9, keep the grade") becomes
two loadable ComfyUI workflows: a stills graph that generates a first and
last frame per shot, and a video graph that animates each first/last pair.
The creative transposition is Claude's fill; the graphs are deterministic
emitter output. Nobody hand-wires 25 shots of nodes.

**Two-artifact flow, same marker mechanism as report.md.**
`scripts/remix.py <workdir> --brief "…"` parses the report's Shot prompts
section and writes `remix.md` with three pending markers per shot
(`first_frame_prompt`, `last_frame_prompt`, `video_prompt`) plus one global
`style_keeper` marker, reusing the exact `<!-- pending Claude fill: … -->`
convention so SKILL.md's marker walk and failure modes apply unchanged.
After the fill, `scripts/remix.py <workdir> --emit` parses remix.md and
writes `comfy/stills_workflow.json`, `comfy/video_workflow.json`, and
`comfy/input/shotNN_ref.jpg` (reference frames copied and renamed for
ComfyUI's input folder).

**Node stack is measured, not invented.** The graphs target the nodes in
Jérémie's actual install, read from the litegraph JSON embedded in his own
ComfyUI output PNGs (Downloads + Desktop, 2026-08-30): `GeminiImage2Node`
(Nano Banana 2 / Gemini 3.1 Flash Image, 2K, aspect-ratio widget,
reference-image conditioning) for stills; `ByteDance2FirstLastFrameNode`
(Seedance 2.0, 1080p, first_frame/last_frame image links, prompt link) →
`SaveVideo` for video; `PrimitiveStringMultiline` / `StringConstantMultiline`
for prompts; `LoadImage`/`SaveImage`. Templates for all seven node types are
committed verbatim in `scripts/comfy_templates.json` — real instances with
their `widgets_values` ordering intact (the part a hand-written graph gets
wrong), scrubbed of creative prompt text and filenames. Emitting from
captured templates instead of authored node specs is the load-bearing call:
widget order is undocumented API-surface and drifts per node-pack version;
capture beats transcription.

**Restyle-from-reference (Jérémie's call, this session).** Each shot's
original frame enters the Gemini node as image conditioning with the
transposed prompt as instruction — composition, light and grade carry over
structurally instead of being re-described. This matches how the existing
stills workflow already uses the node ("Modify lighting to …" over
reference images).

**What the emitter does NOT decide.** Seedance duration stays at the
template default (8s) rather than being derived from the report's
`~Xs to next cut` figures — the allowed duration values are not evidenced,
and remix shots are re-timed by intent anyway; the real shot length is
carried into `remix.md` for hand-tuning. The video graph's `LoadImage`
widgets point at `shotNN_first.png` / `shotNN_last.png` placeholder names:
picking WHICH generated still wins is a human step, so the contract is
"rename your picks to these names and drop them in ComfyUI's input folder"
rather than pretending the pipeline is pickless.

**Runtime contract.** `remix.py` + `comfy_templates.json` are additive
files; every pre-existing script stays byte-identical to 0.4.0. Tests
assert remix.md schema and workflow-graph integrity (unique ids, every
link's endpoints exist with correct slot indices, per-shot node counts) —
not pixel output, which only a live ComfyUI can prove.


## 2026-08-30 — Remix revisions from the first live ComfyUI test

**Consistency chaining (Jérémie's finding, first real run).** Generating
first and last frames independently from the same reference makes the
model invent the transposed subject twice — the Defenders didn't match
across the pair. Fix: stills become two passes. Pass 1 generates the
FIRST frame from the reference; the user approves a pick
(`shotNN_first.png`); pass 2 generates the LAST frame **conditioned on
the approved first frame**, with `last_frame_prompt` redefined as a
delta instruction ("what changed by the end of the shot"). The human
approval gate between passes is load-bearing, not overhead — chaining
from an unapproved frame would propagate a bad pick into everything
downstream.

**One combined workflow, dual engines, mute-to-choose.** Sections A
(stills) and B (video) in one litegraph file. Per stage both engines are
emitted — stills: Nano Banana Pro (`gemini-3-pro-image-preview`) and
`gpt-image-2`; video: Seedance (`ByteDance2FirstLastFrameNode`) and
`GeminiVideoOmni` (first→image_1, last→image_2) — with the non-chosen
engine muted (litegraph mode 2). Engine switching is a UI mute-toggle,
not a re-emit. `"Seedance 2.5"` is emitted per Jérémie's stated use;
only `"Seedance 2.0"` is evidenced in captures — flagged in SKILL.md.

**Hash-vault caching on every generation branch (Jérémie's request).**
The triad from his own workflows, wiring read from the capture:
prompt → `DeterministicHashVault.payload_string`; DHV.hash_key →
`HashVaultSave.hash_key`; gen output → HVS.api_output; DHV.cached_data +
DHV.is_cached + HVS.api_output → `LazyAPISwitch`; savers consume
LAS.final_output. One deviation from the evidenced usage: conditioning
images are wired into DHV's `any_input` slots so the cache key includes
them — his instances key on the prompt alone, which would serve stale
results when a re-picked first frame reuses an unchanged last-frame
prompt. This wiring is UNVERIFIED against a live run; if the node can't
hash image tensors, unplug the any_input links and fall back to
prompt-only keys.


## 2026-08-30 — Wireless chaining replaces the file round-trip (Jérémie's call)

The pick-and-rename gate (`shotNN_first.png` via LoadImage) is replaced by
his Wireless pattern, wiring read from the captures: every generation
branch's `LazyAPISwitch.final_output` → `WirelessSend` on channel
`shotNN_first` / `shotNN_last`; the last-frame generators and the video
section consume via `WirelessGet` on the same channels. One queue run now
produces firsts → lasts → videos end-to-end; LoadImage survives only for
the reference frames. Stills still reach disk through the send's
passthrough → SaveImage (his own passthrough→Preview pattern, with Save in
place of Preview).

**Trade, made explicitly:** the human approval gate between passes is
gone — the last frame chains from whatever pass 1 produced. Curation
moves to re-queueing: tweak the offending branch's prompt or seed and run
again; the hash vault serves every unchanged branch from cache, so a redo
costs one API call, not a re-run of the film.

**Channel semantics:** both engines of a stage send on the same channel
so the wireless chain survives engine switching without re-emitting — the
muted engine never fires. Corollary, documented in SKILL.md: exactly one
stills engine may be unmuted per run; unmuting both makes the channel
value nondeterministic.

**Instrument note:** the first emit crashed on a StopIteration — the
conditioning loop in `_vaulted` shadowed the `out_name` parameter, so the
gen→HashVaultSave link asked GeminiImage2Node for a "value" output. The
graph-integrity tests caught it before any workflow shipped; loop
variable renamed.
