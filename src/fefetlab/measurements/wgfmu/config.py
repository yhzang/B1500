"""Configuration models for WGFMU smoke workflows."""

from dataclasses import dataclass


@dataclass
class PulsePatternParams:
    """Pulse waveform definition for a single WGFMU channel."""

    chan_id: int
    pattern_name: str
    v_init: float
    v_pulse: float
    t_rise_s: float
    t_high_s: float
    t_fall_s: float
    t_base_s: float
    repeat_count: int = 1


@dataclass
class MeasureEventParams:
    """Measurement-event definition bound to a WGFMU pattern."""

    event_name: str
    start_time_s: float
    points: int
    interval_s: float
    average_s: float
    raw_data_mode: str = "averaged"


@dataclass
class WgfmuSmokeConfig:
    """Run-level configuration for the WGFMU smoke path.

    This remains intentionally lightweight for now. It captures the stable
    parameters already used in notebook prototypes while leaving room for a
    future, richer production config.
    """

    label: str
    operation_mode: str = "FASTIV"
    force_voltage_range: str = "AUTO"
    measure_mode: str = "CURRENT"
    measure_current_range: str = "1MA"
    measure_voltage_range: str = "10V"
    measure_enabled: bool = True
    treat_warning_as_error: bool = False
    timeout_s: float = 30.0
    notes: str = ""
