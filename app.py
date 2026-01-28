import streamlit as st

st.set_page_config(
    page_title="Home",
    layout="wide",
)

st.title("Home")
st.markdown(
    """
    Explore the `annotale.db` SQLite database with interactive views.

    Use the navigation sidebar to move between pages:
    - Overview of tables and schemas
    - Distributions (TALEs, families, RVDs)
    - TALE families
    - Crosstabs (strain/species vs. family)
    """
)
