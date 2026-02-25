import streamlit as st


def init_page(page_title: str, active_page: str) -> None:
    st.set_page_config(page_title=page_title, layout="wide")
    st.sidebar.image("img/AnnoTALE_transp.png", width=140)
    st.session_state["active_page"] = active_page
