"""Tests for remix.py — remix.md schema and ComfyUI workflow emission."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import remix  # noqa: E402

FILLED_REPORT = """---
source: https://example.test/v
title: Test Video
---

# Test Video

## Shot prompts

### Shot 1 — [00:00] `frame_0001.jpg` (~2.0s to next cut)

- **image_prompt:** A red barn at dawn, wide shot.
- **motion_note:** Slow push-in.

### Shot 2 — [00:02] `frame_0002.jpg`

- **image_prompt:** Close-up of hands on a rope.
- **motion_note:** Static hold.

## Quotable moments

None.
"""


class TestRemix(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="watch-remix-test-"))
        (self.tmp / "report.md").write_text(FILLED_REPORT, encoding="utf-8")
        frames = self.tmp / "frames"
        frames.mkdir()
        for n in ("frame_0001.jpg", "frame_0002.jpg"):
            (frames / n).write_bytes(b"\xff\xd8\xff\xe0fakejpg")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fill(self, path: Path):
        text = path.read_text(encoding="utf-8")
        i = 0

        def repl(_m):
            nonlocal i
            i += 1
            return f"Filled content number {i}."

        path.write_text(remix.PENDING_RE.sub(repl, text), encoding="utf-8")

    def test_write_remix_schema(self):
        out = remix.write_remix(self.tmp, "cows become tractors", "16:9")
        text = out.read_text(encoding="utf-8")
        self.assertEqual(text.count("### Shot "), 2)
        self.assertEqual(len(remix.PENDING_RE.findall(text)), 2 * 3 + 1)
        self.assertIn("- **style_keeper:**", text)
        self.assertIn("aspect_ratio: 16:9", text)
        self.assertIn("- **original_brief:** A red barn at dawn, wide shot.", text)
        # duration carried when the report had one, omitted when it didn't
        self.assertIn("(~2.0s in the original)", text)

    def test_report_with_pending_markers_refuses(self):
        (self.tmp / "report.md").write_text(
            FILLED_REPORT.replace(
                "A red barn at dawn, wide shot.",
                "<!-- pending Claude fill: x -->",
            ),
            encoding="utf-8",
        )
        with self.assertRaises(SystemExit):
            remix.write_remix(self.tmp, "brief", "16:9")

    def test_emit_refuses_unfilled_remix(self):
        remix.write_remix(self.tmp, "brief", "16:9")
        with self.assertRaises(SystemExit):
            remix.emit(self.tmp)

    def test_emit_builds_valid_graphs(self):
        remix.write_remix(self.tmp, "cows become tractors", "16:9")
        self._fill(self.tmp / "remix.md")
        remix.emit(self.tmp)

        indir = self.tmp / "comfy" / "input"
        self.assertTrue((indir / "shot01_ref.jpg").exists())
        self.assertTrue((indir / "shot02_ref.jpg").exists())

        stills = json.loads((self.tmp / "comfy" / "stills_workflow.json").read_text(encoding="utf-8"))
        video = json.loads((self.tmp / "comfy" / "video_workflow.json").read_text(encoding="utf-8"))

        for w, per_shot_nodes, per_shot_links in ((stills, 7, 6), (video, 5, 4)):
            ids = [n["id"] for n in w["nodes"]]
            self.assertEqual(len(ids), len(set(ids)), "node ids must be unique")
            self.assertEqual(len(w["nodes"]), 2 * per_shot_nodes)
            self.assertEqual(len(w["links"]), 2 * per_shot_links)
            self.assertEqual(len(w["groups"]), 2)
            byid = {n["id"]: n for n in w["nodes"]}
            for lid, src, oslot, dst, islot, _typ in w["links"]:
                self.assertIn(lid, byid[src]["outputs"][oslot]["links"])
                self.assertEqual(byid[dst]["inputs"][islot]["link"], lid)
            self.assertEqual(w["last_node_id"], max(ids))

    def test_stills_graph_wiring_and_widgets(self):
        remix.write_remix(self.tmp, "cows become tractors", "16:9")
        self._fill(self.tmp / "remix.md")
        remix.emit(self.tmp)
        w = json.loads((self.tmp / "comfy" / "stills_workflow.json").read_text(encoding="utf-8"))
        gemini = [n for n in w["nodes"] if n["type"] == "GeminiImage2Node"]
        self.assertEqual(len(gemini), 4)  # 2 shots x first+last
        for n in gemini:
            self.assertEqual(n["widgets_values"][remix.GEMINI_W_ASPECT], "16:9")
            # both image conditioning and prompt must be wired
            wired = {i["name"] for i in n["inputs"] if i.get("link") is not None}
            self.assertIn("images", wired)
            self.assertIn("prompt", wired)
        saves = sorted(n["widgets_values"][0] for n in w["nodes"] if n["type"] == "SaveImage")
        self.assertEqual(saves, ["remix/shot01_first", "remix/shot01_last",
                                 "remix/shot02_first", "remix/shot02_last"])
        prompts = [n["widgets_values"][0] for n in w["nodes"]
                   if n["type"] == "PrimitiveStringMultiline"]
        self.assertTrue(all("Style: " in p for p in prompts),
                        "style_keeper must be appended to every stills prompt")

    def test_video_graph_wiring(self):
        remix.write_remix(self.tmp, "brief", "16:9")
        self._fill(self.tmp / "remix.md")
        remix.emit(self.tmp)
        w = json.loads((self.tmp / "comfy" / "video_workflow.json").read_text(encoding="utf-8"))
        byid = {n["id"]: n for n in w["nodes"]}
        bd = [n for n in w["nodes"] if n["type"] == "ByteDance2FirstLastFrameNode"]
        self.assertEqual(len(bd), 2)
        for n in bd:
            wired = {i["name"]: i["link"] for i in n["inputs"]}
            self.assertIsNotNone(wired["first_frame"])
            self.assertIsNotNone(wired["last_frame"])
            self.assertIsNotNone(wired["model.prompt"])
            self.assertNotEqual(wired["first_frame"], wired["last_frame"])
        loads = sorted(n["widgets_values"][0] for n in w["nodes"] if n["type"] == "LoadImage")
        self.assertEqual(loads, ["shot01_first.png", "shot01_last.png",
                                 "shot02_first.png", "shot02_last.png"])


if __name__ == "__main__":
    unittest.main()
