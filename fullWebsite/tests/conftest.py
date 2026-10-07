import pytest


@pytest.fixture(autouse=True)
def default_app_unpaused(monkeypatch):
    """Keep local pause preferences from changing unrelated test behavior."""
    monkeypatch.delenv("APP_PAUSED", raising=False)
