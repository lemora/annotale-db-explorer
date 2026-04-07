import streamlit as st
import sqlite3

from utils.analytics import track_page_visit
from utils.db import DB_PATH

REQUIRED_TABLES = {
    "tale",
    "samples",
    "repeat",
    "tale_family",
    "tale_family_member",
    "taxonomy",
}

APP_TITLE = "AnnoTALE DB Explorer"

SIDEBAR_PAGES = [
    ("Home", "Home", "pages/00_Home.py"),
    ("DB Overview", "DB Overview", "pages/01_DB_Overview.py"),
    ("Distributions", "Distributions", "pages/02_Distributions.py"),
    ("Sample Map", "Sample Map", "pages/04_Sample_Map.py"),
    ("Genome Organization", "Genome Organization", "pages/05_Genome_Organization.py"),
    ("TALE Detail", "TALE Detail", "pages/06_TALE_Detail.py"),
    ("TALE Families", "TALE Families", "pages/03_TALE_Families.py"),
    ("TALE Family Analysis", "TALE Family Analysis", "pages/07_TALE_Family_Analysis.py"),
]


def db_unavailable_reason() -> str | None:
    if not DB_PATH.exists():
        return f"Database file is missing: `{DB_PATH}`"
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
            ).fetchall()
        available = {row[0] for row in rows}
        missing = sorted(REQUIRED_TABLES - available)
        if missing:
            return (
                f"Database is present but missing required tables in `{DB_PATH}`: "
                f"{', '.join(missing)}"
            )
    except Exception:  # noqa: BLE001
        return f"Could not read SQLite database at `{DB_PATH}`"
    return None


def init_page(
    page_title: str,
    active_page: str,
    require_db: bool = True,
    track_analytics: bool = True,
) -> None:
    browser_title = APP_TITLE if page_title == "Home" else f"{APP_TITLE}: {page_title}"
    st.set_page_config(
        page_title=browser_title,
        page_icon="img/AnnoTALE-db-explorer.png",
        layout="wide",
    )
    reason = db_unavailable_reason()
    if reason is not None:
        st.error(reason)
        if require_db:
            st.stop()
    st.sidebar.image("img/AnnoTALE-db-explorer.png", width=140)
    st.sidebar.markdown("### Navigation")
    for page_id, label, path in SIDEBAR_PAGES:
        st.sidebar.page_link(
            path,
            label=label,
            disabled=(page_id == active_page),
            use_container_width=True,
        )
    st.session_state["active_page"] = active_page
    if track_analytics:
        track_page_visit()
