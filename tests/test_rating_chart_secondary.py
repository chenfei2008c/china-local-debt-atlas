import csv
import unittest
from decimal import Decimal
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

    def test_repository_contains_hubei_2021_direct_counties_aggregate(self):
        city_master = [
            {
                "city_id": "CN-429000",
                "city_name_cn": "省直辖县级行政区划",
                "province_name": "湖北省",
                "metric_year": "2021",
            }
        ]
        facts, sources = province_debt_sources.extract_official_debt_facts(city_master)
        row = facts[("CN-429000", "2021")]
        self.assertEqual(row["statutory_debt_balance_100m"], Decimal("276.164"))
        self.assertEqual(row["source_doc_id"], "SRC-SECONDARY-DEBT-HUBEI-2021-DIRECT-AGG")
        self.assertEqual(row["source_grade"], "B2")
        self.assertTrue(any(source["source_doc_id"] == "SRC-SECONDARY-DEBT-HUBEI-2021-DIRECT-AGG" for source in sources))

    def test_repository_contains_hubei_2023_direct_counties_aggregate(self):
        city_master = [
            {
                "city_id": "CN-429000",
                "city_name_cn": "省直辖县级行政区划",
                "province_name": "湖北省",
                "metric_year": "2023",
            }
        ]
        facts, sources = province_debt_sources.extract_official_debt_facts(city_master)
        row = facts[("CN-429000", "2023")]
        self.assertEqual(row["statutory_debt_balance_100m"], Decimal("415.92"))
        self.assertEqual(row["source_doc_id"], "SRC-SECONDARY-DEBT-HUBEI-2023-DIRECT-AGG")
        self.assertEqual(row["source_grade"], "B2")
        self.assertTrue(any(source["source_doc_id"] == "SRC-SECONDARY-DEBT-HUBEI-2023-DIRECT-AGG" for source in sources))

    def test_repository_contains_hubei_2022_direct_counties_provisional_aggregate(self):
        city_master = [
            {
                "city_id": "CN-429000",
                "city_name_cn": "省直辖县级行政区划",
                "province_name": "湖北省",
                "metric_year": "2022",
            }
        ]
        facts, sources = province_debt_sources.extract_official_debt_facts(city_master)
        row = facts[("CN-429000", "2022")]
        self.assertEqual(row["statutory_debt_balance_100m"], Decimal("345.7402"))
        self.assertEqual(row["source_doc_id"], "SRC-SECONDARY-DEBT-HUBEI-2022-DIRECT-AGG")
        self.assertEqual(row["source_grade"], "B2")
        self.assertTrue(any(source["source_doc_id"] == "SRC-SECONDARY-DEBT-HUBEI-2022-DIRECT-AGG" for source in sources))

    def test_repository_maps_henan_2023_jiyuan_to_direct_county_row(self):
        city_master = [
            {
                "city_id": "CN-419000",
                "city_name_cn": "省直辖县级行政区划",
                "province_name": "河南省",
                "metric_year": "2023",
            }
        ]
        facts, _ = province_debt_sources.extract_official_debt_facts(city_master)
        row = facts[("CN-419000", "2023")]
        self.assertEqual(row["statutory_debt_balance_100m"], Decimal("148.71"))
        self.assertEqual(row["source_doc_id"], "SRC-SECONDARY-DEBT-HENAN-2023-CITY-TOTALS")

    def test_repository_contains_inner_mongolia_2021_chart_rows_for_missing_cities(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            ("CN-150600", "2021"): "1670.9",
            ("CN-150200", "2021"): "1041.1",
            ("CN-152500", "2021"): "472.3",
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
            self.assertEqual(rows[key]["source_doc_id"], "SRC-SECONDARY-RATING-INNER-MONGOLIA-2021-CITY-CHART")
            self.assertEqual(rows[key]["value_origin"], "chart_digitized")
            self.assertEqual(rows[key]["source_grade"], "B2")

    def test_repository_contains_inner_mongolia_xilingol_2023_chart_estimate(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if row.get("city_id") == "CN-152500" and row.get("metric_year") == "2023"
            }
        row = rows[("CN-152500", "2023")]
        self.assertEqual(row["statutory_debt_balance_100m"], "553.7")
        self.assertEqual(row["source_doc_id"], "SRC-SECONDARY-RATING-INNER-MONGOLIA-2024-CITY-CHART")
        self.assertEqual(row["value_origin"], "chart_digitized")
        self.assertEqual(row["source_grade"], "B2")

    def test_repository_contains_hubei_enshi_2021_chart_estimate(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if row.get("city_id") == "CN-422800" and row.get("metric_year") == "2021"
            }
        row = rows[("CN-422800", "2021")]
        self.assertEqual(row["statutory_debt_balance_100m"], "450.0")
        self.assertEqual(row["source_doc_id"], "SRC-SECONDARY-RATING-HUBEI-2019-2021-CITY-CHART")
        self.assertEqual(row["value_origin"], "chart_digitized")
        self.assertEqual(row["source_grade"], "B2")

    def test_repository_contains_hubei_enshi_2022_chart_derived_estimate(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if row.get("city_id") == "CN-422800" and row.get("metric_year") == "2022"
            }
        row = rows[("CN-422800", "2022")]
        self.assertEqual(row["statutory_debt_balance_100m"], "516.0")
        self.assertEqual(row["source_doc_id"], "SRC-SECONDARY-RATING-HUBEI-2022-DEBT-RATIO-CHART")
        self.assertEqual(row["value_origin"], "calculated")
        self.assertEqual(row["source_grade"], "B2")

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

    def test_repository_contains_next_ten_statutory_debt_gap_rows(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            ("CN-150200", "2018"): ("860.88900", "SRC-SECONDARY-CEIC-CN-150200-COMPONENTS", "calculated"),
            ("CN-150200", "2019"): ("930.11170", "SRC-SECONDARY-CEIC-CN-150200-COMPONENTS", "calculated"),
            ("CN-150200", "2020"): ("1000.0", "SRC-SECONDARY-RATING-INNER-MONGOLIA-2020-2022-CITY-CHART", "chart_digitized"),
            ("CN-150200", "2022"): ("1071.9", "SRC-SECONDARY-DEBT-BAOTOU-2022-OFFICIAL", "published_text"),
            ("CN-152500", "2020"): ("495.0", "SRC-SECONDARY-RATING-INNER-MONGOLIA-2020-2022-CITY-CHART", "chart_digitized"),
            ("CN-152500", "2022"): ("596.0", "SRC-SECONDARY-RATING-INNER-MONGOLIA-2020-2022-CITY-CHART", "chart_digitized"),
            ("CN-530900", "2019"): ("198.14", "SRC-SECONDARY-DEBT-YUNNAN-LINCANG-2019", "published_text"),
            ("CN-533300", "2023"): ("145.0", "SRC-SECONDARY-RATING-YUNNAN-2022-2023-CITY-CHART", "chart_digitized"),
            ("CN-460200", "2018"): ("220.0", "SRC-SECONDARY-DEBT-HAINAN-SANYA-2018-REPORT", "published_text"),
            ("CN-530700", "2019"): ("180.0", "SRC-SECONDARY-RATING-YUNNAN-2019-2021", "chart_digitized"),
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if (row["city_id"], row["metric_year"]) in expected
            }
        self.assertEqual(set(rows), set(expected))
        for key, (value, source_doc_id, value_origin) in expected.items():
            self.assertEqual(rows[key]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[key]["source_doc_id"], source_doc_id)
            self.assertEqual(rows[key]["value_origin"], value_origin)
            self.assertEqual(rows[key]["source_grade"], "D" if source_doc_id.startswith("SRC-SECONDARY-CEIC") else "B2")

    def test_repository_contains_current_batch_of_ten_statutory_debt_gap_rows(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            ("CN-620900", "2019"): ("112.9044", "SRC-OFFICIAL-DEBT-GANSU-JIUQUAN-2019", "disclosed", "A1"),
            ("CN-650500", "2020"): ("191.54", "SRC-SECONDARY-DEBT-XINJIANG-HAMI-2020", "published_text", "B2"),
            ("CN-654300", "2020"): ("204.6134", "SRC-OFFICIAL-DEBT-XINJIANG-ALTAY-2020", "disclosed", "A1"),
            ("CN-460200", "2023"): ("594.99", "SRC-SECONDARY-DEBT-HAINAN-SANYA-2023", "disclosed", "B2"),
            ("CN-460200", "2024"): ("747.00973", "SRC-OFFICIAL-DEBT-HAINAN-SANYA-2024", "disclosed", "A1"),
            ("CN-460200", "2025"): ("836.2", "SRC-OFFICIAL-DEBT-HAINAN-SANYA-2025", "disclosed", "A1"),
            ("CN-450500", "2020"): ("220.0", "SRC-SECONDARY-RATING-GUANGXI-2019-2021-CITY-CHART", "chart_digitized", "B2"),
            ("CN-140900", "2023"): ("420.0", "SRC-SECONDARY-RATING-SHANXI-2022-2023-CITY-CHART", "chart_digitized", "B2"),
            ("CN-361100", "2019"): ("510.0", "SRC-SECONDARY-RATING-JIANGXI-2019-2021-CITY-CHART", "chart_digitized", "B2"),
            ("CN-530800", "2018"): ("200.0", "SRC-SECONDARY-RATING-YUNNAN-2018-CITY-CHART", "chart_digitized", "B2"),
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if (row["city_id"], row["metric_year"]) in expected
            }
        self.assertEqual(set(rows), set(expected))
        for key, (value, source_doc_id, value_origin, source_grade) in expected.items():
            self.assertEqual(rows[key]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[key]["source_doc_id"], source_doc_id)
            self.assertEqual(rows[key]["value_origin"], value_origin)
            self.assertEqual(rows[key]["source_grade"], source_grade)

    def test_repository_contains_three_ceic_statutory_debt_gap_rows(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "ceic_city_debt_2018_2025.csv"
        expected = {
            ("CN-130300", "2019"): ("495.35260", "SRC-SECONDARY-CEIC-CN-130300", "disclosed"),
            ("CN-130700", "2019"): ("555.55000", "SRC-SECONDARY-CEIC-CN-130700", "disclosed"),
            ("CN-360500", "2018"): ("191.28000", "SRC-SECONDARY-CEIC-CN-360500", "disclosed"),
        }
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if (row["city_id"], row["metric_year"]) in expected
            }
        self.assertEqual(set(rows), set(expected))
        for key, (value, source_doc_id, value_origin) in expected.items():
            self.assertEqual(rows[key]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[key]["source_doc_id"], source_doc_id)
            self.assertEqual(rows[key]["value_origin"], value_origin)

    def test_repository_contains_laiwu_legacy_prefecture_debt_rows(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            ("CN-371200", "2018"): ("68.9955", "SRC-OFFICIAL-DEBT-JINAN-LAIWU-2018", "disclosed", "A1"),
            ("CN-371200", "2019"): ("98.1358", "SRC-OFFICIAL-DEBT-JINAN-LAIWU-2019", "disclosed", "A1"),
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if (row["city_id"], row["metric_year"]) in expected
            }
        self.assertEqual(set(rows), set(expected))
        for key, (value, source_doc_id, value_origin, source_grade) in expected.items():
            self.assertEqual(rows[key]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[key]["source_doc_id"], source_doc_id)
            self.assertEqual(rows[key]["value_origin"], value_origin)
            self.assertEqual(rows[key]["source_grade"], source_grade)

    def test_repository_contains_danzhou_official_2018_2019_debt_rows(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = {
            ("CN-460400", "2018"): ("83.0018397569", "SRC-OFFICIAL-DEBT-HN-DANZHOU-2018", "disclosed", "A1"),
            ("CN-460400", "2019"): ("119.1320047025", "SRC-OFFICIAL-DEBT-HN-DANZHOU-2019", "disclosed", "A1"),
        }
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if (row["city_id"], row["metric_year"]) in expected
            }
        self.assertEqual(set(rows), set(expected))
        for key, (value, source_doc_id, value_origin, source_grade) in expected.items():
            self.assertEqual(rows[key]["statutory_debt_balance_100m"], value)
            self.assertEqual(rows[key]["source_doc_id"], source_doc_id)
            self.assertEqual(rows[key]["value_origin"], value_origin)
            self.assertEqual(rows[key]["source_grade"], source_grade)

    def test_repository_contains_sanya_official_2019_debt_row(self):
        path = Path(__file__).resolve().parents[1] / "raw" / "province_debt" / "secondary" / "rating_chart_city_debt_2018_2025.csv"
        expected = ("282.6863758905", "SRC-OFFICIAL-DEBT-HN-SANYA-2019", "disclosed", "A1")
        with path.open(encoding="utf-8", newline="") as handle:
            rows = {
                (row["city_id"], row["metric_year"]): row
                for row in csv.DictReader(handle)
                if (row["city_id"], row["metric_year"]) == ("CN-460200", "2019")
            }
        self.assertEqual(set(rows), { ("CN-460200", "2019") })
        row = rows[("CN-460200", "2019")]
        self.assertEqual(
            (row["statutory_debt_balance_100m"], row["source_doc_id"], row["value_origin"], row["source_grade"]),
            expected,
        )

    def test_repository_contains_hubei_2019_direct_counties_official_aggregate(self):
        city_master = [
            {
                "city_id": "CN-429000",
                "city_name_cn": "省直辖县级行政区划",
                "province_name": "湖北省",
                "metric_year": "2019",
            }
        ]
        facts, sources = province_debt_sources.extract_official_debt_facts(city_master)
        row = facts[("CN-429000", "2019")]
        self.assertEqual(row["statutory_debt_balance_100m"], Decimal("201.6700542538"))
        self.assertEqual(row["source_doc_id"], "SRC-OFFICIAL-DEBT-HUBEI-2019-DIRECT-AGG")
        self.assertEqual(row["source_grade"], "A1")
        self.assertTrue(any(source["source_doc_id"] == "SRC-OFFICIAL-DEBT-HUBEI-2019-DIRECT-AGG" for source in sources))

    def test_repository_contains_hubei_2018_direct_counties_official_aggregate(self):
        city_master = [
            {
                "city_id": "CN-429000",
                "city_name_cn": "省直辖县级行政区划",
                "province_name": "湖北省",
                "metric_year": "2018",
            }
        ]
        facts, sources = province_debt_sources.extract_official_debt_facts(city_master)
        row = facts[("CN-429000", "2018")]
        self.assertEqual(row["statutory_debt_balance_100m"], Decimal("172.9096868225"))
        self.assertEqual(row["source_doc_id"], "SRC-OFFICIAL-DEBT-HUBEI-2018-DIRECT-AGG")
        self.assertEqual(row["source_grade"], "A1")
        self.assertTrue(any(source["source_doc_id"] == "SRC-OFFICIAL-DEBT-HUBEI-2018-DIRECT-AGG" for source in sources))


if __name__ == "__main__":
    unittest.main()
