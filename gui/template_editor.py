from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.detect import detect_columns
from app.template_model import ColumnRule, Template
from gui import theme


class TemplateEditor(ctk.CTkToplevel):
    def __init__(self, parent, store_dir: Path, template: Template | None):
        super().__init__(parent)
        self.store_dir = store_dir
        self.original_name = template.name if template else None
        self.column_vars: dict[str, tk.BooleanVar] = {}
        self.column_checkboxes: dict[str, ctk.CTkCheckBox] = {}

        self.title("Edit Template" if template else "New Template")
        self.geometry("620x520")
        self.minsize(560, 380)
        self.configure(fg_color=theme.BG)
        self.transient(parent)
        self.after(50, self.grab_set)  # deferred so the CTkToplevel has finished drawing first
        if theme.ICON_PATH.exists():
            icon = str(theme.ICON_PATH)

            def try_set_icon():
                # .ico only works with Tk's iconbitmap on Windows -- best-effort elsewhere
                try:
                    self.iconbitmap(icon)
                except Exception:
                    pass

            self.after(100, try_set_icon)
            self.after(300, try_set_icon)

        self.id_var = tk.StringVar(value="")
        self.id_var.trace_add("write", self._on_id_changed)

        name_frame = ctk.CTkFrame(self, fg_color="transparent")
        name_frame.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(name_frame, text="Template name:", text_color=theme.TEXT).pack(side="left")
        self.name_var = tk.StringVar(value=template.name if template else "")
        ctk.CTkEntry(name_frame, textvariable=self.name_var).pack(side="left", fill="x", expand=True, padx=(8, 0))

        load_frame = ctk.CTkFrame(self, fg_color="transparent")
        load_frame.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkButton(
            load_frame,
            text="Select source file...",
            command=self.load_file,
            fg_color=theme.SECONDARY_ACCENT,
            hover_color=theme.SECONDARY_ACCENT_HOVER,
            text_color=theme.TEXT_ON_SECONDARY,
            corner_radius=8,
        ).pack(side="left")
        self.file_label = ctk.CTkLabel(load_frame, text="(no file loaded)", text_color=theme.TEXT_MUTED)
        self.file_label.pack(side="left", padx=(10, 0))

        columns_card = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=12, border_width=1, border_color=theme.BORDER)
        columns_card.pack(fill="both", expand=True, padx=16, pady=8)

        header_frame = ctk.CTkFrame(columns_card, fg_color="transparent")
        header_frame.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(header_frame, text="Column", width=260, anchor="w", text_color=theme.TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(header_frame, text="Delete", width=70, anchor="w", text_color=theme.TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(header_frame, text="Common Identifier", width=150, anchor="w", text_color=theme.TEXT_MUTED).pack(
            side="left"
        )

        self.columns_frame = ctk.CTkScrollableFrame(columns_card, fg_color="transparent")
        self.columns_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.status_label = ctk.CTkLabel(self, text="", text_color=theme.TEXT_MUTED)
        self.status_label.pack(fill="x", padx=16)

        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(fill="x", padx=16, pady=(8, 16))
        ctk.CTkButton(
            action_frame,
            text="Save",
            command=self.save,
            fg_color=theme.PRIMARY_ACCENT,
            hover_color=theme.PRIMARY_ACCENT_HOVER,
            text_color=theme.TEXT_ON_ACCENT,
            corner_radius=8,
        ).pack(side="right")
        ctk.CTkButton(
            action_frame,
            text="Cancel",
            command=self.destroy,
            fg_color=theme.WARM_GRAY,
            hover_color=theme.WARM_GRAY_HOVER,
            text_color=theme.TEXT_ON_ACCENT,
            corner_radius=8,
        ).pack(side="right", padx=(0, 6))

        if template:
            self._render_columns(
                [c.name for c in template.columns],
                delete_state={c.name: c.delete for c in template.columns},
                id_state=template.id_column,
            )
            self.status_label.configure(
                text=f"Loaded saved template ({len(template.columns)} columns). "
                "Select a source file above to re-check columns against a fresh export."
            )

    def _on_id_changed(self, *_):
        id_col = self.id_var.get()
        for col, cb in self.column_checkboxes.items():
            if col == id_col:
                self.column_vars[col].set(False)
                # fade the checkbox out (border and fill both drop to the pale card-border
                # tone) so it's visually obvious this option isn't available, not just inert
                cb.configure(state="disabled", border_color=theme.BORDER, fg_color=theme.BORDER)
            else:
                cb.configure(state="normal", border_color=theme.WARM_GRAY, fg_color=theme.PRIMARY_ACCENT)

    def load_file(self):
        path = filedialog.askopenfilename(
            title="Select a sample source file",
            filetypes=[("CSV or Excel", "*.csv *.xlsx *.xls"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            columns = detect_columns(Path(path))
        except Exception as exc:
            messagebox.showerror("Couldn't read file", f"Could not read columns from this file:\n{exc}")
            return
        if not columns:
            messagebox.showwarning("No columns found", "That file doesn't appear to have any columns.")
            return

        self.file_label.configure(text=Path(path).name, text_color=theme.TEXT)

        prev_delete = {name: var.get() for name, var in self.column_vars.items()}
        had_previous_columns = bool(prev_delete)
        prev_id = self.id_var.get()
        new_cols = set(columns) - set(prev_delete)
        removed_cols = set(prev_delete) - set(columns)

        self._render_columns(columns, delete_state=prev_delete, id_state=prev_id if prev_id in columns else None)

        # only worth interrupting with a popup when there was a previous column set to compare
        # against (i.e. re-checking an existing template) -- on a template's first file load,
        # every column is trivially "new" and that's not informative
        if had_previous_columns and (new_cols or removed_cols):
            parts = []
            if new_cols:
                parts.append(
                    "New columns found (default: kept, not set as common identifier):\n  "
                    + "\n  ".join(sorted(new_cols))
                )
            if removed_cols:
                parts.append("Columns no longer present (their settings were dropped):\n  " + "\n  ".join(sorted(removed_cols)))
            messagebox.showinfo("Columns changed", "\n\n".join(parts))
        else:
            self.status_label.configure(text=f"{len(columns)} columns detected from {Path(path).name}.")

    def _render_columns(self, columns: list[str], delete_state: dict[str, bool], id_state: str | None):
        for child in self.columns_frame.winfo_children():
            child.destroy()
        self.column_vars = {}
        self.column_checkboxes = {}

        for col in columns:
            row = ctk.CTkFrame(self.columns_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=col, width=260, anchor="w", text_color=theme.TEXT).pack(side="left")
            delete_var = tk.BooleanVar(value=delete_state.get(col, False))
            cb = ctk.CTkCheckBox(
                row,
                text="",
                variable=delete_var,
                width=70,
                fg_color=theme.PRIMARY_ACCENT,
                hover_color=theme.PRIMARY_ACCENT_HOVER,
                border_color=theme.WARM_GRAY,
            )
            cb.pack(side="left")
            ctk.CTkRadioButton(
                row,
                text="",
                variable=self.id_var,
                value=col,
                width=150,
                fg_color=theme.PRIMARY_ACCENT,
                hover_color=theme.PRIMARY_ACCENT_HOVER,
            ).pack(side="left")
            self.column_vars[col] = delete_var
            self.column_checkboxes[col] = cb

        self.id_var.set(id_state or "")  # triggers _on_id_changed to disable the ID column's delete box

    INVALID_NAME_CHARS = '<>:"/\\|?*'

    def save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Give this template a name before saving.")
            return
        bad_chars = sorted(set(name) & set(self.INVALID_NAME_CHARS))
        if bad_chars:
            messagebox.showerror(
                "Invalid name",
                f"Template name can't contain: {' '.join(bad_chars)}",
            )
            return
        if not self.column_vars:
            messagebox.showwarning("No columns", "Select a source file to detect its columns before saving.")
            return

        id_col = self.id_var.get() or None
        if id_col is None:
            proceed = messagebox.askyesno(
                "No common identifier set",
                "No column is marked as the common identifier. This template won't be usable for "
                "anonymized, cross-referenced output until one is set. Save anyway?",
            )
            if not proceed:
                return

        target_path = self.store_dir / f"{name}.json"
        if target_path.exists() and name != self.original_name:
            proceed = messagebox.askyesno(
                "Replace existing template?",
                f"A template named '{name}' already exists. Replace it?",
            )
            if not proceed:
                return

        columns = [
            ColumnRule(name=col, delete=delete_var.get(), is_id=(col == id_col))
            for col, delete_var in self.column_vars.items()
        ]
        template = Template(name=name, columns=columns)

        try:
            template.save(self.store_dir)
        except OSError as exc:
            messagebox.showerror("Couldn't save template", f"Could not save this template:\n{exc}")
            return

        # only remove the old file (on rename) after the new one has saved successfully,
        # so a failed save never leaves you with neither the old nor the new template
        if self.original_name and self.original_name != name:
            old_path = self.store_dir / f"{self.original_name}.json"
            if old_path.exists():
                old_path.unlink()

        self.destroy()
