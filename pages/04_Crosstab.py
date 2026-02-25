import altair as alt
import streamlit as st

from utils.db import load_crosstab_source
from utils.page import init_page
from utils.taxonomy import apply_taxon_fallback, build_legacy_taxon_map

init_page("Species/Pathovar/Strain vs. Family", "Crosstab")
st.title("Species/Pathovar/Strain vs. Family Cross-Tab")

view = st.radio(
    "",
    ["Species", "Species + Pathovar", "Strain"],
    index=0,
    horizontal=True,
    key="crosstab_view",
)

raw = load_crosstab_source()

if raw.empty:
    st.warning("No family/strain data available.")
    st.stop()

sample_tax = raw.drop_duplicates(subset=["sample_id"])
legacy_map = build_legacy_taxon_map(
    sample_tax,
    include_pathovar=True,
    legacy_col="legacy_strain_name",
    sample_id_col="sample_id",
)

if view != "Strain":
    include_pathovar = view == "Species + Pathovar"
    raw["strain"] = apply_taxon_fallback(
        raw,
        include_pathovar=include_pathovar,
        legacy_map=legacy_map,
        id_col="sample_id",
        legacy_col="legacy_strain_name",
    )
    raw = raw.groupby(["strain", "family"]).size().reset_index(name="count")
else:
    strain_name = raw["strain_name"].fillna("").str.strip()
    legacy_name = raw["legacy_strain_name"].fillna("").str.strip()
    raw["strain"] = strain_name.where(strain_name != "", legacy_name)
    raw["strain"] = raw["strain"].where(raw["strain"] != "", "Unknown")

    raw["species_pathovar"] = apply_taxon_fallback(
        raw,
        include_pathovar=True,
        legacy_map=legacy_map,
        id_col="sample_id",
        legacy_col="legacy_strain_name",
    )
    raw["species_pathovar"] = raw["species_pathovar"].fillna("Unknown")
    raw = raw.groupby(["strain", "family", "species_pathovar"]).size().reset_index(
        name="count"
    )

raw["strain"] = raw["strain"].str.replace("Xanthomonas", "X.", regex=False)

family_totals = raw.groupby("family")["count"].sum().sort_values(ascending=False)
strain_totals = raw.groupby("strain")["count"].sum().sort_values(ascending=False)

max_strains = len(strain_totals)
if "prev_view" not in st.session_state:
    st.session_state["prev_view"] = st.session_state["crosstab_view"]
if st.session_state["crosstab_view"] != st.session_state["prev_view"]:
    st.session_state["crosstab_show_all"] = False
    st.session_state["prev_view"] = st.session_state["crosstab_view"]

if view == "Species":
    top_n = max_strains
else:
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

families = sorted(family_totals.index.tolist())
strains = strain_totals.head(top_n).index.tolist()

subset = raw[raw["family"].isin(families) & raw["strain"].isin(strains)]

pivot = subset.pivot_table(index="strain", columns="family", values="count", fill_value=0)

long_df = pivot.reset_index().melt(id_vars="strain", var_name="family", value_name="count")
if view == "Strain":
    strain_meta = (
        raw.dropna(subset=["species_pathovar"])
        .groupby(["strain", "species_pathovar"])["count"]
        .sum()
        .reset_index()
        .sort_values(["strain", "count"], ascending=[True, False])
        .groupby("strain")
        .head(1)[["strain", "species_pathovar"]]
    )
    long_df = long_df.merge(strain_meta, on="strain", how="left")

chart_height = max(450, 24 * len(strains))

tooltip_fields = ["strain:N", "family:N", "count:Q"]
if view == "Strain":
    tooltip_fields = ["strain:N", "species_pathovar:N", "family:N", "count:Q"]

chart = (
    alt.Chart(long_df)
    .mark_rect()
    .encode(
        x=alt.X("family:N", title="Family", sort=families, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y(
            "strain:N",
            title=(
                "Species + Pathovar"
                if view == "Species + Pathovar"
                else ("Species" if view == "Species" else "Strain")
            ),
            sort=strains,
            axis=alt.Axis(labelLimit=1000, labelOverlap=False),
        ),
        color=alt.condition(
            "datum.count == 0",
            alt.value("#ffffff"),
            alt.Color("count:Q", scale=alt.Scale(scheme="blues")),
        ),
        tooltip=tooltip_fields,
    )
)

st.altair_chart(chart.properties(height=chart_height), use_container_width=True)
