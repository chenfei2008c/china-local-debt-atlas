import re
import unittest

from scripts import collect_national_panel as national_panel


class Qinghai2025FundBatchTests(unittest.TestCase):
    EXPECTED = {
        "CN-630100": ("西宁市", "17.91"),
        "CN-632800": ("海西蒙古族藏族自治州", "4.87"),
        "CN-630200": ("海东市", "3.58"),
        "CN-632500": ("海南藏族自治州", "1.10"),
        "CN-632300": ("黄南藏族自治州", "0.21"),
        "CN-632200": ("海北藏族自治州", "0.67"),
        "CN-632700": ("玉树藏族自治州", "0.17"),
        "CN-632600": ("果洛藏族自治州", "0.28"),
    }

    def test_all_eight_city_year_sources_are_exact_b2_table_values(self):
        sources = {
            item["city_id"]: item
            for item in national_panel.CITY_YEAR_FUND_SOURCES
            if item["year"] == 2025 and item["city_id"] in self.EXPECTED
        }
        self.assertEqual(set(sources), set(self.EXPECTED))
        for city_id, (city_name, expected) in self.EXPECTED.items():
            source = sources[city_id]
            self.assertEqual(source["city_name"], city_name)
            self.assertEqual(source["source_grade"], "B2")
            self.assertEqual(source["source_format"], "image")
            text = re.sub(r"\s+", "", source["text_path"].read_text(encoding="utf-8"))
            match = re.search(source["pattern"], text)
            self.assertIsNotNone(match)
            self.assertEqual(match.group(1), expected)

    def test_loader_normalizes_all_eight_values_to_100m(self):
        values, source_rows = national_panel.load_city_year_fund_sources()
        qinghai_rows = [
            row for row in source_rows if row["source_doc_id"].startswith("SRC-B2-QINGHAI-CITY-FUND-2025-")
        ]
        self.assertEqual(len(qinghai_rows), 8)
        self.assertTrue(all(row["mime_type"] == "image/jpeg" for row in qinghai_rows))
        for city_id, (_, expected) in self.EXPECTED.items():
            value = values[(city_id, "2025")]
            self.assertEqual(str(value["gov_fund_revenue_100m"]), expected)
            self.assertEqual(value["source_grade"], "B2")
            self.assertEqual(value["data_status"], "execution")


if __name__ == "__main__":
    unittest.main()
