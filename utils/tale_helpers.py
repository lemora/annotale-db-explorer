from __future__ import annotations

import pandas as pd

from utils.clustering import preferred_strain_label
from utils.taxonomy import abbreviate_taxon_labels, resolved_taxon_labels


def tale_selector_labels(rows: pd.DataFrame) -> pd.Series:
    family = rows["family"].fillna("Unassigned")
    legacy_token = rows["legacy_name"].fillna("").str.split().str[0]
    family_number = pd.Series(
        [
            token[len(name) :]
            if name != "Unassigned" and token.startswith(name) and token[len(name) :].isdigit()
            else ""
            for name, token in zip(family, legacy_token)
        ],
        index=rows.index,
    )
    sample = preferred_strain_label(rows, default="Unknown")
    taxonomy = abbreviate_taxon_labels(resolved_taxon_labels(rows, include_pathovar=True))
    return (
        rows["tale_id"].astype(int).astype(str)
        + " · " + family + family_number.where(family_number == "", " " + family_number)
        + " · " + taxonomy + " · " + sample
    )
