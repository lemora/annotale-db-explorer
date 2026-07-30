import streamlit as st

from utils.db_schema import foreign_key_relations, table_counts, table_rows, table_schema
from utils.page import init_page

init_page("DB Overview", "DB Overview")
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


def dot_label(value: str) -> str:
    return value.replace('"', '\\"')


def build_fk_graph_dot(
    tables: list[str],
    relations,
    selected: str | None,
) -> str:
    visible = set(tables)
    lines = [
        "digraph fk_dependencies {",
        "  graph [rankdir=LR, bgcolor=\"transparent\", pad=\"0.05\", nodesep=\"0.25\", ranksep=\"0.45\", margin=\"0\", concentrate=true, ratio=compress];",
        "  node [shape=box, style=\"rounded,filled\", fontname=\"Helvetica\", fontsize=9, margin=\"0.07,0.04\", height=\"0.24\"];",
        "  edge [fontname=\"Helvetica\", fontsize=8, color=\"#6b7280\", arrowsize=0.55];",
    ]
    for table_name in tables:
        fill = "#fff2df" if table_name == selected else "#f8fafc"
        border = "#f28c28" if table_name == selected else "#94a3b8"
        label = table_name
        lines.append(
            f'  "{dot_label(table_name)}" [label="{dot_label(label)}", fillcolor="{fill}", color="{border}"];'
        )
    connected_tables = set(relations["source_table"]).union(relations["target_table"])
    isolated_tables = [table_name for table_name in tables if table_name not in connected_tables]
    if {"dmat", "analysis_config"}.issubset(isolated_tables):
        isolated_tables = [
            "dmat",
            "analysis_config",
            *[
                table_name
                for table_name in isolated_tables
                if table_name not in {"dmat", "analysis_config"}
            ],
        ]
    for source, target in zip(isolated_tables, isolated_tables[1:]):
        lines.append(
            f'  "{dot_label(source)}" -> "{dot_label(target)}" [style=invis, weight=20];'
        )
    for _, relation in relations.iterrows():
        source = relation["source_table"]
        target = relation["target_table"]
        if source not in visible or target not in visible:
            continue
        edge_label = f'{relation["source_column"]} → {relation["target_column"]}'
        lines.append(
            f'  "{dot_label(source)}" -> "{dot_label(target)}" [label="{dot_label(edge_label)}"];'
        )
    lines.append("}")
    return "\n".join(lines)

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

with st.expander("Foreign Key Graph", expanded=False):
    relations = foreign_key_relations()
    visible_relations = relations[
        relations["source_table"].isin(visible_tables)
        & relations["target_table"].isin(visible_tables)
    ]
    if visible_relations.empty:
        st.info("No foreign key relations found for the visible tables.")
    else:
        st.graphviz_chart(
            build_fk_graph_dot(
                visible_tables,
                visible_relations,
                st.session_state.get("selected_table"),
            ),
            width="stretch",
        )

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
        sample = table_rows(table, limit=None)
    else:
        limit = st.slider("Sample size", 5, 200, 20, 5)
        sample = table_rows(table, limit=limit)
    st.dataframe(sample, use_container_width=True, height=300)
