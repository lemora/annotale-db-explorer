import pandas as pd
import streamlit as st

from utils.analytics import track_page_visit
from utils.sample_helpers import (
    build_sample_selector_rows,
    country_or_unknown,
    format_sample_label,
)
from utils.sample_queries import (
    load_sample_assemblies,
    load_sample_detail,
    load_strains,
)
from utils.tale_queries import load_strain_tales
from utils.fasta_export import coalesce_text
from utils.page import init_page
from utils.taxonomy import resolved_taxon_labels
from utils.theme import blue_card_dark_mode_css


def to_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return int(cleaned) if cleaned.isdigit() else None


def sample_title(row: pd.Series) -> str:
    return coalesce_text(
        row.get("strain_name"),
        row.get("legacy_strain_name"),
        default="Unknown sample",
    )


def ncbi_biosample_url(biosample_id: str) -> str:
    return f"https://www.ncbi.nlm.nih.gov/biosample/{biosample_id}"


def ncbi_taxonomy_url(tax_id: int) -> str:
    return f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={tax_id}"


def ncbi_nuccore_url(accession: str) -> str:
    return f"https://www.ncbi.nlm.nih.gov/nuccore/{accession}"


def ncbi_assembly_url(accession: str) -> str:
    return f"https://www.ncbi.nlm.nih.gov/assembly/{accession}"


def ncbi_accession_url(accession: str, accession_type: object) -> str:
    if str(accession_type or "").strip().lower() == "assembly":
        return ncbi_assembly_url(accession)
    return ncbi_nuccore_url(accession)


def missing_value_label(value: str, label: str) -> str:
    return value if value != "Unknown" else "-"


def assembly_option_label(row: pd.Series) -> str:
    accession = coalesce_text(row.get("accession"))
    replicon_type = coalesce_text(row.get("replicon_type"))
    if replicon_type != "Unknown":
        return f"{accession} ({replicon_type})"
    return accession


def sample_option_label(row: pd.Series) -> str:
    return format_sample_label(row)


def load_sample_selector_rows() -> pd.DataFrame:
    return build_sample_selector_rows(load_strains())


def initialize_widget_state(key: str, options: list[str] | list[int], fallback) -> None:
    if st.session_state.get(key) not in options:
        st.session_state[key] = fallback


def sync_sample_url(sample_id: int) -> None:
    st.query_params.clear()
    st.query_params["sample_id"] = str(int(sample_id))
    st.session_state["sample_page_last_query_id"] = int(sample_id)
init_page("Sample", "Sample", track_analytics=False)
st.title("Sample")

st.markdown(
    """
    <style>
    .sample-hero {
        padding: 1.1rem 1.2rem;
        border: 1px solid #d9dfd2;
        border-radius: 16px;
        background:
            radial-gradient(circle at top right, rgba(174, 196, 136, 0.35), transparent 34%),
            linear-gradient(145deg, #f7f4ea 0%, #eef4e6 100%);
        margin-bottom: 1rem;
    }
    .sample-kicker {
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-size: 0.75rem;
        color: #55624b;
        margin-bottom: 0.35rem;
    }
    .sample-title {
        font-size: 2rem;
        line-height: 1.1;
        font-weight: 700;
        color: #182018;
        margin: 0 0 0.35rem 0;
    }
    .sample-meta {
        font-size: 0.98rem;
        color: #334033;
        margin: 0.15rem 0;
    }
    .sample-meta-label {
        display: inline-block;
        min-width: 7rem;
        font-weight: 700;
        color: #1f271c;
    }
    .link-card {
        padding: 0.9rem 1rem;
        border: 1px solid #e2e5dc;
        border-radius: 14px;
        background: #fbfbf7;
        min-height: 104px;
    }
    .link-card strong {
        display: block;
        margin-bottom: 0.2rem;
        color: #1f271c;
    }
    .link-card span {
        color: #5d6657;
        font-size: 0.92rem;
    }
    """
    + blue_card_dark_mode_css(
        card_selector=".sample-hero",
        title_selector=".sample-title",
        sub_selector=".sample-kicker",
        label_selector=".sample-meta-label",
        text_selector=".sample-meta",
        link_card_selector=".link-card",
        link_title_selector=".link-card strong",
        link_text_selector=".link-card span",
    )
    + """
    </style>
    """,
    unsafe_allow_html=True,
)

selector_rows = load_sample_selector_rows()
if selector_rows.empty:
    st.warning("No sample data available.")
    st.stop()

pending_sample_id = st.session_state.pop("sample_page_pending_sample_id", None)
query_sample_id = to_int(st.query_params.get("sample_id"))
sample_ids = selector_rows["sample_id"].tolist()

