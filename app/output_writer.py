from __future__ import annotations

from pathlib import Path

import pandas as pd

from .engine import RunResult


def needs_secondary_file(result: RunResult, include_key: bool) -> bool:
    """True if there's anything that must stay out of the clean/matched output --
    unresolved rows (unedited, so they carry real identifying info) and/or a
    requested key. The clean output file should never contain identifying
    information, so anything sensitive gets segregated into a second file."""
    has_key = include_key and result.key_table is not None and not result.key_table.empty
    return bool(result.unresolved_tables) or has_key


def write_csv(result: RunResult, out_path: Path) -> None:
    """Writes the clean, matched/anonymized output only."""
    if len(result.tables) != 1:
        raise ValueError("CSV output only supports a single template/tab at a time.")
    _, df = next(iter(result.tables.items()))
    df.to_csv(out_path, index=False)


def write_csv_key(result: RunResult, out_path: Path) -> None:
    """A CSV run is always a single, fully-matched template (no cross-report
    matching happens), so there's never anything unresolved to write here --
    only the key mapping, when requested."""
    if result.key_table is None or result.key_table.empty:
        raise ValueError("No key available for this run.")
    result.key_table.to_csv(out_path, index=False)


def write_xlsx(result: RunResult, out_path: Path) -> None:
    """Writes the clean, matched/anonymized output only -- this file never contains
    identifying information, so it's safe to hand off for analysis on its own."""
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for name, df in result.tables.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)


def write_xlsx_secondary(result: RunResult, out_path: Path, include_key: bool) -> None:
    """Writes whatever needs to stay separate from the clean output: unresolved rows
    and/or the key mapping. Only call when needs_secondary_file() is True."""
    has_key = include_key and result.key_table is not None and not result.key_table.empty
    if not result.unresolved_tables and not has_key:
        raise ValueError("Nothing to write to a secondary file for this run.")
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for name, df in result.unresolved_tables.items():
            df.to_excel(writer, sheet_name=f"Unresolved - {name}"[:31], index=False)
        if has_key:
            result.key_table.to_excel(writer, sheet_name="Key", index=False)
