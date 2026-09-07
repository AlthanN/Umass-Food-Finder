import json

import pytest

from food_finder.models import MenuItem, MenuSnapshot, SourceFailure
from food_finder.storage import (
    InMemoryMenuRepository,
    UpstashMenuRepository,
    has_upstash_configuration,
    resolve_upstash_credentials,
)


@pytest.fixture(autouse=True)
def clear_redis_environment(monkeypatch):
    for name in (
        "UPSTASH_REDIS_REST_URL",
        "UPSTASH_REDIS_REST_TOKEN",
        "KV_REST_API_URL",
        "KV_REST_API_TOKEN",
        "KV_REST_API_READ_ONLY_TOKEN",
        "KV_URL",
        "REDIS_URL",
    ):
        monkeypatch.delenv(name, raising=False)


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


def test_existing_vercel_kv_credentials_are_supported(monkeypatch):
    monkeypatch.setenv("KV_REST_API_URL", "https://kv.example")
    monkeypatch.setenv("KV_REST_API_TOKEN", "write-token")

    assert resolve_upstash_credentials() == ("https://kv.example", "write-token")
    assert has_upstash_configuration() is True


def test_upstash_names_take_precedence_over_vercel_kv_names(monkeypatch):
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://upstash.example")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "upstash-token")
    monkeypatch.setenv("KV_REST_API_URL", "https://kv.example")
    monkeypatch.setenv("KV_REST_API_TOKEN", "kv-token")

    assert resolve_upstash_credentials() == (
        "https://upstash.example",
        "upstash-token",
    )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("UPSTASH_REDIS_REST_URL", "https://upstash.example"),
        ("UPSTASH_REDIS_REST_TOKEN", "token-only"),
        ("KV_REST_API_URL", "https://kv.example"),
        ("KV_REST_API_TOKEN", "token-only"),
        ("KV_REST_API_READ_ONLY_TOKEN", "read-only"),
    ],
)
def test_incomplete_or_read_only_credentials_are_not_accepted(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    assert resolve_upstash_credentials() is None
    assert has_upstash_configuration() is False


def test_incomplete_preferred_pair_does_not_mix_or_fall_back(monkeypatch):
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://upstash.example")
    monkeypatch.setenv("KV_REST_API_URL", "https://kv.example")
    monkeypatch.setenv("KV_REST_API_TOKEN", "kv-token")

    assert resolve_upstash_credentials() is None
