# AnnoTALE DB Explorer

Streamlit app for interactive exploration of the local `annotale.db` SQLite database.

## What You Can Do

- Inspect database tables, schemas, and sample rows.
- Explore TALE and family-level distributions, including taxonomy mismatch summaries.
- Navigate TALE family trees with linked TALE selection.
- Compare family counts by species/pathovar/strain.
- Visualize sample geography on a country-level map.

## Requirements

- Python 3.10 or newer
- `annotale.db` file in the repository root

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

- `app.py`: Streamlit entrypoint (home page)
- `pages/`: multi-page Streamlit views
- `db_utils.py`: database connection and reusable query helpers
- `taxonomy_utils.py`: taxonomy fallback and mapping helpers
- `tree_utils.py`: Newick parsing and tree layout helpers
- `annotale.db`: SQLite data source

## Troubleshooting

- If the app starts but shows no data, verify `annotale.db` exists at repo root.
- If dependencies are missing, rerun `pip install -r requirements.txt`.
- If Streamlit cache looks stale after DB updates, clear cache from Streamlit settings and rerun.
