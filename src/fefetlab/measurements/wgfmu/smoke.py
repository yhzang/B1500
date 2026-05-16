"""Smoke workflow for WGFMU scaffold development."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import time

import pandas as pd

from .backend import WgfmuBackend
from .config import MeasureEventParams, PulsePatternParams, WgfmuSmokeConfig
from .export import WgfmuDataExporter


@dataclass
class WgfmuSmokeResult:
    df: pd.DataFrame
    qc_df: pd.DataFrame
    meta: dict
    paths: dict
    channel_ids: list[int]
    complete: int
    total: int
    issues: list[str]


class WgfmuSmokeRunner:
    """Minimal Python smoke runner for the WGFMU module scaffold."""

    def __init__(self, backend: WgfmuBackend, exporter: WgfmuDataExporter | None = None):
        self.backend = backend
        self.exporter = exporter or WgfmuDataExporter()

    def run(
        self,
        *,
        resource: str,
        pulse_cfg: PulsePatternParams,
        meas_cfg: MeasureEventParams,
        run_cfg: WgfmuSmokeConfig,
    ) -> WgfmuSmokeResult:
        run_dir = self.exporter.create_run_dir(run_cfg.label)
        paths = self.exporter.build_paths(run_dir)

        self.backend.open_session(resource)
        self.backend.set_timeout(run_cfg.timeout_s)
        channel_ids = self.backend.get_channel_ids()

        if pulse_cfg.chan_id not in channel_ids:
            try:
                self.backend.close_session()
            finally:
                raise RuntimeError(
                    f"pulse_cfg.chan_id={pulse_cfg.chan_id} not found in detected channels {channel_ids}"
                )

        try:
            self.backend.clear()

            self.backend.create_pattern(pulse_cfg.pattern_name, pulse_cfg.v_init)
            self.backend.add_vector(pulse_cfg.pattern_name, pulse_cfg.t_rise_s, pulse_cfg.v_pulse)
            self.backend.add_vector(pulse_cfg.pattern_name, pulse_cfg.t_high_s, pulse_cfg.v_pulse)
            self.backend.add_vector(pulse_cfg.pattern_name, pulse_cfg.t_fall_s, pulse_cfg.v_init)
            self.backend.add_vector(pulse_cfg.pattern_name, pulse_cfg.t_base_s, pulse_cfg.v_init)

            self.backend.set_measure_event(
                pattern=pulse_cfg.pattern_name,
                event=meas_cfg.event_name,
                time_s=meas_cfg.start_time_s,
                points=meas_cfg.points,
                interval_s=meas_cfg.interval_s,
                average_s=meas_cfg.average_s,
                raw_data_mode=meas_cfg.raw_data_mode,
            )
            self.backend.add_sequence(
                chan_id=pulse_cfg.chan_id,
                pattern=pulse_cfg.pattern_name,
                count=pulse_cfg.repeat_count,
            )
            self.backend.export_ascii(str(paths["export_ascii"]))

            self.backend.initialize()
            if run_cfg.treat_warning_as_error:
                self.backend.treat_warnings_as_errors("SEVERE")

            self.backend.set_operation_mode(pulse_cfg.chan_id, run_cfg.operation_mode)
            self.backend.set_force_voltage_range(pulse_cfg.chan_id, run_cfg.force_voltage_range)
            self.backend.set_measure_enabled(pulse_cfg.chan_id, run_cfg.measure_enabled)
            self.backend.set_measure_mode(pulse_cfg.chan_id, run_cfg.measure_mode)
            if run_cfg.measure_mode.upper() == "CURRENT":
                self.backend.set_measure_current_range(pulse_cfg.chan_id, run_cfg.measure_current_range)
            else:
                self.backend.set_measure_voltage_range(pulse_cfg.chan_id, run_cfg.measure_voltage_range)

            self.backend.connect(pulse_cfg.chan_id)

            t0 = time.time()
            self.backend.execute()
            self.backend.wait_until_completed()
            elapsed_s = time.time() - t0

            complete, total = self.backend.get_measure_value_size(pulse_cfg.chan_id)
            df = self.backend.get_measure_values(pulse_cfg.chan_id).copy()
            if "value" in df.columns:
                if run_cfg.measure_mode.upper() == "CURRENT":
                    df = df.rename(columns={"value": "current_A"})
                else:
                    df = df.rename(columns={"value": "voltage_V"})

            issues: list[str] = []
            if len(df) == 0:
                issues.append("empty_dataframe")
            if complete != total:
                issues.append(f"incomplete_measurement:{complete}/{total}")
            if run_cfg.measure_mode.upper() == "CURRENT" and "current_A" not in df.columns:
                issues.append("missing_current_A")
            if run_cfg.measure_mode.upper() == "VOLTAGE" and "voltage_V" not in df.columns:
                issues.append("missing_voltage_V")

            qc_df = pd.DataFrame([
                {
                    "label": run_cfg.label,
                    "status": "ok" if not issues else "suspect",
                    "issues": ";".join(issues),
                    "n_rows": len(df),
                    "complete": complete,
                    "total": total,
                }
            ])

            meta = {
                "pulse_cfg": asdict(pulse_cfg),
                "meas_cfg": asdict(meas_cfg),
                "run_cfg": asdict(run_cfg),
                "detected_channel_ids": channel_ids,
                "complete": complete,
                "total": total,
                "issues": issues,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "execution_time_s": elapsed_s,
                "error_summary": self.backend.get_error_summary(),
                "warning_summary": self.backend.get_warning_summary(),
            }
            self.exporter.save_result(df=df, qc_df=qc_df, meta=meta, paths=paths)

            return WgfmuSmokeResult(
                df=df,
                qc_df=qc_df,
                meta=meta,
                paths=paths,
                channel_ids=channel_ids,
                complete=complete,
                total=total,
                issues=issues,
            )
        finally:
            try:
                self.backend.disconnect(pulse_cfg.chan_id)
            except Exception:
                pass
            self.backend.close_session()
