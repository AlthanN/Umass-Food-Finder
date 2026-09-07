"""Menu snapshot repositories for local and serverless runtimes."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from .models import MenuSnapshot


SNAPSHOT_KEY = "umass-food-finder:menu-snapshot:v1"
UPSTASH_ENVIRONMENT = ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN")
VERCEL_KV_ENVIRONMENT = ("KV_REST_API_URL", "KV_REST_API_TOKEN")


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
        self.client = client or create_upstash_client()
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
    return resolve_upstash_credentials() is not None


def create_upstash_client():
    from upstash_redis import Redis

    credentials = resolve_upstash_credentials()
    if credentials is None:
        raise ValueError("A complete Upstash Redis credential pair is required")
    url, token = credentials
    return Redis(url=url, token=token, allow_telemetry=False)


def resolve_upstash_credentials() -> tuple[str, str] | None:
    """Resolve a complete REST credential pair without mixing naming schemes."""
    for url_name, token_name in (UPSTASH_ENVIRONMENT, VERCEL_KV_ENVIRONMENT):
        url = os.getenv(url_name)
        token = os.getenv(token_name)
        if url or token:
            return (url, token) if url and token else None
    return None
