from decimal import Decimal
import unittest

from scripts.province_debt_sources import extract_official_debt_facts


class DebtBalanceGapBatchTests(unittest.TestCase):
    def test_2022_linyi_kaifeng_xuchang_citywide_balances_are_registered(self):
        city_master = [
            {
                "city_id": "CN-371300",
                "city_name_cn": "临沂市",
                "province_name": "山东省",
                "metric_year": 2022,
            },
            {
                "city_id": "CN-410200",
                "city_name_cn": "开封市",
                "province_name": "河南省",
                "metric_year": 2022,
            },
            {
                "city_id": "CN-411000",
                "city_name_cn": "许昌市",
                "province_name": "河南省",
                "metric_year": 2022,
            },
        ]

        facts, sources = extract_official_debt_facts(city_master)

        self.assertEqual(
            facts[("CN-371300", "2022")]["statutory_debt_balance_100m"],
            Decimal("1463.25"),
        )
        self.assertEqual(
            facts[("CN-410200", "2022")]["statutory_debt_balance_100m"],
            Decimal("623.6"),
        )
        self.assertEqual(
            facts[("CN-411000", "2022")]["statutory_debt_balance_100m"],
            Decimal("677.30"),
        )
        source_ids = {item["source_doc_id"] for item in sources}
        self.assertTrue(
            {
                "SRC-B2-DEBT-SHANDONG-LINYI-2022-BALANCE",
                "SRC-A2-DEBT-HENAN-KAIFENG-2022-BALANCE",
                "SRC-A2-DEBT-HENAN-XUCHANG-2022-BALANCE",
            }.issubset(source_ids)
        )


if __name__ == "__main__":
    unittest.main()
