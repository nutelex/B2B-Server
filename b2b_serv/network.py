from __future__ import annotations

import json
import random
import string
import threading
import time
from typing import Callable, Optional
from urllib import error, parse, request

from .protocol import encode_link


def generate_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


class SessionEngine:
    def __init__(self, on_event: Callable[[str, dict], None]) -> None:
        self.on_event = on_event
        self.running = False
        self.role = "idle"
        self.code = ""
        self.sender_name = "DJ"
        self.relay_base_url = ""
        self.peer_name = ""
        self._poll_thread: Optional[threading.Thread] = None

    def create_session(self, username: str, local_relay_base_url: str, public_relay_url: str) -> tuple[str, str]:
        self.stop()
        self.role = "host"
        self.sender_name = username
        self.relay_base_url = local_relay_base_url.rstrip("/")
        self.code = generate_code()
        self._post("/host", {"name": username, "code": self.code})
        self.running = True
        self._start_polling()
        return self.code, encode_link(public_relay_url.rstrip("/"), 443, self.code)

    def join_session(self, username: str, relay_base_url: str, code: str) -> None:
        self.stop()
        self.role = "guest"
        self.sender_name = username
        self.relay_base_url = relay_base_url.rstrip("/")
        self.code = code
        self._post("/join", {"name": username, "code": code})
        self.running = True
        self._start_polling()

    def approve_pending(self) -> None:
        self._post("/approve", {"code": self.code})

    def reject_pending(self) -> None:
        self._post("/reject", {"code": self.code})

    def send_control(self, deck: str, control: str, value: float) -> None:
        if not self.running or not self.code:
            return
        self._post(
            "/control",
            {
                "code": self.code,
                "role": self.role,
                "event": {
                    "from": self.sender_name,
                    "deck": deck,
                    "control": control,
                    "value": value,
                },
            },
        )

    def stop(self) -> None:
        self.running = False
        self.peer_name = ""

    def _start_polling(self) -> None:
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self) -> None:
        while self.running:
            try:
                query = parse.urlencode({"code": self.code, "role": self.role})
                result = self._get(f"/poll?{query}")
                for event in result.get("events", []):
                    self._handle_message(event["kind"], event.get("payload", {}))
            except Exception as exc:
                self.on_event("connection_error", {"message": str(exc)})
                self.running = False
                return
            time.sleep(0.25)

    def _handle_message(self, kind: str, payload: dict) -> None:
        if kind == "approval_needed":
            self.on_event("approval_needed", {"name": payload["name"]})
        elif kind == "join_approved":
            self.peer_name = payload.get("peer_name", "")
            self.on_event("peer_connected", {"name": self.peer_name})
        elif kind == "peer_connected":
            self.peer_name = payload.get("name", payload.get("peer_name", ""))
            self.on_event("peer_connected", {"name": self.peer_name})
        elif kind == "join_rejected":
            self.on_event("join_rejected", {})
        elif kind == "remote_control":
            self.on_event(
                "remote_control",
                {
                    "name": payload.get("from", "Remote DJ"),
                    "deck": payload["deck"],
                    "control": payload["control"],
                    "value": payload["value"],
                },
            )

    def _post(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.relay_base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._read(req)

    def _get(self, path: str) -> dict:
        req = request.Request(self.relay_base_url + path, method="GET")
        return self._read(req)

    def _read(self, req: request.Request) -> dict:
        try:
            with request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError("Connexion au relais impossible.") from exc
        if not result.get("ok", False):
            raise RuntimeError(result.get("message", "Erreur de session."))
        return result
