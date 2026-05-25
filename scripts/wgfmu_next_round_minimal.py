#!/usr/bin/env python
"""Stop-gated minimal WGFMU next-round runner for yhzang B1500.

Stages:
  S0: open/fixture smoke, no write pulse, low read-only pulses only
  S1: device read-only baseline, no write pulse
  E1: RAWD QUICK300ms v2, ±5 V / 100 us write, delay to 300 ms
  E2: minimal read-disturb, A1/A100/C1/C10 only, skips C100
  E5: read-window visibility grid, Vg×Vd grid after write, two delays

Default mode is dry-run with an in-process audit backend. Dry-run never opens
VISA, never loads wgfmu.dll, and never drives hardware outputs. Live mode must
be requested one stage at a time using --live --confirm <STAGE>.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GATE_CH = 202   # hardcoded: yhzang wiring, do not autodetect
DRAIN_CH = 201  # hardcoded: yhzang wiring, do not autodetect
ALLOWED_CHANNELS = {201, 202, 301}
FORBIDDEN_CHANNELS = {302}

VG_READS = [-0.2, 0.0, 0.2]
VD_READ = 0.05
T_RF = 100e-9
T_RESET = 1e-3
T_WRITE = 100e-6
T_READ = 5e-6
T_NEUTRAL = 100e-6
N_PTS = 5
V_ERS = +5.0
V_PGM = -5.0
DELAYS_QUICK300 = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 3e-2, 1e-1, 3e-1]
DELAYS_FULL = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1.0, 3.0, 10.0]
E2_MINIMAL_COMBOS = [
    ("ERS", "A", 1),
    ("PGM", "A", 1),
    ("ERS", "A", 100),
    ("PGM", "A", 100),
    ("ERS", "C", 1),
    ("PGM", "C", 1),
    ("ERS", "C", 10),
    ("PGM", "C", 10),
]

# Wide-Vg read grid for pFeFET: include Vg=-1.0V, otherwise the main MW
# can be invisible in deep subthreshold near Vg≈0.
VG_E5 = [-1.0, -0.7, -0.4, -0.2, 0.0, 0.2]
VD_E5 = [0.01, 0.05, 0.10, 0.50]
DELAYS_E5 = [10e-6, 1.0]
VG_CYCLE = [-1.0, -0.7, -0.4]
CYCLE_DELAY = 10e-6

FIELDNAMES = [
    "timestamp_iso", "stage", "device_id", "geometry", "sequence_id", "repeat_index",
    "state_target", "delay_s", "dose_mode", "n_read", "Vg_read_V", "Vd_read_V",
    "Id_mean_A", "Id_std_A", "Ig_mean_A", "Ig_std_A", "n_d", "n_g", "note",
]


class StopGate(RuntimeError):
    """Raised when a live run must stop before the next stage/shot."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class StageSummary:
    stage: str
    out_csv: Path
    rows: int
    max_abs_id_a: float
    max_abs_ig_a: float
    report_code: str


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _slug(s: str) -> str:
    keep = []
    for ch in str(s):
        keep.append(ch if ch.isalnum() or ch in ("-", "_") else "_")
    out = "".join(keep).strip("_")
    return out or "device"


# ---------------------------------------------------------------------------
# Dry-run audit backend. It implements the subset used below and records enough
# state to catch vector-budget, timing, and zero/negative-dt mistakes.
class AuditBackend:
    def __init__(self):
        self.session_opened = False
        self._channels = [201, 202, 301, 302]
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

    def set_measure_event(self, pattern: str, event: str, time_s: float, points: int,
                          interval_s: float, average_s: float, raw_data_mode: str):
        if points <= 0 or interval_s <= 0 or average_s <= 0:
            raise ValueError(f"bad measure event {event}: points={points}, interval={interval_s}, average={average_s}")
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

    def execute(self):
        self.execute_count += 1
        if len(self._sequences) != 2:
            raise RuntimeError(f"expected 2 synchronized sequences, got {self._sequences}")
        durations = [self._pattern_duration(seq["pattern"]) for seq in self._sequences]
        if not math.isclose(durations[0], durations[1], rel_tol=0, abs_tol=2e-12):
            raise RuntimeError(f"gate/drain duration mismatch: {durations}")
        for name, payload in self._patterns.items():
            n_vec = len(payload.get("vectors", []))
            self.max_vectors_seen = max(self.max_vectors_seen, n_vec)
            if n_vec > 2048:
                raise RuntimeError(f"pattern {name} has {n_vec} vectors > 2048")
        self._last_values.clear()
        for seq in self._sequences:
            ch = int(seq["chan_id"])
            pat = seq["pattern"]
            rows = []
            base = 8e-9 if ch == DRAIN_CH else 2e-7
            for ev in sorted(self._events.values(), key=lambda e: e["time_s"]):
                if ev["pattern"] != pat:
                    continue
                for k in range(ev["points"]):
                    t = ev["time_s"] + k * ev["interval_s"]
                    val = base + (k + 1) * (1e-10 if ch == DRAIN_CH else 2e-9)
                    rows.append({"time_s": t, "value": val})
            self._last_values[ch] = pd.DataFrame(rows, columns=["time_s", "value"])
        return 0

    def wait_until_completed(self):
        return 0

    def get_measure_value_size(self, chan_id: int) -> tuple[int, int]:
        n = len(self._last_values.get(int(chan_id), pd.DataFrame()))
        return n, n

    def get_measure_values(self, chan_id: int) -> pd.DataFrame:
        return self._last_values.get(int(chan_id), pd.DataFrame(columns=["time_s", "value"])).copy()


