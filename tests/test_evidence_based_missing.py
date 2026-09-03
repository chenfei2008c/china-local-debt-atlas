import unittest

from scripts.evidence_based_missing import (
    EVIDENCE_BY_KEY,
    EVIDENCE_SOURCE_DOCUMENTS,
)


class EvidenceBasedMissingTests(unittest.TestCase):
    def test_sansha_search_record_covers_latest_targeted_review(self):
        source_id = "SRC-EVIDENCE-MISSING-SANSHA-SEARCH-2026"
        source = next(item for item in EVIDENCE_SOURCE_DOCUMENTS if item["source_doc_id"] == source_id)

        self.assertEqual(source["publication_date"], "2026-09-03")
        self.assertIn("统计公报", source["note"])
        self.assertIn("一般公共预算收入", source["note"])
        self.assertIn("财政收支", source["note"])
        self.assertIn("未取得可直接入表的年度全市数值", source["note"])

    def test_latest_xpcc_rating_followup_is_registered_without_creating_values(self):
        source_id = "SRC-EVIDENCE-MISSING-XPCC-FOLLOWUP-2025"
        source = next(item for item in EVIDENCE_SOURCE_DOCUMENTS if item["source_doc_id"] == source_id)

        self.assertEqual(source["publication_date"], "2025-12-23")
        self.assertIn("B029742-P83757-2025-C-GZ2025.pdf", source["source_url"])
        self.assertIn("2024或2025年全年", source["note"])

        for key in (
            ("CN-659000", "2024", "gdp_current_100m"),
            ("CN-659000", "2024", "gdp_real_growth_pct"),
            ("CN-659000", "2025", "gdp_current_100m"),
            ("CN-659000", "2025", "gdp_real_growth_pct"),
        ):
            self.assertIn(source_id, EVIDENCE_BY_KEY[key]["evidence_source_doc_ids"])

    def test_latest_xpcc_report_strengthens_post_2021_fiscal_missing_evidence(self):
        source_id = "SRC-EVIDENCE-MISSING-XPCC-TRANSPARENCY-2025"
        source = next(item for item in EVIDENCE_SOURCE_DOCUMENTS if item["source_doc_id"] == source_id)

        self.assertEqual(source["publication_date"], "2025-11-28")
        self.assertIn("33be9df3-8a08-4dcf-aaa7-f324e17e1137.pdf", source["source_url"])
        self.assertIn("自2021年起", source["note"])
        self.assertIn("上半年", source["note"])

        for key in (
            ("CN-659000", "2022", "general_public_revenue_100m"),
            ("CN-659000", "2025", "general_public_revenue_100m"),
            ("CN-659000", "2021", "general_public_expenditure_100m"),
            ("CN-659000", "2025", "general_public_expenditure_100m"),
        ):
            self.assertIn(source_id, EVIDENCE_BY_KEY[key]["evidence_source_doc_ids"])


if __name__ == "__main__":
    unittest.main()
