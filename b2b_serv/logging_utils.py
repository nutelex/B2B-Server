from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .runtime import app_data_dir


def log_file_path() -> Path:
    return app_data_dir() / "b2b-serv.log"


def append_log(message: str) -> str:
    timestamped = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    path = log_file_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(timestamped + "\n")
    return timestamped


def read_logs() -> str:
    path = log_file_path()
    if not path.exists():
        return "Aucun log pour le moment."
    return path.read_text(encoding="utf-8")
