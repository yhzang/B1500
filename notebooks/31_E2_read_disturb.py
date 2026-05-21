#!/usr/bin/env python3
"""E2: Read Disturb Dose Matrix — determine if ID-VG sweep corrupts FeFET state.

Purpose: If Mode A (single pulse read) gives positive MW but Mode C (quasi-static 
sweep) gives negative MW -> read disturb is real, all previous DC data suspect.

Three read modes:
  A: single 5us pulse at Vg_read=0V (minimal disturb)
  B: 11-step staircase -0.5V to +0.5V, 5us/step
  C: quasi-static sweep -1.5V to +1.5V, 2ms/step (high disturb dose)

For each mode, repeat N_read times: 1, 3, 10, 30, 100
After each read-mode block: 5us single-point verify read

Usage:
  python 31_E2_read_disturb.py --dry-run   # test
  python 31_E2_read_disturb.py             # real measurement
"""
import argparse, datetime, os, sys, time
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--device", default="L40W10")
parser.add_argument("--output-dir", default=None)
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
from fefetlab.measurements.wgfmu.experiments import PFeFETParams, E2Config

PARAMS = PFeFETParams()
cfg = E2Config(params=PARAMS)
N_READ_LIST = cfg.n_read_list  # [1, 3, 10, 30]

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = args.output_dir or os.path.join(PROJECT_ROOT, "runs", f"{ts}_E2_read_disturb_{args.device}")
os.makedirs(out_dir, exist_ok=True)

print(f"E2 Read Disturb: modes A/B/C × N_read={N_READ_LIST} × 2 states")
print(f"Output: {out_dir}")

# Mode definitions
MODES = {
    "A": {"desc": "Single 5us pulse", "vg_list": [0.0], "dwell_s": 5e-6},
    "B": {"desc": "11-step staircase", "vg_list": list(np.linspace(-0.5, 0.5, 11)), "dwell_s": 5e-6},
    "C": {"desc": "Quasi-static sweep", "vg_list": list(np.linspace(-1.5, 1.5, 61)), "dwell_s": 2e-3},
}

results = []
for state in ["ERS", "PGM"]:
    for mode_name, mode_cfg in MODES.items():
        for n_read in N_READ_LIST:
            print(f"  state={state} mode={mode_name} n_read={n_read} ... ", end="", flush=True)
            
            if args.dry_run:
                # Simulate: Mode C shifts Vth more than A
                base_id = 500e-9
                mode_shift = {"A": 0, "B": -50e-9, "C": -200e-9}[mode_name]
                n_shift = mode_shift * np.log1p(n_read) / np.log1p(100)
                noise = np.random.normal(0, 10e-9)
                verify_id = base_id + n_shift + noise
            else:
                # TODO: Real hardware execution
                # For each n_read:
                #   1. Reset
                #   2. Write (ERS or PGM, ±5V, 100us)
                #   3. Apply read-mode block n_read times
                #   4. Do 5us verify read
                verify_id = float("nan")
            
            results.append({
                "state": state,
                "mode": mode_name,
                "mode_desc": mode_cfg["desc"],
                "n_read": n_read,
                "read_dose_Vs": n_read * len(mode_cfg["vg_list"]) * mode_cfg["dwell_s"],
                "verify_Id_A": verify_id,
            })
            print(f"verify_Id={verify_id:.2e}A")

# Save CSV
import csv
csv_path = os.path.join(out_dir, f"E2_read_disturb_{ts}.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=results[0].keys())
    w.writeheader()
    w.writerows(results)
print(f"Saved: {csv_path}")

# Quick plot
try:
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, state in zip(axes, ["ERS", "PGM"]):
        for mode in ["A", "B", "C"]:
            d = [r for r in results if r["state"] == state and r["mode"] == mode]
            ax.plot([r["n_read"] for r in d], [abs(r["verify_Id_A"]) for r in d],
                    "o-", label=f"Mode {mode}")
        ax.set_xlabel("N_read (cumulative reads)")
        ax.set_ylabel("|Id_verify| (A)")
        ax.set_xscale("log")
        ax.set_title(f"{state} — Read Disturb")
        ax.legend()
        ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "E2_read_disturb.png"), dpi=150)
    plt.close(fig)
except ImportError:
    pass

print(f"E2 complete. Results: {out_dir}")
