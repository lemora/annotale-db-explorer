import altair as alt
import pandas as pd
import streamlit as st

from db_utils import load_families, load_tales, load_strains, query_df

LENGTH_SOURCES = ["Genomic coordinates", "DNA sequence", "Protein sequence"]
DISCREPANCY_LABELS = {
    0: "0 (inclusive)",
    1: "1 (end excluded)",
    3: "3 (stop+inclusive)",
    4: "4 (stop+excluded)",
    7: "7",
    22: "22",
    31: "31",
}
DISCREPANCY_ORDER = [
    "0 (inclusive)",
    "1 (end excluded)",
    "3 (stop+inclusive)",
    "4 (stop+excluded)",
    "7",
    "22",
    "31",
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

st.subheader("Family Size Distribution")
if families.empty:
    st.info("No family data available.")
else:
    family_chart = (
        alt.Chart(families)
        .mark_bar()
        .encode(
            x=alt.X("member_count:Q", bin=alt.Bin(maxbins=50), title="Members"),
            y=alt.Y("count():Q", title="Families"),
            tooltip=["count():Q"],
        )
    )
    st.altair_chart(family_chart.properties(height=300), use_container_width=True)

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
length_compare["genomic_length"] = (
    length_compare["end_pos"] - length_compare["start_pos"] + 1
)
length_compare["dna_length"] = length_compare["dna_seq"].fillna("").str.len()
length_compare["protein_length"] = (
    length_compare["protein_seq"].fillna("").str.len()
)
length_compare["length_diff"] = (
    length_compare["genomic_length"] - length_compare["dna_length"]
)
length_compare["protein_len_times3_minus_dna"] = (
    (length_compare["protein_length"] * 3) - length_compare["dna_length"]
)
metric_left, metric_right = st.columns(2)
comparable = length_compare[
    length_compare["genomic_length"].notnull()
    & (length_compare["genomic_length"] > 0)
    & (length_compare["dna_length"] > 0)
]
length_compare = comparable[
    comparable["genomic_length"] != comparable["dna_length"]
]
metric_left.metric("TALEs with comparable lengths", len(comparable))
metric_right.metric("TALEs with length discrepancy", len(length_compare))
if length_compare.empty:
    st.info("No TALEs found with differing lengths under the current filters.")
else:
    st.caption("Genomic minus DNA length (+1)")
    stats = (
        comparable[["genomic_length", "dna_length"]]
        .assign(
            genomic_minus_dna_plus1=lambda df: df["genomic_length"] - df["dna_length"]
        )
        .groupby("genomic_minus_dna_plus1")
        .size()
        .reset_index(name="count")
    )
    stats = stats[
        stats["genomic_minus_dna_plus1"].isin(DISCREPANCY_LABELS.keys())
    ]
    stats["label"] = stats["genomic_minus_dna_plus1"].map(DISCREPANCY_LABELS)
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
                title="Genomic − DNA length (+1)",
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
        length_compare[
            [
                "id",
                "name",
                "start_pos",
                "end_pos",
                "genomic_length",
                "dna_length",
                "length_diff",
                "protein_len_times3_minus_dna",
            ]
        ].rename(columns={"length_diff": "genomic_minus_dna_plus1"}),
        use_container_width=True,
        height=260,
    )

st.subheader("TALEs by Strain / Species + Pathovar")
if strains.empty:
    st.info("No strain metadata available.")
else:
    tales_with_strain = tales.merge(
        strains[["id", "name", "species", "pathovar"]],
        left_on="strain_id",
        right_on="id",
        how="left",
        suffixes=("", "_strain"),
    )
    view = st.radio(
        "",
        ["Strain", "Species + Pathovar"],
        index=0,
        horizontal=True,
        key="dist_view",
    )
    if view == "Strain":
        tales_with_strain["strain"] = tales_with_strain["name_strain"].fillna("Unknown")
        y_field = "strain"
        y_title = "Strain"
    else:
        tales_with_strain["species_pathovar"] = (
            tales_with_strain["species"].fillna("Unknown")
            + " "
            + tales_with_strain["pathovar"].fillna("")
        )
        tales_with_strain["species_pathovar"] = tales_with_strain[
            "species_pathovar"
        ].str.replace("Xanthomonas", "X.", regex=False)
        y_field = "species_pathovar"
        y_title = "Species + Pathovar"

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

