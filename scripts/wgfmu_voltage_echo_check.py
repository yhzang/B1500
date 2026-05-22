#!/usr/bin/env python
"""Low-risk WGFMU voltage echo check for yhzang B1500.

This script verifies WGFMU VOLTAGE measurement mode on the same low-voltage
read-only waveform used by S0/S1.  It is safe to run on a contacted device
because it does not apply write pulses: Gate uses [-0.2, 0, +0.2] V and Drain
uses +0.05 V during the read window.

Important limitation: this checks terminal self-measured voltage for the
low-voltage read phase only.  It does not replace an oscilloscope check and does
not prove the ±5 V / 100 us E1 write-pulse amplitude at the probe tip.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from wgfmu_next_round_minimal import (  # noqa: E402
    AuditBackend,
    DRAIN_CH,
    GATE_CH,
    N_PTS,
    T_READ,
    VD_READ,
    VG_READS,
    StopGate,
    _build_read_phase,
    _now_tag,
    _safe_disconnect,
    _slug,
    _validate_channels,
)


FIELDNAMES = [
    "timestamp_iso", "device_id", "geometry", "sequence_id",
    "Vg_cmd_V", "Vg_meas_mean_V", "Vg_meas_std_V", "Vg_err_V", "n_g",
    "Vd_cmd_V", "Vd_meas_mean_V", "Vd_meas_std_V", "Vd_err_V", "n_d",
    "note",
]


class VoltageAuditBackend(AuditBackend):
    """Dry-run backend that returns commanded pattern voltages at event times."""

    def _pattern_value_at(self, pattern: str, t_s: float) -> float:
        payload = self._patterns.get(pattern, {})
        vectors = payload.get("vectors", [])
        last_v = float(payload.get("init_v", 0.0))
        elapsed = 0.0
        for dt, target_v in vectors:
            dt = float(dt)
            target_v = float(target_v)
            if t_s <= elapsed + dt + 1e-15:
                if dt <= 0:
                    return target_v
                frac = max(0.0, min(1.0, (t_s - elapsed) / dt))
                return last_v + frac * (target_v - last_v)
            elapsed += dt
            last_v = target_v
        return last_v

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
            for ev in sorted(self._events.values(), key=lambda e: e["time_s"]):
                if ev["pattern"] != pat:
                    continue
                for k in range(ev["points"]):
                    t = ev["time_s"] + k * ev["interval_s"]
                    rows.append({"time_s": t, "value": self._pattern_value_at(pat, t)})
            self._last_values[ch] = pd.DataFrame(rows, columns=["time_s", "value"])
        return 0


def make_backend(live: bool):
    if not live:
        b = VoltageAuditBackend()
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


def _configure_voltage_and_run(backend, *, timeout_s: float = 30.0):
    backend.add_sequence(GATE_CH, "gp", 1)
    backend.add_sequence(DRAIN_CH, "dp", 1)
    backend.initialize()
    for ch, force_range in [(GATE_CH, "AUTO"), (DRAIN_CH, "3V")]:
        backend.set_operation_mode(ch, "FASTIV")
        backend.set_force_voltage_range(ch, force_range)
        backend.set_measure_enabled(ch, True)
        backend.set_measure_mode(ch, "VOLTAGE")
        backend.set_measure_voltage_range(ch, "10V")
    backend.set_timeout(timeout_s)
    backend.connect(GATE_CH)
    backend.connect(DRAIN_CH)
    try:
        backend.execute()
        backend.wait_until_completed()
        return backend.get_measure_values(GATE_CH), backend.get_measure_values(DRAIN_CH)
    finally:
        _safe_disconnect(backend, GATE_CH, DRAIN_CH)


def _summarize_voltage_windows(g_df: pd.DataFrame, d_df: pd.DataFrame, windows: list[dict]) -> list[dict]:
    g_t = g_df["time_s"].to_numpy(dtype=float) if len(g_df) else np.array([])
    g_v = g_df["value"].to_numpy(dtype=float) if len(g_df) else np.array([])
    d_t = d_df["time_s"].to_numpy(dtype=float) if len(d_df) else np.array([])
    d_v = d_df["value"].to_numpy(dtype=float) if len(d_df) else np.array([])
    rows = []
    for seq, w in enumerate(windows):
        t0, t1 = float(w["t0"]), float(w["t1"])
        gm = (g_t >= t0) & (g_t <= t1)
        dm = (d_t >= t0) & (d_t <= t1)
        g_sub = g_v[gm]
        d_sub = d_v[dm]
        vg_cmd = float(w["vg"])
        vd_cmd = float(w["vd"])
        vg_mean = float(np.nanmean(g_sub)) if len(g_sub) else float("nan")
        vd_mean = float(np.nanmean(d_sub)) if len(d_sub) else float("nan")
        rows.append({
            "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
            "sequence_id": seq,
            "Vg_cmd_V": vg_cmd,
            "Vg_meas_mean_V": vg_mean,
            "Vg_meas_std_V": float(np.nanstd(g_sub)) if len(g_sub) > 1 else 0.0,
            "Vg_err_V": vg_mean - vg_cmd if not math.isnan(vg_mean) else float("nan"),
            "n_g": int(len(g_sub)),
            "Vd_cmd_V": vd_cmd,
            "Vd_meas_mean_V": vd_mean,
            "Vd_meas_std_V": float(np.nanstd(d_sub)) if len(d_sub) > 1 else 0.0,
            "Vd_err_V": vd_mean - vd_cmd if not math.isnan(vd_mean) else float("nan"),
            "n_d": int(len(d_sub)),
            "note": "low_voltage_self_measured_terminal_echo_not_scope_probe_tip",
        })
    return rows


def run_voltage_echo(backend, args) -> Path:
    backend.clear()
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)
    windows = _build_read_phase(
        backend,
        vg_reads=[float(x) for x in VG_READS],
        vd_read=float(VD_READ),
        t_read=float(T_READ),
        n_pts=int(N_PTS),
    )
    g_df, d_df = _configure_voltage_and_run(backend, timeout_s=30.0)
    rows = _summarize_voltage_windows(g_df, d_df, windows)
    for r in rows:
        r["device_id"] = args.device_id
        r["geometry"] = args.geometry
    bad_samples = [r for r in rows if int(r["n_g"]) <= 0 or int(r["n_d"]) <= 0]
    if bad_samples:
        raise StopGate("VOLTAGE_ECHO_STOP_NO_SAMPLES", f"{len(bad_samples)} rows have n_g/n_d <= 0")
    errs = []
    for r in rows:
        for key in ("Vg_err_V", "Vd_err_V"):
            v = float(r[key])
            if not math.isnan(v):
                errs.append(abs(v))
    max_err = max(errs) if errs else float("nan")
    out_dir = (ROOT / "runs" if args.live else ROOT / "_agent" / "dryrun_audit") / f"{_now_tag()}_VOLTAGE_ECHO_{_slug(args.device_id)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "voltage_echo_low_v_read_only.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in FIELDNAMES})
    code = "VOLTAGE_ECHO_DONE_LOW_VOLTAGE_ONLY"
    if errs and max_err > args.v_error_stop_V:
        code = f"VOLTAGE_ECHO_STOP_ERR_GT_{args.v_error_stop_V:g}V"
    print(f"REPORT_CODE: {code}")
    print(f"STAGE_SUMMARY: rows={len(rows)} max_abs_voltage_error_V={max_err:.6e}")
    print("LIMITATION: low-voltage terminal self-measure only; not an oscilloscope proof of ±5V write pulse at probe tip")
    print(f"OUTPUT_CSV: {out_csv}")
    if code.startswith("VOLTAGE_ECHO_STOP"):
        raise StopGate(code, f"max_abs_voltage_error={max_err:.3e} V > {args.v_error_stop_V:g} V")
    return out_csv


def parse_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description="Low-risk WGFMU voltage echo check before E1")
    p.add_argument("--live", action="store_true", help="Open B1500/WGFMU and execute low-voltage waveform")
    p.add_argument("--confirm", default="", help="Must be VOLTAGE_ECHO for live mode")
    p.add_argument("--device-id", default="UNKNOWN_DEVICE")
    p.add_argument("--geometry", default="UNKNOWN_GEOMETRY")
    p.add_argument("--v-error-stop-V", type=float, default=0.08)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print("PLAN_BEGIN")
    print(f"live={args.live} device_id={args.device_id} geometry={args.geometry}")
    print(f"hardcoded_channels: Gate={GATE_CH}, Drain={DRAIN_CH}; low_voltage_read_only Vg={VG_READS}, Vd={VD_READ} V")
    print("PLAN_END")
    if args.live and args.confirm != "VOLTAGE_ECHO":
        print("REPORT_CODE: SETUP_STOP_CONFIRM_REQUIRED_VOLTAGE_ECHO")
        return 2
    backend = None
    try:
        backend, _resource = make_backend(args.live)
        run_voltage_echo(backend, args)
        return 0
    except StopGate as exc:
        print(f"REPORT_CODE: {exc.code}")
        print(f"STOP_REASON: {exc}")
        return 2
    finally:
        if backend is not None:
            try:
                backend.close_session()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
