from __future__ import annotations

import re

import pandas as pd

from utils.taxonomy import abbreviate_taxon_labels


def fasta_text(header: str, sequence: str) -> str:
    if not sequence:
        return f">{header}\n"
    wrapped = [sequence[idx : idx + 80] for idx in range(0, len(sequence), 80)]
    return f">{header}\n" + "\n".join(wrapped) + "\n"


def slugify_filename_part(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "").strip())
    collapsed = "_".join(part for part in cleaned.split("_") if part)
    return collapsed or "unknown"


def coalesce_text(*values, default: str = "Unknown") -> str:
    for value in values:
        if pd.notna(value):
            text = str(value).strip()
            if text and text.lower() != "nan":
                return text
    return default


def optional_text(*values) -> str:
    return coalesce_text(*values, default="")


def abbreviated_taxon(species: object, pathovar: object, taxon_name: object) -> str:
    species_text = optional_text(species)
    pathovar_text = optional_text(pathovar)
    if species_text:
        base = species_text if not pathovar_text else f"{species_text} pv. {pathovar_text}"
    else:
        base = optional_text(taxon_name)
    if not base:
        return ""
    return abbreviate_taxon_labels(pd.Series([base])).iloc[0]


def legacy_taxon_label(sample_name: object, legacy_sample_name: object) -> str:
    sample_text = optional_text(sample_name)
    legacy_text = optional_text(legacy_sample_name)
    if not legacy_text:
        return ""
    if sample_text and legacy_text.endswith(sample_text):
        prefix = legacy_text[: -len(sample_text)].strip()
        if prefix:
            return prefix
    if not sample_text:
        return legacy_text
    return ""


def strand_display(strand: object) -> str:
    if pd.isna(strand):
        return "?"
    try:
        strand_int = int(strand)
    except (TypeError, ValueError):
        return str(strand)
    if strand_int > 0:
        return f"+{strand_int}"
    return str(strand_int)


def genomic_location(accession: object, start_pos: object, end_pos: object, strand: object) -> str:
    accession_text = optional_text(accession)
    if not accession_text:
        return ""
    if pd.notna(start_pos) and pd.notna(end_pos):
        return (
            f"[{accession_text}: {int(start_pos)}-{int(end_pos)}:{strand_display(strand)}]"
        )
    return f"[{accession_text}]"


def tale_alias_text(tale_name: object) -> str:
    tale_text = optional_text(tale_name)
    if not tale_text:
        return ""
    parenthetical_parts = re.findall(r"\(([^()]*)\)", tale_text)
    cleaned_parts = [
        part.strip()
        for part in parenthetical_parts
        if part.strip() and part.strip().lower() != "pseudo"
    ]
    return cleaned_parts[0] if cleaned_parts else ""


def stable_tale_class_label(family: object) -> str:
    family_text = optional_text(family)
    if not family_text:
        return "talclassunknown"
    family_token = re.sub(r"[^0-9A-Za-z]+", "_", family_text.strip()).strip("_")
    return family_token or "talclassunknown"


def stable_tale_id_label(tale_id: object, family: object = None) -> str:
    if pd.isna(tale_id):
        tale_id_label = "taleidunknown"
    else:
        try:
            tale_id_token = str(int(tale_id))
        except (TypeError, ValueError):
            tale_id_token = re.sub(r"[^0-9A-Za-z]+", "_", str(tale_id).strip()).strip("_")
        tale_id_label = f"taleid{tale_id_token}" if tale_id_token else "taleidunknown"
    return f"{tale_id_label}_{stable_tale_class_label(family)}"


def stable_tale_download_file_stub(tale_id: object, family: object = None) -> str:
    return f"annotale_tales_{slugify_filename_part(stable_tale_id_label(tale_id, family))}"


def enumerate_stable_tale_labels(
    frame: pd.DataFrame,
    *,
    tale_id_col: str = "tale_id",
    family_col: str = "family",
) -> pd.Series:
    return frame.apply(
        lambda row: stable_tale_id_label(row.get(tale_id_col), row.get(family_col)),
        axis=1,
    )


def build_multi_fasta(frame: pd.DataFrame, *, sort_columns: list[str]) -> str:
    if frame.empty:
        return ""

    ordered = frame.sort_values(sort_columns, na_position="last").copy()
    ordered["download_tale_label"] = enumerate_stable_tale_labels(ordered)

    fasta_entries: list[str] = []
    for row in ordered.itertuples(index=False):
        dna_seq = optional_text(getattr(row, "dna_seq", None))
        if not dna_seq:
            continue
        header = tale_download_header(
            family=getattr(row, "family", None),
            tale_label=getattr(row, "download_tale_label", None),
            species=getattr(row, "species", None),
            pathovar=getattr(row, "pathovar", None),
            taxon_name=getattr(row, "taxon_name", None),
            tale_id=getattr(row, "tale_id", None),
            sample_name=getattr(row, "sample_name", getattr(row, "strain_name", None)),
            legacy_sample_name=getattr(row, "legacy_strain_name", None),
            tale_name=getattr(row, "tale_name", None),
            accession=getattr(row, "accession", None),
            start_pos=getattr(row, "start_pos", None),
            end_pos=getattr(row, "end_pos", None),
            strand=getattr(row, "strand", None),
        )
        fasta_entries.append(fasta_text(header, dna_seq))
    return "".join(fasta_entries)


def tale_download_header(
    *,
    family: object,
    tale_label: object = None,
    species: object = None,
    pathovar: object = None,
    taxon_name: object = None,
    tale_id: object = None,
    sample_name: object,
    legacy_sample_name: object = None,
    tale_name: object,
    accession: object,
    start_pos: object = None,
    end_pos: object = None,
    strand: object = None,
) -> str:
    display_label = optional_text(tale_label) or stable_tale_id_label(tale_id, family)
    taxon_label = legacy_taxon_label(sample_name, legacy_sample_name) or abbreviated_taxon(
        species, pathovar, taxon_name
    )
    strain_label = optional_text(sample_name)
    if not strain_label and not sample_name:
        strain_label = ""
    alias_text = tale_alias_text(tale_name)
    parts = [
        display_label,
        taxon_label,
        strain_label,
        f"({alias_text})" if alias_text else "",
        genomic_location(accession, start_pos, end_pos, strand),
    ]
    parts = [part for part in parts if part]
    return " ".join(parts)
