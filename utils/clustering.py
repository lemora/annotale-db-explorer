from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from utils.taxonomy import (
    abbreviate_taxon_labels,
    apply_taxon_fallback,
    build_legacy_taxon_map,
)


ENTITY_LEVELS = [
    "Species",
    "Species + Pathovar",
]

SET_AGGREGATION_OPTIONS = [
    "Union (any strain)",
    "Majority of strains (>=50%)",
    "Core (all strains)",
]


def preferred_strain_label(df: pd.DataFrame, default: str | None = None) -> pd.Series:
    strain_name = df["strain_name"].fillna("").astype(str).str.strip()
    legacy_name = df["legacy_strain_name"].fillna("").astype(str).str.strip()
    label = strain_name.where(strain_name != "", legacy_name)
    fallback = pd.NA if default is None else default
    return label.where(label != "", fallback)


def strain_label(df: pd.DataFrame) -> pd.Series:
    return preferred_strain_label(df, default="Unknown strain")


def assembly_label(df: pd.DataFrame) -> pd.Series:
    accession = df["accession"].fillna("").astype(str).str.strip()
    assembly_id = df["assembly_id"].fillna(-1).astype(int).astype(str)
    replicon_type = df["replicon_type"].fillna("").astype(str).str.strip()
    base = accession.where(accession != "", "assembly " + assembly_id)
    suffix = replicon_type.where(replicon_type != "", "unknown replicon")
    strain = strain_label(df)
    return base + " (" + suffix + ")" + " | " + strain


def entity_labels(source: pd.DataFrame, entity_level: str) -> pd.Series:
    if entity_level == "Strain":
        return strain_label(source)
    if entity_level == "Assembly / Replicon":
        return assembly_label(source)

    sample_tax = source.drop_duplicates(subset=["sample_id"])
    include_pathovar = entity_level == "Species + Pathovar"
    legacy_map = build_legacy_taxon_map(
        sample_tax,
        include_pathovar=include_pathovar,
        legacy_col="legacy_strain_name",
        sample_id_col="sample_id",
    )
    labels = apply_taxon_fallback(
        source,
        include_pathovar=include_pathovar,
        legacy_map=legacy_map,
        id_col="sample_id",
        legacy_col="legacy_strain_name",
    )
    return abbreviate_taxon_labels(labels).fillna("Unknown")


