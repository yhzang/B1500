"""WGFMU module for fefetlab — pulse measurement, IV sweeps, wake-up runs.

This package layers on top of the Keysight B1530A WGFMU2 instrument library.

Backends (parallel to DC's mock/real split):
  * :class:`DummyWgfmuBackend`  — deterministic synthetic data for unit tests
                                   and mock-path smoke (no instrument).
  * :class:`RealWgfmuBackend`   — ctypes binding to ``wgfmu.dll``. The real
                                   path used on the test-bench machine.
                                   Safe to *import* on any OS; the DLL is only
                                   resolved when ``.load()`` (or any session
                                   call) is invoked.

Measurement protocols (built on backends + pulse builder):
  * :class:`WgfmuSmokeRunner`     — single-pulse smoke (kept stable).
  * :class:`WgfmuIVSweepRunner`   — pulse-train IV sweep.
  * :class:`WgfmuWakeupRunner`    — multi-stage wake-up with low-disturb readout.

Builders / helpers:
  * :class:`PulseSegment`, :class:`PulseTrainBuilder`,
    :func:`linear_voltage_segments` — declarative pulse-train construction.
"""

from .audit_backend import AuditBackend
from .backend import DummyWgfmuBackend, WgfmuBackend
from .config import MeasureEventParams, PulsePatternParams, WgfmuSmokeConfig
from .export import WgfmuDataExporter
from .iv_sweep import WgfmuIVSweepConfig, WgfmuIVSweepResult, WgfmuIVSweepRunner
from .pulse_builder import (
    PulseSegment,
    PulseTrainBuilder,
    PulseTrainPlan,
    linear_voltage_segments,
)
from .real_backend import RealWgfmuBackend, WgfmuLibraryError
from .smoke import WgfmuSmokeResult, WgfmuSmokeRunner
from .wakeup import (
    WakeupReadout,
    WakeupStage,
    WgfmuWakeupConfig,
    WgfmuWakeupResult,
    WgfmuWakeupRunner,
)

# Notebook compatibility aliases during the migration period.
WgfmuLib = WgfmuBackend
DummyWgfmuLib = DummyWgfmuBackend


def list_wgfmu_scaffold_features() -> dict[str, list[str]]:
    """Return a compact feature map of the current WGFMU module."""
    return {
        "config": [
            "pulse_pattern_params",
            "measure_event_params",
            "smoke_run_config",
            "iv_sweep_config",
            "wakeup_config",
        ],
        "backend": [
            "abstract_backend_interface",
            "dummy_backend_for_local_development",
            "audit_backend_for_hardware_free_dry_run",
            "real_backend_ctypes_binding",
            "notebook_compatibility_aliases",
        ],
        "workflow": [
            "channel_discovery",
            "offline_pattern_setup",
            "online_channel_setup",
            "execute_and_wait",
            "result_fetch_and_column_normalization",
            "basic_qc",
            "export_and_cleanup",
            "pulse_train_iv_sweep",
            "multistage_wakeup_with_readout",
        ],
        "export": [
            "run_directory_creation",
            "parsed_csv",
            "qc_csv",
            "meta_json",
            "ascii_setup_export",
            "iv_curve_csv",
            "wakeup_cycles_csv",
            "plan_json",
        ],
    }


__all__ = [
    # core
    "PulsePatternParams",
    "MeasureEventParams",
    "WgfmuSmokeConfig",
    "WgfmuBackend",
    "DummyWgfmuBackend",
    "AuditBackend",
    "RealWgfmuBackend",
    "WgfmuLibraryError",
    "WgfmuLib",
    "DummyWgfmuLib",
    "WgfmuDataExporter",
    "WgfmuSmokeRunner",
    "WgfmuSmokeResult",
    "list_wgfmu_scaffold_features",
    # pulse train
    "PulseSegment",
    "PulseTrainBuilder",
    "PulseTrainPlan",
    "linear_voltage_segments",
    # IV sweep
    "WgfmuIVSweepConfig",
    "WgfmuIVSweepResult",
    "WgfmuIVSweepRunner",
    # wakeup
    "WakeupStage",
    "WakeupReadout",
    "WgfmuWakeupConfig",
    "WgfmuWakeupResult",
    "WgfmuWakeupRunner",
]


from .setup_helpers import (
    ensure_wgfmu_dll_path,
    autodetect_visa_addr,
    clear_b1500_status_for_wgfmu_open,
    autodetect_wgfmu_chan,
)
