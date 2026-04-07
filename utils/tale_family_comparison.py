from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from utils.clustering import (
    build_entity_family_presence,
    build_heatmap_long_df,
    build_top_pair_table,
    compute_similarity,
    order_entities,
)
from utils.db import load_crosstab_source, load_tale_set_cluster_source
from utils.taxonomy import (
    abbreviate_taxon_labels,
    apply_taxon_fallback,
    build_legacy_taxon_map,
    filter_incomplete_taxa,
)


@dataclass
class SimilarityViewResult:
    presence: pd.DataFrame
    meta: pd.DataFrame
    similarity_result: object
    order: list[str]
    pair_table: pd.DataFrame
    heatmap_df: pd.DataFrame


@dataclass
class CrosstabViewResult:
    long_df: pd.DataFrame
    families: list[str]
    rows: list[str]
    y_title: str
    value_column: str
    value_title: str
    total_row_count: int


def extract_selected_cell(event_payload: object) -> tuple[str, str] | None:
    if not isinstance(event_payload, dict):
        return None

    def find_selected(value) -> tuple[str, str] | None:
        if isinstance(value, dict):
            left = value.get("entity_y")
            right = value.get("entity_x")
            if left is not None and right is not None:
                return str(left), str(right)
            for nested in value.values():
                found = find_selected(nested)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = find_selected(item)
                if found is not None:
                    return found
        return None

    return find_selected(event_payload.get("selection", {}))


def color_scale_value(series: pd.Series, mode: str) -> pd.Series:
    if mode == "Sqrt":
        return series.pow(0.5)
    return series


@st.cache_data(show_spinner=False)
def build_similarity_view(
    entity_level: str,
    order_mode: str,
    color_scale_mode: str,
    exclude_pseudo: bool,
    include_incomplete_taxa: bool,
    set_aggregation: str,
    include_empty_entities: bool,
) -> SimilarityViewResult:
    source = load_tale_set_cluster_source()
    source = filter_incomplete_taxa(
        source,
        entity_level=entity_level,
        include_incomplete_taxa=include_incomplete_taxa,
    )
    presence, meta = build_entity_family_presence(
        source,
        entity_level=entity_level,
        exclude_pseudo=exclude_pseudo,
        set_aggregation=set_aggregation,
        include_empty_entities=include_empty_entities,
    )
    if not include_empty_entities:
        kept_entities = meta.loc[meta["family_count"] >= 1, "entity"].tolist()
        presence = presence.reindex(kept_entities, fill_value=0)
        meta = meta.loc[meta["entity"].isin(kept_entities)].reset_index(drop=True)

    similarity_result = compute_similarity(presence)
    order = order_entities(
        similarity_result.similarity,
        order_mode=order_mode,
    )
    pair_table = build_top_pair_table(
        similarity_result.similarity,
        similarity_result.shared_counts,
        similarity_result.family_sizes,
    )
    heatmap_df = build_heatmap_long_df(
        similarity_result.similarity,
        similarity_result.shared_counts,
        order=order,
    )
    heatmap_df["color_value"] = color_scale_value(
        heatmap_df["similarity"].astype(float),
        color_scale_mode,
    )
    return SimilarityViewResult(
        presence=presence,
        meta=meta,
        similarity_result=similarity_result,
        order=order,
        pair_table=pair_table,
        heatmap_df=heatmap_df,
    )


