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
    load_followup_2025_city_fiscal,
    load_ningxia_2025_city_fiscal,
    load_next2_2025_city_fiscal,
    load_next3_2025_city_fiscal,
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


if __name__ == "__main__":
    unittest.main()
