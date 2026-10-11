import re
import unittest

from scripts import collect_national_panel as national_panel


class Shijiazhuang2024FundBatchTests(unittest.TestCase):
    def test_citywide_2024_fund_value_has_exact_official_evidence(self):
        source_id = "SRC-A1-SHIJIAZHUANG-CITY-FUND-2024"
        sources = {
            item["source_doc_id"]: item
            for item in national_panel.CITY_YEAR_FUND_SOURCES
            if item["source_doc_id"] == source_id
        }
        self.assertIn(source_id, sources)
        source = sources[source_id]
        self.assertEqual(
            (source["city_name"], source["city_id"], source["year"]),
            ("石家庄市", "CN-130100", 2024),
        )
        self.assertEqual(source["source_grade"], "A1")
        self.assertEqual(source["data_status"], "final")
        excerpt = source["text_path"].read_text(encoding="utf-8")
        match = re.search(source["pattern"], re.sub(r"\s+", "", excerpt))
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "3792041")


if __name__ == "__main__":
    unittest.main()
