from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

import pyvisa


@dataclass
class VisaConfig:
    """
    VISA session configuration.
    resource: VISA resource string, e.g. "GPIB0::17::INSTR"
    backend: None -> default (prefer IVI), "@py" -> pyvisa-py
    """
    resource: str
    timeout_ms: int = 10000
    write_termination: Optional[str] = "\r\n"
    read_termination: Optional[str] = "\r\n"
    send_end: bool = True
    backend: Optional[str] = None


class VisaSession:
    """
    Reliable PyVISA session wrapper.

    Responsibility boundary:
      - Handles connect / disconnect
      - Handles write/query with stable terminators
      - Does NOT contain B1500-specific command logic
    """

    def __init__(self, cfg: VisaConfig):
        self.cfg = cfg
        self.rm: Optional[pyvisa.ResourceManager] = None
        self.inst: Optional[Any] = None

    def open(self) -> "VisaSession":
        if self.cfg.backend:
            self.rm = pyvisa.ResourceManager(self.cfg.backend)
        else:
            self.rm = pyvisa.ResourceManager()

        self.inst = self.rm.open_resource(self.cfg.resource)
        self.inst.timeout = int(self.cfg.timeout_ms)
        self.inst.send_end = bool(self.cfg.send_end)
        self.inst.write_termination = self.cfg.write_termination
        self.inst.read_termination = self.cfg.read_termination
        return self

    def close(self) -> None:
        if self.inst is not None:
            try:
                self.inst.close()
            finally:
                self.inst = None

        if self.rm is not None:
            try:
                self.rm.close()
            finally:
                self.rm = None

    def __enter__(self) -> "VisaSession":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def write(self, cmd: str) -> None:
        if self.inst is None:
            raise RuntimeError("VISA session is not opened.")
        self.inst.write(cmd)

    def query(self, cmd: str) -> str:
        if self.inst is None:
            raise RuntimeError("VISA session is not opened.")
        resp = self.inst.query(cmd)



