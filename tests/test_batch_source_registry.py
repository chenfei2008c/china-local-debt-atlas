import unittest

from scripts.batch_source_registry import (
    ACCEPTED_SOURCE_GRADES,
    CORE_RAW_FIELDS,
    build_batch_source_registry,
    build_core_coverage_report,
    normalize_batch_source,
)


class BatchSourceRegistryTests(unittest.TestCase):
    def test_normalize_batch_source_marks_only_high_grade_sources_as_final_eligible(self):
        normalized = normalize_batch_source(
            {
                "source_doc_id": "SRC-TEST-JS-FUND-2024",
                "province_name": "江苏省",
                "year": 2024,
                "source_grade": "A2",
                "document_type": "省级分地区财政表",
                "url": "https://example.test/js-2024.xlsx",
                "fields": ["gov_fund_revenue_100m", "general_public_revenue_100m"],
            }
        )

        self.assertEqual(normalized["year"], "2024")
        self.assertEqual(normalized["source_grade"], "A2")
        self.assertEqual(normalized["accepted_for_final"], "true")
        self.assertEqual(
            normalized["fields"],
            "general_public_revenue_100m;gov_fund_revenue_100m",
        )

        provisional = normalize_batch_source(
            {
                "source_doc_id": "SRC-TEST-SECONDARY-2024",
                "year": 2024,
                "source_grade": "D",
                "fields": ["gov_fund_revenue_100m"],
            }
        )
        self.assertEqual(provisional["accepted_for_final"], "false")
        self.assertEqual(ACCEPTED_SOURCE_GRADES, {"A1", "A2", "B1", "B2"})

    def test_registry_aggregates_multicity_field_lineage_as_one_batch(self):
        sources = [
            {
                "source_doc_id": "SRC-TEST-JS-FUND-2024",
                "publisher": "江苏省财政厅",
                "source_grade": "A2",
                "document_type": "省级分地区财政表",
                "source_url": "https://example.test/js-2024.xlsx",
                "publication_date": "2025-01-01",
            }
        ]
        lineage = [
            {
                "target_record_id": "MACRO-CN-320100-2024-PREFECTURE",
                "target_field": "gov_fund_revenue_100m",
                "source_doc_id": "SRC-TEST-JS-FUND-2024",
                "normalized_value": "100.00",
                "selected_flag": "true",
            },
            {
                "target_record_id": "MACRO-CN-320200-2024-PREFECTURE",
                "target_field": "general_public_revenue_100m",
                "source_doc_id": "SRC-TEST-JS-FUND-2024",
                "normalized_value": "200.00",
                "selected_flag": "true",
            },
        ]

        rows = build_batch_source_registry(sources, lineage)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["coverage_scope"], "multicity_batch")
        self.assertEqual(rows[0]["covered_city_count"], "2")
        self.assertEqual(rows[0]["covered_year_count"], "1")
        self.assertEqual(rows[0]["covered_core_value_count"], "2")
        self.assertEqual(
            rows[0]["covered_fields"],
            "general_public_revenue_100m;gov_fund_revenue_100m",
        )

    def test_coverage_report_separates_numeric_and_high_grade_coverage(self):
        macro_rows = [
            {
                "city_id": "CN-320100",
                "metric_year": "2024",
                "gov_fund_revenue_100m": "100.00",
                "general_public_revenue_100m": "300.00",
            },
            {
                "city_id": "CN-320200",
                "metric_year": "2024",
                "gov_fund_revenue_100m": "50.00",
                "general_public_revenue_100m": None,
            },
        ]
        sources = [
            {"source_doc_id": "SRC-A2", "source_grade": "A2"},
            {"source_doc_id": "SRC-D", "source_grade": "D"},
        ]
        lineage = [
            {
                "target_record_id": "MACRO-CN-320100-2024-PREFECTURE",
                "target_field": "gov_fund_revenue_100m",
                "source_doc_id": "SRC-A2",
                "normalized_value": "100.00",
                "selected_flag": "true",
            },
            {
                "target_record_id": "MACRO-CN-320200-2024-PREFECTURE",
                "target_field": "gov_fund_revenue_100m",
                "source_doc_id": "SRC-D",
                "normalized_value": "50.00",
                "selected_flag": "true",
            },
            {
                "target_record_id": "MACRO-CN-320100-2024-PREFECTURE",
                "target_field": "general_public_revenue_100m",
                "source_doc_id": "SRC-A2",
                "normalized_value": "300.00",
                "selected_flag": "true",
            },
        ]

        report = build_core_coverage_report(macro_rows, lineage, sources)
        fund = next(row for row in report if row["field_name"] == "gov_fund_revenue_100m")
        revenue = next(row for row in report if row["field_name"] == "general_public_revenue_100m")

        self.assertEqual(fund["target_rows"], "2")
        self.assertEqual(fund["numeric_non_null_rows"], "2")
        self.assertEqual(fund["high_grade_rows"], "1")
        self.assertEqual(fund["provisional_rows"], "1")
        self.assertEqual(fund["numeric_missing_rows"], "0")
        self.assertEqual(fund["high_grade_missing_rows"], "1")
        self.assertEqual(revenue["numeric_non_null_rows"], "1")
        self.assertEqual(revenue["numeric_missing_rows"], "1")

    def test_calculated_debt_totals_inherit_grade_from_accepted_components(self):
        macro_rows = [
            {
                "city_id": "CN-320100",
                "metric_year": "2024",
                "general_debt_limit_100m": "100.00",
                "special_debt_limit_100m": "200.00",
                "statutory_debt_limit_100m": "300.00",
            }
        ]
        sources = [{"source_doc_id": "SRC-A2", "source_grade": "A2"}]
        lineage = [
            {
                "target_record_id": "MACRO-CN-320100-2024-PREFECTURE",
                "target_field": "general_debt_limit_100m",
                "source_doc_id": "SRC-A2",
                "normalized_value": "100.00",
                "selected_flag": "true",
            },
            {
                "target_record_id": "MACRO-CN-320100-2024-PREFECTURE",
                "target_field": "special_debt_limit_100m",
                "source_doc_id": "SRC-A2",
                "normalized_value": "200.00",
                "selected_flag": "true",
            },
            {
                "target_record_id": "MACRO-CN-320100-2024-PREFECTURE",
                "target_field": "statutory_debt_limit_100m",
                "source_doc_id": "",
                "normalized_value": "300.00",
                "value_origin": "calculated",
                "calculation_id": "CAL-CN-320100-2024-statutory_debt_limit_100m",
                "selected_flag": "true",
            },
        ]

        report = build_core_coverage_report(macro_rows, lineage, sources)
        limit = next(row for row in report if row["field_name"] == "statutory_debt_limit_100m")

        self.assertEqual(limit["numeric_non_null_rows"], "1")
        self.assertEqual(limit["high_grade_rows"], "1")
        self.assertEqual(limit["high_grade_missing_rows"], "0")

    def test_core_field_list_contains_the_eight_raw_dependencies(self):
        self.assertEqual(
            set(CORE_RAW_FIELDS),
            {
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "resident_population_10k",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
                "statutory_debt_limit_100m",
                "statutory_debt_balance_100m",
            },
        )


if __name__ == "__main__":
    unittest.main()
