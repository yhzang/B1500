"""Wake-up runner: repeated PGM/ERS pulses with periodic IV readout.

Background (project-4 总台 R1-B / H1 hypothesis):
  Real PFeFET devices need a wake-up phase before stable memory window appears,
  but with too strong a wake-up the trap mechanism dominates over ferroelectric
  switching, producing negative MW. We need to scan wake-up strength
  (e.g. ±3V/30us → ±5V/30us → ±5V/100us) and watch how the IV curve evolves
  pulse-by-pulse.

This runner alternates PGM/ERS pulses with thin IV-readout subsweeps and
returns:
  * wake-up cycle log (cycle index, polarity, v_amp, t_pulse)
  * per-cycle Vth proxy (currently: low-V readout current at v_read)
  * full samples_df for downstream analysis

It deliberately reuses :class:`WgfmuIVSweepRunner`'s building blocks via the
shared :class:`PulseTrainBuilder` so we do not duplicate the
pattern-vector machinery.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import time
from typing import Optional

import numpy as np
import pandas as pd

from .backend import WgfmuBackend
from .export import WgfmuDataExporter
from .pulse_builder import PulseSegment, PulseTrainBuilder, PulseTrainPlan


@dataclass
class WakeupStage:
    """One wake-up stage = N pgm/ers cycles at fixed amplitude/width."""

    n_cycles: int
    v_pgm: float
    v_ers: float
    t_pgm_s: float = 30e-6
    t_ers_s: float = 30e-6
    rise_fall_s: float = 1e-6
    inter_pulse_s: float = 2e-6
    label: Optional[str] = None


@dataclass
class WakeupReadout:
    """A short, low-disturbance readout used between wake-up cycles."""

    v_read: float = -0.5
    t_read_s: float = 5e-6
    rise_fall_s: float = 1e-6
    measure_points: int = 10
    measure_average_s: float = 200e-9


@dataclass
class WgfmuWakeupConfig:
    label: str
    chan_id: int = 101
    v_init: float = 0.0
    v_base: float = 0.0
    operation_mode: str = "FASTIV"
    force_voltage_range: str = "AUTO"
    measure_mode: str = "CURRENT"
    measure_current_range: str = "1MA"
    measure_voltage_range: str = "10V"
    measure_enabled: bool = True
    treat_warning_as_error: bool = False
    timeout_s: float = 120.0
    notes: str = ""
    extra_meta: dict = field(default_factory=dict)


@dataclass
class WgfmuWakeupResult:
    samples_df: pd.DataFrame
    cycles_df: pd.DataFrame  # one row per wake-up cycle
    qc_df: pd.DataFrame
    meta: dict
    paths: dict
    plan: PulseTrainPlan
    channel_ids: list[int]
    complete: int
    total: int
    issues: list[str]


def _build_wakeup_segments(
    stages: list[WakeupStage], readout: WakeupReadout
) -> tuple[list[PulseSegment], list[dict]]:
    """Compose stages × cycles into segments, returning cycle metadata too."""
    segments: list[PulseSegment] = []
    cycle_meta: list[dict] = []
    cycle_idx = 0
    for stage_idx, stage in enumerate(stages):
        stage_label = stage.label or f"stage{stage_idx}_pgm{stage.v_pgm:+.1f}V"
        for k in range(stage.n_cycles):
            # PGM pulse (no measurement during PGM — usually too noisy)
            segments.append(
                PulseSegment(
                    v_pulse=stage.v_pgm,
                    t_rise_s=stage.rise_fall_s,
                    t_high_s=stage.t_pgm_s,
                    t_fall_s=stage.rise_fall_s,
                    t_base_s=stage.inter_pulse_s,
                    label=f"{stage_label}_cyc{k:03d}_pgm",
                    measure_during_high=False,
                    measure_points=0,
                )
            )
            # ERS pulse (no measurement)
            segments.append(
                PulseSegment(
                    v_pulse=stage.v_ers,
                    t_rise_s=stage.rise_fall_s,
                    t_high_s=stage.t_ers_s,
                    t_fall_s=stage.rise_fall_s,
                    t_base_s=stage.inter_pulse_s,
                    label=f"{stage_label}_cyc{k:03d}_ers",
                    measure_during_high=False,
                    measure_points=0,
                )
            )
            # Readout pulse (measure during high)
            segments.append(
                PulseSegment(
                    v_pulse=readout.v_read,
                    t_rise_s=readout.rise_fall_s,
                    t_high_s=readout.t_read_s,
                    t_fall_s=readout.rise_fall_s,
                    t_base_s=readout.rise_fall_s,
                    label=f"{stage_label}_cyc{k:03d}_read",
                    measure_during_high=True,
                    measure_points=readout.measure_points,
                    measure_average_s=readout.measure_average_s,
                )
            )
            cycle_meta.append(
                {
                    "cycle_idx": cycle_idx,
                    "stage_idx": stage_idx,
                    "stage_label": stage_label,
                    "v_pgm": stage.v_pgm,
                    "v_ers": stage.v_ers,
                    "t_pgm_s": stage.t_pgm_s,
                    "t_ers_s": stage.t_ers_s,
                    "v_read": readout.v_read,
                    "t_read_s": readout.t_read_s,
                }
            )
            cycle_idx += 1
    return segments, cycle_meta


class WgfmuWakeupRunner:
    """Run a multi-stage wake-up sequence with per-cycle readout."""

    def __init__(
        self,
        backend: WgfmuBackend,
        exporter: Optional[WgfmuDataExporter] = None,
    ):
        self.backend = backend
        self.exporter = exporter or WgfmuDataExporter()

    def run(
        self,
        *,
        resource: str,
        stages: list[WakeupStage],
        readout: WakeupReadout,
        cfg: WgfmuWakeupConfig,
        pattern_name: Optional[str] = None,
    ) -> WgfmuWakeupResult:
        segments, cycle_meta = _build_wakeup_segments(stages, readout)

        pattern_name = pattern_name or f"{cfg.label}_pattern"
        builder = PulseTrainBuilder(
            pattern_name=pattern_name, v_init=cfg.v_init, v_base=cfg.v_base
        )
        plan = builder.build(segments)

        run_dir = self.exporter.create_run_dir(cfg.label)
        paths = self.exporter.build_paths(run_dir)
        paths["cycles"] = run_dir / "cycles.csv"
        paths["samples"] = run_dir / "samples.csv"
        paths["plan_json"] = run_dir / "plan.json"

        self.backend.open_session(resource)
        self.backend.set_timeout(cfg.timeout_s)
        channel_ids = self.backend.get_channel_ids()
        if cfg.chan_id not in channel_ids:
            try:
                self.backend.close_session()
            finally:
                raise RuntimeError(
                    f"cfg.chan_id={cfg.chan_id} not in detected channels {channel_ids}"
                )

        try:
            self.backend.clear()

            self.backend.create_pattern(plan.pattern_name, plan.v_init)
            for d_t, v in plan.vectors:
                self.backend.add_vector(plan.pattern_name, d_t, v)
            for event_name, t_start, points, interval, average, mode in plan.measure_events:
                self.backend.set_measure_event(
                    pattern=plan.pattern_name,
                    event=event_name,
                    time_s=t_start,
                    points=points,
                    interval_s=interval,
                    average_s=average,
                    raw_data_mode=mode,
                )
            self.backend.add_sequence(
                chan_id=cfg.chan_id, pattern=plan.pattern_name, count=1
            )
            self.backend.export_ascii(str(paths["export_ascii"]))

            self.backend.initialize()
            if cfg.treat_warning_as_error:
                self.backend.treat_warnings_as_errors("SEVERE")
            self.backend.set_operation_mode(cfg.chan_id, cfg.operation_mode)
            self.backend.set_force_voltage_range(cfg.chan_id, cfg.force_voltage_range)
            self.backend.set_measure_enabled(cfg.chan_id, cfg.measure_enabled)
            self.backend.set_measure_mode(cfg.chan_id, cfg.measure_mode)
            if cfg.measure_mode.upper() == "CURRENT":
                self.backend.set_measure_current_range(cfg.chan_id, cfg.measure_current_range)
            else:
                self.backend.set_measure_voltage_range(cfg.chan_id, cfg.measure_voltage_range)
            self.backend.connect(cfg.chan_id)

            t0 = time.time()
            self.backend.execute()
            self.backend.wait_until_completed()
            elapsed_s = time.time() - t0

            complete, total = self.backend.get_measure_value_size(cfg.chan_id)
            samples = self.backend.get_measure_values(cfg.chan_id).copy()
            value_col = "current_A" if cfg.measure_mode.upper() == "CURRENT" else "voltage_V"
            if "value" in samples.columns:
                samples = samples.rename(columns={"value": value_col})

            # Find each readout segment and aggregate
            read_segments = [s for s in plan.segments if s["measure_points"] > 0]
            assert len(read_segments) == len(cycle_meta), (
                f"plan/segment mismatch: {len(read_segments)} read segs vs "
                f"{len(cycle_meta)} cycle entries"
            )
            cycle_rows = []
            for seg, cyc in zip(read_segments, cycle_meta):
                t_start, t_end = seg["t_high_start_s"], seg["t_high_end_s"]
                mask = (samples["time_s"] >= t_start) & (samples["time_s"] <= t_end)
                sub = samples.loc[mask]
                i_read = float(sub[value_col].mean()) if len(sub) else float("nan")
                i_std = float(sub[value_col].std(ddof=0)) if len(sub) else float("nan")
                cycle_rows.append(
                    {
                        **cyc,
                        "i_read_mean": i_read,
                        "i_read_std": i_std,
                        "n_samples": int(len(sub)),
                        "t_read_start_s": t_start,
                        "t_read_end_s": t_end,
                    }
                )
            cycles_df = pd.DataFrame(cycle_rows)

            issues: list[str] = []
            if len(samples) == 0:
                issues.append("empty_samples")
            if complete != total:
                issues.append(f"incomplete_measurement:{complete}/{total}")
            if cycles_df["n_samples"].eq(0).any():
                issues.append("empty_readout_window")
            qc_df = pd.DataFrame([{
                "label": cfg.label,
                "status": "ok" if not issues else "suspect",
                "issues": ";".join(issues),
                "n_cycles": len(cycles_df),
                "n_samples": len(samples),
                "complete": complete,
                "total": total,
            }])

            meta = {
                "cfg": asdict(cfg),
                "stages": [asdict(s) for s in stages],
                "readout": asdict(readout),
                "plan_summary": {
                    "pattern_name": plan.pattern_name,
                    "n_segments": len(plan.segments),
                    "total_duration_s": plan.total_duration_s,
                    "n_vectors": len(plan.vectors),
                    "n_measure_events": len(plan.measure_events),
                },
                "detected_channel_ids": channel_ids,
                "complete": complete,
                "total": total,
                "issues": issues,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "execution_time_s": elapsed_s,
                "error_summary": self.backend.get_error_summary(),
                "warning_summary": self.backend.get_warning_summary(),
            }

            self.exporter.save_result(df=samples, qc_df=qc_df, meta=meta, paths=paths)
            cycles_df.to_csv(paths["cycles"], index=False, encoding="utf-8")
            samples.to_csv(paths["samples"], index=False, encoding="utf-8")
            paths["plan_json"].write_text(
                json.dumps(
                    {
                        "pattern_name": plan.pattern_name,
                        "v_init": plan.v_init,
                        "v_base": plan.v_base,
                        "n_vectors": len(plan.vectors),
                        "n_measure_events": len(plan.measure_events),
                        "segments": plan.segments,
                        "cycles": cycle_meta,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            return WgfmuWakeupResult(
                samples_df=samples,
                cycles_df=cycles_df,
                qc_df=qc_df,
                meta=meta,
                paths=paths,
                plan=plan,
                channel_ids=channel_ids,
                complete=complete,
                total=total,
                issues=issues,
            )
        finally:
            try:
                self.backend.disconnect(cfg.chan_id)
            except Exception:
                pass
            self.backend.close_session()


__all__ = [
    "WakeupStage",
    "WakeupReadout",
    "WgfmuWakeupConfig",
    "WgfmuWakeupResult",
    "WgfmuWakeupRunner",
]
