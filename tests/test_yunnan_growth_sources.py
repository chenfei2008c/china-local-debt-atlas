import re
import unittest

from scripts.yunnan_growth_sources import YUNNAN_GDP_GROWTH_SOURCES


class YunnanGrowthSourceTests(unittest.TestCase):
    def test_batch_covers_the_low_grade_yunnan_growth_values(self):
        expected = {
            ("CN-532300", 2018): "10.2",
            ("CN-532300", 2019): "9.1",
            ("CN-532300", 2020): "6.0",
            ("CN-532500", 2018): "9.7",
            ("CN-532500", 2019): "8.5",
            ("CN-532500", 2020): "5.2",
            ("CN-532600", 2018): "10.3",
            ("CN-532600", 2019): "10.1",
            ("CN-532600", 2020): "5.4",
            ("CN-532800", 2018): "8.1",
            ("CN-532800", 2019): "10.1",
            ("CN-532800", 2020): "3.6",
            ("CN-532900", 2018): "9.3",
            ("CN-532900", 2019): "6.1",
            ("CN-533100", 2018): "8.0",
            ("CN-533100", 2019): "7.9",
            ("CN-533300", 2018): "12.1",
            ("CN-533300", 2019): "11.1",
            ("CN-533300", 2020): "7.1",
            ("CN-533400", 2018): "9.5",
            ("CN-533400", 2019): "11.6",
            ("CN-533400", 2020): "5.1",
        }
        self.assertEqual(
            {(source["city_id"], source["year"]) for source in YUNNAN_GDP_GROWTH_SOURCES},
            set(expected),
        )
        self.assertEqual(len(YUNNAN_GDP_GROWTH_SOURCES), len(expected))
        for source in YUNNAN_GDP_GROWTH_SOURCES:
            text = re.sub(r"\s+", "", source["path"].read_text(encoding="utf-8"))
            match = re.search(source["patterns"]["gdp_real_growth_pct"], text)
            self.assertIsNotNone(match, source["source_doc_id"])
            self.assertEqual(match.group(1), expected[(source["city_id"], source["year"])])
            self.assertEqual(source["source_grade"], source["expected_grade"])
            self.assertEqual(source["data_status"], "reported")
            self.assertEqual(source["raw_units"]["gdp_real_growth_pct"], "%")
            self.assertEqual(
                source["lineage_locator_type"],
                "html_text_statement" if source["source_format"] == "html" else "pdf_text_statement",
            )
            self.assertIn("GDP实际增速", source["lineage_selection_reason"])
            self.assertIn("可比", source["lineage_normalization_rule"])

    def test_sources_only_expose_real_growth_field(self):
        for source in YUNNAN_GDP_GROWTH_SOURCES:
            self.assertEqual(tuple(source["patterns"]), ("gdp_real_growth_pct",))
            self.assertIn("可比", source["note"])
            self.assertIn("行政范围=全州", source["source_locator"])


if __name__ == "__main__":
    unittest.main()
