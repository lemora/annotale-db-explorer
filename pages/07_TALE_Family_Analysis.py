import altair as alt
import pandas as pd
import streamlit as st

from utils.clustering import ENTITY_LEVELS, SET_AGGREGATION_OPTIONS, shared_family_lists
from utils.page import init_page
from utils.tale_family_comparison import (
    build_crosstab_view,
    build_similarity_view,
    extract_selected_cell,
)


PAGE_TITLE = "TALE Family Analysis"
PAGE_KEY = "tale_family_comparison"
CROSSTAB_STRAIN_WINDOW_SIZE = 40


def state_key(name: str) -> str:
    return f"{PAGE_KEY}_{name}"


def render_strain_window_pager(total_row_count: int) -> int:
    window_count = max(
        1,
        (total_row_count + CROSSTAB_STRAIN_WINDOW_SIZE - 1) // CROSSTAB_STRAIN_WINDOW_SIZE,
    )
    page_key = state_key("crosstab_window_page")
    current_page = int(st.session_state.get(page_key, 1))
    current_page = min(max(current_page, 1), window_count)

    input_col, info_col = st.columns([1, 2])
    entered_page = input_col.number_input(
        "Strain window",
        min_value=1,
        max_value=window_count,
        value=current_page,
        step=1,
        key=state_key("crosstab_window_input"),
        help="Shows non-overlapping blocks of strain rows.",
    )
    current_page = int(entered_page)

    current_page = min(max(current_page, 1), window_count)
    st.session_state[page_key] = current_page
    info_col.caption(f"Page {current_page} / {window_count}")
    return current_page - 1


def current_selected_pair(order: list[str], pair_table: pd.DataFrame) -> tuple[str, str]:
    default_left = order[0]
    default_right = order[1]
    if not pair_table.empty:
        default_left = pair_table.iloc[0]["Entity A"]
        default_right = pair_table.iloc[0]["Entity B"]

    selected_cell_y = st.session_state.get(state_key("selected_cell_y"))
    selected_cell_x = st.session_state.get(state_key("selected_cell_x"))
    selected_left = st.session_state.get(state_key("left_entity"))
    selected_right = st.session_state.get(state_key("right_entity"))

    diagonal_selected = (
        selected_cell_x in order
        and selected_cell_y in order
        and selected_cell_x == selected_cell_y
    )
    if diagonal_selected:
        return selected_cell_x, selected_cell_x
    if selected_left in order and selected_right in order and selected_left != selected_right:
        return tuple(sorted((selected_left, selected_right)))
    return default_left, default_right


def mark_selected_heatmap_cells(
    heatmap_df: pd.DataFrame,
    order: list[str],
    selected_pair: tuple[str, str],
) -> pd.DataFrame:
    plot_df = heatmap_df.copy()
    left_entity, right_entity = selected_pair
    selected_cell_y = st.session_state.get(state_key("selected_cell_y"))
    selected_cell_x = st.session_state.get(state_key("selected_cell_x"))
    plot_df["is_selected"] = False

    if selected_cell_x in order and selected_cell_y in order:
        if selected_cell_x == selected_cell_y:
            plot_df["is_selected"] = (
                plot_df["entity_x"].eq(selected_cell_x)
                & plot_df["entity_y"].eq(selected_cell_y)
            )
        else:
            plot_df["is_selected"] = (
                (
                    plot_df["entity_x"].eq(selected_cell_x)
                    & plot_df["entity_y"].eq(selected_cell_y)
                )
                | (
                    plot_df["entity_x"].eq(selected_cell_y)
                    & plot_df["entity_y"].eq(selected_cell_x)
                )
            )
        return plot_df

    plot_df["is_selected"] = (
        (plot_df["entity_x"].eq(left_entity) & plot_df["entity_y"].eq(right_entity))
        | (plot_df["entity_x"].eq(right_entity) & plot_df["entity_y"].eq(left_entity))
    )
    return plot_df


