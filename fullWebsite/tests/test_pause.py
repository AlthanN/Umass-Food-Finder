import pytest

from app import create_app
from food_finder.models import MenuSnapshot
from food_finder.storage import InMemoryMenuRepository


@pytest.mark.parametrize("value,paused", [(None, False), ("false", False), ("true", True), (" TRUE ", True)])
def test_pause_flag(monkeypatch, value, paused):
    if value is not None:
        monkeypatch.setenv("APP_PAUSED", value)
    app = create_app(menu_snapshot=MenuSnapshot(successful_sources=1))
    response = app.test_client().get("/")
    assert app.config["APP_PAUSED"] is paused
    assert response.status_code == (503 if paused else 200)
    if paused:
        assert response.headers["Cache-Control"] == "no-store"
        assert b"temporarily paused" in response.data
        assert b"fixing a few bugs" in response.data
        assert b"js/app.js" not in response.data
        assert b"<form" not in response.data
    else:
        assert b"search-form" in response.data


@pytest.mark.parametrize("query", ["", "pizza&intent=search"])
def test_paused_search_has_no_storage_or_analytics_calls(monkeypatch, query):
    class ForbiddenDependencies:
        def load(self):
            pytest.fail("Paused search must not read storage")

        def record_search(self, *args):
            pytest.fail("Paused search must not record analytics")

    monkeypatch.setenv("APP_PAUSED", "true")
    dependency = ForbiddenDependencies()
    client = create_app(repository=dependency, analytics_repository=dependency).test_client()
    response = client.get(f"/search?foodName={query}")
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    assert "Set-Cookie" not in response.headers
    data = response.get_json()
    assert set(data) == {"query", "results", "message", "data_status", "failed_sources", "loaded_at"}
    assert data["results"] == []
    assert data["failed_sources"] == []
    assert data["loaded_at"] is None
    assert data["data_status"] == "unavailable"
    assert "temporarily paused" in data["message"]


def test_paused_operational_routes_still_work(monkeypatch):
    monkeypatch.setenv("APP_PAUSED", "true")
    monkeypatch.setenv("CRON_SECRET", "test-cron")
    snapshot = MenuSnapshot(successful_sources=1)

    class FakeScraper:
        def fetch(self):
            return snapshot

    repository = InMemoryMenuRepository(snapshot)
    app = create_app(repository=repository, scraper=FakeScraper())
    app.config["ANALYTICS_SECRET"] = "test-analytics"
    client = app.test_client()
    assert client.get("/static/css/styles.css").status_code == 200
    assert client.get("/health").status_code == 200
    for path, secret in [("/api/refresh", "test-cron"), ("/api/analytics/searches", "test-analytics")]:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": f"Bearer {secret}"}).status_code == 200


def test_paused_local_startup_skips_scrape(monkeypatch):
    monkeypatch.setenv("APP_PAUSED", "true")
    monkeypatch.setattr("app.has_upstash_configuration", lambda: False)

    class ForbiddenScraper:
        def fetch(self):
            pytest.fail("Paused local startup must not scrape")

    app = create_app(load_local_data=True, scraper=ForbiddenScraper())
    assert app.test_client().get("/").status_code == 503
