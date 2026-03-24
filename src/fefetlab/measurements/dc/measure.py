"""Single-point DC measurement functions."""

import time
from typing import Dict, Optional
from dataclasses import dataclass, asdict

from ...b1500 import B1500, B1500Error
from .config import DCSweepConfig


@dataclass
class DCMeasureResult:
    """Result from a single DC measurement point.

    Attributes:
        vg_set: Gate voltage set point (V)
        vd_set: Drain voltage set point (V)
        vs_set: Source voltage set point (V)
        ig_A: Gate current measured (A), None if error
        id_A: Drain current measured (A), None if error
        is_A: Source current measured (A), None if error
        err: Error code/message from instrument
        status: 'ok' or 'invalid'
        timestamp: Unix timestamp of measurement
    """
    vg_set: float
    vd_set: float
    vs_set: float
    ig_A: Optional[float] = None
    id_A: Optional[float] = None
    is_A: Optional[float] = None
    err: Optional[str] = None
    status: str = "ok"
    timestamp: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for DataFrame/JSON export."""
        return asdict(self)


class DCMeasurePoint:
    """Single-point DC measurement executor.

    Handles voltage setting, delay, current measurement, and error handling
    for a single measurement point in a DC sweep.
    """

    def __init__(self, b1500: B1500, config: DCSweepConfig):
        """Initialize measurement executor.

        Args:
            b1500: B1500 instrument instance
            config: DC sweep configuration
        """
        self.b1500 = b1500
        self.config = config
        self.ch_g = config.channels['G'].channel
        self.ch_d = config.channels['D'].channel
        self.ch_s = config.channels['S'].channel

    def measure(self, vg: float, vd: float, vs: float) -> DCMeasureResult:
        """Execute a single-point DC measurement.

        Sets voltages on G/D/S, waits, measures currents, then returns to zero.

        Args:
            vg: Gate voltage (V)
            vd: Drain voltage (V)
            vs: Source voltage (V)

        Returns:
            DCMeasureResult containing measured currents and status
        """
        result = DCMeasureResult(
            vg_set=vg,
            vd_set=vd,
            vs_set=vs,
            timestamp=time.time()
        )

        try:
            # Apply voltages
            cfg_g = self.config.channels['G']
            cfg_d = self.config.channels['D']
            cfg_s = self.config.channels['S']

            self.b1500.dv(self.ch_g, cfg_g.vrange, vg, cfg_g.i_comp)
            self.b1500.dv(self.ch_d, cfg_d.vrange, vd, cfg_d.i_comp)
            self.b1500.dv(self.ch_s, cfg_s.vrange, vs, cfg_s.i_comp)

            # Wait for settling
            time.sleep(self.config.delay_s)

            # Measure currents
            result.ig_A = self.b1500.ti(self.ch_g)
            result.id_A = self.b1500.ti(self.ch_d)
            result.is_A = self.b1500.ti(self.ch_s)

            # Check instrument errors
            result.err = self.b1500.errx()

        except B1500Error as e:
            result.status = "invalid"
            result.err = str(e)
            result.ig_A = None
            result.id_A = None
            result.is_A = None

        except Exception as e:
            result.status = "invalid"
            result.err = repr(e)

        finally:
            # Always return to zero and disable channels
            self._safe_zero_and_cl()

        return result

    def _safe_zero_and_cl(self):
        """Safely zero and disable channels, ignoring errors."""
        channels = [self.ch_g, self.ch_d, self.ch_s]
        try:
            self.b1500.dz(channels)
        except Exception:
            pass

        try:
            self.b1500.cl(channels)
        except Exception:
            pass
