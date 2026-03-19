import altair as alt
import pandas as pd
import streamlit as st
from urllib.parse import quote

from utils.db import load_strain_tales, load_strains, load_tale_detail, query_df
from utils.page import init_page
from utils.taxonomy import apply_taxon_fallback, build_legacy_taxon_map
from utils.theme import SELECTED_ACCENT, blue_card_dark_mode_css

init_page("Genome Organization", "Genome Organization")
st.title("TALE Genomic Organization")
st.caption("TALE positions by replicon and strand, colored by family.")
st.markdown(
    """
    <style>
    .selected-tale-card {
        padding: 1rem 1.1rem;
        border: 1px solid #dfe6d8;
        border-radius: 16px;
        background: linear-gradient(180deg, #fbfbf7 0%, #f3f7ef 100%);
        min-height: 180px;
    }
    .selected-tale-name {
        font-size: 1.2rem;
        font-weight: 700;
        color: #1d2618;
        margin-bottom: 0.3rem;
    }
    .selected-tale-sub {
        color: #5c6658;
        font-size: 0.9rem;
        margin-bottom: 0.8rem;
    }
    .selected-tale-label {
        font-weight: 700;
        color: #283222;
    }
    .selected-tale-line {
        color: #374235;
        margin: 0.28rem 0;
    }
    """
    + blue_card_dark_mode_css(
        card_selector=".selected-tale-card",
        title_selector=".selected-tale-name",
        sub_selector=".selected-tale-sub",
        label_selector=".selected-tale-label",
        text_selector=".selected-tale-line",
    )
    + """
    </style>
    """,
    unsafe_allow_html=True,
)

DEFAULT_SAMPLE_ID = 4
DEFAULT_GAP_THRESHOLD = 100_000
RETAINED_GAP_SIZE = 25_000
BOX_HEIGHT = 18
ESTIMATED_CHART_WIDTH_PX = 1600.0
MIN_BOX_SVG_WIDTH = 14
MAX_BOX_SVG_WIDTH = 2400
LABEL_CHAR_WIDTH = 11
LABEL_WIDTH_PADDING = 6
LABEL_FONT_SCALE = 0.66
LABEL_DOWNSCALE_DELAY_PX = 40
MIN_LABEL_FONT_SIZE = 10.5
MAX_LABEL_FONT_SIZE = 14.5
FAMILY_COLORS = [
    "#4E79A7",
    "#F28E2B",
    "#E15759",
    "#76B7B2",
    "#59A14F",
    "#EDC948",
    "#B07AA1",
    "#FF9DA7",
    "#9C755F",
    "#BAB0AC",
    "#1F77B4",
    "#FF7F0E",
    "#2CA02C",
    "#D62728",
    "#9467BD",
    "#8C564B",
    "#E377C2",
    "#7F7F7F",
    "#BCBD22",
    "#17BECF",
]
UNPLACED_TABLE_COLUMNS = [
    "tale_id",
    "tale_name",
    "family",
    "assembly_label",
    "protein_len",
    "pseudo_label",
]
LABEL_TABLE_COLUMNS = [
    "plot_number",
    "tale_id",
    "tale_name",
    "family_color",
    "family",
    "assembly_label",
    "strand_label",
    "start_pos",
    "end_pos",
    "feature_len",
    "protein_len",
    "pseudo_label",
]


def build_plot_box_svg(
    fill_color: str,
    label: str,
    box_svg_width: int,
    label_font_size: float,
    label_natural_width: int,
    *,
    selected: bool = False,
) -> str:
    inner_label_width = max(1, min(box_svg_width - 4, label_natural_width))
    inner_label_x = max(0, (box_svg_width - inner_label_width) / 2)
    selected_border = (
        f"<rect class='selected-border' x='1' y='1' width='{max(0, box_svg_width - 2)}' "
        f"height='{max(0, BOX_HEIGHT - 2)}' fill='none' "
        "stroke='#111111' stroke-width='2'/>"
        if selected
        else ""
    )
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {box_svg_width} {BOX_HEIGHT}' preserveAspectRatio='none'>"
        "<style>"
        ".selected-border { stroke: #111111; }"
        "@media (prefers-color-scheme: dark) { .selected-border { stroke: #ffffff; } }"
        "</style>"
        f"<rect x='0' y='0' width='{box_svg_width}' height='{BOX_HEIGHT}' fill='{fill_color}'/>"
        f"{selected_border}"
        f"<svg x='{inner_label_x:.2f}' y='0' width='{inner_label_width}' height='{BOX_HEIGHT}' "
        f"viewBox='0 0 {label_natural_width} {BOX_HEIGHT}' preserveAspectRatio='xMidYMid meet'>"
        f"<text x='{label_natural_width / 2}' y='10.1' text-anchor='middle' dominant-baseline='middle' "
        f"font-family='Arial, sans-serif' font-size='{label_font_size:.2f}' font-weight='400' fill='#111111'>{label}</text>"
        "</svg>"
        "</svg>"
    )
    return "data:image/svg+xml;utf8," + quote(svg, safe="")


