# AnnoTALE DB Explorer

Streamlit app for interactive exploration of the local `data/annotale.db` SQLite database.

## What You Can Do

- Inspect database tables, schemas, and sample rows.
- Explore TALE and family-level distributions, including taxonomy mismatch summaries.
- Navigate TALE family trees with linked TALE selection.
- Compare family counts by species/pathovar/strain.
- Visualize sample geography on a country-level map.

## Requirements

- Python 3.10 or newer
- `data/annotale.db` file in the repository

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m streamlit run app.py
```

Then open the local URL shown by Streamlit (usually `http://localhost:8501`).

## Project Structure

- `app.py`: Streamlit entrypoint and page navigation
- `pages/`: page rendering and page-local logic
- `utils/db.py`: centralized SQL/database query layer
- `utils/`: shared helpers (page setup, taxonomy helpers, tree helpers)
- `data/annotale.db`: SQLite data source

## Troubleshooting

- If the app starts but shows no data, verify `data/annotale.db` exists.
- If dependencies are missing, rerun `pip install -r requirements.txt`.
- If Streamlit cache looks stale after DB updates, clear cache from Streamlit settings and rerun.
