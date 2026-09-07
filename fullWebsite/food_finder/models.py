"""Data structures shared by the scraper, search service, and Flask app."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class MenuItem:
    meal: str
    category: str
    food: str
    location: str
    date: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class SourceFailure:
    location: str
    date: str | None
    reason: str

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


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

    @classmethod
    def unavailable(cls, reason: str) -> "MenuSnapshot":
        return cls(
            failures=[SourceFailure(location="All dining halls", date=None, reason=reason)],
            attempted_sources=1,
        )
