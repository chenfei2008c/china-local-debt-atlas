import re
import unittest

from scripts import collect_national_panel as national_panel


class Jiamusi2024FundBatchTests(unittest.TestCase):
    def test_citywide_2024_fund_value_has_exact_official_evidence(self):
        source_id = "SRC-A1-JIAMUSI-CITY-FUND-2024"
        source = next(
            item
            for item in national_panel.CITY_YEAR_FUND_SOURCES
            if item["source_doc_id"] == source_id
        )
        self.assertEqual((source["city_id"], source["year"]), ("CN-230800", 2024))
        self.assertEqual(source["source_grade"], "A1")
        text = re.sub(r"\s+", "", source["text_path"].read_text(encoding="utf-8"))
        match = re.search(source["pattern"], text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "174993")


if __name__ == "__main__":
    unittest.main()
