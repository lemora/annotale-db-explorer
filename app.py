import streamlit as st

st.set_page_config(
    page_title="Home",
    layout="wide",
)

st.session_state["active_page"] = "Home"
left, right = st.columns([3, 1], vertical_alignment="top")
with left:
    st.title("AnnoTALE DB Explorer")
    st.image("img/AnnoTALE_transp.png", width=260)
    st.markdown(
        """
        Explore the `annotale.db` SQLite database with fast, interactive views for TALE families,
        repeat composition, strain/species distributions, and taxonomy comparisons.

        Use the navigation sidebar to jump between:
        - Overview of tables and schemas
        - Distributions (TALEs, families, RVDs)
        - TALE families and tree inspection
        - Crosstabs (strain/species vs. family)
        - Taxonomy comparison (NCBI vs. legacy)
        - Sample locations and year filters
        """
    )
with right:
    st.empty()
