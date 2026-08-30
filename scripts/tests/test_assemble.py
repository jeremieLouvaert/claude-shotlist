"""Tests for assemble.py — clip matching, trimming, concat, EDL."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import assemble  # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

REMIX_MD = """---
title: Test
aspect_ratio: 16:9
---

# Remix — Test

## Global style

- **style_keeper:** Warm grade.

## Shots

### Shot 1 — [00:00] `frame_0001.jpg` (~1.5s in the original)

- **first_frame_prompt:** a
- **last_frame_prompt:** b
- **video_prompt:** c

### Shot 2 — [00:02] `frame_0002.jpg`

- **first_frame_prompt:** a
- **last_frame_prompt:** b
- **video_prompt:** c
"""


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class TestAssemble(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="watch-assemble-test-"))
        (self.tmp / "remix.md").write_text(REMIX_MD, encoding="utf-8")
        self.clips = self.tmp / "clips"
        self.clips.mkdir()
        for name, secs in (("shot01_seedance_00001_.mp4", 4), ("shot02_seedance_00001_.mp4", 4)):
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                 "-i", f"testsrc=duration={secs}:size=320x180:rate=24",
                 "-pix_fmt", "yuv420p", str(self.clips / name)],
                check=True, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_find_clip_matches_token_newest(self):
        extra = self.clips / "shot01_seedance_00002_.mp4"
        shutil.copyfile(self.clips / "shot01_seedance_00001_.mp4", extra)
        found = assemble.find_clip(self.clips, 1)
        self.assertEqual(found.name, "shot01_seedance_00002_.mp4")
        self.assertIsNone(assemble.find_clip(self.clips, 9))

    def test_assemble_trims_concats_and_writes_edl(self):
        argv = sys.argv
        sys.argv = ["assemble", str(self.tmp), "--clips", str(self.clips)]
        try:
            assemble.main()
        finally:
            sys.argv = argv
        out = self.tmp / "assembly" / "final.mp4"
        edl = self.tmp / "assembly" / "final.edl"
        self.assertTrue(out.exists())
        self.assertTrue(edl.exists())
        # shot 1 trimmed to 1.5s (reference duration), shot 2 full 4s
        info = assemble.probe(out)
        self.assertAlmostEqual(info["dur"], 5.5, delta=0.3)
        text = edl.read_text(encoding="utf-8")
        self.assertIn("TITLE: final", text)
        self.assertIn("FROM CLIP NAME: shot01_seedance_00001_.mp4", text)
        self.assertIn("FROM CLIP NAME: shot02_seedance_00001_.mp4", text)
        # two events, record TCs contiguous: event 2 starts where event 1 ends
        self.assertIn("00:00:01:12 00:00:05:12", text)  # 1.5s @ 24fps -> frame 36
        parts = sorted(p.name for p in (self.tmp / "assembly" / "parts").glob("*.mp4"))
        self.assertEqual(parts, ["shot01.mp4", "shot02.mp4"])

    def test_missing_clip_warns_but_cuts(self):
        (self.clips / "shot02_seedance_00001_.mp4").unlink()
        argv = sys.argv
        sys.argv = ["assemble", str(self.tmp), "--clips", str(self.clips)]
        try:
            assemble.main()
        finally:
            sys.argv = argv
        info = assemble.probe(self.tmp / "assembly" / "final.mp4")
        self.assertAlmostEqual(info["dur"], 1.5, delta=0.2)

    def test_refuses_unfilled_remix(self):
        (self.tmp / "remix.md").write_text(
            REMIX_MD.replace("- **video_prompt:** c",
                             "- **video_prompt:** <!-- pending Claude fill: x -->", 1),
            encoding="utf-8")
        with self.assertRaises(SystemExit):
            assemble.parse_shots(self.tmp / "remix.md")


if __name__ == "__main__":
    unittest.main()
