from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.db_core import db_fingerprint, get_conn, query_df, quote_identifier


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
    counts: list[dict[str, int | str]] = []
    cur = get_conn().cursor()
    for name in list_tables():
        cur.execute(f"SELECT COUNT(*) FROM {name}")
        counts.append({"table": name, "rows": int(cur.fetchone()[0])})
    return pd.DataFrame(counts).sort_values("rows", ascending=False)


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


def foreign_key_relations() -> pd.DataFrame:
    return _foreign_key_relations(db_fingerprint())


@st.cache_data(show_spinner=False)
def _foreign_key_relations(fingerprint: tuple[int, int]) -> pd.DataFrame:
    rows = []
    conn = get_conn()
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
