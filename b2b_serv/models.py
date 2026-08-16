from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PeerInfo:
    name: str
    ip: str
    tcp_port: int
    udp_port: int


@dataclass
class SessionState:
    mode: str = "idle"
    username: str = "DJ"
    session_code: str = ""
    host_ip: str = ""
    tcp_port: int = 45900
    udp_port: int = 45901
    peer: Optional[PeerInfo] = None
    approved: bool = False
    activity_log: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.activity_log.append(message)
        self.activity_log[:] = self.activity_log[-200:]
