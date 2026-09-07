from datetime import date

from app import create_app
from food_finder.analytics import InMemorySearchAnalyticsRepository
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


def test_feedback_form_is_only_enabled_when_configured():
    app = create_app(menu_snapshot=MenuSnapshot(successful_sources=1))
    app.config.update(TESTING=True, FORMSPREE_FORM_ID="")
    without_feedback = app.test_client().get("/")

    app.config["FORMSPREE_FORM_ID"] = "abc123"
    with_feedback = app.test_client().get("/")

    assert b'id="feedback-form"' not in without_feedback.data
    assert b"Feedback is not configured yet" in without_feedback.data
    assert b'id="feedback-form"' in with_feedback.data
    assert b'data-endpoint="https://formspree.io/f/abc123"' in with_feedback.data
    assert b'name="_gotcha"' in with_feedback.data
    assert b'name="email"' not in with_feedback.data


def test_feedback_form_contains_anonymous_category_and_message_fields():
    app = create_app(menu_snapshot=MenuSnapshot(successful_sources=1))
    app.config.update(TESTING=True, FORMSPREE_FORM_ID="abc123")

    response = app.test_client().get("/")

    assert b'name="category"' in response.data
    assert b'name="message"' in response.data
    assert b'minlength="10"' in response.data
    assert b'maxlength="2000"' in response.data


def test_partial_snapshot_explains_that_no_match_may_be_incomplete():
    failure = SourceFailure("Franklin", "2026-09-06", "offline")
    snapshot = MenuSnapshot(successful_sources=3, failures=[failure])

    data = make_client(snapshot).get("/search?foodName=sushi").get_json()

    assert data["data_status"] == "partial"
    assert "may be incomplete" in data["message"]


def test_only_intentional_nonblank_searches_are_counted(monkeypatch):
    analytics = InMemorySearchAnalyticsRepository()
    snapshot = MenuSnapshot(successful_sources=1)
    app = create_app(menu_snapshot=snapshot, analytics_repository=analytics)
    app.config.update(TESTING=True)
    monkeypatch.setattr("app._today_eastern", lambda: date(2026, 9, 7))
    client = app.test_client()

    client.get("/search?foodName=pizza")
    client.get("/search?foodName=pizza&intent=search")
    client.get("/search?foodName=%20&intent=search")

    report = analytics.get_report(date(2026, 9, 7), days=1)
    assert report["lifetime"]["searches"] == 1
    assert report["lifetime"]["unique_searchers"] == 1


def test_search_analytics_cookie_is_private_and_reused(monkeypatch):
    analytics = InMemorySearchAnalyticsRepository()
    app = create_app(
        menu_snapshot=MenuSnapshot(successful_sources=1),
        analytics_repository=analytics,
    )
    app.config.update(TESTING=True)
    monkeypatch.setattr("app._today_eastern", lambda: date(2026, 9, 7))
    client = app.test_client()

    first = client.get(
        "/search?foodName=pizza&intent=search", base_url="https://example.com"
    )
    second = client.get(
        "/search?foodName=tofu&intent=search", base_url="https://example.com"
    )

    cookie = first.headers["Set-Cookie"]
    assert "uff_visitor_id=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=Lax" in cookie
    assert "Set-Cookie" not in second.headers
    assert analytics.total_searches == 2
    assert len(analytics.lifetime_searchers) == 1


def test_malformed_analytics_cookie_is_replaced():
    analytics = InMemorySearchAnalyticsRepository()
    app = create_app(
        menu_snapshot=MenuSnapshot(successful_sources=1),
        analytics_repository=analytics,
    )
    app.config.update(TESTING=True)
    client = app.test_client()
    client.set_cookie("uff_visitor_id", "invalid")

    response = client.get("/search?foodName=pizza&intent=search")

    cookie = response.headers["Set-Cookie"]
    assert "uff_visitor_id=" in cookie
    assert "uff_visitor_id=invalid" not in cookie


def test_analytics_write_failure_does_not_break_search():
    class FailedAnalytics:
        def record_search(self, visitor_id, day):
            raise RuntimeError("offline")

    app = create_app(
        menu_snapshot=MenuSnapshot(successful_sources=1),
        analytics_repository=FailedAnalytics(),
    )
    app.config.update(TESTING=True)

    response = app.test_client().get("/search?foodName=pizza&intent=search")

    assert response.status_code == 200
    assert response.get_json()["data_status"] == "empty"


def test_search_analytics_endpoint_is_private(monkeypatch):
    analytics = InMemorySearchAnalyticsRepository()
    analytics.record_search("visitor-one", date(2026, 9, 7))
    app = create_app(
        menu_snapshot=MenuSnapshot(successful_sources=1),
        analytics_repository=analytics,
    )
    app.config.update(TESTING=True, ANALYTICS_SECRET="analytics-secret")
    monkeypatch.setattr("app._today_eastern", lambda: date(2026, 9, 7))
    client = app.test_client()

    unauthorized = client.get("/api/analytics/searches")
    authorized = client.get(
        "/api/analytics/searches",
        headers={"Authorization": "Bearer analytics-secret"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.headers["Cache-Control"] == "no-store"
    assert authorized.get_json()["lifetime"]["searches"] == 1
    assert len(authorized.get_json()["daily"]) == 30


def test_search_analytics_endpoint_handles_storage_failure():
    class FailedAnalytics:
        def get_report(self, end_date, *, days):
            raise RuntimeError("offline")

    app = create_app(
        menu_snapshot=MenuSnapshot(successful_sources=1),
        analytics_repository=FailedAnalytics(),
    )
    app.config.update(TESTING=True, ANALYTICS_SECRET="analytics-secret")

    response = app.test_client().get(
        "/api/analytics/searches",
        headers={"Authorization": "Bearer analytics-secret"},
    )

    assert response.status_code == 503
    assert response.get_json() == {"status": "unavailable"}
