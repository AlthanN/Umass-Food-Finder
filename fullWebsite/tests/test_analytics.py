from datetime import date

from food_finder.analytics import (
    DAILY_RETENTION_SECONDS,
    LIFETIME_SEARCHERS_KEY,
    LIFETIME_SEARCHES_KEY,
    InMemorySearchAnalyticsRepository,
    UpstashSearchAnalyticsRepository,
)


class FakePipeline:
    def __init__(self, results=None):
        self.commands = []
        self.results = results or []

    def _add(self, name, *arguments):
        self.commands.append((name, *arguments))
        return self

    def incr(self, key):
        return self._add("incr", key)

    def get(self, key):
        return self._add("get", key)

    def pfadd(self, key, visitor_id):
        return self._add("pfadd", key, visitor_id)

    def pfcount(self, key):
        return self._add("pfcount", key)

    def expire(self, key, seconds):
        return self._add("expire", key, seconds)

    def exec(self):
        return self.results


class FakeRedis:
    def __init__(self, results=None):
        self.pipeline_instance = FakePipeline(results)

    def pipeline(self):
        return self.pipeline_instance


def test_in_memory_analytics_counts_searches_and_unique_browsers():
    repository = InMemorySearchAnalyticsRepository()
    day = date(2026, 9, 7)

    repository.record_search("visitor-one", day)
    repository.record_search("visitor-one", day)
    repository.record_search("visitor-two", day)

    report = repository.get_report(day, days=1)
    assert report["lifetime"] == {
        "searches": 3,
        "unique_searchers": 2,
        "searches_per_searcher": 1.5,
    }
    assert report["daily"][0]["searches"] == 3
    assert report["daily"][0]["unique_searchers"] == 2


def test_upstash_analytics_records_all_metrics_in_one_pipeline():
    client = FakeRedis()
    repository = UpstashSearchAnalyticsRepository(client)

    repository.record_search("visitor-one", date(2026, 9, 7))

    commands = client.pipeline_instance.commands
    assert commands[0] == ("incr", LIFETIME_SEARCHES_KEY)
    assert commands[1] == ("pfadd", LIFETIME_SEARCHERS_KEY, "visitor-one")
    assert commands[2][0] == "incr"
    assert commands[3] == ("expire", commands[2][1], DAILY_RETENTION_SECONDS)
    assert commands[4][0] == "pfadd"
    assert commands[5] == ("expire", commands[4][1], DAILY_RETENTION_SECONDS)


def test_upstash_report_converts_missing_values_to_zero():
    client = FakeRedis(["5", 2, None, 0, "3", 2])
    repository = UpstashSearchAnalyticsRepository(client)

    report = repository.get_report(date(2026, 9, 7), days=2)

    assert report["lifetime"]["searches"] == 5
    assert report["lifetime"]["searches_per_searcher"] == 2.5
    assert report["daily"][0]["date"] == "2026-09-06"
    assert report["daily"][0]["searches"] == 0
    assert report["daily"][1]["searches"] == 3
    assert report["daily"][1]["unique_searchers"] == 2
