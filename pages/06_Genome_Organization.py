import altair as alt
import pandas as pd
import streamlit as st

from utils.db import load_strain_tales, load_strains, query_df
from utils.page import init_page
from utils.taxonomy import apply_taxon_fallback, build_legacy_taxon_map

init_page("Genome Organization", "Genome Organization")
st.title("TALE Genomic Organization")
st.caption("TALE positions by replicon and strand, colored by family.")

DEFAULT_SAMPLE_ID = 4
DEFAULT_GAP_THRESHOLD = 100_000
RETAINED_GAP_SIZE = 25_000
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
            gap_mid = gap_start + (gap_size / 2.0)
            collapsed_rows.append(
                {
                    "assembly_label": assembly_label,
                    "gap_start": int(gap_start),
                    "gap_end": int(gap_end),
                    "gap_size": int(gap_size),
                    "removed_from_axis": int(removed_from_axis),
                    "gap_mid_plot": gap_mid - offset - (removed_from_axis / 2.0),
                }
            )
            offset += removed_from_axis

            mask = (
                (plot_df["assembly_label"] == assembly_label)
                & (plot_df["start_pos"] >= current.start_pos)
            )
            plot_df.loc[mask, "start_plot"] = plot_df.loc[mask, "start_pos"] - offset
            plot_df.loc[mask, "end_plot"] = plot_df.loc[mask, "end_pos"] - offset

    return plot_df, pd.DataFrame(collapsed_rows)


