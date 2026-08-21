import unittest
from decimal import Decimal

from scripts.batch_table_parser import parse_city_value_rows


class BatchTableParserTests(unittest.TestCase):
    def test_parses_multicity_fund_rows_and_converts_wan_yuan_to_yi_yuan(self):
        facts, rejects = parse_city_value_rows(
            [
                ["广 州 市", "12,345,600"],
                ["深圳市", "20,000,000"],
                ["全省", "99,999,999"],
            ],
            city_aliases={"广州市": "CN-440100", "深圳市": "CN-440300"},
            field_name="gov_fund_revenue_100m",
            value_index=1,
            raw_unit="万元",
            metric_year=2025,
            source_doc_id="SRC-GD-FUND-2025",
            source_grade="A2",
            geo_scope="prefecture_whole",
        )

        self.assertEqual(rejects[0]["reason_code"], "unmatched_city")
        self.assertEqual(len(facts), 2)
        self.assertEqual(facts[0]["city_id"], "CN-440100")
        self.assertEqual(facts[0]["normalized_value"], Decimal("1234.5600"))
        self.assertEqual(facts[1]["normalized_value"], Decimal("2000.0000"))
        self.assertEqual(facts[0]["metric_year"], "2025")

    def test_rejects_city_proper_rows_in_prefecture_whole_batch(self):
        facts, rejects = parse_city_value_rows(
            [["广州市", "100.00"]],
            city_aliases={"广州市": "CN-440100"},
            field_name="general_public_revenue_100m",
            value_index=1,
            raw_unit="亿元",
            metric_year=2024,
            source_doc_id="SRC-GD-REVENUE-2024",
            source_grade="A1",
            geo_scope="city_proper",
        )

        self.assertEqual(facts, [])
        self.assertEqual(rejects[0]["reason_code"], "scope_mismatch")
        self.assertEqual(rejects[0]["city_id"], "CN-440100")

    def test_rejects_invalid_year_and_unknown_field(self):
        with self.assertRaises(ValueError):
            parse_city_value_rows(
                [["广州市", "100"]],
                city_aliases={"广州市": "CN-440100"},
                field_name="not_a_core_field",
                value_index=1,
                raw_unit="亿元",
                metric_year=2025,
                source_doc_id="SRC-TEST",
                source_grade="A2",
                geo_scope="prefecture_whole",
            )

        with self.assertRaises(ValueError):
            parse_city_value_rows(
                [["广州市", "100"]],
                city_aliases={"广州市": "CN-440100"},
                field_name="gov_fund_revenue_100m",
                value_index=1,
                raw_unit="亿元",
                metric_year=2026,
                source_doc_id="SRC-TEST",
                source_grade="A2",
                geo_scope="prefecture_whole",
            )


if __name__ == "__main__":
    unittest.main()