st.subheader("RVD Composition")
family_options = ["All"] + families["name"].tolist()

col1, col2 = st.columns(2)
family_filter = col1.selectbox("Family", family_options)

strain_query = """
SELECT DISTINCT COALESCE(s.strain_name, s.legacy_strain_name, 'Unknown') AS strain
FROM tale_family_member fm
JOIN tale t ON t.id = fm.tale_id
LEFT JOIN assembly a ON a.id = t.assembly_id
LEFT JOIN samples s ON s.id = a.sample_id
WHERE (? = 'All' OR fm.family_id = ?)
ORDER BY strain
"""
strain_df = query_df(strain_query, params=[family_filter, family_filter])
strain_options = ["All"] + strain_df["strain"].fillna("Unknown").tolist()
strain_filter = col2.selectbox("Strain", strain_options)

query = """
SELECT r.rvd AS rvd, COUNT(*) AS count
FROM repeat r
JOIN tale t ON r.tale_id = t.id
LEFT JOIN tale_family_member fm ON t.id = fm.tale_id
LEFT JOIN assembly a ON a.id = t.assembly_id
LEFT JOIN samples s ON s.id = a.sample_id
WHERE (? = 'All' OR fm.family_id = ?)
  AND (? = 'All' OR COALESCE(s.strain_name, s.legacy_strain_name, 'Unknown') = ?)
GROUP BY r.rvd
ORDER BY count DESC
"""
rvd_counts = query_df(
    query, params=[family_filter, family_filter, strain_filter, strain_filter]
)

if rvd_counts.empty:
    st.warning("No repeats match the current filters.")
else:
    chart = (
        alt.Chart(rvd_counts)
        .mark_bar()
        .encode(
            y=alt.Y("rvd:N", sort="-x", title="RVD"),
            x=alt.X("count:Q", title="Count"),
            tooltip=["rvd:N", "count:Q"],
        )
    )
    st.altair_chart(chart.properties(height=400), use_container_width=True)

st.subheader("RVD Counts by Repeat Position")
pos_query = """
SELECT repeat_ordinal AS position, rvd, COUNT(*) AS count
FROM repeat
GROUP BY repeat_ordinal, rvd
ORDER BY repeat_ordinal
"""
pos_counts = query_df(pos_query)

if pos_counts.empty:
    st.warning("No repeat data available for position plot.")
else:
    mode = st.radio(
        "Plot type",
        ["Stacked bars", "Grouped bars"],
        horizontal=True,
        index=0,
        key="rvd_pos_plot_type",
    )
    stacked = mode == "Stacked bars"
    limit_default = mode == "Grouped bars"
    limit_topk = st.checkbox("Limit to top‑K RVDs per position", value=limit_default)
    default_k = 5 if mode == "Grouped bars" else 7
    top_k = st.slider("K", 3, 15, default_k, 1, disabled=not limit_topk)

    plot_counts = pos_counts.copy()
    if limit_topk:
        plot_counts = (
            plot_counts.sort_values(["position", "count"], ascending=[True, False])
            .groupby("position")
            .head(top_k)
        )

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
            xOffset=alt.XOffset("rvd:N") if not stacked else alt.value(0),
            y=alt.Y("count:Q", title="RVD count", stack="zero" if stacked else None),
            color=alt.Color("rvd:N", title="RVD"),
            tooltip=["position:Q", "rvd:N", "count:Q"],
        )
        .add_params(legend_selection)
        .transform_filter(legend_selection)
    )
    st.altair_chart(pos_chart.properties(height=400), use_container_width=True)
