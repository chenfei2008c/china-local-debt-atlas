import re
import unittest

from scripts import collect_national_panel as national_panel


class CityYearFundBatchTests(unittest.TestCase):
    def test_new_fund_batch_has_exact_curated_evidence(self):
        expected = {
            "SRC-A2-ANKANG-CITY-FUND-2023": ("安康市", 2023, "34.32"),
            "SRC-B2-MAANSHAN-CITY-FUND-2023": ("马鞍山市", 2023, "88.1"),
            "SRC-B2-NANPING-CITY-FUND-2023": ("南平市", 2023, "68.04"),
            "SRC-A2-YINCHUAN-CITY-FUND-2023": ("银川市", 2023, "42.57"),
            "SRC-A2-GUYUAN-CITY-FUND-2023": ("固原市", 2023, "3.8"),
            "SRC-A2-YINCHUAN-CITY-FUND-2024": ("银川市", 2024, "47.67"),
            "SRC-A2-ZHONGWEI-CITY-FUND-2024": ("中卫市", 2024, "11.45"),
            "SRC-A2-DIQING-CITY-FUND-2024": ("迪庆藏族自治州", 2024, "0.38"),
            "SRC-A2-SHIZUISHAN-CITY-FUND-2024": ("石嘴山市", 2024, "3.41"),
            "SRC-A2-LASA-CITY-FUND-2024": ("拉萨市", 2024, "21.803"),
        }
        sources = {
            item["source_doc_id"]: item
            for item in national_panel.CITY_YEAR_FUND_SOURCES
            if item["source_doc_id"] in expected
        }
        self.assertEqual(set(sources), set(expected))
        for source_id, (city_name, year, value) in expected.items():
            source = sources[source_id]
            self.assertEqual(source["city_name"], city_name)
            self.assertEqual(source["year"], year)
            self.assertIn(source["source_grade"], {"A2", "B2"})
            excerpt = source["text_path"].read_text(encoding="utf-8")
            pattern = re.compile(source["pattern"])
            match = pattern.search(re.sub(r"\s+", "", excerpt))
            self.assertIsNotNone(match, source_id)
            self.assertEqual(match.group(1), value)


if __name__ == "__main__":
    unittest.main()
