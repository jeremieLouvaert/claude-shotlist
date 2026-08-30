# /shotlist

**A reference video in, a per-shot generation brief out.**

Point it at a competitor ad, a mood-board clip, or your own dailies. Claude downloads the video, cuts it into shots (one frame per detected scene change, not a uniform tick), reads every frame alongside a timestamped transcript, and writes **one still-image generation prompt and one motion/camera note per shot** — the way a director briefs a stills artist, not a caption. You hand-edit the prompts, then feed them into a stills-then-motion pipeline: generate and lock the stills first (e.g. Nano Banana Pro), then run camera interpolation on the locked stills (e.g. Kling, Veo 3.1).

The tool stops at the prompt. Generation stays a separate, deliberate step — the point is a brief you can argue with, not an automated pipeline you can't.

```
/shotlist https://youtu.be/<reference-ad> break this down for a 20s product film
```

## What you get

Every run emits a structured `report.md`. The creative-direction core is the **Shot prompts** section — one entry per cut:

```markdown
### Shot 3 — [00:07] `frame_0003.jpg` (~2.4s to next cut)

- **image_prompt:** Low-angle medium shot of a canvas tent wall in raking
  golden-hour light, 35mm feel, warm amber grade, heavy cotton weave visible
  in the highlights, guy-line cutting the frame diagonally.
- **motion_note:** Slow push-in, ~2s, settling just before the cut; next shot
  answers with the reverse angle, so end the move steady.
```

Around it, the full editorial analysis rides along:

- **Shot-by-shot structure** — scene-change frame extraction, so the shot list matches the edit, and token cost is bounded by the number of cuts, not the duration.
- **0–10s hook microscope** — a dense 2 fps pass plus word-level transcript on the opening, frame-accurate to what was on screen as each word landed.
- **Editorial pacing metrics** — cuts/min, mean and median shot length.
- **TL;DR, key moments, quotable moments, entities, concepts, full transcript** — all as explicit `<!-- pending Claude fill -->` markers that Claude fills from the frames and transcript already in context. No extra API calls.

Running an analysis-only pass (summarize a talk, diagnose a screen recording)? `--no-shot-prompts` skips the shot-prompt section and the report is byte-identical to the upstream `/watch` output.

When the source is static or screen-recorded and scene detection falls back to uniform sampling, per-shot boundaries don't exist — the section then covers hero frames only, under an explicit note, rather than inventing cuts.

## How it works

1. **Download / probe.** URLs via `yt-dlp` (YouTube, Loom, TikTok, X, Instagram, and everything else yt-dlp supports); local files (`.mp4`, `.mov`, `.mkv`, `.webm`) are probed in place.
2. **Cut detection.** `ffmpeg`'s `select=gt(scene,…)` filter extracts one frame per shot boundary. Fixed for ffmpeg ≥ 8 (upstream's `-vsync` flag was removed there; this fork uses `-fps_mode vfr` with a legacy retry).
3. **Transcript.** Native captions first (free, instant). Fallback: Whisper via Groq (`whisper-large-v3`, preferred) or OpenAI (`whisper-1`).
4. **Claude reads everything.** Frame paths print with `t=MM:SS` markers; Claude `Read`s each frame as an image and fills every report marker — shot prompts included — grounded in what's actually on screen.
5. **Optional Obsidian auto-save.** The finished report can stage into your vault and run your vault's own ingest op. Skips quietly when no vault is configured.

Focused mode (`--start` / `--end`) gets denser per-second budgets when you only care about a window — far more useful than a sparse pass over a 10-minute video.

## Install

Install from a clone:

```bash
git clone https://github.com/jeremieLouvaert/claude-shotlist ~/.claude/skills/shotlist     # Claude Code (manual)
git clone https://github.com/jeremieLouvaert/claude-shotlist ~/.codex/skills/shotlist      # Codex / generic skills
bash scripts/build-skill.sh                          # claude.ai: builds dist/shotlist.skill to upload
```

Zero config to start: `ffmpeg` and `yt-dlp` install on first run via `brew` on macOS (Linux/Windows print exact commands). A Whisper API key (`GROQ_API_KEY` or `OPENAI_API_KEY` in `~/.config/watch/.env`) is only needed for videos without captions.

## Configuration

| Variable | Effect |
|----------|--------|
| `SHOTLIST_VAULT_DIR` | Path to your Obsidian vault; enables auto-save. |
| `WATCH_VAULT_DIR` | Honored as a fallback (upstream compat). |
| *(unset)* | Auto-detects `~/Second brain/`, `~/Documents/Obsidian/`, `~/Obsidian/`; otherwise the ingest steps skip quietly. |

API keys live in `~/.config/watch/.env` (mode `0600`; path kept from upstream so existing setups keep working). `--no-whisper` skips the fallback entirely.

## Scope, deliberately

- **No image or video generation.** Output is prompts, not pixels.
- **Public URLs and local files only.** No auth, no private platforms.
- **Detector accuracy is ffmpeg's, not this tool's.** The scene threshold occasionally merges near-identical cuts; the report schema is tested against fixed fixtures, the detector is not pinned.

## Credits

Built on [taoufik123-collab/claude-watch](https://github.com/taoufik123-collab/claude-watch) by Taoufik (scene-change extraction, hook microscope, structured report, Obsidian ingest), itself based on [bradautomates/claude-video](https://github.com/bradautomates/claude-video) by Bradley Bonanno (the yt-dlp + ffmpeg + Whisper pipeline). Both MIT; full attribution in [AUTHORS.md](AUTHORS.md) and [LICENSE](LICENSE). This fork adds the per-shot generation brief and the creative-direction framing.
