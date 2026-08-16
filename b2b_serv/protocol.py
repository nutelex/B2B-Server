from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Message:
    kind: str
    payload: dict[str, Any]

    def to_bytes(self) -> bytes:
        return (json.dumps({"kind": self.kind, "payload": self.payload}) + "\n").encode("utf-8")

    @staticmethod
    def from_bytes(raw: bytes) -> "Message":
        data = json.loads(raw.decode("utf-8").strip())
        return Message(kind=data["kind"], payload=data.get("payload", {}))


def encode_link(relay_url: str, relay_port: int, code: str) -> str:
    return f"b2bserv://join?relay={relay_url}&port={relay_port}&code={code}"
