"""解析省级财政厅公开的地级行政单元政府债务表。

不同省份的 PDF 表格布局并不完全一致。本模块只做保守的行级解析：
调用方必须提供该省的地级行政单元白名单，只有以白名单名称开头且带有
足够数值列的行才会被纳入；省本级、市本级、区县和小计行不会被误并入。
"""

from __future__ import annotations

import re
import unicodedata
import html
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


NUMBER_RE = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|[—–-]")
XLSX_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _normal_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", "", value)


def _decimal(token: str) -> Decimal | None:
    token = token.strip().replace(",", "")
    if token in {"", "-", "—", "–"}:
        return None
    try:
        return Decimal(token)
    except InvalidOperation:
        return None


def parse_numeric_tokens(line: str) -> list[Decimal | None]:
    """从一行中提取数字列。

    破折号表示公开表中的空缺，不转换成 0。PDF 文本中的逗号千分位会被
    去除，返回 Decimal 以便后续按亿元等单位转换。
    """
    return [_decimal(token) for token in NUMBER_RE.findall(unicodedata.normalize("NFKC", line))]


def _find_city(line: str, expected_city_names: Iterable[str]) -> str | None:
    normalized_line = _normal_text(line)
    candidates = sorted(
        {_normal_text(name): name for name in expected_city_names if name},
        key=len,
        reverse=True,
    )
    for normalized_name in candidates:
        if normalized_line.startswith(normalized_name):
            # “城市本级”“市本级”等不是全市/全州口径；精确白名单名称后若
            # 紧跟本级，也必须跳过。
            tail = normalized_line[len(normalized_name) :]
            if tail.startswith("本级"):
                return None
            return normalized_name
    return None


