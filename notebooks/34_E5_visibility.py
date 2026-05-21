#!/usr/bin/env python3
"""E5: Vd/Vg read grid — visibility and leakage pathway diagnosis.

After write: read with Vg={-0.4,-0.2,0,+0.2,+0.4}V × Vd={0.01,0.05,0.10,0.50}V
Two read times: 10us and 1s after write

If MW changes sign with different Vd -> Svis (H7) dominates, not real FE issue.
If high Vd gives nonlinear/random jumps -> VO-RS leakage (H9).

Usage:
  python 34_E5_visibility.py --dry-run
"""
import argparse, datetime, os, sys, time, csv
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--device", default="L40W10")
parser.add_argument("--output-dir", default=None)
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
from fefetlab.measurements.wgfmu.experiments import PFeFETParams, E5Config

cfg = E5Config()
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = args.output_dir or os.path.join(PROJECT_ROOT, "runs", f"{ts}_E5_visibility_{args.device}")
os.makedirs(out_dir, exist_ok=True)

total = 2 * len(cfg.read_times_s) * len(cfg.vg_grid) * len(cfg.vd_grid) * 5
print(f"E5 Visibility: 2 states × {len(cfg.read_times_s)} times × "
      f"{len(cfg.vg_grid)} Vg × {len(cfg.vd_grid)} Vd × 5 reps = {total} points")

results = []
for rep in range(5):
    for state in ["ERS", "PGM"]:
        for t_read in cfg.read_times_s:
            for vg in cfg.vg_grid:
                for vd in cfg.vd_grid:
                    if args.dry_run:
                        base = 500e-9 * (vd / 0.05)  # scales with Vd
                        state_eff = -100e-9 if state == "ERS" else 50e-9
                        vg_eff = vg * 200e-9
                        noise = np.random.normal(0, 10e-9)
                        id_val = base + state_eff + vg_eff + noise
                    else:
                        id_val = float("nan")
                    
                    results.append({
                        "repeat": rep, "state": state, 
                        "time_after_write_s": t_read,
                        "Vg_read_V": vg, "Vd_read_V": vd,
                        "Id_mean_A": id_val,
                    })

csv_path = os.path.join(out_dir, f"E5_visibility_{ts}.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=results[0].keys())
    w.writeheader()
    w.writerows(results)
print(f"Saved: {csv_path}")
print(f"E5 complete. {len(results)} points. Results: {out_dir}")
