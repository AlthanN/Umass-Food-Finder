from flasksite import create_app
from food_finder.models import MenuItem, MenuSnapshot, SourceFailure


def make_client(snapshot):
    app = create_app(menu_snapshot=snapshot)
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_loads_split_frontend_assets():
    response = make_client(MenuSnapshot(successful_sources=1)).get("/")

    assert response.status_code == 200
    assert b"static/css/styles.css" in response.data
    assert b"static/js/app.js" in response.data


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


def test_partial_snapshot_explains_that_no_match_may_be_incomplete():
    failure = SourceFailure("Franklin", "2026-09-06", "offline")
    snapshot = MenuSnapshot(successful_sources=3, failures=[failure])

    data = make_client(snapshot).get("/search?foodName=sushi").get_json()

    assert data["data_status"] == "partial"
    assert "may be incomplete" in data["message"]
