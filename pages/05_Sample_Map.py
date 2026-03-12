import altair as alt
import plotly.graph_objects as go
import streamlit as st
from streamlit_plotly_events import plotly_events

from utils.db import load_sample_map_source, load_sample_taxonomy
from utils.page import init_page
from utils.taxonomy import (
    abbreviate_taxon_labels,
    apply_taxon_fallback,
    build_legacy_taxon_map,
)

previous_page = st.session_state.get("active_page")
init_page("Sample Map", "Sample Map")

st.title("Sample Locations")
st.caption("Country-level map; dot size indicates sample count.")
if previous_page != "Sample Map":
    st.session_state["selected_country"] = "All"

raw = load_sample_map_source()

if raw.empty:
    st.warning("No sample data available.")
    st.stop()


def parse_country(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if cleaned.lower() in {"-", "unknown", "missing"}:
        return None
    if ":" in cleaned:
        cleaned = cleaned.split(":", 1)[0].strip()
    if "," in cleaned:
        cleaned = cleaned.split(",", 1)[0].strip()
    if cleaned.lower() in {"-", "unknown", "missing"}:
        return None
    return cleaned


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

raw["strain_display"] = raw["strain_name"].fillna(raw["legacy_strain_name"]).fillna(
    "Unknown"
)
raw["country"] = raw["geo_tag"].apply(parse_country)

tax_filter = st.radio(
    "Filter by taxonomy",
    ["All", "Species", "Species + Pathovar"],
    horizontal=True,
    key="sample_map_tax_filter",
)
source = raw.copy()
if tax_filter != "All":
    tax_raw = load_sample_taxonomy()
    if tax_raw.empty:
        st.info("No taxonomy metadata available; showing all samples.")
    else:
        include_pathovar = tax_filter == "Species + Pathovar"
        legacy_map = build_legacy_taxon_map(
            tax_raw,
            include_pathovar=include_pathovar,
            legacy_col="legacy_strain_name",
            sample_id_col="sample_id",
        )
        tax_raw["species_pathovar"] = apply_taxon_fallback(
            tax_raw,
            include_pathovar=include_pathovar,
            legacy_map=legacy_map,
            id_col="sample_id",
            legacy_col="legacy_strain_name",
        )
        tax_raw["species_pathovar"] = abbreviate_taxon_labels(
            tax_raw["species_pathovar"]
        )
        taxon_options = ["All"] + sorted(
            tax_raw["species_pathovar"].dropna().unique().tolist()
        )
        selected_taxon = st.selectbox(
            tax_filter, taxon_options, key="sample_map_taxon"
        )
        if selected_taxon != "All":
            allowed_ids = set(
                tax_raw.loc[
                    tax_raw["species_pathovar"] == selected_taxon, "sample_id"
                ].tolist()
            )
            source = source[source["sample_id"].isin(allowed_ids)]

located_mask = source["country"].notna() & (source["country"] != "")

view_mode = st.radio(
    "View mode",
    ["Static", "Cumulative by year"],
    horizontal=True,
    key="sample_map_view_mode",
)
if "sample_map_prev_view" not in st.session_state:
    st.session_state["sample_map_prev_view"] = view_mode
elif st.session_state["sample_map_prev_view"] != view_mode:
    st.session_state["selected_country"] = "All"
    st.session_state["sample_map_prev_view"] = view_mode

map_placeholder = st.container()
cutoff_year = None
if view_mode == "Cumulative by year":
    valid_years = source.loc[located_mask, "year"].dropna().astype(int)
    if valid_years.empty:
        st.info("No usable collection years found; showing static view instead.")
        view_mode = "Static"
    else:
        cutoff_year = st.slider(
            "Show samples up to year",
            min_value=int(valid_years.min()),
            max_value=int(valid_years.max()),
            value=int(valid_years.max()),
        )

filtered = source.copy()
if view_mode == "Cumulative by year":
    if cutoff_year is not None:
        filtered = filtered[filtered["year"].notna() & (filtered["year"] <= cutoff_year)]
    else:
        filtered = filtered[filtered["year"].notna()]

missing_country = filtered[filtered["country"].isna() | (filtered["country"] == "")]
located = filtered[filtered["country"].notna() & (filtered["country"] != "")]
located = located[
    ~located["country"]
    .astype(str)
    .str.strip()
    .str.lower()
    .isin({"unknown", "missing", "-"})
]

counts = (
    located.groupby("country")
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)
counts["lat"] = counts["country"].map(
    lambda c: COUNTRY_CENTROIDS.get(c, (None, None))[0]
)
counts["lon"] = counts["country"].map(
    lambda c: COUNTRY_CENTROIDS.get(c, (None, None))[1]
)

mappable = counts.dropna(subset=["lat", "lon"]).copy()
selected_country = "All"

if mappable.empty:
    st.info("No mappable locations found for the current filters.")
    selected_rows = located
else:
    mappable["lat"] = mappable["lat"].astype(float)
    mappable["lon"] = mappable["lon"].astype(float)
    mappable["count"] = mappable["count"].astype(float)
    counts_max = float(mappable["count"].max())
    sizes = (mappable["count"] / counts_max * 24 + 6).tolist()
    fig = go.Figure(
        data=go.Scattergeo(
            lat=mappable["lat"].tolist(),
            lon=mappable["lon"].tolist(),
            text=mappable["country"].tolist(),
            customdata=mappable["country"].tolist(),
            mode="markers",
            marker=dict(
                size=sizes,
                color=mappable["count"].tolist(),
                colorscale="Turbo",
                showscale=True,
                colorbar=dict(title="Sample count"),
                line=dict(width=0.6, color="#1a1a1a"),
                opacity=0.85,
            ),
            hovertemplate="%{text}<br>Samples: %{marker.color}<extra></extra>",
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
    with map_placeholder:
        selected = plotly_events(
            fig,
            click_event=True,
            hover_event=False,
            select_event=False,
            override_height=520,
            override_width="100%",
        )

    st.subheader("Country Selection")
    country_options = ["All"] + sorted(located["country"].dropna().unique().tolist())
    if "selected_country" not in st.session_state:
        st.session_state["selected_country"] = "All"
    if selected:
        point_idx = selected[0].get("pointIndex")
        if point_idx is not None and point_idx < len(mappable):
            st.session_state["selected_country"] = mappable.iloc[point_idx]["country"]
    selected_country = st.selectbox(
        "Select a country to inspect samples",
        country_options,
        index=country_options.index(st.session_state["selected_country"])
        if st.session_state["selected_country"] in country_options
        else 0,
    )

    selected_rows = located
    if selected_country != "All":
        selected_rows = located[located["country"] == selected_country]

if selected_rows.empty:
    st.info("No samples for the selected country and filters.")
else:
    sp_counts = (
        selected_rows.groupby(["country"])
        .size()
        .reset_index(name="count")
    )
    if selected_country == "All":
        st.caption("Sample count by country")
        st.dataframe(sp_counts, use_container_width=True, height=220)
    else:
        st.subheader("Species/Pathovar Breakdown")
        tax_raw = load_sample_taxonomy()
        selected_ids = selected_rows["sample_id"].tolist()
        tax_filtered = tax_raw[tax_raw["sample_id"].isin(selected_ids)].copy()

        legacy_map = build_legacy_taxon_map(
            tax_raw,
            include_pathovar=True,
            legacy_col="legacy_strain_name",
            sample_id_col="sample_id",
        )
        tax_filtered["species_pathovar"] = apply_taxon_fallback(
            tax_filtered,
            include_pathovar=True,
            legacy_map=legacy_map,
            id_col="sample_id",
            legacy_col="legacy_strain_name",
        )
        tax_filtered["species_pathovar"] = abbreviate_taxon_labels(
            tax_filtered["species_pathovar"]
        )
        sp_counts = (
            tax_filtered["species_pathovar"]
            .value_counts()
            .rename_axis("species_pathovar")
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        sp_chart = (
            alt.Chart(sp_counts)
            .mark_bar()
            .encode(
                x=alt.X("count:Q", title="Sample count", axis=alt.Axis(format="d")),
                y=alt.Y("species_pathovar:N", sort="-x", title="Species + Pathovar"),
                tooltip=["species_pathovar:N", "count:Q"],
            )
        )
        st.altair_chart(sp_chart.properties(height=300), use_container_width=True)

with st.expander("Samples Without Location", expanded=False):
    if missing_country.empty:
        st.info("No samples missing location data.")
    else:
        missing_rows = missing_country[["sample_id", "strain_display"]]
        st.dataframe(missing_rows, use_container_width=True, height=300)
