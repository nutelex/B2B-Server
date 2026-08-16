from __future__ import annotations

import os
import sys
from pathlib import Path


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundled_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", app_base_dir()))
    return base.joinpath(*parts)


def app_data_dir() -> Path:
    root = Path(os.getenv("LOCALAPPDATA", app_base_dir()))
    path = root / "B2BServ"
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_tk_environment() -> None:
    candidates = [
        bundled_path("tcl", "tcl8.6"),
        app_base_dir() / "tcl" / "tcl8.6",
        Path(sys.base_prefix) / "tcl" / "tcl8.6",
        Path(sys.base_prefix) / "tcl" / "tcl8",
    ]
    tk_candidates = [
        bundled_path("tcl", "tk8.6"),
        app_base_dir() / "tcl" / "tk8.6",
        Path(sys.base_prefix) / "tcl" / "tk8.6",
    ]

    for path in candidates:
        if (path / "init.tcl").exists():
            os.environ["TCL_LIBRARY"] = str(path)
            break

    for path in tk_candidates:
        if (path / "tk.tcl").exists():
            os.environ["TK_LIBRARY"] = str(path)
            break
