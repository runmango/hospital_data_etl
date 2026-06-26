"""LIS discovery helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..config import LisDiscoveryConfig
from ..oracle_client import OracleClient
from .metadata import (
    extract_table_columns,
    list_accessible_owners,
    list_accessible_tables,
    sample_table_rows,
    search_columns_by_keywords,
    search_tables_by_keywords,
)


def _summary_frame(summary: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame([summary])


def discover_lis_tables(client: OracleClient, config: LisDiscoveryConfig) -> dict[str, pd.DataFrame]:
    owners_df = list_accessible_owners(client)
    tables_df = list_accessible_tables(client, limit=1000)
    candidate_tables_df = search_tables_by_keywords(
        client,
        keywords=config.table_keywords,
        excluded_owners=config.excluded_owners,
        limit=1000,
    )
    candidate_columns_df = search_columns_by_keywords(
        client,
        keywords=config.column_keywords,
        excluded_owners=config.excluded_owners,
        limit=1000,
    )
    summary = {
        "owner_count": int(len(owners_df)),
        "accessible_table_count": int(len(tables_df)),
        "candidate_table_count": int(len(candidate_tables_df)),
        "candidate_column_count": int(len(candidate_columns_df)),
    }
    return {
        "owners": owners_df,
        "accessible_tables": tables_df,
        "candidate_tables": candidate_tables_df,
        "candidate_columns": candidate_columns_df,
        "summary": _summary_frame(summary),
    }


def inspect_lis_table(
    client: OracleClient,
    owner: str,
    table_name: str,
    sample_limit: int = 10,
) -> dict[str, pd.DataFrame]:
    columns_df = extract_table_columns(client, owner, table_name)
    sample_df = sample_table_rows(client, owner, table_name, limit=sample_limit)
    summary = {
        "owner": owner.upper(),
        "table_name": table_name.upper(),
        "column_count": int(len(columns_df)),
        "sample_row_count": int(len(sample_df)),
        "sample_limit": int(sample_limit),
    }
    return {
        "columns": columns_df,
        "sample": sample_df,
        "summary": _summary_frame(summary),
    }


def inspect_lis_candidates(client: OracleClient, config: LisDiscoveryConfig) -> dict[str, pd.DataFrame]:
    return discover_lis_tables(client, config)
