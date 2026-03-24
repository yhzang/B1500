"""Generic DC sweep runner for various sweep types."""

from typing import List, Callable, Optional
import pandas as pd

from ...b1500 import B1500
from .config import DCSweepConfig
from .measure import DCMeasurePoint, DCMeasureResult


class DCSweepRunner:
    """Generic DC sweep executor supporting various sweep patterns.

    Provides flexible sweep execution for:
    - Id-Vg: Fixed Vd/Vs, sweep Vg
    - Id-Vd: Fixed Vs, sweep Vg×Vd
    - Custom sweep patterns
    """

    def __init__(self, b1500: B1500, config: DCSweepConfig):
        """Initialize sweep runner.

        Args:
            b1500: B1500 instrument instance
            config: DC sweep configuration
        """
        self.b1500 = b1500
        self.config = config
        self.measurer = DCMeasurePoint(b1500, config)
        self._configure_instrument()

    def _configure_instrument(self):
        """Apply instrument settings from config."""
        self.b1500.fmt(self.config.fmt_mode)
        self.b1500.av(self.config.av_count, self.config.av_mode)
        self.b1500.fl(self.config.fl_mode)

        channels = [ch.channel for ch in self.config.channels.values()]
        self.b1500.cn(channels)

    def sweep_vg(
        self,
        vg_points: List[float],
        vd_fixed: float,
        vs_fixed: float,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> pd.DataFrame:
        """Execute Id-Vg sweep (fixed Vd/Vs, sweep Vg).

        Args:
            vg_points: List of gate voltages to sweep
            vd_fixed: Fixed drain voltage
            vs_fixed: Fixed source voltage
            progress_callback: Optional callback(current, total) for progress

        Returns:
            DataFrame with columns: vg_set, vd_set, vs_set, ig_A, id_A, is_A, err, status, timestamp
        """
        results = []
        total = len(vg_points)

        for idx, vg in enumerate(vg_points):
            result = self.measurer.measure(vg, vd_fixed, vs_fixed)
            results.append(result.to_dict())

            if progress_callback:
                progress_callback(idx + 1, total)

        return pd.DataFrame(results)

    def sweep_vd(
        self,
        vg_points: List[float],
        vd_points: List[float],
        vs_fixed: float,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> pd.DataFrame:
        """Execute Id-Vd sweep (fixed Vs, sweep Vg×Vd).

        Args:
            vg_points: List of gate voltages
            vd_points: List of drain voltages to sweep
            vs_fixed: Fixed source voltage
            progress_callback: Optional callback(current, total) for progress

        Returns:
            DataFrame with measurement results
        """
        results = []
        total = len(vg_points) * len(vd_points)
        count = 0

        for vg in vg_points:
            for vd in vd_points:
                result = self.measurer.measure(vg, vd, vs_fixed)
                results.append(result.to_dict())

                count += 1
                if progress_callback:
                    progress_callback(count, total)

        return pd.DataFrame(results)

    def sweep_custom(
        self,
        sweep_points: List[tuple[float, float, float]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> pd.DataFrame:
        """Execute custom sweep pattern.

        Args:
            sweep_points: List of (Vg, Vd, Vs) tuples
            progress_callback: Optional callback(current, total) for progress

        Returns:
            DataFrame with measurement results
        """
        results = []
        total = len(sweep_points)

        for idx, (vg, vd, vs) in enumerate(sweep_points):
            result = self.measurer.measure(vg, vd, vs)
            results.append(result.to_dict())

            if progress_callback:
                progress_callback(idx + 1, total)

        return pd.DataFrame(results)
