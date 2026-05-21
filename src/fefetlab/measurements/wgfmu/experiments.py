"""E1-E5 experiment orchestration for PFeFET negative-MW characterization.

This module builds WGFMU pulse sequences for the 5 discriminative experiments
defined in 项目4 理论分析 2026-05-19_WGFMU实验设计_v1.md.

All experiments share:
- ERS: +5.0V, 100us, rise/fall 100ns  (Wang-Yuan Fig.4-8 standard)
- PGM: -5.0V, 100us, rise/fall 100ns
- Reset: 0V, 1ms
- Read: 3-point {-0.2, 0.0, +0.2}V, 5us each, Vd=0.05V
- Gate: CH201, Drain: CH202 (yhzang B1500, GPIB1::17)
- Measure range: 1MA (6004), FASTIV mode (2001)
- Each delay point independently reset (anti-cumulative-bias)
- Delay order randomized (anti-time-drift)
- Single-point read only (anti-read-disturb), except E2

WGFMU constants from official WGFMU.cs (B1530A InstLib Sample):
  OPERATION_MODE:  FASTIV=2001
  MEASURE_MODE:    CURRENT=4001
  MEASURE_RANGE:   1MA=6004
  MEASURE_ENABLED: ENABLE=7001, DISABLE=7000
  EVENT_DATA:      AVERAGED=12000, RAW=12001
"""
from __future__ import annotations

import csv
import datetime
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np


# ── Default parameters (Wang-Yuan Fig.4-8) ──────────────────────────
@dataclass
class PFeFETParams:
    """Standard PFeFET write/read parameters."""
    v_ers: float = 5.0          # ERS gate voltage (positive for p-type)
    v_pgm: float = -5.0         # PGM gate voltage
    t_ers_s: float = 100e-6     # ERS pulse width
    t_pgm_s: float = 100e-6     # PGM pulse width
    t_rise_s: float = 100e-9    # rise time
    t_fall_s: float = 100e-9    # fall time
    v_reset: float = 0.0        # reset voltage
    t_reset_s: float = 1e-3     # reset duration
    vg_read_list: list = field(default_factory=lambda: [-0.2, 0.0, 0.2])
    vd_read: float = 0.05       # drain read voltage
    t_read_s: float = 5e-6      # read pulse width
    chan_gate: int = 201         # WGFMU gate channel
    chan_drain: int = 202        # WGFMU drain channel
    measure_range: str = "1MA"  # current measure range
    measure_points_per_read: int = 10  # samples per read pulse
    measure_average_s: float = 200e-9  # per-sample averaging


# ── E1: RAWD ────────────────────────────────────────────────────────
@dataclass
class E1Config:
    """E1: Write-After-Read-Delay configuration."""
    params: PFeFETParams = field(default_factory=PFeFETParams)
    delays_s: list = field(default_factory=lambda: [1e-6, 1e-5, 1e-4, 1e-3, 1e-2])
    n_repeats: int = 3
    randomize_delays: bool = True
    label: str = "E1_rawd"


@dataclass
class E1Result:
    """One E1 measurement point."""
    repeat_idx: int
    delay_s: float
    state: str          # "ERS" or "PGM"
    vg_read_v: float
    id_mean_a: float
    id_std_a: float
    ig_mean_a: float = 0.0
    ig_std_a: float = 0.0


def build_e1_sequence(cfg: E1Config) -> list:
    """Build the full E1 measurement plan as a list of dicts.
    
    Each entry describes one atomic measurement:
    reset -> write(state) -> wait(delay) -> read(vg) 
    
    Returns list of {repeat, delay_s, state, vg_read, sequence_order}.
    """
    plan = []
    for rep in range(cfg.n_repeats):
        delay_order = list(range(len(cfg.delays_s)))
        if cfg.randomize_delays:
            random.shuffle(delay_order)
        
        for seq_idx, delay_idx in enumerate(delay_order):
            delay = cfg.delays_s[delay_idx]
            for state in ["ERS", "PGM"]:
                for vg in cfg.params.vg_read_list:
                    plan.append({
                        "repeat": rep,
                        "delay_s": delay,
                        "state": state,
                        "vg_read": vg,
                        "sequence_order": seq_idx,
                        "delay_idx": delay_idx,
                    })
    return plan


