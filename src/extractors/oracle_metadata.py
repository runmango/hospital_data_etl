"""Generic Oracle metadata discovery helpers."""

from __future__ import annotations

import pandas as pd

from ..oracle_client import OracleClient

_EXCLUDED_OWNERS = (
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

RIS_COLUMN_KEYWORDS = (
    "PATIENT",
    "BRXH",
    "ZYH",
    "MZH",
    "EXAM",
    "REPORT",
    "IMAGE",
    "DICOM",
    "STUDY",
    "ACCESSION",
    "JC",
    "BG",
    "JCBW",
    "JCMC",
    "JCSJ",
    "BGSJ",
)


def _limit(value: int, default: int) -> int:
    if value is None:
        return default
    parsed = int(value)
    if parsed < 1:
        raise ValueError("limit must be greater than 0")
    return parsed


def list_accessible_tables(client: OracleClient, limit: int = 100) -> pd.DataFrame:
    sql = """
select *
from (
  select owner, table_name
  from all_tables
  where owner not in (
    'SYS','SYSTEM','XDB','CTXSYS','MDSYS','ORDSYS',
    'OUTLN','WMSYS','DBSNMP','APPQOSSYS'
  )
  order by owner, table_name
)
where rownum <= :limit
"""
    return client.query(sql, params={"limit": _limit(limit, 100)})


def inspect_table_schema(client: OracleClient, owner: str, table_name: str) -> pd.DataFrame:
    sql = """
select column_id, column_name, data_type, data_length, nullable
from all_tab_columns
where owner = upper(:owner)
  and table_name = upper(:table_name)
order by column_id
"""
    dataframe = client.query(sql, params={"owner": owner, "table_name": table_name})
    if not dataframe.empty:
        dataframe.insert(0, "TABLE_NAME", table_name.upper())
        dataframe.insert(0, "OWNER", owner.upper())
    return dataframe


def search_candidate_columns(client: OracleClient, limit: int = 200) -> pd.DataFrame:
    sql = """
select *
from (
  select owner, table_name, column_name, data_type, data_length, nullable
  from all_tab_columns
  where owner not in (
    'SYS','SYSTEM','XDB','CTXSYS','MDSYS','ORDSYS',
    'OUTLN','WMSYS','DBSNMP','APPQOSSYS'
  )
    and (
      upper(column_name) like '%PATIENT%'
      or upper(column_name) like '%BRXH%'
      or upper(column_name) like '%ZYH%'
      or upper(column_name) like '%MZH%'
      or upper(column_name) like '%EXAM%'
      or upper(column_name) like '%REPORT%'
      or upper(column_name) like '%IMAGE%'
      or upper(column_name) like '%DICOM%'
      or upper(column_name) like '%STUDY%'
      or upper(column_name) like '%ACCESSION%'
      or upper(column_name) like '%JC%'
      or upper(column_name) like '%BG%'
      or upper(column_name) like '%JCBW%'
      or upper(column_name) like '%JCMC%'
      or upper(column_name) like '%JCSJ%'
      or upper(column_name) like '%BGSJ%'
    )
  order by owner, table_name, column_name
)
where rownum <= :limit
"""
    return client.query(sql, params={"limit": _limit(limit, 200)})
