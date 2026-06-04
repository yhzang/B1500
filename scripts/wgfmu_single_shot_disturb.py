#!/usr/bin/env python
"""Single-write WGFMU tests for fragile L10 pFeFET points (E6S + E1S).

Standalone companion to ``wgfmu_next_round_minimal.py``. It DOES NOT modify that
module — it only *imports* its already-validated backend / orchestration helpers
(dry-run audit backend, channel validation, read-phase math, stop gates, CSV /
manifest writers) and adds new experiments that each write the device only once.

Why a new file / single-write stages
-------------------------------------
These L10 points only survive their *first* write (cycle / pause / paired
E6R+E6D, and even the base E1 which re-writes for every delay, collapse or break
on later writes). So any measurement that needs many writes can never run here.
Both stages below write the device **exactly once per shot** and do everything
else inside ONE WGFMU pattern / ONE execute(), staying inside the first-shot
budget.

Stages
------
E6S — single-shot disturb:
    reset -> write(ERS|PGM) -> READ[pre] -> neutral wait
          -> disturb pulse (opposite polarity, half-Vdd-ish)
          -> ( wait(delay) -> READ[post] )   for each post-delay
    Outputs dId @ main read point and dVth = -dId/gm (gm from the pre-read).

E1S — single-write retention / relaxation (E1 done with ONE write):
    reset -> write(ERS|PGM) -> ( wait(delay) -> READ )  for each delay
    i.e. write once, then watch that ONE written state relax by reading at
    increasing delays WITHOUT re-writing. ERS and PGM are separate shots, so a
    full ERS+PGM retention curve costs only 2 writes (vs base E1's 16-22).

    IMPORTANT physics tradeoff vs base E1: because there is only one write, the
    reads are cumulative in real time and each read (~a few us per Vg point)
    consumes time, so very short requested delays can merge. The honest, actually
    realized delay is recorded per row as delay_s (requested value kept in
    requested_delay_s). For clean sub-10us resolution use base E1 (fresh write per
    delay) instead; E1S trades that for not destroying the device.

Read points default to [-1.0 V, -0.7 V]: -1.0 V is the main MW read point; the
-0.7 V neighbour gives a local transconductance gm (used by E6S for dVth).

Safety
------
Dry-run is the DEFAULT (no VISA, no DLL, no hardware output). Live mode must be
requested explicitly:  --stage <E6S|E1S> --live --confirm <E6S|E1S> . Negative-
valued list args must use '=', e.g.  --read-vg=-1.0,-0.7 .
"""
from __future__ import annotations

import argparse
import datetime as _dt
import math
import sys
from pathlib import Path

# --- import the existing, tested module without modifying it ----------------
# This file is expected to live next to wgfmu_next_round_minimal.py (scripts/).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import wgfmu_next_round_minimal as base  # noqa: E402  reuse backend + orchestration

# Pull the orchestration primitives that base imported into its namespace.
ExperimentContext = base.ExperimentContext
StopGate = base.StopGate
StopGatePolicy = base.StopGatePolicy
make_stage_dir = base.make_stage_dir
summarize_rows = base.summarize_rows
validate_live_request = base.validate_live_request
write_manifest_yaml = base.write_manifest_yaml
write_report_code = base.write_report_code
write_rows_csv = base.write_rows_csv
write_summary_md = base.write_summary_md

# ---------------------------------------------------------------------------
# E6S defaults
# ---------------------------------------------------------------------------
STAGE_NAME = "E6S"
STAGE_LABEL = "E6S_single_shot_disturb"
CSV_NAME = "e6s_single_shot_disturb.csv"

E6S_READ_VG_DEFAULT = [-1.0, -0.7]   # [0] = main MW read point, [1] = gm neighbour
E6S_MAIN_VG = -1.0
E6S_AMP_DEFAULT = 2.5                # disturb magnitude (V); sign opposite to written state
E6S_WIDTH_DEFAULT = 100e-6           # disturb pulse width (s)
E6S_POST_DELAYS_DEFAULT = [1e-6, 1e-4, 1e-2]  # disturb-end -> post-read delays (s)
E6S_NEUTRAL_WAIT = 10e-6             # gap between pre-read and disturb pulse
E6S_IG_STOP_UA_DEFAULT = 30.0

# ---------------------------------------------------------------------------
# E1S defaults (single-write retention / relaxation)
# ---------------------------------------------------------------------------
E1S_STAGE_LABEL = "E1S_single_write_retention"
E1S_CSV_NAME = "e1s_single_write_retention.csv"
# Wide pFeFET read grid incl. main MW point -1.0 V (mirrors base VG_E5 minus the
# positive tail; deep-subthreshold MW is invisible near Vg≈0).
E1S_READ_VG_DEFAULT = [-1.0, -0.7, -0.4, -0.2, 0.0]
E1S_MAIN_VG = -1.0
# Requested delays from write-end to each read; must be increasing (no time
# travel in one waveform). Short ones may merge — see module docstring.
E1S_DELAYS_DEFAULT = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0]
E1S_IG_STOP_UA_DEFAULT = 20.0

E1S_FIELDNAMES = [
    "timestamp_iso", "stage", "device_id", "geometry", "sequence_id", "repeat_index",
    "state_target", "requested_delay_s", "delay_s", "Vg_read_V", "Vd_read_V",
    "Id_mean_A", "Id_std_A", "Ig_mean_A", "Ig_std_A", "n_d", "n_g", "note",
]

# ---------------------------------------------------------------------------
# E6M defaults (multi-disturb accumulation: one full write, then many
# subcritical disturb pulses, read only at key N checkpoints)
# ---------------------------------------------------------------------------
E6M_STAGE_LABEL = "E6M_multi_disturb_accumulation"
E6M_CSV_NAME = "e6m_multi_disturb_accumulation.csv"
E6M_READ_VG_DEFAULT = [-1.0, -0.7]   # [0] main MW point, [1] gm neighbour
E6M_MAIN_VG = -1.0
# Disturb pulse = subcritical (half/third-Vdd), OPPOSITE polarity to written
# state, applied repeatedly. Default ~1/2 Vdd for +/-5 V write; pass 1.67 for
# ~1/3 Vdd. Keep it subcritical (below FE switch threshold) so the device is
# only "written" once (the single full write), and the train is a disturb train.
E6M_AMP_DEFAULT = 2.5
# E6M disturb pulse width shares --disturb-width-s with E6S (default 100us), so
# E6M at N=1 is directly comparable to one E6S disturb pulse. Shorten via CLI for
# pulse-train style if desired.
E6M_INTERVAL_DEFAULT = 1e-6  # gap between disturb pulses (s); larger -> more recovery
E6M_CHECKPOINTS_DEFAULT = [1, 3, 10, 30, 100, 300, 1000]
E6M_IG_STOP_UA_DEFAULT = 30.0
E6M_VECTORS_PER_PULSE = 4    # rise + hold + fall + interval (on gp)

