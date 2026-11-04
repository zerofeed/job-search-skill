"""Offline tests for the pure filtering logic in fetch_opportunities.py.

Run from the repo root:  python3 -m unittest discover -s tests -v
"""
import importlib.util
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills/job-search/scripts/fetch_opportunities.py"
spec = importlib.util.spec_from_file_location("fetch_opportunities", SCRIPT)
fo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fo)


class FilterState(unittest.TestCase):
    """Reset the module-level filter config around each test."""

    def setUp(self):
        fo.EXCLUDE_KEYWORDS, fo.LOCATION_ALLOW, fo.LOCATION_BLOCK = [], [], []

    tearDown = setUp


class TitleMatching(FilterState):
    def test_keyword_substring_is_case_insensitive(self):
        self.assertTrue(fo.matches_keywords("Senior Backend Engineer", ["backend engineer"]))

    def test_no_keyword_means_no_match(self):
        self.assertFalse(fo.matches_keywords("Office Manager", ["engineer"]))

    def test_exclude_beats_keyword(self):
        fo.EXCLUDE_KEYWORDS = ["frontend"]
        self.assertFalse(fo.matches_keywords("Senior Frontend Engineer", ["engineer"]))
        self.assertTrue(fo.matches_keywords("Senior Backend Engineer", ["engineer"]))


class LocationFilter(FilterState):
    def test_no_config_keeps_everything(self):
        self.assertTrue(fo.location_ok("Tokyo, Japan"))

    def test_allow_wins_over_block(self):
        fo.LOCATION_ALLOW, fo.LOCATION_BLOCK = ["latam"], ["united states"]
        self.assertTrue(fo.location_ok("LATAM / United States"))

    def test_block_rejects_onsite(self):
        fo.LOCATION_BLOCK = ["united states"]
        self.assertFalse(fo.location_ok("New York, United States"))

    def test_remote_or_empty_kept_when_unlisted(self):
        fo.LOCATION_ALLOW = ["latam"]
        self.assertTrue(fo.location_ok("Remote"))
        self.assertTrue(fo.location_ok(""))

    def test_unlisted_onsite_city_is_rejected(self):
        fo.LOCATION_ALLOW = ["latam"]
        self.assertFalse(fo.location_ok("Berlin, Germany"))


class WatchlistParsing(unittest.TestCase):
    def test_parses_ats_rows_and_skips_none(self):
        table = (
            "| Company | Domain | Career Page | ATS | Slug | Last checked |\n"
            "|---|---|---|---|---|---|\n"
            "| Acme | x | url | greenhouse | acme | — |\n"
            "| Beta | x | url | ashby | beta | — |\n"
            "| Gamma | x | url | none | — | — |\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(table)
        entries = fo.parse_watchlist(f.name)
        self.assertEqual([(e.empresa, e.ats, e.slug) for e in entries],
                         [("Acme", "greenhouse", "acme"), ("Beta", "ashby", "beta")])


class Dedup(unittest.TestCase):
    def test_same_url_ignoring_case_and_trailing_slash(self):
        rows = [{"url": "https://x.com/a/"}, {"url": "https://X.com/a"}, {"url": "https://x.com/b"}]
        self.assertEqual(len(fo.deduplicate(rows)), 2)


if __name__ == "__main__":
    unittest.main()
