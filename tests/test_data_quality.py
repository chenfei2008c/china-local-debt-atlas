import unittest
from decimal import Decimal

from scripts.collect_national_panel import compute_derived_values
from scripts.data_quality import ACCEPTED_SOURCE_GRADES, assess_field_value, is_accepted_source_grade
from scripts.report_missing_data import FIELD_LABELS
from scripts.validate_national_panel import provisional_source_grade_error


class DataQualityTests(unittest.TestCase):
    def test_only_high_grade_sources_are_accepted(self):
        self.assertEqual(ACCEPTED_SOURCE_GRADES, {"A1", "A2", "B1", "B2"})
        for grade in ACCEPTED_SOURCE_GRADES:
            self.assertTrue(is_accepted_source_grade(grade))
        self.assertFalse(is_accepted_source_grade("C"))
        self.assertFalse(is_accepted_source_grade("D"))
        self.assertFalse(is_accepted_source_grade(None))

    def test_field_value_requires_matching_scope_and_year(self):
        accepted = assess_field_value(
            value="100.00",
            source_grade="A2",
            source_year=2025,
            metric_year=2025,
            source_geo_scope="prefecture_whole",
            metric_geo_scope="prefecture_whole",
        )
        self.assertEqual(accepted.status, "accepted")
        self.assertEqual(accepted.normalized_value, Decimal("100.00"))

        self.assertEqual(
            assess_field_value(
                value="100.00",
                source_grade="A2",
                source_year=2025,
                metric_year=2025,
                source_geo_scope="city_proper",
                metric_geo_scope="prefecture_whole",
            ).status,
            "blocked",
        )
        self.assertEqual(
            assess_field_value(
                value="100.00",
                source_grade="D",
                source_year=2025,
                metric_year=2025,
                source_geo_scope="prefecture_whole",
                metric_geo_scope="prefecture_whole",
            ).status,
            "provisional",
        )

    def test_fund_dependence_uses_combined_revenue_denominator(self):
        result = compute_derived_values(
            {
                "gov_fund_revenue_100m": "100.00",
                "general_public_revenue_100m": "300.00",
            }
        )

        self.assertEqual(result["fund_revenue_dependence_pct"], Decimal("25.00"))
        self.assertEqual(result["gov_fund_to_general_revenue_pct"], Decimal("33.33"))

    def test_derived_metric_blocks_non_positive_denominator(self):
        result = compute_derived_values(
            {
                "statutory_debt_balance_100m": "100.00",
                "gdp_current_100m": "-10.00",
                "general_public_revenue_100m": "-20.00",
                "general_public_expenditure_100m": "100.00",
                "gov_fund_revenue_100m": "10.00",
            }
        )

        self.assertIsNone(result["statutory_debt_to_gdp_pct"])
        self.assertIsNone(result["statutory_debt_to_revenue_pct"])
        self.assertIsNone(result["fund_revenue_dependence_pct"])

    def test_revenue_alias_matches_canonical_metric(self):
        result = compute_derived_values(
            {
                "statutory_debt_balance_100m": "100.00",
                "general_public_revenue_100m": "200.00",
            }
        )

        self.assertEqual(result["statutory_debt_to_revenue_pct"], Decimal("50.00"))
        self.assertEqual(result["statutory_debt_to_general_revenue_pct"], Decimal("50.00"))

    def test_provisional_rows_may_use_b2_but_must_declare_grade(self):
        self.assertIsNone(provisional_source_grade_error({"data_status": "provisional", "source_grade": "B2"}))
        self.assertIsNotNone(provisional_source_grade_error({"data_status": "provisional", "source_grade": ""}))

    def test_missing_report_includes_canonical_derived_fields(self):
        self.assertIn("debt_limit_utilization_pct", FIELD_LABELS)
        self.assertIn("statutory_debt_to_revenue_pct", FIELD_LABELS)
        self.assertIn("fund_revenue_dependence_pct", FIELD_LABELS)


if __name__ == "__main__":
    unittest.main()