# ---------------------------------------------------------------------------
def _validate_channels(channel_ids: Iterable[int]) -> None:
    ids = set(int(x) for x in channel_ids)
    if GATE_CH not in ids or DRAIN_CH not in ids:
        raise StopGate("SETUP_STOP_CHANNEL_MISSING", f"Gate={GATE_CH}, Drain={DRAIN_CH}, detected={sorted(ids)}")
    bad = [ch for ch in (GATE_CH, DRAIN_CH) if ch in FORBIDDEN_CHANNELS or ch not in ALLOWED_CHANNELS]
    if bad:
        raise StopGate("SETUP_STOP_BAD_CHANNEL", f"bad channel(s): {bad}")


def make_backend(live: bool):
    if not live:
        b = AuditBackend()
        b.open_session("DUMMY::WGFMU")
        _validate_channels(b.get_channel_ids())
        print("DRY_RUN_BACKEND: no VISA, no DLL, no hardware output")
        print(f"CHANNELS_OK: Gate={GATE_CH}, Drain={DRAIN_CH}, detected={b.get_channel_ids()}")
        return b, "DUMMY::WGFMU"

    from fefetlab.measurements.wgfmu import (  # local import keeps dry-run hardware-free
        RealWgfmuBackend,
        autodetect_visa_addr,
        clear_b1500_status_for_wgfmu_open,
        ensure_wgfmu_dll_path,
    )

    dll = ensure_wgfmu_dll_path()
    print(f"WGFMU_DLL: {dll}")
    visa_addr = (os.environ.get("B1500_VISA_ADDR") or "").strip()
    if visa_addr:
        print(f"B1500_VISA_ADDR_OVERRIDE: {visa_addr}")
    else:
        visa_addr = autodetect_visa_addr("B1500")
    print(f"B1500_VISA: {visa_addr}")
    backend = RealWgfmuBackend()
    backend.load()
    idn = clear_b1500_status_for_wgfmu_open(visa_addr)
    print(f"B1500 preflight ERRX drain OK: {idn}")
    backend.open_session(visa_addr)
    backend.set_timeout(30.0)
    channel_ids = backend.get_channel_ids()
    print(f"WGFMU_CHANNELS: {channel_ids}")
    _validate_channels(channel_ids)
    print(f"CHANNELS_OK: Gate={GATE_CH}, Drain={DRAIN_CH}")
    return backend, visa_addr


def _safe_disconnect(backend, *channels: int) -> None:
    for ch in channels:
        try:
            backend.disconnect(ch)
        except Exception:
            pass


def _configure_and_run_phase(backend, *, measure: bool, timeout_s: float = 30.0):
    backend.add_sequence(GATE_CH, "gp", 1)
    backend.add_sequence(DRAIN_CH, "dp", 1)
    backend.initialize()
    for ch, force_range in [(GATE_CH, "AUTO"), (DRAIN_CH, "3V")]:
        backend.set_operation_mode(ch, "FASTIV")
        backend.set_force_voltage_range(ch, force_range)
        backend.set_measure_enabled(ch, True)
        backend.set_measure_mode(ch, "CURRENT")
        backend.set_measure_current_range(ch, "1MA")
    backend.set_timeout(timeout_s)
    backend.connect(GATE_CH)
    backend.connect(DRAIN_CH)
    try:
        backend.execute()
        backend.wait_until_completed()
        if not measure:
            return None, None
        g_df = backend.get_measure_values(GATE_CH)
        d_df = backend.get_measure_values(DRAIN_CH)
        return g_df, d_df
    finally:
        _safe_disconnect(backend, GATE_CH, DRAIN_CH)


def _summarize_windows(g_df: pd.DataFrame, d_df: pd.DataFrame, windows: list[dict]) -> list[dict]:
    g_t = g_df["time_s"].to_numpy(dtype=float) if len(g_df) else np.array([])
    g_v = g_df["value"].to_numpy(dtype=float) if len(g_df) else np.array([])
    d_t = d_df["time_s"].to_numpy(dtype=float) if len(d_df) else np.array([])
    d_v = d_df["value"].to_numpy(dtype=float) if len(d_df) else np.array([])
    out = []
    for w in windows:
        t0, t1 = w["t0"], w["t1"]
        gm = (g_t >= t0) & (g_t <= t1)
        dm = (d_t >= t0) & (d_t <= t1)
        g_sub = g_v[gm]
        d_sub = d_v[dm]
        out.append({
            "Vg_read_V": float(w["vg"]),
            "Vd_read_V": float(w["vd"]),
            "Id_mean_A": float(np.nanmean(d_sub)) if len(d_sub) else float("nan"),
            "Id_std_A": float(np.nanstd(d_sub)) if len(d_sub) > 1 else 0.0,
            "Ig_mean_A": float(np.nanmean(g_sub)) if len(g_sub) else float("nan"),
            "Ig_std_A": float(np.nanstd(g_sub)) if len(g_sub) > 1 else 0.0,
            "n_d": int(len(d_sub)),
            "n_g": int(len(g_sub)),
        })
    return out


