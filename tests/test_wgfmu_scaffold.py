import json
from pathlib import Path

from fefetlab.measurements.wgfmu import (
    DummyWgfmuBackend,
    MeasureEventParams,
    PulsePatternParams,
    WgfmuDataExporter,
    WgfmuSmokeConfig,
    WgfmuSmokeRunner,
    list_wgfmu_scaffold_features,
)


def test_wgfmu_scaffold_exports_are_importable():
    features = list_wgfmu_scaffold_features()

    assert "config" in features
    assert "backend" in features
    assert "workflow" in features
    assert "export" in features
    assert "offline_pattern_setup" in features["workflow"]
    assert "dummy_backend_for_local_development" in features["backend"]


def test_dummy_wgfmu_smoke_runner_creates_outputs_and_renames_current_column(tmp_path):
    pulse_cfg = PulsePatternParams(
        chan_id=101,
        pattern_name="smoke_pulse",
        v_init=0.0,
        v_pulse=-1.0,
        t_rise_s=1e-6,
        t_high_s=2e-6,
        t_fall_s=1e-6,
        t_base_s=2e-6,
        repeat_count=2,
    )
    meas_cfg = MeasureEventParams(
        event_name="smoke_event",
        start_time_s=0.0,
        points=8,
        interval_s=2e-7,
        average_s=2e-7,
    )
    run_cfg = WgfmuSmokeConfig(label="wgfmu_smoke")

    exporter = WgfmuDataExporter(base_dir=tmp_path)
    runner = WgfmuSmokeRunner(DummyWgfmuBackend(), exporter=exporter)

    result = runner.run(
        resource="DUMMY::INSTR",
        pulse_cfg=pulse_cfg,
        meas_cfg=meas_cfg,
        run_cfg=run_cfg,
    )

    assert "current_A" in result.df.columns
    assert "value" not in result.df.columns
    assert result.qc_df.iloc[0]["status"] == "ok"
    assert result.complete == result.total
    assert result.paths["parsed"].exists()
    assert result.paths["qc"].exists()
    assert result.paths["meta"].exists()
    assert result.paths["export_ascii"].exists()

    meta = json.loads(result.paths["meta"].read_text(encoding="utf-8"))
    assert meta["pulse_cfg"]["pattern_name"] == "smoke_pulse"
    assert meta["run_cfg"]["operation_mode"] == "FASTIV"
    assert meta["issues"] == []


def test_dummy_wgfmu_smoke_runner_supports_voltage_mode(tmp_path):
    pulse_cfg = PulsePatternParams(
        chan_id=101,
        pattern_name="voltage_smoke",
        v_init=0.0,
        v_pulse=1.0,
        t_rise_s=1e-6,
        t_high_s=2e-6,
        t_fall_s=1e-6,
        t_base_s=2e-6,
    )
    meas_cfg = MeasureEventParams(
        event_name="voltage_event",
        start_time_s=0.0,
        points=6,
        interval_s=1e-6,
        average_s=1e-6,
    )
    run_cfg = WgfmuSmokeConfig(label="wgfmu_voltage", measure_mode="VOLTAGE")

    runner = WgfmuSmokeRunner(
        DummyWgfmuBackend(),
        exporter=WgfmuDataExporter(base_dir=tmp_path),
    )
    result = runner.run(
        resource="DUMMY::INSTR",
        pulse_cfg=pulse_cfg,
        meas_cfg=meas_cfg,
        run_cfg=run_cfg,
    )

    assert "voltage_V" in result.df.columns
    assert "current_A" not in result.df.columns
