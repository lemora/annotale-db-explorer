import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_plotly_events import plotly_events

from utils.analytics import track_page_visit
from utils.clustering import preferred_strain_label
from utils.page import init_page
from utils.sample_helpers import (
    INVALID_COUNTRY_LABELS,
    UNKNOWN_COUNTRY,
    add_species_pathovar_columns,
    parse_country,
)
from utils.sample_queries import load_sample_map_source, load_sample_taxonomy
from utils.taxonomy import abbreviate_taxon_labels

COUNTRY_CENTROIDS = {
    "Argentina": (-38.4161, -63.6167),
    "Australia": (-25.2744, 133.7751),
    "Belgium": (50.5039, 4.4699),
    "Benin": (9.3077, 2.3158),
    "Brazil": (-14.235, -51.9253),
    "Burkina Faso": (12.2383, -1.5616),
    "Cameroon": (7.3697, 12.3547),
    "Canada": (56.1304, -106.3468),
    "Chile": (-35.6751, -71.543),
    "China": (35.8617, 104.1954),
    "Colombia": (4.5709, -74.2973),
    "France": (46.2276, 2.2137),
    "India": (20.5937, 78.9629),
    "Iran": (32.4279, 53.688),
    "Japan": (36.2048, 138.2529),
    "Kenya": (-0.0236, 37.9062),
    "Madagascar": (-18.7669, 46.8691),
    "Malawi": (-13.2543, 34.3015),
    "Malaysia": (4.2105, 101.9758),
    "Mali": (17.5707, -3.9962),
    "Martinique": (14.6415, -61.0242),
    "Mauritius": (-20.3484, 57.5522),
    "Mexico": (23.6345, -102.5528),
    "Netherlands": (52.1326, 5.2913),
    "New Zealand": (-40.9006, 174.886),
    "Niger": (17.6078, 8.0817),
    "Norway": (60.472, 8.4689),
    "Pakistan": (30.3753, 69.3451),
    "Philippines": (12.8797, 121.774),
    "Puerto Rico": (18.2208, -66.5901),
    "Reunion": (-21.1151, 55.5364),
    "Russia": (61.524, 105.3188),
    "Senegal": (14.4974, -14.4524),
    "Singapore": (1.3521, 103.8198),
    "South Africa": (-30.5595, 22.9375),
    "South Korea": (35.9078, 127.7669),
    "Spain": (40.4637, -3.7492),
    "Sudan": (12.8628, 30.2176),
    "Switzerland": (46.8182, 8.2275),
    "Taiwan": (23.6978, 120.9605),
    "Tanzania": (-6.369, 34.8888),
    "Thailand": (15.87, 100.9925),
    "Tunisia": (33.8869, 9.5375),
    "USA": (37.0902, -95.7129),
    "Uganda": (1.3733, 32.2903),
    "United Kingdom": (55.3781, -3.436),
    "Uruguay": (-32.5228, -55.7658),
}

def sample_option_label(row: pd.Series) -> str:
    strain_display = str(row.get("strain_display") or "Unknown").strip() or "Unknown"
    year = row.get("year")
    year_display = str(int(year)) if pd.notna(year) else "year unknown"
    return f"{strain_display} ({year_display})"


def extract_selected_species_pathovar(event_payload) -> str | None:
    if not isinstance(event_payload, dict):
        return None

    def find_selected(value) -> str | None:
        if isinstance(value, dict):
            direct = value.get("species_pathovar")
            if direct is not None:
                return str(direct)
            for nested in value.values():
                found = find_selected(nested)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = find_selected(item)
                if found is not None:
                    return found
        return None

    return find_selected(event_payload.get("selection", {}))


def to_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return int(cleaned) if cleaned.isdigit() else None


@st.cache_data(show_spinner=False)
def build_sample_map_base() -> pd.DataFrame:
    raw = load_sample_map_source().copy()
    raw["strain_display"] = preferred_strain_label(raw, default="Unknown")
    raw["country"] = raw["geo_tag"].apply(parse_country)
    return raw