def run_e1_single_point(backend, cfg: E1Config, state: str, 
                         delay_s: float, vg_read: float) -> dict:
    """Execute one E1 atomic measurement on real hardware.
    
    Sequence: reset -> write(state) -> wait(delay) -> read(vg_read)
    
    Returns dict with Id_mean, Id_std, Ig_mean, Ig_std.
    """
    p = cfg.params
    
    # Build gate pattern: reset -> write -> delay -> read
    gate_pattern = f"e1_gate_{state}_{delay_s:.0e}"
    backend.create_pattern(gate_pattern, p.v_reset)
    
    # 1) Reset
    backend.add_vector(gate_pattern, p.t_reset_s, p.v_reset)
    
    # 2) Write pulse (ERS or PGM)
    v_write = p.v_ers if state == "ERS" else p.v_pgm
    backend.add_vector(gate_pattern, p.t_rise_s, v_write)   # rise
    backend.add_vector(gate_pattern, max(p.t_ers_s, p.t_pgm_s) if state == "ERS" else p.t_pgm_s, v_write)  # hold
    backend.add_vector(gate_pattern, p.t_fall_s, p.v_reset)  # fall
    
    # 3) Delay (at reset voltage)
    if delay_s > 0:
        backend.add_vector(gate_pattern, delay_s, p.v_reset)
    
    # 4) Read pulse
    backend.add_vector(gate_pattern, p.t_rise_s, vg_read)     # rise to read voltage
    backend.add_vector(gate_pattern, p.t_read_s, vg_read)     # hold for read
    backend.add_vector(gate_pattern, p.t_fall_s, p.v_reset)   # fall back
    
    # Set measure event during read (skip first 3us for settling)
    t_before_read = (p.t_reset_s + p.t_rise_s + 
                     (p.t_ers_s if state == "ERS" else p.t_pgm_s) + 
                     p.t_fall_s + delay_s + p.t_rise_s)
    guard = min(p.t_rise_s, p.t_read_s * 0.1)
    meas_start = t_before_read + p.t_read_s * 0.6  # measure last 40% of read
    meas_window = p.t_read_s * 0.4 - guard
    n_pts = max(p.measure_points_per_read, 1)
    interval = meas_window / n_pts
    avg_time = min(p.measure_average_s, interval * 0.9)
    
    backend.set_measure_event(
        gate_pattern, "read_id", meas_start, n_pts, interval, avg_time, "averaged"
    )
    
    # Build drain pattern: 0V except during read -> Vd
    drain_pattern = f"e1_drain_{state}_{delay_s:.0e}"
    backend.create_pattern(drain_pattern, 0.0)
    t_total_before_read = t_before_read - p.t_rise_s
    backend.add_vector(drain_pattern, t_total_before_read, 0.0)  # hold 0V
    backend.add_vector(drain_pattern, p.t_rise_s, p.vd_read)     # rise
    backend.add_vector(drain_pattern, p.t_read_s, p.vd_read)     # hold
    backend.add_vector(drain_pattern, p.t_fall_s, 0.0)           # fall
    
    # Configure channels
    backend.set_operation_mode(p.chan_gate, "FASTIV")
    backend.set_operation_mode(p.chan_drain, "FASTIV")
    backend.set_measure_mode(p.chan_gate, "CURRENT")
    backend.set_measure_mode(p.chan_drain, "CURRENT")
    backend.set_measure_current_range(p.chan_gate, p.measure_range)
    backend.set_measure_current_range(p.chan_drain, p.measure_range)
    backend.set_measure_enabled(p.chan_gate, True)
    backend.set_measure_enabled(p.chan_drain, True)
    
    # Add sequences
    backend.add_sequence(p.chan_gate, gate_pattern, 1)
    backend.add_sequence(p.chan_drain, drain_pattern, 1)
    
    # Execute
    backend.connect(p.chan_gate)
    backend.connect(p.chan_drain)
    backend.execute()
    backend.wait_until_completed()
    
    # Get results - drain current during read
    n_measured = backend.get_measure_value_size(p.chan_drain)
    if n_measured > 0:
        times, values = backend.get_measure_values(p.chan_drain)
        id_arr = np.array(values[:n_measured])
        result = {
            "id_mean": float(np.mean(id_arr)),
            "id_std": float(np.std(id_arr)),
        }
    else:
        result = {"id_mean": 0.0, "id_std": 0.0}
    
    # Gate current (leakage monitoring)
    n_gate = backend.get_measure_value_size(p.chan_gate)
    if n_gate > 0:
        _, gvals = backend.get_measure_values(p.chan_gate)
        ig_arr = np.array(gvals[:n_gate])
        result["ig_mean"] = float(np.mean(ig_arr))
        result["ig_std"] = float(np.std(ig_arr))
    else:
        result["ig_mean"] = 0.0
        result["ig_std"] = 0.0
    
    # Cleanup for next point
    backend.disconnect(p.chan_gate)
    backend.disconnect(p.chan_drain)
    backend.clear()
    
    return result


