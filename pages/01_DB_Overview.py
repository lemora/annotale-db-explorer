import streamlit as st

from db_utils import list_tables, query_df, table_counts, table_schema

st.set_page_config(page_title="DB Overview", layout="wide")

st.sidebar.image("img/AnnoTALE_transp.png", width=140)

st.session_state["active_page"] = "DB Overview"
st.title("Database Overview")

counts = table_counts()
tables = counts["table"].tolist()
meta_tables = {"schema_migrations", "data_version", "sqlite_sequence"}

st.subheader("Tables")
filter_text = st.text_input("Filter tables", value="")
show_meta = st.checkbox("Show meta tables", value=False)
visible_tables = [t for t in tables if show_meta or t not in meta_tables]
filtered = [t for t in visible_tables if filter_text.lower() in t.lower()]

cols_per_row = 4
for i in range(0, len(filtered), cols_per_row):
    cols = st.columns(cols_per_row)
    for col, table in zip(cols, filtered[i : i + cols_per_row]):
        row_count = int(counts.loc[counts["table"] == table, "rows"].iloc[0])
        if col.button(f"{table} ({row_count})", use_container_width=True):
            st.session_state["selected_table"] = table

selected = st.session_state.get("selected_table")
if selected not in visible_tables and visible_tables:
    selected = visible_tables[0]

st.subheader("Table Explorer")
table = st.selectbox(
    "Select a table", visible_tables, index=visible_tables.index(selected)
)
st.session_state["selected_table"] = table

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
    limit = st.slider("Sample size", 5, 200, 20, 5)
    sample = query_df(f"SELECT * FROM {table} LIMIT {limit}")
    st.dataframe(sample, use_container_width=True, height=300)
