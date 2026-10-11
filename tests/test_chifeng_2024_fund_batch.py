import re
import unittest

from scripts import collect_national_panel as national_panel


class Chifeng2024FundBatchTests(unittest.TestCase):
    SOURCE_ID = "SRC-A2-CHIFENG-CITY-FUND-2024"

    def _source(self):
        return next(
            item
            for item in national_panel.CITY_YEAR_FUND_SOURCES
            if item["source_doc_id"] == self.SOURCE_ID
        )

    def test_source_is_full_city_final_decision_value(self):
        source = self._source()
        self.assertEqual((source["city_id"], source["year"]), ("CN-150400", 2024))
        self.assertEqual(source["city_name"], "赤峰市")
        self.assertEqual(source["source_grade"], "A2")
        self.assertEqual(source["source_format"], "pdf")
        self.assertEqual(source["data_status"], "final")
        text = re.sub(r"\s+", "", source["text_path"].read_text(encoding="utf-8"))
        match = re.search(source["pattern"], text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "430865")
        self.assertIn("全市口径", source["note"])

    def test_loader_normalizes_full_city_value_to_100m(self):
        values, source_rows = national_panel.load_city_year_fund_sources()
        value = values[("CN-150400", "2024")]
        self.assertEqual(str(value["gov_fund_revenue_100m"]), "43.09")
        self.assertEqual(value["source_grade"], "A2")
        self.assertEqual(value["data_status"], "final")
        self.assertEqual(
            sum(row["source_doc_id"] == self.SOURCE_ID for row in source_rows),
            1,
        )


if __name__ == "__main__":
    unittest.main()
