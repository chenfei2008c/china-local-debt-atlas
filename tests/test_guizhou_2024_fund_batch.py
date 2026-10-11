import re
import unittest

from scripts import collect_national_panel as national_panel


class Guizhou2024FundBatchTests(unittest.TestCase):
    EXPECTED = {
        "CN-522300": ("黔西南布依族苗族自治州", "167.00"),
        "CN-522600": ("黔东南苗族侗族自治州", "106.44"),
    }

    def test_two_prefecturewide_values_are_exact_table_values(self):
        sources = {
            item["city_id"]: item
            for item in national_panel.CITY_YEAR_FUND_SOURCES
            if item["year"] == 2024 and item["city_id"] in self.EXPECTED
        }
        self.assertEqual(set(sources), set(self.EXPECTED))
        for city_id, (city_name, expected) in self.EXPECTED.items():
            source = sources[city_id]
            self.assertEqual(source["city_name"], city_name)
            self.assertEqual(source["source_grade"], "B2")
            self.assertEqual(source["source_format"], "pdf")
            text = re.sub(r"\s+", "", source["text_path"].read_text(encoding="utf-8"))
            match = re.search(source["pattern"], text)
            self.assertIsNotNone(match)
            self.assertEqual(match.group(1), expected)

    def test_loader_normalizes_values_and_preserves_execution_status(self):
        values, source_rows = national_panel.load_city_year_fund_sources()
        batch_rows = [
            row
            for row in source_rows
            if row["source_doc_id"].startswith("SRC-B2-GUIZHOU-CITY-FUND-2024-")
        ]
        self.assertEqual(len(batch_rows), 2)
        for city_id, (_, expected) in self.EXPECTED.items():
            value = values[(city_id, "2024")]
            self.assertEqual(str(value["gov_fund_revenue_100m"]), expected)
            self.assertEqual(value["source_grade"], "B2")
            self.assertEqual(value["data_status"], "execution")


if __name__ == "__main__":
    unittest.main()
