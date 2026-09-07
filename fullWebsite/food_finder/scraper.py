"""Fetch and parse menus from UMass Dining."""

from __future__ import annotations

import json
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import MenuItem, MenuSnapshot, SourceFailure


LOGGER = logging.getLogger(__name__)
MENU_PAGE_URL = "https://www.umassdining.com/locations-menus/worcester/menu"
MENU_API_URL = "https://www.umassdining.com/foodpro-menu-ajax"
DINING_HALLS = {1: "Worcester", 2: "Franklin", 3: "Hampshire", 4: "Berkshire"}


class MenuScraper:
    def __init__(self, *, session=None, max_days: int = 14, timeout: float = 10) -> None:
        self.session = session or self._build_session()
        self.max_days = max_days
        self.timeout = timeout

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=1,
            backoff_factor=0.25,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.headers.update({"User-Agent": "UMass-Food-Finder/1.0"})
        return session

    def fetch(self) -> MenuSnapshot:
        try:
            dates = self._fetch_dates()
        except (requests.RequestException, ValueError) as exc:
            LOGGER.warning("Could not discover UMass menu dates: %s", exc)
            return MenuSnapshot.unavailable(str(exc))

        items: list[MenuItem] = []
        failures: list[SourceFailure] = []
        successful_sources = 0

        for location_id, location_name in DINING_HALLS.items():
            for date_value in dates:
                try:
                    response = self.session.get(
                        MENU_API_URL,
                        params={"tid": location_id, "date": date_value},
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    items.extend(parse_menu_response(date_value, location_name, response.content))
                    successful_sources += 1
                except (requests.RequestException, ValueError, TypeError) as exc:
                    LOGGER.warning("Could not load %s menu for %s: %s", location_name, date_value, exc)
                    failures.append(SourceFailure(location_name, _format_date_safe(date_value), str(exc)))

        return MenuSnapshot(
            items=items,
            failures=failures,
            attempted_sources=len(DINING_HALLS) * len(dates),
            successful_sources=successful_sources,
        )

    def _fetch_dates(self) -> list[str]:
        response = self.session.get(MENU_PAGE_URL, timeout=self.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        selector = soup.find("select", id="upcoming-foodpro")
        if selector is None:
            raise ValueError("UMass menu page did not contain the date selector")

        dates = [
            option.get("value", "").strip()
            for option in selector.find_all("option")[: self.max_days]
            if option.get("value", "").strip()
        ]
        if not dates:
            raise ValueError("UMass menu page did not provide any dates")
        return dates


def parse_menu_response(date_value: str, location: str, content: bytes | str) -> list[MenuItem]:
    """Parse UMass JSON, whose category values contain HTML fragments."""
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("Menu response must be a JSON object")

    formatted_date = datetime.strptime(date_value, "%m/%d/%Y").strftime("%Y-%m-%d")
    items: list[MenuItem] = []
    for meal, categories in payload.items():
        if not isinstance(meal, str) or not isinstance(categories, dict):
            raise ValueError("Menu response has an unexpected meal structure")
        for category, dishes_html in categories.items():
            if not isinstance(category, str) or not isinstance(dishes_html, str):
                raise ValueError("Menu response has an unexpected category structure")
            soup = BeautifulSoup(dishes_html, "html.parser")
            for dish in soup.find_all("a"):
                food = " ".join(dish.get_text(" ", strip=True).split())
                if food:
                    items.append(MenuItem(meal.strip().title(), category.strip(), food, location, formatted_date))
    return items


def _format_date_safe(date_value: str) -> str:
    try:
        return datetime.strptime(date_value, "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return date_value
