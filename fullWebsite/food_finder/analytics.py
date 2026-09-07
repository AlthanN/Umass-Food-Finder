"""Privacy-conscious aggregate search analytics repositories."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Protocol

from .storage import create_upstash_client


ANALYTICS_PREFIX = "umass-food-finder:analytics:v1"
LIFETIME_SEARCHES_KEY = f"{ANALYTICS_PREFIX}:searches:lifetime"
LIFETIME_SEARCHERS_KEY = f"{ANALYTICS_PREFIX}:searchers:lifetime"
DAILY_RETENTION_SECONDS = 90 * 24 * 60 * 60


class SearchAnalyticsRepository(Protocol):
    def record_search(self, visitor_id: str, day: date) -> None: ...

    def get_report(self, end_date: date, *, days: int = 30) -> dict: ...


class InMemorySearchAnalyticsRepository:
    """Process-local analytics used during development and tests."""

    def __init__(self) -> None:
        self.total_searches = 0
        self.lifetime_searchers: set[str] = set()
        self.daily_searches: dict[date, int] = defaultdict(int)
        self.daily_searchers: dict[date, set[str]] = defaultdict(set)

    def record_search(self, visitor_id: str, day: date) -> None:
        self.total_searches += 1
        self.lifetime_searchers.add(visitor_id)
        self.daily_searches[day] += 1
        self.daily_searchers[day].add(visitor_id)

    def get_report(self, end_date: date, *, days: int = 30) -> dict:
        dates = _report_dates(end_date, days)
        daily = [
            _metric_row(
                day.isoformat(),
                self.daily_searches.get(day, 0),
                len(self.daily_searchers.get(day, set())),
            )
            for day in dates
        ]
        return _report(self.total_searches, len(self.lifetime_searchers), daily)


class UpstashSearchAnalyticsRepository:
    """Aggregate counters backed by serverless-friendly Upstash Redis."""

    def __init__(self, client: Any | None = None) -> None:
        self.client = client or create_upstash_client()

    def record_search(self, visitor_id: str, day: date) -> None:
        searches_key, searchers_key = _daily_keys(day)
        pipeline = self.client.pipeline()
        pipeline.incr(LIFETIME_SEARCHES_KEY)
        pipeline.pfadd(LIFETIME_SEARCHERS_KEY, visitor_id)
        pipeline.incr(searches_key)
        pipeline.expire(searches_key, DAILY_RETENTION_SECONDS)
        pipeline.pfadd(searchers_key, visitor_id)
        pipeline.expire(searchers_key, DAILY_RETENTION_SECONDS)
        pipeline.exec()

    def get_report(self, end_date: date, *, days: int = 30) -> dict:
        dates = _report_dates(end_date, days)
        pipeline = self.client.pipeline()
        pipeline.get(LIFETIME_SEARCHES_KEY)
        pipeline.pfcount(LIFETIME_SEARCHERS_KEY)
        for day in dates:
            searches_key, searchers_key = _daily_keys(day)
            pipeline.get(searches_key)
            pipeline.pfcount(searchers_key)

        values = pipeline.exec()
        total_searches = _as_int(values[0])
        lifetime_searchers = _as_int(values[1])
        daily = []
        for index, day in enumerate(dates):
            offset = 2 + index * 2
            daily.append(
                _metric_row(
                    day.isoformat(),
                    _as_int(values[offset]),
                    _as_int(values[offset + 1]),
                )
            )
        return _report(total_searches, lifetime_searchers, daily)


def _daily_keys(day: date) -> tuple[str, str]:
    suffix = day.isoformat()
    return (
        f"{ANALYTICS_PREFIX}:searches:daily:{suffix}",
        f"{ANALYTICS_PREFIX}:searchers:daily:{suffix}",
    )


def _report_dates(end_date: date, days: int) -> list[date]:
    if days < 1:
        raise ValueError("days must be positive")
    return [end_date - timedelta(days=offset) for offset in reversed(range(days))]


def _metric_row(label: str, searches: int, searchers: int) -> dict:
    return {
        "date": label,
        "searches": searches,
        "unique_searchers": searchers,
        "searches_per_searcher": _average(searches, searchers),
    }


def _report(total_searches: int, lifetime_searchers: int, daily: list[dict]) -> dict:
    return {
        "lifetime": {
            "searches": total_searches,
            "unique_searchers": lifetime_searchers,
            "searches_per_searcher": _average(total_searches, lifetime_searchers),
        },
        "daily": daily,
    }


def _average(searches: int, searchers: int) -> float:
    return round(searches / searchers, 2) if searchers else 0.0


def _as_int(value: Any) -> int:
    return int(value) if value is not None else 0
