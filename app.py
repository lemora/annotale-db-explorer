import streamlit as st

pages = [
    st.Page("views/00_Home.py", title="Home", default=True),
    st.Page("views/01_DB_Overview.py", title="DB Overview"),
    st.Page("views/02_Sample_Map.py", title="Sample Map"),
    st.Page("views/03_Sample.py", title="Sample"),
    st.Page("views/04_Genome_Organization.py", title="Genome Organization"),
    st.Page("views/05_TALE_Detail.py", title="TALE Detail"),
    st.Page("views/06_TALE_Families.py", title="TALE Families"),
]

navigation = st.navigation(pages, position="hidden")
navigation.run()
