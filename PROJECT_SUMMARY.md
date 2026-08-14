# Data Anonymizer — Project Summary

*Written as a handoff/reference document at the end of a long build session. Covers what was built, why, known risks, and suggested next steps.*

## What This Is

A standalone Windows (and experimentally, macOS) desktop app that anonymizes CSV/Excel report exports before analysis — strips configured columns, replaces a "common identifier" column with a random ID (consistently, so the same real person gets the same fake ID across multiple reports run together), and optionally keeps a private key to reverse the mapping later. Built for a workflow where sensitive exports (student/staff data) need PII removed before being handed to analysis (including LLM-based analysis).

## Architecture

- **`app/`** — pure business logic, no GUI dependencies, unit-testable:
  - `engine.py` — matching/anonymization core (`process_run`)
  - `template_model.py` — `Template`/`ColumnRule`, JSON save/load
  - `output_writer.py` — Excel/CSV writing
  - `detect.py` — column header detection from a sample file
  - `paths.py` — cross-context path resolution (see below)
  - `errors.py` — crash logging + friendly error dialog
- **`gui/`** — CustomTkinter UI:
  - `main_window.py` — two-pane main window (templates left, run-queue right)
  - `template_editor.py` — create/edit template dialog
  - `theme.py` — color palette, fonts, icon path
- **`main.py`** — entry point, wraps startup in the crash handler
- **`test_phase1.py`** — regression suite covering the `app/` logic (matching, blank IDs, key generation, template round-trip). **No automated tests exist for the GUI layer** — all GUI behavior was verified manually, live, via computer-use, each time it changed. That verification isn't repeatable/regression-proof going forward.

## Major Design Decisions

- **Normalized ID matching**: strips whitespace/case/non-alphanumeric before comparing IDs across reports, so formatting differences between source systems don't cause false mismatches.
- **Blank IDs → Unresolved, not silently matched**: a row with no identifier can't be cross-referenced, so it's treated the same as an unmatched row (this was actually a bug fixed late in the project — see below).
- **ID column always survives to output** regardless of its own delete flag — needed for anonymization/cross-referencing to mean anything.
- **Delete-checkbox semantics** (not "keep"): fewer clicks, since most columns in a report are typically kept.
- **CSV output is single-report only**: if multiple reports are selected with CSV chosen, the user gets a confirmation dialog rather than a silent restriction.
- **Unresolved rows are unedited**: unmatched rows go to a separate `Unresolved - <Report>` tab with the *original*, un-anonymized, un-filtered data — so the user has full context to manually reconcile or discard them, rather than losing information.
- **Two-file output split**: the clean/matched output and anything identifying (Unresolved rows, the Key) are written to two separate files, never one — so the primary file is provably safe to hand off on its own, with no chance of PII riding along in an unread tab. The user picks one destination folder; filenames are auto-generated with a shared timestamp (`anonymized_output_<timestamp>`, `key_unresolved_<timestamp>`) so the two files from one run are easy to pair up. A CSV run's companion key file matches CSV format rather than always being Excel.
- **Anonymize defaults to checked**: re-checks itself automatically whenever the run transitions from empty to non-empty (i.e., a genuinely fresh run), but respects a manual uncheck for the rest of that run — so adding more reports to an in-progress run never silently re-enables it against the user's choice.
- **Template storage lives in `%APPDATA%\Data Anonymizer\templates\`**, not relative to the app's install location. This was a deliberate fix — see Packaging section, it would have silently broken in the packaged app otherwise.
- **Color palette**: settled on a warm/earthy palette (terracotta `#CD8B62`, sand `#EED7A1`, dark slate `#475C6C`) per the user's own reference images — an earlier teal/blue pass (based on the org's brand guide) was explicitly replaced because the user found it "too striking."

## Bugs Found & Fixed (via a second Claude instance's code review)

The user had a separate Claude instance review the code for unbiased feedback. Real, confirmed issues fixed:

1. **Template rename could lose data** — old file was deleted *before* the new one was confirmed saved. Fixed: save-then-delete, with try/except.
2. **Silent overwrite** — saving a template under a name matching a different existing template silently clobbered it. Fixed: confirmation dialog. (This had already bitten the project once — an early test script accidentally overwrote a real template this same way.)
3. **Blank-ID rows silently landed in the "matched" output** with an empty anonymized ID, instead of going to Unresolved. Fixed by removing an overly-clever exclusion in the matching logic.
4. **No CSV encoding fallback** — plain `pd.read_csv`/`pd.read_excel` would corrupt the first column header on a BOM-prefixed UTF-8 file (common from Excel "Save As CSV," which real SIS/LMS exports frequently produce). Fixed: `encoding="utf-8-sig"`.
5. **Run button not disabled mid-run** — invited double-submission. Fixed with try/finally around the run logic.

