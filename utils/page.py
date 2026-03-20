import streamlit as st
import sqlite3

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
    ("Home", "pages/00_Home.py"),
    ("DB Overview", "pages/01_DB_Overview.py"),
    ("Distributions", "pages/02_Distributions.py"),
    ("Crosstab", "pages/04_Crosstab.py"),
    ("Sample Map", "pages/05_Sample_Map.py"),
    ("TALE Families", "pages/03_TALE_Families.py"),
    ("Genome Organization", "pages/06_Genome_Organization.py"),
    ("TALE Detail", "pages/07_TALE_Detail.py"),
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


def init_page(page_title: str, active_page: str, require_db: bool = True) -> None:
    browser_title = APP_TITLE if page_title == "Home" else f"{APP_TITLE}: {page_title}"
    st.set_page_config(
        page_title=browser_title,
        page_icon="img/AnnoTALE_transp.png",
        layout="wide",
    )
    reason = db_unavailable_reason()
    if reason is not None:
        st.error(reason)
        if require_db:
            st.stop()
    st.sidebar.image("img/AnnoTALE_transp.png", width=140)
    st.sidebar.markdown("### Navigation")
    for label, path in SIDEBAR_PAGES:
        st.sidebar.page_link(
            path,
            label=label,
            disabled=(label == active_page),
            use_container_width=True,
        )
    st.session_state["active_page"] = active_page
