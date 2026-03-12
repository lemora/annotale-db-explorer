from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "annotale.db"


@st.cache_resource
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=rw", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(query: str, params: Iterable | None = None) -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query(query, conn, params=params)


@st.cache_data(show_spinner=False)
def list_tables() -> list[str]:
    rows = query_df(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
    )
    return rows["name"].tolist()


@st.cache_data(show_spinner=False)
def table_schema(table_name: str) -> pd.DataFrame:
    if table_name not in list_tables():
        raise ValueError(f"Unknown table: {table_name}")
    return query_df(f"PRAGMA table_info({table_name})")


@st.cache_data(show_spinner=False)
def table_counts() -> pd.DataFrame:
    names = list_tables()
    data = []
    conn = get_conn()
    cur = conn.cursor()
    for name in names:
        cur.execute(f"SELECT COUNT(*) FROM {name}")
        count = cur.fetchone()[0]
        data.append({"table": name, "rows": count})
    return pd.DataFrame(data).sort_values("rows", ascending=False)


@st.cache_data(show_spinner=False)
def table_rows(table_name: str, limit: int | None = None) -> pd.DataFrame:
    if table_name not in list_tables():
        raise ValueError(f"Unknown table: {table_name}")
    if limit is None:
        return query_df(f"SELECT * FROM {table_name}")
    return query_df(f"SELECT * FROM {table_name} LIMIT ?", params=[int(limit)])


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
def load_strains() -> pd.DataFrame:
    df = query_df(
        "SELECT s.id AS id, "
        "s.biosample_id AS biosample_id, "
        "s.strain_name AS strain_name, "
        "s.legacy_strain_name AS legacy_strain_name, "
        "tx.species AS species, "
        "tx.pathovar AS pathovar, "
        "tx.raw_name AS taxon_name, "
        "s.geo_tag AS geo_tag, "
        "tx.ncbi_tax_id AS tax_id "
        "FROM samples s "
        "LEFT JOIN taxonomy tx ON tx.id = s.taxon_id"
    )
    strain_name = df["strain_name"].fillna("").str.strip()
    legacy_name = df["legacy_strain_name"].fillna("").str.strip()

    def last_token(series: pd.Series) -> pd.Series:
        return series.str.split().str[-1]

    strain_last = last_token(strain_name)
    legacy_last = last_token(legacy_name)
    df["name"] = strain_last.where(strain_name != "", legacy_last)
    return df[
        [
            "id",
            "biosample_id",
            "name",
            "species",
            "pathovar",
            "taxon_name",
            "geo_tag",
            "tax_id",
            "strain_name",
            "legacy_strain_name",
        ]
    ]


@st.cache_data(show_spinner=False)
def load_repeats() -> pd.DataFrame:
    return query_df(
        "SELECT tale_id, repeat_ordinal, rvd, rvd_pos, rvd_len, masked_seq_1, masked_seq_2 "
        "FROM repeat"
    )


@st.cache_data(show_spinner=False)
def load_sample_taxonomy() -> pd.DataFrame:
    return query_df(
        "SELECT s.id AS sample_id, s.legacy_strain_name, tx.species, tx.pathovar, tx.raw_name AS taxon_name "
        "FROM samples s "
        "LEFT JOIN taxonomy tx ON tx.id = s.taxon_id"
    )


@st.cache_data(show_spinner=False)
def load_repeat_positions() -> pd.DataFrame:
    return query_df(
        """
        SELECT repeat_ordinal AS position, rvd, tale_id
        FROM repeat
        """
    )


@st.cache_data(show_spinner=False)
def load_taxonomy_comparison_source() -> pd.DataFrame:
    return query_df(
        """
        SELECT s.id AS sample_id,
               s.legacy_strain_name,
               tx.ncbi_tax_id,
               tx.raw_name AS taxon_name,
               tx.species,
               tx.pathovar,
               CASE
                 WHEN s.legacy_strain_name IS NULL OR TRIM(s.legacy_strain_name) = '' THEN NULL
                 WHEN instr(TRIM(s.legacy_strain_name), ' ') > 0
                   THEN substr(TRIM(s.legacy_strain_name), 1, instr(TRIM(s.legacy_strain_name), ' ') - 1)
                 ELSE TRIM(s.legacy_strain_name)
               END AS legacy_code
        FROM samples s
        LEFT JOIN taxonomy tx ON tx.id = s.taxon_id
        """
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
        LEFT JOIN taxonomy tx ON tx.id = s.taxon_id
        """
    )


@st.cache_data(show_spinner=False)
def load_sample_map_source() -> pd.DataFrame:
    return query_df(
        """
        SELECT s.id AS sample_id,
               s.legacy_strain_name,
               s.strain_name,
               s.geo_tag,
               s.collection_date,
               CASE
                 WHEN length(trim(s.collection_date)) = 4
                      AND trim(s.collection_date) GLOB '[0-9][0-9][0-9][0-9]'
                   THEN CAST(substr(trim(s.collection_date), 1, 4) AS INTEGER)
                 WHEN trim(s.collection_date) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
                   THEN CAST(substr(trim(s.collection_date), 1, 4) AS INTEGER)
                 WHEN trim(s.collection_date) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                   THEN CAST(substr(trim(s.collection_date), 1, 4) AS INTEGER)
                 ELSE NULL
               END AS year
        FROM samples s
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
        LEFT JOIN taxonomy tx ON tx.id = s.taxon_id
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
               a.replicon_type
        FROM tale t
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN tale_family_member fm ON fm.tale_id = t.id
        WHERE a.sample_id = ?
        ORDER BY
            CASE WHEN t.start_pos IS NULL THEN 1 ELSE 0 END,
            a.accession,
            t.start_pos,
            t.id
        """,
        params=[int(strain_id)],
    )
