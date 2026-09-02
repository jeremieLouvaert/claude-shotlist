---
name: shotlist
description: Turn a reference video (competitor ad, mood-board clip, dailies) into a per-shot generation brief — one still-image prompt + one motion/camera note per detected cut — for a stills-then-motion pipeline, plus the full editorial analysis (scene-change frames, pacing metrics, 0-10s hook microscope, transcript from captions or Whisper) in an ingest-ready `report.md`. Optional Obsidian auto-ingest (configurable via `$SHOTLIST_VAULT_DIR`, `$WATCH_VAULT_DIR` honored).
argument-hint: "<video-url-or-path> [why you're studying it]"
allowed-tools: Bash, Read, AskUserQuestion
homepage: https://github.com/jeremieLouvaert/claude-shotlist
repository: https://github.com/jeremieLouvaert/claude-shotlist
author: jeremie
license: MIT
user-invocable: true
---

# /shotlist — a reference video becomes a per-shot generation brief

You don't have a video input; this skill gives you one. A Python script downloads the video, extracts frames as JPEGs (one per detected shot via scene-change), gets a timestamped transcript (native captions first, then Whisper API as fallback), runs editorial pacing metrics, and microscopes the first 10 seconds at higher density. You then `Read` each frame path to see the images, combine them with the transcript to answer the user, fill the structured `report.md`, and offer to ingest the analysis into the user's Obsidian vault.

## What v2 does differently

- **Scene-change frame sampling** — one frame per detected shot instead of uniform ticks. Cuts the frame budget on long videos while capturing every transition.
- **Editorial pacing metrics** — cuts/min, mean shot length, motion (when available). Lets you reason about pacing the way an editor does.
- **Hook microscope** — first 10s auto-runs at 2 fps + word-level Whisper. The single most leveraged 10 seconds of any video deserves dense treatment.
- **Structured `report.md`** — every watch emits an ingest-shaped report at `<workdir>/report.md` with TL;DR, key moments, hook breakdown, editorial profile, shot prompts, quotable moments, entities, concepts, and transcript. Narrative sections are emitted as `<!-- pending Claude fill: ... -->` markers — you fill them in before offering ingest.
- **Shot Prompts** — one still-image generation prompt + one motion/camera note per detected shot, for a stills-then-motion creative-direction pipeline (lock stills first, then camera interpolation on the locked stills). On by default; `--no-shot-prompts` skips it for analysis-only runs. No new dependencies or API calls — filled by you at Step 4 from the frames + transcript already in context.
- **Step 4.5 — Ingest gate** — after answering the user, you ask once: "Want to ingest this into your Obsidian vault?" If yes, and a vault is detected, you read `$VAULT_DIR/CLAUDE.md` (if it exists) and run that vault's Ingest op against the report.

None of the above add new dependencies — pure ffmpeg + stdlib + the existing Whisper backend.

## Configuration — finding the user's Obsidian vault

Steps 4.4 and 4.5 stage the report inside an Obsidian vault so the user can read it where they read everything else. Resolve the vault directory in this order — first hit wins, and the result is what `$VAULT_DIR` refers to everywhere below:

1. **`$SHOTLIST_VAULT_DIR` env var** — if set and the path exists, use it. This is the user-controlled override. `$WATCH_VAULT_DIR` is honored as a fallback (upstream compat).
2. **`~/Second brain/`** — if it exists as a directory.
3. **`~/Documents/Obsidian/`** — if it exists as a directory.
4. **`~/Obsidian/`** — if it exists as a directory.
5. **None found** — skip Steps 4.4 and 4.5 entirely. Print one line in chat so the user knows what happened: `📄 Report (no vault detected): <workdir>/report.md`. Suggest they set `SHOTLIST_VAULT_DIR` if they want auto-ingest.

A quick way to resolve it in bash inside the skill:

```bash
VAULT_DIR="${SHOTLIST_VAULT_DIR:-${WATCH_VAULT_DIR:-}}"
if [ -z "$VAULT_DIR" ] || [ ! -d "$VAULT_DIR" ]; then
  for candidate in "$HOME/Second brain" "$HOME/Documents/Obsidian" "$HOME/Obsidian"; do
    if [ -d "$candidate" ]; then VAULT_DIR="$candidate"; break; fi
  done
fi
```

