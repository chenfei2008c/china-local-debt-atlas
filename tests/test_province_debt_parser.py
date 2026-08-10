import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import zipfile

from scripts.province_debt_parser import extract_city_rows, extract_xlsx_city_rows, parse_numeric_tokens


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


if __name__ == "__main__":
    unittest.main()
