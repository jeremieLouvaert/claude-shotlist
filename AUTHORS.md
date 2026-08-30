# Authors & credits

## Original project

**Bradley Bonanno** — [bradautomates/claude-video](https://github.com/bradautomates/claude-video)

The original `/watch` skill: yt-dlp download, the ffmpeg frame pipeline, the Groq/OpenAI
Whisper backends, the multi-surface install flow, and the SessionStart hook. Released under
the MIT license, © 2026 Bradley Bonanno.

## This distribution — claude-watch

**Taoufik** — [taoufik123-collab](https://github.com/taoufik123-collab)

Scene-change frame extraction, the 0-10s hook microscope, the structured `report.md`, and
optional Obsidian auto-save, on top of Bradley's pipeline.

## This fork — claude-shotlist

**Jérémie Louvaert**

Per-shot generation prompts (`image_prompt` + `motion_note` per detected cut) for
stills-then-motion creative-direction pipelines, the ffmpeg ≥ 8 scene-extraction fix,
and the `/shotlist` identity, on top of Taoufik's claude-watch.