if st.session_state.get("sample_page_sample_id") not in sample_ids:
    st.session_state["sample_page_sample_id"] = int(selector_rows.iloc[0]["sample_id"])
if pending_sample_id in sample_ids:
    st.session_state["sample_page_sample_id"] = int(pending_sample_id)
    pending_row = selector_rows[selector_rows["sample_id"] == int(pending_sample_id)].iloc[0]
    st.session_state["sample_page_species"] = pending_row["species_display"]
    st.session_state["sample_page_pathovar"] = pending_row["pathovar_display"]
elif (
    query_sample_id in sample_ids
    and query_sample_id != st.session_state.get("sample_page_last_query_id")
):
    st.session_state["sample_page_sample_id"] = int(query_sample_id)
    query_row = selector_rows[selector_rows["sample_id"] == int(query_sample_id)].iloc[0]
    st.session_state["sample_page_species"] = query_row["species_display"]
    st.session_state["sample_page_pathovar"] = query_row["pathovar_display"]

selected_sample_id = int(st.session_state["sample_page_sample_id"])
selected_row = selector_rows[selector_rows["sample_id"] == selected_sample_id].iloc[0]
species_options = sorted(selector_rows["species_display"].drop_duplicates().tolist())
initialize_widget_state(
    "sample_page_species", species_options, selected_row["species_display"]
)
selected_species = st.selectbox("Species", species_options, key="sample_page_species")

species_scope = selector_rows[selector_rows["species_display"] == selected_species].copy()
pathovar_options = sorted(species_scope["pathovar_display"].drop_duplicates().tolist())
default_pathovar = (
    selected_row["pathovar_display"]
    if selected_row["species_display"] == selected_species and selected_row["pathovar_display"] in pathovar_options
    else pathovar_options[0]
)
initialize_widget_state("sample_page_pathovar", pathovar_options, default_pathovar)
selected_pathovar = st.selectbox("Pathovar", pathovar_options, key="sample_page_pathovar")

sample_scope = species_scope[species_scope["pathovar_display"] == selected_pathovar].copy()
sample_scope = sample_scope.sort_values(["sample_display", "sample_id"]).reset_index(drop=True)
sample_options = sample_scope["sample_id"].tolist()
default_sample_id = selected_sample_id if selected_sample_id in sample_options else sample_options[0]
initialize_widget_state("sample_page_sample_id", sample_options, default_sample_id)
selected_sample_id = int(
    st.selectbox(
        "Strain / BioSample ID",
        sample_options,
        key="sample_page_sample_id",
        format_func=lambda sample_id: sample_option_label(
            sample_scope.loc[sample_scope["sample_id"] == sample_id].iloc[0]
        ),
    )
)
sync_sample_url(selected_sample_id)

detail = load_sample_detail(selected_sample_id)
if detail.empty:
    st.warning("No sample detail found.")
    st.stop()

track_page_visit()

row = detail.iloc[0]
sample_name = sample_title(row)
taxonomy_name = resolved_taxon_labels(detail, include_pathovar=True).iloc[0]
taxonomy_level = coalesce_text(row.get("taxonomy_rank"))
assemblies = load_sample_assemblies(selected_sample_id)
tales = load_strain_tales(selected_sample_id)
tale_counts = (
    tales["family"]
    .fillna("Unassigned")
    .value_counts()
    .rename_axis("family")
    .reset_index(name="TALEs")
)
top_families = ", ".join(
    tale_counts.head(6).apply(lambda row_: f"{row_['family']} ({int(row_['TALEs'])})", axis=1).tolist()
)