The vault's URL-name (for the `obsidian://` URL scheme in Step 4.4) is the final path component — e.g. `$HOME/Second brain` → `Second brain`. URL-encode spaces as `%20`.

## Step 0 — Setup preflight (runs every `/shotlist` invocation, silent on success)

**Python interpreter:** every `python3 ...` command in this skill is for macOS/Linux. On **Windows**, substitute `python` — the `python3` command on Windows is the Microsoft Store stub and will not run the script.

Before every `/shotlist` run, verify that dependencies and an API key are in place:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py" --check
```

This is a <100ms lookup. On exit 0, the script emits **nothing** — proceed to Step 1 without comment. **Do NOT announce "setup is complete" to the user** — they don't need a status message on every turn. The only acceptable user-visible output from Step 0 is when remediation is required.

On non-zero exit, follow the table:

| Exit | Meaning | Action |
|------|---------|--------|
| `2` | Missing binaries (`ffmpeg` / `ffprobe` / `yt-dlp`) | Run installer |
| `3` | No Whisper API key | Run installer to scaffold `.env`, then ask user for a key |
| `4` | Both missing | Run installer, then ask for a key |

The installer is idempotent — safe to re-run:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py"
```

On macOS with Homebrew, it auto-installs `ffmpeg` and `yt-dlp`. On Linux/Windows, it prints the exact install commands for the user to run. It scaffolds `~/.config/watch/.env` with commented placeholders at `0600` perms, and writes `SETUP_COMPLETE=true` once deps + a key are in place so the next session knows this user has already been through the wizard.

**If an API key is still missing after install:** use `AskUserQuestion` to ask the user whether they have a Groq API key (preferred — cheaper, faster) or an OpenAI key. Then write it into `~/.config/watch/.env` — set the matching `GROQ_API_KEY=...` or `OPENAI_API_KEY=...` line. If they don't want to set up Whisper, proceed with `--no-whisper` and tell them videos without native captions will come back frames-only.

**Structured mode (optional):** `python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py" --json` emits `{status, first_run, missing_binaries, whisper_backend, has_api_key, config_file, platform}` where `status` is one of `ready | needs_install | needs_key | needs_install_and_key`. Use this when you need to branch on specifics (e.g. "is this the user's very first run?" → `first_run: true`).

Within a single session, you can skip Step 0 on follow-up `/shotlist` calls — once `--check` returned 0, nothing about the environment changes between turns.

## When to use

- User pastes a video URL (YouTube, Vimeo, X, TikTok, Twitch clip, most yt-dlp-supported sites) and asks about it.
- User points at a local video file (`.mp4`, `.mov`, `.mkv`, `.webm`, etc.) and asks about it.
- User types `/shotlist <url-or-path> [question]`.

## Recommended limits

- **Best accuracy: videos under 10 minutes.** Frame coverage scales inversely with duration.
- **Hard caps: 100 frames total and 2 fps.** Token cost grows with frame count, so the script targets a frame budget by duration (and never exceeds 2 fps even when the budget would imply more):
  - ≤30s → ~1-2 fps (up to 30 frames)
  - 30s-1min → ~40 frames
  - 1-3min → ~60 frames
  - 3-10min → ~80 frames
  - \>10min → 100 frames, sparsely spaced (warning printed)
- If the user hands you a long video, consider asking whether they want a specific section before burning tokens on a sparse scan.

## How to invoke

