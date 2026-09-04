"""按指标全量索引批量冻结聚汇城市序列。

逐城逐页检索会重复请求同一指标索引，且在网络代理较慢时容易长时间阻塞。
本模块先抓取一个指标的全量检索索引，再按标题严格筛选目标地级行政单元的
全市总量序列，最后只冻结命中的序列详情。它只扩展原始快照，不直接修改主表；
主表仍由现有采集器重建，所有新增值继续作为 B2 公开二手精确序列登记。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from scripts.gotohui_snapshot_collector import (
        API_ROOT,
        METRIC_FIELDS,
        QUERY_WORDS,
        SNAPSHOT_PATH,
        YEAR_RANGE,
        _read_city_targets,
        merge_snapshot_series,
    )
except ModuleNotFoundError:  # 允许以 python scripts/... 直接运行
    from gotohui_snapshot_collector import (  # type: ignore
        API_ROOT,
        METRIC_FIELDS,
        QUERY_WORDS,
        SNAPSHOT_PATH,
        YEAR_RANGE,
        _read_city_targets,
        merge_snapshot_series,
    )


CITY_TOTAL_SUFFIXES = {
    "fund": (
        "地方政府性基金收入",
        "政府性基金收入",
        "地方财政收入:政府性基金收入",
    ),
    "limit": ("地方政府债务限额",),
}


def acceptable_city_total_series_title(
    metric: str, city_name: str, title: str
) -> bool:
    """只接受标题精确匹配的城市全市总量序列。

    特意不接受“本级”、区县、预算数、土地出让收入等标题，避免把行政范围
    或指标层级混入全国主表。
    """

    return title.strip() in {
        f"{city_name}{suffix}"
        for suffix in CITY_TOTAL_SUFFIXES.get(metric, ())
    }


def select_city_series_from_index(
    metric: str,
    cities_by_id: Mapping[str, str],
    items: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """从指标索引中筛选目标城市，并把城市代码写入索引条目。"""

    title_to_city = {
        f"{city_name}{suffix}": (str(city_id), str(city_name))
        for city_id, city_name in cities_by_id.items()
        for suffix in CITY_TOTAL_SUFFIXES.get(metric, ())
    }
    selected: dict[str, dict[str, Any]] = {}
    for item in items:
        title = str(item.get("title") or "").strip()
        city = title_to_city.get(title)
        series_id = str(item.get("id") or "")
        if city is None or not series_id:
            continue
        record = dict(item)
        record["city_id"], record["city_name"] = city
        selected[series_id] = record
    return [selected[key] for key in sorted(selected)]


def _json_request_short(url: str, timeout: float, retries: int = 1) -> dict[str, Any] | None:
    context = ssl._create_unverified_context()
    for attempt in range(max(1, retries)):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                },
            )
            with urlopen(request, timeout=timeout, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            if attempt + 1 < max(1, retries):
                continue
    return None


def _index_page_url(metric: str, page: int) -> str:
    query = urlencode(
        {
            "word": QUERY_WORDS[metric],
            "channel": "data",
            "page": page,
        }
    )
    return f"{API_ROOT}/search?{query}"


def fetch_metric_index(
    metric: str,
    *,
    workers: int = 16,
    timeout: float = 12.0,
    retries: int = 1,
    max_pages: int | None = None,
) -> tuple[list[dict[str, Any]], list[int]]:
    """抓取一个指标的全量索引，返回条目和失败页码。"""

    first = _json_request_short(
        _index_page_url(metric, 1), timeout=timeout, retries=retries
    )
    if not first:
        return [], [1]
    data = first.get("data") or {}
    total_pages = int(data.get("total_page") or 1)
    if max_pages is not None:
        total_pages = min(total_pages, max(1, max_pages))
    pages: dict[int, list[dict[str, Any]]] = {
        1: list(data.get("list") or [])
    }
    failures: list[int] = []

    def fetch(page: int) -> tuple[int, list[dict[str, Any]] | None]:
        payload = _json_request_short(
            _index_page_url(metric, page), timeout=timeout, retries=retries
        )
        return page, None if not payload else list((payload.get("data") or {}).get("list") or [])

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(fetch, page) for page in range(2, total_pages + 1)]
        for future in as_completed(futures):
            page, values = future.result()
            if values is None:
                failures.append(page)
            else:
                pages[page] = values
    items: list[dict[str, Any]] = []
    for page in sorted(pages):
        items.extend(pages[page])
    return items, sorted(failures)


def _freeze_series_short(
    item: Mapping[str, Any], *, metric: str, timeout: float, retries: int
) -> dict[str, Any] | None:
    series_id = str(item.get("id") or "")
    payload = _json_request_short(
        f"{API_ROOT}/pc/macro/chart/{series_id}",
        timeout=timeout,
        retries=retries,
    )
    if not payload:
        return None
    data = payload.get("data") or {}
    labels = [str(value) for value in data.get("labels") or []]
    values = data.get("values") or []
    allowed_years = {str(year) for year in YEAR_RANGE}
    rows = [
        {"year": year, "value": value}
        for year, value in zip(labels, values)
        if year in allowed_years and value not in (None, "", "-", "—", "–")
    ]
    if not rows:
        return None
    chart_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "city_id": str(item["city_id"]),
        "city_name": str(item["city_name"]),
        "metric": metric,
        "series_id": series_id,
        "title": str(item.get("title") or data.get("title") or ""),
        "unit": str(item.get("unit") or data.get("unit") or ""),
        "source": str(item.get("source") or ""),
        "data_range": str(item.get("data_range") or ""),
        "url": str(item.get("url") or f"https://www.gotohui.com/show-{series_id}"),
        "content_hash_sha256": hashlib.sha256(chart_bytes).hexdigest(),
        "rows": rows,
    }


def collect_batch(
    root: Path,
    metrics: set[str],
    *,
    index_workers: int = 16,
    freeze_workers: int = 16,
    timeout: float = 12.0,
    retries: int = 1,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """批量扩展快照并返回可审计汇总。"""

    snapshot_path = root / SNAPSHOT_PATH
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    existing = list(payload.get("series") or [])
    seen_ids = {str(item.get("series_id")) for item in existing}
    additions: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"metrics": {}}

    for metric in sorted(metrics):
        target_rows = _read_city_targets(root, {metric})
        cities_by_id = {
            city_id: city_name for _metric, city_id, city_name in target_rows
        }
        index_items, failed_pages = fetch_metric_index(
            metric,
            workers=index_workers,
            timeout=timeout,
            retries=retries,
            max_pages=max_pages,
        )
        selected = select_city_series_from_index(metric, cities_by_id, index_items)
        to_freeze = [
            item for item in selected if str(item.get("id")) not in seen_ids
        ]
        frozen: list[dict[str, Any]] = []

        def freeze(item: Mapping[str, Any]) -> dict[str, Any] | None:
            return _freeze_series_short(
                item, metric=metric, timeout=timeout, retries=retries
            )

        with ThreadPoolExecutor(max_workers=max(1, freeze_workers)) as executor:
            futures = [executor.submit(freeze, item) for item in to_freeze]
            for future in as_completed(futures):
                result = future.result()
                if result is not None and result["series_id"] not in seen_ids:
                    seen_ids.add(result["series_id"])
                    frozen.append(result)
        additions.extend(frozen)
        summary["metrics"][metric] = {
            "target_cities": len(cities_by_id),
            "index_items": len(index_items),
            "selected_series": len(selected),
            "frozen_series": len(frozen),
            "frozen_cells": sum(len(item["rows"]) for item in frozen),
            "failed_index_pages": failed_pages,
        }

    merged = merge_snapshot_series(existing, additions)
    payload["series"] = merged
    snapshot_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary["new_series"] = len(additions)
    summary["new_cells"] = sum(len(item.get("rows") or []) for item in additions)
    summary["total_series"] = len(merged)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="按指标全量索引批量扩展聚汇序列快照")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--metrics", default="fund,limit")
    parser.add_argument("--index-workers", type=int, default=16)
    parser.add_argument("--freeze-workers", type=int, default=16)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=None)
    args = parser.parse_args()
    metrics = {item.strip() for item in args.metrics.split(",") if item.strip()}
    unknown = metrics - set(METRIC_FIELDS)
    if unknown:
        parser.error(f"未知指标：{sorted(unknown)}")
    result = collect_batch(
        args.root,
        metrics,
        index_workers=args.index_workers,
        freeze_workers=args.freeze_workers,
        timeout=args.timeout,
        retries=args.retries,
        max_pages=args.max_pages,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