def add_box_svg_assets(
    assembly_tales: pd.DataFrame,
    assembly_domain: list[float],
    selected_tale_id: int | None,
) -> pd.DataFrame:
    chart_domain_span = max(assembly_domain[1] - assembly_domain[0], 1.0)
    px_per_plot_unit = ESTIMATED_CHART_WIDTH_PX / chart_domain_span

    svg_ready = assembly_tales.copy()
    svg_ready["box_span"] = svg_ready["end_plot"] - svg_ready["start_plot"]
    svg_ready["box_svg_width"] = (
        (svg_ready["box_span"] * px_per_plot_unit)
        .round()
        .clip(lower=MIN_BOX_SVG_WIDTH, upper=MAX_BOX_SVG_WIDTH)
        .astype(int)
    )
    label_lengths = svg_ready["plot_number_label"].str.len().clip(lower=1)
    svg_ready["label_natural_width"] = (label_lengths * LABEL_CHAR_WIDTH) + LABEL_WIDTH_PADDING
    svg_ready["label_font_size"] = (
        ((svg_ready["box_svg_width"] + LABEL_DOWNSCALE_DELAY_PX) / label_lengths)
        * LABEL_FONT_SCALE
    ).clip(lower=MIN_LABEL_FONT_SIZE, upper=MAX_LABEL_FONT_SIZE)
    svg_ready["box_svg"] = svg_ready.apply(
        lambda row: build_plot_box_svg(
            row["family_color"],
            row["plot_number_label"],
            int(row["box_svg_width"]),
            float(row["label_font_size"]),
            int(row["label_natural_width"]),
            selected=selected_tale_id is not None and int(row["tale_id"]) == int(selected_tale_id),
        ),
        axis=1,
    )
    return svg_ready


def to_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return int(cleaned) if cleaned.isdigit() else None


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


def assembly_label_from_parts(assembly_id, accession, replicon_type) -> str:
    accession_text = str(accession or "").strip()
    replicon_text = str(replicon_type or "").strip()
    suffix = (
        f" ({replicon_text})"
        if replicon_text and replicon_text.lower() != "unknown"
        else ""
    )
    if accession_text and accession_text.lower() != "unknown":
        return f"{accession_text}{suffix}"
    return f"assembly {int(assembly_id)}{suffix}"


def sample_option_label(row: pd.Series) -> str:
    strain_name = str(row["strain_name"] or "").strip()
    if not strain_name or strain_name.lower() == "nan":
        strain_name = str(row["legacy_strain_name"] or "").strip()
    if not strain_name or strain_name.lower() == "nan":
        strain_name = "unknown strain"

    biosample_id = str(row["biosample_id"] or "").strip()
    if biosample_id and biosample_id.lower() != "nan":
        return f"{int(row['id'])} | {strain_name} | {biosample_id}"
    return f"{int(row['id'])} | {strain_name} | unknown biosample id"


def sample_ids_with_tales() -> set[int]:
    rows = query_df(
        """
        SELECT DISTINCT a.sample_id AS sample_id
        FROM tale t
        JOIN assembly a ON a.id = t.assembly_id
        WHERE a.sample_id IS NOT NULL
        """
    )
    return set(pd.to_numeric(rows["sample_id"], errors="coerce").dropna().astype(int))


def split_species_pathovar(label: str) -> tuple[str, str]:
    cleaned = str(label or "").strip()
    if not cleaned or cleaned.lower() == "unknown":
        return "Unknown", "Unknown"

    parts = cleaned.split(maxsplit=2)
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1]}", parts[2]
    if len(parts) == 2:
        return cleaned, "Unknown"
    return cleaned, "Unknown"


