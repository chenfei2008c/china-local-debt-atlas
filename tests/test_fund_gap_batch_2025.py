import re
import unittest

from scripts import collect_national_panel as national_panel


class FundGapBatch2025Tests(unittest.TestCase):
    def test_new_gap_values_have_exact_curated_evidence(self):
        expected = {
            "SRC-B2-JILIN-FUND-2025-220300": ("四平市", "CN-220300", 2025, "3.46"),
            "SRC-B2-JILIN-FUND-2025-220400": ("辽源市", "CN-220400", 2025, "7.78"),
            "SRC-B2-JILIN-FUND-2025-220500": ("通化市", "CN-220500", 2025, "22.60"),
            "SRC-B2-JILIN-FUND-2025-220600": ("白山市", "CN-220600", 2025, "4.61"),
            "SRC-B2-JILIN-FUND-2025-222400": ("延边朝鲜族自治州", "CN-222400", 2025, "15.95"),
            "SRC-A2-YANGQUAN-FUND-2024": ("阳泉市", "CN-140300", 2024, "15.66"),
            "SRC-B2-CHENZHOU-FUND-2024": ("郴州市", "CN-431000", 2024, "135.96"),
        }
        sources = {
            item["source_doc_id"]: item
            for item in national_panel.CITY_YEAR_FUND_SOURCES
            if item["source_doc_id"] in expected
        }
        self.assertEqual(set(sources), set(expected))
        for source_id, (city_name, city_id, year, value) in expected.items():
            source = sources[source_id]
            self.assertEqual((source["city_name"], source["city_id"], source["year"]), (city_name, city_id, year))
            self.assertIn(source["source_grade"], {"A2", "B2"})
            excerpt = source["text_path"].read_text(encoding="utf-8")
            match = re.search(source["pattern"], re.sub(r"\s+", "", excerpt))
            self.assertIsNotNone(match, source_id)
            self.assertEqual(match.group(1), value)

        values, _ = national_panel.load_city_year_fund_sources()
        for _, city_id, year, value in expected.values():
            self.assertEqual(str(values[(city_id, str(year))]["gov_fund_revenue_100m"]), value)

    def test_sichuan_regional_fiscal_source_carries_neijiang_fund(self):
        source = next(
            item
            for item in national_panel.CITY_YEAR_FUND_SOURCES
            if item["source_doc_id"] == "SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-NEIJIANG"
        )
        self.assertEqual(source["city_id"], "CN-511000")
        self.assertEqual(source["pattern"], r"内江市｜[^｜]+｜[^｜]+｜([0-9.]+)｜")


if __name__ == "__main__":
    unittest.main()
