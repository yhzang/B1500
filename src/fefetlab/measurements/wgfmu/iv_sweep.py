"""IV sweep runner: replay a pulse train and parse per-pulse measurements.

This is the core deliverable for project-4 R1-A ("switch DC sweep to WGFMU
pulse sweep, compare DC vs pulsed readout").

Workflow:
  1. Build :class:`PulseTrainPlan` from :class:`PulseSegment` segments.
  2. Push pattern + measure events to backend.
  3. Execute, wait, fetch.
  4. Slice the per-pulse measurement window and produce a per-pulse
     ``(v_pulse, i_mean, i_std, n_samples)`` summary suitable for an IV curve.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .backend import WgfmuBackend
from .config import WgfmuSmokeConfig
from .export import WgfmuDataExporter
from .pulse_builder import PulseSegment, PulseTrainBuilder, PulseTrainPlan


@dataclass
class WgfmuIVSweepResult:
    """Result of a pulse-train IV sweep.

    ``samples_df`` contains the raw measure points (time_s, value).
    ``iv_df`` is the per-pulse summary: one row per :class:`PulseSegment`
    with columns ``label, v_pulse, i_mean_A, i_std_A, n_samples, t_start_s,
    t_end_s``.
    """

    samples_df: pd.DataFrame
    iv_df: pd.DataFrame
    qc_df: pd.DataFrame
    meta: dict
    paths: dict
    plan: PulseTrainPlan
    channel_ids: list[int]
    complete: int
    total: int
    issues: list[str]


@dataclass
class WgfmuIVSweepConfig:
    """Config for :class:`WgfmuIVSweepRunner`.

    Inherits everything :class:`WgfmuSmokeConfig` carries, plus sweep-level
    options. Keeping it flat keeps notebooks readable.
    """

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
    timeout_s: float = 60.0
    sequence_count: int = 1
    notes: str = ""
    extra_meta: dict = field(default_factory=dict)


class WgfmuIVSweepRunner:
    """Compose pulse train → push to backend → execute → return parsed IV."""

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
        segments: list[PulseSegment],
        cfg: WgfmuIVSweepConfig,
        pattern_name: Optional[str] = None,
    ) -> WgfmuIVSweepResult:
        pattern_name = pattern_name or f"{cfg.label}_pattern"
        builder = PulseTrainBuilder(
            pattern_name=pattern_name, v_init=cfg.v_init, v_base=cfg.v_base
        )
        plan = builder.build(segments)

        run_dir = self.exporter.create_run_dir(cfg.label)
        paths = self.exporter.build_paths(run_dir)
        # Add IV-specific extra paths
        paths["iv_curve"] = run_dir / "iv_curve.csv"
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

            # Offline: pattern + vectors + measure events + sequence
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
                chan_id=cfg.chan_id, pattern=plan.pattern_name, count=cfg.sequence_count
            )
            self.backend.export_ascii(str(paths["export_ascii"]))

            # Online setup
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

            # Execute
            t0 = time.time()
            self.backend.execute()
            self.backend.wait_until_completed()
            elapsed_s = time.time() - t0

            complete, total = self.backend.get_measure_value_size(cfg.chan_id)
            samples = self.backend.get_measure_values(cfg.chan_id).copy()
            value_col = "current_A" if cfg.measure_mode.upper() == "CURRENT" else "voltage_V"
            if "value" in samples.columns:
                samples = samples.rename(columns={"value": value_col})

            # Per-pulse summary
            iv_rows: list[dict] = []
            for seg_meta in plan.segments:
                t_start = seg_meta["t_high_start_s"]
                t_end = seg_meta["t_high_end_s"]
                mask = (samples["time_s"] >= t_start) & (samples["time_s"] <= t_end)
                sub = samples.loc[mask]
                if len(sub) == 0:
                    i_mean = float("nan")
                    i_std = float("nan")
                    n_samples = 0
                else:
                    i_mean = float(sub[value_col].mean())
                    i_std = float(sub[value_col].std(ddof=0))
                    n_samples = int(len(sub))
                iv_rows.append(
                    {
                        "label": seg_meta["label"],
                        "v_pulse": seg_meta["v_pulse"],
                        "value_mean": i_mean,
                        "value_std": i_std,
                        "n_samples": n_samples,
                        "t_high_start_s": t_start,
                        "t_high_end_s": t_end,
                    }
                )
            iv_df = pd.DataFrame(iv_rows)
            iv_df.attrs["value_column"] = value_col

            # QC
            issues: list[str] = []
            if len(samples) == 0:
                issues.append("empty_samples")
            if complete != total:
                issues.append(f"incomplete_measurement:{complete}/{total}")
            if iv_df["n_samples"].eq(0).any():
                issues.append("empty_pulse_window")
            qc_df = pd.DataFrame([{
                "label": cfg.label,
                "status": "ok" if not issues else "suspect",
                "issues": ";".join(issues),
                "n_pulses": len(iv_df),
                "n_samples": len(samples),
                "complete": complete,
                "total": total,
            }])

            meta = {
                "cfg": asdict(cfg),
                "plan_summary": {
                    "pattern_name": plan.pattern_name,
                    "v_init": plan.v_init,
                    "v_base": plan.v_base,
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

            # Persist
            self.exporter.save_result(df=samples, qc_df=qc_df, meta=meta, paths=paths)
            iv_df.to_csv(paths["iv_curve"], index=False, encoding="utf-8")
            samples.to_csv(paths["samples"], index=False, encoding="utf-8")
            import json
            paths["plan_json"].write_text(
                json.dumps(
                    {
                        "pattern_name": plan.pattern_name,
                        "v_init": plan.v_init,
                        "v_base": plan.v_base,
                        "vectors": plan.vectors,
                        "measure_events": plan.measure_events,
                        "segments": plan.segments,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            return WgfmuIVSweepResult(
                samples_df=samples,
                iv_df=iv_df,
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


__all__ = ["WgfmuIVSweepRunner", "WgfmuIVSweepConfig", "WgfmuIVSweepResult"]
