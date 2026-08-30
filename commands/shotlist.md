---
description: Turn a reference video (URL or local path) into a per-shot generation brief — one still-image prompt + one motion note per cut — plus full editorial analysis. Downloads with yt-dlp, extracts scene-change frames with ffmpeg, transcribes from captions or Whisper.
argument-hint: <video-url-or-path> [question]
allowed-tools: [Bash, Read, AskUserQuestion]
---

Invoke the `shotlist` skill (defined in SKILL.md) with the user's arguments: $ARGUMENTS

Follow the skill's full pipeline: preflight setup check → download via yt-dlp → extract frames at auto-scaled fps → pull captions or Whisper transcript → Read each frame → answer the user grounded in frames and transcript, filling the report's Shot Prompts and analysis markers. If the user provided no arguments, ask them for a video URL or local path before proceeding.