def _build_read_phase(backend, *, vg_reads: list[float], vd_read: float, t_prefix: float = T_NEUTRAL,
                      t_read: float = T_READ, n_pts: int = N_PTS,
                      event_offset_s: float = 0.0) -> list[dict]:
    guard = min(200e-9, t_read * 0.2)
    meas_window = max(t_read - guard, t_read * 0.5)
    interval = meas_window / max(n_pts, 1)
    average = min(200e-9, interval * 0.8)
    gap = 1e-6

    windows = []
    t_cursor = 0.0
    if t_prefix > 0:
        backend.add_vector("gp", t_prefix, 0.0)
        t_cursor += t_prefix

    for i, vg in enumerate(vg_reads):
        backend.add_vector("gp", T_RF, float(vg)); t_cursor += T_RF
        read_start = t_cursor
        backend.add_vector("gp", t_read, float(vg)); t_cursor += t_read
        backend.add_vector("gp", T_RF, 0.0); t_cursor += T_RF
        windows.append({
            "idx": i,
            "vg": float(vg),
            "vd": float(vd_read),
            "t0": event_offset_s + read_start + guard,
            "t1": event_offset_s + read_start + t_read,
        })
        if i < len(vg_reads) - 1:
            backend.add_vector("gp", gap, 0.0); t_cursor += gap

    t_total = t_cursor
    if t_prefix > 0:
        backend.add_vector("dp", t_prefix, 0.0)
    if t_total > t_prefix:
        backend.add_vector("dp", T_RF, float(vd_read))
        backend.add_vector("dp", max(t_total - t_prefix - 2 * T_RF, T_RF), float(vd_read))
        backend.add_vector("dp", T_RF, 0.0)
    for w in windows:
        i = w["idx"]
        backend.set_measure_event("gp", f"g{i}", w["t0"], n_pts, interval, average, "averaged")
        backend.set_measure_event("dp", f"d{i}", w["t0"], n_pts, interval, average, "averaged")
    return windows


def run_readonly_shot(backend, *, vg_reads: list[float], vd_read: float, n_pts: int = N_PTS,
                      timeout_s: float = 30.0) -> list[dict]:
    backend.clear()
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)
    windows = _build_read_phase(backend, vg_reads=vg_reads, vd_read=vd_read, n_pts=n_pts)
    g_df, d_df = _configure_and_run_phase(backend, measure=True, timeout_s=timeout_s)
    return _summarize_windows(g_df, d_df, windows)


def run_e1_shot(backend, *, state: str, delay_s: float, vg_reads: list[float] = VG_READS,
                vd_read: float = VD_READ, n_pts: int = N_PTS,
                v_write: float | None = None, t_write: float = T_WRITE) -> list[dict]:
    if v_write is None:
        v_write = V_ERS if state == "ERS" else V_PGM
    backend.clear()
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)

    # Gate reset + write + delay.
    t_prefix = 0.0
    for dt, vg in [
        (T_RESET, 0.0),
        (T_RF, v_write),
        (t_write, v_write),
        (T_RF, 0.0),
    ]:
        backend.add_vector("gp", dt, vg)
        backend.add_vector("dp", dt, 0.0)
        t_prefix += dt
    if delay_s > 0:
        backend.add_vector("gp", delay_s, 0.0)
        backend.add_vector("dp", delay_s, 0.0)
        t_prefix += delay_s

    windows = _build_read_phase(
        backend,
        vg_reads=vg_reads,
        vd_read=vd_read,
        t_prefix=0.0,
        n_pts=n_pts,
        event_offset_s=t_prefix,
    )

    timeout_s = max(30.0, delay_s * 3 + 10.0)
    g_df, d_df = _configure_and_run_phase(backend, measure=True, timeout_s=timeout_s)
    return _summarize_windows(g_df, d_df, windows)


# ---------------------------------------------------------------------------
# E2 helpers: copied in minimized form from the split-dose notebook logic.
WGFMU_MAX_VECTORS_PER_PATTERN = 2048
WGFMU_VECTOR_GUARD = 128


def _dose_profile(mode: str):
    if mode == "A":
        return 5e-6, [0.0]
    if mode == "B":
        return 5e-6, np.linspace(-0.5, 0.5, 11).tolist()
    if mode == "C":
        return 2e-3, np.linspace(-1.5, 1.5, 21).tolist()
    raise ValueError(f"Unknown dose mode: {mode!r}")


def _dose_vectors_per_sweep(mode: str) -> int:
    _t_step, vg_steps = _dose_profile(mode)
    return len(vg_steps) * 3 + 1


