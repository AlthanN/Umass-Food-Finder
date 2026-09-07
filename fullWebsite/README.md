# UMass Food Finder

UMass Food Finder searches upcoming menus for Worcester, Franklin, Hampshire,
and Berkshire dining commons. The app loads up to 14 days of menus once when
the Flask process starts; searches use that in-memory snapshot and do not make
additional requests to UMass Dining.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python flasksite.py
```

Open <http://127.0.0.1:5000>. Restart the process when you want to refresh the
menus. The development reloader is disabled so a local run does not scrape
twice.

## Project structure

- `flasksite.py` creates the Flask app and defines its routes.
- `food_finder/scraper.py` obtains and parses UMass menu data.
- `food_finder/search.py` contains network-free search behavior.
- `templates/` and `static/` contain the page, styles, JavaScript, and image.
- `archive/` contains inactive prototypes retained for reference.

## Data availability

Individual hall/date failures are recorded while successful menus remain
searchable. A successful empty response means no food is listed for that menu;
it is not treated as a network failure. If no menu source can be loaded, the
site still starts and the search endpoint returns a clear unavailable response.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests use fake HTTP responses and never contact UMass Dining.
