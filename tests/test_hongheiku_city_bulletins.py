import unittest
from decimal import Decimal

from scripts.hongheiku_city_bulletins import is_target_bulletin_title
from scripts.crei_city_bulletins import parse_bulletin_text


class HongheikuBulletinTests(unittest.TestCase):
    def test_title_matching_accepts_prefecture_but_rejects_county(self):
        self.assertTrue(is_target_bulletin_title("(河北省)保定市2025年国民经济和社会发展统计公报", "保定市"))
        self.assertTrue(is_target_bulletin_title("二〇二五年辽阳市国民经济和社会发展统计公报", "辽阳市"))
        self.assertTrue(is_target_bulletin_title("2025年巴州国民经济和社会发展统计公报", "巴音郭楞蒙古自治州"))
        self.assertTrue(is_target_bulletin_title("甘孜州二Ｏ二三年国民经济和社会发展主要统计数据公报", "甘孜藏族自治州", "2023"))
        self.assertTrue(is_target_bulletin_title("2024年保定市国民经济和社会发展统计公报", "保定市", "2024"))
        self.assertTrue(is_target_bulletin_title("2022年贵阳市国民经济和社会发展统计公报", "贵阳市", "2022"))
        self.assertTrue(is_target_bulletin_title("2021年铜陵市国民经济和社会发展统计公报", "铜陵市", "2021"))
        self.assertTrue(is_target_bulletin_title("2020年白城市国民经济和社会发展统计公报", "白城市", "2020"))
        self.assertFalse(is_target_bulletin_title("(保定市)蠡县2025年国民经济和社会发展统计公报", "保定市"))

    def test_page_normalization_keeps_exact_prefecture_values(self):
        parsed = parse_bulletin_text(
            "初步核算，2025年全市地区生产总值(GDP) 392.2亿元，按不变价计算，同比增长5.1%。"
            "全年一般公共预算收入 48.30 亿元，一般公共预算支出 126.40 亿元。"
        )
        self.assertEqual(parsed["gdp_current_100m"], Decimal("392.20"))
        self.assertEqual(parsed["gdp_real_growth_pct"], Decimal("5.10"))
        self.assertEqual(parsed["general_public_revenue_100m"], Decimal("48.30"))
        self.assertEqual(parsed["general_public_expenditure_100m"], Decimal("126.40"))
