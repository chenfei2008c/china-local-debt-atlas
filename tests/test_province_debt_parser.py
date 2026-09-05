import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import zipfile

from scripts.province_debt_parser import extract_city_rows, extract_xlsx_city_rows, merge_debt_rows, parse_numeric_tokens


class ProvinceDebtParserTests(unittest.TestCase):
    def test_parse_numeric_tokens_keeps_commas_and_dash_as_missing(self):
        self.assertEqual(
            parse_numeric_tokens("济南市 4,057.45 278.85 3,778.60 3,770.56 270.55 3,500.01"),
            [Decimal("4057.45"), Decimal("278.85"), Decimal("3778.60"), Decimal("3770.56"), Decimal("270.55"), Decimal("3500.01")],
        )
        self.assertEqual(parse_numeric_tokens("甲 12.5 — 8.2"), [Decimal("12.5"), None, Decimal("8.2")])

    def test_extracts_prefecture_whole_rows_and_skips_nested_rows(self):
        text = """
山东省 35720.60 8190.85 27529.75 32811.38 8058.09 24753.29
省本级 2590.10 1646.94 943.16 2507.09 1608.01 899.08
地市小计 33130.50 6543.91 26586.59 30304.29 6450.08 23854.21
 济南市 4057.45 278.85 3778.60 3770.56 270.55 3500.01
 市本级 2738.11 129.27 2608.84 2604.23 126.28 2477.95
 历下区 88.81 0.15 88.66 88.59 0.06 88.53
 青岛市 4725.95 1146.45 3579.50 4382.57 1145.59 3236.98
"""
        rows = extract_city_rows(
            text,
            expected_city_names={"济南市", "青岛市"},
            year=2024,
            province_name="山东省",
            source_doc_id="SRC-TEST",
            layout="total6",
        )
        self.assertEqual([row["city_name_cn"] for row in rows], ["济南市", "青岛市"])
        self.assertEqual(rows[0]["statutory_debt_balance_100m"], Decimal("3770.56"))
        self.assertEqual(rows[0]["general_debt_balance_100m"], Decimal("270.55"))
        self.assertEqual(rows[0]["special_debt_balance_100m"], Decimal("3500.01"))
        self.assertEqual(rows[0]["geo_scope"], "prefecture_whole")

    def test_extracts_component_only_rows_and_applies_unit_factor(self):
        text = "郑州市 16,361,277 16,140,957\n开封市 1,991,853 1,968,597\n"
        rows = extract_city_rows(
            text,
            expected_city_names={"郑州市", "开封市"},
            year=2024,
            province_name="河南省",
            source_doc_id="SRC-TEST-HENAN",
            layout="component2",
            component="general",
            unit_factor=Decimal("0.0001"),
        )
        self.assertEqual(rows[0]["general_debt_limit_100m"], Decimal("1636.1277"))
        self.assertEqual(rows[0]["general_debt_balance_100m"], Decimal("1614.0957"))
        self.assertIsNone(rows[0]["special_debt_balance_100m"])

    def test_official_components_override_lower_grade_total_and_recompute_sum(self):
        rows = [
            {
                "city_name_cn": "宜昌市",
                "province_name": "湖北省",
                "metric_year": "2024",
                "source_doc_id": "SRC-OFFICIAL-YICHANG",
                "source_grade": "A1",
                "general_debt_limit_100m": Decimal("158.7938"),
                "general_debt_balance_100m": Decimal("149.9815"),
                "special_debt_limit_100m": None,
                "special_debt_balance_100m": None,
                "statutory_debt_limit_100m": None,
                "statutory_debt_balance_100m": None,
                "evidence_excerpt": "一般债务",
            },
            {
                "city_name_cn": "宜昌市",
                "province_name": "湖北省",
                "metric_year": "2024",
                "source_doc_id": "SRC-OFFICIAL-YICHANG",
                "source_grade": "A1",
                "general_debt_limit_100m": None,
                "general_debt_balance_100m": None,
                "special_debt_limit_100m": Decimal("810.7920"),
                "special_debt_balance_100m": Decimal("748.5077"),
                "statutory_debt_limit_100m": None,
                "statutory_debt_balance_100m": None,
                "evidence_excerpt": "专项债务",
            },
            {
                "city_name_cn": "宜昌市",
                "province_name": "湖北省",
                "metric_year": "2024",
                "source_doc_id": "SRC-SECONDARY-YICHANG",
                "source_grade": "D",
                "general_debt_limit_100m": None,
                "general_debt_balance_100m": None,
                "special_debt_limit_100m": None,
                "special_debt_balance_100m": None,
                "statutory_debt_limit_100m": None,
                "statutory_debt_balance_100m": Decimal("1214.8177"),
                "evidence_excerpt": "低等级总额线索",
            },
        ]
        merged = merge_debt_rows(rows)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["statutory_debt_limit_100m"], Decimal("969.5858"))
        self.assertEqual(merged[0]["statutory_debt_balance_100m"], Decimal("898.4892"))

    def test_extracts_mixed_general_special_balance_rows(self):
        text = "哈尔滨市 16409355 17948198 17918648 12585443 14697083 14614159"
        rows = extract_city_rows(
            text,
            expected_city_names={"哈尔滨市"},
            year=2023,
            province_name="黑龙江省",
            source_doc_id="SRC-TEST-HLJ",
            layout="balance6",
            unit_factor=Decimal("0.0001"),
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["general_debt_limit_100m"], Decimal("1794.8198"))
        self.assertEqual(row["general_debt_balance_100m"], Decimal("1791.8648"))
        self.assertEqual(row["special_debt_limit_100m"], Decimal("1469.7083"))
        self.assertEqual(row["special_debt_balance_100m"], Decimal("1461.4159"))

    def test_extracts_previous_year_balances_without_mislabeling_next_year_limits(self):
        text = "哈尔滨市 13558354 15153384 14882258"
        rows = extract_city_rows(
            text,
            expected_city_names={"哈尔滨市"},
            year=2019,
            province_name="黑龙江省",
            source_doc_id="SRC-TEST-HLJ-PRIOR",
            layout="component3_previous_balance",
            component="general",
            unit_factor=Decimal("0.0001"),
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["general_debt_balance_100m"], Decimal("1355.8354"))
        self.assertIsNone(rows[0]["general_debt_limit_100m"])

    def test_extracts_direct_general_special_rows_after_year(self):
        text = "怒江州 2025 200.09 113.50 86.59"
        rows = extract_city_rows(
            text,
            expected_city_names={"怒江州"},
            year=2025,
            province_name="云南省",
            source_doc_id="SRC-TEST-NUJIANG",
            layout="direct3_general_special_after_year",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["statutory_debt_balance_100m"], Decimal("200.09"))
        self.assertEqual(rows[0]["general_debt_balance_100m"], Decimal("113.50"))
        self.assertEqual(rows[0]["special_debt_balance_100m"], Decimal("86.59"))

    def test_extracts_city_rows_from_shared_string_xlsx(self):
        sheet = """<?xml version='1.0'?><worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><sheetData>
        <row r='10'><c r='C10' t='s'><v>0</v></c><c r='D10'><v>100</v></c><c r='E10'><v>40</v></c><c r='F10'><v>60</v></c><c r='G10'><v>90</v></c><c r='H10'><v>35</v></c><c r='I10'><v>55</v></c></row>
        <row r='11'><c r='C11' t='inlineStr'><is><t>市本级</t></is></c><c r='D11'><v>10</v></c><c r='E11'><v>4</v></c><c r='F11'><v>6</v></c><c r='G11'><v>9</v></c><c r='H11'><v>3</v></c><c r='I11'><v>6</v></c></row>
        </sheetData></worksheet>"""
        shared = """<?xml version='1.0'?><sst xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><si><t>测试市</t></si></sst>"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sample.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("xl/sharedStrings.xml", shared)
                archive.writestr("xl/worksheets/sheet1.xml", sheet)
            rows = extract_xlsx_city_rows(
                path,
                {"测试市"},
                2024,
                "测试省",
                "SRC-TEST-XLSX",
                unit_factor=Decimal("0.0001"),
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["city_name_cn"], "测试市")
        self.assertEqual(rows[0]["statutory_debt_balance_100m"], Decimal("0.009"))

    def test_extracts_total9_rows_from_xlsx_without_using_new_limit_as_limit(self):
        cell_parts = ["<c r='C10' t='inlineStr'><is><t>测试九列市</t></is></c>"]
        for column, value in zip("DEFGHIJKL", [100, 40, 60, 8, 2, 6, 90, 35, 55]):
            cell_parts.append(f"<c r='{column}10'><v>{value}</v></c>")
        cells = "".join(cell_parts)
        sheet = f"<?xml version='1.0'?><worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><sheetData><row r='10'>{cells}</row></sheetData></worksheet>"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sample-total9.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("xl/worksheets/sheet1.xml", sheet)
            rows = extract_xlsx_city_rows(
                path,
                {"测试九列市"},
                2022,
                "测试省",
                "SRC-TEST-XLSX-TOTAL9",
                value_columns=tuple("DEFGHIJKL"),
                layout="total9",
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["statutory_debt_limit_100m"], Decimal("100"))
        self.assertEqual(rows[0]["general_debt_limit_100m"], Decimal("40"))
        self.assertEqual(rows[0]["special_debt_limit_100m"], Decimal("60"))
        self.assertEqual(rows[0]["statutory_debt_balance_100m"], Decimal("90"))

    def test_extracts_total9_rows_with_balance_group_at_end(self):
        text = "乌鲁木齐市 1653.99 512.96 1141.03 136.99 3.00 133.99 1532.18 441.17 1091.01"
        rows = extract_city_rows(
            text,
            expected_city_names={"乌鲁木齐市"},
            year=2023,
            province_name="新疆维吾尔自治区",
            source_doc_id="SRC-TEST-XJ-2023",
            layout="total9",
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["statutory_debt_limit_100m"], Decimal("1653.99"))
        self.assertEqual(row["general_debt_limit_100m"], Decimal("512.96"))
        self.assertEqual(row["special_debt_limit_100m"], Decimal("1141.03"))
        self.assertEqual(row["statutory_debt_balance_100m"], Decimal("1532.18"))
        self.assertEqual(row["general_debt_balance_100m"], Decimal("441.17"))
        self.assertEqual(row["special_debt_balance_100m"], Decimal("1091.01"))

    def test_extracts_direct_limit_new_limit_and_balance_rows(self):
        text = "乌鲁木齐市 16316900 3783000 15888995"
        rows = extract_city_rows(
            text,
            expected_city_names={"乌鲁木齐市"},
            year=2024,
            province_name="新疆维吾尔自治区",
            source_doc_id="SRC-TEST-XJ-DIRECT3",
            layout="direct3_component_limit_new_balance",
            component="special",
            unit_factor=Decimal("0.0001"),
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["special_debt_limit_100m"], Decimal("1631.6900"))
        self.assertEqual(rows[0]["special_debt_balance_100m"], Decimal("1588.8995"))
        self.assertIsNone(rows[0]["statutory_debt_limit_100m"])

    def test_tibet_2024_city_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-CITY-DEBT-TIBET-SHANNAN-2024", source_ids)
        self.assertIn("SRC-CITY-DEBT-TIBET-ALI-2024", source_ids)

        city_master = [
            {"city_id": "CN-540500", "province_name": "西藏自治区", "city_name_cn": "山南市", "metric_year": 2024},
            {"city_id": "CN-542500", "province_name": "西藏自治区", "city_name_cn": "阿里地区", "metric_year": 2024},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-540500", "2024")]["statutory_debt_balance_100m"], Decimal("83.71"))
        self.assertEqual(facts[("CN-542500", "2024")]["statutory_debt_balance_100m"], Decimal("54.6774"))

        xizang_city_master = [
            {"city_id": "CN-540200", "province_name": "西藏自治区", "city_name_cn": "日喀则市", "metric_year": 2024},
            {"city_id": "CN-540400", "province_name": "西藏自治区", "city_name_cn": "林芝市", "metric_year": 2024},
            {"city_id": "CN-540600", "province_name": "西藏自治区", "city_name_cn": "那曲市", "metric_year": 2024},
        ]
        xizang_facts, _ = extract_official_debt_facts(xizang_city_master)
        self.assertEqual(xizang_facts[("CN-540200", "2024")]["statutory_debt_balance_100m"], Decimal("117.35"))
        self.assertEqual(xizang_facts[("CN-540400", "2024")]["statutory_debt_balance_100m"], Decimal("55.23"))
        self.assertEqual(xizang_facts[("CN-540600", "2024")]["statutory_debt_balance_100m"], Decimal("120.53"))

        xiongan_city_master = [
            {"city_id": "CN-133100", "province_name": "河北省", "city_name_cn": "雄安新区", "metric_year": 2024},
        ]
        xiongan_facts, _ = extract_official_debt_facts(xiongan_city_master)
        self.assertEqual(xiongan_facts[("CN-133100", "2024")]["statutory_debt_balance_100m"], Decimal("2625.21"))

    def test_xinjiang_2024_batch_source_covers_fund_and_debt(self):
        from scripts.collect_national_panel import load_xinjiang_2024_city_fund_sources
        from scripts.province_debt_sources import extract_official_debt_facts

        fund_values, fund_sources = load_xinjiang_2024_city_fund_sources()
        self.assertEqual(len(fund_values), 14)
        self.assertEqual(len(fund_sources), 1)
        self.assertEqual(fund_values[("CN-650100", "2024")]["gov_fund_revenue_100m"], Decimal("92.28"))
        self.assertEqual(fund_values[("CN-653200", "2024")]["gov_fund_revenue_100m"], Decimal("13.96"))
        self.assertEqual({item["source_grade"] for item in fund_sources}, {"A1"})

        city_master = [
            {"city_id": "CN-650100", "province_name": "新疆维吾尔自治区", "city_name_cn": "乌鲁木齐市", "metric_year": 2024},
            {"city_id": "CN-653200", "province_name": "新疆维吾尔自治区", "city_name_cn": "和田地区", "metric_year": 2024},
        ]
        debt_values, debt_sources = extract_official_debt_facts(city_master)
        self.assertEqual(debt_values[("CN-650100", "2024")]["special_debt_limit_100m"], Decimal("1631.6900"))
        self.assertEqual(debt_values[("CN-650100", "2024")]["special_debt_balance_100m"], Decimal("1588.8995"))
        self.assertEqual(debt_values[("CN-653200", "2024")]["special_debt_balance_100m"], Decimal("376.2400"))
        self.assertTrue(any(item["source_doc_id"] == "SRC-PROVINCE-DEBT-XINJIANG-2024" for item in debt_sources))

        jinchang_city_master = [
            {"city_id": "CN-620300", "province_name": "甘肃省", "city_name_cn": "金昌市", "metric_year": 2024},
        ]
        jinchang_facts, _ = extract_official_debt_facts(jinchang_city_master)
        self.assertEqual(jinchang_facts[("CN-620300", "2024")]["statutory_debt_balance_100m"], Decimal("128.28"))

        inner_mongolia_city_master = [
            {"city_id": "CN-150600", "province_name": "内蒙古自治区", "city_name_cn": "鄂尔多斯市", "metric_year": 2025},
            {"city_id": "CN-150200", "province_name": "内蒙古自治区", "city_name_cn": "包头市", "metric_year": 2025},
            {"city_id": "CN-150700", "province_name": "内蒙古自治区", "city_name_cn": "呼伦贝尔市", "metric_year": 2025},
            {"city_id": "CN-150900", "province_name": "内蒙古自治区", "city_name_cn": "乌兰察布市", "metric_year": 2025},
            {"city_id": "CN-152900", "province_name": "内蒙古自治区", "city_name_cn": "阿拉善盟", "metric_year": 2025},
        ]
        inner_mongolia_facts, _ = extract_official_debt_facts(inner_mongolia_city_master)
        self.assertEqual(inner_mongolia_facts[("CN-150600", "2025")]["statutory_debt_balance_100m"], Decimal("1823.50"))
        self.assertEqual(inner_mongolia_facts[("CN-150200", "2025")]["statutory_debt_balance_100m"], Decimal("1158.20"))
        self.assertEqual(inner_mongolia_facts[("CN-150700", "2025")]["statutory_debt_balance_100m"], Decimal("630.80"))
        self.assertEqual(inner_mongolia_facts[("CN-150900", "2025")]["statutory_debt_balance_100m"], Decimal("835.90"))
        self.assertEqual(inner_mongolia_facts[("CN-152900", "2025")]["statutory_debt_balance_100m"], Decimal("280.40"))

    def test_fujian_2020_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-FUJIAN-CITIES-2020", source_ids)
        city_master = [
            {"city_id": "CN-350100", "province_name": "福建省", "city_name_cn": "福州市", "metric_year": 2020},
            {"city_id": "CN-350200", "province_name": "福建省", "city_name_cn": "厦门市", "metric_year": 2020},
            {"city_id": "CN-350700", "province_name": "福建省", "city_name_cn": "南平市", "metric_year": 2020},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-350100", "2020")]["statutory_debt_balance_100m"], Decimal("1302.3560384832"))
        self.assertEqual(facts[("CN-350200", "2020")]["statutory_debt_balance_100m"], Decimal("1112.113673"))
        self.assertEqual(facts[("CN-350700", "2020")]["statutory_debt_balance_100m"], Decimal("494.36"))

    def test_fujian_2018_2019_official_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-FUJIAN-CITIES-2018", source_ids)
        self.assertIn("SRC-OFFICIAL-DEBT-FUJIAN-CITIES-2019", source_ids)
        city_master = [
            {"city_id": "CN-350100", "province_name": "福建省", "city_name_cn": "福州市", "metric_year": 2018},
            {"city_id": "CN-350300", "province_name": "福建省", "city_name_cn": "莆田市", "metric_year": 2018},
            {"city_id": "CN-350100", "province_name": "福建省", "city_name_cn": "福州市", "metric_year": 2019},
            {"city_id": "CN-350300", "province_name": "福建省", "city_name_cn": "莆田市", "metric_year": 2019},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-350100", "2018")]["statutory_debt_balance_100m"], Decimal("858.94"))
        self.assertEqual(facts[("CN-350300", "2018")]["statutory_debt_balance_100m"], Decimal("482.86"))
        self.assertEqual(facts[("CN-350100", "2019")]["statutory_debt_balance_100m"], Decimal("1086.5008195589"))
        self.assertEqual(facts[("CN-350300", "2019")]["statutory_debt_balance_100m"], Decimal("518.148546"))

    def test_shaanxi_2018_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-SHAANXI-CITIES-2018", source_ids)
        city_master = [
            {"city_id": "CN-610100", "province_name": "陕西省", "city_name_cn": "西安市", "metric_year": 2018},
            {"city_id": "CN-610300", "province_name": "陕西省", "city_name_cn": "宝鸡市", "metric_year": 2018},
            {"city_id": "CN-610700", "province_name": "陕西省", "city_name_cn": "汉中市", "metric_year": 2018},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-610100", "2018")]["statutory_debt_balance_100m"], Decimal("1965"))
        self.assertEqual(facts[("CN-610300", "2018")]["statutory_debt_balance_100m"], Decimal("180"))
        self.assertEqual(facts[("CN-610700", "2018")]["statutory_debt_balance_100m"], Decimal("205"))

    def test_shaanxi_2021_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-SHAANXI-CITIES-2021", source_ids)
        city_master = [
            {"city_id": "CN-610100", "province_name": "陕西省", "city_name_cn": "西安市", "metric_year": 2021},
            {"city_id": "CN-610300", "province_name": "陕西省", "city_name_cn": "宝鸡市", "metric_year": 2021},
            {"city_id": "CN-610700", "province_name": "陕西省", "city_name_cn": "汉中市", "metric_year": 2021},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-610100", "2021")]["statutory_debt_balance_100m"], Decimal("3230.92"))
        self.assertEqual(facts[("CN-610100", "2021")]["general_debt_balance_100m"], Decimal("979.49"))
        self.assertEqual(facts[("CN-610100", "2021")]["special_debt_balance_100m"], Decimal("2251.43"))
        self.assertEqual(facts[("CN-610300", "2021")]["statutory_debt_balance_100m"], Decimal("303.37"))
        self.assertEqual(facts[("CN-610700", "2021")]["statutory_debt_balance_100m"], Decimal("372.73"))

    def test_shaanxi_2019_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-SHAANXI-CITIES-2019", source_ids)
        city_master = [
            {"city_id": "CN-610100", "province_name": "陕西省", "city_name_cn": "西安市", "metric_year": 2019},
            {"city_id": "CN-610300", "province_name": "陕西省", "city_name_cn": "宝鸡市", "metric_year": 2019},
            {"city_id": "CN-610700", "province_name": "陕西省", "city_name_cn": "汉中市", "metric_year": 2019},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-610100", "2019")]["statutory_debt_balance_100m"], Decimal("2647.59"))
        self.assertEqual(facts[("CN-610100", "2019")]["general_debt_balance_100m"], Decimal("899.65"))
        self.assertEqual(facts[("CN-610100", "2019")]["special_debt_balance_100m"], Decimal("1747.94"))
        self.assertEqual(facts[("CN-610300", "2019")]["statutory_debt_balance_100m"], Decimal("206.77"))
        self.assertEqual(facts[("CN-610700", "2019")]["statutory_debt_balance_100m"], Decimal("266.30"))

    def test_shanxi_jinzhong_2022_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-SECONDARY-DEBT-SHANXI-JINZHONG-2022", source_ids)
        city_master = [
            {"city_id": "CN-140700", "province_name": "山西省", "city_name_cn": "晋中市", "metric_year": 2022},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-140700", "2022")]["statutory_debt_balance_100m"], Decimal("514.8808"))
        self.assertEqual(facts[("CN-140700", "2022")]["general_debt_balance_100m"], Decimal("254.2280"))
        self.assertEqual(facts[("CN-140700", "2022")]["special_debt_balance_100m"], Decimal("256.5535"))

    def test_shanxi_taiyuan_2022_secondary_total_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-SECONDARY-DEBT-SHANXI-TAIYUAN-2022", source_ids)
        city_master = [
            {"city_id": "CN-140100", "province_name": "山西省", "city_name_cn": "太原市", "metric_year": 2022},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-140100", "2022")]["statutory_debt_balance_100m"], Decimal("983.15"))
        self.assertIsNone(facts[("CN-140100", "2022")]["general_debt_balance_100m"])
        self.assertIsNone(facts[("CN-140100", "2022")]["special_debt_balance_100m"])

    def test_shanxi_yangquan_2023_official_whole_city_total_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-SHANXI-YANGQUAN-2023", source_ids)
        city_master = [
            {"city_id": "CN-140300", "province_name": "山西省", "city_name_cn": "阳泉市", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-140300", "2023")]["statutory_debt_balance_100m"], Decimal("313.70"))
        self.assertIsNone(facts[("CN-140300", "2023")]["general_debt_balance_100m"])
        self.assertIsNone(facts[("CN-140300", "2023")]["special_debt_balance_100m"])

    def test_shanxi_datong_linfen_2022_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-SHANXI-DATONG-2022", source_ids)
        self.assertIn("SRC-SECONDARY-DEBT-SHANXI-LINFEN-2022", source_ids)
        city_master = [
            {"city_id": "CN-140200", "province_name": "山西省", "city_name_cn": "大同市", "metric_year": 2022},
            {"city_id": "CN-141000", "province_name": "山西省", "city_name_cn": "临汾市", "metric_year": 2022},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-140200", "2022")]["statutory_debt_balance_100m"], Decimal("507.23"))
        self.assertEqual(facts[("CN-141000", "2022")]["statutory_debt_balance_100m"], Decimal("506.09"))

    def test_liaoning_2021_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-LIAONING-CITIES-2021", source_ids)
        self.assertIn("SRC-OFFICIAL-DEBT-LIAONING-CITIES-2023", source_ids)
        city_master = [
            {"city_id": "CN-210100", "province_name": "辽宁省", "city_name_cn": "沈阳市", "metric_year": 2021},
            {"city_id": "CN-210200", "province_name": "辽宁省", "city_name_cn": "大连市", "metric_year": 2021},
            {"city_id": "CN-211400", "province_name": "辽宁省", "city_name_cn": "葫芦岛市", "metric_year": 2021},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-210100", "2021")]["statutory_debt_balance_100m"], Decimal("1801.88"))
        self.assertEqual(facts[("CN-210100", "2021")]["general_debt_balance_100m"], Decimal("965.07"))
        # 大连已有中央平台 A2 精确值；新省财政厅附件值作为同键交叉证据并入 evidence_excerpt。
        self.assertEqual(facts[("CN-210200", "2021")]["statutory_debt_balance_100m"], Decimal("2369.4981322671"))
        self.assertIn("大连市 2369.50 1512.25 857.25", facts[("CN-210200", "2021")]["evidence_excerpt"])
        self.assertEqual(facts[("CN-211400", "2021")]["statutory_debt_balance_100m"], Decimal("405.04"))

        city_master_2023 = [
            {"city_id": "CN-210100", "province_name": "辽宁省", "city_name_cn": "沈阳市", "metric_year": 2023},
            {"city_id": "CN-210200", "province_name": "辽宁省", "city_name_cn": "大连市", "metric_year": 2023},
            {"city_id": "CN-211400", "province_name": "辽宁省", "city_name_cn": "葫芦岛市", "metric_year": 2023},
        ]
        facts_2023, _ = extract_official_debt_facts(city_master_2023)
        self.assertEqual(facts_2023[("CN-210100", "2023")]["statutory_debt_balance_100m"], Decimal("2275.253370"))
        # 大连已有中央平台精确值；省财政厅附件的四舍五入/原始精度值保留为交叉证据。
        self.assertEqual(facts_2023[("CN-210200", "2023")]["statutory_debt_balance_100m"], Decimal("2897.6301498859"))
        self.assertIn("大连市 2897.630150 1659.179058 1238.451092", facts_2023[("CN-210200", "2023")]["evidence_excerpt"])
        self.assertEqual(facts_2023[("CN-211400", "2023")]["statutory_debt_balance_100m"], Decimal("546.367910"))

    def test_liaoning_2022_and_2023_official_city_tables_fill_limit_columns(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-LIAONING-CITIES-2022-TOTAL6", source_ids)
        self.assertIn("SRC-OFFICIAL-DEBT-LIAONING-CITIES-2023-TOTAL6", source_ids)
        city_master = [
            {"city_id": "CN-210100", "province_name": "辽宁省", "city_name_cn": "沈阳市", "metric_year": 2022},
            {"city_id": "CN-211400", "province_name": "辽宁省", "city_name_cn": "葫芦岛市", "metric_year": 2022},
            {"city_id": "CN-210100", "province_name": "辽宁省", "city_name_cn": "沈阳市", "metric_year": 2023},
            {"city_id": "CN-211400", "province_name": "辽宁省", "city_name_cn": "葫芦岛市", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-210100", "2022")]["statutory_debt_limit_100m"], Decimal("2077.79"))
        self.assertEqual(facts[("CN-210100", "2022")]["general_debt_limit_100m"], Decimal("1057.97"))
        self.assertEqual(facts[("CN-210100", "2022")]["statutory_debt_balance_100m"], Decimal("1907.80"))
        self.assertEqual(facts[("CN-211400", "2023")]["statutory_debt_limit_100m"], Decimal("546.92"))
        self.assertEqual(facts[("CN-211400", "2023")]["special_debt_balance_100m"], Decimal("144.969145"))

    def test_zhangye_2023_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-GANSU-ZHANGYE-2023", source_ids)
        city_master = [
            {"city_id": "CN-620700", "province_name": "甘肃省", "city_name_cn": "张掖市", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-620700", "2023")]["statutory_debt_balance_100m"], Decimal("309.56"))
        self.assertEqual(facts[("CN-620700", "2023")]["general_debt_balance_100m"], Decimal("85.26"))
        self.assertEqual(facts[("CN-620700", "2023")]["special_debt_balance_100m"], Decimal("224.30"))

    def test_qingyang_2023_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-GANSU-QINGYANG-2023", source_ids)
        city_master = [
            {"city_id": "CN-621000", "province_name": "甘肃省", "city_name_cn": "庆阳市", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-621000", "2023")]["statutory_debt_balance_100m"], Decimal("407.68"))
        self.assertEqual(facts[("CN-621000", "2023")]["general_debt_balance_100m"], Decimal("159.28"))
        self.assertEqual(facts[("CN-621000", "2023")]["special_debt_balance_100m"], Decimal("248.41"))

    def test_anhui_2023_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        for city_key in ("HUANGSHAN", "LIUAN", "FUYANG", "CHUZHOU"):
            self.assertIn(f"SRC-SECONDARY-DEBT-ANHUI-{city_key}-2023", source_ids)
        city_master = [
            {"city_id": "CN-341000", "province_name": "安徽省", "city_name_cn": "黄山市", "metric_year": 2023},
            {"city_id": "CN-341500", "province_name": "安徽省", "city_name_cn": "六安市", "metric_year": 2023},
            {"city_id": "CN-341200", "province_name": "安徽省", "city_name_cn": "阜阳市", "metric_year": 2023},
            {"city_id": "CN-341100", "province_name": "安徽省", "city_name_cn": "滁州市", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-341000", "2023")]["statutory_debt_balance_100m"], Decimal("442.87"))
        self.assertEqual(facts[("CN-341500", "2023")]["statutory_debt_balance_100m"], Decimal("1089.91"))
        self.assertEqual(facts[("CN-341200", "2023")]["statutory_debt_balance_100m"], Decimal("1517.76"))
        self.assertEqual(facts[("CN-341100", "2023")]["statutory_debt_balance_100m"], Decimal("1289.80"))

    def test_xinjiang_2020_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-XINJIANG-URUMQI-2020", source_ids)
        self.assertIn("SRC-OFFICIAL-DEBT-XINJIANG-KARAMAY-2020", source_ids)
        city_master = [
            {"city_id": "CN-650100", "province_name": "新疆维吾尔自治区", "city_name_cn": "乌鲁木齐市", "metric_year": 2020},
            {"city_id": "CN-650200", "province_name": "新疆维吾尔自治区", "city_name_cn": "克拉玛依市", "metric_year": 2020},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-650100", "2020")]["statutory_debt_balance_100m"], Decimal("1188.94"))
        self.assertEqual(facts[("CN-650100", "2020")]["general_debt_balance_100m"], Decimal("405.54"))
        self.assertEqual(facts[("CN-650100", "2020")]["special_debt_balance_100m"], Decimal("783.40"))
        self.assertEqual(facts[("CN-650200", "2020")]["statutory_debt_balance_100m"], Decimal("228.34"))
        self.assertEqual(facts[("CN-650200", "2020")]["general_debt_balance_100m"], Decimal("161.84"))
        self.assertEqual(facts[("CN-650200", "2020")]["special_debt_balance_100m"], Decimal("66.50"))

    def test_xinjiang_2020_additional_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        for source_id in (
            "SRC-OFFICIAL-DEBT-XINJIANG-TURPAN-2020",
            "SRC-OFFICIAL-DEBT-XINJIANG-BAYINGOLIN-2020",
            "SRC-SECONDARY-DEBT-XINJIANG-AKSU-2020",
            "SRC-SECONDARY-DEBT-XINJIANG-CHANGJI-2020",
            "SRC-SECONDARY-DEBT-XINJIANG-BORTALA-2020",
        ):
            self.assertIn(source_id, source_ids)
        city_master = [
            {"city_id": "CN-650400", "province_name": "新疆维吾尔自治区", "city_name_cn": "吐鲁番市", "metric_year": 2020},
            {"city_id": "CN-652800", "province_name": "新疆维吾尔自治区", "city_name_cn": "巴音郭楞蒙古自治州", "metric_year": 2020},
            {"city_id": "CN-652900", "province_name": "新疆维吾尔自治区", "city_name_cn": "阿克苏地区", "metric_year": 2020},
            {"city_id": "CN-652300", "province_name": "新疆维吾尔自治区", "city_name_cn": "昌吉回族自治州", "metric_year": 2020},
            {"city_id": "CN-652700", "province_name": "新疆维吾尔自治区", "city_name_cn": "博尔塔拉蒙古自治州", "metric_year": 2020},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-650400", "2020")]["statutory_debt_balance_100m"], Decimal("155.1"))
        self.assertEqual(facts[("CN-650400", "2020")]["general_debt_balance_100m"], Decimal("70.11"))
        self.assertEqual(facts[("CN-652800", "2020")]["statutory_debt_balance_100m"], Decimal("335.54"))
        self.assertEqual(facts[("CN-652800", "2020")]["special_debt_balance_100m"], Decimal("177.58"))
        self.assertEqual(facts[("CN-652900", "2020")]["statutory_debt_balance_100m"], Decimal("310.55"))
        self.assertEqual(facts[("CN-652900", "2020")]["general_debt_balance_100m"], Decimal("195.65"))
        self.assertEqual(facts[("CN-652300", "2020")]["statutory_debt_balance_100m"], Decimal("344.80"))
        self.assertEqual(facts[("CN-652300", "2020")]["special_debt_balance_100m"], Decimal("162.12"))
        self.assertEqual(facts[("CN-652700", "2020")]["statutory_debt_balance_100m"], Decimal("200.84"))

    def test_xinjiang_2020_kashgar_kizilsu_ili_official_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        for source_id in (
            "SRC-OFFICIAL-DEBT-XINJIANG-KASHGAR-2020",
            "SRC-OFFICIAL-DEBT-XINJIANG-KIZILSU-2020",
            "SRC-OFFICIAL-DEBT-XINJIANG-ILI-2020",
        ):
            self.assertIn(source_id, source_ids)
        city_master = [
            {"city_id": "CN-653000", "province_name": "新疆维吾尔自治区", "city_name_cn": "克孜勒苏柯尔克孜自治州", "metric_year": 2020},
            {"city_id": "CN-653100", "province_name": "新疆维吾尔自治区", "city_name_cn": "喀什地区", "metric_year": 2020},
            {"city_id": "CN-654000", "province_name": "新疆维吾尔自治区", "city_name_cn": "伊犁哈萨克自治州", "metric_year": 2020},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-653000", "2020")]["statutory_debt_balance_100m"], Decimal("131.55"))
        self.assertIsNone(facts[("CN-653000", "2020")]["general_debt_balance_100m"])
        self.assertEqual(facts[("CN-653100", "2020")]["statutory_debt_balance_100m"], Decimal("319.95"))
        self.assertEqual(facts[("CN-653100", "2020")]["general_debt_balance_100m"], Decimal("228.9267519935"))
        self.assertEqual(facts[("CN-653100", "2020")]["special_debt_balance_100m"], Decimal("91.017"))
        self.assertEqual(facts[("CN-654000", "2020")]["statutory_debt_balance_100m"], Decimal("358.93"))
        self.assertEqual(facts[("CN-654000", "2020")]["general_debt_balance_100m"], Decimal("206.30"))
        self.assertEqual(facts[("CN-654000", "2020")]["special_debt_balance_100m"], Decimal("152.63"))

    def test_xinjiang_2020_hetian_tacheng_secondary_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-SECONDARY-DEBT-XINJIANG-HOTAN-2020", source_ids)
        self.assertIn("SRC-SECONDARY-DEBT-XINJIANG-TACHENG-2020", source_ids)
        city_master = [
            {"city_id": "CN-653200", "province_name": "新疆维吾尔自治区", "city_name_cn": "和田地区", "metric_year": 2020},
            {"city_id": "CN-654200", "province_name": "新疆维吾尔自治区", "city_name_cn": "塔城地区", "metric_year": 2020},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-653200", "2020")]["statutory_debt_balance_100m"], Decimal("258.96"))
        self.assertIsNone(facts[("CN-653200", "2020")]["general_debt_balance_100m"])
        self.assertIsNone(facts[("CN-653200", "2020")]["special_debt_balance_100m"])
        self.assertEqual(facts[("CN-654200", "2020")]["statutory_debt_balance_100m"], Decimal("219.65"))
        self.assertIsNone(facts[("CN-654200", "2020")]["general_debt_balance_100m"])
        self.assertIsNone(facts[("CN-654200", "2020")]["special_debt_balance_100m"])

    def test_guangxi_2023_rating_top3_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-SECONDARY-DEBT-GUANGXI-2023-TOP3", source_ids)
        city_master = [
            {"city_id": "CN-450100", "province_name": "广西壮族自治区", "city_name_cn": "南宁市", "metric_year": 2023},
            {"city_id": "CN-450200", "province_name": "广西壮族自治区", "city_name_cn": "柳州市", "metric_year": 2023},
            {"city_id": "CN-450300", "province_name": "广西壮族自治区", "city_name_cn": "桂林市", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-450100", "2023")]["statutory_debt_balance_100m"], Decimal("1483.42"))
        self.assertEqual(facts[("CN-450200", "2023")]["statutory_debt_balance_100m"], Decimal("897.70"))
        self.assertEqual(facts[("CN-450300", "2023")]["statutory_debt_balance_100m"], Decimal("846.00"))

    def test_yunnan_2022_gcs66_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        for city_key in ("QUJING", "LIJIANG", "LINCANG", "HONGHE", "WENSHAN", "DEHONG", "NUJIANG", "DIQING"):
            self.assertIn(f"SRC-SECONDARY-DEBT-GCS66-YUNNAN-{city_key}-2022", source_ids)
        city_master = [
            {"city_id": "CN-530300", "province_name": "云南省", "city_name_cn": "曲靖市", "metric_year": 2022},
            {"city_id": "CN-530700", "province_name": "云南省", "city_name_cn": "丽江市", "metric_year": 2022},
            {"city_id": "CN-530900", "province_name": "云南省", "city_name_cn": "临沧市", "metric_year": 2022},
            {"city_id": "CN-532500", "province_name": "云南省", "city_name_cn": "红河哈尼族彝族自治州", "metric_year": 2022},
            {"city_id": "CN-532600", "province_name": "云南省", "city_name_cn": "文山壮族苗族自治州", "metric_year": 2022},
            {"city_id": "CN-533100", "province_name": "云南省", "city_name_cn": "德宏傣族景颇族自治州", "metric_year": 2022},
            {"city_id": "CN-533300", "province_name": "云南省", "city_name_cn": "怒江傈僳族自治州", "metric_year": 2022},
            {"city_id": "CN-533400", "province_name": "云南省", "city_name_cn": "迪庆藏族自治州", "metric_year": 2022},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-530300", "2022")]["statutory_debt_balance_100m"], Decimal("773.56"))
        self.assertEqual(facts[("CN-530300", "2022")]["general_debt_balance_100m"], Decimal("277.40"))
        self.assertEqual(facts[("CN-530300", "2022")]["special_debt_balance_100m"], Decimal("496.16"))
        self.assertEqual(facts[("CN-530700", "2022")]["statutory_debt_balance_100m"], Decimal("319.77"))
        self.assertEqual(facts[("CN-530900", "2022")]["statutory_debt_balance_100m"], Decimal("458.20"))
        self.assertIsNone(facts[("CN-530900", "2022")]["general_debt_balance_100m"])
        self.assertEqual(facts[("CN-532500", "2022")]["statutory_debt_balance_100m"], Decimal("667.53"))
        self.assertEqual(facts[("CN-532500", "2022")]["general_debt_balance_100m"], Decimal("218.75"))
        self.assertEqual(facts[("CN-532600", "2022")]["statutory_debt_balance_100m"], Decimal("560.2386"))
        self.assertEqual(facts[("CN-533100", "2022")]["statutory_debt_balance_100m"], Decimal("300.42"))
        self.assertEqual(facts[("CN-533100", "2022")]["special_debt_balance_100m"], Decimal("204.10"))
        self.assertEqual(facts[("CN-533300", "2022")]["statutory_debt_balance_100m"], Decimal("121.76"))
        self.assertEqual(facts[("CN-533400", "2022")]["statutory_debt_balance_100m"], Decimal("120.71"))
        self.assertEqual(facts[("CN-533400", "2022")]["general_debt_balance_100m"], Decimal("88.65"))

    def test_yunnan_dali_2022_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-YUNNAN-DALI-2022", source_ids)
        city_master = [
            {
                "city_id": "CN-532900",
                "province_name": "云南省",
                "city_name_cn": "大理白族自治州",
                "metric_year": 2022,
            }
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-532900", "2022")]["statutory_debt_balance_100m"], Decimal("643.100199"))
        self.assertEqual(facts[("CN-532900", "2022")]["general_debt_balance_100m"], Decimal("192.651142"))
        self.assertEqual(facts[("CN-532900", "2022")]["special_debt_balance_100m"], Decimal("450.449057"))

    def test_yunnan_dehong_2018_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-YUNNAN-DEHONG-2018", source_ids)
        city_master = [
            {
                "city_id": "CN-533100",
                "province_name": "云南省",
                "city_name_cn": "德宏傣族景颇族自治州",
                "metric_year": 2018,
            }
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-533100", "2018")]["statutory_debt_balance_100m"], Decimal("186.9383"))
        self.assertEqual(facts[("CN-533100", "2018")]["general_debt_balance_100m"], Decimal("95.1623"))
        self.assertEqual(facts[("CN-533100", "2018")]["special_debt_balance_100m"], Decimal("91.7760"))

    def test_yunnan_2020_2021_gcs66_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        expected_sources = {
            "SRC-SECONDARY-DEBT-GCS66-YUNNAN-HONGHE-2020",
            "SRC-SECONDARY-DEBT-GCS66-YUNNAN-HONGHE-2021",
            "SRC-SECONDARY-DEBT-GCS66-YUNNAN-WENSHAN-2021",
            "SRC-SECONDARY-DEBT-GCS66-YUNNAN-XISHUANGBANNA-2020",
            "SRC-SECONDARY-DEBT-GCS66-YUNNAN-DALI-2020",
            "SRC-SECONDARY-DEBT-GCS66-YUNNAN-DALI-2021",
            "SRC-SECONDARY-DEBT-GCS66-YUNNAN-DIQING-2020",
            "SRC-SECONDARY-DEBT-GCS66-YUNNAN-DIQING-2021",
        }
        self.assertTrue(expected_sources <= source_ids)
        city_master = [
            {"city_id": "CN-532500", "province_name": "云南省", "city_name_cn": "红河哈尼族彝族自治州", "metric_year": 2020},
            {"city_id": "CN-532500", "province_name": "云南省", "city_name_cn": "红河哈尼族彝族自治州", "metric_year": 2021},
            {"city_id": "CN-532600", "province_name": "云南省", "city_name_cn": "文山壮族苗族自治州", "metric_year": 2021},
            {"city_id": "CN-532800", "province_name": "云南省", "city_name_cn": "西双版纳傣族自治州", "metric_year": 2020},
            {"city_id": "CN-532900", "province_name": "云南省", "city_name_cn": "大理白族自治州", "metric_year": 2020},
            {"city_id": "CN-532900", "province_name": "云南省", "city_name_cn": "大理白族自治州", "metric_year": 2021},
            {"city_id": "CN-533400", "province_name": "云南省", "city_name_cn": "迪庆藏族自治州", "metric_year": 2020},
            {"city_id": "CN-533400", "province_name": "云南省", "city_name_cn": "迪庆藏族自治州", "metric_year": 2021},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-532500", "2020")]["statutory_debt_balance_100m"], Decimal("430.4"))
        self.assertEqual(facts[("CN-532500", "2021")]["statutory_debt_balance_100m"], Decimal("563"))
        self.assertEqual(facts[("CN-532600", "2021")]["statutory_debt_balance_100m"], Decimal("496.9862"))
        self.assertEqual(facts[("CN-532800", "2020")]["statutory_debt_balance_100m"], Decimal("141.9"))
        self.assertEqual(facts[("CN-532800", "2020")]["general_debt_balance_100m"], Decimal("53.3"))
        self.assertEqual(facts[("CN-532900", "2020")]["statutory_debt_balance_100m"], Decimal("456.35"))
        self.assertEqual(facts[("CN-532900", "2021")]["statutory_debt_balance_100m"], Decimal("561.4319"))
        self.assertEqual(facts[("CN-532900", "2021")]["special_debt_balance_100m"], Decimal("369.7491"))
        self.assertEqual(facts[("CN-533400", "2020")]["statutory_debt_balance_100m"], Decimal("105.9270"))
        self.assertEqual(facts[("CN-533400", "2020")]["general_debt_balance_100m"], Decimal("88.4970"))
        self.assertEqual(facts[("CN-533400", "2021")]["statutory_debt_balance_100m"], Decimal("112.9566"))
        self.assertEqual(facts[("CN-533400", "2021")]["special_debt_balance_100m"], Decimal("26.3700"))

    def test_yunnan_2019_official_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        expected_sources = {
            "SRC-OFFICIAL-DEBT-YUNNAN-DALI-2019",
            "SRC-OFFICIAL-DEBT-YUNNAN-HONGHE-2019",
            "SRC-OFFICIAL-DEBT-YUNNAN-WENSHAN-2019",
        }
        self.assertTrue(expected_sources <= source_ids)
        city_master = [
            {"city_id": "CN-532500", "province_name": "云南省", "city_name_cn": "红河哈尼族彝族自治州", "metric_year": 2019},
            {"city_id": "CN-532600", "province_name": "云南省", "city_name_cn": "文山壮族苗族自治州", "metric_year": 2019},
            {"city_id": "CN-532900", "province_name": "云南省", "city_name_cn": "大理白族自治州", "metric_year": 2019},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-532500", "2019")]["statutory_debt_balance_100m"], Decimal("309.74"))
        self.assertIsNone(facts[("CN-532500", "2019")]["general_debt_balance_100m"])
        self.assertEqual(facts[("CN-532600", "2019")]["statutory_debt_balance_100m"], Decimal("280.8957"))
        self.assertEqual(facts[("CN-532600", "2019")]["general_debt_balance_100m"], Decimal("193.8657"))
        self.assertEqual(facts[("CN-532600", "2019")]["special_debt_balance_100m"], Decimal("87.0300"))
        self.assertEqual(facts[("CN-532900", "2019")]["statutory_debt_balance_100m"], Decimal("316.41"))
        self.assertIsNone(facts[("CN-532900", "2019")]["special_debt_balance_100m"])

    def test_sichuan_2019_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-SICHUAN-CITIES-2019", source_ids)
        city_master = [
            {"city_id": "CN-510400", "province_name": "四川省", "city_name_cn": "攀枝花市", "metric_year": 2019},
            {"city_id": "CN-511000", "province_name": "四川省", "city_name_cn": "内江市", "metric_year": 2019},
            {"city_id": "CN-511400", "province_name": "四川省", "city_name_cn": "眉山市", "metric_year": 2019},
            {"city_id": "CN-512000", "province_name": "四川省", "city_name_cn": "资阳市", "metric_year": 2019},
            {"city_id": "CN-513200", "province_name": "四川省", "city_name_cn": "阿坝藏族羌族自治州", "metric_year": 2019},
            {"city_id": "CN-513300", "province_name": "四川省", "city_name_cn": "甘孜藏族自治州", "metric_year": 2019},
            {"city_id": "CN-513400", "province_name": "四川省", "city_name_cn": "凉山彝族自治州", "metric_year": 2019},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-510400", "2019")]["statutory_debt_balance_100m"], Decimal("203"))
        self.assertEqual(facts[("CN-511000", "2019")]["statutory_debt_balance_100m"], Decimal("400"))
        self.assertEqual(facts[("CN-511400", "2019")]["statutory_debt_balance_100m"], Decimal("405"))
        self.assertEqual(facts[("CN-512000", "2019")]["statutory_debt_balance_100m"], Decimal("328"))
        self.assertEqual(facts[("CN-513200", "2019")]["statutory_debt_balance_100m"], Decimal("74"))
        self.assertEqual(facts[("CN-513300", "2019")]["statutory_debt_balance_100m"], Decimal("89"))
        self.assertEqual(facts[("CN-513400", "2019")]["statutory_debt_balance_100m"], Decimal("345"))
        self.assertIsNone(facts[("CN-510400", "2019")]["general_debt_balance_100m"])

    def test_sichuan_2020_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-SICHUAN-CITIES-2020", source_ids)
        city_master = [
            {"city_id": "CN-510400", "province_name": "四川省", "city_name_cn": "攀枝花市", "metric_year": 2020},
            {"city_id": "CN-511000", "province_name": "四川省", "city_name_cn": "内江市", "metric_year": 2020},
            {"city_id": "CN-511400", "province_name": "四川省", "city_name_cn": "眉山市", "metric_year": 2020},
            {"city_id": "CN-512000", "province_name": "四川省", "city_name_cn": "资阳市", "metric_year": 2020},
            {"city_id": "CN-513200", "province_name": "四川省", "city_name_cn": "阿坝藏族羌族自治州", "metric_year": 2020},
            {"city_id": "CN-513300", "province_name": "四川省", "city_name_cn": "甘孜藏族自治州", "metric_year": 2020},
            {"city_id": "CN-513400", "province_name": "四川省", "city_name_cn": "凉山彝族自治州", "metric_year": 2020},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-510400", "2020")]["statutory_debt_balance_100m"], Decimal("221"))
        self.assertEqual(facts[("CN-510400", "2020")]["general_debt_balance_100m"], Decimal("143"))
        self.assertEqual(facts[("CN-511000", "2020")]["statutory_debt_balance_100m"], Decimal("466"))
        self.assertEqual(facts[("CN-511400", "2020")]["special_debt_balance_100m"], Decimal("269"))
        self.assertEqual(facts[("CN-512000", "2020")]["statutory_debt_balance_100m"], Decimal("361"))
        self.assertEqual(facts[("CN-513200", "2020")]["general_debt_balance_100m"], Decimal("64"))
        self.assertEqual(facts[("CN-513300", "2020")]["special_debt_balance_100m"], Decimal("19"))
        self.assertEqual(facts[("CN-513400", "2020")]["statutory_debt_balance_100m"], Decimal("384"))

    def test_sichuan_2022_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-SICHUAN-CITIES-2022", source_ids)
        city_master = [
            {"city_id": "CN-510400", "province_name": "四川省", "city_name_cn": "攀枝花市", "metric_year": 2022},
            {"city_id": "CN-511000", "province_name": "四川省", "city_name_cn": "内江市", "metric_year": 2022},
            {"city_id": "CN-511400", "province_name": "四川省", "city_name_cn": "眉山市", "metric_year": 2022},
            {"city_id": "CN-512000", "province_name": "四川省", "city_name_cn": "资阳市", "metric_year": 2022},
            {"city_id": "CN-513200", "province_name": "四川省", "city_name_cn": "阿坝藏族羌族自治州", "metric_year": 2022},
            {"city_id": "CN-513300", "province_name": "四川省", "city_name_cn": "甘孜藏族自治州", "metric_year": 2022},
            {"city_id": "CN-513400", "province_name": "四川省", "city_name_cn": "凉山彝族自治州", "metric_year": 2022},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-510400", "2022")]["statutory_debt_balance_100m"], Decimal("238.6"))
        self.assertEqual(facts[("CN-510400", "2022")]["general_debt_balance_100m"], Decimal("144.2"))
        self.assertEqual(facts[("CN-511000", "2022")]["statutory_debt_balance_100m"], Decimal("624.7"))
        self.assertEqual(facts[("CN-511400", "2022")]["special_debt_balance_100m"], Decimal("429.0"))
        self.assertEqual(facts[("CN-512000", "2022")]["statutory_debt_balance_100m"], Decimal("513.0"))
        self.assertEqual(facts[("CN-513200", "2022")]["general_debt_balance_100m"], Decimal("73.7"))
        self.assertEqual(facts[("CN-513300", "2022")]["special_debt_balance_100m"], Decimal("32.9"))
        self.assertEqual(facts[("CN-513400", "2022")]["statutory_debt_balance_100m"], Decimal("454.3"))

    def test_sichuan_2023_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-SICHUAN-CITIES-2023", source_ids)
        city_master = [
            {"city_id": "CN-510400", "province_name": "四川省", "city_name_cn": "攀枝花市", "metric_year": 2023},
            {"city_id": "CN-511000", "province_name": "四川省", "city_name_cn": "内江市", "metric_year": 2023},
            {"city_id": "CN-511400", "province_name": "四川省", "city_name_cn": "眉山市", "metric_year": 2023},
            {"city_id": "CN-512000", "province_name": "四川省", "city_name_cn": "资阳市", "metric_year": 2023},
            {"city_id": "CN-513200", "province_name": "四川省", "city_name_cn": "阿坝藏族羌族自治州", "metric_year": 2023},
            {"city_id": "CN-513300", "province_name": "四川省", "city_name_cn": "甘孜藏族自治州", "metric_year": 2023},
            {"city_id": "CN-513400", "province_name": "四川省", "city_name_cn": "凉山彝族自治州", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-510400", "2023")]["statutory_debt_balance_100m"], Decimal("260.2"))
        self.assertEqual(facts[("CN-510400", "2023")]["general_debt_balance_100m"], Decimal("147.0"))
        self.assertEqual(facts[("CN-511000", "2023")]["statutory_debt_balance_100m"], Decimal("698.7"))
        self.assertEqual(facts[("CN-511400", "2023")]["special_debt_balance_100m"], Decimal("498.9"))
        self.assertEqual(facts[("CN-512000", "2023")]["statutory_debt_balance_100m"], Decimal("566.5"))
        self.assertEqual(facts[("CN-513200", "2023")]["general_debt_balance_100m"], Decimal("80.9"))
        self.assertEqual(facts[("CN-513300", "2023")]["special_debt_balance_100m"], Decimal("41.2"))
        self.assertEqual(facts[("CN-513400", "2023")]["statutory_debt_balance_100m"], Decimal("497.9"))

    def test_tibet_2020_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-TIBET-CITIES-2020", source_ids)
        city_master = [
            {"city_id": "CN-540100", "province_name": "西藏自治区", "city_name_cn": "拉萨市", "metric_year": 2020},
            {"city_id": "CN-540200", "province_name": "西藏自治区", "city_name_cn": "日喀则市", "metric_year": 2020},
            {"city_id": "CN-540300", "province_name": "西藏自治区", "city_name_cn": "昌都市", "metric_year": 2020},
            {"city_id": "CN-540400", "province_name": "西藏自治区", "city_name_cn": "林芝市", "metric_year": 2020},
            {"city_id": "CN-540500", "province_name": "西藏自治区", "city_name_cn": "山南市", "metric_year": 2020},
            {"city_id": "CN-540600", "province_name": "西藏自治区", "city_name_cn": "那曲市", "metric_year": 2020},
            {"city_id": "CN-542500", "province_name": "西藏自治区", "city_name_cn": "阿里地区", "metric_year": 2020},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-540100", "2020")]["statutory_debt_balance_100m"], Decimal("63.59"))
        self.assertEqual(facts[("CN-540100", "2020")]["general_debt_balance_100m"], Decimal("15.29"))
        self.assertEqual(facts[("CN-540200", "2020")]["statutory_debt_balance_100m"], Decimal("59.50"))
        self.assertEqual(facts[("CN-540300", "2020")]["special_debt_balance_100m"], Decimal("4.08"))
        self.assertEqual(facts[("CN-540400", "2020")]["statutory_debt_balance_100m"], Decimal("15.88"))
        self.assertEqual(facts[("CN-540500", "2020")]["general_debt_balance_100m"], Decimal("7.21"))
        self.assertEqual(facts[("CN-540600", "2020")]["special_debt_balance_100m"], Decimal("12.97"))
        self.assertEqual(facts[("CN-542500", "2020")]["statutory_debt_balance_100m"], Decimal("23.28"))

    def test_tibet_2021_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-TIBET-CITIES-2021", source_ids)
        city_master = [
            {"city_id": "CN-540100", "province_name": "西藏自治区", "city_name_cn": "拉萨市", "metric_year": 2021},
            {"city_id": "CN-540200", "province_name": "西藏自治区", "city_name_cn": "日喀则市", "metric_year": 2021},
            {"city_id": "CN-540300", "province_name": "西藏自治区", "city_name_cn": "昌都市", "metric_year": 2021},
            {"city_id": "CN-540400", "province_name": "西藏自治区", "city_name_cn": "林芝市", "metric_year": 2021},
            {"city_id": "CN-540500", "province_name": "西藏自治区", "city_name_cn": "山南市", "metric_year": 2021},
            {"city_id": "CN-540600", "province_name": "西藏自治区", "city_name_cn": "那曲市", "metric_year": 2021},
            {"city_id": "CN-542500", "province_name": "西藏自治区", "city_name_cn": "阿里地区", "metric_year": 2021},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-540100", "2021")]["statutory_debt_balance_100m"], Decimal("79.862686"))
        self.assertEqual(facts[("CN-540100", "2021")]["general_debt_balance_100m"], Decimal("26.754086"))
        self.assertEqual(facts[("CN-540200", "2021")]["statutory_debt_balance_100m"], Decimal("77.356778"))
        self.assertEqual(facts[("CN-540300", "2021")]["special_debt_balance_100m"], Decimal("4.0800"))
        self.assertEqual(facts[("CN-540400", "2021")]["statutory_debt_balance_100m"], Decimal("23.937935"))
        self.assertEqual(facts[("CN-540500", "2021")]["general_debt_balance_100m"], Decimal("20.6978"))
        self.assertEqual(facts[("CN-540600", "2021")]["special_debt_balance_100m"], Decimal("41.0214"))
        self.assertEqual(facts[("CN-542500", "2021")]["statutory_debt_balance_100m"], Decimal("25.0672"))

    def test_tibet_2022_official_city_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-TIBET-CITIES-2022", source_ids)
        city_master = [
            {"city_id": "CN-540100", "province_name": "西藏自治区", "city_name_cn": "拉萨市", "metric_year": 2022},
            {"city_id": "CN-540200", "province_name": "西藏自治区", "city_name_cn": "日喀则市", "metric_year": 2022},
            {"city_id": "CN-540300", "province_name": "西藏自治区", "city_name_cn": "昌都市", "metric_year": 2022},
            {"city_id": "CN-540400", "province_name": "西藏自治区", "city_name_cn": "林芝市", "metric_year": 2022},
            {"city_id": "CN-540500", "province_name": "西藏自治区", "city_name_cn": "山南市", "metric_year": 2022},
            {"city_id": "CN-540600", "province_name": "西藏自治区", "city_name_cn": "那曲市", "metric_year": 2022},
            {"city_id": "CN-542500", "province_name": "西藏自治区", "city_name_cn": "阿里地区", "metric_year": 2022},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-540100", "2022")]["statutory_debt_balance_100m"], Decimal("91.942686"))
        self.assertEqual(facts[("CN-540100", "2022")]["general_debt_balance_100m"], Decimal("35.804086"))
        self.assertEqual(facts[("CN-540200", "2022")]["statutory_debt_balance_100m"], Decimal("84.617778"))
        self.assertEqual(facts[("CN-540300", "2022")]["special_debt_balance_100m"], Decimal("5.2200"))
        self.assertEqual(facts[("CN-540400", "2022")]["statutory_debt_balance_100m"], Decimal("25.497935"))
        self.assertEqual(facts[("CN-540500", "2022")]["general_debt_balance_100m"], Decimal("35.7778"))
        self.assertEqual(facts[("CN-540600", "2022")]["special_debt_balance_100m"], Decimal("41.0214"))
        self.assertEqual(facts[("CN-542500", "2022")]["statutory_debt_balance_100m"], Decimal("29.3472"))

    def test_tibet_2019_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-CITY-DEBT-TIBET-LHASA-2019", source_ids)
        self.assertIn("SRC-CITY-DEBT-TIBET-CHANGDU-2019", source_ids)
        city_master = [
            {"city_id": "CN-540100", "province_name": "西藏自治区", "city_name_cn": "拉萨市", "metric_year": 2019},
            {"city_id": "CN-540300", "province_name": "西藏自治区", "city_name_cn": "昌都市", "metric_year": 2019},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-540100", "2019")]["statutory_debt_balance_100m"], Decimal("37.6758"))
        self.assertEqual(facts[("CN-540100", "2019")]["general_debt_balance_100m"], Decimal("12.3758"))
        self.assertEqual(facts[("CN-540100", "2019")]["special_debt_balance_100m"], Decimal("25.3000"))
        self.assertEqual(facts[("CN-540300", "2019")]["statutory_debt_balance_100m"], Decimal("46.78"))
        self.assertEqual(facts[("CN-540300", "2019")]["general_debt_balance_100m"], Decimal("45.60"))
        self.assertEqual(facts[("CN-540300", "2019")]["special_debt_balance_100m"], Decimal("1.18"))

    def test_tibet_2023_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        for source_id in (
            "SRC-CITY-DEBT-TIBET-LHASA-2023",
            "SRC-CITY-DEBT-TIBET-CHANGDU-2023",
            "SRC-CITY-DEBT-TIBET-SHANNAN-2023",
        ):
            self.assertIn(source_id, source_ids)
        city_master = [
            {"city_id": "CN-540100", "province_name": "西藏自治区", "city_name_cn": "拉萨市", "metric_year": 2023},
            {"city_id": "CN-540300", "province_name": "西藏自治区", "city_name_cn": "昌都市", "metric_year": 2023},
            {"city_id": "CN-540500", "province_name": "西藏自治区", "city_name_cn": "山南市", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-540100", "2023")]["statutory_debt_balance_100m"], Decimal("104.42"))
        self.assertEqual(facts[("CN-540100", "2023")]["general_debt_balance_100m"], Decimal("45.85"))
        self.assertEqual(facts[("CN-540100", "2023")]["special_debt_balance_100m"], Decimal("58.57"))
        self.assertEqual(facts[("CN-540300", "2023")]["statutory_debt_balance_100m"], Decimal("93.92"))
        self.assertEqual(facts[("CN-540300", "2023")]["general_debt_balance_100m"], Decimal("81.86"))
        self.assertEqual(facts[("CN-540300", "2023")]["special_debt_balance_100m"], Decimal("12.06"))
        self.assertEqual(facts[("CN-540500", "2023")]["statutory_debt_balance_100m"], Decimal("76.4678"))
        self.assertEqual(facts[("CN-540500", "2023")]["general_debt_balance_100m"], Decimal("42.4978"))
        self.assertEqual(facts[("CN-540500", "2023")]["special_debt_balance_100m"], Decimal("33.9700"))

    def test_yunnan_2023_official_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        for source_id in (
            "SRC-OFFICIAL-DEBT-YUNNAN-HONGHE-2023",
            "SRC-OFFICIAL-DEBT-YUNNAN-DALI-2023",
            "SRC-OFFICIAL-DEBT-YUNNAN-DIQING-2023",
        ):
            self.assertIn(source_id, source_ids)
        city_master = [
            {"city_id": "CN-532500", "province_name": "云南省", "city_name_cn": "红河哈尼族彝族自治州", "metric_year": 2023},
            {"city_id": "CN-532900", "province_name": "云南省", "city_name_cn": "大理白族自治州", "metric_year": 2023},
            {"city_id": "CN-533400", "province_name": "云南省", "city_name_cn": "迪庆藏族自治州", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-532500", "2023")]["statutory_debt_balance_100m"], Decimal("806.75"))
        self.assertEqual(facts[("CN-532500", "2023")]["general_debt_balance_100m"], Decimal("269.00"))
        self.assertEqual(facts[("CN-532500", "2023")]["special_debt_balance_100m"], Decimal("537.75"))
        self.assertEqual(facts[("CN-532900", "2023")]["statutory_debt_balance_100m"], Decimal("717.7668"))
        self.assertEqual(facts[("CN-532900", "2023")]["general_debt_balance_100m"], Decimal("220.4977"))
        self.assertEqual(facts[("CN-532900", "2023")]["special_debt_balance_100m"], Decimal("497.2691"))
        self.assertEqual(facts[("CN-533400", "2023")]["statutory_debt_balance_100m"], Decimal("171.2156"))
        self.assertEqual(facts[("CN-533400", "2023")]["general_debt_balance_100m"], Decimal("105.1156"))
        self.assertEqual(facts[("CN-533400", "2023")]["special_debt_balance_100m"], Decimal("66.1000"))

    def test_shanxi_2023_official_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        for source_id in (
            "SRC-OFFICIAL-DEBT-SHANXI-CHANGZHI-2023",
            "SRC-OFFICIAL-DEBT-SHANXI-JINCHENG-2023",
            "SRC-SECONDARY-DEBT-SHANXI-YUNCHENG-2023",
            "SRC-OFFICIAL-DEBT-SHANXI-LVLIANG-2023",
        ):
            self.assertIn(source_id, source_ids)
        city_master = [
            {"city_id": "CN-140400", "province_name": "山西省", "city_name_cn": "长治市", "metric_year": 2023},
            {"city_id": "CN-140500", "province_name": "山西省", "city_name_cn": "晋城市", "metric_year": 2023},
            {"city_id": "CN-140800", "province_name": "山西省", "city_name_cn": "运城市", "metric_year": 2023},
            {"city_id": "CN-141100", "province_name": "山西省", "city_name_cn": "吕梁市", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-140400", "2023")]["statutory_debt_balance_100m"], Decimal("423.84"))
        self.assertEqual(facts[("CN-140400", "2023")]["general_debt_balance_100m"], Decimal("190.09"))
        self.assertEqual(facts[("CN-140400", "2023")]["special_debt_balance_100m"], Decimal("233.75"))
        self.assertEqual(facts[("CN-140500", "2023")]["statutory_debt_balance_100m"], Decimal("350.67"))
        self.assertEqual(facts[("CN-140500", "2023")]["general_debt_balance_100m"], Decimal("118.03"))
        self.assertEqual(facts[("CN-140500", "2023")]["special_debt_balance_100m"], Decimal("232.64"))
        self.assertEqual(facts[("CN-140800", "2023")]["statutory_debt_balance_100m"], Decimal("421.55"))
        self.assertEqual(facts[("CN-140800", "2023")]["general_debt_balance_100m"], Decimal("173.10"))
        self.assertEqual(facts[("CN-140800", "2023")]["special_debt_balance_100m"], Decimal("248.45"))
        self.assertEqual(facts[("CN-141100", "2023")]["statutory_debt_balance_100m"], Decimal("500.28"))
        self.assertIsNone(facts[("CN-141100", "2023")]["general_debt_balance_100m"])
        self.assertIsNone(facts[("CN-141100", "2023")]["special_debt_balance_100m"])

    def test_guizhou_2018_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        for source_id in (
            "SRC-OFFICIAL-DEBT-GUIZHOU-LIUPANSHUI-2018",
            "SRC-OFFICIAL-DEBT-GUIZHOU-ZUNYI-2018",
            "SRC-OFFICIAL-DEBT-GUIZHOU-BIJIE-2018",
            "SRC-OFFICIAL-DEBT-GUIZHOU-QIANXINAN-2018",
            "SRC-OFFICIAL-DEBT-GUIZHOU-QIANDONGNAN-2018",
        ):
            self.assertIn(source_id, source_ids)
        city_master = [
            {"city_id": "CN-520200", "province_name": "贵州省", "city_name_cn": "六盘水市", "metric_year": 2018},
            {"city_id": "CN-520300", "province_name": "贵州省", "city_name_cn": "遵义市", "metric_year": 2018},
            {"city_id": "CN-520500", "province_name": "贵州省", "city_name_cn": "毕节市", "metric_year": 2018},
            {"city_id": "CN-522300", "province_name": "贵州省", "city_name_cn": "黔西南布依族苗族自治州", "metric_year": 2018},
            {"city_id": "CN-522600", "province_name": "贵州省", "city_name_cn": "黔东南苗族侗族自治州", "metric_year": 2018},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-520200", "2018")]["statutory_debt_balance_100m"], Decimal("568.02"))
        self.assertEqual(facts[("CN-520200", "2018")]["general_debt_balance_100m"], Decimal("481.91"))
        self.assertEqual(facts[("CN-520200", "2018")]["special_debt_balance_100m"], Decimal("86.11"))
        self.assertEqual(facts[("CN-520300", "2018")]["statutory_debt_balance_100m"], Decimal("1365.64"))
        self.assertEqual(facts[("CN-520500", "2018")]["statutory_debt_balance_100m"], Decimal("911.24"))
        self.assertEqual(facts[("CN-520500", "2018")]["general_debt_balance_100m"], Decimal("690.64"))
        self.assertEqual(facts[("CN-520500", "2018")]["special_debt_balance_100m"], Decimal("220.60"))
        self.assertEqual(facts[("CN-522300", "2018")]["statutory_debt_balance_100m"], Decimal("443.7200"))
        self.assertEqual(facts[("CN-522300", "2018")]["general_debt_balance_100m"], Decimal("346.2139"))
        self.assertEqual(facts[("CN-522300", "2018")]["special_debt_balance_100m"], Decimal("97.5061"))
        self.assertEqual(facts[("CN-522600", "2018")]["statutory_debt_balance_100m"], Decimal("414.68"))
        self.assertIsNone(facts[("CN-522600", "2018")]["general_debt_balance_100m"])
        self.assertIsNone(facts[("CN-522600", "2018")]["special_debt_balance_100m"])

    def test_gansu_2019_jinchang_secondary_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-SECONDARY-DEBT-GANSU-JINCHANG-2019", source_ids)
        city_master = [
            {"city_id": "CN-620300", "province_name": "甘肃省", "city_name_cn": "金昌市", "metric_year": 2019},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        fact = facts[("CN-620300", "2019")]
        self.assertEqual(fact["statutory_debt_balance_100m"], Decimal("53.90"))
        self.assertIsNone(fact["general_debt_balance_100m"])
        self.assertIsNone(fact["special_debt_balance_100m"])

    def test_gansu_2021_pingliang_secondary_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-SECONDARY-DEBT-GANSU-PINGLIANG-2021", source_ids)
        city_master = [
            {"city_id": "CN-620800", "province_name": "甘肃省", "city_name_cn": "平凉市", "metric_year": 2021},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        fact = facts[("CN-620800", "2021")]
        self.assertEqual(fact["statutory_debt_balance_100m"], Decimal("208.03"))
        self.assertEqual(fact["general_debt_balance_100m"], Decimal("87.52"))
        self.assertEqual(fact["special_debt_balance_100m"], Decimal("120.51"))

    def test_gansu_2020_tianshui_official_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-GANSU-TIANSHUI-2020", source_ids)
        city_master = [
            {"city_id": "CN-620500", "province_name": "甘肃省", "city_name_cn": "天水市", "metric_year": 2020},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        fact = facts[("CN-620500", "2020")]
        self.assertEqual(fact["statutory_debt_balance_100m"], Decimal("164.64"))
        self.assertEqual(fact["general_debt_balance_100m"], Decimal("65.26"))
        self.assertEqual(fact["special_debt_balance_100m"], Decimal("99.38"))

    def test_shaanxi_2022_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        for source_id in (
            "SRC-OFFICIAL-DEBT-SHAANXI-BAOJI-2022",
            "SRC-OFFICIAL-DEBT-SHAANXI-HANZHONG-2022",
            "SRC-SECONDARY-DEBT-SHAANXI-YANAN-2022",
            "SRC-SECONDARY-DEBT-SHAANXI-XIANYANG-2022",
            "SRC-SECONDARY-DEBT-SHAANXI-WEINAN-2022",
        ):
            self.assertIn(source_id, source_ids)
        city_master = [
            {"city_id": "CN-610300", "province_name": "陕西省", "city_name_cn": "宝鸡市", "metric_year": 2022},
            {"city_id": "CN-610700", "province_name": "陕西省", "city_name_cn": "汉中市", "metric_year": 2022},
            {"city_id": "CN-610600", "province_name": "陕西省", "city_name_cn": "延安市", "metric_year": 2022},
            {"city_id": "CN-610400", "province_name": "陕西省", "city_name_cn": "咸阳市", "metric_year": 2022},
            {"city_id": "CN-610500", "province_name": "陕西省", "city_name_cn": "渭南市", "metric_year": 2022},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        expected = {
            "CN-610300": ("369.48", "184.28", "185.20"),
            "CN-610700": ("431.38", "200.18", "231.20"),
            "CN-610600": ("621.2106", "314.5726", "306.6380"),
            "CN-610400": ("432.61", "171.31", "261.30"),
            "CN-610500": ("553.44", "259.17", "294.28"),
        }
        for city_id, (total, general, special) in expected.items():
            fact = facts[(city_id, "2022")]
            self.assertEqual(fact["statutory_debt_balance_100m"], Decimal(total))
            self.assertEqual(fact["general_debt_balance_100m"], Decimal(general))
            self.assertEqual(fact["special_debt_balance_100m"], Decimal(special))

    def test_inner_mongolia_2023_ordos_secondary_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-SECONDARY-DEBT-INNER-MONGOLIA-ORDOS-2023", source_ids)
        city_master = [
            {"city_id": "CN-150600", "province_name": "内蒙古自治区", "city_name_cn": "鄂尔多斯市", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        fact = facts[("CN-150600", "2023")]
        self.assertEqual(fact["statutory_debt_balance_100m"], Decimal("1870.10"))
        self.assertEqual(fact["general_debt_balance_100m"], Decimal("1586.40"))
        self.assertEqual(fact["special_debt_balance_100m"], Decimal("283.70"))

    def test_inner_mongolia_2023_baotou_alxa_secondary_totals_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-SECONDARY-DEBT-INNER-MONGOLIA-BAOTOU-ALXA-2023", source_ids)
        city_master = [
            {"city_id": "CN-150200", "province_name": "内蒙古自治区", "city_name_cn": "包头市", "metric_year": 2023},
            {"city_id": "CN-152900", "province_name": "内蒙古自治区", "city_name_cn": "阿拉善盟", "metric_year": 2023},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-150200", "2023")]["statutory_debt_balance_100m"], Decimal("1280.45"))
        self.assertEqual(facts[("CN-152900", "2023")]["statutory_debt_balance_100m"], Decimal("306.58"))
        self.assertIsNone(facts[("CN-150200", "2023")]["general_debt_balance_100m"])
        self.assertIsNone(facts[("CN-152900", "2023")]["special_debt_balance_100m"])

    def test_inner_mongolia_xilingol_2018_whole_league_official_debt_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-INNER-MONGOLIA-XILINGOL-2018", source_ids)
        city_master = [
            {"city_id": "CN-152500", "province_name": "内蒙古自治区", "city_name_cn": "锡林郭勒盟", "metric_year": 2018},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        fact = facts[("CN-152500", "2018")]
        self.assertEqual(fact["statutory_debt_balance_100m"], Decimal("337.2350574131"))
        self.assertEqual(fact["general_debt_balance_100m"], Decimal("323.6195574128"))
        self.assertEqual(fact["special_debt_balance_100m"], Decimal("13.6155000003"))
        self.assertIn("专项债务余额13.6155000003亿元", fact["balance_limit_exception_note"])

    def test_guangxi_2018_secondary_city_debt_sources_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        for city in ("LIUZHOU", "GUILIN", "YULIN", "WUZHOU", "GUIGANG", "QINZHOU"):
            self.assertIn(f"SRC-SECONDARY-DEBT-GUANGXI-{city}-2018", source_ids)
        city_master = [
            {"city_id": "CN-450200", "province_name": "广西壮族自治区", "city_name_cn": "柳州市", "metric_year": 2018},
            {"city_id": "CN-450300", "province_name": "广西壮族自治区", "city_name_cn": "桂林市", "metric_year": 2018},
            {"city_id": "CN-450400", "province_name": "广西壮族自治区", "city_name_cn": "梧州市", "metric_year": 2018},
            {"city_id": "CN-450700", "province_name": "广西壮族自治区", "city_name_cn": "钦州市", "metric_year": 2018},
            {"city_id": "CN-450800", "province_name": "广西壮族自治区", "city_name_cn": "贵港市", "metric_year": 2018},
            {"city_id": "CN-450900", "province_name": "广西壮族自治区", "city_name_cn": "玉林市", "metric_year": 2018},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        expected = {
            "CN-450200": ("560.98", "192.82", "368.16"),
            "CN-450300": ("419.7", "266.8", "152.9"),
            "CN-450400": ("221.8", "163.3", "58.6"),
            "CN-450700": ("270.45", "132.53", "137.92"),
            "CN-450800": ("154.2", "102.9", "51.3"),
            "CN-450900": ("201.5", "145.6", "55.9"),
        }
        for city_id, (total, general, special) in expected.items():
            fact = facts[(city_id, "2018")]
            self.assertEqual(fact["statutory_debt_balance_100m"], Decimal(total))
            self.assertEqual(fact["general_debt_balance_100m"], Decimal(general))
            self.assertEqual(fact["special_debt_balance_100m"], Decimal(special))

    def test_yunnan_2024_wenshan_and_xishuangbanna_official_totals_are_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-YUNNAN-WENSHAN-2024", source_ids)
        self.assertIn("SRC-OFFICIAL-DEBT-YUNNAN-XISHUANGBANNA-2024", source_ids)
        city_master = [
            {"city_id": "CN-532600", "province_name": "云南省", "city_name_cn": "文山壮族苗族自治州", "metric_year": 2024},
            {"city_id": "CN-532800", "province_name": "云南省", "city_name_cn": "西双版纳傣族自治州", "metric_year": 2024},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        self.assertEqual(facts[("CN-532600", "2024")]["statutory_debt_balance_100m"], Decimal("896.5882"))
        self.assertEqual(facts[("CN-532800", "2024")]["statutory_debt_balance_100m"], Decimal("305.39"))
        self.assertIsNone(facts[("CN-532600", "2024")]["general_debt_balance_100m"])
        self.assertIsNone(facts[("CN-532800", "2024")]["special_debt_balance_100m"])

    def test_yunnan_2024_nujiang_official_debt_report_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-OFFICIAL-DEBT-YUNNAN-NUJIANG-2024", source_ids)
        city_master = [
            {"city_id": "CN-533300", "province_name": "云南省", "city_name_cn": "怒江傈僳族自治州", "metric_year": 2024},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        fact = facts[("CN-533300", "2024")]
        self.assertEqual(fact["statutory_debt_balance_100m"], Decimal("174.10"))
        self.assertEqual(fact["general_debt_balance_100m"], Decimal("111.59"))
        self.assertEqual(fact["special_debt_balance_100m"], Decimal("62.51"))

    def test_guangxi_2018_chongzuo_secondary_debt_source_is_registered_and_extracted(self):
        from scripts.province_debt_sources import OFFICIAL_PROVINCE_DEBT_SOURCES, extract_official_debt_facts

        source_ids = {str(source["source_doc_id"]) for source in OFFICIAL_PROVINCE_DEBT_SOURCES}
        self.assertIn("SRC-SECONDARY-DEBT-GUANGXI-CHONGZUO-2018", source_ids)
        city_master = [
            {"city_id": "CN-451400", "province_name": "广西壮族自治区", "city_name_cn": "崇左市", "metric_year": 2018},
        ]
        facts, _ = extract_official_debt_facts(city_master)
        fact = facts[("CN-451400", "2018")]
        self.assertEqual(fact["statutory_debt_balance_100m"], Decimal("156.12"))
        self.assertEqual(fact["general_debt_balance_100m"], Decimal("120.08"))
        self.assertEqual(fact["special_debt_balance_100m"], Decimal("36.04"))

if __name__ == "__main__":
    unittest.main()
