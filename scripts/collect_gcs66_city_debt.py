#!/usr/bin/env python3
"""从公开预算报告库批量抓取市级法定政府债务余额。

该脚本只把报告中明确披露的“政府债务余额”写入次级来源暂存表；不把
城投债、隐性债务或政府性基金债券发行额当作法定债务余额。来源等级固定为
B2，后续应优先用财政厅、人大预算/决算公开表升级。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import re
import ssl
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MISSING = ROOT / "outputs" / "national_prefecture_panel_2018_2026" / "missing_statutory_debt_2018_2025.csv"
DEFAULT_OUTPUT = ROOT / "raw" / "province_debt" / "secondary" / "gcs66_city_debt_2018_2025.csv"
DEFAULT_ARCHIVE = ROOT / "raw" / "province_debt" / "secondary" / "gcs66"
DEFAULT_FUND_PANEL = ROOT / "outputs" / "national_prefecture_panel_2018_2026" / "city_macro_fiscal.csv"
DEFAULT_FUND_OUTPUT = ROOT / "raw" / "province_fiscal" / "secondary" / "gcs66_city_fund_2018_2025.csv"
DEFAULT_FUND_ARCHIVE = ROOT / "raw" / "province_fiscal" / "secondary" / "gcs66_fund"
SEARCH_ROOT = "https://www.gcs66.com"
SEARCH_PATH = "/documents/list.html"
SOURCE_GRADE = "B2"


def _ssl_context() -> ssl.SSLContext:
    """显式加载 macOS/Python 未自动发现的系统 CA 证书。"""
    for candidate in (
        Path("/etc/ssl/cert.pem"),
        Path("/usr/local/etc/openssl@3/cert.pem"),
        Path("/opt/homebrew/etc/openssl@3/cert.pem"),
    ):
        if candidate.exists():
            return ssl.create_default_context(cafile=str(candidate))
    return ssl.create_default_context()


SSL_CONTEXT = _ssl_context()


def _number(value: str) -> Decimal:
    return Decimal(value.replace(",", "").replace(" ", ""))


def _plain_text(value: str) -> str:
    value = html.unescape(value or "").replace("\xa0", " ")
    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", "", value)


def archive_path_value(path: Path) -> str:
    """返回可写入血缘的归档路径，支持测试或临时目录位于仓库外。"""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _excerpt(text: str, needle: str, radius: int = 120) -> str:
    position = text.find(needle)
    if position < 0:
        return text[: radius * 2]
    return text[max(0, position - radius) : position + radius]


def _candidate_sentences(text: str, year: int) -> Iterable[str]:
    normalized = _plain_text(text)
    for sentence in re.split(r"[。；!?！？]", normalized):
        if str(year) in sentence and "债务余额" in sentence:
            yield sentence


def extract_fund_fact(
    text: str,
    *,
    city_name: str,
    province_name: str,
    year: int,
    source_doc_id: str,
    source_url: str,
) -> dict[str, Any] | None:
    """提取报告中指定城市和年份的全市政府性基金收入实际数。

    只接受同一语句内同时出现年度、全市/全州等全域口径、基金收入和
    实际完成/执行/决算表述的数值。预算安排数、年中累计数、市本级数和
    区县数均拒绝，避免把预算草案或局部口径写入主表。
    """
    normalized = _plain_text(text)
    sentences = re.split(r"[。；!?！？]", normalized)
    scope = r"(?:全市|全州|全区|全盟|全地区)"
    fund = r"(?:政府性基金预算收入|政府性基金收入)"
    amount = r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(亿元|万元)"
    pattern = re.compile(
        rf"{year}年[^。；!?！？]*?{scope}[^。；!?！？]*?{fund}"
        rf"[^。；!?！？]*?(?:实际完成|执行数|决算数|完成)(?:为|是|：|:)?\s*{amount}"
    )
    for sentence in sentences:
        if city_name not in sentence and "全市" not in sentence and "全州" not in sentence:
            continue
        if any(marker in sentence for marker in ("1-11", "1至11", "截至", "预算安排", "拟安排")):
            continue
        match = pattern.search(sentence)
        if not match:
            continue
        raw_value = _number(match.group(1))
        raw_unit = match.group(2)
        normalized_value = raw_value if raw_unit == "亿元" else raw_value * Decimal("0.0001")
        return {
            "city_name_cn": city_name,
            "province_name": province_name,
            "metric_year": year,
            "geo_scope": "prefecture_whole",
            "source_doc_id": source_doc_id,
            "line_number": "",
            "table_name": f"{year}年城市财政预算执行报告中的全市政府性基金收入",
            "evidence_excerpt": sentence,
            "unit_factor": Decimal("1") if raw_unit == "亿元" else Decimal("0.0001"),
            "value_origin": "disclosed",
            "source_url": source_url,
            "source_grade": SOURCE_GRADE,
            "gov_fund_revenue_100m": normalized_value,
            "gov_fund_revenue_raw_100m": raw_value,
            "gov_fund_revenue_raw_unit": raw_unit,
            "data_status": "final" if "决算" in sentence else "execution",
        }


def extract_debt_fact(
    text: str,
    *,
    city_name: str,
    province_name: str,
    year: int,
    source_doc_id: str,
    source_url: str,
) -> dict[str, Any] | None:
    """提取报告中指定城市和年份的法定债务余额事实。"""
    city_key = _plain_text(city_name)
    candidates = list(_candidate_sentences(text, year))
    if not candidates:
        return None
    total_pattern = re.compile(
        r"(?:地方政府|政府)?债务余额(?:合计)?(?:为|是|：|:)?"
        r"([0-9][0-9,]*(?:\.[0-9]+)?)亿元"
    )
    component_pattern = {
        "general": re.compile(r"一般债务(?:余额)?(?:为|是|：|:)?([0-9][0-9,]*(?:\.[0-9]+)?)亿元"),
        "special": re.compile(r"专项债务(?:余额)?(?:为|是|：|:)?([0-9][0-9,]*(?:\.[0-9]+)?)亿元"),
    }
    for sentence in candidates:
        if city_key not in sentence and "全市" not in sentence and "全区" not in sentence and "全州" not in sentence and "全省" not in sentence:
            continue
        total_match = total_pattern.search(sentence)
        if not total_match:
            continue
        total = _number(total_match.group(1))
        general_match = component_pattern["general"].search(sentence)
        special_match = component_pattern["special"].search(sentence)
        general = _number(general_match.group(1)) if general_match else None
        special = _number(special_match.group(1)) if special_match else None
        return {
            "city_name_cn": city_name,
            "province_name": province_name,
            "metric_year": year,
            "geo_scope": "prefecture_whole",
            "source_doc_id": source_doc_id,
            "line_number": "",
            "table_name": f"{year}年市级财政预算/决算报告中的政府债务余额",
            "evidence_excerpt": sentence,
            "unit_factor": Decimal("1"),
            "value_origin": "disclosed",
            "source_url": source_url,
            "source_grade": SOURCE_GRADE,
            "general_debt_limit_100m": None,
            "general_debt_balance_100m": general,
            "special_debt_limit_100m": None,
            "special_debt_balance_100m": special,
            "statutory_debt_limit_100m": None,
            "statutory_debt_balance_100m": total,
        }
    return None


@dataclass(frozen=True)
class SearchDocument:
    title: str
    url: str


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href = ""
        self._chunks: list[str] = []
        self.links: list[SearchDocument] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        href = values.get("href") or ""
        if "/document_detail/" in href:
            self._href = href
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            title = _plain_text("".join(self._chunks))
            if title:
                self.links.append(SearchDocument(title=title, url=urljoin(SEARCH_ROOT, self._href)))
            self._href = ""
            self._chunks = []


def _get(url: str, *, timeout: float = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ChinaLocalDebtAtlas/1.0)",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
        return response.read().decode("utf-8", "ignore")


def search_documents(province_name: str, city_name: str, year: int | None = None) -> list[SearchDocument]:
    year_label = f"{year}年" if year is not None else ""
    topic = f"{province_name}{city_name}{year_label}财政预算执行政府债务"
    url = f"{SEARCH_ROOT}{SEARCH_PATH}?{urlencode({'topic': topic})}"
    parser = _AnchorParser()
    parser.feed(_get(url))
    unique: dict[str, SearchDocument] = {}
    for document in parser.links:
        unique.setdefault(document.url, document)
    return list(unique.values())


def _city_document(title: str, city_name: str) -> bool:
    title = _plain_text(title)
    city = _plain_text(city_name)
    position = title.find(city)
    if position < 0:
        return False
    after = title[position + len(city) :]
    if after and not re.match(r"(?:人民政府|政府|财政局|财政预算|预算)", after):
        return False
    return "财政" in title or "预算" in title or "决算" in title


def _candidate_document(document: SearchDocument, city_name: str, years: set[int]) -> bool:
    if not _city_document(document.title, city_name):
        return False
    years_in_title = {int(value) for value in re.findall(r"20\d{2}", document.title)}
    return bool(years & years_in_title or {year + 1 for year in years} & years_in_title)


def _candidate_fund_document(document: SearchDocument, city_name: str, years: set[int]) -> bool:
    """筛选地级市本身的预算报告，排除同名下辖区县报告。"""
    title = _plain_text(document.title)
    city = _plain_text(city_name)
    position = title.find(city)
    if position < 0:
        return False
    after = title[position + len(city) :]
    if after and not re.match(r"(?:20\d{2}|人民政府|政府|财政局|财政预算|预算)", after):
        return False
    years_in_title = {int(value) for value in re.findall(r"20\d{2}", title)}
    return bool(years & years_in_title) and any(word in title for word in ("财政", "预算", "决算"))


def collect_city(
    province_name: str,
    city_name: str,
    years: set[int],
    archive_dir: Path,
    *,
    max_documents: int = 18,
) -> list[dict[str, Any]]:
    documents = [document for document in search_documents(province_name, city_name) if _candidate_document(document, city_name, years)]
    documents = documents[:max_documents]
    facts: dict[int, dict[str, Any]] = {}
    archive_dir.mkdir(parents=True, exist_ok=True)
    for document in documents:
        try:
            body = _get(document.url)
        except Exception:
            continue
        text = _plain_text(body)
        for year in sorted(years):
            if year in facts:
                continue
            source_id = f"SRC-SECONDARY-GCS66-{hashlib.sha1(document.url.encode()).hexdigest()[:12].upper()}"
            fact = extract_debt_fact(
                text,
                city_name=city_name,
                province_name=province_name,
                year=year,
                source_doc_id=source_id,
                source_url=document.url,
            )
            if fact:
                facts[year] = fact
                archive_name = f"{province_name}_{city_name}_{year}_{hashlib.sha1(document.url.encode()).hexdigest()[:10]}.html"
                (archive_dir / archive_name).write_text(body, encoding="utf-8")
        time.sleep(0.05)
        if facts.keys() >= years:
            break
    return list(facts.values())


def collect_city_fund(
    province_name: str,
    city_name: str,
    years: set[int],
    archive_dir: Path,
    *,
    max_documents: int = 18,
) -> list[dict[str, Any]]:
    """从GCS66城市预算报告中提取全市基金收入执行/决算数。"""
    documents_by_url: dict[str, SearchDocument] = {}
    for year in sorted(years):
        for search_year in (year, year + 1):
            for document in search_documents(province_name, city_name, year=search_year):
                if _candidate_fund_document(document, city_name, {year}):
                    documents_by_url.setdefault(document.url, document)
    documents = list(documents_by_url.values())[:max_documents]
    facts: dict[int, dict[str, Any]] = {}
    archive_dir.mkdir(parents=True, exist_ok=True)
    for document in documents:
        try:
            body = _get(document.url)
        except Exception:
            continue
        for year in sorted(years):
            if year in facts:
                continue
            source_id = f"SRC-SECONDARY-GCS66-FUND-{hashlib.sha1(document.url.encode()).hexdigest()[:12].upper()}"
            fact = extract_fund_fact(
                body,
                city_name=city_name,
                province_name=province_name,
                year=year,
                source_doc_id=source_id,
                source_url=document.url,
            )
            if fact:
                fact["document_title"] = document.title
                archive_name = f"{province_name}_{city_name}_{year}_{hashlib.sha1(document.url.encode()).hexdigest()[:10]}.html"
                archive_path = archive_dir / archive_name
                archive_path.write_text(body, encoding="utf-8")
                fact["archive_path"] = archive_path_value(archive_path)
                facts[year] = fact
        time.sleep(0.05)
        if facts.keys() >= years:
            break
    return list(facts.values())


def _read_missing(path: Path, top_combinations: int) -> dict[tuple[str, str], dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    counts = Counter((row["province_name"], int(row["metric_year"])) for row in rows)
    selected = {key for key, _count in counts.most_common(top_combinations)}
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["province_name"], row["city_name_cn"])
        if (row["province_name"], int(row["metric_year"])) not in selected:
            continue
        output.setdefault(key, {"province_name": row["province_name"], "city_name_cn": row["city_name_cn"], "years": set()})["years"].add(int(row["metric_year"]))
    return output


def _read_missing_fund(path: Path, years: set[int], top_combinations: int) -> dict[tuple[str, str], dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if int(row["metric_year"]) in years and not row.get("gov_fund_revenue_100m")]
    counts = Counter((row["province_name"], int(row["metric_year"])) for row in rows)
    selected = {key for key, _count in counts.most_common(top_combinations)}
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        combination = (row["province_name"], int(row["metric_year"]))
        if combination not in selected:
            continue
        key = (row["province_name"], row["city_name_cn"])
        output.setdefault(
            key,
            {"province_name": row["province_name"], "city_name_cn": row["city_name_cn"], "years": set()},
        )["years"].add(int(row["metric_year"]))
    return output


def _write_output(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    fields = [
        "city_id", "city_name_cn", "province_name", "metric_year", "statutory_debt_balance_100m",
        "general_debt_balance_100m", "special_debt_balance_100m", "value_origin", "source_doc_id",
        "source_url", "evidence_excerpt", "source_grade",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: str(row.get(field, "")) if row.get(field) is not None else "" for field in fields})


def _write_fund_output(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    fields = [
        "city_id", "city_name_cn", "province_name", "metric_year", "gov_fund_revenue_100m",
        "gov_fund_revenue_raw_100m", "gov_fund_revenue_raw_unit", "data_status", "value_origin",
        "source_doc_id", "source_url", "document_title", "archive_path", "evidence_excerpt", "source_grade",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: str(row.get(field, "")) if row.get(field) is not None else "" for field in fields})


def load_gcs66_city_fund_sources(
    root: Path,
    city_master: Iterable[dict[str, Any]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取并严格校验 GCS66 全市基金收入批次，转换为主表合并接口。"""
    batch_path = Path(root) / "raw/province_fiscal/secondary/gcs66_city_fund_2018_2025.csv"
    if not batch_path.exists():
        return {}, []
    valid_keys: dict[tuple[str, str], dict[str, Any]] = {}
    for city in city_master:
        city_id = str(city.get("city_id") or "")
        year = str(city.get("metric_year") or "")
        if city_id and year:
            valid_keys[(city_id, year)] = city
    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    with batch_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            city_id = str(row.get("city_id") or "")
            try:
                year = str(int(row.get("metric_year") or ""))
                value = Decimal(str(row.get("gov_fund_revenue_100m") or "").replace(",", ""))
            except (ValueError, ArithmeticError):
                continue
            key = (city_id, year)
            if key not in valid_keys or not (2018 <= int(year) <= 2025):
                continue
            if str(row.get("source_grade") or "") != SOURCE_GRADE:
                continue
            source_id = str(row.get("source_doc_id") or "")
            source_url = str(row.get("source_url") or "")
            if not source_id or not source_url or value < 0:
                continue
            city = valid_keys[key]
            if str(row.get("city_name_cn") or "") != str(city.get("city_name_cn") or ""):
                continue
            archive_path = str(row.get("archive_path") or "")
            archive_file = Path(archive_path)
            if not archive_file.is_absolute():
                archive_file = Path(root) / archive_file
            content_hash = ""
            if archive_file.exists() and archive_file.is_file():
                content_hash = hashlib.sha256(archive_file.read_bytes()).hexdigest()
            data_status = str(row.get("data_status") or "execution")
            status_label = "决算数" if data_status == "final" else "执行数"
            data_status_label = f"{year}年{status_label}"
            source_locator = (
                f"{archive_path or source_url}；报告正文；城市={city.get('city_name_cn', '')}；"
                f"{data_status_label}；行政范围=全市"
            )
            record: dict[str, Any] = {
                "gov_fund_revenue_100m": value,
                "gov_fund_revenue_raw_100m": str(row.get("gov_fund_revenue_raw_100m") or value),
                "gov_fund_revenue_raw_unit": str(row.get("gov_fund_revenue_raw_unit") or "亿元"),
                "gov_fund_revenue_evidence_excerpt": str(row.get("evidence_excerpt") or ""),
                "source_doc_id": source_id,
                "source_grade": SOURCE_GRADE,
                "source_format": "html",
                "data_status": data_status,
                "data_status_label": data_status_label,
                "value_origin": str(row.get("value_origin") or "disclosed"),
                "source_locator": source_locator,
                "table_name": str(row.get("table_name") or f"{year}年全市政府性基金预算收入执行情况"),
                "_field_sources": {},
            }
            record["_field_sources"] = {"gov_fund_revenue_100m": dict(record)}
            prior = values.get(key)
            if prior is None:
                values[key] = record
            elif prior.get("gov_fund_revenue_100m") != record.get("gov_fund_revenue_100m"):
                # 同一城市年度出现冲突时保留首个可审计事实，由后续复核队列处理。
                continue
            if source_id in seen_source_ids:
                continue
            seen_source_ids.add(source_id)
            sources.append(
                {
                    "source_doc_id": source_id,
                    "publisher": "GCS66",
                    "publisher_level": "公开预算报告转载",
                    "document_title": str(row.get("document_title") or "城市财政预算执行报告"),
                    "title_source": "gcs66_document_detail",
                    "attachment_title": str(row.get("document_title") or "城市财政预算执行报告"),
                    "document_type": "城市财政预算执行/决算报告（全市政府性基金收入）",
                    "source_url": source_url,
                    "landing_page_url": source_url,
                    "attachment_url": source_url,
                    "canonical_url": source_url,
                    "final_resolved_url": source_url,
                    "file_name": archive_file.name if archive_file.name else "",
                    "mime_type": "text/html",
                    "publication_date": "",
                    "publication_date_raw": "",
                    "period_end": f"{year}-12-31",
                    "downloaded_at": "",
                    "content_hash_sha256": content_hash,
                    "archive_uri": f"archive://national-prefecture-panel/{archive_path}" if archive_path else "",
                    "archive_backend": "internal_object" if archive_path else "",
                    "archive_path": archive_path,
                    "page_count": "",
                    "source_grade": SOURCE_GRADE,
                    "http_status": "200",
                    "access_status": "精确全市口径来源已归档",
                    "supersedes_doc_id": "",
                    "note": "仅接收 GCS66 报告正文中年度、全市口径、实际完成/执行数或决算数；排除预算安排、年中累计数、市本级和区县口径。",
                }
            )
    return values, sources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--missing", type=Path, default=DEFAULT_MISSING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--top-combinations", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-documents", type=int, default=18)
    parser.add_argument("--fund", action="store_true", help="采集城市政府性基金收入，而不是债务余额")
    parser.add_argument("--panel", type=Path, default=DEFAULT_FUND_PANEL)
    parser.add_argument("--fund-years", default="2018,2019,2020,2021,2022,2023,2024,2025")
    args = parser.parse_args()

    if args.fund:
        years = {int(item) for item in args.fund_years.split(",") if item.strip()}
        targets = _read_missing_fund(args.panel, years, args.top_combinations)
        # 主表保留稳定城市代码，便于合并器做严格身份校验。
        city_ids = {
            (row["province_name"], row["city_name_cn"], int(row["metric_year"])): row["city_id"]
            for row in csv.DictReader(args.panel.open(encoding="utf-8-sig"))
        }
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {
                executor.submit(
                    collect_city_fund,
                    item["province_name"],
                    item["city_name_cn"],
                    item["years"],
                    args.archive_dir if args.archive_dir != DEFAULT_ARCHIVE else DEFAULT_FUND_ARCHIVE,
                    max_documents=args.max_documents,
                ): key
                for key, item in targets.items()
            }
            for future in as_completed(futures):
                key = futures[future]
                try:
                    rows = future.result()
                except Exception as exc:
                    print(f"ERROR {key[0]} {key[1]}: {exc}")
                    rows = []
                for row in rows:
                    row["city_id"] = city_ids.get((row["province_name"], row["city_name_cn"], int(row["metric_year"])), "")
                print(f"{key[0]} {key[1]}: {len(rows)} rows", flush=True)
                results.extend(rows)
        results.sort(key=lambda row: (row["province_name"], row["city_name_cn"], row["metric_year"]))
        output = args.output if args.output != DEFAULT_OUTPUT else DEFAULT_FUND_OUTPUT
        output.parent.mkdir(parents=True, exist_ok=True)
        _write_fund_output(output, results)
        print(f"基金采集城市数：{len(targets)}")
        print(f"基金采集记录数：{len(results)}")
        print(f"输出：{output}")
        return 0

    targets = _read_missing(args.missing, args.top_combinations)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                collect_city,
                item["province_name"],
                item["city_name_cn"],
                item["years"],
                args.archive_dir,
                max_documents=args.max_documents,
            ): key
            for key, item in targets.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                rows = future.result()
            except Exception as exc:  # 保留其他城市任务继续执行
                print(f"ERROR {key[0]} {key[1]}: {exc}")
                rows = []
            print(f"{key[0]} {key[1]}: {len(rows)} rows", flush=True)
            results.extend(rows)
    results.sort(key=lambda row: (row["province_name"], row["city_name_cn"], row["metric_year"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write_output(args.output, results)
    print(f"抓取城市数：{len(targets)}")
    print(f"抓取记录数：{len(results)}")
    print(f"输出：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
