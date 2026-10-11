import unittest
from pathlib import Path

from scripts.regional_fiscal_2022_2024 import load_regional_fiscal_sources


class RegionalFiscal2024FundBatchTests(unittest.TestCase):
    def test_archived_rating_tables_expose_exact_whole_prefecture_fund_values(self):
        values, sources = load_regional_fiscal_sources(Path(__file__).resolve().parents[1])

        expected = {
            ("CN-451300", "2024"): "16.87",  # 来宾市
            ("CN-421100", "2024"): "76.41",  # 黄冈市
            ("CN-632200", "2024"): "0.79",   # 海北藏族自治州
            ("CN-530900", "2024"): "20.23",  # 临沧市
            ("CN-140600", "2024"): "22.10",  # 朔州市
        }

        for key, expected_value in expected.items():
            self.assertIn(key, values)
            self.assertEqual(str(values[key]["gov_fund_revenue_100m"]), expected_value)
            self.assertEqual(values[key]["source_grade"], "B2")
            self.assertIn("全市", values[key]["source_locator"])

        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-B2-GUANGXI-REGIONAL-FISCAL-2024-FUND", source_ids)
        self.assertIn("SRC-B2-YUNNAN-REGIONAL-FISCAL-2024-FUND", source_ids)


if __name__ == "__main__":
    unittest.main()
