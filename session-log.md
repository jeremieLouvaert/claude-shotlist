# Session log

## 2026-08-30 — Shot Prompts fork, first pass

**Done.**

- Read upstream in full (SKILL.md, report.py, frames.py, watch.py, tests,
  CHANGELOG). Baseline: 7 tests OK, 2 skipped for missing ffmpeg.
- Installed ffmpeg 9.0.1 (scoop) for fixture work — which exposed that
  upstream scene extraction is dead on ffmpeg ≥ 8 (`-vsync` removed).
  Fixed with `-fps_mode vfr` + legacy retry; the two skipped tests now run
  and pass. Logged in decisions.md.
- Schema designed and logged before code (decisions.md): `## Shot prompts`
  between Editorial profile and Quotable moments; `### Shot n — [MM:SS]
  `frame` (~Xs to next cut)` headings; `image_prompt` + `motion_note` as
  standard `<!-- pending Claude fill -->` markers; per-frame entries in
  scene mode, hero-only + note on uniform fallback, note on empty frames.
  Flag-off (`--no-shot-prompts`) verified **byte-identical** to the
  upstream emitter on the same payload (diff against
  `git show HEAD:scripts/report.py` output).
- Fixtures: `scripts/tests/fixtures/make_fixtures.py` generates four
  synthetic sub-30s clips with known cut structure (5-shot, 3-shot,
  static, 12-shot — the last clears watch.py's `uniform_fallback_min=10`).
  Binaries gitignored; generator committed.
- End-to-end through watch.py on fixtures, all exit 0: scene path (10
  entries on the 12-shot clip), uniform path (hero-only + note on
  static.mp4), flag-off (zero shot-prompt bytes).
- 5 new unit tests (schema only, fixed frame paths + transcript fixture,
  no video). Suite: **12/12 OK**.
- SKILL.md: v2-differently bullet, flag doc, Step 4 fill list (both
  fields, director-brief register), two failure-mode rows. CHANGELOG
  0.3.0.

**Wrong turns.** Ran the first e2e batch before regenerating fixtures
(cuts_12shots.mp4 didn't exist yet — the "File not found" was mine, not
the tool's). Detector jitter on synthetic solid-color cuts (4/5, 10/12
boundaries) — recorded as measured instrument behavior rather than
"fixed"; tests assert schema, not detector accuracy.

**Pending.**

- No real-video run yet: yt-dlp isn't installed here and no real local
  footage was at hand. The prompt-fill *quality* loop (Step 4 output on
  real frames, hand-edit distance) is unvalidated — synthetic color fields
  can't exercise it. First real reference clip is the next step.
- README not updated (CHANGELOG + SKILL.md are; README rewrite left for
  when the fork's identity/naming is decided).
- No decision yet on whether the fork keeps the `/watch` name or ships as
  a separate command; upstream plugin metadata untouched.


## 2026-08-30 — Identity pass: /watch → /shotlist

**Done.**

- Naming decided (Jérémie, via question): rename command + repo, README
  rewritten around the creative-direction use case. Name: **/shotlist**,
  repo **claude-shotlist**.
- Interface-level rename only — scripts/*.py byte-identical to 0.3.0
  (see decisions.md for the depth call and the compat surfaces kept:
  `~/.config/watch/.env`, `raw/watched/`, `$WATCH_VAULT_DIR` fallback).
- Touched: SKILL.md (frontmatter name/description/author, title, all
  command references, vault-var resolution, de-personalized "Taoufik's
  Second Brain" phrasing), commands/watch.md → commands/shotlist.md,
  .claude-plugin/{plugin,marketplace}.json, .codex-plugin/plugin.json
  (all 0.4.0), hooks/scripts/check-setup.sh status lines,
  scripts/build-skill.sh + release.yml (dist/shotlist.skill), README
  (full rewrite: per-shot brief lead, stills-then-motion pipeline,
  unpublished-install note, credits kept), AUTHORS.md (fork section),
  CHANGELOG 0.4.0.
- Verified: scripts/ untouched vs 0.3.0 (git diff empty for runtime
  files), 12/12 tests OK, JSON manifests parse.

**Pending (unchanged).**

- Real-video validation of prompt-fill quality — still the next
  substantive step; needs yt-dlp or real footage.
- GitHub publication: create the claude-shotlist repo, restore
  homepage/repository fields, replace README `<this-repo>` placeholders.


## 2026-08-30 — Real-video validation of Step-4 prompt fill

**Done.**

- Installed yt-dlp (scoop; node present for its JS runtime). No Whisper
  key on this machine → ran `--no-whisper`; native captions still pulled.
- Real run: Coleman "The Outside is Calling" (31s brand anthem,
  youtube.com/watch?v=AYrBZTHXGV8), intent "creative-direction reference:
  per-shot stills-then-motion brief". Pipeline end-to-end clean: 17
  scene-change shots (durations 1.0–5.7s, all with real `~Xs to next cut`
  figures), 20 hook frames, captions fetched, report emitted with 44
  pending markers. Uniform-fallback did NOT trigger — first confirmation
  of the scene path on real footage.
- Filled all 44 markers from the frames (17 image_prompt + 17
  motion_note + TL;DR/key moments/hook/profile/quotables/entities/
  concepts). 0 markers left; report UTF-8 clean. Workdir: session
  scratchpad `coleman-run/` (not committed — frames are third-party
  stills, report references local paths).

**Judgment — hand-edit distance (the thing this step existed to measure).**

- `image_prompt`: LOW. 512px frames carried enough signal (subject,
  composition, light direction, grade, even lens character via FPV blur /
  drone perspective) that the prompts are usable as-is for a stills
  generator; remaining edits are generator-specific style keywords, not
  content. No frame was too small to describe confidently.
- `motion_note`: MEDIUM, structurally. A still cannot show camera motion;
  notes are inferred from motion blur + perspective + neighbouring
  frames. On this clip (FPV/drone-heavy) inference was easy; on
  tripod/subtle-move footage the note would be a guess. This is a
  limitation of the input, not the schema.
- Two instrument observations: (1) the scene frame is grabbed at the cut,
  so shot 4's title card was caught mid-animation — `hook_frames/` had
  the settled version; (2) captions on a music-only ad are junk
  ("[Music] is / my days") — the quotables section needed an honest
  "none spoken" fill, which the schema absorbed fine.
- Both lessons folded into SKILL.md Step 4 (new sub-bullet under the
  shot-prompts fill spec). No runtime changes; scripts still byte-identical
  to 0.3.0. 12/12 tests OK.

**Pending.**

- GitHub publication (unchanged): create claude-shotlist repo, restore
  homepage/repository fields in SKILL.md + both plugin manifests, replace
  README `<this-repo>` placeholders, tag v0.4.0.
- Optional deeper validation: run a still from a filled image_prompt
  through an actual image generator and compare against the source frame
  — measures prompt fidelity, not just plausibility. Not done here (no
  generator wired into this environment).
