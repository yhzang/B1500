"""High-level API for DC sweeps - simplified interface."""

from pathlib import Path
from typing import List, Optional
import pandas as pd

from ...instruments.visa_session import VisaSession
from ...b1500 import B1500
from .config import DCSweepConfig
from .sweep import DCSweepRunner
from .export import DCDataExporter


class DCSweepAPI:
    """High-level API for executing and exporting DC sweeps.

    Provides simple methods for common sweep patterns (Id-Vg, Id-Vd)
    with automatic configuration, execution, and data export.

    Example:
        >>> from fefetlab.dc import DCSweepAPI
        >>> with VisaSession(visa_config) as session:
        ...     api = DCSweepAPI(session, ch_g=4, ch_d=5, ch_s=6)
        ...     result = api.run_idvg_sweep(
        ...         vg_points=[0.0, -0.2, -0.4],
        ...         vd_fixed=0.1,
        ...         vs_fixed=0.0
        ...     )
        ...     print(f"Data saved to: {result['run_dir']}")
    """

    def __init__(
        self,
        session: VisaSession,
        ch_g: int,
        ch_d: int,
        ch_s: int,
        config: Optional[DCSweepConfig] = None,
        export_dir: Path = Path("runs")
    ):
        """Initialize DC sweep API.

        Args:
            session: Active VISA session
            ch_g: Gate channel number
            ch_d: Drain channel number
            ch_s: Source channel number
            config: Optional custom sweep config (defaults to notebook settings)
            export_dir: Base directory for saving results
        """
        self.b1500 = B1500(session)
        self.config = config or DCSweepConfig.from_notebooks_default(ch_g, ch_d, ch_s)
        self.runner = DCSweepRunner(self.b1500, self.config)
        self.exporter = DCDataExporter(export_dir)

    def run_idvg_sweep(
        self,
        vg_points: List[float],
        vd_fixed: float,
        vs_fixed: float,
        auto_export: bool = True,
        verbose: bool = True
    ) -> dict:
        """Execute Id-Vg sweep (transfer characteristics).

        Args:
            vg_points: List of gate voltages to sweep
            vd_fixed: Fixed drain voltage
            vs_fixed: Fixed source voltage
            auto_export: Automatically save results to CSV/JSON/QC
            verbose: Print progress information

        Returns:
            Dict with 'df' (DataFrame), and if auto_export=True:
            'run_dir', 'data_paths', 'qc_df'
        """
        if verbose:
            print(f"Starting Id-Vg sweep: {len(vg_points)} points")
            print(f"Vd={vd_fixed} V, Vs={vs_fixed} V")

        def progress(current, total):
            if verbose:
                print(f"Progress: {current}/{total}", end="\r")

        df = self.runner.sweep_vg(
            vg_points=vg_points,
            vd_fixed=vd_fixed,
            vs_fixed=vs_fixed,
            progress_callback=progress if verbose else None
        )

        if verbose:
            print(f"\nSweep completed: {len(df)} measurements")

        result = {'df': df}

        if auto_export:
            export_result = self.exporter.export_sweep(df, "idvg_sweep")
            result.update(export_result)
            if verbose:
                print(f"Results saved to: {export_result['run_dir']}")

        return result

    def run_idvd_sweep(
        self,
        vg_points: List[float],
        vd_points: List[float],
        vs_fixed: float,
        auto_export: bool = True,
        verbose: bool = True
    ) -> dict:
        """Execute Id-Vd sweep (output characteristics).

        Args:
            vg_points: List of gate voltages
            vd_points: List of drain voltages to sweep
            vs_fixed: Fixed source voltage
            auto_export: Automatically save results to CSV/JSON/QC
            verbose: Print progress information

        Returns:
            Dict with 'df' (DataFrame), and if auto_export=True:
            'run_dir', 'data_paths', 'qc_df'
        """
        if verbose:
            total = len(vg_points) * len(vd_points)
            print(f"Starting Id-Vd sweep: {total} points")
            print(f"Vg points: {vg_points}")
            print(f"Vd points: {vd_points}, Vs={vs_fixed} V")

        def progress(current, total):
            if verbose:
                print(f"Progress: {current}/{total}", end="\r")

        df = self.runner.sweep_vd(
            vg_points=vg_points,
            vd_points=vd_points,
            vs_fixed=vs_fixed,
            progress_callback=progress if verbose else None
        )

        if verbose:
            print(f"\nSweep completed: {len(df)} measurements")

        result = {'df': df}

        if auto_export:
            export_result = self.exporter.export_sweep(df, "idvd_sweep")
            result.update(export_result)
            if verbose:
                print(f"Results saved to: {export_result['run_dir']}")

        return result

    def run_custom_sweep(
        self,
        sweep_points: List[tuple[float, float, float]],
        sweep_name: str = "custom_sweep",
        auto_export: bool = True,
        verbose: bool = True
    ) -> dict:
        """Execute custom sweep pattern.

        Args:
            sweep_points: List of (Vg, Vd, Vs) tuples
            sweep_name: Name for the sweep (used in export directory)
            auto_export: Automatically save results
            verbose: Print progress

        Returns:
            Dict with 'df' and optionally export results
        """
        if verbose:
            print(f"Starting custom sweep: {len(sweep_points)} points")

        def progress(current, total):
            if verbose:
                print(f"Progress: {current}/{total}", end="\r")

        df = self.runner.sweep_custom(
            sweep_points=sweep_points,
            progress_callback=progress if verbose else None
        )

        if verbose:
            print(f"\nSweep completed: {len(df)} measurements")

        result = {'df': df}

        if auto_export:
            export_result = self.exporter.export_sweep(df, sweep_name)
            result.update(export_result)
            if verbose:
                print(f"Results saved to: {export_result['run_dir']}")

        return result