E6M_FIELDNAMES = [
    "timestamp_iso", "stage", "device_id", "geometry", "sequence_id", "repeat_index",
    "state_target", "n_disturb", "cum_disturb_time_s", "phase", "Vg_read_V", "Vd_read_V",
    "Id_mean_A", "Id_std_A", "Ig_mean_A", "Ig_std_A", "n_d", "n_g",
    "initial_state", "V_disturb_V", "t_disturb_s", "t_interval_s",
    "dId_vs_base_A", "gm_S", "dVth_vs_base_V", "note",
]

_READ_GAP = 1e-6

FIELDNAMES = [
    "timestamp_iso", "stage", "device_id", "geometry", "sequence_id", "repeat_index",
    "state_target", "phase", "delay_after_disturb_s", "Vg_read_V", "Vd_read_V",
    "Id_mean_A", "Id_std_A", "Ig_mean_A", "Ig_std_A", "n_d", "n_g",
    "initial_state", "V_disturb_V", "t_disturb_s",
    "dId_disturb_A", "gm_S", "dVth_disturb_V", "note",
]


def _parse_float_list_csv(value):
    if value is None or str(value).strip() == "":
        return []
    out = []
    for part in str(value).split(","):
        part = part.strip()
        if part:
            out.append(float(part))
    return out


def _parse_int_list_csv(value):
    if value is None or str(value).strip() == "":
        return []
    out = []
    for part in str(value).split(","):
        part = part.strip()
        if part:
            out.append(int(part))
    return out


def _resolve_write_v(state: str, args) -> float | None:
    """Write magnitude honoring --write-v; polarity stays ERS=+ / PGM=-.
    Returns None to let run_e6s_shot fall back to base.V_ERS/V_PGM (+/-5 V)."""
    wv = getattr(args, "write_v", None)
    if wv is None:
        return None
    mag = abs(float(wv))
    return +mag if state == "ERS" else -mag


# ---------------------------------------------------------------------------
# Read-phase builder (own copy, supports an event-name prefix so several read
# blocks can coexist in ONE pattern). Mirrors base._build_read_phase timing so
# base._summarize_windows / base._configure_and_run_phase work unchanged.
# ---------------------------------------------------------------------------
def _read_block_duration(n_vg: int, t_read: float) -> float:
    n = max(int(n_vg), 0)
    return n * (2 * base.T_RF + t_read) + max(n - 1, 0) * _READ_GAP


def _add_read_block(backend, *, vg_reads, vd_read, n_pts, t_read,
                    event_offset_s, event_prefix):
    """Append one read block to patterns 'gp'/'dp'; return (windows, duration_s).

    Keeps gate and drain pattern durations equal (WGFMU requires aligned
    patterns), exactly like base._build_read_phase.
    """
    guard = min(200e-9, t_read * 0.2)
    meas_window = max(t_read - guard, t_read * 0.5)
    interval = meas_window / max(n_pts, 1)
    average = min(200e-9, interval * 0.8)

    windows = []
    t_cursor = 0.0
    for i, vg in enumerate(vg_reads):
        backend.add_vector("gp", base.T_RF, float(vg)); t_cursor += base.T_RF
        read_start = t_cursor
        backend.add_vector("gp", t_read, float(vg)); t_cursor += t_read
        backend.add_vector("gp", base.T_RF, 0.0); t_cursor += base.T_RF
        windows.append({
            "idx": i,
            "vg": float(vg),
            "vd": float(vd_read),
            "t0": event_offset_s + read_start + guard,
            "t1": event_offset_s + read_start + t_read,
        })
        if i < len(vg_reads) - 1:
            backend.add_vector("gp", _READ_GAP, 0.0); t_cursor += _READ_GAP

    # Drain: hold Vd across the whole block, matched total duration.
    backend.add_vector("dp", base.T_RF, float(vd_read))
    backend.add_vector("dp", max(t_cursor - 2 * base.T_RF, base.T_RF), float(vd_read))
    backend.add_vector("dp", base.T_RF, 0.0)

    for w in windows:
        i = w["idx"]
        backend.set_measure_event("gp", f"{event_prefix}g{i}", w["t0"], n_pts, interval, average, "averaged")
        backend.set_measure_event("dp", f"{event_prefix}d{i}", w["t0"], n_pts, interval, average, "averaged")
    return windows, t_cursor


# ---------------------------------------------------------------------------
# The single-shot disturb shot: ONE write, pre-read, disturb, post-read(s).
# ---------------------------------------------------------------------------
def run_e6s_shot(backend, *, initial_state, v_disturb, t_disturb_s, post_delays_s,
                 vg_reads, vd_read, n_pts, t_read, v_write, t_write,
                 neutral_wait=E6S_NEUTRAL_WAIT):
    if v_write is None:
        v_initial = base.V_ERS if initial_state == "ERS" else base.V_PGM
    else:
        mag = abs(float(v_write))
        v_initial = +mag if initial_state == "ERS" else -mag

    post_delays = sorted(float(d) for d in post_delays_s if float(d) >= 0)
    if not post_delays:
        post_delays = [neutral_wait]

    backend.clear()
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)

    t_cursor = 0.0
    # reset + the ONE write pulse
    for dt, vg in [
        (base.T_RESET, 0.0),
        (base.T_RF, v_initial),
        (t_write, v_initial),
        (base.T_RF, 0.0),
    ]:
        backend.add_vector("gp", dt, float(vg))
        backend.add_vector("dp", dt, 0.0)
        t_cursor += dt

    windows = []

    # pre-disturb read
    pre_w, dur = _add_read_block(
        backend, vg_reads=vg_reads, vd_read=vd_read, n_pts=n_pts, t_read=t_read,
        event_offset_s=t_cursor, event_prefix="pre_",
    )
    for w in pre_w:
        w["phase"] = "pre"
        w["delay_after_disturb_s"] = ""
    windows.extend(pre_w)
    t_cursor += dur

    # neutral gap, then the disturb pulse
    for dt, vg in [
        (neutral_wait, 0.0),
        (base.T_RF, v_disturb),
        (t_disturb_s, v_disturb),
        (base.T_RF, 0.0),
    ]:
        backend.add_vector("gp", dt, float(vg))
        backend.add_vector("dp", dt, 0.0)
        t_cursor += dt
    t_disturb_end = t_cursor

    # post-disturb reads at increasing, honest delays
    for k, d in enumerate(post_delays):
        target_start = t_disturb_end + d
        wait_needed = target_start - t_cursor
        if wait_needed > 0:
            backend.add_vector("gp", wait_needed, 0.0)
            backend.add_vector("dp", wait_needed, 0.0)
            t_cursor += wait_needed
        actual_delay = t_cursor - t_disturb_end
        post_w, dur = _add_read_block(
            backend, vg_reads=vg_reads, vd_read=vd_read, n_pts=n_pts, t_read=t_read,
            event_offset_s=t_cursor, event_prefix=f"post{k}_",
        )
        for w in post_w:
            w["phase"] = "post"
            w["delay_after_disturb_s"] = actual_delay
        windows.extend(post_w)
        t_cursor += dur

    timeout_s = max(30.0, t_cursor * 3 + 10.0)
    g_df, d_df = base._configure_and_run_phase(backend, measure=True, timeout_s=timeout_s)
    out = base._summarize_windows(g_df, d_df, windows)
    for o, w in zip(out, windows):
        o["phase"] = w["phase"]
        o["delay_after_disturb_s"] = w["delay_after_disturb_s"]
    return out


