"""Core services for the UMass Food Finder."""

from .analytics import (
    InMemorySearchAnalyticsRepository,
    SearchAnalyticsRepository,
    UpstashSearchAnalyticsRepository,
)
from .models import MenuItem, MenuSnapshot, SourceFailure
from .scraper import MenuScraper
from .search import search_menu
from .storage import InMemoryMenuRepository, MenuRepository, UpstashMenuRepository

__all__ = [
    "InMemoryMenuRepository",
    "InMemorySearchAnalyticsRepository",
    "MenuItem",
    "MenuRepository",
    "MenuScraper",
    "MenuSnapshot",
    "SearchAnalyticsRepository",
    "SourceFailure",
    "UpstashMenuRepository",
    "UpstashSearchAnalyticsRepository",
    "search_menu",
]
