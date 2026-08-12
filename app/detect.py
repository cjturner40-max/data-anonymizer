from __future__ import annotations

from pathlib import Path

import pandas as pd


def detect_columns(file_path: Path) -> list[str]:
    """Read just the header row of a CSV or Excel file and return its column names."""
    file_path = Path(file_path)
    if file_path.suffix.lower() == ".csv":
        df = pd.read_csv(file_path, nrows=0, encoding="utf-8-sig")
    else:
        df = pd.read_excel(file_path, nrows=0)
    return list(df.columns)