def run_e1s_shot(backend, *, state, delays_s, vg_reads, vd_read, n_pts, t_read,
                 v_write, t_write):
    """Single-write retention: ONE write, then read at increasing delays without
    re-writing. Returns flat read rows tagged with the actually-realized delay
    (delay_s) and the originally-requested delay (requested_delay_s).

    The whole sequence lives in one pattern / one execute, so the device is
    written exactly once. Delays are realized as the wall-clock offset from the
    end of the write pulse to the start of each read block; because reads take
    real time, short requested delays may be rounded up (honest value reported).
    """
    if v_write is None:
        v_w = base.V_ERS if state == "ERS" else base.V_PGM
    else:
        mag = abs(float(v_write))
        v_w = +mag if state == "ERS" else -mag

    delays = sorted(float(d) for d in delays_s if float(d) >= 0)
    if not delays:
        delays = [1e-6]

    backend.clear()
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)

    t_cursor = 0.0
    # reset + the ONE write pulse
    for dt, vg in [
        (base.T_RESET, 0.0),
        (base.T_RF, v_w),
        (t_write, v_w),
        (base.T_RF, 0.0),
    ]:
        backend.add_vector("gp", dt, float(vg))
        backend.add_vector("dp", dt, 0.0)
        t_cursor += dt
    t_write_end = t_cursor

    windows = []
    for k, d in enumerate(delays):
        target_start = t_write_end + d
        wait_needed = target_start - t_cursor
        if wait_needed > 0:
            backend.add_vector("gp", wait_needed, 0.0)
            backend.add_vector("dp", wait_needed, 0.0)
            t_cursor += wait_needed
        actual_delay = t_cursor - t_write_end
        block_w, dur = _add_read_block(
            backend, vg_reads=vg_reads, vd_read=vd_read, n_pts=n_pts, t_read=t_read,
            event_offset_s=t_cursor, event_prefix=f"d{k}_",
        )
        for w in block_w:
            w["requested_delay_s"] = d
            w["delay_s"] = actual_delay
        windows.extend(block_w)
        t_cursor += dur

    timeout_s = max(30.0, t_cursor * 3 + 10.0)
    g_df, d_df = base._configure_and_run_phase(backend, measure=True, timeout_s=timeout_s)
    out = base._summarize_windows(g_df, d_df, windows)
    for o, w in zip(out, windows):
        o["requested_delay_s"] = w["requested_delay_s"]
        o["delay_s"] = w["delay_s"]
    return out


def _gm_from_pre(pre_by_vg: dict, main_vg: float):
    """Local gm (S) at main_vg from the pre-disturb read using two Vg points."""
    vgs = sorted(pre_by_vg.keys())
    if main_vg not in pre_by_vg or len(vgs) < 2:
        return float("nan")
    others = [v for v in vgs if v != main_vg]
    nb = min(others, key=lambda v: abs(v - main_vg))
    dv = float(main_vg) - float(nb)
    if dv == 0:
        return float("nan")
    return (float(pre_by_vg[main_vg]) - float(pre_by_vg[nb])) / dv


# ---------------------------------------------------------------------------
# Stage driver
# ---------------------------------------------------------------------------
def _check_samples(rows, stage):
    bad = [r for r in rows if int(r.get("n_d", 0)) <= 0 or int(r.get("n_g", 0)) <= 0]
    if bad:
        raise StopGate(f"{stage}_STOP_NO_SAMPLES", f"{len(bad)} rows have n_d/n_g <= 0")


def _check_ig(rows, stage, threshold_uA):
    StopGatePolicy(
        metric="Ig_mean_A",
        threshold=threshold_uA * 1e-6,
        threshold_label=f"{threshold_uA:g}UA",
    ).check(rows, stage)


