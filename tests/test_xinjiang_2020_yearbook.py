import csv
import unittest
from pathlib import Path

from scripts.xinjiang_2020_yearbook import load_xinjiang_2020_yearbook_sources


class Xinjiang2020YearbookTests(unittest.TestCase):
    def test_official_yearbook_covers_prefecture_rows_and_converts_units(self):
        root = Path(__file__).resolve().parents[1]
        with (root / "outputs" / "national_prefecture_panel_2018_2026" / "dim_city.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            cities = list(csv.DictReader(handle))

        values, sources = load_xinjiang_2020_yearbook_sources(root, cities)

        self.assertEqual(len(sources), 3)
        # 新疆 2020 年地级行政单元白名单实际为14个地州；每个记录包含四项核心字段。
        self.assertEqual(len(values), 14)
        self.assertEqual(
            sum(1 for record in values.values() for field in (
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
            ) if record.get(field) is not None),
            56,
        )
        kizilsu = values[("CN-653000", "2020")]
        self.assertEqual(kizilsu["gdp_current_100m"], "169.24")
        self.assertEqual(kizilsu["gdp_real_growth_pct"], "4.10")
        self.assertEqual(kizilsu["general_public_revenue_100m"], "16.01")
        self.assertEqual(kizilsu["general_public_expenditure_100m"], "184.61")
        self.assertEqual(kizilsu["gdp_real_growth_pct_value_origin"], "calculated")
        self.assertEqual(
            kizilsu["gdp_real_growth_pct_calculation_formula_id"],
            "F-XINJIANG-GDP-INDEX-TO-GROWTH",
        )

        source_ids = {source["source_doc_id"] for source in sources}
        self.assertEqual(
            source_ids,
            {
                "SRC-A1-XINJIANG-YEARBOOK-2021-GDP-2020",
                "SRC-A1-XINJIANG-YEARBOOK-2021-GDP-INDEX-2020",
                "SRC-A1-XINJIANG-YEARBOOK-2021-FISCAL-2020",
            },
        )
        self.assertTrue(all(source["source_grade"] == "A1" for source in sources))


if __name__ == "__main__":
    unittest.main()
