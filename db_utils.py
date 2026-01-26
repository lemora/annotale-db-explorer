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
        "SELECT name, member_count, tree_newick FROM family ORDER BY member_count DESC"
    )


@st.cache_data(show_spinner=False)
def load_family_members() -> pd.DataFrame:
    return query_df("SELECT family_id, tale_id FROM family_member")


@st.cache_data(show_spinner=False)
def load_tales() -> pd.DataFrame:
    return query_df(
        "SELECT id, name, name_short, name_suffix, is_pseudo, strain_id, accession_id, "
        "start_pos, end_pos, strand, is_new, dna_seq, protein_seq FROM tale"
    )


@st.cache_data(show_spinner=False)
def load_strains() -> pd.DataFrame:
    return query_df(
        "SELECT id, name, species, pathovar, isolate, geo_tag, tax_id FROM strain"
    )


@st.cache_data(show_spinner=False)
def load_repeats() -> pd.DataFrame:
    return query_df(
        "SELECT tale_id, repeat_ordinal, rvd, rvd_pos, rvd_len, masked_seq_1, masked_seq_2 "
        "FROM repeat"
    )

