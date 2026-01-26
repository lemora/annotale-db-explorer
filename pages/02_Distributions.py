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
if not families.empty:
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
else:
    st.info("No family data available.")

st.subheader("TALE Lengths")
length_source = st.selectbox(
    "Length source",
    ["Genomic coordinates", "DNA sequence", "Protein sequence"],
    index=0,
)

lengths = tales.copy()
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
        y=alt.Y("count():Q", title="TALEs"),
        tooltip=["count():Q"],
    )
)

st.altair_chart(len_chart.properties(height=300), use_container_width=True)

st.subheader("TALEs by Strain")
if not strains.empty:
    tales_with_strain = tales.merge(
        strains[["id", "name", "species", "pathovar"]],
        left_on="strain_id",
        right_on="id",
        how="left",
        suffixes=("", "_strain"),
    )
    top_n = st.slider("Top strains", 5, 50, 20, 5)
    counts = (
        tales_with_strain.groupby("name_strain").size().reset_index(name="count")
    )
    counts = counts.sort_values("count", ascending=False).head(top_n)

    strain_chart = (
        alt.Chart(counts)
        .mark_bar()
        .encode(
            y=alt.Y("name_strain:N", sort="-x", title="Strain"),
            x=alt.X("count:Q", title="TALEs"),
            tooltip=["count:Q"],
        )
    )
    st.altair_chart(strain_chart.properties(height=400), use_container_width=True)
else:
    st.info("No strain metadata available.")

st.subheader("RVD Composition")
family_options = ["All"] + families["name"].tolist()
strain_options = ["All"] + strains["name"].fillna("Unknown").tolist()

col1, col2, col3 = st.columns(3)
family_filter = col1.selectbox("Family", family_options)
strain_filter = col2.selectbox("Strain", strain_options)
top_n = col3.slider("Top RVDs", 10, 50, 20, 5)

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

rvd_counts = query_df(query, params=[family_filter, family_filter, strain_filter, strain_filter])

if rvd_counts.empty:
    st.warning("No repeats match the current filters.")
else:
    rvd_counts = rvd_counts.head(top_n)
    chart = (
        alt.Chart(rvd_counts)
        .mark_bar()
        .encode(
            y=alt.Y("rvd:N", sort="-x", title="RVD"),
            x=alt.X("count:Q", title="Count"),
            tooltip=["count:Q"],
        )
    )
    st.altair_chart(chart.properties(height=400), use_container_width=True)
