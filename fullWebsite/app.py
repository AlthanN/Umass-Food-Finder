"""Flask and Vercel WSGI entrypoint for the UMass Food Finder."""

from __future__ import annotations

import hmac
import logging
import os

from flask import Flask, jsonify, render_template, request

from food_finder import (
    InMemoryMenuRepository,
    MenuScraper,
    MenuSnapshot,
    UpstashMenuRepository,
    search_menu,
)
from food_finder.storage import has_upstash_configuration


def create_app(
    *,
    menu_snapshot=None,
    repository=None,
    scraper=None,
    load_local_data=False,
) -> Flask:
    """Create the app with injectable storage and scraping dependencies."""
    app = Flask(__name__)
    scraper = scraper or MenuScraper()

    if repository is None and menu_snapshot is not None:
        repository = InMemoryMenuRepository(menu_snapshot)
    elif repository is None and has_upstash_configuration():
        repository = UpstashMenuRepository()
    elif repository is None and load_local_data:
        app.logger.info("Loading UMass menus for this application process")
        repository = InMemoryMenuRepository(scraper.fetch())
    elif repository is None:
        repository = InMemoryMenuRepository()

    app.extensions["menu_repository"] = repository
    app.extensions["menu_scraper"] = scraper
    app.config["VERCEL_ANALYTICS_SCRIPT_SRC"] = os.getenv(
        "VERCEL_ANALYTICS_SCRIPT_SRC", ""
    )
    app.config["FORMSPREE_FORM_ID"] = os.getenv("FORMSPREE_FORM_ID", "")

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            analytics_script_src=app.config["VERCEL_ANALYTICS_SCRIPT_SRC"],
            formspree_form_id=app.config["FORMSPREE_FORM_ID"],
        )

    @app.get("/search")
    def search_food():
        query = request.args.get("foodName", "").strip()
        snapshot = _load_snapshot(app)

        if not query:
            return jsonify(_response(snapshot, query, [], "Please enter a food name.")), 400

        if snapshot.data_status == "unavailable":
            message = "Menu data is currently unavailable. Please try again later."
            return jsonify(_response(snapshot, query, [], message)), 503

        results = search_menu(snapshot.items, query)
        if snapshot.data_status == "empty":
            message = "No food is currently listed for the available dining hall dates."
        elif not results and snapshot.data_status == "partial":
            message = (
                f'No loaded menu items matched "{query}". '
                "Some menus were unavailable, so results may be incomplete."
            )
        elif not results:
            message = f'No menu items matched "{query}".'
        elif snapshot.data_status == "partial":
            message = "Some menus could not be loaded, so these results may be incomplete."
        else:
            message = None

        return jsonify(_response(snapshot, query, results, message))

    @app.get("/api/refresh")
    def refresh_menus():
        expected_secret = os.getenv("CRON_SECRET", "")
        provided_header = request.headers.get("Authorization", "")
        expected_header = f"Bearer {expected_secret}"
        if not expected_secret or not hmac.compare_digest(provided_header, expected_header):
            return jsonify({"status": "unauthorized"}), 401

        snapshot = app.extensions["menu_scraper"].fetch()
        if snapshot.data_status == "unavailable":
            app.logger.error("Menu refresh failed; preserving the existing snapshot")
            return jsonify(_refresh_response(snapshot, saved=False)), 502

        try:
            app.extensions["menu_repository"].save(snapshot)
        except Exception:
            app.logger.exception("Could not save the refreshed menu snapshot")
            return jsonify(_refresh_response(snapshot, saved=False)), 503
        return jsonify(_refresh_response(snapshot, saved=True))

    @app.get("/health")
    def health():
        snapshot = _load_snapshot(app)
        healthy = snapshot.data_status != "unavailable"
        return jsonify(
            {
                "status": "ok" if healthy else "unavailable",
                "data_status": snapshot.data_status,
                "loaded_at": snapshot.loaded_at if healthy else None,
            }
        ), 200 if healthy else 503

    return app


def _response(snapshot, query, results, message):
    return {
        "query": query,
        "results": [item.to_dict() for item in results],
        "message": message,
        "data_status": snapshot.data_status,
        "failed_sources": [
            {"location": failure.location, "date": failure.date}
            for failure in snapshot.failures
        ],
        "loaded_at": snapshot.loaded_at,
    }


def _load_snapshot(app: Flask) -> MenuSnapshot:
    try:
        snapshot = app.extensions["menu_repository"].load()
        if snapshot is None:
            return MenuSnapshot.unavailable("Menu cache has not been seeded")
        return snapshot
    except Exception:
        app.logger.exception("Could not load the menu snapshot")
        return MenuSnapshot.unavailable("Menu storage is unavailable")


def _refresh_response(snapshot: MenuSnapshot, *, saved: bool):
    return {
        "status": snapshot.data_status,
        "saved": saved,
        "items": len(snapshot.items),
        "successful_sources": snapshot.successful_sources,
        "failed_sources": len(snapshot.failures),
        "loaded_at": snapshot.loaded_at,
    }


# Vercel detects this top-level WSGI application. It performs no startup scrape.
app = create_app()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app(load_local_data=True).run(debug=True, use_reloader=False)
