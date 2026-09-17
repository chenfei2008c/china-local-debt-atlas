import csv
import tempfile
import unittest
from pathlib import Path

from scripts import collect_gcs66_city_debt as collector
from scripts import collect_national_panel as national_panel


class Gcs66CityFundTests(unittest.TestCase):
    def test_extracts_full_city_actual_fund_revenue(self):
        self.assertTrue(hasattr(collector, "extract_fund_fact"))
        text = (
            "关于安阳市2021年财政预算执行情况和2022年财政预算（草案）的报告。"
            "汇总全市各级人代会批准的2021年全市政府性基金收入预算为208.8亿元，"
            "实际完成123亿元，为年初预算的58.9%。"
        )
        fact = collector.extract_fund_fact(
            text,
            city_name="安阳市",
            province_name="河南省",
            year=2021,
            source_doc_id="SRC-TEST-GCS66-ANYANG-2021",
            source_url="https://www.gcs66.com/document_detail/test.html",
        )
        self.assertIsNotNone(fact)
        self.assertEqual(str(fact["gov_fund_revenue_100m"]), "123")

    def test_extracts_fund_revenue_from_html_report_body(self):
        text = (
            "<p>2021年全市政府性基金收入预算为208.8亿元，实际完成123亿元。</p>"
        )
        fact = collector.extract_fund_fact(
            text,
            city_name="安阳市",
            province_name="河南省",
            year=2021,
            source_doc_id="SRC-TEST-GCS66-ANYANG-HTML-2021",
            source_url="https://www.gcs66.com/document_detail/test.html",
        )
        self.assertIsNotNone(fact)
        self.assertEqual(str(fact["gov_fund_revenue_100m"]), "123")

    def test_rejects_city_level_and_in_year_budget_values(self):
        self.assertTrue(hasattr(collector, "extract_fund_fact"))
        text = (
            "2022年全市政府性基金收入预算为203.8亿元，1-11月份实际完成60亿元；"
            "2022年市本级政府性基金收入实际完成20亿元。"
        )
        fact = collector.extract_fund_fact(
            text,
            city_name="安阳市",
            province_name="河南省",
            year=2022,
            source_doc_id="SRC-TEST-GCS66-ANYANG-2022",
            source_url="https://www.gcs66.com/document_detail/test.html",
        )
        self.assertIsNone(fact)

    def test_archive_path_accepts_external_temp_directory(self):
        archive_path = Path("/private/tmp/gcs66_fund_test/安阳市_2021.html")
        self.assertEqual(collector.archive_path_value(archive_path), str(archive_path))

    def test_loads_b2_fund_batch_as_mergeable_source(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            batch_path = root / "raw/province_fiscal/secondary/gcs66_city_fund_2018_2025.csv"
            batch_path.parent.mkdir(parents=True)
            with batch_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "city_id", "city_name_cn", "province_name", "metric_year",
                        "gov_fund_revenue_100m", "gov_fund_revenue_raw_100m",
                        "gov_fund_revenue_raw_unit", "data_status", "value_origin",
                        "source_doc_id", "source_url", "document_title", "archive_path",
                        "evidence_excerpt", "source_grade",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "city_id": "CN-410500",
                        "city_name_cn": "安阳市",
                        "province_name": "河南省",
                        "metric_year": "2021",
                        "gov_fund_revenue_100m": "123",
                        "gov_fund_revenue_raw_100m": "123",
                        "gov_fund_revenue_raw_unit": "亿元",
                        "data_status": "execution",
                        "value_origin": "disclosed",
                        "source_doc_id": "SRC-SECONDARY-GCS66-FUND-ANYANG-2021",
                        "source_url": "https://www.gcs66.com/document_detail/test.html",
                        "document_title": "安阳市2021年财政预算执行报告",
                        "archive_path": "raw/province_fiscal/secondary/gcs66_fund/anyang.html",
                        "evidence_excerpt": "2021年全市政府性基金收入实际完成123亿元",
                        "source_grade": "B2",
                    }
                )
            values, sources = collector.load_gcs66_city_fund_sources(
                root,
                [{
                    "city_id": "CN-410500",
                    "city_name_cn": "安阳市",
                    "province_name": "河南省",
                    "metric_year": 2021,
                }],
            )
            self.assertEqual(str(values[("CN-410500", "2021")]["gov_fund_revenue_100m"]), "123")
            self.assertEqual(values[("CN-410500", "2021")]["source_grade"], "B2")
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]["source_doc_id"], "SRC-SECONDARY-GCS66-FUND-ANYANG-2021")

    def test_national_panel_exposes_gcs66_fund_loader(self):
        self.assertIs(national_panel.load_gcs66_city_fund_sources, collector.load_gcs66_city_fund_sources)


if __name__ == "__main__":
    unittest.main()
