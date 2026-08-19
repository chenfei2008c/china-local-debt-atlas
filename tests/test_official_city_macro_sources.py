import unittest
from decimal import Decimal

from scripts.official_city_macro_sources import (
    parse_city_fund_revenue_text,
    parse_guangdong_city_budget_page,
    parse_guangdong_city_gdp_html,
)


class OfficialCityMacroSourceTests(unittest.TestCase):
    def test_parse_guangdong_city_gdp_table(self):
        html = """
        <table>
          <tr><th>地区</th><th>地区生产总值</th><th>第一产业</th><th>第二产业</th><th>第三产业</th><th>比上年增长</th></tr>
          <tr><td>广州市</td><td>32039.46</td><td>321.09</td><td>8350.00</td><td>23368.37</td><td>4.0</td></tr>
          <tr><td>深圳市</td><td>38731.80</td><td>20.00</td><td>15000.00</td><td>23711.80</td><td>5.5</td></tr>
        </table>
        """

        result = parse_guangdong_city_gdp_html(html)

        self.assertEqual(result["广州市"]["gdp_current_100m"], Decimal("32039.46"))
        self.assertEqual(result["广州市"]["gdp_real_growth_pct"], Decimal("4.0"))
        self.assertEqual(result["深圳市"]["gdp_current_100m"], Decimal("38731.80"))

    def test_ignore_non_city_rows_and_thousands_separators(self):
        html = """
        <table>
          <tr><td>全省</td><td>145,000.00</td><td>1</td><td>2</td><td>3</td><td>4.0</td></tr>
          <tr><td>珠海市</td><td>4,573.10</td><td>1</td><td>2</td><td>3</td><td>2.7%</td></tr>
        </table>
        """

        result = parse_guangdong_city_gdp_html(html)

        self.assertNotIn("全省", result)
        self.assertEqual(result["珠海市"]["gdp_current_100m"], Decimal("4573.10"))
        self.assertEqual(result["珠海市"]["gdp_real_growth_pct"], Decimal("2.7"))

    def test_parse_guangdong_city_budget_execution_page(self):
        page = """
        2025年全省各市一般公共预算收入执行情况表
        广 州 市 19,944,566 21,816,833 21,848,219 100.1% 103.1%
        深 圳 市 40,653,094 40,765,132 41,637,704 102.1% 106.4%
        珠三角核心区 94,670,350 99,436,220 100,184,244 100.8% 104.0%
        """

        result = parse_guangdong_city_budget_page(page, "general_public_revenue_100m")

        self.assertEqual(result["广州市"]["general_public_revenue_100m"], Decimal("2184.8219"))
        self.assertEqual(result["深圳市"]["general_public_revenue_100m"], Decimal("4163.7704"))
        self.assertNotIn("珠三角核心区", result)

    def test_parse_guangdong_city_budget_execution_expenditure(self):
        page = """
        2025年全省各市一般公共预算支出执行情况表
        广 州 市 27,882,116 28,789,239 28,015,394 97.3% 100.9%
        """

        result = parse_guangdong_city_budget_page(page, "general_public_expenditure_100m")

        self.assertEqual(result["广州市"]["general_public_expenditure_100m"], Decimal("2801.5394"))

    def test_parse_city_fund_revenue_from_official_report_text(self):
        text = "2025 年全市政府性基金预算收入 138.49 亿元，完成预算的 107.26%。"

        self.assertEqual(parse_city_fund_revenue_text(text), Decimal("138.49"))
        self.assertEqual(
            parse_city_fund_revenue_text("2025年，全市政府性基金预算收入667亿元。"),
            Decimal("667"),
        )
        self.assertEqual(
            parse_city_fund_revenue_text("2.政府性基金预算执行情况。全市政府性基金预算收入138.49亿元。"),
            Decimal("138.49"),
        )


if __name__ == "__main__":
    unittest.main()
