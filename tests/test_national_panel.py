import csv
from decimal import Decimal
from pathlib import Path

import unittest

from scripts.collect_national_panel import (
    build_city_master,
    build_debt_rows,
    build_collection_status,
    build_evidence_based_missing_rows,
    build_macro_rows,
    compute_derived_values,
    load_city_year_fiscal_sources,
    load_followup_2025_city_fiscal,
    load_city_year_fund_sources,
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
    load_next_2025_city_fiscal,
    load_shandong_2025_city_fiscal,
    order_calculation_rows_for_lineage,
    validate_city_master,
    validate_no_zero_for_missing,
)


class NationalPanelTests(unittest.TestCase):

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
        self.assertEqual(len(build_evidence_based_missing_rows()), 10)

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
        self.assertEqual(len(sources), 20)
        self.assertEqual({source["source_grade"] for source in sources}, {"A1", "A2"})
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
        baoshan = values[("CN-530500", "2025")]
        self.assertEqual(baoshan["general_public_revenue_100m"], Decimal("65.42"))
        self.assertEqual(baoshan["general_public_expenditure_100m"], Decimal("261.71"))
        self.assertEqual(baoshan["gov_fund_revenue_100m"], Decimal("31.64"))
        self.assertEqual(baoshan["data_status"], "execution")
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
            {"gov_fund_revenue_100m"},
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
            {"gov_fund_revenue_100m"},
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
            {"gov_fund_revenue_100m"},
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
            {"gov_fund_revenue_100m"},
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
        self.assertEqual(len(sources), 2)
        self.assertEqual(values["CN-653200"]["gdp_real_growth_pct"], Decimal("6.60"))
        self.assertEqual(values["CN-653200"]["general_public_revenue_100m"], Decimal("51.73"))
        self.assertEqual(values["CN-653200"]["general_public_expenditure_100m"], Decimal("454.22"))
        self.assertEqual(values["CN-653200"]["gov_fund_revenue_100m"], Decimal("10.34"))
        self.assertEqual(values["CN-653000"]["gdp_current_100m"], Decimal("272.24"))
        self.assertEqual(values["CN-653000"]["resident_population_10k"], Decimal("64.07"))
        self.assertEqual(values["CN-653000"]["general_public_revenue_100m"], Decimal("28.63"))
        self.assertEqual(values["CN-653000"]["general_public_expenditure_100m"], Decimal("199.90"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A2"})

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

        self.assertEqual(len(values), 30)
        self.assertEqual(len(sources), 30)
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
        self.assertEqual(values[("CN-210900", "2025")]["gov_fund_revenue_100m"], Decimal("4.22"))
        self.assertEqual(values[("CN-210900", "2025")]["data_status"], "final")
        self.assertEqual(values[("CN-410400", "2019")]["data_status"], "final")
        self.assertEqual(values[("CN-411200", "2018")]["gov_fund_revenue_100m"], Decimal("42.62"))
        self.assertEqual(values[("CN-141100", "2018")]["gov_fund_revenue_100m"], Decimal("22.21"))
        self.assertEqual(values[("CN-411700", "2018")]["gov_fund_revenue_100m"], Decimal("184.70"))
        self.assertEqual(values[("CN-130100", "2018")]["gov_fund_revenue_100m"], Decimal("560.87"))
        self.assertEqual(values[("CN-350400", "2018")]["gov_fund_revenue_100m"], Decimal("81.42"))
        self.assertEqual(values[("CN-350400", "2019")]["gov_fund_revenue_100m"], Decimal("90.06"))
        self.assertEqual({source["source_grade"] for source in sources}, {"A1", "A2", "B2"})

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