def load_scope_samples() -> pd.DataFrame:
    strains = load_strains()
    if strains.empty:
        return strains

    legacy_map = build_legacy_taxon_map(
        strains,
        include_pathovar=True,
        legacy_col="legacy_strain_name",
        sample_id_col="id",
    )
    scoped = strains.copy()
    scoped["species_pathovar"] = apply_taxon_fallback(
        scoped,
        include_pathovar=True,
        legacy_map=legacy_map,
        id_col="id",
        legacy_col="legacy_strain_name",
    ).fillna("Unknown")
    scoped = scoped[scoped["id"].isin(sample_ids_with_tales())].copy()

    split_values = scoped["species_pathovar"].apply(split_species_pathovar)
    scoped["species_display"] = split_values.str[0]
    scoped["pathovar_display"] = split_values.str[1]
    return scoped.sort_values(
        ["species_display", "pathovar_display", "id"]
    ).reset_index(drop=True)


def default_scope(scoped_samples: pd.DataFrame) -> tuple[str, str]:
    default_row = scoped_samples[scoped_samples["id"] == DEFAULT_SAMPLE_ID]
    if not default_row.empty:
        row = default_row.iloc[0]
        return row["species_display"], row["pathovar_display"]

    first = scoped_samples.iloc[0]
    return first["species_display"], first["pathovar_display"]


def initialize_widget_state(key: str, options: list[str] | list[int], fallback):
    if st.session_state.get(key) not in options:
        st.session_state[key] = fallback


def rerun_page() -> None:
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


def apply_query_tale_selection(
    scope_samples: pd.DataFrame, selected_tale_id: int | None
) -> None:
    if selected_tale_id is None:
        return
    if st.session_state.get("genome_org_last_query_tale_id") == int(selected_tale_id):
        return

    query_tale_detail = load_tale_detail(int(selected_tale_id))
    if query_tale_detail.empty:
        return

    query_row = query_tale_detail.iloc[0]
    query_sample_id = query_row.get("sample_id")
    if pd.isna(query_sample_id):
        return

    sample_match = scope_samples[scope_samples["id"] == int(query_sample_id)]
    if sample_match.empty:
        return

    sample_row = sample_match.iloc[0]
    st.session_state["genome_org_species"] = sample_row["species_display"]
    st.session_state["genome_org_pathovar"] = sample_row["pathovar_display"]
    st.session_state["genome_org_sample_id"] = int(query_sample_id)
    st.session_state["genome_org_selected_tale_id"] = int(selected_tale_id)
    if st.session_state.get("genome_org_query_select_focus_assembly", True):
        st.session_state["genome_org_target_assembly"] = assembly_label_from_parts(
            query_row.get("assembly_id"),
            query_row.get("accession"),
            query_row.get("replicon_type"),
        )
    st.session_state["genome_org_last_query_tale_id"] = int(selected_tale_id)
    st.session_state["genome_org_query_select_focus_assembly"] = True


def apply_pending_navigation_selection(scope_samples: pd.DataFrame) -> None:
    pending_sample_id = st.session_state.pop("genome_org_pending_sample_id", None)
    pending_tale_id = st.session_state.pop("genome_org_pending_tale_id", None)
    pending_assembly = st.session_state.pop("genome_org_pending_assembly", None)
    if pending_sample_id is None:
        return

    sample_match = scope_samples[scope_samples["id"] == int(pending_sample_id)]
    if sample_match.empty:
        return

    sample_row = sample_match.iloc[0]
    st.session_state["genome_org_species"] = sample_row["species_display"]
    st.session_state["genome_org_pathovar"] = sample_row["pathovar_display"]
    st.session_state["genome_org_sample_id"] = int(pending_sample_id)
    if pending_tale_id is not None:
        st.session_state["genome_org_selected_tale_id"] = int(pending_tale_id)
        st.session_state["genome_org_last_query_tale_id"] = None
    if pending_assembly:
        st.session_state["genome_org_target_assembly"] = pending_assembly


def select_scope_samples(scoped_samples: pd.DataFrame) -> tuple[str, str, pd.DataFrame]:
    default_species, default_pathovar = default_scope(scoped_samples)

    species_options = sorted(scoped_samples["species_display"].unique().tolist())
    initialize_widget_state("genome_org_species", species_options, default_species)
    selected_species = st.selectbox("Species", species_options, key="genome_org_species")

    pathovar_scope = scoped_samples[
        scoped_samples["species_display"] == selected_species
    ].copy()
    pathovar_options = sorted(pathovar_scope["pathovar_display"].unique().tolist())
    default_for_species = (
        default_pathovar if default_pathovar in pathovar_options else pathovar_options[0]
    )
    initialize_widget_state("genome_org_pathovar", pathovar_options, default_for_species)
    selected_pathovar = st.selectbox(
        "Pathovar", pathovar_options, key="genome_org_pathovar"
    )

    selected_scope = scoped_samples[
        (scoped_samples["species_display"] == selected_species)
        & (scoped_samples["pathovar_display"] == selected_pathovar)
    ].copy()
    return selected_species, selected_pathovar, selected_scope.sort_values("id").reset_index(
        drop=True
    )


