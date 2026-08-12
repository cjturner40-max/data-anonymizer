from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

from app.paths import user_data_dir

LOG_PATH = user_data_dir() / "logs" / "error.log"


def log_exception(exc_type, exc_value, exc_tb) -> Path:
    """Append a crash's full traceback to the log file, creating it if needed."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n--- {datetime.now().isoformat(timespec='seconds')} ---\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    return LOG_PATH


def show_error_and_log(exc_type, exc_value, exc_tb) -> None:
    """Log an unexpected exception and surface a plain error dialog instead of
    letting it vanish silently -- windowed builds have no console, so an
    uncaught exception normally leaves no trace at all."""
    log_path = log_exception(exc_type, exc_value, exc_tb)
    try:
        messagebox.showerror(
            "Unexpected error",
            "Something went wrong and the app needs attention.\n\n"
            f"Details were saved to:\n{log_path}",
        )
    except Exception:
        pass  # even if the dialog itself fails, the log write above already happened
