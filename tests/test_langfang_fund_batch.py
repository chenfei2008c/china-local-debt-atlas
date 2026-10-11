import re
import unittest

from scripts import collect_national_panel as national_panel


class LangfangFundBatchTests(unittest.TestCase):
    def test_2023_citywide_fund_value(self):
        source = self._source("SRC-A2-LANGFANG-CITY-FUND-2023")
        self.assertEqual((source["city_id"], source["year"]), ("CN-131000", 2023))
        self.assertEqual(source["source_grade"], "A2")
        text = re.sub(r"\s+", "", source["text_path"].read_text(encoding="utf-8"))
        match = re.search(source["pattern"], text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "1356286")

    def test_2024_citywide_fund_value(self):
        source = self._source("SRC-A2-LANGFANG-CITY-FUND-2024")
        self.assertEqual((source["city_id"], source["year"]), ("CN-131000", 2024))
        self.assertEqual(source["source_grade"], "A2")
        text = re.sub(r"\s+", "", source["text_path"].read_text(encoding="utf-8"))
        match = re.search(source["pattern"], text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "82.8")

    @staticmethod
    def _source(source_id):
        return next(
            item
            for item in national_panel.CITY_YEAR_FUND_SOURCES
            if item["source_doc_id"] == source_id
        )


if __name__ == "__main__":
    unittest.main()
