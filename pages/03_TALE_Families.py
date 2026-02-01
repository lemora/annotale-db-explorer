import altair as alt
import html
import streamlit as st
import streamlit.components.v1 as components

from db_utils import load_families, load_tales, query_df
from tree_utils import layout_tree, try_parse_newick

st.set_page_config(page_title="TALE Families", layout="wide")

st.title("TALE Families")

INNER_SPACING = 38.0
LEAF_EXTENSION = 120.0
Y_SPACING = 14.0
TREE_MIN_HEIGHT = 520
RVD_CHART_HEIGHT = 300
SELECTED_RVD_HEIGHT = 110
SP_CHART_HEIGHT = 150


def to_int(value: str) -> int | None:
    if value is None:
        return None
    value = value.strip()
    return int(value) if value.isdigit() else None


def extract_selected_id(event_payload: dict | None) -> int | None:
    if not isinstance(event_payload, dict):
        return None

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

    selected = find_tale_id(event_payload)
    return int(selected) if selected is not None else None


def build_edge_points(nodes_df, edges_df, selected_id: int | None) -> list[dict]:
    edges_df = edges_df.reset_index().rename(columns={"index": "edge_id"})
    allowed_node_ids = set(nodes_df["node_id"].tolist())
    points: list[dict] = []

    for _, edge in edges_df.iterrows():
        if edge["parent_id"] not in allowed_node_ids or edge["child_id"] not in allowed_node_ids:
            continue
        parent = nodes_df.loc[nodes_df["node_id"] == edge["parent_id"]].iloc[0]
        child = nodes_df.loc[nodes_df["node_id"] == edge["child_id"]].iloc[0]
        points.extend(
            (
                {
                    "edge_id": int(edge["edge_id"]),
                    "order": 0,
                    "x": float(parent["x_plot"]),
                    "y": float(parent["y_plot"]),
                    "is_leaf": bool(parent["is_leaf"]),
                    "tale_id": parent["tale_id"],
                    "tale_name": parent["tale_name"] or "",
                    "tooltip_text": (
                        f"{int(parent['tale_id'])}: {parent['tale_name'] or ''}"
                        if parent["is_leaf"] and parent["tale_id"] is not None
                        else None
                    ),
                    "is_selected": bool(parent["tale_id"] == selected_id),
                    "is_pseudo": int(parent["is_pseudo"])
                    if str(parent["is_pseudo"]) not in ("None", "nan")
                    else 0,
                },
                {
                    "edge_id": int(edge["edge_id"]),
                    "order": 1,
                    "x": float(child["x_plot"]),
                    "y": float(child["y_plot"]),
                    "is_leaf": bool(child["is_leaf"]),
                    "tale_id": child["tale_id"],
                    "tale_name": child["tale_name"] or "",
                    "tooltip_text": (
                        f"{int(child['tale_id'])}: {child['tale_name'] or ''}"
                        if child["is_leaf"] and child["tale_id"] is not None
                        else None
                    ),
                    "is_selected": bool(child["tale_id"] == selected_id),
                    "is_pseudo": int(child["is_pseudo"])
                    if str(child["is_pseudo"]) not in ("None", "nan")
                    else 0,
                },
            )
        )

    if not points:
        lone = nodes_df.iloc[0]
        points.append(
            {
                "edge_id": 0,
                "order": 0,
                "x": float(lone["x_plot"]),
                "y": float(lone["y_plot"]),
                "is_leaf": bool(lone["is_leaf"]),
                "tale_id": lone["tale_id"],
                "tale_name": lone["tale_name"] or "",
                "tooltip_text": (
                    f"{int(lone['tale_id'])}: {lone['tale_name'] or ''}"
                    if lone["is_leaf"] and lone["tale_id"] is not None
                    else None
                ),
                "is_selected": bool(lone["tale_id"] == selected_id),
                "is_pseudo": int(lone["is_pseudo"])
                if str(lone["is_pseudo"]) not in ("None", "nan")
                else 0,
            }
        )

    return points


