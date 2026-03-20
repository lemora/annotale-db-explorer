import altair as alt
import pandas as pd
import streamlit as st

from utils.db import (
    load_strains,
    load_tale_distribution_source,
)
from utils.page import init_page
from utils.taxonomy import (
    abbreviate_taxon_labels,
    apply_taxon_fallback,
    build_legacy_taxon_map,
)

LENGTH_SOURCES = ["Genomic coordinates", "DNA sequence", "Protein sequence"]
def apply_tale_filters(
    df: pd.DataFrame, exclude_pseudo: bool, exclude_missing_genomic: bool
) -> pd.DataFrame:
    filtered = df
    if exclude_pseudo:
        filtered = filtered[filtered["is_pseudo"].fillna(0) == 0]
    if exclude_missing_genomic:
        filtered = filtered[
            filtered["start_pos"].notnull() & filtered["end_pos"].notnull()
        ]
    return filtered


def add_length_column(df: pd.DataFrame, source: str) -> pd.Series:
    if source == "Genomic coordinates":
        return df["end_pos"] - df["start_pos"] + 1
    if source == "DNA sequence":
        return df["dna_length"]
    return df["protein_length"]


@st.cache_data(show_spinner=False)
def build_length_source(
    source: str, exclude_pseudo: bool, exclude_missing_genomic: bool
) -> pd.DataFrame:
    tales = load_tale_distribution_source()
    filtered = apply_tale_filters(tales, exclude_pseudo, exclude_missing_genomic).copy()
    filtered["length"] = add_length_column(filtered, source)
    filtered = filtered[pd.notnull(filtered["length"]) & (filtered["length"] > 0)]
    return filtered[["length"]]


@st.cache_data(show_spinner=False)
def build_distribution_counts(view: str) -> pd.DataFrame:
    tales = load_tale_distribution_source()
    strains = load_strains()
    tales_with_strain = tales.merge(
        strains[
            [
                "id",
                "name",
                "species",
                "pathovar",
                "taxon_name",
                "legacy_strain_name",
            ]
        ],
        left_on="strain_id",
        right_on="id",
        how="left",
        suffixes=("", "_strain"),
    )

    if view == "Strain":
        counts = (
            tales_with_strain.assign(
                label=tales_with_strain["name"].fillna("Unknown")
            )
            .groupby("label")
            .size()
            .reset_index(name="count")
        )
        return counts.sort_values("count", ascending=False)

    include_pathovar = view == "Species + Pathovar"
    legacy_map = build_legacy_taxon_map(
        strains,
        include_pathovar=include_pathovar,
        legacy_col="legacy_strain_name",
        sample_id_col="id",
    )
    labels = apply_taxon_fallback(
        tales_with_strain,
        include_pathovar=include_pathovar,
        legacy_map=legacy_map,
        id_col="strain_id",
        legacy_col="legacy_strain_name",
    )
    labels = abbreviate_taxon_labels(labels)
    counts = (
        tales_with_strain.assign(label=labels)
        .groupby("label")
        .size()
        .reset_index(name="count")
    )
    return counts.sort_values("count", ascending=False)

init_page("Distributions", "Distributions")
st.title("Distributions and Summary")

strains = load_strains()
tales = load_tale_distribution_source()

if tales.empty:
    st.warning("No TALE records found.")
    st.stop()

st.subheader("TALE Lengths")
length_source = st.selectbox("Length source", LENGTH_SOURCES, index=0)
exclude_pseudo = st.checkbox("Exclude pseudo TALEs", value=True)
exclude_missing_genomic = st.checkbox(
    "Exclude TALEs without genomic positions", value=False
)

lengths = build_length_source(
    length_source,
    exclude_pseudo,
    exclude_missing_genomic,
)

len_chart = (
    alt.Chart(lengths)
    .mark_bar()
    .encode(
        x=alt.X("length:Q", bin=alt.Bin(maxbins=60), title="Length"),
        y=alt.Y("count():Q", title="Number of TALEs"),
        tooltip=["count():Q"],
    )
)

st.altair_chart(len_chart.properties(height=300), use_container_width=True)

st.subheader("TALEs by Strain / Species + Pathovar")
if strains.empty:
    st.info("No strain metadata available.")
