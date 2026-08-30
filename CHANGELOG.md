# Changelog

All notable changes are documented here. (Through 0.3.0 this project was `/watch`.)

## [0.5.0] — 2026-08-30

Remix: a filled report becomes one loadable ComfyUI workflow that recreates the reference as your own film — per shot a first frame (from the reference), a last frame (chained from the generated first for subject consistency), and a first→last video pass, in a single queue run. The transposition ("horses become Land Rovers, keep the grade, 16:9") is Claude's fill; the node graph is deterministic emitter output. Validated end-to-end on a live ComfyUI install (0.34.2).

### Added
- `scripts/remix.py` — phase 1 (`--brief`) parses the report's Shot prompts into `remix.md` with `first_frame_prompt` / `last_frame_prompt` / `video_prompt` markers per shot plus a global `style_keeper`; phase 2 (`--emit`) builds ONE combined `comfy/remix_workflow.json`. Section A (stills, blue groups): reference frame + shared prompt → Nano Banana Pro `GeminiImage2Node` AND `gpt-image-2` `OpenAIGPTImageNodeV2`; the LAST frame generates conditioned on the generated first frame. Section B (video, green groups): Seedance `ByteDance2FirstLastFrameNode` AND `GeminiVideoOmni` (first→image_1 / last→image_2), per-shot duration from the reference's real shot length (clamped 4–30s). Both phases refuse to run over unfilled markers.
- **Wireless chaining** (`WirelessSend`/`WirelessGet` on `shotNN_first` / `shotNN_last` channels): firsts → lasts → videos flow in one queue run with no file round-trip; only the reference frames are read from disk, and `--comfy-input` / `$SHOTLIST_COMFY_INPUT` copies those straight into ComfyUI's input folder.
- **Hash-vault caching** on every generation branch (`DeterministicHashVault` → `HashVaultSave` → `LazyAPISwitch`, keyed on prompt + conditioning inputs): redoing one branch re-queues one API call, everything unchanged serves from cache.
- Dual engines per stage with the non-chosen one muted (`--stills-engine nano|gpt`, `--video-engine seedance|omni`, `--seedance-model`); switching engines is a UI mute-toggle, not a re-emit. Exactly one stills engine unmuted per run (shared channel).
- `scripts/comfy_templates.json` — node templates captured verbatim from a real install's output-PNG metadata, scrubbed of creative content; the Seedance 2.5 widget layout is taken from the running server's `/object_info` (the schema authority — captured layouts go stale when node packs update). Overlap-free layout computed from the captured node sizes.
- SKILL.md Step 6 (Remix) + failure-mode rows; 8 new tests (remix.md schema, refusal paths, graph integrity, wireless chaining, engine muting, vault keying, Seedance 2.5 widget layout, zero node overlaps). Suite: 22.

### Unchanged
- Every pre-existing script is byte-identical to 0.4.0; remix is additive.

## [0.4.0] — 2026-08-30

Identity: the fork ships as **`/shotlist`** (repo: claude-shotlist), a creative-direction tool, no longer claiming the upstream `/watch` name. Runtime pipeline (`scripts/*.py`) is untouched — byte-identical to 0.3.0.

### Changed
- Skill/command/plugin renamed `watch` → `shotlist` across SKILL.md frontmatter, `commands/shotlist.md`, `.claude-plugin/`, `.codex-plugin/`, hooks status lines, and the `.skill` build (`dist/shotlist.skill`).
- README rewritten around the creative-direction workflow (reference video → per-shot brief → stills-then-motion generation); analysis features documented as riding along.
- Vault override: `$SHOTLIST_VAULT_DIR` preferred, `$WATCH_VAULT_DIR` honored as fallback.
- `homepage`/`repository` metadata removed until the fork has a published home.

### Kept for compatibility
- `~/.config/watch/.env` config path, `raw/watched/` vault staging path, `$WATCH_VAULT_DIR`, and all `scripts/*.py` internals (including `[watch]` stderr prefixes and `prog="watch"`).

## [0.3.0] — 2026-08-30

Creative-direction fork: per-shot AI-generation prompts for a stills-then-motion pipeline (stills generator first, camera interpolation on the locked stills). Additive — a run with `--no-shot-prompts` produces a report byte-identical to 0.2.0 (verified by diff against the 0.2.0 emitter on the same payload).

### Added
- `## Shot prompts` section in `report.md` (between Editorial profile and Quotable moments): one entry per scene-change frame with two `<!-- pending Claude fill -->` fields — `image_prompt` (still-image generation prompt, director-brief register) and `motion_note` (camera movement/pacing into and out of the shot). Headings carry timestamp, frame filename, and measured shot length (`~Xs to next cut`). Filled by Claude at Step 4 from evidence already in context — no new API calls, no new dependencies.
- Uniform-fallback handling: when scene detection fell back to uniform sampling (static/screen-recorded source), per-shot boundaries don't exist — the section covers hero frames only under an explicit note.
- `--no-shot-prompts` flag in `scripts/watch.py` for analysis-only runs.
- `scripts/tests/fixtures/make_fixtures.py` — generates four synthetic sub-30s clips with known cut structure (ffmpeg lavfi sources, nothing downloaded, nothing committed) for fixture-first testing.
- 5 unit tests for the shot-prompt report schema (fixed frame paths + transcript fixture, no video required): scene-mode entry count, section placement, uniform-mode hero-only coverage, empty-frames note, flag-off omission with upstream section order intact.
- SKILL.md: Step 4 fill list documents both new fields, flag documented, two failure-mode rows added (uniform-sampled note is correct behavior; missing section = flag was passed).