def render_similarity_controls() -> dict[str, object]:
    control_col1, control_col2, control_col3 = st.columns(3)
    entity_level = control_col1.selectbox(
        "Entity level",
        ENTITY_LEVELS,
        index=0,
        key=state_key("entity_level"),
        help="Compare aggregated TALE family sets at species level or species + pathovar level.",
    )
    set_aggregation = control_col2.selectbox(
        "Higher-level set method",
        SET_AGGREGATION_OPTIONS,
        index=1,
        key=state_key("set_aggregation"),
        help="How to turn multiple associated strain-level TALE family sets into one aggregated higher-level set.",
    )
    exclude_pseudo = st.checkbox(
        "Exclude pseudo TALEs",
        value=True,
        key=state_key("exclude_pseudo"),
    )
    include_empty_entities = False
    if set_aggregation != "Union (any strain)":
        include_empty_entities = st.checkbox(
            "Show entities with no retained families",
            value=False,
            key=state_key("include_empty_entities"),
            help="Keep entities visible even if the selected higher-level set method leaves them with zero retained TALE families.",
        )
    include_incomplete_taxa = st.checkbox(
        "Include incomplete taxa",
        value=False,
        key=state_key("include_incomplete_taxa"),
        help=(
            "By default, undefined species such as `X. sp.` are excluded in Species view, "
            "and rows without a defined pathovar are excluded in Species + Pathovar view."
        ),
    )
    style_col1, style_col2 = st.columns(2)
    order_mode = style_col1.radio(
        "Heatmap axis ordering",
        ["Alphabetical", "Hierarchical clustering"],
        index=0,
        horizontal=True,
        key=state_key("order_mode"),
        help="Changes row/column order only.",
    )
    color_scale_mode = style_col2.radio(
        "Heatmap color scaling",
        ["Linear", "Sqrt"],
        index=0,
        horizontal=True,
        key=state_key("color_scale_mode"),
        help="`Linear` uses the raw similarity value. `Sqrt` colors by sqrt(similarity), which spreads lower values apart and increases contrast there.",
    )

    return {
        "entity_level": entity_level,
        "set_aggregation": set_aggregation,
        "order_mode": order_mode,
        "exclude_pseudo": exclude_pseudo,
        "include_empty_entities": include_empty_entities,
        "include_incomplete_taxa": include_incomplete_taxa,
        "color_scale_mode": color_scale_mode,
    }


def render_similarity_heatmap(
    order: list[str],
    heatmap_df: pd.DataFrame,
) -> None:
    pair_select = alt.selection_point(
        fields=["entity_x", "entity_y"],
        on="click",
        clear=False,
        empty=False,
        name=f"{PAGE_KEY}_pair_select",
    )
    chart = (
        alt.Chart(heatmap_df)
        .mark_rect()
        .encode(
            x=alt.X(
                "entity_x:N",
                sort=order,
                title=None,
                axis=alt.Axis(labelAngle=-50, labelLimit=240, labelOverlap=False),
            ),
            y=alt.Y(
                "entity_y:N",
                sort=list(reversed(order)),
                title=None,
                axis=alt.Axis(labelLimit=240, labelOverlap=False),
            ),
            color=alt.Color(
                "color_value:Q",
                title="Similarity color",
                scale=alt.Scale(scheme="blues"),
            ),
            stroke=alt.condition(
                alt.datum.is_selected,
                alt.value("#f97316"),
                alt.value(None),
            ),
            strokeWidth=alt.condition(
                alt.datum.is_selected,
                alt.value(2.5),
                alt.value(0),
            ),
            tooltip=[
                alt.Tooltip("entity_y:N", title="Entity A"),
                alt.Tooltip("entity_x:N", title="Entity B"),
                alt.Tooltip("similarity:Q", title="Jaccard", format=".3f"),
                alt.Tooltip("shared_families:Q", title="Shared families", format=".0f"),
            ],
        )
        .add_params(pair_select)
    )

    chart_height = max(480, 16 * len(order))
    try:
        event = st.vega_lite_chart(
            chart.properties(height=chart_height).to_dict(),
            use_container_width=True,
            theme="streamlit",
            on_select="rerun",
            key=state_key("heatmap"),
        )
        clicked_cell = extract_selected_cell(event)
        if clicked_cell is not None:
            clicked_left, clicked_right = clicked_cell
            previous_selected_y = st.session_state.get(state_key("selected_cell_y"))
            previous_selected_x = st.session_state.get(state_key("selected_cell_x"))
            st.session_state[state_key("selected_cell_y")] = clicked_left
            st.session_state[state_key("selected_cell_x")] = clicked_right
            if clicked_left == clicked_right:
                st.session_state[state_key("left_entity")] = clicked_left
                st.session_state[state_key("right_entity")] = clicked_right
            else:
                normalized_left, normalized_right = tuple(sorted((clicked_left, clicked_right)))
                st.session_state[state_key("left_entity")] = normalized_left
                st.session_state[state_key("right_entity")] = normalized_right
            if previous_selected_y != clicked_left or previous_selected_x != clicked_right:
                st.rerun()
    except TypeError:
        st.altair_chart(chart.properties(height=chart_height), use_container_width=True)


