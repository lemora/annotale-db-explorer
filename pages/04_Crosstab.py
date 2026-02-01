import altair as alt
import streamlit as st

from db_utils import query_df

st.set_page_config(page_title="Pathovar/Strain vs. Family", layout="wide")

st.sidebar.image("img/AnnoTALE_transp.png", width=140)

st.session_state["active_page"] = "Crosstab"
st.title("Pathovar/Strain vs. Family Cross-Tab")

view = st.radio(
    "",
    ["Species + Pathovar vs. Family", "Strain vs. Family"],
    index=0,
    horizontal=True,
    key="crosstab_view",
)

if view == "Strain vs. Family":
    query = """
    SELECT COALESCE(s.strain_name, s.legacy_strain_name, 'Unknown') AS strain,
           fm.family_id AS family,
           COUNT(*) AS count
    FROM tale_family_member fm
    JOIN tale t ON t.id = fm.tale_id
    LEFT JOIN assembly a ON a.id = t.assembly_id
    LEFT JOIN samples s ON s.id = a.sample_id
    GROUP BY strain, family
    """
else:
    query = """
    SELECT COALESCE(tx.species, 'Unknown') || ' ' || COALESCE(tx.pathovar, '') AS strain,
           fm.family_id AS family,
           COUNT(*) AS count
    FROM tale_family_member fm
    JOIN tale t ON t.id = fm.tale_id
    LEFT JOIN assembly a ON a.id = t.assembly_id
    LEFT JOIN samples s ON s.id = a.sample_id
    LEFT JOIN taxonomy tx ON tx.id = s.taxon_id
    GROUP BY strain, family
    """

raw = query_df(query)

if raw.empty:
    st.warning("No family/strain data available.")
    st.stop()

raw["strain"] = raw["strain"].str.replace("Xanthomonas", "X.", regex=False)

family_totals = raw.groupby("family")["count"].sum().sort_values(ascending=False)
strain_totals = raw.groupby("strain")["count"].sum().sort_values(ascending=False)

max_strains = len(strain_totals)
if "prev_view" not in st.session_state:
    st.session_state["prev_view"] = st.session_state["crosstab_view"]
if st.session_state["crosstab_view"] != st.session_state["prev_view"]:
    st.session_state["crosstab_show_all"] = False
    st.session_state["prev_view"] = st.session_state["crosstab_view"]

show_all = st.checkbox("Show all rows", value=False, key="crosstab_show_all")
top_n = st.slider(
    "Show top rows (by total TALE count)",
    5,
    max(5, max_strains),
    min(20, max_strains),
    5,
    disabled=show_all,
)
top_n = max_strains if show_all else top_n

families = family_totals.index.tolist()
strains = strain_totals.head(top_n).index.tolist()

subset = raw[raw["family"].isin(families) & raw["strain"].isin(strains)]

pivot = subset.pivot_table(index="strain", columns="family", values="count", fill_value=0)

long_df = pivot.reset_index().melt(id_vars="strain", var_name="family", value_name="count")

chart_height = max(450, 24 * len(strains))

chart = (
    alt.Chart(long_df)
    .mark_rect()
    .encode(
        x=alt.X("family:N", title="Family", sort=families, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y(
            "strain:N",
            title=("Species + Pathovar" if view == "Species + Pathovar vs. Family" else "Strain"),
            sort=strains,
            axis=alt.Axis(labelLimit=1000, labelOverlap=False),
        ),
        color=alt.condition(
            "datum.count == 0",
            alt.value("#ffffff"),
            alt.Color("count:Q", scale=alt.Scale(scheme="blues")),
        ),
        tooltip=["strain:N", "family:N", "count:Q"],
    )
)

st.altair_chart(chart.properties(height=chart_height), use_container_width=True)
