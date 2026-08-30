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
