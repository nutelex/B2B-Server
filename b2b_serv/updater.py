from __future__ import annotations

import json
import subprocess
import tempfile
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

    subprocess.Popen(
        [str(target), "/VERYSILENT", "/NORESTART", "/CLOSEAPPLICATIONS"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return target


def _find_installer_asset(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if name.endswith("installer.exe"):
            return asset
    return None
