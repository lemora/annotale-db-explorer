import streamlit as st

pages = [
    st.Page("pages/00_Home.py", title="Home", default=True),
    st.Page("pages/01_DB_Overview.py", title="DB Overview"),
    st.Page("pages/02_Distributions.py", title="Distributions"),
    st.Page("pages/03_TALE_Families.py", title="TALE Families"),
    st.Page("pages/04_Crosstab.py", title="Crosstab"),
    st.Page("pages/05_Sample_Map.py", title="Sample Map"),
    st.Page("pages/06_Genome_Organization.py", title="Genome Organization"),
]

navigation = st.navigation(pages)
navigation.run()