st.markdown(
    f"""
    <div class="sample-hero">
        <div class="sample-kicker">Sample Record</div>
        <div class="sample-title">{sample_name}</div>
        <div class="sample-meta"><span class="sample-meta-label">Taxonomy</span>{taxonomy_name}</div>
        <div class="sample-meta"><span class="sample-meta-label">Taxonomy level</span>{missing_value_label(taxonomy_level, 'taxonomy level')}</div>
        <div class="sample-meta"><span class="sample-meta-label">BioSample</span>{missing_value_label(coalesce_text(row.get('biosample_id')), 'BioSample')}</div>
        <div class="sample-meta"><span class="sample-meta-label">Location</span>{missing_value_label(coalesce_text(row.get('geo_tag')), 'location')}</div>
        <div class="sample-meta"><span class="sample-meta-label">Collection date</span>{missing_value_label(coalesce_text(row.get('collection_date')), 'collection date')}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

nav_col1, nav_col2 = st.columns(2)
if nav_col1.button("📍 Open in Sample Map", use_container_width=True):
    st.session_state["sample_map_pending_country"] = country_or_unknown(
        row.get("geo_tag")
    )
    st.session_state["sample_map_pending_taxon"] = taxonomy_name
    st.session_state["sample_map_pending_sample_id"] = int(row["sample_id"])
    st.query_params.clear()
    st.query_params["sample_id"] = str(int(row["sample_id"]))
    if hasattr(st, "switch_page"):
        st.switch_page("pages/02_Sample_Map.py")
if nav_col2.button("🧬 Open in Genome Organization", use_container_width=True):
    st.session_state["genome_org_pending_sample_id"] = int(row["sample_id"])
    st.session_state.pop("genome_org_pending_tale_id", None)
    st.session_state.pop("genome_org_pending_assembly", None)
    if hasattr(st, "switch_page"):
        st.switch_page("pages/04_Genome_Organization.py")

assembly_card_title = "Assemblies" if len(assemblies) > 1 else "Assembly"
selected_assembly = assemblies.iloc[0] if not assemblies.empty else None
assembly_options: list[int] = []
assembly_key = "sample_page_assembly_id"
if not assemblies.empty:
    assembly_options = assemblies["assembly_id"].tolist()
    if (
        st.session_state.get(assembly_key) not in assembly_options
        or st.session_state.get("sample_page_assembly_sample_id") != int(selected_sample_id)
    ):
        st.session_state[assembly_key] = int(assembly_options[0])
    st.session_state["sample_page_assembly_sample_id"] = int(selected_sample_id)
    selected_assembly = assemblies.loc[
        assemblies["assembly_id"] == int(st.session_state[assembly_key])
    ].iloc[0]

accession_text = (
    coalesce_text(selected_assembly.get("accession"))
    if selected_assembly is not None
    else "Unknown"
)
accession_type = (
    selected_assembly.get("accession_type")
    if selected_assembly is not None
    else None
)
biosample_id = coalesce_text(row.get("biosample_id"))
ncbi_tax_id = row.get("ncbi_tax_id")
card_cols = st.columns(3)
with card_cols[0]:
    st.markdown(
        f"""
        <div class="link-card">
            <strong>Taxonomy ({missing_value_label(taxonomy_level, 'level')})</strong>
            <span>{missing_value_label(taxonomy_name, 'taxonomy')}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button(
        "Open NCBI Taxonomy",
        ncbi_taxonomy_url(int(ncbi_tax_id)) if pd.notna(ncbi_tax_id) else "#",
        use_container_width=True,
        disabled=not pd.notna(ncbi_tax_id),
    )
with card_cols[1]:
    st.markdown(
        f"""
        <div class="link-card">
            <strong>BioSample</strong>
            <span>{missing_value_label(biosample_id, 'BioSample')}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button(
        "Open NCBI BioSample",
        ncbi_biosample_url(biosample_id) if biosample_id != "Unknown" else "#",
        use_container_width=True,
        disabled=biosample_id == "Unknown",
    )
with card_cols[2]:
    assembly_card_value = (
        missing_value_label(accession_text, "accession")
    )
    st.markdown(
        f"""
        <div class="link-card">
            <strong>{assembly_card_title}</strong>
            <span>{assembly_card_value}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if len(assemblies) > 1:
        assembly_action_cols = st.columns([1.3, 1.2], gap="small")
        with assembly_action_cols[0]:
            st.link_button(
                "Open NCBI Assembly",
                ncbi_accession_url(accession_text, accession_type) if accession_text != "Unknown" else "#",
                use_container_width=True,
                disabled=accession_text == "Unknown",
            )
        with assembly_action_cols[1]:
            st.selectbox(
                "Assemblies",
                assembly_options,
                key=assembly_key,
                label_visibility="collapsed",
                format_func=lambda assembly_id: assembly_option_label(
                    assemblies.loc[assemblies["assembly_id"] == assembly_id].iloc[0]
                ),
            )
    else:
        st.link_button(
            "Open NCBI Assembly",
            ncbi_accession_url(accession_text, accession_type) if accession_text != "Unknown" else "#",
            use_container_width=True,
            disabled=accession_text == "Unknown",
        )

stats_left, stats_mid, stats_right = st.columns(3)
stats_left.metric("TALEs", tales["tale_id"].nunique() if not tales.empty else 0)
stats_mid.metric(
    "Families",
    tales["family"].fillna("Unassigned").nunique() if not tales.empty else 0,
)
stats_right.metric(
    "Assemblies",
    len(assemblies),
)
