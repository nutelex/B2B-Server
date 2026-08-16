from __future__ import annotations

import json
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

    return {
        "current_version": __version__,
        "latest_version": latest_tag.lstrip("v"),
        "html_url": payload.get("html_url", "https://github.com/nutelex/B2B-Server/releases/latest"),
        "name": payload.get("name", latest_tag),
    }