def _dose_chunk_counts(mode: str, n_read: int,
                       max_vectors: int = WGFMU_MAX_VECTORS_PER_PATTERN - WGFMU_VECTOR_GUARD) -> list[int]:
    per = _dose_vectors_per_sweep(mode)
    max_reads = max(1, max_vectors // per)
    chunks, remaining = [], int(n_read)
    while remaining > 0:
        k = min(max_reads, remaining)
        chunks.append(k)
        remaining -= k
    return chunks


def _add_dose_vectors(backend, *, mode: str, n_read: int) -> tuple[float, int]:
    t_step, vg_steps = _dose_profile(mode)
    gap = 1e-6
    t_total = 0.0
    n_vec = 0
    for _ in range(int(n_read)):
        for vg in vg_steps:
            backend.add_vector("gp", T_RF, float(vg)); n_vec += 1
            backend.add_vector("gp", t_step, float(vg)); n_vec += 1
            backend.add_vector("gp", T_RF, 0.0); n_vec += 1
            t_total += T_RF + t_step + T_RF
        backend.add_vector("gp", gap, 0.0); n_vec += 1
        t_total += gap
    if n_vec > WGFMU_MAX_VECTORS_PER_PATTERN:
        raise RuntimeError(f"dose vector budget exceeded: mode={mode} n={n_read} vectors={n_vec}")
    return t_total, n_vec


def _run_reset_write_phase(backend, *, state: str):
    v_write = V_ERS if state == "ERS" else V_PGM
    backend.clear()
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)
    for dt, vg in [(T_RESET, 0.0), (T_RF, v_write), (T_WRITE, v_write), (T_RF, 0.0)]:
        backend.add_vector("gp", dt, vg)
        backend.add_vector("dp", dt, 0.0)
    _configure_and_run_phase(backend, measure=False, timeout_s=30.0)


def _run_dose_chunk_phase(backend, *, mode: str, n_chunk: int, vd_read: float):
    backend.clear()
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)
    t_dose, n_vec = _add_dose_vectors(backend, mode=mode, n_read=n_chunk)
    backend.add_vector("dp", T_RF, float(vd_read))
    backend.add_vector("dp", max(t_dose - 2 * T_RF, T_RF), float(vd_read))
    backend.add_vector("dp", T_RF, 0.0)
    timeout_s = max(30.0, t_dose * 3 + 10.0)
    _configure_and_run_phase(backend, measure=False, timeout_s=timeout_s)
    return n_vec


def run_e2_shot(backend, *, state: str, mode: str, n_read: int,
                vg_reads: list[float] = VG_READS, vd_read: float = VD_READ) -> list[dict]:
    _run_reset_write_phase(backend, state=state)
    chunks = _dose_chunk_counts(mode, n_read)
    for n_chunk in chunks:
        _run_dose_chunk_phase(backend, mode=mode, n_chunk=n_chunk, vd_read=vd_read)
    return run_readonly_shot(backend, vg_reads=vg_reads, vd_read=vd_read, n_pts=N_PTS, timeout_s=30.0)


# ---------------------------------------------------------------------------
def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})


def _stage_dir(args, stage: str) -> Path:
    device = _slug(args.device_id)
    if args.live:
        base = ROOT / "runs"
        return base / f"{_now_tag()}_{stage}_{device}"
    return ROOT / "_agent" / "dryrun_audit" / f"{_now_tag()}_{stage}_{device}"


def _summarize(stage: str, out_csv: Path, rows: list[dict], code: str) -> StageSummary:
    if not rows:
        max_id = max_ig = float("nan")
    else:
        max_id = max(abs(float(r.get("Id_mean_A", 0.0))) for r in rows if not pd.isna(r.get("Id_mean_A", float("nan"))))
        max_ig = max(abs(float(r.get("Ig_mean_A", 0.0))) for r in rows if not pd.isna(r.get("Ig_mean_A", float("nan"))))
    print(f"REPORT_CODE: {code}")
    print(f"STAGE_SUMMARY: stage={stage} rows={len(rows)} max_abs_Id_A={max_id:.6e} max_abs_Ig_A={max_ig:.6e}")
    print(f"OUTPUT_CSV: {out_csv}")
    return StageSummary(stage, out_csv, len(rows), max_id, max_ig, code)


def _check_samples(rows: list[dict], stage: str) -> None:
    bad = [r for r in rows if int(r.get("n_d", 0)) <= 0 or int(r.get("n_g", 0)) <= 0]
    if bad:
        raise StopGate(f"{stage}_STOP_NO_SAMPLES", f"{len(bad)} rows have n_d/n_g <= 0")


def _check_ig(rows: list[dict], stage: str, threshold_uA: float) -> None:
    vals = [abs(float(r.get("Ig_mean_A", float("nan")))) for r in rows]
    vals = [v for v in vals if not math.isnan(v)]
    max_ig = max(vals) if vals else float("nan")
    if vals and max_ig > threshold_uA * 1e-6:
        raise StopGate(f"{stage}_STOP_IG_GT_{threshold_uA:g}UA", f"max |Ig|={max_ig:.3e} A > {threshold_uA:g} uA")


