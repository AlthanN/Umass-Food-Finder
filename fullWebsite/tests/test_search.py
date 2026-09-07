from food_finder.models import MenuItem
from food_finder.search import search_menu


def item(food, *, date="2026-09-06", location="Worcester", meal="Lunch"):
    return MenuItem(meal, "Entrees", food, location, date)


def test_search_is_trimmed_case_insensitive_and_partial():
    items = [item("Spicy Tofu"), item("Chicken Soup")]

    assert search_menu(items, "  TOFu ") == [items[0]]


def test_search_has_deterministic_date_and_location_order():
    items = [
        item("Pizza B", location="Berkshire"),
        item("Pizza A", location="Worcester"),
        item("Pizza Tomorrow", date="2026-09-07"),
    ]

    assert [result.food for result in search_menu(items, "pizza")] == [
        "Pizza A",
        "Pizza B",
        "Pizza Tomorrow",
    ]


def test_blank_or_missing_match_returns_empty_list():
    items = [item("Pizza")]

    assert search_menu(items, "  ") == []
    assert search_menu(items, "sushi") == []
