from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.db_core import query_df


TALE_SEQUENCES_CTE = """
WITH tale_sequences AS (
    SELECT t.*,
           t.dna_start_seq || COALESCE((
               SELECT group_concat(dna_seq, '')
               FROM (
                   SELECT r.dna_seq
                   FROM repeat r
                   WHERE r.tale_id = t.id
                   ORDER BY r.repeat_ordinal
               )
           ), '') || t.dna_end_seq AS dna_seq,
           t.protein_start_seq || COALESCE((
               SELECT group_concat(protein_seq, '')
               FROM (
                   SELECT r.protein_seq
                   FROM repeat r
                   WHERE r.tale_id = t.id
                   ORDER BY r.repeat_ordinal
               )
           ), '') || t.protein_end_seq AS protein_seq
    FROM tale t
)
"""


@st.cache_data(show_spinner=False)
def load_families() -> pd.DataFrame:
    return query_df(
        "SELECT name, member_count, tree_newick FROM tale_family ORDER BY member_count DESC"
    )


@st.cache_data(show_spinner=False)
def load_family_alignment(family_name: str) -> str:
    rows = query_df(
        "SELECT alignment_fasta FROM tale_family WHERE name = ?", params=[family_name]
    )
    return "" if rows.empty else str(rows.iloc[0]["alignment_fasta"] or "")


@st.cache_data(show_spinner=False)
def load_family_members() -> pd.DataFrame:
    return query_df("SELECT family_id, tale_id FROM tale_family_member")


@st.cache_data(show_spinner=False)
def load_tales() -> pd.DataFrame:
    return query_df(
        TALE_SEQUENCES_CTE
        + "SELECT t.id, t.legacy_name AS name, t.is_pseudo, a.sample_id AS strain_id, "
        "t.start_pos, t.end_pos, t.strand, t.is_new, t.dna_seq, t.protein_seq "
        "FROM tale_sequences t "
        "LEFT JOIN assembly a ON a.id = t.assembly_id"
    )


@st.cache_data(show_spinner=False)
def load_family_tale_rows(family_name: str) -> pd.DataFrame:
    return query_df(
        """
        SELECT t.id AS id,
               fm.family_id AS family,
               s.strain_name,
               s.legacy_strain_name,
               tx.species,
               tx.pathovar,
               tx.raw_name AS taxon_name,
               t.is_pseudo AS is_pseudo,
               COUNT(r.repeat_ordinal) AS repeat_len
        FROM tale_family_member fm
        JOIN tale t ON t.id = fm.tale_id
        LEFT JOIN repeat r ON r.tale_id = t.id
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN samples s ON s.id = a.sample_id
        LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id
        WHERE fm.family_id = ?
        GROUP BY t.id, fm.family_id, s.strain_name, s.legacy_strain_name,
                 tx.species, tx.pathovar, tx.raw_name, t.is_pseudo
        ORDER BY t.id
        """,
        params=[family_name],
    )


@st.cache_data(show_spinner=False)
def load_family_species_pathovar(family_name: str) -> pd.DataFrame:
    return query_df(
        """
        SELECT s.id AS sample_id,
               s.legacy_strain_name,
               tx.species,
               tx.pathovar,
               tx.raw_name AS taxon_name
        FROM tale_family_member fm
        JOIN tale t ON t.id = fm.tale_id
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN samples s ON s.id = a.sample_id
        LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id
        WHERE fm.family_id = ?
        """,
        params=[family_name],
    )


@st.cache_data(show_spinner=False)
def load_tale_rvds(tale_id: int) -> pd.DataFrame:
    return query_df(
        """
        SELECT r.repeat_ordinal AS position, r.rvd AS rvd
        FROM repeat r
        WHERE r.tale_id = ?
        ORDER BY r.repeat_ordinal
        """,
        params=[int(tale_id)],
    )


@st.cache_data(show_spinner=False)
def load_strain_tales(strain_id: int) -> pd.DataFrame:
    return query_df(
        TALE_SEQUENCES_CTE
        + """
        SELECT t.id AS tale_id,
               t.legacy_name AS tale_name,
               t.dna_seq,
               t.is_pseudo,
               t.is_new,
               t.start_pos,
               t.end_pos,
               t.strand,
               t.protein_seq,
               fm.family_id AS family,
               a.id AS assembly_id,
               a.accession,
               a.version,
               a.accession_type,
               a.replicon_type,
               s.strain_name AS sample_name,
               s.legacy_strain_name,
               tx.raw_name AS taxon_name,
               tx.species,
               tx.pathovar
        FROM tale_sequences t
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN tale_family_member fm ON fm.tale_id = t.id
        LEFT JOIN samples s ON s.id = a.sample_id
        LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id
        WHERE a.sample_id = ?
        ORDER BY
            CASE WHEN t.start_pos IS NULL THEN 1 ELSE 0 END,
            a.accession,
            t.start_pos,
            t.id
        """,
        params=[int(strain_id)],
    )


@st.cache_data(show_spinner=False)
def load_tale_options() -> pd.DataFrame:
    return query_df(
        """
        SELECT t.id AS tale_id,
               t.legacy_name,
               fm.family_id AS family,
               s.strain_name,
               s.legacy_strain_name,
               tx.species,
               tx.pathovar,
               tx.raw_name AS taxon_name
        FROM tale t
        LEFT JOIN tale_family_member fm ON fm.tale_id = t.id
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN samples s ON s.id = a.sample_id
        LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id
        ORDER BY t.id
        """
    )


@st.cache_data(show_spinner=False)
def load_tale_detail(tale_id: int) -> pd.DataFrame:
    return query_df(
        TALE_SEQUENCES_CTE
        + """
        SELECT t.id AS tale_id,
               t.legacy_name AS tale_name,
               t.dna_seq,
               t.protein_seq,
               t.start_pos,
               t.end_pos,
               t.strand,
               t.is_new,
               t.is_pseudo,
               fm.family_id AS family,
               a.id AS assembly_id,
               a.accession,
               a.version,
               a.accession_type,
               a.replicon_type,
               s.id AS sample_id,
               s.biosample_id,
               s.legacy_strain_name,
               s.strain_name,
               s.geo_tag,
               s.collection_date,
               tx.ncbi_tax_id,
               tx.rank AS taxonomy_rank,
               tx.raw_name AS taxon_name,
               tx.species,
               tx.pathovar
        FROM tale_sequences t
        LEFT JOIN tale_family_member fm ON fm.tale_id = t.id
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN samples s ON s.id = a.sample_id
        LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id
        WHERE t.id = ?
        """,
        params=[int(tale_id)],
    )


@st.cache_data(show_spinner=False)
def load_family_download_rows(family_name: str) -> pd.DataFrame:
    return query_df(
        TALE_SEQUENCES_CTE
        + """
        SELECT t.id AS tale_id,
               t.legacy_name AS tale_name,
               t.dna_seq,
               t.start_pos,
               t.end_pos,
               t.strand,
               fm.family_id AS family,
               a.accession,
               s.strain_name,
               s.legacy_strain_name,
               tx.raw_name AS taxon_name,
               tx.species,
               tx.pathovar
        FROM tale_family_member fm
        JOIN tale_sequences t ON t.id = fm.tale_id
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN samples s ON s.id = a.sample_id
        LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id
        WHERE fm.family_id = ?
        ORDER BY t.id
        """,
        params=[family_name],
    )