def run_stage_s0(backend, args) -> StageSummary:
    """Open/fixture smoke: no write, small read-only pulses."""
    out_dir = _stage_dir(args, "S0_open_fixture_smoke")
    rows = []
    seq = 0
    for rep in range(args.s0_reps):
        rr = run_readonly_shot(backend, vg_reads=VG_READS, vd_read=VD_READ, n_pts=N_PTS)
        for r in rr:
            rows.append({
                "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                "stage": "S0", "device_id": args.device_id, "geometry": args.geometry,
                "sequence_id": seq, "repeat_index": rep, "state_target": "READ_ONLY_OPEN",
                "delay_s": "", "dose_mode": "", "n_read": "", **r, "note": "no_write_open_or_fixture",
            })
        seq += 1
    _check_samples(rows, "S0")
    _check_ig(rows, "S0", args.s0_ig_stop_uA)
    out_csv = out_dir / "s0_open_fixture_smoke.csv"
    _write_rows(out_csv, rows)
    return _summarize("S0", out_csv, rows, "S0_DONE_PROCEED_TO_S1_IF_PROBES_ON_DEVICE")


def run_stage_s1(backend, args) -> StageSummary:
    """Device contacted baseline: no write, 20 low-disturb reads by default."""
    out_dir = _stage_dir(args, "S1_device_read_only_baseline")
    rows = []
    seq = 0
    for rep in range(args.s1_reps):
        rr = run_readonly_shot(backend, vg_reads=VG_READS, vd_read=VD_READ, n_pts=N_PTS)
        for r in rr:
            rows.append({
                "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                "stage": "S1", "device_id": args.device_id, "geometry": args.geometry,
                "sequence_id": seq, "repeat_index": rep, "state_target": "READ_ONLY_DEVICE",
                "delay_s": "", "dose_mode": "", "n_read": "", **r, "note": "no_write_device_baseline",
            })
        seq += 1
    _check_samples(rows, "S1")
    _check_ig(rows, "S1", args.s1_ig_stop_uA)
    out_csv = out_dir / "s1_device_read_only_baseline.csv"
    _write_rows(out_csv, rows)
    return _summarize("S1", out_csv, rows, "S1_DONE_PROCEED_TO_E1")


def run_stage_e1(backend, args) -> StageSummary:
    vg_reads = VG_E5 if args.e1_wide_vg else VG_READS
    delay_list = DELAYS_FULL if args.e1_full_delays else DELAYS_QUICK300
    out_dir = _stage_dir(args, "E1_RAWD_QUICK300ms_v2")
    rows = []
    seq = 0
    rng = random.Random(args.seed)
    for rep in range(args.e1_reps):
        delays = list(delay_list)
        if args.randomize_delays:
            rng.shuffle(delays)
        for delay_s in delays:
            for state in ["ERS", "PGM"]:
                rr = run_e1_shot(backend, state=state, delay_s=delay_s, vg_reads=vg_reads)
                for r in rr:
                    rows.append({
                        "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                        "stage": "E1", "device_id": args.device_id, "geometry": args.geometry,
                        "sequence_id": seq, "repeat_index": rep, "state_target": state,
                        "delay_s": delay_s, "dose_mode": "", "n_read": "", **r,
                        "note": "QUICK300ms_v2",
                    })
                _check_samples(rows[-len(rr):], "E1")
                _check_ig(rows[-len(rr):], "E1", args.e1_ig_stop_uA)
                print(f"SHOT_OK: E1 rep={rep} state={state} delay_s={delay_s:g} seq={seq}")
                seq += 1
    out_csv = out_dir / "e1_rawd_quick300ms_v2.csv"
    _write_rows(out_csv, rows)
    return _summarize("E1", out_csv, rows, "E1_DONE_PROCEED_TO_E2_MINIMAL_IF_TREND_HEALTHY")


def run_stage_e2(backend, args) -> StageSummary:
    out_dir = _stage_dir(args, "E2_minimal_A1_A100_C1_C10")
    rows = []
    seq = 0
    for rep in range(args.e2_reps):
        for state, mode, n_read in E2_MINIMAL_COMBOS:
            rr = run_e2_shot(backend, state=state, mode=mode, n_read=n_read)
            for r in rr:
                rows.append({
                    "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                    "stage": "E2", "device_id": args.device_id, "geometry": args.geometry,
                    "sequence_id": seq, "repeat_index": rep, "state_target": state,
                    "delay_s": T_NEUTRAL, "dose_mode": mode, "n_read": n_read, **r,
                    "note": "minimal_no_C100",
                })
            _check_samples(rows[-len(rr):], "E2")
            _check_ig(rows[-len(rr):], "E2", args.e2_ig_stop_uA)
            print(f"SHOT_OK: E2 rep={rep} state={state} mode={mode} n_read={n_read} seq={seq}")
            seq += 1
    out_csv = out_dir / "e2_minimal_A1_A100_C1_C10.csv"
    _write_rows(out_csv, rows)
    return _summarize("E2", out_csv, rows, "E2_MINIMAL_DONE")


# E3 constants
E3_WIDTHS = [1e-6, 3e-6, 10e-6, 30e-6, 100e-6, 300e-6]
E3_AMPS = [3.0, 4.0, 5.0]
E3_DELAY = 10e-6


