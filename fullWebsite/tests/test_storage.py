import json

import pytest

from food_finder.models import MenuItem, MenuSnapshot, SourceFailure
from food_finder.storage import InMemoryMenuRepository, UpstashMenuRepository


class FakeRedis:
    def __init__(self, value=None):
        self.value = value
        self.set_calls = []

    def get(self, key):
        return self.value

    def set(self, key, value):
        self.value = value
        self.set_calls.append((key, value))
        return True


def sample_snapshot():
    return MenuSnapshot(
        items=[MenuItem("Lunch", "Entrees", "Pizza", "Worcester", "2026-09-06")],
        failures=[SourceFailure("Franklin", "2026-09-06", "offline")],
        attempted_sources=4,
        successful_sources=3,
        loaded_at="2026-09-06T10:00:00+00:00",
    )


def test_snapshot_round_trip_through_redis():
    client = FakeRedis()
    repository = UpstashMenuRepository(client)
    snapshot = sample_snapshot()

    repository.save(snapshot)

    assert len(client.set_calls) == 1
    assert repository.load() == snapshot


def test_repository_accepts_automatically_deserialized_redis_value():
    client = FakeRedis(sample_snapshot().to_dict())

    assert UpstashMenuRepository(client).load() == sample_snapshot()


def test_missing_snapshot_returns_none():
    assert UpstashMenuRepository(FakeRedis()).load() is None


@pytest.mark.parametrize(
    "value",
    ["not-json", json.dumps({"items": []}), [], {"items": [None], "failures": []}],
)
def test_malformed_snapshot_is_rejected(value):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        UpstashMenuRepository(FakeRedis(value)).load()


def test_in_memory_repository_can_be_replaced():
    repository = InMemoryMenuRepository()
    snapshot = sample_snapshot()

    assert repository.load() is None
    repository.save(snapshot)
    assert repository.load() is snapshot
