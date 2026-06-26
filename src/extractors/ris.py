"""RIS extraction helpers."""

from __future__ import annotations

import re

import pandas as pd

from ..oracle_client import OracleClient

RIS_DIMAGE_COLUMNS = {
    "ID": "影像记录ID",
    "SERIALNO": "影像序列号",
    "STOREPATH": "存储根路径",
    "PATHDETAIL": "详细路径",
    "IMAGEF": "图像文件名",
}


def _as_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def build_image_path(storepath, pathdetail, imagef) -> str:
    parts = [_as_text(storepath), _as_text(pathdetail), _as_text(imagef)]
    parts = [part for part in parts if part]
    if not parts:
        return ""

    separator = "\\" if any("\\" in part for part in parts) else "/"
    first = parts[0]
    prefix = ""
    first_body = first

    if separator == "\\":
        if re.match(r"^[A-Za-z]:", first):
            prefix = first[:2]
            first_body = first[2:]
        elif first.startswith(("\\\\", "//")):
            prefix = "\\\\"
    elif first.startswith("/"):
        prefix = "/"

    segments = []
    for index, part in enumerate(parts):
        source = first_body if index == 0 else part
        for segment in re.split(r"[\\/]+", source.strip("\\/")):
            if segment:
                segments.append(segment)

    joined = separator.join(segments)
    if not prefix:
        return joined
    if prefix.endswith(separator):
        return prefix + joined
    return prefix + (separator + joined if joined else "")


def extract_ris_dimage(client: OracleClient, limit: int = 1000) -> pd.DataFrame:
    sql = """
select *
from (
  select
    ID,
    SERIALNO,
    STOREPATH,
    PATHDETAIL,
    IMAGEF
  from JK_WSB.RIS_DIMAGE
  order by ID
)
where rownum <= :limit
"""
    dataframe = client.query(sql, params={"limit": int(limit)})
    if dataframe.empty:
        return pd.DataFrame(columns=[*RIS_DIMAGE_COLUMNS.values(), "完整影像路径"])

    # Oracle/pandas may return uppercase column names; keep lookup defensive.
    normalized = {column.upper(): column for column in dataframe.columns}
    output = pd.DataFrame()
    for source_column, chinese_name in RIS_DIMAGE_COLUMNS.items():
        actual_column = normalized.get(source_column)
        output[chinese_name] = dataframe[actual_column] if actual_column else ""

    output["完整影像路径"] = [
        build_image_path(storepath, pathdetail, imagef)
        for storepath, pathdetail, imagef in zip(
            output["存储根路径"],
            output["详细路径"],
            output["图像文件名"],
        )
    ]
    return output