def prepare_tales(sample_id: int) -> pd.DataFrame:
    tales = load_strain_tales(sample_id).copy()
    tales["family"] = tales["family"].fillna("Unassigned")
    tales["replicon_type"] = tales["replicon_type"].fillna("unknown")
    tales["accession"] = tales["accession"].fillna("unknown")
    def assembly_label(row: pd.Series) -> str:
        replicon_type = str(row["replicon_type"] or "").strip()
        suffix = f" ({replicon_type})" if replicon_type and replicon_type != "unknown" else ""
        if row["accession"] != "unknown":
            return f"{row['accession']}{suffix}"
        return f"assembly {int(row['assembly_id'])}{suffix}"

    tales["assembly_label"] = tales.apply(assembly_label, axis=1)
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
    filtered["number_min_width"] = filtered["plot_number_label"].str.len() * 65
    return filtered, without_coords.drop_duplicates(subset=["tale_id"]).copy()


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
) -> None:
    assembly_label = assembly_tales["assembly_label"].iloc[0]
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
    tale_tooltip = [
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

    st.subheader(assembly_label)

    chart = (
        alt.Chart(assembly_tales)
        .mark_bar(size=18)
        .encode(
            x=alt.X(
                "start_plot:Q",
                title=(
                    "Genomic position"
                    if not compress_gaps
                    else "Genomic position (compressed)"
                ),
                scale=alt.Scale(domain=assembly_domain),
            ),
            x2="end_plot:Q",
            y=alt.Y("lane:N", title=None, sort=lane_order, axis=alt.Axis(labelLimit=500)),
            color=alt.Color(
                "family:N",
                legend=None,
                scale=alt.Scale(
                    domain=all_families,
                    range=[colors_by_family[family] for family in all_families],
                ),
            ),
            opacity=alt.condition(
                "datum.is_pseudo == 1",
                alt.value(0.55),
                alt.value(0.95),
            ),
            tooltip=tale_tooltip,
        )
    )

    labels = (
        alt.Chart(assembly_tales)
        .mark_text(align="center", baseline="middle", fontSize=10, color="#111111")
        .encode(
            x=alt.X("label_pos:Q"),
            y=alt.Y("lane:N", sort=lane_order),
            text="plot_number_label:N",
            tooltip=tale_tooltip,
        )
        .transform_calculate(label_pos="(datum.start_plot + datum.end_plot) / 2")
        .transform_filter("datum.plot_len >= datum.number_min_width")
    )

    layers = [chart]
    if compress_gaps and not collapsed_intervals.empty:
        assembly_gaps = collapsed_intervals[
            collapsed_intervals["assembly_label"] == assembly_label
        ].copy()
        if not assembly_gaps.empty:
            layers.append(
                alt.Chart(assembly_gaps)
                .mark_rule(color="#666666", strokeDash=[4, 4], strokeWidth=1)
                .encode(
                    x=alt.X("gap_mid_plot:Q"),
                    tooltip=[
                        alt.Tooltip("assembly_label:N", title="Assembly"),
                        alt.Tooltip("gap_start:Q", title="Gap start", format=",.0f"),
                        alt.Tooltip("gap_end:Q", title="Gap end", format=",.0f"),
                        alt.Tooltip("gap_size:Q", title="Skipped span", format=",.0f"),
                    ],
                )
            )
    layers.append(labels)

    st.altair_chart(
        alt.layer(*layers).properties(height=chart_height),
        use_container_width=True,
    )


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
            "id",
            "plot TALE number",
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

    table_height = min(900, max(160, 35 * (len(display_table) + 1)))
    styler = display_table.style.map(
        lambda value: f"background-color: {value}; color: {value};",
        subset=["family color"],
    )
    styler = styler.map(
        lambda value: "font-weight: 700;",
        subset=["plot TALE number"],
    )
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


scope_samples = load_scope_samples()
if scope_samples.empty:
    st.warning("No TALE-linked sample metadata available.")
    st.stop()

selected_species, selected_pathovar, sample_scope = select_scope_samples(scope_samples)
current_scope = f"{selected_species} | {selected_pathovar}"
previous_scope = st.session_state.get("genome_org_previous_scope")

if previous_scope != current_scope:
    st.session_state.pop("genome_org_sample_id", None)
st.session_state["genome_org_previous_scope"] = current_scope

selected_sample_id, selected_sample_row = select_sample(sample_scope)

tales = prepare_tales(int(selected_sample_id))
if tales.empty:
    st.info("No TALEs found for the selected sample.")
    st.stop()

available_assemblies = tales["assembly_label"].drop_duplicates().tolist()
selected_assemblies = st.multiselect(
    "Assemblies / replicons",
    available_assemblies,
    default=available_assemblies,
)
compress_gaps = st.checkbox("Compress empty genome regions", value=True)
st.markdown(f"**Selected Species:** {selected_species}")
st.markdown(f"**Selected Pathovar:** {selected_pathovar}")
st.markdown(f"**Selected Sample / Strain:** {sample_option_label(selected_sample_row)}")

plot_tales, unplaced_tales = prepare_plot_tales(
    tales,
    selected_assemblies=selected_assemblies,
)
if plot_tales.empty:
    if unplaced_tales.empty:
        st.info("No TALEs match the current filters.")
        st.stop()
    st.info("This sample has TALEs, but none with genomic coordinates for the current filters.")
    plot_df = pd.DataFrame()
    collapsed_intervals = pd.DataFrame()
else:
    if compress_gaps:
        plot_df, collapsed_intervals = compress_empty_regions(
            plot_tales,
            min_gap_size=DEFAULT_GAP_THRESHOLD,
            retained_gap_size=RETAINED_GAP_SIZE,
        )
    else:
        plot_df = plot_tales.copy()
        plot_df["start_plot"] = plot_df["start_pos"]
        plot_df["end_plot"] = plot_df["end_pos"]
        collapsed_intervals = pd.DataFrame()

if not plot_df.empty:
    plot_df["plot_len"] = plot_df["end_plot"] - plot_df["start_plot"]
    families = sorted(plot_df["family"].dropna().unique().tolist())
    colors_by_family = family_color_map(families)
    plot_df["family_color"] = plot_df["family"].map(colors_by_family)

    summary_left, summary_mid, summary_right = st.columns(3)
    summary_left.metric("TALEs", len(plot_df))
    summary_mid.metric("Families", plot_df["family"].nunique())
    summary_right.metric("Assemblies", plot_df["assembly_label"].nunique())

    for assembly_label in plot_df["assembly_label"].drop_duplicates().tolist():
        render_assembly_chart(
            plot_df[plot_df["assembly_label"] == assembly_label].copy(),
            all_families=families,
            colors_by_family=colors_by_family,
            compress_gaps=compress_gaps,
            collapsed_intervals=collapsed_intervals,
        )

    st.caption(
        "Each bar is one TALE. Numbers inside bars map to the label table below. "
        "Separate lanes show strand within each assembly/replicon. "
        "Pseudo TALEs are semi-transparent."
    )

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

if not unplaced_tales.empty:
    render_unplaced_table(unplaced_tales)
