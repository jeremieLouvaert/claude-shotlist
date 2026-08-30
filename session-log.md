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