def run_stage_e6s(backend, args):
    ctx = ExperimentContext(
        root=base.ROOT, device_id=args.device_id, geometry=args.geometry,
        live=args.live, seed=args.seed,
    )
    out_dir = make_stage_dir(ctx, STAGE_LABEL)

    vg_reads = _parse_float_list_csv(args.read_vg) or list(E6S_READ_VG_DEFAULT)
    main_vg = E6S_MAIN_VG if any(abs(v - E6S_MAIN_VG) < 1e-9 for v in vg_reads) else vg_reads[0]
    main_key = round(float(main_vg), 6)
    _e6s_wide_recovery = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0]
    post_delays = (_parse_float_list_csv(args.post_delays)
                   or (_e6s_wide_recovery if getattr(args, "wide_recovery", False) else list(E6S_POST_DELAYS_DEFAULT)))
    amp_abs = abs(float(args.disturb_amp))
    t_read = float(args.t_read_s)
    vd_read = float(args.vd_read)

    rows = []
    seq = 0
    for rep in range(args.reps):
        for initial_state in (["ERS", "PGM"] if args.write_state == "BOTH" else [args.write_state]):
            v_disturb = -amp_abs if initial_state == "ERS" else amp_abs
            rr = run_e6s_shot(
                backend,
                initial_state=initial_state,
                v_disturb=v_disturb,
                t_disturb_s=args.disturb_width_s,
                post_delays_s=post_delays,
                vg_reads=vg_reads,
                vd_read=vd_read,
                n_pts=args.n_pts,
                t_read=t_read,
                v_write=_resolve_write_v(initial_state, args),
                t_write=float(getattr(args, "t_write_s", None) or base.T_WRITE),
                neutral_wait=args.neutral_wait_s,
            )

            # pre-disturb Id by Vg -> local gm at main read point
            pre_by_vg = {round(float(r["Vg_read_V"]), 6): r["Id_mean_A"]
                         for r in rr if r.get("phase") == "pre"}
            gm = _gm_from_pre(pre_by_vg, main_key)
            pre_main = pre_by_vg.get(main_key, float("nan"))

            for r in rr:
                vg_key = round(float(r["Vg_read_V"]), 6)
                is_main_post = (r.get("phase") == "post" and vg_key == main_key)
                if is_main_post and not math.isnan(pre_main):
                    d_id = float(r["Id_mean_A"]) - float(pre_main)
                    d_vth = (-d_id / gm) if (gm and not math.isnan(gm)) else float("nan")
                else:
                    d_id = ""
                    d_vth = ""
                rows.append({
                    "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                    "stage": "E6S", "device_id": args.device_id, "geometry": args.geometry,
                    "sequence_id": seq, "repeat_index": rep, "state_target": initial_state,
                    "phase": r.get("phase", ""),
                    "delay_after_disturb_s": r.get("delay_after_disturb_s", ""),
                    "Vg_read_V": r["Vg_read_V"], "Vd_read_V": r["Vd_read_V"],
                    "Id_mean_A": r["Id_mean_A"], "Id_std_A": r["Id_std_A"],
                    "Ig_mean_A": r["Ig_mean_A"], "Ig_std_A": r["Ig_std_A"],
                    "n_d": r["n_d"], "n_g": r["n_g"],
                    "initial_state": initial_state,
                    "V_disturb_V": v_disturb,
                    "t_disturb_s": args.disturb_width_s,
                    "dId_disturb_A": d_id,
                    "gm_S": (gm if is_main_post else ""),
                    "dVth_disturb_V": d_vth,
                    "note": f"single_shot_disturb_after_{initial_state}_{v_disturb:+g}V_{args.disturb_width_s:g}s",
                })
            try:
                _check_samples(rows[-len(rr):], "E6S")
                _check_ig(rows[-len(rr):], "E6S", args.e6s_ig_stop_uA)
            except StopGate:
                # fragile L10: a tripped stop-gate must NOT discard the already-measured
                # (irreplaceable first-shot) rows. Flush before propagating the gate.
                if rows:
                    write_rows_csv(out_dir / CSV_NAME, rows, FIELDNAMES)
                raise
            _gm_str = f"{gm:.3e}" if not math.isnan(gm) else "nan"
            print(f"SHOT_OK: E6S rep={rep} initial={initial_state} disturb={v_disturb:+g}V "
                  f"pre_main={pre_main:.3e}A gm={_gm_str}S seq={seq}")
            seq += 1

    out_csv = out_dir / CSV_NAME
    write_rows_csv(out_csv, rows, FIELDNAMES)

    code = "E6S_SINGLE_SHOT_DISTURB_DONE"
    summary = summarize_rows("E6S", out_csv, rows, code)
    manifest = {
        "stage": "E6S",
        "stage_label": STAGE_LABEL,
        "device_id": args.device_id,
        "geometry": args.geometry,
        "live": bool(args.live),
        "plan_mode_equivalent": not bool(args.live),
        "seed": args.seed,
        "channels": {
            "gate": base.GATE_CH, "drain": base.DRAIN_CH,
            "allowed": sorted(base.ALLOWED_CHANNELS), "forbidden": sorted(base.FORBIDDEN_CHANNELS),
        },
        "protocol": "single_shot: reset->write->read[pre]->disturb->read[post]xN (ONE write per shot)",
        "e6s_params": {
            "reps_per_state": args.reps,
            "read_vg": vg_reads,
            "main_vg": main_vg,
            "vd_read": vd_read,
            "t_read_s": t_read,
            "disturb_amp_abs_V": amp_abs,
            "disturb_width_s": args.disturb_width_s,
            "post_delays_s": post_delays,
            "neutral_wait_s": args.neutral_wait_s,
            "write_v_arg": getattr(args, "write_v", None),
            "v_ers_eff": (_resolve_write_v("ERS", args) if getattr(args, "write_v", None) is not None else base.V_ERS),
            "v_pgm_eff": (_resolve_write_v("PGM", args) if getattr(args, "write_v", None) is not None else base.V_PGM),
            "t_write_s_eff": float(getattr(args, "t_write_s", None) or base.T_WRITE),
        },
        "stop_gate_uA": {"E6S": args.e6s_ig_stop_uA},
        "output_csv": str(out_csv),
        "report_code": code,
        "command_args": list(getattr(args, "_argv", sys.argv[1:])),
    }
    manifest_path = write_manifest_yaml(out_csv.parent, manifest)
    write_report_code(out_csv.parent, summary)
    write_summary_md(out_csv.parent, summary, manifest_path=manifest_path)
    print(f"MANIFEST: {manifest_path}")
    return summary


def _run_disturb_train_chunk(backend, *, v_disturb, t_disturb_s, t_interval_s, n_pulses):
    """Apply n_pulses subcritical disturb pulses on the gate in ONE pattern /
    ONE execute, no readout. Drain held at 0. Used between read checkpoints.

    Each pulse = rise(T_RF) + hold(t_disturb) + fall(T_RF) + interval gap.
    """
    if n_pulses <= 0:
        return
    backend.clear()
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)
    t_total = 0.0
    for _ in range(int(n_pulses)):
        for dt, vg in [
            (base.T_RF, v_disturb),
            (t_disturb_s, v_disturb),
            (base.T_RF, 0.0),
            (t_interval_s, 0.0),
        ]:
            backend.add_vector("gp", dt, float(vg))
            backend.add_vector("dp", dt, 0.0)
            t_total += dt
    timeout_s = max(30.0, t_total * 3 + 10.0)
    base._configure_and_run_phase(backend, measure=False, timeout_s=timeout_s)
    return t_total


