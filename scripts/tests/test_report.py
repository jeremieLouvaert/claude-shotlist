"""Tests for report.md emission."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from report import write_report  # noqa: E402


class TestReport(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="watch-report-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_writes_all_required_sections(self):
        out = write_report(
            out_path=self.tmp / "report.md",
            source="https://youtu.be/test",
            title="Test Video",
            duration_seconds=125.0,
            intent="studying hook patterns",
            transcript_segments=[
                {"start": 0.0, "end": 2.0, "text": "Hello world."},
                {"start": 2.0, "end": 5.0, "text": "Second segment."},
            ],
            transcript_source="captions",
            all_frames=[
                {"index": 0, "timestamp_seconds": 0.0, "path": "/tmp/f1.jpg"},
                {"index": 1, "timestamp_seconds": 5.0, "path": "/tmp/f2.jpg"},
                {"index": 2, "timestamp_seconds": 60.0, "path": "/tmp/f3.jpg"},
            ],
            hero_frames=[
                {"index": 0, "timestamp_seconds": 0.0, "path": "/tmp/f1.jpg"},
                {"index": 1, "timestamp_seconds": 5.0, "path": "/tmp/f2.jpg"},
            ],
            pacing={
                "shot_count": 6,
                "cuts_per_minute": 2.88,
                "mean_shot_length": 20.83,
                "median_shot_length": 18.5,
                "shots": [],
            },
            hook={"frames": [], "words": [], "ran": False, "skipped_reason": "video <30s"},
        )

        text = out.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("source: https://youtu.be/test", text)
        self.assertIn("intent: studying hook patterns", text)
        self.assertIn("hero_frames:", text)
        for header in (
            "# Test Video",
            "## TL;DR",
            "## Key moments",
            "## Hook microscope",
            "## Editorial profile",
            "## Quotable moments",
            "## Entities mentioned",
            "## Concepts surfaced",
            "## Transcript",
        ):
            self.assertIn(header, text, f"missing: {header}")
        self.assertIn("<!-- pending Claude fill", text)
        self.assertIn("Cuts/min: 2.88", text)
        self.assertIn("Mean shot length: 20.83", text)
        self.assertIn("Hello world.", text)


def _base_payload(all_frames, hero_frames):
    return dict(
        source="fixture://test",
        title="Shot Prompt Test",
        duration_seconds=24.0,
        intent="creative direction",
        transcript_segments=[{"start": 0.0, "end": 2.0, "text": "Hello."}],
        transcript_source="captions",
        all_frames=all_frames,
        hero_frames=hero_frames,
        pacing={"shot_count": len(all_frames), "cuts_per_minute": 30.0,
                "mean_shot_length": 2.0, "median_shot_length": 2.0, "shots": []},
        hook={"frames": [], "words": [], "ran": False, "skipped_reason": "test"},
    )


def _scene_frames(n, step=2.0):
    return [
        {"index": i, "timestamp_seconds": i * step,
         "path": f"/tmp/frame_{i:04d}.jpg", "source": "scene-change"}
        for i in range(n)
    ]


class TestShotPrompts(unittest.TestCase):
    """Report-schema logic for the Shot Prompts section.

    Fixed frame paths + a transcript fixture only — no video, no download.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="watch-shotprompt-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, all_frames, hero_frames, **kw):
        out = write_report(
            out_path=self.tmp / "report.md",
            **_base_payload(all_frames, hero_frames), **kw,
        )
        return out.read_text(encoding="utf-8")

    def test_scene_mode_one_entry_per_frame(self):
        frames = _scene_frames(12)
        text = self._write(frames, frames[:1])
        self.assertIn("## Shot prompts", text)
        self.assertEqual(text.count("### Shot "), 12)
        # both fields present per entry, as pending markers
        self.assertEqual(text.count("- **image_prompt:** <!-- pending Claude fill"), 12)
        self.assertEqual(text.count("- **motion_note:** <!-- pending Claude fill"), 12)
        # timestamp + frame filename + duration-to-next-cut on the heading
        self.assertIn("### Shot 1 — [00:00] `frame_0000.jpg` (~2.0s to next cut)", text)
        # last shot's span runs to video end (24.0 - 22.0)
        self.assertIn("### Shot 12 — [00:22] `frame_0011.jpg` (~2.0s to next cut)", text)

    def test_section_sits_between_editorial_and_quotable(self):
        frames = _scene_frames(3)
        text = self._write(frames, frames[:1])
        i_editorial = text.index("## Editorial profile")
        i_shots = text.index("## Shot prompts")
        i_quotable = text.index("## Quotable moments")
        self.assertTrue(i_editorial < i_shots < i_quotable)

    def test_uniform_mode_covers_hero_frames_only(self):
        # no "source" key = uniform sampling; per-shot boundaries don't exist
        frames = [
            {"index": i, "timestamp_seconds": float(i), "path": f"/tmp/u_{i}.jpg"}
            for i in range(20)
        ]
        heroes = [frames[0], frames[10]]
        text = self._write(frames, heroes)
        self.assertIn("## Shot prompts", text)
        self.assertIn("uniform-sampled", text)
        self.assertEqual(text.count("### Shot "), 2)
        # no duration span in uniform mode
        self.assertNotIn("to next cut", text)

    def test_empty_frames_emits_note_not_entries(self):
        text = self._write([], [])
        self.assertIn("## Shot prompts", text)
        self.assertIn("No frames extracted", text)
        self.assertEqual(text.count("### Shot "), 0)

    def test_flag_off_omits_section_and_matches_upstream_shape(self):
        frames = _scene_frames(5)
        text = self._write(frames, frames[:1], include_shot_prompts=False)
        self.assertNotIn("## Shot prompts", text)
        self.assertNotIn("image_prompt", text)
        # every upstream section still present and ordered
        order = ["## TL;DR", "## Key moments", "## Hook microscope",
                 "## Editorial profile", "## Quotable moments",
                 "## Entities mentioned", "## Concepts surfaced",
                 "## Transcript", "## All frames"]
        idx = [text.index(h) for h in order]
        self.assertEqual(idx, sorted(idx))


if __name__ == "__main__":
    unittest.main()
