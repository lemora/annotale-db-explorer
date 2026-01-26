import altair as alt
import pandas as pd
import streamlit as st

from db_utils import query_df

st.set_page_config(page_title="Strain vs Family", layout="wide")

st.title("Strain vs. Family Cross-Tab")

view = st.radio(
    "View",
    ["Strain vs Family", "Species + Pathovar vs Family"],
    horizontal=True,
)

col1, col2 = st.columns(2)

if view == "Strain vs Family":
    query = """
    SELECT COALESCE(s.name, 'Unknown') AS strain,
           fm.family_id AS family,
           COUNT(*) AS count
    FROM family_member fm
    JOIN tale t ON t.id = fm.tale_id
    LEFT JOIN strain s ON s.id = t.strain_id
    GROUP BY strain, family
    """
else:
    query = """
    SELECT COALESCE(s.species, 'Unknown') || ' ' || COALESCE(s.pathovar, '') AS strain,
           fm.family_id AS family,
           COUNT(*) AS count
    FROM family_member fm
    JOIN tale t ON t.id = fm.tale_id
    LEFT JOIN strain s ON s.id = t.strain_id
    GROUP BY strain, family
    """

raw = query_df(query)

if raw.empty:
    st.warning("No family/strain data available.")
    st.stop()

raw["strain"] = raw["strain"].str.replace("Xanthomonas", "X", regex=False)
raw["display_label"] = raw["strain"]
raw["full_label"] = raw["strain"]

family_totals = raw.groupby("family")["count"].sum().sort_values(ascending=False)
strain_totals = raw.groupby("display_label")["count"].sum().sort_values(ascending=False)

max_strains = len(strain_totals)
top_strains = col1.slider(
    "Top strains (by TALE count)", 5, max(5, max_strains), min(20, max_strains), 5
)

families = family_totals.index.tolist()
strains = strain_totals.head(top_strains).index.tolist()

subset = raw[raw["family"].isin(families) & raw["display_label"].isin(strains)]

pivot = subset.pivot_table(
    index="display_label", columns="family", values="count", fill_value=0
)

long_df = pivot.reset_index().melt(
    id_vars="display_label", var_name="family", value_name="count"
)
long_df = long_df.merge(
    subset[["display_label", "full_label"]].drop_duplicates(),
    on="display_label",
    how="left",
)

chart_height = max(450, 24 * len(strains))

chart = (
    alt.Chart(long_df)
    .mark_rect()
    .encode(
        x=alt.X("family:N", title="Family", sort=families, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y(
            "display_label:N",
            title=("Species + Pathovar" if view == "Species + Pathovar vs Family" else "Strain"),
            sort=strains,
        ),
        color=alt.Color("count:Q", scale=alt.Scale(scheme="blues")),
        tooltip=["full_label:N", "family:N", "count:Q"],
    )
)

st.altair_chart(chart.properties(height=chart_height), use_container_width=True)
