from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "annotale.db"


def db_fingerprint() -> tuple[int, int]:
    stat = DB_PATH.stat()
    return stat.st_mtime_ns, stat.st_size


def get_conn() -> sqlite3.Connection:
    return _get_conn(db_fingerprint())


@st.cache_resource
def _get_conn(fingerprint: tuple[int, int]) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TEMP VIEW taxonomy_compat AS
        WITH RECURSIVE lineage(taxon_id, id, ncbi_tax_id, rank, name, parent_id) AS (
            SELECT id, id, ncbi_tax_id, rank, name, parent_id FROM taxonomy
            UNION ALL
            SELECT lineage.taxon_id, t.id, t.ncbi_tax_id, t.rank, t.name, t.parent_id
            FROM lineage JOIN taxonomy t ON t.id = lineage.parent_id
        ), rollup AS (
            SELECT taxon_id AS id,
                   MAX(CASE WHEN id = taxon_id THEN ncbi_tax_id END) AS ncbi_tax_id,
                   MAX(CASE WHEN id = taxon_id THEN rank END) AS rank,
                   MAX(CASE WHEN id = taxon_id THEN name END) AS raw_name,
                   MAX(CASE WHEN rank = 'genus' THEN name END) AS genus,
                   MAX(CASE WHEN rank = 'species' THEN name END) AS species_name,
                   MAX(CASE WHEN rank = 'species group' THEN name END) AS species_group_name,
                   MAX(CASE WHEN rank = 'pathovar' THEN name END) AS pathovar
            FROM lineage
            GROUP BY taxon_id
        )
        SELECT id, ncbi_tax_id, rank, raw_name,
               CASE WHEN COALESCE(species_name, species_group_name) IS NULL THEN NULL
                    WHEN genus IS NULL OR COALESCE(species_name, replace(species_group_name, ' group', '')) LIKE genus || ' %'
                      THEN COALESCE(species_name, replace(species_group_name, ' group', ''))
                    ELSE genus || ' ' || COALESCE(species_name, replace(species_group_name, ' group', '')) END AS species,
               pathovar
        FROM rollup
        """
    )
    return conn


def query_df(query: str, params: Iterable | None = None) -> pd.DataFrame:
    return pd.read_sql_query(query, get_conn(), params=params)


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