def select_sample(scope_samples: pd.DataFrame) -> tuple[int, pd.Series]:
    sample_options = scope_samples["id"].tolist()
    fallback = DEFAULT_SAMPLE_ID if DEFAULT_SAMPLE_ID in sample_options else sample_options[0]
    initialize_widget_state("genome_org_sample_id", sample_options, fallback)

    selected_sample_id = st.selectbox(
        "Sample / Strain",
        sample_options,
        key="genome_org_sample_id",
        format_func=lambda sample_id: sample_option_label(
            scope_samples.loc[scope_samples["id"] == sample_id].iloc[0]
        ),
    )
    selected_sample_row = scope_samples.loc[
        scope_samples["id"] == selected_sample_id
    ].iloc[0]
    return int(selected_sample_id), selected_sample_row


def compress_empty_regions(
    tales: pd.DataFrame, min_gap_size: int, retained_gap_size: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    plot_df = tales.copy()
    plot_df["start_plot"] = plot_df["start_pos"]
    plot_df["end_plot"] = plot_df["end_pos"]

    collapsed_rows: list[dict] = []
    for assembly_label in plot_df["assembly_label"].drop_duplicates().tolist():
        assembly_rows = plot_df[plot_df["assembly_label"] == assembly_label]
        intervals = list(
            assembly_rows[["start_pos", "end_pos"]]
            .dropna()
            .sort_values(["start_pos", "end_pos"])
            .itertuples(index=False)
        )
        offset = 0.0
        for previous, current in zip(intervals, intervals[1:]):
            gap_start = float(previous.end_pos)
            gap_end = float(current.start_pos)
            gap_size = gap_end - gap_start
            if gap_size <= min_gap_size:
                continue

            removed_from_axis = gap_size - retained_gap_size
            offset_before = offset
            offset += removed_from_axis
            gap_start_plot = gap_start - offset_before
            gap_end_plot = gap_end - offset
            collapsed_rows.append(
                {
                    "assembly_label": assembly_label,
                    "gap_start": int(gap_start),
                    "gap_end": int(gap_end),
                    "gap_size": int(gap_size),
                    "removed_from_axis": int(removed_from_axis),
                    "offset_before": int(offset_before),
                    "offset_after": int(offset),
                    "gap_start_plot": gap_start_plot,
                    "gap_end_plot": gap_end_plot,
                    "gap_mid_plot": (gap_start_plot + gap_end_plot) / 2.0,
                }
            )

            mask = (
                (plot_df["assembly_label"] == assembly_label)
                & (plot_df["start_pos"] >= current.start_pos)
            )
            plot_df.loc[mask, "start_plot"] = plot_df.loc[mask, "start_pos"] - offset
            plot_df.loc[mask, "end_plot"] = plot_df.loc[mask, "end_pos"] - offset

    return plot_df, pd.DataFrame(collapsed_rows)


def compressed_axis_label_expr(assembly_gaps: pd.DataFrame) -> str:
    if assembly_gaps.empty:
        return "format(datum.value, ',.0f')"

    sorted_gaps = assembly_gaps.sort_values(["gap_start_plot", "gap_end_plot"])
    expr = "datum.value"
    for gap in sorted_gaps.itertuples(index=False):
        gap_start_plot = float(gap.gap_start_plot)
        gap_end_plot = float(gap.gap_end_plot)
        gap_start = float(gap.gap_start)
        gap_size = float(gap.gap_size)
        offset_after = float(gap.offset_after)
        inside_gap_expr = (
            f"({gap_start} + ((datum.value - {gap_start_plot}) * {gap_size} / "
            f"{RETAINED_GAP_SIZE}))"
        )
        expr = (
            f"(datum.value < {gap_start_plot} ? {expr} : "
            f"datum.value <= {gap_end_plot} ? {inside_gap_expr} : "
            f"(datum.value + {offset_after}))"
        )

    return f"format({expr}, ',.0f')"


def prepare_tales(sample_id: int) -> pd.DataFrame:
    tales = load_strain_tales(sample_id).copy()
    tales["family"] = tales["family"].fillna("Unassigned")
    tales["replicon_type"] = tales["replicon_type"].fillna("unknown")
    tales["accession"] = tales["accession"].fillna("unknown")
    tales["assembly_label"] = tales.apply(
        lambda row: assembly_label_from_parts(
            row["assembly_id"], row["accession"], row["replicon_type"]
        ),
        axis=1,
    )
    tales["strand_label"] = tales["strand"].map({1: "+", -1: "-"}).fillna("?")
    tales["lane"] = tales["assembly_label"] + "  strand " + tales["strand_label"]
    tales["feature_len"] = tales["end_pos"] - tales["start_pos"]
    tales["protein_len"] = tales["protein_seq"].fillna("").str.len()
    tales["pseudo_label"] = tales["is_pseudo"].fillna(0).astype(int).map(
        {0: "No", 1: "Yes"}
    )
    return tales


def prepare_plot_tales(
    tales: pd.DataFrame, selected_assemblies: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    filtered = tales[tales["assembly_label"].isin(selected_assemblies)].copy()
    with_coords = filtered[
        filtered["start_pos"].notna()
        & filtered["end_pos"].notna()
        & (filtered["end_pos"] >= filtered["start_pos"])
    ].copy()
    without_coords = filtered.drop(with_coords.index).copy()
    filtered = with_coords
    if filtered.empty:
        return filtered, without_coords

    filtered = filtered.drop_duplicates(subset=["tale_id"]).copy()
    filtered = filtered.sort_values(
        ["assembly_label", "start_pos", "end_pos", "tale_id"]
    ).reset_index(drop=True)
    filtered["plot_number"] = filtered.index + 1
    filtered["plot_number_label"] = filtered["plot_number"].astype(str)
    return filtered, without_coords.drop_duplicates(subset=["tale_id"]).copy()


def initialize_selected_tale_state() -> None:
    if "genome_org_selected_tale_id" not in st.session_state:
        st.session_state["genome_org_selected_tale_id"] = None


def initialize_assembly_filter(available_assemblies: list[str]) -> list[str]:
    target_assembly = st.session_state.pop("genome_org_target_assembly", None)
    current_assemblies = st.session_state.get("genome_org_assemblies")
    if not current_assemblies or not set(current_assemblies).issubset(
        set(available_assemblies)
    ):
        st.session_state["genome_org_assemblies"] = available_assemblies
    if target_assembly in available_assemblies:
        st.session_state["genome_org_assemblies"] = [target_assembly]

    return st.multiselect(
        "Assemblies / replicons",
        available_assemblies,
        key="genome_org_assemblies",
    )


def build_plot_data(
    tales: pd.DataFrame, selected_assemblies: list[str], compress_gaps: bool
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    plot_tales, unplaced_tales = prepare_plot_tales(
        tales,
        selected_assemblies=selected_assemblies,
    )
    if plot_tales.empty:
        return pd.DataFrame(), pd.DataFrame(), unplaced_tales

    if not compress_gaps:
        plot_df = plot_tales.copy()
        plot_df["start_plot"] = plot_df["start_pos"]
        plot_df["end_plot"] = plot_df["end_pos"]
        return plot_df, pd.DataFrame(), unplaced_tales

    plot_df, collapsed_intervals = compress_empty_regions(
        plot_tales,
        min_gap_size=DEFAULT_GAP_THRESHOLD,
        retained_gap_size=RETAINED_GAP_SIZE,
    )
    return plot_df, collapsed_intervals, unplaced_tales


def family_color_map(families: list[str]) -> dict[str, str]:
    return {
        family: FAMILY_COLORS[idx % len(FAMILY_COLORS)]
        for idx, family in enumerate(families)
    }


def render_assembly_chart(
    assembly_tales: pd.DataFrame,
    all_families: list[str],
    colors_by_family: dict[str, str],
    compress_gaps: bool,
    collapsed_intervals: pd.DataFrame,
    selected_tale_id: int | None,
) -> int | None:
    assembly_label = assembly_tales["assembly_label"].iloc[0]
    selection_name = (
        "selected_tale_" + "".join(ch if ch.isalnum() else "_" for ch in assembly_label)
    )
    chart_key = "genome_org_chart_" + "".join(
        ch if ch.isalnum() else "_" for ch in assembly_label
    )
    assembly_gaps = pd.DataFrame()
    if compress_gaps and not collapsed_intervals.empty:
        assembly_gaps = collapsed_intervals[
            collapsed_intervals["assembly_label"] == assembly_label
        ].copy()
    lane_order = []
    strand_labels = assembly_tales["strand_label"].drop_duplicates().tolist()
    for strand_label in ["+", "-", "?"]:
        lane = f"{assembly_label}  strand {strand_label}"
        if strand_label in strand_labels:
            lane_order.append(lane)

    chart_height = max(140, 44 * len(lane_order))
    domain_min = float(assembly_tales["start_plot"].min())
    domain_max = float(assembly_tales["end_plot"].max())
    domain_padding = max(500.0, (domain_max - domain_min) * 0.02)
    domain_start = domain_min - domain_padding
    if not compress_gaps:
        domain_start = max(0.0, domain_start)
    assembly_domain = [domain_start, domain_max + domain_padding]
    st.subheader(assembly_label)
    tale_tooltip = [
        alt.Tooltip("tale_id:Q", title="TALE ID", format=".0f"),
        alt.Tooltip("plot_number:Q", title="plot TALE number", format=".0f"),
        alt.Tooltip("tale_name:N", title="TALE"),
        alt.Tooltip("family:N", title="Family"),
        alt.Tooltip("strand_label:N", title="Strand"),
        alt.Tooltip("start_pos:Q", title="Start", format=",.0f"),
        alt.Tooltip("end_pos:Q", title="End", format=",.0f"),
        alt.Tooltip("feature_len:Q", title="Length (e-s)", format=",.0f"),
        alt.Tooltip("protein_len:Q", title="Protein aa", format=",.0f"),
        alt.Tooltip("pseudo_label:N", title="Pseudo"),
        alt.Tooltip("assembly_label:N", title="Assembly"),
    ]
    x_axis = alt.Axis()
    if compress_gaps:
        x_axis = alt.Axis(labelExpr=compressed_axis_label_expr(assembly_gaps))
    tale_select = alt.selection_point(
        fields=["tale_id"],
        on="click",
        clear=False,
        empty=False,
        name=selection_name,
    )

    assembly_tales = add_box_svg_assets(
        assembly_tales,
        assembly_domain=assembly_domain,
        selected_tale_id=selected_tale_id,
    )

    chart = (
        alt.Chart(assembly_tales)
        .mark_image(aspect=False, height=BOX_HEIGHT)
        .encode(
            x=alt.X(
                "start_plot:Q",
                title=(
                    "Genomic position"
                    if not compress_gaps
                    else "Genomic position (compressed)"
                ),
                scale=alt.Scale(domain=assembly_domain),
                axis=x_axis,
            ),
            x2="end_plot:Q",
            y=alt.Y("lane:N", title=None, sort=lane_order, axis=alt.Axis(labelLimit=500)),
            detail=alt.Detail("tale_id:N"),
            url=alt.Url("box_svg:N"),
            opacity=alt.condition(
                tale_select,
                alt.value(1.0),
                alt.value(0.9),
            ),
            tooltip=tale_tooltip,
        )
        .add_params(tale_select)
    )
    chart_spec = chart.properties(height=chart_height).to_dict()
    try:
        event = st.vega_lite_chart(
            chart_spec,
            use_container_width=True,
            theme="streamlit",
            on_select="rerun",
            key=chart_key,
        )
    except TypeError:
        st.altair_chart(chart.properties(height=chart_height), use_container_width=True)
        return None

    clicked_id = extract_selected_id(event)
    if clicked_id is not None:
        return clicked_id
    return None


def render_selected_tale(selected_row: pd.Series) -> None:
    st.subheader("Selected TALE")
    coordinates = "Not available"
    if pd.notna(selected_row.get("start_pos")) and pd.notna(selected_row.get("end_pos")):
        coordinates = (
            f"{int(selected_row['start_pos']):,} - {int(selected_row['end_pos']):,}"
        )
    genomic_length = "Not available"
    if pd.notna(selected_row.get("feature_len")):
        genomic_length = f"{int(selected_row['feature_len']):,}"
    protein_length = "Not available"
    if pd.notna(selected_row.get("protein_len")):
        protein_length = f"{int(selected_row['protein_len']):,}"

    st.markdown(
        f"""
        <div class="selected-tale-card">
            <div class="selected-tale-name">{selected_row['tale_name']}</div>
            <div class="selected-tale-sub">
                TALE ID {int(selected_row['tale_id'])} • {selected_row['family']} • {selected_row['assembly_label']}
            </div>
            <div class="selected-tale-line"><span class="selected-tale-label">Coordinates:</span> {coordinates}</div>
            <div class="selected-tale-line"><span class="selected-tale-label">Strand:</span> {selected_row['strand_label']}</div>
            <div class="selected-tale-line"><span class="selected-tale-label">Pseudo:</span> {selected_row['pseudo_label']}</div>
            <div class="selected-tale-line"><span class="selected-tale-label">Genomic length:</span> {genomic_length}</div>
            <div class="selected-tale-line"><span class="selected-tale-label">Protein aa:</span> {protein_length}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        "Open TALE Detail",
        key=f"open_family_page_{int(selected_row['tale_id'])}",
        use_container_width=True,
    ):
        selected_id = int(selected_row["tale_id"])
        st.session_state["tale_detail_id"] = selected_id
        st.session_state["tale_detail_last_query_id"] = selected_id
        st.query_params["tale_id"] = str(selected_id)
        if hasattr(st, "switch_page"):
            st.switch_page("pages/07_TALE_Detail.py")


def render_label_table(plot_df: pd.DataFrame) -> None:
    label_table = plot_df[LABEL_TABLE_COLUMNS].rename(
        columns={
            "plot_number": "plot TALE number",
            "tale_id": "id",
            "tale_name": "name",
            "family_color": "family color",
            "strand_label": "strand",
            "start_pos": "start",
            "end_pos": "end",
            "feature_len": "genomic_length (e-s)",
            "protein_len": "protein_length (aa)",
            "pseudo_label": "is_pseudo",
        }
    )
    label_table["family color"] = label_table["family color"].fillna("#cccccc")
    display_table = label_table[
        [
            "plot TALE number",
            "id",
            "name",
            "family",
            "family color",
            "assembly_label",
            "strand",
            "start",
            "end",
            "genomic_length (e-s)",
            "protein_length (aa)",
            "is_pseudo",
        ]
    ].rename(columns={"assembly_label": "assembly"})

    selected_tale_id = st.session_state.get("genome_org_selected_tale_id")

    def highlight_selected_row(row: pd.Series) -> list[str]:
        if selected_tale_id is not None and int(row["id"]) == int(selected_tale_id):
            styles = []
            for column in row.index:
                cell_style = (
                    f"border-top: 1px solid {SELECTED_ACCENT}; border-bottom: 1px solid {SELECTED_ACCENT};"
                )
                if column != "family color":
                    cell_style += f" background-color: {SELECTED_ACCENT}22;"
                styles.append(cell_style)
            return styles
        return ["" for _ in row]

    table_height = min(900, max(160, 35 * (len(display_table) + 1)))
    styler = display_table.style.map(
        lambda value: f"background-color: {value}; color: {value};",
        subset=["family color"],
    )
    styler = styler.apply(highlight_selected_row, axis=1)
    styler = styler.map(
        lambda value: "font-weight: 700;",
        subset=["plot TALE number"],
    )
    styler = styler.hide(axis="index")
    st.dataframe(styler, use_container_width=True, height=table_height)


def render_unplaced_table(unplaced_tales: pd.DataFrame) -> None:
    st.subheader("TALEs Without Genomic Coordinates")
    unplaced = unplaced_tales[UNPLACED_TABLE_COLUMNS].rename(
        columns={
            "tale_id": "id",
            "tale_name": "name",
            "assembly_label": "assembly",
            "protein_len": "protein_length (aa)",
            "pseudo_label": "is_pseudo",
        }
    )
    table_height = min(700, max(140, 35 * (len(unplaced) + 1)))
    st.dataframe(unplaced, use_container_width=True, height=table_height)


def render_selection_summary(
    selected_species: str, selected_pathovar: str, selected_sample_row: pd.Series
) -> None:
    st.markdown(f"**Selected Species:** {selected_species}")
    st.markdown(f"**Selected Pathovar:** {selected_pathovar}")
    st.markdown(f"**Selected Sample / Strain:** {sample_option_label(selected_sample_row)}")


def render_selected_tale_from_rows(rows: pd.DataFrame) -> None:
    selected_tale_id = st.session_state.get("genome_org_selected_tale_id")
    if selected_tale_id is None or rows.empty:
        return

    matching_rows = rows[rows["tale_id"].astype(int) == int(selected_tale_id)]
    if matching_rows.empty:
        return

    st.query_params["tale_id"] = str(int(selected_tale_id))
    render_selected_tale(matching_rows.iloc[0])


def build_selected_tale_rows(tales: pd.DataFrame) -> pd.DataFrame:
    selected_rows = tales.copy()
    if "feature_len" not in selected_rows.columns:
        selected_rows["feature_len"] = selected_rows["end_pos"] - selected_rows["start_pos"]
    if "protein_len" not in selected_rows.columns:
        selected_rows["protein_len"] = selected_rows["protein_seq"].fillna("").str.len()
    if "strand_label" not in selected_rows.columns:
        selected_rows["strand_label"] = selected_rows["strand"].map({1: "+", -1: "-"}).fillna("?")
    if "pseudo_label" not in selected_rows.columns:
        selected_rows["pseudo_label"] = selected_rows["is_pseudo"].fillna(0).astype(int).map(
            {0: "No", 1: "Yes"}
        )
    return selected_rows


def render_plot_section(
    plot_df: pd.DataFrame,
    collapsed_intervals: pd.DataFrame,
    compress_gaps: bool,
    selected_tale_rows: pd.DataFrame,
) -> None:
    families = sorted(plot_df["family"].dropna().unique().tolist())
    colors_by_family = family_color_map(families)
    plot_df["family_color"] = plot_df["family"].map(colors_by_family)

    summary_left, summary_mid, summary_right = st.columns(3)
    summary_left.metric("TALEs", len(plot_df))
    summary_mid.metric("Families", plot_df["family"].nunique())
    summary_right.metric("Assemblies", plot_df["assembly_label"].nunique())

    clicked_tale_id = None
    for assembly_label in plot_df["assembly_label"].drop_duplicates().tolist():
        event_tale_id = render_assembly_chart(
            plot_df[plot_df["assembly_label"] == assembly_label].copy(),
            all_families=families,
            colors_by_family=colors_by_family,
            compress_gaps=compress_gaps,
            collapsed_intervals=collapsed_intervals,
            selected_tale_id=st.session_state.get("genome_org_selected_tale_id"),
        )
        if event_tale_id is not None:
            clicked_tale_id = int(event_tale_id)

    if clicked_tale_id is not None and (
        st.session_state.get("genome_org_selected_tale_id") != clicked_tale_id
    ):
        st.session_state["genome_org_selected_tale_id"] = clicked_tale_id
        st.session_state["genome_org_last_query_tale_id"] = clicked_tale_id
        st.session_state["genome_org_query_select_focus_assembly"] = False
        st.query_params["tale_id"] = str(clicked_tale_id)
        rerun_page()

    st.caption(
        "Each box is one TALE, and the in-box label matches the plot TALE number. "
        "Click a box to select it. "
        "Separate lanes show strand within each assembly/replicon. "
        "Pseudo TALEs are semi-transparent."
    )

    render_selected_tale_from_rows(selected_tale_rows)

    if compress_gaps and not collapsed_intervals.empty:
        st.caption("Dashed lines mark collapsed genome intervals with no TALEs.")
        with st.expander("Collapsed regions", expanded=False):
            table_height = min(320, max(120, 35 * (len(collapsed_intervals) + 1)))
            st.dataframe(
                collapsed_intervals[
                    ["assembly_label", "gap_start", "gap_end", "gap_size", "removed_from_axis"]
                ].rename(
                    columns={
                        "gap_start": "start",
                        "gap_end": "end",
                        "gap_size": "span",
                    }
                ),
                use_container_width=True,
                height=table_height,
            )

    st.subheader("TALE Labels")
    render_label_table(plot_df)


scope_samples = load_scope_samples()
if scope_samples.empty:
    st.warning("No TALE-linked sample metadata available.")
    st.stop()

apply_pending_navigation_selection(scope_samples)
selected_from_query = to_int(st.query_params.get("tale_id"))
apply_query_tale_selection(scope_samples, selected_from_query)

selected_species, selected_pathovar, sample_scope = select_scope_samples(scope_samples)
current_scope = f"{selected_species} | {selected_pathovar}"
st.session_state["genome_org_previous_scope"] = current_scope

selected_sample_id, selected_sample_row = select_sample(sample_scope)
initialize_selected_tale_state()

tales = prepare_tales(int(selected_sample_id))
if tales.empty:
    st.info("No TALEs found for the selected sample.")
    st.stop()

available_assemblies = tales["assembly_label"].drop_duplicates().tolist()
selected_assemblies = initialize_assembly_filter(available_assemblies)
compress_gaps = st.checkbox("Compress empty genome regions", value=True)
render_selection_summary(selected_species, selected_pathovar, selected_sample_row)

plot_df, collapsed_intervals, unplaced_tales = build_plot_data(
    tales,
    selected_assemblies=selected_assemblies,
    compress_gaps=compress_gaps,
)
selected_tale_rows = build_selected_tale_rows(tales)
if plot_df.empty:
    if unplaced_tales.empty:
        st.info("No TALEs match the current filters.")
        st.stop()
    st.info("This sample has TALEs, but none with genomic coordinates for the current filters.")
    render_selected_tale_from_rows(selected_tale_rows)
else:
    render_plot_section(
        plot_df,
        collapsed_intervals,
        compress_gaps,
        selected_tale_rows,
    )

if not unplaced_tales.empty:
    render_unplaced_table(unplaced_tales)