def extract_city_rows(
    text: str,
    expected_city_names: Iterable[str],
    year: int,
    province_name: str,
    source_doc_id: str,
    layout: str = "total6",
    component: str | None = None,
    unit_factor: Decimal = Decimal("1"),
    table_name: str = "",
) -> list[dict[str, object]]:
    """解析地级行政单元行。

    layout=``total6`` 时列顺序为：限额合计、一般限额、专项限额、余额合计、
    一般余额、专项余额；layout=``component2`` 时列顺序为该分项限额、该分项余额。
    ``unit_factor`` 用于把万元转换为亿元（0.0001）。
    """
    expected_lookup = {_normal_text(name): name for name in expected_city_names}
    rows: list[dict[str, object]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        line_number = index + 1
        city_key = _find_city(line, expected_lookup)
        if city_key is None:
            continue
        # 叙述标题常以“城市名+年份”开头，例如“新余市2023年末地方政府债务余额”。
        # 这类标题本身不是数据行；若把标题中的年份当作第一列，会把 2023、2024
        # 等年份错误写入余额字段。真实数据行通常是“城市名 数值”，因此在匹配
        # 行级白名单后，先排除紧跟年份的标题行。
        normalized_tail = _normal_text(line)[len(city_key) :]
        if (
            layout != "direct3_general_special_after_year"
            and normalized_tail.startswith(str(year))
            and normalized_tail[len(str(year)) :].startswith("年")
        ):
            continue
        numbers = parse_numeric_tokens(line)
        evidence_line = line
        required_count = 9 if layout == "total9" else (6 if layout in {"total6", "balance6", "total6_balance_first"} else (3 if layout in {"component3", "component3_previous_balance", "balance3", "direct3_general_special", "direct3_general_special_after_year", "direct3_component_limit_new_balance", "limit3"} else (1 if layout in {"direct1", "limit1"} else 2)))
        # 部分 PDF 会把较长的自治州名称拆成两行，但数字仍在下一行；
        # 仅在已匹配白名单且当前数字列不足时合并下一行，避免跨行误配。
        if len(numbers) < required_count and index + 1 < len(lines):
            next_line = lines[index + 1]
            next_numbers = parse_numeric_tokens(next_line)
            if len(next_numbers) >= required_count:
                evidence_line = f"{line.rstrip()} {next_line.lstrip()}"
                numbers = parse_numeric_tokens(evidence_line)
        if layout in {"total6", "balance6", "total6_balance_first"} and len(numbers) < 6:
            continue
        if layout == "total9" and len(numbers) < 9:
            continue
        if layout == "component2" and len(numbers) < 2:
            continue
        if layout == "balance3" and len(numbers) < 3:
            continue
        if layout == "direct3_general_special" and len(numbers) < 3:
            continue
        if layout == "direct3_general_special_after_year" and len(numbers) < 4:
            continue
        if layout == "direct3_component_limit_new_balance" and len(numbers) < 3:
            continue
        if layout == "direct1" and len(numbers) < 1:
            continue
        if layout == "limit1" and len(numbers) < 1:
            continue
        if layout == "limit3" and len(numbers) < 3:
            continue
        values = [value * unit_factor if value is not None else None for value in numbers]
        row: dict[str, object] = {
            "city_name_cn": expected_lookup[city_key],
            "province_name": province_name,
            "metric_year": str(year),
            "geo_scope": "prefecture_whole",
            "source_doc_id": source_doc_id,
            "line_number": line_number,
            "table_name": table_name,
            "evidence_excerpt": evidence_line.strip(),
            "unit_factor": unit_factor,
            "general_debt_limit_100m": None,
            "general_debt_balance_100m": None,
            "special_debt_limit_100m": None,
            "special_debt_balance_100m": None,
            "statutory_debt_limit_100m": None,
            "statutory_debt_balance_100m": None,
        }
        if layout == "total6":
            total_limit, general_limit, special_limit, total_balance, general_balance, special_balance = values[:6]
            row.update(
                {
                    "general_debt_limit_100m": general_limit,
                    "general_debt_balance_100m": general_balance,
                    "special_debt_limit_100m": special_limit,
                    "special_debt_balance_100m": special_balance,
                    "statutory_debt_limit_100m": total_limit,
                    "statutory_debt_balance_100m": total_balance,
                }
            )
        elif layout == "total9":
            # 新疆等省份的表格按“限额总额、一般限额、专项限额；新增债务限额三列；
            # 余额总额、一般余额、专项余额”列示。中间三列不属于本表的标准字段，
            # 余额必须取最后三列，不能按 total6 截取前六列。
            total_limit, general_limit, special_limit = values[:3]
            total_balance, general_balance, special_balance = values[-3:]
            row.update(
                {
                    "general_debt_limit_100m": general_limit,
                    "general_debt_balance_100m": general_balance,
                    "special_debt_limit_100m": special_limit,
                    "special_debt_balance_100m": special_balance,
                    "statutory_debt_limit_100m": total_limit,
                    "statutory_debt_balance_100m": total_balance,
                }
            )
        elif layout == "balance6":
            # 黑龙江等省份的分地区表按“上一年末余额、当年限额、当年末余额”
            # 分别列出一般债务和专项债务，六列顺序为：一般三列、专项三列。
            _, general_limit, general_balance, _, special_limit, special_balance = values[:6]
            row.update(
                {
                    "general_debt_limit_100m": general_limit,
                    "general_debt_balance_100m": general_balance,
                    "special_debt_limit_100m": special_limit,
                    "special_debt_balance_100m": special_balance,
                }
            )
        elif layout == "total6_balance_first":
            # 陕西等省份按“合计限额、合计余额、一般限额、一般余额、专项限额、专项余额”列示。
            total_limit, total_balance, general_limit, general_balance, special_limit, special_balance = values[:6]
            row.update(
                {
                    "general_debt_limit_100m": general_limit,
                    "general_debt_balance_100m": general_balance,
                    "special_debt_limit_100m": special_limit,
                    "special_debt_balance_100m": special_balance,
                    "statutory_debt_limit_100m": total_limit,
                    "statutory_debt_balance_100m": total_balance,
                }
            )
        elif layout == "component3" and component in {"general", "special"}:
            # 表中同时列出上年末余额、当年限额、当年末余额，取后两列。
            _, limit, balance = values[:3]
            row[f"{component}_debt_limit_100m"] = limit
            row[f"{component}_debt_balance_100m"] = balance
        elif layout == "component3_previous_balance" and component in {"general", "special"}:
            # 复用下一年度决算表中的“上年末余额”列，只接入历史余额；
            # 下一年度限额和下一年度余额不得误标为历史年度字段。
            row[f"{component}_debt_balance_100m"] = values[0]
        elif layout == "component2" and component in {"general", "special"}:
            limit, balance = values[:2]
            row[f"{component}_debt_limit_100m"] = limit
            row[f"{component}_debt_balance_100m"] = balance
        elif layout == "balance3":
            total_balance, general_balance, special_balance = values[:3]
            row.update(
                {
                    "general_debt_balance_100m": general_balance,
                    "special_debt_balance_100m": special_balance,
                    "statutory_debt_balance_100m": total_balance,
                }
            )
        elif layout == "direct1":
            row["statutory_debt_balance_100m"] = values[0]
        elif layout == "limit1":
            row["statutory_debt_limit_100m"] = values[0]
        elif layout == "limit3":
            total_limit, general_limit, special_limit = values[:3]
            row.update(
                {
                    "general_debt_limit_100m": general_limit,
                    "special_debt_limit_100m": special_limit,
                    "statutory_debt_limit_100m": total_limit,
                }
            )
        elif layout == "direct3_general_special":
            total_balance, general_balance, special_balance = values[:3]
            row.update(
                {
                    "general_debt_balance_100m": general_balance,
                    "special_debt_balance_100m": special_balance,
                    "statutory_debt_balance_100m": total_balance,
                }
            )
        elif layout == "direct3_general_special_after_year":
            # 有些叙述行先列年份，再列全市总额、一般债券和专项债券余额。
            # 年份不是债务金额，必须跳过第一列，避免把年份误作总余额。
            total_balance, general_balance, special_balance = values[1:4]
            row.update(
                {
                    "general_debt_balance_100m": general_balance,
                    "special_debt_balance_100m": special_balance,
                    "statutory_debt_balance_100m": total_balance,
                }
            )
        elif layout == "direct3_component_limit_new_balance" and component in {"general", "special"}:
            # 新疆等表格按“分项限额、当年新增限额、分项余额”列示；
            # 新增限额不是主表字段，不能把专项债务分项误命名为法定总额。
            component_limit, _new_limit, component_balance = values[:3]
            row.update(
                {
                    f"{component}_debt_limit_100m": component_limit,
                    f"{component}_debt_balance_100m": component_balance,
                }
            )
        else:
            raise ValueError(f"不支持的债务表布局：{layout!r} / component={component!r}")
        rows.append(row)
    return rows


def extract_xlsx_city_rows(
    path: Path,
    expected_city_names: Iterable[str],
    year: int,
    province_name: str,
    source_doc_id: str,
    unit_factor: Decimal = Decimal("1"),
    table_name: str = "",
    sheet_path: str = "xl/worksheets/sheet1.xml",
    name_column: str = "C",
    value_columns: tuple[str, ...] = ("D", "E", "F", "G", "H", "I"),
    layout: str = "total6",
) -> list[dict[str, object]]:
    """读取中央国债登记结算公司公开 XLSX 中的地级行政单元总表。

    这类公开表通常使用 D:I 六列：债务限额合计、一般债务限额、专项债务限额、
    债务余额合计、一般债务余额、专项债务余额。函数只匹配调用方提供的地级
    行政单元白名单，因此不会把“市本级”、区县或省本级混入地级市口径。
    """
    expected_lookup = {_normal_text(name): name for name in expected_city_names if name}
    rows: list[dict[str, object]] = []
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("m:si", XLSX_NS):
                shared_strings.append("".join(text.text or "" for text in item.findall(".//m:t", XLSX_NS)))
        root = ET.fromstring(archive.read(sheet_path))
        for row in root.findall(".//m:sheetData/m:row", XLSX_NS):
            cells: dict[str, str] = {}
            for cell in row.findall("m:c", XLSX_NS):
                reference = cell.get("r", "")
                column = "".join(character for character in reference if character.isalpha())
                value = cell.find("m:v", XLSX_NS)
                if value is None:
                    value_text = "".join(text.text or "" for text in cell.findall(".//m:t", XLSX_NS))
                else:
                    value_text = value.text or ""
                    if cell.get("t") == "s" and value_text.isdigit():
                        index = int(value_text)
                        value_text = shared_strings[index] if index < len(shared_strings) else ""
                value_text = html.unescape(value_text).strip()
                if value_text:
                    cells[column] = value_text
            raw_city_name = cells.get(name_column, "")
            city_key = _normal_text(raw_city_name)
            if not city_key or city_key not in expected_lookup:
                continue
            values = [cells.get(column, "") or "—" for column in value_columns]
            if len(values) < 6:
                continue
            line = " ".join([raw_city_name, *values])
            parsed = parse_numeric_tokens(line)
            if len(parsed) < 6:
                continue
            if layout == "total9":
                scaled = [value * unit_factor if value is not None else None for value in parsed[-9:]]
                total_limit, general_limit, special_limit = scaled[:3]
                total_balance, general_balance, special_balance = scaled[-3:]
            else:
                scaled = [value * unit_factor if value is not None else None for value in parsed[-6:]]
                total_limit, general_limit, special_limit, total_balance, general_balance, special_balance = scaled
            rows.append(
                {
                    "city_name_cn": expected_lookup[city_key],
                    "province_name": province_name,
                    "metric_year": str(year),
                    "geo_scope": "prefecture_whole",
                    "source_doc_id": source_doc_id,
                    "line_number": int(row.get("r", "0")),
                    "table_name": table_name,
                    "evidence_excerpt": line,
                    "unit_factor": unit_factor,
                    "general_debt_limit_100m": general_limit,
                    "general_debt_balance_100m": general_balance,
                    "special_debt_limit_100m": special_limit,
                    "special_debt_balance_100m": special_balance,
                    "statutory_debt_limit_100m": total_limit,
                    "statutory_debt_balance_100m": total_balance,
                }
            )
    return rows


def merge_debt_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """按城市、年度合并总表及一般/专项分项表，并在分项齐全时勾稽合计。"""
    def source_priority(row: dict[str, object]) -> int:
        # 官方 A1/A2 应优先于审计/债券披露 B1/B2，后者又优先于 C/D
        # 线索。相同等级仍保持先出现者优先，避免无依据地覆盖同级冲突值。
        grade = str(row.get("source_grade", "")).strip().upper()
        return {
            "A1": 3,
            "A2": 3,
            "B1": 2,
            "B2": 2,
            "C": 1,
            "D": 0,
        }.get(grade, 0)

    # 省直辖县级行政区划等占位名称会在多个省份重复出现，合并键必须带省份，
    # 否则河南、湖北、海南、新疆等同名行会被错误合并。
    merged: dict[tuple[str, str, str], dict[str, object]] = {}
    for incoming in rows:
        key = (
            str(incoming.get("province_name", "")),
            str(incoming["city_name_cn"]),
            str(incoming["metric_year"]),
        )
        target = merged.setdefault(key, dict(incoming))
        if "_field_source_priority" not in target:
            initial_priority = source_priority(target)
            target["_field_source_priority"] = {
                field: initial_priority
                for field in (
                    "general_debt_limit_100m",
                    "general_debt_balance_100m",
                    "special_debt_limit_100m",
                    "special_debt_balance_100m",
                    "statutory_debt_limit_100m",
                    "statutory_debt_balance_100m",
                )
                if target.get(field) is not None
            }
        field_priorities = target["_field_source_priority"]
        incoming_priority = source_priority(incoming)
        for field in (
            "general_debt_limit_100m",
            "general_debt_balance_100m",
            "special_debt_limit_100m",
            "special_debt_balance_100m",
            "statutory_debt_limit_100m",
            "statutory_debt_balance_100m",
        ):
            if incoming.get(field) is None:
                continue
            current_priority = int(field_priorities.get(field, source_priority(target)))
            if target.get(field) is None or incoming_priority > current_priority:
                target[field] = incoming[field]
                field_priorities[field] = incoming_priority
        if incoming.get("evidence_excerpt") and incoming.get("evidence_excerpt") != target.get("evidence_excerpt"):
            target["evidence_excerpt"] = f"{target.get('evidence_excerpt', '')} | {incoming['evidence_excerpt']}"
        if incoming.get("balance_limit_exception_note") and not target.get("balance_limit_exception_note"):
            target["balance_limit_exception_note"] = incoming["balance_limit_exception_note"]
    for row in merged.values():
        field_priorities = row.get("_field_source_priority", {})
        component_limit_priority = max(
            int(field_priorities.get("general_debt_limit_100m", -1)),
            int(field_priorities.get("special_debt_limit_100m", -1)),
        )
        component_balance_priority = max(
            int(field_priorities.get("general_debt_balance_100m", -1)),
            int(field_priorities.get("special_debt_balance_100m", -1)),
        )
        aggregate_limit_priority = int(field_priorities.get("statutory_debt_limit_100m", -1))
        aggregate_balance_priority = int(field_priorities.get("statutory_debt_balance_100m", -1))
        if (
            row.get("general_debt_limit_100m") is not None
            and row.get("special_debt_limit_100m") is not None
            and (
                row.get("statutory_debt_limit_100m") is None
                or component_limit_priority > aggregate_limit_priority
            )
        ):
            row["statutory_debt_limit_100m"] = row["general_debt_limit_100m"] + row["special_debt_limit_100m"]
        if (
            row.get("general_debt_balance_100m") is not None
            and row.get("special_debt_balance_100m") is not None
            and (
                row.get("statutory_debt_balance_100m") is None
                or component_balance_priority > aggregate_balance_priority
            )
        ):
            row["statutory_debt_balance_100m"] = row["general_debt_balance_100m"] + row["special_debt_balance_100m"]
        row.pop("_field_source_priority", None)
    return sorted(merged.values(), key=lambda row: (str(row["metric_year"]), str(row["city_name_cn"])))