def save_e1_results(results: list, output_dir: str, cfg: E1Config):
    """Save E1 results to CSV."""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"{cfg.label}_{ts}.csv")
    
    fieldnames = [
        "timestamp_iso", "device_id", "geometry", "sequence_id",
        "repeat_index", "state_target", "delay_s", 
        "vg_read_V", "vd_read_V",
        "Id_mean_A", "Id_std_A", "Ig_mean_A", "Ig_std_A", "note"
    ]
    
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "timestamp_iso": datetime.datetime.now().isoformat(),
                "device_id": "",
                "geometry": "",
                "sequence_id": r.get("sequence_order", 0),
                "repeat_index": r.get("repeat", 0),
                "state_target": r.get("state", ""),
                "delay_s": r.get("delay_s", 0),
                "vg_read_V": r.get("vg_read", 0),
                "vd_read_V": cfg.params.vd_read,
                "Id_mean_A": r.get("id_mean", 0),
                "Id_std_A": r.get("id_std", 0),
                "Ig_mean_A": r.get("ig_mean", 0),
                "Ig_std_A": r.get("ig_std", 0),
                "note": "",
            })
    return path


# ── E2: Read Disturb ────────────────────────────────────────────────
@dataclass 
class E2Config:
    """E2: Read disturb dose matrix."""
    params: PFeFETParams = field(default_factory=PFeFETParams)
    n_read_list: list = field(default_factory=lambda: [1, 3, 10, 30])
    label: str = "E2_read_disturb"


# ── E3: Pulse Matrix ────────────────────────────────────────────────
@dataclass
class E3Config:
    """E3: PGM/ERS pulse width-amplitude 2D matrix."""
    params: PFeFETParams = field(default_factory=PFeFETParams)
    v_ers_list: list = field(default_factory=lambda: [3.0, 4.0, 5.0, 6.0])
    v_pgm_list: list = field(default_factory=lambda: [-3.0, -4.0, -5.0, -6.0])
    widths_s: list = field(default_factory=lambda: [1e-6, 3e-6, 1e-5, 3e-5, 1e-4, 3e-4])
    delay_after_write_s: float = 10e-6
    label: str = "E3_pulse_matrix"


# ── E4: Imprint Pre-bias ────────────────────────────────────────────
@dataclass
class E4Config:
    """E4: Imprint polarity pre-bias test."""
    params: PFeFETParams = field(default_factory=PFeFETParams)
    prebias_voltages: list = field(default_factory=lambda: [+2.0, -2.0, 0.0])
    prebias_durations_s: list = field(default_factory=lambda: [1e-3, 1e-2, 1e-1, 1.0])
    post_delays_s: list = field(default_factory=lambda: [10e-6, 10.0])
    label: str = "E4_imprint"


# ── E5: Visibility Grid ─────────────────────────────────────────────
@dataclass
class E5Config:
    """E5: Vd/Vg read grid for visibility and leakage."""
    params: PFeFETParams = field(default_factory=PFeFETParams)
    vg_grid: list = field(default_factory=lambda: [-0.4, -0.2, 0.0, 0.2, 0.4])
    vd_grid: list = field(default_factory=lambda: [0.01, 0.05, 0.10, 0.50])
    read_times_s: list = field(default_factory=lambda: [10e-6, 1.0])
    label: str = "E5_visibility"


__all__ = [
    "PFeFETParams",
    "E1Config", "E1Result", "build_e1_sequence", "run_e1_single_point", "save_e1_results",
    "E2Config",
    "E3Config", 
    "E4Config",
    "E5Config",
]
