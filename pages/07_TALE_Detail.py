import altair as alt
import pandas as pd
import streamlit as st

from utils.db import load_tale_detail, load_tale_options, load_tale_rvds
from utils.page import init_page
from utils.theme import blue_card_dark_mode_css

init_page("TALE Detail", "TALE Detail")
st.title("TALE Detail")


def to_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return int(cleaned) if cleaned.isdigit() else None


def coalesce_text(*values, default: str = "Unknown") -> str:
    for value in values:
        if pd.notna(value):
            text = str(value).strip()
            if text and text.lower() != "nan":
                return text
    return default


def taxonomy_label(row: pd.Series) -> str:
    species = coalesce_text(row.get("species"), default="")
    pathovar = coalesce_text(row.get("pathovar"), default="")
    if species:
        return f"{species} pv. {pathovar}" if pathovar else species
    return coalesce_text(row.get("taxon_name"))


def strand_label(value) -> str:
    return {1: "+", -1: "-"}.get(value, "?")


def fasta_text(header: str, sequence: str) -> str:
    if not sequence:
        return f">{header}\n"
    wrapped = [sequence[idx : idx + 80] for idx in range(0, len(sequence), 80)]
    return f">{header}\n" + "\n".join(wrapped) + "\n"


def ncbi_nuccore_url(accession: str) -> str:
    return f"https://www.ncbi.nlm.nih.gov/nuccore/{accession}"


def ncbi_biosample_url(biosample_id: str) -> str:
    return f"https://www.ncbi.nlm.nih.gov/biosample/{biosample_id}"


def ncbi_taxonomy_url(tax_id: int) -> str:
    return f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={tax_id}"


def sequence_composition(sequence: str, alphabet: list[str]) -> pd.DataFrame:
    if not sequence:
        return pd.DataFrame(columns=["symbol", "count", "fraction"])
    cleaned = sequence.upper()
    rows = []
    for symbol in alphabet:
        count = cleaned.count(symbol)
        rows.append(
            {
                "symbol": symbol,
                "count": count,
                "fraction": (count / len(cleaned)) if cleaned else 0.0,
            }
        )
    return pd.DataFrame(rows)


def local_position_rows(start_pos: int, end_pos: int, flank: int = 1000) -> pd.DataFrame:
    left = max(0, start_pos - flank)
    right = end_pos + flank
    return pd.DataFrame(
        [
            {
                "segment": "TALE",
                "start_local": flank,
                "end_local": flank + (end_pos - start_pos),
                "start_actual": start_pos,
                "end_actual": end_pos,
                "window_start": left,
                "window_end": right,
            }
        ]
    )


