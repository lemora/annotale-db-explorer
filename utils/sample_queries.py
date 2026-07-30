from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.clustering import preferred_strain_label
from utils.db_core import query_df


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
        "LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id"
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
        "LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id"
    )


@st.cache_data(show_spinner=False)
def load_sample_detail(sample_id: int) -> pd.DataFrame:
    return query_df(
        """
        SELECT s.id AS sample_id,
               s.biosample_id,
               s.strain_name,
               s.legacy_strain_name,
               s.geo_tag,
               s.collection_date,
               tx.raw_name AS taxon_name,
               tx.rank AS taxonomy_rank,
               tx.species,
               tx.pathovar,
               tx.ncbi_tax_id
        FROM samples s
        LEFT JOIN taxonomy_compat tx ON tx.id = s.taxon_id
        WHERE s.id = ?
        """,
        params=[int(sample_id)],
    )


@st.cache_data(show_spinner=False)
def load_sample_assemblies(sample_id: int) -> pd.DataFrame:
    return query_df(
        """
        SELECT a.id AS assembly_id,
               a.accession,
               a.version,
               a.accession_type,
               a.replicon_type,
               COUNT(t.id) AS tale_count
        FROM assembly a
        LEFT JOIN tale t ON t.assembly_id = a.id
        WHERE a.sample_id = ?
        GROUP BY a.id, a.accession, a.version, a.accession_type, a.replicon_type
        ORDER BY a.accession, a.id
        """,
        params=[int(sample_id)],
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
def load_sample_ids_with_tales() -> set[int]:
    rows = query_df(
        """
        SELECT DISTINCT a.sample_id AS sample_id
        FROM assembly a
        JOIN tale t ON t.assembly_id = a.id
        WHERE a.sample_id IS NOT NULL
        """
    )
    return set(pd.to_numeric(rows["sample_id"], errors="coerce").dropna().astype(int))
