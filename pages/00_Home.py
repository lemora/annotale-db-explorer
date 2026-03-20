import streamlit as st

from utils.db import load_families, load_strains, load_tales
from utils.page import init_page

init_page("Home", "Home", require_db=False)
st.title("AnnoTALE DB Explorer")
st.caption(
    "Interactive explorer for the "
    "[AnnoTALE](https://github.com/jstacs/annotale) SQLite database."
)

st.image("img/AnnoTALE_transp.png", width=220)
st.markdown(
    """
    Use the sidebar to move through database overview, TALE distributions,
    crosstabs, sample geography, family trees, genome organization,
    and individual TALE detail.
    """
)

st.markdown("---")

st.subheader("Database Snapshot")

def metric_count(loader) -> str:
    try:
        return f"{len(loader()):,}"
    except Exception:  # noqa: BLE001
        return "-"


m1, m2, m3 = st.columns(3)
m1.metric("TALEs", metric_count(load_tales))
m2.metric("Families", metric_count(load_families))
m3.metric("Samples/Strains", metric_count(load_strains))

st.markdown("---")
st.subheader("Pages")

p1, p2 = st.columns(2)
with p1:
    st.markdown(
        """
        **DB Overview**  
        Inspect table counts, schemas, and sample rows.

        **Distributions**  
        Explore TALE lengths, family sizes, RVD composition, and taxonomy comparison.

        **Crosstab**  
        Compare TALE family counts across species/pathovars/strains.

        **Sample Map**  
        View country-level sample distribution and metadata.
        """
    )
with p2:
    st.markdown(
        """
        **TALE Families**  
        Navigate family trees and inspect selected TALE details.

        **Genome Organization**  
        View TALE positions across assemblies and strands for a selected strain.

        **TALE Detail**  
        Inspect one TALE, download sequences, and follow record-level links.
        """
    )
