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

    def test_latest_xpcc_catalog_reviews_are_registered(self):
        finance_id = "SRC-EVIDENCE-MISSING-XPCC-FINANCE-CATALOG-2026"
        finance = next(item for item in EVIDENCE_SOURCE_DOCUMENTS if item["source_doc_id"] == finance_id)
        self.assertEqual(finance["publication_date"], "2026-09-03")
        self.assertIn("第1—10页逐页核验", finance["note"])
        self.assertIn("2021—2025", finance["note"])

        statistics_id = "SRC-EVIDENCE-MISSING-XPCC-STATISTICS-CATALOG-2026"
        statistics = next(item for item in EVIDENCE_SOURCE_DOCUMENTS if item["source_doc_id"] == statistics_id)
        self.assertEqual(statistics["publication_date"], "2026-09-03")
        self.assertIn("当前列表为空", statistics["note"])
        self.assertIn("2024或2025年", statistics["note"])

        for key in (
            ("CN-659000", "2024", "gdp_current_100m"),
            ("CN-659000", "2025", "gdp_current_100m"),
            ("CN-659000", "2022", "general_public_revenue_100m"),
            ("CN-659000", "2025", "general_public_expenditure_100m"),
        ):
            self.assertIn(
                statistics_id if key[2].startswith("gdp") else finance_id,
                EVIDENCE_BY_KEY[key]["evidence_source_doc_ids"],
            )

    def test_latest_year_end_reviews_are_registered_without_creating_values(self):
        xiongan_id = "SRC-EVIDENCE-MISSING-XIONGAN-2025-DECISION-REPORT"
        xiongan = next(item for item in EVIDENCE_SOURCE_DOCUMENTS if item["source_doc_id"] == xiongan_id)
        self.assertEqual(xiongan["publication_date"], "2026-08-10")
        self.assertIn("5页官方附件", xiongan["note"])
        self.assertIn("未披露2024或2025年新区全域GDP", xiongan["note"])

        xpcc_id = "SRC-EVIDENCE-MISSING-XPCC-YEAR-END-2025"
        xpcc = next(item for item in EVIDENCE_SOURCE_DOCUMENTS if item["source_doc_id"] == xpcc_id)
        self.assertEqual(xpcc["publication_date"], "2025-12-31")
        self.assertIn("前三季度", xpcc["note"])
        self.assertIn("未公开2025全年GDP", xpcc["note"])

        for key in (
            ("CN-133100", "2024", "gdp_real_growth_pct"),
            ("CN-133100", "2025", "gdp_current_100m"),
            ("CN-659000", "2024", "gdp_current_100m"),
            ("CN-659000", "2025", "gdp_real_growth_pct"),
        ):
            self.assertIn(
                xiongan_id if key[0] == "CN-133100" else xpcc_id,
                EVIDENCE_BY_KEY[key]["evidence_source_doc_ids"],
            )


if __name__ == "__main__":
    unittest.main()
