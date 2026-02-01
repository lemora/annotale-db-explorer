import altair as alt
import pandas as pd
import streamlit as st

from db_utils import query_df

st.set_page_config(page_title="Taxonomy Comparison", layout="wide")

st.title("Taxonomy: NCBI vs Legacy")
st.caption(
    "Legacy taxonomy is inferred from the first token of `samples.legacy_strain_name` "
    "and mapped to long-form taxa."
)

raw = query_df(
    """
    SELECT s.id AS sample_id,
           s.legacy_strain_name,
           s.strain_name,
           s.geo_tag,
           s.collection_date,
           s.biosample_id,
           tx.ncbi_tax_id,
           tx.rank,
           tx.raw_name AS taxon_name,
           tx.species,
           tx.pathovar,
           CASE
             WHEN s.legacy_strain_name IS NULL OR TRIM(s.legacy_strain_name) = '' THEN NULL
             WHEN instr(TRIM(s.legacy_strain_name), ' ') > 0
               THEN substr(TRIM(s.legacy_strain_name), 1, instr(TRIM(s.legacy_strain_name), ' ') - 1)
             ELSE TRIM(s.legacy_strain_name)
           END AS legacy_code
    FROM samples s
    LEFT JOIN taxonomy tx ON tx.id = s.taxon_id
    """
)

if raw.empty:
    st.warning("No sample/taxonomy data available.")
    st.stop()


def format_ncbi_taxon(row: pd.Series) -> str:
    species = row.get("species")
    pathovar = row.get("pathovar")
    if pd.notna(species) and str(species).strip():
        if pd.notna(pathovar) and str(pathovar).strip():
            return f"{species} pv. {pathovar}"
        return str(species)
    taxon_name = row.get("taxon_name")
    if pd.notna(taxon_name) and str(taxon_name).strip():
        return str(taxon_name)
    return "Unknown"


raw["legacy_code"] = raw["legacy_code"].fillna("Unknown")
raw["ncbi_taxon"] = raw.apply(format_ncbi_taxon, axis=1)

seed = (
    raw.groupby(["legacy_code", "ncbi_taxon"])
    .size()
    .reset_index(name="count")
    .sort_values(["legacy_code", "count"], ascending=[True, False])
    .groupby("legacy_code")
    .head(1)
)
legacy_map = dict(seed.set_index("legacy_code")["ncbi_taxon"].to_dict())
raw["legacy_taxon"] = raw["legacy_code"].map(legacy_map)
raw["legacy_taxon"] = raw["legacy_taxon"].fillna("Unknown legacy taxonomy")

st.subheader("Taxonomy Mismatch Overview")
mismatches = raw[
    (raw["legacy_taxon"] != "Unknown legacy taxonomy")
    & (raw["ncbi_taxon"] != "Unknown")
    & (raw["legacy_taxon"] != raw["ncbi_taxon"])
].copy()

if mismatches.empty:
    st.info("No mismatches found between legacy and NCBI taxonomy.")
else:
    mismatch_counts = (
        mismatches.groupby(["legacy_taxon", "ncbi_taxon"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    plot_df = mismatch_counts
    mismatch_chart = (
        alt.Chart(plot_df)
        .mark_bar()
        .encode(
            y=alt.Y(
                "legacy_taxon:N",
                sort="-x",
                title="Legacy taxonomy",
                axis=alt.Axis(labelLimit=300),
            ),
            x=alt.X("count:Q", title="Mismatch count"),
            color=alt.Color("ncbi_taxon:N", title="NCBI taxonomy"),
            tooltip=["legacy_taxon:N", "ncbi_taxon:N", "count:Q"],
        )
    )
    st.altair_chart(mismatch_chart.properties(height=360), use_container_width=True)

st.subheader("Samples With Differing Taxonomy")
limit = st.slider("Mismatch sample limit", 10, 200, 50, 10)
show_cols = [
    "legacy_taxon",
    "ncbi_taxon",
    "ncbi_tax_id",
]
grouped_rows = (
    mismatches.groupby(show_cols)
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)
st.dataframe(grouped_rows.head(limit), use_container_width=True, height=360)
