import streamlit as st

from db_utils import load_families, load_strains, load_tales

st.set_page_config(page_title="Home", layout="wide")

st.sidebar.image("img/AnnoTALE_transp.png", width=140)

st.session_state["active_page"] = "Home"
st.title("AnnoTALE DB Explorer")
st.caption("Interactive explorer for the local `annotale.db` SQLite database.")

hero_left, hero_right = st.columns([3, 1], vertical_alignment="top")
with hero_left:
    st.image("img/AnnoTALE_transp.png", width=220)
    st.markdown(
        """
        Use the sidebar to move between pages for schema inspection, TALE distributions,
        family trees, crosstabs, and sample geography.
        """
    )
with hero_right:
    st.empty()

st.markdown("---")

st.subheader("Database Snapshot")
try:
    tales = load_tales()
    families = load_families()
    strains = load_strains()
    m1, m2, m3 = st.columns(3)
    m1.metric("TALEs", f"{len(tales):,}")
    m2.metric("Families", f"{len(families):,}")
    m3.metric("Samples/Strains", f"{len(strains):,}")
except Exception as exc:  # noqa: BLE001
    st.warning(f"Could not load database summary: {exc}")

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

        **TALE Families**  
        Navigate family trees and inspect selected TALE details.
        """
    )
with p2:
    st.markdown(
        """
        **Crosstab**  
        Compare TALE family counts across species/pathovars/strains.

        **Sample Map**  
        View country-level sample distribution and metadata.
        """
    )
