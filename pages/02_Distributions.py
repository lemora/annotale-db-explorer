import altair as alt
import pandas as pd
import streamlit as st

from db_utils import load_families, load_tales, load_strains, query_df
from taxonomy_utils import apply_taxon_fallback, build_legacy_taxon_map

LENGTH_SOURCES = ["Genomic coordinates", "DNA sequence", "Protein sequence"]
DISCREPANCY_LABELS = {
    -1: "-1 (ei)",
    0: "0 (ee)",
    2: "2 (stop+ei)",
    3: "3 (stop + ee)",
    6: "6 (aa+stop+ee)",
    21: "21",
    30: "30",
}
DISCREPANCY_ORDER = [
    "-1 (ei)",
    "0 (ee)",
    "2 (stop+ei)",
    "3 (stop + ee)",
    "6 (aa+stop+ee)",
    "21",
    "30",
]


def apply_tale_filters(
    df: pd.DataFrame, exclude_pseudo: bool, exclude_missing_genomic: bool
) -> pd.DataFrame:
    filtered = df.copy()
    if exclude_pseudo:
        filtered = filtered[filtered["is_pseudo"].fillna(0) == 0]
    if exclude_missing_genomic:
        filtered = filtered[
            filtered["start_pos"].notnull() & filtered["end_pos"].notnull()
        ]
    return filtered


def add_length_column(df: pd.DataFrame, source: str) -> pd.DataFrame:
    if source == "Genomic coordinates":
        df["length"] = df["end_pos"] - df["start_pos"] + 1
    elif source == "DNA sequence":
        df["length"] = df["dna_seq"].fillna("").str.len()
    else:
        df["length"] = df["protein_seq"].fillna("").str.len()
    return df

st.set_page_config(page_title="Distributions", layout="wide")

st.sidebar.image("img/AnnoTALE_transp.png", width=140)

st.session_state["active_page"] = "Distributions"
st.title("Distributions and Summary")

families = load_families()
tales = load_tales()
strains = load_strains()

if tales.empty:
    st.warning("No TALE records found.")
    st.stop()

st.subheader("TALE Lengths")
length_source = st.selectbox("Length source", LENGTH_SOURCES, index=0)
exclude_pseudo = st.checkbox("Exclude pseudo TALEs", value=True)
exclude_missing_genomic = st.checkbox(
    "Exclude TALEs without genomic positions", value=False
)

lengths = apply_tale_filters(tales, exclude_pseudo, exclude_missing_genomic)
lengths = add_length_column(lengths, length_source)
lengths = lengths[pd.notnull(lengths["length"]) & (lengths["length"] > 0)]

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

st.caption("TALEs where DNA length differs from genomic length")
length_compare = lengths.copy()
length_compare["genomic_length"] = length_compare["end_pos"] - length_compare["start_pos"]
length_compare["dna_length"] = length_compare["dna_seq"].fillna("").str.len()
length_compare["length_diff"] = (
    length_compare["genomic_length"] - length_compare["dna_length"]
)
length_compare["dna_last3"] = (
    length_compare["dna_seq"].fillna("").str.upper().str[-3:]
)
length_compare["dna_ends_with_stop"] = (
    length_compare["dna_seq"]
    .fillna("")
    .str.upper()
    .str.endswith(("TAA", "TAG", "TGA"))
)
metric_left, metric_right = st.columns(2)
comparable = length_compare[
    length_compare["genomic_length"].notnull()
    & (length_compare["genomic_length"] > 0)
    & (length_compare["dna_length"] > 0)
]
length_compare = comparable[comparable["genomic_length"] != comparable["dna_length"]]
table_data = comparable.assign(
    genomic_minus_dna=lambda df: df["genomic_length"] - df["dna_length"]
)
metric_left.metric("Number of TALEs", len(comparable))
metric_right.metric("TALEs with length discrepancy", len(length_compare))
if length_compare.empty:
    st.info("No TALEs found with differing lengths under the current filters.")
