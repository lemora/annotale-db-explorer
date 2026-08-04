import streamlit as st

from utils.sample_queries import load_strains
from utils.tale_queries import load_families, load_tales
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
    Use the sidebar to explore the database, map and sample overviews,
    genome organization, TALE details, and families.
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


def page_link(path: str, title: str, description: str) -> None:
    st.page_link(path, label=title)
    st.caption(description)


p1, p2 = st.columns(2)
with p1:
    page_link("views/01_DB_Overview.py", "DB Overview", "Inspect table counts, schemas, and sample rows.")
    page_link("views/02_Sample_Map.py", "Sample Map", "View country-level sample distribution and metadata.")
    page_link("views/03_Sample.py", "Sample", "View a sample overview and links to related records.")
with p2:
    page_link("views/04_Genome_Organization.py", "Genome Organization", "View TALE positions across assemblies and strands for a selected strain.")
    page_link("views/05_TALE_Detail.py", "TALE Detail", "Inspect one TALE, download sequences, and follow record-level links.")
    page_link("views/06_TALE_Families.py", "TALE Families", "Navigate family trees and inspect selected TALE details.")
