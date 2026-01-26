import streamlit as st

st.set_page_config(
    page_title="Annotale DB Explorer",
    layout="wide",
)

st.title("Annotale DB Explorer")
st.markdown(
    """
    Explore the `annotale.db` SQLite database with interactive views.

    Use the navigation sidebar to move between pages:
    - Overview of tables and schemas
    - Distributions (TALEs, families, RVDs)
    - Family trees
    - Strain vs. family cross-tabs
    """
)
