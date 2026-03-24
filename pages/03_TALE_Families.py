import altair as alt
import html
import streamlit as st
import streamlit.components.v1 as components

from utils.db import (
    load_families,
    load_family_download_rows,
    load_family_members,
    load_family_rvd_counts,
    load_family_species_pathovar,
    load_family_tale_rows,
    load_tale_rvds,
    load_tales,
)
from utils.fasta_export import (
    build_multi_fasta,
    slugify_filename_part,
)
from utils.analytics import track_page_visit
from utils.page import init_page
from utils.theme import PSEUDO_TALE_GREY, SELECTED_ACCENT
from utils.taxonomy import (
    abbreviate_taxon_labels,
    apply_taxon_fallback,
    build_legacy_taxon_map,
)
from utils.tree import layout_tree, try_parse_newick

init_page("TALE Families", "TALE Families", track_analytics=False)
st.title("TALE Families")

INNER_SPACING = 38.0
LEAF_EXTENSION = 120.0
Y_SPACING = 14.0
TREE_MIN_HEIGHT = 520
RVD_CHART_HEIGHT = 300
SELECTED_RVD_HEIGHT = 110
SP_CHART_HEIGHT = 150


def rerun_page() -> None:
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


def chart_key_for_family(family_name: str, selected_tale_id: int | None) -> str:
    family_part = "".join(ch if ch.isalnum() else "_" for ch in family_name)
    tale_part = "none" if selected_tale_id is None else str(int(selected_tale_id))
    return f"family_tree_{family_part}_{tale_part}"


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
    internal_nodes = nodes_df[~nodes_df["is_leaf"]]
    deepest_internal_depth = int(internal_nodes["y"].max()) if not internal_nodes.empty else None
    child_map: dict[int, list[int]] = {}
    node_lookup = nodes_df.set_index("node_id")

    for _, edge in edges_df.iterrows():
        parent_id = int(edge["parent_id"])
        child_id = int(edge["child_id"])
        child_map.setdefault(parent_id, []).append(child_id)

    leaf_depth_cache: dict[int, set[int]] = {}

    def descendant_leaf_depths(node_id: int) -> set[int]:
        if node_id in leaf_depth_cache:
            return leaf_depth_cache[node_id]
        node = node_lookup.loc[node_id]
        if bool(node["is_leaf"]):
            depths = {int(node["y"])}
        else:
            depths = set()
            for child_id in child_map.get(node_id, []):
                depths.update(descendant_leaf_depths(child_id))
        leaf_depth_cache[node_id] = depths
        return depths

    for _, edge in edges_df.iterrows():
        if edge["parent_id"] not in allowed_node_ids or edge["child_id"] not in allowed_node_ids:
            continue
        parent = nodes_df.loc[nodes_df["node_id"] == edge["parent_id"]].iloc[0]
        child = nodes_df.loc[nodes_df["node_id"] == edge["child_id"]].iloc[0]
        parent_leaf_depths = descendant_leaf_depths(int(parent["node_id"]))
        sibling_ids = [
            node_id
            for node_id in child_map.get(int(parent["node_id"]), [])
            if node_id != int(child["node_id"])
        ]
        sibling_anchor_x = (
            max(float(node_lookup.loc[node_id]["x_plot"]) for node_id in sibling_ids)
            if sibling_ids
            else float(parent["x_plot"])
        )
        parent_point = {
            "edge_id": int(edge["edge_id"]),
            "order": 0,
            "x": float(parent["x_plot"]),
            "y": float(parent["y_plot"]),
            "show_point": True,
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
        }
        child_point = {
            "edge_id": int(edge["edge_id"]),
            "order": 1,
            "x": float(child["x_plot"]),
            "y": float(child["y_plot"]),
            "show_point": True,
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
        }

        if (
            child["is_leaf"]
            and deepest_internal_depth is not None
            and int(parent["y"]) < deepest_internal_depth
            and len(parent_leaf_depths) > 1
        ):
            points.extend(
                (
                    parent_point,
                    {
                        "edge_id": int(edge["edge_id"]),
                        "order": 1,
                        "x": sibling_anchor_x,
                        "y": float(child["y_plot"]),
                        "show_point": False,
                        "is_leaf": False,
                        "tale_id": None,
                        "tale_name": "",
                        "tooltip_text": None,
                        "is_selected": False,
                        "is_pseudo": 0,
                    },
                    {
                        **child_point,
                        "order": 2,
                    },
                )
            )
        else:
            points.extend((parent_point, child_point))

    if not points:
        lone = nodes_df.iloc[0]
        points.append(
            {
                "edge_id": 0,
                "order": 0,
                "x": float(lone["x_plot"]),
                "y": float(lone["y_plot"]),
                "show_point": True,
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
      const selectedId = "{selected_id or ''}";
      if (selectedId) {{
        setTimeout(() => {{
          const wrapper = document.getElementById('tale-table-wrapper');
          const row = document.querySelector(`#tale-table tbody tr[data-id='${{selectedId}}']`);
          if (wrapper && row) {{
            const targetTop = row.offsetTop - wrapper.clientHeight / 2 + row.clientHeight / 2;
            wrapper.scrollTop = Math.max(0, targetTop);
          }}
        }}, 50);
      }}
    </script>
    <style>
      :root {{
        color-scheme: light dark;
        --tale-table-bg: #ffffff;
        --tale-table-text: #1f2937;
        --tale-table-border: #e5e7eb;
        --tale-table-header-bg: #f9fafb;
        --tale-table-hover-bg: #fff0e6;
        --tale-table-selected-bg: {SELECTED_ACCENT};
        --tale-table-selected-text: #ffffff;
      }}

      @media (prefers-color-scheme: dark) {{
        :root {{
          --tale-table-bg: #0f172a;
          --tale-table-text: #e5e7eb;
          --tale-table-border: #334155;
          --tale-table-header-bg: #1e293b;
          --tale-table-hover-bg: #2a3446;
        }}
      }}

      body {{ margin: 0; background: transparent; }}
      #tale-table-wrapper {{
        max-height: 300px;
        overflow: auto;
        border: 1px solid var(--tale-table-border);
        background: var(--tale-table-bg);
      }}
      #tale-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        color: var(--tale-table-text);
        background: var(--tale-table-bg);
      }}
      #tale-table th, #tale-table td {{
        padding: 6px 8px;
        border-bottom: 1px solid var(--tale-table-border);
      }}
      #tale-table tr.row.selected {{
        background: var(--tale-table-selected-bg);
        color: var(--tale-table-selected-text);
      }}
      #tale-table tr.row:hover {{ background: var(--tale-table-hover-bg); }}
      #tale-table thead th {{
        position: sticky;
        top: 0;
        background: var(--tale-table-header-bg);
        z-index: 1;
      }}
    </style>
    """
    components.html(table_html, height=320)


def sync_family_url(family_name: str | None, tale_id: int | None) -> None:
    st.query_params.clear()
    if family_name is not None:
        st.query_params["family"] = family_name
    if tale_id is not None:
        st.query_params["tale_id"] = str(int(tale_id))
    track_page_visit()


def queue_selection(family_name: str | None, tale_id: int | None) -> None:
    st.session_state["family_pending_family_control"] = family_name
    st.session_state["family_pending_tale_control"] = tale_id


def normalize_selection(
    requested_family_name: str | None,
    requested_tale_id: int | None,
    fallback_family_name: str,
) -> tuple[str, int | None]:
    if requested_tale_id in tale_to_family:
        resolved_family_name = tale_to_family[int(requested_tale_id)]
        return resolved_family_name, int(requested_tale_id)

    if requested_family_name in family_options:
        resolved_family_name = str(requested_family_name)
    else:
        resolved_family_name = fallback_family_name

    family_tales = family_to_tale_ids.get(resolved_family_name, [])
    if requested_tale_id in family_tales:
        return resolved_family_name, int(requested_tale_id)
    if family_tales:
        return resolved_family_name, int(family_tales[0])
    return resolved_family_name, None


def apply_selection(family_name: str, tale_id: int | None) -> None:
    st.session_state["family_idx"] = family_options.index(family_name)
    st.session_state["selected_tale_id"] = tale_id


def resolve_selection_state(
    family_options: list[str],
    all_tale_options: list[int],
) -> tuple[str, int | None]:
    if "family_idx" not in st.session_state:
        st.session_state["family_idx"] = 0
    st.session_state["family_idx"] = max(
        0, min(st.session_state["family_idx"], len(family_options) - 1)
    )

    fallback_family_name = family_options[st.session_state["family_idx"]]
    pending_family_name = st.session_state.pop("family_pending_family_control", None)
    pending_tale_id = st.session_state.pop("family_pending_tale_control", None)
    if pending_tale_id is not None:
        pending_tale_id = int(pending_tale_id)

    requested_family_name = (
        pending_family_name
        if pending_family_name is not None
        else str(st.query_params.get("family") or "").strip() or None
    )
    requested_tale_id = (
        pending_tale_id
        if pending_tale_id is not None
        else to_int(st.query_params.get("tale_id"))
    )
    if requested_tale_id is None:
        current_selected_id = st.session_state.get("selected_tale_id")
        if current_selected_id in all_tale_options:
            requested_tale_id = int(current_selected_id)

    family_name, tale_id = normalize_selection(
        requested_family_name,
        requested_tale_id,
        fallback_family_name=fallback_family_name,
    )
    apply_selection(family_name, tale_id)
    if (
        str(st.query_params.get("family") or "").strip() != family_name
        or to_int(st.query_params.get("tale_id")) != tale_id
    ):
        sync_family_url(family_name, tale_id)
    return family_name, tale_id


def queue_first_tale_for_family(family_name: str) -> None:
    family_tales = family_to_tale_ids.get(family_name, [])
    target_tale_id = family_tales[0] if family_tales else None
    queue_selection(family_name, target_tale_id)
    sync_family_url(family_name, target_tale_id)


def render_selection_controls(
    current_family_name: str,
    selected_id: int | None,
    all_tale_options: list[int],
    tale_name_by_id: dict[int, str],
    family_options: list[str],
    family_sizes: dict[str, int],
) -> str:
    if all_tale_options:
        selected_tale_index = (
            all_tale_options.index(selected_id) if selected_id in all_tale_options else 0
        )
        selected_tale = st.selectbox(
            "Select a TALE:",
            all_tale_options,
            index=selected_tale_index,
            format_func=lambda tale_id: f"{tale_id}: {tale_name_by_id.get(tale_id, '')}",
        )
        if selected_tale != selected_id:
            target_family_name = tale_to_family.get(int(selected_tale), current_family_name)
            queue_selection(target_family_name, int(selected_tale))
            sync_family_url(target_family_name, int(selected_tale))
            rerun_page()
        selected_detail_tale_id = int(selected_tale)
        if st.button("🔎 Open Selected TALE Detail", use_container_width=True):
            st.session_state["tale_detail_id"] = selected_detail_tale_id
            st.session_state["tale_detail_last_query_id"] = selected_detail_tale_id
            st.query_params["tale_id"] = str(selected_detail_tale_id)
            if hasattr(st, "switch_page"):
                st.switch_page("pages/07_TALE_Detail.py")

    st.markdown("---")

    prev_col, next_col = st.columns(2)
    current_idx = family_options.index(current_family_name)
    if prev_col.button("← Previous Family"):
        new_idx = (current_idx - 1) % len(family_options)
        queue_first_tale_for_family(family_options[new_idx])
        rerun_page()
    if next_col.button("Next Family →"):
        new_idx = (current_idx + 1) % len(family_options)
        queue_first_tale_for_family(family_options[new_idx])
        rerun_page()

    selected_family = st.selectbox(
        "Family",
        family_options,
        index=current_idx,
        format_func=lambda name: f"{name} ({int(family_sizes.get(name, 0))})",
    )
    if current_family_name != selected_family:
        queue_first_tale_for_family(selected_family)
        rerun_page()
    return selected_family


def render_species_pathovar_panel(family_name: str) -> None:
    st.subheader("TALEs by Species + Pathovar")
    sp_raw = load_family_species_pathovar(family_name)
    if sp_raw.empty:
        st.info("No species/pathovar data for this family.")
        return

    legacy_map = build_legacy_taxon_map(
        sp_raw,
        include_pathovar=True,
        legacy_col="legacy_strain_name",
        sample_id_col="sample_id",
    )
    species_pathovar = apply_taxon_fallback(
        sp_raw,
        include_pathovar=True,
        legacy_map=legacy_map,
        id_col="sample_id",
        legacy_col="legacy_strain_name",
    )
    sp_counts = (
        species_pathovar.dropna()
        .value_counts()
        .rename_axis("species_pathovar")
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    sp_counts["species_pathovar"] = abbreviate_taxon_labels(
        sp_counts["species_pathovar"]
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

families = load_families()
families = families[families["tree_newick"].fillna("").str.strip() != ""]
if families.empty:
    st.warning("No families found.")
    st.stop()

family_options = sorted(families["name"].tolist())
family_sizes = dict(zip(families["name"], families["member_count"]))
tales_df = load_tales()

family_members = load_family_members()
family_members = family_members[family_members["family_id"].isin(family_options)].copy()
if not family_members.empty:
    family_members["tale_id"] = family_members["tale_id"].astype(int)
    family_members = family_members.sort_values(["family_id", "tale_id"])

family_to_tale_ids = (
    family_members.groupby("family_id")["tale_id"].apply(list).to_dict()
    if not family_members.empty
    else {}
)
tale_to_family = (
    family_members.drop_duplicates("tale_id").set_index("tale_id")["family_id"].to_dict()
    if not family_members.empty
    else {}
)

if tales_df.empty:
    all_tale_options = []
    tale_name_by_id = {}
else:
    all_tale_rows = tales_df[["id", "name"]].copy()
    all_tale_rows["id"] = all_tale_rows["id"].astype(int)
    if not family_members.empty:
        all_tale_rows = all_tale_rows[all_tale_rows["id"].isin(family_members["tale_id"])]
    all_tale_rows = all_tale_rows.sort_values("id")
    all_tale_options = all_tale_rows["id"].tolist()
    tale_name_by_id = dict(zip(all_tale_rows["id"], all_tale_rows["name"].fillna("")))

current_family_name, selected_id = resolve_selection_state(
    family_options,
    all_tale_options,
)

left, right = st.columns([2, 3])

with left:
    render_selection_controls(
        current_family_name,
        selected_id,
        all_tale_options,
        tale_name_by_id,
        family_options,
        family_sizes,
    )
    family_name = family_options[st.session_state["family_idx"]]
    family_download_rows = load_family_download_rows(family_name)
    family_fasta_payload = build_multi_fasta(family_download_rows, sort_columns=["tale_id"])
    st.download_button(
        "📥 Download Family TALEs as Genomic FASTA",
        data=family_fasta_payload,
        file_name=f"{slugify_filename_part(family_name)}_family_tales_as_genomic_fasta.fasta",
        mime="text/plain",
        disabled=not bool(family_fasta_payload),
        help="Downloads genomic DNA sequences for all TALEs in the selected family.",
        use_container_width=True,
    )

row = families[families["name"] == family_name].iloc[0]
family_tales = family_to_tale_ids.get(family_name, [])

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

if not tales_df.empty:
    tales_df = tales_df[["id", "name", "is_pseudo"]].rename(columns={"name": "tale_name"})
    nodes_df = nodes_df.merge(tales_df, left_on="tale_id", right_on="id", how="left")
else:
    nodes_df["tale_name"] = None
    nodes_df["is_pseudo"] = 0

if selected_id is not None and selected_id not in nodes_df["tale_id"].dropna().tolist():
    selected_id = family_tales[0] if family_tales else None
    queue_selection(family_name, selected_id)
    sync_family_url(family_name, selected_id)
    rerun_page()

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
        else {
            "type": "line",
            "point": {
                "filled": True,
                "size": 70,
                "opacity": {"expr": "datum.show_point ? 1 : 0"},
            },
        }
    ),
    "encoding": {
        "x": {"field": "x", "type": "quantitative", "axis": None},
        "y": {"field": "y", "type": "quantitative", "axis": None, "scale": {"reverse": True}},
        "detail": {"field": "edge_id", "type": "nominal"},
        "order": {"field": "order", "type": "quantitative"},
        "color": {
            "condition": [
                {"test": "datum.is_selected === true", "value": SELECTED_ACCENT},
                {"test": "datum.tale_id != null && datum.tale_id == leaf.tale_id", "value": SELECTED_ACCENT},
                {"test": "datum.is_leaf === true && datum.is_pseudo == 1", "value": PSEUDO_TALE_GREY},
                {"test": "datum.is_leaf === true", "value": "#1f77b4"},
            ],
            "value": "#bdbdbd",
        },
        "tooltip": {
            "condition": {
                "test": "datum.tooltip_text != null && datum.tooltip_text !== ''",
                "field": "tooltip_text",
                "type": "nominal",
                "title": "TALE",
            },
            "value": None,
        },
    },
}

with right:
    st.markdown(
        "<div style='text-align: center; font-size: 0.875rem; opacity: 0.75;'>"
        "Click a node in the tree to select a TALE."
        "</div>",
        unsafe_allow_html=True,
    )
    try:
        event = st.vega_lite_chart(
            spec,
            use_container_width=True,
            theme="streamlit",
            on_select="rerun",
            key=chart_key_for_family(family_name, selected_id),
        )
    except TypeError:
        event = st.vega_lite_chart(
            spec,
            use_container_width=True,
            theme="streamlit",
            key=chart_key_for_family(family_name, selected_id),
        )

selected_event_id = extract_selected_id(event)
if selected_event_id is not None and int(selected_event_id) != selected_id:
    target_family_name = tale_to_family.get(int(selected_event_id), family_name)
    queue_selection(target_family_name, int(selected_event_id))
    sync_family_url(target_family_name, int(selected_event_id))
    rerun_page()

with left:
    st.subheader("Family TALEs")
    tale_rows = load_family_tale_rows(family_name)
    render_tale_table(tale_rows, selected_id)

    render_species_pathovar_panel(family_name)

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

    rvd_pos_all = load_family_rvd_counts(family_name, exclude_pseudo=False)
    rvd_pos_filtered = load_family_rvd_counts(family_name, exclude_pseudo=True)
    if not rvd_pos_all.empty:
        rvd_pos_all["position"] = rvd_pos_all["position"] + 1
    if not rvd_pos_filtered.empty:
        rvd_pos_filtered["position"] = rvd_pos_filtered["position"] + 1
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
            tale_rvds = load_tale_rvds(int(selected_id))
            if tale_rvds.empty:
                st.info("No repeat data for the selected TALE.")
            else:
                tale_rvds["position"] = tale_rvds["position"] + 1
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
