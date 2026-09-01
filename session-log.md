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


## 2026-08-30 — Publication prep (outbound blocked, handed to Jérémie)

**Done.**

- Restored `homepage`/`repository` (github.com/jeremieLouvaert/claude-shotlist)
  in SKILL.md frontmatter, `.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`; replaced
  README `<this-repo>` placeholders and dropped the "not yet published" note.
  Manifests re-parsed OK. Commit 3c903f0.
- Renamed branch `shot-prompts` → `main` (stale local `main` was just
  upstream's tip 7711231; deleted, recoverable via `upstream/main`).
- Tagged `v0.4.0` (annotated). Pushing the tag triggers release.yml →
  builds and attaches `dist/shotlist.skill`.

**Blocked — by design.** The CanvasCamp-root guardrail hook rejects GitHub
mutations from an agent shell (outbound is Jérémie's to run). Commands to
finish, from `claude-shotlist/`:

```
gh repo create claude-shotlist --public --source . --remote origin --push --description "Turn a reference video into a per-shot generation brief: one image prompt + one motion note per detected cut. Fork of taoufik123-collab/claude-watch."
git push origin v0.4.0
```

Then verify: release appears with `dist/shotlist.skill` attached, README
renders, clone-install path works.


## 2026-08-30 — Published; bundle-strip bug found and fixed

**Done.**

- Jérémie ran the outbound pair; verified from running: repo public,
  `main` = local tip, release v0.4.0 green with `shotlist.skill`
  attached — downloaded and unzipped the asset to confirm layout.
- Adding the requested exclude list (decisions.md, session-log.md,
  `.codex-plugin/`) exposed that **`zip -d` was a silent no-op wherever
  Info-ZIP isn't installed** — `|| true` swallowed the missing binary, so
  a local build shipped *every* excluded path while exiting green (the
  Actions build only worked because ubuntu has `zip`). The
  green-without-measuring failure mode, again.
- Rewrote the strip in Python (`zipfile`), preserving the git-archive
  commit comment, with a post-strip assertion that no excluded entry
  survives and a loud error when no python is found. Rebuilt locally:
  17 files, excluded paths gone. Commits 7c59f95 + d03007b.

**Pending.**

- `main` is 2 commits ahead of origin — the push is Jérémie's
  (guardrail). Next tag (v0.4.1 or later) will carry the leaner bundle;
  the v0.4.0 release asset stays as built (21 files, includes the
  working record — public in the repo anyway, not worth a re-release).
- Optional: prompt-fidelity check (generate from an image_prompt,
  compare to source frame) — needs an image generator.

## 2026-08-30 — Install-path test: fresh clone, real run on CanvasCamp's own footage

**Done.** Cloned the published repo (origin tip 8373418) into scratchpad and ran
it as a user would: CanvasCamp's "Bell Tent Fly: How to set up the All Purpose
Fly" (103s, youtube lKX6J8NRasg). Pipeline clean: 25 scene-change shots, 20 hook
frames, 60 markers emitted and all filled; 0 left, UTF-8 clean. New paths
exercised vs the Coleman run: 1-3min budget tier, no-captions degrade (silent
video — overlays carry the steps), long-tail shots (19.3s and 17.2s uncut).

**Observed.** (1) Numbered step overlays land mid-shot, so scene sampling caught
steps 1/4/7-10 but skipped 2-3/5-6 — text-overlay tutorials shed information
that cut-aligned sampling can't see; noted honestly in the report's quotables.
(2) The 17s closing shot is briefed only to its first beat — a still can't
evidence how an uncut tail resolves; marked unverified in the motion_note.
Workdir: watch-g4n8z01h (temp, not committed).


## 2026-08-30 — Hands-on test via the Skill path: cosmos.so save → Instagram reel

**Done.** First run through the real skill mechanism (installed at
`~/.claude/skills/shotlist`, invoked as /shotlist in a live session) on a
video Jérémie threw in: a cosmos.so moodboard save
(cosmos.so/e/1550931937). Report filled 19/19 markers and staged with
relative frame links at
`CanvasCamp-Brain/raw/watched/antonhugo-horse-trek-reel-2026-08-30/`.

**Findings (both candidate 0.5.0 items, logged in decisions.md).**

1. **cosmos.so is not a supported source** — yt-dlp's generic extractor
   fails on it. The element page's og-metadata names the original post
   (here an Instagram reel URL, which ran clean). Resolution is a manual
   hop today; a docs line in SKILL.md's failure-modes table (or a small
   pre-resolver) would make moodboard saves first-class inputs.
2. **Letterboxed reels defeat scene-change detection** — measured, not
   inferred: the 11s reel has ~9 real cuts, every one scoring 0.09–0.15
   against the 0.3 threshold, because the unchanging black canvas +
   static caption dilute ffmpeg's whole-frame scene score. The tool
   degraded exactly as documented (uniform fallback, hero-only prompts,
   note emitted) — correct behavior, blind rule. Candidate fix:
   auto-crop detection before scene scoring.

**Also observed.** Vault auto-detect misses `CanvasCamp-Brain` (not on
the candidate list); `SHOTLIST_VAULT_DIR` suggested to Jérémie. Both
vault stagings so far were manual copies with paths rewritten relative —
which is what Step 4.4 does anyway.


## 2026-08-30 — 0.5.0: Remix stage built and exercised end-to-end

**Done.** `scripts/remix.py` + `scripts/comfy_templates.json` (schema logged
in decisions.md before code). Node stack grounded by reading the litegraph
JSON embedded in Jérémie's own ComfyUI output PNGs (Downloads + Desktop):
GeminiImage2Node stills with reference-image conditioning,
ByteDance2FirstLastFrameNode (Seedance 2.0) video, seven templates captured
verbatim and scrubbed. Jérémie's calls: Seedance runs in his ComfyUI;
restyle-from-reference conditioning. 18/18 tests; pre-existing scripts
byte-identical to 0.4.0. SKILL.md Step 6 + failure rows; CHANGELOG;
manifests at 0.5.0. Installed clone at `~/.claude/skills/shotlist` pulled
to the same commit.

**Exercised live** on the antonhugo horse-trek report with the real brief
(horses → Land Rover Defenders, CanvasCamp × Patagonia people, Kyrgyz
landscape, 16:9, keep the grade): 16/16 remix markers filled, emit produced
a 35-node stills graph + 25-node video graph, both passing integrity
checks (unique ids, link endpoint/slot correctness). NOT yet loaded into a
live ComfyUI — the one verification only Jérémie's install can provide.

**Pending.** Jérémie loads both workflows in ComfyUI (load success +
generation quality = the real gate); push (now 6 commits ahead); tag
v0.5.0 when validated; letterbox cropdetect + cosmos resolver still open
0.5.x candidates.


## 2026-08-30 — 0.5.0 validated live in ComfyUI; ready to publish

**Done.** The full remix chain ran clean in Jérémie's ComfyUI (local
portable, F: drive, 0.34.2): stills generated, wireless chaining held,
and after the Seedance 2.5 widget fix the video section ran too —
"it works!". Iterations this session, each from a live test error:
consistency chaining (last from generated first), hash-vault caching,
wireless channels replacing file round-trips, overlap-free layout from
measured node sizes with colored sections, and the Seedance 2.5 layout
taken from the running server's `/object_info` (the schema authority
captures can't be — logged in decisions.md and cross-session memory).
`--comfy-input` now copies refs straight into ComfyUI's input.