else:
    view = st.radio(
        "TALE distribution view",
        ["Species", "Species + Pathovar", "Strain"],
        index=0,
        horizontal=True,
        key="dist_view",
        label_visibility="collapsed",
    )
    counts = build_distribution_counts(view)
    y_title = "Strain" if view == "Strain" else view

    show_all_labels = st.checkbox("Show all labels", value=False)
    chart_height = max(400, 18 * len(counts)) if show_all_labels else 400
    y_axis = (
        alt.Axis(labelLimit=2000, labelOverlap=False, title=y_title)
        if show_all_labels
        else alt.Axis(labels=False, title=y_title)
    )

    strain_chart = (
        alt.Chart(counts)
        .mark_bar()
        .encode(
            y=alt.Y(
                "label:N",
                sort="-x",
                title=y_title,
                axis=y_axis,
            ),
            x=alt.X("count:Q", title="TALE count"),
            tooltip=["label:N", "count:Q"],
        )
    )
    st.altair_chart(strain_chart.properties(height=chart_height), use_container_width=True)

# st.markdown("---")
# with st.expander("Taxonomy Comparison (Legacy vs NCBI)", expanded=False):
#     st.caption(
#         "Legacy taxonomy is inferred from the first token of "
#         "`samples.legacy_strain_name` and mapped to long-form taxa."
#     )
#
#     tax_raw = load_taxonomy_comparison_source()
#
#     if tax_raw.empty:
#         st.info("No sample/taxonomy data available.")
#     else:
#         def format_ncbi_taxon(row: pd.Series) -> str:
#             species = row.get("species")
#             pathovar = row.get("pathovar")
#             if pd.notna(species) and str(species).strip():
#                 if pd.notna(pathovar) and str(pathovar).strip():
#                     return f"{species} pv. {pathovar}"
#                 return str(species)
#             taxon_name = row.get("taxon_name")
#             if pd.notna(taxon_name) and str(taxon_name).strip():
#                 return str(taxon_name)
#             return "Unknown"
#
#         tax_raw["ncbi_taxon"] = tax_raw.apply(format_ncbi_taxon, axis=1)
#         seed = (
#             tax_raw.groupby(["legacy_code", "ncbi_taxon"])
#             .size()
#             .reset_index(name="count")
#             .sort_values(["legacy_code", "count"], ascending=[True, False])
#             .groupby("legacy_code")
#             .head(1)
#         )
#         legacy_map = dict(seed.set_index("legacy_code")["ncbi_taxon"].to_dict())
#         tax_raw["legacy_taxon"] = tax_raw["legacy_code"].map(legacy_map)
#         tax_raw["legacy_taxon"] = tax_raw["legacy_taxon"].fillna(
#             "Unknown legacy taxonomy"
#         )
#         tax_raw["ncbi_taxon"] = tax_raw["ncbi_taxon"].where(
#             tax_raw["ncbi_taxon"] != "Unknown", tax_raw["legacy_taxon"]
#         )
#         tax_raw["ncbi_taxon"] = tax_raw["ncbi_taxon"].replace(
#             "Unknown legacy taxonomy", "Unknown"
#         )
#         tax_raw["ncbi_taxon"] = tax_raw["ncbi_taxon"].fillna("Unknown")
#
#         mismatches = tax_raw[
#             (tax_raw["legacy_taxon"] != "Unknown legacy taxonomy")
#             & (tax_raw["ncbi_taxon"] != "Unknown")
#             & (tax_raw["legacy_taxon"] != tax_raw["ncbi_taxon"])
#         ].copy()
#
#         if mismatches.empty:
#             st.info("No mismatches found between legacy and NCBI taxonomy.")
#         else:
#             st.caption("Taxonomy mismatch overview")
#             mismatch_counts = (
#                 mismatches.groupby(["legacy_taxon", "ncbi_taxon"])
#                 .size()
#                 .reset_index(name="count")
#                 .sort_values("count", ascending=False)
#             )
#             mismatch_chart = (
#                 alt.Chart(mismatch_counts)
#                 .mark_bar()
#                 .encode(
#                     y=alt.Y(
#                         "legacy_taxon:N",
#                         sort="-x",
#                         title="Legacy taxonomy",
#                         axis=alt.Axis(labelLimit=300),
#                     ),
#                     x=alt.X("count:Q", title="Mismatch count"),
#                     color=alt.Color("ncbi_taxon:N", title="NCBI taxonomy"),
#                     tooltip=["legacy_taxon:N", "ncbi_taxon:N", "count:Q"],
#                 )
#             )
#             st.altair_chart(
#                 mismatch_chart.properties(height=320),
#                 use_container_width=True,
#             )
#
#             st.caption("Samples with differing taxonomy")
#             mismatch_rows = (
#                 mismatches.groupby(
#                     ["legacy_taxon", "ncbi_taxon", "ncbi_tax_id"]
#                 )
#                 .size()
#                 .reset_index(name="count")
#                 .sort_values("count", ascending=False)
#             )
#             st.dataframe(mismatch_rows, use_container_width=True, height=320)
