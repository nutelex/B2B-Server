from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

try:
    import mido
except ImportError:  # pragma: no cover - optional dependency in dev
    mido = None


@dataclass
class MidiPortSnapshot:
    inputs: list[str]
    outputs: list[str]


class MidiBridge:
    def __init__(
        self,
        on_local_message: Callable[[dict], None],
        on_status: Callable[[str], None],
    ) -> None:
        self.on_local_message = on_local_message
        self.on_status = on_status
        self.input_name = ""
        self.output_name = ""
        self._input_port = None
        self._output_port = None
        self._input_thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def available(self) -> bool:
        return mido is not None

    def list_ports(self) -> MidiPortSnapshot:
        if not self.available:
            return MidiPortSnapshot(inputs=[], outputs=[])
        return MidiPortSnapshot(
            inputs=list(mido.get_input_names()),
            outputs=list(mido.get_output_names()),
        )

    def start_input(self, port_name: str) -> None:
        if not self.available:
            raise RuntimeError("Support MIDI non installe.")
        self.stop_input()
        self.input_name = port_name
        self._input_port = mido.open_input(port_name)
        self._running = True
        self._input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self._input_thread.start()
        self.on_status(f"Entree MIDI active : {port_name}")

    def stop_input(self) -> None:
        self._running = False
        if self._input_thread:
            self._input_thread.join(timeout=0.5)
            self._input_thread = None
        if self._input_port:
            self._input_port.close()
            self._input_port = None
        self.input_name = ""

    def set_output(self, port_name: str) -> None:
        if not self.available:
            raise RuntimeError("Support MIDI non installe.")
        if self._output_port:
            self._output_port.close()
            self._output_port = None
        self.output_name = ""
        if not port_name:
            self.on_status("Sortie MIDI distante desactivee.")
            return
        self._output_port = mido.open_output(port_name)
        self.output_name = port_name
        self.on_status(f"Sortie MIDI distante : {port_name}")

    def send_remote_message(self, payload: dict) -> None:
        if not self.available or not self._output_port:
            return
        try:
            message = mido.Message.from_dict(payload)
        except Exception as exc:
            self.on_status(f"Message MIDI distant invalide : {exc}")
            return
        self._output_port.send(message)

    def shutdown(self) -> None:
        self.stop_input()
        if self._output_port:
            self._output_port.close()
            self._output_port = None
        self.output_name = ""

    def _input_loop(self) -> None:
        while self._running and self._input_port:
            for message in self._input_port.iter_pending():
                payload = message.dict()
                payload["type"] = message.type
                self.on_local_message(payload)
            time.sleep(0.005)
