from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Resolve a path to a bundled read-only resource (e.g. the app icon) -- works both
    running from source and from a PyInstaller-frozen executable, where bundled files
    are unpacked to a temporary directory at runtime."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    else:
        base = PROJECT_ROOT
    return base.joinpath(*parts)


def user_data_dir() -> Path:
    """Per-user writable location for this app's persistent data (saved templates).
    Always here regardless of where the app itself is installed or run from, so it
    survives reinstalls/updates and works even if the app ends up somewhere
    read-only, like Program Files."""
    appdata = os.getenv("APPDATA") or str(Path.home())
    return Path(appdata) / "Data Anonymizer"
