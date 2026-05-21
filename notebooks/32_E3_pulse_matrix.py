#!/usr/bin/env python3
"""E3: PGM/ERS Pulse Width-Amplitude 2D Matrix — find positive-MW operating window.

Sweeps ERS amplitude × width and PGM amplitude × width to find if any 
combination gives MW > 0 (FE dominant over trap).

Quick: 4 amplitudes × 3 widths = 12 points
Full: 4 amplitudes × 6 widths = 24 points per polarity

Usage:
  python 32_E3_pulse_matrix.py --dry-run
  python 32_E3_pulse_matrix.py --full
"""
import argparse, datetime, os, sys, time, csv, random
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--full", action="store_true")
parser.add_argument("--device", default="L40W10")
parser.add_argument("--output-dir", default=None)
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
from fefetlab.measurements.wgfmu.experiments import PFeFETParams, E3Config

PARAMS = PFeFETParams()
cfg = E3Config(params=PARAMS)

V_ERS = cfg.v_ers_list    # [3, 4, 5, 6]
V_PGM = cfg.v_pgm_list    # [-3, -4, -5, -6]
if args.full:
    WIDTHS = cfg.widths_s  # [1us, 3us, 10us, 30us, 100us, 300us]
else:
    WIDTHS = [1e-6, 1e-5, 1e-4]  # quick 3 widths

DELAY = cfg.delay_after_write_s  # 10us

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = args.output_dir or os.path.join(PROJECT_ROOT, "runs", f"{ts}_E3_pulse_matrix_{args.device}")
os.makedirs(out_dir, exist_ok=True)

print(f"E3 Pulse Matrix: {len(V_ERS)} amplitudes × {len(WIDTHS)} widths")

# Build randomized test order
points = []
for ve in V_ERS:
    for vp in V_PGM:
        for tw in WIDTHS:
            points.append({"v_ers": ve, "v_pgm": vp, "width_s": tw})
random.shuffle(points)

results = []
for i, pt in enumerate(points):
    print(f"  [{i+1}/{len(points)}] ERS={pt['v_ers']:+.0f}V PGM={pt['v_pgm']:+.0f}V "
          f"width={pt['width_s']:.0e}s ... ", end="", flush=True)
    
    for vg_read in PARAMS.vg_read_list:
        if args.dry_run:
            # Simulate: stronger/longer pulse -> more FE but also more trap
            fe_contrib = -0.3 * (abs(pt["v_ers"]) / 5) * min(pt["width_s"] / 50e-6, 1)
            trap_contrib = 0.2 * (abs(pt["v_ers"]) / 5) * min(pt["width_s"] / 10e-6, 1)
            mw_proxy = fe_contrib + trap_contrib + np.random.normal(0, 0.02)
            id_ers = 500e-9 + mw_proxy * 200e-9
            id_pgm = 500e-9 - mw_proxy * 100e-9
        else:
            id_ers = float("nan")
            id_pgm = float("nan")
        
        results.append({
            **pt, "vg_read": vg_read, "delay_s": DELAY,
            "Id_ers_A": id_ers, "Id_pgm_A": id_pgm,
            "MW_proxy": id_ers - id_pgm,
        })
    print(f"done")

csv_path = os.path.join(out_dir, f"E3_pulse_matrix_{ts}.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=results[0].keys())
    w.writeheader()
    w.writerows(results)
print(f"Saved: {csv_path}")

# 2D heatmap
try:
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    vg0 = [r for r in results if r["vg_read"] == 0.0]
    if vg0:
        amps = sorted(set(r["v_ers"] for r in vg0))
        wids = sorted(set(r["width_s"] for r in vg0))
        mw_grid = np.full((len(amps), len(wids)), np.nan)
        for r in vg0:
            ai = amps.index(r["v_ers"])
            wi = wids.index(r["width_s"])
            mw_grid[ai, wi] = r["MW_proxy"]
        
        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(mw_grid, aspect="auto", origin="lower",
                       extent=[0, len(wids)-1, 0, len(amps)-1])
        ax.set_xticks(range(len(wids)))
        ax.set_xticklabels([f"{w:.0e}" for w in wids], rotation=45)
        ax.set_yticks(range(len(amps)))
        ax.set_yticklabels([f"{a:+.0f}V" for a in amps])
        ax.set_xlabel("Pulse width (s)")
        ax.set_ylabel("ERS amplitude (V)")
        ax.set_title(f"E3 MW proxy heatmap — {args.device}")
        plt.colorbar(im, label="MW proxy (A)")
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, "E3_heatmap.png"), dpi=150)
        plt.close(fig)
except ImportError:
    pass

print(f"E3 complete. Results: {out_dir}")
