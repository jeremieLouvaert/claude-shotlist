"""Tests for download.py — moodboard-save resolution (no network)."""
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import download  # noqa: E402

# Mirrors the measured cosmos.so element page (2026-09-02): site-level
# Organization/WebSite JSON-LD blocks whose sameAs lists Cosmos's own
# socials (the trap), an unparseable block, then the element's own block
# carrying the original post URL in sameAs.
COSMOS_PAGE = """<html><head>
<meta property="og:title" content="Found on Cosmos"/>
<script type="application/ld+json">{"@context":"https://schema.org",
"@type":"Organization","name":"Cosmos",
"sameAs":["https://www.instagram.com/cosmos/","https://x.com/thecosmos"]}</script>
<script type="application/ld+json">{"@context":"https://schema.org",
"@type":"WebSite","name":"Cosmos","url":"https://www.cosmos.so"}</script>
<script type="application/ld+json">{not json</script>
<script type="application/ld+json">{"@context":"https://schema.org",
"@type":"ImageObject","contentUrl":"https://cdn.cosmos.so/abc",
"sameAs":"https://www.instagram.com/reels/DUqonyBiSqM/"}</script>
</head><body></body></html>"""

NO_SOURCE_PAGE = COSMOS_PAGE.replace(
    '"sameAs":"https://www.instagram.com/reels/DUqonyBiSqM/"',
    '"name":"untraceable save"')


class TestMoodboardResolve(unittest.TestCase):

    def setUp(self):
        self._orig_fetch = download._fetch_page

    def tearDown(self):
        download._fetch_page = self._orig_fetch

    def test_cosmos_resolves_to_element_sameas_not_org_socials(self):
        download._fetch_page = lambda url: COSMOS_PAGE
        out = download.resolve_moodboard_url("https://www.cosmos.so/e/1550931937")
        self.assertEqual(out, "https://www.instagram.com/reels/DUqonyBiSqM/")

    def test_non_moodboard_url_passes_through_without_fetch(self):
        def boom(url):
            raise AssertionError("must not fetch non-moodboard URLs")
        download._fetch_page = boom
        url = "https://www.youtube.com/watch?v=AYrBZTHXGV8"
        self.assertEqual(download.resolve_moodboard_url(url), url)

    def test_cosmos_without_source_url_fails_loud(self):
        download._fetch_page = lambda url: NO_SOURCE_PAGE
        with self.assertRaises(SystemExit):
            download.resolve_moodboard_url("https://cosmos.so/e/123")

    def test_cosmos_fetch_failure_fails_loud_with_manual_hop(self):
        def fail(url):
            raise OSError("connection refused")
        download._fetch_page = fail
        with self.assertRaises(SystemExit):
            download.resolve_moodboard_url("https://cosmos.so/e/123")


if __name__ == "__main__":
    unittest.main()
