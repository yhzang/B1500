"""Data export and QC (Quality Control) generation for DC sweeps."""

import time
from pathlib import Path
from typing import Optional, List
import pandas as pd


class DCDataExporter:
    """Export DC sweep data and generate QC reports.

    Handles saving measurement data to CSV/JSON and generating
    quality control reports based on error status and data validity.
    """

    def __init__(self, base_dir: Path = Path("runs")):
        """Initialize exporter.

        Args:
            base_dir: Base directory for saving runs (default: ./runs)
        """
        self.base_dir = base_dir

    def create_run_dir(self, sweep_type: str) -> Path:
        """Create timestamped run directory.

        Args:
            sweep_type: Type of sweep (e.g., 'idvg_sweep', 'idvd_sweep')

        Returns:
            Path to created run directory
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        run_dir = self.base_dir / f"{timestamp}_{sweep_type}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def save_data(
        self,
        df: pd.DataFrame,
        run_dir: Path,
        basename: str = "data"
    ) -> dict[str, Path]:
        """Save DataFrame to CSV and JSON.

        Args:
            df: DataFrame to save
            run_dir: Directory to save files
            basename: Base filename (without extension)

        Returns:
            Dict with 'csv' and 'json' keys mapping to saved file paths
        """
        paths = {}

        csv_path = run_dir / f"{basename}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        paths['csv'] = csv_path

        json_path = run_dir / f"{basename}.json"
        df.to_json(json_path, orient="records", force_ascii=False, indent=2)
        paths['json'] = json_path

        return paths

    def generate_qc(
        self,
        df: pd.DataFrame,
        run_dir: Optional[Path] = None,
        basename: str = "qc"
    ) -> pd.DataFrame:
        """Generate QC report from measurement data.

        Checks for instrument errors and missing data.

        Args:
            df: DataFrame with measurement results
            run_dir: Optional directory to save QC CSV
            basename: Base filename for QC file

        Returns:
            DataFrame with QC results
        """
        qc_records = []

        for _, row in df.iterrows():
            issues = []

            # Check instrument error
            err_str = str(row.get("err", "")).strip()
            if err_str and err_str not in ["0", '0,"No Error."', "0 (No Error)"]:
                issues.append("instrument_error")

            # Check for missing current data
            if pd.isna(row.get("id_A")):
                issues.append("missing_id")
            if pd.isna(row.get("ig_A")):
                issues.append("missing_ig")
            if pd.isna(row.get("is_A")):
                issues.append("missing_is")

            # Check status field
            if row.get("status") != "ok":
                issues.append("measurement_failed")

            qc_records.append({
                "vg_set": row.get("vg_set"),
                "vd_set": row.get("vd_set"),
                "vs_set": row.get("vs_set"),
                "status": "ok" if not issues else "suspect",
                "issues": ";".join(issues) if issues else "",
                "timestamp": row.get("timestamp"),
            })

        qc_df = pd.DataFrame(qc_records)

        if run_dir is not None:
            qc_path = run_dir / f"{basename}.csv"
            qc_df.to_csv(qc_path, index=False, encoding="utf-8-sig")

        return qc_df

    def export_sweep(
        self,
        df: pd.DataFrame,
        sweep_type: str,
        include_qc: bool = True
    ) -> dict:
        """Complete export workflow: create dir, save data, generate QC.

        Args:
            df: DataFrame with measurement results
            sweep_type: Type of sweep for directory naming
            include_qc: Whether to generate QC report

        Returns:
            Dict with 'run_dir', 'data_paths', and optionally 'qc_df'
        """
        run_dir = self.create_run_dir(sweep_type)
        data_paths = self.save_data(df, run_dir)

        result = {
            'run_dir': run_dir,
            'data_paths': data_paths,
        }

        if include_qc:
            qc_df = self.generate_qc(df, run_dir)
            result['qc_df'] = qc_df

        return result