### Fixed
- `scripts/frames.py` scene extraction on ffmpeg ≥ 8: `-vsync` was removed upstream in ffmpeg; now passes `-fps_mode vfr` and retries with the legacy `-vsync vfr` on ffmpeg < 5.1. Behavior-preserving; also un-skips the two ffmpeg-dependent unit tests on current ffmpeg installs.

## [0.2.0] — 2026-05-25

Based on [bradautomates/claude-video](https://github.com/bradautomates/claude-video) v0.1.3 by Bradley Bonanno (MIT). Its pipeline (yt-dlp + ffmpeg + Whisper) is preserved; everything below is additive.

### Added
- Scene-change frame extraction in `scripts/frames.py` — `extract_scene_change()` + `select_hero_frames()` using ffmpeg's `select=gt(scene,...)` filter. One frame per detected shot instead of uniform every-N-seconds sampling. Keeps token cost flat on long videos. Uniform sampling still available as a fallback for static/screen-recorded sources.
- 0-10s hook microscope in `scripts/hook.py` — 2 fps frames + word-level Whisper transcript on the opening 10 seconds, so the report can tell you what's on screen *as each word lands*.
- Editorial pacing metrics in `scripts/pacing.py` — shot count, cuts/min, mean + median shot length.
- Structured `report.md` emitter in `scripts/report.py` — fixed-schema ingest-ready report with `<!-- pending Claude fill: ... -->` markers for narrative sections (TL;DR, key moments, hook breakdown, editorial profile, quotable moments, entities, concepts).
- Word-level timestamps in `scripts/whisper.py` (Groq + OpenAI backends extended).
- New CLI flags in `scripts/watch.py`: `--intent`, `--no-scene-change`, `--no-hook-microscope`.
- Step 4.4 (stage to Obsidian vault) + Step 4.5 (ingest gate) in `SKILL.md` — optional auto-save to your Obsidian vault. Path resolved via `$WATCH_VAULT_DIR` or auto-detected from `~/Second brain/`, `~/Documents/Obsidian/`, `~/Obsidian/`. Skips cleanly when no vault is detected.
- 7 unit tests under `scripts/tests/` (stdlib `unittest`, no pytest dependency).

### Changed
- `SKILL.md` is now a v2 contract — describes the structured report, the marker-fill step, and the vault config. Backwards-compatible with /watch invocations that don't care about ingest.
- README documents the added features and the `$WATCH_VAULT_DIR` configuration.

## [0.1.3] — 2026-05-09

### Fixed
- Windows: `video.info.json` is read as UTF-8 (#4). Previously `Path.read_text()` defaulted to cp1252 on Windows and crashed on yt-dlp's UTF-8 output, silently dropping Title/Uploader from the report. Same fix applied to `.env` reads/writes in `whisper.py` and `setup.py`.
- `download.py` now logs info.json parse failures to stderr instead of swallowing them.

### Security
- Hardened subprocess argv against option injection (#2): inserted `--` before the URL in the yt-dlp argv, and tightened `is_url` to reject `-`-prefixed sources and require a non-empty netloc. Resolved video/audio paths to absolute via `Path.resolve()` before passing to `ffmpeg`/`ffprobe`, so a relative path starting with `-` can't be misinterpreted as a flag.

## [0.1.2] — 2026-04-24

### Fixed
- Windows console crash: removed the emoji from the long-video warning in `watch.py`; cp1252 consoles couldn't encode it.
- `setup.py` now prints `winget` / `pip` install commands on Windows instead of "unsupported platform" — matches what the README already promised.

### Changed
- `SKILL.md` notes that on Windows the scripts must be invoked with `python`, not `python3` (the latter is the Microsoft Store stub on Windows).

## [0.1.1] — 2026-04-24

### Fixed
- Added `commands/watch.md` shim so `/watch` is callable when installed as a Claude Code plugin. Without it, the plugin loaded but the skill wasn't exposed as a slash command.
- `scripts/build-skill.sh` now strips `commands/` from the claude.ai `.skill` bundle alongside `hooks/` and `.claude-plugin/`.

## [0.1.0] — 2026-04-24

Initial marketplace release.

### Added
- `/watch <url-or-path> [question]` slash command.
- yt-dlp download with native caption extraction (manual + auto-subs).
- ffmpeg frame extraction with auto-scaled fps (≤2 fps, ≤100 frames, duration-aware budget).
- `--start` / `--end` focused mode with denser frame budget and transcript range filtering.
- Whisper fallback (Groq preferred, OpenAI secondary) for videos without captions.
- `setup.py` preflight: silent `--check`, structured `--json`, and installer that auto-runs `brew install` on macOS.
- Session-start hook that prints a one-line status on first run / partial config.
- `.skill` bundle packaging for claude.ai upload via `scripts/build-skill.sh`.
