"""Backend abstraction for WGFMU control."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import json

import pandas as pd


class WgfmuBackend(ABC):
    """Abstract backend interface for WGFMU workflows.

    The real implementation will eventually wrap the official WGFMU instrument
    library. For now we keep the interface close to the notebook prototype.
    """

    def __init__(self):
        self.session_opened = False

    @abstractmethod
    def open_session(self, resource: str):
        raise NotImplementedError

    @abstractmethod
    def close_session(self):
        raise NotImplementedError

    @abstractmethod
    def initialize(self):
        raise NotImplementedError

    @abstractmethod
    def clear(self):
        raise NotImplementedError

    @abstractmethod
    def set_timeout(self, timeout_s: float):
        raise NotImplementedError

    @abstractmethod
    def get_channel_ids(self) -> list[int]:
        raise NotImplementedError

    @abstractmethod
    def get_error_summary(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_warning_summary(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def treat_warnings_as_errors(self, level: str):
        raise NotImplementedError

    @abstractmethod
    def create_pattern(self, pattern: str, init_v: float):
        raise NotImplementedError

    @abstractmethod
    def add_vector(self, pattern: str, dtime_s: float, voltage: float):
        raise NotImplementedError

    @abstractmethod
    def set_measure_event(
        self,
        pattern: str,
        event: str,
        time_s: float,
        points: int,
        interval_s: float,
        average_s: float,
        raw_data_mode: str,
    ):
        raise NotImplementedError

    @abstractmethod
    def add_sequence(self, chan_id: int, pattern: str, count: int):
        raise NotImplementedError

    @abstractmethod
    def export_ascii(self, filepath: str):
        raise NotImplementedError

    @abstractmethod
    def set_operation_mode(self, chan_id: int, mode: str):
        raise NotImplementedError

    @abstractmethod
    def set_force_voltage_range(self, chan_id: int, rng: str):
        raise NotImplementedError

    @abstractmethod
    def set_measure_enabled(self, chan_id: int, enabled: bool):
        raise NotImplementedError

    @abstractmethod
    def set_measure_mode(self, chan_id: int, mode: str):
        raise NotImplementedError

    @abstractmethod
    def set_measure_current_range(self, chan_id: int, rng: str):
        raise NotImplementedError

    @abstractmethod
    def set_measure_voltage_range(self, chan_id: int, rng: str):
        raise NotImplementedError

    @abstractmethod
    def connect(self, chan_id: int):
        raise NotImplementedError

    @abstractmethod
    def disconnect(self, chan_id: int):
        raise NotImplementedError

    @abstractmethod
    def execute(self):
        raise NotImplementedError

    @abstractmethod
    def wait_until_completed(self):
        raise NotImplementedError

    @abstractmethod
    def get_measure_value_size(self, chan_id: int) -> tuple[int, int]:
        raise NotImplementedError

    @abstractmethod
    def get_measure_values(self, chan_id: int) -> pd.DataFrame:
        raise NotImplementedError


class DummyWgfmuBackend(WgfmuBackend):
    """Local-development backend with deterministic fake data."""

    def __init__(self):
        super().__init__()
        self._resource: str | None = None
        self._timeout_s: float | None = None
        self._channels = [101, 102]
        self._connected: set[int] = set()
        self._patterns: dict[str, dict] = {}
        self._events: dict[str, dict] = {}
        self._sequences: list[dict] = []
        self._measure_mode_by_channel: dict[int, str] = {}
        self._warnings_as_errors_level: str | None = None

    def open_session(self, resource: str):
        self._resource = resource
        self.session_opened = True
        return 0

    def close_session(self):
        self.session_opened = False
        self._connected.clear()
        return 0

    def initialize(self):
        return 0

    def clear(self):
        self._patterns.clear()
        self._events.clear()
        self._sequences.clear()
        return 0

    def set_timeout(self, timeout_s: float):
        self._timeout_s = timeout_s
        return 0

    def get_channel_ids(self) -> list[int]:
        return list(self._channels)

    def get_error_summary(self) -> str:
        return ""

    def get_warning_summary(self) -> str:
        return ""

    def treat_warnings_as_errors(self, level: str):
        self._warnings_as_errors_level = level
        return 0

    def create_pattern(self, pattern: str, init_v: float):
        self._patterns[pattern] = {"init_v": init_v, "vectors": []}
        return 0

    def add_vector(self, pattern: str, dtime_s: float, voltage: float):
        self._patterns.setdefault(pattern, {"init_v": 0.0, "vectors": []})
        self._patterns[pattern]["vectors"].append({"dtime_s": dtime_s, "voltage": voltage})
        return 0

    def set_measure_event(
        self,
        pattern: str,
        event: str,
        time_s: float,
        points: int,
        interval_s: float,
        average_s: float,
        raw_data_mode: str,
    ):
        self._events[event] = {
            "pattern": pattern,
            "time_s": time_s,
            "points": points,
            "interval_s": interval_s,
            "average_s": average_s,
            "raw_data_mode": raw_data_mode,
        }
        return 0

    def add_sequence(self, chan_id: int, pattern: str, count: int):
        self._sequences.append({"chan_id": chan_id, "pattern": pattern, "count": count})
        return 0

    def export_ascii(self, filepath: str):
        payload = {
            "resource": self._resource,
            "timeout_s": self._timeout_s,
            "patterns": self._patterns,
            "events": self._events,
            "sequences": self._sequences,
            "warnings_as_errors": self._warnings_as_errors_level,
        }
        Path(filepath).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    def set_operation_mode(self, chan_id: int, mode: str):
        return 0

    def set_force_voltage_range(self, chan_id: int, rng: str):
        return 0

    def set_measure_enabled(self, chan_id: int, enabled: bool):
        return 0

    def set_measure_mode(self, chan_id: int, mode: str):
        self._measure_mode_by_channel[chan_id] = mode.upper()
        return 0

    def set_measure_current_range(self, chan_id: int, rng: str):
        return 0

    def set_measure_voltage_range(self, chan_id: int, rng: str):
        return 0

    def connect(self, chan_id: int):
        self._connected.add(chan_id)
        return 0

    def disconnect(self, chan_id: int):
        self._connected.discard(chan_id)
        return 0

    def execute(self):
        return 0

    def wait_until_completed(self):
        return 0

    def get_measure_value_size(self, chan_id: int) -> tuple[int, int]:
        mode = self._measure_mode_by_channel.get(chan_id, "CURRENT")
        total = 8 if mode == "VOLTAGE" else 20
        return total, total

    def get_measure_values(self, chan_id: int) -> pd.DataFrame:
        mode = self._measure_mode_by_channel.get(chan_id, "CURRENT")
        total, _ = self.get_measure_value_size(chan_id)
        time_s = [idx * 2e-7 for idx in range(total)]
        if mode == "VOLTAGE":
            value = [0.1 * idx for idx in range(total)]
        else:
            value = [1e-9 + (3e-6 - 1e-9) * idx / max(total - 1, 1) for idx in range(total)]
        return pd.DataFrame({"time_s": time_s, "value": value})
