"""地方统计部门地市级经济指标网页表格解析器。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import re
from typing import Any


GUANGDONG_CITY_NAMES = (
    "广州市",
    "深圳市",
    "珠海市",
    "汕头市",
    "佛山市",
    "韶关市",
    "河源市",
    "梅州市",
    "惠州市",
    "汕尾市",
    "东莞市",
    "中山市",
    "江门市",
    "阳江市",
    "湛江市",
    "茂名市",
    "肇庆市",
    "清远市",
    "潮州市",
    "揭阳市",
    "云浮市",
)

_BUDGET_NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?%?")


class _TableParser(HTMLParser):
    """提取 HTML 中所有表格行，保留单元格文本顺序。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _as_decimal(value: str) -> Decimal | None:
    cleaned = value.replace(",", "").replace("，", "").replace("%", "").strip()
    cleaned = re.sub(r"\s+", "", cleaned)
    if not cleaned or cleaned in {"—", "–", "-", "\u2014", "\u2013"}:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _city_name(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\u3000", "")).strip()


def parse_guangdong_city_gdp_html(html_text: str) -> dict[str, dict[str, Any]]:
    """解析广东省统计局“各市地区生产总值初步核算结果”表。

    返回值只保留名称以“市”结尾的地级行政单元，避免把全省、分项或合计行
    误匹配为城市。表格前五列为地区生产总值及三次产业，增长率位于第六列。
    """

    parser = _TableParser()
    parser.feed(html_text)
    result: dict[str, dict[str, Any]] = {}
    for cells in parser.rows:
        if len(cells) < 6:
            continue
        city_name = _city_name(cells[0])
        if not city_name.endswith("市") or city_name in {"全省", "全省市"}:
            continue
        gdp = _as_decimal(cells[1])
        growth = _as_decimal(cells[5])
        if gdp is None or growth is None:
            continue
        result[city_name] = {
            "gdp_current_100m": gdp,
            "gdp_real_growth_pct": growth,
        }
    return result


def parse_guangdong_city_budget_page(page_text: str, field: str) -> dict[str, dict[str, Any]]:
    """解析广东省财政厅地市一般公共预算执行表。

    表中各市行的前三个数字依次为年初预算数、调整预算数、执行数，原始单位为
    万元。只接受广东省 21 个地级市白名单，避免把区域合计、说明文字或横琴合作
    区行误识别为地级市；返回值同时保留原始执行数，供字段血缘引用。
    """

    if field not in {"general_public_revenue_100m", "general_public_expenditure_100m"}:
        raise ValueError(f"不支持的广东地市财政字段: {field}")

    result: dict[str, dict[str, Any]] = {}
    for raw_line in page_text.splitlines():
        compact = re.sub(r"\s+", "", raw_line)
        city_name = next((name for name in GUANGDONG_CITY_NAMES if compact.startswith(name)), None)
        if city_name is None:
            continue
        suffix = raw_line
        for character in city_name:
            suffix = re.sub(r"^\s*" + re.escape(character), "", suffix, count=1)
        tokens = _BUDGET_NUMBER_RE.findall(suffix)
        if len(tokens) < 3:
            continue
        execution_raw = _as_decimal(tokens[2])
        if execution_raw is None:
            continue
        result[city_name] = {
            field: execution_raw / Decimal("10000"),
            f"{field}_raw_10k": execution_raw,
        }
    return result


def parse_city_fund_revenue_text(text: str) -> Decimal | None:
    """从城市官方预算报告正文提取 2025 年全市政府性基金预算收入。"""

    compact = re.sub(r"\s+", "", text)
    patterns = (
        r"2025年[,，]?全市政府性基金预算收入(-?\d[\d,]*(?:\.\d+)?)亿元",
        r"政府性基金预算执行情况。全市政府性基金预算收入(-?\d[\d,]*(?:\.\d+)?)亿元",
    )
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            return _as_decimal(match.group(1))
    return None
