#!/usr/bin/env python3
"""E1: Write-After-Read-Delay (RAWD) — PFeFET negative-MW characterization.

Sequence per delay point:
  Reset(0V,1ms) -> Write(ERS+5V or PGM-5V, 100us) -> wait(t_delay) -> 3-pt read

Parameters: ±5V/100us (Wang-Yuan Fig.4-8 standard)
Quick mode: 5 delays × 3 repeats ≈ 3 min/device
Full mode: 17 delays × 10 repeats ≈ 55 min/device

Usage:
  python 30_E1_rawd.py                    # quick mode
  python 30_E1_rawd.py --full             # full 17-delay mode
  python 30_E1_rawd.py --device L40W10    # specify device geometry
"""
import argparse
import datetime
import os
import sys
import random
import time

import numpy as np

# ── Parse args ──────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="E1 RAWD experiment")
parser.add_argument("--full", action="store_true", help="Full 17-delay mode")
parser.add_argument("--device", default="L40W10", help="Device geometry label")
parser.add_argument("--output-dir", default=None, help="Output directory")
parser.add_argument("--dry-run", action="store_true", help="Use dummy backend")
args = parser.parse_args()

# ── Add project to path ─────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from fefetlab.measurements.wgfmu.experiments import (
    PFeFETParams, E1Config, build_e1_sequence, 
    run_e1_single_point, save_e1_results,
)

# ── Configuration ────────────────────────────────────────────────────
# ⚠️ EDIT THESE for your device / session
PARAMS = PFeFETParams(
    v_ers=5.0,          # +5V ERS (Wang-Yuan standard)
    v_pgm=-5.0,         # -5V PGM
    t_ers_s=100e-6,     # 100us (saturation ensured per Fig.4-12)
    t_pgm_s=100e-6,     # 100us  
    t_rise_s=100e-9,    # 100ns rise/fall
    t_fall_s=100e-9,
    v_reset=0.0,
    t_reset_s=1e-3,     # 1ms reset
    vg_read_list=[-0.2, 0.0, 0.2],  # 3-point read
    vd_read=0.05,       # 50mV drain
    t_read_s=5e-6,      # 5us read pulse
    chan_gate=201,       # yhzang B1500 WGFMU channels
    chan_drain=202,
    measure_range="1MA", # ~11nA noise floor
    measure_points_per_read=10,
    measure_average_s=200e-9,
)

if args.full:
    DELAYS = [1e-6, 3e-6, 1e-5, 3e-5, 1e-4, 3e-4, 
              1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1,
              1, 3, 10, 30, 100]
    N_REPEATS = 10
else:
    DELAYS = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2]
    N_REPEATS = 3

cfg = E1Config(params=PARAMS, delays_s=DELAYS, n_repeats=N_REPEATS)

# ── Output directory ─────────────────────────────────────────────────
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = args.output_dir or os.path.join(
    PROJECT_ROOT, "runs", f"{ts}_{cfg.label}_{args.device}"
)
os.makedirs(out_dir, exist_ok=True)

# ── Backend ──────────────────────────────────────────────────────────
if args.dry_run:
    from fefetlab.measurements.wgfmu.backend import DummyWgfmuBackend
    backend = DummyWgfmuBackend()
    print("[DRY RUN] Using dummy backend")
else:
    from fefetlab.measurements.wgfmu.real_backend import RealWgfmuBackend
    backend = RealWgfmuBackend()
    backend.open_session()
    backend.initialize()
    print(f"[LIVE] Connected to B1500, channels {PARAMS.chan_gate}/{PARAMS.chan_drain}")

# ── Build measurement plan ───────────────────────────────────────────
plan = build_e1_sequence(cfg)
n_total = len(plan)
print(f"E1 RAWD: {len(DELAYS)} delays × {N_REPEATS} repeats × 2 states × "
      f"{len(PARAMS.vg_read_list)} reads = {n_total} points")
print(f"Delays: {DELAYS}")
print(f"Output: {out_dir}")

# ── Execute ──────────────────────────────────────────────────────────
results = []
t_start = time.time()

for i, point in enumerate(plan):
    state = point["state"]
    delay = point["delay_s"]
    vg = point["vg_read"]
    rep = point["repeat"]
    
    print(f"  [{i+1}/{n_total}] rep={rep} state={state} delay={delay:.1e}s vg={vg:+.1f}V ... ", 
          end="", flush=True)
    
    try:
        if args.dry_run:
            # Simulate: base current + state-dependent shift + delay decay
            base_id = 500e-9 if args.device.startswith("L40") else 50e-9
            state_shift = -200e-9 if state == "ERS" else +100e-9
            delay_decay = 50e-9 * np.exp(-delay / 0.01)
            noise = np.random.normal(0, 10e-9)
            meas = {
                "id_mean": base_id + state_shift + delay_decay + noise,
                "id_std": abs(noise) * 3,
                "ig_mean": 1e-9 * np.random.normal(0, 1),
                "ig_std": 1e-9,
            }
        else:
            meas = run_e1_single_point(backend, cfg, state, delay, vg)
        
        point.update(meas)
        results.append(point)
        print(f"Id={point['id_mean']:.2e}A")
        
    except Exception as e:
        print(f"ERROR: {e}")
        point.update({"id_mean": float("nan"), "id_std": float("nan"),
                       "ig_mean": float("nan"), "ig_std": float("nan"),
                       "error": str(e)})
        results.append(point)

elapsed = time.time() - t_start
print(f"\nDone in {elapsed:.1f}s. {len(results)} points collected.")

# ── Save ─────────────────────────────────────────────────────────────
csv_path = save_e1_results(results, out_dir, cfg)
print(f"Saved: {csv_path}")

# ── Quick analysis ───────────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    for ax, state in zip(axes, ["ERS", "PGM"]):
        state_data = [r for r in results if r["state"] == state and r["vg_read"] == 0.0]
        if not state_data:
            continue
        delays = [r["delay_s"] for r in state_data]
        ids = [abs(r["id_mean"]) for r in state_data]
        ax.scatter(delays, ids, alpha=0.5, s=20)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Post-write delay (s)")
        ax.set_ylabel("|Id| (A)")
        ax.set_title(f"{state} state — Id vs delay (Vg_read=0V)")
        ax.grid(True, alpha=0.3)
    
    fig.suptitle(f"E1 RAWD — {args.device}", fontsize=14)
    fig.tight_layout()
    fig_path = os.path.join(out_dir, "E1_rawd_quick.png")
    fig.savefig(fig_path, dpi=150)
    print(f"Plot: {fig_path}")
    plt.close(fig)
except ImportError:
    print("matplotlib not available, skipping plot")

# ── Cleanup ──────────────────────────────────────────────────────────
if not args.dry_run:
    backend.close_session()
    print("Session closed.")

print(f"\n{'='*60}")
print(f"E1 RAWD complete. Results in: {out_dir}")
print(f"{'='*60}")
