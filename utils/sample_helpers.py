from __future__ import annotations

import pandas as pd

from utils.clustering import preferred_strain_label
from utils.taxonomy import normalized_pathovar_text, normalize_taxon_text

INVALID_COUNTRY_LABELS = {"unknown", "missing", "-"}
UNKNOWN_COUNTRY = "Unknown"


def add_species_pathovar_columns(rows: pd.DataFrame) -> pd.DataFrame:
    enriched = rows.copy()
    enriched["species_display"] = normalize_taxon_text(enriched["species"]).fillna(
        UNKNOWN_COUNTRY
    )
    enriched["pathovar_display"] = normalized_pathovar_text(enriched["pathovar"]).replace(
        "", UNKNOWN_COUNTRY
    )
    enriched["species_pathovar"] = (
        enriched["species_display"] + " " + enriched["pathovar_display"]
    ).where(enriched["pathovar_display"] != UNKNOWN_COUNTRY, enriched["species_display"])
    return enriched


def build_sample_selector_rows(rows: pd.DataFrame, *, id_column: str = "id") -> pd.DataFrame:
    selector_rows = rows.copy()
    if id_column != "sample_id":
        selector_rows = selector_rows.rename(columns={id_column: "sample_id"})
    selector_rows["sample_display"] = preferred_strain_label(
        selector_rows, default=UNKNOWN_COUNTRY
    ).fillna(UNKNOWN_COUNTRY)
    selector_rows = add_species_pathovar_columns(selector_rows)
    return selector_rows.sort_values(["sample_id"]).reset_index(drop=True)


def format_sample_label(row: pd.Series) -> str:
    strain_name = str(row.get("strain_name") or "").strip()
    if not strain_name or strain_name.lower() == "nan":
        strain_name = str(row.get("legacy_strain_name") or "").strip()
    if not strain_name or strain_name.lower() == "nan":
        strain_name = "unknown strain"

    biosample_id = str(row.get("biosample_id") or "").strip()
    if biosample_id and biosample_id.lower() != "nan":
        return f"{strain_name} | {biosample_id}"
    return f"{strain_name} | unknown biosample id"


def parse_country(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned or cleaned.lower() in INVALID_COUNTRY_LABELS:
        return None
    if ":" in cleaned:
        cleaned = cleaned.split(":", 1)[0].strip()
    if "," in cleaned:
        cleaned = cleaned.split(",", 1)[0].strip()
    if not cleaned or cleaned.lower() in INVALID_COUNTRY_LABELS:
        return None
    return cleaned


def country_or_unknown(value: str | None) -> str:
    return parse_country(value) or UNKNOWN_COUNTRY