def run_stage_e3_width(backend, args) -> StageSummary:
    """E3 pulse-width scan: fixed ±5V, vary width."""
    out_dir = _stage_dir(args, "E3_pulse_width_scan")
    vg_reads = VG_E5 if args.e1_wide_vg else VG_READS
    rows = []
    seq = 0
    rng = random.Random(args.seed + 3)
    combos = [(s, tw) for s in ["ERS", "PGM"] for tw in E3_WIDTHS]
    for rep in range(args.e3_reps):
        order = list(combos)
        rng.shuffle(order)
        for state, tw in order:
            v_w = V_ERS if state == "ERS" else V_PGM
            rr = run_e1_shot(backend, state=state, delay_s=E3_DELAY,
                             vg_reads=vg_reads, v_write=v_w, t_write=tw)
            for r in rr:
                rows.append({
                    "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                    "stage": "E3W", "device_id": args.device_id, "geometry": args.geometry,
                    "sequence_id": seq, "repeat_index": rep, "state_target": state,
                    "delay_s": E3_DELAY, "dose_mode": f"tw={tw:g}", "n_read": "", **r,
                    "note": f"width_scan_amp={abs(v_w):g}V_tw={tw:g}s",
                })
            _check_samples(rows[-len(rr):], "E3W")
            _check_ig(rows[-len(rr):], "E3W", args.e3_ig_stop_uA)
            print(f"SHOT_OK: E3W rep={rep} state={state} tw={tw:g} seq={seq}")
            seq += 1
    out_csv = out_dir / "e3_pulse_width_scan.csv"
    _write_rows(out_csv, rows)
    return _summarize("E3W", out_csv, rows, "E3W_PULSE_WIDTH_DONE")


def run_stage_e3_amp(backend, args) -> StageSummary:
    """E3 amplitude scan: fixed 100µs width, vary amplitude."""
    out_dir = _stage_dir(args, "E3_amplitude_scan")
    vg_reads = VG_E5 if args.e1_wide_vg else VG_READS
    rows = []
    seq = 0
    rng = random.Random(args.seed + 30)
    combos = [(s, a) for s in ["ERS", "PGM"] for a in E3_AMPS]
    for rep in range(args.e3_reps):
        order = list(combos)
        rng.shuffle(order)
        for state, amp in order:
            v_w = +amp if state == "ERS" else -amp
            rr = run_e1_shot(backend, state=state, delay_s=E3_DELAY,
                             vg_reads=vg_reads, v_write=v_w, t_write=T_WRITE)
            for r in rr:
                rows.append({
                    "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                    "stage": "E3A", "device_id": args.device_id, "geometry": args.geometry,
                    "sequence_id": seq, "repeat_index": rep, "state_target": state,
                    "delay_s": E3_DELAY, "dose_mode": f"amp={v_w:+g}", "n_read": "", **r,
                    "note": f"amp_scan_V={v_w:+g}_tw={T_WRITE:g}s",
                })
            _check_samples(rows[-len(rr):], "E3A")
            _check_ig(rows[-len(rr):], "E3A", args.e3_ig_stop_uA)
            print(f"SHOT_OK: E3A rep={rep} state={state} amp={v_w:+g} seq={seq}")
            seq += 1
    out_csv = out_dir / "e3_amplitude_scan.csv"
    _write_rows(out_csv, rows)
    return _summarize("E3A", out_csv, rows, "E3A_AMPLITUDE_DONE")


# E4 constants
E4_PREBIAS_V = [0.0, +2.0, -2.0]
E4_PREBIAS_S = [1e-3, 100e-3, 1.0]
E4_POST_DELAY = 10e-6


def run_e4_shot(backend, *, state: str, prebias_v: float, prebias_s: float,
                post_delay_s: float, vg_reads: list[float], vd_read: float = VD_READ,
                n_pts: int = N_PTS) -> list[dict]:
    """Pre-bias → neutral wait → write → delay → read."""
    v_write = V_ERS if state == "ERS" else V_PGM
    backend.clear()
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)

    t_prefix = 0.0
    # Pre-bias
    if abs(prebias_v) > 0.001 and prebias_s > 0:
        for dt, vg in [(T_RF, prebias_v), (prebias_s, prebias_v), (T_RF, 0.0)]:
            backend.add_vector("gp", dt, vg)
            backend.add_vector("dp", dt, 0.0)
            t_prefix += dt
    # Neutral wait
    backend.add_vector("gp", T_RESET, 0.0)
    backend.add_vector("dp", T_RESET, 0.0)
    t_prefix += T_RESET
    # Write
    for dt, vg in [(T_RF, v_write), (T_WRITE, v_write), (T_RF, 0.0)]:
        backend.add_vector("gp", dt, vg)
        backend.add_vector("dp", dt, 0.0)
        t_prefix += dt
    # Post-write delay
    if post_delay_s > 0:
        backend.add_vector("gp", post_delay_s, 0.0)
        backend.add_vector("dp", post_delay_s, 0.0)
        t_prefix += post_delay_s

    windows = _build_read_phase(
        backend, vg_reads=vg_reads, vd_read=vd_read, t_prefix=0.0,
        n_pts=n_pts, event_offset_s=t_prefix,
    )
    timeout_s = max(30.0, prebias_s * 3 + post_delay_s * 3 + 10.0)
    g_df, d_df = _configure_and_run_phase(backend, measure=True, timeout_s=timeout_s)
    return _summarize_windows(g_df, d_df, windows)


