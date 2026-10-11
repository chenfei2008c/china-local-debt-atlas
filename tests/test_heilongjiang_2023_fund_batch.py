import re
import unittest

from scripts import collect_national_panel as national_panel


class Heilongjiang2023FundBatchTests(unittest.TestCase):
    def test_citywide_2023_fund_values_have_exact_evidence(self):
        expected = {
            "SRC-A2-MUDANJIANG-CITY-FUND-EXECUTION-2023": ("牡丹江市", "CN-231000", 2023, "60078", "execution"),
            "SRC-B2-QIQIHAER-CITY-FUND-2023": ("齐齐哈尔市", "CN-230200", 2023, "14.48", "reported"),
        }
        sources = {
            item["source_doc_id"]: item
            for item in national_panel.CITY_YEAR_FUND_SOURCES
            if item["source_doc_id"] in expected
        }
        self.assertEqual(set(sources), set(expected))
        for source_id, (city_name, city_id, year, value, data_status) in expected.items():
            source = sources[source_id]
            self.assertEqual((source["city_name"], source["city_id"], source["year"]), (city_name, city_id, year))
            self.assertIn(source["source_grade"], {"A2", "B2"})
            self.assertEqual(source["data_status"], data_status)
            excerpt = source["text_path"].read_text(encoding="utf-8")
            match = re.search(source["pattern"], re.sub(r"\s+", "", excerpt))
            self.assertIsNotNone(match, source_id)
            self.assertEqual(match.group(1), value)


if __name__ == "__main__":
    unittest.main()
