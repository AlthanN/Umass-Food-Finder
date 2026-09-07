"""Menu snapshot repositories for local and serverless runtimes."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from .models import MenuSnapshot


SNAPSHOT_KEY = "umass-food-finder:menu-snapshot:v1"


class MenuRepository(Protocol):
    def load(self) -> MenuSnapshot | None: ...

    def save(self, snapshot: MenuSnapshot) -> None: ...


class InMemoryMenuRepository:
    def __init__(self, snapshot: MenuSnapshot | None = None) -> None:
        self.snapshot = snapshot

    def load(self) -> MenuSnapshot | None:
        return self.snapshot

    def save(self, snapshot: MenuSnapshot) -> None:
        self.snapshot = snapshot


class UpstashMenuRepository:
    def __init__(self, client: Any | None = None, *, key: str = SNAPSHOT_KEY) -> None:
        if client is None:
            from upstash_redis import Redis

            client = Redis.from_env(allow_telemetry=False)
        self.client = client
        self.key = key

    def load(self) -> MenuSnapshot | None:
        value = self.client.get(self.key)
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if isinstance(value, str):
            value = json.loads(value)
        return MenuSnapshot.from_dict(value)

    def save(self, snapshot: MenuSnapshot) -> None:
        # Redis SET replaces one key atomically, so readers never see half a refresh.
        self.client.set(self.key, json.dumps(snapshot.to_dict(), separators=(",", ":")))


def has_upstash_configuration() -> bool:
    return bool(os.getenv("UPSTASH_REDIS_REST_URL") and os.getenv("UPSTASH_REDIS_REST_TOKEN"))
