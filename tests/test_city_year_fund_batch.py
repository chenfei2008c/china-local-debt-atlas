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
            "SRC-A2-YULIN-CITY-FUND-2023": ("榆林市", 2023, "83.1934"),
            "SRC-B2-HEBI-CITY-FUND-2023": ("鹤壁市", 2023, "32.06"),
            "SRC-B2-YANGJIANG-CITY-FUND-2023": ("阳江市", 2023, "289898"),
            "SRC-B2-SANMENXIA-CITY-FUND-2023": ("三门峡市", 2023, "37.25"),
            "SRC-B2-LUOHE-CITY-FUND-2023": ("漯河市", 2023, "54.43"),
            "SRC-B2-ANYANG-CITY-FUND-2023": ("安阳市", 2023, "65.10"),
            "SRC-B2-ANSHUN-CITY-FUND-2023": ("安顺市", 2023, "98.43"),
            "SRC-B2-CHANGSHA-CITY-FUND-2024": ("长沙市", 2024, "576.8"),
            "SRC-B2-HAIKOU-CITY-FUND-2024": ("海口市", 2024, "120.4"),
            "SRC-A2-DANZHOU-CITY-FUND-2024": ("儋州市", 2024, "4.57"),
            "SRC-A2-BEIJING-CITY-FUND-2024": ("北京市", 2024, "2094.9"),
            "SRC-A2-TIANJIN-CITY-FUND-2024": ("天津市", 2024, "6885592"),
            "SRC-A2-SHANGHAI-CITY-FUND-2024": ("上海市", 2024, "3202.8"),
            "SRC-A2-CHONGQING-CITY-FUND-2024": ("重庆市", 2024, "1722.6"),
            "SRC-B2-ZHOUSHAN-CITY-FUND-2024": ("舟山市", 2024, "84.18"),
            "SRC-B2-LISHUI-CITY-FUND-2024": ("丽水市", 2024, "294.61"),
            "SRC-B2-WEIHAI-CITY-FUND-2024": ("威海市", 2024, "211.09"),
            "SRC-B2-RIZHAO-CITY-FUND-2024": ("日照市", 2024, "194.49"),
            "SRC-B2-DEZHOU-CITY-FUND-2024": ("德州市", 2024, "231.64"),
            "SRC-B2-BINZHOU-CITY-FUND-2024": ("滨州市", 2024, "290.13"),
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