def run_stage_e4(backend, args) -> StageSummary:
    """E4: pre-bias polarity test."""
    out_dir = _stage_dir(args, "E4_prebias")
    vg_reads = VG_E5 if args.e1_wide_vg else VG_READS
    rows = []
    seq = 0
    rng = random.Random(args.seed + 4)
    combos = [(s, pv, ps) for s in ["ERS", "PGM"] for pv in E4_PREBIAS_V for ps in E4_PREBIAS_S]
    for rep in range(args.e4_reps):
        order = list(combos)
        rng.shuffle(order)
        for state, pv, ps in order:
            rr = run_e4_shot(backend, state=state, prebias_v=pv, prebias_s=ps,
                             post_delay_s=E4_POST_DELAY, vg_reads=vg_reads)
            for r in rr:
                rows.append({
                    "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                    "stage": "E4", "device_id": args.device_id, "geometry": args.geometry,
                    "sequence_id": seq, "repeat_index": rep, "state_target": state,
                    "delay_s": E4_POST_DELAY, "dose_mode": f"pb={pv:+g}V/{ps:g}s",
                    "n_read": "", **r,
                    "note": f"prebias_{pv:+g}V_{ps:g}s",
                })
            _check_samples(rows[-len(rr):], "E4")
            _check_ig(rows[-len(rr):], "E4", args.e4_ig_stop_uA)
            print(f"SHOT_OK: E4 rep={rep} state={state} pb={pv:+g}V/{ps:g}s seq={seq}")
            seq += 1
    out_csv = out_dir / "e4_prebias.csv"
    _write_rows(out_csv, rows)
    return _summarize("E4", out_csv, rows, "E4_PREBIAS_DONE")


def run_stage_e5(backend, args) -> StageSummary:
    """E5: Vg×Vd read-window visibility grid after write."""
    out_dir = _stage_dir(args, "E5_visibility_grid")
    rows = []
    seq = 0
    rng = random.Random(args.seed + 5)
    combos = []
    for state in ["ERS", "PGM"]:
        for vd in VD_E5:
            for delay_s in DELAYS_E5:
                combos.append((state, vd, delay_s))
    for rep in range(args.e5_reps):
        order = list(combos)
        rng.shuffle(order)
        for state, vd, delay_s in order:
            rr = run_e1_shot(backend, state=state, delay_s=delay_s,
                             vg_reads=VG_E5, vd_read=vd, n_pts=N_PTS)
            for r in rr:
                rows.append({
                    "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                    "stage": "E5", "device_id": args.device_id, "geometry": args.geometry,
                    "sequence_id": seq, "repeat_index": rep, "state_target": state,
                    "delay_s": delay_s, "dose_mode": "", "n_read": "", **r,
                    "note": f"visibility_grid_Vd={vd:g}",
                })
            _check_samples(rows[-len(rr):], "E5")
            _check_ig(rows[-len(rr):], "E5", args.e5_ig_stop_uA)
            print(f"SHOT_OK: E5 rep={rep} state={state} Vd={vd:g} delay_s={delay_s:g} seq={seq}")
            seq += 1
    out_csv = out_dir / "e5_visibility_grid.csv"
    _write_rows(out_csv, rows)
    return _summarize("E5", out_csv, rows, "E5_VISIBILITY_DONE")


def run_stage_cycle(backend, args) -> StageSummary:
    """Cycle endurance: repeated ERS/PGM writes with fixed 10us read."""
    out_dir = _stage_dir(args, "CYCLE_endurance")
    rows = []
    seq = 0
    for cyc in range(args.cycle_count):
        for state in ["ERS", "PGM"]:
            rr = run_e1_shot(backend, state=state, delay_s=CYCLE_DELAY,
                             vg_reads=VG_CYCLE, vd_read=VD_READ, n_pts=N_PTS)
            for r in rr:
                rows.append({
                    "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                    "stage": "CYCLE", "device_id": args.device_id, "geometry": args.geometry,
                    "sequence_id": seq, "repeat_index": cyc, "state_target": state,
                    "delay_s": CYCLE_DELAY, "dose_mode": "cycle_endurance", "n_read": cyc + 1,
                    **r, "note": f"cycle={cyc+1}_fixed_10us",
                })
            _check_samples(rows[-len(rr):], "CYCLE")
            _check_ig(rows[-len(rr):], "CYCLE", args.cycle_ig_stop_uA)
            print(f"SHOT_OK: CYCLE cycle={cyc+1} state={state} seq={seq}")
            seq += 1
    out_csv = out_dir / "cycle_endurance.csv"
    _write_rows(out_csv, rows)
    return _summarize("CYCLE", out_csv, rows, "CYCLE_ENDURANCE_DONE")


