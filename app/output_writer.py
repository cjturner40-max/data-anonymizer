from __future__ import annotations

from pathlib import Path

import pandas as pd

from .engine import RunResult


def write_csv(result: RunResult, out_path: Path) -> None:
    if len(result.tables) != 1:
        raise ValueError("CSV output only supports a single template/tab at a time.")
    _, df = next(iter(result.tables.items()))
    df.to_csv(out_path, index=False)


def write_xlsx(result: RunResult, out_path: Path, include_key: bool = False) -> None:
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for name, df in result.tables.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
        for name, df in result.unresolved_tables.items():
            df.to_excel(writer, sheet_name=f"Unresolved - {name}"[:31], index=False)
        if include_key and result.key_table is not None and not result.key_table.empty:
            result.key_table.to_excel(writer, sheet_name="Key", index=False)
