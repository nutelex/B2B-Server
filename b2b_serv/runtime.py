from __future__ import annotations

import json
import os
import subprocess
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


def settings_file_path() -> Path:
    return app_data_dir() / "settings.json"


def load_settings() -> dict:
    path = settings_file_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(payload: dict) -> None:
    path = settings_file_path()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


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


def find_uninstaller() -> Path | None:
    base = app_base_dir()
    candidates = [
        base / "_setup" / "unins000.exe",
        base / "unins000.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def launch_uninstaller() -> None:
    uninstaller = find_uninstaller()
    if not uninstaller:
        raise FileNotFoundError("Desinstallateur introuvable.")
    subprocess.Popen([str(uninstaller)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def detect_windows_dj_controllers() -> list[str]:
    if sys.platform != "win32":
        return []

    script = r"""
$patterns = @('Hercules', 'Inpulse', 'Impulse', 'MK2', 'Numark', 'NS4FX', 'Pioneer', 'DDJ', 'DJM', 'Traktor', 'Denon', 'Reloop', 'Vestax', 'Serato')
$devices = Get-PnpDevice -PresentOnly | Where-Object {
    $_.FriendlyName -or $_.Name
} | ForEach-Object {
    [PSCustomObject]@{
        Name = if ($_.FriendlyName) { $_.FriendlyName } else { $_.Name }
    }
}
$matches = @()
foreach ($device in $devices) {
    foreach ($pattern in $patterns) {
        if ($device.Name -like "*$pattern*") {
            $matches += $device.Name
            break
        }
    }
}
$matches | Sort-Object -Unique | ConvertTo-Json -Compress
"""
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return []

    raw = completed.stdout.strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    if isinstance(data, str):
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, str)]
    return []