def render_pair_inspector(similarity_view, selected_pair: tuple[str, str]) -> None:
    st.subheader("Pair Inspector")
    alphabetical_entities = sorted(similarity_view.order)
    default_left, default_right = selected_pair

    pair_col1, pair_col2 = st.columns(2)
    with pair_col1:
        left_entity = st.selectbox(
            "Entity A",
            alphabetical_entities,
            index=alphabetical_entities.index(default_left)
            if default_left in alphabetical_entities
            else 0,
            key=state_key("left_select"),
        )
    with pair_col2:
        neighbor_candidates = [label for label in alphabetical_entities if label >= left_entity]
        neighbor_default = default_right if default_right in neighbor_candidates else neighbor_candidates[0]
        right_entity = st.selectbox(
            "Entity B",
            neighbor_candidates,
            index=neighbor_candidates.index(neighbor_default),
            key=state_key("right_select"),
        )

    st.session_state[state_key("left_entity")] = left_entity
    st.session_state[state_key("right_entity")] = right_entity
    if left_entity == right_entity:
        st.info("Selected heatmap cell is a self-comparison, so Entity A and Entity B are the same.")

    shared, left_only, right_only = shared_family_lists(
        similarity_view.presence,
        left_entity=left_entity,
        right_entity=right_entity,
    )
    left_size = int(similarity_view.similarity_result.family_sizes.loc[left_entity])
    right_size = int(similarity_view.similarity_result.family_sizes.loc[right_entity])
    shared_count = int(similarity_view.similarity_result.shared_counts.loc[left_entity, right_entity])
    pair_similarity = float(similarity_view.similarity_result.similarity.loc[left_entity, right_entity])

    stat_col1, stat_col2, stat_col3 = st.columns(3)
    stat_col1.metric("Jaccard", f"{pair_similarity:.3f}")
    stat_col2.metric("Shared families", shared_count)
    stat_col3.metric("Union families", left_size + right_size - shared_count)

    st.markdown(f"**{left_entity}**: {left_size} families")
    st.markdown(f"**{right_entity}**: {right_size} families")

    st.subheader("Pair Overlap Summary")
    pair_summary_df = pd.DataFrame(
        [
            {"segment": f"{left_entity} only", "count": len(left_only), "group": "A only", "color": "#2563eb"},
            {"segment": "Shared", "count": len(shared), "group": "Shared", "color": "#4b5563"},
            {"segment": f"{right_entity} only", "count": len(right_only), "group": "B only", "color": "#059669"},
        ]
    )
    pair_summary_chart = (
        alt.Chart(pair_summary_df)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
        .encode(
            x=alt.X("group:N", title=None, sort=["A only", "Shared", "B only"]),
            y=alt.Y("count:Q", title="Distinct TALE families"),
            color=alt.Color("color:N", scale=None, legend=None),
            tooltip=[
                alt.Tooltip("segment:N", title="Segment"),
                alt.Tooltip("count:Q", title="Family count", format=".0f"),
            ],
        )
    )
    pair_summary_labels = (
        alt.Chart(pair_summary_df)
        .mark_text(dy=-8, fontSize=12, fontWeight="bold")
        .encode(
            x=alt.X("group:N", sort=["A only", "Shared", "B only"]),
            y="count:Q",
            text=alt.Text("count:Q", format=".0f"),
        )
    )
    st.altair_chart((pair_summary_chart + pair_summary_labels).properties(height=260), use_container_width=True)
    st.caption("Overlap is split into left-only, shared, and right-only family counts.")

    list_col1, list_col2, list_col3 = st.columns(3)
    list_col1.markdown("**Shared**")
    list_col1.caption(", ".join(shared) if shared else "None")
    list_col2.markdown("**A only**")
    list_col2.caption(", ".join(left_only) if left_only else "None")
    list_col3.markdown("**B only**")
    list_col3.caption(", ".join(right_only) if right_only else "None")