**State.** 22/22 tests. CHANGELOG 0.5.0 finalized; v0.5.0 tagged at this
commit. Push is Jérémie's: `git push origin main` + `git push origin
v0.5.0` (tag push triggers the release build). Installed clone at
`~/.claude/skills/shotlist` synced.

**Open.** Letterbox cropdetect + cosmos.so resolver (0.5.x candidates);
prompt-fidelity check now cheap to run — the stills exist, compare
against reference frames when Jérémie wants it.


## 2026-08-30 — 0.6.0: assemble + fidelity + presets, tested on the real run

**Done.** `assemble.py` (head-trim to reference rhythm, concat, CMX3600
EDL, parts/ for hand editing) — smoke-tested on the real shot01 Seedance
clip (5.06s one-shot cut + EDL emitted). `remix.py --fidelity` pair
listing — run on the real outputs; shot 1 verdict PASS: the
wireless-chained last frame kept vehicles, loads and light consistent
with the first (the consistency fix observed working on production
output). `canvascamp` preset seeded at `CanvasCamp-Brain/remix-presets.md`
(Draft, pre-OQ-015); SKILL.md preset resolution + Step 7. Env vars
`SHOTLIST_VAULT_DIR` and `SHOTLIST_COMFY_INPUT` set user-level. 26/26
tests. Manifests 0.6.0; v0.6.0 tagged.

**Pending.** Jérémie: `git push origin main` + `git push origin v0.6.0`.
Remotion tokens-driven graphics pass parked until OQ-015.


## 2026-09-01 — Omni Flash 1.1 re-check: real mismatch, fixed pre-push

**Done.** The flagged Omni tension checked against the running server's
`/object_info` (0.34.2) and confirmed as a real defect in the tagged-but-
unpushed v0.6.0: "Omni Flash 1.1" doesn't exist on the emitted v1
`GeminiVideoOmni` node — only on `GeminiVideoOmniV2`, with a different
sub-widget layout per model key. Migrated the omni branch to V2 (per-key
widget lists from /object_info, unevidenced keys refuse loudly,
task_type=image_to_video explicit, 1080p for Seedance parity). Two more
defects found and fixed in the same pass: `--omni-model` was silently
dropped between `emit()` and the graph builder, and the test suite was
copying 8-byte fixture JPGs over the REAL horse-trek reference frames in
ComfyUI's input folder via `$SHOTLIST_COMFY_INPUT` (refs restored
byte-identical from the workdir; setUp now strips the var). Details in
decisions.md. 29/29 tests. Comfy Cloud MCP authenticated this session.

**Pending.** Push is Jérémie's; recommended shape (nothing is public yet):
`git tag -f v0.6.0 && git push origin main && git push origin v0.6.0` so
one clean 0.6.0 ships — CHANGELOG is written for that path. If v0.6.0 is
pushed as previously tagged instead, move the new "Fixed" bullets to a
0.6.1 section. Live-load of the V2 omni graph in ComfyUI is the
outstanding verification (same gate the Seedance 2.5 layout passed).
Still open: letterbox cropdetect, cosmos.so resolver, full-film run.
