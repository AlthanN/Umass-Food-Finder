import json

import pytest
import requests

from food_finder.scraper import DINING_HALLS, MENU_API_URL, MenuScraper, parse_menu_response


class FakeResponse:
    def __init__(self, content=b"", status=200):
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, menu_responses):
        self.menu_responses = iter(menu_responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url == MENU_API_URL:
            response = next(self.menu_responses)
            if isinstance(response, Exception):
                raise response
            return response
        return FakeResponse(b'<select id="upcoming-foodpro"><option value="09/06/2026">Today</option></select>')


def menu_response(food="Pizza"):
    payload = {"lunch": {"Entrees": f'<a>  {food}  </a>'}}
    return FakeResponse(json.dumps(payload).encode())


def test_parse_menu_response_extracts_and_normalizes_items():
    content = json.dumps({"late night": {"Grill": "<a> Spicy  Tofu </a><span>ignore</span>"}})

    items = parse_menu_response("09/06/2026", "Worcester", content)

    assert len(items) == 1
    assert items[0].to_dict() == {
        "meal": "Late Night",
        "category": "Grill",
        "food": "Spicy Tofu",
        "location": "Worcester",
        "date": "2026-09-06",
    }


@pytest.mark.parametrize("content", ["[]", "not json", '{"lunch": []}', '{"lunch": {"x": null}}'])
def test_parse_menu_response_rejects_unexpected_data(content):
    with pytest.raises((ValueError, TypeError, json.JSONDecodeError)):
        parse_menu_response("09/06/2026", "Worcester", content)


def test_successful_empty_responses_are_empty_not_unavailable():
    session = FakeSession([FakeResponse(b"{}") for _ in DINING_HALLS])

    snapshot = MenuScraper(session=session, max_workers=1).fetch()

    assert snapshot.data_status == "empty"
    assert snapshot.successful_sources == 4
    assert snapshot.items == []


def test_scraper_preserves_successful_data_after_partial_failure():
    responses = [menu_response(), requests.ConnectionError("offline"), menu_response(), menu_response()]

    snapshot = MenuScraper(session=FakeSession(responses), max_workers=1).fetch()

    assert snapshot.data_status == "partial"
    assert snapshot.successful_sources == 3
    assert len(snapshot.items) == 3
    assert snapshot.failures[0].location == "Franklin"


def test_missing_date_selector_returns_unavailable():
    class NoDatesSession(FakeSession):
        def get(self, url, **kwargs):
            return FakeResponse(b"<html></html>")

    snapshot = MenuScraper(session=NoDatesSession([]), max_workers=1).fetch()

    assert snapshot.data_status == "unavailable"
    assert snapshot.items == []
