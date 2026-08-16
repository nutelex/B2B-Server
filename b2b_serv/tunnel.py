from __future__ import annotations

import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .runtime import app_base_dir, bundled_path


class CloudflaredTunnel:
    def __init__(self, on_log: Callable[[str], None]) -> None:
        self.on_log = on_log
        self.process: Optional[subprocess.Popen[str]] = None
        self.public_url: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self.last_lines: list[str] = []

    def start(self, local_port: int, timeout: float = 20.0) -> str:
        self.stop()
        executable = self._resolve_executable()
        command = [str(executable), "tunnel", "--url", f"http://127.0.0.1:{local_port}"]
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._thread = threading.Thread(target=self._read_output, daemon=True)
        self._thread.start()

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.public_url:
                return self.public_url
            if self.process.poll() is not None:
                break
            time.sleep(0.1)

        details = self._build_error_details()
        self.stop()
        raise RuntimeError(details)

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        self.public_url = None

    def _read_output(self) -> None:
        assert self.process is not None
        assert self.process.stdout is not None
        for line in self.process.stdout:
            text = line.strip()
            if text:
                self.on_log(text)
                self.last_lines.append(text)
                self.last_lines[:] = self.last_lines[-10:]
            if not self.public_url:
                match = re.search(r"https://[a-zA-Z0-9.-]+trycloudflare\.com", text)
                if match:
                    self.public_url = match.group(0)

    def _build_error_details(self) -> str:
        if self.process and self.process.poll() is not None:
            code = self.process.returncode
            if self.last_lines:
                return f"Impossible d'ouvrir le tunnel automatiquement. Code cloudflared: {code}. Detail: {self.last_lines[-1]}"
            return f"Impossible d'ouvrir le tunnel automatiquement. Code cloudflared: {code}."
        if self.last_lines:
            return f"Impossible d'ouvrir le tunnel automatiquement. Dernier message: {self.last_lines[-1]}"
        return "Impossible d'ouvrir le tunnel automatiquement. Verifie cloudflared, la connexion internet et les restrictions reseau."

    def _resolve_executable(self) -> Path:
        candidates = [
            app_base_dir() / "cloudflared.exe",
            bundled_path("cloudflared.exe"),
            Path(r"C:\WINDOWS\system32\cloudflared.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError("cloudflared.exe introuvable. Ajoute-le a cote de l'application.")
