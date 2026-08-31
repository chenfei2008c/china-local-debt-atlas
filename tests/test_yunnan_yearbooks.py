import re
import unittest

from scripts.yunnan_yearbooks import YUNNAN_YEARBOOK_SOURCES


class YunnanYearbookSourceTests(unittest.TestCase):
    def test_official_yearbook_batch_covers_sixteen_prefectures_and_three_years(self):
        self.assertEqual(len(YUNNAN_YEARBOOK_SOURCES), 96)
        self.assertEqual(
            {source["year"] for source in YUNNAN_YEARBOOK_SOURCES},
            {2018, 2019, 2020},
        )
        self.assertEqual(
            {source["city_id"] for source in YUNNAN_YEARBOOK_SOURCES},
            {
                "CN-530100",
                "CN-530300",
                "CN-530400",
                "CN-530500",
                "CN-530600",
                "CN-530700",
                "CN-530800",
                "CN-530900",
                "CN-532300",
                "CN-532500",
                "CN-532600",
                "CN-532800",
                "CN-532900",
                "CN-533100",
                "CN-533300",
                "CN-533400",
            },
        )

    def test_kunming_2018_exact_yearbook_values_are_parseable(self):
        source = next(
            source
            for source in YUNNAN_YEARBOOK_SOURCES
            if source["city_id"] == "CN-530100"
            and source["year"] == 2018
            and "gdp_current_100m" in source["patterns"]
        )
        text = source["path"].read_text(encoding="utf-8")
        compact = re.sub(r"\s+", "", text)
        expected = {
            "gdp_current_100m": "5206.90",
        }
        for field, value in expected.items():
            match = re.search(source["patterns"][field], compact)
            self.assertIsNotNone(match, field)
            self.assertEqual(match.group(1), value, field)
        self.assertEqual(source["source_grade"], "A2")
        self.assertEqual(source["data_status"], "yearbook")

        fiscal_source = next(
            source
            for source in YUNNAN_YEARBOOK_SOURCES
            if source["city_id"] == "CN-530100"
            and source["year"] == 2018
            and "general_public_revenue_100m" in source["patterns"]
        )
        fiscal_compact = re.sub(
            r"\s+", "", fiscal_source["path"].read_text(encoding="utf-8")
        )
        self.assertEqual(
            re.search(
                fiscal_source["patterns"]["general_public_revenue_100m"],
                fiscal_compact,
            ).group(1),
            "595.630",
        )
        self.assertEqual(
            re.search(
                fiscal_source["patterns"]["general_public_expenditure_100m"],
                fiscal_compact,
            ).group(1),
            "756.800",
        )


if __name__ == "__main__":
    unittest.main()
