from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable

import pandas as pd
import streamlit as st

from utils.clustering import preferred_strain_label

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "annotale.db"


def db_fingerprint() -> tuple[int, int]:
    stat = DB_PATH.stat()
    return stat.st_mtime_ns, stat.st_size


def get_conn() -> sqlite3.Connection:
    return _get_conn(db_fingerprint())


@st.cache_resource
def _get_conn(fingerprint: tuple[int, int]) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=rw", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(query: str, params: Iterable | None = None) -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query(query, conn, params=params)


def list_tables() -> list[str]:
    return _list_tables(db_fingerprint())


@st.cache_data(show_spinner=False)
def _list_tables(fingerprint: tuple[int, int]) -> list[str]:
    rows = query_df(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
    )
    return rows["name"].tolist()


def table_schema(table_name: str) -> pd.DataFrame:
    return _table_schema(table_name, db_fingerprint())


@st.cache_data(show_spinner=False)
def _table_schema(table_name: str, fingerprint: tuple[int, int]) -> pd.DataFrame:
    if table_name not in list_tables():
        raise ValueError(f"Unknown table: {table_name}")
    return query_df(f"PRAGMA table_info({table_name})")


def table_counts() -> pd.DataFrame:
    return _table_counts(db_fingerprint())


@st.cache_data(show_spinner=False)
def _table_counts(fingerprint: tuple[int, int]) -> pd.DataFrame:
    names = list_tables()
    data = []
    conn = get_conn()
    cur = conn.cursor()
    for name in names:
        cur.execute(f"SELECT COUNT(*) FROM {name}")
        count = cur.fetchone()[0]
        data.append({"table": name, "rows": count})
    return pd.DataFrame(data).sort_values("rows", ascending=False)


def table_rows(table_name: str, limit: int | None = None) -> pd.DataFrame:
    return _table_rows(table_name, limit, db_fingerprint())


@st.cache_data(show_spinner=False)
def _table_rows(
    table_name: str, limit: int | None, fingerprint: tuple[int, int]
) -> pd.DataFrame:
    if table_name not in list_tables():
        raise ValueError(f"Unknown table: {table_name}")
    if limit is None:
        return query_df(f"SELECT * FROM {table_name}")
    return query_df(f"SELECT * FROM {table_name} LIMIT ?", params=[int(limit)])


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def foreign_key_relations() -> pd.DataFrame:
    return _foreign_key_relations(db_fingerprint())


@st.cache_data(show_spinner=False)
def _foreign_key_relations(fingerprint: tuple[int, int]) -> pd.DataFrame:
    conn = get_conn()
    rows = []
    for table in list_tables():
        fk_rows = conn.execute(f"PRAGMA foreign_key_list({quote_identifier(table)})").fetchall()
        for fk in fk_rows:
            rows.append(
                {
                    "source_table": table,
                    "source_column": fk["from"],
                    "target_table": fk["table"],
                    "target_column": fk["to"],
                    "on_update": fk["on_update"],
                    "on_delete": fk["on_delete"],
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "source_table",
            "source_column",
            "target_table",
            "target_column",
            "on_update",
            "on_delete",
        ],
    )


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
    df["name"] = preferred_strain_label(df).str.split().str[-1]
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
def load_sample_taxonomy() -> pd.DataFrame:
    return query_df(
        "SELECT s.id AS sample_id, s.legacy_strain_name, tx.species, tx.pathovar, tx.raw_name AS taxon_name "
        "FROM samples s "
        "LEFT JOIN taxonomy tx ON tx.id = s.taxon_id"
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
        LEFT JOIN taxonomy tx ON tx.id = s.taxon_id
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
        LEFT JOIN taxonomy tx ON tx.id = s.taxon_id
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
               tx.id AS taxonomy_id,
               tx.ncbi_tax_id,
               tx.rank AS taxonomy_rank,
               tx.raw_name AS taxon_name,
               tx.species,
               tx.pathovar
        FROM tale t
        LEFT JOIN tale_family_member fm ON fm.tale_id = t.id
        LEFT JOIN assembly a ON a.id = t.assembly_id
        LEFT JOIN samples s ON s.id = a.sample_id
        LEFT JOIN taxonomy tx ON tx.id = s.taxon_id
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
        LEFT JOIN taxonomy tx ON tx.id = s.taxon_id
        WHERE fm.family_id = ?
        ORDER BY t.id
        """,
        params=[family_name],
    )