def render_crosstab_section() -> None:
    st.header("Family Count Crosstab")
    normalize_by_family_size = st.session_state.get(state_key("crosstab_normalize"), False)
    if normalize_by_family_size:
        st.caption(
            "This heatmap shows each cell as the percentage of all TALEs in a family that are assigned "
            "to the selected species, species/pathovar, or strain. Darker cells indicate a larger share of that family."
        )
    else:
        st.caption(
            "This heatmap shows absolute TALE counts per family, grouped by the selected species, "
            "species/pathovar, or strain. Each cell is the number of TALE records assigned to that family "
            "within that grouping; darker cells indicate higher counts."
        )
    control_col1, control_col2 = st.columns([1, 2])
    view = control_col1.selectbox(
        "Entity level",
        ["Species", "Species + Pathovar", "Strain"],
        index=0,
        key=state_key("crosstab_view"),
        help="Chooses the grouping level used to aggregate TALE family counts in the crosstab heatmap.",
    )
    include_incomplete_taxa = False
    if view in {"Species", "Species + Pathovar"}:
        include_incomplete_taxa = st.checkbox(
            "Include incomplete taxa",
            value=False,
            key=state_key("crosstab_incomplete_taxa"),
            help=(
                "By default, undefined species such as `X. sp.` are excluded in Species view, "
                "and rows without a defined pathovar are excluded in Species + Pathovar view."
            ),
        )

    normalize_by_family_size = st.checkbox(
        "Normalize by family size",
        value=False,
        key=state_key("crosstab_normalize"),
        help="Show each cell as the percentage of all TALEs in that family that fall into the given row, instead of absolute counts.",
    )
    axis_order_mode = st.radio(
        "Heatmap axis ordering",
        ["Alphabetical", "Total count"],
        index=1,
        horizontal=True,
        key=state_key("crosstab_axis_order"),
        help="Changes row and family order only.",
    )
    show_all_rows = False
    top_n = 20
    row_window_index = 0

    if view == "Strain":
        st.caption(
            f"Strain crosstabs are shown in fixed windows of {CROSSTAB_STRAIN_WINDOW_SIZE} rows to keep rendering responsive."
        )
    else:
        show_all_rows = view == "Species" or st.checkbox(
            "Show all crosstab rows",
            value=False,
            key=state_key("crosstab_show_all"),
        )
        top_n = st.slider(
            "Show top crosstab rows",
            min_value=5,
            max_value=100,
            value=20,
            step=5,
            disabled=show_all_rows,
            key=state_key("crosstab_top_n"),
        )

    crosstab_view = build_crosstab_view(
        view=view,
        include_incomplete_taxa=include_incomplete_taxa,
        show_all_rows=show_all_rows,
        top_n=top_n,
        row_window_index=row_window_index,
        row_window_size=CROSSTAB_STRAIN_WINDOW_SIZE,
        axis_order_mode=axis_order_mode,
        normalize_by_family_size=normalize_by_family_size,
    )
    if crosstab_view.long_df.empty:
        st.info("No family/strain data available for the current crosstab settings.")
        return

    if view == "Strain":
        row_window_index = render_strain_window_pager(crosstab_view.total_row_count)
        crosstab_view = build_crosstab_view(
            view=view,
            include_incomplete_taxa=include_incomplete_taxa,
            show_all_rows=show_all_rows,
            top_n=top_n,
            row_window_index=row_window_index,
            row_window_size=CROSSTAB_STRAIN_WINDOW_SIZE,
            axis_order_mode=axis_order_mode,
            normalize_by_family_size=normalize_by_family_size,
        )
        start_row = row_window_index * CROSSTAB_STRAIN_WINDOW_SIZE + 1
        end_row = min(crosstab_view.total_row_count, start_row + len(crosstab_view.rows) - 1)
        st.caption(
            f"Showing strains {start_row}-{end_row} of {crosstab_view.total_row_count}."
        )

    chart_height = max(450, 24 * len(crosstab_view.rows))
    value_format = ".1f" if crosstab_view.value_column == "family_percent" else ".0f"
    tooltip = [
        alt.Tooltip("row_label:N", title=crosstab_view.y_title),
        alt.Tooltip("family:N", title="Family"),
    ]
    if "species_pathovar" in crosstab_view.long_df.columns:
        tooltip.append(alt.Tooltip("species_pathovar:N", title="Species + Pathovar"))
    tooltip.append(
        alt.Tooltip(f"{crosstab_view.value_column}:Q", title=crosstab_view.value_title, format=value_format)
    )
    chart = (
        alt.Chart(crosstab_view.long_df)
        .mark_rect()
        .encode(
            x=alt.X(
                "family:N",
                title="Family",
                sort=crosstab_view.families,
                axis=alt.Axis(labelAngle=-45),
            ),
            y=alt.Y(
                "row_label:N",
                title=crosstab_view.y_title,
                sort=crosstab_view.rows,
                axis=alt.Axis(labelLimit=1000, labelOverlap=False),
            ),
            color=alt.condition(
                f"datum.{crosstab_view.value_column} == 0",
                alt.value("#ffffff"),
                alt.Color(
                    f"{crosstab_view.value_column}:Q",
                    title=crosstab_view.value_title,
                    scale=alt.Scale(scheme="blues"),
                ),
            ),
            tooltip=tooltip,
        )
    )
    if normalize_by_family_size:
        st.caption("Normalized view: each cell shows the percentage of all TALEs in that family assigned to the displayed row.")
    st.altair_chart(chart.properties(height=chart_height), use_container_width=True)


