# AnnoTALE DB Explorer

Streamlit app for interactive exploration of the local `data/annotale.db` SQLite database.

## What You Can Do

- Inspect database tables, schemas, and sample rows.
- Explore TALE and family-level distributions, including taxonomy mismatch summaries.
- Navigate TALE family trees with linked TALE selection.
- Compare family counts by species/pathovar/strain.
- Visualize sample geography on a country-level map.
- Inspect TALE genomic organization across assemblies and strands.
- Open a dedicated TALE detail view with sequence downloads and external links.

## Requirements

- `data/annotale.db` file in the repository
- Docker with Compose support

## Run

```bash
docker compose up --build -d
```

Open `http://localhost:8501`.

To stop:

```bash
docker compose down
```

## Analytics

Self-hosted page-visit logging is available and persists in `./analytics/analytics.sqlite3` when enabled via Docker Compose. Details are documented in [docs/analytics.md](docs/analytics.md).

## Project Structure

- `app.py`: Streamlit entrypoint and page navigation
- `.streamlit/config.toml`: Streamlit client configuration
- `pages/`: page rendering and page-local logic
- `utils/db.py`: centralized SQL/database query layer
- `utils/analytics.py`: self-hosted analytics logging
- `utils/`: shared helpers for page setup, taxonomy handling, tree layout, and theme constants
- `data/annotale.db`: SQLite data source

## Troubleshooting

- If the app starts but shows no data, verify `data/annotale.db` exists.
- If Docker is already running an old image, rebuild with `docker compose up --build -d`.
- If Streamlit cache looks stale after DB updates, clear cache from Streamlit settings and rerun.