st.markdown(
    """
    <style>
    .tale-hero {
        padding: 1.1rem 1.2rem;
        border: 1px solid #d9dfd2;
        border-radius: 16px;
        background:
            radial-gradient(circle at top right, rgba(174, 196, 136, 0.35), transparent 34%),
            linear-gradient(145deg, #f7f4ea 0%, #eef4e6 100%);
        margin-bottom: 1rem;
    }
    .tale-kicker {
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-size: 0.75rem;
        color: #55624b;
        margin-bottom: 0.35rem;
    }
    .tale-title {
        font-size: 2rem;
        line-height: 1.1;
        font-weight: 700;
        color: #182018;
        margin: 0 0 0.35rem 0;
    }
    .tale-meta {
        font-size: 0.98rem;
        color: #334033;
        margin: 0.15rem 0;
    }
    .tale-meta-label {
        display: inline-block;
        min-width: 5.5rem;
        font-weight: 700;
        color: #1f271c;
    }
    .tale-meta-value {
        color: #334033;
    }
    .tale-chip-row {
        margin-top: 0.8rem;
    }
    .tale-chip {
        display: inline-block;
        padding: 0.3rem 0.55rem;
        margin: 0 0.45rem 0.35rem 0;
        border-radius: 999px;
        background: #dfe8cf;
        color: #26311f;
        font-size: 0.84rem;
    }
    .link-card {
        padding: 0.9rem 1rem;
        border: 1px solid #e2e5dc;
        border-radius: 14px;
        background: #fbfbf7;
        min-height: 92px;
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
        card_selector=".tale-hero",
        title_selector=".tale-title",
        sub_selector=".tale-kicker",
        label_selector=".tale-meta-label",
        text_selector=".tale-meta, .tale-meta-value",
        chip_selector=".tale-chip",
        link_card_selector=".link-card",
        link_title_selector=".link-card strong",
        link_text_selector=".link-card span",
    )
    + """
    </style>
    """,
    unsafe_allow_html=True,
)

tale_options = load_tale_options()
if tale_options.empty:
    st.warning("No TALEs found.")
    st.stop()

tale_options = tale_options.copy()
tale_options["tale_id"] = tale_options["tale_id"].astype(int)
tale_ids = tale_options["tale_id"].tolist()
tale_name_by_id = dict(
    zip(tale_options["tale_id"], tale_options["tale_name"].fillna(""))
)

selected_from_query = to_int(st.query_params.get("tale_id"))
last_query_tale_id = st.session_state.get("tale_detail_last_query_id")
if st.session_state.get("tale_detail_id") not in tale_ids:
    st.session_state["tale_detail_id"] = (
        int(selected_from_query) if selected_from_query in tale_ids else tale_ids[0]
    )
elif selected_from_query in tale_ids and selected_from_query != last_query_tale_id:
    st.session_state["tale_detail_id"] = int(selected_from_query)

selected_tale_id = st.selectbox(
    "TALE",
    tale_ids,
    key="tale_detail_id",
    format_func=lambda tale_id: f"{tale_id}: {tale_name_by_id.get(tale_id, '')}",
)
selected_tale_id = int(selected_tale_id)
st.query_params["tale_id"] = str(selected_tale_id)
st.session_state["tale_detail_last_query_id"] = selected_tale_id

detail = load_tale_detail(selected_tale_id)
if detail.empty:
    st.warning("No detail found for the selected TALE.")
    st.stop()

row = detail.iloc[0]
dna_seq = coalesce_text(row.get("dna_seq"), default="")
protein_seq = coalesce_text(row.get("protein_seq"), default="")
family_name = coalesce_text(row.get("family"))
sample_name = coalesce_text(row.get("strain_name"), row.get("legacy_strain_name"))
assembly_accession = coalesce_text(row.get("accession"))
replicon_type = coalesce_text(row.get("replicon_type"))
taxonomy_name = taxonomy_label(row)
current_strand = strand_label(row.get("strand"))
assembly_suffix = (
    f" ({replicon_type})"
    if replicon_type != "Unknown"
    else ""
)
assembly_display = (
    f"{assembly_accession}{assembly_suffix}"
    if assembly_accession != "Unknown"
    else f"assembly {coalesce_text(row.get('assembly_id'))}{assembly_suffix}"
)
genomic_length = None
if pd.notna(row.get("start_pos")) and pd.notna(row.get("end_pos")):
    genomic_length = int(row["end_pos"]) - int(row["start_pos"])

st.markdown(
    f"""
    <div class="tale-hero">
        <div class="tale-kicker">TALE Record</div>
        <div class="tale-title">{row["tale_name"]}</div>
        <div class="tale-meta"><span class="tale-meta-label">TALE</span><span class="tale-meta-value">ID {int(row["tale_id"])} • Family {family_name} • Strand {current_strand}</span></div>
        <div class="tale-meta"><span class="tale-meta-label">Sample</span><span class="tale-meta-value">{sample_name}</span></div>
        <div class="tale-meta"><span class="tale-meta-label">Assembly</span><span class="tale-meta-value">{assembly_display}</span></div>
        <div class="tale-meta"><span class="tale-meta-label">Taxonomy</span><span class="tale-meta-value">{taxonomy_name}</span></div>
        <div class="tale-chip-row">
            <span class="tale-chip">{'Pseudo' if int(row['is_pseudo'] or 0) == 1 else 'Non-pseudo'}</span>
            <span class="tale-chip">{replicon_type if replicon_type != "Unknown" else 'Replicon type unknown'}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

rvds = load_tale_rvds(selected_tale_id)

nav_col1, nav_col2 = st.columns(2)
if nav_col1.button("Open in TALE Families", key=f"to_family_{int(row['tale_id'])}", use_container_width=True):
    selected_id = int(row["tale_id"])
    st.session_state["selected_tale_id"] = selected_id
    st.session_state["family_selected_tale_control"] = selected_id
    st.query_params["tale_id"] = str(selected_id)
    if hasattr(st, "switch_page"):
        st.switch_page("pages/03_TALE_Families.py")
if nav_col2.button("Open in Genome Organization", key=f"to_genome_{int(row['tale_id'])}", use_container_width=True):
    selected_id = int(row["tale_id"])
    sample_id = row.get("sample_id")
    species_display = coalesce_text(row.get("species"))
    pathovar_display = coalesce_text(row.get("pathovar"))
    if pd.notna(sample_id):
        st.session_state["genome_org_sample_id"] = int(sample_id)
    if species_display != "Unknown":
        st.session_state["genome_org_species"] = species_display
    else:
        st.session_state.pop("genome_org_species", None)
    if pathovar_display != "Unknown":
        st.session_state["genome_org_pathovar"] = pathovar_display
    else:
        st.session_state.pop("genome_org_pathovar", None)
    st.session_state["genome_org_selected_tale_id"] = selected_id
    st.session_state["genome_org_last_query_tale_id"] = None
    if pd.notna(sample_id):
        st.session_state["genome_org_pending_sample_id"] = int(sample_id)
    st.session_state["genome_org_pending_tale_id"] = selected_id
    st.session_state.pop("genome_org_pending_assembly", None)
    st.session_state.pop("genome_org_target_assembly", None)
    st.session_state.pop("genome_org_assemblies", None)
    st.session_state["genome_org_query_select_focus_assembly"] = False
    st.session_state["genome_org_previous_scope"] = None
    st.query_params["tale_id"] = str(selected_id)
    if hasattr(st, "switch_page"):
        st.switch_page("pages/06_Genome_Organization.py")

st.subheader("Links")
link_cols = st.columns(3)
with link_cols[0]:
    st.markdown(
        f"""
        <div class="link-card">
            <strong>Assembly</strong>
            <span>{assembly_accession if assembly_accession != "Unknown" else 'No accession available'}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if assembly_accession != "Unknown":
        st.link_button("Open NCBI accession", ncbi_nuccore_url(assembly_accession), use_container_width=True)
with link_cols[1]:
    biosample_id = coalesce_text(row.get("biosample_id"))
    st.markdown(
        f"""
        <div class="link-card">
            <strong>BioSample</strong>
            <span>{biosample_id}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if biosample_id != "Unknown":
        st.link_button("Open NCBI BioSample", ncbi_biosample_url(biosample_id), use_container_width=True)
with link_cols[2]:
    ncbi_tax_id = row.get("ncbi_tax_id")
    st.markdown(
        f"""
        <div class="link-card">
            <strong>Taxonomy</strong>
            <span>{taxonomy_name}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if pd.notna(ncbi_tax_id):
        st.link_button("Open NCBI Taxonomy", ncbi_taxonomy_url(int(ncbi_tax_id)), use_container_width=True)

overview_left, overview_right = st.columns([1.1, 1])
with overview_left:
    st.subheader("Sequence Sizes")
    size_rows = pd.DataFrame(
        [
            {"measure": "Genomic span", "length": genomic_length or 0, "label": f"{genomic_length:,} nt" if genomic_length is not None else "Unknown"},
            {"measure": "DNA sequence", "length": len(dna_seq), "label": f"{len(dna_seq):,} nt"},
            {"measure": "Protein sequence", "length": len(protein_seq), "label": f"{len(protein_seq):,} aa"},
        ]
    )
    size_chart = (
        alt.Chart(size_rows)
        .mark_bar(cornerRadiusEnd=8)
        .encode(
            x=alt.X("length:Q", title="Length"),
            y=alt.Y(
                "measure:N",
                sort=["Genomic span", "DNA sequence", "Protein sequence"],
                title=None,
            ),
            color=alt.Color(
                "measure:N",
                scale=alt.Scale(
                    domain=["Genomic span", "DNA sequence", "Protein sequence"],
                    range=["#6e8c47", "#b96a33", "#3f6f8b"],
                ),
                legend=None,
            ),
            tooltip=["measure:N", "label:N"],
        )
    )
    size_labels = (
        alt.Chart(size_rows)
        .mark_text(opacity=0)
    )
    st.altair_chart(size_chart.properties(height=160), use_container_width=True)
    if genomic_length is not None and dna_seq:
        delta = genomic_length - len(dna_seq)
        st.caption(f"Genomic span minus DNA sequence length: {delta:,} nt")

with overview_right:
    st.subheader("Genomic Placement")
    if genomic_length is None:
        st.info("No genomic coordinates available.")
    else:
        placement_df = local_position_rows(int(row["start_pos"]), int(row["end_pos"]))
        actual_label = f"{int(row['start_pos']):,} - {int(row['end_pos']):,}"
        local_end = 1000 + (int(row["end_pos"]) - int(row["start_pos"]))
        window_end_local = 2000 + (int(row["end_pos"]) - int(row["start_pos"]))
        mid_left = 500
        mid_right = local_end + 500
        placement_chart = (
            alt.Chart(placement_df)
            .mark_bar(size=24, cornerRadius=8, color="#6e8c47")
            .encode(
                x=alt.X(
                    "start_local:Q",
                    title="Compressed local genome view",
                    axis=alt.Axis(
                        values=[0, mid_left, 1000, local_end, mid_right, window_end_local],
                        labelExpr=(
                            f"datum.value == 0 ? '{placement_df.iloc[0]['window_start']:,}' : "
                            f"datum.value == {mid_left} ? '{placement_df.iloc[0]['window_start'] + 500:,}' : "
                            f"datum.value == 1000 ? '{int(row['start_pos']):,}' : "
                            f"datum.value == {local_end} ? '{int(row['end_pos']):,}' : "
                            f"datum.value == {mid_right} ? '{int(row['end_pos']) + 500:,}' : "
                            f"'{placement_df.iloc[0]['window_end']:,}'"
                        ),
                        labelAngle=0,
                    ),
                ),
                x2="end_local:Q",
                y=alt.Y("segment:N", title=None, axis=alt.Axis(labels=False, ticks=False)),
                tooltip=[
                    alt.Tooltip("start_actual:Q", title="Start", format=",.0f"),
                    alt.Tooltip("end_actual:Q", title="End", format=",.0f"),
                ],
            )
        )
        st.markdown(f"**TALE span:** `{actual_label}`")
        st.altair_chart(placement_chart.properties(height=120), use_container_width=True)
        st.caption("Empty flanking regions are compressed to a fixed local window around the TALE.")

composition_cols = st.columns(2)
with composition_cols[0]:
    st.subheader("DNA Composition")
    dna_comp = sequence_composition(dna_seq, ["A", "C", "G", "T"])
    if dna_comp.empty:
        st.info("No DNA sequence available.")
    else:
        dna_chart = (
            alt.Chart(dna_comp)
            .mark_arc(innerRadius=36)
            .encode(
                theta=alt.Theta("count:Q"),
                color=alt.Color(
                    "symbol:N",
                    scale=alt.Scale(
                        domain=["A", "C", "G", "T"],
                        range=["#9a633a", "#5d8b58", "#4f6f94", "#d3a437"],
                    ),
                    legend=alt.Legend(title=None, orient="bottom"),
                ),
                tooltip=["symbol:N", "count:Q", alt.Tooltip("fraction:Q", format=".1%")],
            )
        )
        st.altair_chart(dna_chart.properties(height=220), use_container_width=True)

with composition_cols[1]:
    st.subheader("RVD Architecture")
    if rvds.empty:
        st.info("No RVDs found for this TALE.")
    else:
        rvd_chart = (
            alt.Chart(rvds)
            .mark_circle(size=120, color="#b15d2a")
            .encode(
                x=alt.X("position:Q", title="Repeat position", axis=alt.Axis(format="d")),
                y=alt.Y("rvd:N", title="RVD"),
                tooltip=["position:Q", "rvd:N"],
            )
        )
        st.altair_chart(rvd_chart.properties(height=220), use_container_width=True)
        st.markdown(f"**RVD string:** `{' '.join(rvds['rvd'].fillna('').tolist())}`")

st.subheader("Downloads")
download_cols = st.columns(2)
dna_header = f"tale_{int(row['tale_id'])}|{row['tale_name']}|dna"
protein_header = f"tale_{int(row['tale_id'])}|{row['tale_name']}|protein"
download_cols[0].download_button(
    "Download DNA FASTA",
    data=fasta_text(dna_header, dna_seq),
    file_name=f"tale_{int(row['tale_id'])}_dna.fasta",
    mime="text/plain",
    disabled=not bool(dna_seq),
    use_container_width=True,
)
download_cols[1].download_button(
    "Download Protein FASTA",
    data=fasta_text(protein_header, protein_seq),
    file_name=f"tale_{int(row['tale_id'])}_protein.fasta",
    mime="text/plain",
    disabled=not bool(protein_seq),
    use_container_width=True,
)

seq_tab_dna, seq_tab_protein, seq_tab_meta = st.tabs(["DNA", "Protein", "Metadata"])
with seq_tab_dna:
    st.caption(f"DNA sequence ({len(dna_seq):,} nt)")
    if dna_seq:
        st.code(dna_seq, language=None)
    else:
        st.info("No DNA sequence available.")
with seq_tab_protein:
    st.caption(f"Protein sequence ({len(protein_seq):,} aa)")
    if protein_seq:
        st.code(protein_seq, language=None)
    else:
        st.info("No protein sequence available.")
with seq_tab_meta:
    meta_left, meta_right = st.columns(2)
    with meta_left:
        st.markdown(f"**Assembly ID:** {coalesce_text(row.get('assembly_id'))}")
        st.markdown(f"**Accession type:** {coalesce_text(row.get('accession_type'))}")
        st.markdown(f"**Version:** {coalesce_text(row.get('version'))}")
        st.markdown(f"**Replicon type:** {replicon_type}")
        st.markdown(f"**Sample ID:** {coalesce_text(row.get('sample_id'))}")
        st.markdown(f"**BioSample ID:** {coalesce_text(row.get('biosample_id'))}")
        st.markdown(f"**Geography:** {coalesce_text(row.get('geo_tag'))}")
    with meta_right:
        st.markdown(f"**Taxonomy rank:** {coalesce_text(row.get('taxonomy_rank'))}")
        st.markdown(f"**NCBI tax ID:** {coalesce_text(row.get('ncbi_tax_id'))}")
        st.markdown(f"**Collection date:** {coalesce_text(row.get('collection_date'))}")
        st.markdown(f"**Coordinates:** {coalesce_text(row.get('start_pos'))} - {coalesce_text(row.get('end_pos'))}")
        st.markdown(f"**Strand:** {current_strand}")
        st.markdown(f"**Is new:** {'Yes' if int(row['is_new'] or 0) == 1 else 'No'}")
        st.markdown(f"**Pseudo:** {'Yes' if int(row['is_pseudo'] or 0) == 1 else 'No'}")