init_page(PAGE_TITLE, PAGE_TITLE)
st.title(PAGE_TITLE)
st.caption(
    "This page combines two complementary views: a family-count crosstab showing how many TALEs "
    "from each family are observed per selected grouping, and a Jaccard-based comparison of aggregated "
    "TALE family sets."
)

render_crosstab_section()
st.divider()

st.header("TALE Family Comparison")
st.caption(
    "This heatmap compares aggregated TALE family presence/absence sets between species or species/pathovar groups using Jaccard similarity."
)
controls = render_similarity_controls()
similarity_view = build_similarity_view(**controls)

if similarity_view.presence.empty or len(similarity_view.presence.index) < 2:
    st.info("Not enough entities remain after filtering to compute pairwise similarity.")
    st.stop()

selected_pair = current_selected_pair(similarity_view.order, similarity_view.pair_table)
heatmap_df = mark_selected_heatmap_cells(
    similarity_view.heatmap_df,
    similarity_view.order,
    selected_pair,
)

max_pair_similarity = (
    float(similarity_view.pair_table.iloc[0]["Similarity"])
    if not similarity_view.pair_table.empty
    else 0.0
)
metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
metric_col1.metric("Entities in matrix", len(similarity_view.order))
metric_col2.metric(
    "Median family richness",
    int(similarity_view.meta["family_count"].median()) if not similarity_view.meta.empty else 0,
)
metric_col3.metric(
    "Median TALE count",
    int(similarity_view.meta["tale_count"].median()) if not similarity_view.meta.empty else 0,
)
metric_col4.metric("Top pair Jaccard", f"{max_pair_similarity:.2f}")

render_similarity_heatmap(similarity_view.order, heatmap_df)
st.caption("Click a heatmap cell to populate the pair inspector below.")

with st.expander("Strongest Overlaps", expanded=False):
    if similarity_view.pair_table.empty:
        st.info("No pairwise overlaps available for the current filter set.")
    else:
        display_pairs = similarity_view.pair_table.copy()
        display_pairs["Similarity"] = display_pairs["Similarity"].map(lambda value: round(value, 3))
        display_pairs["A contained in B"] = display_pairs["A contained in B"].map(lambda value: round(value, 3))
        display_pairs["B contained in A"] = display_pairs["B contained in A"].map(lambda value: round(value, 3))
        st.dataframe(display_pairs, use_container_width=True, hide_index=True)

render_pair_inspector(similarity_view, selected_pair)
