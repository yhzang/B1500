"""Tests for the WGFMU IV-sweep / wake-up / pulse-builder / real-backend additions.

All tests run on Linux without a real instrument by using ``DummyWgfmuBackend``.
The Keysight DLL must NEVER be loaded as a side-effect of *import*.
"""

from __future__ import annotations

import ctypes
import math
import sys
import types

import pytest

from fefetlab.measurements.wgfmu import (
    DummyWgfmuBackend,
    PulseSegment,
    PulseTrainBuilder,
    RealWgfmuBackend,
    WakeupReadout,
    WakeupStage,
    WgfmuDataExporter,
    WgfmuIVSweepConfig,
    WgfmuIVSweepRunner,
    WgfmuWakeupConfig,
    WgfmuWakeupRunner,
    linear_voltage_segments,
    list_wgfmu_scaffold_features,
)
from fefetlab.measurements.wgfmu.experiments import (
    E1Config,
    PFeFETParams,
    run_e1_single_point,
)
from fefetlab.measurements.wgfmu.setup_helpers import clear_b1500_status_for_wgfmu_open


# ---------------------------------------------------------------- pulse builder
def test_pulse_train_builder_produces_consistent_timeline():
    segments = linear_voltage_segments(
        v_start=-0.5, v_stop=-2.0, n_points=4,
        t_rise_s=1e-6, t_high_s=2e-6, t_fall_s=1e-6, t_base_s=1e-6,
        measure_points=5,
    )
    builder = PulseTrainBuilder(pattern_name="p", v_init=0.0, v_base=0.0)
    plan = builder.build(segments)

    # 4 segments × 4 vectors per pulse = 16 vectors total
    assert len(plan.vectors) == 4 * 4
    # Each pulse contributes one measure event
    assert len(plan.measure_events) == 4
    # Each segment metadata must be sorted by t_start_s
    starts = [s["t_start_s"] for s in plan.segments]
    assert starts == sorted(starts)
    # Total duration equals the sum of all vector dtimes
    total = sum(dt for dt, _v in plan.vectors)
    assert math.isclose(plan.total_duration_s, total, rel_tol=1e-12)


def test_pulse_train_waveform_samples_reaches_target_voltages():
    segments = [PulseSegment(v_pulse=-1.5, t_rise_s=1e-6, t_high_s=2e-6,
                             t_fall_s=1e-6, t_base_s=1e-6,
                             measure_points=3, measure_average_s=200e-9)]
    plan = PulseTrainBuilder(pattern_name="p", v_init=0.0, v_base=0.0).build(segments)
    t, v = plan.waveform_samples(dt_s=1e-7)
    assert v.min() <= -1.4
    assert v.max() >= -0.001
    # last sample returns to v_base
    assert abs(v[-1]) < 1e-9


# ---------------------------------------------------------------- IV sweep runner
def test_iv_sweep_runner_with_dummy_completes_full_workflow(tmp_path):
    """End-to-end: builder → backend offline setup → execute → result parsing.

    Uses the deterministic DummyWgfmuBackend which returns linear synthetic
    samples; we verify the workflow contract (paths exist, columns named, qc OK)
    rather than physics realism.
    """
    segments = linear_voltage_segments(
        v_start=0.0, v_stop=-2.0, n_points=8,
        t_rise_s=1e-6, t_high_s=3e-6, t_fall_s=1e-6, t_base_s=1e-6,
        measure_points=6, measure_average_s=200e-9,
    )
    cfg = WgfmuIVSweepConfig(
        label="unit_test_iv_sweep",
        chan_id=101, v_init=0.0, v_base=0.0,
    )
    runner = WgfmuIVSweepRunner(
        DummyWgfmuBackend(),
        exporter=WgfmuDataExporter(base_dir=tmp_path),
    )
    result = runner.run(resource="DUMMY::INSTR", segments=segments, cfg=cfg)

    # Outputs present
    assert result.paths["iv_curve"].exists()
    assert result.paths["samples"].exists()
    assert result.paths["plan_json"].exists()
    assert result.paths["meta"].exists()

    # IV table shape: one row per segment
    assert len(result.iv_df) == 8
    assert {"label", "v_pulse", "value_mean", "value_std", "n_samples"} <= set(
        result.iv_df.columns
    )

    # value_column attr propagated (current vs voltage measure mode)
    assert result.iv_df.attrs["value_column"] == "current_A"

    # Samples DataFrame has the renamed value column
    assert "current_A" in result.samples_df.columns
    assert "value" not in result.samples_df.columns


def test_iv_sweep_runner_rejects_unknown_channel(tmp_path):
    cfg = WgfmuIVSweepConfig(label="bad_ch", chan_id=999)
    runner = WgfmuIVSweepRunner(
        DummyWgfmuBackend(),
        exporter=WgfmuDataExporter(base_dir=tmp_path),
    )
    segments = linear_voltage_segments(
        v_start=0, v_stop=-1, n_points=2, measure_points=2,
    )
    with pytest.raises(RuntimeError, match="not in detected channels"):
        runner.run(resource="DUMMY::INSTR", segments=segments, cfg=cfg)


def test_e1_single_point_uses_backend_dataframe_result_contract():
    """Regression: E1 helper must treat WGFMU result size as a tuple and data as a DataFrame."""
    backend = DummyWgfmuBackend()
    backend.open_session("DUMMY::INSTR")
    backend._channels = [201, 202]
    cfg = E1Config(
        params=PFeFETParams(
            chan_gate=202,
            chan_drain=201,
            allowed_channels=(201, 202),
            measure_points_per_read=4,
        ),
        delays_s=[1e-6],
    )

    result = run_e1_single_point(backend, cfg, state="ERS", delay_s=1e-6, vg_read=0.0)

    assert {"id_mean", "id_std", "ig_mean", "ig_std"} <= set(result)
    assert result["id_mean"] > 0
    assert result["ig_mean"] > 0