def render_tale_table(tale_rows, selected_id: int | None) -> None:
    rows_html = []
    for _, row in tale_rows.iterrows():
        rid = int(row["id"])
        rname = html.escape(row["name"] or "")
        selected_class = " selected" if selected_id == rid else ""
        rep_len = row["repeat_len"]
        rep_len_display = f"{int(rep_len)}" if rep_len == rep_len else ""
        rows_html.append(
            f"<tr class='row{selected_class}' data-id='{rid}'>"
            f"<td>{rid}</td><td>{rname}</td><td>{rep_len_display}</td></tr>"
        )

    table_html = f"""
    <div id='tale-table-wrapper'>
      <table id='tale-table'>
        <thead><tr><th>ID</th><th>Name</th><th>Repeat Length</th></tr></thead>
        <tbody>
          {''.join(rows_html)}
        </tbody>
      </table>
    </div>
    <script>
      const rows = document.querySelectorAll('#tale-table tbody tr');
      rows.forEach(r => r.addEventListener('click', () => {{
        const id = r.getAttribute('data-id');
        const url = new URL(window.parent.location.href);
        url.searchParams.set('tale_id', id);
        window.parent.location.href = url.toString();
      }}));
      const selectedId = "{selected_id or ''}";
      if (selectedId) {{
        setTimeout(() => {{
          const el = document.querySelector(`#tale-table tbody tr[data-id='${{selectedId}}']`);
          if (el) {{
            el.scrollIntoView({{block: "center"}});
          }}
        }}, 50);
      }}
    </script>
    <style>
      #tale-table-wrapper {{ max-height: 300px; overflow: auto; border: 1px solid #eee; }}
      #tale-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
      #tale-table th, #tale-table td {{ padding: 6px 8px; border-bottom: 1px solid #f0f0f0; }}
      #tale-table tr.row.selected {{ background: #ff7f0e; color: #fff; }}
      #tale-table tr.row:hover {{ background: #fff0e6; cursor: pointer; }}
      #tale-table thead th {{ position: sticky; top: 0; background: #fafafa; z-index: 1; }}
    </style>
    """
    components.html(table_html, height=320)


families = load_families()
families = families[families["tree_newick"].fillna("").str.strip() != ""]
if families.empty:
    st.warning("No families found.")
    st.stop()

left, right = st.columns([2, 3])

with left:
    family_name = st.selectbox(
        "Family", sorted(families["name"].tolist()), key="family_name"
    )

row = families[families["name"] == family_name].iloc[0]
if st.session_state.get("prev_family") != family_name:
    st.session_state["selected_tale_id"] = None
    st.session_state["prev_family"] = family_name

with left:
    col1, col2 = st.columns(2)
    col1.metric("Members", int(row["member_count"]))
    col2.metric("Family", row["name"])

root = try_parse_newick(row["tree_newick"] or "")
if not root:
    st.warning("Newick tree could not be parsed for this family.")
    st.stop()

nodes_df, edges_df = layout_tree(root)
max_depth = int(nodes_df["y"].max()) if not nodes_df.empty else 1

nodes_df["x_plot"] = nodes_df["y"] * INNER_SPACING
nodes_df["y_plot"] = nodes_df["x"] * Y_SPACING
nodes_df.loc[nodes_df["is_leaf"], "x_plot"] = max_depth * INNER_SPACING + LEAF_EXTENSION

nodes_df["tale_id"] = nodes_df["name"].apply(to_int)

tales_df = load_tales()
if not tales_df.empty:
    tales_df = tales_df[["id", "name", "is_pseudo"]].rename(columns={"name": "tale_name"})
    nodes_df = nodes_df.merge(tales_df, left_on="tale_id", right_on="id", how="left")
else:
    nodes_df["tale_name"] = None
    nodes_df["is_pseudo"] = 0

selected_from_query = st.query_params.get("tale_id")
if selected_from_query:
    try:
        st.session_state["selected_tale_id"] = int(selected_from_query)
    except ValueError:
        pass

selected_id = st.session_state.get("selected_tale_id")
if selected_id is not None:
    try:
        selected_id = int(selected_id)
    except ValueError:
        selected_id = None

