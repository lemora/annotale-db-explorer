from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.db_core import query_df


@st.cache_data(show_spinner=False)
def load_families() -> pd.DataFrame:
    return query_df(
        "SELECT name, member_count, tree_newick FROM tale_family ORDER BY member_count DESC"
    )


@st.cache_data(show_spinner=False)
def load_family_members() -> pd.DataFrame:
    return query_df("SELECT family_id, tale_id FROM tale_family_member")


@st.cache_data(show_spinner=False)
def load_tales() -> pd.DataFrame:
    return query_df(
        "SELECT t.id, t.legacy_name AS name, t.is_pseudo, a.sample_id AS strain_id, "
        "t.start_pos, t.end_pos, t.strand, t.is_new, t.dna_seq, t.protein_seq "
        "FROM tale t "
        "LEFT JOIN assembly a ON a.id = t.assembly_id"
    )


@st.cache_data(show_spinner=False)
def load_crosstab_source() -> pd.DataFrame:
    return query_df(
        """
        SELECT fm.family_id AS family,
               s.id AS sample_id,
               s.strain_name,
               s.legacy_strain_name,
               tx.species,
               tx.pathovar,
               tx.raw_name AS taxon_name
        FROM tale_family_member fm
        JOIN tale t ON t.id = fm.tale_id
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN samples s ON s.id = a.sample_id
        LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id
        """
    )


@st.cache_data(show_spinner=False)
def load_tale_set_cluster_source() -> pd.DataFrame:
    return query_df(
        """
        SELECT fm.family_id AS family,
               t.id AS tale_id,
               t.is_pseudo,
               a.id AS assembly_id,
               a.accession,
               a.replicon_type,
               s.id AS sample_id,
               s.strain_name,
               s.legacy_strain_name,
               tx.species,
               tx.pathovar,
               tx.raw_name AS taxon_name
        FROM tale_family_member fm
        JOIN tale t ON t.id = fm.tale_id
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN samples s ON s.id = a.sample_id
        LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id
        """
    )


@st.cache_data(show_spinner=False)
def load_family_tale_rows(family_name: str) -> pd.DataFrame:
    return query_df(
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
def load_family_rvd_counts(family_name: str, exclude_pseudo: bool = False) -> pd.DataFrame:
    clause = " AND t.is_pseudo = 0" if exclude_pseudo else ""
    return query_df(
        f"""
        SELECT r.repeat_ordinal AS position, r.rvd AS rvd, COUNT(*) AS count
        FROM repeat r
        JOIN tale t ON t.id = r.tale_id
        JOIN tale_family_member fm ON fm.tale_id = t.id
        WHERE fm.family_id = ?{clause}
        GROUP BY r.repeat_ordinal, r.rvd
        ORDER BY r.repeat_ordinal
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
        """
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
        FROM tale t
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
               t.legacy_name AS tale_name
        FROM tale t
        ORDER BY t.id
        """
    )


@st.cache_data(show_spinner=False)
def load_tale_detail(tale_id: int) -> pd.DataFrame:
    return query_df(
        """
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
        FROM tale t
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
        """
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
        JOIN tale t ON t.id = fm.tale_id
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN samples s ON s.id = a.sample_id
        LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id
        WHERE fm.family_id = ?
        ORDER BY t.id
        """,
        params=[family_name],
    )