def print_plan(args) -> None:
    print("PLAN_BEGIN")
    print(f"live={args.live} stage={args.stage} device_id={args.device_id} geometry={args.geometry}")
    print(f"hardcoded_channels: Gate={GATE_CH}, Drain={DRAIN_CH}; forbidden={sorted(FORBIDDEN_CHANNELS)}")
    print(f"S0: reps={args.s0_reps}, no write, VG={VG_READS}, VD={VD_READ} V, stop |Ig|>{args.s0_ig_stop_uA:g} uA")
    print(f"S1: reps={args.s1_reps}, no write, VG={VG_READS}, VD={VD_READ} V, stop |Ig|>{args.s1_ig_stop_uA:g} uA")
    print(f"E1: delays={DELAYS_QUICK300}, reps={args.e1_reps}, ERS=+5V/100us, PGM=-5V/100us, stop |Ig|>{args.e1_ig_stop_uA:g} uA")
    print(f"E2: combos={E2_MINIMAL_COMBOS}, reps={args.e2_reps}, split-dose chunks, skip C100, stop |Ig|>{args.e2_ig_stop_uA:g} uA")
    print(f"E5: Vg={VG_E5}, Vd={VD_E5}, delays={DELAYS_E5}, reps={args.e5_reps}, stop |Ig|>{args.e5_ig_stop_uA:g} uA")
    print("PLAN_END")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=["PLAN", "S0", "S1", "E1", "E2", "E3W", "E3A", "E4", "E5", "CYCLE", "ALL_DRY"], default="PLAN")
    ap.add_argument("--live", action="store_true", help="Open real WGFMU session and drive hardware for one stage only")
    ap.add_argument("--confirm", default="", help="Must equal selected stage in live mode, e.g. --confirm S1")
    ap.add_argument("--device-id", default="L40W10_01")
    ap.add_argument("--geometry", default="L40W10")
    ap.add_argument("--seed", type=int, default=20260522)
    ap.add_argument("--randomize-delays", action="store_true", default=True)
    ap.add_argument("--s0-reps", type=int, default=5)
    ap.add_argument("--s1-reps", type=int, default=20)
    ap.add_argument("--e1-reps", type=int, default=3)
    ap.add_argument("--e2-reps", type=int, default=2)
    ap.add_argument("--s0-ig-stop-uA", type=float, default=5.0)
    ap.add_argument("--s1-ig-stop-uA", type=float, default=5.0)
    ap.add_argument("--e1-ig-stop-uA", type=float, default=20.0)
    ap.add_argument("--e1-wide-vg", action="store_true", default=False,
                    help="Use E5 wide Vg grid for E1 reads instead of default [-0.2,0,0.2]")
    ap.add_argument("--e1-full-delays", action="store_true", default=False,
                    help="Use DELAYS_FULL (to 10s) instead of DELAYS_QUICK300 (to 300ms)")
    ap.add_argument("--e2-ig-stop-uA", type=float, default=20.0)
    ap.add_argument("--e3-reps", type=int, default=3)
    ap.add_argument("--e3-ig-stop-uA", type=float, default=30.0)
    ap.add_argument("--e4-reps", type=int, default=3)
    ap.add_argument("--e4-ig-stop-uA", type=float, default=30.0)
    ap.add_argument("--e5-reps", type=int, default=3)
    ap.add_argument("--e5-ig-stop-uA", type=float, default=20.0)
    ap.add_argument("--cycle-count", type=int, default=20)
    ap.add_argument("--cycle-ig-stop-uA", type=float, default=30.0)
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    print_plan(args)

    if args.stage == "PLAN":
        print("REPORT_CODE: PLAN_ONLY_NO_HARDWARE")
        return 0
    if args.live:
        if args.stage == "ALL_DRY":
            print("REPORT_CODE: SETUP_STOP_LIVE_ALL_FORBIDDEN")
            print("Live mode is intentionally one stage at a time. Use --stage S0/S1/E1/E2 --live --confirm <STAGE>.")
            return 2
        if args.confirm != args.stage:
            print(f"REPORT_CODE: SETUP_STOP_CONFIRM_REQUIRED_{args.stage}")
            print(f"For live mode, rerun with: --live --confirm {args.stage}")
            return 2

    backend = None
    try:
        backend, _resource = make_backend(args.live)
        stages = ["S0", "S1", "E1", "E2", "E3W", "E3A", "E4", "E5", "CYCLE"] if args.stage == "ALL_DRY" else [args.stage]
        for stage in stages:
            if stage == "S0":
                run_stage_s0(backend, args)
            elif stage == "S1":
                run_stage_s1(backend, args)
            elif stage == "E1":
                run_stage_e1(backend, args)
            elif stage == "E2":
                run_stage_e2(backend, args)
            elif stage == "E3W":
                run_stage_e3_width(backend, args)
            elif stage == "E3A":
                run_stage_e3_amp(backend, args)
            elif stage == "E4":
                run_stage_e4(backend, args)
            elif stage == "E5":
                run_stage_e5(backend, args)
            elif stage == "CYCLE":
                run_stage_cycle(backend, args)
            else:
                raise ValueError(stage)
        if not args.live and isinstance(backend, AuditBackend):
            print(f"DRY_RUN_AUDIT: execute_count={backend.execute_count} max_vectors_seen={backend.max_vectors_seen}")
        return 0
    except StopGate as exc:
        print(f"REPORT_CODE: {exc.code}")
        print(f"STOP_GATE: {exc}")
        return 20
    except KeyboardInterrupt:
        print("REPORT_CODE: USER_ABORTED")
        return 130
    finally:
        if backend is not None:
            try:
                backend.close_session()
            except Exception:
                pass
            time.sleep(0.2)


if __name__ == "__main__":
    raise SystemExit(main())
