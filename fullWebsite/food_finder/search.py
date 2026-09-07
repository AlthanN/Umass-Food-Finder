"""Pure menu search functions."""

from __future__ import annotations

from collections.abc import Iterable

from .models import MenuItem


LOCATION_ORDER = {
    "Worcester": 0,
    "Franklin": 1,
    "Hampshire": 2,
    "Berkshire": 3,
}


def search_menu(items: Iterable[MenuItem], query: str) -> list[MenuItem]:
    """Return case-insensitive substring matches in a stable display order."""
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return []

    matches = [item for item in items if normalized_query in item.food.casefold()]
    return sorted(
        matches,
        key=lambda item: (
            item.date,
            LOCATION_ORDER.get(item.location, len(LOCATION_ORDER)),
            item.meal.casefold(),
            item.food.casefold(),
        ),
    )
