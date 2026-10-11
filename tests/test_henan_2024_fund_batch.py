import re
import unittest

from scripts import collect_national_panel as national_panel


class Henan2024FundBatchTests(unittest.TestCase):
    def _source(self, source_id):
        return next(
            item
            for item in national_panel.CITY_YEAR_FUND_SOURCES
            if item["source_doc_id"] == source_id
        )

    def test_xuchang_2024_citywide_fund_value(self):
        source = self._source("SRC-A1-XUCHANG-CITY-FUND-2024")
        self.assertEqual((source["city_id"], source["year"]), ("CN-411000", 2024))
        self.assertEqual(source["source_grade"], "A1")
        text = re.sub(r"\s+", "", source["text_path"].read_text(encoding="utf-8"))
        match = re.search(source["pattern"], text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "78.7")

    def test_nanyang_2024_citywide_fund_value(self):
        source = self._source("SRC-A1-NANYANG-CITY-FUND-2024")
        self.assertEqual((source["city_id"], source["year"]), ("CN-411300", 2024))
        self.assertEqual(source["source_grade"], "A1")
        text = re.sub(r"\s+", "", source["text_path"].read_text(encoding="utf-8"))
        match = re.search(source["pattern"], text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "117.7")


if __name__ == "__main__":
    unittest.main()