def _e6m_max_pulses_per_chunk():
    """Max disturb pulses per pattern, honoring the WGFMU vector budget."""
    budget = base.WGFMU_MAX_VECTORS_PER_PATTERN - 128
    # each pulse adds 4 vectors on gp AND 4 on dp; the per-pattern cap applies
    # per pattern, so 4 vectors/pulse on the gp pattern is the binding limit.
    return max(1, budget // E6M_VECTORS_PER_PULSE)


def _run_disturb_train_to(backend, *, v_disturb, t_disturb_s, t_interval_s,
                          current_n, target_n):
    """Advance the cumulative disturb count from current_n to target_n, chunking
    so no single pattern exceeds the vector budget. Returns (new_n, added_time_s).
    """
    remaining = int(target_n) - int(current_n)
    if remaining < 0:
        raise ValueError(f"checkpoint regressed: current={current_n} target={target_n}")
    max_chunk = _e6m_max_pulses_per_chunk()
    added_time = 0.0
    while remaining > 0:
        chunk = min(max_chunk, remaining)
        dt = _run_disturb_train_chunk(
            backend, v_disturb=v_disturb, t_disturb_s=t_disturb_s,
            t_interval_s=t_interval_s, n_pulses=chunk,
        )
        added_time += dt or 0.0
        current_n += chunk
        remaining -= chunk
    return current_n, added_time


def run_stage_e6m(backend, args):
    """E6M: multi-disturb accumulation. ONE full write, then a train of many
    SUBCRITICAL (half/third-Vdd, opposite-polarity) disturb pulses; read the
    state only at key N checkpoints (1,3,10,...) to trace Id vs cumulative
    disturb count. The device is fully written exactly once per (state) shot;
    the train is below the FE switch threshold, so it disturbs without
    re-writing — stays inside the first-shot budget.

    KB framing (Hoffmann2022 / Otomo2024 / Hamai2023 / Ni2018 / Dahan2022):
    repeated disturb is history-conditioned (not linear accumulation); pulse
    width and inter-pulse interval are state-reconditioning knobs, so larger
    intervals should suppress accumulation.
    """
    ctx = ExperimentContext(
        root=base.ROOT, device_id=args.device_id, geometry=args.geometry,
        live=args.live, seed=args.seed,
    )
    out_dir = make_stage_dir(ctx, E6M_STAGE_LABEL)

    vg_reads = _parse_float_list_csv(args.read_vg) or list(E6M_READ_VG_DEFAULT)
    main_vg = E6M_MAIN_VG if any(abs(v - E6M_MAIN_VG) < 1e-9 for v in vg_reads) else vg_reads[0]
    main_key = round(float(main_vg), 6)
    checkpoints = sorted(set(int(c) for c in _parse_int_list_csv(args.checkpoints)
                             if int(c) > 0)) or list(E6M_CHECKPOINTS_DEFAULT)
    amp_abs = abs(float(args.disturb_amp))
    t_disturb = float(args.disturb_width_s)
    t_interval = float(args.interval_s)
    vd_read = float(args.vd_read)
    t_write = float(getattr(args, "t_write_s", None) or base.T_WRITE)

    states = ["ERS"] if args.e6m_state == "ERS" else (["PGM"] if args.e6m_state == "PGM" else ["ERS", "PGM"])

    rows = []
    seq = 0
    for rep in range(args.reps):
        for initial_state in states:
            v_write = _resolve_write_v(initial_state, args)
            v_disturb = -amp_abs if initial_state == "ERS" else amp_abs

            # --- ONE full write ---
            base._run_reset_write_phase(backend, state=initial_state,
                                        v_write=v_write, t_write=t_write)

            # --- baseline read (N=0), no disturb yet ---
            base_rr = base.run_readonly_shot(backend, vg_reads=vg_reads,
                                             vd_read=vd_read, n_pts=args.n_pts)
            base_by_vg = {round(float(r["Vg_read_V"]), 6): r["Id_mean_A"] for r in base_rr}
            gm = _gm_from_pre(base_by_vg, main_key)
            base_main = base_by_vg.get(main_key, float("nan"))

            def _emit(rr, n_disturb, cum_time, phase):
                for r in rr:
                    vg_key = round(float(r["Vg_read_V"]), 6)
                    is_main = (vg_key == main_key)
                    if is_main and not math.isnan(base_main):
                        d_id = float(r["Id_mean_A"]) - float(base_main)
                        d_vth = (-d_id / gm) if (gm and not math.isnan(gm)) else float("nan")
                    else:
                        d_id, d_vth = "", ""
                    rows.append({
                        "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                        "stage": "E6M", "device_id": args.device_id, "geometry": args.geometry,
                        "sequence_id": seq, "repeat_index": rep, "state_target": initial_state,
                        "n_disturb": n_disturb, "cum_disturb_time_s": cum_time, "phase": phase,
                        "Vg_read_V": r["Vg_read_V"], "Vd_read_V": r["Vd_read_V"],
                        "Id_mean_A": r["Id_mean_A"], "Id_std_A": r["Id_std_A"],
                        "Ig_mean_A": r["Ig_mean_A"], "Ig_std_A": r["Ig_std_A"],
                        "n_d": r["n_d"], "n_g": r["n_g"],
                        "initial_state": initial_state, "V_disturb_V": v_disturb,
                        "t_disturb_s": t_disturb, "t_interval_s": t_interval,
                        "dId_vs_base_A": (d_id if is_main else ""),
                        "gm_S": (gm if is_main else ""),
                        "dVth_vs_base_V": (d_vth if is_main else ""),
                        "note": f"N={n_disturb}_{phase}_after_{initial_state}_disturb{v_disturb:+g}V",
                    })

            _emit(base_rr, 0, 0.0, "baseline")

            # --- disturb train with checkpoint reads ---
            current_n = 0
            cum_time = 0.0
            for cp in checkpoints:
                current_n, added = _run_disturb_train_to(
                    backend, v_disturb=v_disturb, t_disturb_s=t_disturb,
                    t_interval_s=t_interval, current_n=current_n, target_n=cp,
                )
                cum_time += added
                rr = base.run_readonly_shot(backend, vg_reads=vg_reads,
                                            vd_read=vd_read, n_pts=args.n_pts)
                _emit(rr, current_n, cum_time, "checkpoint")
                try:
                    _check_samples(rows[-len(rr):], "E6M")
                    _check_ig(rows[-len(rr):], "E6M", args.e6m_ig_stop_uA)
                except StopGate:
                    # fragile L10: flush measured checkpoints before the stop-gate aborts.
                    if rows:
                        write_rows_csv(out_dir / E6M_CSV_NAME, rows, E6M_FIELDNAMES)
                    raise
                # progress: dId at main point vs baseline
                main_now = next((float(r["Id_mean_A"]) for r in rr
                                 if round(float(r["Vg_read_V"]), 6) == main_key), float("nan"))
                did = (main_now - base_main) if not math.isnan(base_main) else float("nan")
                print(f"SHOT_OK: E6M rep={rep} {initial_state} N={current_n} "
                      f"Id@{main_vg:g}V={main_now:.3e}A dId={did:+.3e}A seq={seq}")
                seq += 1

    out_csv = out_dir / E6M_CSV_NAME
    write_rows_csv(out_csv, rows, E6M_FIELDNAMES)

    code = "E6M_MULTI_DISTURB_ACCUMULATION_DONE"
    summary = summarize_rows("E6M", out_csv, rows, code)
    manifest = {
        "stage": "E6M", "stage_label": E6M_STAGE_LABEL,
        "device_id": args.device_id, "geometry": args.geometry,
        "live": bool(args.live), "plan_mode_equivalent": not bool(args.live),
        "seed": args.seed,
        "channels": {
            "gate": base.GATE_CH, "drain": base.DRAIN_CH,
            "allowed": sorted(base.ALLOWED_CHANNELS), "forbidden": sorted(base.FORBIDDEN_CHANNELS),
        },
        "protocol": "multi_disturb: reset->ONE full write->baseline read->"
                    "(disturb train chunked, read at N checkpoints). Disturb is "
                    "subcritical (alpha*Vdd), opposite polarity; device written once.",
        "e6m_params": {
            "reps": args.reps, "states": states, "read_vg": vg_reads, "main_vg": main_vg,
            "vd_read": vd_read, "checkpoints_N": checkpoints,
            "disturb_amp_abs_V": amp_abs, "disturb_width_s": t_disturb,
            "interval_s": t_interval, "max_pulses_per_chunk": _e6m_max_pulses_per_chunk(),
            "write_v_arg": getattr(args, "write_v", None),
            "v_ers_eff": (_resolve_write_v("ERS", args) if getattr(args, "write_v", None) is not None else base.V_ERS),
            "v_pgm_eff": (_resolve_write_v("PGM", args) if getattr(args, "write_v", None) is not None else base.V_PGM),
            "t_write_s_eff": t_write,
        },
        "stop_gate_uA": {"E6M": args.e6m_ig_stop_uA},
        "output_csv": str(out_csv), "report_code": code,
        "command_args": list(getattr(args, "_argv", sys.argv[1:])),
    }
    manifest_path = write_manifest_yaml(out_csv.parent, manifest)
    write_report_code(out_csv.parent, summary)
    write_summary_md(out_csv.parent, summary, manifest_path=manifest_path)
    print(f"MANIFEST: {manifest_path}")
    return summary


def _print_plan_e6m(args) -> None:
    vg_reads = _parse_float_list_csv(args.read_vg) or list(E6M_READ_VG_DEFAULT)
    checkpoints = sorted(set(int(c) for c in _parse_int_list_csv(args.checkpoints)
                             if int(c) > 0)) or list(E6M_CHECKPOINTS_DEFAULT)
    _wv = getattr(args, "write_v", None)
    if _wv is None:
        ers, pgm, src = base.V_ERS, base.V_PGM, "default(+/-5 V)"
    else:
        ers, pgm, src = _resolve_write_v("ERS", args), _resolve_write_v("PGM", args), "--write-v"
    tw = float(getattr(args, "t_write_s", None) or base.T_WRITE)
    states = ["ERS"] if args.e6m_state == "ERS" else (["PGM"] if args.e6m_state == "PGM" else ["ERS", "PGM"])
    print("PLAN_BEGIN")
    print(f"live={args.live} stage=E6M device_id={args.device_id} geometry={args.geometry}")
    print(f"channels: Gate={base.GATE_CH}, Drain={base.DRAIN_CH}; "
          f"allowed={sorted(base.ALLOWED_CHANNELS)} forbidden={sorted(base.FORBIDDEN_CHANNELS)}")
    print(f"WRITE_PARAMS: ERS={ers:+g}V PGM={pgm:+g}V t_write={tw:g}s (src={src})  [ONE full write per shot]")
    print(f"READ_PARAMS: vd_read={float(args.vd_read):g}V read_vg={vg_reads} (main={E6M_MAIN_VG:g}V)")
    print("E6M: ONE full write -> baseline read -> subcritical disturb TRAIN, read only at N checkpoints.")
    print(f"  disturb: amp=-/+{abs(float(args.disturb_amp)):g}V (opposite to state, SUBCRITICAL), "
          f"width={float(args.disturb_width_s):g}s, interval={float(args.interval_s):g}s")
    print(f"  checkpoints_N={checkpoints}  states={states}  reps={args.reps}")
    print(f"  chunked: <= {_e6m_max_pulses_per_chunk()} pulses/pattern (vector budget safe)")
    print(f"  outputs: Id & dId(vs baseline) & dVth at main point vs cumulative N")
    print(f"  stop |Ig|>{args.e6m_ig_stop_uA:g} uA")
    print("PLAN_END")


def run_stage_e1s(backend, args):
    """E1S: single-write retention. ONE write per (state, rep); read the same
    written state at increasing delays without re-writing. ERS + PGM are separate
    shots, so a full retention curve costs 2 writes total. The MW per delay is
    Id(ERS) - Id(PGM) at the main read point, computed in post-processing/plots.
    """
    ctx = ExperimentContext(
        root=base.ROOT, device_id=args.device_id, geometry=args.geometry,
        live=args.live, seed=args.seed,
    )
    out_dir = make_stage_dir(ctx, E1S_STAGE_LABEL)

    vg_reads = _parse_float_list_csv(args.read_vg) or list(E1S_READ_VG_DEFAULT)
    delays = _parse_float_list_csv(args.delays) or list(E1S_DELAYS_DEFAULT)
    vd_read = float(args.vd_read)
    t_read = float(args.t_read_s)

    rows = []
    seq = 0
    for rep in range(args.reps):
        for state in (["ERS", "PGM"] if args.write_state == "BOTH" else [args.write_state]):
            rr = run_e1s_shot(
                backend,
                state=state,
                delays_s=delays,
                vg_reads=vg_reads,
                vd_read=vd_read,
                n_pts=args.n_pts,
                t_read=t_read,
                v_write=_resolve_write_v(state, args),
                t_write=float(getattr(args, "t_write_s", None) or base.T_WRITE),
            )
            for r in rr:
                rows.append({
                    "timestamp_iso": _dt.datetime.now().isoformat(timespec="seconds"),
                    "stage": "E1S", "device_id": args.device_id, "geometry": args.geometry,
                    "sequence_id": seq, "repeat_index": rep, "state_target": state,
                    "requested_delay_s": r.get("requested_delay_s", ""),
                    "delay_s": r.get("delay_s", ""),
                    "Vg_read_V": r["Vg_read_V"], "Vd_read_V": r["Vd_read_V"],
                    "Id_mean_A": r["Id_mean_A"], "Id_std_A": r["Id_std_A"],
                    "Ig_mean_A": r["Ig_mean_A"], "Ig_std_A": r["Ig_std_A"],
                    "n_d": r["n_d"], "n_g": r["n_g"],
                    "note": f"single_write_retention_{state}_one_write_then_read_vs_delay",
                })
            try:
                _check_samples(rows[-len(rr):], "E1S")
                _check_ig(rows[-len(rr):], "E1S", args.e1s_ig_stop_uA)
            except StopGate:
                # fragile L10: flush already-measured rows before the stop-gate aborts the run.
                if rows:
                    write_rows_csv(out_dir / E1S_CSV_NAME, rows, E1S_FIELDNAMES)
                raise
            print(f"SHOT_OK: E1S rep={rep} state={state} delays={len(delays)} "
                  f"(ONE write) seq={seq}")
            seq += 1

    out_csv = out_dir / E1S_CSV_NAME
    write_rows_csv(out_csv, rows, E1S_FIELDNAMES)

    code = "E1S_SINGLE_WRITE_RETENTION_DONE"
    summary = summarize_rows("E1S", out_csv, rows, code)
    manifest = {
        "stage": "E1S",
        "stage_label": E1S_STAGE_LABEL,
        "device_id": args.device_id,
        "geometry": args.geometry,
        "live": bool(args.live),
        "plan_mode_equivalent": not bool(args.live),
        "seed": args.seed,
        "channels": {
            "gate": base.GATE_CH, "drain": base.DRAIN_CH,
            "allowed": sorted(base.ALLOWED_CHANNELS), "forbidden": sorted(base.FORBIDDEN_CHANNELS),
        },
        "protocol": "single_write_retention: reset->write->(wait(delay)->read)xN, ONE write per shot; "
                    "reads cumulative in real time, realized delay recorded as delay_s",
        "e1s_params": {
            "reps_per_state": args.reps,
            "read_vg": vg_reads,
            "main_vg": E1S_MAIN_VG,
            "vd_read": vd_read,
            "t_read_s": t_read,
            "requested_delays_s": delays,
            "write_v_arg": getattr(args, "write_v", None),
            "v_ers_eff": (_resolve_write_v("ERS", args) if getattr(args, "write_v", None) is not None else base.V_ERS),
            "v_pgm_eff": (_resolve_write_v("PGM", args) if getattr(args, "write_v", None) is not None else base.V_PGM),
            "t_write_s_eff": float(getattr(args, "t_write_s", None) or base.T_WRITE),
        },
        "stop_gate_uA": {"E1S": args.e1s_ig_stop_uA},
        "output_csv": str(out_csv),
        "report_code": code,
        "command_args": list(getattr(args, "_argv", sys.argv[1:])),
    }
    manifest_path = write_manifest_yaml(out_csv.parent, manifest)
    write_report_code(out_csv.parent, summary)
    write_summary_md(out_csv.parent, summary, manifest_path=manifest_path)
    print(f"MANIFEST: {manifest_path}")
    return summary


def _print_plan_e1s(args) -> None:
    vg_reads = _parse_float_list_csv(args.read_vg) or list(E1S_READ_VG_DEFAULT)
    delays = _parse_float_list_csv(args.delays) or list(E1S_DELAYS_DEFAULT)
    _wv = getattr(args, "write_v", None)
    if _wv is None:
        ers, pgm, src = base.V_ERS, base.V_PGM, "default(+/-5 V)"
    else:
        ers, pgm, src = _resolve_write_v("ERS", args), _resolve_write_v("PGM", args), "--write-v"
    tw = float(getattr(args, "t_write_s", None) or base.T_WRITE)
    print("PLAN_BEGIN")
    print(f"live={args.live} stage=E1S device_id={args.device_id} geometry={args.geometry}")
    print(f"channels: Gate={base.GATE_CH}, Drain={base.DRAIN_CH}; "
          f"allowed={sorted(base.ALLOWED_CHANNELS)} forbidden={sorted(base.FORBIDDEN_CHANNELS)}")
    print(f"WRITE_PARAMS: ERS={ers:+g}V PGM={pgm:+g}V t_write={tw:g}s (src={src})")
    print(f"READ_PARAMS: vd_read={float(args.vd_read):g}V read_vg={vg_reads} (main={E1S_MAIN_VG:g}V) t_read={float(args.t_read_s):g}s")
    print("E1S: ONE write per shot, then read the SAME state at increasing delays (no re-write).")
    _states = ["ERS", "PGM"] if args.write_state == "BOTH" else [args.write_state]
    print(f"  requested_delays={delays}  reps/state={args.reps}  write_state={args.write_state} states={_states} -> {len(_states)} write(s)/rep")
    print("  NOTE: reads are cumulative in real time; short delays may merge. Realized delay saved as delay_s.")
    print("  MW(delay) = Id(ERS)-Id(PGM) @ main read point (computed in analysis).")
    print(f"  stop |Ig|>{args.e1s_ig_stop_uA:g} uA")
    print("PLAN_END")


def print_plan(args) -> None:
    vg_reads = _parse_float_list_csv(args.read_vg) or list(E6S_READ_VG_DEFAULT)
    _e6s_wide_recovery = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0]
    post_delays = (_parse_float_list_csv(args.post_delays)
                   or (_e6s_wide_recovery if getattr(args, "wide_recovery", False) else list(E6S_POST_DELAYS_DEFAULT)))
    amp_abs = abs(float(args.disturb_amp))
    _wv = getattr(args, "write_v", None)
    if _wv is None:
        ers, pgm, src = base.V_ERS, base.V_PGM, "default(+/-5 V)"
    else:
        ers, pgm, src = _resolve_write_v("ERS", args), _resolve_write_v("PGM", args), "--write-v"
    tw = float(getattr(args, "t_write_s", None) or base.T_WRITE)
    print("PLAN_BEGIN")
    print(f"live={args.live} stage=E6S device_id={args.device_id} geometry={args.geometry}")
    print(f"channels: Gate={base.GATE_CH}, Drain={base.DRAIN_CH}; "
          f"allowed={sorted(base.ALLOWED_CHANNELS)} forbidden={sorted(base.FORBIDDEN_CHANNELS)}")
    print(f"WRITE_PARAMS: ERS={ers:+g}V PGM={pgm:+g}V t_write={tw:g}s (src={src})")
    print(f"READ_PARAMS: vd_read={float(args.vd_read):g}V read_vg={vg_reads} (main={E6S_MAIN_VG:g}V) t_read={float(args.t_read_s):g}s")
    print("E6S: ONE write per shot, then read[pre] -> disturb -> read[post] x len(delays).")
    print(f"  disturb: amp=-/+{amp_abs:g}V (opposite to written state), width={args.disturb_width_s:g}s, "
          f"neutral_wait={args.neutral_wait_s:g}s")
    _states = ["ERS", "PGM"] if args.write_state == "BOTH" else [args.write_state]
    print(f"  post_delays={post_delays}  reps/state={args.reps}  write_state={args.write_state} states={_states} -> {len(_states)} write(s)/rep")
    print(f"  outputs per shot: dId@{E6S_MAIN_VG:g}V = Id(post)-Id(pre); gm from pre-read 2 pts; dVth=-dId/gm")
    print(f"  stop |Ig|>{args.e6s_ig_stop_uA:g} uA")
    print("PLAN_END")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=["PLAN", "E6S", "E1S", "E6M"], default="PLAN",
                    help="PLAN prints the plan only (no backend); E6S = single-shot disturb; "
                         "E1S = single-write retention (one write, read vs delay); "
                         "E6M = multi-disturb accumulation (one write, disturb train, read at N checkpoints)")
    ap.add_argument("--live", action="store_true",
                    help="Open the real WGFMU session and drive hardware. Default is dry-run.")
    ap.add_argument("--confirm", default="", help="Must equal the stage in live mode, e.g. --confirm E6S / --confirm E1S / --confirm E6M")
    ap.add_argument("--device-id", default="L10W10_XX")
    ap.add_argument("--geometry", default="L10W10")
    # channel routing (delegated to base.configure_channel_map)
    ap.add_argument("--gate-ch", type=int, default=base.DEFAULT_GATE_CH)
    ap.add_argument("--drain-ch", type=int, default=base.DEFAULT_DRAIN_CH)
    ap.add_argument("--allowed-channels", default=",".join(str(x) for x in sorted(base.DEFAULT_ALLOWED_CHANNELS)))
    ap.add_argument("--forbidden-channels", default=",".join(str(x) for x in sorted(base.DEFAULT_FORBIDDEN_CHANNELS)))
    ap.add_argument("--seed", type=int, default=20260603)
    # write params (shared meaning with the base script)
    ap.add_argument("--write-v", type=float, default=None,
                    help="Write magnitude in V; ERS=+|v|/PGM=-|v|. Default None = +/-5 V.")
    ap.add_argument("--t-write-s", type=float, default=None, help="Write pulse width (s), default 100e-6")
    ap.add_argument("--write-state", choices=["ERS", "PGM", "BOTH"], default="BOTH",
                    help="Which state(s) to WRITE. BOTH = ERS then PGM (2 full writes/device, BIPOLAR). "
                         "Use ERS or PGM for ONE write per device — minimizes the bipolar stress that breaks "
                         "fragile L10. Applies to E1S/E6S (E6M still uses --e6m-state).")
    ap.add_argument("--vd-read", type=float, default=base.VD_READ, help="Read drain voltage (V), default 0.05")
    ap.add_argument("--n-pts", type=int, default=base.N_PTS,
                    help="Samples averaged per read window (default 5). Raise (e.g. 32) on fragile points to shrink SEM.")
    ap.add_argument("--read-irange-drain", default=None,
                    help="Drain(Id) measure current range: 1UA/10UA/100UA/1MA (default keeps 1MA). "
                         "Lower = better resolution on uA reads; 100UA safe vs <=30uA stop gate, 10UA best SNR.")
    ap.add_argument("--read-irange-gate", default=None,
                    help="Gate(Ig) measure current range; default keeps 1MA (gate leakage can be large).")
    ap.add_argument("--wide-recovery", action="store_true",
                    help="E6S: wide post-disturb recovery delays 1us..100s (trap re-emission / recovery scan).")
    # E6S-specific
    ap.add_argument("--read-vg", default=None,
                    help="Comma-separated read Vg points; [0]=main MW point, rest give gm. "
                         "Use '=' for negatives, e.g. --read-vg=-1.0,-0.7 (default -1.0,-0.7)")
    ap.add_argument("--t-read-s", type=float, default=base.T_READ, help="Read pulse width (s), default 5e-6")
    ap.add_argument("--disturb-amp", type=float, default=E6S_AMP_DEFAULT,
                    help="Disturb magnitude (V); sign is opposite to the written state (default 2.5)")
    ap.add_argument("--disturb-width-s", type=float, default=E6S_WIDTH_DEFAULT,
                    help="Disturb pulse width (s), default 100e-6")
    ap.add_argument("--post-delays", default=None,
                    help="Comma-separated disturb->post-read delays (s), e.g. 1e-6,1e-4,1e-2 "
                         "(default 1e-6,1e-4,1e-2)")
    ap.add_argument("--neutral-wait-s", type=float, default=E6S_NEUTRAL_WAIT,
                    help="Gap between pre-read and disturb pulse (s), default 10e-6")
    ap.add_argument("--reps", type=int, default=1,
                    help="Repeats per state (ERS,PGM). Default 1 = one write per state. "
                         "Each rep is a fresh single-shot; only raise on robust points.")
    ap.add_argument("--e6s-ig-stop-uA", type=float, default=E6S_IG_STOP_UA_DEFAULT)
    # E1S-specific
    ap.add_argument("--delays", default=None,
                    help="E1S: comma-separated write->read delays (s), increasing, "
                         "e.g. 1e-6,1e-5,1e-4,1e-3,1e-2,1e-1,1.0 (default that list)")
    ap.add_argument("--e1s-ig-stop-uA", type=float, default=E1S_IG_STOP_UA_DEFAULT)
    # E6M-specific (multi-disturb accumulation)
    ap.add_argument("--checkpoints", default=None,
                    help="E6M: comma-separated cumulative disturb counts to read at, "
                         "e.g. 1,3,10,30,100,300,1000 (default that list)")
    ap.add_argument("--interval-s", type=float, default=E6M_INTERVAL_DEFAULT,
                    help="E6M: gap between disturb pulses (s); larger = more recovery "
                         "between pulses (default 1e-6). Scan this to test interval effect.")
    ap.add_argument("--e6m-state", choices=["ERS", "PGM", "BOTH"], default="BOTH",
                    help="E6M: which written state to disturb (default BOTH = ERS then PGM)")
    ap.add_argument("--e6m-ig-stop-uA", type=float, default=E6M_IG_STOP_UA_DEFAULT)
    args = ap.parse_args(argv)
    args._argv = list(argv) if argv is not None else list(sys.argv[1:])
    return args