else:
    st.caption("Genomic minus DNA length")
    stats = (
        comparable[["genomic_length", "dna_length"]]
        .assign(
            genomic_minus_dna=lambda df: df["genomic_length"] - df["dna_length"]
        )
        .groupby("genomic_minus_dna")
        .size()
        .reset_index(name="count")
    )
    stats = stats[stats["genomic_minus_dna"].isin(DISCREPANCY_LABELS.keys())]
    stats["label"] = stats["genomic_minus_dna"].map(DISCREPANCY_LABELS)
    stats = (
        stats.set_index("label")
        .reindex(DISCREPANCY_ORDER, fill_value=0)
        .reset_index()
    )
    bar_chart = (
        alt.Chart(stats)
        .mark_bar()
        .encode(
            x=alt.X(
                "label:N",
                title="Genomic − DNA length",
                sort=DISCREPANCY_ORDER,
            ),
            y=alt.Y("count:Q", title="TALE count"),
            tooltip=["label:N", "count:Q"],
        )
    )
    label_chart = (
        alt.Chart(stats)
        .mark_text(dy=-6)
        .encode(
            x=alt.X("label:N", sort=DISCREPANCY_ORDER),
            y=alt.Y("count:Q"),
            text=alt.Text("count:Q"),
        )
    )
    st.altair_chart(
        (bar_chart + label_chart).properties(height=220), use_container_width=True
    )
    st.dataframe(
        table_data[
            [
                "id",
                "name",
                "strain_id",
                "start_pos",
                "end_pos",
                "strand",
                "genomic_length",
                "dna_length",
                "genomic_minus_dna",
                "dna_last3",
                "dna_ends_with_stop",
            ]
        ],
        use_container_width=True,
        height=260,
    )

st.subheader("TALEs by Strain / Species + Pathovar")
if strains.empty:
    st.info("No strain metadata available.")
else:
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
    view = st.radio(
        "TALE distribution view",
        ["Species", "Species + Pathovar", "Strain"],
        index=0,
        horizontal=True,
        key="dist_view",
        label_visibility="collapsed",
    )
    if view == "Strain":
        tales_with_strain["strain"] = tales_with_strain["name_strain"].fillna("Unknown")
        y_field = "strain"
        y_title = "Strain"
    else:
        include_pathovar = view == "Species + Pathovar"
        legacy_map = build_legacy_taxon_map(
            strains,
            include_pathovar=include_pathovar,
            legacy_col="legacy_strain_name",
            sample_id_col="id",
        )
        tales_with_strain["species_pathovar"] = apply_taxon_fallback(
            tales_with_strain,
            include_pathovar=include_pathovar,
            legacy_map=legacy_map,
            id_col="strain_id",
            legacy_col="legacy_strain_name",
        )
        tales_with_strain["species_pathovar"] = tales_with_strain[
            "species_pathovar"
        ].str.replace("Xanthomonas", "X.", regex=False)
        y_field = "species_pathovar"
        y_title = "Species" if view == "Species" else "Species + Pathovar"

    counts = tales_with_strain.groupby(y_field).size().reset_index(name="count")
    counts = counts.sort_values("count", ascending=False)

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
                f"{y_field}:N",
                sort="-x",
                title=y_title,
                axis=y_axis,
            ),
            x=alt.X("count:Q", title="TALE count"),
            tooltip=[f"{y_field}:N", "count:Q"],
        )
    )
    st.altair_chart(strain_chart.properties(height=chart_height), use_container_width=True)

st.subheader("RVD Counts by Repeat Position")
pos_query = """
SELECT repeat_ordinal AS position, rvd, tale_id
FROM repeat
"""
pos_raw = query_df(pos_query)

if pos_raw.empty:
    st.warning("No repeat data available for position plot.")
