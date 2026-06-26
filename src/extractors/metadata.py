"""Oracle metadata extraction helpers."""

from __future__ import annotations

import re
from typing import Iterable

import pandas as pd

from ..oracle_client import OracleClient

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_$#]+$")
DEFAULT_EXCLUDED_OWNERS = (
    "SYS",
    "SYSTEM",
    "XDB",
    "CTXSYS",
    "MDSYS",
    "ORDSYS",
    "OUTLN",
    "WMSYS",
    "DBSNMP",
    "APPQOSSYS",
)


def validate_identifier(value: str, field_name: str = "identifier") -> str:
    if value is None:
        raise ValueError(f"{field_name} is required")
    normalized = value.strip().upper()
    if not normalized or not _IDENTIFIER_RE.match(normalized):
        raise ValueError(
            f"Invalid {field_name}: {value}. Only letters, numbers, underscore, $, and # are allowed."
        )
    return normalized


def validate_limit(value: int | None, default: int = 100, maximum: int = 1000) -> int:
    parsed = default if value is None else int(value)
    if parsed < 1:
        raise ValueError("limit must be greater than 0")
    if parsed > maximum:
        raise ValueError(f"limit must not exceed {maximum}")
    return parsed


def _excluded_owner_clause(excluded_owners: Iterable[str] | None, params: dict) -> str:
    owners = tuple(validate_identifier(owner, "excluded_owner") for owner in (excluded_owners or ()))
    if not owners:
        return ""
    placeholders = []
    for index, owner in enumerate(owners):
        key = f"excluded_owner_{index}"
        params[key] = owner
        placeholders.append(f":{key}")
    return " and owner not in (" + ", ".join(placeholders) + ")"


def _keyword_clause(column_name: str, keywords: Iterable[str], params: dict) -> str:
    clauses = []
    for index, keyword in enumerate(keywords):
        value = str(keyword).strip().upper()
        if not value:
            continue
        key = f"keyword_{index}"
        params[key] = f"%{value}%"
        clauses.append(f"upper({column_name}) like :{key}")
    if not clauses:
        raise ValueError("At least one keyword is required")
    return "(" + " or ".join(clauses) + ")"


def list_accessible_owners(client: OracleClient) -> pd.DataFrame:
    sql = """
select distinct owner
from all_tables
order by owner
"""
    return client.query(sql)


def list_accessible_tables(
    client: OracleClient,
    owner: str | None = None,
    table_name_like: str | None = None,
    limit: int = 100,
) -> pd.DataFrame:
    safe_limit = validate_limit(limit, default=100, maximum=1000)
    params = {"limit": safe_limit, "owner": None, "table_name_like": None}
    if owner:
        params["owner"] = validate_identifier(owner, "owner")
    if table_name_like:
        params["table_name_like"] = str(table_name_like).upper()

    sql = """
select *
from (
  select owner, table_name, num_rows, last_analyzed
  from all_tables
  where (:owner is null or owner = upper(:owner))
    and (:table_name_like is null or table_name like upper(:table_name_like))
  order by owner, table_name
)
where rownum <= :limit
"""
    return client.query(sql, params=params)


def extract_table_columns(client: OracleClient, owner: str, table_name: str) -> pd.DataFrame:
    sql = """
select column_name, data_type, data_length, nullable, column_id
from all_tab_columns
where owner = upper(:owner)
and table_name = upper(:table_name)
order by column_id
"""
    return client.query(
        sql,
        params={
            "owner": validate_identifier(owner, "owner"),
            "table_name": validate_identifier(table_name, "table_name"),
        },
    )


def search_tables_by_keywords(
    client: OracleClient,
    keywords: Iterable[str],
    excluded_owners: Iterable[str] | None = None,
    limit: int = 100,
) -> pd.DataFrame:
    safe_limit = validate_limit(limit, default=100, maximum=1000)
    params = {"limit": safe_limit}
    owner_clause = _excluded_owner_clause(excluded_owners, params)
    keyword_clause = _keyword_clause("table_name", keywords, params)
    sql = f"""
select *
from (
  select owner, table_name, num_rows, last_analyzed
  from all_tables
  where 1 = 1
    {owner_clause}
    and {keyword_clause}
  order by owner, table_name
)
where rownum <= :limit
"""
    return client.query(sql, params=params)


def search_columns_by_keywords(
    client: OracleClient,
    keywords: Iterable[str],
    excluded_owners: Iterable[str] | None = None,
    limit: int = 100,
) -> pd.DataFrame:
    safe_limit = validate_limit(limit, default=100, maximum=1000)
    params = {"limit": safe_limit}
    owner_clause = _excluded_owner_clause(excluded_owners, params)
    keyword_clause = _keyword_clause("column_name", keywords, params)
    sql = f"""
select *
from (
  select owner, table_name, column_name, data_type, data_length, nullable, column_id
  from all_tab_columns
  where 1 = 1
    {owner_clause}
    and {keyword_clause}
  order by owner, table_name, column_name
)
where rownum <= :limit
"""
    return client.query(sql, params=params)


def sample_table_rows(client: OracleClient, owner: str, table_name: str, limit: int = 10) -> pd.DataFrame:
    safe_owner = validate_identifier(owner, "owner")
    safe_table = validate_identifier(table_name, "table_name")
    safe_limit = validate_limit(limit, default=10, maximum=100)
    sql = f"""
select *
from (
  select *
  from {safe_owner}.{safe_table}
)
where rownum <= :limit
"""
    return client.query(sql, params={"limit": safe_limit})


def inspect_his_tables(client: OracleClient) -> dict[str, pd.DataFrame]:
    return {
        "brjbxx_columns": extract_table_columns(client, "JK_WSB", "BRJBXX"),
        "brzdqk_columns": extract_table_columns(client, "JK_WSB", "BRZDQK"),
    }

