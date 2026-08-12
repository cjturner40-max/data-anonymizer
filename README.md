# Data Anonymizer

## Purpose

Data Anonymizer is a standalone desktop app for preparing sensitive spreadsheet exports (CSV/Excel) for analysis without exposing personally identifying information. You define reusable templates per report type — specifying which columns to strip and which column holds the common identifier — then run one or more reports through a single pass that anonymizes identifiers, cross-references matching individuals across reports, and produces clean output ready to hand off for analysis, while keeping the ability to trace results back to real identities entirely in your own control.

## Critical Features

- **Reusable report templates** — Each source report type gets a saved template defining which columns to delete and which column is the common identifier, so you configure it once and reuse it on every future export of that report.
- **Column auto-detection** — Point a template at a sample file and it reads the columns automatically; it only interrupts you with a "columns changed" alert when re-checking an existing template against a fresh file, not on first setup.
- **Anonymization with consistent IDs** — Turning on anonymization replaces the common identifier with a random ID, and the same real person gets the same anonymized ID across every report in that run, so cross-referencing still works on the anonymized data.
- **Cross-report matching with Unresolved tabs** — When multiple reports run together, rows are matched by identifier (tolerant of case/whitespace differences); anything that can't be matched across all selected reports is pulled into its own "Unresolved - `<Report>`" tab, left completely unedited, rather than mixed into the clean output.
- **Optional Key tab** — "Include Key" adds a tab mapping every real identifier to its anonymized counterpart, letting you privately backtrack anonymized analysis results to real individuals later without re-running anything.
- **Flexible output** — Export to Excel (multi-tab, supports everything above) or CSV (single report only, with a confirmation prompt if more than one is selected).

## Downloads

Pre-built apps are on the [Releases page](https://github.com/cjturner40-max/data-anonymizer/releases) — Windows `.exe` and macOS `.app` (zipped).