else:
    tax_filter = st.radio(
        "Filter by taxonomy",
        ["All", "Species", "Species + Pathovar"],
        horizontal=True,
        key="rvd_pos_tax_filter",
    )

    plot_source = pos_raw.merge(
        tales[["id", "strain_id"]],
        left_on="tale_id",
        right_on="id",
        how="left",
        suffixes=("", "_tale"),
    )
    plot_source = plot_source.merge(
        strains[["id", "species", "pathovar", "taxon_name", "legacy_strain_name"]],
        left_on="strain_id",
        right_on="id",
        how="left",
        suffixes=("", "_strain"),
    )

    if tax_filter != "All":
        if strains.empty:
            st.info("No strain metadata available; showing all repeats.")
        else:
            include_pathovar = tax_filter == "Species + Pathovar"
            legacy_map = build_legacy_taxon_map(
                strains,
                include_pathovar=include_pathovar,
                legacy_col="legacy_strain_name",
                sample_id_col="id",
            )
            plot_source["species_pathovar"] = apply_taxon_fallback(
                plot_source,
                include_pathovar=include_pathovar,
                legacy_map=legacy_map,
                id_col="strain_id",
                legacy_col="legacy_strain_name",
            )
            plot_source["species_pathovar"] = plot_source["species_pathovar"].str.replace(
                "Xanthomonas", "X.", regex=False
            )
            taxon_options = ["All"] + sorted(
                plot_source["species_pathovar"].dropna().unique().tolist()
            )
            selected_taxon = st.selectbox(
                tax_filter, taxon_options, key="rvd_pos_taxon"
            )
            if selected_taxon != "All":
                plot_source = plot_source[
                    plot_source["species_pathovar"] == selected_taxon
                ]

    if plot_source.empty:
        st.warning("No repeats match the current taxonomy filter.")
        plot_counts = pd.DataFrame(columns=["position", "rvd", "count"])
    else:
        plot_counts = (
            plot_source.groupby(["position", "rvd"]).size().reset_index(name="count")
        )

    limit_topk = st.checkbox("Limit to top‑K RVDs per position", value=False)
    default_k = 7
    top_k = st.slider("K", 3, 15, default_k, 1, disabled=not limit_topk)

    if limit_topk:
        plot_counts = (
            plot_counts.sort_values(["position", "count"], ascending=[True, False])
            .groupby("position")
            .head(top_k)
        )

    if plot_counts.empty:
        st.info("No repeat data to plot for the current filters.")
    else:
        legend_selection = alt.selection_point(fields=["rvd"], bind="legend")
        pos_chart = (
            alt.Chart(plot_counts)
            .mark_bar()
            .encode(
                x=alt.X(
                    "position:O",
                    title="Repeat position within TALE",
                    sort="ascending",
                ),
                y=alt.Y(
                    "count:Q",
                    title="RVD percent",
                    stack="normalize",
                    axis=alt.Axis(format=".0%"),
                ),
                color=alt.Color("rvd:N", title="RVD"),
                tooltip=[
                    "position:Q",
                    "rvd:N",
                    "count:Q",
                    alt.Tooltip("percent:Q", title="Percent", format=".1%"),
                ],
            )
            .add_params(legend_selection)
            .transform_filter(legend_selection)
            .transform_joinaggregate(total="sum(count)", groupby=["position"])
            .transform_calculate(percent="datum.count / datum.total")
        )
        st.altair_chart(pos_chart.properties(height=400), use_container_width=True)

st.markdown("---")
st.subheader("Taxonomy Comparison (Legacy vs NCBI)")
st.caption(
    "Legacy taxonomy is inferred from the first token of `samples.legacy_strain_name` "
    "and mapped to long-form taxa."
)

tax_raw = query_df(
    """
    SELECT s.id AS sample_id,
           s.legacy_strain_name,
           tx.ncbi_tax_id,
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

if tax_raw.empty:
    st.info("No sample/taxonomy data available.")
else:
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

    tax_raw["ncbi_taxon"] = tax_raw.apply(format_ncbi_taxon, axis=1)
    seed = (
        tax_raw.groupby(["legacy_code", "ncbi_taxon"])
        .size()
        .reset_index(name="count")
        .sort_values(["legacy_code", "count"], ascending=[True, False])
        .groupby("legacy_code")
        .head(1)
    )
    legacy_map = dict(seed.set_index("legacy_code")["ncbi_taxon"].to_dict())
    tax_raw["legacy_taxon"] = tax_raw["legacy_code"].map(legacy_map)
    tax_raw["legacy_taxon"] = tax_raw["legacy_taxon"].fillna("Unknown legacy taxonomy")
    tax_raw["ncbi_taxon"] = tax_raw["ncbi_taxon"].where(
        tax_raw["ncbi_taxon"] != "Unknown", tax_raw["legacy_taxon"]
    )
    tax_raw["ncbi_taxon"] = tax_raw["ncbi_taxon"].replace(
        "Unknown legacy taxonomy", "Unknown"
    )
    tax_raw["ncbi_taxon"] = tax_raw["ncbi_taxon"].fillna("Unknown")

    mismatches = tax_raw[
        (tax_raw["legacy_taxon"] != "Unknown legacy taxonomy")
        & (tax_raw["ncbi_taxon"] != "Unknown")
        & (tax_raw["legacy_taxon"] != tax_raw["ncbi_taxon"])
    ].copy()

    if mismatches.empty:
        st.info("No mismatches found between legacy and NCBI taxonomy.")
    else:
        st.caption("Taxonomy mismatch overview")
        mismatch_counts = (
            mismatches.groupby(["legacy_taxon", "ncbi_taxon"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        mismatch_chart = (
            alt.Chart(mismatch_counts)
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
        st.altair_chart(mismatch_chart.properties(height=320), use_container_width=True)

        st.caption("Samples with differing taxonomy")
        mismatch_rows = (
            mismatches.groupby(["legacy_taxon", "ncbi_taxon", "ncbi_tax_id"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        st.dataframe(mismatch_rows, use_container_width=True, height=320)
