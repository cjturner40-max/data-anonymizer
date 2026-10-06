from __future__ import annotations

import time
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

from app.paths import user_data_dir

LOG_PATH = user_data_dir() / "logs" / "error.log"

# An error raised from a per-event callback (e.g. a window <Configure> handler) can
# re-fire on every event, and the error dialog itself generates more events -- so one
# bug could become an endless stream of dialogs. Remember when each distinct failure
# last occurred and stay quiet while it keeps repeating.
_REPEAT_QUIET_SECONDS = 30
_last_seen: dict[tuple, float] = {}


def _signature(exc_type, exc_value, exc_tb) -> tuple:
    frames = traceback.extract_tb(exc_tb)
    where = (frames[-1].filename, frames[-1].lineno) if frames else None
    return (exc_type.__name__, str(exc_value), where)


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
    signature = _signature(exc_type, exc_value, exc_tb)
    last = _last_seen.get(signature)
    _last_seen[signature] = time.monotonic()
    if last is not None and time.monotonic() - last < _REPEAT_QUIET_SECONDS:
        return  # same failure still repeating -- already logged and shown

    log_path = log_exception(exc_type, exc_value, exc_tb)
    try:
        messagebox.showerror(
            "Unexpected error",
            "Something went wrong and the app needs attention.\n\n"
            f"Details were saved to:\n{log_path}",
        )
    except Exception:
        pass  # even if the dialog itself fails, the log write above already happened
    _last_seen[signature] = time.monotonic()  # the dialog may have been open a while
