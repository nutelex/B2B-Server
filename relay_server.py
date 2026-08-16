from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse


@dataclass
class Session:
    code: str
    host_name: str
    guest_name: str = ""
    pending_name: str = ""
    queues: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))


class RelayState:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.lock = threading.Lock()

    def host_session(self, code: str, host_name: str) -> dict[str, Any]:
        with self.lock:
            self.sessions[code] = Session(code=code, host_name=host_name)
        return {"ok": True, "code": code}

    def join_session(self, code: str, guest_name: str) -> dict[str, Any]:
        with self.lock:
            session = self.sessions.get(code)
            if not session:
                return {"ok": False, "message": "Session introuvable."}
            if session.guest_name or session.pending_name:
                return {"ok": False, "message": "Session deja occupee."}
            session.pending_name = guest_name
            session.queues["host"].append({"kind": "approval_needed", "payload": {"name": guest_name}})
        return {"ok": True}

    def approve_join(self, code: str) -> dict[str, Any]:
        with self.lock:
            session = self.sessions.get(code)
            if not session or not session.pending_name:
                return {"ok": False, "message": "Aucune demande en attente."}
            session.guest_name = session.pending_name
            session.pending_name = ""
            session.queues["host"].append({"kind": "peer_connected", "payload": {"name": session.guest_name}})
            session.queues["guest"].append({"kind": "join_approved", "payload": {"peer_name": session.host_name}})
        return {"ok": True}

    def reject_join(self, code: str) -> dict[str, Any]:
        with self.lock:
            session = self.sessions.get(code)
            if not session or not session.pending_name:
                return {"ok": False, "message": "Aucune demande en attente."}
            session.pending_name = ""
            session.queues["guest"].append({"kind": "join_rejected", "payload": {}})
        return {"ok": True}

    def send_control(self, code: str, sender_role: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            session = self.sessions.get(code)
            if not session:
                return {"ok": False, "message": "Session introuvable."}
            target = "guest" if sender_role == "host" else "host"
            session.queues[target].append({"kind": "remote_control", "payload": payload})
        return {"ok": True}

    def poll(self, code: str, role: str) -> dict[str, Any]:
        with self.lock:
            session = self.sessions.get(code)
            if not session:
                return {"ok": False, "message": "Session introuvable.", "events": []}
            events = list(session.queues[role])
            session.queues[role].clear()
        return {"ok": True, "events": events}


class RelayRequestHandler(BaseHTTPRequestHandler):
    state: RelayState

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, {"ok": True})
            return
        if parsed.path == "/poll":
            query = parse_qs(parsed.query)
            code = query.get("code", [""])[0]
            role = query.get("role", [""])[0]
            self._send_json(200, self.state.poll(code, role))
            return
        self._send_json(404, {"ok": False, "message": "Not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8"))

        if self.path == "/host":
            result = self.state.host_session(payload["code"], payload["name"])
        elif self.path == "/join":
            result = self.state.join_session(payload["code"], payload["name"])
        elif self.path == "/approve":
            result = self.state.approve_join(payload["code"])
        elif self.path == "/reject":
            result = self.state.reject_join(payload["code"])
        elif self.path == "/control":
            result = self.state.send_control(payload["code"], payload["role"], payload["event"])
        else:
            self._send_json(404, {"ok": False, "message": "Not found"})
            return

        self._send_json(200, result)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LocalRelayServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 47000) -> None:
        self.host = host
        self.port = port
        self.state = RelayState()
        handler = type("BoundRelayHandler", (RelayRequestHandler,), {})
        handler.state = self.state
        self.server = ThreadingHTTPServer((host, port), handler)
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        deadline = time.time() + 2
        while time.time() < deadline:
            if self.thread.is_alive():
                return
            time.sleep(0.05)

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)


if __name__ == "__main__":
    relay = LocalRelayServer(host="0.0.0.0", port=47000)
    relay.start()
    print("Relay HTTP listening on 0.0.0.0:47000")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        relay.stop()
