from __future__ import annotations

import pandas as pd


def aligned_rvds(alignment_fasta: str) -> pd.DataFrame:
    rows: list[dict[str, int | str]] = []
    tale_id: int | None = None
    sequence: list[str] = []

    def add_sequence() -> None:
        if tale_id is None:
            return
        aligned_sequence = "".join(sequence)
        for offset in range(0, len(aligned_sequence), 2):
            rvd = aligned_sequence[offset : offset + 2]
            if len(rvd) == 2 and rvd != "--":
                rows.append({"tale_id": tale_id, "position": offset // 2 + 1, "rvd": rvd})

    for line in alignment_fasta.splitlines():
        if line.startswith(">"):
            add_sequence()
            tale_id = int(line[1:].split()[0])
            sequence = []
        else:
            sequence.append(line.strip())
    add_sequence()

    return pd.DataFrame(rows, columns=["tale_id", "position", "rvd"])


def aligned_rvd_counts(alignment_fasta: str, excluded_tale_ids: set[int] | None = None) -> pd.DataFrame:
    aligned = aligned_rvds(alignment_fasta)
    if excluded_tale_ids:
        aligned = aligned[~aligned["tale_id"].isin(excluded_tale_ids)]

    if aligned.empty:
        return pd.DataFrame(columns=["position", "rvd", "count"])
    return (
        aligned
        .groupby(["position", "rvd"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
