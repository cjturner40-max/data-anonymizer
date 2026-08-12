from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .template_model import Template


def normalize_id(value) -> str:
    """Trim whitespace, ignore case, and strip non-alphanumeric characters before comparing IDs."""
    if pd.isna(value):
        return ""
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


def _read_table(file_path: Path) -> pd.DataFrame:
    file_path = Path(file_path)
    if file_path.suffix.lower() == ".csv":
        return pd.read_csv(file_path, dtype=str, encoding="utf-8-sig")
    return pd.read_excel(file_path, dtype=str)


def _generate_unique_ids(count: int, digits: int = 8) -> list[str]:
    ceiling = 10**digits
    while count > ceiling * 0.5:
        digits += 1
        ceiling = 10**digits
    pool = random.sample(range(ceiling), count)
    return [str(n).zfill(digits) for n in pool]


@dataclass
class RunResult:
    tables: dict[str, pd.DataFrame]  # matched rows only, per template (column-filtered, anonymized)
    unresolved_tables: dict[str, pd.DataFrame]  # unmatched rows only, unedited from the source file
    unmatched_count: int
    unmatched_by_template: dict[str, int]
    key_table: pd.DataFrame | None  # real ID -> anonymized ID, for rows that appear anonymized in `tables`


def process_run(
    templates: dict[str, Template],
    input_files: dict[str, Path],
    anonymize: bool,
) -> RunResult:
    if anonymize and any(t.id_column is None for t in templates.values()):
        missing = [name for name, t in templates.items() if t.id_column is None]
        raise ValueError(f"Cannot anonymize: no common identifier set for template(s): {missing}")

    full_tables: dict[str, pd.DataFrame] = {}  # unfiltered, exactly as read from the source file
    raw_tables: dict[str, pd.DataFrame] = {}  # filtered to the template's kept columns
    norm_id_cols: dict[str, pd.Series] = {}

    for name, template in templates.items():
        full_df = _read_table(input_files[name])
        missing_cols = set(template.kept_columns) - set(full_df.columns)
        if missing_cols:
            raise ValueError(
                f"'{Path(input_files[name]).name}' is missing expected columns for "
                f"template '{name}': {sorted(missing_cols)}"
            )
        full_tables[name] = full_df
        df = full_df[template.kept_columns].copy()
        id_col = template.id_column
        norm_id_cols[name] = df[id_col].map(normalize_id) if id_col else pd.Series(dtype=str)
        raw_tables[name] = df

    unmatched_mask: dict[str, pd.Series] = {
        name: pd.Series(False, index=raw_tables[name].index) for name in templates
    }

    key_table: pd.DataFrame | None = None

    if anonymize:
        if len(templates) > 1:
            id_sets = {name: set(s) - {""} for name, s in norm_id_cols.items()}
            common_ids = set.intersection(*id_sets.values())
            # blank IDs are never in common_ids (each id_set drops "" before intersecting),
            # so a blank-ID row always lands in unmatched -- there's nothing to cross-reference
            # it against, so it belongs in Unresolved rather than silently riding into the
            # clean/anonymized output with an empty ID
            for name in templates:
                unmatched_mask[name] = ~norm_id_cols[name].isin(common_ids)

        all_norm_ids: set[str] = set()
        for s in norm_id_cols.values():
            all_norm_ids.update(v for v in s if v)
        fake_ids = _generate_unique_ids(len(all_norm_ids))
        id_map = dict(zip(sorted(all_norm_ids), fake_ids))

        # normalized ids that actually end up anonymized in a matched row -- ids that only
        # appear in unresolved/unmatched rows keep their real value there, so they don't
        # need a key entry. Capture one representative raw (pre-anonymization) ID string
        # per normalized id, for display in the key.
        matched_norm_ids: set[str] = set()
        raw_id_by_norm: dict[str, str] = {}
        for name, template in templates.items():
            id_col = template.id_column
            matched_norm_ids.update(norm_id_cols[name][~unmatched_mask[name]])
            for raw_val, norm_val in zip(raw_tables[name][id_col], norm_id_cols[name]):
                if norm_val and norm_val not in raw_id_by_norm:
                    raw_id_by_norm[norm_val] = raw_val
        matched_norm_ids.discard("")

        for name, template in templates.items():
            id_col = template.id_column
            raw_tables[name][id_col] = norm_id_cols[name].map(lambda v: id_map.get(v, "") if v else "")

        ordered = sorted(matched_norm_ids)
        key_table = pd.DataFrame(
            {
                "Common Identifier": [raw_id_by_norm[n] for n in ordered],
                "Anonymized ID": [id_map[n] for n in ordered],
            }
        )

    matched_tables: dict[str, pd.DataFrame] = {}
    unresolved_tables: dict[str, pd.DataFrame] = {}
    for name in templates:
        mask = unmatched_mask[name]
        matched_tables[name] = raw_tables[name].loc[~mask].reset_index(drop=True)
        if mask.any():
            unresolved_tables[name] = full_tables[name].loc[mask].reset_index(drop=True)

    unmatched_by_template = {name: int(mask.sum()) for name, mask in unmatched_mask.items()}
    return RunResult(
        tables=matched_tables,
        unresolved_tables=unresolved_tables,
        unmatched_count=sum(unmatched_by_template.values()),
        unmatched_by_template=unmatched_by_template,
        key_table=key_table,
    )
