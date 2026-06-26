"""CSV export helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_dataframe_to_csv(
    dataframe: pd.DataFrame,
    output_path: str | Path,
    encoding: str = "utf-8-sig",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(path, index=False, encoding=encoding)
    return path

