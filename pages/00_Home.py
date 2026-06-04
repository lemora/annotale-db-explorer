import streamlit as st

from utils.db import load_families, load_strains, load_tales
from utils.page import init_page

REPO_URL = "https://github.com/lemora/annotale-db-explorer"
GITHUB_ICON_URL = (
    "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/github/github-original.svg"
)
HOME_CAPTION_HTML = (
    '<p style="font-size:0.875rem;opacity:0.8;margin:0 0 1rem 0;">'
    'Interactive explorer for the '
    '<a href="https://github.com/jstacs/annotale" target="_blank">AnnoTALE</a> '
    'SQLite database. '
    f'<a href="{REPO_URL}" target="_blank" rel="noopener noreferrer" '
    'aria-label="GitHub repository" title="GitHub repository" '
    'style="display:inline-block;vertical-align:middle;margin-left:0.4rem;">'
    f'<img src="{GITHUB_ICON_URL}" width="18" style="vertical-align:middle;"></a></p>'
)

init_page("Home", "Home", require_db=False)
st.image("img/AnnoTALE_transp.png", width=160)
st.title("AnnoTALE DB Explorer")
st.markdown(HOME_CAPTION_HTML, unsafe_allow_html=True)
st.markdown(
    """
    Use the sidebar to move through database overview, sample geography,
    genome organization, individual TALE detail, family trees and family analysis.
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

        **Sample Map**  
        View country-level sample distribution and metadata.
        """
    )
with p2:
    st.markdown(
        """
        **Genome Organization**  
        View TALE positions across assemblies and strands for a selected strain.

        **TALE Detail**  
        Inspect one TALE, download sequences, and follow record-level links.

        **TALE Families**  
        Navigate family trees and inspect selected TALE details.

        **TALE Family Analysis**  
        Compare TALE family counts across taxa and inspect Jaccard-based family-set similarity.
        """
    )
