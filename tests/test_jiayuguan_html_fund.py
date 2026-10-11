import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collect_national_panel as panel  # noqa: E402


class JiayuguanHtmlFundTest(unittest.TestCase):
    def test_archived_html_matches_fund_pattern_after_tag_normalization(self):
        text_path = ROOT / "raw/province_fiscal/2025/official/jiayuguan_2025_budget_report_excerpt.txt"
        text = text_path.read_text(encoding="utf-8")
        compact = re.sub(r"\\s+", "", re.sub(r"<[^>]+>", "", text))
        config = next(
            item
            for item in panel.CITY_YEAR_FISCAL_SOURCES
            if item["source_doc_id"] == "SRC-A2-JIAYUGUAN-CITY-FUND-2025"
        )
        match = re.search(config["patterns"]["gov_fund_revenue_100m"], compact)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "2.06")


if __name__ == "__main__":
    unittest.main()
