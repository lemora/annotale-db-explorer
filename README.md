# Annotale DB Explorer

Streamlit app to explore the `annotale.db` SQLite database with interactive views.

## Requirements

- Python 3.10+
- `annotale.db` in the repo root

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m streamlit run app.py
```

## Pages

- **Overview**: tables and schemas, quick row samples
- **Distributions**: family sizes, TALE lengths, TALEs by strain, RVD composition
- **Family Trees**: interactive Vega-Lite tree with clickable leaf selection
- **Crosstab**: strain vs. family heatmap

## Notes

- Family tree selection highlights the clicked TALE leaf and shows the selected ID/name above the chart.
- Leaf tooltips show TALE ID and name only.
