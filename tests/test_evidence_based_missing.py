import unittest

from scripts.evidence_based_missing import (
    EVIDENCE_BY_KEY,
    EVIDENCE_SOURCE_DOCUMENTS,
)


class EvidenceBasedMissingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
