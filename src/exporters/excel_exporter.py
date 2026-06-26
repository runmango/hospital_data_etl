"""Excel export helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pandas as pd


def _as_dataframe(value) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, Mapping):
        return pd.DataFrame([value])
    return pd.DataFrame(value)


def export_dataframes_to_excel(
    sheets: Mapping[str, object],
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, value in sheets.items():
            dataframe = _as_dataframe(value)
            safe_sheet_name = sheet_name[:31]
            dataframe.to_excel(writer, sheet_name=safe_sheet_name, index=False)

    return path

