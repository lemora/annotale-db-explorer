import streamlit as st

from db_utils import query_df, table_counts, table_schema

st.set_page_config(page_title="DB Overview", layout="wide")

st.sidebar.image("img/AnnoTALE_transp.png", width=140)

st.session_state["active_page"] = "DB Overview"
st.title("Database Overview")

BUTTON_HIGHLIGHT_CSS = """
<style>
.stButton > button[kind="primary"] {
    background-color: #f28c28;
    border-color: #f28c28;
    color: #ffffff;
}
.stButton > button[kind="primary"]:hover {
    background-color: #e27e1f;
    border-color: #e27e1f;
    color: #ffffff;
}
</style>
"""
st.markdown(BUTTON_HIGHLIGHT_CSS, unsafe_allow_html=True)

counts = table_counts()
tables = counts["table"].tolist()
row_counts = {
    row["table"]: int(row["rows"])
    for _, row in counts[["table", "rows"]].iterrows()
}
meta_tables = {"schema_migrations", "data_version", "sqlite_sequence"}

st.subheader("Tables")
show_meta = st.checkbox("Show meta tables", value=False)
visible_tables = [t for t in tables if show_meta or t not in meta_tables]

if not visible_tables:
    st.info("No tables available with current filters.")
    st.stop()

selected_table = st.session_state.get("selected_table")
if selected_table not in visible_tables:
    selected_table = visible_tables[0]
    st.session_state["selected_table"] = selected_table

cols_per_row = 4
for i in range(0, len(visible_tables), cols_per_row):
    cols = st.columns(cols_per_row)
    for col, table in zip(cols, visible_tables[i : i + cols_per_row]):
        row_count = row_counts.get(table, 0)
        is_selected = selected_table == table
        if col.button(
            f"{table} ({row_count})",
            use_container_width=True,
            type="primary" if is_selected else "secondary",
            key=f"table_btn_{table}",
        ):
            st.session_state["selected_table"] = table
            st.rerun()

st.subheader("Table Explorer")
table = st.session_state.get("selected_table")

schema = table_schema(table)
schema = schema.rename(
    columns={
        "cid": "col_id",
        "name": "column",
        "type": "type",
        "notnull": "not_null",
        "dflt_value": "default",
        "pk": "primary_key",
    }
)

left, right = st.columns([1, 2])
left.metric("Rows", int(counts.loc[counts["table"] == table, "rows"].iloc[0]))
left.metric("Columns", len(schema))

with right:
    st.caption("Schema")
    st.dataframe(schema, use_container_width=True, height=240)

st.caption("Sample rows")
if table == "dmat":
    st.info("Sample rows are hidden for `dmat` because the single entry is very large.")
else:
    show_all_rows = st.checkbox("Show all rows", value=False)
    if show_all_rows:
        sample = query_df(f"SELECT * FROM {table}")
    else:
        limit = st.slider("Sample size", 5, 200, 20, 5)
        sample = query_df(f"SELECT * FROM {table} LIMIT {limit}")
    st.dataframe(sample, use_container_width=True, height=300)
