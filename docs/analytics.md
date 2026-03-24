# Analytics Logging

This app can log page visits to a local SQLite database for later private analysis.

## Defaults

- enabled in Docker Compose
- hashed IP storage by default
- 30 day retention by default
- persistent storage in `./analytics/analytics.sqlite3`

## Run

Set a real salt before starting the app:

```bash
export ANALYTICS_HASH_SALT='replace-this-with-a-long-random-secret'
docker compose up --build -d
```

You can also use a `.env` file in the repo root:

```env
ANALYTICS_ENABLED=true
ANALYTICS_HASH_SALT=replace-this-with-a-long-random-secret
ANALYTICS_IP_MODE=hash
ANALYTICS_RETENTION_DAYS=30
```

## Persistence

Logs are stored in `./analytics/analytics.sqlite3` on the host. Rebuilding or restarting with `docker compose up -d --build` does not delete that file because `./analytics` is mounted into the container.

## Environment Variables

- `ANALYTICS_ENABLED=true`
- `ANALYTICS_DB_PATH=/app/analytics/analytics.sqlite3`
- `ANALYTICS_IP_MODE=hash`
- `ANALYTICS_RETENTION_DAYS=30`
- `ANALYTICS_HASH_SALT=...`

`ANALYTICS_IP_MODE` options:

- `hash`: recommended; stores a salted SHA-256 hash of the IP address
- `raw`: stores the full IP address
- `off`: stores no IP-derived value

`ANALYTICS_RETENTION_DAYS` options:

- `30`: default; delete analytics rows older than 30 days
- `indefinite`: keep logs until you delete them manually
- any other positive number like `90`: delete older analytics rows automatically

## Logged Data

- random per-session ID
- first seen and last seen timestamps
- visited page names
- page visit timestamps
- current URL
- user agent
- locale and timezone if available from Streamlit

## Quick Inspection

```bash
sqlite3 analytics/analytics.sqlite3 ".tables"
sqlite3 analytics/analytics.sqlite3 "SELECT ts, session_id, page, url FROM analytics_page_views ORDER BY ts DESC LIMIT 20;"
```

## Safe Copy For Local Analysis

Create a snapshot on the server first:

```bash
sqlite3 analytics/analytics.sqlite3 ".backup '/tmp/analytics-copy.sqlite3'"
```

Then copy that snapshot to your local machine.