def main(argv=None) -> int:
    import os
    import time
    args = parse_args(argv)
    if getattr(args, "read_irange_drain", None):
        base.MEAS_IRANGE_DRAIN = args.read_irange_drain.upper()
    if getattr(args, "read_irange_gate", None):
        base.MEAS_IRANGE_GATE = args.read_irange_gate.upper()
    try:
        base.configure_channel_map(args)
    except StopGate as exc:
        print(f"REPORT_CODE: {exc.code}")
        print(f"STOP_GATE: {exc}")
        return 2

    if args.stage == "E1S":
        _print_plan_e1s(args)
    elif args.stage == "E6M":
        _print_plan_e6m(args)
    else:
        print_plan(args)
    if args.stage == "PLAN":
        print("REPORT_CODE: PLAN_ONLY_NO_HARDWARE")
        return 0

    if args.live:
        try:
            validate_live_request(args.stage, args.live, args.confirm)
        except StopGate as exc:
            print(f"REPORT_CODE: {exc.code}")
            print(f"For live mode, rerun with: --stage {args.stage} --live --confirm {args.stage}")
            return 2

    backend = None
    try:
        backend, resource = base.make_backend(args.live)
        args._backend_resource = resource
        if args.stage == "E1S":
            run_stage_e1s(backend, args)
        elif args.stage == "E6M":
            run_stage_e6m(backend, args)
        else:
            run_stage_e6s(backend, args)
        if not args.live and isinstance(backend, base.AuditBackend):
            print(f"DRY_RUN_AUDIT: execute_count={backend.execute_count} "
                  f"max_vectors_seen={backend.max_vectors_seen}")
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
