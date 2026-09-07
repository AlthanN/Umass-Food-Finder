"""Data structures shared by the scraper, search service, and Flask app."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class MenuItem:
    meal: str
    category: str
    food: str
    location: str
    date: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MenuItem":
        return cls(**{field: _required_string(data, field) for field in ("meal", "category", "food", "location", "date")})


@dataclass(frozen=True)
class SourceFailure:
    location: str
    date: str | None
    reason: str

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceFailure":
        date = data.get("date")
        if date is not None and not isinstance(date, str):
            raise ValueError("Source failure date must be a string or null")
        return cls(
            location=_required_string(data, "location"),
            date=date,
            reason=_required_string(data, "reason"),
        )


@dataclass
class MenuSnapshot:
    items: list[MenuItem] = field(default_factory=list)
    failures: list[SourceFailure] = field(default_factory=list)
    attempted_sources: int = 0
    successful_sources: int = 0
    loaded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def data_status(self) -> str:
        if self.successful_sources == 0:
            return "unavailable"
        if self.failures:
            return "partial"
        if not self.items:
            return "empty"
        return "complete"

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "failures": [failure.to_dict() for failure in self.failures],
            "attempted_sources": self.attempted_sources,
            "successful_sources": self.successful_sources,
            "loaded_at": self.loaded_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MenuSnapshot":
        if not isinstance(data, dict):
            raise ValueError("Stored menu snapshot must be an object")
        items = data.get("items")
        failures = data.get("failures")
        if not isinstance(items, list) or not isinstance(failures, list):
            raise ValueError("Stored menu snapshot has invalid collections")
        if not all(isinstance(item, dict) for item in items):
            raise ValueError("Stored menu snapshot has invalid menu items")
        if not all(isinstance(failure, dict) for failure in failures):
            raise ValueError("Stored menu snapshot has invalid failures")
        attempted = data.get("attempted_sources")
        successful = data.get("successful_sources")
        loaded_at = data.get("loaded_at")
        if not isinstance(attempted, int) or not isinstance(successful, int):
            raise ValueError("Stored menu snapshot has invalid source counts")
        if not isinstance(loaded_at, str):
            raise ValueError("Stored menu snapshot has an invalid timestamp")
        return cls(
            items=[MenuItem.from_dict(item) for item in items],
            failures=[SourceFailure.from_dict(failure) for failure in failures],
            attempted_sources=attempted,
            successful_sources=successful,
            loaded_at=loaded_at,
        )

    @classmethod
    def unavailable(cls, reason: str) -> "MenuSnapshot":
        return cls(
            failures=[SourceFailure(location="All dining halls", date=None, reason=reason)],
            attempted_sources=1,
        )


def _required_string(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value
