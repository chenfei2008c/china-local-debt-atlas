import unittest
import csv
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.collect_gcs66_city_debt import _read_missing, extract_debt_fact


class Gcs66CityDebtTests(unittest.TestCase):
    def test_read_missing_builds_city_targets_from_top_combinations(self):
        rows = [
            {"province_name": "河南省", "city_name_cn": "郑州市", "metric_year": "2018"},
            {"province_name": "河南省", "city_name_cn": "郑州市", "metric_year": "2019"},
            {"province_name": "山东省", "city_name_cn": "济南市", "metric_year": "2018"},
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "missing.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)
            targets = _read_missing(path, top_combinations=3)
        self.assertEqual(set(targets), {("河南省", "郑州市"), ("山东省", "济南市")})
        self.assertEqual(targets[("河南省", "郑州市")]["years"], {2018, 2019})

    def test_extracts_target_year_city_total_and_components(self):
        text = (
            "关于郑州市2021年财政预算执行情况和2022年财政预算草案的报告 "
            "截至2021年底，郑州市政府债务余额为2943.4亿元，"
            "其中：一般债务1363.5亿元，专项债务1579.9亿元。"
        )
        fact = extract_debt_fact(
            text,
            city_name="郑州市",
            province_name="河南省",
            year=2021,
            source_doc_id="SRC-TEST-GCS66",
            source_url="https://example.test/document_detail/1.html",
        )
        self.assertEqual(fact["statutory_debt_balance_100m"], Decimal("2943.4"))
        self.assertEqual(fact["general_debt_balance_100m"], Decimal("1363.5"))
        self.assertEqual(fact["special_debt_balance_100m"], Decimal("1579.9"))
        self.assertEqual(fact["source_grade"], "B2")

    def test_does_not_use_a_different_year_in_the_same_report(self):
        text = (
            "截至2020年底，郑州市政府债务余额为2500亿元。"
            "截至2021年底，郑州市政府债务余额为2943.4亿元。"
        )
        fact = extract_debt_fact(
            text,
            city_name="郑州市",
            province_name="河南省",
            year=2021,
            source_doc_id="SRC-TEST-GCS66",
            source_url="https://example.test/document_detail/2.html",
        )
        self.assertEqual(fact["statutory_debt_balance_100m"], Decimal("2943.4"))


if __name__ == "__main__":
    unittest.main()
