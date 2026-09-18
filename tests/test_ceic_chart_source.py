import unittest

from scripts.ceic_city_limit_fund import _chart_base


class CeicChartSourceTest(unittest.TestCase):
    def test_chart_base_preserves_ceic_query_parameters(self):
        page = '''
        <input class="chart-base-link" value="/datapage/charts/o_china_demo" />
        <img src="https://www.ceicdata.com/datapage/charts/o_china_demo/?type=area&from=2015-12-01&to=2025-12-01&lang=en" />
        '''

        self.assertEqual(
            _chart_base(page),
            "https://www.ceicdata.com/datapage/charts/o_china_demo/"
            "?type=area&from=2015-12-01&to=2025-12-01&lang=en",
        )