# ---------------------------------------------------------------- wakeup runner
def test_wakeup_runner_with_dummy_produces_per_cycle_readout(tmp_path):
    """End-to-end wake-up workflow contract: stages × cycles → cycles_df rows.

    Note: ``DummyWgfmuBackend`` returns a fixed 20-sample frame starting at t=0,
    so the per-cycle readout windows (which sit much later in the pulse train)
    will be empty. We assert the *workflow shape* — row count, columns,
    stage_idx coverage, export paths — not the readout numerical content.
    Real backend on the test-bench machine will return the full timeline.
    """
    stages = [
        WakeupStage(n_cycles=4, v_pgm=-3.0, v_ers=3.0, label="s0"),
        WakeupStage(n_cycles=4, v_pgm=-5.0, v_ers=5.0, label="s1"),
    ]
    readout = WakeupReadout(v_read=-0.8, measure_points=5)
    cfg = WgfmuWakeupConfig(label="unit_test_wakeup", chan_id=101)

    runner = WgfmuWakeupRunner(
        DummyWgfmuBackend(),
        exporter=WgfmuDataExporter(base_dir=tmp_path),
    )
    result = runner.run(
        resource="DUMMY::INSTR", stages=stages, readout=readout, cfg=cfg
    )

    # Workflow contract — exports present
    assert result.paths["cycles"].exists()
    assert result.paths["samples"].exists()
    assert result.paths["plan_json"].exists()

    # Row count == sum(stage.n_cycles)
    assert len(result.cycles_df) == 4 + 4
    # Both stages represented
    assert set(result.cycles_df["stage_idx"]) == {0, 1}
    # Required columns present
    required_cols = {
        "cycle_idx", "stage_idx", "stage_label",
        "v_pgm", "v_ers", "v_read",
        "i_read_mean", "i_read_std", "n_samples",
    }
    assert required_cols <= set(result.cycles_df.columns)


# ---------------------------------------------------------------- real backend
def test_real_backend_can_be_constructed_without_dll_on_any_os():
    """RealWgfmuBackend instantiation must never touch the filesystem.

    This is the contract that keeps `import fefetlab` safe on Linux/macOS.
    """
    backend = RealWgfmuBackend()
    assert backend._dll is None
    # Touching properties before load() should still be fine
    assert hasattr(backend, "session_opened")


def test_real_backend_load_fails_gracefully_when_dll_missing(monkeypatch):
    """Calling .load() with no usable DLL must raise a clear OSError, not segfault.

    The B1500 test machine has a real system-level wgfmu.dll installed, so this
    test must not rely on a physically missing DLL. Mock the loader instead.
    """
    monkeypatch.delenv("WGFMU_DLL_PATH", raising=False)

    def _missing_dll(_path):
        raise OSError("mock missing wgfmu.dll")

    monkeypatch.setattr(ctypes, "WinDLL", _missing_dll, raising=False)
    backend = RealWgfmuBackend(dll_path="/nonexistent/wgfmu.dll")
    with pytest.raises(OSError, match="Could not load wgfmu\\.dll"):
        backend.load()


def test_wgfmu_open_preflight_drains_errx_without_cls(monkeypatch):
    """Regression: yhzang B1500A enqueues +100 on *CLS, so preflight must not send it."""

    class FakeInst:
        def __init__(self):
            self.writes = []
            self.reads = iter([
                '100,"Undefined GPIB command."',
                '0,"No Error."',
                '0,"No Error."',
            ])
            self.closed = False

        def clear(self):
            return None

        def write(self, cmd):
            self.writes.append(cmd)
            if cmd == "*CLS":
                raise AssertionError("preflight must not send *CLS")

        def read(self):
            return next(self.reads)

        def query(self, cmd):
            assert cmd == "*IDN?"
            return "Agilent Technologies,B1500A,MY55231213,A.06.02.2023.0401"

        def close(self):
            self.closed = True

    class FakeRM:
        def __init__(self):
            self.inst = FakeInst()
            self.closed = False

        def open_resource(self, addr):
            assert addr == "GPIB1::17::INSTR"
            return self.inst

        def close(self):
            self.closed = True

    fake_rm = FakeRM()
    monkeypatch.setitem(sys.modules, "pyvisa", types.SimpleNamespace(ResourceManager=lambda: fake_rm))
    monkeypatch.setattr("time.sleep", lambda _s: None)

    idn = clear_b1500_status_for_wgfmu_open("GPIB1::17::INSTR")

    assert "B1500A" in idn
    assert "*CLS" not in fake_rm.inst.writes
    assert fake_rm.inst.writes == ["ERRX?", "ERRX?", "ERRX?"]
    assert fake_rm.inst.closed
    assert fake_rm.closed


# ---------------------------------------------------------------- feature map
def test_scaffold_feature_map_advertises_new_capabilities():
    feats = list_wgfmu_scaffold_features()
    assert "iv_sweep_config" in feats["config"]
    assert "wakeup_config" in feats["config"]
    assert "real_backend_ctypes_binding" in feats["backend"]
    assert "pulse_train_iv_sweep" in feats["workflow"]
    assert "multistage_wakeup_with_readout" in feats["workflow"]
    assert "iv_curve_csv" in feats["export"]
    assert "wakeup_cycles_csv" in feats["export"]
