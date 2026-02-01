import streamlit as st

st.set_page_config(
    page_title="Home",
    layout="wide",
)

st.sidebar.image("img/AnnoTALE_transp.png", width=140)

st.session_state["active_page"] = "Home"
left, right = st.columns([3, 1], vertical_alignment="top")
with left:
    st.title("AnnoTALE DB Explorer")
    st.image("img/AnnoTALE_transp.png", width=260)
    st.markdown(
        """
        Explore the latest `annotale.db` database with interactive, schema-aware views.

        **Quick start**
        - Browse tables and schemas in **DB Overview**
        - Inspect distributions (TALE length, RVDs, families) in **Distributions**
        - Explore phylogeny in **TALE Families**
        - Compare taxa and strains in **Crosstab** and **Taxonomy Comparison**
        - Visualize sample geography in **Sample Map**
        """
    )
with right:
    st.empty()
