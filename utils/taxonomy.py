import pandas as pd


def legacy_code(series: pd.Series) -> pd.Series:
    cleaned = series.fillna("").str.strip()
    code = cleaned.where(cleaned == "", cleaned.str.split().str[0])
    return code.replace("", pd.NA)


def format_taxon(
    df: pd.DataFrame,
    include_pathovar: bool,
    species_col: str = "species",
    pathovar_col: str = "pathovar",
    taxon_name_col: str = "taxon_name",
) -> pd.Series:
    species = df[species_col].fillna("").str.strip()
    pathovar = df[pathovar_col].fillna("").str.strip()
    taxon_name = df[taxon_name_col].fillna("").str.strip()
    taxon_name = taxon_name.where(taxon_name != "", pd.NA)
    base = species.where(species != "", pd.NA)
    if include_pathovar:
        base = base + " " + pathovar.where(pathovar != "", "")
    return base.fillna(taxon_name)


def build_legacy_taxon_map(
    df: pd.DataFrame,
    include_pathovar: bool,
    legacy_col: str = "legacy_strain_name",
    sample_id_col: str | None = None,
    species_col: str = "species",
    pathovar_col: str = "pathovar",
    taxon_name_col: str = "taxon_name",
) -> dict[str, str]:
    legacy_codes = legacy_code(df[legacy_col])
    taxon = format_taxon(
        df,
        include_pathovar=include_pathovar,
        species_col=species_col,
        pathovar_col=pathovar_col,
        taxon_name_col=taxon_name_col,
    )
    seed_df = df.assign(legacy_code=legacy_codes, taxon=taxon)
    if sample_id_col:
        seed_df = seed_df.drop_duplicates(subset=[sample_id_col])
    seed = (
        seed_df.dropna(subset=["legacy_code", "taxon"])
        .groupby(["legacy_code", "taxon"])
        .size()
        .reset_index(name="count")
        .sort_values(["legacy_code", "count"], ascending=[True, False])
        .groupby("legacy_code")
        .head(1)
    )
    return dict(seed.set_index("legacy_code")["taxon"].to_dict())


def apply_taxon_fallback(
    df: pd.DataFrame,
    include_pathovar: bool,
    legacy_map: dict[str, str] | None = None,
    id_col: str | None = "sample_id",
    legacy_col: str = "legacy_strain_name",
    species_col: str = "species",
    pathovar_col: str = "pathovar",
    taxon_name_col: str = "taxon_name",
) -> pd.Series:
    base_taxon = format_taxon(
        df,
        include_pathovar=include_pathovar,
        species_col=species_col,
        pathovar_col=pathovar_col,
        taxon_name_col=taxon_name_col,
    )
    if id_col:
        has_id = df[id_col].notna()
    else:
        has_id = pd.Series(True, index=df.index)
    result = base_taxon.copy()
    missing_taxon = has_id & result.isna()
    if missing_taxon.any() and legacy_map is not None:
        codes = legacy_code(df[legacy_col])
        result.loc[missing_taxon] = codes.loc[missing_taxon].map(legacy_map)
    result.loc[has_id] = result.loc[has_id].fillna("Unknown")
    return result
