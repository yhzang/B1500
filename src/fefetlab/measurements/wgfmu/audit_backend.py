"""Hardware-free WGFMU audit backend for dry-run experiment checks.

The class implements only the small backend subset used by stop-gated WGFMU
scripts.  It never opens VISA and never loads ``wgfmu.dll``; instead it audits
pattern timing, synchronized Gate/Drain sequences, measurement events, and the
B1530A vector-budget envelope before producing deterministic sample frames.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd


class AuditBackend:
    """Dry-run backend for WGFMU two-channel stage scripts.

    Parameters are explicit so a fixture can choose Gate/Drain channels without
    relying on the yhzang default wiring.  The returned current levels are small
    deterministic placeholders for contract tests only; they are not a device
    model.
    """

    def __init__(
        self,
        *,
        gate_ch: int = 202,
        drain_ch: int = 201,
        channels: Iterable[int] = (201, 202, 301, 302),
        max_vectors_per_pattern: int = 2048,
    ):
        if int(gate_ch) == int(drain_ch):
            raise ValueError("gate_ch and drain_ch must be different")
        self.gate_ch = int(gate_ch)
        self.drain_ch = int(drain_ch)
        self.max_vectors_per_pattern = int(max_vectors_per_pattern)
        self.session_opened = False
        self._channels = [int(ch) for ch in channels]
        self._patterns: dict[str, dict] = {}
        self._events: dict[str, dict] = {}
        self._sequences: list[dict] = []
        self._connected: set[int] = set()
        self._last_values: dict[int, pd.DataFrame] = {}
        self.execute_count = 0
        self.max_vectors_seen = 0
        self.timeout_s = None

    def open_session(self, resource: str):
        self.session_opened = True
        return 0

    def close_session(self):
        self.session_opened = False
        return 0

    def load(self):
        return None

    def initialize(self):
        return 0

    def clear(self):
        self._patterns.clear()
        self._events.clear()
        self._sequences.clear()
        self._last_values.clear()
        return 0

    def set_timeout(self, timeout_s: float):
        self.timeout_s = float(timeout_s)
        return 0

    def get_channel_ids(self) -> list[int]:
        return list(self._channels)

    def get_error_summary(self) -> str:
        return ""

    def get_warning_summary(self) -> str:
        return ""

    def treat_warnings_as_errors(self, level: str):
        return 0

    def create_pattern(self, pattern: str, init_v: float):
        self._patterns[pattern] = {"init_v": float(init_v), "vectors": []}
        return 0

    def add_vector(self, pattern: str, dtime_s: float, voltage: float):
        if dtime_s <= 0:
            raise ValueError(f"non-positive dtime in {pattern}: {dtime_s}")
        self._patterns.setdefault(pattern, {"init_v": 0.0, "vectors": []})
        self._patterns[pattern]["vectors"].append((float(dtime_s), float(voltage)))
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
        if points <= 0 or interval_s <= 0 or average_s <= 0:
            raise ValueError(
                f"bad measure event {event}: points={points}, interval={interval_s}, average={average_s}"
            )
        if average_s >= interval_s:
            raise ValueError(f"average_s must be < interval_s for {event}")
        self._events[event] = {
            "pattern": pattern,
            "time_s": float(time_s),
            "points": int(points),
            "interval_s": float(interval_s),
            "average_s": float(average_s),
            "raw_data_mode": raw_data_mode,
        }
        return 0

    def add_sequence(self, chan_id: int, pattern: str, count: int):
        self._sequences.append({"chan_id": int(chan_id), "pattern": pattern, "count": int(count)})
        return 0

    def export_ascii(self, filepath: str):
        return 0

    def set_operation_mode(self, chan_id: int, mode: str):
        return 0

    def set_force_voltage_range(self, chan_id: int, rng: str):
        return 0

    def set_measure_enabled(self, chan_id: int, enabled: bool):
        return 0

    def set_measure_mode(self, chan_id: int, mode: str):
        return 0

    def set_measure_current_range(self, chan_id: int, rng: str):
        return 0

    def set_measure_voltage_range(self, chan_id: int, rng: str):
        return 0

    def connect(self, chan_id: int):
        self._connected.add(int(chan_id))
        return 0

    def disconnect(self, chan_id: int):
        self._connected.discard(int(chan_id))
        return 0

    def _pattern_duration(self, name: str) -> float:
        return sum(dt for dt, _v in self._patterns.get(name, {}).get("vectors", []))

    def _validate_sequences(self) -> None:
        if len(self._sequences) != 2:
            raise RuntimeError(f"expected 2 synchronized sequences, got {self._sequences}")
        sequence_channels = {int(seq["chan_id"]) for seq in self._sequences}
        expected_channels = {self.gate_ch, self.drain_ch}
        if sequence_channels != expected_channels:
            raise RuntimeError(f"expected Gate/Drain sequences {sorted(expected_channels)}, got {sorted(sequence_channels)}")
        durations = [self._pattern_duration(seq["pattern"]) for seq in self._sequences]
        if not math.isclose(durations[0], durations[1], rel_tol=0, abs_tol=2e-12):
            raise RuntimeError(f"gate/drain duration mismatch: {durations}")

    def _validate_vector_budget(self) -> None:
        for name, payload in self._patterns.items():
            n_vec = len(payload.get("vectors", []))
            self.max_vectors_seen = max(self.max_vectors_seen, n_vec)
            if n_vec > self.max_vectors_per_pattern:
                raise RuntimeError(f"pattern {name} has {n_vec} vectors > {self.max_vectors_per_pattern}")

    def execute(self):
        self.execute_count += 1
        self._validate_sequences()
        self._validate_vector_budget()
        self._last_values.clear()
        for seq in self._sequences:
            ch = int(seq["chan_id"])
            pat = seq["pattern"]
            rows = []
            base = 8e-9 if ch == self.drain_ch else 2e-7
            step = 1e-10 if ch == self.drain_ch else 2e-9
            for ev in sorted(self._events.values(), key=lambda e: e["time_s"]):
                if ev["pattern"] != pat:
                    continue
                for k in range(ev["points"]):
                    t = ev["time_s"] + k * ev["interval_s"]
                    rows.append({"time_s": t, "value": base + (k + 1) * step})
            self._last_values[ch] = pd.DataFrame(rows, columns=["time_s", "value"])
        return 0

    def wait_until_completed(self):
        return 0

    def get_measure_value_size(self, chan_id: int) -> tuple[int, int]:
        n = len(self._last_values.get(int(chan_id), pd.DataFrame()))
        return n, n

    def get_measure_values(self, chan_id: int) -> pd.DataFrame:
        return self._last_values.get(int(chan_id), pd.DataFrame(columns=["time_s", "value"])).copy()