**Step 1 — parse the user input.** Separate the video source from any question the user asked. The question (or the user's prior stated interest) IS the intent — pass it to the script via `--intent`. Example: `/shotlist https://youtu.be/abc what's the hook pattern?` → source = `https://youtu.be/abc`, intent = `what's the hook pattern?`. If no question is given, use a brief inferred intent ("general summary") so the report's TL;DR has a lens. The intent shapes how the report's TL;DR and entity/concept sections get filled at Step 4 — same video with intent "pricing tactics" vs "editing style" produces different reports.

**Step 2 — run the watch script.** Pass the source verbatim. Do not shell-escape it yourself beyond normal quoting:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/watch.py" "<source>" --intent "<intent string>"
```

Pass `--intent` whenever you have any signal from the user about why they want this video — the question they asked, a stated goal, or a brief inferred summary. Empty `--intent` works but produces less-targeted report sections.

Optional flags:
- `--start T` / `--end T` — focus on a section. Accepts `SS`, `MM:SS`, or `HH:MM:SS`. When either is set, fps auto-scales denser (see "Focusing on a section" below).
- `--max-frames N` — lower the cap for tighter token budget (e.g. `--max-frames 40`)
- `--resolution W` — change frame width in px (default 512; bump to 1024 only if the user needs to read on-screen text)
- `--fps F` — override auto-fps (clamped to 2 fps max). Setting `--fps` disables scene-change sampling.
- `--out-dir DIR` — keep working files somewhere specific (default: an auto-generated tmp dir)
- `--whisper groq|openai` — force a specific Whisper backend (default: prefer Groq if both keys exist)
- `--no-whisper` — disable the Whisper fallback entirely (frames-only if no captions)
- `--no-scene-change` — force uniform frame sampling (debug only; usually leave on)
- `--no-hook-microscope` — skip the 0-10s dense pass (saves ~1 Whisper call)
- `--no-shot-prompts` — skip the per-shot generation-prompt section in `report.md`. Use for analysis-only runs where nobody will generate from this video; it removes the largest block of fill markers from Step 4.

### Focusing on a section (higher frame rate)

When the user asks about a specific moment — "what happens at the 2 minute mark?", "zoom into 0:45 to 1:00", "the first 10 seconds" — pass `--start` and/or `--end`. The script switches to focused-mode budgets, which are denser than full-video budgets (still capped at 2 fps):

- ≤5s → 2 fps (up to 10 frames)
- 5-15s → 2 fps (up to 30 frames)
- 15-30s → ~2 fps (up to 60 frames)
- 30-60s → ~1.3 fps (up to 80 frames)
- 60-180s → ~0.6 fps (100 frames, capped)

Focused mode is the right call for:
- Any moment/range the user names explicitly ("around 2:30", "the intro", "the last 30 seconds").
- Any video longer than ~10 minutes where the user's question is about a specific part — running focused on the relevant section is far more useful than a sparse scan of the whole thing.
- Re-runs after a full scan didn't have enough detail in some region.

Transcript is auto-filtered to the same range. Frame timestamps are absolute (real video timeline, not offset-from-start).

Examples:
```bash
# Last 10 seconds of a 1 minute video
python3 "${CLAUDE_SKILL_DIR}/scripts/watch.py" video.mp4 --start 50 --end 60

# Zoom into 2:15 → 2:45 at 3 fps (90 frames)
python3 "${CLAUDE_SKILL_DIR}/scripts/watch.py" "$URL" --start 2:15 --end 2:45 --fps 3

# From 1h12m to the end of the video
python3 "${CLAUDE_SKILL_DIR}/scripts/watch.py" "$URL" --start 1:12:00
```

**Step 3 — Read every frame path the script lists.** The Read tool renders JPEGs directly as images for you. Read all frames in a single message (parallel tool calls) so you see them together. The frames are in chronological order with a `t=MM:SS` timestamp so you can align them to the transcript.

**Step 4 — answer the user, then fill the report.** You now have three streams of evidence:
- **Frames** — what's on screen at each timestamp
- **Transcript** — what's said at each timestamp
- **`report.md`** — structured artifact at `<workdir>/report.md` with `<!-- pending Claude fill: ... -->` markers

First, answer the user's question in chat citing timestamps.

Then, **fill in the pending markers in `report.md` using the Edit tool**. Walk every `<!-- pending Claude fill: ... -->` in order:
- **TL;DR** — 3-5 bullets through the lens of the user's intent (read from the frontmatter)
- **Key moments** — 5-10 timestamped bullets
- **Hook microscope interpretation** — frame-by-frame: visual change × what's said; identify the hook pattern (question, contrarian claim, in-medias-res, demo-first, etc.)
- **Editorial profile fingerprint** — one-line style summary inferred from pacing numbers + hero frames
- **Shot prompts** (unless `--no-shot-prompts` was passed) — two fields per `### Shot` entry, written from the frame image at that timestamp plus the transcript around it:
  - `image_prompt` — a still-image generation prompt for that exact frame: subject, composition, camera angle/lens feel, lighting, color grade, material/texture cues. Write it the way a director briefs a stills artist, not a caption. Concrete nouns and light, no plot summary.
  - `motion_note` — 1-2 lines on camera movement and pacing into/out of that shot (the `~Xs to next cut` figure in the heading is the shot's real length — respect it), for the motion pass once the still is locked.
  - Two lessons from real-footage runs: a scene frame is grabbed at the cut, so it can catch a title or graphic mid-animation — check `hook_frames/` (or the neighbouring shots) for the settled version before describing it. And a single still cannot show camera motion — infer `motion_note` from motion blur, perspective and the neighbouring frames, and say in the note when the move is a guess rather than legible in the frame.
- **Quotable moments** — top 3-5 punchy, standalone lines from the transcript
- **Entities mentioned** — people, companies, tools, places — formatted to match wiki/entities/ slugs (kebab-case, lowercase). Use `[[wikilink]]` style.
- **Concepts surfaced** — frameworks, mental models, named patterns — short gist each

The fully-filled `report.md` is what gets ingested at Step 4.5. Do not skip the fill — empty markers won't ingest cleanly.

**Step 4.4 — Stage to the Obsidian vault and open in Obsidian (when a vault is detected).** After filling every marker, resolve `$VAULT_DIR` per the Configuration section. **If no vault is detected, skip this step** and emit `📄 Report (no vault detected): <workdir>/report.md` in chat instead.

When `$VAULT_DIR` resolves:

1. **Derive the slug now** (do not wait for Step 4.5). Take the video title from `report.md` frontmatter, slugify (lowercase, ASCII-only, hyphens, max 60 chars), append `-YYYY-MM-DD`. Example: `karpathy-claude-md-43k-installs-2026-05-24`.
2. **Create the staging dir:** `mkdir -p "$VAULT_DIR/raw/watched/<slug>"`.
3. **Copy `report.md` + every hero frame** (filenames in the report frontmatter under `hero_frames:`) into that dir. The report MUST live inside the vault for Obsidian to open it.
4. **Open in Obsidian via URL scheme** (macOS). The vault URL-name is the final component of `$VAULT_DIR` with spaces URL-encoded as `%20`:
   ```bash
   VAULT_NAME=$(basename "$VAULT_DIR" | sed 's/ /%20/g')
   open "obsidian://open?vault=${VAULT_NAME}&file=raw/watched/<slug>/report.md"
   ```
   The `file=` value is the path relative to the vault root, no leading slash. Don't ask permission — the user has already opted in by running /shotlist.
5. **Echo the vault-relative path in chat** on its own line: `📄 Report (open in Obsidian): raw/watched/<slug>/report.md`. So if Obsidian was closed / the URL handler missed, the user can still navigate to it manually inside the vault.

Rationale: the report is the leverage point of /shotlist. If the user reads everything in Obsidian, opening in Preview or VS Code defeats the purpose. Staging at 4.4 also means Step 4.5's "Yes / Stage" branches are no-ops on the copy step (the file is already in the vault); they only differ in whether the Ingest op runs.

**Cleanup implication for Step 4.5:** if the user picks "No, drop it" at 4.5 AND a vault was staged at 4.4, ALSO `rm -rf "$VAULT_DIR/raw/watched/<slug>"` since we pre-staged. Do NOT drop the vault copy if they picked Yes or Stage.

**Step 4.5 — Offer ingest into the Obsidian vault.** **Skip this step entirely if no vault was detected at Step 4.4.** Otherwise use `AskUserQuestion` once, with these options (do NOT skip if a vault was found unless the user explicitly said "don't ingest" before /shotlist ran):

> **Question:** "Want to ingest this into your Obsidian vault?"
> - **Yes — same angle** ("<intent>")
> - **Yes — different angle** (user specifies in the notes field)
> - **Stage to `raw/watched/` for later**
> - **No, drop it**

Routing based on response:

**A. Yes (same or different angle):**
1. Derive the slug: take the video title from `report.md` frontmatter, slugify (lowercase, ASCII-only, hyphens, max 60 chars), append `-YYYY-MM-DD`. Example: `me-at-the-zoo-2026-05-24`.
2. Confirm the staging dir exists at `$VAULT_DIR/raw/watched/<slug>/` (Step 4.4 already created it).
3. The report + hero frames are already copied there from Step 4.4.
4. **If "different angle":** Re-edit the TL;DR + Entities + Concepts sections of the copied report to reflect the new angle the user specified, before running ingest.
5. **If `$VAULT_DIR/CLAUDE.md` exists:** Read it to refresh the Ingest op definition — that file is authoritative; this skill must not duplicate its steps. Execute the Ingest op against `raw/watched/<slug>/report.md` exactly as `$VAULT_DIR/CLAUDE.md` defines it.
6. **If no `$VAULT_DIR/CLAUDE.md` exists:** Run a generic ingest — read the report, identify entities + concepts, append a one-line entry to `$VAULT_DIR/log.md` (create if missing), and tell the user the report is staged at `raw/watched/<slug>/report.md` and they can wire up an Ingest op of their own.
7. Report back to the user in chat: which entity pages were touched (if any), the path to the staged report, and the `log.md` entry written.

**B. Stage to `raw/watched/` for later:**
1. The staging from Step 4.4 already did the file copy.
2. Do NOT touch the wiki. Do NOT append to `log.md`.
3. Tell the user in chat: "Staged at `$(basename $VAULT_DIR)/raw/watched/<slug>/`. Run an Ingest op against it when you're ready."

**C. No, drop it:** proceed to Step 5 (cleanup) — and per the cleanup-implication note in Step 4.4, `rm -rf "$VAULT_DIR/raw/watched/<slug>"` to undo the pre-staging.

The "different angle" path is what makes /shotlist truly plug-and-play — the user can watch a video for one reason, then on the way out decide it's actually more useful for a different concept, and the resulting wiki entry reframes accordingly.

**Step 5 — clean up.** The script prints a working directory at the end. If you ingested (Step 4.5 path A), the hero frames + report.md are already copied into the vault — you can `rm -rf` the original workdir. If you staged (path B), same — the workdir copy is no longer needed. If the user picked "no, drop it" (path C) and isn't going to ask follow-ups, delete with `rm -rf <dir>`. If they might ask follow-ups, leave it in place.

## Step 6 — Remix (optional): report → ComfyUI workflows

When the user wants to RECREATE the reference as their own film ("remix this into…", "change the horses to jeeps", "make this a <brand> movie"), a filled report becomes two loadable ComfyUI workflows — a stills graph that generates a first and a last frame per shot, and a video graph that animates each locked first/last pair (Seedance first+last-frame conditioning).

1. **Create the remix sheet.** The brief is the user's transposition in their words (subjects to swap, world, target aspect ratio, what to keep):
   ```bash
   python3 "C:/Users/Jeremie/.claude/skills/shotlist/scripts/remix.py" "<workdir>" --brief "<transposition brief>" [--ar 16:9]
   ```
   This parses the report's Shot prompts section into `<workdir>/remix.md` with three pending markers per shot (`first_frame_prompt`, `last_frame_prompt`, `video_prompt`) plus one global `style_keeper`. It refuses to run on a report with unfilled markers.
2. **Fill every marker** (same walk as Step 4). `first_frame_prompt` is an **instruction against the reference frame** ("replace the riders with…", "reframe to 16:9 extending the landscape…", "remove the caption text"), not a from-scratch description. `last_frame_prompt` is an **instruction against the approved first frame** — the generated still the user picks becomes its conditioning image, so it must describe only what changes by the end of the shot ("the vehicles have advanced 40 meters, dust behind the wheels"); this chaining is what keeps transposed subjects consistent within a shot (generating first and last independently from the reference makes the model invent the subject twice — measured failure on the first live test). `video_prompt` describes only the motion between the locked frames. `style_keeper` is one sentence naming the original's grade/light/lens, auto-appended to every stills prompt. Never put a real person's likeness in a transposed prompt — recast as a fictional person.
3. **Emit the workflow:**
   ```bash
   python3 "C:/Users/Jeremie/.claude/skills/shotlist/scripts/remix.py" "<workdir>" --emit [--stills-engine nano|gpt] [--video-engine seedance|omni] [--seedance-model "Seedance 2.5"]
   ```
   Writes ONE combined `comfy/remix_workflow.json` plus `comfy/input/shotNN_ref.*` (renamed reference frames — the only files the graph reads from disk). The graph has two labelled sections: **A — STILLS** (per shot: FIRST frame generates from the reference; LAST frame generates conditioned on the first frame, received over a wireless channel) and **B — VIDEO** (first/last arrive via `WirelessGet` → Seedance `ByteDance2FirstLastFrameNode` AND `GeminiVideoOmniV2` with first→image_1 / last→image_2; `--omni-model` picks the V2 model key, `"Omni Flash 1.1"` default or `"Omni Flash"` — the sub-widget layout differs per key and both are emitted from the running server's `/object_info`, not the captures). The chain is fully procedural: each generation branch's `LazyAPISwitch.final_output` feeds a `WirelessSend` on channel `shotNN_first` / `shotNN_last`, downstream consumers use `WirelessGet` on the same channel — one queue run produces firsts → lasts → videos with no file round-trip or renaming. Every generation node is wrapped in the hash-vault caching triad (`DeterministicHashVault` → `HashVaultSave` → `LazyAPISwitch`, keyed on prompt + conditioning inputs), so redoing one branch (tweak its prompt or seed, re-queue) reuses every unchanged branch from cache. Both engines per stage are emitted with the non-chosen one **muted** (`GeminiImage2Node` Nano Banana Pro vs `gpt-image-2`; Seedance vs Omni) — switching is a UI mute-toggle. Both engines share a channel, so exactly ONE stills engine may be unmuted per run — unmuting both makes the channel value nondeterministic. Stills also save to disk via the send's passthrough (`output/remix/`, engine-suffixed) for review.

The graph is emitted from `scripts/comfy_templates.json` — node instances captured from a real install. If the user's ComfyUI lacks those node packs, the file loads with missing-node placeholders — tell them which packs the graph expects rather than editing the JSON by hand. When the user's ComfyUI server is reachable (usually `http://127.0.0.1:8188`), `GET /object_info/<ClassName>` is the schema authority for widget layouts — prefer it over the captured templates whenever a node errors on a widget value.

**Brief presets.** If the user names a preset in a remix ask ("use the canvascamp preset"), read `$SHOTLIST_VAULT_DIR/remix-presets.md` — one `## <name>` heading per preset, body is the brief verbatim — and expand it as the `--brief`. If the file or preset doesn't exist, say so and ask for the brief in words; offer to save it as a new preset for next time.

**Fidelity check (before the video pass).** After the stills generate, run:
   ```bash
   python3 "C:/Users/Jeremie/.claude/skills/shotlist/scripts/remix.py" "<workdir>" --fidelity "<ComfyUI output/remix dir>"
   ```
   It lists reference-vs-generated pairs per shot half. `Read` each pair side by side and judge against the shot's prompt: subject count and identity, the single accent color, grade and light direction, composition, and first↔last consistency (same vehicles/people/wardrobe in both). Report drift per shot with a pass/redo verdict and the prompt tweak that would fix it; the user re-queues only the flagged branches (the hash vault serves the rest from cache).

## Step 7 — Assemble (after the video pass): clips → film + EDL

When the generated clips exist (ComfyUI's `output/remix/`, or a folder of downloads), cut them into a film with the reference's rhythm:

```bash
python3 "C:/Users/Jeremie/.claude/skills/shotlist/scripts/assemble.py" "<workdir>" --clips "<clips dir>" [--audio <music bed>]
```

Clips are matched per shot by the `shotNN` token (newest file wins), trimmed FROM THE HEAD to the shot's reference duration (the head is the locked first frame; the tail is where video models drift), normalized to the first clip's resolution/fps, and hard-cut in shot order. Outputs land in `<workdir>/assembly/`: `final.mp4`, `final.edl` (CMX3600 — imports into Resolve/Premiere for hand finishing), and the trimmed `parts/`. Shots without a reference duration use the full clip. `--audio` lays a bed under the cut; beat-matched editing and sound design stay human work — say so rather than pretending otherwise. Missing clips warn and are skipped, so a partial run still yields a watchable cut.

## Transcription

The script gets a timestamped transcript in one of two ways:

1. **Native captions (free, preferred).** yt-dlp pulls manual or auto-generated subtitles from the source platform if available.
2. **Whisper API fallback.** If no captions came back (or the source is a local file), the script extracts audio (`ffmpeg -vn -ac 1 -ar 16000 -b:a 64k`, ~0.5 MB/min) and uploads it to whichever Whisper API has a key configured:
   - **Groq** — `whisper-large-v3`. Preferred default: cheaper, faster. Get a key at console.groq.com/keys.
   - **OpenAI** — `whisper-1`. Fallback. Get a key at platform.openai.com/api-keys.

Both keys live in `~/.config/watch/.env`. The script prefers Groq when both are set; override with `--whisper openai` to force OpenAI. Use `--no-whisper` to skip the fallback entirely.

## Failure modes and handling

- **Setup preflight failed** → run `python3 "${CLAUDE_SKILL_DIR}/scripts/setup.py"` (auto-installs ffmpeg/yt-dlp via brew on macOS, scaffolds the `.env`). For API key, ask the user via `AskUserQuestion` and write it to `~/.config/watch/.env`.
- **No transcript available** → captions missing AND (no Whisper key OR Whisper API failed). Script prints a hint pointing to setup. Proceed frames-only and tell the user.
- **Long video warning printed** → acknowledge it in your answer. Offer to re-run focused on a specific section via `--start`/`--end` rather than a sparse full-video scan.
- **Download fails** → yt-dlp's error goes to stderr. If it's a login-required or region-locked video, tell the user plainly; do not keep retrying.
- **cosmos.so (moodboard) URL given** → handled automatically: `download.py` resolves the save to the original post URL before yt-dlp runs (the element page's own JSON-LD block names it in `sameAs`) and prints the hop to stderr. If it exits saying no original post was found or the fetch failed, open the save in a browser and pass the original post URL directly — do not retry the cosmos URL.
- **Whisper request fails** → the error is printed to stderr (likely: invalid key, rate limit, or 25 MB upload limit on a very long video). The report will say "none available" for transcript. You can retry with `--whisper openai` if Groq failed (or vice versa).
- **Report has unfilled `<!-- pending Claude fill: ... -->` markers** → you skipped Step 4. Go back, read the report, fill every marker via Edit, then offer ingest. Never ingest a half-filled report — the vault Ingest op will produce sparse/wrong entity pages.
- **Shot prompts section says frames were uniform-sampled** → the source had no detectable cuts (static/screen-recorded), so per-shot boundaries don't exist and prompts cover hero frames only. That is correct behavior, not an error — tell the user; if they need denser coverage for generation, re-run focused on the range they care about.
- **Shot prompts section is missing but the user wants generation prompts** → the run used `--no-shot-prompts`. Re-run without the flag (or, if frames + transcript are still in context, append the section by hand following the schema above rather than re-downloading).
- **`remix.py --brief` refuses: report has pending markers** → finish the Step 4 fill first; the remix sheet inherits `image_prompt`/`motion_note` per shot and fiction in, fiction out.
- **`remix.py --emit` refuses: remix.md has pending markers or empty fields** → the fill was skipped or partial. Fill every `first_frame_prompt` / `last_frame_prompt` / `video_prompt` and `style_keeper`, then re-run `--emit`.
- **Generated workflow loads with red missing-node placeholders in ComfyUI** → the install lacks the node packs the graph targets (GeminiImage2Node, ByteDance2FirstLastFrameNode, StringConstantMultiline). Name the missing packs to the user; do not hand-edit the JSON to substitute different nodes.
- **Ingest fails partway** → do not roll back. The vault Ingest op is idempotent on re-run (it updates existing pages rather than duplicating). Tell the user what failed, leave the staged artifact in `raw/watched/<slug>/`, and they can re-run by saying "ingest the staged report at `<slug>`".

## Token efficiency

This skill burns tokens primarily on frames. Order of magnitude:
- 80 frames at 512px wide is roughly 50-80k image tokens depending on aspect ratio.
- The transcript is cheap (a few thousand tokens at most for a 10-minute video).
- Bumping `--resolution` to 1024 roughly quadruples the image tokens per frame. Only do it when necessary.

If you already watched a video this session and the user asks a follow-up, do **not** re-run the script — you already have the frames and transcript in context. Just answer from what you have.

## Security & Permissions

**What this skill does:**
- Runs `yt-dlp` locally to download the video and pull native captions when the source supports them (public data; the request goes directly to whatever host the URL points at)
- Runs `ffmpeg` / `ffprobe` locally to extract frames as JPEGs and, when Whisper is needed, a mono 16 kHz audio clip
- Sends the extracted audio clip to Groq's Whisper API (`api.groq.com/openai/v1/audio/transcriptions`) when `GROQ_API_KEY` is set (preferred — cheaper, faster)
- Sends the extracted audio clip to OpenAI's audio transcription API (`api.openai.com/v1/audio/transcriptions`) when `OPENAI_API_KEY` is set and Groq is not, or when `--whisper openai` is forced
- Writes the downloaded video, frames, audio, and an intermediate transcript to a working directory under the system temp dir (or `--out-dir` if specified) so Claude can `Read` them
- Reads / creates `~/.config/watch/.env` (mode `0600`) to store the Whisper API key(s) and a `SETUP_COMPLETE` marker. As a fallback, also reads `.env` in the current working directory
- Reads `$VAULT_DIR/CLAUDE.md` at orchestration time (only when ingest is requested and the file exists) to follow that vault's Ingest operation definition
- Writes a structured `report.md` plus copies of hero frames into `$VAULT_DIR/raw/watched/<slug>/` when a vault is detected at Step 4.4
- When ingest is consented to: reads and writes pages under `$VAULT_DIR/wiki/` (entities, concepts, sources, index.md) and appends to `$VAULT_DIR/log.md` — following the actions defined by the vault's Ingest op (or a generic fallback if no `CLAUDE.md` is present)

**What this skill does NOT do:**
- Does not upload the video itself to any API — only the extracted audio goes out, and only when native captions are missing AND Whisper is not disabled with `--no-whisper`
- Does not access any platform account (no login, no session cookies, no posting)
- Does not share API keys between providers (Groq key only goes to `api.groq.com`, OpenAI key only goes to `api.openai.com`)
- Does not log, cache, or write API keys to stdout, stderr, or output files
- Does not persist anything outside the working directory and `~/.config/watch/.env` (and the Obsidian vault when ingest is consented to) — clean up the working directory when you're done (Step 5)
- Does not write into the vault without explicit user consent at the Step 4.5 prompt
- Does not silently overwrite wiki claims — contradictions surface as WARN flags per the Ingest op contract

**Bundled scripts:** `scripts/watch.py` (entry point), `scripts/download.py` (yt-dlp wrapper), `scripts/frames.py` (ffmpeg uniform + scene-change extraction + hero selection), `scripts/pacing.py` (editorial metrics), `scripts/hook.py` (0-10s microscope), `scripts/report.py` (structured report emitter), `scripts/transcribe.py` (caption selection + Whisper orchestration), `scripts/whisper.py` (Groq / OpenAI clients, supports word-level timestamps), `scripts/setup.py` (preflight + installer)

Review scripts before first use to verify behavior.
