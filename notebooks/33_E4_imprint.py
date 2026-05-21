#!/usr/bin/env python3
"""E4: Imprint polarity pre-bias test — can pre-bias shift the negative MW center?

Pre-bias: +2V, -2V, 0V for 1ms/10ms/100ms/1s
Then: write(ERS or PGM) -> delay(10us or 10s) -> 3-pt read

If ±2V pre-bias systematically moves the MW center -> H4 imprint or resettable Qocc.
If only short delay affected -> Qocc recoverable, not stable Vimp.

Usage:
  python 33_E4_imprint.py --dry-run
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
from fefetlab.measurements.wgfmu.experiments import PFeFETParams, E4Config

cfg = E4Config()
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = args.output_dir or os.path.join(PROJECT_ROOT, "runs", f"{ts}_E4_imprint_{args.device}")
os.makedirs(out_dir, exist_ok=True)

total = (len(cfg.prebias_voltages) * len(cfg.prebias_durations_s) * 
         len(cfg.post_delays_s) * 2 * len(cfg.params.vg_read_list) * 3)
print(f"E4 Imprint: {len(cfg.prebias_voltages)} polarities × {len(cfg.prebias_durations_s)} durations × "
      f"{len(cfg.post_delays_s)} delays × 2 states × 3 reads × 3 reps = {total} points")

results = []
for rep in range(3):
    for vpre in cfg.prebias_voltages:
        for tpre in cfg.prebias_durations_s:
            for state in ["ERS", "PGM"]:
                for delay in cfg.post_delays_s:
                    for vg in cfg.params.vg_read_list:
                        if args.dry_run:
                            # Simulate: pre-bias shifts center
                            base = 500e-9
                            prebias_effect = vpre * 30e-9 * np.log1p(tpre / 0.01)
                            delay_decay = prebias_effect * 0.5 if delay > 1 else 0
                            id_val = base + prebias_effect - delay_decay + np.random.normal(0, 10e-9)
                        else:
                            id_val = float("nan")
                        
                        results.append({
                            "repeat": rep, "prebias_V": vpre, "prebias_s": tpre,
                            "state": state, "post_delay_s": delay,
                            "vg_read_V": vg, "Id_A": id_val,
                        })

csv_path = os.path.join(out_dir, f"E4_imprint_{ts}.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=results[0].keys())
    w.writeheader()
    w.writerows(results)
print(f"Saved: {csv_path}")
print(f"E4 complete. {len(results)} points. Results: {out_dir}")
