from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from app.engine import process_run
from app.errors import show_error_and_log
from app.output_writer import write_csv, write_xlsx
from app.paths import user_data_dir
from app.template_model import Template
from gui import theme
from gui.template_editor import TemplateEditor

STORE_DIR = user_data_dir() / "templates"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def _style_listbox(listbox: tk.Listbox):
    listbox.configure(
        bg=theme.LIST_BG,
        fg=theme.TEXT,
        selectbackground=theme.PRIMARY_ACCENT,
        selectforeground=theme.TEXT_ON_ACCENT,
        activestyle="none",
        relief="flat",
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=theme.BORDER,
        highlightcolor=theme.BORDER,
        font=(theme.FONT_FAMILY, 11),
    )


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Data Anonymizer")
        self._set_initial_geometry()
        self.minsize(760, 500)
        self.configure(fg_color=theme.BG)
        self._set_icon()

        self.templates: list[Template] = []
        self.templates_by_name: dict[str, Template] = {}
        self.task_entries: dict[str, Path] = {}  # template name -> source file path
        self.format_var = tk.StringVar(value="xlsx")
        self.anonymize_var = tk.BooleanVar(value=False)
        self.include_key_var = tk.BooleanVar(value=False)

        self._build_layout()
        self.refresh_list()

    def report_callback_exception(self, exc_type, exc_value, exc_tb):
        # Tkinter's default here just prints to stderr, which doesn't exist in a
        # --windowed build -- without this override, a bug in any button click or
        # other event handler fails completely silently. This keeps the app running
        # (matching normal Tkinter behavior) but actually surfaces what happened.
        show_error_and_log(exc_type, exc_value, exc_tb)

    def _set_initial_geometry(self):
        # split the difference between the old fixed size (860x540) and 75% of the screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        large_w = screen_w * 0.75
        large_h = screen_h * 0.75
        width = max(int((860 + large_w) / 2), 760)
        height = max(int((540 + large_h) / 2), 500)
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _set_icon(self):
        # .ico only works with Tk's iconbitmap on Windows -- macOS/Linux need a
        # different format/API entirely, so this is best-effort: skip quietly
        # rather than let a cosmetic feature take the whole app down.
        if not theme.ICON_PATH.exists():
            return
        icon = str(theme.ICON_PATH)

        def try_set():
            try:
                self.iconbitmap(icon)
            except Exception:
                pass

        try_set()
        # customtkinter re-applies its own default icon shortly after init, so
        # re-set ours a moment later to make sure it's the one that sticks
        self.after(250, try_set)

    def _build_layout(self):
        panes = ctk.CTkFrame(self, fg_color="transparent")
        panes.pack(fill="both", expand=True, padx=16, pady=16)
        panes.columnconfigure(0, weight=1, uniform="panes")
        panes.columnconfigure(1, weight=0, minsize=36)
        panes.columnconfigure(2, weight=1, uniform="panes")
        panes.rowconfigure(0, weight=1)

        # --- left pane: template management ---
        left = ctk.CTkFrame(panes, fg_color=theme.CARD, corner_radius=12, border_width=1, border_color=theme.BORDER)
        left.grid(row=0, column=0, sticky="nsew")

        left_inner = ctk.CTkFrame(left, fg_color="transparent")
        left_inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            left_inner, text="Report Templates", font=(theme.FONT_FAMILY, 15, "bold"), text_color=theme.TEXT
        ).pack(anchor="w")
        ctk.CTkLabel(
            left_inner,
            text="Double-click a template to attach a file",
            font=(theme.FONT_FAMILY, 11),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 8))

        list_frame = tk.Frame(left_inner, bg=theme.CARD)
        list_frame.pack(fill="both", expand=True)
        self.template_listbox = tk.Listbox(list_frame, activestyle="none", exportselection=False)
        _style_listbox(self.template_listbox)
        self.template_listbox.pack(fill="both", expand=True)
        self.template_listbox.bind("<Double-Button-1>", lambda e: self.add_to_run())

        template_buttons = ctk.CTkFrame(left_inner, fg_color="transparent")
        template_buttons.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(
            template_buttons, text="New Template...", command=self.new_template, **self._secondary_button_kwargs()
        ).pack(side="left")
        ctk.CTkButton(
            template_buttons, text="Edit Selected...", command=self.edit_selected, **self._secondary_button_kwargs()
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            template_buttons, text="Delete Selected", command=self.delete_selected, **self._secondary_button_kwargs()
        ).pack(side="left")

        # --- arrow between panes ---
        arrow_frame = ctk.CTkFrame(panes, fg_color="transparent")
        arrow_frame.grid(row=0, column=1, sticky="ns", padx=2)
        ctk.CTkLabel(
            arrow_frame, text=">", font=(theme.FONT_FAMILY, 42, "bold"), text_color=theme.PRIMARY_ACCENT
        ).place(relx=0.5, rely=0.5, anchor="center")

        # --- right pane: current run ---
        right = ctk.CTkFrame(panes, fg_color=theme.CARD, corner_radius=12, border_width=1, border_color=theme.BORDER)
        right.grid(row=0, column=2, sticky="nsew")

        right_inner = ctk.CTkFrame(right, fg_color="transparent")
        right_inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            right_inner, text="Reports Selected", font=(theme.FONT_FAMILY, 15, "bold"), text_color=theme.TEXT
        ).pack(anchor="w")
        ctk.CTkLabel(right_inner, text="", font=(theme.FONT_FAMILY, 11)).pack(anchor="w", pady=(0, 8))

        task_list_frame = tk.Frame(right_inner, bg=theme.CARD)
        task_list_frame.pack(fill="both", expand=True)

        tree_style = ttk.Style(self)
        tree_style.theme_use("clam")
        tree_style.configure(
            "Task.Treeview",
            background=theme.LIST_BG,
            fieldbackground=theme.LIST_BG,
            foreground=theme.TEXT,
            rowheight=24,
            font=(theme.FONT_FAMILY, 11),
            borderwidth=1,
            bordercolor=theme.BORDER,
            relief="flat",
        )
        tree_style.configure(
            "Task.Treeview.Heading",
            background=theme.CARD,
            foreground=theme.TEXT_MUTED,
            font=(theme.FONT_FAMILY, 10, "bold"),
            relief="flat",
            borderwidth=1,
            bordercolor=theme.BORDER,
        )
        tree_style.map(
            "Task.Treeview",
            background=[("selected", theme.PRIMARY_ACCENT)],
            foreground=[("selected", theme.TEXT_ON_ACCENT)],
        )

        self.task_listbox = ttk.Treeview(
            task_list_frame,
            columns=("template", "file"),
            show="headings",
            style="Task.Treeview",
            selectmode="browse",
        )
        self.task_listbox.heading("template", text="Report Template", anchor="w")
        self.task_listbox.heading("file", text="Source File", anchor="w")
        self.task_listbox.column("template", anchor="w", width=150)
        self.task_listbox.column("file", anchor="w", width=150)
        self.task_listbox.pack(fill="both", expand=True)

        # ttk.Treeview has no native per-column divider in most themes, so overlay a
        # thin rule at the column midpoint (columns are equal width, so 50% lines up)
        column_divider = tk.Frame(task_list_frame, bg=theme.BORDER, width=1)
        column_divider.place(relx=0.5, rely=0, relheight=1)

        task_buttons = ctk.CTkFrame(right_inner, fg_color="transparent")
        task_buttons.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(
            task_buttons, text="Remove Selected", command=self.remove_from_run, **self._secondary_button_kwargs()
        ).pack(side="left")

        # --- bottom controls ---
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=(0, 16))

        controls = ctk.CTkFrame(bottom, fg_color="transparent")
        controls.pack(side="left", fill="y")

        format_frame = ctk.CTkFrame(controls, fg_color="transparent")
        format_frame.pack(anchor="w")
        ctk.CTkLabel(format_frame, text="Output format:", text_color=theme.TEXT).pack(side="left")
        ctk.CTkRadioButton(
            format_frame,
            text="Excel (.xlsx)",
            variable=self.format_var,
            value="xlsx",
            fg_color=theme.PRIMARY_ACCENT,
            hover_color=theme.PRIMARY_ACCENT_HOVER,
            text_color=theme.TEXT,
        ).pack(side="left", padx=(10, 0))
        ctk.CTkRadioButton(
            format_frame,
            text="CSV",
            variable=self.format_var,
            value="csv",
            fg_color=theme.PRIMARY_ACCENT,
            hover_color=theme.PRIMARY_ACCENT_HOVER,
            text_color=theme.TEXT,
        ).pack(side="left", padx=(10, 0))

        anon_frame = ctk.CTkFrame(controls, fg_color="transparent")
        anon_frame.pack(anchor="w", pady=(6, 0))
        self.anonymize_check = ctk.CTkCheckBox(
            anon_frame,
            text="Anonymize common identifier in output",
            variable=self.anonymize_var,
            command=self._sync_include_key_state,
            fg_color=theme.PRIMARY_ACCENT,
            hover_color=theme.PRIMARY_ACCENT_HOVER,
            text_color=theme.TEXT,
        )
        self.anonymize_check.pack(side="left")
        self.anonymize_note = ctk.CTkLabel(anon_frame, text="", text_color=theme.TEXT_MUTED)
        self.anonymize_note.pack(side="left", padx=(8, 0))

        key_frame = ctk.CTkFrame(controls, fg_color="transparent")
        key_frame.pack(anchor="w", pady=(4, 0))
        self.include_key_check = ctk.CTkCheckBox(
            key_frame,
            text="Include Key",
            variable=self.include_key_var,
            state="disabled",
            fg_color=theme.PRIMARY_ACCENT,
            hover_color=theme.PRIMARY_ACCENT_HOVER,
            text_color=theme.TEXT,
        )
        self.include_key_check.pack(side="left")

        self.status_label = ctk.CTkLabel(
            controls, text="", text_color=theme.TEXT_MUTED, wraplength=460, justify="left"
        )
        self.status_label.pack(anchor="w", pady=(8, 0))

        run_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        run_frame.pack(side="right")
        self.run_button = ctk.CTkButton(
            run_frame,
            text="Run Task",
            command=self.run_task,
            width=150,
            height=56,
            corner_radius=10,
            font=(theme.FONT_FAMILY, 16, "bold"),
            fg_color=theme.PRIMARY_ACCENT,
            hover_color=theme.PRIMARY_ACCENT_HOVER,
            text_color=theme.TEXT_ON_ACCENT,
        )
        self.run_button.pack()

    @staticmethod
    def _secondary_button_kwargs():
        return dict(
            fg_color=theme.SECONDARY_ACCENT,
            hover_color=theme.SECONDARY_ACCENT_HOVER,
            text_color=theme.TEXT_ON_SECONDARY,
            corner_radius=8,
            font=(theme.FONT_FAMILY, 12),
        )

    # --- template list (left pane) ---

    def refresh_list(self):
        self.template_listbox.delete(0, tk.END)
        self.templates = Template.load_all(STORE_DIR)
        self.templates_by_name = {t.name: t for t in self.templates}
        for t in self.templates:
            id_note = (
                f"  (Common Identifier: {t.id_column})" if t.id_column else "  (no Common Identifier set)"
            )
            self.template_listbox.insert(tk.END, f"{t.name}{id_note}")

        for name in list(self.task_entries):
            if name not in self.templates_by_name:
                del self.task_entries[name]
        self._refresh_task_list()

    def _selected_template(self) -> Template | None:
        sel = self.template_listbox.curselection()
        if not sel:
            return None
        return self.templates[sel[0]]

    def new_template(self):
        editor = TemplateEditor(self, STORE_DIR, template=None)
        self.wait_window(editor)
        self.refresh_list()

    def edit_selected(self):
        template = self._selected_template()
        if template is None:
            messagebox.showinfo("No selection", "Select a template to edit first.")
            return
        editor = TemplateEditor(self, STORE_DIR, template=template)
        self.wait_window(editor)
        self.refresh_list()

    def delete_selected(self):
        template = self._selected_template()
        if template is None:
            messagebox.showinfo("No selection", "Select a template to delete first.")
            return
        if not messagebox.askyesno("Delete template", f"Delete template '{template.name}'? This cannot be undone."):
            return
        path = STORE_DIR / f"{template.name}.json"
        if path.exists():
            path.unlink()
        self.refresh_list()

    # --- run list (right pane) ---

    def add_to_run(self):
        template = self._selected_template()
        if template is None:
            return
        path = filedialog.askopenfilename(
            title=f"Select source file for '{template.name}'",
            filetypes=[("CSV or Excel", "*.csv *.xlsx *.xls"), ("All files", "*.*")],
        )
        if not path:
            return
        self.task_entries[template.name] = Path(path)
        self._refresh_task_list()

    def _refresh_task_list(self):
        self.task_listbox.delete(*self.task_listbox.get_children())
        for name, path in self.task_entries.items():
            self.task_listbox.insert("", "end", iid=name, values=(name, path.name))
        self._update_anonymize_availability()

    def remove_from_run(self):
        sel = self.task_listbox.selection()
        if not sel:
            return
        name = sel[0]
        del self.task_entries[name]
        self._refresh_task_list()

    def _update_anonymize_availability(self):
        selected = [self.templates_by_name[name] for name in self.task_entries if name in self.templates_by_name]
        if not selected:
            self.anonymize_check.configure(state="disabled")
            self.anonymize_var.set(False)
            self.anonymize_note.configure(text="")
        else:
            missing_id = [t.name for t in selected if t.id_column is None]
            if missing_id:
                self.anonymize_check.configure(state="disabled")
                self.anonymize_var.set(False)
                self.anonymize_note.configure(
                    text=f"Unavailable — no common identifier set for: {', '.join(missing_id)}"
                )
            else:
                self.anonymize_check.configure(state="normal")
                self.anonymize_note.configure(text="")
        self._sync_include_key_state()

    def _sync_include_key_state(self):
        # "Include Key" only makes sense once anonymization is actually turned on
        if self.anonymize_var.get():
            self.include_key_check.configure(state="normal")
        else:
            self.include_key_var.set(False)
            self.include_key_check.configure(state="disabled")

    # --- run task ---

    def run_task(self):
        if not self.task_entries:
            messagebox.showwarning("Nothing selected", "Double-click a template on the left to add it to the run.")
            return

        self.run_button.configure(state="disabled")
        try:
            self._run_task_body()
        finally:
            self.run_button.configure(state="normal")

    def _run_task_body(self):
        selected_names = list(self.task_entries.keys())
        selected = [self.templates_by_name[name] for name in selected_names]

        output_format = self.format_var.get()
        if output_format == "csv" and len(selected) > 1:
            first = selected[0]
            proceed = messagebox.askyesno(
                "CSV supports one report only",
                f"CSV output only supports a single report at a time, but {len(selected)} are selected. "
                f"Only '{first.name}' would be exported; the rest would be skipped.\n\n"
                "Continue with just that one, or Cancel to change your selection (e.g. switch to Excel)?",
            )
            if not proceed:
                return
            selected = [first]
            selected_names = [first.name]

        anonymize = self.anonymize_var.get()
        templates = {name: self.templates_by_name[name] for name in selected_names}
        input_files = {name: self.task_entries[name] for name in selected_names}

        try:
            result = process_run(templates, input_files, anonymize=anonymize)
        except Exception as exc:
            messagebox.showerror("Run failed", str(exc))
            return

        default_ext = ".xlsx" if output_format == "xlsx" else ".csv"
        default_name = (selected[0].name if len(selected) == 1 else "anonymized_output") + default_ext
        out_path = filedialog.asksaveasfilename(
            title="Save output as...",
            defaultextension=default_ext,
            filetypes=[("Excel", "*.xlsx")] if output_format == "xlsx" else [("CSV", "*.csv")],
            initialfile=default_name,
        )
        if not out_path:
            return

        try:
            if output_format == "xlsx":
                write_xlsx(result, Path(out_path), include_key=self.include_key_var.get())
            else:
                write_csv(result, Path(out_path))
        except PermissionError:
            messagebox.showerror(
                "Couldn't write output",
                f"Couldn't save to:\n{out_path}\n\n"
                "This usually means the file is currently open in Excel or another program. "
                "Close it and try again, or choose a different filename.",
            )
            return
        except Exception as exc:
            messagebox.showerror("Couldn't write output", str(exc))
            return

        if result.unmatched_count:
            breakdown = ", ".join(f"{name}: {n}" for name, n in result.unmatched_by_template.items() if n)
            messagebox.showwarning(
                "Some rows didn't match",
                f"{result.unmatched_count} row(s) could not be matched across all selected reports "
                f"({breakdown}). Those rows were left out of the matched tabs and placed, unedited, "
                "in separate 'Unresolved - <report>' tabs in the output file for you to review.",
            )

        messagebox.showinfo("Done", f"Output saved to:\n{out_path}")
        self.status_label.configure(text=f"Last run saved to {out_path}")


def main():
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
