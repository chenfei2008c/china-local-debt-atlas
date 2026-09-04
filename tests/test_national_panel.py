import csv
import tempfile
from decimal import Decimal
from pathlib import Path

import unittest

from scripts.collect_national_panel import (
    build_city_master,
    build_debt_rows,
    build_collection_status,
    build_custom_calculation_rows,
    build_evidence_based_missing_rows,
    build_macro_rows,
    compute_derived_values,
    load_city_year_fiscal_sources,
    load_followup_2025_city_fiscal,
    load_city_year_fund_sources,
    load_city_yearbook_sources,
    load_jiangsu_city_fiscal_sources,
    load_jiangsu_city_fund_sources,
    load_ningxia_2025_city_fiscal,
    load_next2_2025_city_fiscal,
    load_next3_2025_city_fiscal,
    load_next4_2025_city_fiscal,
    load_next5_2025_city_fiscal,
    load_next6_2025_city_fiscal,
    load_next7_2025_city_fiscal,
    load_next8_2025_city_economic,
    load_next9_2025_city_economic,
    load_next10_2025_city_economic,
    load_next11_2025_city_economic,
    load_next12_2025_city_economic,
    load_next13_2025_city_economic,
    load_next14_2025_city_economic,
    load_next15_2025_city_economic,
    load_next16_2025_city_economic,
    load_next17_2025_city_economic,
    load_next18_2025_city_economic,
    load_next19_2025_city_economic,
    load_next20_2025_city_economic,
    load_next21_2025_city_economic,
    load_next22_2025_city_economic,
    load_next23_2025_city_economic,
    load_next24_2025_city_economic,
    load_next25_2025_city_economic,
    load_next26_2025_city_economic,
    load_next27_2025_city_economic,
    load_next28_2025_city_economic,
    load_next29_2025_city_economic,
    load_next30_2025_city_economic,
    load_next_2025_city_fiscal,
    load_shandong_2025_city_fiscal,
    order_calculation_rows_for_lineage,
    validate_city_master,
    validate_no_zero_for_missing,
)
from scripts.gotohui_city_series import load_gotohui_city_series_sources
from scripts.collect_national_panel import merge_gotohui_city_series_batch
from scripts.dachuang_city_panel import load_dachuang_city_panel_sources
from scripts.haidatas_city_panel import load_haidatas_city_panel_sources
from scripts.sichuan_2018_yearbook import load_sichuan_2018_yearbook_sources
from scripts.evidence_based_missing import EVIDENCE_BY_KEY
from scripts.gotohui_snapshot_collector import (
    _read_city_targets,
    acceptable_series_title,
    normalize_series_value,
    merge_snapshot_series,
)
from scripts.crei_city_bulletins import is_target_bulletin_title, parse_bulletin_text
from scripts.hongheiku_city_bulletins import (
    _filter_sitemap_urls,
    _unfetched_urls,
    load_hongheiku_city_bulletin_sources,
)
from scripts.direct_admin_gdp_growth import (
    DIRECT_ADMIN_GDP_GROWTH_FORMULA_ID,
    calculate_weighted_growth,
)
from scripts.province_debt_sources import extract_official_debt_facts
from scripts.nbs_city_annual_2024 import load_nbs_city_annual_2024


