# AnnoTALE DB Explorer

<img src="img/AnnoTALE-db-explorer.png" width="200">

Streamlit app for interactive exploration of the local `data/annotale.db` SQLite database.

## What You Can Do

- Inspect database tables, schemas, sample rows
- Visualize sample locations on a country-level map
- View a sample overview and links to related records
- View TALE positions across assemblies and strands for a selected strain
- Open TALE detail views with metadata and sequence downloads
- Navigate TALE family trees and linked TALE selections

## Requirements

- `data/annotale.db` file in the repository
- Docker with compose support

## Run

```bash
docker compose up --build -d
```

Open `http://localhost:8501`.

To stop:

```bash
docker compose down
```

## Project Structure

- `app.py`: Streamlit entrypoint and page navigation
- `.streamlit/config.toml`: Streamlit client configuration
- `views/`: page rendering and page-local logic
- `utils/db.py`: centralized SQL/database query layer
- `utils/`: shared helpers for page setup, taxonomy handling, tree layout, and theme constants
- `data/annotale.db`: SQLite data source
