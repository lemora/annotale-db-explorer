import altair as alt
import pandas as pd
import streamlit as st

from db_utils import load_families, load_tales, load_strains, query_df

st.set_page_config(page_title="Distributions", layout="wide")

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
length_source = st.selectbox(
    "Length source",
    ["Genomic coordinates", "DNA sequence", "Protein sequence"],
    index=0,
)
exclude_pseudo = st.checkbox("Exclude pseudo TALEs", value=False)

lengths = tales.copy()
if exclude_pseudo:
    lengths = lengths[lengths["is_pseudo"].fillna(0) == 0]
if length_source == "Genomic coordinates":
    lengths["length"] = lengths["end_pos"] - lengths["start_pos"] + 1
elif length_source == "DNA sequence":
    lengths["length"] = lengths["dna_seq"].fillna("").str.len()
else:
    lengths["length"] = lengths["protein_seq"].fillna("").str.len()

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
SELECT DISTINCT COALESCE(s.name, 'Unknown') AS strain
FROM family_member fm
JOIN tale t ON t.id = fm.tale_id
LEFT JOIN strain s ON t.strain_id = s.id
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
LEFT JOIN family_member fm ON t.id = fm.tale_id
LEFT JOIN strain s ON t.strain_id = s.id
WHERE (? = 'All' OR fm.family_id = ?)
  AND (? = 'All' OR s.name = ?)
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
    pos_chart = (
        alt.Chart(pos_counts)
        .mark_bar()
        .encode(
            x=alt.X(
                "position:Q",
                title="Repeat position within TALE",
                scale=alt.Scale(domain=[0, float(pos_counts["position"].max())]),
            ),
            y=alt.Y("count:Q", title="RVD count", stack="zero"),
            color=alt.Color("rvd:N", title="RVD"),
            tooltip=["position:Q", "rvd:N", "count:Q"],
        )
    )
    st.altair_chart(pos_chart.properties(height=400), use_container_width=True)
