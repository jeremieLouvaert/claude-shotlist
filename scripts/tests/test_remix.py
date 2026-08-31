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

    def _emit(self, **kw) -> dict:
        remix.write_remix(self.tmp, "cows become tractors", "16:9")
        self._fill(self.tmp / "remix.md")
        remix.emit(self.tmp, **kw)
        return json.loads((self.tmp / "comfy" / "remix_workflow.json").read_text(encoding="utf-8"))

    def test_emit_builds_valid_combined_graph(self):
        w = self._emit()
        indir = self.tmp / "comfy" / "input"
        self.assertTrue((indir / "shot01_ref.jpg").exists())
        self.assertTrue((indir / "shot02_ref.jpg").exists())

        ids = [n["id"] for n in w["nodes"]]
        self.assertEqual(len(ids), len(set(ids)), "node ids must be unique")
        from collections import Counter
        counts = Counter(n["type"] for n in w["nodes"])
        # 2 shots: 1 LoadImage each (the reference frame; picks flow wirelessly)
        self.assertEqual(counts["LoadImage"], 2 * 1)
        # wireless: 4 sends per shot (2 halves x 2 engines, shared channel),
        # 3 gets per shot (stills pass-2 conditioning + video first/last)
        self.assertEqual(counts["WirelessSend"], 2 * 4)
        self.assertEqual(counts["WirelessGet"], 2 * 3)
        # every generation branch is wrapped in the hash-vault triad:
        # per shot 2 halves x 2 stills engines + 2 video engines = 6 triads
        for t in ("DeterministicHashVault", "HashVaultSave", "LazyAPISwitch"):
            self.assertEqual(counts[t], 2 * 6, t)
        self.assertEqual(counts["GeminiImage2Node"], 2 * 2)
        self.assertEqual(counts["OpenAIGPTImageNodeV2"], 2 * 2)
        self.assertEqual(counts["ByteDance2FirstLastFrameNode"], 2)
        self.assertEqual(counts["GeminiVideoOmni"], 2)
        self.assertEqual(counts["SaveImage"], 2 * 4)
        self.assertEqual(counts["SaveVideo"], 2 * 2)
        # 2 groups per shot + 2 section super-groups
        self.assertEqual(len(w["groups"]), 2 * 2 + 2)
        byid = {n["id"]: n for n in w["nodes"]}
        for lid, src, oslot, dst, islot, _typ in w["links"]:
            self.assertIn(lid, byid[src]["outputs"][oslot]["links"])
            self.assertEqual(byid[dst]["inputs"][islot]["link"], lid)
        self.assertEqual(w["last_node_id"], max(ids))
        # image savers consume the wireless send's passthrough (his pattern);
        # video savers consume the vault switch
        for n in w["nodes"]:
            if n["type"] in ("SaveImage", "SaveVideo"):
                lid = n["inputs"][0]["link"]
                src = next(l for l in w["links"] if l[0] == lid)[1]
                expect = "WirelessSend" if n["type"] == "SaveImage" else "LazyAPISwitch"
                self.assertEqual(byid[src]["type"], expect)

    def test_last_frame_wireless_chained_from_first(self):
        w = self._emit()
        byid = {n["id"]: n for n in w["nodes"]}
        linkmap = {l[0]: l for l in w["links"]}
        def src_of(node, in_name):
            link = next(i["link"] for i in node["inputs"] if i["name"] == in_name)
            return byid[linkmap[link][1]]
        firsts, lasts = 0, 0
        for n in w["nodes"]:
            if n["type"] != "GeminiImage2Node":
                continue
            cond = src_of(n, "images")
            if cond["type"] == "LoadImage":
                self.assertTrue(cond["widgets_values"][0].endswith("_ref.jpg"))
                firsts += 1
            else:
                self.assertEqual(cond["type"], "WirelessGet")
                self.assertTrue(cond["widgets_values"][0].endswith("_first"))
                lasts += 1
        self.assertEqual((firsts, lasts), (2, 2))
        # sends per shot share the channel: shotNN_first from both engines
        chans = sorted(n["widgets_values"][0] for n in w["nodes"] if n["type"] == "WirelessSend")
        self.assertEqual(chans, ["shot01_first", "shot01_first", "shot01_last", "shot01_last",
                                 "shot02_first", "shot02_first", "shot02_last", "shot02_last"])

    def test_vault_keyed_on_prompt_and_conditioning(self):
        w = self._emit()
        byid = {n["id"]: n for n in w["nodes"]}
        linkmap = {l[0]: l for l in w["links"]}
        for n in w["nodes"]:
            if n["type"] != "DeterministicHashVault":
                continue
            wired = {i["name"] for i in n["inputs"] if i.get("link") is not None}
            self.assertIn("payload_string", wired)
            self.assertIn("any_input", wired, "conditioning image must be in the cache key")

    def test_stills_wiring_widgets_and_engine_muting(self):
        w = self._emit()  # default: nano active, gpt muted
        nano = [n for n in w["nodes"] if n["type"] == "GeminiImage2Node"]
        gpt = [n for n in w["nodes"] if n["type"] == "OpenAIGPTImageNodeV2"]
        self.assertEqual(len(nano), 4)  # 2 shots x first+last
        self.assertEqual(len(gpt), 4)
        for n in nano:
            self.assertEqual(n["mode"], remix.MODE_ACTIVE)
            self.assertEqual(n["widgets_values"][remix.GEMINI_W_MODEL],
                             "gemini-3-pro-image-preview")
            self.assertEqual(n["widgets_values"][remix.GEMINI_W_ASPECT], "16:9")
            wired = {i["name"] for i in n["inputs"] if i.get("link") is not None}
            self.assertIn("images", wired)
            self.assertIn("prompt", wired)
        for n in gpt:
            self.assertEqual(n["mode"], remix.MODE_MUTED)
            self.assertEqual((n["widgets_values"][remix.GPT_W_WIDTH],
                              n["widgets_values"][remix.GPT_W_HEIGHT]), (2560, 1440))
            wired = {i["name"] for i in n["inputs"] if i.get("link") is not None}
            self.assertIn("model.images.image_1", wired)
            self.assertIn("prompt", wired)
        saves = sorted(n["widgets_values"][0] for n in w["nodes"]
                       if n["type"] == "SaveImage" and "_nano" in n["widgets_values"][0])
        self.assertEqual(saves, ["remix/shot01_first_nano", "remix/shot01_last_nano",
                                 "remix/shot02_first_nano", "remix/shot02_last_nano"])
        prompts = [n["widgets_values"][0] for n in w["nodes"]
                   if n["type"] == "PrimitiveStringMultiline"
                   and not n["widgets_values"][0].startswith("engine:")]
        self.assertTrue(all("Style: " in p for p in prompts),
                        "style_keeper must be appended to every stills prompt")

    def test_vault_cache_keys_unique_per_engine(self):
        w = self._emit()
        byid = {n["id"]: n for n in w["nodes"]}
        linkmap = {l[0]: l for l in w["links"]}
        keys = []
        for n in w["nodes"]:
            if n["type"] != "DeterministicHashVault":
                continue
            srcs = frozenset(linkmap[i["link"]][1] for i in n["inputs"]
                             if i.get("link") is not None)
            keys.append(srcs)
            # every vault must include an engine tag in its key
            tag_types = [byid[x]["widgets_values"][0] for x in srcs
                         if byid[x]["type"] == "PrimitiveStringMultiline"
                         and str(byid[x]["widgets_values"][0]).startswith("engine:")]
            self.assertEqual(len(tag_types), 1, "each vault needs exactly one engine tag")
        self.assertEqual(len(keys), len(set(keys)),
                         "two vaults share identical key inputs -> cache collision")

    def test_video_wiring_and_engine_muting(self):
        w = self._emit(video_engine="omni")  # omni active, seedance muted
        bd = [n for n in w["nodes"] if n["type"] == "ByteDance2FirstLastFrameNode"]
        omni = [n for n in w["nodes"] if n["type"] == "GeminiVideoOmni"]
        self.assertEqual(len(bd), 2)
        self.assertEqual(len(omni), 2)
        by_seed = {n["widgets_values"][6]: n for n in bd}
        # shot 1 has a 2.0s original -> clamped to Seedance's 4s minimum;
        # shot 2 has no duration -> schema default 5
        self.assertEqual(by_seed[1]["widgets_values"][3], 4)
        self.assertEqual(by_seed[2]["widgets_values"][3], 5)
        for n in bd:
            self.assertEqual(n["mode"], remix.MODE_MUTED)
            self.assertEqual(n["widgets_values"][remix.BYTEDANCE_W_MODEL], "Seedance 2.5")
            # live-schema 2.5 layout: output_format combo at index 5
            self.assertEqual(n["widgets_values"][5], "mp4")
            self.assertEqual(len(n["widgets_values"]), 11)
            wired = {i["name"]: i["link"] for i in n["inputs"]}
            self.assertIsNotNone(wired["first_frame"])
            self.assertIsNotNone(wired["last_frame"])
            self.assertIsNotNone(wired["model.prompt"])
            self.assertNotEqual(wired["first_frame"], wired["last_frame"])
        for n in omni:
            self.assertEqual(n["mode"], remix.MODE_ACTIVE)
            self.assertEqual(n["widgets_values"][remix.OMNI_W_MODEL], "Omni Flash 1.1")
            wired = {i["name"]: i["link"] for i in n["inputs"]}
            self.assertIsNotNone(wired["model.images.image_1"])
            self.assertIsNotNone(wired["model.images.image_2"])
            self.assertIsNotNone(wired["model.prompt"])
            self.assertNotEqual(wired["model.images.image_1"], wired["model.images.image_2"])
        gets = sorted(n["widgets_values"][0] for n in w["nodes"] if n["type"] == "WirelessGet")
        # shotNN_first appears twice: stills pass-2 conditioning + video input
        self.assertEqual(gets, ["shot01_first", "shot01_first", "shot01_last",
                                "shot02_first", "shot02_first", "shot02_last"])

    def test_no_node_overlaps_and_section_colors(self):
        w = self._emit()
        boxes = []
        for n in w["nodes"]:
            x, y = n["pos"]
            wd, h = n["size"]
            boxes.append((n["type"], x, y, x + wd, y + h))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                intersects = a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]
                self.assertFalse(intersects, f"nodes overlap: {a[0]} vs {b[0]}")
        # stills and video sections use distinct group colors
        colors = {g["color"] for g in w["groups"]}
        self.assertEqual(len(colors), 4, "per-shot + section colors, stills vs video")

    def test_gpt_stills_engine_active_when_selected(self):
        w = self._emit(stills_engine="gpt")
        for n in w["nodes"]:
            if n["type"] == "OpenAIGPTImageNodeV2":
                self.assertEqual(n["mode"], remix.MODE_ACTIVE)
            if n["type"] == "GeminiImage2Node":
                self.assertEqual(n["mode"], remix.MODE_MUTED)


if __name__ == "__main__":
    unittest.main()
