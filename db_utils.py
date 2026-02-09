from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parent / "annotale.db"


@st.cache_resource
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