class NationalPanelTests(unittest.TestCase):

    def test_sichuan_2018_official_yearbook_batch_covers_all_prefectures(self):
        root = Path(__file__).resolve().parents[1]
        with (root / "outputs/national_prefecture_panel_2018_2026/dim_city.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            city_master = list(csv.DictReader(handle))

        values, sources = load_sichuan_2018_yearbook_sources(root, city_master)

        self.assertEqual(len(values), 21)
        chengdu = values[("CN-510100", "2018")]
        self.assertEqual(chengdu["gdp_current_100m"], Decimal("15342.77"))
        self.assertEqual(chengdu["gdp_real_growth_pct"], Decimal("8.00"))
        self.assertEqual(chengdu["general_public_revenue_100m"], Decimal("1424.16"))
        self.assertEqual(chengdu["general_public_expenditure_100m"], Decimal("1837.42"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})
        self.assertEqual(len(sources), 4)
        self.assertIn("02-10.jpg", chengdu["_field_sources"]["gdp_current_100m"]["source_url"])
        self.assertIn("08-04.jpg", chengdu["_field_sources"]["general_public_expenditure_100m"]["source_url"])

    def test_qinghai_2018_2019_official_yearbook_fiscal_batch_upgrades_six_prefectures(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            ("CN-632200", "2018"): ("4.44", "79.30"),
            ("CN-632300", "2018"): ("3.16", "86.04"),
            ("CN-632500", "2018"): ("10.45", "107.42"),
            ("CN-632600", "2018"): ("2.31", "77.78"),
            ("CN-632700", "2018"): ("2.10", "100.96"),
            ("CN-632800", "2018"): ("54.48", "138.18"),
            ("CN-632200", "2019"): ("3.75", "82.98"),
            ("CN-632300", "2019"): ("3.48", "109.03"),
            ("CN-632500", "2019"): ("10.17", "116.51"),
            ("CN-632600", "2019"): ("1.89", "93.81"),
            ("CN-632700", "2019"): ("1.98", "153.45"),
            ("CN-632800", "2019"): ("49.52", "163.58"),
        }
        for key, (revenue, expenditure) in expected.items():
            record = values[key]
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue), key)
            self.assertEqual(record["general_public_expenditure_100m"], Decimal(expenditure), key)
            self.assertIn("SRC-A2-HAINAN-YEARBOOK-2022-QINGHAI", record["source_doc_id"])

        batch_sources = [
            source
            for source in sources
            if source["source_doc_id"].startswith("SRC-A2-HAINAN-YEARBOOK-2022-QINGHAI")
        ]
        self.assertEqual({source["source_grade"] for source in batch_sources}, {"A2"})
        self.assertEqual({source["period_end"] for source in batch_sources}, {"2018-12-31", "2019-12-31"})

    def test_nbs_annual_source_declares_a1_in_source_registry_payload(self):
        root = Path(__file__).resolve().parents[1]
        _values, sources = load_nbs_city_annual_2024(root, [])

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["source_doc_id"], "SRC-A1-NBS-MAJOR-CITY-ANNUAL-2024")
        self.assertEqual(sources[0]["source_grade"], "A1")
        self.assertTrue(sources[0]["accepted_for_final"])

    def test_custom_calculation_lineage_preserves_formula_and_inputs(self):
        rows = build_custom_calculation_rows(
            [
                {
                    "target_record_id": "MACRO-CN-460300-2018-PREFECTURE",
                    "target_field": "gdp_current_100m",
                    "value_origin": "calculated",
                    "calculation_id": "CAL-CN-460300-2018-gdp_current_100m",
                    "calculation_formula_id": "F-HN-SANSHA-GDP-RESIDUAL",
                    "calculation_input_record_ids": "SRC-HN-GDP-TOTAL-2018;SRC-HN-GDP-18-REGIONS-2018",
                    "calculation_input_fields": "hainan_province_gdp_total_100m;hainan_18_city_gdp_sum_100m",
                    "normalized_value": "0.09",
                    "raw_unit": "亿元",
                    "calculation_note": "省级总量减去18个市县合计。",
                }
            ],
            set(),
        )
        self.assertEqual(rows[0]["formula_id"], "F-HN-SANSHA-GDP-RESIDUAL")
        self.assertEqual(rows[0]["input_record_ids"], "SRC-HN-GDP-TOTAL-2018;SRC-HN-GDP-18-REGIONS-2018")
        self.assertEqual(rows[0]["input_fields"], "hainan_province_gdp_total_100m;hainan_18_city_gdp_sum_100m")
        self.assertEqual(rows[0]["output_value"], "0.09")

    def test_hainan_sansha_gdp_residual_is_explicit_calculation(self):
        values, _sources = load_city_year_fiscal_sources()

        expected = {
            "2018": Decimal("0.09"),
            "2019": Decimal("3.61"),
            "2020": Decimal("3.36"),
            "2021": Decimal("2.00"),
            "2022": Decimal("6.66"),
            "2023": Decimal("0.90"),
            "2024": Decimal("6.42"),
            "2025": Decimal("7.93"),
        }
        for year, value in expected.items():
            record = values.get(("CN-460300", year), {})
            self.assertEqual(record.get("gdp_current_100m"), value, year)
            self.assertEqual(record.get("value_origin"), "calculated", year)
            self.assertEqual(
                record.get("calculation_id"),
                f"CAL-CN-460300-{year}-gdp_current_100m",
                year,
            )
            self.assertIn("hainan_province_gdp_total_100m", record.get("calculation_input_fields", ""))
            self.assertIn("hainan_18_city_gdp_sum_100m", record.get("calculation_input_fields", ""))

    def test_hainan_sansha_fiscal_residual_fills_2018_to_2021(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "2018": ("1.00", "24.17"),
            "2019": ("0.47", "21.58"),
            "2020": ("0.62", "22.23"),
            "2021": ("0.89", "19.10"),
        }
        for year, (revenue, expenditure) in expected.items():
            record = values[("CN-460300", year)]
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue), year)
            self.assertEqual(record["general_public_expenditure_100m"], Decimal(expenditure), year)
            for field in ("general_public_revenue_100m", "general_public_expenditure_100m"):
                field_source = record["_field_sources"][field]
                self.assertEqual(field_source["value_origin"], "calculated", year)
                self.assertEqual(field_source["calculation_formula_id"], "F-HN-SANSHA-FISCAL-RESIDUAL", year)
                self.assertIn("hainan_all_regions_fiscal_subtotal_10000yuan", field_source["calculation_input_fields"])
                self.assertIn("hainan_18_city_fiscal_sum_10000yuan", field_source["calculation_input_fields"])

        source_ids = {item["source_doc_id"] for item in sources}
        for yearbook_year, data_year in ((2019, 2018), (2020, 2019), (2021, 2020), (2022, 2021)):
            for field in ("REVENUE", "EXPENDITURE"):
                self.assertIn(
                    f"SRC-A2-HAINAN-YEARBOOK-{yearbook_year}-SANSHA-{field}-{data_year}",
                    source_ids,
                )


    def test_hubei_direct_admin_yearbook_fills_2018_core_values(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-429000", "2018")]["gdp_current_100m"],
            Decimal("2175.65"),
        )
        self.assertEqual(
            values[("CN-429000", "2018")]["general_public_revenue_100m"],
            Decimal("84.69"),
        )
        self.assertEqual(
            values[("CN-429000", "2018")]["general_public_expenditure_100m"],
            Decimal("260.25"),
        )
        self.assertEqual(
            values[("CN-429000", "2018")]["gdp_real_growth_pct"],
            Decimal("8.29"),
        )
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-HUBEI-YEARBOOK-2019-429000-CORE", source_ids)
        source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-A2-HUBEI-YEARBOOK-2019-429000-CORE"
        )
        self.assertEqual(source["mime_type"], "application/vnd.ms-excel")
        self.assertEqual(source["access_status"], "官方Excel附件已归档")

    def test_jinan_2020_yearbook_fills_laiwu_2019_core_values(self):
        values, sources = load_city_year_fiscal_sources()

        record = values[("CN-371200", "2019")]
        self.assertEqual(record["gdp_current_100m"], Decimal("871.60"))
        self.assertEqual(record["general_public_revenue_100m"], Decimal("50.98"))
        self.assertEqual(record["general_public_expenditure_100m"], Decimal("70.23"))
        self.assertNotIn("gdp_real_growth_pct", record)
        self.assertIn("SRC-A2-JINAN-YEARBOOK-2020-LAIWU-2019", record["source_doc_id"])
        source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-A2-JINAN-YEARBOOK-2020-LAIWU-2019"
        )
        self.assertEqual(source["source_grade"], "A2")
        self.assertIn("第129、188、192页", source["note"])

    def test_xinjiang_bingtuan_official_bulletins_fill_2018_to_2023_core_values(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "2018": ("2515.16", "6.00", "103.82", "957.12"),
            "2019": ("2747.07", "6.30", "142.54", "1158.16"),
            "2020": ("2905.14", "4.50", "153.28", "1166.80"),
            "2021": ("3395.61", "8.00", "186.47", None),
            "2022": ("3500.71", "3.00", None, None),
            "2023": ("3696.58", "6.90", None, None),
        }
        fields = (
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        )
        for year, expected_values in expected.items():
            row = values.get(("CN-659000", year))
            self.assertIsNotNone(row, year)
            self.assertEqual(
                tuple(str(row.get(field)) if row.get(field) is not None else None for field in fields),
                expected_values,
            )

        source_ids = {item["source_doc_id"] for item in sources}
        for year in expected:
            self.assertIn(f"SRC-A2-XPCC-{year}-CORE", source_ids)
        self.assertIn("SRC-B2-XPCC-2021-REVENUE-RATING", source_ids)
        revenue_source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-B2-XPCC-2021-REVENUE-RATING"
        )
        self.assertEqual(revenue_source["source_grade"], "B2")
        self.assertEqual(
            values[("CN-659000", "2021")]["_field_sources"]["general_public_revenue_100m"]["page_number"],
            "13",
        )

    def test_guilin_2024_official_report_fills_whole_city_expenditure(self):
        values, sources = load_city_year_fiscal_sources()

        record = values[("CN-450300", "2024")]
        self.assertEqual(record["general_public_expenditure_100m"], Decimal("519.64"))
        self.assertIn("SRC-A2-GUILIN-CITY-FISCAL-EXPENDITURE-2024", record["source_doc_id"])
        self.assertIn(
            "一般公共预算支出=519.64亿元",
            record["general_public_expenditure_100m_evidence_excerpt"],
        )
        source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-A2-GUILIN-CITY-FISCAL-EXPENDITURE-2024"
        )
        self.assertEqual(source["publisher"], "桂林市财政局")
        self.assertEqual(source["attachment_url"], "https://czj.guilin.gov.cn/zwgk/glsbjyjsgkpt/sbjzfzys/P020251216316883452399.pdf")
        self.assertIn("不使用市本级162.38亿元", source["note"])

    def test_hubei_direct_admin_bulletins_fill_2025_core_values(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-429000", "2025")]["gdp_current_100m"],
            Decimal("3089.08"),
        )
        self.assertEqual(
            values[("CN-429000", "2025")]["general_public_revenue_100m"],
            Decimal("125.22"),
        )
        self.assertEqual(
            values[("CN-429000", "2025")]["general_public_expenditure_100m"],
            Decimal("329.76"),
        )
        self.assertEqual(
            values[("CN-429000", "2025")]["gdp_real_growth_pct"],
            Decimal("6.55"),
        )
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-HUBEI-2025-BULLETINS-429000-CORE", source_ids)

    def test_huanggang_2025_official_budget_report_fills_whole_city_expenditure(self):
        values, sources = load_city_year_fiscal_sources()

        record = values[("CN-421100", "2025")]
        self.assertEqual(record["general_public_revenue_100m"], Decimal("205.60"))
        self.assertEqual(record["general_public_expenditure_100m"], Decimal("694.00"))
        self.assertEqual(record["gov_fund_revenue_100m"], Decimal("96.88"))
        self.assertIn("SRC-A2-HUANGGANG-CITY-FISCAL-2025", record["source_doc_id"])
        self.assertIn(
            "一般公共预算支出=694.00亿元",
            record["general_public_expenditure_100m_evidence_excerpt"],
        )
        source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-A2-HUANGGANG-CITY-FISCAL-2025"
        )
        self.assertEqual(source["publisher"], "黄冈市财政局")
        self.assertEqual(source["source_grade"], "A2")

    def test_hainan_direct_admin_yearbook_fills_gdp_history_and_2023_fiscal(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-469000", "2018")]["gdp_current_100m"],
            Decimal("2181.88"),
        )
        self.assertEqual(
            values[("CN-469000", "2023")]["gdp_current_100m"],
            Decimal("3217.66"),
        )
        self.assertEqual(
            values[("CN-469000", "2023")]["general_public_revenue_100m"],
            Decimal("196.92"),
        )
        self.assertEqual(
            values[("CN-469000", "2023")]["general_public_expenditure_100m"],
            Decimal("792.51"),
        )
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-HAINAN-YEARBOOK-2024-469000-CORE-2018", source_ids)

    def test_hainan_2025_yearbook_scanned_tables_fill_2024_core_values(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-469000", "2024")]["gdp_current_100m"],
            Decimal("3441.22"),
        )
        self.assertEqual(
            values[("CN-469000", "2024")]["general_public_revenue_100m"],
            Decimal("190.27"),
        )
        self.assertEqual(
            values[("CN-469000", "2024")]["general_public_expenditure_100m"],
            Decimal("828.65"),
        )
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-HAINAN-YEARBOOK-2025-469000-GDP-2024", source_ids)
        self.assertIn("SRC-A2-HAINAN-YEARBOOK-2025-469000-REVENUE-2024", source_ids)
        self.assertIn("SRC-A2-HAINAN-YEARBOOK-2025-469000-EXPENDITURE-2024", source_ids)

    def test_hainan_2025_december_monthly_report_fills_direct_admin_aggregate(self):
        values, sources = load_city_year_fiscal_sources()

        record = values[("CN-469000", "2025")]
        self.assertEqual(record["gdp_current_100m"], Decimal("3473.85"))
        self.assertEqual(record["general_public_revenue_100m"], Decimal("206.57"))
        self.assertEqual(record["general_public_expenditure_100m"], Decimal("836.42"))
        self.assertEqual(record["gov_fund_revenue_100m"], Decimal("69.30"))
        self.assertEqual(record["gdp_real_growth_pct"], Decimal("2.80"))
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-HAINAN-2025-DEC-MONTHLY-469000-CORE", source_ids)

    def test_direct_admin_gdp_growth_is_reproducible_calculated_value(self):
        values, _sources = load_city_year_fiscal_sources()
        expected = {
            ("CN-429000", "2018"): "8.29",
            ("CN-429000", "2019"): "7.75",
            ("CN-429000", "2020"): "-4.80",
            ("CN-429000", "2021"): "10.00",
            ("CN-429000", "2022"): "2.31",
            ("CN-429000", "2023"): "5.65",
            ("CN-429000", "2024"): "5.72",
            ("CN-429000", "2025"): "6.55",
            ("CN-469000", "2018"): "4.59",
            ("CN-469000", "2019"): "4.40",
            ("CN-469000", "2020"): "2.25",
            ("CN-469000", "2021"): "8.76",
            ("CN-469000", "2022"): "1.48",
            ("CN-469000", "2023"): "7.75",
            ("CN-469000", "2024"): "3.51",
            ("CN-469000", "2025"): "2.80",
        }
        for key, raw_expected in expected.items():
            row = values[key]
            field_source = row["_field_sources"]["gdp_real_growth_pct"]
            self.assertEqual(row["gdp_real_growth_pct"], Decimal(raw_expected), key)
            self.assertEqual(field_source["value_origin"], "calculated", key)
            self.assertEqual(
                field_source["calculation_formula_id"],
                DIRECT_ADMIN_GDP_GROWTH_FORMULA_ID,
                key,
            )
            self.assertIn("previous_year_component_gdp_100m", field_source["calculation_input_fields"])
            self.assertIn("component_gdp_real_growth_pct", field_source["calculation_input_fields"])
            self.assertTrue(field_source["calculation_input_record_ids"], key)

    def test_direct_admin_growth_formula_uses_previous_year_gdp_weights(self):
        value = calculate_weighted_growth(
            [Decimal("100"), Decimal("300")],
            [Decimal("10"), Decimal("0")],
        )
        self.assertEqual(value, Decimal("2.50"))

    def test_hainan_2023_yearbook_scanned_tables_fill_2022_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-469000", "2022")]["general_public_revenue_100m"],
            Decimal("182.07"),
        )
        self.assertEqual(
            values[("CN-469000", "2022")]["general_public_expenditure_100m"],
            Decimal("765.26"),
        )
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-HAINAN-YEARBOOK-2023-469000-REVENUE-2022", source_ids)
        self.assertIn("SRC-A2-HAINAN-YEARBOOK-2023-469000-EXPENDITURE-2022", source_ids)

    def test_hainan_2019_to_2021_yearbooks_fill_2018_to_2020_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "2018": ("167.38", "709.42"),
            "2019": ("176.69", "754.67"),
            "2020": ("172.10", "770.86"),
        }
        for year, (revenue, expenditure) in expected.items():
            self.assertEqual(
                values[("CN-469000", year)]["general_public_revenue_100m"],
                Decimal(revenue),
            )
            self.assertEqual(
                values[("CN-469000", year)]["general_public_expenditure_100m"],
                Decimal(expenditure),
            )

        source_ids = {item["source_doc_id"] for item in sources}
        for yearbook_year, data_year in ((2019, 2018), (2020, 2019), (2021, 2020)):
            self.assertIn(
                f"SRC-A2-HAINAN-YEARBOOK-{yearbook_year}-469000-REVENUE-{data_year}",
                source_ids,
            )
            self.assertIn(
                f"SRC-A2-HAINAN-YEARBOOK-{yearbook_year}-469000-EXPENDITURE-{data_year}",
                source_ids,
            )

    def test_hainan_2022_yearbook_fills_2021_direct_admin_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()

        row = values[("CN-469000", "2021")]
        self.assertEqual(row["general_public_revenue_100m"], Decimal("203.20"))
        self.assertEqual(row["general_public_expenditure_100m"], Decimal("700.55"))
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-HAINAN-YEARBOOK-2022-469000-REVENUE-2021", source_ids)
        self.assertIn("SRC-A2-HAINAN-YEARBOOK-2022-469000-EXPENDITURE-2021", source_ids)

    def test_jiyuan_official_bulletins_fill_2024_and_2025_core_values(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(values[("CN-419000", "2024")]["gdp_current_100m"], Decimal("780.21"))
        self.assertEqual(values[("CN-419000", "2024")]["gdp_real_growth_pct"], Decimal("5.30"))
        self.assertEqual(values[("CN-419000", "2024")]["general_public_revenue_100m"], Decimal("60.60"))
        self.assertEqual(values[("CN-419000", "2024")]["general_public_expenditure_100m"], Decimal("79.00"))
        self.assertEqual(values[("CN-419000", "2025")]["gdp_current_100m"], Decimal("807.81"))
        self.assertEqual(values[("CN-419000", "2025")]["gdp_real_growth_pct"], Decimal("5.00"))
        self.assertEqual(values[("CN-419000", "2025")]["general_public_revenue_100m"], Decimal("62.78"))
        self.assertEqual(values[("CN-419000", "2025")]["general_public_expenditure_100m"], Decimal("82.66"))
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-JIYUAN-2024-STATISTICAL-BULLETIN-CORE", source_ids)
        self.assertIn("SRC-A2-JIYUAN-2025-STATISTICAL-BULLETIN-CORE", source_ids)

    def test_jiyuan_historical_official_sources_fill_2018_to_2023_core_values(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "2018": ("641.84", "8.30", "50.10", "69.00"),
            "2019": ("686.96", "7.80", "57.10", "77.50"),
            "2020": ("691.35", "3.30", "58.40", "81.30"),
            "2021": ("762.23", "6.10", "59.10", "81.59"),
            "2022": ("806.22", "4.40", "66.80", "84.20"),
            "2023": ("788.61", "5.40", "60.00", "75.50"),
        }
        fields = (
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        )
        for year, row in expected.items():
            self.assertEqual(
                tuple(str(values[("CN-419000", year)][field]) for field in fields),
                row,
            )
        source_ids = {item["source_doc_id"] for item in sources}
        for year in (2018, 2019, 2021, 2022, 2023):
            self.assertIn(
                f"SRC-A2-JIYUAN-{year}-STATISTICAL-BULLETIN-CORE",
                source_ids,
            )
        self.assertIn("SRC-A2-JIYUAN-2020-BUDGET-EXECUTION-CORE", source_ids)
        self.assertIn("SRC-A2-JIYUAN-2020-GDP-FINAL-REVIEW", source_ids)
        source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-A2-JIYUAN-2018-STATISTICAL-BULLETIN-CORE"
        )
        self.assertEqual(source["mime_type"], "application/msword")

    def test_sina_2025_city_revenue_chart_extracts_qinhuangdao_and_xingtai(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-130300", "2025")]["general_public_revenue_100m"],
            Decimal("174.70"),
        )
        self.assertEqual(
            values[("CN-130500", "2025")]["general_public_revenue_100m"],
            Decimal("220.90"),
        )
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-B2-SINA-300-CITIES-2025-QINHUANGDAO-REVENUE", source_ids)
        self.assertIn("SRC-B2-SINA-300-CITIES-2025-XINGTAI-REVENUE", source_ids)

    def test_xingtai_2025_official_budget_execution_overrides_secondary_revenue_and_fills_expenditure_and_fund(self):
        values, sources = load_city_year_fiscal_sources()

        row = values[("CN-130500", "2025")]
        self.assertEqual(row["general_public_revenue_100m"], Decimal("220.90"))
        self.assertEqual(row["general_public_expenditure_100m"], Decimal("701.90"))
        self.assertEqual(row["gov_fund_revenue_100m"], Decimal("120.20"))
        self.assertEqual(
            row["_field_sources"]["general_public_revenue_100m"]["source_doc_id"],
            "SRC-A2-XINGTAI-CITY-FISCAL-2025",
        )
        self.assertEqual(
            row["_field_sources"]["general_public_revenue_100m"]["data_status"],
            "execution",
        )
        source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-A2-XINGTAI-CITY-FISCAL-2025"
        )
        self.assertEqual(source["source_grade"], "A2")
        self.assertEqual(
            source["archive_path"],
            "raw/province_fiscal/2025/official/xingtai_2025_budget_execution.pdf",
        )

    def test_gotohui_songyuan_2025_area_indicator_fills_general_budget_revenue(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-220700", "2025")]["general_public_revenue_100m"],
            Decimal("71.99"),
        )
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-B2-GOTOHUI-SONGYUAN-2025-REVENUE", source_ids)

    def test_songyuan_2025_statistical_bulletin_fills_whole_city_expenditure(self):
        values, sources = load_city_year_fiscal_sources()

        row = values[("CN-220700", "2025")]
        self.assertEqual(row["general_public_expenditure_100m"], Decimal("308.03"))
        self.assertIn(
            "一般公共预算支出=308.03亿元",
            row["general_public_expenditure_100m_evidence_excerpt"],
        )
        self.assertEqual(
            row["_field_sources"]["general_public_expenditure_100m"]["source_doc_id"],
            "SRC-B2-SONGYUAN-STATISTICAL-BULLETIN-2025-EXPENDITURE",
        )
        source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-B2-SONGYUAN-STATISTICAL-BULLETIN-2025-EXPENDITURE"
        )
        self.assertEqual(source["source_grade"], "B2")
        self.assertEqual(source["period_end"], "2025-12-31")
        self.assertIn("地方财政支出", source["note"])

    def test_baishan_2025_local_revenue_is_explicitly_mapped_to_general_budget_revenue(self):
        values, sources = load_city_year_fiscal_sources()

        row = values[("CN-220600", "2025")]
        self.assertEqual(row["general_public_revenue_100m"], Decimal("36.80"))
        self.assertEqual(row["gdp_current_100m"], Decimal("590.17"))
        self.assertEqual(row["gdp_real_growth_pct"], Decimal("5.60"))
        self.assertEqual(row["general_public_expenditure_100m"], Decimal("230.21"))
        self.assertIn(
            "一般公共预算收入=36.80亿元",
            row["general_public_revenue_100m_evidence_excerpt"],
        )
        source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-B2-BAISHAN-CITY-MACRO-FISCAL-2025"
        )
        self.assertIn("地方级财政收入", source["note"])
        self.assertIn("规范映射", source["note"])

    def test_ali_2024_rating_report_fills_gdp_growth(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-542500", "2024")]["gdp_real_growth_pct"],
            Decimal("8.60"),
        )
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-B2-ALI-REGION-GDP-GROWTH-2024", source_ids)

    def test_ali_official_history_fills_2020_fiscal_and_corrects_2021_gdp(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-542500", "2020")]["general_public_revenue_100m"],
            Decimal("5.18"),
        )
        self.assertEqual(
            values[("CN-542500", "2020")]["general_public_expenditure_100m"],
            Decimal("101.05"),
        )
        self.assertEqual(
            values[("CN-542500", "2021")]["gdp_current_100m"],
            Decimal("77.65"),
        )
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-B2-ALI-REGION-REVENUE-2020", source_ids)
        self.assertIn("SRC-A2-ALI-REGION-FISCAL-2020-DECISION-XLS", source_ids)
        self.assertIn("SRC-A2-ALI-REGION-GDP-2021-REVIEW", source_ids)

    def test_ali_ceic_history_fills_2022_2023_revenue_and_expenditure(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-542500", "2022")]["general_public_revenue_100m"],
            Decimal("5.54"),
        )
        self.assertEqual(
            values[("CN-542500", "2022")]["general_public_expenditure_100m"],
            Decimal("113.92"),
        )
        self.assertEqual(
            values[("CN-542500", "2023")]["general_public_revenue_100m"],
            Decimal("7.20"),
        )
        self.assertEqual(
            values[("CN-542500", "2023")]["general_public_expenditure_100m"],
            Decimal("162.73"),
        )
        for source_id in (
            "SRC-B2-CEIC-ALI-REVENUE-2022",
            "SRC-B2-CEIC-ALI-REVENUE-2023",
            "SRC-B2-CEIC-ALI-EXPENDITURE-2022",
            "SRC-B2-CEIC-ALI-EXPENDITURE-2023",
        ):
            self.assertIn(source_id, {item["source_doc_id"] for item in sources})
        ceic_source = next(
            item for item in sources if item["source_doc_id"] == "SRC-B2-CEIC-ALI-REVENUE-2022"
        )
        self.assertEqual(ceic_source["title_source"], "secondary_public_page")
        self.assertEqual(ceic_source["access_status"], "公开指标页已归档")
        self.assertEqual(
            values[("CN-542500", "2023")]["_field_sources"]["general_public_revenue_100m"]["source_grade"],
            "B2",
        )

    def test_yushu_2024_gotohui_overview_is_preserved_with_official_fiscal_source(self):
        values, sources = load_city_year_fiscal_sources()

        row = values[("CN-632700", "2024")]
        self.assertEqual(row["general_public_revenue_100m"], Decimal("3.74"))
        self.assertEqual(row["general_public_expenditure_100m"], Decimal("163.76"))
        source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-B2-GOTOHUI-YUSHU-2024-REVENUE"
        )
        self.assertIn("总览", source["note"])
        self.assertIn("玉树统计局", source["note"])

    def test_yushu_2024_official_budget_execution_fills_whole_prefecture_expenditure(self):
        values, sources = load_city_year_fiscal_sources()

        row = values[("CN-632700", "2024")]
        self.assertEqual(row["general_public_expenditure_100m"], Decimal("163.76"))
        self.assertEqual(
            row["_field_sources"]["general_public_expenditure_100m"]["source_doc_id"],
            "SRC-A2-YUSHU-2024-BUDGET-EXECUTION",
        )
        self.assertEqual(
            row["_field_sources"]["general_public_expenditure_100m"]["source_grade"],
            "A2",
        )
        self.assertEqual(row["gov_fund_revenue_100m"], Decimal("0.25"))
        self.assertEqual(
            row["_field_sources"]["gov_fund_revenue_100m"]["source_doc_id"],
            "SRC-A2-YUSHU-2024-BUDGET-EXECUTION",
        )
        source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-A2-YUSHU-2024-BUDGET-EXECUTION"
        )
        self.assertEqual(source["source_grade"], "A2")
        self.assertIn("全州", source["note"])
        self.assertEqual(
            row["_field_sources"]["general_public_expenditure_100m"]["data_status"],
            "execution",
        )

    def test_ceic_2025_expenditure_pages_fill_qinhuangdao_qitaihe_yanan(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-130300", "2025")]["general_public_expenditure_100m"],
            Decimal("398.90"),
        )
        self.assertEqual(
            values[("CN-230900", "2025")]["general_public_expenditure_100m"],
            Decimal("115.30"),
        )
        self.assertEqual(
            values[("CN-610600", "2025")]["general_public_expenditure_100m"],
            Decimal("515.88"),
        )
        source_ids = {item["source_doc_id"] for item in sources}
        for source_id in (
            "SRC-B2-CEIC-QINHUANGDAO-2025-EXPENDITURE-YTD",
            "SRC-B2-CEIC-QITAIHE-2025-EXPENDITURE",
            "SRC-B2-CEIC-YANAN-2025-EXPENDITURE",
        ):
            self.assertIn(source_id, source_ids)
        for city_id in ("CN-130300", "CN-230900", "CN-610600"):
            self.assertEqual(
                values[(city_id, "2025")]["_field_sources"]
                ["general_public_expenditure_100m"]["source_grade"],
                "B2",
            )

    def test_anyang_2025_finance_infographic_fills_whole_city_expenditure(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-410500", "2025")]["general_public_expenditure_100m"],
            Decimal("458.90"),
        )
        source = next(
            item for item in sources
            if item["source_doc_id"] == "SRC-B2-ANYANG-2025-EXPENDITURE"
        )
        self.assertEqual(source["source_grade"], "B2")
        self.assertEqual(source["title_source"], "secondary_public_page")
        self.assertEqual(
            values[("CN-410500", "2025")]["_field_sources"]
            ["general_public_expenditure_100m"]["data_status"],
            "execution",
        )

    def test_heze_2025_official_budget_execution_fills_whole_city_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertEqual(
            values[("CN-371700", "2025")]["general_public_revenue_100m"],
            Decimal("333.37"),
        )
        self.assertEqual(
            values[("CN-371700", "2025")]["general_public_expenditure_100m"],
            Decimal("759.26"),
        )
        heze_source = next(
            source
            for source in sources
            if source["source_doc_id"] == "SRC-A2-HEZE-CITY-FISCAL-2025"
        )
        self.assertEqual(heze_source["source_grade"], "A2")
        self.assertEqual(
            values[("CN-371700", "2025")]["_field_sources"]["general_public_expenditure_100m"]["data_status"],
            "execution",
        )

    def test_guangdong_2025_provincial_debt_table_extracts_whole_city_limit_and_balance(self):
        city_master = [
            {
                "city_id": "CN-440200",
                "city_name_cn": "韶关市",
                "province_name": "广东省",
                "metric_year": "2025",
            },
            {
                "city_id": "CN-441700",
                "city_name_cn": "阳江市",
                "province_name": "广东省",
                "metric_year": "2025",
            },
            {
                "city_id": "CN-440300",
                "city_name_cn": "深圳市",
                "province_name": "广东省",
                "metric_year": "2025",
            },
            {
                "city_id": "CN-440400",
                "city_name_cn": "珠海市",
                "province_name": "广东省",
                "metric_year": "2025",
            },
        ]

        facts, sources = extract_official_debt_facts(city_master)

        shaoguan = facts[("CN-440200", "2025")]
        self.assertEqual(shaoguan["statutory_debt_limit_100m"], Decimal("943.99"))
        self.assertEqual(shaoguan["statutory_debt_balance_100m"], Decimal("937.62"))
        self.assertEqual(shaoguan["source_grade"], "A2")
        self.assertTrue(any(item["source_doc_id"] == "SRC-PROVINCE-DEBT-GUANGDONG-2025" for item in sources))

        yangjiang = facts[("CN-441700", "2025")]
        self.assertEqual(yangjiang["statutory_debt_limit_100m"], Decimal("683.97"))
        self.assertEqual(yangjiang["statutory_debt_balance_100m"], Decimal("679.70"))

        shenzhen = facts[("CN-440300", "2025")]
        self.assertEqual(shenzhen["statutory_debt_limit_100m"], Decimal("4557.18"))
        self.assertEqual(shenzhen["statutory_debt_balance_100m"], Decimal("4492.30"))

        zhuhai = facts[("CN-440400", "2025")]
        self.assertEqual(zhuhai["statutory_debt_limit_100m"], Decimal("1743.64"))
        self.assertEqual(zhuhai["statutory_debt_balance_100m"], Decimal("1737.09"))

    def test_gotohui_snapshot_collector_rejects_budget_and_component_titles(self):
        self.assertTrue(
            acceptable_series_title("fund", "西宁市", "西宁市地方政府性基金收入")
        )
        self.assertTrue(
            acceptable_series_title("fund", "西宁市", "西宁市地方政府性基金本级收入")
        )
        self.assertFalse(
            acceptable_series_title("fund", "西宁市", "西宁市政府性基金收入预算数")
        )
        self.assertFalse(
            acceptable_series_title("fund", "西宁市", "西宁市政府性基金收入:国有土地使用权出让收入")
        )

    def test_gotohui_snapshot_collector_normalizes_units_and_deduplicates_series(self):
        self.assertEqual(normalize_series_value("revenue", "123456", "万元"), Decimal("12.35"))
        self.assertEqual(normalize_series_value("population", "3142300", "人"), Decimal("314.23"))
        existing = [{"series_id": "1", "metric": "gdp"}]
        additions = [{"series_id": "1", "metric": "gdp"}, {"series_id": "2", "metric": "growth"}]
        self.assertEqual(
            [item["series_id"] for item in merge_snapshot_series(existing, additions)],
            ["1", "2"],
        )

    def test_gotohui_snapshot_collector_skips_city_years_not_in_roster(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "outputs/national_prefecture_panel_2018_2026"
            output.mkdir(parents=True)
            with (output / "city_macro_fiscal.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["city_id", "city_name_cn", "metric_year", "gdp_current_100m"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "city_id": "CN-133100",
                        "city_name_cn": "雄安新区",
                        "metric_year": "2025",
                        "gdp_current_100m": "",
                    }
                )
            self.assertEqual(_read_city_targets(root, {"gdp"}), [("gdp", "CN-133100", "雄安新区")])

    def test_crei_bulletin_parser_keeps_prefecture_scope_and_exact_units(self):
        title = "2025年清远市国民经济和社会发展统计公报"
        self.assertTrue(is_target_bulletin_title(title, "清远市"))
        self.assertFalse(is_target_bulletin_title("2025年清远市清新区国民经济和社会发展统计公报", "清远市"))
        parsed = parse_bulletin_text(
            "根据统一核算，2025年全市地区生产总值2317.47亿元，比上年增长4.5%。"
            "年末全市常住人口397.64万人。全年一般公共预算收入123.45亿元，"
            "一般公共预算支出234.56亿元。"
        )
        self.assertEqual(parsed["gdp_current_100m"], Decimal("2317.47"))
        self.assertEqual(parsed["gdp_real_growth_pct"], Decimal("4.50"))
        self.assertEqual(parsed["resident_population_10k"], Decimal("397.64"))
        self.assertEqual(parsed["general_public_revenue_100m"], Decimal("123.45"))
        self.assertEqual(parsed["general_public_expenditure_100m"], Decimal("234.56"))

    def test_bulletin_parser_reads_population_in_people_and_government_fund_revenue(self):
        parsed = parse_bulletin_text(
            "年末全市常住人口3294517人。全市政府性基金预算收入14.4亿元。"
        )
        self.assertEqual(parsed["resident_population_10k"], Decimal("329.45"))
        self.assertEqual(parsed["gov_fund_revenue_100m"], Decimal("14.40"))

    def test_hongheiku_loader_backfills_population_and_fund_but_excludes_county_pages(self):
        root = Path(__file__).resolve().parents[1]
        with (root / "outputs/national_prefecture_panel_2018_2026/dim_city.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            city_master = list(csv.DictReader(handle))
        values, _sources = load_hongheiku_city_bulletin_sources(root, city_master)

        daqing = values[("CN-230600", "2022")]
        self.assertEqual(daqing["resident_population_10k"], Decimal("272.70"))
        self.assertEqual(daqing["gov_fund_revenue_100m"], Decimal("14.90"))
        self.assertNotIn(("CN-371400", "2025"), values)

    def test_hongheiku_sitemap_filter_keeps_only_requested_city_directory(self):
        urls = [
            "https://tjgb.hongheiku.com/djs/123.html",
            "https://tjgb.hongheiku.com/xjtjgb/xj2020/456.html",
            "https://tjgb.hongheiku.com/djs/789.html",
        ]
        self.assertEqual(
            _filter_sitemap_urls(urls, ("djs/",)),
            [urls[0], urls[2]],
        )

    def test_hongheiku_crawler_skips_urls_already_in_snapshot(self):
        urls = [
            "https://tjgb.hongheiku.com/djs/123.html",
            "https://tjgb.hongheiku.com/djs/456.html",
        ]
        self.assertEqual(
            _unfetched_urls(urls, {urls[0]: {"source_url": urls[0]}}),
            [urls[1]],
        )

    def test_crei_bulletin_parser_does_not_use_later_deposit_balance_as_revenue(self):
        parsed = parse_bulletin_text(
            "全年全市公共财政预算收入完成125.7亿元，比上年增长15.5%。"
            "其中，税收收入完成79.3亿元。一般公共预算支出509.9亿元。"
            "年末全市金融机构人民币各项存款余额2523.1亿元。"
        )
        self.assertEqual(parsed["general_public_revenue_100m"], Decimal("125.70"))
        self.assertEqual(parsed["general_public_expenditure_100m"], Decimal("509.90"))

    def test_crei_bulletin_parser_handles_spaced_numbers_and_parenthetical_scope(self):
        parsed = parse_bulletin_text(
            "其中，地方一般公共预算收入（含两县）87.25亿元，"
            "地方一般公共预算支出（含两县）317.57亿元。"
            "全市一般公共预算支出8 00.12亿元。"
            "年末全市常住人口225．00万人。"
        )
        self.assertEqual(parsed["general_public_revenue_100m"], Decimal("87.25"))
        self.assertEqual(parsed["general_public_expenditure_100m"], Decimal("317.57"))
        self.assertEqual(parsed["resident_population_10k"], Decimal("225.00"))

    def test_crei_bulletin_parser_handles_footnotes_and_public_finance_variants(self):
        parsed = parse_bulletin_text(
            "全年地方一般公共预算收入[8]184.20亿元，"
            "一般公共财政预算支出599.20亿元。"
        )
        self.assertEqual(parsed["general_public_revenue_100m"], Decimal("184.20"))
        self.assertEqual(parsed["general_public_expenditure_100m"], Decimal("599.20"))

    def test_siping_2025_official_report_uses_whole_city_county_scope(self):
        values, sources = load_city_year_fiscal_sources()
        siping = values[("CN-220300", "2025")]
        self.assertEqual(siping["general_public_revenue_100m"], Decimal("75.14"))
        self.assertEqual(siping["general_public_expenditure_100m"], Decimal("291.44"))
        self.assertEqual(
            siping["_field_sources"]["general_public_revenue_100m"]["source_grade"],
            "A2",
        )
        self.assertEqual(
            siping["_field_sources"]["general_public_expenditure_100m"]["source_grade"],
            "A2",
        )
        self.assertIn("SRC-A2-SIPING-CITY-FISCAL-2025", siping["source_doc_id"])
        self.assertTrue(any(item["source_doc_id"] == "SRC-A2-SIPING-CITY-FISCAL-2025" for item in sources))

    def test_2024_official_city_core_batch_upgrades_d_provisional_gdp_values(self):
        values, sources = load_city_year_fiscal_sources()

        jining = values[("CN-370800", "2024")]
        self.assertEqual(jining["gdp_current_100m"], Decimal("5867.50"))
        self.assertEqual(
            jining["_field_sources"]["gdp_current_100m"]["source_grade"],
            "A2",
        )
        self.assertEqual(
            jining["_field_sources"]["general_public_revenue_100m"]["source_grade"],
            "A2",
        )

        mudanjiang = values[("CN-231000", "2024")]
        self.assertEqual(mudanjiang["gdp_current_100m"], Decimal("1051.40"))
        self.assertEqual(
            mudanjiang["_field_sources"]["gdp_current_100m"]["source_grade"],
            "A2",
        )

        baoji = values[("CN-610300", "2024")]
        self.assertEqual(
            baoji["_field_sources"]["gdp_real_growth_pct"]["source_grade"],
            "A2",
        )
        self.assertIn(
            "SRC-A2-BAOJI-CITY-STATISTICAL-BULLETIN-2024",
            {item["source_doc_id"] for item in sources},
        )

    def test_liaoyuan_2025_official_page_uses_local_general_budget_revenue_and_expenditure(self):
        values, sources = load_city_year_fiscal_sources()
        liaoyuan = values[("CN-220400", "2025")]
        self.assertEqual(liaoyuan["general_public_revenue_100m"], Decimal("31.77"))
        self.assertEqual(liaoyuan["general_public_expenditure_100m"], Decimal("174.27"))
        self.assertEqual(
            liaoyuan["_field_sources"]["general_public_revenue_100m"]["source_grade"],
            "A2",
        )
        self.assertEqual(
            liaoyuan["_field_sources"]["general_public_expenditure_100m"]["source_grade"],
            "A2",
        )
        self.assertIn("SRC-A2-LIAOYUAN-CITY-FISCAL-2025", liaoyuan["source_doc_id"])
        self.assertTrue(any(item["source_doc_id"] == "SRC-A2-LIAOYUAN-CITY-FISCAL-2025" for item in sources))

    def test_yanbian_2025_official_page_uses_whole_state_budget_values(self):
        values, sources = load_city_year_fiscal_sources()
        yanbian = values[("CN-222400", "2025")]
        self.assertEqual(yanbian["general_public_revenue_100m"], Decimal("94.80"))
        self.assertEqual(yanbian["general_public_expenditure_100m"], Decimal("402.60"))
        self.assertEqual(
            yanbian["_field_sources"]["general_public_revenue_100m"]["source_grade"],
            "A2",
        )
        self.assertEqual(
            yanbian["_field_sources"]["general_public_expenditure_100m"]["source_grade"],
            "A2",
        )
        self.assertIn("SRC-A2-YANBIAN-STATE-FISCAL-2025", yanbian["source_doc_id"])
        self.assertTrue(any(item["source_doc_id"] == "SRC-A2-YANBIAN-STATE-FISCAL-2025" for item in sources))

    def test_gotohui_public_series_adapter_keeps_exact_units_and_b2_lineage(self):
        root = Path(__file__).resolve().parents[1]
        with (root / "outputs/national_prefecture_panel_2018_2026/dim_city.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            city_master = list(csv.DictReader(handle))
        values, sources = load_gotohui_city_series_sources(root, city_master)

        self.assertGreaterEqual(len(sources), 1500)
        population = values[("CN-340400", "2018")]
        self.assertEqual(population["resident_population_10k"], Decimal("314.23"))
        self.assertEqual(population["source_grade"], "B2")
        self.assertEqual(population["source_platform"], "gotohui")
        revenue = values[("CN-152900", "2018")]
        self.assertEqual(revenue["general_public_revenue_100m"], Decimal("24.31"))
        self.assertIn("2018", revenue["general_public_revenue_100m_evidence_excerpt"])
        fund = values[("CN-440300", "2018")]
        self.assertEqual(fund["gov_fund_revenue_100m"], Decimal("964.64"))
        limit = values[("CN-440300", "2018")]
        self.assertEqual(limit["statutory_debt_limit_100m"], Decimal("385.00"))

    def test_gotohui_limit_series_is_merged_into_empty_national_fields(self):
        root = Path(__file__).resolve().parents[1]
        with (root / "outputs/national_prefecture_panel_2018_2026/dim_city.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            city_master = list(csv.DictReader(handle))
        candidates, _sources = load_gotohui_city_series_sources(root, city_master)
        target_keys = {("CN-360400", "2022"), ("CN-542500", "2022")}
        merged = {}

        merge_gotohui_city_series_batch(merged, {
            key: candidates[key]
            for key in target_keys
        })

        self.assertEqual(
            merged[("CN-360400", "2022")]["statutory_debt_limit_100m"],
            Decimal("1299.81"),
        )
        self.assertEqual(
            merged[("CN-542500", "2022")]["statutory_debt_limit_100m"],
            Decimal("30.58"),
        )
        self.assertIn(
            "SRC-B2-GOTOHUI-LIMIT-1679381",
            merged[("CN-360400", "2022")]["source_doc_id"],
        )

    def test_dachuang_public_panel_is_explicit_d_provisional_and_normalizes_units(self):
        root = Path(__file__).resolve().parents[1]
        with (root / "outputs/national_prefecture_panel_2018_2026/dim_city.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            city_master = list(csv.DictReader(handle))
        values, sources = load_dachuang_city_panel_sources(root, city_master)

        shenzhen = values[("CN-440300", "2021")]
        self.assertEqual(shenzhen["gdp_current_100m"], Decimal("31473.84"))
        self.assertEqual(shenzhen["general_public_revenue_100m"], Decimal("3857.39"))
        self.assertEqual(shenzhen["resident_population_10k"], Decimal("1768.16"))
        self.assertEqual(shenzhen["source_grade"], "D")
        self.assertEqual(shenzhen["data_status"], "provisional")
        self.assertEqual(shenzhen["source_platform"], "dachuang")
        self.assertTrue(sources[0]["content_hash_sha256"])

        # 2022 年临汾人口是明显的十倍异常值，适配器宁可留空，也不把异常值写入主表。
        self.assertNotIn("resident_population_10k", values[("CN-141000", "2022")])

    def test_haidatas_public_panel_reads_exact_cells_and_excludes_ambiguous_population(self):
        root = Path(__file__).resolve().parents[1]
        with (root / "outputs/national_prefecture_panel_2018_2026/dim_city.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            city_master = list(csv.DictReader(handle))
        values, sources = load_haidatas_city_panel_sources(root, city_master)

        self.assertEqual(len(sources), 1)
        self.assertEqual(len(values), 1348)
        anqing = values[("CN-340800", "2018")]
        self.assertEqual(anqing["gdp_current_100m"], Decimal("2196.75"))
        self.assertEqual(anqing["general_public_revenue_100m"], Decimal("133.20"))
        self.assertEqual(anqing["gov_fund_revenue_100m"], Decimal("177.30"))
        self.assertEqual(anqing["statutory_debt_limit_100m"], Decimal("413.17"))
        self.assertEqual(anqing["source_grade"], "D")
        self.assertEqual(anqing["source_platform"], "haidatas")
        self.assertEqual(
            anqing["_field_sources"]["gov_fund_revenue_100m"]["cell_range"],
            "AF1017",
        )
        self.assertNotIn("resident_population_10k", anqing)
        self.assertTrue(sources[0]["content_hash_sha256"])

    def test_city_yearbook_adapter_reads_exact_city_cells_and_units(self):
        root = Path(__file__).resolve().parents[1]
        with (root / "outputs/national_prefecture_panel_2018_2026/dim_city.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            city_master = list(csv.DictReader(handle))
        values, sources = load_city_yearbook_sources(root, city_master)

        self.assertEqual(len(sources), 7)
        beijing_2019 = values[("CN-110000", "2019")]
        self.assertEqual(beijing_2019["gdp_current_100m"], Decimal("35371.00"))
        self.assertEqual(beijing_2019["general_public_revenue_100m"], Decimal("5817.10"))
        self.assertEqual(beijing_2019["source_grade"], "B2")
        self.assertEqual(values[("CN-110000", "2020")]["resident_population_10k"], Decimal("2189.00"))
        self.assertEqual(values[("CN-110000", "2023")]["resident_population_10k"], Decimal("2186.00"))
        self.assertNotIn("resident_population_10k", values[("CN-110000", "2021")])

    def test_city_yearbook_2025_population_adapter_reads_2024_resident_population(self):
        root = Path(__file__).resolve().parents[1]
        with (root / "outputs/national_prefecture_panel_2018_2026/dim_city.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            city_master = list(csv.DictReader(handle))
        values, sources = load_city_yearbook_sources(root, city_master)

        jincheng = values[("CN-140500", "2024")]
        self.assertEqual(jincheng["resident_population_10k"], Decimal("217.00"))
        self.assertEqual(jincheng["resident_population_10k_cell_range"], "C28")
        self.assertEqual(jincheng["source_doc_id"], "SRC-B2-CITY-YEARBOOK-2025-POPULATION")
        self.assertEqual(jincheng["source_grade"], "B2")
        self.assertIn("Sheet9", jincheng["source_locator"])
        self.assertEqual(len(sources), 7)
        source = next(item for item in sources if item["source_doc_id"] == "SRC-B2-CITY-YEARBOOK-2025-POPULATION")
        self.assertIn("chinautc.com", source["landing_page_url"])
        self.assertTrue(source["content_hash_sha256"])

    def test_jiangsu_2025_budget_excerpts_extract_six_whole_city_batches(self):
        values, sources = load_city_year_fiscal_sources()
        expected = {
            "CN-320100": ("1620.90", "1704.90", "886.40"),
            "CN-320600": ("730.00", "1188.70", "768.90"),
            "CN-320700": ("305.70", "607.80", "206.50"),
            "CN-320800": ("335.30", "718.30", "311.60"),
            "CN-320900": ("515.74", "1099.03", "425.83"),
            "CN-321300": ("316.60", "688.60", "215.10"),
        }
        for city_id, (revenue, expenditure, fund_revenue) in expected.items():
            with self.subTest(city_id=city_id):
                row = values[(city_id, "2025")]
                self.assertEqual(row["general_public_revenue_100m"], Decimal(revenue))
                self.assertEqual(row["general_public_expenditure_100m"], Decimal(expenditure))
                self.assertEqual(row["gov_fund_revenue_100m"], Decimal(fund_revenue))
                self.assertEqual(row["data_status"], "execution")
        source_ids = {
            item["source_doc_id"]
            for item in sources
            if "JIANGSU_" in item["source_doc_id"]
        }
        self.assertEqual(len(source_ids), 6)

    def test_city_yearbook_upgrades_provisional_panel_values_without_overwriting_official(self):
        city = {
            "city_id": "CN-110000",
            "admin_code_6": "110000",
            "city_name_cn": "北京市",
            "province_code": "110000",
            "province_name": "北京市",
            "prefecture_type": "municipality",
            "sample_tier": "separate",
            "metric_year": "2020",
        }
        yearbook = {
            ("CN-110000", "2020"): {
                "source_doc_id": "SRC-B2-CITY-YEARBOOK-2021",
                "source_grade": "B2",
                "source_format": "xlsx",
                "source_locator": "yearbook.xlsx；Sheet1；行=7；城市=北京市",
                "table_name": "2020年地级以上城市数据",
                "sheet_name": "Sheet1",
                "gdp_current_100m": Decimal("36103.00"),
                "gdp_current_100m_raw": Decimal("36103"),
                "gdp_current_100m_raw_unit": "亿元",
                "gdp_current_100m_cell_range": "T7",
                "gdp_current_100m_evidence_excerpt": "36103",
                "gdp_real_growth_pct": Decimal("1.20"),
                "gdp_real_growth_pct_raw": Decimal("1.2"),
                "gdp_real_growth_pct_raw_unit": "%",
                "gdp_real_growth_pct_cell_range": "X7",
                "gdp_real_growth_pct_evidence_excerpt": "1.2",
                "_field_sources": {},
            },
        }
        yearbook[("CN-110000", "2020")]["_field_sources"] = {
            field: dict(yearbook[("CN-110000", "2020")])
            for field in ("gdp_current_100m", "gdp_real_growth_pct")
        }
        rows, lineage = build_macro_rows(
            [city],
            [
                {
                    "city_code": "110000",
                    "year": "2020",
                    "gdp": "350000",
                    "gdp_growth": "0.5",
                    "pop_avg": "",
                    "fiscal_revenue": "100000",
                    "fiscal_exp": "200000",
                }
            ],
            {},
            city_yearbook_macro=yearbook,
        )
        self.assertEqual(rows[0]["gdp_current_100m"], Decimal("36103.00"))
        self.assertEqual(rows[0]["source_grade"], "B2")
        self.assertTrue(any(item["source_doc_id"] == "SRC-B2-CITY-YEARBOOK-2021" for item in lineage))
        self.assertTrue(any(item["source_doc_id"] == "SRC-CITY-PANEL-1990-2023" and not item["selected_flag"] for item in lineage))

    def test_supplemental_2025_fiscal_adapter_reads_whole_city_values(self):
        values, sources = load_city_year_fiscal_sources()

        self.assertGreaterEqual(len(sources), 220)
        self.assertEqual(values[("CN-330100", "2025")]["gov_fund_revenue_100m"], Decimal("1717.13"))
        self.assertEqual(values[("CN-420100", "2025")]["gov_fund_revenue_100m"], Decimal("1453.81"))
        self.assertEqual(values[("CN-410200", "2025")]["gov_fund_revenue_100m"], Decimal("72.80"))
        self.assertEqual(values[("CN-653000", "2025")]["resident_population_10k"], Decimal("64.07"))

        supplemental = [
            source for source in sources
            if str(source.get("source_doc_id", "")).startswith("SRC-SUPPLEMENTAL-CITY-FISCAL-2025-")
        ]
        self.assertEqual(len(supplemental), 68)
        self.assertTrue(all(source["content_hash_sha256"] for source in supplemental))
        self.assertTrue(any("chinamoney.com.cn" in source["source_url"] for source in supplemental))

    def test_yunnan_2024_regional_fiscal_adapter_reads_exact_table(self):
        values, sources = load_city_year_fiscal_sources()
        regional = [
            source for source in sources
            if str(source.get("source_doc_id", "")).startswith("SRC-B2-YUNNAN-REGIONAL-FISCAL-2024-")
        ]
        self.assertEqual(len(regional), 10)
        sample = values[("CN-530900", "2024")]
        self.assertEqual(sample["gdp_current_100m"], Decimal("1150.19"))
        self.assertEqual(sample["gdp_real_growth_pct"], Decimal("3.70"))
        self.assertEqual(sample["general_public_revenue_100m"], Decimal("50.56"))
        self.assertEqual(sample["gov_fund_revenue_100m"], Decimal("20.23"))

    def test_sichuan_2025_regional_table_extracts_government_fund_revenue(self):
        values, sources = load_city_year_fiscal_sources()

        regional = [
            source for source in sources
            if str(source.get("source_doc_id", "")).startswith("SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-REVENUE-")
        ]
        self.assertEqual(len(regional), 18)
        self.assertEqual(values[("CN-511900", "2025")]["gov_fund_revenue_100m"], Decimal("123.94"))
        self.assertEqual(values[("CN-510600", "2025")]["gov_fund_revenue_100m"], Decimal("186.57"))
        self.assertEqual(values[("CN-513300", "2025")]["gov_fund_revenue_100m"], Decimal("8.63"))

    def test_multi_city_rating_tables_fill_2024_and_2025_economic_fiscal_gaps(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            ("CN-130400", "2024"): ("4703.80", "6.10", "379.54", "942.22", "105.82"),
            ("CN-130400", "2025"): ("4920.10", "6.40", None, None, None),
            ("CN-510500", "2024"): ("2836.52", "4.00", "222.17", "500.47", "179.38"),
            ("CN-510500", "2025"): ("3004.29", "6.40", None, None, None),
            ("CN-350700", "2024"): ("2090.30", "5.30", "114.84", None, "64.27"),
            ("CN-350700", "2025"): ("2189.73", "5.00", "119.21", None, None),
            ("CN-350900", "2024"): ("3901.99", "1.10", "254.60", None, "62.77"),
            ("CN-350900", "2025"): ("4251.72", "7.50", "271.45", None, None),
            ("CN-350200", "2024"): ("8589.01", "5.50", "933.35", "1059.20", "423.68"),
            ("CN-350200", "2025"): ("8980.37", "5.70", None, None, None),
        }
        fields = (
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
            "gov_fund_revenue_100m",
        )
        for key, row_expected in expected.items():
            record = values[key]
            for field, expected_value in zip(fields, row_expected):
                if expected_value is not None:
                    self.assertEqual(record[field], Decimal(expected_value), f"{key} {field}")

        source_ids = {source["source_doc_id"] for source in sources}
        self.assertIn("SRC-B2-CITY-RATING-2024-HANDAN", source_ids)
        self.assertIn("SRC-B2-CITY-RATING-2025-XIAMEN", source_ids)

    def test_next_rating_batch_fills_zhejiang_and_city_2024_2025_gaps(self):
        values, sources = load_city_year_fiscal_sources()

        zhejiang_expected = {
            "CN-330100": ("23011.00", "5.20", "2693.21"),
            "CN-330200": ("18716.00", "4.90", "1795.23"),
            "CN-330300": ("10213.90", "6.10", "647.03"),
            "CN-330400": ("7851.06", "5.20", "652.44"),
            "CN-330500": ("4452.80", "5.90", "389.50"),
            "CN-330600": ("8932.00", "6.50", "603.45"),
            "CN-330700": ("7313.47", "6.30", "555.63"),
            "CN-330800": ("2401.63", "5.50", "216.10"),
            "CN-330900": ("2346.10", "6.60", "217.52"),
            "CN-331000": ("7005.87", "6.10", "517.47"),
            "CN-331100": ("2301.40", "6.40", "198.05"),
        }
        for city_id, (gdp, growth, revenue) in zhejiang_expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["gdp_current_100m"], Decimal(gdp), city_id)
            self.assertEqual(record["gdp_real_growth_pct"], Decimal(growth), city_id)
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue), city_id)

        expected = {
            ("CN-440400", "2024"): ("4479.06", "3.50", "475.16", "648.39", "91.38"),
            ("CN-440400", "2025"): ("4573.10", "6.90", "494.10", "668.64", None),
            ("CN-340800", "2024"): ("3156.00", "6.00", "203.40", None, "51.60"),
            ("CN-340800", "2025"): ("3306.08", "5.70", "210.50", None, None),
            ("CN-440600", "2024"): (None, None, "767.08", "919.99", "492.77"),
            ("CN-320300", "2024"): (None, None, "560.29", "1052.38", "388.41"),
            ("CN-320300", "2025"): ("9957.22", "5.80", None, None, None),
            ("CN-321200", "2024"): ("7020.95", "5.10", "453.08", "695.93", "420.56"),
            ("CN-321200", "2025"): ("7255.27", "5.30", None, None, None),
        }
        fields = (
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
            "gov_fund_revenue_100m",
        )
        for key, row_expected in expected.items():
            record = values[key]
            for field, expected_value in zip(fields, row_expected):
                if expected_value is not None:
                    self.assertEqual(record[field], Decimal(expected_value), f"{key} {field}")

        source_ids = {source["source_doc_id"] for source in sources}
        self.assertIn("SRC-B2-ZHEJIANG-REGIONAL-FISCAL-2025-HANGZHOU", source_ids)
        self.assertIn("SRC-B2-CITY-RATING-2024-ZHUHAI", source_ids)

    def test_validated_next_city_batches_are_integrated_into_national_panel_sources(self):
        values, sources = load_city_year_fiscal_sources()

        changdu = values[("CN-540300", "2025")]
        self.assertEqual(changdu["gdp_current_100m"], Decimal("424.86"))
        self.assertEqual(changdu["gdp_real_growth_pct"], Decimal("6.70"))
        self.assertEqual(changdu["general_public_revenue_100m"], Decimal("33.64"))
        self.assertEqual(changdu["general_public_expenditure_100m"], Decimal("342.32"))

        harbin = values[("CN-230100", "2025")]
        self.assertEqual(harbin["gdp_current_100m"], Decimal("6188.50"))
        self.assertEqual(harbin["gdp_real_growth_pct"], Decimal("4.60"))
        self.assertEqual(harbin["resident_population_10k"], Decimal("988.70"))
        self.assertEqual(harbin["general_public_revenue_100m"], Decimal("368.30"))
        self.assertEqual(harbin["general_public_expenditure_100m"], Decimal("1245.20"))

        hefei = values[("CN-340100", "2025")]
        self.assertEqual(hefei["gdp_current_100m"], Decimal("14210.00"))
        self.assertEqual(hefei["gdp_real_growth_pct"], Decimal("6.10"))
        self.assertEqual(hefei["general_public_revenue_100m"], Decimal("977.35"))
        self.assertEqual(hefei["general_public_expenditure_100m"], Decimal("1558.59"))

        source_ids = {source["source_doc_id"] for source in sources}
        self.assertIn("SRC-B2-TIBET-CITY-STATISTICAL-CHANGDU-2025", source_ids)
        self.assertIn("SRC-B2-HEILONGJIANG-CITY-STATISTICAL-HARBIN-2025", source_ids)
        self.assertIn("SRC-B2-ANHUI-CITY-STATISTICAL-HEFEI-2025", source_ids)

    def test_evidence_based_missing_is_explicitly_registered_for_unpublished_debt(self):
        city = {
            "city_id": "CN-460300",
            "city_name_cn": "三沙市",
            "province_name": "海南省",
            "metric_year": "2025",
        }
        macro = {
            "city_id": "CN-460300",
            "metric_year": "2025",
            "data_status": "not_collected",
            "source_grade": "",
            "source_doc_id": "",
            "general_debt_balance_100m": None,
            "statutory_debt_balance_100m": None,
        }
        debt_status = next(item for item in build_collection_status([city], [macro]) if item["module"] == "法定债务")
        self.assertEqual(debt_status["collection_status"], "evidence_based_missing")
        self.assertEqual(debt_status["error_code"], "PUBLIC_SOURCE_EXHAUSTED")
        macro_status = next(item for item in build_collection_status([city], [macro]) if item["module"] == "经济财政")
        self.assertEqual(macro_status["collection_status"], "evidence_based_missing")
        self.assertEqual(macro_status["error_code"], "PUBLIC_SOURCE_EXHAUSTED")
        self.assertGreaterEqual(macro_status["evidence_count"], 3)

        macro_rows_by_key = {}
        for evidence in EVIDENCE_BY_KEY.values():
            key = (evidence["city_id"], str(evidence["metric_year"]))
            macro_rows_by_key.setdefault(
                key,
                {"city_id": key[0], "metric_year": key[1]},
            )[evidence["field_name"]] = None
        evidence_rows = build_evidence_based_missing_rows(list(macro_rows_by_key.values()))
        # 阿里地区 2020 年 GDP 实际增速已由官方 A1 来源补录，不再登记为缺失。
        self.assertEqual(len(evidence_rows), 55)

        macro_rows_by_key[("CN-460300", "2022")]["gdp_current_100m"] = "6.66"
        filtered_rows = build_evidence_based_missing_rows(list(macro_rows_by_key.values()))
        self.assertEqual(len(filtered_rows), 54)

    def test_new_fund_calculations_are_appended_after_existing_lineages(self):
        rows = [
            {"target_record_id": "old", "target_field": "statutory_debt_to_gdp_pct", "calculation_id": "old-1"},
            {"target_record_id": "old", "target_field": "fund_revenue_dependence_pct", "calculation_id": "old-fund"},
            {"target_record_id": "new", "target_field": "fund_revenue_dependence_pct", "calculation_id": "new-1"},
            {"target_record_id": "old", "target_field": "fiscal_self_sufficiency_pct", "calculation_id": "old-2"},
            {"target_record_id": "new", "target_field": "gov_fund_to_general_revenue_pct", "calculation_id": "new-2"},
        ]

        ordered = order_calculation_rows_for_lineage(rows, {"new"})

        self.assertEqual(
            [row["calculation_id"] for row in ordered],
            ["old-1", "old-fund", "old-2", "new-1", "new-2"],
        )

    def test_city_master_has_stable_annual_keys_and_explicit_special_samples(self):
        rows = build_city_master(
            {
                2024: [
                    ("110100000000", "市辖区", "2", "110000000000", "0"),
                    ("440100000000", "广州市", "2", "440000000000", "0"),
                    ("532900000000", "大理白族自治州", "2", "530000000000", "0"),
                ]
            },
            years=range(2024, 2025),
        )

        self.assertEqual({row["city_id"] for row in rows}, {"CN-110000", "CN-440100", "CN-532900"})
        self.assertTrue(all(row["metric_year"] == "2024" for row in rows))
        self.assertEqual(next(row for row in rows if row["city_id"] == "CN-110000")["sample_tier"], "separate")
        self.assertEqual(next(row for row in rows if row["city_id"] == "CN-532900")["sample_tier"], "extended")
        validate_city_master(rows)


    def test_derived_values_use_decimal_and_leave_missing_as_none(self):
        result = compute_derived_values(
            {
                "statutory_debt_balance_100m": "100.00",
                "statutory_debt_limit_100m": "125.00",
                "gdp_current_100m": "1000.00",
                "general_public_revenue_100m": "200.00",
                "general_public_expenditure_100m": "250.00",
                "gov_fund_revenue_100m": None,
            }
        )

        self.assertEqual(result["debt_limit_utilization_pct"], Decimal("80.00"))
        self.assertEqual(result["statutory_debt_to_gdp_pct"], Decimal("10.00"))
        self.assertEqual(result["fiscal_self_sufficiency_pct"], Decimal("80.00"))
        self.assertIsNone(result["gov_fund_to_general_revenue_pct"])


    def test_direct_statutory_total_is_not_overwritten_by_rounded_components(self):
        result = compute_derived_values(
            {
                "general_debt_balance_100m": "170.51",
                "special_debt_balance_100m": "330.98",
                "statutory_debt_balance_100m": "501.50",
                "general_debt_limit_100m": "185.83",
                "special_debt_limit_100m": "335.71",
                "statutory_debt_limit_100m": "521.54",
            }
        )

        self.assertEqual(result["statutory_debt_balance_100m"], Decimal("501.50"))
        self.assertEqual(result["statutory_debt_limit_100m"], Decimal("521.54"))


    def test_ingested_official_total_is_preferred_when_stored_as_direct_evidence(self):
        result = compute_derived_values(
            {
                "general_debt_balance_100m": "170.51",
                "special_debt_balance_100m": "330.98",
                "_official_direct_statutory_balance": "501.4969125523",
                "general_debt_limit_100m": "185.83",
                "special_debt_limit_100m": "335.71",
                "_official_direct_statutory_limit": "521.542476",
            }
        )

        self.assertEqual(result["statutory_debt_balance_100m"], Decimal("501.50"))
        self.assertEqual(result["statutory_debt_limit_100m"], Decimal("521.54"))


    def test_implausible_direct_total_falls_back_to_component_sum(self):
        result = compute_derived_values(
            {
                "general_debt_balance_100m": "8895.34",
                "special_debt_balance_100m": "2157.58",
                "_official_direct_statutory_balance": "7227.39",
                "general_debt_limit_100m": "9467.59",
                "special_debt_limit_100m": "2240.20",
                "_official_direct_statutory_limit": "0.20",
            }
        )

        self.assertEqual(result["statutory_debt_balance_100m"], Decimal("11052.92"))
        self.assertEqual(result["statutory_debt_limit_100m"], Decimal("11707.79"))


    def test_missing_numeric_fields_are_not_serialized_as_zero(self):
        rows = [{"gdp_current_100m": 0, "general_public_revenue_100m": None, "missing_reason": "not found"}]
        with self.assertRaises(AssertionError):
            validate_no_zero_for_missing(rows)

        validate_no_zero_for_missing(
            [{"gdp_current_100m": None, "general_public_revenue_100m": None}]
        )


    def test_secondary_debt_is_not_marked_as_officially_extracted(self):
        city = {
            "city_id": "CN-540200",
            "admin_code_6": "540200",
            "city_name_cn": "日喀则市",
            "province_code": "54",
            "province_name": "西藏自治区",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2024",
        }
        facts = {
            ("CN-540200", "2024"): {
                "source_doc_id": "SRC-SECONDARY-DEBT-TIBET-2024-TOTALS",
                "source_grade": "B2",
                "statutory_debt_balance_100m": "117.35",
                "table_name": "2024年末各地地方政府债务余额",
                "line_number": 3,
                "evidence_excerpt": "日喀则市 117.35",
            }
        }
        rows, _ = build_macro_rows([city], [], {}, facts)
        self.assertEqual(rows[0]["data_status"], "secondary_debt")
        self.assertEqual(rows[0]["collection_status"], "needs_review")
        self.assertEqual(build_debt_rows(rows)[0]["collection_status"], "needs_review")

    def test_debt_fact_with_balance_above_limit_is_blocked(self):
        city = {
            "city_id": "CN-150800",
            "admin_code_6": "150800",
            "city_name_cn": "巴彦淖尔市",
            "province_code": "15",
            "province_name": "内蒙古自治区",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2018",
        }
        facts = {
            ("CN-150800", "2018"): {
                "source_doc_id": "SRC-OFFICIAL-DEBT-INNER-MONGOLIA-BAYANNUR-2018",
                "source_grade": "A2",
                "general_debt_limit_100m": "247.82",
                "general_debt_balance_100m": "257.53",
                "special_debt_limit_100m": "42.75",
                "special_debt_balance_100m": "47.98",
                "statutory_debt_limit_100m": "290.57",
                "statutory_debt_balance_100m": "305.52",
            }
        }

        rows, _ = build_macro_rows([city], [], {}, facts)

        self.assertIsNone(rows[0]["statutory_debt_limit_100m"])
        self.assertIsNone(rows[0]["statutory_debt_balance_100m"])
        self.assertEqual(rows[0]["collection_status"], "needs_review")
        self.assertIn("余额超过限额", rows[0]["note"])

    def test_guangdong_2025_official_gdp_batch_is_field_level_lineaged(self):
        city = {
            "city_id": "CN-440100",
            "admin_code_6": "440100",
            "city_name_cn": "广州市",
            "province_code": "44",
            "province_name": "广东省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        gd_2025_gdp = {
            "CN-440100": {
                "gdp_current_100m": "32039.46",
                "gdp_real_growth_pct": "4.0",
            }
        }

        rows, lineage = build_macro_rows([city], [], {}, {}, gd_2025_gdp)

        self.assertEqual(rows[0]["gdp_current_100m"], Decimal("32039.46"))
        self.assertEqual(rows[0]["gdp_real_growth_pct"], Decimal("4.00"))
        self.assertEqual(rows[0]["data_status"], "preliminary")
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {"gdp_current_100m", "gdp_real_growth_pct"},
        )
        self.assertTrue(all(item["source_doc_id"] == "SRC-GD-CITY-GDP-2025" for item in lineage))

    def test_guangdong_2025_official_fiscal_batch_is_execution_and_lineaged(self):
        city = {
            "city_id": "CN-440100",
            "admin_code_6": "440100",
            "city_name_cn": "广州市",
            "province_code": "44",
            "province_name": "广东省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        gd_2025_gdp = {
            "CN-440100": {
                "gdp_current_100m": "32039.46",
                "gdp_real_growth_pct": "4.0",
            }
        }
        gd_2025_fiscal = {
            "CN-440100": {
                "general_public_revenue_100m": "2184.8219",
                "general_public_expenditure_100m": "2801.5394",
                "general_public_revenue_100m_raw_10k": "21848219",
                "general_public_expenditure_100m_raw_10k": "28015394",
            }
        }
        gd_2025_fund = {
            "CN-440100": {
                "gov_fund_revenue_100m": "1000.00",
                "gov_fund_revenue_raw_100m": "1000.00",
                "source_doc_id": "SRC-GZ-CITY-FUND-2025",
                "source_locator": "官方预算报告正文：2025年全市政府性基金预算收入；城市=广州市",
            }
        }

        rows, lineage = build_macro_rows([city], [], {}, {}, gd_2025_gdp, gd_2025_fiscal, gd_2025_fund)

        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("2184.82"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("2801.54"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("1000.00"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("31.40"))
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertIn("SRC-GD-CITY-FISCAL-2025", rows[0]["source_doc_id"])
        self.assertIn("SRC-GZ-CITY-FUND-2025", rows[0]["source_doc_id"])
        fiscal_fields = {
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        }
        self.assertEqual(
            {item["target_field"] for item in lineage if item["source_doc_id"] == "SRC-GD-CITY-FISCAL-2025"},
            fiscal_fields,
        )

    def test_ningxia_2025_city_fiscal_batch_uses_whole_city_values_and_units(self):
        values, sources = load_ningxia_2025_city_fiscal()

        self.assertEqual(len(values), 4)
        self.assertEqual(values["CN-640100"]["general_public_revenue_100m"], Decimal("171.59"))
        self.assertEqual(values["CN-640100"]["general_public_expenditure_100m"], Decimal("406.04"))
        self.assertEqual(values["CN-640100"]["gov_fund_revenue_100m"], Decimal("45.26"))
        self.assertEqual(values["CN-640300"]["general_public_revenue_100m"], Decimal("47.49"))
        self.assertEqual(values["CN-640300"]["gov_fund_revenue_100m"], Decimal("20.71"))
        self.assertEqual(values["CN-640300"]["general_public_revenue_100m_raw_unit"], "万元")
        self.assertEqual(len(sources), 4)

        city = {
            "city_id": "CN-640100",
            "admin_code_6": "640100",
            "city_name_cn": "银川市",
            "province_code": "64",
            "province_name": "宁夏回族自治区",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, {}, {}, {}, values,
        )

        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("171.59"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("406.04"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("45.26"))
        self.assertEqual(rows[0]["fiscal_self_sufficiency_pct"], Decimal("42.26"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("20.87"))
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {"general_public_revenue_100m", "general_public_expenditure_100m", "gov_fund_revenue_100m"},
        )
    def test_shandong_2025_city_fiscal_batch_uses_official_whole_city_values(self):
        values, sources = load_shandong_2025_city_fiscal()

        self.assertEqual(values["CN-370100"]["general_public_revenue_100m"], Decimal("1093.35"))
        self.assertEqual(values["CN-370100"]["general_public_expenditure_100m"], Decimal("1407.49"))
        self.assertEqual(values["CN-370100"]["gov_fund_revenue_100m"], Decimal("567.26"))
        self.assertEqual(values["CN-370200"]["general_public_revenue_100m"], Decimal("1340.72"))
        self.assertEqual(values["CN-370200"]["general_public_expenditure_100m"], Decimal("1718.52"))
        self.assertEqual(values["CN-370200"]["gov_fund_revenue_100m"], Decimal("324.65"))
        self.assertEqual(len(sources), 2)
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})

        city = {
            "city_id": "CN-370200",
            "admin_code_6": "370200",
            "city_name_cn": "青岛市",
            "province_code": "37",
            "province_name": "山东省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, shandong_2025_fiscal=values,
        )

        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("1340.72"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("1718.52"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("324.65"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("19.49"))
        self.assertEqual({item["target_field"] for item in lineage}, {
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
            "gov_fund_revenue_100m",
        })

    def test_2024_sichuan_and_lijiang_batch_extracts_remaining_core_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            ("CN-530700", "2024"): {
                "general_public_expenditure_100m": Decimal("181.01"),
            },
            ("CN-511700", "2024"): {
                "general_public_expenditure_100m": Decimal("598.20"),
            },
            ("CN-513300", "2024"): {
                "gdp_current_100m": Decimal("580.52"),
                "gdp_real_growth_pct": Decimal("5.40"),
                "general_public_revenue_100m": Decimal("60.50"),
                "general_public_expenditure_100m": Decimal("454.50"),
            },
            ("CN-513400", "2024"): {
                "gdp_current_100m": Decimal("2474.90"),
                "gdp_real_growth_pct": Decimal("6.00"),
                "general_public_revenue_100m": Decimal("220.30"),
                "general_public_expenditure_100m": Decimal("848.50"),
            },
            ("CN-510300", "2024"): {
                "gdp_current_100m": Decimal("1876.24"),
                "gdp_real_growth_pct": Decimal("7.10"),
                "general_public_revenue_100m": Decimal("85.30"),
                "general_public_expenditure_100m": Decimal("304.27"),
            },
        }
        for key, fields in expected.items():
            self.assertIn(key, values)
            for field, expected_value in fields.items():
                self.assertEqual(values[key][field], expected_value)

        source_ids = {source["source_doc_id"] for source in sources}
        self.assertTrue({
            "SRC-A2-LIJIANG-CITY-FISCAL-EXPENDITURE-2024",
            "SRC-A2-DAZHOU-CITY-FISCAL-EXPENDITURE-2024",
            "SRC-B2-GANZI-CITY-MACRO-FISCAL-2024",
            "SRC-B2-LIANGSHAN-CITY-MACRO-FISCAL-2024",
            "SRC-B2-ZIGONG-CITY-MACRO-2024",
            "SRC-B2-ZIGONG-CITY-FISCAL-2024",
        }.issubset(source_ids))

    def test_2024_heihe_and_2025_ali_heze_batch_extracts_remaining_core_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            ("CN-231100", "2024"): {
                "gdp_current_100m": Decimal("711.40"),
                "gdp_real_growth_pct": Decimal("3.30"),
                "general_public_revenue_100m": Decimal("56.20"),
                "general_public_expenditure_100m": Decimal("323.50"),
            },
            ("CN-542500", "2025"): {
                "gdp_current_100m": Decimal("114.21"),
                "gdp_real_growth_pct": Decimal("6.60"),
                "general_public_revenue_100m": Decimal("3.71"),
                "general_public_expenditure_100m": Decimal("174.61"),
            },
            ("CN-371700", "2025"): {
                "gdp_current_100m": Decimal("4937.40"),
                "gdp_real_growth_pct": Decimal("5.00"),
                "general_public_revenue_100m": Decimal("333.37"),
            },
        }
        for key, fields in expected.items():
            self.assertIn(key, values)
            for field, expected_value in fields.items():
                self.assertEqual(values[key][field], expected_value)

        ali_2025 = values[("CN-542500", "2025")]
        self.assertIn(
            "地方财政收入=37094万元",
            ali_2025["general_public_revenue_100m_evidence_excerpt"],
        )
        ali_source = next(
            source
            for source in sources
            if source["source_doc_id"] == "SRC-A2-ALI-REGION-MACRO-FISCAL-2025"
        )
        self.assertIn("地方财政收入", ali_source["note"])
        self.assertIn("规范映射", ali_source["note"])
        self.assertEqual(
            ali_2025["_field_sources"]["general_public_revenue_100m"]["source_grade"],
            "A2",
        )
        source_ids = {source["source_doc_id"] for source in sources}
        self.assertIn("SRC-A2-HEIHE-CITY-MACRO-FISCAL-2024", source_ids)
        self.assertIn("SRC-A2-ALI-REGION-MACRO-FISCAL-2025", source_ids)
        self.assertIn("SRC-B2-HEZE-CITY-MACRO-FISCAL-2025", source_ids)

    def test_2024_2025_official_macro_followup_batch_extracts_ten_core_values(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            ("CN-533400", "2024"): {
                "gdp_current_100m": Decimal("307.01"),
                "gdp_real_growth_pct": Decimal("0.40"),
            },
            ("CN-653200", "2024"): {
                "gdp_current_100m": Decimal("598.36"),
            },
            ("CN-131000", "2025"): {
                "gdp_current_100m": Decimal("4040.50"),
                "gdp_real_growth_pct": Decimal("5.80"),
            },
            ("CN-140300", "2024"): {
                "gdp_real_growth_pct": Decimal("-0.90"),
            },
            ("CN-460100", "2024"): {
                "gdp_real_growth_pct": Decimal("4.00"),
            },
            ("CN-654000", "2024"): {
                "gdp_real_growth_pct": Decimal("6.00"),
            },
            ("CN-230100", "2024"): {
                "gdp_real_growth_pct": Decimal("4.30"),
            },
            ("CN-230400", "2024"): {
                "gdp_real_growth_pct": Decimal("-2.90"),
            },
        }
        for key, fields in expected.items():
            self.assertIn(key, values)
            for field, expected_value in fields.items():
                self.assertEqual(values[key][field], expected_value)

        source_ids = {source["source_doc_id"] for source in sources}
        self.assertTrue({
            "SRC-A2-DIQING-CITY-MACRO-FISCAL-2024",
            "SRC-B2-HOTAN-REGION-GDP-2024",
            "SRC-A2-LANGFANG-CITY-MACRO-2025",
            "SRC-A2-YANGQUAN-CITY-GROWTH-2024",
            "SRC-B2-HAIKOU-CITY-GROWTH-2024",
            "SRC-A2-YILI-REGION-GROWTH-2024",
            "SRC-A2-HARBIN-CITY-GROWTH-2024",
            "SRC-A2-HEGANG-CITY-GROWTH-2024",
        }.issubset(source_ids))

    def test_2023_2025_macro_gap_batch_extracts_reviewed_values(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            ("CN-370800", "2024"): {
                "gdp_real_growth_pct": Decimal("5.80"),
                "general_public_revenue_100m": Decimal("496.30"),
                "general_public_expenditure_100m": Decimal("800.20"),
            },
            ("CN-411100", "2024"): {
                "general_public_revenue_100m": Decimal("139.00"),
                "general_public_expenditure_100m": Decimal("269.70"),
            },
            ("CN-371600", "2024"): {
                "gdp_current_100m": Decimal("3404.74"),
                "gdp_real_growth_pct": Decimal("6.20"),
                "general_public_revenue_100m": Decimal("306.92"),
                "general_public_expenditure_100m": Decimal("570.22"),
            },
            ("CN-371500", "2024"): {
                "gdp_real_growth_pct": Decimal("5.70"),
                "general_public_revenue_100m": Decimal("257.10"),
            },
            ("CN-510100", "2024"): {
                "gdp_real_growth_pct": Decimal("5.70"),
            },
            ("CN-512000", "2024"): {
                "gdp_real_growth_pct": Decimal("6.50"),
            },
            ("CN-653100", "2023"): {
                "gdp_current_100m": Decimal("1508.35"),
                "gdp_real_growth_pct": Decimal("6.40"),
                "general_public_revenue_100m": Decimal("86.43"),
                "general_public_expenditure_100m": Decimal("773.41"),
            },
            ("CN-652300", "2023"): {
                "general_public_revenue_100m": Decimal("227.35"),
                "general_public_expenditure_100m": Decimal("385.49"),
            },
            ("CN-433100", "2023"): {
                "gdp_current_100m": Decimal("825.85"),
                "gdp_real_growth_pct": Decimal("2.60"),
                "general_public_revenue_100m": Decimal("79.90"),
                "general_public_expenditure_100m": Decimal("369.79"),
            },
            ("CN-360200", "2024"): {
                "general_public_expenditure_100m": Decimal("250.00"),
            },
            ("CN-420700", "2024"): {
                "general_public_expenditure_100m": Decimal("171.24"),
            },
            ("CN-421100", "2025"): {
                "general_public_revenue_100m": Decimal("205.60"),
            },
        }
        for key, fields in expected.items():
            self.assertIn(key, values)
            for field, expected_value in fields.items():
                self.assertEqual(values[key][field], expected_value)

        source_ids = {source["source_doc_id"] for source in sources}
        self.assertTrue({
            "SRC-B2-JINING-CITY-MACRO-FISCAL-2024",
            "SRC-B2-BINZHOU-CITY-MACRO-FISCAL-2024",
            "SRC-A2-KASHI-REGION-MACRO-FISCAL-2023-REVIEWED",
            "SRC-B2-XIANGXI-PREFECTURE-MACRO-FISCAL-2023",
            "SRC-A2-EZHOU-CITY-EXPENDITURE-2024",
        }.issubset(source_ids))

    def test_next_2025_city_fiscal_batch_extracts_four_official_city_sources(self):
        values, sources = load_next_2025_city_fiscal()

        expected = {
            "CN-320400": ("715.50", "832.80", "413.70"),
            "CN-410300": ("421.80", "723.30", "225.70"),
            "CN-430600": ("207.00", "664.20", "224.10"),
            "CN-430400": ("185.22", "701.16", "208.71"),
        }
        self.assertEqual(len(values), 4)
        for city_id, (revenue, expenditure, fund_revenue) in expected.items():
            self.assertEqual(values[city_id]["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(values[city_id]["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(values[city_id]["gov_fund_revenue_100m"], Decimal(fund_revenue))
        self.assertEqual(len(sources), 4)
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})

        city = {
            "city_id": "CN-410300",
            "admin_code_6": "410300",
            "city_name_cn": "洛阳市",
            "province_code": "41",
            "province_name": "河南省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, _ = build_macro_rows(
            [city], [], {}, {}, next_2025_fiscal=values,
        )
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("421.80"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("723.30"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("225.70"))

    def test_followup_2025_city_fiscal_batch_extracts_four_official_city_sources(self):
        values, sources = load_followup_2025_city_fiscal()

        expected = {
            "CN-320200": ("1225.39", "1274.85", "650.93"),
            "CN-430700": ("192.68", "602.56", "100.29"),
            "CN-430900": ("113.60", "432.00", "45.10"),
            "CN-320500": ("2490.20", "2545.80", None),
        }
        self.assertEqual(len(values), 4)
        for city_id, (revenue, expenditure, fund_revenue) in expected.items():
            self.assertEqual(values[city_id]["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(values[city_id]["general_public_expenditure_100m"], Decimal(expenditure))
            if fund_revenue is not None:
                self.assertEqual(values[city_id]["gov_fund_revenue_100m"], Decimal(fund_revenue))
            else:
                self.assertNotIn("gov_fund_revenue_100m", values[city_id])
        self.assertEqual(len(sources), 4)
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})

        city = {
            "city_id": "CN-320200",
            "admin_code_6": "320200",
            "city_name_cn": "无锡市",
            "province_code": "32",
            "province_name": "江苏省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, _ = build_macro_rows(
            [city], [], {}, {}, followup_2025_fiscal=values,
        )
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("1225.39"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("1274.85"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("650.93"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("34.69"))

    def test_next2_2025_city_fiscal_batch_preserves_b2_grade_and_extracts_four_cities(self):
        values, sources = load_next2_2025_city_fiscal()

        expected = {
            "CN-320300": ("575.33", "1053.50", "357.19"),
            "CN-321000": ("376.33", "717.88", "536.95"),
            "CN-321100": ("339.03", "568.23", None),
            "CN-321200": ("475.49", "686.40", "388.35"),
        }
        self.assertEqual(len(values), 4)
        for city_id, (revenue, expenditure, fund_revenue) in expected.items():
            self.assertEqual(values[city_id]["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(values[city_id]["general_public_expenditure_100m"], Decimal(expenditure))
            if fund_revenue is None:
                self.assertNotIn("gov_fund_revenue_100m", values[city_id])
            else:
                self.assertEqual(values[city_id]["gov_fund_revenue_100m"], Decimal(fund_revenue))
            self.assertEqual(values[city_id]["source_grade"], "B2")
        self.assertEqual(len(sources), 4)
        self.assertEqual({source["source_grade"] for source in sources}, {"B2"})

        city = {
            "city_id": "CN-321000",
            "admin_code_6": "321000",
            "city_name_cn": "扬州市",
            "province_code": "32",
            "province_name": "江苏省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, next2_2025_fiscal=values,
        )
        self.assertEqual(rows[0]["source_grade"], "B2")
        self.assertEqual(rows[0]["collection_status"], "needs_review")
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("376.33"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("717.88"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("536.95"))
        self.assertTrue(all("B2" in item["selection_reason"] for item in lineage))

    def test_next3_2025_city_fiscal_batch_extracts_official_and_b2_sources(self):
        values, sources = load_next3_2025_city_fiscal()

        expected = {
            "CN-350100": ("750.55", "1037.15", "502.60", "A2"),
            "CN-350500": ("592.07", "880.29", "292.07", "A2"),
            "CN-430100": ("1296.87", "1625.77", None, "A2"),
            "CN-210100": ("794.20", "1031.90", None, "B2"),
        }
        self.assertEqual(len(values), 4)
        for city_id, (revenue, expenditure, fund_revenue, grade) in expected.items():
            self.assertEqual(values[city_id]["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(values[city_id]["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(values[city_id]["source_grade"], grade)
            if fund_revenue is None:
                self.assertNotIn("gov_fund_revenue_100m", values[city_id])
            else:
                self.assertEqual(values[city_id]["gov_fund_revenue_100m"], Decimal(fund_revenue))
        self.assertEqual(len(sources), 4)
        self.assertEqual(
            {source["source_grade"] for source in sources},
            {"A2", "B2"},
        )

        city = {
            "city_id": "CN-350100",
            "admin_code_6": "350100",
            "city_name_cn": "福州市",
            "province_code": "35",
            "province_name": "福建省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, next3_2025_fiscal=values,
        )
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["collection_status"], "extracted")
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("750.55"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("1037.15"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("502.60"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("40.11"))
        self.assertTrue(all("B2" not in item["selection_reason"] for item in lineage))

    def test_next4_2025_city_fiscal_batch_extracts_five_city_sources(self):
        values, sources = load_next4_2025_city_fiscal()

        expected = {
            "CN-420100": ("1743.06", "2520.61", "1453.81", "A2"),
            "CN-410100": ("1181.30", "1517.10", None, "A2"),
            "CN-510100": ("2000.70", "2680.00", None, "B2"),
            "CN-360100": ("537.77", "914.44", None, "A2"),
            "CN-450100": ("381.69", "822.34", None, "B2"),
        }
        self.assertEqual(len(values), 5)
        for city_id, (revenue, expenditure, fund_revenue, grade) in expected.items():
            self.assertEqual(values[city_id]["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(values[city_id]["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(values[city_id]["source_grade"], grade)
            if fund_revenue is None:
                self.assertNotIn("gov_fund_revenue_100m", values[city_id])
            else:
                self.assertEqual(values[city_id]["gov_fund_revenue_100m"], Decimal(fund_revenue))
        self.assertEqual(len(sources), 5)
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

        city = {
            "city_id": "CN-420100",
            "admin_code_6": "420100",
            "city_name_cn": "武汉市",
            "province_code": "42",
            "province_name": "湖北省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, next4_2025_fiscal=values,
        )
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["collection_status"], "extracted")
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("1743.06"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("2520.61"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("1453.81"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("45.48"))
        self.assertTrue(all("B2" not in item["selection_reason"] for item in lineage))

    def test_next5_2025_city_fiscal_batch_extracts_five_city_sources(self):
        values, sources = load_next5_2025_city_fiscal()

        expected = {
            "CN-610100": ("979.35", "1513.02", None, "A2"),
            "CN-460100": ("253.80", "336.74", None, "B2"),
            "CN-640100": ("209.70", "440.75", None, "A2"),
            "CN-650100": ("409.23", "569.06", "145.24", "A2"),
            "CN-530100": ("575.00", "843.47", None, "B2"),
        }
        self.assertEqual(len(values), 5)
        for city_id, (revenue, expenditure, fund_revenue, grade) in expected.items():
            self.assertEqual(values[city_id]["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(values[city_id]["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(values[city_id]["source_grade"], grade)
            if fund_revenue is None:
                self.assertNotIn("gov_fund_revenue_100m", values[city_id])
            else:
                self.assertEqual(values[city_id]["gov_fund_revenue_100m"], Decimal(fund_revenue))
        self.assertEqual(len(sources), 5)
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

        city = {
            "city_id": "CN-650100",
            "admin_code_6": "650100",
            "city_name_cn": "乌鲁木齐市",
            "province_code": "65",
            "province_name": "新疆维吾尔自治区",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, next5_2025_fiscal=values,
        )
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["collection_status"], "extracted")
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("409.23"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("569.06"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("145.24"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("26.19"))
        self.assertTrue(all("B2" not in item["selection_reason"] for item in lineage))

    def test_next6_2025_city_fiscal_batch_extracts_five_city_sources(self):
        values, sources = load_next6_2025_city_fiscal()

        expected = {
            "CN-130100": ("758.80", "1320.70", "A2"),
            "CN-140100": ("443.07", "709.86", "B2"),
            "CN-230800": ("83.50", "408.20", "B2"),
            "CN-540300": ("33.64", "342.32", "B2"),
            "CN-230100": ("368.30", "1245.20", "B2"),
        }
        self.assertEqual(len(values), 5)
        for city_id, (revenue, expenditure, grade) in expected.items():
            self.assertEqual(values[city_id]["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(values[city_id]["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(values[city_id]["source_grade"], grade)
        self.assertEqual(len(sources), 5)
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

        city = {
            "city_id": "CN-130100",
            "admin_code_6": "130100",
            "city_name_cn": "石家庄市",
            "province_code": "13",
            "province_name": "河北省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, next6_2025_fiscal=values,
        )
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["collection_status"], "extracted")
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("758.80"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("1320.70"))
        self.assertEqual(rows[0]["fiscal_self_sufficiency_pct"], Decimal("57.45"))
        self.assertTrue(all("B2" not in item["selection_reason"] for item in lineage))

    def test_next7_2025_city_fiscal_batch_extracts_five_city_sources(self):
        values, sources = load_next7_2025_city_fiscal()

        expected = {
            "CN-340100": ("977.35", "1558.59", "B2"),
            "CN-420500": ("327.05", "694.98", "B2"),
            "CN-421000": ("190.99", "582.99", "A2"),
            "CN-420200": ("213.50", "352.00", "A2"),
            "CN-210800": ("146.00", "253.60", "A2"),
        }
        self.assertEqual(len(values), 5)
        for city_id, (revenue, expenditure, grade) in expected.items():
            self.assertEqual(values[city_id]["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(values[city_id]["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(values[city_id]["source_grade"], grade)
        self.assertEqual(len(sources), 5)
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

        city = {
            "city_id": "CN-210800",
            "admin_code_6": "210800",
            "city_name_cn": "营口市",
            "province_code": "21",
            "province_name": "辽宁省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, next7_2025_fiscal=values,
        )
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["collection_status"], "extracted")
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("146.00"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("253.60"))
        self.assertEqual(rows[0]["fiscal_self_sufficiency_pct"], Decimal("57.57"))
        self.assertTrue(all("B2" not in item["selection_reason"] for item in lineage))

    def test_existing_2025_bulletin_batches_extract_economic_fields(self):
        cases = [
            (load_followup_2025_city_fiscal, "CN-320500", "27695.10", "5.40", "1304.77"),
            (load_next3_2025_city_fiscal, "CN-350500", "13778.34", "5.30", None),
            (load_next3_2025_city_fiscal, "CN-430100", "15737.82", "4.00", None),
            (load_next4_2025_city_fiscal, "CN-410100", "15244.60", "5.40", "1313.80"),
            (load_next4_2025_city_fiscal, "CN-360100", "8141.69", "4.70", None),
            (load_next5_2025_city_fiscal, "CN-640100", "3033.52", "5.30", "294.26"),
            (load_next5_2025_city_fiscal, "CN-650100", "4658.19", "4.50", "415.39"),
            (load_next6_2025_city_fiscal, "CN-130100", "8651.70", "6.00", "1124.69"),
            (load_next5_2025_city_fiscal, "CN-530100", "8637.45", "4.20", "874.40"),
            (load_next5_2025_city_fiscal, "CN-610100", "13902.67", "4.70", "1323.63"),
            (load_next6_2025_city_fiscal, "CN-140100", "5382.45", "1.30", None),
            (load_next6_2025_city_fiscal, "CN-230800", "1052.30", "4.70", None),
            (load_next6_2025_city_fiscal, "CN-230100", "6188.50", "4.60", "988.70"),
            (load_next6_2025_city_fiscal, "CN-540300", "424.86", "6.70", "77.20"),
            (load_next7_2025_city_fiscal, "CN-421000", "3712.34", "6.30", "508.29"),
        ]
        for loader, city_id, gdp, growth, population in cases:
            values, _ = loader()
            self.assertEqual(values[city_id]["gdp_current_100m"], Decimal(gdp))
            self.assertEqual(values[city_id]["gdp_real_growth_pct"], Decimal(growth))
            if population is None:
                self.assertNotIn("resident_population_10k", values[city_id])
            else:
                self.assertEqual(values[city_id]["resident_population_10k"], Decimal(population))

    def test_next8_2025_city_economic_batch_extracts_wuhai_statistics(self):
        values, sources = load_next8_2025_city_economic()

        self.assertEqual(len(values), 2)
        self.assertEqual(values["CN-150300"]["gdp_current_100m"], Decimal("540.75"))
        self.assertEqual(values["CN-150300"]["gdp_real_growth_pct"], Decimal("-1.40"))
        self.assertEqual(values["CN-150300"]["general_public_revenue_100m"], Decimal("86.06"))
        self.assertEqual(values["CN-150300"]["general_public_expenditure_100m"], Decimal("132.40"))
        self.assertEqual(values["CN-150300"]["source_grade"], "B2")
        self.assertEqual(values["CN-610300"]["gdp_current_100m"], Decimal("2648.87"))
        self.assertEqual(values["CN-610300"]["gdp_real_growth_pct"], Decimal("6.00"))
        self.assertEqual(values["CN-610300"]["resident_population_10k"], Decimal("321.56"))
        self.assertEqual(values["CN-610300"]["source_grade"], "A2")
        self.assertEqual(values["CN-610300"]["data_status"], "preliminary")
        self.assertEqual(len(sources), 2)
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

        city = {
            "city_id": "CN-150300",
            "admin_code_6": "150300",
            "city_name_cn": "乌海市",
            "province_code": "15",
            "province_name": "内蒙古自治区",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, next8_2025_economic=values,
        )
        self.assertEqual(rows[0]["source_grade"], "B2")
        self.assertEqual(rows[0]["collection_status"], "needs_review")
        self.assertEqual(rows[0]["gdp_current_100m"], Decimal("540.75"))
        self.assertEqual(rows[0]["gdp_real_growth_pct"], Decimal("-1.40"))
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("86.06"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("132.40"))
        self.assertTrue(all(item["source_doc_id"] == "SRC-B2-INNER-MONGOLIA-CITY-STATISTICAL-WUHAI-2025" for item in lineage))

        baoji_city = {
            "city_id": "CN-610300",
            "admin_code_6": "610300",
            "city_name_cn": "宝鸡市",
            "province_code": "61",
            "province_name": "陕西省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        baoji_rows, baoji_lineage = build_macro_rows(
            [baoji_city], [], {}, {}, next8_2025_economic=values,
        )
        self.assertEqual(baoji_rows[0]["source_grade"], "A2")
        self.assertEqual(baoji_rows[0]["data_status"], "preliminary")
        self.assertEqual(baoji_rows[0]["collection_status"], "extracted")
        self.assertEqual(baoji_rows[0]["gdp_current_100m"], Decimal("2648.87"))
        self.assertEqual(baoji_rows[0]["gdp_real_growth_pct"], Decimal("6.00"))
        self.assertEqual(baoji_rows[0]["resident_population_10k"], Decimal("321.56"))
        self.assertTrue(all(item["source_doc_id"] == "SRC-A2-BAOJI-CITY-ECONOMIC-2025" for item in baoji_lineage))

    def test_jiangsu_city_fund_batch_extracts_2018_to_2024_whole_city_tables(self):
        values, sources = load_jiangsu_city_fund_sources()

        self.assertEqual(len(values), 78)
        self.assertEqual(len(sources), 6)
        self.assertEqual(values[("CN-320100", "2018")]["gov_fund_revenue_100m"], Decimal("1614.62"))
        self.assertEqual(values[("CN-321300", "2018")]["gov_fund_revenue_100m"], Decimal("132.75"))
        self.assertEqual(values[("CN-320100", "2020")]["gov_fund_revenue_100m"], Decimal("2208.40"))
        self.assertEqual(values[("CN-321300", "2020")]["gov_fund_revenue_100m"], Decimal("302.86"))
        self.assertEqual(values[("CN-320100", "2021")]["gov_fund_revenue_100m"], Decimal("2493.14"))
        self.assertEqual(values[("CN-321300", "2021")]["gov_fund_revenue_100m"], Decimal("390.18"))
        self.assertEqual(values[("CN-320100", "2022")]["gov_fund_revenue_100m"], Decimal("1560.29"))
        self.assertEqual(values[("CN-321300", "2022")]["gov_fund_revenue_100m"], Decimal("355.39"))
        self.assertEqual(values[("CN-320100", "2023")]["gov_fund_revenue_100m"], Decimal("1254.30"))
        self.assertEqual(values[("CN-321300", "2023")]["gov_fund_revenue_100m"], Decimal("309.20"))
        self.assertEqual(values[("CN-320100", "2024")]["gov_fund_revenue_100m"], Decimal("937.59"))
        self.assertEqual(values[("CN-321300", "2024")]["gov_fund_revenue_100m"], Decimal("217.18"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A1"})

        cities = [
            {
                "city_id": "CN-320100",
                "admin_code_6": "320100",
                "city_name_cn": "南京市",
                "province_code": "32",
                "province_name": "江苏省",
                "prefecture_type": "地级市",
                "sample_tier": "core",
                "metric_year": year,
            }
            for year in ("2018", "2020", "2021", "2022", "2023", "2024")
        ]
        rows, lineage = build_macro_rows(
            cities, [], {}, {}, jiangsu_city_fund=values,
        )
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("1614.62"))
        self.assertEqual(rows[1]["gov_fund_revenue_100m"], Decimal("2208.40"))
        self.assertEqual(rows[2]["gov_fund_revenue_100m"], Decimal("2493.14"))
        self.assertEqual(rows[3]["gov_fund_revenue_100m"], Decimal("1560.29"))
        self.assertEqual(rows[4]["gov_fund_revenue_100m"], Decimal("1254.30"))
        self.assertEqual(rows[5]["gov_fund_revenue_100m"], Decimal("937.59"))
        for row in rows:
            self.assertEqual(row["source_grade"], "A1")
            self.assertEqual(row["data_status"], "official_fiscal")
            self.assertEqual(row["collection_status"], "extracted")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {"gov_fund_revenue_100m"},
        )

    def test_next30_2025_fuzhou_official_bulletin_extracts_four_core_fields(self):
        values, sources = load_next30_2025_city_economic()

        self.assertEqual(len(values), 1)
        self.assertEqual(values["CN-350100"]["gdp_current_100m"], Decimal("15112.32"))
        self.assertEqual(values["CN-350100"]["gdp_real_growth_pct"], Decimal("5.60"))
        self.assertEqual(values["CN-350100"]["resident_population_10k"], Decimal("852.10"))
        self.assertEqual(values["CN-350100"]["general_public_revenue_100m"], Decimal("750.55"))
        self.assertEqual(values["CN-350100"]["general_public_expenditure_100m"], Decimal("1037.15"))
        self.assertEqual(sources[0]["source_grade"], "A2")
        city = {
            "city_id": "CN-350100",
            "admin_code_6": "350100",
            "city_name_cn": "福州市",
            "province_code": "35",
            "province_name": "福建省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, next30_2025_economic=values,
        )
        self.assertEqual(rows[0]["gdp_current_100m"], Decimal("15112.32"))
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("750.55"))
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual({item["target_field"] for item in lineage}, {
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "resident_population_10k",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        })

    def test_jiangsu_city_fiscal_batch_extracts_2024_whole_city_tables(self):
        values, sources = load_jiangsu_city_fiscal_sources()

        self.assertEqual(len(values), 13)
        self.assertEqual(len(sources), 1)
        self.assertEqual(values[("CN-320100", "2024")]["general_public_revenue_100m"], Decimal("1596.02"))
        self.assertEqual(values[("CN-320100", "2024")]["general_public_expenditure_100m"], Decimal("1705.26"))
        self.assertEqual(values[("CN-321300", "2024")]["general_public_revenue_100m"], Decimal("310.00"))
        self.assertEqual(values[("CN-321300", "2024")]["general_public_expenditure_100m"], Decimal("662.82"))

        nanjing = {
            "city_id": "CN-320100",
            "admin_code_6": "320100",
            "city_name_cn": "南京市",
            "province_code": "32",
            "province_name": "江苏省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2024",
        }
        rows, lineage = build_macro_rows(
            [nanjing], [], {}, {}, jiangsu_city_fiscal=values,
        )
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("1596.02"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("1705.26"))
        self.assertEqual(rows[0]["source_grade"], "A1")
        self.assertEqual(rows[0]["collection_status"], "extracted")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {"general_public_revenue_100m", "general_public_expenditure_100m"},
        )

    def test_city_year_fiscal_batch_extracts_chaoyang_2024_fast_report(self):
        values, sources = load_city_year_fiscal_sources()

        record = values[("CN-211300", "2024")]
        self.assertEqual(record["general_public_revenue_100m"], Decimal("87.68"))
        self.assertEqual(record["general_public_expenditure_100m"], Decimal("314.77"))
        self.assertEqual(record["gov_fund_revenue_100m"], Decimal("12.56"))
        self.assertEqual(record["data_status"], "execution")
        self.assertEqual(record["data_status_label"], "2024年快报数")
        self.assertGreaterEqual(len(sources), 316)
        self.assertEqual({source["source_grade"] for source in sources}, {"A1", "A2", "B2"})

    def test_city_year_fiscal_batch_adds_curated_2025_statistical_and_budget_sources(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-652900": ("2042.98", "5.40", "205.40", "589.70"),
            "CN-652800": ("1723.53", "5.50", "125.94", "329.13"),
            "CN-652700": ("575.15", "6.60", "56.93", "151.54"),
            "CN-430700": (None, None, "192.68", "602.56"),
            "CN-652300": ("2637.67", "6.80", "276.81", "453.35"),
            "CN-430100": ("15737.82", "4.00", "1296.87", "1625.77"),
            "CN-320400": (None, None, "715.50", "832.80"),
            "CN-350100": (None, None, "750.55", "1037.15"),
            "CN-650500": ("1162.95", "9.30", "133.20", "233.43"),
            "CN-430400": (None, None, "185.22", "701.16"),
            "CN-653100": ("1752.12", "6.40", "110.51", "812.52"),
            "CN-370200": (None, None, "1340.72", "1718.52"),
            "CN-440700": (None, None, None, None),
            "CN-460100": ("2562.85", "4.80", "253.80", "336.70"),
            "CN-350500": ("13778.34", "5.30", "592.07", "880.29"),
            "CN-320500": ("27695.10", "5.40", "2490.20", "2545.80"),
            "CN-650400": ("668.10", "3.30", "79.34", "151.43"),
            "CN-320200": (None, None, "1225.39", "1274.85"),
            "CN-430900": (None, None, "113.60", "432.00"),
            "CN-210100": (None, None, "794.20", "1031.90"),
            "CN-321000": ("8056.75", "5.50", "376.33", "717.88"),
            "CN-321100": ("5736.78", "5.40", "339.03", "568.23"),
        }
        for city_id, expected_values in expected.items():
            record = values[(city_id, "2025")]
            for field, expected_value in zip(
                [
                    "gdp_current_100m",
                    "gdp_real_growth_pct",
                    "general_public_revenue_100m",
                    "general_public_expenditure_100m",
                ],
                expected_values,
            ):
                if expected_value in (None, ""):
                    self.assertNotIn(field, record)
                else:
                    self.assertEqual(record[field], Decimal(expected_value))
        self.assertGreaterEqual(len(sources), 316)
        curated_ids = {
            source["source_doc_id"]
            for source in sources
            if source["source_doc_id"].startswith("SRC-2025-CURATED-")
        }
        self.assertEqual(len(curated_ids), 22)

    def test_bengbu_2025_bulletin_adds_exact_gdp_growth_sentence(self):
        values, sources = load_city_year_fiscal_sources()

        record = values[("CN-340300", "2025")]
        self.assertEqual(record["gdp_current_100m"], Decimal("2421.10"))
        self.assertEqual(record["gdp_real_growth_pct"], Decimal("5.50"))
        self.assertEqual(record["gdp_real_growth_pct_raw_unit"], "%")
        self.assertIn("5.5%", record["gdp_real_growth_pct_evidence_excerpt"])
        source = next(
            item for item in sources if item["source_doc_id"] == "SRC-B2-AUTONOMOUS-CITY-MACRO-2025-BENGBU"
        )
        self.assertEqual(source["source_grade"], "B2")
        self.assertTrue(all(source["source_grade"] in {"A1", "A2", "B2"} for source in sources))

    def test_ali_2022_2023_gdp_batch_keeps_derived_growth_out_and_marks_estimate(self):
        values, sources = load_city_year_fiscal_sources()

        ali_2022 = values[("CN-542500", "2022")]
        self.assertEqual(ali_2022["gdp_current_100m"], Decimal("80.51"))
        self.assertNotIn("gdp_real_growth_pct", ali_2022)
        self.assertEqual(ali_2022["source_grade"], "B2")

        ali_2023 = values[("CN-542500", "2023")]
        self.assertEqual(ali_2023["gdp_current_100m"], Decimal("91.51"))
        self.assertEqual(ali_2023["gdp_real_growth_pct"], Decimal("13.00"))
        self.assertEqual(ali_2023["data_status"], "preliminary")
        ali_2023_source = next(
            item for item in sources if item["source_doc_id"] == "SRC-B2-ALI-REGION-MACRO-2023-INTERVIEW"
        )
        self.assertIn("预计", ali_2023_source["note"])
        self.assertTrue(any(item["source_doc_id"] == "SRC-B2-ALI-REGION-GDP-2022-RATING" for item in sources))

    def test_jiangsu_2025_city_reports_add_six_missing_whole_city_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-320100": ("1620.90", "1704.90", "886.40"),
            "CN-320600": ("730.00", "1188.70", "768.90"),
            "CN-320700": ("305.70", "607.80", "206.50"),
            "CN-320800": ("335.30", "718.30", "311.60"),
            "CN-320900": ("515.74", "1099.03", "425.83"),
            "CN-321300": ("316.60", "688.60", "215.10"),
        }
        for city_id, (revenue, expenditure, fund) in expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(record["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(fund))
            self.assertEqual(record["source_grade"], "A2")
            self.assertEqual(record["data_status"], "execution")
        self.assertGreaterEqual(len(sources), 79)
        taian = values[("CN-370900", "2025")]
        self.assertEqual(taian["general_public_revenue_100m"], Decimal("261.96"))
        self.assertEqual(taian["general_public_expenditure_100m"], Decimal("486.44"))
        self.assertEqual(taian["gov_fund_revenue_100m"], Decimal("130.77"))
        self.assertEqual(taian["data_status"], "execution")
        taian_source = next(source for source in sources if source["source_doc_id"] == "SRC-A2-TAIAN-CITY-FISCAL-2025")
        self.assertIn("czj.taian.gov.cn", taian_source["landing_page_url"])
        chaoyang_2025 = values[("CN-211300", "2025")]
        self.assertEqual(chaoyang_2025["general_public_revenue_100m"], Decimal("90.31"))
        self.assertEqual(chaoyang_2025["general_public_expenditure_100m"], Decimal("301.34"))
        self.assertEqual(chaoyang_2025["gov_fund_revenue_100m"], Decimal("13.48"))
        self.assertEqual(chaoyang_2025["data_status"], "execution")
        chaoyang_source = next(source for source in sources if source["source_doc_id"] == "SRC-A2-CHAOYANG-CITY-FISCAL-2025")
        self.assertIn("files.chaoyang.gov.cn", chaoyang_source["landing_page_url"])
        nanchang = values[("CN-360100", "2025")]
        self.assertEqual(nanchang["general_public_revenue_100m"], Decimal("537.77"))
        self.assertEqual(nanchang["general_public_expenditure_100m"], Decimal("914.44"))
        self.assertEqual(nanchang["gov_fund_revenue_100m"], Decimal("160.20"))
        self.assertEqual(nanchang["data_status"], "execution")
        nanchang_source = next(source for source in sources if source["source_doc_id"] == "SRC-A1-NANCHANG-CITY-FISCAL-2025")
        self.assertIn("2026sjysgk/202602/0fa3b64fca014c0ca082cef616012ec9.shtml", nanchang_source["landing_page_url"])
        self.assertIn("14.2025%E5%B9%B4%E5%85%A8%E5%B8%82%E6%94%BF%E5%BA%9C", nanchang_source["attachment_url"])
        haikou = values[("CN-460100", "2025")]
        self.assertEqual(haikou["general_public_revenue_100m"], Decimal("253.80"))
        self.assertEqual(haikou["general_public_expenditure_100m"], Decimal("336.70"))
        self.assertEqual(haikou["gov_fund_revenue_100m"], Decimal("68.40"))
        self.assertEqual(haikou["data_status"], "execution")
        yinchuan = values[("CN-640100", "2025")]
        self.assertEqual(yinchuan["general_public_revenue_100m"], Decimal("171.59"))
        self.assertEqual(yinchuan["general_public_expenditure_100m"], Decimal("406.04"))
        self.assertEqual(yinchuan["gov_fund_revenue_100m"], Decimal("45.26"))
        self.assertEqual(yinchuan["data_status"], "execution")
        beijing = values[("CN-110000", "2025")]
        self.assertEqual(beijing["general_public_revenue_100m"], Decimal("6680.60"))
        self.assertEqual(beijing["general_public_expenditure_100m"], Decimal("8401.90"))
        self.assertEqual(beijing["gov_fund_revenue_100m"], Decimal("2193.90"))
        self.assertEqual(beijing["data_status"], "execution")
        chongqing = values[("CN-500000", "2025")]
        self.assertEqual(chongqing["general_public_revenue_100m"], Decimal("2736.00"))
        self.assertEqual(chongqing["general_public_expenditure_100m"], Decimal("5691.00"))
        self.assertEqual(chongqing["gov_fund_revenue_100m"], Decimal("1593.00"))
        self.assertEqual(chongqing["data_status"], "execution")
        shanghai = values[("CN-310000", "2025")]
        self.assertEqual(shanghai["general_public_revenue_100m"], Decimal("8500.90"))
        self.assertEqual(shanghai["general_public_expenditure_100m"], Decimal("9976.00"))
        self.assertEqual(shanghai["gov_fund_revenue_100m"], Decimal("3039.60"))
        self.assertEqual(shanghai["data_status"], "execution")
        tianjin = values[("CN-120000", "2025")]
        self.assertEqual(tianjin["general_public_revenue_100m"], Decimal("2221.70"))
        self.assertEqual(tianjin["general_public_expenditure_100m"], Decimal("3359.70"))
        self.assertEqual(tianjin["gov_fund_revenue_100m"], Decimal("605.50"))
        self.assertEqual(tianjin["data_status"], "execution")
        jingdezhen = values[("CN-360200", "2025")]
        self.assertEqual(jingdezhen["general_public_revenue_100m"], Decimal("90.94"))
        self.assertEqual(jingdezhen["general_public_expenditure_100m"], Decimal("234.95"))
        self.assertEqual(jingdezhen["gov_fund_revenue_100m"], Decimal("172.69"))
        self.assertEqual(jingdezhen["data_status"], "execution")

    def test_jiangxi_regional_table_extracts_economic_and_fiscal_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-360300": ("1276.04", "5.30", "231.27", "87.65"),
            "CN-360400": ("4246.50", "5.20", "322.00", "168.90"),
            "CN-360500": ("1215.58", "5.80", "85.13", "51.50"),
            "CN-360600": ("1459.41", "6.20", "118.33", "66.93"),
            "CN-360700": ("5221.29", "5.50", "333.89", "212.66"),
            "CN-360800": ("3105.67", "5.70", "218.34", "66.87"),
            "CN-360900": ("3930.24", "5.60", "276.34", "121.58"),
            "CN-361000": ("2298.11", "5.90", "150.67", "112.35"),
            "CN-361100": ("3935.90", "5.60", "289.20", "200.40"),
        }
        for city_id, (gdp, growth, revenue, fund) in expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["gdp_current_100m"], Decimal(gdp))
            self.assertEqual(record["gdp_real_growth_pct"], Decimal(growth))
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(fund))
            self.assertEqual(record["data_status"], "execution")
            self.assertEqual(record["source_grade"], "B2")
        self.assertGreaterEqual(len(sources), 88)

        city = {
            "city_id": "CN-360700",
            "admin_code_6": "360700",
            "city_name_cn": "赣州市",
            "province_code": "36",
            "province_name": "江西省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows([city], [], {}, {}, city_year_fiscal=values)
        self.assertEqual(rows[0]["gdp_current_100m"], Decimal("5221.29"))
        self.assertEqual(rows[0]["gdp_real_growth_pct"], Decimal("5.50"))
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("333.89"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("212.66"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("38.91"))
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
                "gov_fund_revenue_100m",
            },
        )
        baoshan = values[("CN-530500", "2025")]
        self.assertEqual(baoshan["general_public_revenue_100m"], Decimal("65.42"))
        self.assertEqual(baoshan["general_public_expenditure_100m"], Decimal("261.71"))
        self.assertEqual(baoshan["gov_fund_revenue_100m"], Decimal("31.64"))
        self.assertEqual(baoshan["data_status"], "execution")
        dali = values[("CN-532900", "2025")]
        self.assertEqual(dali["general_public_revenue_100m"], Decimal("108.02"))
        self.assertEqual(dali["general_public_expenditure_100m"], Decimal("372.30"))
        self.assertEqual(dali["gov_fund_revenue_100m"], Decimal("15.94"))
        self.assertEqual(dali["source_grade"], "A2")
        self.assertEqual(dali["data_status"], "execution")
        dali_source = next(source for source in sources if source["source_doc_id"] == "SRC-A2-DALI-CITY-FISCAL-2025")
        self.assertIn("dali.gov.cn", dali_source["landing_page_url"])
        honghe = values[("CN-532500", "2025")]
        self.assertEqual(honghe["general_public_revenue_100m"], Decimal("153.90"))
        self.assertEqual(honghe["general_public_expenditure_100m"], Decimal("513.50"))
        self.assertEqual(honghe["gov_fund_revenue_100m"], Decimal("76.00"))
        self.assertEqual(honghe["source_grade"], "A2")
        self.assertEqual(honghe["data_status"], "execution")
        honghe_source = next(source for source in sources if source["source_doc_id"] == "SRC-A2-HONGHE-CITY-FISCAL-2025")
        self.assertIn("hh.gov.cn", honghe_source["landing_page_url"])
        diqing = values[("CN-533400", "2025")]
        self.assertEqual(diqing["general_public_revenue_100m"], Decimal("18.49"))
        self.assertEqual(diqing["general_public_expenditure_100m"], Decimal("142.43"))
        self.assertEqual(diqing["gov_fund_revenue_100m"], Decimal("1.48"))
        self.assertEqual(diqing["source_grade"], "A2")
        self.assertEqual(diqing["data_status"], "execution")
        diqing_source = next(source for source in sources if source["source_doc_id"] == "SRC-A2-DIQING-CITY-FISCAL-2025")
        self.assertIn("diqing.gov.cn", diqing_source["landing_page_url"])
        yuxi = values[("CN-530400", "2025")]
        self.assertEqual(yuxi["general_public_revenue_100m"], Decimal("148.21"))
        self.assertEqual(yuxi["general_public_expenditure_100m"], Decimal("300.55"))
        self.assertEqual(yuxi["gov_fund_revenue_100m"], Decimal("27.05"))
        self.assertEqual(yuxi["source_grade"], "A2")
        self.assertEqual(yuxi["data_status"], "execution")
        yuxi_source = next(source for source in sources if source["source_doc_id"] == "SRC-A2-YUXI-CITY-FISCAL-2025")
        self.assertIn("yuxi.gov.cn", yuxi_source["landing_page_url"])
        qujing = values[("CN-530300", "2025")]
        self.assertEqual(qujing["general_public_revenue_100m"], Decimal("164.20"))
        self.assertEqual(qujing["general_public_expenditure_100m"], Decimal("526.50"))
        self.assertEqual(qujing["gov_fund_revenue_100m"], Decimal("37.80"))
        self.assertEqual(qujing["source_grade"], "A2")
        self.assertEqual(qujing["data_status"], "execution")
        qujing_source = next(source for source in sources if source["source_doc_id"] == "SRC-A2-QUJING-CITY-FISCAL-2025")
        self.assertIn("qj.gov.cn", qujing_source["landing_page_url"])
        lijiang = values[("CN-530700", "2025")]
        self.assertEqual(lijiang["general_public_revenue_100m"], Decimal("56.78"))
        self.assertEqual(lijiang["general_public_expenditure_100m"], Decimal("176.32"))
        self.assertEqual(lijiang["gov_fund_revenue_100m"], Decimal("17.07"))
        self.assertEqual(lijiang["source_grade"], "A2")
        self.assertEqual(lijiang["data_status"], "execution")
        lijiang_source = next(source for source in sources if source["source_doc_id"] == "SRC-A2-LIJIANG-CITY-FISCAL-2025")
        self.assertIn("lijiang.gov.cn", lijiang_source["landing_page_url"])
        self.assertIn(".xlsx", lijiang_source["attachment_url"])
        lincang = values[("CN-530900", "2025")]
        self.assertEqual(lincang["general_public_revenue_100m"], Decimal("51.54"))
        self.assertEqual(lincang["general_public_expenditure_100m"], Decimal("266.52"))
        self.assertEqual(lincang["gov_fund_revenue_100m"], Decimal("15.11"))
        self.assertEqual(lincang["statutory_debt_limit_100m"], Decimal("701.62"))
        self.assertEqual(lincang["statutory_debt_balance_100m"], Decimal("689.07"))
        self.assertEqual(lincang["source_grade"], "A2")
        self.assertEqual(lincang["data_status"], "execution")
        lincang_source = next(source for source in sources if source["source_doc_id"] == "SRC-A2-LINCANG-CITY-FISCAL-2025")
        self.assertIn("lincang.gov.cn", lincang_source["landing_page_url"])
        self.assertIn(".pdf", lincang_source["attachment_url"])
        puer = values[("CN-530800", "2025")]
        self.assertEqual(puer["general_public_revenue_100m"], Decimal("62.57"))
        self.assertEqual(puer["general_public_expenditure_100m"], Decimal("306.28"))
        self.assertEqual(puer["gov_fund_revenue_100m"], Decimal("19.53"))
        self.assertEqual(puer["source_grade"], "B2")
        self.assertEqual(puer["data_status"], "execution")
        puer_source = next(source for source in sources if source["source_doc_id"] == "SRC-B2-PUER-CITY-FISCAL-2025")
        self.assertIn("puerw.cn", puer_source["landing_page_url"])
        lvliang = values[("CN-141100", "2025")]
        self.assertEqual(lvliang["general_public_revenue_100m"], Decimal("278.26"))
        self.assertEqual(lvliang["general_public_expenditure_100m"], Decimal("585.48"))
        self.assertEqual(lvliang["gov_fund_revenue_100m"], Decimal("21.62"))
        self.assertEqual(lvliang["data_status"], "execution")
        jincheng = values[("CN-140500", "2025")]
        self.assertEqual(jincheng["general_public_revenue_100m"], Decimal("230.58"))
        self.assertEqual(jincheng["general_public_expenditure_100m"], Decimal("392.05"))
        self.assertEqual(jincheng["gov_fund_revenue_100m"], Decimal("40.64"))
        self.assertEqual(jincheng["data_status"], "execution")
        pingdingshan = values[("CN-410400", "2025")]
        self.assertEqual(pingdingshan["general_public_revenue_100m"], Decimal("226.62"))
        self.assertEqual(pingdingshan["general_public_expenditure_100m"], Decimal("451.26"))
        self.assertEqual(pingdingshan["data_status"], "execution")

        chaoyang = {
            "city_id": "CN-211300",
            "admin_code_6": "211300",
            "city_name_cn": "朝阳市",
            "province_code": "21",
            "province_name": "辽宁省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2024",
        }
        rows, lineage = build_macro_rows(
            [chaoyang], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("87.68"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("314.77"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("12.56"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("12.53"))
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

        lincang_city = {
            "city_id": "CN-530900",
            "admin_code_6": "530900",
            "city_name_cn": "临沧市",
            "province_code": "53",
            "province_name": "云南省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        lincang_rows, lincang_lineage = build_macro_rows(
            [lincang_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(lincang_rows[0]["statutory_debt_limit_100m"], Decimal("701.62"))
        self.assertEqual(lincang_rows[0]["statutory_debt_balance_100m"], Decimal("689.07"))
        self.assertEqual(lincang_rows[0]["debt_limit_utilization_pct"], Decimal("98.21"))
        self.assertEqual(lincang_rows[0]["fund_revenue_dependence_pct"], Decimal("22.67"))
        self.assertEqual(
            {item["target_field"] for item in lincang_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
                "statutory_debt_limit_100m",
                "statutory_debt_balance_100m",
            },
        )

        puer_city = {
            "city_id": "CN-530800",
            "admin_code_6": "530800",
            "city_name_cn": "普洱市",
            "province_code": "53",
            "province_name": "云南省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        puer_rows, puer_lineage = build_macro_rows(
            [puer_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(puer_rows[0]["general_public_revenue_100m"], Decimal("62.57"))
        self.assertEqual(puer_rows[0]["general_public_expenditure_100m"], Decimal("306.28"))
        self.assertEqual(puer_rows[0]["gov_fund_revenue_100m"], Decimal("19.53"))
        self.assertEqual(puer_rows[0]["fund_revenue_dependence_pct"], Decimal("23.79"))
        self.assertEqual(puer_rows[0]["source_grade"], "B2")
        self.assertEqual(
            {item["target_field"] for item in puer_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

        zhangye = values[("CN-620700", "2025")]
        self.assertEqual(zhangye["general_public_revenue_100m"], Decimal("38.90"))
        self.assertEqual(zhangye["general_public_expenditure_100m"], Decimal("194.40"))
        self.assertEqual(zhangye["gov_fund_revenue_100m"], Decimal("8.70"))
        self.assertEqual(zhangye["data_status_label"], "2025年执行数（正文披露）")

        zhangye_city = {
            "city_id": "CN-620700",
            "admin_code_6": "620700",
            "city_name_cn": "张掖市",
            "province_code": "62",
            "province_name": "甘肃省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        zhangye_rows, zhangye_lineage = build_macro_rows(
            [zhangye_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(zhangye_rows[0]["general_public_revenue_100m"], Decimal("38.90"))
        self.assertEqual(zhangye_rows[0]["general_public_expenditure_100m"], Decimal("194.40"))
        self.assertEqual(zhangye_rows[0]["gov_fund_revenue_100m"], Decimal("8.70"))
        self.assertEqual(zhangye_rows[0]["fund_revenue_dependence_pct"], Decimal("18.28"))
        self.assertEqual(zhangye_rows[0]["source_grade"], "A2")
        self.assertEqual(zhangye_rows[0]["data_status"], "execution")

        pingliang = values[("CN-620800", "2025")]
        self.assertEqual(pingliang["general_public_revenue_100m"], Decimal("34.60"))
        self.assertEqual(pingliang["general_public_expenditure_100m"], Decimal("260.70"))
        self.assertEqual(pingliang["gov_fund_revenue_100m"], Decimal("13.70"))
        pingliang_city = {
            "city_id": "CN-620800",
            "admin_code_6": "620800",
            "city_name_cn": "平凉市",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "province_name": "甘肃省",
            "province_code": "62",
            "metric_year": "2025",
        }
        pingliang_rows, pingliang_lineage = build_macro_rows(
            [pingliang_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(pingliang_rows[0]["general_public_revenue_100m"], Decimal("34.60"))
        self.assertEqual(pingliang_rows[0]["general_public_expenditure_100m"], Decimal("260.70"))
        self.assertEqual(pingliang_rows[0]["gov_fund_revenue_100m"], Decimal("13.70"))
        self.assertEqual(pingliang_rows[0]["fund_revenue_dependence_pct"], Decimal("28.36"))
        self.assertEqual(pingliang_rows[0]["source_grade"], "A2")
        self.assertEqual(pingliang_rows[0]["data_status"], "execution")
        changsha = values[("CN-430100", "2025")]
        self.assertEqual(changsha["gov_fund_revenue_100m"], Decimal("528.70"))
        changsha_city = {
            "city_id": "CN-430100",
            "admin_code_6": "430100",
            "city_name_cn": "长沙市",
            "province_code": "43",
            "province_name": "湖南省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        changsha_rows, changsha_lineage = build_macro_rows(
            [changsha_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(changsha_rows[0]["gov_fund_revenue_100m"], Decimal("528.70"))
        self.assertEqual(changsha_rows[0]["source_grade"], "A2")
        self.assertEqual(changsha_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in changsha_lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        chuxiong = values[("CN-532300", "2025")]
        self.assertEqual(chuxiong["general_public_revenue_100m"], Decimal("35.17"))
        self.assertEqual(chuxiong["general_public_expenditure_100m"], Decimal("55.57"))
        self.assertEqual(chuxiong["gov_fund_revenue_100m"], Decimal("27.24"))
        chuxiong_city = {
            "city_id": "CN-532300",
            "admin_code_6": "532300",
            "city_name_cn": "楚雄州",
            "province_code": "53",
            "province_name": "云南省",
            "prefecture_type": "自治州",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        chuxiong_rows, chuxiong_lineage = build_macro_rows(
            [chuxiong_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(chuxiong_rows[0]["general_public_revenue_100m"], Decimal("35.17"))
        self.assertEqual(chuxiong_rows[0]["general_public_expenditure_100m"], Decimal("55.57"))
        self.assertEqual(chuxiong_rows[0]["gov_fund_revenue_100m"], Decimal("27.24"))
        self.assertEqual(chuxiong_rows[0]["source_grade"], "A2")
        self.assertEqual(chuxiong_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in chuxiong_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        suzhou = values[("CN-320500", "2025")]
        self.assertEqual(suzhou["gov_fund_revenue_100m"], Decimal("788.00"))
        suzhou_city = {
            "city_id": "CN-320500",
            "admin_code_6": "320500",
            "city_name_cn": "苏州市",
            "province_code": "32",
            "province_name": "江苏省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        suzhou_rows, suzhou_lineage = build_macro_rows(
            [suzhou_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(suzhou_rows[0]["gov_fund_revenue_100m"], Decimal("788.00"))
        self.assertEqual(suzhou_rows[0]["source_grade"], "A2")
        self.assertEqual(suzhou_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in suzhou_lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "resident_population_10k",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        shijiazhuang = values[("CN-130100", "2025")]
        self.assertEqual(shijiazhuang["gov_fund_revenue_100m"], Decimal("372.65"))
        shijiazhuang_city = {
            "city_id": "CN-130100",
            "admin_code_6": "130100",
            "city_name_cn": "石家庄市",
            "province_code": "13",
            "province_name": "河北省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        shijiazhuang_rows, shijiazhuang_lineage = build_macro_rows(
            [shijiazhuang_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(shijiazhuang_rows[0]["gov_fund_revenue_100m"], Decimal("372.65"))
        self.assertEqual(shijiazhuang_rows[0]["source_grade"], "A1")
        self.assertEqual(shijiazhuang_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in shijiazhuang_lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "resident_population_10k",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        xian = values[("CN-610100", "2025")]
        self.assertEqual(xian["gov_fund_revenue_100m"], Decimal("681.83"))
        xian_city = {
            "city_id": "CN-610100",
            "admin_code_6": "610100",
            "city_name_cn": "西安市",
            "province_code": "61",
            "province_name": "陕西省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        xian_rows, xian_lineage = build_macro_rows(
            [xian_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(xian_rows[0]["gov_fund_revenue_100m"], Decimal("681.83"))
        self.assertEqual(xian_rows[0]["source_grade"], "A2")
        self.assertEqual(xian_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in xian_lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "resident_population_10k",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        nanchang_city = {
            "city_id": "CN-360100",
            "admin_code_6": "360100",
            "city_name_cn": "南昌市",
            "province_code": "36",
            "province_name": "江西省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        nanchang_rows, nanchang_lineage = build_macro_rows(
            [nanchang_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(nanchang_rows[0]["general_public_revenue_100m"], Decimal("537.77"))
        self.assertEqual(nanchang_rows[0]["general_public_expenditure_100m"], Decimal("914.44"))
        self.assertEqual(nanchang_rows[0]["gov_fund_revenue_100m"], Decimal("160.20"))
        self.assertEqual(nanchang_rows[0]["fund_revenue_dependence_pct"], Decimal("22.95"))

        self.assertEqual(nanchang_rows[0]["source_grade"], "A1")
        self.assertEqual(nanchang_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in nanchang_lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        haikou_city = {
            "city_id": "CN-460100",
            "admin_code_6": "460100",
            "city_name_cn": "海口市",
            "province_code": "46",
            "province_name": "海南省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        haikou_rows, haikou_lineage = build_macro_rows(
            [haikou_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(haikou_rows[0]["general_public_revenue_100m"], Decimal("253.80"))
        self.assertEqual(haikou_rows[0]["general_public_expenditure_100m"], Decimal("336.70"))
        self.assertEqual(haikou_rows[0]["gov_fund_revenue_100m"], Decimal("68.40"))
        self.assertEqual(haikou_rows[0]["fund_revenue_dependence_pct"], Decimal("21.23"))
        self.assertEqual(haikou_rows[0]["source_grade"], "A2")
        self.assertEqual(haikou_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in haikou_lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        yinchuan_city = {
            "city_id": "CN-640100",
            "admin_code_6": "640100",
            "city_name_cn": "银川市",
            "province_code": "64",
            "province_name": "宁夏回族自治区",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        yinchuan_rows, yinchuan_lineage = build_macro_rows(
            [yinchuan_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(yinchuan_rows[0]["general_public_revenue_100m"], Decimal("171.59"))
        self.assertEqual(yinchuan_rows[0]["general_public_expenditure_100m"], Decimal("406.04"))
        self.assertEqual(yinchuan_rows[0]["gov_fund_revenue_100m"], Decimal("45.26"))
        self.assertEqual(yinchuan_rows[0]["fund_revenue_dependence_pct"], Decimal("20.87"))
        self.assertEqual(yinchuan_rows[0]["source_grade"], "A2")
        self.assertEqual(yinchuan_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in yinchuan_lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "resident_population_10k",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        beijing_city = {
            "city_id": "CN-110000",
            "admin_code_6": "110000",
            "city_name_cn": "北京市",
            "province_code": "11",
            "province_name": "北京市",
            "prefecture_type": "直辖市",
            "sample_tier": "separate",
            "metric_year": "2025",
        }
        beijing_rows, beijing_lineage = build_macro_rows(
            [beijing_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(beijing_rows[0]["general_public_revenue_100m"], Decimal("6680.60"))
        self.assertEqual(beijing_rows[0]["general_public_expenditure_100m"], Decimal("8401.90"))
        self.assertEqual(beijing_rows[0]["gov_fund_revenue_100m"], Decimal("2193.90"))
        self.assertEqual(beijing_rows[0]["fund_revenue_dependence_pct"], Decimal("24.72"))
        self.assertEqual(beijing_rows[0]["source_grade"], "A2")
        self.assertEqual(beijing_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in beijing_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        chongqing_city = {
            "city_id": "CN-500000",
            "admin_code_6": "500000",
            "city_name_cn": "重庆市",
            "province_code": "50",
            "province_name": "重庆市",
            "prefecture_type": "直辖市",
            "sample_tier": "separate",
            "metric_year": "2025",
        }
        chongqing_rows, chongqing_lineage = build_macro_rows(
            [chongqing_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(chongqing_rows[0]["general_public_revenue_100m"], Decimal("2736.00"))
        self.assertEqual(chongqing_rows[0]["general_public_expenditure_100m"], Decimal("5691.00"))
        self.assertEqual(chongqing_rows[0]["gov_fund_revenue_100m"], Decimal("1593.00"))
        self.assertEqual(chongqing_rows[0]["fund_revenue_dependence_pct"], Decimal("36.80"))
        self.assertEqual(chongqing_rows[0]["source_grade"], "A2")
        self.assertEqual(chongqing_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in chongqing_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        shanghai_city = {
            "city_id": "CN-310000",
            "admin_code_6": "310000",
            "city_name_cn": "上海市",
            "province_code": "31",
            "province_name": "上海市",
            "prefecture_type": "直辖市",
            "sample_tier": "separate",
            "metric_year": "2025",
        }
        shanghai_rows, shanghai_lineage = build_macro_rows(
            [shanghai_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(shanghai_rows[0]["general_public_revenue_100m"], Decimal("8500.90"))
        self.assertEqual(shanghai_rows[0]["general_public_expenditure_100m"], Decimal("9976.00"))
        self.assertEqual(shanghai_rows[0]["gov_fund_revenue_100m"], Decimal("3039.60"))
        self.assertEqual(shanghai_rows[0]["fund_revenue_dependence_pct"], Decimal("26.34"))
        self.assertEqual(shanghai_rows[0]["source_grade"], "A2")
        self.assertEqual(shanghai_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in shanghai_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        tianjin_city = {
            "city_id": "CN-120000",
            "admin_code_6": "120000",
            "city_name_cn": "天津市",
            "province_code": "12",
            "province_name": "天津市",
            "prefecture_type": "直辖市",
            "sample_tier": "separate",
            "metric_year": "2025",
        }
        tianjin_rows, tianjin_lineage = build_macro_rows(
            [tianjin_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(tianjin_rows[0]["general_public_revenue_100m"], Decimal("2221.70"))
        self.assertEqual(tianjin_rows[0]["general_public_expenditure_100m"], Decimal("3359.70"))
        self.assertEqual(tianjin_rows[0]["gov_fund_revenue_100m"], Decimal("605.50"))
        self.assertEqual(tianjin_rows[0]["fund_revenue_dependence_pct"], Decimal("21.42"))
        self.assertEqual(tianjin_rows[0]["source_grade"], "A2")
        self.assertEqual(tianjin_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in tianjin_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        jingdezhen_city = {
            "city_id": "CN-360200",
            "admin_code_6": "360200",
            "city_name_cn": "景德镇市",
            "province_code": "36",
            "province_name": "江西省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        jingdezhen_rows, jingdezhen_lineage = build_macro_rows(
            [jingdezhen_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(jingdezhen_rows[0]["general_public_revenue_100m"], Decimal("90.94"))
        self.assertEqual(jingdezhen_rows[0]["general_public_expenditure_100m"], Decimal("234.95"))
        self.assertEqual(jingdezhen_rows[0]["gov_fund_revenue_100m"], Decimal("172.69"))
        self.assertEqual(jingdezhen_rows[0]["fund_revenue_dependence_pct"], Decimal("65.50"))
        self.assertEqual(jingdezhen_rows[0]["source_grade"], "A2")
        self.assertEqual(jingdezhen_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in jingdezhen_lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        baoshan_city = {
            "city_id": "CN-530500",
            "admin_code_6": "530500",
            "city_name_cn": "保山市",
            "province_code": "53",
            "province_name": "云南省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        baoshan_rows, baoshan_lineage = build_macro_rows(
            [baoshan_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(baoshan_rows[0]["general_public_revenue_100m"], Decimal("65.42"))
        self.assertEqual(baoshan_rows[0]["general_public_expenditure_100m"], Decimal("261.71"))
        self.assertEqual(baoshan_rows[0]["gov_fund_revenue_100m"], Decimal("31.64"))
        self.assertEqual(baoshan_rows[0]["fund_revenue_dependence_pct"], Decimal("32.60"))
        self.assertEqual(baoshan_rows[0]["source_grade"], "A2")
        self.assertEqual(baoshan_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in baoshan_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        lvliang_city = {
            "city_id": "CN-141100",
            "admin_code_6": "141100",
            "city_name_cn": "吕梁市",
            "province_code": "14",
            "province_name": "山西省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        lvliang_rows, lvliang_lineage = build_macro_rows(
            [lvliang_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(lvliang_rows[0]["general_public_revenue_100m"], Decimal("278.26"))
        self.assertEqual(lvliang_rows[0]["general_public_expenditure_100m"], Decimal("585.48"))
        self.assertEqual(lvliang_rows[0]["gov_fund_revenue_100m"], Decimal("21.62"))
        self.assertEqual(lvliang_rows[0]["fund_revenue_dependence_pct"], Decimal("7.21"))
        self.assertEqual(lvliang_rows[0]["source_grade"], "A2")
        self.assertEqual(lvliang_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lvliang_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        jincheng_city = {
            "city_id": "CN-140500",
            "admin_code_6": "140500",
            "city_name_cn": "晋城市",
            "province_code": "14",
            "province_name": "山西省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        jincheng_rows, jincheng_lineage = build_macro_rows(
            [jincheng_city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(jincheng_rows[0]["general_public_revenue_100m"], Decimal("230.58"))
        self.assertEqual(jincheng_rows[0]["general_public_expenditure_100m"], Decimal("392.05"))
        self.assertEqual(jincheng_rows[0]["gov_fund_revenue_100m"], Decimal("40.64"))
        self.assertEqual(jincheng_rows[0]["fund_revenue_dependence_pct"], Decimal("14.98"))
        self.assertEqual(jincheng_rows[0]["source_grade"], "A2")
        self.assertEqual(jincheng_rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in jincheng_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        self.assertEqual(
            {item["target_field"] for item in pingliang_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )
        self.assertEqual(
            {item["target_field"] for item in zhangye_lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_zhejiang_2024_regional_table_extracts_economic_and_fiscal_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-330100": ("21860.00", "4.70", "2640.33", "1531.08"),
            "CN-330200": ("18147.70", "5.40", "1790.04", "716.61"),
            "CN-330300": ("9718.80", "6.30", "632.58", "938.53"),
            "CN-330400": ("7569.53", "5.60", "638.72", "446.62"),
            "CN-330500": ("4213.40", "5.80", "410.73", "381.85"),
            "CN-330600": ("8369.00", "6.50", "588.88", "411.60"),
            "CN-330700": ("6925.52", "6.30", "536.80", "572.48"),
            "CN-330800": ("2262.83", "6.40", "208.55", "192.06"),
        }
        for city_id, expected_values in expected.items():
            record = values[(city_id, "2024")]
            self.assertEqual(record["gdp_current_100m"], Decimal(expected_values[0]))
            self.assertEqual(record["gdp_real_growth_pct"], Decimal(expected_values[1]))
            self.assertEqual(record["general_public_revenue_100m"], Decimal(expected_values[2]))
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(expected_values[3]))
            self.assertEqual(record["source_grade"], "B2")
            self.assertEqual(record["data_status"], "execution")

        zhejiang_sources = [
            source
            for source in sources
            if source["source_doc_id"].startswith("SRC-B2-ZHEJIANG-REGIONAL-FISCAL-2024-")
        ]
        self.assertEqual(len(zhejiang_sources), 8)
        self.assertTrue(all(source["source_grade"] == "B2" for source in zhejiang_sources))

    def test_jiangxi_2024_regional_table_extracts_economic_and_fiscal_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-360100": ("7800.37", "4.90", "526.13", "133.83"),
            "CN-360700": ("4940.47", "5.40", "327.65", "293.80"),
            "CN-360400": ("4021.75", "3.80", "326.00", "155.30"),
            "CN-361100": ("3720.90", "5.70", "282.00", "226.90"),
            "CN-360900": ("3711.05", "6.10", "284.11", "162.02"),
            "CN-360800": ("2917.30", "5.70", "213.54", "74.18"),
            "CN-361000": ("2173.08", "5.90", "147.63", "140.85"),
            "CN-360600": ("1384.34", "7.30", "113.83", "61.91"),
            "CN-360300": ("1211.44", "4.60", "115.36", "121.27"),
            "CN-360200": ("1179.30", "4.10", "90.53", "209.50"),
            "CN-360500": ("1142.52", "0.60", "84.20", "56.00"),
        }
        for city_id, expected_values in expected.items():
            record = values[(city_id, "2024")]
            self.assertEqual(record["gdp_current_100m"], Decimal(expected_values[0]))
            self.assertEqual(record["gdp_real_growth_pct"], Decimal(expected_values[1]))
            self.assertEqual(record["general_public_revenue_100m"], Decimal(expected_values[2]))
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(expected_values[3]))
            expected_grade = "A2" if city_id == "CN-360200" else "B2"
            self.assertEqual(record["source_grade"], expected_grade)
            self.assertEqual(record["data_status"], "execution")

        jiangxi_sources = [
            source
            for source in sources
            if source["source_doc_id"].startswith("SRC-B2-JIANGXI-REGIONAL-FISCAL-2024-")
        ]
        self.assertEqual(len(jiangxi_sources), 11)
        self.assertTrue(all(source["source_grade"] == "B2" for source in jiangxi_sources))

    def test_hubei_2024_regional_table_extracts_economic_and_fiscal_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-420100": ("21106.23", "5.20", "1667.31", "1485.61"),
            "CN-420500": ("6191.12", "6.50", "294.07", None),
            "CN-420600": ("6102.41", "5.90", "285.47", "232.11"),
            "CN-421100": ("3216.65", "6.20", "188.03", "76.41"),
            "CN-420300": ("2565.84", "6.50", "154.55", "99.01"),
            "CN-422800": ("1661.36", "5.80", "102.04", "59.56"),
            "CN-421300": ("1442.35", "6.10", "66.90", "24.74"),
            "CN-420700": ("1341.30", "6.50", "101.52", "113.06"),
        }
        for city_id, expected_values in expected.items():
            record = values[(city_id, "2024")]
            self.assertEqual(record["gdp_current_100m"], Decimal(expected_values[0]))
            self.assertEqual(record["gdp_real_growth_pct"], Decimal(expected_values[1]))
            self.assertEqual(record["general_public_revenue_100m"], Decimal(expected_values[2]))
            if expected_values[3] is None:
                self.assertNotIn("gov_fund_revenue_100m", record)
            else:
                self.assertEqual(record["gov_fund_revenue_100m"], Decimal(expected_values[3]))
            expected_grade = "A2" if city_id == "CN-420700" else "B2"
            self.assertEqual(record["source_grade"], expected_grade)
            self.assertEqual(record["data_status"], "execution")

        hubei_sources = [
            source
            for source in sources
            if source["source_doc_id"].startswith("SRC-B2-HUBEI-REGIONAL-FISCAL-2024-")
        ]
        self.assertEqual(len(hubei_sources), 8)
        self.assertTrue(all(source["source_grade"] == "B2" for source in hubei_sources))

    def test_shanxi_2024_regional_table_extracts_economic_and_fiscal_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-140100": ("5418.87", "1.20", "440.26", "154.49"),
            "CN-140400": ("2593.40", "2.60", "284.73", "39.13"),
            "CN-140700": ("2458.80", "2.30", "179.44", "35.00"),
            "CN-140500": ("2409.80", "6.80", "256.56", "25.83"),
            "CN-140800": ("2190.60", "3.50", "113.55", "35.58"),
            "CN-140200": ("1802.50", "2.50", "188.09", "34.35"),
            "CN-140900": ("1343.40", "-2.20", "136.98", "22.05"),
            "CN-140600": ("1328.50", "-0.50", "131.36", "22.10"),
        }
        for city_id, expected_values in expected.items():
            record = values[(city_id, "2024")]
            self.assertEqual(record["gdp_current_100m"], Decimal(expected_values[0]))
            self.assertEqual(record["gdp_real_growth_pct"], Decimal(expected_values[1]))
            self.assertEqual(record["general_public_revenue_100m"], Decimal(expected_values[2]))
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(expected_values[3]))
            self.assertEqual(record["source_grade"], "B2")
            self.assertEqual(record["data_status"], "execution")

        shanxi_sources = [
            source
            for source in sources
            if source["source_doc_id"].startswith("SRC-B2-SHANXI-REGIONAL-FISCAL-2024-")
        ]
        self.assertEqual(len(shanxi_sources), 8)
        self.assertTrue(all(source["source_grade"] == "B2" for source in shanxi_sources))

    def test_guangxi_2024_regional_table_extracts_economic_and_fiscal_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-450100": ("5995", "3.0", "381.16", "150.59"),
            "CN-450200": ("2951", "1.5", "149.09", "60.66"),
            "CN-450300": ("2517", "3.1", "127.06", "49.43"),
            "CN-450900": ("2347", "4.3", "94.04", "48.09"),
            "CN-450500": ("1888", "5.4", "78.17", "28.14"),
            "CN-450400": ("1622", "7.2", "77.16", "67.73"),
            "CN-451200": ("1404", "5.3", "54.13", "14.25"),
            "CN-451400": ("1313", "6.0", "49.95", "38.91"),
            "CN-451300": ("1030", "5.1", "68.84", "16.87"),
        }
        for city_id, expected_values in expected.items():
            record = values[(city_id, "2024")]
            self.assertEqual(record["gdp_current_100m"], Decimal(expected_values[0]))
            self.assertEqual(record["gdp_real_growth_pct"], Decimal(expected_values[1]))
            self.assertEqual(record["general_public_revenue_100m"], Decimal(expected_values[2]))
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(expected_values[3]))
            self.assertIn(record["source_grade"], {"A2", "B2"})
            self.assertEqual(record["data_status"], "execution")

        guangxi_sources = [
            source
            for source in sources
            if source["source_doc_id"].startswith("SRC-B2-GUANGXI-REGIONAL-FISCAL-2024-")
        ]
        self.assertEqual(len(guangxi_sources), 9)
        self.assertTrue(all(source["source_grade"] == "B2" for source in guangxi_sources))

    def test_anhui_2024_regional_table_extracts_economic_and_fiscal_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-340100": ("13507.69", "6.1", "955.01", "606.20"),
            "CN-340200": ("5120.50", "6.4", "426.76", "167.50"),
            "CN-340800": ("3156.00", "6.0", "203.40", "51.60"),
            "CN-340500": ("2784.60", "6.0", "216.80", "87.90"),
            "CN-341600": ("2521.60", "6.1", "168.84", None),
            "CN-341300": ("2457.30", "5.1", "162.48", "80.64"),
            "CN-341800": ("2053.50", "5.8", "198.10", "88.00"),
            "CN-340700": ("1325.50", "6.4", "117.20", None),
            "CN-341700": ("1177.80", "6.3", "96.28", "11.41"),
        }
        for city_id, expected_values in expected.items():
            record = values[(city_id, "2024")]
            self.assertEqual(record["gdp_current_100m"], Decimal(expected_values[0]))
            self.assertEqual(record["gdp_real_growth_pct"], Decimal(expected_values[1]))
            self.assertEqual(record["general_public_revenue_100m"], Decimal(expected_values[2]))
            if expected_values[3] is None:
                self.assertNotIn("gov_fund_revenue_100m", record)
            else:
                self.assertEqual(record["gov_fund_revenue_100m"], Decimal(expected_values[3]))
            self.assertIn(record["source_grade"], {"A2", "B2"})
            self.assertEqual(record["data_status"], "execution")

        anhui_sources = [
            source
            for source in sources
            if source["source_doc_id"].startswith("SRC-B2-ANHUI-REGIONAL-FISCAL-2024-")
        ]
        self.assertEqual(len(anhui_sources), 9)
        self.assertTrue(all(source["source_grade"] == "B2" for source in anhui_sources))

    def test_shaanxi_2024_regional_table_extracts_economic_and_fiscal_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-610100": ("13317.78", "4.6", "1002.37", "1214.91"),
            "CN-610800": ("7548.68", "6.0", "618.90", None),
            "CN-610400": ("3001.27", "6.5", "114.66", "67.42"),
            "CN-610600": ("2383.36", "5.5", "173.64", "47.84"),
            "CN-610500": ("2157.73", "5.7", "87.77", "64.69"),
            "CN-610200": ("588.82", "6.4", "24.31", "4.70"),
        }
        for city_id, expected_values in expected.items():
            record = values[(city_id, "2024")]
            self.assertEqual(record["gdp_current_100m"], Decimal(expected_values[0]))
            self.assertEqual(record["gdp_real_growth_pct"], Decimal(expected_values[1]))
            if expected_values[2] is None:
                self.assertNotIn("general_public_revenue_100m", record)
                self.assertNotIn("gov_fund_revenue_100m", record)
            else:
                self.assertEqual(record["general_public_revenue_100m"], Decimal(expected_values[2]))
                if expected_values[3] is None:
                    self.assertNotIn("gov_fund_revenue_100m", record)
                else:
                    self.assertEqual(record["gov_fund_revenue_100m"], Decimal(expected_values[3]))
            self.assertEqual(
                record["source_grade"],
                "A1" if city_id == "CN-610800" else "B2",
            )
            self.assertEqual(record["data_status"], "execution")

        shaanxi_sources = [
            source
            for source in sources
            if source["source_doc_id"].startswith("SRC-B2-SHAANXI-REGIONAL-FISCAL-2024-")
        ]
        self.assertEqual(len(shaanxi_sources), 6)
        self.assertTrue(all(source["source_grade"] == "B2" for source in shaanxi_sources))

    def test_city_year_fiscal_batch_adds_shandong_2025_budget_statistics(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-370700": ("630.50", "909.00"),
            "CN-370300": ("419.73", "583.28"),
            "CN-371600": ("318.26", "516.72"),
        }
        for city_id, (revenue, expenditure) in expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(record["general_public_expenditure_100m"], Decimal(expenditure))
        self.assertGreaterEqual(len(sources), 316)
        weifang_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-A2-WEIFANG-CITY-FISCAL-2025"
        )
        self.assertIn("wfcmw.cn", weifang_source["landing_page_url"])
        self.assertEqual(weifang_source["source_grade"], "A2")
        zibo_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-A2-ZIBO-CITY-FISCAL-2025"
        )
        self.assertIn("zibo.gov.cn", zibo_source["landing_page_url"])
        binzhou_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-B2-BINZHOU-CITY-FISCAL-2025"
        )
        self.assertEqual(binzhou_source["source_grade"], "B2")

    def test_city_year_fiscal_batch_adds_zaozhuang_2025_statistical_bulletin(self):
        values, sources = load_city_year_fiscal_sources()

        zaozhuang = values[("CN-370400", "2025")]
        self.assertEqual(zaozhuang["general_public_revenue_100m"], Decimal("200.20"))
        self.assertEqual(zaozhuang["general_public_expenditure_100m"], Decimal("369.16"))
        zaozhuang_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-B2-ZAOZHUANG-CITY-FISCAL-2025"
        )
        self.assertIn("hongheiku.com", zaozhuang_source["landing_page_url"])
        self.assertEqual(zaozhuang_source["source_grade"], "B2")
        self.assertGreaterEqual(len(sources), 316)

    def test_2025_statistical_bulletins_fill_zaozhuang_taizhou_wuhai_economic_gaps(self):
        values, sources = load_city_year_fiscal_sources()

        zaozhuang = values[("CN-370400", "2025")]
        self.assertEqual(zaozhuang["gdp_current_100m"], Decimal("2502.52"))
        self.assertEqual(zaozhuang["gdp_real_growth_pct"], Decimal("5.70"))
        self.assertEqual(zaozhuang["resident_population_10k"], Decimal("380.04"))

        taizhou = values[("CN-321200", "2025")]
        self.assertEqual(taizhou["resident_population_10k"], Decimal("445.10"))

        wuhai = values[("CN-150300", "2025")]
        self.assertEqual(wuhai["resident_population_10k"], Decimal("54.90"))

        for city_id in ("CN-370400", "CN-321200", "CN-150300"):
            city_sources = [
                source for source in sources
                if city_id.replace("-", "") in source["source_doc_id"]
            ]
            self.assertTrue(city_sources)

        city = {
            "city_id": "CN-370400",
            "admin_code_6": "370400",
            "city_name_cn": "枣庄市",
            "province_code": "37",
            "province_name": "山东省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, _ = build_macro_rows([city], [], {}, {}, city_year_fiscal=values)
        self.assertEqual(rows[0]["resident_population_10k"], Decimal("380.04"))

    def test_sichuan_regional_report_adds_2025_revenue_for_18_city_years(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-510300": "87.20",
            "CN-510600": "210.32",
            "CN-510700": "227.62",
            "CN-510800": "77.50",
            "CN-510900": "106.80",
            "CN-511000": "93.43",
            "CN-511100": "172.16",
            "CN-511300": "118.95",
            "CN-511400": "164.50",
            "CN-511500": "333.90",
            "CN-511600": "109.00",
            "CN-511700": "200.30",
            "CN-511900": "75.41",
            "CN-512000": "73.60",
            "CN-513200": "52.10",
            "CN-513300": "71.86",
            "CN-513400": "232.39",
            "CN-510400": "105.20",
        }
        for city_id, revenue in expected.items():
            self.assertEqual(
                values[(city_id, "2025")]["general_public_revenue_100m"],
                Decimal(revenue),
            )

        expected_gdp = {
            "CN-510300": "2003.66",
            "CN-510600": "3387.12",
            "CN-510700": "4600.66",
            "CN-510800": "1348.78",
            "CN-510900": "2002.14",
            "CN-511000": "2050.66",
            "CN-511100": "2501.54",
            "CN-511300": "2901.76",
            "CN-511400": "2008.72",
            "CN-511500": "4134.73",
            "CN-511600": "1700.87",
            "CN-511700": "2990.86",
            "CN-511900": "916.64",
            "CN-512000": "1150.81",
            "CN-513200": "601.19",
            "CN-513300": "613.11",
            "CN-513400": "2605.75",
            "CN-510400": "1409.57",
        }
        for city_id, gdp in expected_gdp.items():
            self.assertEqual(
                values[(city_id, "2025")]["gdp_current_100m"],
                Decimal(gdp),
            )

        report_sources = [
            source for source in sources
            if source["source_doc_id"].startswith("SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-REVENUE-")
        ]
        self.assertEqual(len(report_sources), 18)
        self.assertEqual({source["source_grade"] for source in report_sources}, {"B2"})
        self.assertTrue(all(values[(city_id, "2025")]["page_number"] == "9" for city_id in expected))

    def test_hegang_2025_official_bulletin_fills_four_target_fields(self):
        values, sources = load_city_year_fiscal_sources()

        record = values[("CN-230400", "2025")]
        self.assertEqual(record["gdp_current_100m"], Decimal("392.20"))
        self.assertEqual(record["gdp_real_growth_pct"], Decimal("5.10"))
        self.assertEqual(record["general_public_revenue_100m"], Decimal("36.60"))
        self.assertEqual(record["general_public_expenditure_100m"], Decimal("144.70"))
        self.assertIn("2025年初步统计/执行数", record["source_locator"])
        source = next(
            item
            for item in sources
            if item["source_doc_id"] == "SRC-A2-HEGANG-CITY-BULLETIN-2025-CORE"
        )
        self.assertEqual(source["publisher"], "鹤岗市统计局")
        self.assertEqual(source["source_grade"], "A2")

    def test_liaoning_2025_official_bulletins_fill_huludao_and_liaoyang(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-211400": ("1013.70", "3.50", "80.00", "250.00", "SRC-A2-HULUDAO-CITY-BULLETIN-2025-CORE"),
            "CN-211000": ("1001.20", "4.10", "91.10", "168.30", "SRC-A2-LIAOYANG-CITY-BULLETIN-2025-CORE"),
        }
        for city_id, (gdp, growth, revenue, expenditure, source_id) in expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["gdp_current_100m"], Decimal(gdp))
            self.assertEqual(record["gdp_real_growth_pct"], Decimal(growth))
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(record["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(record["source_grade"], "A2")
            self.assertIn(source_id, record["source_doc_id"])
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertTrue(expected["CN-211400"][4] in source_ids)
        self.assertTrue(expected["CN-211000"][4] in source_ids)

    def test_qinghai_and_gannan_2025_official_bulletins_fill_four_target_fields(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            "CN-630100": ("1914.80", "3.30", "213.40", "375.40", "SRC-A2-XINING-CITY-BULLETIN-2025-CORE"),
            "CN-623000": ("275.62", "5.40", "14.50", "227.06", "SRC-A2-GANNAN-STATE-BULLETIN-2025-CORE"),
        }
        for city_id, (gdp, growth, revenue, expenditure, source_id) in expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["gdp_current_100m"], Decimal(gdp))
            self.assertEqual(record["gdp_real_growth_pct"], Decimal(growth))
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(record["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(record["source_grade"], "A2")
            self.assertIn(source_id, record["source_doc_id"])
        self.assertEqual(
            {item["source_doc_id"] for item in sources if item["source_doc_id"] in {x[4] for x in expected.values()}},
            {x[4] for x in expected.values()},
        )

    def test_honghe_2025_official_gdp_and_chuzhou_wuzhong_2024_fiscal_fill_gaps(self):
        values, sources = load_city_year_fiscal_sources()

        honghe = values[("CN-532500", "2025")]
        self.assertEqual(honghe["gdp_current_100m"], Decimal("3154.52"))
        self.assertEqual(honghe["gdp_real_growth_pct"], Decimal("5.5"))
        self.assertIn("SRC-A2-HONGHE-CITY-GDP-2025", honghe["source_doc_id"])

        chuzhou = values[("CN-341100", "2024")]
        self.assertEqual(chuzhou["general_public_revenue_100m"], Decimal("307.1"))
        self.assertEqual(chuzhou["general_public_expenditure_100m"], Decimal("579"))
        self.assertIn("SRC-A2-CHUZHOU-CITY-BULLETIN-2024-FISCAL", chuzhou["source_doc_id"])

        wuzhong = values[("CN-640300", "2024")]
        self.assertEqual(wuzhong["general_public_revenue_100m"], Decimal("43.14"))
        self.assertEqual(wuzhong["general_public_expenditure_100m"], Decimal("279.37"))
        self.assertIn("SRC-A2-WUZHONG-CITY-FISCAL-2024", wuzhong["source_doc_id"])

        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-HONGHE-CITY-GDP-2025", source_ids)
        self.assertIn("SRC-A2-CHUZHOU-CITY-BULLETIN-2024-FISCAL", source_ids)
        self.assertIn("SRC-A2-WUZHONG-CITY-FISCAL-2024", source_ids)

    def test_xuchang_and_baiyin_2024_official_fiscal_sources_fill_gaps(self):
        values, sources = load_city_year_fiscal_sources()

        xuchang = values[("CN-411000", "2024")]
        self.assertEqual(xuchang["general_public_revenue_100m"], Decimal("183.90"))
        self.assertEqual(xuchang["general_public_expenditure_100m"], Decimal("364.10"))
        self.assertIn("SRC-A2-XUCHANG-CITY-BULLETIN-2024-FISCAL", xuchang["source_doc_id"])
        self.assertEqual(xuchang["source_grade"], "A2")

        baiyin = values[("CN-620400", "2024")]
        self.assertEqual(baiyin["general_public_revenue_100m"], Decimal("40.13"))
        self.assertEqual(baiyin["general_public_expenditure_100m"], Decimal("223.39"))
        self.assertIn("SRC-A2-BAIYIN-CITY-ECONOMIC-RUN-2024-FISCAL", baiyin["source_doc_id"])
        self.assertEqual(baiyin["source_grade"], "A2")

        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-XUCHANG-CITY-BULLETIN-2024-FISCAL", source_ids)
        self.assertIn("SRC-A2-BAIYIN-CITY-ECONOMIC-RUN-2024-FISCAL", source_ids)

    def test_baoshan_and_suihua_2024_official_bulletins_fill_all_four_core_fields(self):
        values, sources = load_city_year_fiscal_sources()

        baoshan = values[("CN-530500", "2024")]
        self.assertEqual(baoshan["gdp_current_100m"], Decimal("1281.91"))
        self.assertEqual(baoshan["gdp_real_growth_pct"], Decimal("2.60"))
        self.assertEqual(baoshan["general_public_revenue_100m"], Decimal("60.22"))
        self.assertEqual(baoshan["general_public_expenditure_100m"], Decimal("253.84"))
        self.assertIn("SRC-A2-BAOSHAN-CITY-BULLETIN-2024-MACRO-FISCAL", baoshan["source_doc_id"])
        self.assertEqual(baoshan["source_grade"], "A2")

        suihua = values[("CN-231200", "2024")]
        self.assertEqual(suihua["gdp_current_100m"], Decimal("1244.00"))
        self.assertEqual(suihua["gdp_real_growth_pct"], Decimal("3.20"))
        self.assertEqual(suihua["general_public_revenue_100m"], Decimal("83.40"))
        self.assertEqual(suihua["general_public_expenditure_100m"], Decimal("558.40"))
        self.assertIn("SRC-A2-SUIHUA-CITY-BULLETIN-2024-MACRO-FISCAL", suihua["source_doc_id"])
        self.assertEqual(suihua["source_grade"], "A2")

        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-BAOSHAN-CITY-BULLETIN-2024-MACRO-FISCAL", source_ids)
        self.assertIn("SRC-A2-SUIHUA-CITY-BULLETIN-2024-MACRO-FISCAL", source_ids)

    def test_bazhou_2022_2023_and_haidong_2024_fiscal_sources_fill_gaps(self):
        values, sources = load_city_year_fiscal_sources()

        bazhou_expected = {
            "2022": ("1519.84", "1.80", "90.94", "290.56"),
            "2023": ("1601.20", "6.20", "102.85", "303.71"),
        }
        fields = (
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        )
        for year, expected in bazhou_expected.items():
            bazhou = values[("CN-652800", year)]
            self.assertEqual(
                tuple(str(bazhou[field]) for field in fields),
                expected,
            )
            self.assertIn(
                f"SRC-A2-BAZHOU-CITY-BULLETIN-{year}-MACRO-FISCAL",
                bazhou["source_doc_id"],
            )
            self.assertEqual(bazhou["source_grade"], "A2")

        haidong = values[("CN-630200", "2024")]
        self.assertEqual(haidong["general_public_revenue_100m"], Decimal("31.36"))
        self.assertEqual(haidong["general_public_expenditure_100m"], Decimal("292.63"))
        self.assertIn("SRC-B2-HAIDONG-CITY-BULLETIN-2024-FISCAL", haidong["source_doc_id"])
        self.assertEqual(haidong["source_grade"], "B2")

        source_ids = {item["source_doc_id"] for item in sources}
        for year in bazhou_expected:
            self.assertIn(f"SRC-A2-BAZHOU-CITY-BULLETIN-{year}-MACRO-FISCAL", source_ids)
        self.assertIn("SRC-B2-HAIDONG-CITY-BULLETIN-2024-FISCAL", source_ids)

    def test_macro_gap_batch_2_sources_fill_current_missing_values(self):
        values, sources = load_city_year_fiscal_sources()

        expected = {
            ("CN-131100", "2024"): {
                "general_public_revenue_100m": Decimal("152.7"),
                "general_public_expenditure_100m": Decimal("451.7"),
            },
            ("CN-140600", "2024"): {
                "general_public_expenditure_100m": Decimal("261.46"),
            },
            ("CN-341200", "2024"): {
                "general_public_revenue_100m": Decimal("195.1"),
                "general_public_expenditure_100m": Decimal("662.3"),
            },
            ("CN-421300", "2024"): {
                "general_public_expenditure_100m": Decimal("238.37"),
            },
            ("CN-540500", "2024"): {
                "general_public_revenue_100m": Decimal("21.4"),
                "general_public_expenditure_100m": Decimal("284.5"),
            },
            ("CN-540600", "2024"): {
                "general_public_revenue_100m": Decimal("11.43"),
                "general_public_expenditure_100m": Decimal("319.48"),
            },
            ("CN-360300", "2025"): {
                "general_public_expenditure_100m": Decimal("334.77"),
            },
            ("CN-510600", "2025"): {
                "gdp_real_growth_pct": Decimal("5.4"),
                "general_public_expenditure_100m": Decimal("437.3"),
            },
            ("CN-510800", "2025"): {
                "gdp_real_growth_pct": Decimal("6.4"),
                "general_public_expenditure_100m": Decimal("353.36"),
            },
            ("CN-420600", "2025"): {
                "gdp_real_growth_pct": Decimal("2.1"),
            },
            ("CN-632300", "2022"): {
                "gdp_current_100m": Decimal("110.89"),
                "gdp_real_growth_pct": Decimal("0.2"),
            },
        }
        for key, field_values in expected.items():
            for field, expected_value in field_values.items():
                self.assertEqual(values[key][field], expected_value, (key, field))
            self.assertEqual(values[key]["source_grade"], "B2")

        source_ids = {item["source_doc_id"] for item in sources}
        self.assertEqual(len({values[key]["source_doc_id"] for key in expected}), 11)
        for key in expected:
            for source_id in values[key]["source_doc_id"].split(";"):
                self.assertIn(source_id, source_ids)

    def test_macro_gap_batch_3_sources_fill_anqing_and_dezhou_2025_gaps(self):
        values, sources = load_city_year_fiscal_sources()

        anqing = values[("CN-340800", "2025")]
        self.assertEqual(anqing["general_public_expenditure_100m"], Decimal("585.1"))
        self.assertIn("SRC-B2-ANQING-CITY-FISCAL-2025", anqing["source_doc_id"])
        self.assertEqual(anqing["source_grade"], "B2")

        dezhou = values[("CN-371400", "2025")]
        self.assertEqual(dezhou["gdp_current_100m"], Decimal("4214.61"))
        self.assertEqual(dezhou["gdp_real_growth_pct"], Decimal("5.3"))
        self.assertEqual(dezhou["general_public_revenue_100m"], Decimal("271.24"))
        self.assertEqual(dezhou["general_public_expenditure_100m"], Decimal("572.74"))
        self.assertIn("SRC-B2-DEZHOU-CITY-GDP-2025", dezhou["source_doc_id"])
        self.assertIn("SRC-B2-DEZHOU-CITY-FISCAL-2025", dezhou["source_doc_id"])
        self.assertIn("SRC-A2-DEZHOU-CITY-MACRO-FISCAL-2025", dezhou["source_doc_id"])
        self.assertEqual(dezhou["source_grade"], "A2")

        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-B2-ANQING-CITY-FISCAL-2025", source_ids)
        self.assertIn("SRC-B2-DEZHOU-CITY-GDP-2025", source_ids)
        self.assertIn("SRC-B2-DEZHOU-CITY-FISCAL-2025", source_ids)

    def test_macro_gap_batch_4_source_fills_shuangyashan_2025_core_gaps(self):
        values, sources = load_city_year_fiscal_sources()

        shuangyashan = values[("CN-230500", "2025")]
        self.assertEqual(shuangyashan["gdp_current_100m"], Decimal("571.1"))
        self.assertEqual(shuangyashan["gdp_real_growth_pct"], Decimal("4.2"))
        self.assertEqual(shuangyashan["general_public_revenue_100m"], Decimal("58.28"))
        self.assertEqual(shuangyashan["general_public_expenditure_100m"], Decimal("224.52"))
        self.assertIn("SRC-B2-SHUANGYASHAN-CITY-MACRO-FISCAL-2025", shuangyashan["source_doc_id"])
        self.assertEqual(shuangyashan["source_grade"], "B2")

        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-B2-SHUANGYASHAN-CITY-MACRO-FISCAL-2025", source_ids)

    def test_macro_gap_batch_5_official_dezhou_bulletin_fills_growth_and_upgrades_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()

        dezhou = values[("CN-371400", "2025")]
        self.assertEqual(dezhou["gdp_current_100m"], Decimal("4214.61"))
        self.assertEqual(dezhou["gdp_real_growth_pct"], Decimal("5.3"))
        self.assertEqual(dezhou["general_public_revenue_100m"], Decimal("271.24"))
        self.assertEqual(dezhou["general_public_expenditure_100m"], Decimal("572.74"))
        self.assertIn("SRC-A2-DEZHOU-CITY-MACRO-FISCAL-2025", dezhou["source_doc_id"])
        self.assertEqual(dezhou["source_grade"], "A2")

        source_ids = {item["source_doc_id"] for item in sources}
        self.assertIn("SRC-A2-DEZHOU-CITY-MACRO-FISCAL-2025", source_ids)

    def test_langfang_2025_official_budget_report_extracts_whole_city_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()
        langfang = values[("CN-131000", "2025")]
        self.assertEqual(langfang["general_public_revenue_100m"], Decimal("311.80"))
        self.assertEqual(langfang["general_public_expenditure_100m"], Decimal("618.70"))
        self.assertEqual(langfang["gov_fund_revenue_100m"], Decimal("86.80"))
        self.assertEqual(langfang["source_grade"], "A2")
        self.assertEqual(langfang["data_status"], "execution")
        langfang_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-A2-LANGFANG-CITY-FISCAL-2025"
        )
        self.assertIn("zhuanti.lf.gov.cn", langfang_source["landing_page_url"])
        self.assertIn("202605061438290149.7z", langfang_source["attachment_url"])
        self.assertEqual(langfang_source["mime_type"], "application/x-7z-compressed")
        self.assertEqual(langfang_source["access_status"], "官方7z附件已归档")
        self.assertEqual(langfang_source["page_count"], "18")

        city = {
            "city_id": "CN-131000",
            "admin_code_6": "131000",
            "city_name_cn": "廊坊市",
            "province_code": "13",
            "province_name": "河北省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("311.80"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("618.70"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("86.80"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("21.78"))
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_baoding_2025_official_budget_report_extracts_whole_city_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()
        baoding = values[("CN-130600", "2025")]
        self.assertEqual(baoding["general_public_revenue_100m"], Decimal("327.06"))
        self.assertEqual(baoding["general_public_expenditure_100m"], Decimal("995.77"))
        self.assertEqual(baoding["gov_fund_revenue_100m"], Decimal("106.98"))
        self.assertEqual(baoding["source_grade"], "A2")
        self.assertEqual(baoding["data_status"], "execution")
        baoding_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-A2-BAODING-CITY-FISCAL-2025"
        )
        self.assertIn("baoding.gov.cn", baoding_source["landing_page_url"])
        self.assertIn("viewFile.do?type=2", baoding_source["attachment_url"])
        self.assertEqual(baoding_source["page_count"], "47")

        city = {
            "city_id": "CN-130600",
            "admin_code_6": "130600",
            "city_name_cn": "保定市",
            "province_code": "13",
            "province_name": "河北省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("327.06"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("995.77"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("106.98"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("24.65"))
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_chengde_2025_official_budget_report_extracts_whole_city_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()
        chengde = values[("CN-130800", "2025")]
        self.assertEqual(chengde["general_public_revenue_100m"], Decimal("144.80"))
        self.assertEqual(chengde["general_public_expenditure_100m"], Decimal("515.60"))
        self.assertEqual(chengde["gov_fund_revenue_100m"], Decimal("27.20"))
        self.assertEqual(chengde["source_grade"], "A2")
        self.assertEqual(chengde["data_status"], "execution")
        chengde_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-A2-CHENGDE-CITY-FISCAL-2025"
        )
        self.assertIn("chengde.gov.cn", chengde_source["landing_page_url"])
        self.assertIn("f937d2f41f9f42a3b640fc1563fa648b.docx", chengde_source["attachment_url"])
        self.assertEqual(chengde_source["mime_type"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertEqual(chengde_source["page_count"], "")

        city = {
            "city_id": "CN-130800",
            "admin_code_6": "130800",
            "city_name_cn": "承德市",
            "province_code": "13",
            "province_name": "河北省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("144.80"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("515.60"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("27.20"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("15.81"))
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertTrue(all(item["locator_type"] == "docx_text_statement" for item in lineage))
        self.assertTrue(all(item["extraction_method"] == "curated-official-docx-statement-parser" for item in lineage))
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_official_fiscal_fund_value_wins_over_lower_grade_fund_duplicate(self):
        fiscal_values, _ = load_city_year_fiscal_sources()
        city = {
            "city_id": "CN-370900",
            "admin_code_6": "370900",
            "city_name_cn": "泰安市",
            "province_code": "37",
            "province_name": "山东省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        duplicate_fund = {
            ("CN-370900", "2025"): {
                "gov_fund_revenue_100m": Decimal("130.77"),
                "source_doc_id": "SRC-B2-TAIAN-CITY-FUND-2025",
                "source_grade": "B2",
                "data_status": "execution",
            }
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, city_year_fiscal=fiscal_values, city_year_fund=duplicate_fund
        )
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("130.77"))
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(
            {item["source_doc_id"] for item in lineage if item["target_field"] == "gov_fund_revenue_100m"},
            {"SRC-A2-TAIAN-CITY-FISCAL-2025"},
        )

    def test_new_verified_macro_gap_batch_is_loaded_with_field_provenance(self):
        values, sources = load_city_year_fiscal_sources()

        xiongan_2024 = values[("CN-133100", "2024")]
        self.assertEqual(xiongan_2024["general_public_revenue_100m"], Decimal("35.58"))
        self.assertEqual(xiongan_2024["general_public_expenditure_100m"], Decimal("498.98"))
        self.assertEqual(xiongan_2024["source_grade"], "A1")
        self.assertEqual(xiongan_2024["data_status"], "final")

        xiongan_2025 = values[("CN-133100", "2025")]
        self.assertEqual(xiongan_2025["general_public_revenue_100m"], Decimal("47.08"))
        self.assertEqual(xiongan_2025["general_public_expenditure_100m"], Decimal("475.20"))
        self.assertEqual(xiongan_2025["source_grade"], "A2")
        self.assertEqual(xiongan_2025["data_status"], "final")

        panjin_2024 = values[("CN-211100", "2024")]
        self.assertEqual(panjin_2024["general_public_expenditure_100m"], Decimal("210.80"))
        self.assertEqual(panjin_2024["source_grade"], "A2")
        self.assertEqual(panjin_2024["data_status"], "execution")

        daxinganling_2023 = values[("CN-232700", "2023")]
        self.assertEqual(daxinganling_2023["gdp_real_growth_pct"], Decimal("-0.40"))
        self.assertEqual(daxinganling_2023["source_grade"], "B2")

        source_ids = {item["source_doc_id"] for item in sources}
        self.assertTrue(
            {
                "SRC-A2-XIONGAN-CITY-FISCAL-2024",
                "SRC-A2-XIONGAN-CITY-FISCAL-2025",
                "SRC-A2-PANJIN-CITY-FISCAL-2024",
                "SRC-B2-DAXINGANLING-CITY-MACRO-2023",
            }.issubset(source_ids)
        )

    def test_current_four_field_gap_batch_is_loaded_with_field_provenance(self):
        values, sources = load_city_year_fiscal_sources()

        haixi = values[("CN-632800", "2025")]
        self.assertEqual(haixi["gdp_current_100m"], Decimal("917.29"))
        self.assertEqual(haixi["gdp_real_growth_pct"], Decimal("7.50"))
        self.assertEqual(haixi["general_public_revenue_100m"], Decimal("81.52"))
        self.assertEqual(haixi["source_grade"], "B2")

        qitaihe = values[("CN-230900", "2025")]
        self.assertEqual(qitaihe["gdp_current_100m"], Decimal("249.40"))
        self.assertEqual(qitaihe["gdp_real_growth_pct"], Decimal("5.50"))
        self.assertEqual(qitaihe["general_public_revenue_100m"], Decimal("34.68"))
        self.assertEqual(qitaihe["source_grade"], "B2")

        yulin = values[("CN-610800", "2025")]
        self.assertEqual(yulin["general_public_revenue_100m"], Decimal("562.52"))
        self.assertEqual(yulin["source_grade"], "A1")
        self.assertEqual(
            yulin["_field_sources"]["general_public_revenue_100m"]["source_grade"],
            "B2",
        )
        self.assertEqual(
            yulin["_field_sources"]["general_public_expenditure_100m"]["source_grade"],
            "A1",
        )

        liaocheng = values[("CN-371500", "2024")]
        self.assertEqual(liaocheng["general_public_expenditure_100m"], Decimal("576.50"))
        self.assertEqual(liaocheng["source_grade"], "B2")

        xianyang = values[("CN-610400", "2024")]
        self.assertEqual(xianyang["general_public_expenditure_100m"], Decimal("517.50"))
        self.assertEqual(xianyang["source_grade"], "B2")

        yanan = values[("CN-610600", "2024")]
        self.assertEqual(yanan["general_public_expenditure_100m"], Decimal("560.58"))
        self.assertEqual(yanan["source_grade"], "B2")

        source_ids = {item["source_doc_id"] for item in sources}
        self.assertTrue(
            {
                "SRC-B2-SINA-CREDIT-300-CITIES-2025-HAIXI",
                "SRC-B2-SINA-CREDIT-300-CITIES-2025-QITAIHE",
                "SRC-B2-SINA-CREDIT-300-CITIES-2025-YULIN",
                "SRC-B2-HUAON-CITY-FISCAL-2024-LIAOCHENG",
                "SRC-B2-HUAON-CITY-FISCAL-2024-XIANYANG",
                "SRC-B2-YANAN-STATISTICAL-BULLETIN-FISCAL-2024",
            }.issubset(source_ids)
        )

    def test_datong_2025_official_budget_report_extracts_whole_city_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()
        datong = values[("CN-140200", "2025")]
        self.assertEqual(datong["general_public_revenue_100m"], Decimal("175.39"))
        self.assertEqual(datong["general_public_expenditure_100m"], Decimal("469.28"))
        self.assertEqual(datong["gov_fund_revenue_100m"], Decimal("44.74"))
        self.assertEqual(datong["source_grade"], "B2")
        self.assertEqual(datong["data_status"], "execution")
        datong_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-B2-DATONG-CITY-FISCAL-2025"
        )
        self.assertIn("dt.gov.cn", datong_source["landing_page_url"])
        self.assertEqual(datong_source["mime_type"], "text/html")
        self.assertEqual(datong_source["page_count"], "1")

        city = {
            "city_id": "CN-140200",
            "admin_code_6": "140200",
            "city_name_cn": "大同市",
            "province_code": "14",
            "province_name": "山西省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("175.39"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("469.28"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("44.74"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("20.32"))
        self.assertEqual(rows[0]["source_grade"], "B2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_changzhi_2025_scanned_official_budget_report_extracts_whole_city_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()
        changzhi = values[("CN-140400", "2025")]
        self.assertEqual(changzhi["general_public_revenue_100m"], Decimal("215.70"))
        self.assertEqual(changzhi["general_public_expenditure_100m"], Decimal("493.97"))
        self.assertEqual(changzhi["gov_fund_revenue_100m"], Decimal("41.53"))
        self.assertEqual(changzhi["source_grade"], "A2")
        self.assertEqual(changzhi["data_status"], "execution")
        changzhi_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-A2-CHANGZHI-CITY-FISCAL-2025"
        )
        self.assertIn("changzhi.gov.cn", changzhi_source["landing_page_url"])
        self.assertIn("P020260122388192880171.pdf", changzhi_source["attachment_url"])
        self.assertEqual(changzhi_source["mime_type"], "application/pdf")
        self.assertEqual(changzhi_source["page_count"], "16")

        city = {
            "city_id": "CN-140400",
            "admin_code_6": "140400",
            "city_name_cn": "长治市",
            "province_code": "14",
            "province_name": "山西省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("215.70"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("493.97"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("41.53"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("16.15"))
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_xuancheng_2025_official_budget_report_extracts_whole_city_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()
        xuancheng = values[("CN-341800", "2025")]
        self.assertEqual(xuancheng["general_public_revenue_100m"], Decimal("200.10"))
        self.assertEqual(xuancheng["general_public_expenditure_100m"], Decimal("377.00"))
        self.assertEqual(xuancheng["gov_fund_revenue_100m"], Decimal("60.60"))
        self.assertEqual(xuancheng["source_grade"], "A2")
        self.assertEqual(xuancheng["data_status"], "execution")
        xuancheng_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-A2-XUANCHENG-CITY-FISCAL-2025"
        )
        self.assertIn("xuancheng.gov.cn", xuancheng_source["landing_page_url"])
        self.assertIn("20260206a37c3db21a3a448a91fb29d6117c45f5.pdf", xuancheng_source["attachment_url"])
        self.assertEqual(xuancheng_source["mime_type"], "application/pdf")
        self.assertEqual(xuancheng_source["page_count"], "15")

        city = {
            "city_id": "CN-341800",
            "admin_code_6": "341800",
            "city_name_cn": "宣城市",
            "province_code": "34",
            "province_name": "安徽省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, city_year_fiscal=values,
        )
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("200.10"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("377.00"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("60.60"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("23.25"))
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_liaoning_and_luan_2025_official_reports_extract_whole_city_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()
        expected = {
            "CN-210400": ("77.20", "187.80", "5.60", "final", "6.76"),
            "CN-210900": ("53.68", "174.24", "4.23", "final", "7.30"),
            "CN-211100": ("150.10", "216.30", "16.10", "execution", "9.69"),
            "CN-341500": ("184.20", "215.70", "41.00", "execution", "18.21"),
        }
        self.assertEqual(len({city_id for city_id, year in values if year == "2025" and city_id in expected}), 4)
        for city_id, (revenue, expenditure, fund_revenue, data_status, dependence) in expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(record["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(fund_revenue))
            self.assertEqual(record["source_grade"], "A2")
            self.assertEqual(record["data_status"], data_status)

        fuxin_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-A2-FUXIN-CITY-FISCAL-2025"
        )
        self.assertEqual(fuxin_source["mime_type"], "text/html")
        self.assertIn("fuxin.gov.cn", fuxin_source["landing_page_url"])

        city = {
            "city_id": "CN-210900",
            "admin_code_6": "210900",
            "city_name_cn": "阜新市",
            "province_code": "21",
            "province_name": "辽宁省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows([city], [], {}, {}, city_year_fiscal=values)
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("53.68"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("174.24"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("4.23"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("7.30"))
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["data_status"], "final")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_chifeng_ankang_yaan_tangshan_sanya_2025_reports_extract_whole_city_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()
        expected = {
            "CN-150400": ("126.25", "687.27", "46.69", "B2"),
            "CN-610900": ("39.34", "400.04", "36.98", "B2"),
            "CN-511800": ("87.86", "251.34", "37.92", "B2"),
            "CN-130200": ("588.20", "1082.75", "299.63", "B2"),
            "CN-460200": ("155.20", "239.20", "138.70", "A2"),
        }
        for city_id, (revenue, expenditure, fund_revenue, grade) in expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(record["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(fund_revenue))
            self.assertEqual(record["source_grade"], grade)
            self.assertEqual(record["data_status"], "execution")

        sanya_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-A2-SANYA-CITY-FISCAL-2025"
        )
        self.assertEqual(sanya_source["mime_type"], "text/html")
        self.assertIn("sanya.gov.cn", sanya_source["landing_page_url"])

        city = {
            "city_id": "CN-610900",
            "admin_code_6": "610900",
            "city_name_cn": "安康市",
            "province_code": "61",
            "province_name": "陕西省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows([city], [], {}, {}, city_year_fiscal=values)
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("39.34"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("400.04"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("36.98"))
        self.assertEqual(rows[0]["source_grade"], "B2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_huainan_2025_official_report_extracts_whole_city_fiscal_and_debt_values(self):
        values, sources = load_city_year_fiscal_sources()
        huainan = values[("CN-340400", "2025")]
        self.assertEqual(huainan["general_public_revenue_100m"], Decimal("139.00"))
        self.assertEqual(huainan["general_public_expenditure_100m"], Decimal("345.40"))
        self.assertEqual(huainan["statutory_debt_limit_100m"], Decimal("793.10"))
        self.assertEqual(huainan["statutory_debt_balance_100m"], Decimal("782.70"))
        self.assertNotIn("gov_fund_revenue_100m", huainan)
        self.assertEqual(huainan["source_grade"], "A2")
        self.assertEqual(huainan["data_status"], "execution")
        huainan_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-A2-HUAINAN-CITY-FISCAL-DEBT-2025"
        )
        self.assertEqual(huainan_source["mime_type"], "application/pdf")
        self.assertIn("huainan.gov.cn", huainan_source["landing_page_url"])
        self.assertEqual(huainan_source["page_count"], "20")

        city = {
            "city_id": "CN-340400",
            "admin_code_6": "340400",
            "city_name_cn": "淮南市",
            "province_code": "34",
            "province_name": "安徽省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows([city], [], {}, {}, city_year_fiscal=values)
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("139.00"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("345.40"))
        self.assertEqual(rows[0]["statutory_debt_limit_100m"], Decimal("793.10"))
        self.assertEqual(rows[0]["statutory_debt_balance_100m"], Decimal("782.70"))
        self.assertEqual(rows[0]["debt_limit_utilization_pct"], Decimal("98.69"))
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "statutory_debt_limit_100m",
                "statutory_debt_balance_100m",
            },
        )

    def test_hohhot_weihai_ezhou_2025_official_reports_extract_whole_city_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()
        expected = {
            "CN-150100": ("268.61", "582.60", "75.78", "B2"),
            "CN-371000": ("257.91", "485.56", "225.52", "A2"),
            "CN-420700": ("107.14", "187.37", "134.68", "A2"),
        }
        for city_id, (revenue, expenditure, fund_revenue, grade) in expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(record["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(fund_revenue))
            self.assertEqual(record["source_grade"], grade)
            self.assertEqual(record["data_status"], "execution")

        weihai_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-A2-WEIHAI-CITY-FISCAL-2025"
        )
        self.assertEqual(weihai_source["mime_type"], "application/pdf")
        self.assertIn("weihai.gov.cn", weihai_source["landing_page_url"])
        self.assertEqual(weihai_source["page_count"], "136")

        city = {
            "city_id": "CN-371000",
            "admin_code_6": "371000",
            "city_name_cn": "威海市",
            "province_code": "37",
            "province_name": "山东省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows([city], [], {}, {}, city_year_fiscal=values)
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("257.91"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("485.56"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("225.52"))
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_luzhou_handan_2025_rating_tables_extract_whole_city_fiscal_values(self):
        values, sources = load_city_year_fiscal_sources()
        expected = {
            "CN-510500": ("233.50", "523.80", "143.70"),
            "CN-130400": ("386.37", "935.15", "163.44"),
        }
        for city_id, (revenue, expenditure, fund_revenue) in expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["general_public_revenue_100m"], Decimal(revenue))
            self.assertEqual(record["general_public_expenditure_100m"], Decimal(expenditure))
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(fund_revenue))
            self.assertEqual(record["source_grade"], "B2")
            self.assertEqual(record["data_status"], "execution")

        luzhou_source = next(
            source for source in sources if source["source_doc_id"] == "SRC-B2-LUZHOU-CITY-FISCAL-2025"
        )
        self.assertEqual(luzhou_source["mime_type"], "application/pdf")
        self.assertIn("sse.com.cn", luzhou_source["landing_page_url"])
        self.assertEqual(luzhou_source["page_count"], "28")

        city = {
            "city_id": "CN-510500",
            "admin_code_6": "510500",
            "city_name_cn": "泸州市",
            "province_code": "51",
            "province_name": "四川省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows([city], [], {}, {}, city_year_fiscal=values)
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("233.50"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("523.80"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("143.70"))
        self.assertEqual(rows[0]["source_grade"], "B2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_2025_rating_tables_keep_all_decimal_digits_in_last_column(self):
        values, _ = load_city_year_fiscal_sources()

        taizhou = values[("CN-321200", "2025")]
        self.assertEqual(taizhou["general_public_revenue_100m"], Decimal("475.49"))
        self.assertEqual(taizhou["general_public_expenditure_100m"], Decimal("686.40"))
        self.assertEqual(taizhou["gov_fund_revenue_100m"], Decimal("388.35"))

        xuzhou = values[("CN-320300", "2025")]
        self.assertEqual(xuzhou["general_public_revenue_100m"], Decimal("575.33"))
        self.assertEqual(xuzhou["general_public_expenditure_100m"], Decimal("1053.50"))
        self.assertEqual(xuzhou["gov_fund_revenue_100m"], Decimal("357.19"))

    def test_chaoyang_2025_fiscal_batch_builds_derived_values(self):
        values, _ = load_city_year_fiscal_sources()
        city = {
            "city_id": "CN-211300",
            "admin_code_6": "211300",
            "city_name_cn": "朝阳市",
            "province_code": "21",
            "province_name": "辽宁省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows([city], [], {}, {}, city_year_fiscal=values)
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("90.31"))
        self.assertEqual(rows[0]["general_public_expenditure_100m"], Decimal("301.34"))
        self.assertEqual(rows[0]["gov_fund_revenue_100m"], Decimal("13.48"))
        self.assertEqual(rows[0]["fund_revenue_dependence_pct"], Decimal("12.99"))
        self.assertEqual(rows[0]["source_grade"], "A2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_next9_2025_henan_economic_batch_extracts_three_cities(self):
        values, sources = load_next9_2025_city_economic()

        self.assertEqual(len(values), 3)
        self.assertEqual(len(sources), 3)
        self.assertEqual(values["CN-410200"]["gdp_current_100m"], Decimal("2860.06"))
        self.assertEqual(values["CN-410200"]["gdp_real_growth_pct"], Decimal("5.10"))
        self.assertEqual(values["CN-410200"]["resident_population_10k"], Decimal("468.70"))
        self.assertEqual(values["CN-410200"]["general_public_revenue_100m"], Decimal("139.70"))
        self.assertEqual(values["CN-410200"]["general_public_expenditure_100m"], Decimal("419.25"))
        self.assertEqual(values["CN-410700"]["gdp_current_100m"], Decimal("3687.07"))
        self.assertEqual(values["CN-410700"]["resident_population_10k"], Decimal("609.10"))
        self.assertEqual(values["CN-410500"]["gdp_current_100m"], Decimal("2765.80"))
        self.assertEqual(values["CN-410500"]["gdp_real_growth_pct"], Decimal("5.50"))
        self.assertEqual(values["CN-410500"]["general_public_expenditure_100m"], Decimal("458.90"))
        self.assertEqual({source["source_grade"] for source in sources}, {"B2"})

        kaifeng = {
            "city_id": "CN-410200",
            "admin_code_6": "410200",
            "city_name_cn": "开封市",
            "province_code": "41",
            "province_name": "河南省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        rows, lineage = build_macro_rows([kaifeng], [], {}, {}, next9_2025_economic=values)
        self.assertEqual(rows[0]["gdp_current_100m"], Decimal("2860.06"))
        self.assertEqual(rows[0]["general_public_revenue_100m"], Decimal("139.70"))
        self.assertEqual(rows[0]["source_grade"], "B2")
        self.assertEqual(rows[0]["data_status"], "execution")
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "resident_population_10k",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
            },
        )

    def test_next10_2025_henan_economic_batch_extracts_three_cities(self):
        values, sources = load_next10_2025_city_economic()

        self.assertEqual(len(values), 3)
        self.assertEqual(len(sources), 3)
        self.assertEqual(values["CN-411300"]["gdp_current_100m"], Decimal("5167.86"))
        self.assertEqual(values["CN-411300"]["gdp_real_growth_pct"], Decimal("6.50"))
        self.assertEqual(values["CN-411300"]["resident_population_10k"], Decimal("939.50"))
        self.assertEqual(values["CN-411300"]["general_public_revenue_100m"], Decimal("228.27"))
        self.assertEqual(values["CN-411300"]["general_public_expenditure_100m"], Decimal("820.36"))
        self.assertEqual(values["CN-411000"]["gdp_current_100m"], Decimal("3583.40"))
        self.assertEqual(values["CN-411000"]["resident_population_10k"], Decimal("434.60"))
        self.assertEqual(values["CN-411000"]["general_public_revenue_100m"], Decimal("192.10"))
        self.assertEqual(values["CN-410600"]["gdp_current_100m"], Decimal("1144.12"))
        self.assertEqual(values["CN-410600"]["gdp_real_growth_pct"], Decimal("6.60"))
        self.assertEqual(values["CN-410600"]["general_public_expenditure_100m"], Decimal("180.46"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

    def test_next11_2025_henan_economic_batch_extracts_three_cities(self):
        values, sources = load_next11_2025_city_economic()

        self.assertEqual(len(values), 3)
        self.assertEqual(len(sources), 3)
        self.assertEqual(values["CN-411400"]["gdp_current_100m"], Decimal("3475.38"))
        self.assertEqual(values["CN-411400"]["gdp_real_growth_pct"], Decimal("6.20"))
        self.assertEqual(values["CN-411400"]["resident_population_10k"], Decimal("756.40"))
        self.assertEqual(values["CN-411400"]["general_public_revenue_100m"], Decimal("193.35"))
        self.assertEqual(values["CN-411400"]["general_public_expenditure_100m"], Decimal("575.56"))
        self.assertEqual(values["CN-411500"]["gdp_current_100m"], Decimal("3196.70"))
        self.assertEqual(values["CN-411500"]["resident_population_10k"], Decimal("595.70"))
        self.assertEqual(values["CN-411500"]["general_public_revenue_100m"], Decimal("137.16"))
        self.assertEqual(values["CN-411600"]["gdp_current_100m"], Decimal("3810.83"))
        self.assertEqual(values["CN-411600"]["gdp_real_growth_pct"], Decimal("6.10"))
        self.assertEqual(values["CN-411600"]["general_public_expenditure_100m"], Decimal("686.48"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

    def test_next12_2025_henan_economic_batch_extracts_three_cities(self):
        values, sources = load_next12_2025_city_economic()

        self.assertEqual(len(values), 3)
        self.assertEqual(len(sources), 3)
        self.assertEqual(values["CN-410900"]["gdp_current_100m"], Decimal("2106.17"))
        self.assertEqual(values["CN-410900"]["gdp_real_growth_pct"], Decimal("5.60"))
        self.assertEqual(values["CN-410900"]["resident_population_10k"], Decimal("366.10"))
        self.assertEqual(values["CN-410900"]["general_public_revenue_100m"], Decimal("123.50"))
        self.assertEqual(values["CN-410900"]["general_public_expenditure_100m"], Decimal("346.18"))
        self.assertEqual(values["CN-411700"]["gdp_current_100m"], Decimal("3501.64"))
        self.assertEqual(values["CN-411700"]["resident_population_10k"], Decimal("665.90"))
        self.assertEqual(values["CN-411700"]["general_public_revenue_100m"], Decimal("214.04"))
        self.assertEqual(values["CN-411100"]["gdp_current_100m"], Decimal("1954.00"))
        self.assertEqual(values["CN-411100"]["gdp_real_growth_pct"], Decimal("6.10"))
        self.assertEqual(values["CN-411100"]["general_public_expenditure_100m"], Decimal("281.20"))
        self.assertEqual({source["source_grade"] for source in sources}, {"B2"})

    def test_next13_2025_pingdingshan_economic_batch_extracts_official_bulletin(self):
        values, sources = load_next13_2025_city_economic()

        self.assertEqual(len(values), 1)
        self.assertEqual(len(sources), 1)
        self.assertEqual(values["CN-410400"]["gdp_current_100m"], Decimal("2929.40"))
        self.assertEqual(values["CN-410400"]["gdp_real_growth_pct"], Decimal("5.40"))
        self.assertEqual(values["CN-410400"]["resident_population_10k"], Decimal("484.40"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})

    def test_next14_2025_jiaozuo_economic_batch_extracts_official_pdf(self):
        values, sources = load_next14_2025_city_economic()

        self.assertEqual(len(values), 1)
        self.assertEqual(len(sources), 1)
        self.assertEqual(values["CN-410800"]["gdp_current_100m"], Decimal("2479.60"))
        self.assertEqual(values["CN-410800"]["gdp_real_growth_pct"], Decimal("6.50"))
        self.assertEqual(values["CN-410800"]["resident_population_10k"], Decimal("346.70"))
        self.assertEqual(values["CN-410800"]["general_public_revenue_100m"], Decimal("135.10"))
        self.assertEqual(values["CN-410800"]["general_public_expenditure_100m"], Decimal("325.50"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})

    def test_next15_2025_sanmenxia_luoyang_economic_batch_extracts_two_cities(self):
        values, sources = load_next15_2025_city_economic()

        self.assertEqual(len(values), 2)
        self.assertEqual(len(sources), 2)
        self.assertEqual(values["CN-411200"]["gdp_current_100m"], Decimal("1702.61"))
        self.assertEqual(values["CN-411200"]["gdp_real_growth_pct"], Decimal("6.10"))
        self.assertEqual(values["CN-411200"]["resident_population_10k"], Decimal("199.50"))
        self.assertEqual(values["CN-411200"]["general_public_revenue_100m"], Decimal("149.51"))
        self.assertEqual(values["CN-411200"]["general_public_expenditure_100m"], Decimal("286.72"))
        self.assertEqual(values["CN-410300"]["gdp_current_100m"], Decimal("6164.52"))
        self.assertEqual(values["CN-410300"]["gdp_real_growth_pct"], Decimal("6.00"))
        self.assertEqual(values["CN-410300"]["resident_population_10k"], Decimal("708.30"))
        self.assertEqual(values["CN-410300"]["general_public_revenue_100m"], Decimal("421.80"))
        self.assertEqual(values["CN-410300"]["general_public_expenditure_100m"], Decimal("725.20"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

    def test_next16_2025_hunan_economic_batch_extracts_three_cities(self):
        values, sources = load_next16_2025_city_economic()

        self.assertEqual(len(values), 3)
        self.assertEqual(len(sources), 3)
        self.assertEqual(values["CN-430600"]["gdp_current_100m"], Decimal("5386.88"))
        self.assertEqual(values["CN-430600"]["gdp_real_growth_pct"], Decimal("5.50"))
        self.assertEqual(values["CN-430600"]["resident_population_10k"], Decimal("493.27"))
        self.assertEqual(values["CN-430900"]["gdp_current_100m"], Decimal("2381.46"))
        self.assertEqual(values["CN-430900"]["gdp_real_growth_pct"], Decimal("5.50"))
        self.assertEqual(values["CN-430900"]["resident_population_10k"], Decimal("369.19"))
        self.assertEqual(values["CN-430700"]["gdp_current_100m"], Decimal("4770.90"))
        self.assertEqual(values["CN-430700"]["gdp_real_growth_pct"], Decimal("5.60"))
        self.assertEqual(values["CN-430700"]["resident_population_10k"], Decimal("510.70"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})

    def test_economic_batch_preserves_existing_fiscal_fields(self):
        values, _ = load_next16_2025_city_economic()
        city = {
            "city_id": "CN-430600",
            "admin_code_6": "430600",
            "city_name_cn": "岳阳市",
            "province_code": "43",
            "province_name": "湖南省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2025",
        }
        fiscal = {
            "CN-430600": {
                "source_doc_id": "SRC-FISCAL-HUNAN-YUEYANG-2025",
                "source_grade": "A2",
                "data_status": "execution",
                "general_public_revenue_100m": Decimal("207.00"),
                "general_public_expenditure_100m": Decimal("664.20"),
                "gov_fund_revenue_100m": Decimal("224.10"),
            }
        }
        rows, lineage = build_macro_rows(
            [city], [], {}, {}, next_2025_fiscal=fiscal, next16_2025_economic=values
        )
        row = rows[0]
        self.assertEqual(row["gdp_current_100m"], Decimal("5386.88"))
        self.assertEqual(row["resident_population_10k"], Decimal("493.27"))
        self.assertEqual(row["general_public_revenue_100m"], Decimal("207.00"))
        self.assertEqual(row["general_public_expenditure_100m"], Decimal("664.20"))
        self.assertEqual(row["gov_fund_revenue_100m"], Decimal("224.10"))
        self.assertEqual(
            row["source_doc_id"],
            "SRC-FISCAL-HUNAN-YUEYANG-2025;SRC-A2-HUNAN-CITY-STATISTICAL-YUEYANG-2025",
        )
        self.assertEqual(
            {item["target_field"] for item in lineage},
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "resident_population_10k",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            },
        )

    def test_next17_2025_hunan_economic_batch_extracts_six_cities(self):
        values, sources = load_next17_2025_city_economic()

        self.assertEqual(len(values), 6)
        self.assertEqual(len(sources), 6)
        self.assertEqual(values["CN-430400"]["gdp_current_100m"], Decimal("4689.55"))
        self.assertEqual(values["CN-430400"]["resident_population_10k"], Decimal("636.36"))
        self.assertEqual(values["CN-430400"]["general_public_revenue_100m"], Decimal("186.35"))
        self.assertEqual(values["CN-430500"]["gdp_real_growth_pct"], Decimal("0.20"))
        self.assertEqual(values["CN-430500"]["general_public_expenditure_100m"], Decimal("652.20"))
        self.assertEqual(values["CN-431000"]["resident_population_10k"], Decimal("455.74"))
        self.assertEqual(values["CN-431100"]["gdp_current_100m"], Decimal("2829.58"))
        self.assertEqual(values["CN-431200"]["general_public_revenue_100m"], Decimal("125.94"))
        self.assertEqual(values["CN-431300"]["resident_population_10k"], Decimal("368.28"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})

    def test_next18_2025_hunan_economic_batch_extracts_three_cities(self):
        values, sources = load_next18_2025_city_economic()

        self.assertEqual(len(values), 3)
        self.assertEqual(len(sources), 3)
        self.assertEqual(values["CN-430800"]["gdp_current_100m"], Decimal("667.83"))
        self.assertEqual(values["CN-430800"]["gdp_real_growth_pct"], Decimal("3.00"))
        self.assertEqual(values["CN-430800"]["resident_population_10k"], Decimal("146.33"))
        self.assertEqual(values["CN-430300"]["general_public_revenue_100m"], Decimal("108.29"))
        self.assertEqual(values["CN-430300"]["general_public_expenditure_100m"], Decimal("295.50"))
        self.assertEqual(values["CN-433100"]["gdp_current_100m"], Decimal("889.50"))
        self.assertEqual(values["CN-433100"]["resident_population_10k"], Decimal("236.06"))
        self.assertEqual(values["CN-433100"]["general_public_revenue_100m"], Decimal("79.90"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})

    def test_next19_2025_hunan_economic_batch_extracts_zhuzhou(self):
        values, sources = load_next19_2025_city_economic()

        self.assertEqual(len(values), 1)
        self.assertEqual(len(sources), 1)
        self.assertEqual(values["CN-430200"]["gdp_current_100m"], Decimal("4063.50"))
        self.assertEqual(values["CN-430200"]["gdp_real_growth_pct"], Decimal("5.60"))
        self.assertEqual(values["CN-430200"]["resident_population_10k"], Decimal("382.04"))
        self.assertEqual(values["CN-430200"]["general_public_revenue_100m"], Decimal("200.40"))
        self.assertEqual(values["CN-430200"]["general_public_expenditure_100m"], Decimal("490.30"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})

    def test_next20_2025_hunan_population_batch_extracts_changsha(self):
        values, sources = load_next20_2025_city_economic()

        self.assertEqual(len(values), 1)
        self.assertEqual(len(sources), 1)
        self.assertEqual(values["CN-430100"]["resident_population_10k"], Decimal("1072.14"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})

    def test_next21_2025_xinjiang_economic_batch_extracts_three_cities(self):
        values, sources = load_next21_2025_city_economic()

        self.assertEqual(len(values), 3)
        self.assertEqual(len(sources), 3)
        self.assertEqual(values["CN-650200"]["gdp_current_100m"], Decimal("1303.96"))
        self.assertEqual(values["CN-650200"]["general_public_revenue_100m"], Decimal("106.92"))
        self.assertEqual(values["CN-650200"]["general_public_expenditure_100m"], Decimal("174.77"))
        self.assertEqual(values["CN-650400"]["resident_population_10k"], Decimal("70.15"))
        self.assertEqual(values["CN-650400"]["general_public_revenue_100m"], Decimal("79.34"))
        self.assertEqual(values["CN-650500"]["gdp_real_growth_pct"], Decimal("9.30"))
        self.assertEqual(values["CN-650500"]["general_public_expenditure_100m"], Decimal("233.43"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

    def test_next22_2025_xinjiang_economic_batch_extracts_changji(self):
        values, sources = load_next22_2025_city_economic()

        self.assertEqual(len(values), 1)
        self.assertEqual(len(sources), 1)
        self.assertEqual(values["CN-652300"]["gdp_current_100m"], Decimal("2637.67"))
        self.assertEqual(values["CN-652300"]["gdp_real_growth_pct"], Decimal("6.80"))
        self.assertEqual(values["CN-652300"]["general_public_revenue_100m"], Decimal("276.81"))
        self.assertEqual(values["CN-652300"]["general_public_expenditure_100m"], Decimal("453.35"))
        self.assertEqual({source["source_grade"] for source in sources}, {"B2"})

    def test_next23_2025_xinjiang_economic_batch_extracts_bozhou_and_bazhou(self):
        values, sources = load_next23_2025_city_economic()

        self.assertEqual(len(values), 2)
        self.assertEqual(len(sources), 2)
        self.assertEqual(values["CN-652700"]["gdp_current_100m"], Decimal("575.15"))
        self.assertEqual(values["CN-652700"]["general_public_revenue_100m"], Decimal("56.93"))
        self.assertEqual(values["CN-652700"]["gov_fund_revenue_100m"], Decimal("25.52"))
        self.assertEqual(values["CN-652800"]["resident_population_10k"], Decimal("146.68"))
        self.assertEqual(values["CN-652800"]["general_public_expenditure_100m"], Decimal("329.13"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

    def test_next24_2025_xinjiang_economic_batch_extracts_hotan_and_kizilsu(self):
        values, sources = load_next24_2025_city_economic()

        self.assertEqual(len(values), 2)
        self.assertEqual(len(sources), 3)
        self.assertEqual(values["CN-653200"]["gdp_current_100m"], Decimal("648.11"))
        self.assertEqual(values["CN-653200"]["gdp_real_growth_pct"], Decimal("6.60"))
        self.assertEqual(values["CN-653200"]["general_public_revenue_100m"], Decimal("51.73"))
        self.assertEqual(values["CN-653200"]["general_public_expenditure_100m"], Decimal("454.22"))
        self.assertEqual(values["CN-653200"]["gov_fund_revenue_100m"], Decimal("10.34"))
        self.assertEqual(values["CN-653000"]["gdp_current_100m"], Decimal("272.24"))
        self.assertEqual(values["CN-653000"]["resident_population_10k"], Decimal("64.07"))
        self.assertEqual(values["CN-653000"]["general_public_revenue_100m"], Decimal("28.63"))
        self.assertEqual(values["CN-653000"]["general_public_expenditure_100m"], Decimal("199.90"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

    def test_next25_2025_xinjiang_economic_batch_extracts_aksu_and_kashgar(self):
        values, sources = load_next25_2025_city_economic()

        self.assertEqual(len(values), 2)
        self.assertEqual(len(sources), 2)
        self.assertEqual(values["CN-652900"]["gdp_current_100m"], Decimal("2042.98"))
        self.assertEqual(values["CN-652900"]["gdp_real_growth_pct"], Decimal("5.40"))
        self.assertEqual(values["CN-652900"]["general_public_revenue_100m"], Decimal("205.40"))
        self.assertEqual(values["CN-652900"]["general_public_expenditure_100m"], Decimal("589.70"))
        self.assertEqual(values["CN-653100"]["gdp_current_100m"], Decimal("1752.12"))
        self.assertEqual(values["CN-653100"]["gdp_real_growth_pct"], Decimal("6.40"))
        self.assertEqual(values["CN-653100"]["general_public_revenue_100m"], Decimal("110.51"))
        self.assertEqual(values["CN-653100"]["general_public_expenditure_100m"], Decimal("812.52"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2", "B2"})

    def test_next26_2025_chengdu_economic_batch_extracts_bulletin_values(self):
        values, sources = load_next26_2025_city_economic()

        self.assertEqual(len(values), 1)
        self.assertEqual(len(sources), 1)
        self.assertEqual(values["CN-510100"]["gdp_current_100m"], Decimal("24763.60"))
        self.assertEqual(values["CN-510100"]["gdp_real_growth_pct"], Decimal("5.80"))
        self.assertEqual(values["CN-510100"]["resident_population_10k"], Decimal("2153.50"))
        self.assertEqual(sources[0]["source_grade"], "B2")

    def test_next27_2025_jiangsu_economic_batch_extracts_yangzhou_and_zhenjiang(self):
        values, sources = load_next27_2025_city_economic()

        self.assertEqual(len(values), 2)
        self.assertEqual(len(sources), 2)
        self.assertEqual(values["CN-321000"]["gdp_current_100m"], Decimal("8056.75"))
        self.assertEqual(values["CN-321000"]["gdp_real_growth_pct"], Decimal("5.50"))
        self.assertEqual(values["CN-321000"]["resident_population_10k"], Decimal("456.49"))
        self.assertEqual(values["CN-321100"]["gdp_current_100m"], Decimal("5736.78"))
        self.assertEqual(values["CN-321100"]["gdp_real_growth_pct"], Decimal("5.40"))
        self.assertEqual({source["source_grade"] for source in sources}, {"B2"})

    def test_next28_2025_haikou_yichang_batch_extracts_economic_population(self):
        values, sources = load_next28_2025_city_economic()

        self.assertEqual(len(values), 2)
        self.assertEqual(len(sources), 2)
        self.assertEqual(values["CN-460100"]["gdp_current_100m"], Decimal("2562.85"))
        self.assertEqual(values["CN-460100"]["gdp_real_growth_pct"], Decimal("4.80"))
        self.assertEqual(values["CN-420500"]["resident_population_10k"], Decimal("390.06"))
        self.assertEqual({source["source_grade"] for source in sources}, {"B2"})

    def test_next29_2025_hefei_batch_extracts_population(self):
        values, sources = load_next29_2025_city_economic()

        self.assertEqual(len(values), 1)
        self.assertEqual(len(sources), 1)
        self.assertEqual(values["CN-340100"]["resident_population_10k"], Decimal("1000.50"))
        self.assertEqual(sources[0]["source_grade"], "B2")

    def test_city_year_fund_batch_extracts_hohhot_and_chifeng(self):
        values, sources = load_city_year_fund_sources()

        self.assertEqual(len(values), 82)
        self.assertEqual(len(sources), 82)
        self.assertEqual(values[("CN-445300", "2025")]["gov_fund_revenue_100m"], Decimal("10.22"))
        yunfu_source = next(source for source in sources if source["source_doc_id"] == "SRC-A2-YUNFU-CITY-FUND-2025")
        self.assertIn("yunfu.gov.cn", yunfu_source["landing_page_url"])
        self.assertEqual(yunfu_source["source_grade"], "A2")
        self.assertEqual(values[("CN-440400", "2025")]["gov_fund_revenue_100m"], Decimal("32.70"))
        self.assertEqual(values[("CN-440600", "2025")]["gov_fund_revenue_100m"], Decimal("376.06"))
        self.assertEqual(values[("CN-440400", "2025")]["source_grade"], "B2")
        self.assertEqual(values[("CN-440600", "2025")]["source_grade"], "B2")
        self.assertEqual(values[("CN-440700", "2025")]["gov_fund_revenue_100m"], Decimal("120.01"))
        jiangmen_source = next(source for source in sources if source["source_doc_id"] == "SRC-A2-JIANGMEN-CITY-FUND-2025")
        self.assertIn("jiangmen.gov.cn", jiangmen_source["landing_page_url"])
        self.assertEqual(jiangmen_source["source_grade"], "A2")
        self.assertEqual(values[("CN-150100", "2024")]["gov_fund_revenue_100m"], Decimal("112.52"))
        self.assertEqual(values[("CN-150100", "2025")]["gov_fund_revenue_100m"], Decimal("75.78"))
        self.assertEqual(values[("CN-150400", "2025")]["gov_fund_revenue_100m"], Decimal("46.69"))
        self.assertEqual(values[("CN-140200", "2025")]["gov_fund_revenue_100m"], Decimal("44.74"))
        self.assertEqual(values[("CN-141100", "2025")]["gov_fund_revenue_100m"], Decimal("21.62"))
        self.assertEqual(values[("CN-410400", "2025")]["gov_fund_revenue_100m"], Decimal("70.30"))
        self.assertEqual(values[("CN-610900", "2025")]["gov_fund_revenue_100m"], Decimal("36.98"))
        self.assertEqual(values[("CN-341800", "2025")]["gov_fund_revenue_100m"], Decimal("60.60"))
        self.assertEqual(values[("CN-511800", "2025")]["gov_fund_revenue_100m"], Decimal("37.92"))
        self.assertEqual(values[("CN-410100", "2025")]["gov_fund_revenue_100m"], Decimal("277.50"))
        self.assertEqual(values[("CN-510100", "2025")]["gov_fund_revenue_100m"], Decimal("1280.45"))
        self.assertEqual(values[("CN-610300", "2025")]["gov_fund_revenue_100m"], Decimal("29.84"))
        self.assertEqual(values[("CN-410400", "2019")]["gov_fund_revenue_100m"], Decimal("119.93"))
        self.assertEqual(values[("CN-410200", "2019")]["gov_fund_revenue_100m"], Decimal("189.30"))
        self.assertEqual(values[("CN-411300", "2019")]["gov_fund_revenue_100m"], Decimal("217.70"))
        self.assertEqual(values[("CN-411200", "2019")]["gov_fund_revenue_100m"], Decimal("38.76"))
        self.assertEqual(values[("CN-411600", "2019")]["gov_fund_revenue_100m"], Decimal("213.80"))
        self.assertEqual(values[("CN-410800", "2025")]["gov_fund_revenue_100m"], Decimal("76.10"))
        self.assertEqual(values[("CN-411600", "2025")]["gov_fund_revenue_100m"], Decimal("87.90"))
        self.assertEqual(values[("CN-410700", "2025")]["gov_fund_revenue_100m"], Decimal("38.60"))
        self.assertEqual(values[("CN-410200", "2025")]["gov_fund_revenue_100m"], Decimal("72.80"))
        self.assertEqual(values[("CN-130200", "2025")]["gov_fund_revenue_100m"], Decimal("299.63"))
        self.assertEqual(values[("CN-210400", "2025")]["gov_fund_revenue_100m"], Decimal("5.60"))
        self.assertEqual(values[("CN-210400", "2025")]["data_status"], "final")
        self.assertEqual(values[("CN-210900", "2025")]["gov_fund_revenue_100m"], Decimal("4.23"))
        self.assertEqual(values[("CN-210900", "2025")]["data_status"], "final")
        self.assertEqual(values[("CN-211100", "2025")]["gov_fund_revenue_100m"], Decimal("16.10"))
        self.assertEqual(values[("CN-211100", "2025")]["data_status"], "execution")
        self.assertEqual(values[("CN-511900", "2025")]["gov_fund_revenue_100m"], Decimal("123.94"))
        self.assertEqual(values[("CN-511600", "2025")]["gov_fund_revenue_100m"], Decimal("97.40"))
        self.assertEqual(values[("CN-511000", "2025")]["gov_fund_revenue_100m"], Decimal("118.79"))
        self.assertEqual(values[("CN-511300", "2025")]["gov_fund_revenue_100m"], Decimal("188.70"))
        self.assertEqual(values[("CN-510600", "2025")]["gov_fund_revenue_100m"], Decimal("186.57"))
        self.assertEqual(values[("CN-511500", "2025")]["gov_fund_revenue_100m"], Decimal("149.60"))
        self.assertEqual(values[("CN-510400", "2025")]["gov_fund_revenue_100m"], Decimal("17.39"))
        self.assertEqual(values[("CN-513200", "2025")]["gov_fund_revenue_100m"], Decimal("12.50"))
        self.assertEqual(values[("CN-513300", "2025")]["gov_fund_revenue_100m"], Decimal("8.63"))
        self.assertEqual(values[("CN-513400", "2025")]["gov_fund_revenue_100m"], Decimal("56.53"))
        sichuan_sources = [source for source in sources if source["source_doc_id"].startswith("SRC-B2-SICHUAN-REGIONAL-FISCAL-2025")]
        self.assertEqual(len(sichuan_sources), 10)
        self.assertTrue(all(source["source_grade"] == "B2" for source in sichuan_sources))
        self.assertEqual(values[("CN-510500", "2025")]["gov_fund_revenue_100m"], Decimal("143.70"))
        self.assertEqual(values[("CN-510500", "2025")]["data_status"], "execution")
        self.assertEqual(values[("CN-341500", "2025")]["gov_fund_revenue_100m"], Decimal("41.00"))
        self.assertEqual(values[("CN-341500", "2025")]["data_status"], "execution")
        self.assertEqual(values[("CN-441500", "2025")]["gov_fund_revenue_100m"], Decimal("31.40"))
        self.assertEqual(values[("CN-441500", "2025")]["data_status"], "execution")
        self.assertEqual(values[("CN-371000", "2025")]["gov_fund_revenue_100m"], Decimal("225.52"))
        self.assertEqual(values[("CN-371000", "2025")]["data_status"], "execution")
        self.assertEqual(values[("CN-130400", "2025")]["gov_fund_revenue_100m"], Decimal("163.44"))
        self.assertEqual(values[("CN-130400", "2025")]["data_status"], "execution")
        self.assertEqual(values[("CN-340800", "2025")]["gov_fund_revenue_100m"], Decimal("40.40"))
        self.assertEqual(values[("CN-340800", "2025")]["data_status"], "execution")
        self.assertEqual(values[("CN-420700", "2025")]["gov_fund_revenue_100m"], Decimal("134.68"))
        self.assertEqual(values[("CN-420700", "2025")]["data_status"], "execution")
        self.assertEqual(values[("CN-370700", "2025")]["gov_fund_revenue_100m"], Decimal("413.14"))
        self.assertEqual(values[("CN-370300", "2025")]["gov_fund_revenue_100m"], Decimal("238.07"))
        self.assertEqual(values[("CN-370900", "2025")]["gov_fund_revenue_100m"], Decimal("130.77"))
        self.assertEqual(values[("CN-371600", "2025")]["gov_fund_revenue_100m"], Decimal("156.32"))
        self.assertEqual(values[("CN-371100", "2025")]["gov_fund_revenue_100m"], Decimal("179.29"))
        self.assertEqual(values[("CN-370400", "2025")]["gov_fund_revenue_100m"], Decimal("287.24"))

    def test_2025_fund_batch_extracts_fujian_and_other_whole_city_values(self):
        values, sources = load_city_year_fund_sources()

        expected = {
            "CN-350200": ("317.77", "B2"),
            "CN-350300": ("109.19", "A2"),
            "CN-350400": ("27.24", "A2"),
            "CN-350700": ("57.48", "B2"),
            "CN-350800": ("63.43", "B2"),
            "CN-350900": ("61.13", "B2"),
            "CN-450600": ("17.90", "A2"),
            "CN-640400": ("20.71", "A2"),
            "CN-341300": ("61.81", "A2"),
            "CN-441700": ("20.56", "B2"),
        }

        self.assertEqual(
            {city_id for city_id, year in values if year == "2025" and city_id in expected},
            set(expected),
        )
        for city_id, (fund_revenue, source_grade) in expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(fund_revenue))
            self.assertEqual(record["source_grade"], source_grade)
            self.assertEqual(record["data_status"], "execution")
        self.assertEqual(values[("CN-350400", "2025")]["gov_fund_revenue_raw_100m"], Decimal("272426"))
        self.assertEqual(values[("CN-350400", "2025")]["gov_fund_revenue_raw_unit"], "万元")

        batch_source_ids = {
            source["source_doc_id"]
            for source in sources
            if source["source_doc_id"].startswith("SRC-2025-FUND-BATCH-")
        }
        self.assertEqual(len(batch_source_ids), 10)
        self.assertEqual({values[key]["data_status"] for key in [
            ("CN-370700", "2025"), ("CN-370300", "2025"), ("CN-370900", "2025"),
            ("CN-371600", "2025"), ("CN-371100", "2025"), ("CN-370400", "2025"),
        ]}, {"execution"})
        self.assertEqual(values[("CN-460200", "2025")]["gov_fund_revenue_100m"], Decimal("138.70"))
        self.assertEqual(values[("CN-460200", "2025")]["data_status"], "execution")
        self.assertEqual(values[("CN-530400", "2025")]["gov_fund_revenue_100m"], Decimal("27.05"))
        self.assertEqual(values[("CN-530300", "2025")]["gov_fund_revenue_100m"], Decimal("37.80"))
        self.assertEqual(values[("CN-410400", "2019")]["data_status"], "final")
        self.assertEqual(values[("CN-411200", "2018")]["gov_fund_revenue_100m"], Decimal("42.62"))
        self.assertEqual(values[("CN-141100", "2018")]["gov_fund_revenue_100m"], Decimal("22.21"))
        self.assertEqual(values[("CN-411700", "2018")]["gov_fund_revenue_100m"], Decimal("184.70"))
        self.assertEqual(values[("CN-130100", "2018")]["gov_fund_revenue_100m"], Decimal("560.87"))
        self.assertEqual(values[("CN-350400", "2018")]["gov_fund_revenue_100m"], Decimal("81.42"))
        self.assertEqual(values[("CN-350400", "2019")]["gov_fund_revenue_100m"], Decimal("90.06"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A1", "A2", "B2"})

    def test_2025_zhejiang_fund_batch_extracts_all_eleven_whole_city_values(self):
        values, sources = load_city_year_fund_sources()

        expected = {
            "CN-330100": "1717.13",
            "CN-330200": "535.34",
            "CN-330300": "884.27",
            "CN-330400": "414.43",
            "CN-330500": "345.94",
            "CN-330600": "407.19",
            "CN-330700": "541.78",
            "CN-330800": "170.15",
            "CN-330900": "89.39",
            "CN-331000": "463.06",
            "CN-331100": "234.13",
        }

        for city_id, fund_revenue in expected.items():
            record = values[(city_id, "2025")]
            self.assertEqual(record["gov_fund_revenue_100m"], Decimal(fund_revenue))
            self.assertEqual(record["source_grade"], "B2")
            self.assertEqual(record["data_status"], "execution")
        batch_source_ids = {
            source["source_doc_id"]
            for source in sources
            if source["source_doc_id"].startswith("SRC-B2-ZHEJIANG-2025-FUND-")
        }
        self.assertEqual(len(batch_source_ids), 11)

        cities = [
            {
                "city_id": city_id,
                "admin_code_6": city_id.removeprefix("CN-"),
                "city_name_cn": "呼和浩特市" if city_id == "CN-150100" else "赤峰市",
                "province_code": "15",
                "province_name": "内蒙古自治区",
                "prefecture_type": "地级市",
                "sample_tier": "core",
                "metric_year": year,
            }
            for city_id, year in (
                ("CN-150100", "2024"),
                ("CN-150100", "2025"),
                ("CN-150400", "2025"),
                ("CN-140200", "2025"),
                ("CN-141100", "2025"),
                ("CN-410400", "2025"),
                ("CN-610900", "2025"),
                ("CN-341800", "2025"),
                ("CN-511800", "2025"),
                ("CN-410100", "2025"),
                ("CN-510100", "2025"),
                ("CN-610300", "2025"),
            )
        ]
        rows, lineage = build_macro_rows(cities, [], {}, {}, city_year_fund=values)
        self.assertEqual(
            [row["gov_fund_revenue_100m"] for row in rows],
            [
                Decimal("112.52"),
                Decimal("75.78"),
                Decimal("46.69"),
                Decimal("44.74"),
                Decimal("21.62"),
                Decimal("70.30"),
                Decimal("36.98"),
                Decimal("60.60"),
                Decimal("37.92"),
                Decimal("277.50"),
                Decimal("1280.45"),
                Decimal("29.84"),
            ],
        )
        self.assertEqual({row["source_grade"] for row in rows}, {"A1", "A2", "B2"})
        self.assertEqual({row["collection_status"] for row in rows}, {"extracted", "needs_review"})
        self.assertEqual({item["target_field"] for item in lineage}, {"gov_fund_revenue_100m"})

        pingdingshan = {
            "city_id": "CN-410400",
            "admin_code_6": "410400",
            "city_name_cn": "平顶山市",
            "province_code": "41",
            "province_name": "河南省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2019",
        }
        final_rows, final_lineage = build_macro_rows(
            [pingdingshan], [], {}, {}, city_year_fund=values,
        )
        self.assertEqual(final_rows[0]["gov_fund_revenue_100m"], Decimal("119.93"))
        self.assertEqual(final_rows[0]["source_grade"], "A1")
        self.assertEqual(final_rows[0]["collection_status"], "extracted")
        self.assertEqual({item["target_field"] for item in final_lineage}, {"gov_fund_revenue_100m"})

        sanming = {
            "city_id": "CN-350400",
            "admin_code_6": "350400",
            "city_name_cn": "三明市",
            "province_code": "35",
            "province_name": "福建省",
            "prefecture_type": "地级市",
            "sample_tier": "core",
            "metric_year": "2018",
        }
        sanming_rows, sanming_lineage = build_macro_rows(
            [sanming], [], {}, {}, city_year_fund=values,
        )
        self.assertEqual(sanming_rows[0]["gov_fund_revenue_100m"], Decimal("81.42"))
        self.assertEqual(sanming_rows[0]["source_grade"], "A2")
        self.assertEqual(sanming_rows[0]["collection_status"], "extracted")
        self.assertEqual({item["target_field"] for item in sanming_lineage}, {"gov_fund_revenue_100m"})


if __name__ == "__main__":
    unittest.main()
