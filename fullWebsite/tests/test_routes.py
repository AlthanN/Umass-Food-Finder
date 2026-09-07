from app import create_app
from food_finder.models import MenuItem, MenuSnapshot, SourceFailure
from food_finder.storage import InMemoryMenuRepository


def make_client(snapshot):
    app = create_app(menu_snapshot=snapshot)
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_loads_split_frontend_assets():
    response = make_client(MenuSnapshot(successful_sources=1)).get("/")

    assert response.status_code == 200
    assert b"static/css/styles.css" in response.data
    assert b"static/js/app.js" in response.data
    assert b'rel="icon"' in response.data
    assert b"static/image.png" in response.data


def test_blank_query_has_consistent_envelope():
    response = make_client(MenuSnapshot(successful_sources=1)).get("/search?foodName=%20")
    data = response.get_json()

    assert response.status_code == 400
    assert data["query"] == ""
    assert data["results"] == []
    assert data["data_status"] == "empty"


def test_search_returns_matches_and_category():
    pizza = MenuItem("Lunch", "Entrees", "Cheese Pizza", "Worcester", "2026-09-06")
    response = make_client(MenuSnapshot(items=[pizza], successful_sources=1)).get("/search?foodName=pizza")
    data = response.get_json()

    assert response.status_code == 200
    assert data["data_status"] == "complete"
    assert data["results"][0]["category"] == "Entrees"
    assert data["message"] is None


def test_no_match_is_a_valid_200_response():
    pizza = MenuItem("Lunch", "Entrees", "Cheese Pizza", "Worcester", "2026-09-06")
    response = make_client(MenuSnapshot(items=[pizza], successful_sources=1)).get("/search?foodName=sushi")

    assert response.status_code == 200
    assert response.get_json()["results"] == []


def test_empty_menu_is_distinct_from_upstream_failure():
    empty_response = make_client(MenuSnapshot(successful_sources=4)).get("/search?foodName=pizza")
    unavailable = MenuSnapshot.unavailable("offline")
    unavailable_response = make_client(unavailable).get("/search?foodName=pizza")

    assert empty_response.status_code == 200
    assert empty_response.get_json()["data_status"] == "empty"
    assert unavailable_response.status_code == 503
    assert unavailable_response.get_json()["data_status"] == "unavailable"


def test_partial_snapshot_exposes_failed_sources_and_results():
    pizza = MenuItem("Dinner", "Entrees", "Pizza", "Berkshire", "2026-09-06")
    failure = SourceFailure("Franklin", "2026-09-06", "offline")
    snapshot = MenuSnapshot(items=[pizza], failures=[failure], successful_sources=3)

    data = make_client(snapshot).get("/search?foodName=pizza").get_json()

    assert data["data_status"] == "partial"
    assert len(data["results"]) == 1
    assert data["failed_sources"][0]["location"] == "Franklin"
    assert "reason" not in data["failed_sources"][0]


def test_health_reports_seeded_and_missing_snapshots():
    healthy = make_client(MenuSnapshot(successful_sources=1)).get("/health")
    missing_app = create_app(repository=InMemoryMenuRepository())
    missing_app.config.update(TESTING=True)
    missing = missing_app.test_client().get("/health")

    assert healthy.status_code == 200
    assert healthy.get_json()["status"] == "ok"
    assert missing.status_code == 503
    assert missing.get_json()["loaded_at"] is None


def test_refresh_requires_the_cron_secret(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "a-secret-longer-than-16")
    app = create_app(repository=InMemoryMenuRepository())
    app.config.update(TESTING=True)
    client = app.test_client()

    assert client.get("/api/refresh").status_code == 401
    assert client.get(
        "/api/refresh", headers={"Authorization": "Bearer wrong"}
    ).status_code == 401


def test_refresh_saves_a_usable_snapshot(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "a-secret-longer-than-16")
    snapshot = MenuSnapshot(
        items=[MenuItem("Lunch", "Entrees", "Pizza", "Worcester", "2026-09-06")],
        successful_sources=1,
    )

    class FakeScraper:
        def fetch(self):
            return snapshot

    repository = InMemoryMenuRepository()
    app = create_app(repository=repository, scraper=FakeScraper())
    app.config.update(TESTING=True)
    response = app.test_client().get(
        "/api/refresh",
        headers={"Authorization": "Bearer a-secret-longer-than-16"},
    )

    assert response.status_code == 200
    assert response.get_json()["saved"] is True
    assert repository.load() is snapshot


def test_total_refresh_failure_preserves_previous_snapshot(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "a-secret-longer-than-16")
    previous = MenuSnapshot(successful_sources=1, loaded_at="previous")

    class FailedScraper:
        def fetch(self):
            return MenuSnapshot.unavailable("offline")

    repository = InMemoryMenuRepository(previous)
    app = create_app(repository=repository, scraper=FailedScraper())
    app.config.update(TESTING=True)
    response = app.test_client().get(
        "/api/refresh",
        headers={"Authorization": "Bearer a-secret-longer-than-16"},
    )

    assert response.status_code == 502
    assert response.get_json()["saved"] is False
    assert repository.load() is previous


def test_analytics_script_is_only_rendered_when_configured():
    app = create_app(menu_snapshot=MenuSnapshot(successful_sources=1))
    app.config.update(TESTING=True)
    without_analytics = app.test_client().get("/")

    app.config["VERCEL_ANALYTICS_SCRIPT_SRC"] = "/analytics/script.js"
    with_analytics = app.test_client().get("/")

    assert b"window.va" not in without_analytics.data
    assert b'/analytics/script.js' in with_analytics.data


def test_partial_snapshot_explains_that_no_match_may_be_incomplete():
    failure = SourceFailure("Franklin", "2026-09-06", "offline")
    snapshot = MenuSnapshot(successful_sources=3, failures=[failure])

    data = make_client(snapshot).get("/search?foodName=sushi").get_json()

    assert data["data_status"] == "partial"
    assert "may be incomplete" in data["message"]
