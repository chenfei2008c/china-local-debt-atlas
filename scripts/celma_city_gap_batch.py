"""财政部地方政府债券信息公开平台城市年度批量接口适配器。

该适配器面向全国地级行政单元的缺口补全。平台城市接口使用四位行政代码，
且 ``NDZB`` 请求不能带 ``isAdmin`` 参数；每个指标需要单独请求。原始 JSON
按城市和指标归档后离线合并，避免主表重建依赖实时网络。

只读取精确总指标：0101 债务限额、0601 债务余额、1103 政府性基金收入。
不使用一般/专项分项行替代总额，也不把空响应转换为零。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = "https://www.governbond.org.cn:4443/api/loadBondData.action"
ARCHIVE_DIR = ROOT / "raw" / "province_fiscal" / "celma_gap_batch"
PANEL_PATH = ROOT / "outputs" / "national_prefecture_panel_2018_2026" / "city_macro_fiscal.csv"
SOURCE_GRADE = "A1"
INDICATORS = {
    "01": ("0101", "statutory_debt_limit_100m", "债务限额"),
    "06": ("0601", "statutory_debt_balance_100m", "债务余额"),
    "1103": ("1103", "gov_fund_revenue_100m", "政府性基金收入"),
}
START_YEAR = 2018
END_YEAR = 2025


def _ssl_context() -> ssl.SSLContext:
    for candidate in (
        Path("/etc/ssl/cert.pem"),
        Path("/usr/local/etc/openssl@3/cert.pem"),
        Path("/opt/homebrew/etc/openssl@3/cert.pem"),
    ):
        if candidate.exists():
            return ssl.create_default_context(cafile=str(candidate))
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL_CONTEXT = _ssl_context()


def _decimal(value: Any) -> Decimal | None:
    try:
        if value in (None, "", "null"):
            return None
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def city_code_from_admin_code(value: str) -> str:
    code = "".join(ch for ch in str(value or "") if ch.isdigit())
    return code[:4] if len(code) >= 4 else ""


def load_city_specs(panel_path: Path = PANEL_PATH) -> dict[str, dict[str, str]]:
    specs: dict[str, dict[str, str]] = {}
    with panel_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("metric_year", "").isdigit() or not START_YEAR <= int(row["metric_year"]) <= END_YEAR:
                continue
            code = city_code_from_admin_code(row.get("admin_code_6", ""))
            if not code:
                continue
            specs.setdefault(
                code,
                {
                    "city_id": str(row.get("\ufeffcity_id") or row.get("city_id") or ""),
                    "city_name_cn": str(row.get("city_name_cn") or ""),
                    "province_name": str(row.get("province_name") or ""),
                },
            )
    return specs


def request_indicator(city_code: str, indicator: str, *, timeout: float = 25.0, retries: int = 3) -> bytes:
    url = f"{API_ROOT}?{urlencode({'dataType': 'NDZB', 'adCode': city_code, 'zb': indicator})}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; ChinaLocalDebtAtlas/1.0)",
                    "Referer": "https://www.celma.org.cn/ndsj/index.jhtml",
                    "Accept": "application/json",
                },
            )
            with urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
                return response.read()
        except Exception as exc:  # 网络服务偶发超时，下一次重试
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"接口请求失败 city={city_code} indicator={indicator}: {last_error}")


def download_gap_batch(
    *,
    panel_path: Path = PANEL_PATH,
    archive_dir: Path = ARCHIVE_DIR,
    workers: int = 8,
) -> dict[str, int]:
    specs = load_city_specs(panel_path)
    archive_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(code, indicator) for code in sorted(specs) for indicator in INDICATORS]
    stats = {"jobs": len(jobs), "downloaded": 0, "cached": 0, "failed": 0, "nonempty": 0}

    def one(job: tuple[str, str]) -> tuple[str, str, str, bool, bool]:
        code, indicator = job
        path = archive_dir / f"{code}_{indicator}.json"
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                return code, indicator, "cached", bool(payload.get("data")), False
            except (OSError, ValueError):
                pass
        try:
            body = request_indicator(code, indicator)
            path.write_bytes(body)
            payload = json.loads(body)
            return code, indicator, "downloaded", bool(payload.get("data")), False
        except Exception as exc:
            (archive_dir / f"{code}_{indicator}.error.txt").write_text(str(exc), encoding="utf-8")
            return code, indicator, "failed", False, True

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(one, job) for job in jobs]
        for index, future in enumerate(as_completed(futures), start=1):
            _code, _indicator, status, nonempty, failed = future.result()
            stats[status] += 1
            stats["nonempty"] += int(nonempty)
            stats["failed"] += int(failed)
            if index % 50 == 0:
                print(f"celma gap batch {index}/{len(jobs)}", flush=True)
    return stats


def _source_id(city_code: str, indicator: str) -> str:
    return f"SRC-A1-CELMA-CITY-BATCH-{city_code}-{indicator}"


def _archive_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def load_celma_gap_batch_sources(
    root: Path,
    city_master: Iterable[dict[str, Any]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取归档 JSON，并按精确总指标生成字段级来源。"""
    city_by_code: dict[str, dict[str, Any]] = {}
    for city in city_master:
        code = city_code_from_admin_code(str(city.get("admin_code_6") or city.get("city_code") or ""))
        if code:
            city_by_code.setdefault(code, city)
    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    archive_dir = Path(root) / ARCHIVE_DIR.relative_to(ROOT)
    if not archive_dir.exists():
        return values, sources
    for path in sorted(archive_dir.glob("*_*.json")):
        code, indicator = path.stem.rsplit("_", 1)
        if code not in city_by_code or indicator not in INDICATORS:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        zbid, field, label = INDICATORS[indicator]
        source_id = _source_id(code, indicator)
        source_url = f"{API_ROOT}?{urlencode({'dataType': 'NDZB', 'adCode': code, 'zb': indicator})}"
        city = city_by_code[code]
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        sources.append(
            {
                "source_doc_id": source_id,
                "publisher": "财政部政府债务研究和评估中心",
                "publisher_level": "中央",
                "document_title": f"中国地方政府债券信息公开平台——{city.get('city_name_cn', '')}{label}年度接口",
                "title_source": "official_api",
                "attachment_title": path.name,
                "document_type": "地方政府债券信息公开平台城市年度指标JSON快照",
                "source_url": source_url,
                "landing_page_url": "https://www.celma.org.cn/ndsj/index.jhtml",
                "attachment_url": source_url,
                "canonical_url": source_url,
                "final_resolved_url": source_url,
                "file_name": path.name,
                "mime_type": "application/json",
                "publication_date": str(date.today()),
                "publication_date_raw": "年度接口实时快照",
                "period_end": "2025-12-31",
                "downloaded_at": "",
                "content_hash_sha256": content_hash,
                "archive_uri": f"archive://national-prefecture-panel/{_archive_path(root, path)}",
                "archive_backend": "internal_object",
                "archive_path": _archive_path(root, path),
                "page_count": "",
                "source_grade": SOURCE_GRADE,
                "http_status": "200",
                "access_status": "接口原始响应已归档" if payload.get("data") else "接口公开但该城市指标为空",
                "supersedes_doc_id": "",
                "note": f"公开年度接口精确返回城市总{label}，只选取ZB_ID={zbid}；原始单位为亿元，空响应不转为零。",
            }
        )
        for item in payload.get("data") or []:
            if str(item.get("ZB_ID") or "") != zbid:
                continue
            year = str(item.get("SET_YEAR") or "")
            if not year.isdigit() or not START_YEAR <= int(year) <= END_YEAR:
                continue
            value = _decimal(item.get("AMOUNT"))
            if value is None:
                continue
            key = (str(city.get("city_id") or ""), year)
            record = values.setdefault(
                key,
                {
                    "source_doc_id": source_id,
                    "source_grade": SOURCE_GRADE,
                    "source_format": "json",
                    "data_status": "reported",
                    "data_status_label": f"{year}年财政部地方政府债券信息公开平台年度接口值",
                    "city_id": city.get("city_id"),
                    "city_name": city.get("city_name_cn"),
                    "year": year,
                    "_field_sources": {},
                },
            )
            record[field] = value
            field_source = {
                "source_doc_id": source_id,
                "source_grade": SOURCE_GRADE,
                "source_format": "json",
                "data_status": "reported",
                "data_status_label": f"{year}年财政部地方政府债券信息公开平台年度接口值",
                "source_locator": f"{_archive_path(root, path)}；接口参数=dataType=NDZB&adCode={code}&zb={indicator}；城市={city.get('city_name_cn', '')}；年份={year}；ZB_ID={zbid}",
                "table_name": f"财政部平台{year}年度城市{label}",
                "page_number": "JSON记录",
                f"{field}_raw_100m": value,
                f"{field}_raw_unit": "亿元",
                f"{field}_evidence_excerpt": json.dumps(item, ensure_ascii=False, separators=(",", ":")),
            }
            record["_field_sources"][field] = field_source
            record[f"{field}_raw_100m"] = value
            record[f"{field}_raw_unit"] = "亿元"
            record[f"{field}_evidence_excerpt"] = field_source[f"{field}_evidence_excerpt"]
    return values, sources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="下载所有地级代码的目标指标接口快照")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.download:
        print(download_gap_batch(workers=args.workers), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