@st.cache_data(show_spinner=False)
def build_crosstab_view(
    view: str,
    include_incomplete_taxa: bool,
    show_all_rows: bool,
    top_n: int,
    row_window_index: int,
    row_window_size: int,
    axis_order_mode: str,
    normalize_by_family_size: bool,
) -> CrosstabViewResult:
    raw = load_crosstab_source()
    if raw.empty:
        return CrosstabViewResult(
            long_df=pd.DataFrame(),
            families=[],
            rows=[],
            y_title=view,
            value_column="count",
            value_title="TALE count",
            total_row_count=0,
        )

    if view in {"Species", "Species + Pathovar"}:
        raw = filter_incomplete_taxa(
            raw,
            entity_level=view,
            include_incomplete_taxa=include_incomplete_taxa,
        )

    sample_tax = raw.drop_duplicates(subset=["sample_id"])
    if view != "Strain":
        include_pathovar = view == "Species + Pathovar"
        legacy_map = build_legacy_taxon_map(
            sample_tax,
            include_pathovar=include_pathovar,
            legacy_col="legacy_strain_name",
            sample_id_col="sample_id",
        )
        raw["row_label"] = apply_taxon_fallback(
            raw,
            include_pathovar=include_pathovar,
            legacy_map=legacy_map,
            id_col="sample_id",
            legacy_col="legacy_strain_name",
        )
        raw = raw.groupby(["row_label", "family"]).size().reset_index(name="count")
    else:
        legacy_map = build_legacy_taxon_map(
            sample_tax,
            include_pathovar=True,
            legacy_col="legacy_strain_name",
            sample_id_col="sample_id",
        )
        strain_name = raw["strain_name"].fillna("").str.strip()
        legacy_name = raw["legacy_strain_name"].fillna("").str.strip()
        raw["row_label"] = strain_name.where(strain_name != "", legacy_name)
        raw["row_label"] = raw["row_label"].where(raw["row_label"] != "", "Unknown")
        raw["species_pathovar"] = apply_taxon_fallback(
            raw,
            include_pathovar=True,
            legacy_map=legacy_map,
            id_col="sample_id",
            legacy_col="legacy_strain_name",
        ).fillna("Unknown")
        raw = raw.groupby(["row_label", "family", "species_pathovar"]).size().reset_index(
            name="count"
        )

    raw["row_label"] = abbreviate_taxon_labels(raw["row_label"])
    family_totals = raw.groupby("family")["count"].sum()
    row_totals = raw.groupby("row_label")["count"].sum().sort_values(ascending=False)
    total_row_count = len(row_totals)

    if view == "Strain":
        rows = row_totals.index.tolist()
    elif show_all_rows or view == "Species":
        rows = row_totals.index.tolist()
    else:
        rows = row_totals.head(top_n).index.tolist()

    if axis_order_mode == "Total count":
        families = family_totals.sort_values(ascending=False).index.tolist()
        if show_all_rows or view == "Species":
            rows = row_totals.index.tolist()
    else:
        families = sorted(family_totals.index.tolist())
        rows = sorted(rows)

    if view == "Strain":
        start = max(0, row_window_index * row_window_size)
        stop = start + row_window_size
        rows = rows[start:stop]

    subset = raw[raw["family"].isin(families) & raw["row_label"].isin(rows)]
    pivot = subset.pivot_table(index="row_label", columns="family", values="count", fill_value=0)
    pivot = pivot.reindex(index=rows, columns=families, fill_value=0)

    long_df = pivot.reset_index().melt(
        id_vars="row_label",
        var_name="family",
        value_name="count",
    )

    y_title = "Strain" if view == "Strain" else view
    if view == "Strain":
        row_meta = (
            raw.dropna(subset=["species_pathovar"])
            .groupby(["row_label", "species_pathovar"])["count"]
            .sum()
            .reset_index()
            .sort_values(["row_label", "count"], ascending=[True, False])
            .groupby("row_label")
            .head(1)[["row_label", "species_pathovar"]]
        )
        long_df = long_df.merge(row_meta, on="row_label", how="left")

    if normalize_by_family_size:
        long_df["family_total"] = long_df["family"].map(family_totals).fillna(0.0)
        long_df["family_percent"] = (
            100.0 * long_df["count"] / long_df["family_total"].where(long_df["family_total"] > 0, pd.NA)
        ).fillna(0.0)
        value_column = "family_percent"
        value_title = "Family share (%)"
    else:
        value_column = "count"
        value_title = "TALE count"

    return CrosstabViewResult(
        long_df=long_df,
        families=families,
        rows=rows,
        y_title=y_title,
        value_column=value_column,
        value_title=value_title,
        total_row_count=total_row_count,
    )
