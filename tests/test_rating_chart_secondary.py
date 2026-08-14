import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import province_debt_sources


class RatingChartSecondaryTests(unittest.TestCase):
    def test_repository_contains_yunnan_2019_exact_or_calculated_city_totals(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                row["city_id"]: row
                for row in csv.DictReader(handle)
                if row.get("source_doc_id") in {
                    "SRC-SECONDARY-CCXI-YUNNAN-KUNMING-2019",
                    "SRC-SECONDARY-CCXI-YUNNAN-DEHONG-2019",
                }
            }
        self.assertEqual(rows["CN-530100"]["metric_year"], "2019")
        self.assertEqual(rows["CN-530100"]["statutory_debt_balance_100m"], "2059.86")
        self.assertEqual(rows["CN-530100"]["value_origin"], "disclosed")
        self.assertEqual(rows["CN-533100"]["statutory_debt_balance_100m"], "213.92")
        self.assertEqual(rows["CN-533100"]["value_origin"], "calculated")

    def test_repository_contains_yunnan_2019_2021_chart_gap_rows(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            ("CN-530800", "2019"), ("CN-532800", "2019"), ("CN-533400", "2019"), ("CN-533300", "2019"),
            ("CN-530100", "2020"), ("CN-530800", "2020"), ("CN-532600", "2020"),
            ("CN-533100", "2020"), ("CN-533300", "2020"),
            ("CN-530100", "2021"), ("CN-532800", "2021"), ("CN-533100", "2021"),
            ("CN-533300", "2021"),
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if (row["city_id"], row["metric_year"]) in expected
            }
        self.assertEqual(set(rows), expected)
        for key, row in rows.items():
            if key == ("CN-530100", "2021"):
                self.assertEqual(row["value_origin"], "disclosed")
                self.assertEqual(row["statutory_debt_balance_100m"], "2149.00")
            else:
                self.assertIn(row["value_origin"], {"chart_digitized", "calculated"})
                self.assertEqual(row["source_grade"], "B2")

    def test_repository_contains_gansu_2022_chart_rows_for_all_fourteen_city_states(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = [
                row
                for row in csv.DictReader(handle)
                if row.get("source_doc_id") == "SRC-SECONDARY-RATING-GANSU-2020-2022"
                and row.get("metric_year") == "2022"
            ]
        self.assertEqual(len(rows), 14)
        self.assertEqual({row["city_id"] for row in rows}, {
            "CN-620100", "CN-620200", "CN-620300", "CN-620400", "CN-620500",
            "CN-620600", "CN-620700", "CN-620800", "CN-620900", "CN-621000",
            "CN-621100", "CN-621200", "CN-622900", "CN-623000",
        })

    def test_repository_contains_gansu_2023_chart_rows_for_currently_missing_city_states(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = [
                row
                for row in csv.DictReader(handle)
                if row.get("source_doc_id") == "SRC-SECONDARY-RATING-GANSU-2021-2023"
                and row.get("metric_year") == "2023"
            ]
        self.assertEqual(len(rows), 11)
        self.assertEqual(
            {row["city_id"] for row in rows},
            {
                "CN-620200", "CN-620300", "CN-620400", "CN-620500", "CN-620600",
                "CN-620800", "CN-620900", "CN-621100", "CN-621200", "CN-622900", "CN-623000",
            },
        )
        self.assertTrue(all(row["value_origin"] == "chart_digitized" and row["source_grade"] == "B2" for row in rows))

    def test_repository_contains_gansu_2020_2021_chart_rows_for_currently_missing_city_states(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            ("CN-620900", "2020"): "137.8",
            ("CN-620800", "2020"): "168.3",
            ("CN-622900", "2020"): "168.3",
            ("CN-623000", "2020"): "92.1",
            ("CN-620900", "2021"): "177.5",
            ("CN-622900", "2021"): "244.4",
            ("CN-623000", "2021"): "153.0",
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if (row["city_id"], row["metric_year"]) in expected
                and row.get("source_doc_id") == "SRC-SECONDARY-RATING-GANSU-2020-2022"
            }
        self.assertEqual(set(rows), set(expected))
        for key, value in expected.items():
            self.assertEqual(rows[key]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[key]["value_origin"], "chart_digitized")
            self.assertEqual(rows[key]["source_grade"], "B2")

    def test_repository_contains_gansu_2021_chart_rows_for_jinchang_and_tianshui(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            ("CN-620300", "2021"): "96.0",
            ("CN-620500", "2021"): "232.0",
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if (row["city_id"], row["metric_year"]) in expected
                and row.get("source_doc_id") == "SRC-SECONDARY-RATING-GANSU-2020-2022"
            }
        self.assertEqual(set(rows), set(expected))
        for key, value in expected.items():
            self.assertEqual(rows[key]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[key]["value_origin"], "chart_digitized")
            self.assertEqual(rows[key]["source_grade"], "B2")

    def test_repository_contains_guangxi_2018_chart_rows_for_missing_cities(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            ("CN-450500", "2018"): "180.0",
            ("CN-450600", "2018"): "150.0",
            ("CN-451000", "2018"): "320.0",
            ("CN-451200", "2018"): "200.0",
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if (row["city_id"], row["metric_year"]) in expected
            }
        self.assertEqual(set(rows), set(expected))
        for key, value in expected.items():
            self.assertEqual(rows[key]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[key]["source_doc_id"], "SRC-SECONDARY-RATING-GUANGXI-2017-2019")
            self.assertEqual(rows[key]["value_origin"], "chart_digitized")
            self.assertEqual(rows[key]["source_grade"], "B2")

    def test_repository_contains_xizang_2019_chart_rows_for_currently_missing_city_states(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            "CN-540200": "37.8",
            "CN-540500": "14.5",
            "CN-540400": "8.0",
            "CN-542500": "9.3",
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                row["city_id"]: row
                for row in csv.DictReader(handle)
                if row.get("source_doc_id") == "SRC-SECONDARY-RATING-TIBET-2019-2021"
                and row.get("metric_year") == "2019"
            }
        self.assertEqual(set(rows), set(expected))
        for city_id, value in expected.items():
            self.assertEqual(rows[city_id]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[city_id]["value_origin"], "chart_digitized")
            self.assertEqual(rows[city_id]["source_grade"], "B2")

    def test_repository_contains_gansu_2024_chart_rows_for_currently_missing_city_states(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            "CN-620600": "410.9",
            "CN-620800": "336.0",
            "CN-620900": "307.7",
            "CN-621200": "400.8",
            "CN-622900": "441.3",
            "CN-623000": "303.6",
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                row["city_id"]: row
                for row in csv.DictReader(handle)
                if row.get("source_doc_id") == "SRC-SECONDARY-RATING-GANSU-2024-CITY-CHART"
                and row.get("metric_year") == "2024"
            }
        self.assertEqual(set(rows), set(expected))
        for city_id, value in expected.items():
            self.assertEqual(rows[city_id]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[city_id]["value_origin"], "chart_digitized")
            self.assertEqual(rows[city_id]["source_grade"], "B2")

    def test_repository_contains_shanxi_2022_currently_missing_city_totals(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            "CN-140300": "291.39",
            "CN-140500": "308.10",
            "CN-140600": "245.65",
            "CN-140800": "363.06",
            "CN-140900": "418.29",
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                row["city_id"]: row
                for row in csv.DictReader(handle)
                if row.get("metric_year") == "2022" and row.get("city_id") in expected
            }
        self.assertEqual(set(rows), set(expected))
        for city_id, value in expected.items():
            self.assertEqual(rows[city_id]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[city_id]["value_origin"], "disclosed")
            self.assertEqual(rows[city_id]["source_grade"], "B2")

    def test_repository_contains_hainan_haikou_2018_2019_secondary_totals(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            "2018": "624.0",
            "2019": "690.3",
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                row["metric_year"]: row
                for row in csv.DictReader(handle)
                if row.get("city_id") == "CN-460100" and row.get("metric_year") in expected
            }
        self.assertEqual(set(rows), set(expected))
        for metric_year, value in expected.items():
            self.assertEqual(rows[metric_year]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[metric_year]["value_origin"], "disclosed")
            self.assertEqual(rows[metric_year]["source_grade"], "B2")

    def test_reads_gansu_2022_chart_digitized_value_with_provenance(self):
        city_master = [
            {
                "city_id": "CN-620500",
                "city_name_cn": "天水市",
                "province_name": "甘肃省",
                "metric_year": "2022",
            }
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "rating_chart.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "city_id",
                        "city_name_cn",
                        "province_name",
                        "metric_year",
                        "statutory_debt_balance_100m",
                        "source_doc_id",
                        "source_url",
                        "evidence_excerpt",
                        "source_grade",
                        "value_origin",
                        "table_name",
                        "document_title",
                        "publisher",
                        "publication_date",
                        "period_end",
                        "source_note",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "city_id": "CN-620500",
                        "city_name_cn": "天水市",
                        "province_name": "甘肃省",
                        "metric_year": "2022",
                        "statutory_debt_balance_100m": "293.5",
                        "source_doc_id": "SRC-SECONDARY-RATING-GANSU-2020-2022",
                        "source_url": "https://www.lhratings.com/file/f6efde6f69d.pdf",
                        "evidence_excerpt": "图7：天水市2022年绿色柱按纵轴刻度估读约293.5亿元",
                        "source_grade": "B2",
                        "value_origin": "chart_digitized",
                        "table_name": "图7 2020—2022年底甘肃省各地级市（州）政府债务余额情况",
                        "document_title": "地方政府与城投企业债务风险研究报告——甘肃篇",
                        "publisher": "联合资信评估股份有限公司",
                        "publication_date": "2023-10-20",
                        "period_end": "2022-12-31",
                        "source_note": "图表转录值，仅作阶段性补缺。",
                    }
                )
            with patch.object(province_debt_sources, "RATING_CHART_SECONDARY_DEBT_PATH", path):
                rows, sources = province_debt_sources._extract_rating_chart_secondary_debt_facts(city_master)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["city_id"], "CN-620500")
        self.assertEqual(rows[0]["metric_year"], "2022")
        self.assertEqual(rows[0]["statutory_debt_balance_100m"], province_debt_sources.Decimal("293.5"))
        self.assertEqual(rows[0]["source_grade"], "B2")
        self.assertEqual(rows[0]["value_origin"], "chart_digitized")
        self.assertEqual(sources[0]["source_doc_id"], "SRC-SECONDARY-RATING-GANSU-2020-2022")

    def test_reads_chart_digitized_city_year_values_with_provenance(self):
        city_master = [
            {
                "city_id": "CN-340100",
                "city_name_cn": "合肥市",
                "province_name": "安徽省",
                "metric_year": "2019",
            }
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "rating_chart.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "city_id",
                        "city_name_cn",
                        "province_name",
                        "metric_year",
                        "statutory_debt_balance_100m",
                        "source_doc_id",
                        "source_url",
                        "evidence_excerpt",
                        "source_grade",
                        "value_origin",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "city_id": "CN-340100",
                        "city_name_cn": "合肥市",
                        "province_name": "安徽省",
                        "metric_year": "2019",
                        "statutory_debt_balance_100m": "869.2",
                        "source_doc_id": "SRC-SECONDARY-RATING-ANHUI-2019-2021",
                        "source_url": "https://example.test/anhui.pdf",
                        "evidence_excerpt": "图8，2019年柱形图按纵轴刻度转录约869.2亿元",
                        "source_grade": "B2",
                        "value_origin": "chart_digitized",
                    }
                )
            with patch.object(province_debt_sources, "RATING_CHART_SECONDARY_DEBT_PATH", path):
                rows, sources = province_debt_sources._extract_rating_chart_secondary_debt_facts(city_master)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["city_id"], "CN-340100")
        self.assertEqual(rows[0]["statutory_debt_balance_100m"], province_debt_sources.Decimal("869.2"))
        self.assertEqual(rows[0]["source_grade"], "B2")
        self.assertEqual(rows[0]["value_origin"], "chart_digitized")
        self.assertEqual(rows[0]["geo_scope"], "prefecture_whole")
        self.assertEqual(sources[0]["source_doc_id"], "SRC-SECONDARY-RATING-ANHUI-2019-2021")

    def test_ignores_rows_outside_city_master(self):
        city_master = [
            {
                "city_id": "CN-340100",
                "city_name_cn": "合肥市",
                "province_name": "安徽省",
                "metric_year": "2019",
            }
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "rating_chart.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["city_id", "city_name_cn", "province_name", "metric_year", "statutory_debt_balance_100m", "source_doc_id"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "city_id": "CN-999999",
                        "city_name_cn": "不在主表的城市",
                        "province_name": "安徽省",
                        "metric_year": "2019",
                        "statutory_debt_balance_100m": "1",
                        "source_doc_id": "SRC-SECONDARY-TEST",
                    }
                )
            with patch.object(province_debt_sources, "RATING_CHART_SECONDARY_DEBT_PATH", path):
                rows, sources = province_debt_sources._extract_rating_chart_secondary_debt_facts(city_master)

        self.assertEqual(rows, [])
        self.assertEqual(sources, [])

    def test_accepts_multiple_metric_years_for_a_city_present_in_one_roster_snapshot(self):
        city_master = [
            {
                "city_id": "CN-340100",
                "city_name_cn": "合肥市",
                "province_name": "安徽省",
                "metric_year": "2025",
            }
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "rating_chart.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "city_id", "city_name_cn", "province_name", "metric_year",
                        "statutory_debt_balance_100m", "source_doc_id",
                    ],
                )
                writer.writeheader()
                for year, value in (("2019", "869.2"), ("2020", "934.7")):
                    writer.writerow(
                        {
                            "city_id": "CN-340100",
                            "city_name_cn": "合肥市",
                            "province_name": "安徽省",
                            "metric_year": year,
                            "statutory_debt_balance_100m": value,
                            "source_doc_id": "SRC-SECONDARY-TEST-MULTIYEAR",
                        }
                    )
            with patch.object(province_debt_sources, "RATING_CHART_SECONDARY_DEBT_PATH", path):
                rows, sources = province_debt_sources._extract_rating_chart_secondary_debt_facts(city_master)

        self.assertEqual([(row["metric_year"], row["statutory_debt_balance_100m"]) for row in rows], [
            ("2019", province_debt_sources.Decimal("869.2")),
            ("2020", province_debt_sources.Decimal("934.7")),
        ])
        self.assertEqual(len(sources), 1)

    def test_reads_ceic_csv_with_utf8_bom_and_multiple_metric_years(self):
        city_master = [
            {
                "city_id": "CN-340100",
                "city_name_cn": "合肥市",
                "province_name": "安徽省",
                "metric_year": "2025",
            }
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "ceic.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "city_id", "city_name_cn", "metric_year",
                        "statutory_debt_balance_100m", "source_doc_id", "source_url",
                    ],
                )
                writer.writeheader()
                for year, value in (("2019", "869.2"), ("2020", "934.7")):
                    writer.writerow(
                        {
                            "city_id": "CN-340100",
                            "city_name_cn": "合肥市",
                            "metric_year": year,
                            "statutory_debt_balance_100m": value,
                            "source_doc_id": "SRC-SECONDARY-CEIC-TEST",
                            "source_url": "https://example.test/ceic",
                        }
                    )
            with patch.object(province_debt_sources, "CEIC_SECONDARY_DEBT_PATH", path):
                rows, sources = province_debt_sources._extract_ceic_secondary_debt_facts(city_master)

        self.assertEqual(len(rows), 2)
        self.assertEqual({row["metric_year"] for row in rows}, {"2019", "2020"})
        self.assertEqual({row["statutory_debt_balance_100m"] for row in rows}, {
            province_debt_sources.Decimal("869.2"),
            province_debt_sources.Decimal("934.7"),
        })
        self.assertEqual(sources[0]["source_doc_id"], "SRC-SECONDARY-CEIC-TEST")


if __name__ == "__main__":
    unittest.main()
