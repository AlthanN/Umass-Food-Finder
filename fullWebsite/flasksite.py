"""Flask entrypoint for the UMass Food Finder."""

from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request

from food_finder import MenuScraper, MenuSnapshot, search_menu


def create_app(*, menu_snapshot=None, scraper=None) -> Flask:
    """Create the app and load one menu snapshot for this process."""
    app = Flask(__name__)

    if menu_snapshot is None:
        app.logger.info("Loading UMass menus for this application process")
        menu_snapshot = (scraper or MenuScraper()).fetch()
    app.extensions["menu_snapshot"] = menu_snapshot

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/search")
    def search_food():
        query = request.args.get("foodName", "").strip()
        snapshot: MenuSnapshot = app.extensions["menu_snapshot"]

        if not query:
            return jsonify(_response(snapshot, query, [], "Please enter a food name.")), 400

        if snapshot.data_status == "unavailable":
            message = "Menu data is currently unavailable. Restart the app to try again."
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

    return app


def _response(snapshot, query, results, message):
    return {
        "query": query,
        "results": [item.to_dict() for item in results],
        "message": message,
        "data_status": snapshot.data_status,
        "failed_sources": [failure.to_dict() for failure in snapshot.failures],
        "loaded_at": snapshot.loaded_at,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(debug=True, use_reloader=False)
