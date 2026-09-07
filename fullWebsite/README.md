# UMass Food Finder

UMass Food Finder searches up to 14 days of menus for Worcester, Franklin,
Hampshire, and Berkshire dining commons.

Locally, the app scrapes once when it starts and searches that in-memory
snapshot. On Vercel, a daily scheduled job writes the latest snapshot to
Upstash Redis so serverless instances do not scrape during user requests.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. Restart the process to refresh local menu data.
The development reloader is disabled so it does not scrape twice.

Run the tests with:

```bash
pip install -r requirements-dev.txt
pytest
```

Tests use fake HTTP and Redis clients and never contact UMass Dining.

## Deploy to Vercel

1. Import `https://github.com/AlthanN/Umass-Food-Finder` in Vercel.
2. Set the project's **Root Directory** to `fullWebsite`.
3. Install **Upstash for Redis** from the Vercel Marketplace and connect it to
   the project. Confirm that Vercel added `UPSTASH_REDIS_REST_URL` and
   `UPSTASH_REDIS_REST_TOKEN` to the production environment.
4. Add `CRON_SECRET` in Project Settings > Environment Variables. Use a random
   value containing at least 16 characters and enable it for Production.
5. Deploy the project. Vercel detects the top-level Flask `app` in `app.py`.
6. Seed the menu cache immediately rather than waiting for the first cron run:

   ```bash
   curl -H "Authorization: Bearer YOUR_CRON_SECRET" \
     https://YOUR_DOMAIN/api/refresh
   ```

7. Open `https://YOUR_DOMAIN/health`. It should return HTTP 200 with an `ok`
   status and a `loaded_at` timestamp.

The Vercel cron invokes `/api/refresh` at `0 10 * * *`. Vercel schedules are
UTC-only, so this is 6:00 AM Eastern during daylight time and 5:00 AM during
standard time. The endpoint rejects requests that do not carry the configured
secret. A total scrape failure leaves the previous Redis snapshot intact.

## Enable visitor analytics

1. Open the deployed project in Vercel and select **Analytics**.
2. Enable Web Analytics and deploy once so Vercel creates its analytics routes.
3. Select the HTML setup instructions and copy the generated script source,
   which looks like `/a-unique-path/script.js`.
4. Add that value as `VERCEL_ANALYTICS_SCRIPT_SRC` in the Production
   environment and redeploy.
5. Visit the production site and confirm a request to the corresponding
   analytics `/view` endpoint appears in the browser Network panel.

Analytics are visible privately in the Vercel dashboard. Vercel reports page
views and privacy-friendly daily unique visitors; it does not create a public
lifetime visitor counter.

## Architecture and failure behavior

- `app.py` defines page, search, health, and scheduled-refresh routes.
- `food_finder/scraper.py` fetches menus concurrently with bounded workers.
- `food_finder/storage.py` stores one versioned snapshot in Redis or memory.
- `food_finder/search.py` performs deterministic, network-free searches.
- `templates/` and `static/` contain the page, styles, JavaScript, and logo.
- `archive/` contains inactive hackathon prototypes retained for reference.

A successful empty UMass response means no food is listed and is not treated as
a failure. Partial refreshes remain searchable and identify missing hall/date
sources. Internal request errors are logged but are not exposed by the public
API. If Redis has not been seeded or cannot be reached, `/search` and `/health`
return HTTP 503 with a safe unavailable response.