if selected_id is not None and selected_id not in nodes_df["tale_id"].dropna().tolist():
    selected_id = None
    st.session_state["selected_tale_id"] = None

edge_points = build_edge_points(nodes_df, edges_df, selected_id)
chart_height = max(TREE_MIN_HEIGHT, int(nodes_df["x"].max() * 18))
single_node = len(edge_points) == 1

spec = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "width": "container",
    "height": chart_height,
    "padding": {"top": 24, "right": 24, "left": 10, "bottom": 10},
    "data": {"values": edge_points},
    "params": [
        {
            "name": "leaf",
            "select": {"type": "point", "on": "click", "fields": ["tale_id"]},
        }
    ],
    "mark": (
        {"type": "point", "filled": True, "size": 90}
        if single_node
        else {"type": "line", "point": {"filled": True, "size": 70}}
    ),
    "encoding": {
        "x": {"field": "x", "type": "quantitative", "axis": None},
        "y": {"field": "y", "type": "quantitative", "axis": None, "scale": {"reverse": True}},
        "detail": {"field": "edge_id", "type": "nominal"},
        "order": {"field": "order", "type": "quantitative"},
        "color": {
            "condition": [
                {"test": "datum.is_selected === true", "value": "#ff7f0e"},
                {"test": "datum.tale_id != null && datum.tale_id == leaf.tale_id", "value": "#ff7f0e"},
                {"test": "datum.is_leaf === true && datum.is_pseudo == 1", "value": "#000000"},
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

selected_event_id = extract_selected_id(event)
if selected_event_id is not None:
    st.session_state["selected_tale_id"] = int(selected_event_id)
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

with left:
    st.subheader("Family TALEs")
    tale_rows = query_df(
        """
        SELECT t.id AS id,
               t.legacy_name AS name,
               t.is_pseudo AS is_pseudo,
               MAX(r.repeat_ordinal) + 1 AS repeat_len
        FROM tale_family_member fm
        JOIN tale t ON t.id = fm.tale_id
        LEFT JOIN repeat r ON r.tale_id = t.id
        WHERE fm.family_id = ?
        GROUP BY t.id, t.legacy_name, t.is_pseudo
        ORDER BY t.id
        """,
        params=[family_name],
    )
    render_tale_table(tale_rows, selected_id)

    st.subheader("TALEs by Species + Pathovar")
    sp_counts = query_df(
        """
        SELECT COALESCE(tx.species, 'Unknown') || ' ' || COALESCE(tx.pathovar, '') AS species_pathovar,
               COUNT(*) AS count
        FROM tale_family_member fm
        JOIN tale t ON t.id = fm.tale_id
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN samples s ON s.id = a.sample_id
        LEFT JOIN taxonomy tx ON tx.id = s.taxon_id
        WHERE fm.family_id = ?
        GROUP BY species_pathovar
        ORDER BY count DESC
        """,
        params=[family_name],
    )
    if sp_counts.empty:
        st.info("No species/pathovar data for this family.")
    else:
        sp_counts["species_pathovar"] = sp_counts["species_pathovar"].str.replace(
            "Xanthomonas", "X.", regex=False
        )
        sp_chart = (
            alt.Chart(sp_counts)
            .mark_bar()
            .encode(
                y=alt.Y(
                    "species_pathovar:N",
                    sort="-x",
                    title="Species + Pathovar",
                    axis=alt.Axis(labelLimit=2000, labelOverlap=False),
                ),
                x=alt.X("count:Q", title="TALE count", axis=alt.Axis(format="d")),
                tooltip=["species_pathovar:N", "count:Q"],
            )
        )
        st.altair_chart(sp_chart.properties(height=SP_CHART_HEIGHT), use_container_width=True)

    st.subheader("RVD Counts by Repeat Position")
    selected_is_pseudo = False
    if selected_id is not None:
        selected_match = nodes_df[nodes_df["tale_id"] == selected_id]
        if not selected_match.empty:
            selected_is_pseudo = int(selected_match.iloc[0]["is_pseudo"] or 0) == 1
    if selected_is_pseudo:
        st.session_state["exclude_pseudo_family_plots"] = False
    exclude_pseudo_plots = st.checkbox(
        "Exclude pseudo TALEs in plot",
        value=False,
        key="exclude_pseudo_family_plots",
        disabled=selected_is_pseudo,
    )

    rvd_pos_all = query_df(
        """
        SELECT r.repeat_ordinal AS position, r.rvd AS rvd, COUNT(*) AS count
        FROM repeat r
        JOIN tale t ON t.id = r.tale_id
        JOIN tale_family_member fm ON fm.tale_id = t.id
        WHERE fm.family_id = ?
        GROUP BY r.repeat_ordinal, r.rvd
        ORDER BY r.repeat_ordinal
        """,
        params=[family_name],
    )
    rvd_pos_filtered = query_df(
        """
        SELECT r.repeat_ordinal AS position, r.rvd AS rvd, COUNT(*) AS count
        FROM repeat r
        JOIN tale t ON t.id = r.tale_id
        JOIN tale_family_member fm ON fm.tale_id = t.id
        WHERE fm.family_id = ? AND t.is_pseudo = 0
        GROUP BY r.repeat_ordinal, r.rvd
        ORDER BY r.repeat_ordinal
        """,
        params=[family_name],
    )
    rvd_pos = rvd_pos_filtered if exclude_pseudo_plots else rvd_pos_all

    if rvd_pos.empty:
        st.info("No repeat data for this family.")
    else:
        pos_domain = sorted(rvd_pos["position"].dropna().unique().tolist())
        rvd_domain_all = sorted(rvd_pos_all["rvd"].dropna().unique().tolist())
        rvd_domain_filtered = sorted(rvd_pos_filtered["rvd"].dropna().unique().tolist())
        rvd_domain = (
            [rvd for rvd in rvd_domain_all if rvd in rvd_domain_filtered]
            if exclude_pseudo_plots
            else rvd_domain_all
        )

        rvd_chart = (
            alt.Chart(rvd_pos)
            .mark_bar()
            .encode(
                x=alt.X(
                    "position:O",
                    title="Repeat position within TALE",
                    sort="ascending",
                    scale=alt.Scale(domain=pos_domain),
                ),
                y=alt.Y("count:Q", title="RVD count", stack="zero"),
                color=alt.Color(
                    "rvd:N",
                    title="RVD",
                    scale=alt.Scale(domain=rvd_domain, scheme="tableau20"),
                ),
                tooltip=["position:Q", "rvd:N", "count:Q"],
            )
        )
        st.altair_chart(rvd_chart.properties(height=RVD_CHART_HEIGHT), use_container_width=True)

        st.subheader("Selected TALE RVDs")
        if selected_id is None:
            st.info("Select a TALE to show its RVD sequence.")
        else:
            tale_rvds = query_df(
                """
                SELECT r.repeat_ordinal AS position, r.rvd AS rvd
                FROM repeat r
                WHERE r.tale_id = ?
                ORDER BY r.repeat_ordinal
                """,
                params=[int(selected_id)],
            )
            if tale_rvds.empty:
                st.info("No repeat data for the selected TALE.")
            else:
                tale_base = alt.Chart(tale_rvds).encode(
                    x=alt.X(
                        "position:O",
                        title="Repeat position",
                        sort="ascending",
                        axis=alt.Axis(labelOverlap=False),
                        scale=alt.Scale(domain=pos_domain),
                    ),
                    tooltip=["position:Q", "rvd:N"],
                )
                tale_bars = tale_base.mark_bar().encode(
                    y=alt.value(0),
                    color=alt.Color(
                        "rvd:N",
                        scale=alt.Scale(domain=rvd_domain, scheme="tableau20"),
                        legend=None,
                    ),
                )
                tale_labels = tale_base.mark_text(
                    dy=-6,
                    size=10,
                    color="#2b2b2b",
                ).encode(
                    y=alt.value(0),
                    text="rvd:N",
                )
                tale_chart = alt.layer(tale_bars, tale_labels)
                st.altair_chart(
                    tale_chart.properties(height=SELECTED_RVD_HEIGHT),
                    use_container_width=True,
                )
