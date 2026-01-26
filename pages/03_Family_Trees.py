import streamlit as st

from db_utils import load_families, load_tales
from tree_utils import layout_tree, try_parse_newick

st.set_page_config(page_title="Family Trees", layout="wide")

st.title("Family Trees")

families = load_families()
families = families[families["tree_newick"].fillna("").str.strip() != ""]
if families.empty:
    st.warning("No families found.")
    st.stop()

left, right = st.columns([1, 3])

with left:
    family_name = st.selectbox("Family", sorted(families["name"].tolist()))

row = families[families["name"] == family_name].iloc[0]

with left:
    col1, col2 = st.columns(2)
    col1.metric("Members", int(row["member_count"]))
    col2.metric("Family", row["name"])

root = try_parse_newick(row["tree_newick"] or "")
if not root:
    st.warning("Newick tree could not be parsed for this family.")
    st.stop()

nodes_df, edges_df = layout_tree(root)

# Horizontal layout: root left, leaves right
inner_spacing = 38.0
leaf_extension = 120.0
y_spacing = 14.0
max_depth = int(nodes_df["y"].max()) if not nodes_df.empty else 1

nodes_df["x_plot"] = nodes_df["y"] * inner_spacing
nodes_df["y_plot"] = nodes_df["x"] * y_spacing
nodes_df.loc[nodes_df["is_leaf"], "x_plot"] = max_depth * inner_spacing + leaf_extension

# Attach TALE metadata

def to_int(value: str) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if value.isdigit():
        return int(value)
    return None


nodes_df["tale_id"] = nodes_df["name"].apply(to_int)

if not load_tales().empty:
    tales = load_tales()[["id", "name"]].rename(columns={"name": "tale_name"})
    nodes_df = nodes_df.merge(tales, left_on="tale_id", right_on="id", how="left")
else:
    nodes_df["tale_name"] = None

# Selected TALE (persisted)
selected_id = st.session_state.get("selected_tale_id")
selected_name = ""
if selected_id is not None:
    try:
        selected_id = int(selected_id)
    except ValueError:
        selected_id = None
with left:
    st.subheader("Selected TALE")
    if selected_id is not None:
        match = nodes_df[nodes_df["tale_id"] == selected_id]
        if not match.empty:
            selected_name = match.iloc[0]["tale_name"] or ""
        st.write(f"{selected_id} | {selected_name}")
    else:
        st.info("Click a TALE leaf to select it.")

# Build edge points for single-view Vega-Lite (required for selection)
edges_df = edges_df.reset_index().rename(columns={"index": "edge_id"})
edge_points = []
for _, edge in edges_df.iterrows():
    parent = nodes_df.loc[nodes_df["node_id"] == edge["parent_id"]].iloc[0]
    child = nodes_df.loc[nodes_df["node_id"] == edge["child_id"]].iloc[0]
    tooltip_text_parent = None
    if parent["is_leaf"] and parent["tale_id"] is not None:
        tooltip_text_parent = f"{int(parent['tale_id'])}: {parent['tale_name'] or ''}"
    edge_points.append(
        {
            "edge_id": int(edge["edge_id"]),
            "order": 0,
            "x": float(parent["x_plot"]),
            "y": float(parent["y_plot"]),
            "is_leaf": bool(parent["is_leaf"]),
            "tale_id": parent["tale_id"],
            "tale_name": parent["tale_name"] or "",
            "tooltip_text": tooltip_text_parent,
        }
    )
    tooltip_text_child = None
    if child["is_leaf"] and child["tale_id"] is not None:
        tooltip_text_child = f"{int(child['tale_id'])}: {child['tale_name'] or ''}"
    edge_points.append(
        {
            "edge_id": int(edge["edge_id"]),
            "order": 1,
            "x": float(child["x_plot"]),
            "y": float(child["y_plot"]),
            "is_leaf": bool(child["is_leaf"]),
            "tale_id": child["tale_id"],
            "tale_name": child["tale_name"] or "",
            "tooltip_text": tooltip_text_child,
        }
    )

spec = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "width": "container",
    "height": max(520, int(nodes_df["x"].max() * 18)),
    "data": {"values": edge_points},
    "params": [
        {
            "name": "leaf",
            "select": {"type": "point", "on": "click", "fields": ["tale_id"]},
        }
    ],
    "mark": {"type": "line", "point": {"filled": True, "size": 70}},
    "encoding": {
        "x": {"field": "x", "type": "quantitative", "axis": None},
        "y": {"field": "y", "type": "quantitative", "axis": None, "scale": {"reverse": True}},
        "detail": {"field": "edge_id", "type": "nominal"},
        "order": {"field": "order", "type": "quantitative"},
        "color": {
            "condition": [
                {"test": "datum.tale_id != null && datum.tale_id == leaf.tale_id", "value": "#ff7f0e"},
                {"test": "datum.is_leaf === true", "value": "#1f77b4"},
            ],
            "value": "#bdbdbd",
        },
        "tooltip": {"field": "tooltip_text", "type": "nominal", "title": "TALE"},
    },
}

with right:
    try:
        event = st.vega_lite_chart(
            spec, use_container_width=True, theme="streamlit", on_select="rerun"
        )
    except TypeError:
        event = st.vega_lite_chart(spec, use_container_width=True, theme="streamlit")

selected_event_id = None
if isinstance(event, dict):
    def find_tale_id(data):
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "tale_id" and value is not None:
                    return value
                found = find_tale_id(value)
                if found is not None:
                    return found
        elif isinstance(data, list):
            for item in data:
                found = find_tale_id(item)
                if found is not None:
                    return found
        return None

    selected_event_id = find_tale_id(event)

if selected_event_id is not None:
    st.session_state["selected_tale_id"] = int(selected_event_id)
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()
