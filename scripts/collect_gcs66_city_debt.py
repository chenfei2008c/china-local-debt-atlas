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
    return re.sub(r"\s+", "", value)


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


def search_documents(province_name: str, city_name: str) -> list[SearchDocument]:
    topic = f"{province_name}{city_name}财政预算执行政府债务"
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--missing", type=Path, default=DEFAULT_MISSING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--top-combinations", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-documents", type=int, default=18)
    args = parser.parse_args()

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
