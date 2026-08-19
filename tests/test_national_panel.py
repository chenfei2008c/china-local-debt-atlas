import csv
from decimal import Decimal
from pathlib import Path

import unittest

from scripts.collect_national_panel import (
    build_city_master,
    build_debt_rows,
    build_macro_rows,
    compute_derived_values,
    validate_city_master,
    validate_no_zero_for_missing,
)


class NationalPanelTests(unittest.TestCase):

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


if __name__ == "__main__":
    unittest.main()
