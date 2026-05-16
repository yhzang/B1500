"""Pulse-train builder for WGFMU multi-step waveforms.

The B1530A WGFMU 'pattern' is a list of ``(dtime, voltage)`` vectors anchored to
an initial voltage. To run an IV sweep with short pulses, we need to compose
several pulses on a single time axis along with their measure events.

This module is **backend-agnostic**: it produces a declarative pattern that any
``WgfmuBackend`` can replay via ``create_pattern`` / ``add_vector`` /
``set_measure_event`` / ``add_sequence``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

import numpy as np


@dataclass
class PulseSegment:
    """One rectangular pulse with a base hold afterwards.

    Layout (anchored to the previous segment's end at v_base):
      rise(t_rise, v_base->v_pulse) → high(t_high, v_pulse)
      → fall(t_fall, v_pulse->v_base) → base(t_base, v_base)
    """

    v_pulse: float
    t_rise_s: float = 1e-6
    t_high_s: float = 2e-6
    t_fall_s: float = 1e-6
    t_base_s: float = 2e-6
    label: Optional[str] = None
    measure_during_high: bool = True
    measure_points: int = 20
    measure_average_s: float = 100e-9


@dataclass
class PulseTrainPlan:
    """The output of :class:`PulseTrainBuilder.build`.

    ``vectors`` is a list of ``(dtime_s, voltage_V)`` pairs ready for
    ``backend.add_vector``. ``measure_events`` is a list of
    ``(event_name, time_s, points, interval_s, average_s, raw_data_mode)``
    tuples ready for ``backend.set_measure_event``. Both share the same time
    origin: the start of the pattern (after ``v_init`` is applied).
    """

    pattern_name: str
    v_init: float
    v_base: float
    vectors: list[tuple[float, float]] = field(default_factory=list)
    measure_events: list[tuple[str, float, int, float, float, str]] = field(
        default_factory=list
    )
    # Per-segment metadata for downstream visualization / parsing
    segments: list[dict] = field(default_factory=list)

    @property
    def total_duration_s(self) -> float:
        return sum(dt for dt, _v in self.vectors)

    def waveform_samples(self, dt_s: float = 1e-7) -> tuple[np.ndarray, np.ndarray]:
        """Reconstruct a dense (time, voltage) sampling of the planned waveform.

        Useful for visualization and unit-tests that want to verify the shape
        without actually running the instrument.
        """
        times: list[float] = [0.0]
        volts: list[float] = [self.v_init]
        t = 0.0
        v = self.v_init
        for d_t, target_v in self.vectors:
            if d_t <= 0:
                v = target_v
                continue
            n = max(int(np.ceil(d_t / dt_s)), 1)
            for k in range(1, n + 1):
                frac = k / n
                times.append(t + frac * d_t)
                volts.append(v + frac * (target_v - v))
            t += d_t
            v = target_v
        return np.asarray(times), np.asarray(volts)


class PulseTrainBuilder:
    """Compose a list of :class:`PulseSegment` into a single WGFMU pattern.

    All times are in seconds, all voltages in volts. ``v_init`` is the channel
    quiescent voltage applied before the pattern starts; ``v_base`` is the
    inter-pulse hold value (typically equal to ``v_init``).
    """

    def __init__(
        self,
        *,
        pattern_name: str = "iv_pulse_train",
        v_init: float = 0.0,
        v_base: float = 0.0,
    ):
        self.pattern_name = pattern_name
        self.v_init = v_init
        self.v_base = v_base

    def build(self, segments: Iterable[PulseSegment]) -> PulseTrainPlan:
        segs = list(segments)
        plan = PulseTrainPlan(
            pattern_name=self.pattern_name,
            v_init=self.v_init,
            v_base=self.v_base,
        )

        t_cursor = 0.0
        for idx, seg in enumerate(segs):
            label = seg.label or f"pulse_{idx:03d}"

            # 1) rise to v_pulse
            plan.vectors.append((seg.t_rise_s, seg.v_pulse))
            t_after_rise = t_cursor + seg.t_rise_s
            # 2) hold high
            plan.vectors.append((seg.t_high_s, seg.v_pulse))
            t_after_high = t_after_rise + seg.t_high_s
            # 3) fall back to v_base
            plan.vectors.append((seg.t_fall_s, plan.v_base))
            t_after_fall = t_after_high + seg.t_fall_s
            # 4) base hold
            plan.vectors.append((seg.t_base_s, plan.v_base))
            t_after_base = t_after_fall + seg.t_base_s

            if seg.measure_during_high and seg.measure_points > 0:
                # Place measurement window centred inside the high portion,
                # leaving a small guard near the rise/fall edges.
                guard = min(seg.t_rise_s, seg.t_fall_s, seg.t_high_s * 0.1)
                meas_window = max(seg.t_high_s - 2 * guard, seg.t_high_s * 0.5)
                interval = meas_window / max(seg.measure_points, 1)
                start_time = t_after_rise + guard
                plan.measure_events.append(
                    (
                        label,
                        start_time,
                        seg.measure_points,
                        interval,
                        min(seg.measure_average_s, interval * 0.9),
                        "averaged",
                    )
                )

            plan.segments.append(
                {
                    "index": idx,
                    "label": label,
                    "v_pulse": seg.v_pulse,
                    "t_start_s": t_cursor,
                    "t_high_start_s": t_after_rise,
                    "t_high_end_s": t_after_high,
                    "t_end_s": t_after_base,
                    "measure_points": seg.measure_points if seg.measure_during_high else 0,
                }
            )
            t_cursor = t_after_base

        return plan


def linear_voltage_segments(
    *,
    v_start: float,
    v_stop: float,
    n_points: int,
    t_rise_s: float = 1e-6,
    t_high_s: float = 2e-6,
    t_fall_s: float = 1e-6,
    t_base_s: float = 2e-6,
    measure_points: int = 20,
    measure_average_s: float = 100e-9,
    measure_during_high: bool = True,
) -> list[PulseSegment]:
    """Helper: build a linear sweep of N pulses from v_start to v_stop."""
    voltages = np.linspace(v_start, v_stop, max(n_points, 2))
    out: list[PulseSegment] = []
    for i, v in enumerate(voltages):
        out.append(
            PulseSegment(
                v_pulse=float(v),
                t_rise_s=t_rise_s,
                t_high_s=t_high_s,
                t_fall_s=t_fall_s,
                t_base_s=t_base_s,
                label=f"vg_{i:03d}_{v:+.3f}V".replace(".", "p"),
                measure_during_high=measure_during_high,
                measure_points=measure_points,
                measure_average_s=measure_average_s,
            )
        )
    return out


__all__ = [
    "PulseSegment",
    "PulseTrainPlan",
    "PulseTrainBuilder",
    "linear_voltage_segments",
]