def build_entity_family_presence(
    source: pd.DataFrame,
    entity_level: str,
    exclude_pseudo: bool = True,
    set_aggregation: str = "Union (any strain)",
    include_empty_entities: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    filtered = source.copy()
    if exclude_pseudo:
        filtered = filtered[filtered["is_pseudo"].fillna(0) == 0]

    filtered["entity"] = entity_labels(filtered, entity_level)
    filtered["family"] = filtered["family"].fillna("Unknown")
    filtered = filtered.dropna(subset=["entity", "family"])
    all_entities = sorted(filtered["entity"].dropna().unique().tolist())

    if entity_level in {"Species", "Species + Pathovar"}:
        filtered["strain_entity"] = strain_label(filtered)
        entity_strains = (
            filtered[["entity", "strain_entity"]]
            .drop_duplicates()
            .groupby("entity")
            .size()
            .rename("strain_count")
            .reset_index()
        )
        family_support = (
            filtered[["entity", "strain_entity", "family"]]
            .drop_duplicates()
            .groupby(["entity", "family"])
            .size()
            .rename("supporting_strains")
            .reset_index()
            .merge(entity_strains, on="entity", how="left")
        )
        if set_aggregation == "Core (all strains)":
            included = family_support["supporting_strains"] >= family_support["strain_count"]
        elif set_aggregation == "Majority of strains (>=50%)":
            included = (
                family_support["supporting_strains"]
                >= 0.5 * family_support["strain_count"]
            )
        else:
            included = family_support["supporting_strains"] >= 1
        family_support = family_support.loc[included, ["entity", "family"]]
        presence = (
            family_support.assign(value=1)
            .pivot(index="entity", columns="family", values="value")
            .fillna(0)
            .astype(int)
        )
    else:
        presence = (
            filtered[["entity", "family"]]
            .drop_duplicates()
            .assign(value=1)
            .pivot(index="entity", columns="family", values="value")
            .fillna(0)
            .astype(int)
        )

    meta = filtered.groupby("entity").agg(tale_count=("tale_id", "nunique")).reset_index()
    family_count = (
        presence.sum(axis=1).rename("family_count").reset_index().rename(columns={"index": "entity"})
    )
    meta = meta.merge(family_count, on="entity", how="left").fillna({"family_count": 0})
    meta["family_count"] = meta["family_count"].astype(int)

    if include_empty_entities and all_entities:
        meta = (
            pd.DataFrame({"entity": all_entities})
            .merge(meta, on="entity", how="left")
            .fillna({"tale_count": 0, "family_count": 0})
        )
        meta["tale_count"] = meta["tale_count"].astype(int)
        meta["family_count"] = meta["family_count"].astype(int)
        presence = presence.reindex(all_entities, fill_value=0)
    return presence, meta


@dataclass
class SimilarityResult:
    similarity: pd.DataFrame
    shared_counts: pd.DataFrame
    family_sizes: pd.Series


def compute_similarity(presence: pd.DataFrame) -> SimilarityResult:
    if presence.empty:
        empty = pd.DataFrame(index=presence.index, columns=presence.index, dtype=float)
        return SimilarityResult(empty, empty, pd.Series(dtype=float))

    matrix = presence.to_numpy(dtype=np.int16)
    shared_counts = matrix @ matrix.T
    family_sizes = matrix.sum(axis=1).astype(float)

    union = family_sizes[:, None] + family_sizes[None, :] - shared_counts
    similarity = np.divide(
        shared_counts,
        union,
        out=np.zeros_like(shared_counts, dtype=float),
        where=union > 0,
    )

    np.fill_diagonal(similarity, 1.0)
    shared_df = pd.DataFrame(shared_counts, index=presence.index, columns=presence.index)
    sim_df = pd.DataFrame(similarity, index=presence.index, columns=presence.index)
    size_series = pd.Series(family_sizes, index=presence.index, name="family_count")
    return SimilarityResult(sim_df, shared_df, size_series)


def hierarchical_average_linkage_order(similarity: pd.DataFrame) -> list[str]:
    labels = similarity.index.tolist()
    if len(labels) <= 1:
        return labels

    distance = 1.0 - similarity.to_numpy(dtype=float)
    clusters: dict[int, list[int]] = {i: [i] for i in range(len(labels))}
    active = list(clusters.keys())
    next_cluster_id = len(labels)

    while len(active) > 1:
        best_pair: tuple[int, int] | None = None
        best_distance: float | None = None
        for i, left in enumerate(active[:-1]):
            left_members = clusters[left]
            for right in active[i + 1 :]:
                right_members = clusters[right]
                current_distance = float(
                    distance[np.ix_(left_members, right_members)].mean()
                )
                if best_distance is None or current_distance < best_distance:
                    best_distance = current_distance
                    best_pair = (left, right)
        if best_pair is None:
            break
        left, right = best_pair
        merged = clusters[left] + clusters[right]
        active = [cluster for cluster in active if cluster not in (left, right)]
        clusters[next_cluster_id] = merged
        active.append(next_cluster_id)
        next_cluster_id += 1

    final_cluster = clusters[active[0]]
    return [labels[index] for index in final_cluster]


def order_entities(
    similarity: pd.DataFrame,
    order_mode: str,
) -> list[str]:
    if order_mode == "Hierarchical clustering":
        return hierarchical_average_linkage_order(similarity)
    return sorted(similarity.index.tolist())


def build_heatmap_long_df(
    similarity: pd.DataFrame,
    shared_counts: pd.DataFrame,
    order: list[str],
) -> pd.DataFrame:
    if not order:
        return pd.DataFrame()

    sim_long = (
        similarity.loc[order, order]
        .rename_axis(index="entity_y", columns="entity_x")
        .stack()
        .reset_index(name="similarity")
    )
    shared_long = (
        shared_counts.loc[order, order]
        .rename_axis(index="entity_y", columns="entity_x")
        .stack()
        .reset_index(name="shared_families")
    )
    plot_df = sim_long.merge(shared_long, on=["entity_y", "entity_x"], how="left")
    plot_df["is_diagonal"] = plot_df["entity_x"] == plot_df["entity_y"]
    return plot_df


def build_top_pair_table(
    similarity: pd.DataFrame,
    shared_counts: pd.DataFrame,
    family_sizes: pd.Series,
    limit: int = 25,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    labels = sorted(similarity.index.tolist())
    for left_idx, left in enumerate(labels[:-1]):
        for right in labels[left_idx + 1 :]:
            shared = int(shared_counts.loc[left, right])
            left_size = int(family_sizes.loc[left])
            right_size = int(family_sizes.loc[right])
            union = left_size + right_size - shared
            rows.append(
                {
                    "Entity A": left,
                    "Entity B": right,
                    "Similarity": float(similarity.loc[left, right]),
                    "Shared families": shared,
                    "Union families": union,
                    "A family count": left_size,
                    "B family count": right_size,
                    "A contained in B": shared / left_size if left_size else 0.0,
                    "B contained in A": shared / right_size if right_size else 0.0,
                }
            )
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values(
            ["Similarity", "Shared families", "Union families", "Entity A", "Entity B"],
            ascending=[False, False, False, True, True],
        )
        .head(limit)
        .reset_index(drop=True)
    )


def shared_family_lists(
    presence: pd.DataFrame,
    left_entity: str,
    right_entity: str,
) -> tuple[list[str], list[str], list[str]]:
    left_presence = presence.loc[left_entity].astype(bool)
    right_presence = presence.loc[right_entity].astype(bool)
    families = presence.columns
    shared = families[left_presence & right_presence].tolist()
    left_only = families[left_presence & ~right_presence].tolist()
    right_only = families[right_presence & ~left_presence].tolist()
    return shared, left_only, right_only


def classical_mds_projection(
    similarity: pd.DataFrame,
    family_sizes: pd.Series,
) -> pd.DataFrame:
    if similarity.empty:
        return pd.DataFrame(columns=["entity", "x", "y", "family_count"])

    labels = similarity.index.tolist()
    if len(labels) == 1:
        return pd.DataFrame(
            {
                "entity": labels,
                "x": [0.0],
                "y": [0.0],
                "family_count": [float(family_sizes.iloc[0])],
            }
        )

    distance = 1.0 - similarity.to_numpy(dtype=float)
    squared = distance ** 2
    n = squared.shape[0]
    centering = np.eye(n) - np.ones((n, n)) / n
    gram = -0.5 * centering @ squared @ centering

    eigenvalues, eigenvectors = np.linalg.eigh(gram)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]

    positive = np.clip(eigenvalues[:2], a_min=0.0, a_max=None)
    coords = eigenvectors[:, :2] * np.sqrt(positive)
    if coords.shape[1] < 2:
        coords = np.pad(coords, ((0, 0), (0, 2 - coords.shape[1])))

    return pd.DataFrame(
        {
            "entity": labels,
            "x": coords[:, 0],
            "y": coords[:, 1],
            "family_count": family_sizes.reindex(labels).astype(float).to_numpy(),
        }
    )
