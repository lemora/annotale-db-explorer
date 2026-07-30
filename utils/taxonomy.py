import pandas as pd


def normalize_taxon_text(series: pd.Series) -> pd.Series:
    normalized = series.fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    return normalized.replace("", pd.NA)


def normalized_species_text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()


def normalized_pathovar_text(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.replace(r"^(pv\.|pathovar)\s+", "", regex=True, case=False)
    )


def format_taxon(
    df: pd.DataFrame,
    include_pathovar: bool,
    species_col: str = "species",
    pathovar_col: str = "pathovar",
    taxon_name_col: str = "taxon_name",
) -> pd.Series:
    species = normalize_taxon_text(df[species_col])
    pathovar = normalize_taxon_text(
        df[pathovar_col]
        .fillna("")
        .astype(str)
        .str.replace(r"^(pv\.|pathovar)\s+", "", regex=True, case=False)
    )
    taxon_name = normalize_taxon_text(df[taxon_name_col])
    base = species.where(species != "", pd.NA)
    if include_pathovar:
        pathovar = pathovar.fillna("")
        base = base + pathovar.where(pathovar == "", " pv. " + pathovar)
    return base.fillna(taxon_name)


def abbreviate_taxon_labels(series: pd.Series) -> pd.Series:
    normalized = normalize_taxon_text(series)
    return normalized.str.replace("Xanthomonas", "X.", regex=False)


def resolved_taxon_labels(
    df: pd.DataFrame,
    include_pathovar: bool,
    *,
    abbreviate: bool = False,
    species_col: str = "species",
    pathovar_col: str = "pathovar",
    taxon_name_col: str = "taxon_name",
) -> pd.Series:
    labels = format_taxon(
        df,
        include_pathovar=include_pathovar,
        species_col=species_col,
        pathovar_col=pathovar_col,
        taxon_name_col=taxon_name_col,
    ).fillna("Unknown")
    if abbreviate:
        labels = abbreviate_taxon_labels(labels)
    return labels


def filter_incomplete_taxa(
    df: pd.DataFrame,
    entity_level: str,
    include_incomplete_taxa: bool,
    species_col: str = "species",
    pathovar_col: str = "pathovar",
) -> pd.DataFrame:
    if include_incomplete_taxa:
        return df
    if entity_level not in {"Species", "Species + Pathovar"}:
        return df

    filtered = df.copy()
    species = normalized_species_text(filtered[species_col])
    valid_species = (species != "") & ~species.str.contains(
        r"(?:^|\s)sp\.?$",
        case=False,
        regex=True,
    )
    filtered = filtered.loc[valid_species].copy()

    if entity_level == "Species + Pathovar":
        pathovar = normalized_pathovar_text(filtered[pathovar_col])
        valid_pathovar = (pathovar != "") & ~pathovar.str.fullmatch(r"unknown", case=False)
        filtered = filtered.loc[valid_pathovar].copy()

    return filtered