@st.cache_data(show_spinner=False)
def build_taxonomy_labels(include_pathovar: bool) -> pd.DataFrame:
    tax_raw = add_species_pathovar_columns(load_sample_taxonomy())
    if not include_pathovar:
        tax_raw["species_pathovar"] = tax_raw["species_display"]
    tax_raw["species_pathovar"] = abbreviate_taxon_labels(tax_raw["species_pathovar"])
    return tax_raw[["sample_id", "species_pathovar"]]


@st.cache_data(show_spinner=False)
def build_taxonomy_filter_rows() -> pd.DataFrame:
    tax_raw = add_species_pathovar_columns(load_sample_taxonomy())
    return tax_raw[["sample_id", "species_display", "pathovar_display"]]


@st.cache_data(show_spinner=False)
def build_country_counts(located: pd.DataFrame) -> pd.DataFrame:
    counts = (
        located.groupby("country")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    counts["lat"] = counts["country"].map(
        lambda country: COUNTRY_CENTROIDS.get(country, (None, None))[0]
    )
    counts["lon"] = counts["country"].map(
        lambda country: COUNTRY_CENTROIDS.get(country, (None, None))[1]
    )
    return counts


@st.cache_data(show_spinner=False)
def filter_source(
    source: pd.DataFrame,
    view_mode: str,
    cutoff_year: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    filtered = source.copy()
    if view_mode == "Cumulative by year":
        if cutoff_year is not None:
            filtered = filtered[
                filtered["year"].notna() & (filtered["year"] <= cutoff_year)
            ]
        else:
            filtered = filtered[filtered["year"].notna()]

    missing_country = filtered[filtered["country"].isna() | (filtered["country"] == "")]
    located = filtered[filtered["country"].notna() & (filtered["country"] != "")]
    located = located[
        ~located["country"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(INVALID_COUNTRY_LABELS)
    ]
    return missing_country, located


@st.cache_data(show_spinner=False)
def build_sample_selection_rows(selected_rows: pd.DataFrame) -> pd.DataFrame:
    tax_rows = build_taxonomy_labels(True)
    merged = selected_rows.merge(tax_rows, on="sample_id", how="left")
    merged["species_pathovar"] = merged["species_pathovar"].fillna("Unknown")
    return merged[
        ["sample_id", "strain_display", "country", "species_pathovar", "year"]
    ].sort_values(["species_pathovar", "strain_display", "sample_id"]).reset_index(
        drop=True
    )


def apply_pending_navigation(previous_page: str | None) -> None:
    pending_country = st.session_state.pop("sample_map_pending_country", None)
    pending_taxon = st.session_state.pop("sample_map_pending_taxon", None)
    pending_sample_id = st.session_state.pop("sample_map_pending_sample_id", None)

    if previous_page != "Sample Map" and pending_country is None:
        st.session_state["selected_country"] = "All"
    if "sample_map_prev_country" not in st.session_state:
        st.session_state["sample_map_prev_country"] = st.session_state.get(
            "selected_country", "All"
        )
    if pending_country is None:
        return

    st.session_state["selected_country"] = pending_country
    st.session_state["sample_map_prev_country"] = pending_country
    st.session_state["sample_map_species_filter"] = "All"
    st.session_state["sample_map_pathovar_filter"] = "All"
    st.session_state["sample_map_view_mode"] = "Static"
    st.session_state["sample_map_prev_view"] = "Static"
    if pending_taxon is not None:
        st.session_state[f"sample_map_species_breakdown_{pending_country}_selected_taxon"] = pending_taxon
        st.session_state[f"sample_map_species_breakdown_{pending_country}_last_chart_taxon"] = pending_taxon
        st.session_state[f"sample_map_taxon_dropdown_{pending_country}"] = pending_taxon
    if pending_sample_id is not None:
        st.session_state[f"sample_map_sample_id_{pending_country}"] = int(pending_sample_id)


def sync_sample_map_url(sample_id: int | None) -> None:
    st.query_params.clear()
    if sample_id is not None:
        st.query_params["sample_id"] = str(int(sample_id))
        st.session_state["sample_map_last_query_sample_id"] = int(sample_id)
    track_page_visit()


def apply_query_sample_selection(raw: pd.DataFrame, selected_sample_id: int | None) -> None:
    if selected_sample_id is None:
        return
    if st.session_state.get("sample_map_last_query_sample_id") == int(selected_sample_id):
        return

    query_match = raw[raw["sample_id"] == int(selected_sample_id)]
    if query_match.empty:
        return

    query_country = query_match.iloc[0].get("country")
    resolved_country = (
        str(query_country)
        if pd.notna(query_country) and str(query_country).strip()
        else UNKNOWN_COUNTRY
    )
    st.session_state["selected_country"] = resolved_country
    st.session_state["sample_map_prev_country"] = resolved_country
    st.session_state[f"sample_map_sample_id_{resolved_country}"] = int(selected_sample_id)
    st.session_state["sample_map_last_query_sample_id"] = int(selected_sample_id)


def reset_country_scoped_state(country: str) -> None:
    prefix = f"sample_map_species_breakdown_{country}"
    st.session_state.pop(f"{prefix}_selected_taxon", None)
    st.session_state.pop(f"{prefix}_last_chart_taxon", None)
    st.session_state.pop(f"sample_map_taxon_dropdown_{country}", None)
    st.session_state.pop(f"sample_map_sample_id_{country}", None)


def render_page_styles() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px;
            border: 1px solid #d9dfd2;
            background:
                radial-gradient(circle at top right, rgba(174, 196, 136, 0.35), transparent 34%),
                linear-gradient(145deg, #f7f4ea 0%, #eef4e6 100%);
        }
        .sample-nav-card {
            padding: 0 0 0.3rem 0;
        }
        .sample-nav-kicker {
            letter-spacing: 0.08em;
            text-transform: uppercase;
            font-size: 0.75rem;
            color: #55624b;
            margin-bottom: 0.35rem;
        }
        .sample-nav-title {
            font-size: 1.2rem;
            line-height: 1.1;
            font-weight: 700;
            color: #182018;
            margin: 0 0 0.35rem 0;
        }
        .sample-nav-text {
            color: #374235;
            margin: 0 0 0.8rem 0;
        }
        @media (prefers-color-scheme: dark) {
            .sample-nav-kicker {
                color: #aac4d8;
            }
            .sample-nav-title {
                color: #eef6fb;
            }
            .sample-nav-text {
                color: #dceaf3;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_taxonomy_filters(
    raw: pd.DataFrame,
    taxonomy_rows: pd.DataFrame,
) -> pd.DataFrame:
    if taxonomy_rows.empty:
        st.info("No taxonomy metadata available; showing all samples.")
        return raw

    st.markdown("**Filter samples by taxonomy.**")
    filtered = raw.copy()
    species_options = ["All"] + sorted(
        taxonomy_rows["species_display"].dropna().unique().tolist()
    )
    selected_species = st.selectbox(
        "Species",
        species_options,
        key="sample_map_species_filter",
    )

    if selected_species == "All":
        st.session_state["sample_map_pathovar_filter"] = "All"
        return filtered

    species_rows = taxonomy_rows[
        taxonomy_rows["species_display"] == selected_species
    ].copy()
    filtered = filtered[filtered["sample_id"].isin(species_rows["sample_id"])]

    pathovar_options = ["All"] + sorted(
        species_rows["pathovar_display"].dropna().unique().tolist()
    )
    if st.session_state.get("sample_map_pathovar_filter") not in pathovar_options:
        st.session_state["sample_map_pathovar_filter"] = "All"

    selected_pathovar = st.selectbox(
        "Pathovar",
        pathovar_options,
        key="sample_map_pathovar_filter",
    )
    if selected_pathovar == "All":
        return filtered

    allowed_ids = species_rows.loc[
        species_rows["pathovar_display"] == selected_pathovar, "sample_id"
    ]
    return filtered[filtered["sample_id"].isin(allowed_ids)]


def resolve_view_mode() -> str:
    view_mode = st.radio(
        "View mode",
        ["Static", "Cumulative by year"],
        horizontal=True,
        key="sample_map_view_mode",
    )
    previous_view_mode = st.session_state.setdefault(
        "sample_map_prev_view",
        view_mode,
    )
    if previous_view_mode != view_mode:
        st.session_state["selected_country"] = "All"
        st.session_state["sample_map_prev_view"] = view_mode
    return view_mode


def resolve_cutoff_year(source: pd.DataFrame, view_mode: str) -> tuple[str, int | None]:
    if view_mode != "Cumulative by year":
        return view_mode, None

    located_mask = source["country"].notna() & (source["country"] != "")
    valid_years = source.loc[located_mask, "year"].dropna().astype(int)
    if valid_years.empty:
        st.info("No usable collection years found; showing static view instead.")
        return "Static", None

    year_options = sorted(valid_years.unique().tolist())
    state_key = "sample_map_cutoff_year"
    current_year = st.session_state.get(state_key, year_options[-1])
    if current_year not in year_options:
        current_year = year_options[-1]

    if len(year_options) == 1:
        cutoff_year = int(year_options[0])
        st.caption(f"Show samples up to year: {cutoff_year}")
    else:
        cutoff_year = st.select_slider(
            "Show samples up to year",
            options=year_options,
            value=current_year,
        )
    st.session_state[state_key] = int(cutoff_year)
    return view_mode, int(cutoff_year)


def render_selection_panels(
    selected_rows: pd.DataFrame,
    selected_country: str,
) -> None:
    if selected_rows.empty:
        st.info("No samples for the selected country and filters.")
        return

    sample_rows = build_sample_selection_rows(selected_rows)
    sp_counts = (
        sample_rows["species_pathovar"]
        .value_counts()
        .rename_axis("species_pathovar")
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    if selected_country == "All":
        country_counts = (
            selected_rows.groupby("country")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        with st.expander("Sample Count By Country", expanded=False):
            st.dataframe(country_counts, use_container_width=True, height=220)

    st.subheader("Species/Pathovar Breakdown")
    selected_species_pathovar = render_species_pathovar_chart(sp_counts, selected_country)
    render_sample_navigation_card(
        sample_rows=sample_rows,
        selected_country=selected_country,
        selected_species_pathovar=selected_species_pathovar,
    )


def render_map(
    mappable: pd.DataFrame,
    selected_country: str,
) -> list[dict]:
    plot_rows = mappable.copy()
    plot_rows["lat"] = plot_rows["lat"].astype(float)
    plot_rows["lon"] = plot_rows["lon"].astype(float)
    plot_rows["count"] = plot_rows["count"].astype(float)
    counts_max = float(plot_rows["count"].max())
    sizes = (plot_rows["count"] / counts_max * 24 + 6).tolist()

    fig = go.Figure()
    fig.add_trace(
        go.Scattergeo(
            lat=plot_rows["lat"].tolist(),
            lon=plot_rows["lon"].tolist(),
            text=plot_rows["country"].tolist(),
            customdata=plot_rows["country"].tolist(),
            mode="markers",
            marker=dict(
                size=sizes,
                color=plot_rows["count"].tolist(),
                colorscale="Turbo",
                showscale=True,
                colorbar=dict(title="Sample count"),
                line=dict(width=0.6, color="#1a1a1a"),
                opacity=0.85,
            ),
            hovertemplate="%{text}<br>Samples: %{marker.color}<extra></extra>",
        )
    )

    selected_marker = plot_rows[plot_rows["country"] == selected_country]
    if not selected_marker.empty:
        fig.add_trace(
            go.Scattergeo(
                lat=selected_marker["lat"].tolist(),
                lon=selected_marker["lon"].tolist(),
                text=selected_marker["country"].tolist(),
                customdata=selected_marker["country"].tolist(),
                mode="markers",
                marker=dict(
                    size=(selected_marker["count"] / counts_max * 24 + 12).tolist(),
                    color="rgba(0,0,0,0)",
                    line=dict(width=3, color="#111111"),
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        geo=dict(
            projection_type="natural earth",
            showland=True,
            landcolor="#f2f2f2",
            showcountries=True,
            countrycolor="#bdbdbd",
        ),
        height=520,
    )
    return plotly_events(
        fig,
        click_event=True,
        hover_event=False,
        select_event=False,
        override_height=520,
        override_width="100%",
    )


def handle_country_selection(
    located: pd.DataFrame,
    missing_country: pd.DataFrame,
    mappable: pd.DataFrame,
) -> tuple[str, pd.DataFrame]:
    selected_country = st.session_state.get("selected_country", "All")

    if not mappable.empty:
        with st.container():
            selected = render_map(mappable, selected_country)
        if selected:
            point_idx = selected[0].get("pointIndex")
            if point_idx is not None and point_idx < len(mappable):
                clicked_country = mappable.iloc[point_idx]["country"]
                if selected_country != clicked_country:
                    st.session_state["selected_country"] = clicked_country
                    st.session_state["sample_map_prev_country"] = clicked_country
                    st.rerun()

    st.subheader("Country Selection")
    country_options = ["All"] + sorted(located["country"].dropna().unique().tolist())
    if not missing_country.empty:
        country_options.append(UNKNOWN_COUNTRY)

    selected_country = st.selectbox(
        "Select a country to inspect samples",
        country_options,
        index=country_options.index(st.session_state.get("selected_country", "All"))
        if st.session_state.get("selected_country", "All") in country_options
        else 0,
    )

    previous_country = st.session_state.get("sample_map_prev_country", "All")
    if selected_country != previous_country:
        st.session_state["selected_country"] = selected_country
        reset_country_scoped_state(previous_country)
        reset_country_scoped_state(selected_country)
        st.session_state["sample_map_prev_country"] = selected_country
        st.rerun()

    if selected_country == UNKNOWN_COUNTRY:
        return selected_country, missing_country
    if selected_country == "All":
        return selected_country, located
    return selected_country, located[located["country"] == selected_country]


def render_species_pathovar_chart(
    sp_counts: pd.DataFrame,
    selected_country: str,
) -> str:
    chart_key = f"sample_map_species_breakdown_{selected_country}"
    state_key = f"{chart_key}_selected_taxon"
    chart_event_key = f"{chart_key}_last_chart_taxon"
    dropdown_key = f"sample_map_taxon_dropdown_{selected_country}"

    selected_species_pathovar = st.session_state.get(
        dropdown_key,
        st.session_state.get(state_key, "All"),
    )
    st.session_state[state_key] = selected_species_pathovar

    chart_data = sp_counts.copy()
    chart_data["is_selected"] = chart_data["species_pathovar"].eq(selected_species_pathovar)
    max_sample_count = int(chart_data["count"].max()) if not chart_data.empty else 0
    x_tick_values = list(range(0, max_sample_count + 1))

    taxon_select = alt.selection_point(
        fields=["species_pathovar"],
        on="click",
        clear=False,
        empty=False,
        name="sample_map_taxon_select",
    )
    chart = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            x=alt.X(
                "count:Q",
                title="Sample count",
                axis=alt.Axis(format="d", values=x_tick_values),
            ),
            y=alt.Y("species_pathovar:N", sort="-x", title="Species + Pathovar"),
            color=alt.condition(
                alt.datum.is_selected,
                alt.value("#0F766E"),
                alt.value("#B8C7C3"),
            ),
            stroke=alt.condition(
                alt.datum.is_selected,
                alt.value("#063B35"),
                alt.value("#7F918C"),
            ),
            strokeWidth=alt.condition(
                alt.datum.is_selected,
                alt.value(2.5),
                alt.value(0.6),
            ),
            opacity=alt.condition(alt.datum.is_selected, alt.value(1.0), alt.value(0.55)),
            tooltip=["species_pathovar:N", "count:Q"],
        )
        .add_params(taxon_select)
    )

    try:
        event = st.vega_lite_chart(
            chart.to_dict(),
            use_container_width=True,
            theme="streamlit",
            on_select="rerun",
            key=chart_key,
        )
        clicked_species_pathovar = extract_selected_species_pathovar(event)
        if clicked_species_pathovar is not None:
            if st.session_state.get(chart_event_key) != clicked_species_pathovar:
                st.session_state[chart_event_key] = clicked_species_pathovar
                st.session_state[state_key] = clicked_species_pathovar
                st.session_state[dropdown_key] = clicked_species_pathovar
                st.rerun()
    except TypeError:
        st.altair_chart(chart.properties(height=300), use_container_width=True)

    return st.session_state.get(
        dropdown_key,
        st.session_state.get(state_key, "All"),
    )


def render_sample_navigation_card(
    sample_rows: pd.DataFrame,
    selected_country: str,
    selected_species_pathovar: str,
) -> None:
    chart_key = f"sample_map_species_breakdown_{selected_country}"
    state_key = f"{chart_key}_selected_taxon"
    chart_event_key = f"{chart_key}_last_chart_taxon"
    dropdown_key = f"sample_map_taxon_dropdown_{selected_country}"

    with st.container(border=True):
        st.markdown(
            """
            <div class="sample-nav-card">
                <div class="sample-nav-kicker">Selection</div>
                <div class="sample-nav-title">Open A Selected Sample</div>
                <div class="sample-nav-text">
                    Choose a species/pathovar scope and then open one of its associated samples in Genome Organization.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        taxon_options = ["All"] + sample_rows["species_pathovar"].drop_duplicates().tolist()
        if selected_species_pathovar not in taxon_options:
            selected_species_pathovar = "All"
        if st.session_state.get(dropdown_key) not in taxon_options:
            st.session_state[dropdown_key] = selected_species_pathovar

        selected_species_pathovar = st.selectbox(
            "Selected species + pathovar",
            taxon_options,
            key=dropdown_key,
        )
        st.session_state[state_key] = selected_species_pathovar
        st.session_state[chart_event_key] = selected_species_pathovar

        visible_samples = sample_rows
        if selected_species_pathovar != "All":
            visible_samples = sample_rows[
                sample_rows["species_pathovar"] == selected_species_pathovar
            ].copy()

        if visible_samples.empty:
            st.info("No samples found for the selected species/pathovar.")
            return

        visible_samples = visible_samples.sort_values(
            ["strain_display", "sample_id"],
            key=lambda column: column.str.casefold()
            if column.name == "strain_display"
            else column,
        )
        sample_options = visible_samples["sample_id"].tolist()
        sample_dropdown_key = f"sample_map_sample_id_{selected_country}"
        if st.session_state.get(sample_dropdown_key) not in sample_options:
            st.session_state[sample_dropdown_key] = sample_options[0]

        selected_sample_id = st.selectbox(
            "Associated samples",
            sample_options,
            key=sample_dropdown_key,
            format_func=lambda sample_id: sample_option_label(
                visible_samples.loc[visible_samples["sample_id"] == sample_id].iloc[0]
            ),
        )
        sync_sample_map_url(int(selected_sample_id))
        button_col1, button_col2 = st.columns(2)
        if button_col1.button(
            "🧾 Open Sample Page",
            key=f"sample_map_open_sample_{selected_country}",
            use_container_width=True,
        ):
                st.session_state["sample_page_pending_sample_id"] = int(selected_sample_id)
                st.query_params.clear()
                st.query_params["sample_id"] = str(int(selected_sample_id))
                if hasattr(st, "switch_page"):
                    st.switch_page("pages/03_Sample.py")
        if button_col2.button(
            "🧬 Open Sample in Genome Organization",
            key=f"sample_map_open_genome_{selected_country}",
            use_container_width=True,
        ):
            st.session_state["genome_org_pending_sample_id"] = int(selected_sample_id)
            st.session_state.pop("genome_org_pending_tale_id", None)
            st.session_state.pop("genome_org_pending_assembly", None)
            st.session_state.pop("genome_org_target_assembly", None)
            st.session_state.pop("genome_org_assemblies", None)
            st.session_state["genome_org_previous_scope"] = None
            if hasattr(st, "switch_page"):
                st.switch_page("pages/04_Genome_Organization.py")


previous_page = st.session_state.get("active_page")
init_page("Sample Map", "Sample Map", track_analytics=False)
apply_pending_navigation(previous_page)

st.title("Sample Locations")
st.caption("Country-level map; dot size indicates sample count.")
render_page_styles()

raw = build_sample_map_base()
if raw.empty:
    st.warning("No sample data available.")
    st.stop()

selected_sample_from_query = to_int(st.query_params.get("sample_id"))
apply_query_sample_selection(raw, selected_sample_from_query)

taxonomy_rows = build_taxonomy_filter_rows()
source = apply_taxonomy_filters(raw, taxonomy_rows)
view_mode = resolve_view_mode()
view_mode, cutoff_year = resolve_cutoff_year(source, view_mode)

missing_country, located = filter_source(source, view_mode, cutoff_year)
counts = build_country_counts(located)
mappable = counts.dropna(subset=["lat", "lon"]).copy()

selected_country, selected_rows = handle_country_selection(
    located=located,
    missing_country=missing_country,
    mappable=mappable,
)
render_selection_panels(selected_rows, selected_country)
