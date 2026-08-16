from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib import error, request

from .version import __version__

REPO_API_LATEST = "https://api.github.com/repos/nutelex/B2B-Server/releases/latest"


def parse_version(value: str) -> tuple[int, ...]:
    cleaned = value.strip().lstrip("v")
    parts = []
    for item in cleaned.split("."):
        try:
            parts.append(int(item))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_for_update() -> dict[str, Any] | None:
    req = request.Request(
        REPO_API_LATEST,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "B2B-Serv-Updater",
        },
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    latest_tag = str(payload.get("tag_name", "")).strip()
    if not latest_tag:
        return None

    latest_version = parse_version(latest_tag)
    current_version = parse_version(__version__)
    if latest_version <= current_version:
        return None

    installer_asset = _find_installer_asset(payload.get("assets", []))
    return {
        "current_version": __version__,
        "latest_version": latest_tag.lstrip("v"),
        "html_url": payload.get("html_url", "https://github.com/nutelex/B2B-Server/releases/latest"),
        "name": payload.get("name", latest_tag),
        "installer_url": installer_asset.get("browser_download_url", "") if installer_asset else "",
        "installer_name": installer_asset.get("name", "") if installer_asset else "",
    }


def download_and_launch_update(installer_url: str, installer_name: str) -> Path:
    if not installer_url:
        raise RuntimeError("Aucun installateur de mise a jour n'est disponible.")

    temp_dir = Path(tempfile.gettempdir()) / "B2BServUpdater"
    temp_dir.mkdir(parents=True, exist_ok=True)
    target = temp_dir / (installer_name or "B2B-Serv-Installer.exe")
    helper = temp_dir / "run_update.ps1"
    ready_flag = temp_dir / "update_ready.flag"
    if ready_flag.exists():
        ready_flag.unlink()

    req = request.Request(
        installer_url,
        headers={"User-Agent": "B2B-Serv-Updater"},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            target.write_bytes(response.read())
    except error.URLError as exc:
        raise RuntimeError("Telechargement de la mise a jour impossible.") from exc

    restart_target = Path(sys.executable).resolve()
    helper.write_text(
        _build_update_helper_script(target, restart_target, ready_flag),
        encoding="utf-8",
    )

    process = subprocess.Popen(
        [
            "powershell.exe",
            "-Sta",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_ready_flag(ready_flag, process)
    return target


def _find_installer_asset(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if name.endswith("installer.exe"):
            return asset
    return None


def _build_update_helper_script(installer_path: Path, restart_target: Path, ready_flag: Path) -> str:
    installer = str(installer_path).replace("'", "''")
    restart = str(restart_target).replace("'", "''")
    ready = str(ready_flag).replace("'", "''")
    return f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

Set-Content -Path '{ready}' -Value 'ready'

$form = New-Object System.Windows.Forms.Form
$form.Text = 'B2B Serv'
$form.Width = 420
$form.Height = 140
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.TopMost = $true

$label = New-Object System.Windows.Forms.Label
$label.Left = 20
$label.Top = 20
$label.Width = 360
$label.Height = 50
$label.Text = 'Mise a jour en cours...`r`nL''application va se relancer automatiquement.'
$form.Controls.Add($label)

$installer = Start-Process -FilePath '{installer}' -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CLOSEAPPLICATIONS','/FORCECLOSEAPPLICATIONS' -PassThru

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 1000
$timer.Add_Tick({{
    if ($installer.HasExited) {{
        $timer.Stop()
        Start-Process -FilePath '{restart}'
        $form.Close()
    }}
}})
$timer.Start()

[void]$form.ShowDialog()
"""


def _wait_for_ready_flag(ready_flag: Path, process: subprocess.Popen[bytes | str], timeout: float = 8.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ready_flag.exists():
            return
        if process.poll() is not None:
            break
        time.sleep(0.1)
    raise RuntimeError("Le module de mise a jour ne s'est pas lance correctement.")