Also fixed based on the user's own live testing:
6. **Raw `PermissionError` shown on locked files** (e.g., output file open in Excel) — now shows a specific, actionable message. Verified by actually locking a file in real Excel and re-triggering the save.
7. **Dead code left over from the single-file → two-file output rewrite** — a leftover fragment after the permission-error dialog referenced `self` inside a `@staticmethod` (no `self` in scope) and an undefined variable, so it would throw a second, confusing "unexpected error" popup immediately after every legitimate permission-error dialog. Verified fixed by write-protecting a folder with `icacls` and re-triggering a real save failure.

Points from the review that were deliberately **not** acted on (judgment calls, not oversights): a theoretical ID-collision risk from stripping punctuation (doesn't apply to this org's actual ID formats), a preview-before-save step, an audit trail of runs, and pinned `requirements.txt` versions beyond `>=`.

## Packaging (Windows)

Built with PyInstaller (`--onefile --windowed`, `.spec` file committed to the repo as the build recipe).

**Critical catch before packaging**: template storage was originally resolved relative to the app's own source file location. In a PyInstaller onefile build, that resolves to a temp extraction folder that's wiped on every exit — templates would have silently vanished after every session. Fixed via `app/paths.py::user_data_dir()`, which uses `%APPDATA%\Data Anonymizer\`. Existing real templates were migrated there and verified; the old in-project folder was deleted after confirming the migration matched exactly.

**Crash handling added**: `--windowed` builds have no console, so unhandled exceptions normally vanish with zero trace. Added a catch-all in `main.py` (startup errors) and an override of Tkinter's `report_callback_exception` (runtime/callback errors) that both log to `%APPDATA%\Data Anonymizer\logs\error.log` and show a plain dialog. **Verified by deliberately injecting test crashes in both code paths** and confirming the dialog + log both fire correctly, then reverting the test code.

Final Windows build (~39 MB) was tested thoroughly, live: template CRUD, save-collision protection, invalid-name validation, full anonymize+Key+Unresolved run, locked-file handling, disabled-button-during-run.

**Rebuilt** after the default-checked-anonymize / two-file-output / timestamped-filenames changes (see Major Design Decisions). Re-verified live in the packaged exe: templates still load correctly, anonymize defaults to checked.

One resolved false alarm worth knowing about: partway through testing the packaged exe, templates appeared to not be loading. Extensive debugging eventually showed this was **not a real bug** — it was an artifact of the testing method (the computer-use tool's `open_application` kept spawning duplicate process instances, and screenshots were catching those before they'd finished their (slow, first-run, likely-antivirus-scanned) startup). The underlying app code was correct the whole time.

## Packaging (macOS) — ⚠️ Untested on real hardware

Built via GitHub Actions (`macos-latest` runner, since PyInstaller can't cross-compile). The build pipeline succeeded and the resulting `.app` bundle structure looks correct, **but nobody has actually launched it on a real Mac.** Before triggering the build, one cross-platform bug was proactively caught and fixed by reading the code (not by testing, since no Mac was available): the window-icon code used a Windows-only `.ico`/`iconbitmap()` call that would likely have crashed the app on launch on macOS. Wrapped in try/except so it fails silently instead. This fix is unverified on real hardware — **flagging this as the single biggest open risk in the project.**

The Mac build also has no custom icon (PyInstaller's default was used, to reduce first-build risk) and is unsigned, so macOS Gatekeeper will block it on first launch (right-click → Open bypasses this, same idea as Windows SmartScreen).

## Distribution

- **GitHub repo** (private): `github.com/cjturner40-max/data-anonymizer` — source code + macOS build workflow + README. Verified no sensitive data before pushing (all sample/test data is synthetic dummy data).
- **GitHub Release `v1.0.0`**: permanent home for both built binaries — Windows `.exe` (tested) and macOS `.app.zip` (build-verified only). This is the right mechanism for distributing built binaries (not committing them to git history, and not relying on CI artifacts which expire).
- Both unsigned executables will trigger first-run OS warnings (SmartScreen on Windows, Gatekeeper on Mac) — worth a heads-up to any colleague trying it.

## Suggested Next Steps

1. **Get the macOS build tested on an actual Mac** — this is the one thing that's genuinely unverified.
2. If real Mac testing surfaces issues, iterate via the same GitHub Actions workflow (`git push` + `gh workflow run build-macos.yml`), no Mac needed on the Windows side.
3. Consider adding a `.icns` icon to the Mac build once it's confirmed working.
4. If this sees real regular use, revisit the declined review items (audit trail, preview-before-save) — they were judged unnecessary for the current use case, not necessarily forever.
5. `requirements.txt` uses `>=` not pinned versions — fine for now, but worth pinning exactly if reproducibility ever becomes important.

## Key Locations

- Project folder: `C:\Users\cjtur\OneDrive\Desktop\Cowork OS\Data Anonymizer App`
- Templates (runtime data): `%APPDATA%\Data Anonymizer\templates\`
- Crash log: `%APPDATA%\Data Anonymizer\logs\error.log`
- GitHub repo: https://github.com/cjturner40-max/data-anonymizer
- Release/downloads: https://github.com/cjturner40-max/data-anonymizer/releases/tag/v1.0.0
