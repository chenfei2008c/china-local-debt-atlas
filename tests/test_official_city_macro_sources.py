import unittest
from decimal import Decimal

from scripts.official_city_macro_sources import parse_guangdong_city_gdp_html


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


if __name__ == "__main__":
    unittest.main()
